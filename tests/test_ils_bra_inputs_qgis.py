"""QGIS dialog checks for provisional ILS BRA inputs."""

import sys
import unittest
from pathlib import Path

from qgis.PyQt import QtWidgets
from qgis.core import QgsApplication, QgsPointXY


WORKSPACE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORKSPACE.parent))

from safeguarding_builder.safeguarding_builder_dialog import SafeguardingBuilderDialog


class IlsBraInputsQgisTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        existing = QtWidgets.QApplication.instance()
        cls._owns_qgis_app = existing is None
        cls.app = existing or QgsApplication([], True)
        if cls._owns_qgis_app:
            cls.app.initQgis()

    @classmethod
    def tearDownClass(cls):
        if cls._owns_qgis_app:
            cls.app.exitQgis()

    def setUp(self):
        self.dialog = SafeguardingBuilderDialog()
        self.runway_index = min(self.dialog._runway_groups)
        runway = self.dialog._runway_groups[self.runway_index]
        runway.desig_le.setText("09")
        runway.suffix_combo.setCurrentText("L")
        runway.thr_east_le.setText("455000")
        runway.thr_north_le.setText("5772000")
        runway.rec_east_le.setText("456000")
        runway.rec_north_le.setText("5772000")
        self.dialog.refresh_ils_bra_runway_options()
        self.validated_runway = {
            "original_index": self.runway_index,
            "thr_point": QgsPointXY(455000, 5772000),
            "rec_thr_point": QgsPointXY(456000, 5772000),
            "type1": "Precision Approach CAT I",
            "type2": "Precision Approach CAT II/III",
        }

    def tearDown(self):
        self.dialog.close()
        self.dialog.deleteLater()

    def test_derived_glide_path_position_captures_generation_inputs(self):
        self.dialog.add_ils_bra_row(
            {
                "component": "glide_path",
                "runway_ref": f"{self.runway_index}:1",
                "id": "GP-09L",
                "position_mode": "runway_offset",
                "distance_inside_threshold": "300",
                "signed_offset": "120",
                "ground_elevation": "18.5",
                "source_reference": "NASF worked-example provisional construction",
            }
        )

        self.assertEqual(self.dialog.table_ils_bra.columnCount(), 10)
        errors = []
        installations = self.dialog.get_ils_bra_input_data(
            [self.validated_runway],
            errors,
        )

        self.assertEqual(errors, [])
        self.assertEqual(len(installations), 1)
        installation = installations[0]
        self.assertAlmostEqual(installation["easting"], 455300.0)
        self.assertAlmostEqual(installation["northing"], 5771880.0)
        self.assertEqual(installation["antenna_offset"], 120.0)
        self.assertTrue(installation["provisional"])

    def test_direct_coordinates_derive_runway_offset(self):
        self.dialog.add_ils_bra_row(
            {
                "component": "glide_path",
                "runway_ref": f"{self.runway_index}:1",
                "id": "GP-DIRECT",
                "position_mode": "direct",
                "easting": "455300",
                "northing": "5771880",
                "ground_elevation": "19",
                "source_reference": "Surveyed antenna front face",
            }
        )
        errors = []
        installation = self.dialog.get_ils_bra_input_data(
            [self.validated_runway], errors
        )[0]
        self.assertEqual(errors, [])
        self.assertAlmostEqual(installation["distance_inside_threshold"], 300.0)
        self.assertAlmostEqual(installation["signed_offset"], 120.0)

    def test_localiser_position_is_derived_beyond_opposite_runway_end(self):
        self.dialog.add_ils_bra_row(
            {
                "component": "localiser",
                "runway_ref": f"{self.runway_index}:1",
                "id": "LOC-09L",
                "position_mode": "runway_offset",
                "runway_relative_distance": "300",
                "ground_elevation": "17.5",
                "source_reference": "NASF worked-example provisional construction",
            }
        )
        errors = []
        installation = self.dialog.get_ils_bra_input_data(
            [self.validated_runway], errors
        )[0]

        self.assertEqual(errors, [])
        self.assertAlmostEqual(installation["easting"], 456300.0)
        self.assertAlmostEqual(installation["northing"], 5772000.0)
        self.assertEqual(installation["distance_beyond_runway_end"], 300.0)
        self.assertEqual(installation["signed_offset"], 0.0)
        self.assertEqual(installation["localiser_category"], "cat_i")
        self.assertEqual(installation["runway_length"], 1000.0)

    def test_localiser_direct_coordinates_must_follow_extended_centreline(self):
        self.dialog.add_ils_bra_row(
            {
                "component": "localiser",
                "runway_ref": f"{self.runway_index}:1",
                "id": "LOC-OFFSET",
                "position_mode": "direct",
                "easting": "456300",
                "northing": "5772005",
                "ground_elevation": "17.5",
                "source_reference": "Surveyed localiser",
            }
        )
        errors = []
        installations = self.dialog.get_ils_bra_input_data(
            [self.validated_runway], errors
        )
        self.assertEqual(installations, [])
        self.assertTrue(any("extended runway centreline" in error for error in errors))

    def test_rows_round_trip_through_persistence_shape(self):
        source = {
            "component": "glide_path",
            "runway_ref": f"{self.runway_index}:2",
            "id": "GP-27R",
            "position_mode": "runway_offset",
            "distance_inside_threshold": "300",
            "signed_offset": "-130",
            "ground_elevation": "19",
            "source_reference": "Worked-example provisional construction",
        }
        self.dialog.add_ils_bra_row(source)
        saved = self.dialog.get_ils_bra_save_rows()
        payload = self.dialog._build_save_payload("TEST")
        self.dialog.load_ils_bra_rows(saved)

        self.assertEqual(payload["ils_bra_installations"][0]["id"], "GP-27R")
        self.assertTrue(payload["ils_bra_installations"][0]["provisional"])
        self.assertEqual(self.dialog.table_ils_bra.rowCount(), 1)
        self.assertEqual(self.dialog.table_ils_bra.cellWidget(0, 1).currentText(), "RWY 27R approach end")


if __name__ == "__main__":
    unittest.main()
