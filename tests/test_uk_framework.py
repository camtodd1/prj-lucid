"""Tests for the UK CAA/DfT safeguarding framework profile."""

import unittest

from core.run_history import runtime_input_fingerprint
from frameworks.registry import (
    DEFAULT_FRAMEWORK_ID,
    get_framework_profile,
    is_known_framework,
    iter_framework_profiles,
)


class UkFrameworkProfileTests(unittest.TestCase):
    def setUp(self):
        self.profile = get_framework_profile("uk_caa_safeguarding")

    def test_profile_is_registered_without_changing_the_default(self):
        self.assertEqual(DEFAULT_FRAMEWORK_ID, "nasf_aus")
        self.assertTrue(is_known_framework("uk"))
        self.assertEqual(get_framework_profile("uk_caa").id, "uk_caa_safeguarding")
        self.assertIn(self.profile, tuple(iter_framework_profiles()))
        self.assertEqual(
            self.profile.guideline_group_definitions(),
            {
                "C": "Wildlife Consultation",
                "D": "Wind Turbine Safeguarding",
                "I": "Public Safety Zones",
            },
        )
        self.assertNotIn("I", self.profile.guideline_group_definitions(options={}))
        self.assertIn(
            "I",
            self.profile.guideline_group_definitions(
                options={"psz_applicable": True, "pscz_length_m": 1000}
            ),
        )

    def test_consultation_radii_are_fixed_and_source_scoped(self):
        wildlife = self.profile.wildlife_parameters({"wildlife_radius_km": 14.5})
        turbines = self.profile.wind_turbine_parameters({"wind_turbine_radius_km": 32})
        self.assertEqual(wildlife["model"], "uk_consultation_circle")
        self.assertEqual(wildlife["radius_m"], 13000.0)
        self.assertEqual(wildlife["family_id"], "wildlife_consultation")
        self.assertEqual(turbines["radius_m"], 30000.0)
        self.assertEqual(turbines["family_id"], "wind_energy_consultation")
        self.assertEqual(wildlife["geometry_status"], "indicative_default")

    def test_psz_requires_explicit_applicability_and_traffic_band(self):
        disabled = self.profile.public_safety_area_parameters({})
        incomplete = self.profile.public_safety_area_parameters({"psz_applicable": True})
        short = self.profile.public_safety_area_parameters(
            {"psz_applicable": True, "pscz_length_m": 1000}
        )
        long = self.profile.public_safety_area_parameters(
            {"psz_applicable": True, "pscz_length_m": 1500}
        )
        self.assertFalse(disabled["enabled"])
        self.assertFalse(incomplete["enabled"])
        self.assertFalse(incomplete["selection_complete"])
        self.assertEqual([zone["length_m"] for zone in short["zones"]], [500.0, 1000.0])
        self.assertEqual([zone["length_m"] for zone in long["zones"]], [500.0, 1500.0])
        self.assertTrue(short["enabled"])

    def test_crane_screen_preserves_independent_local_and_national_triggers(self):
        local = self.profile.screen_crane_notification(6000, 10.1)
        shielded = self.profile.screen_crane_notification(1000, 20, True)
        national = self.profile.screen_crane_notification(50000, 100, True)
        below = self.profile.screen_crane_notification(6000, 10)
        self.assertTrue(local["notification_required"])
        self.assertEqual(local["reason_codes"], ("within_6km_over_10m_unshielded",))
        self.assertFalse(shielded["notification_required"])
        self.assertTrue(national["national_trigger"])
        self.assertFalse(national["local_trigger"])
        self.assertFalse(below["notification_required"])
        self.assertEqual(national["profile_id"], "uk_caa_cranes")
        self.assertEqual(national["source_id"], "UK-7")
        self.assertEqual(national["assessment_result"], "consult")
        long_term = self.profile.screen_crane_notification(50000, 150, True, 0, 91)
        self.assertTrue(long_term["dgc_notification"])
        self.assertEqual(long_term["lighting_status"], "mandatory_medium_intensity")
        self.assertEqual(long_term["lighting_intensity_cd"], 2000.0)
        self.assertTrue(long_term["intermediate_lights_required"])
        with self.assertRaises(ValueError):
            self.profile.screen_crane_notification(-1, 20)

    def test_safeguarding_options_affect_run_fingerprint(self):
        base = {
            "icao_code": "EGLL",
            "safeguarding_framework": "uk_caa_safeguarding",
            "safeguarding_options": {"psz_applicable": False, "pscz_length_m": None},
        }
        changed = dict(base)
        changed["safeguarding_options"] = {
            "psz_applicable": True,
            "pscz_length_m": 1000.0,
        }
        self.assertNotEqual(
            runtime_input_fingerprint(base),
            runtime_input_fingerprint(changed),
        )


if __name__ == "__main__":
    unittest.main()
