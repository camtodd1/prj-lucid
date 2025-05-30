# -*- coding: utf-8 -*-
# safeguarding_builder.py

import os.path
import math
import traceback
import re

# import functools # Not used directly
from typing import Dict, Optional, List, Any, Tuple

# --- Qt Imports ---
from qgis.PyQt import QtCore  # type: ignore
from qgis.PyQt.QtCore import QSettings, QTranslator, QCoreApplication, QVariant, QDateTime  # type: ignore
from qgis.PyQt.QtGui import QIcon  # type: ignore
from qgis.PyQt.QtWidgets import QAction, QMessageBox, QPushButton  # type: ignore

# --- QGIS Imports ---
from qgis.core import (  # type: ignore
    QgsProject,
    QgsVectorLayer,
    QgsFields,
    QgsField,
    QgsFeature,
    QgsGeometry,
    QgsLineString,
    QgsPointXY,
    QgsPolygon,
    QgsPoint,
    QgsLayerTreeGroup,
    QgsLayerTreeNode,
    QgsLayerTreeLayer,
    QgsMessageLog,
    Qgis,
    QgsCoordinateReferenceSystem,
    QgsVectorFileWriter,
    QgsDistanceArea,
    QgsWkbTypes,
)

# --- Local Imports ---
from . import cns_dimensions
from . import ols_dimensions


try:
    # Attempt to import generated resources
    from .resources_rc import *  # noqa: F403
except ImportError:
    # Fallback message if resources haven't been compiled
    print("Note: resources_rc.py not found or generated. Icons might be missing.")
# Import the dialog class
from .safeguarding_builder_dialog import SafeguardingBuilderDialog

# Plugin-specific constant for logging
PLUGIN_TAG = "SafeguardingBuilder"

# ============================================================
# Constants for Guideline Parameters
# ============================================================
GUIDELINE_B_FAR_EDGE_OFFSET = 500.0
GUIDELINE_B_ZONE_LENGTH_BACKWARD = 1400.0
GUIDELINE_B_ZONE_HALF_WIDTH = 1200.0

GUIDELINE_C_RADIUS_A_M = 3000.0
GUIDELINE_C_RADIUS_B_M = 8000.0
GUIDELINE_C_RADIUS_C_M = 13000.0
GUIDELINE_C_BUFFER_SEGMENTS = 144  # Increase segments for smoother circles

GUIDELINE_D_TURBINE_RADIUS_M = 30000.0
GUIDELINE_D_BUFFER_SEGMENTS = 144  # Segments for smoother circle

GUIDELINE_E_ZONE_PARAMS = {
    "A": {
        "ext": 1000.0,
        "half_w": 300.0,
        "desc": "Lighting Control Zone A",
        "max_intensity": "0cd",
    },
    "B": {
        "ext": 2000.0,
        "half_w": 450.0,
        "desc": "Lighting Control Zone B",
        "max_intensity": "50cd",
    },
    "C": {
        "ext": 3000.0,
        "half_w": 600.0,
        "desc": "Lighting Control Zone C",
        "max_intensity": "150cd",
    },
    "D": {
        "ext": 4500.0,
        "half_w": 750.0,
        "desc": "Lighting Control Zone D",
        "max_intensity": "450cd",
    },
}
GUIDELINE_E_ZONE_ORDER = ["A", "B", "C", "D"]
MOS_REF_GUIDELINE_E = "MOS 9.144(2)"
NASF_REF_GUIDELINE_E = "NASF Guideline E"

GUIDELINE_I_PSA_LENGTH = 1000.0
GUIDELINE_I_PSA_INNER_WIDTH = 350.0
GUIDELINE_I_PSA_OUTER_WIDTH = 250.0
GUIDELINE_I_MOS_REF_VAL = "n/a"
GUIDELINE_I_NASF_REF_VAL = "NASF Guideline I"

RAOA_MOS_REF_VAL = "MOS 6.20"
MOS_REF_TAXIWAY_SEPARATION = "MOS 6.53"

CONICAL_CONTOUR_INTERVAL = 10.0  # Height interval in meters for conical surface
APPROACH_CONTOUR_INTERVAL = 10.0  # Height interval in meters for approach surfaces
TOCS_CONTOUR_INTERVAL = 10.0  # Height interval in meters for TOCS surfaces
TRANSITIONAL_CONTOUR_INTERVAL = 10.0  # Height interval in meters for transitional surfaces

# ============================================================
# Main Plugin Class - SafeguardingBuilder
# ============================================================
class SafeguardingBuilder:
    """QGIS Plugin Implementation for NASF Safeguarding Surface Generation."""

    def __init__(self, iface):
        """Constructor: Initializes plugin resources and UI connections."""
        self.iface = iface
        self.plugin_dir = os.path.dirname(__file__)
        self.successfully_generated_layers: List[QgsVectorLayer] = []
        self.translator: Optional[QTranslator] = None
        self.actions: List[QAction] = []
        self.menu = self.tr("&Safeguarding Builder")
        self.dlg: Optional[SafeguardingBuilderDialog] = None
        self.style_map: Dict[str, str] = {}
        self.reference_elevation_datum: Optional[float] = None
        self.arp_elevation_amsl: Optional[float] = None

        self.output_mode: str = "memory"
        self.output_path: Optional[str] = None
        self.output_format_driver: Optional[str] = None
        self.output_format_extension: Optional[str] = None
        self.dissolve_output: bool = False

        self._init_locale()

    def _initialise_crs(self):
        """Force QGIS to initialise CRS subsystems by adding and removing a dummy layer."""
        plugin_tag = PLUGIN_TAG
        crs_authid = QgsProject.instance().crs().authid()
        # QgsMessageLog.logMessage(f"Initialising CRS: {crs_authid}", plugin_tag, Qgis.Info)
        dummy = QgsVectorLayer(f"Point?crs={crs_authid}", "crs_init_dummy", "memory")
        if dummy.isValid():
            QgsProject.instance().addMapLayer(dummy, False)
            QgsProject.instance().removeMapLayer(dummy)
            # QgsMessageLog.logMessage("CRS initialisation dummy layer added and removed successfully.", plugin_tag, Qgis.Info)
        else:
            QgsMessageLog.logMessage(
                "CRS initialisation dummy layer failed to create.",
                plugin_tag,
                Qgis.Warning,
            )

    def _init_locale(self):
        """Load translation file."""
        locale_code = QSettings().value("locale/userLocale", "")[0:2]
        locale_path = os.path.join(
            self.plugin_dir, "i18n", f"SafeguardingBuilder_{locale_code}.qm"
        )
        if os.path.exists(locale_path):
            self.translator = QTranslator()
            if self.translator.load(locale_path):
                QCoreApplication.installTranslator(self.translator)
            else:
                # QgsMessageLog.logMessage(f"Failed to load translation file: {locale_path}", PLUGIN_TAG, level=Qgis.Warning)
                self.translator = None

    def tr(self, message: str) -> str:
        """Get the translation for a string using Qt translation API."""
        if self.translator:
            # Use type() for class name to avoid potential undefined variable
            return QCoreApplication.translate(type(self).__name__, message)
        return message

    def add_action(
        self,
        icon_path: str,
        text: str,
        callback,
        enabled_flag: bool = True,
        add_to_menu: bool = True,
        add_to_toolbar: bool = True,
        status_tip: Optional[str] = None,
        whats_this: Optional[str] = None,
        parent=None,
    ) -> QAction:
        """Helper method to add an action to the QGIS GUI (menu/toolbar)."""
        try:
            icon = QIcon(icon_path)
            if icon.isNull() and icon_path.startswith(":/"):
                raise NameError  # Force fallback if resource icon is invalid
        except (NameError, TypeError):
            icon = QIcon()
            QgsMessageLog.logMessage(
                f"Icon resource not found or invalid: {icon_path}. Using default.",
                PLUGIN_TAG,
                level=Qgis.Warning,
            )

        action = QAction(icon, text, parent)
        action.triggered.connect(callback)
        action.setEnabled(enabled_flag)
        if status_tip:
            action.setStatusTip(status_tip)
        if whats_this:
            action.setWhatsThis(whats_this)
        if add_to_toolbar:
            self.iface.addToolBarIcon(action)
        if add_to_menu:
            self.iface.addPluginToMenu(self.menu, action)
        self.actions.append(action)
        return action

    def initGui(self):
        """Create the menu entries and toolbar icons inside the QGIS GUI."""
        icon_path = ":/plugins/safeguarding_builder/icon.png"
        try:
            if QIcon(icon_path).isNull():
                raise NameError
        except (NameError, TypeError):
            icon_path_file = os.path.join(self.plugin_dir, "icon.png")
            if os.path.exists(icon_path_file):
                icon_path = icon_path_file
            else:
                QgsMessageLog.logMessage(
                    f"Icon resource/fallback not found: {icon_path_file}",
                    PLUGIN_TAG,
                    level=Qgis.Warning,
                )
                icon_path = ""

        self.add_action(
            icon_path,
            text=self.tr("NASF Safeguarding Builder"),
            callback=self.run,
            parent=self.iface.mainWindow(),
        )

    def unload(self):
        """Removes the plugin menu item and icon from QGIS GUI."""
        for action in self.actions:
            self.iface.removePluginMenu(self.tr("&Safeguarding Builder"), action)
            self.iface.removeToolBarIcon(action)
        if self.dlg:
            try:
                self.dlg.finished.disconnect(self.dialog_finished)
            except TypeError:
                pass
            try:
                self.dlg.deleteLater()
            except Exception as e:
                QgsMessageLog.logMessage(
                    f"Error cleaning dialog: {e}", PLUGIN_TAG, level=Qgis.Warning
                )
            self.dlg = None
        self.successfully_generated_layers = []

    def run(self):
        """Shows the plugin dialog or brings it to front if already open."""
        if self.dlg is not None and self.dlg.isVisible():
            self.dlg.raise_()
            self.dlg.activateWindow()
            QgsMessageLog.logMessage(
                "Dialog already open.", PLUGIN_TAG, level=Qgis.Info
            )
            return

        self.successfully_generated_layers = []  # Reset layers list

        if self.dlg is None:
            parent_window = self.iface.mainWindow()
            try:
                self.dlg = SafeguardingBuilderDialog(parent=parent_window)
            except Exception as e:
                QgsMessageLog.logMessage(
                    f"Error creating dialog: {e}\n{traceback.format_exc()}",
                    PLUGIN_TAG,
                    level=Qgis.Critical,
                )
                QMessageBox.critical(
                    parent_window,
                    self.tr("Dialog Error"),
                    self.tr("Could not create dialog. Check logs."),
                )
                return

            # Connect Signals
            generate_button = self.dlg.findChild(QPushButton, "pushButton_Generate")

            if generate_button:
                generate_button.clicked.connect(self.run_safeguarding_processing)
            else:
                # This is a critical UI failure if the main action button is missing.
                QgsMessageLog.logMessage(
                    "CRITICAL UI ERROR: 'Generate Safeguarding Surfaces' button (expected objectName 'pushButton_Generate') not found in dialog.",
                    PLUGIN_TAG,
                    level=Qgis.Critical,
                )
                QMessageBox.critical(
                    self.dlg,
                    self.tr("UI Error"),
                    self.tr(
                        "Main 'Generate' button is missing from the dialog. Plugin cannot function."
                    ),
                )
                self.dlg.deleteLater()  # Clean up the partially created dialog
                self.dlg = None
                return

            # The dialog's built-in close mechanisms (X button, Esc key)
            # will emit the finished signal.
            self.dlg.finished.connect(self.dialog_finished)

        self.dlg.show()
        QgsMessageLog.logMessage(
            "Safeguarding Builder dialog shown.", PLUGIN_TAG, level=Qgis.Info
        )

    def dialog_finished(self, result: int):
        """Slot connected to the dialog's finished signal for cleanup."""
        QgsMessageLog.logMessage(
            f"Dialog finished signal received (result code: {result})",
            PLUGIN_TAG,
            level=Qgis.Info,
        )  # Use Info level
        self.dlg = None

    # ============================================================
    # Core Processing Logic
    # ============================================================

    def _calculate_reference_elevation_datum(
        self, arp_elevation: Optional[float], runway_data_list: List[dict]
    ) -> Optional[float]:
        """
        Calculates the Reference Elevation Datum based on CASA MOS 139 requirements.
        Rounds result down to the nearest half metre.
        Uses validated runway data containing 'thr_elev_1' and 'thr_elev_2'.
        """
        plugin_tag = PLUGIN_TAG  # Local variable for convenience

        if arp_elevation is None:
            # Critical: Cannot calculate RED without ARP Elevation.
            QgsMessageLog.logMessage(
                "Cannot calculate RED: ARP Elevation is missing.",
                plugin_tag,
                level=Qgis.Critical,
            )
            return None

        if not runway_data_list:
            # Warning: No runways provided, cannot calculate RED based on thresholds.
            QgsMessageLog.logMessage(
                "Cannot calculate RED: No runway data provided.",
                plugin_tag,
                level=Qgis.Warning,
            )
            return None

        threshold_elevations: List[float] = []
        missing_elev_rwy_summaries: List[str] = (
            []
        )  # Store summary strings for missing elevations

        for rwy_data in runway_data_list:
            # Use validated keys 'thr_elev_1' and 'thr_elev_2'
            thr_elev = rwy_data.get("thr_elev_1")
            rec_thr_elev = rwy_data.get("thr_elev_2")

            # Generate a name for logging/reporting
            rwy_name = rwy_data.get(
                "short_name", f"RWY Index {rwy_data.get('original_index', '?')}"
            )

            # Check if the retrieved values are valid floats
            valid_thr = isinstance(thr_elev, (int, float))
            valid_rec = isinstance(rec_thr_elev, (int, float))

            # Add valid elevations to the list
            if valid_thr:
                threshold_elevations.append(float(thr_elev))
            if valid_rec:
                threshold_elevations.append(float(rec_thr_elev))

            # Collect summary if elevations are missing for this runway
            if not valid_thr or not valid_rec:
                missing_parts = []
                if not valid_thr:
                    missing_parts.append("THR1")
                if not valid_rec:
                    missing_parts.append("THR2")
                missing_elev_rwy_summaries.append(
                    f"{rwy_name} ({'/'.join(missing_parts)})"
                )

        # --- Post-Loop Checks and Logging ---

        # Critical Error: No valid threshold elevations found at all.
        if not threshold_elevations:
            QgsMessageLog.logMessage(
                "Cannot calculate RED: No valid threshold elevations found in any runway data.",
                plugin_tag,
                level=Qgis.Critical,
            )
            # User feedback is crucial here as it prevents further dependent calculations.
            if self.iface:
                self.iface.messageBar().pushMessage(
                    self.tr("Error"),
                    self.tr(
                        "Cannot calculate Reference Elevation Datum: No valid threshold elevations found."
                    ),
                    level=Qgis.Critical,
                    duration=10,
                )
            return None

        # Warning: Some elevations were missing, but calculation can proceed.
        if missing_elev_rwy_summaries:
            summary_str = ", ".join(missing_elev_rwy_summaries)
            # Log a single warning summarizing all missing elevations.
            QgsMessageLog.logMessage(
                f"Warning: Missing threshold elevations for: [{summary_str}]. "
                "RED calculation proceeding with available data.",
                plugin_tag,
                level=Qgis.Warning,
            )
            # Provide a single warning to the user.
            if self.iface:
                self.iface.messageBar().pushMessage(
                    self.tr("Warning"),
                    self.tr(
                        "Missing threshold elevations for some runways. "
                        "RED calculation may be inaccurate. Check Log Messages panel for details."
                    ),
                    level=Qgis.Warning,
                    duration=8,
                )

        # --- Calculation ---
        avg_thr_elev = sum(threshold_elevations) / len(threshold_elevations)
        # Info: Log the average value used in the calculation.
        QgsMessageLog.logMessage(
            f"Calculated Average Threshold Elevation: {avg_thr_elev:.3f}m AMSL",
            plugin_tag,
            level=Qgis.Info,
        )

        reference_elevation_unrounded: float
        # Apply MOS 139 rule
        if abs(arp_elevation - avg_thr_elev) <= 3.0:
            reference_elevation_unrounded = arp_elevation
            # Info: Log the basis for the RED value.
            QgsMessageLog.logMessage(
                "RED based on ARP Elevation (within 3m of average THR elev).",
                plugin_tag,
                level=Qgis.Info,
            )
        else:
            reference_elevation_unrounded = avg_thr_elev
            # Info: Log the basis for the RED value.
            QgsMessageLog.logMessage(
                "RED based on Average Threshold Elevation (>3m difference from ARP).",
                plugin_tag,
                level=Qgis.Info,
            )

        # Round down to the nearest half metre
        # reference_elevation_datum = math.floor(reference_elevation_unrounded * 2) / 2.0

        reference_elevation_datum = reference_elevation_unrounded

        # Success: Log the final calculated RED.
        QgsMessageLog.logMessage(
            f"Calculated Reference Elevation Datum (RED): {reference_elevation_datum:.2f}m AMSL ",
            # f"(Unrounded: {reference_elevation_unrounded:.3f}m)",
            plugin_tag,
            level=Qgis.Success,
        )
        return reference_elevation_datum

    def run_safeguarding_processing(self):
        plugin_tag = PLUGIN_TAG
        QgsMessageLog.logMessage(
            "--- Safeguarding Processing Started ---", plugin_tag, level=Qgis.Info
        )

        self.successfully_generated_layers = []
        self.reference_elevation_datum = None
        self.arp_elevation_amsl = None
        self.output_mode = "memory"
        self.output_path = None
        self.output_format_driver = None
        self.output_format_extension = None
        self.dissolve_output = False

        if self.dlg is None:
            QgsMessageLog.logMessage(
                "Processing aborted: Dialog reference missing.",
                plugin_tag,
                level=Qgis.Critical,
            )
            return

        project = QgsProject.instance()
        target_crs = project.crs()
        target_crs_authid = target_crs.authid()
        if not target_crs or not target_crs.isValid():
            QgsMessageLog.logMessage(
                "Processing aborted: Project CRS is invalid or not set.",
                plugin_tag,
                level=Qgis.Critical,
            )
            self.iface.messageBar().pushMessage(
                self.tr("Error"),
                self.tr(
                    "Project CRS is invalid or not set. Please set a valid Projected CRS."
                ),
                level=Qgis.Critical,
                duration=10,
            )
            return

        QgsMessageLog.logMessage(
            f"Using Project CRS: {target_crs_authid} ({target_crs.description()})",
            plugin_tag,
            level=Qgis.Info,
        )

        # Force CRS subsystem to initialise properly
        self._initialise_crs()
        # QgsMessageLog.logMessage(
        #     f"CRS initialisation complete. Project CRS is now active: {target_crs.authid()}",
        #     plugin_tag,
        #     level=Qgis.Info,
        # )

        specialised_safeguarding_group = None

        input_data = None
        try:
            input_data = self.dlg.get_all_input_data()
            if input_data is None:
                QgsMessageLog.logMessage(
                    "Processing aborted: Input validation failed (check previous messages or dialog).",
                    plugin_tag,
                    level=Qgis.Warning,
                )
                return
        except Exception as e:
            QgsMessageLog.logMessage(
                f"Critical error getting input data: {e}\n{traceback.format_exc()}",
                plugin_tag,
                level=Qgis.Critical,
            )
            self.iface.messageBar().pushMessage(
                self.tr("Error"),
                self.tr("Failed to retrieve input data. See log for details."),
                level=Qgis.Critical,
                duration=10,
            )
            return

        self.output_mode = input_data.get("output_mode", "memory")
        self.icao_code = input_data.get("icao_code", "UNKNOWN_ICAO")
        self.output_path = input_data.get("output_path")
        self.output_format_driver = input_data.get("output_format_driver")
        self.output_format_extension = input_data.get("output_format_extension")
        self.dissolve_output = input_data.get("dissolve_output", False)
        QgsMessageLog.logMessage(
            f"Processing Mode: {self.output_mode}. "
            f"Path: {self.output_path or 'N/A'}. "
            f"Format: {self.output_format_driver or 'N/A'}. "
            f"Dissolve: {self.dissolve_output}",
            plugin_tag,
            level=Qgis.Info,
        )

        icao_code = input_data.get("icao_code", "UNKNOWN")
        arp_point = input_data.get("arp_point")
        arp_east = input_data.get("arp_easting")
        arp_north = input_data.get("arp_northing")
        met_point = input_data.get("met_point")
        runway_input_list = input_data.get("runways", [])
        cns_input_list = input_data.get("cns_facilities", [])
        self.arp_elevation_amsl = input_data.get("arp_elevation")

        if not runway_input_list:
            QgsMessageLog.logMessage(
                "No valid runway data found to process.", plugin_tag, level=Qgis.Warning
            )
            self.iface.messageBar().pushMessage(
                self.tr("Warning"),
                self.tr("No valid runway data found after validation."),
                level=Qgis.Warning,
                duration=5,
            )

        if runway_input_list:
            self.style_map = {
                "ARP": "arp_point.qml",
                "Runway Centreline": "rwy_centreline_line.qml",
                "MET Station Location": "default_point.qml",
                "MET Instrument Enclosure": "default_zone_polygon.qml",
                "MET Buffer Zone": "default_zone_polygon.qml",
                "MET Obstacle Buffer Zone": "default_zone_polygon.qml",
                "Runway Pavement": "physical_runway.qml",
                "PreThreshold Runway": "physical_prethreshold_runway.qml",
                "PreThreshold Area": "physical_prethreshold_area.qml",
                "DisplacedThresholdMarking": "physical_displaced_marking.qml",
                "PreThresholdAreaMarking": "physical_pre_area_marking.qml",
                "Runway Shoulders": "physical_runway_shoulder.qml",
                "Runway Graded Strips": "physical_graded_strips.qml",
                "Runway Overall Strips": "physical_overall_strips.qml",
                "Runway Strip Flyover Area": "default_zone_polygon.qml",
                "Runway End Safety Areas (RESA)": "physical_resa.qml",
                "Stopways": "physical_stopway.qml",
                "RAOA": "default_zone_polygon.qml",
                "Taxiway Separation Line": "twy_separation_line.qml",
                "WSZ Runway": "guideline_b_wsz.qml",
                "WMZ A": "default_zone_polygon.qml",
                "WMZ B": "default_zone_polygon.qml",
                "WMZ C": "default_zone_polygon.qml",
                "Wind Turbine Assessment Zone": "default_zone_polygon.qml",
                "LCZ A": "default_zone_polygon.qml",
                "LCZ B": "default_zone_polygon.qml",
                "LCZ C": "default_zone_polygon.qml",
                "LCZ D": "default_zone_polygon.qml",
                "OLS Approach": "ols_approach_polygon.qml",
                "OLS Approach Contour": "ols_approach_contours.qml",
                "OLS Inner Approach": "default_ofz_polygon.qml",
                "OLS Inner Transitional": "default_ofz_polygon.qml",
                "OLS Baulked Landing": "default_ofz_polygon.qml",
                "OLS TOCS": "ols_tocs_polygon.qml",
                "OLS TOCS Contour": "ols_tocs_contours.qml",
                "OLS IHS": "default_ols_polygon.qml",
                "OLS Transitional": "default_ols_polygon.qml",
                "OLS Transitional Contour": "ols_transitional_contours.qml",
                "OLS Conical": "default_ols_polygon.qml",
                "OLS Conical Contour": "ols_conical_contours.qml",
                "OLS OHS": "default_ols_polygon.qml",
                "CNS Circle Zone": "default_cns_zone_polygon.qml",
                "CNS Donut Zone": "default_cns_zone_polygon.qml",
                "Default CNS": "default_cns_zone_polygon.qml",
                "PSA Runway": "guideline_i_psa.qml",
                "Default Polygon": "default_zone_polygon.qml",
                "Default Line": "default_line.qml",
                "Default Point": "default_point.qml",
            }

            root = project.layerTreeRoot()
            main_group_name = f"{icao_code} {self.tr('Safeguarding Surfaces')}"
            main_group = self._setup_main_group(root, main_group_name, project)
            if main_group is None:
                self.iface.messageBar().pushMessage(
                    self.tr("Error"),
                    self.tr("Failed to create main layer group."),
                    level=Qgis.Critical,
                    duration=10,
                )
                return

            arp_layer_created = False
            if arp_point:
                arp_layer = self.create_arp_layer(
                    arp_point,
                    arp_east,
                    arp_north,
                    icao_code,
                    target_crs,
                    main_group,
                    self.arp_elevation_amsl,
                )
                if arp_layer:
                    arp_layer_created = True
                if self.arp_elevation_amsl is None and arp_layer:
                    fetched_elev = self._try_get_arp_elevation_from_layer(arp_layer)
                    if fetched_elev is not None:
                        QgsMessageLog.logMessage(
                            f"Note: ARP Elevation ({fetched_elev:.2f}m) found on layer after RED calculation might have failed.",
                            plugin_tag,
                            level=Qgis.Warning,
                        )

            met_layers_created_ok = False
            if met_point:
                met_group = main_group.addGroup(
                    self.tr("Meteorological Instrument Station")
                )
                if met_group:
                    met_layers_created_ok, _ = self.process_met_station_surfaces(
                        met_point, icao_code, target_crs, met_group
                    )
                else:
                    QgsMessageLog.logMessage(
                        "Failed to create 'Meteorological Instrument Station' subgroup.",
                        plugin_tag,
                        level=Qgis.Warning,
                    )
            else:
                QgsMessageLog.logMessage(
                    "Skipping MET Station processing: No valid coordinates provided.",
                    plugin_tag,
                    level=Qgis.Info,
                )

            processed_runway_data_list, any_runway_base_data_ok = (
                self._process_runways_part1(
                    main_group, project, target_crs, icao_code, runway_input_list
                )
            )

            if any_runway_base_data_ok:
                for rwy_data in processed_runway_data_list:
                    cl_layer = rwy_data.get("centreline_layer")
                    if cl_layer:
                        self._apply_style(cl_layer, self.style_map)

            physical_geom_group = None
            protection_area_group = None
            physical_layers = {}
            any_physical_or_protection_ok = False

            if processed_runway_data_list and any_runway_base_data_ok:
                physical_geom_group = main_group.addGroup(self.tr("Physical Geometry"))
                protection_area_group = main_group.addGroup(
                    self.tr("Runway Protection Areas")
                )
                specialised_safeguarding_group = main_group.findGroup(
                    self.tr("Specialised Safeguarding")
                )
                if (
                    not specialised_safeguarding_group
                ):  # Should have been created earlier
                    specialised_safeguarding_group = main_group.addGroup(
                        self.tr("Specialised Safeguarding")
                    )

                if (
                    physical_geom_group
                    and protection_area_group
                    and specialised_safeguarding_group
                ):
                    common_fields = [
                        QgsField("rwy", QVariant.String, self.tr("Runway Name"), 30),
                        QgsField("desc", QVariant.String, self.tr("Element Type"), 50),
                        QgsField("len_m", QVariant.Double, self.tr("len_m"), 12, 3),
                        QgsField("wid_m", QVariant.Double, self.tr("wid_m"), 12, 3),
                        QgsField(
                            "ref_mos", QVariant.String, self.tr("MOS Reference"), 250
                        ),
                    ]
                    stopway_resa_fields = common_fields + [
                        QgsField(
                            "end_desig", QVariant.String, self.tr("End Designator"), 10
                        )
                    ]
                    pre_threshold_fields = common_fields + [
                        QgsField(
                            "end_desig", QVariant.String, self.tr("End Designator"), 10
                        )
                    ]
                    marking_fields = [
                        QgsField("rwy", QVariant.String, self.tr("Runway Name"), 30),
                        QgsField("desc", QVariant.String, self.tr("Element Type"), 50),
                        QgsField("len_m", QVariant.Double, self.tr("len_m"), 12, 3),
                        QgsField(
                            "end_desig", QVariant.String, self.tr("End Designator"), 10
                        ),
                        QgsField(
                            "ref_mos", QVariant.String, self.tr("MOS Reference"), 250
                        ),
                    ]

                    layer_definitions = {
                        "rwy": {
                            "name": self.tr("Runway Pavement"),
                            "fields": common_fields,
                            "group": physical_geom_group,
                        },
                        "PreThresholdRunway": {
                            "name": self.tr("Pre-Threshold Runway"),
                            "fields": pre_threshold_fields,
                            "group": physical_geom_group,
                        },
                        "PreThresholdArea": {
                            "name": self.tr("Pre-Threshold Area"),
                            "fields": pre_threshold_fields,
                            "group": physical_geom_group,
                        },
                        "DisplacedThresholdMarking": {
                            "name": self.tr("Displaced Threshold Markings"),
                            "fields": marking_fields,
                            "geom_type": "LineString",
                            "group": physical_geom_group,
                        },
                        "PreThresholdAreaMarking": {
                            "name": self.tr("Pre-Threshold Area Markings"),
                            "fields": marking_fields,
                            "geom_type": "LineString",
                            "group": physical_geom_group,
                        },
                        "Shoulder": {
                            "name": self.tr("Runway Shoulders"),
                            "fields": common_fields,
                            "group": physical_geom_group,
                        },
                        "Stopway": {
                            "name": self.tr("Stopways"),
                            "fields": stopway_resa_fields,
                            "group": protection_area_group,
                        },
                        "GradedStrip": {
                            "name": self.tr("Runway Graded Strip"),
                            "fields": common_fields,
                            "group": protection_area_group,
                        },
                        "FlyoverStrip": {
                            "name": self.tr("Runway Strip Flyover Area"),
                            "fields": common_fields,
                            "group": protection_area_group,
                        },
                        "OverallStrip": {
                            "name": self.tr("Runway Overall Strip"),
                            "fields": common_fields,
                            "group": protection_area_group,
                        },
                        "RESA": {
                            "name": self.tr("Runway End Safety Area (RESA)"),
                            "fields": stopway_resa_fields,
                            "group": protection_area_group,
                        },
                    }
                    style_key_map = {
                        "rwy": "Runway Pavement",
                        "PreThresholdRunway": "PreThreshold Runway",
                        "PreThresholdArea": "PreThreshold Area",
                        "DisplacedThresholdMarking": "DisplacedThresholdMarking",
                        "PreThresholdAreaMarking": "PreThresholdAreaMarking",
                        "Shoulder": "Runway Shoulders",
                        "Stopway": "Stopways",
                        "GradedStrip": "Runway Graded Strips",
                        "FlyoverStrip": "Runway Strip Flyover Area",
                        "OverallStrip": "Runway Overall Strips",
                        "RESA": "Runway End Safety Areas (RESA)",
                    }

                    for element_type, definition in layer_definitions.items():
                        target_group = definition.get("group")
                        if not target_group:
                            QgsMessageLog.logMessage(
                                f"Warning: No target group defined for {element_type}, skipping layer setup.",
                                plugin_tag,
                                level=Qgis.Warning,
                            )
                            continue
                        geom_type_str = definition.get("geom_type", "Polygon")
                        layer_name_internal = f"physical_{element_type}_{icao_code}_{id(self)}_{QtCore.QDateTime.currentMSecsSinceEpoch()}"
                        layer_display_name = f"{icao_code} {definition['name']}"
                        layer_uri = ""
                        if geom_type_str == "LineString":
                            layer_uri = f"LineString?crs={target_crs_authid}&index=yes"
                        elif geom_type_str == "Polygon":
                            layer_uri = f"Polygon?crs={target_crs_authid}&index=yes"
                        else:
                            QgsMessageLog.logMessage(
                                f"Warning: Unsupported geometry type '{geom_type_str}' for layer URI.",
                                plugin_tag,
                                level=Qgis.Warning,
                            )
                            continue
                        layer = QgsVectorLayer(layer_uri, layer_name_internal, "memory")

                        if (
                            layer.isValid()
                            and layer.dataProvider()
                            and layer.dataProvider().addAttributes(definition["fields"])
                        ):
                            layer.updateFields()
                            layer.setName(layer_display_name)
                            layer.setCustomProperty(
                                "target_group_node", target_group.name()
                            )
                            layer.setCustomProperty(
                                "safeguarding_style_key",
                                style_key_map.get(element_type),
                            )
                            if layer.startEditing():
                                physical_layers[element_type] = layer
                            else:
                                QgsMessageLog.logMessage(
                                    f"Warning: Failed startEditing for layer '{layer_display_name}'.",
                                    plugin_tag,
                                    level=Qgis.Warning,
                                )
                                physical_layers[element_type] = None
                        else:
                            QgsMessageLog.logMessage(
                                f"Critical: Failed initialize layer '{layer_display_name}'.",
                                plugin_tag,
                                level=Qgis.Critical,
                            )
                            physical_layers[element_type] = None

                    physical_geom_features_added = {
                        element_type: False for element_type in physical_layers.keys()
                    }
                    QgsMessageLog.logMessage(
                        "Populating physical geometry & protection area layers...",
                        plugin_tag,
                        level=Qgis.Info,
                    )
                    for rwy_data in processed_runway_data_list:
                        runway_name_log = rwy_data.get(
                            "short_name", f"RWY_{rwy_data.get('original_index','?')}"
                        )
                        try:
                            generated_elements_list = self.generate_physical_geometry(
                                rwy_data
                            )
                            if generated_elements_list is None:
                                continue

                            graded_strip_geom: Optional[QgsGeometry] = None
                            overall_strip_geom: Optional[QgsGeometry] = None
                            graded_strip_attrs: Optional[dict] = None
                            overall_strip_attrs: Optional[dict] = None

                            for (
                                element_type,
                                geometry,
                                attributes,
                            ) in generated_elements_list:
                                target_layer = physical_layers.get(element_type)
                                if (
                                    target_layer is None
                                    or not target_layer.isEditable()
                                ):
                                    continue
                                if geometry is None or geometry.isEmpty():
                                    continue
                                if not geometry.isGeosValid():
                                    geometry = geometry.makeValid()
                                if (
                                    geometry is None
                                    or geometry.isEmpty()
                                    or not geometry.isGeosValid()
                                ):
                                    continue

                                if element_type == "GradedStrip":
                                    graded_strip_geom = geometry
                                    graded_strip_attrs = attributes
                                elif element_type == "OverallStrip":
                                    overall_strip_geom = geometry
                                    overall_strip_attrs = attributes

                                feature = QgsFeature(target_layer.fields())
                                feature.setGeometry(geometry)
                                for field_name, value in attributes.items():
                                    idx = feature.fieldNameIndex(field_name)
                                    if idx != -1:
                                        feature.setAttribute(idx, value)

                                add_ok, _ = target_layer.dataProvider().addFeatures(
                                    [feature]
                                )
                                if add_ok:
                                    physical_geom_features_added[element_type] = True
                                    any_physical_or_protection_ok = True
                                else:
                                    QgsMessageLog.logMessage(
                                        f"Warning: Failed add feature {element_type} for {runway_name_log}.",
                                        plugin_tag,
                                        level=Qgis.Warning,
                                    )

                            flyover_layer = physical_layers.get("FlyoverStrip")
                            if (
                                flyover_layer
                                and flyover_layer.isEditable()
                                and graded_strip_geom
                                and overall_strip_geom
                            ):
                                try:
                                    # Ensure inputs are valid before difference
                                    if not graded_strip_geom.isGeosValid():
                                        graded_strip_geom = (
                                            graded_strip_geom.makeValid()
                                        )
                                    if not overall_strip_geom.isGeosValid():
                                        overall_strip_geom = (
                                            overall_strip_geom.makeValid()
                                        )

                                    if (
                                        graded_strip_geom
                                        and overall_strip_geom
                                        and graded_strip_geom.isGeosValid()
                                        and overall_strip_geom.isGeosValid()
                                    ):
                                        flyover_geom = overall_strip_geom.difference(
                                            graded_strip_geom
                                        )
                                        if flyover_geom and not flyover_geom.isEmpty():
                                            flyover_geom = (
                                                flyover_geom.makeValid()
                                            )  # Validate result
                                            if (
                                                flyover_geom
                                                and not flyover_geom.isEmpty()
                                                and flyover_geom.isGeosValid()
                                            ):
                                                # Create feature for flyover area
                                                flyover_feat = QgsFeature(
                                                    flyover_layer.fields()
                                                )
                                                flyover_feat.setGeometry(flyover_geom)

                                                # --- MODIFIED ATTRIBUTE CALCULATION FOR FLYOVER ---
                                                flyover_attrs = (
                                                    {}
                                                )  # Start with an empty dict for flyover-specific attributes

                                                # 'rwy' and 'ref_mos' can be taken from overall_strip_attrs if available
                                                if overall_strip_attrs:
                                                    flyover_attrs["rwy"] = (
                                                        overall_strip_attrs.get("rwy")
                                                    )
                                                    flyover_attrs["ref_mos"] = (
                                                        overall_strip_attrs.get(
                                                            "ref_mos"
                                                        )
                                                    )

                                                flyover_attrs["desc"] = (
                                                    "Flyover Strip Area"
                                                )

                                                # Calculate len_m and wid_m as per your logic
                                                # len_m can be taken from either graded or overall strip length
                                                if (
                                                    graded_strip_attrs
                                                    and "len_m" in graded_strip_attrs
                                                ):
                                                    flyover_attrs["len_m"] = (
                                                        graded_strip_attrs["len_m"]
                                                    )
                                                elif (
                                                    overall_strip_attrs
                                                    and "len_m" in overall_strip_attrs
                                                ):  # Fallback to overall
                                                    flyover_attrs["len_m"] = (
                                                        overall_strip_attrs["len_m"]
                                                    )
                                                else:
                                                    flyover_attrs["len_m"] = (
                                                        None  # Or some default if neither is available
                                                    )

                                                if (
                                                    graded_strip_attrs
                                                    and overall_strip_attrs
                                                    and "wid_m" in graded_strip_attrs
                                                    and "wid_m" in overall_strip_attrs
                                                    and isinstance(
                                                        graded_strip_attrs["wid_m"],
                                                        (int, float),
                                                    )
                                                    and isinstance(
                                                        overall_strip_attrs["wid_m"],
                                                        (int, float),
                                                    )
                                                ):

                                                    overall_w = overall_strip_attrs[
                                                        "wid_m"
                                                    ]
                                                    graded_w = graded_strip_attrs[
                                                        "wid_m"
                                                    ]
                                                    if overall_w > graded_w:
                                                        flyover_attrs["wid_m"] = (
                                                            overall_w - graded_w
                                                        ) / 2.0
                                                    else:
                                                        flyover_attrs["wid_m"] = (
                                                            0.0  # Or None, if width is not positive
                                                        )
                                                        QgsMessageLog.logMessage(
                                                            f"Warning: Overall strip width not greater than graded strip width for {runway_name_log}. Flyover width set to 0.",
                                                            plugin_tag,
                                                            level=Qgis.Warning,
                                                        )
                                                else:
                                                    flyover_attrs["wid_m"] = None

                                                for (
                                                    field_name,
                                                    value,
                                                ) in flyover_attrs.items():
                                                    idx = flyover_feat.fieldNameIndex(
                                                        field_name
                                                    )
                                                    if idx != -1:
                                                        flyover_feat.setAttribute(
                                                            idx, value
                                                        )

                                                (
                                                    add_fly_ok,
                                                    _,
                                                ) = flyover_layer.dataProvider().addFeatures(
                                                    [flyover_feat]
                                                )
                                                if add_fly_ok:
                                                    physical_geom_features_added[
                                                        "FlyoverStrip"
                                                    ] = True
                                                    any_physical_or_protection_ok = True
                                                else:
                                                    QgsMessageLog.logMessage(
                                                        f"Warning: Failed add feature FlyoverStrip for {runway_name_log}.",
                                                        plugin_tag,
                                                        level=Qgis.Warning,
                                                    )
                                            else:
                                                QgsMessageLog.logMessage(
                                                    f"Warning: FlyoverStrip geometry invalid after difference/makeValid for {runway_name_log}.",
                                                    plugin_tag,
                                                    level=Qgis.Warning,
                                                )
                                        else:
                                            QgsMessageLog.logMessage(
                                                f"Warning: FlyoverStrip geometry is empty after difference for {runway_name_log}.",
                                                plugin_tag,
                                                level=Qgis.Warning,
                                            )
                                    else:
                                        QgsMessageLog.logMessage(
                                            f"Warning: Cannot calculate FlyoverStrip difference due to invalid input strip geometries for {runway_name_log}.",
                                            plugin_tag,
                                            level=Qgis.Warning,
                                        )
                                except Exception as e_diff:
                                    QgsMessageLog.logMessage(
                                        f"Warning: Error calculating FlyoverStrip difference for {runway_name_log}: {e_diff}",
                                        plugin_tag,
                                        level=Qgis.Warning,
                                    )
                            elif flyover_layer and flyover_layer.isEditable():
                                QgsMessageLog.logMessage(
                                    f"Info: Skipping FlyoverStrip for {runway_name_log}: Graded or Overall strip geometry missing.",
                                    plugin_tag,
                                    level=Qgis.Info,
                                )

                        except Exception as e_phys:
                            QgsMessageLog.logMessage(
                                f"Critical Error populating layers for {runway_name_log}: {e_phys}\n{traceback.format_exc()}",
                                plugin_tag,
                                level=Qgis.Critical,
                            )
                            continue

                    QgsMessageLog.logMessage(
                        "Finalizing and saving physical geometry & protection area layers...",
                        plugin_tag,
                        level=Qgis.Info,
                    )
                    any_layer_successfully_processed_in_this_block = False
                    project_root = QgsProject.instance().layerTreeRoot()

                    for element_type, temp_memory_layer in physical_layers.items():
                        if temp_memory_layer and temp_memory_layer.isValid():
                            if temp_memory_layer.isEditable():
                                if not temp_memory_layer.commitChanges():
                                    QgsMessageLog.logMessage(
                                        f"Warning: Failed to commit changes on temporary layer '{temp_memory_layer.name()}'. Features might be incomplete. Errors: {temp_memory_layer.commitErrors()}",
                                        plugin_tag,
                                        Qgis.Warning,
                                    )

                            if temp_memory_layer.featureCount() > 0:
                                display_name_for_final_layer = temp_memory_layer.name()
                                fields_for_final_layer = temp_memory_layer.fields()

                                qgis_geom_type_enum = temp_memory_layer.geometryType()
                                geom_type_str_for_final_layer = "Unknown"
                                if qgis_geom_type_enum == Qgis.GeometryType.Point:
                                    geom_type_str_for_final_layer = "Point"
                                elif qgis_geom_type_enum == Qgis.GeometryType.Line:
                                    geom_type_str_for_final_layer = "LineString"
                                elif qgis_geom_type_enum == Qgis.GeometryType.Polygon:
                                    geom_type_str_for_final_layer = "Polygon"
                                else:
                                    QgsMessageLog.logMessage(
                                        f"Warning: Unknown QGIS geometry type enum {qgis_geom_type_enum} for temp layer '{display_name_for_final_layer}'. Defaulting to 'Unknown'.",
                                        plugin_tag,
                                        Qgis.Warning,
                                    )

                                features_to_write = [
                                    QgsFeature(f)
                                    for f in temp_memory_layer.getFeatures()
                                ]

                                target_group_name = temp_memory_layer.customProperty(
                                    "target_group_node"
                                )
                                style_key_for_final_layer = str(
                                    temp_memory_layer.customProperty(
                                        "safeguarding_style_key", "Default Polygon"
                                    )
                                )

                                target_group_node: Optional[QgsLayerTreeGroup] = None
                                if target_group_name and isinstance(
                                    target_group_name, str
                                ):
                                    target_group_node = project_root.findGroup(
                                        target_group_name
                                    )

                                if not target_group_node:
                                    QgsMessageLog.logMessage(
                                        f"Warning: Target group '{target_group_name}' not found for '{display_name_for_final_layer}'. Using main plugin group.",
                                        plugin_tag,
                                        Qgis.Warning,
                                    )
                                    target_group_node = main_group

                                final_layer = self._create_and_add_layer(
                                    geometry_type_str=geom_type_str_for_final_layer,
                                    internal_name_base=element_type,
                                    display_name=display_name_for_final_layer,
                                    fields=fields_for_final_layer,
                                    features=features_to_write,
                                    layer_group=target_group_node,
                                    style_key=style_key_for_final_layer,
                                )
                                if final_layer:
                                    any_physical_or_protection_ok = True
                                    any_layer_successfully_processed_in_this_block = (
                                        True
                                    )
                            else:
                                QgsMessageLog.logMessage(
                                    f"Skipping final processing for '{temp_memory_layer.name()}': No features were present in its temporary layer.",
                                    plugin_tag,
                                    level=Qgis.Info,
                                )
                        else:
                            QgsMessageLog.logMessage(
                                f"Skipping final processing for element_type '{element_type}': Its temporary memory layer was None or invalid.",
                                plugin_tag,
                                Qgis.Warning,
                            )

                    if (
                        not any_layer_successfully_processed_in_this_block
                        and physical_layers
                    ):
                        QgsMessageLog.logMessage(
                            "Warning: No physical geometry or protection area layers were successfully processed/saved in this block.",
                            plugin_tag,
                            Qgis.Warning,
                        )

                    if physical_geom_group:
                        for rwy_data in processed_runway_data_list:
                            cl_layer = rwy_data.get("centreline_layer")
                            if cl_layer:
                                cl_node = project_root.findLayer(cl_layer.id())
                                if cl_node:
                                    cloned_node = cl_node.clone()
                                    physical_geom_group.insertChildNode(0, cloned_node)
                                    cl_node.parent().removeChildNode(cl_node)

                else:
                    if not physical_geom_group:
                        QgsMessageLog.logMessage(
                            "Failed to create 'Physical Geometry' subgroup.",
                            plugin_tag,
                            level=Qgis.Warning,
                        )
                    if not protection_area_group:
                        QgsMessageLog.logMessage(
                            "Failed to create 'Runway Protection Areas' subgroup.",
                            plugin_tag,
                            level=Qgis.Warning,
                        )

            guideline_groups = self._create_guideline_groups(main_group)

            ofz_group = None
            if guideline_groups.get("F"):
                ofz_group = guideline_groups["F"].addGroup(
                    self.tr("OLS Obstacle Free Zone")
                )

            self.reference_elevation_datum = self._calculate_reference_elevation_datum(
                self.arp_elevation_amsl, runway_input_list
            )
            pa_runways_exist = any(
                "PA" in rwy.get("type1", "") or "PA" in rwy.get("type2", "")
                for rwy in runway_input_list
                if rwy
            )
            if self.reference_elevation_datum is None and pa_runways_exist:
                QgsMessageLog.logMessage(
                    "Aborting OLS generation: RED calculation failed and precision approach runways exist.",
                    plugin_tag,
                    level=Qgis.Critical,
                )
                self.iface.messageBar().pushMessage(
                    self.tr("Error"),
                    self.tr(
                        "Reference Elevation Datum calculation failed. Cannot generate OLS for precision runways."
                    ),
                    level=Qgis.Critical,
                    duration=10,
                )

            guideline_c_processed = False
            guideline_d_processed = False
            guideline_g_processed = False
            if arp_point and guideline_groups.get("C"):
                guideline_c_processed = self.process_guideline_c(
                    arp_point, icao_code, target_crs, guideline_groups["C"]
                )

            if arp_point and guideline_groups.get("D"):
                guideline_d_processed = self.process_guideline_d(
                    arp_point, icao_code, target_crs, guideline_groups["D"]
                )
            elif not arp_point and guideline_groups.get("D"):
                QgsMessageLog.logMessage(
                    "Guideline D (Wind Turbine) skipped: ARP point not available.",
                    plugin_tag,
                    level=Qgis.Info,
                )

            if cns_input_list and guideline_groups.get("G"):
                try:
                    guideline_g_processed = self.process_guideline_g(
                        cns_input_list, icao_code, target_crs, guideline_groups["G"]
                    )
                except Exception as e_proc_g:
                    QgsMessageLog.logMessage(
                        f"Critical error processing Guideline G (CNS): {e_proc_g}\n{traceback.format_exc()}",
                        plugin_tag,
                        level=Qgis.Critical,
                    )
            elif not cns_input_list:
                QgsMessageLog.logMessage(
                    "Guideline G (CNS) skipped: No valid CNS facilities data provided.",
                    plugin_tag,
                    level=Qgis.Info,
                )

            any_guideline_processed_ok = self._process_runways_part2(
                processed_runway_data_list,
                guideline_groups,
                specialised_safeguarding_group,
                ofz_group,
            )

            airport_wide_ols_processed = False
            if guideline_groups.get("F") and processed_runway_data_list:
                if self.reference_elevation_datum is not None:
                    try:
                        airport_wide_ols_processed = self._generate_airport_wide_ols(
                            processed_runway_data_list,
                            guideline_groups["F"],
                            self.reference_elevation_datum,
                            icao_code,
                        )
                        if airport_wide_ols_processed:
                            any_guideline_processed_ok = True
                    except Exception as e_ols_wide:
                        QgsMessageLog.logMessage(
                            f"Critical Error generating Airport-Wide OLS: {e_ols_wide}\n{traceback.format_exc()}",
                            plugin_tag,
                            level=Qgis.Critical,
                        )
                        self.iface.messageBar().pushMessage(
                            self.tr("Error"),
                            self.tr(
                                "Failed to generate airport-wide OLS surfaces. Check logs."
                            ),
                            level=Qgis.Critical,
                            duration=10,
                        )
                else:
                    QgsMessageLog.logMessage(
                        "Skipping Airport-Wide OLS (IHS, Conical, etc.): Reference Elevation Datum calculation failed or was not possible.",
                        plugin_tag,
                        level=Qgis.Warning,
                    )
            elif not processed_runway_data_list:
                QgsMessageLog.logMessage(
                    "Skipping Airport-Wide OLS (IHS, Conical, etc.): No valid runway data was processed.",
                    plugin_tag,
                    level=Qgis.Info,
                )

            self._final_feedback(
                main_group,
                root,
                icao_code,
                arp_layer_created,
                met_layers_created_ok,
                any_runway_base_data_ok,
                guideline_c_processed,
                guideline_d_processed,
                guideline_g_processed,
                any_guideline_processed_ok,
                len(processed_runway_data_list),
                len(runway_input_list),
                any_physical_or_protection_ok,
            )

            QgsMessageLog.logMessage(
                "--- Safeguarding Processing Finished ---", plugin_tag, level=Qgis.Info
            )

            if self.successfully_generated_layers:
                if self.dlg:
                    self.dlg.accept()
            else:
                pass

    # ============================================================
    # Helper Methods
    # ============================================================

    def _setup_main_group(
        self, root_node: QgsLayerTreeNode, group_name: str, project: QgsProject
    ) -> Optional[QgsLayerTreeGroup]:
        """Finds and clears or creates the main layer group."""
        existing_group = root_node.findGroup(group_name)
        if existing_group:
            QgsMessageLog.logMessage(
                f"Removing existing group: {group_name}", PLUGIN_TAG, level=Qgis.Info
            )
            self._remove_group_recursively(existing_group, project)
            parent_node = existing_group.parent()
            if parent_node:
                parent_node.removeChildNode(existing_group)
        main_group = root_node.addGroup(group_name)
        if not main_group:
            QgsMessageLog.logMessage(
                f"Failed create group: {group_name}", PLUGIN_TAG, level=Qgis.Critical
            )
            return None
        return main_group

    def _remove_group_recursively(
        self, group_node: QgsLayerTreeGroup, project: QgsProject
    ):
        """Helper to remove layers within a group and its subgroups."""
        if not group_node:
            return
        children_copy = list(group_node.children())  # Iterate over copy
        for node in children_copy:
            if isinstance(node, QgsLayerTreeLayer):
                layer_id = node.layerId()
                if layer_id and project.mapLayer(layer_id):
                    project.removeMapLayer(layer_id)
            elif isinstance(node, QgsLayerTreeGroup):
                self._remove_group_recursively(node, project)
                group_node.removeChildNode(node)  # Remove subgroup after its contents

    def _process_runways_part1(
        self,
        main_group: QgsLayerTreeGroup,
        project: QgsProject,
        target_crs: QgsCoordinateReferenceSystem,
        icao_code: str,
        runway_input_list: List[Dict[str, Any]],
    ) -> tuple[List[Dict[str, Any]], bool]:
        """Processes validated runway inputs, creates centrelines, returns enriched data list."""
        plugin_tag = PLUGIN_TAG
        processed_runway_data_list = []
        any_runway_base_data_ok = False
        if not runway_input_list:
            return [], False

        QgsMessageLog.logMessage(
            f"Processing {len(runway_input_list)} runway(s)...",
            plugin_tag,
            level=Qgis.Info,
        )

        for runway_data in runway_input_list:
            index = runway_data.get("original_index", "?")
            short_runway_name = f"RWY_{index}_ERR"
            centreline_layer = None
            runway_processed_ok = False
            try:
                designator_num = runway_data.get("designator_num")
                suffix = runway_data.get("suffix", "")
                thr_point = runway_data.get("thr_point")
                rec_thr_point = runway_data.get("rec_thr_point")
                arc_num_val = runway_data.get("arc_num")
                arc_let_val = runway_data.get("arc_let")
                if designator_num is None or thr_point is None or rec_thr_point is None:
                    QgsMessageLog.logMessage(
                        f"Skipping centreline for Runway Index {index}: Missing essential data (Designator Num/Points).",
                        plugin_tag,
                        level=Qgis.Warning,
                    )
                    continue

                # Generate runway name (keep this logic)
                primary_desig = f"{designator_num:02d}{suffix}"
                reciprocal_num = (
                    (designator_num + 18)
                    if designator_num <= 18
                    else (designator_num - 18)
                )
                reciprocal_suffix_map = {"L": "R", "R": "L", "C": "C", "": ""}
                reciprocal_suffix = reciprocal_suffix_map.get(suffix, "")
                reciprocal_desig = f"{reciprocal_num:02d}{reciprocal_suffix}"
                short_runway_name = f"{primary_desig}/{reciprocal_desig}"
                runway_data["short_name"] = short_runway_name

                # Call the helper to create the layer
                # Pass target_crs as it might be needed by distance calcs inside helpers called by create_runway_centreline_layer
                # ### MODIFIED: Pass arc_num_val and arc_let_val ###
                centreline_layer = self.create_runway_centreline_layer(
                    thr_point,
                    rec_thr_point,
                    short_runway_name,
                    target_crs,
                    main_group,
                    arc_num_val,
                    arc_let_val,
                )

                # Check the result from the helper
                if centreline_layer:
                    runway_data["centreline_layer"] = centreline_layer
                    any_runway_base_data_ok = True
                    runway_processed_ok = True
                else:
                    runway_data["centreline_layer"] = None
                    # Failure already logged by create_runway_centreline_layer or _create_and_add_layer
                    QgsMessageLog.logMessage(
                        f"Failed create/add centreline layer for {short_runway_name}.",
                        plugin_tag,
                        level=Qgis.Warning,
                    )

                if runway_processed_ok:
                    processed_runway_data_list.append(runway_data)

            except Exception as e:
                # Catch unexpected errors during the processing of this specific runway's base data
                QgsMessageLog.logMessage(
                    f"Critical error processing base data for runway {short_runway_name} (Index {index}): {e}\n{traceback.format_exc()}",
                    plugin_tag,
                    level=Qgis.Critical,
                )
                # if centreline_layer and centreline_layer.isValid() and project.mapLayer(centreline_layer.id()): project.removeMapLayer(centreline_layer.id())
                continue  # Process next runway

            # QgsMessageLog.logMessage(f"Finished processing centrelines. {len(processed_runway_data_list)}/{len(runway_input_list)} successful.", plugin_tag, level=Qgis.Info)
        return processed_runway_data_list, any_runway_base_data_ok

    def _create_guideline_groups(
        self, main_group: QgsLayerTreeGroup
    ) -> Dict[str, Optional[QgsLayerTreeGroup]]:
        """Creates the top-level groups for each guideline."""
        guideline_defs = {
            "A": "Guideline A: Noise",
            "B": "Guideline B: Windshear",
            "C": "Guideline C: Wildlife",
            "D": "Guideline D: Wind Turbine",
            "E": "Guideline E: Lighting",
            "F": "Guideline F: Airspace",
            "G": "Guideline G: CNS",
            "H": "Guideline H: Heli",
            "I": "Guideline I: Safety",
        }
        guideline_groups: Dict[str, Optional[QgsLayerTreeGroup]] = {}
        for key, name in guideline_defs.items():
            grp = main_group.addGroup(self.tr(name))
            guideline_groups[key] = grp
            if not grp:
                QgsMessageLog.logMessage(
                    f"Failed create group: {name}", PLUGIN_TAG, level=Qgis.Warning
                )
        return guideline_groups

    def _sanitize_filename(self, name: str, replace_char: str = "_") -> str:
        """Removes or replaces characters invalid for filenames."""
        # Remove leading/trailing whitespace
        name = name.strip()
        # Replace invalid characters (common examples, might need adjustment)
        name = re.sub(r'[<>:"/\\|?* ]+', replace_char, name)
        # Replace multiple consecutive replacement characters with a single one
        name = re.sub(f"{replace_char}+", replace_char, name)
        # Remove leading/trailing replacement characters
        name = name.strip(replace_char)
        # Limit length (optional)
        # max_len = 100
        # if len(name) > max_len: name = name[:max_len].strip(replace_char)
        if not name:
            name = "unnamed_layer"  # Fallback if sanitization results in empty string

        return name.rstrip(".") or "unnamed_layer"

    def _create_and_add_layer(
        self,
        geometry_type_str: str,
        internal_name_base: str,
        display_name: str,
        fields: QgsFields,
        features: List[QgsFeature],
        layer_group: QgsLayerTreeGroup,
        style_key: str,
    ) -> Optional[QgsVectorLayer]:
        """
        Helper to create/populate a layer, add to project/group, and apply style.
        Handles both memory layer creation and file writing based on self.output_mode.
        Logs warnings or errors on failure. Returns the added layer or None.
        """
        plugin_tag = PLUGIN_TAG
        project = QgsProject.instance()
        target_crs = project.crs()
        target_crs.authid()

        if not features:
            QgsMessageLog.logMessage(
                f"Skipping layer '{display_name}': No features generated.",
                plugin_tag,
                level=Qgis.Info,
            )
            return None

        try:
            uri = f"{geometry_type_str}?crs={target_crs.authid()}"
            layer = QgsVectorLayer(uri, display_name, "memory")
            if not layer.isValid():
                QgsMessageLog.logMessage(
                    f"Failed to create layer '{display_name}' with URI '{uri}'",
                    plugin_tag,
                    Qgis.Critical,
                )
                return None

            layer.startEditing()
            layer.dataProvider().addAttributes(fields)
            layer.updateFields()
            layer.dataProvider().addFeatures(features)
            layer.commitChanges()

            # Apply style if available
            if style_key in self.style_map:
                style_filename = self.style_map[style_key]
                style_path = os.path.join(self.plugin_dir, "styles", style_filename)
                if os.path.exists(style_path):
                    try:
                        layer.loadNamedStyle(style_path)
                        layer.triggerRepaint()
                    except Exception as e:
                        QgsMessageLog.logMessage(
                            f"Exception during loadNamedStyle for '{style_path}' on layer '{display_name}': {e}",
                            plugin_tag,
                            level=Qgis.Warning,
                        )
                else:
                    QgsMessageLog.logMessage(
                        f"Style file not found: '{style_path}' for key '{style_key}'",
                        plugin_tag,
                        Qgis.Warning,
                    )

            # Save to file if using file output
            if self.output_mode == "file":
                if not all(
                    [
                        self.output_path,
                        self.output_format_driver,
                        self.output_format_extension,
                    ]
                ):
                    QgsMessageLog.logMessage(
                        f"Skipping file save for '{display_name}': Output path/driver/extension missing.",
                        plugin_tag,
                        level=Qgis.Critical,
                    )
                    return layer

                QgsMessageLog.logMessage(
                    f"display_name = '{display_name}'", plugin_tag, Qgis.Info
                )

                # Sanitize filename and construct full path
                name_without_ext = os.path.splitext(display_name)[0]
                safe_name = self._sanitize_filename(name_without_ext)
                full_path = os.path.join(
                    self.output_path, f"{safe_name}{self.output_format_extension}"
                )

                temp_layer = QgsVectorLayer(uri, f"temp_{internal_name_base}", "memory")
                temp_layer.dataProvider().addAttributes(fields)
                temp_layer.updateFields()
                temp_layer.dataProvider().addFeatures(features)

                result = QgsVectorFileWriter.writeAsVectorFormat(
                    temp_layer,
                    full_path,
                    "UTF-8",
                    temp_layer.crs(),
                    self.output_format_driver,
                )

                if (
                    isinstance(result, tuple)
                    and result[0] == QgsVectorFileWriter.NoError
                ):
                    QgsMessageLog.logMessage(
                        f"Layer '{display_name}' successfully written to '{full_path}'.",
                        plugin_tag,
                        Qgis.Info,
                    )
                    loaded_layer = self.iface.addVectorLayer(
                        full_path, display_name, "ogr"
                    )
                    if loaded_layer and loaded_layer.isValid():
                        root = project.layerTreeRoot()
                        loaded_node = root.findLayer(loaded_layer.id())
                        if loaded_node:
                            cloned_node = loaded_node.clone()
                            layer_group.insertChildNode(0, cloned_node)
                            loaded_node.parent().removeChildNode(loaded_node)
                        loaded_layer.setCustomProperty(
                            "safeguarding_style_key", style_key
                        )
                        self._apply_style(loaded_layer, self.style_map)
                        self.successfully_generated_layers.append(loaded_layer)
                        return loaded_layer
                    else:
                        QgsMessageLog.logMessage(
                            f"Failed to reload written layer '{display_name}' from '{full_path}'.",
                            plugin_tag,
                            Qgis.Warning,
                        )
                else:
                    QgsMessageLog.logMessage(
                        f"Error writing layer '{display_name}' to file: {result}",
                        plugin_tag,
                        Qgis.Warning,
                    )

            # Add to group in TOC for memory output
            QgsProject.instance().addMapLayer(layer, False)
            layer_group.addLayer(layer)
            self.successfully_generated_layers.append(layer)

            # QgsMessageLog.logMessage(f"Layer '{display_name}' created and added successfully.", plugin_tag, Qgis.Info)
            return layer

        except Exception as e:
            QgsMessageLog.logMessage(
                f"Error creating/adding layer '{display_name}': {e}",
                plugin_tag,
                Qgis.Critical,
            )
            return None

    def _apply_style(self, layer: QgsVectorLayer, style_map: Dict[str, str]):
        """
        Applies QML style based on custom property.
        Minimal checking: Attempts load, logs only critical exceptions.
        """
        plugin_tag = PLUGIN_TAG
        if not layer or not layer.isValid():
            return
        layer_name = layer.name() or f"Layer {layer.id()}"
        qml_filename = None
        style_key = layer.customProperty("safeguarding_style_key")
        try:
            # Find the QML filename (same logic)
            if style_key:
                qml_filename = style_map.get(str(style_key))
            if not qml_filename:  # Fallback logic
                geom_type = layer.geometryType()
                # Define fallback keys based on geometry type
                default_key_map = {
                    Qgis.GeometryType.Polygon: "Default Polygon",
                    Qgis.GeometryType.Line: "Default Line",
                    Qgis.GeometryType.Point: "Default Point",
                }
                default_key = default_key_map.get(geom_type)
                if default_key:
                    qml_filename = style_map.get(default_key)

            if qml_filename:
                # Construct the path relative to the plugin directory
                qml_path = os.path.join(self.plugin_dir, "styles", qml_filename)

                # --- Simplest Approach: Try loading, ignore return value ---
                try:
                    # Directly attempt to load the style
                    layer.loadNamedStyle(qml_path)
                    # Trigger repaint assuming load worked if no exception occurred
                    layer.triggerRepaint()
                except Exception as e_load:
                    # Log only if loadNamedStyle itself raises an exception
                    # This is less common than it returning an error message/code
                    QgsMessageLog.logMessage(
                        f"Exception during loadNamedStyle for '{qml_path}' on layer '{layer_name}': {e_load}",
                        plugin_tag,
                        level=Qgis.Warning,
                    )
                # --- End Simplest Approach ---

            else:  # No style key or fallback found for this layer type
                QgsMessageLog.logMessage(
                    f"Info: No specific or default style key found for layer '{layer_name}'. QGIS default will apply.",
                    plugin_tag,
                    level=Qgis.Info,
                )

        except Exception as e:
            # Catch errors in the overall style finding/path logic
            QgsMessageLog.logMessage(
                f"Critical Error applying style logic to '{layer_name}': {e}\n{traceback.format_exc()}",
                plugin_tag,
                level=Qgis.Critical,
            )

    def _interpolate_along_edge(self, edge_pts, target_elev):
        """
        Interpolates along an edge (list of (QgsPointXY, elev)) to find XY at target elevation.
        Returns QgsPointXY or None if out of range.
        """
        for i in range(len(edge_pts) - 1):
            elev1, elev2 = edge_pts[i][1], edge_pts[i + 1][1]
            if (elev1 - target_elev) * (elev2 - target_elev) <= 0:
                # target_elev is between elev1 and elev2, or equal to one
                t = (
                    (target_elev - elev1) / (elev2 - elev1)
                    if abs(elev2 - elev1) > 1e-9
                    else 0
                )
                x = edge_pts[i][0].x() + t * (
                    edge_pts[i + 1][0].x() - edge_pts[i][0].x()
                )
                y = edge_pts[i][0].y() + t * (
                    edge_pts[i + 1][0].y() - edge_pts[i][0].y()
                )
                return QgsPointXY(x, y)
        return None

    # Make sure _try_get_arp_elevation_from_layer helper exists or is implemented
    def _try_get_arp_elevation_from_layer(
        self, arp_layer: QgsVectorLayer
    ) -> Optional[float]:
        """Attempts to get elevation from Z value or attribute of the first ARP feature."""
        if not arp_layer or not arp_layer.isValid() or arp_layer.featureCount() == 0:
            return None
        try:
            feature = next(arp_layer.getFeatures())  # Get the first feature
            geom = feature.geometry()
            if geom and geom.hasZ():
                point_z = geom.vertexAt(0)  # For PointZ geometry
                if point_z and isinstance(point_z.z(), (int, float)):
                    return float(point_z.z())

            # Fallback: Check for an 'elev_m' attribute
            elev_field_idx = feature.fieldNameIndex("elev_m")
            if elev_field_idx != -1:
                elev_val = feature.attribute(elev_field_idx)
                if isinstance(elev_val, (int, float)):
                    return float(elev_val)
                # Try converting if it's a string representation of a number
                elif isinstance(elev_val, str):
                    try:
                        return float(elev_val)
                    except ValueError:
                        pass  # Ignore conversion errors

        except Exception as e:
            QgsMessageLog.logMessage(
                f"Error trying to get ARP elevation from layer: {e}",
                PLUGIN_TAG,
                level=Qgis.Warning,
            )
        return None

    def _get_runway_midpoint(
        self, thr_point: QgsPointXY, rec_thr_point: QgsPointXY
    ) -> Optional[QgsPointXY]:
        """Calculates the midpoint of the line segment between two points."""
        if not thr_point or not rec_thr_point:
            return None
        try:
            mid_x = (thr_point.x() + rec_thr_point.x()) / 2.0
            mid_y = (thr_point.y() + rec_thr_point.y()) / 2.0
            return QgsPointXY(mid_x, mid_y)
        except Exception as e:
            QgsMessageLog.logMessage(
                f"Error calculating runway midpoint: {e}",
                PLUGIN_TAG,
                level=Qgis.Warning,
            )
            return None

    def _process_runways_part2(
        self,
        processed_runway_data_list: List[dict],
        guideline_groups: Dict[str, Optional[QgsLayerTreeGroup]],
        specialised_group_node: Optional[QgsLayerTreeGroup],
        ofz_group: Optional[QgsLayerTreeGroup],
    ) -> bool:
        """Processes runway-specific guidelines."""
        any_guideline_processed_ok = False
        if not processed_runway_data_list:
            return False
        for runway_data in processed_runway_data_list:
            rwy_name = runway_data.get(
                "short_name", f"RWY_{runway_data.get('original_index', '?')}"
            )
            run_success_flags = []
            try:  # Standard Guidelines
                if guideline_groups.get("B"):
                    run_success_flags.append(
                        self.process_guideline_b(runway_data, guideline_groups["B"])
                    )
                if guideline_groups.get("E"):
                    run_success_flags.append(
                        self.process_guideline_e(runway_data, guideline_groups["E"])
                    )
                if guideline_groups.get("F"):
                    run_success_flags.append(
                        self.process_guideline_f(
                            runway_data, guideline_groups["F"], ofz_group
                        )
                    )  # F = OLS App/TOCS
                if guideline_groups.get("I"):
                    run_success_flags.append(
                        self.process_guideline_i(runway_data, guideline_groups["I"])
                    )
                # Add calls for other guidelines (A, F, H) here if implemented

                # Specialised Surfaces
                if specialised_group_node:
                    run_success_flags.append(
                        self.process_raoa(runway_data, specialised_group_node)
                    )
                    # <<< ADD CALL for Taxiway Separation >>>
                    run_success_flags.append(
                        self.process_taxiway_separation(
                            runway_data, specialised_group_node
                        )
                    )
                else:
                    QgsMessageLog.logMessage(
                        f"Skipping Specialised surfaces for {rwy_name}: Group missing.",
                        PLUGIN_TAG,
                        level=Qgis.Warning,
                    )

                if any(run_success_flags):
                    any_guideline_processed_ok = True
            except Exception as e_guideline:
                QgsMessageLog.logMessage(
                    f"Error processing guidelines/specialised for {rwy_name}: {e_guideline}",
                    PLUGIN_TAG,
                    level=Qgis.Critical,
                )
        return any_guideline_processed_ok

    def _final_feedback(
        self,
        main_group: Optional[QgsLayerTreeGroup],
        root_node: QgsLayerTreeNode,
        icao_code: str,
        arp_ok: bool,
        met_ok: bool,
        rwy_base_ok: bool,
        guide_c_ok: bool,
        guide_d_ok: bool,
        guide_g_ok: bool,
        guide_rwy_ok: bool,
        processed_rwy_count: int,
        total_runways_in_input: int,
        physical_protection_ok: bool,
    ):
        """Provides final user feedback."""
        if (
            main_group is None and self.output_mode == "memory"
        ):  # If no group and memory, something is wrong
            self.iface.messageBar().pushMessage(
                self.tr("Error"),
                self.tr("Processing error: Main layer group not created."),
                level=Qgis.Critical,
            )
            return

        project = QgsProject.instance()

        # Check if any layers were successfully generated and added to our tracking list
        anything_successfully_generated = bool(self.successfully_generated_layers)

        if anything_successfully_generated:
            msg_parts = [f"{self.tr('Processing complete for')} {icao_code}. "]

            # Add summary of what was processed (optional, can be kept brief)
            # For brevity, we can simplify this part or remove it if the layer count is enough.
            # Example of a brief summary:
            num_layers_created = len(self.successfully_generated_layers)
            msg_parts.append(
                self.tr("{n} layer(s) generated. ").format(n=num_layers_created)
            )

            output_destination_message = ""
            if self.output_mode == "file" and self.output_path:
                output_destination_message = self.tr(
                    "Output files saved to directory: {path}"
                ).format(path=self.output_path)

                msg_parts.append(output_destination_message)
            elif self.output_mode == "memory":
                output_destination_message = self.tr("Layers created in memory.")
                msg_parts.append(output_destination_message)

            final_user_message = " ".join(msg_parts).strip()
            final_log_message = f"{final_user_message}"  # For QgsMessageLog

            self.iface.messageBar().pushMessage(
                self.tr("Success"), final_user_message, level=Qgis.Success, duration=10
            )  # Increased duration
            QgsMessageLog.logMessage(
                final_log_message, PLUGIN_TAG, level=Qgis.Success
            )  # Log overall success

            if (
                main_group
            ):  # Only expand group if it exists (it might not if only file output and no group made)
                main_group.setExpanded(True)
        else:
            # This case means self.successfully_generated_layers is empty
            self.iface.messageBar().pushMessage(
                self.tr("Process Finished"),
                self.tr("No layers were generated. Check logs for warnings or errors."),
                level=Qgis.Warning,
                duration=7,
            )
            QgsMessageLog.logMessage(
                "Processing finished, but no layers were successfully generated or added.",
                PLUGIN_TAG,
                level=Qgis.Warning,
            )
            if main_group and root_node.findGroup(
                main_group.name()
            ):  # Only try to remove group if it was created
                self._remove_group_recursively(main_group, project)
                if main_group.parent():
                    main_group.parent().removeChildNode(main_group)

    # --- Geometry Creation Helpers ---
    def create_arp_layer(
        self,
        arp_point: QgsPointXY,
        arp_east: Optional[float],
        arp_north: Optional[float],
        icao_code: str,
        crs: QgsCoordinateReferenceSystem,
        layer_group: QgsLayerTreeGroup,
        arp_elevation: Optional[float] = None,
    ) -> Optional[QgsVectorLayer]:  # Added elevation param
        """Creates the ARP point layer using the helper."""
        # Add Elevation field
        fields = QgsFields()
        fields.append(QgsField("icao_code", QVariant.String))
        fields.append(QgsField("desc", QVariant.String))
        fields.append(QgsField("coord_east", QVariant.Double))
        fields.append(QgsField("coord_north", QVariant.Double))
        fields.append(QgsField("elev_m", QVariant.Double, "Elevation (AMSL)", 10, 2))
        # fields.append(QgsField("red", QVariant.Double, "Reference Elevation Datum", 10, 2))

        try:
            # Attempt to create geometry with Z value if elevation provided
            arp_geom: Optional[QgsGeometry] = None
            if arp_elevation is not None:
                try:  # QgsPoint requires QGIS 3.x, use QgsPointXY as fallback if needed
                    from qgis.core import QgsPoint  # type: ignore

                    arp_geom = QgsGeometry(
                        QgsPoint(arp_point.x(), arp_point.y(), arp_elevation)
                    )
                except ImportError:
                    arp_geom = QgsGeometry.fromPointXY(arp_point)  # Fallback to 2D
                    QgsMessageLog.logMessage(
                        "QgsPoint (3D) not available, creating 2D ARP geometry.",
                        PLUGIN_TAG,
                        level=Qgis.Warning,
                    )
            else:
                arp_geom = QgsGeometry.fromPointXY(arp_point)

            if arp_geom is None or arp_geom.isNull():
                return None

            feature = QgsFeature(fields)
            feature.setGeometry(arp_geom)
            east_attr = arp_east if arp_east is not None else arp_point.x()
            north_attr = arp_north if arp_north is not None else arp_point.y()
            # Set attributes including elevation
            feature.setAttributes(
                [
                    icao_code,
                    f"Aerodrome Reference Point",
                    east_attr,
                    north_attr,
                    arp_elevation,
                ]
            )
            return self._create_and_add_layer(
                "Point",
                f"arp_{icao_code}",
                f"{icao_code} {self.tr('ARP')}",
                fields,
                [feature],
                layer_group,
                "ARP",
            )
        except Exception as e:
            QgsMessageLog.logMessage(
                f"Error in create_arp_layer: {e}", PLUGIN_TAG, level=Qgis.Critical
            )
            return None

    def _create_centered_oriented_square(
        self, center_point: QgsPointXY, side_length: float, description: str = "Square"
    ) -> Optional[QgsGeometry]:
        """Creates a square polygon centered on a point."""
        plugin_tag = PLUGIN_TAG
        if not center_point or side_length <= 0:
            # Log reason for skipping if inputs invalid
            QgsMessageLog.logMessage(
                f"Skipping '{description}': Invalid center point or side length ({side_length}).",
                plugin_tag,
                level=Qgis.Warning,
            )
            return None
        try:
            half_side = side_length / 2.0
            # Calculate corners (keep logic)
            min_x = center_point.x() - half_side
            max_x = center_point.x() + half_side
            min_y = center_point.y() - half_side
            max_y = center_point.y() + half_side
            sw = QgsPointXY(min_x, min_y)
            se = QgsPointXY(max_x, min_y)
            ne = QgsPointXY(max_x, max_y)
            nw = QgsPointXY(min_x, max_y)
            # Call the main polygon creator (which logs its own warnings on failure)
            return self._create_polygon_from_corners([sw, se, ne, nw], description)
        except Exception as e:
            QgsMessageLog.logMessage(
                f"Warning: Error during geometry calculation for '{description}': {e}",
                plugin_tag,
                level=Qgis.Warning,
            )
            return None

    def create_runway_centreline_layer(
        self,
        point1: QgsPointXY,
        point2: QgsPointXY,
        runway_name: str,
        crs: QgsCoordinateReferenceSystem,  # CRS needed by caller, not directly used here now
        layer_group: QgsLayerTreeGroup,
        arc_num_val: Optional[str] = None,
        arc_let_val: Optional[str] = None,
    ) -> Optional[QgsVectorLayer]:
        """Creates the runway centreline layer using the helper."""
        plugin_tag = PLUGIN_TAG

        try:
            # Validate input points
            if not isinstance(point1, QgsPointXY) or not isinstance(point2, QgsPointXY):
                QgsMessageLog.logMessage(
                    f"Cannot create Centreline for {runway_name}: Invalid input point types.",
                    plugin_tag,
                    level=Qgis.Warning,
                )
                return None
            if point1.compare(point2, epsilon=1e-6):
                QgsMessageLog.logMessage(
                    f"Cannot create Centreline for {runway_name}: Start and end points are identical.",
                    plugin_tag,
                    level=Qgis.Warning,
                )
                return None

            # Define fields
            fields = QgsFields(
                [
                    QgsField("rwy", QVariant.String),
                    QgsField("len_m", QVariant.Double),
                    QgsField(
                        "rwy_head", QVariant.Double, "Runway Heading (degrees)", 10, 3
                    ),
                    QgsField(
                        "reciprocal_head",
                        QVariant.Double,
                        "Reciprocal Heading (degrees)",
                        10,
                        3,
                    ),
                    QgsField("toda", QVariant.String),
                    QgsField("tora", QVariant.String),
                    QgsField("lda", QVariant.String),
                    QgsField("asda", QVariant.String),
                    QgsField("arc_num", QVariant.String, "arc_num", 5),
                    QgsField("arc_let", QVariant.String, "arc_let", 5),
                ]
            )

            # Create geometry
            line_geom = QgsGeometry(QgsLineString([point1, point2]))
            if line_geom.isNull() or line_geom.isEmpty():
                QgsMessageLog.logMessage(
                    f"Cannot create Centreline for {runway_name}: Generated line geometry is null or empty.",
                    plugin_tag,
                    level=Qgis.Warning,
                )
                return None

            # Calculate length (handle potential None)
            length = line_geom.length()
            length_attr = round(length, 3) if length is not None else None

            # Get Azimuths
            rwy_params = self._get_runway_parameters(point1, point2)
            azimuth_attr = None
            reciprocal_azimuth_attr = None
            if rwy_params:
                azimuth_attr = (
                    round(rwy_params.get("azimuth_p_r"), 3)
                    if rwy_params.get("azimuth_p_r") is not None
                    else None
                )
                reciprocal_azimuth_attr = (
                    round(rwy_params.get("azimuth_r_p"), 3)
                    if rwy_params.get("azimuth_r_p") is not None
                    else None
                )
            else:
                QgsMessageLog.logMessage(
                    f"Could not calculate azimuths for centreline {runway_name}",
                    plugin_tag,
                    level=Qgis.Warning,
                )

            # Prepare feature
            feature = QgsFeature(fields)
            feature.setGeometry(line_geom)
            feature.setAttributes(
                [
                    runway_name,
                    length_attr,
                    azimuth_attr,
                    reciprocal_azimuth_attr,
                    None,  # TODA - blank for now
                    None,  # TORA - blank for now
                    None,  # LDA - blank for now
                    None,  # ASDA - blank for now
                    arc_num_val,
                    arc_let_val,
                ]
            )

            # Call the layer creation helper (which now handles its own logging)
            layer = self._create_and_add_layer(
                "LineString",
                f"cl_{runway_name.replace('/', '_')}",
                f"{self.tr('RWY')} {runway_name} {self.tr('Centreline')}",
                fields,
                [feature],
                layer_group,
                "Runway Centreline",  # Style key
            )
            return layer  # Return the result from the helper (layer object or None)

        except Exception as e:
            # Catch unexpected errors during geometry/feature prep
            QgsMessageLog.logMessage(
                f"Critical error creating Centreline feature/geometry for {runway_name}: {e}\n{traceback.format_exc()}",
                plugin_tag,
                level=Qgis.Critical,
            )
            return None

    def _create_offset_rectangle(
        self,
        start_point: QgsPointXY,
        outward_azimuth_degrees: float,
        far_edge_offset: float,
        zone_length_backward: float,
        half_width: float,
        description: str = "Offset Rectangle",
    ) -> Optional[QgsGeometry]:
        """Creates a rectangle offset from a point along an azimuth."""
        plugin_tag = PLUGIN_TAG
        if start_point is None or half_width <= 0:
            QgsMessageLog.logMessage(
                f"Skipping '{description}': Invalid start point or half width ({half_width}).",
                plugin_tag,
                level=Qgis.Warning,
            )
            return None
        try:
            # Calculate points (keep logic)
            backward_azimuth = (outward_azimuth_degrees + 180.0) % 360.0
            az_perp_r = (outward_azimuth_degrees + 90.0) % 360.0
            az_perp_l = (outward_azimuth_degrees - 90.0 + 360.0) % 360.0
            far_edge_center = start_point.project(
                far_edge_offset, outward_azimuth_degrees
            )
            near_edge_center = far_edge_center.project(
                zone_length_backward, backward_azimuth
            )
            if not far_edge_center or not near_edge_center:
                QgsMessageLog.logMessage(
                    f"Warning: Failed center point projection for '{description}'.",
                    plugin_tag,
                    level=Qgis.Warning,
                )
                return None
            near_l = near_edge_center.project(half_width, az_perp_l)
            near_r = near_edge_center.project(half_width, az_perp_r)
            far_l = far_edge_center.project(half_width, az_perp_l)
            far_r = far_edge_center.project(half_width, az_perp_r)
            corner_points = [near_l, near_r, far_r, far_l]
            if not all(p is not None for p in corner_points):
                QgsMessageLog.logMessage(
                    f"Warning: Failed corner point projection for '{description}'.",
                    plugin_tag,
                    level=Qgis.Warning,
                )
                return None
            # Call main polygon creator
            return self._create_polygon_from_corners(corner_points, description)
        except Exception as e:
            QgsMessageLog.logMessage(
                f"Warning: Error during geometry calculation for '{description}': {e}",
                plugin_tag,
                level=Qgis.Warning,
            )
            return None

    def _create_runway_aligned_rectangle(
        self,
        point1: QgsPointXY,
        point2: QgsPointXY,
        extension_m: float,
        half_width_m: float,
        description: str = "Aligned Rectangle",
    ) -> Optional[QgsGeometry]:
        plugin_tag = PLUGIN_TAG
        if (
            not point1
            or not point2
            or half_width_m <= 0
            or point1.compare(point2, 1e-6)
        ):
            QgsMessageLog.logMessage(
                f"Skipping '{description}': Invalid points or half width ({half_width_m}).",
                plugin_tag,
                level=Qgis.Warning,
            )
            return None
        try:
            params = self._get_runway_parameters(point1, point2)
            if not params:
                QgsMessageLog.logMessage(
                    f"Warning: Failed getting runway parameters for '{description}'.",
                    plugin_tag,
                    level=Qgis.Warning,
                )
                return None  # Already logged by helper
            rect_start_center = point1.project(extension_m, params["azimuth_r_p"])
            rect_end_center = point2.project(extension_m, params["azimuth_p_r"])
            if not rect_start_center or not rect_end_center:
                QgsMessageLog.logMessage(
                    f"Warning: Failed center point projection for '{description}'.",
                    plugin_tag,
                    level=Qgis.Warning,
                )
                return None
            corner_start_l = rect_start_center.project(
                half_width_m, params["azimuth_perp_l"]
            )
            corner_start_r = rect_start_center.project(
                half_width_m, params["azimuth_perp_r"]
            )
            corner_end_l = rect_end_center.project(
                half_width_m, params["azimuth_perp_l"]
            )
            corner_end_r = rect_end_center.project(
                half_width_m, params["azimuth_perp_r"]
            )
            corner_points = [corner_start_l, corner_start_r, corner_end_r, corner_end_l]
            if not all(p is not None for p in corner_points):
                QgsMessageLog.logMessage(
                    f"Warning: Failed corner point projection for '{description}'.",
                    plugin_tag,
                    level=Qgis.Warning,
                )
                return None
            return self._create_polygon_from_corners(corner_points, description)
        except Exception as e:
            QgsMessageLog.logMessage(
                f"Warning: Error during geometry calculation for '{description}': {e}",
                plugin_tag,
                level=Qgis.Warning,
            )
            return None

    def _create_trapezoid(
        self,
        start_point: QgsPointXY,
        outward_azimuth_degrees: float,
        length: float,
        inner_half_width: float,
        outer_half_width: float,
        description: str = "Trapezoid",
    ) -> Optional[QgsGeometry]:
        plugin_tag = PLUGIN_TAG
        if (
            not start_point
            or length <= 0
            or inner_half_width < 0
            or outer_half_width < 0
        ):
            QgsMessageLog.logMessage(
                f"Skipping '{description}': Invalid start point/length/widths.",
                plugin_tag,
                level=Qgis.Warning,
            )
            return None
        try:
            az_perp_r = (outward_azimuth_degrees + 90.0) % 360.0
            az_perp_l = (outward_azimuth_degrees - 90.0 + 360.0) % 360.0
            inner_l = start_point.project(inner_half_width, az_perp_l)
            inner_r = start_point.project(inner_half_width, az_perp_r)
            outer_center = start_point.project(length, outward_azimuth_degrees)
            if not outer_center:
                QgsMessageLog.logMessage(
                    f"Warning: Failed center point projection for '{description}'.",
                    plugin_tag,
                    level=Qgis.Warning,
                )
                return None
            outer_l = outer_center.project(outer_half_width, az_perp_l)
            outer_r = outer_center.project(outer_half_width, az_perp_r)
            corner_points = [inner_l, inner_r, outer_r, outer_l]
            if not all(p is not None for p in corner_points):
                QgsMessageLog.logMessage(
                    f"Warning: Failed corner point projection for '{description}'.",
                    plugin_tag,
                    level=Qgis.Warning,
                )
                return None
            return self._create_polygon_from_corners(corner_points, description)
        except Exception as e:
            QgsMessageLog.logMessage(
                f"Warning: Error during geometry calculation for '{description}': {e}",
                plugin_tag,
                level=Qgis.Warning,
            )
            return None

    def _calculate_strip_dimensions(self, runway_data: dict) -> dict:
        """Calculates required strip widths and extension length."""
        plugin_tag = PLUGIN_TAG
        # Default results
        results = {
            "overall_width": None,
            "graded_width": None,
            "extension_length": None,
            "mos_overall_width_ref": "N/A",
            "mos_graded_width_ref": "N/A",
            "mos_extension_length_ref": "N/A",
        }
        log_name = runway_data.get(
            "short_name", f"RWY_{runway_data.get('original_index','?')}"
        )

        arc_num_str = runway_data.get("arc_num")
        runway_type = runway_data.get(
            "type1"
        )  # Assuming type1 governs strip dimensions
        runway_width = runway_data.get("width")

        if not arc_num_str or not runway_type:
            QgsMessageLog.logMessage(
                f"Strip calc skipped for {log_name}: Missing ARC number or Type 1.",
                plugin_tag,
                level=Qgis.Info,
            )
            return results  # Return defaults if essential info missing

        try:
            arc_num = int(arc_num_str)
        except (ValueError, TypeError):
            QgsMessageLog.logMessage(
                f"Strip calc skipped for {log_name}: Invalid ARC number '{arc_num_str}'.",
                plugin_tag,
                level=Qgis.Warning,
            )
            return results  # Return defaults if ARC invalid

        is_non_instrument_or_npa = runway_type in [
            "Non-Instrument (NI)",
            "Non-Precision Approach (NPA)",
        ]

        # Overall Width
        if arc_num in [1, 2] and is_non_instrument_or_npa:
            results.update(
                {
                    "overall_width": 140.0,
                    "mos_overall_width_ref": "MOS T6.17(4) Code 1/2 NI/NPA",
                }
            )
        elif arc_num in [1, 2, 3, 4]:  # Covers Code 3/4 or PA Cat I/II/III
            results.update(
                {
                    "overall_width": 280.0,
                    "mos_overall_width_ref": "MOS T6.17(4) Code 3/4 or PA",
                }
            )

        # Graded Width
        if arc_num == 1:
            results.update(
                {"graded_width": 60.0, "mos_graded_width_ref": "MOS T6.17(1) Code 1"}
            )
        elif arc_num == 2:
            results.update(
                {"graded_width": 80.0, "mos_graded_width_ref": "MOS T6.17(1) Code 2"}
            )
        elif arc_num in [3, 4]:
            # Ensure runway_width is usable for comparison
            try:
                width_val = (
                    float(runway_width) if runway_width is not None else 45.0
                )  # Assume >=45 if missing
            except (ValueError, TypeError):
                QgsMessageLog.logMessage(
                    f"Warning: Invalid runway width '{runway_width}' for graded strip calc on {log_name}. Assuming >= 45m.",
                    plugin_tag,
                    level=Qgis.Warning,
                )
                width_val = 45.0  # Default assumption

            if width_val < 45.0:
                results.update(
                    {
                        "graded_width": 90.0,
                        "mos_graded_width_ref": "MOS T6.17(1) Code 3/4 (<45m)",
                    }
                )
            else:  # >= 45m or width missing/invalid
                results.update(
                    {
                        "graded_width": 150.0,
                        "mos_graded_width_ref": "MOS T6.17(1) Code 3/4 (>=45m)",
                    }
                )

        # Extension Length
        is_non_instrument_code_1_or_2 = (
            runway_type == "Non-Instrument (NI)" and arc_num in [1, 2]
        )
        if is_non_instrument_code_1_or_2:
            results.update(
                {
                    "extension_length": 30.0,
                    "mos_extension_length_ref": "MOS 6.16(a) NI Code 1/2",
                }
            )
        else:  # Includes NPA, PA, or NI Code 3/4
            results.update(
                {
                    "extension_length": 60.0,
                    "mos_extension_length_ref": "MOS 6.16(b)",
                }
            )

        # QgsMessageLog.logMessage(f"Strip Dims for {log_name}: {results}", plugin_tag, level=Qgis.Info)

        return results

    def _calculate_resa_dimensions(self, runway_data: dict) -> dict:
        """Calculates required RESA dimensions and applicability."""
        arc_num_str = runway_data.get("arc_num")
        type1 = runway_data.get("type1")
        type2 = runway_data.get("type2")
        runway_width = runway_data.get("width")
        results = {
            "required": False,
            "width": None,
            "length": None,
            # "mos_applicability_ref": "MOS 6.2.6.1/2",
            "mos_width_ref": "N/A",
            "mos_length_ref": "N/A",
        }
        log_name = runway_data.get("short_name", "RWY")  # For logging
        if not arc_num_str or not type1:
            QgsMessageLog.logMessage(
                f"RESA calc skipped {log_name}: Missing ARC/Type1.",
                PLUGIN_TAG,
                level=Qgis.Info,
            )
            return results
        try:
            arc_num = int(arc_num_str)
        except (ValueError, TypeError):
            QgsMessageLog.logMessage(
                f"RESA calc skipped {log_name}: Invalid ARC '{arc_num_str}'.",
                PLUGIN_TAG,
                level=Qgis.Warning,
            )
            return results
        instrument_types = [
            "Non-Precision Approach (NPA)",
            "Precision Approach CAT I",
            "Precision Approach CAT II/III",
        ]
        end1_is_instrument = type1 in instrument_types
        end2_is_instrument = type2 in instrument_types if type2 else False
        if arc_num in [3, 4]:
            results["required"] = True
            results["mos_applicability_ref"] += " (Code 3/4)"
        elif arc_num in [1, 2] and (end1_is_instrument or end2_is_instrument):
            results["required"] = True
            results["mos_applicability_ref"] += " (Code 1/2 Instr)"
        if results["required"]:
            results["mos_width_ref"] = "MOS 6.2.6.5"
            results["mos_length_ref"] = "MOS 6.2.6 & T6.18"
            if runway_width is not None and runway_width > 0:
                results["width"] = 2.0 * runway_width
            else:
                QgsMessageLog.logMessage(
                    f"RESA width calc warning {log_name}: Runway width missing.",
                    PLUGIN_TAG,
                    level=Qgis.Warning,
                )
                results["mos_width_ref"] += " (RWY Width Missing)"
            if arc_num in [1, 2]:
                results["length"] = 120.0
                results["mos_length_ref"] += " (Code 1/2 Pref)"
            elif arc_num in [3, 4]:
                results["length"] = 240.0
                results["mos_length_ref"] += " (Code 3/4 Pref)"
        else:
            results["mos_applicability_ref"] += " (Not Required)"
        QgsMessageLog.logMessage(
            f"RESA Dims for {log_name}: {results}", PLUGIN_TAG, level=Qgis.Info
        )
        return results

    def _get_runway_parameters(
        self, thr_point: QgsPointXY, rec_thr_point: QgsPointXY
    ) -> Optional[dict]:
        """Calculates basic length and azimuths between two threshold points."""
        plugin_tag = PLUGIN_TAG
        if not isinstance(thr_point, QgsPointXY) or not isinstance(
            rec_thr_point, QgsPointXY
        ):
            QgsMessageLog.logMessage(
                "Invalid threshold point types for runway parameter calculation.",
                plugin_tag,
                level=Qgis.Warning,
            )
            return None
        if thr_point.compare(rec_thr_point, 1e-6):
            QgsMessageLog.logMessage(
                "Threshold points are identical for runway parameter calculation.",
                plugin_tag,
                level=Qgis.Warning,
            )
            return None

        try:
            length = thr_point.distance(rec_thr_point)
            azimuth_p_r = thr_point.azimuth(
                rec_thr_point
            )  # Primary THR -> Reciprocal THR
            azimuth_r_p = rec_thr_point.azimuth(
                thr_point
            )  # Reciprocal THR -> Primary THR

            # Check for valid results from QGIS geometry methods
            if (
                length is None
                or math.isnan(length)
                or length < 0
                or azimuth_p_r is None
                or math.isnan(azimuth_p_r)
                or azimuth_r_p is None
                or math.isnan(azimuth_r_p)
            ):
                QgsMessageLog.logMessage(
                    f"Failed to calculate valid length/azimuth for runway parameters (L:{length}, Az P->R:{azimuth_p_r}, Az R->P:{azimuth_r_p}).",
                    plugin_tag,
                    level=Qgis.Warning,
                )
                return None

            # Perpendicular azimuths (calculated from original azimuth_p_r before its normalization for this return dict)
            # These calculations already ensure results are in the 0-360 range.
            azimuth_perp_r = (azimuth_p_r + 90.0) % 360.0
            azimuth_perp_l = (
                azimuth_p_r - 90.0 + 360.0
            ) % 360.0  # Ensure positive before modulo

            # Normalize main azimuths to be in the 0-360 degree range.
            # (value + 360.0) % 360.0 ensures a positive result in [0, 360.0).
            azimuth_p_r_norm = (azimuth_p_r + 360.0) % 360.0
            azimuth_r_p_norm = (azimuth_r_p + 360.0) % 360.0

            return {
                "length": length,
                "azimuth_p_r": azimuth_p_r_norm,
                "azimuth_r_p": azimuth_r_p_norm,
                "azimuth_perp_l": azimuth_perp_l,
                "azimuth_perp_r": azimuth_perp_r,
            }
        except Exception as e:
            QgsMessageLog.logMessage(
                f"Warning: Unexpected error calculating runway parameters: {e}",
                plugin_tag,
                level=Qgis.Warning,
            )
            return None

    def _get_physical_runway_endpoints(
        self,
        thr_point_primary: QgsPointXY,
        thr_point_reciprocal: QgsPointXY,
        displaced_thr_primary: float,  # Displacement distance BEFORE primary threshold
        displaced_thr_reciprocal: float,  # Displacement distance BEFORE reciprocal threshold
        rwy_params: dict,  # Result from _get_runway_parameters
    ) -> Optional[Tuple[QgsPointXY, QgsPointXY, float]]:
        """
        Calculates the coordinates of the actual physical pavement ends,
        accounting for displaced thresholds.

        Args:
          thr_point_primary: Landing threshold coordinate for the primary end.
          thr_point_reciprocal: Landing threshold coordinate for the reciprocal end.
          displaced_thr_primary: Displacement length before the primary threshold (m).
          displaced_thr_reciprocal: Displacement length before the reciprocal threshold (m).
          rwy_params: Dictionary containing runway azimuths ('azimuth_p_r', 'azimuth_r_p').

        Returns:
          Tuple (phys_end_point_primary, phys_end_point_reciprocal, total_physical_length)
          or None if calculation fails.
        """
        # --- Input Validation ---
        if (
            not isinstance(thr_point_primary, QgsPointXY)
            or not isinstance(thr_point_reciprocal, QgsPointXY)
            or not isinstance(displaced_thr_primary, (int, float))
            or not isinstance(displaced_thr_reciprocal, (int, float))
            or displaced_thr_primary < 0
            or displaced_thr_reciprocal < 0
        ):
            QgsMessageLog.logMessage(
                "Invalid input types for physical endpoint calculation.",
                PLUGIN_TAG,
                level=Qgis.Warning,
            )
            return None

        if (
            not rwy_params
            or "azimuth_p_r" not in rwy_params
            or "azimuth_r_p" not in rwy_params
        ):
            QgsMessageLog.logMessage(
                "Missing required azimuths in rwy_params for physical endpoint calculation.",
                PLUGIN_TAG,
                level=Qgis.Warning,
            )
            return None

        azimuth_p_r = rwy_params["azimuth_p_r"]  # Primary -> Reciprocal
        azimuth_r_p = rwy_params["azimuth_r_p"]  # Reciprocal -> Primary

        # --- Calculate Primary Physical End ---
        # Start at the primary landing threshold.
        # Project "backwards" along the runway centerline.
        # The direction "backwards" from primary threshold is along the azimuth R->P.
        phys_end_point_primary = thr_point_primary
        if (
            displaced_thr_primary > 1e-6
        ):  # Use tolerance, only project if displacement exists
            projected_point = thr_point_primary.project(
                displaced_thr_primary, azimuth_r_p
            )
            if projected_point:
                phys_end_point_primary = projected_point
            else:
                QgsMessageLog.logMessage(
                    f"Failed to project primary physical endpoint (Dist: {displaced_thr_primary}m, Az: {azimuth_r_p}).",
                    PLUGIN_TAG,
                    level=Qgis.Warning,
                )
                return None  # Projection failed

        # --- Calculate Reciprocal Physical End ---
        # Start at the reciprocal landing threshold.
        # Project "backwards" along the runway centerline.
        # The direction "backwards" from reciprocal threshold is along the azimuth P->R.
        phys_end_point_reciprocal = thr_point_reciprocal
        if displaced_thr_reciprocal > 1e-6:  # Use tolerance
            projected_point = thr_point_reciprocal.project(
                displaced_thr_reciprocal, azimuth_p_r
            )
            if projected_point:
                phys_end_point_reciprocal = projected_point
            else:
                QgsMessageLog.logMessage(
                    f"Failed to project reciprocal physical endpoint (Dist: {displaced_thr_reciprocal}m, Az: {azimuth_p_r}).",
                    PLUGIN_TAG,
                    level=Qgis.Warning,
                )
                return None  # Projection failed

        # --- Calculate Total Physical Length ---
        try:
            total_physical_length = phys_end_point_primary.distance(
                phys_end_point_reciprocal
            )
            if total_physical_length is None:
                QgsMessageLog.logMessage(
                    "Failed to calculate distance between physical endpoints.",
                    PLUGIN_TAG,
                    level=Qgis.Warning,
                )
                return None
        except Exception as e_dist:
            QgsMessageLog.logMessage(
                f"Error calculating distance between physical endpoints: {e_dist}",
                PLUGIN_TAG,
                level=Qgis.Warning,
            )
            return None

        return phys_end_point_primary, phys_end_point_reciprocal, total_physical_length

    def _create_polygon_from_corners(
        self, corners: List[QgsPointXY], description: str = "Polygon"
    ) -> Optional[QgsGeometry]:
        """Creates a QgsGeometry polygon from a list of corner points. Logs warnings on failure."""
        plugin_tag = PLUGIN_TAG

        # Input validation
        if (
            not corners
            or len(corners) < 3
            or None in corners
            or not all(isinstance(p, QgsPointXY) for p in corners)
        ):
            QgsMessageLog.logMessage(
                f"Cannot create polygon '{description}': Invalid input corner points.",
                plugin_tag,
                level=Qgis.Warning,
            )
            return None

        try:
            # Ensure list is closed (first == last)
            closed_corners = (
                corners + [corners[0]]
                if not corners[0].compare(corners[-1], 1e-6)
                else corners
            )

            # Create exterior ring
            exterior_ring = QgsLineString(closed_corners)
            if exterior_ring.isEmpty():
                QgsMessageLog.logMessage(
                    f"Cannot create polygon '{description}': Generated exterior ring is empty.",
                    plugin_tag,
                    level=Qgis.Warning,
                )
                return None

            # Create polygon geometry
            polygon = QgsPolygon(exterior_ring)
            geom = QgsGeometry(polygon)

            if geom.isNull() or geom.isEmpty():
                QgsMessageLog.logMessage(
                    f"Cannot create polygon '{description}': Initial geometry is null or empty after QgsPolygon creation.",
                    plugin_tag,
                    level=Qgis.Warning,
                )
                return None

            # Check validity and attempt fix if necessary
            if not geom.isGeosValid():
                geom_valid = geom.makeValid()

                if (
                    not geom_valid
                    or geom_valid.isNull()
                    or geom_valid.isEmpty()
                    or not geom_valid.isGeosValid()
                ):
                    QgsMessageLog.logMessage(
                        f"Cannot create polygon '{description}': Geometry invalid even after makeValid().",
                        plugin_tag,
                        level=Qgis.Warning,
                    )
                    return None

                # Handle potential MultiPolygon result from makeValid()
                valid_poly_types = [
                    Qgis.WkbType.Polygon,
                    Qgis.WkbType.PolygonZ,
                    Qgis.WkbType.PolygonM,
                    Qgis.WkbType.PolygonZM,
                ]
                valid_multipoly_types = [
                    Qgis.WkbType.MultiPolygon,
                    Qgis.WkbType.MultiPolygonZ,
                    Qgis.WkbType.MultiPolygonM,
                    Qgis.WkbType.MultiPolygonZM,
                ]

                if geom_valid.wkbType() in valid_multipoly_types:
                    polygons = geom_valid.asMultiPolygon()
                    largest_poly_geom = None
                    max_area = -1.0
                    if polygons:  # Check if conversion to MultiPolygon worked
                        for poly_rings in polygons:
                            # Ensure we handle potential empty ring lists
                            if (
                                poly_rings and poly_rings[0]
                            ):  # Check if exterior ring exists
                                try:
                                    # Create temporary polygon from rings
                                    temp_poly = QgsPolygon(
                                        poly_rings[0], poly_rings[1:]
                                    )  # Pass exterior and list of interiors
                                    temp_geom = QgsGeometry(temp_poly)
                                    if not temp_geom.isNull():
                                        area = temp_geom.area()
                                        if area > max_area:
                                            max_area = area
                                            largest_poly_geom = temp_geom
                                except Exception as e_multi:
                                    # Log error during specific polygon creation within multipolygon parts
                                    QgsMessageLog.logMessage(
                                        f"Warning: Error processing part of MultiPolygon for '{description}': {e_multi}",
                                        plugin_tag,
                                        level=Qgis.Warning,
                                    )

                    if largest_poly_geom:
                        geom = largest_poly_geom  # Use the largest valid part
                    else:
                        # Failed to extract a valid polygon from the MultiPolygon result
                        QgsMessageLog.logMessage(
                            f"Cannot create polygon '{description}': Failed to extract valid part from MultiPolygon after makeValid().",
                            plugin_tag,
                            level=Qgis.Warning,
                        )
                        return None
                elif geom_valid.wkbType() not in valid_poly_types:
                    # makeValid returned something other than Polygon or MultiPolygon
                    QgsMessageLog.logMessage(
                        f"Cannot create polygon '{description}': makeValid() resulted in unexpected geometry type '{geom_valid.wkbType()}'",
                        plugin_tag,
                        level=Qgis.Warning,
                    )
                    return None
                else:
                    # makeValid succeeded and resulted in a simple Polygon
                    geom = geom_valid

            # Final check on the potentially modified geometry
            if (
                geom is None
                or geom.isNull()
                or geom.isEmpty()
                or not geom.isGeosValid()
            ):
                QgsMessageLog.logMessage(
                    f"Cannot create polygon '{description}': Final geometry check failed (Null/Empty/Invalid).",
                    plugin_tag,
                    level=Qgis.Warning,
                )
                return None

            # If we reach here, geometry should be valid
            return geom

        except Exception as e:
            # Catch-all for unexpected errors
            QgsMessageLog.logMessage(
                f"Critical error in _create_polygon_from_corners for '{description}': {e}\n{traceback.format_exc()}",
                plugin_tag,
                level=Qgis.Critical,
            )
            return None

    def _create_rectangle_from_start(
        self,
        start_center_point: QgsPointXY,
        outward_azimuth: float,
        length: float,
        half_width: float,
        description: str = "Rectangle",
    ) -> Optional[QgsGeometry]:
        plugin_tag = PLUGIN_TAG
        if not start_center_point or length <= 0 or half_width < 0:
            QgsMessageLog.logMessage(
                f"Skipping '{description}': Invalid start point/length/half width.",
                plugin_tag,
                level=Qgis.Warning,
            )
            return None
        try:
            end_center_point = start_center_point.project(length, outward_azimuth)
            if not end_center_point:
                QgsMessageLog.logMessage(
                    f"Warning: Failed end point projection for '{description}'",
                    plugin_tag,
                    level=Qgis.Warning,
                )
                return None
            azimuth_perp_r = (outward_azimuth + 90.0) % 360.0
            azimuth_perp_l = (outward_azimuth - 90.0 + 360.0) % 360.0
            start_l = start_center_point.project(half_width, azimuth_perp_l)
            start_r = start_center_point.project(half_width, azimuth_perp_r)
            end_l = end_center_point.project(half_width, azimuth_perp_l)
            end_r = end_center_point.project(half_width, azimuth_perp_r)
            corners = [start_l, start_r, end_r, end_l]
            if not all(p is not None for p in corners):
                QgsMessageLog.logMessage(
                    f"Warning: Failed corner point projection for '{description}'",
                    plugin_tag,
                    level=Qgis.Warning,
                )
                return None
            return self._create_polygon_from_corners(corners, description)
        except Exception as e:
            QgsMessageLog.logMessage(
                f"Warning: Error during geometry calculation for '{description}': {e}",
                plugin_tag,
                level=Qgis.Warning,
            )
            return None

    def generate_physical_geometry(
        self, runway_data: dict
    ) -> Optional[List[Tuple[str, QgsGeometry, dict]]]:
        """
        Calculates geometry and attributes for physical runway components.
        Returns a list of tuples: (element_type_key, geometry, attributes)
        or None if basic parameters are missing or calculation fails critically.
        Logs warnings for non-critical issues (e.g., single element failure).
        """
        plugin_tag = PLUGIN_TAG

        thr_point = runway_data.get("thr_point")
        rec_thr_point = runway_data.get("rec_thr_point")
        runway_width = runway_data.get("width")
        shoulder_width = runway_data.get("shoulder")
        runway_name = runway_data.get("short_name", "RWY")
        log_name = (
            runway_name
            if runway_name != "RWY"
            else f"RWY_{runway_data.get('original_index','?')}"
        )

        disp_val_1 = runway_data.get("thr_displaced_1")
        disp_val_2 = runway_data.get("thr_displaced_2")
        pre_val_1 = runway_data.get("thr_pre_area_1")
        pre_val_2 = runway_data.get("thr_pre_area_2")

        disp_thr_1: float = 0.0
        disp_thr_2: float = 0.0
        pre_area_len_1: float = 0.0
        pre_area_len_2: float = 0.0

        try:
            if disp_val_1 is not None:
                disp_thr_1 = float(disp_val_1)
        except (ValueError, TypeError):
            QgsMessageLog.logMessage(
                f"Warning: Invalid Displacement 1 value '{disp_val_1}' for {log_name}, using 0.0.",
                plugin_tag,
                level=Qgis.Warning,
            )
        try:
            if disp_val_2 is not None:
                disp_thr_2 = float(disp_val_2)
        except (ValueError, TypeError):
            QgsMessageLog.logMessage(
                f"Warning: Invalid Displacement 2 value '{disp_val_2}' for {log_name}, using 0.0.",
                plugin_tag,
                level=Qgis.Warning,
            )
        try:
            if pre_val_1 is not None:
                pre_area_len_1 = float(pre_val_1)
        except (ValueError, TypeError):
            QgsMessageLog.logMessage(
                f"Warning: Invalid Pre-Threshold Area 1 length '{pre_val_1}' for {log_name}, using 0.0.",
                plugin_tag,
                level=Qgis.Warning,
            )
        try:
            if pre_val_2 is not None:
                pre_area_len_2 = float(pre_val_2)
        except (ValueError, TypeError):
            QgsMessageLog.logMessage(
                f"Warning: Invalid Pre-Threshold Area 2 length '{pre_val_2}' for {log_name}, using 0.0.",
                plugin_tag,
                level=Qgis.Warning,
            )

        if not thr_point or not rec_thr_point:
            QgsMessageLog.logMessage(
                f"Skipping physical geom generation for {log_name}: Missing threshold points.",
                plugin_tag,
                level=Qgis.Warning,
            )
            return None

        rwy_params = self._get_runway_parameters(thr_point, rec_thr_point)
        if rwy_params is None:
            QgsMessageLog.logMessage(
                f"Skipping physical geom generation for {log_name}: Failed to get base runway parameters.",
                plugin_tag,
                level=Qgis.Warning,
            )
            return None

        physical_endpoints_result = self._get_physical_runway_endpoints(
            thr_point, rec_thr_point, disp_thr_1, disp_thr_2, rwy_params
        )
        if physical_endpoints_result is None:
            QgsMessageLog.logMessage(
                f"Skipping physical geom generation for {log_name}: Failed to calculate physical endpoints.",
                plugin_tag,
                level=Qgis.Warning,
            )
            return None
        phys_p_start, phys_p_end, physical_length = physical_endpoints_result

        generated_elements: List[Tuple[str, QgsGeometry, dict]] = []

        # --- 1. Runway Pavement (Landing Area: Between Thresholds) ---
        if runway_width is not None and runway_width > 0:
            try:
                half_width = runway_width / 2.0
                thr_l = thr_point.project(half_width, rwy_params["azimuth_perp_l"])
                thr_r = thr_point.project(half_width, rwy_params["azimuth_perp_r"])
                rec_l = rec_thr_point.project(half_width, rwy_params["azimuth_perp_l"])
                rec_r = rec_thr_point.project(half_width, rwy_params["azimuth_perp_r"])
                if all([thr_l, thr_r, rec_l, rec_r]):
                    landing_pavement_geom = self._create_polygon_from_corners(
                        [thr_l, thr_r, rec_r, rec_l], f"Landing Pavement {log_name}"
                    )
                    if landing_pavement_geom:
                        landing_length = rwy_params["length"]
                        physical_refs = ols_dimensions.get_physical_refs()
                        pavement_ref = physical_refs.get("pavement", "MOS 6.2.3")
                        # Use correct field names: 'rwy', 'desc', 'ref_mos'
                        attributes = {
                            "rwy": runway_name,
                            "desc": "Runway Pavement",
                            "wid_m": runway_width,
                            "len_m": round(landing_length, 3),
                            "ref_mos": pavement_ref,
                        }
                        generated_elements.append(
                            ("rwy", landing_pavement_geom, attributes)
                        )
                else:
                    QgsMessageLog.logMessage(
                        f"Warning: Failed to calculate landing pavement corners for {log_name}.",
                        plugin_tag,
                        level=Qgis.Warning,
                    )
            except Exception as e:
                QgsMessageLog.logMessage(
                    f"Warning: Error calculating Landing Pavement for {log_name}: {e}",
                    plugin_tag,
                    level=Qgis.Warning,
                )
        else:
            QgsMessageLog.logMessage(
                f"Info: Skipping Landing Pavement for {log_name}: Width ({runway_width}) not specified or invalid.",
                plugin_tag,
                level=Qgis.Info,
            )

        # --- 1b. Pre-Threshold Runway Areas (Displaced Areas) ---
        if runway_width is not None and runway_width > 0:
            pre_threshold_features = []
            half_width = runway_width / 2.0
            primary_desig = (
                runway_name.split("/")[0] if "/" in runway_name else "Primary"
            )
            reciprocal_desig = (
                runway_name.split("/")[1] if "/" in runway_name else "Reciprocal"
            )

            if disp_thr_1 > 1e-6:
                try:
                    start_point = phys_p_start
                    end_point = thr_point
                    p_start_l = start_point.project(
                        half_width, rwy_params["azimuth_perp_l"]
                    )
                    p_start_r = start_point.project(
                        half_width, rwy_params["azimuth_perp_r"]
                    )
                    p_end_l = end_point.project(
                        half_width, rwy_params["azimuth_perp_l"]
                    )
                    p_end_r = end_point.project(
                        half_width, rwy_params["azimuth_perp_r"]
                    )
                    if all([p_start_l, p_start_r, p_end_l, p_end_r]):
                        geom = self._create_polygon_from_corners(
                            [p_start_l, p_start_r, p_end_r, p_end_l],
                            f"Pre-Threshold {primary_desig}",
                        )
                        if geom:
                            physical_refs = ols_dimensions.get_physical_refs()
                            pavement_ref = physical_refs.get("pavement", "MOS 6.04")
                            # Use correct field names: 'rwy', 'desc', 'ref_mos', and add 'end_desig'
                            attributes = {
                                "rwy": runway_name,
                                "desc": f"Pre-Threshold Pavement ({primary_desig})",
                                "wid_m": runway_width,
                                "len_m": round(disp_thr_1, 3),
                                "ref_mos": pavement_ref,
                                "end_desig": primary_desig,
                            }
                            pre_threshold_features.append(
                                ("PreThresholdRunway", geom, attributes)
                            )
                    else:
                        QgsMessageLog.logMessage(
                            f"Warning: Failed calculate corners for Pre-Threshold Pavement {primary_desig}.",
                            plugin_tag,
                            level=Qgis.Warning,
                        )
                except Exception as e:
                    QgsMessageLog.logMessage(
                        f"Warning: Error generating Pre-Threshold Pavement {primary_desig}: {e}",
                        plugin_tag,
                        level=Qgis.Warning,
                    )

            if disp_thr_2 > 1e-6:
                try:
                    start_point = phys_p_end
                    end_point = rec_thr_point
                    r_start_l = start_point.project(
                        half_width, rwy_params["azimuth_perp_l"]
                    )
                    r_start_r = start_point.project(
                        half_width, rwy_params["azimuth_perp_r"]
                    )
                    r_end_l = end_point.project(
                        half_width, rwy_params["azimuth_perp_l"]
                    )
                    r_end_r = end_point.project(
                        half_width, rwy_params["azimuth_perp_r"]
                    )
                    if all([r_start_l, r_start_r, r_end_l, r_end_r]):
                        geom = self._create_polygon_from_corners(
                            [r_start_l, r_start_r, r_end_r, r_end_l],
                            f"Pre-Threshold {reciprocal_desig}",
                        )
                        if geom:
                            physical_refs = ols_dimensions.get_physical_refs()
                            pavement_ref = physical_refs.get("pavement", "MOS 6.04")
                            # Use correct field names: 'rwy', 'desc', 'ref_mos', and add 'end_desig'
                            attributes = {
                                "rwy": runway_name,
                                "desc": f"Pre-Threshold Pavement ({reciprocal_desig})",
                                "wid_m": runway_width,
                                "len_m": round(disp_thr_2, 3),
                                "ref_mos": pavement_ref,
                                "end_desig": reciprocal_desig,
                            }
                            pre_threshold_features.append(
                                ("PreThresholdRunway", geom, attributes)
                            )
                    else:
                        QgsMessageLog.logMessage(
                            f"Warning: Failed calculate corners for Pre-Threshold Pavement {reciprocal_desig}.",
                            plugin_tag,
                            level=Qgis.Warning,
                        )
                except Exception as e:
                    QgsMessageLog.logMessage(
                        f"Warning: Error generating Pre-Threshold Pavement {reciprocal_desig}: {e}",
                        plugin_tag,
                        level=Qgis.Warning,
                    )

            generated_elements.extend(pre_threshold_features)

        # --- 1c. Pre-Threshold Area (Blast Pad, etc.) ---
        if runway_width is not None and runway_width > 0:
            pre_threshold_area_features = []
            half_width = runway_width / 2.0
            primary_desig = (
                runway_name.split("/")[0] if "/" in runway_name else "Primary"
            )
            reciprocal_desig = (
                runway_name.split("/")[1] if "/" in runway_name else "Reciprocal"
            )

            if pre_area_len_1 > 1e-6:
                try:
                    area_start_point = phys_p_start
                    outward_azimuth = rwy_params["azimuth_r_p"]
                    geom = self._create_rectangle_from_start(
                        area_start_point,
                        outward_azimuth,
                        pre_area_len_1,
                        half_width,
                        f"Pre-Threshold Area {primary_desig}",
                    )
                    if geom:
                        # Use correct field names: 'rwy', 'desc', 'ref_mos', and add 'end_desig'
                        attributes = {
                            "rwy": runway_name,
                            "desc": f"Pre-Threshold Area ({primary_desig})",
                            "wid_m": runway_width,
                            "len_m": round(pre_area_len_1, 3),
                            "ref_mos": "MOS 8.16",
                            "end_desig": primary_desig,
                        }
                        pre_threshold_area_features.append(
                            ("PreThresholdArea", geom, attributes)
                        )
                except Exception as e:
                    QgsMessageLog.logMessage(
                        f"Warning: Error generating Pre-Threshold Area {primary_desig}: {e}",
                        plugin_tag,
                        level=Qgis.Warning,
                    )

            if pre_area_len_2 > 1e-6:
                try:
                    area_start_point = phys_p_end
                    outward_azimuth = rwy_params["azimuth_p_r"]
                    geom = self._create_rectangle_from_start(
                        area_start_point,
                        outward_azimuth,
                        pre_area_len_2,
                        half_width,
                        f"Pre-Threshold Area {reciprocal_desig}",
                    )
                    if geom:
                        # Use correct field names: 'rwy', 'desc', 'ref_mos', and add 'end_desig'
                        attributes = {
                            "rwy": runway_name,
                            "desc": f"Pre-Threshold Area ({reciprocal_desig})",
                            "wid_m": runway_width,
                            "len_m": round(pre_area_len_2, 3),
                            "ref_mos": "MOS 8.16",
                            "end_desig": reciprocal_desig,
                        }
                        pre_threshold_area_features.append(
                            ("PreThresholdArea", geom, attributes)
                        )
                except Exception as e:
                    QgsMessageLog.logMessage(
                        f"Warning: Error generating Pre-Threshold Area {reciprocal_desig}: {e}",
                        plugin_tag,
                        level=Qgis.Warning,
                    )

            generated_elements.extend(pre_threshold_area_features)

        # --- 1d. Displaced Threshold Markings ---
        displaced_marking_features = []
        primary_desig = runway_name.split("/")[0] if "/" in runway_name else "Primary"
        reciprocal_desig = (
            runway_name.split("/")[1] if "/" in runway_name else "Reciprocal"
        )
        marking_ref = "MOS 8.26"

        if disp_thr_1 > 1e-6:
            try:
                line_geom = QgsGeometry.fromPolylineXY([phys_p_start, thr_point])
                if line_geom and not line_geom.isEmpty():
                    line_len = line_geom.length()
                    # Use correct field names: 'rwy', 'desc', 'ref_mos'
                    attributes = {
                        "rwy": runway_name,
                        "desc": "Displaced Threshold Marking",
                        "end_desig": primary_desig,
                        "len_m": round(line_len, 3) if line_len else None,
                        "ref_mos": marking_ref,
                    }
                    displaced_marking_features.append(
                        ("DisplacedThresholdMarking", line_geom, attributes)
                    )
                else:
                    QgsMessageLog.logMessage(
                        f"Warning: Failed generate geometry for Primary Displaced Marking {log_name}.",
                        plugin_tag,
                        level=Qgis.Warning,
                    )
            except Exception as e:
                QgsMessageLog.logMessage(
                    f"Warning: Error generating Primary Displaced Marking {log_name}: {e}",
                    plugin_tag,
                    level=Qgis.Warning,
                )

        if disp_thr_2 > 1e-6:
            try:
                line_geom = QgsGeometry.fromPolylineXY([phys_p_end, rec_thr_point])
                if line_geom and not line_geom.isEmpty():
                    line_len = line_geom.length()
                    # Use correct field names: 'rwy', 'desc', 'ref_mos'
                    attributes = {
                        "rwy": runway_name,
                        "desc": "Displaced Threshold Marking",
                        "end_desig": reciprocal_desig,
                        "len_m": round(line_len, 3) if line_len else None,
                        "ref_mos": marking_ref,
                    }
                    displaced_marking_features.append(
                        ("DisplacedThresholdMarking", line_geom, attributes)
                    )
                else:
                    QgsMessageLog.logMessage(
                        f"Warning: Failed generate geometry for Reciprocal Displaced Marking {log_name}.",
                        plugin_tag,
                        level=Qgis.Warning,
                    )
            except Exception as e:
                QgsMessageLog.logMessage(
                    f"Warning: Error generating Reciprocal Displaced Marking {log_name}: {e}",
                    plugin_tag,
                    level=Qgis.Warning,
                )

        generated_elements.extend(displaced_marking_features)

        # --- 1e. Pre-Threshold Area Markings ---
        pre_area_marking_features = []
        if pre_area_len_1 > 1e-6:
            try:
                outermost_p = phys_p_start.project(
                    pre_area_len_1, rwy_params["azimuth_r_p"]
                )
                if not outermost_p:
                    raise ValueError("Projection failed")
                line_geom = QgsGeometry.fromPolylineXY([outermost_p, phys_p_start])
                if line_geom and not line_geom.isEmpty():
                    line_len = line_geom.length()
                    # Use correct field names: 'rwy', 'desc', 'ref_mos'
                    attributes = {
                        "rwy": runway_name,
                        "desc": "Pre-Threshold Area Marking",
                        "end_desig": primary_desig,
                        "len_m": round(line_len, 3) if line_len else None,
                        "ref_mos": "MOS 8.16(2)",
                    }
                    pre_area_marking_features.append(
                        ("PreThresholdAreaMarking", line_geom, attributes)
                    )
                else:
                    QgsMessageLog.logMessage(
                        f"Warning: Failed generate geometry for Primary Pre-Area Marking {log_name}.",
                        plugin_tag,
                        level=Qgis.Warning,
                    )
            except Exception as e:
                QgsMessageLog.logMessage(
                    f"Warning: Error generating Primary Pre-Area Marking {log_name}: {e}",
                    plugin_tag,
                    level=Qgis.Warning,
                )

        if pre_area_len_2 > 1e-6:
            try:
                outermost_r = phys_p_end.project(
                    pre_area_len_2, rwy_params["azimuth_p_r"]
                )
                if not outermost_r:
                    raise ValueError("Projection failed")
                line_geom = QgsGeometry.fromPolylineXY([outermost_r, phys_p_end])
                if line_geom and not line_geom.isEmpty():
                    line_len = line_geom.length()
                    # Use correct field names: 'rwy', 'desc', 'ref_mos'
                    attributes = {
                        "rwy": runway_name,
                        "desc": "Pre-Threshold Area Marking",
                        "end_desig": reciprocal_desig,
                        "len_m": round(line_len, 3) if line_len else None,
                        "ref_mos": "MOS 8.16(2)",
                    }
                    pre_area_marking_features.append(
                        ("PreThresholdAreaMarking", line_geom, attributes)
                    )
                else:
                    QgsMessageLog.logMessage(
                        f"Warning: Failed generate geometry for Reciprocal Pre-Area Marking {log_name}.",
                        plugin_tag,
                        level=Qgis.Warning,
                    )
            except Exception as e:
                QgsMessageLog.logMessage(
                    f"Warning: Error generating Reciprocal Pre-Area Marking {log_name}: {e}",
                    plugin_tag,
                    level=Qgis.Warning,
                )

        generated_elements.extend(pre_area_marking_features)

        # --- 2. Runway Shoulders ---
        if (
            shoulder_width is not None
            and shoulder_width > 0
            and runway_width is not None
            and runway_width > 0
        ):
            try:
                half_width = runway_width / 2.0
                phys_start_l = phys_p_start.project(
                    half_width, rwy_params["azimuth_perp_l"]
                )
                phys_start_r = phys_p_start.project(
                    half_width, rwy_params["azimuth_perp_r"]
                )
                phys_end_l = phys_p_end.project(
                    half_width, rwy_params["azimuth_perp_l"]
                )
                phys_end_r = phys_p_end.project(
                    half_width, rwy_params["azimuth_perp_r"]
                )
                if not all([phys_start_l, phys_start_r, phys_end_l, phys_end_r]):
                    raise ValueError(
                        "Failed to calculate physical pavement corners for shoulders."
                    )

                outer_start_l = phys_start_l.project(
                    shoulder_width, rwy_params["azimuth_perp_l"]
                )
                outer_start_r = phys_start_r.project(
                    shoulder_width, rwy_params["azimuth_perp_r"]
                )
                outer_end_l = phys_end_l.project(
                    shoulder_width, rwy_params["azimuth_perp_l"]
                )
                outer_end_r = phys_end_r.project(
                    shoulder_width, rwy_params["azimuth_perp_r"]
                )

                physical_refs = ols_dimensions.get_physical_refs()
                shoulder_ref = physical_refs.get("shoulder", "MOS 6.2.4")
                # Use correct field names: 'rwy', 'desc', 'ref_mos'
                shoulder_attrs = {
                    "rwy": runway_name,
                    "desc": "Runway Shoulder",
                    "wid_m": shoulder_width,
                    "len_m": round(physical_length, 3),
                    "ref_mos": shoulder_ref,
                }

                if all([outer_start_l, outer_end_l]):
                    left_corners = [
                        phys_start_l,
                        outer_start_l,
                        outer_end_l,
                        phys_end_l,
                    ]
                    left_shoulder_poly = self._create_polygon_from_corners(
                        left_corners, f"Left Shoulder {log_name}"
                    )
                    if left_shoulder_poly:
                        generated_elements.append(
                            ("Shoulder", left_shoulder_poly, shoulder_attrs.copy())
                        )
                else:
                    QgsMessageLog.logMessage(
                        f"Warning: Failed calculate outer corners for left shoulder for {log_name}.",
                        plugin_tag,
                        level=Qgis.Warning,
                    )

                if all([outer_start_r, outer_end_r]):
                    right_corners = [
                        phys_start_r,
                        phys_end_r,
                        outer_end_r,
                        outer_start_r,
                    ]
                    right_shoulder_poly = self._create_polygon_from_corners(
                        right_corners, f"Right Shoulder {log_name}"
                    )
                    if right_shoulder_poly:
                        generated_elements.append(
                            ("Shoulder", right_shoulder_poly, shoulder_attrs.copy())
                        )
                else:
                    QgsMessageLog.logMessage(
                        f"Warning: Failed calculate outer corners for right shoulder for {log_name}.",
                        plugin_tag,
                        level=Qgis.Warning,
                    )

            except Exception as e_shld:
                QgsMessageLog.logMessage(
                    f"Warning: Error calculating Shoulders {log_name}: {e_shld}",
                    plugin_tag,
                    level=Qgis.Warning,
                )
        elif shoulder_width is not None and shoulder_width > 0:
            QgsMessageLog.logMessage(
                f"Info: Skipping Shoulders for {log_name}: Runway width missing.",
                plugin_tag,
                level=Qgis.Info,
            )

        # --- 3. Runway Strips ---
        strip_dims = None
        strip_end_center_p = None
        strip_end_center_r = None
        strip_length = None
        try:
            arc_num_val = runway_data.get("arc_num")
            arc_num = int(arc_num_val) if arc_num_val is not None else 0
            type1_abbr = ols_dimensions.get_runway_type_abbr(runway_data.get("type1"))
            runway_width_for_strip = runway_data.get("width")

            strip_dims = ols_dimensions.get_strip_params(
                arc_num, type1_abbr, runway_width_for_strip
            )
            runway_data["calculated_strip_dims"] = strip_dims

            if strip_dims is None:
                QgsMessageLog.logMessage(
                    f"Warning (Physical Geom): Failed to calculate strip parameters for {log_name} "
                    f"(ARC={arc_num}, Type={type1_abbr}, Width={runway_width_for_strip}). "
                    "Dependent elements (Strips, RESA, IHS Base) may fail.",
                    plugin_tag,
                    level=Qgis.Warning,
                )

            if strip_dims and all(
                strip_dims.get(dim) is not None
                for dim in ["overall_width", "graded_width", "extension_length"]
            ):
                extension = strip_dims["extension_length"]
                graded_width = strip_dims["graded_width"]
                overall_width = strip_dims["overall_width"]
                graded_half_width = graded_width / 2.0
                overall_half_width = overall_width / 2.0

                strip_end_center_p = phys_p_start.project(
                    extension, rwy_params["azimuth_r_p"]
                )
                strip_end_center_r = phys_p_end.project(
                    extension, rwy_params["azimuth_p_r"]
                )

                if strip_end_center_p and strip_end_center_r:
                    strip_length = strip_end_center_p.distance(strip_end_center_r)
                    if strip_length is None:
                        raise ValueError("Failed to calculate strip length.")

                    graded_strip_geom = self._create_runway_aligned_rectangle(
                        strip_end_center_p,
                        strip_end_center_r,
                        0.0,
                        graded_half_width,
                        f"Graded Strip {log_name}",
                    )
                    if graded_strip_geom:
                        graded_ref = f"{strip_dims.get('mos_graded_width_ref','')}; {strip_dims.get('mos_extension_length_ref','')}"
                        # Use correct field names: 'rwy', 'desc', 'ref_mos'
                        graded_attrs = {
                            "rwy": runway_name,
                            "desc": "Graded Strip",
                            "wid_m": graded_width,
                            "len_m": round(strip_length, 3),
                            "ref_mos": graded_ref,
                        }
                        generated_elements.append(
                            ("GradedStrip", graded_strip_geom, graded_attrs)
                        )

                    overall_strip_geom = self._create_runway_aligned_rectangle(
                        strip_end_center_p,
                        strip_end_center_r,
                        0.0,
                        overall_half_width,
                        f"Overall Strip {log_name}",
                    )
                    if overall_strip_geom:
                        overall_ref = f"{strip_dims.get('mos_overall_width_ref','')}; {strip_dims.get('mos_extension_length_ref','')}"
                        # Use correct field names: 'rwy', 'desc', 'ref_mos'
                        overall_attrs = {
                            "rwy": runway_name,
                            "desc": "Overall Strip",
                            "wid_m": overall_width,
                            "len_m": round(strip_length, 3),
                            "ref_mos": overall_ref,
                        }
                        generated_elements.append(
                            ("OverallStrip", overall_strip_geom, overall_attrs)
                        )
                else:
                    QgsMessageLog.logMessage(
                        f"Warning: Skipping Strips for {log_name}: Invalid strip end points calculation.",
                        plugin_tag,
                        level=Qgis.Warning,
                    )
                    strip_dims = None
            else:
                QgsMessageLog.logMessage(
                    f"Info: Skipping Strips for {log_name}: Strip dimensions calculation failed or incomplete.",
                    plugin_tag,
                    level=Qgis.Info,
                )
                strip_dims = None
        except Exception as e:
            QgsMessageLog.logMessage(
                f"Warning: Error calculating Strips for {log_name}: {e}",
                plugin_tag,
                level=Qgis.Warning,
            )
            strip_dims = None

        # --- 4. RESAs ---
        try:
            type1_abbr = ols_dimensions.get_runway_type_abbr(runway_data.get("type1"))
            type2_abbr = ols_dimensions.get_runway_type_abbr(runway_data.get("type2"))
            resa_dims = ols_dimensions.get_resa_params(
                int(runway_data.get("arc_num", 0)), type1_abbr, type2_abbr
            )

            if (
                resa_dims
                and resa_dims.get("required")
                and strip_end_center_p
                and strip_end_center_r
                and runway_width is not None
                and runway_width > 0
            ):
                resa_length = resa_dims.get("length")
                resa_width_val = 2.0 * runway_width
                resa_half_width = resa_width_val / 2.0

                if resa_length is None or resa_length <= 0:
                    raise ValueError("Required RESA length missing or invalid.")

                primary_desig = (
                    runway_name.split("/")[0] if "/" in runway_name else "Primary"
                )
                reciprocal_desig = (
                    runway_name.split("/")[1] if "/" in runway_name else "Reciprocal"
                )
                resa_ref = f"{resa_dims.get('mos_applicability_ref','')}; {resa_dims.get('mos_width_ref','')}; {resa_dims.get('mos_length_ref','')}"
                # Use correct field names: 'rwy', 'desc', 'ref_mos'
                resa_base_attrs = {
                    "rwy": runway_name,
                    "desc": "RESA",
                    "len_m": resa_length,
                    "wid_m": resa_width_val,
                    "ref_mos": resa_ref,
                }

                try:
                    resa1_geom = self._create_rectangle_from_start(
                        strip_end_center_p,
                        rwy_params["azimuth_r_p"],
                        resa_length,
                        resa_half_width,
                        f"RESA {primary_desig}",
                    )
                    if resa1_geom:
                        resa1_attrs = resa_base_attrs.copy()
                        resa1_attrs["end_desig"] = primary_desig
                        generated_elements.append(("RESA", resa1_geom, resa1_attrs))
                except Exception as e_resa1:
                    QgsMessageLog.logMessage(
                        f"Warning: Error RESA {primary_desig} for {log_name}: {e_resa1}",
                        plugin_tag,
                        level=Qgis.Warning,
                    )

                try:
                    resa2_geom = self._create_rectangle_from_start(
                        strip_end_center_r,
                        rwy_params["azimuth_p_r"],
                        resa_length,
                        resa_half_width,
                        f"RESA {reciprocal_desig}",
                    )
                    if resa2_geom:
                        resa2_attrs = resa_base_attrs.copy()
                        resa2_attrs["end_desig"] = reciprocal_desig
                        generated_elements.append(("RESA", resa2_geom, resa2_attrs))
                except Exception as e_resa2:
                    QgsMessageLog.logMessage(
                        f"Warning: Error RESA {reciprocal_desig} for {log_name}: {e_resa2}",
                        plugin_tag,
                        level=Qgis.Warning,
                    )

            elif resa_dims and resa_dims.get("required"):
                QgsMessageLog.logMessage(
                    f"Info: Skipping RESAs for {log_name}: Required but prerequisite data (strip ends/runway width) incomplete.",
                    plugin_tag,
                    level=Qgis.Info,
                )

        except Exception as e_resa_section:
            QgsMessageLog.logMessage(
                f"Warning: Error processing RESA Section for {log_name}: {e_resa_section}",
                plugin_tag,
                level=Qgis.Warning,
            )

        # --- 5. Stopways ---
        # Placeholder: Add logic here if needed.
        # If Stopways are implemented, ensure attribute keys match 'stopway_resa_fields':
        # e.g., attributes = {'rwy': runway_name, 'desc': 'Stopway', ..., 'end_desig': ..., 'ref_mos': ...}

        QgsMessageLog.logMessage(
            f"Finished physical geometry processing for {log_name}. Generated {len(generated_elements)} element features.",
            plugin_tag,
            level=Qgis.Success,
        )

        return generated_elements if generated_elements else None

    def _generate_airport_wide_ols(
        self,
        processed_runway_data_list: List[dict],
        ols_layer_group: QgsLayerTreeGroup,
        reference_elevation_datum: float,
        icao_code: str,
    ) -> bool:
        """
        Generates airport-wide OLS: IHS, Conical (with contours), OHS, Transitional.
        Accounts for displaced thresholds when calculating IHS base strip outlines.
        Requires processed runway data, RED, group, and ICAO code.
        Logs start/end, key parameters, warnings, and critical errors.
        """
        plugin_tag = PLUGIN_TAG
        # Constants for this method
        BUFFER_SEGMENTS = 36  # Segments for geometry buffers

        QgsMessageLog.logMessage(
            f"Starting Airport-Wide OLS Generation (Transitional, IHS, Conical, OHS - Applying RED: {reference_elevation_datum:.2f}m)",
            plugin_tag,
            level=Qgis.Info,
        )
        overall_success = (
            False  # Tracks if *any* airport-wide OLS layer was successfully created
        )

        # --- Get IHS Parameters ---
        ihs_base_height_agl = ols_dimensions.get_ihs_base_height()
        if ihs_base_height_agl is None:
            QgsMessageLog.logMessage(
                "Cannot generate Airport-Wide OLS: Failed to retrieve IHS base height parameter.",
                plugin_tag,
                level=Qgis.Critical,
            )
            return False
        IHS_ELEVATION_AMSL = reference_elevation_datum + ihs_base_height_agl

        # --- Initialize Variables ---
        ihs_base_geom: Optional[QgsGeometry] = None
        outer_conical_geom: Optional[QgsGeometry] = None
        highest_arc_num = 0
        highest_precision_type_str = "Non-Instrument (NI)"  # Default lowest precision

        # --- 1. Generate Individual Strip Outline Geometries ---
        strip_outline_geoms: List[QgsGeometry] = []
        QgsMessageLog.logMessage(
            "Generating individual runway strip outlines for IHS base...",
            plugin_tag,
            level=Qgis.Info,
        )

        if not processed_runway_data_list:
            QgsMessageLog.logMessage(
                "Cannot generate IHS base: No processed runway data available.",
                plugin_tag,
                level=Qgis.Warning,
            )

        for i, rwy_data in enumerate(processed_runway_data_list):
            runway_processed = False  # Flag for this specific runway
            try:  # Broad try block for processing a single runway's outline
                rwy_name = rwy_data.get(
                    "short_name", f"RWY_{rwy_data.get('original_index','?')}"
                )
                thr_point = rwy_data.get("thr_point")
                rec_thr_point = rwy_data.get("rec_thr_point")
                arc_num_str = rwy_data.get("arc_num")
                type1_str = rwy_data.get("type1")
                type2_str = rwy_data.get("type2")
                rwy_data.get("width")

                # Robustly get displacement values
                disp_val_1 = rwy_data.get("thr_displaced_1")
                disp_val_2 = rwy_data.get("thr_displaced_2")
                disp_thr_1 = float(disp_val_1) if disp_val_1 is not None else 0.0
                disp_thr_2 = float(disp_val_2) if disp_val_2 is not None else 0.0

                # Check Essential Data
                if not all([thr_point, rec_thr_point, arc_num_str]):
                    # Use Warning level for skips that prevent outline generation
                    QgsMessageLog.logMessage(
                        f"Skipping {rwy_name} strip outline - Missing essential data (Points/ARC Str).",
                        plugin_tag,
                        level=Qgis.Warning,
                    )
                    continue

                # Check ARC Number
                try:
                    arc_num = int(arc_num_str)
                    highest_arc_num = max(highest_arc_num, arc_num)
                except (ValueError, TypeError):
                    QgsMessageLog.logMessage(
                        f"Skipping {rwy_name} strip outline - Invalid ARC number '{arc_num_str}'.",
                        plugin_tag,
                        level=Qgis.Warning,
                    )
                    continue

                # Track highest precision type
                type_order = [
                    "",
                    "Non-Instrument (NI)",
                    "Non-Precision Approach (NPA)",
                    "Precision Approach CAT I",
                    "Precision Approach CAT II/III",
                ]
                current_type1_idx = (
                    type_order.index(type1_str) if type1_str in type_order else 1
                )
                current_type2_idx = (
                    type_order.index(type2_str) if type2_str in type_order else 1
                )
                current_max_type_str = type_order[
                    max(current_type1_idx, current_type2_idx)
                ]
                highest_idx_overall = (
                    type_order.index(highest_precision_type_str)
                    if highest_precision_type_str in type_order
                    else 1
                )
                if max(current_type1_idx, current_type2_idx) > highest_idx_overall:
                    highest_precision_type_str = current_max_type_str

                # Check Runway Parameters
                rwy_params = self._get_runway_parameters(thr_point, rec_thr_point)
                if not rwy_params:
                    QgsMessageLog.logMessage(
                        f"Skipping {rwy_name} strip outline - Failed runway params.",
                        plugin_tag,
                        level=Qgis.Warning,
                    )
                    continue

                # Check Physical Endpoints
                physical_endpoints_result = self._get_physical_runway_endpoints(
                    thr_point, rec_thr_point, disp_thr_1, disp_thr_2, rwy_params
                )
                if physical_endpoints_result is None:
                    QgsMessageLog.logMessage(
                        f"Skipping {rwy_name} strip outline - Failed physical endpoints calc.",
                        plugin_tag,
                        level=Qgis.Warning,
                    )
                    continue
                phys_p_start, phys_p_end, _ = physical_endpoints_result

                # Check Strip Dimensions
                strip_dims = rwy_data.get("calculated_strip_dims")
                if not strip_dims:
                    QgsMessageLog.logMessage(
                        f"Skipping {rwy_name} strip outline - 'calculated_strip_dims' was not found or invalid: {repr(strip_dims)}.",
                        plugin_tag,
                        level=Qgis.Warning,
                    )
                    continue

                # Check Strip Dimensions Content
                strip_width = strip_dims.get("overall_width")
                strip_ext = strip_dims.get("extension_length")
                is_width_valid = (
                    isinstance(strip_width, (int, float)) and strip_width > 0
                )
                is_ext_valid = isinstance(strip_ext, (int, float)) and strip_ext >= 0
                if not is_width_valid or not is_ext_valid:
                    QgsMessageLog.logMessage(
                        f"Skipping {rwy_name} strip outline - invalid content in strip_dims (W:{strip_width}, E:{strip_ext}).",
                        plugin_tag,
                        level=Qgis.Warning,
                    )
                    continue

                # Check Strip Endpoint Projection
                strip_end_p = phys_p_start.project(strip_ext, rwy_params["azimuth_r_p"])
                strip_end_r = phys_p_end.project(strip_ext, rwy_params["azimuth_p_r"])
                if not strip_end_p or not strip_end_r:
                    QgsMessageLog.logMessage(
                        f"Skipping {rwy_name} strip outline - failed strip end point projection.",
                        plugin_tag,
                        level=Qgis.Warning,
                    )
                    continue

                # Check IHS Radius Calculation
                ihs_params = ols_dimensions.get_ols_params(
                    arc_num, current_max_type_str, "IHS"
                )
                ihs_end_radius = ihs_params.get("radius") if ihs_params else None
                if (
                    ihs_end_radius is None
                    or not isinstance(ihs_end_radius, (int, float))
                    or ihs_end_radius <= 0
                ):
                    if isinstance(strip_width, (int, float)) and strip_width > 0:
                        ihs_end_radius = strip_width / 2.0
                        # Info log for using fallback radius might be useful even in production
                        QgsMessageLog.logMessage(
                            f"Info: Using fallback radius {ihs_end_radius:.2f}m for {rwy_name} IHS outline (based on strip width).",
                            plugin_tag,
                            level=Qgis.Info,
                        )
                    else:
                        QgsMessageLog.logMessage(
                            f"Skipping {rwy_name} strip outline - Cannot determine valid IHS radius (Params:{ihs_params}, Width:{strip_width}).",
                            plugin_tag,
                            level=Qgis.Warning,
                        )
                        continue

                # --- Geometry Generation ---
                try:  # Generate the geometry
                    buffer_p = QgsGeometry.fromPointXY(strip_end_p).buffer(
                        ihs_end_radius, BUFFER_SEGMENTS
                    )
                    buffer_r = QgsGeometry.fromPointXY(strip_end_r).buffer(
                        ihs_end_radius, BUFFER_SEGMENTS
                    )

                    corner_p_l = strip_end_p.project(
                        ihs_end_radius, rwy_params["azimuth_perp_l"]
                    )
                    corner_p_r = strip_end_p.project(
                        ihs_end_radius, rwy_params["azimuth_perp_r"]
                    )
                    corner_r_l = strip_end_r.project(
                        ihs_end_radius, rwy_params["azimuth_perp_l"]
                    )
                    corner_r_r = strip_end_r.project(
                        ihs_end_radius, rwy_params["azimuth_perp_r"]
                    )
                    connector = None
                    if all([corner_p_l, corner_p_r, corner_r_l, corner_r_r]):
                        connector = self._create_polygon_from_corners(
                            [corner_p_l, corner_p_r, corner_r_r, corner_r_l],
                            f"Strip Connector {rwy_name}",
                        )

                    components = [
                        g
                        for g in [buffer_p, buffer_r, connector]
                        if g and not g.isEmpty()
                    ]

                    if len(components) >= 2:
                        runway_strip_geom = QgsGeometry.unaryUnion(components)
                        if runway_strip_geom is None or runway_strip_geom.isEmpty():
                            runway_strip_geom = None  # Ensure it's None if union failed

                        if runway_strip_geom:  # Check if union produced something
                            valid_geom = runway_strip_geom.makeValid()
                            if (
                                valid_geom
                                and not valid_geom.isEmpty()
                                and valid_geom.isGeosValid()
                            ):
                                strip_outline_geoms.append(valid_geom)
                                runway_processed = True  # Mark success for this runway
                            else:
                                QgsMessageLog.logMessage(
                                    f"Warning: Generated strip outline for {rwy_name} is invalid after makeValid(), skipping.",
                                    plugin_tag,
                                    level=Qgis.Warning,
                                )
                    elif not components:
                        QgsMessageLog.logMessage(
                            f"Warning: Skipping strip outline for {rwy_name}: Failed to generate valid buffer/connector components.",
                            plugin_tag,
                            level=Qgis.Warning,
                        )
                    # else: Only one component was valid, cannot form outline.

                except Exception as e_strip_geom:
                    QgsMessageLog.logMessage(
                        f"Error generating strip outline geom for {rwy_name}: {e_strip_geom}",
                        plugin_tag,
                        level=Qgis.Warning,
                    )

            except Exception as loop_body_error:
                current_rwy_id = rwy_data.get(
                    "short_name", rwy_data.get("original_index", f"Unknown Index {i}")
                )
                QgsMessageLog.logMessage(
                    f"CRITICAL: Unexpected error processing runway {current_rwy_id} (Loop Index {i}) in Airport OLS strip outline loop: {loop_body_error}\n{traceback.format_exc()}",
                    plugin_tag,
                    level=Qgis.Critical,
                )
                continue  # Process next runway if possible

        # --- End of loop ---

        # --- 2. Combine Outlines & Calculate Convex Hull ---
        if not strip_outline_geoms:
            QgsMessageLog.logMessage(
                "IHS Generation Failed: No valid runway strip outlines were generated.",
                plugin_tag,
                level=Qgis.Critical,
            )
            QgsMessageLog.logMessage(
                f"(Info: Highest runway precision type detected: {highest_precision_type_str}, ARC: {highest_arc_num})",
                plugin_tag,
                level=Qgis.Info,
            )
            return False

        QgsMessageLog.logMessage(
            f"Creating IHS base polygon from Convex Hull of {len(strip_outline_geoms)} strip outline(s)...",
            plugin_tag,
            level=Qgis.Info,
        )
        try:
            merged_geom = QgsGeometry.unaryUnion(strip_outline_geoms)
            if not merged_geom or merged_geom.isEmpty():
                raise ValueError("unaryUnion of strip outlines failed.")
            ihs_base_geom = merged_geom.convexHull()
            if not ihs_base_geom or ihs_base_geom.isEmpty():
                raise ValueError("convexHull calculation failed.")
            if not ihs_base_geom.isGeosValid():
                QgsMessageLog.logMessage(
                    "IHS base convex hull is invalid, attempting makeValid()...",
                    plugin_tag,
                    level=Qgis.Info,
                )
                ihs_base_geom = ihs_base_geom.makeValid()
            if not ihs_base_geom or not ihs_base_geom.isGeosValid():
                raise ValueError("IHS base geometry invalid after makeValid().")
        except Exception as e_hull:
            QgsMessageLog.logMessage(
                f"IHS Generation Failed: Error during Convex Hull creation: {e_hull}",
                plugin_tag,
                level=Qgis.Critical,
            )
            return False

        # --- 3. Create IHS Layer ---
        if ihs_base_geom:
            try:
                ihs_ref_params = ols_dimensions.get_ols_params(
                    highest_arc_num, highest_precision_type_str, "IHS"
                )
                ref_text = (
                    ihs_ref_params.get("ref", "MOS 8.2.18")
                    if ihs_ref_params
                    else "MOS 8.2.18"
                )
                fields = self._get_ols_fields("IHS")
                feature = QgsFeature(fields)
                feature.setGeometry(ihs_base_geom)
                attr_map = {
                    "rwy_name": self.tr("Airport Wide"),
                    "surface": "IHS",
                    "section_desc": "Inner Horizontal Surface",
                    "elev_m": IHS_ELEVATION_AMSL,
                    "height_agl": ihs_base_height_agl,
                    "ref_mos": ref_text,
                }
                for name, value in attr_map.items():
                    idx = fields.indexFromName(name)
                    print(f"Assigning {name} = {value}, idx = {idx}")  # DEBUG
                    if idx != -1:
                        feature.setAttribute(idx, value)
                layer = self._create_and_add_layer(
                    "Polygon",
                    f"OLS_IHS_{icao_code}",
                    f"{self.tr('OLS')} IHS {icao_code}",
                    fields,
                    [feature],
                    ols_layer_group,
                    "OLS IHS",
                )
                if layer:
                    overall_success = True
            except Exception as e_ihs_layer:
                QgsMessageLog.logMessage(
                    f"Critical error creating IHS Feature/Layer: {e_ihs_layer}\n{traceback.format_exc()}",
                    plugin_tag,
                    level=Qgis.Critical,
                )
                ihs_base_geom = None

        # --- 4. Generate Conical Surface & Contours ---
        conical_layer_created = False
        if ihs_base_geom:
            conical_params = ols_dimensions.get_ols_params(
                highest_arc_num, highest_precision_type_str, "CONICAL"
            )
            if conical_params:
                height_extent_agl = conical_params.get("height_extent_agl")
                slope = conical_params.get("slope")
                ref = conical_params.get("ref", "MOS 8.2.19")
                if (
                    slope is not None
                    and slope > 0
                    and height_extent_agl is not None
                    and height_extent_agl > 0
                ):
                    horizontal_extent = height_extent_agl / slope
                    conical_outer_elevation = IHS_ELEVATION_AMSL + height_extent_agl
                    QgsMessageLog.logMessage(
                        f"Generating Conical Surface: Slope={slope*100:.1f}%, H Ext={height_extent_agl:.1f}m, Horiz Ext={horizontal_extent:.1f}m, Top Elev AMSL={conical_outer_elevation:.2f}m",
                        plugin_tag,
                        level=Qgis.Info,
                    )
                    try:
                        temp_outer_geom = ihs_base_geom.buffer(
                            horizontal_extent, BUFFER_SEGMENTS
                        )
                        if temp_outer_geom and not temp_outer_geom.isEmpty():
                            temp_outer_geom = temp_outer_geom.makeValid()
                            if temp_outer_geom.isGeosValid():
                                outer_conical_geom = temp_outer_geom
                                temp_conical_geom = outer_conical_geom.difference(
                                    ihs_base_geom
                                )
                                if temp_conical_geom:
                                    temp_conical_geom = temp_conical_geom.makeValid()
                                if (
                                    temp_conical_geom
                                    and not temp_conical_geom.isEmpty()
                                    and temp_conical_geom.isGeosValid()
                                ):
                                    fields = self._get_ols_fields("Conical")
                                    feature = QgsFeature(fields)
                                    feature.setGeometry(temp_conical_geom)
                                    conical_total_height_agl = (
                                        ihs_base_height_agl + height_extent_agl
                                    )
                                    attr_map = {
                                        "rwy_name": self.tr("Airport Wide"),
                                        "surface": "Conical",
                                        "section_desc": "Conical Surface",
                                        "elev_m": conical_outer_elevation,
                                        "height_agl": conical_total_height_agl,
                                        "slope_perc": slope * 100.0,
                                        "ref_mos": ref,
                                        "height_extent": height_extent_agl,
                                    }
                                    for name, value in attr_map.items():
                                        idx = fields.indexFromName(name)
                                        if idx != -1:
                                            feature.setAttribute(idx, value)
                                    layer = self._create_and_add_layer(
                                        "Polygon",
                                        f"OLS_Conical_{icao_code}",
                                        f"{self.tr('OLS')} Conical {icao_code}",
                                        fields,
                                        [feature],
                                        ols_layer_group,
                                        "OLS Conical",
                                    )
                                    if layer:
                                        overall_success = True
                                        conical_layer_created = True
                                else:
                                    QgsMessageLog.logMessage(
                                        "Failed generate valid Conical ring geometry (difference/makeValid).",
                                        plugin_tag,
                                        level=Qgis.Warning,
                                    )
                            else:
                                QgsMessageLog.logMessage(
                                    "Failed generate valid outer Conical buffer after makeValid.",
                                    plugin_tag,
                                    level=Qgis.Warning,
                                )
                        else:
                            QgsMessageLog.logMessage(
                                "Failed generate outer Conical buffer (buffer returned None/empty).",
                                plugin_tag,
                                level=Qgis.Warning,
                            )
                    except Exception as e_conical:
                        QgsMessageLog.logMessage(
                            f"Error during Conical Surface generation: {e_conical}",
                            plugin_tag,
                            level=Qgis.Warning,
                        )
                elif height_extent_agl is not None and height_extent_agl <= 0:
                    QgsMessageLog.logMessage(
                        "Skipping Conical Surface: Height extent zero or negative.",
                        plugin_tag,
                        level=Qgis.Info,
                    )
                else:
                    QgsMessageLog.logMessage(
                        "Skipping Conical Surface: Invalid parameters (Slope/Height Extent).",
                        plugin_tag,
                        level=Qgis.Warning,
                    )
            else:
                QgsMessageLog.logMessage(
                    f"Skipping Conical Surface: No params found for Code {highest_arc_num}, Type {highest_precision_type_str}.",
                    plugin_tag,
                    level=Qgis.Warning,
                )

        # --- 4b. Generate Conical CONTOURS ---
        if (
            conical_layer_created
            and ihs_base_geom
            and outer_conical_geom
            and slope
            and height_extent_agl
            and height_extent_agl > 0
            and conical_outer_elevation is not None
        ):
            QgsMessageLog.logMessage(
                f"Generating Conical Contours at {CONICAL_CONTOUR_INTERVAL}m intervals...",
                plugin_tag,
                level=Qgis.Info,
            )
            contour_features: List[QgsFeature] = []
            ref = conical_params.get("ref", "MOS 8.2.19")
            fields = self._get_conical_contour_fields()

            def _extract_exterior_ring_line(geom: QgsGeometry) -> Optional[QgsGeometry]:
                # Returns a LineString geometry of the exterior ring, or None if not available.
                poly = geom.asPolygon()
                if poly and len(poly) > 0 and len(poly[0]) > 1:
                    return QgsGeometry.fromPolylineXY(poly[0])
                multipoly = geom.asMultiPolygon()
                if multipoly and len(multipoly) > 0 and len(multipoly[0]) > 0:
                    return QgsGeometry.fromPolylineXY(multipoly[0][0])
                return None

            # 1. Start contour at IHS base
            start_geom = QgsGeometry(ihs_base_geom)
            if start_geom and not start_geom.isEmpty() and start_geom.isGeosValid():
                line_geom = _extract_exterior_ring_line(start_geom)
                if line_geom and not line_geom.isEmpty() and line_geom.isGeosValid():
                    feat = QgsFeature(fields)
                    feat.setGeometry(line_geom)
                    feat.setAttribute(
                        fields.indexFromName("surface"),
                        f"Conical Contour {IHS_ELEVATION_AMSL:.0f}m",
                    )
                    feat.setAttribute(
                        fields.indexFromName("contour_elev_am"), IHS_ELEVATION_AMSL
                    )
                    feat.setAttribute(fields.indexFromName("contour_hgt_abv"), 0)
                    feat.setAttribute(fields.indexFromName("ref_mos"), ref)
                    contour_features.append(feat)
                    QgsMessageLog.logMessage(
                        f"Conical start contour at {IHS_ELEVATION_AMSL:.2f}m AMSL.",
                        plugin_tag,
                        Qgis.Info,
                    )
                else:
                    QgsMessageLog.logMessage(
                        "Failed to extract exterior ring for IHS base.",
                        plugin_tag,
                        Qgis.Warning,
                    )

            # 2. Interval contours (main loop)
            if IHS_ELEVATION_AMSL % CONICAL_CONTOUR_INTERVAL == 0:
                first_contour_elev_amsl = IHS_ELEVATION_AMSL + CONICAL_CONTOUR_INTERVAL
            else:
                first_contour_elev_amsl = (
                    math.ceil(IHS_ELEVATION_AMSL / CONICAL_CONTOUR_INTERVAL)
                    * CONICAL_CONTOUR_INTERVAL
                )
            current_target_contour_elev_amsl = first_contour_elev_amsl

            while current_target_contour_elev_amsl < conical_outer_elevation - 1e-6:
                contour_h_above_ihs = min(
                    current_target_contour_elev_amsl - IHS_ELEVATION_AMSL,
                    height_extent_agl,
                )
                if contour_h_above_ihs < 1e-6:
                    current_target_contour_elev_amsl += CONICAL_CONTOUR_INTERVAL
                    continue
                try:
                    horizontal_dist = contour_h_above_ihs / slope
                    outer_geom = ihs_base_geom.buffer(horizontal_dist, BUFFER_SEGMENTS)
                    if (
                        outer_geom
                        and not outer_geom.isEmpty()
                        and outer_geom.isGeosValid()
                    ):
                        line_geom = _extract_exterior_ring_line(outer_geom)
                        if (
                            line_geom
                            and not line_geom.isEmpty()
                            and line_geom.isGeosValid()
                        ):
                            feat = QgsFeature(fields)
                            feat.setGeometry(line_geom)
                            feat.setAttribute(
                                fields.indexFromName("surface"),
                                f"Conical Contour {current_target_contour_elev_amsl:.0f}m",
                            )
                            feat.setAttribute(
                                fields.indexFromName("contour_elev_am"),
                                current_target_contour_elev_amsl,
                            )
                            feat.setAttribute(
                                fields.indexFromName("contour_hgt_abv"),
                                contour_h_above_ihs,
                            )
                            feat.setAttribute(fields.indexFromName("ref_mos"), ref)
                            contour_features.append(feat)
                            # QgsMessageLog.logMessage(
                            #     f"Conical interval contour at {current_target_contour_elev_amsl:.2f}m AMSL.", plugin_tag, Qgis.Info
                            # )
                except Exception as e_contour:
                    QgsMessageLog.logMessage(
                        f"Error generating conical interval contour at elev={current_target_contour_elev_amsl}: {e_contour}",
                        plugin_tag,
                        Qgis.Warning,
                    )
                current_target_contour_elev_amsl += CONICAL_CONTOUR_INTERVAL

            # 3. End contour at conical outer elevation
            final_dist = height_extent_agl / slope  # buffer distance to outer edge
            end_geom = ihs_base_geom.buffer(final_dist, BUFFER_SEGMENTS)
            if end_geom and not end_geom.isEmpty() and end_geom.isGeosValid():
                line_geom = _extract_exterior_ring_line(end_geom)
                if line_geom and not line_geom.isEmpty() and line_geom.isGeosValid():
                    # Avoid duplicate (shouldn't happen but check)
                    if not any(
                        abs(f.attribute("contour_elev_am") - conical_outer_elevation)
                        < 1e-3
                        for f in contour_features
                    ):
                        feat = QgsFeature(fields)
                        feat.setGeometry(line_geom)
                        feat.setAttribute(
                            fields.indexFromName("surface"),
                            f"Conical Contour {conical_outer_elevation:.0f}m",
                        )
                        feat.setAttribute(
                            fields.indexFromName("contour_elev_am"),
                            conical_outer_elevation,
                        )
                        feat.setAttribute(
                            fields.indexFromName("contour_hgt_abv"), height_extent_agl
                        )
                        feat.setAttribute(fields.indexFromName("ref_mos"), ref)
                        contour_features.append(feat)
                        QgsMessageLog.logMessage(
                            f"Conical end contour at {conical_outer_elevation:.2f}m AMSL.",
                            plugin_tag,
                            Qgis.Info,
                        )
                else:
                    QgsMessageLog.logMessage(
                        "Failed to extract exterior ring for conical outer edge.",
                        plugin_tag,
                        Qgis.Warning,
                    )

            # 4. Layer creation
            if contour_features:
                contour_layer = self._create_and_add_layer(
                    "LineString",
                    f"OLS_Conical_Contours_{icao_code}",
                    f"{self.tr('OLS')} Conical Contours {icao_code}",
                    fields,
                    contour_features,
                    ols_layer_group,
                    "OLS Conical Contour",
                )
                if contour_layer:
                    overall_success = True
                    QgsMessageLog.logMessage(
                        f"Created conical contour layer for {icao_code}, {len(contour_features)} features.",
                        plugin_tag,
                        Qgis.Info,
                    )
            else:
                QgsMessageLog.logMessage(
                    f"No conical contours generated for {icao_code}.",
                    plugin_tag,
                    Qgis.Warning,
                )

        # --- 5. Generate Outer Horizontal Surface (OHS) ---
        ohs_params = ols_dimensions.get_ols_params(
            highest_arc_num, highest_precision_type_str, "OHS"
        )
        if ohs_params:
            radius = ohs_params.get("radius")
            height_agl = ohs_params.get("height_agl")
            ref = ohs_params.get("ref", "MOS 8.2.20")
            QgsMessageLog.logMessage(
                f"OHS required (Code {highest_arc_num}, Type {highest_precision_type_str}). Radius={radius}m, Height={height_agl}m AGL.",
                plugin_tag,
                level=Qgis.Info,
            )
            if radius is not None and height_agl is not None and radius > 0:
                ohs_elevation_amsl = reference_elevation_datum + height_agl
                arp_point_xy: Optional[QgsPointXY] = None
                project = QgsProject.instance()
                # Construct the expected ARP layer name that your plugin creates
                expected_arp_layer_name = f"{icao_code} {self.tr('ARP')}"  # Match display name from create_arp_layer

                arp_layer_candidates = project.mapLayersByName(expected_arp_layer_name)

                found_arp_point_layer = None
                for lyr in arp_layer_candidates:
                    if (
                        lyr.isValid()
                        and lyr.geometryType() == QgsWkbTypes.PointGeometry
                    ):  # Check for Point geometry
                        found_arp_point_layer = lyr
                        break  # Found a suitable point layer

                if found_arp_point_layer:
                    arp_feat = next(found_arp_point_layer.getFeatures(), None)
                    if (
                        arp_feat
                        and arp_feat.hasGeometry()
                        and not arp_feat.geometry().isNull()
                    ):
                        geom = arp_feat.geometry()
                        actual_wkb_type = geom.wkbType()

                        # QgsMessageLog.logMessage(
                        #     f"ARP feature for OHS: Layer='{found_arp_point_layer.name()}', "
                        #     f"Geom valid? {geom.isGeosValid()}, "
                        #     f"WKBType Int: {actual_wkb_type} ({QgsWkbTypes.displayString(actual_wkb_type)})",
                        #     PLUGIN_TAG,
                        #     Qgis.Info,
                        # )

                        acceptable_point_wkb_types = {
                            QgsWkbTypes.Point,
                            QgsWkbTypes.PointZ,
                            QgsWkbTypes.PointM,
                            QgsWkbTypes.PointZM,
                            QgsWkbTypes.MultiPoint,
                            QgsWkbTypes.MultiPointZ,
                            QgsWkbTypes.MultiPointM,
                            QgsWkbTypes.MultiPointZM,
                        }

                        if actual_wkb_type in acceptable_point_wkb_types:
                            if QgsWkbTypes.isMultiType(actual_wkb_type):
                                multi_point_geom = geom.constGet()
                                if (
                                    multi_point_geom
                                    and multi_point_geom.numGeometries() > 0
                                ):
                                    point_part = multi_point_geom.geometryN(0)
                                    if point_part:
                                        arp_point_xy = QgsPointXY(
                                            point_part.x(), point_part.y()
                                        )
                            else:
                                arp_point_xy = geom.asPoint()
                        else:
                            QgsMessageLog.logMessage(
                                f"ARP layer '{found_arp_point_layer.name()}' feature has WKBType {QgsWkbTypes.displayString(actual_wkb_type)}, NOT an acceptable Point type for OHS.",
                                PLUGIN_TAG,
                                level=Qgis.Warning,
                            )

                    else:
                        QgsMessageLog.logMessage(
                            f"ARP layer '{found_arp_point_layer.name()}' found, but no valid features/geometry for OHS.",
                            PLUGIN_TAG,
                            level=Qgis.Warning,
                        )
                else:
                    QgsMessageLog.logMessage(
                        f"Could not find a valid POINT layer named '{expected_arp_layer_name}' for OHS.",
                        PLUGIN_TAG,
                        level=Qgis.Warning,
                    )

                if arp_point_xy:  # Only proceed if arp_point_xy was successfully set
                    try:
                        center_geom = QgsGeometry.fromPointXY(arp_point_xy)
                        ohs_full_circle_geom = center_geom.buffer(
                            radius, 144
                        )  # Use high segments
                        if ohs_full_circle_geom and not ohs_full_circle_geom.isEmpty():
                            ohs_full_circle_geom = ohs_full_circle_geom.makeValid()
                            if ohs_full_circle_geom.isGeosValid():
                                ohs_final_geom = ohs_full_circle_geom
                                if (
                                    outer_conical_geom
                                    and outer_conical_geom.isGeosValid()
                                ):
                                    # QgsMessageLog.logMessage(
                                    #     "Attempting to difference Conical outer boundary from OHS circle.",
                                    #     plugin_tag,
                                    #     level=Qgis.Info,
                                    # )
                                    try:
                                        difference_geom = (
                                            ohs_full_circle_geom.difference(
                                                outer_conical_geom
                                            )
                                        )
                                        if difference_geom:
                                            difference_geom = (
                                                difference_geom.makeValid()
                                            )
                                            if (
                                                difference_geom.isGeosValid()
                                                and not difference_geom.isEmpty()
                                            ):
                                                ohs_final_geom = difference_geom
                                            else:
                                                QgsMessageLog.logMessage(
                                                    "Warning: Difference op for OHS resulted in invalid/empty geometry. Using full circle.",
                                                    plugin_tag,
                                                    level=Qgis.Warning,
                                                )
                                        else:
                                            QgsMessageLog.logMessage(
                                                "Warning: Difference op for OHS returned None. Using full circle.",
                                                plugin_tag,
                                                level=Qgis.Warning,
                                            )
                                    except Exception as e_diff:
                                        QgsMessageLog.logMessage(
                                            f"Warning: Error during OHS difference operation: {e_diff}. Using full circle.",
                                            plugin_tag,
                                            level=Qgis.Warning,
                                        )
                                else:
                                    QgsMessageLog.logMessage(
                                        "Info: Conical outer boundary not available or invalid for OHS difference. Using full OHS circle.",
                                        plugin_tag,
                                        level=Qgis.Info,
                                    )

                                fields = self._get_ols_fields("OHS")
                                feature = QgsFeature(fields)
                                feature.setGeometry(ohs_final_geom)
                                attr_map = {
                                    "surface": "OHS",
                                    "section_desc": "Outer Horizontal Surface",
                                    "elev_m": ohs_elevation_amsl,
                                    "height_agl": height_agl,
                                    "ref_mos": ref,
                                    "radius_m": radius,
                                }
                                if fields.indexFromName("rwy_name") != -1:
                                    attr_map["rwy_name"] = self.tr("Airport Wide")
                                for name, value in attr_map.items():
                                    idx = fields.indexFromName(name)
                                    print(
                                        f"Assigning {name} = {value}, idx = {idx}"
                                    )  # DEBUG
                                    if idx != -1:
                                        feature.setAttribute(idx, value)
                                layer = self._create_and_add_layer(
                                    "Polygon",
                                    f"OLS_OHS_{icao_code}",
                                    f"{self.tr('OLS')} OHS {icao_code}",
                                    fields,
                                    [feature],
                                    ols_layer_group,
                                    "OLS OHS",
                                )
                                if layer:
                                    overall_success = True
                            else:
                                QgsMessageLog.logMessage(
                                    "Failed create valid OHS full circle geom (makeValid failed).",
                                    plugin_tag,
                                    level=Qgis.Warning,
                                )
                        else:
                            QgsMessageLog.logMessage(
                                "Failed create OHS full circle geom (buffer failed).",
                                plugin_tag,
                                level=Qgis.Warning,
                            )
                    except Exception as e_ohs:
                        QgsMessageLog.logMessage(
                            f"Error generating OHS: {e_ohs}",
                            plugin_tag,
                            level=Qgis.Critical,
                        )
                else:
                    QgsMessageLog.logMessage(
                        "Skipping OHS generation: Could not find ARP point.",
                        plugin_tag,
                        level=Qgis.Warning,
                    )
            else:
                QgsMessageLog.logMessage(
                    "Skipping OHS generation: Invalid parameters (Radius/Height AGL).",
                    plugin_tag,
                    level=Qgis.Warning,
                )
        else:
            QgsMessageLog.logMessage(
                "Outer Horizontal Surface not required for this airport configuration.",
                plugin_tag,
                level=Qgis.Info,
            )

        # --- 6. Generate Transitional Surfaces ---
        if ihs_base_geom and IHS_ELEVATION_AMSL is not None:
            # Note: Transitional feature generation logs its own start/finish messages inside the helper now
            # QgsMessageLog.logMessage("Generating Transitional Surface features...", plugin_tag, level=Qgis.Info) # Removed from here
            transitional_features = []
            try:
                target_crs = QgsProject.instance().crs()
                if target_crs and target_crs.isValid():
                    transitional_features, transitional_contour_features = (
                        self._generate_transitional_features(
                            processed_runway_data_list,
                            IHS_ELEVATION_AMSL,
                            target_crs,
                        )
                    )
                    if transitional_features:
                        transitional_fields = self._get_ols_fields("Transitional")
                        poly_layer = self._create_and_add_layer(
                            "Polygon",
                            f"OLS_Transitional_{icao_code}",
                            f"{self.tr('OLS')} Transitional {icao_code}",
                            transitional_fields,
                            transitional_features,
                            ols_layer_group,
                            "OLS Transitional",
                        )
                        if poly_layer:
                            overall_success = True
                            QgsMessageLog.logMessage(
                                f"Created Transitional Polygon Layer: {poly_layer.name()} ({len(transitional_features)} features)",
                                PLUGIN_TAG,
                                level=Qgis.Info,
                            )

                    # --- Create Transitional Contour Line Layer ---
                    if transitional_contour_features:
                        contour_fields = self._get_transitional_contour_fields()
                        contour_layer = self._create_and_add_layer(
                            "LineString",
                            f"OLS_Transitional_Contours_{icao_code}",
                            f"{self.tr('OLS')} Transitional Contours {icao_code}",
                            contour_fields,
                            transitional_contour_features,
                            ols_layer_group,
                            "OLS Transitional Contour",
                        )
                        if contour_layer:
                            overall_success = True
                            QgsMessageLog.logMessage(
                                f"Created Transitional Contour Layer: {contour_layer.name()} ({len(transitional_contour_features)} features)",
                                PLUGIN_TAG,
                                level=Qgis.Info,
                            )
                    else:
                        QgsMessageLog.logMessage(
                            f"No Transitional Contour features created for {icao_code}.",
                            PLUGIN_TAG,
                            level=Qgis.Warning,
                        )
                else:
                    QgsMessageLog.logMessage(
                        "Skipping Transitional: Invalid Project CRS.",
                        plugin_tag,
                        level=Qgis.Warning,
                    )
            except Exception as e_trans:
                QgsMessageLog.logMessage(
                    f"Error during Transitional Surface generation/layer addition: {e_trans}\n{traceback.format_exc()}",
                    plugin_tag,
                    level=Qgis.Critical,
                )
        else:
            QgsMessageLog.logMessage(
                "Skipping Transitional Surface generation: IHS geometry or elevation not available/valid.",
                plugin_tag,
                level=Qgis.Info,
            )

        # --- Final Log ---
        QgsMessageLog.logMessage(
            f"Finished Airport-Wide OLS Generation.", plugin_tag, level=Qgis.Info
        )
        return overall_success

    # --- Geometry Helper Methods ---

    def _get_polygon_edges(
        self, polygon_geom: QgsGeometry
    ) -> List[Optional[QgsLineString]]:
        """Extracts exterior ring segments from a single polygon geometry."""
        if not polygon_geom or polygon_geom.isNull() or not polygon_geom.isGeosValid():
            return []
        if not polygon_geom.wkbType() in [Qgis.WkbType.Polygon, Qgis.WkbType.PolygonZ]:
            # Handle multipart potentially? For now, assume simple polygon input after makeValid
            return []

        try:
            poly = polygon_geom.constGet()  # Get QgsPolygon base object
            if not poly:
                return []
            exterior = poly.exteriorRing()
            if (
                not exterior
                or exterior.isEmpty()
                or not exterior.isGeosValid()
                or not exterior.isClosed()
            ):
                return []

            edges = []
            points = list(exterior.vertices())
            if len(points) < 4:
                return (
                    []
                )  # Need at least 3 unique points + closing point for a triangle

            for i in range(len(points) - 1):
                p1 = points[i]
                p2 = points[i + 1]
                epsilon = 1e-6
                if abs(p1.x() - p2.x()) > epsilon or abs(p1.y() - p2.y()) > epsilon:
                    try:
                        line = QgsLineString(
                            [QgsPointXY(p1.x(), p1.y()), QgsPointXY(p2.x(), p2.y())]
                        )
                        if line and not line.isEmpty():
                            edges.append(line)
                        else:
                            edges.append(None)
                    except Exception as e_line:
                        QgsMessageLog.logMessage(
                            f"Error creating edge line: {e_line}",
                            PLUGIN_TAG,
                            level=Qgis.Warning,
                        )
                        edges.append(None)
                else:
                    edges.append(None)  # Skip zero-length segments (based on XY)
            return edges
        except Exception as e:
            QgsMessageLog.logMessage(
                f"Error in _get_polygon_edges: {e}", PLUGIN_TAG, level=Qgis.Critical
            )
            return []

    def _get_elevation_at_point_along_gradient(
        self,
        point_xy: QgsPointXY,  # Input is QgsPointXY
        line_start_pt: QgsPointXY,
        line_end_pt: QgsPointXY,
        line_start_elev: float,
        line_end_elev: float,
        target_crs: QgsCoordinateReferenceSystem,
    ) -> Optional[float]:
        """Calculates elevation by projecting point onto line defined by start/end points/elevs."""
        plugin_tag = PLUGIN_TAG
        if None in [
            point_xy,
            line_start_pt,
            line_end_pt,
            line_start_elev,
            line_end_elev,
            target_crs,
        ]:
            return None

        epsilon = 1e-6
        if (
            abs(line_start_pt.x() - line_end_pt.x()) < epsilon
            and abs(line_start_pt.y() - line_end_pt.y()) < epsilon
        ):
            return line_start_elev

        try:
            dist_area = QgsDistanceArea()
            transform_context = QgsProject.instance().transformContext()
            dist_area.setSourceCrs(target_crs, transform_context)

            line_geom = QgsGeometry.fromPolylineXY([line_start_pt, line_end_pt])
            if line_geom.isNull():
                QgsMessageLog.logMessage(
                    "Failed elevation interpolation: Line geometry is null.",
                    plugin_tag,
                    level=Qgis.Warning,
                )
                return None

            line_length = dist_area.measureLine(line_start_pt, line_end_pt)
            if line_length < epsilon:
                return line_start_elev

            # Get the underlying primitive (should be QgsAbstractGeometry, likely QgsLineString)
            line_primitive = (
                line_geom.constGet()
            )  # Use constGet() for read-only access if possible
            if line_primitive is None:
                QgsMessageLog.logMessage(
                    "Failed elevation interpolation: Could not get geometry primitive.",
                    plugin_tag,
                    level=Qgis.Warning,
                )
                return None

            # Convert input point_xy to QgsPoint for closestSegment
            point_qgsp = QgsPoint(point_xy.x(), point_xy.y())

            # Call closestSegment on the primitive
            result_tuple = line_primitive.closestSegment(point_qgsp)

            if result_tuple is None or len(result_tuple) < 2:
                QgsMessageLog.logMessage(
                    "Failed elevation interpolation: closestSegment returned None or invalid tuple.",
                    plugin_tag,
                    level=Qgis.Warning,
                )
                return None

            closest_point_qgsp = result_tuple[1]

            if not isinstance(closest_point_qgsp, QgsPoint):
                QgsMessageLog.logMessage(
                    f"Failed elevation interpolation: closestSegment did not return QgsPoint as second element (got {type(closest_point_qgsp)}).",
                    plugin_tag,
                    level=Qgis.Warning,
                )
                return None

            projected_point_xy = QgsPointXY(
                closest_point_qgsp.x(), closest_point_qgsp.y()
            )

            dist_along = dist_area.measureLine(line_start_pt, projected_point_xy)
            dist_along = max(0.0, min(dist_along, line_length))
            fraction_along = dist_along / line_length

            elevation_diff = line_end_elev - line_start_elev
            interpolated_elev = line_start_elev + (fraction_along * elevation_diff)

            return interpolated_elev

        except AttributeError as e_attr:
            # Specific catch for attribute errors like 'closestSegment' not found
            QgsMessageLog.logMessage(
                f"AttributeError in elevation interpolation: {e_attr}. API mismatch?",
                plugin_tag,
                level=Qgis.Critical,
            )
            return None
        except TypeError as e_type:
            QgsMessageLog.logMessage(
                f"Critical TypeError in elevation interpolation: {e_type}. Check code.",
                plugin_tag,
                level=Qgis.Critical,
            )
            return None
        except Exception as e:
            QgsMessageLog.logMessage(
                f"Warning: Error in elevation interpolation: {e}",
                plugin_tag,
                level=Qgis.Warning,
            )
            return None

    # Add this new helper function to your SafeguardingBuilder class

    def _get_polygon_side_3d_points(
        self,
        surface_geom_2d: QgsGeometry,  # The 2D polygon of IA or BLS
        centerline_start_pt_xy: QgsPointXY,
        centerline_end_pt_xy: QgsPointXY,  # For IA, this is its own end; for BLS, its own end
        start_elevation_amsl: float,  # Elevation at centerline_start_pt_xy
        end_elevation_amsl: float,  # Elevation at centerline_end_pt_xy
        start_half_width: float,
        end_half_width: float,
        side_label: str,  # 'L' or 'R'
    ) -> Optional[
        Tuple[QgsPoint, QgsPoint]
    ]:  # Returns (inner_3d_pt, outer_3d_pt) for the specified side
        plugin_tag = PLUGIN_TAG  # Assuming PLUGIN_TAG is accessible or pass it

        """
        Calculates the 3D coordinates of the inner and outer points of one side
        of a sloped trapezoidal or rectangular surface (like IA or BLS).
        'inner' means closer to the reference threshold from which the surface originates.
        'outer' means further from that reference threshold.
        """
        if (
            not surface_geom_2d
            or surface_geom_2d.isEmpty()
            or not surface_geom_2d.isGeosValid()
        ):
            return None
        if None in [start_elevation_amsl, end_elevation_amsl]:
            return None

        # Determine the azimuth of the surface centerline
        surface_centerline_az = centerline_start_pt_xy.azimuth(centerline_end_pt_xy)
        if centerline_start_pt_xy.compare(centerline_end_pt_xy, 1e-3):
            surface_centerline_az = 0
            QgsMessageLog.logMessage(
                f"Debug _poly_side: CL start/end same for {side_label}, using az 0.",
                plugin_tag,
                Qgis.Info,
            )

        perp_az: float
        # This is the version that worked for your IA panels:
        side_label = side_label.upper()
        if side_label == "L":
            perp_az = (surface_centerline_az + 90.0) % 360.0  # Your "effective Left"
        elif side_label == "R":
            perp_az = (
                surface_centerline_az - 90.0 + 360.0
            ) % 360.0  # Your "effective Right"
        else:
            QgsMessageLog.logMessage(
                f"Debug _poly_side: Invalid side_label '{side_label}'.",
                plugin_tag,
                Qgis.Warning,
            )
            return None

        QgsMessageLog.logMessage(
            f"Debug _poly_side ({side_label}): surface_centerline_az={surface_centerline_az:.2f}, calculated_perp_az={perp_az:.2f}",
            plugin_tag,
            Qgis.Info,
        )  # DEBUG LOG

        p_inner_side_xy = centerline_start_pt_xy.project(start_half_width, perp_az)
        p_outer_side_xy = centerline_end_pt_xy.project(end_half_width, perp_az)

        if not p_inner_side_xy or not p_outer_side_xy:
            QgsMessageLog.logMessage(
                f"Debug _poly_side ({side_label}): Failed to project side points.",
                plugin_tag,
                Qgis.Warning,
            )
            return None

        # Log the calculated side points
        QgsMessageLog.logMessage(
            f"Debug _poly_side ({side_label}): p_inner_side_xy={p_inner_side_xy.asWkt()}, p_outer_side_xy={p_outer_side_xy.asWkt()}",
            plugin_tag,
            Qgis.Info,
        )  # DEBUG LOG

        p_inner_3d = QgsPoint(
            p_inner_side_xy.x(), p_inner_side_xy.y(), start_elevation_amsl
        )
        p_outer_3d = QgsPoint(
            p_outer_side_xy.x(), p_outer_side_xy.y(), end_elevation_amsl
        )

        return p_inner_3d, p_outer_3d

    def _flip_side_label(self, side_label: str) -> str:
        return "R" if side_label.upper() == "L" else "L"

    def _define_strip_edge_segment_3d(
        self,
        p_align_ia_inner_xy: QgsPointXY,  # XY point near IA inner edge (e.g., centerline of IA inner edge)
        p_align_bls_inner_xy: QgsPointXY,  # XY point near BLS inner edge (e.g., centerline of BLS inner edge)
        strip_half_width: float,
        outward_perp_az_from_rwy_cl: float,  # Azimuth from rwy CL to this strip edge (L or R)
        rwy_primary_thr_pt: QgsPointXY,  # For overall runway gradient
        rwy_reciprocal_thr_pt: QgsPointXY,
        rwy_primary_thr_elev: float,
        rwy_reciprocal_thr_elev: float,
    ) -> Optional[
        Tuple[QgsPoint, QgsPoint]
    ]:  # Returns (start_3d_on_strip, end_3d_on_strip)
        """Defines the 3D segment of the ITS base along the runway strip edge."""

        if None in [rwy_primary_thr_elev, rwy_reciprocal_thr_elev]:
            return None

        # Project to strip edge
        strip_p1_xy = p_align_ia_inner_xy.project(
            strip_half_width, outward_perp_az_from_rwy_cl
        )
        strip_p2_xy = p_align_bls_inner_xy.project(
            strip_half_width, outward_perp_az_from_rwy_cl
        )

        if not strip_p1_xy or not strip_p2_xy:
            return None

        # Get elevations along runway gradient
        z1_strip = self._get_elevation_at_point_along_gradient(
            strip_p1_xy,
            rwy_primary_thr_pt,
            rwy_reciprocal_thr_pt,
            rwy_primary_thr_elev,
            rwy_reciprocal_thr_elev,
            QgsProject.instance().crs(),
        )
        z2_strip = self._get_elevation_at_point_along_gradient(
            strip_p2_xy,
            rwy_primary_thr_pt,
            rwy_reciprocal_thr_pt,
            rwy_primary_thr_elev,
            rwy_reciprocal_thr_elev,
            QgsProject.instance().crs(),
        )

        if z1_strip is None or z2_strip is None:
            return None

        p1_strip_3d = QgsPoint(strip_p1_xy.x(), strip_p1_xy.y(), z1_strip)
        p2_strip_3d = QgsPoint(strip_p2_xy.x(), strip_p2_xy.y(), z2_strip)

        return p1_strip_3d, p2_strip_3d

    def _clip_3d_segment_to_elevation(
        self, p1: QgsPoint, p2: QgsPoint, clip_elevation: float
    ) -> Optional[Tuple[QgsPoint, QgsPoint]]:
        """
        Clips a 3D line segment (defined by QgsPoint with Z) against a horizontal plane.
        Returns the portion of the segment below or at the clip_elevation.
        Assumes p1 and p2 have valid Z values.
        Returns None if the entire segment is above the clip elevation.
        """
        if not all([p1, p2]):
            return None
        z1, z2 = p1.z(), p2.z()
        if z1 is None or z2 is None:
            return None  # Need Z values

        # --- FIX: Replace compare for QgsPoint ---
        epsilon = 1e-6
        # Check if points are effectively the same
        if (
            abs(p1.x() - p2.x()) < epsilon
            and abs(p1.y() - p2.y()) < epsilon
            and abs(z1 - z2) < epsilon
        ):
            # If the single point is below, return it twice, otherwise None
            return (p1, p1) if z1 <= clip_elevation + epsilon else None
        # --- END FIX ---

        # Case 1: Both points are at or below the clipping plane
        if z1 <= clip_elevation + epsilon and z2 <= clip_elevation + epsilon:
            return p1, p2

        # Case 2: Both points are above the clipping plane
        if z1 > clip_elevation + epsilon and z2 > clip_elevation + epsilon:
            return None

        # Case 3: One point above, one point below/at -> Calculate intersection
        # Ensure p1 is the point below/at the plane
        if z1 > clip_elevation:
            p1, p2 = p2, p1  # Swap points
            z1, z2 = p2.z(), p1.z()  # Swap elevations

        # Calculate interpolation factor (t) where elevation equals clip_elevation
        delta_z = z2 - z1
        if (
            abs(delta_z) < epsilon
        ):  # Points are effectively at same Z but one passed check? Should be caught by Case 1/2. Return original below point(s).
            # Should only happen if z1 is approximately clip_elevation
            return p1, p1  # Segment is horizontal at clip_elevation

        t = (clip_elevation - z1) / delta_z
        # Clamp t just in case of floating point issues near 0 or 1
        t = max(0.0, min(t, 1.0))

        # Calculate intersection point coordinates
        x_intersect = p1.x() + t * (p2.x() - p1.x())
        y_intersect = p1.y() + t * (p2.y() - p1.y())
        z_intersect = clip_elevation  # By definition

        p_intersect = QgsPoint(x_intersect, y_intersect, z_intersect)

        # Return the segment from the original lower point (p1) to the intersection point
        return p1, p_intersect

    def _generate_inner_transitional_surface(
        self,
        arc_num,
        rwy_type,
        thr_point,
        azimuth,
        origin_elev,
        ofz_params,
        end_desig,
        runway_name,
    ):
        width = ofz_params.get("width")
        length = ofz_params.get("length")
        slope = ofz_params.get("slope")
        start_dist_from_thr = ofz_params.get("start_dist_from_thr")
        ref = ofz_params.get("ref", "MOS (Verify)")

        QgsMessageLog.logMessage(
            f"Entered _generate_inner_transitional_surface for {runway_name} {end_desig}",
            PLUGIN_TAG,
            Qgis.Info,
        )

        if None in [width, length, slope, start_dist_from_thr]:
            return None

        start_point = thr_point.project(start_dist_from_thr, azimuth)
        azimuth_perp_l = (azimuth - 90) % 360
        azimuth_perp_r = (azimuth + 90) % 360

        half_width = width / 2.0
        app_left = start_point.project(half_width, azimuth_perp_l)
        app_right = start_point.project(half_width, azimuth_perp_r)
        surf_left = app_left.project(length, azimuth_perp_l)
        surf_right = app_right.project(length, azimuth_perp_r)

        poly_points = [app_left, app_right, surf_right, surf_left, app_left]
        poly_geom = QgsGeometry.fromPolygonXY([poly_points])
        fields = self._get_ols_fields("InnerTransitional")
        feat = QgsFeature(fields)
        feat.setGeometry(poly_geom)
        height_agl = length * slope
        attr_map = {
            "rwy_name": runway_name,
            "surface": "Inner Transitional",
            "end_desig": end_desig,
            "elev_m": origin_elev + height_agl if origin_elev is not None else None,
            "height_agl": height_agl,
            "slope_perc": slope * 100.0,
            "ref_mos": ref,
            "len_m": length,
            "innerw_m": width,
            "outerw_m": width + 2 * length,
            "origin_offset": start_dist_from_thr,
        }
        for name, value in attr_map.items():
            idx = fields.indexFromName(name)
            if idx != -1:
                feat.setAttribute(idx, value)
        return feat

    def _generate_baulked_landing_surface(
        self,
        runway_data: dict,
        rwy_params: dict,
        thr_point: QgsPointXY,
        outward_azimuth: float,
        bls_param_dict: dict,
        end_desig: str,
        IHS_ELEVATION_AMSL: float,  # Changed from Optional to required
    ) -> Optional[Tuple[QgsFeature, QgsGeometry, float, float, QgsPointXY, float]]:
        plugin_tag = PLUGIN_TAG
        runway_name = runway_data.get("short_name", "N/A")
        QgsMessageLog.logMessage(
            f"Debug BLS Helper Entered: End {end_desig}, Params: {bls_param_dict}, IHS: {IHS_ELEVATION_AMSL}",
            plugin_tag,
            Qgis.Info,
        )

        width = bls_param_dict.get("width")
        start_dist_from_thr = bls_param_dict.get("start_dist_from_thr")
        divergence = bls_param_dict.get("divergence")
        slope = bls_param_dict.get("slope")
        ref = bls_param_dict.get("ref", "MOS (Verify)")

        # Consolidate missing param check for clarity
        missing_params_list = []
        if width is None:
            missing_params_list.append("width")
        if start_dist_from_thr is None:
            missing_params_list.append("start_dist_from_thr")
        if divergence is None:
            missing_params_list.append("divergence")
        if slope is None:
            missing_params_list.append("slope")
        if IHS_ELEVATION_AMSL is None:
            missing_params_list.append(
                "IHS_ELEVATION_AMSL"
            )  # Should not be None if type hint is enforced

        if missing_params_list:
            QgsMessageLog.logMessage(
                f"Debug BLS Helper: {end_desig} returning None, missing essential inputs: {', '.join(missing_params_list)}",
                plugin_tag,
                Qgis.Warning,
            )
            return None

        inner_edge_center_pt = thr_point.project(start_dist_from_thr, outward_azimuth)
        if not inner_edge_center_pt:
            QgsMessageLog.logMessage(
                f"Debug BLS Helper: {end_desig} returning None, failed inner_edge_center_pt calc.",
                plugin_tag,
                Qgis.Warning,
            )
            return None

        required_rwy_keys = ["thr_point", "rec_thr_point", "thr_elev_1", "thr_elev_2"]
        if not all(
            key in runway_data and runway_data[key] is not None
            for key in required_rwy_keys
        ):
            QgsMessageLog.logMessage(
                f"Debug BLS Helper: {end_desig} returning None, runway_data missing keys for elevation calc: { {k: runway_data.get(k) for k in required_rwy_keys} }",
                plugin_tag,
                Qgis.Warning,
            )
            return None

        inner_edge_elev_amsl = self._get_elevation_at_point_along_gradient(
            inner_edge_center_pt,
            runway_data.get("thr_point"),
            runway_data.get("rec_thr_point"),
            runway_data.get("thr_elev_1"),
            runway_data.get("thr_elev_2"),
            QgsProject.instance().crs(),
        )
        QgsMessageLog.logMessage(
            f"Debug BLS Helper: {end_desig} inner_edge_elev_amsl: {inner_edge_elev_amsl}",
            plugin_tag,
            Qgis.Info,
        )
        if inner_edge_elev_amsl is None:
            QgsMessageLog.logMessage(
                f"Debug BLS Helper: {end_desig} returning None, inner_edge_elev_amsl is None.",
                plugin_tag,
                Qgis.Warning,
            )
            return None

        height_to_gain = IHS_ELEVATION_AMSL - inner_edge_elev_amsl
        calculated_length: float
        QgsMessageLog.logMessage(
            f"Debug BLS Helper: {end_desig} height_to_gain: {height_to_gain}, slope: {slope}",
            plugin_tag,
            Qgis.Info,
        )
        if height_to_gain <= 0:
            calculated_length = 0.0
            QgsMessageLog.logMessage(
                f"Debug BLS Helper: {end_desig} starts at/above IHS. Length is 0.",
                plugin_tag,
                Qgis.Info,
            )
        elif slope <= 1e-9:  # Using a small epsilon for float comparison
            QgsMessageLog.logMessage(
                f"Debug BLS Helper: {end_desig} returning None, slope is effectively zero ({slope}) and BLS starts below IHS.",
                plugin_tag,
                Qgis.Warning,
            )
            return None
        else:
            calculated_length = height_to_gain / slope
        QgsMessageLog.logMessage(
            f"Debug BLS Helper: {end_desig} calculated_length: {calculated_length}",
            plugin_tag,
            Qgis.Info,
        )

        if (
            calculated_length < -1e-9
        ):  # Allow for very small negative due to float precision if height_to_gain is near zero
            QgsMessageLog.logMessage(
                f"Debug BLS Helper: {end_desig} returning None, invalid (negative) calculated_length: {calculated_length}.",
                plugin_tag,
                Qgis.Warning,
            )
            return None

        # If calculated_length is 0 (starts at/above IHS), still create a degenerate feature or handle as per requirements.
        # For now, let's assume a zero-length surface is acceptable if it starts at/above IHS.

        half_width_inner = width / 2.0
        # If calculated_length is 0, final_width will be equal to width.
        final_width = width + (2 * calculated_length * divergence)
        half_width_outer = final_width / 2.0

        bls_geom = self._create_trapezoid(
            inner_edge_center_pt,
            outward_azimuth,
            calculated_length,
            half_width_inner,
            half_width_outer,
            f"Baulked Landing {end_desig}",
        )
        # The _create_trapezoid helper should handle zero length appropriately (e.g., return None or a line/point)
        # We need to check its output.
        QgsMessageLog.logMessage(
            f"Debug BLS Helper: {end_desig} bls_geom created. Is valid: {bls_geom is not None and not bls_geom.isEmpty() and bls_geom.isGeosValid()}",
            plugin_tag,
            Qgis.Info,
        )

        if not bls_geom or bls_geom.isEmpty() or not bls_geom.isGeosValid():
            # If calculated_length was 0, _create_trapezoid might return None or an empty/invalid geometry.
            # Decide if this is an error or if a degenerate (e.g., line) feature should be made.
            # For now, if it's not a valid polygon, we return None.
            if calculated_length <= 1e-9:  # If length was effectively zero
                QgsMessageLog.logMessage(
                    f"Debug BLS Helper: {end_desig} has zero length. No polygon geometry created by _create_trapezoid. Returning None.",
                    plugin_tag,
                    Qgis.Info,
                )
            else:
                QgsMessageLog.logMessage(
                    f"Debug BLS Helper: {end_desig} returning None, invalid bls_geom from _create_trapezoid.",
                    plugin_tag,
                    Qgis.Warning,
                )
            return None

        # --- Feature Creation ---
        fields = self._get_ols_fields("BaulkedLanding")
        feature = QgsFeature(fields)
        feature.setGeometry(bls_geom)

        height_agl_val = calculated_length * slope
        elev_m_val = IHS_ELEVATION_AMSL  # Outer edge is at IHS

        attr_map = {
            "rwy_name": runway_name,
            "surface": "Baulked Landing",
            "end_desig": end_desig,
            "elev_m": elev_m_val,
            "height_agl": height_agl_val,
            "slope_perc": slope * 100.0,
            "ref_mos": ref,
            "len_m": calculated_length,
            "innerw_m": width,
            "outerw_m": final_width,
            "divergence_perc": divergence * 100.0,
            "origin_offset": start_dist_from_thr,
        }
        for name, value in attr_map.items():
            idx = fields.indexFromName(name)
            if idx != -1:
                feature.setAttribute(idx, value)

        QgsMessageLog.logMessage(
            f"Debug BLS Helper: {end_desig} successfully created feature.",
            plugin_tag,
            Qgis.Info,
        )

        # --- THE CRUCIAL RETURN STATEMENT ---
        return (
            feature,
            bls_geom,
            calculated_length,
            inner_edge_elev_amsl,
            inner_edge_center_pt,
            final_width,
        )

    def _generate_its_panel_feature(
        self,
        base_p1_3d: QgsPoint,
        base_p2_3d: QgsPoint,
        its_slope: float,
        IHS_ELEVATION_AMSL: float,
        outward_projection_azimuth: float,
        runway_name: str,
        end_desig: str,
        side_label: str,
        panel_description: str,
        ref_mos: str,
        ols_fields: QgsFields,
    ) -> Optional[QgsFeature]:
        plugin_tag = PLUGIN_TAG

        # --- CORRECTED Z CHECK ---
        z1_base_val = base_p1_3d.z()
        z2_base_val = base_p2_3d.z()

        # Check if Z values are None or not finite (e.g., NaN, Inf)
        # math.isfinite() is good for this.
        if not (
            isinstance(z1_base_val, (int, float))
            and math.isfinite(z1_base_val)
            and isinstance(z2_base_val, (int, float))
            and math.isfinite(z2_base_val)
        ):
            QgsMessageLog.logMessage(
                f"ITS Panel Gen Error for {panel_description} {end_desig} {side_label}: Base points have invalid or missing Z values (P1_Z: {z1_base_val}, P2_Z: {z2_base_val}).",
                plugin_tag,
                Qgis.Warning,
            )
            return None
        # --- END CORRECTED Z CHECK ---

        p1_base_xy = QgsPointXY(base_p1_3d.x(), base_p1_3d.y())
        p2_base_xy = QgsPointXY(base_p2_3d.x(), base_p2_3d.y())
        # z1_base and z2_base are now confirmed to be valid floats
        z1_base = z1_base_val
        z2_base = z2_base_val

        if (
            z1_base >= IHS_ELEVATION_AMSL - 1e-6
            and z2_base >= IHS_ELEVATION_AMSL - 1e-6
        ):
            return None

        if its_slope <= 1e-9:
            QgsMessageLog.logMessage(
                f"ITS Panel Gen Error for {panel_description} {end_desig} {side_label}: ITS slope is zero or negative.",
                plugin_tag,
                Qgis.Warning,
            )
            return None

        h_dist1 = (
            (IHS_ELEVATION_AMSL - z1_base) / its_slope
            if z1_base < IHS_ELEVATION_AMSL
            else 0.0
        )
        h_dist2 = (
            (IHS_ELEVATION_AMSL - z2_base) / its_slope
            if z2_base < IHS_ELEVATION_AMSL
            else 0.0
        )
        h_dist1 = max(0.0, h_dist1)
        h_dist2 = max(0.0, h_dist2)

        p1_top_xy = p1_base_xy.project(h_dist1, outward_projection_azimuth)
        p2_top_xy = p2_base_xy.project(h_dist2, outward_projection_azimuth)

        if not p1_top_xy or not p2_top_xy:
            QgsMessageLog.logMessage(
                f"ITS Panel Gen Error for {panel_description} {end_desig} {side_label}: Failed to project top points.",
                plugin_tag,
                Qgis.Warning,
            )
            return None

        if p1_base_xy.compare(p2_base_xy, epsilon=1e-3):
            if h_dist1 <= 1e-3 and h_dist2 <= 1e-3:
                return None

        if h_dist1 < 1e-3 and h_dist2 < 1e-3 and p1_base_xy.distance(p2_base_xy) < 1e-3:
            return None

        panel_corners_xy = [p1_base_xy, p2_base_xy, p2_top_xy, p1_top_xy]
        panel_geom = self._create_polygon_from_corners(
            panel_corners_xy, f"ITS Panel {panel_description} {end_desig} {side_label}"
        )

        if not panel_geom or panel_geom.isEmpty() or not panel_geom.isGeosValid():
            return None

        feature = QgsFeature(ols_fields)
        feature.setGeometry(panel_geom)
        avg_base_elev = (z1_base + z2_base) / 2.0
        height_gain_panel = (
            IHS_ELEVATION_AMSL - avg_base_elev
            if avg_base_elev < IHS_ELEVATION_AMSL
            else 0.0
        )

        attr_map = {
            "rwy_name": runway_name,
            "surface": "Inner Transitional",
            "end_desig": end_desig,
            "section_desc": panel_description,
            "elev_m": IHS_ELEVATION_AMSL,
            "height_agl": height_gain_panel,
            "slope_perc": its_slope * 100.0,
            "ref_mos": ref_mos,
            "side": side_label,
        }
        final_attr_map = {
            k: v for k, v in attr_map.items() if ols_fields.indexFromName(k) != -1
        }
        for name, value in final_attr_map.items():
            feature.setAttribute(ols_fields.indexFromName(name), value)

        return feature

    def _generate_parallel_contours_in_panel(
        self,
        top_start: QgsPointXY,
        top_end: QgsPointXY,
        IHS_ELEVATION_AMSL: float,
        base_start: QgsPointXY,
        base_end: QgsPointXY,
        z_start: float,
        z_end: float,
        transitional_slope: float,
        contour_fields: QgsFields,
        contour_interval: float,
        panel_geom: QgsGeometry,
        section_desc: str,
        side_label: str,
        runway_name: str,
        end_desig: str,
        transitional_ref: str,
    ) -> list:
        """
        For an approach-adjacent panel, generate contour lines at regular intervals parallel to the top edge,
        clipped to the panel polygon. Dynamically detects the 'downhill' direction.
        """
        contours = []
        min_panel_elev = min(z_start, z_end)
        max_panel_elev = IHS_ELEVATION_AMSL

        # Top edge direction vector (from top_start to top_end)
        dx = top_end.x() - top_start.x()
        dy = top_end.y() - top_start.y()
        top_len = (dx**2 + dy**2) ** 0.5
        if top_len == 0:
            return []  # Avoid division by zero
        ux, uy = dx / top_len, dy / top_len

        # Two possible normals: one points 'down', the other 'up'
        normals = [(-uy, ux), (uy, -ux)]
        extra = 2 * top_len

        # Figure out which normal points inside the polygon by testing the first contour
        first_contour_elev = max(
            contour_interval,
            contour_interval * (int(min_panel_elev // contour_interval) + 1),
        )
        direction_found = False
        for nx, ny in normals:
            delta_z = max_panel_elev - first_contour_elev
            offset = delta_z / transitional_slope
            long_pt1 = QgsPointXY(
                top_start.x() + nx * offset - ux * extra,
                top_start.y() + ny * offset - uy * extra,
            )
            long_pt2 = QgsPointXY(
                top_end.x() + nx * offset + ux * extra,
                top_end.y() + ny * offset + uy * extra,
            )
            test_geom = QgsGeometry.fromPolylineXY([long_pt1, long_pt2])
            clipped = test_geom.intersection(panel_geom)
            if not clipped.isEmpty():
                # This normal points into the panel
                direction_found = True
                break
        if not direction_found:
            # If neither normal yields a valid contour, return nothing
            return contours

        # Now generate all contours in the selected direction
        current_z = first_contour_elev
        while current_z < max_panel_elev - 1e-6:
            delta_z = max_panel_elev - current_z
            offset = delta_z / transitional_slope
            pt1 = QgsPointXY(
                top_start.x() + nx * offset - ux * extra,
                top_start.y() + ny * offset - uy * extra,
            )
            pt2 = QgsPointXY(
                top_end.x() + nx * offset + ux * extra,
                top_end.y() + ny * offset + uy * extra,
            )
            line_geom = QgsGeometry.fromPolylineXY([pt1, pt2])
            clipped = line_geom.intersection(panel_geom)
            if clipped.isEmpty():
                current_z += contour_interval
                continue

            # Handle multipart or single part
            geoms = []
            if clipped.isMultipart():
                geoms = [
                    QgsGeometry.fromPolylineXY(line)
                    for line in clipped.asMultiPolyline()
                ]
            elif clipped.type() == QgsWkbTypes.LineGeometry:
                geoms = [clipped]
            else:
                current_z += contour_interval
                continue

            for g in geoms:
                if g.length() < 1e-3:
                    continue
                feat = QgsFeature(contour_fields)
                feat.setGeometry(g)
                attr_map = {
                    "rwy_name": runway_name,
                    "surface": "Transitional",
                    "section_desc": section_desc,
                    "side": side_label,
                    "end_desig": end_desig,
                    "contour_elev_am": current_z,
                    "ref_mos": transitional_ref,
                }
                for name, value in attr_map.items():
                    idx = contour_fields.indexFromName(name)
                    if idx != -1:
                        feat.setAttribute(idx, value)
                contours.append(feat)

            current_z += contour_interval

        return contours

    def _generate_transitional_features(
        self,
        processed_runway_data_list: List[dict],
        IHS_ELEVATION_AMSL: float,
        target_crs: QgsCoordinateReferenceSystem,
    ) -> Tuple[List[QgsFeature], List[QgsFeature]]:
        """
        Generates polygon features for main Transitional OLS and contour line features.
        Returns (polygon_features, contour_features)
        """
        plugin_tag = PLUGIN_TAG
        QgsMessageLog.logMessage(
            "Starting Transitional Surface feature generation...",
            plugin_tag,
            level=Qgis.Info,
        )

        transitional_features: List[QgsFeature] = []
        transitional_contour_features: List[QgsFeature] = []
        transitional_fields = self._get_ols_fields("Transitional")
        contour_fields = self._get_transitional_contour_fields()
        contour_interval = TRANSITIONAL_CONTOUR_INTERVAL

        if IHS_ELEVATION_AMSL is None:
            QgsMessageLog.logMessage(
                "Skipping Transitional features: IHS Elevation is missing.",
                plugin_tag,
                level=Qgis.Warning,
            )
            return [], []

        approach_edges_cache = {}

        # --- Pass 1: Pre-calculate Approach Section Edge Geometries for Lookups ---
        for runway_data in processed_runway_data_list:
            runway_name = runway_data.get("short_name")
            thr_point = runway_data.get("thr_point")
            rec_thr_point = runway_data.get("rec_thr_point")
            arc_num_str = runway_data.get("arc_num")
            type1_str = runway_data.get("type1")
            type2_str = runway_data.get("type2")
            if not all([runway_name, thr_point, rec_thr_point, arc_num_str]):
                continue
            try:
                arc_num = int(arc_num_str)
            except ValueError:
                continue
            rwy_params = self._get_runway_parameters(thr_point, rec_thr_point)
            if not rwy_params:
                continue
            primary_desig, reciprocal_desig = (
                runway_name.split("/") if "/" in runway_name else ("THR1", "THR2")
            )
            for end_idx, (end_desig, end_type, end_thr_pt, outward_az) in enumerate(
                [
                    (primary_desig, type1_str, thr_point, rwy_params["azimuth_r_p"]),
                    (
                        reciprocal_desig,
                        type2_str,
                        rec_thr_point,
                        rwy_params["azimuth_p_r"],
                    ),
                ]
            ):
                approach_sections_params = ols_dimensions.get_ols_params(
                    arc_num, end_type, "APPROACH"
                )
                if not approach_sections_params:
                    continue
                current_section_start_pt = None
                current_section_start_width = 0.0
                for i, section_params in enumerate(approach_sections_params):
                    length = section_params.get("length", 0.0)
                    divergence = section_params.get("divergence", 0.0)
                    if length <= 0:
                        continue
                    if i == 0:
                        start_dist = section_params.get("start_dist_from_thr", 0.0)
                        start_width = section_params.get("start_width", 0.0)
                        if start_width <= 0:
                            break
                        current_section_start_pt = end_thr_pt.project(
                            start_dist, outward_az
                        )
                        current_section_start_width = start_width
                    else:
                        if current_section_start_pt is None:
                            break
                    if not current_section_start_pt:
                        break
                    start_hw = current_section_start_width / 2.0
                    end_width = current_section_start_width + (2 * length * divergence)
                    end_hw = end_width / 2.0
                    end_pt = current_section_start_pt.project(length, outward_az)
                    if not end_pt:
                        break
                    az_perp_l = (outward_az + 270.0) % 360.0
                    az_perp_r = (outward_az + 90.0) % 360.0
                    p_start_l = current_section_start_pt.project(start_hw, az_perp_l)
                    p_start_r = current_section_start_pt.project(start_hw, az_perp_r)
                    p_end_l = end_pt.project(end_hw, az_perp_l)
                    p_end_r = end_pt.project(end_hw, az_perp_r)
                    if all([p_start_l, p_end_l, p_start_r, p_end_r]):
                        edge_l = QgsLineString([p_start_l, p_end_l])
                        edge_r = QgsLineString([p_start_r, p_end_r])
                        approach_edges_cache[(runway_name, end_desig, i, "L")] = edge_l
                        approach_edges_cache[(runway_name, end_desig, i, "R")] = edge_r
                    current_section_start_pt = end_pt
                    current_section_start_width = end_width

        # --- Pass 2: Generate Transitional Features ---

        for runway_data in processed_runway_data_list:
            runway_name = runway_data.get("short_name")
            thr_point = runway_data.get("thr_point")
            rec_thr_point = runway_data.get("rec_thr_point")
            thr_elev = runway_data.get("thr_elev_1")
            rec_thr_elev = runway_data.get("thr_elev_2")
            arc_num_str = runway_data.get("arc_num")
            type1_str = runway_data.get("type1")
            type2_str = runway_data.get("type2")
            calculated_strip_dims = runway_data.get("calculated_strip_dims")

            if not all(
                [
                    runway_name,
                    thr_point,
                    rec_thr_point,
                    arc_num_str,
                    calculated_strip_dims,
                    thr_elev is not None,
                    rec_thr_elev is not None,
                ]
            ):
                QgsMessageLog.logMessage(
                    f"Skipping Transitional features for {runway_name}: Missing required data.",
                    plugin_tag,
                    level=Qgis.Warning,
                )
                continue
            try:
                arc_num = int(arc_num_str)
            except ValueError:
                QgsMessageLog.logMessage(
                    f"Skipping Transitional features for {runway_name}: Invalid ARC.",
                    plugin_tag,
                    level=Qgis.Warning,
                )
                continue
            rwy_params = self._get_runway_parameters(thr_point, rec_thr_point)
            if not rwy_params or rwy_params["length"] < 1e-6:
                QgsMessageLog.logMessage(
                    f"Skipping Transitional features for {runway_name}: Invalid runway params.",
                    plugin_tag,
                    level=Qgis.Warning,
                )
                continue
            primary_desig, reciprocal_desig = (
                runway_name.split("/") if "/" in runway_name else ("THR1", "THR2")
            )

            # --- Get Transitional Slope ---
            type_abbr_1 = ols_dimensions.get_runway_type_abbr(type1_str)
            type_abbr_2 = ols_dimensions.get_runway_type_abbr(type2_str)
            type_order_abbr = ["", "NI", "NPA", "PA_I", "PA_II_III"]
            type_order_full = [
                "",
                "Non-Instrument (NI)",
                "Non-Precision Approach (NPA)",
                "Precision Approach CAT I",
                "Precision Approach CAT II/III",
            ]
            try:
                idx1 = type_order_abbr.index(type_abbr_1)
            except ValueError:
                idx1 = 1
            try:
                idx2 = type_order_abbr.index(type_abbr_2)
            except ValueError:
                idx2 = 1
            governing_type_index = max(idx1, idx2)
            if governing_type_index < len(type_order_full):
                governing_type_str_full = (
                    type_order_full[governing_type_index]
                    if type_order_full[governing_type_index]
                    else "Non-Instrument (NI)"
                )
            else:
                governing_type_str_full = "Non-Instrument (NI)"
            trans_params = ols_dimensions.get_ols_params(
                arc_num, governing_type_str_full, "Transitional"
            )
            if (
                not trans_params
                or "slope" not in trans_params
                or trans_params["slope"] <= 1e-9
            ):
                QgsMessageLog.logMessage(
                    f"Skipping Transitional features for {runway_name}: No valid slope found for classification ('{governing_type_str_full}').",
                    plugin_tag,
                    level=Qgis.Warning,
                )
                continue
            transitional_slope = trans_params["slope"]
            transitional_ref = trans_params.get("ref", "MOS 8.2.17 (Verify)")

            # --- Strip-Adjacent Sides (original rectangular logic) ---
            strip_overall_width = calculated_strip_dims.get("overall_width")
            strip_extension = calculated_strip_dims.get("extension_length")
            if strip_overall_width is None or strip_extension is None:
                QgsMessageLog.logMessage(
                    f"Skipping Transitional features for {runway_name}: Missing calc strip dims.",
                    plugin_tag,
                    level=Qgis.Warning,
                )
                continue
            strip_overall_half_width = strip_overall_width / 2.0
            strip_end_p = thr_point.project(strip_extension, rwy_params["azimuth_r_p"])
            strip_end_r = rec_thr_point.project(
                strip_extension, rwy_params["azimuth_p_r"]
            )
            if not strip_end_p or not strip_end_r:
                QgsMessageLog.logMessage(
                    f"Skipping Transitional features for {runway_name}: Failed strip end points.",
                    plugin_tag,
                    level=Qgis.Warning,
                )
                continue
            strip_corner_p_l = strip_end_p.project(
                strip_overall_half_width, rwy_params["azimuth_perp_l"]
            )
            strip_corner_p_r = strip_end_p.project(
                strip_overall_half_width, rwy_params["azimuth_perp_r"]
            )
            strip_corner_r_l = strip_end_r.project(
                strip_overall_half_width, rwy_params["azimuth_perp_l"]
            )
            strip_corner_r_r = strip_end_r.project(
                strip_overall_half_width, rwy_params["azimuth_perp_r"]
            )
            if not all(
                [strip_corner_p_l, strip_corner_p_r, strip_corner_r_l, strip_corner_r_r]
            ):
                QgsMessageLog.logMessage(
                    f"Skipping Transitional features for {runway_name}: Failed strip corners.",
                    plugin_tag,
                    level=Qgis.Warning,
                )
                continue
            strip_edge_l = QgsLineString([strip_corner_p_l, strip_corner_r_l])
            strip_edge_r = QgsLineString([strip_corner_p_r, strip_corner_r_r])

            # --- Generate Strip Transitional Sides (rectangular) ---
            for side_label, strip_edge, outward_azimuth in [
                ("L", strip_edge_l, rwy_params["azimuth_perp_l"]),
                ("R", strip_edge_r, rwy_params["azimuth_perp_r"]),
            ]:
                if not strip_edge or strip_edge.isEmpty():
                    continue
                p_start_qgsp = strip_edge.startPoint()
                p_end_qgsp = strip_edge.endPoint()
                p_start_xy = QgsPointXY(p_start_qgsp.x(), p_start_qgsp.y())
                p_end_xy = QgsPointXY(p_end_qgsp.x(), p_end_qgsp.y())
                z_start = self._get_elevation_at_point_along_gradient(
                    p_start_xy,
                    thr_point,
                    rec_thr_point,
                    thr_elev,
                    rec_thr_elev,
                    target_crs,
                )
                z_end = self._get_elevation_at_point_along_gradient(
                    p_end_xy,
                    thr_point,
                    rec_thr_point,
                    thr_elev,
                    rec_thr_elev,
                    target_crs,
                )
                if z_start is None or z_end is None:
                    continue
                if z_start >= IHS_ELEVATION_AMSL and z_end >= IHS_ELEVATION_AMSL:
                    continue
                h_dist_start = max(
                    0.0, (IHS_ELEVATION_AMSL - z_start) / transitional_slope
                )
                h_dist_end = max(0.0, (IHS_ELEVATION_AMSL - z_end) / transitional_slope)
                p_upper_start = p_start_xy.project(h_dist_start, outward_azimuth)
                p_upper_end = p_end_xy.project(h_dist_end, outward_azimuth)
                if not p_upper_start or not p_upper_end:
                    continue
                corners = [p_start_xy, p_end_xy, p_upper_end, p_upper_start]
                poly_geom = self._create_polygon_from_corners(
                    corners, f"Trans Strip {side_label} {runway_name}"
                )
                if poly_geom:
                    feat = QgsFeature(transitional_fields)
                    feat.setGeometry(poly_geom)
                    attr_map = {
                        "rwy_name": runway_name,
                        "surface": "Transitional",
                        "section_desc": "Transitional Strip Adjacent Surface",
                        "elev_m": IHS_ELEVATION_AMSL,
                        "height_agl": IHS_ELEVATION_AMSL - min(z_start, z_end),
                        "side": side_label,
                        "slope_perc": transitional_slope * 100.0,
                        "ref_mos": transitional_ref,
                    }
                    for name, value in attr_map.items():
                        idx = transitional_fields.indexFromName(name)
                        if idx != -1:
                            feat.setAttribute(idx, value)
                    transitional_features.append(feat)

                    # ---- Generate contours for this strip-adjacent section ----
                    strip_contours = self._generate_transitional_strip_contours(
                        base_start=p_start_xy,
                        base_end=p_end_xy,
                        top_start=p_upper_start,
                        top_end=p_upper_end,
                        z_start=z_start,
                        z_end=z_end,
                        IHS_ELEVATION_AMSL=IHS_ELEVATION_AMSL,
                        contour_fields=contour_fields,
                        contour_interval=contour_interval,
                        section_desc="Transitional Strip Adjacent Surface",
                        side_label=side_label,
                        runway_name=runway_name,
                        transitional_ref=transitional_ref,
                        bounding_polygon=poly_geom,
                    )
                    transitional_contour_features.extend(strip_contours)

            # --- Approach-Adjacent Transitional Surfaces (this section is updated) ---
            for end_idx, (
                end_desig,
                end_type,
                end_thr_pt,
                end_thr_elev,
                outward_az,
            ) in enumerate(
                [
                    (
                        primary_desig,
                        type1_str,
                        thr_point,
                        thr_elev,
                        rwy_params["azimuth_r_p"],
                    ),
                    (
                        reciprocal_desig,
                        type2_str,
                        rec_thr_point,
                        rec_thr_elev,
                        rwy_params["azimuth_p_r"],
                    ),
                ]
            ):
                approach_sections_params = ols_dimensions.get_ols_params(
                    arc_num, end_type, "APPROACH"
                )
                if not approach_sections_params:
                    continue

                current_section_start_elev = end_thr_elev
                current_section_start_pt_ctr = None
                prev_section_length = 0.0

                for i, section_params in enumerate(approach_sections_params):
                    section_length = section_params.get("length", 0.0)
                    section_slope = section_params.get("slope", 0.0)
                    section_params.get("divergence", 0.0)
                    if section_length <= 0:
                        continue
                    if i == 0:
                        start_dist = section_params.get("start_dist_from_thr", 0.0)
                        current_section_start_pt_ctr = end_thr_pt.project(
                            start_dist, outward_az
                        )
                    else:
                        if current_section_start_pt_ctr:
                            current_section_start_pt_ctr = (
                                current_section_start_pt_ctr.project(
                                    prev_section_length, outward_az
                                )
                            )
                        else:
                            break
                    if not current_section_start_pt_ctr:
                        break
                    section_end_elev = (
                        (current_section_start_elev + section_length * section_slope)
                        if current_section_start_elev is not None
                        else None
                    )
                    if section_end_elev is None:
                        continue
                    for side_label, outward_perp_azimuth in [
                        ("L", (outward_az + 270.0) % 360.0),
                        ("R", (outward_az + 90.0) % 360.0),
                    ]:
                        approach_edge = approach_edges_cache.get(
                            (runway_name, end_desig, i, side_label)
                        )
                        if not approach_edge or approach_edge.isEmpty():
                            continue
                        pa_start = approach_edge.startPoint()
                        pa_end = approach_edge.endPoint()
                        za_start = current_section_start_elev
                        za_end = section_end_elev

                        # --- Clip approach side at IHS elevation ---
                        pa_start_clipped = pa_start
                        pa_end_clipped = pa_end
                        za_start_clipped = za_start
                        za_end_clipped = za_end

                        if (
                            za_start < IHS_ELEVATION_AMSL
                            and za_end > IHS_ELEVATION_AMSL
                        ):
                            # Crossing from below to above IHS: interpolate where it meets
                            frac = (IHS_ELEVATION_AMSL - za_start) / (za_end - za_start)
                            pa_end_clipped = QgsPoint(
                                pa_start.x() + frac * (pa_end.x() - pa_start.x()),
                                pa_start.y() + frac * (pa_end.y() - pa_start.y()),
                                IHS_ELEVATION_AMSL,
                            )
                            za_end_clipped = IHS_ELEVATION_AMSL
                        elif (
                            za_end < IHS_ELEVATION_AMSL
                            and za_start > IHS_ELEVATION_AMSL
                        ):
                            frac = (IHS_ELEVATION_AMSL - za_end) / (za_start - za_end)
                            pa_start_clipped = QgsPoint(
                                pa_end.x() + frac * (pa_start.x() - pa_end.x()),
                                pa_end.y() + frac * (pa_start.y() - pa_end.y()),
                                IHS_ELEVATION_AMSL,
                            )
                            za_start_clipped = IHS_ELEVATION_AMSL
                        elif (
                            za_start >= IHS_ELEVATION_AMSL
                            and za_end >= IHS_ELEVATION_AMSL
                        ):
                            continue

                        # --- Generate panel corners ---
                        points_base = [
                            QgsPointXY(pa_start_clipped.x(), pa_start_clipped.y()),
                            QgsPointXY(pa_end_clipped.x(), pa_end_clipped.y()),
                        ]
                        elevations_base = [za_start_clipped, za_end_clipped]
                        points_top = []
                        for base_pt, base_elev in zip(points_base, elevations_base):
                            h_dist = max(
                                0.0,
                                (IHS_ELEVATION_AMSL - base_elev) / transitional_slope,
                            )
                            top_pt = base_pt.project(h_dist, outward_perp_azimuth)
                            points_top.append(top_pt)

                        corners = [
                            points_base[0],
                            points_base[1],
                            points_top[1],
                            points_top[0],
                        ]
                        poly_geom = self._create_polygon_from_corners(
                            corners,
                            f"Trans App {end_desig} Sec{i+1} {side_label}",
                        )
                        if poly_geom:
                            feat = QgsFeature(transitional_fields)
                            feat.setGeometry(poly_geom)
                            attr_map = {
                                "rwy_name": runway_name,
                                "surface": "Transitional",
                                "end_desig": end_desig,
                                "section_desc": f"Transitional {end_desig} Approach Adjacent Surface",
                                "elev_m": IHS_ELEVATION_AMSL,
                                "height_agl": IHS_ELEVATION_AMSL
                                - min(za_start_clipped, za_end_clipped),
                                "side": side_label,
                                "slope_perc": transitional_slope * 100.0,
                                "ref_mos": transitional_ref,
                            }
                            for name, value in attr_map.items():
                                idx = transitional_fields.indexFromName(name)
                                if idx != -1:
                                    feat.setAttribute(idx, value)
                            transitional_features.append(feat)

                            # --- Use points_top explicitly here ---
                            top_start = points_top[0]
                            top_end = points_top[1]
                            approach_contours = self._generate_parallel_contours_in_panel(
                                top_start=top_start,
                                top_end=top_end,
                                IHS_ELEVATION_AMSL=IHS_ELEVATION_AMSL,
                                base_start=points_base[0],
                                base_end=points_base[1],
                                z_start=za_start_clipped,
                                z_end=za_end_clipped,
                                transitional_slope=transitional_slope,
                                contour_fields=contour_fields,
                                contour_interval=contour_interval,
                                panel_geom=poly_geom,
                                section_desc=f"Transitional {end_desig} Approach Adjacent Surface",
                                side_label=side_label,
                                runway_name=runway_name,
                                end_desig=end_desig,
                                transitional_ref=transitional_ref,
                            )
                            transitional_contour_features.extend(approach_contours)

                    current_section_start_elev = section_end_elev
                    prev_section_length = section_length

        QgsMessageLog.logMessage(
            f"Finished Transitional Surface feature generation. Created {len(transitional_features)} polygons, {len(transitional_contour_features)} contours.",
            plugin_tag,
            level=Qgis.Info,
        )
        return transitional_features, transitional_contour_features

    # --- Guideline Processing Functions (Using Helper) ---
    def process_met_station_surfaces(
        self,
        met_point_proj_crs: QgsPointXY,
        icao_code: str,
        target_crs: QgsCoordinateReferenceSystem,
        layer_group: QgsLayerTreeGroup,
    ) -> Tuple[bool, List[QgsVectorLayer]]:
        """Generates MET station layers (Point, Enclosure, Buffers). Uses helper."""
        # Note: Return value changed slightly, second element not directly used now
        any_layer_ok = False
        enclosure_geom: Optional[QgsGeometry] = None
        met_geom_target_crs = QgsGeometry.fromPointXY(met_point_proj_crs)
        if met_geom_target_crs.isNull():
            return False, []

        # Layer 1: Point
        try:
            # Build a QgsFields object, not a list
            fields = QgsFields()
            fields.append(QgsField("desc", QVariant.String))
            fields.append(QgsField("coord_east", QVariant.Double))
            fields.append(QgsField("coord_north", QVariant.Double))
            fields.append(QgsField("elev_m", QVariant.Double))
            fields.append(QgsField("ref_mos", QVariant.String, "MOS Reference", 20))

            feat = QgsFeature(fields)  # Pass QgsFields, not list!
            feat.setGeometry(met_geom_target_crs)
            feat.setAttributes(
                [
                    self.tr("MET Station Location"),
                    met_point_proj_crs.x(),
                    met_point_proj_crs.y(),
                    0.0,  # Elevation not provided, set to 0.0
                    "MOS 19.17",
                ]
            )
            if self._create_and_add_layer(
                "Point",
                f"met_loc_{icao_code}",
                self.tr("MET Station Location"),
                fields,
                [feat],
                layer_group,
                "MET Station Location",
            ):
                any_layer_ok = True
        except Exception as e:
            QgsMessageLog.logMessage(
                f"Error MET Point: {e}", PLUGIN_TAG, level=Qgis.Critical
            )

        # Layer 2: Enclosure
        try:
            side = 16.0
            name = self.tr("MET Instrument Enclosure")
            geom = self._create_centered_oriented_square(met_point_proj_crs, side, name)
            if geom:
                enclosure_geom = geom
                fields = QgsFields(
                    [
                        QgsField("desc", QVariant.String),
                        QgsField("coord_east", QVariant.Double),
                        QgsField("coord_north", QVariant.Double),
                        QgsField("side_m", QVariant.Double),
                        QgsField("ref_mos", QVariant.String, "MOS Reference", 20),
                    ]
                )
                feat = QgsFeature(fields)
                feat.setGeometry(geom)
                feat.setAttributes(
                    [
                        "MET Instrument Enclosure",
                        met_point_proj_crs.x(),
                        met_point_proj_crs.y(),
                        side,
                        "MOS 19.18(2)(a)",
                    ]
                )
            if self._create_and_add_layer(
                "Polygon",
                f"met_enc_{icao_code}",
                name,
                fields,
                [feat],
                layer_group,
                "MET Instrument Enclosure",
            ):
                any_layer_ok = True
        except Exception as e:
            QgsMessageLog.logMessage(
                f"Error MET Enclosure: {e}", PLUGIN_TAG, level=Qgis.Critical
            )

        # Layer 3: Buffer Zone
        try:
            side = 30.0
            name = self.tr("MET Buffer Zone")
            geom = self._create_centered_oriented_square(met_point_proj_crs, side, name)
            if geom:
                fields = QgsFields(
                    [
                        QgsField("desc", QVariant.String),
                        QgsField("coord_east", QVariant.Double),
                        QgsField("coord_north", QVariant.Double),
                        QgsField("side_m", QVariant.Double),
                        QgsField("ref_mos", QVariant.String, "MOS Reference", 20),
                    ]
                )
                feat = QgsFeature(fields)
                feat.setGeometry(geom)
                feat.setAttributes(
                    [
                        "MET Buffer Zone",
                        met_point_proj_crs.x(),
                        met_point_proj_crs.y(),
                        side,
                        "MOS 19.18(2)(a)",
                    ]
                )
            if self._create_and_add_layer(
                "Polygon",
                f"met_buf_{icao_code}",
                name,
                fields,
                [feat],
                layer_group,
                "MET Buffer Zone",
            ):
                any_layer_ok = True
        except Exception as e:
            QgsMessageLog.logMessage(
                f"Error MET Buffer: {e}", PLUGIN_TAG, level=Qgis.Critical
            )

        # Layer 4: Obstruction Buffer
        if enclosure_geom:
            try:
                dist = 80.0
                name = self.tr("MET Obstacle Buffer Zone")
                buffered_geom = enclosure_geom.buffer(dist, 12)
                buffered_geom = (
                    buffered_geom.makeValid()
                    if buffered_geom and not buffered_geom.isGeosValid()
                    else buffered_geom
                )
                if buffered_geom and not buffered_geom.isEmpty():
                    fields = QgsFields(
                        [
                            QgsField("desc", QVariant.String),
                            QgsField("coord_east", QVariant.Double),
                            QgsField("coord_north", QVariant.Double),
                            QgsField("buffer_m", QVariant.Double),
                            QgsField("ref_mos", QVariant.String, "MOS Reference", 20),
                        ]
                    )
                    feat = QgsFeature(fields)
                    feat.setGeometry(buffered_geom)
                    feat.setAttributes(
                        [
                            "MET Obstacle Buffer Zone",
                            met_point_proj_crs.x(),
                            met_point_proj_crs.y(),
                            dist,
                            "MOS 19.18(2)(a)",
                        ]
                    )
                if self._create_and_add_layer(
                    "Polygon",
                    f"met_obs_{icao_code}",
                    name,
                    fields,
                    [feat],
                    layer_group,
                    "MET Obstacle Buffer Zone",
                ):
                    any_layer_ok = True
            except Exception as e:
                QgsMessageLog.logMessage(
                    f"Error MET Obstruction Buffer: {e}",
                    PLUGIN_TAG,
                    level=Qgis.Critical,
                )

        # Return overall success status, generated layers are in self.successfully_generated_layers
        return any_layer_ok, []  # Return empty list as layers added internally

    def _generate_transitional_strip_contours(
        self,
        base_start: QgsPointXY,
        base_end: QgsPointXY,
        top_start: QgsPointXY,
        top_end: QgsPointXY,
        z_start: float,
        z_end: float,
        IHS_ELEVATION_AMSL: float,
        contour_fields: QgsFields,
        contour_interval: float,
        section_desc: str,
        side_label: str,
        runway_name: str,
        transitional_ref: str,
        bounding_polygon=None,
    ) -> List[QgsFeature]:
        """
        Generates contour lines for a rectangular (strip-adjacent) transitional surface section.
        Returns a list of QgsFeature line features.
        """
        contours = []
        min_z = min(z_start, z_end)
        max_z = IHS_ELEVATION_AMSL
        first_contour = math.ceil(min_z / contour_interval) * contour_interval
        current_z = first_contour
        while current_z < max_z:
            # Linear interpolation for contour endpoints along base->top lines
            t_start = (
                (current_z - z_start) / (max_z - z_start) if max_z > z_start else 1.0
            )
            t_end = (current_z - z_end) / (max_z - z_end) if max_z > z_end else 1.0
            pt_left = QgsPointXY(
                base_start.x() + t_start * (top_start.x() - base_start.x()),
                base_start.y() + t_start * (top_start.y() - base_start.y()),
            )
            pt_right = QgsPointXY(
                base_end.x() + t_end * (top_end.x() - base_end.x()),
                base_end.y() + t_end * (top_end.y() - base_end.y()),
            )
            line_geom = QgsGeometry.fromPolylineXY([pt_left, pt_right])

            # --- CLIP to rectangle polygon if provided ---
            if bounding_polygon is not None and line_geom is not None:
                clipped_geom = line_geom.intersection(bounding_polygon)
                if clipped_geom.isEmpty():
                    current_z += contour_interval
                    continue  # Skip if completely outside
                line_geom = clipped_geom  # Use the clipped geometry

            feat = QgsFeature(contour_fields)
            feat.setGeometry(line_geom)
            # Assign attributes (add/remove fields as appropriate)
            attr_map = {
                "rwy_name": runway_name,
                "surface": "Transitional",
                "section_desc": section_desc,
                "contour_elev_am": current_z,
            }
            #     QgsMessageLog.logMessage(
            #     f"Setting contour_elev_am for contour: current_z={current_z} (type={type(current_z)})",
            #     PLUGIN_TAG,
            #     level=Qgis.Info,
            # )
            for name, value in attr_map.items():
                idx = contour_fields.indexFromName(name)
                if idx != -1:
                    feat.setAttribute(idx, value)
            contours.append(feat)
            current_z += contour_interval
        return contours

    def process_guideline_a(
        self, runway_data: dict, layer_group: QgsLayerTreeGroup
    ) -> bool:
        """Placeholder for Guideline A: Aircraft Noise processing."""
        QgsMessageLog.logMessage(
            "Guideline A processing not implemented.", PLUGIN_TAG, level=Qgis.Info
        )
        return False
        # Note: This is a placeholder function, actual implementation is not provided.

    def process_guideline_b(
        self, runway_data: dict, layer_group: QgsLayerTreeGroup
    ) -> bool:
        """Processes Guideline B: Windshear Assessment Zone."""
        runway_name = runway_data.get(
            "short_name", f"RWY_{runway_data.get('original_index','?')}"
        )
        thr_point = runway_data.get("thr_point")
        rec_thr_point = runway_data.get("rec_thr_point")
        if not all([thr_point, rec_thr_point, layer_group]):
            return False
        params = self._get_runway_parameters(thr_point, rec_thr_point)
        if params is None:
            return False

        fields = QgsFields(
            [
                QgsField("rwy_name", QVariant.String),
                QgsField("desc", QVariant.String),
                QgsField("end_desig", QVariant.String),
                QgsField("ref_nasf", QVariant.String),
            ]
        )
        features_to_add = []
        primary_desig, reciprocal_desig = (
            runway_name.split("/") if "/" in runway_name else ("Primary", "Reciprocal")
        )
        try:
            geom_p = self._create_offset_rectangle(
                thr_point,
                params["azimuth_p_r"],
                GUIDELINE_B_FAR_EDGE_OFFSET,
                GUIDELINE_B_ZONE_LENGTH_BACKWARD,
                GUIDELINE_B_ZONE_HALF_WIDTH,
                f"WSZ {primary_desig}",
            )
            if geom_p:
                feat = QgsFeature(fields)
                feat.setGeometry(geom_p)
                feat.setAttributes(
                    [
                        runway_name,
                        "Windshear Assessment Zone",
                        primary_desig,
                        "NASF Guideline B",
                    ]
                )
                features_to_add.append(feat)
        except Exception as e:
            QgsMessageLog.logMessage(
                f"Error WSZ Primary {runway_name}: {e}", PLUGIN_TAG, level=Qgis.Warning
            )
        try:
            geom_r = self._create_offset_rectangle(
                rec_thr_point,
                params["azimuth_r_p"],
                GUIDELINE_B_FAR_EDGE_OFFSET,
                GUIDELINE_B_ZONE_LENGTH_BACKWARD,
                GUIDELINE_B_ZONE_HALF_WIDTH,
                f"WSZ {reciprocal_desig}",
            )
            if geom_r:
                feat = QgsFeature(fields)
                feat.setGeometry(geom_r)
                feat.setAttributes(
                    [
                        runway_name,
                        "Windshear Assessment Zone",
                        primary_desig,
                        "NASF Guideline B",
                    ]
                )
                features_to_add.append(feat)
        except Exception as e:
            QgsMessageLog.logMessage(
                f"Error WSZ Reciprocal {runway_name}: {e}",
                PLUGIN_TAG,
                level=Qgis.Warning,
            )

        layer_created = self._create_and_add_layer(
            "Polygon",
            f"WSZ_{runway_name.replace('/', '_')}",
            f"WSZ {self.tr('RWY')} {runway_name}",
            fields,
            features_to_add,
            layer_group,
            "WSZ Runway",
        )
        return layer_created is not None

    def process_guideline_c(
        self,
        arp_point: QgsPointXY,
        icao_code: str,
        target_crs: QgsCoordinateReferenceSystem,
        layer_group: QgsLayerTreeGroup,
    ) -> bool:
        """Processes Guideline C: Wildlife Management Zone."""
        if not all(
            [arp_point, icao_code, target_crs, target_crs.isValid(), layer_group]
        ):
            return False
        overall_success = False
        try:
            arp_geom = QgsGeometry.fromPointXY(arp_point)
            if arp_geom.isNull():
                return False

            def create_wzm_layer(
                zone: str,
                geom: Optional[QgsGeometry],
                desc: str,
                r_in: float,
                r_out: float,
            ) -> bool:
                if not geom:
                    return False
                display_name = f"{self.tr('WMZ')} {zone} ({r_in:.0f}-{r_out:.0f}km)"
                internal_name = f"WMZ_{zone}_{icao_code}"
                fields = QgsFields(
                    [
                        QgsField("zone", QVariant.String),
                        QgsField("desc", QVariant.String),
                        QgsField("inner_rad_km", QVariant.Double),
                        QgsField("outer_rad_km", QVariant.Double),
                        QgsField("ref_mos", QVariant.String),
                        QgsField("ref_nasf", QVariant.String),
                    ]
                )
                feature = QgsFeature(fields)
                feature.setGeometry(geom)
                feature.setAttributes(
                    [
                        f"Area {zone}",
                        desc,
                        r_in,
                        r_out,
                        "MOS 17.01(2)",
                        "NASF Guideline C",
                    ]
                )
                layer = self._create_and_add_layer(
                    "Polygon",
                    internal_name,
                    display_name,
                    fields,
                    [feature],
                    layer_group,
                    f"WMZ {zone}",
                )
                return layer is not None

            geom_a = arp_geom.buffer(
                GUIDELINE_C_RADIUS_A_M, GUIDELINE_C_BUFFER_SEGMENTS
            )
            geom_a = (
                geom_a.makeValid() if geom_a and not geom_a.isGeosValid() else geom_a
            )
            geom_b_full = arp_geom.buffer(
                GUIDELINE_C_RADIUS_B_M, GUIDELINE_C_BUFFER_SEGMENTS
            )
            geom_b_full = (
                geom_b_full.makeValid()
                if geom_b_full and not geom_b_full.isGeosValid()
                else geom_b_full
            )
            geom_c_full = arp_geom.buffer(
                GUIDELINE_C_RADIUS_C_M, GUIDELINE_C_BUFFER_SEGMENTS
            )
            geom_c_full = (
                geom_c_full.makeValid()
                if geom_c_full and not geom_c_full.isGeosValid()
                else geom_c_full
            )
            geom_b = None
            geom_c = None
            if geom_b_full:
                geom_b = geom_b_full.difference(geom_a) if geom_a else geom_b_full
                geom_b = (
                    geom_b.makeValid()
                    if geom_b and not geom_b.isGeosValid()
                    else geom_b
                )
            if geom_c_full:
                geom_for_diff = geom_b_full if geom_b_full else geom_a
                geom_c = (
                    geom_c_full.difference(geom_for_diff)
                    if geom_for_diff
                    else geom_c_full
                )
                geom_c = (
                    geom_c.makeValid()
                    if geom_c and not geom_c.isGeosValid()
                    else geom_c
                )

            if create_wzm_layer(
                "A",
                geom_a,
                self.tr("Wildlife Management Zone A (0-3km)"),
                0.0,
                GUIDELINE_C_RADIUS_A_M / 1000.0,
            ):
                overall_success = True
            if create_wzm_layer(
                "B",
                geom_b,
                self.tr("Wildlife Management Zone B (3-8km)"),
                GUIDELINE_C_RADIUS_A_M / 1000.0,
                GUIDELINE_C_RADIUS_B_M / 1000.0,
            ):
                overall_success = True
            if create_wzm_layer(
                "C",
                geom_c,
                self.tr("Wildlife Management Zone C (8-13km)"),
                GUIDELINE_C_RADIUS_B_M / 1000.0,
                GUIDELINE_C_RADIUS_C_M / 1000.0,
            ):
                overall_success = True
            return overall_success
        except Exception as e:
            QgsMessageLog.logMessage(
                f"Error Guideline C: {e}", PLUGIN_TAG, level=Qgis.Critical
            )
            return False

    def process_guideline_d(
        self,
        arp_point: QgsPointXY,
        icao_code: str,
        target_crs: QgsCoordinateReferenceSystem,  # For consistency, though buffer uses geom's CRS
        layer_group: QgsLayerTreeGroup,
    ) -> bool:
        """Processes Guideline D: Wind Turbine Assessment Zone."""
        plugin_tag = PLUGIN_TAG
        if not all([arp_point, icao_code, layer_group]):
            QgsMessageLog.logMessage(
                "Guideline D (Wind Turbine) skipped: Missing ARP point, ICAO code, or layer group.",
                plugin_tag,
                level=Qgis.Warning,
            )
            return False

        # Constants are defined at the top of the file
        # GUIDELINE_D_TURBINE_RADIUS_M
        # GUIDELINE_D_BUFFER_SEGMENTS

        try:
            arp_geom = QgsGeometry.fromPointXY(arp_point)
            if arp_geom.isNull():
                QgsMessageLog.logMessage(
                    "Guideline D (Wind Turbine) skipped: ARP geometry is null.",
                    plugin_tag,
                    level=Qgis.Warning,
                )
                return False

            turbine_zone_geom = arp_geom.buffer(
                GUIDELINE_D_TURBINE_RADIUS_M, GUIDELINE_D_BUFFER_SEGMENTS
            )
            if not turbine_zone_geom or turbine_zone_geom.isEmpty():
                QgsMessageLog.logMessage(
                    "Guideline D: Failed to create turbine zone buffer.",
                    plugin_tag,
                    level=Qgis.Warning,
                )
                return False

            valid_geom = turbine_zone_geom.makeValid()
            if not valid_geom or not valid_geom.isGeosValid() or valid_geom.isEmpty():
                QgsMessageLog.logMessage(
                    "Guideline D: Turbine zone geometry invalid after makeValid.",
                    plugin_tag,
                    level=Qgis.Warning,
                )
                return False

            fields = QgsFields(
                [
                    QgsField("icao_code", QVariant.String, self.tr("ICAO Code"), 10),
                    QgsField(
                        "description", QVariant.String, self.tr("Description"), 100
                    ),
                    QgsField(
                        "radius_km", QVariant.Double, self.tr("Radius (km)"), 8, 2
                    ),
                    QgsField(
                        "ref_nasf", QVariant.String, self.tr("Guideline Ref."), 50
                    ),
                ]
            )

            feature = QgsFeature(fields)
            feature.setGeometry(valid_geom)
            feature.setAttributes(
                [
                    icao_code,
                    self.tr("Wind Turbine Assessment Zone (30km Radius)"),
                    GUIDELINE_D_TURBINE_RADIUS_M / 1000.0,
                    self.tr("NASF Guideline D"),
                ]
            )

            layer_display_name = (
                f"{icao_code} {self.tr('Wind Turbine Assessment Zone')}"
            )
            internal_name_base = f"Guideline_D_TurbineZone_{icao_code}"
            style_key = "Wind Turbine Assessment Zone"  # Matches style_map key

            layer_created = self._create_and_add_layer(
                "Polygon",
                internal_name_base,
                layer_display_name,
                fields,
                [feature],
                layer_group,
                style_key,
            )
            return layer_created is not None
        except Exception as e:
            QgsMessageLog.logMessage(
                f"Error processing Guideline D (Wind Turbine): {e}\n{traceback.format_exc()}",
                plugin_tag,
                level=Qgis.Critical,
            )
            return False

    def process_guideline_e(
        self, runway_data: dict, layer_group: QgsLayerTreeGroup
    ) -> bool:
        """Processes Guideline E: Lighting Control Zone and the new LCZ Area circle."""
        runway_name = runway_data.get(
            "short_name", f"RWY_{runway_data.get('original_index','?')}"
        )
        thr_point = runway_data.get("thr_point")
        rec_thr_point = runway_data.get("rec_thr_point")

        if not all(
            [thr_point, rec_thr_point, layer_group]
        ):  # Basic check for core data
            QgsMessageLog.logMessage(
                f"Guideline E skipped for {runway_name}: Missing threshold points or layer group.",
                PLUGIN_TAG,
                level=Qgis.Warning,
            )
            return False
        if thr_point.compare(rec_thr_point, 1e-6):  # Check if points are identical
            QgsMessageLog.logMessage(
                f"Guideline E skipped for {runway_name}: Threshold points are identical.",
                PLUGIN_TAG,
                level=Qgis.Warning,
            )
            return False

        full_geoms: Dict[str, Optional[QgsGeometry]] = {}
        final_geoms: Dict[str, Optional[QgsGeometry]] = {}
        overall_success = False

        # --- Standard LCZ Zones (A, B, C, D) ---
        try:
            # This is the updated create_lcz_layer function
            def create_lcz_layer(
                zone_letter: str, geom: Optional[QgsGeometry]
            ) -> bool:  # Renamed 'zone' to 'zone_letter'
                if not geom:
                    return False
                params = GUIDELINE_E_ZONE_PARAMS[zone_letter]
                display_name = f"{self.tr('LCZ')} {zone_letter} {runway_name}"
                internal_name = f"LCZ_{zone_letter}_{runway_name.replace('/', '_')}"
                fields = QgsFields(
                    [
                        QgsField("rwy", QVariant.String),
                        QgsField("zone", QVariant.String),
                        QgsField("desc", QVariant.String),
                        QgsField("inner_extent_m", QVariant.Double),
                        QgsField("outer_extent_m", QVariant.Double),
                        QgsField("wid_m", QVariant.Double),
                        QgsField("max_intensity", QVariant.String),
                        QgsField("ref_mos", QVariant.String),
                        QgsField("ref_nasf", QVariant.String),
                    ]
                )

                inner_extent_val = 0.0
                zone_index = GUIDELINE_E_ZONE_ORDER.index(zone_letter)
                if zone_index > 0:
                    previous_zone_id = GUIDELINE_E_ZONE_ORDER[zone_index - 1]
                    inner_extent_val = GUIDELINE_E_ZONE_PARAMS[previous_zone_id]["ext"]

                attributes = [
                    runway_name,
                    zone_letter,  # Use the letter A, B, C, D
                    params["desc"],
                    inner_extent_val,
                    params["ext"],
                    params["half_w"] * 2,
                    params["max_intensity"],
                    MOS_REF_GUIDELINE_E,
                    NASF_REF_GUIDELINE_E,
                ]
                feature = QgsFeature(fields)
                feature.setGeometry(geom)
                feature.setAttributes(attributes)
                layer = self._create_and_add_layer(
                    "Polygon",
                    internal_name,
                    display_name,
                    fields,
                    [feature],
                    layer_group,
                    f"LCZ {zone_letter}",
                )
                return layer is not None

            for zone_id_geom_gen in GUIDELINE_E_ZONE_ORDER:
                params_geom = GUIDELINE_E_ZONE_PARAMS[zone_id_geom_gen]
                geom_full = self._create_runway_aligned_rectangle(
                    thr_point,
                    rec_thr_point,
                    params_geom["ext"],
                    params_geom["half_w"],
                    f"LCZ Full {zone_id_geom_gen} {runway_name}",
                )
                full_geoms[zone_id_geom_gen] = (
                    geom_full.makeValid()
                    if geom_full and not geom_full.isGeosValid()
                    else geom_full
                )

            geom_prev_for_diff = full_geoms.get("A")
            final_geoms["A"] = geom_prev_for_diff

            for i, zone_id_diff in enumerate(GUIDELINE_E_ZONE_ORDER[1:]):
                geom_curr_for_diff = full_geoms.get(zone_id_diff)
                prev_zone_id_for_diff = GUIDELINE_E_ZONE_ORDER[i]
                geom_prev_valid_for_diff = full_geoms.get(prev_zone_id_for_diff)

                if geom_curr_for_diff and geom_prev_valid_for_diff:
                    diff_geom = geom_curr_for_diff.difference(geom_prev_valid_for_diff)
                    final_geoms[zone_id_diff] = (
                        diff_geom.makeValid()
                        if diff_geom and not diff_geom.isGeosValid()
                        else diff_geom
                    )
                elif geom_curr_for_diff:
                    final_geoms[zone_id_diff] = geom_curr_for_diff
                else:
                    final_geoms[zone_id_diff] = None

            for zone_id_create in GUIDELINE_E_ZONE_ORDER:
                if final_geoms.get(zone_id_create):
                    if create_lcz_layer(zone_id_create, final_geoms[zone_id_create]):
                        overall_success = True
        except Exception as e:
            QgsMessageLog.logMessage(
                f"Error processing standard LCZ zones for {runway_name}: {e}\n{traceback.format_exc()}",
                PLUGIN_TAG,
                level=Qgis.Critical,
            )
            # overall_success might still be true if the new LCZ Area succeeds below

        # --- LCZ Area (6000m circle from runway midpoint) ---
        try:
            midpoint = self._get_runway_midpoint(thr_point, rec_thr_point)
            if midpoint:
                midpoint_geom = QgsGeometry.fromPointXY(midpoint)
                if not midpoint_geom.isNull():
                    radius_m = 6000.0
                    lcz_area_circle_geom = midpoint_geom.buffer(
                        radius_m, GUIDELINE_C_BUFFER_SEGMENTS
                    )  # Use same buffer segments as Guideline C for smoothness

                    if lcz_area_circle_geom and not lcz_area_circle_geom.isEmpty():
                        valid_lcz_area_geom = lcz_area_circle_geom.makeValid()
                        if valid_lcz_area_geom and valid_lcz_area_geom.isGeosValid():
                            lcz_area_fields = QgsFields(
                                [
                                    QgsField(
                                        "rwy",
                                        QVariant.String,
                                        self.tr("Runway Name"),
                                        30,
                                    ),
                                    QgsField(
                                        "desc",
                                        QVariant.String,
                                        self.tr("Description"),
                                        50,
                                    ),
                                    QgsField(
                                        "radius_m",
                                        QVariant.Double,
                                        self.tr("Radius (m)"),
                                        10,
                                        1,
                                    ),
                                    QgsField(
                                        "ref_mos",
                                        QVariant.String,
                                        self.tr("MOS Reference"),
                                        50,
                                    ),
                                    QgsField(
                                        "ref_nasf",
                                        QVariant.String,
                                        self.tr("NASF Guideline Reference"),
                                        50,
                                    ),
                                ]
                            )

                            feature = QgsFeature(lcz_area_fields)
                            feature.setGeometry(valid_lcz_area_geom)
                            attributes = [
                                runway_name,
                                "Lighting Control Area (6km Radius)",  # Description
                                radius_m,
                                "MOS 9.144(2)",  # Reference for LCZ Area
                                NASF_REF_GUIDELINE_E,  # Re-using Guideline E NASF ref, or a new one if needed
                            ]
                            feature.setAttributes(attributes)

                            display_name = f"{self.tr('LCZ Area')} {runway_name}"
                            internal_name = f"LCZ_Area_{runway_name.replace('/', '_')}"
                            # Add a style key for this new layer type if you intend to style it uniquely
                            style_key_lcz_area = "LCZ Area"  # Example, add to self.style_map if specific .qml exists
                            if style_key_lcz_area not in self.style_map:
                                self.style_map[style_key_lcz_area] = (
                                    "default_zone_polygon.qml"  # Fallback style
                                )

                            layer = self._create_and_add_layer(
                                "Polygon",
                                internal_name,
                                display_name,
                                lcz_area_fields,
                                [feature],
                                layer_group,
                                style_key_lcz_area,
                            )
                            if layer:
                                overall_success = True  # If this succeeds, the whole Guideline E processing is a success
                        else:
                            QgsMessageLog.logMessage(
                                f"Failed to create valid LCZ Area circle geometry for {runway_name} after makeValid.",
                                PLUGIN_TAG,
                                level=Qgis.Warning,
                            )
                    else:
                        QgsMessageLog.logMessage(
                            f"Failed to buffer LCZ Area circle for {runway_name}.",
                            PLUGIN_TAG,
                            level=Qgis.Warning,
                        )
                else:
                    QgsMessageLog.logMessage(
                        f"Failed to create geometry from midpoint for LCZ Area {runway_name}.",
                        PLUGIN_TAG,
                        level=Qgis.Warning,
                    )
            else:
                QgsMessageLog.logMessage(
                    f"Failed to calculate midpoint for LCZ Area {runway_name}.",
                    PLUGIN_TAG,
                    level=Qgis.Warning,
                )
        except Exception as e_lcz_area:
            QgsMessageLog.logMessage(
                f"Error processing LCZ Area (6km circle) for {runway_name}: {e_lcz_area}\n{traceback.format_exc()}",
                PLUGIN_TAG,
                level=Qgis.Critical,
            )

        return overall_success  # True if either standard LCZs or the new LCZ Area was created

    # ============================================================
    # Guideline F: OLS Processing Helpers
    # ============================================================
    def _get_conical_contour_fields(self) -> QgsFields:
        """Returns the QgsFields definition for the Conical Contour layer."""
        fields = QgsFields(
            [
                QgsField("surface", QVariant.String, self.tr("Surface Type"), 30),
                QgsField(
                    "contour_elev_am",
                    QVariant.Double,
                    self.tr("Contour Elev (AMSL)"),
                    10,
                    2,
                ),
                QgsField(
                    "contour_hgt_abv",
                    QVariant.Double,
                    self.tr("Height Above IHS (m)"),
                    10,
                    2,
                ),
                QgsField("ref_mos", QVariant.String, self.tr("Reference"), 100),
            ]
        )
        return fields

    def _get_approach_contour_fields(self) -> QgsFields:
        """Returns the QgsFields definition for the Approach Contour layer."""
        fields = QgsFields(
            [
                QgsField("rwy_name", QVariant.String, self.tr("rwy"), 50),
                QgsField("end_desig", QVariant.String, self.tr("End Designator"), 10),
                QgsField("surface", QVariant.String, self.tr("Surface Type"), 30),
                QgsField(
                    "contour_elev_am",
                    QVariant.Double,
                    self.tr("Contour Elev (AMSL)"),
                    10,
                    2,
                ),
            ]
        )
        return fields

    def _get_tocs_contour_fields(self) -> QgsFields:
        return QgsFields(
            [
                QgsField("rwy_name", QVariant.String),
                QgsField("end_desig", QVariant.String),
                QgsField("surface", QVariant.String),
                QgsField("contour_elev_am", QVariant.Double),
            ]
        )

    def _get_transitional_contour_fields(self) -> QgsFields:
        """
        Returns minimal fields for the Transitional Contour lines.
        """
        return QgsFields(
            [
                QgsField("rwy_name", QVariant.String, self.tr("Runway"), 50),
                QgsField("surface", QVariant.String, self.tr("Surface Type"), 30),
                QgsField("section_desc", QVariant.String, self.tr("Section Desc"), 50),
                QgsField(
                    "contour_elev_am",
                    QVariant.Double,
                    self.tr("Contour Elev (AMSL)"),
                    10,
                    2,
                ),
            ]
        )

    def get_exterior_ring_as_linestring(geom: QgsGeometry) -> Optional[QgsGeometry]:
        """
        Returns the exterior ring as a LineString geometry (QgsGeometry) from a polygon or multipolygon.
        Returns None if not possible.
        """
        # Try asPolygon (single polygon)
        poly = geom.asPolygon()
        if poly and len(poly) > 0 and len(poly[0]) > 1:
            return QgsGeometry.fromPolylineXY(poly[0])
        # Try asMultiPolygon (multi-polygon)
        multi = geom.asMultiPolygon()
        if multi and len(multi) > 0 and len(multi[0]) > 0 and len(multi[0][0]) > 1:
            return QgsGeometry.fromPolylineXY(multi[0][0])
        return None

    def _get_ols_fields(self, surface_type: str) -> QgsFields:
        """Returns the QgsFields definition for a given OLS surface type."""
        # Base fields common to most OLS layers
        fields_list = [
            QgsField("rwy_name", QVariant.String, self.tr("rwy"), 50),
            QgsField("surface", QVariant.String, self.tr("Surface Type"), 50),
            QgsField("end_desig", QVariant.String, self.tr("End Designator"), 10),
            QgsField("section_desc", QVariant.String, self.tr("Section Desc"), 50),
            QgsField(
                "elev_m", QVariant.Double, self.tr("Outer Elev (AMSL)"), 10, 2
            ),  # Clarify: Elevation at outer edge of this section
            QgsField(
                "height_agl", QVariant.Double, self.tr("Height Gain (m)"), 10, 2
            ),  # Clarify: Height gain across this section
            QgsField("slope_perc", QVariant.Double, self.tr("Slope (%)"), 6, 3),
            QgsField("ref_mos", QVariant.String, self.tr("Reference"), 100),
        ]
        # Add specific fields based on type
        if surface_type in [
            "Approach",
            "TOCS",
            "InnerApproach",
            "InnerTransitional",
            "BaulkedLanding",
        ]:
            fields_list.extend(
                [
                    QgsField(
                        "len_m", QVariant.Double, self.tr("Section Length (m)"), 12, 2
                    ),  # Clarify: Length of this section
                    QgsField(
                        "innerw_m",
                        QVariant.Double,
                        self.tr("Section Start W (m)"),
                        10,
                        2,
                    ),  # Clarify: Width at start of this section
                    QgsField(
                        "outerw_m", QVariant.Double, self.tr("Section End W (m)"), 10, 2
                    ),  # Clarify: Width at end of this section
                    QgsField(
                        "diverg_perc", QVariant.Double, self.tr("Divergence (%)"), 6, 3
                    ),
                    QgsField(
                        "origin_offset",
                        QVariant.Double,
                        self.tr("Start Dist THR (m)"),
                        10,
                        2,
                    ),  # Clarify: Dist from THR to start of this section
                ]
            )
        elif surface_type == "Conical":
            fields_list.extend(
                [
                    QgsField(
                        "height_extent",
                        QVariant.Double,
                        self.tr("Height Extent (AGL)"),
                        10,
                        2,
                    ),  # Above IHS
                ]
            )
        elif surface_type == "OHS":
            fields_list.extend(
                [
                    QgsField("radius_m", QVariant.Double, self.tr("Radius (m)"), 12, 2),
                ]
            )
        elif surface_type == "Transitional":
            fields_list.extend(
                [
                    QgsField("side", QVariant.String, self.tr("Side (L/R)"), 5),
                ]
            )

        # Conditionally remove fields not applicable to the specific surface type
        final_fields = []
        # Define which fields to REMOVE for each type
        remove_map = {
            "IHS": [
                "end_desig",
                "len_m",
                "innerw_m",
                "outerw_m",
                "diverg_perc",
                "origin_offset",
                "height_extent",
                "radius_m",
                "side",
                "slope_perc",
            ],
            "Conical": [
                "end_desig",
                "len_m",
                "innerw_m",
                "outerw_m",
                "diverg_perc",
                "origin_offset",
                "shape_desc",
                "radius_m",
                "side",
            ],
            "OHS": [
                "end_desig",
                "len_m",
                "innerw_m",
                "outerw_m",
                "diverg_perc",
                "origin_offset",
                "shape_desc",
                "height_extent",
                "side",
                "slope_perc",
            ],
            "Transitional": [
                "end_desig",
                "len_m",
                "innerw_m",
                "outerw_m",
                "diverg_perc",
                "origin_offset",
                "shape_desc",
                "height_extent",
                "radius_m",
            ],
            "Approach": [
                "shape_desc",
                "height_extent",
                "radius_m",
                "side",
            ],  # Keep App/TOCS specific + base + Section_Desc
            "InnerApproach": [
                "shape_desc",
                "height_extent",
                "radius_m",
                "side",
                "diverg_perc",
                "section_desc",
            ],  # Inner Approach is single section
            "TOCS": [
                "shape_desc",
                "height_extent",
                "radius_m",
                "side",
            ],  # Keep App/TOCS specific + base
            "InnerTransitional": [
                "shape_desc",
                "height_extent",
                "radius_m",
                "side",
                "diverg_perc",
                "section_desc",
            ],
            "BaulkedLanding": [
                "shape_desc",
                "height_extent",
                "radius_m",
                "side",
                "section_desc",
            ],
        }
        fields_to_remove = set(remove_map.get(surface_type, []))

        for field in fields_list:
            if field.name() not in fields_to_remove:
                # Update labels for clarity
                if field.name() == "elev_m":
                    field.setAlias(self.tr("Section Upper Elev (AMSL)"))
                elif field.name() == "height_agl":
                    field.setAlias(self.tr("Section Height Gain (m)"))
                elif field.name() == "len_m":
                    field.setAlias(self.tr("Section Length (m)"))
                elif field.name() == "innerw_m":
                    field.setAlias(self.tr("Section Start W (m)"))
                elif field.name() == "outerw_m":
                    field.setAlias(self.tr("Section End W (m)"))
                elif field.name() == "origin_offset":
                    field.setAlias(self.tr("Section Start Dist THR (m)"))
                final_fields.append(field)

        return QgsFields(final_fields)

    def _generate_approach_surface(
        self,
        runway_data: dict,
        rwy_params: dict,
        arc_num: int,
        end_type: str,
        thr_point: QgsPointXY,
        outward_azimuth: float,
        end_desig: str,
        threshold_elevation: Optional[float],
    ) -> Tuple[List[QgsFeature], List[QgsFeature]]:  # <<< Changed return type
        """
        Generates a list of Approach Surface section features (polygons)
        and a list of contour line features.
        Returns a tuple: (list_of_main_polygon_features, list_of_contour_features)
        """

        # --- Get Section Parameters ---
        sections = ols_dimensions.get_ols_params(arc_num, end_type, "APPROACH")
        if not sections:
            QgsMessageLog.logMessage(
                f"No Approach params found for {end_desig} (Code {arc_num}, Type {end_type})",
                PLUGIN_TAG,
                level=Qgis.Warning,
            )
            return [], []  # <<< Return empty lists

        # --- Initialize Variables ---
        main_polygon_features: List[QgsFeature] = (
            []
        )  # <<< List to hold section features
        contour_line_features: List[QgsFeature] = []
        # calculated_total_length = 0.0 # No longer needed for overall feature
        # final_outer_width = 0.0     # No longer needed for overall feature
        # final_outer_elevation = threshold_elevation # No longer needed for overall feature

        if threshold_elevation is None:
            QgsMessageLog.logMessage(
                f"Warning: Threshold elevation missing for Approach {end_desig}. Contour/Section AMSL values will be None.",
                PLUGIN_TAG,
                level=Qgis.Warning,
            )

        # --- Loop Through Sections ---
        current_start_point: Optional[QgsPointXY] = None
        current_start_width: float = 0.0
        current_elevation_amsl = threshold_elevation
        current_dist_from_thr = (
            0.0  # Keep track of cumulative distance for Origin_Offset
        )

        for i, section_params in enumerate(sections):
            # --- Get section parameters ---
            section_length = section_params.get("length", 0.0)
            section_slope = section_params.get("slope", 0.0)
            section_divergence = section_params.get("divergence", 0.0)  # Per side
            ref = section_params.get("ref", "MOS T8.2-1 (Check)")

            if section_length <= 0:
                continue  # Skip sections with no length

            # --- Determine Start Point, Width, and Origin Offset for this section ---
            section_start_dist_thr: Optional[float] = None
            if i == 0:  # First section
                start_dist_offset = section_params.get("start_dist_from_thr", 0.0)
                start_width = section_params.get("start_width", 0.0)
                if start_width <= 0:
                    QgsMessageLog.logMessage(
                        f"Error: Invalid start_width {start_width} for Approach {end_desig} Section 1.",
                        PLUGIN_TAG,
                        level=Qgis.Critical,
                    )
                    return [], []
                current_start_point = thr_point.project(
                    start_dist_offset, outward_azimuth
                )
                current_start_width = start_width
                current_dist_from_thr = (
                    start_dist_offset  # Initialize cumulative distance
                )
                section_start_dist_thr = start_dist_offset  # Store for attribute
            else:  # Subsequent sections start where previous ended
                if current_start_point is None or current_start_width <= 0:
                    QgsMessageLog.logMessage(
                        f"Error: Cannot start Approach {end_desig} Section {i+1}, previous section failed.",
                        PLUGIN_TAG,
                        level=Qgis.Critical,
                    )
                    return [], []
                # Start point, width, and elevation carry over
                section_start_dist_thr = (
                    current_dist_from_thr  # Distance to *start* of this section
                )

            # --- Calculate End Point and Width for this section ---
            current_start_hw = current_start_width / 2.0
            section_end_width = current_start_width + (
                2 * section_length * section_divergence
            )
            end_hw = section_end_width / 2.0
            end_point = current_start_point.project(section_length, outward_azimuth)

            if not end_point:
                QgsMessageLog.logMessage(
                    f"Error calculating end point for Approach {end_desig} Section {i+1}.",
                    PLUGIN_TAG,
                    level=Qgis.Warning,
                )
                continue  # Skip this section

            # --- Generate Section Geometry ---
            section_geom: Optional[QgsGeometry] = None
            # Determine Section Description
            section_desc = f"Section {i+1}"
            if (
                abs(section_slope) < 1e-9 and i > 0
            ):  # If slope is effectively zero and not the first section
                section_desc = "Horizontal"

            section_name_log = f"Approach {end_desig} {section_desc}"

            if abs(section_divergence) < 1e-9:  # Horizontal section or parallel sides
                section_geom = self._create_rectangle_from_start(
                    current_start_point,
                    outward_azimuth,
                    section_length,
                    current_start_hw,
                    section_name_log,
                )
            else:  # Diverging section
                section_geom = self._create_trapezoid(
                    current_start_point,
                    outward_azimuth,
                    section_length,
                    current_start_hw,
                    end_hw,
                    section_name_log,
                )

            valid_geom: Optional[QgsGeometry] = None
            if section_geom and not section_geom.isEmpty():
                valid_geom = section_geom.makeValid()
                if (
                    not valid_geom
                    or valid_geom.isEmpty()
                    or not valid_geom.isGeosValid()
                ):
                    QgsMessageLog.logMessage(
                        f"Warning: Invalid geometry generated for {section_name_log}.",
                        PLUGIN_TAG,
                        level=Qgis.Warning,
                    )
                    valid_geom = None  # Invalidate if makeValid failed
            else:
                QgsMessageLog.logMessage(
                    f"Warning: Failed to generate geometry for {section_name_log}.",
                    PLUGIN_TAG,
                    level=Qgis.Warning,
                )

            # --- Create Feature for THIS Section ---
            if valid_geom:
                try:
                    fields = self._get_ols_fields("Approach")
                    feature = QgsFeature(fields)
                    feature.setGeometry(valid_geom)

                    # Calculate section-specific elevations/heights
                    section_outer_elevation = (
                        (current_elevation_amsl + section_length * section_slope)
                        if current_elevation_amsl is not None
                        else None
                    )
                    section_height_gain = (
                        section_length * section_slope
                    )  # Height gain over this section

                    attr_map = {
                        "rwy_name": runway_data.get("short_name", "N/A"),
                        "surface": "Approach",
                        "end_desig": end_desig,
                        "section_desc": section_desc,
                        "elev_m": section_outer_elevation,  # Elevation at outer edge of this section
                        "height_agl": section_height_gain,  # Height gain over this section
                        "slope_perc": (
                            section_slope * 100.0 if section_slope is not None else None
                        ),
                        "ref_mos": ref,
                        "len_m": section_length,  # Length of this section
                        "innerw_m": current_start_width,  # Width at start of this section
                        "outerw_m": section_end_width,  # Width at end of this section
                        "diverg_perc": (
                            section_divergence * 100.0
                            if section_divergence is not None
                            else None
                        ),
                        "origin_offset": section_start_dist_thr,  # Distance from THR to start of this section
                    }
                    for name, value in attr_map.items():
                        idx = fields.indexFromName(name)
                        if idx != -1:
                            feature.setAttribute(idx, value)

                    main_polygon_features.append(
                        feature
                    )  # Add section feature to the list

                except Exception as e_feat:
                    QgsMessageLog.logMessage(
                        f"Error creating feature for {section_name_log}: {e_feat}",
                        PLUGIN_TAG,
                        level=Qgis.Critical,
                    )
                    # Optionally decide whether to halt all processing for this approach end
                    # return [], contour_line_features # Example: Stop if one section fails

            # --- Generate Contours within this Section ---
            if (
                current_elevation_amsl is not None
                and section_outer_elevation is not None
            ):
                start_elev = current_elevation_amsl
                end_elev = section_outer_elevation

                contour_elevs = set()

                if abs(section_slope) < 1e-9 and i > 0:
                    # Horizontal section (non-initial): add start and end
                    contour_elevs.add(round(start_elev, 6))
                    contour_elevs.add(round(end_elev, 6))
                else:
                    # Sloped section: intervals + start
                    first_contour = (
                        math.ceil(start_elev / APPROACH_CONTOUR_INTERVAL)
                        * APPROACH_CONTOUR_INTERVAL
                    )
                    if first_contour < start_elev - 1e-6:
                        first_contour += APPROACH_CONTOUR_INTERVAL

                    c_elev = first_contour
                    while c_elev <= end_elev + 1e-6:
                        contour_elevs.add(round(c_elev, 6))
                        c_elev += APPROACH_CONTOUR_INTERVAL

                    contour_elevs.add(round(start_elev, 6))

                # --- Add a contour at the very end of the final section if it's horizontal ---
                if abs(section_slope) < 1e-9 and i == len(sections) - 1:
                    contour_elevs.add(round(end_elev, 6))

                contour_elevs = sorted(contour_elevs)

                for target_elev in contour_elevs:
                    delta_h = target_elev - start_elev
                    max_delta_h = section_length * section_slope

                    if abs(section_slope) < 1e-9:
                        dist_along = 0
                    else:
                        if delta_h < -1e-6 or delta_h > max_delta_h + 1e-6:
                            continue  # Skip contours outside this section
                        dist_along = delta_h / section_slope

                    cl_point = current_start_point.project(dist_along, outward_azimuth)
                    current_width_at_dist = current_start_width + (
                        2 * dist_along * section_divergence
                    )
                    half_width = current_width_at_dist / 2.0

                    if cl_point and half_width > 0:
                        az_perp_l = (outward_azimuth - 90.0 + 360.0) % 360.0
                        az_perp_r = (outward_azimuth + 90.0) % 360.0
                        pt_l = cl_point.project(half_width, az_perp_l)
                        pt_r = cl_point.project(half_width, az_perp_r)

                        if pt_l and pt_r:
                            contour_geom = QgsGeometry.fromPolylineXY([pt_l, pt_r])
                            if contour_geom and not contour_geom.isEmpty():
                                # --- CLIP CONTOUR TO CURRENT SECTION POLYGON ---
                                if valid_geom:  # Clip to current section
                                    clipped_geom = contour_geom.intersection(valid_geom)
                                    if clipped_geom and not clipped_geom.isEmpty():
                                        contour_fields = QgsFields(
                                            [
                                                QgsField("rwy_name", QVariant.String),
                                                QgsField("end_desig", QVariant.String),
                                                QgsField("surface", QVariant.String),
                                                QgsField(
                                                    "contour_elev_am", QVariant.Double
                                                ),
                                            ]
                                        )
                                        contour_feature = QgsFeature(contour_fields)
                                        contour_feature.setGeometry(clipped_geom)
                                        contour_attr_map = {
                                            "rwy_name": runway_data.get(
                                                "short_name", "N/A"
                                            ),
                                            "end_desig": end_desig,
                                            "surface": "Approach",
                                            "contour_elev_am": target_elev,
                                        }
                                        contour_feature.setAttributes(
                                            [
                                                contour_attr_map[k]
                                                for k in contour_attr_map
                                            ]
                                        )
                                        contour_line_features.append(contour_feature)

            # --- Update for next iteration ---
            current_start_point = end_point
            current_start_width = section_end_width
            # Use calculated outer elevation for the start of the next section
            current_elevation_amsl = section_outer_elevation
            current_dist_from_thr += section_length  # Update cumulative distance

        # --- Return lists of features ---
        return (
            main_polygon_features,
            contour_line_features,
        )  # <<< Return list of section features

    def _generate_tocs(
        self,
        runway_data: dict,
        rwy_params: dict,
        arc_num: int,
        end_type: str,
        runway_phys_end_point: QgsPointXY,
        clearway_len: float,
        outward_azimuth: float,
        end_desig: str,
        origin_elevation: Optional[float],
    ) -> Tuple[Optional[QgsFeature], List[QgsFeature]]:
        """
        Generates a single Take-Off Climb Surface (TOCS) feature and a list of contour features.
        Shape can be a composite trapezoid + rectangle based on parameters.
        """

        # Always define these!
        final_geom = None
        tocs_contour_features = []

        # 1. Get Parameters
        params = ols_dimensions.get_ols_params(arc_num, None, "TOCS")
        if not params:
            QgsMessageLog.logMessage(
                f"No TOCS params found for {end_desig} (Code {arc_num})",
                PLUGIN_TAG,
                level=Qgis.Warning,
            )
            return None, []

        try:
            origin_offset = params.get("origin_offset")
            inner_width = params.get("inner_edge_width")
            divergence = params.get("divergence")
            overall_length = params.get("length")
            final_width = params.get("final_width")
            slope = params.get("slope")
            ref = params.get("ref", "MOS T8.2-1 (Check)")

            essential_params = [
                origin_offset,
                inner_width,
                divergence,
                overall_length,
                final_width,
                slope,
            ]
            if any(p is None for p in essential_params):
                missing_keys = [
                    k
                    for k, v in params.items()
                    if v is None
                    and k
                    in [
                        "origin_offset",
                        "inner_edge_width",
                        "divergence",
                        "length",
                        "final_width",
                        "slope",
                    ]
                ]
                QgsMessageLog.logMessage(
                    f"Essential TOCS parameters missing or None ({', '.join(missing_keys)}) for Code {arc_num}, End {end_desig}.",
                    PLUGIN_TAG,
                    level=Qgis.Critical,
                )
                return None, []

            origin_offset = float(origin_offset)
            inner_width = float(inner_width)
            divergence = float(divergence)
            overall_length = float(overall_length)
            final_width = float(final_width)
            slope = float(slope)

        except (ValueError, TypeError, KeyError) as e_param:
            QgsMessageLog.logMessage(
                f"Error processing/converting TOCS parameters for Code {arc_num}, End {end_desig}: {e_param}",
                PLUGIN_TAG,
                level=Qgis.Critical,
            )
            return None, []

        inner_hw = inner_width / 2.0
        final_hw = final_width / 2.0

        if (
            overall_length <= 0
            or inner_width <= 0
            or divergence is None
            or divergence < 0
            or final_width <= 0
        ):
            QgsMessageLog.logMessage(
                f"Invalid TOCS dimensions/params for {end_desig} (L={overall_length}, IW={inner_width}, FW={final_width}, Div={divergence})",
                PLUGIN_TAG,
                level=Qgis.Warning,
            )
            return None, []

        # 2. Calculate Start Point of TOCS Inner Edge
        effective_takeoff_start = runway_phys_end_point
        if clearway_len > 1e-6:
            projected_clearway_end = effective_takeoff_start.project(
                clearway_len, outward_azimuth
            )
            if not projected_clearway_end:
                QgsMessageLog.logMessage(
                    f"Failed calc TOCS clearway end point {end_desig}",
                    PLUGIN_TAG,
                    level=Qgis.Warning,
                )
                return None, []
            effective_takeoff_start = projected_clearway_end

        start_point = effective_takeoff_start.project(origin_offset, outward_azimuth)
        if not start_point:
            QgsMessageLog.logMessage(
                f"Failed calc TOCS start point after offset {end_desig}",
                PLUGIN_TAG,
                level=Qgis.Warning,
            )
            return None, []

        # 3. Calculate Length of Divergence Section
        width_increase_per_side = final_hw - inner_hw
        length_divergence = (
            width_increase_per_side / divergence if width_increase_per_side > 0 else 0.0
        )

        # 4. Generate Geometry
        try:
            if length_divergence >= overall_length - 1e-6:
                outer_hw_at_overall = inner_hw + (overall_length * divergence)
                final_geom = self._create_trapezoid(
                    start_point,
                    outward_azimuth,
                    overall_length,
                    inner_hw,
                    outer_hw_at_overall,
                    f"TOCS Trapezoid {end_desig}",
                )
            else:
                trap_geom = self._create_trapezoid(
                    start_point,
                    outward_azimuth,
                    length_divergence,
                    inner_hw,
                    final_hw,
                    f"TOCS Trapezoid Part {end_desig}",
                )
                rect_start_point = start_point.project(
                    length_divergence, outward_azimuth
                )
                length_rectangle = overall_length - length_divergence

                if not rect_start_point or length_rectangle < 1e-6:
                    final_geom = trap_geom
                else:
                    rect_geom = self._create_rectangle_from_start(
                        rect_start_point,
                        outward_azimuth,
                        length_rectangle,
                        final_hw,
                        f"TOCS Rectangle Part {end_desig}",
                    )
                    if trap_geom and rect_geom:
                        combined = QgsGeometry.unaryUnion([trap_geom, rect_geom])
                        if combined and not combined.isEmpty():
                            final_geom = combined.makeValid()
                        else:
                            final_geom = trap_geom
                    elif trap_geom:
                        final_geom = trap_geom
                    else:
                        final_geom = None

        except Exception as e_geom:
            QgsMessageLog.logMessage(
                f"Error generating TOCS geometry for {end_desig}: {e_geom}",
                PLUGIN_TAG,
                level=Qgis.Critical,
            )
            return None, []

        if not final_geom or final_geom.isEmpty() or not final_geom.isGeosValid():
            QgsMessageLog.logMessage(
                f"Failed create valid TOCS geometry for {end_desig}",
                PLUGIN_TAG,
                level=Qgis.Warning,
            )
            return None, []

        # 5. Create TOCS Polygon Feature
        height_agl = overall_length * slope
        elevation_amsl = (
            (origin_elevation + height_agl) if origin_elevation is not None else None
        )

        fields = self._get_ols_fields("TOCS")
        feature = QgsFeature(fields)
        feature.setGeometry(final_geom)
        attr_map = {
            "rwy_name": runway_data.get("short_name", "N/A"),
            "surface": "TOCS",
            "end_desig": end_desig,
            "elev_m": elevation_amsl,
            "height_agl": height_agl,
            "slope_perc": slope * 100.0 if slope is not None else None,
            "ref_mos": ref,
            "len_m": overall_length,
            "innerw_m": inner_width,
            "outerw_m": final_width,
            "diverg_perc": divergence * 100.0 if divergence is not None else None,
            "origin_offset": origin_offset,
        }
        for name, value in attr_map.items():
            idx = fields.indexFromName(name)
            if idx != -1:
                feature.setAttribute(idx, value)

        # ---- TOCS Contour Features with Clipping ----
        # TOCS_CONTOUR_INTERVAL = 10.0  # Adjust as needed
        tocs_contour_features = []
        if origin_elevation is not None and overall_length > 0:
            start_elev = origin_elevation
            end_elev = origin_elevation + height_agl

            contour_elevs = set()

            # Add interval contours
            first_contour = (
                math.ceil(start_elev / TOCS_CONTOUR_INTERVAL) * TOCS_CONTOUR_INTERVAL
            )
            if first_contour < start_elev - 1e-6:
                first_contour += TOCS_CONTOUR_INTERVAL

            c_elev = first_contour
            while c_elev <= end_elev + 1e-6:
                contour_elevs.add(round(c_elev, 6))
                c_elev += TOCS_CONTOUR_INTERVAL

            # Always add start and end elevation
            contour_elevs.add(round(start_elev, 6))
            contour_elevs.add(round(end_elev, 6))

            contour_elevs = sorted(contour_elevs)

            for target_elev in contour_elevs:
                delta_h = target_elev - start_elev
                if slope == 0:
                    dist_along = 0
                else:
                    if delta_h < -1e-6 or delta_h > height_agl + 1e-6:
                        continue
                    dist_along = delta_h / slope

                is_last_contour = abs(target_elev - end_elev) < 1e-6

                if is_last_contour:
                    # At the end: use polygon outer width, no clipping
                    cl_point = start_point.project(overall_length, outward_azimuth)
                    current_width_at_dist = final_width
                    half_width = current_width_at_dist / 2.0

                    if cl_point and half_width > 0:
                        az_perp_l = (outward_azimuth - 90.0 + 360.0) % 360.0
                        az_perp_r = (outward_azimuth + 90.0) % 360.0
                        pt_l = cl_point.project(half_width, az_perp_l)
                        pt_r = cl_point.project(half_width, az_perp_r)

                        if pt_l and pt_r:
                            contour_geom = QgsGeometry.fromPolylineXY([pt_l, pt_r])
                            # No clipping for the last contour
                            final_contour_geom = contour_geom
                else:
                    # Intermediate contours: project as normal, then clip
                    cl_point = start_point.project(dist_along, outward_azimuth)
                    current_width_at_dist = inner_width + (2 * dist_along * divergence)
                    half_width = current_width_at_dist / 2.0

                    if cl_point and half_width > 0:
                        az_perp_l = (outward_azimuth - 90.0 + 360.0) % 360.0
                        az_perp_r = (outward_azimuth + 90.0) % 360.0
                        pt_l = cl_point.project(half_width, az_perp_l)
                        pt_r = cl_point.project(half_width, az_perp_r)

                        if pt_l and pt_r:
                            contour_geom = QgsGeometry.fromPolylineXY([pt_l, pt_r])
                            # Clip to TOCS polygon
                            final_contour_geom = contour_geom.intersection(final_geom)
                # If valid, create the feature
                if (
                    "final_contour_geom" in locals()
                    and final_contour_geom
                    and not final_contour_geom.isEmpty()
                ):
                    contour_fields = QgsFields(
                        [
                            QgsField("rwy_name", QVariant.String),
                            QgsField("end_desig", QVariant.String),
                            QgsField("surface", QVariant.String),
                            QgsField("contour_elev_am", QVariant.Double),
                        ]
                    )
                    contour_feature = QgsFeature(contour_fields)
                    contour_feature.setGeometry(final_contour_geom)
                    contour_attr_map = {
                        "rwy_name": runway_data.get("short_name", "N/A"),
                        "end_desig": end_desig,
                        "surface": "TOCS",
                        "contour_elev_am": target_elev,
                    }
                    contour_feature.setAttributes(
                        [contour_attr_map[k] for k in contour_attr_map]
                    )
                    tocs_contour_features.append(contour_feature)
                # Clean up variable for next loop
                if "final_contour_geom" in locals():
                    del final_contour_geom

        # Return both the polygon and the contour features list
        return feature, tocs_contour_features

    def process_guideline_f(
        self,
        runway_data: dict,
        layer_group: QgsLayerTreeGroup,
        ofz_group: Optional[QgsLayerTreeGroup] = None,
    ) -> bool:
        plugin_tag = PLUGIN_TAG

        # --- Get Core Data from runway_data ---
        runway_name = runway_data.get(
            "short_name", f"RWY_{runway_data.get('original_index','?')}"
        )
        primary_threshold_point = runway_data.get("thr_point")
        reciprocal_threshold_point = runway_data.get("rec_thr_point")
        arc_num_str = runway_data.get("arc_num")
        primary_approach_type_str = runway_data.get("type1", "")
        reciprocal_approach_type_str = runway_data.get("type2", "")
        primary_thr_elev = runway_data.get("thr_elev_1")
        reciprocal_thr_elev = runway_data.get("thr_elev_2")

        runway_actual_width_val = runway_data.get("width")
        if runway_actual_width_val is None:
            QgsMessageLog.logMessage(
                f"Runway OLS for {runway_name} SKIPPED: Missing 'width' in runway_data.",
                plugin_tag,
                Qgis.Warning,
            )
            return False
        try:
            runway_actual_width = float(runway_actual_width_val)
            if runway_actual_width <= 0:
                QgsMessageLog.logMessage(
                    f"Runway OLS for {runway_name} SKIPPED: Runway 'width' ({runway_actual_width}) must be positive.",
                    plugin_tag,
                    Qgis.Warning,
                )
                return False
        except (ValueError, TypeError):
            QgsMessageLog.logMessage(
                f"Runway OLS for {runway_name} SKIPPED: Invalid 'width' ('{runway_actual_width_val}') in runway_data.",
                plugin_tag,
                Qgis.Warning,
            )
            return False

        QgsMessageLog.logMessage(
            f"Starting Runway OLS processing (OFZ components, Approach, TOCS) for {runway_name}",
            plugin_tag,
            level=Qgis.Info,
        )

        if not all(
            [
                primary_threshold_point,
                reciprocal_threshold_point,
                layer_group,
                arc_num_str,
            ]
        ):
            QgsMessageLog.logMessage(
                f"Runway OLS for {runway_name} SKIPPED: Missing essential base data.",
                plugin_tag,
                Qgis.Warning,
            )
            return False
        try:
            arc_num = int(arc_num_str)
        except (ValueError, TypeError):
            QgsMessageLog.logMessage(
                f"Runway OLS for {runway_name} SKIPPED: Invalid ARC number '{arc_num_str}'.",
                plugin_tag,
                Qgis.Warning,
            )
            return False

        primary_desig, reciprocal_desig = (
            runway_name.split("/") if "/" in runway_name else ("THR1", "THR2")
        )

        QgsMessageLog.logMessage(
            f"DEBUG PGF Start: For Runway '{runway_name}'...", plugin_tag, Qgis.Info
        )

        rwy_params = self._get_runway_parameters(
            primary_threshold_point, reciprocal_threshold_point
        )
        if rwy_params is None:
            return False  # Error logged in helper

        az_primary_to_reciprocal = rwy_params["azimuth_p_r"]
        az_reciprocal_to_primary = rwy_params["azimuth_r_p"]

        clearway_len_at_primary_end = float(
            runway_data.get("clearway1_len", 0.0) or 0.0
        )
        clearway_len_at_reciprocal_end = float(
            runway_data.get("clearway2_len", 0.0) or 0.0
        )
        disp_at_primary_thr = float(runway_data.get("thr_displaced_1", 0.0) or 0.0)
        disp_at_reciprocal_thr = float(runway_data.get("thr_displaced_2", 0.0) or 0.0)

        physical_endpoints_result_tuple = self._get_physical_runway_endpoints(
            primary_threshold_point,
            reciprocal_threshold_point,
            disp_at_primary_thr,
            disp_at_reciprocal_thr,
            rwy_params,
        )
        if physical_endpoints_result_tuple is None:
            return False  # Error logged in helper
        phys_pavement_end_near_primary_thr, phys_pavement_end_near_reciprocal_thr, _ = (
            physical_endpoints_result_tuple
        )

        overall_success = False
        inner_approach_features, approach_poly_features, approach_contour_features = (
            [],
            [],
            [],
        )
        (
            tocs_poly_features,
            tocs_contour_features,
            ofz_inner_trans_features,
            ofz_bls_features,
        ) = ([], [], [], [])

        IHS_ELEVATION_AMSL: Optional[float] = None
        if self.reference_elevation_datum is not None:
            ihs_base_height_agl = ols_dimensions.get_ihs_base_height()
            if ihs_base_height_agl is not None:
                IHS_ELEVATION_AMSL = (
                    self.reference_elevation_datum + ihs_base_height_agl
                )
        if IHS_ELEVATION_AMSL is None:
            QgsMessageLog.logMessage(
                f"Runway OLS for {runway_name}: IHS Elevation could not be determined.",
                plugin_tag,
                Qgis.Warning,
            )

        runway_end_configurations = [
            {
                "current_desig": primary_desig,
                "landing_threshold_pt": primary_threshold_point,
                "landing_threshold_elev": primary_thr_elev,
                "approach_type_str": primary_approach_type_str,
                "approach_surface_outward_azimuth": az_reciprocal_to_primary,
                "baulked_landing_origin_thr_pt": primary_threshold_point,
                "baulked_landing_flight_path_azimuth": az_primary_to_reciprocal,
                "tocs_departure_pavement_end_pt": phys_pavement_end_near_reciprocal_thr,
                "tocs_flight_path_azimuth": az_primary_to_reciprocal,
                "tocs_clearway_len_at_departure_end": clearway_len_at_reciprocal_end,
                "runway_orientation_azimuth_for_its_perp": az_primary_to_reciprocal,
            },
            {
                "current_desig": reciprocal_desig,
                "landing_threshold_pt": reciprocal_threshold_point,
                "landing_threshold_elev": reciprocal_thr_elev,
                "approach_type_str": reciprocal_approach_type_str,
                "approach_surface_outward_azimuth": az_primary_to_reciprocal,
                "baulked_landing_origin_thr_pt": reciprocal_threshold_point,
                "baulked_landing_flight_path_azimuth": az_reciprocal_to_primary,
                "tocs_departure_pavement_end_pt": phys_pavement_end_near_primary_thr,
                "tocs_flight_path_azimuth": az_reciprocal_to_primary,
                "tocs_clearway_len_at_departure_end": clearway_len_at_primary_end,
                "runway_orientation_azimuth_for_its_perp": az_reciprocal_to_primary,
            },
        ]

        for config in runway_end_configurations:
            current_desig = config["current_desig"]
            QgsMessageLog.logMessage(
                f"Processing OLS for {runway_name} - End {current_desig}",
                plugin_tag,
                Qgis.Info,
            )

            ia_geom_for_its: Optional[QgsGeometry] = None
            ia_cl_start_xy: Optional[QgsPointXY] = None
            ia_cl_end_xy: Optional[QgsPointXY] = None
            ia_start_elev: Optional[float] = None
            ia_end_elev: Optional[float] = None
            ia_width: Optional[float] = None
            ia_length_param_val: Optional[float] = None

            bls_geom_for_its: Optional[QgsGeometry] = None
            bls_cl_start_xy: Optional[QgsPointXY] = None
            bls_cl_end_xy: Optional[QgsPointXY] = None
            bls_start_elev: Optional[float] = None
            bls_start_width: Optional[float] = None
            bls_end_width: Optional[float] = None
            bls_len: Optional[float] = None

            # --- Inner Approach ---
            try:
                QgsMessageLog.logMessage(
                    f"Debug InnerApproach: Attempting for {current_desig}",
                    plugin_tag,
                    Qgis.Info,
                )
                ia_params = ols_dimensions.get_ols_params(
                    arc_num, config["approach_type_str"], "InnerApproach"
                )
                if ia_params:
                    ia_slope_param = ia_params.get("slope")
                    ia_start_dist_param = ia_params.get("start_dist_from_thr")
                    ia_length_param_val = ia_params.get("length")
                    ia_width_param_val = ia_params.get("width")
                    ia_ref_param = ia_params.get("ref")
                    if all(
                        v is not None
                        for v in [
                            ia_slope_param,
                            ia_start_dist_param,
                            ia_length_param_val,
                            ia_width_param_val,
                        ]
                    ):
                        ia_cl_start_xy = config["landing_threshold_pt"].project(
                            ia_start_dist_param,
                            config["approach_surface_outward_azimuth"],
                        )
                        if ia_cl_start_xy:
                            ia_geom_for_its = self._create_rectangle_from_start(
                                ia_cl_start_xy,
                                config["approach_surface_outward_azimuth"],
                                ia_length_param_val,
                                ia_width_param_val / 2.0,
                                f"IA {current_desig}",
                            )
                            if ia_geom_for_its and ia_geom_for_its.isGeosValid():
                                ia_width = ia_width_param_val
                                ia_start_elev = (
                                    self._get_elevation_at_point_along_gradient(
                                        ia_cl_start_xy,
                                        primary_threshold_point,
                                        reciprocal_threshold_point,
                                        primary_thr_elev,
                                        reciprocal_thr_elev,
                                        QgsProject.instance().crs(),
                                    )
                                )
                                if ia_start_elev is not None:
                                    ia_end_elev = ia_start_elev + (
                                        ia_length_param_val * ia_slope_param
                                    )
                                    ia_cl_end_xy = ia_cl_start_xy.project(
                                        ia_length_param_val,
                                        config["approach_surface_outward_azimuth"],
                                    )
                                else:
                                    ia_end_elev = None
                                    QgsMessageLog.logMessage(
                                        f"Warning: IA {current_desig} start elevation is None.",
                                        plugin_tag,
                                        Qgis.Warning,
                                    )

                                fields = self._get_ols_fields("InnerApproach")
                                feat = QgsFeature(fields)
                                feat.setGeometry(ia_geom_for_its)
                                h_agl = ia_length_param_val * ia_slope_param
                                attrs = {
                                    "rwy_name": runway_name,
                                    "surface": "Inner Approach",
                                    "end_desig": current_desig,
                                    "elev_m": ia_end_elev,
                                    "height_agl": h_agl,
                                    "slope_perc": ia_slope_param * 100.0,
                                    "ref_mos": ia_ref_param,
                                    "len_m": ia_length_param_val,
                                    "innerw_m": ia_width_param_val,
                                    "outerw_m": ia_width_param_val,
                                    "origin_offset": ia_start_dist_param,
                                }
                                for n, v_attr in attrs.items():
                                    if fields.indexFromName(n) != -1:
                                        feat.setAttribute(
                                            fields.indexFromName(n), v_attr
                                        )
                                inner_approach_features.append(feat)
                QgsMessageLog.logMessage(
                    f"Debug InnerApproach: Completed for {current_desig}",
                    plugin_tag,
                    Qgis.Info,
                )
            except Exception as e_ia:
                QgsMessageLog.logMessage(
                    f"ERROR generating Inner Approach for {current_desig}: {e_ia}\n{traceback.format_exc()}",
                    plugin_tag,
                    Qgis.Critical,
                )

            # --- Baulked Landing ---
            try:
                QgsMessageLog.logMessage(
                    f"Debug BaulkedLanding: Attempting for {current_desig}",
                    plugin_tag,
                    Qgis.Info,
                )
                bls_params_dict = ols_dimensions.get_ols_params(
                    arc_num, config["approach_type_str"], "BaulkedLanding"
                )
                if bls_params_dict and IHS_ELEVATION_AMSL is not None:
                    QgsMessageLog.logMessage(
                        f"  DEBUG BLS Pre-Call for '{current_desig}': Origin THR: {config['baulked_landing_origin_thr_pt'].asWkt() if config['baulked_landing_origin_thr_pt'] else 'None'}, Azimuth: {config['baulked_landing_flight_path_azimuth']}",
                        plugin_tag,
                        Qgis.Info,
                    )
                    bls_result_tuple = self._generate_baulked_landing_surface(
                        runway_data,
                        rwy_params,
                        config["baulked_landing_origin_thr_pt"],
                        config["baulked_landing_flight_path_azimuth"],
                        bls_params_dict,
                        current_desig,
                        IHS_ELEVATION_AMSL,
                    )
                    QgsMessageLog.logMessage(
                        f"Debug BLS {current_desig}: Helper result: {bls_result_tuple is not None}",
                        plugin_tag,
                        Qgis.Info,
                    )
                    if bls_result_tuple:
                        feat_bls, bls_g, bls_l, bls_se, bls_cl_s_xy, bls_ew = (
                            bls_result_tuple
                        )
                        bls_geom_for_its = bls_g
                        bls_len = bls_l
                        bls_start_elev = bls_se
                        bls_cl_start_xy = bls_cl_s_xy
                        bls_end_width = bls_ew
                        bls_start_width = bls_params_dict.get("width")
                        if bls_cl_start_xy and bls_len is not None:
                            bls_cl_end_xy = bls_cl_start_xy.project(
                                bls_len, config["baulked_landing_flight_path_azimuth"]
                            )
                        if feat_bls:
                            ofz_bls_features.append(feat_bls)
                        else:
                            QgsMessageLog.logMessage(
                                f"Debug BLS {current_desig}: Feature from helper was None.",
                                plugin_tag,
                                Qgis.Warning,
                            )
                    else:
                        QgsMessageLog.logMessage(
                            f"Debug BLS {current_desig}: Helper returned None overall.",
                            plugin_tag,
                            Qgis.Warning,
                        )
                elif not bls_params_dict:
                    QgsMessageLog.logMessage(
                        f"Debug BaulkedLanding: Skipped {current_desig}: No params.",
                        plugin_tag,
                        Qgis.Info,
                    )
                elif IHS_ELEVATION_AMSL is None:
                    QgsMessageLog.logMessage(
                        f"Debug BaulkedLanding: Skipped {current_desig}: IHS_ELEVATION_AMSL is None.",
                        plugin_tag,
                        Qgis.Warning,
                    )
                QgsMessageLog.logMessage(
                    f"Debug BaulkedLanding: Completed for {current_desig}",
                    plugin_tag,
                    Qgis.Info,
                )
            except Exception as e_bls:
                QgsMessageLog.logMessage(
                    f"ERROR generating Baulked Landing for {current_desig}: {e_bls}\n{traceback.format_exc()}",
                    plugin_tag,
                    Qgis.Critical,
                )

            # --- Inner Transitional Surface ---
            if IHS_ELEVATION_AMSL is not None:
                it_params_dict = ols_dimensions.get_ols_params(
                    arc_num, config["approach_type_str"], "InnerTransitional"
                )
                if it_params_dict:
                    its_slope = it_params_dict.get("slope")
                    its_ref_mos = it_params_dict.get("ref", "MOS Ref ITS")

                    if its_slope is not None and its_slope > 1e-9:
                        its_fields = self._get_ols_fields("InnerTransitional")
                        strip_params_for_its = ols_dimensions.get_strip_params(
                            arc_num, config["approach_type_str"], runway_actual_width
                        )
                        graded_strip_total_width = 150.0
                        if (
                            strip_params_for_its
                            and strip_params_for_its.get("graded_width") is not None
                        ):
                            graded_strip_total_width = strip_params_for_its.get(
                                "graded_width"
                            )
                        else:
                            QgsMessageLog.logMessage(
                                f"Debug ITS {current_desig}: Using default strip width {graded_strip_total_width}m.",
                                plugin_tag,
                                Qgis.Info,
                            )
                        graded_strip_half_width = graded_strip_total_width / 2.0

                        main_centerline_orient_az = config[
                            "runway_orientation_azimuth_for_its_perp"
                        ]
                        # This definition of L/R for ITS projection is based on the main runway orientation
                        outward_az_L_ITS_projection = (
                            main_centerline_orient_az - 90.0 + 360.0
                        ) % 360.0
                        outward_az_R_ITS_projection = (
                            main_centerline_orient_az + 90.0
                        ) % 360.0

                        for side_label_its_panel, outward_projection_az_for_panel in [
                            ("L", outward_az_L_ITS_projection),
                            ("R", outward_az_R_ITS_projection),
                        ]:
                            QgsMessageLog.logMessage(
                                f"Generating ITS for {current_desig} - ITS Panel Side '{side_label_its_panel}'",
                                plugin_tag,
                                Qgis.Info,
                            )

                            P_IA_inner_3d_side, P_IA_outer_3d_side = None, None
                            P_BLS_inner_3d_side, P_BLS_outer_3d_side = None, None

                            # Define which side of IA/BLS corresponds to this ITS panel side
                            # If _get_polygon_side_3d_points uses (L=surface_az+90, R=surface_az-90)
                            # And IA surface az points "inwards" while BLS surface az points "outwards"
                            # then for the "L" ITS panel:
                            #   - We need the "L" side of IA (using side_label_its_panel 'L')
                            #   - We need the "L" side of BLS (using side_label_its_panel 'L')
                            # The helper _get_polygon_side_3d_points handles L/R relative to *its input surface's centerline*

                            if all(
                                v is not None
                                for v in [
                                    ia_geom_for_its,
                                    ia_cl_start_xy,
                                    ia_cl_end_xy,
                                    ia_start_elev,
                                    ia_end_elev,
                                    ia_width,
                                ]
                            ):
                                ia_side_pts_tuple = self._get_polygon_side_3d_points(
                                    ia_geom_for_its,
                                    ia_cl_start_xy,
                                    ia_cl_end_xy,
                                    ia_start_elev,
                                    ia_end_elev,
                                    ia_width / 2.0,
                                    ia_width / 2.0,
                                    side_label_its_panel,
                                )
                                if ia_side_pts_tuple:
                                    P_IA_inner_3d_side, P_IA_outer_3d_side = (
                                        ia_side_pts_tuple
                                    )

                            if (
                                all(
                                    v is not None
                                    for v in [
                                        bls_geom_for_its,
                                        bls_cl_start_xy,
                                        bls_cl_end_xy,
                                        bls_start_elev,
                                        bls_start_width,
                                        bls_end_width,
                                    ]
                                )
                                and bls_len is not None
                                and bls_len > 1e-6
                            ):
                                bls_side_pts_tuple = self._get_polygon_side_3d_points(
                                    bls_geom_for_its,
                                    bls_cl_start_xy,
                                    bls_cl_end_xy,
                                    bls_start_elev,
                                    IHS_ELEVATION_AMSL,
                                    bls_start_width / 2.0,
                                    bls_end_width / 2.0,
                                    self._flip_side_label(
                                        side_label_its_panel
                                    ),
                                )
                                if bls_side_pts_tuple:
                                    P_BLS_inner_3d_side, P_BLS_outer_3d_side = (
                                        bls_side_pts_tuple
                                    )

                            if P_IA_outer_3d_side and P_IA_inner_3d_side:
                                panel_feat = self._generate_its_panel_feature(
                                    P_IA_outer_3d_side,
                                    P_IA_inner_3d_side,
                                    its_slope,
                                    IHS_ELEVATION_AMSL,
                                    outward_projection_az_for_panel,
                                    runway_name,
                                    current_desig,
                                    side_label_its_panel,
                                    "IA Adjacent",
                                    its_ref_mos,
                                    its_fields,
                                )
                                if panel_feat:
                                    ofz_inner_trans_features.append(panel_feat)
                            else:
                                QgsMessageLog.logMessage(
                                    f"ITS IA-Adjacent Panel {current_desig} {side_label_its_panel} SKIPPED: Missing 3D base points from IA.",
                                    plugin_tag,
                                    Qgis.Warning,
                                )

                            if P_BLS_inner_3d_side and P_BLS_outer_3d_side:
                                panel_feat = self._generate_its_panel_feature(
                                    P_BLS_inner_3d_side,
                                    P_BLS_outer_3d_side,
                                    its_slope,
                                    IHS_ELEVATION_AMSL,
                                    outward_projection_az_for_panel,
                                    runway_name,
                                    current_desig,
                                    side_label_its_panel,
                                    "BLS Adjacent",
                                    its_ref_mos,
                                    its_fields,
                                )
                                if panel_feat:
                                    ofz_inner_trans_features.append(panel_feat)
                            else:
                                QgsMessageLog.logMessage(
                                    f"ITS BLS-Adjacent Panel {current_desig} {side_label_its_panel} SKIPPED: Missing 3D base points from BLS.",
                                    plugin_tag,
                                    Qgis.Warning,
                                )

                            if (
                                P_IA_inner_3d_side
                                and P_BLS_inner_3d_side
                                and ia_cl_start_xy
                                and bls_cl_start_xy
                            ):
                                strip_base_seg_3d = self._define_strip_edge_segment_3d(
                                    ia_cl_start_xy,
                                    bls_cl_start_xy,
                                    graded_strip_half_width,
                                    outward_projection_az_for_panel,
                                    primary_threshold_point,
                                    reciprocal_threshold_point,
                                    primary_thr_elev,
                                    reciprocal_thr_elev,
                                )
                                if strip_base_seg_3d:
                                    strip_p1_3d, strip_p2_3d = strip_base_seg_3d
                                    panel_feat = self._generate_its_panel_feature(
                                        strip_p1_3d,
                                        strip_p2_3d,
                                        its_slope,
                                        IHS_ELEVATION_AMSL,
                                        outward_projection_az_for_panel,
                                        runway_name,
                                        current_desig,
                                        side_label_its_panel,
                                        "Strip Adjacent",
                                        its_ref_mos,
                                        its_fields,
                                    )
                                    if panel_feat:
                                        ofz_inner_trans_features.append(panel_feat)
                                else:
                                    QgsMessageLog.logMessage(
                                        f"ITS Strip Panel {current_desig} {side_label_its_panel} SKIPPED: _define_strip_edge_segment_3d None.",
                                        plugin_tag,
                                        Qgis.Warning,
                                    )
                            else:
                                QgsMessageLog.logMessage(
                                    f"ITS Strip Panel {current_desig} {side_label_its_panel} SKIPPED: Missing required alignment points.",
                                    plugin_tag,
                                    Qgis.Warning,
                                )
                    else:
                        QgsMessageLog.logMessage(
                            f"ITS for {current_desig} SKIPPED: Invalid ITS slope.",
                            plugin_tag,
                            Qgis.Warning,
                        )
                else:
                    QgsMessageLog.logMessage(
                        f"ITS for {current_desig} SKIPPED: No ITS parameters found.",
                        plugin_tag,
                        Qgis.Info,
                    )
            else:
                QgsMessageLog.logMessage(
                    f"ITS for {current_desig} SKIPPED: IHS_ELEVATION_AMSL is None.",
                    plugin_tag,
                    Qgis.Warning,
                )

            # --- Main Approach ---
            try:
                QgsMessageLog.logMessage(
                    f"Debug MainApproach: Attempting for {current_desig}",
                    plugin_tag,
                    Qgis.Info,
                )
                app_sections, app_contours = self._generate_approach_surface(
                    runway_data,
                    rwy_params,
                    arc_num,
                    config["approach_type_str"],
                    config["landing_threshold_pt"],
                    config["approach_surface_outward_azimuth"],
                    current_desig,
                    config["landing_threshold_elev"],
                )
                if app_sections:
                    approach_poly_features.extend(app_sections)
                if app_contours:
                    approach_contour_features.extend(app_contours)
                QgsMessageLog.logMessage(
                    f"Debug MainApproach: Completed for {current_desig}. Sections: {len(app_sections)}, Contours: {len(app_contours)}",
                    plugin_tag,
                    Qgis.Info,
                )
            except Exception as e_app:
                QgsMessageLog.logMessage(
                    f"ERROR generating Main Approach for {current_desig}: {e_app}\n{traceback.format_exc()}",
                    plugin_tag,
                    Qgis.Critical,
                )

            # --- Take-off Climb Surface (TOCS) ---
            try:
                QgsMessageLog.logMessage(
                    f"Debug TOCS: Attempting for {current_desig}", plugin_tag, Qgis.Info
                )
                tocs_plane_origin_pt = config["tocs_departure_pavement_end_pt"]
                tocs_params_for_offset = ols_dimensions.get_ols_params(
                    arc_num, None, "TOCS"
                )
                origin_offset_param_val = 60.0
                if tocs_params_for_offset:
                    origin_offset_param_val = tocs_params_for_offset.get(
                        "origin_offset", 60.0
                    )

                if config["tocs_clearway_len_at_departure_end"] > 1e-6:
                    tocs_plane_origin_pt = tocs_plane_origin_pt.project(
                        config["tocs_clearway_len_at_departure_end"],
                        config["tocs_flight_path_azimuth"],
                    )
                else:
                    tocs_plane_origin_pt = tocs_plane_origin_pt.project(
                        origin_offset_param_val, config["tocs_flight_path_azimuth"]
                    )

                tocs_actual_start_elevation = None
                if tocs_plane_origin_pt:
                    tocs_actual_start_elevation = (
                        self._get_elevation_at_point_along_gradient(
                            tocs_plane_origin_pt,
                            primary_threshold_point,
                            reciprocal_threshold_point,
                            primary_thr_elev,
                            reciprocal_thr_elev,
                            QgsProject.instance().crs(),
                        )
                    )

                feat_tocs_local = None
                if (
                    tocs_actual_start_elevation is not None
                    and tocs_plane_origin_pt is not None
                ):
                    QgsMessageLog.logMessage(
                        f"  DEBUG TOCS for '{current_desig}': Plane Origin Pt: {tocs_plane_origin_pt.asWkt()}, Actual Start Elev: {tocs_actual_start_elevation:.2f}",
                        plugin_tag,
                        Qgis.Info,
                    )
                    tocs_feat, tocs_conts = self._generate_tocs(
                        runway_data,
                        rwy_params,
                        arc_num,
                        config["approach_type_str"],
                        config["tocs_departure_pavement_end_pt"],
                        config["tocs_clearway_len_at_departure_end"],
                        config["tocs_flight_path_azimuth"],
                        current_desig,
                        tocs_actual_start_elevation,
                    )
                    feat_tocs_local = tocs_feat
                    if tocs_feat:
                        tocs_poly_features.append(tocs_feat)
                    if tocs_conts:
                        tocs_contour_features.extend(tocs_conts)
                else:
                    QgsMessageLog.logMessage(
                        f"Debug TOCS: Skipped for {current_desig} due to missing origin point or elevation for TOCS plane.",
                        plugin_tag,
                        Qgis.Warning,
                    )
                QgsMessageLog.logMessage(
                    f"Debug TOCS: Completed for {current_desig}. Feature generated: {feat_tocs_local is not None}",
                    plugin_tag,
                    Qgis.Info,
                )
            except Exception as e_tocs:
                QgsMessageLog.logMessage(
                    f"ERROR generating TOCS for {current_desig}: {e_tocs}\n{traceback.format_exc()}",
                    plugin_tag,
                    Qgis.Critical,
                )

        # --- END OF LOOP for runway_end_configurations ---

        QgsMessageLog.logMessage(
            f"Debug ProcessGuidelineF: Finished processing LOOP for runway {runway_name}. Total BLS features: {len(ofz_bls_features)}, Total ITS features: {len(ofz_inner_trans_features)}",
            plugin_tag,
            Qgis.Info,
        )

        # --- Layer Creation ---
        target_ofz_group = ofz_group if ofz_group is not None else layer_group

        # Inner Approach Layer
        if inner_approach_features:
            fields = self._get_ols_fields("InnerApproach")
            descriptive_style_key = "OLS Inner Approach"  # Use the descriptive key
            if self._create_and_add_layer(
                "Polygon",
                f"OLS_InnerApproach_{runway_name.replace('/', '_')}",
                f"{self.tr('OLS')} Inner Approach {runway_name}",
                fields,
                inner_approach_features,
                target_ofz_group,
                descriptive_style_key,  # Pass the descriptive key
            ):
                overall_success = True

        # Inner Transitional Layer
        if ofz_inner_trans_features:
            fields = self._get_ols_fields("InnerTransitional")
            descriptive_style_key = "OLS Inner Transitional"  # Use the descriptive key
            if self._create_and_add_layer(
                "Polygon",
                f"OLS_InnerTransitional_{runway_name.replace('/', '_')}",
                f"{self.tr('OLS')} Inner Transitional {runway_name}",
                fields,
                ofz_inner_trans_features,
                target_ofz_group,
                descriptive_style_key,  # Pass the descriptive key
            ):
                overall_success = True

        # Logging for empty ITS on Precision Approach runways
        is_precision_runway = False
        if hasattr(ols_dimensions, "PRECISION_APPROACH_TYPES"):
            current_runway_type_abbrs = {
                ols_dimensions.get_runway_type_abbr(s.get("approach_type_str"))
                for s in runway_end_configurations
                if s.get("approach_type_str")
            }
            is_precision_runway = any(
                abbr in ols_dimensions.PRECISION_APPROACH_TYPES
                for abbr in current_runway_type_abbrs
            )
        else:
            QgsMessageLog.logMessage(
                "Warning: ols_dimensions.PRECISION_APPROACH_TYPES not found for ITS logging.",
                plugin_tag,
                Qgis.Warning,
            )

        if not ofz_inner_trans_features and is_precision_runway:
            QgsMessageLog.logMessage(
                f"Warning: Inner Transitional layer for PA runway {runway_name} is empty. Check ITS generation logic and data extraction.",
                plugin_tag,
                Qgis.Warning,
            )
        elif (
            not ofz_inner_trans_features
        ):  # General info if not a PA runway and still empty
            QgsMessageLog.logMessage(
                f"Info: Inner Transitional layer for {runway_name} is empty (may be normal for non-PA or if generation is placeholder).",
                plugin_tag,
                Qgis.Info,
            )

        # Baulked Landing Layer
        QgsMessageLog.logMessage(
            f"Debug BLS Layer Creation: Total ofz_bls_features count: {len(ofz_bls_features)} for runway {runway_name}",
            plugin_tag,
            Qgis.Info,
        )
        if ofz_bls_features:
            fields = self._get_ols_fields("BaulkedLanding")
            descriptive_style_key = "OLS Baulked Landing"  # Use the descriptive key
            QgsMessageLog.logMessage(
                f"Debug BLS Layer Creation: Attempting layer for {runway_name} with {len(ofz_bls_features)} features. Group: {target_ofz_group.name()}",
                plugin_tag,
                Qgis.Info,
            )
            bls_layer = self._create_and_add_layer(
                "Polygon",
                f"OLS_BaulkedLanding_{runway_name.replace('/', '_')}",
                f"{self.tr('OLS')} Baulked Landing {runway_name}",
                fields,
                ofz_bls_features,
                target_ofz_group,
                descriptive_style_key,  # Pass the descriptive key
            )
            if bls_layer:
                overall_success = True
                QgsMessageLog.logMessage(
                    f"Debug BLS Layer Creation: Layer '{bls_layer.name()}' created for {runway_name}.",
                    plugin_tag,
                    Qgis.Success,
                )
            else:
                QgsMessageLog.logMessage(
                    f"Debug BLS Layer Creation: _create_and_add_layer FAILED for BLS {runway_name}.",
                    plugin_tag,
                    Qgis.Critical,
                )
        else:
            QgsMessageLog.logMessage(
                f"Debug BLS Layer Creation: No features in ofz_bls_features list for {runway_name}. Layer not created.",
                plugin_tag,
                Qgis.Info,
            )

        # Approach Sections Layer
        if approach_poly_features:
            fields = self._get_ols_fields("Approach")
            descriptive_style_key = "OLS Approach"  # Use the descriptive key
            if self._create_and_add_layer(
                "Polygon",
                f"OLS_Approach_{runway_name.replace('/', '_')}",
                f"{self.tr('OLS')} Approach Sections {runway_name}",
                fields,
                approach_poly_features,
                layer_group,  # Main Approach usually goes in the general OLS group
                descriptive_style_key,  # Pass the descriptive key
            ):
                overall_success = True

        # Approach Contours Layer
        if approach_contour_features:
            fields = self._get_approach_contour_fields()
            descriptive_style_key = "OLS Approach Contour"  # Use the descriptive key
            if self._create_and_add_layer(
                "LineString",
                f"OLS_ApproachContours_{runway_name.replace('/', '_')}",
                f"{self.tr('OLS')} Approach Contours {runway_name}",
                fields,
                approach_contour_features,
                layer_group,
                descriptive_style_key,  # Pass the descriptive key
            ):
                overall_success = True

        # TOCS Polygons Layer
        if tocs_poly_features:
            fields = self._get_ols_fields("TOCS")
            descriptive_style_key = "OLS TOCS"  # Use the descriptive key
            if self._create_and_add_layer(
                "Polygon",
                f"OLS_TOCS_{runway_name.replace('/', '_')}",
                f"{self.tr('OLS')} TOCS {runway_name}",
                fields,
                tocs_poly_features,
                layer_group,
                descriptive_style_key,  # Pass the descriptive key
            ):
                overall_success = True

        # TOCS Contours Layer
        if tocs_contour_features:
            fields = self._get_tocs_contour_fields()
            descriptive_style_key = "OLS TOCS Contour"  # Use the descriptive key
            if self._create_and_add_layer(
                "LineString",
                f"OLS_TOCS_Contours_{runway_name.replace('/', '_')}",
                f"{self.tr('OLS')} TOCS Contours {runway_name}",
                fields,
                tocs_contour_features,
                layer_group,
                descriptive_style_key,  # Pass the descriptive key
            ):
                overall_success = True

        QgsMessageLog.logMessage(
            f"Finished Runway OLS processing for {runway_name}. Overall success for this runway: {overall_success}",
            plugin_tag,
            level=Qgis.Success if overall_success else Qgis.Warning,
        )
        return overall_success

    def process_guideline_g(
        self,
        cns_facilities_data: List[dict],
        icao_code: str,
        target_crs: QgsCoordinateReferenceSystem,
        layer_group: QgsLayerTreeGroup,
    ) -> bool:
        """Processes Guideline G: CNS Facilities BRAs using pre-validated data."""
        if not cns_facilities_data:
            QgsMessageLog.logMessage(
                "Guideline G skipped: No valid CNS facilities provided.",
                PLUGIN_TAG,
                level=Qgis.Info,
            )
            return False
        overall_success = False
        fields = QgsFields(
            [
                QgsField("sourcefacid", QVariant.String),
                QgsField("factype", QVariant.String),
                QgsField("surfname", QVariant.String),
                QgsField("reqheight", QVariant.Double),
                QgsField("guideline", QVariant.String),
                QgsField("shape", QVariant.String),
                QgsField("innerrad_m", QVariant.Double),
                QgsField("outerrad_m", QVariant.Double),
                QgsField("heightrule", QVariant.String),
            ]
        )

        for facility_data in cns_facilities_data:
            facility_id = facility_data.get("id", "N/A")
            facility_type = facility_data.get("type", "Unknown")
            facility_geom = facility_data.get("geom")
            facility_elev = facility_data.get("elevation")
            if not facility_geom or not facility_geom.isGeosValid():
                continue
            bra_specs_list = cns_dimensions.get_cns_spec(facility_type)
            if not bra_specs_list:
                continue

            for surface_spec in bra_specs_list:
                try:
                    surface_name = surface_spec.get("SurfaceName", "Unkn")
                    shape_type = surface_spec.get("shape", "Unkn").upper()
                    type_parts = facility_type.split("(")
                    fac_acronym = ""
                    if len(type_parts) > 1 and type_parts[1].strip().endswith(")"):
                        fac_acronym = type_parts[1].strip()[:-1].strip()
                    else:
                        predefined_acronyms = {
                            "NON-DIRECTIONAL BEACON": "NDB",
                            "VHF OMNI-DIRECTIONAL RANGE": "VOR",
                            "DISTANCE MEASURING EQUIPMENT": "DME",
                            "PRIMARY SURVEILLANCE RADAR": "PSR",
                            "SECONDARY SURVEILLANCE RADAR": "SSR",
                            "GROUND BASED AUGMENTATION SYSTEM": "GBAS",
                        }
                        fac_acronym = predefined_acronyms.get(
                            facility_type.upper(), facility_type.split(" ")[0]
                        )
                    layer_display_name = (
                        f"{fac_acronym} {surface_name}"
                        if fac_acronym
                        else f"{facility_type} {surface_name}"
                    )
                    fac_identifier = (
                        facility_id
                        if facility_id != "N/A"
                        else facility_type.replace(" ", "_")[:10]
                    )
                    internal_name_base = f"G_CNS_{icao_code}_{fac_identifier}_{surface_name.replace(' ', '_')}"
                    internal_name_base = "".join(
                        c if c.isalnum() else "_" for c in internal_name_base
                    )
                    surface_geom = self._generate_circular_or_donut(
                        facility_geom,
                        surface_spec,
                        f"{surface_name} for {facility_type} ID {facility_id}",
                    )
                    if not surface_geom:
                        continue
                    height_rule = surface_spec.get("heightrule", "TBD")
                    height_value = surface_spec.get("HeightValue")
                    req_height = self._calculate_cns_height(
                        facility_elev,
                        height_rule,
                        height_value,
                        surface_geom,
                        facility_geom,
                    )
                    feature = QgsFeature(fields)
                    feature.setGeometry(surface_geom)
                    feature.setAttributes(
                        [
                            facility_id,
                            facility_type,
                            surface_name,
                            req_height,
                            "G",
                            shape_type,
                            surface_spec.get("InnerRadius_m"),
                            surface_spec.get("OuterRadius_m"),
                            height_rule,
                        ]
                    )
                    if shape_type == "CIRCLE":
                        style_key = "CNS Circle Zone"
                    elif shape_type == "DONUT":
                        style_key = "CNS Donut Zone"
                    else:
                        style_key = "Default CNS"
                    layer_created = self._create_and_add_layer(
                        "Polygon",
                        internal_name_base,
                        layer_display_name,
                        fields,
                        [feature],
                        layer_group,
                        style_key,
                    )
                    if layer_created:
                        overall_success = True
                except Exception as e_spec:
                    QgsMessageLog.logMessage(
                        f"Error processing CNS surface '{surface_name}' for '{facility_type}': {e_spec}",
                        PLUGIN_TAG,
                        level=Qgis.Critical,
                    )

        if overall_success:
            QgsMessageLog.logMessage(
                f"Guideline G: Finished processing CNS.", PLUGIN_TAG, level=Qgis.Info
            )
        else:
            QgsMessageLog.logMessage(
                "Guideline G: No CNS layers generated or added.",
                PLUGIN_TAG,
                level=Qgis.Info,
            )
        return overall_success

    def _generate_circular_or_donut(
        self, facility_point_geom: QgsGeometry, surface_spec: dict, description: str
    ) -> Optional[QgsGeometry]:
        """Generates a QgsGeometry (Circle or Donut) based on the surface spec."""
        if (
            not facility_point_geom
            or not facility_point_geom.isGeosValid()
            or not facility_point_geom.wkbType()
            in [
                Qgis.WkbType.Point,
                Qgis.WkbType.PointZ,
                Qgis.WkbType.PointM,
                Qgis.WkbType.PointZM,
            ]
        ):
            return None
        shape = surface_spec.get("shape", "").upper()
        outer_radius = surface_spec.get("OuterRadius_m")
        inner_radius = surface_spec.get("InnerRadius_m", 0.0)
        if (
            outer_radius is None
            or not isinstance(outer_radius, (int, float))
            or outer_radius <= 0
        ):
            return None
        if (
            inner_radius is None
            or not isinstance(inner_radius, (int, float))
            or inner_radius < 0
        ):
            inner_radius = 0.0
        buffer_segments = 36
        outer_geom = facility_point_geom.buffer(outer_radius, buffer_segments)
        if not outer_geom or not outer_geom.isGeosValid():
            outer_geom = outer_geom.makeValid() if outer_geom else None
        if not outer_geom or not outer_geom.isGeosValid():
            QgsMessageLog.logMessage(
                f"Error: Invalid outer buffer {outer_radius}m for '{description}'.",
                PLUGIN_TAG,
                level=Qgis.Warning,
            )
            return None
        if shape == "CIRCLE":
            return outer_geom if inner_radius <= 1e-6 else None
        if shape == "DONUT":
            if inner_radius >= outer_radius:
                return None
            if inner_radius <= 1e-6:
                return outer_geom
            inner_geom = facility_point_geom.buffer(inner_radius, buffer_segments)
            if not inner_geom or not inner_geom.isGeosValid():
                inner_geom = inner_geom.makeValid() if inner_geom else None
            if not inner_geom or not inner_geom.isGeosValid():
                QgsMessageLog.logMessage(
                    f"Error: Invalid inner buffer {inner_radius}m for DONUT '{description}'.",
                    PLUGIN_TAG,
                    level=Qgis.Warning,
                )
                return None
            try:
                donut_geom = outer_geom.difference(inner_geom)
                if donut_geom and donut_geom.isGeosValid():
                    return donut_geom
                elif donut_geom:
                    fixed_donut = donut_geom.makeValid()
                    return (
                        fixed_donut
                        if fixed_donut and fixed_donut.isGeosValid()
                        else None
                    )
                else:
                    return None
            except Exception as e:
                QgsMessageLog.logMessage(
                    f"Error difference DONUT '{description}': {e}",
                    PLUGIN_TAG,
                    level=Qgis.Critical,
                )
                return None
        else:
            QgsMessageLog.logMessage(
                f"Warning: Unknown shape '{shape}' for '{description}'.",
                PLUGIN_TAG,
                level=Qgis.Warning,
            )
            return None

    def _calculate_cns_height(
        self,
        facility_elevation: Optional[float],
        rule: Optional[str],
        value: Any,
        geometry: QgsGeometry,
        facility_geom: QgsGeometry,
    ) -> Optional[float]:
        """Calculates the controlling height for the BRA surface. Placeholder."""
        if facility_elevation is None and rule in ["FacilityElevation + AGL", "Slope"]:
            return None
        try:
            if rule == "TBD" or rule is None:
                return facility_elevation
            elif rule == "FacilityElevation + AGL":
                return (
                    facility_elevation + float(value)
                    if value is not None
                    else facility_elevation
                )
            elif rule == "Fixed_AMSL":
                return float(value) if value is not None else None
            elif rule == "Slope":
                QgsMessageLog.logMessage(
                    f"Warning: Slope height rule '{rule}' not implemented.",
                    PLUGIN_TAG,
                    level=Qgis.Warning,
                )
                return facility_elevation
            else:
                QgsMessageLog.logMessage(
                    f"Warning: Unknown height rule '{rule}'.",
                    PLUGIN_TAG,
                    level=Qgis.Warning,
                )
                return None
        except (ValueError, TypeError, Exception) as e:
            QgsMessageLog.logMessage(
                f"Error calculating CNS height (Rule: {rule}, Val: {value}): {e}",
                PLUGIN_TAG,
                level=Qgis.Warning,
            )
            return None

    def process_guideline_i(
        self, runway_data: dict, layer_group: QgsLayerTreeGroup
    ) -> bool:
        """Processes Guideline I: Public Safety Area (PSA) Trapezoids."""
        runway_name = runway_data.get(
            "short_name", f"RWY_{runway_data.get('original_index','?')}"
        )
        thr_point = runway_data.get("thr_point")
        rec_thr_point = runway_data.get("rec_thr_point")
        if not all([thr_point, rec_thr_point, layer_group]):
            return False
        params = self._get_runway_parameters(thr_point, rec_thr_point)
        if params is None:
            return False
        psa_inner_half_w = GUIDELINE_I_PSA_INNER_WIDTH / 2.0
        psa_outer_half_w = GUIDELINE_I_PSA_OUTER_WIDTH / 2.0
        if psa_inner_half_w < 0 or psa_outer_half_w < 0:
            return False

        fields = QgsFields(
            [
                QgsField("rwy", QVariant.String),
                QgsField("desc", QVariant.String),
                QgsField("end_desig", QVariant.String),
                QgsField("len_m", QVariant.Double),
                QgsField("inner_width", QVariant.Double),
                QgsField("outer_width", QVariant.Double),
                QgsField("ref_mos", QVariant.String),
                QgsField("ref_nasf", QVariant.String),
            ]
        )
        features_to_add = []
        primary_desig, reciprocal_desig = (
            runway_name.split("/") if "/" in runway_name else ("Primary", "Reciprocal")
        )
        try:
            geom_p = self._create_trapezoid(
                thr_point,
                params["azimuth_r_p"],
                GUIDELINE_I_PSA_LENGTH,
                psa_inner_half_w,
                psa_outer_half_w,
                f"PSA {primary_desig}",
            )
            if geom_p:
                feat = QgsFeature(fields)
                feat.setGeometry(geom_p)
                feat.setAttributes(
                    [
                        runway_name,
                        f"Public Safety Area {primary_desig}",
                        primary_desig,
                        GUIDELINE_I_PSA_LENGTH,
                        GUIDELINE_I_PSA_INNER_WIDTH,
                        GUIDELINE_I_PSA_OUTER_WIDTH,
                        GUIDELINE_I_MOS_REF_VAL,
                        GUIDELINE_I_NASF_REF_VAL,
                    ]
                )
                features_to_add.append(feat)
        except Exception as e:
            QgsMessageLog.logMessage(
                f"Error PSA Primary {runway_name}: {e}", PLUGIN_TAG, level=Qgis.Warning
            )
        try:
            geom_r = self._create_trapezoid(
                rec_thr_point,
                params["azimuth_p_r"],
                GUIDELINE_I_PSA_LENGTH,
                psa_inner_half_w,
                psa_outer_half_w,
                f"PSA {reciprocal_desig}",
            )
            if geom_r:
                feat = QgsFeature(fields)
                feat.setGeometry(geom_r)
                feat.setAttributes(
                    [
                        runway_name,
                        f"Public Safety Area {reciprocal_desig}",
                        reciprocal_desig,
                        GUIDELINE_I_PSA_LENGTH,
                        GUIDELINE_I_PSA_INNER_WIDTH,
                        GUIDELINE_I_PSA_OUTER_WIDTH,
                        GUIDELINE_I_MOS_REF_VAL,
                        GUIDELINE_I_NASF_REF_VAL,
                    ]
                )
                features_to_add.append(feat)
        except Exception as e:
            QgsMessageLog.logMessage(
                f"Error PSA Reciprocal {runway_name}: {e}",
                PLUGIN_TAG,
                level=Qgis.Warning,
            )

        layer_created = self._create_and_add_layer(
            "Polygon",
            f"PSA_{runway_name.replace('/', '_')}",
            f"PSA {self.tr('RWY')} {runway_name}",
            fields,
            features_to_add,
            layer_group,
            "PSA Runway",
        )
        return layer_created is not None

    # ============================================================
    # Specialised Safeguarding Processing (e.g., RAOA)
    # ============================================================

    def _get_raoa_fields(self) -> QgsFields:
        """Returns the QgsFields definition for the RAOA layer."""
        fields = QgsFields(
            [
                QgsField("rwy", QVariant.String, self.tr("rwy"), 50),
                QgsField("desc", QVariant.String, self.tr("desc"), 50),
                QgsField("end_desig", QVariant.String, self.tr("end_desig"), 10),
                QgsField("len_m", QVariant.Double, self.tr("len_m"), 10, 2),
                QgsField("wid_m", QVariant.Double, self.tr("wid_m"), 10, 2),
                QgsField("ref_mos", QVariant.String, self.tr("MOS Reference"), 100),
            ]
        )
        return fields

    def process_raoa(self, runway_data: dict, layer_group: QgsLayerTreeGroup) -> bool:
        """Generates RAOA if applicable (Precision Approach runways)."""
        plugin_tag = PLUGIN_TAG
        runway_name = runway_data.get(
            "short_name", f"RWY_{runway_data.get('original_index','?')}"
        )
        thr_point = runway_data.get("thr_point")
        rec_thr_point = runway_data.get("rec_thr_point")
        type1_str = runway_data.get("type1", "")
        type2_str = runway_data.get("type2", "")

        if not all([thr_point, rec_thr_point, layer_group]):
            return False  # Basic check
        rwy_params = self._get_runway_parameters(thr_point, rec_thr_point)
        if rwy_params is None:
            return False  # Helper logs error

        RAOA_LENGTH = 300.0
        RAOA_WIDTH = 120.0
        RAOA_HALF_WIDTH = RAOA_WIDTH / 2.0
        APPLICABLE_TYPES = ["Precision Approach CAT I", "Precision Approach CAT II/III"]
        features_to_add: List[QgsFeature] = []
        primary_desig, reciprocal_desig = (
            runway_name.split("/") if "/" in runway_name else ("THR1", "THR2")
        )

        # Check Primary End
        if type1_str in APPLICABLE_TYPES:
            try:
                outward_azimuth = rwy_params["azimuth_r_p"]
                geom = self._create_rectangle_from_start(
                    thr_point,
                    outward_azimuth,
                    RAOA_LENGTH,
                    RAOA_HALF_WIDTH,
                    f"RAOA {primary_desig}",
                )
                if geom:
                    fields = self._get_raoa_fields()
                    feature = QgsFeature(fields)
                    feature.setGeometry(geom)
                    attributes = [
                        runway_name,
                        f"RAOA {primary_desig}",
                        primary_desig,
                        RAOA_LENGTH,
                        RAOA_WIDTH,
                        RAOA_MOS_REF_VAL,
                    ]
                    feature.setAttributes(attributes)
                    features_to_add.append(feature)
            except Exception as e:
                QgsMessageLog.logMessage(
                    f"Warning: Error generating RAOA for {primary_desig}: {e}",
                    plugin_tag,
                    level=Qgis.Warning,
                )

        # Check Reciprocal End
        if type2_str in APPLICABLE_TYPES:
            try:
                outward_azimuth = rwy_params["azimuth_p_r"]
                geom = self._create_rectangle_from_start(
                    rec_thr_point,
                    outward_azimuth,
                    RAOA_LENGTH,
                    RAOA_HALF_WIDTH,
                    f"RAOA {reciprocal_desig}",
                )
                if geom:
                    fields = self._get_raoa_fields()
                    feature = QgsFeature(fields)
                    feature.setGeometry(geom)
                    attributes = [
                        runway_name,
                        f"RAOA {reciprocal_desig}",
                        reciprocal_desig,
                        RAOA_LENGTH,
                        RAOA_WIDTH,
                        RAOA_MOS_REF_VAL,
                    ]
                    feature.setAttributes(attributes)
                    features_to_add.append(feature)
            except Exception as e:
                QgsMessageLog.logMessage(
                    f"Warning: Error generating RAOA for {reciprocal_desig}: {e}",
                    plugin_tag,
                    level=Qgis.Warning,
                )

        # Create Layer if Features Exist
        if features_to_add:
            layer_name_display = f"RAOA {runway_name}"
            internal_name_base = f"RAOA_{runway_name.replace('/', '_')}"
            fields = self._get_raoa_fields()
            style_key = "RAOA"  # Ensure this matches style_map
            layer_created = self._create_and_add_layer(
                "Polygon",
                internal_name_base,
                layer_name_display,
                fields,
                features_to_add,
                layer_group,
                style_key,
            )
            # No final success log needed here, helper logs errors.
            return layer_created is not None
        else:
            # Keep this Info log - useful to know why layer wasn't created
            QgsMessageLog.logMessage(
                f"RAOA not applicable or failed for {runway_name}",
                plugin_tag,
                level=Qgis.Info,
            )
            return False

    def _get_taxiway_separation_fields(self) -> QgsFields:
        """Returns the QgsFields definition for the Taxiway Separation layer."""
        fields = QgsFields(
            [
                QgsField("rwy", QVariant.String, self.tr("Runway Name"), 50),
                QgsField(
                    "desc", QVariant.String, self.tr("desc"), 100
                ),
                QgsField("offset_m", QVariant.Double, self.tr("offset_m"), 10, 2),
                QgsField(
                    "ref_mos", QVariant.String, self.tr("MOS Reference"), 100
                ),
                QgsField(
                    "appr_type", QVariant.String, self.tr("appr_type"), 50
                ),
                QgsField(
                    "arc_num", QVariant.String, self.tr("arc_num"), 5
                ),
                QgsField(
                    "arc_let", QVariant.String, self.tr("arc_let"), 5
                ),
                QgsField("side", QVariant.String, self.tr("Side (L/R)"), 5),
            ]
        )
        return fields

    def process_taxiway_separation(
        self, runway_data: dict, layer_group: QgsLayerTreeGroup
    ) -> bool:
        """Generates Taxiway Minimum Separation lines."""
        plugin_tag = PLUGIN_TAG
        runway_name = runway_data.get(
            "short_name", f"RWY_{runway_data.get('original_index','?')}"
        )
        thr_point = runway_data.get("thr_point")
        rec_thr_point = runway_data.get("rec_thr_point")
        arc_num_str = runway_data.get("arc_num")
        arc_let_raw = runway_data.get("arc_let")
        type1_str = runway_data.get("type1", "")
        type2_str = runway_data.get("type2", "")

        # Essential Checks
        if not all([thr_point, rec_thr_point, layer_group, arc_num_str]):
            QgsMessageLog.logMessage(
                f"Taxiway Sep skipped {runway_name}: Missing essential data.",
                plugin_tag,
                level=Qgis.Warning,
            )
            return False
        try:
            arc_num = int(
                arc_num_str
            )  # Keep as int for logic, convert to str for attribute
        except (ValueError, TypeError):
            QgsMessageLog.logMessage(
                f"Taxiway Sep skipped {runway_name}: Invalid ARC Number '{arc_num_str}'.",
                plugin_tag,
                level=Qgis.Warning,
            )
            return False

        # Validate ARC Letter
        if (
            not arc_let_raw
            or not isinstance(arc_let_raw, str)
            or not arc_let_raw.strip()
        ):
            QgsMessageLog.logMessage(
                f"Taxiway Sep skipped {runway_name}: ARC Letter not provided or invalid ('{arc_let_raw}').",
                plugin_tag,
                level=Qgis.Warning,
            )
            return False
        arc_let = arc_let_raw.strip().upper()  # Use cleaned letter

        rwy_params = self._get_runway_parameters(thr_point, rec_thr_point)
        if (
            rwy_params is None
            or rwy_params.get("length") is None
            or rwy_params["length"] <= 0
        ):
            QgsMessageLog.logMessage(
                f"Taxiway Sep skipped {runway_name}: Invalid runway parameters or length.",
                plugin_tag,
                level=Qgis.Warning,
            )
            return False

        # Determine Governing Type (keep logic)
        type_order = [
            "",
            "Non-Instrument (NI)",
            "Non-Precision Approach (NPA)",
            "Precision Approach CAT I",
            "Precision Approach CAT II/III",
        ]
        idx1 = type_order.index(type1_str) if type1_str in type_order else 1
        idx2 = type_order.index(type2_str) if type2_str in type_order else 1
        governing_type_str = type_order[max(idx1, idx2)]

        # Get Offset Parameter
        offset_params = ols_dimensions.get_taxiway_separation_offset(
            arc_num, arc_let, governing_type_str
        )
        if not offset_params:
            QgsMessageLog.logMessage(
                f"Skipping Taxiway Sep for {runway_name}: No offset parameters found for classification (ARC={arc_num}, Let='{arc_let}', Type='{governing_type_str}').",
                plugin_tag,
                level=Qgis.Warning,
            )
            return False
        offset_m = offset_params.get("offset_m")
        if offset_m is None or offset_m <= 0:
            QgsMessageLog.logMessage(
                f"Skipping Taxiway Sep for {runway_name}: Invalid offset value ({offset_m}).",
                plugin_tag,
                level=Qgis.Warning,
            )
            return False

        # Calculate Geometry (keep logic)
        runway_length = rwy_params["length"]
        line_length = runway_length * 1.5
        extension = (line_length - runway_length) / 2.0
        line_start_cl = thr_point.project(extension, rwy_params["azimuth_r_p"])
        line_end_cl = line_start_cl.project(line_length, rwy_params["azimuth_p_r"])
        if not line_start_cl or not line_end_cl:
            QgsMessageLog.logMessage(
                f"Failed calc taxiway sep line start/end points for {runway_name}",
                plugin_tag,
                level=Qgis.Warning,
            )
            return False

        features_to_add: List[QgsFeature] = []
        geom_ok = True
        surface_description = f"Minimum Taxiway Separation {runway_name}"
        # Left Line
        try:
            pt_start_l = line_start_cl.project(offset_m, rwy_params["azimuth_perp_l"])
            pt_end_l = line_end_cl.project(offset_m, rwy_params["azimuth_perp_l"])
            if pt_start_l and pt_end_l:
                geom_l = QgsGeometry.fromPolylineXY([pt_start_l, pt_end_l])
                if geom_l and not geom_l.isEmpty():
                    fields = self._get_taxiway_separation_fields()
                    feat_l = QgsFeature(fields)
                    feat_l.setGeometry(geom_l)

                    # Defensively prepare variables for attr_map
                    attr_runway_name = (
                        runway_name if runway_name and runway_name.strip() else "N/A"
                    )
                    attr_surface_description = (
                        surface_description
                        if surface_description and surface_description.strip()
                        else "N/A"
                    )
                    # offset_m is confirmed to be a valid float by prior checks
                    attr_mos_ref = (
                        MOS_REF_TAXIWAY_SEPARATION  # This is a module-level constant
                    )
                    attr_app_type = (
                        governing_type_str
                        if governing_type_str and governing_type_str.strip()
                        else "N/A"
                    )
                    attr_arc_num_str = str(arc_num)  # arc_num is an int, str() is safe
                    attr_arc_let = arc_let if arc_let and arc_let.strip() else "N/A"

                    attr_map = {
                        "rwy": attr_runway_name,
                        "desc": attr_surface_description,
                        "offset_m": offset_m,
                        "ref_mos": attr_mos_ref,
                        "appr_type": attr_app_type,
                        "arc_num": attr_arc_num_str,
                        "arc_let": attr_arc_let,
                        "side": "L",
                    }
                    # QgsMessageLog.logMessage(f"Taxiway Sep Left Attr Map for {runway_name}: {attr_map}", plugin_tag, level=Qgis.Info)

                    for name, value in attr_map.items():
                        idx = fields.indexFromName(name)
                        if idx != -1:
                            feat_l.setAttribute(idx, value)
                        else:
                            QgsMessageLog.logMessage(
                                f"Warning: Field '{name}' not found in layer for Taxiway Separation (Left Line).",
                                plugin_tag,
                                level=Qgis.Warning,
                            )
                    features_to_add.append(feat_l)
                else:
                    geom_ok = False
            else:
                geom_ok = False
        except Exception as e:
            geom_ok = False
            QgsMessageLog.logMessage(
                f"Warning: Error generating Left Taxi Sep line for {runway_name}: {e}\n{traceback.format_exc()}",
                plugin_tag,
                level=Qgis.Warning,
            )

        # Right Line (similar try-except block and attribute setting)
        try:
            pt_start_r = line_start_cl.project(offset_m, rwy_params["azimuth_perp_r"])
            pt_end_r = line_end_cl.project(offset_m, rwy_params["azimuth_perp_r"])
            if pt_start_r and pt_end_r:
                geom_r = QgsGeometry.fromPolylineXY([pt_start_r, pt_end_r])
                if geom_r and not geom_r.isEmpty():
                    fields = self._get_taxiway_separation_fields()
                    feat_r = QgsFeature(fields)
                    feat_r.setGeometry(geom_r)

                    # Reuse defensively prepared variables from the Left Line section as they are identical for the Right Line
                    attr_map_right = {
                        "rwy": attr_runway_name,
                        "desc": attr_surface_description,
                        "offset_m": offset_m,
                        "ref_mos": attr_mos_ref,
                        "appr_type": attr_app_type,
                        "arc_num": attr_arc_num_str,
                        "arc_let": attr_arc_let,
                        "side": "R",
                    }
                    # QgsMessageLog.logMessage(f"Taxiway Sep Right Attr Map for {runway_name}: {attr_map_right}", plugin_tag, level=Qgis.Info)

                    for name, value in attr_map_right.items():
                        idx = fields.indexFromName(name)
                        if idx != -1:
                            feat_r.setAttribute(idx, value)
                        else:
                            QgsMessageLog.logMessage(
                                f"Warning: Field '{name}' not found in layer for Taxiway Separation (Right Line).",
                                plugin_tag,
                                level=Qgis.Warning,
                            )
                    features_to_add.append(feat_r)
                else:
                    geom_ok = False
            else:
                geom_ok = False
        except Exception as e:
            geom_ok = False
            QgsMessageLog.logMessage(
                f"Warning: Error generating Right Taxi Sep line for {runway_name}: {e}\n{traceback.format_exc()}",
                plugin_tag,
                level=Qgis.Warning,
            )

        if (
            not geom_ok and not features_to_add
        ):  # If geometry failed AND no features were added
            QgsMessageLog.logMessage(
                f"Failed to generate taxiway separation line geometries for {runway_name}",
                plugin_tag,
                level=Qgis.Warning,
            )
            return False

        # Create Layer
        if features_to_add:
            layer_name_display = f"Taxiway Separation {runway_name}"
            internal_name_base = f"TaxiwaySep_{runway_name.replace('/', '_')}"
            fields = self._get_taxiway_separation_fields()
            style_key = "Taxiway Separation Line"
            layer_created = self._create_and_add_layer(
                "LineString",
                internal_name_base,
                layer_name_display,
                fields,
                features_to_add,
                layer_group,
                style_key,
            )
            return layer_created is not None
        else:
            return False


# ============================================================
# End of Plugin Class
# ============================================================
