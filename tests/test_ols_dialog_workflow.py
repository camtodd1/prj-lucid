import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from qgis.PyQt import QtWidgets


WORKSPACE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORKSPACE.parent))

from safeguarding_builder.safeguarding_builder_dialog import SafeguardingBuilderDialog
from safeguarding_builder.safeguarding_builder import SafeguardingBuilder


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
        self.assertEqual(self.dialog.label_baselineOlsRuleset.text(), "Baseline OLS")
        self.assertEqual(self.dialog.label_comparisonOlsRuleset.text(), "Comparison OLS")
        self.assertEqual(baseline.currentData(), "mos139_2019")
        self.assertEqual(comparison.itemData(0), "")
        self.assertEqual(comparison.itemText(0), "None — baseline only")

    def test_unavailable_controlling_rulesets_remain_visible_but_disabled(self):
        baseline = self.dialog.baseline_ols_ruleset_combo
        cap168_index = baseline.findData("uk_caa_cap168_edition_13")

        self.assertGreaterEqual(cap168_index, 0)
        self.assertIn("unavailable", baseline.itemText(cap168_index).lower())
        self.assertFalse(baseline.model().item(cap168_index).isEnabled())

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
        self.assertFalse(self.dialog._contour_interval_labels["annex14_ofs"].isHidden())
        self.assertFalse(
            self.dialog._contour_interval_labels["comparison_approach"].isHidden()
        )
        self.assertTrue(self.dialog._contour_interval_labels["approach"].isHidden())
        self.assertTrue(
            self.dialog._contour_interval_labels["comparison_annex14_ofs"].isHidden()
        )
        self.assertTrue(self.dialog.checkBox_generateControllingOls.isChecked())
        self.assertFalse(self.dialog.checkBox_generateControllingOls.isEnabled())

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

    def test_baseline_mode_hides_future_family_rows(self):
        self.select_mode("ruleset_aligned")
        self.dialog.toolButtonContourOverrides.setChecked(True)

        self.assertTrue(self.dialog.frame_olsFamilyExplanation.isHidden())
        self.assertFalse(self.dialog._contour_interval_labels["approach"].isHidden())
        self.assertTrue(self.dialog._contour_interval_labels["annex14_ofs"].isHidden())
        self.assertFalse(self.dialog.labelComparisonContourEmpty.isHidden())
        self.assertTrue(
            self.dialog._contour_interval_labels["comparison_approach"].isHidden()
        )
        self.assertTrue(self.dialog.checkBox_generateControllingOls.isEnabled())

    def test_future_mode_shows_only_ofs_oes_family_rows(self):
        self.select_mode("future_annex14_ofs_oes")
        self.dialog.toolButtonContourOverrides.setChecked(True)

        self.assertFalse(self.dialog.frame_olsFamilyExplanation.isHidden())
        self.assertEqual(self.dialog.label_olsOfsTitle.text(), "OFS — protected airspace")
        self.assertIn("Obstacle-free surface", self.dialog.label_olsOfsDetail.text())
        self.assertEqual(self.dialog.label_olsOesTitle.text(), "OES — assessment trigger")
        self.assertIn("not an approval limit", self.dialog.label_olsOesDetail.text())
        self.assertFalse(self.dialog.frameBaselineContourSettings.isHidden())
        self.assertFalse(self.dialog.toolButtonContourOverrides.isHidden())
        self.assertTrue(self.dialog._contour_interval_labels["approach"].isHidden())
        self.assertFalse(self.dialog._contour_interval_labels["annex14_ofs"].isHidden())
        self.assertFalse(self.dialog._contour_interval_labels["annex14_oes"].isHidden())
        self.assertTrue(
            self.dialog._contour_interval_labels["modernisation_ofs_change"].isHidden()
        )
        self.assertTrue(
            self.dialog._contour_interval_labels["modernisation_oes_change"].isHidden()
        )

    def test_future_family_contours_are_directly_editable_and_used_by_generation(self):
        self.select_mode("future_annex14_ofs_oes")
        self.dialog.toolButtonContourOverrides.setChecked(True)
        ofs_primary = self.dialog._contour_primary_interval_spinboxes["annex14_ofs"]
        ofs_intermediate = self.dialog._contour_interval_spinboxes["annex14_ofs"]
        oes_primary = self.dialog._contour_primary_interval_spinboxes["annex14_oes"]
        oes_intermediate = self.dialog._contour_interval_spinboxes["annex14_oes"]

        self.assertIs(
            self.dialog._contour_interval_labels["annex14_ofs"].parentWidget(),
            self.dialog.frameBaselineContourSettings,
        )
        for spinbox in (ofs_primary, ofs_intermediate, oes_primary, oes_intermediate):
            self.assertFalse(spinbox.isHidden())
            self.assertTrue(spinbox.isEnabled())

        ofs_primary.setValue(40.0)
        ofs_intermediate.setValue(8.0)
        oes_primary.setValue(25.0)
        oes_intermediate.setValue(5.0)
        options = self.dialog.get_contour_interval_options()

        self.assertEqual(options["annex14_ofs"], {"primary": 40.0, "intermediate": 8.0})
        self.assertEqual(options["annex14_oes"], {"primary": 25.0, "intermediate": 5.0})
        builder = object.__new__(SafeguardingBuilder)
        builder.contour_intervals = options
        self.assertEqual(builder._annex14_contour_interval("approach", "OFS"), 8.0)
        self.assertEqual(builder._annex14_contour_interval("approach", "OES"), 5.0)

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
            self.dialog._contour_interval_spinboxes["annex14_ofs"].value(),
            8.0,
        )

    def test_comparison_change_contours_are_directly_editable_per_family(self):
        self.select_mode("modernisation_comparison")
        self.dialog.toolButtonContourOverrides.setChecked(True)
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

        self.assertEqual((ofs_primary.value(), ofs_intermediate.value()), (5.0, 1.0))
        self.assertEqual((oes_primary.value(), oes_intermediate.value()), (5.0, 1.0))
        for spinbox in (ofs_primary, ofs_intermediate, oes_primary, oes_intermediate):
            self.assertFalse(spinbox.isHidden())
            self.assertTrue(spinbox.isEnabled())

        ofs_primary.setValue(2.0)
        ofs_intermediate.setValue(0.25)
        oes_primary.setValue(1.5)
        oes_intermediate.setValue(0.2)
        options = self.dialog.get_contour_interval_options()
        builder = object.__new__(SafeguardingBuilder)
        builder.contour_intervals = options

        self.assertEqual(
            builder._modernisation_change_contour_intervals("OFS"),
            (0.25, 2.0),
        )
        self.assertEqual(
            builder._modernisation_change_contour_intervals("OES"),
            (0.2, 1.5),
        )

    def test_change_contour_defaults_are_not_overwritten_by_surface_default(self):
        self.dialog.doubleSpinBoxContourDefaultPrimary.setValue(100.0)
        self.dialog.doubleSpinBoxContourDefault.setValue(20.0)

        self.assertEqual(
            self.dialog._contour_primary_interval_spinboxes[
                "modernisation_ofs_change"
            ].value(),
            5.0,
        )
        self.assertEqual(
            self.dialog._contour_interval_spinboxes[
                "modernisation_ofs_change"
            ].value(),
            1.0,
        )

    def test_comparison_mode_requires_controlling_output_and_shows_all_rows(self):
        self.dialog.checkBox_generateControllingOls.setChecked(False)
        self.select_mode("modernisation_comparison")
        self.dialog.toolButtonContourOverrides.setChecked(True)

        self.assertTrue(self.dialog.checkBox_generateControllingOls.isChecked())
        self.assertFalse(self.dialog.checkBox_generateControllingOls.isEnabled())
        self.assertFalse(self.dialog._contour_interval_labels["approach"].isHidden())
        self.assertFalse(
            self.dialog._contour_interval_labels["comparison_annex14_ofs"].isHidden()
        )
        self.assertFalse(self.dialog.toolButtonContourOverrides.isHidden())
        self.assertTrue(self.dialog._contour_interval_labels["annex14_ofs"].isHidden())
        self.assertIn("Highest workload", self.dialog.label_olsModeDescription.text())
        self.assertEqual(self.dialog.label_olsInlineStatus.text(), "OLS ready.")
        self.assertTrue(self.dialog.label_olsInlineStatus.isHidden())
        self.assertEqual(self.dialog.groupBox_controllingOls.title(), "Generated Outputs")

    def test_ols_warning_is_shown_once_in_the_inline_status_area(self):
        self.dialog._update_ols_workflow_ui(
            dependency_status={"state": "warning", "summary": "Controlling OLS is experimental."},
            runway_count=1,
        )

        self.assertFalse(self.dialog.label_olsInlineStatus.isHidden())
        self.assertEqual(
            self.dialog.label_olsInlineStatus.text(),
            "Controlling OLS is experimental.",
        )
        self.assertNotIn("experimental", self.dialog.label_olsModeDescription.text().lower())

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

    def test_legacy_comparison_payload_cannot_disable_required_controlling_output(self):
        self.select_mode("modernisation_comparison")

        self.dialog._load_output_options({"generate_controlling_ols": False})

        self.assertTrue(self.dialog.checkBox_generateControllingOls.isChecked())
        self.assertFalse(self.dialog.checkBox_generateControllingOls.isEnabled())

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
        comparison = self.dialog._contour_interval_spinboxes["comparison_annex14_ofs"]
        baseline.setValue(8.0)
        comparison.setValue(6.0)
        options = self.dialog.get_contour_interval_options()
        builder = object.__new__(SafeguardingBuilder)
        builder.contour_intervals = options

        builder._contour_interval_ruleset_role = "baseline"
        self.assertEqual(builder._get_contour_interval("approach", 10.0), 8.0)
        builder._contour_interval_ruleset_role = "comparison"
        self.assertEqual(builder._get_contour_interval("annex14_ofs", 10.0), 6.0)

    def test_legacy_surface_intervals_seed_comparison_column_when_loading(self):
        self.dialog.set_contour_interval_options(
            {
                "default": {"primary": 50.0, "intermediate": 10.0},
                "annex14_ofs": {"primary": 40.0, "intermediate": 7.0},
            }
        )

        self.assertEqual(
            self.dialog._contour_interval_spinboxes["comparison_annex14_ofs"].value(),
            7.0,
        )

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

    def test_phase_progress_and_safe_cancel_state(self):
        self.dialog.begin_processing(10)
        self.dialog.set_processing_status("Solving controlling envelopes...", step=8, total_steps=10)

        self.assertTrue(self.dialog._processing_status_active)
        self.assertEqual(self.dialog._processing_progress_bar.minimum(), 0)
        self.assertEqual(self.dialog._processing_progress_bar.maximum(), 10)
        self.assertEqual(self.dialog._processing_progress_bar.value(), 8)
        self.assertFalse(self.dialog._processing_cancel_button.isHidden())

        self.dialog.request_processing_cancel()

        self.assertTrue(self.dialog.is_processing_cancel_requested())
        self.assertFalse(self.dialog._processing_cancel_button.isEnabled())
        self.assertIn("finishing the current phase", self.dialog.label_footer_status.text())

        self.dialog.clear_processing_status("Generation cancelled — completed layers were kept.")

        self.assertFalse(self.dialog._processing_status_active)
        self.assertFalse(self.dialog.is_processing_cancel_requested())
        self.assertTrue(self.dialog._processing_progress_bar.isHidden())
        self.assertEqual(
            self.dialog.label_footer_status.text(),
            "Generation cancelled — completed layers were kept.",
        )

    def test_builder_stops_at_checkpoint_after_cancel_request(self):
        builder = object.__new__(SafeguardingBuilder)
        builder.dlg = self.dialog
        self.dialog.begin_processing(10)
        self.dialog.request_processing_cancel()

        with patch.object(builder, "_finish_processing_cancelled") as finish_cancelled:
            should_continue = builder._processing_checkpoint("Next phase", 4, 10)

        self.assertFalse(should_continue)
        finish_cancelled.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
