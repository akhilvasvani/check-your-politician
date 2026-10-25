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
    non_strings = [c for c in codes if not isinstance(c, str)]
    if non_strings:
        # Report and check only the string members; unhashable or mixed-type
        # members would otherwise raise TypeError below.
        problems.append(f"{where}.warning_codes: every code must be a string, got {non_strings!r}")
        codes = [c for c in codes if isinstance(c, str)]
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
    retrieved = _check_ts(problems, where, "source_retrieved_at", entry.get("source_retrieved_at"), gen_ts, nullable=True)
    period_end = _check_date(problems, where, "latest_reporting_period_end", entry.get("latest_reporting_period_end"), gen_date)
    # Both describe what this entry's attempt used, so neither can postdate it
    # (generated_at alone is not enough: subset runs keep older attempted_at).
    attempted = parse_utc_timestamp(entry.get("attempted_at"))
    if attempted is not None and retrieved is not None and retrieved > attempted:
        problems.append(f"{where}: source_retrieved_at {entry['source_retrieved_at']} is after attempted_at {entry['attempted_at']}")
    if attempted is not None and period_end is not None and period_end > attempted.date().isoformat():
        problems.append(
            f"{where}: latest_reporting_period_end {period_end} is after attempted_at's UTC date {attempted.date().isoformat()}"
        )
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
    try:
        raw = path.read_bytes()
    except OSError as exc:  # permissions, removed after exists(), I/O errors
        return [f"freshness.json: could not be read: {exc}"]
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        return [f"freshness.json: not valid UTF-8: {exc}"]
    data, problems = parse_freshness_text(text)
    if problems:
        return problems
    if isinstance(data, dict) and "schema_version" not in data:
        v1_problems = validate_freshness_v1(data)
        if v1_problems:
            return v1_problems
        return ["freshness.json: legacy schema v1 file; run build_all.py once to migrate it to v2"]
    return validate_freshness(data, official_ids, require_all=require_all)


def funding_payload_problems(official_id, funding) -> list:
    """Schema and semantic checks for one parsed funding.json (shared by
    validate_all() and the build-time snapshot check)."""
    problems = [f"{official_id}/funding.json: {p}" for p in validation.validate_schema(funding, schemas.get("funding"))]
    payload_id = (funding.get("official") or {}).get("id") if isinstance(funding, dict) else None
    if isinstance(funding, dict) and isinstance(funding.get("official"), dict) and payload_id != official_id:
        problems.append(f"{official_id}/funding.json: official.id {payload_id!r} does not match the official {official_id!r}")
    dupes = validation.find_duplicates(funding.get("donors", []), key_fn=lambda d: d["name"])
    problems.extend(f"{official_id}/funding.json: duplicate donor '{d}'" for d in dupes)
    for donor in funding.get("donors", []):
        for c in donor.get("contributions", []):
            if c.get("source_url") and not validation.is_valid_url(c["source_url"], validation.ALLOWED_SOURCE_DOMAINS):
                problems.append(f"{official_id}/funding.json: donor '{donor['name']}' has an untrusted source_url")
    return problems


def record_payload_problems(official_id, record) -> list:
    """Schema and semantic checks for one parsed record.json (shared by
    validate_all() and the build-time snapshot check)."""
    problems = [f"{official_id}/record.json: {p}" for p in validation.validate_schema(record, schemas.get("record"))]
    if isinstance(record, dict) and "official_id" in record and record["official_id"] != official_id:
        problems.append(
            f"{official_id}/record.json: official_id {record['official_id']!r} does not match the official {official_id!r}"
        )
    dupes = validation.find_duplicates(record.get("items", []), key_fn=lambda i: i.get("council_file"))
    problems.extend(f"{official_id}/record.json: duplicate council_file '{d}'" for d in dupes)
    for item in record.get("items", []):
        if not validation.is_valid_record_id(item.get("council_file", "")):
            problems.append(f"{official_id}/record.json: invalid council_file '{item.get('council_file')}'")
        if item.get("source_url") and not validation.is_valid_url(item["source_url"], validation.ALLOWED_SOURCE_DOMAINS):
            problems.append(f"{official_id}/record.json: item {item.get('council_file')} has an untrusted source_url")
    return problems


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
            problems.extend(funding_payload_problems(official_id, funding))

        if not record_path.exists():
            problems.append(f"{official_id}: missing record.json")
        else:
            record = json.loads(record_path.read_text())
            problems.extend(record_payload_problems(official_id, record))

    problems.extend(validate_freshness_file(FRESHNESS_PATH, reg.official_ids(officials)))

    return problems


# --- effective-snapshot checks (build-time; Step 4C) --------------------------
#
# Used by build_all.py before anything is published. They are deliberately
# NOT part of validate_all() / this script's CLI, whose behavior is unchanged.
# effective_paths maps (official_id, dataset) -> the file that would be
# served after publication: the copy staged by this run, or the currently
# published copy that is retained.

SNAPSHOT_DATASETS = ("funding", "record")


def read_json_file(path: Path):
    """(data, problem): parse a JSON file without raising for OSError,
    UnicodeDecodeError or malformed JSON."""
    try:
        raw = Path(path).read_bytes()
    except OSError as exc:
        return None, f"could not be read: {exc}"
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        return None, f"not valid UTF-8: {exc}"
    try:
        return json.loads(text), None
    except json.JSONDecodeError as exc:
        return None, f"not valid JSON: {exc}"


def load_snapshot_outputs(officials, effective_paths):
    """(payloads, problems): parse every required per-official output.
    payloads maps (official_id, dataset) -> parsed JSON for files that parsed."""
    payloads, problems = {}, []
    for official in officials:
        official_id = official.get("id")
        for dataset in SNAPSHOT_DATASETS:
            path = effective_paths.get((official_id, dataset))
            if path is None or not Path(path).is_file():
                problems.append(f"{official_id}: missing {dataset}.json")
                continue
            data, problem = read_json_file(path)
            if problem:
                problems.append(f"{official_id}/{dataset}.json: {problem}")
            elif not isinstance(data, dict):
                problems.append(f"{official_id}/{dataset}.json: top level must be an object")
            else:
                payloads[(official_id, dataset)] = data
    return payloads, problems


def validate_snapshot(officials, effective_paths, freshness) -> list:
    """The same schema and semantic checks validate_all() applies to the
    committed tree, applied to the effective snapshot instead: every
    required output (staged or retained) plus the new freshness payload."""
    payloads, problems = load_snapshot_outputs(officials, effective_paths)
    for (official_id, dataset), data in sorted(payloads.items()):
        if dataset == "funding":
            problems.extend(funding_payload_problems(official_id, data))
        else:
            problems.extend(record_payload_problems(official_id, data))
    problems.extend(validate_freshness(freshness, reg.official_ids(officials), require_all=True))
    return problems


def validate_snapshot_claims(officials, freshness, previous, staged, effective_paths, target_ids=None) -> list:
    """Check that freshness describes exactly the effective snapshot.

    staged: set of (official_id, dataset) outputs written by this run.
    previous: the previous v2 snapshot (after any v1 migration) or None.
    target_ids: the subset being rebuilt, or None/empty for every official.

    - freshness covers exactly the ids in officials.json;
    - every official has both outputs; a dataset with neither a staged nor a
      previously published file is NO_PUBLISHABLE_FILE (first-ever failure
      is fatal: nothing claims nonexistent previous data is served);
    - targeted: status ok <=> an output was staged by this run; failed or
      skipped retains the published file and needs a prior last_success_at;
    - untargeted (subset runs): nothing staged and the entry is the
      previous entry verbatim (an older ok status is legitimate);
    - counts match the effective file (displayed_donor_count / item_count);
    - BUILD_FAILED_PREVIOUS_DATA_SERVED only with a retained file.
    """
    problems = []
    ids = reg.official_ids(officials)
    entries = (freshness or {}).get("officials")
    if not isinstance(entries, dict):
        return ["freshness: officials must be an object"]
    if set(entries) != set(ids):
        problems.append(
            f"freshness ids do not match officials.json: missing {sorted(set(ids) - set(entries))}, "
            f"unknown {sorted(set(entries) - set(ids))}"
        )
    stray = sorted(f"{o}/{d}" for o, d in staged if o not in set(ids) or d not in SNAPSHOT_DATASETS)
    if stray:
        problems.append(f"staged outputs for unknown officials/datasets: {stray}")
    prev_entries = (previous or {}).get("officials") or {}
    payloads, _ = load_snapshot_outputs(officials, effective_paths)  # unreadable files are reported by validate_snapshot()
    for official_id in ids:
        targeted = not target_ids or official_id in target_ids
        for dataset in SNAPSHOT_DATASETS:
            where = f"{official_id}.{dataset}"
            entry = (entries.get(official_id) or {}).get(dataset)
            if not isinstance(entry, dict):
                problems.append(f"{where}: no freshness entry")
                continue
            status = entry.get("status")
            is_staged = (official_id, dataset) in staged
            path = effective_paths.get((official_id, dataset))
            exists = path is not None and Path(path).is_file()
            codes = entry.get("warning_codes") or []
            if not exists:
                problems.append(
                    f"{where}: NO_PUBLISHABLE_FILE: status {status!r} with no output staged by this run "
                    "and no previously published file"
                )
            if targeted:
                if status == "ok" and not is_staged:
                    problems.append(f"{where}: status 'ok' requires an output staged by this run")
                if status in ("failed", "skipped"):
                    if is_staged:
                        problems.append(f"{where}: status {status!r} but this run staged an output")
                    if exists and entry.get("last_success_at") is None:
                        problems.append(f"{where}: retains a published file but last_success_at is null")
            else:
                if is_staged:
                    problems.append(f"{where}: untargeted official has a staged output")
                prev = (prev_entries.get(official_id) or {}).get(dataset)
                if entry != prev:
                    problems.append(f"{where}: untargeted entry differs from the previous snapshot")
            if "BUILD_FAILED_PREVIOUS_DATA_SERVED" in codes and (is_staged or not exists):
                problems.append(f"{where}: BUILD_FAILED_PREVIOUS_DATA_SERVED without a retained published file")
            data = payloads.get((official_id, dataset))
            if data is not None:
                if dataset == "funding":
                    actual = len(data.get("donors") or [])
                    if entry.get("displayed_donor_count") != actual:
                        problems.append(
                            f"{where}: displayed_donor_count {entry.get('displayed_donor_count')!r} != {actual} donor(s) in the file"
                        )
                else:
                    actual = len(data.get("items") or [])
                    if entry.get("item_count") != actual:
                        problems.append(f"{where}: item_count {entry.get('item_count')!r} != {actual} item(s) in the file")
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
