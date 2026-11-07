#!/usr/bin/env python3
"""Speaker-turn chunker for meeting transcripts.

Design (locked by the M1.0 audit, 2026-08-19):

- One utterance = one chunk. `vtt_flatten.stitch_utterances` already produces
  speaker-scoped turns; we no longer flatten them back into a token stream.
- Attribution is `resolver(turn.speaker)` per chunk; no dominant-speaker vote.
- Turns longer than SUB_CHUNK_MAX_WORDS are split on sentence boundaries with
  a small overlap. Each sub-chunk carries an interpolated start_sec based on
  character offset over the utterance's timeline.

This module is a pure library: no I/O, no network. See build_transcripts.py
for the surrounding pipeline.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


# --- Tunables ---------------------------------------------------------------
#
# Kept as module constants (not CLI flags) because they interact with the
# similarity floor in api/search-transcripts.js and with the eval doc. If you
# change them, re-run the eval (M1.4) and update MIN_SIMILARITY.

# Turns at or below this word count are emitted as a single chunk. Above,
# they're split on sentence boundaries. Chosen from the M1.0 length audit:
# median utterance is 11 words, p90 is 129, so 120 leaves ~89% of turns
# untouched and only splits the long-monologue tail.
SUB_CHUNK_MAX_WORDS = 120

# Target size for each sub-chunk of an over-long turn. Small enough that
# embeddings stay topically peaked, big enough that context isn't lost.
SUB_CHUNK_TARGET_WORDS = 90

# Overlap in sentences between adjacent sub-chunks. One sentence of shared
# context bridges a topic transition without letting adjacent sub-chunks
# become near-duplicates.
SUB_CHUNK_OVERLAP_SENTENCES = 1


# CART output is ALL-CAPS prose. Sentence terminators are conventional. Use
# a lookbehind so the terminator stays attached to the preceding sentence.
_SENT_SPLIT = re.compile(r"(?<=[.?!])\s+")


@dataclass(frozen=True)
class TurnChunk:
    """One indexed chunk emitted from the chunker.

    Fields mirror the storage schema so `build_transcripts.embed_and_upsert`
    can copy through without recomputing attribution.
    """

    chunk_idx: int
    start_sec: float
    end_sec: float
    source_label: str | None  # raw CART label from the utterance
    text: str
    token_count: int          # word count (approx)
    sub_chunk_idx: int        # 0 for a whole-turn chunk; 0..N-1 within a split turn
    sub_chunk_of: int         # 1 for whole-turn; N for the N sub-chunks of a split turn


def _split_sentences(text: str) -> list[str]:
    parts = [s.strip() for s in _SENT_SPLIT.split(text or "") if s and s.strip()]
    return parts if parts else ([text.strip()] if text and text.strip() else [])


def _sub_chunk_sentences(
    sentences: list[str],
    target_words: int,
    overlap_sentences: int,
) -> list[list[str]]:
    """Pack sentences into groups of ~target_words each, with sentence overlap.

    Returns a list of sentence-lists. Each group's flattened word count is
    approximately `target_words` (may run over by one sentence's worth on
    the tail; never split a sentence).
    """
    if not sentences:
        return []
    groups: list[list[str]] = []
    i = 0
    while i < len(sentences):
        cur: list[str] = []
        cur_words = 0
        j = i
        while j < len(sentences):
            wc = len(sentences[j].split())
            if cur and cur_words + wc > target_words:
                break
            cur.append(sentences[j])
            cur_words += wc
            j += 1
        if not cur:
            # A single sentence longer than target_words. Emit it whole rather
            # than mid-sentence — CART sentences are usually short enough that
            # this only fires on run-on public comment; better to keep the
            # sentence intact than fabricate a cut point.
            cur = [sentences[i]]
            j = i + 1
        groups.append(cur)
        if j >= len(sentences):
            break
        # Overlap: back up by `overlap_sentences` for the next group's start,
        # but never fewer than 1 new sentence (else infinite loop on a single
        # dominant sentence).
        next_i = max(j - overlap_sentences, i + 1)
        i = next_i
    return groups


def _interpolate_time(
    utt_start: float,
    utt_end: float,
    utt_text_len: int,
    char_offset: int,
) -> float:
    """Linear interpolation of a per-character start time.

    CART VTTs don't preserve per-word timestamps once flattened; a linear
    interpolation across the utterance is the best proxy without re-parsing
    the inline <c> tags. Errors are bounded by utterance duration — a typical
    long turn is ≤ 2 minutes, so worst-case placement error for a mid-turn
    sub-chunk is ~1 minute. YouTube deep-links treat that as "close enough
    that the viewer sees context around the quoted line."
    """
    if utt_end <= utt_start or utt_text_len <= 0:
        return utt_start
    frac = max(0.0, min(1.0, char_offset / utt_text_len))
    return utt_start + frac * (utt_end - utt_start)


def chunk_turns(utts) -> list[TurnChunk]:
    """Convert a list of Utterance-like objects into TurnChunk rows.

    Accepts anything with `.start`, `.end`, `.speaker`, `.text` attributes
    (dataclass Utterance from vtt_flatten, or a dict-like adapter). Emits
    chunks in stable meeting order, with monotonic `chunk_idx`.
    """
    chunks: list[TurnChunk] = []
    idx = 0
    for u in utts:
        text = (u.text or "").strip()
        if not text:
            continue
        words = text.split()
        wc = len(words)

        # Short turn: emit as-is.
        if wc <= SUB_CHUNK_MAX_WORDS:
            chunks.append(TurnChunk(
                chunk_idx=idx,
                start_sec=float(u.start),
                end_sec=float(u.end),
                source_label=u.speaker,
                text=text,
                token_count=wc,
                sub_chunk_idx=0,
                sub_chunk_of=1,
            ))
            idx += 1
            continue

        # Long turn: sub-chunk on sentence boundaries.
        sentences = _split_sentences(text)
        groups = _sub_chunk_sentences(
            sentences, SUB_CHUNK_TARGET_WORDS, SUB_CHUNK_OVERLAP_SENTENCES
        )
        if not groups:
            # Degenerate: no sentences found; emit whole turn as one chunk.
            chunks.append(TurnChunk(
                chunk_idx=idx,
                start_sec=float(u.start),
                end_sec=float(u.end),
                source_label=u.speaker,
                text=text,
                token_count=wc,
                sub_chunk_idx=0,
                sub_chunk_of=1,
            ))
            idx += 1
            continue

        text_len = len(text)
        n = len(groups)
        # Precompute the character offset where each group starts. We locate
        # the group's first sentence in the original text by scanning forward
        # (sentences are consumed in order, so this is O(n)).
        cursor = 0
        for sub_idx, group in enumerate(groups):
            first = group[0]
            pos = text.find(first, cursor)
            if pos < 0:
                pos = cursor
            cursor = pos + len(first)
            sub_start = _interpolate_time(u.start, u.end, text_len, pos)
            sub_end = (
                _interpolate_time(u.start, u.end, text_len, cursor)
                if sub_idx < n - 1 else float(u.end)
            )
            sub_text = " ".join(group)
            chunks.append(TurnChunk(
                chunk_idx=idx,
                start_sec=float(sub_start),
                end_sec=float(sub_end),
                source_label=u.speaker,
                text=sub_text,
                token_count=len(sub_text.split()),
                sub_chunk_idx=sub_idx,
                sub_chunk_of=n,
            ))
            idx += 1
    return chunks
