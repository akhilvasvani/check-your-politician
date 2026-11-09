"""Offline safeguards around canonical transcript construction and indexing."""

from __future__ import annotations

import sys
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from transcripts.build_transcripts import Meeting, build_transcript_json, embed_and_upsert  # noqa: E402
from transcripts.chunker import TurnChunk  # noqa: E402
from transcripts.speaker_resolver import SpeakerResolver  # noqa: E402


class FakeUtterance:
    def __init__(self, speaker: str, text: str):
        self.start = 1.0
        self.end = 2.0
        self.speaker = speaker
        self.text = text


class NeverCalledSupabase:
    def table(self, _name):
        raise AssertionError("Supabase must not be called after partial embeddings")


class TranscriptBuildTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root = Path(__file__).resolve().parent.parent
        cls.resolver = SpeakerResolver(root / "data" / "transcripts" / "roster.json")

    def test_canonical_artifact_keeps_all_source_meetings(self):
        meeting = Meeting(
            video_id="welTRe5_RH4",
            meeting_date=date(2026, 6, 30),
            primegov_id=17801,
            title="City Council Meeting",
            source_meetings=(
                {"primegov_id": 17801, "title": "City Council Meeting"},
                {"primegov_id": 18451, "title": "Special City Council Meeting #2"},
            ),
        )
        doc = build_transcript_json(
            meeting, [FakeUtterance("A. Nazarian", "I move the item.")], self.resolver
        )
        self.assertEqual(
            [row["primegov_id"] for row in doc["source_meetings"]], [17801, 18451]
        )

    def test_partial_embedding_batch_refuses_to_call_supabase(self):
        chunks = [
            TurnChunk(0, 0.0, 1.0, "A. Nazarian", "one", 1, 0, 1),
            TurnChunk(1, 1.0, 2.0, "A. Nazarian", "two", 1, 0, 1),
        ]
        transcript = {"video_id": "abcdefghijk", "meeting_date": "2026-08-19"}

        def partial_embedder(_texts, _api_key):
            return [[0.0] * 1024]

        with self.assertRaisesRegex(RuntimeError, "Partial embeddings"):
            embed_and_upsert(
                transcript,
                chunks,
                NeverCalledSupabase(),
                "not-a-real-key",
                self.resolver,
                embedder=partial_embedder,
            )


if __name__ == "__main__":
    unittest.main()
