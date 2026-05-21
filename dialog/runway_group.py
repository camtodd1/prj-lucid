# -*- coding: utf-8 -*-
"""Dynamic runway input widget used by the main dialog."""

from typing import Dict, Optional

from qgis.PyQt import QtCore, QtGui, QtWidgets  # type: ignore

from .dialog_constants import (
    CALC_PLACEHOLDER,
    NA_PLACEHOLDER,
    WIDGET_MISSING_MSG,
)


class RunwayWidgetGroup(QtWidgets.QGroupBox):
    """
    Manages the UI elements and layout for a single runway group.

    The main dialog owns the calculations and validation; this widget owns
    runway-specific controls, value access, and change/remove signals.
    """

    inputChanged = QtCore.pyqtSignal()
    removeRequested = QtCore.pyqtSignal(int)

    def __init__(
        self,
        index: int,
        coord_validator: QtGui.QValidator,
        parent: QtWidgets.QWidget = None,
    ):
        title = f"Runway {index}"
        super().__init__(title, parent)

        self.index = index
        self.numeric_validator = QtGui.QDoubleValidator()
        self.numeric_validator.setNotation(
            QtGui.QDoubleValidator.Notation.StandardNotation
        )
        self.coord_validator = coord_validator
        self.distance_validator = QtGui.QDoubleValidator(0.0, 9999.9, 1, self)
        self.distance_validator.setNotation(
            QtGui.QDoubleValidator.Notation.StandardNotation
        )

        self.setObjectName(f"groupBox_runway_{self.index}")
        self.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Preferred,
            QtWidgets.QSizePolicy.Policy.MinimumExpanding,
        )

        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        groupBox_layout = QtWidgets.QVBoxLayout(self)

        gridLayout_Coords = QtWidgets.QGridLayout()
        gridLayout_Coords.setObjectName(f"gridLayout_Coords_{self.index}")
        gridLayout_Coords.setColumnStretch(0, 2)
        gridLayout_Coords.setColumnStretch(1, 1)
        gridLayout_Coords.setColumnStretch(2, 1)

        label_designation_row = QtWidgets.QLabel("Designation:")
        label_designation_row.setAlignment(
            QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter
        )
        label_easting_row = QtWidgets.QLabel("Easting:")
        label_easting_row.setAlignment(
            QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter
        )
        label_northing_row = QtWidgets.QLabel("Northing:")
        label_northing_row.setAlignment(
            QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter
        )
        label_elevation_row = QtWidgets.QLabel("Elevation (m):")
        label_elevation_row.setAlignment(
            QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter
        )
        label_displaced_row = QtWidgets.QLabel("Displaced (m):")
        label_displaced_row.setAlignment(
            QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter
        )
        label_pre_threshold_area_row = QtWidgets.QLabel("Pre-threshold Area (m):")
        label_pre_threshold_area_row.setAlignment(
            QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter
        )

        h_layout_desig_inputs = QtWidgets.QHBoxLayout()
        self.desig_le = QtWidgets.QLineEdit()
        self.desig_le.setObjectName(f"lineEdit_rwy_desig_{self.index}")
        self.desig_le.setMaxLength(2)
        self.desig_le.setToolTip("Enter 2-digit primary designation (01-36).")
        self.desig_le.setValidator(QtGui.QIntValidator(1, 36, self))
        self.suffix_combo = QtWidgets.QComboBox()
        self.suffix_combo.setObjectName(f"comboBox_rwy_suffix_{self.index}")
        self.suffix_combo.addItems(["", "L", "C", "R"])
        self.suffix_combo.setToolTip("Runway suffix (Leave blank if none)")
        self.suffix_combo.setFocusPolicy(QtCore.Qt.FocusPolicy.StrongFocus)
        h_layout_desig_inputs.addWidget(self.desig_le)
        h_layout_desig_inputs.addWidget(self.suffix_combo)

        self.rec_desig_hdr_lbl = QtWidgets.QLabel(CALC_PLACEHOLDER)
        self.rec_desig_hdr_lbl.setObjectName(f"label_header_desig2_{self.index}")
        self.rec_desig_hdr_lbl.setToolTip("Calculated reciprocal designation")
        self.rec_desig_hdr_lbl.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)

        self.thr_east_le = QtWidgets.QLineEdit()
        self.thr_east_le.setObjectName(f"lineEdit_thr_easting_{self.index}")
        self.thr_east_le.setPlaceholderText("e.g., 456789.12")
        self.thr_east_le.setToolTip("Easting coordinate of primary threshold")
        self.thr_east_le.setValidator(self.coord_validator)

        self.thr_north_le = QtWidgets.QLineEdit()
        self.thr_north_le.setObjectName(f"lineEdit_thr_northing_{self.index}")
        self.thr_north_le.setPlaceholderText("e.g., 123456.78")
        self.thr_north_le.setToolTip("Northing coordinate of primary threshold")
        self.thr_north_le.setValidator(self.coord_validator)

        self.rec_east_le = QtWidgets.QLineEdit()
        self.rec_east_le.setObjectName(f"lineEdit_reciprocal_thr_easting_{self.index}")
        self.rec_east_le.setPlaceholderText("e.g., 457890.34")
        self.rec_east_le.setToolTip("Easting coordinate of reciprocal threshold")
        self.rec_east_le.setValidator(self.coord_validator)

        self.rec_north_le = QtWidgets.QLineEdit()
        self.rec_north_le.setObjectName(
            f"lineEdit_reciprocal_thr_northing_{self.index}"
        )
        self.rec_north_le.setPlaceholderText("e.g., 124567.90")
        self.rec_north_le.setToolTip("Northing coordinate of reciprocal threshold")
        self.rec_north_le.setValidator(self.coord_validator)

        self.thr_elev_1_le = QtWidgets.QLineEdit()
        self.thr_elev_1_le.setObjectName(f"lineEdit_thr_elev_1_{self.index}")
        self.thr_elev_1_le.setPlaceholderText("e.g., 150.5")
        self.thr_elev_1_le.setToolTip("Elevation (AMSL) of primary threshold")
        self.thr_elev_1_le.setValidator(self.numeric_validator)

        self.thr_elev_2_le = QtWidgets.QLineEdit()
        self.thr_elev_2_le.setObjectName(f"lineEdit_thr_elev_2_{self.index}")
        self.thr_elev_2_le.setPlaceholderText("e.g., 149.8")
        self.thr_elev_2_le.setToolTip("Elevation (AMSL) of reciprocal threshold")
        self.thr_elev_2_le.setValidator(self.numeric_validator)

        self.thr_displaced_1_le = QtWidgets.QLineEdit()
        self.thr_displaced_1_le.setObjectName(f"lineEdit_thr_displaced_1_{self.index}")
        self.thr_displaced_1_le.setPlaceholderText("e.g., 300")
        self.thr_displaced_1_le.setToolTip(
            "Displaced threshold distance for primary end (meters). Leave blank if none."
        )
        self.thr_displaced_1_le.setValidator(self.distance_validator)

        self.thr_displaced_2_le = QtWidgets.QLineEdit()
        self.thr_displaced_2_le.setObjectName(f"lineEdit_thr_displaced_2_{self.index}")
        self.thr_displaced_2_le.setPlaceholderText("e.g., 0")
        self.thr_displaced_2_le.setToolTip(
            "Displaced threshold distance for reciprocal end (meters). Leave blank if none."
        )
        self.thr_displaced_2_le.setValidator(self.distance_validator)

        self.thr_pre_area_1_le = QtWidgets.QLineEdit()
        self.thr_pre_area_1_le.setObjectName(f"lineEdit_thr_pre_area_1_{self.index}")
        self.thr_pre_area_1_le.setPlaceholderText("e.g., 60")
        self.thr_pre_area_1_le.setToolTip(
            "Length of pre-threshold area for primary end (meters). Leave blank if none."
        )
        self.thr_pre_area_1_le.setValidator(self.distance_validator)

        self.thr_pre_area_2_le = QtWidgets.QLineEdit()
        self.thr_pre_area_2_le.setObjectName(f"lineEdit_thr_pre_area_2_{self.index}")
        self.thr_pre_area_2_le.setPlaceholderText("e.g., 60")
        self.thr_pre_area_2_le.setToolTip(
            "Length of pre-threshold area for reciprocal end (meters). Leave blank if none."
        )
        self.thr_pre_area_2_le.setValidator(self.distance_validator)

        current_coord_row = 0
        gridLayout_Coords.addWidget(label_designation_row, current_coord_row, 0)
        gridLayout_Coords.addLayout(h_layout_desig_inputs, current_coord_row, 1)
        gridLayout_Coords.addWidget(self.rec_desig_hdr_lbl, current_coord_row, 2)
        current_coord_row += 1
        gridLayout_Coords.addWidget(label_easting_row, current_coord_row, 0)
        gridLayout_Coords.addWidget(self.thr_east_le, current_coord_row, 1)
        gridLayout_Coords.addWidget(self.rec_east_le, current_coord_row, 2)
        current_coord_row += 1
        gridLayout_Coords.addWidget(label_northing_row, current_coord_row, 0)
        gridLayout_Coords.addWidget(self.thr_north_le, current_coord_row, 1)
        gridLayout_Coords.addWidget(self.rec_north_le, current_coord_row, 2)
        current_coord_row += 1
        gridLayout_Coords.addWidget(label_elevation_row, current_coord_row, 0)
        gridLayout_Coords.addWidget(self.thr_elev_1_le, current_coord_row, 1)
        gridLayout_Coords.addWidget(self.thr_elev_2_le, current_coord_row, 2)
        current_coord_row += 1
        gridLayout_Coords.addWidget(label_displaced_row, current_coord_row, 0)
        gridLayout_Coords.addWidget(self.thr_displaced_1_le, current_coord_row, 1)
        gridLayout_Coords.addWidget(self.thr_displaced_2_le, current_coord_row, 2)
        current_coord_row += 1
        gridLayout_Coords.addWidget(label_pre_threshold_area_row, current_coord_row, 0)
        gridLayout_Coords.addWidget(self.thr_pre_area_1_le, current_coord_row, 1)
        gridLayout_Coords.addWidget(self.thr_pre_area_2_le, current_coord_row, 2)

        groupBox_layout.addLayout(gridLayout_Coords)
        self._add_declared_distance_controls(groupBox_layout)

        self.rwy_name_lbl = QtWidgets.QLabel(CALC_PLACEHOLDER)
        self.rwy_name_lbl.setObjectName(f"label_rwy_name_{self.index}")
        self.rwy_name_lbl.setAlignment(
            QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter
        )
        font = self.rwy_name_lbl.font()
        font.setBold(True)
        self.rwy_name_lbl.setFont(font)
        self.rwy_name_lbl.setContentsMargins(0, 5, 0, 5)
        groupBox_layout.addWidget(self.rwy_name_lbl)

        detailsLayout = QtWidgets.QGridLayout()
        detailsLayout.setObjectName(f"detailsLayout_{self.index}")
        detailsLayout.setColumnStretch(0, 1)
        detailsLayout.setColumnStretch(1, 1)
        current_details_row = 0

        label_rwy_dist_text = QtWidgets.QLabel("Length (m):")
        label_rwy_dist_text.setAlignment(
            QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter
        )
        self.dist_lbl = QtWidgets.QLabel(CALC_PLACEHOLDER)
        self.dist_lbl.setObjectName(f"label_rwy_distance_{self.index}")
        detailsLayout.addWidget(label_rwy_dist_text, current_details_row, 0)
        detailsLayout.addWidget(self.dist_lbl, current_details_row, 1)
        current_details_row += 1

        label_rwy_azim_text = QtWidgets.QLabel("Azimuth (deg):")
        label_rwy_azim_text.setAlignment(
            QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter
        )
        self.azim_lbl = QtWidgets.QLabel(CALC_PLACEHOLDER)
        self.azim_lbl.setObjectName(f"label_rwy_azimuth_{self.index}")
        detailsLayout.addWidget(label_rwy_azim_text, current_details_row, 0)
        detailsLayout.addWidget(self.azim_lbl, current_details_row, 1)
        current_details_row += 1

        label_runway_width = QtWidgets.QLabel("Runway Width (m):")
        label_runway_width.setAlignment(
            QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter
        )
        self.width_le = QtWidgets.QLineEdit()
        self.width_le.setObjectName(f"lineEdit_runway_width_{self.index}")
        self.width_le.setToolTip("Enter actual runway width (meters).")
        width_validator = QtGui.QDoubleValidator(0.01, 9999.99, 2, self)
        width_validator.setNotation(QtGui.QDoubleValidator.Notation.StandardNotation)
        self.width_le.setValidator(width_validator)
        detailsLayout.addWidget(label_runway_width, current_details_row, 0)
        detailsLayout.addWidget(self.width_le, current_details_row, 1)
        current_details_row += 1

        label_runway_shoulder = QtWidgets.QLabel("Runway Shoulder (m):")
        label_runway_shoulder.setAlignment(
            QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter
        )
        self.shoulder_le = QtWidgets.QLineEdit()
        self.shoulder_le.setObjectName(f"lineEdit_rwy_shoulder_{self.index}")
        self.shoulder_le.setToolTip(
            "Enter width of runway shoulder (each side, if applicable)."
        )
        self.shoulder_le.setValidator(self.distance_validator)
        detailsLayout.addWidget(label_runway_shoulder, current_details_row, 0)
        detailsLayout.addWidget(self.shoulder_le, current_details_row, 1)
        current_details_row += 1

        self._add_arc_controls(detailsLayout, current_details_row)
        current_details_row += 2
        self._add_runway_type_controls(detailsLayout, current_details_row)

        groupBox_layout.addLayout(detailsLayout)

        line_separator = QtWidgets.QFrame()
        line_separator.setObjectName(f"line_runway_group_{self.index}")
        line_separator.setFrameShape(QtWidgets.QFrame.Shape.HLine)
        line_separator.setFrameShadow(QtWidgets.QFrame.Shadow.Sunken)
        groupBox_layout.addWidget(line_separator)

        self.remove_button = QtWidgets.QPushButton("Remove This Runway")
        self.remove_button.setObjectName(f"pushButton_remove_runway_{self.index}")
        self.remove_button.setToolTip("Remove this runway")
        groupBox_layout.addWidget(self.remove_button)

    def _add_arc_controls(self, layout: QtWidgets.QGridLayout, row: int) -> None:
        label_arc_num = QtWidgets.QLabel("ARC Number:")
        label_arc_num.setAlignment(
            QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter
        )
        self.arc_num_combo = QtWidgets.QComboBox()
        self.arc_num_combo.setObjectName(f"comboBox_arc_num_{self.index}")
        for label, value in [
            ("", ""),
            ("1 (<800m)", "1"),
            ("2 (800 - 1200m)", "2"),
            ("3 (1200 - 1800m)", "3"),
            ("4 (>=1800m)", "4"),
        ]:
            self.arc_num_combo.addItem(label, userData=value)
        self.arc_num_combo.setToolTip("Select Aerodrome Reference Code Number")
        self.arc_num_combo.setFocusPolicy(QtCore.Qt.FocusPolicy.StrongFocus)
        layout.addWidget(label_arc_num, row, 0)
        layout.addWidget(self.arc_num_combo, row, 1)

        label_arc_let = QtWidgets.QLabel("ARC Letter:")
        label_arc_let.setAlignment(
            QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter
        )
        self.arc_let_combo = QtWidgets.QComboBox()
        self.arc_let_combo.setObjectName(f"comboBox_arc_let_{self.index}")
        for label, value in [
            ("", ""),
            ("A (Cessna 172)", "A"),
            ("B (Pilatus PC-12)", "B"),
            ("C (DHC-8, B737)", "C"),
            ("D (B767)", "D"),
            ("E (B777, A330, B787)", "E"),
            ("F (A380, B747)", "F"),
        ]:
            self.arc_let_combo.addItem(label, userData=value)
        self.arc_let_combo.setToolTip("Select Aerodrome Reference Code Letter")
        self.arc_let_combo.setFocusPolicy(QtCore.Qt.FocusPolicy.StrongFocus)
        layout.addWidget(label_arc_let, row + 1, 0)
        layout.addWidget(self.arc_let_combo, row + 1, 1)

    def _add_runway_type_controls(self, layout: QtWidgets.QGridLayout, row: int) -> None:
        runway_types = [
            "",
            "Non-Instrument (NI)",
            "Non-Precision Approach (NPA)",
            "Precision Approach CAT I",
            "Precision Approach CAT II/III",
        ]
        self.type1_lbl = QtWidgets.QLabel("(Primary End) Type:")
        self.type1_lbl.setObjectName(f"label_type_desig1_{self.index}")
        self.type1_lbl.setAlignment(
            QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter
        )
        self.type1_combo = QtWidgets.QComboBox()
        self.type1_combo.setObjectName(f"comboBox_type_desig1_{self.index}")
        self.type1_combo.addItems(runway_types)
        self.type1_combo.setToolTip("Select type for primary end.")
        self.type1_combo.setFocusPolicy(QtCore.Qt.FocusPolicy.StrongFocus)
        layout.addWidget(self.type1_lbl, row, 0)
        layout.addWidget(self.type1_combo, row, 1)

        self.type2_lbl = QtWidgets.QLabel("(Reciprocal End) Type:")
        self.type2_lbl.setObjectName(f"label_type_desig2_{self.index}")
        self.type2_lbl.setAlignment(
            QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter
        )
        self.type2_combo = QtWidgets.QComboBox()
        self.type2_combo.setObjectName(f"comboBox_type_desig2_{self.index}")
        self.type2_combo.addItems(runway_types)
        self.type2_combo.setToolTip("Select type for reciprocal end.")
        self.type2_combo.setFocusPolicy(QtCore.Qt.FocusPolicy.StrongFocus)
        layout.addWidget(self.type2_lbl, row + 1, 0)
        layout.addWidget(self.type2_combo, row + 1, 1)

    def _add_declared_distance_controls(self, parent_layout: QtWidgets.QVBoxLayout):
        declared_group = QtWidgets.QGroupBox("Declared Distances")
        declared_group.setObjectName(f"groupBox_declared_distances_{self.index}")
        declared_layout = QtWidgets.QGridLayout(declared_group)
        declared_layout.setColumnStretch(0, 2)
        declared_layout.setColumnStretch(1, 1)
        declared_layout.setColumnStretch(2, 1)

        primary_label = QtWidgets.QLabel("Primary End")
        reciprocal_label = QtWidgets.QLabel("Reciprocal End")
        primary_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        reciprocal_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        declared_layout.addWidget(primary_label, 0, 1)
        declared_layout.addWidget(reciprocal_label, 0, 2)

        clearway_label = QtWidgets.QLabel("Clearway (m):")
        self.clearway1_len_le = QtWidgets.QLineEdit()
        self.clearway1_len_le.setObjectName(f"lineEdit_clearway1_len_{self.index}")
        self.clearway1_len_le.setPlaceholderText("0")
        self.clearway1_len_le.setToolTip(
            "Clearway length beyond the primary physical runway end."
        )
        self.clearway1_len_le.setValidator(self.distance_validator)

        self.clearway2_len_le = QtWidgets.QLineEdit()
        self.clearway2_len_le.setObjectName(f"lineEdit_clearway2_len_{self.index}")
        self.clearway2_len_le.setPlaceholderText("0")
        self.clearway2_len_le.setToolTip(
            "Clearway length beyond the reciprocal physical runway end."
        )
        self.clearway2_len_le.setValidator(self.distance_validator)
        declared_layout.addWidget(clearway_label, 1, 0)
        declared_layout.addWidget(self.clearway1_len_le, 1, 1)
        declared_layout.addWidget(self.clearway2_len_le, 1, 2)

        stopway_label = QtWidgets.QLabel("Stopway (m):")
        self.stopway1_len_le = QtWidgets.QLineEdit()
        self.stopway1_len_le.setObjectName(f"lineEdit_stopway1_len_{self.index}")
        self.stopway1_len_le.setPlaceholderText("0")
        self.stopway1_len_le.setToolTip(
            "Stopway length beyond the primary physical runway end."
        )
        self.stopway1_len_le.setValidator(self.distance_validator)

        self.stopway2_len_le = QtWidgets.QLineEdit()
        self.stopway2_len_le.setObjectName(f"lineEdit_stopway2_len_{self.index}")
        self.stopway2_len_le.setPlaceholderText("0")
        self.stopway2_len_le.setToolTip(
            "Stopway length beyond the reciprocal physical runway end."
        )
        self.stopway2_len_le.setValidator(self.distance_validator)
        declared_layout.addWidget(stopway_label, 2, 0)
        declared_layout.addWidget(self.stopway1_len_le, 2, 1)
        declared_layout.addWidget(self.stopway2_len_le, 2, 2)

        takeoff_label = QtWidgets.QLabel("Takeoff available:")
        self.takeoff_available_1_cb = QtWidgets.QCheckBox()
        self.takeoff_available_1_cb.setObjectName(
            f"checkBox_takeoff_available_1_{self.index}"
        )
        self.takeoff_available_1_cb.setChecked(True)
        self.takeoff_available_1_cb.setToolTip(
            "Takeoff is available in the primary runway direction."
        )

        self.takeoff_available_2_cb = QtWidgets.QCheckBox()
        self.takeoff_available_2_cb.setObjectName(
            f"checkBox_takeoff_available_2_{self.index}"
        )
        self.takeoff_available_2_cb.setChecked(True)
        self.takeoff_available_2_cb.setToolTip(
            "Takeoff is available in the reciprocal runway direction."
        )
        declared_layout.addWidget(takeoff_label, 3, 0)
        declared_layout.addWidget(self.takeoff_available_1_cb, 3, 1)
        declared_layout.addWidget(self.takeoff_available_2_cb, 3, 2)

        landing_label = QtWidgets.QLabel("Landing available:")
        self.landing_available_1_cb = QtWidgets.QCheckBox()
        self.landing_available_1_cb.setObjectName(
            f"checkBox_landing_available_1_{self.index}"
        )
        self.landing_available_1_cb.setChecked(True)
        self.landing_available_1_cb.setToolTip(
            "Landing is available toward the primary runway threshold."
        )

        self.landing_available_2_cb = QtWidgets.QCheckBox()
        self.landing_available_2_cb.setObjectName(
            f"checkBox_landing_available_2_{self.index}"
        )
        self.landing_available_2_cb.setChecked(True)
        self.landing_available_2_cb.setToolTip(
            "Landing is available toward the reciprocal runway threshold."
        )
        declared_layout.addWidget(landing_label, 4, 0)
        declared_layout.addWidget(self.landing_available_1_cb, 4, 1)
        declared_layout.addWidget(self.landing_available_2_cb, 4, 2)

        parent_layout.addWidget(declared_group)

    def _connect_signals(self):
        for widget in [
            self.desig_le,
            self.thr_east_le,
            self.thr_north_le,
            self.rec_east_le,
            self.rec_north_le,
            self.thr_elev_1_le,
            self.thr_elev_2_le,
            self.thr_displaced_1_le,
            self.thr_displaced_2_le,
            self.thr_pre_area_1_le,
            self.thr_pre_area_2_le,
            self.width_le,
            self.shoulder_le,
            self.clearway1_len_le,
            self.clearway2_len_le,
            self.stopway1_len_le,
            self.stopway2_len_le,
        ]:
            widget.textChanged.connect(self.inputChanged.emit)
        for checkbox in [
            self.takeoff_available_1_cb,
            self.takeoff_available_2_cb,
            self.landing_available_1_cb,
            self.landing_available_2_cb,
        ]:
            checkbox.stateChanged.connect(self.inputChanged.emit)
        for combo in [
            self.suffix_combo,
            self.arc_num_combo,
            self.arc_let_combo,
            self.type1_combo,
            self.type2_combo,
        ]:
            combo.currentIndexChanged.connect(self.inputChanged.emit)
        self.remove_button.clicked.connect(self._emit_remove_request)

    def _arc_number_for_length(self, length_m: float) -> Optional[str]:
        if length_m < 800:
            return "1"
        if length_m < 1200:
            return "2"
        if length_m < 1800:
            return "3"
        return "4"

    def _emit_remove_request(self):
        self.removeRequested.emit(self.index)

    def get_input_data(self) -> Dict[str, str]:
        return {
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
            "thr_pre_area_1": self.thr_pre_area_1_le.text(),
            "thr_pre_area_2": self.thr_pre_area_2_le.text(),
            "width": self.width_le.text(),
            "shoulder": self.shoulder_le.text(),
            "clearway1_len": self.clearway1_len_le.text(),
            "clearway2_len": self.clearway2_len_le.text(),
            "stopway1_len": self.stopway1_len_le.text(),
            "stopway2_len": self.stopway2_len_le.text(),
            "takeoff_available_1": self.takeoff_available_1_cb.isChecked(),
            "takeoff_available_2": self.takeoff_available_2_cb.isChecked(),
            "landing_available_1": self.landing_available_1_cb.isChecked(),
            "landing_available_2": self.landing_available_2_cb.isChecked(),
            "arc_num": self.arc_num_combo.currentData(),
            "arc_let": self.arc_let_combo.currentData(),
            "type1": self.type1_combo.currentText(),
            "type2": self.type2_combo.currentText(),
        }

    def set_input_data(self, data: Dict[str, str]):
        widgets_to_block = self._input_widgets()
        for widget in widgets_to_block:
            widget.blockSignals(True)
        try:
            self.desig_le.setText(data.get("designator_str", ""))
            suffix_idx = self.suffix_combo.findText(
                data.get("suffix", ""), QtCore.Qt.MatchFlag.MatchFixedString
            )
            self.suffix_combo.setCurrentIndex(suffix_idx if suffix_idx >= 0 else 0)
            self.thr_east_le.setText(data.get("thr_easting", ""))
            self.thr_north_le.setText(data.get("thr_northing", ""))
            self.rec_east_le.setText(data.get("rec_easting", ""))
            self.rec_north_le.setText(data.get("rec_northing", ""))
            self.thr_elev_1_le.setText(data.get("thr_elev_1", ""))
            self.thr_elev_2_le.setText(data.get("thr_elev_2", ""))
            self.thr_displaced_1_le.setText(data.get("thr_displaced_1", ""))
            self.thr_displaced_2_le.setText(data.get("thr_displaced_2", ""))
            self.thr_pre_area_1_le.setText(data.get("thr_pre_area_1", ""))
            self.thr_pre_area_2_le.setText(data.get("thr_pre_area_2", ""))
            self.width_le.setText(data.get("width", ""))
            self.shoulder_le.setText(data.get("shoulder", ""))
            self.clearway1_len_le.setText(data.get("clearway1_len", ""))
            self.clearway2_len_le.setText(data.get("clearway2_len", ""))
            self.stopway1_len_le.setText(data.get("stopway1_len", ""))
            self.stopway2_len_le.setText(data.get("stopway2_len", ""))
            self.takeoff_available_1_cb.setChecked(
                self._bool_from_saved_value(data.get("takeoff_available_1", True))
            )
            self.takeoff_available_2_cb.setChecked(
                self._bool_from_saved_value(data.get("takeoff_available_2", True))
            )
            self.landing_available_1_cb.setChecked(
                self._bool_from_saved_value(data.get("landing_available_1", True))
            )
            self.landing_available_2_cb.setChecked(
                self._bool_from_saved_value(data.get("landing_available_2", True))
            )
            self._set_combo_data(self.arc_num_combo, data.get("arc_num", ""))
            self._set_combo_data(self.arc_let_combo, data.get("arc_let", ""))
            self._set_combo_text(self.type1_combo, data.get("type1", ""))
            self._set_combo_text(self.type2_combo, data.get("type2", ""))
        finally:
            for widget in widgets_to_block:
                widget.blockSignals(False)
            self.inputChanged.emit()

    def update_display_labels(self, results: Dict[str, str]):
        self.rec_desig_hdr_lbl.setText(
            results.get("reciprocal_desig_full", NA_PLACEHOLDER)
        )
        self.rwy_name_lbl.setText(results.get("runway_name", WIDGET_MISSING_MSG))
        self.dist_lbl.setText(results.get("distance", WIDGET_MISSING_MSG))
        self.azim_lbl.setText(results.get("azimuth", WIDGET_MISSING_MSG))
        self.type1_lbl.setText(results.get("type1_label_text", "(Primary End) Type:"))
        self.type2_lbl.setText(
            results.get("type2_label_text", "(Reciprocal End) Type:")
        )

    def clear_inputs(self):
        widgets_to_block = self._input_widgets()
        for widget in widgets_to_block:
            widget.blockSignals(True)
        try:
            for line_edit in [
                self.desig_le,
                self.thr_east_le,
                self.thr_north_le,
                self.rec_east_le,
                self.rec_north_le,
                self.thr_elev_1_le,
                self.thr_elev_2_le,
                self.thr_displaced_1_le,
                self.thr_displaced_2_le,
                self.thr_pre_area_1_le,
                self.thr_pre_area_2_le,
                self.width_le,
                self.shoulder_le,
                self.clearway1_len_le,
                self.clearway2_len_le,
                self.stopway1_len_le,
                self.stopway2_len_le,
            ]:
                line_edit.clear()
            for checkbox in [
                self.takeoff_available_1_cb,
                self.takeoff_available_2_cb,
                self.landing_available_1_cb,
                self.landing_available_2_cb,
            ]:
                checkbox.setChecked(True)
            for combo in [
                self.suffix_combo,
                self.arc_num_combo,
                self.arc_let_combo,
                self.type1_combo,
                self.type2_combo,
            ]:
                combo.setCurrentIndex(0)
        finally:
            for widget in widgets_to_block:
                widget.blockSignals(False)
            self.inputChanged.emit()

    def _input_widgets(self):
        return [
            self.desig_le,
            self.suffix_combo,
            self.thr_east_le,
            self.thr_north_le,
            self.rec_east_le,
            self.rec_north_le,
            self.thr_elev_1_le,
            self.thr_elev_2_le,
            self.thr_displaced_1_le,
            self.thr_displaced_2_le,
            self.thr_pre_area_1_le,
            self.thr_pre_area_2_le,
            self.width_le,
            self.shoulder_le,
            self.clearway1_len_le,
            self.clearway2_len_le,
            self.stopway1_len_le,
            self.stopway2_len_le,
            self.takeoff_available_1_cb,
            self.takeoff_available_2_cb,
            self.landing_available_1_cb,
            self.landing_available_2_cb,
            self.arc_num_combo,
            self.arc_let_combo,
            self.type1_combo,
            self.type2_combo,
        ]

    def _set_combo_data(self, combo: QtWidgets.QComboBox, value: str) -> None:
        idx = combo.findData(value)
        combo.setCurrentIndex(idx if idx >= 0 else 0)

    def _set_combo_text(self, combo: QtWidgets.QComboBox, value: str) -> None:
        idx = combo.findText(value, QtCore.Qt.MatchFlag.MatchFixedString)
        combo.setCurrentIndex(idx if idx >= 0 else 0)

    def _bool_from_saved_value(self, value) -> bool:
        if isinstance(value, bool):
            return value
        if value is None:
            return True
        return str(value).strip().lower() not in {"0", "false", "no", "off"}
