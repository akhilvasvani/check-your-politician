"""Loads the JSON Schema files under data/schemas/ and resolves the one kind
of $ref they use (a same-directory sibling file, e.g. "provenance.schema.json")
by inlining it. This keeps data/schemas/*.json as the single source of truth
for shape documentation, with validation.validate_schema() actually enforcing
them — no separate hand-duplicated schema living in Python.
"""

from __future__ import annotations

import json
from pathlib import Path

SCHEMA_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "schemas"


def _resolve_refs(node, cache: dict):
    if isinstance(node, dict):
        if set(node.keys()) == {"$ref"}:
            ref_name = node["$ref"]
            if ref_name not in cache:
                cache[ref_name] = json.loads((SCHEMA_DIR / ref_name).read_text())
                cache[ref_name] = _resolve_refs(cache[ref_name], cache)
            return cache[ref_name]
        return {k: _resolve_refs(v, cache) for k, v in node.items()}
    if isinstance(node, list):
        return [_resolve_refs(v, cache) for v in node]
    return node


def load_schema(filename: str) -> dict:
    raw = json.loads((SCHEMA_DIR / filename).read_text())
    return _resolve_refs(raw, {})


OFFICIALS_SCHEMA = None
FUNDING_SCHEMA = None
RECORD_SCHEMA = None
SOURCES_REGISTRY_SCHEMA = None
BUILD_REPORT_SCHEMA = None
FRESHNESS_SCHEMA = None


def get(name: str) -> dict:
    """Lazy-load and cache a schema by short name: officials, funding, record,
    sources_registry, build_report, freshness."""
    global OFFICIALS_SCHEMA, FUNDING_SCHEMA, RECORD_SCHEMA, SOURCES_REGISTRY_SCHEMA
    global BUILD_REPORT_SCHEMA, FRESHNESS_SCHEMA
    mapping = {
        "officials": ("OFFICIALS_SCHEMA", "officials.schema.json"),
        "funding": ("FUNDING_SCHEMA", "funding.schema.json"),
        "record": ("RECORD_SCHEMA", "record.schema.json"),
        "sources_registry": ("SOURCES_REGISTRY_SCHEMA", "sources_registry.schema.json"),
        "build_report": ("BUILD_REPORT_SCHEMA", "build_report.schema.json"),
        "freshness": ("FRESHNESS_SCHEMA", "freshness.schema.json"),
    }
    if name not in mapping:
        raise KeyError(f"unknown schema '{name}'")
    var_name, filename = mapping[name]
    value = globals()[var_name]
    if value is None:
        value = load_schema(filename)
        globals()[var_name] = value
    return value
