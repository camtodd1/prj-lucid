"""Save, load, and clear helpers for dialog input state."""

import json
import os

from qgis.core import QgsMessageLog, Qgis  # type: ignore
from qgis.PyQt import QtCore, QtWidgets  # type: ignore
from qgis.PyQt.QtWidgets import (  # type: ignore
    QFileDialog,
    QMessageBox,
    QComboBox,
    QTableWidgetItem,
)

from .dialog_constants import (
    CONTOUR_INTERVAL_KEYS,
    CONTOUR_INTERVAL_KEY_DEFAULTS,
    DEFAULT_CONTOUR_INTERVAL,
    DEFAULT_PRIMARY_CONTOUR_INTERVAL,
    DEFAULT_OUTPUT_FORMAT,
    DIALOG_LOG_TAG,
    OUTPUT_FORMATS,
)

try:
    from ..frameworks.registry import DEFAULT_FRAMEWORK_ID, normalize_framework_id
    from ..rulesets.registry import DEFAULT_RULESET_ID, normalize_ruleset_id
except ImportError:
    from frameworks.registry import DEFAULT_FRAMEWORK_ID, normalize_framework_id  # type: ignore
    from rulesets.registry import DEFAULT_RULESET_ID, normalize_ruleset_id  # type: ignore


class PersistenceMixin:
    """Mixin for clearing, saving, and loading dialog state."""

    def _ruleset_combo_widget(self):
        combo = getattr(self, "ruleset_combo", None)
        try:
            if isinstance(combo, QComboBox):
                _ = combo.currentIndex()
                return combo
        except RuntimeError:
            pass
        combo = self.findChild(QComboBox, "comboBox_ruleset") if hasattr(self, "findChild") else None
        if isinstance(combo, QComboBox):
            try:
                _ = combo.currentIndex()
                return combo
            except RuntimeError:
                return None
        return None

    def _framework_combo_widget(self):
        combo = getattr(self, "framework_combo", None)
        try:
            if isinstance(combo, QComboBox):
                _ = combo.currentIndex()
                return combo
        except RuntimeError:
            pass
        combo = self.findChild(QComboBox, "comboBox_safeguarding_framework") if hasattr(self, "findChild") else None
        if isinstance(combo, QComboBox):
            try:
                _ = combo.currentIndex()
                return combo
            except RuntimeError:
                return None
        return None

    def _protected_airspace_policy_combo_widget(self):
        combo = getattr(self, "protected_airspace_policy_combo", None)
        try:
            if isinstance(combo, QComboBox):
                _ = combo.currentIndex()
                return combo
        except RuntimeError:
            pass
        combo = self.findChild(QComboBox, "comboBox_protected_airspace_policy") if hasattr(self, "findChild") else None
        if isinstance(combo, QComboBox):
            try:
                _ = combo.currentIndex()
                return combo
            except RuntimeError:
                return None
        return None

    def _baseline_ols_ruleset_combo_widget(self):
        combo = getattr(self, "baseline_ols_ruleset_combo", None)
        return combo if isinstance(combo, QComboBox) else None

    def _comparison_ols_ruleset_combo_widget(self):
        combo = getattr(self, "comparison_ols_ruleset_combo", None)
        return combo if isinstance(combo, QComboBox) else None

    def _pick_json_file(self, title: str, accept_mode: QFileDialog.AcceptMode, initial_path: str = "") -> str:
        """Use a Qt file dialog that behaves reliably inside the plugin shell."""
        file_filter = self.tr("JSON Files (*.json)")
        if accept_mode == QFileDialog.AcceptMode.AcceptOpen:
            file_path, _ = QFileDialog.getOpenFileName(
                self,
                title,
                "",
                file_filter,
            )
            return file_path

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            title,
            initial_path,
            file_filter,
        )
        return file_path

    def clear_all_inputs(self, confirm: bool = True) -> None:
        if confirm:
            reply = QMessageBox.question(
                self,
                self.tr("Confirm Clear"),
                self.tr("Clear all inputs and runway definitions?"),
                QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No,
                QtWidgets.QMessageBox.StandardButton.No,
            )
            if reply == QtWidgets.QMessageBox.StandardButton.No:
                return

        cns_table = self._table("table_cns_facility")
        if cns_table:
            cns_table.setRowCount(0)

        for name in [
            "lineEdit_airport_name",
            "lineEdit_iata_code",
            "lineEdit_arp_easting",
            "lineEdit_arp_northing",
            "lineEdit_arp_elevation",
            "lineEdit_met_easting",
            "lineEdit_met_northing",
            "lineEdit_met_elevation",
        ]:
            widget = self._line_edit(name)
            if widget:
                widget.clear()

        ruleset_combo = self._ruleset_combo_widget()
        if isinstance(ruleset_combo, QComboBox):
            idx = ruleset_combo.findData(DEFAULT_RULESET_ID)
            ruleset_combo.setCurrentIndex(idx if idx >= 0 else 0)
        framework_combo = self._framework_combo_widget()
        if isinstance(framework_combo, QComboBox):
            idx = framework_combo.findData(DEFAULT_FRAMEWORK_ID)
            framework_combo.setCurrentIndex(idx if idx >= 0 else 0)
        protected_airspace_combo = self._protected_airspace_policy_combo_widget()
        if isinstance(protected_airspace_combo, QComboBox):
            idx = protected_airspace_combo.findData("ruleset_aligned")
            protected_airspace_combo.setCurrentIndex(idx if idx >= 0 else 0)
        if hasattr(self, "_set_ols_ruleset_selection"):
            self._set_ols_ruleset_selection(DEFAULT_RULESET_ID, "")

        for index in list(self._runway_groups.keys()):
            self._remove_runway_group_internal(index)
        self._runway_groups.clear()
        self._runway_id_counter = 0

        if self.scroll_area_layout is not None:
            self.add_runway_group()
        else:
            QgsMessageLog.logMessage(
                "Warn (Clear): Layout missing, couldn't add runway back.",
                DIALOG_LOG_TAG,
                level=Qgis.Warning,
            )

        self._reset_output_options()
        if hasattr(self, "_reset_agl_options"):
            self._reset_agl_options()
        self._update_dialog_height()
        if hasattr(self, "update_dialog_status"):
            self.update_dialog_status()

    def save_input_data(self):
        icao_code = self._line_text("lineEdit_airport_name").strip().upper()
        suggested_filename = f"{icao_code}_safeguarding_inputs.json" if icao_code else "safeguarding_inputs.json"
        file_path = self._pick_json_file(self.tr("Save Inputs"), QFileDialog.AcceptMode.AcceptSave, suggested_filename)
        if not file_path:
            return
        if not file_path.lower().endswith(".json"):
            file_path += ".json"

        data_to_save = self._build_save_payload(icao_code)
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(data_to_save, f, indent=4, ensure_ascii=False)
            QMessageBox.information(
                self,
                self.tr("Save Successful"),
                self.tr("Input data saved to:\n{path}").format(path=file_path),
            )
        except Exception as e:
            error_msg = self.tr("Error saving data:") + f"\n{type(e).__name__}: {e}"
            QgsMessageLog.logMessage(f"Save error {file_path}: {e}", DIALOG_LOG_TAG, level=Qgis.Critical)
            QMessageBox.critical(self, self.tr("Save Error"), error_msg)

    def load_input_data(self):
        if self._has_existing_input_data():
            reply = QtWidgets.QMessageBox.question(
                self,
                self.tr("Confirm Load"),
                self.tr("This will clear current inputs and load data from the selected file. Continue?"),
                QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No,
                QtWidgets.QMessageBox.StandardButton.No,
            )
            if reply == QtWidgets.QMessageBox.StandardButton.No:
                return

        file_path = self._pick_json_file(self.tr("Load Inputs"), QFileDialog.AcceptMode.AcceptOpen)
        if not file_path:
            return

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                loaded_data = json.load(f)
            self._validate_loaded_payload(loaded_data)
            self.clear_all_inputs(confirm=False)
            self._apply_loaded_payload(loaded_data)
            self._update_dialog_height()
            if hasattr(self, "queue_current_airport_lookup"):
                self.queue_current_airport_lookup()
            if hasattr(self, "update_dialog_status"):
                self.update_dialog_status()
        except (IOError, json.JSONDecodeError, ValueError) as e:
            self._handle_load_error(file_path, e, unexpected=False)
        except Exception as e:
            self._handle_load_error(file_path, e, unexpected=True)

    def _build_save_payload(self, icao_code: str):
        ruleset_combo = self._ruleset_combo_widget()
        framework_combo = self._framework_combo_widget()
        protected_airspace_combo = self._protected_airspace_policy_combo_widget()
        design_standard = ruleset_combo.currentData() if ruleset_combo else DEFAULT_RULESET_ID
        protected_airspace_policy = (
            protected_airspace_combo.currentData() if protected_airspace_combo else "ruleset_aligned"
        )
        baseline_ols_ruleset = design_standard
        comparison_ols_ruleset = ""
        if hasattr(self, "_current_ols_ruleset_ids"):
            baseline_ols_ruleset, comparison_ols_ruleset = self._current_ols_ruleset_ids()
        data_to_save = {
            "icao_code": icao_code,
            "iata_code": self._line_text("lineEdit_iata_code").strip().upper(),
            "arp_easting": self._line_text("lineEdit_arp_easting"),
            "arp_northing": self._line_text("lineEdit_arp_northing"),
            "arp_elevation": self._line_text("lineEdit_arp_elevation"),
            "met_easting": self._line_text("lineEdit_met_easting"),
            "met_northing": self._line_text("lineEdit_met_northing"),
            "met_elevation": self._line_text("lineEdit_met_elevation"),
            "design_standard": design_standard,
            "ruleset": design_standard,
            "safeguarding_framework": framework_combo.currentData() if framework_combo else DEFAULT_FRAMEWORK_ID,
            "protected_airspace_policy": protected_airspace_policy,
            "baseline_ols_ruleset": baseline_ols_ruleset,
            "comparison_ols_ruleset": comparison_ols_ruleset or None,
            "runways": [self._runway_groups[idx].get_input_data() for idx in sorted(self._runway_groups.keys())],
            "cns_facilities": self._get_cns_save_rows(),
        }
        if hasattr(self, "_get_agl_save_options"):
            data_to_save["agl_options"] = self._get_agl_save_options()
        output_mode = "file" if self.radioFileOutput.isChecked() else "memory"
        data_to_save["output_options"] = {
            "mode": output_mode,
            "path": self.fileWidgetOutputPath.filePath().strip(),
            "format": self.comboOutputFormat.currentText(),
        }
        if hasattr(self, "get_contour_interval_options"):
            data_to_save["output_options"]["contour_intervals"] = self.get_contour_interval_options()
        return data_to_save

    def _get_cns_save_rows(self):
        cns_rows = []
        cns_table = self._table("table_cns_facility")
        if not cns_table:
            return cns_rows
        for row in range(cns_table.rowCount()):
            try:
                combo = cns_table.cellWidget(row, 0)
                type_txt = combo.currentText() if isinstance(combo, QComboBox) else ""
                cns_rows.append(
                    {
                        "type": type_txt,
                        "easting_x": self._table_text(cns_table, row, 1),
                        "northing_y": self._table_text(cns_table, row, 2),
                        "elevation": self._table_text(cns_table, row, 3),
                    }
                )
            except Exception as e:
                QgsMessageLog.logMessage(
                    f"Save CNS row {row+1} error: {e}",
                    DIALOG_LOG_TAG,
                    level=Qgis.Warning,
                )
        return cns_rows

    def _has_existing_input_data(self) -> bool:
        global_widgets = [
            self._line_edit(name)
            for name in [
                "lineEdit_airport_name",
                "lineEdit_iata_code",
                "lineEdit_arp_easting",
                "lineEdit_arp_northing",
                "lineEdit_arp_elevation",
                "lineEdit_met_easting",
                "lineEdit_met_northing",
                "lineEdit_met_elevation",
            ]
        ]
        if any(widget and widget.text() for widget in global_widgets):
            return True
        ruleset_combo = self._ruleset_combo_widget()
        if isinstance(ruleset_combo, QComboBox) and ruleset_combo.currentData() not in {None, DEFAULT_RULESET_ID}:
            return True
        framework_combo = self._framework_combo_widget()
        if isinstance(framework_combo, QComboBox) and framework_combo.currentData() not in {None, DEFAULT_FRAMEWORK_ID}:
            return True
        protected_airspace_combo = self._protected_airspace_policy_combo_widget()
        if (
            isinstance(protected_airspace_combo, QComboBox)
            and protected_airspace_combo.currentData() not in {None, "ruleset_aligned"}
        ):
            return True
        if hasattr(self, "_current_ols_ruleset_ids"):
            baseline_ols_ruleset, comparison_ols_ruleset = self._current_ols_ruleset_ids()
            if baseline_ols_ruleset != DEFAULT_RULESET_ID or comparison_ols_ruleset:
                return True
        if any(self._runway_has_existing_input(group.get_input_data()) for group in self._runway_groups.values()):
            return True
        cns_table = self._table("table_cns_facility")
        if cns_table and cns_table.rowCount() > 0:
            return True
        if hasattr(self, "_agl_options_changed") and self._agl_options_changed():
            return True
        return self._output_options_changed()

    def _runway_has_existing_input(self, runway_data) -> bool:
        default_fields = {
            "takeoff_available_1",
            "takeoff_available_2",
            "landing_available_1",
            "landing_available_2",
            "lahso_applied_1",
            "lahso_applied_2",
        }
        return any(str(value).strip() for key, value in runway_data.items() if key not in default_fields)

    def _validate_loaded_payload(self, loaded_data) -> None:
        if not isinstance(loaded_data, dict):
            raise ValueError("Invalid format: Top level is not a dictionary.")
        missing = [key for key in ["icao_code", "runways"] if key not in loaded_data]
        if missing:
            raise ValueError(f"Missing required keys: {', '.join(missing)}")
        if not isinstance(loaded_data.get("runways"), list):
            raise ValueError("Invalid format: 'runways' key is not a list.")
        if "cns_facilities" in loaded_data and not isinstance(loaded_data.get("cns_facilities"), list):
            raise ValueError("Invalid format: 'cns_facilities' key exists but is not a list.")

    def _apply_loaded_payload(self, loaded_data) -> None:
        self._set_line_text("lineEdit_airport_name", loaded_data.get("icao_code", ""))
        self._set_line_text("lineEdit_iata_code", loaded_data.get("iata_code", ""))
        self._set_line_text("lineEdit_arp_easting", loaded_data.get("arp_easting", ""))
        self._set_line_text("lineEdit_arp_northing", loaded_data.get("arp_northing", ""))
        self._set_line_text("lineEdit_arp_elevation", loaded_data.get("arp_elevation", ""))
        self._set_line_text("lineEdit_met_easting", loaded_data.get("met_easting", ""))
        self._set_line_text("lineEdit_met_northing", loaded_data.get("met_northing", ""))
        self._set_line_text("lineEdit_met_elevation", loaded_data.get("met_elevation", ""))
        ruleset_combo = self._ruleset_combo_widget()
        if isinstance(ruleset_combo, QComboBox):
            ruleset_id = normalize_ruleset_id(
                loaded_data.get("design_standard", loaded_data.get("ruleset", DEFAULT_RULESET_ID))
            )
            idx = ruleset_combo.findData(ruleset_id)
            ruleset_combo.setCurrentIndex(idx if idx >= 0 else 0)
        framework_combo = self._framework_combo_widget()
        if isinstance(framework_combo, QComboBox):
            framework_id = normalize_framework_id(loaded_data.get("safeguarding_framework", DEFAULT_FRAMEWORK_ID))
            idx = framework_combo.findData(framework_id)
            framework_combo.setCurrentIndex(idx if idx >= 0 else 0)
        protected_airspace_combo = self._protected_airspace_policy_combo_widget()
        if isinstance(protected_airspace_combo, QComboBox):
            policy_id = loaded_data.get("protected_airspace_policy", "ruleset_aligned")
            idx = protected_airspace_combo.findData(policy_id)
            protected_airspace_combo.setCurrentIndex(idx if idx >= 0 else 0)
        if hasattr(self, "_set_ols_ruleset_selection"):
            baseline_ols_ruleset = loaded_data.get("baseline_ols_ruleset")
            comparison_ols_ruleset = loaded_data.get("comparison_ols_ruleset")
            if not baseline_ols_ruleset:
                policy_id = loaded_data.get("protected_airspace_policy", "ruleset_aligned")
                baseline_ols_ruleset = (
                    "icao_annex14_vol1_modernised_ofs_oes"
                    if policy_id == "future_annex14_ofs_oes"
                    else loaded_data.get(
                        "design_standard",
                        loaded_data.get("ruleset", DEFAULT_RULESET_ID),
                    )
                )
                if policy_id == "modernisation_comparison":
                    comparison_ols_ruleset = "icao_annex14_vol1_modernised_ofs_oes"
            self._set_ols_ruleset_selection(
                normalize_ruleset_id(baseline_ols_ruleset),
                normalize_ruleset_id(comparison_ols_ruleset)
                if comparison_ols_ruleset
                else "",
            )
        self._load_runway_rows(loaded_data.get("runways", []))
        if hasattr(self, "_load_agl_options"):
            self._load_agl_options(loaded_data.get("agl_options", {}))
        self._load_cns_rows(loaded_data.get("cns_facilities", []))
        self._load_output_options(loaded_data.get("output_options", {}))

    def _load_runway_rows(self, loaded_runways_list) -> None:
        if loaded_runways_list:
            first_index = min(self._runway_groups.keys()) if self._runway_groups else None
            first_group = self._runway_groups.get(first_index) if first_index is not None else None
            if first_group:
                first_group.set_input_data(self._with_runway_defaults(loaded_runways_list[0]))
            else:
                QgsMessageLog.logMessage(
                    "Load Error: First runway group missing after clear.",
                    DIALOG_LOG_TAG,
                    level=Qgis.Warning,
                )

            for runway_data_item in loaded_runways_list[1:]:
                try:
                    self.add_runway_group()
                    new_group = self._runway_groups.get(self._runway_id_counter)
                    if new_group:
                        new_group.set_input_data(self._with_runway_defaults(runway_data_item))
                    else:
                        QgsMessageLog.logMessage(
                            f"Load Error: Group {self._runway_id_counter} missing after add.",
                            DIALOG_LOG_TAG,
                            level=Qgis.Warning,
                        )
                except Exception as e_loop:
                    QgsMessageLog.logMessage(
                        f"Load Error processing runway item: {e_loop}",
                        DIALOG_LOG_TAG,
                        level=Qgis.Warning,
                    )
        elif self._runway_groups:
            self.update_runway_calculations(min(self._runway_groups.keys()))

    def _load_cns_rows(self, loaded_cns_list) -> None:
        cns_table = self._table("table_cns_facility")
        if not cns_table or not loaded_cns_list:
            return
        cns_table.setRowCount(0)
        for item_data in loaded_cns_list:
            if not isinstance(item_data, dict):
                QgsMessageLog.logMessage(
                    f"Load CNS Warn: Skipping non-dict: {item_data}",
                    DIALOG_LOG_TAG,
                    level=Qgis.Warning,
                )
                continue
            try:
                row = cns_table.rowCount()
                cns_table.insertRow(row)
                combo = QComboBox()
                combo.addItems([""] + self.CNS_FACILITY_TYPES)
                idx = combo.findText(
                    item_data.get("type", ""),
                    QtCore.Qt.MatchFlag.MatchFixedString,
                )
                combo.setCurrentIndex(idx if idx >= 0 else 0)
                cns_table.setCellWidget(row, 0, combo)
                cns_table.setItem(row, 1, QTableWidgetItem(item_data.get("easting_x", "")))
                cns_table.setItem(row, 2, QTableWidgetItem(item_data.get("northing_y", "")))
                cns_table.setItem(row, 3, QTableWidgetItem(item_data.get("elevation", "")))
            except Exception as e:
                QgsMessageLog.logMessage(
                    f"Load CNS error item {item_data}: {e}",
                    DIALOG_LOG_TAG,
                    level=Qgis.Warning,
                )

    def _load_output_options(self, output_options) -> None:
        if not isinstance(output_options, dict):
            return
        output_mode = output_options.get("mode", "memory")
        if output_mode == "file" and hasattr(self, "radioFileOutput"):
            self.radioFileOutput.setChecked(True)
        elif hasattr(self, "radioMemoryOutput"):
            self.radioMemoryOutput.setChecked(True)

        output_format = output_options.get("format", DEFAULT_OUTPUT_FORMAT)
        if hasattr(self, "comboOutputFormat"):
            idx = self.comboOutputFormat.findText(output_format, QtCore.Qt.MatchFlag.MatchFixedString)
            self.comboOutputFormat.setCurrentIndex(idx if idx >= 0 else 0)

        output_path = output_options.get("path", "")
        if output_path and os.path.isfile(output_path):
            output_path = os.path.dirname(output_path)
        if hasattr(self, "fileWidgetOutputPath"):
            self.fileWidgetOutputPath.setFilePath(output_path)

        if hasattr(self, "set_contour_interval_options"):
            self.set_contour_interval_options(output_options.get("contour_intervals", {}))
        if hasattr(self, "_update_ols_workflow_ui"):
            self._update_ols_workflow_ui()
        self._on_output_option_changed()

    def _reset_output_options(self) -> None:
        if hasattr(self, "radioMemoryOutput"):
            self.radioMemoryOutput.setChecked(True)
        if hasattr(self, "fileWidgetOutputPath"):
            self.fileWidgetOutputPath.setFilePath("")
        if hasattr(self, "comboOutputFormat") and DEFAULT_OUTPUT_FORMAT in OUTPUT_FORMATS:
            self.comboOutputFormat.setCurrentText(DEFAULT_OUTPUT_FORMAT)
        if hasattr(self, "set_contour_interval_options"):
            self.set_contour_interval_options({})
        self._on_output_option_changed()

    def _output_options_changed(self) -> bool:
        if hasattr(self, "radioFileOutput") and self.radioFileOutput.isChecked():
            return True
        if hasattr(self, "fileWidgetOutputPath") and self.fileWidgetOutputPath.filePath().strip():
            return True
        if hasattr(self, "get_contour_interval_options"):
            contour_options = self.get_contour_interval_options()
            default_options = contour_options.get("default", {})
            if not isinstance(default_options, dict):
                default_options = {"intermediate": default_options}
            if (
                abs(float(default_options.get("primary", DEFAULT_PRIMARY_CONTOUR_INTERVAL)) - DEFAULT_PRIMARY_CONTOUR_INTERVAL)
                > 1e-9
            ):
                return True
            if abs(float(default_options.get("intermediate", DEFAULT_CONTOUR_INTERVAL)) - DEFAULT_CONTOUR_INTERVAL) > 1e-9:
                return True
            for key in CONTOUR_INTERVAL_KEYS:
                value = contour_options.get(key, {})
                if not isinstance(value, dict):
                    value = {"intermediate": value}
                key_defaults = CONTOUR_INTERVAL_KEY_DEFAULTS.get(key, {})
                expected_primary = key_defaults.get("primary", DEFAULT_PRIMARY_CONTOUR_INTERVAL)
                expected_intermediate = key_defaults.get("intermediate", DEFAULT_CONTOUR_INTERVAL)
                if abs(float(value.get("primary", expected_primary)) - expected_primary) > 1e-9:
                    return True
                if abs(float(value.get("intermediate", expected_intermediate)) - expected_intermediate) > 1e-9:
                    return True
        return False

    def _handle_load_error(self, file_path: str, error: Exception, unexpected: bool) -> None:
        error_details = f"{type(error).__name__}: {error}"
        if unexpected:
            log_msg = f"Unexpected load error ({file_path}): {error_details}"
            user_msg = (
                self.tr("An unexpected error occurred during loading:") + f"\n\n{self.tr('Error')}: {error_details}"
            )
        else:
            log_msg = f"Load Error ({file_path}): {error_details}"
            user_msg = (
                self.tr("Error loading data from file:") + f"\n{file_path}\n\n{self.tr('Error')}: {error_details}"
            )
        QgsMessageLog.logMessage(log_msg, DIALOG_LOG_TAG, level=Qgis.Critical)
        QMessageBox.critical(self, self.tr("Load Error"), user_msg)
        try:
            self.clear_all_inputs(confirm=False)
        except Exception as clear_err:
            QgsMessageLog.logMessage(
                f"Error during post-load-error cleanup: {clear_err}",
                DIALOG_LOG_TAG,
                level=Qgis.Critical,
            )

    def _with_runway_defaults(self, runway_data):
        runway_data.setdefault("runway_end_elev_1", runway_data.get("thr_elev_1", ""))
        runway_data.setdefault("runway_end_elev_2", runway_data.get("thr_elev_2", ""))
        runway_data.setdefault("threshold_elev_1", "")
        runway_data.setdefault("threshold_elev_2", "")
        runway_data.setdefault("thr_pre_area_1", "")
        runway_data.setdefault("thr_pre_area_2", "")
        runway_data.setdefault("thr_displaced_1", "")
        runway_data.setdefault("thr_displaced_2", "")
        runway_data.setdefault("clearway1_len", "")
        runway_data.setdefault("clearway2_len", "")
        runway_data.setdefault("stopway1_len", "")
        runway_data.setdefault("stopway2_len", "")
        runway_data.setdefault("tora_override_1", "")
        runway_data.setdefault("tora_override_2", "")
        runway_data.setdefault("toda_override_1", "")
        runway_data.setdefault("toda_override_2", "")
        runway_data.setdefault("asda_override_1", "")
        runway_data.setdefault("asda_override_2", "")
        runway_data.setdefault("lda_override_1", "")
        runway_data.setdefault("lda_override_2", "")
        runway_data.setdefault("adg", runway_data.get("design_group", ""))
        runway_data.setdefault("design_group", runway_data.get("adg", ""))
        runway_data.setdefault("surface_category", "")
        runway_data.setdefault("surface_material", "")
        runway_data.setdefault("takeoff_available_1", True)
        runway_data.setdefault("takeoff_available_2", True)
        runway_data.setdefault("landing_available_1", True)
        runway_data.setdefault("landing_available_2", True)
        runway_data.setdefault("lahso_applied_1", False)
        runway_data.setdefault("lahso_applied_2", False)
        return runway_data

    def _line_edit(self, name: str):
        return getattr(self, name, self.findChild(QtWidgets.QLineEdit, name))

    def _line_text(self, name: str) -> str:
        widget = self._line_edit(name)
        return widget.text() if widget else ""

    def _set_line_text(self, name: str, value: str) -> None:
        widget = self._line_edit(name)
        if widget:
            widget.setText(value)

    def _table(self, name: str):
        return getattr(self, name, self.findChild(QtWidgets.QTableWidget, name))

    def _table_text(self, table, row: int, column: int) -> str:
        item = table.item(row, column)
        return item.text() if item else ""
