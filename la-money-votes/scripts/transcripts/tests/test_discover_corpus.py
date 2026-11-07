import json
import tempfile
import unittest
from pathlib import Path

from transcripts.discover_corpus import (
    build_manifest,
    exclusion_reason,
    extract_youtube_id,
)


TAXONOMY = {
    1: {"canonical_name": "Los Angeles City Council", "body_type": "city_council"},
    4: {"canonical_name": "Public Safety Committee", "body_type": "standing_committee"},
}


def row(**overrides):
    base = {
        "id": 100,
        "committeeId": 1,
        "title": "City Council Meeting",
        "dateTime": "2026-08-18T10:00:00",
        "meetingState": 3,
        "videoUrl": "https://youtube.com/watch?v=2Wm-11hPNns",
    }
    base.update(overrides)
    return base


class DiscoverCorpusTests(unittest.TestCase):
    def test_extract_youtube_id(self):
        self.assertEqual(
            extract_youtube_id("https://youtube.com/watch?v=2Wm-11hPNns"),
            "2Wm-11hPNns",
        )
        self.assertEqual(
            extract_youtube_id("https://youtu.be/2Wm-11hPNns?t=10"),
            "2Wm-11hPNns",
        )
        self.assertIsNone(extract_youtube_id(""))
        self.assertIsNone(extract_youtube_id("https://example.com/video"))

    def test_policy_exclusions(self):
        self.assertEqual(
            exclusion_reason(row(title="City Council Meeting - SAP"), TAXONOMY),
            "sap_duplicate",
        )
        self.assertEqual(
            exclusion_reason(
                row(committeeId=4, title="CANCELLED - Public Safety Committee"),
                TAXONOMY,
            ),
            "cancelled",
        )
        self.assertEqual(
            exclusion_reason(
                row(committeeId=999, title="Ad Hoc Committee for Example"),
                TAXONOMY,
            ),
            "ad_hoc_body",
        )

    def test_manifest_preserves_unknown_caption_state(self):
        manifest = build_manifest(
            [row()],
            TAXONOMY,
            {},
            days=90,
            generated_at="2026-08-19T20:00:00+00:00",
        )
        meeting = manifest["meetings"][0]
        self.assertEqual(meeting["pipeline_state"], "discovered")
        self.assertEqual(meeting["caption_status"], "not_checked_m3_0")
        self.assertEqual(meeting["ingest_disposition"], "m3_1_caption_preflight")
        self.assertEqual(manifest["summary"]["new_video_candidates"], 1)

    def test_no_video_is_terminally_blocked(self):
        manifest = build_manifest(
            [row(videoUrl="")],
            TAXONOMY,
            {},
            days=90,
            generated_at="2026-08-19T20:00:00+00:00",
        )
        meeting = manifest["meetings"][0]
        self.assertEqual(meeting["pipeline_state"], "blocked")
        self.assertFalse(meeting["retryable"])
        self.assertEqual(meeting["missing_reason"], "primegov_row_has_no_youtube_video")

    def test_discovery_regeneration_preserves_matching_checkpoint_and_error(self):
        prior = {
            "meetings": [{
                "primegov_id": 100,
                "video_id": "2Wm-11hPNns",
                "pipeline_state": "caption_preflighted",
                "caption_status": "approved_cart_track",
                "caption_language": "en-uYU-mmqFLq8",
                "caption_preflighted_at": "2026-08-19T20:10:00+00:00",
                "last_error": "old transient error retained until successful fetch",
                "retryable": True,
                "ingest_disposition": "m3_1_caption_fetch",
            }]
        }
        manifest = build_manifest(
            [row()],
            TAXONOMY,
            {},
            days=90,
            generated_at="2026-08-19T20:00:00+00:00",
            prior_manifest=prior,
        )
        meeting = manifest["meetings"][0]
        self.assertEqual(meeting["pipeline_state"], "caption_preflighted")
        self.assertEqual(meeting["caption_status"], "approved_cart_track")
        self.assertEqual(
            meeting["last_error"], "old transient error retained until successful fetch"
        )
        self.assertEqual(manifest["summary"]["new_video_candidates"], 1)

    def test_existing_canonical_json_marks_video_published(self):
        with tempfile.TemporaryDirectory() as tmp:
            artifact = Path(tmp) / "existing.json"
            artifact.write_text(json.dumps({"video_id": "2Wm-11hPNns"}))
            existing = {
                "2Wm-11hPNns": {
                    "artifact_path": "data/transcripts/2Wm-11hPNns.json",
                    "artifact_sha256": "abc",
                    "utterance_count": 10,
                    "official_ids": ["cd01-official"],
                    "canonical_primegov_id": 100,
                    "canonical_title": "City Council Meeting",
                }
            }
            manifest = build_manifest(
                [row()],
                TAXONOMY,
                existing,
                days=90,
                generated_at="2026-08-19T20:00:00+00:00",
            )
            meeting = manifest["meetings"][0]
            self.assertEqual(meeting["pipeline_state"], "published")
            self.assertEqual(meeting["caption_status"], "available_indexed")
            self.assertEqual(meeting["embedding_model"], "pplx-embed-v1-0.6b")

    def test_duplicate_video_id_is_reported_not_collapsed(self):
        manifest = build_manifest(
            [
                row(id=100),
                row(id=101, title="Special City Council Meeting #2"),
            ],
            TAXONOMY,
            {},
            days=90,
            generated_at="2026-08-19T20:00:00+00:00",
        )
        self.assertEqual(len(manifest["meetings"]), 2)
        self.assertEqual(manifest["summary"]["unique_youtube_videos"], 1)
        self.assertEqual(manifest["summary"]["video_id_collisions"], 1)


if __name__ == "__main__":
    unittest.main()
