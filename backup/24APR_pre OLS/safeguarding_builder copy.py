# -*- coding: utf-8 -*-
# safeguarding_builder.py

import os.path
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
    QgsLineString, QgsPointXY, QgsPolygon,
    QgsLayerTreeGroup, QgsLayerTreeNode,  QgsLayerTreeLayer,
    QgsMessageLog, Qgis, QgsCoordinateReferenceSystem,
    QgsVectorFileWriter, QgsCoordinateTransformContext,
    QgsVectorLayerUtils, QgsCoordinateTransform
)
from qgis.gui import QgsMessageBar # QgsFileWidget not used directly

# --- Local Imports ---
from . import cns_dimensions # Assuming cns_dimensions.py is in the same directory
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

    def run_safeguarding_processing(self):
        """Orchestrates the creation of safeguarding surfaces using validated input data."""
        QgsMessageLog.logMessage("--- Safeguarding Processing Started ---", PLUGIN_TAG, level=Qgis.Info)
        self.successfully_generated_layers = []
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
          "WSZ Runway": "guideline_b_wsz.qml",
          "WMZ A": "default_zone_polygon.qml",
          "WMZ B": "default_zone_polygon.qml",
          "WMZ C": "default_zone_polygon.qml",
          "LCZ A": "default_zone_polygon.qml",
          "LCZ B": "default_zone_polygon.qml",
          "LCZ C": "default_zone_polygon.qml",
          "LCZ D": "default_zone_polygon.qml",
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
            arp_layer = self.create_arp_layer(arp_point, arp_east, arp_north, icao_code, target_crs, main_group) # Pass main_group
            if arp_layer: arp_layer_created = True

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
                        generated_elements = self.generate_physical_geometry(rwy_data)
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

        # Process Airport-Wide Guidelines
        guideline_c_processed = False; guideline_g_processed = False
        if arp_point and guideline_groups.get('C'): guideline_c_processed = self.process_guideline_c(arp_point, icao_code, target_crs, guideline_groups['C'])
        if cns_input_list and guideline_groups.get('G'):
            try: guideline_g_processed = self.process_guideline_g(cns_input_list, icao_code, target_crs, guideline_groups['G'])
            except Exception as e_proc_g: QgsMessageLog.logMessage(f"Guideline G error: {e_proc_g}", PLUGIN_TAG, level=Qgis.Critical)
        elif not cns_input_list: QgsMessageLog.logMessage("Guideline G skipped: No valid CNS facilities.", PLUGIN_TAG, level=Qgis.Info)

        # Runway Loop (Part 2 - Guideline Processing)
        any_guideline_processed_ok = self._process_runways_part2(processed_runway_data_list, guideline_groups)

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

    def _process_runways_part2(self, processed_runway_data_list: List[dict], guideline_groups: Dict[str, Optional[QgsLayerTreeGroup]]) -> bool:
        """Processes runway-specific guidelines."""
        any_guideline_processed_ok = False
        if not processed_runway_data_list: return False
        for runway_data in processed_runway_data_list:
            rwy_name = runway_data.get('short_name', f"RWY_{runway_data.get('original_index', '?')}")
            run_success_flags = []
            try: # Process guidelines for this runway
                if guideline_groups.get('B'): run_success_flags.append(self.process_guideline_b(runway_data, guideline_groups['B']))
                if guideline_groups.get('E'): run_success_flags.append(self.process_guideline_e(runway_data, guideline_groups['E']))
                if guideline_groups.get('I'): run_success_flags.append(self.process_guideline_i(runway_data, guideline_groups['I']))
                # Add calls for other guidelines (A, F, H) here if implemented
                if any(run_success_flags): any_guideline_processed_ok = True
            except Exception as e_guideline: QgsMessageLog.logMessage(f"Error processing guidelines for {rwy_name}: {e_guideline}", PLUGIN_TAG, level=Qgis.Critical)
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
    # --- Inside class SafeguardingBuilder ---
          
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
    def create_arp_layer(self, arp_point: QgsPointXY, arp_east: Optional[float], arp_north: Optional[float], icao_code: str, crs: QgsCoordinateReferenceSystem, layer_group: QgsLayerTreeGroup) -> Optional[QgsVectorLayer]:
        """Creates the ARP point layer using the helper."""
        fields = QgsFields([QgsField("ICAO", QVariant.String), QgsField("Name", QVariant.String), QgsField("Easting", QVariant.Double), QgsField("Northing", QVariant.Double)])
        try:
            arp_geom = QgsGeometry.fromPointXY(arp_point);
            if arp_geom.isNull(): return None
            feature = QgsFeature(fields); feature.setGeometry(arp_geom)
            east_attr = arp_east if arp_east is not None else arp_point.x(); north_attr = arp_north if arp_north is not None else arp_point.y()
            feature.setAttributes([icao_code, f"{icao_code} ARP", east_attr, north_attr])
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
        if not isinstance(thr_point, QgsPointXY) or not isinstance(rec_thr_point, QgsPointXY) or thr_point.compare(rec_thr_point, 1e-6): return None
        try:
            length = thr_point.distance(rec_thr_point); azimuth_p_r = thr_point.azimuth(rec_thr_point); azimuth_r_p = rec_thr_point.azimuth(thr_point)
            azimuth_perp_r = (azimuth_p_r + 90.0) % 360.0; azimuth_perp_l = (azimuth_p_r - 90.0 + 360.0) % 360.0
            return {'length': length, 'azimuth_p_r': azimuth_p_r, 'azimuth_r_p': azimuth_r_p, 'azimuth_perp_l': azimuth_perp_l, 'azimuth_perp_r': azimuth_perp_r}
        except Exception as e: QgsMessageLog.logMessage(f"Error calculating runway parameters: {e}", PLUGIN_TAG, level=Qgis.Critical); return None

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

    def process_guideline_f(self, runway_data: dict, layer_group: QgsLayerTreeGroup) -> bool:
        """Placeholder for Guideline F: Protected Airspace processing."""
        QgsMessageLog.logMessage("Guideline F processing not implemented.", PLUGIN_TAG, level=Qgis.Info)
        return False

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
# End of Plugin Class
# ============================================================