# -*- coding: utf-8 -*-
# safeguarding_builder_dialog.py
"""
Dialog class for the Safeguarding Builder QGIS plugin.
Handles user input for airport, ARP, runway, and CNS data.
Dynamically adds/removes runway groups using a helper class
and performs real-time calculations for display.
CNS coordinates are assumed to be in the current Project CRS.
"""

import functools
import math
import os
import json
from typing import List, Optional, Dict, Any

# --- QGIS Imports ---
from qgis.core import (
    QgsMessageLog, Qgis, QgsPointXY, QgsProject, QgsCoordinateReferenceSystem,
    QgsCoordinateTransform, QgsGeometry
)
from qgis.PyQt import uic, QtWidgets, QtGui, QtCore
from qgis.PyQt.QtWidgets import (
    QFileDialog, QMessageBox, QTableWidget, QTableWidgetItem, QComboBox,
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
        super().__init__(f"Runway {index}", parent)
        self.index = index
        self.numeric_validator = QtGui.QDoubleValidator()
        self.numeric_validator.setNotation(QtGui.QDoubleValidator.Notation.StandardNotation)
        self.coord_validator = coord_validator
        
        self.setObjectName(f"groupBox_runway_{self.index}")
        self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Preferred, QtWidgets.QSizePolicy.Policy.MinimumExpanding)
        
        self._setup_ui() # Call the updated setup method
        self._connect_signals()
        
    def _setup_ui(self):
        """Creates and arranges all widgets within this group box."""
        # Use a smaller margin/spacing for the main group layout if needed
        groupBox_layout = QtWidgets.QVBoxLayout(self)
        # groupBox_layout.setContentsMargins(5, 5, 5, 5) # Optional: Adjust margins
        # groupBox_layout.setSpacing(5) # Optional: Adjust spacing between elements
        
        # --- Coordinate Grid Layout ---
        gridLayout_Coords = QtWidgets.QGridLayout()
        gridLayout_Coords.setObjectName(f"gridLayout_Coords_{self.index}")
        gridLayout_Coords.setColumnStretch(0, 2) # Label column 50%
        gridLayout_Coords.setColumnStretch(1, 1) # Input column 1 25%
        gridLayout_Coords.setColumnStretch(2, 1) # Input column 2 25%
        # gridLayout_Coords.setHorizontalSpacing(10) # Optional: Adjust horizontal space
        
        # Labels (Left-Justified)
        label_designation_row = QtWidgets.QLabel("Designation:")
        label_designation_row.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter)
        label_easting_row = QtWidgets.QLabel("Easting:")
        label_easting_row.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter)
        label_northing_row = QtWidgets.QLabel("Northing:")
        label_northing_row.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter)
        label_elevation_row = QtWidgets.QLabel("Elevation (m):")
        label_elevation_row.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter)
        
        # Input Widgets (Setup as before)
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
        
        # Add Widgets to Coordinate Grid
        gridLayout_Coords.addWidget(label_designation_row, 0, 0); gridLayout_Coords.addLayout(h_layout_desig_inputs, 0, 1); gridLayout_Coords.addWidget(self.rec_desig_hdr_lbl, 0, 2)
        gridLayout_Coords.addWidget(label_easting_row, 1, 0); gridLayout_Coords.addWidget(self.thr_east_le, 1, 1); gridLayout_Coords.addWidget(self.rec_east_le, 1, 2)
        gridLayout_Coords.addWidget(label_northing_row, 2, 0); gridLayout_Coords.addWidget(self.thr_north_le, 2, 1); gridLayout_Coords.addWidget(self.rec_north_le, 2, 2)
        gridLayout_Coords.addWidget(label_elevation_row, 3, 0); gridLayout_Coords.addWidget(self.thr_elev_1_le, 3, 1); gridLayout_Coords.addWidget(self.thr_elev_2_le, 3, 2)
        
        groupBox_layout.addLayout(gridLayout_Coords) # Add grid first
        
        # --- Runway Name Label (Styled) ---
        self.rwy_name_lbl = QtWidgets.QLabel(CALC_PLACEHOLDER)
        self.rwy_name_lbl.setObjectName(f"label_rwy_name_{self.index}")
        # <<< STYLE CHANGE: Set Alignment Left and Bold Font >>>
        self.rwy_name_lbl.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter)
        font = self.rwy_name_lbl.font()
        font.setBold(True)
        self.rwy_name_lbl.setFont(font)
        # <<< END STYLE CHANGE >>>
        # Add with small top/bottom margins to create some visual separation
        self.rwy_name_lbl.setContentsMargins(0, 5, 0, 5) # Left, Top, Right, Bottom
        groupBox_layout.addWidget(self.rwy_name_lbl) # Add runway name label
        
        # --- Details Grid Layout ---
        detailsLayout = QtWidgets.QGridLayout()
        detailsLayout.setObjectName(f"detailsLayout_{self.index}"); detailsLayout.setColumnStretch(0, 1); detailsLayout.setColumnStretch(1, 1)
        current_row = 0
        
        # Detail Labels (Left-Justified)
        label_rwy_dist_text = QtWidgets.QLabel("Length (m):"); label_rwy_dist_text.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter)
        self.dist_lbl = QtWidgets.QLabel(CALC_PLACEHOLDER); self.dist_lbl.setObjectName(f"label_rwy_distance_{self.index}")
        detailsLayout.addWidget(label_rwy_dist_text, current_row, 0); detailsLayout.addWidget(self.dist_lbl, current_row, 1); current_row += 1
        label_rwy_azim_text = QtWidgets.QLabel("Azimuth (°):"); label_rwy_azim_text.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter)
        self.azim_lbl = QtWidgets.QLabel(CALC_PLACEHOLDER); self.azim_lbl.setObjectName(f"label_rwy_azimuth_{self.index}")
        detailsLayout.addWidget(label_rwy_azim_text, current_row, 0); detailsLayout.addWidget(self.azim_lbl, current_row, 1); current_row += 1
        label_runway_width = QtWidgets.QLabel("Runway Width (m):"); label_runway_width.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter)
        self.width_le = QtWidgets.QLineEdit(); self.width_le.setObjectName(f"lineEdit_runway_width_{self.index}"); self.width_le.setToolTip("Enter actual runway width (meters).")
        width_validator = QtGui.QDoubleValidator(0.01, 9999.99, 2, self); width_validator.setNotation(QtGui.QDoubleValidator.Notation.StandardNotation); self.width_le.setValidator(width_validator)
        detailsLayout.addWidget(label_runway_width, current_row, 0); detailsLayout.addWidget(self.width_le, current_row, 1); current_row += 1
        label_runway_shoulder = QtWidgets.QLabel("Runway Shoulder (m):"); label_runway_shoulder.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter)
        self.shoulder_le = QtWidgets.QLineEdit(); self.shoulder_le.setObjectName(f"lineEdit_rwy_shoulder_{self.index}"); self.shoulder_le.setToolTip("Enter width of runway shoulder (each side, if applicable).")
        shoulder_validator = QtGui.QDoubleValidator(0.0, 999.9, 1, self); shoulder_validator.setNotation(QtGui.QDoubleValidator.Notation.StandardNotation); self.shoulder_le.setValidator(shoulder_validator)
        detailsLayout.addWidget(label_runway_shoulder, current_row, 0); detailsLayout.addWidget(self.shoulder_le, current_row, 1); current_row += 1
        label_arc_num = QtWidgets.QLabel("ARC Number:"); label_arc_num.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter)
        self.arc_num_combo = QtWidgets.QComboBox(); self.arc_num_combo.setObjectName(f"comboBox_arc_num_{self.index}"); self.arc_num_combo.addItems(["", "1", "2", "3", "4"]); self.arc_num_combo.setToolTip("Select Aerodrome Reference Code Number"); self.arc_num_combo.setFocusPolicy(QtCore.Qt.FocusPolicy.StrongFocus)
        detailsLayout.addWidget(label_arc_num, current_row, 0); detailsLayout.addWidget(self.arc_num_combo, current_row, 1); current_row += 1
        label_arc_let = QtWidgets.QLabel("ARC Letter:"); label_arc_let.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter)
        self.arc_let_combo = QtWidgets.QComboBox(); self.arc_let_combo.setObjectName(f"comboBox_arc_let_{self.index}"); self.arc_let_combo.addItems(["", "A", "B", "C", "D", "E", "F"]); self.arc_let_combo.setToolTip("Select Aerodrome Reference Code Letter"); self.arc_let_combo.setFocusPolicy(QtCore.Qt.FocusPolicy.StrongFocus)
        detailsLayout.addWidget(label_arc_let, current_row, 0); detailsLayout.addWidget(self.arc_let_combo, current_row, 1); current_row += 1
        runway_types = ["", "Non-Instrument (NI)", "Non-Precision Approach (NPA)", "Precision Approach CAT I", "Precision Approach CAT II/III"]
        self.type1_lbl = QtWidgets.QLabel("(Primary End) Type:"); self.type1_lbl.setObjectName(f"label_type_desig1_{self.index}"); self.type1_lbl.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter)
        self.type1_combo = QtWidgets.QComboBox(); self.type1_combo.setObjectName(f"comboBox_type_desig1_{self.index}"); self.type1_combo.addItems(runway_types); self.type1_combo.setToolTip("Select type for primary end."); self.type1_combo.setFocusPolicy(QtCore.Qt.FocusPolicy.StrongFocus)
        detailsLayout.addWidget(self.type1_lbl, current_row, 0); detailsLayout.addWidget(self.type1_combo, current_row, 1); current_row += 1
        self.type2_lbl = QtWidgets.QLabel("(Reciprocal End) Type:"); self.type2_lbl.setObjectName(f"label_type_desig2_{self.index}"); self.type2_lbl.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter)
        self.type2_combo = QtWidgets.QComboBox(); self.type2_combo.setObjectName(f"comboBox_type_desig2_{self.index}"); self.type2_combo.addItems(runway_types); self.type2_combo.setToolTip("Select type for reciprocal end."); self.type2_combo.setFocusPolicy(QtCore.Qt.FocusPolicy.StrongFocus)
        detailsLayout.addWidget(self.type2_lbl, current_row, 0); detailsLayout.addWidget(self.type2_combo, current_row, 1); current_row += 1
        
        groupBox_layout.addLayout(detailsLayout) # Add details grid
        
        # --- Separator and Remove Button ---
        line_separator = QtWidgets.QFrame(); line_separator.setObjectName(f"line_runway_group_{self.index}"); line_separator.setFrameShape(QtWidgets.QFrame.Shape.HLine); line_separator.setFrameShadow(QtWidgets.QFrame.Shadow.Sunken)
        groupBox_layout.addWidget(line_separator)
        self.remove_button = QtWidgets.QPushButton("Remove This Runway"); self.remove_button.setObjectName(f"pushButton_remove_runway_{self.index}"); self.remove_button.setToolTip(f"Remove this runway")
        groupBox_layout.addWidget(self.remove_button)
        
        
    # --- _connect_signals, get_input_data, set_input_data, update_display_labels, clear_inputs ---
    # --- remain IDENTICAL to the previous version ---
    # ... (Paste the existing methods here without modification) ...
    def _connect_signals(self):
        """Connect internal widget signals."""
        self.desig_le.textChanged.connect(self.inputChanged.emit)
        self.suffix_combo.currentIndexChanged.connect(self.inputChanged.emit)
        self.thr_east_le.textChanged.connect(self.inputChanged.emit)
        self.thr_north_le.textChanged.connect(self.inputChanged.emit)
        self.rec_east_le.textChanged.connect(self.inputChanged.emit)
        self.rec_north_le.textChanged.connect(self.inputChanged.emit)
        self.thr_elev_1_le.textChanged.connect(self.inputChanged.emit) # <<< NEW FIELD >>>
        self.thr_elev_2_le.textChanged.connect(self.inputChanged.emit) # <<< NEW FIELD >>>
        self.width_le.textChanged.connect(self.inputChanged.emit)
        self.shoulder_le.textChanged.connect(self.inputChanged.emit) # <<< NEW FIELD >>>
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
            # Create the dictionary more clearly
            data = {
                    "designator_str": self.desig_le.text(),
                    "suffix": self.suffix_combo.currentText(),
                    "thr_easting": self.thr_east_le.text(),
                    "thr_northing": self.thr_north_le.text(),
                    "rec_easting": self.rec_east_le.text(),
                    "rec_northing": self.rec_north_le.text(),
                    "thr_elev_1": self.thr_elev_1_le.text(),
                    "thr_elev_2": self.thr_elev_2_le.text(),
                    "width": self.width_le.text(),
                    "shoulder": self.shoulder_le.text(),
                    "arc_num": self.arc_num_combo.currentText(),
                    "arc_let": self.arc_let_combo.currentText(),
                    "type1": self.type1_combo.currentText(),
                    "type2": self.type2_combo.currentText(),
            } # Closing brace now on the same logical level as opening
        
            # --- Add this Debug Print ---
            # Use repr() to clearly see if strings are empty or have hidden whitespace
            print(f"DEBUG get_input_data Index {self.index}: "
                        f"Thr E={repr(data['thr_easting'])}, Thr N={repr(data['thr_northing'])}, "
                        f"Rec E={repr(data['rec_easting'])}, Rec N={repr(data['rec_northing'])}")
            # --- End Debug Print ---
        
            return data
    def set_input_data(self, data: Dict[str, str]):
        """Populates the input widgets from a dictionary."""
        widgets_to_block = [ self.desig_le, self.suffix_combo, self.thr_east_le, self.thr_north_le, self.rec_east_le, self.rec_north_le, self.thr_elev_1_le, self.thr_elev_2_le, self.width_le, self.shoulder_le, self.arc_num_combo, self.arc_let_combo, self.type1_combo, self.type2_combo ]
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
            if self.width_le: self.width_le.setText(data.get("width", ""))
            if self.shoulder_le: self.shoulder_le.setText(data.get("shoulder", ""))
            if self.arc_num_combo: idx = self.arc_num_combo.findText(data.get("arc_num", ""), QtCore.Qt.MatchFlag.MatchFixedString); self.arc_num_combo.setCurrentIndex(idx if idx >= 0 else 0)
            if self.arc_let_combo: idx = self.arc_let_combo.findText(data.get("arc_let", ""), QtCore.Qt.MatchFlag.MatchFixedString); self.arc_let_combo.setCurrentIndex(idx if idx >= 0 else 0)
            if self.type1_combo: idx = self.type1_combo.findText(data.get("type1", ""), QtCore.Qt.MatchFlag.MatchFixedString); self.type1_combo.setCurrentIndex(idx if idx >= 0 else 0)
            if self.type2_combo: idx = self.type2_combo.findText(data.get("type2", ""), QtCore.Qt.MatchFlag.MatchFixedString); self.type2_combo.setCurrentIndex(idx if idx >= 0 else 0)
        finally:
            for w in widgets_to_block:
                 if w: w.blockSignals(False)
            self.inputChanged.emit()
            
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
        widgets_to_block = [ self.desig_le, self.suffix_combo, self.thr_east_le, self.thr_north_le, self.rec_east_le, self.rec_north_le, self.thr_elev_1_le, self.thr_elev_2_le, self.width_le, self.shoulder_le, self.arc_num_combo, self.arc_let_combo, self.type1_combo, self.type2_combo ]
        for w in widgets_to_block:
            if w: w.blockSignals(True)
        try:
            if self.desig_le: self.desig_le.clear()
            if self.suffix_combo: self.suffix_combo.setCurrentIndex(0)
            if self.thr_east_le: self.thr_east_le.clear();
            if self.thr_north_le: self.thr_north_le.clear()
            if self.rec_east_le: self.rec_east_le.clear();
            if self.rec_north_le: self.rec_north_le.clear()
            if self.thr_elev_1_le: self.thr_elev_1_le.clear();
            if self.thr_elev_2_le: self.thr_elev_2_le.clear()
            if self.width_le: self.width_le.clear();
            if self.shoulder_le: self.shoulder_le.clear()
            if self.arc_num_combo: self.arc_num_combo.setCurrentIndex(0);
            if self.arc_let_combo: self.arc_let_combo.setCurrentIndex(0)
            if self.type1_combo: self.type1_combo.setCurrentIndex(0);
            if self.type2_combo: self.type2_combo.setCurrentIndex(0)
        finally:
            for w in widgets_to_block:
                if w: w.blockSignals(False)
            self.inputChanged.emit()

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
            if not scroll_area.widgetResizable(): scroll_area.setWidgetResizable(True)
            scroll_content_widget = scroll_area.widget()
            if scroll_content_widget:
                layout = scroll_content_widget.layout()
                if not layout:
                    layout = QtWidgets.QVBoxLayout(scroll_content_widget)
                    scroll_content_widget.setLayout(layout)
                # Ensure it's a QVBoxLayout for adding widgets vertically
                if isinstance(layout, QtWidgets.QVBoxLayout):
                    self.scroll_area_layout = layout
                else:
                     QgsMessageLog.logMessage("Critical: Scroll area content widget layout is not QVBoxLayout.",
                                             DIALOG_LOG_TAG, level=Qgis.Critical)
                     # Fallback: create a new VBox layout? Or disable adding?
                     # For now, let's proceed assuming it *should* be QVBoxLayout
                     # If you designed it differently, this needs adjustment.
                     self.scroll_area_layout = layout # Assign anyway, but might cause issues

            else: QgsMessageLog.logMessage("Critical: Scroll area content widget missing.", DIALOG_LOG_TAG, level=Qgis.Critical)
        else: QgsMessageLog.logMessage("Critical: scrollArea_runways not found in UI.", DIALOG_LOG_TAG, level=Qgis.Critical)

        add_runway_button = self.findChild(QtWidgets.QPushButton, 'pushButton_add_runway')
        if not self.scroll_area_layout:
            QgsMessageLog.logMessage("Critical: Scroll area layout unavailable.", DIALOG_LOG_TAG, level=Qgis.Critical)
            if add_runway_button: add_runway_button.setEnabled(False); add_runway_button.setToolTip("Layout missing.")

        # --- Setup Coordinate Validators ---
        self.coord_validator = QtGui.QDoubleValidator()
        self.coord_validator.setNotation(QtGui.QDoubleValidator.Notation.StandardNotation)
        self._setup_arp_validators(self.coord_validator)

        # --- Connect Global Controls ---
        self._connect_global_controls()

        # --- Connect Action Buttons ---
        clear_button = self.findChild(QtWidgets.QPushButton, "pushButton_clear_all")
        save_button = self.findChild(QtWidgets.QPushButton, "pushButton_save_data")
        load_button = self.findChild(QtWidgets.QPushButton, "pushButton_load_data")
        if clear_button: clear_button.clicked.connect(self.clear_all_inputs)
        if save_button: save_button.clicked.connect(self.save_input_data)
        if load_button: load_button.clicked.connect(self.load_input_data)

        # --- Setup CNS Manual Entry Section ---
        self._setup_cns_manual_entry()

        # --- Add the first runway group programmatically ---
        if self.scroll_area_layout: self.add_runway_group()
        else: QgsMessageLog.logMessage("Warning: Could not add initial runway group (layout missing).", DIALOG_LOG_TAG, level=Qgis.Warning)

        # --- Ensure initial size calculation happens ---
        QtCore.QTimer.singleShot(0, self._update_dialog_height)

    # =========================================================================
    # == Initialization Helper Methods (mostly unchanged)
    # =========================================================================
    def _setup_arp_validators(self, validator: QtGui.QDoubleValidator):
        """Finds ARP/MET widgets and applies validators."""
        widgets_to_validate = [
            'lineEdit_arp_easting', 'lineEdit_arp_northing',
            'lineEdit_met_easting', 'lineEdit_met_northing'
        ]
        tooltips = {
            'lineEdit_arp_easting': "Airport Reference Point (ARP) Easting Coordinate",
            'lineEdit_arp_northing': "Airport Reference Point (ARP) Northing Coordinate",
            'lineEdit_met_easting': "MET Station Easting Coordinate (Optional)",
            'lineEdit_met_northing': "MET Station Northing Coordinate (Optional)"
        }
        placeholders = {
             'lineEdit_arp_easting': "e.g., 455000.00",
             'lineEdit_arp_northing': "e.g., 5772000.00",
             'lineEdit_met_easting': "e.g., 455100.00",
             'lineEdit_met_northing': "e.g., 5772100.00"
        }

        for name in widgets_to_validate:
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
            # ... (error logging as before) ...
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

    # =========================================================================
    # == Runway Group Management (Main logic unchanged, relies on helper class)
    # =========================================================================
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
            QgsMessageLog.logMessage(f"Skipping calc update for index {runway_index}: Group not found.", DIALOG_LOG_TAG, level=Qgis.Debug)
            return

        input_data = group_widget.get_input_data()
        icao_le = getattr(self, 'lineEdit_airport_name', self.findChild(QtWidgets.QLineEdit, "lineEdit_airport_name"))
        icao_code = icao_le.text().strip().upper() if icao_le else ""

        # --- Initialize Results ---
        calculation_results = { # Default/error values
            "reciprocal_desig_full": NA_PLACEHOLDER, "runway_name": WIDGET_MISSING_MSG,
            "distance": WIDGET_MISSING_MSG, "azimuth": WIDGET_MISSING_MSG,
            "type1_label_text": "(Primary End) Type:", "type2_label_text": "(Reciprocal End) Type:",
        }

        # --- Perform Calculations ---
        try:
            # Designator & Name
            rwy_desig_str = input_data.get('designator_str')
            rwy_suffix = input_data.get('suffix', '')
            full_desig_1_str, full_desig_2_str = "??", "??"
            type1_label_str, type2_label_str = calculation_results["type1_label_text"], calculation_results["type2_label_text"]
            rwy_name_str = calculation_results["runway_name"]

            try: # Inner try for designation math
                if not rwy_desig_str: raise ValueError("Designation empty")
                rwy_desig_val = int(rwy_desig_str);
                if not (1 <= rwy_desig_val <= 36): raise ValueError("Designation out of range (1-36)")
                full_desig_1_str = f"{rwy_desig_val:02d}{rwy_suffix}"
                type1_label_str = f"{full_desig_1_str} End Type:"
                reciprocal_val = (rwy_desig_val + 18) if rwy_desig_val <= 18 else (rwy_desig_val - 18)
                rec_desig_num_str = f"{reciprocal_val:02d}"
                rec_suffix_map = {"L": "R", "R": "L", "C": "C", "": ""}
                rec_suffix = rec_suffix_map.get(rwy_suffix, "")
                full_desig_2_str = f"{rec_desig_num_str}{rec_suffix}"
                type2_label_str = f"{full_desig_2_str} End Type:"
                base_name = f"Runway {full_desig_1_str}/{full_desig_2_str}"
                rwy_name_str = f"{icao_code} {base_name}" if icao_code else base_name
            except ValueError:
                full_desig_2_str = "Invalid"; rwy_name_str = "Invalid Designation"
            calculation_results.update({
                "reciprocal_desig_full": full_desig_2_str, "runway_name": rwy_name_str,
                "type1_label_text": type1_label_str, "type2_label_text": type2_label_str
            })

            # Distance & Azimuth
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
        group_widget.update_display_labels(calculation_results)

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

        new_group = RunwayWidgetGroup(index=runway_index,
                                      coord_validator=self.coord_validator,
                                      parent=scroll_content_widget)

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
        # ... (Get display name logic as before) ...
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

    # =========================================================================
    # == CNS Manual Entry Methods (Unchanged)
    # =========================================================================
    # ... (add_cns_row and remove_cns_rows methods are identical to previous version) ...
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


    # =========================================================================
    # == Data Gathering Methods (Updated for new fields)
    # =========================================================================
    def get_all_input_data(self) -> Optional[Dict[str, Any]]:
        """
        Gathers all validated inputs (global, runways, CNS).
        Returns dict or None if critical validation fails.
        """
        final_data = {}
        validation_ok = True
        error_messages = []

        # --- Global Inputs ---
        icao, arp_pt, arp_e, arp_n, met_pt = self._get_global_inputs()
        if icao is None: return None
        final_data.update({
            'icao_code': icao, 'arp_point': arp_pt, 'arp_easting': arp_e,
            'arp_northing': arp_n, 'met_point': met_pt
        })

        # --- Runway Inputs ---
        runway_data_list = []
        if not self._runway_groups:
             validation_ok = False; error_messages.append("At least one runway definition is required.")
        else:
            for index, group_widget in sorted(self._runway_groups.items()):
                runway_inputs = group_widget.get_input_data()
                validated_runway = self._validate_runway_data(index, runway_inputs, error_messages) # Pass error list
                if validated_runway:
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

        return final_data


    def _validate_runway_data(self, index: int, inputs: Dict[str, str], errors: List[str]) -> Optional[Dict[str, Any]]:
        """Validates raw inputs for a single runway."""
        validated = {'original_index': index}
        current_errors = 0
        
        # Add a log at the very start of THIS specific validation call
        QgsMessageLog.logMessage(f"--- Validating Rwy {index} --- Inputs Dict: {inputs}", DIALOG_LOG_TAG, Qgis.Info)
        
        # Designator
        desig_str = inputs.get('designator_str', '')
        try:
            desig_val = int(desig_str)
            if not (1 <= desig_val <= 36): raise ValueError("Designator must be 01-36")
            validated['designator_num'] = desig_val
            validated['suffix'] = inputs.get('suffix', '')
        except ValueError as e:
            errors.append(f"Rwy {index}: Invalid primary designator '{desig_str}'. ({e})")
            current_errors += 1
            
        # Validate Coordinates (Threshold 1)
        thr_east_str = inputs.get('thr_easting', '')
        thr_north_str = inputs.get('thr_northing', '')
        # --- Log strings BEFORE conversion ---
        QgsMessageLog.logMessage(f"Rwy {index} Thr1 Strings: E={repr(thr_east_str)}, N={repr(thr_north_str)}", DIALOG_LOG_TAG, Qgis.Info)
        try:
            thr_east_f = float(thr_east_str)
            thr_north_f = float(thr_north_str)
            validated['thr_point'] = QgsPointXY(thr_east_f, thr_north_f)
            QgsMessageLog.logMessage(f"Rwy {index} Thr1 Conversion OK", DIALOG_LOG_TAG, Qgis.Info) # Log success
        except (ValueError, TypeError) as e:
            errors.append(f"Rwy {index}: Invalid primary threshold coordinates (Input: E='{thr_east_str}', N='{thr_north_str}'). Error: {e}") # Add error details
            validated['thr_point'] = None
            current_errors += 1
            QgsMessageLog.logMessage(f"Rwy {index} Thr1 Conversion FAILED: {e}", DIALOG_LOG_TAG, Qgis.Warning) # Log failure
            
        # Validate Coordinates (Threshold 2)
        rec_east_str = inputs.get('rec_easting', '')
        rec_north_str = inputs.get('rec_northing', '')
        # --- Log strings BEFORE conversion ---
        QgsMessageLog.logMessage(f"Rwy {index} Thr2 Strings: E={repr(rec_east_str)}, N={repr(rec_north_str)}", DIALOG_LOG_TAG, Qgis.Info)
        try:
            rec_east_f = float(rec_east_str)
            rec_north_f = float(rec_north_str)
            validated['rec_thr_point'] = QgsPointXY(rec_east_f, rec_north_f)
            QgsMessageLog.logMessage(f"Rwy {index} Thr2 Conversion OK", DIALOG_LOG_TAG, Qgis.Info) # Log success
        except (ValueError, TypeError) as e:
            errors.append(f"Rwy {index}: Invalid reciprocal threshold coordinates (Input: E='{rec_east_str}', N='{rec_north_str}'). Error: {e}") # Add error details
            validated['rec_thr_point'] = None
            current_errors += 1
            QgsMessageLog.logMessage(f"Rwy {index} Thr2 Conversion FAILED: {e}", DIALOG_LOG_TAG, Qgis.Warning) # Log failure
            
        # Check if points are valid and not coincident - USE CORRECT KEYS
        # <<< KEY NAME CHANGE >>>
        pt1 = validated.get('thr_point')
        pt2 = validated.get('rec_thr_point')
        if pt1 and pt2:
            if pt1.distance(pt2) < 1e-6:
                 errors.append(f"Rwy {index}: Threshold coordinates are identical.")
                 current_errors += 1
        # Note: If pt1 or pt2 is None from previous errors, this check is skipped implicitly
                
        # Validate Elevations (Optional)
        try: # Primary Elevation
            elev1_str = inputs.get('thr_elev_1', '').strip()
            validated['thr_elev_1'] = float(elev1_str) if elev1_str else None
        except ValueError: errors.append(f"Rwy {index}: Invalid primary elevation '{inputs.get('thr_elev_1', '')}'."); current_errors += 1; validated['thr_elev_1'] = None
        try: # Reciprocal Elevation
            elev2_str = inputs.get('thr_elev_2', '').strip()
            validated['thr_elev_2'] = float(elev2_str) if elev2_str else None
        except ValueError: errors.append(f"Rwy {index}: Invalid reciprocal elevation '{inputs.get('thr_elev_2', '')}'."); current_errors += 1; validated['thr_elev_2'] = None
        
        # Width (Mandatory positive)
        try:
            width_val = float(inputs.get('width', ''))
            if width_val <= 0: raise ValueError("Width must be positive")
            validated['width'] = width_val
        except (ValueError, TypeError):
            errors.append(f"Rwy {index}: Invalid runway width '{inputs.get('width', '')}'. Must be a positive number.")
            current_errors += 1
            
        # Shoulder (Optional, non-negative)
        try:
            shoulder_str = inputs.get('shoulder', '').strip()
            if shoulder_str:
                shoulder_val = float(shoulder_str)
                if shoulder_val < 0: raise ValueError("Shoulder cannot be negative")
                validated['shoulder'] = shoulder_val
            else: validated['shoulder'] = None # Explicitly None if empty
        except ValueError:
            errors.append(f"Rwy {index}: Invalid shoulder width '{inputs.get('shoulder', '')}'. Must be non-negative.")
            current_errors += 1
            
        # Optional fields (just copy text)
        validated['arc_num'] = inputs.get('arc_num')
        validated['arc_let'] = inputs.get('arc_let')
        validated['type1'] = inputs.get('type1')
        validated['type2'] = inputs.get('type2')
        
        # Final log for this validation attempt
        QgsMessageLog.logMessage(f"--- Validation Result Rwy {index}: Success={current_errors == 0}, ThrPt1_Valid={validated.get('thr_point') is not None}, ThrPt2_Valid={validated.get('rec_thr_point') is not None}", DIALOG_LOG_TAG, Qgis.Info)
        return validated if current_errors == 0 else None

    # ... (_get_global_inputs and _get_cns_manual_data remain the same) ...
    def _get_global_inputs(self) -> tuple[Optional[str], Optional[QgsPointXY], Optional[float], Optional[float], Optional[QgsPointXY]]:
        """Retrieves and validates ICAO, ARP coords, and MET coords."""
        icao_code: Optional[str] = None
        arp_point: Optional[QgsPointXY] = None
        arp_east: Optional[float] = None
        arp_north: Optional[float] = None
        met_point_proj_crs: Optional[QgsPointXY] = None

        try:
            icao_lineEdit = getattr(self, 'lineEdit_airport_name', self.findChild(QtWidgets.QLineEdit, "lineEdit_airport_name"))
            arp_east_lineEdit = getattr(self, 'lineEdit_arp_easting', self.findChild(QtWidgets.QLineEdit, "lineEdit_arp_easting"))
            arp_north_lineEdit = getattr(self, 'lineEdit_arp_northing', self.findChild(QtWidgets.QLineEdit, "lineEdit_arp_northing"))
            met_east_lineEdit = getattr(self, 'lineEdit_met_easting', self.findChild(QtWidgets.QLineEdit, "lineEdit_met_easting"))
            met_north_lineEdit = getattr(self, 'lineEdit_met_northing', self.findChild(QtWidgets.QLineEdit, "lineEdit_met_northing"))

            if not icao_lineEdit: raise RuntimeError("UI Error: Cannot find 'lineEdit_airport_name'.")
            icao_code_str = icao_lineEdit.text().strip().upper()
            if not icao_code_str:
                QMessageBox.critical(self, self.tr("Input Error"), self.tr("Airport ICAO Code is required."))
                return None, None, None, None, None
            icao_code = icao_code_str

            # ARP (Optional)
            if arp_east_lineEdit and arp_north_lineEdit:
                arp_east_str = arp_east_lineEdit.text().strip()
                arp_north_str = arp_north_lineEdit.text().strip()
                if arp_east_str and arp_north_str:
                    try:
                        arp_east_val = float(arp_east_str); arp_north_val = float(arp_north_str)
                        arp_point = QgsPointXY(arp_east_val, arp_north_val)
                        arp_east, arp_north = arp_east_val, arp_north_val
                    except ValueError:
                        QMessageBox.warning(self, self.tr("Input Warning"), self.tr("Invalid ARP coordinate format. ARP ignored."))
                        arp_point, arp_east, arp_north = None, None, None

            # MET Station (Optional)
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

        except (AttributeError, RuntimeError, Exception) as e:
            # ... (error handling as before) ...
            return None, None, None, None, None

        return icao_code, arp_point, arp_east, arp_north, met_point_proj_crs

    def _get_cns_manual_data(self) -> Optional[List[Dict[str, Any]]]:
        """Reads and validates CNS facility data from the manual entry table."""
        cns_facilities_data = []
        cns_table = getattr(self, 'table_cns_facility', self.findChild(QtWidgets.QTableWidget, 'table_cns_facility'))
        if not cns_table: # ... (error handling as before) ...
             return None
        project_crs = QgsProject.instance().crs()
        if not project_crs or not project_crs.isValid(): # ... (error handling as before) ...
             return None

        skipped_rows, rows_with_errors, total_rows = 0, 0, cns_table.rowCount()
        for row in range(total_rows):
            # ... (validation logic for each CNS row is identical to previous version) ...
            facility_type = ""
            facility_elevation: Optional[float] = None
            point_geom_project_crs: Optional[QgsGeometry] = None
            valid_row = True
            error_in_row = False
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
                            point_xy = QgsPointXY(float(x_str), float(y_str))
                            point_geom_project_crs = QgsGeometry.fromPointXY(point_xy)
                            if point_geom_project_crs.isNull(): valid_row = False; error_in_row = True; QgsMessageLog.logMessage(f"CNS Row {row+1}: Null geom.", DIALOG_LOG_TAG, level=Qgis.Warning)
                        except ValueError: valid_row = False; error_in_row = True; QgsMessageLog.logMessage(f"CNS Row {row+1}: Invalid coords.", DIALOG_LOG_TAG, level=Qgis.Warning)
                if valid_row:
                    elev_item = cns_table.item(row, 3); elev_str = elev_item.text().strip() if elev_item else ""
                    if elev_str:
                        try: facility_elevation = float(elev_str)
                        except ValueError: facility_elevation = None; QgsMessageLog.logMessage(f"CNS Row {row+1}: Invalid elev.", DIALOG_LOG_TAG, level=Qgis.Warning)
            except Exception as e: valid_row = False; error_in_row = True; QgsMessageLog.logMessage(f"CNS Row {row+1} Error: {e}", DIALOG_LOG_TAG, level=Qgis.Critical)

            if valid_row and point_geom_project_crs:
                facility_id = f'Manual_{row+1}_{facility_type.replace(" ", "_").replace("-","").replace("(","").replace(")","")}'[:50]
                cns_facilities_data.append({'id': facility_id, 'type': facility_type, 'geom': point_geom_project_crs, 'elevation': facility_elevation, 'params': {} })
            elif error_in_row: rows_with_errors += 1; skipped_rows += 1
            elif not valid_row: skipped_rows += 1

        # ... (Final feedback message box logic identical to previous version) ...
        if rows_with_errors > 0: QMessageBox.warning(self, "CNS Data Warning", f"{rows_with_errors} CNS row(s) had errors and were skipped.\n({skipped_rows} total skipped). Check Log.")
        elif skipped_rows > 0 and skipped_rows == total_rows and total_rows > 0: QMessageBox.information(self, "CNS Data Info", "All CNS rows skipped (missing data).")
        elif skipped_rows > 0: QMessageBox.information(self, "CNS Data Info", f"{skipped_rows} CNS rows skipped (missing data).")

        return cns_facilities_data


    # =========================================================================
    # == Action Button Handlers (Logic mostly unchanged, relies on helpers)
    # =========================================================================
    def clear_all_inputs(self, confirm: bool = True) -> None:
        """Clears all inputs, removes all runways, adds one back, clears CNS."""
        if confirm:
            reply = QMessageBox.question(self, self.tr('Confirm Clear'), self.tr("Clear all inputs?"),
                                         QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No,
                                         QtWidgets.QMessageBox.StandardButton.No)
            if reply == QtWidgets.QMessageBox.StandardButton.No: return

        # Clear CNS
        cns_table = getattr(self, 'table_cns_facility', self.findChild(QtWidgets.QTableWidget, 'table_cns_facility'))
        if cns_table: cns_table.setRowCount(0)

        # Clear Global
        for name in ["lineEdit_airport_name", "lineEdit_arp_easting", "lineEdit_arp_northing", "lineEdit_met_easting", "lineEdit_met_northing"]:
             widget = getattr(self, name, self.findChild(QtWidgets.QLineEdit, name))
             if widget: widget.clear()

        # Remove ALL Runway Groups
        indices_to_remove = list(self._runway_groups.keys())
        for index in indices_to_remove:
            self._remove_runway_group_internal(index)

        # Reset State
        self._runway_groups.clear()
        self._runway_id_counter = 0

        # Add back one empty runway group
        if self.scroll_area_layout: self.add_runway_group()
        else: QgsMessageLog.logMessage("Warn (Clear): Layout missing, couldn't add runway back.", DIALOG_LOG_TAG, level=Qgis.Warning)

        self._update_dialog_height()

    def save_input_data(self):
        """Gathers current inputs and saves them to a JSON file."""
        # ... (Get filename logic as before) ...
        icao_le = getattr(self, 'lineEdit_airport_name', self.findChild(QtWidgets.QLineEdit, "lineEdit_airport_name"))
        icao_code = icao_le.text().strip().upper() if icao_le else ""
        suggested_filename = f"{icao_code}_safeguarding_inputs.json" if icao_code else "safeguarding_inputs.json"
        file_path, _ = QFileDialog.getSaveFileName(self, self.tr("Save Inputs"), suggested_filename, self.tr("JSON Files (*.json)"))
        if not file_path: return
        if not file_path.lower().endswith(".json"): file_path += ".json"

        data_to_save = {}
        # Save Global Data
        # ... (identical to previous version, reads from widgets) ...
        arp_east_le = getattr(self, 'lineEdit_arp_easting', self.findChild(QtWidgets.QLineEdit, "lineEdit_arp_easting"))
        arp_north_le = getattr(self, 'lineEdit_arp_northing', self.findChild(QtWidgets.QLineEdit, "lineEdit_arp_northing"))
        met_east_le = getattr(self, 'lineEdit_met_easting', self.findChild(QtWidgets.QLineEdit, "lineEdit_met_easting"))
        met_north_le = getattr(self, 'lineEdit_met_northing', self.findChild(QtWidgets.QLineEdit, "lineEdit_met_northing"))
        data_to_save["icao_code"] = icao_code
        data_to_save["arp_easting"] = arp_east_le.text() if arp_east_le else ""
        data_to_save["arp_northing"] = arp_north_le.text() if arp_north_le else ""
        data_to_save["met_easting"] = met_east_le.text() if met_east_le else ""
        data_to_save["met_northing"] = met_north_le.text() if met_north_le else ""

        # Save Runway Data (uses get_input_data from helper class)
        data_to_save["runways"] = [self._runway_groups[idx].get_input_data() for idx in sorted(self._runway_groups.keys())]

        # Save CNS Data
        # ... (identical to previous version, reads from table) ...
        cns_list = []
        cns_table = getattr(self, 'table_cns_facility', self.findChild(QtWidgets.QTableWidget, 'table_cns_facility'))
        if cns_table:
            for row in range(cns_table.rowCount()):
                try:
                    combo = cns_table.cellWidget(row, 0)
                    type_txt = combo.currentText() if isinstance(combo, QComboBox) and combo.currentIndex() > 0 else ""
                    x_item, y_item, elev_item = cns_table.item(row, 1), cns_table.item(row, 2), cns_table.item(row, 3)
                    x_txt, y_txt = (x_item.text() if x_item else ""), (y_item.text() if y_item else "")
                    if type_txt and x_txt and y_txt:
                        cns_list.append({"type": type_txt, "easting_x": x_txt, "northing_y": y_txt, "elevation": elev_item.text() if elev_item else ""})
                except Exception as e: QgsMessageLog.logMessage(f"Save CNS row {row+1} error: {e}", DIALOG_LOG_TAG, level=Qgis.Warning)
        data_to_save["cns_facilities"] = cns_list


        # Write JSON
        # ... (identical to previous version) ...
        try:
            with open(file_path, 'w', encoding='utf-8') as f: json.dump(data_to_save, f, indent=4, ensure_ascii=False)
            QMessageBox.information(self, self.tr("Save Successful"), self.tr("Data saved:\n{path}").format(path=file_path))
        except Exception as e:
             error_msg = self.tr("Error saving data:") + f"\n{type(e).__name__}: {e}"
             QgsMessageLog.logMessage(f"Save error {file_path}: {e}", DIALOG_LOG_TAG, level=Qgis.Critical)
             QMessageBox.critical(self, self.tr("Save Error"), error_msg)


    def load_input_data(self):
        """Loads safeguarding inputs from a JSON file."""
        # ... (Confirmation check logic is identical) ...
        has_data = False
        global_widgets = [getattr(self, name, self.findChild(QtWidgets.QLineEdit, name)) for name in ["lineEdit_airport_name", "lineEdit_arp_easting", "lineEdit_met_easting"]]
        if any(w and w.text() for w in global_widgets): has_data = True
        if not has_data and self._runway_groups: has_data = True
        cns_table = getattr(self, 'table_cns_facility', self.findChild(QtWidgets.QTableWidget, 'table_cns_facility'))
        if not has_data and cns_table and cns_table.rowCount() > 0: has_data = True
        if has_data:
            reply = QtWidgets.QMessageBox.question(self, self.tr('Confirm Load'), self.tr("Overwrite current inputs?"),
                                                 QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No,
                                                 QtWidgets.QMessageBox.StandardButton.No)
            if reply == QtWidgets.QMessageBox.StandardButton.No: return

        # ... (File Dialog logic is identical) ...
        file_path, _ = QFileDialog.getOpenFileName(self, self.tr("Load Inputs"), "", self.tr("JSON Files (*.json)"))
        if not file_path: return

        # ... (Read/Validate JSON structure logic is identical) ...
        loaded_data = None
        try:
            with open(file_path, 'r', encoding='utf-8') as f: loaded_data = json.load(f)
            if not isinstance(loaded_data, dict): raise ValueError("Invalid format")
            required = ["icao_code", "arp_easting", "arp_northing", "runways"] # Ensure required keys
            if any(k not in loaded_data for k in required): raise ValueError("Missing keys")
            if not isinstance(loaded_data.get("runways"), list): raise ValueError("'runways' not list")
            if "cns_facilities" in loaded_data and not isinstance(loaded_data.get("cns_facilities"), list): raise ValueError("'cns_facilities' not list")

            # --- Clear Existing Data ---
            self.clear_all_inputs(confirm=False) # Adds one empty group back

            # --- Populate Global Fields ---
            # ... (identical logic using getattr or findChild) ...
            icao_le = getattr(self, 'lineEdit_airport_name', self.findChild(QtWidgets.QLineEdit, "lineEdit_airport_name"))
            arp_east_le = getattr(self, 'lineEdit_arp_easting', self.findChild(QtWidgets.QLineEdit, "lineEdit_arp_easting"))
            arp_north_le = getattr(self, 'lineEdit_arp_northing', self.findChild(QtWidgets.QLineEdit, "lineEdit_arp_northing"))
            met_east_le = getattr(self, 'lineEdit_met_easting', self.findChild(QtWidgets.QLineEdit, "lineEdit_met_easting"))
            met_north_le = getattr(self, 'lineEdit_met_northing', self.findChild(QtWidgets.QLineEdit, "lineEdit_met_northing"))
            if icao_le: icao_le.setText(loaded_data.get("icao_code", ""))
            if arp_east_le: arp_east_le.setText(loaded_data.get("arp_easting", ""))
            if arp_north_le: arp_north_le.setText(loaded_data.get("arp_northing", ""))
            if met_east_le: met_east_le.setText(loaded_data.get("met_easting", ""))
            if met_north_le: met_north_le.setText(loaded_data.get("met_northing", ""))


            # --- Populate Runway Fields ---
            loaded_runways_list = loaded_data.get("runways", [])
            if loaded_runways_list:
                # Populate the first group (already created by clear_all_inputs)
                first_runway_index = min(self._runway_groups.keys()) if self._runway_groups else None
                first_group = self._runway_groups.get(first_runway_index)
                if first_group:
                    first_group.set_input_data(loaded_runways_list[0]) # Populates and triggers update
                else: # Should not happen if clear worked
                     QgsMessageLog.logMessage("Load Error: First runway group missing after clear.", DIALOG_LOG_TAG, level=Qgis.Warning)

                # Add and populate the rest
                for runway_data_item in loaded_runways_list[1:]:
                    try:
                        self.add_runway_group() # Adds widget, stores in dict
                        new_index = self._runway_id_counter
                        new_group = self._runway_groups.get(new_index)
                        if new_group:
                            new_group.set_input_data(runway_data_item) # Populates & triggers update
                        else: QgsMessageLog.logMessage(f"Load Error: Group {new_index} missing after add.", DIALOG_LOG_TAG, level=Qgis.Warning)
                    except Exception as e_loop: QgsMessageLog.logMessage(f"Load Error processing runway item: {e_loop}", DIALOG_LOG_TAG, level=Qgis.Warning)
            elif self._runway_groups: # File has no runways, update the one empty group
                 first_runway_index = min(self._runway_groups.keys())
                 self.update_runway_calculations(first_runway_index)


            # --- Populate CNS Table ---
            # ... (identical logic using cellWidget/setItem) ...
            cns_table = getattr(self, 'table_cns_facility', self.findChild(QtWidgets.QTableWidget, 'table_cns_facility'))
            loaded_cns_list = loaded_data.get("cns_facilities", [])
            if cns_table and loaded_cns_list:
                cns_table.setRowCount(0)
                for item in loaded_cns_list:
                   try:
                       row = cns_table.rowCount(); cns_table.insertRow(row)
                       combo = QComboBox(); combo.addItems([""] + self.CNS_FACILITY_TYPES)
                       idx = combo.findText(item.get("type", ""), QtCore.Qt.MatchFlag.MatchFixedString)
                       combo.setCurrentIndex(idx if idx >= 0 else 0)
                       cns_table.setCellWidget(row, 0, combo)
                       cns_table.setItem(row, 1, QTableWidgetItem(item.get("easting_x", "")))
                       cns_table.setItem(row, 2, QTableWidgetItem(item.get("northing_y", "")))
                       cns_table.setItem(row, 3, QTableWidgetItem(item.get("elevation", "")))
                   except Exception as e: QgsMessageLog.logMessage(f"Load CNS error: {e}", DIALOG_LOG_TAG, level=Qgis.Warning)

            # --- Final Steps ---
            self._update_dialog_height()
            QMessageBox.information(self, self.tr("Load Successful"), self.tr("Data loaded:\n{path}").format(path=file_path))

        except (IOError, json.JSONDecodeError, ValueError) as e:
            # ... (identical error handling) ...
            error_details = f"{type(e).__name__}: {e}"; log_msg = f"Load Error {file_path}: {error_details}"; user_msg = self.tr("Load Error.") + f"\n{file_path}\n\n{self.tr('Error')}: {error_details}"
            QgsMessageLog.logMessage(log_msg, DIALOG_LOG_TAG, level=Qgis.Critical); QMessageBox.critical(self, self.tr("Load Error"), user_msg)
            try: self.clear_all_inputs(confirm=False)
            except Exception as clear_err: QgsMessageLog.logMessage(f"Error post-load cleanup: {clear_err}", DIALOG_LOG_TAG, level=Qgis.Critical)
        except Exception as e:
            # ... (identical unexpected error handling) ...
            error_details = f"{type(e).__name__}: {e}"; log_msg = f"Unexpected load error {file_path}: {error_details}"; user_msg = self.tr("Unexpected Load Error.") + f"\n\n{self.tr('Error')}: {error_details}"
            QgsMessageLog.logMessage(log_msg, DIALOG_LOG_TAG, level=Qgis.Critical); QMessageBox.critical(self, self.tr("Load Error"), user_msg)
            try: self.clear_all_inputs(confirm=False)
            except Exception as clear_err: QgsMessageLog.logMessage(f"Error post-load cleanup: {clear_err}", DIALOG_LOG_TAG, level=Qgis.Critical)

# ========================= End of Class Definition =========================

# ... (Optional __main__ block for basic testing remains the same) ...
if __name__ == '__main__':
    import sys
    from qgis.PyQt.QtWidgets import QApplication
    class MockQgisInterface: pass
    class MockQgsProject:
        def instance(self): return self
        def crs(self): return QgsCoordinateReferenceSystem("EPSG:4326") # Example
    if not QgsProject.instance(): QgsProject.instance = MockQgsProject.instance # Patch only if needed

    app = QApplication(sys.argv)
    dialog = SafeguardingBuilderDialog()
    dialog.show()
    sys.exit(app.exec())