#!/usr/bin/env python3
"""Build the additive M3.3 graded-relevance fixture from the locked M1/M2 sets.

This authoring helper copies all 30 legacy targets unchanged, adds reviewed
query classes and exact grade-3 target judgments, records the q06/q19 near
misses, and adds six grounded variants for missing evaluation classes.
It performs no network access.
"""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from transcripts.eval_metrics import validate_query_set


REPO = Path(__file__).resolve().parents[2]
DATA = REPO / "data" / "transcripts"
OUT = DATA / "eval_queries_m3_3.json"
MODEL = "pplx-embed-v1-0.6b"
MODEL_VERSION = 1
REVIEWER = "M3.3 authoring review"
REVIEWED_AT = "2026-08-20"

MEETING_DATES = {
    "H-OkhDWvgYE": "2026-06-26",
    "MBjio010l60": "2026-08-14",
    "QePVCuF0iAY": "2026-08-11",
    "UkdZRHDB9qs": "2026-08-04",
    "eLYlonECp7o": "2026-08-05",
    "hyhgFSAqBRM": "2026-06-24",
    "oHYuOqkXv-0": "2026-08-12",
    "oPUdYYi9HyE": "2026-07-01",
    "welTRe5_RH4": "2026-06-30",
}


def judgment(
    video_id: str,
    chunk_idx: int,
    sub_chunk_idx: int | None,
    grade: int,
    label: str,
    rationale: str,
) -> dict[str, Any]:
    return {
        "key": {
            "video_id": video_id,
            "chunk_idx": chunk_idx,
            "sub_chunk_idx": sub_chunk_idx,
        },
        "grade": grade,
        "label": label,
        "rationale": rationale,
        "reviewer": REVIEWER,
        "reviewed_at": REVIEWED_AT,
    }


def legacy_query(source: dict[str, Any], rpc: str) -> dict[str, Any]:
    video_id = source["expected_video_id"]
    legacy_sub_idx = source.get("expected_sub_chunk_idx")
    # Graded judgments are always exact. Whole-turn rows use sub_chunk_idx=0,
    # while the legacy target keeps an omitted sub-index as a parent wildcard.
    judgment_sub_idx = source.get("expected_sub_chunk_idx", 0)
    body = "public_comment" if rpc == "search_public_comment" else "city_council"
    classes = [source["difficulty"]]
    if rpc == "search_transcripts":
        classes.append("per_official")
    if source["id"] == "q13":
        classes.append("long_turn")
    if source["id"] == "q19":
        classes.extend(["low_signal", "near_miss"])
    if source["id"] == "q06":
        classes.append("near_miss")

    query = {
        "id": source["id"],
        "text": source["text"],
        "classes": classes,
        "body": body,
        "search": {
            "rpc": rpc,
            "official_id": source.get("expected_official_id"),
            "date_from": None,
            "date_to": None,
            "match_count": 8,
            "embedding_model": MODEL,
            "embedding_version": MODEL_VERSION,
        },
        "legacy_target": {
            "video_id": video_id,
            "chunk_idx": source["expected_chunk_idx"],
            "sub_chunk_idx": legacy_sub_idx,
        },
        "judgments": [
            judgment(
                video_id,
                source["expected_chunk_idx"],
                judgment_sub_idx,
                3,
                "direct",
                f"Locked M1/M2 target: {source['topic_evidence']}",
            )
        ],
        "evidence": {
            "meeting_date": MEETING_DATES[video_id],
            "source": "canonical transcript",
            "review_status": "single_reviewed",
        },
    }
    if source.get("expected_name"):
        query["expected_name"] = source["expected_name"]
    if source["id"] == "q06":
        query["judgments"].append(
            judgment(
                "oHYuOqkXv-0",
                596,
                0,
                2,
                "partially_responsive",
                "Same speaker explicitly discusses motions expanding auditing power, "
                "but the excerpt lacks the target's agreement and zero-cost detail.",
            )
        )
    if source["id"] == "q19":
        for chunk_idx, sub_idx in ((682, 1), (681, 0)):
            query["judgments"].append(
                judgment(
                    "oHYuOqkXv-0",
                    chunk_idx,
                    sub_idx,
                    1,
                    "topical_adjacency",
                    "Same speaker and committee context, but does not support the claim "
                    "that she deferred because she had already commented.",
                )
            )
    return query


def variant(
    source: dict[str, Any],
    *,
    query_id: str,
    text: str,
    classes: list[str],
    rpc: str,
    date_bounded: bool = False,
) -> dict[str, Any]:
    query = legacy_query(source, rpc)
    query["id"] = query_id
    query["text"] = text
    query["classes"] = classes
    query["legacy_source_id"] = source["id"]
    if date_bounded:
        meeting_date = MEETING_DATES[source["expected_video_id"]]
        query["search"]["date_from"] = meeting_date
        query["search"]["date_to"] = meeting_date
    return query


def build() -> dict[str, Any]:
    official = json.loads((DATA / "eval_queries.json").read_text())["queries"]
    public = json.loads((DATA / "eval_queries_public_comment.json").read_text())["queries"]
    by_id = {q["id"]: q for q in official + public}
    queries = [legacy_query(q, "search_transcripts") for q in official]
    queries += [legacy_query(q, "search_public_comment") for q in public]

    queries += [
        variant(
            by_id["q06"],
            query_id="m3-date-01",
            text="On August 12, 2026, who argued for broader audit authority in the Olympics agreement?",
            classes=["date_bounded", "paraphrase", "per_official"],
            rpc="search_transcripts",
            date_bounded=True,
        ),
        variant(
            by_id["pc-03-boyle-heights-warehouse-fire"],
            query_id="m3-date-02",
            text="At the June 24, 2026 meeting, what did a commenter say about the Boyle Heights warehouse fire and ammonia?",
            classes=["date_bounded", "lexical"],
            rpc="search_public_comment",
            date_bounded=True,
        ),
        variant(
            by_id["q04"],
            query_id="m3-entity-01",
            text="At the Korean Liberation event, which councilmember recognized Councilmember John Lee's mother?",
            classes=["entity_confusion", "lexical", "per_official"],
            rpc="search_transcripts",
        ),
        variant(
            by_id["pc-08-scientology-l-ron-hubbard-way"],
            query_id="m3-entity-02",
            text="What did former Scientology members ask Public Works to do about the street named for L. Ron Hubbard?",
            classes=["entity_confusion", "paraphrase"],
            rpc="search_public_comment",
        ),
        variant(
            by_id["q19"],
            query_id="m3-low-signal-01",
            text="Who yielded to colleagues after saying the committee had already heard her concerns?",
            classes=["low_signal", "semantic", "per_official"],
            rpc="search_transcripts",
        ),
        variant(
            by_id["q13"],
            query_id="m3-long-turn-01",
            text="Who remembered Larry as part of the Pacific Palisades community's recovery journey?",
            classes=["long_turn", "paraphrase", "per_official"],
            rpc="search_transcripts",
        ),
    ]

    return {
        "schema_version": "m3.3-v1",
        "description": "Additive graded-relevance evaluation for CYP transcript RAG.",
        "evaluation": {
            "k_values": [1, 3, 8],
            "floor_sweep": [0.15, 0.20, 0.25, 0.30, 0.35],
            "relevance_scale": {
                "0": "not relevant",
                "1": "topical, entity, role, or procedural adjacency; does not answer",
                "2": "partially responsive or semantically adjacent evidence",
                "3": "directly answers with supporting evidence",
            },
            "gain": "2^grade - 1",
            "unjudged_policy": "report separately; hold final run for judgment completion",
            "legacy_contract": "q01-q20 targets, zero-based ranks, parent@1/@3, five floors, match_count=8",
        },
        "coverage": {
            "indexed_officials_with_queries": sorted(
                {q["search"]["official_id"] for q in queries if q["search"]["official_id"]}
            ),
            "not_eligible": [
                {
                    "official_id": "cd8-official",
                    "name": "Marqueece Harris-Dawson",
                    "reason": "Current CART rows resolve to council-president rather than direct official speech; adjudicate in M3.4.",
                    "reviewed_at": REVIEWED_AT,
                }
            ],
            "pending": [
                {
                    "body": "committee",
                    "reason": "M3.1 has not published a verified committee transcript corpus; do not fabricate committee judgments.",
                }
            ],
            "uncovered_published_videos": [
                {
                    "video_id": "QePVCuF0iAY",
                    "meeting_date": MEETING_DATES["QePVCuF0iAY"],
                    "reason": "Official-query judgment authoring remains pending.",
                },
                {
                    "video_id": "welTRe5_RH4",
                    "meeting_date": MEETING_DATES["welTRe5_RH4"],
                    "reason": "Shared-recording provenance requires reviewed query selection.",
                },
            ],
        },
        "queries": queries,
    }


def main() -> None:
    qset = build()
    validate_query_set(qset)
    OUT.write_text(json.dumps(qset, indent=2) + "\n")
    print(f"wrote {OUT} ({len(qset['queries'])} queries)")


if __name__ == "__main__":
    main()
