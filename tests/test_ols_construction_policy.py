"""Pure policy tests for independently constructed conventional OLS contexts."""

from __future__ import annotations

import math
import unittest
from dataclasses import replace

from rulesets.annex14.profile import ANNEX14_CURRENT_OLS_PROFILE
from rulesets.cap168.profile import CAP168_PROFILE
from rulesets.easa.profile import EASA_PROFILE
from rulesets.ols_construction import (
    ANNEX14_CURRENT_OLS_CONSTRUCTION_POLICY,
    CAP168_OLS_CONSTRUCTION_POLICY,
    EASA_OLS_CONSTRUCTION_POLICY,
    OlsConstructionContext,
    OlsRunwayContext,
    OlsRunwayEndContext,
)


class Point:
    def __init__(self, x: float, y: float):
        self.x = x
        self.y = y

    def distance(self, other: "Point") -> float:
        return math.hypot(self.x - other.x, self.y - other.y)


def runway(
    index: int,
    length: float,
    *,
    arc: int = 3,
    arc_letter: str = "C",
    runway_type: str = "PA_I",
    x: float = 0.0,
    elevation: float = 100.0,
    clearway: float = 0.0,
    lda: float | None = None,
    takeoff_track_type: str = "aligned",
    takeoff_track_wkt: str = "",
    is_wide_runway: bool = False,
) -> OlsRunwayContext:
    primary = OlsRunwayEndContext(
        direction="primary",
        designator=f"{index:02d}",
        threshold_point=Point(x, 0.0),
        threshold_elevation_m=elevation,
        runway_end_elevation_m=elevation,
        approach_type=runway_type,
        classified_type=runway_type,
        clearway_length_m=clearway,
        tora_m=length,
        toda_m=length + clearway,
        asda_m=length,
        lda_m=length if lda is None else lda,
        takeoff_track_type=takeoff_track_type,
        takeoff_track_wkt=takeoff_track_wkt,
    )
    reciprocal = replace(
        primary,
        direction="reciprocal",
        designator=f"{index + 18:02d}",
        threshold_point=Point(x + length, 0.0),
    )
    return OlsRunwayContext(
        runway_id=f"RWY-{index}",
        original_index=index,
        arc_number=arc,
        arc_letter=arc_letter,
        width_m=45.0,
        physical_length_m=length,
        threshold_length_m=length,
        primary_threshold_point=primary.threshold_point,
        reciprocal_threshold_point=reciprocal.threshold_point,
        primary_physical_end_point=primary.threshold_point,
        reciprocal_physical_end_point=reciprocal.threshold_point,
        strip_parameters={"overall_width": 300.0, "extension_length": 60.0},
        ends=(primary, reciprocal),
        is_wide_runway=is_wide_runway,
        generation_data={"original_index": index},
    )


def context(*runways: OlsRunwayContext, arp: Point | None = None) -> OlsConstructionContext:
    return OlsConstructionContext(
        ruleset_id="uk_caa_cap168_edition_13",
        runways=tuple(runways),
        arp_point=arp,
        reference_elevation_datum_m=123.0,
    )


class Cap168ConstructionPolicyTests(unittest.TestCase):
    def test_longest_physical_runway_is_main_with_stable_tie_break(self):
        first = runway(1, 1800.0)
        second = runway(2, 2400.0)
        third = runway(3, 2400.0)
        self.assertEqual(context(first, second, third).main_runway.original_index, 2)

    def test_main_runway_ihs_length_and_type_bands(self):
        cases = (
            (runway(1, 900.0, arc=1, runway_type="NI"), "runway_midpoint_circle", 2000.0),
            (runway(1, 1200.0, arc=2, runway_type="NI"), "runway_midpoint_circle", 2500.0),
            (runway(1, 1799.9, arc=3, runway_type="NPA"), "runway_midpoint_circle", 4000.0),
            (runway(1, 1800.0, arc=3, runway_type="NPA"), "strip_end_racetrack", 4000.0),
        )
        for item, shape, radius in cases:
            with self.subTest(length=item.physical_length_m, arc=item.arc_number):
                plan = CAP168_OLS_CONSTRUCTION_POLICY.ihs_plan(context(item), item)
                self.assertEqual(plan["shape"], shape)
                self.assertEqual(plan["radius"], radius)

    def test_subsidiary_runway_uses_tangent_join_only_when_applicable(self):
        main = runway(1, 2200.0, x=0.0)
        near = runway(2, 1900.0, x=2500.0)
        far = runway(3, 1900.0, x=10000.0)
        short = runway(4, 1700.0, x=500.0)
        ctx = context(main, near, far, short)
        self.assertEqual(CAP168_OLS_CONSTRUCTION_POLICY.ihs_plan(ctx, near)["radius"], 3000.0)
        self.assertEqual(CAP168_OLS_CONSTRUCTION_POLICY.ihs_plan(ctx, far)["shape"], "not_applicable")
        self.assertEqual(CAP168_OLS_CONSTRUCTION_POLICY.ihs_plan(ctx, short)["shape"], "not_applicable")

    def test_lowest_threshold_datum_conical_and_ohs_length_bands(self):
        short = runway(1, 1099.0, arc=1, runway_type="NI", elevation=95.0)
        short_spec = CAP168_OLS_CONSTRUCTION_POLICY.airport_wide_spec(CAP168_PROFILE, context(short))
        self.assertEqual(short_spec["ihs_elevation_amsl"], 140.0)
        self.assertEqual(short_spec["conical"]["height_extent_agl"], 35.0)
        self.assertIsNone(short_spec["ohs"])

        medium = runway(1, 1100.0, elevation=90.0)
        medium_spec = CAP168_OLS_CONSTRUCTION_POLICY.airport_wide_spec(
            CAP168_PROFILE, context(medium, arp=Point(0, 0))
        )
        self.assertEqual(medium_spec["ohs"]["radius"], 10000.0)
        self.assertEqual(medium_spec["ohs"]["elevation_amsl"], 240.0)

        long = runway(1, 1860.0)
        long_spec = CAP168_OLS_CONSTRUCTION_POLICY.airport_wide_spec(
            CAP168_PROFILE, context(long, arp=Point(0, 0))
        )
        self.assertEqual(long_spec["ohs"]["radius"], 15000.0)

    def test_tocs_origin_width_and_heading_change_rules(self):
        item = runway(
            1,
            2400.0,
            arc=3,
            clearway=180.0,
            takeoff_track_type="curved_gt_15",
            takeoff_track_wkt="LINESTRING (0 0, 16000 0)",
            is_wide_runway=True,
        )
        ctx = context(item, arp=Point(0, 0))
        params = CAP168_OLS_CONSTRUCTION_POLICY.parameters(
            CAP168_PROFILE, ctx, item, item.ends[0], 3, "PA_I", "TOCS"
        )
        self.assertEqual(params["origin_station_from_pavement_end"], 180.0)
        self.assertEqual(params["inner_edge_width"], 300.0)
        self.assertEqual(params["final_width"], 1800.0)
        approach = CAP168_OLS_CONSTRUCTION_POLICY.parameters(
            CAP168_PROFILE, ctx, item, item.ends[0], 3, "PA_I", "Approach"
        )
        self.assertEqual(approach[0]["start_width"], 300.0)

        normal = runway(2, 2400.0, arc=3)
        normal_params = CAP168_OLS_CONSTRUCTION_POLICY.parameters(
            CAP168_PROFILE, context(normal, arp=Point(0, 0)), normal, normal.ends[0], 3, "PA_I", "TOCS"
        )
        self.assertEqual(normal_params["inner_edge_width"], 180.0)

    def test_baulked_landing_uses_lda_and_code_f_width(self):
        item = runway(1, 2000.0, arc=1, lda=1700.0)
        params = CAP168_OLS_CONSTRUCTION_POLICY.parameters(
            CAP168_PROFILE, context(item, arp=Point(0, 0)), item, item.ends[0], 1, "PA_I", "BaulkedLanding"
        )
        self.assertEqual(params["start_dist_from_thr"], 1760.0)
        code_f = runway(2, 2000.0, arc=3, arc_letter="F")
        code_f_params = CAP168_OLS_CONSTRUCTION_POLICY.parameters(
            CAP168_PROFILE, context(code_f, arp=Point(0, 0)), code_f, code_f.ends[0], 3, "PA_I", "BaulkedLanding"
        )
        self.assertEqual(code_f_params["width"], code_f_params["code_letter_f_width"])

    def test_non_aligned_tracks_require_explicit_geometry(self):
        item = runway(1, 2000.0, takeoff_track_type="offset")
        errors = CAP168_OLS_CONSTRUCTION_POLICY.validate(context(item, arp=Point(0, 0)))
        self.assertTrue(any("takeoff track geometry" in error for error in errors))


class OtherConventionalPolicyTests(unittest.TestCase):
    def test_easa_tocs_clearway_turning_and_guidance_ohs(self):
        item = runway(
            1,
            2200.0,
            arc=3,
            clearway=200.0,
            takeoff_track_type="curved_gt_15",
            takeoff_track_wkt="LINESTRING (0 0, 16000 0)",
        )
        ctx = replace(context(item), ruleset_id="easa_cs_adr_dsn_issue_7")
        params = EASA_OLS_CONSTRUCTION_POLICY.parameters(
            EASA_PROFILE, ctx, item, item.ends[0], 3, "PA_I", "TOCS"
        )
        self.assertEqual(params["origin_station_from_pavement_end"], 200.0)
        self.assertEqual(params["inner_edge_width"], params["inner_edge_width_clearway"])
        self.assertEqual(params["final_width"], params["final_width_turning"])
        spec = EASA_OLS_CONSTRUCTION_POLICY.airport_wide_spec(EASA_PROFILE, ctx)
        self.assertEqual(spec["ohs"]["applicability"], "guidance_only")
        self.assertFalse(spec["extend_conical_to_ohs"])

    def test_easa_variable_approach_meets_ihs_then_uses_remaining_length(self):
        item = runway(1, 2200.0, arc=3, runway_type="NPA", elevation=100.0)
        ctx = replace(context(item), ruleset_id="easa_cs_adr_dsn_issue_7")
        sections = EASA_OLS_CONSTRUCTION_POLICY.parameters(
            EASA_PROFILE, ctx, item, item.ends[0], 3, "NPA", "Approach"
        )
        self.assertEqual(sections[0]["length"], 3000.0)
        self.assertAlmostEqual(sections[1]["length"], 320.0, places=6)
        self.assertAlmostEqual(sections[2]["length"], 11680.0, places=6)
        self.assertEqual(sum(section["length"] for section in sections), 15000.0)

    def test_current_annex14_uses_source_loaded_tables_and_clearway_tocs(self):
        item = runway(
            1,
            2000.0,
            arc=3,
            runway_type="PA_I",
            clearway=240.0,
            takeoff_track_type="curved_gt_15",
            takeoff_track_wkt="LINESTRING (0 0, 16000 0)",
        )
        ctx = replace(context(item), ruleset_id="icao_annex14_vol1_current_ols")
        errors = ANNEX14_CURRENT_OLS_CONSTRUCTION_POLICY.validate(ctx)
        self.assertTrue(ANNEX14_CURRENT_OLS_CONSTRUCTION_POLICY.source_ready)
        self.assertEqual(errors, ())
        approach = ANNEX14_CURRENT_OLS_PROFILE.ols_parameters(3, "PA_I", "Approach")
        self.assertEqual(approach[0]["start_width"], 280.0)
        self.assertEqual([section["length"] for section in approach], [3000.0, 3600.0, 8400.0])
        tocs = ANNEX14_CURRENT_OLS_CONSTRUCTION_POLICY.parameters(
            ANNEX14_CURRENT_OLS_PROFILE,
            ctx,
            item,
            item.ends[0],
            3,
            "PA_I",
            "TOCS",
        )
        self.assertEqual(tocs["origin_station_from_pavement_end"], 240.0)
        self.assertEqual(tocs["final_width"], 1800.0)

    def test_current_annex14_airport_wide_and_code_f_ofz(self):
        item = runway(1, 2000.0, arc=3, arc_letter="F", runway_type="PA_I")
        ctx = replace(context(item), ruleset_id="icao_annex14_vol1_current_ols")
        spec = ANNEX14_CURRENT_OLS_CONSTRUCTION_POLICY.airport_wide_spec(
            ANNEX14_CURRENT_OLS_PROFILE,
            ctx,
        )
        self.assertEqual(spec["ihs_elevation_amsl"], 168.0)
        self.assertEqual(spec["conical"]["height_extent_agl"], 100.0)
        self.assertFalse(spec["extend_conical_to_ohs"])
        self.assertIsNone(spec["ohs"])
        inner_approach = ANNEX14_CURRENT_OLS_CONSTRUCTION_POLICY.parameters(
            ANNEX14_CURRENT_OLS_PROFILE,
            ctx,
            item,
            item.ends[0],
            3,
            "PA_I",
            "InnerApproach",
        )
        self.assertEqual(inner_approach["width"], 140.0)
        balked = ANNEX14_CURRENT_OLS_CONSTRUCTION_POLICY.parameters(
            ANNEX14_CURRENT_OLS_PROFILE,
            ctx,
            item,
            item.ends[0],
            3,
            "PA_I",
            "BalkedLanding",
        )
        self.assertEqual(balked["width"], 140.0)
        self.assertEqual(
            balked["start_dist_rule"],
            "1800_m_or_end_of_runway_strip_whichever_is_less",
        )

    def test_current_annex14_strip_and_clearway_dependency_bands(self):
        expected_non_instrument = {
            1: (60.0, 60.0, 30.0),
            2: (80.0, 80.0, 60.0),
            3: (110.0, 110.0, 60.0),
            4: (150.0, 150.0, 60.0),
        }
        for code, expected in expected_non_instrument.items():
            with self.subTest(code=code):
                params = ANNEX14_CURRENT_OLS_PROFILE.strip_parameters(code, "NI", 30.0)
                self.assertEqual(
                    (
                        params["overall_width"],
                        params["graded_width"],
                        params["extension_length"],
                    ),
                    expected,
                )

        instrument = ANNEX14_CURRENT_OLS_PROFILE.strip_parameters(3, "PA_I", 45.0)
        self.assertEqual(instrument["overall_width"], 280.0)
        self.assertEqual(instrument["graded_width"], 150.0)
        clearways = ANNEX14_CURRENT_OLS_PROFILE.clearway_parameters(
            strip_overall_width=instrument["overall_width"],
            physical_length=1000.0,
            clearway_primary_input=600.0,
            clearway_reciprocal_input=100.0,
            is_instrument_runway=True,
        )
        self.assertEqual(clearways["primary"]["length_m"], 500.0)
        self.assertTrue(clearways["primary"]["capped"])
        self.assertEqual(clearways["primary"]["width_m"], 150.0)


if __name__ == "__main__":
    unittest.main()
