"""Geometry checks for the provisional glide-path BRA construction."""

import math
import sys
import unittest
from pathlib import Path

from qgis.core import QgsLayerTreeGroup, QgsPointXY, QgsWkbTypes


WORKSPACE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORKSPACE.parent))

from safeguarding_builder.frameworks.nasf.ils_bra import (
    construct_provisional_glide_path_bra,
    construct_provisional_localiser_bra,
    ils_bra_contour_geometries,
)
from safeguarding_builder.frameworks.nasf.cns_guideline import NasfCnsGuidelineMixin


class _LayerStub:
    def __init__(self):
        self.properties = {}

    def setCustomProperty(self, key, value):
        self.properties[key] = value


class _IlsHarness(NasfCnsGuidelineMixin):
    def __init__(self):
        self.created = []

    def _create_and_add_layer(
        self,
        geometry_type,
        internal_name,
        display_name,
        fields,
        features,
        layer_group,
        style_key,
    ):
        layer = _LayerStub()
        self.created.append(
            {
                "geometry_type": geometry_type,
                "internal_name": internal_name,
                "display_name": display_name,
                "features": list(features),
                "layer_group": layer_group,
                "style_key": style_key,
                "layer": layer,
            }
        )
        return layer


class IlsBraGeometryQgisTests(unittest.TestCase):
    def setUp(self):
        self.surfaces = construct_provisional_glide_path_bra(
            {
                "front_face_point": QgsPointXY(455300, 5771880),
                "runway_interior_unit": (1.0, 0.0),
                "signed_offset": 120.0,
                "ground_elevation": 18.5,
                "source_reference": "Provisional worked example",
            }
        )
        self.by_role = {surface["surface_role"]: surface for surface in self.surfaces}

    def test_constructs_horizontal_base_from_offset_plus_40_by_300(self):
        base = self.by_role["provisional_horizontal_base"]["geometry"]
        box = base.boundingBox()
        self.assertAlmostEqual(box.width(), 300.0, places=6)
        self.assertAlmostEqual(box.height(), 160.0, places=6)
        self.assertTrue(QgsWkbTypes.hasZ(base.wkbType()))

    def test_constructs_rear_and_three_sloped_surface_roles(self):
        self.assertEqual(
            set(self.by_role),
            {
                "provisional_horizontal_base",
                "provisional_rear_horizontal",
                "provisional_longitudinal",
                "provisional_lateral_outer",
                "provisional_lateral_runway_side",
            },
        )
        rear = self.by_role["provisional_rear_horizontal"]["geometry"].boundingBox()
        self.assertAlmostEqual(rear.width(), 50.0, places=6)
        self.assertAlmostEqual(rear.height(), 80.0, places=6)

    def test_longitudinal_plane_rises_from_300_to_1500_metres(self):
        longitudinal = self.by_role["provisional_longitudinal"]["geometry"]
        z_values = [point.z() for point in longitudinal.constGet().exteriorRing().points()]
        self.assertAlmostEqual(min(z_values), 18.5, places=6)
        self.assertAlmostEqual(
            max(z_values),
            18.5 + 1200.0 * math.tan(math.radians(0.5)),
            places=6,
        )

    def test_contour_geometry_intersects_and_merges_sloped_surface_pieces(self):
        contours = ils_bra_contour_geometries(self.surfaces, 23.5)

        self.assertTrue(contours)
        self.assertTrue(all(not geometry.isEmpty() for geometry in contours))
        self.assertTrue(all(geometry.isGeosValid() for geometry in contours))
        self.assertTrue(all(QgsWkbTypes.hasZ(geometry.wkbType()) for geometry in contours))
        self.assertTrue(
            all(
                abs(point.z() - 23.5) <= 1e-6
                for geometry in contours
                for point in geometry.vertices()
            )
        )

    def test_processor_emits_provisional_surface_and_classified_contour_layers(self):
        harness = _IlsHarness()
        group = QgsLayerTreeGroup("Guideline G")
        installation = {
            "id": "GP-09",
            "component": "glide_path",
            "runway_designation": "09",
            "front_face_point": QgsPointXY(455300, 5771880),
            "runway_interior_unit": (1.0, 0.0),
            "signed_offset": 120.0,
            "ground_elevation": 18.5,
            "source_reference": "Provisional worked example",
        }

        self.assertTrue(
            harness.process_ils_building_restricted_areas(
                [installation], "YTEST", group
            )
        )
        self.assertEqual(len(harness.created), 2)
        created = next(
            item for item in harness.created if item["style_key"] == "ILS BRA Surface"
        )
        contours = next(
            item for item in harness.created if item["style_key"] == "ILS BRA Contour"
        )
        self.assertEqual(created["geometry_type"], "PolygonZ")
        self.assertEqual(created["display_name"], "Glide Path 09 - Surface")
        self.assertEqual(created["layer_group"].name(), "RWY 09")
        self.assertEqual(len(created["features"]), 5)
        self.assertTrue(
            all(feature.attribute("runway") == "09" for feature in created["features"])
        )
        self.assertTrue(
            all(feature.attribute("provisional") for feature in created["features"])
        )
        self.assertTrue(created["layer"].properties["safeguarding_provisional"])
        self.assertEqual(contours["geometry_type"], "LineStringZ")
        self.assertEqual(contours["display_name"], "Glide Path 09 - Contours")
        self.assertIs(contours["layer_group"], created["layer_group"])
        levels = {
            (feature.attribute("contagl_m"), feature.attribute("contclass"))
            for feature in contours["features"]
        }
        self.assertIn((0.0, "primary"), levels)
        self.assertIn((5.0, "intermediate"), levels)
        self.assertIn((10.0, "primary"), levels)
        elevations = {
            (feature.attribute("contagl_m"), feature.attribute("contelev_m"))
            for feature in contours["features"]
        }
        self.assertIn((0.0, 18.5), elevations)
        self.assertIn((5.0, 23.5), elevations)
        self.assertIn((10.0, 28.5), elevations)
        self.assertTrue(contours["layer"].properties["safeguarding_provisional"])
        self.assertEqual(
            contours["layer"].properties["safeguarding_contour_primary_m"], 10.0
        )
        self.assertEqual(
            contours["layer"].properties["safeguarding_contour_intermediate_m"], 5.0
        )

    def test_localiser_constructs_runway_centred_cat_i_envelope(self):
        surfaces = construct_provisional_localiser_bra(
            {
                "point": QgsPointXY(456300, 5772000),
                "runway_interior_unit": (1.0, 0.0),
                "runway_length": 1000.0,
                "distance_beyond_runway_end": 300.0,
                "localiser_category": "cat_i",
                "ground_elevation": 17.5,
                "source_reference": "Provisional worked example",
            }
        )
        by_role = {surface["surface_role"]: surface for surface in surfaces}
        self.assertEqual(len(surfaces), 5)
        base = by_role["provisional_localiser_horizontal_base"]["geometry"].boundingBox()
        rear = by_role["provisional_localiser_rear_horizontal"]["geometry"].boundingBox()
        self.assertAlmostEqual(base.width(), 300.0, places=6)
        self.assertAlmostEqual(base.height(), 90.0, places=6)
        self.assertAlmostEqual(rear.width(), 50.0, places=6)
        self.assertAlmostEqual(rear.height(), 90.0, places=6)
        self.assertEqual(surfaces[0]["forward_extent_m"], 1800.0)
        self.assertEqual(surfaces[0]["category_half_width_m"], 500.0)
        self.assertTrue(all(surface["geometry"].isGeosValid() for surface in surfaces))

    def test_localiser_cat_ii_iii_uses_1000_m_half_width(self):
        surfaces = construct_provisional_localiser_bra(
            {
                "point": QgsPointXY(456300, 5772000),
                "runway_interior_unit": (1.0, 0.0),
                "runway_length": 3000.0,
                "distance_beyond_runway_end": 300.0,
                "localiser_category": "cat_ii_iii",
                "ground_elevation": 17.5,
            }
        )
        self.assertTrue(all(surface["category_half_width_m"] == 1000.0 for surface in surfaces))

    def test_processor_generates_localiser_layer(self):
        harness = _IlsHarness()
        group = QgsLayerTreeGroup("Guideline G")
        installation = {
            "id": "LOC-09",
            "component": "localiser",
            "runway_designation": "09",
            "point": QgsPointXY(456300, 5772000),
            "runway_interior_unit": (1.0, 0.0),
            "runway_length": 1000.0,
            "distance_beyond_runway_end": 300.0,
            "localiser_category": "cat_i",
            "signed_offset": 0.0,
            "ground_elevation": 17.5,
            "source_reference": "Provisional worked example",
        }
        self.assertTrue(
            harness.process_ils_building_restricted_areas(
                [installation], "YTEST", group
            )
        )
        created = next(
            item for item in harness.created if item["style_key"] == "ILS BRA Surface"
        )
        contours = next(
            item for item in harness.created if item["style_key"] == "ILS BRA Contour"
        )
        self.assertEqual(len(created["features"]), 5)
        self.assertEqual(created["display_name"], "Localiser 09 - Surface")
        self.assertEqual(contours["display_name"], "Localiser 09 - Contours")
        self.assertEqual(created["layer_group"].name(), "RWY 09")
        self.assertIs(contours["layer_group"], created["layer_group"])
        self.assertTrue(
            all(feature.attribute("loc_cat") == "cat_i" for feature in created["features"])
        )
        self.assertEqual(
            {
                feature.attribute("contclass")
                for feature in contours["features"]
            },
            {"primary", "intermediate"},
        )

    def test_processor_groups_components_under_their_runway(self):
        harness = _IlsHarness()
        root = QgsLayerTreeGroup("Guideline G")
        installations = [
            {
                "id": "GP-09",
                "component": "glide_path",
                "runway_designation": "09",
                "front_face_point": QgsPointXY(455300, 5771880),
                "runway_interior_unit": (1.0, 0.0),
                "signed_offset": 120.0,
                "ground_elevation": 18.5,
                "source_reference": "Provisional worked example",
            },
            {
                "id": "LOC-09",
                "component": "localiser",
                "runway_designation": "09",
                "point": QgsPointXY(456300, 5772000),
                "runway_interior_unit": (1.0, 0.0),
                "runway_length": 1000.0,
                "distance_beyond_runway_end": 300.0,
                "localiser_category": "cat_i",
                "signed_offset": 0.0,
                "ground_elevation": 17.5,
                "source_reference": "Provisional worked example",
            },
            {
                "id": "GP-27",
                "component": "glide_path",
                "runway_designation": "27",
                "front_face_point": QgsPointXY(456700, 5772120),
                "runway_interior_unit": (-1.0, 0.0),
                "signed_offset": 120.0,
                "ground_elevation": 19.0,
                "source_reference": "Provisional worked example",
            },
        ]

        self.assertTrue(
            harness.process_ils_building_restricted_areas(
                installations, "YTEST", root
            )
        )
        ils_group = root.children()[0]
        self.assertEqual(ils_group.name(), "ILS Building Restricted Areas (Provisional)")
        runway_groups = {child.name(): child for child in ils_group.children()}
        self.assertEqual(set(runway_groups), {"RWY 09", "RWY 27"})
        self.assertTrue(all(
            created["layer_group"] is runway_groups["RWY 09"]
            for created in harness.created
            if " 09 - " in created["display_name"]
        ))
        self.assertTrue(all(
            created["layer_group"] is runway_groups["RWY 27"]
            for created in harness.created
            if " 27 - " in created["display_name"]
        ))
        self.assertEqual(
            {created["display_name"] for created in harness.created},
            {
                "Glide Path 09 - Surface",
                "Glide Path 09 - Contours",
                "Localiser 09 - Surface",
                "Localiser 09 - Contours",
                "Glide Path 27 - Surface",
                "Glide Path 27 - Contours",
            },
        )


if __name__ == "__main__":
    unittest.main()
