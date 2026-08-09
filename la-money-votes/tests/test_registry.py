import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from pipeline import registry as reg

from .helpers import FIXTURES


class TestRegistry(unittest.TestCase):
    def setUp(self):
        self.officials = reg.load_officials(FIXTURES / "officials.json")
        self.sources_registry = reg.load_registry(FIXTURES / "registry.json")

    def test_loads_fixture_officials(self):
        self.assertEqual(reg.official_ids(self.officials), {"official-a", "official-b"})

    def test_clean_cross_reference_has_no_problems(self):
        problems = reg.validate_cross_reference(self.officials, self.sources_registry)
        self.assertEqual(problems, [])

    def test_detects_official_missing_from_registry(self):
        officials = self.officials + [{"id": "official-c", "name": "C", "office": "Test Seat C"}]
        problems = reg.validate_cross_reference(officials, self.sources_registry)
        self.assertTrue(any("official-c" in p and "no entry" in p for p in problems))

    def test_detects_orphaned_registry_entry(self):
        registry = {"schema_version": "1.0", "officials": dict(self.sources_registry["officials"])}
        registry["officials"]["official-z"] = registry["officials"]["official-a"]
        problems = reg.validate_cross_reference(self.officials, registry)
        self.assertTrue(any("official-z" in p and "not in" in p for p in problems))

    def test_detects_duplicate_official_id(self):
        officials = self.officials + [dict(self.officials[0])]
        problems = reg.validate_cross_reference(officials, self.sources_registry)
        self.assertTrue(any("duplicate official id 'official-a'" in p for p in problems))

    def test_registry_entry_returns_expected_shape(self):
        entry = reg.registry_entry(self.sources_registry, "official-a")
        self.assertEqual(entry["funding"]["committees"], ["Officer A Test Committee 2026"])
        self.assertIsNone(entry["funding"]["election_result"])

    def test_registry_entry_raises_for_unknown_id(self):
        with self.assertRaises(KeyError):
            reg.registry_entry(self.sources_registry, "does-not-exist")


if __name__ == "__main__":
    unittest.main()
