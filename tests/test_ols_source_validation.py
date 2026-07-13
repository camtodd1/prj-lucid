"""Source-backed analytical checks for OLS, CAP168, Annex 14 and comparisons."""

from __future__ import annotations

import importlib
import json
import math
import unittest
from pathlib import Path

try:
    from .ols_source_oracle import (
        affine_delta,
        circular_axis_conical_intersection_y,
        circular_conical_elevation,
        conical_elevation,
        conical_offset_for_elevation,
        controlling_identity,
        first_station_for_elevation,
        half_width_at_station,
        piecewise_axis_elevation,
        station_for_affine_delta,
        transverse_elevation,
        transverse_offset_for_elevation,
    )
except ImportError:  # unittest discovery imports test files as top-level modules.
    from ols_source_oracle import (
        affine_delta,
        circular_axis_conical_intersection_y,
        circular_conical_elevation,
        conical_elevation,
        conical_offset_for_elevation,
        controlling_identity,
        first_station_for_elevation,
        half_width_at_station,
        piecewise_axis_elevation,
        station_for_affine_delta,
        transverse_elevation,
        transverse_offset_for_elevation,
    )


MANIFEST_PATH = Path(__file__).parent / "fixtures" / "ols" / "source_validation_v1.json"


def _load_manifest() -> dict:
    with MANIFEST_PATH.open("r", encoding="utf-8") as handle:
        return json.load(handle)


class OlsSourceValidationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = _load_manifest()
        cls.elevation_tolerance = cls.manifest["tolerances"]["analytical_elevation_m"]
        cls.distance_tolerance = cls.manifest["tolerances"]["analytical_distance_m"]

    def assertSourceSubset(self, actual, expected, path="value"):
        """Recursively compare cited source facts with production parameters."""
        if isinstance(expected, dict):
            self.assertIsInstance(actual, dict, path)
            for key, expected_value in expected.items():
                self.assertIn(key, actual, f"{path}.{key}")
                self.assertSourceSubset(actual[key], expected_value, f"{path}.{key}")
            return
        if isinstance(expected, list):
            self.assertIsInstance(actual, list, path)
            self.assertEqual(len(actual), len(expected), path)
            for index, (actual_value, expected_value) in enumerate(zip(actual, expected)):
                self.assertSourceSubset(actual_value, expected_value, f"{path}[{index}]")
            return
        if isinstance(expected, float):
            self.assertTrue(
                math.isclose(
                    float(actual),
                    expected,
                    rel_tol=0.0,
                    abs_tol=self.manifest["tolerances"]["source_parameter_absolute"],
                ),
                f"{path}: expected {expected!r}, got {actual!r}",
            )
            return
        self.assertEqual(actual, expected, path)

    def test_manifest_records_authoritative_editions_and_future_applicability(self):
        documents = self.manifest["documents"]
        self.assertEqual(documents["mos139"]["compilation_date"], "2026-05-12")
        self.assertEqual(documents["mos139"]["authorised_version"], "F2026C00403")
        self.assertEqual(documents["annex14"]["edition"], "Ninth Edition")
        self.assertEqual(documents["annex14"]["future_chapter_applicability"], "2030-11-21")
        self.assertEqual(documents["cap168"]["edition"], "Thirteenth Edition")
        self.assertEqual(documents["cap168"]["current_ols_applicability_end"], "2030-11-20")
        self.assertEqual(
            [item["corrected_m"] for item in documents["cap168"]["confirmed_corrections"]],
            [60.0, 3600.0, 2500.0],
        )
        self.assertEqual(documents["cap168"]["correction_confirmation"], "user-confirmed 2026-07-13")
        self.assertEqual(len(documents["mos139"]["sha256"]), 64)
        self.assertEqual(len(documents["annex14"]["sha256"]), 64)
        self.assertEqual(len(documents["cap168"]["sha256"]), 64)

    def test_cited_source_parameters_match_production_constants(self):
        for check in self.manifest["production_parameter_checks"]:
            with self.subTest(check=check["id"], source=check["source_ref"]):
                locator = check["production"]
                module = importlib.import_module(locator["module"])
                actual = getattr(module, locator["symbol"])
                if "key" in locator:
                    key = locator["key"]
                    if locator.get("tuple_key"):
                        key = tuple(key)
                    actual = actual[key]
                self.assertSourceSubset(actual, check["expected"], check["id"])

    def test_cap168_corrected_code2_ni_ihs_is_recorded_but_context_gated(self):
        from rulesets.cap168 import ols_surfaces

        correction = ols_surfaces.IHS_PLAN_RULES["main_runway_below_1800_m_ni_code_2"]
        self.assertEqual(correction["printed_radius"], 250.0)
        self.assertEqual(correction["radius"], 2500.0)
        self.assertEqual(correction["correction_status"], "user_confirmed")
        with self.assertLogs("rulesets.cap168.ols_surfaces", level="WARNING"):
            self.assertIsNone(ols_surfaces.get_ols_params(2, "NI", "IHS"))

    def test_cap168_profile_remains_gated_while_source_lookups_are_detached(self):
        from rulesets.cap168 import ols_surfaces
        from rulesets.cap168.profile import CAP168_PROFILE

        approach = ols_surfaces.get_ols_params(1, "PA_I", "Approach")
        self.assertIsNotNone(approach)
        self.assertEqual([section["length"] for section in approach], [3000.0, 2500.0, 9500.0])
        approach[0]["length"] = -1.0
        self.assertEqual(ols_surfaces.get_ols_params(1, "PA_I", "Approach")[0]["length"], 3000.0)

        take_off = ols_surfaces.get_ols_params(3, None, "TOCS")
        self.assertEqual(take_off["final_width"], 1200.0)
        self.assertEqual(take_off["heading_change_gt_15_final_width"], 1800.0)
        self.assertEqual(ols_surfaces.get_ihs_base_height(), 45.0)

        self.assertIsNone(CAP168_PROFILE.ols_parameters(1, "PA_I", "Approach"))
        self.assertIsNone(CAP168_PROFILE.ihs_base_height())

    def test_independent_mos139_elevations_and_contour_locations(self):
        case = self.manifest["analytical_cases"]["mos139_npa_code3"]
        approach = case["approach"]
        approach_base_m = case["assumptions"]["approach_inner_edge_elevation_m"]
        for checkpoint in approach["elevation_checkpoints"]:
            actual_m = piecewise_axis_elevation(
                approach_base_m,
                checkpoint["station_m"],
                approach["sections"],
            )
            self.assertAlmostEqual(actual_m, checkpoint["expected_elevation_m"], delta=self.elevation_tolerance)

        for checkpoint in approach["contour_checkpoints"]:
            station_m = first_station_for_elevation(
                approach_base_m,
                checkpoint["elevation_m"],
                approach["sections"],
            )
            self.assertAlmostEqual(station_m, checkpoint["expected_station_m"], delta=self.distance_tolerance)
            half_width_m = half_width_at_station(
                approach["inner_edge_length_m"],
                station_m,
                approach["sections"],
            )
            self.assertAlmostEqual(half_width_m, checkpoint["expected_half_width_m"], delta=self.distance_tolerance)

        takeoff = case["take_off_climb"]
        takeoff_base_m = case["assumptions"]["take_off_inner_edge_elevation_m"]
        takeoff_contour = takeoff["contour_checkpoint"]
        self.assertAlmostEqual(
            first_station_for_elevation(takeoff_base_m, takeoff_contour["elevation_m"], takeoff["sections"]),
            takeoff_contour["expected_station_m"],
            delta=self.distance_tolerance,
        )
        self.assertAlmostEqual(
            piecewise_axis_elevation(
                takeoff_base_m,
                takeoff["end_checkpoint"]["station_m"],
                takeoff["sections"],
            ),
            takeoff["end_checkpoint"]["expected_elevation_m"],
            delta=self.elevation_tolerance,
        )

        conical = case["inner_horizontal_and_conical"]
        expected_ihs_m = (
            case["assumptions"]["reference_elevation_datum_m"] + conical["inner_horizontal_height_above_red_m"]
        )
        self.assertAlmostEqual(
            expected_ihs_m,
            conical["inner_horizontal_expected_elevation_m"],
            delta=self.elevation_tolerance,
        )
        for checkpoint in conical["contour_checkpoints"]:
            offset_m = conical_offset_for_elevation(expected_ihs_m, checkpoint["elevation_m"], conical["conical_slope"])
            self.assertAlmostEqual(offset_m, checkpoint["expected_offset_from_ihs_m"], delta=self.distance_tolerance)
            self.assertAlmostEqual(
                conical_elevation(expected_ihs_m, offset_m, conical["conical_slope"]),
                checkpoint["elevation_m"],
                delta=self.elevation_tolerance,
            )

        transitional = case["transitional"]
        transition_contour = transitional["contour_checkpoint"]
        transition_offset_m = transverse_offset_for_elevation(
            transitional["lower_edge_elevation_m"],
            transition_contour["elevation_m"],
            transitional["slope"],
        )
        self.assertAlmostEqual(
            transition_offset_m, transition_contour["expected_offset_m"], delta=self.distance_tolerance
        )
        self.assertAlmostEqual(
            transverse_elevation(
                transitional["lower_edge_elevation_m"],
                transition_offset_m,
                transitional["slope"],
            ),
            transition_contour["elevation_m"],
            delta=self.elevation_tolerance,
        )

    def test_independent_curved_axis_conical_intersection_has_equal_elevations(self):
        case = self.manifest["analytical_cases"]["mos139_axis_conical_intersection"]
        assumptions = case["assumptions"]
        for checkpoint in case["checkpoints"]:
            with self.subTest(station_m=checkpoint["station_m"]):
                y_m = circular_axis_conical_intersection_y(
                    checkpoint["station_m"],
                    assumptions["circle_centre_x_m"],
                    assumptions["inner_horizontal_radius_m"],
                    assumptions["inner_horizontal_elevation_m"],
                    assumptions["conical_slope"],
                    assumptions["axis_base_elevation_m"],
                    assumptions["axis_slope"],
                )
                self.assertAlmostEqual(y_m, checkpoint["expected_y_m"], delta=self.distance_tolerance)
                axis_elevation_m = (
                    assumptions["axis_base_elevation_m"] + assumptions["axis_slope"] * checkpoint["station_m"]
                )
                conical_elevation_m = circular_conical_elevation(
                    checkpoint["station_m"],
                    y_m,
                    assumptions["circle_centre_x_m"],
                    assumptions["inner_horizontal_radius_m"],
                    assumptions["inner_horizontal_elevation_m"],
                    assumptions["conical_slope"],
                )
                self.assertAlmostEqual(
                    axis_elevation_m, checkpoint["expected_elevation_m"], delta=self.elevation_tolerance
                )
                self.assertAlmostEqual(
                    conical_elevation_m,
                    checkpoint["expected_elevation_m"],
                    delta=self.elevation_tolerance,
                )
                self.assertAlmostEqual(
                    axis_elevation_m,
                    conical_elevation_m,
                    delta=self.manifest["tolerances"]["intersection_equality_residual_m"],
                )

    def test_independent_cap168_elevations_and_contour_locations(self):
        case = self.manifest["analytical_cases"]["cap168_pa_code1"]
        approach = case["approach"]
        base_m = case["assumptions"]["approach_inner_edge_elevation_m"]
        for checkpoint in approach["elevation_checkpoints"]:
            self.assertAlmostEqual(
                piecewise_axis_elevation(base_m, checkpoint["station_m"], approach["sections"]),
                checkpoint["expected_elevation_m"],
                delta=self.elevation_tolerance,
            )

        contour = approach["contour_checkpoint"]
        station_m = first_station_for_elevation(base_m, contour["elevation_m"], approach["sections"])
        self.assertAlmostEqual(station_m, contour["expected_station_m"], delta=self.distance_tolerance)
        self.assertAlmostEqual(
            half_width_at_station(approach["inner_edge_length_m"], station_m, approach["sections"]),
            contour["expected_half_width_m"],
            delta=self.distance_tolerance,
        )

        conical = case["inner_horizontal_and_conical"]
        expected_ihs_m = (
            case["assumptions"]["lowest_runway_threshold_elevation_m"]
            + conical["inner_horizontal_height_above_lowest_threshold_m"]
        )
        self.assertAlmostEqual(
            expected_ihs_m,
            conical["inner_horizontal_expected_elevation_m"],
            delta=self.elevation_tolerance,
        )
        conical_contour = conical["contour_checkpoint"]
        offset_m = conical_offset_for_elevation(
            expected_ihs_m,
            conical_contour["elevation_m"],
            conical["conical_slope"],
        )
        self.assertAlmostEqual(
            offset_m,
            conical_contour["expected_offset_from_ihs_m"],
            delta=self.distance_tolerance,
        )

    def test_independent_annex14_future_elevations_and_contours(self):
        case = self.manifest["analytical_cases"]["annex14_future"]
        for surface_name in (
            "ofs_instrument_approach_adg_iii",
            "oes_precision_approach",
            "oes_take_off_climb_heavy_adg_iii",
        ):
            surface = case[surface_name]
            for checkpoint in surface["elevation_checkpoints"]:
                self.assertAlmostEqual(
                    piecewise_axis_elevation(surface["base_elevation_m"], checkpoint["station_m"], surface["sections"]),
                    checkpoint["expected_elevation_m"],
                    delta=self.elevation_tolerance,
                )
            if "contour_checkpoint" in surface:
                checkpoint = surface["contour_checkpoint"]
                self.assertAlmostEqual(
                    first_station_for_elevation(
                        surface["base_elevation_m"], checkpoint["elevation_m"], surface["sections"]
                    ),
                    checkpoint["expected_station_m"],
                    delta=self.distance_tolerance,
                )

        transitional = case["ofs_transitional"]
        checkpoint = transitional["contour_checkpoint"]
        self.assertAlmostEqual(
            transverse_offset_for_elevation(
                transitional["lower_edge_elevation_m"],
                checkpoint["elevation_m"],
                transitional["slope"],
            ),
            checkpoint["expected_offset_m"],
            delta=self.distance_tolerance,
        )

        departure = case["oes_instrument_departure"]
        departure_base_m = departure["runway_elevation_at_toda_m"] + departure["inner_edge_offset_m"]
        self.assertAlmostEqual(departure_base_m, departure["expected_base_elevation_m"], delta=self.elevation_tolerance)
        for checkpoint in departure["elevation_checkpoints"]:
            self.assertAlmostEqual(
                piecewise_axis_elevation(departure_base_m, checkpoint["station_m"], departure["sections"]),
                checkpoint["expected_elevation_m"],
                delta=self.elevation_tolerance,
            )

        horizontal = case["oes_horizontal_adg_iii"]
        self.assertAlmostEqual(
            horizontal["aerodrome_elevation_m"] + horizontal["height_above_aerodrome_m"],
            horizontal["expected_elevation_m"],
            delta=self.elevation_tolerance,
        )

    def test_independent_comparison_contours_and_controlling_identity(self):
        case = self.manifest["analytical_cases"]["comparison"]
        baseline = case["baseline"]
        future = case["future"]
        for checkpoint in case["delta_contour_checkpoints"]:
            station_m = station_for_affine_delta(
                checkpoint["delta_m"],
                baseline["base_elevation_m"],
                baseline["slope"],
                future["base_elevation_m"],
                future["slope"],
            )
            self.assertAlmostEqual(station_m, checkpoint["expected_station_m"], delta=self.distance_tolerance)
            self.assertAlmostEqual(
                affine_delta(
                    station_m,
                    baseline["base_elevation_m"],
                    baseline["slope"],
                    future["base_elevation_m"],
                    future["slope"],
                ),
                checkpoint["delta_m"],
                delta=self.elevation_tolerance,
            )

        for checkpoint in case["controller_checkpoints"]:
            station_m = checkpoint["station_m"]
            baseline_elevation_m = baseline["base_elevation_m"] + baseline["slope"] * station_m
            future_elevation_m = future["base_elevation_m"] + future["slope"] * station_m
            self.assertAlmostEqual(
                future_elevation_m - baseline_elevation_m,
                checkpoint["expected_delta_m"],
                delta=self.elevation_tolerance,
            )
            self.assertEqual(
                controlling_identity({baseline["id"]: baseline_elevation_m, future["id"]: future_elevation_m}),
                checkpoint["expected_controller_id"],
            )


if __name__ == "__main__":
    unittest.main()
