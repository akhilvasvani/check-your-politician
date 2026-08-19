#!/usr/bin/env python3
"""Smoke test: run flatten + resolve over the 9 spike VTTs, print coverage.

This intentionally lives outside build_transcripts.py while we iterate — it
uses the spike VTT paths directly. Once build_transcripts.py exists, delete
this script.
"""
from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).parent.parent.parent  # la-money-votes/
sys.path.insert(0, str(REPO / "scripts"))

from transcripts.vtt_flatten import parse_vtt, dedupe_rolling, stitch_utterances
from transcripts.speaker_resolver import SpeakerResolver

# 9-meeting spike corpus (uploaded to sandbox in prior session)
FILES = [
    "/home/user/workspace/uploaded_attachments/a5e837b5702b4ef7b0b2da7f50342c83/UkdZRHDB9qs.en-uYU-mmqFLq8.vtt",
    "/home/user/workspace/uploaded_attachments/86dae4884b354ce89901792f5b88c442/eLYlonECp7o.en-uYU-mmqFLq8.vtt",
    "/home/user/workspace/uploaded_attachments/86dae4884b354ce89901792f5b88c442/MBjio010l60.en-uYU-mmqFLq8.vtt",
    "/home/user/workspace/uploaded_attachments/86dae4884b354ce89901792f5b88c442/oHYuOqkXv-0.en-uYU-mmqFLq8.vtt",
    "/home/user/workspace/uploaded_attachments/86dae4884b354ce89901792f5b88c442/QePVCuF0iAY.en-uYU-mmqFLq8.vtt",
    "/home/user/workspace/uploaded_attachments/37072b1f2875430aa8c30d0147125d8b/oPUdYYi9HyE.en-uYU-mmqFLq8.vtt",
    "/home/user/workspace/uploaded_attachments/37072b1f2875430aa8c30d0147125d8b/welTRe5_RH4.en-uYU-mmqFLq8.vtt",
    "/home/user/workspace/uploaded_attachments/37072b1f2875430aa8c30d0147125d8b/H-OkhDWvgYE.en-uYU-mmqFLq8.vtt",
    "/home/user/workspace/uploaded_attachments/37072b1f2875430aa8c30d0147125d8b/hyhgFSAqBRM.en-uYU-mmqFLq8.vtt",
]

resolver = SpeakerResolver(REPO / "data" / "transcripts" / "roster.json")

overall = Counter()  # by resolution_method
unresolved: list[tuple[str, str]] = []  # (video_id, source_label)

for path in FILES:
    p = Path(path)
    video_id = p.stem.split(".")[0]
    cues = parse_vtt(p)
    deduped = dedupe_rolling(cues)
    utts = stitch_utterances(deduped)
    first_labeled = next((i for i, u in enumerate(utts) if u.speaker is not None), 0)
    utts = utts[first_labeled:]

    for u in utts:
        r = resolver.resolve(u.speaker)
        method = r.resolution_method
        if method.startswith("fuzzy-from:"):
            method_bucket = "fuzzy"
        else:
            method_bucket = method
        overall[method_bucket] += 1
        if r.resolved_role == "unknown":
            unresolved.append((video_id, str(u.speaker)))

total = sum(overall.values())
print(f"Total utterances processed: {total}")
print()
print("Resolution method breakdown:")
for method, n in sorted(overall.items(), key=lambda kv: -kv[1]):
    pct = 100.0 * n / total
    print(f"  {method:>22}  {n:>5}  ({pct:.1f}%)")

print()
print(f"Unresolved samples ({len(unresolved)} total, first 15):")
for vid, lab in unresolved[:15]:
    print(f"  {vid}  label={lab!r}")
