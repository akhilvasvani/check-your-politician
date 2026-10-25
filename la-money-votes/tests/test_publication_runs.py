"""Step 4C, Checkpoint 2: journaled publication, rollback, recovery, the build
lock, run ids / report fields, --verify-run and the --skip-freshness dry run.

Every test runs against a TempRepo (never the real data/). Failure injection
patches one of the small seams in scripts/pipeline/publish.py (_replace,
_copy_file, _unlink, _remove_tree) or a builder; lock contention and owner
death use real separate processes. Offline only.
"""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import textwrap
import time
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import build_all
import build_funding
import build_record
from pipeline import publish

from .test_freshness import NOW_1, NOW_LATER, FreshnessTestCase, run_main

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"


class PublishTestCase(FreshnessTestCase):
    def setUp(self):
        super().setUp()
        self.droot = self.repo.path("data")
        self.pdir = publish.publish_dir(self.droot)

    # -- helpers --

    def kwargs(self, *, now=NOW_LATER, target_ids=None, csv=True):
        kw = dict(officials=self.officials, sources_registry=self.sources_registry, now=now, target_ids=target_ids)
        if csv:
            kw.update(
                csv_path=self.repo.path("data", "raw", "contributions.csv"),
                statements_csv=self.repo.path("data", "raw", "statements_filed.csv"),
            )
        else:
            kw.update(csv_path=self.repo.path("data", "raw", "does-not-exist.csv"))
        return kw

    def run_build(self, *, run_id=None, dry_run=False, on_report=None, **kw):
        return build_all.build_snapshot(run_id=run_id, dry_run=dry_run, on_report=on_report, **self.kwargs(**kw))

    def seed(self):
        report, _ = self.run_build(run_id="seed", now=NOW_1)
        self.assertEqual(report.publication, publish.PUB_VERIFIED, (report.fatal_errors, report.publication_problems))
        self.assertTrue(report.ok, report.fatal_errors)
        return report

    def published_bytes(self):
        root = self.repo.root
        paths = sorted(root.glob("data/officials/*/*.json"))
        if self.fpath.exists():
            paths.append(self.fpath)
        return {str(p.relative_to(root)): p.read_bytes() for p in paths}

    def run_dirs(self):
        return sorted(p.name for p in self.pdir.iterdir()) if self.pdir.exists() else []

    def journal(self, run_id):
        return json.loads((publish.run_dir(self.droot, run_id) / "journal.json").read_text())

    def live(self, *parts):
        return self.repo.path("data", *parts).read_bytes()

    def freshness(self):
        return json.loads(self.fpath.read_text())

    def break_record_fixture(self, official_id="official-a"):
        fixture = self.repo.path("data", "sources", "records", f"{official_id}.json")
        data = json.loads(fixture.read_text())
        data["items"][0]["date"] = "not-a-date"
        fixture.write_text(json.dumps(data))

    def change_record_fixtures(self):
        """A valid edit to every record fixture, so the next build's
        record.json files differ from the published ones (without it the
        rebuilt files are byte-identical and a rollback has nothing to undo)."""
        for official_id in self.ids:
            fixture = self.repo.path("data", "sources", "records", f"{official_id}.json")
            data = json.loads(fixture.read_text())
            data["items"][0]["title"] += " (amended)"
            fixture.write_text(json.dumps(data))

    def assert_rolled_back_to(self, before, report, publication=publish.PUB_ROLLED_BACK):
        self.assertEqual(report.publication, publication, report.publication_problems)
        self.assertFalse(report.ok)
        self.assertEqual(report.snapshot_manifest, {})
        self.assertEqual(report.replaced_files, {})
        self.assertEqual(self.published_bytes(), before)

    def recover_ids(self):
        return publish.recover_all(self.droot, self.ids)


def fail_on(seam_name, predicate, exc=None):
    """Patch publish.<seam_name> so calls whose (src, dst) satisfy predicate
    raise OSError; other calls run the real operation."""
    real = getattr(publish, seam_name)

    def wrapper(*args):
        if predicate(*args):
            raise exc or OSError(28, f"injected {seam_name} failure")
        return real(*args)

    return mock.patch.object(publish, seam_name, wrapper)


def is_live(path, *suffix):
    p = Path(path)
    return ".publish" not in p.parts and p.as_posix().endswith("/".join(suffix))


# --- ordinary outcomes ------------------------------------------------------


class TestPublication(PublishTestCase):
    def test_first_full_build_publishes_verified_snapshot_and_cleans_up(self):
        report, freshness = self.run_build(run_id="first", now=NOW_1)
        self.assertTrue(report.ok, report.fatal_errors)
        self.assertEqual((report.publication, report.run_id, report.mode), ("verified", "first", "build"))
        self.assertIsNone(report.journal_state)  # cleaned up
        self.assertEqual(self.run_dirs(), [])
        self.assertEqual(self.freshness(), freshness)
        expected = {publish.target_for(o, d) for o in self.ids for d in ("funding", "record")} | {"freshness.json"}
        self.assertEqual(set(report.snapshot_manifest), expected)
        self.assertEqual(set(report.replaced_files), expected)
        for target, sha in report.snapshot_manifest.items():
            self.assertEqual(publish.sha256_file(self.droot / target), sha)
        self.assertTrue(all(not v["had_prior"] for v in report.replaced_files.values()))
        self.assertEqual(build_all.build_exit_code(report), 0)

    def test_ordinary_partial_success_publishes_and_retains_the_failed_file(self):
        self.seed()
        old_record = self.live("officials", "official-a", "record.json")
        self.break_record_fixture("official-a")
        report, _ = self.run_build(run_id="partial")
        self.assertEqual(report.publication, "verified", report.publication_problems)
        self.assertFalse(report.ok)  # a failed builder is still a failed build
        self.assertEqual(build_all.build_exit_code(report), 1)
        self.assertEqual(self.live("officials", "official-a", "record.json"), old_record)
        self.assertNotIn("officials/official-a/record.json", report.replaced_files)
        self.assertIn("officials/official-a/record.json", report.snapshot_manifest)
        entry = self.freshness()["officials"]["official-a"]["record"]
        self.assertEqual(entry["status"], "failed")
        self.assertIn("BUILD_FAILED_PREVIOUS_DATA_SERVED", entry["warning_codes"])
        self.assertEqual(self.run_dirs(), [])

    def test_first_ever_failure_is_fatal_and_publishes_nothing(self):
        self.break_record_fixture("official-a")
        report, _ = self.run_build(run_id="first-fail", now=NOW_1)
        self.assertEqual(report.publication, "not_attempted")
        self.assertTrue(any("NO_PUBLISHABLE_FILE" in e for e in report.fatal_errors), report.fatal_errors)
        self.assertEqual(self.published_bytes(), {})
        self.assertEqual(self.run_dirs(), [])

    def test_subset_run_preserves_untargeted_files_and_entries(self):
        self.seed()
        before = self.published_bytes()
        prev_b = self.freshness()["officials"]["official-b"]
        report, _ = self.run_build(run_id="subset", target_ids={"official-a"})
        self.assertEqual(report.publication, "verified", report.publication_problems)
        self.assertEqual(report.target_ids, ["official-a"])
        for ds in ("funding", "record"):
            key = f"data/officials/official-b/{ds}.json"
            self.assertEqual(self.published_bytes()[key], before[key])
            self.assertNotIn(f"officials/official-b/{ds}.json", report.replaced_files)
            self.assertIn(f"officials/official-b/{ds}.json", report.snapshot_manifest)
        self.assertEqual(self.freshness()["officials"]["official-b"], prev_b)

    def test_invalid_retained_file_blocks_publication(self):
        self.seed()
        path = self.repo.path("data", "officials", "official-a", "funding.json")
        data = json.loads(path.read_text())
        data["donors"] = data["donors"][:-1] if data["donors"] else [{"bogus": True}]
        path.write_text(json.dumps(data))
        before = self.published_bytes()
        report, _ = self.run_build(run_id="bad-retained", csv=False)  # funding skipped -> retained
        self.assertEqual(report.publication, "not_attempted")
        self.assertTrue(any("official-a.funding" in e for e in report.fatal_errors), report.fatal_errors)
        self.assertEqual(self.published_bytes(), before)
        self.assertEqual(self.run_dirs(), [])

    def test_invalid_staged_file_blocks_publication(self):
        self.seed()
        before = self.published_bytes()
        real = build_record.build_record_for_official

        def corrupting(official_id, *a, **kw):
            result = real(official_id, *a, **kw)
            out = Path(kw["out_root"]) / official_id / "record.json"
            data = json.loads(out.read_text())
            data["items"] = data["items"][:-1]  # count no longer matches freshness
            out.write_text(json.dumps(data))
            return result

        with mock.patch.object(build_record, "build_record_for_official", corrupting):
            report, _ = self.run_build(run_id="bad-staged")
        self.assertEqual(report.publication, "not_attempted")
        self.assertTrue(any("snapshot:" in e for e in report.fatal_errors), report.fatal_errors)
        self.assertEqual(self.published_bytes(), before)
        self.assertEqual(self.run_dirs(), [])

    def test_unexpected_exceptions_from_either_builder_publish_nothing(self):
        self.seed()
        before = self.published_bytes()
        cases = [
            (build_funding, "build_funding_payload", RuntimeError("boom"), "funding builder raised unexpectedly"),
            (build_record, "load_fixture", KeyError("boom"), "record builder raised unexpectedly"),
        ]
        for i, (module, name, exc, fragment) in enumerate(cases):
            with self.subTest(builder=name), mock.patch.object(module, name, side_effect=exc):
                report, _ = self.run_build(run_id=f"raise-{i}")
            self.assertEqual(report.publication, "not_attempted")
            self.assertTrue(any(fragment in e for e in report.fatal_errors), report.fatal_errors)
            self.assertEqual(self.published_bytes(), before)
            self.assertEqual(self.run_dirs(), [])

    def test_source_loading_exception_is_reported_at_the_boundary_then_raised(self):
        self.seed()
        before = self.published_bytes()
        seen = []
        with mock.patch.object(
            build_funding, "load_rows_by_official_from_csv", side_effect=RuntimeError("csv exploded")
        ), self.assertRaises(RuntimeError):
            self.run_build(run_id="src-raise", on_report=seen.append)
        self.assertEqual(len(seen), 1)
        report = seen[0]
        self.assertEqual((report.publication, report.run_id), ("not_attempted", "src-raise"))
        self.assertIn("build raised before publication: RuntimeError: csv exploded", report.fatal_errors)
        self.assertEqual(self.published_bytes(), before)
        self.assertEqual(self.run_dirs(), [])

    def test_source_loading_exception_through_the_cli_writes_the_report_and_exits_1(self):
        self.seed()
        before = self.published_bytes()
        with mock.patch.object(build_funding, "load_rows_by_official_from_csv", side_effect=RuntimeError("csv exploded")):
            with mock.patch("sys.stderr"):
                code, _ = run_main(self, "--run-id", "cli-src")
        self.assertEqual(code, 1)
        written = json.loads(self.repo.path("data", "r.json").read_text())
        self.assertEqual((written["run_id"], written["publication"]), ("cli-src", "not_attempted"))
        self.assertTrue(any("csv exploded" in e for e in written["fatal_errors"]))
        self.assertEqual(self.published_bytes(), before)

    def test_invalid_and_duplicate_run_ids_are_refused_before_building(self):
        self.seed()
        before = self.published_bytes()
        report, _ = self.run_build(run_id="../escape")
        self.assertEqual(report.publication, "not_attempted")
        self.assertTrue(any("invalid run id" in e for e in report.fatal_errors))
        publish.run_dir(self.droot, "dup").mkdir(parents=True)
        report, _ = self.run_build(run_id="dup")
        self.assertTrue(any("already exists" in e for e in report.fatal_errors), report.fatal_errors)
        self.assertEqual(report.results, [])
        self.assertEqual(self.published_bytes(), before)

    def test_report_is_written_while_the_lock_is_still_held(self):
        observed = []

        def on_report(report):
            try:
                publish.RunLock(self.droot, "probe", "probe").acquire().release()
                observed.append("free")
            except publish.LockBusy:
                observed.append("held")

        self.run_build(run_id="locked-report", now=NOW_1, on_report=on_report)
        self.assertEqual(observed, ["held"])
        publish.RunLock(self.droot, "after", "probe").acquire().release()  # released afterwards


# --- review attestation --------------------------------------------------------


class TestReviewRevocation(PublishTestCase):
    def test_revocation_applies_on_success_and_is_restored_on_rollback(self):
        self.set_review("official-a", "2026-10-01")
        self.seed()
        self.assertEqual(self.freshness()["officials"]["official-a"]["record"]["reviewed_through"], "2026-10-01")
        reviewed = self.published_bytes()

        # revoke, but the freshness replacement fails -> rollback keeps the review
        self.set_review("official-a", None)
        with fail_on("_replace", lambda src, dst: is_live(dst, "freshness.json")):
            report, _ = self.run_build(run_id="revoke-fail")
        self.assert_rolled_back_to(reviewed, report)
        self.assertEqual(self.freshness()["officials"]["official-a"]["record"]["reviewed_through"], "2026-10-01")

        # the same revocation, published
        report, _ = self.run_build(run_id="revoke-ok")
        self.assertEqual(report.publication, "verified", report.publication_problems)
        entry = self.freshness()["officials"]["official-a"]["record"]
        self.assertIsNone(entry["reviewed_through"])
        self.assertIn("REVIEW_DATE_MISSING", entry["warning_codes"])


# --- failure injection -----------------------------------------------------------


class TestFailureInjection(PublishTestCase):
    def test_backup_preparation_failure_changes_nothing(self):
        self.seed()
        before = self.published_bytes()
        with fail_on("_copy_file", lambda src, dst: "backup" in Path(dst).parts):
            report, _ = self.run_build(run_id="backup-fail")
        self.assertEqual(report.publication, "not_attempted")
        self.assertTrue(any("backup preparation failed" in p for p in report.publication_problems))
        self.assertTrue(report.fatal_errors)
        self.assertEqual(self.published_bytes(), before)
        self.assertEqual(self.run_dirs(), [])

    def test_replacement_failure_rolls_back_every_position_including_freshness(self):
        self.seed()
        self.change_record_fixtures()
        before = self.published_bytes()
        targets = [publish.target_for(o, d) for o in self.ids for d in ("funding", "record")] + ["freshness.json"]
        for n, target in enumerate(targets):
            with self.subTest(fail_at=target):
                with fail_on("_replace", lambda src, dst, t=target: is_live(dst, t)):
                    report, _ = self.run_build(run_id=f"replace-fail-{n}")
                self.assert_rolled_back_to(before, report)
                self.assertTrue(any("replacement failed" in p for p in report.publication_problems))
                self.assertEqual(self.run_dirs(), [])
        report, _ = self.run_build(run_id="replace-ok")  # the same change, unhindered, does change the tree
        self.assertEqual(report.publication, "verified")
        self.assertNotEqual(self.published_bytes(), before)

    def test_replacement_failure_on_first_ever_build_removes_new_files(self):
        with fail_on("_replace", lambda src, dst: is_live(dst, "freshness.json")):
            report, _ = self.run_build(run_id="first-replace-fail", now=NOW_1)
        self.assert_rolled_back_to({}, report)
        self.assertEqual(self.run_dirs(), [])

    def test_post_publication_validation_failure_rolls_back(self):
        self.seed()
        self.change_record_fixtures()
        before = self.published_bytes()
        states = []

        def failing_verify(*args, **kwargs):
            states.append(self.journal("verify-fail")["state"])
            return ["injected live-tree problem"]

        with mock.patch.object(build_all, "verify_live_snapshot", failing_verify):
            report, _ = self.run_build(run_id="verify-fail")
        self.assertEqual(states, ["PUBLISHED"])
        self.assert_rolled_back_to(before, report)
        self.assertIn("post-publication verification: injected live-tree problem", report.publication_problems)

    def test_real_post_publication_check_catches_a_retained_file_changed_mid_publication(self):
        self.seed()
        retained = self.repo.path("data", "officials", "official-b", "funding.json")
        real = publish._replace

        def replace_then_tamper(src, dst):
            real(src, dst)
            if is_live(dst, "freshness.json"):
                retained.write_bytes(retained.read_bytes() + b" ")

        tampered = retained.read_bytes() + b" "
        with mock.patch.object(publish, "_replace", replace_then_tamper):
            report, _ = self.run_build(run_id="tamper", target_ids={"official-a"})
        self.assertTrue(
            any("officials/official-b/funding.json: live sha256" in p for p in report.publication_problems),
            report.publication_problems,
        )
        # The retained file is not back at its prior hash, so the rollback is
        # not complete: the run must not claim rolled_back or drop its journal.
        self.assertEqual(report.publication, "recovery_required", report.publication_problems)
        self.assertEqual(self.journal("tamper")["state"], "RECOVERY_REQUIRED")
        self.assertEqual(retained.read_bytes(), tampered)  # the unknown edit is not overwritten

    def test_rollback_failure_keeps_journal_and_backups_and_blocks_until_recover(self):
        self.seed()
        self.change_record_fixtures()
        before = self.published_bytes()
        restore_fail = fail_on("_copy_file", lambda src, dst: "backup" in Path(src).parts)
        with fail_on("_replace", lambda src, dst: is_live(dst, "freshness.json")), restore_fail:
            report, _ = self.run_build(run_id="rb-fail")
        self.assertEqual(report.publication, "recovery_required")
        self.assertEqual(report.journal_state, "RECOVERY_REQUIRED")
        self.assertEqual(self.journal("rb-fail")["state"], "RECOVERY_REQUIRED")
        self.assertTrue((publish.run_dir(self.droot, "rb-fail") / "backup").is_dir())
        self.assertNotEqual(self.published_bytes(), before)  # mixed tree, awaiting recovery

        blocked, _ = self.run_build(run_id="next")
        self.assertEqual(blocked.publication, "not_attempted")
        self.assertTrue(any("unresolved publication journal" in e for e in blocked.fatal_errors))
        self.assertEqual(blocked.results, [])

        # interrupted recovery: the first restore fails again; repeatable
        with fail_on("_copy_file", lambda src, dst: "backup" in Path(src).parts):
            self.assertEqual(self.recover_ids()[0][1], "recovery_required")
        self.assertEqual(self.journal("rb-fail")["state"], "RECOVERY_REQUIRED")
        self.assertEqual(self.recover_ids(), [("rb-fail", "rolled_back", [])])
        self.assertEqual(self.published_bytes(), before)
        self.assertEqual(self.run_dirs(), [])
        self.assertEqual(self.recover_ids(), [])

    def test_rollback_never_overwrites_unknown_content(self):
        self.seed()
        self.change_record_fixtures()
        target = self.repo.path("data", "officials", "official-a", "record.json")
        restore_fail = fail_on("_copy_file", lambda src, dst: "backup" in Path(src).parts)
        with fail_on("_replace", lambda src, dst: is_live(dst, "freshness.json")), restore_fail:
            self.run_build(run_id="unknown")
        target.write_text('{"edited": "by a human"}')
        outcome, problems = self.recover_ids()[0][1:]
        self.assertEqual(outcome, "recovery_required")
        self.assertTrue(any("matches neither the prior nor the new version" in p for p in problems), problems)
        self.assertEqual(target.read_text(), '{"edited": "by a human"}')
        self.assertTrue((publish.run_dir(self.droot, "unknown") / "journal.json").is_file())

    def test_cleanup_failure_after_verified_warns_blocks_and_is_recoverable(self):
        self.seed()
        with fail_on("_remove_tree", lambda path: True):
            report, _ = self.run_build(run_id="dirty")
        self.assertEqual(report.publication, "verified")
        self.assertEqual(report.publication_warnings, ["CLEANUP_INCOMPLETE"])
        self.assertEqual(report.journal_state, "VERIFIED")
        self.assertEqual(build_all.build_exit_code(report), 1)
        published = self.published_bytes()
        blocked, _ = self.run_build(run_id="next")
        self.assertTrue(any("state 'VERIFIED'" in e for e in blocked.fatal_errors), blocked.fatal_errors)
        self.assertEqual(self.recover_ids(), [("dirty", "cleaned", [])])
        self.assertEqual(self.published_bytes(), published)  # cleanup never rolls back a verified run
        report, _ = self.run_build(run_id="next-2")
        self.assertEqual(report.publication, "verified")


# --- journals ------------------------------------------------------------------


class TestUnsafeJournals(PublishTestCase):
    def interrupted(self, run_id="j"):
        self.seed()
        self.change_record_fixtures()
        restore_fail = fail_on("_copy_file", lambda src, dst: "backup" in Path(src).parts)
        with fail_on("_replace", lambda src, dst: is_live(dst, "freshness.json")), restore_fail:
            self.run_build(run_id=run_id)
        return publish.run_dir(self.droot, run_id)

    def assert_refused(self, rdir, fragment):
        snapshot = self.published_bytes()
        outcome, problems = publish.recover_run(rdir, self.droot, self.ids)
        self.assertEqual(outcome, "refused")
        self.assertTrue(any(fragment in p for p in problems), problems)
        self.assertEqual(self.published_bytes(), snapshot)

    def test_unsafe_journals_are_refused_without_touching_anything(self):
        mutations = [
            ("traversal target", lambda j: j["entries"][0].update(target="../../etc/passwd"), "unsafe or unknown target"),
            ("unknown official", lambda j: j["entries"][0].update(target="officials/nobody/record.json"), "unsafe or unknown target"),
            ("staged path", lambda j: j["entries"][0].update(staged="/etc/passwd"), "staged path must be"),
            ("backup path", lambda j: j["entries"][0].update(backup="backup/../../x"), "backup path must be"),
            ("bad hash", lambda j: j["entries"][0].update(new_sha256="zz"), "new_sha256"),
            ("run id", lambda j: j.update(run_id="other"), "does not match its directory"),
            ("state", lambda j: j.update(state="DONE"), "unknown state"),
            ("extra key", lambda j: j.update(extra=1), "keys must be exactly"),
            ("freshness order", lambda j: j["entries"].reverse(), "freshness.json must appear exactly once"),
            ("manifest", lambda j: j["manifest"].update({"freshness.json": "0" * 64}), "manifest hash"),
        ]
        rdir = self.interrupted()
        original = (rdir / "journal.json").read_text()
        for name, mutate, fragment in mutations:
            with self.subTest(case=name):
                journal = json.loads(original)
                mutate(journal)
                (rdir / "journal.json").write_text(json.dumps(journal))
                self.assert_refused(rdir, fragment)
        (rdir / "journal.json").write_text("{not json")
        self.assert_refused(rdir, "journal could not be read")

    def test_symlinked_entries_are_refused_and_block_builds(self):
        self.seed()
        self.pdir.mkdir(parents=True, exist_ok=True)
        outside = self.repo.path("outside")
        outside.mkdir()
        (self.pdir / "linked").symlink_to(outside, target_is_directory=True)
        report, _ = self.run_build(run_id="next")
        self.assertTrue(any("unexpected entry" in e for e in report.fatal_errors), report.fatal_errors)
        self.assertEqual(self.recover_ids()[0][:2], ("linked", "refused"))
        self.assertTrue((self.pdir / "linked").is_symlink() and outside.is_dir())

    def test_journal_less_run_dir_is_abandoned_staging_and_does_not_block(self):
        self.seed()
        (publish.run_dir(self.droot, "abandoned") / "staging").mkdir(parents=True)
        report, _ = self.run_build(run_id="next")
        self.assertEqual(report.publication, "verified", report.fatal_errors)
        self.assertEqual(self.recover_ids(), [("abandoned", "cleaned", [])])

    def test_prepared_journal_recovers_without_changing_published_files(self):
        self.seed()
        before = self.published_bytes()
        # die immediately after PUBLISHING is recorded: nothing replaced yet
        with mock.patch.object(publish, "_replace", side_effect=KeyboardInterrupt), self.assertRaises(KeyboardInterrupt):
            self.run_build(run_id="early")
        self.assertEqual(self.journal("early")["state"], "PUBLISHING")
        self.assertEqual(self.recover_ids(), [("early", "rolled_back", [])])
        self.assertEqual(self.published_bytes(), before)


# --- --verify-run ----------------------------------------------------------------


class TestVerifyRun(PublishTestCase):
    def cli(self, *argv):
        with mock.patch("sys.stderr"):
            return run_main(self, *argv)

    def test_verify_run_accepts_its_own_verified_run_and_never_rewrites_the_report(self):
        code, _ = self.cli("--run-id", "r1")
        self.assertEqual(code, 0)
        report_path = self.repo.path("data", "r.json")
        report_bytes = report_path.read_bytes()
        code, out = self.cli("--verify-run", "r1")
        self.assertEqual(code, 0, out)
        self.assertEqual(report_path.read_bytes(), report_bytes)

    def test_verify_run_after_a_subset_run(self):
        self.cli("--run-id", "r1")
        code, _ = self.cli("--run-id", "r2", "--official", "official-a")
        self.assertEqual(code, 0)
        code, out = self.cli("--verify-run", "r2")
        self.assertEqual(code, 0, out)

    def test_stale_or_wrong_run_reports_fail(self):
        self.cli("--run-id", "r1")
        code, out = self.cli("--verify-run", "r0")
        self.assertEqual(code, 1)
        self.assertIn("does not match 'r0' (stale or foreign report)", out)

        self.cli("--run-id", "dry", "--skip-freshness")  # overwrites r.json with a dry-run report
        code, out = self.cli("--verify-run", "dry")
        self.assertEqual(code, 1)
        self.assertIn("is not a publishing build", out)
        self.assertIn("not 'verified'", out)

        self.break_record_fixture("official-a")
        with fail_on("_replace", lambda src, dst: is_live(dst, "freshness.json")):
            self.cli("--run-id", "rolled")
        code, out = self.cli("--verify-run", "rolled")
        self.assertEqual(code, 1)
        self.assertIn("report publication is 'rolled_back'", out)

    def test_retained_or_replaced_file_mutation_is_detected(self):
        self.cli("--run-id", "r1")
        self.cli("--run-id", "r2", "--official", "official-a")
        for rel in ("officials/official-b/record.json", "officials/official-a/funding.json", "freshness.json"):
            with self.subTest(file=rel):
                path = self.droot / rel
                original = path.read_bytes()
                path.write_bytes(original + b"\n")
                code, out = self.cli("--verify-run", "r2")
                self.assertEqual(code, 1)
                self.assertIn(f"{rel}: live sha256", out)
                path.write_bytes(original)
        code, _ = self.cli("--verify-run", "r2")
        self.assertEqual(code, 0)

    def test_a_newer_publication_makes_the_older_report_stale(self):
        self.cli("--run-id", "r1")
        old_report = self.repo.path("data", "r.json").read_bytes()
        self.set_review("official-a", "2026-10-01")  # guarantees r2's freshness.json differs
        code, _ = self.cli("--run-id", "r2")
        self.assertEqual(code, 0)
        self.repo.path("data", "r.json").write_bytes(old_report)
        code, out = self.cli("--verify-run", "r1")
        self.assertEqual(code, 1)
        self.assertIn("freshness.json: live sha256", out)


# --- dry run ---------------------------------------------------------------------


class TestDryRun(PublishTestCase):
    def test_cli_dry_run_leaves_every_generated_file_byte_identical(self):
        code, _ = run_main(self, "--run-id", "seed")
        self.assertEqual(code, 0)
        before = self.generated_bytes()
        self.break_record_fixture("official-b")  # a real change the dry run must not publish
        code, out = run_main(self, "--run-id", "dry", "--skip-freshness")
        self.assertEqual(code, 1)  # exit reflects the checks
        self.assertEqual(self.generated_bytes(), before)
        report = json.loads(self.repo.path("data", "r.json").read_text())
        self.assertEqual((report["mode"], report["publication"]), ("dry_run", "dry_run"))
        self.assertEqual((report["replaced_files"], report["snapshot_manifest"]), ({}, {}))
        self.assertEqual(self.run_dirs(), [])
        self.assertIn("publication dry_run", out)

    def test_clean_dry_run_exits_0_and_first_ever_dry_run_publishes_nothing(self):
        code, _ = run_main(self, "--skip-freshness")
        self.assertEqual(code, 0)
        self.assertEqual(self.published_bytes(), {})
        self.assertFalse(self.fpath.exists())


# --- real processes: lock contention and owner death -----------------------------------


CHILD = textwrap.dedent(
    """
    import json, os, signal, sys, time
    from pathlib import Path
    sys.path.insert(0, {scripts!r})
    import build_all, build_funding, build_record
    from pipeline import publish, registry as reg
    root = Path({root!r})
    for module, attrs in (
        (build_funding, dict(ROOT=root, DEFAULT_CSV=root / "data/raw/contributions.csv",
                             DEFAULT_STATEMENTS_CSV=root / "data/raw/statements_filed.csv",
                             CONTRIBUTIONS_CACHE=root / "data/raw/.cache/m6g2-gc6c.json",
                             STATEMENTS_CACHE=root / "data/raw/.cache/br3a-db9a.json")),
        (build_record, dict(ROOT=root)),
        (build_all, dict(ROOT=root, FRESHNESS_PATH=root / "data/freshness.json",
                         DEFAULT_REPORT_PATH=root / "data/build_report.json")),
    ):
        for k, v in attrs.items():
            setattr(module, k, v)
    action = sys.argv[1]
    if action == "hold":
        lock = publish.RunLock(root / "data", "holder", "build").acquire()
        print("locked", flush=True)
        time.sleep(60)
    elif action == "kill-mid-publish":
        real, count = publish._replace, [0]
        def replace(src, dst):
            if count[0] == int(sys.argv[2]):
                os.kill(os.getpid(), signal.SIGKILL)
            real(src, dst)
            count[0] += 1
        publish._replace = replace
        build_all.build_snapshot(
            run_id="killed",
            officials=reg.load_officials(root / "data/officials.json"),
            sources_registry=reg.load_registry(root / "data/sources/registry.json"),
            csv_path=root / "data/raw/contributions.csv",
            statements_csv=root / "data/raw/statements_filed.csv",
        )
    """
)


class TestProcessLock(PublishTestCase):
    def child(self, *args):
        code = CHILD.format(scripts=str(SCRIPTS), root=str(self.repo.root))
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
        return subprocess.Popen(
            [sys.executable, "-c", code, *args], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env
        )

    def start_holder(self):
        proc = self.child("hold")
        self.addCleanup(lambda: (proc.kill(), proc.wait(), proc.stdout.close(), proc.stderr.close()))
        self.assertEqual(proc.stdout.readline().strip(), "locked")
        return proc

    def test_contention_changes_nothing_and_writes_no_report(self):
        self.seed()
        before = self.published_bytes()
        self.start_holder()
        reports = []
        with self.assertRaises(publish.LockBusy) as ctx:
            self.run_build(run_id="denied", on_report=reports.append)
        self.assertIn("'holder'", str(ctx.exception))
        self.assertEqual(reports, [])
        self.assertEqual(self.published_bytes(), before)
        self.assertEqual(self.run_dirs(), [])

        report_path = self.repo.path("data", "r.json")
        with mock.patch("sys.stderr"):
            for argv in (("--run-id", "denied"), ("--recover",), ("--verify-run", "seed")):
                with self.subTest(argv=argv):
                    code, _ = run_main(self, *argv)
                    self.assertEqual(code, publish.LOCK_BUSY_EXIT)
                    self.assertFalse(report_path.exists())
        self.assertEqual(self.published_bytes(), before)

    def test_contention_leaves_a_pre_existing_report_byte_identical(self):
        self.seed()
        before = self.published_bytes()
        report_path = self.repo.path("data", "r.json")
        markdown_path = self.repo.path("data", "r.md")
        sentinel = b'{"SENTINEL": "pre-existing report, must survive"}\n'
        report_path.write_bytes(sentinel)
        markdown_path.write_bytes(sentinel)
        self.start_holder()
        with mock.patch("sys.stderr"):
            for argv in (("--run-id", "denied"), ("--run-id", "denied-dry", "--skip-freshness")):
                with self.subTest(argv=argv):
                    code, _ = run_main(self, *argv, "--markdown-path", str(markdown_path))
                    self.assertEqual(code, publish.LOCK_BUSY_EXIT)
                    self.assertEqual(report_path.read_bytes(), sentinel)
                    self.assertEqual(markdown_path.read_bytes(), sentinel)
        self.assertEqual(self.published_bytes(), before)
        self.assertEqual(self.run_dirs(), [])

    def test_owner_death_releases_the_lock(self):
        self.seed()
        proc = self.start_holder()
        proc.send_signal(signal.SIGKILL)
        proc.wait(timeout=10)
        report, _ = self.run_build(run_id="after-death")
        self.assertEqual(report.publication, "verified", report.fatal_errors)

    def test_owner_killed_mid_publication_blocks_until_recover_restores_everything(self):
        self.seed()
        self.change_record_fixtures()
        before = self.published_bytes()
        proc = self.child("kill-mid-publish", "2")
        proc.communicate(timeout=60)
        self.assertEqual(proc.returncode, -signal.SIGKILL)
        self.assertEqual(self.journal("killed")["state"], "PUBLISHING")
        self.assertNotEqual(self.published_bytes(), before)  # two files already replaced
        blocked, _ = self.run_build(run_id="next")
        self.assertTrue(any("unresolved publication journal for run 'killed'" in e for e in blocked.fatal_errors))
        with mock.patch("sys.stderr"):
            code, out = run_main(self, "--recover")
        self.assertEqual(code, 0, out)
        self.assertIn("recover: killed: rolled_back", out)
        self.assertEqual(self.published_bytes(), before)
        self.assertEqual(self.run_dirs(), [])
        code, out = run_main(self, "--recover")
        self.assertEqual((code, out.strip()), (0, "recover: nothing to recover"))


if __name__ == "__main__":
    unittest.main()
