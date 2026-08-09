"""Integration tests for build_funding.py / build_record.py / build_all.py.

These run the real builder code (not reimplementations of it) against the
fixture data in tests/fixtures/, writing into a throwaway temp directory
(see tests/helpers.TempRepo) so the actual repo's data/ is never touched and
no network call is made. Socrata-fetch code paths are intentionally not
exercised here (that would require either a live call or a hand-built fake
Socrata response); the CSV-driven and cache-only-with-a-fixture-cache paths
below cover the same downstream logic (normalize -> validate -> write).
"""

from __future__ import annotations

import json
import sys
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import build_all
import build_funding
import build_record
from pipeline import registry as reg

from .helpers import TempRepo, patch_module_root, restore_module_attrs


class BuilderTestCase(unittest.TestCase):
    """Common setUp/tearDown: build a TempRepo and monkeypatch the ROOT-ish
    module constants in build_funding / build_record / build_all to point at
    it, restoring the originals afterward so tests don't leak state into
    each other or into any later use of the real modules in this process.
    """

    def setUp(self):
        self.repo = TempRepo()
        self._saved_funding = patch_module_root(
            build_funding,
            self.repo.root,
            {
                "DEFAULT_CSV": self.repo.path("data", "raw", "contributions.csv"),
                "DEFAULT_STATEMENTS_CSV": self.repo.path("data", "raw", "statements_filed.csv"),
                "CONTRIBUTIONS_CACHE": self.repo.path("data", "raw", ".cache", "m6g2-gc6c.json"),
                "STATEMENTS_CACHE": self.repo.path("data", "raw", ".cache", "br3a-db9a.json"),
            },
        )
        self._saved_record = patch_module_root(build_record, self.repo.root)
        self._saved_all = patch_module_root(
            build_all,
            self.repo.root,
            {
                "DEFAULT_REPORT_PATH": self.repo.path("data", "build_report.json"),
                "FRESHNESS_PATH": self.repo.path("data", "freshness.json"),
            },
        )
        self.officials = reg.load_officials(self.repo.path("data", "officials.json"))
        self.sources_registry = reg.load_registry(self.repo.path("data", "sources", "registry.json"))

    def tearDown(self):
        restore_module_attrs(build_funding, self._saved_funding)
        restore_module_attrs(build_record, self._saved_record)
        restore_module_attrs(build_all, self._saved_all)
        self.repo.cleanup()


class TestBuildFunding(BuilderTestCase):
    def test_builds_funding_json_from_csv(self):
        rows_by_official = build_funding.load_rows_by_official_from_csv(
            self.repo.path("data", "raw", "contributions.csv"),
            {"official-a": ["Officer A Test Committee 2026"]},
        )
        statement_links = build_funding.load_statement_links_from_csv(
            self.repo.path("data", "raw", "statements_filed.csv")
        )
        official = next(o for o in self.officials if o["id"] == "official-a")
        today = date.today().isoformat()

        status, count, problems, notes = build_funding.build_funding_for_official(
            official, rows_by_official, self.sources_registry, statement_links, today, today
        )

        self.assertEqual(status, "ok")
        self.assertEqual(problems, [])
        self.assertEqual(count, 2)  # "Jane Donor" + "Acme PAC" -- "City of Los Angeles" row is a Misc. Increase, excluded

        out_path = self.repo.path("data", "officials", "official-a", "funding.json")
        self.assertTrue(out_path.exists())
        payload = json.loads(out_path.read_text())
        names = {d["name"] for d in payload["donors"]}
        self.assertEqual(names, {"Jane Donor", "Acme PAC"})

        jane = next(d for d in payload["donors"] if d["name"] == "Jane Donor")
        self.assertEqual(jane["total"], 750)  # 500 + 250, across two contributions
        self.assertEqual(jane["employer"], "Acme Corp")
        self.assertEqual(len(jane["contributions"]), 2)
        # every contribution carries a provenance block
        for c in jane["contributions"]:
            self.assertIn("provenance", c)
            self.assertEqual(c["provenance"]["retrieved_at"], today)
        # the statements-filed join resolved a per-contribution source_url
        self.assertTrue(any(c.get("source_url") for c in jane["contributions"]))

    def test_official_with_no_matching_rows_still_writes_valid_empty_result(self):
        official = next(o for o in self.officials if o["id"] == "official-b")
        today = date.today().isoformat()
        # official-b's committee name has zero rows in the fixture CSV
        status, count, problems, notes = build_funding.build_funding_for_official(
            official, {}, self.sources_registry, {}, today, today
        )
        self.assertEqual(status, "ok")
        self.assertEqual(count, 0)
        self.assertTrue(any("no rows matched" in n for n in notes))

    def test_unknown_official_id_fails_cleanly(self):
        fake_official = {"id": "does-not-exist", "name": "Nobody", "office": "Nowhere"}
        today = date.today().isoformat()
        status, count, problems, notes = build_funding.build_funding_for_official(
            fake_official, {}, self.sources_registry, {}, today, today
        )
        self.assertEqual(status, "failed")
        self.assertTrue(problems)

    def test_row_with_unparseable_amount_is_dropped_not_written_as_invalid(self):
        official = next(o for o in self.officials if o["id"] == "official-a")
        today = date.today().isoformat()
        bad_rows = {
            "official-a": [
                {
                    build_funding.COL_DATE: "01/01/2026",
                    build_funding.COL_CONTRIBUTOR: "Broken Row Donor",
                    build_funding.COL_COMMITTEE: "Officer A Test Committee 2026",
                    build_funding.COL_COMMITTEE_ID: "9999001",
                    build_funding.COL_AMOUNT: "not-a-number",
                    build_funding.COL_TYPE: "Monetary Contributions (Itemized)",
                }
            ]
        }
        # build_donors() silently drops rows whose amount fails to parse
        # (parse_amount returns None), rather than writing a donor with a
        # broken amount -- so this is a valid (if donor-less) build, not a
        # validation failure. This intentionally documents that behavior.
        status, count, problems, notes = build_funding.build_funding_for_official(
            official, bad_rows, self.sources_registry, {}, today, today
        )
        self.assertEqual(status, "ok")
        self.assertEqual(count, 0)
        self.assertEqual(problems, [])

    def test_untrusted_source_url_fails_validation_without_overwriting_prior_valid_file(self):
        official = next(o for o in self.officials if o["id"] == "official-a")
        today = date.today().isoformat()
        rows_by_official = build_funding.load_rows_by_official_from_csv(
            self.repo.path("data", "raw", "contributions.csv"),
            {"official-a": ["Officer A Test Committee 2026"]},
        )
        # Establish a valid baseline file first.
        build_funding.build_funding_for_official(official, rows_by_official, self.sources_registry, {}, today, today)
        out_path = self.repo.path("data", "officials", "official-a", "funding.json")
        baseline = out_path.read_text()
        self.assertTrue(baseline)  # sanity check the baseline write happened

        # Now supply a statement_links entry pointing at a domain outside
        # ALLOWED_SOURCE_DOMAINS -- this must fail validation and must NOT
        # be allowed to overwrite the valid baseline file above.
        untrusted_links = {("9999001", "2026-01-01", "2026-06-30"): "https://not-an-official-domain.example.com/doc"}
        status, count, problems, notes = build_funding.build_funding_for_official(
            official, rows_by_official, self.sources_registry, untrusted_links, today, today
        )
        self.assertEqual(status, "failed")
        self.assertTrue(any("untrusted source_url" in p for p in problems))
        self.assertEqual(out_path.read_text(), baseline)  # untouched


class TestBuildRecord(BuilderTestCase):
    def test_builds_record_json_from_fixture(self):
        today = date.today().isoformat()
        status, count, problems, notes = build_record.build_record_for_official(
            "official-a", self.sources_registry, today
        )
        self.assertEqual(status, "ok")
        self.assertEqual(problems, [])
        self.assertEqual(count, 2)

        out_path = self.repo.path("data", "officials", "official-a", "record.json")
        payload = json.loads(out_path.read_text())
        self.assertEqual(payload["official_id"], "official-a")
        for item in payload["items"]:
            self.assertIn("provenance", item)
            self.assertEqual(item["provenance"]["retrieved_at"], today)
        # council_file "25-0001" resolves to a CFMS source_url
        cf1 = next(i for i in payload["items"] if i["council_file"] == "25-0001")
        self.assertTrue(cf1["source_url"].startswith("https://cityclerk.lacity.org/"))

    def test_mayoral_style_record_id_has_no_per_item_url(self):
        today = date.today().isoformat()
        status, count, problems, notes = build_record.build_record_for_official(
            "official-b", self.sources_registry, today
        )
        self.assertEqual(status, "ok")
        out_path = self.repo.path("data", "officials", "official-b", "record.json")
        payload = json.loads(out_path.read_text())
        ed1 = next(i for i in payload["items"] if i["council_file"] == "ED-1")
        self.assertIsNone(ed1["source_url"])

    def test_invalid_date_in_fixture_fails_without_writing(self):
        fixture_path = self.repo.path("data", "sources", "records", "official-a.json")
        data = json.loads(fixture_path.read_text())
        data["items"][0]["date"] = "not-a-date"
        fixture_path.write_text(json.dumps(data))

        today = date.today().isoformat()
        status, count, problems, notes = build_record.build_record_for_official(
            "official-a", self.sources_registry, today
        )
        self.assertEqual(status, "failed")
        self.assertTrue(any("invalid date" in p for p in problems))
        out_path = self.repo.path("data", "officials", "official-a", "record.json")
        self.assertFalse(out_path.exists())

    def test_missing_fixture_file_fails_cleanly(self):
        self.repo.path("data", "sources", "records", "official-a.json").unlink()
        today = date.today().isoformat()
        status, count, problems, notes = build_record.build_record_for_official(
            "official-a", self.sources_registry, today
        )
        self.assertEqual(status, "failed")
        self.assertTrue(problems)


class TestBuildAll(BuilderTestCase):
    def test_runs_both_builders_for_every_official(self):
        build_report, freshness = build_all.run(
            officials=self.officials,
            sources_registry=self.sources_registry,
            csv_path=self.repo.path("data", "raw", "contributions.csv"),
            statements_csv=self.repo.path("data", "raw", "statements_filed.csv"),
        )
        self.assertTrue(build_report.ok)
        self.assertEqual(len(build_report.results), 4)  # 2 officials x 2 builders
        self.assertTrue(all(r.status == "ok" for r in build_report.results))
        self.assertIn("official-a", freshness["officials"])
        self.assertIn("official-b", freshness["officials"])

    def test_one_official_record_failure_does_not_block_the_other(self):
        fixture_path = self.repo.path("data", "sources", "records", "official-a.json")
        data = json.loads(fixture_path.read_text())
        data["items"][0]["date"] = "not-a-date"
        fixture_path.write_text(json.dumps(data))

        build_report, freshness = build_all.run(
            officials=self.officials,
            sources_registry=self.sources_registry,
            csv_path=self.repo.path("data", "raw", "contributions.csv"),
            statements_csv=self.repo.path("data", "raw", "statements_filed.csv"),
        )
        self.assertFalse(build_report.ok)

        a_record = next(r for r in build_report.results if r.official_id == "official-a" and r.builder == "record")
        b_record = next(r for r in build_report.results if r.official_id == "official-b" and r.builder == "record")
        self.assertEqual(a_record.status, "failed")
        self.assertEqual(b_record.status, "ok")  # not affected by official-a's failure

    def test_missing_csv_marks_funding_skipped_not_failed(self):
        self.repo.path("data", "raw", "contributions.csv").unlink()
        build_report, freshness = build_all.run(
            officials=self.officials,
            sources_registry=self.sources_registry,
            csv_path=self.repo.path("data", "raw", "contributions.csv"),
            statements_csv=self.repo.path("data", "raw", "statements_filed.csv"),
        )
        funding_results = [r for r in build_report.results if r.builder == "funding"]
        self.assertTrue(all(r.status == "skipped" for r in funding_results))
        self.assertTrue(build_report.ok)  # skipped alone doesn't fail the build
        self.assertTrue(build_report.unavailable_sources)

    def test_cross_reference_mismatch_is_fatal_and_returns_no_freshness(self):
        officials = self.officials + [{"id": "official-ghost", "name": "Ghost", "office": "Nowhere"}]
        build_report, freshness = build_all.run(
            officials=officials,
            sources_registry=self.sources_registry,
            csv_path=self.repo.path("data", "raw", "contributions.csv"),
            statements_csv=self.repo.path("data", "raw", "statements_filed.csv"),
        )
        self.assertFalse(build_report.ok)
        self.assertTrue(build_report.fatal_errors)
        self.assertEqual(freshness, {})

    def test_build_report_writes_valid_json(self):
        build_report, freshness = build_all.run(
            officials=self.officials,
            sources_registry=self.sources_registry,
            csv_path=self.repo.path("data", "raw", "contributions.csv"),
            statements_csv=self.repo.path("data", "raw", "statements_filed.csv"),
        )
        report_path = self.repo.path("data", "build_report.json")
        build_report.write(report_path)
        loaded = json.loads(report_path.read_text())
        self.assertEqual(loaded["ok"], True)
        self.assertEqual(len(loaded["results"]), 4)


if __name__ == "__main__":
    unittest.main()
