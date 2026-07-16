# -*- coding: utf-8 -*-
# safeguarding_builder.py

import os.path
import math
import re
import traceback
from pathlib import Path

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
    Qgis,
    QgsCoordinateReferenceSystem,
)

# --- Local Imports ---
from .core.layers import LayerMixin
from .core import output_structure
from .core.run_log import QgsMessageLog, RunLog, set_active_run_log
from .core.styles import DEFAULT_STYLE_MAP
from .core.run_history import (
    RuntimeRunRecorder,
    classify_runway_configuration,
    runtime_input_fingerprint,
)
from .surfaces.physical import PhysicalGeometryMixin
from .surfaces.annex14_geometry import Annex14GeometryMixin
from .surfaces.airfield_ground_lighting import AirfieldGroundLightingMixin
from .surfaces.specialised import SpecialisedSurfacesMixin
from .surfaces.met import MetSurfacesMixin
from .frameworks.nasf.processors import NasfGuidelinesMixin
from .frameworks.nasf.lighting import LightingGuidelineMixin
from .guidelines.ols_guideline import OlsGuidelineMixin
from .guidelines.controlling_ols_engine import ControllingOlsEngineMixin
from .guidelines.ols_modernisation_comparison import OlsModernisationComparisonMixin
from .reports.declared_distances import annotate_declared_distance_warnings, apply_declared_distance_overrides
from .reports.runway_summary import build_runway_summaries, render_markdown_report
from .frameworks.registry import get_framework_profile
from .rulesets.context import (
    OlsConstructionContext,
    OlsRunwayContext,
    OlsRunwayEndContext,
    RulesetContext,
)
from .rulesets.registry import get_ruleset_profile


try:
    # Attempt to import generated resources
    from . import resources_rc

    resources_rc.qInitResources
except ImportError:
    # Resource registration is optional; operational logging is not available
    # during module import and import-time console noise is deliberately avoided.
    resources_rc = None
# Import the dialog class
from .safeguarding_builder_dialog import SafeguardingBuilderDialog

# Plugin-specific constant for logging
PLUGIN_TAG = "SafeguardingBuilder"


# ============================================================
# Main Plugin Class - SafeguardingBuilder
# ============================================================
class SafeguardingBuilder(
    NasfGuidelinesMixin,
    LightingGuidelineMixin,
    ControllingOlsEngineMixin,
    OlsModernisationComparisonMixin,
    OlsGuidelineMixin,
    PhysicalGeometryMixin,
    Annex14GeometryMixin,
    AirfieldGroundLightingMixin,
    SpecialisedSurfacesMixin,
    MetSurfacesMixin,
    LayerMixin,
):
    """QGIS plugin implementation for aerodrome safeguarding surface generation."""

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
        self.contour_intervals: Dict[str, float] = {}
        self.protected_airspace_policy: str = "ruleset_aligned"
        self._run_log: Optional[RunLog] = None
        self.ruleset = get_ruleset_profile()
        self.baseline_ols_ruleset = self.ruleset
        self.comparison_ols_ruleset = None
        self.protected_airspace_ruleset = self.baseline_ols_ruleset
        self._contour_interval_ruleset_role = "baseline"
        self.framework = get_framework_profile()
        self.ruleset_context = RulesetContext(
            design_standard=self.ruleset,
            safeguarding_framework=self.framework,
        )

        self._init_locale()

    def _initialise_crs(self):
        """Force QGIS to initialise CRS subsystems by adding and removing a dummy layer."""
        plugin_tag = PLUGIN_TAG
        crs_authid = QgsProject.instance().crs().authid()
        dummy = QgsVectorLayer(f"Point?crs={crs_authid}", "crs_init_dummy", "memory")
        if dummy.isValid():
            QgsProject.instance().addMapLayer(dummy, False)
            QgsProject.instance().removeMapLayer(dummy)
        else:
            QgsMessageLog.logMessage(
                "CRS initialisation dummy layer failed to create.",
                plugin_tag,
                Qgis.Warning,
            )

    def _init_locale(self):
        """Load translation file."""
        locale_code = QSettings().value("locale/userLocale", "")[0:2]
        locale_path = os.path.join(self.plugin_dir, "i18n", f"SafeguardingBuilder_{locale_code}.qm")
        if os.path.exists(locale_path):
            self.translator = QTranslator()
            if self.translator.load(locale_path):
                QCoreApplication.installTranslator(self.translator)
            else:
                self.translator = None

    def tr(self, message: str) -> str:
        """Get the translation for a string using Qt translation API."""
        if self.translator:
            # Use type() for class name to avoid potential undefined variable
            return QCoreApplication.translate(type(self).__name__, message)
        return message

    def _log(self, message: str, level=Qgis.Info, notify_user: bool = False):
        """Compatibility entry point routed through the structured run logger."""
        del notify_user
        QgsMessageLog.logMessage(message, PLUGIN_TAG, level=level)

    def _log_skip(self, message: str):
        self._log(f"[skip] {message}", Qgis.Info, notify_user=False)

    def _log_warning(self, message: str, notify_user: bool = True):
        del notify_user
        self._log(message, Qgis.Warning)

    def _log_critical(self, message: str, notify_user: bool = True):
        del notify_user
        self._log(message, Qgis.Critical)

    def _diagnostic(self, message: str, topic: Optional[str] = None):
        run_log = getattr(self, "_run_log", None)
        if run_log is not None:
            run_log.diagnostic(topic or "generation", message)

    def _crs_is_geographic(self, crs: QgsCoordinateReferenceSystem) -> bool:
        """Return True when a CRS uses angular units and is unsuitable for metre buffers."""
        try:
            return bool(crs.isGeographic())
        except Exception:
            return False

    def get_active_ruleset(self):
        """Return the active ruleset profile, defaulting to MOS139."""
        return getattr(self, "ruleset", get_ruleset_profile())

    def get_active_protected_airspace_ruleset(self):
        """Return the ruleset profile used for protected airspace/OLS generation."""
        return getattr(self, "protected_airspace_ruleset", self.get_active_ruleset())

    def _build_ols_construction_context(
        self,
        ruleset,
        processed_runway_data_list: List[Dict[str, Any]],
        arp_point=None,
    ) -> OlsConstructionContext:
        """Normalise runway inputs independently under one selected OLS ruleset."""

        context_runways: List[OlsRunwayContext] = []
        for source_runway in processed_runway_data_list:
            runway_data = dict(source_runway)
            runway_data.pop("_effective_clearway_specs", None)
            runway_data.pop("_calculated_strip_ruleset_id", None)
            runway_data.pop("calculated_strip_dims", None)
            thr_point = runway_data.get("thr_point")
            rec_thr_point = runway_data.get("rec_thr_point")
            rwy_params = self._get_runway_parameters(thr_point, rec_thr_point)
            if not rwy_params:
                continue
            physical_endpoints = self._get_physical_runway_endpoints(
                thr_point,
                rec_thr_point,
                self._non_negative_float(runway_data.get("thr_displaced_1"), 0.0),
                self._non_negative_float(runway_data.get("thr_displaced_2"), 0.0),
                rwy_params,
            )
            if physical_endpoints is None:
                continue
            physical_primary, physical_reciprocal, physical_length = physical_endpoints
            try:
                arc_number = int(runway_data.get("arc_num"))
            except (TypeError, ValueError):
                continue
            width_m = self._non_negative_float(runway_data.get("width"), 0.0)
            classified_primary = ruleset.classify_runway_type(runway_data.get("type1"))
            classified_reciprocal = ruleset.classify_runway_type(runway_data.get("type2"))
            type_rank = {"NI": 0, "NPA": 1, "PA_I": 2, "PA_II_III": 3}
            strip_classification = classified_primary
            if getattr(ruleset, "id", "") != "mos139_2019":
                strip_classification = max(
                    (classified_primary, classified_reciprocal),
                    key=lambda value: type_rank.get(value, -1),
                )
            strip_parameters = ruleset.strip_parameters(
                arc_number,
                strip_classification,
                width_m or None,
            ) or {}
            runway_data["calculated_strip_dims"] = strip_parameters
            runway_data["_calculated_strip_ruleset_id"] = ruleset.id
            clearway_specs = self._calculate_effective_clearway_specs(
                runway_data,
                physical_length,
                ruleset=ruleset,
            )
            declared_distances = self._calculate_declared_distances(runway_data, ruleset=ruleset)
            runway_data["declared_distances"] = declared_distances
            records_by_direction = {
                str(record.get("direction") or ""): record
                for record in declared_distances
            }
            runway_name = runway_data.get(
                "short_name",
                f"RWY_{runway_data.get('original_index', '?')}",
            )
            primary_designator, reciprocal_designator = (
                runway_name.split("/", 1)
                if "/" in runway_name
                else (runway_name, "Reciprocal")
            )

            def end_context(
                direction: str,
                designator: str,
                threshold_point,
                threshold_elevation_key: str,
                runway_end_elevation_key: str,
                approach_type_key: str,
                classified_type: str,
                suffix: str,
            ) -> OlsRunwayEndContext:
                record = records_by_direction.get(direction, {})
                return OlsRunwayEndContext(
                    direction=direction,
                    designator=designator,
                    threshold_point=threshold_point,
                    threshold_elevation_m=runway_data.get(threshold_elevation_key),
                    runway_end_elevation_m=runway_data.get(runway_end_elevation_key),
                    approach_type=str(runway_data.get(approach_type_key) or ""),
                    classified_type=classified_type,
                    clearway_length_m=float(record.get("clearway_m") or 0.0),
                    stopway_length_m=float(record.get("stopway_m") or 0.0),
                    tora_m=record.get("tora_m"),
                    toda_m=record.get("toda_m"),
                    asda_m=record.get("asda_m"),
                    lda_m=record.get("lda_m"),
                    approach_track_type=str(
                        runway_data.get(f"approach_track_type_{suffix}") or "aligned"
                    ),
                    approach_track_wkt=str(
                        runway_data.get(f"approach_track_wkt_{suffix}") or ""
                    ),
                    takeoff_track_type=str(
                        runway_data.get(f"takeoff_track_type_{suffix}") or "aligned"
                    ),
                    takeoff_track_wkt=str(
                        runway_data.get(f"takeoff_track_wkt_{suffix}") or ""
                    ),
                )

            ends = (
                end_context(
                    "primary",
                    primary_designator,
                    thr_point,
                    "threshold_elev_1",
                    "runway_end_elev_1",
                    "type1",
                    classified_primary,
                    "1",
                ),
                end_context(
                    "reciprocal",
                    reciprocal_designator,
                    rec_thr_point,
                    "threshold_elev_2",
                    "runway_end_elev_2",
                    "type2",
                    classified_reciprocal,
                    "2",
                ),
            )
            context_runways.append(
                OlsRunwayContext(
                    runway_id=runway_name,
                    original_index=int(runway_data.get("original_index") or 0),
                    arc_number=arc_number,
                    arc_letter=str(runway_data.get("arc_let") or "").strip().upper(),
                    width_m=width_m,
                    physical_length_m=float(physical_length),
                    threshold_length_m=float(rwy_params.get("length") or 0.0),
                    primary_threshold_point=thr_point,
                    reciprocal_threshold_point=rec_thr_point,
                    primary_physical_end_point=physical_primary,
                    reciprocal_physical_end_point=physical_reciprocal,
                    strip_parameters=dict(strip_parameters),
                    ends=ends,
                    is_wide_runway=bool(
                        runway_data.get("cap168_wide_runway")
                        or strip_parameters.get("wide_non_instrument_variation")
                    ),
                    generation_data=runway_data,
                )
            )
        return OlsConstructionContext(
            ruleset_id=ruleset.id,
            runways=tuple(context_runways),
            arp_point=arp_point,
            arp_elevation_m=getattr(self, "arp_elevation_amsl", None),
            reference_elevation_datum_m=getattr(self, "reference_elevation_datum", None),
        )

    def _activate_ols_construction_context(self, ruleset, context: OlsConstructionContext) -> bool:
        """Install and validate the context consumed by conventional geometry."""

        errors = tuple(ruleset.ols_construction_policy().validate(context))
        self.ols_construction_context = context
        if errors:
            for error in errors:
                self._log_warning(f"[skip] {ruleset.display_name} OLS: {error}")
            return False
        return True

    def get_active_framework(self):
        """Return the active safeguarding framework profile, defaulting to NASF."""
        return getattr(self, "framework", get_framework_profile())

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
                QgsMessageLog.logMessage(f"Error cleaning dialog: {e}", PLUGIN_TAG, level=Qgis.Warning)
            self.dlg = None
        self.successfully_generated_layers = []

    def run(self):
        """Shows the plugin dialog or brings it to front if already open."""
        if self.dlg is not None and self.dlg.isVisible():
            self.dlg.raise_()
            self.dlg.activateWindow()
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
                    self.tr("Main 'Generate' button is missing from the dialog. Plugin cannot function."),
                )
                self.dlg.deleteLater()  # Clean up the partially created dialog
                self.dlg = None
                return

            # The dialog's built-in close mechanisms (X button, Esc key)
            # will emit the finished signal.
            self.dlg.finished.connect(self.dialog_finished)

        self.dlg.show()

    def dialog_finished(self, result: int):
        """Slot connected to the dialog's finished signal for cleanup."""
        del result
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
        Uses validated runway data containing runway-end elevations.
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

        runway_end_elevations: List[float] = []
        missing_elev_rwy_summaries: List[str] = []  # Store summary strings for missing elevations

        for rwy_data in runway_data_list:
            end_elev = rwy_data.get("runway_end_elev_1")
            rec_end_elev = rwy_data.get("runway_end_elev_2")

            # Generate a name for logging/reporting
            rwy_name = rwy_data.get("short_name", f"RWY Index {rwy_data.get('original_index', '?')}")

            # Check if the retrieved values are valid floats
            valid_end = isinstance(end_elev, (int, float))
            valid_rec = isinstance(rec_end_elev, (int, float))

            # Add valid elevations to the list
            if valid_end:
                runway_end_elevations.append(float(end_elev))
            if valid_rec:
                runway_end_elevations.append(float(rec_end_elev))

            # Collect summary if elevations are missing for this runway
            if not valid_end or not valid_rec:
                missing_parts = []
                if not valid_end:
                    missing_parts.append("END1")
                if not valid_rec:
                    missing_parts.append("END2")
                missing_elev_rwy_summaries.append(f"{rwy_name} ({'/'.join(missing_parts)})")

        # --- Post-Loop Checks and Logging ---

        # Critical Error: No valid runway-end elevations found at all.
        if not runway_end_elevations:
            QgsMessageLog.logMessage(
                "Cannot calculate RED: No valid runway-end elevations found in any runway data.",
                plugin_tag,
                level=Qgis.Critical,
            )
            # User feedback is crucial here as it prevents further dependent calculations.
            if self.iface:
                self.iface.messageBar().pushMessage(
                    self.tr("Error"),
                    self.tr("Cannot calculate Reference Elevation Datum: No valid runway-end elevations found."),
                    level=Qgis.Critical,
                    duration=10,
                )
            return None

        # Warning: Some elevations were missing, but calculation can proceed.
        if missing_elev_rwy_summaries:
            summary_str = ", ".join(missing_elev_rwy_summaries)
            # Log a single warning summarizing all missing elevations.
            QgsMessageLog.logMessage(
                f"Warning: Missing runway-end elevations for: [{summary_str}]. "
                "RED calculation proceeding with available data.",
                plugin_tag,
                level=Qgis.Warning,
            )
            # Provide a single warning to the user.
            if self.iface:
                self.iface.messageBar().pushMessage(
                    self.tr("Warning"),
                    self.tr(
                        "Missing runway-end elevations for some runways. "
                        "RED calculation may be inaccurate. Check Log Messages panel for details."
                    ),
                    level=Qgis.Warning,
                    duration=8,
                )

        # --- Calculation ---
        avg_end_elev = sum(runway_end_elevations) / len(runway_end_elevations)
        # Info: Log the average value used in the calculation.
        QgsMessageLog.logMessage(
            f"Calculated Average Runway-End Elevation: {avg_end_elev:.3f}m AMSL",
            plugin_tag,
            level=Qgis.Info,
        )

        reference_elevation_unrounded: float
        # Apply MOS 139 rule
        if abs(arp_elevation - avg_end_elev) <= 3.0:
            reference_elevation_unrounded = arp_elevation
            red_basis = "ARP elevation"
            # Info: Log the basis for the RED value.
            QgsMessageLog.logMessage(
                "RED based on ARP Elevation (within 3m of average runway-end elev).",
                plugin_tag,
                level=Qgis.Info,
            )
        else:
            reference_elevation_unrounded = avg_end_elev
            red_basis = "average runway-end elevation"
            # Info: Log the basis for the RED value.
            QgsMessageLog.logMessage(
                "RED based on Average Runway-End Elevation (>3m difference from ARP).",
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
        if self._run_log is not None:
            self._run_log.output(
                "reference elevation datum",
                value_m=f"{reference_elevation_datum:.2f}",
                basis=red_basis,
                samples=len(runway_end_elevations),
            )
        return reference_elevation_datum

    def run_safeguarding_processing(self):
        """Run generation and always append one GUI/headless runtime record."""
        run_log = RunLog()
        self._run_log = run_log
        set_active_run_log(run_log)
        project_crs = QgsProject.instance().crs()
        run_log.start(
            crs=project_crs.authid()
            if project_crs is not None and project_crs.isValid()
            else None
        )
        recorder = RuntimeRunRecorder(
            Path(self.plugin_dir),
            qgis_version=getattr(Qgis, "QGIS_VERSION", "unknown"),
        )
        self._runtime_run_recorder = recorder
        self._processing_run_status = "aborted"
        recorder.set_context(
            airport=None,
            design_ruleset=getattr(getattr(self, "ruleset", None), "id", None),
            baseline_ruleset=getattr(getattr(self, "baseline_ols_ruleset", None), "id", None),
            comparison_ruleset=getattr(getattr(self, "comparison_ols_ruleset", None), "id", None),
            design_ruleset_label=getattr(getattr(self, "ruleset", None), "display_name", None),
            baseline_ruleset_label=getattr(
                getattr(self, "baseline_ols_ruleset", None), "display_name", None
            ),
            comparison_ruleset_label=getattr(
                getattr(self, "comparison_ols_ruleset", None), "display_name", None
            ),
            **dict(getattr(self.dlg, "_runtime_test_context", {}) or {}),
        )
        recorder.start_phase("startup")
        try:
            return self._run_safeguarding_processing()
        except Exception:
            self._processing_run_status = "failed"
            raise
        finally:
            layer_count, feature_count = self._runtime_generated_output_counts()
            try:
                if not recorder._output_counts_set:
                    recorder.set_output_counts(layer_count, feature_count)
                recorder.finish(self._processing_run_status)
            except Exception as exc:
                self._log_warning(f"Could not append runtime test record: {exc}", notify_user=False)
            finally:
                self._runtime_run_recorder = None
                output = (
                    self.output_path
                    if self.output_mode == "file" and self.output_path
                    else self.output_mode or "unknown"
                )
                run_log.finish(
                    self._processing_run_status,
                    airport=getattr(self, "icao_code", None),
                    runways=getattr(self, "_processing_runway_summary", None),
                    layers=layer_count,
                    features=feature_count,
                    output=output,
                )
                set_active_run_log(None)
                self._run_log = None

    def _runtime_generated_output_counts(self) -> Tuple[int, int]:
        """Return valid generated layer and feature totals for partial runs."""
        layers = []
        seen_layer_ids = set()
        for layer in list(getattr(self, "successfully_generated_layers", []) or []):
            try:
                if layer is None or not layer.isValid():
                    continue
                layer_id = str(layer.id())
                if layer_id in seen_layer_ids:
                    continue
                seen_layer_ids.add(layer_id)
                layers.append(layer)
            except Exception:
                continue
        feature_count = 0
        for layer in layers:
            try:
                feature_count += max(0, int(layer.featureCount()))
            except Exception:
                continue
        return len(layers), feature_count

    def _run_safeguarding_processing(self):
        plugin_tag = PLUGIN_TAG

        self.successfully_generated_layers = []
        self.reference_elevation_datum = None
        self.arp_elevation_amsl = None
        self.output_mode = "memory"
        self.output_path = None
        self.output_format_driver = None
        self.output_format_extension = None
        self.contour_intervals = {}
        self.protected_airspace_policy = "ruleset_aligned"
        self.baseline_ols_ruleset = self.ruleset
        self.comparison_ols_ruleset = None
        self._contour_interval_ruleset_role = "baseline"
        self._processing_main_group = None
        self._processing_total_steps = 10

        if self.dlg is None:
            self._log_critical("Processing aborted: dialog reference missing.")
            return

        self._begin_processing_progress(self._processing_total_steps)
        self._set_processing_status(
            self.tr("Starting safeguarding generation..."),
            step=0,
            total_steps=self._processing_total_steps,
        )

        project = QgsProject.instance()
        target_crs = project.crs()
        target_crs_authid = target_crs.authid()
        if not target_crs or not target_crs.isValid():
            self._log_critical("Processing aborted: project CRS is invalid or not set.")
            self.iface.messageBar().pushMessage(
                self.tr("Error"),
                self.tr("Project CRS is invalid or not set. Please set a valid Projected CRS."),
                level=Qgis.Critical,
                duration=10,
            )
            self._clear_processing_status()
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
            self._clear_processing_status()
            return

        if self._run_log is not None:
            self._run_log.start(crs=target_crs_authid)

        # Force CRS subsystem to initialise properly
        self._initialise_crs()

        specialised_safeguarding_group = None

        input_data = None
        try:
            if not self._processing_checkpoint(
                self.tr("Reading and validating inputs..."),
                1,
                self._processing_total_steps,
                phase_key="inputs",
            ):
                return
            input_data = self.dlg.get_all_input_data()
            if input_data is None:
                self._log_warning(
                    "Processing aborted: input validation failed. Check the dialog and preceding messages."
                )
                self._clear_processing_status()
                return
        except Exception as e:
            self._log_critical(f"Processing aborted: failed to read input data: {e}\n{traceback.format_exc()}")
            self.iface.messageBar().pushMessage(
                self.tr("Error"),
                self.tr("Failed to retrieve input data. See log for details."),
                level=Qgis.Critical,
                duration=10,
            )
            self._clear_processing_status()
            return

        self.output_mode = input_data.get("output_mode", "memory")
        self.icao_code = input_data.get("icao_code", "UNKNOWN_ICAO")
        self.output_path = input_data.get("output_path")
        self.output_format_driver = input_data.get("output_format_driver")
        self.output_format_extension = input_data.get("output_format_extension")
        self.contour_intervals = input_data.get("contour_intervals", {})
        self.ruleset = get_ruleset_profile(input_data.get("design_standard") or input_data.get("ruleset"))
        protected_airspace_policy = input_data.get("protected_airspace_policy", "ruleset_aligned")
        self.protected_airspace_policy = protected_airspace_policy
        baseline_ols_ruleset_id = input_data.get("baseline_ols_ruleset")
        comparison_ols_ruleset_id = input_data.get("comparison_ols_ruleset")
        if not baseline_ols_ruleset_id:
            baseline_ols_ruleset_id = (
                "icao_annex14_vol1_modernised_ofs_oes"
                if protected_airspace_policy == "future_annex14_ofs_oes"
                else self.ruleset.id
            )
            if protected_airspace_policy == "modernisation_comparison":
                comparison_ols_ruleset_id = "icao_annex14_vol1_modernised_ofs_oes"
        self.baseline_ols_ruleset = get_ruleset_profile(baseline_ols_ruleset_id)
        self.comparison_ols_ruleset = (
            get_ruleset_profile(comparison_ols_ruleset_id)
            if comparison_ols_ruleset_id
            else None
        )
        self.protected_airspace_ruleset = self.baseline_ols_ruleset
        self._processing_total_steps = 10 if self.comparison_ols_ruleset is not None else 9
        self.framework = get_framework_profile(input_data.get("safeguarding_framework"))
        self.ruleset_context = RulesetContext(
            design_standard=self.ruleset,
            safeguarding_framework=self.framework,
        )

        runway_input_list = input_data.get("runways", [])
        self._processing_runway_summary = f"0/{len(runway_input_list)}"
        runtime_test_context = dict(
            getattr(self.dlg, "_runtime_test_context", {}) or {}
        )
        runtime_test_context.setdefault("test_case_id", "manual_entry")
        runtime_test_context.setdefault("test_case_name", "Manual entry")
        runtime_test_context.setdefault(
            "runway_configuration",
            classify_runway_configuration(runway_input_list),
        )
        runtime_runway_count = runtime_test_context.pop(
            "runway_count", len(runway_input_list)
        )
        runtime_fingerprint = runtime_test_context.pop(
            "input_fingerprint", runtime_input_fingerprint(input_data)
        )

        recorder = getattr(self, "_runtime_run_recorder", None)
        if recorder is not None:
            recorder.set_context(
                airport=input_data.get("icao_code"),
                design_ruleset=self.ruleset.id,
                baseline_ruleset=self.baseline_ols_ruleset.id,
                comparison_ruleset=getattr(self.comparison_ols_ruleset, "id", None),
                design_ruleset_label=self.ruleset.display_name,
                baseline_ruleset_label=self.baseline_ols_ruleset.display_name,
                comparison_ruleset_label=getattr(
                    self.comparison_ols_ruleset, "display_name", None
                ),
                runway_count=runtime_runway_count,
                input_fingerprint=runtime_fingerprint,
                **runtime_test_context,
            )

        icao_code = input_data.get("icao_code", "UNKNOWN")
        arp_point = input_data.get("arp_point")
        arp_east = input_data.get("arp_easting")
        arp_north = input_data.get("arp_northing")
        met_point = input_data.get("met_point")
        cns_input_list = input_data.get("cns_facilities", [])
        agl_options = input_data.get("agl_options", {"enabled": False})
        self.arp_elevation_amsl = input_data.get("arp_elevation")

        output_desc = (
            "memory"
            if self.output_mode == "memory"
            else f"{self.output_format_driver or 'file'} -> {self.output_path or 'N/A'}"
        )
        if self._run_log is not None:
            self._run_log.update_context(
                airport=icao_code,
                ruleset=self.ruleset.id,
                baseline=self.baseline_ols_ruleset.id,
                comparison=getattr(self.comparison_ols_ruleset, "id", "none"),
                framework=self.framework.id,
                output=output_desc,
            )
            self._run_log.output(
                "inputs",
                airport=icao_code,
                runways=len(runway_input_list),
                arp="yes" if arp_point is not None else "no",
                met="yes" if met_point is not None else "no",
                agl="enabled" if agl_options.get("enabled") else "disabled",
                cns=len(cns_input_list),
                ruleset=self.ruleset.id,
                baseline=self.baseline_ols_ruleset.id,
                comparison=getattr(self.comparison_ols_ruleset, "id", "none"),
                framework=self.framework.id,
                output=output_desc,
            )

        if not runway_input_list:
            self._log_warning("Processing aborted: no valid runway data found.")
            self.iface.messageBar().pushMessage(
                self.tr("Warning"),
                self.tr("No valid runway data found after validation."),
                level=Qgis.Warning,
                duration=5,
            )
            self._clear_processing_status()

        if runway_input_list:
            self.style_map = dict(DEFAULT_STYLE_MAP)
            if not self._processing_checkpoint(
                self.tr("Preparing output groups and reference layers..."),
                2,
                self._processing_total_steps,
                phase_key="output_setup",
            ):
                return

            root = project.layerTreeRoot()
            main_group_name = f"{icao_code} {self.tr('Safeguarding Builder')}"
            main_group = self._setup_main_group(root, main_group_name, project)
            if main_group is None:
                self.iface.messageBar().pushMessage(
                    self.tr("Error"),
                    self.tr("Failed to create main layer group."),
                    level=Qgis.Critical,
                    duration=10,
                )
                self._clear_processing_status()
                return
            self._processing_main_group = main_group

            output_groups = self._create_output_layer_groups(main_group, bool(agl_options.get("enabled")))
            reference_group = output_groups.get("reference_data")
            if reference_group is None:
                reference_group = main_group
            external_safeguarding_group = output_groups.get("external_safeguarding")
            if external_safeguarding_group is None:
                external_safeguarding_group = main_group
            ols_surfaces_group = output_groups.get("ols_surfaces")
            if ols_surfaces_group is None:
                ols_surfaces_group = main_group
            debug_group = output_groups.get("debug_development")
            if debug_group is None:
                debug_group = main_group
            controlling_ols_surfaces_group = output_groups.get("controlling_ols_surfaces")
            if controlling_ols_surfaces_group is None:
                controlling_ols_surfaces_group = debug_group
            controlling_contours_group = output_groups.get("controlling_contours")
            if controlling_contours_group is None:
                controlling_contours_group = debug_group

            arp_layer_created = False
            if arp_point is not None:
                arp_layer = self.create_arp_layer(
                    arp_point,
                    arp_east,
                    arp_north,
                    icao_code,
                    target_crs,
                    reference_group,
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

            runway_centreline_group = (
                self._ensure_layer_group(reference_group, output_structure.RUNWAY_CENTRE_LINES) or reference_group
            )

            met_layers_created_ok = False
            if met_point is not None:
                met_group = reference_group.addGroup(self.tr(output_structure.METEOROLOGICAL_STATION))
                if met_group is not None:
                    self._stage_layer_tree_node(met_group)
                    met_layers_created_ok, _ = self.process_met_station_surfaces(
                        met_point, icao_code, target_crs, met_group
                    )
                else:
                    QgsMessageLog.logMessage(
                        f"Failed to create '{output_structure.METEOROLOGICAL_STATION}' subgroup.",
                        plugin_tag,
                        level=Qgis.Warning,
                    )
            else:
                self._log_skip("MET station surfaces: no MET coordinates provided.")

            if cns_input_list:
                cns_source_group = reference_group.addGroup(self.tr(output_structure.CNS_TECHNICAL_FACILITIES))
                if cns_source_group is not None:
                    self._stage_layer_tree_node(cns_source_group)
                    self.create_cns_source_facility_layer(cns_input_list, icao_code, cns_source_group)
                else:
                    self._log_warning("[skip] CNS source facilities: failed to create reference group.")

            if not self._processing_checkpoint(
                self.tr("Generating runway reference geometry..."),
                3,
                self._processing_total_steps,
                phase_key="runway_reference_geometry",
            ):
                return
            processed_runway_data_list, any_runway_base_data_ok = self._process_runways_part1(
                runway_centreline_group, project, target_crs, icao_code, runway_input_list
            )

            if any_runway_base_data_ok:
                for rwy_data in processed_runway_data_list:
                    cl_layer = rwy_data.get("centreline_layer")
                    if cl_layer is not None:
                        self._apply_style(cl_layer, self.style_map)

            agl_group = None
            if agl_options.get("enabled"):
                agl_group = output_groups.get("airfield_ground_lighting")
                if agl_group is not None:
                    self._stage_layer_tree_node(agl_group)

            if not self._processing_checkpoint(
                self.tr("Generating physical and protection surfaces..."),
                4,
                self._processing_total_steps,
                phase_key="physical_and_protection",
            ):
                return
            (
                specialised_safeguarding_group,
                any_physical_or_protection_ok,
            ) = self._process_physical_and_protection_layers(
                main_group,
                icao_code,
                processed_runway_data_list,
                any_runway_base_data_ok,
                {
                    "markings": output_groups.get("markings"),
                    "physical_geometry": output_groups.get("physical_geometry"),
                    "runway_protection_areas": output_groups.get("runway_protection_areas"),
                    "specialised_safeguarding": output_groups.get("specialised_safeguarding"),
                },
            )

            agl_processed_ok = False
            if not self._processing_checkpoint(
                self.tr("Generating supporting safeguarding layers..."),
                5,
                self._processing_total_steps,
                phase_key="supporting_safeguarding",
            ):
                return
            if agl_options.get("enabled"):
                self._set_processing_status(
                    self.tr("Generating airfield ground lighting layers..."),
                    step=5,
                    total_steps=self._processing_total_steps,
                )
                if agl_group is not None:
                    agl_processed_ok = self.process_airfield_ground_lighting(
                        processed_runway_data_list,
                        agl_options,
                        agl_group,
                    )
                else:
                    self._log_warning("[skip] Airfield ground lighting: failed to create output group.")
            else:
                self._log_skip("Airfield ground lighting: option not enabled.")

            if not self._processing_checkpoint(
                self.tr(self.get_active_framework().generation_status_message()),
                5,
                self._processing_total_steps,
                phase_key="supporting_safeguarding",
            ):
                return
            guideline_groups = self._create_guideline_groups(external_safeguarding_group, bool(cns_input_list))
            guideline_groups["F"] = ols_surfaces_group
            self._reset_controlling_ols_engine()

            airport_wide_ols_group = None
            runway_ols_group = None
            ofz_group = output_groups.get("obstacle_free_zone")
            if guideline_groups.get("F") is not None:
                runway_ols_group = guideline_groups["F"]
                airport_wide_ols_group = output_groups.get("airport_wide_ols")

            self.reference_elevation_datum = self._calculate_reference_elevation_datum(
                self.arp_elevation_amsl, runway_input_list
            )
            self._ols_source_runways = processed_runway_data_list
            self._ols_arp_point = arp_point
            baseline_ols_context = self._build_ols_construction_context(
                self.baseline_ols_ruleset,
                processed_runway_data_list,
                arp_point=arp_point,
            )
            self._ols_construction_contexts = {
                self.baseline_ols_ruleset.id: baseline_ols_context,
            }
            baseline_ols_context_ready = self._activate_ols_construction_context(
                self.baseline_ols_ruleset,
                baseline_ols_context,
            )
            baseline_airport_spec = self.baseline_ols_ruleset.ols_construction_policy().airport_wide_spec(
                self.baseline_ols_ruleset,
                baseline_ols_context,
            )
            baseline_ols_requires_red = (
                baseline_airport_spec.get("datum_name") == "reference_elevation_datum"
            )
            pa_runways_exist = any(
                "PA" in rwy.get("type1", "") or "PA" in rwy.get("type2", "") for rwy in runway_input_list if rwy
            )
            if self.reference_elevation_datum is None and pa_runways_exist and baseline_ols_requires_red:
                QgsMessageLog.logMessage(
                    "Aborting OLS generation: RED calculation failed and precision approach runways exist.",
                    plugin_tag,
                    level=Qgis.Critical,
                )
                self.iface.messageBar().pushMessage(
                    self.tr("Error"),
                    self.tr("Reference Elevation Datum calculation failed. Cannot generate OLS for precision runways."),
                    level=Qgis.Critical,
                    duration=10,
                )

            (
                wildlife_processed,
                wind_turbine_processed,
                cns_processed,
            ) = self._process_airport_safeguarding(
                arp_point,
                cns_input_list,
                icao_code,
                target_crs,
                guideline_groups,
            )

            if not self._processing_checkpoint(
                self.tr("Generating runway OLS surfaces..."),
                6,
                self._processing_total_steps,
                phase_key="runway_ols",
            ):
                return
            any_guideline_processed_ok = self._process_runways_part2(
                processed_runway_data_list,
                guideline_groups,
                specialised_safeguarding_group,
                ofz_group,
                runway_ols_group,
                airport_wide_ols_group,
                ols_runway_data_list=(
                    processed_runway_data_list
                    if getattr(self.baseline_ols_ruleset, "protected_airspace_model", "")
                    == "annex14_modernised_ofs_oes"
                    else baseline_ols_context.generation_runways()
                    if baseline_ols_context_ready
                    else []
                ),
            )

            if not self._processing_checkpoint(
                self.tr("Generating airport-wide OLS surfaces..."),
                7,
                self._processing_total_steps,
                phase_key="airport_wide_ols",
            ):
                return
            any_guideline_processed_ok = self._process_airport_wide_ols_if_possible(
                guideline_groups,
                processed_runway_data_list,
                icao_code,
                any_guideline_processed_ok,
                airport_wide_ols_group,
            )
            solved_ols_engines: Dict[str, Any] = {}
            if not self._processing_checkpoint(
                self.tr("Solving controlling protected-airspace envelopes..."),
                8,
                self._processing_total_steps,
                phase_key="controlling_envelope",
            ):
                return
            if guideline_groups.get("F") is not None:
                if self._is_future_annex14_protected_airspace():
                    self._set_processing_status(
                        self.tr("Solving controlling Annex 14 OFS/OES surfaces..."),
                        step=8,
                        total_steps=self._processing_total_steps,
                    )
                    controlling_ols_ok = self._create_annex14_controlling_surface_layers(
                        icao_code,
                        runway_ols_group,
                        airport_wide_ols_group,
                        debug_group,
                        solved_engines=solved_ols_engines,
                    )
                else:
                    self._set_processing_status(
                        self.tr("Solving controlling OLS lower envelope..."),
                        step=8,
                        total_steps=self._processing_total_steps,
                    )
                    controlling_ols_ok = self._create_controlling_ols_layers(
                        icao_code,
                        debug_group,
                        controlling_ols_surfaces_group,
                        controlling_contours_group,
                        solved_engines=solved_ols_engines,
                    )
                if self._processing_cancel_requested():
                    self._finish_processing_cancelled()
                    return
                any_guideline_processed_ok = any_guideline_processed_ok or controlling_ols_ok
                if getattr(self, "comparison_ols_ruleset", None) is not None:
                    if not self._processing_checkpoint(
                        self.tr("Generating and comparing the selected OLS ruleset..."),
                        9,
                        self._processing_total_steps,
                        phase_key="ruleset_comparison",
                    ):
                        return
                    comparison_ok = self._run_ols_ruleset_comparison(
                        icao_code,
                        processed_runway_data_list,
                        output_groups,
                        debug_group,
                        solved_baseline_engines=solved_ols_engines,
                    )
                    if self._processing_cancel_requested():
                        self._finish_processing_cancelled()
                        return
                    any_guideline_processed_ok = any_guideline_processed_ok or comparison_ok
            any_guideline_processed_ok = any_guideline_processed_ok or agl_processed_ok

            if not self._processing_checkpoint(
                self.tr("Finalising generated layers and report..."),
                self._processing_total_steps,
                self._processing_total_steps,
                phase_key="finalisation",
            ):
                return
            self._write_runway_summary_report(icao_code, processed_runway_data_list)
            self._repair_output_layer_tree(main_group)
            self._remove_empty_generated_groups(main_group)

            self._final_feedback(
                main_group,
                root,
                icao_code,
                len(processed_runway_data_list),
                len(runway_input_list),
            )

            self._processing_run_status = (
                "completed" if self.successfully_generated_layers else "failed"
            )

            if self.successfully_generated_layers:
                if self.dlg:
                    self._set_processing_status(
                        self.tr("Generation complete. Closing dialog..."),
                        step=self._processing_total_steps,
                        total_steps=self._processing_total_steps,
                    )
                    self.dlg.accept()
            else:
                self._clear_processing_status()

    def _begin_processing_progress(self, total_steps: int) -> None:
        if self.dlg is not None and hasattr(self.dlg, "begin_processing"):
            self.dlg.begin_processing(total_steps)
        QCoreApplication.processEvents()

    def _processing_cancel_requested(self) -> bool:
        return bool(
            self.dlg is not None
            and hasattr(self.dlg, "is_processing_cancel_requested")
            and self.dlg.is_processing_cancel_requested()
        )

    def _processing_checkpoint(
        self,
        message: str,
        step: int,
        total_steps: int,
        phase_key: Optional[str] = None,
    ) -> bool:
        """Enter a phase unless cancellation was requested during the previous phase."""
        QCoreApplication.processEvents()
        if self._processing_cancel_requested():
            self._finish_processing_cancelled()
            return False
        recorder = getattr(self, "_runtime_run_recorder", None)
        if recorder is not None and phase_key:
            recorder.start_phase(phase_key)
        run_log = getattr(self, "_run_log", None)
        if run_log is not None and phase_key and run_log.started:
            run_log.phase(
                step,
                total_steps,
                phase_key,
                message.rstrip(". …"),
            )
        self._set_processing_status(message, step=step, total_steps=total_steps)
        return True

    def _finish_processing_cancelled(self) -> None:
        """Keep completed layers and make a partial run safe to inspect or restart."""
        self._processing_run_status = "cancelled"
        main_group = getattr(self, "_processing_main_group", None)
        if main_group is not None:
            try:
                self._repair_output_layer_tree(main_group)
                self._remove_empty_generated_groups(main_group)
            except Exception as exc:
                self._log_warning(f"Cancellation cleanup warning: {exc}")
        if self._run_log is not None:
            self._run_log.update_context(
                reason="cancelled at a safe phase boundary; completed layers were kept"
            )
        if self.iface is not None:
            self.iface.messageBar().pushMessage(
                self.tr("Cancelled"),
                self.tr("Generation stopped after the current phase. Completed layers were kept."),
                level=Qgis.Info,
                duration=6,
            )
        self._clear_processing_status(
            self.tr("Generation cancelled — completed layers were kept.")
        )

    def _set_processing_status(
        self,
        message: str,
        step: Optional[int] = None,
        total_steps: Optional[int] = None,
    ) -> None:
        if self.dlg is not None and hasattr(self.dlg, "set_processing_status"):
            self.dlg.set_processing_status(message, step=step, total_steps=total_steps)
        QCoreApplication.processEvents()

    def _clear_processing_status(self, final_message: Optional[str] = None) -> None:
        if self.dlg is not None and hasattr(self.dlg, "clear_processing_status"):
            self.dlg.clear_processing_status(final_message=final_message)
        QCoreApplication.processEvents()

    # ============================================================
    # Helper Methods
    # ============================================================

    def _process_airport_safeguarding(
        self,
        arp_point: Optional[QgsPointXY],
        cns_input_list: List[dict],
        icao_code: str,
        target_crs: QgsCoordinateReferenceSystem,
        guideline_groups: Dict[str, Optional[QgsLayerTreeGroup]],
    ) -> Tuple[bool, bool, bool]:
        plugin_tag = PLUGIN_TAG
        wildlife_processed = False
        wind_turbine_processed = False
        cns_processed = False
        if arp_point is not None and guideline_groups.get("C") is not None:
            self._diagnostic(
                f"Wildlife safeguarding: generating from ARP "
                f"({arp_point.x():.3f}, {arp_point.y():.3f})."
            )
            wildlife_processed = self.process_wildlife_safeguarding(
                arp_point,
                icao_code,
                target_crs,
                guideline_groups["C"],
            )
            if not wildlife_processed:
                self._log_warning(
                    "Wildlife safeguarding failed: no zone layers were created. Check preceding Wildlife messages."
                )
        elif arp_point is None and guideline_groups.get("C") is not None:
            self._log_skip("Wildlife safeguarding: ARP coordinates missing; wildlife zones not generated.")

        if arp_point is not None and guideline_groups.get("D") is not None:
            wind_turbine_processed = self.process_wind_turbine_safeguarding(
                arp_point,
                icao_code,
                target_crs,
                guideline_groups["D"],
            )
        elif arp_point is None and guideline_groups.get("D") is not None:
            self._log_skip("Wind turbine safeguarding: ARP coordinates missing; turbine zone not generated.")

        if cns_input_list and guideline_groups.get("G") is not None:
            try:
                cns_processed = self.process_cns_building_restricted_areas(
                    cns_input_list, icao_code, target_crs, guideline_groups["G"]
                )
            except Exception as e_proc_g:
                QgsMessageLog.logMessage(
                    f"Critical error processing CNS building restricted areas: {e_proc_g}\n{traceback.format_exc()}",
                    plugin_tag,
                    level=Qgis.Critical,
                )
        elif not cns_input_list:
            self._log_skip("CNS building restricted areas: no valid CNS facilities data provided.")

        return wildlife_processed, wind_turbine_processed, cns_processed

    def _process_airport_wide_ols_if_possible(
        self,
        guideline_groups: Dict[str, Optional[QgsLayerTreeGroup]],
        processed_runway_data_list: List[dict],
        icao_code: str,
        any_guideline_processed_ok: bool,
        airport_wide_ols_group: Optional[QgsLayerTreeGroup] = None,
    ) -> bool:
        plugin_tag = PLUGIN_TAG
        airport_wide_ols_processed = False
        if (
            getattr(self.get_active_protected_airspace_ruleset(), "protected_airspace_model", "")
            == "annex14_modernised_ofs_oes"
        ):
            self._log_skip("Airport-wide current OLS: protected airspace policy is future Annex 14 OFS/OES.")
            return False
        active_context = getattr(self, "ols_construction_context", None)
        active_policy = self.get_active_protected_airspace_ruleset().ols_construction_policy()
        airport_spec = (
            active_policy.airport_wide_spec(
                self.get_active_protected_airspace_ruleset(),
                active_context,
            )
            if active_context is not None
            else {}
        )
        airport_wide_datum = airport_spec.get(
            "datum_elevation_m",
            self.reference_elevation_datum,
        )
        context_runways = (
            active_context.generation_runways()
            if active_context is not None
            else processed_runway_data_list
        )
        if guideline_groups.get("F") is not None and context_runways:
            if airport_spec.get("ihs_elevation_amsl") is not None:
                try:
                    airport_wide_ols_processed = self._generate_airport_wide_ols(
                        context_runways,
                        airport_wide_ols_group or guideline_groups["F"],
                        float(airport_wide_datum or 0.0),
                        icao_code,
                        guideline_groups["F"],
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
                        self.tr("Failed to generate airport-wide OLS surfaces. Check logs."),
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
                reciprocal_num = (designator_num + 18) if designator_num <= 18 else (designator_num - 18)
                reciprocal_suffix_map = {"L": "R", "R": "L", "C": "C", "": ""}
                reciprocal_suffix = reciprocal_suffix_map.get(suffix, "")
                reciprocal_desig = f"{reciprocal_num:02d}{reciprocal_suffix}"
                short_runway_name = f"{primary_desig}/{reciprocal_desig}"
                runway_data["short_name"] = short_runway_name
                runway_data["declared_distances"] = self._calculate_declared_distances(runway_data)
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
                    runway_data.get("design_group") or runway_data.get("adg"),
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

        return processed_runway_data_list, any_runway_base_data_ok

    def _write_runway_summary_report(
        self, icao_code: str, processed_runway_data_list: List[Dict[str, Any]]
    ) -> Optional[str]:
        """Write the Critical Runway Information Summary Markdown report."""
        if not processed_runway_data_list:
            self._log_skip("Runway summary report: no processed runway data.")
            return None
        if self.output_mode != "file":
            self._log("Runway summary report not written: select file output to create the Markdown report.")
            return None
        if not self.output_path:
            self._log_warning("[skip] Runway summary report: file output path is not available.")
            return None

        safe_icao = self._sanitize_filename(icao_code or "UNKNOWN")
        report_path = os.path.join(self.output_path, f"{safe_icao}_Critical_Runway_Information_Summary.md")
        try:
            summaries = build_runway_summaries(processed_runway_data_list)
            markdown = render_markdown_report(icao_code, None, summaries)
            with open(report_path, "w", encoding="utf-8") as report_file:
                report_file.write(markdown)
            self._diagnostic(f"Runway summary report written to '{report_path}'.")
            return report_path
        except Exception as e:
            self._log_warning(f"Runway summary report failed: {e}\n{traceback.format_exc()}")
            return None

    def _calculate_declared_distances(
        self,
        runway_data: Dict[str, Any],
        ruleset=None,
    ) -> List[Dict[str, Any]]:
        """Calculate baseline declared distances for both runway directions."""
        runway_name = runway_data.get("short_name", f"RWY_{runway_data.get('original_index', '?')}")
        thr_point = runway_data.get("thr_point")
        rec_thr_point = runway_data.get("rec_thr_point")
        if thr_point is None or rec_thr_point is None:
            return []

        rwy_params = self._get_runway_parameters(thr_point, rec_thr_point)
        if rwy_params is None:
            return []

        disp_primary = self._non_negative_float(runway_data.get("thr_displaced_1"), 0.0)
        disp_reciprocal = self._non_negative_float(runway_data.get("thr_displaced_2"), 0.0)
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

        clearway_specs = self._calculate_effective_clearway_specs(
            runway_data,
            physical_length,
            ruleset=ruleset,
        )
        clearway_primary_end = clearway_specs["primary"]["length_m"]
        clearway_reciprocal_end = clearway_specs["reciprocal"]["length_m"]
        clearway_primary_input = self._non_negative_float(runway_data.get("clearway1_len"), 0.0)
        clearway_reciprocal_input = self._non_negative_float(runway_data.get("clearway2_len"), 0.0)
        stopway_primary_end = self._non_negative_float(runway_data.get("stopway1_len"), 0.0)
        stopway_reciprocal_end = self._non_negative_float(runway_data.get("stopway2_len"), 0.0)

        primary_takeoff_available = self._bool_from_runway_data(runway_data.get("takeoff_available_1", True))
        reciprocal_takeoff_available = self._bool_from_runway_data(runway_data.get("takeoff_available_2", True))
        primary_landing_available = self._bool_from_runway_data(runway_data.get("landing_available_1", True))
        reciprocal_landing_available = self._bool_from_runway_data(runway_data.get("landing_available_2", True))

        primary_tora = physical_length if primary_takeoff_available else None
        reciprocal_tora = physical_length if reciprocal_takeoff_available else None
        primary_lda = threshold_length + disp_reciprocal if primary_landing_available else None
        reciprocal_lda = threshold_length + disp_primary if reciprocal_landing_available else None

        records = [
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
                "clearway_input_m": clearway_reciprocal_input,
                "stopway_m": stopway_reciprocal_end,
                "stopway_input_m": stopway_reciprocal_end,
                "takeoff_available": primary_takeoff_available,
                "landing_available": primary_landing_available,
                "tora_m": primary_tora,
                "toda_m": (primary_tora + clearway_reciprocal_end if primary_tora is not None else None),
                "asda_m": (primary_tora + stopway_reciprocal_end if primary_tora is not None else None),
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
                "clearway_input_m": clearway_primary_input,
                "stopway_m": stopway_primary_end,
                "stopway_input_m": stopway_primary_end,
                "takeoff_available": reciprocal_takeoff_available,
                "landing_available": reciprocal_landing_available,
                "tora_m": reciprocal_tora,
                "toda_m": (reciprocal_tora + clearway_primary_end if reciprocal_tora is not None else None),
                "asda_m": (reciprocal_tora + stopway_primary_end if reciprocal_tora is not None else None),
                "lda_m": reciprocal_lda,
            },
        ]
        records = self._apply_declared_distance_policy(records, ruleset=ruleset)
        records = apply_declared_distance_overrides(runway_data, records)
        warnings = annotate_declared_distance_warnings(runway_data, records)
        if warnings:
            existing_warnings = list(runway_data.get("summary_warnings") or [])
            runway_data["summary_warnings"] = sorted(set(existing_warnings + warnings))
            for warning in warnings:
                QgsMessageLog.logMessage(warning, PLUGIN_TAG, level=Qgis.Warning)
        return records

    def _apply_declared_distance_policy(
        self,
        records: List[Dict[str, Any]],
        ruleset=None,
    ) -> List[Dict[str, Any]]:
        active_ruleset = ruleset or self.get_active_ruleset()
        declared_distance_parameters = getattr(active_ruleset, "declared_distance_parameters", None)
        if not callable(declared_distance_parameters):
            return records

        params = declared_distance_parameters() or {}
        if params.get("rounding") != "nearest_metre":
            return records

        distance_keys = params.get("distance_keys", ())
        for record in records:
            for key in distance_keys:
                value = record.get(key)
                if value is not None:
                    record[key] = round(float(value))
        return records

    def _calculate_effective_clearway_specs(
        self,
        runway_data: Dict[str, Any],
        physical_length: Optional[float] = None,
        ruleset=None,
    ) -> Dict[str, Dict[str, Any]]:
        """Return clearway specs under the explicitly selected ruleset."""
        cached_specs = runway_data.get("_effective_clearway_specs")
        ruleset = ruleset or self.get_active_ruleset()
        ruleset_id = getattr(ruleset, "id", None)
        if (
            isinstance(cached_specs, dict)
            and "primary" in cached_specs
            and "reciprocal" in cached_specs
            and cached_specs.get("ruleset_id") == ruleset_id
        ):
            return cached_specs

        runway_name = runway_data.get("short_name", f"RWY_{runway_data.get('original_index', '?')}")
        runway_width = self._non_negative_float(runway_data.get("width"), 0.0)
        try:
            arc_num = int(float(runway_data.get("arc_num") or 0))
        except (TypeError, ValueError):
            arc_num = 0

        type1_abbr = ruleset.classify_runway_type(runway_data.get("type1"))
        type2_abbr = ruleset.classify_runway_type(runway_data.get("type2"))
        is_instrument_runway = type1_abbr in {"NPA", "PA_I", "PA_II_III"} or type2_abbr in {
            "NPA",
            "PA_I",
            "PA_II_III",
        }

        strip_dims = (
            runway_data.get("calculated_strip_dims")
            if runway_data.get("_calculated_strip_ruleset_id") in {None, ruleset_id}
            else None
        )
        if not strip_dims:
            strip_dims = ruleset.strip_parameters(arc_num, type1_abbr, runway_width or None)
            runway_data["calculated_strip_dims"] = strip_dims
            runway_data["_calculated_strip_ruleset_id"] = ruleset_id

        strip_extension = self._non_negative_float((strip_dims or {}).get("extension_length"), 0.0)
        strip_overall_width = self._non_negative_float((strip_dims or {}).get("overall_width"), 0.0)

        clearway_parameters = getattr(ruleset, "clearway_parameters", None)
        if callable(clearway_parameters):
            profile_specs = clearway_parameters(
                runway_width=runway_width or None,
                strip_extension=strip_extension,
                strip_overall_width=strip_overall_width,
                physical_length=physical_length,
                clearway_primary_input=self._non_negative_float(runway_data.get("clearway1_len"), 0.0),
                clearway_reciprocal_input=self._non_negative_float(runway_data.get("clearway2_len"), 0.0),
                stopway_primary=self._non_negative_float(runway_data.get("stopway1_len"), 0.0),
                stopway_reciprocal=self._non_negative_float(runway_data.get("stopway2_len"), 0.0),
                is_instrument_runway=is_instrument_runway,
                arc_num=arc_num,
            )
        else:
            profile_specs = None

        if (
            isinstance(profile_specs, dict)
            and isinstance(profile_specs.get("primary"), dict)
            and isinstance(profile_specs.get("reciprocal"), dict)
        ):
            specs = profile_specs
            specs["ruleset_id"] = ruleset_id
            for end_key in ("primary", "reciprocal"):
                end_spec = specs.get(end_key, {})
                if end_spec.get("capped"):
                    max_length_m = end_spec.get("max_length_m")
                    QgsMessageLog.logMessage(
                        f"Clearway length for {runway_name} {end_key} end "
                        f"({end_spec.get('input_length_m', 0.0):.3f} m) exceeds half the TORA "
                        f"({max_length_m:.3f} m); capping to {end_spec.get('ref', 'active ruleset')}.",
                        PLUGIN_TAG,
                        level=Qgis.Warning,
                    )
            runway_data["_effective_clearway_specs"] = specs
            runway_data["effective_clearway1_len"] = specs["primary"]["length_m"]
            runway_data["effective_clearway2_len"] = specs["reciprocal"]["length_m"]
            runway_data["effective_clearway_width_m"] = max(
                specs["primary"].get("width_m", 0.0),
                specs["reciprocal"].get("width_m", 0.0),
            )
            return specs

        clearway_width = 150.0 if is_instrument_runway else strip_overall_width
        if clearway_width <= 1e-6 and runway_width > 0:
            clearway_width = runway_width
            QgsMessageLog.logMessage(
                f"Clearway width for {runway_name} fell back to runway width because strip width was unavailable.",
                PLUGIN_TAG,
                level=Qgis.Warning,
            )

        max_clearway_length = None
        if physical_length is not None and physical_length > 0:
            max_clearway_length = physical_length / 2.0

        def end_spec(end_key: str, input_key: str, stopway_key: str) -> Dict[str, Any]:
            input_length = self._non_negative_float(runway_data.get(input_key), 0.0)
            default_length = strip_extension + self._non_negative_float(runway_data.get(stopway_key), 0.0)
            effective_length = max(input_length, default_length)
            source = "input" if input_length >= default_length and input_length > 1e-6 else "runway-strip default"

            if input_length > 1e-6 and input_length < default_length:
                QgsMessageLog.logMessage(
                    f"Clearway input for {runway_name} {end_key} end ({input_length:.3f} m) is shorter than "
                    f"the default runway-to-strip-end distance ({default_length:.3f} m); using the default.",
                    PLUGIN_TAG,
                    level=Qgis.Warning,
                )

            if max_clearway_length is not None and effective_length > max_clearway_length:
                QgsMessageLog.logMessage(
                    f"Clearway length for {runway_name} {end_key} end ({effective_length:.3f} m) exceeds "
                    f"half the TORA ({max_clearway_length:.3f} m); capping to MOS 6.29(1).",
                    PLUGIN_TAG,
                    level=Qgis.Warning,
                )
                effective_length = max_clearway_length
                source = f"{source}; capped"

            return {
                "length_m": round(effective_length, 3),
                "width_m": round(clearway_width, 3),
                "input_length_m": round(input_length, 3),
                "default_length_m": round(default_length, 3),
                "source": source,
                "ref_mos": "MOS 6.27; MOS 6.28; MOS 6.29",
            }

        specs = {
            "primary": end_spec("primary", "clearway1_len", "stopway1_len"),
            "reciprocal": end_spec("reciprocal", "clearway2_len", "stopway2_len"),
            "ruleset_id": ruleset_id,
        }
        runway_data["_effective_clearway_specs"] = specs
        runway_data["effective_clearway1_len"] = specs["primary"]["length_m"]
        runway_data["effective_clearway2_len"] = specs["reciprocal"]["length_m"]
        runway_data["effective_clearway_width_m"] = clearway_width
        return specs

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

    def _ensure_layer_group(
        self,
        parent_group: QgsLayerTreeGroup,
        name: str,
    ) -> Optional[QgsLayerTreeGroup]:
        """Find or create a child group and stage it for generated output."""
        if parent_group is None:
            return None
        group = self._find_direct_child_group(parent_group, self.tr(name))
        if group is None:
            group = parent_group.addGroup(self.tr(name))
        self._stage_layer_tree_node(group)
        return group

    def _baseline_ols_group_name(self) -> str:
        """Return the layer-tree label for the selected baseline ruleset."""
        profile = getattr(self, "baseline_ols_ruleset", None)
        display_name = getattr(profile, "display_name", None) or self.tr("Selected ruleset")
        return self.tr(f"Baseline OLS — {display_name}")

    def _find_direct_child_group(
        self,
        parent_group: QgsLayerTreeGroup,
        name: str,
    ) -> Optional[QgsLayerTreeGroup]:
        """Return a direct child group by name without recursively searching other branches."""
        if parent_group is None:
            return None
        for child in parent_group.children():
            if isinstance(child, QgsLayerTreeGroup) and child.name() == name:
                return child
        return None

    def _create_output_layer_groups(
        self,
        main_group: QgsLayerTreeGroup,
        agl_enabled: bool,
    ) -> Dict[str, Optional[QgsLayerTreeGroup]]:
        """Create the main generated layer tree sections in display order."""
        groups: Dict[str, Optional[QgsLayerTreeGroup]] = {}
        groups["reference_data"] = self._ensure_layer_group(main_group, output_structure.REFERENCE_DATA)
        groups["aerodrome_infrastructure"] = self._ensure_layer_group(
            main_group, output_structure.AERODROME_INFRASTRUCTURE
        )
        groups["runway_protection_and_separation"] = self._ensure_layer_group(
            main_group, output_structure.RUNWAY_PROTECTION_AND_SEPARATION
        )
        groups["protected_airspace"] = self._ensure_layer_group(main_group, output_structure.PROTECTED_AIRSPACE)
        groups["external_safeguarding"] = self._ensure_layer_group(
            main_group, self.get_active_framework().safeguarding_group_name()
        )
        groups["nasf_guidelines"] = groups["external_safeguarding"]
        groups["debug_development"] = self._ensure_layer_group(main_group, output_structure.DEBUG_DEVELOPMENT)

        infrastructure_group = groups["aerodrome_infrastructure"]
        if infrastructure_group is not None:
            if agl_enabled:
                groups["airfield_ground_lighting"] = self._ensure_layer_group(
                    infrastructure_group, output_structure.AIRFIELD_GROUND_LIGHTING
                )
            groups["markings"] = self._ensure_layer_group(infrastructure_group, output_structure.MARKINGS)
            groups["physical_geometry"] = self._ensure_layer_group(
                infrastructure_group, output_structure.PHYSICAL_GEOMETRY
            )

        protection_group = groups["runway_protection_and_separation"]
        if protection_group is not None:
            groups["runway_protection_areas"] = self._ensure_layer_group(
                protection_group, output_structure.RUNWAY_PROTECTION_AREAS
            )
            groups["specialised_safeguarding"] = self._ensure_layer_group(
                protection_group, output_structure.SPECIALISED_RUNWAY_SAFEGUARDING
            )
        protected_airspace_group = groups["protected_airspace"]
        if protected_airspace_group is not None:
            baseline_surface_group = self._ensure_layer_group(
                protected_airspace_group,
                self._baseline_ols_group_name(),
            )
            groups["baseline_ols"] = baseline_surface_group
            if self._is_future_annex14_protected_airspace():
                groups["ols_surfaces"] = self._ensure_layer_group(baseline_surface_group, "OFS")
                groups["airport_wide_ols"] = self._ensure_layer_group(baseline_surface_group, "OES")
            else:
                groups["obstacle_free_zone"] = self._ensure_layer_group(
                    baseline_surface_group, output_structure.OBSTACLE_FREE_ZONE
                )
                groups["ols_surfaces"] = self._ensure_layer_group(
                    baseline_surface_group, output_structure.PRIMARY_SURFACES
                )
                groups["airport_wide_ols"] = self._ensure_layer_group(
                    baseline_surface_group, output_structure.SECONDARY_SURFACES
                )
                groups["controlling_surfaces"] = self._ensure_layer_group(
                    baseline_surface_group, output_structure.CONTROLLING_SURFACES
                )
                groups["controlling_ols_surfaces"] = groups["controlling_surfaces"]
                groups["controlling_contours"] = groups["controlling_surfaces"]
            comparison_ruleset = getattr(self, "comparison_ols_ruleset", None)
            if comparison_ruleset is not None:
                comparison_surface_group = self._ensure_layer_group(
                    protected_airspace_group,
                    f"Comparison OLS — {comparison_ruleset.display_name}",
                )
                comparison_is_annex14 = (
                    getattr(comparison_ruleset, "protected_airspace_model", "")
                    == "annex14_modernised_ofs_oes"
                )
                if comparison_is_annex14:
                    groups["comparison_ols_surfaces"] = self._ensure_layer_group(
                        comparison_surface_group,
                        "OFS",
                    )
                    groups["comparison_airport_wide_ols"] = self._ensure_layer_group(
                        comparison_surface_group,
                        "OES",
                    )
                    groups["comparison_controlling_surfaces"] = comparison_surface_group
                else:
                    groups["comparison_obstacle_free_zone"] = self._ensure_layer_group(
                        comparison_surface_group,
                        output_structure.OBSTACLE_FREE_ZONE,
                    )
                    groups["comparison_ols_surfaces"] = self._ensure_layer_group(
                        comparison_surface_group,
                        output_structure.PRIMARY_SURFACES,
                    )
                    groups["comparison_airport_wide_ols"] = self._ensure_layer_group(
                        comparison_surface_group,
                        output_structure.SECONDARY_SURFACES,
                    )
                    groups["comparison_controlling_surfaces"] = self._ensure_layer_group(
                        comparison_surface_group,
                        output_structure.CONTROLLING_SURFACES,
                    )

                result_group = self._ensure_layer_group(
                    protected_airspace_group,
                    "OLS Ruleset Comparison",
                )
                baseline_is_annex14 = self._is_future_annex14_protected_airspace()
                if baseline_is_annex14 or comparison_is_annex14:
                    groups["comparison_result_ofs"] = self._ensure_layer_group(
                        result_group,
                        "OFS — Protected Airspace Change",
                    )
                    groups["comparison_result_oes"] = self._ensure_layer_group(
                        result_group,
                        "OES — Assessment Trigger Change",
                    )
                    groups["comparison_ofs"] = groups["comparison_result_ofs"]
                    groups["comparison_oes"] = groups["comparison_result_oes"]
                else:
                    groups["comparison_result_ols"] = self._ensure_layer_group(
                        result_group,
                        "OLS — Protected Airspace Change",
                    )
        return groups

    def _is_future_annex14_protected_airspace(self) -> bool:
        return (
            getattr(self.get_active_protected_airspace_ruleset(), "protected_airspace_model", "")
            == "annex14_modernised_ofs_oes"
        )

    def _is_modernisation_comparison(self) -> bool:
        comparison_ruleset = getattr(self, "comparison_ols_ruleset", None)
        return (
            comparison_ruleset is not None
            and getattr(comparison_ruleset, "protected_airspace_model", "")
            == "annex14_modernised_ofs_oes"
            and not self._is_future_annex14_protected_airspace()
        )

    def _run_ols_ruleset_comparison(
        self,
        icao_code: str,
        processed_runway_data_list: List[dict],
        output_groups: Dict[str, Optional[QgsLayerTreeGroup]],
        debug_group: QgsLayerTreeGroup,
        solved_baseline_engines: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Generate the selected comparison ruleset and compare solved envelopes."""
        comparison_ruleset = getattr(self, "comparison_ols_ruleset", None)
        if comparison_ruleset is None:
            return False
        if self._is_modernisation_comparison():
            return self._run_modernisation_comparison(
                icao_code,
                processed_runway_data_list,
                output_groups,
                debug_group,
                solved_baseline_engine=(solved_baseline_engines or {}).get("baseline"),
            )

        baseline_candidates = list(getattr(self, "_controlling_ols_candidates", []) or [])
        baseline_exclusions = list(
            getattr(self, "_controlling_ols_exclusion_geometries", []) or []
        )
        comparison_primary_group = output_groups.get("comparison_ols_surfaces")
        comparison_secondary_group = output_groups.get("comparison_airport_wide_ols")
        comparison_ofz_group = output_groups.get("comparison_obstacle_free_zone")
        comparison_controlling_group = output_groups.get("comparison_controlling_surfaces")
        if comparison_primary_group is None or comparison_secondary_group is None:
            self._log_warning("[skip] OLS ruleset comparison: comparison output groups are unavailable.")
            return False
        if not baseline_candidates:
            self._log_warning("[skip] OLS ruleset comparison: baseline envelope is empty.")
            return False

        original_protected_ruleset = self.protected_airspace_ruleset
        original_ols_context = getattr(self, "ols_construction_context", None)
        original_contour_role = getattr(
            self, "_contour_interval_ruleset_role", "baseline"
        )
        try:
            self.protected_airspace_ruleset = comparison_ruleset
            self._contour_interval_ruleset_role = "comparison"
            comparison_context = self._build_ols_construction_context(
                comparison_ruleset,
                processed_runway_data_list,
                arp_point=getattr(self, "_ols_arp_point", None),
            )
            self._ols_construction_contexts[comparison_ruleset.id] = comparison_context
            if not self._activate_ols_construction_context(
                comparison_ruleset,
                comparison_context,
            ):
                return False
            comparison_runways = (
                processed_runway_data_list
                if getattr(comparison_ruleset, "protected_airspace_model", "")
                == "annex14_modernised_ofs_oes"
                else comparison_context.generation_runways()
            )
            self._reset_controlling_ols_engine()
            comparison_is_annex14 = self._is_future_annex14_protected_airspace()
            geometry_created = False
            runway_total = len(comparison_runways)
            for runway_index, runway_data in enumerate(comparison_runways, start=1):
                self._set_processing_status(
                    self.tr(
                        f"Comparison OLS: creating {comparison_ruleset.display_name} candidates "
                        f"({runway_index}/{runway_total})..."
                    )
                )
                if self._processing_cancel_requested():
                    return geometry_created
                if comparison_is_annex14:
                    created = self.process_annex14_geometry(
                        runway_data,
                        comparison_primary_group,
                        comparison_secondary_group,
                    )
                else:
                    created = self.process_runway_ols_surfaces(
                        runway_data,
                        comparison_primary_group,
                        comparison_ofz_group,
                    )
                geometry_created = created or geometry_created

            if (
                not comparison_is_annex14
                and comparison_context is not None
            ):
                comparison_spec = comparison_ruleset.ols_construction_policy().airport_wide_spec(
                    comparison_ruleset,
                    comparison_context,
                )
                geometry_created = self._generate_airport_wide_ols(
                    comparison_runways,
                    comparison_secondary_group,
                    float(comparison_spec.get("datum_elevation_m") or 0.0),
                    icao_code,
                    comparison_primary_group,
                ) or geometry_created

            comparison_candidates = list(
                getattr(self, "_controlling_ols_candidates", []) or []
            )
            comparison_exclusions = list(
                getattr(self, "_controlling_ols_exclusion_geometries", []) or []
            )
            if not geometry_created or not comparison_candidates:
                self._log_warning(
                    "[skip] OLS ruleset comparison: the comparison ruleset produced no candidates."
                )
                return False

            solved_comparison_engines: Dict[str, Any] = {}
            if comparison_is_annex14:
                controlling_created = self._create_annex14_controlling_surface_layers(
                    icao_code,
                    comparison_primary_group,
                    comparison_secondary_group,
                    debug_group,
                    solved_engines=solved_comparison_engines,
                )
            else:
                controlling_created = self._create_controlling_ols_layers(
                    icao_code,
                    debug_group,
                    comparison_controlling_group,
                    comparison_controlling_group,
                    solved_engines=solved_comparison_engines,
                )
            if self._processing_cancel_requested():
                return controlling_created

            comparison_groups = {
                "OFS": output_groups.get("comparison_result_ofs"),
                "OES": output_groups.get("comparison_result_oes"),
                "OLS": output_groups.get("comparison_result_ols"),
            }
            comparison_created = self._create_ols_ruleset_comparison_layers(
                icao_code=icao_code,
                baseline_ruleset_id=self.baseline_ols_ruleset.id,
                comparison_ruleset_id=comparison_ruleset.id,
                baseline_model=getattr(
                    self.baseline_ols_ruleset,
                    "protected_airspace_model",
                    "ols_current",
                ),
                comparison_model=getattr(
                    comparison_ruleset,
                    "protected_airspace_model",
                    "ols_current",
                ),
                baseline_candidates=baseline_candidates,
                baseline_exclusions=baseline_exclusions,
                comparison_candidates=comparison_candidates,
                comparison_exclusions=comparison_exclusions,
                output_groups=comparison_groups,
                solved_baseline_engines=solved_baseline_engines,
                solved_comparison_engines=solved_comparison_engines,
            )
            return controlling_created or comparison_created
        finally:
            self.protected_airspace_ruleset = original_protected_ruleset
            self.ols_construction_context = original_ols_context
            self._contour_interval_ruleset_role = original_contour_role

    def _run_modernisation_comparison(
        self,
        icao_code: str,
        processed_runway_data_list: List[dict],
        output_groups: Dict[str, Optional[QgsLayerTreeGroup]],
        debug_group: QgsLayerTreeGroup,
        solved_baseline_engine=None,
    ) -> bool:
        """Generate future OFS/OES beside the selected baseline and compare envelopes."""
        baseline_candidates = list(getattr(self, "_controlling_ols_candidates", []) or [])
        baseline_exclusions = list(getattr(self, "_controlling_ols_exclusion_geometries", []) or [])
        future_ofs_group = output_groups.get("comparison_ols_surfaces")
        future_oes_group = output_groups.get("comparison_airport_wide_ols")
        comparison_ofs_group = output_groups.get("comparison_ofs")
        comparison_oes_group = output_groups.get("comparison_oes")
        if any(
            group is None
            for group in (future_ofs_group, future_oes_group, comparison_ofs_group, comparison_oes_group)
        ):
            self._log_warning("[skip] OLS modernisation comparison: output groups are unavailable.")
            return False
        if not baseline_candidates:
            self._log_warning("[skip] OLS modernisation comparison: baseline envelope is empty.")
            return False

        original_protected_ruleset = self.protected_airspace_ruleset
        original_contour_role = getattr(
            self, "_contour_interval_ruleset_role", "baseline"
        )
        try:
            self.protected_airspace_ruleset = getattr(
                self,
                "comparison_ols_ruleset",
                None,
            ) or get_ruleset_profile("icao_annex14_vol1_modernised_ofs_oes")
            self._contour_interval_ruleset_role = "comparison"
            self._reset_controlling_ols_engine()
            future_geometry_created = False
            runway_total = len(processed_runway_data_list)
            for runway_index, runway_data in enumerate(processed_runway_data_list, start=1):
                self._set_processing_status(
                    self.tr(
                        f"Modernisation: creating future Annex 14 candidates ({runway_index}/{runway_total})..."
                    )
                )
                if self._processing_cancel_requested():
                    return future_geometry_created
                future_geometry_created = self.process_annex14_geometry(
                    runway_data,
                    future_ofs_group,
                    future_oes_group,
                ) or future_geometry_created
            future_candidates = list(getattr(self, "_controlling_ols_candidates", []) or [])
            if not future_geometry_created or not future_candidates:
                self._log_warning(
                    "[skip] OLS modernisation comparison: future Annex 14 produced no candidates. "
                    "Check ADG and runway operational inputs."
                )
                return False
            solved_future_engines: Dict[str, Any] = {}
            future_controlling_created = self._create_annex14_controlling_surface_layers(
                icao_code,
                future_ofs_group,
                future_oes_group,
                debug_group,
                solved_engines=solved_future_engines,
            )
            if self._processing_cancel_requested():
                return future_controlling_created
            comparison_created = self._create_ols_modernisation_comparison_layers(
                icao_code,
                self.baseline_ols_ruleset.id,
                baseline_candidates,
                baseline_exclusions,
                future_candidates,
                comparison_ofs_group,
                comparison_oes_group,
                solved_baseline_engine=solved_baseline_engine,
                solved_future_engines=solved_future_engines,
                comparison_ruleset_id=self.comparison_ols_ruleset.id,
            )
            return future_controlling_created or comparison_created
        finally:
            self.protected_airspace_ruleset = original_protected_ruleset
            self._contour_interval_ruleset_role = original_contour_role

    def _move_layer_tree_node(
        self,
        node: QgsLayerTreeNode,
        destination_group: QgsLayerTreeGroup,
    ) -> bool:
        """Move a layer tree node by cloning it to a destination and removing the original."""
        if node is None or destination_group is None:
            return False
        parent = node.parent()
        if parent is None or parent == destination_group:
            return False
        try:
            if isinstance(node, QgsLayerTreeLayer):
                layer_id = node.layerId()
                if layer_id:
                    for child in destination_group.children():
                        if isinstance(child, QgsLayerTreeLayer) and child.layerId() == layer_id:
                            parent.removeChildNode(node)
                            return True
            cloned_node = node.clone()
            self._stage_layer_tree_node(cloned_node)
            destination_group.insertChildNode(len(destination_group.children()), cloned_node)
            parent.removeChildNode(node)
            return True
        except Exception as e:
            QgsMessageLog.logMessage(
                f"Warning: Failed to move layer tree node '{node.name()}': {e}",
                PLUGIN_TAG,
                level=Qgis.Warning,
            )
            return False

    def _merge_or_move_direct_group(
        self,
        parent_group: QgsLayerTreeGroup,
        source_group_name: str,
        destination_group: QgsLayerTreeGroup,
    ) -> bool:
        """Move a direct child group into a destination, merging with an existing child group if present."""
        source_group = self._find_direct_child_group(parent_group, source_group_name)
        if source_group is None or destination_group is None or source_group == destination_group:
            return False

        existing_destination_child = self._find_direct_child_group(destination_group, source_group_name)
        if existing_destination_child is None:
            return self._move_layer_tree_node(source_group, destination_group)

        moved_any = False
        for child in list(source_group.children()):
            moved_any = self._move_layer_tree_node(child, existing_destination_child) or moved_any
        try:
            parent_group.removeChildNode(source_group)
        except Exception as e:
            QgsMessageLog.logMessage(
                f"Warning: Failed to remove empty duplicate group '{source_group_name}': {e}",
                PLUGIN_TAG,
                level=Qgis.Warning,
            )
        return moved_any

    def _flatten_direct_child_group(self, parent_group: QgsLayerTreeGroup, group_name: str) -> bool:
        """Move a child group's contents into its parent and remove the empty wrapper."""
        source_group = self._find_direct_child_group(parent_group, group_name)
        if source_group is None or parent_group is None:
            return False

        moved_any = False
        for child in list(source_group.children()):
            moved_any = self._move_layer_tree_node(child, parent_group) or moved_any
        try:
            if not source_group.children():
                parent_group.removeChildNode(source_group)
        except Exception as e:
            QgsMessageLog.logMessage(
                f"Warning: Failed to remove flattened group '{group_name}': {e}",
                PLUGIN_TAG,
                level=Qgis.Warning,
            )
        return moved_any

    def _repair_output_layer_tree(self, main_group: QgsLayerTreeGroup) -> None:
        """Move known generated nodes into the reviewed layer hierarchy if QGIS added them at root level."""
        if main_group is None:
            return

        reference_group = self._ensure_layer_group(main_group, output_structure.REFERENCE_DATA)
        infrastructure_group = self._ensure_layer_group(main_group, output_structure.AERODROME_INFRASTRUCTURE)
        protection_group = self._ensure_layer_group(main_group, output_structure.RUNWAY_PROTECTION_AND_SEPARATION)
        protected_airspace_group = self._ensure_layer_group(main_group, output_structure.PROTECTED_AIRSPACE)
        baseline_surface_group = self._ensure_layer_group(
            protected_airspace_group,
            self._baseline_ols_group_name(),
        )
        if self._is_future_annex14_protected_airspace():
            obstacle_free_zone_group = None
            primary_surfaces_group = self._ensure_layer_group(baseline_surface_group, "OFS")
            secondary_surfaces_group = self._ensure_layer_group(baseline_surface_group, "OES")
            controlling_surfaces_group = baseline_surface_group
        else:
            obstacle_free_zone_group = self._ensure_layer_group(
                baseline_surface_group,
                output_structure.OBSTACLE_FREE_ZONE,
            )
            primary_surfaces_group = (
                self._ensure_layer_group(baseline_surface_group, output_structure.PRIMARY_SURFACES)
                if baseline_surface_group is not None
                else None
            )
            secondary_surfaces_group = self._ensure_layer_group(
                baseline_surface_group,
                output_structure.SECONDARY_SURFACES,
            )
            controlling_surfaces_group = self._ensure_layer_group(
                baseline_surface_group,
                output_structure.CONTROLLING_SURFACES,
            )
        framework = self.get_active_framework()
        external_group = self._ensure_layer_group(main_group, framework.safeguarding_group_name())
        debug_group = self._ensure_layer_group(main_group, output_structure.DEBUG_DEVELOPMENT)
        if (
            reference_group is None
            or infrastructure_group is None
            or protection_group is None
            or protected_airspace_group is None
            or baseline_surface_group is None
            or (
                not self._is_future_annex14_protected_airspace()
                and obstacle_free_zone_group is None
            )
            or primary_surfaces_group is None
            or secondary_surfaces_group is None
            or controlling_surfaces_group is None
            or external_group is None
            or debug_group is None
        ):
            return

        baseline_child_names = (
            output_structure.OBSTACLE_FREE_ZONE,
            output_structure.PRIMARY_SURFACES,
            output_structure.SECONDARY_SURFACES,
            output_structure.CONTROLLING_SURFACES,
            "OFS",
            "OES",
        )
        for child_name in baseline_child_names:
            self._merge_or_move_direct_group(
                protected_airspace_group,
                self.tr(child_name),
                baseline_surface_group,
            )

        for child in list(debug_group.children()):
            if not isinstance(child, QgsLayerTreeLayer):
                continue
            layer = child.layer()
            layer_name = layer.name() if layer is not None else child.name()
            style_key = str(layer.customProperty("safeguarding_style_key") or "") if layer is not None else ""
            if style_key == "OLS Controlling Planar Region" or "OLS Controlling Planar Regions" in layer_name:
                self._move_layer_tree_node(child, controlling_surfaces_group)
            elif style_key == "OLS Controlling Contour" or "OLS Controlling Contours" in layer_name:
                self._move_layer_tree_node(child, controlling_surfaces_group)

        runway_centreline_group = self._ensure_layer_group(reference_group, output_structure.RUNWAY_CENTRE_LINES)
        self._merge_or_move_direct_group(main_group, self.tr("Runway Centrelines"), reference_group)
        self._merge_or_move_direct_group(main_group, self.tr(output_structure.RUNWAY_CENTRE_LINES), reference_group)
        self._merge_or_move_direct_group(main_group, self.tr(output_structure.METEOROLOGICAL_STATION), reference_group)
        self._merge_or_move_direct_group(main_group, self.tr("CNS Facilities / Source Facilities"), reference_group)
        self._merge_or_move_direct_group(main_group, self.tr(output_structure.CNS_TECHNICAL_FACILITIES), reference_group)

        for child in list(main_group.children()):
            if not isinstance(child, QgsLayerTreeLayer):
                continue
            layer = child.layer()
            layer_name = layer.name() if layer is not None else child.name()
            style_key = layer.customProperty("safeguarding_style_key") if layer is not None else None
            if style_key == "ARP" or layer_name.endswith(f" {self.tr('ARP')}"):
                self._move_layer_tree_node(child, reference_group)
            elif "Centreline" in layer_name and runway_centreline_group is not None:
                self._move_layer_tree_node(child, runway_centreline_group)

        for group_name in [
            "Airfield Ground Lighting (AGL)",
            output_structure.AIRFIELD_GROUND_LIGHTING,
            output_structure.MARKINGS,
            output_structure.PHYSICAL_GEOMETRY,
        ]:
            self._merge_or_move_direct_group(main_group, self.tr(group_name), infrastructure_group)

        physical_geometry_group = self._find_group_by_path(
            main_group, [output_structure.AERODROME_INFRASTRUCTURE, output_structure.PHYSICAL_GEOMETRY]
        )
        if physical_geometry_group is not None and runway_centreline_group is not None:
            for child in list(physical_geometry_group.children()):
                if not isinstance(child, QgsLayerTreeLayer):
                    continue
                layer = child.layer()
                layer_name = layer.name() if layer is not None else child.name()
                style_key = str(layer.customProperty("safeguarding_style_key") or "") if layer is not None else ""
                if style_key == "Runway Centreline" or (
                    "Centreline" in layer_name and "Marking" not in layer_name
                ):
                    self._move_layer_tree_node(child, runway_centreline_group)

        for group_name in [
            output_structure.RUNWAY_PROTECTION_AREAS,
            output_structure.SPECIALISED_RUNWAY_SAFEGUARDING,
        ]:
            self._merge_or_move_direct_group(main_group, self.tr(group_name), protection_group)

        for group_name in framework.guideline_group_names(include_cns=True):
            self._merge_or_move_direct_group(main_group, self.tr(group_name), external_group)

        self._repair_debug_development_layer_tree(main_group, debug_group)

        legacy_guideline_f_name = self.tr("Guideline F - Airspace / OLS")
        self._merge_or_move_direct_group(main_group, legacy_guideline_f_name, primary_surfaces_group)
        legacy_guideline_f_group = self._find_direct_child_group(
            primary_surfaces_group, legacy_guideline_f_name
        )
        if legacy_guideline_f_group is not None:
            for child in list(legacy_guideline_f_group.children()):
                self._move_layer_tree_node(child, primary_surfaces_group)
            if not legacy_guideline_f_group.children():
                primary_surfaces_group.removeChildNode(legacy_guideline_f_group)
        for child in list(main_group.children()):
            if isinstance(child, QgsLayerTreeGroup) and re.fullmatch(r"RWY\s+\S+", child.name() or ""):
                self._merge_or_move_direct_group(main_group, child.name(), primary_surfaces_group)

        # Migrate the former OLS hierarchy and any legacy category groups into the
        # three reviewed folders without retaining extra wrapper levels.
        legacy_ols_names = [output_structure.OLS_SURFACES, "Annex 14 Future OLS Standard"]
        legacy_primary_names = [
            self.get_active_framework().guideline_f_subgroup_names()["runway"],
            "Future Annex 14 OLS Surfaces",
        ]
        legacy_ofz_names = [
            self.get_active_framework().guideline_f_subgroup_names()["ofz"],
        ]
        airport_wide_legacy_name = self.get_active_framework().guideline_f_subgroup_names()["airport_wide"]
        for legacy_name, destination in [
            (airport_wide_legacy_name, secondary_surfaces_group),
            *((name, primary_surfaces_group) for name in legacy_primary_names),
            *((name, obstacle_free_zone_group) for name in legacy_ofz_names),
        ]:
            if destination is None:
                continue
            legacy_group = self._find_direct_child_group(main_group, self.tr(legacy_name))
            if legacy_group is not None:
                for child in list(legacy_group.children()):
                    self._move_layer_tree_node(child, destination)
                if not legacy_group.children():
                    main_group.removeChildNode(legacy_group)
        for legacy_name in legacy_ols_names:
            legacy_group = self._find_direct_child_group(protected_airspace_group, self.tr(legacy_name))
            if legacy_group is None:
                continue
            airport_wide_name = self.tr(airport_wide_legacy_name)
            airport_wide_group = self._find_direct_child_group(legacy_group, airport_wide_name)
            if airport_wide_group is not None:
                for child in list(airport_wide_group.children()):
                    self._move_layer_tree_node(child, secondary_surfaces_group)
                if not airport_wide_group.children():
                    legacy_group.removeChildNode(airport_wide_group)
            for primary_name in legacy_primary_names:
                primary_group = self._find_direct_child_group(legacy_group, self.tr(primary_name))
                if primary_group is not None:
                    for child in list(primary_group.children()):
                        self._move_layer_tree_node(child, primary_surfaces_group)
                    if not primary_group.children():
                        legacy_group.removeChildNode(primary_group)
            for ofz_name in legacy_ofz_names:
                ofz_legacy_group = self._find_direct_child_group(
                    legacy_group, self.tr(ofz_name)
                )
                if ofz_legacy_group is not None and obstacle_free_zone_group is not None:
                    for child in list(ofz_legacy_group.children()):
                        self._move_layer_tree_node(child, obstacle_free_zone_group)
                    if not ofz_legacy_group.children():
                        legacy_group.removeChildNode(ofz_legacy_group)
            for child in list(legacy_group.children()):
                self._move_layer_tree_node(child, primary_surfaces_group)
            if not legacy_group.children():
                protected_airspace_group.removeChildNode(legacy_group)

        for legacy_name in [output_structure.CONTROLLING_OLS_SURFACES, output_structure.CONTROLLING_CONTOURS]:
            legacy_group = self._find_direct_child_group(protected_airspace_group, self.tr(legacy_name))
            if legacy_group is not None:
                for child in list(legacy_group.children()):
                    self._move_layer_tree_node(child, controlling_surfaces_group)
                if not legacy_group.children():
                    protected_airspace_group.removeChildNode(legacy_group)

        self._repair_guideline_f_layer_tree(
            primary_surfaces_group,
            secondary_surfaces_group,
            obstacle_free_zone_group,
            extra_source_groups=[main_group],
        )
        self._repair_debug_development_layer_tree(main_group, debug_group)

    def _is_legacy_diagnostic_layer(self, node: QgsLayerTreeLayer) -> bool:
        """Return True for legacy proof-of-concept layers that still need migration."""
        layer = node.layer()
        layer_name = layer.name() if layer is not None else node.name()
        style_key = str(layer.customProperty("safeguarding_style_key") or "") if layer is not None else ""
        if style_key in {"OLS Controlling Planar Region", "OLS Controlling Contour"} or any(
            production_name in layer_name
            for production_name in ["OLS Controlling Planar Regions", "OLS Controlling Contours"]
        ):
            return False
        return "POC" in layer_name

    def _repair_debug_development_layer_tree(
        self,
        root_group: QgsLayerTreeGroup,
        debug_group: QgsLayerTreeGroup,
    ) -> None:
        """Move legacy proof-of-concept layers into the diagnostic group."""
        if root_group is None or debug_group is None:
            return

        def visit(group: QgsLayerTreeGroup) -> None:
            for child in list(group.children()):
                if isinstance(child, QgsLayerTreeLayer):
                    if group != debug_group and self._is_legacy_diagnostic_layer(child):
                        self._move_layer_tree_node(child, debug_group)
                elif isinstance(child, QgsLayerTreeGroup) and child != debug_group:
                    visit(child)

        visit(root_group)

    def _repair_guideline_f_layer_tree(
        self,
        primary_surfaces_group: QgsLayerTreeGroup,
        secondary_surfaces_group: QgsLayerTreeGroup,
        obstacle_free_zone_group: Optional[QgsLayerTreeGroup] = None,
        extra_source_groups: Optional[List[QgsLayerTreeGroup]] = None,
    ) -> None:
        """Move direct OLS layers into the reviewed primary/secondary folders."""
        if primary_surfaces_group is None or secondary_surfaces_group is None:
            return

        airport_wide_style_keys = {
            "OLS IHS",
            "OLS Conical",
            "OLS Conical Contour",
            "OLS OHS",
            "OLS Transitional",
            "OLS Transitional Contour",
        }
        runway_style_keys = {
            "OLS Approach",
            "OLS Approach Contour",
            "OLS TOCS",
            "OLS TOCS Contour",
        }
        ofz_style_keys = {
            "OLS Inner Approach",
            "OLS Inner Transitional",
            "OLS Baulked Landing",
            "OLS OFZ Contour",
        }

        def ols_destination_for_node(node: QgsLayerTreeLayer) -> Optional[QgsLayerTreeGroup]:
            if self._is_legacy_diagnostic_layer(node):
                return None
            layer = node.layer()
            layer_name = layer.name() if layer is not None else node.name()
            style_key = str(layer.customProperty("safeguarding_style_key") or "") if layer is not None else ""

            if style_key in ofz_style_keys or any(
                label in layer_name
                for label in [
                    "OLS Inner Approach",
                    "OLS Inner Transitional",
                    "OLS Baulked Landing",
                ]
            ):
                if obstacle_free_zone_group is not None:
                    runway_match = re.search(r"\bRWY\s+(\S+)$", layer_name)
                    if runway_match:
                        return self._ensure_layer_group(
                            obstacle_free_zone_group,
                            f"RWY {runway_match.group(1)}",
                        )
                    return obstacle_free_zone_group
                return primary_surfaces_group
            if style_key in airport_wide_style_keys or any(
                label in layer_name
                for label in [
                    "OLS IHS",
                    "OLS Conical",
                    "OLS OHS",
                    "OLS Transitional",
                ]
            ):
                return secondary_surfaces_group
            if style_key in runway_style_keys or any(
                label in layer_name
                for label in [
                    "OLS Approach",
                    "OLS TOCS",
                ]
            ):
                return primary_surfaces_group
            return None

        if obstacle_free_zone_group is not None:
            for runway_group in list(primary_surfaces_group.children()):
                if not isinstance(runway_group, QgsLayerTreeGroup):
                    continue
                nested_ofz = self._find_direct_child_group(
                    runway_group, self.tr(output_structure.OBSTACLE_FREE_ZONE)
                )
                if nested_ofz is None:
                    continue
                destination_runway = self._ensure_layer_group(
                    obstacle_free_zone_group, runway_group.name()
                )
                for child in list(nested_ofz.children()):
                    self._move_layer_tree_node(child, destination_runway)
                if not nested_ofz.children():
                    runway_group.removeChildNode(nested_ofz)

        source_groups = [primary_surfaces_group, secondary_surfaces_group]
        if obstacle_free_zone_group is not None:
            source_groups.append(obstacle_free_zone_group)
        source_groups.extend(group for group in (extra_source_groups or []) if group is not None)
        for group in source_groups:
            for child in list(group.children()):
                if not isinstance(child, QgsLayerTreeLayer):
                    continue
                destination_group = ols_destination_for_node(child)
                if destination_group is not None and destination_group != group:
                    self._move_layer_tree_node(child, destination_group)

    def _create_guideline_groups(
        self,
        main_group: QgsLayerTreeGroup,
        include_cns: bool = True,
    ) -> Dict[str, Optional[QgsLayerTreeGroup]]:
        """Creates the top-level groups for each guideline."""
        guideline_defs = self.get_active_framework().guideline_group_definitions(include_cns=include_cns)
        guideline_groups: Dict[str, Optional[QgsLayerTreeGroup]] = {}
        for key, name in guideline_defs.items():
            grp = self._ensure_layer_group(main_group, name)
            guideline_groups[key] = grp
            if grp is None:
                QgsMessageLog.logMessage(f"Failed create group: {name}", PLUGIN_TAG, level=Qgis.Warning)
        if not include_cns:
            guideline_groups["G"] = None
        return guideline_groups

    def _ensure_valid_geometry(self, geom: Optional[QgsGeometry], description: str) -> Optional[QgsGeometry]:
        """Return a valid non-empty geometry, only calling makeValid when needed."""
        if geom is None or geom.isEmpty():
            return None
        try:
            if geom.isGeosValid():
                return geom
            fixed_geom = geom.makeValid()
            if fixed_geom is not None and not fixed_geom.isEmpty() and fixed_geom.isGeosValid():
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
    def _try_get_arp_elevation_from_layer(self, arp_layer: QgsVectorLayer) -> Optional[float]:
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

    def _get_runway_midpoint(self, thr_point: QgsPointXY, rec_thr_point: QgsPointXY) -> Optional[QgsPointXY]:
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
        runway_ols_group: Optional[QgsLayerTreeGroup] = None,
        airport_wide_ols_group: Optional[QgsLayerTreeGroup] = None,
        ols_runway_data_list: Optional[List[dict]] = None,
    ) -> bool:
        """Generate runway-specific safeguarding outputs."""
        any_guideline_processed_ok = False
        if not processed_runway_data_list:
            return False
        ols_data_by_index = {
            runway_data.get("original_index"): runway_data
            for runway_data in (ols_runway_data_list or [])
        }
        for runway_data in processed_runway_data_list:
            rwy_name = runway_data.get("short_name", f"RWY_{runway_data.get('original_index', '?')}")
            run_success_flags = []
            try:
                if guideline_groups.get("B") is not None:
                    run_success_flags.append(self.process_windshear_safeguarding(runway_data, guideline_groups["B"]))
                if guideline_groups.get("E") is not None:
                    run_success_flags.append(self.process_lighting_control_zones(runway_data, guideline_groups["E"]))
                if guideline_groups.get("F") is not None:
                    ols_runway_data = ols_data_by_index.get(
                        runway_data.get("original_index")
                    )
                    if ols_runway_data is None:
                        self._log_skip(
                            f"Runway OLS {rwy_name}: selected ruleset context is unavailable."
                        )
                        ols_runway_data = None
                    if (
                        getattr(self.get_active_protected_airspace_ruleset(), "protected_airspace_model", "")
                        == "annex14_modernised_ofs_oes"
                    ) and ols_runway_data is not None:
                        run_success_flags.append(
                            self.process_annex14_geometry(
                                ols_runway_data,
                                runway_ols_group or guideline_groups["F"],
                                airport_wide_ols_group,
                            )
                        )
                    elif ols_runway_data is not None:
                        run_success_flags.append(
                            self.process_runway_ols_surfaces(
                                ols_runway_data,
                                runway_ols_group or guideline_groups["F"],
                                ofz_group,
                            )
                        )  # F = OLS App/TOCS
                if guideline_groups.get("I") is not None:
                    run_success_flags.append(self.process_public_safety_areas(runway_data, guideline_groups["I"]))
                # Add calls for other safeguarding generators as they are implemented.

                # Specialised Surfaces
                if specialised_group_node is not None:
                    run_success_flags.append(self.process_raoa(runway_data, specialised_group_node))
                    run_success_flags.append(self.process_taxiway_separation(runway_data, specialised_group_node))
                else:
                    QgsMessageLog.logMessage(
                        f"Skipping Specialised surfaces for {rwy_name}: Group missing.",
                        PLUGIN_TAG,
                        level=Qgis.Warning,
                    )

                if any(run_success_flags):
                    any_guideline_processed_ok = True
                if self._run_log is not None:
                    generated_counts = runway_data.get("generated_feature_counts") or {}
                    feature_total = sum(
                        int(value)
                        for value in generated_counts.values()
                        if isinstance(value, (int, float))
                    )
                    self._run_log.output(
                        "runway generation",
                        runway=rwy_name,
                        features=feature_total,
                    )
            except Exception as e_guideline:
                QgsMessageLog.logMessage(
                    f"Error processing guidelines/specialised for {rwy_name}: {e_guideline}",
                    PLUGIN_TAG,
                    level=Qgis.Critical,
                )
        if specialised_group_node is not None:
            try:
                if self.process_runway_separation_assessment(processed_runway_data_list, specialised_group_node):
                    any_guideline_processed_ok = True
            except Exception as e_parallel_sep:
                QgsMessageLog.logMessage(
                    f"Error processing parallel runway standards layer: {e_parallel_sep}",
                    PLUGIN_TAG,
                    level=Qgis.Critical,
                )
        return any_guideline_processed_ok

    def _count_layer_tree_contents(self, node: QgsLayerTreeNode) -> Tuple[int, int, List[str]]:
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
                child_layers, child_features, child_empty = self._count_layer_tree_contents(child)
                layer_count += child_layers
                feature_count += child_features
                empty_layers.extend(child_empty)

        return layer_count, feature_count, empty_layers

    def _remove_empty_generated_groups(self, main_group: Optional[QgsLayerTreeGroup]) -> None:
        """Remove empty generated groups so disabled or inputless options do not clutter the layer tree."""
        if main_group is None:
            return

        removable_names = {
            self.tr(output_structure.METEOROLOGICAL_STATION),
            self.tr(output_structure.CNS_TECHNICAL_FACILITIES),
            self.tr("Airfield Ground Lighting (AGL)"),
            self.tr(output_structure.AIRFIELD_GROUND_LIGHTING),
            self.tr(self.get_active_framework().guideline_group_name("G")),
        }
        guideline_f_subgroups = self.get_active_framework().guideline_f_subgroup_names()
        removable_names.update(
            {
                self.tr(guideline_f_subgroups["runway"]),
                self.tr(guideline_f_subgroups["ofz"]),
            }
        )

        def prune(group: QgsLayerTreeGroup) -> bool:
            for child in list(group.children()):
                if isinstance(child, QgsLayerTreeGroup):
                    prune(child)

            if group == main_group or group.name() not in removable_names:
                return False

            layer_count, feature_count, _ = self._count_layer_tree_contents(group)
            if layer_count == 0 and feature_count == 0:
                parent = group.parent()
                if parent is not None:
                    parent.removeChildNode(group)
                    return True
            return False

        prune(main_group)

    def _find_group_by_path(
        self,
        root_group: Optional[QgsLayerTreeGroup],
        path: List[str],
    ) -> Optional[QgsLayerTreeGroup]:
        """Find a direct-descendant group path below root_group."""
        group = root_group
        for segment in path:
            if group is None:
                return None
            group = self._find_direct_child_group(group, self.tr(segment))
        return group

    def _final_feedback(
        self,
        main_group: Optional[QgsLayerTreeGroup],
        root_node: QgsLayerTreeNode,
        icao_code: str,
        processed_rwy_count: int,
        total_runways_in_input: int,
    ):
        """Provides final user feedback."""
        if main_group is None and self.output_mode == "memory":  # If no group and memory, something is wrong
            self.iface.messageBar().pushMessage(
                self.tr("Error"),
                self.tr("Processing error: Main layer group not created."),
                level=Qgis.Critical,
            )
            return

        project = QgsProject.instance()

        # Check if any layers were successfully generated and added to our tracking list
        anything_successfully_generated = bool(self.successfully_generated_layers)
        self._processing_runway_summary = (
            f"{processed_rwy_count}/{total_runways_in_input}"
            if total_runways_in_input
            else "0"
        )

        if anything_successfully_generated:
            tree_layer_count, tree_feature_count, _ = self._count_layer_tree_contents(
                main_group
            )
            num_layers_created = tree_layer_count or len(self.successfully_generated_layers)
            recorder = getattr(self, "_runtime_run_recorder", None)
            if recorder is not None:
                recorder.set_output_counts(num_layers_created, tree_feature_count)
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
            self.iface.messageBar().pushMessage(
                self.tr("Success"), final_user_message, level=Qgis.Success, duration=10
            )  # Increased duration
            self._emit_section_outputs(main_group)
            if self._run_log is not None:
                self._run_log.update_context(
                    airport=icao_code,
                    runways=self._processing_runway_summary,
                    output=(self.output_path if self.output_mode == "file" else self.output_mode),
                )

            if (
                main_group is not None
            ):  # Only expand group if it exists (it might not if only file output and no group made)
                self._stage_layer_tree_node(main_group)
        else:
            recorder = getattr(self, "_runtime_run_recorder", None)
            if recorder is not None:
                recorder.set_output_counts(0, 0)
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
                main_group is not None and root_node.findGroup(main_group.name()) is not None
            ):  # Only try to remove group if it was created
                self._remove_group_recursively(main_group, project)
                if main_group.parent() is not None:
                    main_group.parent().removeChildNode(main_group)

    def _emit_section_outputs(self, main_group: Optional[QgsLayerTreeGroup]) -> None:
        """Emit one concise output line per populated user-facing section."""
        if main_group is None or self._run_log is None:
            return
        debug_name = self.tr(output_structure.DEBUG_DEVELOPMENT)
        for child in main_group.children():
            if isinstance(child, QgsLayerTreeGroup):
                if child.name() == debug_name:
                    continue
                layers, features, _ = self._count_layer_tree_contents(child)
                if layers > 0 and features > 0:
                    self._run_log.output(
                        child.name(),
                        layers=layers,
                        features=features,
                    )

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

                    arp_geom = QgsGeometry(QgsPoint(arp_point.x(), arp_point.y(), arp_elevation))
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
            QgsMessageLog.logMessage(f"Error in create_arp_layer: {e}", PLUGIN_TAG, level=Qgis.Critical)
            return None

    def create_cns_source_facility_layer(
        self,
        cns_facilities_data: List[Dict[str, Any]],
        icao_code: str,
        layer_group: QgsLayerTreeGroup,
    ) -> Optional[QgsVectorLayer]:
        """Creates a reference point layer for manually supplied CNS facilities."""
        if not cns_facilities_data or layer_group is None:
            return None

        fields = QgsFields(
            [
                QgsField("facility_id", QVariant.String, self.tr("Facility ID"), 50),
                QgsField("facility_type", QVariant.String, self.tr("Facility Type"), 100),
                QgsField("coord_east", QVariant.Double, self.tr("Easting"), 12, 3),
                QgsField("coord_north", QVariant.Double, self.tr("Northing"), 12, 3),
                QgsField("elev_m", QVariant.Double, self.tr("Elevation AMSL (m)"), 12, 3),
            ]
        )
        features: List[QgsFeature] = []
        for facility_data in cns_facilities_data:
            geom = facility_data.get("geom")
            if geom is None or geom.isNull() or geom.isEmpty():
                continue
            try:
                point = geom.asPoint()
            except Exception:
                point = None
            if point is None:
                continue

            feature = QgsFeature(fields)
            feature.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(point.x(), point.y())))
            feature.setAttributes(
                [
                    facility_data.get("id", ""),
                    facility_data.get("type", ""),
                    point.x(),
                    point.y(),
                    facility_data.get("elevation"),
                ]
            )
            features.append(feature)

        return self._create_and_add_layer(
            "Point",
            f"CNS_Source_Facilities_{icao_code}",
            f"{icao_code} {self.tr('CNS Source Facilities')}",
            fields,
            features,
            layer_group,
            "Default Point",
        )

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
        design_group_val: Optional[str] = None,
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
                    QgsField("rwy_head", QVariant.Double, "Runway Heading (degrees)", 10, 3),
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
                    QgsField("adg", QVariant.String, "adg", 10),
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
                    round(rwy_params.get("azimuth_p_r"), 3) if rwy_params.get("azimuth_p_r") is not None else None
                )
                reciprocal_azimuth_attr = (
                    round(rwy_params.get("azimuth_r_p"), 3) if rwy_params.get("azimuth_r_p") is not None else None
                )
            else:
                QgsMessageLog.logMessage(
                    f"Could not calculate azimuths for centreline {runway_name}",
                    plugin_tag,
                    level=Qgis.Warning,
                )

            declared_distance_attrs = self._format_centreline_declared_distances(declared_distances or [])

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
                    design_group_val,
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
            far_edge_center = start_point.project(far_edge_offset, outward_azimuth_degrees)
            near_edge_center = far_edge_center.project(zone_length_backward, backward_azimuth)
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
        if not point1 or not point2 or half_width_m <= 0 or point1.compare(point2, 1e-6):
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
            corner_start_l = rect_start_center.project(half_width_m, params["azimuth_perp_l"])
            corner_start_r = rect_start_center.project(half_width_m, params["azimuth_perp_r"])
            corner_end_l = rect_end_center.project(half_width_m, params["azimuth_perp_l"])
            corner_end_r = rect_end_center.project(half_width_m, params["azimuth_perp_r"])
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
        if not start_point or length <= 0 or inner_half_width < 0 or outer_half_width < 0:
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

    def _get_runway_parameters(self, thr_point: QgsPointXY, rec_thr_point: QgsPointXY) -> Optional[dict]:
        """Calculates basic length and azimuths between two threshold points."""
        plugin_tag = PLUGIN_TAG
        if not isinstance(thr_point, QgsPointXY) or not isinstance(rec_thr_point, QgsPointXY):
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
            azimuth_p_r = thr_point.azimuth(rec_thr_point)  # Primary THR -> Reciprocal THR
            azimuth_r_p = rec_thr_point.azimuth(thr_point)  # Reciprocal THR -> Primary THR

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
            azimuth_perp_l = (azimuth_p_r - 90.0 + 360.0) % 360.0  # Ensure positive before modulo

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

        if not rwy_params or "azimuth_p_r" not in rwy_params or "azimuth_r_p" not in rwy_params:
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
        if displaced_thr_primary > 1e-6:  # Use tolerance, only project if displacement exists
            projected_point = thr_point_primary.project(displaced_thr_primary, azimuth_r_p)
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
            projected_point = thr_point_reciprocal.project(displaced_thr_reciprocal, azimuth_p_r)
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
            total_physical_length = phys_end_point_primary.distance(phys_end_point_reciprocal)
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
        if not corners or len(corners) < 3 or None in corners or not all(isinstance(p, QgsPointXY) for p in corners):
            QgsMessageLog.logMessage(
                f"Cannot create polygon '{description}': Invalid input corner points.",
                plugin_tag,
                level=Qgis.Warning,
            )
            return None

        try:
            # Ensure list is closed (first == last)
            closed_corners = corners + [corners[0]] if not corners[0].compare(corners[-1], 1e-6) else corners

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

                if not geom_valid or geom_valid.isNull() or geom_valid.isEmpty() or not geom_valid.isGeosValid():
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
                            if poly_rings and poly_rings[0]:  # Check if exterior ring exists
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
            if geom is None or geom.isNull() or geom.isEmpty() or not geom.isGeosValid():
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
