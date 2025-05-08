# -*- coding: utf-8 -*-
# safeguarding_builder.py

import os.path
import functools
from typing import Union, Dict, Optional, List, Any # Added Any type hint

# --- Qt Imports ---
from qgis.PyQt import QtWidgets, QtCore
from qgis.PyQt.QtCore import QSettings, QTranslator, QCoreApplication, QVariant
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction, QMessageBox, QPushButton, QDialogButtonBox

# --- QGIS Imports ---
from qgis.core import (
    QgsProject, QgsVectorLayer, QgsVectorDataProvider,
    QgsFields, QgsField, QgsFeature, QgsGeometry, QgsGeometryUtils,
    QgsLineString, QgsPointXY, QgsPolygon,
    QgsLayerTreeGroup, QgsLayerTreeNode,
    QgsMessageLog, Qgis, QgsCoordinateReferenceSystem
)
from qgis.gui import QgsMessageBar

# --- Plugin Imports ---
# Make sure resources_rc is generated if you use resources
try:
    from .resources_rc import * # noqa: F403
except ImportError:
    print("Note: resources_rc.py not found or generated. Icons might be missing.")
    # Define dummy resource paths if needed for testing without compiling resources
    # ICON_PATH = "path/to/your/icon.png"

from .safeguarding_builder_dialog import SafeguardingBuilderDialog

# Plugin-specific constant for logging
PLUGIN_TAG = 'SafeguardingBuilder'

# ============================================================
# Constants for Guideline Parameters
# ============================================================
# Guideline B
GUIDELINE_B_FAR_EDGE_OFFSET = 500.0
GUIDELINE_B_ZONE_LENGTH_BACKWARD = 1400.0
GUIDELINE_B_ZONE_HALF_WIDTH = 1200.0

# Guideline C
GUIDELINE_C_RADIUS_A_M = 3000.0
GUIDELINE_C_RADIUS_B_M = 8000.0
GUIDELINE_C_RADIUS_C_M = 13000.0
GUIDELINE_C_BUFFER_SEGMENTS = 144

# Guideline E
GUIDELINE_E_ZONE_PARAMS = {
    'A': {'ext': 1000.0, 'half_w': 300.0, 'desc': "Lighting Zone A (0-1km ext, 300m HW)"},
    'B': {'ext': 2000.0, 'half_w': 450.0, 'desc': "Lighting Zone B (1-2km ext, 450m HW)"},
    'C': {'ext': 3000.0, 'half_w': 600.0, 'desc': "Lighting Zone C (2-3km ext, 600m HW)"},
    'D': {'ext': 4500.0, 'half_w': 750.0, 'desc': "Lighting Zone D (3-4.5km ext, 750m HW)"}
}
GUIDELINE_E_ZONE_ORDER = ['A', 'B', 'C', 'D']

# Guideline I (PSA)
GUIDELINE_I_PSA_LENGTH = 1000.0
GUIDELINE_I_PSA_INNER_WIDTH = 350.0 # Full Width
GUIDELINE_I_PSA_OUTER_WIDTH = 250.0 # Full Width

# ============================================================
# Main Plugin Class - SafeguardingBuilder
# ============================================================
class SafeguardingBuilder:
    """QGIS Plugin Implementation for NASF Safeguarding Surface Generation."""

    def __init__(self, iface):
        """Constructor: Initializes plugin resources and UI connections."""
        self.iface = iface
        self.plugin_dir = os.path.dirname(__file__)
        self.translator = None
        self.actions = []
        self.menu = self.tr(u'&Safeguarding Builder')
        self.dlg = None
        self._init_locale()

    def _init_locale(self):
        """Load translation file."""
        locale_code = QSettings().value('locale/userLocale', '')[0:2]
        locale_path = os.path.join(self.plugin_dir, 'i18n', f'SafeguardingBuilder_{locale_code}.qm')
        if os.path.exists(locale_path):
            self.translator = QTranslator()
            if self.translator.load(locale_path): QCoreApplication.installTranslator(self.translator)
            else: QgsMessageLog.logMessage(f"Failed to load translation file: {locale_path}", PLUGIN_TAG, level=Qgis.Warning); self.translator = None
        # else: No translation file found for current locale

    def tr(self, message):
        """Get the translation for a string using Qt translation API."""
        if self.translator: return QCoreApplication.translate('SafeguardingBuilder', message)
        return message

    def add_action(self, icon_path: str, text: str, callback, enabled_flag: bool = True, add_to_menu: bool = True, add_to_toolbar: bool = True, status_tip: str = None, whats_this: str = None, parent=None) -> QAction:
        """Helper method to add an action to the QGIS GUI (menu/toolbar)."""
        try:
            icon = QIcon(icon_path)
        except NameError: # If resources_rc wasn't imported
             icon = QIcon() # Default empty icon
             QgsMessageLog.logMessage(f"Icon resource not found: {icon_path}. Using default.", PLUGIN_TAG, level=Qgis.Warning)

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
        # Use actual path if resources fail, otherwise use resource path
        try:
             icon_path = ':/plugins/safeguarding_builder/icon.png'
             QIcon(icon_path) # Test if resource exists
        except (NameError, TypeError):
             icon_path = os.path.join(self.plugin_dir, "icon.png") # Fallback path

        self.add_action(
            icon_path,
            text=self.tr('NASF Safeguarding Builder'),
            callback=self.run,
            parent=self.iface.mainWindow()
        )

    def unload(self):
        """Removes the plugin menu item and icon from QGIS GUI."""
        for action in self.actions:
            self.iface.removePluginMenu(self.tr('&Safeguarding Builder'), action)
            self.iface.removeToolBarIcon(action)
        if self.dlg:
            try: self.dlg.close()
            except Exception as e: QgsMessageLog.logMessage(f"Error closing dialog during unload: {e}", PLUGIN_TAG, level=Qgis.Warning)
            self.dlg = None

    def run(self):
        """Shows the plugin dialog or brings it to front if already open."""
        # ### NOTE: Ensure the correct dialog code is loaded by reloading plugin / restarting QGIS if you see AttributeError
        if self.dlg is not None and self.dlg.isVisible():
            self.dlg.raise_(); self.dlg.activateWindow()
            QgsMessageLog.logMessage("Dialog already open, bringing to front.", PLUGIN_TAG, level=Qgis.Info)
            return

        # Create the dialog
        # ### FIX: Pass the active window as parent
        parent_window = self.iface.mainWindow()
        try:
             self.dlg = SafeguardingBuilderDialog(parent=parent_window)
        except AttributeError as e:
             # Specific catch for the _update_dialog_height error if it persists
             if '_update_dialog_height' in str(e):
                  msg = self.tr("Error initializing dialog. Please ensure the plugin is correctly installed and reload QGIS (or use Plugin Reloader).")
                  QgsMessageLog.logMessage(f"{msg} Details: {e}", PLUGIN_TAG, level=Qgis.Critical)
                  QMessageBox.critical(parent_window, self.tr("Plugin Load Error"), msg)
                  return
             else: # Re-raise other AttributeErrors
                  raise e
        except Exception as e:
             QgsMessageLog.logMessage(f"Unexpected error creating dialog: {e}", PLUGIN_TAG, level=Qgis.Critical)
             QMessageBox.critical(parent_window, self.tr("Dialog Error"), self.tr("Could not create the plugin dialog."))
             return

        # --- Connect Signals ---
        # ### FIX: Use object name from UI file for Generate button if changed
        generate_button = self.dlg.findChild(QPushButton, "pushButton_Generate") # Adjust name if needed
        button_box = self.dlg.findChild(QDialogButtonBox, "buttonBox")

        # Disconnect first
        # ### NOTE: Simplified disconnect using try/except
        if generate_button:
            try: generate_button.clicked.disconnect(self.run_safeguarding_processing)
            except TypeError: pass
        if button_box:
            try: button_box.accepted.disconnect(self.dlg.accept)
            except TypeError: pass
            try: button_box.rejected.disconnect(self.dlg.reject)
            except TypeError: pass
        try: self.dlg.finished.disconnect(self.dialog_finished)
        except TypeError: pass

        # Connect Generate button
        if generate_button:
            generate_button.clicked.connect(self.run_safeguarding_processing)
            # QgsMessageLog.logMessage("Connected Generate button.", PLUGIN_TAG, level=Qgis.Info) # Less noisy
        else:
            error_msg = self.tr("CRITICAL UI ERROR: Could not find 'Generate' button.") # Adjust name if needed
            QgsMessageLog.logMessage(error_msg, PLUGIN_TAG, level=Qgis.Critical)
            QMessageBox.critical(self.dlg, self.tr("UI Error"), f"{error_msg}\n{self.tr('Please check the UI file.')}")
            self.dlg.deleteLater(); self.dlg = None; return

        # Connect standard OK/Cancel buttons
        if button_box:
            button_box.accepted.connect(self.dlg.accept)
            button_box.rejected.connect(self.dlg.reject)

        # Connect dialog finished signal
        self.dlg.finished.connect(self.dialog_finished)

        self.dlg.show()
        QgsMessageLog.logMessage("Safeguarding Builder dialog shown.", PLUGIN_TAG, level=Qgis.Info)

    def dialog_finished(self, result: int):
        """Slot connected to the dialog's finished(int) signal."""
        QgsMessageLog.logMessage(f"Dialog finished signal received (result code: {result})", PLUGIN_TAG, level=Qgis.Info)
        # ### NOTE: Decide if dialog should persist or be recreated. Setting self.dlg=None forces recreation.
        # self.dlg = None

    # ============================================================
    # Core Processing Logic
    # ============================================================

    def run_safeguarding_processing(self):
        """Orchestrates the creation of safeguarding surfaces."""
        QgsMessageLog.logMessage("--- Safeguarding Processing Started ---", PLUGIN_TAG, level=Qgis.Info)
        self.iface.messageBar().pushMessage(self.tr("Info"), self.tr("Processing started..."), level=Qgis.Info, duration=3)

        if self.dlg is None:
            QgsMessageLog.logMessage("Processing aborted: Dialog instance is missing.", PLUGIN_TAG, level=Qgis.Critical)
            return

        project = QgsProject.instance()
        target_crs = project.crs()

        # --- 1. Get Global Inputs ---
        icao_code, arp_point, arp_east, arp_north = self._get_global_inputs()
        if icao_code is None: return # Error message already shown

        if not target_crs or not target_crs.isValid():
            self.iface.messageBar().pushMessage(self.tr("Error"), self.tr("Project CRS is invalid or not set."), level=Qgis.Critical, duration=7)
            return
        QgsMessageLog.logMessage(f"Using Project CRS: {target_crs.authid()} - {target_crs.description()}", PLUGIN_TAG, level=Qgis.Info)

        # --- 2. Setup Layer Tree ---
        root = project.layerTreeRoot()
        main_group_name = f"{icao_code} {self.tr('Safeguarding Surfaces')}"
        main_group = self._setup_main_group(root, main_group_name, project)
        if main_group is None: return

        # --- 3. Create ARP Layer ---
        arp_layer_created = False
        if arp_point:
            arp_layer = self.create_arp_layer(arp_point, arp_east, arp_north, icao_code, target_crs)
            if arp_layer:
                project.addMapLayer(arp_layer, False)
                main_group.addLayer(arp_layer)
                arp_layer_created = True
            # else: Error logged in create_arp_layer

        # --- 4. Runway Loop (Part 1 - Centrelines & Data Collection) ---
        # ### FIX: This now also collects Width, ARC, Type
        valid_runway_data_list, any_runway_base_data_ok = self._process_runways_part1(main_group, project, target_crs, icao_code)

        # --- 5. Create Guideline Groups ---
        guideline_groups = self._create_guideline_groups(main_group)

        # --- 6. Process Airport-Wide Guidelines (e.g., Guideline C) ---
        guideline_c_processed = False
        if arp_point and guideline_groups.get('C'):
            guideline_c_processed = self.process_guideline_c(arp_point, icao_code, target_crs, guideline_groups['C'])
        # elif not arp_point: QgsMessageLog.logMessage("Skipping Guideline C (No valid ARP).", PLUGIN_TAG, level=Qgis.Info)
        # elif not guideline_groups.get('C'): QgsMessageLog.logMessage("Skipping Guideline C (Group missing).", PLUGIN_TAG, level=Qgis.Warning)

        # --- 7. Runway Loop (Part 2 - Guideline Processing) ---
        any_guideline_processed_ok = self._process_runways_part2(valid_runway_data_list, guideline_groups)

        # --- 8. Final Feedback & Cleanup ---
        self._final_feedback(main_group, root, icao_code, arp_layer_created, any_runway_base_data_ok, guideline_c_processed, any_guideline_processed_ok, len(valid_runway_data_list), len(self.dlg._active_runway_indices if self.dlg else []))

        # --- 9. Close Dialog ---
        if self.dlg: self.dlg.accept() # Use accept to close cleanly

        QgsMessageLog.logMessage("--- Safeguarding Processing Finished ---", PLUGIN_TAG, level=Qgis.Info)


    # ============================================================
    # Helper Methods for run_safeguarding_processing
    # ============================================================

    def _get_global_inputs(self) -> tuple[Optional[str], Optional[QgsPointXY], Optional[float], Optional[float]]:
        """Retrieves and validates ICAO code and ARP coordinates from the dialog."""
        # ### NOTE: Simplified error handling slightly
        icao_code = None; arp_point = None; arp_east = None; arp_north = None
        try:
            icao_lineEdit = self.dlg.findChild(QtWidgets.QLineEdit, "lineEdit_airport_name")
            if not icao_lineEdit: raise RuntimeError("Cannot find 'lineEdit_airport_name'.")
            icao_code_str = icao_lineEdit.text().strip().upper()
            if not icao_code_str:
                self.iface.messageBar().pushMessage(self.tr("Error"), self.tr("Airport ICAO Code is required."), level=Qgis.Critical, duration=5)
                return None, None, None, None
            icao_code = icao_code_str

            arp_east_lineEdit = self.dlg.findChild(QtWidgets.QLineEdit, "lineEdit_arp_easting")
            arp_north_lineEdit = self.dlg.findChild(QtWidgets.QLineEdit, "lineEdit_arp_northing")
            if arp_east_lineEdit and arp_north_lineEdit:
                arp_east_str = arp_east_lineEdit.text().strip()
                arp_north_str = arp_north_lineEdit.text().strip()
                if arp_east_str and arp_north_str:
                    try:
                        arp_east_val = float(arp_east_str); arp_north_val = float(arp_north_str)
                        arp_point = QgsPointXY(arp_east_val, arp_north_val)
                        arp_east, arp_north = arp_east_val, arp_north_val
                    except ValueError:
                        self.iface.messageBar().pushMessage(self.tr("Warning"), self.tr("Invalid ARP coordinate format, Guideline C skipped."), level=Qgis.Warning, duration=5)
                        # arp_point remains None
        except (AttributeError, RuntimeError, Exception) as e:
            error_msg = self.tr("Error getting global inputs:") + f" {e}"
            QgsMessageLog.logMessage(error_msg, PLUGIN_TAG, level=Qgis.Critical)
            self.iface.messageBar().pushMessage(self.tr("Error"), error_msg, level=Qgis.Critical, duration=7)
            return None, None, None, None

        return icao_code, arp_point, arp_east, arp_north

    def _setup_main_group(self, root_node: QgsLayerTreeNode, group_name: str, project: QgsProject) -> Optional[QgsLayerTreeGroup]:
        """Finds and clears or creates the main layer group."""
        # ### NOTE: Simplified removal logic slightly
        existing_group = root_node.findGroup(group_name)
        if existing_group:
            QgsMessageLog.logMessage(f"Removing existing layer group: {group_name}", PLUGIN_TAG, level=Qgis.Info)
            # Remove children recursively BEFORE removing group node
            for node in existing_group.children():
                 if isinstance(node, QgsLayerTreeLayer) and node.layer():
                      project.removeMapLayer(node.layerId())
                 elif isinstance(node, QgsLayerTreeGroup):
                      self._remove_group_recursively(node, project) # Helper needed for nested groups
            root_node.removeChildNode(existing_group) # Now remove the empty group

        main_group = root_node.addGroup(group_name)
        if not main_group:
            msg = self.tr("Failed to create main layer group:") + f" {group_name}"
            self.iface.messageBar().pushMessage(self.tr("Error"), msg, level=Qgis.Critical, duration=5)
            QgsMessageLog.logMessage(msg, PLUGIN_TAG, level=Qgis.Critical)
            return None
        return main_group

    # ### FIX: Added helper for recursive group removal
    def _remove_group_recursively(self, group_node: QgsLayerTreeGroup, project: QgsProject):
         """Helper to remove layers and subgroups before removing a group."""
         for node in group_node.children():
              if isinstance(node, QgsLayerTreeLayer) and node.layer():
                   project.removeMapLayer(node.layerId())
              elif isinstance(node, QgsLayerTreeGroup):
                   self._remove_group_recursively(node, project)
         # After children are gone, remove this group (done by caller _setup_main_group)
         # Do not call group_node.parent().removeChildNode(group_node) here - causes issues

    def _process_runways_part1(self, main_group: QgsLayerTreeGroup, project: QgsProject, target_crs: QgsCoordinateReferenceSystem, icao_code: str) -> tuple[List[Dict[str, Any]], bool]:
      """
      Processes dialog runway inputs: validates core data (desig, coords), creates/adds centrelines,
      and collects all data (including optional Width, ARC, Type) for guideline processing.
      Allows processing to continue even if optional fields like Width are empty/invalid.
      """
      valid_runway_data_list = []
      any_runway_base_data_ok = False
      try:
        active_indices = sorted(list(self.dlg._active_runway_indices))
      except AttributeError:
        QgsMessageLog.logMessage("Error accessing dialog's active runway indices.", PLUGIN_TAG, level=Qgis.Critical)
        return [], False
      
      for index in active_indices:
        short_runway_name = f"RWY_{index}_ERR"; centreline_layer = None
        runway_data: Dict[str, Any] = { # Initialize dict for this runway
          "icao": icao_code, "index": index, "target_crs": target_crs,
          "short_name": short_runway_name # Default name
        }
        try:
          # --- Retrieve widget values ---
          group_box = self.dlg.findChild(QtWidgets.QGroupBox, f"groupBox_runway_{index}")
          if not group_box: raise RuntimeError(f"GroupBox not found for index {index}.")
          
          desig_le = group_box.findChild(QtWidgets.QLineEdit, f"lineEdit_rwy_desig_{index}")
          suffix_combo = group_box.findChild(QtWidgets.QComboBox, f"comboBox_rwy_suffix_{index}")
          thr_east_le = group_box.findChild(QtWidgets.QLineEdit, f"lineEdit_thr_easting_{index}")
          thr_north_le = group_box.findChild(QtWidgets.QLineEdit, f"lineEdit_thr_northing_{index}")
          rec_east_le = group_box.findChild(QtWidgets.QLineEdit, f"lineEdit_reciprocal_thr_easting_{index}")
          rec_north_le = group_box.findChild(QtWidgets.QLineEdit, f"lineEdit_reciprocal_thr_northing_{index}")
          width_le = group_box.findChild(QtWidgets.QLineEdit, f"lineEdit_runway_width_{index}")
          arc_num_combo = group_box.findChild(QtWidgets.QComboBox, f"comboBox_arc_num_{index}")
          arc_let_combo = group_box.findChild(QtWidgets.QComboBox, f"comboBox_arc_let_{index}")
          type1_combo = group_box.findChild(QtWidgets.QComboBox, f"comboBox_type_desig1_{index}")
          type2_combo = group_box.findChild(QtWidgets.QComboBox, f"comboBox_type_desig2_{index}")
          
          # Check core widgets needed for centreline and naming
          core_widgets = [desig_le, suffix_combo, thr_east_le, thr_north_le, rec_east_le, rec_north_le]
          # Check optional widgets (log warning if missing but don't stop)
          optional_widgets = [width_le, arc_num_combo, arc_let_combo, type1_combo, type2_combo]
          if not all(core_widgets): raise RuntimeError(f"Could not find core widgets for runway index {index}.")
          if not all(optional_widgets): QgsMessageLog.logMessage(f"Warning: Missing optional input widgets for runway {index}.", PLUGIN_TAG, level=Qgis.Warning)
          
          
          # --- Get and Validate CORE Values (Designation, Coordinates) ---
          rwy_desig_str = desig_le.text()
          suffix = suffix_combo.currentText()
          thr_east_str = thr_east_le.text().strip(); thr_north_str = thr_north_le.text().strip()
          rec_thr_east_str = rec_east_le.text().strip(); rec_thr_north_str = rec_north_le.text().strip()
          
          # Core validation - raises ValueError on failure, skipping this runway
          if not rwy_desig_str: raise ValueError("Designation cannot be empty.")
          try: designator_num = int(rwy_desig_str)
          except ValueError: raise ValueError("Designator must be a number.")
          if not (1 <= designator_num <= 36): raise ValueError("Designator must be between 01 and 36.")
          
          if not all([thr_east_str, thr_north_str, rec_thr_east_str, rec_thr_north_str]): raise ValueError("Coordinate fields cannot be empty.")
          try:
            thr_east = float(thr_east_str); thr_north = float(thr_north_str)
            rec_thr_east = float(rec_thr_east_str); rec_thr_north = float(rec_thr_north_str)
          except ValueError as e: raise ValueError(f"Invalid coordinate format: {e}") from e
          thr_point = QgsPointXY(thr_east, thr_north); rec_thr_point = QgsPointXY(rec_thr_east, rec_thr_north)
          if thr_point.compare(rec_thr_point, epsilon=1e-6): raise ValueError("Threshold points are coincident.")
          
          # --- Get and Store OPTIONAL Values (Width, ARC, Type) ---
          # Width (Store None if empty/invalid, log warning but DO NOT raise error)
          width: Optional[float] = None
          if width_le: # Check if widget exists
            width_str = width_le.text().strip()
            if width_str:
              try:
                width_val = float(width_str)
                if width_val > 0:
                  width = width_val
                else: QgsMessageLog.logMessage(f"Runway {index}: Width '{width_str}' not positive. Storing as None.", PLUGIN_TAG, level=Qgis.Warning)
              except ValueError: QgsMessageLog.logMessage(f"Runway {index}: Invalid Width format '{width_str}'. Storing as None.", PLUGIN_TAG, level=Qgis.Warning)
            # else: Width is empty, width remains None
              
          # ARC/Type (Get text, store as is or None if widget missing)
          arc_num_str = arc_num_combo.currentText() if arc_num_combo else None
          arc_let_str = arc_let_combo.currentText() if arc_let_combo else None
          type1_str = type1_combo.currentText() if type1_combo else None
          type2_str = type2_combo.currentText() if type2_combo else None
          
          
          # --- Update runway_data dictionary ---
          runway_data["designator_num"] = designator_num
          runway_data["suffix"] = suffix
          runway_data["thr_point"] = thr_point
          runway_data["rec_thr_point"] = rec_thr_point
          runway_data["width"] = width # Store width (could be None)
          runway_data["arc_num"] = arc_num_str
          runway_data["arc_let"] = arc_let_str
          runway_data["type1"] = type1_str # Primary end type
          runway_data["type2"] = type2_str # Reciprocal end type
          
          
          # --- Format Runway Name (use validated data) ---
          primary_desig = f"{designator_num:02d}{suffix}"
          reciprocal_num = (designator_num + 18) if designator_num <= 18 else (designator_num - 18)
          reciprocal_suffix = {"L": "R", "R": "L", "C": "C"}.get(suffix, "")
          reciprocal_desig = f"{reciprocal_num:02d}{reciprocal_suffix}"
          short_runway_name = f"{primary_desig}/{reciprocal_desig}"
          runway_data["short_name"] = short_runway_name # Update name in dict
          
          # --- Create Centreline Layer ---
          centreline_layer = self.create_runway_centreline_layer(thr_point, rec_thr_point, short_runway_name, target_crs)
          if centreline_layer:
            project.addMapLayer(centreline_layer, False)
            node = main_group.addLayer(centreline_layer)
            if node: node.setName(f"{self.tr('Runway')} {short_runway_name} {self.tr('Centreline')}")
            runway_data["centreline_layer"] = centreline_layer
          else:
            QgsMessageLog.logMessage(f"Failed to create centreline layer for {short_runway_name}.", PLUGIN_TAG, level=Qgis.Warning)
            runway_data["centreline_layer"] = None
            
          # --- Add to list if CORE checks passed ---
          valid_runway_data_list.append(runway_data)
          any_runway_base_data_ok = True
          
        except (ValueError, RuntimeError, TypeError) as e: # Catch CORE validation errors
          error_message = self.tr("Skipping Runway Index {idx} (Core Data Error):").format(idx=index) + f" {e}"
          QgsMessageLog.logMessage(error_message, PLUGIN_TAG, level=Qgis.Warning)
          self.iface.messageBar().pushMessage(self.tr("Input Error"), error_message, level=Qgis.Warning, duration=8)
          # Don't remove centreline here as it wouldn't have been created if core data failed
          continue # Skip to next runway index
        except Exception as e: # Catch unexpected errors
          error_message = self.tr("Unexpected error processing Runway {idx} (Part 1):").format(idx=index) + f" {e}"
          QgsMessageLog.logMessage(error_message, PLUGIN_TAG, level=Qgis.Critical)
          self.iface.messageBar().pushMessage(self.tr("Processing Error"), error_message, level=Qgis.Critical, duration=8)
          if centreline_layer and centreline_layer.isValid(): project.removeMapLayer(centreline_layer.id()) # Cleanup if created before unexpected error
          continue
      
      return valid_runway_data_list, any_runway_base_data_ok
  
    def _create_guideline_groups(self, main_group: QgsLayerTreeGroup) -> Dict[str, Optional[QgsLayerTreeGroup]]:
        """Creates the top-level groups for each guideline within the main group."""
        # ### NOTE: Added H for Helipads placeholder
        guideline_defs = {
            'A': self.tr("Guideline A: Aircraft Noise"),
            'B': self.tr("Guideline B: Windshear"),
            'C': self.tr("Guideline C: Wildlife"),
            'E': self.tr("Guideline E: Lighting"),
            'F': self.tr("Guideline F: Protected Airspace"),
            'G': self.tr("Guideline G: CNS Facilities"),
            'H': self.tr("Guideline H: Helicopter Landing Sites"),
            'I': self.tr("Guideline I: Public Safety")
        }
        guideline_groups: Dict[str, Optional[QgsLayerTreeGroup]] = {}
        # QgsMessageLog.logMessage("Creating top-level guideline groups...", PLUGIN_TAG, level=Qgis.Info)
        for key, name in guideline_defs.items():
            grp = main_group.addGroup(name)
            if grp: guideline_groups[key] = grp
            else: guideline_groups[key] = None; QgsMessageLog.logMessage(f"Failed to create group: {name}", PLUGIN_TAG, level=Qgis.Warning)
        return guideline_groups

    def _process_runways_part2(self, valid_runway_data_list: List[dict], guideline_groups: Dict[str, Optional[QgsLayerTreeGroup]]) -> bool:
        """Processes runway-specific guidelines for each valid runway."""
        # ### NOTE: Simplified logic slightly
        any_guideline_processed_ok = False
        if not valid_runway_data_list:
            QgsMessageLog.logMessage("Skipping Runway Guidelines: No valid runway data.", PLUGIN_TAG, level=Qgis.Info)
            return False

        # QgsMessageLog.logMessage(f"Runway Loop Part 2: Processing Guidelines for {len(valid_runway_data_list)} valid runways...", PLUGIN_TAG, level=Qgis.Info)
        for runway_data in valid_runway_data_list:
            rwy_name = runway_data.get('short_name', f"RWY_{runway_data.get('index', '?')}")
            # QgsMessageLog.logMessage(f"--- Processing Guidelines for {rwy_name} ---", PLUGIN_TAG, level=Qgis.Info)
            run_success_flags = []
            try:
                # Call processing functions, checking if the target group exists
                # ### NOTE: Pass runway_data which now contains Width, ARC, Type etc.
                if guideline_groups.get('A'): run_success_flags.append(self.process_guideline_a(runway_data, guideline_groups['A']))
                if guideline_groups.get('B'): run_success_flags.append(self.process_guideline_b(runway_data, guideline_groups['B']))
                if guideline_groups.get('E'): run_success_flags.append(self.process_guideline_e(runway_data, guideline_groups['E']))
                if guideline_groups.get('F'): run_success_flags.append(self.process_guideline_f(runway_data, guideline_groups['F']))
                if guideline_groups.get('G'): run_success_flags.append(self.process_guideline_g(runway_data, guideline_groups['G']))
                # Guideline H might be separate logic not per-runway
                if guideline_groups.get('I'): run_success_flags.append(self.process_guideline_i(runway_data, guideline_groups['I']))

                if any(run_success_flags): # If any guideline processing returned True for this runway
                    any_guideline_processed_ok = True

            except Exception as e_guideline:
                error_message = self.tr("Error processing guidelines for Runway {rwy}:").format(rwy=rwy_name) + f" {e_guideline}"
                QgsMessageLog.logMessage(error_message, PLUGIN_TAG, level=Qgis.Critical)
                self.iface.messageBar().pushMessage(self.tr("Guideline Error"), error_message, level=Qgis.Critical, duration=8)
                continue # Continue to next runway

        return any_guideline_processed_ok

    def _final_feedback(self, main_group: Optional[QgsLayerTreeGroup], root_node: QgsLayerTreeNode, icao_code: str,
                        arp_ok: bool, rwy_base_ok: bool, guide_c_ok: bool, guide_rwy_ok: bool,
                        processed_rwy_count: int, active_rwy_count: int):
        """Provides final user feedback and cleans up empty group if necessary."""
        if main_group is None: return

        # Check if *anything* was successfully created
        anything_created = arp_ok or rwy_base_ok or guide_c_ok or guide_rwy_ok

        if anything_created:
            # Build success message
            success_msg_parts = [f"{self.tr('Processing complete for')} {icao_code}."]
            if active_rwy_count > 0: # Only mention runways if some were defined
                 status = f"{processed_rwy_count}/{active_rwy_count} runways"
                 if rwy_base_ok and guide_rwy_ok: status += " processed successfully."
                 elif rwy_base_ok: status += " base data processed."
                 else: status += " had errors."
                 success_msg_parts.append(status)
            # Add messages for specific successes if needed (e.g., guide_c_ok)

            final_msg = " ".join(success_msg_parts)
            self.iface.messageBar().pushMessage(self.tr("Success"), final_msg.strip(), level=Qgis.Success, duration=7)
            main_group.setExpanded(True) # Expand the main group
            # QgsMessageLog.logMessage("Safeguarding processing finished successfully.", PLUGIN_TAG, level=Qgis.Info)
        else:
            # Only reached if all parts failed or were skipped
            self.iface.messageBar().pushMessage(self.tr("Warning"), self.tr("No safeguarding surfaces or base data generated."), level=Qgis.Warning, duration=6)
            QgsMessageLog.logMessage("Safeguarding processing finished, but nothing was generated.", PLUGIN_TAG, level=Qgis.Warning)
            # Remove the empty main group
            if root_node.findGroup(main_group.name()):
                QgsMessageLog.logMessage(f"Removing empty main group: {main_group.name()}", PLUGIN_TAG, level=Qgis.Info)
                project = QgsProject.instance()
                self._remove_group_recursively(main_group, project) # Use helper to clear potential empty subgroups
                root_node.removeChildNode(main_group)


    # ============================================================
    # Geometry Creation Helper Methods
    # ============================================================
    # ### NOTE: These methods seem generally okay, added some minor robustness checks

    def create_arp_layer(self, arp_point: QgsPointXY, arp_east: Optional[float], arp_north: Optional[float], icao_code: str, crs: QgsCoordinateReferenceSystem) -> Optional[QgsVectorLayer]:
        """Creates a temporary memory layer containing the ARP point."""
        # QgsMessageLog.logMessage(f"Creating ARP layer for {icao_code}", PLUGIN_TAG, level=Qgis.Info)
        try:
            internal_layer_name = f"arp_{icao_code}_{id(self)}"; display_name = f"{icao_code} {self.tr('ARP')}"
            layer = QgsVectorLayer(f"Point?crs={crs.authid()}", internal_layer_name, "memory")
            if not layer.isValid(): QgsMessageLog.logMessage(f"Failed memory layer creation for ARP", PLUGIN_TAG, level=Qgis.Critical); return None

            provider = layer.dataProvider(); fields = QgsFields()
            fields.append(QgsField("ICAO", QVariant.String, self.tr("ICAO Code"), 4))
            fields.append(QgsField("Name", QVariant.String, self.tr("Point Name"), 50))
            fields.append(QgsField("Easting", QVariant.Double, self.tr("Easting"), 12, 3))
            fields.append(QgsField("Northing", QVariant.Double, self.tr("Northing"), 12, 3))
            provider.addAttributes(fields); layer.updateFields()

            arp_geom = QgsGeometry.fromPointXY(arp_point)
            if arp_geom.isNull(): QgsMessageLog.logMessage("Failed ARP geometry creation", PLUGIN_TAG, level=Qgis.Warning); return None

            feature = QgsFeature(fields); feature.setGeometry(arp_geom)
            east_attr = arp_east if arp_east is not None else arp_point.x(); north_attr = arp_north if arp_north is not None else arp_point.y()
            feature.setAttributes([icao_code, display_name, east_attr, north_attr])

            layer.startEditing()
            flag, _ = provider.addFeatures([feature])
            if not flag or not layer.commitChanges():
                error_msg = layer.commitErrors(); layer.rollBack()
                QgsMessageLog.logMessage(f"Failed commit ARP layer. Error: {error_msg}", PLUGIN_TAG, level=Qgis.Warning); return None

            layer.updateExtents(); layer.setName(display_name)
            return layer
        except Exception as e: QgsMessageLog.logMessage(f"Error in create_arp_layer: {e}", PLUGIN_TAG, level=Qgis.Critical); return None

    def create_runway_centreline_layer(self, point1: QgsPointXY, point2: QgsPointXY, runway_name: str, crs: QgsCoordinateReferenceSystem) -> Optional[QgsVectorLayer]:
        """Creates a temporary memory layer for the runway centreline."""
        try:
            if not isinstance(point1, QgsPointXY) or not isinstance(point2, QgsPointXY): return None # Basic type check

            internal_layer_name = f"temp_centreline_{runway_name.replace('/', '_')}_{id(self)}"
            layer = QgsVectorLayer(f"LineString?crs={crs.authid()}", internal_layer_name, "memory")
            if not layer.isValid(): QgsMessageLog.logMessage(f"Failed centreline layer creation for {runway_name}", PLUGIN_TAG, level=Qgis.Critical); return None

            provider = layer.dataProvider(); fields = QgsFields()
            fields.append(QgsField("RWY_Name", QVariant.String, self.tr("Runway Name"), 30))
            fields.append(QgsField("Length_m", QVariant.Double, self.tr("Length (m)"), 12, 3))
            provider.addAttributes(fields); layer.updateFields()

            line_geom = QgsGeometry(QgsLineString([point1, point2]))
            if line_geom.isNull() or line_geom.isEmpty() or not line_geom.isSimple(): QgsMessageLog.logMessage(f"Invalid centreline geometry for {runway_name}.", PLUGIN_TAG, level=Qgis.Warning); return None

            feature = QgsFeature(fields); feature.setGeometry(line_geom)
            length = line_geom.length(); length_attr = round(length, 3) if length is not None and length >= 0 else None
            feature.setAttributes([runway_name, length_attr])

            layer.startEditing()
            flag, _ = provider.addFeatures([feature])
            if not flag or not layer.commitChanges():
                error_msg = layer.commitErrors(); layer.rollBack()
                QgsMessageLog.logMessage(f"Failed commit centreline layer for {runway_name}. Error: {error_msg}", PLUGIN_TAG, level=Qgis.Warning); return None

            layer.updateExtents()
            return layer
        except Exception as e: QgsMessageLog.logMessage(f"Error in create_runway_centreline_layer for {runway_name}: {e}", PLUGIN_TAG, level=Qgis.Critical); return None

    def _create_offset_rectangle(self, start_point: QgsPointXY, outward_azimuth_degrees: float, far_edge_offset: float, zone_length_backward: float, half_width: float, description: str = "Offset Rectangle") -> Optional[QgsGeometry]:
        """Helper function to create WSZ rectangle (Guideline B)."""
        # ### NOTE: Uses constants defined at top now
        try:
            if start_point is None or half_width < 0: return None # Basic checks
            backward_azimuth = (outward_azimuth_degrees + 180.0) % 360.0; az_perp_r = (outward_azimuth_degrees + 90.0) % 360.0; az_perp_l = (outward_azimuth_degrees - 90.0 + 360.0) % 360.0
            far_edge_center = start_point.project(far_edge_offset, outward_azimuth_degrees)
            near_edge_center = far_edge_center.project(zone_length_backward, backward_azimuth)
            if not far_edge_center or not near_edge_center: return None
            near_l = near_edge_center.project(half_width, az_perp_l); near_r = near_edge_center.project(half_width, az_perp_r)
            far_l = far_edge_center.project(half_width, az_perp_l); far_r = far_edge_center.project(half_width, az_perp_r)
            corner_points = [near_l, near_r, far_r, far_l];
            if not all(p is not None for p in corner_points): return None
            exterior_ring = QgsLineString(corner_points + [corner_points[0]]); polygon = QgsPolygon(exterior_ring)
            geom = QgsGeometry(polygon);
            if geom.isNull() or geom.isEmpty(): return None
            if not geom.isGeosValid(): geom = geom.makeValid()
            if geom.isNull() or geom.isEmpty(): return None # Check again after makeValid
            return geom
        except Exception as e: QgsMessageLog.logMessage(f"Error in _create_offset_rectangle for {description}: {e}", PLUGIN_TAG, level=Qgis.Critical); return None

    def _create_runway_aligned_rectangle(self, thr_point: QgsPointXY, rec_thr_point: QgsPointXY, extension_m: float, half_width_m: float, description: str = "Aligned Rectangle") -> Optional[QgsGeometry]:
        """Helper function to create runway-aligned rectangle (Guideline E)."""
        try:
            if not thr_point or not rec_thr_point or half_width_m < 0: return None
            if thr_point.distance(rec_thr_point) < 1e-6: return None # Check distance
            azimuth_p_to_r = thr_point.azimuth(rec_thr_point); azimuth_r_to_p = rec_thr_point.azimuth(thr_point)
            az_perp_r = (azimuth_p_to_r + 90.0) % 360.0; az_perp_l = (azimuth_p_to_r - 90.0 + 360.0) % 360.0
            rect_start_center = thr_point.project(extension_m, azimuth_r_to_p); rect_end_center = rec_thr_point.project(extension_m, azimuth_p_to_r)
            if not rect_start_center or not rect_end_center: return None
            corner_start_l = rect_start_center.project(half_width_m, az_perp_l); corner_start_r = rect_start_center.project(half_width_m, az_perp_r)
            corner_end_l = rect_end_center.project(half_width_m, az_perp_l); corner_end_r = rect_end_center.project(half_width_m, az_perp_r)
            corner_points = [corner_start_l, corner_start_r, corner_end_r, corner_end_l]
            if not all(p is not None for p in corner_points): return None
            exterior_ring = QgsLineString(corner_points + [corner_points[0]]); polygon = QgsPolygon(exterior_ring)
            geom = QgsGeometry(polygon);
            if geom.isNull() or geom.isEmpty(): return None
            if not geom.isGeosValid(): geom = geom.makeValid()
            if geom.isNull() or geom.isEmpty(): return None
            return geom
        except Exception as e: QgsMessageLog.logMessage(f"Error in _create_runway_aligned_rectangle for {description}: {e}", PLUGIN_TAG, level=Qgis.Critical); return None

    def _create_trapezoid(self, start_point: QgsPointXY, outward_azimuth_degrees: float, length: float, inner_half_width: float, outer_half_width: float, description: str = "Trapezoid") -> Optional[QgsGeometry]:
        """Helper function to create a trapezoid (Guideline I)."""
        # ### NOTE: Uses constants defined at top now
        try:
            if not start_point or length <= 0 or inner_half_width < 0 or outer_half_width < 0: return None
            az_perp_r = (outward_azimuth_degrees + 90.0) % 360.0; az_perp_l = (outward_azimuth_degrees - 90.0 + 360.0) % 360.0
            inner_l = start_point.project(inner_half_width, az_perp_l); inner_r = start_point.project(inner_half_width, az_perp_r)
            outer_center = start_point.project(length, outward_azimuth_degrees)
            if not outer_center: return None
            outer_l = outer_center.project(outer_half_width, az_perp_l); outer_r = outer_center.project(outer_half_width, az_perp_r)
            corner_points = [inner_l, inner_r, outer_r, outer_l]
            if not all(p is not None for p in corner_points): return None
            exterior_ring = QgsLineString(corner_points + [corner_points[0]]); polygon = QgsPolygon(exterior_ring)
            geom = QgsGeometry(polygon);
            if geom.isNull() or geom.isEmpty(): return None
            if not geom.isGeosValid(): geom = geom.makeValid()
            if geom.isNull() or geom.isEmpty(): return None
            return geom
        except Exception as e: QgsMessageLog.logMessage(f"Error in _create_trapezoid for {description}: {e}", PLUGIN_TAG, level=Qgis.Critical); return None
      
    def _calculate_strip_dimensions(self, runway_data: dict) -> dict:
      """
      Calculates required Runway Strip dimensions based on MOS Part 139.
  
      Args:
        runway_data: Dictionary containing runway details like 'arc_num',
              'runway_type', and 'width'.
  
      Returns:
        Dictionary with 'overall_width', 'graded_width', 'extension_length',
        and corresponding 'mos_...' reference strings. Returns None values
        if essential inputs are missing.
      """
      arc_num_str = runway_data.get('arc_num')
      runway_type = runway_data.get('type1') # Use primary end type for determination? Or does it apply runway-wide? Assume Type1 for now.
      runway_width = runway_data.get('width') # Can be None
      
      if not arc_num_str or not runway_type:
        QgsMessageLog.logMessage(f"Strip calc skipped for {runway_data.get('short_name', 'unknown')}: Missing ARC Num or Runway Type.", PLUGIN_TAG, level=Qgis.Warning)
        return {'overall_width': None, 'graded_width': None, 'extension_length': None,
            'mos_overall_width_ref': "Input Missing", 'mos_graded_width_ref': "Input Missing", 'mos_extension_length_ref': "Input Missing"}
      
      try:
        arc_num = int(arc_num_str)
      except (ValueError, TypeError):
        QgsMessageLog.logMessage(f"Strip calc skipped for {runway_data.get('short_name', 'unknown')}: Invalid ARC Num '{arc_num_str}'.", PLUGIN_TAG, level=Qgis.Warning)
        return {'overall_width': None, 'graded_width': None, 'extension_length': None,
            'mos_overall_width_ref': "Invalid ARC", 'mos_graded_width_ref': "Invalid ARC", 'mos_extension_length_ref': "Invalid ARC"}
      
      results = {
        'overall_width': None, 'graded_width': None, 'extension_length': None,
        'mos_overall_width_ref': "", 'mos_graded_width_ref': "", 'mos_extension_length_ref': ""
      }
      
      # Overall Width (MOS 6.2.5.7 / Table 6.17 (4)) - Seems to depend only on ARC Num from your table
      if arc_num in [1, 2]:
        results['overall_width'] = 140.0
        results['mos_overall_width_ref'] = "MOS 139 Table 6.17(4)" # Reference check: Your provided table had 140m for 1/2 and 280m for 3/4 based on precision. Let's re-verify this rule later if needed. Assuming 140/280 rule for now.
      elif arc_num in [3, 4]:
        results['overall_width'] = 280.0
        results['mos_overall_width_ref'] = "MOS 139 Table 6.17(4)"
      else:
        results['mos_overall_width_ref'] = "Invalid ARC Num"
        
        
      # Graded Width (MOS 6.2.5.9 / Table 6.17 (1)) - Depends on ARC Num and sometimes Runway Width
      results['mos_graded_width_ref'] = "MOS 139 Table 6.17(1)"
      if arc_num == 1:
        results['graded_width'] = 60.0
      elif arc_num == 2:
        results['graded_width'] = 80.0
      elif arc_num == 3:
        if runway_width is not None and runway_width <= 45.0: # Need runway width input
          results['graded_width'] = 90.0
        elif runway_width is not None and runway_width > 45.0:
          results['graded_width'] = 150.0
        else: # Runway width unknown or invalid - cannot apply rule accurately
          results['graded_width'] = None # Or default to minimum? Set to None for now.
          results['mos_graded_width_ref'] += " (Width Missing/Invalid)"
          QgsMessageLog.logMessage(f"Graded Strip Width for ARC 3 requires Runway Width. Using None.", PLUGIN_TAG, level=Qgis.Warning)
      elif arc_num == 4:
        # Assuming 150m for ARC 4 regardless of width unless <45m specified otherwise in MOS
        # Per your table, condition was "If the runway width is 45m or more" -> 150m. What if <45m for ARC 4? Defaulting to 150m.
        results['graded_width'] = 150.0
        # Add check if runway_width is needed and missing?
        # if runway_width is None:
        #      results['mos_graded_width_ref'] += " (Width Missing - Assumed >=45m)"
        
      else: # Invalid ARC Num
        results['graded_width'] = None
        results['mos_graded_width_ref'] = "Invalid ARC Num"
      
      # Extension Length (MOS 6.2.5.6) - Depends on ARC Num & Instrument Type
      is_non_instrument_code_1 = (runway_type == "Non-Instrument (NI)" and arc_num == 1)
      if is_non_instrument_code_1:
        results['extension_length'] = 30.0
        results['mos_extension_length_ref'] = "MOS 139 6.2.5.6(a)"
      else:
        results['extension_length'] = 60.0
        results['mos_extension_length_ref'] = "MOS 139 6.2.5.6(b)"
        
      return results

    def _calculate_resa_dimensions(self, runway_data: dict) -> dict:
      """
      Calculates required RESA dimensions and applicability based on MOS Part 139.
  
      Args:
        runway_data: Dictionary containing runway details like 'arc_num',
              'runway_type', and 'width'.
  
      Returns:
        Dictionary with 'required' (bool), 'width', 'length', and
        corresponding 'mos_...' reference strings.
      """
      arc_num_str = runway_data.get('arc_num')
      runway_type = runway_data.get('type1') # Check applicability based on primary end? Assume yes.
      runway_width = runway_data.get('width') # Required for RESA width calc
      
      results = {
        'required': False, 'width': None, 'length': None,
        'mos_applicability_ref': "MOS 139 6.2.6.1/2",
        'mos_width_ref': "MOS 139 6.2.6.5",
        'mos_length_ref': "MOS 139 6.2.6.3/4 & Table 6.18"
      }
      
      if not arc_num_str or not runway_type:
        QgsMessageLog.logMessage(f"RESA calc skipped for {runway_data.get('short_name', 'unknown')}: Missing ARC Num or Runway Type.", PLUGIN_TAG, level=Qgis.Warning)
        results['mos_applicability_ref'] = "Input Missing"
        return results
      
      try:
        arc_num = int(arc_num_str)
      except (ValueError, TypeError):
        QgsMessageLog.logMessage(f"RESA calc skipped for {runway_data.get('short_name', 'unknown')}: Invalid ARC Num '{arc_num_str}'.", PLUGIN_TAG, level=Qgis.Warning)
        results['mos_applicability_ref'] = "Invalid ARC"
        return results
      
      # Determine RESA Applicability (Based on refined logic using specific Type strings)
      generate_resa = False
      instrument_types = ["Non-Precision Approach (NPA)", "Precision Approach CAT I", "Precision Approach CAT II/III"]
      
      if arc_num in [3, 4]:
        generate_resa = True
        results['mos_applicability_ref'] += " (Code 3/4)"
      elif arc_num in [1, 2] and runway_type in instrument_types:
        generate_resa = True
        results['mos_applicability_ref'] += " (Code 1/2 Instrument)"
      # else: Code 1/2 Non-Instrument - RESA not required (excluding scheduled ops)
        
      results['required'] = generate_resa
      
      if generate_resa:
        # Calculate Width (Requires Runway Width)
        if runway_width is not None and runway_width > 0:
          results['width'] = 2.0 * runway_width
        else:
          results['width'] = None # Cannot calculate without runway width
          results['mos_width_ref'] += " (Runway Width Missing/Invalid)"
          QgsMessageLog.logMessage(f"RESA Width for {runway_data.get('short_name', 'unknown')} requires Runway Width. Using None.", PLUGIN_TAG, level=Qgis.Warning)
          
        # Calculate Length (Preferred)
        if arc_num in [1, 2]:
          results['length'] = 120.0
          results['mos_length_ref'] += " (Preferred)"
        elif arc_num in [3, 4]:
          results['length'] = 240.0
          results['mos_length_ref'] += " (Preferred)"
        else: # Should not happen if ARC validation passed
          results['length'] = None
          results['mos_length_ref'] = "Invalid ARC Num"
      else:
        results['mos_applicability_ref'] += " (Not Required)"
        # Width/Length remain None, clear specific refs
        results['mos_width_ref'] = "N/A"
        results['mos_length_ref'] = "N/A"
        
        
      return results
  
    def _get_runway_parameters(self, thr_point: QgsPointXY, rec_thr_point: QgsPointXY) -> Optional[dict]:
      """
      Calculates basic geometric parameters for a runway segment.
  
      Args:
        thr_point: Starting threshold point (Primary).
        rec_thr_point: Ending threshold point (Reciprocal).
  
      Returns:
        Dictionary containing 'length', 'azimuth_p_r', 'azimuth_r_p',
        'azimuth_perp_l', 'azimuth_perp_r'. Returns None if points
        are invalid or coincident.
      """
      if not isinstance(thr_point, QgsPointXY) or not isinstance(rec_thr_point, QgsPointXY):
        QgsMessageLog.logMessage("Invalid input points for runway parameter calculation.", PLUGIN_TAG, level=Qgis.Warning)
        return None
      if thr_point.compare(rec_thr_point, epsilon=1e-6):
        QgsMessageLog.logMessage("Threshold points are coincident, cannot calculate parameters.", PLUGIN_TAG, level=Qgis.Warning)
        return None
      
      try:
        length = thr_point.distance(rec_thr_point)
        azimuth_p_r = thr_point.azimuth(rec_thr_point) # Primary to Reciprocal
        azimuth_r_p = rec_thr_point.azimuth(thr_point) # Reciprocal to Primary
        
        # Perpendicular azimuths relative to Primary -> Reciprocal direction
        azimuth_perp_r = (azimuth_p_r + 90.0) % 360.0 # Right side
        azimuth_perp_l = (azimuth_p_r - 90.0 + 360.0) % 360.0 # Left side
        
        return {
          'length': length,
          'azimuth_p_r': azimuth_p_r,
          'azimuth_r_p': azimuth_r_p,
          'azimuth_perp_l': azimuth_perp_l,
          'azimuth_perp_r': azimuth_perp_r
        }
      except Exception as e:
        QgsMessageLog.logMessage(f"Error calculating runway parameters: {e}", PLUGIN_TAG, level=Qgis.Critical)
        return None
      
      
    def _create_polygon_from_corners(self, corners: List[QgsPointXY], description: str = "Polygon") -> Optional[QgsGeometry]:
      """
      Creates a QgsGeometry (Polygon) from a list of corner points.
  
      Args:
        corners: List of QgsPointXY vertices in order.
        description: A string description for logging purposes.
  
      Returns:
        A valid QgsGeometry polygon, or None if creation/validation fails.
      """
      if not corners or len(corners) < 3:
        QgsMessageLog.logMessage(f"Insufficient corners ({len(corners)}) for polygon '{description}'.", PLUGIN_TAG, level=Qgis.Warning)
        return None
      if not all(isinstance(p, QgsPointXY) for p in corners):
        QgsMessageLog.logMessage(f"Invalid point types found in corners for polygon '{description}'.", PLUGIN_TAG, level=Qgis.Warning)
        return None
      
      try:
        # Ensure the ring is closed
        if not corners[0].compare(corners[-1], epsilon=1e-6):
          closed_corners = corners + [corners[0]]
        else:
          closed_corners = corners
          
        exterior_ring = QgsLineString(closed_corners)
        if exterior_ring.isEmpty() or not exterior_ring.isSimple(): # Check line validity
          QgsMessageLog.logMessage(f"Exterior ring invalid for polygon '{description}'.", PLUGIN_TAG, level=Qgis.Warning)
          return None
      
        polygon = QgsPolygon(exterior_ring)
        geom = QgsGeometry(polygon)
      
        if geom.isNull() or geom.isEmpty():
          QgsMessageLog.logMessage(f"Failed to create initial geometry for '{description}'.", PLUGIN_TAG, level=Qgis.Warning)
          return None
      
        # Validate and attempt repair if needed
        if not geom.isGeosValid():
          QgsMessageLog.logMessage(f"Geometry for '{description}' is invalid according to GEOS, attempting makeValid().", PLUGIN_TAG, level=Qgis.Info)
          geom_valid = geom.makeValid()
          if geom_valid.isNull() or geom_valid.isEmpty():
            QgsMessageLog.logMessage(f"makeValid() failed for polygon '{description}'.", PLUGIN_TAG, level=Qgis.Warning)
            return None
          # Check WkbType after makeValid - it might return MultiPolygon etc.
          # For now, we only want simple polygons. Handle multipart later if necessary.
          if geom_valid.wkbType() not in [Qgis.WkbType.Polygon, Qgis.WkbType.PolygonZ, Qgis.WkbType.PolygonM, Qgis.WkbType.PolygonZM]:
            QgsMessageLog.logMessage(f"makeValid() resulted in non-Polygon type for '{description}'. Type: {Qgis.WkbType.displayString(geom_valid.wkbType())}", PLUGIN_TAG, level=Qgis.Warning)
            return None # Reject non-polygons for now
          geom = geom_valid # Use the validated geometry
          
        # Final check
        if geom.isNull() or geom.isEmpty():
          QgsMessageLog.logMessage(f"Final geometry is null/empty for polygon '{description}'.", PLUGIN_TAG, level=Qgis.Warning)
          return None
      
        return geom
  
      except Exception as e:
        QgsMessageLog.logMessage(f"Unexpected error in _create_polygon_from_corners for '{description}': {e}", PLUGIN_TAG, level=Qgis.Critical)
        return None
  
    # ============================================================
    # NEW: Physical Geometry Generation Function
    # ============================================================
    def generate_physical_geometry(self, runway_data: dict) -> Optional[List[Tuple[str, QgsGeometry, dict]]]:
      """
      Calculates the QgsGeometry and attributes for the physical components
      of a single runway (Runway Polygon, Shoulders, Stopways, Strips, RESAs).
    
      Args:
        runway_data: Dictionary containing all details for one runway.
    
      Returns:
        A list of tuples, where each tuple represents one geometry element:
        (element_type: str, geometry: QgsGeometry, attributes: dict).
        Returns None if essential data is missing or calculation fails early.
        Returns an empty list if no geometries are generated (e.g., RESA not required).
      """
      # --- 1. Retrieve essential data and parameters ---
      thr_point = runway_data.get('thr_point')
      rec_thr_point = runway_data.get('rec_thr_point')
      runway_width = runway_data.get('width') # This is now crucial
      runway_name = runway_data.get('short_name', f"RWY_{runway_data.get('index','?')}")
      # target_crs = runway_data.get('target_crs') # CRS needed for layer creation later
      
      # Basic validation
      if not all([thr_point, rec_thr_point]):
        QgsMessageLog.logMessage(f"Physical geometry skipped for {runway_name}: Missing threshold points.", PLUGIN_TAG, level=Qgis.Warning)
        return None
      if runway_width is None or not isinstance(runway_width, (int, float)) or runway_width <= 0:
        QgsMessageLog.logMessage(f"Runway Polygon skipped for {runway_name}: Invalid or missing Runway Width ({runway_width}).", PLUGIN_TAG, level=Qgis.Warning)
        # We can still potentially generate Strips/RESAs if needed, but not the runway polygon itself.
        # For now, let's return None if width is missing, as it's fundamental. Revisit if needed.
        return None
      
      params = self._get_runway_parameters(thr_point, rec_thr_point)
      if params is None:
        QgsMessageLog.logMessage(f"Physical geometry skipped for {runway_name}: Failed to get runway parameters.", PLUGIN_TAG, level=Qgis.Warning)
        return None
      
      # List to hold generated geometry tuples: (element_type, geometry, attributes)
      generated_elements = []
      
      # --- 2. Generate Runway Polygon ---
      try:
        half_width = runway_width / 2.0
        
        # Calculate corners using perpendicular offsets from threshold points
        # Note: QgsPointXY.project(distance, azimuth)
        thr_l = thr_point.project(half_width, params['azimuth_perp_l'])
        thr_r = thr_point.project(half_width, params['azimuth_perp_r'])
        rec_l = rec_thr_point.project(half_width, params['azimuth_perp_l'])
        rec_r = rec_thr_point.project(half_width, params['azimuth_perp_r'])
        
        corners = [thr_l, thr_r, rec_r, rec_l] # Order for polygon winding
        
        if not all(corners): # Check if any projection failed
          raise ValueError("Corner point calculation failed.")
        
        runway_geom = self._create_polygon_from_corners(corners, f"Runway Polygon {runway_name}")
        
        if runway_geom:
          attributes = {
            'RWY_Name': runway_name,
            'Type': 'Runway Pavement',
            'Width_m': runway_width,
            'Length_m': round(params['length'], 3),
            'MOS_Ref': 'MOS 139 6.2.3' # General reference for runway physical characteristics
          }
          generated_elements.append(('Runway', runway_geom, attributes))
        else:
          # Error logged within _create_polygon_from_corners
          QgsMessageLog.logMessage(f"Failed to create valid Runway Polygon geometry for {runway_name}.", PLUGIN_TAG, level=Qgis.Warning)
          # Continue to try and generate other elements? Or return None? Let's continue for now.
          
      except Exception as e:
        QgsMessageLog.logMessage(f"Error generating Runway Polygon for {runway_name}: {e}", PLUGIN_TAG, level=Qgis.Critical)
        # Decide if failure here prevents other elements. Let's return None for now if the core runway fails.
        return None
      
      # --- 3. Generate Shoulders (Placeholder - requires UI input) ---
      # shoulder_width = runway_data.get('shoulder_width', 0)
      # if shoulder_width > 0:
      #     try:
      #         # Calculate shoulder corners (adjacent to runway corners)
      #         # Left Shoulder
      #         # Right Shoulder
      #         # Create geometries and attributes
      #         # generated_elements.append(('Shoulder', shoulder_geom_l, shoulder_attrs_l))
      #         # generated_elements.append(('Shoulder', shoulder_geom_r, shoulder_attrs_r))
      #         pass # Implement later
      #     except Exception as e:
      #         QgsMessageLog.logMessage(f"Error generating Shoulders for {runway_name}: {e}", PLUGIN_TAG, level=Qgis.Warning)
      
      
      # --- 4. Generate Stopways (Placeholder - requires UI input) ---
      # stopway1_present = runway_data.get('stopway1_present', False)
      # stopway1_length = runway_data.get('stopway1_length', 0)
      # stopway2_present = runway_data.get('stopway2_present', False)
      # stopway2_length = runway_data.get('stopway2_length', 0)
      #
      # if stopway1_present and stopway1_length > 0:
      #    try:
      #        # Calculate corners for stopway off primary end (thr_point end)
      #        # Use runway_width, stopway1_length, params['azimuth_r_p']
      #        # generated_elements.append(('Stopway', stopway1_geom, stopway1_attrs))
      #        pass # Implement later
      #    except Exception as e:
      #         QgsMessageLog.logMessage(f"Error generating Stopway 1 for {runway_name}: {e}", PLUGIN_TAG, level=Qgis.Warning)
      #
      # if stopway2_present and stopway2_length > 0:
      #    try:
      #        # Calculate corners for stopway off reciprocal end (rec_thr_point end)
      #        # Use runway_width, stopway2_length, params['azimuth_p_r']
      #        # generated_elements.append(('Stopway', stopway2_geom, stopway2_attrs))
      #        pass # Implement later
      #    except Exception as e:
      #         QgsMessageLog.logMessage(f"Error generating Stopway 2 for {runway_name}: {e}", PLUGIN_TAG, level=Qgis.Warning)
      
      
      # --- 5. Generate Strips (Placeholder) ---
      # try:
      #      strip_dims = self._calculate_strip_dimensions(runway_data)
      #      if strip_dims and strip_dims.get('overall_width') and strip_dims.get('graded_width') and strip_dims.get('extension_length'):
      #          # Determine strip start/end points (considering stopways if implemented)
      #          strip_start_point = thr_point # Adjust if stopway1 exists
      #          strip_end_point = rec_thr_point # Adjust if stopway2 exists
      #          extension = strip_dims['extension_length']
      #
      #          # Calculate Graded Strip corners
      #          # Use strip_start_point, strip_end_point, extension, strip_dims['graded_width']/2.0
      #          # Create geometry and attributes (including strip_dims['mos_graded_width_ref'], strip_dims['mos_extension_length_ref'])
      #          # generated_elements.append(('GradedStrip', graded_strip_geom, graded_strip_attrs))
      #
      #          # Calculate Overall Strip corners
      #          # Use strip_start_point, strip_end_point, extension, strip_dims['overall_width']/2.0
      #          # Create geometry and attributes (including strip_dims['mos_overall_width_ref'], strip_dims['mos_extension_length_ref'])
      #          # generated_elements.append(('OverallStrip', overall_strip_geom, overall_strip_attrs))
      #      else:
      #          QgsMessageLog.logMessage(f"Skipping Strip generation for {runway_name} due to missing dimensions.", PLUGIN_TAG, level=Qgis.Warning)
      # except Exception as e:
      #     QgsMessageLog.logMessage(f"Error generating Strips for {runway_name}: {e}", PLUGIN_TAG, level=Qgis.Warning)
      
      
      # --- 6. Generate RESAs (Placeholder) ---
      # try:
      #     resa_dims = self._calculate_resa_dimensions(runway_data)
      #     if resa_dims and resa_dims['required'] and resa_dims.get('width') and resa_dims.get('length'):
      #         # Determine RESA start points (at end of strip extension)
      #         # Need strip start/end points from step 5
      #         # resa1_start_point = strip_start_point.project(extension, params['azimuth_r_p']) # Example
      #         # resa2_start_point = strip_end_point.project(extension, params['azimuth_p_r']) # Example
      #
      #         # Calculate RESA 1 corners (off primary end)
      #         # Use resa1_start_point, resa_dims['width']/2.0, resa_dims['length'], params['azimuth_r_p']
      #         # Create geometry and attributes (including resa_dims['mos_..._ref'])
      #         # generated_elements.append(('RESA', resa1_geom, resa1_attrs))
      #
      #         # Calculate RESA 2 corners (off reciprocal end)
      #         # Use resa2_start_point, resa_dims['width']/2.0, resa_dims['length'], params['azimuth_p_r']
      #         # Create geometry and attributes (including resa_dims['mos_..._ref'])
      #         # generated_elements.append(('RESA', resa2_geom, resa2_attrs))
      #     elif resa_dims and not resa_dims['required']:
      #          pass # RESA not required, do nothing
      #     else:
      #          QgsMessageLog.logMessage(f"Skipping RESA generation for {runway_name} due to missing dimensions or applicability.", PLUGIN_TAG, level=Qgis.Warning)
      # except Exception as e:
      #     QgsMessageLog.logMessage(f"Error generating RESAs for {runway_name}: {e}", PLUGIN_TAG, level=Qgis.Warning)
      
      
      # --- 7. Return collected elements ---
      return generated_elements

    # ============================================================
    # Guideline Processing Functions
    # ============================================================
    # ### NOTE: These should return True on success, False on failure/skip

    def process_guideline_a(self, runway_data: dict, layer_group: QgsLayerTreeGroup) -> bool:
        """Placeholder for Guideline A: Aircraft Noise processing."""
        # QgsMessageLog.logMessage(f"Guideline A (placeholder) for {runway_data['short_name']}", PLUGIN_TAG, level=Qgis.Info)
        # TODO: Implement Guideline A logic
        return False # Return False as it's not implemented

    def process_guideline_b(self, runway_data: dict, layer_group: QgsLayerTreeGroup) -> bool:
      """Processes Guideline B: Windshear Assessment Zone."""
      runway_name = runway_data.get('short_name', f"RWY_{runway_data.get('index','?')}")
      # QgsMessageLog.logMessage(f"Guideline B processing for {runway_name}", PLUGIN_TAG, level=Qgis.Debug)
      thr_point = runway_data.get('thr_point'); rec_thr_point = runway_data.get('rec_thr_point')
      target_crs = runway_data.get('target_crs'); project = QgsProject.instance()
      if not all([thr_point, rec_thr_point, target_crs, project, layer_group]): return False # Skip if data missing
      if thr_point.distance(rec_thr_point) < 1e-6: return False # Skip if coincident
      
      try: primary_desig = runway_name.split('/')[0]; reciprocal_desig = runway_name.split('/')[-1]
      except IndexError: primary_desig = "P"; reciprocal_desig = "R"
      
      layer_name_internal = f"WSZ_{runway_name.replace('/', '_')}_{id(self)}"; layer_display_name = f"WSZ {self.tr('Runway')} {runway_name}"
      wsz_layer = QgsVectorLayer(f"Polygon?crs={target_crs.authid()}", layer_name_internal, "memory")
      if not wsz_layer.isValid(): return False
      
      provider = wsz_layer.dataProvider(); fields = QgsFields()
      fields.append(QgsField("RWY_Name", QVariant.String, self.tr("Runway Name"))); fields.append(QgsField("Zone_Type", QVariant.String, self.tr("Zone Type"))); fields.append(QgsField("End_Desig", QVariant.String, self.tr("End Designator")))
      provider.addAttributes(fields); wsz_layer.updateFields()
      
      azimuth_p_to_r = thr_point.azimuth(rec_thr_point); azimuth_r_to_p = rec_thr_point.azimuth(thr_point)
      wsz_features_to_add = []
      success_p, success_r = False, False
      
      try: # Primary End
        geom_primary = self._create_offset_rectangle(
          thr_point,
          azimuth_p_to_r, # Outward Azimuth
          GUIDELINE_B_FAR_EDGE_OFFSET,
          GUIDELINE_B_ZONE_LENGTH_BACKWARD,
          GUIDELINE_B_ZONE_HALF_WIDTH, # ### FIX: Removed '/ 2.0'
          f"End {primary_desig}"
        )
        if geom_primary:
          feat = QgsFeature(fields); feat.setGeometry(geom_primary); feat.setAttributes([runway_name, "Windshear Assessment", primary_desig])
          wsz_features_to_add.append(feat); success_p = True
      except Exception as e_p: QgsMessageLog.logMessage(f"Error primary WSZ for {runway_name}: {e_p}", PLUGIN_TAG, level=Qgis.Warning)
      
      try: # Reciprocal End
        geom_reciprocal = self._create_offset_rectangle(
          rec_thr_point,
          azimuth_r_to_p, # Outward Azimuth
          GUIDELINE_B_FAR_EDGE_OFFSET,
          GUIDELINE_B_ZONE_LENGTH_BACKWARD,
          GUIDELINE_B_ZONE_HALF_WIDTH, # ### FIX: Removed '/ 2.0'
          f"End {reciprocal_desig}"
        )
        if geom_reciprocal:
          feat = QgsFeature(fields); feat.setGeometry(geom_reciprocal); feat.setAttributes([runway_name, "Windshear Assessment", reciprocal_desig])
          wsz_features_to_add.append(feat); success_r = True
      except Exception as e_r: QgsMessageLog.logMessage(f"Error reciprocal WSZ for {runway_name}: {e_r}", PLUGIN_TAG, level=Qgis.Warning)
      
      # (Rest of the function remains the same - committing layer etc.)
      if wsz_features_to_add:
        wsz_layer.startEditing()
        flag, _ = provider.addFeatures(wsz_features_to_add)
        if flag and wsz_layer.commitChanges():
          wsz_layer.updateExtents(); project.addMapLayer(wsz_layer, False)
          node = layer_group.addLayer(wsz_layer);
          if node: node.setName(layer_display_name)
          return True # Return True if layer committed
        else: wsz_layer.rollBack(); QgsMessageLog.logMessage(f"Failed commit WSZ layer {layer_name_internal}", PLUGIN_TAG, level=Qgis.Warning); return False
      else: return False # No features added
      
    def process_guideline_c(self, arp_point: QgsPointXY, icao_code: str, target_crs: QgsCoordinateReferenceSystem, layer_group: QgsLayerTreeGroup) -> bool:
        """Processes Guideline C: Wildlife Management Zone."""
        # QgsMessageLog.logMessage(f"Guideline C processing for {icao_code}", PLUGIN_TAG, level=Qgis.Info)
        if not all([arp_point, icao_code, target_crs, target_crs.isValid(), layer_group]): return False
        success_flag = False; project = QgsProject.instance()
        try:
            arp_geom = QgsGeometry.fromPointXY(arp_point);
            if arp_geom.isNull(): return False
            geom_a_full = arp_geom.buffer(GUIDELINE_C_RADIUS_A_M, GUIDELINE_C_BUFFER_SEGMENTS)
            geom_b_full = arp_geom.buffer(GUIDELINE_C_RADIUS_B_M, GUIDELINE_C_BUFFER_SEGMENTS)
            geom_c_full = arp_geom.buffer(GUIDELINE_C_RADIUS_C_M, GUIDELINE_C_BUFFER_SEGMENTS)
            if not geom_a_full or geom_a_full.isEmpty() or not geom_a_full.isGeosValid(): geom_a_full = None
            if not geom_b_full or geom_b_full.isEmpty() or not geom_b_full.isGeosValid(): geom_b_full = None
            if not geom_c_full or geom_c_full.isEmpty() or not geom_c_full.isGeosValid(): geom_c_full = None
            geom_a_final = geom_a_full; geom_b_final = None; geom_c_final = None
            if geom_b_full and geom_a_full: diff = geom_b_full.difference(geom_a_full); geom_b_final = diff if diff and not diff.isEmpty() and diff.isGeosValid() else None
            elif geom_b_full: geom_b_final = geom_b_full
            if geom_c_full and geom_b_full: diff = geom_c_full.difference(geom_b_full); geom_c_final = diff if diff and not diff.isEmpty() and diff.isGeosValid() else None
            elif geom_c_full: geom_c_final = geom_c_full

            def create_wzm_layer(zone_letter: str, geom: Optional[QgsGeometry], desc: str, inner_r_km: float, outer_r_km: float) -> bool:
                nonlocal success_flag;
                if not geom: return False
                layer_name_internal = f"WMZ_{zone_letter}_{icao_code}_{id(self)}"; layer_display_name = f"{self.tr('WMZ')} {zone_letter} ({inner_r_km:.0f}-{outer_r_km:.0f}km)"
                layer = QgsVectorLayer(f"Polygon?crs={target_crs.authid()}", layer_name_internal, "memory");
                if not layer.isValid(): return False
                provider = layer.dataProvider(); fields = QgsFields()
                fields.append(QgsField("Zone", QVariant.String)); fields.append(QgsField("Desc", QVariant.String)); fields.append(QgsField("InnerKm", QVariant.Double)); fields.append(QgsField("OuterKm", QVariant.Double))
                provider.addAttributes(fields); layer.updateFields()
                feature = QgsFeature(fields); feature.setGeometry(geom); feature.setAttributes([f"Area {zone_letter}", desc, inner_r_km, outer_r_km])
                layer.startEditing(); flag, _ = provider.addFeatures([feature])
                if flag and layer.commitChanges(): layer.updateExtents(); project.addMapLayer(layer, False); node = layer_group.addLayer(layer); node.setName(layer_display_name) if node else None; success_flag = True; return True
                else: layer.rollBack(); QgsMessageLog.logMessage(f"Failed commit WMZ {zone_letter} layer", PLUGIN_TAG, level=Qgis.Warning); return False

            create_wzm_layer("A", geom_a_final, self.tr("0-3km"), 0.0, GUIDELINE_C_RADIUS_A_M / 1000.0)
            create_wzm_layer("B", geom_b_final, self.tr("3-8km"), GUIDELINE_C_RADIUS_A_M / 1000.0, GUIDELINE_C_RADIUS_B_M / 1000.0)
            create_wzm_layer("C", geom_c_final, self.tr("8-13km"), GUIDELINE_C_RADIUS_B_M / 1000.0, GUIDELINE_C_RADIUS_C_M / 1000.0)
            return success_flag
        except Exception as e: QgsMessageLog.logMessage(f"Error Guideline C processing: {e}", PLUGIN_TAG, level=Qgis.Critical); return False

    def process_guideline_e(self, runway_data: dict, layer_group: QgsLayerTreeGroup) -> bool:
        """Processes Guideline E: Lighting Control Zone (Clipped Rectangles)."""
        runway_name = runway_data.get('short_name', f"RWY_{runway_data.get('index','?')}")
        # QgsMessageLog.logMessage(f"Guideline E processing for {runway_name}", PLUGIN_TAG, level=Qgis.Info)
        thr_point = runway_data.get('thr_point'); rec_thr_point = runway_data.get('rec_thr_point')
        target_crs = runway_data.get('target_crs'); project = QgsProject.instance()
        if not all([thr_point, rec_thr_point, target_crs, project, layer_group]): return False
        full_geoms: Dict[str, Optional[QgsGeometry]] = {}; final_geoms: Dict[str, Optional[QgsGeometry]] = {}; success_flag = False
        try:
            for zone_id in GUIDELINE_E_ZONE_ORDER:
                params = GUIDELINE_E_ZONE_PARAMS[zone_id]; desc = f"LCZ Full {zone_id} RWY {runway_name}"
                geom = self._create_runway_aligned_rectangle(thr_point, rec_thr_point, params['ext'], params['half_w'], desc)
                full_geoms[zone_id] = geom
            final_geoms['A'] = full_geoms.get('A'); geom_prev = final_geoms['A']
            for zone_id in GUIDELINE_E_ZONE_ORDER[1:]:
                 geom_curr = full_geoms.get(zone_id)
                 if geom_curr and geom_prev: diff = geom_curr.difference(geom_prev); final_geoms[zone_id] = diff if diff and not diff.isEmpty() and diff.isGeosValid() else None
                 elif geom_curr: final_geoms[zone_id] = geom_curr
                 else: final_geoms[zone_id] = None
                 geom_prev = geom_curr if geom_curr else geom_prev

            def create_lcz_layer(zone_id: str, geom: Optional[QgsGeometry]) -> bool:
                nonlocal success_flag;
                if not geom: return False
                params = GUIDELINE_E_ZONE_PARAMS[zone_id]; layer_name_internal = f"LCZ_{zone_id}_{runway_name.replace('/', '_')}_{id(self)}"; layer_display_name = f"{self.tr('LCZ')} {zone_id} {runway_name}"
                layer = QgsVectorLayer(f"Polygon?crs={target_crs.authid()}", layer_name_internal, "memory");
                if not layer.isValid(): return False
                provider = layer.dataProvider(); fields = QgsFields()
                fields.append(QgsField("RWY", QVariant.String)); fields.append(QgsField("Zone", QVariant.String)); fields.append(QgsField("Desc", QVariant.String)); fields.append(QgsField("Ext_m", QVariant.Double)); fields.append(QgsField("HW_m", QVariant.Double))
                provider.addAttributes(fields); layer.updateFields()
                feature = QgsFeature(fields); feature.setGeometry(geom); feature.setAttributes([runway_name, zone_id, params['desc'], params['ext'], params['half_w']])
                layer.startEditing(); flag, _ = provider.addFeatures([feature])
                if flag and layer.commitChanges(): layer.updateExtents(); project.addMapLayer(layer, False); node = layer_group.addLayer(layer); node.setName(layer_display_name) if node else None; success_flag = True; return True
                else: layer.rollBack(); QgsMessageLog.logMessage(f"Failed commit LCZ {zone_id} layer", PLUGIN_TAG, level=Qgis.Warning); return False
            for zone_id in GUIDELINE_E_ZONE_ORDER: create_lcz_layer(zone_id, final_geoms.get(zone_id))
            return success_flag
        except Exception as e: QgsMessageLog.logMessage(f"Error Guideline E processing for {runway_name}: {e}", PLUGIN_TAG, level=Qgis.Critical); return False

    def process_guideline_f(self, runway_data: dict, layer_group: QgsLayerTreeGroup) -> bool:
        """Placeholder for Guideline F: Protected Airspace processing."""
        # QgsMessageLog.logMessage(f"Guideline F (placeholder) for {runway_data['short_name']}", PLUGIN_TAG, level=Qgis.Info)
        # TODO: Implement OLS / PANS-OPS surfaces
        return False

    def process_guideline_g(self, runway_data: dict, layer_group: QgsLayerTreeGroup) -> bool:
        """Placeholder for Guideline G: CNS Facilities processing."""
        # QgsMessageLog.logMessage(f"Guideline G (placeholder) for {runway_data['short_name']}", PLUGIN_TAG, level=Qgis.Info)
        # TODO: Implement CNS protection zones
        return False

    def process_guideline_i(self, runway_data: dict, layer_group: QgsLayerTreeGroup) -> bool:
        """Processes Guideline I: Public Safety Area (PSA) Trapezoids."""
        runway_name = runway_data.get('short_name', f"RWY_{runway_data.get('index','?')}")
        # QgsMessageLog.logMessage(f"Guideline I processing for {runway_name}", PLUGIN_TAG, level=Qgis.Info)
        thr_point = runway_data.get('thr_point'); rec_thr_point = runway_data.get('rec_thr_point')
        target_crs = runway_data.get('target_crs'); project = QgsProject.instance()
        if not all([thr_point, rec_thr_point, target_crs, project, layer_group]): return False

        # Use constants, calculate half-widths
        psa_inner_half_w = GUIDELINE_I_PSA_INNER_WIDTH / 2.0
        psa_outer_half_w = GUIDELINE_I_PSA_OUTER_WIDTH / 2.0

        layer_name_internal = f"PSA_{runway_name.replace('/', '_')}_{id(self)}"; layer_display_name = f"PSA {self.tr('Runway')} {runway_name}"
        psa_layer = QgsVectorLayer(f"Polygon?crs={target_crs.authid()}", layer_name_internal, "memory")
        if not psa_layer.isValid(): return False

        provider = psa_layer.dataProvider(); fields = QgsFields()
        fields.append(QgsField("RWY", QVariant.String)); fields.append(QgsField("Zone", QVariant.String)); fields.append(QgsField("End", QVariant.String)); fields.append(QgsField("Len", QVariant.Double)); fields.append(QgsField("InW", QVariant.Double)); fields.append(QgsField("OutW", QVariant.Double))
        provider.addAttributes(fields); psa_layer.updateFields()

        psa_features_to_add = []; success_p, success_r = False, False
        try:
            primary_desig = runway_name.split('/')[0]; reciprocal_desig = runway_name.split('/')[-1]
            azimuth_p_to_r = thr_point.azimuth(rec_thr_point); azimuth_r_to_p = rec_thr_point.azimuth(thr_point)
        except (IndexError, AttributeError, TypeError) as e: QgsMessageLog.logMessage(f"Guideline I skipped for {runway_name}: Azimuth/Desig error: {e}", PLUGIN_TAG, level=Qgis.Warning); return False

        try: # Primary End
            geom_primary = self._create_trapezoid(thr_point, azimuth_r_to_p, GUIDELINE_I_PSA_LENGTH, psa_inner_half_w, psa_outer_half_w, f"PSA End {primary_desig}")
            if geom_primary:
                feat = QgsFeature(fields); feat.setGeometry(geom_primary); feat.setAttributes([runway_name, "PSA", primary_desig, GUIDELINE_I_PSA_LENGTH, GUIDELINE_I_PSA_INNER_WIDTH, GUIDELINE_I_PSA_OUTER_WIDTH])
                psa_features_to_add.append(feat); success_p = True
        except Exception as e_p: QgsMessageLog.logMessage(f"Error primary PSA for {runway_name}: {e_p}", PLUGIN_TAG, level=Qgis.Warning)
        try: # Reciprocal End
            geom_reciprocal = self._create_trapezoid(rec_thr_point, azimuth_p_to_r, GUIDELINE_I_PSA_LENGTH, psa_inner_half_w, psa_outer_half_w, f"PSA End {reciprocal_desig}")
            if geom_reciprocal:
                feat = QgsFeature(fields); feat.setGeometry(geom_reciprocal); feat.setAttributes([runway_name, "PSA", reciprocal_desig, GUIDELINE_I_PSA_LENGTH, GUIDELINE_I_PSA_INNER_WIDTH, GUIDELINE_I_PSA_OUTER_WIDTH])
                psa_features_to_add.append(feat); success_r = True
        except Exception as e_r: QgsMessageLog.logMessage(f"Error reciprocal PSA for {runway_name}: {e_r}", PLUGIN_TAG, level=Qgis.Warning)

        if psa_features_to_add:
            psa_layer.startEditing()
            flag, _ = provider.addFeatures(psa_features_to_add)
            if flag and psa_layer.commitChanges():
                psa_layer.updateExtents(); project.addMapLayer(psa_layer, False)
                node = layer_group.addLayer(psa_layer); node.setName(layer_display_name) if node else None
                return True # Return True if layer committed
            else: psa_layer.rollBack(); QgsMessageLog.logMessage(f"Failed commit PSA layer {layer_name_internal}", PLUGIN_TAG, level=Qgis.Warning); return False
        else: return False # No features added

# ============================================================
# End of Plugin Class
# ============================================================