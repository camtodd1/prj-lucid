import unittest
import importlib

from frameworks.registry import (
    DEFAULT_FRAMEWORK_ID,
    get_framework_profile,
    iter_framework_profiles,
    normalize_framework_id,
)
from core import output_structure
from core.constants import LAYER_FEATURE_BATCH_SIZE
from guidelines import guideline_constants
from guidelines.ols_constants import CONICAL_CONTOUR_INTERVAL
from rulesets.registry import get_ruleset_profile
from rulesets.context import RulesetContext
from dimensions import cns_dimensions
from surfaces.constants import RAOA_MOS_REF_VAL


class FrameworkRegistryTest(unittest.TestCase):
    def test_default_framework_is_nasf_aus(self):
        self.assertEqual(DEFAULT_FRAMEWORK_ID, "nasf_aus")
        self.assertEqual(get_framework_profile().id, "nasf_aus")

    def test_legacy_nasf_alias_normalizes_to_canonical_id(self):
        self.assertEqual(normalize_framework_id("NASF"), "nasf_aus")
        self.assertEqual(get_framework_profile("nasf").id, "nasf_aus")
        self.assertEqual(get_framework_profile("australia_nasf").id, "nasf_aus")

    def test_structured_payload_normalizes_to_canonical_id(self):
        self.assertEqual(normalize_framework_id({"id": "NASF"}), "nasf_aus")
        self.assertEqual(normalize_framework_id({"safeguarding_framework": "NASF"}), "nasf_aus")
        self.assertEqual(normalize_framework_id({"framework": "NASF"}), "nasf_aus")

    def test_profiles_expose_capabilities(self):
        profile = get_framework_profile("nasf_aus")
        self.assertTrue(profile.supports("framework.windshear"))
        self.assertTrue(profile.supports("framework.wildlife"))
        self.assertTrue(profile.supports("framework.lighting_control"))
        self.assertEqual(profile.capability_status("framework.cns.bra"), "partial")
        self.assertEqual(profile.capability_status("framework.met.station"), "partial")

    def test_registry_has_ui_profiles(self):
        profiles = list(iter_framework_profiles())
        self.assertGreaterEqual(len(profiles), 1)
        self.assertEqual(profiles[0].display_name, "NASF (Australia)")

    def test_policy_context_exposes_design_standard_and_framework(self):
        context = RulesetContext(
            design_standard=get_ruleset_profile({"ruleset": "MOS139"}),
            safeguarding_framework=get_framework_profile(None),
        )
        self.assertEqual(context.design_standard_id, "mos139_2019")
        self.assertEqual(context.ruleset_id, "mos139_2019")
        self.assertEqual(context.framework_id, "nasf_aus")
        self.assertEqual(context.aerodrome_standard.id, "mos139_2019")

    def test_nasf_profile_exposes_guideline_parameters(self):
        profile = get_framework_profile("nasf_aus")

        windshear = profile.windshear_parameters()
        self.assertEqual(windshear["far_edge_offset"], 500.0)
        self.assertEqual(windshear["zone_length_backward"], 1400.0)
        self.assertEqual(windshear["zone_half_width"], 1200.0)
        self.assertEqual(windshear["ref_nasf"], "NASF Guideline B")

        wildlife = profile.wildlife_parameters()
        self.assertEqual(wildlife["radius_a_m"], 3000.0)
        self.assertEqual(wildlife["radius_b_m"], 8000.0)
        self.assertEqual(wildlife["radius_c_m"], 13000.0)
        self.assertEqual(wildlife["buffer_segments"], 144)

        wind_turbine = profile.wind_turbine_parameters()
        self.assertEqual(wind_turbine["radius_m"], 30000.0)
        self.assertEqual(wind_turbine["ref_nasf"], "NASF Guideline D")

    def test_nasf_profile_exposes_lighting_and_psa_parameters(self):
        profile = get_framework_profile("nasf_aus")

        lighting = profile.lighting_control_parameters()
        self.assertEqual(lighting["zone_order"], ["A", "B", "C", "D"])
        self.assertEqual(lighting["zones"]["D"]["max_intensity"], "450cd")
        self.assertEqual(lighting["area_radius_m"], 6000.0)
        self.assertEqual(lighting["nasf_ref"], "NASF Guideline E")

        psa = profile.public_safety_area_parameters()
        self.assertEqual(psa["length"], 1000.0)
        self.assertEqual(psa["inner_width"], 350.0)
        self.assertEqual(psa["outer_width"], 250.0)
        self.assertEqual(psa["nasf_ref"], "NASF Guideline I")

    def test_nasf_profile_exposes_cns_bra_specs(self):
        profile = get_framework_profile("nasf_aus")
        specs = profile.cns_spec("VHF Omni-Directional Range (VOR)")

        self.assertIsNotNone(specs)
        self.assertEqual(specs[0]["SurfaceName"], "Zone A")
        self.assertEqual(specs[0]["OuterRadius_m"], 100)

    def test_nasf_profile_exposes_layer_tree_metadata(self):
        profile = get_framework_profile("nasf_aus")

        self.assertEqual(profile.safeguarding_group_name(), "05 External Safeguarding")
        self.assertEqual(profile.safeguarding_summary_section(), "05 External Safeguarding")
        self.assertEqual(profile.generation_status_message(), "Generating external safeguarding layers...")

        guideline_groups = profile.guideline_group_definitions()
        self.assertEqual(guideline_groups["B"], "Building-Induced Windshear / Turbulence")
        self.assertNotIn("F", guideline_groups)
        self.assertEqual(guideline_groups["G"], "CNS / Technical Safeguarding")
        self.assertNotIn("G", profile.guideline_group_definitions(include_cns=False))

        guideline_f_subgroups = profile.guideline_f_subgroup_names()
        self.assertEqual(guideline_f_subgroups["airport_wide"], "Airport-wide OLS")
        self.assertEqual(guideline_f_subgroups["runway"], "Runway Approach And Take-off")
        self.assertEqual(guideline_f_subgroups["ofz"], "Obstacle Free Zone")

        guideline_f_labels = profile.guideline_f_checklist_labels()
        self.assertEqual(guideline_f_labels["airport_wide"], "Airport-wide OLS")

    def test_output_structure_separates_protected_airspace_from_external_safeguarding(self):
        self.assertEqual(output_structure.PROTECTED_AIRSPACE, "04 Protected Airspace")
        self.assertEqual(output_structure.EXTERNAL_SAFEGUARDING, "05 External Safeguarding")
        self.assertEqual(output_structure.OLS_SURFACES, "OLS Surfaces")
        self.assertEqual(output_structure.DEBUG_DEVELOPMENT, "99 Debug / Development")
        self.assertIn(output_structure.PROTECTED_AIRSPACE, output_structure.SECTION_ORDER)
        self.assertLess(
            output_structure.SECTION_ORDER.index(output_structure.PROTECTED_AIRSPACE),
            output_structure.SECTION_ORDER.index(output_structure.EXTERNAL_SAFEGUARDING),
        )

    def test_nasf_profile_exposes_empty_group_reasons(self):
        profile = get_framework_profile("nasf_aus")

        self.assertIn("external safeguarding layers", profile.empty_group_reason("05 External Safeguarding"))
        self.assertIn("windshear", profile.empty_group_reason("Building-Induced Windshear / Turbulence"))
        self.assertIn("CNS", profile.empty_group_reason("CNS / Technical Safeguarding"))
        self.assertEqual(profile.empty_group_reason("Unrelated Group"), "")

    def test_legacy_cns_dimensions_shim_uses_nasf_data(self):
        legacy_specs = cns_dimensions.get_cns_spec("VHF Omni-Directional Range (VOR)")
        framework_specs = get_framework_profile("nasf_aus").cns_spec("VHF Omni-Directional Range (VOR)")

        self.assertEqual(legacy_specs, framework_specs)

    def test_legacy_guideline_constants_shim_uses_new_owners(self):
        self.assertEqual(guideline_constants.LAYER_FEATURE_BATCH_SIZE, LAYER_FEATURE_BATCH_SIZE)
        self.assertEqual(guideline_constants.RAOA_MOS_REF_VAL, RAOA_MOS_REF_VAL)
        self.assertEqual(guideline_constants.CONICAL_CONTOUR_INTERVAL, CONICAL_CONTOUR_INTERVAL)
        self.assertEqual(
            guideline_constants.GUIDELINE_E_ZONE_PARAMS,
            get_framework_profile("nasf_aus").lighting_control_parameters()["zones"],
        )

    def test_legacy_simple_guidelines_shim_uses_nasf_processors(self):
        try:
            simple_module = importlib.import_module("guidelines.simple")
            processors_module = importlib.import_module("frameworks.nasf.processors")
        except ModuleNotFoundError as exc:
            if exc.name == "qgis":
                self.skipTest("QGIS runtime is not available")
            raise

        SimpleGuidelinesMixin = simple_module.SimpleGuidelinesMixin
        NasfGuidelinesMixin = processors_module.NasfGuidelinesMixin
        self.assertIs(SimpleGuidelinesMixin, NasfGuidelinesMixin)
        self.assertTrue(hasattr(NasfGuidelinesMixin, "process_guideline_b"))
        self.assertTrue(hasattr(NasfGuidelinesMixin, "process_guideline_c"))
        self.assertTrue(hasattr(NasfGuidelinesMixin, "process_guideline_g"))
        self.assertTrue(hasattr(NasfGuidelinesMixin, "process_guideline_i"))


if __name__ == "__main__":
    unittest.main()
