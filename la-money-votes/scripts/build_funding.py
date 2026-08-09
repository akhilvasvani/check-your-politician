#!/usr/bin/env python3
"""la-money-votes — build_funding.py, Person 1 owns this file.

Reads a locally downloaded LA Ethics Commission "City Campaign Contributions
(and Misc Increases to Cash)" export and writes data/officials/<id>/funding.json
for each official listed in data/officials.json, per the schema frozen in
CONTRACT.md.

Usage:
    python3 scripts/build_funding.py [path/to/contributions.csv]

The CSV itself is not committed to the repo — download it locally from the
LA Ethics Commission and pass its path, or drop it at the DEFAULT_CSV path
below.
"""

import argparse
import csv
import json
import re
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OFFICIALS_INDEX = ROOT / "data" / "officials.json"
DEFAULT_CSV = ROOT / "data" / "raw" / "contributions.csv"
TOP_N_DONORS = 30

# Primary source for every number in the output. Only verified, stable URLs
# belong here — a dead or guessed link on a transparency site is worse than no
# link at all. The Ethics Commission publishes contributions in bulk, with no
# per-donor permalink, so this is a dataset-level citation and the UI presents
# it that way (one note under the donor table, not a link per row).
SOURCE = {
    "name": "Los Angeles City Ethics Commission — City Campaign Contributions (and Misc. Increases to Cash)",
    "url": "https://ethics.lacity.org/",
}

# Election outcomes, hand-curated. The contributions export records who gave to
# which committee for which election — it never records who won, so this cannot
# be derived from the CSV and lives here instead of being inferred. Keeping it
# in the script (rather than editing funding.json directly) means a regenerate
# doesn't silently drop it.
#
# - cd11-official (Traci Park): won outright in the June 2, 2026 primary,
#   second term began ~2026-07-01. Same curation as build_record.py's term
#   cutoffs — see that file's docstring.
# - cd14-official (Ysabel Jurado): won the November 5, 2024 CD14 general.
# - cd2-official (Adrin Nazarian): the LA City Clerk's "Current Elected
#   Officials" roster confirms he assumed office 12/9/24 for his first term
#   (https://clerk.lacity.gov/articles/current-elected-officials), which is
#   only possible if he won the November 5, 2024 CD2 general — the contribution
#   export itself never says this, so it's recorded here rather than derived.
# - mayor-bass: 2026 election is still ahead, so there is no result yet.
ELECTION_RESULTS = {
    "cd11-official": "won",
    "cd14-official": "won",
    "cd2-official": "won",
}

# CSV column names, as they appear in the LA Ethics Commission export header.
COL_DATE = "Contribution Date"
COL_CONTRIBUTOR = "Contributor"
COL_OCCUPATION = "Contrib Occupation"
COL_EMPLOYER = "Contrib Employer"
COL_COMMITTEE = "Committee Name"
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

# Map each official id -> the campaign committee name(s) exactly as they
# appear in the CSV's Committee Name column, ordered [primary, general, ...].
# Rows across all of an official's committees are merged into one donor list.
# The first name is used as the canonical "committee" shown in the output.
# Matched case-insensitively. Found by inspecting the real LA Ethics export
# (Committee Type 'C' = candidate-controlled, confirmed against Office/
# District/Candidate columns) — not placeholders.
COMMITTEES = {
    # Karen Bass, current mayor, running for reelection in 2026.
    "mayor-bass": ["Re-Elect Karen Bass for Mayor 2026", "Re-Elect Karen Bass for Mayor 2026-General"],
    # Ysabel Jurado, elected CD14 in Nov 2024; her current term runs to 2028,
    # so she has no 2026 committee yet — these are her 2024 election committees.
    "cd14-official": ["Jurado for City Council 2024", "Ysabel Jurado for City Council 2024-General"],
    # Traci Park, current CD11 councilmember, running for reelection in 2026.
    "cd11-official": ["Traci Park for City Council 2026"],
    # Adrin Nazarian, elected CD2 in Nov 2024; current term runs to 2028, so
    # these are his 2024 election committees (primary + general). Confirmed
    # via a live query against the same Ethics Commission dataset SOURCE
    # cites (data.lacity.org resource m6g2-gc6c), grouped by cand_name =
    # 'Nazarian, Adrin' — not copied from a secondary aggregator.
    "cd2-official": [
        "Adrin Nazarian for City Council 2024",
        "Adrin Nazarian for City Council 2024-General",
    ],
}

PAC_PATTERN = re.compile(
    r"\b(PAC|POLITICAL ACTION|COMMITTEE?|UNION|LOCAL \d+)\b", re.I
)
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
    cleaned = raw.strip().replace("$", "").replace(",", "")
    if not cleaned:
        return None
    try:
        value = round(float(cleaned), 2)
    except ValueError:
        return None
    return int(value) if value == int(value) else value


def parse_date(raw):
    raw = (raw or "").strip()
    if not raw:
        return None
    try:
        return datetime.strptime(raw, "%m/%d/%Y").strftime("%Y-%m-%d")
    except ValueError:
        return None


def infer_donor_type(name, has_occupation_or_employer):
    if PAC_PATTERN.search(name):
        return "pac"
    if not has_occupation_or_employer and BUSINESS_PATTERN.search(name):
        return "business"
    return "individual"


def committee_lookup():
    """Map lowercased committee name -> official id, across all officials."""
    lookup = {}
    for official_id, names in COMMITTEES.items():
        for name in names:
            lookup[name.strip().lower()] = official_id
    return lookup


def load_rows_by_official(csv_path: Path):
    """Stream the CSV once, keeping only rows for configured committees.

    The real export can be hundreds of MB, so we filter as we read instead
    of materializing every row (most of which belong to committees we don't
    care about) into memory.
    """
    lookup = committee_lookup()
    rows_by_official = {official_id: [] for official_id in COMMITTEES}
    with csv_path.open(newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            official_id = lookup.get((row.get(COL_COMMITTEE) or "").strip().lower())
            if official_id:
                rows_by_official[official_id].append(row)
    return rows_by_official


def build_donors(rows):
    grouped = {}
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
            contributions.append({"date": parse_date(row.get(COL_DATE)), "amount": amount})
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


def build_reelection(official_id, committee_names, rows, today=None):
    """Re-election status for one official.

    "active" means the campaign is still ahead of its election, so it has to be
    checked against the election date, not just the year in the committee name:
    a committee called "... 2026" is still named that the day after the 2026
    election, and a build that only looked at the name would keep reporting a
    finished campaign as live. The date is authoritative; the committee year is
    only a fallback for rows that carry no election date.

    This is still a build-time snapshot. Consumers that can go stale between
    builds should compare election_date against the current date themselves —
    js/app.js does exactly that when it picks the banner's tense.
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
        # Absent until the election has actually happened; see ELECTION_RESULTS.
        "result": ELECTION_RESULTS.get(official_id) if not active else None,
    }


def build_funding(official, rows_by_official, today=None) -> None:
    official_id = official.get("id")
    committee_names = COMMITTEES.get(official_id, [])
    rows = rows_by_official.get(official_id, [])

    if not committee_names:
        print(f"warning: no committee configured for {official_id!r}; writing empty donor list")
    elif not rows:
        print(f"warning: no CSV rows matched {committee_names!r} for {official_id!r}")

    payload = {
        "official": {
            "id": official_id,
            "name": official.get("name"),
            "office": official.get("office"),
            "reelection": build_reelection(official_id, committee_names, rows, today),
        },
        "source": dict(SOURCE, committees=committee_names),
        "donors": build_donors(rows),
    }

    out_path = ROOT / "data" / "officials" / official_id / "funding.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2) + "\n")
    print(f"wrote {out_path.relative_to(ROOT)} ({len(payload['donors'])} donors)")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "csv_path",
        nargs="?",
        default=str(DEFAULT_CSV),
        help=f"path to the LA Ethics Commission contributions CSV (default: {DEFAULT_CSV})",
    )
    parser.add_argument(
        "--official",
        action="append",
        help=(
            "only (re)build funding.json for this official id; may be repeated. "
            "Default: every official in data/officials.json. Use this when the "
            "CSV on hand only covers one official's committee(s), so the others' "
            "already-committed funding.json isn't overwritten with an empty "
            "donor list for rows it can't find."
        ),
    )
    args = parser.parse_args()

    csv_path = Path(args.csv_path)
    if not csv_path.exists():
        raise SystemExit(f"CSV not found: {csv_path}")

    rows_by_official = load_rows_by_official(csv_path)

    today = date.today().isoformat()
    officials = json.loads(OFFICIALS_INDEX.read_text())
    if args.official:
        officials = [o for o in officials if o.get("id") in args.official]
    for official in officials:
        build_funding(official, rows_by_official, today)


if __name__ == "__main__":
    main()
