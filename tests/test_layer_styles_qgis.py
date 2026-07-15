"""QGIS renderer checks for generated safeguarding layers."""

from __future__ import annotations

import unittest

from qgis.core import (
    QgsFeature,
    QgsFillSymbol,
    QgsGeometry,
    QgsPointXY,
    QgsRuleBasedRenderer,
    QgsVectorLayer,
)

from core.layers import LayerMixin


class LayerStyleTests(unittest.TestCase):
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

        LayerMixin()._prune_annex14_renderer_rules(layer)

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


if __name__ == "__main__":
    unittest.main()
