import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from qgis.PyQt import QtCore, QtWidgets
from qgis.core import (
    QgsApplication,
    QgsCoordinateReferenceSystem,
    QgsProject,
    QgsVectorLayer,
)


WORKSPACE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORKSPACE.parent))

from safeguarding_builder.core.osm_aeroway import (
    AEROWAY_RADIUS_M,
    OVERPASS_ENDPOINTS,
    apply_aeroway_style,
    build_aeroway_query,
    fetch_aeroway_osm,
)
from safeguarding_builder.safeguarding_builder_dialog import SafeguardingBuilderDialog
from safeguarding_builder.safeguarding_builder import SafeguardingBuilder


class OsmAerowayTests(unittest.TestCase):
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

    def test_query_covers_all_element_types_at_fixed_radius(self):
        query = build_aeroway_query(-33.9461, 151.1772)

        self.assertEqual(AEROWAY_RADIUS_M, 5_000)
        self.assertIn('node["aeroway"](around:5000,-33.9461000,151.1772000)', query)
        self.assertIn('way["aeroway"](around:5000,-33.9461000,151.1772000)', query)
        self.assertIn(
            'relation["aeroway"](around:5000,-33.9461000,151.1772000)',
            query,
        )
        self.assertTrue(query.endswith("out body qt;"))

    def test_download_fails_over_to_second_endpoint(self):
        valid_osm = b'<osm version="0.6" generator="test"/>'
        attempts = []
        with patch(
            "safeguarding_builder.core.osm_aeroway._post_overpass",
            side_effect=[RuntimeError("HTTP 504"), valid_osm],
        ) as post:
            result = fetch_aeroway_osm(
                -33.9461,
                151.1772,
                attempt_callback=lambda attempt, total: attempts.append(
                    (attempt, total)
                ),
            )

        self.assertEqual(result, valid_osm)
        self.assertEqual(attempts, [(1, 2), (2, 2)])
        self.assertEqual(post.call_count, 2)
        self.assertEqual(post.call_args_list[0].args[0], OVERPASS_ENDPOINTS[0])
        self.assertEqual(post.call_args_list[1].args[0], OVERPASS_ENDPOINTS[1])

    def test_download_reports_failure_after_all_endpoints(self):
        with patch(
            "safeguarding_builder.core.osm_aeroway._post_overpass",
            side_effect=RuntimeError("gateway timeout"),
        ):
            with self.assertRaisesRegex(
                RuntimeError,
                "All Overpass endpoints failed",
            ):
                fetch_aeroway_osm(-33.9461, 151.1772)

    def test_query_rejects_invalid_coordinates(self):
        with self.assertRaises(ValueError):
            build_aeroway_query(91, 0)
        with self.assertRaises(ValueError):
            build_aeroway_query(0, 181)

    def test_airfield_plan_style_prioritizes_movement_surfaces(self):
        runway = QgsVectorLayer("LineString?crs=EPSG:3857", "runway", "memory")
        apply_aeroway_style(runway, "runway")
        runway_symbol = runway.renderer().symbol()
        self.assertEqual(runway_symbol.color().name(), "#454c54")
        self.assertEqual(runway_symbol.symbolLayerCount(), 2)
        self.assertEqual(
            runway_symbol.symbolLayer(1).color().name(),
            "#f7f7f3",
        )

        aerodrome = QgsVectorLayer(
            "Polygon?crs=EPSG:3857",
            "aerodrome",
            "memory",
        )
        apply_aeroway_style(aerodrome, "aerodrome")
        self.assertEqual(
            aerodrome.renderer().symbol().color().name(),
            "#e8edf2",
        )
        self.assertAlmostEqual(aerodrome.renderer().symbol().opacity(), 0.18)

    def test_dialog_exposes_arp_download_button(self):
        dialog = SafeguardingBuilderDialog()
        try:
            self.assertEqual(
                dialog.pushButton_DownloadOsmAeroway.text(),
                "Download OSM aeroway features within 5 km",
            )
        finally:
            dialog.close()
            dialog.deleteLater()

    def test_download_uses_an_immediate_indeterminate_progress_dialog(self):
        dialog = SafeguardingBuilderDialog()
        builder = SafeguardingBuilder.__new__(SafeguardingBuilder)
        builder.translator = None
        builder.dlg = dialog
        progress = builder._create_osm_download_progress_dialog()
        try:
            progress.show()
            QtWidgets.QApplication.processEvents()
            self.assertEqual(
                progress.windowTitle(),
                "Downloading airport map elements",
            )
            self.assertEqual(progress.progress_bar.minimum(), 0)
            self.assertEqual(progress.progress_bar.maximum(), 0)
            self.assertGreaterEqual(progress.minimumWidth(), 520)
            self.assertGreaterEqual(progress.minimumHeight(), 96)
            self.assertGreaterEqual(progress.width(), 520)
            self.assertGreaterEqual(progress.height(), 96)
            window_types = getattr(QtCore.Qt, "WindowType", QtCore.Qt)
            widget_attributes = getattr(
                QtCore.Qt,
                "WidgetAttribute",
                QtCore.Qt,
            )
            self.assertTrue(
                progress.windowFlags() & window_types.FramelessWindowHint
            )
            self.assertTrue(
                progress.testAttribute(
                    widget_attributes.WA_TranslucentBackground
                )
            )
            self.assertIn("border-radius: 10px", progress.styleSheet())
        finally:
            progress.close()
            progress.deleteLater()
            dialog.close()
            dialog.deleteLater()

    def test_download_status_messages_use_plain_english(self):
        builder = SafeguardingBuilder.__new__(SafeguardingBuilder)
        builder.translator = None

        self.assertEqual(
            builder._osm_download_attempt_message(1, 2),
            "Getting the airport map elements…",
        )
        self.assertEqual(
            builder._osm_download_attempt_message(2, 2),
            "The first map server did not respond. Trying a second server…",
        )
        self.assertIn(
            "taking longer than usual",
            builder._osm_download_slow_message(1, 2),
        )

    def test_download_starts_in_background_and_leaves_progress_visible(self):
        dialog = SafeguardingBuilderDialog()
        dialog.lineEdit_arp_easting.setText("507000")
        dialog.lineEdit_arp_northing.setText("5707000")
        QgsProject.instance().setCrs(QgsCoordinateReferenceSystem("EPSG:32630"))
        builder = SafeguardingBuilder.__new__(SafeguardingBuilder)
        builder.translator = None
        builder.dlg = dialog
        builder.iface = MagicMock()
        progress = MagicMock()
        task = MagicMock()
        manager = MagicMock()
        manager.addTask.return_value = True
        try:
            with (
                patch.object(
                    builder,
                    "_create_osm_download_progress_dialog",
                    return_value=progress,
                ),
                patch(
                    "safeguarding_builder.safeguarding_builder.QgsTask.fromFunction",
                    return_value=task,
                ),
                patch(
                    "safeguarding_builder.safeguarding_builder.QgsApplication.taskManager",
                    return_value=manager,
                ),
            ):
                builder.download_osm_aeroway()

            progress.show.assert_called_once()
            manager.addTask.assert_called_once_with(task)
            task.progressChanged.connect.assert_called_once()
            self.assertFalse(dialog.pushButton_DownloadOsmAeroway.isEnabled())
        finally:
            dialog.close()
            dialog.deleteLater()

    def test_qgis_splits_downloaded_features_into_aeroway_layers(self):
        osm = b"""<?xml version="1.0" encoding="UTF-8"?>
<osm version="0.6" generator="test">
  <node id="1" lat="-33.9461" lon="151.1772">
    <tag k="aeroway" v="parking_position"/>
  </node>
  <node id="2" lat="-33.9460" lon="151.1770"/>
  <node id="3" lat="-33.9450" lon="151.1780"/>
  <node id="4" lat="-33.9462" lon="151.1774">
    <tag k="aeroway" v="holding_position"/>
  </node>
  <node id="5" lat="-33.9440" lon="151.1780"/>
  <node id="6" lat="-33.9440" lon="151.1790"/>
  <node id="7" lat="-33.9450" lon="151.1790"/>
  <node id="8" lat="-33.9438" lon="151.1778">
    <tag k="aeroway" v="navigationaid"/>
    <tag k="navigationaid" v="als"/>
  </node>
  <node id="9" lat="-33.9436" lon="151.1776">
    <tag k="aeroway" v="navigationaid"/>
    <tag k="navigationaid" v="papi"/>
  </node>
  <node id="12" lat="-33.9434" lon="151.1774">
    <tag k="aeroway" v="navigationaid"/>
    <tag k="navigationaid" v="vasi"/>
  </node>
  <way id="10">
    <nd ref="2"/>
    <nd ref="3"/>
    <tag k="aeroway" v="taxiway"/>
  </way>
  <way id="11">
    <nd ref="3"/>
    <nd ref="5"/>
    <nd ref="6"/>
    <nd ref="7"/>
    <nd ref="3"/>
    <tag k="aeroway" v="apron"/>
  </way>
</osm>
"""
        project = QgsProject.instance()
        project.clear()
        project.setCrs(QgsCoordinateReferenceSystem("EPSG:3857"))
        builder = SafeguardingBuilder.__new__(SafeguardingBuilder)
        builder.translator = None
        with tempfile.NamedTemporaryFile(suffix=".osm") as osm_file:
            osm_file.write(osm)
            osm_file.flush()
            loaded = builder._load_osm_aeroway_layers(osm_file.name)

        self.assertEqual(
            {layer.name() for layer in project.mapLayers().values()},
            {
                "apron",
                "holding_position",
                "navigationaid",
                "parking_position",
                "taxiway",
            },
        )
        self.assertEqual(loaded, 5)
        self.assertEqual(project.crs().authid(), "EPSG:3857")
        for layer in project.mapLayers().values():
            self.assertEqual(layer.crs().authid(), "EPSG:3857")
            self.assertGreaterEqual(layer.fields().indexOf("aeroway"), 0)
            self.assertGreaterEqual(layer.featureCount(), 1)
        navigation_layer = next(
            layer
            for layer in project.mapLayers().values()
            if layer.name() == "navigationaid"
        )
        self.assertGreaterEqual(
            navigation_layer.fields().indexOf("navigationaid"),
            0,
        )
        self.assertEqual(
            {feature["navigationaid"] for feature in navigation_layer.getFeatures()},
            {"als", "papi", "vasi"},
        )
        self.assertGreaterEqual(
            navigation_layer.fields().indexOf("other_tags"),
            0,
        )
        navigation_point = next(navigation_layer.getFeatures()).geometry().asPoint()
        self.assertGreater(abs(navigation_point.x()), 1_000_000)
        self.assertGreater(abs(navigation_point.y()), 1_000_000)
        layers_by_name = {
            layer.name(): layer for layer in project.mapLayers().values()
        }
        for name, layer in layers_by_name.items():
            self.assertEqual(
                layer.customProperty("safeguarding_builder/osm_aeroway_style"),
                name,
            )
        self.assertEqual(
            layers_by_name["taxiway"].renderer().symbol().color().name(),
            "#7c858e",
        )
        self.assertAlmostEqual(
            layers_by_name["taxiway"].renderer().symbol().width(),
            1.8,
        )
        taxiway_symbol = layers_by_name["taxiway"].renderer().symbol()
        self.assertEqual(taxiway_symbol.symbolLayerCount(), 2)
        self.assertEqual(
            taxiway_symbol.symbolLayer(1).color().name(),
            "#f2c230",
        )
        self.assertAlmostEqual(
            taxiway_symbol.symbolLayer(1).width(),
            0.28,
        )
        navigation_renderer = layers_by_name["navigationaid"].renderer()
        self.assertEqual(navigation_renderer.type(), "categorizedSymbol")
        self.assertEqual(
            {
                str(category.value()): category.symbol().color().name()
                for category in navigation_renderer.categories()
            },
            {
                "als": "#d18b00",
                "papi": "#7557b8",
                "vasi": "#9868c8",
            },
        )
        self.assertTrue(
            layers_by_name["navigationaid"].hasScaleBasedVisibility()
        )
        self.assertEqual(
            layers_by_name["navigationaid"].minimumScale(),
            25_000,
        )
        self.assertTrue(
            layers_by_name["parking_position"].hasScaleBasedVisibility()
        )
        self.assertEqual(
            layers_by_name["parking_position"].minimumScale(),
            10_000,
        )
        self.assertEqual(
            layers_by_name["apron"].renderer().symbol().color().name(),
            "#c7cdd2",
        )
        self.assertAlmostEqual(
            layers_by_name["apron"].renderer().symbol().opacity(),
            0.68,
        )
        group = project.layerTreeRoot().findGroup(
            "OSM aeroway — 5 km from ARP"
        )
        self.assertIsNotNone(group)
        self.assertEqual(
            [child.name() for child in group.children()],
            [
                "navigationaid",
                "holding_position",
                "parking_position",
                "taxiway",
                "apron",
            ],
        )
        project.clear()


if __name__ == "__main__":
    unittest.main()
