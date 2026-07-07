import json
import unittest
from pathlib import Path

from reports.declared_distances import annotate_declared_distance_warnings, apply_declared_distance_overrides


FIXTURE_DIR = Path(__file__).parent / "fixtures" / "declared_distances"


class DeclaredDistanceFixtureTest(unittest.TestCase):
    def test_declared_distance_fixtures(self):
        fixture_paths = sorted(FIXTURE_DIR.glob("*.json"))
        self.assertTrue(fixture_paths, "Expected declared-distance fixture files")

        for fixture_path in fixture_paths:
            with self.subTest(fixture=fixture_path.name):
                fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
                records = apply_declared_distance_overrides(fixture["runway_data"], fixture["records"])
                warnings = annotate_declared_distance_warnings(fixture["runway_data"], records)

                self.assertEqual(warnings, fixture["expected"].get("warnings", []))
                self._assert_expected_records(records, fixture["expected"].get("records", []))

    def _assert_expected_records(self, records, expected_records):
        indexed_records = {record.get("direction"): record for record in records}
        for expected in expected_records:
            direction = expected["direction"]
            self.assertIn(direction, indexed_records)
            record = indexed_records[direction]
            notes_contains = expected.get("notes_contains", [])
            for key, expected_value in expected.items():
                if key in {"direction", "notes_contains"}:
                    continue
                self.assertEqual(record.get(key), expected_value, key)
            for expected_note in notes_contains:
                self.assertIn(expected_note, record.get("notes", ""))


if __name__ == "__main__":
    unittest.main()
