import unittest

from frameworks.registry import (
    DEFAULT_FRAMEWORK_ID,
    get_framework_profile,
    iter_framework_profiles,
    normalize_framework_id,
)
from rulesets.registry import get_ruleset_profile
from rulesets.context import RulesetContext


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


if __name__ == "__main__":
    unittest.main()
