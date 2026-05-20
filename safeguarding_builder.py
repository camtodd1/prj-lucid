# -*- coding: utf-8 -*-
# safeguarding_builder.py

import os.path
import math
import traceback

# import functools # Not used directly
from typing import Dict, Optional, List, Any, Tuple

# --- Qt Imports ---
from qgis.PyQt.QtCore import QSettings, QTranslator, QCoreApplication, QVariant  # type: ignore
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
    QgsLayerTreeGroup,
    QgsLayerTreeLayer,
    QgsLayerTreeNode,
    QgsMessageLog,
    Qgis,
    QgsCoordinateReferenceSystem,
)

# --- Local Imports ---
from .core.layers import LayerMixin
from .core.styles import DEFAULT_STYLE_MAP
from .surfaces.physical import PhysicalGeometryMixin
from .surfaces.specialised import SpecialisedSurfacesMixin
from .surfaces.met import MetSurfacesMixin
from .guidelines.simple import SimpleGuidelinesMixin
from .guidelines.lighting import LightingGuidelineMixin
from .guidelines.ols import OlsGuidelineMixin
from .reports.runway_summary import build_runway_summaries, render_markdown_report


try:
    # Attempt to import generated resources
    from . import resources_rc

    resources_rc.qInitResources
except ImportError:
    # Fallback message if resources haven't been compiled
    print("Note: resources_rc.py not found or generated. Icons might be missing.")
# Import the dialog class
from .safeguarding_builder_dialog import SafeguardingBuilderDialog

# Plugin-specific constant for logging
PLUGIN_TAG = "SafeguardingBuilder"

# ============================================================
# Main Plugin Class - SafeguardingBuilder
# ============================================================
class SafeguardingBuilder(
    SimpleGuidelinesMixin,
    LightingGuidelineMixin,
    OlsGuidelineMixin,
    PhysicalGeometryMixin,
    SpecialisedSurfacesMixin,
    MetSurfacesMixin,
    LayerMixin,
):
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
        self.debug_logging: bool = False

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

    def _log(self, message: str, level=Qgis.Info, notify_user: bool = False):
        """Log plugin messages with QGIS 3/4 compatible notification hints."""
        try:
            QgsMessageLog.logMessage(
                message,
                PLUGIN_TAG,
                level=level,
                notifyUser=notify_user,
            )
        except TypeError:
            QgsMessageLog.logMessage(message, PLUGIN_TAG, level=level)

    def _log_success(self, message: str, notify_user: bool = False):
        self._log(message, Qgis.Success, notify_user)

    def _log_warning(self, message: str, notify_user: bool = True):
        self._log(message, Qgis.Warning, notify_user)

    def _log_critical(self, message: str, notify_user: bool = True):
        self._log(message, Qgis.Critical, notify_user)

    def _log_debug(self, message: str):
        if self.debug_logging:
            self._log(message, Qgis.Info, notify_user=False)

    def _crs_is_geographic(self, crs: QgsCoordinateReferenceSystem) -> bool:
        """Return True when a CRS uses angular units and is unsuitable for metre buffers."""
        try:
            return bool(crs.isGeographic())
        except Exception:
            return False

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
                    self.tr("Could not create dialog:\n\n{error}\n\nCheck logs for the full traceback.").format(
                        error=e
                    ),
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
        reference_elevation_datum = math.floor(reference_elevation_unrounded * 2) / 2.0

        # reference_elevation_datum = reference_elevation_unrounded

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
        self._log("Started safeguarding generation.")

        self.successfully_generated_layers = []
        self.reference_elevation_datum = None
        self.arp_elevation_amsl = None
        self.output_mode = "memory"
        self.output_path = None
        self.output_format_driver = None
        self.output_format_extension = None
        self.dissolve_output = False

        if self.dlg is None:
            self._log_critical("Processing aborted: dialog reference missing.")
            return

        project = QgsProject.instance()
        target_crs = project.crs()
        target_crs_authid = target_crs.authid()
        if not target_crs or not target_crs.isValid():
            self._log_critical("Processing aborted: project CRS is invalid or not set.")
            self.iface.messageBar().pushMessage(
                self.tr("Error"),
                self.tr(
                    "Project CRS is invalid or not set. Please set a valid Projected CRS."
                ),
                level=Qgis.Critical,
                duration=10,
            )
            return

        if self._crs_is_geographic(target_crs):
            crs_msg = (
                f"Processing aborted: project CRS {target_crs_authid} "
                f"({target_crs.description()}) is geographic. "
                "Safeguarding surfaces use metre distances; set a projected CRS."
            )
            self._log_critical(crs_msg)
            self.iface.messageBar().pushMessage(
                self.tr("Error"),
                self.tr(
                    "Project CRS is geographic. Set a projected CRS in metres before generating safeguarding surfaces."
                ),
                level=Qgis.Critical,
                duration=12,
            )
            return

        self._log(f"Project CRS: {target_crs_authid} ({target_crs.description()}).")

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
                self._log_warning(
                    "Processing aborted: input validation failed. Check the dialog and preceding messages."
                )
                return
        except Exception as e:
            self._log_critical(
                f"Processing aborted: failed to read input data: {e}\n{traceback.format_exc()}"
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

        icao_code = input_data.get("icao_code", "UNKNOWN")
        arp_point = input_data.get("arp_point")
        arp_east = input_data.get("arp_easting")
        arp_north = input_data.get("arp_northing")
        met_point = input_data.get("met_point")
        runway_input_list = input_data.get("runways", [])
        cns_input_list = input_data.get("cns_facilities", [])
        self.arp_elevation_amsl = input_data.get("arp_elevation")

        output_desc = (
            "memory"
            if self.output_mode == "memory"
            else f"{self.output_format_driver or 'file'} -> {self.output_path or 'N/A'}"
        )
        self._log(
            f"Inputs: ICAO={icao_code}, output={output_desc}, "
            f"ARP={'yes' if arp_point is not None else 'no'}, "
            f"MET={'yes' if met_point is not None else 'no'}, "
            f"CNS={len(cns_input_list)}, runways={len(runway_input_list)}."
        )

        if not runway_input_list:
            self._log_warning("Processing aborted: no valid runway data found.")
            self.iface.messageBar().pushMessage(
                self.tr("Warning"),
                self.tr("No valid runway data found after validation."),
                level=Qgis.Warning,
                duration=5,
            )

        if runway_input_list:
            self.style_map = dict(DEFAULT_STYLE_MAP)

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
            if arp_point is not None:
                arp_layer = self.create_arp_layer(
                    arp_point,
                    arp_east,
                    arp_north,
                    icao_code,
                    target_crs,
                    main_group,
                    self.arp_elevation_amsl,
                )
                if arp_layer is not None:
                    arp_layer_created = True
                if self.arp_elevation_amsl is None and arp_layer is not None:
                    fetched_elev = self._try_get_arp_elevation_from_layer(arp_layer)
                    if fetched_elev is not None:
                        QgsMessageLog.logMessage(
                            f"Note: ARP Elevation ({fetched_elev:.2f}m) found on layer after RED calculation might have failed.",
                            plugin_tag,
                            level=Qgis.Warning,
                        )

            met_layers_created_ok = False
            if met_point is not None:
                met_group = main_group.addGroup(
                    self.tr("Meteorological Instrument Station")
                )
                if met_group is not None:
                    self._stage_layer_tree_node(met_group)
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
                self._log(
                    "MET skipped: no MET coordinates provided; MET station surfaces not generated."
                )

            processed_runway_data_list, any_runway_base_data_ok = (
                self._process_runways_part1(
                    main_group, project, target_crs, icao_code, runway_input_list
                )
            )

            if any_runway_base_data_ok:
                for rwy_data in processed_runway_data_list:
                    cl_layer = rwy_data.get("centreline_layer")
                    if cl_layer is not None:
                        self._apply_style(cl_layer, self.style_map)

            (
                specialised_safeguarding_group,
                any_physical_or_protection_ok,
            ) = self._process_physical_and_protection_layers(
                main_group,
                icao_code,
                processed_runway_data_list,
                any_runway_base_data_ok,
            )

            guideline_groups = self._create_guideline_groups(main_group)

            ofz_group = None
            if guideline_groups.get("F") is not None:
                ofz_group = guideline_groups["F"].addGroup(
                    self.tr("OLS Obstacle Free Zone")
                )
                self._stage_layer_tree_node(ofz_group)

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

            (
                guideline_c_processed,
                guideline_d_processed,
                guideline_g_processed,
            ) = self._process_airport_guidelines(
                arp_point,
                cns_input_list,
                icao_code,
                target_crs,
                guideline_groups,
            )

            any_guideline_processed_ok = self._process_runways_part2(
                processed_runway_data_list,
                guideline_groups,
                specialised_safeguarding_group,
                ofz_group,
            )

            any_guideline_processed_ok = self._process_airport_wide_ols_if_possible(
                guideline_groups,
                processed_runway_data_list,
                icao_code,
                any_guideline_processed_ok,
            )

            self._write_runway_summary_report(icao_code, processed_runway_data_list)

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

            self._log("Finished safeguarding generation.")

            if self.successfully_generated_layers:
                if self.dlg:
                    self.dlg.accept()
            else:
                pass

    # ============================================================
    # Helper Methods
    # ============================================================



    def _process_airport_guidelines(
        self,
        arp_point: Optional[QgsPointXY],
        cns_input_list: List[dict],
        icao_code: str,
        target_crs: QgsCoordinateReferenceSystem,
        guideline_groups: Dict[str, Optional[QgsLayerTreeGroup]],
    ) -> Tuple[bool, bool, bool]:
        plugin_tag = PLUGIN_TAG
        guideline_c_processed = False
        guideline_d_processed = False
        guideline_g_processed = False
        if arp_point is not None and guideline_groups.get("C") is not None:
            self._log(
                f"Guideline C Wildlife: generating from ARP ({arp_point.x():.3f}, {arp_point.y():.3f})."
            )
            guideline_c_processed = self.process_guideline_c(
                arp_point, icao_code, target_crs, guideline_groups["C"]
            )
            if not guideline_c_processed:
                self._log_warning(
                    "Guideline C Wildlife failed: no zone layers were created. Check preceding Wildlife messages."
                )
        elif arp_point is None and guideline_groups.get("C") is not None:
            self._log(
                "Guideline C Wildlife skipped: ARP coordinates missing; wildlife zones not generated."
            )

        if arp_point is not None and guideline_groups.get("D") is not None:
            guideline_d_processed = self.process_guideline_d(
                arp_point, icao_code, target_crs, guideline_groups["D"]
            )
        elif arp_point is None and guideline_groups.get("D") is not None:
            self._log(
                "Guideline D Wind Turbine skipped: ARP coordinates missing; turbine zone not generated."
            )

        if cns_input_list and guideline_groups.get("G") is not None:
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

        return guideline_c_processed, guideline_d_processed, guideline_g_processed

    def _process_airport_wide_ols_if_possible(
        self,
        guideline_groups: Dict[str, Optional[QgsLayerTreeGroup]],
        processed_runway_data_list: List[dict],
        icao_code: str,
        any_guideline_processed_ok: bool,
    ) -> bool:
        plugin_tag = PLUGIN_TAG
        airport_wide_ols_processed = False
        if guideline_groups.get("F") is not None and processed_runway_data_list:
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

        return any_guideline_processed_ok

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
                runway_data["declared_distances"] = (
                    self._calculate_declared_distances(runway_data)
                )
                runway_data["generated_feature_counts"] = {
                    **runway_data.get("generated_feature_counts", {}),
                    "DeclaredDistance": len(runway_data.get("declared_distances") or []),
                }

                centreline_layer = self.create_runway_centreline_layer(
                    thr_point,
                    rec_thr_point,
                    short_runway_name,
                    target_crs,
                    main_group,
                    arc_num_val,
                    arc_let_val,
                    runway_data.get("declared_distances"),
                )

                # Check the result from the helper
                if centreline_layer is not None:
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

    def _write_runway_summary_report(
        self, icao_code: str, processed_runway_data_list: List[Dict[str, Any]]
    ) -> Optional[str]:
        """Write the Critical Runway Information Summary Markdown report."""
        if not processed_runway_data_list:
            self._log("Runway summary report skipped: no processed runway data.")
            return None
        if self.output_mode != "file":
            self._log(
                "Runway summary report not written: select file output to create the Markdown report."
            )
            return None
        if not self.output_path:
            self._log_warning(
                "Runway summary report skipped: file output path is not available."
            )
            return None

        safe_icao = self._sanitize_filename(icao_code or "UNKNOWN")
        report_path = os.path.join(
            self.output_path, f"{safe_icao}_Critical_Runway_Information_Summary.md"
        )
        try:
            summaries = build_runway_summaries(processed_runway_data_list)
            markdown = render_markdown_report(icao_code, None, summaries)
            with open(report_path, "w", encoding="utf-8") as report_file:
                report_file.write(markdown)
            self._log_success(f"Runway summary report written to '{report_path}'.")
            return report_path
        except Exception as e:
            self._log_warning(
                f"Runway summary report failed: {e}\n{traceback.format_exc()}"
            )
            return None

    def _calculate_declared_distances(
        self, runway_data: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Calculate baseline declared distances for both runway directions."""
        runway_name = runway_data.get(
            "short_name", f"RWY_{runway_data.get('original_index', '?')}"
        )
        thr_point = runway_data.get("thr_point")
        rec_thr_point = runway_data.get("rec_thr_point")
        if thr_point is None or rec_thr_point is None:
            return []

        rwy_params = self._get_runway_parameters(thr_point, rec_thr_point)
        if rwy_params is None:
            return []

        disp_primary = self._non_negative_float(
            runway_data.get("thr_displaced_1"), 0.0
        )
        disp_reciprocal = self._non_negative_float(
            runway_data.get("thr_displaced_2"), 0.0
        )
        physical_endpoints = self._get_physical_runway_endpoints(
            thr_point, rec_thr_point, disp_primary, disp_reciprocal, rwy_params
        )
        if physical_endpoints is None:
            return []

        _, _, physical_length = physical_endpoints
        threshold_length = rwy_params.get("length")
        if physical_length is None or threshold_length is None:
            return []

        if "/" in runway_name:
            primary_desig, reciprocal_desig = runway_name.split("/", 1)
        else:
            primary_desig = runway_name
            reciprocal_desig = "Reciprocal"

        clearway_primary_end = self._non_negative_float(
            runway_data.get("clearway1_len"), 0.0
        )
        clearway_reciprocal_end = self._non_negative_float(
            runway_data.get("clearway2_len"), 0.0
        )
        stopway_primary_end = self._non_negative_float(
            runway_data.get("stopway1_len"), 0.0
        )
        stopway_reciprocal_end = self._non_negative_float(
            runway_data.get("stopway2_len"), 0.0
        )

        primary_takeoff_available = self._bool_from_runway_data(
            runway_data.get("takeoff_available_1", True)
        )
        reciprocal_takeoff_available = self._bool_from_runway_data(
            runway_data.get("takeoff_available_2", True)
        )
        primary_landing_available = self._bool_from_runway_data(
            runway_data.get("landing_available_1", True)
        )
        reciprocal_landing_available = self._bool_from_runway_data(
            runway_data.get("landing_available_2", True)
        )

        primary_tora = physical_length if primary_takeoff_available else None
        reciprocal_tora = physical_length if reciprocal_takeoff_available else None
        primary_lda = (
            threshold_length + disp_reciprocal
            if primary_landing_available
            else None
        )
        reciprocal_lda = (
            threshold_length + disp_primary
            if reciprocal_landing_available
            else None
        )

        return [
            {
                "rwy": runway_name,
                "end_desig": primary_desig,
                "direction": "primary",
                "point": thr_point,
                "bearing_deg": rwy_params.get("azimuth_p_r"),
                "physical_len_m": physical_length,
                "threshold_len_m": threshold_length,
                "disp_thr_m": disp_primary,
                "clearway_m": clearway_reciprocal_end,
                "stopway_m": stopway_reciprocal_end,
                "takeoff_available": primary_takeoff_available,
                "landing_available": primary_landing_available,
                "tora_m": primary_tora,
                "toda_m": (
                    primary_tora + clearway_reciprocal_end
                    if primary_tora is not None
                    else None
                ),
                "asda_m": (
                    primary_tora + stopway_reciprocal_end
                    if primary_tora is not None
                    else None
                ),
                "lda_m": primary_lda,
            },
            {
                "rwy": runway_name,
                "end_desig": reciprocal_desig,
                "direction": "reciprocal",
                "point": rec_thr_point,
                "bearing_deg": rwy_params.get("azimuth_r_p"),
                "physical_len_m": physical_length,
                "threshold_len_m": threshold_length,
                "disp_thr_m": disp_reciprocal,
                "clearway_m": clearway_primary_end,
                "stopway_m": stopway_primary_end,
                "takeoff_available": reciprocal_takeoff_available,
                "landing_available": reciprocal_landing_available,
                "tora_m": reciprocal_tora,
                "toda_m": (
                    reciprocal_tora + clearway_primary_end
                    if reciprocal_tora is not None
                    else None
                ),
                "asda_m": (
                    reciprocal_tora + stopway_primary_end
                    if reciprocal_tora is not None
                    else None
                ),
                "lda_m": reciprocal_lda,
            },
        ]

    def _non_negative_float(self, value: Any, default: float = 0.0) -> float:
        try:
            parsed = float(value)
            return parsed if parsed >= 0 else default
        except (TypeError, ValueError):
            return default

    def _bool_from_runway_data(self, value: Any) -> bool:
        if isinstance(value, bool):
            return value
        if value is None:
            return True
        return str(value).strip().lower() not in {"0", "false", "no", "off"}

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
            if grp is None:
                QgsMessageLog.logMessage(
                    f"Failed create group: {name}", PLUGIN_TAG, level=Qgis.Warning
                )
            else:
                self._stage_layer_tree_node(grp)
        return guideline_groups

    def _ensure_valid_geometry(
        self, geom: Optional[QgsGeometry], description: str
    ) -> Optional[QgsGeometry]:
        """Return a valid non-empty geometry, only calling makeValid when needed."""
        if geom is None or geom.isEmpty():
            return None
        try:
            if geom.isGeosValid():
                return geom
            fixed_geom = geom.makeValid()
            if (
                fixed_geom is not None
                and not fixed_geom.isEmpty()
                and fixed_geom.isGeosValid()
            ):
                return fixed_geom
        except Exception as e:
            QgsMessageLog.logMessage(
                f"Warning: Geometry validation failed for {description}: {e}",
                PLUGIN_TAG,
                level=Qgis.Warning,
            )
            return None

        QgsMessageLog.logMessage(
            f"Warning: Geometry invalid after makeValid for {description}.",
            PLUGIN_TAG,
            level=Qgis.Warning,
        )
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
                if guideline_groups.get("B") is not None:
                    run_success_flags.append(
                        self.process_guideline_b(runway_data, guideline_groups["B"])
                    )
                if guideline_groups.get("E") is not None:
                    run_success_flags.append(
                        self.process_guideline_e(runway_data, guideline_groups["E"])
                    )
                if guideline_groups.get("F") is not None:
                    run_success_flags.append(
                        self.process_guideline_f(
                            runway_data, guideline_groups["F"], ofz_group
                        )
                    )  # F = OLS App/TOCS
                if guideline_groups.get("I") is not None:
                    run_success_flags.append(
                        self.process_guideline_i(runway_data, guideline_groups["I"])
                    )
                # Add calls for other guidelines (A, F, H) here if implemented

                # Specialised Surfaces
                if specialised_group_node is not None:
                    run_success_flags.append(
                        self.process_raoa(runway_data, specialised_group_node)
                    )
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

    def _count_layer_tree_contents(
        self, node: QgsLayerTreeNode
    ) -> Tuple[int, int, List[str]]:
        """Count valid layers/features below a layer tree node and collect empty layer names."""
        layer_count = 0
        feature_count = 0
        empty_layers: List[str] = []

        if isinstance(node, QgsLayerTreeLayer):
            layer = node.layer()
            if layer is None or not layer.isValid():
                empty_layers.append(node.name())
                return 0, 0, empty_layers
            layer_count = 1
            try:
                feature_count = max(0, int(layer.featureCount()))
            except Exception:
                feature_count = 0
            if feature_count == 0:
                empty_layers.append(layer.name())
            return layer_count, feature_count, empty_layers

        if isinstance(node, QgsLayerTreeGroup):
            for child in node.children():
                child_layers, child_features, child_empty = (
                    self._count_layer_tree_contents(child)
                )
                layer_count += child_layers
                feature_count += child_features
                empty_layers.extend(child_empty)

        return layer_count, feature_count, empty_layers

    def _empty_group_reason(self, group_name: str, met_ok: bool) -> str:
        """Return a concise explanation for expected empty top-level groups."""
        if group_name.startswith(self.tr("Guideline A:")):
            return "placeholder only; no surface construction logic implemented"
        if group_name.startswith(self.tr("Guideline B:")):
            return "no windshear layers generated; check runway inputs and preceding warnings"
        if group_name.startswith(self.tr("Guideline C:")):
            return "ARP missing or wildlife zone generation failed; check preceding Wildlife warnings"
        if group_name.startswith(self.tr("Guideline D:")):
            return "ARP missing or wind turbine zone generation failed"
        if group_name.startswith(self.tr("Guideline E:")):
            return "no lighting layers generated; check runway inputs and preceding warnings"
        if group_name.startswith(self.tr("Guideline F:")):
            return "no airspace/OLS layers generated; check runway, approach, and RED inputs"
        if group_name.startswith(self.tr("Guideline G:")):
            return "no CNS layers generated, or CNS input was not provided"
        if group_name.startswith(self.tr("Guideline H:")):
            return "placeholder only; no surface construction logic implemented"
        if group_name.startswith(self.tr("Guideline I:")):
            return "no public safety area layers generated; check runway inputs and preceding warnings"
        if group_name == self.tr("Physical Geometry"):
            return "no physical geometry generated; check runway dimensions and coordinates"
        if group_name == self.tr("Runway Protection Areas"):
            return "no protection areas generated; check runway inputs and preceding warnings"
        if group_name == self.tr("Specialised Safeguarding"):
            return "no specialised safeguarding layers generated; check runway inputs and preceding warnings"
        if group_name == self.tr("Meteorological Instrument Station") and not met_ok:
            return "MET coordinates not provided"
        return "no populated layers generated; check preceding warnings for skipped prerequisites"

    def _build_layer_tree_summary(
        self,
        main_group: Optional[QgsLayerTreeGroup],
        met_ok: bool,
    ) -> Tuple[List[str], List[str], int, int]:
        """Summarise actual generated layer tree contents for final logging."""
        if main_group is None:
            return [], ["Main group missing"], 0, 0

        populated: List[str] = []
        empty: List[str] = []
        total_layers = 0
        total_features = 0

        direct_layer_count = 0
        direct_feature_count = 0
        direct_empty_layers: List[str] = []

        for child in main_group.children():
            child_layers, child_features, child_empty = self._count_layer_tree_contents(
                child
            )
            total_layers += child_layers
            total_features += child_features

            if isinstance(child, QgsLayerTreeLayer):
                direct_layer_count += child_layers
                direct_feature_count += child_features
                direct_empty_layers.extend(child_empty)
                continue

            if isinstance(child, QgsLayerTreeGroup):
                group_name = child.name()
                if child_layers > 0 and child_features > 0:
                    populated.append(
                        f"{group_name}: {child_layers} layer(s), {child_features} feature(s)"
                    )
                    if child_empty:
                        empty.append(
                            f"{group_name}: empty layer(s) {', '.join(child_empty)} (0 features)"
                        )
                elif child_layers > 0:
                    empty.append(
                        f"{group_name}: {child_layers} empty layer(s) ({', '.join(child_empty)})"
                    )
                else:
                    empty.append(f"{group_name}: {self._empty_group_reason(group_name, met_ok)}")

        if direct_layer_count:
            if direct_feature_count:
                populated.insert(
                    0,
                    f"Top-level layers: {direct_layer_count} layer(s), {direct_feature_count} feature(s)",
                )
                if direct_empty_layers:
                    empty.insert(
                        0,
                        f"Top-level layers: empty layer(s) {', '.join(direct_empty_layers)} (0 features)",
                    )
            else:
                empty.insert(
                    0,
                    f"Top-level layers: {direct_layer_count} empty layer(s) ({', '.join(direct_empty_layers)})",
                )

        return populated, empty, total_layers, total_features

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
            (
                populated_summaries,
                empty_summaries,
                tree_layer_count,
                tree_feature_count,
            ) = self._build_layer_tree_summary(main_group, met_ok)
            num_layers_created = tree_layer_count or len(self.successfully_generated_layers)
            if not met_ok:
                empty_summaries.append(
                    "Meteorological Instrument Station: MET coordinates not provided; group not created"
                )
            if not arp_ok:
                empty_summaries.append("ARP: ARP coordinates not provided; layer not created")
            runway_summary = (
                f"runways={processed_rwy_count}/{total_runways_in_input}"
                if total_runways_in_input
                else "runways=0"
            )

            if self.output_mode == "file" and self.output_path:
                output_summary = f"files saved to {self.output_path}"
            elif self.output_mode == "memory":
                output_summary = "memory layers created and left unchecked"
            else:
                output_summary = self.output_mode or "output complete"

            final_user_message = (
                f"Processing complete for {icao_code}. "
                f"{num_layers_created} layer(s), {tree_feature_count} feature(s); {output_summary}."
            )
            final_log_message = (
                f"Complete: {icao_code} - {num_layers_created} layer(s), "
                f"{tree_feature_count} feature(s), {runway_summary}, {output_summary}."
            )

            self.iface.messageBar().pushMessage(
                self.tr("Success"), final_user_message, level=Qgis.Success, duration=10
            )  # Increased duration
            self._log_success(final_log_message, notify_user=True)
            if populated_summaries:
                self._log(
                    "Generated groups:\n- " + "\n- ".join(populated_summaries)
                )
            if empty_summaries:
                self._log(
                    "Not generated:\n- " + "\n- ".join(empty_summaries)
                )

            if (
                main_group is not None
            ):  # Only expand group if it exists (it might not if only file output and no group made)
                self._stage_layer_tree_node(main_group)
        else:
            # This case means self.successfully_generated_layers is empty
            self.iface.messageBar().pushMessage(
                self.tr("Process Finished"),
                self.tr("No layers were generated. Check logs for warnings or errors."),
                level=Qgis.Warning,
                duration=7,
            )
            self._log_warning(
                "Processing finished: no layers were generated. Check preceding warnings/errors for the skipped prerequisite."
            )
            if (
                main_group is not None
                and root_node.findGroup(main_group.name()) is not None
            ):  # Only try to remove group if it was created
                self._remove_group_recursively(main_group, project)
                if main_group.parent() is not None:
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
                    "Aerodrome Reference Point",
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
        declared_distances: Optional[List[Dict[str, Any]]] = None,
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

            declared_distance_attrs = self._format_centreline_declared_distances(
                declared_distances or []
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
                    declared_distance_attrs["toda"],
                    declared_distance_attrs["tora"],
                    declared_distance_attrs["lda"],
                    declared_distance_attrs["asda"],
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

    def _format_centreline_declared_distances(
        self, declared_distances: List[Dict[str, Any]]
    ) -> Dict[str, Optional[str]]:
        """Format per-direction declared distances for centreline attributes."""
        formatted = {}
        for field_name in ["toda", "tora", "lda", "asda"]:
            value_key = f"{field_name}_m"
            parts = []
            for record in declared_distances:
                end_desig = record.get("end_desig")
                value = record.get(value_key)
                if end_desig and value is not None:
                    parts.append(f"{end_desig}={round(float(value), 3):g}")
            formatted[field_name] = ";".join(parts) if parts else None
        return formatted

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

    # ============================================================
    # ============================================================
    # Specialised Safeguarding Processing (e.g., RAOA)
    # ============================================================



# ============================================================
# End of Plugin Class
# ============================================================
