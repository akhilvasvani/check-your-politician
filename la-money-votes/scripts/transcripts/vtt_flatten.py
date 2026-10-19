#!/usr/bin/env python3
"""Flatten a YouTube rolling-window CART VTT into canonical (start, end, text) segments.

Strategy:
- YouTube's live-caption VTTs emit each visible-line update as a new cue. Each cue's
  payload holds the top N-1 visible lines of prior text plus a new bottom line
  containing inline <c> word-timing tags for karaoke display.
- To flatten: strip all <c>-tag markup, keep only the LAST non-blank textual line
  of each cue (this is the new content), and re-anchor its start timestamp using
  the first inline <c> timestamp when present (finer-grained than the cue-level
  start), or fall back to the cue-level start otherwise.
- Then merge adjacent lines that came in as CART fragments back into full utterances,
  splitting on speaker-label boundaries (>> Name:).
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path

VTT_TS = re.compile(
    r"^(\d{2}:\d{2}:\d{2}\.\d{3})\s+-->\s+(\d{2}:\d{2}:\d{2}\.\d{3})"
)
INLINE_TS = re.compile(r"<(\d{2}:\d{2}:\d{2}\.\d{3})>")
C_TAG = re.compile(r"<c[^>]*>|</c>")
INLINE_ANY_TAG = re.compile(r"<[^>]+>")
SPEAKER_LABEL = re.compile(r"^&gt;&gt;\s*([^:]+):\s*(.*)$")


def ts_to_seconds(ts: str) -> float:
    h, m, s = ts.split(":")
    return int(h) * 3600 + int(m) * 60 + float(s)


@dataclass
class RawLine:
    start: float
    end: float
    text: str  # cleaned of all <c> tags


def parse_vtt(path: Path) -> list[RawLine]:
    """Extract the NEW bottom line from each rolling cue, with best available start ts."""
    lines = path.read_text().splitlines()
    out: list[RawLine] = []
    i = 0
    while i < len(lines):
        m = VTT_TS.match(lines[i])
        if not m:
            i += 1
            continue
        cue_start = ts_to_seconds(m.group(1))
        cue_end = ts_to_seconds(m.group(2))
        i += 1
        # Collect payload until next blank or next timestamp
        payload = []
        while i < len(lines) and lines[i].strip() != "" and not VTT_TS.match(lines[i]):
            payload.append(lines[i])
            i += 1
        if not payload:
            continue
        # The last non-blank line is the "new" content in a rolling-window frame.
        # But rolling cues alternate:
        #   frame A: 3 lines, only the bottom has <c> tags (in-progress word display)
        #   frame B: 3 lines of finalized text (no <c> tags)
        # We want the LAST line of every frame.
        last = payload[-1]
        # Prefer the earliest inline <c> timestamp as start (finer-grained than cue_start)
        inline_starts = INLINE_TS.findall(last)
        if inline_starts:
            start = ts_to_seconds(inline_starts[0])
        else:
            start = cue_start
        # Strip all inline tags
        cleaned = INLINE_ANY_TAG.sub("", last).strip()
        if not cleaned:
            continue
        out.append(RawLine(start=start, end=cue_end, text=cleaned))
    return out


def dedupe_rolling(raw: list[RawLine]) -> list[RawLine]:
    """Remove consecutive duplicate lines (rolling frame emits the same
    finalized bottom line twice: once with <c> tags, once without)."""
    out: list[RawLine] = []
    seen_last = ""
    for r in raw:
        if r.text == seen_last:
            # Update end timestamp to the later of the two
            if out:
                out[-1] = RawLine(out[-1].start, max(out[-1].end, r.end), out[-1].text)
            continue
        out.append(r)
        seen_last = r.text
    return out


@dataclass
class Utterance:
    start: float
    end: float
    speaker: str | None  # e.g. "City Attorney", "Speaker", "Councilmember Price"; None if no label
    text: str


def stitch_utterances(lines: list[RawLine]) -> list[Utterance]:
    """Merge CART line-fragments into speaker-turn utterances.

    Rules:
    - A line starting with '&gt;&gt; NAME:' opens a new utterance and captures the speaker.
    - Subsequent lines without a new speaker label append to the current utterance's text.
    - The end timestamp of an utterance is the end of its last appended line.
    """
    utts: list[Utterance] = []
    cur: Utterance | None = None
    for r in lines:
        m = SPEAKER_LABEL.match(r.text)
        if m:
            if cur is not None:
                utts.append(cur)
            speaker = m.group(1).strip()
            body = m.group(2).strip()
            cur = Utterance(start=r.start, end=r.end, speaker=speaker, text=body)
        else:
            if cur is None:
                # Pre-meeting content with no speaker label yet — accumulate under "None"
                cur = Utterance(start=r.start, end=r.end, speaker=None, text=r.text)
            else:
                # Append with a space if the CART fragment is a continuation
                cur.text = (cur.text + " " + r.text).strip()
                cur.end = r.end
    if cur is not None:
        utts.append(cur)
    return utts


def main(vtt_path: str) -> None:
    path = Path(vtt_path)
    raw = parse_vtt(path)
    print(f"[parse] extracted {len(raw)} raw line-frames", file=sys.stderr)
    deduped = dedupe_rolling(raw)
    print(f"[dedup] {len(deduped)} unique lines ({100 * (1 - len(deduped)/max(1,len(raw))):.1f}% reduction)", file=sys.stderr)
    utts = stitch_utterances(deduped)
    print(f"[stitch] {len(utts)} utterances", file=sys.stderr)
    # Speaker frequency
    from collections import Counter
    speaker_counts = Counter(u.speaker for u in utts)
    print("[speakers] frequency:", file=sys.stderr)
    for spk, n in speaker_counts.most_common(20):
        print(f"  {spk!r}: {n}", file=sys.stderr)
    # Emit a preview
    print("=== FIRST 5 UTTERANCES ===")
    for u in utts[:5]:
        print(f"[{u.start:8.2f}s → {u.end:8.2f}s] ({u.speaker}) {u.text[:200]}")
    print("\n=== 5 UTTERANCES FROM MEETING PROPER (after 1h mark) ===")
    mid = [u for u in utts if u.start > 3600][:5]
    for u in mid:
        print(f"[{u.start:8.2f}s → {u.end:8.2f}s] ({u.speaker}) {u.text[:200]}")
    print(f"\n=== SIZE STATS ===")
    total_chars = sum(len(u.text) for u in utts)
    print(f"Total chars: {total_chars:,}")
    print(f"Median utterance chars: {sorted(len(u.text) for u in utts)[len(utts)//2]}")
    print(f"Utterances >500 chars: {sum(1 for u in utts if len(u.text) > 500)}")
    print(f"Utterances >2000 chars: {sum(1 for u in utts if len(u.text) > 2000)}")


if __name__ == "__main__":
    main(sys.argv[1])
