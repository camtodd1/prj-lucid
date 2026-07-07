import unittest

from reports.declared_distances import annotate_declared_distance_warnings, apply_declared_distance_overrides
from reports.runway_summary import build_runway_summaries


class DeclaredDistanceWarningTest(unittest.TestCase):
    def test_no_overrides_keep_calculated_values(self):
        runway = {"short_name": "05/23"}
        records = [
            {
                "direction": "primary",
                "end_desig": "05",
                "tora_m": 2000.0,
                "toda_m": 2100.0,
                "asda_m": 2050.0,
                "lda_m": 1900.0,
            }
        ]

        updated = apply_declared_distance_overrides(runway, records)

        self.assertEqual(updated, records)
        self.assertEqual(records[0]["tora_m"], 2000.0)
        self.assertEqual(records[0]["calc_tora_m"], 2000.0)
        self.assertEqual(records[0]["calc_src"], "calculated")

    def test_partial_overrides_replace_only_supplied_values(self):
        runway = {
            "short_name": "05/23",
            "tora_override_1": 1950.0,
            "asda_override_1": 2025.0,
            "declared_distance_source": "AIP AD 2 YSMK",
            "declared_distance_notes": "Reduced due to obstacle assessment",
        }
        records = [
            {
                "direction": "primary",
                "end_desig": "05",
                "tora_m": 2000.0,
                "toda_m": 2100.0,
                "asda_m": 2050.0,
                "lda_m": 1900.0,
            }
        ]

        apply_declared_distance_overrides(runway, records)

        self.assertEqual(records[0]["tora_m"], 1950.0)
        self.assertEqual(records[0]["toda_m"], 2100.0)
        self.assertEqual(records[0]["asda_m"], 2025.0)
        self.assertEqual(records[0]["calc_tora_m"], 2000.0)
        self.assertEqual(records[0]["calc_asda_m"], 2050.0)
        self.assertEqual(records[0]["calc_src"], "override")
        self.assertEqual(records[0]["override_fields"], "TORA, ASDA")
        self.assertIn("Source: AIP AD 2 YSMK", records[0]["notes"])
        self.assertIn("Reduced due to obstacle assessment", records[0]["notes"])

    def test_summary_includes_declared_distance_provenance(self):
        runway = {
            "short_name": "05/23",
            "declared_distance_source": "AIP AD 2 YSMK",
            "declared_distance_notes": "Published values verified",
            "declared_distances": [],
        }

        summary = build_runway_summaries([runway])[0]

        self.assertIn("Declared-distance source: AIP AD 2 YSMK", summary["warnings"])
        self.assertIn("Declared-distance notes: Published values verified", summary["warnings"])

    def test_overrides_without_source_warn(self):
        runway = {
            "short_name": "05/23",
            "tora_override_1": 1950.0,
        }
        records = [
            {
                "direction": "primary",
                "end_desig": "05",
                "physical_len_m": 2000.0,
                "threshold_len_m": 2000.0,
                "takeoff_available": True,
                "landing_available": True,
                "tora_m": 2000.0,
                "toda_m": 2100.0,
                "asda_m": 2050.0,
                "lda_m": 1900.0,
            }
        ]

        apply_declared_distance_overrides(runway, records)
        warnings = annotate_declared_distance_warnings(runway, records)

        self.assertIn("05/23 05: declared-distance overrides are used but no source is recorded.", warnings)
        self.assertIn("no source is recorded", records[0]["notes"])

    def test_override_relationship_warnings_use_effective_values(self):
        runway = {
            "short_name": "05/23",
            "toda_override_1": 1900.0,
            "asda_override_1": 1800.0,
            "declared_distance_source": "Manual test source",
        }
        records = [
            {
                "direction": "primary",
                "end_desig": "05",
                "physical_len_m": 2000.0,
                "threshold_len_m": 2000.0,
                "takeoff_available": True,
                "landing_available": True,
                "tora_m": 2000.0,
                "toda_m": 2100.0,
                "asda_m": 2050.0,
                "lda_m": 1900.0,
            }
        ]

        apply_declared_distance_overrides(runway, records)
        warnings = annotate_declared_distance_warnings(runway, records)

        self.assertIn("05/23 05: TODA is less than TORA.", warnings)
        self.assertIn("05/23 05: ASDA is less than TORA.", warnings)

    def test_valid_declared_distances_have_no_warnings(self):
        runway = {
            "short_name": "05/23",
            "thr_displaced_1": 100.0,
            "thr_displaced_2": 50.0,
        }
        records = [
            {
                "end_desig": "05",
                "physical_len_m": 2000.0,
                "threshold_len_m": 1850.0,
                "takeoff_available": True,
                "landing_available": True,
                "clearway_m": 200.0,
                "stopway_m": 100.0,
                "tora_m": 2000.0,
                "toda_m": 2200.0,
                "asda_m": 2100.0,
                "lda_m": 1900.0,
            }
        ]

        self.assertEqual(annotate_declared_distance_warnings(runway, records), [])
        self.assertEqual(records[0]["notes"], "")

    def test_takeoff_unavailable_warns_when_clearway_or_stopway_entered(self):
        runway = {"short_name": "05/23"}
        records = [
            {
                "end_desig": "05",
                "physical_len_m": 2000.0,
                "threshold_len_m": 2000.0,
                "takeoff_available": False,
                "landing_available": True,
                "clearway_m": 150.0,
                "clearway_input_m": 150.0,
                "stopway_m": 80.0,
                "stopway_input_m": 80.0,
                "tora_m": None,
                "toda_m": None,
                "asda_m": None,
                "lda_m": 2000.0,
            }
        ]

        warnings = annotate_declared_distance_warnings(runway, records)

        self.assertIn(
            "05/23 05: takeoff is unavailable but clearway/stopway values are entered; TODA/ASDA remain blank.",
            warnings,
        )
        self.assertIn("takeoff is unavailable", records[0]["notes"])

    def test_takeoff_unavailable_ignores_effective_clearway_default(self):
        runway = {"short_name": "05/23"}
        records = [
            {
                "end_desig": "05",
                "physical_len_m": 2000.0,
                "threshold_len_m": 2000.0,
                "takeoff_available": False,
                "landing_available": True,
                "clearway_m": 60.0,
                "clearway_input_m": 0.0,
                "stopway_m": 0.0,
                "stopway_input_m": 0.0,
                "tora_m": None,
                "toda_m": None,
                "asda_m": None,
                "lda_m": 2000.0,
            }
        ]

        warnings = annotate_declared_distance_warnings(runway, records)

        self.assertEqual(warnings, [])
        self.assertEqual(records[0]["notes"], "")

    def test_impossible_distance_relationships_are_reported(self):
        runway = {
            "short_name": "05/23",
            "thr_displaced_1": 1100.0,
            "thr_displaced_2": 950.0,
        }
        records = [
            {
                "end_desig": "05",
                "physical_len_m": 2000.0,
                "threshold_len_m": -50.0,
                "takeoff_available": True,
                "landing_available": True,
                "clearway_m": 0.0,
                "stopway_m": 0.0,
                "tora_m": 2000.0,
                "toda_m": 1990.0,
                "asda_m": 1980.0,
                "lda_m": 2050.0,
            }
        ]

        warnings = annotate_declared_distance_warnings(runway, records)

        self.assertIn("05/23: threshold-to-threshold length is not positive.", warnings)
        self.assertIn(
            "05/23: combined displaced thresholds (2050 m) leave no positive threshold-to-threshold landing length.",
            warnings,
        )
        self.assertIn("05/23 05: TODA is less than TORA.", warnings)
        self.assertIn("05/23 05: ASDA is less than TORA.", warnings)
        self.assertIn("05/23 05: LDA exceeds physical runway length.", warnings)

    def test_existing_notes_are_preserved(self):
        runway = {"short_name": "05/23"}
        records = [
            {
                "end_desig": "05",
                "physical_len_m": 2000.0,
                "threshold_len_m": 2000.0,
                "takeoff_available": True,
                "landing_available": True,
                "tora_m": None,
                "toda_m": None,
                "asda_m": None,
                "lda_m": None,
                "notes": "Published data unavailable",
            }
        ]

        warnings = annotate_declared_distance_warnings(runway, records)

        self.assertIn("Published data unavailable", records[0]["notes"])
        self.assertIn("05/23 05: takeoff is available but TORA is missing or non-positive.", warnings)
        self.assertIn("05/23 05: landing is available but LDA is missing or non-positive.", warnings)


if __name__ == "__main__":
    unittest.main()
