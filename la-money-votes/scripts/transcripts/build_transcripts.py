#!/usr/bin/env python3
"""Orchestrator: fetch → flatten → resolve → chunk → embed → upsert.

Runs locally on the Mac mini (or CI runner with MPS/CUDA). Idempotent per
meeting: `data/transcripts/{video_id}.json` on disk is the retry signal —
if it's present, embed+upsert is safe to re-run; if absent, the whole
meeting is re-processed on the next run.

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
    YT_DLP_PATH               (optional, default: 'yt-dlp' on PATH)
    YT_DLP_COOKIES_BROWSER    (optional, default: 'chrome' — pass '' to disable)
    VTT_CACHE_DIR             (optional, default: '.cache/youtube' — gitignored)
    EMBED_DEVICE              (optional, default: auto — 'mps' | 'cuda' | 'cpu')
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import shutil
import subprocess
import sys
import time
from collections import Counter
from dataclasses import dataclass, asdict
from datetime import datetime, date, timezone
from pathlib import Path
from typing import Iterable, Iterator

# Third-party imports are done lazily so --no-embed can run without them installed.
# See requirements-transcripts.txt.


REPO = Path(__file__).parent.parent.parent  # la-money-votes/
DATA_DIR = REPO / "data" / "transcripts"
ROSTER_PATH = DATA_DIR / "roster.json"
VTT_CACHE_DEFAULT = REPO / ".cache" / "youtube"

PRIMEGOV_URL = "https://lacity.primegov.com/api/v2/PublicPortal/ListArchivedMeetingsByDays?days=180"
CART_LANG_CODE = "en-uYU-mmqFLq8"   # channel-stable per M0.3b findings
COUNCIL_MEETING_TITLE = "City Council Meeting"

CHUNK_TOKENS = 400
CHUNK_OVERLAP = 50
EMBED_MODEL = "intfloat/e5-small-v2"
EMBED_DIM = 384
EMBED_VERSION = 1

log = logging.getLogger("build_transcripts")


# ---------------------------------------------------------------------------
# Local imports from this module.
# ---------------------------------------------------------------------------
sys.path.insert(0, str(REPO / "scripts"))
from transcripts.vtt_flatten import parse_vtt, dedupe_rolling, stitch_utterances
from transcripts.speaker_resolver import SpeakerResolver, Resolution


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
        # Strict title match. Excludes "-SAP" (Spanish-language duplicate) and committee meetings.
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
    """Download the CART VTT for one video. Returns the local path, or None if unavailable.

    Never raises for missing captions — that is a normal case (fresh livestream
    not yet transcoded). Only raises on infrastructure errors (missing yt-dlp, etc).
    """
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
# Step 3: Chunker (400-token windows with 50-token overlap, utterance-aware).
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Chunk:
    chunk_idx: int
    start_sec: float
    end_sec: float
    source_labels: tuple[str | None, ...]  # de-duplicated raw CART labels in this window
    text: str
    token_count: int


def chunk_utterances(utts, target: int = CHUNK_TOKENS, overlap: int = CHUNK_OVERLAP) -> list[Chunk]:
    if not utts:
        return []
    # Flatten to (utt_index, token) so we can slice on token boundaries.
    tokens: list[tuple[int, str]] = []
    for i, u in enumerate(utts):
        for tok in (u.text or "").split():
            tokens.append((i, tok))

    chunks: list[Chunk] = []
    step = target - overlap
    idx = 0
    ci = 0
    while idx < len(tokens):
        window = tokens[idx: idx + target]
        if not window:
            break
        start_utt_idx = window[0][0]
        end_utt_idx = window[-1][0]
        labels_in_window = tuple(dict.fromkeys(  # preserve order, dedup
            utts[j].speaker for j in range(start_utt_idx, end_utt_idx + 1)
        ))
        text = " ".join(tok for _, tok in window)
        chunks.append(Chunk(
            chunk_idx=ci,
            start_sec=utts[start_utt_idx].start,
            end_sec=utts[end_utt_idx].end,
            source_labels=labels_in_window,
            text=text,
            token_count=len(window),
        ))
        ci += 1
        idx += step
    return chunks


# ---------------------------------------------------------------------------
# Step 4: Build the on-disk transcript JSON (canonical, human-readable).
# ---------------------------------------------------------------------------
def build_transcript_json(meeting: Meeting, utts, resolver: SpeakerResolver) -> dict:
    """Produce data/transcripts/{video_id}.json.

    This file is canonical: it survives even if Supabase is wiped. Ingestion
    to Supabase (Step 6) reads from it. The raw VTT is gitignored; this JSON
    is committed.
    """
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
# Step 5: Embed chunks and upsert to Supabase.
# ---------------------------------------------------------------------------
def _load_embedder(device_env: str | None):
    from sentence_transformers import SentenceTransformer
    import torch
    if device_env:
        device = device_env
    elif torch.backends.mps.is_available():
        device = "mps"
    elif torch.cuda.is_available():
        device = "cuda"
    else:
        device = "cpu"
    log.info("loading %s on device=%s", EMBED_MODEL, device)
    return SentenceTransformer(EMBED_MODEL, device=device), device


def _build_supabase_client():
    from supabase import create_client
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    return create_client(url, key)


def embed_and_upsert(transcript: dict, chunks: list[Chunk], embedder, supabase) -> int:
    """Embed chunks and upsert into transcript_chunks. Returns row count."""
    # Build per-chunk resolved-speaker metadata from the utterance stream.
    # Rule: attribute the chunk to the DOMINANT speaker (most tokens) in its window.
    #       If tied, use the FIRST speaker in the window.
    # This is a display convenience only; the raw source_labels stay in the JSON
    # for anyone who wants full fidelity.
    utts = transcript["utterances"]
    docs, meta = [], []
    for c in chunks:
        # Find dominant speaker across the tokens in this window.
        # We already have source_labels in order-preserving dedup; pick the one
        # that spans the most tokens by walking utterances that overlap [start_sec, end_sec].
        overlapping = [u for u in utts if u["end_sec"] >= c.start_sec and u["start_sec"] <= c.end_sec]
        if overlapping:
            per_speaker: Counter = Counter()
            for u in overlapping:
                per_speaker[u["source_label"]] += len((u["text"] or "").split())
            dominant_label, _ = per_speaker.most_common(1)[0]
            dominant = next(u for u in overlapping if u["source_label"] == dominant_label)
            resolved_role = dominant["resolved_role"]
            resolved_official_id = dominant["resolved_official_id"]
            resolved_name = dominant["resolved_name"]
            resolution_method = dominant["resolution_method"]
            source_label = dominant["source_label"]
        else:
            resolved_role = "unknown"
            resolved_official_id = None
            resolved_name = "Unknown"
            resolution_method = "unresolved"
            source_label = None

        docs.append(f"passage: {c.text}")
        meta.append({
            "video_id": transcript["video_id"],
            "meeting_date": transcript["meeting_date"],
            "chunk_idx": c.chunk_idx,
            "start_sec": c.start_sec,
            "end_sec": c.end_sec,
            "source_label": source_label,
            "resolved_role": resolved_role,
            "resolved_official_id": resolved_official_id,
            "resolved_name": resolved_name,
            "resolution_method": resolution_method,
            "text": c.text,
            "token_count": c.token_count,
            "embedding_model": EMBED_MODEL,
            "embedding_version": EMBED_VERSION,
        })

    t0 = time.time()
    embs = embedder.encode(docs, batch_size=32, show_progress_bar=False, normalize_embeddings=True)
    log.info("embedded %d chunks in %.1fs", len(docs), time.time() - t0)

    rows = []
    for m, e in zip(meta, embs):
        # Supabase expects a Python list for pgvector; float() cast keeps JSON small.
        m["embedding"] = [float(x) for x in e]
        rows.append(m)

    # Upsert on the unique key so re-runs are idempotent.
    resp = (supabase.table("transcript_chunks")
            .upsert(rows, on_conflict="video_id,chunk_idx,embedding_model")
            .execute())
    if getattr(resp, "error", None):
        raise RuntimeError(f"supabase upsert failed: {resp.error}")
    return len(rows)


# ---------------------------------------------------------------------------
# Step 6: Full pipeline for one meeting.
# ---------------------------------------------------------------------------
def process_meeting(meeting: Meeting, resolver: SpeakerResolver, embedder, supabase,
                    cache_dir: Path, do_embed: bool) -> dict:
    """Full pipeline for one meeting. Returns a small stats dict for the report."""
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

    # Write canonical JSON to disk (atomic rename).
    dest = DATA_DIR / f"{meeting.video_id}.json"
    tmp = dest.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(transcript, indent=2))
    tmp.rename(dest)
    stats["json_written"] = str(dest.relative_to(REPO))
    stats["utterance_count"] = transcript["utterance_count"]
    stats["coverage"] = transcript["coverage"]

    chunks = chunk_utterances(utts)
    stats["chunk_count"] = len(chunks)

    if do_embed:
        n = embed_and_upsert(transcript, chunks, embedder, supabase)
        stats["chunks_upserted"] = n
        stats["status"] = "ingested"
    else:
        stats["status"] = "json-only (--no-embed)"

    return stats


# ---------------------------------------------------------------------------
# Entrypoint.
# ---------------------------------------------------------------------------
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
                            meeting_date=date.today(),  # unknown when overriding
                            primegov_id=-1,
                            title="(override)")]
    else:
        meetings = fetch_meeting_index(top=args.top)
        log.info("selected %d meetings from PrimeGov", len(meetings))

    resolver = SpeakerResolver(ROSTER_PATH)

    embedder = None
    supabase = None
    if not args.no_embed:
        embedder, _ = _load_embedder(os.environ.get("EMBED_DEVICE"))
        supabase = _build_supabase_client()

    report = []
    for m in meetings:
        try:
            stats = process_meeting(m, resolver, embedder, supabase, cache_dir, do_embed=not args.no_embed)
        except Exception:
            log.exception("failed to process %s", m.video_id)
            stats = {"video_id": m.video_id, "status": "error"}
        report.append(stats)
        log.info("meeting %s → %s", m.video_id, stats.get("status"))

    # Print final report as JSON for machine + human consumption.
    print(json.dumps({"report": report}, indent=2))
    # Non-zero exit if any meeting errored (retry-friendly).
    return 0 if not any(r.get("status") == "error" for r in report) else 1


if __name__ == "__main__":
    sys.exit(main())
