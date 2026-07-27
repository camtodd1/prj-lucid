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

    def test_cns_slope_contours_start_at_the_lowest_level_and_classify_primary_lines(self):
        levels = slope_contour_levels(
            {
                "HeightRule": "Radial Slope",
                "SlopeDegrees": 45,
                "SlopeStartHeightAGL_m": 2,
                "SlopeStartDistance_m": 10,
                "OuterRadius_m": 30,
                "ContourInterval_m": 5,
            },
            primary_interval_m=10,
            intermediate_interval_m=5,
        )
        self.assertEqual([level["height_agl_m"] for level in levels], [2.0, 7.0, 12.0, 17.0, 22.0])
        self.assertEqual(
            [level["contour_class"] for level in levels],
            ["primary", "intermediate", "primary", "intermediate", "primary"],
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
        specs = get_cns_spec("High Frequency (HF) Transmit Site")
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

    def test_high_frequency_receiver_has_source_defined_vertical_conditions(self):
        specs = get_cns_spec("High Frequency (HF) Receiver Site")
        self.assertIsNotNone(specs)
        by_name = {spec["SurfaceName"]: spec for spec in specs}

        slope = by_name["Zone A - 2.5 Degree Slope"]
        self.assertEqual((slope["InnerRadius_m"], slope["OuterRadius_m"]), (100, 6000))
        self.assertEqual(slope["SlopeDegrees"], 2.5)
        self.assertEqual(len(slope_contour_levels(slope)), 52)
        self.assertEqual(by_name["Area of Interest - Above 267 m"]["MinHeightAboveAntenna_m"], 267)
        self.assertEqual(by_name["Area of Interest - Above 267 m"]["HeightComparator"], ">")
        self.assertEqual(
            by_name["Zone B"]["ActionRequired"],
            "No requirements. Airservices Australia should be advised of proposals for large obstructions.",
        )

    def test_marker_beacon_has_inner_referral_and_50_degree_boundary(self):
        specs = get_cns_spec("Middle and Outer Marker Beacon")
        self.assertIsNotNone(specs)
        by_name = {spec["SurfaceName"]: spec for spec in specs}

        inner = by_name["Zone A - Inner"]
        self.assertEqual((inner["InnerRadius_m"], inner["OuterRadius_m"]), (0, 5))
        self.assertEqual(inner["HeightRule"], "All Heights")
        self.assertEqual(
            inner["ActionRequired"],
            "All applications must be referred to Airservices Australia for assessment.",
        )

        slope = by_name["Zone A - 50 Degree Slope"]
        self.assertEqual((slope["InnerRadius_m"], slope["OuterRadius_m"]), (5, 50))
        self.assertEqual(slope["HeightRule"], "Radial Slope")
        self.assertEqual(slope["SlopeDegrees"], 50)
        self.assertAlmostEqual(slope["SlopeStartHeightAGL_m"], 5.958768, places=6)
        self.assertEqual(slope_contour_levels(slope)[0]["radius_m"], 5.0)

        zone_b = by_name["Zone B"]
        self.assertEqual((zone_b["InnerRadius_m"], zone_b["OuterRadius_m"]), (5, 50))
        self.assertEqual(zone_b["HeightRule"], "Does Not Cross Zone Boundary")
        self.assertEqual(zone_b["ActionRequired"], "No requirements.")
        self.assertEqual(
            get_cns_spec("Middle and Outer Marker"),
            specs,
        )

    def test_gbas_surfaces_explicitly_have_no_height_rule(self):
        for facility_type in (
            "Ground Based Augmentation System (GBAS) - RSMU",
            "GBAS - VDB",
        ):
            with self.subTest(facility_type=facility_type):
                specs = get_cns_spec(facility_type)
                self.assertIsNotNone(specs)
                self.assertTrue(all(spec["HeightRule"] == "N/A" for spec in specs))

    def test_legacy_high_frequency_type_remains_a_transmit_site_alias(self):
        self.assertEqual(
            get_cns_spec("High Frequency (HF)"),
            get_cns_spec("High Frequency (HF) Transmit Site"),
        )


if __name__ == "__main__":
    unittest.main()
