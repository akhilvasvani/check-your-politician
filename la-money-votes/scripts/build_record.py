#!/usr/bin/env python3
"""la-money-votes — build_record.py

Writes data/officials/<id>/record.json for one or more officials listed in
data/officials.json, per the schema frozen in CONTRACT.md (with additive
provenance/source fields — see CONTRACT.md "Additions").

DATA SOURCE (hand-curated, no invented entries, no automated fetch):
LA City Council's Council File Management System (CFMS, at
cityclerk.lacity.org/lacityclerkconnect) has no official bulk API, CSV, or
JSON export — see README "Source policy / known limitations" for the full
research trail. Every item is instead looked up individually by council
file number and cross-checked against news coverage / official
councilmember or mayoral press releases, then stored as versioned per-
official JSON data (not hard-coded in this file) at
data/sources/records/<official-slug>.json, one array entry per curated
item. Mayor Bass does not sponsor or vote on Council Files (she is not a
Council member), so her items use her own numbered Executive Directives
("ED-#") and Emergency Executive Orders ("EO-#") from mayor.lacity.gov in
the council_file field instead.

To add or update an item: edit the official's fixture file directly (not
this script), citing a real council_file / activity you can point to, then
rerun this script for that official.

Usage:
    python3 scripts/build_record.py --official mayor-bass
    python3 scripts/build_record.py                    # every official in the registry
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pipeline import atomic_io, provenance as prov, registry as reg, schemas, validation

ROOT = Path(__file__).resolve().parent.parent

# Primary-source roots. Only verified, stable URLs belong here — a dead or
# guessed link on a transparency site is worse than no link at all.
CFMS_ROOT = "https://cityclerk.lacity.org/lacityclerkconnect/"
CFMS_VIEWRECORD = CFMS_ROOT + "index.cfm?fa=ccfi.viewrecord&cfnumber={council_file}"

# Council file numbers look like "25-0542", with an optional "-S<n>" suffix
# for a numbered sub-file ("25-0600-S17").
COUNCIL_FILE_PATTERN = re.compile(r"^\d{2}-\d{4}(?:-S\d+)?$")


def source_url_for(council_file: str):
    """Primary-source URL for one record item, or None when none is verified.

    Council files resolve to their own CFMS record page. Mayoral Executive
    Directives and Emergency Executive Orders ("ED-9", "EO-1") are published
    as individual PDFs on mayor.lacity.gov under no URL pattern we've been
    able to verify, so they get no per-item link and fall back to the
    dataset-level source note the UI renders under the table.
    """
    council_file = (council_file or "").strip()
    if COUNCIL_FILE_PATTERN.match(council_file):
        return CFMS_VIEWRECORD.format(council_file=council_file)
    return None


def load_fixture(fixture_relative_path: str):
    path = ROOT / fixture_relative_path
    if not path.exists():
        raise FileNotFoundError(f"no record fixture at {path}")
    data = json.loads(path.read_text())
    return data.get("items", [])


def build_record_payload(official_id, entry, retrieved_at):
    fixture_items = load_fixture(entry["record"]["fixture"])
    source_block = dict(entry["record"]["source"])
    source_block["retrieved_at"] = retrieved_at
    source_block["methodology_version"] = prov.METHODOLOGY_VERSION

    items = []
    for item in fixture_items:
        council_file = item.get("council_file")
        url = source_url_for(council_file)
        enriched = dict(item)
        enriched["source_url"] = url
        enriched["provenance"] = prov.make_provenance(
            source_name=source_block["name"],
            source_url=url or source_block.get("url"),
            retrieved_at=retrieved_at,
            meeting_date=item.get("date"),
            record_id=council_file,
            methodology_version=prov.METHODOLOGY_VERSION,
        )
        items.append(enriched)

    return {
        "official_id": official_id,
        "source": source_block,
        "items": items,
    }


def build_record_for_official(official_id, sources_registry, retrieved_at):
    """Build, validate, and write record.json for one official.

    Returns (status, record_count, problems, source_notes) — never raises;
    a missing fixture or a validation problem is reported and skipped
    without touching any previously-written, valid record.json.
    """
    problems = []
    source_notes = []
    try:
        entry = reg.registry_entry(sources_registry, official_id)
    except KeyError as exc:
        return "failed", 0, [str(exc)], source_notes

    try:
        payload = build_record_payload(official_id, entry, retrieved_at)
    except FileNotFoundError as exc:
        return "failed", 0, [str(exc)], source_notes

    if not payload["items"]:
        source_notes.append(f"{official_id}: fixture has zero curated items")

    problems.extend(validation.validate_schema(payload, schemas.get("record")))
    for item in payload["items"]:
        if not validation.is_valid_record_id(item.get("council_file", "")):
            problems.append(f"{official_id}: '{item.get('council_file')}' is not a recognized council_file/ED/EO id format")
        if not validation.is_valid_date(item.get("date", "")):
            problems.append(f"{official_id}: item {item.get('council_file')} has invalid date {item.get('date')!r}")
        if item.get("source_url") and not validation.is_valid_url(item["source_url"], validation.ALLOWED_SOURCE_DOMAINS):
            problems.append(f"{official_id}: item {item.get('council_file')} has an untrusted source_url")
    dupe_files = validation.find_duplicates(payload["items"], key_fn=lambda i: i.get("council_file"))
    for cf in dupe_files:
        problems.append(f"{official_id}: duplicate council_file '{cf}' in output")

    out_path = ROOT / "data" / "officials" / official_id / "record.json"
    written = atomic_io.write_if_valid(out_path, payload, problems)
    if not written:
        return "failed", 0, problems, source_notes
    return "ok", len(payload["items"]), problems, source_notes


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--official",
        action="append",
        help="only (re)build record.json for this official id; may be repeated. Default: every official in the registry.",
    )
    args = parser.parse_args()

    officials = reg.load_officials()
    sources_registry = reg.load_registry()
    cross_ref_problems = reg.validate_cross_reference(officials, sources_registry)
    if cross_ref_problems:
        for p in cross_ref_problems:
            print(f"error: {p}")
        raise SystemExit(1)

    retrieved_at = date.today().isoformat()
    target_ids = set(args.official) if args.official else None

    exit_code = 0
    for official in officials:
        official_id = official.get("id")
        if target_ids and official_id not in target_ids:
            continue
        status, count, problems, notes = build_record_for_official(official_id, sources_registry, retrieved_at)
        for note in notes:
            print(f"note: {note}")
        if status == "ok":
            print(f"wrote data/officials/{official_id}/record.json ({count} items)")
        else:
            exit_code = 1
            print(f"error: {official_id}: record.json NOT written — {'; '.join(problems)}")

    if exit_code:
        raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
