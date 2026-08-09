#!/usr/bin/env python3
"""la-money-votes — build_all.py

Deterministic orchestrator: reads the officials registry and runs both
builders (funding, record) for every configured official.

Guarantees:
- One official's failure never blocks another's — each (official, builder)
  pair is wrapped in its own try/except and recorded independently (see
  scripts/pipeline/report.py). This is why build_funding.py / build_record.py
  never raise for a per-official problem; they return a status instead.
- Produces data/build_report.json (gitignored — see .gitignore), a
  machine-readable summary consumed by the CI workflow (to fail the job) and
  by the scheduled refresh workflow (to compose the data-refresh PR body).
- Fails the overall build (non-zero exit) if any required official's data or
  validation failed. A dataset that's simply unavailable this run (e.g. the
  live API is down and there's no cache yet) is recorded as a failure too --
  see "known limitations" in README for what "required" means here.
- Never overwrites previously-committed, valid JSON with partial or
  malformed output — build_funding.py / build_record.py's own
  write_if_valid() already enforces that per file; this script does not
  bypass it.
- Writes data/freshness.json (committed) summarizing when each official's
  data last built successfully and how many records it has, so the frontend
  or a maintainer can see at a glance how fresh the published data is.

Usage:
    python3 scripts/build_all.py
    python3 scripts/build_all.py --fetch-socrata
    python3 scripts/build_all.py --official mayor-bass --official cd1-official
    python3 scripts/build_all.py --report-path /tmp/build_report.json
"""

from __future__ import annotations

import argparse
import importlib
import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pipeline import atomic_io, registry as reg, report as report_mod

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_REPORT_PATH = ROOT / "data" / "build_report.json"
FRESHNESS_PATH = ROOT / "data" / "freshness.json"

build_funding = importlib.import_module("build_funding")
build_record = importlib.import_module("build_record")


def run(
    target_ids=None,
    fetch_socrata=False,
    csv_path=None,
    statements_csv=None,
    use_cache_only=False,
    officials=None,
    sources_registry=None,
):
    """officials / sources_registry may be passed in directly (already-loaded
    lists/dicts) instead of read from disk -- this is what the test suite
    uses to run the real orchestration logic against fixture data without
    touching data/officials.json or data/sources/registry.json."""
    if officials is None:
        officials = reg.load_officials()
    if sources_registry is None:
        sources_registry = reg.load_registry()

    build_report = report_mod.BuildReport()

    cross_ref_problems = reg.validate_cross_reference(officials, sources_registry)
    if cross_ref_problems:
        for p in cross_ref_problems:
            build_report.add_fatal(p)
        return build_report, {}

    today = date.today().isoformat()
    committees_by_official = {
        oid: entry["funding"]["committees"] for oid, entry in sources_registry["officials"].items()
    }

    # --- funding: load all rows once, up front, so a network/CSV problem is
    # a single fatal error rather than N confusing per-official failures ---
    try:
        if fetch_socrata:
            rows_by_official = build_funding.load_rows_by_official_from_api(
                committees_by_official, use_cache_only=use_cache_only
            )
            api_statements = build_funding.socrata.fetch_dataset(
                build_funding.STATEMENTS_RESOURCE_ID,
                cache_path=build_funding.STATEMENTS_CACHE,
                use_cache_only=use_cache_only,
            )
            statement_links = build_funding.load_statement_links_from_rows(api_statements)
        else:
            path = Path(csv_path) if csv_path else build_funding.DEFAULT_CSV
            if not path.exists():
                build_report.add_unavailable_source(
                    f"funding: contributions CSV not found at {path} — funding.json builds skipped for all officials"
                )
                rows_by_official = {}
                statement_links = {}
            else:
                rows_by_official = build_funding.load_rows_by_official_from_csv(path, committees_by_official)
                statement_links = build_funding.load_statement_links_from_csv(
                    Path(statements_csv) if statements_csv else build_funding.DEFAULT_STATEMENTS_CSV
                )
    except build_funding.socrata.SourceUnavailable as exc:
        build_report.add_unavailable_source(f"funding: Socrata fetch failed and no cache available: {exc}")
        rows_by_official = {}
        statement_links = {}

    freshness = {"generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "officials": {}}

    for official in officials:
        official_id = official.get("id")
        if target_ids and official_id not in target_ids:
            continue
        freshness["officials"][official_id] = {}

        # funding
        if rows_by_official:
            status, count, problems, notes = build_funding.build_funding_for_official(
                official, rows_by_official, sources_registry, statement_links, today, today
            )
        else:
            status, count, problems, notes = "skipped", 0, [], []
        build_report.add(report_mod.OfficialResult(official_id, "funding", status, count, problems, notes))
        freshness["officials"][official_id]["funding"] = {
            "status": status,
            "last_success_at": today if status == "ok" else None,
            "donor_count": count,
        }

        # record — independent try/except so a fixture bug for one official
        # never stops the rest of the build.
        try:
            r_status, r_count, r_problems, r_notes = build_record.build_record_for_official(
                official_id, sources_registry, today
            )
        except Exception as exc:  # noqa: BLE001 - isolate unexpected per-official failures
            r_status, r_count, r_problems, r_notes = "failed", 0, [f"unexpected error: {exc}"], []
        build_report.add(report_mod.OfficialResult(official_id, "record", r_status, r_count, r_problems, r_notes))
        freshness["officials"][official_id]["record"] = {
            "status": r_status,
            "last_success_at": today if r_status == "ok" else None,
            "item_count": r_count,
        }

    return build_report, freshness


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
    parser.add_argument("--skip-freshness", action="store_true", help="don't write data/freshness.json (used by tests)")
    args = parser.parse_args()

    target_ids = set(args.official) if args.official else None
    build_report, freshness = run(
        target_ids=target_ids,
        fetch_socrata=args.fetch_socrata,
        csv_path=args.csv_path,
        statements_csv=args.statements_csv,
        use_cache_only=args.use_cache_only,
    )

    build_report.write(Path(args.report_path))
    if args.markdown_path:
        Path(args.markdown_path).write_text(build_report.to_markdown() + "\n")
    print(build_report.summary_line())
    for result in build_report.results:
        marker = {"ok": "ok", "failed": "FAILED", "skipped": "skipped"}[result.status]
        print(f"  {result.official_id:20s} {result.builder:8s} {marker:8s} {result.record_count} record(s)")
        for p in result.problems:
            print(f"      - {p}")
    for note in build_report.unavailable_sources:
        print(f"  unavailable source: {note}")
    for err in build_report.fatal_errors:
        print(f"  fatal: {err}")

    # freshness.json always reflects reality, including per-official failures
    # -- unlike funding.json/record.json (which must never be partial), this
    # file's entire purpose is to honestly report what succeeded and what
    # didn't, so a fatal cross-reference error is the only thing that skips
    # it (there's nothing per-official to report in that case).
    if freshness and not args.skip_freshness and not build_report.fatal_errors:
        atomic_io.atomic_write_json(FRESHNESS_PATH, freshness)
        print(f"wrote {FRESHNESS_PATH.relative_to(ROOT)}")

    if not build_report.ok:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
