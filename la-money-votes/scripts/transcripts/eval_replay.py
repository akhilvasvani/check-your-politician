#!/usr/bin/env python3
"""M3.3 offline candidate-pool extraction and replay.

The graded eval has a judgment gap: the fixture locks a target grade per query
but most of the top-8 candidate pool is still ungraded, so judged coverage@8
sits far below 1.0. Closing that gap needs a human to look at every returned
candidate -- which must not cost a fresh embedding or RPC call every time.

This module works entirely from the retrieval traces the runner already saves
under `per_query[...]["at_floor"][...]["returned"]`:

  extract  pull the union of returned candidates per query into a review
           worksheet, marking which are already judged and which are not.
  merge    fold a reviewed worksheet back into the query fixture, including
           explicit grade-0 judgments for candidates confirmed irrelevant.
  replay   re-score the saved traces against the current judgments and emit a
           full report, optionally gated on complete top-8 judgment coverage.

Nothing here performs network, embedding, caption, or database access. Replay
reuses `evaluate_floor` from the live runner, so the legacy exact/parent
metrics and the graded contract are computed by the same code in both paths
and cannot drift.

A trace is only replayable if the query that produced it still matches the
current fixture. Editing a query's text or search parameters invalidates its
trace, and replay refuses to score it rather than reporting a stale number.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Iterable

from transcripts import eval_transcript_rag as runner
from transcripts.eval_metrics import exact_key, validate_query_set

WORKSHEET_SCHEMA = "m3.3-review-worksheet-v1"
REPLAY_SCHEMA = "m3.3-replay-v1"


# --------------------------------------------------------------------------
# trace loading
# --------------------------------------------------------------------------
def load_trace(path: Path) -> dict[str, dict]:
    """Normalize a saved eval report into {query_id: {query, at_floor}}.

    Handles both saved layouts: the flat `per_query[qid]` written by the
    single-RPC runs, and the `per_query[rpc][qid]` layout written by the M2
    combined report.
    """
    report = json.loads(path.read_text())
    per_query = report.get("per_query")
    if not isinstance(per_query, dict) or not per_query:
        raise ValueError(f"{path.name}: no per_query traces")

    flat: dict[str, dict] = {}
    for key, value in per_query.items():
        if isinstance(value, dict) and "at_floor" in value:
            flat[key] = value                      # flat layout
        elif isinstance(value, dict):
            for qid, trace in value.items():       # nested by RPC
                if not isinstance(trace, dict) or "at_floor" not in trace:
                    raise ValueError(f"{path.name}: malformed trace for {qid!r}")
                if qid in flat:
                    raise ValueError(f"{path.name}: duplicate trace for {qid!r}")
                trace = dict(trace)
                trace.setdefault("rpc", key)
                flat[qid] = trace
        else:
            raise ValueError(f"{path.name}: malformed per_query entry {key!r}")
    if not flat:
        raise ValueError(f"{path.name}: no usable traces")
    return flat


def load_traces(paths: Iterable[Path]) -> dict[str, dict]:
    """Merge several trace files. Later files must not redefine a query id."""
    merged: dict[str, dict] = {}
    for path in paths:
        for qid, trace in load_trace(path).items():
            if qid in merged:
                raise ValueError(f"{qid}: trace defined in more than one file")
            trace = dict(trace)
            trace.setdefault("trace_source", path.name)
            merged[qid] = trace
    return merged


# --------------------------------------------------------------------------
# staleness
# --------------------------------------------------------------------------
def effective_search(query: dict, *, fallback_rpc: str | None = None) -> dict[str, Any]:
    """Search parameters for a query in either the legacy or M3.3 schema."""
    search = query.get("search") or {}
    return {
        "rpc": search.get("rpc") or fallback_rpc,
        "official_id": search.get("official_id", query.get("expected_official_id")),
        "date_from": search.get("date_from"),
        "date_to": search.get("date_to"),
        "embedding_model": search.get("embedding_model", runner.EMBED_MODEL),
        "match_count": search.get("match_count", runner.MATCH_COUNT),
    }


def stale_reasons(current: dict, trace: dict) -> list[str]:
    """Why a saved trace may no longer be scored against `current`.

    An empty list means the trace was produced by an equivalent search over
    identical query text and can be replayed.
    """
    traced_query = trace.get("query") or {}
    reasons: list[str] = []
    if traced_query.get("text") != current.get("text"):
        reasons.append("query text changed since the trace was recorded")

    traced_rpc = trace.get("rpc")
    now = effective_search(current)
    then = effective_search(traced_query, fallback_rpc=traced_rpc)
    for field in ("rpc", "official_id", "date_from", "date_to",
                  "embedding_model", "match_count"):
        # A legacy trace never recorded an RPC of its own; the report-level
        # RPC recorded at load time stands in for it.
        if then[field] is None and field == "rpc":
            continue
        if now[field] != then[field]:
            reasons.append(
                f"{field} changed: trace={then[field]!r} fixture={now[field]!r}"
            )
    return reasons


# --------------------------------------------------------------------------
# candidate-pool extraction
# --------------------------------------------------------------------------
def extract_candidate_pool(trace: dict) -> list[dict]:
    """Union the rows a query returned across every recorded floor.

    Raising the similarity floor only removes rows, so the union is the widest
    pool the query ever produced. Each candidate keeps its best (lowest) rank,
    its highest similarity, and the floors at which it survived, so a reviewer
    can grade the rows that actually shape the ranking first.
    """
    pool: dict[tuple, dict] = {}
    for floor_key, entry in sorted((trace.get("at_floor") or {}).items()):
        for rank, row in enumerate(entry.get("returned") or []):
            key = exact_key(row)
            candidate = pool.get(key)
            if candidate is None:
                candidate = {
                    "key": {
                        "video_id": row["video_id"],
                        "chunk_idx": row["chunk_idx"],
                        "sub_chunk_idx": row.get("sub_chunk_idx"),
                    },
                    "sub_chunk_of": row.get("sub_chunk_of"),
                    "resolved_name": row.get("resolved_name"),
                    "text_head": row.get("text_head"),
                    "best_rank": rank,
                    "max_similarity": row.get("similarity"),
                    "seen_at_floors": [],
                }
                pool[key] = candidate
            candidate["best_rank"] = min(candidate["best_rank"], rank)
            if row.get("similarity") is not None:
                candidate["max_similarity"] = max(
                    candidate["max_similarity"] if candidate["max_similarity"] is not None else row["similarity"],
                    row["similarity"],
                )
            candidate["seen_at_floors"].append(floor_key)
    return sorted(pool.values(), key=lambda c: (c["best_rank"], -(c["max_similarity"] or 0)))


def judged_keys(query: dict) -> dict[tuple, int]:
    return {exact_key(j["key"]): int(j["grade"]) for j in query.get("judgments") or []}


def pool_status(query: dict, trace: dict) -> dict[str, Any]:
    """Judged/ungraded split for one query's saved candidate pool."""
    pool = extract_candidate_pool(trace)
    graded = judged_keys(query)
    for candidate in pool:
        candidate["existing_grade"] = graded.get(exact_key(candidate["key"]))
    ungraded = [c for c in pool if c["existing_grade"] is None]
    return {
        "pool": pool,
        "pool_size": len(pool),
        "judged": len(pool) - len(ungraded),
        "ungraded": len(ungraded),
        "coverage": round((len(pool) - len(ungraded)) / len(pool), 6) if pool else None,
        "stale_reasons": stale_reasons(query, trace),
    }


# --------------------------------------------------------------------------
# worksheet
# --------------------------------------------------------------------------
def build_worksheet(qset: dict, traces: dict[str, dict], *, queries_file: str,
                    trace_files: list[str]) -> dict:
    """Emit the reviewer-facing worksheet for every ungraded candidate."""
    entries = []
    missing_trace = []
    for query in qset["queries"]:
        trace = traces.get(query["id"])
        if trace is None:
            missing_trace.append(query["id"])
            continue
        status = pool_status(query, trace)
        search = effective_search(query)
        entries.append({
            "id": query["id"],
            "text": query["text"],
            "rpc": search["rpc"],
            "official_id": search["official_id"],
            "body": query.get("body"),
            "classes": query.get("classes"),
            "legacy_target": query.get("legacy_target"),
            "stale_reasons": status["stale_reasons"],
            "pool_size": status["pool_size"],
            "already_judged": status["judged"],
            "candidates": [
                {
                    **{k: candidate[k] for k in (
                        "key", "sub_chunk_of", "resolved_name", "text_head",
                        "best_rank", "max_similarity", "seen_at_floors",
                        "existing_grade")},
                    # Reviewer fills these in. `grade: null` means "not yet
                    # reviewed" and is never treated as 0.
                    "grade": None,
                    "label": None,
                    "rationale": None,
                }
                for candidate in status["pool"] if candidate["existing_grade"] is None
            ],
        })
    return {
        "schema_version": WORKSHEET_SCHEMA,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "queries_file": queries_file,
        "trace_files": trace_files,
        "instructions": (
            "Set grade to 0-3 for every candidate you review. 0 means reviewed "
            "and irrelevant -- it is a judgment, not a default. Leave grade null "
            "to leave a candidate unreviewed; merge skips those and replay keeps "
            "reporting them as unjudged. Every graded candidate needs a rationale."
        ),
        "queries_without_trace": missing_trace,
        "queries": entries,
    }


def merge_worksheet(qset: dict, worksheet: dict, *, reviewer: str,
                    reviewed_at: str | None = None) -> tuple[dict, dict]:
    """Fold reviewed grades into the fixture. Unreviewed candidates are skipped."""
    if worksheet.get("schema_version") != WORKSHEET_SCHEMA:
        raise ValueError(f"worksheet schema must be {WORKSHEET_SCHEMA}")
    stamp = reviewed_at or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    by_id = {q["id"]: q for q in qset["queries"]}
    added = 0
    skipped = 0
    per_query: dict[str, int] = {}

    for entry in worksheet.get("queries") or []:
        query = by_id.get(entry["id"])
        if query is None:
            raise ValueError(f"worksheet references unknown query {entry['id']!r}")
        existing = judged_keys(query)
        for candidate in entry.get("candidates") or []:
            grade = candidate.get("grade")
            if grade is None:
                skipped += 1
                continue
            if grade not in (0, 1, 2, 3):
                raise ValueError(
                    f"{entry['id']}: grade must be an integer 0-3, got {grade!r}"
                )
            if not candidate.get("rationale"):
                raise ValueError(
                    f"{entry['id']}: candidate {candidate['key']} needs a rationale"
                )
            key = exact_key(candidate["key"])
            if key in existing:
                raise ValueError(
                    f"{entry['id']}: candidate {candidate['key']} is already judged"
                )
            query.setdefault("judgments", []).append({
                "key": candidate["key"],
                "grade": int(grade),
                "label": candidate.get("label") or ("irrelevant" if grade == 0 else "reviewed"),
                "rationale": candidate["rationale"],
                "reviewer": candidate.get("reviewer") or reviewer,
                "reviewed_at": candidate.get("reviewed_at") or stamp,
            })
            existing[key] = int(grade)
            added += 1
            per_query[entry["id"]] = per_query.get(entry["id"], 0) + 1
    return qset, {
        "judgments_added": added,
        "candidates_left_unreviewed": skipped,
        "per_query": per_query,
    }


# --------------------------------------------------------------------------
# replay
# --------------------------------------------------------------------------
def replay(qset: dict, traces: dict[str, dict], *, rpc_name: str = "auto") -> dict:
    """Re-score saved traces against current judgments. No I/O beyond the inputs."""
    is_m3 = qset.get("schema_version") == "m3.3-v1"
    if is_m3:
        validate_query_set(qset)

    replayable: list[dict] = []
    excluded: dict[str, list[str]] = {}
    for query in qset["queries"]:
        trace = traces.get(query["id"])
        if trace is None:
            excluded[query["id"]] = ["no saved trace"]
            continue
        reasons = stale_reasons(query, trace)
        if reasons:
            excluded[query["id"]] = reasons
            continue
        replayable.append(query)
    if not replayable:
        raise ValueError("no query has a replayable trace")

    floors = sorted({
        floor
        for query in replayable
        for floor in (traces[query["id"]].get("at_floor") or {})
    })

    def saved_rows(query: dict, floor: float, current_rpc: str) -> list[dict]:
        entry = (traces[query["id"]].get("at_floor") or {}).get(f"{floor:.2f}")
        if entry is None:
            raise ValueError(f"{query['id']}: no saved rows at floor {floor:.2f}")
        # Re-expose text_head as text so a replayed trace round-trips intact.
        return [dict(row, text=row.get("text_head", "")) for row in entry["returned"]]

    aggregate_by_floor: dict[str, dict] = {}
    per_query_traces: dict[str, dict] = {q["id"]: {"query": q, "at_floor": {}} for q in replayable}
    for floor_key in floors:
        agg, floor_traces = runner.evaluate_floor(
            replayable, qset, rpc_name, float(floor_key), saved_rows,
            is_m3=is_m3, verbose=False,
        )
        aggregate_by_floor[floor_key] = agg
        for qid, trace in floor_traces.items():
            per_query_traces[qid]["at_floor"][floor_key] = trace

    coverage = {
        query["id"]: pool_status(query, traces[query["id"]])
        for query in replayable
    }
    incomplete = sorted(
        qid for qid, status in coverage.items() if status["ungraded"] > 0
    )
    return {
        "schema_version": REPLAY_SCHEMA,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "source": "replayed from saved traces; no embedding or RPC calls",
        "floor_sweep": [float(f) for f in floors],
        "n_queries_total": len(qset["queries"]),
        "n_queries_replayed": len(replayable),
        "excluded_queries": excluded,
        "judgment_coverage": {
            "queries_with_incomplete_pool_judgments": incomplete,
            "pool_judged_total": sum(s["judged"] for s in coverage.values()),
            "pool_candidates_total": sum(s["pool_size"] for s in coverage.values()),
            "per_query": {
                qid: {k: status[k] for k in ("pool_size", "judged", "ungraded", "coverage")}
                for qid, status in coverage.items()
            },
        },
        "aggregate_by_floor": aggregate_by_floor,
        "per_query": per_query_traces,
    }


def coverage_complete(report: dict) -> tuple[bool, list[str]]:
    """True only when every replayed query has its whole saved pool judged."""
    problems: list[str] = []
    cov = report["judgment_coverage"]
    if cov["queries_with_incomplete_pool_judgments"]:
        problems.append(
            f"{len(cov['queries_with_incomplete_pool_judgments'])} queries have "
            f"ungraded candidates in their saved top-8 pool"
        )
    if report["excluded_queries"]:
        problems.append(
            f"{len(report['excluded_queries'])} queries could not be replayed"
        )
    return (not problems), problems


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------
def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)

    p_extract = sub.add_parser("extract", help="build a review worksheet from saved traces")
    p_extract.add_argument("--queries", type=Path, required=True)
    p_extract.add_argument("--trace", type=Path, nargs="+", required=True)
    p_extract.add_argument("--out", type=Path, required=True)

    p_merge = sub.add_parser("merge", help="fold a reviewed worksheet into the fixture")
    p_merge.add_argument("--queries", type=Path, required=True)
    p_merge.add_argument("--worksheet", type=Path, required=True)
    p_merge.add_argument("--out", type=Path, required=True)
    p_merge.add_argument("--reviewer", required=True)

    p_replay = sub.add_parser("replay", help="re-score saved traces offline")
    p_replay.add_argument("--queries", type=Path, required=True)
    p_replay.add_argument("--trace", type=Path, nargs="+", required=True)
    p_replay.add_argument("--out", type=Path, required=True)
    p_replay.add_argument(
        "--require-full-coverage", action="store_true",
        help="exit non-zero unless every replayed query's saved pool is fully judged",
    )

    args = parser.parse_args(argv)
    qset = json.loads(args.queries.read_text())

    if args.command == "extract":
        traces = load_traces(args.trace)
        worksheet = build_worksheet(
            qset, traces,
            queries_file=args.queries.name,
            trace_files=[p.name for p in args.trace],
        )
        args.out.write_text(json.dumps(worksheet, indent=2))
        pending = sum(len(q["candidates"]) for q in worksheet["queries"])
        print(f"[replay] wrote {args.out}")
        print(f"[replay] {len(worksheet['queries'])} queries with traces; "
              f"{pending} candidates awaiting review")
        if worksheet["queries_without_trace"]:
            print(f"[replay] no trace for: {', '.join(worksheet['queries_without_trace'])}")
        return 0

    if args.command == "merge":
        worksheet = json.loads(args.worksheet.read_text())
        merged, stats = merge_worksheet(qset, worksheet, reviewer=args.reviewer)
        validate_query_set(merged)
        args.out.write_text(json.dumps(merged, indent=2))
        print(f"[replay] wrote {args.out}")
        print(f"[replay] added {stats['judgments_added']} judgments; "
              f"{stats['candidates_left_unreviewed']} left unreviewed")
        return 0

    traces = load_traces(args.trace)
    report = replay(qset, traces)
    args.out.write_text(json.dumps(report, indent=2))
    complete, problems = coverage_complete(report)
    cov = report["judgment_coverage"]
    print(f"[replay] wrote {args.out}")
    print(f"[replay] replayed {report['n_queries_replayed']}/{report['n_queries_total']} queries")
    print(f"[replay] pool judgments: {cov['pool_judged_total']}/{cov['pool_candidates_total']}")
    for problem in problems:
        print(f"[replay] INCOMPLETE: {problem}")
    if args.require_full_coverage and not complete:
        print("[replay] failing: --require-full-coverage was requested")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
