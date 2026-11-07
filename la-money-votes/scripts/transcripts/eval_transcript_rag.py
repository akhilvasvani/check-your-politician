#!/usr/bin/env python3
"""Eval runner: sweep p_min_similarity over a transcript-RAG gold set.

Extended in M2.3 to dispatch across two RPCs:
  - search_transcripts     (per-official search, M1 gold set)
  - search_public_comment  (public-comment-only search, M2.3 gold set)

The gold set may declare `"rpc": "..."` at the top level; the runner uses
that unless overridden by --rpc on the CLI.

For each query:
  1. Embed via Perplexity /v1/embeddings (base64_int8 -> float list).
     Embeddings are cached to --embeddings on first run so floor sweeps and
     re-runs skip the embedding API (cost optimization).
  2. Call the selected RPC with p_match_count=8 and vary p_min_similarity
     across the sweep. search_transcripts additionally requires
     p_official_id (taken from `expected_official_id` on each query).
  3. Score:
       - exact_hit@k: top-k contains the exact (video_id, chunk_idx,
                      sub_chunk_idx) target when a sub-chunk is specified,
                      or (video_id, chunk_idx) otherwise.
       - parent_hit@k: top-k contains any row with the same (video_id,
                      chunk_idx) as the target.
       - null-rate: proportion of queries that returned 0 rows at this floor.
       - top1_sim: distribution of top-1 similarity scores.

M3.3 adds an additive graded-relevance schema. A query may declare its RPC,
date bounds, model pin, exact 0-3 judgments, and query classes. The runner
continues to emit the legacy exact/parent metrics while adding nDCG,
judgment-coverage, and segmented breakdowns. Mixed-RPC fixtures are supported.

Env:
  PPLX_API_KEY  - Perplexity API key for embeddings
  SUPABASE_URL  - Supabase project URL
  SUPABASE_ANON_KEY - Anon JWT (RPCs are SECURITY INVOKER + RLS-safe)

Usage:
  # search_transcripts (M1 gold set)
  python eval_transcript_rag.py \
      --queries data/transcripts/eval_queries.json \
      --out data/transcripts/eval_results_m1.4.json

  # search_public_comment (M2.3 gold set; --rpc auto reads gold-set field)
  python eval_transcript_rag.py \
      --queries data/transcripts/eval_queries_public_comment.json \
      --out /tmp/eval_public_comment.json
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import statistics
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from transcripts.eval_metrics import cache_key, score_graded, validate_query_set

EMBED_URL = "https://api.perplexity.ai/v1/embeddings"
EMBED_MODEL = "pplx-embed-v1-0.6b"
EMBED_DIM = 1024
MODEL_VERSION = 1

FLOOR_SWEEP = [0.15, 0.20, 0.25, 0.30, 0.35]
MATCH_COUNT = 8


def curl_json(url: str, headers: list[str], body: dict) -> Any:
    """POST JSON via curl -sk (sandbox has TLS quirks with requests/httpx)."""
    args = ["curl", "-sk", "-X", "POST", url]
    for h in headers:
        args += ["-H", h]
    args += ["-H", "Content-Type: application/json", "--data", json.dumps(body)]
    r = subprocess.run(args, capture_output=True, text=True, timeout=60)
    if r.returncode != 0:
        raise RuntimeError(f"curl failed rc={r.returncode}: {r.stderr[:400]}")
    try:
        return json.loads(r.stdout)
    except json.JSONDecodeError:
        raise RuntimeError(f"non-JSON response: {r.stdout[:400]}")


def embed_query(text: str, api_key: str) -> list[float]:
    payload = curl_json(
        EMBED_URL,
        [f"Authorization: Bearer {api_key}"],
        {"input": [text], "model": EMBED_MODEL, "encoding_format": "base64_int8"},
    )
    if "data" not in payload:
        raise RuntimeError(f"embed error: {payload}")
    raw = base64.b64decode(payload["data"][0]["embedding"])
    vec = [float(b if b < 128 else b - 256) for b in raw]
    if len(vec) != EMBED_DIM:
        raise RuntimeError(f"unexpected dim {len(vec)}")
    return vec


def rpc_search(
    supabase_url: str,
    anon_key: str,
    rpc_name: str,
    query_embedding: list[float],
    official_id: str | None,
    min_similarity: float,
    match_count: int = MATCH_COUNT,
    date_from: str | None = None,
    date_to: str | None = None,
    embedding_model: str = EMBED_MODEL,
) -> list[dict]:
    """Dispatch to the named RPC. search_transcripts requires p_official_id;
    search_public_comment does not accept it (filters on resolved_role instead).
    """
    url = f"{supabase_url}/rest/v1/rpc/{rpc_name}"
    headers = [f"apikey: {anon_key}", f"Authorization: Bearer {anon_key}"]
    body: dict[str, Any] = {
        "p_query_embedding": query_embedding,
        "p_match_count": match_count,
        "p_min_similarity": min_similarity,
        "p_date_from": date_from,
        "p_date_to": date_to,
        "p_embedding_model": embedding_model,
    }
    if rpc_name == "search_transcripts":
        if not official_id:
            raise RuntimeError("search_transcripts requires expected_official_id on the query")
        body["p_official_id"] = official_id
    res = curl_json(url, headers, body)
    if isinstance(res, dict) and res.get("code"):
        raise RuntimeError(f"RPC error: {res}")
    return res or []


def query_rpc(query: dict, qset: dict, override: str) -> str:
    if override != "auto":
        return override
    return (query.get("search") or {}).get("rpc") or qset.get("rpc", "search_transcripts")


def legacy_target(query: dict) -> tuple[str, int, int | None]:
    if "legacy_target" in query:
        target = query["legacy_target"]
        return target["video_id"], target["chunk_idx"], target.get("sub_chunk_idx")
    return (
        query["expected_video_id"],
        query["expected_chunk_idx"],
        query.get("expected_sub_chunk_idx"),
    )


def _load_embedding_cache(path: Path | None, queries: list[dict], is_m3: bool) -> dict[str, list[float]]:
    if not path or not path.exists():
        return {}
    payload = json.loads(path.read_text())
    if payload.get("schema_version") == "query-embedding-cache-v2":
        return payload.get("entries") or {}
    if is_m3:
        raise RuntimeError(
            "M3.3 requires query-embedding-cache-v2; legacy id-only cache is unsafe"
        )
    # Backward compatibility for the old id -> vector cache on unchanged M1/M2 fixtures.
    return {q["id"]: payload[q["id"]] for q in queries if q["id"] in payload}


def _embedding_lookup_key(query: dict, is_m3: bool) -> str:
    if not is_m3:
        return query["id"]
    search = query["search"]
    return cache_key(
        query["id"],
        query["text"],
        search["embedding_model"],
        search["embedding_version"],
    )


def _write_embedding_cache(path: Path, entries: dict[str, list[float]]) -> None:
    payload = {
        "schema_version": "query-embedding-cache-v2",
        "entries": entries,
    }
    path.write_text(json.dumps(payload))


def _mean(values: list[float | None]) -> float | None:
    present = [value for value in values if value is not None]
    return round(statistics.mean(present), 6) if present else None


def summarize_group(records: list[dict]) -> dict:
    n = len(records)
    return {
        "n_queries": n,
        "parent_at1_pct": round(100 * sum(r["parent_rank"] == 0 for r in records) / n, 1),
        "parent_at3_pct": round(
            100 * sum(r["parent_rank"] is not None and r["parent_rank"] < 3 for r in records) / n,
            1,
        ),
        "ndcg_at1": _mean([r.get("ndcg_at1") for r in records]),
        "ndcg_at3": _mean([r.get("ndcg_at3") for r in records]),
        "ndcg_at8": _mean([r.get("ndcg_at8") for r in records]),
        "judged_coverage_at8": _mean([r.get("judged_coverage_at8") for r in records]),
    }


def build_breakdowns(records: list[dict]) -> dict[str, dict[str, dict]]:
    dimensions: dict[str, dict[str, list[dict]]] = {
        "query_class": {},
        "official": {},
        "body": {},
        "rpc": {},
        "date_filter": {},
    }
    for record in records:
        for query_class in record["classes"]:
            dimensions["query_class"].setdefault(query_class, []).append(record)
        for dimension in ("official", "body", "rpc", "date_filter"):
            dimensions[dimension].setdefault(record[dimension], []).append(record)
    return {
        dimension: {
            value: summarize_group(group)
            for value, group in sorted(groups.items())
        }
        for dimension, groups in dimensions.items()
    }


def score_hits(
    rows: list[dict], target_video: str, target_chunk_idx: int, target_sub_idx: int | None
) -> dict:
    """Return per-position match info.

    exact_match: exact (video_id, chunk_idx, sub_chunk_idx) tuple hit.
    parent_match: same (video_id, chunk_idx) regardless of sub_chunk_idx.
    """
    exact_pos = None
    parent_pos = None
    for i, r in enumerate(rows):
        same_parent = r["video_id"] == target_video and r["chunk_idx"] == target_chunk_idx
        if same_parent:
            if parent_pos is None:
                parent_pos = i
            if target_sub_idx is None or r.get("sub_chunk_idx") == target_sub_idx:
                if exact_pos is None:
                    exact_pos = i
    return {
        "exact_rank": exact_pos,  # None = miss
        "parent_rank": parent_pos,  # None = miss
        "top1_sim": rows[0]["similarity"] if rows else None,
        "n_returned": len(rows),
    }


def evaluate_floor(
    queries: list[dict],
    qset: dict,
    rpc_name: str,
    floor: float,
    row_provider,
    *,
    is_m3: bool,
    pause: float = 0.0,
    verbose: bool = True,
) -> tuple[dict, dict]:
    """Score every query at one similarity floor.

    `row_provider(query, floor, rpc) -> rows` supplies the candidate rows, so
    the identical scoring path serves both a live RPC sweep and an offline
    replay of saved traces. Keeping one implementation is what guarantees the
    legacy exact/parent metrics and the graded contract cannot drift between
    the two.
    """
    key = f"{floor:.2f}"
    floor_traces: dict[str, dict] = {}
    exact_at1 = 0
    exact_at3 = 0
    exact_at8 = 0
    parent_at1 = 0
    parent_at3 = 0
    parent_at8 = 0
    nulls = 0
    top1_sims: list[float] = []
    graded_records: list[dict] = []

    for q in queries:
        current_rpc = query_rpc(q, qset, rpc_name)
        search = q.get("search") or {}
        rows = row_provider(q, floor, current_rpc)
        target_video, target_chunk, target_sub = legacy_target(q)
        score = score_hits(rows, target_video, target_chunk, target_sub)
        graded = score_graded(rows, q["judgments"]) if is_m3 else {}
        score.update(graded)

        floor_traces[q["id"]] = {
            "rpc": current_rpc,
            "score": score,
            "returned": [
                {
                    "video_id": r["video_id"],
                    "chunk_idx": r["chunk_idx"],
                    "sub_chunk_idx": r.get("sub_chunk_idx"),
                    "sub_chunk_of": r.get("sub_chunk_of"),
                    "similarity": r["similarity"],
                    "resolved_name": r.get("resolved_name"),
                    "text_head": (r.get("text") or "")[:180],
                }
                for r in rows
            ],
        }
        if is_m3:
            graded_records.append({
                **score,
                "classes": q["classes"],
                "official": search.get("official_id") or "public_comment",
                "body": q["body"],
                "rpc": current_rpc,
                "date_filter": (
                    "bounded"
                    if search.get("date_from") or search.get("date_to")
                    else "unbounded"
                ),
            })

        if score["n_returned"] == 0:
            nulls += 1
        if score["top1_sim"] is not None:
            top1_sims.append(score["top1_sim"])

        if score["exact_rank"] is not None:
            if score["exact_rank"] == 0:
                exact_at1 += 1
            if score["exact_rank"] < 3:
                exact_at3 += 1
            if score["exact_rank"] < 8:
                exact_at8 += 1
        if score["parent_rank"] is not None:
            if score["parent_rank"] == 0:
                parent_at1 += 1
            if score["parent_rank"] < 3:
                parent_at3 += 1
            if score["parent_rank"] < 8:
                parent_at8 += 1

        marker = "H" if score["exact_rank"] == 0 else ("h" if score["exact_rank"] is not None else ("p" if score["parent_rank"] is not None else "."))
        if verbose:
            print(f"  {q['id']} [{marker}] top1_sim={score['top1_sim']} exact={score['exact_rank']} parent={score['parent_rank']} n={score['n_returned']}", flush=True)
        if pause:
            time.sleep(pause)

    n = len(queries)
    agg = {
        "n_queries": n,
        "exact_at1_pct": round(100 * exact_at1 / n, 1),
        "exact_at3_pct": round(100 * exact_at3 / n, 1),
        "exact_at8_pct": round(100 * exact_at8 / n, 1),
        "parent_at1_pct": round(100 * parent_at1 / n, 1),
        "parent_at3_pct": round(100 * parent_at3 / n, 1),
        "parent_at8_pct": round(100 * parent_at8 / n, 1),
        "null_pct": round(100 * nulls / n, 1),
        "top1_sim_median": round(statistics.median(top1_sims), 3) if top1_sims else None,
        "top1_sim_min": round(min(top1_sims), 3) if top1_sims else None,
        "top1_sim_max": round(max(top1_sims), 3) if top1_sims else None,
    }
    agg["legacy_metrics"] = {
        field: agg[field]
        for field in (
            "n_queries",
            "exact_at1_pct",
            "exact_at3_pct",
            "exact_at8_pct",
            "parent_at1_pct",
            "parent_at3_pct",
            "parent_at8_pct",
            "null_pct",
            "top1_sim_median",
            "top1_sim_min",
            "top1_sim_max",
        )
    }
    if is_m3:
        agg["graded_metrics"] = {
            "ndcg_at1": _mean([r.get("ndcg_at1") for r in graded_records]),
            "ndcg_at3": _mean([r.get("ndcg_at3") for r in graded_records]),
            "ndcg_at8": _mean([r.get("ndcg_at8") for r in graded_records]),
            "mean_grade_at1": _mean([r.get("mean_grade_at1") for r in graded_records]),
            "mean_grade_at3": _mean([r.get("mean_grade_at3") for r in graded_records]),
            "mean_grade_at8": _mean([r.get("mean_grade_at8") for r in graded_records]),
            "judged_coverage_at1": _mean(
                [r.get("judged_coverage_at1") for r in graded_records]
            ),
            "judged_coverage_at3": _mean(
                [r.get("judged_coverage_at3") for r in graded_records]
            ),
            "judged_coverage_at8": _mean(
                [r.get("judged_coverage_at8") for r in graded_records]
            ),
            "unjudged_rows": sum(r.get("unjudged_count", 0) for r in graded_records),
        }
        agg["breakdowns"] = build_breakdowns(graded_records)
    return agg, floor_traces


def run(queries_path: Path, out_path: Path, embeddings_path: Path | None, rpc_name: str) -> None:
    supabase_url = os.environ["SUPABASE_URL"]
    anon_key = os.environ["SUPABASE_ANON_KEY"]

    qset = json.loads(queries_path.read_text())
    queries = qset["queries"]
    is_m3 = qset.get("schema_version") == "m3.3-v1"
    if is_m3:
        validate_query_set(qset)
    resolved_rpcs = {query_rpc(query, qset, rpc_name) for query in queries}
    report_rpc = next(iter(resolved_rpcs)) if len(resolved_rpcs) == 1 else "mixed"
    print(
        f"[eval] loaded {len(queries)} queries from {queries_path.name} "
        f"(rpc={report_rpc})",
        flush=True,
    )

    embeddings = _load_embedding_cache(embeddings_path, queries, is_m3)
    if embeddings:
        print(
            f"[eval] loaded {len(embeddings)} cached embeddings from "
            f"{embeddings_path.name}",
            flush=True,
        )
    missing = [q for q in queries if _embedding_lookup_key(q, is_m3) not in embeddings]
    if missing:
        api_key = os.environ["PPLX_API_KEY"]
        print(f"[eval] embedding {len(missing)} uncached queries...", flush=True)
        for q in missing:
            embeddings[_embedding_lookup_key(q, is_m3)] = embed_query(q["text"], api_key)
            if embeddings_path:
                _write_embedding_cache(embeddings_path, embeddings)
            time.sleep(0.2)
        print(f"[eval] embedding cache now has {len(embeddings)} entries", flush=True)

    # Step 2: sweep floors, score each query at each floor.
    per_query_traces: dict[str, dict] = {q["id"]: {"query": q, "at_floor": {}} for q in queries}
    aggregate_by_floor: dict[str, dict] = {}

    def live_rows(query: dict, floor: float, current_rpc: str) -> list[dict]:
        search = query.get("search") or {}
        return rpc_search(
            supabase_url,
            anon_key,
            current_rpc,
            embeddings[_embedding_lookup_key(query, is_m3)],
            search.get("official_id", query.get("expected_official_id")),
            floor,
            match_count=search.get("match_count", MATCH_COUNT),
            date_from=search.get("date_from"),
            date_to=search.get("date_to"),
            embedding_model=search.get("embedding_model", EMBED_MODEL),
        )

    for floor in FLOOR_SWEEP:
        key = f"{floor:.2f}"
        print(f"\n[eval] --- floor {key} ---", flush=True)
        agg, floor_traces = evaluate_floor(
            queries, qset, rpc_name, floor, live_rows, is_m3=is_m3, pause=0.1
        )
        for qid, trace in floor_traces.items():
            per_query_traces[qid]["at_floor"][key] = trace
        aggregate_by_floor[key] = agg
        print(f"  [agg] exact@1={agg['exact_at1_pct']}% exact@3={agg['exact_at3_pct']}% parent@1={agg['parent_at1_pct']}% parent@3={agg['parent_at3_pct']}% null={agg['null_pct']}% top1_med={agg['top1_sim_median']}", flush=True)

    report = {
        "version": qset.get("version") or qset.get("schema_version"),
        "rpc": report_rpc,
        "queries_file": queries_path.name,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "floor_sweep": FLOOR_SWEEP,
        "match_count": MATCH_COUNT,
        "embedding_model": EMBED_MODEL,
        "embedding_version": MODEL_VERSION if is_m3 else None,
        "aggregate_by_floor": aggregate_by_floor,
        "per_query": per_query_traces,
    }
    if is_m3:
        report["coverage"] = qset["coverage"]
        report["evaluation"] = qset["evaluation"]
    out_path.write_text(json.dumps(report, indent=2))
    print(f"\n[eval] wrote {out_path}", flush=True)

    # Print the summary table
    print("\n== SUMMARY ==")
    print(f"{'floor':>6}  {'exact@1':>8}  {'exact@3':>8}  {'parent@1':>9}  {'parent@3':>9}  {'null%':>6}  {'top1_med':>9}")
    for floor in FLOOR_SWEEP:
        a = aggregate_by_floor[f"{floor:.2f}"]
        print(f"{floor:>6.2f}  {a['exact_at1_pct']:>8}  {a['exact_at3_pct']:>8}  {a['parent_at1_pct']:>9}  {a['parent_at3_pct']:>9}  {a['null_pct']:>6}  {str(a['top1_sim_median']):>9}")


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--queries", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--embeddings", type=Path, default=None,
                   help="Optional path to pre-computed query embeddings JSON (skips embed step)")
    p.add_argument("--rpc", choices=["auto", "search_transcripts", "search_public_comment"],
                   default="auto",
                   help="Which Supabase RPC to sweep. 'auto' uses the gold set's declared 'rpc' field, defaulting to search_transcripts.")
    args = p.parse_args(argv)
    run(args.queries, args.out, args.embeddings, args.rpc)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
