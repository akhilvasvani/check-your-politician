"""Tests for the freshness.json v2 contract: the generator and preflight in
build_all.py, the validators in validate_data.py, and the outcome log and
cache-provenance sidecar in pipeline/socrata.py.

Test kinds (see the Step 4B report):
- Real file I/O: every build runs the real orchestrator against a throwaway
  TempRepo (tests/helpers.py) and really writes funding.json, record.json,
  freshness.json, the Socrata cache and its sidecar under a temp directory.
- Mocks: Socrata is never contacted. socrata._request is replaced by an
  in-memory fake ("live"), or by one that raises SourceUnavailable
  ("network down"); socrata._utcnow is pinned. Nothing else is mocked,
  except reg.load_* and sys.argv in the main() tests and schemas.get in one
  configuration test.
- Fixtures: tests/fixtures/ (officials, registry, CSVs, record fixtures).

A module-level guard (setUpModule / tearDownModule) hashes the real committed
data and fixture files and fails the run if any test changed them.
"""

from __future__ import annotations

import copy
import hashlib
import io
import json
import sys
import unittest
from contextlib import redirect_stdout
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import build_all
import build_funding
import validate_data
from pipeline import atomic_io
from pipeline import registry as reg
from pipeline import socrata

from .helpers import REPO_ROOT
from .test_builders import BuilderTestCase

UTC = timezone.utc
NOW_1 = datetime(2026, 10, 18, 12, 0, 0, tzinfo=UTC)
NOW_2 = datetime(2026, 10, 18, 15, 30, 0, tzinfo=UTC)
NOW_LATER = datetime(2026, 11, 2, 15, 0, 0, tzinfo=UTC)
FETCH_1 = datetime(2026, 10, 18, 11, 59, 0, tzinfo=UTC)
FETCH_LATER = datetime(2026, 11, 2, 14, 0, 0, tzinfo=UTC)
FETCH_1_TS = "2026-10-18T11:59:00+00:00"
FETCH_LATER_TS = "2026-11-02T14:00:00+00:00"
CONTRIB_ID = build_funding.CONTRIBUTIONS_RESOURCE_ID
STMT_ID = build_funding.STATEMENTS_RESOURCE_ID

# --- guard: tests must never modify real committed data (requirement 20) ---

_PROTECTED_GLOBS = (
    "data/officials/*/funding.json",
    "data/officials/*/record.json",
    "data/sources/records/*.json",
    "data/sources/registry.json",
    "data/officials.json",
    "data/freshness.json",
    "tests/fixtures/**/*",
)
_BASELINE_HASHES = {}


def _hash_protected():
    out = {}
    for pattern in _PROTECTED_GLOBS:
        for path in sorted(REPO_ROOT.glob(pattern)):
            if path.is_file():
                out[str(path.relative_to(REPO_ROOT))] = hashlib.sha256(path.read_bytes()).hexdigest()
    return out


def setUpModule():
    _BASELINE_HASHES.update(_hash_protected())


def tearDownModule():
    after = _hash_protected()
    if after != _BASELINE_HASHES:
        changed = sorted(k for k in set(after) | set(_BASELINE_HASHES) if after.get(k) != _BASELINE_HASHES.get(k))
        raise AssertionError(f"tests modified committed data or fixture files: {changed}")


# --- fake Socrata data -------------------------------------------------------


def api_row(name, amount, period_end, con_type="Monetary Contributions (Itemized)"):
    return {
        "con_date": "2026-03-01T00:00:00.000",
        "con_name": name,
        "cmt_nm": "Officer A Test Committee 2026",
        "cmt_id": "9999001",
        "per_beg_date": "2026-01-01T00:00:00.000",
        "per_end_date": period_end,
        "con_amount": str(amount),
        "con_type": con_type,
        "election_date": "2026-11-03T00:00:00.000",
    }


API_CONTRIBUTIONS = [
    api_row("Jane Donor", 500, "2026-06-30T00:00:00.000"),
    api_row("Acme PAC", 1000, "2026-06-30T00:00:00.000"),
    api_row("Late Filer", 25, "2026-09-30T00:00:00.000"),
    api_row("City of Los Angeles", 5000, "2026-09-30T00:00:00.000", con_type="Misc. Increase(s) to Cash"),
]
API_STATEMENTS = [
    {
        "cmt_id": "9999001",
        "period_from_date": "2026-01-01T00:00:00.000",
        "period_to_date": "2026-06-30T00:00:00.000",
        "stmt_link": {"url": "https://ethics.lacity.org/view/?document_id=999999"},
    }
]


def fake_socrata(contributions="live", statements="live", contribution_rows=API_CONTRIBUTIONS,
                 statement_rows=API_STATEMENTS, calls=None):
    """A stand-in for socrata._request. Each dataset is "live" (return the
    rows) or "down" (raise SourceUnavailable, as a real network failure
    would after its retries)."""

    def request(url, timeout, retries):
        resource = CONTRIB_ID if CONTRIB_ID in url else STMT_ID if STMT_ID in url else None
        if resource is None:
            raise AssertionError(f"unexpected URL {url}")
        if calls is not None:
            calls.append(resource)
        mode, rows = (contributions, contribution_rows) if resource == CONTRIB_ID else (statements, statement_rows)
        if mode == "down":
            raise socrata.SourceUnavailable(f"simulated network failure for {resource}")
        return copy.deepcopy(rows)

    return request


def strip_time_varying(freshness):
    out = copy.deepcopy(freshness)
    out.pop("generated_at", None)
    for datasets in out.get("officials", {}).values():
        for entry in datasets.values():
            entry.pop("attempted_at", None)
    return out


V1_SNAPSHOT = {
    "generated_at": "2026-10-05T21:59:15+00:00",
    "officials": {
        "official-a": {
            "funding": {"status": "ok", "last_success_at": "2026-10-05", "donor_count": 2},
            "record": {"status": "ok", "last_success_at": "2026-10-05", "item_count": 2},
        },
        "official-b": {
            "funding": {"status": "failed", "last_success_at": None, "donor_count": 0},
            "record": {"status": "ok", "last_success_at": "2026-10-05", "item_count": 0},
        },
    },
}


class FreshnessTestCase(BuilderTestCase):
    def setUp(self):
        super().setUp()
        self.ids = reg.official_ids(self.officials)
        self.fpath = self.repo.path("data", "freshness.json")
        self.cache = self.repo.path("data", "raw", ".cache", f"{CONTRIB_ID}.json")
        self.stmt_cache = self.repo.path("data", "raw", ".cache", f"{STMT_ID}.json")
        socrata.reset_fetch_outcomes()

    def tearDown(self):
        socrata.reset_fetch_outcomes()
        super().tearDown()

    # -- building --

    def build(self, *, api=None, use_cache_only=False, fetch_time=FETCH_1, now=NOW_1, target_ids=None, save=True):
        """Run the real orchestrator through the same path as main():
        build_all.build_snapshot(). api=None -> CSV build from the fixture
        CSVs; otherwise an API build with socrata._request replaced by api.
        save=True publishes a valid snapshot (outputs and freshness.json, so
        the next build reads it as its previous snapshot); save=False is a
        dry run that stages and validates but publishes nothing."""
        kwargs = dict(target_ids=target_ids, officials=self.officials, sources_registry=self.sources_registry, now=now)
        if api is None:
            kwargs.update(
                csv_path=self.repo.path("data", "raw", "contributions.csv"),
                statements_csv=self.repo.path("data", "raw", "statements_filed.csv"),
            )
            report, freshness = build_all.build_snapshot(dry_run=not save, **kwargs)
        else:
            with mock.patch.object(socrata, "_request", api), mock.patch.object(socrata, "_utcnow", lambda: fetch_time):
                report, freshness = build_all.build_snapshot(
                    dry_run=not save, fetch_socrata=True, use_cache_only=use_cache_only, **kwargs
                )
        if save and freshness and not report.fatal_errors:
            self.assertValid(freshness)
            self.assertEqual(report.publication, "verified", report.publication_problems)
        return report, freshness

    def funding(self, freshness, official_id="official-a"):
        return freshness["officials"][official_id]["funding"]

    def record(self, freshness, official_id="official-a"):
        return freshness["officials"][official_id]["record"]

    # -- files --

    def write_json(self, path, data):
        Path(path).write_text(json.dumps(data, indent=2))

    def set_review(self, official_id, value, remove=False):
        path = self.repo.path("data", "sources", "records", f"{official_id}.json")
        data = json.loads(path.read_text())
        if remove:
            data.pop("reviewed_through", None)
        else:
            data["reviewed_through"] = value
        path.write_text(json.dumps(data))

    def write_cache(self, rows):
        """Overwrite the contributions cache with rows; any sidecar no longer
        matches, exactly as if the cache had been replaced by other means."""
        self.cache.write_text(json.dumps(rows))

    def generated_bytes(self):
        """Every file a build can write: per-official outputs, freshness.json
        and the Socrata caches/sidecars."""
        root = self.repo.root
        paths = list(root.glob("data/officials/*/*.json")) + list(root.glob("data/raw/.cache/*"))
        if self.fpath.exists():
            paths.append(self.fpath)
        return {str(p.relative_to(root)): p.read_bytes() for p in sorted(paths)}

    # -- assertions --

    def assertValid(self, freshness):
        problems = validate_data.validate_freshness(freshness, self.ids)
        self.assertEqual(problems, [], "\n".join(problems))

    def assertInvalid(self, freshness, fragment):
        problems = validate_data.validate_freshness(freshness, self.ids)
        self.assertTrue(any(fragment in p for p in problems), f"expected {fragment!r} in {problems}")

    def assertPreflightFailsWithoutMutation(self, fragment, **build_kwargs):
        before = self.generated_bytes()
        report, freshness = self.build(save=False, **build_kwargs)
        self.assertEqual(freshness, {})
        self.assertEqual(report.results, [], "no builder may run after a preflight failure")
        self.assertTrue(any(fragment in e for e in report.fatal_errors), f"expected {fragment!r} in {report.fatal_errors}")
        self.assertEqual(self.generated_bytes(), before, "a generated file changed after a preflight failure")
        return report


# --- validator ----------------------------------------------------------------


class TestValidator(FreshnessTestCase):
    def valid(self):
        _, freshness = self.build(save=False)
        return freshness

    def test_01_valid_v2_file_passes(self):
        freshness = self.valid()
        self.assertEqual(freshness["schema_version"], "2.0")
        self.assertValid(freshness)
        self.write_json(self.fpath, freshness)
        self.assertEqual(validate_data.validate_freshness_file(self.fpath, self.ids), [])

    def test_01b_committed_file_satisfies_the_contract(self):
        # Validated by contract only, so it keeps passing after real v2
        # builds replace the migrated values. Exact migration behavior is
        # pinned against the fixed V1_SNAPSHOT fixture in TestMigration.
        committed = REPO_ROOT / "data" / "freshness.json"
        officials = reg.load_officials(REPO_ROOT / "data" / "officials.json")
        self.assertEqual(validate_data.validate_freshness_file(committed, reg.official_ids(officials)), [])
        data = json.loads(committed.read_text())
        self.assertEqual(data["schema_version"], validate_data.FRESHNESS_SCHEMA_VERSION)
        self.assertEqual(set(data["officials"]), set(reg.official_ids(officials)))

    def test_02_malformed_existing_file_fails(self):
        dup = '{"schema_version": "2.0", "generated_at": "2026-10-18T12:00:00+00:00", "officials": {"official-a": {}, "official-a": {}}}'
        for text in ("{not json", "", "[]", "null", dup):
            with self.subTest(text=text):
                self.fpath.write_text(text)
                self.assertTrue(validate_data.validate_freshness_file(self.fpath, self.ids))
                data, problems, _ = build_all.load_previous_freshness(self.fpath, self.ids)
                self.assertIsNone(data)
                self.assertTrue(problems)

    def test_02b_missing_file_is_not_a_problem(self):
        self.assertFalse(self.fpath.exists())
        self.assertEqual(validate_data.validate_freshness_file(self.fpath, self.ids), [])
        self.assertEqual(build_all.load_previous_freshness(self.fpath, self.ids), (None, [], "missing"))

    def test_02c_committed_v1_file_is_reported_not_accepted(self):
        self.write_json(self.fpath, V1_SNAPSHOT)
        problems = validate_data.validate_freshness_file(self.fpath, self.ids)
        self.assertEqual(len(problems), 1)
        self.assertIn("legacy schema v1 file; run build_all.py once", problems[0])

    def test_03_unknown_official_fails(self):
        freshness = self.valid()
        freshness["officials"]["official-ghost"] = copy.deepcopy(freshness["officials"]["official-a"])
        self.assertInvalid(freshness, "unknown official id")

    def test_04_missing_official_fails(self):
        freshness = self.valid()
        del freshness["officials"]["official-b"]
        self.assertInvalid(freshness, "missing official id")

    def test_04b_missing_dataset_fails(self):
        freshness = self.valid()
        del freshness["officials"]["official-b"]["record"]
        self.assertInvalid(freshness, "missing required field 'record'")

    def test_05_unknown_status_fails(self):
        freshness = self.valid()
        self.funding(freshness)["status"] = "partial"
        self.assertInvalid(freshness, "not in allowed values")

    def test_06_unknown_warning_code_fails(self):
        freshness = self.valid()
        self.funding(freshness)["warning_codes"] = ["COUNT_DROP"]
        self.assertInvalid(freshness, "unknown code")

    def test_06b_warning_code_on_wrong_dataset_fails(self):
        for code in ("NO_ROWS_MATCHED", "SOURCE_CACHE_FALLBACK", "SOURCE_RETRIEVED_AT_UNKNOWN"):
            with self.subTest(code=code):
                freshness = self.valid()
                record = self.record(freshness)
                record["warning_codes"] = sorted(record["warning_codes"] + [code])
                self.assertInvalid(freshness, "not allowed for this dataset")

    def test_07_invalid_impossible_or_future_dates_fail(self):
        cases = [
            (("funding", "last_success_at"), "2026/10/18", "not a valid YYYY-MM-DD"),
            (("funding", "last_success_at"), "2026-02-30", "not a valid YYYY-MM-DD"),
            (("record", "last_success_at"), "2026-10-19", "after generated_at"),
            (("funding", "attempted_at"), "2026-10-18T12:00:01+00:00", "after generated_at"),
            (("funding", "attempted_at"), "2026-10-18T12:00:00", "not a valid UTC timestamp"),
            (("funding", "attempted_at"), "2026-10-18T12:00:00+05:00", "not a valid UTC timestamp"),
            (("funding", "attempted_at"), "2026-13-01T00:00:00+00:00", "not a valid UTC timestamp"),
            (("funding", "latest_reporting_period_end"), "2026-12-31", "after generated_at"),
            (("record", "reviewed_through"), "2026-10-19", "after generated_at"),
        ]
        for (dataset, field), value, fragment in cases:
            with self.subTest(field=field, value=value):
                freshness = self.valid()
                entry = freshness["officials"]["official-a"][dataset]
                entry[field] = value
                # keep paired warning codes consistent so only the date rule fires
                drop = {"latest_reporting_period_end": "LATEST_REPORTING_PERIOD_UNKNOWN", "reviewed_through": "REVIEW_DATE_MISSING"}
                entry["warning_codes"] = [c for c in entry["warning_codes"] if c != drop.get(field)]
                self.assertInvalid(freshness, fragment)
        freshness = self.valid()
        freshness["generated_at"] = "not-a-time"
        self.assertInvalid(freshness, "generated_at")

    def test_07b_future_source_retrieved_at_fails(self):
        _, freshness = self.build(api=fake_socrata(), save=False)
        self.funding(freshness)["source_retrieved_at"] = "2027-01-01T00:00:00+00:00"
        self.assertInvalid(freshness, "after generated_at")

    def test_07c_ok_status_must_match_attempt_date(self):
        freshness = self.valid()
        self.funding(freshness)["last_success_at"] = "2026-10-16"
        self.assertInvalid(freshness, "must be attempted_at's UTC date")
        freshness = self.valid()
        self.funding(freshness)["last_success_at"] = "2026-10-17"  # v1 local-date window
        self.assertValid(freshness)

    def test_08_prohibited_field_combinations_fail(self):
        cases = [
            ("funding", "reviewed_through", "2026-10-01"),
            ("record", "source_retrieved_at", "2026-10-18T11:00:00+00:00"),
            ("record", "latest_reporting_period_end", "2026-06-30"),
            ("funding", "coverage_through", "2026-06-30"),
            ("funding", "item_count", 2),
            ("record", "stale", True),
        ]
        for dataset, field, value in cases:
            with self.subTest(dataset=dataset, field=field):
                freshness = self.valid()
                freshness["officials"]["official-a"][dataset][field] = value
                self.assertInvalid(freshness, "unexpected field")
        for source_type in ("automated_csv", "unknown"):
            with self.subTest(source_type=source_type):
                freshness = self.valid()
                funding = self.funding(freshness)
                funding["source_type"] = source_type
                funding["source_retrieved_at"] = "2026-10-18T11:00:00+00:00"
                funding["warning_codes"].remove("SOURCE_RETRIEVED_AT_UNKNOWN")
                self.assertInvalid(freshness, f"must be null for {source_type}")

    def test_08b_paired_unknown_codes_are_enforced(self):
        freshness = self.valid()
        self.funding(freshness)["warning_codes"].remove("SOURCE_RETRIEVED_AT_UNKNOWN")
        self.assertInvalid(freshness, "SOURCE_RETRIEVED_AT_UNKNOWN must be present exactly when")
        freshness = self.valid()
        self.funding(freshness)["warning_codes"] = sorted(self.funding(freshness)["warning_codes"] + ["LATEST_REPORTING_PERIOD_UNKNOWN"])
        self.assertInvalid(freshness, "LATEST_REPORTING_PERIOD_UNKNOWN must be present exactly when")

    def test_17_donor_count_must_equal_displayed_donor_count(self):
        freshness = self.valid()
        funding = self.funding(freshness)
        self.assertEqual(funding["donor_count"], funding["displayed_donor_count"])
        funding["donor_count"] = funding["displayed_donor_count"] + 1
        self.assertInvalid(freshness, "must equal displayed_donor_count")

    def test_counts_must_be_nonnegative_integers(self):
        for field, value in (("displayed_donor_count", -1), ("matched_row_count", 1.5), ("matched_row_count", True)):
            with self.subTest(field=field, value=value):
                freshness = self.valid()
                funding = self.funding(freshness)
                funding[field] = value
                if field == "displayed_donor_count":
                    funding["donor_count"] = value
                self.assertInvalid(freshness, field)
        freshness = self.valid()
        self.record(freshness)["item_count"] = -3
        self.assertInvalid(freshness, "item_count")


# --- A: reporting period is bound to the rows actually used --------------------


class TestReportingPeriod(FreshnessTestCase):
    def test_A1_live_rows_produce_their_own_maximum(self):
        _, freshness = self.build(api=fake_socrata())
        self.assertEqual(self.funding(freshness)["latest_reporting_period_end"], "2026-09-30")

    def test_A1b_csv_rows_produce_their_own_maximum(self):
        _, freshness = self.build()
        self.assertEqual(self.funding(freshness)["latest_reporting_period_end"], "2026-06-30")

    def test_A2_cached_rows_produce_the_cached_rows_maximum(self):
        self.write_cache([api_row("Cached Donor", 300, "2026-05-31T00:00:00.000")])
        self.stmt_cache.write_text(json.dumps(API_STATEMENTS))
        _, freshness = self.build(api=fake_socrata("down", "down"), use_cache_only=True)
        funding = self.funding(freshness)
        self.assertEqual(funding["latest_reporting_period_end"], "2026-05-31")
        self.assertEqual(funding["matched_row_count"], 1)

    def test_A3_cached_period_replaces_a_different_previous_value(self):
        _, first = self.build(api=fake_socrata())
        self.assertEqual(self.funding(first)["latest_reporting_period_end"], "2026-09-30")
        self.write_cache([api_row("Older Cache", 300, "2026-04-30T00:00:00.000")])
        _, second = self.build(api=fake_socrata("down", "live"), now=NOW_LATER, fetch_time=FETCH_LATER)
        funding = self.funding(second)
        self.assertEqual(funding["status"], "ok")
        self.assertEqual(funding["latest_reporting_period_end"], "2026-04-30")
        self.assertIn("SOURCE_CACHE_FALLBACK", funding["warning_codes"])

    def test_A4_failed_build_carries_the_previous_value(self):
        _, first = self.build(api=fake_socrata())
        bad = copy.deepcopy(API_STATEMENTS)
        bad[0]["stmt_link"] = {"url": "https://evil.example.com/x"}  # fails official-a's validation
        _, second = self.build(api=fake_socrata(statement_rows=bad), now=NOW_LATER, fetch_time=FETCH_LATER)
        self.assertEqual(self.funding(second)["status"], "failed")
        self.assertEqual(self.funding(second)["latest_reporting_period_end"], self.funding(first)["latest_reporting_period_end"])

    def test_A4b_skipped_build_carries_the_previous_value(self):
        _, first = self.build(api=fake_socrata())
        self.cache.unlink()
        _, second = self.build(api=fake_socrata("down", "down"), now=NOW_LATER)
        self.assertEqual(self.funding(second)["status"], "skipped")
        self.assertEqual(self.funding(second)["latest_reporting_period_end"], "2026-09-30")

    def test_A5_invalid_period_ends_never_become_coverage_claims(self):
        invalid = [None, "garbage", "2026-02-30T00:00:00.000", "2027-06-30T00:00:00.000", ""]
        rows = [api_row(f"Donor {i}", 100 + i, value) for i, value in enumerate(invalid)]
        _, first = self.build(api=fake_socrata())  # previous value 2026-09-30
        _, second = self.build(api=fake_socrata(contribution_rows=rows), now=NOW_LATER, fetch_time=FETCH_LATER)
        funding = self.funding(second)
        self.assertEqual(funding["status"], "ok")
        self.assertIsNone(funding["latest_reporting_period_end"])  # not carried from the previous snapshot
        self.assertIn("LATEST_REPORTING_PERIOD_UNKNOWN", funding["warning_codes"])
        mixed = rows + [api_row("Valid", 1, "2026-03-31T00:00:00.000")]
        _, third = self.build(api=fake_socrata(contribution_rows=mixed), now=NOW_LATER, fetch_time=FETCH_LATER)
        self.assertEqual(self.funding(third)["latest_reporting_period_end"], "2026-03-31")

    def test_16_and_18_period_end_and_matched_rows_are_measured_before_the_cap(self):
        rows = [api_row(f"Donor {i:02d}", 1000 + i, "2026-06-30T00:00:00.000") for i in range(30)]
        rows.append(api_row("Smallest Donor", 1, "2026-09-30T00:00:00.000"))  # outside the top-30 cap
        rows.append(api_row("City of Los Angeles", 5, "2026-08-31T00:00:00.000", con_type="Misc. Increase(s) to Cash"))
        _, freshness = self.build(api=fake_socrata(contribution_rows=rows))
        funding = self.funding(freshness)
        self.assertEqual(funding["displayed_donor_count"], 30)
        self.assertEqual(funding["matched_row_count"], 32)
        self.assertEqual(funding["latest_reporting_period_end"], "2026-09-30")
        published = json.loads(self.repo.path("data", "officials", "official-a", "funding.json").read_text())
        ends = {c["provenance"]["reporting_period"]["to"] for d in published["donors"] for c in d["contributions"]}
        self.assertNotIn("2026-09-30", ends)  # proves it was not read from the capped output

    def test_18b_matched_row_count_includes_all_contribution_types(self):
        _, freshness = self.build()
        self.assertEqual(self.funding(freshness)["matched_row_count"], 4)  # 3 donor rows + 1 Misc. Increase row
        self.assertEqual(self.funding(freshness)["displayed_donor_count"], 2)


# --- B: source provenance and the Socrata outcome log --------------------------


class TestSourceProvenance(FreshnessTestCase):
    def seed_cache(self):
        """A live build that writes both caches and their verified sidecars."""
        _, freshness = self.build(api=fake_socrata(), save=False)
        self.assertTrue(socrata.cache_meta_path(self.cache).exists())
        return freshness

    def test_B1_contributions_live_statements_live(self):
        _, freshness = self.build(api=fake_socrata())
        funding = self.funding(freshness)
        self.assertEqual(funding["source_type"], "automated_api")
        self.assertEqual(funding["source_retrieved_at"], FETCH_1_TS)
        for code in ("SOURCE_CACHE_FALLBACK", "SUPPORTING_SOURCE_CACHE_FALLBACK", "SOURCE_RETRIEVED_AT_UNKNOWN"):
            self.assertNotIn(code, funding["warning_codes"])
        self.assertIn("EMPLOYER_OCCUPATION_UNAVAILABLE", funding["warning_codes"])
        self.assertEqual(socrata.get_fetch_outcome(CONTRIB_ID).origin, socrata.ORIGIN_LIVE)
        self.assertEqual(socrata.get_fetch_outcome(STMT_ID).origin, socrata.ORIGIN_LIVE)

    def test_B2_contributions_cache_with_verified_sidecar_statements_live(self):
        self.seed_cache()
        _, freshness = self.build(api=fake_socrata("down", "live"), now=NOW_LATER, fetch_time=FETCH_LATER)
        funding = self.funding(freshness)
        self.assertEqual(funding["status"], "ok")
        self.assertEqual(funding["last_success_at"], "2026-11-02")
        self.assertEqual(funding["source_retrieved_at"], FETCH_1_TS)  # when the cached rows were retrieved
        self.assertIn("SOURCE_CACHE_FALLBACK", funding["warning_codes"])
        self.assertNotIn("SUPPORTING_SOURCE_CACHE_FALLBACK", funding["warning_codes"])
        self.assertEqual(socrata.get_fetch_outcome(CONTRIB_ID).origin, socrata.ORIGIN_CACHE_FALLBACK)
        self.assertEqual(socrata.get_fetch_outcome(STMT_ID).origin, socrata.ORIGIN_LIVE)

    def test_B2b_contributions_cache_without_provenance_is_unknown_not_carried(self):
        _, first = self.build(api=fake_socrata())  # previous snapshot has FETCH_1_TS
        socrata.cache_meta_path(self.cache).unlink()  # e.g. a cache written before sidecars existed
        _, second = self.build(api=fake_socrata("down", "live"), now=NOW_LATER, fetch_time=FETCH_LATER)
        funding = self.funding(second)
        self.assertIsNone(funding["source_retrieved_at"])
        self.assertIn("SOURCE_RETRIEVED_AT_UNKNOWN", funding["warning_codes"])
        self.assertIn("SOURCE_CACHE_FALLBACK", funding["warning_codes"])

    def test_B2c_tampered_cache_is_unknown(self):
        self.seed_cache()
        self.write_cache(API_CONTRIBUTIONS[:1])  # contents no longer match the sidecar hash
        _, freshness = self.build(api=fake_socrata("down", "live"), now=NOW_LATER, fetch_time=FETCH_LATER)
        self.assertIsNone(self.funding(freshness)["source_retrieved_at"])

    def test_B2e_same_row_count_tamper_is_unknown(self):
        # Row count still matches the sidecar; only the content hash can detect the edit.
        self.seed_cache()
        edited = [dict(row) for row in API_CONTRIBUTIONS]
        edited[0] = api_row("Jane Donor", 999, "2026-06-30T00:00:00.000")
        self.write_cache(edited)
        _, freshness = self.build(api=fake_socrata("down", "live"), now=NOW_LATER, fetch_time=FETCH_LATER)
        self.assertIsNone(self.funding(freshness)["source_retrieved_at"])
        self.assertIn("SOURCE_RETRIEVED_AT_UNKNOWN", self.funding(freshness)["warning_codes"])

    def test_B2d_sidecar_time_after_generated_at_is_not_trusted(self):
        self.seed_cache()  # sidecar says FETCH_1 (11:59)
        early = datetime(2026, 10, 18, 11, 0, 0, tzinfo=UTC)
        _, freshness = self.build(api=fake_socrata("down", "down"), use_cache_only=True, now=early)
        self.assertIsNone(self.funding(freshness)["source_retrieved_at"])
        self.assertIn("SOURCE_RETRIEVED_AT_UNKNOWN", self.funding(freshness)["warning_codes"])

    def test_B3_contributions_live_statements_cache(self):
        self.seed_cache()
        _, freshness = self.build(api=fake_socrata("live", "down"), now=NOW_LATER, fetch_time=FETCH_LATER)
        funding = self.funding(freshness)
        self.assertEqual(funding["source_retrieved_at"], FETCH_LATER_TS)
        self.assertIn("SUPPORTING_SOURCE_CACHE_FALLBACK", funding["warning_codes"])
        self.assertNotIn("SOURCE_CACHE_FALLBACK", funding["warning_codes"])
        self.assertEqual(socrata.get_fetch_outcome(CONTRIB_ID).retrieved_at, FETCH_LATER_TS)

    def test_B4_both_cache(self):
        self.seed_cache()
        _, freshness = self.build(api=fake_socrata("down", "down"), now=NOW_LATER, fetch_time=FETCH_LATER)
        funding = self.funding(freshness)
        self.assertEqual(funding["status"], "ok")
        self.assertEqual(funding["source_retrieved_at"], FETCH_1_TS)
        self.assertIn("SOURCE_CACHE_FALLBACK", funding["warning_codes"])
        self.assertIn("SUPPORTING_SOURCE_CACHE_FALLBACK", funding["warning_codes"])

    def test_B4b_cache_only_mode(self):
        self.seed_cache()
        calls = []
        _, freshness = self.build(api=fake_socrata(calls=calls), use_cache_only=True, now=NOW_LATER)
        self.assertEqual(calls, [])  # the network is never tried
        self.assertEqual(socrata.get_fetch_outcome(CONTRIB_ID).origin, socrata.ORIGIN_CACHE_ONLY)
        self.assertEqual(self.funding(freshness)["source_retrieved_at"], FETCH_1_TS)
        self.assertIn("SOURCE_CACHE_FALLBACK", self.funding(freshness)["warning_codes"])

    def test_B5_contributions_unavailable_statements_live(self):
        calls = []
        report, freshness = self.build(api=fake_socrata("down", "live", calls=calls))
        self.assertTrue(report.unavailable_sources)
        funding = self.funding(freshness)
        self.assertEqual(funding["status"], "skipped")
        self.assertIn("SOURCE_UNAVAILABLE", funding["warning_codes"])
        self.assertIsNone(funding["source_retrieved_at"])
        self.assertEqual(socrata.get_fetch_outcome(CONTRIB_ID).origin, socrata.ORIGIN_UNAVAILABLE)
        self.assertIsNone(socrata.get_fetch_outcome(STMT_ID))  # never requested after the failure
        self.assertNotIn(STMT_ID, calls)

    def test_B6_sequential_runs_never_leak_outcomes(self):
        self.build(api=fake_socrata())
        self.assertEqual(socrata.get_fetch_outcome(CONTRIB_ID).origin, socrata.ORIGIN_LIVE)
        self.build(api=fake_socrata(), use_cache_only=True, now=NOW_2)
        self.assertEqual(socrata.get_fetch_outcome(CONTRIB_ID).origin, socrata.ORIGIN_CACHE_ONLY)
        self.build(now=NOW_2)  # a CSV run resets the log too
        self.assertIsNone(socrata.get_fetch_outcome(CONTRIB_ID))
        self.assertIsNone(socrata.get_fetch_outcome(STMT_ID))

    def test_B7_failed_request_followed_by_successful_run(self):
        _, first = self.build(api=fake_socrata("down", "down"))
        self.assertEqual(self.funding(first)["status"], "skipped")
        _, second = self.build(api=fake_socrata(), now=NOW_LATER, fetch_time=FETCH_LATER)
        funding = self.funding(second)
        self.assertEqual(funding["status"], "ok")
        self.assertEqual(funding["source_retrieved_at"], FETCH_LATER_TS)
        self.assertNotIn("SOURCE_UNAVAILABLE", funding["warning_codes"])

    def test_csv_build_is_never_a_live_retrieval(self):
        _, freshness = self.build()
        funding = self.funding(freshness)
        self.assertEqual(funding["source_type"], "automated_csv")
        self.assertIsNone(funding["source_retrieved_at"])
        self.assertIn("SOURCE_RETRIEVED_AT_UNKNOWN", funding["warning_codes"])
        b = self.funding(freshness, "official-b")
        self.assertEqual(b["warning_codes"], [
            "LATEST_REPORTING_PERIOD_UNKNOWN", "NO_ROWS_MATCHED", "SOURCE_RETRIEVED_AT_UNKNOWN", "ZERO_ITEMS",
        ])

    def test_09_failure_carries_forward_prior_values(self):
        _, first = self.build(api=fake_socrata())
        bad = copy.deepcopy(API_STATEMENTS)
        bad[0]["stmt_link"] = {"url": "https://evil.example.com/x"}
        fixture = self.repo.path("data", "sources", "records", "official-a.json")
        data = json.loads(fixture.read_text())
        data["items"][0]["date"] = "not-a-date"
        fixture.write_text(json.dumps(data))
        _, second = self.build(api=fake_socrata(statement_rows=bad), now=NOW_LATER, fetch_time=FETCH_LATER)
        f1, f2 = self.funding(first), self.funding(second)
        self.assertEqual(f2["status"], "failed")
        self.assertEqual(f2["attempted_at"], "2026-11-02T15:00:00+00:00")
        for key in ("last_success_at", "source_retrieved_at", "latest_reporting_period_end",
                    "displayed_donor_count", "matched_row_count", "donor_count", "source_type"):
            self.assertEqual(f2[key], f1[key], key)
        self.assertIn("BUILD_FAILED_PREVIOUS_DATA_SERVED", f2["warning_codes"])
        r1, r2 = self.record(first), self.record(second)
        self.assertEqual(r2["status"], "failed")
        self.assertEqual((r2["last_success_at"], r2["item_count"]), (r1["last_success_at"], r1["item_count"]))
        self.assertIn("BUILD_FAILED_PREVIOUS_DATA_SERVED", r2["warning_codes"])

    def test_10_skip_carries_forward_prior_values(self):
        _, first = self.build(api=fake_socrata())
        for path in (self.cache, self.stmt_cache):
            path.unlink()
        _, second = self.build(api=fake_socrata("down", "down"), now=NOW_LATER)
        for official_id in ("official-a", "official-b"):
            f1, f2 = self.funding(first, official_id), self.funding(second, official_id)
            self.assertEqual(f2["status"], "skipped")
            self.assertIn("SOURCE_UNAVAILABLE", f2["warning_codes"])
            for key in ("last_success_at", "source_retrieved_at", "latest_reporting_period_end",
                        "displayed_donor_count", "matched_row_count"):
                self.assertEqual(f2[key], f1[key], f"{official_id}.{key}")

    def test_11_cache_fallback_never_stamps_a_new_live_time(self):
        _, first = self.build(api=fake_socrata())
        _, second = self.build(api=fake_socrata("down", "down"), now=NOW_LATER, fetch_time=FETCH_LATER)
        self.assertEqual(self.funding(second)["source_retrieved_at"], FETCH_1_TS)
        self.assertNotEqual(self.funding(second)["source_retrieved_at"], FETCH_LATER_TS)

    def test_12_live_retrieval_updates_source_retrieved_at(self):
        self.build(api=fake_socrata())
        _, second = self.build(api=fake_socrata(), now=NOW_LATER, fetch_time=FETCH_LATER)
        self.assertEqual(self.funding(second)["source_retrieved_at"], FETCH_LATER_TS)


class TestSocrataOutcomeLog(unittest.TestCase):
    """fetch_dataset() keeps its signature and return value; the outcome log
    and sidecar are additive. _request is replaced in every case."""

    def setUp(self):
        import tempfile

        socrata.reset_fetch_outcomes()
        self.tmp = Path(tempfile.mkdtemp(prefix="cyp-socrata-"))
        self.cache = self.tmp / "x.json"

    def tearDown(self):
        import shutil

        socrata.reset_fetch_outcomes()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def fetch(self, request, resource="res-1", where=None, **kwargs):
        with mock.patch.object(socrata, "_request", request), mock.patch.object(socrata, "_utcnow", lambda: FETCH_1):
            return socrata.fetch_dataset(resource, where=where, cache_path=kwargs.pop("cache", self.cache), **kwargs)

    def down(self, url, timeout, retries):
        raise socrata.SourceUnavailable("down")

    def test_live_writes_cache_and_verified_sidecar(self):
        self.assertEqual(self.fetch(lambda u, t, r: [{"a": 1}]), [{"a": 1}])
        self.assertEqual(socrata.get_fetch_outcome("res-1"), socrata.FetchOutcome("res-1", "live", FETCH_1_TS, True))
        self.assertEqual(self.cache.read_text(), json.dumps([{"a": 1}]))  # cache format unchanged
        meta = json.loads(socrata.cache_meta_path(self.cache).read_text())
        self.assertEqual(meta["retrieved_at"], FETCH_1_TS)
        self.assertEqual(meta["sha256"], hashlib.sha256(self.cache.read_bytes()).hexdigest())

    def test_cache_origins_report_sidecar_time_only_when_verified(self):
        self.fetch(lambda u, t, r: [{"a": 1}])
        self.assertEqual(self.fetch(self.down), [{"a": 1}])
        self.assertEqual(socrata.get_fetch_outcome("res-1"), socrata.FetchOutcome("res-1", "cache_fallback", FETCH_1_TS, True))
        self.fetch(self.down, use_cache_only=True)
        self.assertEqual(socrata.get_fetch_outcome("res-1").origin, "cache_only")
        # each untrusted variant -> no time
        variants = {
            "different filter": dict(where="x = 1"),
            "different resource": dict(resource="res-other"),
        }
        for label, kwargs in variants.items():
            with self.subTest(label):
                resource = kwargs.get("resource", "res-1")
                self.fetch(self.down, **kwargs)
                self.assertEqual(socrata.get_fetch_outcome(resource), socrata.FetchOutcome(resource, "cache_fallback", None, False))
        meta_path = socrata.cache_meta_path(self.cache)
        for label, mutate in {
            "bad sidecar json": lambda: meta_path.write_text("{"),
            "row count mismatch": lambda: meta_path.write_text(json.dumps({**json.loads(meta_path.read_text()), "row_count": 9})),
            "missing sidecar": lambda: meta_path.unlink(),
            "same-count content edit": lambda: self.cache.write_text(json.dumps([{"a": 2}])),
        }.items():
            with self.subTest(label):
                self.fetch(lambda u, t, r: [{"a": 1}])  # reset to a verified pair
                mutate()
                self.fetch(self.down)
                self.assertIsNone(socrata.get_fetch_outcome("res-1").retrieved_at)

    def test_unavailable_and_reset(self):
        with self.assertRaises(socrata.SourceUnavailable):
            self.fetch(self.down, cache=self.tmp / "missing.json")
        self.assertEqual(socrata.get_fetch_outcome("res-1").origin, "unavailable")
        with self.assertRaises(socrata.SourceUnavailable):
            self.fetch(self.down, cache=self.tmp / "missing.json", use_cache_only=True)
        socrata.reset_fetch_outcomes()
        self.assertIsNone(socrata.get_fetch_outcome("res-1"))

    def test_two_resources_are_kept_separately(self):
        self.fetch(lambda u, t, r: [{"a": 1}], resource="contrib", cache=self.tmp / "c.json")
        with self.assertRaises(socrata.SourceUnavailable):
            self.fetch(self.down, resource="stmt", cache=self.tmp / "missing.json")
        self.assertEqual(socrata.get_fetch_outcome("contrib").origin, "live")
        self.assertEqual(socrata.get_fetch_outcome("stmt").origin, "unavailable")


# --- C: v1 migration ----------------------------------------------------------


class TestMigration(FreshnessTestCase):
    def test_C_migration_preserves_only_what_v1_recorded(self):
        v2 = build_all.migrate_v1_to_v2(V1_SNAPSHOT)
        self.assertValid(v2)
        a, b = v2["officials"]["official-a"], v2["officials"]["official-b"]
        self.assertEqual(a["funding"], {
            "source_type": "unknown", "status": "ok", "attempted_at": "2026-10-05T21:59:15+00:00",
            "last_success_at": "2026-10-05", "source_retrieved_at": None, "latest_reporting_period_end": None,
            "displayed_donor_count": 2, "matched_row_count": None, "donor_count": 2,
            "warning_codes": ["LATEST_REPORTING_PERIOD_UNKNOWN", "SOURCE_RETRIEVED_AT_UNKNOWN", "SOURCE_TYPE_UNKNOWN"],
        })
        self.assertEqual(a["record"]["reviewed_through"], None)
        self.assertEqual(a["record"]["warning_codes"], ["REVIEW_DATE_MISSING"])
        self.assertEqual(b["funding"]["status"], "failed")
        self.assertIsNone(b["funding"]["last_success_at"])
        self.assertNotIn("BUILD_FAILED_PREVIOUS_DATA_SERVED", b["funding"]["warning_codes"])
        self.assertIn("ZERO_ITEMS", b["record"]["warning_codes"])

    def test_C_valid_v1_on_disk_is_migrated_by_the_build_and_written_as_v2(self):
        # Step 4C: a retained file must exist for every carried-forward entry
        # and its count must match, so first publish real outputs, then put
        # a local v1 snapshot on disk that describes exactly those files.
        # (The shared V1_SNAPSHOT fixture is left unchanged.)
        code, _ = run_main(self)
        self.assertEqual(code, 0)
        counts = {
            oid: len(json.loads(self.repo.path("data", "officials", oid, "funding.json").read_text())["donors"])
            for oid in ("official-a", "official-b")
        }
        v1 = copy.deepcopy(V1_SNAPSHOT)
        v1["officials"]["official-a"]["funding"]["donor_count"] = counts["official-a"]
        v1["officials"]["official-b"]["funding"] = {
            "status": "ok", "last_success_at": "2026-10-05", "donor_count": counts["official-b"]
        }
        self.write_json(self.fpath, v1)
        self.repo.path("data", "raw", "contributions.csv").unlink()  # funding skipped -> carried from v1
        code, _ = run_main(self)
        self.assertEqual(code, 0)
        written = json.loads(self.fpath.read_text())
        self.assertValid(written)
        funding = self.funding(written)
        self.assertEqual((funding["status"], funding["source_type"], funding["last_success_at"]), ("skipped", "unknown", "2026-10-05"))
        self.assertEqual(funding["displayed_donor_count"], 2)

    def test_C_v1_west_of_utc_local_date_is_accepted(self):
        v1 = copy.deepcopy(V1_SNAPSHOT)
        v1["generated_at"] = "2026-10-06T03:00:00+00:00"  # 2026-10-05 evening in Los Angeles
        self.write_json(self.fpath, v1)
        data, problems, kind = build_all.load_previous_freshness(self.fpath, self.ids)
        self.assertEqual((problems, kind), ([], "v1-migrated"))
        self.assertEqual(data["officials"]["official-a"]["funding"]["last_success_at"], "2026-10-05")

    def test_C_malformed_or_partial_v1_fails_before_mutation(self):
        self.build()  # create generated files to protect
        def v1_with(mutate):
            v1 = copy.deepcopy(V1_SNAPSHOT)
            mutate(v1)
            return v1
        cases = {
            "missing record": v1_with(lambda v: v["officials"]["official-a"].pop("record")),
            "extra top-level key": v1_with(lambda v: v.update(note="x")),
            "v2 field mixed in": v1_with(lambda v: v["officials"]["official-a"]["funding"].update(warning_codes=[])),
            "unknown status": v1_with(lambda v: v["officials"]["official-a"]["funding"].update(status="partial")),
            "ok without date": v1_with(lambda v: v["officials"]["official-a"]["funding"].update(last_success_at=None)),
            "failed with date": v1_with(lambda v: v["officials"]["official-b"]["funding"].update(last_success_at="2026-10-05")),
            "negative count": v1_with(lambda v: v["officials"]["official-a"]["record"].update(item_count=-1)),
            "bad generated_at": v1_with(lambda v: v.update(generated_at="yesterday")),
            "future date": v1_with(lambda v: v["officials"]["official-a"]["funding"].update(last_success_at="2026-10-06")),
            "impossible date": v1_with(lambda v: v["officials"]["official-a"]["funding"].update(last_success_at="2026-02-30")),
        }
        for label, v1 in cases.items():
            with self.subTest(label):
                self.write_json(self.fpath, v1)
                self.assertPreflightFailsWithoutMutation("previous freshness.json is invalid", now=NOW_LATER)
                with self.assertRaises(ValueError):
                    build_all.migrate_v1_to_v2(v1)

    def test_C_unknown_schema_version_fails_before_mutation(self):
        _, valid = self.build()
        for version in ("1.0", "3.0", 2, None):
            with self.subTest(version=version):
                self.write_json(self.fpath, {**valid, "schema_version": version})
                self.assertPreflightFailsWithoutMutation("unsupported schema_version", now=NOW_LATER)


# --- D: human review dates ----------------------------------------------------


class TestReviewedThrough(FreshnessTestCase):
    def test_D1_absent_field_with_previous_value_is_carried(self):
        self.set_review("official-a", "2026-09-30")
        self.build()
        self.set_review("official-a", None, remove=True)
        _, freshness = self.build(now=NOW_LATER)
        self.assertEqual(self.record(freshness)["reviewed_through"], "2026-09-30")

    def test_D2_absent_field_without_previous_value_is_null(self):
        _, freshness = self.build()
        for official_id in ("official-a", "official-b"):
            self.assertIsNone(self.record(freshness, official_id)["reviewed_through"])
            self.assertIn("REVIEW_DATE_MISSING", self.record(freshness, official_id)["warning_codes"])

    def test_D3_valid_date_passes_through_and_replaces(self):
        self.set_review("official-a", "2026-09-30")
        _, first = self.build()
        self.assertEqual(self.record(first)["reviewed_through"], "2026-09-30")
        self.assertNotIn("REVIEW_DATE_MISSING", self.record(first)["warning_codes"])
        self.set_review("official-a", "2026-10-31")
        _, second = self.build(now=NOW_LATER)
        self.assertEqual(self.record(second)["reviewed_through"], "2026-10-31")

    def test_D4_explicit_null_revokes_a_previous_date(self):
        self.set_review("official-a", "2026-09-30")
        self.build()
        self.set_review("official-a", None)
        _, freshness = self.build(now=NOW_LATER)
        self.assertIsNone(self.record(freshness)["reviewed_through"])
        self.assertIn("REVIEW_DATE_MISSING", self.record(freshness)["warning_codes"])

    def test_D4b_revocation_applies_even_when_the_record_build_fails(self):
        self.set_review("official-a", "2026-09-30")
        self.build()
        fixture = self.repo.path("data", "sources", "records", "official-a.json")
        data = json.loads(fixture.read_text())
        data["reviewed_through"] = None
        data["items"][0]["date"] = "not-a-date"
        fixture.write_text(json.dumps(data))
        _, freshness = self.build(now=NOW_LATER)
        self.assertEqual(self.record(freshness)["status"], "failed")
        self.assertIsNone(self.record(freshness)["reviewed_through"])

    def test_D5_malformed_impossible_future_or_non_string_dates_fail_before_mutation(self):
        self.build()
        for value, fragment in (
            ("2026/09/30", "not a valid YYYY-MM-DD"),
            ("2026-02-30", "not a valid YYYY-MM-DD"),
            ("2026-10-19", "after the build's UTC date 2026-10-18"),
            (20260930, "not a valid YYYY-MM-DD"),
            ("", "not a valid YYYY-MM-DD"),
        ):
            with self.subTest(value=value):
                self.set_review("official-b", value)
                self.assertPreflightFailsWithoutMutation(fragment)

    def test_D6_date_equal_to_current_utc_date_is_accepted(self):
        self.set_review("official-a", "2026-10-18")
        report, freshness = self.build()
        self.assertFalse(report.fatal_errors)
        self.assertEqual(self.record(freshness)["reviewed_through"], "2026-10-18")
        # 23:30 on 2026-10-18 in Los Angeles is 2026-10-19 UTC: that UTC date is accepted
        self.set_review("official-a", "2026-10-19")
        report, freshness = self.build(now=datetime(2026, 10, 19, 6, 30, 0, tzinfo=UTC))
        self.assertEqual(self.record(freshness)["reviewed_through"], "2026-10-19")


# --- E / F: preflight and partial builds ---------------------------------------


class TestPreflight(FreshnessTestCase):
    def setUp(self):
        super().setUp()
        self.build()  # a published snapshot to protect
        # Change an input so any builder that ran would change funding.json.
        with self.repo.path("data", "raw", "contributions.csv").open("a") as f:
            f.write("05/01/2026,New Donor,None,None,Officer A Test Committee 2026,9999001,01/01/2026,06/30/2026,999.00,Monetary Contributions (Itemized),11/03/2026\n")

    def test_E0_control_a_normal_build_does_change_generated_files(self):
        before = self.generated_bytes()
        self.build(now=NOW_LATER)
        self.assertNotEqual(self.generated_bytes(), before)

    def test_E1_malformed_previous_snapshot(self):
        self.fpath.write_text("{not json")
        self.assertPreflightFailsWithoutMutation("not valid JSON")

    def test_E2_contract_violating_previous_snapshot(self):
        data = json.loads(self.fpath.read_text())
        self.funding(data)["donor_count"] = 999
        self.write_json(self.fpath, data)
        self.assertPreflightFailsWithoutMutation("must equal displayed_donor_count")

    def test_E3_unknown_official_argument(self):
        self.assertPreflightFailsWithoutMutation("unknown official id(s) ['official-ghost']", target_ids={"official-ghost"})

    def test_E4_subset_without_previous_snapshot(self):
        self.fpath.unlink()
        self.assertPreflightFailsWithoutMutation("run a full build first to initialize freshness", target_ids={"official-a"})

    def test_E5_subset_with_incomplete_previous_snapshot(self):
        data = json.loads(self.fpath.read_text())
        del data["officials"]["official-b"]
        self.write_json(self.fpath, data)
        self.assertPreflightFailsWithoutMutation("(missing: ['official-b'])", target_ids={"official-a"})

    def test_E6_invalid_review_date(self):
        self.set_review("official-a", "2026-13-01")
        self.assertPreflightFailsWithoutMutation("reviewed_through '2026-13-01'")

    def test_E7_schema_and_generator_version_mismatch(self):
        fake = {"properties": {"schema_version": {"enum": ["3.0"]}}}
        with mock.patch.object(validate_data.schemas, "get", lambda name: fake):
            self.assertPreflightFailsWithoutMutation("does not match generator")

    def test_E8_api_build_preflight_failure_makes_no_request(self):
        calls = []
        self.fpath.write_text("{not json")
        self.assertPreflightFailsWithoutMutation("not valid JSON", api=fake_socrata(calls=calls))
        self.assertEqual(calls, [])

    def test_F1_subset_updates_only_the_target_and_preserves_others(self):
        before = json.loads(self.fpath.read_text())
        _, after = self.build(now=NOW_LATER, target_ids={"official-a"})
        self.assertEqual(list(after["officials"]), ["official-a", "official-b"])
        self.assertEqual(after["officials"]["official-b"], before["officials"]["official-b"])
        self.assertEqual(
            json.dumps(after["officials"]["official-b"], indent=2), json.dumps(before["officials"]["official-b"], indent=2)
        )
        self.assertEqual(self.funding(after, "official-b")["attempted_at"], "2026-10-18T12:00:00+00:00")
        self.assertEqual(self.funding(after)["attempted_at"], "2026-11-02T15:00:00+00:00")
        self.assertEqual(self.funding(after)["displayed_donor_count"], 3)  # New Donor picked up
        b_funding = self.repo.path("data", "officials", "official-b", "funding.json")
        self.assertTrue(b_funding.exists())

    def test_19_identical_inputs_give_semantically_identical_output(self):
        _, first = self.build(now=NOW_1, save=False)
        _, second = self.build(now=NOW_2, save=False)
        self.assertNotEqual(first["generated_at"], second["generated_at"])
        self.assertEqual(strip_time_varying(first), strip_time_varying(second))
        _, again = self.build(now=NOW_1, save=False)
        self.assertEqual(json.dumps(first, sort_keys=True), json.dumps(again, sort_keys=True))


# --- main() --------------------------------------------------------------------


def run_main(case, *argv):
    out = io.StringIO()
    with mock.patch.object(reg, "load_officials", lambda path=None: copy.deepcopy(case.officials)), mock.patch.object(
        reg, "load_registry", lambda path=None: copy.deepcopy(case.sources_registry)
    ), mock.patch.object(sys, "argv", ["build_all.py", "--report-path", str(case.repo.path("data", "r.json")), *argv]):
        with redirect_stdout(out):
            try:
                build_all.main()
                code = 0
            except SystemExit as exc:
                code = exc.code
    return code, out.getvalue()


class TestMain(FreshnessTestCase):
    def test_main_writes_valid_v2_and_carries_forward_on_next_run(self):
        code, _ = run_main(self)
        self.assertEqual(code, 0)
        first = json.loads(self.fpath.read_text())
        self.assertValid(first)
        self.repo.path("data", "raw", "contributions.csv").unlink()
        run_main(self)
        second = json.loads(self.fpath.read_text())
        self.assertValid(second)
        self.assertEqual(self.funding(second)["last_success_at"], self.funding(first)["last_success_at"])

    def test_main_preflight_failure_exits_1_and_changes_nothing(self):
        run_main(self)
        self.fpath.write_text("{not json")
        before = self.generated_bytes()
        code, output = run_main(self)
        self.assertEqual(code, 1)
        self.assertIn("fatal: preflight: previous freshness.json is invalid", output)
        self.assertEqual(self.generated_bytes(), before)

    def test_main_skip_freshness_still_validates_but_never_writes(self):
        code, _ = run_main(self, "--skip-freshness")
        self.assertEqual(code, 0)
        self.assertFalse(self.fpath.exists())


# --- final verification: historical last_success_at --------------------------


def _at(y, m, d, hh=12, mm=0):
    return datetime(y, m, d, hh, mm, 0, tzinfo=UTC)


class TestLastSuccessAt(FreshnessTestCase):
    """last_success_at <= attempted_at's UTC date always holds; on failed or
    skipped any earlier date is legitimate (the published file is older than
    the attempt); a newly successful v2 build stamps its own UTC date."""

    def test_same_day_success(self):
        _, freshness = self.build(api=fake_socrata())  # build() asserts validity
        self.assertEqual(self.funding(freshness)["last_success_at"], "2026-10-18")
        self.assertEqual(self.record(freshness)["last_success_at"], "2026-10-18")

    def test_one_day_old_success_after_failed_attempt(self):
        self.build(api=fake_socrata())
        bad = copy.deepcopy(API_STATEMENTS)
        bad[0]["stmt_link"] = {"url": "https://evil.example.com/x"}  # official-a funding fails
        _, second = self.build(api=fake_socrata(statement_rows=bad), now=_at(2026, 10, 19), fetch_time=_at(2026, 10, 19, 11))
        funding = self.funding(second)
        self.assertEqual((funding["status"], funding["last_success_at"]), ("failed", "2026-10-18"))
        self.assertEqual(funding["attempted_at"], "2026-10-19T12:00:00+00:00")

    def test_months_old_success_after_failed_then_skipped_then_new_success(self):
        self.build(api=fake_socrata())  # success 2026-10-18
        bad = copy.deepcopy(API_STATEMENTS)
        bad[0]["stmt_link"] = {"url": "https://evil.example.com/x"}
        _, failed = self.build(api=fake_socrata(statement_rows=bad), now=_at(2027, 2, 15), fetch_time=_at(2027, 2, 15, 11))
        self.assertEqual((self.funding(failed)["status"], self.funding(failed)["last_success_at"]), ("failed", "2026-10-18"))
        for path in (self.cache, self.stmt_cache):
            path.unlink()
        _, skipped = self.build(api=fake_socrata("down", "down"), now=_at(2027, 3, 1))
        self.assertEqual((self.funding(skipped)["status"], self.funding(skipped)["last_success_at"]), ("skipped", "2026-10-18"))
        self.assertValid(skipped)
        _, ok = self.build(api=fake_socrata(), now=_at(2027, 3, 2), fetch_time=_at(2027, 3, 2, 11))
        self.assertEqual((self.funding(ok)["status"], self.funding(ok)["last_success_at"]), ("ok", "2027-03-02"))

    def test_validator_accepts_months_old_date_on_failed_and_skipped(self):
        _, freshness = self.build(save=False)
        for status in ("failed", "skipped"):
            with self.subTest(status):
                f = copy.deepcopy(freshness)
                entry = self.funding(f)
                entry["status"] = status
                entry["last_success_at"] = "2026-05-01"
                if status == "failed":
                    entry["warning_codes"] = sorted(entry["warning_codes"] + ["BUILD_FAILED_PREVIOUS_DATA_SERVED"])
                self.assertValid(f)

    def test_last_success_after_attempted_at_fails_for_every_status(self):
        _, freshness = self.build(save=False)  # generated_at 2026-10-18
        for dataset in ("funding", "record"):
            for status in ("ok", "failed", "skipped"):
                with self.subTest(dataset=dataset, status=status):
                    f = copy.deepcopy(freshness)
                    entry = f["officials"]["official-a"][dataset]
                    entry["status"] = status
                    entry["attempted_at"] = "2026-10-16T12:00:00+00:00"
                    entry["last_success_at"] = "2026-10-18"
                    self.assertInvalid(f, "is after attempted_at")

    def test_ok_entry_must_carry_this_attempts_date(self):
        # "ok" means this attempt succeeded, so a months-old date with status
        # ok is contradictory (only v1's local-date stamp, one day back, is
        # tolerated). Historical dates belong to failed/skipped entries.
        _, freshness = self.build(save=False)
        f = copy.deepcopy(freshness)
        self.funding(f)["last_success_at"] = "2026-10-17"
        self.assertValid(f)
        self.funding(f)["last_success_at"] = "2026-05-01"
        self.assertInvalid(f, "status 'ok' means this attempt succeeded")


# --- final verification: source_type transitions -----------------------------


class TestSourceTypeTransitions(FreshnessTestCase):
    def start_from_v1(self):
        self.write_json(self.fpath, V1_SNAPSHOT)

    def test_migrated_entry_starts_unknown_with_code(self):
        v2 = build_all.migrate_v1_to_v2(V1_SNAPSHOT)
        for official_id in ("official-a", "official-b"):
            funding = self.funding(v2, official_id)
            self.assertEqual(funding["source_type"], "unknown")
            self.assertIn("SOURCE_TYPE_UNKNOWN", funding["warning_codes"])
        self.assertValid(v2)

    def test_failed_build_carries_unknown(self):
        self.start_from_v1()
        bad = copy.deepcopy(API_STATEMENTS)
        bad[0]["stmt_link"] = {"url": "https://evil.example.com/x"}
        _, freshness = self.build(api=fake_socrata(statement_rows=bad))
        funding = self.funding(freshness)
        self.assertEqual((funding["status"], funding["source_type"]), ("failed", "unknown"))
        self.assertIn("SOURCE_TYPE_UNKNOWN", funding["warning_codes"])

    def test_skipped_build_carries_unknown(self):
        self.start_from_v1()
        _, freshness = self.build(api=fake_socrata("down", "down"))  # no cache -> skipped
        for official_id in ("official-a", "official-b"):
            funding = self.funding(freshness, official_id)
            self.assertEqual((funding["status"], funding["source_type"]), ("skipped", "unknown"))
            self.assertIn("SOURCE_TYPE_UNKNOWN", funding["warning_codes"])

    def test_live_success_replaces_unknown_with_automated_api(self):
        self.start_from_v1()
        _, freshness = self.build(api=fake_socrata())
        funding = self.funding(freshness)
        self.assertEqual((funding["status"], funding["source_type"]), ("ok", "automated_api"))
        self.assertNotIn("SOURCE_TYPE_UNKNOWN", funding["warning_codes"])

    def test_cached_success_replaces_unknown_with_automated_api(self):
        self.build(api=fake_socrata(), save=False)  # seed caches only
        self.start_from_v1()
        _, freshness = self.build(api=fake_socrata("down", "down"), now=NOW_LATER)
        funding = self.funding(freshness)
        self.assertEqual((funding["status"], funding["source_type"]), ("ok", "automated_api"))
        self.assertIn("SOURCE_CACHE_FALLBACK", funding["warning_codes"])
        self.assertNotIn("SOURCE_TYPE_UNKNOWN", funding["warning_codes"])

    def test_csv_success_replaces_unknown_with_automated_csv(self):
        self.start_from_v1()
        _, freshness = self.build()
        funding = self.funding(freshness)
        self.assertEqual((funding["status"], funding["source_type"]), ("ok", "automated_csv"))
        self.assertNotIn("SOURCE_TYPE_UNKNOWN", funding["warning_codes"])

    def test_new_entry_without_previous_never_becomes_unknown(self):
        self.repo.path("data", "raw", "contributions.csv").unlink()
        _, csv_skipped = self.build(save=False)  # no previous file, CSV missing
        self.assertEqual(self.funding(csv_skipped)["status"], "skipped")
        self.assertEqual(self.funding(csv_skipped)["source_type"], "automated_csv")
        _, api_skipped = self.build(api=fake_socrata("down", "down"), save=False)
        self.assertEqual(self.funding(api_skipped)["source_type"], "automated_api")
        for f in (csv_skipped, api_skipped):
            self.assertNotIn("SOURCE_TYPE_UNKNOWN", self.funding(f)["warning_codes"])
            self.assertValid(f)

    def test_generator_rejects_unknown_as_an_attempt_type(self):
        with self.assertRaises(ValueError):
            build_all._funding_entry(
                prev=None, status="ok", attempted_at="2026-10-18T12:00:00+00:00", run_date="2026-10-18",
                attempt_source_type="unknown", source_loaded=True, committees=["c"], matched_rows=[],
                displayed_count=0, contributions=None, statements=None,
            )

    def test_validator_ties_unknown_to_its_code_and_to_migration_shape(self):
        v2 = build_all.migrate_v1_to_v2(V1_SNAPSHOT)
        missing_code = copy.deepcopy(v2)
        self.funding(missing_code)["warning_codes"].remove("SOURCE_TYPE_UNKNOWN")
        self.assertInvalid(missing_code, "SOURCE_TYPE_UNKNOWN must be present exactly when source_type is unknown")
        _, csv = self.build(save=False)
        stray_code = copy.deepcopy(csv)
        self.funding(stray_code)["warning_codes"] = sorted(self.funding(stray_code)["warning_codes"] + ["SOURCE_TYPE_UNKNOWN"])
        self.assertInvalid(stray_code, "SOURCE_TYPE_UNKNOWN must be present exactly when source_type is unknown")
        # a v2-built entry relabelled "unknown" still carries v2-only measurements
        relabelled = copy.deepcopy(csv)
        entry = self.funding(relabelled)
        entry["source_type"] = "unknown"
        entry["warning_codes"] = sorted(entry["warning_codes"] + ["SOURCE_TYPE_UNKNOWN"])
        self.assertInvalid(relabelled, "must be null while source_type is unknown")
        self.assertInvalid(relabelled, "latest_reporting_period_end must be null while source_type is unknown")


# --- final verification: cache sidecar hygiene --------------------------------


class _FakeResponse:
    def __init__(self, body):
        self.body = body

    def read(self):
        return self.body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class TestCacheSidecarHygiene(unittest.TestCase):
    SECRET = "tok-SECRET-do-not-persist-123"

    def setUp(self):
        import tempfile

        socrata.reset_fetch_outcomes()
        self.tmp = Path(tempfile.mkdtemp(prefix="cyp-sidecar-"))
        self.cache = self.tmp / "x.json"
        self.meta = socrata.cache_meta_path(self.cache)

    def tearDown(self):
        import shutil

        socrata.reset_fetch_outcomes()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def live_fetch_through_real_request(self, rows, where="cmt_id = '1'"):
        """Exercise the real _request (headers included); only urlopen is faked."""
        sent = []

        def urlopen(req, timeout):
            sent.append(req)
            return _FakeResponse(json.dumps(rows).encode("utf-8"))

        with mock.patch.dict("os.environ", {"SOCRATA_APP_TOKEN": self.SECRET}), mock.patch.object(
            socrata.urllib.request, "urlopen", urlopen
        ), mock.patch.object(socrata, "_utcnow", lambda: FETCH_1):
            out = socrata.fetch_dataset("res-1", where=where, cache_path=self.cache, retries=1)
        return out, sent

    def test_production_sidecars_live_next_to_the_gitignored_caches(self):
        cache_dir = build_funding.ROOT / "data" / "raw" / ".cache"
        for cache in (build_funding.CONTRIBUTIONS_CACHE, build_funding.STATEMENTS_CACHE):
            meta = socrata.cache_meta_path(cache)
            self.assertEqual(meta.parent, cache_dir)
            self.assertEqual(meta.name, cache.name + ".meta.json")
        import shutil
        import subprocess

        if shutil.which("git") is None:
            self.skipTest("git not available")
        root = build_funding.ROOT
        inside = subprocess.run(["git", "-C", str(root), "rev-parse", "--is-inside-work-tree"], capture_output=True, text=True)
        if inside.returncode != 0:
            self.skipTest("not a git checkout")
        for cache in (build_funding.CONTRIBUTIONS_CACHE, build_funding.STATEMENTS_CACHE):
            for path in (cache, socrata.cache_meta_path(cache), Path(str(socrata.cache_meta_path(cache)) + ".tmp")):
                result = subprocess.run(["git", "-C", str(root), "check-ignore", "-q", str(path)])
                self.assertEqual(result.returncode, 0, f"{path} is not gitignored")

    def test_sidecar_has_exactly_the_documented_fields_and_no_secrets(self):
        rows = [{"a": 1}, {"a": 2}]
        out, sent = self.live_fetch_through_real_request(rows)
        self.assertEqual(out, rows)
        self.assertEqual(sent[0].get_header("X-app-token"), self.SECRET)  # the token was really sent
        meta = json.loads(self.meta.read_text())
        self.assertEqual(set(meta), {"meta_version", "resource_id", "where", "retrieved_at", "row_count", "sha256"})
        self.assertEqual(meta["resource_id"], "res-1")
        self.assertEqual(meta["where"], "cmt_id = '1'")
        self.assertEqual(meta["retrieved_at"], FETCH_1_TS)
        self.assertEqual(meta["row_count"], 2)
        self.assertEqual(meta["sha256"], hashlib.sha256(self.cache.read_bytes()).hexdigest())
        for path in (self.cache, self.meta):
            text = path.read_text().lower()
            self.assertNotIn(self.SECRET.lower(), text)
            for marker in ("token", "authorization", "cookie", "password", "secret", "x-app"):
                self.assertNotIn(marker, text, f"{marker!r} in {path.name}")
        self.assertEqual(sorted(p.name for p in self.tmp.iterdir()), ["x.json", "x.json.meta.json"])  # no temp left

    def test_crash_while_writing_sidecar_leaves_cache_unverified(self):
        self.live_fetch_through_real_request([{"a": 1}])  # a verified pair exists
        with mock.patch.object(type(self.meta), "replace", side_effect=OSError("simulated crash")):
            with self.assertRaises(OSError):
                self.live_fetch_through_real_request([{"a": 9}])
        self.assertFalse(self.meta.exists(), "the stale sidecar must be gone before the cache is rewritten")
        with mock.patch.object(socrata, "_request", lambda u, t, r: (_ for _ in ()).throw(socrata.SourceUnavailable("down"))):
            rows = socrata.fetch_dataset("res-1", where="cmt_id = '1'", cache_path=self.cache)
        self.assertEqual(rows, [{"a": 9}])  # cached rows may be used...
        self.assertEqual(socrata.get_fetch_outcome("res-1"), socrata.FetchOutcome("res-1", "cache_fallback", None, False))

    def test_metadata_without_cache_is_never_trusted(self):
        self.live_fetch_through_real_request([{"a": 1}])
        self.cache.unlink()
        for kwargs in ({"use_cache_only": True}, {}):
            with self.subTest(kwargs):
                with mock.patch.object(socrata, "_request", lambda u, t, r: (_ for _ in ()).throw(socrata.SourceUnavailable("down"))):
                    with self.assertRaises(socrata.SourceUnavailable):
                        socrata.fetch_dataset("res-1", where="cmt_id = '1'", cache_path=self.cache, **kwargs)
                self.assertEqual(socrata.get_fetch_outcome("res-1"), socrata.FetchOutcome("res-1", "unavailable", None, False))

    def test_corrupted_cache_with_metadata_is_never_trusted(self):
        # Unchanged from main: an unreadable cache raises instead of returning
        # rows; no outcome with a timestamp is recorded.
        self.live_fetch_through_real_request([{"a": 1}])
        self.cache.write_text("{not json")
        with self.assertRaises(ValueError):
            socrata.fetch_dataset("res-1", where="cmt_id = '1'", cache_path=self.cache, use_cache_only=True)
        self.assertIsNone(socrata.get_fetch_outcome("res-1"))

    def test_same_row_count_edit_fails_the_hash(self):
        self.live_fetch_through_real_request([{"a": 1}, {"a": 2}])
        self.cache.write_text(json.dumps([{"a": 1}, {"a": 3}]))
        socrata.fetch_dataset("res-1", where="cmt_id = '1'", cache_path=self.cache, use_cache_only=True)
        self.assertEqual(socrata.get_fetch_outcome("res-1"), socrata.FetchOutcome("res-1", "cache_only", None, False))


class TestCorruptedCacheBuild(FreshnessTestCase):
    def test_corrupted_contributions_cache_stops_the_build_before_any_write(self):
        self.build(api=fake_socrata())  # caches, sidecars, generated files exist
        self.cache.write_text("{not json")
        before = self.generated_bytes()
        with self.assertRaises(ValueError):
            self.build(api=fake_socrata("down", "live"), now=NOW_LATER)
        self.assertEqual(self.generated_bytes(), before)


# --- corrective pass: robustness regressions ----------------------------------


class TestPreviousFileReadFailures(FreshnessTestCase):
    """Expected read/decode failures of the previous freshness.json become
    structured preflight problems; they never escape as exceptions."""

    def assert_structured_problem(self, fragment):
        data, problems, kind = build_all.load_previous_freshness(self.fpath, self.ids)
        self.assertIsNone(data)
        self.assertEqual(kind, "invalid")
        self.assertEqual(len(problems), 1, problems)
        self.assertIn(fragment, problems[0])

    def test_invalid_utf8_is_a_problem(self):
        self.fpath.write_bytes(b'{"schema_version": "2.0", "generated_at": "\xff\xfe"}')
        self.assert_structured_problem("not valid UTF-8")

    def test_permission_error_is_a_problem(self):
        self.write_json(self.fpath, self.build(save=False)[1])
        error = PermissionError(13, "Permission denied", str(self.fpath))
        with mock.patch.object(type(self.fpath), "read_bytes", side_effect=error), mock.patch.object(
            type(self.fpath), "read_text", side_effect=error
        ):
            self.assert_structured_problem("could not be read")

    def test_disappearing_during_read_is_a_problem(self):
        # exists() saw the file; it vanished before the read completed.
        self.write_json(self.fpath, self.build(save=False)[1])
        error = FileNotFoundError(2, "No such file or directory", str(self.fpath))
        with mock.patch.object(type(self.fpath), "read_bytes", side_effect=error), mock.patch.object(
            type(self.fpath), "read_text", side_effect=error
        ):
            self.assert_structured_problem("could not be read")

    def test_unreadable_previous_file_stops_the_build_before_any_write(self):
        self.build(save=True)
        self.fpath.write_bytes(b"\xff\xfe\x00{")
        before = self.generated_bytes()
        result, freshness = self.build(save=False)
        self.assertEqual(freshness, {})
        self.assertTrue(any("not valid UTF-8" in n for n in result.fatal_errors), result.fatal_errors)
        self.assertEqual(self.generated_bytes(), before)


class TestWarningListShapes(FreshnessTestCase):
    """Non-string warning-list members are reported, not raised as TypeError."""

    BAD_LISTS = {
        "dict": [{"code": "ZERO_ITEMS"}],
        "nested list": [["ZERO_ITEMS"]],
        "null": [None],
        "integer": [7],
        "mixed": ["ZERO_ITEMS", {"a": 1}, ["x"], None, 3],
        "mixed hashable": ["ZERO_ITEMS", None, 3],  # sorting str with int/None raises TypeError
    }

    def test_non_string_members_are_problems_for_both_datasets(self):
        base = self.build(save=False)[1]
        for dataset in ("funding", "record"):
            for label, codes in self.BAD_LISTS.items():
                with self.subTest(dataset=dataset, shape=label):
                    f = copy.deepcopy(base)
                    f["officials"]["official-a"][dataset]["warning_codes"] = copy.deepcopy(codes)
                    try:
                        problems = validate_data.validate_freshness(f, self.ids)
                    except TypeError as exc:  # the regression: must not raise
                        self.fail(f"validate_freshness raised TypeError: {exc}")
                    self.assertTrue(any("warning_codes" in p for p in problems), problems)


class TestAttemptBounds(FreshnessTestCase):
    """source_retrieved_at and latest_reporting_period_end describe what the
    attempt used, so neither may be later than that entry's attempted_at, even
    when still before the snapshot's generated_at."""

    def api_snapshot(self):
        _, freshness = self.build(api=fake_socrata(), save=False)
        return freshness

    def test_retrieval_after_attempt_is_rejected(self):
        f = self.api_snapshot()  # retrieved 11:59, attempted 12:00, generated 12:00
        control = copy.deepcopy(f)
        self.funding(control)["attempted_at"] = "2026-10-18T11:59:00+00:00"  # equal is fine
        self.assertValid(control)
        self.funding(f)["attempted_at"] = "2026-10-18T11:30:00+00:00"
        self.assertInvalid(f, "source_retrieved_at 2026-10-18T11:59:00+00:00 is after attempted_at")

    def test_period_after_attempt_date_is_rejected(self):
        f = self.api_snapshot()  # generated 2026-10-18
        entry = self.funding(f)
        entry.update(
            attempted_at="2026-10-17T12:00:00+00:00",
            last_success_at="2026-10-17",
            source_retrieved_at="2026-10-17T11:59:00+00:00",
        )
        control = copy.deepcopy(f)
        self.funding(control)["latest_reporting_period_end"] = "2026-10-17"  # attempt date itself is fine
        self.assertValid(control)
        entry["latest_reporting_period_end"] = "2026-10-18"  # before generated_at's date, after the attempt's
        self.assertInvalid(f, "latest_reporting_period_end 2026-10-18 is after attempted_at's UTC date 2026-10-17")


class TestStandaloneValidatorReadFailures(FreshnessTestCase):
    """validate_freshness_file() reports expected read/decode failures as
    problems, consistent with load_previous_freshness(). An initially missing
    file is still allowed; one that vanishes mid-read is a read failure."""

    def assert_single_problem(self, fragment):
        problems = validate_data.validate_freshness_file(self.fpath, self.ids)
        self.assertEqual(len(problems), 1, problems)
        self.assertIn(fragment, problems[0])

    def test_invalid_utf8(self):
        self.fpath.write_bytes(b'{"schema_version": "2.0", "generated_at": "\xff\xfe"}')
        self.assert_single_problem("not valid UTF-8")

    def test_permission_failure(self):
        self.write_json(self.fpath, self.build(save=False)[1])
        error = PermissionError(13, "Permission denied", str(self.fpath))
        with mock.patch.object(type(self.fpath), "read_bytes", side_effect=error), mock.patch.object(
            type(self.fpath), "read_text", side_effect=error
        ):
            self.assert_single_problem("could not be read")

    def test_disappearance_during_read(self):
        self.write_json(self.fpath, self.build(save=False)[1])
        error = FileNotFoundError(2, "No such file or directory", str(self.fpath))
        with mock.patch.object(type(self.fpath), "read_bytes", side_effect=error), mock.patch.object(
            type(self.fpath), "read_text", side_effect=error
        ):
            self.assert_single_problem("could not be read")

    def test_initially_missing_file_is_still_allowed(self):
        self.assertFalse(self.fpath.exists())
        self.assertEqual(validate_data.validate_freshness_file(self.fpath, self.ids), [])

    def test_cli_reports_invalid_utf8_without_traceback(self):
        # Real CLI on a throwaway copy of the real scripts/ and data/ (the
        # committed files are only read); only freshness.json is corrupted.
        import os
        import shutil
        import subprocess
        import tempfile

        tmp = Path(tempfile.mkdtemp(prefix="cyp-cli-"))
        self.addCleanup(shutil.rmtree, tmp, True)
        app = tmp / "la-money-votes"
        shutil.copytree(REPO_ROOT / "scripts", app / "scripts", ignore=shutil.ignore_patterns("__pycache__"))
        shutil.copytree(REPO_ROOT / "data", app / "data", ignore=shutil.ignore_patterns("raw", "__pycache__"))
        (app / "data" / "freshness.json").write_bytes(b"\xff\xfe{}")
        env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
        result = subprocess.run(
            [sys.executable, "scripts/validate_data.py"], cwd=app, capture_output=True, text=True, env=env, timeout=120
        )
        output = result.stdout + result.stderr
        self.assertNotEqual(result.returncode, 0, output)
        self.assertNotIn("Traceback", output)
        self.assertIn("1 problem(s) found:", result.stdout)
        self.assertIn("freshness.json: not valid UTF-8", result.stdout)


class TestChronologyBounds(FreshnessTestCase):
    """source_retrieved_at <= attempted_at and latest_reporting_period_end <=
    attempted_at's UTC date, for ok, failed and skipped entries."""

    RETRIEVED = FETCH_1_TS  # "2026-10-18T11:59:00+00:00", from the live build at NOW_1

    def entries_by_status(self):
        """Real ok/failed/skipped funding entries (official-a), each carrying a
        verified source_retrieved_at and a computed period from the ok build."""
        _, ok = self.build(api=fake_socrata())
        bad = copy.deepcopy(API_STATEMENTS)
        bad[0]["stmt_link"] = {"url": "https://evil.example.com/x"}
        _, failed = self.build(api=fake_socrata(statement_rows=bad), now=NOW_LATER, fetch_time=FETCH_LATER, save=False)
        for path in (self.cache, self.stmt_cache):
            path.unlink()
        _, skipped = self.build(api=fake_socrata("down", "down"), now=NOW_LATER, save=False)
        out = {"ok": ok, "failed": failed, "skipped": skipped}
        for status, snapshot in out.items():
            entry = self.funding(snapshot)
            self.assertEqual(entry["status"], status)
            self.assertEqual(entry["source_retrieved_at"], self.RETRIEVED)
            self.assertIsNotNone(entry["latest_reporting_period_end"])
        return out

    def test_retrieval_time_against_the_attempt(self):
        cases = {
            "equal": ("2026-10-18T11:59:00+00:00", True),
            "retrieved before attempt": ("2026-10-18T12:00:00+00:00", True),
            "retrieved after attempt": ("2026-10-18T11:30:00+00:00", False),
        }
        for status, snapshot in self.entries_by_status().items():
            for label, (attempted_at, accepted) in cases.items():
                with self.subTest(status=status, case=label):
                    f = copy.deepcopy(snapshot)
                    entry = self.funding(f)
                    entry["attempted_at"] = attempted_at
                    entry["last_success_at"] = "2026-10-18"
                    generated = validate_data.parse_utc_timestamp(f["generated_at"])
                    self.assertLessEqual(validate_data.parse_utc_timestamp(attempted_at), generated)
                    self.assertLess(validate_data.parse_utc_timestamp(self.RETRIEVED), generated)  # retrieval precedes generated_at
                    if accepted:
                        self.assertValid(f)
                    else:
                        self.assertInvalid(f, f"source_retrieved_at {self.RETRIEVED} is after attempted_at {attempted_at}")

    def test_reporting_period_against_the_attempt_date(self):
        cases = {
            "equal": ("2026-09-30", True),
            "period before attempt date": ("2026-10-01", True),
            "period after attempt date": ("2026-09-29", False),
        }
        for status, snapshot in self.entries_by_status().items():
            for label, (attempt_day, accepted) in cases.items():
                with self.subTest(status=status, case=label):
                    f = copy.deepcopy(snapshot)
                    entry = self.funding(f)
                    entry["latest_reporting_period_end"] = "2026-09-30"
                    entry["attempted_at"] = f"{attempt_day}T12:00:00+00:00"
                    entry["last_success_at"] = attempt_day
                    entry["source_retrieved_at"] = f"{attempt_day}T11:00:00+00:00"
                    if accepted:
                        self.assertValid(f)
                    else:
                        self.assertInvalid(f, f"latest_reporting_period_end 2026-09-30 is after attempted_at's UTC date {attempt_day}")

    def test_subset_build_preserves_an_older_untargeted_entry(self):
        _, first = self.build(api=fake_socrata())  # both officials attempted at NOW_1
        older = copy.deepcopy(first["officials"]["official-b"])
        _, second = self.build(api=fake_socrata(), now=NOW_LATER, fetch_time=FETCH_LATER, target_ids=["official-a"])
        self.assertValid(second)  # build() also validated it before saving
        self.assertEqual(second["officials"]["official-b"], older)  # unchanged, incl. attempted_at
        self.assertLess(older["funding"]["attempted_at"], second["generated_at"])
        self.assertEqual(self.funding(second)["attempted_at"], second["generated_at"])
        self.assertEqual(self.funding(second)["source_retrieved_at"], FETCH_LATER_TS)


if __name__ == "__main__":
    unittest.main()
