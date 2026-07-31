"""QGIS geometry checks for UK safeguarding outputs."""

import unittest
import sys
from pathlib import Path
from types import MethodType

from qgis.core import (
    QgsCoordinateReferenceSystem,
    QgsLayerTreeGroup,
    QgsPointXY,
)

WORKSPACE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORKSPACE.parent))

from safeguarding_builder.frameworks.registry import get_framework_profile  # noqa: E402
from safeguarding_builder.safeguarding_builder import SafeguardingBuilder  # noqa: E402


class UkFrameworkGeometryTests(unittest.TestCase):
    def setUp(self):
        self.builder = object.__new__(SafeguardingBuilder)
        self.builder.framework = get_framework_profile("uk_caa_safeguarding")
        self.builder.safeguarding_options = {
            "wildlife_radius_km": 13.0,
            "wind_turbine_radius_km": 30.0,
            "psz_applicable": True,
            "pscz_length_m": 1000.0,
        }
        self.builder.translator = None
        self.captured = []

        def capture_layer(
            _self,
            geometry_type,
            layer_id,
            display_name,
            _fields,
            features,
            _group,
            style_key,
        ):
            self.captured.append(
                (geometry_type, layer_id, display_name, list(features), style_key)
            )
            return object()

        self.builder._create_and_add_layer = MethodType(capture_layer, self.builder)

    def test_uk_airport_consultation_circles_use_distinct_source_profiles(self):
        group = QgsLayerTreeGroup("UK")
        crs = QgsCoordinateReferenceSystem("EPSG:3857")
        arp = QgsPointXY(0.0, 0.0)

        self.assertTrue(
            self.builder.process_wildlife_safeguarding(arp, "EGXX", crs, group)
        )
        self.assertTrue(
            self.builder.process_wind_turbine_safeguarding(arp, "EGXX", crs, group)
        )

        by_style = {record[4]: record for record in self.captured}
        wildlife = by_style["UK Wildlife Consultation"][3][0]
        turbines = by_style["UK Wind Turbine Consultation"][3][0]
        self.assertEqual(wildlife.attribute("outer_rad_km"), 13.0)
        self.assertEqual(wildlife.attribute("profile_id"), "uk_caa_safeguarding")
        self.assertEqual(wildlife.attribute("geometry_status"), "indicative_default")
        self.assertEqual(turbines.attribute("radius_km"), 30.0)
        self.assertEqual(turbines.attribute("family_id"), "wind_energy_consultation")
        self.assertTrue(wildlife.geometry().isGeosValid())
        self.assertTrue(turbines.geometry().isGeosValid())

    def test_dft_psz_triangles_taper_outward_from_both_thresholds(self):
        group = QgsLayerTreeGroup("Public Safety Zones")
        runway_data = {
            "short_name": "09/27",
            "thr_point": QgsPointXY(0.0, 0.0),
            "rec_thr_point": QgsPointXY(2000.0, 0.0),
            "landing_available_1": True,
            "landing_available_2": True,
        }

        self.assertTrue(self.builder.process_public_safety_areas(runway_data, group))

        by_style = {record[4]: record for record in self.captured}
        psrz_features = by_style["UK PSRZ"][3]
        pscz_features = by_style["UK PSCZ"][3]
        self.assertEqual(len(psrz_features), 2)
        self.assertEqual(len(pscz_features), 2)
        self.assertEqual({feature.attribute("len_m") for feature in psrz_features}, {500.0})
        self.assertEqual({feature.attribute("thr_half_w") for feature in psrz_features}, {75.0})
        self.assertEqual({feature.attribute("len_m") for feature in pscz_features}, {1000.0})
        self.assertEqual({feature.attribute("thr_half_w") for feature in pscz_features}, {140.0})

        primary_psrz = next(
            feature for feature in psrz_features if feature.attribute("end_desig") == "09"
        )
        reciprocal_psrz = next(
            feature for feature in psrz_features if feature.attribute("end_desig") == "27"
        )
        self.assertAlmostEqual(primary_psrz.geometry().boundingBox().xMinimum(), -500.0, places=6)
        self.assertAlmostEqual(primary_psrz.geometry().boundingBox().xMaximum(), 0.0, places=6)
        self.assertAlmostEqual(reciprocal_psrz.geometry().boundingBox().xMinimum(), 2000.0, places=6)
        self.assertAlmostEqual(reciprocal_psrz.geometry().boundingBox().xMaximum(), 2500.0, places=6)
        self.assertTrue(all(feature.geometry().isGeosValid() for feature in psrz_features + pscz_features))

        self.captured.clear()
        runway_data["landing_available_2"] = False
        self.assertTrue(self.builder.process_public_safety_areas(runway_data, group))
        self.assertTrue(
            all(
                len(record[3]) == 1 and record[3][0].attribute("end_desig") == "09"
                for record in self.captured
            )
        )

    def test_framework_dispatch_preserves_nasf_wildlife_and_wind_outputs(self):
        self.builder.framework = get_framework_profile("nasf_aus")
        group = QgsLayerTreeGroup("NASF")
        crs = QgsCoordinateReferenceSystem("EPSG:3857")
        arp = QgsPointXY(0.0, 0.0)

        self.assertTrue(
            self.builder.process_wildlife_safeguarding(arp, "YXXX", crs, group)
        )
        self.assertTrue(
            self.builder.process_wind_turbine_safeguarding(arp, "YXXX", crs, group)
        )

        self.assertEqual(
            [record[4] for record in self.captured[:3]],
            ["WMZ A", "WMZ B", "WMZ C"],
        )
        nasf_turbine = self.captured[3][3][0]
        self.assertEqual(nasf_turbine.attribute("ref_nasf"), "NASF Guideline D")
        self.assertEqual(nasf_turbine.attribute("radius_km"), 30.0)


if __name__ == "__main__":
    unittest.main()
