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
        combo = self.dialog.protected_airspace_policy_combo
        combo.setCurrentIndex(combo.findData(mode))
        self.dialog._update_ols_workflow_ui(
            dependency_status={"state": "ready", "summary": "OLS ready."},
            runway_count=2,
        )

    def test_persisted_policy_selector_is_presented_on_ols_tab(self):
        combo = self.dialog.protected_airspace_policy_combo

        self.assertIs(combo.parentWidget(), self.dialog.groupBox_olsWorkflow)
        self.assertTrue(self.dialog.label_protected_airspace_policy.isHidden())
        self.assertEqual(combo.itemData(0), "ruleset_aligned")
        self.assertEqual(combo.itemData(1), "future_annex14_ofs_oes")
        self.assertEqual(combo.itemData(2), "modernisation_comparison")

    def test_baseline_mode_hides_future_family_rows(self):
        self.select_mode("ruleset_aligned")

        self.assertTrue(self.dialog.frame_olsFamilyExplanation.isHidden())
        self.assertFalse(self.dialog._contour_interval_labels["approach"].isHidden())
        self.assertTrue(self.dialog._contour_interval_labels["annex14_ofs"].isHidden())
        self.assertTrue(self.dialog.checkBox_generateControllingOls.isEnabled())

    def test_future_mode_shows_only_ofs_oes_family_rows(self):
        self.select_mode("future_annex14_ofs_oes")

        self.assertFalse(self.dialog.frame_olsFamilyExplanation.isHidden())
        self.assertEqual(self.dialog.label_olsOfsTitle.text(), "OFS — protected airspace")
        self.assertIn("Obstacle-free surface", self.dialog.label_olsOfsDetail.text())
        self.assertEqual(self.dialog.label_olsOesTitle.text(), "OES — assessment trigger")
        self.assertIn("not an approval limit", self.dialog.label_olsOesDetail.text())
        self.assertTrue(self.dialog._contour_interval_labels["approach"].isHidden())
        self.assertFalse(self.dialog._contour_interval_labels["annex14_ofs"].isHidden())
        self.assertFalse(self.dialog._contour_interval_labels["annex14_oes"].isHidden())

    def test_comparison_mode_requires_controlling_output_and_shows_all_rows(self):
        self.dialog.checkBox_generateControllingOls.setChecked(False)
        self.select_mode("modernisation_comparison")

        self.assertTrue(self.dialog.checkBox_generateControllingOls.isChecked())
        self.assertFalse(self.dialog.checkBox_generateControllingOls.isEnabled())
        self.assertFalse(self.dialog._contour_interval_labels["approach"].isHidden())
        self.assertFalse(self.dialog._contour_interval_labels["annex14_ofs"].isHidden())
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
            self.dialog.widgetContourOverrides,
        )

        self.dialog.toolButtonContourOverrides.setChecked(True)

        self.assertFalse(self.dialog.widgetContourOverrides.isHidden())

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
