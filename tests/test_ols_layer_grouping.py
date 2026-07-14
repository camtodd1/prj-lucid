import sys
import unittest
from pathlib import Path

from qgis.core import QgsLayerTreeGroup


WORKSPACE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORKSPACE.parent))

from safeguarding_builder.safeguarding_builder import SafeguardingBuilder
from safeguarding_builder.frameworks.registry import get_framework_profile
from safeguarding_builder.rulesets.registry import get_ruleset_profile


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

    def test_baseline_and_comparison_rulesets_are_parallel_first_order_groups(self):
        self.builder.framework = get_framework_profile()
        self.builder.baseline_ols_ruleset = get_ruleset_profile("mos139_2019")
        self.builder.protected_airspace_ruleset = self.builder.baseline_ols_ruleset
        self.builder.comparison_ols_ruleset = get_ruleset_profile(
            "icao_annex14_vol1_modernised_ofs_oes"
        )
        main_group = QgsLayerTreeGroup("TEST")

        groups = self.builder._create_output_layer_groups(main_group, agl_enabled=False)

        protected_airspace = groups["protected_airspace"]
        baseline = self.direct_group(
            protected_airspace,
            "Baseline OLS — MOS139 (current)",
        )
        comparison = self.direct_group(
            protected_airspace,
            "Comparison OLS — Annex 14 Modernised OLS",
        )
        self.assertIsNotNone(baseline)
        self.assertIsNotNone(comparison)
        self.assertIs(groups["baseline_ols"], baseline)
        self.assertIs(groups["obstacle_free_zone"].parent(), baseline)
        self.assertIs(groups["ols_surfaces"].parent(), baseline)
        self.assertIs(groups["airport_wide_ols"].parent(), baseline)
        self.assertIs(groups["controlling_surfaces"].parent(), baseline)
        self.assertIs(groups["comparison_ols_surfaces"].parent(), comparison)
        self.assertIs(groups["comparison_airport_wide_ols"].parent(), comparison)


if __name__ == "__main__":
    unittest.main()
