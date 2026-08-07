import sys
import tempfile
import types
import unittest
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from unittest.mock import patch

from qgis.PyQt import QtCore, QtWidgets
from qgis.core import QgsFeature, QgsField, QgsGeometry, QgsProject, QgsVectorLayer


WORKSPACE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORKSPACE.parent))

from safeguarding_builder.core.dem_integration import (  # noqa: E402
    CONTOUR_POLYGON_ALGORITHM_ID,
    OPEN_TOPOGRAPHY_ALGORITHM_ID,
    apply_elevation_polygon_style,
    build_ga_wcs_url,
    build_ga_wcs_urls,
    create_elevation_polygons,
    create_ols_square_extent_layer,
    download_ga_dem,
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

    def test_terrain_tab_enables_ga_downloader_for_a_vector_extent(self):
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
            self.assertIsNone(dialog.selected_dem_extent_layer())
            self.assertTrue(dialog.comboBox_dem_extent_layer.isHidden())
            self.assertTrue(dialog.pushButton_DownloadDem.isEnabled())
            self.assertEqual(dialog.selected_dem_source(), "ga_best")
            self.assertTrue(dialog.label_dem_tool_status.isHidden())
            self.assertEqual(dialog.comboBox_dem_source.minimumHeight(), 26)
            self.assertEqual(dialog.comboBox_dem_source.maximumHeight(), 26)
            self.assertEqual(dialog.pushButton_dem_extent_override.height(), 26)
            self.assertEqual(dialog.doubleSpinBox_dem_contour_interval.height(), 26)
            self.assertEqual(dialog.pushButton_DownloadDem.height(), 32)
            self.assertEqual(dialog.pushButton_CreateDemContours.height(), 32)
            self.assertEqual(dialog.pushButton_dem_extent_override.width(), 126)
            self.assertEqual(dialog.widget_dem_extent_row.layout().spacing(), 10)
            self.assertEqual(dialog.pushButton_DownloadDem.width(), 198)
            self.assertEqual(dialog.pushButton_CreateDemContours.width(), 198)
            self.assertEqual(dialog.groupBox_dem_tools.layout().columnMinimumWidth(0), 200)
            self.assertEqual(dialog.comboOutputFormat.minimumHeight(), 26)
            self.assertEqual(dialog.comboOutputFormat.maximumHeight(), 26)
            self.assertEqual(dialog.pushButton_add_CNS.minimumHeight(), 26)
            self.assertEqual(dialog.pushButton_add_CNS.maximumHeight(), 26)
            self.assertEqual(dialog.pushButton_DownloadOsmAeroway.minimumHeight(), 32)
            self.assertEqual(dialog.pushButton_DownloadOsmAeroway.maximumHeight(), 32)
            self.assertEqual(dialog.pushButton_Generate.minimumHeight(), 32)
            self.assertEqual(dialog.pushButton_Generate.maximumHeight(), 32)

            dialog.pushButton_dem_extent_override.setChecked(True)
            self.assertFalse(dialog.comboBox_dem_extent_layer.isHidden())
            self.assertIs(dialog.selected_dem_extent_layer(), layer)
            self.assertEqual(
                dialog.pushButton_dem_extent_override.text(),
                "Automatic",
            )
            self.assertTrue(dialog.label_dem_tool_status.isHidden())

            self.assertFalse(dialog.pushButton_CreateDemContours.isEnabled())
            self.assertFalse(dialog.doubleSpinBox_dem_contour_interval.isEnabled())
            self.assertFalse(dialog.comboBox_dem_contour_output.isEnabled())
            dialog.set_downloaded_dem(layer)
            self.assertTrue(dialog.pushButton_CreateDemContours.isEnabled())
            self.assertTrue(dialog.doubleSpinBox_dem_contour_interval.isEnabled())
            self.assertTrue(dialog.comboBox_dem_contour_output.isEnabled())
            self.assertEqual(dialog.dem_contour_interval(), 5.0)
            self.assertEqual(dialog.dem_contour_output_mode(), "temporary")

            dialog.close()
            dialog.deleteLater()

    def test_ga_wcs_request_uses_layer_extent_and_native_resolution(self):
        layer = QgsVectorLayer("Polygon?crs=EPSG:4326", "DEM extent", "memory")
        feature = QgsFeature(layer.fields())
        feature.setGeometry(
            QgsGeometry.fromWkt(
                "POLYGON ((138.50 -34.97, 138.57 -34.97, "
                "138.57 -34.91, 138.50 -34.91, 138.50 -34.97))"
            )
        )
        layer.dataProvider().addFeature(feature)
        layer.updateExtents()

        url = build_ga_wcs_url(layer, "ga_lidar_5m")
        query = parse_qs(urlparse(url).query)

        self.assertIn("DEM_LiDAR_5m_2025", url)
        self.assertEqual(query["coverage"], ["1"])
        self.assertEqual(query["format"], ["GeoTIFF"])
        self.assertEqual(query["crs"], ["EPSG:4283"])
        self.assertEqual(query["bbox"], ["138.500000000000,-34.970000000000,138.570000000000,-34.910000000000"])

    def test_automatic_ols_extent_is_the_smallest_enclosing_square(self):
        project = QgsProject.instance()
        previous_crs = project.crs()
        layer_crs = QgsVectorLayer("Polygon?crs=EPSG:7856", "crs", "memory").crs()
        project.setCrs(layer_crs)
        main_group = project.layerTreeRoot().addGroup("YPAD Safeguarding Builder")
        ols_group = main_group.addGroup("04 Obstacle Limitation Surfaces")
        for name, wkt in (
            ("west", "POLYGON ((0 0, 100 0, 100 50, 0 50, 0 0))"),
            ("east", "POLYGON ((200 50, 300 50, 300 100, 200 100, 200 50))"),
        ):
            layer = QgsVectorLayer("Polygon?crs=EPSG:7856", name, "memory")
            feature = QgsFeature(layer.fields())
            feature.setGeometry(QgsGeometry.fromWkt(wkt))
            layer.dataProvider().addFeature(feature)
            layer.updateExtents()
            project.addMapLayer(layer, False)
            ols_group.addLayer(layer)

        extent_layer = create_ols_square_extent_layer("YPAD")
        extent = extent_layer.extent()

        self.assertAlmostEqual(extent.width(), 300.0)
        self.assertAlmostEqual(extent.height(), 300.0)
        self.assertAlmostEqual(extent.xMinimum(), 0.0)
        self.assertAlmostEqual(extent.yMinimum(), -100.0)
        project.layerTreeRoot().removeChildNode(main_group)
        project.setCrs(previous_crs)

    def test_ga_dem_download_saves_geotiff_and_metadata(self):
        layer = QgsVectorLayer("Polygon?crs=EPSG:4326", "DEM extent", "memory")
        feature = QgsFeature(layer.fields())
        feature.setGeometry(
            QgsGeometry.fromWkt(
                "POLYGON ((138.50 -34.97, 138.51 -34.97, "
                "138.51 -34.96, 138.50 -34.96, 138.50 -34.97))"
            )
        )
        layer.dataProvider().addFeature(feature)
        layer.updateExtents()

        with tempfile.TemporaryDirectory() as directory, patch(
            "safeguarding_builder.core.dem_integration._download_ga_wcs",
            return_value=b"II*\x00test-geotiff",
        ):
            output = Path(directory) / "terrain.tif"
            metadata = download_ga_dem(layer, "ga_srtm_30m", str(output))

            self.assertEqual(output.read_bytes(), b"II*\x00test-geotiff")
            self.assertEqual(metadata["source_service"], "Geoscience Australia WCS")
            self.assertEqual(metadata["vertical_epsg"], "EPSG:5773")

    def test_large_ga_extent_is_split_within_service_tile_limits(self):
        layer = QgsVectorLayer("Polygon?crs=EPSG:4326", "large extent", "memory")
        feature = QgsFeature(layer.fields())
        feature.setGeometry(
            QgsGeometry.fromWkt(
                "POLYGON ((152.945321310581 -27.533738722424, "
                "153.290813120101 -27.533738722424, "
                "153.290813120101 -27.225445896170, "
                "152.945321310581 -27.225445896170, "
                "152.945321310581 -27.533738722424))"
            )
        )
        layer.dataProvider().addFeature(feature)
        layer.updateExtents()

        urls = build_ga_wcs_urls(layer, "ga_lidar_5m")

        self.assertEqual(len(urls), 12)

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
        for lower in range(0, 30, 5):
            feature = QgsFeature(layer.fields())
            feature.setAttributes([float(lower), float(lower + 5)])
            feature.setGeometry(
                QgsGeometry.fromWkt(
                    "POLYGON (({x} 0, {x2} 0, {x2} 10, {x} 10, {x} 0))".format(
                        x=lower * 4,
                        x2=lower * 4 + 10,
                    )
                )
            )
            features.append(feature)
        layer.dataProvider().addFeatures(features)

        self.assertTrue(apply_elevation_polygon_style(layer))
        self.assertEqual(layer.renderer().classAttribute(), "ELEV_MIN")
        categories = layer.renderer().categories()
        self.assertEqual(
            [category.symbol().color().name() for category in categories],
            [
                "#41644a",
                "#78966a",
                "#b7ad72",
                "#b58a55",
                "#7a5940",
                "#d5d0c4",
            ],
        )
        for category in categories:
            self.assertEqual(
                category.symbol().symbolLayer(0).strokeColor().name(),
                "#4e5147",
            )

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
