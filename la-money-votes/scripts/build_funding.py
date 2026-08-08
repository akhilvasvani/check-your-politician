#!/usr/bin/env python3
"""la-money-votes — build_funding.py, Person 1 owns this file.

Reads a locally downloaded LA Ethics Commission campaign contributions CSV
(https://ethics.lacity.org/data/ export format — con_date, con_name, cmt_nm,
con_occp, con_empr, con_amount, election_date, ... columns) and writes
data/officials/<id>/funding.json for each official listed in
data/officials.json, per the schema frozen in CONTRACT.md.

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
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OFFICIALS_INDEX = ROOT / "data" / "officials.json"
DEFAULT_CSV = ROOT / "data" / "raw" / "contributions.csv"
TOP_N_DONORS = 30

# Map each official id -> the campaign committee name exactly as it appears
# in the CSV's cmt_nm column. Rows are matched case-insensitively.
COMMITTEES = {
    # DEMO WIRING ONLY. "Hahn for Mayor 2005" is the only committee present
    # in the sample CSV used to build/smoke-test this script — it's James
    # Hahn's 2003-05 mayoral campaign, NOT Karen Bass's real committee.
    # This proves the pipeline runs end-to-end; it does NOT mean the
    # generated funding.json reflects real Bass donor data. Swap in her
    # actual 2026 reelection committee name before this ships anywhere real.
    "mayor-bass": "Hahn for Mayor 2005",
    # TODO: cd14-official's real name/office is still "REPLACE_ME" in
    # data/officials.json (Person 4's file), and no CD14 rows exist in the
    # sample CSV. Fill in once the official and committee are known.
    "cd14-official": "REPLACE_ME committee name",
    # TODO: same blocker as cd14-official, for CD11.
    "cd11-official": "REPLACE_ME committee name",
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
    if raw is None or raw == "":
        return None
    try:
        value = round(float(raw), 2)
    except ValueError:
        return None
    return int(value) if value == int(value) else value


def parse_date(raw):
    if not raw:
        return None
    return raw[:10] or None


def infer_donor_type(name, has_occupation_or_employer):
    if PAC_PATTERN.search(name):
        return "pac"
    if not has_occupation_or_employer and BUSINESS_PATTERN.search(name):
        return "business"
    return "individual"


def load_rows(csv_path: Path):
    with csv_path.open(newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def index_rows_by_committee(rows):
    index = {}
    for row in rows:
        key = (row.get("cmt_nm") or "").strip().lower()
        index.setdefault(key, []).append(row)
    return index


def build_donors(rows):
    grouped = {}
    for row in rows:
        name = (row.get("con_name") or "").strip()
        amount = parse_amount(row.get("con_amount"))
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
            contributions.append({"date": parse_date(row.get("con_date")), "amount": amount})
            occupation = clean_field(row.get("con_occp"))
            row_employer = clean_field(row.get("con_empr"))
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


def build_reelection(committee_name, rows):
    election_date = None
    for row in rows:
        election_date = parse_date(row.get("election_date"))
        if election_date:
            break

    years = [int(year) for year in YEAR_PATTERN.findall(committee_name or "")]
    active = bool(years) and max(years) >= 2026

    return {
        "active": active,
        "election_date": election_date,
        "committee": committee_name or None,
    }


def build_funding(official, rows_by_committee) -> None:
    official_id = official.get("id")
    committee_name = COMMITTEES.get(official_id)
    rows = rows_by_committee.get((committee_name or "").strip().lower(), []) if committee_name else []

    if not committee_name:
        print(f"warning: no committee configured for {official_id!r}; writing empty donor list")
    elif not rows:
        print(f"warning: no CSV rows matched committee {committee_name!r} for {official_id!r}")

    payload = {
        "official": {
            "id": official_id,
            "name": official.get("name"),
            "office": official.get("office"),
            "reelection": build_reelection(committee_name, rows),
        },
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
    args = parser.parse_args()

    csv_path = Path(args.csv_path)
    if not csv_path.exists():
        raise SystemExit(f"CSV not found: {csv_path}")

    rows = load_rows(csv_path)
    rows_by_committee = index_rows_by_committee(rows)

    officials = json.loads(OFFICIALS_INDEX.read_text())
    for official in officials:
        build_funding(official, rows_by_committee)


if __name__ == "__main__":
    main()
