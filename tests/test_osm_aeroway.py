import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from qgis.PyQt import QtCore, QtWidgets
from qgis.core import (
    QgsApplication,
    QgsCoordinateReferenceSystem,
    QgsFeature,
    QgsGeometry,
    QgsProject,
    QgsVectorLayer,
    Qgis,
)


WORKSPACE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORKSPACE.parent))

from safeguarding_builder.core.osm_aeroway import (
    AEROWAY_RADIUS_M,
    OVERPASS_ENDPOINTS,
    OVERPASS_QUERY_TIMEOUT_S,
    OVERPASS_TRANSFER_TIMEOUT_MS,
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
        self.assertEqual(OVERPASS_QUERY_TIMEOUT_S, 15)
        self.assertEqual(OVERPASS_TRANSFER_TIMEOUT_MS, 20_000)
        self.assertTrue(query.startswith("[out:xml][timeout:15];"))
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

    def test_airfield_labels_use_attributes_only_at_close_scale(self):
        cases = (
            ("LineString", "taxiway", ("ref", "name"), '"ref"'),
            ("Point", "parking_position", ("ref", "name"), '"ref"'),
            ("Point", "gate", ("ref", "name"), '"ref"'),
            ("Polygon", "terminal", ("ref", "name"), '"name"'),
        )
        for geometry, category, fields, preferred_field in cases:
            with self.subTest(category=category):
                field_query = "&".join(
                    f"field={field}:string" for field in fields
                )
                layer = QgsVectorLayer(
                    f"{geometry}?crs=EPSG:3857&{field_query}",
                    category,
                    "memory",
                )
                apply_aeroway_style(layer, category)

                self.assertTrue(layer.labelsEnabled())
                settings = layer.labeling().settings()
                self.assertTrue(settings.isExpression)
                self.assertTrue(settings.fieldName.startswith("coalesce("))
                self.assertLess(
                    settings.fieldName.index(preferred_field),
                    len(settings.fieldName),
                )
                self.assertTrue(settings.scaleVisibility)
                self.assertEqual(settings.minimumScale, 3_000)
                self.assertEqual(settings.maximumScale, 1)
                if category == "taxiway":
                    self.assertFalse(settings.lineSettings().mergeLines())

    def test_taxiway_segments_render_as_one_network_without_merging_features(self):
        layer = QgsVectorLayer(
            "LineString?crs=EPSG:3857&field=ref:string",
            "taxiway",
            "memory",
        )
        features = []
        for ref, wkt in (
            ("A", "LINESTRING (0 0, 10 0)"),
            ("B", "LINESTRING (10 0, 20 5)"),
        ):
            feature = QgsFeature(layer.fields())
            feature["ref"] = ref
            feature.setGeometry(QgsGeometry.fromWkt(wkt))
            features.append(feature)
        layer.dataProvider().addFeatures(features)
        apply_aeroway_style(layer, "taxiway")

        renderer = layer.renderer()
        symbol = renderer.symbol()
        self.assertTrue(renderer.usingSymbolLevels())
        self.assertEqual(symbol.symbolLayer(0).renderingPass(), 0)
        self.assertEqual(symbol.symbolLayer(1).renderingPass(), 1)
        self.assertEqual(symbol.symbolLayer(0).width(), 15.0)
        self.assertEqual(symbol.symbolLayer(1).width(), 0.45)
        for symbol_layer in (symbol.symbolLayer(0), symbol.symbolLayer(1)):
            self.assertEqual(
                symbol_layer.widthUnit(),
                Qgis.RenderUnit.MapUnits,
            )
            self.assertEqual(
                symbol_layer.penCapStyle(),
                QtCore.Qt.PenCapStyle.RoundCap,
            )
            self.assertEqual(
                symbol_layer.penJoinStyle(),
                QtCore.Qt.PenJoinStyle.RoundJoin,
            )
        self.assertEqual(layer.featureCount(), 2)

    def test_taxilane_uses_taxiway_style_with_five_map_unit_width(self):
        layer = QgsVectorLayer(
            "LineString?crs=EPSG:3857",
            "taxilane",
            "memory",
        )

        apply_aeroway_style(layer, "taxilane")

        renderer = layer.renderer()
        symbol = renderer.symbol()
        self.assertTrue(renderer.usingSymbolLevels())
        self.assertEqual(symbol.symbolLayerCount(), 2)
        self.assertEqual(symbol.symbolLayer(0).color().name(), "#7c858e")
        self.assertEqual(symbol.symbolLayer(0).width(), 5.0)
        self.assertEqual(symbol.symbolLayer(1).color().name(), "#f2c230")
        self.assertEqual(symbol.symbolLayer(1).width(), 0.45)
        for symbol_layer in (symbol.symbolLayer(0), symbol.symbolLayer(1)):
            self.assertEqual(symbol_layer.widthUnit(), Qgis.RenderUnit.MapUnits)
            self.assertEqual(
                symbol_layer.penCapStyle(),
                QtCore.Qt.PenCapStyle.RoundCap,
            )
            self.assertEqual(
                symbol_layer.penJoinStyle(),
                QtCore.Qt.PenJoinStyle.RoundJoin,
            )

    def test_dialog_uses_plain_airport_setup_labels(self):
        dialog = SafeguardingBuilderDialog()
        try:
            self.assertEqual(
                dialog.pushButton_DownloadOsmAeroway.text(),
                "Import airport map features",
            )
            self.assertEqual(dialog.groupBox_ARP.title(), "Aerodrome Reference Point")
            self.assertEqual(
                dialog.groupBox_AirportMap.title(),
                "Airport map",
            )
            self.assertEqual(
                dialog.groupBox_MET.title(),
                "Weather station (optional)",
            )
            self.assertEqual(
                dialog.groupBox_ILS_BRA.title(),
                "ILS Building Restricted Areas",
            )
            self.assertGreaterEqual(
                dialog.verticalLayout_cnsTab.indexOf(dialog.groupBox_ILS_BRA),
                0,
            )
            self.assertGreaterEqual(
                dialog.verticalLayout_cnsTab.indexOf(dialog.groupBox_MET),
                0,
            )
            self.assertEqual(
                dialog.verticalLayout_airportTab.indexOf(dialog.groupBox_MET),
                -1,
            )
            self.assertIs(
                dialog.pushButton_DownloadOsmAeroway.parentWidget(),
                dialog.groupBox_AirportMap,
            )
            airport_layout = dialog.verticalLayout_airportTab
            self.assertEqual(airport_layout.indexOf(dialog.groupBox_AirportMap), -1)
            self.assertGreaterEqual(
                dialog.verticalLayout_airportMapTab.indexOf(
                    dialog.groupBox_AirportMap
                ),
                0,
            )
            self.assertGreaterEqual(
                dialog.tabWidget_workflow.indexOf(dialog.tab_airport_map),
                0,
            )
            context = dialog.findChild(
                QtWidgets.QLabel,
                "label_workflow_summary_tab_airport",
            )
            self.assertEqual(
                context.text(),
                "01 Aerodrome Reference Data",
            )
            cns_context = dialog.findChild(
                QtWidgets.QLabel,
                "label_workflow_summary_tab_cns",
            )
            self.assertEqual(
                cns_context.text(),
                "05 CNS / Technical Facilities",
            )
            map_context = dialog.findChild(
                QtWidgets.QLabel,
                "label_workflow_summary_tab_airport_map",
            )
            self.assertEqual(
                map_context.text(),
                "09 Imported Airport Map",
            )
            self.assertTrue(
                all(
                    dialog.tabWidget_workflow.tabIcon(index).isNull()
                    for index in range(dialog.tabWidget_workflow.count())
                )
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
  <way id="13">
    <nd ref="5"/>
    <nd ref="6"/>
    <tag k="aeroway" v="parking_position"/>
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
                "Aprons",
                "Holding Positions",
                "Navigation Aids",
                "Parking Positions",
                "Stand Guidance Lines",
                "Taxiways",
            },
        )
        self.assertEqual(loaded, 6)
        self.assertEqual(project.crs().authid(), "EPSG:3857")
        for layer in project.mapLayers().values():
            self.assertEqual(layer.crs().authid(), "EPSG:3857")
            self.assertGreaterEqual(layer.fields().indexOf("aeroway"), 0)
            self.assertGreaterEqual(layer.featureCount(), 1)
        navigation_layer = next(
            layer
            for layer in project.mapLayers().values()
            if layer.name() == "Navigation Aids"
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
        expected_categories = {
            "Aprons": "apron",
            "Holding Positions": "holding_position",
            "Navigation Aids": "navigationaid",
            "Parking Positions": "parking_position",
            "Stand Guidance Lines": "parking_position",
            "Taxiways": "taxiway",
        }
        for name, layer in layers_by_name.items():
            self.assertEqual(
                layer.customProperty("safeguarding_builder/osm_aeroway_style"),
                expected_categories[name],
            )
        self.assertEqual(
            layers_by_name["Taxiways"].renderer().symbol().color().name(),
            "#7c858e",
        )
        self.assertAlmostEqual(
            layers_by_name["Taxiways"].renderer().symbol().width(),
            15.0,
        )
        taxiway_symbol = layers_by_name["Taxiways"].renderer().symbol()
        self.assertEqual(taxiway_symbol.symbolLayerCount(), 2)
        self.assertEqual(
            taxiway_symbol.symbolLayer(1).color().name(),
            "#f2c230",
        )
        self.assertAlmostEqual(
            taxiway_symbol.symbolLayer(1).width(),
            0.45,
        )
        navigation_renderer = layers_by_name["Navigation Aids"].renderer()
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
            layers_by_name["Navigation Aids"].hasScaleBasedVisibility()
        )
        self.assertEqual(
            layers_by_name["Navigation Aids"].minimumScale(),
            25_000,
        )
        self.assertTrue(
            layers_by_name["Parking Positions"].hasScaleBasedVisibility()
        )
        self.assertEqual(
            layers_by_name["Parking Positions"].minimumScale(),
            10_000,
        )
        self.assertEqual(
            layers_by_name["Aprons"].renderer().symbol().color().name(),
            "#c7cdd2",
        )
        self.assertAlmostEqual(
            layers_by_name["Aprons"].renderer().symbol().opacity(),
            0.68,
        )
        group = project.layerTreeRoot().findGroup("09 Imported Airport Map")
        self.assertIsNotNone(group)
        self.assertEqual(
            [child.name() for child in group.children()],
            [
                "Operational Aids",
                "Stands and Gates",
                "Movement Areas",
            ],
        )
        operational_group = group.findGroup("Operational Aids")
        stands_group = group.findGroup("Stands and Gates")
        movement_group = group.findGroup("Movement Areas")
        self.assertFalse(operational_group.isExpanded())
        self.assertFalse(stands_group.isExpanded())
        self.assertTrue(movement_group.isExpanded())
        self.assertEqual(
            [child.name() for child in operational_group.children()],
            ["Navigation Aids", "Holding Positions"],
        )
        self.assertEqual(
            [child.name() for child in stands_group.children()],
            ["Parking Positions", "Stand Guidance Lines"],
        )
        self.assertEqual(
            [child.name() for child in movement_group.children()],
            ["Taxiways", "Aprons"],
        )
        project.clear()


if __name__ == "__main__":
    unittest.main()
