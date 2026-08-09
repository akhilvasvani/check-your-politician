#!/usr/bin/env python3
"""la-money-votes — build_funding.py

Writes data/officials/<id>/funding.json for one or more officials listed in
data/officials.json, per the schema frozen in CONTRACT.md (with additive
provenance/source fields — see CONTRACT.md "Additions").

Two ways to get input rows, in order of preference:

1. --fetch-socrata (recommended, used by the scheduled refresh workflow):
   pulls live from the LA Ethics Commission's public Socrata API —
   dataset m6g2-gc6c "City Campaign Contributions (and Misc. Increases to
   Cash)" and (for contributions[].source_url) br3a-db9a "City Campaign
   Statements Filed" — both unauthenticated, no API key required. Responses
   are cached under the gitignored data/raw/ so a flaky network doesn't
   block every rebuild, and a failed fetch falls back to that cache instead
   of failing the whole run.

2. --csv-path (offline/manual fallback, also what tests use): a locally
   downloaded CSV export of the same two datasets. Never committed to the
   repo.

Which committee names, election results, and (for --fetch-socrata) which
Socrata dataset each official's data comes from is configured centrally in
data/sources/registry.json — not hard-coded in this file — so that both
build_funding.py and build_record.py, and the cross-reference validator, all
agree on one place. See scripts/pipeline/registry.py.

Usage:
    python3 scripts/build_funding.py --fetch-socrata
    python3 scripts/build_funding.py --fetch-socrata --official mayor-bass
    python3 scripts/build_funding.py --csv-path data/raw/contributions.csv
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pipeline import atomic_io, provenance as prov, registry as reg, schemas, socrata, validation

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CSV = ROOT / "data" / "raw" / "contributions.csv"
DEFAULT_STATEMENTS_CSV = ROOT / "data" / "raw" / "statements_filed.csv"
CONTRIBUTIONS_CACHE = ROOT / "data" / "raw" / ".cache" / "m6g2-gc6c.json"
STATEMENTS_CACHE = ROOT / "data" / "raw" / ".cache" / "br3a-db9a.json"
CONTRIBUTIONS_RESOURCE_ID = "m6g2-gc6c"
STATEMENTS_RESOURCE_ID = "br3a-db9a"
TOP_N_DONORS = 30

# CSV column names, as they appear in the LA Ethics Commission's *export*
# (not its Socrata API — see normalize_api_row() for that mapping). Every
# other function in this file works against these column names regardless
# of which input source populated them.
COL_DATE = "Contribution Date"
COL_CONTRIBUTOR = "Contributor"
COL_OCCUPATION = "Contrib Occupation"
COL_EMPLOYER = "Contrib Employer"
COL_COMMITTEE = "Committee Name"
COL_COMMITTEE_ID = "Committee ID"
COL_PERIOD_BEG = "Period Beg Date"
COL_PERIOD_END = "Period End Date"
COL_AMOUNT = "Contribution Amount"
COL_TYPE = "Contribution Type"
COL_ELECTION_DATE = "Election Date"

# Only these Contribution Type values represent money/goods given by an
# identifiable donor. Excluded: "Unitemized" rows (Contributor is a bucket
# like "UNITEMIZED", below the reporting threshold for naming a donor, e.g.
# small-dollar aggregates), "Misc. Increase(s) to Cash" (not a contribution
# at all — e.g. public matching funds paid by "City of Los Angeles", bank
# interest), and "Loans Received" (debt the campaign owes back, often the
# candidate loaning themselves money — not a donation).
DONOR_CONTRIBUTION_TYPES = {
    "monetary contributions (itemized)",
    "non-monetary contributions (itemized)",
}

PAC_PATTERN = re.compile(r"\b(PAC|POLITICAL ACTION|COMMITTEE?|UNION|LOCAL \d+)\b", re.I)
BUSINESS_PATTERN = re.compile(
    r"\b(INC|LLC|LLP|LP|CORP|CORPORATION|CO|COMPANY|GROUP|PARTNERS|ASSOCIATES|"
    r"ENTERPRISES|HOLDINGS|TRUST|FOUNDATION|LTD|REALTY|PROPERTIES|VENTURES)\.?\b",
    re.I,
)
YEAR_PATTERN = re.compile(r"(20\d{2})")
# CSV rows sometimes spell these fields out literally instead of leaving them
# blank; treat them the same as missing.
BLANK_VALUES = {"none", "n/a", "na", "unknown"}


def clean_field(raw):
    value = (raw or "").strip()
    if not value or value.lower() in BLANK_VALUES:
        return None
    return value


def parse_amount(raw):
    if not raw:
        return None
    cleaned = str(raw).strip().replace("$", "").replace(",", "")
    if not cleaned:
        return None
    try:
        value = round(float(cleaned), 2)
    except ValueError:
        return None
    return int(value) if value == int(value) else value


def parse_date(raw):
    """Accepts either the CSV export's 'MM/DD/YYYY' or the Socrata API's
    ISO 'YYYY-MM-DDTHH:MM:SS.mmm' (only the date part is kept either way)."""
    raw = (raw or "").strip()
    if not raw:
        return None
    for fmt in ("%m/%d/%Y", "%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(raw, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def infer_donor_type(name, has_occupation_or_employer):
    if PAC_PATTERN.search(name):
        return "pac"
    if not has_occupation_or_employer and BUSINESS_PATTERN.search(name):
        return "business"
    return "individual"


def normalize_api_row(row: dict) -> dict:
    """Map one m6g2-gc6c Socrata JSON record to the CSV column-name shape.

    The Socrata contributions dataset does not expose occupation/employer
    (Schedule A itemized detail only breaks those out in the full paper
    filing, not this rolled-up dataset) — those two columns are left absent
    rather than guessed. This is a known, documented gap, not a bug: see
    README "Source policy / known limitations".
    """
    return {
        COL_DATE: row.get("con_date"),
        COL_CONTRIBUTOR: row.get("con_name"),
        COL_OCCUPATION: None,
        COL_EMPLOYER: None,
        COL_COMMITTEE: row.get("cmt_nm"),
        COL_COMMITTEE_ID: row.get("cmt_id"),
        COL_PERIOD_BEG: row.get("per_beg_date"),
        COL_PERIOD_END: row.get("per_end_date"),
        COL_AMOUNT: row.get("con_amount"),
        COL_TYPE: row.get("con_type"),
        COL_ELECTION_DATE: row.get("election_date"),
    }


def normalize_api_statement(row: dict) -> dict:
    link = row.get("stmt_link")
    if isinstance(link, dict):
        link = link.get("url")
    return {
        "cmt_id": row.get("cmt_id"),
        "period_from_date": row.get("period_from_date"),
        "period_to_date": row.get("period_to_date"),
        "stmt_link": link,
    }


def load_statement_links_from_csv(csv_path: Path):
    if not csv_path.exists():
        return {}
    lookup = {}
    with csv_path.open(newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            key = (
                (row.get("cmt_id") or "").strip(),
                parse_date(row.get("period_from_date")) or "",
                parse_date(row.get("period_to_date")) or "",
            )
            link = (row.get("stmt_link") or "").strip()
            if all(key) and link:
                lookup.setdefault(key, link)
    return lookup


def load_statement_links_from_rows(rows):
    lookup = {}
    for row in rows:
        norm = normalize_api_statement(row)
        key = (
            (norm["cmt_id"] or "").strip(),
            parse_date(norm["period_from_date"]) or "",
            parse_date(norm["period_to_date"]) or "",
        )
        link = (norm["stmt_link"] or "").strip() if norm["stmt_link"] else ""
        if all(key) and link:
            lookup.setdefault(key, link)
    return lookup


def committee_lookup(committees_by_official: dict):
    """Map lowercased committee name -> official id, across all officials."""
    lookup = {}
    for official_id, names in committees_by_official.items():
        for name in names:
            lookup[name.strip().lower()] = official_id
    return lookup


def group_rows_by_official(rows, committees_by_official: dict):
    lookup = committee_lookup(committees_by_official)
    grouped = {official_id: [] for official_id in committees_by_official}
    for row in rows:
        official_id = lookup.get((row.get(COL_COMMITTEE) or "").strip().lower())
        if official_id:
            grouped[official_id].append(row)
    return grouped


def load_rows_by_official_from_csv(csv_path: Path, committees_by_official: dict):
    with csv_path.open(newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    return group_rows_by_official(rows, committees_by_official)


def load_rows_by_official_from_api(committees_by_official: dict, use_cache_only: bool = False):
    raw_rows = socrata.fetch_dataset(
        CONTRIBUTIONS_RESOURCE_ID,
        cache_path=CONTRIBUTIONS_CACHE,
        use_cache_only=use_cache_only,
    )
    rows = [normalize_api_row(r) for r in raw_rows]
    return group_rows_by_official(rows, committees_by_official)


def build_donors(rows, statement_links=None, retrieved_at=None, methodology_version=None, source_name=None, source_notes=None):
    statement_links = statement_links or {}
    grouped = {}
    # normalize_api_row() leaves COL_OCCUPATION/COL_EMPLOYER unset (the public
    # Socrata dataset does not expose them); flag that gap once per call
    # rather than silently writing every donor's employer as null with no
    # explanation. CSV-sourced rows always carry these two columns (even if
    # sometimes blank per-row), so this only fires for --fetch-socrata runs.
    if source_notes is not None and rows and all(
        row.get(COL_OCCUPATION) is None and row.get(COL_EMPLOYER) is None for row in rows
    ):
        source_notes.append(
            "employer/occupation not available from the automated Socrata fetch "
            "(the public API dataset does not expose them); only present when "
            "built from a manually-downloaded CSV export via --csv-path"
        )
    for row in rows:
        if (row.get(COL_TYPE) or "").strip().lower() not in DONOR_CONTRIBUTION_TYPES:
            continue
        name = (row.get(COL_CONTRIBUTOR) or "").strip()
        amount = parse_amount(row.get(COL_AMOUNT))
        if not name or amount is None:
            continue
        grouped.setdefault(name, []).append((row, amount))

    donors = []
    for name, entries in grouped.items():
        total = 0
        contributions = []
        employer = None
        has_occupation_or_employer = False
        for row, amount in entries:
            total += amount
            contrib_date = parse_date(row.get(COL_DATE))
            entry = {"date": contrib_date, "amount": amount}
            link_key = (
                (row.get(COL_COMMITTEE_ID) or "").strip(),
                parse_date(row.get(COL_PERIOD_BEG)) or "",
                parse_date(row.get(COL_PERIOD_END)) or "",
            )
            source_url = statement_links.get(link_key)
            if source_url:
                entry["source_url"] = source_url
            entry["provenance"] = prov.make_provenance(
                source_name=source_name,
                source_url=source_url,
                retrieved_at=retrieved_at,
                reporting_period={
                    "from": parse_date(row.get(COL_PERIOD_BEG)),
                    "to": parse_date(row.get(COL_PERIOD_END)),
                },
                record_id=(row.get(COL_COMMITTEE_ID) or "").strip() or None,
                methodology_version=methodology_version,
            )
            contributions.append(entry)
            occupation = clean_field(row.get(COL_OCCUPATION))
            row_employer = clean_field(row.get(COL_EMPLOYER))
            if occupation or row_employer:
                has_occupation_or_employer = True
            if row_employer and not employer:
                employer = row_employer

        contributions.sort(key=lambda c: c["date"] or "")
        total = round(total, 2)
        donors.append(
            {
                "name": name,
                "type": infer_donor_type(name, has_occupation_or_employer),
                "total": int(total) if total == int(total) else total,
                "employer": employer,
                "contributions": contributions,
            }
        )

    donors.sort(key=lambda d: d["total"], reverse=True)
    return donors[:TOP_N_DONORS]


def build_reelection(official_id, committee_names, rows, election_result, today=None):
    """Re-election status for one official.

    "active" means the campaign is still ahead of its election, so it has to
    be checked against the election date, not just the year in the committee
    name. The date is authoritative; the committee-name year is only a
    fallback for rows that carry no election date. This is still a
    build-time snapshot — js/app.js independently re-derives the banner's
    tense against the live current date on every page load.
    """
    today = today or date.today().isoformat()

    election_dates = [parse_date(row.get(COL_ELECTION_DATE)) for row in rows]
    election_dates = [d for d in election_dates if d]
    election_date = max(election_dates) if election_dates else None

    years = [int(y) for name in committee_names for y in YEAR_PATTERN.findall(name)]
    current_year = int(today[:4])
    if election_date:
        active = election_date >= today
    else:
        active = bool(years) and max(years) >= current_year

    return {
        "active": active,
        "election_date": election_date,
        "committee": committee_names[0] if committee_names else None,
        "result": election_result if not active else None,
    }


def build_funding_payload(official, rows, entry, statement_links, today, retrieved_at, source_notes):
    official_id = official.get("id")
    committee_names = entry["funding"]["committees"]
    election_result = entry["funding"].get("election_result")

    if not committee_names:
        source_notes.append(f"{official_id}: no committee configured in registry.json")
    elif not rows:
        source_notes.append(f"{official_id}: no rows matched committees {committee_names!r}")

    source_block = {
        "name": "Los Angeles City Ethics Commission — City Campaign Contributions (and Misc. Increases to Cash)",
        "url": "https://ethics.lacity.org/",
        "committees": committee_names,
        "retrieved_at": retrieved_at,
        "methodology_version": prov.METHODOLOGY_VERSION,
    }

    payload = {
        "official": {
            "id": official_id,
            "name": official.get("name"),
            "office": official.get("office"),
            "reelection": build_reelection(official_id, committee_names, rows, election_result, today),
        },
        "source": source_block,
        "donors": build_donors(
            rows,
            statement_links,
            retrieved_at=retrieved_at,
            methodology_version=prov.METHODOLOGY_VERSION,
            source_name=source_block["name"],
            source_notes=source_notes,
        ),
    }
    return payload


def build_funding_for_official(official, rows_by_official, sources_registry, statement_links, today, retrieved_at):
    """Build, validate, and write funding.json for one official.

    Returns (status, record_count, problems, source_notes) — never raises;
    callers (main() and build_all.py) decide what to do with a "failed"
    status. On any validation problem, the previously-written funding.json
    (if any) is left untouched — see pipeline.atomic_io.write_if_valid.
    """
    official_id = official.get("id")
    problems = []
    source_notes = []
    try:
        entry = reg.registry_entry(sources_registry, official_id)
    except KeyError as exc:
        return "failed", 0, [str(exc)], source_notes

    rows = rows_by_official.get(official_id, [])
    payload = build_funding_payload(official, rows, entry, statement_links, today, retrieved_at, source_notes)

    problems.extend(validation.validate_schema(payload, schemas.get("funding")))
    for donor in payload["donors"]:
        if not validation.is_valid_amount(donor["total"]):
            problems.append(f"{official_id}: donor '{donor['name']}' has invalid total {donor['total']!r}")
        for c in donor["contributions"]:
            if c["date"] and not validation.is_valid_date(c["date"]):
                problems.append(f"{official_id}: donor '{donor['name']}' has invalid contribution date {c['date']!r}")
            if not validation.is_valid_amount(c["amount"]):
                problems.append(f"{official_id}: donor '{donor['name']}' has invalid contribution amount {c['amount']!r}")
            if c.get("source_url") and not validation.is_valid_url(c["source_url"], validation.ALLOWED_SOURCE_DOMAINS):
                problems.append(f"{official_id}: donor '{donor['name']}' has an untrusted source_url {c['source_url']!r}")
    dupe_names = validation.find_duplicates(payload["donors"], key_fn=lambda d: d["name"])
    for name in dupe_names:
        problems.append(f"{official_id}: duplicate donor name '{name}' in output")

    out_path = ROOT / "data" / "officials" / official_id / "funding.json"
    written = atomic_io.write_if_valid(out_path, payload, problems)
    if not written:
        return "failed", 0, problems, source_notes
    return "ok", len(payload["donors"]), problems, source_notes


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--official",
        action="append",
        help="only (re)build funding.json for this official id; may be repeated. Default: every official in the registry.",
    )
    source_group = parser.add_mutually_exclusive_group()
    source_group.add_argument(
        "--fetch-socrata",
        action="store_true",
        help="fetch live from the LA Ethics Commission's public Socrata API instead of reading a local CSV",
    )
    source_group.add_argument(
        "--csv-path",
        default=None,
        help=f"path to a locally-downloaded contributions CSV export (default when neither flag is given: {DEFAULT_CSV})",
    )
    parser.add_argument(
        "--statements-csv",
        default=str(DEFAULT_STATEMENTS_CSV),
        help=f"path to a locally-downloaded 'City Campaign Statements Filed' CSV, used only with --csv-path (default: {DEFAULT_STATEMENTS_CSV})",
    )
    parser.add_argument(
        "--use-cache-only",
        action="store_true",
        help="with --fetch-socrata, never hit the network — read the last cached response only (used by tests / offline dry-runs)",
    )
    args = parser.parse_args()

    officials = reg.load_officials()
    sources_registry = reg.load_registry()
    cross_ref_problems = reg.validate_cross_reference(officials, sources_registry)
    if cross_ref_problems:
        for p in cross_ref_problems:
            print(f"error: {p}")
        raise SystemExit(1)

    committees_by_official = {
        oid: entry["funding"]["committees"] for oid, entry in sources_registry["officials"].items()
    }

    today = date.today().isoformat()
    retrieved_at = today

    if args.fetch_socrata:
        rows_by_official = load_rows_by_official_from_api(committees_by_official, use_cache_only=args.use_cache_only)
        api_statements = socrata.fetch_dataset(
            STATEMENTS_RESOURCE_ID, cache_path=STATEMENTS_CACHE, use_cache_only=args.use_cache_only
        )
        statement_links = load_statement_links_from_rows(api_statements)
    else:
        csv_path = Path(args.csv_path) if args.csv_path else DEFAULT_CSV
        if not csv_path.exists():
            raise SystemExit(f"CSV not found: {csv_path} (pass --csv-path or use --fetch-socrata)")
        rows_by_official = load_rows_by_official_from_csv(csv_path, committees_by_official)
        statement_links = load_statement_links_from_csv(Path(args.statements_csv))

    target_ids = set(args.official) if args.official else None
    exit_code = 0
    for official in officials:
        official_id = official.get("id")
        if target_ids and official_id not in target_ids:
            continue
        status, count, problems, notes = build_funding_for_official(
            official, rows_by_official, sources_registry, statement_links, today, retrieved_at
        )
        for note in notes:
            print(f"note: {note}")
        if status == "ok":
            print(f"wrote data/officials/{official_id}/funding.json ({count} donors)")
        else:
            exit_code = 1
            print(f"error: {official_id}: funding.json NOT written — {'; '.join(problems)}")

    if exit_code:
        raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
