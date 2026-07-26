"""Source-backed EASA CS-ADR-DSN runway marking and lighting checks."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from rulesets.easa import lighting, markings, metadata
from rulesets.easa.profile import EASA_PROFILE


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "ols" / "easa_visual_aids_v1.json"


class EasaVisualAidsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))

    def test_capabilities_are_promoted(self):
        self.assertEqual(metadata.CAPABILITY_STATUS_BY_KEY["markings.runway"], "supported")
        self.assertEqual(metadata.CAPABILITY_STATUS_BY_KEY["lighting.runway"], "supported")
        self.assertEqual(metadata.CAPABILITY_STATUS_BY_KEY["lighting.approach"], "supported")

    def test_source_references_match_fixture(self):
        self.assertEqual(markings.EASA_RUNWAY_CENTRELINE_MARKING_REF, self.fixture["source"]["markings"]["centreline"])
        self.assertEqual(markings.EASA_THRESHOLD_MARKING_REF, self.fixture["source"]["markings"]["threshold"])
        self.assertEqual(markings.EASA_AIMING_POINT_MARKING_REF, self.fixture["source"]["markings"]["aiming_point"])
        self.assertEqual(markings.EASA_TOUCHDOWN_ZONE_MARKING_REF, self.fixture["source"]["markings"]["touchdown_zone"])
        self.assertEqual(lighting.EASA_REF_SIMPLE_APPROACH, self.fixture["source"]["lighting"]["simple_approach"])
        self.assertEqual(lighting.EASA_REF_APPROACH_CAT_I, self.fixture["source"]["lighting"]["precision_cat_i"])
        self.assertEqual(lighting.EASA_REF_APPROACH_CAT_II_III, self.fixture["source"]["lighting"]["precision_cat_ii_iii"])
        self.assertEqual(lighting.EASA_REF_RUNWAY_EDGE, self.fixture["source"]["lighting"]["runway_edge"])
        self.assertEqual(lighting.EASA_REF_THRESHOLD, self.fixture["source"]["lighting"]["threshold"])
        self.assertEqual(lighting.EASA_REF_RUNWAY_END, self.fixture["source"]["lighting"]["runway_end"])
        self.assertEqual(lighting.EASA_REF_RUNWAY_CENTRELINE, self.fixture["source"]["lighting"]["runway_centreline"])
        self.assertEqual(lighting.EASA_REF_TDZ, self.fixture["source"]["lighting"]["touchdown_zone"])
        self.assertEqual(lighting.MOS_REF_STOPWAY, self.fixture["source"]["lighting"]["stopway"])

    def test_threshold_marking_reference_is_exposed_by_profile(self):
        self.assertEqual(EASA_PROFILE.threshold_marking_ref(), markings.EASA_THRESHOLD_MARKING_REF)

    def test_centreline_and_threshold_marking_dimensions(self):
        expected = self.fixture["markings"]["centreline_width_m"]
        self.assertEqual(markings.centreline_marking_width(1, "NI", "NI"), expected["NI_code_1"])
        self.assertEqual(markings.centreline_marking_width(2, "NPA", "NPA"), expected["NPA_code_2"])
        self.assertEqual(markings.centreline_marking_width(3, "NPA", "NPA"), expected["NPA_code_3"])
        self.assertEqual(markings.centreline_marking_width(3, "PA_I", "PA_I"), expected["PA_I"])
        self.assertEqual(markings.centreline_marking_width(3, "PA_II_III", "PA_II_III"), expected["PA_II_III"])

        for width, count in self.fixture["markings"]["threshold_stripes_by_width_m"].items():
            self.assertEqual(markings.threshold_marking_params(float(width))[0], count)

    def test_aiming_point_applicability_and_lda_bands(self):
        expected = self.fixture["markings"]["aiming_point_offsets_by_lda_m"]
        for lda, offset in expected.items():
            self.assertEqual(markings.aiming_point_rule(45.0, float(lda), "PA_I", arc_num=3)[0], offset)

        self.assertIsNone(markings.aiming_point_rule(30.0, 1000.0, "PA_I", arc_num=1))
        self.assertIsNone(markings.aiming_point_rule(30.0, 1000.0, "NI", arc_num=2))
        self.assertIsNotNone(markings.aiming_point_rule(30.0, 1000.0, "NI", arc_num=3, additional_conspicuity=True))

    def test_touchdown_zone_marking_bands(self):
        for lda, offsets in self.fixture["markings"]["touchdown_zone_offsets_m"].items():
            self.assertEqual(markings.touchdown_zone_offsets(float(lda)), offsets)

    def test_runway_lighting_dimensions_and_profiles(self):
        expected = self.fixture["lighting"]
        self.assertEqual(lighting.runway_edge_spacing_for_end("Non-Instrument"), expected["edge_spacing_m"]["non_instrument"])
        self.assertEqual(lighting.runway_edge_spacing_for_end("Non-Precision"), expected["edge_spacing_m"]["instrument"])
        self.assertEqual(lighting.threshold_light_count_for_end("Non-Precision", 18.0), expected["threshold_minimum_lights"])
        self.assertEqual(lighting.threshold_light_count_for_end("Precision Approach CAT I", 30.0), 11)
        self.assertEqual(lighting.runway_end_light_count_for_end("Precision Approach CAT II/III", 30.0), 6)
        self.assertEqual(lighting.runway_end_light_count_for_end("Precision Approach CAT III", 45.0), 8)
        self.assertEqual(lighting.STOPWAY_END_MIN_LIGHTS, expected["stopway_end_minimum_lights"])
        self.assertEqual(lighting.runway_centreline_spacing(True), expected["centreline_spacing_m"]["rvr_below_350"])
        self.assertEqual(lighting.runway_centreline_spacing(False), expected["centreline_spacing_m"]["rvr_at_or_above_350"])

        self.assertEqual(lighting.approach_profile_for_end("Non-Precision")["length_m"], expected["approach_lengths_m"]["simple"])
        self.assertEqual(lighting.approach_profile_for_end("Precision Approach CAT I")["length_m"], expected["approach_lengths_m"]["cat_i"])
        self.assertEqual(lighting.approach_profile_for_end("Precision Approach CAT II/III")["length_m"], expected["approach_lengths_m"]["cat_ii_iii"])

    def test_shared_agl_generator_values_are_available_with_easa_provenance(self):
        required_names = {
            "RUNWAY_CENTRELINE_MAX_OFFSET_M",
            "MOS_REF_DISPLACED_THRESHOLD_EDGE",
            "MOS_REF_RUNWAY_EDGE",
            "MOS_REF_RUNWAY_END",
            "MOS_REF_THRESHOLD_WING_BARS",
            "MOS_REF_RTIL",
            "MOS_REF_TEMP_DISPLACED_THRESHOLD",
            "MOS_REF_STOPWAY",
            "MOS_REF_RUNWAY_CENTRELINE",
            "MOS_REF_TDZ",
            "LIGHT_COLOUR_WHITE",
            "LIGHT_COLOUR_VARIABLE_WHITE",
            "RTIL_DEFAULT_LATERAL_FROM_EDGE_LIGHTS_M",
            "TEMP_DISPLACED_THRESHOLD_SPACING_M",
            "STOPWAY_END_MIN_LIGHTS",
            "TDZ_FIRST_ROW_OFFSET_M",
            "TDZ_MARKING_LENGTH_M",
        }
        values = {name: EASA_PROFILE.agl_value(name) for name in required_names}
        self.assertEqual(values["MOS_REF_STOPWAY"], "CS ADR-DSN.M.705")
        self.assertEqual(values["MOS_REF_TEMP_DISPLACED_THRESHOLD"], "compatibility fallback")
        self.assertEqual(values["MOS_REF_RTIL"], "compatibility fallback")
        self.assertEqual(values["STOPWAY_END_MIN_LIGHTS"], 4)
        self.assertEqual(values["LIGHT_COLOUR_WHITE"], "white")


if __name__ == "__main__":
    unittest.main()
