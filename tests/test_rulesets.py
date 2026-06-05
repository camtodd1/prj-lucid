import unittest

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

    def test_registry_has_ui_profiles(self):
        profiles = list(iter_ruleset_profiles())
        self.assertGreaterEqual(len(profiles), 1)
        self.assertEqual(profiles[0].display_name, "MOS139 (current)")


if __name__ == "__main__":
    unittest.main()
