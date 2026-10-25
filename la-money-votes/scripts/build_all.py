#!/usr/bin/env python3
"""la-money-votes — build_all.py

Deterministic orchestrator: reads the officials registry and runs both
builders (funding, record) for every configured official.

Guarantees:
- One official's expected failure never blocks another's — builders return
  a "failed"/"skipped" status for a per-official problem, recorded
  independently (see scripts/pipeline/report.py). An unexpected exception
  from either builder is fatal for the whole run (Step 4C): nothing may be
  published from it.
- Produces data/build_report.json (gitignored — see .gitignore), a
  machine-readable summary consumed by the CI workflow (to fail the job) and
  by the scheduled refresh workflow (to compose the data-refresh PR body).
- Fails the overall build (non-zero exit) if any required official's data or
  validation failed. A dataset that's simply unavailable this run (e.g. the
  live API is down and there's no cache yet) is recorded as a failure too --
  see "known limitations" in README for what "required" means here.
- Publishes through one path, build_snapshot() (Step 4C; CONTRACT.md):
  every output is staged under data/raw/.publish/<run_id>/staging/, the
  whole effective snapshot is validated, then published with verified
  backups and a journal (freshness.json last), re-verified on the live tree
  and rolled back on any failure. run() only builds and never publishes.
- Writes data/freshness.json (committed, schema_version 2.0) describing, per
  official and dataset, the most recent build attempt and the currently
  published output. See CONTRACT.md "freshness.json v2" for field semantics.
- Runs preflight() before any builder: the previous freshness.json (a valid
  v1 file is migrated in memory), --official arguments, subset-run base
  snapshot and every human-supplied reviewed_through are checked first, and
  any problem stops the build before anything is staged or published.
- Holds an exclusive lock (data/raw/.build.lock) from preflight through
  publication verification and the report write; a second run exits 75.

Usage:
    python3 scripts/build_all.py
    python3 scripts/build_all.py --fetch-socrata
    python3 scripts/build_all.py --official mayor-bass --official cd1-official
    python3 scripts/build_all.py --report-path /tmp/build_report.json
    python3 scripts/build_all.py --skip-freshness          # dry run: publish nothing
    python3 scripts/build_all.py --run-id r1 && \\
        python3 scripts/build_all.py --verify-run r1          # read-only check
    python3 scripts/build_all.py --recover                 # after an interrupted run
"""

from __future__ import annotations

import argparse
import copy
import importlib
import json
import os
import sys
import tempfile
import traceback
from datetime import date, datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pipeline import atomic_io, publish, registry as reg, report as report_mod

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_REPORT_PATH = ROOT / "data" / "build_report.json"
FRESHNESS_PATH = ROOT / "data" / "freshness.json"

build_funding = importlib.import_module("build_funding")
build_record = importlib.import_module("build_record")
validate_data = importlib.import_module("validate_data")
socrata = build_funding.socrata


# --- freshness.json v2 helpers -------------------------------------------
#
# Core rule: `status`, `attempted_at` and `warning_codes` describe the most
# recent attempt; every other field describes the output that is currently
# published. A successful build derives those fields from the inputs it
# actually used; a failed or skipped build carries them forward unchanged
# from the previous snapshot (the previous output is still what is served).
# No date is ever invented: unknown values stay null.

REVIEW_ABSENT = "absent"  # fixture has no reviewed_through key: carry the previous value
REVIEW_REVOKED = "revoked"  # explicit null: clear any previous value
REVIEW_SUPPLIED = "supplied"  # valid YYYY-MM-DD on or before the run's UTC date


def _utc_ts(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).replace(microsecond=0).isoformat()


def latest_reporting_period_end(rows, run_date: str):
    """Latest valid 'Period End Date' across ALL matched rows (every
    contribution type) actually used by this build, measured before donor
    aggregation and before the top-30 display cap. Unparseable values and
    values after the run date are ignored rather than published. Returns
    None if no row has a usable value."""
    best = None
    for row in rows or []:
        end = build_funding.parse_date(row.get(build_funding.COL_PERIOD_END))
        if end and end <= run_date and (best is None or end > best):
            best = end
    return best


def read_review_attestations(sources_registry, official_ids, run_date: str):
    """Read the optional, human-supplied top-level 'reviewed_through' from
    every official's record fixture. Returns ({official_id: (state, value)},
    problems). Any malformed, impossible or future value is a problem: the
    caller must fail before writing anything. A fixture that is missing or
    unreadable is treated as absent here; build_record reports it."""
    out, problems = {}, []
    for official_id in sorted(official_ids):
        entry = sources_registry["officials"].get(official_id, {})
        fixture = (entry.get("record") or {}).get("fixture")
        state = (REVIEW_ABSENT, None)
        if fixture:
            try:
                data = json.loads((ROOT / fixture).read_text())
            except (OSError, ValueError):
                data = None
            if isinstance(data, dict) and "reviewed_through" in data:
                value = data["reviewed_through"]
                if value is None:
                    state = (REVIEW_REVOKED, None)
                elif not isinstance(value, str) or not build_funding.validation.is_valid_date(value):
                    problems.append(f"{fixture}: reviewed_through {value!r} is not a valid YYYY-MM-DD date")
                elif value > run_date:
                    problems.append(f"{fixture}: reviewed_through {value} is after the build's UTC date {run_date}")
                else:
                    state = (REVIEW_SUPPLIED, value)
        out[official_id] = state
    return out, problems


def _sorted_codes(codes) -> list:
    return sorted(set(codes))


def migrate_v1_to_v2(v1: dict) -> dict:
    """Conservatively migrate a valid schema-v1 freshness.json to v2.

    Preserved from v1: status (same ok/failed/skipped meaning), last_success_at,
    donor_count (as displayed_donor_count and the legacy donor_count alias)
    and record item_count. attempted_at and generated_at are set to v1's
    generated_at, the time that v1 snapshot was written. Everything v1 never
    recorded is initialized as unknown: funding source_type "unknown",
    source_retrieved_at, latest_reporting_period_end, matched_row_count and
    reviewed_through all null, with the matching *_UNKNOWN / *_MISSING
    warning codes (SOURCE_TYPE_UNKNOWN for the source type). Raises ValueError unless v1 passes validate_freshness_v1.
    """
    problems = validate_data.validate_freshness_v1(v1)
    if problems:
        raise ValueError("not a valid v1 freshness.json: " + "; ".join(problems))
    attempted_at = validate_data.parse_utc_timestamp(v1["generated_at"]).isoformat()
    out = {"schema_version": validate_data.FRESHNESS_SCHEMA_VERSION, "generated_at": attempted_at, "officials": {}}
    for official_id, datasets in v1["officials"].items():
        f, r = datasets["funding"], datasets["record"]
        f_codes = ["LATEST_REPORTING_PERIOD_UNKNOWN", "SOURCE_RETRIEVED_AT_UNKNOWN", "SOURCE_TYPE_UNKNOWN"]
        if f["last_success_at"] and f["donor_count"] == 0:
            f_codes.append("ZERO_ITEMS")
        r_codes = ["REVIEW_DATE_MISSING"]
        if r["last_success_at"] and r["item_count"] == 0:
            r_codes.append("ZERO_ITEMS")
        out["officials"][official_id] = {
            "funding": {
                "source_type": "unknown",
                "status": f["status"],
                "attempted_at": attempted_at,
                "last_success_at": f["last_success_at"],
                "source_retrieved_at": None,
                "latest_reporting_period_end": None,
                "displayed_donor_count": f["donor_count"],
                "matched_row_count": None,
                "donor_count": f["donor_count"],
                "warning_codes": _sorted_codes(f_codes),
            },
            "record": {
                "source_type": "manual_curated",
                "status": r["status"],
                "attempted_at": attempted_at,
                "last_success_at": r["last_success_at"],
                "reviewed_through": None,
                "item_count": r["item_count"],
                "warning_codes": _sorted_codes(r_codes),
            },
        }
    return out


def load_previous_freshness(path: Path, official_ids):
    """Read and validate the previous snapshot. Returns (data, problems, kind)
    with kind one of "missing", "v2", "v1-migrated".

    Missing file -> (None, [], "missing"). A valid v1 file is migrated in
    memory (migrate_v1_to_v2) and the result validated as complete v2. A
    malformed, partially v1-like, unknown-version or contract-violating file
    -> (None, problems, ...): the caller must stop before writing anything.
    The snapshot is validated against its own official set; officials no
    longer in officials.json are then dropped (officials.json is
    authoritative)."""
    path = Path(path)
    if not path.exists():
        return None, [], "missing"
    try:
        raw = path.read_bytes()
    except OSError as exc:  # permissions, removed after exists(), I/O errors
        return None, [f"freshness.json: could not be read: {exc}"], "invalid"
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        return None, [f"freshness.json: not valid UTF-8: {exc}"], "invalid"
    data, problems = validate_data.parse_freshness_text(text)
    if problems:
        return None, problems, "invalid"
    if not isinstance(data, dict):
        return None, ["freshness.json: top level must be an object"], "invalid"
    kind = "v2"
    if "schema_version" not in data:
        v1_problems = validate_data.validate_freshness_v1(data)
        if v1_problems:
            return None, v1_problems, "invalid"
        data = migrate_v1_to_v2(data)
        kind = "v1-migrated"
    own_ids = set(data["officials"]) if isinstance(data.get("officials"), dict) else set()
    problems = validate_data.validate_freshness(data, own_ids, require_all=True)
    if problems:
        return None, problems, "invalid"
    current = set(official_ids)
    data = copy.deepcopy(data)
    data["officials"] = {oid: v for oid, v in data["officials"].items() if oid in current}
    return data, [], kind


def _check_freshness_config() -> list:
    """The generator and the committed schema must agree on the version."""
    try:
        schema = validate_data.schemas.get("freshness")
        enum = schema["properties"]["schema_version"]["enum"]
    except Exception as exc:  # noqa: BLE001 - any failure here is a config problem
        return [f"freshness schema could not be loaded: {exc}"]
    if enum != [validate_data.FRESHNESS_SCHEMA_VERSION]:
        return [f"freshness schema version {enum} does not match generator {validate_data.FRESHNESS_SCHEMA_VERSION!r}"]
    return []


def preflight(officials, sources_registry, target_ids, freshness_path, run_date):
    """Every check that can fail without touching data, run before any
    builder can write funding.json, record.json or freshness.json. Returns
    (previous_snapshot, review_attestations, problems)."""
    ids = reg.official_ids(officials)
    problems = list(_check_freshness_config())
    if target_ids:
        unknown = sorted(set(target_ids) - ids)
        if unknown:
            problems.append(f"--official: unknown official id(s) {unknown}")
    previous, prev_problems, _kind = load_previous_freshness(freshness_path, ids)
    problems.extend(f"previous freshness.json is invalid: {p}" for p in prev_problems)
    if target_ids and not prev_problems:
        missing = sorted(ids - set((previous or {}).get("officials", {})))
        if previous is None or missing:
            problems.append(
                "--official needs a valid, complete previous freshness.json to preserve untargeted officials; "
                "run a full build first to initialize freshness"
                + (f" (missing: {missing})" if previous is not None else "")
            )
    reviews, review_problems = read_review_attestations(sources_registry, ids, run_date)
    problems.extend(review_problems)
    return previous, reviews, problems


def _funding_entry(*, prev, status, attempted_at, run_date, attempt_source_type, source_loaded,
                   committees, matched_rows, displayed_count, contributions, statements):
    """Compute one official's v2 funding entry. See the module-level rule.

    contributions / statements: the socrata.FetchOutcome of this run's two
    Socrata requests (None for a CSV build)."""
    if attempt_source_type not in ("automated_api", "automated_csv"):
        # "unknown" is reachable only through migrate_v1_to_v2; a v2 build
        # always knows which source it attempted.
        raise ValueError(f"invalid attempt source_type {attempt_source_type!r}")
    prev = prev or {}
    codes = []
    contrib_cached = contributions is not None and contributions.origin in (socrata.ORIGIN_CACHE_FALLBACK, socrata.ORIGIN_CACHE_ONLY)
    stmt_cached = statements is not None and statements.origin in (socrata.ORIGIN_CACHE_FALLBACK, socrata.ORIGIN_CACHE_ONLY)
    if not source_loaded:
        codes.append("SOURCE_UNAVAILABLE")
    else:
        if contrib_cached:
            codes.append("SOURCE_CACHE_FALLBACK")
        if stmt_cached:
            codes.append("SUPPORTING_SOURCE_CACHE_FALLBACK")
    if not committees:
        codes.append("NO_COMMITTEE_CONFIGURED")
    elif source_loaded and not matched_rows:
        codes.append("NO_ROWS_MATCHED")

    if status == "ok":
        # Everything about the published file comes from the rows this build
        # used -- never from an unrelated previous snapshot.
        source_type = attempt_source_type
        last_success_at = run_date
        displayed = displayed_count
        matched = len(matched_rows or [])
        period_end = latest_reporting_period_end(matched_rows, run_date)
        source_retrieved_at = None
        if attempt_source_type == "automated_api" and contributions is not None:
            ts = contributions.retrieved_at  # live time, or verified cache sidecar time
            parsed = validate_data.parse_utc_timestamp(ts) if ts else None
            if parsed is not None and parsed <= validate_data.parse_utc_timestamp(attempted_at):
                source_retrieved_at = ts
    else:
        # Failed or skipped: the previously published file is still served,
        # so everything describing it is carried forward unchanged.
        # Carry the published file's source type. An official with no
        # previous entry has no published funding file, so it takes the
        # attempted type; "unknown" is never introduced here.
        source_type = prev.get("source_type", attempt_source_type)
        last_success_at = prev.get("last_success_at")
        source_retrieved_at = prev.get("source_retrieved_at")
        period_end = prev.get("latest_reporting_period_end")
        displayed = prev.get("displayed_donor_count", 0)
        matched = prev.get("matched_row_count")
        if status == "failed" and last_success_at:
            codes.append("BUILD_FAILED_PREVIOUS_DATA_SERVED")

    if period_end is None:
        codes.append("LATEST_REPORTING_PERIOD_UNKNOWN")
    if source_retrieved_at is None:
        codes.append("SOURCE_RETRIEVED_AT_UNKNOWN")
    if source_type == "unknown":
        codes.append("SOURCE_TYPE_UNKNOWN")
    if last_success_at and displayed == 0:
        codes.append("ZERO_ITEMS")
    if source_type == "automated_api":
        codes.append("EMPLOYER_OCCUPATION_UNAVAILABLE")
    return {
        "source_type": source_type,
        "status": status,
        "attempted_at": attempted_at,
        "last_success_at": last_success_at,
        "source_retrieved_at": source_retrieved_at,
        "latest_reporting_period_end": period_end,
        "displayed_donor_count": displayed,
        "matched_row_count": matched,
        "donor_count": displayed,
        "warning_codes": _sorted_codes(codes),
    }


def _record_entry(*, prev, status, attempted_at, run_date, item_count, review, fixture_missing):
    """review: (state, value) from read_review_attestations. An explicit
    null always revokes; a supplied date applies only when this build
    succeeded (it describes the published record.json); absent carries."""
    prev = prev or {}
    codes = []
    state, value = review
    if status == "ok":
        last_success_at = run_date
        count = item_count
    else:
        last_success_at = prev.get("last_success_at")
        count = prev.get("item_count", 0)
        if fixture_missing:
            codes.append("SOURCE_UNAVAILABLE")
        if status == "failed" and last_success_at:
            codes.append("BUILD_FAILED_PREVIOUS_DATA_SERVED")
    if state == REVIEW_REVOKED:
        reviewed = None
    elif state == REVIEW_SUPPLIED and status == "ok":
        reviewed = value
    else:
        reviewed = prev.get("reviewed_through")
    if reviewed is None:
        codes.append("REVIEW_DATE_MISSING")
    if last_success_at and count == 0:
        codes.append("ZERO_ITEMS")
    return {
        "source_type": "manual_curated",
        "status": status,
        "attempted_at": attempted_at,
        "last_success_at": last_success_at,
        "reviewed_through": reviewed,
        "item_count": count,
        "warning_codes": _sorted_codes(codes),
    }


def run(
    target_ids=None,
    fetch_socrata=False,
    csv_path=None,
    statements_csv=None,
    use_cache_only=False,
    officials=None,
    sources_registry=None,
    freshness_path=None,
    now=None,
    out_root=None,
    context=None,
):
    """officials / sources_registry may be passed in directly (already-loaded
    lists/dicts) instead of read from disk -- this is what the test suite
    uses to run the real orchestration logic against fixture data without
    touching data/officials.json or data/sources/registry.json.

    freshness_path: the previous freshness.json to carry values forward from
    (default FRESHNESS_PATH; it is only read here, main() writes). now: an
    aware datetime used for generated_at/attempted_at/last_success_at (tests
    pin it; production leaves it None for the real UTC clock).

    Order: cross-reference validation and preflight() run first; any problem
    there is fatal and returns before any builder runs, so no generated file
    is modified.

    run() never publishes. out_root: where per-official outputs are written;
    stage_snapshot() passes its staging directory. Without out_root, outputs
    go to a temporary directory that is discarded (callers that only need the
    report and freshness payload). Publication happens only through
    build_snapshot(). context: an
    optional dict that receives the loaded officials, the previous snapshot
    (after any v1 migration) and target_ids, for the snapshot claim checks.

    Builder failures: an expected "failed"/"skipped" status returned by a
    builder is recorded per official and the run continues (partial success).
    An unexpected exception raised by either builder is fatal: the run stops
    and returns no freshness, so nothing may be published."""
    if out_root is None:
        with tempfile.TemporaryDirectory(prefix="build-all-discard-") as tmp:
            return run(
                target_ids=target_ids,
                fetch_socrata=fetch_socrata,
                csv_path=csv_path,
                statements_csv=statements_csv,
                use_cache_only=use_cache_only,
                officials=officials,
                sources_registry=sources_registry,
                freshness_path=freshness_path,
                now=now,
                out_root=Path(tmp) / "officials",
                context=context,
            )
    if officials is None:
        officials = reg.load_officials()
    if sources_registry is None:
        sources_registry = reg.load_registry()
    if freshness_path is None:
        freshness_path = FRESHNESS_PATH

    build_report = report_mod.BuildReport()
    socrata.reset_fetch_outcomes()
    if context is not None:
        context.update(officials=officials, previous=None, target_ids=target_ids)

    cross_ref_problems = reg.validate_cross_reference(officials, sources_registry)
    if cross_ref_problems:
        for p in cross_ref_problems:
            build_report.add_fatal(p)
        return build_report, {}

    preflight_moment = now or datetime.now(timezone.utc)
    previous, reviews, preflight_problems = preflight(
        officials, sources_registry, target_ids, freshness_path,
        preflight_moment.astimezone(timezone.utc).date().isoformat(),
    )
    if preflight_problems:
        for p in preflight_problems:
            build_report.add_fatal(f"preflight: {p}")
        return build_report, {}
    if context is not None:
        context["previous"] = previous

    today = date.today().isoformat()
    committees_by_official = {
        oid: entry["funding"]["committees"] for oid, entry in sources_registry["officials"].items()
    }

    # --- funding: load all rows once, up front, so a network/CSV problem is
    # a single fatal error rather than N confusing per-official failures.
    # Each Socrata outcome is read immediately after its own request. ---
    source_loaded = True
    contributions_outcome = statements_outcome = None
    try:
        if fetch_socrata:
            try:
                rows_by_official = build_funding.load_rows_by_official_from_api(
                    committees_by_official, use_cache_only=use_cache_only
                )
            finally:
                contributions_outcome = socrata.get_fetch_outcome(build_funding.CONTRIBUTIONS_RESOURCE_ID)
            try:
                api_statements = socrata.fetch_dataset(
                    build_funding.STATEMENTS_RESOURCE_ID,
                    cache_path=build_funding.STATEMENTS_CACHE,
                    use_cache_only=use_cache_only,
                )
            finally:
                statements_outcome = socrata.get_fetch_outcome(build_funding.STATEMENTS_RESOURCE_ID)
            statement_links = build_funding.load_statement_links_from_rows(api_statements)
        else:
            path = Path(csv_path) if csv_path else build_funding.DEFAULT_CSV
            if not path.exists():
                build_report.add_unavailable_source(
                    f"funding: contributions CSV not found at {path} — funding.json builds skipped for all officials"
                )
                rows_by_official = {}
                statement_links = {}
                source_loaded = False
            else:
                rows_by_official = build_funding.load_rows_by_official_from_csv(path, committees_by_official)
                statement_links = build_funding.load_statement_links_from_csv(
                    Path(statements_csv) if statements_csv else build_funding.DEFAULT_STATEMENTS_CSV
                )
    except socrata.SourceUnavailable as exc:
        build_report.add_unavailable_source(f"funding: Socrata fetch failed and no cache available: {exc}")
        rows_by_official = {}
        statement_links = {}
        source_loaded = False

    # Snapshot time is taken after the source fetch so source_retrieved_at
    # can never be later than generated_at.
    moment = now or datetime.now(timezone.utc)
    generated_at = _utc_ts(moment)
    run_date = moment.astimezone(timezone.utc).date().isoformat()
    attempt_source_type = "automated_api" if fetch_socrata else "automated_csv"
    prev_officials = (previous or {}).get("officials", {})

    freshness = {
        "schema_version": validate_data.FRESHNESS_SCHEMA_VERSION,
        "generated_at": generated_at,
        "officials": {},
    }

    for official in officials:
        official_id = official.get("id")
        if target_ids and official_id not in target_ids:
            # Untargeted on a subset run: keep its previous entry verbatim
            # (preflight guarantees one exists).
            freshness["officials"][official_id] = copy.deepcopy(prev_officials[official_id])
            continue
        prev_entry = prev_officials.get(official_id, {})
        entry = sources_registry["officials"].get(official_id, {})
        freshness["officials"][official_id] = {}

        # funding
        if rows_by_official:
            try:
                status, count, problems, notes = build_funding.build_funding_for_official(
                    official, rows_by_official, sources_registry, statement_links, today, today, out_root=out_root
                )
            except Exception as exc:  # noqa: BLE001 - unexpected builder error: abort publication
                build_report.add_fatal(f"{official_id}: funding builder raised unexpectedly: {type(exc).__name__}: {exc}")
                return build_report, {}
        else:
            status, count, problems, notes = "skipped", 0, [], []
        build_report.add(report_mod.OfficialResult(official_id, "funding", status, count, problems, notes))
        freshness["officials"][official_id]["funding"] = _funding_entry(
            prev=prev_entry.get("funding"),
            status=status,
            attempted_at=generated_at,
            run_date=run_date,
            attempt_source_type=attempt_source_type,
            source_loaded=source_loaded,
            committees=(entry.get("funding") or {}).get("committees") or [],
            matched_rows=rows_by_official.get(official_id, []) if source_loaded else None,
            displayed_count=count,
            contributions=contributions_outcome,
            statements=statements_outcome,
        )

        # record — an expected failure (bad fixture, validation problem) is a
        # returned "failed" status; an unexpected exception aborts the run.
        try:
            r_status, r_count, r_problems, r_notes = build_record.build_record_for_official(
                official_id, sources_registry, today, out_root=out_root
            )
        except Exception as exc:  # noqa: BLE001 - unexpected builder error: abort publication
            build_report.add_fatal(f"{official_id}: record builder raised unexpectedly: {type(exc).__name__}: {exc}")
            return build_report, {}
        fixture_rel = (entry.get("record") or {}).get("fixture")
        build_report.add(report_mod.OfficialResult(official_id, "record", r_status, r_count, r_problems, r_notes))
        freshness["officials"][official_id]["record"] = _record_entry(
            prev=prev_entry.get("record"),
            status=r_status,
            attempted_at=generated_at,
            run_date=run_date,
            item_count=r_count,
            review=reviews.get(official_id, (REVIEW_ABSENT, None)),
            fixture_missing=bool(fixture_rel) and not (ROOT / fixture_rel).exists(),
        )

    return build_report, freshness


# --- staging and effective-snapshot validation (Step 4C) ---------------------

STAGED_FRESHNESS_NAME = "freshness.json"


class StagedSnapshot:
    """The outcome of stage_snapshot(): what a publication would serve.

    stage_root: staging directory (officials/<id>/{funding,record}.json and
    freshness.json); staged: (official_id, dataset) outputs written by this
    run; effective_paths: (official_id, dataset) -> the file that would be
    served (staged copy, else the retained published copy); freshness: the
    staged freshness payload as re-read from disk; problems: every
    effective-snapshot problem (also recorded as fatal on the report)."""

    def __init__(self, stage_root, staged, effective_paths, freshness, problems, officials=None, previous=None, target_ids=None):
        self.stage_root = stage_root
        self.staged = staged
        self.effective_paths = effective_paths
        self.freshness = freshness
        self.problems = problems
        self.officials = officials
        self.previous = previous
        self.target_ids = target_ids

    @property
    def ok(self) -> bool:
        return not self.problems


def published_output_path(official_id, dataset) -> Path:
    return ROOT / "data" / "officials" / official_id / f"{dataset}.json"


def _staged_outputs(officials_root: Path):
    """(staged, problems): every file under the staging officials/ tree. Only
    <id>/funding.json and <id>/record.json are expected; anything else is a
    problem (claims checks then reject unknown ids/datasets)."""
    staged, problems = set(), []
    if not officials_root.exists():
        return staged, problems
    for path in sorted(officials_root.rglob("*")):
        if path.is_dir():
            continue
        rel = path.relative_to(officials_root)
        if len(rel.parts) == 2 and rel.parts[1] in ("funding.json", "record.json") and not path.is_symlink():
            staged.add((rel.parts[0], rel.parts[1][: -len(".json")]))
        else:
            problems.append(f"unexpected file in staging: officials/{rel.as_posix()}")
    return staged, problems


def stage_snapshot(stage_root, **run_kwargs):
    """Build every output into stage_root and validate the effective snapshot.

    Nothing under data/officials or data/freshness.json is modified here.
    Returns (build_report, StagedSnapshot or None). None means a fatal error
    stopped the run before a snapshot could be composed. Effective-snapshot
    problems are added to build_report as fatal errors, so build_report.ok is
    False whenever the snapshot must not be published."""
    stage_root = Path(stage_root)
    officials_root = stage_root / "officials"
    officials_root.mkdir(parents=True, exist_ok=True)
    context = {}
    build_report, freshness = run(out_root=officials_root, context=context, **run_kwargs)
    if build_report.fatal_errors or not freshness:
        return build_report, None

    officials = context["officials"]
    staged, problems = _staged_outputs(officials_root)

    # Re-read the staged freshness from disk so the check covers the bytes
    # that would be published, not only the in-memory payload.
    staged_freshness_path = stage_root / STAGED_FRESHNESS_NAME
    atomic_io.atomic_write_json(staged_freshness_path, freshness)
    staged_freshness, read_problem = validate_data.read_json_file(staged_freshness_path)
    if read_problem:
        problems.append(f"staged freshness.json: {read_problem}")
        staged_freshness = {}

    effective_paths = {}
    for official in officials:
        official_id = official.get("id")
        for dataset in validate_data.SNAPSHOT_DATASETS:
            if (official_id, dataset) in staged:
                effective_paths[(official_id, dataset)] = officials_root / official_id / f"{dataset}.json"
            else:
                effective_paths[(official_id, dataset)] = published_output_path(official_id, dataset)

    problems.extend(validate_data.validate_snapshot(officials, effective_paths, staged_freshness))
    problems.extend(
        validate_data.validate_snapshot_claims(
            officials,
            staged_freshness,
            context.get("previous"),
            staged,
            effective_paths,
            context.get("target_ids"),
        )
    )
    for p in problems:
        build_report.add_fatal(f"snapshot: {p}")
    return build_report, StagedSnapshot(
        stage_root,
        staged,
        effective_paths,
        staged_freshness,
        problems,
        officials=officials,
        previous=context.get("previous"),
        target_ids=context.get("target_ids"),
    )



# --- orchestration: the single build/publication path (Step 4C) --------------


def data_root() -> Path:
    return ROOT / "data"


def live_output_paths(officials) -> dict:
    return {
        (o.get("id"), ds): published_output_path(o.get("id"), ds)
        for o in officials
        for ds in validate_data.SNAPSHOT_DATASETS
    }


def verify_live_snapshot(officials, manifest, replaced, previous, target_ids, check_untargeted=True) -> list:
    """Verify the live published tree: every file of the full snapshot
    manifest has its recorded hash, every live file passes the effective-
    snapshot and claim checks, and `replaced` ((official_id, dataset) set) is
    what this run published."""
    problems = []
    droot = data_root()
    expected = {publish.target_for(o.get("id"), ds) for o in officials for ds in validate_data.SNAPSHOT_DATASETS}
    expected.add(publish.FRESHNESS_TARGET)
    if set(manifest) != expected:
        problems.append(
            f"snapshot manifest does not cover exactly the required files: missing {sorted(expected - set(manifest))}, "
            f"unexpected {sorted(set(manifest) - expected)}"
        )
    for target, sha in sorted(manifest.items()):
        path = droot / target
        try:
            live = publish.sha256_file(path) if path.is_file() and not path.is_symlink() else None
        except OSError as exc:
            live = None
            problems.append(f"{target}: could not be read: {exc}")
        if live != sha:
            problems.append(f"{target}: live sha256 {live} != manifest {sha}")
    freshness, problem = validate_data.read_json_file(droot / publish.FRESHNESS_TARGET)
    if problem:
        return problems + [f"freshness.json: {problem}"]
    paths = live_output_paths(officials)
    problems.extend(validate_data.validate_snapshot(officials, paths, freshness))
    problems.extend(
        validate_data.validate_snapshot_claims(
            officials, freshness, previous if check_untargeted else freshness, replaced, paths, target_ids
        )
    )
    return problems


def _apply_publication(report, run_id, mode, target_ids, result=None, publication=None):
    report.run_id = run_id
    report.mode = mode
    report.target_ids = sorted(target_ids) if target_ids else None
    if result is not None:
        report.publication = result.publication
        report.journal_state = result.state
        report.replaced_files = result.replaced
        report.snapshot_manifest = result.manifest if result.publication == publish.PUB_VERIFIED else {}
        report.publication_problems = list(result.problems)
        report.publication_warnings = list(result.warnings)
    else:
        report.publication = publication


def build_snapshot(*, run_id=None, dry_run=False, on_report=None, **run_kwargs):
    """The one orchestration path used by the CLI and the test suite.

    Takes the build lock, refuses to run over an unresolved publication,
    stages and validates the effective snapshot, then (unless dry_run)
    publishes it through the journal. on_report(report) is called while the
    lock is still held, so only the lock owner ever writes a report.

    Returns (report, freshness). Raises publish.LockBusy if another run holds
    the lock (nothing is changed). An unexpected exception while loading
    sources or staging is recorded as fatal, reported via on_report, and
    re-raised after the staging area is removed."""
    run_id = run_id or publish.new_run_id()
    mode = "dry_run" if dry_run else "build"
    target_ids = run_kwargs.get("target_ids")
    droot = data_root()
    lock = publish.RunLock(droot, run_id, mode).acquire()
    try:
        pre = list(publish.validate_run_id(run_id))
        rdir = None
        if not pre:
            rdir = publish.run_dir(droot, run_id)
            pre.extend(publish.unresolved_runs(droot))
            if os.path.lexists(rdir):
                pre.append(f"a run directory for {run_id!r} already exists; run ids must be unique")
        if pre:
            report = report_mod.BuildReport()
            for p in pre:
                report.add_fatal(f"publication preflight: {p}")
            _apply_publication(report, run_id, mode, target_ids, publication=publish.PUB_NOT_ATTEMPTED)
            if on_report:
                on_report(report)
            return report, {}

        try:
            report, snap = stage_snapshot(rdir / "staging", **run_kwargs)
        except Exception as exc:  # noqa: BLE001 - owned diagnostics, then preserve the failure
            report = report_mod.BuildReport()
            report.add_fatal(f"build raised before publication: {type(exc).__name__}: {exc}")
            _apply_publication(report, run_id, mode, target_ids, publication=publish.PUB_NOT_ATTEMPTED)
            for p in publish.cleanup_run(rdir):
                report.publication_problems.append(f"cleanup: {p}")
            if on_report:
                on_report(report)
            raise
        freshness = snap.freshness if snap is not None else {}

        if dry_run or snap is None or not snap.ok or report.fatal_errors:
            publication = publish.PUB_DRY_RUN if dry_run else publish.PUB_NOT_ATTEMPTED
            _apply_publication(report, run_id, mode, target_ids, publication=publication)
            for p in publish.cleanup_run(rdir):
                report.publication_problems.append(f"cleanup: {p}")
        else:
            result = publish.publish_snapshot(
                snap,
                droot,
                rdir,
                run_id,
                verify=lambda manifest: verify_live_snapshot(
                    snap.officials, manifest, snap.staged, snap.previous, snap.target_ids
                ),
            )
            _apply_publication(report, run_id, mode, target_ids, result=result)
            if result.publication != publish.PUB_VERIFIED:
                report.add_fatal(f"publication {result.publication}: nothing from this run is published")
        if on_report:
            on_report(report)
        return report, freshness
    finally:
        lock.release()


def _print_report(report) -> None:
    print(report.summary_line())
    for result in report.results:
        marker = {"ok": "ok", "failed": "FAILED", "skipped": "skipped"}[result.status]
        print(f"  {result.official_id:20s} {result.builder:8s} {marker:8s} {result.record_count} record(s)")
        for p in result.problems:
            print(f"      - {p}")
    for note in report.unavailable_sources:
        print(f"  unavailable source: {note}")
    for err in report.fatal_errors:
        print(f"  fatal: {err}")
    for p in report.publication_problems:
        print(f"  publication: {p}")
    for w in report.publication_warnings:
        print(f"  warning: {w}")
    print(
        f"run {report.run_id} ({report.mode}): publication {report.publication}; "
        f"{len(report.replaced_files)} file(s) replaced, {len(report.snapshot_manifest)} in the snapshot manifest"
    )


def build_exit_code(report) -> int:
    if not report.ok or report.publication_warnings:
        return 1
    return 0 if report.publication in (publish.PUB_VERIFIED, publish.PUB_DRY_RUN) else 1


def verify_run(run_id: str, report_path: Path) -> list:
    """Read-only verification of a finished run (used by --verify-run). The
    report is never rewritten. Holds the lock so no publication can be in
    flight while the tree is checked."""
    problems = []
    droot = data_root()
    with publish.RunLock(droot, "verify", "verify"):
        problems.extend(publish.validate_run_id(run_id))
        data, problem = validate_data.read_json_file(Path(report_path))
        if problem:
            return problems + [f"report {report_path}: {problem}"]
        if not isinstance(data, dict):
            return problems + [f"report {report_path}: top level must be an object"]
        if data.get("run_id") != run_id:
            problems.append(f"report run_id {data.get('run_id')!r} does not match {run_id!r} (stale or foreign report)")
        if data.get("mode") != "build":
            problems.append(f"report mode {data.get('mode')!r} is not a publishing build")
        if data.get("publication") != publish.PUB_VERIFIED:
            problems.append(f"report publication is {data.get('publication')!r}, not 'verified'")
        manifest = data.get("snapshot_manifest")
        replaced = data.get("replaced_files")
        if not isinstance(manifest, dict) or not manifest:
            return problems + ["report has no snapshot_manifest"]
        if not isinstance(replaced, dict):
            return problems + ["report has no replaced_files"]
        for target, info in replaced.items():
            if not isinstance(info, dict) or manifest.get(target) != info.get("new_sha256"):
                problems.append(f"replaced file {target!r} does not match the snapshot manifest")
        if publish.FRESHNESS_TARGET not in replaced:
            problems.append("freshness.json was not replaced by this run")
        for p in publish.unresolved_runs(droot):
            if f"run {run_id!r} (state 'VERIFIED')" not in p:  # a VERIFIED, cleanup-incomplete run is still verified
                problems.append(p)
        officials = reg.load_officials()
        staged = set()
        for target in replaced:
            parts = target.split("/")
            if len(parts) == 3 and parts[0] == "officials" and parts[2] in ("funding.json", "record.json"):
                staged.add((parts[1], parts[2][: -len(".json")]))
        target_ids = set(data["target_ids"]) if data.get("target_ids") else None
        # Untargeted entries were proven equal to the previous snapshot when
        # the run published; freshness.json's manifest hash proves they are
        # unchanged since, so they are checked against the live file here.
        problems.extend(verify_live_snapshot(officials, manifest, staged, None, target_ids, check_untargeted=False))
    return problems


def recover() -> int:
    """--recover: resolve every interrupted or unverified publication, then
    exit. Never starts a build."""
    droot = data_root()
    with publish.RunLock(droot, "recover", "recover"):
        try:
            official_ids = reg.official_ids(reg.load_officials())
        except Exception as exc:  # noqa: BLE001 - cannot validate journals without it
            print(f"recover: cannot load officials.json, nothing changed: {exc}", file=sys.stderr)
            return 1
        results = publish.recover_all(droot, official_ids)
    if not results:
        print("recover: nothing to recover")
        return 0
    code = 0
    for name, outcome, problems in results:
        print(f"recover: {name}: {outcome}")
        for p in problems:
            print(f"    - {p}")
        if outcome not in ("cleaned", "rolled_back"):
            code = 1
    return code


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--official", action="append", help="only build this official id; may be repeated")
    parser.add_argument("--fetch-socrata", action="store_true", help="fetch funding data live instead of from a CSV")
    parser.add_argument("--csv-path", default=None, help="contributions CSV path (ignored with --fetch-socrata)")
    parser.add_argument("--statements-csv", default=None, help="statements-filed CSV path (ignored with --fetch-socrata)")
    parser.add_argument("--use-cache-only", action="store_true", help="never hit the network; read cache only")
    parser.add_argument("--report-path", default=str(DEFAULT_REPORT_PATH), help="where to write the build report JSON")
    parser.add_argument(
        "--markdown-path",
        default=None,
        help="also write the human-readable Markdown build report here (used by the scheduled refresh workflow to compose the PR body)",
    )
    parser.add_argument(
        "--skip-freshness",
        action="store_true",
        help="dry run: stage and validate everything, publish nothing (no data/officials or freshness.json change)",
    )
    parser.add_argument("--run-id", default=None, help="unique id for this run's staging/journal and report (default: generated)")
    parser.add_argument(
        "--verify-run",
        metavar="RUN_ID",
        default=None,
        help="read-only: verify that the report at --report-path is RUN_ID's verified publication and matches the live tree",
    )
    parser.add_argument(
        "--recover", action="store_true", help="resolve an interrupted publication (rollback or cleanup), then exit"
    )
    args = parser.parse_args()

    if args.recover:
        try:
            raise SystemExit(recover())
        except publish.LockBusy as exc:
            print(f"build_all: {exc}; recovery not started, nothing changed", file=sys.stderr)
            raise SystemExit(publish.LOCK_BUSY_EXIT)
        except publish.UnsafeLayout as exc:
            print(f"build_all: unsafe layout, recovery not started, nothing changed: {exc}", file=sys.stderr)
            raise SystemExit(1)

    if args.verify_run is not None:
        try:
            problems = verify_run(args.verify_run, Path(args.report_path))
        except publish.LockBusy as exc:
            print(f"build_all: {exc}; verification not started", file=sys.stderr)
            raise SystemExit(publish.LOCK_BUSY_EXIT)
        except publish.UnsafeLayout as exc:
            print(f"build_all: unsafe layout, verification not started: {exc}", file=sys.stderr)
            raise SystemExit(1)
        if problems:
            print(f"verify-run {args.verify_run}: FAILED")
            for p in problems:
                print(f"  - {p}")
            raise SystemExit(1)
        print(f"verify-run {args.verify_run}: verified publication matches the live snapshot")
        return

    def write_reports(report):
        report.write(Path(args.report_path))
        if args.markdown_path:
            Path(args.markdown_path).write_text(report.to_markdown() + "\n")
        _print_report(report)

    target_ids = set(args.official) if args.official else None
    officials = reg.load_officials()
    try:
        report, _ = build_snapshot(
            run_id=args.run_id,
            dry_run=args.skip_freshness,
            on_report=write_reports,
            target_ids=target_ids,
            fetch_socrata=args.fetch_socrata,
            csv_path=args.csv_path,
            statements_csv=args.statements_csv,
            use_cache_only=args.use_cache_only,
            officials=officials,
        )
    except publish.LockBusy as exc:
        print(f"build_all: {exc}; this run did not start and changed nothing", file=sys.stderr)
        raise SystemExit(publish.LOCK_BUSY_EXIT)
    except publish.UnsafeLayout as exc:
        print(f"build_all: unsafe layout, this run did not start and changed nothing: {exc}", file=sys.stderr)
        raise SystemExit(1)
    except Exception:  # noqa: BLE001 - already reported by build_snapshot(); keep the nonzero exit
        traceback.print_exc()
        raise SystemExit(1)
    code = build_exit_code(report)
    if code:
        raise SystemExit(code)

if __name__ == "__main__":
    main()
