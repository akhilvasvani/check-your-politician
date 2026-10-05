#!/usr/bin/env python3
"""Resolve raw CART speaker labels to canonical (role, official_id) pairs.

Pipeline:
    exact-role match          → hit rate ~87.2% on 9-meeting corpus
    exact councilmember match → hit rate ~12.3%
    fuzzy-role match (ed=1)   → hit rate  ~0.1% (CART typos)
    unresolved                → hit rate  ~0.3% (pre-meeting None + rare)

The unresolved bucket is a first-class output: it is written to the transcript JSON
as resolved_role='unknown' and logged for eval review, never silently coerced.

The councilmember lookup is loaded from data/transcripts/roster.json — see that file
for the source of truth. This module has no dependency on data/officials.json; the
link back to official_id is done inside roster.json at authoring time.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


# Canonical role labels observed in CART operator's output, mapped to
# (official_id, role) for downstream storage. official_id is None for
# ephemeral roles like Speaker or Reporter.
ROLE_MAP: dict[str, tuple[str | None, str]] = {
    "Council President": ("council-president", "presiding"),
    "City Attorney":     ("city-attorney",     "counsel"),
    "Clerk":             ("clerk",             "clerk"),
    "Interpreter":       ("interpreter",       "interpreter"),
    "Reporter":          (None,                "reporter"),
    "Speaker":           (None,                "public-speaker"),
}


def levenshtein(a: str, b: str) -> int:
    """Stdlib-only edit-distance. Iterative DP, O(len(a)*len(b))."""
    if a == b:
        return 0
    if len(a) < len(b):
        a, b = b, a
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        curr = [i] + [0] * len(b)
        for j, cb in enumerate(b, 1):
            insert = curr[j - 1] + 1
            delete = prev[j] + 1
            subst = prev[j - 1] + (0 if ca == cb else 1)
            curr[j] = min(insert, delete, subst)
        prev = curr
    return prev[-1]


def fuzzy_role_match(label: str, max_edit: int = 1) -> str | None:
    """Return the canonical role if `label` is within edit-distance max_edit of one."""
    for canonical in ROLE_MAP:
        if levenshtein(label, canonical) <= max_edit:
            return canonical
    return None


@dataclass(frozen=True)
class Resolution:
    """The full resolver output for one CART label."""
    source_label: str | None
    resolved_role: str        # 'councilmember' | 'presiding' | ... | 'unknown'
    resolved_official_id: str | None
    resolved_name: str        # display form
    resolution_method: str    # 'exact-role' | 'exact-councilmember' | 'fuzzy-from:<raw>' | 'unresolved'


class SpeakerResolver:
    """Stateful resolver: build once per pipeline run, call resolve() per utterance."""

    def __init__(self, roster_path: Path):
        roster = json.loads(roster_path.read_text())
        # roster['members'] is a list of {cart_label, first_name, last_name, district, official_id, ...}
        self._councilmembers: dict[str, dict] = {
            m["cart_label"]: m for m in roster["members"]
        }

    def resolve(self, cart_label: str | None) -> Resolution:
        if cart_label is None:
            return Resolution(None, "unknown", None, "Unknown", "unresolved")

        # Path 1: canonical role label.
        if cart_label in ROLE_MAP:
            official_id, role = ROLE_MAP[cart_label]
            return Resolution(cart_label, role, official_id, cart_label, "exact-role")

        # Path 2: canonical councilmember initial+lastname.
        if cart_label in self._councilmembers:
            m = self._councilmembers[cart_label]
            display = f"{m['first_name']} {m['last_name']}"
            return Resolution(
                source_label=cart_label,
                resolved_role="councilmember",
                resolved_official_id=m["official_id"],  # may be None
                resolved_name=display,
                resolution_method="exact-councilmember",
            )

        # Path 3: fuzzy match to a canonical role (handles CART typos).
        fuzzy = fuzzy_role_match(cart_label)
        if fuzzy is not None:
            official_id, role = ROLE_MAP[fuzzy]
            return Resolution(
                source_label=cart_label,
                resolved_role=role,
                resolved_official_id=official_id,
                resolved_name=fuzzy,
                resolution_method=f"fuzzy-from:{cart_label}",
            )

        # Path 4: give up. Flag loudly in eval; do NOT guess.
        return Resolution(cart_label, "unknown", None, cart_label, "unresolved")


if __name__ == "__main__":
    # Smoke test using the shipped roster.
    import sys
    roster = Path(__file__).parent.parent.parent / "data" / "transcripts" / "roster.json"
    r = SpeakerResolver(roster)
    for label in ["Council President", "A. Nazarian", "Council Presiden", "Reporter",
                  "Y. Jurado", "Weird New Role", None]:
        print(f"{label!r:>25} -> {r.resolve(label)}")
