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
import json
from typing import List, Optional, Dict, Any, Tuple

# --- QGIS Imports ---
from qgis.core import ( # type: ignore
    QgsMessageLog, Qgis, QgsPointXY, QgsProject, QgsCoordinateReferenceSystem,
    QgsGeometry,
)
from qgis.PyQt import uic, QtWidgets, QtGui, QtCore # type: ignore
from qgis.PyQt.QtWidgets import ( # type: ignore
    QFileDialog, QMessageBox, QTableWidgetItem, QComboBox,
    QAbstractItemView
)

# --- Constants for UI Placeholders/Messages ---
CALC_PLACEHOLDER = "(Calculated)"
NA_PLACEHOLDER = "N/A"
ENTER_COORDS_MSG = "Enter Coords"
INVALID_COORDS_MSG = "Invalid Coords"
CALC_ERROR_MSG = "Calc Error"
SAME_POINT_MSG = "Same Point"
NEAR_POINTS_MSG = "Near Points"
WIDGET_MISSING_MSG = "Widget?"
# --- End Constants ---

# Load the UI class from the .ui file
FORM_CLASS, _ = uic.loadUiType(os.path.join(
        os.path.dirname(__file__), 'safeguarding_builder_dialog_base.ui'))

# Plugin-specific constant for logging within this module
DIALOG_LOG_TAG = 'SafeguardingBuilderDialog'

# ### NEW: Supported output formats (driver name for QgsVectorFileWriter, user-friendly name, default extension)
OUTPUT_FORMATS = {
    # "GeoPackage": ("GPKG", "GeoPackage", ".gpkg"), 
    "ESRI Shapefile": ("ESRI Shapefile", "ESRI Shapefile", ".shp"),
    "GeoJSON": ("GeoJSON", "GeoJSON", ".geojson"),
}
DEFAULT_OUTPUT_FORMAT = "ESRI Shapefile"

# =========================================================================
# == Runway Widget Group Helper Class
# =========================================================================
class RunwayWidgetGroup(QtWidgets.QGroupBox):
    """
    Manages the UI elements and layout for a single runway group.
    Encapsulates widget creation, data access, and basic signal handling.
    Uses grid layouts, left-justified labels, and styled runway name.
    """
    inputChanged = QtCore.pyqtSignal()
    removeRequested = QtCore.pyqtSignal(int)

    def __init__(self, index: int, coord_validator: QtGui.QValidator, parent: QtWidgets.QWidget = None):
        """Constructor."""
        title = f"Runway {index}"
        super().__init__(title, parent)

        self.index = index
        self.numeric_validator = QtGui.QDoubleValidator()
        self.numeric_validator.setNotation(QtGui.QDoubleValidator.Notation.StandardNotation)
        self.coord_validator = coord_validator
        # <<< NEW/REUSED >>> Validator for non-negative distances (Displaced, Pre-Threshold Area, Shoulder)
        self.distance_validator = QtGui.QDoubleValidator(0.0, 9999.9, 1, self) # Min 0.0, Max 9999.9, 1 decimal
        self.distance_validator.setNotation(QtGui.QDoubleValidator.Notation.StandardNotation)


        self.setObjectName(f"groupBox_runway_{self.index}")
        self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Preferred, QtWidgets.QSizePolicy.Policy.MinimumExpanding)

        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        """Creates and arranges all widgets within this group box."""
        groupBox_layout = QtWidgets.QVBoxLayout(self)

        # --- Coordinate Grid Layout ---
        gridLayout_Coords = QtWidgets.QGridLayout()
        gridLayout_Coords.setObjectName(f"gridLayout_Coords_{self.index}")
        gridLayout_Coords.setColumnStretch(0, 2)
        gridLayout_Coords.setColumnStretch(1, 1)
        gridLayout_Coords.setColumnStretch(2, 1)

        # Labels (Left-Justified)
        label_designation_row = QtWidgets.QLabel("Designation:")
        label_designation_row.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter)
        label_easting_row = QtWidgets.QLabel("Easting:")
        label_easting_row.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter)
        label_northing_row = QtWidgets.QLabel("Northing:")
        label_northing_row.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter)
        label_elevation_row = QtWidgets.QLabel("Elevation (m):")
        label_elevation_row.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter)
        label_displaced_row = QtWidgets.QLabel("Displaced (m):")
        label_displaced_row.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter)
        # <<< NEW >>> Label for Pre-threshold Area
        label_pre_threshold_area_row = QtWidgets.QLabel("Pre-threshold Area (m):")
        label_pre_threshold_area_row.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter)


        # Input Widgets
        h_layout_desig_inputs = QtWidgets.QHBoxLayout()
        self.desig_le = QtWidgets.QLineEdit(); self.desig_le.setObjectName(f"lineEdit_rwy_desig_{self.index}"); self.desig_le.setMaxLength(2); self.desig_le.setToolTip("Enter 2-digit primary designation (01-36)."); self.desig_le.setValidator(QtGui.QIntValidator(1, 36, self))
        self.suffix_combo = QtWidgets.QComboBox(); self.suffix_combo.setObjectName(f"comboBox_rwy_suffix_{self.index}"); self.suffix_combo.addItems(["", "L", "C", "R"]); self.suffix_combo.setToolTip("Runway suffix (Leave blank if none)"); self.suffix_combo.setFocusPolicy(QtCore.Qt.FocusPolicy.StrongFocus)
        h_layout_desig_inputs.addWidget(self.desig_le); h_layout_desig_inputs.addWidget(self.suffix_combo)
        self.rec_desig_hdr_lbl = QtWidgets.QLabel(CALC_PLACEHOLDER); self.rec_desig_hdr_lbl.setObjectName(f"label_header_desig2_{self.index}"); self.rec_desig_hdr_lbl.setToolTip("Calculated reciprocal designation"); self.rec_desig_hdr_lbl.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.thr_east_le = QtWidgets.QLineEdit(); self.thr_east_le.setObjectName(f"lineEdit_thr_easting_{self.index}"); self.thr_east_le.setPlaceholderText("e.g., 456789.12"); self.thr_east_le.setToolTip("Easting coordinate of primary threshold"); self.thr_east_le.setValidator(self.coord_validator)
        self.thr_north_le = QtWidgets.QLineEdit(); self.thr_north_le.setObjectName(f"lineEdit_thr_northing_{self.index}"); self.thr_north_le.setPlaceholderText("e.g., 123456.78"); self.thr_north_le.setToolTip("Northing coordinate of primary threshold"); self.thr_north_le.setValidator(self.coord_validator)
        self.rec_east_le = QtWidgets.QLineEdit(); self.rec_east_le.setObjectName(f"lineEdit_reciprocal_thr_easting_{self.index}"); self.rec_east_le.setPlaceholderText("e.g., 457890.34"); self.rec_east_le.setToolTip("Easting coordinate of reciprocal threshold"); self.rec_east_le.setValidator(self.coord_validator)
        self.rec_north_le = QtWidgets.QLineEdit(); self.rec_north_le.setObjectName(f"lineEdit_reciprocal_thr_northing_{self.index}"); self.rec_north_le.setPlaceholderText("e.g., 124567.90"); self.rec_north_le.setToolTip("Northing coordinate of reciprocal threshold"); self.rec_north_le.setValidator(self.coord_validator)
        self.thr_elev_1_le = QtWidgets.QLineEdit(); self.thr_elev_1_le.setObjectName(f"lineEdit_thr_elev_1_{self.index}"); self.thr_elev_1_le.setPlaceholderText("e.g., 150.5"); self.thr_elev_1_le.setToolTip("Elevation (AMSL) of primary threshold"); self.thr_elev_1_le.setValidator(self.numeric_validator)
        self.thr_elev_2_le = QtWidgets.QLineEdit(); self.thr_elev_2_le.setObjectName(f"lineEdit_thr_elev_2_{self.index}"); self.thr_elev_2_le.setPlaceholderText("e.g., 149.8"); self.thr_elev_2_le.setToolTip("Elevation (AMSL) of reciprocal threshold"); self.thr_elev_2_le.setValidator(self.numeric_validator)
        self.thr_displaced_1_le = QtWidgets.QLineEdit(); self.thr_displaced_1_le.setObjectName(f"lineEdit_thr_displaced_1_{self.index}"); self.thr_displaced_1_le.setPlaceholderText("e.g., 300"); self.thr_displaced_1_le.setToolTip("Displaced threshold distance for primary end (meters). Leave blank if none."); self.thr_displaced_1_le.setValidator(self.distance_validator) # Use distance validator
        self.thr_displaced_2_le = QtWidgets.QLineEdit(); self.thr_displaced_2_le.setObjectName(f"lineEdit_thr_displaced_2_{self.index}"); self.thr_displaced_2_le.setPlaceholderText("e.g., 0"); self.thr_displaced_2_le.setToolTip("Displaced threshold distance for reciprocal end (meters). Leave blank if none."); self.thr_displaced_2_le.setValidator(self.distance_validator) # Use distance validator

        # <<< NEW >>> Pre-threshold Area LineEdits
        self.thr_pre_area_1_le = QtWidgets.QLineEdit()
        self.thr_pre_area_1_le.setObjectName(f"lineEdit_thr_pre_area_1_{self.index}")
        self.thr_pre_area_1_le.setPlaceholderText("e.g., 60")
        self.thr_pre_area_1_le.setToolTip("Length of pre-threshold area (cleared/graded) for primary end (meters). Leave blank if none.")
        self.thr_pre_area_1_le.setValidator(self.distance_validator) # Use distance validator

        self.thr_pre_area_2_le = QtWidgets.QLineEdit()
        self.thr_pre_area_2_le.setObjectName(f"lineEdit_thr_pre_area_2_{self.index}")
        self.thr_pre_area_2_le.setPlaceholderText("e.g., 60")
        self.thr_pre_area_2_le.setToolTip("Length of pre-threshold area (cleared/graded) for reciprocal end (meters). Leave blank if none.")
        self.thr_pre_area_2_le.setValidator(self.distance_validator) # Use distance validator


        # Add Widgets to Coordinate Grid (incrementing row index)
        current_coord_row = 0
        # Row 0: Designation
        gridLayout_Coords.addWidget(label_designation_row, current_coord_row, 0); gridLayout_Coords.addLayout(h_layout_desig_inputs, current_coord_row, 1); gridLayout_Coords.addWidget(self.rec_desig_hdr_lbl, current_coord_row, 2); current_coord_row += 1
        # Row 1: Easting
        gridLayout_Coords.addWidget(label_easting_row, current_coord_row, 0); gridLayout_Coords.addWidget(self.thr_east_le, current_coord_row, 1); gridLayout_Coords.addWidget(self.rec_east_le, current_coord_row, 2); current_coord_row += 1
        # Row 2: Northing
        gridLayout_Coords.addWidget(label_northing_row, current_coord_row, 0); gridLayout_Coords.addWidget(self.thr_north_le, current_coord_row, 1); gridLayout_Coords.addWidget(self.rec_north_le, current_coord_row, 2); current_coord_row += 1
        # Row 3: Elevation
        gridLayout_Coords.addWidget(label_elevation_row, current_coord_row, 0); gridLayout_Coords.addWidget(self.thr_elev_1_le, current_coord_row, 1); gridLayout_Coords.addWidget(self.thr_elev_2_le, current_coord_row, 2); current_coord_row += 1
        # Row 4: Displaced Threshold
        gridLayout_Coords.addWidget(label_displaced_row, current_coord_row, 0); gridLayout_Coords.addWidget(self.thr_displaced_1_le, current_coord_row, 1); gridLayout_Coords.addWidget(self.thr_displaced_2_le, current_coord_row, 2); current_coord_row += 1
        # <<< NEW >>> Row 5: Pre-threshold Area
        gridLayout_Coords.addWidget(label_pre_threshold_area_row, current_coord_row, 0); gridLayout_Coords.addWidget(self.thr_pre_area_1_le, current_coord_row, 1); gridLayout_Coords.addWidget(self.thr_pre_area_2_le, current_coord_row, 2); current_coord_row += 1


        groupBox_layout.addLayout(gridLayout_Coords) # Add coordinate grid

        # --- Runway Name Label (Styled) ---
        self.rwy_name_lbl = QtWidgets.QLabel(CALC_PLACEHOLDER)
        self.rwy_name_lbl.setObjectName(f"label_rwy_name_{self.index}")
        self.rwy_name_lbl.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter)
        font = self.rwy_name_lbl.font(); font.setBold(True); self.rwy_name_lbl.setFont(font)
        self.rwy_name_lbl.setContentsMargins(0, 5, 0, 5)
        groupBox_layout.addWidget(self.rwy_name_lbl)

        # --- Details Grid Layout ---
        detailsLayout = QtWidgets.QGridLayout()
        detailsLayout.setObjectName(f"detailsLayout_{self.index}"); detailsLayout.setColumnStretch(0, 1); detailsLayout.setColumnStretch(1, 1)
        current_details_row = 0

        label_rwy_dist_text = QtWidgets.QLabel("Length (m):"); label_rwy_dist_text.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter)
        self.dist_lbl = QtWidgets.QLabel(CALC_PLACEHOLDER); self.dist_lbl.setObjectName(f"label_rwy_distance_{self.index}")
        detailsLayout.addWidget(label_rwy_dist_text, current_details_row, 0); detailsLayout.addWidget(self.dist_lbl, current_details_row, 1); current_details_row += 1
        label_rwy_azim_text = QtWidgets.QLabel("Azimuth (°):"); label_rwy_azim_text.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter)
        self.azim_lbl = QtWidgets.QLabel(CALC_PLACEHOLDER); self.azim_lbl.setObjectName(f"label_rwy_azimuth_{self.index}")
        detailsLayout.addWidget(label_rwy_azim_text, current_details_row, 0); detailsLayout.addWidget(self.azim_lbl, current_details_row, 1); current_details_row += 1
        label_runway_width = QtWidgets.QLabel("Runway Width (m):"); label_runway_width.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter)
        self.width_le = QtWidgets.QLineEdit(); self.width_le.setObjectName(f"lineEdit_runway_width_{self.index}"); self.width_le.setToolTip("Enter actual runway width (meters).")
        width_validator = QtGui.QDoubleValidator(0.01, 9999.99, 2, self); width_validator.setNotation(QtGui.QDoubleValidator.Notation.StandardNotation); self.width_le.setValidator(width_validator)
        detailsLayout.addWidget(label_runway_width, current_details_row, 0); detailsLayout.addWidget(self.width_le, current_details_row, 1); current_details_row += 1
        label_runway_shoulder = QtWidgets.QLabel("Runway Shoulder (m):"); label_runway_shoulder.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter)
        self.shoulder_le = QtWidgets.QLineEdit(); self.shoulder_le.setObjectName(f"lineEdit_rwy_shoulder_{self.index}"); self.shoulder_le.setToolTip("Enter width of runway shoulder (each side, if applicable).")
        # Use the same distance validator for shoulder
        self.shoulder_le.setValidator(self.distance_validator)
        detailsLayout.addWidget(label_runway_shoulder, current_details_row, 0); detailsLayout.addWidget(self.shoulder_le, current_details_row, 1); current_details_row += 1
        label_arc_num = QtWidgets.QLabel("ARC Number:"); label_arc_num.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter)
        self.arc_num_combo = QtWidgets.QComboBox(); self.arc_num_combo.setObjectName(f"comboBox_arc_num_{self.index}"); self.arc_num_combo.addItems(["", "1", "2", "3", "4"]); self.arc_num_combo.setToolTip("Select Aerodrome Reference Code Number"); self.arc_num_combo.setFocusPolicy(QtCore.Qt.FocusPolicy.StrongFocus)
        detailsLayout.addWidget(label_arc_num, current_details_row, 0); detailsLayout.addWidget(self.arc_num_combo, current_details_row, 1); current_details_row += 1
        label_arc_let = QtWidgets.QLabel("ARC Letter:"); label_arc_let.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter)
        self.arc_let_combo = QtWidgets.QComboBox(); self.arc_let_combo.setObjectName(f"comboBox_arc_let_{self.index}"); self.arc_let_combo.addItems(["", "A", "B", "C", "D", "E", "F"]); self.arc_let_combo.setToolTip("Select Aerodrome Reference Code Letter"); self.arc_let_combo.setFocusPolicy(QtCore.Qt.FocusPolicy.StrongFocus)
        detailsLayout.addWidget(label_arc_let, current_details_row, 0); detailsLayout.addWidget(self.arc_let_combo, current_details_row, 1); current_details_row += 1
        runway_types = ["", "Non-Instrument (NI)", "Non-Precision Approach (NPA)", "Precision Approach CAT I", "Precision Approach CAT II/III"]
        self.type1_lbl = QtWidgets.QLabel("(Primary End) Type:"); self.type1_lbl.setObjectName(f"label_type_desig1_{self.index}"); self.type1_lbl.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter)
        self.type1_combo = QtWidgets.QComboBox(); self.type1_combo.setObjectName(f"comboBox_type_desig1_{self.index}"); self.type1_combo.addItems(runway_types); self.type1_combo.setToolTip("Select type for primary end."); self.type1_combo.setFocusPolicy(QtCore.Qt.FocusPolicy.StrongFocus)
        detailsLayout.addWidget(self.type1_lbl, current_details_row, 0); detailsLayout.addWidget(self.type1_combo, current_details_row, 1); current_details_row += 1
        self.type2_lbl = QtWidgets.QLabel("(Reciprocal End) Type:"); self.type2_lbl.setObjectName(f"label_type_desig2_{self.index}"); self.type2_lbl.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter)
        self.type2_combo = QtWidgets.QComboBox(); self.type2_combo.setObjectName(f"comboBox_type_desig2_{self.index}"); self.type2_combo.addItems(runway_types); self.type2_combo.setToolTip("Select type for reciprocal end."); self.type2_combo.setFocusPolicy(QtCore.Qt.FocusPolicy.StrongFocus)
        detailsLayout.addWidget(self.type2_lbl, current_details_row, 0); detailsLayout.addWidget(self.type2_combo, current_details_row, 1); current_details_row += 1

        groupBox_layout.addLayout(detailsLayout) # Add details grid

        # --- Separator and Remove Button ---
        line_separator = QtWidgets.QFrame(); line_separator.setObjectName(f"line_runway_group_{self.index}"); line_separator.setFrameShape(QtWidgets.QFrame.Shape.HLine); line_separator.setFrameShadow(QtWidgets.QFrame.Shadow.Sunken)
        groupBox_layout.addWidget(line_separator)
        self.remove_button = QtWidgets.QPushButton("Remove This Runway"); self.remove_button.setObjectName(f"pushButton_remove_runway_{self.index}"); self.remove_button.setToolTip(f"Remove this runway")
        groupBox_layout.addWidget(self.remove_button)

    def _connect_signals(self):
        """Connect internal widget signals."""
        self.desig_le.textChanged.connect(self.inputChanged.emit)
        self.suffix_combo.currentIndexChanged.connect(self.inputChanged.emit)
        self.thr_east_le.textChanged.connect(self.inputChanged.emit)
        self.thr_north_le.textChanged.connect(self.inputChanged.emit)
        self.rec_east_le.textChanged.connect(self.inputChanged.emit)
        self.rec_north_le.textChanged.connect(self.inputChanged.emit)
        self.thr_elev_1_le.textChanged.connect(self.inputChanged.emit)
        self.thr_elev_2_le.textChanged.connect(self.inputChanged.emit)
        self.thr_displaced_1_le.textChanged.connect(self.inputChanged.emit)
        self.thr_displaced_2_le.textChanged.connect(self.inputChanged.emit)
        self.thr_pre_area_1_le.textChanged.connect(self.inputChanged.emit) # <<< NEW FIELD >>>
        self.thr_pre_area_2_le.textChanged.connect(self.inputChanged.emit) # <<< NEW FIELD >>>
        self.width_le.textChanged.connect(self.inputChanged.emit)
        self.shoulder_le.textChanged.connect(self.inputChanged.emit)
        self.arc_num_combo.currentIndexChanged.connect(self.inputChanged.emit)
        self.arc_let_combo.currentIndexChanged.connect(self.inputChanged.emit)
        self.type1_combo.currentIndexChanged.connect(self.inputChanged.emit)
        self.type2_combo.currentIndexChanged.connect(self.inputChanged.emit)
        self.remove_button.clicked.connect(self._emit_remove_request)

    def _emit_remove_request(self):
        """Emits the removeRequested signal with this group's index."""
        self.removeRequested.emit(self.index)

    def get_input_data(self) -> Dict[str, str]:
            """Retrieves all input values from the widgets in this group."""
            data = {
                    "designator_str": self.desig_le.text(),
                    "suffix": self.suffix_combo.currentText(),
                    "thr_easting": self.thr_east_le.text(),
                    "thr_northing": self.thr_north_le.text(),
                    "rec_easting": self.rec_east_le.text(),
                    "rec_northing": self.rec_north_le.text(),
                    "thr_elev_1": self.thr_elev_1_le.text(),
                    "thr_elev_2": self.thr_elev_2_le.text(),
                    "thr_displaced_1": self.thr_displaced_1_le.text(),
                    "thr_displaced_2": self.thr_displaced_2_le.text(),
                    "thr_pre_area_1": self.thr_pre_area_1_le.text(), # <<< NEW FIELD >>>
                    "thr_pre_area_2": self.thr_pre_area_2_le.text(), # <<< NEW FIELD >>>
                    "width": self.width_le.text(),
                    "shoulder": self.shoulder_le.text(),
                    "arc_num": self.arc_num_combo.currentText(),
                    "arc_let": self.arc_let_combo.currentText(),
                    "type1": self.type1_combo.currentText(),
                    "type2": self.type2_combo.currentText(),
            }
            return data

    def set_input_data(self, data: Dict[str, str]):
        """Populates the input widgets from a dictionary."""
        widgets_to_block = [
            self.desig_le, self.suffix_combo,
            self.thr_east_le, self.thr_north_le, self.rec_east_le, self.rec_north_le,
            self.thr_elev_1_le, self.thr_elev_2_le,
            self.thr_displaced_1_le, self.thr_displaced_2_le,
            self.thr_pre_area_1_le, self.thr_pre_area_2_le, # <<< NEW FIELDS >>>
            self.width_le, self.shoulder_le,
            self.arc_num_combo, self.arc_let_combo,
            self.type1_combo, self.type2_combo
        ]
        for w in widgets_to_block:
            if w: w.blockSignals(True)
        try:
            if self.desig_le: self.desig_le.setText(data.get("designator_str", ""))
            if self.suffix_combo: idx = self.suffix_combo.findText(data.get("suffix", ""), QtCore.Qt.MatchFlag.MatchFixedString); self.suffix_combo.setCurrentIndex(idx if idx >= 0 else 0)
            if self.thr_east_le: self.thr_east_le.setText(data.get("thr_easting", ""))
            if self.thr_north_le: self.thr_north_le.setText(data.get("thr_northing", ""))
            if self.rec_east_le: self.rec_east_le.setText(data.get("rec_easting", ""))
            if self.rec_north_le: self.rec_north_le.setText(data.get("rec_northing", ""))
            if self.thr_elev_1_le: self.thr_elev_1_le.setText(data.get("thr_elev_1", ""))
            if self.thr_elev_2_le: self.thr_elev_2_le.setText(data.get("thr_elev_2", ""))
            if self.thr_displaced_1_le: self.thr_displaced_1_le.setText(data.get("thr_displaced_1", ""))
            if self.thr_displaced_2_le: self.thr_displaced_2_le.setText(data.get("thr_displaced_2", ""))
            if self.thr_pre_area_1_le: self.thr_pre_area_1_le.setText(data.get("thr_pre_area_1", "")) # <<< NEW FIELD >>>
            if self.thr_pre_area_2_le: self.thr_pre_area_2_le.setText(data.get("thr_pre_area_2", "")) # <<< NEW FIELD >>>
            if self.width_le: self.width_le.setText(data.get("width", ""))
            if self.shoulder_le: self.shoulder_le.setText(data.get("shoulder", ""))
            if self.arc_num_combo: idx = self.arc_num_combo.findText(data.get("arc_num", ""), QtCore.Qt.MatchFlag.MatchFixedString); self.arc_num_combo.setCurrentIndex(idx if idx >= 0 else 0)
            if self.arc_let_combo: idx = self.arc_let_combo.findText(data.get("arc_let", ""), QtCore.Qt.MatchFlag.MatchFixedString); self.arc_let_combo.setCurrentIndex(idx if idx >= 0 else 0)
            if self.type1_combo: idx = self.type1_combo.findText(data.get("type1", ""), QtCore.Qt.MatchFlag.MatchFixedString); self.type1_combo.setCurrentIndex(idx if idx >= 0 else 0)
            if self.type2_combo: idx = self.type2_combo.findText(data.get("type2", ""), QtCore.Qt.MatchFlag.MatchFixedString); self.type2_combo.setCurrentIndex(idx if idx >= 0 else 0)
        finally:
            for w in widgets_to_block:
                 if w: w.blockSignals(False)
            self.inputChanged.emit() # Trigger calculations/updates

    def update_display_labels(self, results: Dict[str, str]):
        """Updates the calculated display labels within this group."""
        if self.rec_desig_hdr_lbl: self.rec_desig_hdr_lbl.setText(results.get("reciprocal_desig_full", NA_PLACEHOLDER))
        if self.rwy_name_lbl: self.rwy_name_lbl.setText(results.get("runway_name", WIDGET_MISSING_MSG))
        if self.dist_lbl: self.dist_lbl.setText(results.get("distance", WIDGET_MISSING_MSG))
        if self.azim_lbl: self.azim_lbl.setText(results.get("azimuth", WIDGET_MISSING_MSG))
        if self.type1_lbl: self.type1_lbl.setText(results.get("type1_label_text", "(Primary End) Type:"))
        if self.type2_lbl: self.type2_lbl.setText(results.get("type2_label_text", "(Reciprocal End) Type:"))

    def clear_inputs(self):
        """Clears all input fields in this group."""
        widgets_to_block = [
            self.desig_le, self.suffix_combo,
            self.thr_east_le, self.thr_north_le, self.rec_east_le, self.rec_north_le,
            self.thr_elev_1_le, self.thr_elev_2_le,
            self.thr_displaced_1_le, self.thr_displaced_2_le,
            self.thr_pre_area_1_le, self.thr_pre_area_2_le, # <<< NEW FIELDS >>>
            self.width_le, self.shoulder_le,
            self.arc_num_combo, self.arc_let_combo,
            self.type1_combo, self.type2_combo
        ]
        for w in widgets_to_block:
            if w: w.blockSignals(True)
        try:
            if self.desig_le: self.desig_le.clear()
            if self.suffix_combo: self.suffix_combo.setCurrentIndex(0)
            if self.thr_east_le: self.thr_east_le.clear()
            if self.thr_north_le: self.thr_north_le.clear()
            if self.rec_east_le: self.rec_east_le.clear()
            if self.rec_north_le: self.rec_north_le.clear()
            if self.thr_elev_1_le: self.thr_elev_1_le.clear()
            if self.thr_elev_2_le: self.thr_elev_2_le.clear()
            if self.thr_displaced_1_le: self.thr_displaced_1_le.clear()
            if self.thr_displaced_2_le: self.thr_displaced_2_le.clear()
            if self.thr_pre_area_1_le: self.thr_pre_area_1_le.clear() # <<< NEW FIELD >>>
            if self.thr_pre_area_2_le: self.thr_pre_area_2_le.clear() # <<< NEW FIELD >>>
            if self.width_le: self.width_le.clear()
            if self.shoulder_le: self.shoulder_le.clear()
            if self.arc_num_combo: self.arc_num_combo.setCurrentIndex(0)
            if self.arc_let_combo: self.arc_let_combo.setCurrentIndex(0)
            if self.type1_combo: self.type1_combo.setCurrentIndex(0)
            if self.type2_combo: self.type2_combo.setCurrentIndex(0)
        finally:
            for w in widgets_to_block:
                if w: w.blockSignals(False)
            self.inputChanged.emit() # Trigger calculations/updates


# =========================================================================
# == Main Dialog Class
# =========================================================================
class SafeguardingBuilderDialog(QtWidgets.QDialog, FORM_CLASS):
    """ Dialog class for user input. """
    def __init__(self, parent=None):
        """Constructor."""
        super().__init__(parent)
        self.setupUi(self)

        self._runway_id_counter = 0
        self._runway_groups: Dict[int, RunwayWidgetGroup] = {}
        self.scroll_area_layout: Optional[QtWidgets.QVBoxLayout] = None

        # --- Scroll Area Setup ---
        scroll_area = self.findChild(QtWidgets.QScrollArea, 'scrollArea_runways')
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
                     QgsMessageLog.logMessage("Critical: Scroll area content widget layout is not QVBoxLayout.", DIALOG_LOG_TAG, level=Qgis.Critical)
                     self.scroll_area_layout = layout # Assign anyway
            else:
                 QgsMessageLog.logMessage("Critical: Scroll area content widget missing.", DIALOG_LOG_TAG, level=Qgis.Critical)
        else:
             QgsMessageLog.logMessage("Critical: scrollArea_runways not found in UI.", DIALOG_LOG_TAG, level=Qgis.Critical)

        add_runway_button = self.findChild(QtWidgets.QPushButton, 'pushButton_add_runway')
        if not self.scroll_area_layout:
            QgsMessageLog.logMessage("Critical: Scroll area layout unavailable.", DIALOG_LOG_TAG, level=Qgis.Critical)
            if add_runway_button: add_runway_button.setEnabled(False); add_runway_button.setToolTip("Layout missing.")

        # --- Setup Coordinate Validators ---
        self.coord_validator = QtGui.QDoubleValidator()
        self.coord_validator.setNotation(QtGui.QDoubleValidator.Notation.StandardNotation)
        self.numeric_validator = QtGui.QDoubleValidator()
        self.numeric_validator.setNotation(QtGui.QDoubleValidator.Notation.StandardNotation)

        self._setup_arp_validators(self.coord_validator, self.numeric_validator)
        self._connect_global_controls()

        # --- Connect Action Buttons ---
        clear_button = self.findChild(QtWidgets.QPushButton, "pushButton_clear_all")
        save_button = self.findChild(QtWidgets.QPushButton, "pushButton_save_data")
        load_button = self.findChild(QtWidgets.QPushButton, "pushButton_load_data")
        if clear_button: clear_button.clicked.connect(self.clear_all_inputs)
        if save_button: save_button.clicked.connect(self.save_input_data)
        if load_button: load_button.clicked.connect(self.load_input_data)

        self._setup_cns_manual_entry()

        # ### NEW: Setup for output options ###
        self._setup_output_options_ui_connections()
        # ### END NEW ###

        if self.scroll_area_layout:
            self.add_runway_group() # Add the first group
        else:
            QgsMessageLog.logMessage("Warning: Could not add initial runway group (layout missing).", DIALOG_LOG_TAG, level=Qgis.Warning)

        QtCore.QTimer.singleShot(0, self._update_dialog_height)

    ### NEW: Method to setup output options UI and connections ###
    def _setup_output_options_ui_connections(self):
        """
        Sets up the UI elements related to output options (memory vs. file).
        Assumes widgets like self.radioMemoryOutput, self.radioFileOutput,
        self.fileWidgetOutputPath, self.comboOutputFormat exist from the .ui file.
        """
        # --- Get references to the new UI elements ---
        # These should be attributes after self.setupUi() if named correctly in Qt Designer
        # Example object names:
        # self.radioMemoryOutput (QRadioButton)
        # self.radioFileOutput (QRadioButton)
        # self.fileWidgetOutputPath (QgsFileWidget)
        # self.comboOutputFormat (QComboBox)

        missing_widgets = []
        if not hasattr(self, 'radioMemoryOutput'): missing_widgets.append("radioMemoryOutput")
        if not hasattr(self, 'radioFileOutput'): missing_widgets.append("radioFileOutput")
        if not hasattr(self, 'fileWidgetOutputPath'): missing_widgets.append("fileWidgetOutputPath")
        if not hasattr(self, 'comboOutputFormat'): missing_widgets.append("comboOutputFormat")

        if missing_widgets:
            QgsMessageLog.logMessage(
                f"Output options UI setup incomplete. Missing widgets: {', '.join(missing_widgets)}",
                DIALOG_LOG_TAG, level=Qgis.Critical
            )
            # Disable functionality or show error to user if critical
            if hasattr(self, 'pushButton_generateSurfaces'): # Assuming your main generate button
                 self.pushButton_generateSurfaces.setEnabled(False)
                 self.pushButton_generateSurfaces.setToolTip("Output options UI is misconfigured.")
            return

        # Populate format combo box
        self.comboOutputFormat.clear()
        for display_name in OUTPUT_FORMATS.keys():
            self.comboOutputFormat.addItem(display_name)
        
        if DEFAULT_OUTPUT_FORMAT in OUTPUT_FORMATS:
            self.comboOutputFormat.setCurrentText(DEFAULT_OUTPUT_FORMAT)

        # Set initial states
        self.radioMemoryOutput.setChecked(True)
        # self.radioFileOutput.setChecked(False) # Implicitly false if Memory is true

        # Configure QgsFileWidget
        self.fileWidgetOutputPath.setStorageMode(1)
        self._update_file_widget_filter() # Set initial filter

        # Connect signals
        self.radioMemoryOutput.toggled.connect(self._on_output_option_changed)
        # radioFileOutput also triggers toggled on radioMemoryOutput, so one connection is enough for the group
        self.comboOutputFormat.currentIndexChanged.connect(self._update_file_widget_filter)

        # Initial UI update based on default selection
        self._on_output_option_changed()

    def _on_output_option_changed(self):
        """
        Updates the enabled state of file output widgets based on radio button selection.
        """
        is_file_output = self.radioFileOutput.isChecked()
        self.fileWidgetOutputPath.setEnabled(is_file_output)
        self.comboOutputFormat.setEnabled(is_file_output)
        
        # Optionally, clear the file path if switching back to memory
        # if not is_file_output:
        #     self.fileWidgetOutputPath.setFilePath("")

    def _update_file_widget_filter(self):
        """
        Updates the QgsFileWidget's file filter based on the selected format
        in comboOutputFormat.
        """
        selected_format_name = self.comboOutputFormat.currentText()
        if selected_format_name in OUTPUT_FORMATS:
            _driver, user_name, extension = OUTPUT_FORMATS[selected_format_name]
            filter_string = f"{user_name} (*{extension})"
            
            # Add other formats to the filter string for convenience in the dialog
            other_formats = []
            for key, (_drv, usr_name, ext) in OUTPUT_FORMATS.items():
                if key != selected_format_name:
                    other_formats.append(f"{usr_name} (*{ext})")
            if other_formats:
                filter_string += ";;" + ";;".join(other_formats)
            
            self.fileWidgetOutputPath.setFilter(filter_string)

            # Try to update the default extension in the file dialog
            # This is a bit tricky as QgsFileWidget doesn't directly expose default Suffix
            # but setting it as part of the path might work if path is empty.
            # if not self.fileWidgetOutputPath.filePath():
            #    self.fileWidgetOutputPath.setFilePath(f"output{extension}") # Placeholder
            #    self.fileWidgetOutputPath.setFilePath("") # Clear it
        else:
            self.fileWidgetOutputPath.setFilter(self.tr("All files (*.*)"))
    ### END NEW ###

    # --- Initialization Helpers (no changes needed here) ---
    def _setup_arp_validators(self, coord_validator: QtGui.QDoubleValidator, numeric_validator: QtGui.QDoubleValidator):
        """Finds ARP/MET widgets and applies validators."""
        widgets_to_validate = [
            ('lineEdit_arp_easting', coord_validator),
            ('lineEdit_arp_northing', coord_validator),
            ('lineEdit_arp_elevation', numeric_validator),
            ('lineEdit_met_easting', coord_validator),
            ('lineEdit_met_northing', coord_validator)
        ]
        tooltips = {
            'lineEdit_arp_easting': "Airport Reference Point (ARP) Easting Coordinate",
            'lineEdit_arp_northing': "Airport Reference Point (ARP) Northing Coordinate",
            'lineEdit_arp_elevation': "Airport Reference Point (ARP) Elevation (AMSL)",
            'lineEdit_met_easting': "MET Station Easting Coordinate (Optional)",
            'lineEdit_met_northing': "MET Station Northing Coordinate (Optional)"
        }
        placeholders = {
            'lineEdit_arp_easting': "e.g., 455000.00",
            'lineEdit_arp_northing': "e.g., 5772000.00",
            'lineEdit_arp_elevation': "e.g., 150.0",
            'lineEdit_met_easting': "e.g., 455100.00",
            'lineEdit_met_northing': "e.g., 5772100.00"
        }
        for name, validator in widgets_to_validate:
            widget = getattr(self, name, self.findChild(QtWidgets.QLineEdit, name))
            if widget:
                widget.setValidator(validator)
                widget.setToolTip(tooltips.get(name, ""))
                widget.setPlaceholderText(placeholders.get(name, ""))
            else:
                QgsMessageLog.logMessage(f"Warning: QLineEdit '{name}' not found.", DIALOG_LOG_TAG, level=Qgis.Warning)

    def _connect_global_controls(self):
        """Connects signals for global widgets."""
        airport_name_le = getattr(self, 'lineEdit_airport_name', self.findChild(QtWidgets.QLineEdit, 'lineEdit_airport_name'))
        add_runway_button = getattr(self, 'pushButton_add_runway', self.findChild(QtWidgets.QPushButton, 'pushButton_add_runway'))

        if airport_name_le:
            airport_name_le.textChanged.connect(self.update_all_runway_calculations)
        else: QgsMessageLog.logMessage("Warning: 'lineEdit_airport_name' not found.", DIALOG_LOG_TAG, level=Qgis.Warning)

        if add_runway_button and self.scroll_area_layout:
            add_runway_button.clicked.connect(self.add_runway_group)
        elif not add_runway_button: QgsMessageLog.logMessage("Warning: 'pushButton_add_runway' not found.", DIALOG_LOG_TAG, level=Qgis.Warning)
        elif not self.scroll_area_layout: QgsMessageLog.logMessage("Warning: 'pushButton_add_runway' not connected (layout missing).", DIALOG_LOG_TAG, level=Qgis.Warning)

    def _setup_cns_manual_entry(self):
        """Sets up the CNS Manual Entry table and connects signals."""
        cns_table = getattr(self, 'table_cns_facility', self.findChild(QtWidgets.QTableWidget, 'table_cns_facility'))
        add_button = getattr(self, 'pushButton_add_CNS', self.findChild(QtWidgets.QPushButton, 'pushButton_add_CNS'))
        remove_button = getattr(self, 'pushButton_remove_CNS', self.findChild(QtWidgets.QPushButton, 'pushButton_remove_CNS'))

        if not all([cns_table, add_button, remove_button]):
            QgsMessageLog.logMessage("Critical: CNS Manual Entry setup failed - widgets missing.", DIALOG_LOG_TAG, level=Qgis.Critical)
            return

        cns_table.setColumnCount(4)
        cns_table.setHorizontalHeaderLabels(["Facility Type", "Easting/X", "Northing/Y", "Elev (AMSL)"])
        add_button.clicked.connect(self.add_cns_row)
        remove_button.clicked.connect(self.remove_cns_rows)
        add_button.setToolTip("Add a new row to enter a CNS facility manually.")
        remove_button.setToolTip("Remove the selected CNS facility row(s).")

        self.CNS_FACILITY_TYPES = sorted([
            "High Frequency (HF)", "Very High Frequency (VHF)", "Satellite Ground Station (SGS)",
            "Non-Directional Beacon (NDB)", "Distance Measuring Equipment (DME)",
            "VHF Omni-Directional Range (VOR)", "Conventional VHF Omni-Directional Range (CVOR)",
            "Doppler VHF Omni-Directional Range (DVOR) - Elevated",
            "Doppler VHF Omni-Directional Range (DVOR) - Ground Mounted",
            "Middle and Outer Marker", "Automatic Dependent Surveillance Broadcast (ADS-B)",
            "Wide Area Multilateration (WAM)", "Primary Surveillance Radar (PSR)",
            "Secondary Surveillance Radar (SSR)", "Ground Based Augmentation System (GBAS) - RSMU",
            "GBAS - VDB", "Link Dishes", "Radar Site Monitor - Type A", "Radar Site Monitor - Type B",
            "Glide Path (GP)", "Localiser (LOC)"
        ])

    # --- Runway Group Management (no changes needed here) ---
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
            icao_le = getattr(self, 'lineEdit_airport_name', self.findChild(QtWidgets.QLineEdit, "lineEdit_airport_name"))
            icao_code = icao_le.text().strip().upper() if icao_le else "" # Get ICAO code early
        
            # --- Initialize Results ---
            calculation_results = { # Default/error values
                "reciprocal_desig_full": NA_PLACEHOLDER, "runway_name": WIDGET_MISSING_MSG, # Default name
                "distance": WIDGET_MISSING_MSG, "azimuth": WIDGET_MISSING_MSG,
                "type1_label_text": "(Primary End) Type:", "type2_label_text": "(Reciprocal End) Type:",
            }
        
            # --- Perform Calculations ---
            try:
                # Designator & Name
                rwy_desig_str = input_data.get('designator_str')
                rwy_suffix = input_data.get('suffix', '')
                # Initialize placeholders for calculated values
                full_desig_1_str, full_desig_2_str = "??", "??"
                compact_desig_1, compact_desig_2 = "??", "??" # <<< NEW: For compact format
                type1_label_str, type2_label_str = calculation_results["type1_label_text"], calculation_results["type2_label_text"]
                rwy_name_str = calculation_results["runway_name"] # Start with default
                
                try: # Inner try for designation math
                    if not rwy_desig_str: raise ValueError("Designation empty")
                    rwy_desig_val = int(rwy_desig_str);
                    if not (1 <= rwy_desig_val <= 36): raise ValueError("Designation out of range (1-36)")
                
                    # Calculate primary designation (both formats)
                    compact_desig_1 = f"{rwy_desig_val:02d}{rwy_suffix}"     # e.g., "09L"
                    full_desig_1_str = f"RWY {compact_desig_1}"             # e.g., "RWY 09L" (still needed for type labels)
                    type1_label_str = f"{full_desig_1_str} Approach Type:" # Update type label text
                
                    # Calculate reciprocal designation (both formats)
                    reciprocal_val = (rwy_desig_val + 18) if rwy_desig_val <= 18 else (rwy_desig_val - 18)
                    rec_desig_num_str = f"{reciprocal_val:02d}"             # e.g., "27"
                    rec_suffix_map = {"L": "R", "R": "L", "C": "C", "": ""}
                    rec_suffix = rec_suffix_map.get(rwy_suffix, "")        # e.g., "R"
                    compact_desig_2 = f"{rec_desig_num_str}{rec_suffix}"    # e.g., "27R"
                    full_desig_2_str = f"RWY {compact_desig_2}"            # e.g., "RWY 27R" (needed for header + type label)
                    type2_label_str = f"{full_desig_2_str} Approach Type:" # Update type label text
                
                    # <<< MODIFIED: Construct the runway name label in the desired format >>>
                    combined_compact_desigs = f"{compact_desig_1}/{compact_desig_2}" # e.g., "09L/27R"
                    if icao_code:
                        rwy_name_str = f"{icao_code} Runway {combined_compact_desigs}" # e.g., "EGLL Runway 09L/27R"
                    else:
                        rwy_name_str = f"Runway {combined_compact_desigs}"          # e.g., "Runway 09L/27R"
                        
                except ValueError:
                    # Handle invalid designation input
                    full_desig_2_str = "Invalid" # Keep this for the header label update
                    rwy_name_str = "Invalid Designation" # Set error message for the main label
                    
                # Update results dictionary with calculated values
                calculation_results.update({
                    "reciprocal_desig_full": full_desig_2_str, # Used for the header label above coords
                    "runway_name": rwy_name_str,               # <<< Uses the newly formatted string >>>
                    "type1_label_text": type1_label_str,
                    "type2_label_text": type2_label_str
                })
                
                # Distance & Azimuth (calculation logic remains the same)
                thr_east_str = input_data.get('thr_easting')
                thr_north_str = input_data.get('thr_northing')
                rec_thr_east_str = input_data.get('rec_easting')
                rec_thr_north_str = input_data.get('rec_northing')
                distance_str, azimuth_str = ENTER_COORDS_MSG, ENTER_COORDS_MSG
                if all([thr_east_str, thr_north_str, rec_thr_east_str, rec_thr_north_str]):
                    try: # Inner try for coordinate math
                        p1 = QgsPointXY(float(thr_east_str), float(thr_north_str))
                        p2 = QgsPointXY(float(rec_thr_east_str), float(rec_thr_north_str))
                        dist = p1.distance(p2)
                        distance_str = f"{dist:.2f}"
                        ZERO_TOL, NEAR_TOL = 1e-6, 0.1
                        if math.isclose(dist, 0.0, abs_tol=ZERO_TOL):
                            azimuth_str = SAME_POINT_MSG + (f" (<{NEAR_TOL}m)" if ZERO_TOL < dist < NEAR_TOL else "")
                        else:
                            az = p1.azimuth(p2) % 360
                            azimuth_str = f"{az:.2f}" + (f" ({NEAR_POINTS_MSG})" if dist < NEAR_TOL else "")
                    except ValueError: distance_str, azimuth_str = INVALID_COORDS_MSG, INVALID_COORDS_MSG
                    except Exception as e_coord:
                        QgsMessageLog.logMessage(f"Coord calc error Rwy {runway_index}: {e_coord}", DIALOG_LOG_TAG, level=Qgis.Warning)
                        distance_str, azimuth_str = CALC_ERROR_MSG, CALC_ERROR_MSG
                calculation_results["distance"] = distance_str
                calculation_results["azimuth"] = azimuth_str
                
            except Exception as e_outer:
                QgsMessageLog.logMessage(f"Outer calc error Rwy {runway_index}: {e_outer}", DIALOG_LOG_TAG, level=Qgis.Critical)
                # Reset results to error state
                calculation_results = { k: CALC_ERROR_MSG for k in calculation_results }
                calculation_results["type1_label_text"] = "(Primary End) Type:" # Reset labels
                calculation_results["type2_label_text"] = "(Reciprocal End) Type:"
                
            # --- Update the group's display labels ---
            group_widget.update_display_labels(calculation_results) # This will now use the correctly formatted "runway_name"
            
    def add_runway_group(self):
        """Creates and adds a new RunwayWidgetGroup instance."""
        if not self.scroll_area_layout:
            QMessageBox.critical(self, "Layout Error", "Scroll area layout missing.")
            return

        runway_index = self._get_next_runway_id()
        scroll_content_widget = self.findChild(QtWidgets.QScrollArea, 'scrollArea_runways').widget()
        if not scroll_content_widget:
             QMessageBox.critical(self, "Layout Error", "Scroll area content widget missing.")
             return

        # Pass all arguments positionally
        new_group = RunwayWidgetGroup(runway_index, self.coord_validator, scroll_content_widget)

        new_group.inputChanged.connect(lambda idx=runway_index: self.update_runway_calculations(idx))
        new_group.removeRequested.connect(self.remove_runway_group)

        # Add to the end of the layout
        self.scroll_area_layout.addWidget(new_group)

        self._runway_groups[runway_index] = new_group
        self._update_dialog_height()
        self.update_runway_calculations(runway_index) # Update placeholders

    def remove_runway_group(self, runway_index_to_remove: int):
        """Handles request to remove a runway group after confirmation."""
        if runway_index_to_remove not in self._runway_groups:
            QgsMessageLog.logMessage(f"Cannot remove: Index {runway_index_to_remove} not found.", DIALOG_LOG_TAG, level=Qgis.Warning)
            return

        group_to_remove = self._runway_groups[runway_index_to_remove]
        runway_display_name = f"Runway {runway_index_to_remove}" # Default
        try:
            name = group_to_remove.rwy_name_lbl.text()
            placeholders = [CALC_PLACEHOLDER, WIDGET_MISSING_MSG, "", None, "Invalid Designation", "Invalid", CALC_ERROR_MSG]
            if name and name not in placeholders: runway_display_name = name
        except AttributeError: pass

        confirmation_message = self.tr("Remove '{name}'?").format(name=runway_display_name)
        reply = QtWidgets.QMessageBox.question(self, self.tr('Confirm Removal'), confirmation_message,
                                             QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No,
                                             QtWidgets.QMessageBox.StandardButton.No)

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
        elif not group_to_remove: QgsMessageLog.logMessage(f"Internal removal Warn: Group {runway_index} not found.", DIALOG_LOG_TAG, level=Qgis.Warning)
        elif not self.scroll_area_layout: QgsMessageLog.logMessage(f"Internal removal Critical: Layout missing, cannot remove widget {runway_index}.", DIALOG_LOG_TAG, level=Qgis.Critical)

    def _update_dialog_height(self):
        """Adjusts the dialog height to fit its contents."""
        QtCore.QTimer.singleShot(0, self.adjustSize)

    # --- CNS Manual Entry Methods (no changes needed here) ---
    def add_cns_row(self):
        """Adds a new, empty row to the CNS facilities table."""
        cns_table = getattr(self, 'table_cns_facility', self.findChild(QtWidgets.QTableWidget, 'table_cns_facility'))
        if not cns_table:
            QgsMessageLog.logMessage("Add CNS Row Error: Table widget 'table_cns_facility' not found.", DIALOG_LOG_TAG, level=Qgis.Critical)
            return

        if not hasattr(self, 'CNS_FACILITY_TYPES') or not self.CNS_FACILITY_TYPES:
             QgsMessageLog.logMessage("Add CNS Row Error: CNS_FACILITY_TYPES list not defined.", DIALOG_LOG_TAG, level=Qgis.Critical)
             QMessageBox.critical(self, "Configuration Error", "Cannot add CNS row: Facility types list is missing.")
             return

        try:
            row_position = cns_table.rowCount()
            cns_table.insertRow(row_position)

            combo_type = QComboBox()
            combo_type.setObjectName(f"cnsComboType_{row_position}")
            combo_type.addItems([""] + self.CNS_FACILITY_TYPES)
            combo_type.setCurrentIndex(0)
            combo_type.setToolTip("Select the type of CNS facility.")
            cns_table.setCellWidget(row_position, 0, combo_type)

            item_x = QTableWidgetItem("")
            item_x.setToolTip("Enter Easting or X coordinate (in Project CRS).")
            cns_table.setItem(row_position, 1, item_x)

            item_y = QTableWidgetItem("")
            item_y.setToolTip("Enter Northing or Y coordinate (in Project CRS).")
            cns_table.setItem(row_position, 2, item_y)

            item_elev = QTableWidgetItem("")
            item_elev.setToolTip("Enter Elevation AMSL (Optional). Leave blank if unknown.")
            cns_table.setItem(row_position, 3, item_elev)

            cns_table.scrollToItem(item_x, QAbstractItemView.ScrollHint.EnsureVisible)
            combo_type.setFocus()
            self._update_dialog_height()

        except Exception as e:
             QgsMessageLog.logMessage(f"Add CNS Row Error during row/widget creation: {e}", DIALOG_LOG_TAG, level=Qgis.Critical)
             QMessageBox.critical(self, "Error", f"Failed to add CNS row:\n{e}")

    def remove_cns_rows(self):
        """Removes the currently selected row(s) from the CNS table."""
        cns_table = getattr(self, 'table_cns_facility', self.findChild(QtWidgets.QTableWidget, 'table_cns_facility'))
        if not cns_table:
            QgsMessageLog.logMessage("Remove CNS Row Error: Table widget 'table_cns_facility' not found.", DIALOG_LOG_TAG, level=Qgis.Critical)
            return

        selected_indices = cns_table.selectionModel().selectedRows()
        if not selected_indices:
            QMessageBox.information(self, self.tr("Remove Rows"), self.tr("No CNS facility rows selected to remove."))
            return

        selected_rows = sorted([index.row() for index in selected_indices], reverse=True)
        reply = QMessageBox.question(self, self.tr('Confirm Removal'),
                                     self.tr("Are you sure you want to remove the {n} selected CNS facility row(s)?").format(n=len(selected_rows)),
                                     QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No,
                                     QtWidgets.QMessageBox.StandardButton.No)

        if reply == QtWidgets.QMessageBox.StandardButton.Yes:
            try:
                for row_index in selected_rows:
                    cns_table.removeRow(row_index)
                self._update_dialog_height()
            except Exception as e:
                QgsMessageLog.logMessage(f"Remove CNS Row Error during row removal: {e}", DIALOG_LOG_TAG, level=Qgis.Critical)
                QMessageBox.critical(self, "Error", f"Failed to remove CNS rows:\n{e}")

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
        output_option_widgets_exist = all(hasattr(self, name) for name in 
                                          ['radioMemoryOutput', 'radioFileOutput', 
                                           'fileWidgetOutputPath', 'comboOutputFormat'])
        if not output_option_widgets_exist:
            QMessageBox.critical(self, "UI Configuration Error",
                                 "Output option widgets are missing from the dialog. Cannot proceed.")
            return None

        # --- Global Inputs ---
        icao, arp_pt, arp_e, arp_n, arp_elev, met_pt = self._get_global_inputs()
        if icao is None: # Critical failure
            return None

        final_data.update({
            'icao_code': icao, 'arp_point': arp_pt, 'arp_easting': arp_e,
            'arp_northing': arp_n, 'arp_elevation': arp_elev, 'met_point': met_pt
        })

        # --- Runway Inputs ---
        runway_data_list = []
        if not self._runway_groups:
            validation_ok = False; error_messages.append("At least one runway definition is required.")
        else:
            for index, group_widget in sorted(self._runway_groups.items()):
                runway_inputs = group_widget.get_input_data()
                validated_runway = self._validate_runway_data(index, runway_inputs, error_messages)
                if validated_runway:
                    # Ensure keys exist (validator should add them, but be safe)
                    validated_runway.setdefault('thr_elev_1', None)
                    validated_runway.setdefault('thr_elev_2', None)
                    validated_runway.setdefault('thr_displaced_1', None)
                    validated_runway.setdefault('thr_displaced_2', None)
                    validated_runway.setdefault('thr_pre_area_1', None) # <<< NEW KEY CHECK >>>
                    validated_runway.setdefault('thr_pre_area_2', None) # <<< NEW KEY CHECK >>>
                    runway_data_list.append(validated_runway)
                else:
                    validation_ok = False # Error messages added by validator

        if not validation_ok:
            QMessageBox.critical(self, "Input Error",
                                "Please correct the following errors:\n- " + "\n- ".join(error_messages))
            return None
        final_data['runways'] = runway_data_list

        # --- CNS Inputs ---
        cns_data = self._get_cns_manual_data()
        if cns_data is None: return None
        final_data['cns_facilities'] = cns_data

        # --- Output Options ---
        if self.radioMemoryOutput.isChecked():
            final_data['output_mode'] = 'memory'
            final_data['output_path'] = None
            final_data['output_format_driver'] = None
            final_data['output_format_extension'] = None
        elif self.radioFileOutput.isChecked():
            final_data['output_mode'] = 'file'
            raw_path_from_widget = self.fileWidgetOutputPath.filePath().strip()
            selected_format_name = self.comboOutputFormat.currentText()
            
            output_path = "" # Initialize output_path to ensure it's always defined
            
            if not raw_path_from_widget:
                # This case is handled by the 'if not output_path:' check later
                pass # output_path remains ""
            elif os.path.isdir(raw_path_from_widget):
                output_path = raw_path_from_widget
            elif os.path.isfile(raw_path_from_widget):
                output_path = os.path.dirname(raw_path_from_widget)
                QgsMessageLog.logMessage(f"Output path ('{raw_path_from_widget}') was a file; using its directory: '{output_path}'.", DIALOG_LOG_TAG, Qgis.Info)
            else: 
                # Path doesn't exist as a file or directory.
                # Try to see if its dirname is an existing directory (e.g., user typed /existing_dir/new_dir_name)
                potential_dir = os.path.dirname(raw_path_from_widget)
                if os.path.exists(potential_dir) and os.path.isdir(potential_dir):
                    output_path = potential_dir
                    QgsMessageLog.logMessage(f"Output path ('{raw_path_from_widget}') was not existing file/dir; using its parent: '{output_path}'.", DIALOG_LOG_TAG, Qgis.Info)
                else:
                    # Assume raw_path_from_widget is the intended directory if QgsFileWidget in directory mode returned it.
                    # The backend's os.path.isdir() will be the final check.
                    output_path = raw_path_from_widget 
                    QgsMessageLog.logMessage(f"Output path ('{raw_path_from_widget}') is being treated as a directory. Backend will verify.", DIALOG_LOG_TAG, Qgis.Info)
                    
            # Now validate the derived/raw output_path and selected_format_name
            if not output_path:
                validation_ok = False
                error_messages.append("Output directory path is required.")
            elif selected_format_name not in OUTPUT_FORMATS:
                validation_ok = False
                error_messages.append(f"Invalid output format selected: {selected_format_name}.")
            else:
                # If validation_ok is still True up to this point
                driver_name, _, extension = OUTPUT_FORMATS[selected_format_name]
                final_data['output_path'] = output_path # Store the processed directory path
                final_data['output_format_driver'] = driver_name
                final_data['output_format_extension'] = extension
                # The block that adjusted output_path based on extension is removed,
                # as self.output_path is now a directory, not a full file path.
                # The backend (_create_and_add_layer) now constructs the full file path.
                
        else: 
            validation_ok = False
            error_messages.append("No output mode selected (memory or file).")
            
        # --- Final Validation Check and Return ---
        # This part should be OUTSIDE the 'Output Options' if/elif/else block,
        # but still within get_all_input_data before returning.
        # The 'validation_ok' flag and 'error_messages' list are accumulated throughout.
        if not validation_ok:
            QMessageBox.critical(self, "Input Error",
                                "Please correct the following errors:\n- " + "\n- ".join(error_messages))
            return None

        # Add dissolve option (this was correctly placed)
        if hasattr(self, 'checkBox_dissolveLayers') and self.checkBox_dissolveLayers:
            final_data['dissolve_output'] = self.checkBox_dissolveLayers.isChecked()
        else:
            final_data['dissolve_output'] = False
            
        return final_data

    # <<< UPDATED >>>
    def _validate_runway_data(self, index: int, inputs: Dict[str, str], errors: List[str]) -> Optional[Dict[str, Any]]:
        """Validates raw inputs for a single runway."""
        validated = {'original_index': index}
        current_errors = 0

        # Designator
        desig_str = inputs.get('designator_str', '')
        try:
            desig_val = int(desig_str)
            if not (1 <= desig_val <= 36): raise ValueError("Designator must be 01-36")
            validated['designator_num'] = desig_val
            validated['suffix'] = inputs.get('suffix', '')
        except ValueError as e:
            errors.append(f"Rwy {index}: Invalid primary designator '{desig_str}'. ({e})")
            current_errors += 1; validated['designator_num'] = None

        # Coordinates (Threshold 1)
        thr_east_str = inputs.get('thr_easting', '')
        thr_north_str = inputs.get('thr_northing', '')
        try:
            thr_east_f = float(thr_east_str); thr_north_f = float(thr_north_str)
            validated['thr_point'] = QgsPointXY(thr_east_f, thr_north_f)
        except (ValueError, TypeError) as e:
            errors.append(f"Rwy {index}: Invalid primary threshold coordinates (E='{thr_east_str}', N='{thr_north_str}'). {e}")
            validated['thr_point'] = None; current_errors += 1

        # Coordinates (Threshold 2)
        rec_east_str = inputs.get('rec_easting', '')
        rec_north_str = inputs.get('rec_northing', '')
        try:
            rec_east_f = float(rec_east_str); rec_north_f = float(rec_north_str)
            validated['rec_thr_point'] = QgsPointXY(rec_east_f, rec_north_f)
        except (ValueError, TypeError) as e:
            errors.append(f"Rwy {index}: Invalid reciprocal threshold coordinates (E='{rec_east_str}', N='{rec_north_str}'). {e}")
            validated['rec_thr_point'] = None; current_errors += 1

        # Check if points are valid and not coincident
        pt1 = validated.get('thr_point')
        pt2 = validated.get('rec_thr_point')
        if pt1 and pt2 and pt1.distance(pt2) < 1e-6:
             errors.append(f"Rwy {index}: Threshold coordinates are identical.")
             current_errors += 1

        # Elevations (Optional)
        try: # Primary Elevation
            elev1_str = inputs.get('thr_elev_1', '').strip()
            validated['thr_elev_1'] = float(elev1_str) if elev1_str else None
        except ValueError: errors.append(f"Rwy {index}: Invalid primary elevation '{inputs.get('thr_elev_1', '')}'."); current_errors += 1; validated['thr_elev_1'] = None
        try: # Reciprocal Elevation
            elev2_str = inputs.get('thr_elev_2', '').strip()
            validated['thr_elev_2'] = float(elev2_str) if elev2_str else None
        except ValueError: errors.append(f"Rwy {index}: Invalid reciprocal elevation '{inputs.get('thr_elev_2', '')}'."); current_errors += 1; validated['thr_elev_2'] = None

        # Displaced Thresholds (Optional, non-negative)
        try: # Primary Displaced
            disp1_str = inputs.get('thr_displaced_1', '').strip()
            if disp1_str:
                disp1_val = float(disp1_str)
                if disp1_val < 0: raise ValueError("Cannot be negative")
                validated['thr_displaced_1'] = disp1_val
            else: validated['thr_displaced_1'] = None
        except ValueError: errors.append(f"Rwy {index}: Invalid primary displaced threshold '{inputs.get('thr_displaced_1', '')}'. Must be non-negative."); current_errors += 1; validated['thr_displaced_1'] = None
        try: # Reciprocal Displaced
            disp2_str = inputs.get('thr_displaced_2', '').strip()
            if disp2_str:
                disp2_val = float(disp2_str)
                if disp2_val < 0: raise ValueError("Cannot be negative")
                validated['thr_displaced_2'] = disp2_val
            else: validated['thr_displaced_2'] = None
        except ValueError: errors.append(f"Rwy {index}: Invalid reciprocal displaced threshold '{inputs.get('thr_displaced_2', '')}'. Must be non-negative."); current_errors += 1; validated['thr_displaced_2'] = None

        # <<< NEW VALIDATION >>> Pre-threshold Area (Optional, non-negative)
        try: # Primary Pre-threshold Area
            pre_area1_str = inputs.get('thr_pre_area_1', '').strip()
            if pre_area1_str:
                pre_area1_val = float(pre_area1_str)
                if pre_area1_val < 0: raise ValueError("Cannot be negative")
                validated['thr_pre_area_1'] = pre_area1_val
            else:
                validated['thr_pre_area_1'] = None # Explicitly None if empty
        except ValueError:
            errors.append(f"Rwy {index}: Invalid primary pre-threshold area '{inputs.get('thr_pre_area_1', '')}'. Must be non-negative.")
            current_errors += 1
            validated['thr_pre_area_1'] = None

        try: # Reciprocal Pre-threshold Area
            pre_area2_str = inputs.get('thr_pre_area_2', '').strip()
            if pre_area2_str:
                pre_area2_val = float(pre_area2_str)
                if pre_area2_val < 0: raise ValueError("Cannot be negative")
                validated['thr_pre_area_2'] = pre_area2_val
            else:
                validated['thr_pre_area_2'] = None
        except ValueError:
            errors.append(f"Rwy {index}: Invalid reciprocal pre-threshold area '{inputs.get('thr_pre_area_2', '')}'. Must be non-negative.")
            current_errors += 1
            validated['thr_pre_area_2'] = None

        # Width (Mandatory positive)
        try:
            width_val = float(inputs.get('width', ''))
            if width_val <= 0: raise ValueError("Width must be positive")
            validated['width'] = width_val
        except (ValueError, TypeError): errors.append(f"Rwy {index}: Invalid runway width '{inputs.get('width', '')}'. Must be a positive number."); current_errors += 1; validated['width'] = None

        # Shoulder (Optional, non-negative)
        try:
            shoulder_str = inputs.get('shoulder', '').strip()
            if shoulder_str:
                shoulder_val = float(shoulder_str)
                if shoulder_val < 0: raise ValueError("Shoulder cannot be negative")
                validated['shoulder'] = shoulder_val
            else: validated['shoulder'] = None
        except ValueError: errors.append(f"Rwy {index}: Invalid shoulder width '{inputs.get('shoulder', '')}'. Must be non-negative."); current_errors += 1; validated['shoulder'] = None

        # Optional fields (just copy text)
        validated['arc_num'] = inputs.get('arc_num')
        validated['arc_let'] = inputs.get('arc_let')
        validated['type1'] = inputs.get('type1')
        validated['type2'] = inputs.get('type2')

        return validated if current_errors == 0 else None

    # --- Global/CNS Input Getters (no changes needed) ---
    def _get_global_inputs(self) -> Tuple[Optional[str], Optional[QgsPointXY], Optional[float], Optional[float], Optional[float], Optional[QgsPointXY]]:
        """Retrieves and validates ICAO, ARP coords, and MET coords."""
        icao_code: Optional[str] = None
        arp_point: Optional[QgsPointXY] = None
        arp_east: Optional[float] = None
        arp_north: Optional[float] = None
        arp_elev: Optional[float] = None
        met_point_proj_crs: Optional[QgsPointXY] = None

        try:
            icao_lineEdit = getattr(self, 'lineEdit_airport_name', self.findChild(QtWidgets.QLineEdit, "lineEdit_airport_name"))
            arp_east_lineEdit = getattr(self, 'lineEdit_arp_easting', self.findChild(QtWidgets.QLineEdit, "lineEdit_arp_easting"))
            arp_north_lineEdit = getattr(self, 'lineEdit_arp_northing', self.findChild(QtWidgets.QLineEdit, "lineEdit_arp_northing"))
            arp_elev_lineEdit = getattr(self, 'lineEdit_arp_elevation', self.findChild(QtWidgets.QLineEdit, "lineEdit_arp_elevation"))
            met_east_lineEdit = getattr(self, 'lineEdit_met_easting', self.findChild(QtWidgets.QLineEdit, "lineEdit_met_easting"))
            met_north_lineEdit = getattr(self, 'lineEdit_met_northing', self.findChild(QtWidgets.QLineEdit, "lineEdit_met_northing"))

            if not icao_lineEdit: raise RuntimeError("UI Error: Cannot find 'lineEdit_airport_name'.")
            icao_code_str = icao_lineEdit.text().strip().upper()
            if not icao_code_str:
                QMessageBox.critical(self, self.tr("Input Error"), self.tr("Airport ICAO Code is required."))
                return None, None, None, None, None, None
            icao_code = icao_code_str

            # ARP (Optional Coords, Optional Elev)
            arp_point, arp_east, arp_north, arp_elev = None, None, None, None # Initialize
            if arp_east_lineEdit and arp_north_lineEdit:
                arp_east_str = arp_east_lineEdit.text().strip()
                arp_north_str = arp_north_lineEdit.text().strip()
                if arp_east_str and arp_north_str:
                    try:
                        arp_east_val = float(arp_east_str); arp_north_val = float(arp_north_str)
                        arp_point = QgsPointXY(arp_east_val, arp_north_val)
                        arp_east, arp_north = arp_east_val, arp_north_val
                    except ValueError:
                        QMessageBox.warning(self, self.tr("Input Warning"), self.tr("Invalid ARP coordinate format. ARP coordinates ignored."))
                        arp_point, arp_east, arp_north = None, None, None
                elif arp_east_str or arp_north_str: # Only one entered
                     QMessageBox.warning(self, self.tr("Input Warning"), self.tr("Both ARP Easting and Northing must be provided if entering coordinates. ARP coordinates ignored."))
                     arp_point, arp_east, arp_north = None, None, None

            # Check ARP Elevation (Optional, but must be valid if entered)
            if arp_elev_lineEdit:
                arp_elev_str = arp_elev_lineEdit.text().strip()
                if arp_elev_str:
                    try:
                        arp_elev = float(arp_elev_str)
                    except ValueError:
                        QMessageBox.critical(self, self.tr("Input Error"), self.tr("Invalid ARP Elevation format. Must be a number."))
                        return None, None, None, None, None, None # Abort data gathering

            # MET Station (Optional)
            met_point_proj_crs = None # Initialize
            if met_east_lineEdit and met_north_lineEdit:
                met_east_str = met_east_lineEdit.text().strip()
                met_north_str = met_north_lineEdit.text().strip()
                if met_east_str and met_north_str:
                    try:
                        met_east_val = float(met_east_str); met_north_val = float(met_north_str)
                        met_point_proj_crs = QgsPointXY(met_east_val, met_north_val)
                    except ValueError:
                        QMessageBox.warning(self, self.tr("Input Warning"), self.tr("Invalid MET station coordinate format. MET station ignored."))
                        met_point_proj_crs = None
                elif met_east_str or met_north_str: # Only one entered
                     QMessageBox.warning(self, self.tr("Input Warning"), self.tr("Both MET Easting and Northing must be provided if entering coordinates. MET station ignored."))
                     met_point_proj_crs = None

        except (AttributeError, RuntimeError, Exception) as e:
            QgsMessageLog.logMessage(f"Error getting global inputs: {e}", DIALOG_LOG_TAG, level=Qgis.Critical)
            QMessageBox.critical(self, self.tr("Internal Error"), self.tr("Error retrieving global inputs. See QGIS log."))
            return None, None, None, None, None, None

        return icao_code, arp_point, arp_east, arp_north, arp_elev, met_point_proj_crs

    def _get_cns_manual_data(self) -> Optional[List[Dict[str, Any]]]:
        """Reads and validates CNS facility data from the manual entry table."""
        cns_facilities_data = []
        cns_table = getattr(self, 'table_cns_facility', self.findChild(QtWidgets.QTableWidget, 'table_cns_facility'))
        if not cns_table:
             QgsMessageLog.logMessage("CNS Validation Error: Table widget not found.", DIALOG_LOG_TAG, level=Qgis.Critical)
             QMessageBox.critical(self, "UI Error", "Cannot find CNS table.")
             return None

        project_crs = QgsProject.instance().crs()
        if not project_crs or not project_crs.isValid():
             QgsMessageLog.logMessage("CNS Validation Error: Invalid Project CRS.", DIALOG_LOG_TAG, level=Qgis.Critical)
             QMessageBox.critical(self, "CRS Error", "Project CRS is invalid. Cannot process CNS coordinates.")
             return None

        skipped_rows, rows_with_errors, total_rows = 0, 0, cns_table.rowCount()
        for row in range(total_rows):
            facility_type = ""; facility_elevation: Optional[float] = None
            point_geom_project_crs: Optional[QgsGeometry] = None
            valid_row = True; error_in_row = False
            try:
                combo_box = cns_table.cellWidget(row, 0)
                if isinstance(combo_box, QComboBox) and combo_box.currentIndex() > 0 and combo_box.currentText(): facility_type = combo_box.currentText()
                else: valid_row = False

                if valid_row:
                    x_item, y_item = cns_table.item(row, 1), cns_table.item(row, 2)
                    x_str, y_str = (x_item.text().strip() if x_item else ""), (y_item.text().strip() if y_item else "")
                    if not x_str or not y_str: valid_row = False
                    else:
                        try:
                            point_xy = QgsPointXY(float(x_str), float(y_str)); point_geom_project_crs = QgsGeometry.fromPointXY(point_xy)
                            if point_geom_project_crs.isNull(): valid_row = False; error_in_row = True; QgsMessageLog.logMessage(f"CNS Row {row+1}: Null geom.", DIALOG_LOG_TAG, level=Qgis.Warning)
                        except ValueError: valid_row = False; error_in_row = True; QgsMessageLog.logMessage(f"CNS Row {row+1}: Invalid coords.", DIALOG_LOG_TAG, level=Qgis.Warning)

                if valid_row:
                    elev_item = cns_table.item(row, 3); elev_str = elev_item.text().strip() if elev_item else ""
                    if elev_str:
                        try: facility_elevation = float(elev_str)
                        except ValueError: facility_elevation = None; error_in_row = True; QgsMessageLog.logMessage(f"CNS Row {row+1}: Invalid elev, ignoring.", DIALOG_LOG_TAG, level=Qgis.Warning)
            except Exception as e: valid_row = False; error_in_row = True; QgsMessageLog.logMessage(f"CNS Row {row+1} Error: {e}", DIALOG_LOG_TAG, level=Qgis.Critical)

            if valid_row and point_geom_project_crs:
                facility_id = f'Manual_{row+1}_{facility_type.replace(" ", "_").replace("-","").replace("(","").replace(")","")}'[:50]
                cns_facilities_data.append({'id': facility_id, 'type': facility_type, 'geom': point_geom_project_crs, 'elevation': facility_elevation, 'params': {} })
            elif error_in_row: rows_with_errors += 1; skipped_rows += 1
            elif not valid_row: skipped_rows += 1

        if rows_with_errors > 0: QMessageBox.warning(self, "CNS Data Warning", f"{rows_with_errors} CNS row(s) had errors/invalid data and were skipped or data ignored.\n({skipped_rows} total skipped/incomplete). Check Log.")
        elif skipped_rows > 0 and skipped_rows == total_rows and total_rows > 0: QMessageBox.information(self, "CNS Data Info", "All CNS rows skipped (missing required data).")
        elif skipped_rows > 0: QMessageBox.information(self, "CNS Data Info", f"{skipped_rows} CNS rows skipped (missing required data).")

        return cns_facilities_data

    # --- Action Button Handlers ---
    # <<< UPDATED load_input_data for compatibility >>>
    # clear_all_inputs and save_input_data need no changes here

    def clear_all_inputs(self, confirm: bool = True) -> None:
        """Clears all inputs, removes all runways, adds one back, clears CNS."""
        if confirm:
            reply = QMessageBox.question(self, self.tr('Confirm Clear'), self.tr("Clear all inputs and runway definitions?"),
                                         QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No,
                                         QtWidgets.QMessageBox.StandardButton.No)
            if reply == QtWidgets.QMessageBox.StandardButton.No: return

        cns_table = getattr(self, 'table_cns_facility', self.findChild(QtWidgets.QTableWidget, 'table_cns_facility'))
        if cns_table: cns_table.setRowCount(0)

        for name in ["lineEdit_airport_name", "lineEdit_arp_easting", "lineEdit_arp_northing", "lineEdit_arp_elevation", "lineEdit_met_easting", "lineEdit_met_northing"]:
             widget = getattr(self, name, self.findChild(QtWidgets.QLineEdit, name))
             if widget: widget.clear()

        indices_to_remove = list(self._runway_groups.keys())
        for index in indices_to_remove:
            self._remove_runway_group_internal(index)

        self._runway_groups.clear(); self._runway_id_counter = 0

        if self.scroll_area_layout: self.add_runway_group()
        else: QgsMessageLog.logMessage("Warn (Clear): Layout missing, couldn't add runway back.", DIALOG_LOG_TAG, level=Qgis.Warning)

        self._update_dialog_height()

    def save_input_data(self):
        """Gathers current inputs and saves them to a JSON file."""
        icao_le = getattr(self, 'lineEdit_airport_name', self.findChild(QtWidgets.QLineEdit, "lineEdit_airport_name"))
        icao_code = icao_le.text().strip().upper() if icao_le else ""
        suggested_filename = f"{icao_code}_safeguarding_inputs.json" if icao_code else "safeguarding_inputs.json"
        file_path, _ = QFileDialog.getSaveFileName(self, self.tr("Save Inputs"), suggested_filename, self.tr("JSON Files (*.json)"))
        if not file_path: return
        if not file_path.lower().endswith(".json"): file_path += ".json"

        data_to_save = {}
        arp_east_le = getattr(self, 'lineEdit_arp_easting', self.findChild(QtWidgets.QLineEdit, "lineEdit_arp_easting"))
        arp_north_le = getattr(self, 'lineEdit_arp_northing', self.findChild(QtWidgets.QLineEdit, "lineEdit_arp_northing"))
        arp_elev_le = getattr(self, 'lineEdit_arp_elevation', self.findChild(QtWidgets.QLineEdit, "lineEdit_arp_elevation"))
        met_east_le = getattr(self, 'lineEdit_met_easting', self.findChild(QtWidgets.QLineEdit, "lineEdit_met_easting"))
        met_north_le = getattr(self, 'lineEdit_met_northing', self.findChild(QtWidgets.QLineEdit, "lineEdit_met_northing"))
        data_to_save["icao_code"] = icao_code
        data_to_save["arp_easting"] = arp_east_le.text() if arp_east_le else ""
        data_to_save["arp_northing"] = arp_north_le.text() if arp_north_le else ""
        data_to_save["arp_elevation"] = arp_elev_le.text() if arp_elev_le else ""
        data_to_save["met_easting"] = met_east_le.text() if met_east_le else ""
        data_to_save["met_northing"] = met_north_le.text() if met_north_le else ""

        # Uses the updated get_input_data which includes pre_area fields
        data_to_save["runways"] = [self._runway_groups[idx].get_input_data() for idx in sorted(self._runway_groups.keys())]

        cns_list = []
        cns_table = getattr(self, 'table_cns_facility', self.findChild(QtWidgets.QTableWidget, 'table_cns_facility'))
        if cns_table:
            for row in range(cns_table.rowCount()):
                try:
                    combo = cns_table.cellWidget(row, 0)
                    type_txt = combo.currentText() if isinstance(combo, QComboBox) else ""
                    x_item, y_item, elev_item = cns_table.item(row, 1), cns_table.item(row, 2), cns_table.item(row, 3)
                    x_txt, y_txt, elev_txt = (x_item.text() if x_item else ""), (y_item.text() if y_item else ""), (elev_item.text() if elev_item else "")
                    cns_list.append({"type": type_txt, "easting_x": x_txt, "northing_y": y_txt, "elevation": elev_txt})
                except Exception as e: QgsMessageLog.logMessage(f"Save CNS row {row+1} error: {e}", DIALOG_LOG_TAG, level=Qgis.Warning)
        data_to_save["cns_facilities"] = cns_list

        try:
            with open(file_path, 'w', encoding='utf-8') as f: json.dump(data_to_save, f, indent=4, ensure_ascii=False)
            QMessageBox.information(self, self.tr("Save Successful"), self.tr("Input data saved to:\n{path}").format(path=file_path))
        except Exception as e:
             error_msg = self.tr("Error saving data:") + f"\n{type(e).__name__}: {e}"; QgsMessageLog.logMessage(f"Save error {file_path}: {e}", DIALOG_LOG_TAG, level=Qgis.Critical); QMessageBox.critical(self, self.tr("Save Error"), error_msg)

    def load_input_data(self):
        """Loads safeguarding inputs from a JSON file."""
        has_data = False
        global_widgets = [getattr(self, name, self.findChild(QtWidgets.QLineEdit, name)) for name in ["lineEdit_airport_name", "lineEdit_arp_easting", "lineEdit_arp_elevation", "lineEdit_met_easting"]]
        if any(w and w.text() for w in global_widgets if w): has_data = True
        if not has_data and self._runway_groups: has_data = True
        cns_table = getattr(self, 'table_cns_facility', self.findChild(QtWidgets.QTableWidget, 'table_cns_facility'))
        if not has_data and cns_table and cns_table.rowCount() > 0: has_data = True
        # if has_data:
        #     reply = QtWidgets.QMessageBox.question(self, self.tr('Confirm Load'), self.tr("This will clear current inputs and load data from the selected file. Continue?"), QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No, QtWidgets.QMessageBox.StandardButton.No)
        #     if reply == QtWidgets.QMessageBox.StandardButton.No: return

        file_path, _ = QFileDialog.getOpenFileName(self, self.tr("Load Inputs"), "", self.tr("JSON Files (*.json)"))
        if not file_path: return

        loaded_data = None
        try:
            with open(file_path, 'r', encoding='utf-8') as f: loaded_data = json.load(f)
            if not isinstance(loaded_data, dict): raise ValueError("Invalid format: Top level is not a dictionary.")
            required = ["icao_code", "runways"]; missing = [k for k in required if k not in loaded_data]
            if missing: raise ValueError(f"Missing required keys: {', '.join(missing)}")
            if not isinstance(loaded_data.get("runways"), list): raise ValueError("Invalid format: 'runways' key is not a list.")
            if "cns_facilities" in loaded_data and not isinstance(loaded_data.get("cns_facilities"), list): raise ValueError("Invalid format: 'cns_facilities' key exists but is not a list.")

            self.clear_all_inputs(confirm=False) # Adds one empty group back

            icao_le = getattr(self, 'lineEdit_airport_name', self.findChild(QtWidgets.QLineEdit, "lineEdit_airport_name"))
            arp_east_le = getattr(self, 'lineEdit_arp_easting', self.findChild(QtWidgets.QLineEdit, "lineEdit_arp_easting"))
            arp_north_le = getattr(self, 'lineEdit_arp_northing', self.findChild(QtWidgets.QLineEdit, "lineEdit_arp_northing"))
            arp_elev_le = getattr(self, 'lineEdit_arp_elevation', self.findChild(QtWidgets.QLineEdit, "lineEdit_arp_elevation"))
            met_east_le = getattr(self, 'lineEdit_met_easting', self.findChild(QtWidgets.QLineEdit, "lineEdit_met_easting"))
            met_north_le = getattr(self, 'lineEdit_met_northing', self.findChild(QtWidgets.QLineEdit, "lineEdit_met_northing"))
            if icao_le: icao_le.setText(loaded_data.get("icao_code", ""))
            if arp_east_le: arp_east_le.setText(loaded_data.get("arp_easting", ""))
            if arp_north_le: arp_north_le.setText(loaded_data.get("arp_northing", ""))
            if arp_elev_le: arp_elev_le.setText(loaded_data.get("arp_elevation", ""))
            if met_east_le: met_east_le.setText(loaded_data.get("met_easting", ""))
            if met_north_le: met_north_le.setText(loaded_data.get("met_northing", ""))

            loaded_runways_list = loaded_data.get("runways", [])
            if loaded_runways_list:
                first_runway_index = min(self._runway_groups.keys()) if self._runway_groups else None
                first_group = self._runway_groups.get(first_runway_index) if first_runway_index is not None else None
                if first_group:
                    first_runway_data = loaded_runways_list[0]
                    # <<< NEW COMPATIBILITY >>> Ensure new keys exist with default ""
                    first_runway_data.setdefault("thr_pre_area_1", "")
                    first_runway_data.setdefault("thr_pre_area_2", "")
                    first_runway_data.setdefault("thr_displaced_1", "") # Also ensure displaced keys
                    first_runway_data.setdefault("thr_displaced_2", "")
                    first_group.set_input_data(first_runway_data)
                else: QgsMessageLog.logMessage("Load Error: First runway group missing after clear.", DIALOG_LOG_TAG, level=Qgis.Warning)

                for runway_data_item in loaded_runways_list[1:]:
                    try:
                        self.add_runway_group()
                        new_index = self._runway_id_counter
                        new_group = self._runway_groups.get(new_index)
                        if new_group:
                            # <<< NEW COMPATIBILITY >>> Ensure new keys exist with default ""
                            runway_data_item.setdefault("thr_pre_area_1", "")
                            runway_data_item.setdefault("thr_pre_area_2", "")
                            runway_data_item.setdefault("thr_displaced_1", "") # Also ensure displaced keys
                            runway_data_item.setdefault("thr_displaced_2", "")
                            new_group.set_input_data(runway_data_item)
                        else: QgsMessageLog.logMessage(f"Load Error: Group {new_index} missing after add.", DIALOG_LOG_TAG, level=Qgis.Warning)
                    except Exception as e_loop: QgsMessageLog.logMessage(f"Load Error processing runway item: {e_loop}", DIALOG_LOG_TAG, level=Qgis.Warning)
            elif self._runway_groups: # File has no runways, update the one empty group
                 first_runway_index = min(self._runway_groups.keys())
                 self.update_runway_calculations(first_runway_index)

            cns_table = getattr(self, 'table_cns_facility', self.findChild(QtWidgets.QTableWidget, 'table_cns_facility'))
            loaded_cns_list = loaded_data.get("cns_facilities", [])
            if cns_table and loaded_cns_list:
                cns_table.setRowCount(0)
                for item_data in loaded_cns_list:
                   if not isinstance(item_data, dict): QgsMessageLog.logMessage(f"Load CNS Warn: Skipping non-dict: {item_data}", DIALOG_LOG_TAG, level=Qgis.Warning); continue
                   try:
                       row = cns_table.rowCount(); cns_table.insertRow(row)
                       combo = QComboBox(); combo.addItems([""] + self.CNS_FACILITY_TYPES)
                       idx = combo.findText(item_data.get("type", ""), QtCore.Qt.MatchFlag.MatchFixedString)
                       combo.setCurrentIndex(idx if idx >= 0 else 0)
                       cns_table.setCellWidget(row, 0, combo)
                       cns_table.setItem(row, 1, QTableWidgetItem(item_data.get("easting_x", "")))
                       cns_table.setItem(row, 2, QTableWidgetItem(item_data.get("northing_y", "")))
                       cns_table.setItem(row, 3, QTableWidgetItem(item_data.get("elevation", "")))
                   except Exception as e: QgsMessageLog.logMessage(f"Load CNS error item {item_data}: {e}", DIALOG_LOG_TAG, level=Qgis.Warning)

            self._update_dialog_height()
            # QMessageBox.information(self, self.tr("Load Successful"), self.tr("Input data loaded from:\n{path}").format(path=file_path))

        except (IOError, json.JSONDecodeError, ValueError) as e:
            error_details = f"{type(e).__name__}: {e}"; log_msg = f"Load Error ({file_path}): {error_details}"; user_msg = self.tr("Error loading data from file:") + f"\n{file_path}\n\n{self.tr('Error')}: {error_details}"
            QgsMessageLog.logMessage(log_msg, DIALOG_LOG_TAG, level=Qgis.Critical); QMessageBox.critical(self, self.tr("Load Error"), user_msg)
            try: self.clear_all_inputs(confirm=False)
            except Exception as clear_err: QgsMessageLog.logMessage(f"Error during post-load-error cleanup: {clear_err}", DIALOG_LOG_TAG, level=Qgis.Critical)
        except Exception as e:
            error_details = f"{type(e).__name__}: {e}"; log_msg = f"Unexpected load error ({file_path}): {error_details}"; user_msg = self.tr("An unexpected error occurred during loading:") + f"\n\n{self.tr('Error')}: {error_details}"
            QgsMessageLog.logMessage(log_msg, DIALOG_LOG_TAG, level=Qgis.Critical); QMessageBox.critical(self, self.tr("Load Error"), user_msg)
            try: self.clear_all_inputs(confirm=False)
            except Exception as clear_err: QgsMessageLog.logMessage(f"Error during post-load-error cleanup: {clear_err}", DIALOG_LOG_TAG, level=Qgis.Critical)


# ========================= End of Class Definition =========================

if __name__ == '__main__':
    import sys
    from qgis.PyQt.QtWidgets import QApplication # type: ignore
    # --- Mock QGIS environment if running standalone ---
    class MockQgisInterface: pass
    class MockQgsProject:
        def __init__(self): self._crs = QgsCoordinateReferenceSystem("EPSG:4326")
        def instance(self): return self
        def crs(self): return self._crs
    if not QgsProject.instance(): QgsProject.setInstance(MockQgsProject())
    # --- End Mock ---

    app = QApplication(sys.argv)
    dialog = SafeguardingBuilderDialog()
    dialog.show()
    sys.exit(app.exec())