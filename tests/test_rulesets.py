import unittest

from dimensions import ols_dimensions
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

    def test_mos139_adapter_matches_legacy_ols_helpers(self):
        profile = get_ruleset_profile("mos139_2019")
        self.assertEqual(
            profile.classify_runway_type("Precision Approach CAT I"),
            ols_dimensions.get_runway_type_abbr("Precision Approach CAT I"),
        )
        self.assertEqual(
            profile.strip_parameters(3, "PA_I", 45.0),
            ols_dimensions.get_strip_params(3, "PA_I", 45.0),
        )
        self.assertEqual(
            profile.resa_parameters(3, "PA_I", "NI"),
            ols_dimensions.get_resa_params(3, "PA_I", "NI"),
        )
        self.assertEqual(
            profile.ols_parameters(3, "Precision Approach CAT I", "APPROACH"),
            ols_dimensions.get_ols_params(3, "Precision Approach CAT I", "APPROACH"),
        )
        self.assertEqual(
            profile.taxiway_separation_offset(3, "C", "Precision Approach CAT I"),
            ols_dimensions.get_taxiway_separation_offset(3, "C", "Precision Approach CAT I"),
        )

    def test_registry_has_ui_profiles(self):
        profiles = list(iter_ruleset_profiles())
        self.assertGreaterEqual(len(profiles), 1)
        self.assertEqual(profiles[0].display_name, "MOS139 (current)")


if __name__ == "__main__":
    unittest.main()
