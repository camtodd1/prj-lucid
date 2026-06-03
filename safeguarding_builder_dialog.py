# -*- coding: utf-8 -*-
# safeguarding_builder_dialog.py
"""
Dialog class for the Safeguarding Builder QGIS plugin.
Handles user input for airport, ARP, runway, and CNS data.
Dynamically adds/removes runway groups using a helper class
and performs real-time calculations for display.
CNS coordinates are assumed to be in the current Project CRS.
"""

import csv
import math
import os
import re
from typing import List, Optional, Dict, Any, Tuple
from html import unescape
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

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
    from .dialog.dialog_constants import (
        CALC_PLACEHOLDER,
        NA_PLACEHOLDER,
        ENTER_COORDS_MSG,
        INVALID_COORDS_MSG,
        CALC_ERROR_MSG,
        DEFAULT_RUNWAY_SURFACE_CATEGORY,
        DEFAULT_RUNWAY_SURFACE_MATERIAL,
        SAME_POINT_MSG,
        NEAR_POINTS_MSG,
        WIDGET_MISSING_MSG,
        DIALOG_LOG_TAG,
        OUTPUT_FORMATS,
        RUNWAY_SURFACE_MATERIALS,
    )
    from .dialog.runway_group import RunwayWidgetGroup
    from .dialog.output_options import OutputOptionsMixin
    from .dialog.cns_table import CnsTableMixin
    from .dialog.agl_options import AglOptionsMixin
    from .dialog.persistence import PersistenceMixin
except ImportError:
    from dialog.dialog_constants import (  # type: ignore
        CALC_PLACEHOLDER,
        NA_PLACEHOLDER,
        ENTER_COORDS_MSG,
        INVALID_COORDS_MSG,
        CALC_ERROR_MSG,
        DEFAULT_RUNWAY_SURFACE_CATEGORY,
        DEFAULT_RUNWAY_SURFACE_MATERIAL,
        SAME_POINT_MSG,
        NEAR_POINTS_MSG,
        WIDGET_MISSING_MSG,
        DIALOG_LOG_TAG,
        OUTPUT_FORMATS,
        RUNWAY_SURFACE_MATERIALS,
    )
    from dialog.runway_group import RunwayWidgetGroup  # type: ignore
    from dialog.output_options import OutputOptionsMixin  # type: ignore
    from dialog.cns_table import CnsTableMixin  # type: ignore
    from dialog.agl_options import AglOptionsMixin  # type: ignore
    from dialog.persistence import PersistenceMixin  # type: ignore

# Load the UI class from the .ui file
FORM_CLASS, _ = uic.loadUiType(os.path.join(os.path.dirname(__file__), "safeguarding_builder_dialog_base.ui"))


# =========================================================================
# == Main Dialog Class
# =========================================================================
class SafeguardingBuilderDialog(
    OutputOptionsMixin,
    CnsTableMixin,
    AglOptionsMixin,
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
        self._processing_status_active = False
        self._processing_progress_bar: Optional[QtWidgets.QProgressBar] = None
        self._airport_lookup_cache: Dict[str, Dict[str, str]] = {}
        self._airport_iata_cache: Dict[str, Dict[str, str]] = {}
        self._airport_dataset_loaded = False
        self._airport_lookup_pending_code: str = ""
        self._airport_lookup_pending_source = "icao"
        self._airport_code_syncing = False
        self._airport_resolved_signature = ""
        self._airport_resolved_summary = ""
        self._airport_lookup_state = "idle"
        self._airport_lookup_status_message = ""
        self._airport_lookup_status_signature = ""
        self._airport_lookup_timer = QtCore.QTimer(self)
        self._airport_lookup_timer.setSingleShot(True)
        self._airport_lookup_timer.timeout.connect(self._resolve_airport_lookup)
        self._style_dialog_header()

        # --- Scroll Area Setup ---
        scroll_area = self.findChild(QtWidgets.QScrollArea, "scrollArea_runways")
        if scroll_area:
            scroll_area.setWidgetResizable(True)
            scroll_content_widget = scroll_area.widget()
            if scroll_content_widget:
                layout = scroll_content_widget.layout()
                if layout is None:
                    layout = QtWidgets.QVBoxLayout(scroll_content_widget)
                    scroll_content_widget.setLayout(layout)
                if isinstance(layout, QtWidgets.QVBoxLayout):
                    layout.setContentsMargins(8, 8, 8, 8)
                    layout.setSpacing(8)
                    layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignTop)
                    scroll_content_widget.setContentsMargins(0, 0, 0, 0)
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

        self._setup_processing_status_widgets()

        add_runway_button = self.findChild(QtWidgets.QPushButton, "pushButton_add_runway")
        if self.scroll_area_layout is None:
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
        self.coord_validator.setNotation(QtGui.QDoubleValidator.Notation.StandardNotation)
        self.numeric_validator = QtGui.QDoubleValidator()
        self.numeric_validator.setNotation(QtGui.QDoubleValidator.Notation.StandardNotation)

        self._setup_arp_validators(self.coord_validator, self.numeric_validator)
        self._style_airport_tab()
        self._connect_global_controls()
        self._setup_dialog_status_connections()

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
        self._setup_agl_options_ui()

        self._setup_output_options_ui_connections()
        self._setup_agl_options_ui_connections()

        if self.scroll_area_layout is not None:
            self.add_runway_group()  # Add the first group
        else:
            QgsMessageLog.logMessage(
                "Warning: Could not add initial runway group (layout missing).",
                DIALOG_LOG_TAG,
                level=Qgis.Warning,
            )

        QtCore.QTimer.singleShot(0, self._update_dialog_height)
        QtCore.QTimer.singleShot(0, self.update_dialog_status)

    def _setup_processing_status_widgets(self) -> None:
        """Add a compact indeterminate progress indicator to the dialog footer."""
        footer_layout = getattr(self, "horizontalLayout_dialogFooter", None)
        if footer_layout is None:
            return
        progress_bar = QtWidgets.QProgressBar(self)
        progress_bar.setObjectName("progressBar_processing")
        progress_bar.setRange(0, 0)
        progress_bar.setTextVisible(False)
        progress_bar.setFixedWidth(180)
        progress_bar.setVisible(False)
        footer_layout.insertWidget(1, progress_bar)
        self._processing_progress_bar = progress_bar

    def set_processing_status(self, message: str) -> None:
        """Show brief generation progress feedback while synchronous processing runs."""
        self._processing_status_active = True
        if hasattr(self, "label_footer_status"):
            self.label_footer_status.setText(message)
        if self._processing_progress_bar is not None:
            self._processing_progress_bar.setVisible(True)
        generate_button = getattr(
            self,
            "pushButton_Generate",
            self.findChild(QtWidgets.QPushButton, "pushButton_Generate"),
        )
        if generate_button:
            generate_button.setEnabled(False)
            generate_button.setText("Generating...")

    def clear_processing_status(self) -> None:
        """Restore normal footer status after generation finishes or aborts."""
        self._processing_status_active = False
        if self._processing_progress_bar is not None:
            self._processing_progress_bar.setVisible(False)
        generate_button = getattr(
            self,
            "pushButton_Generate",
            self.findChild(QtWidgets.QPushButton, "pushButton_Generate"),
        )
        if generate_button:
            generate_button.setEnabled(True)
            generate_button.setText("Generate Airport Layers")
        self.update_dialog_status()

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
            "lineEdit_arp_easting": "455000.00",
            "lineEdit_arp_northing": "5772000.00",
            "lineEdit_arp_elevation": "150.0",
            "lineEdit_met_easting": "455100.00",
            "lineEdit_met_northing": "5772100.00",
            "lineEdit_met_elevation": "150.0",
        }
        for name, validator in widgets_to_validate:
            widget = getattr(self, name, self.findChild(QtWidgets.QLineEdit, name))
            if widget:
                widget.setValidator(validator)
                widget.setToolTip(tooltips.get(name, ""))
                widget.setPlaceholderText(placeholders.get(name, ""))
                widget.setMaximumWidth(160)
            else:
                QgsMessageLog.logMessage(
                    f"Warning: QLineEdit '{name}' not found.",
                    DIALOG_LOG_TAG,
                    level=Qgis.Warning,
                )

        airport_name = getattr(
            self,
            "lineEdit_airport_name",
            self.findChild(QtWidgets.QLineEdit, "lineEdit_airport_name"),
        )
        if airport_name:
            airport_name.setMaximumWidth(220)
            airport_name.setMaxLength(4)

        iata_code = getattr(
            self,
            "lineEdit_iata_code",
            self.findChild(QtWidgets.QLineEdit, "lineEdit_iata_code"),
        )
        if iata_code:
            iata_code.setMaximumWidth(120)
            iata_code.setMaxLength(3)

    def _style_airport_tab(self) -> None:
        """Apply card-like styling and clearer hierarchy to the opening airport tab."""
        airport_layout = getattr(self, "verticalLayout_airportTab", None)
        if isinstance(airport_layout, QtWidgets.QVBoxLayout):
            airport_layout.setContentsMargins(8, 8, 8, 8)
            airport_layout.setSpacing(8)
            airport_layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignTop)

        airport_name_label = getattr(
            self,
            "label_airport_name",
            self.findChild(QtWidgets.QLabel, "label_airport_name"),
        )
        if airport_name_label:
            airport_name_label.setText("ICAO *")
            airport_name_label.setToolTip("Required for runway generation. Enter ICAO or use IATA to look it up.")
            airport_name_label.setStyleSheet("font-weight: 600;")

        iata_label = getattr(
            self,
            "label_iata_code",
            self.findChild(QtWidgets.QLabel, "label_iata_code"),
        )
        if iata_label:
            iata_label.setText("IATA")
            iata_label.setToolTip("Optional. Entering IATA can populate ICAO when a match is found.")
            iata_label.setStyleSheet("font-weight: 600; color: #555555;")

        airport_name_input = getattr(
            self,
            "lineEdit_airport_name",
            self.findChild(QtWidgets.QLineEdit, "lineEdit_airport_name"),
        )
        if airport_name_input:
            airport_name_input.setToolTip("Enter the ICAO airport code.")
            airport_name_input.setPlaceholderText("e.g., YPAD")
            airport_name_input.setMaximumWidth(150)
            airport_name_input.setMinimumWidth(110)

        iata_input = getattr(
            self,
            "lineEdit_iata_code",
            self.findChild(QtWidgets.QLineEdit, "lineEdit_iata_code"),
        )
        if iata_input:
            iata_input.setToolTip("Enter an IATA airport code to look up and populate ICAO.")
            iata_input.setPlaceholderText("e.g., ADL")
            iata_input.setMaximumWidth(120)
            iata_input.setMinimumWidth(90)

        airport_status = getattr(
            self,
            "label_airport_status",
            self.findChild(QtWidgets.QLabel, "label_airport_status"),
        )
        if airport_status:
            airport_status.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter)
            airport_status.setMinimumHeight(26)
            airport_status.setMaximumHeight(28)
            airport_status.setStyleSheet(
                "QLabel { background: #f4f4f4; color: #444; border: 1px solid #d2d2d2; "
                "border-radius: 10px; padding: 4px 10px; font-weight: 600; }"
            )

        airport_lookup = getattr(
            self,
            "label_airport_lookup",
            self.findChild(QtWidgets.QLabel, "label_airport_lookup"),
        )
        if airport_lookup:
            airport_lookup.setStyleSheet("color: #666666; font-size: 11px;")
            airport_lookup.setText("")

        coord_info = getattr(
            self,
            "coord_info",
            self.findChild(QtWidgets.QLabel, "coord_info"),
        )
        if coord_info:
            coord_info.setStyleSheet(
                "QLabel { color: #4b4b4b; font-size: 11px; margin-left: 10px; }"
            )

        airport_identity_frame = getattr(
            self,
            "frame_airport_identity",
            self.findChild(QtWidgets.QFrame, "frame_airport_identity"),
        )
        if airport_identity_frame:
            airport_identity_frame.setStyleSheet(
                """
                QFrame#frame_airport_identity {
                    border: 1px solid #dcdcdc;
                    border-radius: 4px;
                    background: #ffffff;
                }
                """
            )
            airport_identity_frame.setSizePolicy(
                QtWidgets.QSizePolicy.Policy.Expanding,
                QtWidgets.QSizePolicy.Policy.Fixed,
            )
            airport_identity_frame.setMaximumHeight(16777215)
            airport_identity_frame.adjustSize()
            airport_identity_frame.setMaximumHeight(airport_identity_frame.sizeHint().height())

        airport_card_style = """
        QGroupBox {
            border: 1px solid #dcdcdc;
            border-radius: 4px;
            margin-top: 12px;
            padding: 8px;
            background: #ffffff;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            left: 8px;
            padding: 0 4px;
            font-weight: 600;
        }
        """
        for name in ["groupBox_ARP", "groupBox_MET"]:
            group = getattr(self, name, self.findChild(QtWidgets.QGroupBox, name))
            if group:
                group.setFlat(True)
                if name == "groupBox_ARP":
                    group.setTitle("Aerodrome Reference Point (ARP)")
                    group.setStyleSheet(airport_card_style)
                else:
                    group.setTitle("Meteorological Instrument Station (optional)")
                    group.setStyleSheet(
                        """
                        QGroupBox {
                            border: 1px solid #e5e5e5;
                            border-radius: 4px;
                            margin-top: 12px;
                            padding: 8px;
                            background: #fafafa;
                        }
                        QGroupBox::title {
                            subcontrol-origin: margin;
                            left: 8px;
                            padding: 0 4px;
                            font-weight: 500;
                            color: #666666;
                        }
                        """
                    )
                group.setSizePolicy(
                    QtWidgets.QSizePolicy.Policy.Expanding,
                    QtWidgets.QSizePolicy.Policy.Fixed,
                )
        for name in ["label_arp_status", "label_met_status"]:
            label = getattr(self, name, self.findChild(QtWidgets.QLabel, name))
            if label:
                label.setMinimumHeight(24)
                label.setStyleSheet(
                    "QLabel { background: #f4f4f4; color: #555; border: 1px solid #d6d6d6; "
                    "border-radius: 9px; padding: 3px 9px; font-size: 10px; font-weight: 600; }"
                )

    def _style_dialog_header(self) -> None:
        """Tighten the top utility header into a compact visual band."""
        header_frame = getattr(
            self,
            "frame_dialog_header",
            self.findChild(QtWidgets.QFrame, "frame_dialog_header"),
        )
        if header_frame:
            header_frame.setStyleSheet(
                "QFrame#frame_dialog_header { background: #fcfcfc; border-bottom: 1px solid #dedede; }"
            )

        heading_label = getattr(
            self,
            "label_dialog_heading",
            self.findChild(QtWidgets.QLabel, "label_dialog_heading"),
        )
        if heading_label:
            heading_label.setStyleSheet(
                "QLabel { color: #232323; font-size: 20px; font-weight: 700; padding-bottom: 2px; }"
            )

        header_info = getattr(
            self,
            "coord_info",
            self.findChild(QtWidgets.QLabel, "coord_info"),
        )
        if header_info:
            header_info.setWordWrap(False)
            header_info.setTextInteractionFlags(QtCore.Qt.TextInteractionFlag.TextBrowserInteraction)
            header_info.setStyleSheet(
                "QLabel { color: #4b4b4b; font-size: 11px; margin-left: 10px; }"
            )
            header_info.setSizePolicy(
                QtWidgets.QSizePolicy.Policy.Expanding,
                QtWidgets.QSizePolicy.Policy.Fixed,
            )
            header_info.setMaximumHeight(header_info.sizeHint().height())
            header_info.setMinimumHeight(header_info.sizeHint().height())

        crs_prefix = getattr(
            self,
            "label_crs_prefix",
            self.findChild(QtWidgets.QLabel, "label_crs_prefix"),
        )
        if crs_prefix:
            crs_prefix.setStyleSheet("QLabel { color: #333333; font-size: 14px; font-weight: 700; }")

        crs_field = getattr(
            self,
            "lineEdit_airport_crs",
            self.findChild(QtWidgets.QLineEdit, "lineEdit_airport_crs"),
        )
        if crs_field:
            crs_field.setReadOnly(True)
            crs_field.setClearButtonEnabled(False)
            crs_field.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter)
            crs_field.setPlaceholderText("")
            crs_field.setMaximumWidth(172)
            crs_field.setMinimumWidth(172)
            crs_field.setStyleSheet(
                "QLineEdit { background: #ffffff; color: #333333; border: 1px solid #c8c8c8; "
                "border-radius: 8px; padding: 4px 10px; font-size: 13px; font-weight: 600; }"
                "QLineEdit:read-only { background: #ffffff; color: #333333; }"
            )
            crs_field.setText("")
            crs_field.setToolTip("Suggested projected CRS derived from the airport latitude/longitude.")

        header_layout = getattr(
            self,
            "horizontalLayout_dialogHeader",
            None,
        )
        if isinstance(header_layout, QtWidgets.QHBoxLayout):
            header_layout.setContentsMargins(0, 2, 0, 6)
            header_layout.setSpacing(8)

        for button_name in ["pushButton_load_data", "pushButton_save_data", "pushButton_clear_all"]:
            button = getattr(self, button_name, self.findChild(QtWidgets.QPushButton, button_name))
            if button:
                button.setMinimumHeight(30)
                button.setMaximumHeight(30)
                button.setMinimumWidth(100)

        tab_widget = getattr(self, "tabWidget_workflow", self.findChild(QtWidgets.QTabWidget, "tabWidget_workflow"))
        if tab_widget:
            tab_widget.setStyleSheet(
                """
                QTabWidget::pane {
                    border: 1px solid #bcbcbc;
                    top: -1px;
                }
                QTabBar::tab {
                    min-width: 82px;
                    padding: 5px 10px;
                    margin-right: 1px;
                    background: #eeeeee;
                    border: 1px solid #bcbcbc;
                    border-bottom: none;
                    border-top-left-radius: 3px;
                    border-top-right-radius: 3px;
                }
                QTabBar::tab:selected {
                    background: #ffffff;
                    font-weight: 600;
                }
                """
            )


    def _connect_global_controls(self):
        """Connects signals for global widgets."""
        airport_name_le = getattr(
            self,
            "lineEdit_airport_name",
            self.findChild(QtWidgets.QLineEdit, "lineEdit_airport_name"),
        )
        iata_code_le = getattr(
            self,
            "lineEdit_iata_code",
            self.findChild(QtWidgets.QLineEdit, "lineEdit_iata_code"),
        )
        add_runway_button = getattr(
            self,
            "pushButton_add_runway",
            self.findChild(QtWidgets.QPushButton, "pushButton_add_runway"),
        )

        if airport_name_le:
            airport_name_le.textChanged.connect(self._handle_icao_changed)
            airport_name_le.textChanged.connect(self.update_all_runway_calculations)
            airport_name_le.textChanged.connect(self.update_dialog_status)
        else:
            QgsMessageLog.logMessage(
                "Warning: 'lineEdit_airport_name' not found.",
                DIALOG_LOG_TAG,
                level=Qgis.Warning,
            )

        if iata_code_le:
            iata_code_le.textChanged.connect(self._handle_iata_changed)
            iata_code_le.textChanged.connect(self.update_dialog_status)

        if add_runway_button and self.scroll_area_layout is not None:
            add_runway_button.clicked.connect(self.add_runway_group)
        elif not add_runway_button:
            QgsMessageLog.logMessage(
                "Warning: 'pushButton_add_runway' not found.",
                DIALOG_LOG_TAG,
                level=Qgis.Warning,
            )
        elif self.scroll_area_layout is None:
            QgsMessageLog.logMessage(
                "Warning: 'pushButton_add_runway' not connected (layout missing).",
                DIALOG_LOG_TAG,
                level=Qgis.Warning,
            )

    def _handle_icao_changed(self, text: str) -> None:
        """Normalize ICAO input and queue a metadata lookup."""
        if self._airport_code_syncing:
            return
        self._invalidate_airport_resolution()
        icao_input = getattr(
            self,
            "lineEdit_airport_name",
            self.findChild(QtWidgets.QLineEdit, "lineEdit_airport_name"),
        )
        normalized = text.strip().upper()[:4]
        if icao_input and text != normalized:
            cursor_pos = min(icao_input.cursorPosition(), len(normalized))
            blocker = QtCore.QSignalBlocker(icao_input)
            icao_input.setText(normalized)
            icao_input.setCursorPosition(cursor_pos)
            del blocker
        self._queue_airport_lookup(normalized, source="icao")

    def _handle_iata_changed(self, text: str) -> None:
        """Normalize IATA input and queue a reverse lookup."""
        if self._airport_code_syncing:
            return
        self._invalidate_airport_resolution()
        iata_input = getattr(
            self,
            "lineEdit_iata_code",
            self.findChild(QtWidgets.QLineEdit, "lineEdit_iata_code"),
        )
        normalized = text.strip().upper()[:3]
        if iata_input and text != normalized:
            cursor_pos = min(iata_input.cursorPosition(), len(normalized))
            blocker = QtCore.QSignalBlocker(iata_input)
            iata_input.setText(normalized)
            iata_input.setCursorPosition(cursor_pos)
            del blocker
        self._queue_airport_lookup(normalized, source="iata")

    def _invalidate_airport_resolution(self) -> None:
        """Clear resolved airport state when the user edits either code."""
        self._airport_resolved_signature = ""
        self._airport_resolved_summary = ""
        self._airport_lookup_state = "idle"
        self._airport_lookup_status_message = ""
        self._airport_lookup_status_signature = ""
        self._update_airport_crs_display(None)

    def _queue_airport_lookup(self, code: Optional[str] = None, source: str = "icao") -> None:
        """Debounce airport metadata lookup so typing does not spam network calls."""
        airport_lookup = getattr(
            self,
            "label_airport_lookup",
            self.findChild(QtWidgets.QLabel, "label_airport_lookup"),
        )
        if airport_lookup is None:
            return

        source = "iata" if source == "iata" else "icao"
        if source == "iata":
            raw_code = code if code is not None else self.lineEdit_iata_code.text()
            expected_length = 3
        else:
            raw_code = code if code is not None else self.lineEdit_airport_name.text()
            expected_length = 4
        airport_code = raw_code.strip().upper()
        if len(airport_code) != expected_length or not airport_code.isalnum():
            self._airport_lookup_timer.stop()
            self._airport_lookup_pending_code = ""
            self._airport_lookup_pending_source = source
            self._airport_lookup_state = "idle"
            self._airport_lookup_status_message = ""
            self._airport_lookup_status_signature = ""
            airport_lookup.setText("")
            airport_lookup.setToolTip("")
            self._update_airport_crs_display(None)
            return

        cached = (
            self._airport_iata_cache.get(airport_code)
            if source == "iata"
            else self._airport_lookup_cache.get(airport_code)
        )
        if cached:
            self._apply_airport_lookup_result(cached.get("icao", airport_code), cached)
            return

        self._airport_lookup_pending_code = airport_code
        self._airport_lookup_pending_source = source
        self._airport_lookup_state = "pending"
        self._airport_lookup_status_message = ""
        self._airport_lookup_status_signature = self._airport_signature(
            airport_code if source == "icao" else "",
            airport_code if source == "iata" else "",
        )
        airport_lookup.setText("Looking up airport name and location...")
        airport_lookup.setToolTip("Querying OurAirports open data for the airport record.")
        airport_status = getattr(
            self,
            "label_airport_status",
            self.findChild(QtWidgets.QLabel, "label_airport_status"),
        )
        if airport_status:
            airport_status.setText("Resolving airport...")
            airport_status.setStyleSheet(
                "QLabel { background: #fff5e6; color: #9a5b00; border: 1px solid #f0d6a8; "
                "border-radius: 10px; padding: 4px 10px; font-weight: 600; }"
            )
        self._airport_lookup_timer.start(350)

    def queue_current_airport_lookup(self) -> None:
        """Queue lookup for the currently loaded airport code pair."""
        icao = self.lineEdit_airport_name.text().strip().upper() if hasattr(self, "lineEdit_airport_name") else ""
        iata_widget = getattr(self, "lineEdit_iata_code", self.findChild(QtWidgets.QLineEdit, "lineEdit_iata_code"))
        iata = iata_widget.text().strip().upper() if iata_widget else ""
        if len(iata) == 3 and iata.isalnum():
            self._queue_airport_lookup(iata, source="iata")
        elif len(icao) == 4 and icao.isalnum():
            self._queue_airport_lookup(icao, source="icao")
        else:
            self.update_dialog_status()

    def _resolve_airport_lookup(self) -> None:
        """Fetch airport metadata for the current airport code if available."""
        airport_code = self._airport_lookup_pending_code
        source = self._airport_lookup_pending_source
        expected_length = 3 if source == "iata" else 4
        if len(airport_code) != expected_length:
            return

        lookup_error = ""
        try:
            result = (
                self._fetch_airport_metadata_by_iata(airport_code)
                if source == "iata"
                else self._fetch_airport_metadata(airport_code)
            )
        except Exception as exc:  # pragma: no cover - network is best-effort
            lookup_error = str(exc)
            QgsMessageLog.logMessage(
                f"Airport lookup failed for {airport_code}: {exc}",
                DIALOG_LOG_TAG,
                level=Qgis.Info,
            )
            result = None

        current_code = (
            self.lineEdit_iata_code.text().strip().upper()
            if source == "iata"
            else self.lineEdit_airport_name.text().strip().upper()
        )
        if current_code != airport_code:
            return

        airport_lookup = getattr(
            self,
            "label_airport_lookup",
            self.findChild(QtWidgets.QLabel, "label_airport_lookup"),
        )
        if airport_lookup is None:
            return

        if result:
            icao_code = result.get("icao", "").strip().upper()
            iata_code = result.get("iata", "").strip().upper()
            if icao_code:
                self._airport_lookup_cache[icao_code] = result
            if iata_code:
                self._airport_iata_cache[iata_code] = result
            self._airport_lookup_state = "resolved"
            self._airport_lookup_status_message = ""
            self._airport_lookup_status_signature = self._airport_signature(icao_code, iata_code)
            self._apply_airport_lookup_result(icao_code or airport_code, result)
        else:
            self._airport_lookup_state = "error" if lookup_error else "not_found"
            self._airport_lookup_status_signature = self._airport_signature(
                airport_code if source == "icao" else "",
                airport_code if source == "iata" else "",
            )
            self._airport_lookup_status_message = (
                f"Lookup unavailable for {airport_code}." if lookup_error else f"No airport match found for {airport_code}."
            )
            if lookup_error:
                airport_lookup.setText(f"Lookup unavailable for {airport_code}.")
                airport_lookup.setToolTip(f"OurAirports lookup failed: {lookup_error}")
            else:
                airport_lookup.setText(f"No airport match found for {airport_code}.")
                airport_lookup.setToolTip("No OurAirports record was found for the entered airport code.")
            airport_status = getattr(
                self,
                "label_airport_status",
                self.findChild(QtWidgets.QLabel, "label_airport_status"),
            )
            if airport_status:
                airport_status.setText("Airport not found")
                airport_status.setStyleSheet(
                    "QLabel { background: #fff5e6; color: #9a5b00; border: 1px solid #f0d6a8; "
                    "border-radius: 10px; padding: 4px 10px; font-weight: 600; }"
                )
            self._update_airport_crs_display(None)

    def _fetch_airport_metadata_by_iata(self, iata_code: str) -> Optional[Dict[str, str]]:
        """Fetch airport details by IATA code from the OurAirports open-data CSV."""
        cached = self._airport_iata_cache.get(iata_code)
        if cached:
            return cached
        self._load_airport_dataset()
        return self._airport_iata_cache.get(iata_code)

    def _fetch_airport_metadata(self, icao_code: str) -> Optional[Dict[str, str]]:
        """Fetch airport name/location details, preferring the OurAirports open-data CSV."""
        cached = self._airport_lookup_cache.get(icao_code)
        if cached:
            return cached

        try:
            self._load_airport_dataset()
            cached = self._airport_lookup_cache.get(icao_code)
            if cached:
                return cached
        except Exception as exc:  # pragma: no cover - network is best-effort
            QgsMessageLog.logMessage(
                f"Airport CSV lookup failed for {icao_code}, trying page fallback: {exc}",
                DIALOG_LOG_TAG,
                level=Qgis.Info,
            )

        url = f"https://ourairports.com/airports/{icao_code.lower()}/"
        request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urlopen(request, timeout=3) as response:
            raw_html = response.read().decode("utf-8", errors="replace")

        text = unescape(re.sub(r"<script.*?</script>|<style.*?</style>", " ", raw_html, flags=re.S | re.I))
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"\s+", " ", text).strip()

        name_match = re.search(r"Name\s+(.+?)\s+Location\s+(.+?)\s+IATA code", text, flags=re.I)
        if not name_match:
            return None

        name = name_match.group(1).strip()
        location = name_match.group(2).strip()
        location = re.sub(r"\s+,", ",", location)
        location = re.sub(r",\s+", ", ", location)

        coords_match = re.search(r"Coordinates\s+([-\d.]+),\s*([-\d.]+)", text, flags=re.I)
        coordinates = ""
        latitude = ""
        longitude = ""
        if coords_match:
            latitude = coords_match.group(1).strip()
            longitude = coords_match.group(2).strip()
            coordinates = f"{latitude}, {longitude}"

        iata_match = re.search(r"IATA code\s+([A-Z0-9]{3})", text, flags=re.I)
        iata = iata_match.group(1).strip().upper() if iata_match else ""

        return {
            "icao": icao_code,
            "iata": iata,
            "name": name,
            "location": location,
            "coordinates": coordinates,
            "latitude": latitude,
            "longitude": longitude,
        }

    def _load_airport_dataset(self) -> None:
        """Load airport metadata into ICAO and IATA lookup caches."""
        if self._airport_dataset_loaded:
            return

        url = "https://davidmegginson.github.io/ourairports-data/airports.csv"
        request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urlopen(request, timeout=5) as response:
            csv_text = response.read().decode("utf-8-sig", errors="replace")

        for row in csv.DictReader(csv_text.splitlines()):
            record = self._airport_record_from_csv_row(row)
            if not record:
                continue
            icao = record.get("icao", "")
            iata = record.get("iata", "")
            if icao and icao not in self._airport_lookup_cache:
                self._airport_lookup_cache[icao] = record
            if iata and iata not in self._airport_iata_cache:
                self._airport_iata_cache[iata] = record
        self._airport_dataset_loaded = True

    def _airport_record_from_csv_row(self, row: Dict[str, str]) -> Optional[Dict[str, str]]:
        """Convert an OurAirports CSV row into the compact metadata record used by the dialog."""
        ident = row.get("ident", "").strip().upper()
        gps_code = row.get("gps_code", "").strip().upper()
        iata = row.get("iata_code", "").strip().upper()
        icao = gps_code or (ident if len(ident) == 4 else "")
        if not icao and not iata:
            return None

        municipality = row.get("municipality", "").strip()
        iso_region = row.get("iso_region", "").strip()
        iso_country = row.get("iso_country", "").strip()
        region = self._format_airport_region(iso_region)
        location_parts = [part for part in [municipality, region, iso_country] if part]
        coordinates = ""
        latitude = row.get("latitude_deg", "").strip()
        longitude = row.get("longitude_deg", "").strip()
        if latitude and longitude:
            coordinates = f"{latitude}, {longitude}"

        return {
            "icao": icao,
            "iata": iata,
            "name": row.get("name", "").strip(),
            "location": ", ".join(location_parts),
            "coordinates": coordinates,
            "latitude": latitude,
            "longitude": longitude,
        }

    def _format_airport_region(self, iso_region: str) -> str:
        """Return a readable region name for common Australian airport records."""
        australian_regions = {
            "AU-ACT": "Australian Capital Territory",
            "AU-NSW": "New South Wales",
            "AU-NT": "Northern Territory",
            "AU-QLD": "Queensland",
            "AU-SA": "South Australia",
            "AU-TAS": "Tasmania",
            "AU-VIC": "Victoria",
            "AU-WA": "Western Australia",
        }
        if iso_region in australian_regions:
            return australian_regions[iso_region]
        if "-" in iso_region:
            return iso_region.split("-", 1)[1]
        return iso_region

    def _apply_airport_lookup_result(self, icao_code: str, result: Dict[str, str]) -> None:
        """Update the airport lookup label with fetched airport identity metadata."""
        airport_lookup = getattr(
            self,
            "label_airport_lookup",
            self.findChild(QtWidgets.QLabel, "label_airport_lookup"),
        )
        if airport_lookup is None:
            return

        icao = result.get("icao", icao_code).strip().upper()
        iata = result.get("iata", "").strip().upper()
        self._sync_airport_code_fields(icao, iata)

        name = result.get("name", "").strip()
        location = result.get("location", "").strip()
        coordinates = result.get("coordinates", "").strip()
        code_summary = " / ".join(part for part in [icao, iata] if part)
        summary = " - ".join(part for part in [code_summary, name] if part)
        self._airport_resolved_signature = self._airport_signature(icao, iata)
        self._airport_resolved_summary = summary
        airport_lookup.setText(location)
        tooltip_parts = []
        if icao:
            tooltip_parts.append(f"ICAO: {icao}")
        if iata:
            tooltip_parts.append(f"IATA: {iata}")
        if name:
            tooltip_parts.append(f"Name: {name}")
        if location:
            tooltip_parts.append(f"Location: {location}")
        if coordinates:
            tooltip_parts.append(f"Coordinates: {coordinates}")
        airport_lookup.setToolTip(" | ".join(tooltip_parts))
        self._update_airport_crs_display(result)
        airport_status = getattr(
            self,
            "label_airport_status",
            self.findChild(QtWidgets.QLabel, "label_airport_status"),
        )
        if airport_status:
            airport_status.setText(summary)
            airport_status.setStyleSheet(
                "QLabel { background: #eaf6ed; color: #1f6b32; border: 1px solid #c7e7cf; "
                "border-radius: 10px; padding: 4px 10px; font-weight: 600; }"
            )
            airport_status.setToolTip(" | ".join(tooltip_parts))
        self._resize_airport_identity_card()
        self.update_dialog_status()

    def _sync_airport_code_fields(self, icao_code: str, iata_code: str) -> None:
        """Populate paired airport code fields without triggering another lookup loop."""
        self._airport_code_syncing = True
        try:
            icao_input = getattr(
                self,
                "lineEdit_airport_name",
                self.findChild(QtWidgets.QLineEdit, "lineEdit_airport_name"),
            )
            iata_input = getattr(
                self,
                "lineEdit_iata_code",
                self.findChild(QtWidgets.QLineEdit, "lineEdit_iata_code"),
            )
            if icao_input and icao_code and icao_input.text().strip().upper() != icao_code:
                with QtCore.QSignalBlocker(icao_input):
                    icao_input.setText(icao_code)
            if iata_input and iata_code and iata_input.text().strip().upper() != iata_code:
                with QtCore.QSignalBlocker(iata_input):
                    iata_input.setText(iata_code)
        finally:
            self._airport_code_syncing = False

    def _airport_signature(self, icao_code: str, iata_code: str) -> str:
        """Build a stable signature for the current airport codes."""
        return f"{icao_code.strip().upper()}|{iata_code.strip().upper()}"

    def _update_airport_crs_display(self, result: Optional[Dict[str, str]] = None) -> None:
        """Suggest a projected EPSG CRS for the airport location."""
        crs_field = getattr(
            self,
            "lineEdit_airport_crs",
            self.findChild(QtWidgets.QLineEdit, "lineEdit_airport_crs"),
        )
        if crs_field is None:
            return

        latitude = None
        longitude = None
        if result:
            lat_raw = result.get("latitude", "").strip()
            lon_raw = result.get("longitude", "").strip()
            if lat_raw and lon_raw:
                try:
                    latitude = float(lat_raw)
                    longitude = float(lon_raw)
                except ValueError:
                    latitude = None
                    longitude = None
            elif result.get("coordinates", "").strip():
                coords = result.get("coordinates", "").split(",")
                if len(coords) == 2:
                    try:
                        latitude = float(coords[0].strip())
                        longitude = float(coords[1].strip())
                    except ValueError:
                        latitude = None
                        longitude = None

        authid = self._projected_crs_authid_from_latlon(latitude, longitude)
        with QtCore.QSignalBlocker(crs_field):
            crs_field.setText(authid or "")

    def _projected_crs_authid_from_latlon(self, latitude: Optional[float], longitude: Optional[float]) -> str:
        """Return a projected EPSG authid inferred from a latitude/longitude pair."""
        if latitude is None or longitude is None:
            return ""

        if latitude >= 84:
            return "EPSG:3413"
        if latitude <= -80:
            return "EPSG:3031"

        zone = int((longitude + 180.0) // 6.0) + 1
        zone = max(1, min(zone, 60))
        epsg = 32600 + zone if latitude >= 0 else 32700 + zone
        crs = QgsCoordinateReferenceSystem(f"EPSG:{epsg}")
        return crs.authid() if crs.isValid() else ""

    def _resize_airport_identity_card(self) -> None:
        """Keep the airport identity card tight to its content."""
        frame = getattr(
            self,
            "frame_airport_identity",
            self.findChild(QtWidgets.QFrame, "frame_airport_identity"),
        )
        if frame is None:
            return
        frame.adjustSize()
        frame.setMaximumHeight(frame.sizeHint().height())

    def _setup_dialog_status_connections(self):
        """Connect lightweight status labels to high-level input changes."""
        for name in [
            "lineEdit_arp_easting",
            "lineEdit_arp_northing",
            "lineEdit_arp_elevation",
            "lineEdit_met_easting",
            "lineEdit_met_northing",
            "lineEdit_met_elevation",
        ]:
            widget = getattr(self, name, self.findChild(QtWidgets.QLineEdit, name))
            if widget:
                widget.textChanged.connect(self.update_dialog_status)

        cns_table = getattr(
            self,
            "table_cns_facility",
            self.findChild(QtWidgets.QTableWidget, "table_cns_facility"),
        )
        if cns_table:
            cns_table.itemChanged.connect(self.update_dialog_status)

        for name in [
            "radioMemoryOutput",
            "radioFileOutput",
            "comboOutputFormat",
            "fileWidgetOutputPath",
            "checkBox_generateControllingOls",
        ]:
            widget = getattr(self, name, None)
            if not widget:
                continue
            if hasattr(widget, "toggled"):
                widget.toggled.connect(self.update_dialog_status)
            elif hasattr(widget, "currentIndexChanged"):
                widget.currentIndexChanged.connect(self.update_dialog_status)
            elif hasattr(widget, "fileChanged"):
                widget.fileChanged.connect(self.update_dialog_status)

    def _set_small_status_chip(self, label_name: str, text: str, state: str) -> None:
        """Apply a compact status-chip style to section-level labels."""
        label = getattr(self, label_name, self.findChild(QtWidgets.QLabel, label_name))
        if not label:
            return
        colors = {
            "ready": ("#eaf6ed", "#1f6b32", "#c7e7cf"),
            "warning": ("#fff5e6", "#9a5b00", "#f0d6a8"),
            "neutral": ("#f4f4f4", "#555555", "#d6d6d6"),
        }
        background, foreground, border = colors.get(state, colors["neutral"])
        label.setText(text)
        label.setStyleSheet(
            f"QLabel {{ background: {background}; color: {foreground}; border: 1px solid {border}; "
            "border-radius: 9px; padding: 3px 9px; font-size: 10px; font-weight: 600; }}"
        )

    def update_dialog_status(self):
        """Updates compact workflow status labels."""
        icao = self.lineEdit_airport_name.text().strip().upper()
        iata_widget = getattr(self, "lineEdit_iata_code", self.findChild(QtWidgets.QLineEdit, "lineEdit_iata_code"))
        iata = iata_widget.text().strip().upper() if iata_widget else ""
        if hasattr(self, "label_airport_status"):
            current_signature = self._airport_signature(icao, iata)
            if current_signature == self._airport_resolved_signature and self._airport_resolved_summary:
                self.label_airport_status.setText(self._airport_resolved_summary)
                self.label_airport_status.setStyleSheet(
                    "QLabel { background: #eaf6ed; color: #1f6b32; border: 1px solid #c7e7cf; "
                    "border-radius: 10px; padding: 4px 10px; font-weight: 600; }"
                )
            elif (
                current_signature == self._airport_lookup_status_signature
                and self._airport_lookup_state == "pending"
            ):
                self.label_airport_status.setText("Resolving airport...")
                self.label_airport_status.setStyleSheet(
                    "QLabel { background: #fff5e6; color: #9a5b00; border: 1px solid #f0d6a8; "
                    "border-radius: 10px; padding: 4px 10px; font-weight: 600; }"
                )
            elif current_signature == self._airport_lookup_status_signature and self._airport_lookup_state in {"not_found", "error"}:
                self.label_airport_status.setText(self._airport_lookup_status_message or "Airport lookup failed")
                self.label_airport_status.setStyleSheet(
                    "QLabel { background: #fff5e6; color: #9a5b00; border: 1px solid #f0d6a8; "
                    "border-radius: 10px; padding: 4px 10px; font-weight: 600; }"
                )
            elif icao or iata:
                self.label_airport_status.setText("Airport code loaded")
                self.label_airport_status.setStyleSheet(
                    "QLabel { background: #eaf2ff; color: #1f4f99; border: 1px solid #c7d7f5; "
                    "border-radius: 10px; padding: 4px 10px; font-weight: 600; }"
                )
            else:
                self.label_airport_status.setText("ICAO or IATA required")
                self.label_airport_status.setStyleSheet(
                    "QLabel { background: #f4f4f4; color: #444; border: 1px solid #d2d2d2; "
                    "border-radius: 10px; padding: 4px 10px; font-weight: 600; }"
                )
        self._resize_airport_identity_card()

        arp_values = [
            self.lineEdit_arp_easting.text().strip() if hasattr(self, "lineEdit_arp_easting") else "",
            self.lineEdit_arp_northing.text().strip() if hasattr(self, "lineEdit_arp_northing") else "",
            self.lineEdit_arp_elevation.text().strip() if hasattr(self, "lineEdit_arp_elevation") else "",
        ]
        self._set_small_status_chip(
            "label_arp_status",
            "ARP located" if all(arp_values[:2]) else "ARP incomplete" if any(arp_values) else "ARP not set",
            "ready" if all(arp_values[:2]) else "warning" if any(arp_values) else "neutral",
        )

        met_values = [
            self.lineEdit_met_easting.text().strip() if hasattr(self, "lineEdit_met_easting") else "",
            self.lineEdit_met_northing.text().strip() if hasattr(self, "lineEdit_met_northing") else "",
            self.lineEdit_met_elevation.text().strip() if hasattr(self, "lineEdit_met_elevation") else "",
        ]
        self._set_small_status_chip(
            "label_met_status",
            "MET located" if all(met_values[:2]) else "MET incomplete" if any(met_values) else "MET not used",
            "ready" if all(met_values[:2]) else "warning" if any(met_values) else "neutral",
        )

        runway_count = len(self._runway_groups)
        incomplete = 0
        for group in self._runway_groups.values():
            data = group.get_input_data()
            required_values = [
                data.get("designator_str", ""),
                data.get("thr_easting", ""),
                data.get("thr_northing", ""),
                data.get("rec_easting", ""),
                data.get("rec_northing", ""),
                data.get("width", ""),
            ]
            if not all(str(value).strip() for value in required_values):
                incomplete += 1
        if hasattr(self, "label_runway_status"):
            if runway_count == 0:
                self.label_runway_status.setText("Runways: none defined")
            elif incomplete:
                self.label_runway_status.setText(f"Runways: {runway_count} defined, {incomplete} incomplete")
            else:
                self.label_runway_status.setText(f"Runways: {runway_count} ready")

        cns_count = self.table_cns_facility.rowCount() if hasattr(self, "table_cns_facility") else 0
        if hasattr(self, "label_cns_status"):
            self.label_cns_status.setText(f"CNS facilities: {cns_count}" if cns_count else "CNS facilities: none")

        agl_enabled = bool(hasattr(self, "checkBox_agl_enabled") and self.checkBox_agl_enabled.isChecked())
        agl_rows = self.table_agl_approach.rowCount() if hasattr(self, "table_agl_approach") else 0
        if hasattr(self, "label_agl_status"):
            self.label_agl_status.setText(
                f"AGL: enabled, {agl_rows} approach row(s)" if agl_enabled else "AGL: disabled"
            )

        output_text = "Output: memory layers"
        if hasattr(self, "radioFileOutput") and self.radioFileOutput.isChecked():
            output_format = self.comboOutputFormat.currentText()
            path = self.fileWidgetOutputPath.filePath().strip()
            output_text = f"Output: {output_format} files" + (f" to {path}" if path else " (directory required)")
        if hasattr(self, "label_output_status"):
            if hasattr(self, "checkBox_generateControllingOls") and not self.checkBox_generateControllingOls.isChecked():
                output_text += " | controlling OLS skipped"
            self.label_output_status.setText(output_text)

        if hasattr(self, "label_footer_status") and not self._processing_status_active:
            footer_parts = []
            footer_parts.append(icao if icao else "No ICAO")
            footer_parts.append(f"{runway_count} runway(s)")
            if agl_enabled:
                footer_parts.append("AGL")
            footer_parts.append(output_text.replace("Output: ", ""))
            self.label_footer_status.setText(" | ".join(footer_parts))

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
        icao_code = icao_le.text().strip().upper() if icao_le else ""  # Get ICAO code early

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
                type1_label_str = f"{full_desig_1_str} Approach Type:"  # Update type label text

                # Calculate reciprocal designation (both formats)
                reciprocal_val = (rwy_desig_val + 18) if rwy_desig_val <= 18 else (rwy_desig_val - 18)
                rec_desig_num_str = f"{reciprocal_val:02d}"  # e.g., "27"
                rec_suffix_map = {"L": "R", "R": "L", "C": "C", "": ""}
                rec_suffix = rec_suffix_map.get(rwy_suffix, "")  # e.g., "R"
                compact_desig_2 = f"{rec_desig_num_str}{rec_suffix}"  # e.g., "27R"
                full_desig_2_str = f"RWY {compact_desig_2}"  # e.g., "RWY 27R" (needed for header + type label)
                type2_label_str = f"{full_desig_2_str} Approach Type:"  # Update type label text

                # <<< MODIFIED: Construct the runway name label in the desired format >>>
                combined_compact_desigs = f"{compact_desig_1}/{compact_desig_2}"  # e.g., "09L/27R"
                if icao_code:
                    rwy_name_str = f"{icao_code} Runway {combined_compact_desigs}"  # e.g., "EGLL Runway 09L/27R"
                else:
                    rwy_name_str = f"Runway {combined_compact_desigs}"  # e.g., "Runway 09L/27R"

            except ValueError:
                # Handle invalid designation input
                full_desig_2_str = "Invalid"  # Keep this for the header label update
                rwy_name_str = "Invalid Designation"  # Set error message for the main label

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
                        azimuth_str = SAME_POINT_MSG + (f" (<{NEAR_TOL}m)" if ZERO_TOL < dist < NEAR_TOL else "")
                    else:
                        az = p1.azimuth(p2) % 360
                        azimuth_str = f"{az:.2f}" + (f" ({NEAR_POINTS_MSG})" if dist < NEAR_TOL else "")
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
            calculation_results["type1_label_text"] = "(Primary End) Type:"  # Reset labels
            calculation_results["type2_label_text"] = "(Reciprocal End) Type:"

        # --- Update the group's display labels ---
        group_widget.update_display_labels(calculation_results)
        self.update_dialog_status()

    def add_runway_group(self):
        """Creates and adds a new RunwayWidgetGroup instance."""
        if self.scroll_area_layout is None:
            QMessageBox.critical(self, "Layout Error", "Scroll area layout missing.")
            return

        runway_index = self._get_next_runway_id()
        scroll_content_widget = self.findChild(QtWidgets.QScrollArea, "scrollArea_runways").widget()
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
        self.update_runway_calculations(runway_index)  # Update placeholders
        self.update_dialog_status()
        self._focus_runway_group(new_group)

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

        confirmation_message = self.tr("Remove '{name}'?").format(name=runway_display_name)
        reply = QtWidgets.QMessageBox.question(
            self,
            self.tr("Confirm Removal"),
            confirmation_message,
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No,
            QtWidgets.QMessageBox.StandardButton.No,
        )

        if reply == QtWidgets.QMessageBox.StandardButton.Yes:
            self._remove_runway_group_internal(runway_index_to_remove)
            self.update_dialog_status()

    def _remove_runway_group_internal(self, runway_index: int):
        """Internal helper to remove a group without user confirmation."""
        group_to_remove = self._runway_groups.pop(runway_index, None)
        if group_to_remove and self.scroll_area_layout is not None:
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
        elif self.scroll_area_layout is None:
            QgsMessageLog.logMessage(
                f"Internal removal Critical: Layout missing, cannot remove widget {runway_index}.",
                DIALOG_LOG_TAG,
                level=Qgis.Critical,
            )

    def _update_dialog_height(self):
        """Adjusts the dialog height to fit its contents."""
        QtCore.QTimer.singleShot(0, self.adjustSize)

    def _focus_runway_group(self, group_widget: RunwayWidgetGroup) -> None:
        """Scroll to and focus the first runway field in a group."""
        scroll_area = self.findChild(QtWidgets.QScrollArea, "scrollArea_runways")
        if scroll_area:
            QtCore.QTimer.singleShot(0, lambda: scroll_area.ensureWidgetVisible(group_widget))
        runway_name = getattr(group_widget, "desig_le", None)
        if runway_name:
            QtCore.QTimer.singleShot(0, runway_name.setFocus)

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
                validated_runway = self._validate_runway_data(index, runway_inputs, error_messages)
                if validated_runway:
                    # Ensure keys exist (validator should add them, but be safe)
                    validated_runway.setdefault("runway_end_elev_1", None)
                    validated_runway.setdefault("runway_end_elev_2", None)
                    validated_runway.setdefault("threshold_elev_1", None)
                    validated_runway.setdefault("threshold_elev_2", None)
                    validated_runway.setdefault("thr_elev_1", None)
                    validated_runway.setdefault("thr_elev_2", None)
                    validated_runway.setdefault("thr_displaced_1", None)
                    validated_runway.setdefault("thr_displaced_2", None)
                    validated_runway.setdefault("thr_pre_area_1", None)
                    validated_runway.setdefault("thr_pre_area_2", None)
                    runway_data_list.append(validated_runway)
                else:
                    validation_ok = False  # Error messages added by validator

        if not validation_ok:
            QMessageBox.critical(
                self,
                "Input Error",
                "Please correct the following errors:\n- " + "\n- ".join(error_messages),
            )
            return None
        final_data["runways"] = runway_data_list

        # --- Airfield Ground Lighting Inputs ---
        agl_options = self._get_agl_options(error_messages)
        final_data["agl_options"] = agl_options
        if agl_options.get("enabled") and len(error_messages) > 0:
            validation_ok = False

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
                error_messages.append(f"Output directory does not exist: {output_path}")
            elif selected_format_name not in OUTPUT_FORMATS:
                validation_ok = False
                error_messages.append(f"Invalid output format selected: {selected_format_name}.")
            else:
                # If validation_ok is still True up to this point
                driver_name, _, extension = OUTPUT_FORMATS[selected_format_name]
                final_data["output_path"] = output_path  # Store the processed directory path
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
                "Please correct the following errors:\n- " + "\n- ".join(error_messages),
            )
            return None

        if hasattr(self, "get_contour_interval_options"):
            final_data["contour_intervals"] = self.get_contour_interval_options()
        else:
            final_data["contour_intervals"] = {}
        if hasattr(self, "checkBox_generateControllingOls"):
            final_data["generate_controlling_ols"] = self.checkBox_generateControllingOls.isChecked()
        else:
            final_data["generate_controlling_ols"] = True

        return final_data

    def _validate_runway_data(self, index: int, inputs: Dict[str, str], errors: List[str]) -> Optional[Dict[str, Any]]:
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
            errors.append(f"Rwy {index}: Invalid primary designator '{desig_str}'. ({e})")
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
        try:  # Primary runway end elevation
            end_elev1_raw = inputs.get("runway_end_elev_1")
            if end_elev1_raw is None:
                end_elev1_raw = inputs.get("thr_elev_1", "")
            end_elev1_str = str(end_elev1_raw).strip()
            validated["runway_end_elev_1"] = float(end_elev1_str) if end_elev1_str else None
        except ValueError:
            errors.append(
                f"Rwy {index}: Invalid primary runway end elevation '{inputs.get('runway_end_elev_1', '')}'."
            )
            current_errors += 1
            validated["runway_end_elev_1"] = None
        try:  # Reciprocal runway end elevation
            end_elev2_raw = inputs.get("runway_end_elev_2")
            if end_elev2_raw is None:
                end_elev2_raw = inputs.get("thr_elev_2", "")
            end_elev2_str = str(end_elev2_raw).strip()
            validated["runway_end_elev_2"] = float(end_elev2_str) if end_elev2_str else None
        except ValueError:
            errors.append(
                f"Rwy {index}: Invalid reciprocal runway end elevation '{inputs.get('runway_end_elev_2', '')}'."
            )
            current_errors += 1
            validated["runway_end_elev_2"] = None

        try:  # Primary threshold elevation
            threshold_elev1_str = inputs.get("threshold_elev_1", "").strip()
            validated["threshold_elev_1"] = (
                float(threshold_elev1_str) if threshold_elev1_str else validated["runway_end_elev_1"]
            )
        except ValueError:
            errors.append(f"Rwy {index}: Invalid primary threshold elevation '{inputs.get('threshold_elev_1', '')}'.")
            current_errors += 1
            validated["threshold_elev_1"] = validated.get("runway_end_elev_1")
        try:  # Reciprocal threshold elevation
            threshold_elev2_str = inputs.get("threshold_elev_2", "").strip()
            validated["threshold_elev_2"] = (
                float(threshold_elev2_str) if threshold_elev2_str else validated["runway_end_elev_2"]
            )
        except ValueError:
            errors.append(
                f"Rwy {index}: Invalid reciprocal threshold elevation '{inputs.get('threshold_elev_2', '')}'."
            )
            current_errors += 1
            validated["threshold_elev_2"] = validated.get("runway_end_elev_2")

        # Legacy aliases used by existing OLS code paths until all callers are migrated.
        validated["thr_elev_1"] = validated["threshold_elev_1"]
        validated["thr_elev_2"] = validated["threshold_elev_2"]

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
            errors.append(f"Rwy {index}: Invalid runway width '{inputs.get('width', '')}'. Must be a positive number.")
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
            errors.append(f"Rwy {index}: Invalid shoulder width '{inputs.get('shoulder', '')}'. Must be non-negative.")
            current_errors += 1
            validated["shoulder"] = None

        for field_name, label in [
            ("clearway1_len", "primary clearway length"),
            ("clearway2_len", "reciprocal clearway length"),
            ("stopway1_len", "primary stopway length"),
            ("stopway2_len", "reciprocal stopway length"),
        ]:
            try:
                raw_value = str(inputs.get(field_name, "")).strip()
                if raw_value:
                    parsed_value = float(raw_value)
                    if parsed_value < 0:
                        raise ValueError("Cannot be negative")
                    validated[field_name] = parsed_value
                else:
                    validated[field_name] = 0.0
            except ValueError:
                errors.append(f"Rwy {index}: Invalid {label} '{inputs.get(field_name, '')}'. Must be non-negative.")
                current_errors += 1
                validated[field_name] = 0.0

        for field_name in [
            "takeoff_available_1",
            "takeoff_available_2",
            "landing_available_1",
            "landing_available_2",
        ]:
            validated[field_name] = self._bool_from_input(inputs.get(field_name, True))

        # Optional fields (just copy text)
        validated["arc_num"] = inputs.get("arc_num")
        validated["arc_let"] = inputs.get("arc_let")
        surface_category = str(inputs.get("surface_category", "") or "").strip() or DEFAULT_RUNWAY_SURFACE_CATEGORY
        surface_material = str(inputs.get("surface_material", "") or "").strip() or DEFAULT_RUNWAY_SURFACE_MATERIAL
        if surface_category and surface_category not in RUNWAY_SURFACE_MATERIALS:
            errors.append(f"Rwy {index}: Invalid runway surface category '{surface_category}'.")
            current_errors += 1
            surface_category = ""
            surface_material = ""
        elif surface_material and surface_material not in RUNWAY_SURFACE_MATERIALS.get(surface_category, []):
            errors.append(
                f"Rwy {index}: Invalid runway surface material '{surface_material}' for category '{surface_category or 'None'}'."
            )
            current_errors += 1
            surface_material = ""
        validated["surface_category"] = surface_category
        validated["surface_material"] = surface_material
        validated["type1"] = inputs.get("type1")
        validated["type2"] = inputs.get("type2")

        return validated if current_errors == 0 else None

    def _bool_from_input(self, value: Any) -> bool:
        if isinstance(value, bool):
            return value
        if value is None:
            return True
        return str(value).strip().lower() not in {"0", "false", "no", "off"}

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
                            self.tr("Invalid ARP coordinate format. ARP coordinates ignored."),
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
                            self.tr("Invalid MET station coordinate format. MET station ignored."),
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
            QgsMessageLog.logMessage(f"Error getting global inputs: {e}", DIALOG_LOG_TAG, level=Qgis.Critical)
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
