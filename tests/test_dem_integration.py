import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from qgis.PyQt import QtWidgets
from qgis.core import QgsProject, QgsVectorLayer


WORKSPACE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORKSPACE.parent))

from safeguarding_builder.core.dem_integration import (  # noqa: E402
    OPEN_TOPOGRAPHY_ALGORITHM_ID,
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


if __name__ == "__main__":
    unittest.main()
