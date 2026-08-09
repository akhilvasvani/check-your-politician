"""Loads and cross-validates the two registry files every builder depends on:

- data/officials.json            the frozen, user-facing officials index
- data/sources/registry.json     builder configuration per official (committees,
                                  election results, record source/fixture path)

Kept as two files on purpose: officials.json is read directly by the
frontend and its shape is frozen by CONTRACT.md, so pipeline-only config
(which committees a name maps to, which fixture file holds curated record
items, etc.) lives in registry.json instead of growing officials.json.
validate_cross_reference() is what enforces the two files agree with each
other.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
OFFICIALS_INDEX = ROOT / "data" / "officials.json"
SOURCES_REGISTRY = ROOT / "data" / "sources" / "registry.json"


def load_officials(path: Path = OFFICIALS_INDEX) -> list:
    return json.loads(Path(path).read_text())


def load_registry(path: Path = SOURCES_REGISTRY) -> dict:
    return json.loads(Path(path).read_text())


def official_ids(officials: list) -> set:
    return {o["id"] for o in officials if "id" in o}


def validate_cross_reference(officials: list, registry: dict) -> list:
    """Cross-reference validation between the officials registry and the
    per-official builder config. Returns a list of problem strings.
    """
    problems = []
    ids_in_index = official_ids(officials)
    ids_in_registry = set(registry.get("officials", {}).keys())

    missing_from_registry = sorted(ids_in_index - ids_in_registry)
    for oid in missing_from_registry:
        problems.append(
            f"official '{oid}' is in data/officials.json but has no entry in "
            f"data/sources/registry.json — it cannot be built"
        )

    orphaned_in_registry = sorted(ids_in_registry - ids_in_index)
    for oid in orphaned_in_registry:
        problems.append(
            f"official '{oid}' is in data/sources/registry.json but not in "
            f"data/officials.json — remove it or add the official to the index"
        )

    dupe_ids = [o["id"] for o in officials]
    seen = set()
    for oid in dupe_ids:
        if oid in seen:
            problems.append(f"duplicate official id '{oid}' in data/officials.json")
        seen.add(oid)

    return problems


def registry_entry(registry: dict, official_id: str) -> dict:
    entry = registry.get("officials", {}).get(official_id)
    if entry is None:
        raise KeyError(f"no registry.json entry for official '{official_id}'")
    return entry
