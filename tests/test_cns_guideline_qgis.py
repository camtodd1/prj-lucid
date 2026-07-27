"""QGIS geometry checks for implemented NASF Guideline G CNS facilities."""

import unittest

from qgis.core import QgsGeometry, QgsLayerTreeGroup, QgsPointXY

from frameworks.nasf.cns_guideline import NasfCnsGuidelineMixin
from frameworks.nasf.profile import NASF_PROFILE


class _CnsHarness(NasfCnsGuidelineMixin):
    def __init__(self):
        self.created_layers = []

    def get_active_framework(self):
        return NASF_PROFILE

    def _create_and_add_layer(
        self,
        geometry_type,
        internal_name,
        display_name,
        fields,
        features,
        layer_group,
        *_args,
    ):
        self.created_layers.append(
            {
                "geometry_type": geometry_type,
                "internal_name": internal_name,
                "display_name": display_name,
                "fields": fields,
                "features": features,
                "layer_group": layer_group,
            }
        )
        return object()


class CnsGuidelineQgisTests(unittest.TestCase):
    @staticmethod
    def _facility(facility_type):
        return {
            "id": "CNS-01",
            "type": facility_type,
            "geom": QgsGeometry.fromPointXY(QgsPointXY(500000, 6000000)),
            "elevation": 50,
        }

    @staticmethod
    def _radio_link_endpoint(identifier, easting, northing):
        return {
            "id": identifier,
            "type": "Radio Link",
            "link_id": "RL-01",
            "geom": QgsGeometry.fromPointXY(QgsPointXY(easting, northing)),
            "elevation": None,
        }

    def test_satellite_ground_station_generates_three_explicit_bands(self):
        harness = _CnsHarness()

        self.assertTrue(
            harness.process_cns_building_restricted_areas(
                [self._facility("Satellite Ground Station (SGS)")],
                "YTEST",
                None,
                None,
            )
        )

        self.assertEqual(len(harness.created_layers), 3)
        attributes = {
            layer["features"][0].attribute("surfname"): layer["features"][0]
            for layer in harness.created_layers
        }
        self.assertEqual(set(attributes), {"Zone A", "Zone B", "Area of Interest"})
        self.assertEqual(attributes["Zone B"].attribute("maxagl_m"), 10.0)
        self.assertEqual(attributes["Zone B"].attribute("heightcmp"), "<")
        self.assertEqual(attributes["Zone B"].attribute("actionreq"), "No requirements.")
        self.assertEqual(attributes["Area of Interest"].attribute("minagl_m"), 10.0)
        self.assertEqual(attributes["Area of Interest"].attribute("heightcmp"), ">")
        self.assertEqual(
            attributes["Area of Interest"].attribute("actionreq"),
            "All applications must be referred to Airservices Australia for assessment.",
        )
        self.assertTrue(
            attributes["Zone B"].geometry().equals(attributes["Area of Interest"].geometry())
        )

    def test_facility_surfaces_are_grouped_by_cns_element(self):
        harness = _CnsHarness()
        cns_group = QgsLayerTreeGroup("CNS / Technical Safeguarding")

        self.assertTrue(
            harness.process_cns_building_restricted_areas(
                [self._facility("Satellite Ground Station (SGS)")],
                "YTEST",
                None,
                cns_group,
            )
        )

        element_groups = cns_group.children()
        self.assertEqual(len(element_groups), 1)
        self.assertEqual(
            element_groups[0].name(),
            "CNS-01 - Satellite Ground Station (SGS)",
        )
        self.assertTrue(
            all(layer["layer_group"] is element_groups[0] for layer in harness.created_layers)
        )

    def test_high_frequency_transmit_generates_overlapping_surfaces_and_contours(self):
        harness = _CnsHarness()

        self.assertTrue(
            harness.process_cns_building_restricted_areas(
                [self._facility("High Frequency (HF) Transmit Site")],
                "YTEST",
                None,
                None,
            )
        )

        polygons = [layer for layer in harness.created_layers if layer["geometry_type"] == "Polygon"]
        contours = [layer for layer in harness.created_layers if layer["geometry_type"] == "LineString"]
        self.assertEqual(len(polygons), 4)
        self.assertEqual(len(contours), 1)
        polygon_attributes = {
            layer["features"][0].attribute("surfname"): layer["features"][0]
            for layer in polygons
        }
        self.assertEqual(polygon_attributes["Zone A - 2.5 Degree Slope"].attribute("slope_deg"), 2.5)
        self.assertEqual(polygon_attributes["Area of Interest"].attribute("minagl_m"), 10.0)
        self.assertEqual(polygon_attributes["Area of Interest"].attribute("innerrad_m"), 100.0)
        self.assertEqual(polygon_attributes["Area of Interest"].attribute("outerrad_m"), 2000.0)
        self.assertEqual(
            polygon_attributes["Zone B"].attribute("actionreq"),
            "No requirements. Airservices Australia should be advised of proposals for large obstructions.",
        )
        self.assertTrue(
            polygon_attributes["Zone A - 2.5 Degree Slope"].geometry().intersects(
                polygon_attributes["Area of Interest"].geometry()
            )
        )
        self.assertEqual(len(contours[0]["features"]), 5)
        self.assertEqual(
            [feature.attribute("contagl_m") for feature in contours[0]["features"]],
            [10.0, 15.0, 20.0, 25.0, 30.0],
        )

    def test_high_frequency_receiver_generates_overlapping_areas_and_contours(self):
        harness = _CnsHarness()

        self.assertTrue(
            harness.process_cns_building_restricted_areas(
                [self._facility("High Frequency (HF) Receiver Site")],
                "YTEST",
                None,
                None,
            )
        )

        polygons = [layer for layer in harness.created_layers if layer["geometry_type"] == "Polygon"]
        contours = [layer for layer in harness.created_layers if layer["geometry_type"] == "LineString"]
        self.assertEqual(len(polygons), 5)
        self.assertEqual(len(contours), 1)
        attributes = {
            layer["features"][0].attribute("surfname"): layer["features"][0]
            for layer in polygons
        }
        self.assertEqual(attributes["Area of Interest - Above 267 m"].attribute("minant_m"), 267.0)
        self.assertEqual(attributes["Area of Interest - Above 267 m"].attribute("heightcmp"), ">")
        self.assertEqual(
            attributes["Area of Interest - Below Zone A"].attribute("heightrule"),
            "Below Radial Slope",
        )
        self.assertTrue(
            attributes["Zone A - 2.5 Degree Slope"].geometry().intersects(
                attributes["Area of Interest - Below Zone A"].geometry()
            )
        )
        self.assertEqual(len(contours[0]["features"]), 52)

    def test_radio_link_generates_a_30_m_all_height_corridor_from_two_endpoints(self):
        harness = _CnsHarness()
        cns_group = QgsLayerTreeGroup("CNS / Technical Safeguarding")

        self.assertTrue(
            harness.process_cns_building_restricted_areas(
                [
                    self._radio_link_endpoint("Dish A", 500000, 6000000),
                    self._radio_link_endpoint("Dish B", 501000, 6000000),
                ],
                "YTEST",
                None,
                cns_group,
            )
        )

        self.assertEqual(len(harness.created_layers), 1)
        layer = harness.created_layers[0]
        self.assertEqual(layer["layer_group"].name(), "RL-01 - Radio Link")
        self.assertIs(layer["layer_group"].parent(), cns_group)
        feature = layer["features"][0]
        self.assertEqual(layer["geometry_type"], "Polygon")
        self.assertEqual(feature.attribute("link_id"), "RL-01")
        self.assertEqual(feature.attribute("shape"), "CORRIDOR")
        self.assertEqual(feature.attribute("outerrad_m"), 30.0)
        self.assertEqual(feature.attribute("heightrule"), "All Heights")
        self.assertEqual(
            feature.attribute("guidance"),
            "No temporary or permanent obstructions should infringe Zone A.",
        )
        self.assertEqual(
            feature.attribute("actionreq"),
            "All applications must be referred to Airservices Australia for assessment.",
        )
        self.assertGreater(feature.geometry().area(), 60000)

    def test_radio_link_requires_exactly_two_endpoints_for_each_link_id(self):
        harness = _CnsHarness()

        self.assertFalse(
            harness.process_cns_building_restricted_areas(
                [self._radio_link_endpoint("Dish A", 500000, 6000000)],
                "YTEST",
                None,
                None,
            )
        )
        self.assertEqual(harness.created_layers, [])


if __name__ == "__main__":
    unittest.main()
