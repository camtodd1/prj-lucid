import unittest

from dimensions import agl_dimensions as legacy_agl_dimensions
from dimensions import ols_dimensions as legacy_ols_dimensions
from rulesets.mos139 import classification, lighting, ols_surfaces, physical_data, taxiway
from rulesets.registry import (
    DEFAULT_RULESET_ID,
    get_ruleset_profile,
    iter_ruleset_profiles,
    normalize_ruleset_id,
)


class RulesetRegistryTest(unittest.TestCase):
    def test_default_ruleset_is_mos139_2019(self):
        self.assertEqual(DEFAULT_RULESET_ID, "mos139_2019")
        self.assertEqual(get_ruleset_profile().id, "mos139_2019")

    def test_legacy_mos139_alias_normalizes_to_canonical_id(self):
        self.assertEqual(normalize_ruleset_id("MOS139"), "mos139_2019")
        self.assertEqual(get_ruleset_profile("MOS139").id, "mos139_2019")

    def test_structured_payload_normalizes_to_canonical_id(self):
        self.assertEqual(normalize_ruleset_id({"id": "MOS139"}), "mos139_2019")

    def test_profiles_expose_capabilities(self):
        profile = get_ruleset_profile("mos139_2019")
        self.assertTrue(profile.supports("ols.airport_wide"))
        self.assertEqual(profile.capability_status("ols.controlling_lower_envelope"), "experimental")

    def test_mos139_adapter_matches_ruleset_ols_helpers(self):
        profile = get_ruleset_profile("mos139_2019")
        self.assertEqual(
            profile.classify_runway_type("Precision Approach CAT I"),
            classification.get_runway_type_abbr("Precision Approach CAT I"),
        )
        self.assertEqual(
            profile.strip_parameters(3, "PA_I", 45.0),
            physical_data.get_strip_params(3, "PA_I", 45.0),
        )
        self.assertEqual(
            profile.resa_parameters(3, "PA_I", "NI"),
            physical_data.get_resa_params(3, "PA_I", "NI"),
        )
        self.assertEqual(
            profile.ols_parameters(3, "Precision Approach CAT I", "APPROACH"),
            ols_surfaces.get_ols_params(3, "Precision Approach CAT I", "APPROACH"),
        )
        self.assertEqual(
            profile.taxiway_separation_offset(3, "C", "Precision Approach CAT I"),
            taxiway.get_taxiway_separation_offset(3, "C", "Precision Approach CAT I"),
        )

    def test_mos139_threshold_marking_params(self):
        profile = get_ruleset_profile("mos139_2019")
        self.assertEqual(profile.threshold_marking_params(30.0), (8, 1.5))
        self.assertEqual(profile.threshold_marking_params(45.0), (12, 1.7))
        self.assertEqual(profile.threshold_marking_params(30.005), (8, 1.5))
        self.assertIsNone(profile.threshold_marking_params(40.0))

    def test_mos139_centreline_marking_width(self):
        profile = get_ruleset_profile("mos139_2019")
        self.assertEqual(
            profile.centreline_marking_width(4, "Non-Precision Approach (NPA)", "Non-Instrument (NI)"),
            0.45,
        )
        self.assertEqual(
            profile.centreline_marking_width(2, "Non-Precision Approach (NPA)", "Non-Instrument (NI)"),
            0.3,
        )
        self.assertEqual(
            profile.centreline_marking_width(3, "Precision Approach CAT II/III", "Precision Approach CAT I"),
            0.9,
        )

    def test_mos139_aiming_point_rule(self):
        profile = get_ruleset_profile("mos139_2019")
        self.assertEqual(
            profile.aiming_point_rule(45.0, 700.0, "Precision Approach CAT I"),
            (150.0, 30.0, 4.0, 6.0, "MOS 8.22(3)"),
        )
        self.assertEqual(
            profile.aiming_point_rule(45.0, 2400.0, "Precision Approach CAT I"),
            (400.0, 45.0, 9.0, 23.0, "MOS 8.22(3)"),
        )
        self.assertEqual(
            profile.aiming_point_rule(30.0, 1800.0, "Non-Instrument (NI)"),
            (300.0, 45.0, 6.0, 17.0, "MOS 8.22(8)"),
        )
        self.assertIsNone(profile.aiming_point_rule(23.0, 1800.0, "Non-Instrument (NI)"))

    def test_mos139_touchdown_zone_offsets(self):
        profile = get_ruleset_profile("mos139_2019")
        self.assertEqual(profile.touchdown_zone_offsets(800.0), [300.0])
        self.assertEqual(profile.touchdown_zone_offsets(1200.0), [150.0, 300.0, 450.0, 600.0])
        self.assertEqual(
            profile.touchdown_zone_offsets(2400.0),
            [150.0, 300.0, 450.0, 600.0, 750.0, 900.0],
        )

    def test_mos139_runway_holding_position_rule(self):
        profile = get_ruleset_profile("mos139_2019")
        self.assertEqual(
            profile.runway_holding_position_rule(3, "Precision Approach CAT I"),
            (90.0, "MOS 8.39(7); Table 6.56(1)"),
        )
        self.assertEqual(
            profile.runway_holding_position_rule(1, "Non-Precision Approach (NPA)"),
            (40.0, "MOS 8.39(7); Table 6.56(1)"),
        )
        self.assertIsNone(profile.runway_holding_position_rule(1, "Precision Approach CAT II/III"))

    def test_mos139_adapter_matches_ruleset_agl_helpers(self):
        profile = get_ruleset_profile("mos139_2019")
        runway_type = "Precision Approach CAT I"
        for constant_name in [
            "MOS_REF_RUNWAY_EDGE",
            "RUNWAY_EDGE_INSTRUMENT_SPACING_M",
            "RUNWAY_LIGHTING_MIN_WIDTH_M",
            "PRECISION_THRESHOLD_MAX_SPACING_M",
            "RUNWAY_CENTRELINE_MAX_OFFSET_M",
            "TDZ_LENGTH_M",
            "TDZ_MARKING_LENGTH_M",
            "LIGHT_COLOUR_VARIABLE_WHITE",
            "LIGHT_COLOUR_FLASHING_WHITE",
        ]:
            self.assertEqual(profile.agl_value(constant_name), getattr(lighting, constant_name))
        self.assertEqual(
            profile.runway_type_supports_agl(runway_type),
            lighting.runway_type_supports_agl(runway_type),
        )
        self.assertEqual(profile.runway_is_precision(runway_type), lighting.runway_is_precision(runway_type))
        self.assertEqual(
            profile.runway_edge_spacing_for_end("Non-Precision Approach (NPA)"),
            lighting.runway_edge_spacing_for_end("Non-Precision Approach (NPA)"),
        )
        self.assertEqual(
            profile.threshold_light_count_for_end(runway_type, 45.0),
            lighting.threshold_light_count_for_end(runway_type, 45.0),
        )
        self.assertEqual(
            profile.runway_end_light_count_for_end("Precision Approach CAT II/III", 45.0),
            lighting.runway_end_light_count_for_end("Precision Approach CAT II/III", 45.0),
        )
        self.assertEqual(
            profile.temp_displaced_threshold_lights_per_side(30.0),
            lighting.temp_displaced_threshold_lights_per_side(30.0),
        )
        self.assertEqual(
            profile.runway_centreline_required("Non-Instrument (NI)", "Precision Approach CAT II/III", False),
            lighting.runway_centreline_required("Non-Instrument (NI)", "Precision Approach CAT II/III", False),
        )
        self.assertEqual(
            profile.runway_centreline_recommended("Precision Approach CAT I", "Non-Instrument (NI)", 60.0),
            lighting.runway_centreline_recommended("Precision Approach CAT I", "Non-Instrument (NI)", 60.0),
        )
        self.assertEqual(profile.runway_centreline_spacing(True), lighting.runway_centreline_spacing(True))
        self.assertEqual(
            profile.approach_profile_for_end("Precision Approach CAT II/III"),
            lighting.approach_profile_for_end("Precision Approach CAT II/III"),
        )
        self.assertEqual(
            profile.approach_profile_for_end("Non-Instrument (NI)"),
            lighting.approach_profile_for_end("Non-Instrument (NI)"),
        )

    def test_legacy_dimension_shims_forward_to_mos139_sources(self):
        self.assertEqual(
            legacy_ols_dimensions.get_runway_type_abbr("Precision Approach CAT I"),
            classification.get_runway_type_abbr("Precision Approach CAT I"),
        )
        self.assertEqual(
            legacy_agl_dimensions.RUNWAY_LIGHTING_MIN_WIDTH_M,
            lighting.RUNWAY_LIGHTING_MIN_WIDTH_M,
        )
        self.assertEqual(
            legacy_agl_dimensions.approach_profile_for_end("Precision Approach CAT II/III"),
            lighting.approach_profile_for_end("Precision Approach CAT II/III"),
        )

    def test_registry_has_ui_profiles(self):
        profiles = list(iter_ruleset_profiles())
        self.assertGreaterEqual(len(profiles), 1)
        self.assertEqual(profiles[0].display_name, "MOS139 (current)")


if __name__ == "__main__":
    unittest.main()
