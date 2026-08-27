#!/usr/bin/env python3
"""Local-only M3.1 manifest runner.

This module deliberately does not download captions, request embeddings, or
talk to Supabase. It provides the durable manifest and validation boundaries
that a separately approved online runner must use:

* group in-scope PrimeGov rows into one work item per YouTube video;
* ingest authenticated-caption *preflight results* supplied in a local file;
* checkpoint every changed work item atomically;
* retain all PrimeGov identities for a shared recording;
* report deterministic speaker-label coverage before any embedding call; and
* expose mockable embedding/indexing interfaces which reject partial results.

The only CLI action is applying a local preflight-result fixture to a local
manifest. It is safe to run in an offline environment.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Protocol

# Support the documented direct invocation from the la-money-votes root:
# `python scripts/transcripts/m3_1_ingest.py ...`.
if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from transcripts.build_transcripts import EMBED_DIM, EMBED_MODEL, Meeting
from transcripts.speaker_resolver import SpeakerResolver


TERMINAL_STATES = {"published", "blocked"}
ELIGIBLE_STATES = {"discovered", "caption_preflighted"}
CART_LANGUAGE_CODE = "en-uYU-mmqFLq8"
PREFLIGHT_EVIDENCE_FIELDS = (
    "track_name",
    "track_kind",
    "track_vss_id",
    "payload_status",
    "payload_bytes",
    "inspection_method",
    "asr_approved",
)


@dataclass(frozen=True)
class VideoWorkItem:
    """One media-level unit of M3.1 work, with all PrimeGov provenance."""

    video_id: str
    source_meetings: tuple[dict[str, Any], ...]
    pipeline_state: str

    @property
    def primegov_ids(self) -> tuple[int, ...]:
        return tuple(int(m["primegov_id"]) for m in self.source_meetings)


class Embedder(Protocol):
    def __call__(self, texts: list[str]) -> list[list[float]]: ...


class Indexer(Protocol):
    def __call__(self, rows: list[dict[str, Any]]) -> int: ...


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def atomic_write_json(path: Path, value: dict[str, Any]) -> None:
    """Atomically replace a manifest without leaving a partially-written file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, indent=2) + "\n")
    os.replace(tmp, path)


def refresh_current_state_summary(manifest: dict[str, Any]) -> None:
    """Refresh mutable state counts without rewriting discovery cardinality."""
    rows = manifest.get("meetings", [])
    row_counts = Counter(str(row.get("pipeline_state")) for row in rows)
    video_states: dict[str, str] = {}
    for row in rows:
        video_id = row.get("video_id")
        if not video_id:
            continue
        state = str(row.get("pipeline_state"))
        prior = video_states.setdefault(str(video_id), state)
        if prior != state:
            raise ValueError(
                f"{video_id} has divergent source-record states: {prior!r}, {state!r}"
            )
    video_counts = Counter(video_states.values())
    summary = manifest.setdefault("summary", {})
    summary["current_pipeline_state_rows"] = dict(sorted(row_counts.items()))
    summary["current_pipeline_state_videos"] = dict(sorted(video_counts.items()))


def _is_video_candidate(row: dict[str, Any]) -> bool:
    return bool(
        row.get("video_id")
        and row.get("pipeline_state") not in TERMINAL_STATES
        and row.get("retryable", False)
    )


def build_video_work_items(manifest: dict[str, Any]) -> list[VideoWorkItem]:
    """Return exactly one pending work item per video, never per PrimeGov row.

    Multiple PrimeGov records are retained in chronological/ID order. There is
    intentionally no "last record wins" canonicalization here.
    """
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in manifest.get("meetings", []):
        if _is_video_candidate(row):
            grouped.setdefault(str(row["video_id"]), []).append(row)

    work_items: list[VideoWorkItem] = []
    for video_id, rows in grouped.items():
        rows.sort(key=lambda row: (row.get("date_time") or "", int(row["primegov_id"])))
        states = {row.get("pipeline_state") for row in rows}
        # Mixed states for the same recording are unsafe: checkpointing must
        # advance every associated PrimeGov record together.
        if len(states) != 1:
            raise ValueError(f"{video_id} has divergent source-record states: {sorted(states)}")
        work_items.append(
            VideoWorkItem(
                video_id=video_id,
                source_meetings=tuple(rows),
                pipeline_state=states.pop(),
            )
        )
    return sorted(work_items, key=lambda item: item.video_id)


def source_meetings_metadata(work_item: VideoWorkItem) -> list[dict[str, Any]]:
    """Metadata safe to persist inside a canonical `{video_id}.json` artifact."""
    return [
        {
            "primegov_id": int(row["primegov_id"]),
            "title": row.get("title"),
            "meeting_date": row.get("meeting_date"),
            "date_time": row.get("date_time"),
            "committee_id": row.get("committee_id"),
            "normalized_body": row.get("normalized_body"),
            "body_type": row.get("body_type"),
            "meeting_type": row.get("meeting_type"),
            "video_id": work_item.video_id,
        }
        for row in work_item.source_meetings
    ]


def canonical_meeting_for_work_item(work_item: VideoWorkItem) -> Meeting:
    """Build the safe `Meeting` input for a future approved media fetch.

    The primary metadata is the earliest scheduled source record, not the last
    row encountered. All records remain in `source_meetings`, so the primary is
    merely a backward-compatible display value and never destroys collision
    provenance. Multiple calendar dates require an explicit later policy.
    """
    dates = {row.get("meeting_date") for row in work_item.source_meetings}
    if len(dates) != 1 or None in dates:
        raise ValueError(
            f"{work_item.video_id} has ambiguous source meeting dates: {sorted(map(str, dates))}"
        )
    primary = work_item.source_meetings[0]
    return Meeting(
        video_id=work_item.video_id,
        meeting_date=date.fromisoformat(str(primary["meeting_date"])),
        primegov_id=int(primary["primegov_id"]),
        title=str(primary.get("title") or ""),
        source_meetings=tuple(source_meetings_metadata(work_item)),
    )


def attach_source_meetings(transcript: dict[str, Any], work_item: VideoWorkItem) -> dict[str, Any]:
    """Return a canonical artifact payload with collision-safe provenance."""
    if transcript.get("video_id") != work_item.video_id:
        raise ValueError("transcript video_id does not match work item")
    enriched = dict(transcript)
    enriched["source_meetings"] = source_meetings_metadata(work_item)
    return enriched


def _rows_for_video(manifest: dict[str, Any], video_id: str) -> list[dict[str, Any]]:
    rows = [row for row in manifest.get("meetings", []) if row.get("video_id") == video_id]
    if not rows:
        raise ValueError(f"video {video_id} is absent from manifest")
    return rows


def checkpoint_video(
    manifest: dict[str, Any],
    video_id: str,
    *,
    state: str,
    updates: dict[str, Any],
    manifest_path: Path | None = None,
) -> None:
    """Advance every source record for one video and atomically persist it.

    Existing errors are retained unless the caller deliberately supplies a new
    ``last_error`` value. A successful state transition must pass
    ``last_error=None`` explicitly to clear a previous transient error.
    """
    if state not in set(manifest.get("pipeline_states", [])):
        raise ValueError(f"unknown pipeline state {state!r}")
    rows = _rows_for_video(manifest, video_id)
    for row in rows:
        row["pipeline_state"] = state
        row.update(updates)
    refresh_current_state_summary(manifest)
    if manifest_path is not None:
        atomic_write_json(manifest_path, manifest)


def _normalize_preflight_results(raw: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Accept `{videos: {id: result}}`, `{id: result}`, or a result list."""
    if isinstance(raw.get("videos"), dict):
        raw = raw["videos"]
    elif isinstance(raw.get("results"), list):
        raw = {
            str(item["video_id"]): item
            for item in raw["results"]
            if isinstance(item, dict) and item.get("video_id")
        }
    results: dict[str, dict[str, Any]] = {}
    for video_id, result in raw.items():
        if not isinstance(result, dict):
            raise ValueError(f"preflight result for {video_id} must be an object")
        results[str(video_id)] = result
    return results


def apply_caption_preflight(
    manifest: dict[str, Any],
    raw_results: dict[str, Any],
    *,
    manifest_path: Path | None = None,
    checked_at: str | None = None,
    require_complete: bool = True,
) -> list[str]:
    """Apply local authenticated-caption inspection results with checkpoints.

    Result statuses:
      * ``approved``: requires the CART language and advances to
        ``caption_preflighted``; no caption is downloaded.
      * ``blocked``: terminal state with a reviewed missing reason.
      * ``retryable_error``: stays ``discovered`` and records the error.

    By default, every currently eligible unique work item needs an explicit
    result. Set ``require_complete=False`` only for an explicit operator batch;
    unknown or no-longer-pending IDs always fail in either mode.
    """
    results = _normalize_preflight_results(raw_results)
    work_items = build_video_work_items(manifest)
    eligible = {
        item.video_id for item in work_items if item.pipeline_state in ELIGIBLE_STATES
    }
    missing = eligible - set(results)
    unknown = set(results) - eligible
    if require_complete and missing:
        raise ValueError(f"missing preflight result(s): {', '.join(sorted(missing))}")
    if unknown:
        raise ValueError(
            f"preflight refers to unknown or non-pending video(s): {', '.join(sorted(unknown))}"
        )

    applied: list[str] = []
    timestamp = checked_at or utc_now()
    for video_id in sorted(results):
        result = results[video_id]
        status = result.get("status")
        base = {"caption_preflighted_at": result.get("checked_at", timestamp)}
        if "caption_language" in result:
            base["caption_language"] = result["caption_language"]
        for field in PREFLIGHT_EVIDENCE_FIELDS:
            if field in result:
                base[field] = result[field]
        if status == "approved":
            if result.get("caption_language") != CART_LANGUAGE_CODE:
                raise ValueError(
                    f"{video_id} approved without required CART language {CART_LANGUAGE_CODE}"
                )
            checkpoint_video(
                manifest,
                video_id,
                state="caption_preflighted",
                updates={
                    **base,
                    "caption_status": "approved_cart_track",
                    "missing_reason": None,
                    "ingest_disposition": "m3_1_caption_fetch",
                    "last_error": None,
                    "retryable": True,
                },
                manifest_path=manifest_path,
            )
        elif status == "blocked":
            reason = result.get("missing_reason")
            if not reason:
                raise ValueError(f"{video_id} blocked without missing_reason")
            if result.get("asr_approved") is True:
                raise ValueError(f"{video_id} blocked result cannot approve ASR")
            checkpoint_video(
                manifest,
                video_id,
                state="blocked",
                updates={
                    **base,
                    "caption_status": result.get("caption_status", "unavailable_reviewed"),
                    "missing_reason": reason,
                    "ingest_disposition": "blocked_caption_preflight",
                    "last_error": result.get("last_error"),
                    "retryable": False,
                },
                manifest_path=manifest_path,
            )
        elif status == "retryable_error":
            error = result.get("last_error")
            if not error:
                raise ValueError(f"{video_id} retryable_error without last_error")
            checkpoint_video(
                manifest,
                video_id,
                state="discovered",
                updates={
                    **base,
                    "caption_status": "preflight_error",
                    "last_error": error,
                    "retryable": True,
                },
                manifest_path=manifest_path,
            )
        else:
            raise ValueError(f"{video_id} has unsupported preflight status {status!r}")
        applied.append(video_id)
    return applied


def speaker_coverage_report(
    utterances: Iterable[dict[str, Any]],
    resolver: SpeakerResolver,
) -> dict[str, Any]:
    """Return deterministic label frequencies and resolution coverage.

    This is deliberately computed from the parsed canonical artifact before
    embedding. Callers can require review of all unresolved labels instead of
    hiding committee-specific speakers behind a permissive fallback.
    """
    labels: Counter[str] = Counter()
    methods: Counter[str] = Counter()
    roles: Counter[str] = Counter()
    unresolved: Counter[str] = Counter()
    total = 0
    for utterance in utterances:
        label = utterance.get("source_label")
        key = label if label is not None else "<none>"
        resolution = resolver.resolve(label)
        labels[key] += 1
        methods[resolution.resolution_method] += 1
        roles[resolution.resolved_role] += 1
        total += 1
        if resolution.resolution_method == "unresolved":
            unresolved[key] += 1
    return {
        "utterance_count": total,
        "label_frequency": dict(sorted(labels.items())),
        "resolution_method_counts": dict(sorted(methods.items())),
        "resolved_role_counts": dict(sorted(roles.items())),
        "unresolved_labels": dict(sorted(unresolved.items())),
        "unresolved_utterance_count": sum(unresolved.values()),
    }


def require_reviewed_coverage(
    report: dict[str, Any],
    *,
    reviewed_unknown_labels: Iterable[str] = (),
) -> None:
    reviewed = set(reviewed_unknown_labels)
    outstanding = set(report.get("unresolved_labels", {})) - reviewed
    if outstanding:
        raise ValueError(
            "unreviewed speaker labels before embedding: " + ", ".join(sorted(outstanding))
        )


def validate_embeddings(texts: list[str], vectors: list[list[float]]) -> None:
    if len(vectors) != len(texts):
        raise ValueError(f"partial embeddings: got {len(vectors)} for {len(texts)} texts")
    for index, vector in enumerate(vectors):
        if len(vector) != EMBED_DIM:
            raise ValueError(
                f"embedding {index} has dimension {len(vector)}; expected {EMBED_DIM}"
            )


def plan_stale_key_reconciliation(
    *,
    video_id: str,
    embedding_model: str,
    existing_chunk_indexes: Iterable[int],
    intended_chunk_indexes: Iterable[int],
) -> dict[str, Any]:
    """Produce a non-mutating replacement plan for a future transactional RPC.

    Client-side deletion is intentionally not implemented: a separate upsert
    followed by a delete can leave a video half-replaced on failure. The plan
    identifies the exact stale keys so a future `replace_transcript_chunks`
    database RPC can upsert, verify, and delete in one transaction.
    """
    existing = sorted(set(existing_chunk_indexes))
    intended_input = list(intended_chunk_indexes)
    intended = sorted(set(intended_input))
    if len(intended) != len(intended_input):
        # Iterables passed here should normally be concrete lists; fail closed
        # rather than silently discarding duplicate generated chunk indexes.
        raise ValueError("intended chunk indexes are not unique")
    return {
        "video_id": video_id,
        "embedding_model": embedding_model,
        "intended_chunk_indexes": intended,
        "stale_chunk_indexes": sorted(set(existing) - set(intended)),
        "requires_transactional_rpc": "replace_transcript_chunks",
        "client_delete_permitted": False,
    }


def embed_and_index(
    rows: list[dict[str, Any]],
    *,
    embedder: Embedder,
    indexer: Indexer,
    coverage_report: dict[str, Any],
    reviewed_unknown_labels: Iterable[str] = (),
) -> int:
    """Mockable integration seam for the future approved online phase.

    The indexer is not called until coverage and the complete embedding response
    pass validation. The current M3.1 CLI never instantiates either interface.
    """
    require_reviewed_coverage(
        coverage_report, reviewed_unknown_labels=reviewed_unknown_labels
    )
    texts = [str(row["text"]) for row in rows]
    vectors = embedder(texts)
    validate_embeddings(texts, vectors)
    materialized = []
    for row, embedding in zip(rows, vectors):
        indexed = dict(row)
        indexed["embedding"] = embedding
        indexed["embedding_model"] = indexed.get("embedding_model", EMBED_MODEL)
        materialized.append(indexed)
    indexed_count = indexer(materialized)
    if indexed_count != len(materialized):
        raise ValueError(
            f"indexer acknowledged {indexed_count} rows; expected {len(materialized)}"
        )
    return indexed_count


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Apply local M3.1 caption-preflight results to a manifest; no network."
    )
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument(
        "--caption-preflight",
        type=Path,
        required=True,
        help="Local JSON fixture/metadata from an authenticated caption inspection.",
    )
    parser.add_argument(
        "--allow-partial",
        action="store_true",
        help="Apply only the supplied eligible result batch; strict completeness is the default.",
    )
    args = parser.parse_args()
    manifest = load_json(args.manifest)
    results = load_json(args.caption_preflight)
    applied = apply_caption_preflight(
        manifest,
        results,
        manifest_path=args.manifest,
        require_complete=not args.allow_partial,
    )
    print(json.dumps({"preflight_results_applied": applied}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
