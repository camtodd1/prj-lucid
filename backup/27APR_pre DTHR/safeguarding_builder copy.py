# -*- coding: utf-8 -*-
# safeguarding_builder.py

import os.path
import math
# import functools # Not used directly
from typing import Union, Dict, Optional, List, Any, Tuple

# --- Qt Imports ---
from qgis.PyQt import QtWidgets, QtCore
from qgis.PyQt.QtCore import QSettings, QTranslator, QCoreApplication, QVariant, QDateTime
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction, QMessageBox, QPushButton, QDialogButtonBox, QFileDialog

# --- QGIS Imports ---
from qgis.core import (
    QgsProject, QgsVectorLayer, QgsVectorDataProvider,
    QgsFields, QgsField, QgsFeature, QgsGeometry, QgsGeometryUtils,
    QgsLineString, QgsPointXY, QgsPolygon, QgsPoint,
    QgsLayerTreeGroup, QgsLayerTreeNode,  QgsLayerTreeLayer,
    QgsMessageLog, Qgis, QgsCoordinateReferenceSystem,
    QgsVectorFileWriter, QgsCoordinateTransformContext,
    QgsVectorLayerUtils, QgsCoordinateTransform, QgsDistanceArea
)
from qgis.gui import QgsMessageBar # QgsFileWidget not used directly

# --- Local Imports ---
from . import cns_dimensions
from . import ols_dimensions
try:
    # Attempt to import generated resources
    from .resources_rc import * # noqa: F403
except ImportError:
    # Fallback message if resources haven't been compiled
    print("Note: resources_rc.py not found or generated. Icons might be missing.")
# Import the dialog class
from .safeguarding_builder_dialog import SafeguardingBuilderDialog

# Plugin-specific constant for logging
PLUGIN_TAG = 'SafeguardingBuilder'

# ============================================================
# Constants for Guideline Parameters
# ============================================================
GUIDELINE_B_FAR_EDGE_OFFSET = 500.0
GUIDELINE_B_ZONE_LENGTH_BACKWARD = 1400.0
GUIDELINE_B_ZONE_HALF_WIDTH = 1200.0

GUIDELINE_C_RADIUS_A_M = 3000.0
GUIDELINE_C_RADIUS_B_M = 8000.0
GUIDELINE_C_RADIUS_C_M = 13000.0
GUIDELINE_C_BUFFER_SEGMENTS = 144 # Increased segments for smoother circles

GUIDELINE_E_ZONE_PARAMS = {
    'A': {'ext': 1000.0, 'half_w': 300.0, 'desc': "Lighting Zone A (0-1km ext, 300m HW)"},
    'B': {'ext': 2000.0, 'half_w': 450.0, 'desc': "Lighting Zone B (1-2km ext, 450m HW)"},
    'C': {'ext': 3000.0, 'half_w': 600.0, 'desc': "Lighting Zone C (2-3km ext, 600m HW)"},
    'D': {'ext': 4500.0, 'half_w': 750.0, 'desc': "Lighting Zone D (3-4.5km ext, 750m HW)"}
}
GUIDELINE_E_ZONE_ORDER = ['A', 'B', 'C', 'D']

GUIDELINE_I_PSA_LENGTH = 1000.0
GUIDELINE_I_PSA_INNER_WIDTH = 350.0
GUIDELINE_I_PSA_OUTER_WIDTH = 250.0

CONICAL_CONTOUR_INTERVAL = 10.0 # Height interval in meters for conical surface
APPROACH_CONTOUR_INTERVAL = 10.0 # Height interval in meters for approach surfaces

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
        self.menu = self.tr(u'&Safeguarding Builder')
        self.dlg: Optional[SafeguardingBuilderDialog] = None
        self.style_map: Dict[str, str] = {}
        self.reference_elevation_datum: Optional[float] = None
        self._init_locale()

    def _init_locale(self):
        """Load translation file."""
        locale_code = QSettings().value('locale/userLocale', '')[0:2]
        locale_path = os.path.join(self.plugin_dir, 'i18n', f'SafeguardingBuilder_{locale_code}.qm')
        if os.path.exists(locale_path):
            self.translator = QTranslator()
            if self.translator.load(locale_path):
                QCoreApplication.installTranslator(self.translator)
            else:
                QgsMessageLog.logMessage(f"Failed to load translation file: {locale_path}", PLUGIN_TAG, level=Qgis.Warning)
                self.translator = None

    def tr(self, message: str) -> str:
        """Get the translation for a string using Qt translation API."""
        if self.translator:
            # Use type() for class name to avoid potential undefined variable
            return QCoreApplication.translate(type(self).__name__, message)
        return message

    def add_action(self, icon_path: str, text: str, callback, enabled_flag: bool = True,
                   add_to_menu: bool = True, add_to_toolbar: bool = True,
                   status_tip: Optional[str] = None, whats_this: Optional[str] = None,
                   parent=None) -> QAction:
        """Helper method to add an action to the QGIS GUI (menu/toolbar)."""
        try:
            icon = QIcon(icon_path)
            if icon.isNull() and icon_path.startswith(':/'):
                 raise NameError # Force fallback if resource icon is invalid
        except (NameError, TypeError):
            icon = QIcon()
            QgsMessageLog.logMessage(f"Icon resource not found or invalid: {icon_path}. Using default.", PLUGIN_TAG, level=Qgis.Warning)

        action = QAction(icon, text, parent)
        action.triggered.connect(callback)
        action.setEnabled(enabled_flag)
        if status_tip: action.setStatusTip(status_tip)
        if whats_this: action.setWhatsThis(whats_this)
        if add_to_toolbar: self.iface.addToolBarIcon(action)
        if add_to_menu: self.iface.addPluginToMenu(self.menu, action)
        self.actions.append(action)
        return action

    def initGui(self):
        """Create the menu entries and toolbar icons inside the QGIS GUI."""
        icon_path = ':/plugins/safeguarding_builder/icon.png'
        try:
             if QIcon(icon_path).isNull(): raise NameError
        except (NameError, TypeError):
             icon_path_file = os.path.join(self.plugin_dir, "icon.png")
             if os.path.exists(icon_path_file): icon_path = icon_path_file
             else: QgsMessageLog.logMessage(f"Icon resource/fallback not found: {icon_path_file}", PLUGIN_TAG, level=Qgis.Warning); icon_path = ""

        self.add_action(
            icon_path, text=self.tr('NASF Safeguarding Builder'),
            callback=self.run, parent=self.iface.mainWindow()
        )

    def unload(self):
        """Removes the plugin menu item and icon from QGIS GUI."""
        for action in self.actions:
            self.iface.removePluginMenu(self.tr('&Safeguarding Builder'), action)
            self.iface.removeToolBarIcon(action)
        if self.dlg:
            try: self.dlg.finished.disconnect(self.dialog_finished)
            except TypeError: pass
            try: self.dlg.deleteLater()
            except Exception as e: QgsMessageLog.logMessage(f"Error cleaning dialog: {e}", PLUGIN_TAG, level=Qgis.Warning)
            self.dlg = None
        self.successfully_generated_layers = []

    def run(self):
        """Shows the plugin dialog or brings it to front if already open."""
        if self.dlg is not None and self.dlg.isVisible():
            self.dlg.raise_(); self.dlg.activateWindow()
            QgsMessageLog.logMessage("Dialog already open.", PLUGIN_TAG, level=Qgis.Info)
            return

        if self.dlg is None:
            parent_window = self.iface.mainWindow()
            try: self.dlg = SafeguardingBuilderDialog(parent=parent_window)
            except Exception as e: QgsMessageLog.logMessage(f"Error creating dialog: {e}", PLUGIN_TAG, level=Qgis.Critical); QMessageBox.critical(parent_window, self.tr("Dialog Error"), self.tr("Could not create dialog.")); return

            # Connect Signals
            generate_button = self.dlg.findChild(QPushButton, "pushButton_Generate")
            save_project_button = self.dlg.findChild(QPushButton, "pushButton_SaveProject")
            export_layers_button = self.dlg.findChild(QPushButton, "pushButton_ExportLayers")
            button_box = self.dlg.findChild(QDialogButtonBox, "buttonBox")

            if generate_button: generate_button.clicked.connect(self.run_safeguarding_processing)
            else: QgsMessageLog.logMessage("CRITICAL UI ERROR: 'Generate' button missing.", PLUGIN_TAG, level=Qgis.Critical); QMessageBox.critical(self.dlg, self.tr("UI Error"), self.tr("Generate button missing.")); self.dlg.deleteLater(); self.dlg = None; return
            if save_project_button: save_project_button.clicked.connect(self.save_project); save_project_button.setEnabled(False)
            else: QgsMessageLog.logMessage("UI Warn: 'Save Project' button missing.", PLUGIN_TAG, level=Qgis.Warning)
            if export_layers_button: export_layers_button.clicked.connect(self.export_layers); export_layers_button.setEnabled(False)
            else: QgsMessageLog.logMessage("UI Warn: 'Export Layers' button missing.", PLUGIN_TAG, level=Qgis.Warning)
            if button_box: button_box.accepted.connect(self.dlg.accept); button_box.rejected.connect(self.dlg.reject)
            self.dlg.finished.connect(self.dialog_finished)

        self.dlg.show()
        QgsMessageLog.logMessage("Safeguarding Builder dialog shown.", PLUGIN_TAG, level=Qgis.Info)

    def dialog_finished(self, result: int):
        """Slot connected to the dialog's finished signal for cleanup."""
        QgsMessageLog.logMessage(f"Dialog finished signal received (result code: {result})", PLUGIN_TAG, level=Qgis.Info) # Use Info level
        self.dlg = None

    # ============================================================
    # Core Processing Logic
    # ============================================================

    def _calculate_reference_elevation_datum(self, arp_elevation: Optional[float], runway_data_list: List[dict]) -> Optional[float]:
      """
      Calculates the Reference Elevation Datum based on CASA MOS 139 requirements.
      Rounds result down to the nearest half metre.
      Uses validated runway data containing 'thr_elev_1' and 'thr_elev_2'.
      """
      if arp_elevation is None:
        QgsMessageLog.logMessage("Cannot calculate RED: ARP Elevation is missing.", PLUGIN_TAG, level=Qgis.Critical)
        # No message bar here, handled later if needed
        return None
      
      threshold_elevations: List[float] = []
      missing_elev_rwy_names = []
      
      if not runway_data_list:
        QgsMessageLog.logMessage("Cannot calculate RED: No runway data provided.", PLUGIN_TAG, level=Qgis.Warning)
        return None
      
      for i, rwy_data in enumerate(runway_data_list):
        # <<< FIX: Use correct keys 'thr_elev_1' and 'thr_elev_2' >>>
        thr_elev = rwy_data.get('thr_elev_1')
        rec_thr_elev = rwy_data.get('thr_elev_2')
        # <<< END FIX >>>
        
        # Generate a name for logging, using index as fallback
        rwy_name = rwy_data.get('short_name')
        if not rwy_name:
          desig_num = rwy_data.get('designator_num')
          suffix = rwy_data.get('suffix','')
          if desig_num is not None:
            primary_desig = f"{desig_num:02d}{suffix}"
            reciprocal_num = (desig_num + 18) if desig_num <= 18 else (desig_num - 18)
            reciprocal_suffix_map = {"L": "R", "R": "L", "C": "C", "": ""}
            reciprocal_suffix = reciprocal_suffix_map.get(suffix, "")
            reciprocal_desig = f"{reciprocal_num:02d}{reciprocal_suffix}"
            rwy_name = f"{primary_desig}/{reciprocal_desig}"
          else: # Fallback if even designator num is missing (shouldn't happen post-validation)
            rwy_name = f"Runway Index {rwy_data.get('original_index', '?')}"
          
          
        # Check if the retrieved values are valid floats
        valid_thr = isinstance(thr_elev, (int, float))
        valid_rec = isinstance(rec_thr_elev, (int, float))
        
        if valid_thr:
          threshold_elevations.append(float(thr_elev))
        if valid_rec:
          threshold_elevations.append(float(rec_thr_elev))
          
        # Log missing elevations
        if not valid_thr or not valid_rec:
          missing_parts = []
          if not valid_thr: missing_parts.append("PrimaryTHR")
          if not valid_rec: missing_parts.append("ReciprocalTHR")
          missing_elev_rwy_names.append(f"{rwy_name} ({'/'.join(missing_parts)})")
          
          
      if not threshold_elevations:
        # This is the critical error being logged
        QgsMessageLog.logMessage("Cannot calculate RED: No valid threshold elevations found in processed runway data.", PLUGIN_TAG, level=Qgis.Critical)
        self.iface.messageBar().pushMessage(self.tr("Error"), self.tr("Cannot calculate Reference Elevation Datum: No valid threshold elevations found."), level=Qgis.Critical, duration=10)
        return None
      
      if missing_elev_rwy_names:
        QgsMessageLog.logMessage(f"Warning: Missing threshold elevations for: {', '.join(missing_elev_rwy_names)}. Calculation proceeding with available data.", PLUGIN_TAG, level=Qgis.Warning)
        self.iface.messageBar().pushMessage(self.tr("Warning"), self.tr("Missing threshold elevations for some runways. RED calculation may be inaccurate."), level=Qgis.Warning, duration=8)
        
        
      avg_thr_elev = sum(threshold_elevations) / len(threshold_elevations)
      QgsMessageLog.logMessage(f"Calculated Average Threshold Elevation: {avg_thr_elev:.3f}m AMSL", PLUGIN_TAG, level=Qgis.Info)
      
      reference_elevation_unrounded: float
      # Apply MOS 139 rule
      if abs(arp_elevation - avg_thr_elev) <= 3.0:
        reference_elevation_unrounded = arp_elevation
        QgsMessageLog.logMessage("RED based on ARP Elevation (within 3m of average).", PLUGIN_TAG, level=Qgis.Info)
      else:
        reference_elevation_unrounded = avg_thr_elev
        QgsMessageLog.logMessage("RED based on Average Threshold Elevation (>3m difference from ARP).", PLUGIN_TAG, level=Qgis.Info)
        
      # Round down to the nearest half metre
      reference_elevation_datum = math.floor(reference_elevation_unrounded * 2) / 2.0
      
      QgsMessageLog.logMessage(f"Calculated Reference Elevation Datum (RED): {reference_elevation_datum:.2f}m AMSL (Unrounded: {reference_elevation_unrounded:.3f})", PLUGIN_TAG, level=Qgis.Success)
      return reference_elevation_datum

    def run_safeguarding_processing(self):
        """Orchestrates the creation of safeguarding surfaces using validated input data."""
        QgsMessageLog.logMessage("--- Safeguarding Processing Started ---", PLUGIN_TAG, level=Qgis.Info)
        self.successfully_generated_layers = []
        self.reference_elevation_datum = None
        self.iface.messageBar().pushMessage(self.tr("Info"), self.tr("Validating inputs..."), level=Qgis.Info, duration=3)

        if self.dlg is None: QgsMessageLog.logMessage("Processing aborted: Dialog missing.", PLUGIN_TAG, level=Qgis.Critical); return

        project = QgsProject.instance()
        target_crs = project.crs()
        if not target_crs or not target_crs.isValid(): self.iface.messageBar().pushMessage(self.tr("Error"), self.tr("Project CRS is invalid."), level=Qgis.Critical, duration=7); return
        QgsMessageLog.logMessage(f"Using Project CRS: {target_crs.authid()}", PLUGIN_TAG, level=Qgis.Info)

        # Get ALL Validated Input Data
        try:
            input_data = self.dlg.get_all_input_data()
            if input_data is None: QgsMessageLog.logMessage("Processing aborted: Input validation failed.", PLUGIN_TAG, level=Qgis.Warning); return
        except Exception as e: QgsMessageLog.logMessage(f"Critical error getting input data: {e}", PLUGIN_TAG, level=Qgis.Critical); self.iface.messageBar().pushMessage(self.tr("Error"), self.tr("Failed to retrieve input data."), level=Qgis.Critical); return

        # Extract data
        icao_code = input_data.get('icao_code', 'UNKNOWN'); arp_point = input_data.get('arp_point'); arp_east = input_data.get('arp_easting'); arp_north = input_data.get('arp_northing')
        met_point = input_data.get('met_point'); runway_input_list = input_data.get('runways', []); cns_input_list = input_data.get('cns_facilities', [])
        self.arp_elevation_amsl = input_data.get('arp_elevation') # Get ARP elevation

        if not runway_input_list: QgsMessageLog.logMessage("No valid runways to process.", PLUGIN_TAG, level=Qgis.Warning); self.iface.messageBar().pushMessage(self.tr("Warning"), self.tr("No valid runway data found."), level=Qgis.Warning, duration=5); return # Stop if no runways validated
        self.iface.messageBar().pushMessage(self.tr("Info"), self.tr("Processing {n} runways for {icao}...").format(n=len(runway_input_list), icao=icao_code), level=Qgis.Info, duration=3)

        # Define Style Map
        self.style_map = { "ARP": "arp_point.qml", 
          "Runway Centreline": "rwy_centreline_line.qml",
          "MET Station Location": "default_point.qml",
          "MET Instrument Enclosure": "default_zone_polygon.qml",
          "MET Buffer Zone": "default_zone_polygon.qml",
          "MET Obstacle Buffer Zone": "default_zone_polygon.qml",
          "Runway Pavement": "physical_runway.qml",
          "Runway Shoulders": "physical_runway_shoulder.qml",
          "Runway Graded Strips": "physical_graded_strips.qml",
          "Runway Overall Strips": "physical_overall_strips.qml",
          "Runway End Safety Areas (RESA)": "physical_resa.qml",
          "Stopways": "physical_stopway.qml",
          "RAOA": "default_zone_polygon.qml",
          "Taxiway Separation Line": "default_line.qml",
          "WSZ Runway": "guideline_b_wsz.qml",
          "WMZ A": "default_zone_polygon.qml",
          "WMZ B": "default_zone_polygon.qml",
          "WMZ C": "default_zone_polygon.qml",
          "LCZ A": "default_zone_polygon.qml",
          "LCZ B": "default_zone_polygon.qml",
          "LCZ C": "default_zone_polygon.qml",
          "LCZ D": "default_zone_polygon.qml",
          "OLS Approach": "default_ols_polygon.qml",
          "OLS Approach Contour": "default_line.qml",
          "OLS Inner Approach": "default_ols_polygon.qml",
          "OLS TOCS": "default_ols_polygon.qml",
          "OLS IHS": "default_ols_polygon.qml",
          "OLS Transitional": "default_ols_polygon.qml",
          "OLS Conical": "default_ols_polygon.qml",
          "OLS Conical Contour": "default_ols_polygon.qml",
          "OLS OHS": "default_ols_polygon.qml",
          "CNS Circle Zone": "default_cns_zone_polygon.qml",
          "CNS Donut Zone": "default_cns_zone_polygon.qml",
          "Default CNS": "default_cns_zone_polygon.qml",
          "PSA Runway": "guideline_i_psa.qml",
          "Default Polygon": "default_zone_polygon.qml",
          "Default Line": "default_line.qml",
          "Default Point": "default_point.qml" }

        # Setup Layer Tree
        root = project.layerTreeRoot()
        main_group_name = f"{icao_code} {self.tr('Safeguarding Surfaces')}"
        main_group = self._setup_main_group(root, main_group_name, project)
        if main_group is None: return

        # Create ARP Layer
        arp_layer_created = False
        if arp_point:
          arp_layer = self.create_arp_layer(arp_point, arp_east, arp_north, icao_code, target_crs, main_group, self.arp_elevation_amsl)
          if arp_layer: arp_layer_created = True
          # Re-check ARP elevation if it wasn't provided initially
          if self.arp_elevation_amsl is None and arp_layer:
            # Try getting Z or attribute, but RED calculation already attempted/failed
            fetched_elev = self._try_get_arp_elevation_from_layer(arp_layer)
            if fetched_elev is not None:
              QgsMessageLog.logMessage(f"Note: ARP Elevation ({fetched_elev:.2f}m) found on layer after RED calculation failed.", PLUGIN_TAG, level=Qgis.Warning)

        # Create MET Station Layers
        met_layers_created_ok = False
        if met_point:
            met_group = main_group.addGroup(self.tr("Meteorological Instrument Station"))
            if met_group: met_layers_created_ok, _ = self.process_met_station_surfaces(met_point, icao_code, target_crs, met_group)
            else: QgsMessageLog.logMessage("Failed to create MET subgroup.", PLUGIN_TAG, level=Qgis.Warning)
        else: QgsMessageLog.logMessage("Skipping MET Station: No valid coordinates provided.", PLUGIN_TAG, level=Qgis.Info)

        # Runway Loop (Part 1) - Creates Centrelines
        processed_runway_data_list, any_runway_base_data_ok = self._process_runways_part1( main_group, project, target_crs, icao_code, runway_input_list )
        
        # Style Centrelines
        if any_runway_base_data_ok:
            for rwy_data in processed_runway_data_list:
                cl_layer = rwy_data.get("centreline_layer")
                if cl_layer: self._apply_style(cl_layer, self.style_map)

        # Setup & Generate Physical Geometry
        physical_geom_group = None; physical_layers = {}; any_physical_geom_ok = False
        if processed_runway_data_list and any_runway_base_data_ok:
            physical_geom_group = main_group.addGroup(self.tr("Physical Geometry"))
            if physical_geom_group:
                common_fields = [ QgsField("RWY_Name", QVariant.String, self.tr("Runway Name"), 30), QgsField("Type", QVariant.String, self.tr("Element Type"), 50), QgsField("Length_m", QVariant.Double, self.tr("Length (m)"), 12, 3), QgsField("Width_m", QVariant.Double, self.tr("Width (m)"), 12, 3), QgsField("MOS_Ref", QVariant.String, self.tr("MOS Reference"), 250)]
                stopway_resa_fields = common_fields + [QgsField("End_Desig", QVariant.String, self.tr("End Designator"), 10)]
                layer_definitions = { 'Runway': {'name': self.tr('Runway Pavement'), 'fields': common_fields}, 'Shoulder': {'name': self.tr('Runway Shoulders'), 'fields': common_fields}, 'Stopway': {'name': self.tr('Stopways'), 'fields': stopway_resa_fields}, 'GradedStrip': {'name': self.tr('Runway Graded Strips'), 'fields': common_fields}, 'OverallStrip': {'name': self.tr('Runway Overall Strips'), 'fields': common_fields}, 'RESA': {'name': self.tr('Runway End Safety Areas (RESA)'), 'fields': stopway_resa_fields} }
                style_key_map = {"Runway": "Runway Pavement", "Shoulder": "Runway Shoulders", "Stopway": "Stopways", "GradedStrip": "Runway Graded Strips", "OverallStrip": "Runway Overall Strips", "RESA": "Runway End Safety Areas (RESA)"}

                # Create layer structures
                for element_type, definition in layer_definitions.items():
                    layer_name_internal = f"physical_{element_type}_{icao_code}_{id(self)}_{QtCore.QDateTime.currentMSecsSinceEpoch()}"; layer_display_name = f"{icao_code} {definition['name']}"
                    layer = QgsVectorLayer(f"Polygon?crs={target_crs.authid()}", layer_name_internal, "memory")
                    if layer.isValid() and layer.dataProvider() and layer.dataProvider().addAttributes(definition['fields']):
                        layer.updateFields(); layer.setName(layer_display_name); layer.setCustomProperty("safeguarding_style_key", style_key_map.get(element_type, "Default Polygon"))
                        if layer.startEditing(): physical_layers[element_type] = layer;
                        else: QgsMessageLog.logMessage(f"Failed startEditing physical layer {layer_display_name}", PLUGIN_TAG, level=Qgis.Warning); physical_layers[element_type] = None
                    else: QgsMessageLog.logMessage(f"Failed init physical layer {layer_display_name}", PLUGIN_TAG, level=Qgis.Critical); physical_layers[element_type] = None

                # Populate layers
                physical_geom_features_added = {element_type: False for element_type in physical_layers.keys()}
                QgsMessageLog.logMessage("Starting Physical Geometry Generation...", PLUGIN_TAG, level=Qgis.Info)
                for rwy_data in processed_runway_data_list:
                  runway_name_log = rwy_data.get('short_name', f"RWY_{rwy_data.get('original_index','?')}")
                  try:
                    # --- Generate physical geometry ---
                    generated_elements = self.generate_physical_geometry(rwy_data)
                    
                    # --- Store strip dimensions back into runway_data if calculated ---
                    strip_dims = self._calculate_strip_dimensions(rwy_data) # Recalculate or retrieve if stored
                    rwy_data['calculated_strip_dims'] = strip_dims # Store for later use by OLS
                    
                    # <<< ADD THIS DEBUG LOG >>>
                    QgsMessageLog.logMessage(f"DEBUG: Stored strip_dims for {runway_name_log}: {strip_dims!r}", PLUGIN_TAG, level=Qgis.Info)
                    # <<< END DEBUG LOG >>>
                    
                    if not generated_elements: continue
                    for element_type, geometry, attributes in generated_elements:
                        target_layer = physical_layers.get(element_type)
                        if target_layer and target_layer.isValid() and target_layer.isEditable() and geometry and not geometry.isEmpty():
                            if not geometry.isGeosValid(): geometry = geometry.makeValid()
                            if geometry and not geometry.isEmpty() and geometry.isGeosValid():
                                feature = QgsFeature(target_layer.fields()); feature.setGeometry(geometry)
                                for field_name, value in attributes.items():
                                    idx = feature.fieldNameIndex(field_name)
                                    if idx != -1: feature.setAttribute(idx, value)
                                if target_layer.dataProvider().addFeature(feature): physical_geom_features_added[element_type] = True; any_physical_geom_ok = True
                                else: QgsMessageLog.logMessage(f"ERROR adding physical feature {element_type} for {runway_name_log}", PLUGIN_TAG, level=Qgis.Error)
                  except Exception as e_phys: QgsMessageLog.logMessage(f"Error processing physical geom for {runway_name_log}: {e_phys}", PLUGIN_TAG, level=Qgis.Critical)

                # Commit Layers and add to group
                QgsMessageLog.logMessage("Committing physical geometry layers...", PLUGIN_TAG, level=Qgis.Info)
                commit_errors = False
                for element_type, layer in physical_layers.items():
                    if layer and layer.isValid() and layer.isEditable():
                        if physical_geom_features_added.get(element_type, False):
                             if layer.commitChanges():
                                 project.addMapLayer(layer, False)
                                 node = physical_geom_group.addLayer(layer)
                                 if node: node.setName(layer.name()); self._apply_style(layer, self.style_map); self.successfully_generated_layers.append(layer)
                                 else: QgsMessageLog.logMessage(f"Warn: Failed add node for committed layer '{layer.name()}'.", PLUGIN_TAG, level=Qgis.Warning)
                             else: commit_errors = True; QgsMessageLog.logMessage(f"Commit FAILED for '{layer.name()}': {layer.commitErrors()}", PLUGIN_TAG, level=Qgis.Warning); layer.rollBack()
                        else: layer.rollBack()
                if commit_errors: self.iface.messageBar().pushMessage(self.tr("Warning"), self.tr("Commit errors occurred on physical layers."), level=Qgis.Warning, duration=7)
            else: QgsMessageLog.logMessage("Failed to create 'Physical Geometry' subgroup.", PLUGIN_TAG, level=Qgis.Warning)

        # Create Guideline Groups
        guideline_groups = self._create_guideline_groups(main_group)

        # --- ADD: Create Specialised Safeguarding Group ---
        specialised_group_node = main_group.addGroup(self.tr("Specialised Safeguarding"))
        if not specialised_group_node:
          QgsMessageLog.logMessage("Failed create group: Specialised Safeguarding", PLUGIN_TAG, level=Qgis.Warning)
        # Position it if necessary (tricky, might be easier to ensure creation order)
        # Or reorder later if needed using QgsLayerTreeGroup methods

        # --- Calculate Reference Elevation Datum ---
        self.reference_elevation_datum = self._calculate_reference_elevation_datum(
          self.arp_elevation_amsl,
          runway_input_list # Pass the raw list before filtering in part 1
        )
        # Decide how critical RED is. If None, maybe prevent IHS/Conical?
        if self.reference_elevation_datum is None and any('PA' in rwy.get('type1','') or 'PA' in rwy.get('type2','') for rwy in runway_input_list):
          # For precision runways, RED is more critical
          QgsMessageLog.logMessage("Aborting OLS generation: RED calculation failed and precision runways exist.", PLUGIN_TAG, level=Qgis.Critical)
          self.iface.messageBar().pushMessage(self.tr("Error"), self.tr("Reference Elevation Datum calculation failed. Cannot generate OLS for precision runways."), level=Qgis.Critical, duration=10)
          # Depending on requirements, could choose to continue for NI/NPA only
          # return # Or just prevent IHS/Conical later

        # Process Airport-Wide Guidelines
        guideline_c_processed = False; guideline_g_processed = False
        if arp_point and guideline_groups.get('C'): guideline_c_processed = self.process_guideline_c(arp_point, icao_code, target_crs, guideline_groups['C'])
        if cns_input_list and guideline_groups.get('G'):
            try: guideline_g_processed = self.process_guideline_g(cns_input_list, icao_code, target_crs, guideline_groups['G'])
            except Exception as e_proc_g: QgsMessageLog.logMessage(f"Guideline G error: {e_proc_g}", PLUGIN_TAG, level=Qgis.Critical)
        elif not cns_input_list: QgsMessageLog.logMessage("Guideline G skipped: No valid CNS facilities.", PLUGIN_TAG, level=Qgis.Info)

        # Runway Loop (Part 2 - Per-Runway Guideline Processing - *Excluding* OLS IHS/Conical/Transitional)
        any_guideline_processed_ok = self._process_runways_part2(
          processed_runway_data_list,
          guideline_groups,
          specialised_group_node
        )

        # --- Process Airport-Wide OLS (IHS, Conical, Transitional Placeholders) ---
        airport_wide_ols_processed = False
        # Check if RED is valid before proceeding
        if guideline_groups.get('F') and processed_runway_data_list and self.reference_elevation_datum is not None:
          try:
              # <<< MODIFY Call: Pass icao_code >>>
              airport_wide_ols_processed = self._generate_airport_wide_ols(
                processed_runway_data_list,
                guideline_groups['F'],
                self.reference_elevation_datum,
                icao_code
              )
              # <<< END MODIFY Call >>>
              if airport_wide_ols_processed: any_guideline_processed_ok = True
          except Exception as e_ols_wide:
              QgsMessageLog.logMessage(f"Critical Error generating Airport-Wide OLS: {e_ols_wide}", PLUGIN_TAG, level=Qgis.Critical)
              self.iface.messageBar().pushMessage(self.tr("Error"), self.tr("Failed to generate airport-wide OLS surfaces."), level=Qgis.Critical, duration=10)
        elif self.reference_elevation_datum is None:
              QgsMessageLog.logMessage("Skipping Airport-Wide OLS (IHS, Conical): Reference Elevation Datum calculation failed.", PLUGIN_TAG, level=Qgis.Warning)
        elif not processed_runway_data_list:
              QgsMessageLog.logMessage("Skipping Airport-Wide OLS (IHS, Conical): No valid runway data processed.", PLUGIN_TAG, level=Qgis.Warning)

        # Enable Save/Export Buttons
        save_project_button = self.dlg.findChild(QPushButton, "pushButton_SaveProject") if self.dlg else None
        export_layers_button = self.dlg.findChild(QPushButton, "pushButton_ExportLayers") if self.dlg else None
        enable_buttons = bool(self.successfully_generated_layers)
        if save_project_button: save_project_button.setEnabled(enable_buttons)
        if export_layers_button: export_layers_button.setEnabled(enable_buttons)

        # Final Feedback
        self._final_feedback( main_group, root, icao_code, arp_layer_created, met_layers_created_ok, any_runway_base_data_ok, guideline_c_processed, guideline_g_processed, any_guideline_processed_ok, len(processed_runway_data_list), len(runway_input_list), any_physical_geom_ok )
        QgsMessageLog.logMessage("--- Safeguarding Processing Finished ---", PLUGIN_TAG, level=Qgis.Info)

    # ============================================================
    # Save Project Method
    # ============================================================
    def save_project(self):
        """Saves the current QGIS project state as a .qgz file."""
        project = QgsProject.instance()
        if not hasattr(self, 'successfully_generated_layers') or not self.successfully_generated_layers:
            self.iface.messageBar().pushMessage(self.tr("Save Project Error"), self.tr("No layers found to save."), level=Qgis.Warning, duration=7); return

        parent = self.dlg if self.dlg else self.iface.mainWindow(); default_project_filename = "Safeguarding_Project.qgz"
        try:
            icao_code = ""; input_data = self.dlg.get_all_input_data() if self.dlg else None
            if input_data: icao_code = input_data.get('icao_code', '')
            elif self.dlg: icao_le = self.dlg.findChild(QtWidgets.QLineEdit, "lineEdit_airport_name"); icao_code = icao_le.text().strip().upper() if icao_le else ""
            if icao_code: default_project_filename = f"{''.join(c if c.isalnum() else '_' for c in icao_code)}_Safeguarding_Project.qgz"
        except Exception as e: QgsMessageLog.logMessage(f"Minor error generating project filename: {e}", PLUGIN_TAG, level=Qgis.Warning)

        qgz_path, file_filter = QFileDialog.getSaveFileName(parent, self.tr("Save Safeguarding Project"), default_project_filename, self.tr("QGIS Project File (*.qgz)"));
        if not qgz_path: return
        if not qgz_path.lower().endswith(".qgz"): qgz_path += ".qgz"

        QgsMessageLog.logMessage(f"Saving project to {qgz_path}", PLUGIN_TAG, level=Qgis.Info); self.iface.messageBar().pushMessage(self.tr("Saving..."), self.tr("Saving project file..."), level=Qgis.Info, duration=3)
        save_successful = project.write(qgz_path)
        if save_successful:
            QgsMessageLog.logMessage(f"Project saved to {qgz_path}", PLUGIN_TAG, level=Qgis.Success); self.iface.messageBar().pushMessage(self.tr("Project Saved"), self.tr("Project file saved to {file}").format(file=os.path.basename(qgz_path)), level=Qgis.Success, duration=7); project.setFileName(qgz_path)
        else: QgsMessageLog.logMessage(f"Failed to save project to {qgz_path}", PLUGIN_TAG, level=Qgis.Critical); self.iface.messageBar().pushMessage(self.tr("Project Save Failed"), self.tr("Could not save project."), level=Qgis.Critical, duration=10)

    # ============================================================
    # Export Layers Method
    # ============================================================
    def export_layers(self):
        """Exports the generated layers to a GeoPackage file."""
        if not hasattr(self, 'successfully_generated_layers') or not self.successfully_generated_layers:
            self.iface.messageBar().pushMessage(self.tr("Export Error"), self.tr("No generated layers found."), level=Qgis.Warning, duration=5); return

        parent = self.dlg if self.dlg else self.iface.mainWindow(); default_filename = "Safeguarding_Export.gpkg"
        try: # Suggest default filename
            icao_code = ""; input_data = self.dlg.get_all_input_data() if self.dlg else None
            if input_data: icao_code = input_data.get('icao_code', '')
            elif self.dlg: icao_le = self.dlg.findChild(QtWidgets.QLineEdit, "lineEdit_airport_name"); icao_code = icao_le.text().strip().upper() if icao_le else ""
            if icao_code: default_filename = f"{''.join(c if c.isalnum() else '_' for c in icao_code)}_Safeguarding_Export.gpkg"
        except Exception as e: QgsMessageLog.logMessage(f"Minor error generating export filename: {e}", PLUGIN_TAG, level=Qgis.Warning)

        output_path, file_filter = QFileDialog.getSaveFileName(parent, self.tr("Export Layers to GeoPackage"), default_filename, self.tr("GeoPackage (*.gpkg *.GPKG)"));
        if not output_path: return
        if not output_path.lower().endswith(".gpkg"): output_path += ".gpkg"

        QgsMessageLog.logMessage(f"Exporting {len(self.successfully_generated_layers)} layers to {output_path}", PLUGIN_TAG, level=Qgis.Info); self.iface.messageBar().pushMessage(self.tr("Exporting..."), self.tr("Exporting layers..."), level=Qgis.Info, duration=3)

        save_options = QgsVectorFileWriter.SaveVectorOptions(); save_options.driverName = "GPKG"; save_options.symbologyExport = QgsVectorFileWriter.FeatureSymbology
        transform_context = QgsProject.instance().transformContext(); successful_saves = 0; failed_saves = 0; save_errors = []

        for i, layer in enumerate(self.successfully_generated_layers):
            if not layer or not layer.isValid(): failed_saves += 1; save_errors.append(f"Invalid Layer index {i}"); continue
            layer_name = layer.name() or f"Layer_{i+1}_{layer.id()}"; save_options.layerName = layer_name
            save_options.actionOnExistingFile = QgsVectorFileWriter.CreateOrOverwriteFile if i == 0 else QgsVectorFileWriter.CreateOrOverwriteLayer
            returned_value, error_message = QgsVectorFileWriter.writeAsVectorFormatV2(layer, output_path, transform_context, save_options)
            if returned_value == QgsVectorFileWriter.NoError: successful_saves += 1
            else:
                failed_saves += 1; save_errors.append(layer_name); error_map = {val: name for name, val in QgsVectorFileWriter.WriterError.__members__.items()}; error_type_str = error_map.get(returned_value, f"Code {returned_value}")
                log_msg = f"Failed export layer '{layer_name}'. Err: {error_type_str}, Msg: '{error_message}'"; QgsMessageLog.logMessage(f"CRITICAL {log_msg}", PLUGIN_TAG, level=Qgis.Critical)
                if i == 0: QgsMessageLog.logMessage("Aborting export: Failed on first layer.", PLUGIN_TAG, level=Qgis.Critical); self.iface.messageBar().pushMessage(self.tr("Export Failed"), self.tr("Failed on first layer '{layer}'.").format(layer=layer_name), level=Qgis.Critical, duration=15); return

        # Final Export Feedback
        if failed_saves == 0 and successful_saves > 0: self.iface.messageBar().pushMessage(self.tr("Export Successful"), self.tr("Exported {n} layers.").format(n=successful_saves), level=Qgis.Success, duration=7)
        elif successful_saves > 0: self.iface.messageBar().pushMessage(self.tr("Export Partially Successful"), self.tr("Exported {s}, failed {f}. Check logs.").format(s=successful_saves, f=failed_saves), level=Qgis.Warning, duration=12)
        elif successful_saves == 0 and i > 0: self.iface.messageBar().pushMessage(self.tr("Export Failed"), self.tr("Failed export subsequent layers."), level=Qgis.Critical, duration=10)

    # ============================================================
    # Helper Methods
    # ============================================================

    def _setup_main_group(self, root_node: QgsLayerTreeNode, group_name: str, project: QgsProject) -> Optional[QgsLayerTreeGroup]:
        """Finds and clears or creates the main layer group."""
        existing_group = root_node.findGroup(group_name)
        if existing_group:
            QgsMessageLog.logMessage(f"Removing existing group: {group_name}", PLUGIN_TAG, level=Qgis.Info)
            self._remove_group_recursively(existing_group, project)
            parent_node = existing_group.parent()
            if parent_node: parent_node.removeChildNode(existing_group)
        main_group = root_node.addGroup(group_name)
        if not main_group: QgsMessageLog.logMessage(f"Failed create group: {group_name}", PLUGIN_TAG, level=Qgis.Critical); return None
        return main_group

    def _remove_group_recursively(self, group_node: QgsLayerTreeGroup, project: QgsProject):
         """Helper to remove layers within a group and its subgroups."""
         if not group_node: return
         children_copy = list(group_node.children()) # Iterate over copy
         for node in children_copy:
              if isinstance(node, QgsLayerTreeLayer):
                   layer_id = node.layerId()
                   if layer_id and project.mapLayer(layer_id): project.removeMapLayer(layer_id)
              elif isinstance(node, QgsLayerTreeGroup):
                   self._remove_group_recursively(node, project)
                   group_node.removeChildNode(node) # Remove subgroup after its contents

    def _process_runways_part1(self, main_group: QgsLayerTreeGroup, project: QgsProject,
                               target_crs: QgsCoordinateReferenceSystem, icao_code: str,
                               runway_input_list: List[Dict[str, Any]]) -> tuple[List[Dict[str, Any]], bool]:
        """Processes validated runway inputs, creates centrelines, returns enriched data list."""
        processed_runway_data_list = []
        any_runway_base_data_ok = False
        if not runway_input_list: return [], False

        for runway_data in runway_input_list:
            index = runway_data.get('original_index', '?')
            short_runway_name = f"RWY_{index}_ERR"
            centreline_layer = None
            runway_processed_ok = False
            try:
                designator_num = runway_data.get('designator_num'); suffix = runway_data.get('suffix', '')
                thr_point = runway_data.get('thr_point'); rec_thr_point = runway_data.get('rec_thr_point')
                if designator_num is None or thr_point is None or rec_thr_point is None: continue

                primary_desig = f"{designator_num:02d}{suffix}"
                reciprocal_num = (designator_num + 18) if designator_num <= 18 else (designator_num - 18)
                reciprocal_suffix_map = {"L": "R", "R": "L", "C": "C", "": ""}
                reciprocal_suffix = reciprocal_suffix_map.get(suffix, "")
                reciprocal_desig = f"{reciprocal_num:02d}{reciprocal_suffix}"
                short_runway_name = f"{primary_desig}/{reciprocal_desig}"
                runway_data["short_name"] = short_runway_name

                # Pass main_group to create_runway_centreline_layer
                centreline_layer = self.create_runway_centreline_layer(thr_point, rec_thr_point, short_runway_name, target_crs, main_group)
                if centreline_layer:
                    runway_data["centreline_layer"] = centreline_layer
                    any_runway_base_data_ok = True; runway_processed_ok = True
                    QgsMessageLog.logMessage(f"Runway {short_runway_name} centreline created.", PLUGIN_TAG, level=Qgis.Info)
                else: runway_data["centreline_layer"] = None; QgsMessageLog.logMessage(f"Failed create centreline for {short_runway_name}.", PLUGIN_TAG, level=Qgis.Warning)

                if runway_processed_ok: processed_runway_data_list.append(runway_data)
            except Exception as e:
                QgsMessageLog.logMessage(f"Error processing runway {short_runway_name} (Part 1): {e}", PLUGIN_TAG, level=Qgis.Critical)
                # Attempt cleanup if layer was partially created by helper but failed later
                if centreline_layer and centreline_layer.isValid() and project.mapLayer(centreline_layer.id()): project.removeMapLayer(centreline_layer.id())
                continue
        return processed_runway_data_list, any_runway_base_data_ok

    def _create_guideline_groups(self, main_group: QgsLayerTreeGroup) -> Dict[str, Optional[QgsLayerTreeGroup]]:
        """Creates the top-level groups for each guideline."""
        guideline_defs = {'A': "Guideline A: Noise", 'B': "Guideline B: Windshear", 'C': "Guideline C: Wildlife", 'E': "Guideline E: Lighting", 'F': "Guideline F: Airspace", 'G': "Guideline G: CNS", 'H': "Guideline H: Heli", 'I': "Guideline I: Safety"}
        guideline_groups: Dict[str, Optional[QgsLayerTreeGroup]] = {}
        for key, name in guideline_defs.items():
            grp = main_group.addGroup(self.tr(name)); guideline_groups[key] = grp
            if not grp: QgsMessageLog.logMessage(f"Failed create group: {name}", PLUGIN_TAG, level=Qgis.Warning)
        return guideline_groups

    def _apply_style(self, layer: QgsVectorLayer, style_map: Dict[str, str]):
        """Applies QML style based on custom property."""
        if not layer or not layer.isValid(): return
        layer_name = layer.name() or f"Layer {layer.id()}"
        qml_filename = None; style_key = layer.customProperty("safeguarding_style_key")
        try:
            if style_key: qml_filename = style_map.get(str(style_key))
            if not qml_filename: # Fallback logic
                 geom_type = layer.geometryType()
                 default_key = { Qgis.GeometryType.Polygon: "Default Polygon", Qgis.GeometryType.Line: "Default Line", Qgis.GeometryType.Point: "Default Point" }.get(geom_type)
                 if default_key: qml_filename = style_map.get(default_key)
            if qml_filename:
                qml_path = os.path.join(self.plugin_dir, 'styles', qml_filename)
                if os.path.exists(qml_path): layer.loadNamedStyle(qml_path); layer.triggerRepaint()
                else: QgsMessageLog.logMessage(f"Style NOT FOUND: '{qml_path}' for layer '{layer_name}'.", PLUGIN_TAG, level=Qgis.Warning)
        except Exception as e: QgsMessageLog.logMessage(f"Error applying style to '{layer_name}': {e}", PLUGIN_TAG, level=Qgis.Critical)

    def _process_runways_part2(self, processed_runway_data_list: List[dict], guideline_groups: Dict[str, Optional[QgsLayerTreeGroup]],
      specialised_group_node: Optional[QgsLayerTreeGroup]) -> bool:
        """Processes runway-specific guidelines."""
        any_guideline_processed_ok = False
        if not processed_runway_data_list: return False
        for runway_data in processed_runway_data_list:
            rwy_name = runway_data.get('short_name', f"RWY_{runway_data.get('original_index', '?')}")
            run_success_flags = []
            try: # Standard Guidelines
                if guideline_groups.get('B'): run_success_flags.append(self.process_guideline_b(runway_data, guideline_groups['B']))
                if guideline_groups.get('E'): run_success_flags.append(self.process_guideline_e(runway_data, guideline_groups['E']))
                if guideline_groups.get('F'): run_success_flags.append(self.process_guideline_f(runway_data, guideline_groups['F'])) # F = OLS App/TOCS
                if guideline_groups.get('I'): run_success_flags.append(self.process_guideline_i(runway_data, guideline_groups['I']))
                # Add calls for other guidelines (A, F, H) here if implemented
                
                # Specialised Surfaces
                if specialised_group_node:
                  run_success_flags.append(self.process_raoa(runway_data, specialised_group_node))
                  # <<< ADD CALL for Taxiway Separation >>>
                  run_success_flags.append(self.process_taxiway_separation(runway_data, specialised_group_node))
                else:
                  QgsMessageLog.logMessage(f"Skipping Specialised surfaces for {rwy_name}: Group missing.", PLUGIN_TAG, level=Qgis.Warning)
                  
                if any(run_success_flags): any_guideline_processed_ok = True
            except Exception as e_guideline: QgsMessageLog.logMessage(f"Error processing guidelines/specialised for {rwy_name}: {e_guideline}", PLUGIN_TAG, level=Qgis.Critical)
        return any_guideline_processed_ok

    def _final_feedback(self, main_group: Optional[QgsLayerTreeGroup], root_node: QgsLayerTreeNode,
                        icao_code: str, arp_ok: bool, met_ok: bool, rwy_base_ok: bool,
                        guide_c_ok: bool, guide_g_ok: bool, guide_rwy_ok: bool,
                        processed_rwy_count: int, total_runways_in_input: int,
                        physical_geom_ok: bool):
        """Provides final user feedback."""
        if main_group is None: return
        project = QgsProject.instance()
        anything_created = arp_ok or met_ok or rwy_base_ok or physical_geom_ok or guide_c_ok or guide_g_ok or guide_rwy_ok
        if anything_created:
          msg_parts = [f"{self.tr('Processing complete for')} {icao_code}."]
          if arp_ok: msg_parts.append(self.tr("ARP processed."))
          if met_ok: msg_parts.append(self.tr("MET Station processed."))
          if total_runways_in_input > 0:
            status = f"{processed_rwy_count}/{total_runways_in_input} runways"; details = []
            if rwy_base_ok: details.append("base data")
            if physical_geom_ok: details.append("physical geometry")
            if guide_rwy_ok: details.append("guidelines")
            if details: status += f" ({', '.join(details)}) processed."
            elif processed_rwy_count == 0 : status += " had input errors."
            else: status += " processed with some errors."
            msg_parts.append(status)
          if guide_c_ok: msg_parts.append(self.tr("Guideline C processed."))
          if guide_g_ok: msg_parts.append(self.tr("Guideline G processed."))
          final_msg = " ".join(msg_parts)
          self.iface.messageBar().pushMessage(self.tr("Success"), final_msg.strip(), level=Qgis.Success, duration=7)
          main_group.setExpanded(True)
        else:
          self.iface.messageBar().pushMessage(self.tr("Warning"), self.tr("No surfaces generated."), level=Qgis.Warning, duration=6)
          QgsMessageLog.logMessage("Processing finished, nothing generated.", PLUGIN_TAG, level=Qgis.Warning)
          if root_node.findGroup(main_group.name()): # Check if group still exists
            self._remove_group_recursively(main_group, project)
            if main_group.parent(): main_group.parent().removeChildNode(main_group)

    # --- Layer Creation Helper ---
          
    def _create_and_add_layer(self, geometry_type_str: str, internal_name_base: str,
                              display_name: str, fields: QgsFields, features: List[QgsFeature],
                              layer_group: QgsLayerTreeGroup, style_key: str) -> Optional[QgsVectorLayer]:
        """Helper to create, populate, style, and add a memory layer."""
        if not features:
            QgsMessageLog.logMessage(f"Skipping layer '{display_name}': No features generated.", PLUGIN_TAG, level=Qgis.Info)
            return None
      
        project = QgsProject.instance()
        target_crs = project.crs()
        if not target_crs or not target_crs.isValid():
              QgsMessageLog.logMessage(f"Cannot create layer '{display_name}': Invalid target CRS.", PLUGIN_TAG, level=Qgis.Critical)
              return None
      
        layer_name_internal = f"{internal_name_base}_{id(self)}_{QDateTime.currentMSecsSinceEpoch()}"
        # Ensure geometry type string is valid for QgsVectorLayer constructor
        valid_geom_types = ["Point", "LineString", "Polygon"]
        if geometry_type_str not in valid_geom_types:
              QgsMessageLog.logMessage(f"Cannot create layer '{display_name}': Invalid geometry type '{geometry_type_str}'.", PLUGIN_TAG, level=Qgis.Critical)
              return None
        layer = QgsVectorLayer(f"{geometry_type_str}?crs={target_crs.authid()}", layer_name_internal, "memory")
      
        if not layer or not layer.isValid():
            QgsMessageLog.logMessage(f"Failed create valid layer object for '{display_name}'.", PLUGIN_TAG, level=Qgis.Warning)
            return None
      
        provider = layer.dataProvider()
        if not provider or not provider.addAttributes(fields):
            QgsMessageLog.logMessage(f"Failed setup provider/attributes for '{display_name}'.", PLUGIN_TAG, level=Qgis.Warning)
            return None
        layer.updateFields()
      
        layer.setCustomProperty("safeguarding_style_key", style_key)
        layer.setName(display_name)
      
        if layer.startEditing():
            for f_idx, f in enumerate(features):
              geom = f.geometry()
              # QgsMessageLog.logMessage(f"DEBUG ({layer.name()}): Feature {f_idx} geom is None? {geom is None}, isEmpty? {geom.isEmpty() if geom else 'N/A'}, isValid? {geom.isGeosValid() if geom else 'N/A'}", PLUGIN_TAG, level=Qgis.Info)
            flag, out_feats = provider.addFeatures(features)
            if flag and layer.commitChanges():
                layer.updateExtents()
                project.addMapLayer(layer, False)
                node = layer_group.addLayer(layer)
                if node:
                    node.setName(layer.name()) # Sync node name
                    self._apply_style(layer, self.style_map)
                    self.successfully_generated_layers.append(layer)
                    QgsMessageLog.logMessage(f"Successfully created layer: '{display_name}'.", PLUGIN_TAG, level=Qgis.Info)
                    return layer # Success!
                else:
                    # Failed add node
                    QgsMessageLog.logMessage(f"Warn: Failed add node '{display_name}' to layer tree.", PLUGIN_TAG, level=Qgis.Warning)
                    # --- Start Corrected Indentation ---
                    if project.mapLayer(layer.id()):
                        project.removeMapLayer(layer.id())
                    return None # Node add failed
                    # --- End Corrected Indentation ---
            else:
                # Commit or addFeatures failed
                commit_error = layer.commitErrors() if not flag else "AddFeatures failed"
                layer.rollBack()
                QgsMessageLog.logMessage(f"Failed commit/add features for '{display_name}'. Error: {commit_error}", PLUGIN_TAG, level=Qgis.Warning)
                return None # Commit/Add failed
        else:
            # Start editing failed
            QgsMessageLog.logMessage(f"Failed startEditing for '{display_name}'.", PLUGIN_TAG, level=Qgis.Warning)
            return None # Start editing failed

    # --- Geometry Creation Helpers ---
    def create_arp_layer(self, arp_point: QgsPointXY, arp_east: Optional[float], arp_north: Optional[float],
              icao_code: str, crs: QgsCoordinateReferenceSystem, layer_group: QgsLayerTreeGroup,
              arp_elevation: Optional[float] = None) -> Optional[QgsVectorLayer]: # Added elevation param
      """Creates the ARP point layer using the helper."""
      # Add Elevation field
      fields = QgsFields([
        QgsField("ICAO", QVariant.String),
        QgsField("Name", QVariant.String),
        QgsField("Easting", QVariant.Double),
        QgsField("Northing", QVariant.Double),
        QgsField("Elevation", QVariant.Double, "Elevation (AMSL)", 10, 2) # Added
      ])
      try:
        # Attempt to create geometry with Z value if elevation provided
        arp_geom: Optional[QgsGeometry] = None
        if arp_elevation is not None:
          try: # QgsPoint requires QGIS 3.x, use QgsPointXY as fallback if needed
            from qgis.core import QgsPoint
            arp_geom = QgsGeometry(QgsPoint(arp_point.x(), arp_point.y(), arp_elevation))
          except ImportError:
            arp_geom = QgsGeometry.fromPointXY(arp_point) # Fallback to 2D
            QgsMessageLog.logMessage("QgsPoint (3D) not available, creating 2D ARP geometry.", PLUGIN_TAG, level=Qgis.Warning)
        else:
          arp_geom = QgsGeometry.fromPointXY(arp_point)
          
        if arp_geom is None or arp_geom.isNull(): return None
        
        feature = QgsFeature(fields); feature.setGeometry(arp_geom)
        east_attr = arp_east if arp_east is not None else arp_point.x(); north_attr = arp_north if arp_north is not None else arp_point.y()
        # Set attributes including elevation
        feature.setAttributes([icao_code, f"{icao_code} ARP", east_attr, north_attr, arp_elevation])
        return self._create_and_add_layer( "Point", f"arp_{icao_code}", f"{icao_code} {self.tr('ARP')}", fields, [feature], layer_group, "ARP")
      except Exception as e: QgsMessageLog.logMessage(f"Error in create_arp_layer: {e}", PLUGIN_TAG, level=Qgis.Critical); return None

    def _create_centered_oriented_square(self, center_point: QgsPointXY, side_length: float, description: str = "Square") -> Optional[QgsGeometry]:
        """Creates a square polygon centered on a point."""
        if not center_point or side_length <= 0: return None
        try:
            half_side = side_length / 2.0; min_x = center_point.x() - half_side; max_x = center_point.x() + half_side; min_y = center_point.y() - half_side; max_y = center_point.y() + half_side
            sw = QgsPointXY(min_x, min_y); se = QgsPointXY(max_x, min_y); ne = QgsPointXY(max_x, max_y); nw = QgsPointXY(min_x, max_y)
            return self._create_polygon_from_corners([sw, se, ne, nw], description)
        except Exception as e: QgsMessageLog.logMessage(f"Error _create_centered_square '{description}': {e}", PLUGIN_TAG, level=Qgis.Critical); return None

    def create_runway_centreline_layer(self, point1: QgsPointXY, point2: QgsPointXY, runway_name: str, crs: QgsCoordinateReferenceSystem, layer_group: QgsLayerTreeGroup) -> Optional[QgsVectorLayer]:
        """Creates the runway centreline layer using the helper."""
        try:
            if not isinstance(point1, QgsPointXY) or not isinstance(point2, QgsPointXY) or point1.compare(point2, epsilon=1e-6): return None
            fields = QgsFields([QgsField("RWY_Name", QVariant.String), QgsField("Length_m", QVariant.Double)])
            line_geom = QgsGeometry(QgsLineString([point1, point2]))
            if line_geom.isNull() or line_geom.isEmpty() or not line_geom.isSimple(): return None
            feature = QgsFeature(fields); feature.setGeometry(line_geom); length = line_geom.length(); feature.setAttributes([runway_name, round(length, 3) if length is not None else None])
            return self._create_and_add_layer( "LineString", f"cl_{runway_name.replace('/', '_')}", f"{self.tr('Runway')} {runway_name} {self.tr('Centreline')}", fields, [feature], layer_group, "Runway Centreline")
        except Exception as e: QgsMessageLog.logMessage(f"Error create CL for {runway_name}: {e}", PLUGIN_TAG, level=Qgis.Critical); return None

    def _create_offset_rectangle(self, start_point: QgsPointXY, outward_azimuth_degrees: float, far_edge_offset: float, zone_length_backward: float, half_width: float, description: str = "Offset Rectangle") -> Optional[QgsGeometry]:
        """Creates a rectangle offset from a point along an azimuth."""
        if start_point is None or half_width <= 0: return None
        try:
            backward_azimuth = (outward_azimuth_degrees + 180.0) % 360.0; az_perp_r = (outward_azimuth_degrees + 90.0) % 360.0; az_perp_l = (outward_azimuth_degrees - 90.0 + 360.0) % 360.0
            far_edge_center = start_point.project(far_edge_offset, outward_azimuth_degrees); near_edge_center = far_edge_center.project(zone_length_backward, backward_azimuth)
            if not far_edge_center or not near_edge_center: return None
            near_l = near_edge_center.project(half_width, az_perp_l); near_r = near_edge_center.project(half_width, az_perp_r); far_l = far_edge_center.project(half_width, az_perp_l); far_r = far_edge_center.project(half_width, az_perp_r)
            corner_points = [near_l, near_r, far_r, far_l];
            if not all(p is not None for p in corner_points): return None
            return self._create_polygon_from_corners(corner_points, description)
        except Exception as e: QgsMessageLog.logMessage(f"Error _create_offset_rectangle '{description}': {e}", PLUGIN_TAG, level=Qgis.Critical); return None

    def _create_runway_aligned_rectangle(self, point1: QgsPointXY, point2: QgsPointXY, extension_m: float, half_width_m: float, description: str = "Aligned Rectangle") -> Optional[QgsGeometry]:
        """Creates a rectangle aligned with the line between two points, optionally extended."""
        if not point1 or not point2 or half_width_m <= 0 or point1.compare(point2, 1e-6): return None
        try:
            params = self._get_runway_parameters(point1, point2)
            if not params: return None
            rect_start_center = point1.project(extension_m, params['azimuth_r_p']); rect_end_center = point2.project(extension_m, params['azimuth_p_r'])
            if not rect_start_center or not rect_end_center: return None
            corner_start_l = rect_start_center.project(half_width_m, params['azimuth_perp_l']); corner_start_r = rect_start_center.project(half_width_m, params['azimuth_perp_r']); corner_end_l = rect_end_center.project(half_width_m, params['azimuth_perp_l']); corner_end_r = rect_end_center.project(half_width_m, params['azimuth_perp_r'])
            corner_points = [corner_start_l, corner_start_r, corner_end_r, corner_end_l]
            if not all(p is not None for p in corner_points): return None
            return self._create_polygon_from_corners(corner_points, description)
        except Exception as e: QgsMessageLog.logMessage(f"Error _create_aligned_rectangle '{description}': {e}", PLUGIN_TAG, level=Qgis.Critical); return None

    def _create_trapezoid(self, start_point: QgsPointXY, outward_azimuth_degrees: float, length: float, inner_half_width: float, outer_half_width: float, description: str = "Trapezoid") -> Optional[QgsGeometry]:
        """Creates a trapezoid projecting from a point along an azimuth."""
        if not start_point or length <= 0 or inner_half_width < 0 or outer_half_width < 0: return None
        try:
            az_perp_r = (outward_azimuth_degrees + 90.0) % 360.0; az_perp_l = (outward_azimuth_degrees - 90.0 + 360.0) % 360.0
            inner_l = start_point.project(inner_half_width, az_perp_l); inner_r = start_point.project(inner_half_width, az_perp_r); outer_center = start_point.project(length, outward_azimuth_degrees)
            if not outer_center: return None
            outer_l = outer_center.project(outer_half_width, az_perp_l); outer_r = outer_center.project(outer_half_width, az_perp_r)
            corner_points = [inner_l, inner_r, outer_r, outer_l]
            if not all(p is not None for p in corner_points): return None
            return self._create_polygon_from_corners(corner_points, description)
        except Exception as e: QgsMessageLog.logMessage(f"Error _create_trapezoid '{description}': {e}", PLUGIN_TAG, level=Qgis.Critical); return None

    def _calculate_strip_dimensions(self, runway_data: dict) -> dict:
        """Calculates required strip widths and extension length."""
        arc_num_str = runway_data.get('arc_num'); runway_type = runway_data.get('type1'); runway_width = runway_data.get('width')
        results = {'overall_width': None, 'graded_width': None, 'extension_length': None,'mos_overall_width_ref': "N/A", 'mos_graded_width_ref': "N/A", 'mos_extension_length_ref': "N/A"}
        log_name = runway_data.get('short_name', 'RWY') # For logging
        if not arc_num_str or not runway_type: QgsMessageLog.logMessage(f"Strip calc skipped {log_name}: Missing ARC/Type1.", PLUGIN_TAG, level=Qgis.Info); return results
        try: arc_num = int(arc_num_str)
        except (ValueError, TypeError): QgsMessageLog.logMessage(f"Strip calc skipped {log_name}: Invalid ARC '{arc_num_str}'.", PLUGIN_TAG, level=Qgis.Warning); return results
        is_non_instrument_or_npa = runway_type in ["Non-Instrument (NI)", "Non-Precision Approach (NPA)"]
        if arc_num in [1, 2] and is_non_instrument_or_npa: results.update({'overall_width': 140.0, 'mos_overall_width_ref': "MOS T6.17(4) Code 1/2 NI/NPA"})
        elif arc_num in [1, 2, 3, 4]: results.update({'overall_width': 280.0, 'mos_overall_width_ref': "MOS T6.17(4) Code 3/4 or PA"})
        if arc_num == 1: results.update({'graded_width': 60.0, 'mos_graded_width_ref': "MOS T6.17(1) Code 1"})
        elif arc_num == 2: results.update({'graded_width': 80.0, 'mos_graded_width_ref': "MOS T6.17(1) Code 2"})
        elif arc_num in [3, 4]:
            if runway_width is not None and runway_width < 45.0: results.update({'graded_width': 90.0, 'mos_graded_width_ref': "MOS T6.17(1) Code 3/4 (<45m)"})
            else: results.update({'graded_width': 150.0, 'mos_graded_width_ref': "MOS T6.17(1) Code 3/4 (>=45m)"}) # Assume >= 45 if width missing
        is_non_instrument_code_1_or_2 = (runway_type == "Non-Instrument (NI)" and arc_num in [1, 2])
        if is_non_instrument_code_1_or_2: results.update({'extension_length': 30.0, 'mos_extension_length_ref': "MOS 6.2.5.6(a) NI Code 1/2"})
        else: results.update({'extension_length': 60.0, 'mos_extension_length_ref': "MOS 6.2.5.6(b) Other"})
        QgsMessageLog.logMessage(f"Strip Dims for {log_name}: {results}", PLUGIN_TAG, level=Qgis.Info)
        return results

    def _calculate_resa_dimensions(self, runway_data: dict) -> dict:
        """Calculates required RESA dimensions and applicability."""
        arc_num_str = runway_data.get('arc_num'); type1 = runway_data.get('type1'); type2 = runway_data.get('type2'); runway_width = runway_data.get('width')
        results = {'required': False, 'width': None, 'length': None,'mos_applicability_ref': "MOS 6.2.6.1/2", 'mos_width_ref': "N/A", 'mos_length_ref': "N/A"}
        log_name = runway_data.get('short_name', 'RWY') # For logging
        if not arc_num_str or not type1: QgsMessageLog.logMessage(f"RESA calc skipped {log_name}: Missing ARC/Type1.", PLUGIN_TAG, level=Qgis.Info); return results
        try: arc_num = int(arc_num_str)
        except (ValueError, TypeError): QgsMessageLog.logMessage(f"RESA calc skipped {log_name}: Invalid ARC '{arc_num_str}'.", PLUGIN_TAG, level=Qgis.Warning); return results
        instrument_types = ["Non-Precision Approach (NPA)", "Precision Approach CAT I", "Precision Approach CAT II/III"]
        end1_is_instrument = type1 in instrument_types; end2_is_instrument = type2 in instrument_types if type2 else False
        if arc_num in [3, 4]: results['required'] = True; results['mos_applicability_ref'] += " (Code 3/4)"
        elif arc_num in [1, 2] and (end1_is_instrument or end2_is_instrument): results['required'] = True; results['mos_applicability_ref'] += " (Code 1/2 Instr)"
        if results['required']:
            results['mos_width_ref'] = "MOS 6.2.6.5"; results['mos_length_ref'] = "MOS 6.2.6 & T6.18"
            if runway_width is not None and runway_width > 0: results['width'] = 2.0 * runway_width
            else: QgsMessageLog.logMessage(f"RESA width calc warning {log_name}: Runway width missing.", PLUGIN_TAG, level=Qgis.Warning); results['mos_width_ref'] += " (RWY Width Missing)"
            if arc_num in [1, 2]: results['length'] = 120.0; results['mos_length_ref'] += " (Code 1/2 Pref)"
            elif arc_num in [3, 4]: results['length'] = 240.0; results['mos_length_ref'] += " (Code 3/4 Pref)"
        else: results['mos_applicability_ref'] += " (Not Required)"
        QgsMessageLog.logMessage(f"RESA Dims for {log_name}: {results}", PLUGIN_TAG, level=Qgis.Info)
        return results

    def _get_runway_parameters(self, thr_point: QgsPointXY, rec_thr_point: QgsPointXY) -> Optional[dict]:
        """Calculates basic length and azimuths between two threshold points."""
        if not isinstance(thr_point, QgsPointXY) or not isinstance(rec_thr_point, QgsPointXY) or thr_point.compare(rec_thr_point, 1e-6):
          QgsMessageLog.logMessage("Invalid threshold points for runway parameter calculation.", PLUGIN_TAG, level=Qgis.Warning)
          return None
        try:
          length = thr_point.distance(rec_thr_point)
          azimuth_p_r = thr_point.azimuth(rec_thr_point) # Azimuth Primary THR -> Reciprocal THR
          azimuth_r_p = rec_thr_point.azimuth(thr_point) # Azimuth Reciprocal THR -> Primary THR
          # Add check for valid azimuths if needed (e.g., not None or NaN)
          if length is None or azimuth_p_r is None or azimuth_r_p is None:
            QgsMessageLog.logMessage("Failed to calculate length/azimuth for runway parameters.", PLUGIN_TAG, level=Qgis.Warning)
            return None
          
          azimuth_perp_r = (azimuth_p_r + 90.0) % 360.0
          azimuth_perp_l = (azimuth_p_r - 90.0 + 360.0) % 360.0
          return {'length': length, 'azimuth_p_r': azimuth_p_r, 'azimuth_r_p': azimuth_r_p, 'azimuth_perp_l': azimuth_perp_l, 'azimuth_perp_r': azimuth_perp_r}
        except Exception as e:
          QgsMessageLog.logMessage(f"Error calculating runway parameters: {e}", PLUGIN_TAG, level=Qgis.Critical)
          return None
        
    def _get_physical_runway_endpoints(
        self,
        thr_point_primary: QgsPointXY,
        thr_point_reciprocal: QgsPointXY,
        displaced_thr_primary: float, # Displacement distance BEFORE primary threshold
        displaced_thr_reciprocal: float, # Displacement distance BEFORE reciprocal threshold
        rwy_params: dict # Result from _get_runway_parameters
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
        if not isinstance(thr_point_primary, QgsPointXY) or \
          not isinstance(thr_point_reciprocal, QgsPointXY) or \
          not isinstance(displaced_thr_primary, (int, float)) or \
          not isinstance(displaced_thr_reciprocal, (int, float)) or \
          displaced_thr_primary < 0 or displaced_thr_reciprocal < 0:
          QgsMessageLog.logMessage("Invalid input types for physical endpoint calculation.", PLUGIN_TAG, level=Qgis.Warning)
          return None
    
        if not rwy_params or 'azimuth_p_r' not in rwy_params or 'azimuth_r_p' not in rwy_params:
          QgsMessageLog.logMessage("Missing required azimuths in rwy_params for physical endpoint calculation.", PLUGIN_TAG, level=Qgis.Warning)
          return None
    
        azimuth_p_r = rwy_params['azimuth_p_r'] # Primary -> Reciprocal
        azimuth_r_p = rwy_params['azimuth_r_p'] # Reciprocal -> Primary
    
        # --- Calculate Primary Physical End ---
        # Start at the primary landing threshold.
        # Project "backwards" along the runway centerline.
        # The direction "backwards" from primary threshold is along the azimuth R->P.
        phys_end_point_primary = thr_point_primary
        if displaced_thr_primary > 1e-6: # Use tolerance, only project if displacement exists
          projected_point = thr_point_primary.project(displaced_thr_primary, azimuth_r_p)
          if projected_point:
            phys_end_point_primary = projected_point
          else:
            QgsMessageLog.logMessage(f"Failed to project primary physical endpoint (Dist: {displaced_thr_primary}m, Az: {azimuth_r_p}).", PLUGIN_TAG, level=Qgis.Warning)
            return None # Projection failed
    
        # --- Calculate Reciprocal Physical End ---
        # Start at the reciprocal landing threshold.
        # Project "backwards" along the runway centerline.
        # The direction "backwards" from reciprocal threshold is along the azimuth P->R.
        phys_end_point_reciprocal = thr_point_reciprocal
        if displaced_thr_reciprocal > 1e-6: # Use tolerance
          projected_point = thr_point_reciprocal.project(displaced_thr_reciprocal, azimuth_p_r)
          if projected_point:
            phys_end_point_reciprocal = projected_point
          else:
            QgsMessageLog.logMessage(f"Failed to project reciprocal physical endpoint (Dist: {displaced_thr_reciprocal}m, Az: {azimuth_p_r}).", PLUGIN_TAG, level=Qgis.Warning)
            return None # Projection failed
    
        # --- Calculate Total Physical Length ---
        try:
          total_physical_length = phys_end_point_primary.distance(phys_end_point_reciprocal)
          if total_physical_length is None:
            QgsMessageLog.logMessage("Failed to calculate distance between physical endpoints.", PLUGIN_TAG, level=Qgis.Warning)
            return None
        except Exception as e_dist:
          QgsMessageLog.logMessage(f"Error calculating distance between physical endpoints: {e_dist}", PLUGIN_TAG, level=Qgis.Warning)
          return None
    
        return phys_end_point_primary, phys_end_point_reciprocal, total_physical_length

    def _create_polygon_from_corners(self, corners: List[QgsPointXY], description: str = "Polygon") -> Optional[QgsGeometry]:
        """Creates a QgsGeometry polygon from a list of corner points."""
        if not corners or len(corners) < 3 or None in corners or not all(isinstance(p, QgsPointXY) for p in corners): QgsMessageLog.logMessage(f"Invalid corners for polygon '{description}'.", PLUGIN_TAG, level=Qgis.Warning); return None
        try:
            closed_corners = corners + [corners[0]] if not corners[0].compare(corners[-1], 1e-6) else corners
            exterior_ring = QgsLineString(closed_corners)
            if exterior_ring.isEmpty(): QgsMessageLog.logMessage(f"Empty exterior ring for polygon '{description}'.", PLUGIN_TAG, level=Qgis.Warning); return None
            polygon = QgsPolygon(exterior_ring); geom = QgsGeometry(polygon)
            if geom.isNull() or geom.isEmpty(): QgsMessageLog.logMessage(f"Null/Empty geom after QgsPolygon creation '{description}'.", PLUGIN_TAG, level=Qgis.Warning); return None
            if not geom.isGeosValid():
                QgsMessageLog.logMessage(f"Geom invalid '{description}', attempting makeValid().", PLUGIN_TAG, level=Qgis.Info); geom_valid = geom.makeValid()
                if not geom_valid or geom_valid.isNull() or geom_valid.isEmpty(): QgsMessageLog.logMessage(f"makeValid() failed '{description}'.", PLUGIN_TAG, level=Qgis.Warning); return None
                valid_poly_types = [Qgis.WkbType.Polygon, Qgis.WkbType.PolygonZ, Qgis.WkbType.PolygonM, Qgis.WkbType.PolygonZM]; valid_multipoly_types = [Qgis.WkbType.MultiPolygon, Qgis.WkbType.MultiPolygonZ, Qgis.WkbType.MultiPolygonM, Qgis.WkbType.MultiPolygonZM]
                if geom_valid.wkbType() not in (valid_poly_types + valid_multipoly_types): QgsMessageLog.logMessage(f"makeValid() unexpected type '{description}': {geom_valid.wkbType()}", PLUGIN_TAG, level=Qgis.Warning); return None
                if geom_valid.isMultipart():
                    QgsMessageLog.logMessage(f"makeValid() gave MultiPolygon '{description}', extracting largest.", PLUGIN_TAG, level=Qgis.Info); polygons = geom_valid.asMultiPolygon(); largest_poly_geom = None; max_area = -1.0
                    if polygons:
                        for poly_rings in polygons: temp_poly = QgsPolygon(poly_rings[0], poly_rings[1:]); temp_geom = QgsGeometry(temp_poly)
                        if not temp_geom.isNull(): area = temp_geom.area();
                        if area > max_area: max_area = area; largest_poly_geom = temp_geom
                    geom = largest_poly_geom
                else: geom = geom_valid
            if geom is None or geom.isNull() or geom.isEmpty(): QgsMessageLog.logMessage(f"Final geometry null/empty '{description}'.", PLUGIN_TAG, level=Qgis.Warning); return None
            return geom
        except Exception as e: QgsMessageLog.logMessage(f"Error _create_polygon '{description}': {e}", PLUGIN_TAG, level=Qgis.Critical); return None

    def _create_rectangle_from_start(self, start_center_point: QgsPointXY, outward_azimuth: float,
                    length: float, half_width: float,
                    description: str = "Rectangle") -> Optional[QgsGeometry]:
      """Creates a rectangle starting at a point and extending along an azimuth."""
      if not start_center_point or length <= 0 or half_width < 0: # Allow zero half-width? Check usage. Assume >0 for now.
        if half_width <= 0: QgsMessageLog.logMessage(f"Skipping {description}: half_width <= 0", PLUGIN_TAG, level=Qgis.Warning)
        return None
      try:
        # Calculate end center point by projecting forward
        end_center_point = start_center_point.project(length, outward_azimuth)
        if not end_center_point:
          QgsMessageLog.logMessage(f"Failed to calculate end point for {description}", PLUGIN_TAG, level=Qgis.Warning)
          return None
        
        # Calculate perpendicular azimuths relative to the outward direction
        azimuth_perp_r = (outward_azimuth + 90.0) % 360.0
        azimuth_perp_l = (outward_azimuth - 90.0 + 360.0) % 360.0
        
        # Calculate corners based on start and end center points
        start_l = start_center_point.project(half_width, azimuth_perp_l)
        start_r = start_center_point.project(half_width, azimuth_perp_r)
        end_l = end_center_point.project(half_width, azimuth_perp_l)
        end_r = end_center_point.project(half_width, azimuth_perp_r)
        
        corners = [start_l, start_r, end_r, end_l] # Standard rectangle order
        if not all(p is not None for p in corners):
          QgsMessageLog.logMessage(f"Failed to calculate all corners for {description}", PLUGIN_TAG, level=Qgis.Warning)
          return None
        
        # Use the existing robust polygon creation helper
        return self._create_polygon_from_corners(corners, description)
      except Exception as e:
        QgsMessageLog.logMessage(f"Error in _create_rectangle_from_start for '{description}': {e}", PLUGIN_TAG, level=Qgis.Critical)
        return None

    def generate_physical_geometry(self, runway_data: dict) -> Optional[List[Tuple[str, QgsGeometry, dict]]]:
      """
      Calculates geometry and attributes for physical runway components, including shoulders.
      Constructs shoulders directly as two separate polygons.
      Returns a list of tuples: (element_type_key, geometry, attributes)
      or None if basic parameters are missing.
      """
      # Ensure QgsGeometry is definitely known in this scope
      from qgis.core import QgsGeometry
      
      thr_point = runway_data.get('thr_point'); rec_thr_point = runway_data.get('rec_thr_point')
      runway_width = runway_data.get('width'); shoulder_width = runway_data.get('shoulder')
      runway_name = runway_data.get('short_name', 'RWY')
      log_name = runway_name if runway_name != 'RWY' else f"RWY_{runway_data.get('original_index','?')}"
      
      if not thr_point or not rec_thr_point:
        QgsMessageLog.logMessage(f"Skipping physical geom {log_name}: Missing threshold points.", PLUGIN_TAG, level=Qgis.Warning)
        return None
      
      params = self._get_runway_parameters(thr_point, rec_thr_point)
      if params is None:
        QgsMessageLog.logMessage(f"Skipping physical geom {log_name}: Failed to get runway parameters.", PLUGIN_TAG, level=Qgis.Warning)
        return None
      
      generated_elements: List[Tuple[str, QgsGeometry, dict]] = []
      pavement_corners = {} # To store pavement corners if calculated
      
      # --- 1. Runway Pavement ---
      if runway_width is not None and runway_width > 0:
        try:
          half_width = runway_width / 2.0
          thr_l = thr_point.project(half_width, params['azimuth_perp_l'])
          thr_r = thr_point.project(half_width, params['azimuth_perp_r'])
          rec_l = rec_thr_point.project(half_width, params['azimuth_perp_l'])
          rec_r = rec_thr_point.project(half_width, params['azimuth_perp_r'])
          if all([thr_l, thr_r, rec_l, rec_r]):
            pavement_corners = {'thr_l': thr_l, 'thr_r': thr_r, 'rec_l': rec_l, 'rec_r': rec_r} # Store corners
            pavement_geom = self._create_polygon_from_corners([thr_l, thr_r, rec_r, rec_l], f"Runway Pavement {log_name}")
            if pavement_geom:
              attributes = {'RWY_Name': runway_name, 'Type': 'Runway Pavement', 'Width_m': runway_width, 'Length_m': round(params['length'], 3), 'MOS_Ref': 'MOS 139 6.2.3'}
              generated_elements.append(('Runway', pavement_geom, attributes))
            else: QgsMessageLog.logMessage(f"Failed to generate runway pavement geometry for {log_name}.", PLUGIN_TAG, level=Qgis.Warning); pavement_corners = {} # Clear corners if geom failed
          else: QgsMessageLog.logMessage(f"Failed to calculate pavement corners for {log_name}.", PLUGIN_TAG, level=Qgis.Warning); pavement_corners = {}
        except Exception as e: QgsMessageLog.logMessage(f"Error calculating Runway Pavement for {log_name}: {e}", PLUGIN_TAG, level=Qgis.Warning); pavement_corners = {}
      else: QgsMessageLog.logMessage(f"Skipping Runway Pavement for {log_name}: Width not specified.", PLUGIN_TAG, level=Qgis.Info)
      
      # --- 2. Runway Shoulders (Direct Construction of Left and Right) ---
      if shoulder_width is not None and shoulder_width > 0 and pavement_corners: # Need pavement corners
        try:
          # Calculate the 4 outer corner points by projecting from pavement corners
          outer_thr_l = pavement_corners['thr_l'].project(shoulder_width, params['azimuth_perp_l'])
          outer_thr_r = pavement_corners['thr_r'].project(shoulder_width, params['azimuth_perp_r'])
          outer_rec_l = pavement_corners['rec_l'].project(shoulder_width, params['azimuth_perp_l'])
          outer_rec_r = pavement_corners['rec_r'].project(shoulder_width, params['azimuth_perp_r'])
          
          # Define common attributes for shoulders
          shoulder_attrs = {'RWY_Name': runway_name, 'Type': 'Runway Shoulder', 'Width_m': shoulder_width, 'Length_m': round(params['length'], 3), 'MOS_Ref': 'MOS 139 6.2.4'}
          
          # Create Left Shoulder Polygon
          if all([outer_thr_l, outer_rec_l]):
            left_corners = [pavement_corners['thr_l'], outer_thr_l, outer_rec_l, pavement_corners['rec_l']]
            left_shoulder_poly = self._create_polygon_from_corners(left_corners, f"Left Shoulder {log_name}")
            if left_shoulder_poly:
              generated_elements.append(('Shoulder', left_shoulder_poly, shoulder_attrs.copy())) # Append left shoulder
              QgsMessageLog.logMessage(f"Left Shoulder geometry generated for {log_name}.", PLUGIN_TAG, level=Qgis.Info)
            else: QgsMessageLog.logMessage(f"Failed to generate left shoulder geometry for {log_name}.", PLUGIN_TAG, level=Qgis.Warning)
          else: QgsMessageLog.logMessage(f"Failed to calculate outer corners for left shoulder for {log_name}.", PLUGIN_TAG, level=Qgis.Warning)
          
          # Create Right Shoulder Polygon
          if all([outer_thr_r, outer_rec_r]):
            # Note winding order: pavement edge -> outer edge -> pavement edge
            right_corners = [pavement_corners['thr_r'], pavement_corners['rec_r'], outer_rec_r, outer_thr_r]
            right_shoulder_poly = self._create_polygon_from_corners(right_corners, f"Right Shoulder {log_name}")
            if right_shoulder_poly:
              generated_elements.append(('Shoulder', right_shoulder_poly, shoulder_attrs.copy())) # Append right shoulder
              QgsMessageLog.logMessage(f"Right Shoulder geometry generated for {log_name}.", PLUGIN_TAG, level=Qgis.Info)
            else: QgsMessageLog.logMessage(f"Failed to generate right shoulder geometry for {log_name}.", PLUGIN_TAG, level=Qgis.Warning)
          else: QgsMessageLog.logMessage(f"Failed to calculate outer corners for right shoulder for {log_name}.", PLUGIN_TAG, level=Qgis.Warning)
          
        except KeyError as ke: QgsMessageLog.logMessage(f"Error calculating Shoulders {log_name}: Missing pavement corner key {ke}", PLUGIN_TAG, level=Qgis.Warning)
        except Exception as e_shld: QgsMessageLog.logMessage(f"Error calculating Shoulders {log_name}: {e_shld}", PLUGIN_TAG, level=Qgis.Warning)
      elif shoulder_width is not None and shoulder_width > 0:
        QgsMessageLog.logMessage(f"Skipping Shoulders for {log_name}: Pavement corners missing.", PLUGIN_TAG, level=Qgis.Info)
        
      # --- 3. Runway Strips ---
      # (Strip logic remains unchanged)
      strip_dims = None; strip_end_center_p = None; strip_end_center_r = None; strip_length = None
      try:
        strip_dims = self._calculate_strip_dimensions(runway_data)
        if strip_dims and all(strip_dims.get(dim) is not None for dim in ['overall_width', 'graded_width', 'extension_length']):
          extension = strip_dims['extension_length']; graded_width = strip_dims['graded_width']; overall_width = strip_dims['overall_width']; graded_half_width = graded_width / 2.0; overall_half_width = overall_width / 2.0
          strip_end_center_p = thr_point.project(extension, params['azimuth_r_p']); strip_end_center_r = rec_thr_point.project(extension, params['azimuth_p_r'])
          if strip_end_center_p and strip_end_center_r:
            strip_length = strip_end_center_p.distance(strip_end_center_r)
            # 3a. Graded Strip
            graded_strip_geom = self._create_runway_aligned_rectangle(strip_end_center_p, strip_end_center_r, 0.0, graded_half_width, f"Graded Strip {log_name}")
            if graded_strip_geom: graded_attrs = {'RWY_Name': runway_name, 'Type': 'Graded Strip', 'Width_m': graded_width, 'Length_m': round(strip_length, 3), 'MOS_Ref': f"{strip_dims.get('mos_graded_width_ref','')}; {strip_dims.get('mos_extension_length_ref','')}"}; generated_elements.append(('GradedStrip', graded_strip_geom, graded_attrs))
            else: QgsMessageLog.logMessage(f"Failed to generate graded strip geometry for {log_name}.", PLUGIN_TAG, level=Qgis.Warning)
            # 3b. Overall Strip
            overall_strip_geom = self._create_runway_aligned_rectangle(strip_end_center_p, strip_end_center_r, 0.0, overall_half_width, f"Overall Strip {log_name}")
            if overall_strip_geom: overall_attrs = {'RWY_Name': runway_name, 'Type': 'Overall Strip', 'Width_m': overall_width, 'Length_m': round(strip_length, 3), 'MOS_Ref': f"{strip_dims.get('mos_overall_width_ref','')}; {strip_dims.get('mos_extension_length_ref','')}"}; generated_elements.append(('OverallStrip', overall_strip_geom, overall_attrs))
            else: QgsMessageLog.logMessage(f"Failed to generate overall strip geometry for {log_name}.", PLUGIN_TAG, level=Qgis.Warning)
          else: strip_dims = None; QgsMessageLog.logMessage(f"Skipping Strips for {log_name}: Invalid strip end points.", PLUGIN_TAG, level=Qgis.Warning)
        else: strip_dims = None; QgsMessageLog.logMessage(f"Skipping Strips for {log_name}: Strip dimensions incomplete.", PLUGIN_TAG, level=Qgis.Info)
      except Exception as e: QgsMessageLog.logMessage(f"Error calculating Strips for {log_name}: {e}", PLUGIN_TAG, level=Qgis.Warning); strip_dims = None
      
      # --- 4. RESAs ---
      try:
        resa_dims = self._calculate_resa_dimensions(runway_data)
        # Check if RESAs are required AND strip ends were successfully calculated
        if resa_dims and resa_dims.get('required') and strip_dims and strip_end_center_p and strip_end_center_r and all(resa_dims.get(k) is not None for k in ['width', 'length']):
          resa_width = resa_dims['width']; resa_length = resa_dims['length']; resa_half_width = resa_width / 2.0
          primary_desig, reciprocal_desig = runway_name.split('/') if '/' in runway_name else ("Primary", "Reciprocal")
          resa_base_attrs = {'RWY_Name': runway_name, 'Type': 'RESA', 'Length_m': resa_length, 'Width_m': resa_width, 'MOS_Ref': f"{resa_dims.get('mos_applicability_ref','')}; {resa_dims.get('mos_width_ref','')}; {resa_dims.get('mos_length_ref','')}"}
          
          # RESA 1 (Primary End - extends outwards from primary strip end)
          # Start point: strip_end_center_p (the end of the strip beyond the primary threshold)
          # Outward azimuth: azimuth_r_p (the direction AWAY from the reciprocal threshold, extending outwards)
          try:
            resa1_geom = self._create_rectangle_from_start( # USE NEW HELPER
              strip_end_center_p, params['azimuth_r_p'], resa_length, resa_half_width, f"RESA {primary_desig}"
            )
            if resa1_geom:
              resa1_attrs = resa_base_attrs.copy(); resa1_attrs['End_Desig'] = primary_desig
              generated_elements.append(('RESA', resa1_geom, resa1_attrs))
            else: QgsMessageLog.logMessage(f"Failed to generate RESA {primary_desig} geometry for {log_name}.", PLUGIN_TAG, level=Qgis.Warning)
          except Exception as e_resa1: QgsMessageLog.logMessage(f"Error RESA {primary_desig} {log_name}: {e_resa1}", PLUGIN_TAG, level=Qgis.Warning)
          
          # RESA 2 (Reciprocal End - extends outwards from reciprocal strip end)
          # Start point: strip_end_center_r (the end of the strip beyond the reciprocal threshold)
          # Outward azimuth: azimuth_p_r (the direction AWAY from the primary threshold, extending outwards)
          try:
            resa2_geom = self._create_rectangle_from_start( # USE NEW HELPER
              strip_end_center_r, params['azimuth_p_r'], resa_length, resa_half_width, f"RESA {reciprocal_desig}"
            )
            if resa2_geom:
              resa2_attrs = resa_base_attrs.copy(); resa2_attrs['End_Desig'] = reciprocal_desig
              generated_elements.append(('RESA', resa2_geom, resa2_attrs))
            else: QgsMessageLog.logMessage(f"Failed to generate RESA {reciprocal_desig} geometry for {log_name}.", PLUGIN_TAG, level=Qgis.Warning)
          except Exception as e_resa2: QgsMessageLog.logMessage(f"Error RESA {reciprocal_desig} {log_name}: {e_resa2}", PLUGIN_TAG, level=Qgis.Warning)
        elif resa_dims and resa_dims.get('required'):
          QgsMessageLog.logMessage(f"Skipping RESAs for {log_name}: Required but strip data/dims incomplete.", PLUGIN_TAG, level=Qgis.Info)
        # else: RESAs not required or dims missing
          
      except Exception as e_resa_section: # Catch errors in the main RESA block logic
        QgsMessageLog.logMessage(f"Error processing RESA Section for {log_name}: {e_resa_section}", PLUGIN_TAG, level=Qgis.Warning)
      
      # --- 5. Stopways ---
      # (Placeholder)
      
      QgsMessageLog.logMessage(f"Physical geometry finished for {log_name}. Generated {len(generated_elements)} element types.", PLUGIN_TAG, level=Qgis.Info)
      return generated_elements if generated_elements else None
  
    def _generate_airport_wide_ols(self, processed_runway_data_list: List[dict],
                                   ols_layer_group: QgsLayerTreeGroup,
                                   reference_elevation_datum: float,
                                   icao_code: str) -> bool:
        """
        Generates airport-wide OLS: IHS (Convex Hull approx), Conical (with contours), OHS.
        Includes placeholder for Transitional.
        Requires processed runway data, RED, group, and ICAO code.
        """
        QgsMessageLog.logMessage(f"Starting Airport-Wide OLS Generation (ICAO: {icao_code}, RED: {reference_elevation_datum:.2f}m)", PLUGIN_TAG, level=Qgis.Info)
        overall_success = False
        IHS_HEIGHT_ABOVE_RED = 45.0 # Standard IHS height - Verify MOS 139 8.2.18
        IHS_ELEVATION_AMSL = reference_elevation_datum + IHS_HEIGHT_ABOVE_RED
        BUFFER_SEGMENTS = 36 # Segments for buffers
        # CONICAL_CONTOUR_INTERVAL = 10.0 # Height interval in meters
      
        # Variables needed across sections
        ihs_base_geom: Optional[QgsGeometry] = None
        highest_arc_num = 0
        highest_precision_type_str = "Non-Instrument (NI)" # Track highest precision string
      
        # --- 1. Generate Individual Strip Outline Geometries ---
        # ... (This section remains unchanged - calculates strip_outline_geoms, highest_arc_num, highest_precision_type_str) ...
        strip_outline_geoms: List[QgsGeometry] = []
        QgsMessageLog.logMessage("Generating individual strip outlines for IHS base...", PLUGIN_TAG, level=Qgis.Info)
        for rwy_data in processed_runway_data_list:
            rwy_name = rwy_data.get('short_name', f"RWY_{rwy_data.get('original_index','?')}")
            thr_point = rwy_data.get('thr_point'); rec_thr_point = rwy_data.get('rec_thr_point')
            strip_dims = rwy_data.get('calculated_strip_dims')
            arc_num_str = rwy_data.get('arc_num'); type1_str = rwy_data.get('type1'); type2_str = rwy_data.get('type2')
            if not all([thr_point, rec_thr_point, strip_dims, arc_num_str]): continue
            try: arc_num = int(arc_num_str); highest_arc_num = max(highest_arc_num, arc_num)
            except ValueError: arc_num = 0
            type_order = ["", "Non-Instrument (NI)", "Non-Precision Approach (NPA)", "Precision Approach CAT I", "Precision Approach CAT II/III"]
            idx1 = type_order.index(type1_str) if type1_str in type_order else 1; idx2 = type_order.index(type2_str) if type2_str in type_order else 1
            current_max_type_str = type_order[max(idx1, idx2)]
            highest_idx_overall = type_order.index(highest_precision_type_str) if highest_precision_type_str in type_order else 1
            current_max_idx = type_order.index(current_max_type_str)
            if current_max_idx > highest_idx_overall: highest_precision_type_str = current_max_type_str
            strip_width = strip_dims.get('overall_width'); strip_ext = strip_dims.get('extension_length')
            if strip_width is None or strip_width <= 0 or strip_ext is None: continue
            rwy_params = self._get_runway_parameters(thr_point, rec_thr_point);
            if not rwy_params: continue
            strip_end_p = thr_point.project(strip_ext, rwy_params['azimuth_r_p']); strip_end_r = rec_thr_point.project(strip_ext, rwy_params['azimuth_p_r'])
            if not strip_end_p or not strip_end_r: continue
            ihs_lookup_type_abbr = current_max_type_str; ihs_params = ols_dimensions.get_ols_params(arc_num, ihs_lookup_type_abbr, 'IHS')
            ihs_end_radius = ihs_params.get('radius') if ihs_params else None
            if ihs_end_radius is None or ihs_end_radius <= 0: ihs_end_radius = strip_width / 2.0
            try:
                 buffer_p = QgsGeometry.fromPointXY(strip_end_p).buffer(ihs_end_radius, BUFFER_SEGMENTS); buffer_r = QgsGeometry.fromPointXY(strip_end_r).buffer(ihs_end_radius, BUFFER_SEGMENTS)
                 corner_p_l = strip_end_p.project(ihs_end_radius, rwy_params['azimuth_perp_l']); corner_p_r = strip_end_p.project(ihs_end_radius, rwy_params['azimuth_perp_r'])
                 corner_r_l = strip_end_r.project(ihs_end_radius, rwy_params['azimuth_perp_l']); corner_r_r = strip_end_r.project(ihs_end_radius, rwy_params['azimuth_perp_r'])
                 if all([corner_p_l, corner_p_r, corner_r_l, corner_r_r]): connector = self._create_polygon_from_corners([corner_p_l, corner_p_r, corner_r_r, corner_r_l], f"Strip Connector {rwy_name}")
                 else: connector = None
                 if buffer_p and buffer_r and connector: runway_strip_geom = QgsGeometry.unaryUnion([buffer_p, buffer_r, connector]);
                 if runway_strip_geom and not runway_strip_geom.isEmpty(): strip_outline_geoms.append(runway_strip_geom)
            except Exception as e_strip_geom: QgsMessageLog.logMessage(f"Error generating strip outline geom for {rwy_name}: {e_strip_geom}", PLUGIN_TAG, level=Qgis.Warning)
          
          
        # --- 2. Combine Outlines & Calculate Convex Hull for IHS Base ---
        # ... (This section remains unchanged - calculates ihs_base_geom using Convex Hull) ...
        if not strip_outline_geoms: QgsMessageLog.logMessage("IHS Generation Failed: No valid runway strip outlines generated.", PLUGIN_TAG, level=Qgis.Critical); return False
        QgsMessageLog.logMessage(f"Creating IHS base from Convex Hull of {len(strip_outline_geoms)} strip outlines...", PLUGIN_TAG, level=Qgis.Info)
        try:
            merged_geom = QgsGeometry.unaryUnion(strip_outline_geoms);
            if not merged_geom or merged_geom.isEmpty(): raise ValueError("unaryUnion failed.")
            ihs_base_geom = merged_geom.convexHull()
            if not ihs_base_geom or ihs_base_geom.isEmpty(): raise ValueError("convexHull failed.")
            if not ihs_base_geom.isGeosValid(): ihs_base_geom = ihs_base_geom.makeValid()
            if not ihs_base_geom or not ihs_base_geom.isGeosValid(): raise ValueError("makeValid failed after convexHull.")
        except Exception as e_hull: QgsMessageLog.logMessage(f"IHS Generation Failed: Error during Convex Hull: {e_hull}", PLUGIN_TAG, level=Qgis.Critical); return False
        QgsMessageLog.logMessage("Successfully generated IHS base geometry (Convex Hull).", PLUGIN_TAG, level=Qgis.Info)
      
      
        # --- 3. Create IHS Layer ---
        # ... (This section remains unchanged - creates the IHS layer) ...
        ihs_feature: Optional[QgsFeature] = None
        try:
            if ihs_base_geom and not ihs_base_geom.isEmpty():
                ihs_ref_params = ols_dimensions.get_ols_params(highest_arc_num, highest_precision_type_str, 'IHS')
                ref_text = ihs_ref_params.get('ref', 'MOS 139 8.2.18') if ihs_ref_params else 'MOS 139 8.2.18'
                fields = self._get_ols_fields("IHS"); feature = QgsFeature(fields); feature.setGeometry(ihs_base_geom)
                attr_map = { "RWY_Name": self.tr("Airport Wide"), "Surface": "IHS", "Elevation": IHS_ELEVATION_AMSL, "Height_AGL": IHS_HEIGHT_ABOVE_RED, "Ref": ref_text, "Shape_Desc": "Convex Hull Approximation" }
                for name, value in attr_map.items(): idx = fields.indexFromName(name);
                if idx != -1: feature.setAttribute(idx, value)
                ihs_feature = feature
                layer = self._create_and_add_layer("Polygon", f"OLS_IHS_{icao_code}", f"{self.tr('OLS')} IHS {icao_code}", fields, [feature], ols_layer_group, "OLS IHS")
                if layer: overall_success = True; QgsMessageLog.logMessage("IHS Layer Created (Convex Hull Approx).", PLUGIN_TAG, level=Qgis.Info)
                else: QgsMessageLog.logMessage("Failed to create IHS Layer.", PLUGIN_TAG, level=Qgis.Warning); ihs_base_geom = None
            else: QgsMessageLog.logMessage("Skipping IHS Layer creation: Base geometry invalid or empty.", PLUGIN_TAG, level=Qgis.Warning); ihs_base_geom = None
        except Exception as e_ihs_layer: QgsMessageLog.logMessage(f"Error creating IHS Feature/Layer: {e_ihs_layer}", PLUGIN_TAG, level=Qgis.Critical); ihs_base_geom = None
  
        # --- 5. Generate Conical Surface & Contours ---
        conical_feature: Optional[QgsFeature] = None
        outer_conical_geom: Optional[QgsGeometry] = None # Store outer boundary for OHS difference
        main_conical_generated_ok = False
        conical_params: Optional[Dict] = None
        height_extent_agl: Optional[float] = None
        slope: Optional[float] = None
        conical_outer_elevation: Optional[float] = None
        conical_geom: Optional[QgsGeometry] = None # Store the final conical ring geom

        # QgsMessageLog.logMessage(f"DEBUG: State before Conical check: ihs_base_geom is None? {ihs_base_geom is None}, isEmpty? {ihs_base_geom.isEmpty() if ihs_base_geom else 'N/A'}", PLUGIN_TAG, level=Qgis.Info)
        if ihs_base_geom and not ihs_base_geom.isEmpty(): # Check IHS geom is valid
            try: # Outer try for parameter lookup and outer buffer generation
                conical_params = ols_dimensions.get_ols_params(highest_arc_num, highest_precision_type_str, 'CONICAL')
                if conical_params:
                    height_extent_agl = conical_params.get('height_extent_agl') # Height above IHS
                    slope = conical_params.get('slope')
                    ref = conical_params.get('ref', 'MOS 139 8.2.19')
                  
                    if slope is not None and slope > 0 and height_extent_agl is not None and height_extent_agl > 0:
                        horizontal_extent = height_extent_agl / slope
                        conical_outer_elevation = IHS_ELEVATION_AMSL + height_extent_agl
                        QgsMessageLog.logMessage(f"Generating Conical Surface: Slope={slope*100:.1f}%, Height Above IHS={height_extent_agl:.1f}m, Horiz Ext={horizontal_extent:.1f}m, Final Elev AMSL={conical_outer_elevation:.2f}m", PLUGIN_TAG, level=Qgis.Info)
                      
                        # --- Generate Outer Boundary ---
                        temp_outer_geom = ihs_base_geom.buffer(horizontal_extent, BUFFER_SEGMENTS)
                        if temp_outer_geom and not temp_outer_geom.isEmpty():
                              temp_outer_geom = temp_outer_geom.makeValid()
                              if temp_outer_geom.isGeosValid():
                                  # Assign to outer_conical_geom *if* buffer is valid
                                  outer_conical_geom = temp_outer_geom # KEEP THIS ASSIGNMENT
                                  QgsMessageLog.logMessage("Successfully generated valid Conical outer boundary.", PLUGIN_TAG, level=Qgis.Info)
                                
                                  # --- Generate Conical Ring (if outer boundary succeeded) ---
                                  # This inner try focuses only on the difference and layer creation
                                  try:
                                      temp_conical_geom = outer_conical_geom.difference(ihs_base_geom)
                                      if temp_conical_geom: temp_conical_geom = temp_conical_geom.makeValid()
                                    
                                      if temp_conical_geom and not temp_conical_geom.isEmpty() and temp_conical_geom.isGeosValid():
                                          conical_geom = temp_conical_geom # Store the valid ring geom
                                        
                                          # Create feature for the main conical ring
                                          fields = self._get_ols_fields("Conical")
                                          feature = QgsFeature(fields)
                                          feature.setGeometry(conical_geom)
                                          attr_map = { "RWY_Name": self.tr("Airport Wide"), "Surface": "Conical", "Elevation": conical_outer_elevation, "Height_AGL": IHS_HEIGHT_ABOVE_RED + height_extent_agl, "Slope_Perc": slope * 100.0, "Ref": ref, "Height_Extent": height_extent_agl }
                                          for name, value in attr_map.items():
                                              idx = fields.indexFromName(name)
                                              if idx != -1: feature.setAttribute(idx, value)
                                          conical_feature = feature # Store main feature
                                        
                                          # Create layer for the main conical ring
                                          layer = self._create_and_add_layer("Polygon", f"OLS_Conical_{icao_code}", f"{self.tr('OLS')} Conical {icao_code}", fields, [feature], ols_layer_group, "OLS Conical")
                                          if layer:
                                              overall_success = True
                                              main_conical_generated_ok = True # Flag success for contours
                                              QgsMessageLog.logMessage("Conical Layer Created.", PLUGIN_TAG, level=Qgis.Info)
                                          else:
                                              QgsMessageLog.logMessage("Failed to create Conical Layer.", PLUGIN_TAG, level=Qgis.Warning)
                                      else:
                                          QgsMessageLog.logMessage("Failed generate valid Conical ring geometry (difference/makeValid).", PLUGIN_TAG, level=Qgis.Warning)
                                  except Exception as e_conical_ring:
                                      QgsMessageLog.logMessage(f"Error during Conical ring generation/layer creation: {e_conical_ring}", PLUGIN_TAG, level=Qgis.Warning)
                                  # --- End Inner Try ---
                              else:
                                  QgsMessageLog.logMessage("Failed generate valid outer Conical buffer after makeValid.", PLUGIN_TAG, level=Qgis.Warning)
                        else:
                              QgsMessageLog.logMessage("Failed generate outer Conical buffer (buffer returned None/empty).", PLUGIN_TAG, level=Qgis.Warning)
                    elif height_extent_agl is not None and height_extent_agl <= 0:
                        QgsMessageLog.logMessage(f"Skipping Conical Surface: Height extent zero or negative.", PLUGIN_TAG, level=Qgis.Info)
                    else:
                        QgsMessageLog.logMessage(f"Skipping Conical Surface: Invalid params (Slope/Height Extent).", PLUGIN_TAG, level=Qgis.Warning)
                else:
                    QgsMessageLog.logMessage(f"Skipping Conical Surface: No params found for Code {highest_arc_num}, Type {highest_precision_type_str}.", PLUGIN_TAG, level=Qgis.Warning)
            except Exception as e_conical_outer:
                  QgsMessageLog.logMessage(f"Error preparing for Conical Surface generation: {e_conical_outer}", PLUGIN_TAG, level=Qgis.Critical)
        else:
            QgsMessageLog.logMessage(f"Skipping Conical Surface generation: IHS geometry not available.", PLUGIN_TAG, level=Qgis.Info)
        # --- END OF SECTION 4 (Main Conical Surface Generation) ---
          
          
        # --- 5b. Generate Conical CONTOURS ---
        contour_features: List[QgsFeature] = []
        # Check all necessary conditions before starting contour loop
        # Needs IHS geom, slope/height from params, max elevation calculated, and main conical layer success
        if main_conical_generated_ok and ihs_base_geom and slope and height_extent_agl and height_extent_agl > 0 and conical_outer_elevation is not None:
            QgsMessageLog.logMessage(f"Generating Conical Contours at {CONICAL_CONTOUR_INTERVAL}m intervals...", PLUGIN_TAG, level=Qgis.Info)
            previous_contour_geom = QgsGeometry(ihs_base_geom) # Start with IHS as inner boundary
            ref = conical_params.get('ref', 'MOS 139 8.2.19') if conical_params else 'MOS 139 8.2.19' # Get ref again
          
            # Calculate the first contour elevation level *above* the IHS
            if IHS_ELEVATION_AMSL % CONICAL_CONTOUR_INTERVAL == 0:
                  first_contour_elev_amsl = IHS_ELEVATION_AMSL + CONICAL_CONTOUR_INTERVAL
            else:
                  first_contour_elev_amsl = math.ceil(IHS_ELEVATION_AMSL / CONICAL_CONTOUR_INTERVAL) * CONICAL_CONTOUR_INTERVAL
              
            current_target_contour_elev_amsl = first_contour_elev_amsl
          
            # Loop while the target contour is at or below the max conical elevation
            while current_target_contour_elev_amsl <= conical_outer_elevation + 1e-6: # Add tolerance
                contour_h_above_ihs = current_target_contour_elev_amsl - IHS_ELEVATION_AMSL
          
                # Safety check / precision issue prevention
                if contour_h_above_ihs < -1e-6: # Should not happen
                      QgsMessageLog.logMessage(f"Warning: Negative height above IHS calculated for contour {current_target_contour_elev_amsl:.0f}m. Skipping.", PLUGIN_TAG, level=Qgis.Warning)
                      current_target_contour_elev_amsl += CONICAL_CONTOUR_INTERVAL
                      continue
                # Clamp height above IHS to not exceed max extent
                contour_h_above_ihs = min(contour_h_above_ihs, height_extent_agl)
                # Skip if height above IHS is effectively zero (can happen if first contour is exactly at max height)
                if contour_h_above_ihs < 1e-6 :
                    current_target_contour_elev_amsl += CONICAL_CONTOUR_INTERVAL
                    continue

                try:
                    horizontal_dist = contour_h_above_ihs / slope
                    outer_geom = ihs_base_geom.buffer(horizontal_dist, BUFFER_SEGMENTS)
                  
                    if outer_geom and not outer_geom.isEmpty():
                        outer_geom = outer_geom.makeValid()
                        if outer_geom.isGeosValid():
                            # Ensure previous geom is valid before difference
                            if previous_contour_geom and not previous_contour_geom.isGeosValid():
                                previous_contour_geom = previous_contour_geom.makeValid()
                              
                            if previous_contour_geom and previous_contour_geom.isGeosValid():
                                ring_geom = outer_geom.difference(previous_contour_geom)
                                if ring_geom: ring_geom = ring_geom.makeValid()
                              
                                if ring_geom and not ring_geom.isEmpty() and ring_geom.isGeosValid():
                                    # Create feature for this contour ring
                                    fields = self._get_conical_contour_fields()
                                    feature = QgsFeature(fields)
                                    feature.setGeometry(ring_geom)
                                    attr_map = { "Surface": f"Conical Contour {current_target_contour_elev_amsl:.0f}m", "Contour_Elev_AMSL": current_target_contour_elev_amsl, "Contour_Hgt_Abv_IHS": contour_h_above_ihs, "Ref": ref }
                                    for name, value in attr_map.items(): idx = fields.indexFromName(name);
                                    if idx != -1: feature.setAttribute(idx, value)
                                    contour_features.append(feature)
                                else: QgsMessageLog.logMessage(f"Warning: Invalid/empty ring geometry for contour {current_target_contour_elev_amsl:.0f}m.", PLUGIN_TAG, level=Qgis.Warning)
                              
                            # Update previous geometry for next iteration
                            previous_contour_geom = QgsGeometry(outer_geom) # Use copy for safety
                        else: QgsMessageLog.logMessage(f"Warning: makeValid failed for outer contour geom at elev={current_target_contour_elev_amsl}m.", PLUGIN_TAG, level=Qgis.Warning); break
                    else: QgsMessageLog.logMessage(f"Warning: Buffer failed for outer contour geom at elev={current_target_contour_elev_amsl}m.", PLUGIN_TAG, level=Qgis.Warning); break
                except Exception as e_contour: QgsMessageLog.logMessage(f"Error generating contour ring at elev={current_target_contour_elev_amsl}m: {e_contour}", PLUGIN_TAG, level=Qgis.Warning); break

                # Break if we've processed the final height extent (avoid infinite loop on precision issues)
                if contour_h_above_ihs >= height_extent_agl - 1e-6: # Use tolerance
                    break

                # Increment to the next contour level
                current_target_contour_elev_amsl += CONICAL_CONTOUR_INTERVAL
            # --- End Contour Loop ---

            # Create the contour layer if any features were generated
            if contour_features:
                fields = self._get_conical_contour_fields()
                style_key_contour = "OLS Conical Contour"; layer_name_contour = f"{self.tr('OLS')} Conical Contours {icao_code}"; internal_name_contour = f"OLS_Conical_Contours_{icao_code}"
                contour_layer = self._create_and_add_layer("Polygon", internal_name_contour, layer_name_contour, fields, contour_features, ols_layer_group, style_key_contour)
                if contour_layer: overall_success = True; QgsMessageLog.logMessage(f"Created Conical Contour layer with {len(contour_features)} features.", PLUGIN_TAG, level=Qgis.Info)
                else: QgsMessageLog.logMessage("Failed to create Conical Contour layer.", PLUGIN_TAG, level=Qgis.Warning)
        # --- END OF SECTION 4b (Conical Contours) ---
              
              
        # --- 6. Generate Outer Horizontal Surface (OHS) ---
        ohs_params = ols_dimensions.get_ols_params(highest_arc_num, highest_precision_type_str, 'OHS')
        if ohs_params:
            QgsMessageLog.logMessage(f"Outer Horizontal Surface required (Code {highest_arc_num}, Type {highest_precision_type_str}).", PLUGIN_TAG, level=Qgis.Info)
            try:
                radius = ohs_params.get('radius'); height_agl = ohs_params.get('height_agl'); ref = ohs_params.get('ref', 'MOS 139 8.2.20')
                if radius is None or height_agl is None: raise ValueError("Missing OHS radius or height AGL.")
                ohs_elevation_amsl = reference_elevation_datum + height_agl
                arp_point_xy: Optional[QgsPointXY] = None; project = QgsProject.instance(); arp_layer_name = f"{icao_code} ARP"; arp_layers = project.mapLayersByName(arp_layer_name)
                if arp_layers: arp_feat = next(arp_layers[0].getFeatures(), None);
                if arp_feat and arp_feat.geometry() and arp_feat.geometry().wkbType() in [Qgis.WkbType.Point, Qgis.WkbType.PointZ]: arp_point_xy = arp_feat.geometry().asPoint()
              
                if arp_point_xy and radius > 0:
                      center_geom = QgsGeometry.fromPointXY(arp_point_xy)
                      ohs_full_circle_geom = center_geom.buffer(radius, GUIDELINE_C_BUFFER_SEGMENTS) # Use high segments
                      if ohs_full_circle_geom and not ohs_full_circle_geom.isEmpty():
                          ohs_full_circle_geom = ohs_full_circle_geom.makeValid()
                          if ohs_full_circle_geom.isGeosValid():
                                ohs_final_geom = ohs_full_circle_geom # Default to full circle
                            
                                # Difference conical outer boundary (if it was successfully created and is valid)
                                if outer_conical_geom and not outer_conical_geom.isEmpty() and outer_conical_geom.isGeosValid():
                                    QgsMessageLog.logMessage("Attempting to difference Conical outer boundary from OHS circle.", PLUGIN_TAG, level=Qgis.Info)
                                    try: # Specific try for difference
                                        difference_geom = ohs_full_circle_geom.difference(outer_conical_geom)
                                        if difference_geom:
                                            difference_geom = difference_geom.makeValid()
                                            if difference_geom.isGeosValid() and not difference_geom.isEmpty():
                                                ohs_final_geom = difference_geom # Use the difference geom
                                                QgsMessageLog.logMessage("Successfully created OHS geometry (Difference applied).", PLUGIN_TAG, level=Qgis.Info)
                                            else: QgsMessageLog.logMessage("Warning: Difference op for OHS result invalid/empty. Using full circle.", PLUGIN_TAG, level=Qgis.Warning)
                                        else: QgsMessageLog.logMessage("Warning: Difference op for OHS returned None. Using full circle.", PLUGIN_TAG, level=Qgis.Warning)
                                    except Exception as e_diff: QgsMessageLog.logMessage(f"Warning: Error during OHS difference operation: {e_diff}. Using full circle.", PLUGIN_TAG, level=Qgis.Warning)
                                else:
                                    QgsMessageLog.logMessage("Warning: Conical outer boundary not available or invalid for OHS difference. Using full circle.", PLUGIN_TAG, level=Qgis.Warning)
                                  
                                # Create feature with the final OHS geometry
                                fields = self._get_ols_fields("OHS")
                                feature = QgsFeature(fields)
                                feature.setGeometry(ohs_final_geom)
                                attr_map = { "Surface": "OHS", "Elevation": ohs_elevation_amsl, "Height_AGL": height_agl, "Ref": ref, "Radius_m": radius }
                                if fields.indexFromName("RWY_Name") != -1: attr_map["RWY_Name"] = self.tr("Airport Wide")
                                for name, value in attr_map.items(): idx = fields.indexFromName(name);
                                if idx != -1: feature.setAttribute(idx, value)
                                elif name == "Radius_m": QgsMessageLog.logMessage("Warning: OHS Radius_m field missing.", PLUGIN_TAG, level=Qgis.Warning)
                            
                                style_key_ohs = "OLS OHS"; layer_name_ohs = f"{self.tr('OLS')} OHS {icao_code}"; internal_name_ohs = f"OLS_OHS_{icao_code}"
                                if style_key_ohs not in self.style_map: self.style_map[style_key_ohs] = "ols_ohs.qml"
                                layer = self._create_and_add_layer("Polygon", internal_name_ohs, layer_name_ohs, fields, [feature], ols_layer_group, style_key_ohs)
                                if layer: overall_success = True; QgsMessageLog.logMessage("OHS Layer Created.", PLUGIN_TAG, level=Qgis.Info)
                                else: QgsMessageLog.logMessage("Failed to create OHS Layer.", PLUGIN_TAG, level=Qgis.Warning)
                          else: QgsMessageLog.logMessage("Failed create valid OHS full circle geom (makeValid failed).", PLUGIN_TAG, level=Qgis.Warning)
                      else: QgsMessageLog.logMessage("Failed create OHS full circle geom (buffer failed).", PLUGIN_TAG, level=Qgis.Warning)
                else: QgsMessageLog.logMessage("Skipping OHS generation: ARP center point or radius invalid.", PLUGIN_TAG, level=Qgis.Warning)
            except Exception as e_ohs: QgsMessageLog.logMessage(f"Error generating OHS: {e_ohs}", PLUGIN_TAG, level=Qgis.Critical)
        else: QgsMessageLog.logMessage("Outer Horizontal Surface not required for this airport configuration.", PLUGIN_TAG, level=Qgis.Info)

        # --- 7. Generate Transitional Surfaces ---
        transitional_features = []
        # Check prerequisites first
        if ihs_base_geom and not ihs_base_geom.isEmpty() and IHS_ELEVATION_AMSL is not None:
          try: # Try the whole transitional process
            target_crs = QgsProject.instance().crs()
            if target_crs and target_crs.isValid():
              # Ensure self.target_crs is set if used by helpers (if needed)
              # self.target_crs = target_crs
              transitional_features = self._generate_transitional_features(
                processed_runway_data_list,
                IHS_ELEVATION_AMSL,
                target_crs # Pass CRS needed for distance calcs
              )
              
              # Add Layer (still inside the try, but after feature generation)
              if transitional_features:
                transitional_fields = self._get_ols_fields("Transitional")
                trans_layer = self._create_and_add_layer(
                  "Polygon", f"OLS_Transitional_{icao_code}", f"{self.tr('OLS')} Transitional {icao_code}",
                  transitional_fields, transitional_features, ols_layer_group, "OLS Transitional"
                )
                if trans_layer:
                  overall_success = True # Mark success if layer created
                  QgsMessageLog.logMessage(f"Transitional Layer created with {len(transitional_features)} features.", PLUGIN_TAG, level=Qgis.Info)
                else:
                  # Error logged within _create_and_add_layer helper
                  QgsMessageLog.logMessage("Failed to add Transitional Layer to map.", PLUGIN_TAG, level=Qgis.Warning)
              # else: No features generated, nothing to add. Logged within _generate_transitional_features
                  
            else: # CRS is invalid
              QgsMessageLog.logMessage("Skipping Transitional: Invalid Project CRS.", PLUGIN_TAG, level=Qgis.Warning)
          
          except Exception as e_trans: # Catch ANY exception during the transitional process
            QgsMessageLog.logMessage(f"Error during Transitional Surface generation/layer addition: {e_trans}", PLUGIN_TAG, level=Qgis.Critical)
            # Consider if you want to halt further OLS generation if transitional fails critically
          
        else: # IHS prerequisites failed
          QgsMessageLog.logMessage("Skipping Transitional Surface generation: IHS geometry or elevation not available/valid.", PLUGIN_TAG, level=Qgis.Info)
          
        QgsMessageLog.logMessage(f"Finished Airport-Wide OLS Generation. Overall Success: {overall_success}", PLUGIN_TAG, level=Qgis.Info)
        return overall_success
    
    # --- NEW Geometry Helper Methods ---
  
    def _get_polygon_edges(self, polygon_geom: QgsGeometry) -> List[Optional[QgsLineString]]:
      """Extracts exterior ring segments from a single polygon geometry."""
      if not polygon_geom or polygon_geom.isNull() or not polygon_geom.isGeosValid():
        return []
      if not polygon_geom.wkbType() in [Qgis.WkbType.Polygon, Qgis.WkbType.PolygonZ]:
        QgsMessageLog.logMessage(f"DEBUG: _get_polygon_edges received non-polygon type: {polygon_geom.wkbType()}", PLUGIN_TAG, level=Qgis.Warning)
        # Handle multipart potentially? For now, assume simple polygon input after makeValid
        return []
      
      try:
        poly = polygon_geom.constGet() # Get QgsPolygon base object
        if not poly: return []
        exterior = poly.exteriorRing()
        if not exterior or exterior.isEmpty() or not exterior.isGeosValid() or not exterior.isClosed():
          return []
        
        edges = []
        points = list(exterior.vertices())
        if len(points) < 4: return [] # Need at least 3 unique points + closing point for a triangle
        
        for i in range(len(points) - 1):
          p1 = points[i]
          p2 = points[i+1]
          epsilon = 1e-6
          if abs(p1.x() - p2.x()) > epsilon or abs(p1.y() - p2.y()) > epsilon:
            try:
              line = QgsLineString([QgsPointXY(p1.x(), p1.y()), QgsPointXY(p2.x(), p2.y())])
              if line and not line.isEmpty():
                edges.append(line)
              else: edges.append(None)
            except Exception as e_line:
              QgsMessageLog.logMessage(f"Error creating edge line: {e_line}", PLUGIN_TAG, level=Qgis.Warning)
              edges.append(None)
          else: edges.append(None) # Skip zero-length segments (based on XY)
        return edges
      except Exception as e:
        QgsMessageLog.logMessage(f"Error in _get_polygon_edges: {e}", PLUGIN_TAG, level=Qgis.Critical)
        return []
      
    def _get_elevation_at_point_along_gradient(self,
                          point_xy: QgsPointXY, # Input is QgsPointXY
                          line_start_pt: QgsPointXY, line_end_pt: QgsPointXY,
                          line_start_elev: float, line_end_elev: float,
                          target_crs: QgsCoordinateReferenceSystem) -> Optional[float]:
        """Calculates elevation by projecting point onto line defined by start/end points/elevs."""
        if None in [point_xy, line_start_pt, line_end_pt, line_start_elev, line_end_elev, target_crs]:
          return None
      
        epsilon = 1e-6
        if abs(line_start_pt.x() - line_end_pt.x()) < epsilon and abs(line_start_pt.y() - line_end_pt.y()) < epsilon:
          return line_start_elev
      
        try:
          dist_area = QgsDistanceArea()
          dist_area.setSourceCrs(target_crs, QgsProject.instance().transformContext())
          dist_area.setEllipsoid(QgsProject.instance().ellipsoid())
          
          line_geom = QgsGeometry.fromPolylineXY([line_start_pt, line_end_pt])
          if line_geom.isNull(): return None
          
          line_length = dist_area.measureLine(line_start_pt, line_end_pt)
          if line_length < epsilon: return line_start_elev
          
          line_primitive = line_geom.constGet()
          if not line_primitive:
            QgsMessageLog.logMessage("DEBUG: Failed to get line primitive.", PLUGIN_TAG, level=Qgis.Warning)
            return None
          
          # QgsMessageLog.logMessage(f"DEBUG: Calling closestSegment on primitive type {type(line_primitive)}", PLUGIN_TAG, level=Qgis.Info)
          
          # --- FIX: Convert input point_xy to QgsPoint for closestSegment ---
          point_qgsp = QgsPoint(point_xy) # Create QgsPoint from QgsPointXY (Z will be 0 or NaN)
          # --- END FIX ---
          
          try:
            # Pass the QgsPoint version
            sqrd_dist, closest_pt_on_line_qgspoint, _, next_vertex_index = line_primitive.closestSegment(point_qgsp) # Pass QgsPoint
            
            closest_pt_on_line_geom = QgsGeometry(closest_pt_on_line_qgspoint)
            # QgsMessageLog.logMessage(f"DEBUG: closestSegment unpacked 4 values. Closest Pt Geom: {closest_pt_on_line_geom.asWkt(3)}", PLUGIN_TAG, level=Qgis.Info)
            
          except ValueError as e_unpack:
            result_tuple = line_primitive.closestSegment(point_xy)
            QgsMessageLog.logMessage(f"CRITICAL DEBUG: Unpacking closestSegment failed! Error: {e_unpack}. Raw value: {result_tuple!r}", PLUGIN_TAG, level=Qgis.Critical)
            raise e_unpack
            
          # Now isNull() and asPoint() should work on the QgsGeometry object
          if closest_pt_on_line_geom.isNull():
            QgsMessageLog.logMessage("DEBUG: closest_pt_on_line_geom is Null.", PLUGIN_TAG, level=Qgis.Warning)
            return None
          
          projected_point = closest_pt_on_line_geom.asPoint() # Extracts QgsPointXY from geometry
          if projected_point is None:
            QgsMessageLog.logMessage("DEBUG: projected_point is None after asPoint().", PLUGIN_TAG, level=Qgis.Warning)
            return None
          
          dist_along = dist_area.measureLine(line_start_pt, projected_point)
          dist_along = max(0.0, min(dist_along, line_length))
          
          if line_length < epsilon:
            fraction_along = 0.0
          else:
            fraction_along = dist_along / line_length
            
          elevation_diff = line_end_elev - line_start_elev
          interpolated_elev = line_start_elev + (fraction_along * elevation_diff)
          
          return interpolated_elev
      
        except TypeError as e_type:
            # Catch the specific type error if it happens again
            QgsMessageLog.logMessage(f"TypeError in _get_elevation_at_point_along_gradient: {e_type}", PLUGIN_TAG, level=Qgis.Critical)
            return None
        except Exception as e:
            QgsMessageLog.logMessage(f"Error in _get_elevation_at_point_along_gradient: {e}", PLUGIN_TAG, level=Qgis.Warning)
            return None

    def _clip_3d_segment_to_elevation(self, p1: QgsPoint, p2: QgsPoint, clip_elevation: float) -> Optional[Tuple[QgsPoint, QgsPoint]]:
      """
      Clips a 3D line segment (defined by QgsPoint with Z) against a horizontal plane.
      Returns the portion of the segment below or at the clip_elevation.
      Assumes p1 and p2 have valid Z values.
      Returns None if the entire segment is above the clip elevation.
      """
      if not all([p1, p2]): return None
      z1, z2 = p1.z(), p2.z()
      if z1 is None or z2 is None: return None # Need Z values
      
      # --- FIX: Replace compare for QgsPoint ---
      epsilon = 1e-6
      # Check if points are effectively the same
      if abs(p1.x() - p2.x()) < epsilon and abs(p1.y() - p2.y()) < epsilon and abs(z1 - z2) < epsilon:
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
        p1, p2 = p2, p1 # Swap points
        z1, z2 = p2.z(), p1.z() # Swap elevations
        
      # Calculate interpolation factor (t) where elevation equals clip_elevation
      delta_z = z2 - z1
      if abs(delta_z) < epsilon: # Points are effectively at same Z but one passed check? Should be caught by Case 1/2. Return original below point(s).
        # Should only happen if z1 is approximately clip_elevation
        return p1, p1 # Segment is horizontal at clip_elevation
  
      t = (clip_elevation - z1) / delta_z
      # Clamp t just in case of floating point issues near 0 or 1
      t = max(0.0, min(t, 1.0))
  
      # Calculate intersection point coordinates
      x_intersect = p1.x() + t * (p2.x() - p1.x())
      y_intersect = p1.y() + t * (p2.y() - p1.y())
      z_intersect = clip_elevation # By definition
  
      p_intersect = QgsPoint(x_intersect, y_intersect, z_intersect)
  
      # Return the segment from the original lower point (p1) to the intersection point
      return p1, p_intersect
      
    def _generate_transitional_features(self,
                      processed_runway_data_list: List[dict],
                      IHS_ELEVATION_AMSL: float,
                      target_crs: QgsCoordinateReferenceSystem) -> List[QgsFeature]:
      """
      Generates polygon features for the main Transitional OLS.
      Connects runway strip edges and approach surface edges (below IHS)
      up to the Inner Horizontal Surface elevation.
      """
      QgsMessageLog.logMessage("Starting Transitional Surface generation...", PLUGIN_TAG, level=Qgis.Info)
      transitional_features: List[QgsFeature] = []
      transitional_fields = self._get_ols_fields("Transitional") # Includes 'Side' field
      
      if IHS_ELEVATION_AMSL is None:
        QgsMessageLog.logMessage("Skipping Transitional: IHS Elevation is missing.", PLUGIN_TAG, level=Qgis.Warning)
        return []
      
      # Temporary storage for approach edges to avoid recalculating
      # Key: (runway_name, end_desig, section_idx, side) Value: QgsLineString
      approach_edges_cache = {}
      
      # --- Pass 1: Generate Approach Section Edge Geometries (Needed for lookup) ---
      # This is slightly inefficient but avoids complex data passing from process_guideline_f
      QgsMessageLog.logMessage("Transitional: Pre-calculating Approach edge geometries...", PLUGIN_TAG, level=Qgis.Info)
      for runway_data in processed_runway_data_list:
        runway_name = runway_data.get('short_name')
        thr_point = runway_data.get('thr_point'); rec_thr_point = runway_data.get('rec_thr_point')
        arc_num_str = runway_data.get('arc_num')
        type1_str = runway_data.get('type1'); type2_str = runway_data.get('type2')
        
        if not all([runway_name, thr_point, rec_thr_point, arc_num_str]): continue
        try: arc_num = int(arc_num_str)
        except ValueError: continue
        
        rwy_params = self._get_runway_parameters(thr_point, rec_thr_point)
        if not rwy_params: continue
        primary_desig, reciprocal_desig = runway_name.split('/') if '/' in runway_name else ("THR1", "THR2")
        
        for end_idx, (end_desig, end_type, end_thr_pt, outward_az) in enumerate([
          (primary_desig, type1_str, thr_point, rwy_params['azimuth_r_p']),
          (reciprocal_desig, type2_str, rec_thr_point, rwy_params['azimuth_p_r'])
        ]):
          approach_sections_params = ols_dimensions.get_ols_params(arc_num, end_type, 'APPROACH')
          if not approach_sections_params: continue
        
          current_section_start_pt = None
          current_section_start_width = 0.0
        
          for i, section_params in enumerate(approach_sections_params):
            length = section_params.get('length', 0.0)
            divergence = section_params.get('divergence', 0.0)
            if length <= 0: continue
            
            if i == 0:
              start_dist = section_params.get('start_dist_from_thr', 0.0)
              start_width = section_params.get('start_width', 0.0)
              if start_width <= 0: break # Error in params
              current_section_start_pt = end_thr_pt.project(start_dist, outward_az)
              current_section_start_width = start_width
            else:
              if current_section_start_pt is None: break # Previous failed
              
            if not current_section_start_pt: break # Projection failed
            
            start_hw = current_section_start_width / 2.0
            end_width = current_section_start_width + (2 * length * divergence)
            end_hw = end_width / 2.0
            end_pt = current_section_start_pt.project(length, outward_az)
            if not end_pt: break # Projection failed
            
            # Calculate corners for this section
            az_perp_l = (outward_az + 270.0) % 360.0
            az_perp_r = (outward_az + 90.0) % 360.0
            p_start_l = current_section_start_pt.project(start_hw, az_perp_l)
            p_start_r = current_section_start_pt.project(start_hw, az_perp_r)
            p_end_l = end_pt.project(end_hw, az_perp_l)
            p_end_r = end_pt.project(end_hw, az_perp_r)
            
            if all([p_start_l, p_end_l, p_start_r, p_end_r]):
              # Store edge LineStrings
              edge_l = QgsLineString([p_start_l, p_end_l])
              edge_r = QgsLineString([p_start_r, p_end_r])
              approach_edges_cache[(runway_name, end_desig, i, 'L')] = edge_l
              approach_edges_cache[(runway_name, end_desig, i, 'R')] = edge_r
            else:
              QgsMessageLog.logMessage(f"Failed calc approach section corners for {runway_name} {end_desig} Sec {i+1}", PLUGIN_TAG, level=Qgis.Warning)
              
              
            # Update for next section
            current_section_start_pt = end_pt
            current_section_start_width = end_width
      QgsMessageLog.logMessage("Transitional: Finished pre-calculating Approach edges.", PLUGIN_TAG, level=Qgis.Info)
      
      
      # --- Pass 2: Generate Transitional Features ---
      QgsMessageLog.logMessage("Transitional: Generating features...", PLUGIN_TAG, level=Qgis.Info)
      for runway_data in processed_runway_data_list:
        # --- Get Runway Data ---
        runway_name = runway_data.get('short_name')
        thr_point = runway_data.get('thr_point'); rec_thr_point = runway_data.get('rec_thr_point')
        thr_elev = runway_data.get('thr_elev_1'); rec_thr_elev = runway_data.get('thr_elev_2')
        arc_num_str = runway_data.get('arc_num')
        type1_str = runway_data.get('type1'); type2_str = runway_data.get('type2')
        calculated_strip_dims = runway_data.get('calculated_strip_dims') # Needed for strip geometry
        
        if not all([runway_name, thr_point, rec_thr_point, arc_num_str, calculated_strip_dims,
              thr_elev is not None, rec_thr_elev is not None]):
          QgsMessageLog.logMessage(f"Skipping Transitional for {runway_name}: Missing required data (points, elevs, ARC, strip dims).", PLUGIN_TAG, level=Qgis.Warning)
          continue
      
        try: arc_num = int(arc_num_str)
        except ValueError:
          QgsMessageLog.logMessage(f"Skipping Transitional for {runway_name}: Invalid ARC number.", PLUGIN_TAG, level=Qgis.Warning)
          continue
      
        rwy_params = self._get_runway_parameters(thr_point, rec_thr_point)
        if not rwy_params or rwy_params['length'] < 1e-6:
          QgsMessageLog.logMessage(f"Skipping Transitional for {runway_name}: Invalid runway parameters.", PLUGIN_TAG, level=Qgis.Warning)
          continue
      
        primary_desig, reciprocal_desig = runway_name.split('/') if '/' in runway_name else ("THR1", "THR2")
      
        # --- Get Transitional Slope ---
        type_abbr_1 = ols_dimensions.get_runway_type_abbr(type1_str)
        type_abbr_2 = ols_dimensions.get_runway_type_abbr(type2_str)
        # Use most restrictive type for slope lookup (assuming higher index = more restrictive)
        type_order = ["", "NI", "NPA", "PA_I", "PA_II_III"]
        idx1 = type_order.index(type_abbr_1) if type_abbr_1 in type_order else 1
        idx2 = type_order.index(type_abbr_2) if type_abbr_2 in type_order else 1
        governing_type_abbr = type_order[max(idx1, idx2)]
      
        trans_params = ols_dimensions.get_ols_params(arc_num, governing_type_abbr, 'Transitional')
        if not trans_params or 'slope' not in trans_params or trans_params['slope'] <= 1e-9:
          QgsMessageLog.logMessage(f"Skipping Transitional for {runway_name}: No valid slope found for classification.", PLUGIN_TAG, level=Qgis.Warning)
          continue
        transitional_slope = trans_params['slope']
        transitional_ref = trans_params.get('ref', "MOS 139 8.2.17 (Verify)")
      
        # --- Recalculate Overall Strip Geometry ---
        # (Assumes _calculate_strip_dimensions stored overall_width and extension_length in calculated_strip_dims)
        strip_overall_width = calculated_strip_dims.get('overall_width')
        strip_extension = calculated_strip_dims.get('extension_length')
        if strip_overall_width is None or strip_extension is None:
          QgsMessageLog.logMessage(f"Skipping Transitional for {runway_name}: Missing calculated strip dims.", PLUGIN_TAG, level=Qgis.Warning)
          continue
      
        strip_overall_half_width = strip_overall_width / 2.0
        strip_end_p = thr_point.project(strip_extension, rwy_params['azimuth_r_p'])
        strip_end_r = rec_thr_point.project(strip_extension, rwy_params['azimuth_p_r'])
        if not strip_end_p or not strip_end_r:
          QgsMessageLog.logMessage(f"Skipping Transitional for {runway_name}: Failed to calc strip end points.", PLUGIN_TAG, level=Qgis.Warning)
          continue
      
        # Get strip corners
        strip_corner_p_l = strip_end_p.project(strip_overall_half_width, rwy_params['azimuth_perp_l'])
        strip_corner_p_r = strip_end_p.project(strip_overall_half_width, rwy_params['azimuth_perp_r'])
        strip_corner_r_l = strip_end_r.project(strip_overall_half_width, rwy_params['azimuth_perp_l'])
        strip_corner_r_r = strip_end_r.project(strip_overall_half_width, rwy_params['azimuth_perp_r'])
      
        if not all([strip_corner_p_l, strip_corner_p_r, strip_corner_r_l, strip_corner_r_r]):
          QgsMessageLog.logMessage(f"Skipping Transitional for {runway_name}: Failed to calc strip corners.", PLUGIN_TAG, level=Qgis.Warning)
          continue
      
        # Define strip edges (QgsLineString)
        strip_edge_l = QgsLineString([strip_corner_p_l, strip_corner_r_l]) # Left edge (looking from P to R)
        strip_edge_r = QgsLineString([strip_corner_p_r, strip_corner_r_r]) # Right edge
      
        # --- Generate Strip Transitional Sides ---
        for side_label, strip_edge, outward_azimuth in [('L', strip_edge_l, rwy_params['azimuth_perp_l']),
                                ('R', strip_edge_r, rwy_params['azimuth_perp_r'])]:
          if not strip_edge or strip_edge.isEmpty(): continue

          # p_start/p_end are QgsPoint from the linestring
          p_start_qgsp = strip_edge.startPoint()
          p_end_qgsp = strip_edge.endPoint()

          # --- FIX: Create QgsPointXY versions for calculations/polygon ---
          p_start_xy = QgsPointXY(p_start_qgsp.x(), p_start_qgsp.y())
          p_end_xy = QgsPointXY(p_end_qgsp.x(), p_end_qgsp.y())
          # --- END FIX ---

          # Calculate Z at start/end based on centerline gradient using XY points
          z_start = self._get_elevation_at_point_along_gradient(p_start_xy, thr_point, rec_thr_point, thr_elev, rec_thr_elev, target_crs) # Pass XY
          z_end = self._get_elevation_at_point_along_gradient(p_end_xy, thr_point, rec_thr_point, thr_elev, rec_thr_elev, target_crs)     # Pass XY

          if z_start is None or z_end is None:
            QgsMessageLog.logMessage(f"Failed calc Z for strip edge {side_label} on {runway_name}", PLUGIN_TAG, level=Qgis.Warning)
            continue

          # If entire edge is above IHS, skip (Using IHS_ELEVATION_AMSL from outer scope)
          if z_start >= IHS_ELEVATION_AMSL and z_end >= IHS_ELEVATION_AMSL:
            continue

          # Calculate horizontal distances
          h_dist_start = max(0.0, (IHS_ELEVATION_AMSL - z_start) / transitional_slope)
          h_dist_end = max(0.0, (IHS_ELEVATION_AMSL - z_end) / transitional_slope)

          # Project upper points using XY points
          p_upper_start = p_start_xy.project(h_dist_start, outward_azimuth) # Returns QgsPointXY
          p_upper_end = p_end_xy.project(h_dist_end, outward_azimuth)         # Returns QgsPointXY

          if not p_upper_start or not p_upper_end:
            QgsMessageLog.logMessage(f"Failed projecting upper points for strip edge {side_label} on {runway_name}", PLUGIN_TAG, level=Qgis.Warning)
            continue

          # --- FIX: Ensure corners list uses QgsPointXY ---
          corners = [
            p_start_xy,     # Now QgsPointXY
            p_end_xy,       # Now QgsPointXY
            p_upper_end,    # Already QgsPointXY
            p_upper_start   # Already QgsPointXY
          ]
          # --- END FIX ---

          # Create polygon
          poly_geom = self._create_polygon_from_corners(corners, f"Trans Strip {side_label} {runway_name}")

          if poly_geom:
            feat = QgsFeature(transitional_fields)
            feat.setGeometry(poly_geom)
            # ... (set attributes) ...
            attr_map = {
              "RWY_Name": runway_name, "Surface": "Transitional", "End_Desig": "N/A", # Or runway_name
              "Section_Desc": "Strip Side", "Side": side_label,
              "Slope_Perc": transitional_slope * 100.0, "Ref": transitional_ref
            }
            for name, value in attr_map.items():
              idx = transitional_fields.indexFromName(name)
              if idx != -1: feat.setAttribute(idx, value)
            transitional_features.append(feat)
            
            
        # --- Generate Approach Transitional Sides ---
        for end_idx, (end_desig, end_type, end_thr_pt, end_thr_elev, outward_az) in enumerate([
          (primary_desig, type1_str, thr_point, thr_elev, rwy_params['azimuth_r_p']),
          (reciprocal_desig, type2_str, rec_thr_point, rec_thr_elev, rwy_params['azimuth_p_r'])
        ]):
          approach_sections_params = ols_dimensions.get_ols_params(arc_num, end_type, 'APPROACH')
          if not approach_sections_params: continue
      
          current_section_start_elev = end_thr_elev # Approach elev starts at THR
          current_section_start_pt_ctr = None # Centerline start point for this section
      
          for i, section_params in enumerate(approach_sections_params):
            section_length = section_params.get('length', 0.0)
            section_slope = section_params.get('slope', 0.0)
            if section_length <= 0: continue
            
            # Get section start point (centerline)
            if i == 0:
              start_dist = section_params.get('start_dist_from_thr', 0.0)
              current_section_start_pt_ctr = end_thr_pt.project(start_dist, outward_az)
            else:
              if current_section_start_pt_ctr:
                current_section_start_pt_ctr = current_section_start_pt_ctr.project(prev_section_length, outward_az) # Project from previous end
              else: break # Cannot continue if previous failed
              
            if not current_section_start_pt_ctr: break # Projection failed
            
            section_end_elev = (current_section_start_elev + section_length * section_slope) if current_section_start_elev is not None else None
            if section_end_elev is None: continue # Cannot proceed without elevation
            
            for side_label, outward_perp_azimuth in [('L', (outward_az + 270.0) % 360.0),
                                ('R', (outward_az + 90.0) % 360.0)]:
            
              approach_edge = approach_edges_cache.get((runway_name, end_desig, i, side_label))
              if not approach_edge or approach_edge.isEmpty(): continue
            
              pa_start = approach_edge.startPoint()
              pa_end = approach_edge.endPoint()
            
              # Calculate Z at approach edge start/end points for this section
              # Note: Assuming edge points are at same Z as centerline at that point along approach
              # This is an approximation, true Z might vary slightly with divergence
              za_start = current_section_start_elev
              za_end = section_end_elev
            
              # Create QgsPoint with Z for clipping check
              p1_3d = QgsPoint(pa_start.x(), pa_start.y(), za_start)
              p2_3d = QgsPoint(pa_end.x(), pa_end.y(), za_end)
            
              # Clip the 3D segment against IHS elevation
              clipped_segment = self._clip_3d_segment_to_elevation(p1_3d, p2_3d, IHS_ELEVATION_AMSL)
            
              if clipped_segment:
                pa_start_clipped, pa_end_clipped = clipped_segment
                za_start_clipped, za_end_clipped = pa_start_clipped.z(), pa_end_clipped.z()
                
                # Calculate horizontal distances
                h_dist_app_start = max(0.0, (IHS_ELEVATION_AMSL - za_start_clipped) / transitional_slope)
                h_dist_app_end = max(0.0, (IHS_ELEVATION_AMSL - za_end_clipped) / transitional_slope)
                
                # Project upper points (use XY from clipped points)
                pa_upper_start = QgsPointXY(pa_start_clipped.x(), pa_start_clipped.y()).project(h_dist_app_start, outward_perp_azimuth)
                pa_upper_end = QgsPointXY(pa_end_clipped.x(), pa_end_clipped.y()).project(h_dist_app_end, outward_perp_azimuth)
                
                if pa_upper_start and pa_upper_end:
                  corners = [QgsPointXY(pa_start_clipped.x(), pa_start_clipped.y()),
                        QgsPointXY(pa_end_clipped.x(), pa_end_clipped.y()),
                        pa_upper_end, pa_upper_start]
                  poly_geom = self._create_polygon_from_corners(corners, f"Trans App {end_desig} Sec{i+1} {side_label}")
                  
                  if poly_geom:
                    feat = QgsFeature(transitional_fields)
                    feat.setGeometry(poly_geom)
                    attr_map = {
                      "RWY_Name": runway_name, "Surface": "Transitional", "End_Desig": end_desig,
                      "Section_Desc": f"Approach Sec {i+1}", "Side": side_label,
                      "Slope_Perc": transitional_slope * 100.0, "Ref": transitional_ref
                    }
                    for name, value in attr_map.items():
                      idx = transitional_fields.indexFromName(name)
                      if idx != -1: feat.setAttribute(idx, value)
                    transitional_features.append(feat)
              # else: Segment was entirely above IHS
                    
            # Update elevation and store length for next section's start point calculation
            current_section_start_elev = section_end_elev
            prev_section_length = section_length # Store for next iteration's start point calc
            
      QgsMessageLog.logMessage(f"Finished Transitional Surface generation. Created {len(transitional_features)} features.", PLUGIN_TAG, level=Qgis.Info)
      return transitional_features
    
    # --- Guideline Processing Functions (Using Helper) ---
    def process_met_station_surfaces(self, met_point_proj_crs: QgsPointXY, icao_code: str, target_crs: QgsCoordinateReferenceSystem, layer_group: QgsLayerTreeGroup) -> Tuple[bool, List[QgsVectorLayer]]:
        """Generates MET station layers (Point, Enclosure, Buffers). Uses helper."""
        # Note: Return value changed slightly, second element not directly used now
        any_layer_ok = False; enclosure_geom: Optional[QgsGeometry] = None
        met_geom_target_crs = QgsGeometry.fromPointXY(met_point_proj_crs);
        if met_geom_target_crs.isNull(): return False, []

        # Layer 1: Point
        try:
            fields = QgsFields([QgsField("Name", QVariant.String), QgsField("Easting", QVariant.Double), QgsField("Northing", QVariant.Double)])
            feat = QgsFeature(fields); feat.setGeometry(met_geom_target_crs); feat.setAttributes([self.tr("MET Station Location"), met_point_proj_crs.x(), met_point_proj_crs.y()])
            if self._create_and_add_layer("Point", f"met_loc_{icao_code}", self.tr("MET Station Location"), fields, [feat], layer_group, "MET Station Location"): any_layer_ok = True
        except Exception as e: QgsMessageLog.logMessage(f"Error MET Point: {e}", PLUGIN_TAG, level=Qgis.Critical)

        # Layer 2: Enclosure
        try:
            side = 16.0; name = self.tr("MET Instrument Enclosure");
            geom = self._create_centered_oriented_square(met_point_proj_crs, side, name)
            if geom: enclosure_geom = geom; fields=QgsFields([QgsField("Type", QVariant.String), QgsField("Side_m", QVariant.Double)]); feat = QgsFeature(fields); feat.setGeometry(geom); feat.setAttributes(["Enclosure", side])
            if self._create_and_add_layer("Polygon", f"met_enc_{icao_code}", name, fields, [feat], layer_group, "MET Instrument Enclosure"): any_layer_ok = True
        except Exception as e: QgsMessageLog.logMessage(f"Error MET Enclosure: {e}", PLUGIN_TAG, level=Qgis.Critical)

        # Layer 3: Buffer Zone
        try:
            side = 30.0; name = self.tr("MET Buffer Zone");
            geom = self._create_centered_oriented_square(met_point_proj_crs, side, name)
            if geom: fields=QgsFields([QgsField("Type", QVariant.String), QgsField("Side_m", QVariant.Double)]); feat = QgsFeature(fields); feat.setGeometry(geom); feat.setAttributes(["30m Buffer", side])
            if self._create_and_add_layer("Polygon", f"met_buf_{icao_code}", name, fields, [feat], layer_group, "MET Buffer Zone"): any_layer_ok = True
        except Exception as e: QgsMessageLog.logMessage(f"Error MET Buffer: {e}", PLUGIN_TAG, level=Qgis.Critical)

        # Layer 4: Obstruction Buffer
        if enclosure_geom:
             try:
                dist = 80.0; name = self.tr("MET Obstacle Buffer Zone");
                buffered_geom = enclosure_geom.buffer(dist, 12); buffered_geom = buffered_geom.makeValid() if buffered_geom and not buffered_geom.isGeosValid() else buffered_geom
                if buffered_geom and not buffered_geom.isEmpty(): fields=QgsFields([QgsField("Type", QVariant.String), QgsField("Buffer_m", QVariant.Double)]); feat = QgsFeature(fields); feat.setGeometry(buffered_geom); feat.setAttributes(["Obstruction Buffer", dist])
                if self._create_and_add_layer("Polygon", f"met_obs_{icao_code}", name, fields, [feat], layer_group, "MET Obstacle Buffer Zone"): any_layer_ok = True
             except Exception as e: QgsMessageLog.logMessage(f"Error MET Obstruction Buffer: {e}", PLUGIN_TAG, level=Qgis.Critical)

        # Return overall success status, generated layers are in self.successfully_generated_layers
        return any_layer_ok, [] # Return empty list as layers added internally

    def process_guideline_a(self, runway_data: dict, layer_group: QgsLayerTreeGroup) -> bool:
        """Placeholder for Guideline A: Aircraft Noise processing."""
        QgsMessageLog.logMessage("Guideline A processing not implemented.", PLUGIN_TAG, level=Qgis.Info)
        return False

    def process_guideline_b(self, runway_data: dict, layer_group: QgsLayerTreeGroup) -> bool:
        """Processes Guideline B: Windshear Assessment Zone."""
        runway_name = runway_data.get('short_name', f"RWY_{runway_data.get('original_index','?')}")
        thr_point = runway_data.get('thr_point'); rec_thr_point = runway_data.get('rec_thr_point')
        if not all([thr_point, rec_thr_point, layer_group]): return False
        params = self._get_runway_parameters(thr_point, rec_thr_point)
        if params is None: return False

        fields = QgsFields([QgsField("RWY_Name", QVariant.String), QgsField("Zone_Type", QVariant.String), QgsField("End_Desig", QVariant.String)])
        features_to_add = []
        primary_desig, reciprocal_desig = runway_name.split('/') if '/' in runway_name else ("Primary", "Reciprocal")
        try:
            geom_p = self._create_offset_rectangle(thr_point, params['azimuth_p_r'], GUIDELINE_B_FAR_EDGE_OFFSET, GUIDELINE_B_ZONE_LENGTH_BACKWARD, GUIDELINE_B_ZONE_HALF_WIDTH, f"WSZ {primary_desig}")
            if geom_p: feat = QgsFeature(fields); feat.setGeometry(geom_p); feat.setAttributes([runway_name, "Windshear", primary_desig]); features_to_add.append(feat)
        except Exception as e: QgsMessageLog.logMessage(f"Error WSZ Primary {runway_name}: {e}", PLUGIN_TAG, level=Qgis.Warning)
        try:
            geom_r = self._create_offset_rectangle(rec_thr_point, params['azimuth_r_p'], GUIDELINE_B_FAR_EDGE_OFFSET, GUIDELINE_B_ZONE_LENGTH_BACKWARD, GUIDELINE_B_ZONE_HALF_WIDTH, f"WSZ {reciprocal_desig}")
            if geom_r: feat = QgsFeature(fields); feat.setGeometry(geom_r); feat.setAttributes([runway_name, "Windshear", reciprocal_desig]); features_to_add.append(feat)
        except Exception as e: QgsMessageLog.logMessage(f"Error WSZ Reciprocal {runway_name}: {e}", PLUGIN_TAG, level=Qgis.Warning)

        layer_created = self._create_and_add_layer("Polygon", f"WSZ_{runway_name.replace('/', '_')}", f"WSZ {self.tr('Runway')} {runway_name}", fields, features_to_add, layer_group, "WSZ Runway")
        return layer_created is not None

    def process_guideline_c(self, arp_point: QgsPointXY, icao_code: str, target_crs: QgsCoordinateReferenceSystem, layer_group: QgsLayerTreeGroup) -> bool:
        """Processes Guideline C: Wildlife Management Zone."""
        if not all([arp_point, icao_code, target_crs, target_crs.isValid(), layer_group]): return False
        overall_success = False;
        try:
            arp_geom = QgsGeometry.fromPointXY(arp_point);
            if arp_geom.isNull(): return False

            def create_wzm_layer(zone: str, geom: Optional[QgsGeometry], desc: str, r_in: float, r_out: float) -> bool:
                if not geom: return False
                display_name = f"{self.tr('WMZ')} {zone} ({r_in:.0f}-{r_out:.0f}km)"; internal_name = f"WMZ_{zone}_{icao_code}"
                fields = QgsFields([QgsField("Zone", QVariant.String), QgsField("Desc", QVariant.String), QgsField("InnerKm", QVariant.Double), QgsField("OuterKm", QVariant.Double)])
                feature = QgsFeature(fields); feature.setGeometry(geom); feature.setAttributes([f"Area {zone}", desc, r_in, r_out])
                layer = self._create_and_add_layer("Polygon", internal_name, display_name, fields, [feature], layer_group, f"WMZ {zone}")
                return layer is not None

            geom_a = arp_geom.buffer(GUIDELINE_C_RADIUS_A_M, GUIDELINE_C_BUFFER_SEGMENTS); geom_a = geom_a.makeValid() if geom_a and not geom_a.isGeosValid() else geom_a
            geom_b_full = arp_geom.buffer(GUIDELINE_C_RADIUS_B_M, GUIDELINE_C_BUFFER_SEGMENTS); geom_b_full = geom_b_full.makeValid() if geom_b_full and not geom_b_full.isGeosValid() else geom_b_full
            geom_c_full = arp_geom.buffer(GUIDELINE_C_RADIUS_C_M, GUIDELINE_C_BUFFER_SEGMENTS); geom_c_full = geom_c_full.makeValid() if geom_c_full and not geom_c_full.isGeosValid() else geom_c_full
            geom_b = None; geom_c = None
            if geom_b_full: geom_b = geom_b_full.difference(geom_a) if geom_a else geom_b_full; geom_b = geom_b.makeValid() if geom_b and not geom_b.isGeosValid() else geom_b
            if geom_c_full: geom_for_diff = geom_b_full if geom_b_full else geom_a; geom_c = geom_c_full.difference(geom_for_diff) if geom_for_diff else geom_c_full; geom_c = geom_c.makeValid() if geom_c and not geom_c.isGeosValid() else geom_c

            if create_wzm_layer("A", geom_a, self.tr("0-3km Zone"), 0.0, GUIDELINE_C_RADIUS_A_M / 1000.0): overall_success = True
            if create_wzm_layer("B", geom_b, self.tr("3-8km Zone"), GUIDELINE_C_RADIUS_A_M / 1000.0, GUIDELINE_C_RADIUS_B_M / 1000.0): overall_success = True
            if create_wzm_layer("C", geom_c, self.tr("8-13km Zone"), GUIDELINE_C_RADIUS_B_M / 1000.0, GUIDELINE_C_RADIUS_C_M / 1000.0): overall_success = True
            return overall_success
        except Exception as e: QgsMessageLog.logMessage(f"Error Guideline C: {e}", PLUGIN_TAG, level=Qgis.Critical); return False

    def process_guideline_e(self, runway_data: dict, layer_group: QgsLayerTreeGroup) -> bool:
        """Processes Guideline E: Lighting Control Zone."""
        runway_name = runway_data.get('short_name', f"RWY_{runway_data.get('original_index','?')}")
        thr_point = runway_data.get('thr_point'); rec_thr_point = runway_data.get('rec_thr_point')
        if not all([thr_point, rec_thr_point, layer_group]) or thr_point.compare(rec_thr_point, 1e-6): return False
        full_geoms: Dict[str, Optional[QgsGeometry]] = {}; final_geoms: Dict[str, Optional[QgsGeometry]] = {}; overall_success = False
        try:
            def create_lcz_layer(zone: str, geom: Optional[QgsGeometry]) -> bool:
                if not geom: return False
                params = GUIDELINE_E_ZONE_PARAMS[zone]; display_name = f"{self.tr('LCZ')} {zone} {runway_name}"; internal_name = f"LCZ_{zone}_{runway_name.replace('/', '_')}"
                fields=QgsFields([QgsField("RWY", QVariant.String), QgsField("Zone", QVariant.String), QgsField("Desc", QVariant.String), QgsField("Ext_m", QVariant.Double), QgsField("HW_m", QVariant.Double)])
                feature = QgsFeature(fields); feature.setGeometry(geom); feature.setAttributes([runway_name, zone, params['desc'], params['ext'], params['half_w']])
                layer = self._create_and_add_layer("Polygon", internal_name, display_name, fields, [feature], layer_group, f"LCZ {zone}")
                return layer is not None

            for zone_id in GUIDELINE_E_ZONE_ORDER:
                params = GUIDELINE_E_ZONE_PARAMS[zone_id]; geom = self._create_runway_aligned_rectangle(thr_point, rec_thr_point, params['ext'], params['half_w'], f"LCZ Full {zone_id}")
                full_geoms[zone_id] = geom.makeValid() if geom and not geom.isGeosValid() else geom
            geom_prev = full_geoms.get('A'); final_geoms['A'] = geom_prev
            for i, zone_id in enumerate(GUIDELINE_E_ZONE_ORDER[1:]):
                geom_curr = full_geoms.get(zone_id); prev_zone_id = GUIDELINE_E_ZONE_ORDER[i]; geom_prev_valid = full_geoms.get(prev_zone_id)
                if geom_curr and geom_prev_valid: diff = geom_curr.difference(geom_prev_valid); final_geoms[zone_id] = diff.makeValid() if diff and not diff.isGeosValid() else diff
                else: final_geoms[zone_id] = geom_curr
            for zone_id in GUIDELINE_E_ZONE_ORDER:
                if final_geoms.get(zone_id):
                     if create_lcz_layer(zone_id, final_geoms[zone_id]): overall_success = True
            return overall_success
        except Exception as e: QgsMessageLog.logMessage(f"Error Guideline E {runway_name}: {e}", PLUGIN_TAG, level=Qgis.Critical); return False

# ============================================================
# Guideline F: OLS Processing Helpers
# ============================================================
    def _get_conical_contour_fields(self) -> QgsFields:
      """Returns the QgsFields definition for the Conical Contour layer."""
      fields = QgsFields([
        QgsField("Surface", QVariant.String, self.tr("Surface Type"), 30),
        QgsField("Contour_Elev_AMSL", QVariant.Double, self.tr("Contour Elev (AMSL)"), 10, 2),
        QgsField("Contour_Hgt_Abv_IHS", QVariant.Double, self.tr("Height Above IHS (m)"), 10, 2),
        QgsField("Ref", QVariant.String, self.tr("Reference"), 100),
      ])
      return fields
  
    def _get_approach_contour_fields(self) -> QgsFields:
      """Returns the QgsFields definition for the Approach Contour layer."""
      fields = QgsFields([
        QgsField("RWY_Name", QVariant.String, self.tr("Runway"), 50),
        QgsField("End_Desig", QVariant.String, self.tr("End Designator"), 10),
        QgsField("Surface", QVariant.String, self.tr("Surface Type"), 30),
        QgsField("Contour_Elev_AMSL", QVariant.Double, self.tr("Contour Elev (AMSL)"), 10, 2),
        QgsField("Ref", QVariant.String, self.tr("Reference"), 100),
      ])
      return fields
      
    def _get_ols_fields(self, surface_type: str) -> QgsFields:
      """Returns the QgsFields definition for a given OLS surface type."""
      # Base fields common to most OLS layers
      fields_list = [
        QgsField("RWY_Name", QVariant.String, self.tr("Runway"), 50),
        QgsField("Surface", QVariant.String, self.tr("Surface Type"), 50),
        QgsField("End_Desig", QVariant.String, self.tr("End Designator"), 10),
        QgsField("Section_Desc", QVariant.String, self.tr("Section Desc"), 20),
        QgsField("Elevation", QVariant.Double, self.tr("Outer Elev (AMSL)"), 10, 2), # Clarify: Elevation at outer edge of this section
        QgsField("Height_AGL", QVariant.Double, self.tr("Height Gain (m)"), 10, 2), # Clarify: Height gain across this section
        QgsField("Slope_Perc", QVariant.Double, self.tr("Slope (%)"), 6, 3),
        QgsField("Ref", QVariant.String, self.tr("Reference"), 100),
      ]
      # Add specific fields based on type
      if surface_type in ["Approach", "TOCS", "InnerApproach"]:
        fields_list.extend([
          QgsField("Length_m", QVariant.Double, self.tr("Section Length (m)"), 12, 2), # Clarify: Length of this section
          QgsField("InnerW_m", QVariant.Double, self.tr("Section Start W (m)"), 10, 2), # Clarify: Width at start of this section
          QgsField("OuterW_m", QVariant.Double, self.tr("Section End W (m)"), 10, 2),   # Clarify: Width at end of this section
          QgsField("Diverg_Perc", QVariant.Double, self.tr("Divergence (%)"), 6, 3),
          QgsField("Origin_Offset", QVariant.Double, self.tr("Start Dist THR (m)"), 10, 2), # Clarify: Dist from THR to start of this section
        ])
      elif surface_type == "IHS":
        fields_list.extend([
          QgsField("Shape_Desc", QVariant.String, self.tr("Shape Description"), 50)
        ])
      elif surface_type == "Conical":
        fields_list.extend([
          QgsField("Height_Extent", QVariant.Double, self.tr("Height Extent (AGL)"), 10, 2), # Above IHS
        ])
      elif surface_type == "OHS":
        fields_list.extend([
          QgsField("Radius_m", QVariant.Double, self.tr("Radius (m)"), 12, 2),
        ])
      elif surface_type == "Transitional":
        fields_list.extend([
          QgsField("Side", QVariant.String, self.tr("Side (L/R)"), 5),
        ])
        
      # Conditionally remove fields not applicable to the specific surface type
      final_fields = []
      # Define which fields to REMOVE for each type
      remove_map = {
        "IHS": ["End_Desig", "Length_m", "InnerW_m", "OuterW_m", "Diverg_Perc", "Origin_Offset", "Height_Extent", "Radius_m", "Side", "Slope_Perc"],
        "Conical": ["End_Desig", "Length_m", "InnerW_m", "OuterW_m", "Diverg_Perc", "Origin_Offset", "Shape_Desc", "Radius_m", "Side"],
        "OHS": ["End_Desig", "Length_m", "InnerW_m", "OuterW_m", "Diverg_Perc", "Origin_Offset", "Shape_Desc", "Height_Extent", "Side", "Slope_Perc"],
        "Transitional": ["End_Desig", "Length_m", "InnerW_m", "OuterW_m", "Diverg_Perc", "Origin_Offset", "Shape_Desc", "Height_Extent", "Radius_m"],
        "Approach": ["Shape_Desc", "Height_Extent", "Radius_m", "Side"], # Keep App/TOCS specific + base + Section_Desc
        "InnerApproach": ["Shape_Desc", "Height_Extent", "Radius_m", "Side", "Diverg_Perc", "Section_Desc"], # Inner Approach is single section
        "TOCS": ["Shape_Desc", "Height_Extent", "Radius_m", "Side"],     # Keep App/TOCS specific + base
      }
      fields_to_remove = set(remove_map.get(surface_type, []))
      
      for field in fields_list:
          if field.name() not in fields_to_remove:
              # Update labels for clarity
              if field.name() == "Elevation": field.setAlias(self.tr("Section Outer Elev (AMSL)"))
              elif field.name() == "Height_AGL": field.setAlias(self.tr("Section Height Gain (m)"))
              elif field.name() == "Length_m": field.setAlias(self.tr("Section Length (m)"))
              elif field.name() == "InnerW_m": field.setAlias(self.tr("Section Start W (m)"))
              elif field.name() == "OuterW_m": field.setAlias(self.tr("Section End W (m)"))
              elif field.name() == "Origin_Offset": field.setAlias(self.tr("Section Start Dist THR (m)"))
              final_fields.append(field)
            
      return QgsFields(final_fields)
    
    def _generate_approach_surface(self, runway_data: dict, rwy_params: dict, arc_num: int, end_type: str,
                        thr_point: QgsPointXY, outward_azimuth: float, end_desig: str,
                        threshold_elevation: Optional[float]) -> Tuple[List[QgsFeature], List[QgsFeature]]: # <<< Changed return type
      """
      Generates a list of Approach Surface section features (polygons)
      and a list of contour line features.
      Returns a tuple: (list_of_main_polygon_features, list_of_contour_features)
      """
      # --- Define Contour Interval ---
      # APPROACH_CONTOUR_INTERVAL = 10.0 # Defined elsewhere or use self.
  
      # --- Get Section Parameters ---
      sections = ols_dimensions.get_ols_params(arc_num, end_type, 'APPROACH')
      if not sections:
        QgsMessageLog.logMessage(f"No Approach params found for {end_desig} (Code {arc_num}, Type {end_type})", PLUGIN_TAG, level=Qgis.Warning)
        return [], [] # <<< Return empty lists
  
      # --- Initialize Variables ---
      main_polygon_features: List[QgsFeature] = [] # <<< List to hold section features
      contour_line_features: List[QgsFeature] = []
      # calculated_total_length = 0.0 # No longer needed for overall feature
      # final_outer_width = 0.0     # No longer needed for overall feature
      # final_outer_elevation = threshold_elevation # No longer needed for overall feature
  
      if threshold_elevation is None:
        QgsMessageLog.logMessage(f"Warning: Threshold elevation missing for Approach {end_desig}. Contour/Section AMSL values will be None.", PLUGIN_TAG, level=Qgis.Warning)
        
      # --- Loop Through Sections ---
      current_start_point: Optional[QgsPointXY] = None
      current_start_width: float = 0.0
      current_elevation_amsl = threshold_elevation
      current_dist_from_thr = 0.0 # Keep track of cumulative distance for Origin_Offset
  
      for i, section_params in enumerate(sections):
        # --- Get section parameters ---
        section_length = section_params.get('length', 0.0)
        section_slope = section_params.get('slope', 0.0)
        section_divergence = section_params.get('divergence', 0.0) # Per side
        ref = section_params.get('ref', 'MOS 139 T8.2-1 (Check)')
        
        if section_length <= 0: continue # Skip sections with no length
        
        # --- Determine Start Point, Width, and Origin Offset for this section ---
        section_start_dist_thr: Optional[float] = None
        if i == 0: # First section
          start_dist_offset = section_params.get('start_dist_from_thr', 0.0)
          start_width = section_params.get('start_width', 0.0)
          if start_width <= 0:
            QgsMessageLog.logMessage(f"Error: Invalid start_width {start_width} for Approach {end_desig} Section 1.", PLUGIN_TAG, level=Qgis.Critical); return [], []
          current_start_point = thr_point.project(start_dist_offset, outward_azimuth)
          current_start_width = start_width
          current_dist_from_thr = start_dist_offset # Initialize cumulative distance
          section_start_dist_thr = start_dist_offset # Store for attribute
        else: # Subsequent sections start where previous ended
          if current_start_point is None or current_start_width <= 0:
            QgsMessageLog.logMessage(f"Error: Cannot start Approach {end_desig} Section {i+1}, previous section failed.", PLUGIN_TAG, level=Qgis.Critical); return [], []
          # Start point, width, and elevation carry over
          section_start_dist_thr = current_dist_from_thr # Distance to *start* of this section
        
        # --- Calculate End Point and Width for this section ---
        current_start_hw = current_start_width / 2.0
        section_end_width = current_start_width + (2 * section_length * section_divergence)
        end_hw = section_end_width / 2.0
        end_point = current_start_point.project(section_length, outward_azimuth)
        
        if not end_point:
          QgsMessageLog.logMessage(f"Error calculating end point for Approach {end_desig} Section {i+1}.", PLUGIN_TAG, level=Qgis.Warning); continue # Skip this section
          
        # --- Generate Section Geometry ---
        section_geom: Optional[QgsGeometry] = None
        # Determine Section Description
        section_desc = f"Section {i+1}"
        if abs(section_slope) < 1e-9 and i > 0: # If slope is effectively zero and not the first section
              section_desc = "Horizontal"
        
        section_name_log = f"Approach {end_desig} {section_desc}"
        
        if abs(section_divergence) < 1e-9: # Horizontal section or parallel sides
          section_geom = self._create_rectangle_from_start(current_start_point, outward_azimuth, section_length, current_start_hw, section_name_log)
        else: # Diverging section
          section_geom = self._create_trapezoid(current_start_point, outward_azimuth, section_length, current_start_hw, end_hw, section_name_log)
        
        valid_geom: Optional[QgsGeometry] = None
        if section_geom and not section_geom.isEmpty():
          valid_geom = section_geom.makeValid()
          if not valid_geom or valid_geom.isEmpty() or not valid_geom.isGeosValid():
            QgsMessageLog.logMessage(f"Warning: Invalid geometry generated for {section_name_log}.", PLUGIN_TAG, level=Qgis.Warning)
            valid_geom = None # Invalidate if makeValid failed
        else: QgsMessageLog.logMessage(f"Warning: Failed to generate geometry for {section_name_log}.", PLUGIN_TAG, level=Qgis.Warning)
        
        
        # --- Create Feature for THIS Section ---
        if valid_geom:
            try:
                fields = self._get_ols_fields("Approach")
                feature = QgsFeature(fields)
                feature.setGeometry(valid_geom)
              
                # Calculate section-specific elevations/heights
                section_outer_elevation = (current_elevation_amsl + section_length * section_slope) if current_elevation_amsl is not None else None
                section_height_gain = section_length * section_slope # Height gain over this section
              
                attr_map = {
                  "RWY_Name": runway_data.get('short_name', 'N/A'),
                  "Surface": "Approach",
                  "End_Desig": end_desig,
                  "Section_Desc": section_desc,
                  "Elevation": section_outer_elevation, # Elevation at outer edge of this section
                  "Height_AGL": section_height_gain,    # Height gain over this section
                  "Slope_Perc": section_slope * 100.0 if section_slope is not None else None,
                  "Ref": ref,
                  "Length_m": section_length,           # Length of this section
                  "InnerW_m": current_start_width,      # Width at start of this section
                  "OuterW_m": section_end_width,        # Width at end of this section
                  "Diverg_Perc": section_divergence * 100.0 if section_divergence is not None else None,
                  "Origin_Offset": section_start_dist_thr # Distance from THR to start of this section
                }
                for name, value in attr_map.items():
                  idx = fields.indexFromName(name)
                  if idx != -1: feature.setAttribute(idx, value)
                  # else: # Optional: Log if a field is missing (shouldn't happen if _get_ols_fields is correct)
                  #     QgsMessageLog.logMessage(f"DEBUG: Field '{name}' not found in Approach OLS fields.", PLUGIN_TAG, level=Qgis.Debug)
                  
                main_polygon_features.append(feature) # Add section feature to the list
              
            except Exception as e_feat:
                QgsMessageLog.logMessage(f"Error creating feature for {section_name_log}: {e_feat}", PLUGIN_TAG, level=Qgis.Critical)
                # Optionally decide whether to halt all processing for this approach end
                # return [], contour_line_features # Example: Stop if one section fails
              
        # --- Generate Contours within this Section ---
        # (Contour generation logic remains the same, using current_elevation_amsl, section_outer_elevation, etc.)
        # ... contour generation code ...
        if current_elevation_amsl is not None and section_outer_elevation is not None and abs(section_slope) > 1e-9:
            if current_elevation_amsl % APPROACH_CONTOUR_INTERVAL == 0:
                target_elev = current_elevation_amsl
                if target_elev < current_elevation_amsl:
                    target_elev += APPROACH_CONTOUR_INTERVAL
            else:
                target_elev = math.ceil(current_elevation_amsl / APPROACH_CONTOUR_INTERVAL) * APPROACH_CONTOUR_INTERVAL
            if target_elev < current_elevation_amsl - 1e-6 : target_elev += APPROACH_CONTOUR_INTERVAL
          
            while target_elev <= section_outer_elevation + 1e-6:
                delta_h = target_elev - current_elevation_amsl
                max_delta_h = section_length * section_slope
                if delta_h > max_delta_h + 1e-6 : break
                if delta_h < -1e-6 :
                    target_elev += APPROACH_CONTOUR_INTERVAL
                    continue
                if abs(section_slope) < 1e-9: break # Avoid division by zero if somehow slope is tiny
              
                dist_along = delta_h / section_slope
                if dist_along < 0 : dist_along = 0
                if dist_along > section_length + 1e-6: break
              
                cl_point = current_start_point.project(dist_along, outward_azimuth)
                current_width_at_dist = current_start_width + (2 * dist_along * section_divergence)
                half_width = current_width_at_dist / 2.0
              
                if cl_point and half_width > 0:
                    az_perp_l = (outward_azimuth - 90.0 + 360.0) % 360.0
                    az_perp_r = (outward_azimuth + 90.0) % 360.0
                    pt_l = cl_point.project(half_width, az_perp_l)
                    pt_r = cl_point.project(half_width, az_perp_r)
                  
                    if pt_l and pt_r:
                        contour_geom = QgsGeometry.fromPolylineXY([pt_l, pt_r])
                        if contour_geom and not contour_geom.isEmpty():
                            contour_fields = self._get_approach_contour_fields()
                            contour_feature = QgsFeature(contour_fields)
                            contour_feature.setGeometry(contour_geom)
                            contour_attr_map = { "RWY_Name": runway_data.get('short_name', 'N/A'), "End_Desig": end_desig, "Surface": f"Approach Contour {target_elev:.0f}m", "Contour_Elev_AMSL": target_elev, "Ref": ref }
                            for name, value in contour_attr_map.items(): idx = contour_fields.indexFromName(name);
                            if idx != -1: contour_feature.setAttribute(idx, value)
                            contour_line_features.append(contour_feature)
                          
                target_elev += APPROACH_CONTOUR_INTERVAL
        # --- End Contour Generation for Section ---
              
        # --- Update for next iteration ---
        current_start_point = end_point
        current_start_width = section_end_width
        # Use calculated outer elevation for the start of the next section
        current_elevation_amsl = section_outer_elevation
        current_dist_from_thr += section_length # Update cumulative distance
      
      # --- Return lists of features ---
      return main_polygon_features, contour_line_features # <<< Return list of section features
    
    def _generate_tocs(self, runway_data: dict, rwy_params: dict, arc_num: int, end_type: str,
                runway_thr_point: QgsPointXY, # Start point of runway/clearway for offset calc
                clearway_len: float,
                outward_azimuth: float, end_desig: str,
                origin_elevation: Optional[float]) -> Optional[QgsFeature]:
        """
        Generates a single Take-Off Climb Surface (TOCS) feature.
        Shape can be a composite trapezoid + rectangle based on parameters.
        """
        # 1. Get Parameters
        params = ols_dimensions.get_ols_params(arc_num, None, 'TOCS') # TOCS depends only on code
        if not params:
          QgsMessageLog.logMessage(f"No TOCS params found for {end_desig} (Code {arc_num})", PLUGIN_TAG, level=Qgis.Warning)
          return None
      
        origin_offset = params.get('origin_offset', 0.0)
        inner_width = params.get('inner_edge_width', 0.0)
        divergence = params.get('divergence', 0.0) # Per side
        overall_length = params.get('length', 0.0) # Renamed for clarity
        final_width = params.get('final_width', 0.0)
        slope = params.get('slope', 0.0)
        ref = params.get('ref', 'MOS 139 T8.2-1 (Check)')
      
        inner_hw = inner_width / 2.0
        final_hw = final_width / 2.0
      
        if overall_length <= 0 or inner_hw <= 0 or divergence is None or divergence <= 0 or final_width <= inner_width:
          QgsMessageLog.logMessage(f"Invalid TOCS dimensions/params for {end_desig} (L={overall_length}, IW={inner_width}, FW={final_width}, Div={divergence})", PLUGIN_TAG, level=Qgis.Warning)
          return None
      
        # 2. Calculate Start Point of TOCS Inner Edge
        effective_runway_end = runway_thr_point
        if clearway_len > 0:
          effective_runway_end = effective_runway_end.project(clearway_len, outward_azimuth)
        start_point = effective_runway_end.project(origin_offset, outward_azimuth)
        if not start_point:
          QgsMessageLog.logMessage(f"Failed calc TOCS start point {end_desig}", PLUGIN_TAG, level=Qgis.Warning)
          return None
      
        # 3. Calculate Length of Divergence Section
        width_increase_per_side = final_hw - inner_hw
        # If final width is already met or exceeded by inner width, divergence length is 0
        length_divergence = width_increase_per_side / divergence if width_increase_per_side > 0 else 0.0
      
        QgsMessageLog.logMessage(f"TOCS {end_desig}: OverallLen={overall_length:.1f}, DivergLen={length_divergence:.1f}", PLUGIN_TAG, level=Qgis.Info)
      
        # 4. Generate Geometry
        final_geom: Optional[QgsGeometry] = None
        try:
          if length_divergence >= overall_length - 1e-6: # Use tolerance - Essentially single trapezoid
            QgsMessageLog.logMessage(f"TOCS {end_desig}: Generating as single trapezoid (divergence >= overall length).", PLUGIN_TAG, level=Qgis.Info)
            # Calculate outer half-width at the overall_length distance
            outer_hw_at_overall = inner_hw + (overall_length * divergence)
            final_geom = self._create_trapezoid(start_point, outward_azimuth, overall_length, inner_hw, outer_hw_at_overall, f"TOCS Trapezoid {end_desig}")
          
          else: # Composite shape: Trapezoid + Rectangle
            QgsMessageLog.logMessage(f"TOCS {end_desig}: Generating as composite trapezoid + rectangle.", PLUGIN_TAG, level=Qgis.Info)
            # Generate Trapezoid part
            trap_geom = self._create_trapezoid(start_point, outward_azimuth, length_divergence, inner_hw, final_hw, f"TOCS Trapezoid Part {end_desig}")
          
            # Calculate start point and length of Rectangle part
            rect_start_point = start_point.project(length_divergence, outward_azimuth)
            length_rectangle = overall_length - length_divergence
          
            if not rect_start_point or length_rectangle < 1e-6: # Check if rectangle has valid start/length
              QgsMessageLog.logMessage(f"TOCS {end_desig}: Invalid parameters for rectangular part (Start: {rect_start_point}, Len: {length_rectangle:.2f}). Using only trapezoid part.", PLUGIN_TAG, level=Qgis.Warning)
              final_geom = trap_geom # Fallback to just the trapezoid part if rect params invalid
            else:
              rect_geom = self._create_rectangle_from_start(rect_start_point, outward_azimuth, length_rectangle, final_hw, f"TOCS Rectangle Part {end_desig}")
              
              # Combine
              if trap_geom and rect_geom:
                # Use unaryUnion for potentially cleaner joins
                combined = QgsGeometry.unaryUnion([trap_geom, rect_geom])
                if combined and not combined.isEmpty():
                  final_geom = combined.makeValid() # Ensure validity
                else:
                  QgsMessageLog.logMessage(f"TOCS {end_desig}: Union of trapezoid and rectangle failed. Using only trapezoid part.", PLUGIN_TAG, level=Qgis.Warning)
                  final_geom = trap_geom # Fallback
              elif trap_geom:
                QgsMessageLog.logMessage(f"TOCS {end_desig}: Rectangle part failed. Using only trapezoid part.", PLUGIN_TAG, level=Qgis.Warning)
                final_geom = trap_geom # Fallback
              else:
                  QgsMessageLog.logMessage(f"TOCS {end_desig}: Both trapezoid and rectangle parts failed.", PLUGIN_TAG, level=Qgis.Warning)
                  final_geom = None # Complete failure
                
        except Exception as e_geom:
          QgsMessageLog.logMessage(f"Error generating TOCS geometry for {end_desig}: {e_geom}", PLUGIN_TAG, level=Qgis.Critical)
          return None
      
        # 5. Create Feature
        if not final_geom or final_geom.isEmpty() or not final_geom.isGeosValid():
          QgsMessageLog.logMessage(f"Failed create valid TOCS geometry for {end_desig}", PLUGIN_TAG, level=Qgis.Warning)
          return None
      
        # Calculate elevation and offset based on OVERALL length
        height_agl = overall_length * slope
        elevation_amsl = origin_elevation + height_agl if origin_elevation is not None else None
        total_offset_from_thr = runway_thr_point.distance(start_point) if start_point else None
      
        fields = self._get_ols_fields("TOCS")
        feature = QgsFeature(fields)
        feature.setGeometry(final_geom)
        # Set attributes based *only* on the fields present in 'fields'
        attr_map = {
          "RWY_Name": runway_data.get('short_name', 'N/A'),
          "Surface": "TOCS",
          "End_Desig": end_desig,
          "Elevation": elevation_amsl, # Elevation at outer end
          "Height_AGL": height_agl,    # Height difference over total length
          "Slope_Perc": slope * 100.0 if slope is not None else None,
          "Ref": ref,
          "Length_m": overall_length, # Report overall length
          "InnerW_m": inner_width,
          "OuterW_m": final_width,   # Report final width reached
          "Diverg_Perc": divergence * 100.0 if divergence is not None else None,
          "Origin_Offset": total_offset_from_thr # Actual offset from THR
        }
        for name, value in attr_map.items():
          idx = fields.indexFromName(name)
          if idx != -1: feature.setAttribute(idx, value)
          
        return feature

    def process_guideline_f(self, runway_data: dict, layer_group: QgsLayerTreeGroup) -> bool:
      """
      Generates RUNWAY-SPECIFIC Guideline F OLS: Inner Approach, Approach (Polygon + Contours) & TOCS.
      IHS, Conical, Transitional are handled by _generate_airport_wide_ols.
      """
      # ... (Setup code: Get data, checks, get runway params, etc. - unchanged) ...
      runway_name = runway_data.get('short_name', f"RWY_{runway_data.get('original_index','?')}")
      thr_point = runway_data.get('thr_point'); rec_thr_point = runway_data.get('rec_thr_point')
      arc_num_str = runway_data.get('arc_num')
      type1_str = runway_data.get('type1', ''); type2_str = runway_data.get('type2', '')
      thr_elev = runway_data.get('thr_elev_1'); rec_thr_elev = runway_data.get('thr_elev_2')
      
      QgsMessageLog.logMessage(f"Starting Runway OLS processing (InnerApp/App/TOCS) for {runway_name}", PLUGIN_TAG, level=Qgis.Info)
      
      if not all([thr_point, rec_thr_point, layer_group, arc_num_str]):
        QgsMessageLog.logMessage(f"OLS App/TOCS skipped {runway_name}: Missing essential data.", PLUGIN_TAG, level=Qgis.Warning)
        return False
      try: arc_num = int(arc_num_str)
      except (ValueError, TypeError):
        QgsMessageLog.logMessage(f"OLS App/TOCS skipped {runway_name}: Invalid ARC number.", PLUGIN_TAG, level=Qgis.Warning)
        return False
      
      rwy_params = self._get_runway_parameters(thr_point, rec_thr_point)
      if rwy_params is None:
           QgsMessageLog.logMessage(f"OLS App/TOCS skipped {runway_name}: Failed to get runway parameters.", PLUGIN_TAG, level=Qgis.Warning)
           return False
      primary_desig, reciprocal_desig = runway_name.split('/') if '/' in runway_name else ("THR1", "THR2")
      clearway1_len = runway_data.get('clearway1_len', 0.0); clearway2_len = runway_data.get('clearway2_len', 0.0)
      
      # --- Generate Surfaces ---
      overall_success = False
      inner_approach_features: List[QgsFeature] = []
      approach_poly_features: List[QgsFeature] = [] # Will now hold features for ALL sections
      approach_contour_features: List[QgsFeature] = []
      tocs_poly_features: List[QgsFeature] = []
      
      # --- Process Primary End (Designator 1) ---
      try:
        outward_azimuth_p = rwy_params['azimuth_r_p']
        origin_elev_p = thr_elev
        
        # --- 1a. Generate Inner Approach (Primary End) ---
        # (Inner approach logic remains the same - already creates one feature if applicable)
        inner_app_params_p = ols_dimensions.get_ols_params(arc_num, type1_str, 'InnerApproach')
        if inner_app_params_p:
            # ... (parameter extraction, geometry and feature creation for inner_app_feat_p) ...
            # Check if all required params exist
            slope_p = inner_app_params_p.get('slope')
            start_dist_p = inner_app_params_p.get('start_dist_from_thr')
            inner_app_length = inner_app_params_p.get('length')
            inner_app_width = inner_app_params_p.get('width')
            inner_app_ref = inner_app_params_p.get('ref', "MOS 139 T8.2-1 (Verify)")
          
            if all(v is not None for v in [slope_p, start_dist_p, inner_app_length, inner_app_width]):
                 inner_app_half_width = inner_app_width / 2.0
                 start_point_p = thr_point.project(start_dist_p, outward_azimuth_p)
                 if start_point_p:
                      inner_app_geom_p = self._create_rectangle_from_start(
                          start_point_p, outward_azimuth_p, inner_app_length,
                          inner_app_half_width, f"Inner Approach {primary_desig}"
                      )
                      if inner_app_geom_p and not inner_app_geom_p.isEmpty() and inner_app_geom_p.isGeosValid():
                           # ... (create feature 'feat' and set attributes) ...
                           fields = self._get_ols_fields("InnerApproach")
                           feat = QgsFeature(fields)
                           feat.setGeometry(inner_app_geom_p)
                           height_agl_p = inner_app_length * slope_p
                           outer_elev_p = origin_elev_p + height_agl_p if origin_elev_p is not None else None
                           attr_map = {
                               "RWY_Name": runway_name, "Surface": "Inner Approach", "End_Desig": primary_desig,
                               "Elevation": outer_elev_p, "Height_AGL": height_agl_p,
                               "Slope_Perc": slope_p * 100.0, "Ref": inner_app_ref,
                               "Length_m": inner_app_length, "InnerW_m": inner_app_width,
                               "OuterW_m": inner_app_width, # Width is constant
                               "Origin_Offset": start_dist_p
                           }
                           for name, value in attr_map.items():
                               idx = fields.indexFromName(name)
                               if idx != -1: feat.setAttribute(idx, value)
                           inner_approach_features.append(feat) # Append the single inner approach feature
                        
                        
        # --- 1b. Generate Main Approach Surface Sections & Contours (Primary End) ---
        # <<< CHANGE: Unpack list of section features >>>
        section_features_p, contour_features_p = self._generate_approach_surface(
            runway_data, rwy_params, arc_num, type1_str,
            thr_point, outward_azimuth_p,
            primary_desig, origin_elev_p
        )
        # <<< CHANGE: Extend the main list with section features >>>
        if section_features_p: approach_poly_features.extend(section_features_p)
        if contour_features_p: approach_contour_features.extend(contour_features_p)
        
        # --- 1c. Generate Take-off Climb Surface (TOCS) (Primary End) ---
        # (No changes here)
        origin_elev_tocs_p = rec_thr_elev
        feat_tocs1 = self._generate_tocs(runway_data, rwy_params, arc_num, type1_str, rec_thr_point, clearway2_len, rwy_params['azimuth_p_r'], primary_desig, origin_elev_tocs_p)
        if feat_tocs1: tocs_poly_features.append(feat_tocs1)
        
      except Exception as e: QgsMessageLog.logMessage(f"Error processing OLS for Primary End {primary_desig}: {e}", PLUGIN_TAG, level=Qgis.Critical)
      
      
      # --- Process Reciprocal End (Designator 2) ---
      try:
        outward_azimuth_r = rwy_params['azimuth_p_r']
        origin_elev_r = rec_thr_elev
        
        # --- 2a. Generate Inner Approach (Reciprocal End) ---
        # (Inner approach logic remains the same - already creates one feature if applicable)
        inner_app_params_r = ols_dimensions.get_ols_params(arc_num, type2_str, 'InnerApproach')
        if inner_app_params_r:
            # ... (parameter extraction, geometry and feature creation for inner_app_feat_r) ...
            slope_r = inner_app_params_r.get('slope')
            start_dist_r = inner_app_params_r.get('start_dist_from_thr')
            inner_app_length = inner_app_params_r.get('length')
            inner_app_width = inner_app_params_r.get('width')
            inner_app_ref = inner_app_params_r.get('ref', "MOS 139 T8.2-1 (Verify)")
          
            if all(v is not None for v in [slope_r, start_dist_r, inner_app_length, inner_app_width]):
                 inner_app_half_width = inner_app_width / 2.0
                 start_point_r = rec_thr_point.project(start_dist_r, outward_azimuth_r)
                 if start_point_r:
                      inner_app_geom_r = self._create_rectangle_from_start(
                           start_point_r, outward_azimuth_r, inner_app_length,
                           inner_app_half_width, f"Inner Approach {reciprocal_desig}"
                      )
                      if inner_app_geom_r and not inner_app_geom_r.isEmpty() and inner_app_geom_r.isGeosValid():
                           # ... (create feature 'feat' and set attributes) ...
                            fields = self._get_ols_fields("InnerApproach")
                            feat = QgsFeature(fields)
                            feat.setGeometry(inner_app_geom_r)
                            height_agl_r = inner_app_length * slope_r
                            outer_elev_r = origin_elev_r + height_agl_r if origin_elev_r is not None else None
                            attr_map = {
                                "RWY_Name": runway_name, "Surface": "Inner Approach", "End_Desig": reciprocal_desig,
                                "Elevation": outer_elev_r, "Height_AGL": height_agl_r,
                                "Slope_Perc": slope_r * 100.0, "Ref": inner_app_ref,
                                "Length_m": inner_app_length, "InnerW_m": inner_app_width,
                                "OuterW_m": inner_app_width, # Width is constant
                                "Origin_Offset": start_dist_r
                            }
                            for name, value in attr_map.items():
                                idx = fields.indexFromName(name)
                                if idx != -1: feat.setAttribute(idx, value)
                            inner_approach_features.append(feat) # Append the single inner approach feature
                        
        # --- 2b. Generate Main Approach Surface Sections & Contours (Reciprocal End) ---
        # <<< CHANGE: Unpack list of section features >>>
        section_features_r, contour_features_r = self._generate_approach_surface(
            runway_data, rwy_params, arc_num, type2_str,
            rec_thr_point, outward_azimuth_r,
            reciprocal_desig, origin_elev_r
        )
        # <<< CHANGE: Extend the main list with section features >>>
        if section_features_r: approach_poly_features.extend(section_features_r)
        if contour_features_r: approach_contour_features.extend(contour_features_r)
        
        # --- 2c. Generate Take-off Climb Surface (TOCS) (Reciprocal End) ---
        # (No changes here)
        origin_elev_tocs_r = thr_elev
        feat_tocs2 = self._generate_tocs(runway_data, rwy_params, arc_num, type2_str, thr_point, clearway1_len, rwy_params['azimuth_r_p'], reciprocal_desig, origin_elev_tocs_r)
        if feat_tocs2: tocs_poly_features.append(feat_tocs2)
        
      except Exception as e: QgsMessageLog.logMessage(f"Error processing OLS for Reciprocal End {reciprocal_desig}: {e}", PLUGIN_TAG, level=Qgis.Critical)
      
      
      # --- Layer Creation ---
      # (Layer creation logic remains the same - the lists now contain the correct features)
      
      # Create Inner Approach Layer
      if inner_approach_features:
        fields = self._get_ols_fields("InnerApproach")
        style_key_inner_app = "OLS Inner Approach"
        if style_key_inner_app not in self.style_map:
            self.style_map[style_key_inner_app] = "ols_inner_approach.qml"
        layer = self._create_and_add_layer(
            "Polygon", f"OLS_InnerApproach_{runway_name.replace('/', '_')}",
            f"{self.tr('OLS')} Inner Approach {runway_name}", fields,
            inner_approach_features, layer_group, style_key_inner_app
        )
        if layer: overall_success = True
        
      # Create Main Approach Polygon Layer (now contains section features)
      if approach_poly_features:
        fields = self._get_ols_fields("Approach") # Fields now include Section_Desc
        layer = self._create_and_add_layer(
            "Polygon", f"OLS_Approach_{runway_name.replace('/', '_')}",
            f"{self.tr('OLS')} Approach Sections {runway_name}", # Optional: Update display name
            fields, approach_poly_features, layer_group, "OLS Approach"
        )
        if layer: overall_success = True
        
      # Create Approach Contour Line Layer
      if approach_contour_features:
        fields = self._get_approach_contour_fields()
        layer = self._create_and_add_layer("LineString", f"OLS_ApproachContours_{runway_name.replace('/', '_')}", f"{self.tr('OLS')} Approach Contours {runway_name}", fields, approach_contour_features, layer_group, "OLS Approach Contour")
        if layer: overall_success = True
        
      # Create TOCS Polygon Layer
      if tocs_poly_features:
        fields = self._get_ols_fields("TOCS")
        layer = self._create_and_add_layer("Polygon", f"OLS_TOCS_{runway_name.replace('/', '_')}", f"{self.tr('OLS')} TOCS {runway_name}", fields, tocs_poly_features, layer_group, "OLS TOCS")
        if layer: overall_success = True
        
      QgsMessageLog.logMessage(f"Finished Runway OLS (InnerApp/App/TOCS) processing for {runway_name}. Success: {overall_success}", PLUGIN_TAG, level=Qgis.Info)
      return overall_success

    def process_guideline_g(self, cns_facilities_data: List[dict], icao_code: str,
                            target_crs: QgsCoordinateReferenceSystem, layer_group: QgsLayerTreeGroup) -> bool:
        """Processes Guideline G: CNS Facilities BRAs using pre-validated data."""
        if not cns_facilities_data: QgsMessageLog.logMessage("Guideline G skipped: No valid CNS facilities provided.", PLUGIN_TAG, level=Qgis.Info); return False
        overall_success = False
        fields = QgsFields([QgsField("SourceFacID", QVariant.String), QgsField("FacType", QVariant.String), QgsField("SurfName", QVariant.String), QgsField("ReqHeight", QVariant.Double), QgsField("Guideline", QVariant.String), QgsField("Shape", QVariant.String), QgsField("InnerRad_m", QVariant.Double), QgsField("OuterRad_m", QVariant.Double), QgsField("HeightRule", QVariant.String)])

        for facility_data in cns_facilities_data:
            facility_id = facility_data.get('id', 'N/A'); facility_type = facility_data.get('type', 'Unknown'); facility_geom = facility_data.get('geom'); facility_elev = facility_data.get('elevation')
            if not facility_geom or not facility_geom.isGeosValid(): continue
            bra_specs_list = cns_dimensions.get_cns_spec(facility_type);
            if not bra_specs_list: continue

            for surface_spec in bra_specs_list:
                try:
                    surface_name = surface_spec.get('SurfaceName', 'Unkn'); shape_type = surface_spec.get('Shape', 'Unkn').upper()
                    type_parts = facility_type.split('('); fac_acronym = ""
                    if len(type_parts) > 1 and type_parts[1].strip().endswith(')'): fac_acronym = type_parts[1].strip()[:-1].strip()
                    else: predefined_acronyms = {"NON-DIRECTIONAL BEACON": "NDB", "VHF OMNI-DIRECTIONAL RANGE": "VOR", "DISTANCE MEASURING EQUIPMENT": "DME", "PRIMARY SURVEILLANCE RADAR": "PSR", "SECONDARY SURVEILLANCE RADAR": "SSR", "GROUND BASED AUGMENTATION SYSTEM": "GBAS"}; fac_acronym = predefined_acronyms.get(facility_type.upper(), facility_type.split(' ')[0])
                    layer_display_name = f"{fac_acronym} {surface_name}" if fac_acronym else f"{facility_type} {surface_name}"
                    fac_identifier = facility_id if facility_id != 'N/A' else facility_type.replace(" ", "_")[:10]; internal_name_base = f"G_CNS_{icao_code}_{fac_identifier}_{surface_name.replace(' ', '_')}"; internal_name_base = "".join(c if c.isalnum() else "_" for c in internal_name_base)
                    surface_geom = self._generate_circular_or_donut(facility_geom, surface_spec, f"{surface_name} for {facility_type} ID {facility_id}")
                    if not surface_geom: continue
                    height_rule = surface_spec.get('HeightRule', 'TBD'); height_value = surface_spec.get('HeightValue'); req_height = self._calculate_cns_height(facility_elev, height_rule, height_value, surface_geom, facility_geom)
                    feature = QgsFeature(fields); feature.setGeometry(surface_geom); feature.setAttributes([facility_id, facility_type, surface_name, req_height, 'G', shape_type, surface_spec.get('InnerRadius_m'), surface_spec.get('OuterRadius_m'), height_rule])
                    if shape_type == 'CIRCLE': style_key = "CNS Circle Zone"
                    elif shape_type == 'DONUT': style_key = "CNS Donut Zone"
                    else: style_key = "Default CNS"
                    layer_created = self._create_and_add_layer( "Polygon", internal_name_base, layer_display_name, fields, [feature], layer_group, style_key)
                    if layer_created: overall_success = True
                except Exception as e_spec: QgsMessageLog.logMessage(f"Error processing CNS surface '{surface_name}' for '{facility_type}': {e_spec}", PLUGIN_TAG, level=Qgis.Critical)

        if overall_success: QgsMessageLog.logMessage(f"Guideline G: Finished processing CNS.", PLUGIN_TAG, level=Qgis.Info)
        else: QgsMessageLog.logMessage("Guideline G: No CNS layers generated or added.", PLUGIN_TAG, level=Qgis.Info)
        return overall_success
    
    def _generate_circular_or_donut(self, facility_point_geom: QgsGeometry, surface_spec: dict, description: str) -> Optional[QgsGeometry]:
       """Generates a QgsGeometry (Circle or Donut) based on the surface spec."""
       if not facility_point_geom or not facility_point_geom.isGeosValid() or not facility_point_geom.wkbType() in [Qgis.WkbType.Point, Qgis.WkbType.PointZ, Qgis.WkbType.PointM, Qgis.WkbType.PointZM]: return None
       shape = surface_spec.get('Shape', '').upper(); outer_radius = surface_spec.get('OuterRadius_m'); inner_radius = surface_spec.get('InnerRadius_m', 0.0)
       if outer_radius is None or not isinstance(outer_radius, (int, float)) or outer_radius <= 0: return None
       if inner_radius is None or not isinstance(inner_radius, (int, float)) or inner_radius < 0: inner_radius = 0.0
       buffer_segments = 36
       outer_geom = facility_point_geom.buffer(outer_radius, buffer_segments)
       if not outer_geom or not outer_geom.isGeosValid(): outer_geom = outer_geom.makeValid() if outer_geom else None
       if not outer_geom or not outer_geom.isGeosValid(): QgsMessageLog.logMessage(f"Error: Invalid outer buffer {outer_radius}m for '{description}'.", PLUGIN_TAG, level=Qgis.Warning); return None
       if shape == 'CIRCLE': return outer_geom if inner_radius <= 1e-6 else None
       if shape == 'DONUT':
           if inner_radius >= outer_radius: return None
           if inner_radius <= 1e-6: return outer_geom
           inner_geom = facility_point_geom.buffer(inner_radius, buffer_segments)
           if not inner_geom or not inner_geom.isGeosValid(): inner_geom = inner_geom.makeValid() if inner_geom else None
           if not inner_geom or not inner_geom.isGeosValid(): QgsMessageLog.logMessage(f"Error: Invalid inner buffer {inner_radius}m for DONUT '{description}'.", PLUGIN_TAG, level=Qgis.Warning); return None
           try:
               donut_geom = outer_geom.difference(inner_geom)
               if donut_geom and donut_geom.isGeosValid(): return donut_geom
               elif donut_geom: fixed_donut = donut_geom.makeValid(); return fixed_donut if fixed_donut and fixed_donut.isGeosValid() else None
               else: return None
           except Exception as e: QgsMessageLog.logMessage(f"Error difference DONUT '{description}': {e}", PLUGIN_TAG, level=Qgis.Critical); return None
       else: QgsMessageLog.logMessage(f"Warning: Unknown shape '{shape}' for '{description}'.", PLUGIN_TAG, level=Qgis.Warning); return None
      
    def _calculate_cns_height(self, facility_elevation: Optional[float], rule: Optional[str], value: Any, geometry: QgsGeometry, facility_geom: QgsGeometry) -> Optional[float]:
      """Calculates the controlling height for the BRA surface. Placeholder."""
      if facility_elevation is None and rule in ['FacilityElevation + AGL', 'Slope']: return None
      try:
        if rule == 'TBD' or rule is None: return facility_elevation
        elif rule == 'FacilityElevation + AGL': return facility_elevation + float(value) if value is not None else facility_elevation
        elif rule == 'Fixed_AMSL': return float(value) if value is not None else None
        elif rule == 'Slope': QgsMessageLog.logMessage(f"Warning: Slope height rule '{rule}' not implemented.", PLUGIN_TAG, level=Qgis.Warning); return facility_elevation
        else: QgsMessageLog.logMessage(f"Warning: Unknown height rule '{rule}'.", PLUGIN_TAG, level=Qgis.Warning); return None
      except (ValueError, TypeError, Exception) as e: QgsMessageLog.logMessage(f"Error calculating CNS height (Rule: {rule}, Val: {value}): {e}", PLUGIN_TAG, level=Qgis.Warning); return None

    def process_guideline_i(self, runway_data: dict, layer_group: QgsLayerTreeGroup) -> bool:
        """Processes Guideline I: Public Safety Area (PSA) Trapezoids."""
        runway_name = runway_data.get('short_name', f"RWY_{runway_data.get('original_index','?')}")
        thr_point = runway_data.get('thr_point'); rec_thr_point = runway_data.get('rec_thr_point')
        if not all([thr_point, rec_thr_point, layer_group]): return False
        params = self._get_runway_parameters(thr_point, rec_thr_point);
        if params is None: return False
        psa_inner_half_w = GUIDELINE_I_PSA_INNER_WIDTH / 2.0; psa_outer_half_w = GUIDELINE_I_PSA_OUTER_WIDTH / 2.0
        if psa_inner_half_w < 0 or psa_outer_half_w < 0: return False

        fields = QgsFields([QgsField("RWY", QVariant.String), QgsField("Zone", QVariant.String), QgsField("End", QVariant.String), QgsField("Len", QVariant.Double), QgsField("InW", QVariant.Double), QgsField("OutW", QVariant.Double)])
        features_to_add = []; primary_desig, reciprocal_desig = runway_name.split('/') if '/' in runway_name else ("Primary", "Reciprocal")
        try:
            geom_p = self._create_trapezoid(thr_point, params['azimuth_r_p'], GUIDELINE_I_PSA_LENGTH, psa_inner_half_w, psa_outer_half_w, f"PSA {primary_desig}")
            if geom_p: feat = QgsFeature(fields); feat.setGeometry(geom_p); feat.setAttributes([runway_name,"PSA",primary_desig,GUIDELINE_I_PSA_LENGTH,GUIDELINE_I_PSA_INNER_WIDTH,GUIDELINE_I_PSA_OUTER_WIDTH]); features_to_add.append(feat)
        except Exception as e: QgsMessageLog.logMessage(f"Error PSA Primary {runway_name}: {e}", PLUGIN_TAG, level=Qgis.Warning)
        try:
            geom_r = self._create_trapezoid(rec_thr_point, params['azimuth_p_r'], GUIDELINE_I_PSA_LENGTH, psa_inner_half_w, psa_outer_half_w, f"PSA {reciprocal_desig}")
            if geom_r: feat = QgsFeature(fields); feat.setGeometry(geom_r); feat.setAttributes([runway_name,"PSA",reciprocal_desig,GUIDELINE_I_PSA_LENGTH,GUIDELINE_I_PSA_INNER_WIDTH,GUIDELINE_I_PSA_OUTER_WIDTH]); features_to_add.append(feat)
        except Exception as e: QgsMessageLog.logMessage(f"Error PSA Reciprocal {runway_name}: {e}", PLUGIN_TAG, level=Qgis.Warning)

        layer_created = self._create_and_add_layer("Polygon", f"PSA_{runway_name.replace('/', '_')}", f"PSA {self.tr('Runway')} {runway_name}", fields, features_to_add, layer_group, "PSA Runway")
        return layer_created is not None
    
# ============================================================
# Specialised Safeguarding Processing (e.g., RAOA)
# ============================================================
  
    def _get_raoa_fields(self) -> QgsFields:
      """Returns the QgsFields definition for the RAOA layer."""
      fields = QgsFields([
        QgsField("RWY_Name", QVariant.String, self.tr("Runway"), 50),
        QgsField("Surface", QVariant.String, self.tr("Surface Type"), 20),
        QgsField("End_Desig", QVariant.String, self.tr("End Designator"), 10),
        QgsField("Length_m", QVariant.Double, self.tr("Length (m)"), 10, 2),
        QgsField("Width_m", QVariant.Double, self.tr("Width (m)"), 10, 2),
        QgsField("Ref", QVariant.String, self.tr("Reference"), 100), # Optional reference field
      ])
      return fields
    
    def process_raoa(self, runway_data: dict, layer_group: QgsLayerTreeGroup) -> bool:
      """
      Generates the Radio Altimeter Operating Area (RAOA) if applicable.
      Applicable only for Precision Approach runways (CAT I, II, III).
      Creates rectangles 120m x 300m extending outwards from thresholds.
      """
      runway_name = runway_data.get('short_name', f"RWY_{runway_data.get('original_index','?')}")
      thr_point = runway_data.get('thr_point'); rec_thr_point = runway_data.get('rec_thr_point')
      type1_str = runway_data.get('type1', ''); type2_str = runway_data.get('type2', '')
      
      # --- Essential Checks ---
      if not all([thr_point, rec_thr_point, layer_group]):
        QgsMessageLog.logMessage(f"RAOA skipped {runway_name}: Missing essential data.", PLUGIN_TAG, level=Qgis.Warning)
        return False
      
      rwy_params = self._get_runway_parameters(thr_point, rec_thr_point)
      if rwy_params is None:
        QgsMessageLog.logMessage(f"RAOA skipped {runway_name}: Failed get runway parameters.", PLUGIN_TAG, level=Qgis.Warning)
        return False
      
      # --- Constants ---
      RAOA_LENGTH = 300.0
      RAOA_WIDTH = 120.0
      RAOA_HALF_WIDTH = RAOA_WIDTH / 2.0
      APPLICABLE_TYPES = ["Precision Approach CAT I", "Precision Approach CAT II/III"]
      
      features_to_add: List[QgsFeature] = []
      primary_desig, reciprocal_desig = runway_name.split('/') if '/' in runway_name else ("THR1", "THR2")
      
      # --- Check Primary End ---
      if type1_str in APPLICABLE_TYPES:
        try:
          # Outward azimuth from primary threshold
          outward_azimuth = rwy_params['azimuth_r_p']
          geom = self._create_rectangle_from_start(
            thr_point, outward_azimuth, RAOA_LENGTH, RAOA_HALF_WIDTH, f"RAOA {primary_desig}"
          )
          if geom:
            fields = self._get_raoa_fields()
            feature = QgsFeature(fields)
            feature.setGeometry(geom)
            attr_map = {"RWY_Name": runway_name, "Surface": "RAOA", "End_Desig": primary_desig, "Length_m": RAOA_LENGTH, "Width_m": RAOA_WIDTH, "Ref": "MOS 139 Ch 9 (Verify)"}
            for name, value in attr_map.items():
              idx = fields.indexFromName(name)
              if idx != -1: feature.setAttribute(idx, value)
            features_to_add.append(feature)
            QgsMessageLog.logMessage(f"Generated RAOA geometry for {primary_desig}", PLUGIN_TAG, level=Qgis.Info)
          else:
            QgsMessageLog.logMessage(f"Failed to generate RAOA geometry for {primary_desig}", PLUGIN_TAG, level=Qgis.Warning)
        except Exception as e:
          QgsMessageLog.logMessage(f"Error generating RAOA for {primary_desig}: {e}", PLUGIN_TAG, level=Qgis.Warning)
          
      # --- Check Reciprocal End ---
      if type2_str in APPLICABLE_TYPES:
        try:
          # Outward azimuth from reciprocal threshold
          outward_azimuth = rwy_params['azimuth_p_r']
          geom = self._create_rectangle_from_start(
            rec_thr_point, outward_azimuth, RAOA_LENGTH, RAOA_HALF_WIDTH, f"RAOA {reciprocal_desig}"
          )
          if geom:
            fields = self._get_raoa_fields()
            feature = QgsFeature(fields)
            feature.setGeometry(geom)
            attr_map = {"RWY_Name": runway_name, "Surface": "RAOA", "End_Desig": reciprocal_desig, "Length_m": RAOA_LENGTH, "Width_m": RAOA_WIDTH, "Ref": "MOS 139 Ch 9 (Verify)"}
            for name, value in attr_map.items():
              idx = fields.indexFromName(name)
              if idx != -1: feature.setAttribute(idx, value)
            features_to_add.append(feature)
            QgsMessageLog.logMessage(f"Generated RAOA geometry for {reciprocal_desig}", PLUGIN_TAG, level=Qgis.Info)
          else:
            QgsMessageLog.logMessage(f"Failed to generate RAOA geometry for {reciprocal_desig}", PLUGIN_TAG, level=Qgis.Warning)
        except Exception as e:
          QgsMessageLog.logMessage(f"Error generating RAOA for {reciprocal_desig}: {e}", PLUGIN_TAG, level=Qgis.Warning)
          
      # --- Create Layer if Features Exist ---
      if features_to_add:
        layer_name_display = f"RAOA {runway_name}"
        internal_name_base = f"RAOA_{runway_name.replace('/', '_')}"
        fields = self._get_raoa_fields() # Get fields again for layer creation
        style_key = "RAOA"
        
        layer_created = self._create_and_add_layer(
          "Polygon", internal_name_base, layer_name_display, fields,
          features_to_add, layer_group, style_key
        )
        return layer_created is not None
      else:
        QgsMessageLog.logMessage(f"RAOA not applicable or failed for {runway_name}", PLUGIN_TAG, level=Qgis.Info)
        return False # No applicable features generated
      
    def _get_taxiway_separation_fields(self) -> QgsFields:
      """Returns the QgsFields definition for the Taxiway Separation layer."""
      fields = QgsFields([
        QgsField("RWY_Name", QVariant.String, self.tr("Runway"), 50),
        QgsField("Surface", QVariant.String, self.tr("Surface Type"), 30),
        QgsField("Side", QVariant.String, self.tr("Side (L/R)"), 5),
        QgsField("Offset_m", QVariant.Double, self.tr("Offset (m)"), 10, 2),
        QgsField("Ref", QVariant.String, self.tr("Reference"), 100),
      ])
      return fields
    
    def process_taxiway_separation(self, runway_data: dict, layer_group: QgsLayerTreeGroup) -> bool:
      """
      Generates Taxiway Minimum Separation lines parallel to the runway centerline.
      Offset depends on runway classification (ARC Num/Let/Type).
      Line length is 1.5 times the runway length, centered.
      """
      runway_name = runway_data.get('short_name', f"RWY_{runway_data.get('original_index','?')}")
      thr_point = runway_data.get('thr_point'); rec_thr_point = runway_data.get('rec_thr_point')
      arc_num_str = runway_data.get('arc_num'); arc_let = runway_data.get('arc_let') # Get the letter as a string
      type1_str = runway_data.get('type1', ''); type2_str = runway_data.get('type2', '')

      # --- Essential Checks ---
      if not all([thr_point, rec_thr_point, layer_group, arc_num_str]):
        QgsMessageLog.logMessage(f"Taxiway Sep skipped {runway_name}: Missing essential data.", PLUGIN_TAG, level=Qgis.Warning)
        return False
      try:
          arc_num = int(arc_num_str)
      except (ValueError, TypeError):
          QgsMessageLog.logMessage(f"Taxiway Sep skipped {runway_name}: Invalid ARC Number '{arc_num_str}'.", PLUGIN_TAG, level=Qgis.Warning)
          return False

      # --- FIX: Validate ARC Letter ---
      # Check if arc_let is a non-empty string
      if not arc_let or not isinstance(arc_let, str) or not arc_let.strip():
          QgsMessageLog.logMessage(f"Taxiway Sep skipped {runway_name}: ARC Letter not provided or invalid ('{arc_let}').", PLUGIN_TAG, level=Qgis.Warning)
          return False
      else:
          # Optional: Clean up the letter (remove whitespace, ensure uppercase)
          # This is good practice if the downstream function expects a clean uppercase letter
          arc_let = arc_let.strip().upper()
          # You could add further validation here if needed, e.g., check if arc_let is in ['A','B','C','D','E','F']
        
      # --- Get Runway Parameters --- (This was slightly misplaced in the original snippet, should be after checks)
      rwy_params = self._get_runway_parameters(thr_point, rec_thr_point)
      if rwy_params is None or rwy_params.get('length') is None or rwy_params['length'] <= 0:
        QgsMessageLog.logMessage(f"Taxiway Sep skipped {runway_name}: Invalid runway parameters or length.", PLUGIN_TAG, level=Qgis.Warning); return False
        
      # --- Determine Governing Classification ---
      # Use the most restrictive runway type for parameter lookup
      type_order = ["", "Non-Instrument (NI)", "Non-Precision Approach (NPA)", "Precision Approach CAT I", "Precision Approach CAT II/III"]
      idx1 = type_order.index(type1_str) if type1_str in type_order else 1
      idx2 = type_order.index(type2_str) if type2_str in type_order else 1
      governing_type_str = type_order[max(idx1, idx2)]
      
      # --- Get Offset Parameter ---
      offset_params = ols_dimensions.get_taxiway_separation_offset(arc_num, arc_let, governing_type_str)
      if not offset_params:
        QgsMessageLog.logMessage(f"Skipping Taxiway Sep for {runway_name}: No offset parameters found for classification (ARC={arc_num}, Let='{arc_let}', Type='{governing_type_str}'). Check ols_dimensions.py.", PLUGIN_TAG, level=Qgis.Warning)
        return False
      offset_m = offset_params.get('offset_m')
      ref = offset_params.get('ref', 'MOS 139 T9.1 (Verify)')
      if offset_m is None or offset_m <= 0:
        QgsMessageLog.logMessage(f"Skipping Taxiway Sep for {runway_name}: Invalid offset value ({offset_m}).", PLUGIN_TAG, level=Qgis.Warning)
        return False
      
      # --- Calculate Geometry ---
      runway_length = rwy_params['length']
      line_length = runway_length * 1.5
      extension = (line_length - runway_length) / 2.0 # = 0.25 * runway_length
      
      # Start/End points along extended centerline
      # Project back from Primary THR (thr_point) using Reciprocal Azimuth (azimuth_r_p)
      line_start_cl = thr_point.project(extension, rwy_params['azimuth_r_p'])
      # Project forward from start point using Primary Azimuth (azimuth_p_r)
      line_end_cl = line_start_cl.project(line_length, rwy_params['azimuth_p_r'])
      
      if not line_start_cl or not line_end_cl:
        QgsMessageLog.logMessage(f"Failed calc taxiway sep line start/end points for {runway_name}", PLUGIN_TAG, level=Qgis.Warning)
        return False
      
      features_to_add: List[QgsFeature] = []
      geom_ok = True
      # Left Line
      try:
        pt_start_l = line_start_cl.project(offset_m, rwy_params['azimuth_perp_l'])
        pt_end_l = line_end_cl.project(offset_m, rwy_params['azimuth_perp_l'])
        if pt_start_l and pt_end_l:
          geom_l = QgsGeometry.fromPolylineXY([pt_start_l, pt_end_l])
          if geom_l and not geom_l.isEmpty():
            fields = self._get_taxiway_separation_fields()
            feat_l = QgsFeature(fields)
            feat_l.setGeometry(geom_l)
            attr_map = {"RWY_Name": runway_name, "Surface": "Taxiway Separation", "Side": "L", "Offset_m": offset_m, "Ref": ref}
            for name, value in attr_map.items(): idx = fields.indexFromName(name);
            if idx != -1: feat_l.setAttribute(idx, value)
            features_to_add.append(feat_l)
          else: geom_ok = False
        else: geom_ok = False
      except Exception as e: geom_ok = False; QgsMessageLog.logMessage(f"Error generating Left Taxi Sep line for {runway_name}: {e}", PLUGIN_TAG, level=Qgis.Warning)
      
      # Right Line
      try:
        pt_start_r = line_start_cl.project(offset_m, rwy_params['azimuth_perp_r'])
        pt_end_r = line_end_cl.project(offset_m, rwy_params['azimuth_perp_r'])
        if pt_start_r and pt_end_r:
          geom_r = QgsGeometry.fromPolylineXY([pt_start_r, pt_end_r])
          if geom_r and not geom_r.isEmpty():
            fields = self._get_taxiway_separation_fields()
            feat_r = QgsFeature(fields)
            feat_r.setGeometry(geom_r)
            attr_map = {"RWY_Name": runway_name, "Surface": "Taxiway Separation", "Side": "R", "Offset_m": offset_m, "Ref": ref}
            for name, value in attr_map.items(): idx = fields.indexFromName(name);
            if idx != -1: feat_r.setAttribute(idx, value)
            features_to_add.append(feat_r)
          else: geom_ok = False
        else: geom_ok = False
      except Exception as e: geom_ok = False; QgsMessageLog.logMessage(f"Error generating Right Taxi Sep line for {runway_name}: {e}", PLUGIN_TAG, level=Qgis.Warning)
      
      if not geom_ok:
        QgsMessageLog.logMessage(f"Failed to generate one or both taxiway separation line geometries for {runway_name}", PLUGIN_TAG, level=Qgis.Warning)
        # Continue to layer creation if at least one feature was added, otherwise return False
        if not features_to_add: return False
        
      # --- Create Layer ---
      if features_to_add:
        layer_name_display = f"Taxiway Separation {runway_name}"
        internal_name_base = f"TaxiwaySep_{runway_name.replace('/', '_')}"
        fields = self._get_taxiway_separation_fields()
        style_key = "Taxiway Separation Line" # Ensure this matches style_map
        
        layer_created = self._create_and_add_layer(
          "LineString", internal_name_base, layer_name_display, fields,
          features_to_add, layer_group, style_key
        )
        QgsMessageLog.logMessage(f"Finished Taxiway Separation processing for {runway_name}. Layer created: {layer_created is not None}", PLUGIN_TAG, level=Qgis.Info)
        return layer_created is not None
      else:
        # Should have returned earlier if both failed, but as safety net
        return False
    
# ============================================================
# End of Plugin Class
# ============================================================