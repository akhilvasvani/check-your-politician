import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from pipeline import validation


class TestDates(unittest.TestCase):
    def test_valid_date(self):
        self.assertTrue(validation.is_valid_date("2026-01-15"))

    def test_rejects_bad_month(self):
        self.assertFalse(validation.is_valid_date("2026-13-01"))

    def test_rejects_non_date_string(self):
        self.assertFalse(validation.is_valid_date("not-a-date"))

    def test_rejects_wrong_format(self):
        self.assertFalse(validation.is_valid_date("01/15/2026"))

    def test_rejects_none(self):
        self.assertFalse(validation.is_valid_date(None))

    def test_rejects_impossible_day(self):
        self.assertFalse(validation.is_valid_date("2026-02-30"))


class TestUrls(unittest.TestCase):
    def test_valid_https_url(self):
        self.assertTrue(validation.is_valid_url("https://data.lacity.org/resource/m6g2-gc6c.json"))

    def test_rejects_non_http_scheme(self):
        self.assertFalse(validation.is_valid_url("ftp://example.com/file"))

    def test_rejects_empty(self):
        self.assertFalse(validation.is_valid_url(""))
        self.assertFalse(validation.is_valid_url(None))

    def test_domain_allowlist_accepts_known_domain(self):
        self.assertTrue(
            validation.is_valid_url("https://cityclerk.lacity.org/lacityclerkconnect/", validation.ALLOWED_SOURCE_DOMAINS)
        )

    def test_domain_allowlist_rejects_unknown_domain(self):
        self.assertFalse(validation.is_valid_url("https://evil.example.com/page", validation.ALLOWED_SOURCE_DOMAINS))

    def test_domain_allowlist_accepts_subdomain(self):
        self.assertTrue(validation.is_valid_url("https://data.lacity.org/d/m6g2-gc6c", validation.ALLOWED_SOURCE_DOMAINS))


class TestAmounts(unittest.TestCase):
    def test_valid_int(self):
        self.assertTrue(validation.is_valid_amount(100))

    def test_valid_float(self):
        self.assertTrue(validation.is_valid_amount(99.5))

    def test_negative_amount_allowed(self):
        # LA Ethics Commission data legitimately reports negative itemized
        # rows for corrections -- see validation.is_valid_amount docstring.
        self.assertTrue(validation.is_valid_amount(-500))

    def test_rejects_string(self):
        self.assertFalse(validation.is_valid_amount("100"))

    def test_rejects_bool(self):
        self.assertFalse(validation.is_valid_amount(True))

    def test_rejects_nan(self):
        self.assertFalse(validation.is_valid_amount(float("nan")))

    def test_rejects_inf(self):
        self.assertFalse(validation.is_valid_amount(float("inf")))


class TestRecordIds(unittest.TestCase):
    def test_valid_council_file(self):
        self.assertTrue(validation.is_valid_record_id("25-0542"))

    def test_valid_council_file_with_suffix(self):
        self.assertTrue(validation.is_valid_record_id("25-0600-S17"))

    def test_valid_executive_directive(self):
        self.assertTrue(validation.is_valid_record_id("ED-10"))

    def test_valid_executive_order(self):
        self.assertTrue(validation.is_valid_record_id("EO-1"))

    def test_rejects_garbage(self):
        self.assertFalse(validation.is_valid_record_id("not-a-record"))
        self.assertFalse(validation.is_valid_record_id(""))


class TestDuplicates(unittest.TestCase):
    def test_finds_duplicate_keys(self):
        items = [{"name": "A"}, {"name": "B"}, {"name": "A"}]
        self.assertEqual(validation.find_duplicates(items, key_fn=lambda i: i["name"]), ["A"])

    def test_no_duplicates(self):
        items = [{"name": "A"}, {"name": "B"}]
        self.assertEqual(validation.find_duplicates(items, key_fn=lambda i: i["name"]), [])


class TestSchemaValidator(unittest.TestCase):
    def test_required_field_missing(self):
        schema = {"type": "object", "required": ["a", "b"], "properties": {"a": {"type": "string"}, "b": {"type": "number"}}}
        problems = validation.validate_schema({"a": "x"}, schema)
        self.assertEqual(len(problems), 1)
        self.assertIn("b", problems[0])

    def test_wrong_type(self):
        schema = {"type": "object", "properties": {"a": {"type": "number"}}}
        problems = validation.validate_schema({"a": "not-a-number"}, schema)
        self.assertTrue(problems)

    def test_valid_instance_no_problems(self):
        schema = {"type": "object", "required": ["a"], "properties": {"a": {"type": "string"}}}
        self.assertEqual(validation.validate_schema({"a": "ok"}, schema), [])

    def test_array_items_validated(self):
        schema = {"type": "array", "items": {"type": "object", "required": ["x"], "properties": {"x": {"type": "string"}}}}
        problems = validation.validate_schema([{"x": "a"}, {}], schema)
        self.assertEqual(len(problems), 1)

    def test_enum_rejects_unlisted_value(self):
        schema = {"type": "string", "enum": ["won", "lost"]}
        self.assertTrue(validation.validate_schema("draw", schema))
        self.assertEqual(validation.validate_schema("won", schema), [])

    def test_additional_properties_false_flags_extra(self):
        schema = {"type": "object", "properties": {"a": {"type": "string"}}, "additionalProperties": False}
        problems = validation.validate_schema({"a": "x", "extra": 1}, schema)
        self.assertTrue(any("extra" in p for p in problems))

    def test_additional_properties_schema_validates_dynamic_keys(self):
        schema = {
            "type": "object",
            "properties": {},
            "additionalProperties": {"type": "object", "required": ["y"], "properties": {"y": {"type": "string"}}},
        }
        problems = validation.validate_schema({"key1": {"y": "ok"}, "key2": {}}, schema)
        self.assertEqual(len(problems), 1)
        self.assertIn("key2", problems[0])


if __name__ == "__main__":
    unittest.main()
