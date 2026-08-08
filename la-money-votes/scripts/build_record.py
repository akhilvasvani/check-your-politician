#!/usr/bin/env python3
"""la-money-votes — starter build_record.py, Person 2 owns this file.

Generates data/officials/<id>/record.json for each official listed in
data/officials.json. Output must conform to the schema frozen in
CONTRACT.md. Currently writes the mock data unchanged — replace with real
council file / voting record data.
"""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OFFICIALS_INDEX = ROOT / "data" / "officials.json"


def build_record(official_id: str) -> None:
    out_path = ROOT / "data" / "officials" / official_id / "record.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    # TODO: replace with real voting record data lookup.
    raise NotImplementedError(f"build_record not yet implemented for {official_id}")


def main() -> None:
    officials = json.loads(OFFICIALS_INDEX.read_text())
    for official in officials:
        build_record(official["id"])


if __name__ == "__main__":
    main()
