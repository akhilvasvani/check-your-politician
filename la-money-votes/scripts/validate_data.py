#!/usr/bin/env python3
"""la-money-votes — validate_data.py

Schema- and cross-reference-validates whatever JSON is currently committed
under data/ — data/officials.json, data/sources/registry.json, every
data/officials/<id>/{funding.json,record.json}, and data/freshness.json
(schema_version 2.0; see validate_freshness()). A missing freshness.json is
allowed (the site does not depend on it); a present but malformed or
contract-violating one fails validation. Makes no network calls and
does not rebuild anything, so it is fast, deterministic, and safe to run on
every pull request regardless of whether the LA Ethics Commission API is
reachable from the CI runner.

This is what the CI workflow (.github/workflows/ci.yml) runs on every PR. A
full rebuild-from-source dry run (--fetch-socrata) is deliberately NOT part
of the required PR check, since it depends on a third-party API being up;
that live-fetch smoke test still runs, but only in the scheduled refresh
workflow where a flaky fetch is expected to be visible in the build report
rather than block unrelated PRs. See README "CI vs. scheduled refresh".

Usage:
    python3 scripts/validate_data.py
    python3 scripts/validate_data.py --json   # machine-readable output
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pipeline import registry as reg, schemas, validation

ROOT = Path(__file__).resolve().parent.parent
FRESHNESS_PATH = ROOT / "data" / "freshness.json"

# --- freshness.json contract (schema_version 2.0) ---------------------------
#
# The hand-rolled schema validator (pipeline/validation.py) only understands
# type/enum/required/properties/items/additionalProperties, so every date,
# cross-field and coverage rule below is enforced here in Python. See
# data/schemas/freshness.schema.json and CONTRACT.md for field semantics.

FRESHNESS_SCHEMA_VERSION = "2.0"

WARNING_CODES = frozenset(
    {
        "SOURCE_CACHE_FALLBACK",
        "SUPPORTING_SOURCE_CACHE_FALLBACK",
        "SOURCE_RETRIEVED_AT_UNKNOWN",
        "SOURCE_TYPE_UNKNOWN",
        "SOURCE_UNAVAILABLE",
        "BUILD_FAILED_PREVIOUS_DATA_SERVED",
        "NO_COMMITTEE_CONFIGURED",
        "NO_ROWS_MATCHED",
        "ZERO_ITEMS",
        "LATEST_REPORTING_PERIOD_UNKNOWN",
        "REVIEW_DATE_MISSING",
        "EMPLOYER_OCCUPATION_UNAVAILABLE",
    }
)
FUNDING_WARNING_CODES = WARNING_CODES - {"REVIEW_DATE_MISSING"}
# Funding source types. "unknown" exists only for entries migrated from
# schema v1, which never recorded how funding was built; any successful v2
# build replaces it with the attempt's real source type.
FUNDING_SOURCE_TYPES = frozenset({"automated_api", "automated_csv", "unknown"})
STATUSES = ("ok", "failed", "skipped")
RECORD_WARNING_CODES = frozenset(
    {"SOURCE_UNAVAILABLE", "BUILD_FAILED_PREVIOUS_DATA_SERVED", "ZERO_ITEMS", "REVIEW_DATE_MISSING"}
)

# Strict UTC timestamp: seconds precision, explicit +00:00 or Z offset.
_UTC_TS_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\+00:00|Z)$")


def parse_utc_timestamp(value):
    """Return an aware UTC datetime for a strict 'YYYY-MM-DDTHH:MM:SS+00:00'
    (or '...Z') string, else None. Impossible dates/times return None."""
    if not isinstance(value, str) or not _UTC_TS_RE.match(value):
        return None
    try:
        parsed = datetime.strptime(value[:19], "%Y-%m-%dT%H:%M:%S")
    except ValueError:
        return None
    return parsed.replace(tzinfo=timezone.utc)


def _is_count(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _reject_duplicate_keys(pairs):
    seen = {}
    for key, value in pairs:
        if key in seen:
            raise ValueError(f"duplicate key {key!r}")
        seen[key] = value
    return seen


def parse_freshness_text(text: str):
    """Parse freshness.json text, rejecting duplicate object keys (which
    json.loads would otherwise silently collapse). Returns (data, problems)."""
    try:
        return json.loads(text, object_pairs_hook=_reject_duplicate_keys), []
    except ValueError as exc:  # JSONDecodeError is a ValueError subclass
        return None, [f"freshness.json: not valid JSON: {exc}"]


def _check_date(problems, where, field, value, gen_date, nullable=True):
    if value is None:
        if not nullable:
            problems.append(f"{where}.{field}: must not be null")
        return None
    if not validation.is_valid_date(value):
        problems.append(f"{where}.{field}: {value!r} is not a valid YYYY-MM-DD date")
        return None
    if gen_date is not None and value > gen_date:
        problems.append(f"{where}.{field}: {value} is after generated_at's date {gen_date}")
    return value


def _check_ts(problems, where, field, value, gen_ts, nullable=False):
    if value is None:
        if not nullable:
            problems.append(f"{where}.{field}: must not be null")
        return None
    parsed = parse_utc_timestamp(value)
    if parsed is None:
        problems.append(f"{where}.{field}: {value!r} is not a valid UTC timestamp (YYYY-MM-DDTHH:MM:SS+00:00)")
        return None
    if gen_ts is not None and parsed > gen_ts:
        problems.append(f"{where}.{field}: {value} is after generated_at")
    return parsed


def _check_warnings(problems, where, codes, allowed):
    if not isinstance(codes, list):
        return set()
    unknown = [c for c in codes if c not in WARNING_CODES]
    if unknown:
        problems.append(f"{where}.warning_codes: unknown code(s) {unknown}")
    wrong_dataset = [c for c in codes if c in WARNING_CODES and c not in allowed]
    if wrong_dataset:
        problems.append(f"{where}.warning_codes: code(s) {wrong_dataset} not allowed for this dataset")
    if len(set(codes)) != len(codes):
        problems.append(f"{where}.warning_codes: duplicate codes")
    if codes != sorted(codes):
        problems.append(f"{where}.warning_codes: must be sorted")
    return set(codes)


def _check_common(problems, where, entry, gen_ts, gen_date):
    attempted = _check_ts(problems, where, "attempted_at", entry.get("attempted_at"), gen_ts)
    last_success = _check_date(problems, where, "last_success_at", entry.get("last_success_at"), gen_date)
    status = entry.get("status")
    if status == "ok":
        if last_success is None:
            problems.append(f"{where}: status 'ok' requires last_success_at")
        elif attempted is not None:
            # v2 builds write attempted_at's UTC date. Entries migrated from
            # v1 may carry v1's local build date, which in a timezone west of
            # UTC can be the previous calendar day; nothing else is allowed.
            day = attempted.date()
            allowed = {day.isoformat(), (day - timedelta(days=1)).isoformat()}
            if last_success not in allowed:
                problems.append(
                    f"{where}: status 'ok' means this attempt succeeded, so last_success_at "
                    f"({last_success}) must be attempted_at's UTC date ({day.isoformat()}) or the day before"
                )
    if attempted is not None and last_success is not None and last_success > attempted.date().isoformat():
        problems.append(f"{where}: last_success_at {last_success} is after attempted_at")
    return status, last_success


def _validate_funding_entry(problems, where, entry, gen_ts, gen_date):
    status, last_success = _check_common(problems, where, entry, gen_ts, gen_date)
    _check_ts(problems, where, "source_retrieved_at", entry.get("source_retrieved_at"), gen_ts, nullable=True)
    _check_date(problems, where, "latest_reporting_period_end", entry.get("latest_reporting_period_end"), gen_date)
    source_type = entry.get("source_type")
    if source_type in ("automated_csv", "unknown") and entry.get("source_retrieved_at") is not None:
        problems.append(f"{where}: source_retrieved_at must be null for {source_type} (not a verified live retrieval)")

    displayed = entry.get("displayed_donor_count")
    matched = entry.get("matched_row_count")
    legacy = entry.get("donor_count")
    if not _is_count(displayed):
        problems.append(f"{where}.displayed_donor_count: must be a nonnegative integer, got {displayed!r}")
    if not _is_count(legacy):
        problems.append(f"{where}.donor_count: must be a nonnegative integer, got {legacy!r}")
    if matched is not None and not _is_count(matched):
        problems.append(f"{where}.matched_row_count: must be a nonnegative integer or null, got {matched!r}")
    if legacy != displayed:
        problems.append(f"{where}: donor_count ({legacy!r}) must equal displayed_donor_count ({displayed!r})")
    if _is_count(displayed) and _is_count(matched) and displayed > matched:
        problems.append(f"{where}: displayed_donor_count ({displayed}) exceeds matched_row_count ({matched})")

    codes = _check_warnings(problems, where, entry.get("warning_codes"), FUNDING_WARNING_CODES)
    if (entry.get("latest_reporting_period_end") is None) != ("LATEST_REPORTING_PERIOD_UNKNOWN" in codes):
        problems.append(f"{where}: LATEST_REPORTING_PERIOD_UNKNOWN must be present exactly when latest_reporting_period_end is null")
    if "ZERO_ITEMS" in codes and displayed != 0:
        problems.append(f"{where}: ZERO_ITEMS requires displayed_donor_count == 0")
    if "EMPLOYER_OCCUPATION_UNAVAILABLE" in codes and source_type != "automated_api":
        problems.append(f"{where}: EMPLOYER_OCCUPATION_UNAVAILABLE only applies to source_type automated_api")
    if (source_type == "unknown") != ("SOURCE_TYPE_UNKNOWN" in codes):
        problems.append(f"{where}: SOURCE_TYPE_UNKNOWN must be present exactly when source_type is unknown")
    if source_type == "unknown":
        # "unknown" only comes from the v1 migration and is replaced by the
        # first successful v2 funding build, so no v2-only measurement can
        # exist alongside it.
        for field in ("source_retrieved_at", "latest_reporting_period_end", "matched_row_count"):
            if entry.get(field) is not None:
                problems.append(f"{where}: {field} must be null while source_type is unknown (v1-migrated, no successful v2 funding build yet)")
    if (entry.get("source_retrieved_at") is None) != ("SOURCE_RETRIEVED_AT_UNKNOWN" in codes):
        problems.append(f"{where}: SOURCE_RETRIEVED_AT_UNKNOWN must be present exactly when source_retrieved_at is null")
    for code in ("SOURCE_CACHE_FALLBACK", "SUPPORTING_SOURCE_CACHE_FALLBACK"):
        if code in codes and source_type != "automated_api" and status == "ok":
            problems.append(f"{where}: {code} on a successful build requires source_type automated_api")
    _check_status_codes(problems, where, status, last_success, codes)


def _validate_record_entry(problems, where, entry, gen_ts, gen_date):
    status, last_success = _check_common(problems, where, entry, gen_ts, gen_date)
    _check_date(problems, where, "reviewed_through", entry.get("reviewed_through"), gen_date)
    count = entry.get("item_count")
    if not _is_count(count):
        problems.append(f"{where}.item_count: must be a nonnegative integer, got {count!r}")
    codes = _check_warnings(problems, where, entry.get("warning_codes"), RECORD_WARNING_CODES)
    if (entry.get("reviewed_through") is None) != ("REVIEW_DATE_MISSING" in codes):
        problems.append(f"{where}: REVIEW_DATE_MISSING must be present exactly when reviewed_through is null")
    if "ZERO_ITEMS" in codes and count != 0:
        problems.append(f"{where}: ZERO_ITEMS requires item_count == 0")
    _check_status_codes(problems, where, status, last_success, codes)


def _check_status_codes(problems, where, status, last_success, codes):
    if "BUILD_FAILED_PREVIOUS_DATA_SERVED" in codes and not (status == "failed" and last_success is not None):
        problems.append(f"{where}: BUILD_FAILED_PREVIOUS_DATA_SERVED requires status 'failed' and a prior last_success_at")
    if "SOURCE_UNAVAILABLE" in codes and status == "ok":
        problems.append(f"{where}: SOURCE_UNAVAILABLE is inconsistent with status 'ok'")


def validate_freshness(freshness, official_ids, require_all: bool = True) -> list:
    """Validate a parsed freshness.json (schema_version 2.0).

    official_ids: the ids from data/officials.json. With require_all=True
    (the committed-file check) every id must appear exactly once and no
    other id may appear. require_all=False is only for reading a *previous*
    snapshot to carry values forward, where an official added since then is
    legitimately absent.
    """
    problems = []
    if not isinstance(freshness, dict):
        return ["freshness.json: top level must be an object"]
    version = freshness.get("schema_version")
    if version != FRESHNESS_SCHEMA_VERSION:
        return [f"freshness.json: unsupported schema_version {version!r} (expected {FRESHNESS_SCHEMA_VERSION!r})"]

    problems.extend(f"freshness.json: {p}" for p in validation.validate_schema(freshness, schemas.get("freshness")))

    gen_ts = parse_utc_timestamp(freshness.get("generated_at"))
    if gen_ts is None:
        problems.append(f"freshness.json: generated_at {freshness.get('generated_at')!r} is not a valid UTC timestamp")
    gen_date = gen_ts.date().isoformat() if gen_ts else None

    officials = freshness.get("officials")
    if not isinstance(officials, dict):
        return problems
    expected = set(official_ids)
    unknown = sorted(set(officials) - expected)
    if unknown:
        problems.append(f"freshness.json: unknown official id(s) not in officials.json: {unknown}")
    if require_all:
        missing = sorted(expected - set(officials))
        if missing:
            problems.append(f"freshness.json: missing official id(s) from officials.json: {missing}")

    for official_id, datasets in officials.items():
        if not isinstance(datasets, dict):
            continue
        funding = datasets.get("funding")
        record = datasets.get("record")
        if isinstance(funding, dict):
            _validate_funding_entry(problems, f"freshness.json: {official_id}.funding", funding, gen_ts, gen_date)
        if isinstance(record, dict):
            _validate_record_entry(problems, f"freshness.json: {official_id}.record", record, gen_ts, gen_date)
    return problems


_V1_DATASET_KEYS = {"funding": "donor_count", "record": "item_count"}


def validate_freshness_v1(data) -> list:
    """Strictly validate a legacy schema-v1 freshness.json (as written by
    build_all.py before v2), so that only a genuine v1 file is ever migrated.

    v1 shape: {"generated_at": ts, "officials": {id: {"funding": {status,
    last_success_at, donor_count}, "record": {status, last_success_at,
    item_count}}}}, no other keys. v1 wrote last_success_at = the local
    build date when status was "ok", else null. A v1 subset (--official) run
    wrote only the targeted officials, so officials may be a subset."""
    problems = []
    where = "freshness.json (v1)"
    if not isinstance(data, dict):
        return [f"{where}: top level must be an object"]
    if set(data) != {"generated_at", "officials"}:
        return [f"{where}: keys must be exactly generated_at and officials, got {sorted(data)}"]
    gen = parse_utc_timestamp(data["generated_at"])
    if gen is None:
        problems.append(f"{where}: generated_at {data['generated_at']!r} is not a valid UTC timestamp")
    officials = data["officials"]
    if not isinstance(officials, dict):
        return problems + [f"{where}: officials must be an object"]
    allowed_dates = None
    if gen is not None:
        allowed_dates = {gen.date().isoformat(), (gen.date() - timedelta(days=1)).isoformat()}
    for official_id, datasets in officials.items():
        if not isinstance(datasets, dict) or set(datasets) != set(_V1_DATASET_KEYS):
            problems.append(f"{where}: {official_id} must have exactly funding and record")
            continue
        for dataset, count_key in _V1_DATASET_KEYS.items():
            entry = datasets[dataset]
            at = f"{where}: {official_id}.{dataset}"
            if not isinstance(entry, dict) or set(entry) != {"status", "last_success_at", count_key}:
                problems.append(f"{at}: keys must be exactly status, last_success_at, {count_key}")
                continue
            if entry["status"] not in STATUSES:
                problems.append(f"{at}.status: {entry['status']!r} is not one of {list(STATUSES)}")
            if not _is_count(entry[count_key]):
                problems.append(f"{at}.{count_key}: must be a nonnegative integer")
            last = entry["last_success_at"]
            if (entry["status"] == "ok") != (last is not None):
                problems.append(f"{at}: v1 sets last_success_at exactly when status is 'ok'")
            if last is not None:
                if not validation.is_valid_date(last):
                    problems.append(f"{at}.last_success_at: {last!r} is not a valid YYYY-MM-DD date")
                elif allowed_dates is not None and last not in allowed_dates:
                    problems.append(f"{at}.last_success_at: {last} is not generated_at's date or the day before")
    return problems


def validate_freshness_file(path: Path, official_ids, require_all: bool = True) -> list:
    """Validate freshness.json on disk. A missing file is not a problem (the
    site does not depend on it); an existing malformed file is. A committed
    file must be v2; a legacy v1 file is reported so it is not mistaken for
    a valid v2 one (build_all.py migrates a valid v1 file automatically on
    its next run)."""
    path = Path(path)
    if not path.exists():
        return []
    data, problems = parse_freshness_text(path.read_text())
    if problems:
        return problems
    if isinstance(data, dict) and "schema_version" not in data:
        v1_problems = validate_freshness_v1(data)
        if v1_problems:
            return v1_problems
        return ["freshness.json: legacy schema v1 file; run build_all.py once to migrate it to v2"]
    return validate_freshness(data, official_ids, require_all=require_all)


def validate_all() -> list:
    problems = []

    officials_path = reg.OFFICIALS_INDEX
    registry_path = reg.SOURCES_REGISTRY

    if not officials_path.exists():
        return [f"missing {officials_path}"]
    if not registry_path.exists():
        return [f"missing {registry_path}"]

    officials = reg.load_officials(officials_path)
    sources_registry = reg.load_registry(registry_path)

    problems.extend(f"officials.json: {p}" for p in validation.validate_schema(officials, schemas.get("officials")))
    problems.extend(
        f"registry.json: {p}" for p in validation.validate_schema(sources_registry, schemas.get("sources_registry"))
    )
    problems.extend(reg.validate_cross_reference(officials, sources_registry))

    for official in officials:
        official_id = official.get("id")
        funding_path = ROOT / "data" / "officials" / official_id / "funding.json"
        record_path = ROOT / "data" / "officials" / official_id / "record.json"

        if not funding_path.exists():
            problems.append(f"{official_id}: missing funding.json")
        else:
            funding = json.loads(funding_path.read_text())
            problems.extend(
                f"{official_id}/funding.json: {p}" for p in validation.validate_schema(funding, schemas.get("funding"))
            )
            dupes = validation.find_duplicates(funding.get("donors", []), key_fn=lambda d: d["name"])
            problems.extend(f"{official_id}/funding.json: duplicate donor '{d}'" for d in dupes)
            for donor in funding.get("donors", []):
                for c in donor.get("contributions", []):
                    if c.get("source_url") and not validation.is_valid_url(c["source_url"], validation.ALLOWED_SOURCE_DOMAINS):
                        problems.append(f"{official_id}/funding.json: donor '{donor['name']}' has an untrusted source_url")

        if not record_path.exists():
            problems.append(f"{official_id}: missing record.json")
        else:
            record = json.loads(record_path.read_text())
            problems.extend(
                f"{official_id}/record.json: {p}" for p in validation.validate_schema(record, schemas.get("record"))
            )
            dupes = validation.find_duplicates(record.get("items", []), key_fn=lambda i: i.get("council_file"))
            problems.extend(f"{official_id}/record.json: duplicate council_file '{d}'" for d in dupes)
            for item in record.get("items", []):
                if not validation.is_valid_record_id(item.get("council_file", "")):
                    problems.append(f"{official_id}/record.json: invalid council_file '{item.get('council_file')}'")
                if item.get("source_url") and not validation.is_valid_url(item["source_url"], validation.ALLOWED_SOURCE_DOMAINS):
                    problems.append(f"{official_id}/record.json: item {item.get('council_file')} has an untrusted source_url")

    problems.extend(validate_freshness_file(FRESHNESS_PATH, reg.official_ids(officials)))

    return problems


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--json", action="store_true", help="print machine-readable JSON instead of plain text")
    args = parser.parse_args()

    problems = validate_all()

    if args.json:
        print(json.dumps({"ok": not problems, "problems": problems}, indent=2))
    else:
        if not problems:
            print("all committed data is schema-valid and cross-referenced correctly")
        else:
            print(f"{len(problems)} problem(s) found:")
            for p in problems:
                print(f"  - {p}")

    if problems:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
