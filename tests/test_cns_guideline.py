"""Policy checks for implemented NASF Guideline G CNS facilities."""

import unittest

from frameworks.nasf.cns import RADIO_LINK_POLICY, get_cns_spec, slope_contour_levels


class CnsGuidelineTests(unittest.TestCase):
    def test_radio_link_policy_is_an_all_height_referral_corridor(self):
        self.assertEqual(RADIO_LINK_POLICY["Width_m"], 30)
        self.assertEqual(RADIO_LINK_POLICY["HeightRule"], "All Heights")
        self.assertEqual(
            RADIO_LINK_POLICY["ActionRequired"],
            "All applications must be referred to Airservices Australia for assessment.",
        )

    def test_satellite_ground_station_has_explicit_overlapping_height_bands(self):
        specs = get_cns_spec("Satellite Ground Station (SGS)")
        self.assertIsNotNone(specs)
        by_name = {spec["SurfaceName"]: spec for spec in specs}

        self.assertEqual(by_name["Zone A"]["OuterRadius_m"], 30)
        self.assertEqual(by_name["Zone A"]["HeightRule"], "All Heights")
        self.assertEqual(
            by_name["Zone A"]["ActionRequired"],
            "All applications must be referred to Airservices Australia for assessment.",
        )

        for surface_name in ("Zone B", "Area of Interest"):
            self.assertEqual(by_name[surface_name]["InnerRadius_m"], 30)
            self.assertEqual(by_name[surface_name]["OuterRadius_m"], 150)
            self.assertEqual(by_name[surface_name]["HeightBasis"], "AGL")
        self.assertEqual(by_name["Zone B"]["MaxHeightAGL_m"], 10)
        self.assertEqual(by_name["Zone B"]["HeightComparator"], "<")
        self.assertEqual(by_name["Area of Interest"]["MinHeightAGL_m"], 10)
        self.assertEqual(by_name["Area of Interest"]["HeightComparator"], ">")
        self.assertEqual(by_name["Zone B"]["ActionRequired"], "No requirements.")
        self.assertEqual(
            by_name["Area of Interest"]["ActionRequired"],
            "All applications must be referred to Airservices Australia for assessment.",
        )

    def test_high_frequency_transmit_slope_and_area_of_interest_overlap(self):
        specs = get_cns_spec("High Frequency (HF)")
        self.assertIsNotNone(specs)
        by_name = {spec["SurfaceName"]: spec for spec in specs}

        slope = by_name["Zone A - 2.5 Degree Slope"]
        self.assertEqual((slope["InnerRadius_m"], slope["OuterRadius_m"]), (100, 600))
        self.assertEqual(slope["SlopeDegrees"], 2.5)
        self.assertEqual(slope["SlopeStartHeightAGL_m"], 10)
        self.assertEqual(slope["ContourInterval_m"], 5)

        area = by_name["Area of Interest"]
        self.assertEqual((area["InnerRadius_m"], area["OuterRadius_m"]), (100, 2000))
        self.assertEqual(area["MinHeightAGL_m"], 10)
        self.assertEqual(area["HeightComparator"], ">")
        self.assertEqual(
            by_name["Zone B"]["ActionRequired"],
            "No requirements. Airservices Australia should be advised of proposals for large obstructions.",
        )

        contours = slope_contour_levels(slope)
        self.assertEqual([contour["height_agl_m"] for contour in contours], [10.0, 15.0, 20.0, 25.0, 30.0])
        self.assertEqual(contours[0]["radius_m"], 100.0)
        self.assertAlmostEqual(contours[-1]["radius_m"], 558.075311, places=6)


if __name__ == "__main__":
    unittest.main()
