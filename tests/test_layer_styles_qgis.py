"""QGIS renderer checks for generated safeguarding layers."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from qgis.PyQt.QtCore import QVariant
from qgis.core import (
    QgsCoordinateReferenceSystem,
    QgsFeature,
    QgsField,
    QgsFields,
    QgsFillSymbol,
    QgsGeometry,
    QgsPointXY,
    QgsProject,
    QgsRectangle,
    QgsRenderContext,
    QgsRuleBasedRenderer,
    QgsVectorLayer,
)

from core.layers import LayerMixin
from core.styles import DEFAULT_STYLE_MAP


class _FileLayerHarness(LayerMixin):
    def __init__(self, output_path):
        self.output_mode = "file"
        self.output_path = output_path
        self.output_format_driver = "ESRI Shapefile"
        self.output_format_extension = ".shp"
        self.plugin_dir = str(Path(__file__).resolve().parents[1])
        self.style_map = dict(DEFAULT_STYLE_MAP)
        self.successfully_generated_layers = []


class LayerStyleTests(unittest.TestCase):
    def tearDown(self):
        QgsProject.instance().clear()

    @staticmethod
    def _surface_layer(surface_values):
        layer = QgsVectorLayer("Polygon?field=surface:string", "Controlling OES — Surface", "memory")
        for index, surface in enumerate(surface_values):
            feature = QgsFeature(layer.fields())
            feature.setAttribute("surface", surface)
            feature.setGeometry(
                QgsGeometry.fromPolygonXY(
                    [[
                        QgsPointXY(index, 0.0),
                        QgsPointXY(index + 0.8, 0.0),
                        QgsPointXY(index + 0.8, 0.8),
                        QgsPointXY(index, 0.0),
                    ]]
                )
            )
            layer.dataProvider().addFeature(feature)
        return layer

    @staticmethod
    def _set_surface_renderer(layer):
        root = QgsRuleBasedRenderer.Rule(None)
        for surface in (
            "Precision Approach",
            "Instrument Departure",
            "Take-off Climb",
            "Horizontal",
        ):
            symbol = QgsFillSymbol.createSimple({"color": "100,150,200,100"})
            rule = QgsRuleBasedRenderer.Rule(symbol)
            rule.setLabel(surface)
            normalized = surface.lower().replace("-", "_").replace(" ", "_")
            rule.setFilterExpression(
                "replace(replace(lower(\"surface\"), ' ', '_'), '-', '_') "
                f"= '{normalized}'"
            )
            root.appendChild(rule)
        layer.setRenderer(QgsRuleBasedRenderer(root))

    def test_annex_renderer_keeps_only_rules_with_features(self):
        layer = self._surface_layer(["Take-off Climb", "Horizontal"])
        self._set_surface_renderer(layer)
        renderer_before_pruning = layer.renderer()

        LayerMixin()._prune_annex14_renderer_rules(layer)

        self.assertIsNot(layer.renderer(), renderer_before_pruning)
        self.assertEqual(layer.renderer().type(), "RuleRenderer")
        self.assertEqual(
            [rule.label() for rule in layer.renderer().rootRule().children()],
            ["Take-off Climb", "Horizontal"],
        )

    def test_single_represented_surface_remains_a_toggleable_rule(self):
        layer = self._surface_layer(["Take-off Climb"])
        self._set_surface_renderer(layer)

        LayerMixin()._prune_annex14_renderer_rules(layer)

        self.assertEqual(layer.renderer().type(), "RuleRenderer")
        self.assertEqual(
            [rule.label() for rule in layer.renderer().rootRule().children()],
            ["Take-off Climb"],
        )

    def test_individual_single_surface_layer_stays_single_symbol(self):
        layer = self._surface_layer(["Take-off Climb"])
        layer.setName("RWY 01L — Take-off Climb")
        self._set_surface_renderer(layer)

        LayerMixin()._prune_annex14_renderer_rules(layer)

        self.assertEqual(layer.renderer().type(), "singleSymbol")

    def test_nasf_styles_are_distinct_legible_and_labeled(self):
        style_cases = {
            "WSZ Runway": ("rwy_name:string&field=end_desig:string", "WSZ"),
            "PSA Runway": ("rwy:string&field=end_desig:string", "PSA"),
            "WMZ A": (
                "zone:string&field=inner_rad_km:double&field=outer_rad_km:double",
                "inner_rad_km",
            ),
            "WMZ B": (
                "zone:string&field=inner_rad_km:double&field=outer_rad_km:double",
                "inner_rad_km",
            ),
            "WMZ C": (
                "zone:string&field=inner_rad_km:double&field=outer_rad_km:double",
                "inner_rad_km",
            ),
            "Wind Turbine Assessment Zone": (
                "icao_code:string&field=radius_km:double",
                "Wind turbine assessment",
            ),
            "LCZ A": ("rwy:string&field=zone:string&field=max_intensity:string", "LCZ"),
            "LCZ B": ("rwy:string&field=zone:string&field=max_intensity:string", "LCZ"),
            "LCZ C": ("rwy:string&field=zone:string&field=max_intensity:string", "LCZ"),
            "LCZ D": ("rwy:string&field=zone:string&field=max_intensity:string", "LCZ"),
            "LCZ Area": ("rwy:string&field=radius_m:double", "Lighting Control Area"),
            "CNS Circle Zone": (
                "sourcefacid:string&field=surfname:string&field=reqheight:double",
                "surfname",
            ),
            "CNS Donut Zone": (
                "sourcefacid:string&field=surfname:string&field=reqheight:double",
                "surfname",
            ),
            "Default CNS": (
                "sourcefacid:string&field=surfname:string&field=reqheight:double",
                "surfname",
            ),
        }
        styles_dir = Path(__file__).resolve().parents[1] / "styles"
        outline_colors = set()

        for style_key, (fields, label_fragment) in style_cases.items():
            with self.subTest(style_key=style_key):
                style_path = styles_dir / DEFAULT_STYLE_MAP[style_key]
                self.assertTrue(style_path.is_file())
                layer = QgsVectorLayer(f"Polygon?field={fields}", style_key, "memory")
                message, loaded = layer.loadNamedStyle(str(style_path))
                self.assertTrue(loaded, message)
                self.assertTrue(layer.labelsEnabled())
                settings = layer.labeling().settings()
                self.assertIn(label_fragment, settings.fieldName)
                self.assertTrue(settings.isExpression)
                self.assertTrue(settings.scaleVisibility)
                self.assertEqual(settings.maximumScale, 1)
                self.assertGreater(settings.minimumScale, settings.maximumScale)
                self.assertEqual(settings.geometryGenerator, "point_on_surface($geometry)")

                symbol_layer = layer.renderer().symbol().symbolLayer(0)
                self.assertLess(symbol_layer.fillColor().alpha(), 80)
                self.assertEqual(symbol_layer.strokeColor().alpha(), 255)
                self.assertGreaterEqual(symbol_layer.strokeWidth(), 0.5)
                outline_colors.add(symbol_layer.strokeColor().name())

        # Families are intentionally coordinated, but not collapsed to one generic red style.
        self.assertGreaterEqual(len(outline_colors), 10)

    def test_modernisation_change_contour_style_renders_and_labels_zero_contour(self):
        layer = QgsVectorLayer(
            "MultiLineString?field=change:string&field=contour_class:string&field=label_txt:string",
            "Change Contours",
            "memory",
        )
        feature = QgsFeature(layer.fields())
        feature.setAttributes(["transition", "primary", "0.0 m"])
        feature.setGeometry(QgsGeometry.fromMultiPolylineXY([[
            QgsPointXY(0.0, 0.0),
            QgsPointXY(100.0, 0.0),
        ]]))
        layer.dataProvider().addFeature(feature)

        LayerMixin()._apply_modernisation_change_contour_style(layer)

        self.assertTrue(layer.labelsEnabled())
        renderer = layer.renderer()
        zero_rule = next(
            rule
            for rule in renderer.rootRule().children()
            if rule.label() == "0.0 m / equal height"
        )
        self.assertEqual(zero_rule.symbol().color().getRgb(), (76, 84, 88, 235))
        render_context = QgsRenderContext()
        renderer.startRender(render_context, layer.fields())
        try:
            self.assertTrue(renderer.symbolsForFeature(feature, render_context))
        finally:
            renderer.stopRender(render_context)
        labeling = layer.labeling()
        self.assertIsNotNone(labeling)
        label_rules = labeling.rootRule().children()
        self.assertEqual(len(label_rules), 1)
        self.assertEqual(label_rules[0].settings().fieldName, "label_txt")

    def test_modernisation_no_change_style_is_muted_blue_and_subdued(self):
        layer = QgsVectorLayer(
            "Polygon?field=label_txt:string",
            "No Change",
            "memory",
        )
        feature = QgsFeature(layer.fields())
        feature.setAttribute("label_txt", "0.0 m no change")
        feature.setGeometry(
            QgsGeometry.fromRect(QgsRectangle(0.0, 0.0, 100.0, 100.0))
        )
        layer.dataProvider().addFeature(feature)

        LayerMixin()._apply_modernisation_comparison_style(
            layer,
            "OLS Modernisation No Change",
        )

        self.assertEqual(layer.renderer().symbol().color().getRgb(), (91, 143, 174, 68))
        self.assertTrue(layer.labelsEnabled())
        label_rule = layer.labeling().rootRule().children()[0]
        self.assertEqual(
            label_rule.settings().format().color().getRgb(),
            (43, 86, 112, 255),
        )

    def test_modernisation_no_overlay_style_is_neutral_and_distinct(self):
        layer = QgsVectorLayer(
            "Polygon?field=label_txt:string",
            "No Comparison Overlay",
            "memory",
        )
        feature = QgsFeature(layer.fields())
        feature.setAttribute("label_txt", "No comparison overlay")
        feature.setGeometry(
            QgsGeometry.fromRect(QgsRectangle(0.0, 0.0, 100.0, 100.0))
        )
        layer.dataProvider().addFeature(feature)

        LayerMixin()._apply_modernisation_comparison_style(
            layer,
            "OLS Modernisation No Future Overlay",
        )

        self.assertEqual(layer.renderer().symbol().color().getRgb(), (112, 118, 121, 42))
        self.assertTrue(layer.labelsEnabled())
        label_rule = layer.labeling().rootRule().children()[0]
        self.assertEqual(
            label_rule.settings().format().color().getRgb(),
            (68, 74, 78, 255),
        )

    def test_file_layers_with_same_display_name_use_unique_internal_paths(self):
        fields = QgsFields()
        fields.append(QgsField("change", QVariant.String))
        fields.append(QgsField("contour_class", QVariant.String))
        fields.append(QgsField("label_txt", QVariant.String))

        def contour_feature(x_offset):
            feature = QgsFeature(fields)
            feature.setAttributes(["gain", "primary", "+5 m"])
            feature.setGeometry(QgsGeometry.fromMultiPolylineXY([[
                QgsPointXY(x_offset, 0),
                QgsPointXY(x_offset + 1, 1),
            ]]))
            return feature

        with tempfile.TemporaryDirectory() as output_path:
            project = QgsProject.instance()
            project.setCrs(QgsCoordinateReferenceSystem("EPSG:3857"))
            group = project.layerTreeRoot().addGroup("Comparison")
            harness = _FileLayerHarness(output_path)

            ofs_layer = harness._create_and_add_layer(
                "MultiLineString",
                "OLS_Modernisation_OFS_change_contours_TEST",
                "Change Contours",
                fields,
                [contour_feature(0)],
                group,
                "OLS Modernisation Change Contour",
            )
            oes_layer = harness._create_and_add_layer(
                "MultiLineString",
                "OLS_Modernisation_OES_change_contours_TEST",
                "Change Contours",
                fields,
                [contour_feature(2)],
                group,
                "OLS Modernisation Change Contour",
            )

            self.assertIsNotNone(ofs_layer)
            self.assertIsNotNone(oes_layer)
            self.assertTrue(
                Path(output_path, "OLS_Modernisation_OFS_change_contours_TEST.shp").is_file()
            )
            self.assertTrue(
                Path(output_path, "OLS_Modernisation_OES_change_contours_TEST.shp").is_file()
            )
            self.assertNotEqual(ofs_layer.source(), oes_layer.source())
            self.assertEqual(ofs_layer.renderer().type(), "RuleRenderer")
            self.assertEqual(oes_layer.renderer().type(), "RuleRenderer")
            ofs_feature = next(ofs_layer.getFeatures())
            oes_feature = next(oes_layer.getFeatures())
            for persisted_layer, feature in (
                (ofs_layer, ofs_feature),
                (oes_layer, oes_feature),
            ):
                renderer = persisted_layer.renderer()
                render_context = QgsRenderContext()
                renderer.startRender(render_context, persisted_layer.fields())
                try:
                    self.assertTrue(renderer.symbolsForFeature(feature, render_context))
                finally:
                    renderer.stopRender(render_context)
            self.assertEqual(len(group.findLayers()), 2)

    def test_baseline_and_comparison_layers_namespace_reused_internal_names(self):
        fields = QgsFields()
        fields.append(QgsField("ruleset", QVariant.String))

        def ruleset_feature(name, y_offset):
            feature = QgsFeature(fields)
            feature.setAttribute("ruleset", name)
            feature.setGeometry(QgsGeometry.fromMultiPolylineXY([[
                QgsPointXY(0, y_offset),
                QgsPointXY(10, y_offset),
            ]]))
            return feature

        with tempfile.TemporaryDirectory() as output_path:
            project = QgsProject.instance()
            project.setCrs(QgsCoordinateReferenceSystem("EPSG:3857"))
            baseline_group = project.layerTreeRoot().addGroup("Baseline OLS")
            comparison_group = project.layerTreeRoot().addGroup("Comparison OLS")
            harness = _FileLayerHarness(output_path)

            harness._contour_interval_ruleset_role = "baseline"
            baseline_layer = harness._create_and_add_layer(
                "MultiLineString",
                "OLS_Conical_TEST",
                "Conical Contours",
                fields,
                [ruleset_feature("MOS139", 0)],
                baseline_group,
                "Default Line",
            )
            harness._contour_interval_ruleset_role = "comparison"
            comparison_layer = harness._create_and_add_layer(
                "MultiLineString",
                "OLS_Conical_TEST",
                "Conical Contours",
                fields,
                [ruleset_feature("CAP168", 10)],
                comparison_group,
                "Default Line",
            )

            self.assertIsNotNone(baseline_layer)
            self.assertIsNotNone(comparison_layer)
            self.assertTrue(Path(output_path, "OLS_Conical_TEST.shp").is_file())
            self.assertTrue(Path(output_path, "Comparison_OLS_Conical_TEST.shp").is_file())
            self.assertNotEqual(baseline_layer.source(), comparison_layer.source())
            self.assertEqual(
                next(baseline_layer.getFeatures()).attribute("ruleset"),
                "MOS139",
            )
            self.assertEqual(
                next(comparison_layer.getFeatures()).attribute("ruleset"),
                "CAP168",
            )


if __name__ == "__main__":
    unittest.main()
