"""Shared test scaffolding: builds a throwaway repo layout under a temp
directory from tests/fixtures/, so tests exercise the real builder code
against small, known data instead of the actual published dataset — and
never touch the real committed data/ files. No test in this suite makes a
live network call; anything that hits Socrata in production code paths is
exercised here only via socrata.fetch_dataset(use_cache_only=True) against a
fixture cache file, or is simply not exercised.
"""

from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path

FIXTURES = Path(__file__).resolve().parent / "fixtures"
REPO_ROOT = Path(__file__).resolve().parent.parent  # la-money-votes/


class TempRepo:
    """A throwaway la-money-votes/ layout under a temp dir, seeded from
    tests/fixtures/. `.root` is the temp la-money-votes/ directory."""

    def __init__(self):
        self._tmpdir = tempfile.mkdtemp(prefix="cyp-test-")
        self.root = Path(self._tmpdir) / "la-money-votes"
        (self.root / "data" / "officials").mkdir(parents=True)
        (self.root / "data" / "sources" / "records").mkdir(parents=True)
        (self.root / "data" / "raw" / ".cache").mkdir(parents=True)
        # Schemas are stable, shared documentation -- reuse the real ones
        # rather than duplicating them per-test-run.
        shutil.copytree(REPO_ROOT / "data" / "schemas", self.root / "data" / "schemas")

        shutil.copy(FIXTURES / "officials.json", self.root / "data" / "officials.json")
        shutil.copy(FIXTURES / "registry.json", self.root / "data" / "sources" / "registry.json")
        for item in (FIXTURES / "records").glob("*.json"):
            shutil.copy(item, self.root / "data" / "sources" / "records" / item.name)
        shutil.copy(FIXTURES / "contributions.csv", self.root / "data" / "raw" / "contributions.csv")
        shutil.copy(FIXTURES / "statements_filed.csv", self.root / "data" / "raw" / "statements_filed.csv")

        for official in json.loads((self.root / "data" / "officials.json").read_text()):
            (self.root / "data" / "officials" / official["id"]).mkdir(parents=True, exist_ok=True)

    def cleanup(self):
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    def path(self, *parts) -> Path:
        return self.root.joinpath(*parts)


def patch_module_root(module, new_root: Path, extra_attrs: dict | None = None):
    """Monkeypatch a script module's ROOT-derived path constants to point at
    a TempRepo instead of the real repo. Returns the original values so the
    caller can restore them in a finally block.
    """
    saved = {}
    attrs = {"ROOT": new_root}
    if extra_attrs:
        attrs.update(extra_attrs)
    for name, value in attrs.items():
        saved[name] = getattr(module, name)
        setattr(module, name, value)
    return saved


def restore_module_attrs(module, saved: dict):
    for name, value in saved.items():
        setattr(module, name, value)
