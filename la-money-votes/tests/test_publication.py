"""Step 4C, Checkpoint 1: staging/output routing and effective-snapshot
validation (scripts/build_all.py stage_snapshot(), scripts/validate_data.py
validate_snapshot() / validate_snapshot_claims()).

Nothing here publishes: every test asserts that the published tree
(data/officials/*/*.json and data/freshness.json) is byte-identical after
staging, whatever the outcome. Offline only (CSV fixtures, no network).
"""

from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import build_all
import build_funding
import build_record
import validate_data

from .test_freshness import NOW_1, NOW_LATER, FreshnessTestCase


class StagingTestCase(FreshnessTestCase):
    def setUp(self):
        super().setUp()
        self.stage_root = self.repo.path("data", "raw", ".publish", "test-run", "staging")

    def published_bytes(self):
        root = self.repo.root
        paths = sorted(root.glob("data/officials/*/*.json"))
        if self.fpath.exists():
            paths.append(self.fpath)
        return {str(p.relative_to(root)): p.read_bytes() for p in paths}

    def stage(self, *, now=NOW_LATER, target_ids=None, csv=True):
        kwargs = dict(officials=self.officials, sources_registry=self.sources_registry, now=now, target_ids=target_ids)
        if csv:
            kwargs.update(
                csv_path=self.repo.path("data", "raw", "contributions.csv"),
                statements_csv=self.repo.path("data", "raw", "statements_filed.csv"),
            )
        else:
            kwargs.update(csv_path=self.repo.path("data", "raw", "does-not-exist.csv"))
        return build_all.stage_snapshot(self.stage_root, **kwargs)

    def assert_fatal_contains(self, report, fragment):
        self.assertFalse(report.ok)
        self.assertTrue(any(fragment in e for e in report.fatal_errors), report.fatal_errors)

    def break_record_fixture(self, official_id="official-a"):
        fixture = self.repo.path("data", "sources", "records", f"{official_id}.json")
        data = json.loads(fixture.read_text())
        data["items"][0]["date"] = "not-a-date"
        fixture.write_text(json.dumps(data))


class TestStagingRouting(StagingTestCase):
    def test_full_build_stages_everything_and_publishes_nothing(self):
        self.build(now=NOW_1)  # an existing published snapshot
        before = self.published_bytes()
        report, snap = self.stage()
        self.assertTrue(report.ok, report.fatal_errors)
        self.assertTrue(snap.ok, snap.problems)
        self.assertEqual(self.published_bytes(), before)
        expected = {(oid, ds) for oid in self.ids for ds in ("funding", "record")}
        self.assertEqual(snap.staged, expected)
        for key, path in snap.effective_paths.items():
            self.assertEqual(path, self.stage_root / "officials" / key[0] / f"{key[1]}.json")
        self.assertTrue((self.stage_root / "freshness.json").is_file())
        self.assertEqual(snap.freshness["generated_at"], "2026-11-02T15:00:00+00:00")

    def test_first_ever_full_build_stages_without_publishing(self):
        before = self.published_bytes()
        self.assertEqual(before, {})  # nothing published yet
        report, snap = self.stage(now=NOW_1)
        self.assertTrue(report.ok, report.fatal_errors)
        self.assertEqual(self.published_bytes(), {})

    def test_builders_default_out_root_is_unchanged(self):
        # standalone/direct callers still write the published path (D4)
        status, _, problems, _ = build_record.build_record_for_official("official-a", self.sources_registry, "2026-10-18")
        self.assertEqual((status, problems), ("ok", []))
        self.assertTrue(self.repo.path("data", "officials", "official-a", "record.json").is_file())


class TestBuilderFailurePolicy(StagingTestCase):
    def test_expected_record_failure_retains_previous_published_file(self):
        self.build(now=NOW_1)
        before = self.published_bytes()
        self.break_record_fixture("official-a")
        report, snap = self.stage()
        self.assertTrue(snap.ok, snap.problems)  # partial success is a valid snapshot
        self.assertFalse(report.ok)  # but the build still reports the failure
        self.assertFalse(report.fatal_errors)
        self.assertNotIn(("official-a", "record"), snap.staged)
        self.assertEqual(
            snap.effective_paths[("official-a", "record")],
            self.repo.path("data", "officials", "official-a", "record.json"),
        )
        record = self.record(snap.freshness)
        self.assertEqual((record["status"], record["last_success_at"]), ("failed", "2026-10-18"))
        self.assertIn("BUILD_FAILED_PREVIOUS_DATA_SERVED", record["warning_codes"])
        self.assertEqual(self.published_bytes(), before)

    def test_first_ever_expected_failure_is_fatal(self):
        self.break_record_fixture("official-a")
        report, snap = self.stage(now=NOW_1)
        self.assert_fatal_contains(report, "official-a.record: NO_PUBLISHABLE_FILE")
        self.assertFalse(snap.ok)
        self.assertEqual(self.published_bytes(), {})

    def test_first_ever_skipped_funding_is_fatal(self):
        report, _ = self.stage(now=NOW_1, csv=False)
        self.assert_fatal_contains(report, "official-a.funding: NO_PUBLISHABLE_FILE")
        self.assert_fatal_contains(report, "official-b.funding: NO_PUBLISHABLE_FILE")
        self.assertEqual(self.published_bytes(), {})

    def test_skipped_funding_with_previous_output_is_a_valid_partial_snapshot(self):
        self.build(now=NOW_1)
        before = self.published_bytes()
        report, snap = self.stage(csv=False)
        self.assertTrue(report.ok, report.fatal_errors)  # skipped alone does not fail the build
        self.assertTrue(snap.ok, snap.problems)
        self.assertEqual(self.funding(snap.freshness)["status"], "skipped")
        self.assertEqual(self.published_bytes(), before)

    def test_unexpected_funding_exception_is_fatal_and_returns_no_snapshot(self):
        self.build(now=NOW_1)
        before = self.published_bytes()
        with mock.patch.object(build_funding, "build_funding_payload", side_effect=RuntimeError("boom")):
            report, snap = self.stage()
        self.assertIsNone(snap)
        self.assert_fatal_contains(report, "funding builder raised unexpectedly: RuntimeError: boom")
        self.assertEqual(self.published_bytes(), before)

    def test_unexpected_record_exception_is_fatal_and_returns_no_snapshot(self):
        self.build(now=NOW_1)
        before = self.published_bytes()
        with mock.patch.object(build_record, "load_fixture", side_effect=KeyError("boom")):
            report, snap = self.stage()
        self.assertIsNone(snap)
        self.assert_fatal_contains(report, "record builder raised unexpectedly: KeyError")
        self.assertEqual(self.published_bytes(), before)

    def test_unexpected_exception_stops_before_later_officials(self):
        self.build(now=NOW_1)
        calls = []
        real = build_record.build_record_for_official

        def flaky(official_id, *a, **kw):
            calls.append(official_id)
            if official_id == "official-a":
                raise RuntimeError("boom")
            return real(official_id, *a, **kw)

        with mock.patch.object(build_record, "build_record_for_official", flaky):
            report, snap = self.stage()
        self.assertIsNone(snap)
        self.assertEqual(calls, ["official-a"])


class TestEffectiveSnapshotValidation(StagingTestCase):
    def test_retained_file_that_is_schema_invalid_blocks_the_snapshot(self):
        self.build(now=NOW_1)
        self.break_record_fixture("official-a")  # official-a record will be retained
        retained = self.repo.path("data", "officials", "official-a", "record.json")
        self.write_json(retained, {"items": []})  # missing required fields
        before = self.published_bytes()
        report, snap = self.stage()
        self.assertFalse(snap.ok)
        self.assert_fatal_contains(report, "snapshot: official-a/record.json: $: missing required field")
        self.assertEqual(self.published_bytes(), before)

    def assert_retained_record_mutation_blocks(self, mutate, fragment):
        self.build(now=NOW_1)
        self.break_record_fixture("official-a")  # official-a record will be retained
        mutate(self.repo.path("data", "officials", "official-a", "record.json"))
        before = self.published_bytes()
        report, _ = self.stage()
        self.assert_fatal_contains(report, fragment)
        self.assertEqual(self.published_bytes(), before)

    def test_retained_file_that_is_malformed_json_blocks_the_snapshot(self):
        self.assert_retained_record_mutation_blocks(lambda p: p.write_text("{not json"), "official-a/record.json: not valid JSON")

    def test_retained_file_that_is_not_utf8_blocks_the_snapshot(self):
        self.assert_retained_record_mutation_blocks(lambda p: p.write_bytes(b"\xff\xfe"), "official-a/record.json: not valid UTF-8")

    def test_retained_file_that_is_missing_blocks_the_snapshot(self):
        self.assert_retained_record_mutation_blocks(lambda p: p.unlink(), "official-a.record: NO_PUBLISHABLE_FILE")

    def test_staged_file_missing_or_malformed_is_reported(self):
        self.build(now=NOW_1)
        _, snap = self.stage()
        self.assertTrue(snap.ok)
        staged = self.stage_root / "officials" / "official-a" / "funding.json"
        staged.write_text("{truncated")
        problems = validate_data.validate_snapshot(self.officials, snap.effective_paths, snap.freshness)
        self.assertTrue(any("official-a/funding.json: not valid JSON" in p for p in problems), problems)
        staged.unlink()
        problems = validate_data.validate_snapshot(self.officials, snap.effective_paths, snap.freshness)
        self.assertIn("official-a: missing funding.json", problems)

    def test_staged_file_schema_invalid_is_reported(self):
        self.build(now=NOW_1)
        _, snap = self.stage()
        staged = self.stage_root / "officials" / "official-b" / "record.json"
        data = json.loads(staged.read_text())
        data["items"][0]["council_file"] = "not-an-id"
        staged.write_text(json.dumps(data))
        problems = validate_data.validate_snapshot(self.officials, snap.effective_paths, snap.freshness)
        self.assertIn("official-b/record.json: invalid council_file 'not-an-id'", problems)

    def test_invalid_freshness_payload_blocks_the_snapshot(self):
        self.build(now=NOW_1)
        before = self.published_bytes()
        real = build_all._record_entry

        def bad_entry(**kw):
            entry = real(**kw)
            entry["item_count"] = -1
            return entry

        with mock.patch.object(build_all, "_record_entry", bad_entry):
            report, snap = self.stage()
        self.assertFalse(snap.ok)
        self.assert_fatal_contains(report, "item_count: must be a nonnegative integer")
        self.assertEqual(self.published_bytes(), before)

    def test_unexpected_file_in_staging_is_reported(self):
        self.build(now=NOW_1)
        (self.stage_root / "officials" / "official-a").mkdir(parents=True)
        (self.stage_root / "officials" / "official-a" / "notes.json").write_text("{}")
        report, _ = self.stage()
        self.assert_fatal_contains(report, "unexpected file in staging: officials/official-a/notes.json")

    def test_validate_all_cli_behavior_is_unchanged(self):
        # the claim checks are not part of validate_data.py's CLI
        self.assertNotIn("validate_snapshot_claims", validate_data.validate_all.__code__.co_names)


class TestSnapshotClaims(StagingTestCase):
    """validate_snapshot_claims() on a real staged snapshot, mutated one way at
    a time."""

    def setUp(self):
        super().setUp()
        self.build(now=NOW_1)
        self.previous = json.loads(self.fpath.read_text())

    def claims(self, freshness, staged, effective_paths, target_ids=None, previous="default"):
        return validate_data.validate_snapshot_claims(
            self.officials,
            freshness,
            self.previous if previous == "default" else previous,
            staged,
            effective_paths,
            target_ids,
        )

    def test_clean_snapshot_has_no_claim_problems(self):
        _, snap = self.stage()
        self.assertEqual(self.claims(snap.freshness, snap.staged, snap.effective_paths), [])

    def test_ok_entry_requires_a_staged_output(self):
        _, snap = self.stage()
        staged = set(snap.staged) - {("official-a", "funding")}
        paths = dict(snap.effective_paths)
        paths[("official-a", "funding")] = build_all.published_output_path("official-a", "funding")
        problems = self.claims(snap.freshness, staged, paths)
        self.assertIn("official-a.funding: status 'ok' requires an output staged by this run", problems)

    def test_failed_entry_must_not_have_a_staged_output(self):
        self.break_record_fixture("official-a")
        _, snap = self.stage()
        staged = set(snap.staged) | {("official-a", "record")}
        problems = self.claims(snap.freshness, staged, snap.effective_paths)
        self.assertIn("official-a.record: status 'failed' but this run staged an output", problems)
        self.assertIn(
            "official-a.record: BUILD_FAILED_PREVIOUS_DATA_SERVED without a retained published file", problems
        )

    def test_retained_file_needs_a_prior_last_success_at(self):
        self.break_record_fixture("official-a")
        _, snap = self.stage()
        freshness = copy.deepcopy(snap.freshness)
        freshness["officials"]["official-a"]["record"]["last_success_at"] = None
        problems = self.claims(freshness, snap.staged, snap.effective_paths)
        self.assertIn("official-a.record: retains a published file but last_success_at is null", problems)

    def test_counts_must_match_staged_and_retained_files(self):
        self.break_record_fixture("official-a")  # official-a record retained
        _, snap = self.stage()
        freshness = copy.deepcopy(snap.freshness)
        freshness["officials"]["official-b"]["funding"]["displayed_donor_count"] += 1
        freshness["officials"]["official-a"]["record"]["item_count"] += 1
        problems = self.claims(freshness, snap.staged, snap.effective_paths)
        self.assertTrue(any(p.startswith("official-b.funding: displayed_donor_count") for p in problems), problems)
        self.assertTrue(any(p.startswith("official-a.record: item_count") for p in problems), problems)

    def test_freshness_ids_must_match_officials(self):
        _, snap = self.stage()
        freshness = copy.deepcopy(snap.freshness)
        freshness["officials"]["ghost"] = freshness["officials"].pop("official-b")
        problems = self.claims(freshness, snap.staged, snap.effective_paths)
        self.assertTrue(any(p.startswith("freshness ids do not match officials.json") for p in problems), problems)
        self.assertIn("official-b.funding: no freshness entry", problems)

    def test_staged_output_for_unknown_official_is_rejected(self):
        _, snap = self.stage()
        problems = self.claims(snap.freshness, set(snap.staged) | {("ghost", "funding")}, snap.effective_paths)
        self.assertIn("staged outputs for unknown officials/datasets: ['ghost/funding']", problems)


class TestSubsetSnapshots(StagingTestCase):
    def setUp(self):
        super().setUp()
        self.build(now=NOW_1)
        self.previous = json.loads(self.fpath.read_text())

    def test_untargeted_official_keeps_files_and_entry_exactly_including_older_ok(self):
        before = self.published_bytes()
        report, snap = self.stage(target_ids={"official-a"})
        self.assertTrue(report.ok, report.fatal_errors)
        self.assertTrue(snap.ok, snap.problems)
        self.assertEqual(snap.staged, {("official-a", "funding"), ("official-a", "record")})
        b = snap.freshness["officials"]["official-b"]
        self.assertEqual(b, self.previous["officials"]["official-b"])
        self.assertEqual(b["funding"]["status"], "ok")  # older ok, not rebuilt this run: legitimate
        self.assertEqual(b["funding"]["attempted_at"], "2026-10-18T12:00:00+00:00")
        for ds in ("funding", "record"):
            self.assertEqual(snap.effective_paths[("official-b", ds)], build_all.published_output_path("official-b", ds))
        self.assertEqual(self.published_bytes(), before)

    def test_targeted_failure_on_subset_retains_previous_output(self):
        self.break_record_fixture("official-a")
        report, snap = self.stage(target_ids={"official-a"})
        self.assertTrue(snap.ok, snap.problems)
        self.assertEqual(snap.staged, {("official-a", "funding")})
        self.assertEqual(self.record(snap.freshness)["status"], "failed")

    def test_untargeted_entry_must_equal_previous_and_must_not_be_staged(self):
        _, snap = self.stage(target_ids={"official-a"})
        freshness = copy.deepcopy(snap.freshness)
        freshness["officials"]["official-b"]["record"]["attempted_at"] = freshness["generated_at"]
        problems = validate_data.validate_snapshot_claims(
            self.officials, freshness, self.previous, set(snap.staged) | {("official-b", "funding")},
            snap.effective_paths, {"official-a"},
        )
        self.assertIn("official-b.record: untargeted entry differs from the previous snapshot", problems)
        self.assertIn("official-b.funding: untargeted official has a staged output", problems)

    def test_untargeted_retained_file_is_validated(self):
        self.write_json(self.repo.path("data", "officials", "official-b", "funding.json"), {"donors": []})
        report, _ = self.stage(target_ids={"official-a"})
        self.assert_fatal_contains(report, "snapshot: official-b/funding.json: $: missing required field")


class TestReviewRevocationStaging(StagingTestCase):
    def test_revocation_is_staged_but_published_freshness_keeps_the_previous_date(self):
        self.set_review("official-a", "2026-09-30")
        self.build(now=NOW_1)
        before = self.published_bytes()
        self.set_review("official-a", None)
        report, snap = self.stage()
        self.assertTrue(snap.ok, snap.problems)
        self.assertIsNone(self.record(snap.freshness)["reviewed_through"])
        published = json.loads(self.fpath.read_text())
        self.assertEqual(self.record(published)["reviewed_through"], "2026-09-30")
        self.assertEqual(self.published_bytes(), before)


if __name__ == "__main__":
    unittest.main()
