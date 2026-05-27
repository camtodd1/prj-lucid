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
    DEFAULT_OUTPUT_FORMAT,
    DIALOG_LOG_TAG,
    OUTPUT_FORMATS,
)


class PersistenceMixin:
    """Mixin for clearing, saving, and loading dialog state."""

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
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            self.tr("Save Inputs"),
            suggested_filename,
            self.tr("JSON Files (*.json)"),
        )
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

        file_path, _ = QFileDialog.getOpenFileName(self, self.tr("Load Inputs"), "", self.tr("JSON Files (*.json)"))
        if not file_path:
            return

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                loaded_data = json.load(f)
            self._validate_loaded_payload(loaded_data)
            self.clear_all_inputs(confirm=False)
            self._apply_loaded_payload(loaded_data)
            self._update_dialog_height()
            if hasattr(self, "update_dialog_status"):
                self.update_dialog_status()
        except (IOError, json.JSONDecodeError, ValueError) as e:
            self._handle_load_error(file_path, e, unexpected=False)
        except Exception as e:
            self._handle_load_error(file_path, e, unexpected=True)

    def _build_save_payload(self, icao_code: str):
        data_to_save = {
            "icao_code": icao_code,
            "arp_easting": self._line_text("lineEdit_arp_easting"),
            "arp_northing": self._line_text("lineEdit_arp_northing"),
            "arp_elevation": self._line_text("lineEdit_arp_elevation"),
            "met_easting": self._line_text("lineEdit_met_easting"),
            "met_northing": self._line_text("lineEdit_met_northing"),
            "met_elevation": self._line_text("lineEdit_met_elevation"),
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
            "dissolve": self.checkBox_dissolveLayers.isChecked() if hasattr(self, "checkBox_dissolveLayers") else False,
        }
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
        self._set_line_text("lineEdit_arp_easting", loaded_data.get("arp_easting", ""))
        self._set_line_text("lineEdit_arp_northing", loaded_data.get("arp_northing", ""))
        self._set_line_text("lineEdit_arp_elevation", loaded_data.get("arp_elevation", ""))
        self._set_line_text("lineEdit_met_easting", loaded_data.get("met_easting", ""))
        self._set_line_text("lineEdit_met_northing", loaded_data.get("met_northing", ""))
        self._set_line_text("lineEdit_met_elevation", loaded_data.get("met_elevation", ""))
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

        if hasattr(self, "checkBox_dissolveLayers"):
            self.checkBox_dissolveLayers.setChecked(bool(output_options.get("dissolve", False)))
        self._on_output_option_changed()

    def _reset_output_options(self) -> None:
        if hasattr(self, "radioMemoryOutput"):
            self.radioMemoryOutput.setChecked(True)
        if hasattr(self, "fileWidgetOutputPath"):
            self.fileWidgetOutputPath.setFilePath("")
        if hasattr(self, "comboOutputFormat") and DEFAULT_OUTPUT_FORMAT in OUTPUT_FORMATS:
            self.comboOutputFormat.setCurrentText(DEFAULT_OUTPUT_FORMAT)
        if hasattr(self, "checkBox_dissolveLayers"):
            self.checkBox_dissolveLayers.setChecked(False)
        self._on_output_option_changed()

    def _output_options_changed(self) -> bool:
        if hasattr(self, "radioFileOutput") and self.radioFileOutput.isChecked():
            return True
        if hasattr(self, "fileWidgetOutputPath") and self.fileWidgetOutputPath.filePath().strip():
            return True
        if hasattr(self, "checkBox_dissolveLayers") and self.checkBox_dissolveLayers.isChecked():
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
        if not runway_data.get("stopway1_len") and runway_data.get("thr_pre_area_1"):
            runway_data["stopway1_len"] = runway_data.get("thr_pre_area_1")
        if not runway_data.get("stopway2_len") and runway_data.get("thr_pre_area_2"):
            runway_data["stopway2_len"] = runway_data.get("thr_pre_area_2")
        runway_data.setdefault("surface_category", "")
        runway_data.setdefault("surface_material", "")
        runway_data.setdefault("takeoff_available_1", True)
        runway_data.setdefault("takeoff_available_2", True)
        runway_data.setdefault("landing_available_1", True)
        runway_data.setdefault("landing_available_2", True)
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
