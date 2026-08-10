import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from qgis.PyQt import QtCore, QtWidgets


WORKSPACE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORKSPACE.parent))

from safeguarding_builder.safeguarding_builder_dialog import SafeguardingBuilderDialog
from safeguarding_builder.safeguarding_builder import SafeguardingBuilder
from safeguarding_builder.dialog.dialog_constants import CONTOUR_INTERVAL_KEYS


class OlsDialogWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def setUp(self):
        self.dialog = SafeguardingBuilderDialog()

    def tearDown(self):
        self.dialog.close()
        self.dialog.deleteLater()

    def select_mode(self, mode):
        baseline_id = "mos139_2019"
        comparison_id = ""
        if mode == "future_annex14_ofs_oes":
            baseline_id = "icao_annex14_vol1_modernised_ofs_oes"
        elif mode == "modernisation_comparison":
            comparison_id = "icao_annex14_vol1_modernised_ofs_oes"
        self.dialog._set_ols_ruleset_selection(baseline_id, comparison_id)
        self.dialog._update_ols_workflow_ui(
            dependency_status={"state": "ready", "summary": "OLS ready."},
            runway_count=2,
        )

    def test_two_column_ruleset_selectors_are_presented_on_ols_tab(self):
        baseline = self.dialog.baseline_ols_ruleset_combo
        comparison = self.dialog.comparison_ols_ruleset_combo

        self.assertIs(baseline.parentWidget(), self.dialog.groupBox_olsWorkflow)
        self.assertIs(comparison.parentWidget(), self.dialog.groupBox_olsWorkflow)
        self.assertTrue(self.dialog.label_protected_airspace_policy.isHidden())
        self.assertTrue(self.dialog.protected_airspace_policy_combo.isHidden())
        self.assertEqual(self.dialog.groupBox_olsWorkflow.title(), "OLS rulesets")
        self.assertEqual(
            self.dialog.label_baselineOlsRuleset.text(),
            "Baseline (design standard pairing)",
        )
        self.assertEqual(self.dialog.label_comparisonOlsRuleset.text(), "Comparison")
        self.assertIsNone(
            self.dialog.findChild(QtWidgets.QLabel, "label_olsModeDescription")
        )
        context = self.dialog.findChild(
            QtWidgets.QFrame,
            "frame_workflow_context_tab_ols",
        )
        self.assertIsNotNone(context)
        self.assertEqual(
            self.dialog.findChild(
                QtWidgets.QLabel,
                "label_workflow_summary_tab_ols",
            ).text(),
            "Choose which protected-airspace layers to create.",
        )
        self.assertIsNone(
            self.dialog.findChild(QtWidgets.QLabel, "label_olsInlineStatus")
        )
        self.assertEqual(baseline.currentData(), "mos139_2019")
        self.assertEqual(comparison.itemData(0), "")
        self.assertEqual(comparison.itemText(0), "None — baseline only")
        modernised_index = comparison.findData(
            "icao_annex14_vol1_modernised_ofs_oes"
        )
        self.assertEqual(
            comparison.itemText(modernised_index),
            "ICAO Annex 14 Vol I - Modernised OLS",
        )
        self.assertIsNone(
            self.dialog.findChild(
                QtWidgets.QCheckBox,
                "checkBox_generateControllingOls",
            )
        )
        self.assertIsNone(
            self.dialog.findChild(
                QtWidgets.QGroupBox,
                "groupBox_controllingOls",
            )
        )

    def test_output_family_tabs_expose_scoped_generation_actions(self):
        emitted = []
        self.dialog.familyGenerationRequested.connect(emitted.append)

        for family in (
            "airport",
            "runways",
            "cns",
            "ols",
            "lighting",
            "external",
        ):
            button = self.dialog.findChild(
                QtWidgets.QPushButton,
                f"pushButton_generate_{family}_family",
            )
            self.assertIsNotNone(button)
            self.assertEqual(button.text(), "Generate / update")

        self.dialog.findChild(
            QtWidgets.QPushButton,
            "pushButton_generate_lighting_family",
        ).click()
        self.assertEqual(emitted, ["lighting"])
        self.assertEqual(self.dialog.pushButton_Generate.text(), "Generate all layers")
        self.assertIsNone(
            self.dialog.findChild(
                QtWidgets.QPushButton,
                "pushButton_generate_runway_protection_family",
            )
        )

    def test_workflow_tabs_place_ols_before_cns(self):
        tabs = self.dialog.tabWidget_workflow

        self.assertEqual(
            [tabs.tabText(index) for index in range(tabs.count())],
            [
                "Aerodrome",
                "RWY Infra",
                "RWY Protect",
                "OLS",
                "CNS/MET",
                "AGL",
                "External",
                "Terrain",
                "Map",
                "Output",
            ],
        )
        tab_bar = tabs.tabBar()
        self.assertFalse(tab_bar.usesScrollButtons())
        self.assertFalse(tab_bar.expanding())
        self.dialog.resize(800, 760)
        self.dialog.show()
        self.app.processEvents()
        tab_widths = [tab_bar.tabRect(index).width() for index in range(tabs.count())]
        self.assertEqual(len(set(tab_widths)), 1)
        self.assertLessEqual(tab_bar.tabRect(tabs.count() - 1).right(), tab_bar.width())
        self.assertTrue(tabs.tabToolTip(1).startswith("Runway Infrastructure"))
        self.assertTrue(tabs.tabToolTip(2).startswith("Runway Protection"))

    def test_airport_family_validation_does_not_require_runway_inputs(self):
        self.dialog.lineEdit_airport_name.setText("YTST")

        result = self.dialog.get_all_input_data("airport")

        self.assertIsNotNone(result)
        self.assertEqual(result["icao_code"], "YTST")
        self.assertEqual(result["runways"], [])

    def test_baseline_follows_design_standard_and_shows_pairing_label(self):
        design = self.dialog.ruleset_combo
        cap168_index = design.findData("uk_caa_cap168_edition_13")
        self.assertGreaterEqual(cap168_index, 0)

        design.setCurrentIndex(cap168_index)

        self.assertEqual(
            self.dialog.baseline_ols_ruleset_combo.currentData(),
            "uk_caa_cap168_edition_13",
        )
        self.assertEqual(
            self.dialog.label_baselineOlsRuleset.text(),
            "Baseline (design standard pairing)",
        )

    def test_design_standard_excludes_modernised_ols_profile(self):
        design_standard = self.dialog.ruleset_combo

        self.assertEqual(
            design_standard.findData("icao_annex14_vol1_modernised_ofs_oes"),
            -1,
        )
        current_annex_index = design_standard.findData(
            "icao_annex14_vol1_current_ols"
        )
        self.assertGreaterEqual(current_annex_index, 0)
        self.assertEqual(
            design_standard.itemText(current_annex_index),
            "ICAO Annex 14 Vol I (9th Edition, Amendment 18)",
        )

        self.assertGreaterEqual(
            self.dialog.baseline_ols_ruleset_combo.findData(
                "icao_annex14_vol1_modernised_ofs_oes"
            ),
            0,
        )

    def test_agl_dialog_reflects_selected_design_ruleset(self):
        design_standard = self.dialog.ruleset_combo
        easa_index = design_standard.findData("easa_cs_adr_dsn_issue_7")
        mos_index = design_standard.findData("mos139_2019")
        cap168_index = design_standard.findData("uk_caa_cap168_edition_13")

        self.assertGreaterEqual(easa_index, 0)
        self.assertGreaterEqual(mos_index, 0)
        self.assertGreaterEqual(cap168_index, 0)

        self.dialog.checkBox_agl_enabled.setChecked(True)
        design_standard.setCurrentIndex(easa_index)
        self.assertEqual(
            self.dialog.label_agl_edge_spacing.text(),
            "EASA instrument runway edge spacing (m)",
        )

        design_standard.setCurrentIndex(mos_index)
        self.assertEqual(
            self.dialog.label_agl_edge_spacing.text(),
            "MOS edge spacing baseline (m)",
        )

        design_standard.setCurrentIndex(cap168_index)
        self.assertEqual(
            self.dialog.label_agl_edge_spacing.text(),
            "CAP 168 runway edge spacing baseline (m)",
        )

    def test_agl_controls_are_grouped_by_generated_light_type_layer(self):
        expected_groups = {
            "groupBox_agl_layer_runway_edge": [self.dialog.lineEdit_agl_edge_spacing],
            "groupBox_agl_layer_threshold": [
                self.dialog.lineEdit_agl_threshold_spacing,
                self.dialog.lineEdit_agl_threshold_inset,
            ],
        }
        for group_name, controls in expected_groups.items():
            group = getattr(self.dialog, group_name)
            for control in controls:
                self.assertTrue(group.isAncestorOf(control), (group_name, control.objectName()))
        self.dialog.resize(800, 760)
        self.dialog.tabWidget_workflow.setCurrentWidget(self.dialog.tab_lighting)
        self.dialog.show()
        self.app.processEvents()
        self.assertFalse(
            self.dialog.scrollArea_agl_options.horizontalScrollBar().isVisible()
        )

    def test_policy_driven_agl_elements_have_no_manual_controls(self):
        removed_option_keys = {
            "runway_end_lights",
            "temp_displaced_threshold",
            "stopway_lights",
            "tdz_lights",
            "threshold_wing_bars",
            "rtil",
            "centreline_lights",
            "centreline_low_visibility",
            "cat_i_centreline_lights",
            "centreline_offset_m",
            "cat_i_tdz_lights",
            "approach_spacing_m",
            "approach_lighting",
        }
        for object_name in (
            "checkBox_agl_runway_end_lights",
            "checkBox_agl_temp_displaced_threshold",
            "checkBox_agl_stopway_lights",
            "checkBox_agl_tdz_lights",
            "checkBox_agl_threshold_wing_bars",
            "checkBox_agl_rtil",
            "checkBox_agl_centreline_lights",
            "checkBox_agl_centreline_low_visibility",
            "checkBox_agl_cat_i_centreline_lights",
            "lineEdit_agl_centreline_offset",
            "checkBox_agl_cat_i_tdz_lights",
            "label_agl_ruleset_caveat",
            "groupBox_agl_approach",
            "lineEdit_agl_approach_spacing",
            "table_agl_approach",
            "pushButton_add_agl_approach",
            "pushButton_remove_agl_approach",
        ):
            self.assertIsNone(self.dialog.findChild(QtWidgets.QWidget, object_name))
        self.assertTrue(
            removed_option_keys.isdisjoint(self.dialog._get_agl_save_options())
        )

    def test_legacy_modernised_design_standard_loads_as_current_annex(self):
        self.dialog._apply_loaded_payload(
            {
                "icao_code": "TEST",
                "design_standard": "icao_annex14_vol1_modernised_ofs_oes",
                "runways": [],
            }
        )

        self.assertEqual(
            self.dialog.ruleset_combo.currentData(),
            "icao_annex14_vol1_current_ols",
        )
        self.assertEqual(
            self.dialog.baseline_ols_ruleset_combo.currentData(),
            "icao_annex14_vol1_modernised_ofs_oes",
        )

    def test_cap168_and_current_annex14_are_supported_while_easa_is_preview(self):
        baseline = self.dialog.baseline_ols_ruleset_combo
        cap168_index = baseline.findData("uk_caa_cap168_edition_13")
        easa_index = baseline.findData("easa_cs_adr_dsn_issue_7")
        current_annex_index = baseline.findData("icao_annex14_vol1_current_ols")

        self.assertGreaterEqual(cap168_index, 0)
        self.assertTrue(baseline.model().item(cap168_index).isEnabled())
        self.assertTrue(baseline.model().item(easa_index).isEnabled())
        self.assertNotIn("partial preview", baseline.itemText(cap168_index).lower())
        self.assertEqual(baseline.itemText(cap168_index), "UK CAA CAP 168 (Edition 13)")
        self.assertIn("partial preview", baseline.itemText(easa_index).lower())
        self.assertEqual(
            baseline.itemText(current_annex_index),
            "ICAO Annex 14 Vol I - Current OLS",
        )
        self.assertTrue(baseline.model().item(current_annex_index).isEnabled())

    def test_nominated_ols_track_options_round_trip_with_runway_data(self):
        group = self.dialog._runway_groups[1]
        saved = group.get_input_data()
        saved.update(
            {
                "approach_track_type_1": "curved_gt_15",
                "approach_track_wkt_1": "LINESTRING (0 0, 100 10, 200 40)",
                "takeoff_track_type_2": "offset",
                "takeoff_track_wkt_2": "LINESTRING (1000 0, 2000 100)",
                "cap168_wide_runway": True,
            }
        )

        group.set_input_data(saved)
        restored = group.get_input_data()

        self.assertEqual(restored["approach_track_type_1"], "curved_gt_15")
        self.assertEqual(restored["approach_track_wkt_1"], saved["approach_track_wkt_1"])
        self.assertEqual(restored["takeoff_track_type_2"], "offset")
        self.assertEqual(restored["takeoff_track_wkt_2"], saved["takeoff_track_wkt_2"])
        self.assertTrue(restored["cap168_wide_runway"])

    def test_explicit_selection_keeps_legacy_policy_compatible(self):
        self.select_mode("modernisation_comparison")

        self.assertEqual(
            self.dialog.protected_airspace_policy_combo.currentData(),
            "modernisation_comparison",
        )
        self.assertEqual(
            self.dialog._current_ols_ruleset_ids(),
            ("mos139_2019", "icao_annex14_vol1_modernised_ofs_oes"),
        )

    def test_annex_baseline_can_select_mos_as_the_comparison(self):
        self.dialog._set_ols_ruleset_selection(
            "icao_annex14_vol1_modernised_ofs_oes",
            "mos139_2019",
        )

        self.assertEqual(
            self.dialog._current_ols_ruleset_ids(),
            ("icao_annex14_vol1_modernised_ofs_oes", "mos139_2019"),
        )
        self.assertEqual(
            self.dialog.protected_airspace_policy_combo.currentData(),
            "ruleset_comparison",
        )
        self.dialog.toolButtonContourOverrides.setChecked(True)
        self.assertFalse(
            self.dialog._contour_interval_labels["annex14_ofs_approach"].isHidden()
        )
        self.assertFalse(
            self.dialog._contour_interval_labels["comparison_approach"].isHidden()
        )
        self.assertTrue(self.dialog._contour_interval_labels["approach"].isHidden())
        self.assertTrue(
            self.dialog._contour_interval_labels[
                "comparison_annex14_ofs_approach"
            ].isHidden()
        )

    def test_reverse_annex_comparison_still_checks_conventional_red_inputs(self):
        self.dialog._set_ols_ruleset_selection(
            "icao_annex14_vol1_modernised_ofs_oes",
            "mos139_2019",
        )

        status = self.dialog._ols_dependency_status(
            airport_status={
                "identity_ready": True,
                "arp_pair_ready": True,
                "arp_elev_ready": False,
            },
            runway_status={
                "ready": True,
                "red_elevation_ready": False,
            },
            active_ruleset_id="icao_annex14_vol1_modernised_ofs_oes",
            protected_airspace_policy="ruleset_comparison",
        )

        self.assertEqual(status["state"], "warning")
        self.assertIn("airport-wide/secondary OLS", status["summary"])

    def test_save_payload_records_explicit_ols_ruleset_pair(self):
        self.select_mode("modernisation_comparison")

        payload = self.dialog._build_save_payload("TEST")

        self.assertEqual(payload["baseline_ols_ruleset"], "mos139_2019")
        self.assertEqual(
            payload["comparison_ols_ruleset"],
            "icao_annex14_vol1_modernised_ofs_oes",
        )
        self.assertEqual(payload["protected_airspace_policy"], "modernisation_comparison")

    def test_uk_framework_options_are_selectable_and_persisted(self):
        framework = self.dialog.framework_combo
        uk_index = framework.findData("uk_caa_safeguarding")

        self.assertTrue(framework.isEnabled())
        self.assertGreaterEqual(uk_index, 0)
        framework.setCurrentIndex(uk_index)
        self.dialog.show()
        self.app.processEvents()
        self.dialog._sync_global_context_box_geometry()
        self.app.processEvents()
        self.assertGreater(self.dialog.groupBox_ruleset.height(), 136)
        self.assertGreaterEqual(
            self.dialog.uk_framework_options.height(),
            self.dialog.uk_framework_options.sizeHint().height(),
        )
        self.assertFalse(
            self.dialog.uk_psz_applicable.geometry().intersects(
                self.dialog.uk_pscz_length.geometry()
            )
        )
        self.assertIsNone(
            self.dialog.findChild(
                QtWidgets.QDoubleSpinBox,
                "doubleSpinBox_uk_wildlife_radius_km",
            )
        )
        self.assertIsNone(
            self.dialog.findChild(
                QtWidgets.QDoubleSpinBox,
                "doubleSpinBox_uk_wind_turbine_radius_km",
            )
        )
        self.assertIsNone(
            self.dialog.findChild(QtWidgets.QLabel, "label_uk_framework_notice")
        )
        self.dialog.uk_psz_applicable.setChecked(True)
        self.dialog.uk_pscz_length.setCurrentIndex(
            self.dialog.uk_pscz_length.findData(1500.0)
        )

        payload = self.dialog._build_save_payload("EGLL")

        self.assertEqual(payload["safeguarding_framework"], "uk_caa_safeguarding")
        self.assertEqual(
            payload["safeguarding_options"],
            {
                "psz_applicable": True,
                "pscz_length_m": 1500.0,
            },
        )

    def test_save_payload_records_scenario_and_uses_standard_filename(self):
        payload = self.dialog._build_save_payload("YBBN")

        self.assertEqual(payload["runway_configuration"], "single")
        self.assertEqual(payload["test_case_id"], "ybbn_1rwy_single")
        self.assertEqual(payload["test_case_name"], "YBBN 1Rwy Single")
        self.assertEqual(
            self.dialog._suggested_input_filename(
                payload["icao_code"],
                len(payload["runways"]),
                payload["runway_configuration"],
            ),
            "ybbn_1rwy_single.json",
        )
        self.assertEqual(
            self.dialog._test_case_name_from_stem(
                "ybbn_1rwy_single",
                payload["icao_code"],
            ),
            "YBBN 1Rwy Single",
        )

    def test_sourcing_template_tracks_the_complete_input_schema(self):
        template_path = WORKSPACE / "docs" / "templates" / "test-input-template.json"
        payload = json.loads(template_path.read_text(encoding="utf-8"))

        self.dialog._validate_loaded_payload(payload)
        expected_top_level = {
            "test_case_id",
            "test_case_name",
            "icao_code",
            "iata_code",
            "arp_easting",
            "arp_northing",
            "arp_elevation",
            "met_easting",
            "met_northing",
            "met_elevation",
            "design_standard",
            "ruleset",
            "safeguarding_framework",
            "safeguarding_options",
            "protected_airspace_policy",
            "baseline_ols_ruleset",
            "comparison_ols_ruleset",
            "runway_configuration",
            "runways",
            "cns_facilities",
            "agl_options",
            "output_options",
        }
        self.assertTrue(expected_top_level.issubset(payload))
        self.assertEqual(
            set(payload["runways"][0]),
            set(self.dialog._runway_groups[1].get_input_data()),
        )
        self.assertEqual(
            set(payload["output_options"]["contour_intervals"]),
            {"default", *CONTOUR_INTERVAL_KEYS},
        )
        self.assertEqual(
            set(payload["cns_facilities"][0]),
            {"type", "easting_x", "northing_y", "elevation"},
        )
        self.assertEqual(
            set(payload["agl_options"]),
            {"enabled", "edge_spacing_m", "threshold_spacing_m", "threshold_inset_m"},
        )

    def test_loaded_scenario_must_match_runway_count(self):
        payload = {"icao_code": "YTEST", "runways": [{}, {}]}
        for scenario in ("parallel", "intersecting"):
            payload["runway_configuration"] = scenario
            self.dialog._validate_loaded_payload(payload)

        for scenario in ("single", "mixed", "multiple"):
            payload["runway_configuration"] = scenario
            with self.subTest(scenario=scenario):
                with self.assertRaises(ValueError):
                    self.dialog._validate_loaded_payload(payload)

    def test_save_payload_uses_only_canonical_runway_elevation_fields(self):
        group = self.dialog._runway_groups[1]
        group.runway_end_elev_1_le.setText("3.3")
        group.runway_end_elev_2_le.setText("3.8")
        group.threshold_elev_1_le.setText("3.6")
        group.threshold_elev_2_le.setText("0")

        runway = self.dialog._build_save_payload("TEST")["runways"][0]

        self.assertEqual(runway["runway_end_elev_1"], "3.3")
        self.assertEqual(runway["runway_end_elev_2"], "3.8")
        self.assertEqual(runway["threshold_elev_1"], "3.6")
        self.assertEqual(runway["threshold_elev_2"], "0")
        self.assertNotIn("thr_elev_1", runway)
        self.assertNotIn("thr_elev_2", runway)

    def test_save_payload_uses_only_canonical_adg_field(self):
        group = self.dialog._runway_groups[1]
        group._set_combo_data(group.adg_combo, "V")

        runway = self.dialog._build_save_payload("TEST")["runways"][0]

        self.assertEqual(runway["adg"], "V")
        self.assertNotIn("design_group", runway)

    def test_legacy_design_group_is_normalized_at_load_boundary(self):
        legacy = {"design_group": "III"}

        normalized = self.dialog._with_runway_defaults(legacy)

        self.assertEqual(normalized["adg"], "III")
        self.assertNotIn("design_group", normalized)
        self.assertEqual(legacy, {"design_group": "III"})

        self.dialog._load_runway_rows([legacy])
        resaved = self.dialog._build_save_payload("TEST")["runways"][0]
        self.assertEqual(resaved["adg"], "III")
        self.assertNotIn("design_group", resaved)

    def test_load_normalization_prefers_canonical_adg(self):
        normalized = self.dialog._with_runway_defaults(
            {"adg": "V", "design_group": "III"}
        )

        self.assertEqual(normalized["adg"], "V")
        self.assertNotIn("design_group", normalized)

    def test_legacy_runway_requires_modernised_annex14_review(self):
        normalized = self.dialog._with_runway_defaults({"adg": "III"})

        self.assertFalse(normalized["annex14_modernised"]["confirmed"])
        self.assertTrue(normalized["annex14_modernised"]["review_required"])
        self.assertEqual(
            normalized["annex14_modernised"]["primary_end"]["operations"],
            {},
        )

    def test_modernised_annex14_validation_derives_straight_in_operations(self):
        config = {
            "confirmed": True,
            "strip": {
                "source": "manual",
                "overall_width_m": "300",
                "end_extension_m": "60",
            },
            "primary_end": {
                "operations": {"precision_approach": True, "take_off": True},
                "maximum_certificated_takeoff_mass_kg": "5700",
            },
            "reciprocal_end": {"operations": {}},
        }

        normalized, errors = self.dialog._validate_annex14_modernised_config(
            1,
            config,
            {
                "type1": "Precision Approach CAT I",
                "type2": "Non-Instrument (NI)",
                "threshold_elev_1": "10",
                "threshold_elev_2": "11",
            },
        )

        self.assertEqual(errors, [])
        self.assertTrue(
            normalized["primary_end"]["operations"]["precision_approach"]
        )
        self.assertTrue(
            normalized["primary_end"]["operations"]["instrument_departure"]
        )
        self.assertFalse(
            normalized["primary_end"]["operations"]["circling_or_visual_circuit"]
        )
        self.assertIsNone(
            normalized["primary_end"]["maximum_certificated_takeoff_mass_kg"]
        )
        self.assertEqual(normalized["strip"]["source"], "manual")

    def test_modernised_annex14_ignores_specific_oes_under_straight_in_assumption(self):
        config = {
            "confirmed": True,
            "strip": {
                "source": "design_standard_prefill",
                "overall_width_m": 300,
                "end_extension_m": 60,
            },
            "primary_end": {
                "operations": {},
                "specific_oes_required": True,
            },
            "reciprocal_end": {"operations": {}},
        }

        normalized, errors = self.dialog._validate_annex14_modernised_config(
            1,
            config,
            {
                "type1": "Non-Instrument (NI)",
                "type2": "Non-Instrument (NI)",
                "threshold_elev_1": "10",
                "threshold_elev_2": "11",
            },
        )

        self.assertFalse(normalized["review_required"])
        self.assertEqual(errors, [])
        self.assertFalse(normalized["primary_end"]["specific_oes_required"])

    def test_modernised_annex14_allows_no_applicable_oes_operation(self):
        config = {
            "confirmed": True,
            "strip": {
                "source": "manual",
                "overall_width_m": 150,
                "end_extension_m": 60,
            },
            "primary_end": {"operations": {}},
            "reciprocal_end": {"operations": {}},
        }

        normalized, errors = self.dialog._validate_annex14_modernised_config(
            1,
            config,
            {
                "type1": "Non-Instrument (NI)",
                "type2": "Non-Instrument (NI)",
                "threshold_elev_1": "10",
                "threshold_elev_2": "11",
                "takeoff_available_1": False,
                "takeoff_available_2": False,
            },
        )

        self.assertFalse(normalized["review_required"])
        self.assertEqual(errors, [])
        self.assertFalse(
            any(normalized["primary_end"]["operations"].values())
        )

    def test_modernised_straight_in_basis_does_not_gate_on_aerodrome_elevation(self):
        config = {
            "confirmed": True,
            "strip": {
                "source": "manual",
                "overall_width_m": 140,
                "end_extension_m": 60,
            },
            "primary_end": {
                "operations": {
                    "straight_in_non_precision_instrument": True,
                },
            },
            "reciprocal_end": {"operations": {}},
        }
        runway = {
            "type1": "Non-Precision Approach (NPA)",
            "type2": "Non-Instrument (NI)",
            "threshold_elev_1": "10",
            "threshold_elev_2": "11",
            "takeoff_available_1": False,
            "takeoff_available_2": False,
        }

        normalized, errors = self.dialog._validate_annex14_modernised_config(
            1,
            config,
            runway,
        )

        self.assertFalse(normalized["review_required"])
        self.assertEqual(errors, [])
        self.assertTrue(
            normalized["primary_end"]["operations"][
                "straight_in_non_precision_instrument"
            ]
        )
        self.assertFalse(
            normalized["primary_end"]["operations"]["precision_approach"]
        )

    def test_modernised_annex14_automatically_uses_design_strip_and_code_f_case(self):
        normalized, errors = self.dialog._validate_annex14_modernised_config(
            1,
            {},
            {
                "arc_num": "4",
                "arc_let": "F",
                "width": "45",
                "type1": "Precision Approach CAT I",
                "type2": "Precision Approach CAT I",
                "threshold_elev_1": "10",
                "threshold_elev_2": "11",
            },
        )

        self.assertEqual(errors, [])
        self.assertTrue(normalized["confirmed"])
        self.assertEqual(
            normalized["operation_basis"],
            "automatic_conservative_straight_in",
        )
        self.assertEqual(
            normalized["strip"]["source"],
            "design_standard_prefill",
        )
        self.assertEqual(
            normalized["strip"]["design_ruleset_id"],
            self.dialog.ruleset_combo.currentData(),
        )
        self.assertIsNotNone(normalized["strip"]["overall_width_m"])
        self.assertTrue(
            normalized["code_f_without_digital_go_around_avionics"]
        )

    def test_legacy_runway_elevations_are_normalized_at_load_boundary(self):
        legacy = {"thr_elev_1": "0", "thr_elev_2": "12.5"}

        normalized = self.dialog._with_runway_defaults(legacy)

        self.assertEqual(normalized["runway_end_elev_1"], "0")
        self.assertEqual(normalized["runway_end_elev_2"], "12.5")
        self.assertEqual(normalized["threshold_elev_1"], "0")
        self.assertEqual(normalized["threshold_elev_2"], "12.5")
        self.assertNotIn("thr_elev_1", normalized)
        self.assertNotIn("thr_elev_2", normalized)
        self.assertEqual(legacy, {"thr_elev_1": "0", "thr_elev_2": "12.5"})

        self.dialog._load_runway_rows([legacy])
        resaved = self.dialog._build_save_payload("TEST")["runways"][0]
        self.assertEqual(resaved["runway_end_elev_1"], "0")
        self.assertEqual(resaved["runway_end_elev_2"], "12.5")
        self.assertEqual(resaved["threshold_elev_1"], "0")
        self.assertEqual(resaved["threshold_elev_2"], "12.5")
        self.assertNotIn("thr_elev_1", resaved)
        self.assertNotIn("thr_elev_2", resaved)

    def test_load_normalization_preserves_distinct_canonical_elevations(self):
        normalized = self.dialog._with_runway_defaults(
            {
                "runway_end_elev_1": "3.3",
                "runway_end_elev_2": "3.8",
                "threshold_elev_1": "3.6",
                "threshold_elev_2": "3.2",
                "thr_elev_1": "3.6",
                "thr_elev_2": "3.2",
            }
        )

        self.assertEqual(normalized["runway_end_elev_1"], "3.3")
        self.assertEqual(normalized["runway_end_elev_2"], "3.8")
        self.assertEqual(normalized["threshold_elev_1"], "3.6")
        self.assertEqual(normalized["threshold_elev_2"], "3.2")
        self.assertNotIn("thr_elev_1", normalized)
        self.assertNotIn("thr_elev_2", normalized)

    def test_baseline_mode_hides_future_family_rows(self):
        self.select_mode("ruleset_aligned")
        self.dialog.toolButtonContourOverrides.setChecked(True)

        self.assertTrue(self.dialog.frame_olsFamilyExplanation.isHidden())
        self.assertTrue(self.dialog.toolButtonOlsFamilyHelp.isHidden())
        self.assertFalse(self.dialog._contour_interval_labels["approach"].isHidden())
        self.assertTrue(self.dialog._contour_interval_labels["annex14_ofs"].isHidden())
        self.assertFalse(self.dialog.labelComparisonContourEmpty.isHidden())
        self.assertTrue(
            self.dialog._contour_interval_labels["comparison_approach"].isHidden()
        )

    def test_mos139_contours_follow_output_group_sections(self):
        self.select_mode("ruleset_aligned")
        self.dialog.toolButtonContourOverrides.setChecked(True)
        expected_sections = (
            (
                "Obstacle Free Zone",
                (
                    ("inner_approach", "Inner approach"),
                    ("inner_transitional", "Inner transitional"),
                    ("baulked_landing", "Baulked landing"),
                ),
            ),
            (
                "Primary Surfaces",
                (
                    ("approach", "Approach"),
                    ("tocs", "Take-off climb"),
                    ("transitional", "Transitional"),
                ),
            ),
            ("Secondary", (("conical", "Conical"),)),
        )
        layout = self.dialog.frameBaselineContourSettings.layout()
        previous_row = -1
        for section, rows in expected_sections:
            section_label = self.dialog._contour_conventional_section_labels[
                "baseline"
            ][section]
            section_row = layout.getItemPosition(layout.indexOf(section_label))[0]
            self.assertGreater(section_row, previous_row)
            self.assertFalse(section_label.isHidden())
            for key, text in rows:
                label = self.dialog._contour_interval_labels[key]
                row = layout.getItemPosition(layout.indexOf(label))[0]
                self.assertGreater(row, section_row)
                self.assertEqual(label.text(), text)
                self.assertFalse(label.isHidden())
                previous_row = row


    def test_future_mode_shows_requested_granular_oes_and_ofs_rows(self):
        self.select_mode("future_annex14_ofs_oes")
        self.dialog.toolButtonContourOverrides.setChecked(True)

        self.assertFalse(self.dialog.toolButtonOlsFamilyHelp.isHidden())
        self.assertTrue(self.dialog.frame_olsFamilyExplanation.isHidden())
        self.dialog.toolButtonOlsFamilyHelp.setChecked(True)
        self.assertFalse(self.dialog.frame_olsFamilyExplanation.isHidden())
        self.assertEqual(self.dialog.label_olsOfsTitle.text(), "OFS — protected airspace")
        self.assertIn("Obstacle-free surface", self.dialog.label_olsOfsDetail.text())
        self.assertEqual(self.dialog.label_olsOesTitle.text(), "OES — assessment trigger")
        self.assertIn("not an approval limit", self.dialog.label_olsOesDetail.text())
        self.assertFalse(self.dialog.frameBaselineContourSettings.isHidden())
        self.assertFalse(self.dialog.toolButtonContourOverrides.isHidden())
        self.assertTrue(self.dialog._contour_interval_labels["approach"].isHidden())
        expected_rows = {
            "annex14_oes_precision_approach": "Precision Approach",
            "annex14_oes_take_off_climb": "Take-off Climb",
            "annex14_oes_instrument_departure": "Instrument Departure",
            "annex14_ofs_approach": "Approach",
            "annex14_ofs_transitional": "Transitional",
            "annex14_ofs_balked_landing": "Baulked Landing",
            "annex14_ofs_inner_approach": "Inner Approach",
            "annex14_ofs_inner_transitional": "Inner Transitional",
        }
        for key, text in expected_rows.items():
            self.assertEqual(self.dialog._contour_interval_labels[key].text(), text)
            self.assertFalse(self.dialog._contour_interval_labels[key].isHidden())
            self.assertIs(
                self.dialog._contour_interval_labels[key].parentWidget(),
                self.dialog.frameBaselineContourSettings,
            )
        self.assertEqual(
            self.dialog._contour_annex_section_labels["baseline"]["OES"].text(),
            "OES",
        )
        self.assertEqual(
            self.dialog._contour_annex_section_labels["baseline"]["OFS"].text(),
            "OFS",
        )
        self.assertTrue(self.dialog._contour_interval_labels["annex14_ofs"].isHidden())
        self.assertTrue(self.dialog._contour_interval_labels["annex14_oes"].isHidden())
        self.assertTrue(
            self.dialog._contour_interval_labels["modernisation_ofs_change"].isHidden()
        )
        self.assertTrue(
            self.dialog._contour_interval_labels["modernisation_oes_change"].isHidden()
        )

    def test_granular_annex_contours_are_directly_editable_and_used_by_generation(self):
        self.select_mode("future_annex14_ofs_oes")
        self.dialog.toolButtonContourOverrides.setChecked(True)
        intervals = {
            "annex14_oes_precision_approach": 2.0,
            "annex14_oes_take_off_climb": 3.0,
            "annex14_oes_instrument_departure": 4.0,
            "annex14_ofs_approach": 5.0,
            "annex14_ofs_transitional": 6.0,
            "annex14_ofs_balked_landing": 7.0,
            "annex14_ofs_inner_approach": 8.0,
            "annex14_ofs_inner_transitional": 9.0,
        }

        self.assertIs(
            self.dialog._contour_interval_labels["annex14_ofs_approach"].parentWidget(),
            self.dialog.frameBaselineContourSettings,
        )
        for key, value in intervals.items():
            spinbox = self.dialog._contour_interval_spinboxes[key]
            self.assertFalse(spinbox.isHidden())
            self.assertTrue(spinbox.isEnabled())
            spinbox.setValue(value)

        options = self.dialog.get_contour_interval_options()
        builder = object.__new__(SafeguardingBuilder)
        builder.contour_intervals = options
        self.assertEqual(builder._annex14_contour_interval("precision_approach", "OES"), 2.0)
        self.assertEqual(builder._annex14_contour_interval("take_off_climb", "OES"), 3.0)
        self.assertEqual(builder._annex14_contour_interval("instrument_departure", "OES"), 4.0)
        self.assertEqual(builder._annex14_contour_interval("approach", "OFS"), 5.0)
        self.assertEqual(builder._annex14_contour_interval("transitional", "OFS"), 6.0)
        self.assertEqual(builder._annex14_contour_interval("balked_landing", "OFS"), 7.0)
        self.assertEqual(builder._annex14_contour_interval("inner_approach", "OFS"), 8.0)
        self.assertEqual(builder._annex14_contour_interval("inner_transitional", "OFS"), 9.0)

    def test_saved_future_family_override_expands_contextual_settings(self):
        self.dialog.set_contour_interval_options(
            {
                "default": {"primary": 50.0, "intermediate": 10.0},
                "annex14_ofs": {"primary": 40.0, "intermediate": 8.0},
            }
        )
        self.select_mode("modernisation_comparison")

        self.assertTrue(self.dialog.toolButtonContourOverrides.isChecked())
        self.assertFalse(self.dialog.widgetContourOverrides.isHidden())
        self.assertEqual(
            self.dialog._contour_interval_spinboxes[
                "comparison_annex14_ofs_approach"
            ].value(),
            8.0,
        )

    def test_comparison_change_contours_are_directly_editable_per_family(self):
        self.select_mode("modernisation_comparison")
        self.assertFalse(self.dialog.toolButtonComparisonChangeContours.isHidden())
        self.assertFalse(self.dialog.toolButtonComparisonChangeContours.isChecked())
        self.dialog.toolButtonComparisonChangeContours.setChecked(True)
        ofs_primary = self.dialog._contour_primary_interval_spinboxes[
            "modernisation_ofs_change"
        ]
        ofs_intermediate = self.dialog._contour_interval_spinboxes[
            "modernisation_ofs_change"
        ]
        oes_primary = self.dialog._contour_primary_interval_spinboxes[
            "modernisation_oes_change"
        ]
        oes_intermediate = self.dialog._contour_interval_spinboxes[
            "modernisation_oes_change"
        ]

        self.assertEqual((ofs_primary.value(), ofs_intermediate.value()), (10.0, 1.0))
        self.assertEqual((oes_primary.value(), oes_intermediate.value()), (10.0, 1.0))
        for spinbox in (ofs_primary, ofs_intermediate, oes_primary, oes_intermediate):
            self.assertFalse(spinbox.isHidden())
            self.assertTrue(spinbox.isEnabled())

        ofs_primary.setValue(2.0)
        ofs_intermediate.setValue(0.3)
        oes_primary.setValue(1.5)
        oes_intermediate.setValue(0.2)
        options = self.dialog.get_contour_interval_options()
        builder = object.__new__(SafeguardingBuilder)
        builder.contour_intervals = options

        self.assertEqual(
            builder._modernisation_change_contour_intervals("OFS"),
            (0.3, 2.0),
        )
        self.assertEqual(
            builder._modernisation_change_contour_intervals("OES"),
            (0.2, 1.5),
        )

    def test_comparison_change_contours_are_available_for_conventional_rulesets(self):
        for comparison_id in (
            "uk_caa_cap168_edition_13",
            "icao_annex14_vol1_current_ols",
        ):
            with self.subTest(comparison_id=comparison_id):
                self.dialog._set_ols_ruleset_selection(
                    "mos139_2019",
                    comparison_id,
                )
                self.dialog._update_ols_workflow_ui()

                button = self.dialog.toolButtonComparisonChangeContours
                self.assertFalse(button.isHidden())
                button.setChecked(True)
                self.assertFalse(
                    self.dialog._contour_interval_labels[
                        "comparison_change"
                    ].isHidden()
                )
                self.assertTrue(
                    self.dialog._contour_interval_labels[
                        "modernisation_ofs_change"
                    ].isHidden()
                )
                self.assertTrue(
                    self.dialog._contour_interval_labels[
                        "modernisation_oes_change"
                    ].isHidden()
                )
                button.setChecked(False)

    def test_conventional_change_contour_interval_is_saved_for_generation(self):
        self.dialog._set_ols_ruleset_selection(
            "mos139_2019",
            "uk_caa_cap168_edition_13",
        )
        self.dialog._update_ols_workflow_ui()
        self.dialog.toolButtonComparisonChangeContours.setChecked(True)
        self.dialog._contour_primary_interval_spinboxes[
            "comparison_change"
        ].setValue(2.0)
        self.dialog._contour_interval_spinboxes["comparison_change"].setValue(0.5)

        options = self.dialog.get_contour_interval_options()
        builder = object.__new__(SafeguardingBuilder)
        builder.contour_intervals = options

        self.assertEqual(
            builder._modernisation_change_contour_intervals("OLS"),
            (0.5, 2.0),
        )

    def test_contour_control_markup_behaviour(self):
        self.select_mode("modernisation_comparison")
        self.dialog.toolButtonContourOverrides.setChecked(False)

        layout = self.dialog.groupBox_contourIntervals.layout()
        change_label = self.dialog._contour_interval_labels[
            "modernisation_ofs_change"
        ]
        change_row = layout.getItemPosition(layout.indexOf(change_label))[0]
        change_disclosure_row = layout.getItemPosition(
            layout.indexOf(self.dialog.toolButtonComparisonChangeContours)
        )[0]
        disclosure_row = layout.getItemPosition(
            layout.indexOf(self.dialog.toolButtonContourOverrides)
        )[0]
        self.assertLess(change_disclosure_row, change_row)
        self.assertLess(change_row, disclosure_row)
        self.assertIs(change_label.parentWidget(), self.dialog.groupBox_contourIntervals)
        self.assertTrue(change_label.isHidden())
        self.dialog.toolButtonComparisonChangeContours.setChecked(True)
        self.assertFalse(change_label.isHidden())
        self.assertTrue(self.dialog.widgetContourOverrides.isHidden())

        headers = [
            self.dialog.labelContourPrimaryHeader,
            self.dialog.labelContourIntermediateHeader,
            *self.dialog._contour_column_interval_headers["baseline"],
            *self.dialog._contour_column_interval_headers["comparison"],
        ]
        for header in headers:
            self.assertTrue(
                header.alignment() & QtCore.Qt.AlignmentFlag.AlignHCenter
            )

        spinboxes = [
            self.dialog.doubleSpinBoxContourDefaultPrimary,
            self.dialog.doubleSpinBoxContourDefault,
            *self.dialog._contour_primary_interval_spinboxes.values(),
            *self.dialog._contour_interval_spinboxes.values(),
        ]
        self.assertTrue(all(spinbox.decimals() == 1 for spinbox in spinboxes))

        class WheelEvent:
            ignored = False

            def ignore(self):
                self.ignored = True

        spinbox = self.dialog.doubleSpinBoxContourDefault
        original_value = spinbox.value()
        event = WheelEvent()
        spinbox.wheelEvent(event)
        self.assertTrue(event.ignored)
        self.assertEqual(spinbox.value(), original_value)

    def test_change_contour_defaults_are_not_overwritten_by_surface_default(self):
        self.dialog.doubleSpinBoxContourDefaultPrimary.setValue(100.0)
        self.dialog.doubleSpinBoxContourDefault.setValue(20.0)

        self.assertEqual(
            self.dialog._contour_primary_interval_spinboxes[
                "modernisation_ofs_change"
            ].value(),
            10.0,
        )
        self.assertEqual(
            self.dialog._contour_interval_spinboxes[
                "modernisation_ofs_change"
            ].value(),
            1.0,
        )

    def test_comparison_selection_shows_all_comparison_rows(self):
        self.select_mode("modernisation_comparison")
        self.dialog.toolButtonContourOverrides.setChecked(True)

        self.assertFalse(self.dialog._contour_interval_labels["approach"].isHidden())
        self.assertFalse(
            self.dialog._contour_interval_labels[
                "comparison_annex14_ofs_approach"
            ].isHidden()
        )
        self.assertFalse(self.dialog.toolButtonContourOverrides.isHidden())
        self.assertTrue(self.dialog._contour_interval_labels["annex14_ofs"].isHidden())
        status = self.dialog.findChild(
            QtWidgets.QLabel,
            "label_workflow_context_status_tab_ols",
        )
        self.assertEqual(status.text(), "Ready")
        self.assertEqual(status.toolTip(), "OLS ready.")

    def test_ols_warning_is_shown_in_the_muted_context_tile(self):
        self.dialog._update_ols_workflow_ui(
            dependency_status={"state": "warning", "summary": "Controlling OLS is experimental."},
            runway_count=1,
        )

        status = self.dialog.findChild(
            QtWidgets.QLabel,
            "label_workflow_context_status_tab_ols",
        )
        self.assertEqual(status.text(), "Review")
        self.assertEqual(status.toolTip(), "Controlling OLS is experimental.")

    def test_contour_disclosures_report_state_and_reset_is_contextual(self):
        self.assertEqual(self.dialog.groupBox_contourIntervals.title(), "Contour intervals")
        self.assertEqual(
            self.dialog.toolButtonContourOverrides.text(),
            "Surface-specific overrides · Using defaults",
        )
        self.assertTrue(self.dialog.toolButtonResetContourIntervals.isHidden())

        self.dialog._contour_interval_spinboxes["approach"].setValue(5.0)

        self.assertEqual(
            self.dialog.toolButtonContourOverrides.text(),
            "Surface-specific overrides · 1 override",
        )
        self.assertFalse(self.dialog.toolButtonResetContourIntervals.isHidden())

        self.dialog._reset_contour_interval_controls()

        self.assertEqual(
            self.dialog.toolButtonContourOverrides.text(),
            "Surface-specific overrides · Using defaults",
        )
        self.assertTrue(self.dialog.toolButtonResetContourIntervals.isHidden())

    def test_partial_controlling_capability_is_not_a_readiness_warning(self):
        with patch(
            "safeguarding_builder.safeguarding_builder_dialog.get_ruleset_profile"
        ) as get_profile:
            get_profile.return_value.capability_status.side_effect = lambda key: {
                "ols.airport_wide": "supported",
                "ols.controlling_lower_envelope": "partial",
            }.get(key)
            status = self.dialog._ols_dependency_status(
                airport_status={
                    "identity_ready": True,
                    "arp_pair_ready": True,
                    "arp_elev_ready": True,
                },
                runway_status={"ready": True, "red_elevation_ready": True},
                active_ruleset_id="mos139_2019",
                protected_airspace_policy="ruleset_aligned",
            )

        self.assertEqual(status["state"], "ready")
        self.assertNotIn("partial", status["summary"].lower())

    def test_legacy_controlling_toggle_is_ignored_and_not_resaved(self):
        self.select_mode("modernisation_comparison")

        self.dialog._load_output_options({"generate_controlling_ols": False})
        payload = self.dialog._build_save_payload("TEST")

        self.assertNotIn("generate_controlling_ols", payload["output_options"])

    def test_contour_defaults_remain_visible_outside_collapsed_overrides(self):
        self.assertTrue(self.dialog.widgetContourOverrides.isHidden())
        self.assertFalse(self.dialog.doubleSpinBoxContourDefaultPrimary.isHidden())
        self.assertFalse(self.dialog.doubleSpinBoxContourDefault.isHidden())
        self.assertIs(
            self.dialog._contour_interval_labels["approach"].parentWidget(),
            self.dialog.frameBaselineContourSettings,
        )

        self.dialog.toolButtonContourOverrides.setChecked(True)

        self.assertFalse(self.dialog.widgetContourOverrides.isHidden())

    def test_ruleset_columns_keep_baseline_and_comparison_intervals_independent(self):
        self.select_mode("modernisation_comparison")
        baseline = self.dialog._contour_interval_spinboxes["approach"]
        comparison = self.dialog._contour_interval_spinboxes[
            "comparison_annex14_ofs_approach"
        ]
        baseline.setValue(8.0)
        comparison.setValue(6.0)
        options = self.dialog.get_contour_interval_options()
        builder = object.__new__(SafeguardingBuilder)
        builder.contour_intervals = options

        builder._contour_interval_ruleset_role = "baseline"
        self.assertEqual(builder._get_contour_interval("approach", 10.0), 8.0)
        builder._contour_interval_ruleset_role = "comparison"
        self.assertEqual(builder._annex14_contour_interval("approach", "OFS"), 6.0)

    def test_legacy_surface_intervals_seed_comparison_column_when_loading(self):
        self.dialog.set_contour_interval_options(
            {
                "default": {"primary": 50.0, "intermediate": 10.0},
                "annex14_ofs": {"primary": 40.0, "intermediate": 7.0},
            }
        )

        self.assertEqual(
            self.dialog._contour_interval_spinboxes[
                "comparison_annex14_ofs_approach"
            ].value(),
            7.0,
        )

    def test_legacy_annex_family_value_remains_a_generation_fallback(self):
        builder = object.__new__(SafeguardingBuilder)
        builder.contour_intervals = {
            "default": {"primary": 50.0, "intermediate": 10.0},
            "annex14_ofs": {"primary": 40.0, "intermediate": 8.0},
            "comparison_annex14_ofs": {"primary": 35.0, "intermediate": 7.0},
        }

        builder._contour_interval_ruleset_role = "baseline"
        self.assertEqual(builder._annex14_contour_interval("inner_approach", "OFS"), 8.0)
        builder._contour_interval_ruleset_role = "comparison"
        self.assertEqual(builder._annex14_contour_interval("inner_approach", "OFS"), 7.0)

    def test_saved_individual_contour_override_expands_section(self):
        self.dialog.set_contour_interval_options(
            {
                "default": {"primary": 50.0, "intermediate": 10.0},
                "approach": {"primary": 25.0, "intermediate": 5.0},
            }
        )

        self.assertTrue(self.dialog.toolButtonContourOverrides.isChecked())
        self.assertFalse(self.dialog.widgetContourOverrides.isHidden())
        self.assertEqual(
            self.dialog._contour_primary_interval_spinboxes["approach"].value(),
            25.0,
        )

    def test_phase_progress_state_has_no_cancel_control(self):
        self.dialog.begin_processing(10)
        self.dialog.set_processing_status("Solving controlling envelopes...", step=8, total_steps=10)

        self.assertTrue(self.dialog._processing_status_active)
        self.assertEqual(self.dialog._processing_progress_bar.minimum(), 0)
        self.assertEqual(self.dialog._processing_progress_bar.maximum(), 10)
        self.assertEqual(self.dialog._processing_progress_bar.value(), 8)
        self.assertIsNone(
            self.dialog.findChild(
                QtWidgets.QPushButton,
                "pushButton_cancel_processing",
            )
        )

        self.dialog.clear_processing_status("Generation complete.")

        self.assertFalse(self.dialog._processing_status_active)
        self.assertTrue(self.dialog._processing_progress_bar.isHidden())
        self.assertEqual(
            self.dialog.label_footer_status.toolTip(),
            "Generation complete.",
        )

    def test_dynamic_status_text_is_bounded_without_resizing_the_dialog(self):
        self.dialog.show()
        self.app.processEvents()
        self.dialog.resize(824, 760)
        self.app.processEvents()
        original_size = self.dialog.size()

        self.dialog.set_processing_status(
            "Generating a deliberately long protected-airspace status message "
            "that must remain inside the footer allocation",
            step=8,
            total_steps=10,
        )
        self.app.processEvents()

        self.assertEqual(self.dialog.size(), original_size)
        self.assertIn(
            "deliberately long protected-airspace status message",
            self.dialog.label_footer_status.toolTip(),
        )
        self.assertEqual(
            self.dialog.label_footer_status.sizePolicy().horizontalPolicy(),
            QtWidgets.QSizePolicy.Policy.Ignored,
        )

    def test_footer_status_elides_and_retains_full_message_in_tooltip(self):
        message = "A long generation message that cannot fit into a narrow footer label"
        self.dialog.label_footer_status.setFixedWidth(120)

        self.dialog._set_footer_status(message)

        self.assertEqual(self.dialog.label_footer_status.toolTip(), message)
        self.assertNotEqual(self.dialog.label_footer_status.text(), message)
        self.assertIn("…", self.dialog.label_footer_status.text())

    def test_readiness_label_wraps_with_a_shrinkable_width(self):
        readiness = self.dialog.label_generation_readiness_detail

        self.assertTrue(readiness.wordWrap())
        self.assertEqual(readiness.minimumWidth(), 0)
        self.assertEqual(
            readiness.sizePolicy().horizontalPolicy(),
            QtWidgets.QSizePolicy.Policy.Ignored,
        )

    def test_post_initial_height_update_preserves_user_size(self):
        self.dialog.resize(930, 710)
        expected_size = self.dialog.size()

        self.dialog._update_dialog_height()
        self.app.processEvents()

        self.assertEqual(self.dialog.size(), expected_size)

    def test_workflow_tabs_do_not_impose_largest_page_height_on_dock(self):
        self.assertEqual(
            self.dialog.tabWidget_workflow.sizePolicy().verticalPolicy(),
            QtWidgets.QSizePolicy.Policy.Ignored,
        )
        self.assertLess(self.dialog.minimumSizeHint().height(), 700)

    def test_long_workflow_tabs_scroll_instead_of_compressing_controls(self):
        self.dialog.resize(800, 650)
        self.dialog.show()
        for tab_name in ("tab_cns", "tab_ols", "tab_terrain"):
            with self.subTest(tab=tab_name):
                page = getattr(self.dialog, tab_name)
                self.dialog.tabWidget_workflow.setCurrentWidget(page)
                self.app.processEvents()
                scroll_area = self.dialog._workflow_scroll_areas[tab_name]
                self.assertGreater(scroll_area.verticalScrollBar().maximum(), 0)
                context = self.dialog._workflow_context_widgets[tab_name]["frame"]
                self.assertFalse(scroll_area.isAncestorOf(context))

    def test_builder_checkpoint_updates_progress_without_cancel_branch(self):
        builder = object.__new__(SafeguardingBuilder)
        builder._runtime_run_recorder = None
        builder._run_log = None

        with patch.object(builder, "_set_processing_status") as set_status:
            should_continue = builder._processing_checkpoint("Next phase", 4, 10)

        self.assertTrue(should_continue)
        set_status.assert_called_once_with("Next phase", step=4, total_steps=10)


if __name__ == "__main__":
    unittest.main()
