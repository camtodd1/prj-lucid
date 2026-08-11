# -*- coding: utf-8 -*-
"""Dynamic runway input widget used by the main dialog."""

from typing import Any, Dict, Optional

from qgis.PyQt import QtCore, QtGui, QtWidgets  # type: ignore

try:
    from ..rulesets.annex14.metadata import MODERNISED_DISPLAY_NAME
except ImportError:
    from rulesets.annex14.metadata import MODERNISED_DISPLAY_NAME  # type: ignore

from .dialog_constants import (
    CALC_PLACEHOLDER,
    NA_PLACEHOLDER,
    RUNWAY_SURFACE_MATERIALS,
    WIDGET_MISSING_MSG,
)


RUNWAY_FORM_LABEL_MIN_WIDTH = 190
RUNWAY_FORM_FIELD_MIN_WIDTH = 180
RUNWAY_FORM_COLUMN_GAP = 12
RUNWAY_FORM_ROW_HEIGHT = 28
RUNWAY_FORM_VERTICAL_GAP = 6


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
            QtWidgets.QSizePolicy.Policy.Maximum,
        )
        self.setStyleSheet(
            """
            QFrame[runwayCard="true"] {
                border: 1px solid #dcdcdc;
                border-radius: 4px;
                background: #ffffff;
            }
            QLineEdit {
                min-height: 28px;
                max-height: 28px;
            }
            QLineEdit, QComboBox {
                padding-left: 6px;
                padding-right: 6px;
                background: #ffffff;
            }
            QComboBox QAbstractItemView {
                background: #ffffff;
                color: #202124;
                selection-background-color: #e8f0fe;
                selection-color: #202124;
            }
            """
        )

        self._advanced_visible = False
        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        groupBox_layout = QtWidgets.QVBoxLayout(self)
        groupBox_layout.setContentsMargins(10, 10, 10, 10)
        groupBox_layout.setSpacing(8)

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

        self.header_summary_lbl = QtWidgets.QLabel("ARC: -- | ADG: -- | Length: -- | Azimuth: --")
        self.header_summary_lbl.setObjectName(f"label_rwy_summary_{self.index}")
        self.header_summary_lbl.setStyleSheet("color: #666666;")
        title_stack.addWidget(self.header_summary_lbl)

        header_layout.addLayout(title_stack)

        header_layout.addStretch(1)

        self.status_chip_lbl = QtWidgets.QLabel("Incomplete")
        self.status_chip_lbl.setObjectName(f"label_rwy_status_{self.index}")
        self.status_chip_lbl.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.status_chip_lbl.setMaximumHeight(24)
        self.status_chip_lbl.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Fixed,
            QtWidgets.QSizePolicy.Policy.Fixed,
        )
        self.status_chip_lbl.setStyleSheet(
            "QLabel { background: #f4f4f4; color: #555; border: 1px solid #d6d6d6; "
            "border-radius: 9px; padding: 3px 9px; font-size: 10px; font-weight: 600; }"
        )
        status_width = max(
            self.status_chip_lbl.fontMetrics().horizontalAdvance(text)
            for text in ["Incomplete", "Needs attention", "Ready"]
        )
        self.status_chip_lbl.setFixedWidth(status_width + 24)
        header_layout.addWidget(self.status_chip_lbl)

        self.expand_button = QtWidgets.QToolButton()
        self.expand_button.setObjectName(f"toolButton_expand_runway_{self.index}")
        self.expand_button.setCheckable(True)
        self.expand_button.setChecked(False)
        self.expand_button.setArrowType(QtCore.Qt.ArrowType.RightArrow)
        self.expand_button.setToolTip("Show advanced runway details")
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
        core_layout.setHorizontalSpacing(RUNWAY_FORM_COLUMN_GAP)
        core_layout.setVerticalSpacing(RUNWAY_FORM_VERTICAL_GAP)

        gridLayout_Coords = core_layout
        gridLayout_Coords.setObjectName(f"gridLayout_Coords_{self.index}")
        self._configure_runway_form_grid(gridLayout_Coords)

        label_designation_row = QtWidgets.QLabel("Designation:")
        label_designation_row.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter)
        label_easting_row = QtWidgets.QLabel("Easting:")
        label_easting_row.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter)
        label_northing_row = QtWidgets.QLabel("Northing:")
        label_northing_row.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter)
        label_runway_end_elevation_row = QtWidgets.QLabel("Runway End Elevation (m):")
        label_runway_end_elevation_row.setAlignment(
            QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter
        )
        label_threshold_elevation_row = QtWidgets.QLabel("Threshold Elevation (m):")
        label_threshold_elevation_row.setAlignment(
            QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter
        )
        label_displaced_row = QtWidgets.QLabel("Displacement Distance (m):")
        label_displaced_row.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter)
        h_layout_desig_inputs = QtWidgets.QHBoxLayout()
        h_layout_desig_inputs.setContentsMargins(0, 0, 0, 0)
        h_layout_desig_inputs.setSpacing(6)
        self.desig_le = QtWidgets.QLineEdit()
        self.desig_le.setObjectName(f"lineEdit_rwy_desig_{self.index}")
        self.desig_le.setMaxLength(2)
        self.desig_le.setToolTip("Enter 2-digit primary designation (01-36).")
        self.desig_le.setValidator(QtGui.QIntValidator(1, 36, self))
        self.desig_le.setMinimumWidth(60)
        self.desig_le.setMaximumWidth(16777215)
        self.desig_le.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding,
            QtWidgets.QSizePolicy.Policy.Fixed,
        )
        self.suffix_combo = NoWheelComboBox()
        self.suffix_combo.setObjectName(f"comboBox_rwy_suffix_{self.index}")
        self.suffix_combo.addItems(["", "L", "C", "R"])
        self.suffix_combo.setToolTip("Runway suffix (Leave blank if none)")
        self.suffix_combo.setFocusPolicy(QtCore.Qt.FocusPolicy.StrongFocus)
        self.suffix_combo.setMinimumWidth(60)
        self.suffix_combo.setMaximumWidth(80)
        h_layout_desig_inputs.addWidget(self.desig_le)
        h_layout_desig_inputs.addWidget(self.suffix_combo)

        self.rec_desig_hdr_lbl = QtWidgets.QLabel(CALC_PLACEHOLDER)
        self.rec_desig_hdr_lbl.setObjectName(f"label_header_desig2_{self.index}")
        self.rec_desig_hdr_lbl.setToolTip("Calculated reciprocal designation")
        self.rec_desig_hdr_lbl.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.rec_desig_hdr_lbl.setMinimumHeight(28)
        self.rec_desig_hdr_lbl.setStyleSheet(
            "QLabel { color: #555555; border: 1px solid #cfcfcf; border-radius: 4px; padding: 4px 8px; }"
        )
        self._set_control_width(self.rec_desig_hdr_lbl)

        label_runway_width = QtWidgets.QLabel("Runway Width (m):")
        label_runway_width.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter)
        self.width_le = QtWidgets.QLineEdit()
        self.width_le.setObjectName(f"lineEdit_runway_width_{self.index}")
        self.width_le.setToolTip("Enter actual runway width (meters).")
        width_validator = QtGui.QDoubleValidator(0.01, 9999.99, 2, self)
        width_validator.setNotation(QtGui.QDoubleValidator.Notation.StandardNotation)
        self.width_le.setValidator(width_validator)
        self._set_control_width(self.width_le)

        self.thr_east_le = QtWidgets.QLineEdit()
        self.thr_east_le.setObjectName(f"lineEdit_thr_easting_{self.index}")
        self.thr_east_le.setPlaceholderText("e.g., 456789.12")
        self.thr_east_le.setToolTip("Easting coordinate of primary threshold")
        self.thr_east_le.setValidator(self.coord_validator)
        self._set_control_width(self.thr_east_le)

        self.thr_north_le = QtWidgets.QLineEdit()
        self.thr_north_le.setObjectName(f"lineEdit_thr_northing_{self.index}")
        self.thr_north_le.setPlaceholderText("e.g., 123456.78")
        self.thr_north_le.setToolTip("Northing coordinate of primary threshold")
        self.thr_north_le.setValidator(self.coord_validator)
        self._set_control_width(self.thr_north_le)

        self.rec_east_le = QtWidgets.QLineEdit()
        self.rec_east_le.setObjectName(f"lineEdit_reciprocal_thr_easting_{self.index}")
        self.rec_east_le.setPlaceholderText("e.g., 457890.34")
        self.rec_east_le.setToolTip("Easting coordinate of reciprocal threshold")
        self.rec_east_le.setValidator(self.coord_validator)
        self._set_control_width(self.rec_east_le)

        self.rec_north_le = QtWidgets.QLineEdit()
        self.rec_north_le.setObjectName(f"lineEdit_reciprocal_thr_northing_{self.index}")
        self.rec_north_le.setPlaceholderText("e.g., 124567.90")
        self.rec_north_le.setToolTip("Northing coordinate of reciprocal threshold")
        self.rec_north_le.setValidator(self.coord_validator)
        self._set_control_width(self.rec_north_le)

        self.runway_end_elev_1_le = QtWidgets.QLineEdit()
        self.runway_end_elev_1_le.setObjectName(f"lineEdit_runway_end_elev_1_{self.index}")
        self.runway_end_elev_1_le.setPlaceholderText("e.g., 150.5")
        self.runway_end_elev_1_le.setToolTip("Elevation (AMSL) at the physical primary runway end. Used for RED.")
        self.runway_end_elev_1_le.setValidator(self.numeric_validator)
        self._set_control_width(self.runway_end_elev_1_le)

        self.runway_end_elev_2_le = QtWidgets.QLineEdit()
        self.runway_end_elev_2_le.setObjectName(f"lineEdit_runway_end_elev_2_{self.index}")
        self.runway_end_elev_2_le.setPlaceholderText("e.g., 149.8")
        self.runway_end_elev_2_le.setToolTip("Elevation (AMSL) at the physical reciprocal runway end. Used for RED.")
        self.runway_end_elev_2_le.setValidator(self.numeric_validator)
        self._set_control_width(self.runway_end_elev_2_le)

        self.threshold_elev_1_le = QtWidgets.QLineEdit()
        self.threshold_elev_1_le.setObjectName(f"lineEdit_threshold_elev_1_{self.index}")
        self.threshold_elev_1_le.setPlaceholderText("Required")
        self.threshold_elev_1_le.setToolTip(
            "Required elevation (AMSL) of the primary landing threshold."
        )
        self.threshold_elev_1_le.setValidator(self.numeric_validator)
        self._set_control_width(self.threshold_elev_1_le)

        self.threshold_elev_2_le = QtWidgets.QLineEdit()
        self.threshold_elev_2_le.setObjectName(f"lineEdit_threshold_elev_2_{self.index}")
        self.threshold_elev_2_le.setPlaceholderText("Required")
        self.threshold_elev_2_le.setToolTip(
            "Required elevation (AMSL) of the reciprocal landing threshold."
        )
        self.threshold_elev_2_le.setValidator(self.numeric_validator)
        self._set_control_width(self.threshold_elev_2_le)

        self.thr_displaced_1_le = QtWidgets.QLineEdit()
        self.thr_displaced_1_le.setObjectName(f"lineEdit_thr_displaced_1_{self.index}")
        self.thr_displaced_1_le.setPlaceholderText("blank = not displaced")
        self.thr_displaced_1_le.setToolTip(
            "Displaced threshold distance for primary end (meters). Leave blank if none."
        )
        self.thr_displaced_1_le.setValidator(self.distance_validator)
        self._set_control_width(self.thr_displaced_1_le)

        self.thr_displaced_2_le = QtWidgets.QLineEdit()
        self.thr_displaced_2_le.setObjectName(f"lineEdit_thr_displaced_2_{self.index}")
        self.thr_displaced_2_le.setPlaceholderText("blank = not displaced")
        self.thr_displaced_2_le.setToolTip(
            "Displaced threshold distance for reciprocal end (meters). Leave blank if none."
        )
        self.thr_displaced_2_le.setValidator(self.distance_validator)
        self._set_control_width(self.thr_displaced_2_le)

        self.thr_pre_area_1_le = QtWidgets.QLineEdit()
        self.thr_pre_area_1_le.setObjectName(f"lineEdit_thr_pre_area_1_{self.index}")
        self.thr_pre_area_1_le.setPlaceholderText("e.g., 60")
        self.thr_pre_area_1_le.setToolTip("Length of pre-threshold area for primary end (meters). Leave blank if none.")
        self.thr_pre_area_1_le.setValidator(self.distance_validator)
        self._set_control_width(self.thr_pre_area_1_le)

        self.thr_pre_area_2_le = QtWidgets.QLineEdit()
        self.thr_pre_area_2_le.setObjectName(f"lineEdit_thr_pre_area_2_{self.index}")
        self.thr_pre_area_2_le.setPlaceholderText("e.g., 60")
        self.thr_pre_area_2_le.setToolTip(
            "Length of pre-threshold area for reciprocal end (meters). Leave blank if none."
        )
        self.thr_pre_area_2_le.setValidator(self.distance_validator)
        self._set_control_width(self.thr_pre_area_2_le)

        primary_header = self._column_header_label("Primary End")
        reciprocal_header = self._column_header_label("Reciprocal End")

        current_coord_row = 0
        gridLayout_Coords.addWidget(primary_header, current_coord_row, 1)
        gridLayout_Coords.addWidget(reciprocal_header, current_coord_row, 2)
        current_coord_row += 1
        gridLayout_Coords.addWidget(label_designation_row, current_coord_row, 0)
        gridLayout_Coords.addLayout(h_layout_desig_inputs, current_coord_row, 1)
        gridLayout_Coords.addWidget(self.rec_desig_hdr_lbl, current_coord_row, 2)
        self._standardize_form_rows(gridLayout_Coords, 2)

        core_widget.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding,
            QtWidgets.QSizePolicy.Policy.Fixed,
        )

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
        advanced_body_layout.setSpacing(6)
        advanced_body_layout.addWidget(core_widget, 0, QtCore.Qt.AlignmentFlag.AlignTop)

        threshold_group = QtWidgets.QGroupBox("Threshold Details")
        threshold_group.setObjectName(f"groupBox_threshold_details_{self.index}")
        self._style_section_groupbox(threshold_group)
        threshold_layout = QtWidgets.QGridLayout(threshold_group)
        self._configure_runway_form_grid(threshold_layout)

        threshold_layout.addWidget(label_easting_row, 0, 0)
        threshold_layout.addWidget(self.thr_east_le, 0, 1)
        threshold_layout.addWidget(self.rec_east_le, 0, 2)
        threshold_layout.addWidget(label_northing_row, 1, 0)
        threshold_layout.addWidget(self.thr_north_le, 1, 1)
        threshold_layout.addWidget(self.rec_north_le, 1, 2)
        threshold_layout.addWidget(label_threshold_elevation_row, 2, 0)
        threshold_layout.addWidget(self.threshold_elev_1_le, 2, 1)
        threshold_layout.addWidget(self.threshold_elev_2_le, 2, 2)
        threshold_layout.addWidget(label_displaced_row, 3, 0)
        threshold_layout.addWidget(self.thr_displaced_1_le, 3, 1)
        threshold_layout.addWidget(self.thr_displaced_2_le, 3, 2)
        threshold_layout.addWidget(label_runway_end_elevation_row, 4, 0)
        threshold_layout.addWidget(self.runway_end_elev_1_le, 4, 1)
        threshold_layout.addWidget(self.runway_end_elev_2_le, 4, 2)
        self._standardize_form_rows(threshold_layout, 5)

        self.dist_lbl = QtWidgets.QLabel(CALC_PLACEHOLDER)
        self.dist_lbl.setObjectName(f"label_rwy_distance_{self.index}")
        self.dist_lbl.hide()

        self.azim_lbl = QtWidgets.QLabel(CALC_PLACEHOLDER)
        self.azim_lbl.setObjectName(f"label_rwy_azimuth_{self.index}")
        self.azim_lbl.hide()

        label_runway_shoulder = QtWidgets.QLabel("Runway Shoulder (m):")
        label_runway_shoulder.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter)
        self.shoulder_le = QtWidgets.QLineEdit()
        self.shoulder_le.setObjectName(f"lineEdit_rwy_shoulder_{self.index}")
        self.shoulder_le.setToolTip("Enter width of runway shoulder (each side, if applicable).")
        self.shoulder_le.setValidator(self.distance_validator)
        self._set_control_width(self.shoulder_le)

        advanced_body_layout.addWidget(threshold_group)
        self._add_starter_extension_controls(advanced_body_layout)
        self._add_pre_threshold_area_controls(advanced_body_layout)
        self._add_runway_dimensions_controls(advanced_body_layout, label_runway_width, label_runway_shoulder)
        self._add_runway_operations_controls(advanced_body_layout)
        self._add_runway_characteristics_controls(advanced_body_layout)
        self._add_declared_distance_controls(advanced_body_layout)
        self._add_modernised_annex14_controls(advanced_body_layout)
        advanced_layout.addWidget(advanced_body)
        groupBox_layout.addWidget(self.advanced_widget, 0, QtCore.Qt.AlignmentFlag.AlignTop)

        self._update_threshold_dependencies()
        self._update_starter_extension_dependencies()
        self._update_status_chip()
        self._set_advanced_visible(False)

    def _column_header_label(self, text: str) -> QtWidgets.QLabel:
        label = QtWidgets.QLabel(text)
        label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        label.setMinimumHeight(RUNWAY_FORM_ROW_HEIGHT)
        label.setStyleSheet(
            "QLabel { color: #4f5963; font-size: 11px; font-weight: 600; padding: 0 6px; }"
        )
        return label

    def _set_control_width(
        self,
        widget: QtWidgets.QWidget,
    ) -> None:
        widget.setMinimumWidth(0)
        widget.setMaximumWidth(16777215)
        widget.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding,
            widget.sizePolicy().verticalPolicy(),
        )

    def _configure_runway_form_grid(self, layout: QtWidgets.QGridLayout) -> None:
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setHorizontalSpacing(RUNWAY_FORM_COLUMN_GAP)
        layout.setVerticalSpacing(RUNWAY_FORM_VERTICAL_GAP)
        layout.setColumnStretch(0, 0)
        layout.setColumnStretch(1, 1)
        layout.setColumnStretch(2, 1)
        layout.setColumnStretch(3, 0)
        layout.setColumnMinimumWidth(0, RUNWAY_FORM_LABEL_MIN_WIDTH)
        layout.setColumnMinimumWidth(1, RUNWAY_FORM_FIELD_MIN_WIDTH)
        layout.setColumnMinimumWidth(2, RUNWAY_FORM_FIELD_MIN_WIDTH)
        layout.setColumnMinimumWidth(3, 0)

    def _standardize_form_rows(self, layout: QtWidgets.QGridLayout, row_count: int) -> None:
        for row in range(row_count):
            layout.setRowMinimumHeight(row, RUNWAY_FORM_ROW_HEIGHT)

    def _add_arc_controls(
        self,
        layout: QtWidgets.QGridLayout,
        row: int,
        label_col: int = 0,
        input_col: int = 1,
        input_col_span: int = 1,
    ) -> None:
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
        self._set_control_width(self.arc_num_combo)
        layout.addWidget(label_arc_num, row, label_col)
        layout.addWidget(self.arc_num_combo, row, input_col, 1, input_col_span)

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
        self._set_control_width(self.arc_let_combo)
        layout.addWidget(label_arc_let, row + 1, label_col)
        layout.addWidget(self.arc_let_combo, row + 1, input_col, 1, input_col_span)

    def _add_surface_controls(
        self,
        layout: QtWidgets.QGridLayout,
        row: int,
        label_col: int = 0,
        input_col: int = 1,
        input_col_span: int = 1,
    ) -> None:
        label_surface_category = QtWidgets.QLabel("Surface Category:")
        label_surface_category.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter)
        self.surface_category_combo = NoWheelComboBox()
        self.surface_category_combo.setObjectName(f"comboBox_surface_category_{self.index}")
        self.surface_category_combo.addItems([""] + list(RUNWAY_SURFACE_MATERIALS))
        self.surface_category_combo.setToolTip("Select runway surface category.")
        self.surface_category_combo.setFocusPolicy(QtCore.Qt.FocusPolicy.StrongFocus)
        self._set_control_width(self.surface_category_combo)
        layout.addWidget(label_surface_category, row, label_col)
        layout.addWidget(self.surface_category_combo, row, input_col, 1, input_col_span)

        label_surface_material = QtWidgets.QLabel("Surface Material:")
        label_surface_material.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter)
        self.surface_material_combo = NoWheelComboBox()
        self.surface_material_combo.setObjectName(f"comboBox_surface_material_{self.index}")
        self.surface_material_combo.setToolTip("Select runway surface material for the chosen category.")
        self.surface_material_combo.setFocusPolicy(QtCore.Qt.FocusPolicy.StrongFocus)
        self._set_control_width(self.surface_material_combo)
        self._refresh_surface_material_options("")
        layout.addWidget(label_surface_material, row + 1, label_col)
        layout.addWidget(self.surface_material_combo, row + 1, input_col, 1, input_col_span)

    def _add_adg_controls(
        self,
        layout: QtWidgets.QGridLayout,
        row: int,
        label_col: int = 0,
        input_col: int = 1,
        input_col_span: int = 1,
    ) -> None:
        label_adg = QtWidgets.QLabel("ADG:")
        label_adg.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter)
        self.adg_combo = NoWheelComboBox()
        self.adg_combo.setObjectName(f"comboBox_adg_{self.index}")
        for label, value in [
            ("", ""),
            ("I", "I"),
            ("IIA", "IIA"),
            ("IIB", "IIB"),
            ("IIC", "IIC"),
            ("III", "III"),
            ("IV", "IV"),
            ("V", "V"),
        ]:
            self.adg_combo.addItem(label, userData=value)
        self.adg_combo.setToolTip(
            f"Select Aeroplane Design Group for {MODERNISED_DISPLAY_NAME} generation."
        )
        self.adg_combo.setFocusPolicy(QtCore.Qt.FocusPolicy.StrongFocus)
        self._set_control_width(self.adg_combo)
        layout.addWidget(label_adg, row, label_col)
        layout.addWidget(self.adg_combo, row, input_col, 1, input_col_span)

    def _add_runway_type_controls(
        self,
        layout: QtWidgets.QGridLayout,
        row: int,
        label_col: int = 0,
        input_col: int = 1,
        reciprocal_input_col: Optional[int] = None,
    ) -> None:
        self._approach_type_in_threshold_grid = reciprocal_input_col is not None
        runway_types = [
            "",
            "Non-Instrument (NI)",
            "Non-Precision Approach (NPA)",
            "Precision Approach CAT I",
            "Precision Approach CAT II/III",
        ]
        self.type1_lbl = QtWidgets.QLabel("Approach Type:" if reciprocal_input_col is not None else "(Primary End) Type:")
        self.type1_lbl.setObjectName(f"label_type_desig1_{self.index}")
        self.type1_lbl.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter)
        self.type1_combo = NoWheelComboBox()
        self.type1_combo.setObjectName(f"comboBox_type_desig1_{self.index}")
        self.type1_combo.addItems(runway_types)
        self.type1_combo.setToolTip("Select type for primary end.")
        self.type1_combo.setFocusPolicy(QtCore.Qt.FocusPolicy.StrongFocus)
        self._set_control_width(self.type1_combo)
        layout.addWidget(self.type1_lbl, row, label_col)
        layout.addWidget(self.type1_combo, row, input_col)

        self.type2_lbl = QtWidgets.QLabel("" if reciprocal_input_col is not None else "(Reciprocal End) Type:")
        self.type2_lbl.setObjectName(f"label_type_desig2_{self.index}")
        self.type2_lbl.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter)
        self.type2_combo = NoWheelComboBox()
        self.type2_combo.setObjectName(f"comboBox_type_desig2_{self.index}")
        self.type2_combo.addItems(runway_types)
        self.type2_combo.setToolTip("Select type for reciprocal end.")
        self.type2_combo.setFocusPolicy(QtCore.Qt.FocusPolicy.StrongFocus)
        self._set_control_width(self.type2_combo)
        if reciprocal_input_col is None:
            layout.addWidget(self.type2_lbl, row + 1, label_col)
            layout.addWidget(self.type2_combo, row + 1, input_col)
        else:
            layout.addWidget(self.type2_combo, row, reciprocal_input_col)

    def _add_runway_availability_controls(self, layout: QtWidgets.QGridLayout, row: int) -> None:
        takeoff_label = QtWidgets.QLabel("Takeoff available:")
        self.takeoff_available_1_cb = QtWidgets.QCheckBox()
        self.takeoff_available_1_cb.setObjectName(f"checkBox_takeoff_available_1_{self.index}")
        self.takeoff_available_1_cb.setChecked(True)
        self.takeoff_available_1_cb.setToolTip("Takeoff is available in the primary runway direction.")

        self.takeoff_available_2_cb = QtWidgets.QCheckBox()
        self.takeoff_available_2_cb.setObjectName(f"checkBox_takeoff_available_2_{self.index}")
        self.takeoff_available_2_cb.setChecked(True)
        self.takeoff_available_2_cb.setToolTip("Takeoff is available in the reciprocal runway direction.")
        layout.addWidget(takeoff_label, row, 0)
        layout.addWidget(self.takeoff_available_1_cb, row, 1)
        layout.addWidget(self.takeoff_available_2_cb, row, 2)

        landing_label = QtWidgets.QLabel("Landing available:")
        self.landing_available_1_cb = QtWidgets.QCheckBox()
        self.landing_available_1_cb.setObjectName(f"checkBox_landing_available_1_{self.index}")
        self.landing_available_1_cb.setChecked(True)
        self.landing_available_1_cb.setToolTip("Landing is available toward the primary runway threshold.")

        self.landing_available_2_cb = QtWidgets.QCheckBox()
        self.landing_available_2_cb.setObjectName(f"checkBox_landing_available_2_{self.index}")
        self.landing_available_2_cb.setChecked(True)
        self.landing_available_2_cb.setToolTip("Landing is available toward the reciprocal runway threshold.")
        layout.addWidget(landing_label, row + 1, 0)
        layout.addWidget(self.landing_available_1_cb, row + 1, 1)
        layout.addWidget(self.landing_available_2_cb, row + 1, 2)

    def _add_lahso_controls(self, layout: QtWidgets.QGridLayout, row: int) -> None:
        lahso_label = QtWidgets.QLabel("LAHSO applied:")
        self.lahso_applied_1_cb = QtWidgets.QCheckBox()
        self.lahso_applied_1_cb.setObjectName(f"checkBox_lahso_applied_1_{self.index}")
        self.lahso_applied_1_cb.setChecked(False)
        self.lahso_applied_1_cb.setToolTip(
            "Indicates that a LAHSO holding position marking is required for the primary runway direction."
        )

        self.lahso_applied_2_cb = QtWidgets.QCheckBox()
        self.lahso_applied_2_cb.setObjectName(f"checkBox_lahso_applied_2_{self.index}")
        self.lahso_applied_2_cb.setChecked(False)
        self.lahso_applied_2_cb.setToolTip(
            "Indicates that a LAHSO holding position marking is required for the reciprocal runway direction."
        )
        layout.addWidget(lahso_label, row, 0)
        layout.addWidget(self.lahso_applied_1_cb, row, 1)
        layout.addWidget(self.lahso_applied_2_cb, row, 2)

    def _add_starter_extension_controls(
        self, parent_layout: QtWidgets.QVBoxLayout
    ) -> None:
        group = QtWidgets.QGroupBox("Runway Starter Extension")
        group.setObjectName(f"groupBox_starter_extension_{self.index}")
        self._style_section_groupbox(group)
        layout = QtWidgets.QGridLayout(group)
        self._configure_runway_form_grid(layout)
        layout.addWidget(self._column_header_label("Primary End"), 0, 1)
        layout.addWidget(self._column_header_label("Reciprocal End"), 0, 2)

        def extension_edit(suffix: str, tooltip: str) -> QtWidgets.QLineEdit:
            line_edit = QtWidgets.QLineEdit()
            line_edit.setObjectName(f"lineEdit_starter_extension_{suffix}_{self.index}")
            line_edit.setValidator(self.distance_validator)
            line_edit.setToolTip(tooltip)
            self._set_control_width(line_edit)
            return line_edit

        self.starter_extension_length_1_le = extension_edit(
            "length_1", "Length outward from the primary threshold; blank means no starter extension."
        )
        self.starter_extension_length_2_le = extension_edit(
            "length_2", "Length outward from the reciprocal threshold; blank means no starter extension."
        )
        self.starter_extension_width_1_le = extension_edit(
            "width_1", "Paved width of the primary-end starter extension."
        )
        self.starter_extension_width_2_le = extension_edit(
            "width_2", "Paved width of the reciprocal-end starter extension."
        )
        self.starter_extension_shoulder_1_le = extension_edit(
            "shoulder_1", "Starter-extension shoulder width on each side."
        )
        self.starter_extension_shoulder_2_le = extension_edit(
            "shoulder_2", "Starter-extension shoulder width on each side."
        )
        self.starter_extension_outer_elev_1_le = extension_edit(
            "outer_elev_1", "Elevation at the outer end of the primary-end starter extension."
        )
        self.starter_extension_outer_elev_2_le = extension_edit(
            "outer_elev_2", "Elevation at the outer end of the reciprocal-end starter extension."
        )
        self.starter_extension_outer_elev_1_le.setValidator(self.numeric_validator)
        self.starter_extension_outer_elev_2_le.setValidator(self.numeric_validator)

        rows = (
            ("Extension Length (m):", self.starter_extension_length_1_le, self.starter_extension_length_2_le),
            ("Extension Width (m):", self.starter_extension_width_1_le, self.starter_extension_width_2_le),
            ("Shoulder Width (m):", self.starter_extension_shoulder_1_le, self.starter_extension_shoulder_2_le),
            ("Outer-End Elevation (m AHD):", self.starter_extension_outer_elev_1_le, self.starter_extension_outer_elev_2_le),
        )
        for row, (label, primary, reciprocal) in enumerate(rows, start=1):
            layout.addWidget(QtWidgets.QLabel(label), row, 0)
            layout.addWidget(primary, row, 1)
            layout.addWidget(reciprocal, row, 2)
        self._standardize_form_rows(layout, 5)
        self._update_starter_extension_dependencies()
        parent_layout.addWidget(group)

    def _add_pre_threshold_area_controls(
        self, parent_layout: QtWidgets.QVBoxLayout
    ) -> None:
        group = QtWidgets.QGroupBox("Unusable Pre-threshold Area")
        group.setObjectName(f"groupBox_pre_threshold_area_{self.index}")
        self._style_section_groupbox(group)
        layout = QtWidgets.QGridLayout(group)
        self._configure_runway_form_grid(layout)
        layout.addWidget(QtWidgets.QLabel("Area Length (m):"), 0, 0)
        layout.addWidget(self.thr_pre_area_1_le, 0, 1)
        layout.addWidget(self.thr_pre_area_2_le, 0, 2)
        self._standardize_form_rows(layout, 1)
        parent_layout.addWidget(group)

    def _add_runway_dimensions_controls(
        self,
        parent_layout: QtWidgets.QVBoxLayout,
        label_runway_width: QtWidgets.QLabel,
        label_runway_shoulder: QtWidgets.QLabel,
    ) -> None:
        dimensions_group = QtWidgets.QGroupBox("Runway Dimensions")
        dimensions_group.setObjectName(f"groupBox_runway_dimensions_{self.index}")
        self._style_section_groupbox(dimensions_group)
        dimensions_layout = QtWidgets.QGridLayout(dimensions_group)
        self._configure_runway_form_grid(dimensions_layout)

        dimensions_layout.addWidget(label_runway_width, 0, 0)
        self._set_control_width(self.width_le)
        dimensions_layout.addWidget(self.width_le, 0, 1, 1, 2)
        dimensions_layout.addWidget(label_runway_shoulder, 1, 0)
        self._set_control_width(self.shoulder_le)
        dimensions_layout.addWidget(self.shoulder_le, 1, 1, 1, 2)

        clearway_label = QtWidgets.QLabel("Clearway (m):")
        self.clearway1_len_le = QtWidgets.QLineEdit()
        self.clearway1_len_le.setObjectName(f"lineEdit_clearway1_len_{self.index}")
        self.clearway1_len_le.setPlaceholderText("0")
        self.clearway1_len_le.setToolTip("Clearway length beyond the primary physical runway end.")
        self.clearway1_len_le.setValidator(self.distance_validator)
        self._set_control_width(self.clearway1_len_le)

        self.clearway2_len_le = QtWidgets.QLineEdit()
        self.clearway2_len_le.setObjectName(f"lineEdit_clearway2_len_{self.index}")
        self.clearway2_len_le.setPlaceholderText("0")
        self.clearway2_len_le.setToolTip("Clearway length beyond the reciprocal physical runway end.")
        self.clearway2_len_le.setValidator(self.distance_validator)
        self._set_control_width(self.clearway2_len_le)
        dimensions_layout.addWidget(clearway_label, 2, 0)
        dimensions_layout.addWidget(self.clearway1_len_le, 2, 1)
        dimensions_layout.addWidget(self.clearway2_len_le, 2, 2)

        stopway_label = QtWidgets.QLabel("Stopway (m):")
        self.stopway1_len_le = QtWidgets.QLineEdit()
        self.stopway1_len_le.setObjectName(f"lineEdit_stopway1_len_{self.index}")
        self.stopway1_len_le.setPlaceholderText("0")
        self.stopway1_len_le.setToolTip("Stopway length beyond the primary physical runway end.")
        self.stopway1_len_le.setValidator(self.distance_validator)
        self._set_control_width(self.stopway1_len_le)

        self.stopway2_len_le = QtWidgets.QLineEdit()
        self.stopway2_len_le.setObjectName(f"lineEdit_stopway2_len_{self.index}")
        self.stopway2_len_le.setPlaceholderText("0")
        self.stopway2_len_le.setToolTip("Stopway length beyond the reciprocal physical runway end.")
        self.stopway2_len_le.setValidator(self.distance_validator)
        self._set_control_width(self.stopway2_len_le)
        dimensions_layout.addWidget(stopway_label, 3, 0)
        dimensions_layout.addWidget(self.stopway1_len_le, 3, 1)
        dimensions_layout.addWidget(self.stopway2_len_le, 3, 2)

        self.cap168_wide_runway_cb = QtWidgets.QCheckBox(
            "Runway width exceeds the applicable CAP168 Table 3.2 minimum by 10%"
        )
        self.cap168_wide_runway_cb.setObjectName(f"checkBox_cap168_wide_runway_{self.index}")
        self.cap168_wide_runway_cb.setToolTip(
            "Applies CAP168 4.15/4.24 wide-runway inner-edge rules to approach and take-off climb surfaces."
        )
        dimensions_layout.addWidget(QtWidgets.QLabel("CAP168 wide runway:"), 4, 0)
        dimensions_layout.addWidget(self.cap168_wide_runway_cb, 4, 1, 1, 2)
        self._standardize_form_rows(dimensions_layout, 5)

        parent_layout.addWidget(dimensions_group)

    def _add_runway_operations_controls(self, parent_layout: QtWidgets.QVBoxLayout) -> None:
        operations_group = QtWidgets.QGroupBox("Runway Operations")
        operations_group.setObjectName(f"groupBox_runway_operations_{self.index}")
        self._style_section_groupbox(operations_group)
        operations_layout = QtWidgets.QGridLayout(operations_group)
        self._configure_runway_form_grid(operations_layout)

        self._add_runway_availability_controls(operations_layout, 0)
        self._add_lahso_controls(operations_layout, 2)
        self._add_runway_type_controls(operations_layout, 3, 0, 1, reciprocal_input_col=2)
        self._add_ols_track_controls(operations_layout, 4)
        self._standardize_form_rows(operations_layout, 8)

        parent_layout.addWidget(operations_group)

    def _add_ols_track_controls(self, layout: QtWidgets.QGridLayout, row: int) -> None:
        """Add explicit plan-track inputs used by CAP168 conventional OLS."""

        approach_label = QtWidgets.QLabel("OLS approach track:")
        self.approach_track_1_combo = NoWheelComboBox()
        self.approach_track_2_combo = NoWheelComboBox()
        approach_choices = [
            ("Aligned with runway", "aligned"),
            ("Offset straight track", "offset"),
            ("Curved / change up to 15°", "curved"),
            ("Curved / change over 15°", "curved_gt_15"),
        ]
        for combo, suffix in (
            (self.approach_track_1_combo, "1"),
            (self.approach_track_2_combo, "2"),
        ):
            combo.setObjectName(f"comboBox_approach_track_{suffix}_{self.index}")
            for label, value in approach_choices:
                combo.addItem(label, userData=value)
            combo.setToolTip(
                "Nominate the CAP168 approach ground-track form. Non-aligned tracks require a project-CRS LINESTRING below."
            )
            self._set_control_width(combo)
        layout.addWidget(approach_label, row, 0)
        layout.addWidget(self.approach_track_1_combo, row, 1)
        layout.addWidget(self.approach_track_2_combo, row, 2)

        self.approach_track_wkt_1_le = self._track_wkt_line_edit(
            "approach_track_wkt_1",
            "Approach track from the primary threshold outward.",
        )
        self.approach_track_wkt_2_le = self._track_wkt_line_edit(
            "approach_track_wkt_2",
            "Approach track from the reciprocal threshold outward.",
        )
        layout.addWidget(QtWidgets.QLabel("Approach path WKT:"), row + 1, 0)
        layout.addWidget(self.approach_track_wkt_1_le, row + 1, 1)
        layout.addWidget(self.approach_track_wkt_2_le, row + 1, 2)

        takeoff_label = QtWidgets.QLabel("OLS take-off track:")
        self.takeoff_track_1_combo = NoWheelComboBox()
        self.takeoff_track_2_combo = NoWheelComboBox()
        takeoff_choices = [
            ("Aligned with runway", "aligned"),
            ("Offset straight track", "offset"),
            ("Curved / change up to 15°", "curved"),
            ("Heading change over 15°", "curved_gt_15"),
        ]
        for combo, suffix in (
            (self.takeoff_track_1_combo, "1"),
            (self.takeoff_track_2_combo, "2"),
        ):
            combo.setObjectName(f"comboBox_takeoff_track_{suffix}_{self.index}")
            for label, value in takeoff_choices:
                combo.addItem(label, userData=value)
            combo.setToolTip(
                "Nominate the CAP168 take-off ground-track form. The over-15° choice applies the conditional outer width."
            )
            self._set_control_width(combo)
        layout.addWidget(takeoff_label, row + 2, 0)
        layout.addWidget(self.takeoff_track_1_combo, row + 2, 1)
        layout.addWidget(self.takeoff_track_2_combo, row + 2, 2)

        self.takeoff_track_wkt_1_le = self._track_wkt_line_edit(
            "takeoff_track_wkt_1",
            "Take-off track from the primary-direction departure pavement end outward.",
        )
        self.takeoff_track_wkt_2_le = self._track_wkt_line_edit(
            "takeoff_track_wkt_2",
            "Take-off track from the reciprocal-direction departure pavement end outward.",
        )
        layout.addWidget(QtWidgets.QLabel("Take-off path WKT:"), row + 3, 0)
        layout.addWidget(self.takeoff_track_wkt_1_le, row + 3, 1)
        layout.addWidget(self.takeoff_track_wkt_2_le, row + 3, 2)

    def _track_wkt_line_edit(self, suffix: str, tooltip: str) -> QtWidgets.QLineEdit:
        line_edit = QtWidgets.QLineEdit()
        line_edit.setObjectName(f"lineEdit_{suffix}_{self.index}")
        line_edit.setPlaceholderText("LINESTRING (...) when non-aligned")
        line_edit.setToolTip(f"{tooltip} Coordinates use the current project CRS.")
        self._set_control_width(line_edit)
        return line_edit

    def _add_runway_characteristics_controls(self, parent_layout: QtWidgets.QVBoxLayout) -> None:
        classification_group = QtWidgets.QGroupBox("Runway Characteristics")
        classification_group.setObjectName(f"groupBox_classification_{self.index}")
        self._style_section_groupbox(classification_group)
        classification_layout = QtWidgets.QGridLayout(classification_group)
        self._configure_runway_form_grid(classification_layout)

        self._add_arc_controls(
            classification_layout,
            0,
            input_col_span=2,
        )
        self._add_adg_controls(
            classification_layout,
            2,
            input_col_span=2,
        )
        self._add_surface_controls(
            classification_layout,
            3,
            input_col_span=2,
        )
        self._standardize_form_rows(classification_layout, 5)

        parent_layout.addWidget(classification_group)

    def _add_declared_distance_controls(self, parent_layout: QtWidgets.QVBoxLayout):
        declared_group = QtWidgets.QGroupBox("Declared Distances")
        declared_group.setObjectName(f"groupBox_declared_distances_{self.index}")
        self._style_section_groupbox(declared_group)
        declared_layout = QtWidgets.QGridLayout(declared_group)
        self._configure_runway_form_grid(declared_layout)

        self.declared_distance_mode_combo = NoWheelComboBox()
        self.declared_distance_mode_combo.setObjectName(
            f"comboBox_declared_distance_mode_{self.index}"
        )
        self.declared_distance_mode_combo.addItem(
            "Calculated (planning)", "calculated"
        )
        self.declared_distance_mode_combo.addItem(
            "Published (existing runway)", "published"
        )
        self.declared_distance_mode_combo.setToolTip(
            "Use calculated distances for planning, or enter published TORA, TODA, ASDA and LDA values for an existing runway."
        )
        self._set_control_width(self.declared_distance_mode_combo)
        declared_layout.addWidget(QtWidgets.QLabel("Distance source:"), 0, 0)
        declared_layout.addWidget(self.declared_distance_mode_combo, 0, 1, 1, 2)
        declared_layout.addWidget(self._column_header_label("Primary End"), 1, 1)
        declared_layout.addWidget(self._column_header_label("Reciprocal End"), 1, 2)

        self.tora_override_1_le = self._declared_override_line_edit("tora_override_1", "Published primary TORA.")
        self.tora_override_2_le = self._declared_override_line_edit("tora_override_2", "Published reciprocal TORA.")
        declared_layout.addWidget(QtWidgets.QLabel("TORA (m):"), 2, 0)
        declared_layout.addWidget(self.tora_override_1_le, 2, 1)
        declared_layout.addWidget(self.tora_override_2_le, 2, 2)

        self.toda_override_1_le = self._declared_override_line_edit("toda_override_1", "Published primary TODA.")
        self.toda_override_2_le = self._declared_override_line_edit("toda_override_2", "Published reciprocal TODA.")
        declared_layout.addWidget(QtWidgets.QLabel("TODA (m):"), 3, 0)
        declared_layout.addWidget(self.toda_override_1_le, 3, 1)
        declared_layout.addWidget(self.toda_override_2_le, 3, 2)

        self.asda_override_1_le = self._declared_override_line_edit("asda_override_1", "Published primary ASDA.")
        self.asda_override_2_le = self._declared_override_line_edit("asda_override_2", "Published reciprocal ASDA.")
        declared_layout.addWidget(QtWidgets.QLabel("ASDA (m):"), 4, 0)
        declared_layout.addWidget(self.asda_override_1_le, 4, 1)
        declared_layout.addWidget(self.asda_override_2_le, 4, 2)

        self.lda_override_1_le = self._declared_override_line_edit("lda_override_1", "Published primary LDA.")
        self.lda_override_2_le = self._declared_override_line_edit("lda_override_2", "Published reciprocal LDA.")
        declared_layout.addWidget(QtWidgets.QLabel("LDA (m):"), 5, 0)
        declared_layout.addWidget(self.lda_override_1_le, 5, 1)
        declared_layout.addWidget(self.lda_override_2_le, 5, 2)
        self._standardize_form_rows(declared_layout, 6)
        self._update_declared_distance_mode()

        parent_layout.addWidget(declared_group)

    def _add_modernised_annex14_controls(
        self,
        parent_layout: QtWidgets.QVBoxLayout,
    ) -> None:
        container = QtWidgets.QWidget()
        container.setObjectName(f"widget_annex14_modernised_{self.index}")
        container_layout = QtWidgets.QVBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(4)

        disclosure = QtWidgets.QToolButton()
        disclosure.setObjectName(f"toolButton_annex14_modernised_{self.index}")
        disclosure.setText(MODERNISED_DISPLAY_NAME)
        disclosure.setCheckable(True)
        disclosure.setChecked(False)
        disclosure.setArrowType(QtCore.Qt.ArrowType.RightArrow)
        disclosure.setToolButtonStyle(
            QtCore.Qt.ToolButtonStyle.ToolButtonTextBesideIcon
        )
        disclosure.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding,
            QtWidgets.QSizePolicy.Policy.Fixed,
        )
        container_layout.addWidget(disclosure)

        body = QtWidgets.QGroupBox()
        body.setObjectName(f"groupBox_annex14_modernised_{self.index}")
        self._style_section_groupbox(body)
        grid = QtWidgets.QGridLayout(body)
        self._configure_runway_form_grid(grid)

        self.annex14_confirmed_cb = QtWidgets.QCheckBox(
            "I have reviewed the strip and straight-in operation basis"
        )
        self.annex14_confirmed_cb.setObjectName(
            f"checkBox_annex14_confirmed_{self.index}"
        )
        grid.addWidget(QtWidgets.QLabel("Configuration:"), 0, 0)
        grid.addWidget(self.annex14_confirmed_cb, 0, 1, 1, 2)

        self.annex14_strip_source_combo = NoWheelComboBox()
        self.annex14_strip_source_combo.setObjectName(
            f"comboBox_annex14_strip_source_{self.index}"
        )
        self.annex14_strip_source_combo.addItem(
            "Prefilled from design standard",
            "design_standard_prefill",
        )
        self.annex14_strip_source_combo.addItem("Manual override", "manual")
        self.annex14_strip_source_combo.setToolTip(
            "Records whether the OFS strip dimensions were accepted from the "
            "selected design standard or entered manually."
        )
        grid.addWidget(QtWidgets.QLabel("Strip source:"), 1, 0)
        grid.addWidget(self.annex14_strip_source_combo, 1, 1, 1, 2)

        self.annex14_strip_width_le = self._annex14_number_edit(
            "strip_width",
            "Overall strip width used by transitional and inner surfaces.",
        )
        self.annex14_strip_extension_le = self._annex14_number_edit(
            "strip_extension",
            "Strip extension beyond each runway end.",
        )
        grid.addWidget(QtWidgets.QLabel("Strip width / end extension (m):"), 2, 0)
        grid.addWidget(self.annex14_strip_width_le, 2, 1)
        grid.addWidget(self.annex14_strip_extension_le, 2, 2)

        self.annex14_code_f_no_digital_cb = QtWidgets.QCheckBox(
            "Code F aircraft without qualifying digital go-around guidance"
        )
        self.annex14_code_f_no_digital_cb.setObjectName(
            f"checkBox_annex14_code_f_no_digital_{self.index}"
        )
        grid.addWidget(QtWidgets.QLabel("Code F adjustment:"), 3, 0)
        grid.addWidget(self.annex14_code_f_no_digital_cb, 3, 1, 1, 2)

        grid.addWidget(self._column_header_label("Primary End"), 4, 1)
        grid.addWidget(self._column_header_label("Reciprocal End"), 4, 2)
        self._annex14_end_widgets: Dict[str, Dict[str, QtWidgets.QWidget]] = {}
        row = 5
        operation_labels = (
            ("circling_or_visual_circuit", "Circling / visual circuit"),
            (
                "straight_in_non_precision_instrument",
                "Straight-in non-precision instrument",
            ),
            ("precision_approach", "Precision approach"),
            ("instrument_departure", "Instrument departure"),
            ("take_off", "Take-off"),
        )
        operation_note = QtWidgets.QLabel(
            "Standard operations are derived from each runway-end type. "
            "Approaches are assumed straight-in; circling and curved/specific "
            "OES are not generated."
        )
        operation_note.setWordWrap(True)
        grid.addWidget(QtWidgets.QLabel("Operation basis:"), row, 0)
        grid.addWidget(operation_note, row, 1, 1, 2)
        row += 1
        for key, _label in operation_labels:
            for end_key in ("primary_end", "reciprocal_end"):
                end_widgets = self._annex14_end_widgets.setdefault(
                    end_key,
                    {"operations": {}},
                )
                checkbox = QtWidgets.QCheckBox(body)
                checkbox.setObjectName(
                    f"checkBox_annex14_{end_key}_{key}_{self.index}"
                )
                checkbox.hide()
                end_widgets["operations"][key] = checkbox

        numeric_rows = (
            (
                "maximum_certificated_takeoff_mass_kg",
                "Maximum certificated take-off mass (kg, optional)",
                "Blank uses the conservative above-5,700 kg take-off dimensions.",
            ),
            (
                "governing_approach_surface_slope_percent",
                "Governing OFS approach slope (%)",
                "Blank uses the unadjusted table slope.",
            ),
            (
                "obstacle_clearance_height_m",
                "Obstacle clearance height (m)",
                "Blank uses the unadjusted table length.",
            ),
        )
        for key, label, tooltip in numeric_rows:
            grid.addWidget(QtWidgets.QLabel(label + ":"), row, 0)
            for column, end_key in ((1, "primary_end"), (2, "reciprocal_end")):
                line_edit = self._annex14_number_edit(
                    f"{end_key}_{key}",
                    tooltip,
                )
                self._annex14_end_widgets[end_key][key] = line_edit
                grid.addWidget(line_edit, row, column)
            row += 1

        grid.addWidget(QtWidgets.QLabel("Specific/curved OES required:"), row, 0)
        for column, end_key in ((1, "primary_end"), (2, "reciprocal_end")):
            checkbox = QtWidgets.QCheckBox()
            checkbox.setObjectName(
                f"checkBox_annex14_{end_key}_specific_oes_{self.index}"
            )
            checkbox.setToolTip(
                "Specific OES geometry is not supported; selecting this blocks "
                "modernised generation."
            )
            self._annex14_end_widgets[end_key]["specific_oes_required"] = checkbox
            grid.addWidget(checkbox, row, column)
        grid.itemAtPosition(row, 0).widget().hide()
        for column in (1, 2):
            grid.itemAtPosition(row, column).widget().hide()
        self._standardize_form_rows(grid, row + 1)

        body.setVisible(False)
        disclosure.toggled.connect(body.setVisible)
        disclosure.toggled.connect(
            lambda expanded: disclosure.setArrowType(
                QtCore.Qt.ArrowType.DownArrow
                if expanded
                else QtCore.Qt.ArrowType.RightArrow
            )
        )
        self.annex14_modernised_disclosure = disclosure
        self.annex14_modernised_body = body
        container_layout.addWidget(body)
        container.hide()
        parent_layout.addWidget(container)

    def _annex14_number_edit(
        self,
        suffix: str,
        tooltip: str,
    ) -> QtWidgets.QLineEdit:
        line_edit = QtWidgets.QLineEdit()
        line_edit.setObjectName(f"lineEdit_annex14_{suffix}_{self.index}")
        if suffix.endswith("maximum_certificated_takeoff_mass_kg"):
            validator = QtGui.QDoubleValidator(0.0, 9999999.0, 1, line_edit)
            validator.setNotation(QtGui.QDoubleValidator.Notation.StandardNotation)
            line_edit.setValidator(validator)
        else:
            line_edit.setValidator(self.distance_validator)
        line_edit.setToolTip(tooltip)
        self._set_control_width(line_edit)
        return line_edit

    def _annex14_modernised_input_data(self) -> Dict[str, Any]:
        config: Dict[str, Any] = {
            "schema_version": 1,
            "confirmed": True,
            "operation_basis": "automatic_conservative_straight_in",
            "strip": {
                "source": "design_standard_prefill",
                "overall_width_m": self.annex14_strip_width_le.text().strip(),
                "end_extension_m": self.annex14_strip_extension_le.text().strip(),
            },
            "code_f_without_digital_go_around_avionics":
                str(self.arc_let_combo.currentData() or "").upper() == "F",
        }
        end_inputs = {
            "primary_end": (
                self.type1_combo.currentText(),
                self.takeoff_available_1_cb.isChecked(),
            ),
            "reciprocal_end": (
                self.type2_combo.currentText(),
                self.takeoff_available_2_cb.isChecked(),
            ),
        }
        for end_key, widgets in self._annex14_end_widgets.items():
            runway_type, takeoff_available = end_inputs[end_key]
            is_non_precision = "Non-Precision" in runway_type
            is_precision = (
                "Precision Approach" in runway_type
                and not is_non_precision
            )
            is_instrument = is_non_precision or is_precision
            operations = {
                "circling_or_visual_circuit": False,
                "straight_in_non_precision_instrument": is_non_precision,
                "precision_approach": is_precision,
                "instrument_departure": is_instrument and takeoff_available,
                "take_off": takeoff_available,
            }
            config[end_key] = {
                "operations": operations,
                "maximum_certificated_takeoff_mass_kg": None,
                "governing_approach_surface_slope_percent": None,
                "obstacle_clearance_height_m": None,
                "specific_oes_required": False,
            }
        return config

    def _set_annex14_modernised_input_data(self, raw_config: Any) -> None:
        config = raw_config if isinstance(raw_config, dict) else {}
        strip = config.get("strip") if isinstance(config.get("strip"), dict) else {}
        self.annex14_confirmed_cb.setChecked(
            self._bool_from_saved_value(config.get("confirmed", False))
        )
        self._set_combo_data(
            self.annex14_strip_source_combo,
            strip.get("source", "design_standard_prefill"),
        )
        self.annex14_strip_width_le.setText(str(strip.get("overall_width_m", "") or ""))
        self.annex14_strip_extension_le.setText(
            str(strip.get("end_extension_m", "") or "")
        )
        self.annex14_code_f_no_digital_cb.setChecked(
            self._bool_from_saved_value(
                config.get(
                    "code_f_without_digital_go_around_avionics",
                    False,
                )
            )
        )
        for end_key, widgets in self._annex14_end_widgets.items():
            end_config = (
                config.get(end_key)
                if isinstance(config.get(end_key), dict)
                else {}
            )
            operations = (
                end_config.get("operations")
                if isinstance(end_config.get("operations"), dict)
                else {}
            )
            for key, checkbox in widgets["operations"].items():
                checkbox.setChecked(
                    self._bool_from_saved_value(operations.get(key, False))
                )
            for key in (
                "maximum_certificated_takeoff_mass_kg",
                "governing_approach_surface_slope_percent",
                "obstacle_clearance_height_m",
            ):
                widgets[key].setText(str(end_config.get(key, "") or ""))
            widgets["specific_oes_required"].setChecked(
                self._bool_from_saved_value(
                    end_config.get("specific_oes_required", False)
                )
            )

    def _declared_override_line_edit(self, suffix: str, tooltip: str) -> QtWidgets.QLineEdit:
        line_edit = QtWidgets.QLineEdit()
        line_edit.setObjectName(f"lineEdit_{suffix}_{self.index}")
        line_edit.setToolTip(tooltip)
        line_edit.setValidator(self.distance_validator)
        self._set_control_width(line_edit)
        return line_edit

    @staticmethod
    def _positive_line_value(line_edit: QtWidgets.QLineEdit) -> Optional[float]:
        try:
            value = float(line_edit.text())
        except (TypeError, ValueError):
            return None
        return value if value > 0.0 else None

    def _update_threshold_dependencies(self, *_args) -> None:
        for threshold, displacement, runway_end in (
            (self.threshold_elev_1_le, self.thr_displaced_1_le, self.runway_end_elev_1_le),
            (self.threshold_elev_2_le, self.thr_displaced_2_le, self.runway_end_elev_2_le),
        ):
            displaced = self._positive_line_value(displacement) is not None
            runway_end.setReadOnly(not displaced)
            if displaced:
                runway_end.setPlaceholderText("Required when displaced")
            else:
                derived = threshold.text().strip()
                if runway_end.text() != derived:
                    runway_end.setText(derived)
                runway_end.setPlaceholderText("Derived from threshold elevation")
        if hasattr(self, "starter_extension_length_1_le"):
            self._update_starter_extension_dependencies()

    def _update_starter_extension_dependencies(self, *_args) -> None:
        if not hasattr(self, "starter_extension_length_1_le"):
            return
        for length, width, shoulder, outer_elevation, displacement, runway_end in (
            (
                self.starter_extension_length_1_le,
                self.starter_extension_width_1_le,
                self.starter_extension_shoulder_1_le,
                self.starter_extension_outer_elev_1_le,
                self.thr_displaced_1_le,
                self.runway_end_elev_1_le,
            ),
            (
                self.starter_extension_length_2_le,
                self.starter_extension_width_2_le,
                self.starter_extension_shoulder_2_le,
                self.starter_extension_outer_elev_2_le,
                self.thr_displaced_2_le,
                self.runway_end_elev_2_le,
            ),
        ):
            extension_length = self._positive_line_value(length)
            active = extension_length is not None
            width.setReadOnly(not active)
            shoulder.setReadOnly(not active)
            if not active:
                for dependent in (width, shoulder, outer_elevation):
                    if dependent.text():
                        dependent.clear()
                    dependent.setReadOnly(True)
                    dependent.setPlaceholderText("Not applicable")
                continue

            width.setPlaceholderText("Required")
            shoulder.setPlaceholderText("Optional; blank = 0")
            displacement_value = self._positive_line_value(displacement) or 0.0
            outer_is_runway_end = abs(extension_length - displacement_value) <= 1e-6
            outer_elevation.setReadOnly(outer_is_runway_end)
            if outer_is_runway_end:
                derived = runway_end.text().strip()
                if outer_elevation.text() != derived:
                    outer_elevation.setText(derived)
                outer_elevation.setPlaceholderText("Derived from runway-end elevation")
            else:
                outer_elevation.setPlaceholderText("Required")

    def _declared_distance_edits(self):
        return (
            self.tora_override_1_le,
            self.tora_override_2_le,
            self.toda_override_1_le,
            self.toda_override_2_le,
            self.asda_override_1_le,
            self.asda_override_2_le,
            self.lda_override_1_le,
            self.lda_override_2_le,
        )

    def _update_declared_distance_mode(self, _index: int = -1) -> None:
        published = self.declared_distance_mode_combo.currentData() == "published"
        for line_edit in self._declared_distance_edits():
            line_edit.setReadOnly(not published)
        self._update_declared_distance_placeholders()

    def _update_declared_distance_placeholders(self) -> None:
        try:
            threshold_length = float(self.dist_lbl.text())
        except (TypeError, ValueError):
            threshold_length = None

        def value(line_edit: QtWidgets.QLineEdit) -> float:
            try:
                return max(float(line_edit.text() or 0.0), 0.0)
            except (TypeError, ValueError):
                return 0.0

        calculated = [None] * 8
        if threshold_length is not None:
            displaced_1 = value(self.thr_displaced_1_le)
            displaced_2 = value(self.thr_displaced_2_le)
            physical_length = threshold_length + displaced_1 + displaced_2
            primary_tora = physical_length + max(
                value(self.starter_extension_length_1_le) - displaced_1, 0.0
            )
            reciprocal_tora = physical_length + max(
                value(self.starter_extension_length_2_le) - displaced_2, 0.0
            )
            calculated = [
                primary_tora,
                reciprocal_tora,
                primary_tora + value(self.clearway2_len_le),
                reciprocal_tora + value(self.clearway1_len_le),
                primary_tora + value(self.stopway2_len_le),
                reciprocal_tora + value(self.stopway1_len_le),
                threshold_length + displaced_2,
                threshold_length + displaced_1,
            ]

        published = self.declared_distance_mode_combo.currentData() == "published"
        for line_edit, calculated_value in zip(
            self._declared_distance_edits(), calculated
        ):
            if calculated_value is None:
                placeholder = "Enter published value" if published else "Awaiting geometry"
            else:
                label = "Calculated" if published else "Calculated value"
                placeholder = f"{label}: {calculated_value:.3f} m"
            line_edit.setPlaceholderText(placeholder)

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
            self.starter_extension_length_1_le,
            self.starter_extension_length_2_le,
            self.starter_extension_width_1_le,
            self.starter_extension_width_2_le,
            self.starter_extension_shoulder_1_le,
            self.starter_extension_shoulder_2_le,
            self.starter_extension_outer_elev_1_le,
            self.starter_extension_outer_elev_2_le,
            self.width_le,
            self.shoulder_le,
            self.clearway1_len_le,
            self.clearway2_len_le,
            self.stopway1_len_le,
            self.stopway2_len_le,
            self.tora_override_1_le,
            self.tora_override_2_le,
            self.toda_override_1_le,
            self.toda_override_2_le,
            self.asda_override_1_le,
            self.asda_override_2_le,
            self.lda_override_1_le,
            self.lda_override_2_le,
            self.approach_track_wkt_1_le,
            self.approach_track_wkt_2_le,
            self.takeoff_track_wkt_1_le,
            self.takeoff_track_wkt_2_le,
        ]:
            widget.textChanged.connect(self.inputChanged.emit)
        for widget in (
            self.threshold_elev_1_le,
            self.threshold_elev_2_le,
            self.thr_displaced_1_le,
            self.thr_displaced_2_le,
        ):
            widget.textChanged.connect(self._update_threshold_dependencies)
        for widget in (
            self.starter_extension_length_1_le,
            self.starter_extension_length_2_le,
            self.runway_end_elev_1_le,
            self.runway_end_elev_2_le,
        ):
            widget.textChanged.connect(self._update_starter_extension_dependencies)
        for checkbox in [
            self.takeoff_available_1_cb,
            self.takeoff_available_2_cb,
            self.landing_available_1_cb,
            self.landing_available_2_cb,
            self.lahso_applied_1_cb,
            self.lahso_applied_2_cb,
            self.cap168_wide_runway_cb,
            self.annex14_confirmed_cb,
            self.annex14_code_f_no_digital_cb,
            *[
                checkbox
                for widgets in self._annex14_end_widgets.values()
                for checkbox in (
                    *widgets["operations"].values(),
                    widgets["specific_oes_required"],
                )
            ],
        ]:
            checkbox.stateChanged.connect(self.inputChanged.emit)
        for combo in [
            self.suffix_combo,
            self.arc_num_combo,
            self.arc_let_combo,
            self.adg_combo,
            self.surface_material_combo,
            self.type1_combo,
            self.type2_combo,
            self.approach_track_1_combo,
            self.approach_track_2_combo,
            self.takeoff_track_1_combo,
            self.takeoff_track_2_combo,
            self.annex14_strip_source_combo,
        ]:
            combo.currentIndexChanged.connect(self.inputChanged.emit)
        self.declared_distance_mode_combo.currentIndexChanged.connect(
            self._update_declared_distance_mode
        )
        self.declared_distance_mode_combo.currentIndexChanged.connect(
            self.inputChanged.emit
        )
        for line_edit in [
            self.annex14_strip_width_le,
            self.annex14_strip_extension_le,
            *[
                widgets[key]
                for widgets in self._annex14_end_widgets.values()
                for key in (
                    "maximum_certificated_takeoff_mass_kg",
                    "governing_approach_surface_slope_percent",
                    "obstacle_clearance_height_m",
                )
            ],
        ]:
            line_edit.textChanged.connect(self.inputChanged.emit)
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

    def get_input_data(self) -> Dict[str, Any]:
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
            "thr_displaced_1": self.thr_displaced_1_le.text(),
            "thr_displaced_2": self.thr_displaced_2_le.text(),
            "thr_pre_area_1": self.thr_pre_area_1_le.text(),
            "thr_pre_area_2": self.thr_pre_area_2_le.text(),
            "starter_extension_length_1": self.starter_extension_length_1_le.text(),
            "starter_extension_length_2": self.starter_extension_length_2_le.text(),
            "starter_extension_width_1": self.starter_extension_width_1_le.text(),
            "starter_extension_width_2": self.starter_extension_width_2_le.text(),
            "starter_extension_shoulder_1": self.starter_extension_shoulder_1_le.text(),
            "starter_extension_shoulder_2": self.starter_extension_shoulder_2_le.text(),
            "starter_extension_outer_elev_1": self.starter_extension_outer_elev_1_le.text(),
            "starter_extension_outer_elev_2": self.starter_extension_outer_elev_2_le.text(),
            "width": self.width_le.text(),
            "shoulder": self.shoulder_le.text(),
            "clearway1_len": self.clearway1_len_le.text(),
            "clearway2_len": self.clearway2_len_le.text(),
            "stopway1_len": self.stopway1_len_le.text(),
            "stopway2_len": self.stopway2_len_le.text(),
            "declared_distance_mode": self.declared_distance_mode_combo.currentData(),
            "tora_override_1": self.tora_override_1_le.text(),
            "tora_override_2": self.tora_override_2_le.text(),
            "toda_override_1": self.toda_override_1_le.text(),
            "toda_override_2": self.toda_override_2_le.text(),
            "asda_override_1": self.asda_override_1_le.text(),
            "asda_override_2": self.asda_override_2_le.text(),
            "lda_override_1": self.lda_override_1_le.text(),
            "lda_override_2": self.lda_override_2_le.text(),
            "takeoff_available_1": self.takeoff_available_1_cb.isChecked(),
            "takeoff_available_2": self.takeoff_available_2_cb.isChecked(),
            "landing_available_1": self.landing_available_1_cb.isChecked(),
            "landing_available_2": self.landing_available_2_cb.isChecked(),
            "lahso_applied_1": self.lahso_applied_1_cb.isChecked(),
            "lahso_applied_2": self.lahso_applied_2_cb.isChecked(),
            "cap168_wide_runway": self.cap168_wide_runway_cb.isChecked(),
            "arc_num": self.arc_num_combo.currentData(),
            "arc_let": self.arc_let_combo.currentData(),
            "adg": self.adg_combo.currentData(),
            "surface_category": self.surface_category_combo.currentText(),
            "surface_material": self.surface_material_combo.currentText(),
            "type1": self.type1_combo.currentText(),
            "type2": self.type2_combo.currentText(),
            "approach_track_type_1": self.approach_track_1_combo.currentData(),
            "approach_track_type_2": self.approach_track_2_combo.currentData(),
            "approach_track_wkt_1": self.approach_track_wkt_1_le.text().strip(),
            "approach_track_wkt_2": self.approach_track_wkt_2_le.text().strip(),
            "takeoff_track_type_1": self.takeoff_track_1_combo.currentData(),
            "takeoff_track_type_2": self.takeoff_track_2_combo.currentData(),
            "takeoff_track_wkt_1": self.takeoff_track_wkt_1_le.text().strip(),
            "takeoff_track_wkt_2": self.takeoff_track_wkt_2_le.text().strip(),
            "annex14_modernised": self._annex14_modernised_input_data(),
        }

    def set_input_data(self, data: Dict[str, Any]):
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
            self.runway_end_elev_1_le.setText(data.get("runway_end_elev_1", ""))
            self.runway_end_elev_2_le.setText(data.get("runway_end_elev_2", ""))
            self.threshold_elev_1_le.setText(data.get("threshold_elev_1", ""))
            self.threshold_elev_2_le.setText(data.get("threshold_elev_2", ""))
            self.thr_displaced_1_le.setText(data.get("thr_displaced_1", ""))
            self.thr_displaced_2_le.setText(data.get("thr_displaced_2", ""))
            self.thr_pre_area_1_le.setText(data.get("thr_pre_area_1", ""))
            self.thr_pre_area_2_le.setText(data.get("thr_pre_area_2", ""))
            self.starter_extension_length_1_le.setText(data.get("starter_extension_length_1", ""))
            self.starter_extension_length_2_le.setText(data.get("starter_extension_length_2", ""))
            self.starter_extension_width_1_le.setText(data.get("starter_extension_width_1", ""))
            self.starter_extension_width_2_le.setText(data.get("starter_extension_width_2", ""))
            self.starter_extension_shoulder_1_le.setText(data.get("starter_extension_shoulder_1", ""))
            self.starter_extension_shoulder_2_le.setText(data.get("starter_extension_shoulder_2", ""))
            self.starter_extension_outer_elev_1_le.setText(data.get("starter_extension_outer_elev_1", ""))
            self.starter_extension_outer_elev_2_le.setText(data.get("starter_extension_outer_elev_2", ""))
            self.width_le.setText(data.get("width", ""))
            self.shoulder_le.setText(data.get("shoulder", ""))
            self.clearway1_len_le.setText(data.get("clearway1_len", ""))
            self.clearway2_len_le.setText(data.get("clearway2_len", ""))
            self.stopway1_len_le.setText(data.get("stopway1_len", ""))
            self.stopway2_len_le.setText(data.get("stopway2_len", ""))
            mode = data.get("declared_distance_mode")
            if mode not in {"calculated", "published"}:
                mode = "published" if any(
                    data.get(key)
                    for key in (
                        "tora_override_1", "tora_override_2",
                        "toda_override_1", "toda_override_2",
                        "asda_override_1", "asda_override_2",
                        "lda_override_1", "lda_override_2",
                    )
                ) else "calculated"
            self._set_combo_data(self.declared_distance_mode_combo, mode)
            self.tora_override_1_le.setText(data.get("tora_override_1", ""))
            self.tora_override_2_le.setText(data.get("tora_override_2", ""))
            self.toda_override_1_le.setText(data.get("toda_override_1", ""))
            self.toda_override_2_le.setText(data.get("toda_override_2", ""))
            self.asda_override_1_le.setText(data.get("asda_override_1", ""))
            self.asda_override_2_le.setText(data.get("asda_override_2", ""))
            self.lda_override_1_le.setText(data.get("lda_override_1", ""))
            self.lda_override_2_le.setText(data.get("lda_override_2", ""))
            self.takeoff_available_1_cb.setChecked(self._bool_from_saved_value(data.get("takeoff_available_1", True)))
            self.takeoff_available_2_cb.setChecked(self._bool_from_saved_value(data.get("takeoff_available_2", True)))
            self.landing_available_1_cb.setChecked(self._bool_from_saved_value(data.get("landing_available_1", True)))
            self.landing_available_2_cb.setChecked(self._bool_from_saved_value(data.get("landing_available_2", True)))
            self.lahso_applied_1_cb.setChecked(self._bool_from_saved_value(data.get("lahso_applied_1", False)))
            self.lahso_applied_2_cb.setChecked(self._bool_from_saved_value(data.get("lahso_applied_2", False)))
            self.cap168_wide_runway_cb.setChecked(
                self._bool_from_saved_value(data.get("cap168_wide_runway", False))
            )
            self._set_combo_data(self.arc_num_combo, data.get("arc_num", ""))
            self._set_combo_data(self.arc_let_combo, data.get("arc_let", ""))
            self._set_combo_data(self.adg_combo, data.get("adg", ""))
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
            self._set_combo_data(self.approach_track_1_combo, data.get("approach_track_type_1", "aligned"))
            self._set_combo_data(self.approach_track_2_combo, data.get("approach_track_type_2", "aligned"))
            self.approach_track_wkt_1_le.setText(data.get("approach_track_wkt_1", ""))
            self.approach_track_wkt_2_le.setText(data.get("approach_track_wkt_2", ""))
            self._set_combo_data(self.takeoff_track_1_combo, data.get("takeoff_track_type_1", "aligned"))
            self._set_combo_data(self.takeoff_track_2_combo, data.get("takeoff_track_type_2", "aligned"))
            self.takeoff_track_wkt_1_le.setText(data.get("takeoff_track_wkt_1", ""))
            self.takeoff_track_wkt_2_le.setText(data.get("takeoff_track_wkt_2", ""))
            self._set_annex14_modernised_input_data(
                data.get("annex14_modernised")
            )
        finally:
            for widget in widgets_to_block:
                widget.blockSignals(False)
            self._update_threshold_dependencies()
            self._update_starter_extension_dependencies()
            self._update_declared_distance_mode()
            self.inputChanged.emit()

    def update_display_labels(self, results: Dict[str, str]):
        self.rec_desig_hdr_lbl.setText(results.get("reciprocal_desig_full", NA_PLACEHOLDER))
        self.rwy_name_lbl.setText(results.get("runway_name", WIDGET_MISSING_MSG))
        self.dist_lbl.setText(results.get("distance", WIDGET_MISSING_MSG))
        self.azim_lbl.setText(results.get("azimuth", WIDGET_MISSING_MSG))
        if getattr(self, "_approach_type_in_threshold_grid", False):
            self.type1_lbl.setText("Approach Type:")
            self.type1_combo.setToolTip(results.get("type1_label_text", "Primary end approach type"))
            self.type2_combo.setToolTip(results.get("type2_label_text", "Reciprocal end approach type"))
        else:
            self.type1_lbl.setText(results.get("type1_label_text", "(Primary End) Type:"))
            self.type2_lbl.setText(results.get("type2_label_text", "(Reciprocal End) Type:"))
        arc_number = (self.arc_num_combo.currentData() or "").strip()
        arc_letter = (self.arc_let_combo.currentData() or "").strip()
        arc_code = f"{arc_number}{arc_letter}" if (arc_number or arc_letter) else "--"
        adg = (self.adg_combo.currentData() or "").strip() or "--"
        self.header_summary_lbl.setText(
            f"ARC: {arc_code} | ADG: {adg} | Length: {self.dist_lbl.text()} | Azimuth: {self.azim_lbl.text()}"
        )
        self._update_declared_distance_placeholders()
        self._update_status_chip()

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
            self.starter_extension_length_1_le,
            self.starter_extension_length_2_le,
            self.starter_extension_width_1_le,
            self.starter_extension_width_2_le,
            self.starter_extension_shoulder_1_le,
            self.starter_extension_shoulder_2_le,
            self.starter_extension_outer_elev_1_le,
            self.starter_extension_outer_elev_2_le,
            self.width_le,
            self.shoulder_le,
            self.clearway1_len_le,
            self.clearway2_len_le,
            self.stopway1_len_le,
            self.stopway2_len_le,
            self.declared_distance_mode_combo,
            self.tora_override_1_le,
            self.tora_override_2_le,
            self.toda_override_1_le,
            self.toda_override_2_le,
            self.asda_override_1_le,
            self.asda_override_2_le,
            self.lda_override_1_le,
            self.lda_override_2_le,
            self.takeoff_available_1_cb,
            self.takeoff_available_2_cb,
            self.landing_available_1_cb,
            self.landing_available_2_cb,
            self.lahso_applied_1_cb,
            self.lahso_applied_2_cb,
            self.cap168_wide_runway_cb,
            self.arc_num_combo,
            self.arc_let_combo,
            self.adg_combo,
            self.surface_category_combo,
            self.surface_material_combo,
            self.type1_combo,
            self.type2_combo,
            self.approach_track_1_combo,
            self.approach_track_2_combo,
            self.approach_track_wkt_1_le,
            self.approach_track_wkt_2_le,
            self.takeoff_track_1_combo,
            self.takeoff_track_2_combo,
            self.takeoff_track_wkt_1_le,
            self.takeoff_track_wkt_2_le,
            self.annex14_confirmed_cb,
            self.annex14_strip_source_combo,
            self.annex14_strip_width_le,
            self.annex14_strip_extension_le,
            self.annex14_code_f_no_digital_cb,
            *[
                widget
                for widgets in self._annex14_end_widgets.values()
                for widget in (
                    *widgets["operations"].values(),
                    widgets["maximum_certificated_takeoff_mass_kg"],
                    widgets["governing_approach_surface_slope_percent"],
                    widgets["obstacle_clearance_height_m"],
                    widgets["specific_oes_required"],
                )
            ],
        ]

    def _handle_surface_category_changed(self):
        self._refresh_surface_material_options(self.surface_category_combo.currentText())
        self.inputChanged.emit()

    def _style_section_groupbox(self, groupbox: QtWidgets.QGroupBox) -> None:
        """Style runway detail sections as dividers rather than nested boxes."""
        if groupbox is None:
            return
        groupbox.setStyleSheet(
            """
            QGroupBox {
                border: none;
                border-top: 1px solid #e1e4e8;
                margin-top: 10px;
                padding-top: 10px;
                background: transparent;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 0;
                padding: 0 6px 0 0;
                font-weight: 600;
                color: #202124;
                background: #ffffff;
            }
            """
        )

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
        if getattr(self, "_last_status_chip_text", None) == status:
            return
        self._last_status_chip_text = status
        self.status_chip_lbl.setText(status)
        if status == "Ready":
            self.status_chip_lbl.setStyleSheet(
                "QLabel { background: #eaf6ed; color: #1f6b32; border: 1px solid #c7e7cf; border-radius: 9px; padding: 3px 9px; font-size: 10px; font-weight: 600; }"
            )
        elif status == "Needs attention":
            self.status_chip_lbl.setStyleSheet(
                "QLabel { background: #fff5e6; color: #8a5200; border: 1px solid #f0d6a8; border-radius: 9px; padding: 3px 9px; font-size: 10px; font-weight: 600; }"
            )
        else:
            self.status_chip_lbl.setStyleSheet(
                "QLabel { background: #f4f4f4; color: #555; border: 1px solid #d6d6d6; border-radius: 9px; padding: 3px 9px; font-size: 10px; font-weight: 600; }"
            )

    def _sync_height_constraint(self) -> None:
        """Let the card hug visible content without clipping styled controls."""
        self.setMinimumHeight(0)
        self.setMaximumHeight(16777215)
        self.updateGeometry()

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
