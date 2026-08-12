import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

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

    def test_primary_surface_layers_share_the_runway_group_without_wrappers(self):
        primary_group = QgsLayerTreeGroup("Primary Surfaces")

        approach_group = self.builder._ols_runway_surface_group(
            primary_group,
            "01L",
            "Approach",
        )
        takeoff_group = self.builder._ols_runway_surface_group(
            primary_group,
            "01L",
            "Take-off Climb",
        )

        self.assertIs(approach_group, takeoff_group)
        self.assertEqual(approach_group.name(), "RWY 01L")
        self.assertIsNone(self.direct_group(approach_group, "Approach"))
        self.assertIsNone(self.direct_group(approach_group, "Take-off Climb"))

    def test_airport_wide_ols_uses_an_empty_secondary_group(self):
        primary_group = QgsLayerTreeGroup("Primary Surfaces")
        secondary_group = QgsLayerTreeGroup("Secondary Surfaces")
        context = SimpleNamespace(generation_runways=lambda: [{}])
        policy = SimpleNamespace(
            airport_wide_spec=lambda _ruleset, _context: {
                "ihs_elevation_amsl": 50.0,
                "datum_elevation_m": 5.0,
            }
        )
        ruleset = SimpleNamespace(
            protected_airspace_model="ols_current",
            ols_construction_policy=lambda: policy,
        )
        captured = {}
        self.builder.get_active_protected_airspace_ruleset = lambda: ruleset
        self.builder.ols_construction_context = context
        self.builder.reference_elevation_datum = 5.0
        self.builder._generate_airport_wide_ols = (
            lambda _runways, group, _datum, _icao, _runway_group: captured.setdefault(
                "group", group
            ) is group
        )

        created = self.builder._process_airport_wide_ols_if_possible(
            {"F": primary_group},
            [{}],
            "TEST",
            False,
            secondary_group,
        )

        self.assertTrue(created)
        self.assertIs(captured["group"], secondary_group)

    def test_surface_layer_names_use_one_shared_schema(self):
        self.assertEqual(
            self.builder._surface_layer_display_name(
                "Inner Transitional",
                "Surface",
                "19R",
            ),
            "Inner Transitional 19R - Surface",
        )
        self.assertEqual(
            self.builder._surface_layer_display_name(
                "Take-off Climb",
                "Contours",
                "01L",
            ),
            "Take-off Climb 01L - Contours",
        )

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
            "Baseline OLS — MOS139 (C.07 2026)",
        )
        comparison = self.direct_group(
            protected_airspace,
            "Comparison OLS — ICAO Annex 14 Vol I - Modernised OLS",
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

    def test_top_level_sections_include_promoted_cns_group_in_numbered_order(self):
        self.builder.framework = get_framework_profile()
        self.builder.baseline_ols_ruleset = get_ruleset_profile("mos139_2019")
        self.builder.protected_airspace_ruleset = self.builder.baseline_ols_ruleset
        self.builder.comparison_ols_ruleset = None
        main_group = QgsLayerTreeGroup("TEST")

        groups = self.builder._create_output_layer_groups(main_group, agl_enabled=False)

        self.assertEqual(
            [child.name() for child in main_group.children()],
            [
                "01 Aerodrome Reference Data",
                "02 Runway Infrastructure",
                "03 Runway Protection and Safeguarding",
                "04 Obstacle Limitation Surfaces",
                "05 CNS / Technical Facilities",
                "07 External Safeguarding",
            ],
        )
        self.assertIs(
            groups["cns_technical_safeguarding"],
            self.direct_group(main_group, "05 CNS / Technical Facilities"),
        )

    def test_agl_is_a_top_level_group_before_external_safeguarding(self):
        self.builder.framework = get_framework_profile()
        self.builder.baseline_ols_ruleset = get_ruleset_profile("mos139_2019")
        self.builder.protected_airspace_ruleset = self.builder.baseline_ols_ruleset
        self.builder.comparison_ols_ruleset = None
        main_group = QgsLayerTreeGroup("TEST")

        groups = self.builder._create_output_layer_groups(main_group, agl_enabled=True)

        self.assertEqual(
            [child.name() for child in main_group.children()][5:],
            ["06 Airfield Ground Lighting", "07 External Safeguarding"],
        )
        self.assertIs(groups["airfield_ground_lighting"].parent(), main_group)

    def test_generated_layer_groups_are_collapsed_and_unchecked_recursively(self):
        main_group = QgsLayerTreeGroup("TEST")
        cns_group = main_group.addGroup("05 CNS / Technical Facilities")
        cns_group.addGroup("Radio Link")
        for group in (main_group, cns_group):
            group.setExpanded(True)
            group.setItemVisibilityChecked(True)

        self.builder._collapse_layer_tree_groups(main_group)

        groups = [
            main_group,
            cns_group,
            self.direct_group(cns_group, "Radio Link"),
        ]
        self.assertTrue(all(not group.isExpanded() for group in groups))
        self.assertTrue(all(not group.itemVisibilityChecked() for group in groups))


if __name__ == "__main__":
    unittest.main()
