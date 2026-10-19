"""Unit tests for scripts/transcripts/chunker.py.

The M1.0 audit locks these invariants:
  1. Every utterance becomes at least one chunk (no drops).
  2. Attribution is 1:1 with the utterance's speaker (no dominant vote).
  3. Turns > SUB_CHUNK_MAX_WORDS are split into sub-chunks that:
       - never split a sentence,
       - carry monotonic start_sec bracketed by the utterance's [start, end],
       - preserve the raw speaker label on every sub-chunk,
       - each stay within a bounded word count.
  4. Whole-turn chunks report sub_chunk_of == 1, sub_chunk_idx == 0.
"""

from __future__ import annotations

import sys
import unittest
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from transcripts.chunker import (  # noqa: E402
    SUB_CHUNK_MAX_WORDS,
    SUB_CHUNK_TARGET_WORDS,
    chunk_turns,
)


@dataclass
class FakeUtt:
    """Minimal Utterance shim so tests don't depend on vtt_flatten."""
    start: float
    end: float
    speaker: str | None
    text: str


class ChunkTurnsTests(unittest.TestCase):
    def test_short_turn_emits_single_chunk(self):
        utts = [FakeUtt(10.0, 15.0, "T. McOsker", "Thank you Mr. President.")]
        chunks = chunk_turns(utts)
        self.assertEqual(len(chunks), 1)
        c = chunks[0]
        self.assertEqual(c.chunk_idx, 0)
        self.assertEqual(c.source_label, "T. McOsker")
        self.assertEqual(c.text, "Thank you Mr. President.")
        self.assertEqual(c.sub_chunk_idx, 0)
        self.assertEqual(c.sub_chunk_of, 1)
        self.assertEqual(c.start_sec, 10.0)
        self.assertEqual(c.end_sec, 15.0)

    def test_empty_text_utterance_is_skipped(self):
        utts = [
            FakeUtt(0.0, 1.0, "Speaker", "   "),
            FakeUtt(1.0, 2.0, "Clerk", "First up, item 44."),
        ]
        chunks = chunk_turns(utts)
        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0].source_label, "Clerk")

    def test_chunk_idx_is_monotonic_across_utts(self):
        utts = [
            FakeUtt(0.0, 5.0, "A. Nazarian", "Short one."),
            FakeUtt(5.0, 10.0, "T. Park", "Also short."),
            FakeUtt(10.0, 12.0, "Speaker", "Public comment sentence."),
        ]
        chunks = chunk_turns(utts)
        self.assertEqual([c.chunk_idx for c in chunks], [0, 1, 2])

    def test_long_turn_is_subchunked_on_sentence_boundaries(self):
        # 200-word monologue, 20 sentences of ~10 words each. Must split into
        # ≥ 2 sub-chunks that never mid-cut a sentence.
        sentence = "The chamber urges enhanced games agreement without further delay today. "
        text = (sentence * 20).strip()
        utts = [FakeUtt(100.0, 300.0, "T. McOsker", text)]
        chunks = chunk_turns(utts)
        self.assertGreater(len(chunks), 1,
                           "long turn should produce >1 sub-chunk")
        # Every chunk must end at a sentence terminator (last char in .?!).
        for c in chunks:
            self.assertRegex(c.text.strip(), r"[.?!]$",
                             f"sub-chunk did not end at a sentence: {c.text[:80]!r}")
        # Every chunk must carry the speaker label.
        for c in chunks:
            self.assertEqual(c.source_label, "T. McOsker")
        # sub_chunk_of must be consistent across the group.
        n = chunks[0].sub_chunk_of
        self.assertGreater(n, 1)
        self.assertTrue(all(c.sub_chunk_of == n for c in chunks))
        self.assertEqual([c.sub_chunk_idx for c in chunks], list(range(n)))

    def test_sub_chunk_word_counts_are_bounded(self):
        # Ensure no sub-chunk is dramatically over target. We allow one
        # sentence of slack over target because we never split mid-sentence.
        sentence = "This is a short public safety comment about the port. "
        text = (sentence * 40).strip()  # ~400 words, ~40 sentences
        utts = [FakeUtt(0.0, 240.0, "T. McOsker", text)]
        chunks = chunk_turns(utts)
        # 40 sentences * ~10 words = ~400 words / target 90 → ~5 sub-chunks
        max_group_words = SUB_CHUNK_TARGET_WORDS + 15  # + one avg sentence
        for c in chunks:
            self.assertLessEqual(
                c.token_count, max_group_words,
                f"sub-chunk exceeds target+slack: {c.token_count} words"
            )

    def test_sub_chunk_start_secs_are_monotonic_and_bracketed(self):
        text = " ".join(f"Sentence number {i} on the topic." for i in range(60))
        utts = [FakeUtt(100.0, 300.0, "N. Raman", text)]
        chunks = chunk_turns(utts)
        starts = [c.start_sec for c in chunks]
        self.assertEqual(starts, sorted(starts), "start_sec not monotonic")
        for c in chunks:
            self.assertGreaterEqual(c.start_sec, 100.0 - 1e-6)
            self.assertLessEqual(c.end_sec, 300.0 + 1e-6)
            self.assertLessEqual(c.start_sec, c.end_sec)
        # Last sub-chunk must end at utterance end (contract with the deep-link
        # in the UI, which uses start_sec).
        self.assertAlmostEqual(chunks[-1].end_sec, 300.0, places=3)

    def test_over_long_single_sentence_is_kept_whole(self):
        # Pathological CART run-on: a single "sentence" longer than target.
        # Must still be emitted (never dropped), even though it exceeds target.
        long_sentence = ("this is one very long sentence " * 25).strip() + "."
        utts = [FakeUtt(0.0, 60.0, "Speaker", long_sentence)]
        chunks = chunk_turns(utts)
        self.assertGreaterEqual(len(chunks), 1)
        joined = " ".join(c.text for c in chunks)
        self.assertIn("this is one very long sentence", joined)

    def test_jurado_regression_attributes_to_cd14(self):
        # M1.0 audit finding: Jurado spoke 45 times but had 0 attributed
        # chunks in the DB because the old chunker's word-count vote lost
        # her turns to Council President / Speaker. Under chunk_turns, her
        # every utterance is her own chunk. This test doesn't run the
        # resolver — it verifies the chunker preserves the raw label so
        # the resolver has something to work with.
        utts = [
            FakeUtt(0.0, 5.0, "Council President", "Item 44. What say you?"),
            FakeUtt(5.0, 20.0, "Y. Jurado",
                    "Thank you Mr. President. I move to amend the record."),
            FakeUtt(20.0, 25.0, "Speaker", "Public comment on item 44."),
        ]
        chunks = chunk_turns(utts)
        speakers = [c.source_label for c in chunks]
        self.assertIn("Y. Jurado", speakers)
        jurado_chunks = [c for c in chunks if c.source_label == "Y. Jurado"]
        self.assertEqual(len(jurado_chunks), 1)
        self.assertIn("amend the record", jurado_chunks[0].text)

    def test_token_count_matches_split_len(self):
        utts = [FakeUtt(0.0, 1.0, "H. Hutt", "One two three four five.")]
        c = chunk_turns(utts)[0]
        self.assertEqual(c.token_count, 5)

    def test_zero_duration_utt_still_emits_chunk_with_start_time(self):
        # Rare but seen: rolling-cue edge case gives start == end for a
        # single-word interjection. Chunker must not divide by zero.
        utts = [FakeUtt(42.0, 42.0, "Council President", "Aye.")]
        c = chunk_turns(utts)[0]
        self.assertEqual(c.start_sec, 42.0)
        self.assertEqual(c.end_sec, 42.0)

    def test_none_speaker_is_preserved(self):
        utts = [FakeUtt(0.0, 3.0, None, "Pre-meeting announcement text.")]
        c = chunk_turns(utts)[0]
        self.assertIsNone(c.source_label)


if __name__ == "__main__":
    unittest.main()
