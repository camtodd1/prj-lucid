"""QGIS-facing checks against the independent OLS source oracle fixture."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

try:
    from qgis.core import QgsGeometry, QgsPointXY, QgsRectangle

    from guidelines.controlling_ols_engine import (
        ControllingOlsCandidate,
        PlanarControllingOlsEngine,
        axis_elevation_evaluator,
        conical_elevation_evaluator,
    )

    QGIS_AVAILABLE = True
except ImportError:
    QGIS_AVAILABLE = False


MANIFEST_PATH = Path(__file__).parent / "fixtures" / "ols" / "source_validation_v1.json"


@unittest.skipUnless(QGIS_AVAILABLE, "QGIS runtime is required")
class OlsSourceValidationQgisTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with MANIFEST_PATH.open("r", encoding="utf-8") as handle:
            cls.manifest = json.load(handle)
        cls.elevation_tolerance = cls.manifest["tolerances"]["production_evaluator_elevation_m"]
        cls.distance_tolerance = cls.manifest["tolerances"]["production_transition_distance_m"]

    def test_production_axis_evaluators_match_independent_mos_checkpoints(self):
        case = self.manifest["analytical_cases"]["mos139_npa_code3"]
        checkpoints = {
            item["station_m"]: item["expected_elevation_m"] for item in case["approach"]["elevation_checkpoints"]
        }
        evaluators = (
            (0.0, 110.0, 0.02, 3000.0, (0.0, 1000.0, 3000.0)),
            (3000.0, 170.0, 0.025, 3600.0, (5000.0, 6600.0)),
            (6600.0, 260.0, 0.0, 8400.0, (10000.0,)),
        )
        for origin_x_m, origin_elevation_m, slope, max_distance_m, stations_m in evaluators:
            evaluator = axis_elevation_evaluator(
                QgsPointXY(origin_x_m, 0.0),
                90.0,
                origin_elevation_m,
                slope,
                max_distance_m,
            )
            for station_m in stations_m:
                with self.subTest(station_m=station_m):
                    actual_m = evaluator(QgsPointXY(station_m, 25.0))
                    self.assertIsNotNone(actual_m)
                    self.assertAlmostEqual(actual_m, checkpoints[station_m], delta=self.elevation_tolerance)

    def test_production_conical_evaluator_matches_independent_equal_height_offsets(self):
        case = self.manifest["analytical_cases"]["mos139_npa_code3"]
        conical = case["inner_horizontal_and_conical"]
        base = QgsGeometry.fromRect(QgsRectangle(-1000.0, -1000.0, 0.0, 1000.0))
        evaluator = conical_elevation_evaluator(
            base,
            conical["inner_horizontal_expected_elevation_m"],
            conical["conical_slope"],
            conical["conical_height_extent_m"] / conical["conical_slope"],
        )
        for checkpoint in conical["contour_checkpoints"]:
            point = QgsPointXY(checkpoint["expected_offset_from_ihs_m"], 0.0)
            actual_m = evaluator(point)
            self.assertIsNotNone(actual_m)
            self.assertAlmostEqual(actual_m, checkpoint["elevation_m"], delta=self.elevation_tolerance)

    def test_production_axis_evaluator_matches_independent_cap168_section_checkpoints(self):
        case = self.manifest["analytical_cases"]["cap168_pa_code1"]
        sections = case["approach"]["sections"]
        expected = {
            item["station_m"]: item["expected_elevation_m"] for item in case["approach"]["elevation_checkpoints"]
        }
        start_m = 0.0
        start_elevation_m = case["assumptions"]["approach_inner_edge_elevation_m"]
        for section in sections:
            evaluator = axis_elevation_evaluator(
                QgsPointXY(start_m, 0.0),
                90.0,
                start_elevation_m,
                section["slope"],
                section["length_m"],
            )
            end_m = start_m + section["length_m"]
            for station_m, expected_elevation_m in expected.items():
                if start_m < station_m <= end_m:
                    actual_m = evaluator(QgsPointXY(station_m, 20.0))
                    self.assertIsNotNone(actual_m)
                    self.assertAlmostEqual(actual_m, expected_elevation_m, delta=self.elevation_tolerance)
            start_elevation_m += section["length_m"] * section["slope"]
            start_m = end_m

    def test_production_evaluators_match_independent_current_annex14_checkpoints(self):
        case = self.manifest["analytical_cases"]["annex14_current_ni_code3"]
        assumptions = case["assumptions"]
        approach = case["approach"]
        approach_section = approach["sections"][0]
        approach_evaluator = axis_elevation_evaluator(
            QgsPointXY(0.0, 0.0),
            90.0,
            assumptions["approach_inner_edge_elevation_m"],
            approach_section["slope"],
            approach_section["length_m"],
        )
        for checkpoint in approach["elevation_checkpoints"]:
            actual_m = approach_evaluator(QgsPointXY(checkpoint["station_m"], 25.0))
            self.assertIsNotNone(actual_m)
            self.assertAlmostEqual(
                actual_m,
                checkpoint["expected_elevation_m"],
                delta=self.elevation_tolerance,
            )

        horizontal = case["inner_horizontal_and_conical"]
        ihs_elevation_m = horizontal["inner_horizontal_expected_elevation_m"]
        base = QgsGeometry.fromRect(QgsRectangle(-1000.0, -1000.0, 0.0, 1000.0))
        conical_evaluator = conical_elevation_evaluator(
            base,
            ihs_elevation_m,
            horizontal["conical_slope"],
            horizontal["conical_height_extent_m"] / horizontal["conical_slope"],
        )
        contour = horizontal["contour_checkpoint"]
        actual_m = conical_evaluator(
            QgsPointXY(contour["expected_offset_from_ihs_m"], 0.0)
        )
        self.assertIsNotNone(actual_m)
        self.assertAlmostEqual(actual_m, contour["elevation_m"], delta=self.elevation_tolerance)

    def test_production_curved_evaluators_agree_at_independent_intersection_points(self):
        case = self.manifest["analytical_cases"]["mos139_axis_conical_intersection"]
        assumptions = case["assumptions"]
        centre = QgsGeometry.fromPointXY(QgsPointXY(assumptions["circle_centre_x_m"], 0.0))
        circular_ihs = centre.buffer(assumptions["inner_horizontal_radius_m"], 720)
        axis = axis_elevation_evaluator(
            QgsPointXY(0.0, 0.0),
            90.0,
            assumptions["axis_base_elevation_m"],
            assumptions["axis_slope"],
            10.0,
        )
        conical = conical_elevation_evaluator(
            circular_ihs,
            assumptions["inner_horizontal_elevation_m"],
            assumptions["conical_slope"],
            10.0,
        )
        for checkpoint in case["checkpoints"]:
            with self.subTest(station_m=checkpoint["station_m"]):
                point = QgsPointXY(checkpoint["station_m"], checkpoint["expected_y_m"])
                axis_m = axis(point)
                conical_m = conical(point)
                self.assertIsNotNone(axis_m)
                self.assertIsNotNone(conical_m)
                self.assertAlmostEqual(axis_m, checkpoint["expected_elevation_m"], delta=self.elevation_tolerance)
                self.assertAlmostEqual(conical_m, checkpoint["expected_elevation_m"], delta=self.elevation_tolerance)

    def test_production_affine_transition_and_controllers_match_independent_comparison(self):
        case = self.manifest["analytical_cases"]["comparison"]
        baseline = case["baseline"]
        future = case["future"]
        domain = QgsGeometry.fromRect(QgsRectangle(0.0, 0.0, 600.0, 100.0))

        baseline_candidate = ControllingOlsCandidate(
            baseline["id"],
            "Approach",
            domain,
            axis_elevation_evaluator(
                QgsPointXY(0.0, 0.0),
                90.0,
                baseline["base_elevation_m"],
                baseline["slope"],
                600.0,
            ),
            "axis",
            {
                "origin_x": 0.0,
                "origin_y": 0.0,
                "origin_elevation_m": baseline["base_elevation_m"],
                "slope": baseline["slope"],
                "max_distance_m": 600.0,
                "azimuth_degrees": 90.0,
            },
        )
        future_candidate = ControllingOlsCandidate(
            future["id"],
            "Approach",
            domain,
            axis_elevation_evaluator(
                QgsPointXY(0.0, 0.0),
                90.0,
                future["base_elevation_m"],
                future["slope"],
                600.0,
            ),
            "axis",
            {
                "origin_x": 0.0,
                "origin_y": 0.0,
                "origin_elevation_m": future["base_elevation_m"],
                "slope": future["slope"],
                "max_distance_m": 600.0,
                "azimuth_degrees": 90.0,
            },
        )
        engine = PlanarControllingOlsEngine([baseline_candidate, future_candidate])

        transition_lines = engine._candidate_transition_lines(baseline_candidate, future_candidate)
        self.assertEqual(len(transition_lines), 1)
        points = [point for part in engine._line_parts(transition_lines[0]) for point in part]
        self.assertGreaterEqual(len(points), 2)
        expected_transition_m = next(
            checkpoint["expected_station_m"]
            for checkpoint in case["delta_contour_checkpoints"]
            if checkpoint["delta_m"] == 0.0
        )
        for point in points:
            self.assertAlmostEqual(point.x(), expected_transition_m, delta=self.distance_tolerance)

        for checkpoint in case["controller_checkpoints"]:
            controller = engine.controlling_candidate_at_xy(QgsPointXY(checkpoint["station_m"], 50.0))
            self.assertIsNotNone(controller)
            self.assertEqual(controller[0].surface_id, checkpoint["expected_controller_id"])


if __name__ == "__main__":
    unittest.main()
