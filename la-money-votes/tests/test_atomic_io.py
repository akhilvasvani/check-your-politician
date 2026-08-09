import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from pipeline import atomic_io


class TestAtomicWriteJson(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.path = Path(self.tmpdir.name) / "nested" / "out.json"

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_creates_parent_dirs_and_writes(self):
        atomic_io.atomic_write_json(self.path, {"a": 1})
        self.assertEqual(json.loads(self.path.read_text()), {"a": 1})

    def test_no_leftover_temp_files(self):
        atomic_io.atomic_write_json(self.path, {"a": 1})
        leftovers = list(self.path.parent.glob(".*.tmp"))
        self.assertEqual(leftovers, [])

    def test_overwrites_existing_file(self):
        atomic_io.atomic_write_json(self.path, {"a": 1})
        atomic_io.atomic_write_json(self.path, {"a": 2})
        self.assertEqual(json.loads(self.path.read_text()), {"a": 2})


class TestWriteIfValid(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.path = Path(self.tmpdir.name) / "out.json"

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_writes_when_no_problems(self):
        written = atomic_io.write_if_valid(self.path, {"a": 1}, [])
        self.assertTrue(written)
        self.assertEqual(json.loads(self.path.read_text()), {"a": 1})

    def test_skips_when_problems_present(self):
        written = atomic_io.write_if_valid(self.path, {"a": 1}, ["something is wrong"])
        self.assertFalse(written)
        self.assertFalse(self.path.exists())

    def test_never_overwrites_prior_valid_file_with_invalid_payload(self):
        # This is the core guarantee the whole pipeline depends on: a bad
        # rebuild must never clobber a good previously-published file.
        atomic_io.write_if_valid(self.path, {"good": True}, [])
        written = atomic_io.write_if_valid(self.path, {"bad": True}, ["nope"])
        self.assertFalse(written)
        self.assertEqual(json.loads(self.path.read_text()), {"good": True})


if __name__ == "__main__":
    unittest.main()
