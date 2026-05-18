# -*- coding: utf-8 -*-
# safeguarding_builder_dialog.py
"""
Dialog class for the Safeguarding Builder QGIS plugin.
Handles user input for airport, ARP, runway, and CNS data.
Dynamically adds/removes runway groups using a helper class
and performs real-time calculations for display.
CNS coordinates are assumed to be in the current Project CRS.
"""

import math
import os
from typing import List, Optional, Dict, Any, Tuple

# --- QGIS Imports ---
from qgis.core import (  # type: ignore
    QgsMessageLog,
    Qgis,
    QgsPointXY,
    QgsProject,
    QgsCoordinateReferenceSystem,
)
from qgis.PyQt import uic, QtWidgets, QtGui, QtCore  # type: ignore
from qgis.PyQt.QtWidgets import (  # type: ignore
    QMessageBox,
)

try:
    from .dialog.constants import (
        CALC_PLACEHOLDER,
        NA_PLACEHOLDER,
        ENTER_COORDS_MSG,
        INVALID_COORDS_MSG,
        CALC_ERROR_MSG,
        SAME_POINT_MSG,
        NEAR_POINTS_MSG,
        WIDGET_MISSING_MSG,
        DIALOG_LOG_TAG,
        OUTPUT_FORMATS,
        DEFAULT_OUTPUT_FORMAT,
    )
    from .dialog.runway_group import RunwayWidgetGroup
    from .dialog.output_options import OutputOptionsMixin
    from .dialog.cns_table import CnsTableMixin
    from .dialog.persistence import PersistenceMixin
except ImportError:
    from dialog.constants import (  # type: ignore
        CALC_PLACEHOLDER,
        NA_PLACEHOLDER,
        ENTER_COORDS_MSG,
        INVALID_COORDS_MSG,
        CALC_ERROR_MSG,
        SAME_POINT_MSG,
        NEAR_POINTS_MSG,
        WIDGET_MISSING_MSG,
        DIALOG_LOG_TAG,
        OUTPUT_FORMATS,
        DEFAULT_OUTPUT_FORMAT,
    )
    from dialog.runway_group import RunwayWidgetGroup  # type: ignore
    from dialog.output_options import OutputOptionsMixin  # type: ignore
    from dialog.cns_table import CnsTableMixin  # type: ignore
    from dialog.persistence import PersistenceMixin  # type: ignore

# Load the UI class from the .ui file
FORM_CLASS, _ = uic.loadUiType(
    os.path.join(os.path.dirname(__file__), "safeguarding_builder_dialog_base.ui")
)

# =========================================================================
# == Main Dialog Class
# =========================================================================
class SafeguardingBuilderDialog(
    OutputOptionsMixin,
    CnsTableMixin,
    PersistenceMixin,
    QtWidgets.QDialog,
    FORM_CLASS,
):
    """Dialog class for user input."""

    def __init__(self, parent=None):
        """Constructor."""
        super().__init__(parent)
        self.setupUi(self)

        self._runway_id_counter = 0
        self._runway_groups: Dict[int, RunwayWidgetGroup] = {}
        self.scroll_area_layout: Optional[QtWidgets.QVBoxLayout] = None

        # --- Scroll Area Setup ---
        scroll_area = self.findChild(QtWidgets.QScrollArea, "scrollArea_runways")
        if scroll_area:
            scroll_area.setWidgetResizable(True)
            scroll_content_widget = scroll_area.widget()
            if scroll_content_widget:
                layout = scroll_content_widget.layout()
                if not layout:
                    layout = QtWidgets.QVBoxLayout(scroll_content_widget)
                    scroll_content_widget.setLayout(layout)
                if isinstance(layout, QtWidgets.QVBoxLayout):
                    self.scroll_area_layout = layout
                else:
                    QgsMessageLog.logMessage(
                        "Critical: Scroll area content widget layout is not QVBoxLayout.",
                        DIALOG_LOG_TAG,
                        level=Qgis.Critical,
                    )
                    self.scroll_area_layout = layout  # Assign anyway
            else:
                QgsMessageLog.logMessage(
                    "Critical: Scroll area content widget missing.",
                    DIALOG_LOG_TAG,
                    level=Qgis.Critical,
                )
        else:
            QgsMessageLog.logMessage(
                "Critical: scrollArea_runways not found in UI.",
                DIALOG_LOG_TAG,
                level=Qgis.Critical,
            )

        add_runway_button = self.findChild(
            QtWidgets.QPushButton, "pushButton_add_runway"
        )
        if not self.scroll_area_layout:
            QgsMessageLog.logMessage(
                "Critical: Scroll area layout unavailable.",
                DIALOG_LOG_TAG,
                level=Qgis.Critical,
            )
            if add_runway_button:
                add_runway_button.setEnabled(False)
                add_runway_button.setToolTip("Layout missing.")

        # --- Setup Coordinate Validators ---
        self.coord_validator = QtGui.QDoubleValidator()
        self.coord_validator.setNotation(
            QtGui.QDoubleValidator.Notation.StandardNotation
        )
        self.numeric_validator = QtGui.QDoubleValidator()
        self.numeric_validator.setNotation(
            QtGui.QDoubleValidator.Notation.StandardNotation
        )

        self._setup_arp_validators(self.coord_validator, self.numeric_validator)
        self._connect_global_controls()

        # --- Connect Action Buttons ---
        clear_button = self.findChild(QtWidgets.QPushButton, "pushButton_clear_all")
        save_button = self.findChild(QtWidgets.QPushButton, "pushButton_save_data")
        load_button = self.findChild(QtWidgets.QPushButton, "pushButton_load_data")
        if clear_button:
            clear_button.clicked.connect(self.clear_all_inputs)
        if save_button:
            save_button.clicked.connect(self.save_input_data)
        if load_button:
            load_button.clicked.connect(self.load_input_data)

        self._setup_cns_manual_entry()

        self._setup_output_options_ui_connections()

        if self.scroll_area_layout:
            self.add_runway_group()  # Add the first group
        else:
            QgsMessageLog.logMessage(
                "Warning: Could not add initial runway group (layout missing).",
                DIALOG_LOG_TAG,
                level=Qgis.Warning,
            )

        QtCore.QTimer.singleShot(0, self._update_dialog_height)

    # --- Initialization Helpers ---
    def _setup_arp_validators(
        self,
        coord_validator: QtGui.QDoubleValidator,
        numeric_validator: QtGui.QDoubleValidator,
    ):
        """Finds ARP/MET widgets and applies validators."""
        widgets_to_validate = [
            ("lineEdit_arp_easting", coord_validator),
            ("lineEdit_arp_northing", coord_validator),
            ("lineEdit_arp_elevation", numeric_validator),
            ("lineEdit_met_easting", coord_validator),
            ("lineEdit_met_northing", coord_validator),
            ("lineEdit_met_elevation", numeric_validator),
        ]
        tooltips = {
            "lineEdit_arp_easting": "Airport Reference Point (ARP) Easting Coordinate",
            "lineEdit_arp_northing": "Airport Reference Point (ARP) Northing Coordinate",
            "lineEdit_arp_elevation": "Airport Reference Point (ARP) Elevation (AMSL)",
            "lineEdit_met_easting": "MET Station Easting Coordinate (Optional)",
            "lineEdit_met_northing": "MET Station Northing Coordinate (Optional)",
            "lineEdit_met_elevation": "MET Station Elevation (AMSL, Optional)",
        }
        placeholders = {
            "lineEdit_arp_easting": "e.g., 455000.00",
            "lineEdit_arp_northing": "e.g., 5772000.00",
            "lineEdit_arp_elevation": "e.g., 150.0",
            "lineEdit_met_easting": "e.g., 455100.00",
            "lineEdit_met_northing": "e.g., 5772100.00",
            "lineEdit_met_elevation": "e.g., 150.0",
        }
        for name, validator in widgets_to_validate:
            widget = getattr(self, name, self.findChild(QtWidgets.QLineEdit, name))
            if widget:
                widget.setValidator(validator)
                widget.setToolTip(tooltips.get(name, ""))
                widget.setPlaceholderText(placeholders.get(name, ""))
            else:
                QgsMessageLog.logMessage(
                    f"Warning: QLineEdit '{name}' not found.",
                    DIALOG_LOG_TAG,
                    level=Qgis.Warning,
                )

    def _connect_global_controls(self):
        """Connects signals for global widgets."""
        airport_name_le = getattr(
            self,
            "lineEdit_airport_name",
            self.findChild(QtWidgets.QLineEdit, "lineEdit_airport_name"),
        )
        add_runway_button = getattr(
            self,
            "pushButton_add_runway",
            self.findChild(QtWidgets.QPushButton, "pushButton_add_runway"),
        )

        if airport_name_le:
            airport_name_le.textChanged.connect(self.update_all_runway_calculations)
        else:
            QgsMessageLog.logMessage(
                "Warning: 'lineEdit_airport_name' not found.",
                DIALOG_LOG_TAG,
                level=Qgis.Warning,
            )

        if add_runway_button and self.scroll_area_layout:
            add_runway_button.clicked.connect(self.add_runway_group)
        elif not add_runway_button:
            QgsMessageLog.logMessage(
                "Warning: 'pushButton_add_runway' not found.",
                DIALOG_LOG_TAG,
                level=Qgis.Warning,
            )
        elif not self.scroll_area_layout:
            QgsMessageLog.logMessage(
                "Warning: 'pushButton_add_runway' not connected (layout missing).",
                DIALOG_LOG_TAG,
                level=Qgis.Warning,
            )

    # --- Runway Group Management ---
    def _get_next_runway_id(self) -> int:
        """Generates the next unique ID for a new runway group."""
        self._runway_id_counter += 1
        return self._runway_id_counter

    def update_all_runway_calculations(self):
        """Calls update_runway_calculations for all runway groups."""
        active_indices_copy = list(self._runway_groups.keys())
        for index in active_indices_copy:
            self.update_runway_calculations(index)

    def update_runway_calculations(self, runway_index: int):
        """
        Reads inputs for a specific runway, performs calculations,
        and updates its display labels.
        """
        group_widget = self._runway_groups.get(runway_index)
        if not group_widget:
            # QgsMessageLog.logMessage(f"Skipping calc update for index {runway_index}: Group not found.", DIALOG_LOG_TAG, level=Qgis.Debug)
            return

        input_data = group_widget.get_input_data()
        # --- Get ICAO Code ---
        icao_le = getattr(
            self,
            "lineEdit_airport_name",
            self.findChild(QtWidgets.QLineEdit, "lineEdit_airport_name"),
        )
        icao_code = (
            icao_le.text().strip().upper() if icao_le else ""
        )  # Get ICAO code early

        # --- Initialize Results ---
        calculation_results = {  # Default/error values
            "reciprocal_desig_full": NA_PLACEHOLDER,
            "runway_name": WIDGET_MISSING_MSG,  # Default name
            "distance": WIDGET_MISSING_MSG,
            "azimuth": WIDGET_MISSING_MSG,
            "type1_label_text": "(Primary End) Type:",
            "type2_label_text": "(Reciprocal End) Type:",
        }

        # --- Perform Calculations ---
        try:
            # Designator & Name
            rwy_desig_str = input_data.get("designator_str")
            rwy_suffix = input_data.get("suffix", "")
            # Initialize placeholders for calculated values
            full_desig_1_str, full_desig_2_str = "??", "??"
            compact_desig_1, compact_desig_2 = "??", "??"
            type1_label_str, type2_label_str = (
                calculation_results["type1_label_text"],
                calculation_results["type2_label_text"],
            )
            rwy_name_str = calculation_results["runway_name"]  # Start with default

            try:  # Inner try for designation math
                if not rwy_desig_str:
                    raise ValueError("Designation empty")
                rwy_desig_val = int(rwy_desig_str)
                if not (1 <= rwy_desig_val <= 36):
                    raise ValueError("Designation out of range (1-36)")

                # Calculate primary designation (both formats)
                compact_desig_1 = f"{rwy_desig_val:02d}{rwy_suffix}"  # e.g., "09L"
                full_desig_1_str = f"RWY {compact_desig_1}"  # e.g., "RWY 09L" (still needed for type labels)
                type1_label_str = (
                    f"{full_desig_1_str} Approach Type:"  # Update type label text
                )

                # Calculate reciprocal designation (both formats)
                reciprocal_val = (
                    (rwy_desig_val + 18)
                    if rwy_desig_val <= 18
                    else (rwy_desig_val - 18)
                )
                rec_desig_num_str = f"{reciprocal_val:02d}"  # e.g., "27"
                rec_suffix_map = {"L": "R", "R": "L", "C": "C", "": ""}
                rec_suffix = rec_suffix_map.get(rwy_suffix, "")  # e.g., "R"
                compact_desig_2 = f"{rec_desig_num_str}{rec_suffix}"  # e.g., "27R"
                full_desig_2_str = f"RWY {compact_desig_2}"  # e.g., "RWY 27R" (needed for header + type label)
                type2_label_str = (
                    f"{full_desig_2_str} Approach Type:"  # Update type label text
                )

                # <<< MODIFIED: Construct the runway name label in the desired format >>>
                combined_compact_desigs = (
                    f"{compact_desig_1}/{compact_desig_2}"  # e.g., "09L/27R"
                )
                if icao_code:
                    rwy_name_str = f"{icao_code} Runway {combined_compact_desigs}"  # e.g., "EGLL Runway 09L/27R"
                else:
                    rwy_name_str = (
                        f"Runway {combined_compact_desigs}"  # e.g., "Runway 09L/27R"
                    )

            except ValueError:
                # Handle invalid designation input
                full_desig_2_str = "Invalid"  # Keep this for the header label update
                rwy_name_str = (
                    "Invalid Designation"  # Set error message for the main label
                )

            # Update results dictionary with calculated values
            calculation_results.update(
                {
                    "reciprocal_desig_full": full_desig_2_str,  # Used for the header label above coords
                    "runway_name": rwy_name_str,
                    "type1_label_text": type1_label_str,
                    "type2_label_text": type2_label_str,
                }
            )

            # Distance & Azimuth calculation
            thr_east_str = input_data.get("thr_easting")
            thr_north_str = input_data.get("thr_northing")
            rec_thr_east_str = input_data.get("rec_easting")
            rec_thr_north_str = input_data.get("rec_northing")
            distance_str, azimuth_str = ENTER_COORDS_MSG, ENTER_COORDS_MSG
            if all([thr_east_str, thr_north_str, rec_thr_east_str, rec_thr_north_str]):
                try:  # Inner try for coordinate math
                    p1 = QgsPointXY(float(thr_east_str), float(thr_north_str))
                    p2 = QgsPointXY(float(rec_thr_east_str), float(rec_thr_north_str))
                    dist = p1.distance(p2)
                    arc_code = group_widget._arc_number_for_length(dist)
                    if arc_code and not group_widget.arc_num_combo.currentData():
                        idx = group_widget.arc_num_combo.findData(arc_code)
                        if idx != -1:
                            group_widget.arc_num_combo.setCurrentIndex(idx)

                    distance_str = f"{dist:.2f}"
                    ZERO_TOL, NEAR_TOL = 1e-6, 0.1
                    if math.isclose(dist, 0.0, abs_tol=ZERO_TOL):
                        azimuth_str = SAME_POINT_MSG + (
                            f" (<{NEAR_TOL}m)" if ZERO_TOL < dist < NEAR_TOL else ""
                        )
                    else:
                        az = p1.azimuth(p2) % 360
                        azimuth_str = f"{az:.2f}" + (
                            f" ({NEAR_POINTS_MSG})" if dist < NEAR_TOL else ""
                        )
                except ValueError:
                    distance_str, azimuth_str = INVALID_COORDS_MSG, INVALID_COORDS_MSG
                except Exception as e_coord:
                    QgsMessageLog.logMessage(
                        f"Coord calc error Rwy {runway_index}: {e_coord}",
                        DIALOG_LOG_TAG,
                        level=Qgis.Warning,
                    )
                    distance_str, azimuth_str = CALC_ERROR_MSG, CALC_ERROR_MSG
            calculation_results["distance"] = distance_str
            calculation_results["azimuth"] = azimuth_str

        except Exception as e_outer:
            QgsMessageLog.logMessage(
                f"Outer calc error Rwy {runway_index}: {e_outer}",
                DIALOG_LOG_TAG,
                level=Qgis.Critical,
            )
            # Reset results to error state
            calculation_results = {k: CALC_ERROR_MSG for k in calculation_results}
            calculation_results["type1_label_text"] = (
                "(Primary End) Type:"  # Reset labels
            )
            calculation_results["type2_label_text"] = "(Reciprocal End) Type:"

        # --- Update the group's display labels ---
        group_widget.update_display_labels(
            calculation_results
        )

    def add_runway_group(self):
        """Creates and adds a new RunwayWidgetGroup instance."""
        if not self.scroll_area_layout:
            QMessageBox.critical(self, "Layout Error", "Scroll area layout missing.")
            return

        runway_index = self._get_next_runway_id()
        scroll_content_widget = self.findChild(
            QtWidgets.QScrollArea, "scrollArea_runways"
        ).widget()
        if not scroll_content_widget:
            QMessageBox.critical(
                self, "Layout Error", "Scroll area content widget missing."
            )
            return

        # Pass all arguments positionally
        new_group = RunwayWidgetGroup(
            runway_index, self.coord_validator, scroll_content_widget
        )

        new_group.inputChanged.connect(
            lambda idx=runway_index: self.update_runway_calculations(idx)
        )
        new_group.removeRequested.connect(self.remove_runway_group)

        # Add to the end of the layout
        self.scroll_area_layout.addWidget(new_group)

        self._runway_groups[runway_index] = new_group
        self._update_dialog_height()
        self.update_runway_calculations(runway_index)  # Update placeholders

    def remove_runway_group(self, runway_index_to_remove: int):
        """Handles request to remove a runway group after confirmation."""
        if runway_index_to_remove not in self._runway_groups:
            QgsMessageLog.logMessage(
                f"Cannot remove: Index {runway_index_to_remove} not found.",
                DIALOG_LOG_TAG,
                level=Qgis.Warning,
            )
            return

        group_to_remove = self._runway_groups[runway_index_to_remove]
        runway_display_name = f"Runway {runway_index_to_remove}"
        try:
            name = group_to_remove.rwy_name_lbl.text()
            placeholders = [
                CALC_PLACEHOLDER,
                WIDGET_MISSING_MSG,
                "",
                None,
                "Invalid Designation",
                "Invalid",
                CALC_ERROR_MSG,
            ]
            if name and name not in placeholders:
                runway_display_name = name
        except AttributeError:
            pass

        confirmation_message = self.tr("Remove '{name}'?").format(
            name=runway_display_name
        )
        reply = QtWidgets.QMessageBox.question(
            self,
            self.tr("Confirm Removal"),
            confirmation_message,
            QtWidgets.QMessageBox.StandardButton.Yes
            | QtWidgets.QMessageBox.StandardButton.No,
            QtWidgets.QMessageBox.StandardButton.No,
        )

        if reply == QtWidgets.QMessageBox.StandardButton.Yes:
            self._remove_runway_group_internal(runway_index_to_remove)

    def _remove_runway_group_internal(self, runway_index: int):
        """Internal helper to remove a group without user confirmation."""
        group_to_remove = self._runway_groups.pop(runway_index, None)
        if group_to_remove and self.scroll_area_layout:
            group_to_remove.hide()
            self.scroll_area_layout.removeWidget(group_to_remove)
            group_to_remove.deleteLater()
            self._update_dialog_height()
        elif not group_to_remove:
            QgsMessageLog.logMessage(
                f"Internal removal Warn: Group {runway_index} not found.",
                DIALOG_LOG_TAG,
                level=Qgis.Warning,
            )
        elif not self.scroll_area_layout:
            QgsMessageLog.logMessage(
                f"Internal removal Critical: Layout missing, cannot remove widget {runway_index}.",
                DIALOG_LOG_TAG,
                level=Qgis.Critical,
            )

    def _update_dialog_height(self):
        """Adjusts the dialog height to fit its contents."""
        QtCore.QTimer.singleShot(0, self.adjustSize)

    # --- Data Gathering Methods ---
    def get_all_input_data(self) -> Optional[Dict[str, Any]]:
        """
        Gathers all validated inputs (global, runways, CNS).
        Returns dict or None if critical validation fails.
        """
        final_data = {}
        validation_ok = True
        error_messages = []

        # --- Check if output option widgets exist (as a prerequisite) ---
        output_option_widgets_exist = all(
            hasattr(self, name)
            for name in [
                "radioMemoryOutput",
                "radioFileOutput",
                "fileWidgetOutputPath",
                "comboOutputFormat",
            ]
        )
        if not output_option_widgets_exist:
            QMessageBox.critical(
                self,
                "UI Configuration Error",
                "Output option widgets are missing from the dialog. Cannot proceed.",
            )
            return None

        # --- Global Inputs ---
        (
            icao,
            arp_pt,
            arp_e,
            arp_n,
            arp_elev,
            met_pt,
            met_elev,
        ) = self._get_global_inputs()
        if icao is None:  # Critical failure
            return None

        final_data.update(
            {
                "icao_code": icao,
                "arp_point": arp_pt,
                "arp_easting": arp_e,
                "arp_northing": arp_n,
                "arp_elevation": arp_elev,
                "met_point": met_pt,
                "met_elevation": met_elev,
            }
        )

        # --- Runway Inputs ---
        runway_data_list = []
        if not self._runway_groups:
            validation_ok = False
            error_messages.append("At least one runway definition is required.")
        else:
            for index, group_widget in sorted(self._runway_groups.items()):
                runway_inputs = group_widget.get_input_data()
                validated_runway = self._validate_runway_data(
                    index, runway_inputs, error_messages
                )
                if validated_runway:
                    # Ensure keys exist (validator should add them, but be safe)
                    validated_runway.setdefault("thr_elev_1", None)
                    validated_runway.setdefault("thr_elev_2", None)
                    validated_runway.setdefault("thr_displaced_1", None)
                    validated_runway.setdefault("thr_displaced_2", None)
                    validated_runway.setdefault(
                        "thr_pre_area_1", None
                    )
                    validated_runway.setdefault(
                        "thr_pre_area_2", None
                    )
                    runway_data_list.append(validated_runway)
                else:
                    validation_ok = False  # Error messages added by validator

        if not validation_ok:
            QMessageBox.critical(
                self,
                "Input Error",
                "Please correct the following errors:\n- "
                + "\n- ".join(error_messages),
            )
            return None
        final_data["runways"] = runway_data_list

        # --- CNS Inputs ---
        cns_data = self._get_cns_manual_data()
        if cns_data is None:
            return None
        final_data["cns_facilities"] = cns_data

        # --- Output Options ---
        if self.radioMemoryOutput.isChecked():
            final_data["output_mode"] = "memory"
            final_data["output_path"] = None
            final_data["output_format_driver"] = None
            final_data["output_format_extension"] = None
        elif self.radioFileOutput.isChecked():
            final_data["output_mode"] = "file"
            raw_path_from_widget = self.fileWidgetOutputPath.filePath().strip()
            selected_format_name = self.comboOutputFormat.currentText()

            if not raw_path_from_widget:
                output_path = ""
            elif os.path.isdir(raw_path_from_widget):
                output_path = raw_path_from_widget
            elif os.path.isfile(raw_path_from_widget):
                output_path = os.path.dirname(raw_path_from_widget)
                QgsMessageLog.logMessage(
                    f"Output path '{raw_path_from_widget}' was a file; using '{output_path}'.",
                    DIALOG_LOG_TAG,
                    Qgis.Info,
                )
            else:
                output_path = raw_path_from_widget

            if not output_path:
                validation_ok = False
                error_messages.append("Output directory is required.")
            elif not os.path.isdir(output_path):
                validation_ok = False
                error_messages.append(
                    f"Output directory does not exist: {output_path}"
                )
            elif selected_format_name not in OUTPUT_FORMATS:
                validation_ok = False
                error_messages.append(
                    f"Invalid output format selected: {selected_format_name}."
                )
            else:
                # If validation_ok is still True up to this point
                driver_name, _, extension = OUTPUT_FORMATS[selected_format_name]
                final_data["output_path"] = (
                    output_path  # Store the processed directory path
                )
                final_data["output_format_driver"] = driver_name
                final_data["output_format_extension"] = extension

        else:
            validation_ok = False
            error_messages.append("No output mode selected (memory or file).")

        # --- Final Validation Check and Return ---
        if not validation_ok:
            QMessageBox.critical(
                self,
                "Input Error",
                "Please correct the following errors:\n- "
                + "\n- ".join(error_messages),
            )
            return None

        # Add dissolve option
        if hasattr(self, "checkBox_dissolveLayers") and self.checkBox_dissolveLayers:
            final_data["dissolve_output"] = self.checkBox_dissolveLayers.isChecked()
        else:
            final_data["dissolve_output"] = False

        return final_data

    def _validate_runway_data(
        self, index: int, inputs: Dict[str, str], errors: List[str]
    ) -> Optional[Dict[str, Any]]:
        """Validates raw inputs for a single runway."""
        validated = {"original_index": index}
        current_errors = 0

        # Designator
        desig_str = inputs.get("designator_str", "")
        try:
            desig_val = int(desig_str)
            if not (1 <= desig_val <= 36):
                raise ValueError("Designator must be 01-36")
            validated["designator_num"] = desig_val
            validated["suffix"] = inputs.get("suffix", "")
        except ValueError as e:
            errors.append(
                f"Rwy {index}: Invalid primary designator '{desig_str}'. ({e})"
            )
            current_errors += 1
            validated["designator_num"] = None

        # Coordinates (Threshold 1)
        thr_east_str = inputs.get("thr_easting", "")
        thr_north_str = inputs.get("thr_northing", "")
        try:
            thr_east_f = float(thr_east_str)
            thr_north_f = float(thr_north_str)
            validated["thr_point"] = QgsPointXY(thr_east_f, thr_north_f)
        except (ValueError, TypeError) as e:
            errors.append(
                f"Rwy {index}: Invalid primary threshold coordinates (E='{thr_east_str}', N='{thr_north_str}'). {e}"
            )
            validated["thr_point"] = None
            current_errors += 1

        # Coordinates (Threshold 2)
        rec_east_str = inputs.get("rec_easting", "")
        rec_north_str = inputs.get("rec_northing", "")
        try:
            rec_east_f = float(rec_east_str)
            rec_north_f = float(rec_north_str)
            validated["rec_thr_point"] = QgsPointXY(rec_east_f, rec_north_f)
        except (ValueError, TypeError) as e:
            errors.append(
                f"Rwy {index}: Invalid reciprocal threshold coordinates (E='{rec_east_str}', N='{rec_north_str}'). {e}"
            )
            validated["rec_thr_point"] = None
            current_errors += 1

        # Check if points are valid and not coincident
        pt1 = validated.get("thr_point")
        pt2 = validated.get("rec_thr_point")
        if pt1 and pt2 and pt1.distance(pt2) < 1e-6:
            errors.append(f"Rwy {index}: Threshold coordinates are identical.")
            current_errors += 1

        # Elevations (Optional)
        try:  # Primary Elevation
            elev1_str = inputs.get("thr_elev_1", "").strip()
            validated["thr_elev_1"] = float(elev1_str) if elev1_str else None
        except ValueError:
            errors.append(
                f"Rwy {index}: Invalid primary elevation '{inputs.get('thr_elev_1', '')}'."
            )
            current_errors += 1
            validated["thr_elev_1"] = None
        try:  # Reciprocal Elevation
            elev2_str = inputs.get("thr_elev_2", "").strip()
            validated["thr_elev_2"] = float(elev2_str) if elev2_str else None
        except ValueError:
            errors.append(
                f"Rwy {index}: Invalid reciprocal elevation '{inputs.get('thr_elev_2', '')}'."
            )
            current_errors += 1
            validated["thr_elev_2"] = None

        # Displaced Thresholds (Optional, non-negative)
        try:  # Primary Displaced
            disp1_str = inputs.get("thr_displaced_1", "").strip()
            if disp1_str:
                disp1_val = float(disp1_str)
                if disp1_val < 0:
                    raise ValueError("Cannot be negative")
                validated["thr_displaced_1"] = disp1_val
            else:
                validated["thr_displaced_1"] = None
        except ValueError:
            errors.append(
                f"Rwy {index}: Invalid primary displaced threshold '{inputs.get('thr_displaced_1', '')}'. Must be non-negative."
            )
            current_errors += 1
            validated["thr_displaced_1"] = None
        try:  # Reciprocal Displaced
            disp2_str = inputs.get("thr_displaced_2", "").strip()
            if disp2_str:
                disp2_val = float(disp2_str)
                if disp2_val < 0:
                    raise ValueError("Cannot be negative")
                validated["thr_displaced_2"] = disp2_val
            else:
                validated["thr_displaced_2"] = None
        except ValueError:
            errors.append(
                f"Rwy {index}: Invalid reciprocal displaced threshold '{inputs.get('thr_displaced_2', '')}'. Must be non-negative."
            )
            current_errors += 1
            validated["thr_displaced_2"] = None

        # Pre-threshold Area validation (Optional, non-negative)
        try:  # Primary Pre-threshold Area
            pre_area1_str = inputs.get("thr_pre_area_1", "").strip()
            if pre_area1_str:
                pre_area1_val = float(pre_area1_str)
                if pre_area1_val < 0:
                    raise ValueError("Cannot be negative")
                validated["thr_pre_area_1"] = pre_area1_val
            else:
                validated["thr_pre_area_1"] = None  # Explicitly None if empty
        except ValueError:
            errors.append(
                f"Rwy {index}: Invalid primary pre-threshold area '{inputs.get('thr_pre_area_1', '')}'. Must be non-negative."
            )
            current_errors += 1
            validated["thr_pre_area_1"] = None

        try:  # Reciprocal Pre-threshold Area
            pre_area2_str = inputs.get("thr_pre_area_2", "").strip()
            if pre_area2_str:
                pre_area2_val = float(pre_area2_str)
                if pre_area2_val < 0:
                    raise ValueError("Cannot be negative")
                validated["thr_pre_area_2"] = pre_area2_val
            else:
                validated["thr_pre_area_2"] = None
        except ValueError:
            errors.append(
                f"Rwy {index}: Invalid reciprocal pre-threshold area '{inputs.get('thr_pre_area_2', '')}'. Must be non-negative."
            )
            current_errors += 1
            validated["thr_pre_area_2"] = None

        # Width (Mandatory positive)
        try:
            width_val = float(inputs.get("width", ""))
            if width_val <= 0:
                raise ValueError("Width must be positive")
            validated["width"] = width_val
        except (ValueError, TypeError):
            errors.append(
                f"Rwy {index}: Invalid runway width '{inputs.get('width', '')}'. Must be a positive number."
            )
            current_errors += 1
            validated["width"] = None

        # Shoulder (Optional, non-negative)
        try:
            shoulder_str = inputs.get("shoulder", "").strip()
            if shoulder_str:
                shoulder_val = float(shoulder_str)
                if shoulder_val < 0:
                    raise ValueError("Shoulder cannot be negative")
                validated["shoulder"] = shoulder_val
            else:
                validated["shoulder"] = None
        except ValueError:
            errors.append(
                f"Rwy {index}: Invalid shoulder width '{inputs.get('shoulder', '')}'. Must be non-negative."
            )
            current_errors += 1
            validated["shoulder"] = None

        # Optional fields (just copy text)
        validated["arc_num"] = inputs.get("arc_num")
        validated["arc_let"] = inputs.get("arc_let")
        validated["type1"] = inputs.get("type1")
        validated["type2"] = inputs.get("type2")

        return validated if current_errors == 0 else None

    # --- Global/CNS Input Getters (no changes needed) ---
    def _get_global_inputs(
        self,
    ) -> Tuple[
        Optional[str],
        Optional[QgsPointXY],
        Optional[float],
        Optional[float],
        Optional[float],
        Optional[QgsPointXY],
        Optional[float],
    ]:
        """Retrieves and validates ICAO, ARP coords, and MET coords."""
        icao_code: Optional[str] = None
        arp_point: Optional[QgsPointXY] = None
        arp_east: Optional[float] = None
        arp_north: Optional[float] = None
        arp_elev: Optional[float] = None
        met_point_proj_crs: Optional[QgsPointXY] = None
        met_elev: Optional[float] = None

        try:
            icao_lineEdit = getattr(
                self,
                "lineEdit_airport_name",
                self.findChild(QtWidgets.QLineEdit, "lineEdit_airport_name"),
            )
            arp_east_lineEdit = getattr(
                self,
                "lineEdit_arp_easting",
                self.findChild(QtWidgets.QLineEdit, "lineEdit_arp_easting"),
            )
            arp_north_lineEdit = getattr(
                self,
                "lineEdit_arp_northing",
                self.findChild(QtWidgets.QLineEdit, "lineEdit_arp_northing"),
            )
            arp_elev_lineEdit = getattr(
                self,
                "lineEdit_arp_elevation",
                self.findChild(QtWidgets.QLineEdit, "lineEdit_arp_elevation"),
            )
            met_east_lineEdit = getattr(
                self,
                "lineEdit_met_easting",
                self.findChild(QtWidgets.QLineEdit, "lineEdit_met_easting"),
            )
            met_north_lineEdit = getattr(
                self,
                "lineEdit_met_northing",
                self.findChild(QtWidgets.QLineEdit, "lineEdit_met_northing"),
            )
            met_elev_lineEdit = getattr(
                self,
                "lineEdit_met_elevation",
                self.findChild(QtWidgets.QLineEdit, "lineEdit_met_elevation"),
            )

            if not icao_lineEdit:
                raise RuntimeError("UI Error: Cannot find 'lineEdit_airport_name'.")
            icao_code_str = icao_lineEdit.text().strip().upper()
            if not icao_code_str:
                QMessageBox.critical(
                    self,
                    self.tr("Input Error"),
                    self.tr("Airport ICAO Code is required."),
                )
                return None, None, None, None, None, None, None
            icao_code = icao_code_str

            # ARP (Optional Coords, Optional Elev)
            arp_point, arp_east, arp_north, arp_elev = (
                None,
                None,
                None,
                None,
            )  # Initialize
            if arp_east_lineEdit and arp_north_lineEdit:
                arp_east_str = arp_east_lineEdit.text().strip()
                arp_north_str = arp_north_lineEdit.text().strip()
                if arp_east_str and arp_north_str:
                    try:
                        arp_east_val = float(arp_east_str)
                        arp_north_val = float(arp_north_str)
                        arp_point = QgsPointXY(arp_east_val, arp_north_val)
                        arp_east, arp_north = arp_east_val, arp_north_val
                    except ValueError:
                        QMessageBox.warning(
                            self,
                            self.tr("Input Warning"),
                            self.tr(
                                "Invalid ARP coordinate format. ARP coordinates ignored."
                            ),
                        )
                        arp_point, arp_east, arp_north = None, None, None
                elif arp_east_str or arp_north_str:  # Only one entered
                    QMessageBox.warning(
                        self,
                        self.tr("Input Warning"),
                        self.tr(
                            "Both ARP Easting and Northing must be provided if entering coordinates. ARP coordinates ignored."
                        ),
                    )
                    arp_point, arp_east, arp_north = None, None, None

            # Check ARP Elevation (Optional, but must be valid if entered)
            if arp_elev_lineEdit:
                arp_elev_str = arp_elev_lineEdit.text().strip()
                if arp_elev_str:
                    try:
                        arp_elev = float(arp_elev_str)
                    except ValueError:
                        QMessageBox.critical(
                            self,
                            self.tr("Input Error"),
                            self.tr("Invalid ARP Elevation format. Must be a number."),
                        )
                        return (
                            None,
                            None,
                            None,
                            None,
                            None,
                            None,
                            None,
                        )  # Abort data gathering

            # MET Station (Optional)
            met_point_proj_crs = None  # Initialize
            if met_east_lineEdit and met_north_lineEdit:
                met_east_str = met_east_lineEdit.text().strip()
                met_north_str = met_north_lineEdit.text().strip()
                if met_east_str and met_north_str:
                    try:
                        met_east_val = float(met_east_str)
                        met_north_val = float(met_north_str)
                        met_point_proj_crs = QgsPointXY(met_east_val, met_north_val)
                    except ValueError:
                        QMessageBox.warning(
                            self,
                            self.tr("Input Warning"),
                            self.tr(
                                "Invalid MET station coordinate format. MET station ignored."
                            ),
                        )
                        met_point_proj_crs = None
                elif met_east_str or met_north_str:  # Only one entered
                    QMessageBox.warning(
                        self,
                        self.tr("Input Warning"),
                        self.tr(
                            "Both MET Easting and Northing must be provided if entering coordinates. MET station ignored."
                        ),
                    )
                    met_point_proj_crs = None

            if met_elev_lineEdit:
                met_elev_str = met_elev_lineEdit.text().strip()
                if met_elev_str:
                    try:
                        met_elev = float(met_elev_str)
                    except ValueError:
                        QMessageBox.critical(
                            self,
                            self.tr("Input Error"),
                            self.tr("Invalid MET Elevation format. Must be a number."),
                        )
                        return None, None, None, None, None, None, None

        except (AttributeError, RuntimeError, Exception) as e:
            QgsMessageLog.logMessage(
                f"Error getting global inputs: {e}", DIALOG_LOG_TAG, level=Qgis.Critical
            )
            QMessageBox.critical(
                self,
                self.tr("Internal Error"),
                self.tr("Error retrieving global inputs. See QGIS log."),
            )
            return None, None, None, None, None, None, None

        return (
            icao_code,
            arp_point,
            arp_east,
            arp_north,
            arp_elev,
            met_point_proj_crs,
            met_elev,
        )

# ========================= End of Class Definition =========================

if __name__ == "__main__":
    import sys
    from qgis.PyQt.QtWidgets import QApplication  # type: ignore

    # --- Mock QGIS environment if running standalone ---
    class MockQgisInterface:
        pass

    class MockQgsProject:
        def __init__(self):
            self._crs = QgsCoordinateReferenceSystem("EPSG:4326")

        def instance(self):
            return self

        def crs(self):
            return self._crs

    if not QgsProject.instance():
        QgsProject.setInstance(MockQgsProject())
    # --- End Mock ---

    app = QApplication(sys.argv)
    dialog = SafeguardingBuilderDialog()
    dialog.show()
    sys.exit(app.exec())
