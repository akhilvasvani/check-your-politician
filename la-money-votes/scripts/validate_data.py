#!/usr/bin/env python3
"""la-money-votes — validate_data.py

Schema- and cross-reference-validates whatever JSON is currently committed
under data/ — data/officials.json, data/sources/registry.json, and every
data/officials/<id>/{funding.json,record.json}. Makes no network calls and
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
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pipeline import registry as reg, schemas, validation

ROOT = Path(__file__).resolve().parent.parent


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
