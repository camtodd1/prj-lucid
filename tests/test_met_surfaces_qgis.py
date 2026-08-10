"""QGIS checks for MET source and derived-layer grouping."""

import unittest

from qgis.core import QgsGeometry, QgsLayerTreeGroup, QgsPointXY

from surfaces.met import MetSurfacesMixin


class _MetHarness(MetSurfacesMixin):
    def __init__(self):
        self.created_layers = []

    @staticmethod
    def tr(value):
        return value

    @staticmethod
    def _create_centered_oriented_square(center, side_length, _description):
        half_side = side_length / 2.0
        return QgsGeometry.fromPolygonXY(
            [[
                QgsPointXY(center.x() - half_side, center.y() - half_side),
                QgsPointXY(center.x() + half_side, center.y() - half_side),
                QgsPointXY(center.x() + half_side, center.y() + half_side),
                QgsPointXY(center.x() - half_side, center.y() + half_side),
                QgsPointXY(center.x() - half_side, center.y() - half_side),
            ]]
        )

    def _create_and_add_layer(
        self,
        geometry_type,
        _internal_name,
        display_name,
        _fields,
        _features,
        layer_group,
        _style_key,
    ):
        self.created_layers.append((geometry_type, display_name, layer_group))
        return object()


class MetSurfacesQgisTests(unittest.TestCase):
    def test_all_met_layers_use_the_technical_station_group(self):
        harness = _MetHarness()
        station_group = QgsLayerTreeGroup("Meteorological Instrument Station")

        generated, _ = harness.process_met_station_surfaces(
            QgsPointXY(500000, 6000000),
            "YTEST",
            None,
            station_group,
            station_group,
        )

        self.assertTrue(generated)
        groups_by_layer = {
            display_name: layer_group
            for _geometry_type, display_name, layer_group in harness.created_layers
        }
        self.assertTrue(all(group is station_group for group in groups_by_layer.values()))


if __name__ == "__main__":
    unittest.main()
