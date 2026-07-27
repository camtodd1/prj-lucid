"""QGIS geometry checks for implemented NASF Guideline G CNS facilities."""

import unittest

from qgis.core import QgsGeometry, QgsPointXY

from frameworks.nasf.cns_guideline import NasfCnsGuidelineMixin
from frameworks.nasf.profile import NASF_PROFILE


class _CnsHarness(NasfCnsGuidelineMixin):
    def __init__(self):
        self.created_layers = []

    def get_active_framework(self):
        return NASF_PROFILE

    def _create_and_add_layer(self, geometry_type, internal_name, display_name, fields, features, *_args):
        self.created_layers.append(
            {
                "geometry_type": geometry_type,
                "internal_name": internal_name,
                "display_name": display_name,
                "fields": fields,
                "features": features,
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
        self.assertEqual(attributes["Area of Interest"].attribute("minagl_m"), 10.0)
        self.assertEqual(attributes["Area of Interest"].attribute("heightcmp"), ">")
        self.assertTrue(
            attributes["Zone B"].geometry().equals(attributes["Area of Interest"].geometry())
        )

    def test_high_frequency_transmit_generates_overlapping_surfaces_and_contours(self):
        harness = _CnsHarness()

        self.assertTrue(
            harness.process_cns_building_restricted_areas(
                [self._facility("High Frequency (HF)")],
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


if __name__ == "__main__":
    unittest.main()
