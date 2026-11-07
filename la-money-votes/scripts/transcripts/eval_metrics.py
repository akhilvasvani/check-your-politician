"""Pure, offline metrics and validation for transcript retrieval evaluation.

M3.3 adds graded relevance without changing the legacy exact/parent identity
contract.  This module intentionally performs no I/O or network access so the
judgment schema and ranking math can be tested before any embedding or RPC run.
"""

from __future__ import annotations

import hashlib
import math
from datetime import date
from typing import Any


VALID_RPCS = {"search_transcripts", "search_public_comment"}
VALID_GRADES = {0, 1, 2, 3}
VALID_BODIES = {"city_council", "public_comment", "committee"}


def exact_key(row: dict[str, Any]) -> tuple[str, int, int | None]:
    """Return the exact graded-judgment identity for a retrieved row."""
    return (
        str(row["video_id"]),
        int(row["chunk_idx"]),
        None if row.get("sub_chunk_idx") is None else int(row["sub_chunk_idx"]),
    )


def cache_key(query_id: str, text: str, model: str, version: int) -> str:
    """Content-address a query embedding so edited text cannot reuse a stale vector."""
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return f"{query_id}:{model}:v{version}:{digest}"


def _dcg(grades: list[int]) -> float:
    return sum((2**grade - 1) / math.log2(rank + 2) for rank, grade in enumerate(grades))


def score_graded(
    rows: list[dict[str, Any]],
    judgments: list[dict[str, Any]],
    *,
    k_values: tuple[int, ...] = (1, 3, 8),
) -> dict[str, Any]:
    """Score ranked rows against exact 0-3 judgments.

    Unjudged rows are not silently declared irrelevant. They contribute zero
    gain for the provisional nDCG calculation and are counted separately in
    judged coverage so a live run can be held for review.
    """
    grade_by_key = {exact_key(j["key"]): int(j["grade"]) for j in judgments}
    ranked_grades: list[int | None] = [grade_by_key.get(exact_key(row)) for row in rows]
    ideal = sorted(grade_by_key.values(), reverse=True)
    result: dict[str, Any] = {
        "ranked_grades": ranked_grades,
        "unjudged_count": sum(grade is None for grade in ranked_grades),
    }
    for k in k_values:
        observed = [(grade if grade is not None else 0) for grade in ranked_grades[:k]]
        ideal_at_k = ideal[:k]
        dcg = _dcg(observed)
        idcg = _dcg(ideal_at_k)
        judged = sum(grade is not None for grade in ranked_grades[:k])
        denominator = min(k, len(rows))
        result[f"ndcg_at{k}"] = round(dcg / idcg, 6) if idcg else None
        result[f"mean_grade_at{k}"] = (
            round(sum(observed) / denominator, 6) if denominator else None
        )
        result[f"judged_coverage_at{k}"] = (
            round(judged / denominator, 6) if denominator else None
        )
    return result


def _parse_iso_date(value: str, field: str, query_id: str) -> date:
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{query_id}: {field} must be an ISO date") from exc


def validate_query_set(qset: dict[str, Any]) -> None:
    """Raise ValueError when the M3.3 authoring contract is incomplete."""
    if qset.get("schema_version") != "m3.3-v1":
        raise ValueError("schema_version must be m3.3-v1")
    queries = qset.get("queries")
    if not isinstance(queries, list) or not queries:
        raise ValueError("queries must be a non-empty list")

    ids: set[str] = set()
    for query in queries:
        query_id = query.get("id")
        if not query_id or query_id in ids:
            raise ValueError(f"duplicate or missing query id: {query_id!r}")
        ids.add(query_id)
        if not query.get("text"):
            raise ValueError(f"{query_id}: text is required")
        if not query.get("classes"):
            raise ValueError(f"{query_id}: at least one class is required")
        if query.get("body") not in VALID_BODIES:
            raise ValueError(f"{query_id}: unsupported body {query.get('body')!r}")

        search = query.get("search") or {}
        rpc = search.get("rpc")
        if rpc not in VALID_RPCS:
            raise ValueError(f"{query_id}: unsupported RPC {rpc!r}")
        official_id = search.get("official_id")
        if rpc == "search_transcripts" and not official_id:
            raise ValueError(f"{query_id}: official_id is required")
        if rpc == "search_public_comment" and official_id is not None:
            raise ValueError(f"{query_id}: public-comment search cannot filter an official")
        if search.get("match_count") != 8:
            raise ValueError(f"{query_id}: match_count must preserve the legacy value 8")
        if not search.get("embedding_model") or search.get("embedding_version") is None:
            raise ValueError(f"{query_id}: embedding model/version are required")

        date_from = search.get("date_from")
        date_to = search.get("date_to")
        parsed_from = _parse_iso_date(date_from, "date_from", query_id) if date_from else None
        parsed_to = _parse_iso_date(date_to, "date_to", query_id) if date_to else None
        if parsed_from and parsed_to and parsed_from > parsed_to:
            raise ValueError(f"{query_id}: date_from must not be after date_to")

        target = query.get("legacy_target") or {}
        if "video_id" not in target or "chunk_idx" not in target:
            raise ValueError(f"{query_id}: legacy_target is required")

        judgments = query.get("judgments")
        if not isinstance(judgments, list) or not judgments:
            raise ValueError(f"{query_id}: judgments must be non-empty")
        judgment_keys: set[tuple[str, int, int | None]] = set()
        for judgment in judgments:
            key = exact_key(judgment.get("key") or {})
            if key in judgment_keys:
                raise ValueError(f"{query_id}: duplicate judgment key {key}")
            judgment_keys.add(key)
            if judgment.get("grade") not in VALID_GRADES:
                raise ValueError(f"{query_id}: grade must be an integer from 0 to 3")
            if not judgment.get("rationale"):
                raise ValueError(f"{query_id}: every judgment requires rationale")
            if not judgment.get("reviewer") or not judgment.get("reviewed_at"):
                raise ValueError(f"{query_id}: reviewer and reviewed_at are required")

        target_parent = (str(target["video_id"]), int(target["chunk_idx"]))
        target_sub = target.get("sub_chunk_idx")
        if target_sub is None:
            target_is_judged = any(key[:2] == target_parent for key in judgment_keys)
        else:
            target_is_judged = (*target_parent, int(target_sub)) in judgment_keys
        if not target_is_judged:
            raise ValueError(f"{query_id}: legacy target must have a graded judgment")

    coverage = qset.get("coverage") or {}
    exceptions = coverage.get("not_eligible") or []
    if not any(item.get("official_id") == "cd8-official" for item in exceptions):
        raise ValueError("coverage must explicitly record the CD8 not-eligible exception")
    pending = coverage.get("pending") or []
    if not any(item.get("body") == "committee" for item in pending):
        raise ValueError("coverage must explicitly record pending committee evaluation")
