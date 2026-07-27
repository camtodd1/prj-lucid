"""CNS facility table setup, row handling, and validation."""

from typing import Any, Dict, List, Optional

from qgis.core import (  # type: ignore
    QgsGeometry,
    QgsPointXY,
    QgsProject,
    Qgis,
)
from qgis.PyQt import QtCore, QtWidgets  # type: ignore
from qgis.PyQt.QtWidgets import (  # type: ignore
    QAbstractItemView,
    QComboBox,
    QMessageBox,
    QTableWidgetItem,
)

from .dialog_constants import DIALOG_LOG_TAG

try:
    from ..core.run_log import QgsMessageLog
except ImportError:
    from core.run_log import QgsMessageLog  # type: ignore


CNS_FACILITY_TYPES = [
    "High Frequency (HF) Transmit Site",
    "High Frequency (HF) Receiver Site",
    "Very High Frequency (VHF)",
    "Satellite Ground Station (SGS)",
    "Non-Directional Beacon (NDB)",
    "Distance Measuring Equipment (DME)",
    "VHF Omni-Directional Range (VOR)",
    "Conventional VHF Omni-Directional Range (CVOR)",
    "Elevated Counterpoise Conventional VHF Omni-Directional Range (CVOR)",
    "Doppler VHF Omni-Directional Range (DVOR) - Elevated",
    "Doppler VHF Omni-Directional Range (DVOR) - Ground Mounted",
    "Middle and Outer Marker Beacon",
    "Automatic Dependent Surveillance Broadcast (ADS-B)",
    "Wide Area Multilateration (WAM)",
    "Primary Surveillance Radar (PSR)",
    "Secondary Surveillance Radar (SSR)",
    "Ground Based Augmentation System (GBAS) - RSMU",
    "GBAS - VDB",
    "Radio Link",
    "Radar Site Monitor - Type A",
    "Radar Site Monitor - Type B",
]

CNS_CONTOUR_DEFAULT_PRIMARY_INTERVAL = 10.0
CNS_CONTOUR_DEFAULT_INTERMEDIATE_INTERVAL = 5.0


class CnsTableMixin:
    """Mixin for CNS manual-entry table behaviour."""

    def _setup_cns_manual_entry(self):
        cns_table = getattr(
            self,
            "table_cns_facility",
            self.findChild(QtWidgets.QTableWidget, "table_cns_facility"),
        )
        add_button = getattr(
            self,
            "pushButton_add_CNS",
            self.findChild(QtWidgets.QPushButton, "pushButton_add_CNS"),
        )
        remove_button = getattr(
            self,
            "pushButton_remove_CNS",
            self.findChild(QtWidgets.QPushButton, "pushButton_remove_CNS"),
        )

        if not all([cns_table, add_button, remove_button]):
            QgsMessageLog.logMessage(
                "Critical: CNS Manual Entry setup failed - widgets missing.",
                DIALOG_LOG_TAG,
                level=Qgis.Critical,
            )
            return

        self._style_cns_panel()
        cns_tab_layout = getattr(self, "verticalLayout_cnsTab", None)
        if isinstance(cns_tab_layout, QtWidgets.QVBoxLayout):
            cns_tab_layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignTop)

        cns_table.setColumnCount(5)
        cns_table.setHorizontalHeaderLabels(["Facility Type", "Easting", "Northing", "Elev (AMSL)", "Link ID"])
        cns_table.setAlternatingRowColors(True)
        cns_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        cns_table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        cns_table.setEditTriggers(
            QAbstractItemView.EditTrigger.DoubleClicked
            | QAbstractItemView.EditTrigger.EditKeyPressed
            | QAbstractItemView.EditTrigger.AnyKeyPressed
        )
        header = cns_table.horizontalHeader()
        if header:
            header.setStretchLastSection(False)
            header.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.Stretch)
            header.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeMode.Interactive)
            header.setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeMode.Interactive)
            header.setSectionResizeMode(3, QtWidgets.QHeaderView.ResizeMode.Interactive)
            cns_table.setColumnWidth(1, 140)
            cns_table.setColumnWidth(2, 140)
            cns_table.setColumnWidth(3, 110)
            cns_table.setColumnWidth(4, 120)

        cns_table.setMinimumHeight(168)
        cns_table.setMaximumHeight(168)
        cns_table.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding,
            QtWidgets.QSizePolicy.Policy.Fixed,
        )
        self._setup_cns_contour_controls()

        selection_model = cns_table.selectionModel()
        if selection_model is not None:
            selection_model.selectionChanged.connect(lambda *_: self._update_cns_view_state())
        cns_table.itemSelectionChanged.connect(self._update_cns_view_state)
        if cns_table.model() is not None:
            cns_table.model().rowsInserted.connect(lambda *_: self._update_cns_view_state())
            cns_table.model().rowsRemoved.connect(lambda *_: self._update_cns_view_state())

        add_button.clicked.connect(self.add_cns_row)
        remove_button.clicked.connect(self.remove_cns_rows)
        add_button.setToolTip("Add a new row to enter a CNS facility manually.")
        remove_button.setToolTip("Remove the selected CNS facility row(s).")
        add_button.setAutoDefault(False)
        add_button.setDefault(False)
        add_button.setMinimumWidth(130)
        add_button.setMaximumWidth(170)
        remove_button.setMinimumWidth(140)
        remove_button.setMaximumWidth(180)
        button_layout = getattr(self, "horizontalLayout_cnsButtons", None)
        if isinstance(button_layout, QtWidgets.QHBoxLayout):
            button_layout.insertStretch(0, 1)
        self.CNS_FACILITY_TYPES = CNS_FACILITY_TYPES
        self._update_cns_view_state()

    def _setup_cns_contour_controls(self):
        """Add shared primary and intermediate contour controls for CNS slope layers."""
        controls = getattr(self, "widgetCnsContourIntervals", None)
        if controls is None:
            group_layout = getattr(self, "verticalLayout_6", None)
            if not isinstance(group_layout, QtWidgets.QVBoxLayout):
                return
            controls = QtWidgets.QWidget(self)
            controls.setObjectName("widgetCnsContourIntervals")
            layout = QtWidgets.QHBoxLayout(controls)
            layout.setContentsMargins(0, 2, 0, 2)
            layout.setSpacing(8)
            title = QtWidgets.QLabel("CNS contour intervals", controls)
            primary_label = QtWidgets.QLabel("Primary", controls)
            intermediate_label = QtWidgets.QLabel("Intermediate", controls)
            primary = QtWidgets.QDoubleSpinBox(controls)
            primary.setObjectName("doubleSpinBoxCnsContourPrimary")
            intermediate = QtWidgets.QDoubleSpinBox(controls)
            intermediate.setObjectName("doubleSpinBoxCnsContourIntermediate")
            for spinbox, default in (
                (primary, CNS_CONTOUR_DEFAULT_PRIMARY_INTERVAL),
                (intermediate, CNS_CONTOUR_DEFAULT_INTERMEDIATE_INTERVAL),
            ):
                spinbox.setRange(0.1, 1000.0)
                spinbox.setDecimals(1)
                spinbox.setSingleStep(1.0)
                spinbox.setSuffix(" m")
                spinbox.setValue(default)
                spinbox.setMinimumWidth(92)
            primary.setToolTip("Major CNS contour interval applied to every sloped CNS surface.")
            intermediate.setToolTip("Regular CNS contour interval applied to every sloped CNS surface.")
            layout.addWidget(title)
            layout.addStretch(1)
            layout.addWidget(primary_label)
            layout.addWidget(primary)
            layout.addWidget(intermediate_label)
            layout.addWidget(intermediate)
            group_layout.insertWidget(1, controls)
            self.widgetCnsContourIntervals = controls
            self.doubleSpinBoxCnsContourPrimary = primary
            self.doubleSpinBoxCnsContourIntermediate = intermediate
        primary = getattr(self, "doubleSpinBoxCnsContourPrimary", None)
        intermediate = getattr(self, "doubleSpinBoxCnsContourIntermediate", None)
        for spinbox in (primary, intermediate):
            if spinbox is not None:
                spinbox.valueChanged.connect(self._on_cns_contour_interval_changed)

    def _on_cns_contour_interval_changed(self):
        if hasattr(self, "update_dialog_status"):
            self.update_dialog_status()

    def get_cns_contour_interval_options(self) -> Dict[str, float]:
        primary = getattr(self, "doubleSpinBoxCnsContourPrimary", None)
        intermediate = getattr(self, "doubleSpinBoxCnsContourIntermediate", None)
        return {
            "primary": primary.value() if primary is not None else CNS_CONTOUR_DEFAULT_PRIMARY_INTERVAL,
            "intermediate": intermediate.value() if intermediate is not None else CNS_CONTOUR_DEFAULT_INTERMEDIATE_INTERVAL,
        }

    def set_cns_contour_interval_options(self, options) -> None:
        options = options if isinstance(options, dict) else {}
        for name, default in (
            ("primary", CNS_CONTOUR_DEFAULT_PRIMARY_INTERVAL),
            ("intermediate", CNS_CONTOUR_DEFAULT_INTERMEDIATE_INTERVAL),
        ):
            try:
                value = float(options.get(name, default))
            except (TypeError, ValueError):
                value = default
            spinbox = getattr(self, f"doubleSpinBoxCnsContour{name.title()}", None)
            if spinbox is not None:
                spinbox.setValue(value if value > 0 else default)

    def _style_cns_panel(self):
        description = getattr(self, "label_CNS_description", self.findChild(QtWidgets.QLabel, "label_CNS_description"))
        if description:
            description.setStyleSheet("color: #666666; font-size: 11px;")

        table = getattr(self, "table_cns_facility", self.findChild(QtWidgets.QTableWidget, "table_cns_facility"))
        if table:
            table.setStyleSheet(
                """
                QTableWidget {
                    border: 1px solid #e2e2e2;
                    border-radius: 4px;
                    gridline-color: #ececec;
                    background: #ffffff;
                }
                QHeaderView::section {
                    background: #fafafa;
                    padding: 5px 8px;
                    border: 0px;
                    border-bottom: 1px solid #d5d5d5;
                    font-weight: 600;
                }
                """
            )

    def _update_cns_view_state(self):
        cns_table = getattr(self, "table_cns_facility", self.findChild(QtWidgets.QTableWidget, "table_cns_facility"))
        status_label = getattr(self, "label_cns_status", self.findChild(QtWidgets.QLabel, "label_cns_status"))
        remove_button = getattr(self, "pushButton_remove_CNS", self.findChild(QtWidgets.QPushButton, "pushButton_remove_CNS"))
        if cns_table is None:
            return

        row_count = cns_table.rowCount()
        selected_rows = cns_table.selectionModel().selectedRows() if cns_table.selectionModel() else []
        status_helper = getattr(self, "_set_small_status_chip", None)
        if callable(status_helper):
            status_helper(
                "label_cns_status",
                f"CNS facilities: {row_count}" if row_count else "CNS facilities: none",
                "ready" if row_count else "neutral",
            )
        elif status_label:
            status_label.setText(f"CNS facilities: {row_count}" if row_count else "CNS facilities: none")

        if remove_button is not None:
            remove_button.setEnabled(bool(selected_rows))

        header_height = cns_table.horizontalHeader().height() if cns_table.horizontalHeader() else 28
        row_heights = sum(cns_table.rowHeight(row) for row in range(row_count))
        target_height = header_height + row_heights + 10
        if row_count == 0:
            target_height = 168
        else:
            target_height = min(max(target_height, 168), 320)
        cns_table.setMinimumHeight(target_height)
        cns_table.setMaximumHeight(target_height)

    def add_cns_row(self):
        cns_table = self._get_cns_table("Add CNS Row Error")
        if not cns_table:
            return

        if not hasattr(self, "CNS_FACILITY_TYPES") or not self.CNS_FACILITY_TYPES:
            QgsMessageLog.logMessage(
                "Add CNS Row Error: CNS_FACILITY_TYPES list not defined.",
                DIALOG_LOG_TAG,
                level=Qgis.Critical,
            )
            QMessageBox.critical(
                self,
                "Configuration Error",
                "Cannot add CNS row: Facility types list is missing.",
            )
            return

        try:
            row_position = cns_table.rowCount()
            cns_table.insertRow(row_position)

            combo_type = QComboBox()
            combo_type.setObjectName(f"cnsComboType_{row_position}")
            combo_type.addItems([""] + self.CNS_FACILITY_TYPES)
            combo_type.setCurrentIndex(0)
            combo_type.setToolTip("Select the type of CNS facility.")
            combo_type.currentIndexChanged.connect(self._update_cns_view_state)
            if hasattr(self, "update_dialog_status"):
                combo_type.currentIndexChanged.connect(self.update_dialog_status)
            cns_table.setCellWidget(row_position, 0, combo_type)

            item_x = QTableWidgetItem("")
            item_x.setToolTip("Enter Easting or X coordinate (in Project CRS).")
            cns_table.setItem(row_position, 1, item_x)

            item_y = QTableWidgetItem("")
            item_y.setToolTip("Enter Northing or Y coordinate (in Project CRS).")
            cns_table.setItem(row_position, 2, item_y)

            item_elev = QTableWidgetItem("")
            item_elev.setToolTip("Enter Elevation AMSL (Optional). Leave blank if unknown.")
            cns_table.setItem(row_position, 3, item_elev)

            item_link_id = QTableWidgetItem("")
            item_link_id.setToolTip("Required for Radio Link endpoints. Enter the same Link ID for both dishes.")
            cns_table.setItem(row_position, 4, item_link_id)

            cns_table.scrollToItem(item_x, QAbstractItemView.ScrollHint.EnsureVisible)
            combo_type.setFocus()
            self._update_cns_view_state()
            self._update_dialog_height()
            if hasattr(self, "update_dialog_status"):
                self.update_dialog_status()
        except Exception as e:
            QgsMessageLog.logMessage(
                f"Add CNS Row Error during row/widget creation: {e}",
                DIALOG_LOG_TAG,
                level=Qgis.Critical,
            )
            QMessageBox.critical(self, "Error", f"Failed to add CNS row:\n{e}")

    def remove_cns_rows(self):
        cns_table = self._get_cns_table("Remove CNS Row Error")
        if not cns_table:
            return

        selected_indices = cns_table.selectionModel().selectedRows()
        if not selected_indices:
            QMessageBox.information(
                self,
                self.tr("Remove Rows"),
                self.tr("No CNS facility rows selected to remove."),
            )
            return

        selected_rows = sorted([index.row() for index in selected_indices], reverse=True)
        reply = QMessageBox.question(
            self,
            self.tr("Confirm Removal"),
            self.tr("Are you sure you want to remove the {n} selected CNS facility row(s)?").format(
                n=len(selected_rows)
            ),
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No,
            QtWidgets.QMessageBox.StandardButton.No,
        )

        if reply == QtWidgets.QMessageBox.StandardButton.Yes:
            try:
                for row_index in selected_rows:
                    cns_table.removeRow(row_index)
                self._update_cns_view_state()
                self._update_dialog_height()
                if hasattr(self, "update_dialog_status"):
                    self.update_dialog_status()
            except Exception as e:
                QgsMessageLog.logMessage(
                    f"Remove CNS Row Error during row removal: {e}",
                    DIALOG_LOG_TAG,
                    level=Qgis.Critical,
                )
                QMessageBox.critical(self, "Error", f"Failed to remove CNS rows:\n{e}")

    def _get_cns_manual_data(self) -> Optional[List[Dict[str, Any]]]:
        cns_facilities_data = []
        cns_table = self._get_cns_table("CNS Validation Error")
        if not cns_table:
            QMessageBox.critical(self, "UI Error", "Cannot find CNS table.")
            return None

        project_crs = QgsProject.instance().crs()
        if not project_crs or not project_crs.isValid():
            QgsMessageLog.logMessage(
                "CNS Validation Error: Invalid Project CRS.",
                DIALOG_LOG_TAG,
                level=Qgis.Critical,
            )
            QMessageBox.critical(
                self,
                "CRS Error",
                "Project CRS is invalid. Cannot process CNS coordinates.",
            )
            return None

        skipped_rows, rows_with_errors, total_rows = 0, 0, cns_table.rowCount()
        for row in range(total_rows):
            row_data = self._read_cns_row(cns_table, row)
            if row_data.get("valid"):
                cns_facilities_data.append(row_data["facility"])
            elif row_data.get("error"):
                rows_with_errors += 1
                skipped_rows += 1
            else:
                skipped_rows += 1

        cns_facilities_data, invalid_radio_link_rows = self._exclude_unpaired_radio_links(cns_facilities_data)
        if invalid_radio_link_rows:
            rows_with_errors += invalid_radio_link_rows
            skipped_rows += invalid_radio_link_rows

        self._show_cns_skip_message(rows_with_errors, skipped_rows, total_rows)
        return cns_facilities_data

    def _exclude_unpaired_radio_links(self, facilities: List[Dict[str, Any]]) -> tuple[List[Dict[str, Any]], int]:
        """Omit radio-link endpoints unless exactly two rows share a Link ID."""
        grouped: Dict[str, List[Dict[str, Any]]] = {}
        for facility in facilities:
            if facility.get("type") == "Radio Link":
                grouped.setdefault(str(facility.get("link_id", "")).strip(), []).append(facility)
        invalid_ids = {link_id for link_id, endpoints in grouped.items() if not link_id or len(endpoints) != 2}
        if not invalid_ids:
            return facilities, 0
        for link_id in sorted(invalid_ids):
            QgsMessageLog.logMessage(
                f"Radio Link '{link_id or '(missing Link ID)'}' requires exactly two endpoints; skipped.",
                DIALOG_LOG_TAG,
                level=Qgis.Warning,
            )
        retained = [
            facility
            for facility in facilities
            if facility.get("type") != "Radio Link" or str(facility.get("link_id", "")).strip() not in invalid_ids
        ]
        return retained, sum(len(grouped[link_id]) for link_id in invalid_ids)

    def _read_cns_row(self, cns_table, row: int) -> Dict[str, Any]:
        facility_type = ""
        facility_elevation: Optional[float] = None
        point_geom_project_crs: Optional[QgsGeometry] = None
        valid_row = True
        error_in_row = False
        try:
            combo_box = cns_table.cellWidget(row, 0)
            if isinstance(combo_box, QComboBox) and combo_box.currentIndex() > 0 and combo_box.currentText():
                facility_type = combo_box.currentText()
            else:
                valid_row = False

            if valid_row:
                x_item, y_item = cns_table.item(row, 1), cns_table.item(row, 2)
                x_str = x_item.text().strip() if x_item else ""
                y_str = y_item.text().strip() if y_item else ""
                if not x_str or not y_str:
                    valid_row = False
                else:
                    try:
                        point_xy = QgsPointXY(float(x_str), float(y_str))
                        point_geom_project_crs = QgsGeometry.fromPointXY(point_xy)
                        if point_geom_project_crs.isNull():
                            valid_row = False
                            error_in_row = True
                            self._log_cns_row_warning(row, "Null geom.")
                    except ValueError:
                        valid_row = False
                        error_in_row = True
                        self._log_cns_row_warning(row, "Invalid coords.")

            if valid_row:
                elev_item = cns_table.item(row, 3)
                elev_str = elev_item.text().strip() if elev_item else ""
                if elev_str:
                    try:
                        facility_elevation = float(elev_str)
                    except ValueError:
                        error_in_row = True
                        self._log_cns_row_warning(row, "Invalid elev, ignoring.")

            link_id = ""
            if valid_row:
                link_item = cns_table.item(row, 4)
                link_id = link_item.text().strip() if link_item else ""
                if facility_type == "Radio Link" and not link_id:
                    valid_row = False
                    error_in_row = True
                    self._log_cns_row_warning(row, "Radio Link requires a Link ID shared by both endpoints.")
        except Exception as e:
            valid_row = False
            error_in_row = True
            QgsMessageLog.logMessage(f"CNS Row {row+1} Error: {e}", DIALOG_LOG_TAG, level=Qgis.Critical)

        if valid_row and point_geom_project_crs:
            safe_type = facility_type.replace(" ", "_").replace("-", "").replace("(", "").replace(")", "")
            return {
                "valid": True,
                "facility": {
                    "id": f"Manual_{row+1}_{safe_type}"[:50],
                    "type": facility_type,
                    "geom": point_geom_project_crs,
                    "elevation": facility_elevation,
                    "link_id": link_id,
                    "params": {},
                },
            }
        return {"valid": False, "error": error_in_row}

    def _show_cns_skip_message(self, rows_with_errors: int, skipped_rows: int, total_rows: int) -> None:
        if rows_with_errors > 0:
            QMessageBox.warning(
                self,
                "CNS Data Warning",
                (
                    f"{rows_with_errors} CNS row(s) had errors/invalid data and "
                    f"were skipped or data ignored.\n({skipped_rows} total "
                    "skipped/incomplete). Check Log."
                ),
            )
        elif skipped_rows > 0 and skipped_rows == total_rows and total_rows > 0:
            QMessageBox.information(self, "CNS Data Info", "All CNS rows skipped (missing required data).")
        elif skipped_rows > 0:
            QMessageBox.information(
                self,
                "CNS Data Info",
                f"{skipped_rows} CNS rows skipped (missing required data).",
            )

    def _get_cns_table(self, context: str):
        cns_table = getattr(
            self,
            "table_cns_facility",
            self.findChild(QtWidgets.QTableWidget, "table_cns_facility"),
        )
        if not cns_table:
            QgsMessageLog.logMessage(
                f"{context}: Table widget 'table_cns_facility' not found.",
                DIALOG_LOG_TAG,
                level=Qgis.Critical,
            )
        return cns_table

    def _log_cns_row_warning(self, row: int, message: str) -> None:
        QgsMessageLog.logMessage(
            f"CNS Row {row+1}: {message}",
            DIALOG_LOG_TAG,
            level=Qgis.Warning,
        )
