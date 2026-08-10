import unittest

from core.family_modules import (
    FAMILY_CNS,
    FAMILY_LIGHTING,
    FAMILY_OLS,
    family_input_signature,
)


class FamilyModuleSignatureTests(unittest.TestCase):
    def test_agl_options_only_invalidate_lighting(self):
        baseline = {
            "icao_code": "YTEST",
            "design_standard": "mos139_2019",
            "runways": [{"thr_point": (0, 0), "rec_thr_point": (10, 0)}],
            "agl_options": {"enabled": False},
            "baseline_ols_ruleset": "mos139_2019",
        }
        changed = {**baseline, "agl_options": {"enabled": True}}

        self.assertNotEqual(
            family_input_signature(baseline, FAMILY_LIGHTING, "EPSG:28355"),
            family_input_signature(changed, FAMILY_LIGHTING, "EPSG:28355"),
        )
        self.assertEqual(
            family_input_signature(baseline, FAMILY_OLS, "EPSG:28355"),
            family_input_signature(changed, FAMILY_OLS, "EPSG:28355"),
        )

    def test_cns_changes_only_invalidate_cns_family(self):
        baseline = {
            "icao_code": "YTEST",
            "runways": [],
            "cns_facilities": [],
            "agl_options": {"enabled": True},
        }
        changed = {
            **baseline,
            "cns_facilities": [{"id": "VOR-1", "easting": 1.0}],
        }

        self.assertNotEqual(
            family_input_signature(baseline, FAMILY_CNS, "EPSG:28355"),
            family_input_signature(changed, FAMILY_CNS, "EPSG:28355"),
        )
        self.assertEqual(
            family_input_signature(baseline, FAMILY_LIGHTING, "EPSG:28355"),
            family_input_signature(changed, FAMILY_LIGHTING, "EPSG:28355"),
        )

    def test_project_crs_invalidates_geometry_family(self):
        inputs = {"icao_code": "YTEST", "runways": []}

        self.assertNotEqual(
            family_input_signature(inputs, FAMILY_OLS, "EPSG:28355"),
            family_input_signature(inputs, FAMILY_OLS, "EPSG:7855"),
        )


if __name__ == "__main__":
    unittest.main()
