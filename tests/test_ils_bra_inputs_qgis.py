"""QGIS dialog checks for ILS Building Restricted Area inputs."""

import sys
import unittest
from pathlib import Path

from qgis.PyQt import QtWidgets
from qgis.core import QgsApplication, QgsWkbTypes


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
        self.dialog.refresh_ils_bra_runway_options()

    def tearDown(self):
        self.dialog.close()
        self.dialog.deleteLater()

    def test_installation_row_captures_generation_inputs(self):
        self.dialog.add_ils_bra_row(
            {
                "component": "localiser",
                "runway_ref": f"{self.runway_index}:1",
                "id": "LOC-09L",
                "easting": "455000",
                "northing": "5772000",
                "ground_elevation": "18.5",
                "vehicle_critical_area_source": "Airservices drawing ABC-123",
                "vehicle_critical_area_wkt": "POLYGON ((454900 5771900, 455100 5771900, 455100 5772100, 454900 5772100, 454900 5771900))",
            }
        )

        table = self.dialog.table_ils_bra
        self.assertEqual(table.columnCount(), 8)
        self.assertEqual(table.cellWidget(0, 0).currentData(), "localiser")
        self.assertEqual(table.cellWidget(0, 1).currentText(), "RWY 09L approach end")

        errors = []
        installations = self.dialog.get_ils_bra_input_data(
            [{"original_index": self.runway_index}],
            errors,
        )
        self.assertEqual(errors, [])
        self.assertEqual(len(installations), 1)
        self.assertEqual(installations[0]["runway_end"], 1)
        self.assertEqual(
            installations[0]["vehicle_critical_area"].type(),
            QgsWkbTypes.PolygonGeometry,
        )

    def test_rows_round_trip_through_persistence_shape(self):
        source = {
            "component": "glide_path",
            "runway_ref": f"{self.runway_index}:2",
            "id": "GP-27R",
            "easting": "455200",
            "northing": "5772200",
            "ground_elevation": "19",
            "vehicle_critical_area_source": "Derived from approved critical-area plan",
            "vehicle_critical_area_wkt": "POLYGON ((0 0, 10 0, 10 10, 0 10, 0 0))",
        }
        self.dialog.add_ils_bra_row(source)
        saved = self.dialog.get_ils_bra_save_rows()
        payload = self.dialog._build_save_payload("TEST")
        self.dialog.load_ils_bra_rows(saved)

        self.assertEqual(payload["ils_bra_installations"][0]["id"], "GP-27R")
        self.assertEqual(self.dialog.table_ils_bra.rowCount(), 1)
        self.assertEqual(self.dialog.get_ils_bra_save_rows()[0]["id"], "GP-27R")
        self.assertEqual(self.dialog.table_ils_bra.cellWidget(0, 1).currentText(), "RWY 27R approach end")


if __name__ == "__main__":
    unittest.main()
