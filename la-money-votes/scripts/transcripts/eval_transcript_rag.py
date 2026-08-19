#!/usr/bin/env python3
"""M1.4 eval runner: sweep p_min_similarity over the 20-query gold set.

For each query:
  1. Embed via Perplexity /v1/embeddings (base64_int8 -> float list).
  2. Call the search_transcripts RPC with p_official_id set to the expected
     councilmember, p_match_count=8, and vary p_min_similarity across the sweep.
  3. Score:
       - exact_hit@k: top-k contains the exact (video_id, chunk_idx) target.
       - parent_hit@k: top-k contains any row with the same (video_id, chunk_idx)
                      as the target (sub-chunk-agnostic parent-turn match).
       - null-rate: proportion of queries that returned 0 rows at this floor.
       - top1_sim: distribution of top-1 similarity scores.

Outputs a JSON report next to this script's --out path with per-query traces
plus an aggregate summary per floor.

Env:
  PPLX_API_KEY  - Perplexity API key for embeddings
  SUPABASE_URL  - Supabase project URL
  SUPABASE_ANON_KEY - Anon JWT (RPC is SECURITY INVOKER + RLS-safe)

Usage:
  python eval_transcript_rag.py \
      --queries data/transcripts/eval_queries.json \
      --out data/transcripts/eval_results_m1.4.json
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

EMBED_URL = "https://api.perplexity.ai/v1/embeddings"
EMBED_MODEL = "pplx-embed-v1-0.6b"
EMBED_DIM = 1024

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
    query_embedding: list[float],
    official_id: str,
    min_similarity: float,
    match_count: int = MATCH_COUNT,
) -> list[dict]:
    url = f"{supabase_url}/rest/v1/rpc/search_transcripts"
    headers = [f"apikey: {anon_key}", f"Authorization: Bearer {anon_key}"]
    body = {
        "p_query_embedding": query_embedding,
        "p_official_id": official_id,
        "p_match_count": match_count,
        "p_min_similarity": min_similarity,
    }
    res = curl_json(url, headers, body)
    if isinstance(res, dict) and res.get("code"):
        raise RuntimeError(f"RPC error: {res}")
    return res or []


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


def run(queries_path: Path, out_path: Path, embeddings_path: Path | None) -> None:
    supabase_url = os.environ["SUPABASE_URL"]
    anon_key = os.environ["SUPABASE_ANON_KEY"]

    qset = json.loads(queries_path.read_text())
    queries = qset["queries"]
    print(f"[eval] loaded {len(queries)} queries from {queries_path.name}", flush=True)

    embeddings: dict[str, list[float]]
    if embeddings_path and embeddings_path.exists():
        embeddings = json.loads(embeddings_path.read_text())
        print(f"[eval] loaded {len(embeddings)} cached embeddings from {embeddings_path.name}", flush=True)
    else:
        api_key = os.environ["PPLX_API_KEY"]
        print("[eval] embedding all queries...", flush=True)
        embeddings = {}
        for q in queries:
            embeddings[q["id"]] = embed_query(q["text"], api_key)
            time.sleep(0.2)
        print(f"[eval] embedded {len(embeddings)} queries", flush=True)

    # Step 2: sweep floors, score each query at each floor.
    per_query_traces: dict[str, dict] = {q["id"]: {"query": q, "at_floor": {}} for q in queries}
    aggregate_by_floor: dict[str, dict] = {}

    for floor in FLOOR_SWEEP:
        key = f"{floor:.2f}"
        print(f"\n[eval] --- floor {key} ---", flush=True)
        exact_at1 = 0
        exact_at3 = 0
        exact_at8 = 0
        parent_at1 = 0
        parent_at3 = 0
        parent_at8 = 0
        nulls = 0
        top1_sims: list[float] = []

        for q in queries:
            emb = embeddings[q["id"]]
            rows = rpc_search(
                supabase_url,
                anon_key,
                emb,
                q["expected_official_id"],
                floor,
            )
            target_sub = q.get("expected_sub_chunk_idx")
            score = score_hits(rows, q["expected_video_id"], q["expected_chunk_idx"], target_sub)

            per_query_traces[q["id"]]["at_floor"][key] = {
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
            print(f"  {q['id']} [{marker}] top1_sim={score['top1_sim']} exact={score['exact_rank']} parent={score['parent_rank']} n={score['n_returned']}", flush=True)
            time.sleep(0.1)

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
        aggregate_by_floor[key] = agg
        print(f"  [agg] exact@1={agg['exact_at1_pct']}% exact@3={agg['exact_at3_pct']}% parent@1={agg['parent_at1_pct']}% parent@3={agg['parent_at3_pct']}% null={agg['null_pct']}% top1_med={agg['top1_sim_median']}", flush=True)

    report = {
        "version": qset.get("version"),
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "floor_sweep": FLOOR_SWEEP,
        "match_count": MATCH_COUNT,
        "aggregate_by_floor": aggregate_by_floor,
        "per_query": per_query_traces,
    }
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
    args = p.parse_args(argv)
    run(args.queries, args.out, args.embeddings)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
