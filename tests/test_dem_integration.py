import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from qgis.PyQt import QtCore, QtWidgets
from qgis.core import QgsFeature, QgsField, QgsGeometry, QgsProject, QgsVectorLayer


WORKSPACE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORKSPACE.parent))

from safeguarding_builder.core.dem_integration import (  # noqa: E402
    CONTOUR_POLYGON_ALGORITHM_ID,
    OPEN_TOPOGRAPHY_ALGORITHM_ID,
    apply_elevation_polygon_style,
    create_elevation_polygons,
    elevation_polygon_output_path,
    open_topography_dialog,
)
from safeguarding_builder.safeguarding_builder_dialog import (  # noqa: E402
    SafeguardingBuilderDialog,
)


class DemIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def tearDown(self):
        QgsProject.instance().removeAllMapLayers()

    def test_terrain_tab_enables_downloader_for_a_vector_extent(self):
        layer = QgsVectorLayer("Polygon?crs=EPSG:7856", "DEM extent", "memory")
        QgsProject.instance().addMapLayer(layer)

        with patch(
            "safeguarding_builder.dialog.dem_tools.open_topography_algorithm",
            return_value=object(),
        ):
            dialog = SafeguardingBuilderDialog()
            dialog.comboBox_dem_extent_layer.setLayer(layer)
            dialog.refresh_dem_tool_state()

            self.assertGreaterEqual(
                dialog.tabWidget_workflow.indexOf(dialog.tab_terrain),
                0,
            )
            self.assertIs(dialog.selected_dem_extent_layer(), layer)
            self.assertTrue(dialog.pushButton_DownloadDem.isEnabled())
            self.assertIn("pre-filled", dialog.label_dem_tool_status.text())

            self.assertFalse(dialog.pushButton_CreateDemContours.isEnabled())
            dialog.set_downloaded_dem(layer)
            self.assertTrue(dialog.pushButton_CreateDemContours.isEnabled())
            self.assertEqual(dialog.dem_contour_interval(), 5.0)
            self.assertEqual(dialog.dem_contour_output_mode(), "temporary")

            dialog.close()
            dialog.deleteLater()

    def test_processing_dialog_receives_the_selected_layer_as_extent(self):
        layer = QgsVectorLayer("Polygon?crs=EPSG:7856", "DEM extent", "memory")
        calls = []
        processing_module = types.SimpleNamespace(
            execAlgorithmDialog=lambda algorithm_id, parameters: calls.append(
                (algorithm_id, parameters)
            )
        )

        with patch(
            "safeguarding_builder.core.dem_integration.open_topography_algorithm",
            return_value=object(),
        ), patch.dict(sys.modules, {"processing": processing_module}):
            open_topography_dialog(layer)

        self.assertEqual(
            calls,
            [(OPEN_TOPOGRAPHY_ALGORITHM_ID, {"Extent": layer})],
        )

    def test_contour_processing_uses_polygon_band_parameters(self):
        calls = []
        processing_module = types.SimpleNamespace(
            run=lambda algorithm_id, parameters: (
                calls.append((algorithm_id, parameters))
                or {"OUTPUT": "bands.gpkg"}
            )
        )

        with patch(
            "safeguarding_builder.core.dem_integration.contour_polygon_algorithm",
            return_value=object(),
        ), patch.dict(sys.modules, {"processing": processing_module}):
            result = create_elevation_polygons("dem.tif", 5.0, "bands.gpkg")

        self.assertEqual(result, "bands.gpkg")
        algorithm_id, parameters = calls[0]
        self.assertEqual(algorithm_id, CONTOUR_POLYGON_ALGORITHM_ID)
        self.assertEqual(parameters["INTERVAL"], 5.0)
        self.assertEqual(parameters["FIELD_NAME_MIN"], "ELEV_MIN")
        self.assertEqual(parameters["FIELD_NAME_MAX"], "ELEV_MAX")

    def test_elevation_band_style_and_saved_path_are_deterministic(self):
        layer = QgsVectorLayer("Polygon?crs=EPSG:7856", "bands", "memory")
        layer.dataProvider().addAttributes(
            [
                QgsField("ELEV_MIN", QtCore.QMetaType.Type.Double),
                QgsField("ELEV_MAX", QtCore.QMetaType.Type.Double),
            ]
        )
        layer.updateFields()
        features = []
        for lower, upper, x_offset in ((0.0, 5.0, 0), (5.0, 10.0, 20)):
            feature = QgsFeature(layer.fields())
            feature.setAttributes([lower, upper])
            feature.setGeometry(
                QgsGeometry.fromWkt(
                    "POLYGON (({x} 0, {x2} 0, {x2} 10, {x} 10, {x} 0))".format(
                        x=x_offset,
                        x2=x_offset + 10,
                    )
                )
            )
            features.append(feature)
        layer.dataProvider().addFeatures(features)

        self.assertTrue(apply_elevation_polygon_style(layer))
        self.assertEqual(layer.renderer().classAttribute(), "ELEV_MIN")
        self.assertEqual(len(layer.renderer().categories()), 2)

        with tempfile.TemporaryDirectory() as directory:
            first = Path(directory) / "dem_elevation_bands.gpkg"
            first.touch()
            output = elevation_polygon_output_path(
                str(Path(directory) / "dem.tif"),
                directory,
            )
            self.assertTrue(output.endswith("dem_elevation_bands_2.gpkg"))


if __name__ == "__main__":
    unittest.main()
