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


if __name__ == "__main__":
    unittest.main()
