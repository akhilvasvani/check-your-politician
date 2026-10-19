#!/usr/bin/env python3
"""Build a metadata-only corpus-completeness manifest from PrimeGov.

M3.0 deliberately stops before caption download, parsing, embedding, or
database writes. Existing canonical transcript JSONs are inspected to mark
already-published meetings; newly discovered videos remain `discovered` with
caption_status=`not_checked_m3_0` until the separately approved M3.1 preflight.

The output is deterministic for a fixed PrimeGov fixture and canonical data
directory. Network access is only used to read PrimeGov's public meeting list.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import parse_qs, urlparse


REPO = Path(__file__).resolve().parent.parent.parent
DATA_DIR = REPO / "data" / "transcripts"
DEFAULT_TAXONOMY = Path(__file__).with_name("committee_taxonomy.json")
DEFAULT_OUTPUT = DATA_DIR / "corpus_manifest_m3.json"
PRIMEGOV_URL = (
    "https://lacity.primegov.com/api/v2/PublicPortal/"
    "ListArchivedMeetingsByDays?days={days}"
)
PIPELINE_STATES = [
    "discovered",
    "caption_preflighted",
    "caption_fetched",
    "parsed",
    "embedded",
    "indexed",
    "published",
    "blocked",
]
NON_TRANSCRIPT_JSONS = {
    "corpus_manifest_m3.json",
    "eval_queries.json",
    "eval_queries_m3_3.json",
    "eval_queries_public_comment.json",
    "eval_results_m1.4.json",
    "eval_results_m2.json",
    "roster.json",
}


def extract_youtube_id(url: str) -> str | None:
    """Extract an exact 11-character YouTube video ID from common URL forms."""
    if not url:
        return None
    parsed = urlparse(url)
    host = parsed.netloc.lower().removeprefix("www.")
    candidate: str | None = None
    if host in {"youtube.com", "m.youtube.com"}:
        candidate = (parse_qs(parsed.query).get("v") or [None])[0]
        if not candidate and parsed.path.startswith("/shorts/"):
            candidate = parsed.path.split("/", 2)[2]
    elif host == "youtu.be":
        candidate = parsed.path.lstrip("/").split("/", 1)[0]
    if candidate and re.fullmatch(r"[A-Za-z0-9_-]{11}", candidate):
        return candidate
    return None


def load_taxonomy(path: Path) -> dict[int, dict[str, str]]:
    raw = json.loads(path.read_text())
    return {int(key): value for key, value in raw["bodies"].items()}


def fetch_primegov(days: int) -> list[dict[str, Any]]:
    req = urllib.request.Request(
        PRIMEGOV_URL.format(days=days),
        headers={"User-Agent": "check-your-politician/1.0"},
    )
    with urllib.request.urlopen(req, timeout=30) as response:
        return json.load(response)


def load_existing(data_dir: Path) -> dict[str, dict[str, Any]]:
    existing: dict[str, dict[str, Any]] = {}
    for path in sorted(data_dir.glob("*.json")):
        if path.name in NON_TRANSCRIPT_JSONS:
            continue
        try:
            doc = json.loads(path.read_text())
        except (json.JSONDecodeError, OSError):
            continue
        video_id = doc.get("video_id")
        if not video_id:
            continue
        officials = sorted(
            {
                row["resolved_official_id"]
                for row in doc.get("utterances", [])
                if row.get("resolved_official_id")
            }
        )
        attributed_turn_count = sum(
            1
            for row in doc.get("utterances", [])
            if row.get("resolved_official_id")
        )
        public_comment_present = any(
            row.get("resolved_role") == "public-speaker"
            for row in doc.get("utterances", [])
        )
        existing[video_id] = {
            "artifact_path": str(path.relative_to(REPO)),
            "artifact_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "utterance_count": doc.get("utterance_count"),
            "attributed_turn_count": attributed_turn_count,
            "public_comment_present": public_comment_present,
            "official_ids": officials,
            "canonical_primegov_id": doc.get("primegov_id"),
            "canonical_title": doc.get("title"),
            "language_code": doc.get("language_code"),
        }
    return existing


def exclusion_reason(row: dict[str, Any], taxonomy: dict[int, dict[str, str]]) -> str | None:
    title = (row.get("title") or "").strip()
    if int(row.get("committeeId") or -1) not in taxonomy:
        if "ad hoc" in title.lower():
            return "ad_hoc_body"
        if "advisory" in title.lower():
            return "advisory_body"
        if "commission" in title.lower():
            return "commission"
        return "body_not_in_standing_committee_taxonomy"
    if re.search(r"\bSAP\b", title, flags=re.IGNORECASE):
        return "sap_duplicate"
    if title.upper().startswith("CANCELLED"):
        return "cancelled"
    return None


def normalized_meeting_type(title: str, body_type: str) -> str:
    lowered = title.lower()
    if body_type == "city_council":
        if "recessed from" in lowered:
            return "recessed_council"
        if "special" in lowered:
            return "special_council"
        return "regular_council"
    if "special" in lowered:
        return "special_standing_committee"
    return "standing_committee"


CHECKPOINT_FIELDS = (
    "pipeline_state",
    "pipeline_state_basis",
    "caption_status",
    "caption_language",
    "caption_preflighted_at",
    "caption_fetched_at",
    "parsed_at",
    "embedded_at",
    "indexed_at",
    "published_at",
    "last_error",
    "retryable",
    "missing_reason",
    "ingest_disposition",
    "artifact_path",
    "artifact_sha256",
    "utterance_count",
    "chunk_count",
    "attributed_turn_count",
    "public_comment_present",
    "official_ids",
    "canonical_primegov_id",
    "canonical_title",
    "embedding_model",
    "embedding_version",
)


def prior_records_by_primegov_id(manifest: dict[str, Any] | None) -> dict[int, dict[str, Any]]:
    """Index a prior manifest's rows for checkpoint preservation.

    A checkpoint is only reused when both the PrimeGov ID and the exact media
    ID still agree. This prevents a changed PrimeGov video URL from inheriting
    stale parse/index status from a different recording.
    """
    if not manifest:
        return {}
    records: dict[int, dict[str, Any]] = {}
    for item in manifest.get("meetings", []):
        try:
            records[int(item["primegov_id"])] = item
        except (KeyError, TypeError, ValueError):
            continue
    return records


def _preserve_checkpoint(item: dict[str, Any], prior: dict[str, Any] | None) -> None:
    if not prior or prior.get("video_id") != item.get("video_id"):
        return
    for field in CHECKPOINT_FIELDS:
        if field in prior:
            item[field] = prior[field]


def build_manifest(
    rows: Iterable[dict[str, Any]],
    taxonomy: dict[int, dict[str, str]],
    existing: dict[str, dict[str, Any]],
    *,
    days: int,
    generated_at: str,
    prior_manifest: dict[str, Any] | None = None,
) -> dict[str, Any]:
    meetings: list[dict[str, Any]] = []
    exclusions = Counter()
    video_to_primegov_ids: dict[str, list[int]] = {}
    prior_by_id = prior_records_by_primegov_id(prior_manifest)

    for row in rows:
        reason = exclusion_reason(row, taxonomy)
        if reason:
            exclusions[reason] += 1
            continue

        committee_id = int(row["committeeId"])
        body = taxonomy[committee_id]
        title = (row.get("title") or "").strip()
        video_url = row.get("videoUrl") or ""
        video_id = extract_youtube_id(video_url)
        prior = existing.get(video_id or "")

        if video_id:
            video_to_primegov_ids.setdefault(video_id, []).append(int(row["id"]))

        if prior:
            state = "published"
            caption_status = "available_indexed"
            missing_reason = None
            disposition = "already_published"
            # Discovery is local-only: an artifact proves it was produced, not
            # that a database row currently exists. M3.1 verifies indexing
            # separately before it claims an online publication boundary.
            state_basis = "canonical_artifact_present"
        elif video_id:
            state = "discovered"
            caption_status = "not_checked_m3_0"
            missing_reason = None
            disposition = "m3_1_caption_preflight"
            state_basis = "primegov_metadata_only"
        else:
            state = "blocked"
            caption_status = "unavailable_no_video_url"
            missing_reason = "primegov_row_has_no_youtube_video"
            disposition = "blocked_no_video"
            state_basis = "primegov_metadata_only"

        meetings.append(
            {
                "primegov_id": int(row["id"]),
                "committee_id": committee_id,
                "title": title,
                "normalized_body": body["canonical_name"],
                "body_type": body["body_type"],
                "meeting_type": normalized_meeting_type(title, body["body_type"]),
                "meeting_date": (row.get("dateTime") or "")[:10],
                "date_time": row.get("dateTime"),
                "primegov_meeting_state": row.get("meetingState"),
                "video_url": video_url or None,
                "video_id": video_id,
                "pipeline_state": state,
                "pipeline_state_basis": state_basis,
                "discovered_at": generated_at,
                "caption_status": caption_status,
                "caption_language": prior.get("language_code") if prior else None,
                "missing_reason": missing_reason,
                "ingest_disposition": disposition,
                "artifact_path": prior.get("artifact_path") if prior else None,
                "artifact_sha256": prior.get("artifact_sha256") if prior else None,
                "utterance_count": prior.get("utterance_count") if prior else None,
                "chunk_count": None,
                "attributed_turn_count": (
                    prior.get("attributed_turn_count") if prior else None
                ),
                "public_comment_present": (
                    prior.get("public_comment_present") if prior else None
                ),
                "official_ids": prior.get("official_ids", []) if prior else [],
                "canonical_primegov_id": prior.get("canonical_primegov_id") if prior else None,
                "canonical_title": prior.get("canonical_title") if prior else None,
                "caption_preflighted_at": None,
                "caption_fetched_at": None,
                "parsed_at": None,
                "embedded_at": None,
                "indexed_at": None,
                "published_at": None,
                "last_error": None,
                "retryable": bool(video_id and not prior),
                "embedding_model": "pplx-embed-v1-0.6b" if prior else None,
                "embedding_version": 1 if prior else None,
            }
        )
        _preserve_checkpoint(meetings[-1], prior_by_id.get(int(row["id"])))

    meetings.sort(key=lambda item: (item["date_time"] or "", item["primegov_id"]))
    collisions = [
        {"video_id": video_id, "primegov_ids": sorted(ids)}
        for video_id, ids in sorted(video_to_primegov_ids.items())
        if len(ids) > 1
    ]
    unique_videos = {item["video_id"] for item in meetings if item["video_id"]}
    new_videos = {
        item["video_id"]
        for item in meetings
        if item["video_id"]
        and item["pipeline_state"] != "published"
        and item["ingest_disposition"] != "already_published"
    }
    top_regular = sorted(
        (
            item
            for item in meetings
            if item["meeting_type"] == "regular_council" and item["video_id"]
        ),
        key=lambda item: item["date_time"] or "",
        reverse=True,
    )[:10]

    return {
        "manifest_version": 1,
        "generated_at": generated_at,
        "source_url": PRIMEGOV_URL.format(days=days),
        "window_days": days,
        "pipeline_states": PIPELINE_STATES,
        "scope_policy": {
            "include": [
                "City Council meetings",
                "standing committee meetings",
                "special meetings of included bodies",
            ],
            "exclude": [
                "SAP duplicate rows",
                "cancelled meetings",
                "ad hoc committees",
                "advisory committees",
                "boards and commissions",
            ],
        },
        "summary": {
            "in_scope_primegov_rows": len(meetings),
            "unique_youtube_videos": len(unique_videos),
            "already_published_videos": len(unique_videos - new_videos),
            "new_video_candidates": len(new_videos),
            "rows_without_youtube_video": sum(
                1 for item in meetings if not item["video_id"]
            ),
            "excluded_rows": sum(exclusions.values()),
            "excluded_by_reason": dict(sorted(exclusions.items())),
            "video_id_collisions": len(collisions),
        },
        "top_10_regular_council": [
            {
                "meeting_date": item["meeting_date"],
                "primegov_id": item["primegov_id"],
                "video_id": item["video_id"],
                "pipeline_state": item["pipeline_state"],
            }
            for item in top_regular
        ],
        "video_id_collisions": collisions,
        "meetings": meetings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build a metadata-only PrimeGov corpus manifest."
    )
    parser.add_argument("--days", type=int, default=90)
    parser.add_argument("--taxonomy", type=Path, default=DEFAULT_TAXONOMY)
    parser.add_argument("--data-dir", type=Path, default=DATA_DIR)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--fixture", type=Path)
    parser.add_argument(
        "--generated-at",
        help="Fixed ISO timestamp for reproducible fixture tests.",
    )
    args = parser.parse_args()

    rows = json.loads(args.fixture.read_text()) if args.fixture else fetch_primegov(args.days)
    prior_manifest = None
    if args.output.exists():
        try:
            prior_manifest = json.loads(args.output.read_text())
        except (json.JSONDecodeError, OSError):
            # A malformed old manifest should not block fresh discovery, but it
            # must not be silently treated as a usable checkpoint source.
            print(f"warning: cannot preserve checkpoints from {args.output}", file=sys.stderr)
    generated_at = args.generated_at or datetime.now(timezone.utc).isoformat()
    manifest = build_manifest(
        rows,
        load_taxonomy(args.taxonomy),
        load_existing(args.data_dir),
        days=args.days,
        generated_at=generated_at,
        prior_manifest=prior_manifest,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(manifest["summary"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
