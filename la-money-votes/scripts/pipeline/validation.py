"""Dependency-light validation helpers for the la-money-votes data pipeline.

Everything here is stdlib-only (re, datetime, urllib.parse) by design — see
CONTRACT.md "Validation" section for why we hand-roll this instead of adding
a jsonschema dependency. A ValidationError carries a list of human-readable
problem strings; callers collect these into a build report rather than
raising on the first problem, so one bad row doesn't hide the rest.
"""

from __future__ import annotations

import re
from datetime import datetime
from urllib.parse import urlparse

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
COUNCIL_FILE_RE = re.compile(r"^\d{2}-\d{4}(?:-S\d+)?$")
MAYORAL_RECORD_RE = re.compile(r"^(ED|EO)-\d+$")
ALLOWED_URL_SCHEMES = {"https", "http"}
# Domains our own source policy allows citing as a primary source. Anything
# else is very likely a mis-typed or third-party (non-authoritative) URL and
# should fail validation rather than be silently trusted. See README's
# "Source policy" section.
ALLOWED_SOURCE_DOMAINS = {
    "ethics.lacity.org",
    "ethics.lacity.gov",
    "data.lacity.org",
    "cityclerk.lacity.org",
    "clerk.lacity.gov",
    "mayor.lacity.gov",
    "lacity.gov",
    "controller.lacity.gov",
}


class ValidationError(Exception):
    """Raised with one or more human-readable problem descriptions."""

    def __init__(self, problems):
        self.problems = list(problems)
        super().__init__("; ".join(self.problems) or "validation failed")


def is_valid_date(value) -> bool:
    """True for a strict 'YYYY-MM-DD' string that is also a real calendar date."""
    if not isinstance(value, str) or not DATE_RE.match(value):
        return False
    try:
        datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        return False
    return True


def is_valid_url(value, allowed_domains=None) -> bool:
    """True for an http(s) URL with a non-empty host.

    If allowed_domains is given, the host (or its parent domain) must be in
    that set — used to keep citations restricted to our source policy's
    named authoritative domains rather than letting a typo or an unrelated
    site slip through as a "verified" source.
    """
    if not isinstance(value, str) or not value.strip():
        return False
    try:
        parsed = urlparse(value)
    except ValueError:
        return False
    if parsed.scheme not in ALLOWED_URL_SCHEMES or not parsed.netloc:
        return False
    if allowed_domains:
        host = parsed.netloc.lower().split(":")[0]
        if not any(host == d or host.endswith("." + d) for d in allowed_domains):
            return False
    return True


def is_valid_amount(value) -> bool:
    """True for a finite number (int or float), not a string.

    Negative values are allowed on purpose: the LA Ethics Commission source
    data itself reports negative itemized-contribution rows to record
    corrections/reattributions of previously-reported amounts, so rejecting
    negatives would silently drop real, sourced data rather than catch a
    formatting bug. Amounts are already parsed to numbers by the builders
    before this is called; a string here means a formatting/parsing bug
    upstream, not a valid amount, so it fails rather than being coerced.
    """
    if isinstance(value, bool):
        return False
    if not isinstance(value, (int, float)):
        return False
    if value != value or value in (float("inf"), float("-inf")):  # NaN/inf guard
        return False
    return True


def is_valid_record_id(value: str) -> bool:
    return bool(COUNCIL_FILE_RE.match(value) or MAYORAL_RECORD_RE.match(value))


def find_duplicates(items, key_fn):
    """Return the list of keys (from key_fn) that appear more than once."""
    seen = {}
    dupes = []
    for item in items:
        key = key_fn(item)
        seen[key] = seen.get(key, 0) + 1
    for key, count in seen.items():
        if count > 1:
            dupes.append(key)
    return dupes


# ---------------------------------------------------------------------------
# Minimal JSON-Schema-subset validator
# ---------------------------------------------------------------------------
# Supports the subset of JSON Schema our schemas/*.schema.json files actually
# use: type, required, properties, items, enum, additionalProperties. This is
# intentionally not a general JSON Schema implementation — see
# data/schemas/README (in CONTRACT.md) for the supported subset.

_TYPE_MAP = {
    "object": dict,
    "array": list,
    "string": str,
    "number": (int, float),
    "integer": int,
    "boolean": bool,
    "null": type(None),
}


def validate_schema(instance, schema, path="$") -> list:
    """Return a list of problem strings (empty means valid)."""
    problems = []
    types = schema.get("type")
    if types:
        types = [types] if isinstance(types, str) else types
        py_types = tuple(_TYPE_MAP[t] for t in types if t in _TYPE_MAP)
        # bool is a subclass of int in Python; only allow it when "boolean" was requested.
        if isinstance(instance, bool) and int not in [_TYPE_MAP.get(t) for t in types] and bool not in py_types:
            if not isinstance(instance, py_types):
                problems.append(f"{path}: expected type {types}, got bool")
        elif py_types and not isinstance(instance, py_types):
            problems.append(f"{path}: expected type {types}, got {type(instance).__name__}")
            return problems  # further checks would be meaningless

    if "enum" in schema and instance not in schema["enum"]:
        problems.append(f"{path}: {instance!r} not in allowed values {schema['enum']}")

    if isinstance(instance, dict):
        for req in schema.get("required", []):
            if req not in instance:
                problems.append(f"{path}: missing required field '{req}'")
        props = schema.get("properties", {})
        additional = schema.get("additionalProperties")
        extra_keys = set(instance) - set(props)
        if additional is False and extra_keys:
            problems.append(f"{path}: unexpected field(s) {sorted(extra_keys)}")
        elif isinstance(additional, dict):
            # additionalProperties as a schema: validate every key not named in
            # 'properties' against it (used for dynamic-key maps like registry.json's
            # {"officials": {"<any-id>": {...}}}).
            for key in extra_keys:
                problems.extend(validate_schema(instance[key], additional, f"{path}.{key}"))
        for key, subschema in props.items():
            if key in instance:
                problems.extend(validate_schema(instance[key], subschema, f"{path}.{key}"))

    if isinstance(instance, list) and "items" in schema:
        item_schema = schema["items"]
        for i, item in enumerate(instance):
            problems.extend(validate_schema(item, item_schema, f"{path}[{i}]"))

    return problems
