# -*- coding: utf-8 -*-
"""Dynamic runway input widget used by the main dialog."""

from typing import Dict, Optional

from qgis.PyQt import QtCore, QtGui, QtWidgets  # type: ignore

from .dialog_constants import (
    CALC_PLACEHOLDER,
    NA_PLACEHOLDER,
    RUNWAY_SURFACE_MATERIALS,
    WIDGET_MISSING_MSG,
)


class NoWheelComboBox(QtWidgets.QComboBox):
    """Combo box that ignores mouse-wheel changes unless the popup is open."""

    def wheelEvent(self, event: QtGui.QWheelEvent) -> None:
        if self.view().isVisible():
            super().wheelEvent(event)
            return
        event.ignore()


class RunwayWidgetGroup(QtWidgets.QFrame):
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
        super().__init__(parent)

        self.index = index
        self.numeric_validator = QtGui.QDoubleValidator()
        self.numeric_validator.setNotation(QtGui.QDoubleValidator.Notation.StandardNotation)
        self.coord_validator = coord_validator
        self.distance_validator = QtGui.QDoubleValidator(0.0, 9999.9, 1, self)
        self.distance_validator.setNotation(QtGui.QDoubleValidator.Notation.StandardNotation)

        self.setObjectName(f"groupBox_runway_{self.index}")
        self.setProperty("runwayCard", True)
        self.setFrameShape(QtWidgets.QFrame.Shape.StyledPanel)
        self.setFrameShadow(QtWidgets.QFrame.Shadow.Plain)
        self.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Preferred,
            QtWidgets.QSizePolicy.Policy.Preferred,
        )
        self.setStyleSheet(
            """
            QFrame[runwayCard="true"] {
                border: 1px solid #dcdcdc;
                border-radius: 4px;
                background: #ffffff;
            }
            QLineEdit, QComboBox {
                min-height: 28px;
                max-height: 28px;
                padding-left: 6px;
                padding-right: 6px;
            }
            QLineEdit[requiredEmpty="true"] {
                background: #fffbe6;
                border: 1px solid #e0b000;
            }
            """
        )

        self._advanced_visible = False
        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        groupBox_layout = QtWidgets.QVBoxLayout(self)
        groupBox_layout.setContentsMargins(8, 8, 8, 8)
        groupBox_layout.setSpacing(6)

        header_widget = QtWidgets.QWidget(self)
        header_widget.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding,
            QtWidgets.QSizePolicy.Policy.Fixed,
        )
        header_layout = QtWidgets.QHBoxLayout(header_widget)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(6)
        header_layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignTop)

        title_stack = QtWidgets.QVBoxLayout()
        title_stack.setContentsMargins(0, 0, 0, 0)
        title_stack.setSpacing(0)

        self.rwy_name_lbl = QtWidgets.QLabel(CALC_PLACEHOLDER)
        self.rwy_name_lbl.setObjectName(f"label_rwy_name_{self.index}")
        self.rwy_name_lbl.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter)
        title_font = self.rwy_name_lbl.font()
        title_font.setBold(True)
        title_font.setPointSize(title_font.pointSize() + 1)
        self.rwy_name_lbl.setFont(title_font)
        title_stack.addWidget(self.rwy_name_lbl)

        self.header_summary_lbl = QtWidgets.QLabel("Length: -- | Azimuth: --")
        self.header_summary_lbl.setObjectName(f"label_rwy_summary_{self.index}")
        self.header_summary_lbl.setStyleSheet("color: #666666;")
        title_stack.addWidget(self.header_summary_lbl)

        self.required_legend_lbl = QtWidgets.QLabel("* required for Ready")
        self.required_legend_lbl.setObjectName(f"label_rwy_required_legend_{self.index}")
        self.required_legend_lbl.setStyleSheet("color: #777777; font-size: 11px;")
        title_stack.addWidget(self.required_legend_lbl)

        header_layout.addLayout(title_stack)

        header_layout.addStretch(1)

        self.status_chip_lbl = QtWidgets.QLabel("Incomplete")
        self.status_chip_lbl.setObjectName(f"label_rwy_status_{self.index}")
        self.status_chip_lbl.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.status_chip_lbl.setMinimumWidth(90)
        self.status_chip_lbl.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Fixed,
            QtWidgets.QSizePolicy.Policy.Fixed,
        )
        self.status_chip_lbl.setStyleSheet(
            "QLabel { background: #f2f2f2; color: #444; border: 1px solid #d2d2d2; border-radius: 10px; padding: 4px 10px; }"
        )
        header_layout.addWidget(self.status_chip_lbl)

        self.expand_button = QtWidgets.QToolButton()
        self.expand_button.setObjectName(f"toolButton_expand_runway_{self.index}")
        self.expand_button.setCheckable(True)
        self.expand_button.setChecked(False)
        self.expand_button.setArrowType(QtCore.Qt.ArrowType.RightArrow)
        self.expand_button.setToolTip("Show or hide advanced runway details")
        self.expand_button.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Fixed,
            QtWidgets.QSizePolicy.Policy.Fixed,
        )
        self.expand_button.toggled.connect(self._set_advanced_visible)
        header_layout.addWidget(self.expand_button)

        self.remove_button = QtWidgets.QPushButton("Remove")
        self.remove_button.setObjectName(f"pushButton_remove_runway_{self.index}")
        self.remove_button.setToolTip("Remove this runway")
        self.remove_button.setMaximumWidth(90)
        self.remove_button.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Fixed,
            QtWidgets.QSizePolicy.Policy.Fixed,
        )
        header_layout.addWidget(self.remove_button)

        groupBox_layout.addWidget(header_widget, 0, QtCore.Qt.AlignmentFlag.AlignTop)

        core_widget = QtWidgets.QWidget(self)
        core_layout = QtWidgets.QGridLayout(core_widget)
        core_layout.setContentsMargins(0, 0, 0, 0)
        core_layout.setHorizontalSpacing(10)
        core_layout.setVerticalSpacing(8)

        gridLayout_Coords = core_layout
        gridLayout_Coords.setObjectName(f"gridLayout_Coords_{self.index}")
        gridLayout_Coords.setColumnStretch(0, 2)
        gridLayout_Coords.setColumnStretch(1, 1)
        gridLayout_Coords.setColumnStretch(2, 1)

        label_designation_row = QtWidgets.QLabel("Designation:")
        label_designation_row.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter)
        label_easting_row = QtWidgets.QLabel("Easting:")
        label_easting_row.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter)
        label_northing_row = QtWidgets.QLabel("Northing:")
        label_northing_row.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter)
        label_runway_end_elevation_row = QtWidgets.QLabel("Runway End Elev. (m):")
        label_runway_end_elevation_row.setAlignment(
            QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter
        )
        label_threshold_elevation_row = QtWidgets.QLabel("Threshold Elev. (m):")
        label_threshold_elevation_row.setAlignment(
            QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter
        )
        label_displaced_row = QtWidgets.QLabel("Displaced (m):")
        label_displaced_row.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter)
        label_pre_threshold_area_row = QtWidgets.QLabel("Pre-threshold Area (m):")
        label_pre_threshold_area_row.setAlignment(
            QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter
        )
        self._required_field_pairs = []
        self._mark_required_label(label_designation_row)
        self._mark_required_label(label_easting_row)
        self._mark_required_label(label_northing_row)

        h_layout_desig_inputs = QtWidgets.QHBoxLayout()
        self.desig_le = QtWidgets.QLineEdit()
        self.desig_le.setObjectName(f"lineEdit_rwy_desig_{self.index}")
        self.desig_le.setMaxLength(2)
        self.desig_le.setToolTip("Enter 2-digit primary designation (01-36).")
        self.desig_le.setValidator(QtGui.QIntValidator(1, 36, self))
        self.desig_le.setMinimumWidth(96)
        self.suffix_combo = NoWheelComboBox()
        self.suffix_combo.setObjectName(f"comboBox_rwy_suffix_{self.index}")
        self.suffix_combo.addItems(["", "L", "C", "R"])
        self.suffix_combo.setToolTip("Runway suffix (Leave blank if none)")
        self.suffix_combo.setFocusPolicy(QtCore.Qt.FocusPolicy.StrongFocus)
        self.suffix_combo.setMinimumWidth(70)
        h_layout_desig_inputs.addWidget(self.desig_le)
        h_layout_desig_inputs.addWidget(self.suffix_combo)

        self.rec_desig_hdr_lbl = QtWidgets.QLabel(CALC_PLACEHOLDER)
        self.rec_desig_hdr_lbl.setObjectName(f"label_header_desig2_{self.index}")
        self.rec_desig_hdr_lbl.setToolTip("Calculated reciprocal designation")
        self.rec_desig_hdr_lbl.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)

        label_runway_width = QtWidgets.QLabel("Runway Width (m):")
        label_runway_width.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter)
        self._mark_required_label(label_runway_width)
        self.width_le = QtWidgets.QLineEdit()
        self.width_le.setObjectName(f"lineEdit_runway_width_{self.index}")
        self.width_le.setToolTip("Enter actual runway width (meters).")
        width_validator = QtGui.QDoubleValidator(0.01, 9999.99, 2, self)
        width_validator.setNotation(QtGui.QDoubleValidator.Notation.StandardNotation)
        self.width_le.setValidator(width_validator)
        self.width_le.setMinimumWidth(190)

        self.thr_east_le = QtWidgets.QLineEdit()
        self.thr_east_le.setObjectName(f"lineEdit_thr_easting_{self.index}")
        self.thr_east_le.setPlaceholderText("e.g., 456789.12")
        self.thr_east_le.setToolTip("Easting coordinate of primary threshold")
        self.thr_east_le.setValidator(self.coord_validator)
        self.thr_east_le.setMinimumWidth(190)

        self.thr_north_le = QtWidgets.QLineEdit()
        self.thr_north_le.setObjectName(f"lineEdit_thr_northing_{self.index}")
        self.thr_north_le.setPlaceholderText("e.g., 123456.78")
        self.thr_north_le.setToolTip("Northing coordinate of primary threshold")
        self.thr_north_le.setValidator(self.coord_validator)
        self.thr_north_le.setMinimumWidth(190)

        self.rec_east_le = QtWidgets.QLineEdit()
        self.rec_east_le.setObjectName(f"lineEdit_reciprocal_thr_easting_{self.index}")
        self.rec_east_le.setPlaceholderText("e.g., 457890.34")
        self.rec_east_le.setToolTip("Easting coordinate of reciprocal threshold")
        self.rec_east_le.setValidator(self.coord_validator)
        self.rec_east_le.setMinimumWidth(190)

        self.rec_north_le = QtWidgets.QLineEdit()
        self.rec_north_le.setObjectName(f"lineEdit_reciprocal_thr_northing_{self.index}")
        self.rec_north_le.setPlaceholderText("e.g., 124567.90")
        self.rec_north_le.setToolTip("Northing coordinate of reciprocal threshold")
        self.rec_north_le.setValidator(self.coord_validator)
        self.rec_north_le.setMinimumWidth(190)

        self.runway_end_elev_1_le = QtWidgets.QLineEdit()
        self.runway_end_elev_1_le.setObjectName(f"lineEdit_runway_end_elev_1_{self.index}")
        self.runway_end_elev_1_le.setPlaceholderText("e.g., 150.5")
        self.runway_end_elev_1_le.setToolTip("Elevation (AMSL) at the physical primary runway end. Used for RED.")
        self.runway_end_elev_1_le.setValidator(self.numeric_validator)
        self.runway_end_elev_1_le.setMinimumWidth(190)

        self.runway_end_elev_2_le = QtWidgets.QLineEdit()
        self.runway_end_elev_2_le.setObjectName(f"lineEdit_runway_end_elev_2_{self.index}")
        self.runway_end_elev_2_le.setPlaceholderText("e.g., 149.8")
        self.runway_end_elev_2_le.setToolTip("Elevation (AMSL) at the physical reciprocal runway end. Used for RED.")
        self.runway_end_elev_2_le.setValidator(self.numeric_validator)
        self.runway_end_elev_2_le.setMinimumWidth(190)

        self.threshold_elev_1_le = QtWidgets.QLineEdit()
        self.threshold_elev_1_le.setObjectName(f"lineEdit_threshold_elev_1_{self.index}")
        self.threshold_elev_1_le.setPlaceholderText("blank = runway end elev.")
        self.threshold_elev_1_le.setToolTip(
            "Elevation (AMSL) of the primary landing threshold. Leave blank to use the runway-end elevation."
        )
        self.threshold_elev_1_le.setValidator(self.numeric_validator)
        self.threshold_elev_1_le.setMinimumWidth(190)

        self.threshold_elev_2_le = QtWidgets.QLineEdit()
        self.threshold_elev_2_le.setObjectName(f"lineEdit_threshold_elev_2_{self.index}")
        self.threshold_elev_2_le.setPlaceholderText("blank = runway end elev.")
        self.threshold_elev_2_le.setToolTip(
            "Elevation (AMSL) of the reciprocal landing threshold. Leave blank to use the runway-end elevation."
        )
        self.threshold_elev_2_le.setValidator(self.numeric_validator)
        self.threshold_elev_2_le.setMinimumWidth(190)

        self.thr_displaced_1_le = QtWidgets.QLineEdit()
        self.thr_displaced_1_le.setObjectName(f"lineEdit_thr_displaced_1_{self.index}")
        self.thr_displaced_1_le.setPlaceholderText("e.g., 300")
        self.thr_displaced_1_le.setToolTip(
            "Displaced threshold distance for primary end (meters). Leave blank if none."
        )
        self.thr_displaced_1_le.setValidator(self.distance_validator)
        self.thr_displaced_1_le.setMinimumWidth(190)

        self.thr_displaced_2_le = QtWidgets.QLineEdit()
        self.thr_displaced_2_le.setObjectName(f"lineEdit_thr_displaced_2_{self.index}")
        self.thr_displaced_2_le.setPlaceholderText("e.g., 0")
        self.thr_displaced_2_le.setToolTip(
            "Displaced threshold distance for reciprocal end (meters). Leave blank if none."
        )
        self.thr_displaced_2_le.setValidator(self.distance_validator)
        self.thr_displaced_2_le.setMinimumWidth(190)

        self.thr_pre_area_1_le = QtWidgets.QLineEdit()
        self.thr_pre_area_1_le.setObjectName(f"lineEdit_thr_pre_area_1_{self.index}")
        self.thr_pre_area_1_le.setPlaceholderText("e.g., 60")
        self.thr_pre_area_1_le.setToolTip("Length of pre-threshold area for primary end (meters). Leave blank if none.")
        self.thr_pre_area_1_le.setValidator(self.distance_validator)
        self.thr_pre_area_1_le.setMinimumWidth(190)

        self.thr_pre_area_2_le = QtWidgets.QLineEdit()
        self.thr_pre_area_2_le.setObjectName(f"lineEdit_thr_pre_area_2_{self.index}")
        self.thr_pre_area_2_le.setPlaceholderText("e.g., 60")
        self.thr_pre_area_2_le.setToolTip(
            "Length of pre-threshold area for reciprocal end (meters). Leave blank if none."
        )
        self.thr_pre_area_2_le.setValidator(self.distance_validator)
        self.thr_pre_area_2_le.setMinimumWidth(190)

        current_coord_row = 0
        gridLayout_Coords.addWidget(label_designation_row, current_coord_row, 0)
        gridLayout_Coords.addLayout(h_layout_desig_inputs, current_coord_row, 1)
        gridLayout_Coords.addWidget(self.rec_desig_hdr_lbl, current_coord_row, 2)
        current_coord_row += 1
        gridLayout_Coords.addWidget(label_runway_width, current_coord_row, 0)
        gridLayout_Coords.addWidget(self.width_le, current_coord_row, 1, 1, 2)
        current_coord_row += 1
        gridLayout_Coords.addWidget(label_easting_row, current_coord_row, 0)
        gridLayout_Coords.addWidget(self.thr_east_le, current_coord_row, 1)
        gridLayout_Coords.addWidget(self.rec_east_le, current_coord_row, 2)
        current_coord_row += 1
        gridLayout_Coords.addWidget(label_northing_row, current_coord_row, 0)
        gridLayout_Coords.addWidget(self.thr_north_le, current_coord_row, 1)
        gridLayout_Coords.addWidget(self.rec_north_le, current_coord_row, 2)

        core_widget.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding,
            QtWidgets.QSizePolicy.Policy.Fixed,
        )
        groupBox_layout.addWidget(core_widget, 0, QtCore.Qt.AlignmentFlag.AlignTop)

        self.advanced_widget = QtWidgets.QWidget(self)
        advanced_layout = QtWidgets.QVBoxLayout(self.advanced_widget)
        advanced_layout.setContentsMargins(0, 0, 0, 0)
        advanced_layout.setSpacing(8)
        self.advanced_widget.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding,
            QtWidgets.QSizePolicy.Policy.Fixed,
        )

        advanced_body = QtWidgets.QWidget(self.advanced_widget)
        advanced_body_layout = QtWidgets.QVBoxLayout(advanced_body)
        advanced_body_layout.setContentsMargins(0, 0, 0, 0)
        advanced_body_layout.setSpacing(8)

        threshold_group = QtWidgets.QGroupBox("Threshold / Elevation Details")
        threshold_group.setObjectName(f"groupBox_threshold_details_{self.index}")
        threshold_layout = QtWidgets.QGridLayout(threshold_group)
        threshold_layout.setColumnStretch(0, 2)
        threshold_layout.setColumnStretch(1, 1)
        threshold_layout.setColumnStretch(2, 1)

        threshold_layout.addWidget(label_runway_end_elevation_row, 0, 0)
        threshold_layout.addWidget(self.runway_end_elev_1_le, 0, 1)
        threshold_layout.addWidget(self.runway_end_elev_2_le, 0, 2)
        threshold_layout.addWidget(label_threshold_elevation_row, 1, 0)
        threshold_layout.addWidget(self.threshold_elev_1_le, 1, 1)
        threshold_layout.addWidget(self.threshold_elev_2_le, 1, 2)
        threshold_layout.addWidget(label_displaced_row, 2, 0)
        threshold_layout.addWidget(self.thr_displaced_1_le, 2, 1)
        threshold_layout.addWidget(self.thr_displaced_2_le, 2, 2)
        threshold_layout.addWidget(label_pre_threshold_area_row, 3, 0)
        threshold_layout.addWidget(self.thr_pre_area_1_le, 3, 1)
        threshold_layout.addWidget(self.thr_pre_area_2_le, 3, 2)

        advanced_body_layout.addWidget(threshold_group)

        self.dist_lbl = QtWidgets.QLabel(CALC_PLACEHOLDER)
        self.dist_lbl.setObjectName(f"label_rwy_distance_{self.index}")
        self.dist_lbl.hide()

        self.azim_lbl = QtWidgets.QLabel(CALC_PLACEHOLDER)
        self.azim_lbl.setObjectName(f"label_rwy_azimuth_{self.index}")
        self.azim_lbl.hide()

        dimensions_group = QtWidgets.QGroupBox("Dimensions")
        dimensions_group.setObjectName(f"groupBox_dimensions_{self.index}")
        dimensions_layout = QtWidgets.QGridLayout(dimensions_group)
        dimensions_layout.setColumnStretch(0, 2)
        dimensions_layout.setColumnStretch(1, 1)

        label_runway_shoulder = QtWidgets.QLabel("Runway Shoulder (m):")
        label_runway_shoulder.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter)
        self.shoulder_le = QtWidgets.QLineEdit()
        self.shoulder_le.setObjectName(f"lineEdit_rwy_shoulder_{self.index}")
        self.shoulder_le.setToolTip("Enter width of runway shoulder (each side, if applicable).")
        self.shoulder_le.setValidator(self.distance_validator)
        self.shoulder_le.setMinimumWidth(190)
        dimensions_layout.addWidget(label_runway_shoulder, 0, 0)
        dimensions_layout.addWidget(self.shoulder_le, 0, 1)

        advanced_body_layout.addWidget(dimensions_group)
        self._add_declared_distance_controls(advanced_body_layout)

        classification_group = QtWidgets.QGroupBox("Classification / Approach")
        classification_group.setObjectName(f"groupBox_classification_{self.index}")
        classification_layout = QtWidgets.QGridLayout(classification_group)
        classification_layout.setColumnStretch(0, 2)
        classification_layout.setColumnStretch(1, 1)
        self._add_arc_controls(classification_layout, 0)
        self._add_runway_type_controls(classification_layout, 4)

        advanced_body_layout.addWidget(classification_group)
        advanced_layout.addWidget(advanced_body)
        groupBox_layout.addWidget(self.advanced_widget, 0, QtCore.Qt.AlignmentFlag.AlignTop)

        self._required_field_pairs = [
            (label_designation_row, self.desig_le),
            (label_easting_row, self.thr_east_le),
            (label_northing_row, self.thr_north_le),
            (label_easting_row, self.rec_east_le),
            (label_northing_row, self.rec_north_le),
            (label_runway_width, self.width_le),
        ]
        self._set_advanced_visible(False)
        self._sync_height_constraint()
        self._update_status_chip()
        self._update_required_field_indicators()

    def _add_arc_controls(self, layout: QtWidgets.QGridLayout, row: int) -> None:
        label_arc_num = QtWidgets.QLabel("ARC Number:")
        label_arc_num.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter)
        self.arc_num_combo = NoWheelComboBox()
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
        self.arc_num_combo.setMinimumWidth(190)
        layout.addWidget(label_arc_num, row, 0)
        layout.addWidget(self.arc_num_combo, row, 1)

        label_arc_let = QtWidgets.QLabel("ARC Letter:")
        label_arc_let.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter)
        self.arc_let_combo = NoWheelComboBox()
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
        self.arc_let_combo.setMinimumWidth(190)
        layout.addWidget(label_arc_let, row + 1, 0)
        layout.addWidget(self.arc_let_combo, row + 1, 1)

        label_surface_category = QtWidgets.QLabel("Surface Category:")
        label_surface_category.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter)
        self.surface_category_combo = NoWheelComboBox()
        self.surface_category_combo.setObjectName(f"comboBox_surface_category_{self.index}")
        self.surface_category_combo.addItems([""] + list(RUNWAY_SURFACE_MATERIALS))
        self.surface_category_combo.setToolTip("Select runway surface category.")
        self.surface_category_combo.setFocusPolicy(QtCore.Qt.FocusPolicy.StrongFocus)
        self.surface_category_combo.setMinimumWidth(190)
        layout.addWidget(label_surface_category, row + 2, 0)
        layout.addWidget(self.surface_category_combo, row + 2, 1)

        label_surface_material = QtWidgets.QLabel("Surface Material:")
        label_surface_material.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter)
        self.surface_material_combo = NoWheelComboBox()
        self.surface_material_combo.setObjectName(f"comboBox_surface_material_{self.index}")
        self.surface_material_combo.setToolTip("Select runway surface material for the chosen category.")
        self.surface_material_combo.setFocusPolicy(QtCore.Qt.FocusPolicy.StrongFocus)
        self.surface_material_combo.setMinimumWidth(190)
        self._refresh_surface_material_options("")
        layout.addWidget(label_surface_material, row + 3, 0)
        layout.addWidget(self.surface_material_combo, row + 3, 1)

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
        self.type1_lbl.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter)
        self.type1_combo = NoWheelComboBox()
        self.type1_combo.setObjectName(f"comboBox_type_desig1_{self.index}")
        self.type1_combo.addItems(runway_types)
        self.type1_combo.setToolTip("Select type for primary end.")
        self.type1_combo.setFocusPolicy(QtCore.Qt.FocusPolicy.StrongFocus)
        self.type1_combo.setMinimumWidth(190)
        layout.addWidget(self.type1_lbl, row, 0)
        layout.addWidget(self.type1_combo, row, 1)

        self.type2_lbl = QtWidgets.QLabel("(Reciprocal End) Type:")
        self.type2_lbl.setObjectName(f"label_type_desig2_{self.index}")
        self.type2_lbl.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter)
        self.type2_combo = NoWheelComboBox()
        self.type2_combo.setObjectName(f"comboBox_type_desig2_{self.index}")
        self.type2_combo.addItems(runway_types)
        self.type2_combo.setToolTip("Select type for reciprocal end.")
        self.type2_combo.setFocusPolicy(QtCore.Qt.FocusPolicy.StrongFocus)
        self.type2_combo.setMinimumWidth(190)
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
        self.clearway1_len_le.setToolTip("Clearway length beyond the primary physical runway end.")
        self.clearway1_len_le.setValidator(self.distance_validator)

        self.clearway2_len_le = QtWidgets.QLineEdit()
        self.clearway2_len_le.setObjectName(f"lineEdit_clearway2_len_{self.index}")
        self.clearway2_len_le.setPlaceholderText("0")
        self.clearway2_len_le.setToolTip("Clearway length beyond the reciprocal physical runway end.")
        self.clearway2_len_le.setValidator(self.distance_validator)
        declared_layout.addWidget(clearway_label, 1, 0)
        declared_layout.addWidget(self.clearway1_len_le, 1, 1)
        declared_layout.addWidget(self.clearway2_len_le, 1, 2)

        stopway_label = QtWidgets.QLabel("Stopway (m):")
        self.stopway1_len_le = QtWidgets.QLineEdit()
        self.stopway1_len_le.setObjectName(f"lineEdit_stopway1_len_{self.index}")
        self.stopway1_len_le.setPlaceholderText("0")
        self.stopway1_len_le.setToolTip("Stopway length beyond the primary physical runway end.")
        self.stopway1_len_le.setValidator(self.distance_validator)

        self.stopway2_len_le = QtWidgets.QLineEdit()
        self.stopway2_len_le.setObjectName(f"lineEdit_stopway2_len_{self.index}")
        self.stopway2_len_le.setPlaceholderText("0")
        self.stopway2_len_le.setToolTip("Stopway length beyond the reciprocal physical runway end.")
        self.stopway2_len_le.setValidator(self.distance_validator)
        declared_layout.addWidget(stopway_label, 2, 0)
        declared_layout.addWidget(self.stopway1_len_le, 2, 1)
        declared_layout.addWidget(self.stopway2_len_le, 2, 2)

        takeoff_label = QtWidgets.QLabel("Takeoff available:")
        self.takeoff_available_1_cb = QtWidgets.QCheckBox()
        self.takeoff_available_1_cb.setObjectName(f"checkBox_takeoff_available_1_{self.index}")
        self.takeoff_available_1_cb.setChecked(True)
        self.takeoff_available_1_cb.setToolTip("Takeoff is available in the primary runway direction.")

        self.takeoff_available_2_cb = QtWidgets.QCheckBox()
        self.takeoff_available_2_cb.setObjectName(f"checkBox_takeoff_available_2_{self.index}")
        self.takeoff_available_2_cb.setChecked(True)
        self.takeoff_available_2_cb.setToolTip("Takeoff is available in the reciprocal runway direction.")
        declared_layout.addWidget(takeoff_label, 3, 0)
        declared_layout.addWidget(self.takeoff_available_1_cb, 3, 1)
        declared_layout.addWidget(self.takeoff_available_2_cb, 3, 2)

        landing_label = QtWidgets.QLabel("Landing available:")
        self.landing_available_1_cb = QtWidgets.QCheckBox()
        self.landing_available_1_cb.setObjectName(f"checkBox_landing_available_1_{self.index}")
        self.landing_available_1_cb.setChecked(True)
        self.landing_available_1_cb.setToolTip("Landing is available toward the primary runway threshold.")

        self.landing_available_2_cb = QtWidgets.QCheckBox()
        self.landing_available_2_cb.setObjectName(f"checkBox_landing_available_2_{self.index}")
        self.landing_available_2_cb.setChecked(True)
        self.landing_available_2_cb.setToolTip("Landing is available toward the reciprocal runway threshold.")
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
            self.runway_end_elev_1_le,
            self.runway_end_elev_2_le,
            self.threshold_elev_1_le,
            self.threshold_elev_2_le,
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
            if widget in [
                self.desig_le,
                self.thr_east_le,
                self.thr_north_le,
                self.rec_east_le,
                self.rec_north_le,
                self.width_le,
            ]:
                widget.textChanged.connect(self._update_required_field_indicators)
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
            self.surface_material_combo,
            self.type1_combo,
            self.type2_combo,
        ]:
            combo.currentIndexChanged.connect(self.inputChanged.emit)
        self.suffix_combo.currentIndexChanged.connect(self._update_required_field_indicators)
        self.surface_category_combo.currentIndexChanged.connect(self._handle_surface_category_changed)
        self.remove_button.clicked.connect(self._emit_remove_request)
        self.expand_button.toggled.connect(self._update_expand_button_icon)

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
            "runway_end_elev_1": self.runway_end_elev_1_le.text(),
            "runway_end_elev_2": self.runway_end_elev_2_le.text(),
            "threshold_elev_1": self.threshold_elev_1_le.text(),
            "threshold_elev_2": self.threshold_elev_2_le.text(),
            "thr_elev_1": self.threshold_elev_1_le.text() or self.runway_end_elev_1_le.text(),
            "thr_elev_2": self.threshold_elev_2_le.text() or self.runway_end_elev_2_le.text(),
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
            "surface_category": self.surface_category_combo.currentText(),
            "surface_material": self.surface_material_combo.currentText(),
            "type1": self.type1_combo.currentText(),
            "type2": self.type2_combo.currentText(),
        }

    def set_input_data(self, data: Dict[str, str]):
        widgets_to_block = self._input_widgets()
        for widget in widgets_to_block:
            widget.blockSignals(True)
        try:
            self.desig_le.setText(data.get("designator_str", ""))
            suffix_idx = self.suffix_combo.findText(data.get("suffix", ""), QtCore.Qt.MatchFlag.MatchFixedString)
            self.suffix_combo.setCurrentIndex(suffix_idx if suffix_idx >= 0 else 0)
            self.thr_east_le.setText(data.get("thr_easting", ""))
            self.thr_north_le.setText(data.get("thr_northing", ""))
            self.rec_east_le.setText(data.get("rec_easting", ""))
            self.rec_north_le.setText(data.get("rec_northing", ""))
            self.runway_end_elev_1_le.setText(data.get("runway_end_elev_1", "") or data.get("thr_elev_1", ""))
            self.runway_end_elev_2_le.setText(data.get("runway_end_elev_2", "") or data.get("thr_elev_2", ""))
            self.threshold_elev_1_le.setText(data.get("threshold_elev_1", ""))
            self.threshold_elev_2_le.setText(data.get("threshold_elev_2", ""))
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
            self.takeoff_available_1_cb.setChecked(self._bool_from_saved_value(data.get("takeoff_available_1", True)))
            self.takeoff_available_2_cb.setChecked(self._bool_from_saved_value(data.get("takeoff_available_2", True)))
            self.landing_available_1_cb.setChecked(self._bool_from_saved_value(data.get("landing_available_1", True)))
            self.landing_available_2_cb.setChecked(self._bool_from_saved_value(data.get("landing_available_2", True)))
            self._set_combo_data(self.arc_num_combo, data.get("arc_num", ""))
            self._set_combo_data(self.arc_let_combo, data.get("arc_let", ""))
            self._set_combo_text(
                self.surface_category_combo,
                data.get("surface_category", ""),
            )
            self._refresh_surface_material_options(
                self.surface_category_combo.currentText(),
                selected_material=data.get("surface_material", ""),
            )
            self._set_combo_text(self.type1_combo, data.get("type1", ""))
            self._set_combo_text(self.type2_combo, data.get("type2", ""))
        finally:
            for widget in widgets_to_block:
                widget.blockSignals(False)
            self.inputChanged.emit()

    def update_display_labels(self, results: Dict[str, str]):
        self.rec_desig_hdr_lbl.setText(results.get("reciprocal_desig_full", NA_PLACEHOLDER))
        self.rwy_name_lbl.setText(results.get("runway_name", WIDGET_MISSING_MSG))
        self.dist_lbl.setText(results.get("distance", WIDGET_MISSING_MSG))
        self.azim_lbl.setText(results.get("azimuth", WIDGET_MISSING_MSG))
        self.type1_lbl.setText(results.get("type1_label_text", "(Primary End) Type:"))
        self.type2_lbl.setText(results.get("type2_label_text", "(Reciprocal End) Type:"))
        self.header_summary_lbl.setText(
            f"Length: {self.dist_lbl.text()} | Azimuth: {self.azim_lbl.text()}"
        )
        self._update_status_chip()
        self._update_required_field_indicators()
        self._sync_height_constraint()

    def _input_widgets(self):
        return [
            self.desig_le,
            self.suffix_combo,
            self.thr_east_le,
            self.thr_north_le,
            self.rec_east_le,
            self.rec_north_le,
            self.runway_end_elev_1_le,
            self.runway_end_elev_2_le,
            self.threshold_elev_1_le,
            self.threshold_elev_2_le,
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
            self.surface_category_combo,
            self.surface_material_combo,
            self.type1_combo,
            self.type2_combo,
        ]

    def _handle_surface_category_changed(self):
        self._refresh_surface_material_options(self.surface_category_combo.currentText())
        self.inputChanged.emit()

    def _set_advanced_visible(self, visible: bool) -> None:
        self._advanced_visible = visible
        if hasattr(self, "advanced_widget"):
            self.advanced_widget.setVisible(visible)
            self.advanced_widget.setMaximumHeight(16777215 if visible else 0)
            self.advanced_widget.setMinimumHeight(0)
        self._sync_height_constraint()
        self._update_expand_button_icon(visible)

    def _update_expand_button_icon(self, visible: Optional[bool] = None) -> None:
        if visible is None:
            visible = self._advanced_visible
        arrow = QtCore.Qt.ArrowType.DownArrow if visible else QtCore.Qt.ArrowType.RightArrow
        if hasattr(self, "expand_button") and self.expand_button.isChecked() != visible:
            self.expand_button.blockSignals(True)
            self.expand_button.setChecked(visible)
            self.expand_button.blockSignals(False)
        if hasattr(self, "expand_button"):
            self.expand_button.setArrowType(arrow)

    def _update_status_chip(self) -> None:
        if not hasattr(self, "status_chip_lbl"):
            return
        data = self.get_input_data()
        required_values = [
            data.get("designator_str", ""),
            data.get("thr_easting", ""),
            data.get("thr_northing", ""),
            data.get("rec_easting", ""),
            data.get("rec_northing", ""),
            data.get("width", ""),
        ]
        if not all(str(value).strip() for value in required_values):
            status = "Incomplete"
        elif any(text in {CALC_PLACEHOLDER, WIDGET_MISSING_MSG, NA_PLACEHOLDER} for text in [
            self.rwy_name_lbl.text(),
            self.dist_lbl.text(),
            self.azim_lbl.text(),
        ]):
            status = "Needs attention"
        else:
            status = "Ready"
        self.status_chip_lbl.setText(status)
        if status == "Ready":
            self.status_chip_lbl.setStyleSheet(
                "QLabel { background: #eaf6ed; color: #1f6b32; border: 1px solid #c7e7cf; border-radius: 10px; padding: 4px 10px; }"
            )
        elif status == "Needs attention":
            self.status_chip_lbl.setStyleSheet(
                "QLabel { background: #fff5e6; color: #9a5b00; border: 1px solid #f0d6a8; border-radius: 10px; padding: 4px 10px; }"
            )
        else:
            self.status_chip_lbl.setStyleSheet(
                "QLabel { background: #f2f2f2; color: #444; border: 1px solid #d2d2d2; border-radius: 10px; padding: 4px 10px; }"
            )

    def _mark_required_label(self, label: QtWidgets.QLabel) -> None:
        """Annotate a label so required runway fields are visually obvious."""
        base_text = label.text()
        if "*" not in base_text:
            label.setText(f"{base_text} *")
        label.setToolTip("Required for Ready status")
        label.setStyleSheet("font-weight: 600;")

    def _update_required_field_indicators(self) -> None:
        """Highlight the fields that must be completed for a runway to be ready."""
        required_texts = {
            "desig_le": self.desig_le.text().strip(),
            "thr_east_le": self.thr_east_le.text().strip(),
            "thr_north_le": self.thr_north_le.text().strip(),
            "rec_east_le": self.rec_east_le.text().strip(),
            "rec_north_le": self.rec_north_le.text().strip(),
            "width_le": self.width_le.text().strip(),
        }
        for widget_name, value in required_texts.items():
            widget = getattr(self, widget_name, None)
            if not widget:
                continue
            widget.setProperty("requiredEmpty", not bool(value))
            widget.style().unpolish(widget)
            widget.style().polish(widget)
            widget.update()

    def _sync_height_constraint(self) -> None:
        """Clamp the card height in compact mode so it does not float with extra whitespace."""
        if self._advanced_visible:
            self.setMaximumHeight(16777215)
            self.setMinimumHeight(0)
        else:
            self.adjustSize()
            compact_height = self.sizeHint().height()
            self.setMinimumHeight(compact_height)
            self.setMaximumHeight(compact_height)

    def _refresh_surface_material_options(self, category: str, selected_material: str = "") -> None:
        current_material = selected_material or self.surface_material_combo.currentText()
        self.surface_material_combo.blockSignals(True)
        try:
            self.surface_material_combo.clear()
            materials = RUNWAY_SURFACE_MATERIALS.get(category, [])
            self.surface_material_combo.addItem("")
            self.surface_material_combo.addItems(materials)
            if current_material in materials:
                self.surface_material_combo.setCurrentText(current_material)
            else:
                self.surface_material_combo.setCurrentIndex(0)
            self.surface_material_combo.setEnabled(bool(materials))
        finally:
            self.surface_material_combo.blockSignals(False)

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
