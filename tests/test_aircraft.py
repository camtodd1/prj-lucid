"""Bundled aircraft identity, unit conversion and legacy input checks."""

import math
import unittest

from core.aircraft import aircraft_gear_span, aircraft_registry


class AircraftRegistryTests(unittest.TestCase):
    def test_registry_preserves_source_records_and_metric_dimensions(self):
        aircraft = aircraft_registry()
        self.assertEqual(len(aircraft), 388)
        self.assertEqual({int(row["source_row"]) for row in aircraft.values()}, set(range(2, 390)))
        for row in aircraft.values():
            span = float(row["outer_main_gear_wheel_span_m"])
            self.assertTrue(math.isfinite(span) and span > 0, row["id"])
        a320 = aircraft["A320"]
        self.assertEqual(float(a320["outer_main_gear_wheel_span_m"]), 29.4 * 0.3048)
        self.assertAlmostEqual(float(a320["wingspan_m_without_winglets_sharklets"]), 111.9 * 0.3048)
        self.assertAlmostEqual(float(a320["wingspan_m_with_winglets_sharklets"]), 117.5 * 0.3048)
        self.assertAlmostEqual(float(a320["mtow_kg"]), 171961 * 0.45359237)
        self.assertEqual(a320["faa_adg"], "III")
        self.assertEqual(aircraft["C172"]["wingspan_m_with_winglets_sharklets"], "")
        self.assertEqual(aircraft["A10"]["malw_kg"], "")

    def test_aircraft_selection_overrides_legacy_dimension_without_guessing(self):
        self.assertAlmostEqual(aircraft_gear_span({
            "design_aircraft_id": "B738", "outer_main_gear_wheel_span_m": 99,
        }), 23 * 0.3048)
        self.assertEqual(aircraft_gear_span({"outer_main_gear_wheel_span_m": "7"}), 7.0)
        self.assertIsNone(aircraft_gear_span({}))
        with self.assertRaisesRegex(ValueError, "unavailable"):
            aircraft_gear_span({"design_aircraft_id": "UNKNOWN"})
