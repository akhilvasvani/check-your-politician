"""Unit tests for backfill_meeting_dates.

Runs entirely offline against an in-memory PrimeGov fixture. No network
calls, no Supabase calls."""

from __future__ import annotations

import json
import unittest
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory

import sys
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from backfill_meeting_dates import (  # noqa: E402
    PrimegovMeeting,
    build_meeting_index,
    format_plans,
    match_video,
    plan_backfill,
    write_json_updates,
)


PRIMEGOV_FIXTURE = [
    {
        "id": 18466,
        "title": "City Council Meeting",
        "dateTime": "2026-08-14T10:00:00",
        "videoUrl": "https://www.youtube.com/watch?v=MBjio010l60",
    },
    {
        "id": 18451,
        "title": "Special City Council Meeting #2",
        "dateTime": "2026-06-30T10:00:00",
        "videoUrl": "https://www.youtube.com/watch?v=welTRe5_RH4",
    },
    {
        "id": 17724,
        "title": "City Council Meeting",
        "dateTime": "2026-08-04T10:00:00",
        "videoUrl": "https://www.youtube.com/watch?v=UkdZRHDB9qs",
    },
    # A row with no video URL — must be skipped from the index.
    {
        "id": 99999,
        "title": "City Council Meeting",
        "dateTime": "2026-08-01T10:00:00",
        "videoUrl": "",
    },
    # A row with an unparseable date — must be skipped.
    {
        "id": 88888,
        "title": "City Council Meeting",
        "dateTime": "not-a-date",
        "videoUrl": "https://www.youtube.com/watch?v=aaaaaaaaaaa",
    },
]


class BuildMeetingIndexTests(unittest.TestCase):
    def test_indexes_only_rows_with_valid_youtube_ids(self) -> None:
        idx = build_meeting_index(PRIMEGOV_FIXTURE)
        self.assertEqual(set(idx.keys()), {"MBjio010l60", "welTRe5_RH4", "UkdZRHDB9qs"})

    def test_parses_dates(self) -> None:
        idx = build_meeting_index(PRIMEGOV_FIXTURE)
        self.assertEqual(idx["MBjio010l60"].meeting_date, date(2026, 8, 14))
        self.assertEqual(idx["welTRe5_RH4"].meeting_date, date(2026, 6, 30))

    def test_preserves_title_including_specials(self) -> None:
        idx = build_meeting_index(PRIMEGOV_FIXTURE)
        self.assertEqual(idx["welTRe5_RH4"].title, "Special City Council Meeting #2")


class MatchVideoTests(unittest.TestCase):
    def setUp(self) -> None:
        self.idx = build_meeting_index(PRIMEGOV_FIXTURE)

    def test_direct_video_id_match(self) -> None:
        m, method = match_video("MBjio010l60", None, self.idx)
        self.assertIsNotNone(m)
        self.assertEqual(method, "video_id")

    def test_unmatched_video_returns_unmatched(self) -> None:
        m, method = match_video("zzzzzzzzzzz", None, self.idx)
        self.assertIsNone(m)
        self.assertEqual(method, "unmatched")

    def test_date_fallback_off_by_default(self) -> None:
        m, method = match_video("zzzzzzzzzzz", "2026-08-14T00:00:00", self.idx)
        self.assertIsNone(m)
        self.assertEqual(method, "unmatched")

    def test_date_fallback_prefers_closest_regular(self) -> None:
        m, method = match_video(
            "zzzzzzzzzzz",
            "2026-08-04T12:00:00",
            self.idx,
            allow_date_fallback=True,
        )
        self.assertIsNotNone(m)
        self.assertEqual(method, "date_proximity")
        self.assertEqual(m.video_id, "UkdZRHDB9qs")

    def test_date_fallback_skips_special_meetings(self) -> None:
        # welTRe5_RH4 (2026-06-30, special) is closest to 2026-07-01 but
        # not a regular; MBjio010l60 (2026-08-14) is > 3 days away, so
        # nothing should match.
        m, method = match_video(
            "zzzzzzzzzzz",
            "2026-07-01T00:00:00",
            self.idx,
            allow_date_fallback=True,
        )
        self.assertIsNone(m)
        self.assertEqual(method, "unmatched")


class PlanBackfillTests(unittest.TestCase):
    def _make_json(self, tmp: Path, video_id: str, title: str = "(m1.3 re-ingest)") -> Path:
        doc = {
            "video_id": video_id,
            "meeting_date": "2026-08-19",
            "primegov_id": -1,
            "title": title,
            "language_code": "en",
            "ingested_at": "2026-08-19T00:00:00+00:00",
            "coverage": {},
            "utterance_count": 0,
            "utterances": [],
        }
        p = tmp / f"{video_id}.json"
        p.write_text(json.dumps(doc, indent=2))
        return p

    def test_regular_meeting_plans_a_change(self) -> None:
        idx = build_meeting_index(PRIMEGOV_FIXTURE)
        with TemporaryDirectory() as td:
            p = self._make_json(Path(td), "MBjio010l60")
            plans = plan_backfill([p], idx)
        self.assertEqual(len(plans), 1)
        plan = plans[0]
        self.assertEqual(plan.match_method, "video_id")
        self.assertTrue(plan.is_regular)
        self.assertEqual(plan.new_date, "2026-08-14")
        self.assertEqual(plan.new_pgid, 18466)
        self.assertTrue(plan.needs_change)

    def test_special_meeting_flagged_but_planned(self) -> None:
        idx = build_meeting_index(PRIMEGOV_FIXTURE)
        with TemporaryDirectory() as td:
            p = self._make_json(Path(td), "welTRe5_RH4")
            plans = plan_backfill([p], idx)
        plan = plans[0]
        self.assertEqual(plan.match_method, "video_id")
        self.assertFalse(plan.is_regular)
        self.assertIn("non-regular", plan.note)

    def test_unmatched_video_produces_unmatched_plan(self) -> None:
        idx = build_meeting_index(PRIMEGOV_FIXTURE)
        with TemporaryDirectory() as td:
            p = self._make_json(Path(td), "zzzzzzzzzzz")
            plans = plan_backfill([p], idx)
        plan = plans[0]
        self.assertEqual(plan.match_method, "unmatched")
        self.assertFalse(plan.needs_change)


class WriteJsonUpdatesTests(unittest.TestCase):
    def test_writes_changed_fields_and_preserves_rest(self) -> None:
        idx = build_meeting_index(PRIMEGOV_FIXTURE)
        with TemporaryDirectory() as td:
            tmp = Path(td)
            p = tmp / "MBjio010l60.json"
            original = {
                "video_id": "MBjio010l60",
                "meeting_date": "2026-08-19",
                "primegov_id": -1,
                "title": "(m1.3 re-ingest)",
                "language_code": "en",
                "ingested_at": "2026-08-19T00:00:00+00:00",
                "coverage": {"exact": 5},
                "utterance_count": 2,
                "utterances": [{"start_sec": 0.0, "text": "hello"}],
            }
            p.write_text(json.dumps(original, indent=2))
            plans = plan_backfill([p], idx)
            modified = write_json_updates(plans)
            self.assertEqual(modified, 1)
            written = json.loads(p.read_text())
            # Changed fields:
            self.assertEqual(written["meeting_date"], "2026-08-14")
            self.assertEqual(written["primegov_id"], 18466)
            self.assertEqual(written["title"], "City Council Meeting")
            # Preserved fields:
            self.assertEqual(written["language_code"], "en")
            self.assertEqual(written["coverage"], {"exact": 5})
            self.assertEqual(written["utterance_count"], 2)
            self.assertEqual(written["utterances"], [{"start_sec": 0.0, "text": "hello"}])

    def test_idempotent_second_apply_is_a_noop(self) -> None:
        idx = build_meeting_index(PRIMEGOV_FIXTURE)
        with TemporaryDirectory() as td:
            tmp = Path(td)
            p = tmp / "MBjio010l60.json"
            p.write_text(json.dumps({
                "video_id": "MBjio010l60",
                "meeting_date": "2026-08-19",
                "primegov_id": -1,
                "title": "(m1.3 re-ingest)",
                "utterances": [],
            }, indent=2))
            plans_1 = plan_backfill([p], idx)
            write_json_updates(plans_1)
            plans_2 = plan_backfill([p], idx)
            self.assertFalse(plans_2[0].needs_change)
            modified = write_json_updates(plans_2)
        self.assertEqual(modified, 0)


class FormatPlansTests(unittest.TestCase):
    def test_format_runs_without_error(self) -> None:
        idx = build_meeting_index(PRIMEGOV_FIXTURE)
        with TemporaryDirectory() as td:
            tmp = Path(td)
            p = tmp / "MBjio010l60.json"
            p.write_text(json.dumps({
                "video_id": "MBjio010l60",
                "meeting_date": "2026-08-19",
                "primegov_id": -1,
                "title": "(m1.3 re-ingest)",
            }))
            plans = plan_backfill([p], idx)
        out = format_plans(plans)
        self.assertIn("MBjio010l60", out)
        self.assertIn("2026-08-14", out)


if __name__ == "__main__":
    unittest.main()
