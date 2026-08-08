#!/usr/bin/env python3
"""la-money-votes — starter build_funding.py, Person 1 owns this file.

Generates data/officials/<id>/funding.json for each official listed in
data/officials.json. Output must conform to the schema frozen in
CONTRACT.md. Currently writes the mock data unchanged — replace with real
campaign finance data.
"""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OFFICIALS_INDEX = ROOT / "data" / "officials.json"


def build_funding(official_id: str) -> None:
    out_path = ROOT / "data" / "officials" / official_id / "funding.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    # TODO: replace with real funding data lookup.
    raise NotImplementedError(f"build_funding not yet implemented for {official_id}")


def main() -> None:
    officials = json.loads(OFFICIALS_INDEX.read_text())
    for official in officials:
        build_funding(official["id"])


if __name__ == "__main__":
    main()
