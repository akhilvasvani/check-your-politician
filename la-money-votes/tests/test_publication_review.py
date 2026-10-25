"""Step 4C, Checkpoint 2 review findings: regression tests.

1. Filesystem containment: a symlinked lock file or symlinked data/raw (or
   data/raw/.publish) is rejected before anything is mutated, at every entry
   point (build, recovery, verification, journal-less cleanup). External
   sentinel files/directories prove nothing outside the tree changes.
2. Complete rollback verification: after a rollback, the whole previous
   snapshot (replaced and retained files) must be back at its prior hashes,
   otherwise the run is recovery_required and the journal is kept.
3. Payload identity: funding official.id / record official_id must match the
   official whose path the file occupies.
4. Failed lock acquisition: a metadata write failure after flock() releases
   the descriptor, so the same process can acquire the lock again.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import build_all
import build_funding
import build_record
import validate_data
from pipeline import publish

from .test_freshness import run_main
from .test_publication_runs import PublishTestCase, fail_on, is_live


def tree_digest(root: Path) -> dict:
    """relative path -> sha256 (files) / 'dir' / 'link:<target>' for a tree."""
    out = {}
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        for name in sorted(dirnames + filenames):
            p = Path(dirpath) / name
            rel = str(p.relative_to(root))
            if p.is_symlink():
                out[rel] = f"link:{os.readlink(p)}"
            elif p.is_dir():
                out[rel] = "dir"
            else:
                out[rel] = hashlib.sha256(p.read_bytes()).hexdigest()
    return out


def attempt(fn, *a, **kw):
    try:
        fn(*a, **kw)
    except Exception as exc:  # noqa: BLE001 - the caller asserts the type after the side-effect checks
        return exc
    return None


class ContainmentTestCase(PublishTestCase):
    def setUp(self):
        super().setUp()
        self.outside = Path(tempfile.mkdtemp(prefix="cyp-outside-"))
        self.addCleanup(shutil.rmtree, self.outside, True)

    def cli(self, *argv):
        with mock.patch("sys.stderr"):
            return run_main(self, *argv)

    def external_run_tree(self):
        """An external directory shaped like data/raw with a journal-less run
        (staging + backup sentinels) and a sentinel lock file."""
        ext = self.outside / "raw"
        for sub in ("staging", "backup"):
            d = ext / ".publish" / "ext-run" / sub / "officials" / "official-a"
            d.mkdir(parents=True)
            (d / "record.json").write_text(f"SENTINEL {sub}\n")
        (ext / ".build.lock").write_text("SENTINEL lock\n")
        (ext / "keep.txt").write_text("SENTINEL keep\n")
        return ext

    def symlink_raw_to(self, target: Path):
        raw = self.repo.path("data", "raw")
        shutil.rmtree(raw)
        raw.symlink_to(target, target_is_directory=True)


class TestLockFileSymlink(ContainmentTestCase):
    def setUp(self):
        super().setUp()
        self.sentinel = self.outside / "victim.txt"
        self.sentinel.write_text("SENTINEL victim\n")
        lock = publish.lock_path(self.droot)
        lock.parent.mkdir(parents=True, exist_ok=True)
        lock.symlink_to(self.sentinel)
        self.before = tree_digest(self.outside)

    def assert_untouched(self):
        self.assertEqual(self.sentinel.read_text(), "SENTINEL victim\n")
        self.assertEqual(tree_digest(self.outside), self.before)
        self.assertTrue(publish.lock_path(self.droot).is_symlink())

    def test_runlock_refuses_a_symlinked_lock_file(self):
        err = attempt(lambda: publish.RunLock(self.droot, "r", "build").acquire())
        self.assert_untouched()
        self.assertEqual(type(err).__name__, "UnsafeLayout")

    def test_build_recover_and_verify_entry_points_refuse(self):
        err = attempt(self.run_build, run_id="via-link")
        self.assert_untouched()
        self.assertEqual(type(err).__name__, "UnsafeLayout")
        self.assert_untouched()
        for argv in (("--run-id", "cli-link"), ("--recover",), ("--verify-run", "cli-link")):
            with self.subTest(argv=argv):
                code, _ = self.cli(*argv)
                self.assert_untouched()
                self.assertEqual(code, 1)
        self.assertEqual(self.published_bytes(), {})


class TestSymlinkedRawAncestor(ContainmentTestCase):
    def setUp(self):
        super().setUp()
        self.ext = self.external_run_tree()
        self.symlink_raw_to(self.ext)
        self.before = tree_digest(self.outside)

    def assert_untouched(self):
        self.assertEqual(tree_digest(self.outside), self.before)

    def test_recover_all_does_not_follow_a_symlinked_raw_dir(self):
        results = publish.recover_all(self.droot, self.ids)
        self.assertTrue(results and all(outcome == "refused" for _, outcome, _ in results), results)
        self.assert_untouched()

    def test_unresolved_runs_reports_a_symlinked_raw_dir(self):
        self.assertTrue(publish.unresolved_runs(self.droot))
        self.assert_untouched()

    def test_build_recover_and_verify_entry_points_refuse(self):
        err = attempt(self.run_build, run_id="via-raw-link")
        self.assert_untouched()
        self.assertEqual(type(err).__name__, "UnsafeLayout")
        self.assert_untouched()
        for argv in (("--run-id", "cli-raw"), ("--recover",), ("--verify-run", "cli-raw")):
            with self.subTest(argv=argv):
                code, _ = self.cli(*argv)
                self.assert_untouched()
                self.assertEqual(code, 1)
        self.assertEqual(self.published_bytes(), {})


class TestSymlinkedPublishDir(ContainmentTestCase):
    def test_symlinked_publish_dir_is_refused_everywhere(self):
        ext = self.external_run_tree()
        pdir = publish.publish_dir(self.droot)
        pdir.parent.mkdir(parents=True, exist_ok=True)
        pdir.symlink_to(ext / ".publish", target_is_directory=True)
        before = tree_digest(self.outside)
        self.assertTrue(publish.unresolved_runs(self.droot))
        self.assertEqual([o for _, o, _ in publish.recover_all(self.droot, self.ids)], ["refused"])
        err = attempt(self.run_build, run_id="via-publish-link")
        self.assertEqual(tree_digest(self.outside), before)
        self.assertEqual(type(err).__name__, "UnsafeLayout")
        code, _ = self.cli("--recover")
        self.assertEqual(code, 1)
        self.assertEqual(tree_digest(self.outside), before)

    def test_symlinked_staging_and_backup_in_a_journal_less_run_are_unlinked_not_followed(self):
        ext = self.external_run_tree()
        rdir = publish.run_dir(self.droot, "local-run")
        rdir.mkdir(parents=True)
        (rdir / "staging").symlink_to(ext / ".publish" / "ext-run" / "staging", target_is_directory=True)
        (rdir / "backup").symlink_to(ext / ".publish" / "ext-run" / "backup", target_is_directory=True)
        before = tree_digest(self.outside)
        self.assertEqual(publish.recover_all(self.droot, self.ids), [("local-run", "cleaned", [])])
        self.assertFalse(rdir.exists())
        self.assertEqual(tree_digest(self.outside), before)


# --- 2. complete rollback verification ---------------------------------------


class TestCompleteRollbackVerification(PublishTestCase):
    def test_retained_file_changed_during_publication_is_recovery_required(self):
        self.seed()
        self.change_record_fixtures()
        retained = self.repo.path("data", "officials", "official-b", "funding.json")
        original = retained.read_bytes()
        real = publish._replace

        def replace_then_tamper(src, dst):
            real(src, dst)
            if is_live(dst, "freshness.json"):
                retained.write_bytes(original + b" ")

        with mock.patch.object(publish, "_replace", replace_then_tamper):
            report, _ = self.run_build(run_id="tamper", target_ids={"official-a"})
        self.assertEqual(report.publication, "recovery_required", report.publication_problems)
        self.assertTrue(
            any("officials/official-b/funding.json" in p and "prior" in p for p in report.publication_problems),
            report.publication_problems,
        )
        # evidence preserved; the unknown edit is not overwritten
        self.assertEqual(self.journal("tamper")["state"], "RECOVERY_REQUIRED")
        self.assertEqual(retained.read_bytes(), original + b" ")
        # replaced files were restored
        for ds in ("funding", "record"):
            self.assertNotIn(f"officials/official-a/{ds}.json", report.replaced_files)
        # recovery keeps refusing to call it complete until a human restores it
        self.assertEqual(publish.recover_all(self.droot, self.ids)[0][1], "recovery_required")
        self.assertTrue(publish.run_dir(self.droot, "tamper").is_dir())
        retained.write_bytes(original)
        self.assertEqual(publish.recover_all(self.droot, self.ids), [("tamper", "rolled_back", [])])
        self.assertEqual(self.run_dirs(), [])


    def test_journal_with_an_inconsistent_prior_manifest_is_refused(self):
        self.seed()
        self.change_record_fixtures()
        restore_fail = fail_on("_copy_file", lambda src, dst: "backup" in Path(src).parts)
        with fail_on("_replace", lambda src, dst: is_live(dst, "freshness.json")), restore_fail:
            self.run_build(run_id="pm")
        rdir = publish.run_dir(self.droot, "pm")
        original = json.loads((rdir / "journal.json").read_text())
        for name, mutate in (
            ("missing target", lambda j: j["prior_manifest"].pop("officials/official-b/record.json")),
            ("retained differs", lambda j: j["prior_manifest"].update({"officials/official-b/record.json": "0" * 64})),
            ("entry differs", lambda j: j["prior_manifest"].update({"freshness.json": "1" * 64})),
        ):
            with self.subTest(case=name):
                journal = json.loads(json.dumps(original))
                mutate(journal)
                (rdir / "journal.json").write_text(json.dumps(journal))
                before = self.published_bytes()
                outcome, problems = publish.recover_run(rdir, self.droot, self.ids)
                self.assertEqual(outcome, "refused", problems)
                self.assertTrue(any("prior_manifest" in p for p in problems), problems)
                self.assertEqual(self.published_bytes(), before)


# --- 3. payload identity ---------------------------------------------------------


def foreign_funding(a_payload: dict, b_payload: dict) -> dict:
    """official-a's donors (so the count matches) under official-b's identity."""
    out = json.loads(json.dumps(a_payload))
    out["official"] = b_payload["official"]
    out["source"] = b_payload["source"]
    return out


def foreign_record(a_payload: dict, b_payload: dict) -> dict:
    out = json.loads(json.dumps(b_payload))
    out["items"] = a_payload["items"]  # matching item count, still valid
    return out


class TestPayloadIdentity(PublishTestCase):
    def load(self, oid, ds):
        return json.loads(self.repo.path("data", "officials", oid, f"{ds}.json").read_text())

    def test_payload_problems_check_identity(self):
        self.seed()
        a_f, b_f = self.load("official-a", "funding"), self.load("official-b", "funding")
        a_r, b_r = self.load("official-a", "record"), self.load("official-b", "record")
        self.assertEqual(validate_data.funding_payload_problems("official-a", a_f), [])
        self.assertEqual(validate_data.record_payload_problems("official-a", a_r), [])
        self.assertTrue(
            any("official.id" in p for p in validate_data.funding_payload_problems("official-a", foreign_funding(a_f, b_f)))
        )
        self.assertTrue(
            any("official_id" in p for p in validate_data.record_payload_problems("official-a", foreign_record(a_r, b_r)))
        )

    def test_foreign_retained_files_block_publication(self):
        self.seed()
        a_f, b_f = self.load("official-a", "funding"), self.load("official-b", "funding")
        a_r, b_r = self.load("official-a", "record"), self.load("official-b", "record")
        cases = {
            "funding": (foreign_funding(a_f, b_f), dict(csv=False)),  # funding skipped -> retained
            "record": (foreign_record(a_r, b_r), {}),  # record fails -> retained
        }
        for ds, (payload, kw) in cases.items():
            with self.subTest(dataset=ds):
                path = self.repo.path("data", "officials", "official-a", f"{ds}.json")
                original = path.read_bytes()
                path.write_text(json.dumps(payload, indent=2) + "\n")
                fixture = self.repo.path("data", "sources", "records", "official-a.json")
                fixture_bytes = fixture.read_bytes()
                if ds == "record":
                    self.break_record_fixture("official-a")
                before = self.published_bytes()
                report, _ = self.run_build(run_id=f"foreign-retained-{ds}", **kw)
                self.assertEqual(report.publication, "not_attempted", report.publication_problems)
                self.assertTrue(any("does not match" in e and "official-a" in e for e in report.fatal_errors), report.fatal_errors)
                self.assertEqual(self.published_bytes(), before)
                path.write_bytes(original)
                fixture.write_bytes(fixture_bytes)

    def test_foreign_staged_files_block_publication(self):
        self.seed()
        b_f, b_r = self.load("official-b", "funding"), self.load("official-b", "record")
        before = self.published_bytes()
        real_f, real_r = build_funding.build_funding_for_official, build_record.build_record_for_official

        def staged_path(kw, oid, ds):
            return Path(kw["out_root"]) / oid / f"{ds}.json"

        def funding_wrapper(official, *a, **kw):
            result = real_f(official, *a, **kw)
            p = staged_path(kw, official["id"], "funding")
            if official["id"] == "official-a" and p.exists():
                p.write_text(json.dumps(foreign_funding(json.loads(p.read_text()), b_f), indent=2) + "\n")
            return result

        def record_wrapper(official_id, *a, **kw):
            result = real_r(official_id, *a, **kw)
            p = staged_path(kw, official_id, "record")
            if official_id == "official-a" and p.exists():
                p.write_text(json.dumps(foreign_record(json.loads(p.read_text()), b_r), indent=2) + "\n")
            return result

        for name, patcher, fragment in (
            ("funding", mock.patch.object(build_funding, "build_funding_for_official", funding_wrapper), "official.id"),
            ("record", mock.patch.object(build_record, "build_record_for_official", record_wrapper), "official_id"),
        ):
            with self.subTest(dataset=name), patcher:
                report, _ = self.run_build(run_id=f"foreign-staged-{name}")
            self.assertEqual(report.publication, "not_attempted", report.publication_problems)
            self.assertTrue(any(fragment in e for e in report.fatal_errors), report.fatal_errors)
            self.assertEqual(self.published_bytes(), before)


# --- 4. failed lock acquisition cleanup -------------------------------------------


class TestLockAcquisitionFailure(PublishTestCase):
    def check(self, name):
        lock = publish.RunLock(self.droot, "first", "build")
        with mock.patch.object(publish.os, name, side_effect=OSError(5, f"injected {name} failure")):
            with self.assertRaises(OSError):
                lock.acquire()
        self.assertIsNone(lock._fd)
        again = publish.RunLock(self.droot, "second", "build").acquire()  # same process, no LockBusy
        self.assertIn("second", publish.lock_path(self.droot).read_text())
        again.release()
        lock.release()  # harmless no-op

    def test_ftruncate_failure_releases_the_descriptor(self):
        self.check("ftruncate")

    def test_write_failure_releases_the_descriptor(self):
        self.check("write")

    def test_fsync_failure_releases_the_descriptor(self):
        self.check("fsync")


if __name__ == "__main__":
    unittest.main()
