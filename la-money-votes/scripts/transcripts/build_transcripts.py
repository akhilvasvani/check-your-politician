#!/usr/bin/env python3
"""Orchestrator: fetch → flatten → resolve → chunk → embed → upsert.

Runs locally on the Mac mini (or CI runner). Idempotent per meeting:
`data/transcripts/{video_id}.json` on disk is the retry signal — if it's
present, embed+upsert is safe to re-run; if absent, the whole meeting is
re-processed on the next run.

Embedding: Perplexity /v1/embeddings with `pplx-embed-v1-0.6b` (1024-dim,
unnormalized int8 -- see api/search-transcripts.js for the matching
query-side embedder). This decision replaces the earlier E5-small-v2 plan
so both sides of the search pipeline share one credential.

Usage:
    # Default: fetch the 10 most recent City Council regular meetings, ingest all.
    python scripts/transcripts/build_transcripts.py

    # Dry-run: flatten + resolve + write JSON only; skip embed + Supabase.
    python scripts/transcripts/build_transcripts.py --no-embed

    # Single meeting:
    python scripts/transcripts/build_transcripts.py --video-id UkdZRHDB9qs

    # Custom top-N:
    python scripts/transcripts/build_transcripts.py --top 5

Env:
    SUPABASE_URL              (required for upsert)
    SUPABASE_SERVICE_ROLE_KEY (required for upsert)
    PERPLEXITY_API_KEY        (required for embed)
    YT_DLP_PATH               (optional, default: 'yt-dlp' on PATH)
    YT_DLP_COOKIES_BROWSER    (optional, default: 'chrome' — pass '' to disable)
    VTT_CACHE_DIR             (optional, default: '.cache/youtube' — gitignored)
"""

from __future__ import annotations

import argparse
import base64
import json
import logging
import os
import re
import subprocess
import sys
import time
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, date, timezone
from pathlib import Path


REPO = Path(__file__).parent.parent.parent  # la-money-votes/
DATA_DIR = REPO / "data" / "transcripts"
ROSTER_PATH = DATA_DIR / "roster.json"
VTT_CACHE_DEFAULT = REPO / ".cache" / "youtube"

PRIMEGOV_URL = "https://lacity.primegov.com/api/v2/PublicPortal/ListArchivedMeetingsByDays?days=180"
CART_LANG_CODE = "en-uYU-mmqFLq8"   # channel-stable per M0.3b findings
COUNCIL_MEETING_TITLE = "City Council Meeting"

# M1 chunking (2026-08-19): chunks are now speaker turns, not token windows.
# See scripts/transcripts/chunker.py and memory/knowledge/projects/check-your-
# politician's M1.0 audit doc for the reasoning and per-official chunk counts.
# The old CHUNK_TOKENS / CHUNK_OVERLAP knobs are gone; the sub-chunk thresholds
# live in chunker.py (SUB_CHUNK_MAX_WORDS, SUB_CHUNK_TARGET_WORDS).

# Perplexity Embeddings API. See docs.perplexity.ai/docs/embeddings.
# Locked to match api/search-transcripts.js -- MUST match, or vectors are
# incomparable. If you change this, update the schema's default and
# re-embed the entire corpus (upsert on (video_id, chunk_idx,
# embedding_model) makes this incremental-safe).
EMBED_MODEL = "pplx-embed-v1-0.6b"
EMBED_DIM = 1024
EMBED_VERSION = 1
EMBED_URL = "https://api.perplexity.ai/v1/embeddings"

# API request batching. Perplexity supports up to 512 texts / 120K total
# tokens per request; we pick a conservative batch size that fits well
# under both limits given ~400 tokens per chunk (400 * 100 = 40K tokens).
EMBED_BATCH_SIZE = 100

log = logging.getLogger("build_transcripts")


sys.path.insert(0, str(REPO / "scripts"))
from transcripts.vtt_flatten import parse_vtt, dedupe_rolling, stitch_utterances
from transcripts.speaker_resolver import SpeakerResolver
from transcripts.chunker import chunk_turns, TurnChunk


# ---------------------------------------------------------------------------
# Step 1: Enumerate meetings from PrimeGov.
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Meeting:
    video_id: str
    meeting_date: date
    primegov_id: int
    title: str


def fetch_meeting_index(top: int = 10) -> list[Meeting]:
    """Return the top-N most recent regular City Council meetings with videos."""
    import urllib.request
    req = urllib.request.Request(PRIMEGOV_URL, headers={"User-Agent": "check-your-politician/1.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.load(r)

    yt = re.compile(r"v=([a-zA-Z0-9_-]{11})")
    meetings: list[Meeting] = []
    for m in data:
        if m.get("title") != COUNCIL_MEETING_TITLE:
            continue
        video_url = m.get("videoUrl") or ""
        match = yt.search(video_url)
        if not match:
            continue
        meetings.append(Meeting(
            video_id=match.group(1),
            meeting_date=datetime.fromisoformat(m["dateTime"]).date(),
            primegov_id=int(m["id"]),
            title=m["title"],
        ))
    meetings.sort(key=lambda x: x.meeting_date, reverse=True)
    return meetings[:top]


# ---------------------------------------------------------------------------
# Step 2: Fetch VTT via yt-dlp (skip cleanly if captions not ready).
# ---------------------------------------------------------------------------
def fetch_vtt(video_id: str, cache_dir: Path) -> Path | None:
    """Download the CART VTT for one video. Returns the local path, or None
    if unavailable. Never raises for missing captions."""
    out_dir = cache_dir / video_id
    out_dir.mkdir(parents=True, exist_ok=True)
    expected = out_dir / f"{video_id}.{CART_LANG_CODE}.vtt"
    if expected.exists() and expected.stat().st_size > 0:
        log.debug("cache hit: %s", expected)
        return expected

    yt_dlp = os.environ.get("YT_DLP_PATH", "yt-dlp")
    cookies_browser = os.environ.get("YT_DLP_COOKIES_BROWSER", "chrome")

    cmd = [
        yt_dlp,
        "--write-subs", "--sub-format", "vtt",
        "--sub-langs", CART_LANG_CODE,
        "--skip-download", "--ignore-no-formats-error",
        "--output", str(out_dir / "%(id)s.%(ext)s"),
        f"https://www.youtube.com/watch?v={video_id}",
    ]
    if cookies_browser:
        cmd[1:1] = ["--cookies-from-browser", cookies_browser]

    log.info("fetching captions for %s", video_id)
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0 and "no formats" not in (result.stderr or "").lower():
        log.warning("yt-dlp exit=%d for %s\n%s", result.returncode, video_id, result.stderr[-800:])

    if expected.exists() and expected.stat().st_size > 0:
        return expected
    log.info("no captions yet for %s — will retry on next run", video_id)
    return None


# ---------------------------------------------------------------------------
# Step 3: Chunker.
#
# Deleted in M1: the old token-window chunker + word-count-weighted
# attribution vote in embed_and_upsert. That design put every 400-token
# window up for a majority vote; procedural roles (Council President with
# 809 turns of gavel/procedure, or "Speaker" with 736 turns of public
# comment) won almost every vote against a councilmember's short
# interjection, and Jurado ended up with 0 chunks despite speaking in 8 of
# 9 meetings. See chunker.chunk_turns for the replacement: one utterance =
# one chunk, long turns sub-chunked on sentence boundaries.
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Step 4: Build the canonical on-disk transcript JSON.
# ---------------------------------------------------------------------------
def build_transcript_json(meeting: Meeting, utts, resolver: SpeakerResolver) -> dict:
    resolved_utts = []
    coverage = Counter()
    for u in utts:
        r = resolver.resolve(u.speaker)
        method_bucket = "fuzzy" if r.resolution_method.startswith("fuzzy-from:") else r.resolution_method
        coverage[method_bucket] += 1
        resolved_utts.append({
            "start_sec": u.start,
            "end_sec": u.end,
            "source_label": r.source_label,
            "resolved_role": r.resolved_role,
            "resolved_official_id": r.resolved_official_id,
            "resolved_name": r.resolved_name,
            "resolution_method": r.resolution_method,
            "text": u.text,
        })

    return {
        "video_id": meeting.video_id,
        "meeting_date": meeting.meeting_date.isoformat(),
        "primegov_id": meeting.primegov_id,
        "title": meeting.title,
        "language_code": CART_LANG_CODE,
        "ingested_at": datetime.now(timezone.utc).isoformat(),
        "coverage": dict(coverage),
        "utterance_count": len(resolved_utts),
        "utterances": resolved_utts,
    }


# ---------------------------------------------------------------------------
# Step 5: Embed via Perplexity API and upsert to Supabase.
# ---------------------------------------------------------------------------
def embed_batch(texts: list[str], api_key: str) -> list[list[float]]:
    """Call Perplexity /v1/embeddings and decode the base64_int8 response into
    plain float lists (range [-128, 127]). We keep the magnitudes -- pgvector's
    cosine distance operator is unaffected by scale."""
    import urllib.request
    import urllib.error

    body = json.dumps({
        "input": texts,
        "model": EMBED_MODEL,
        # base64_int8 is default; we make it explicit for clarity.
        "encoding_format": "base64_int8",
    }).encode()

    req = urllib.request.Request(
        EMBED_URL,
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    # Retry a few times on 429 / transient 5xx.
    for attempt in range(5):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                payload = json.load(r)
            break
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504) and attempt < 4:
                wait = 2 ** attempt
                log.warning("Perplexity embed HTTP %d, retrying in %ds", e.code, wait)
                time.sleep(wait)
                continue
            raise

    vectors: list[list[float]] = []
    for item in payload["data"]:
        raw = base64.b64decode(item["embedding"])
        # int8 signed
        vec = [int.from_bytes(bytes([b]), "big", signed=True) for b in raw]
        if len(vec) != EMBED_DIM:
            raise RuntimeError(f"Unexpected embedding dim: {len(vec)} != {EMBED_DIM}")
        vectors.append([float(x) for x in vec])
    return vectors


def _build_supabase_client():
    from supabase import create_client
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    return create_client(url, key)


def embed_and_upsert(transcript: dict, chunks: list[TurnChunk], supabase,
                     api_key: str, resolver: SpeakerResolver) -> int:
    """Embed chunks and upsert into transcript_chunks. Returns row count.

    Attribution: each chunk carries its raw CART source_label from the
    originating utterance. We resolve label -> (role, official_id, name)
    here — no dominant-speaker vote, because each chunk is scoped to a
    single speaker turn by construction (see chunker.chunk_turns).
    """
    docs, meta = [], []
    for c in chunks:
        r = resolver.resolve(c.source_label)
        docs.append(c.text)
        meta.append({
            "video_id": transcript["video_id"],
            "meeting_date": transcript["meeting_date"],
            "chunk_idx": c.chunk_idx,
            "start_sec": c.start_sec,
            "end_sec": c.end_sec,
            "source_label": c.source_label,
            "resolved_role": r.resolved_role,
            "resolved_official_id": r.resolved_official_id,
            "resolved_name": r.resolved_name,
            "resolution_method": r.resolution_method,
            "turn_speaker_raw": c.source_label,
            "sub_chunk_idx": c.sub_chunk_idx,
            "sub_chunk_of": c.sub_chunk_of,
            "text": c.text,
            "token_count": c.token_count,
            "embedding_model": EMBED_MODEL,
            "embedding_version": EMBED_VERSION,
        })

    # Batch calls to the embeddings endpoint.
    embs: list[list[float]] = []
    t0 = time.time()
    for i in range(0, len(docs), EMBED_BATCH_SIZE):
        batch = docs[i:i + EMBED_BATCH_SIZE]
        embs.extend(embed_batch(batch, api_key))
    log.info("embedded %d chunks in %.1fs (%s)", len(docs), time.time() - t0, EMBED_MODEL)

    rows = []
    for m, e in zip(meta, embs):
        m["embedding"] = e
        rows.append(m)

    resp = (supabase.table("transcript_chunks")
            .upsert(rows, on_conflict="video_id,chunk_idx,embedding_model")
            .execute())
    if getattr(resp, "error", None):
        raise RuntimeError(f"supabase upsert failed: {resp.error}")
    return len(rows)


# ---------------------------------------------------------------------------
# Step 6: Full pipeline for one meeting.
# ---------------------------------------------------------------------------
def process_meeting(meeting: Meeting, resolver: SpeakerResolver, supabase, api_key: str | None,
                    cache_dir: Path, do_embed: bool) -> dict:
    stats = {"video_id": meeting.video_id, "meeting_date": meeting.meeting_date.isoformat()}

    vtt = fetch_vtt(meeting.video_id, cache_dir)
    if vtt is None:
        stats["status"] = "captions-not-ready"
        return stats

    cues = parse_vtt(vtt)
    deduped = dedupe_rolling(cues)
    utts = stitch_utterances(deduped)
    first_labeled = next((i for i, u in enumerate(utts) if u.speaker is not None), 0)
    utts = utts[first_labeled:]

    if not utts:
        stats["status"] = "empty-after-trim"
        return stats

    transcript = build_transcript_json(meeting, utts, resolver)

    dest = DATA_DIR / f"{meeting.video_id}.json"
    tmp = dest.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(transcript, indent=2))
    tmp.rename(dest)
    stats["json_written"] = str(dest.relative_to(REPO))
    stats["utterance_count"] = transcript["utterance_count"]
    stats["coverage"] = transcript["coverage"]

    chunks = chunk_turns(utts)
    stats["chunk_count"] = len(chunks)
    stats["attributed_chunks"] = sum(
        1 for c in chunks
        if (r := resolver.resolve(c.source_label)).resolved_official_id
        and r.resolved_official_id.startswith("cd")
    )

    if do_embed:
        n = embed_and_upsert(transcript, chunks, supabase, api_key, resolver)
        stats["chunks_upserted"] = n
        stats["status"] = "ingested"
    else:
        stats["status"] = "json-only (--no-embed)"

    return stats


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--top", type=int, default=10, help="How many recent meetings to consider.")
    ap.add_argument("--video-id", help="Process one specific video ID (bypasses PrimeGov).")
    ap.add_argument("--no-embed", action="store_true", help="Skip embedding + Supabase upsert.")
    ap.add_argument("--cache-dir", default=os.environ.get("VTT_CACHE_DIR", str(VTT_CACHE_DEFAULT)))
    ap.add_argument("--log-level", default="INFO")
    args = ap.parse_args()

    logging.basicConfig(
        level=args.log_level,
        format="%(asctime)s %(levelname)-7s %(name)s | %(message)s",
    )

    cache_dir = Path(args.cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)

    if args.video_id:
        meetings = [Meeting(video_id=args.video_id,
                            meeting_date=date.today(),
                            primegov_id=-1,
                            title="(override)")]
    else:
        meetings = fetch_meeting_index(top=args.top)
        log.info("selected %d meetings from PrimeGov", len(meetings))

    resolver = SpeakerResolver(ROSTER_PATH)

    supabase = None
    api_key = None
    if not args.no_embed:
        api_key = os.environ.get("PERPLEXITY_API_KEY")
        if not api_key:
            log.error("PERPLEXITY_API_KEY not set — pass --no-embed for a dry run.")
            return 2
        supabase = _build_supabase_client()

    report = []
    for m in meetings:
        try:
            stats = process_meeting(m, resolver, supabase, api_key, cache_dir, do_embed=not args.no_embed)
        except Exception:
            log.exception("failed to process %s", m.video_id)
            stats = {"video_id": m.video_id, "status": "error"}
        report.append(stats)
        log.info("meeting %s → %s", m.video_id, stats.get("status"))

    print(json.dumps({"report": report}, indent=2))
    return 0 if not any(r.get("status") == "error" for r in report) else 1


if __name__ == "__main__":
    sys.exit(main())
