import sys
import unittest
from pathlib import Path

from qgis.core import QgsLayerTreeGroup


WORKSPACE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORKSPACE.parent))

from safeguarding_builder.safeguarding_builder import SafeguardingBuilder


class OlsLayerGroupingTests(unittest.TestCase):
    def setUp(self):
        self.builder = object.__new__(SafeguardingBuilder)
        self.builder.translator = None

    @staticmethod
    def direct_group(parent, name):
        return next(
            (
                child
                for child in parent.children()
                if isinstance(child, QgsLayerTreeGroup) and child.name() == name
            ),
            None,
        )

    def test_ofz_runway_group_has_no_redundant_surface_wrapper(self):
        ofz_group = QgsLayerTreeGroup("Obstacle Free Zone")

        runway_group = self.builder._ols_runway_group(ofz_group, "01L")

        self.assertEqual(runway_group.name(), "RWY 01L")
        self.assertIs(runway_group.parent(), ofz_group)
        self.assertIsNone(self.direct_group(runway_group, "Obstacle Free Zone"))

    def test_legacy_nested_ofz_is_promoted_beside_primary_surfaces(self):
        primary_group = QgsLayerTreeGroup("Primary Surfaces")
        secondary_group = QgsLayerTreeGroup("Secondary Surfaces")
        ofz_group = QgsLayerTreeGroup("Obstacle Free Zone")
        primary_runway = primary_group.addGroup("RWY 01L")
        nested_ofz = primary_runway.addGroup("Obstacle Free Zone")
        nested_ofz.addGroup("OLS Inner Approach RWY 01L")

        self.builder._repair_guideline_f_layer_tree(
            primary_group,
            secondary_group,
            ofz_group,
        )

        promoted_runway = self.direct_group(ofz_group, "RWY 01L")
        self.assertIsNotNone(promoted_runway)
        self.assertIsNotNone(
            self.direct_group(promoted_runway, "OLS Inner Approach RWY 01L")
        )
        self.assertIsNone(self.direct_group(primary_runway, "Obstacle Free Zone"))


if __name__ == "__main__":
    unittest.main()
