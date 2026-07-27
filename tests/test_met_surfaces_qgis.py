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
    def test_source_point_and_derived_met_layers_use_separate_groups(self):
        harness = _MetHarness()
        reference_group = QgsLayerTreeGroup("01 Reference Data")
        infrastructure_group = QgsLayerTreeGroup("Meteorological Instrument Station")

        generated, _ = harness.process_met_station_surfaces(
            QgsPointXY(500000, 6000000),
            "YTEST",
            None,
            reference_group,
            infrastructure_group,
        )

        self.assertTrue(generated)
        groups_by_layer = {
            display_name: layer_group
            for _geometry_type, display_name, layer_group in harness.created_layers
        }
        self.assertIs(groups_by_layer["MET Station Location"], reference_group)
        self.assertIs(groups_by_layer["MET Instrument Enclosure"], infrastructure_group)
        self.assertIs(groups_by_layer["MET Buffer Zone"], infrastructure_group)
        self.assertIs(groups_by_layer["MET Obstacle Buffer Zone"], infrastructure_group)


if __name__ == "__main__":
    unittest.main()
