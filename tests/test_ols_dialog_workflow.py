import sys
import unittest
from pathlib import Path

from qgis.PyQt import QtWidgets


WORKSPACE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORKSPACE.parent))

from safeguarding_builder.safeguarding_builder_dialog import SafeguardingBuilderDialog


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
        self.assertIn("Highest workload", self.dialog.label_olsWorkload.text())
        self.assertEqual(self.dialog.label_olsInlineStatus.text(), "OLS ready.")

    def test_legacy_comparison_payload_cannot_disable_required_controlling_output(self):
        self.select_mode("modernisation_comparison")

        self.dialog._load_output_options({"generate_controlling_ols": False})

        self.assertTrue(self.dialog.checkBox_generateControllingOls.isChecked())
        self.assertFalse(self.dialog.checkBox_generateControllingOls.isEnabled())


if __name__ == "__main__":
    unittest.main()
