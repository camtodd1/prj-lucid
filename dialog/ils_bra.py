"""ILS Building Restricted Area installation inputs."""

from typing import Any, Dict, List, Optional, Tuple

from qgis.core import QgsGeometry, QgsPointXY, QgsWkbTypes  # type: ignore
from qgis.PyQt import QtCore, QtWidgets  # type: ignore
from qgis.PyQt.QtWidgets import QAbstractItemView, QComboBox, QTableWidgetItem  # type: ignore


ILS_BRA_COMPONENTS: List[Tuple[str, str]] = [
    ("Glide path", "glide_path"),
    ("Localiser", "localiser"),
]


class IlsBraInputsMixin:
    """Manage optional ILS BRA rows and validate generation prerequisites."""

    def _setup_ils_bra_inputs(self) -> None:
        table = getattr(self, "table_ils_bra", None)
        add_button = getattr(self, "pushButton_add_ILS_BRA", None)
        remove_button = getattr(self, "pushButton_remove_ILS_BRA", None)
        if not all([table, add_button, remove_button]):
            return

        table.setColumnCount(8)
        table.setHorizontalHeaderLabels(
            [
                "Component",
                "Runway end",
                "Facility ID",
                "Easting",
                "Northing",
                "Ground elev (AMSL)",
                "VCA source / reference",
                "Vehicle critical area polygon (WKT)",
            ]
        )
        table.setAlternatingRowColors(True)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        table.setEditTriggers(
            QAbstractItemView.EditTrigger.DoubleClicked
            | QAbstractItemView.EditTrigger.EditKeyPressed
            | QAbstractItemView.EditTrigger.AnyKeyPressed
        )
        header = table.horizontalHeader()
        if header:
            for column in range(7):
                header.setSectionResizeMode(column, QtWidgets.QHeaderView.ResizeMode.Interactive)
            header.setSectionResizeMode(7, QtWidgets.QHeaderView.ResizeMode.Stretch)
        for column, width in enumerate([105, 170, 110, 105, 105, 125, 170]):
            table.setColumnWidth(column, width)
        table.setMinimumHeight(150)
        table.setMaximumHeight(260)
        table.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding,
            QtWidgets.QSizePolicy.Policy.Fixed,
        )
        table.setToolTip(
            "Vehicle critical area WKT must be a polygon in the current project CRS. "
            "Use an authority-approved polygon wherever one is available."
        )

        add_button.clicked.connect(self.add_ils_bra_row)
        remove_button.clicked.connect(self.remove_ils_bra_rows)
        add_button.setToolTip("Add a glide path or localiser installation.")
        remove_button.setToolTip("Remove the selected ILS installation row(s).")
        remove_button.setEnabled(False)
        table.itemSelectionChanged.connect(self._update_ils_bra_view_state)
        if table.model() is not None:
            table.model().rowsInserted.connect(lambda *_: self._update_ils_bra_view_state())
            table.model().rowsRemoved.connect(lambda *_: self._update_ils_bra_view_state())

        description = getattr(self, "label_ils_bra_description", None)
        if description:
            description.setStyleSheet("color: #666666; font-size: 11px;")
        self._update_ils_bra_view_state()

    @staticmethod
    def _runway_designations(data: Dict[str, Any]) -> Tuple[str, str]:
        try:
            primary_number = int(str(data.get("designator_str", "")).strip())
            if not 1 <= primary_number <= 36:
                raise ValueError
            primary_suffix = str(data.get("suffix", "") or "").strip().upper()
            reciprocal_number = primary_number + 18 if primary_number <= 18 else primary_number - 18
            reciprocal_suffix = {"L": "R", "R": "L", "C": "C", "": ""}.get(primary_suffix, "")
            return (
                f"{primary_number:02d}{primary_suffix}",
                f"{reciprocal_number:02d}{reciprocal_suffix}",
            )
        except (TypeError, ValueError):
            return "primary", "reciprocal"

    def _ils_bra_runway_end_options(self) -> List[Tuple[str, str]]:
        options: List[Tuple[str, str]] = []
        for runway_index, group in sorted(getattr(self, "_runway_groups", {}).items()):
            primary, reciprocal = self._runway_designations(group.get_input_data())
            options.extend(
                [
                    (f"RWY {primary} approach end", f"{runway_index}:1"),
                    (f"RWY {reciprocal} approach end", f"{runway_index}:2"),
                ]
            )
        return options

    def _new_component_combo(self, selected: str = "") -> QComboBox:
        combo = QComboBox()
        combo.addItem("", "")
        for label, value in ILS_BRA_COMPONENTS:
            combo.addItem(label, value)
        index = combo.findData(selected)
        combo.setCurrentIndex(index if index >= 0 else 0)
        combo.currentIndexChanged.connect(self._update_ils_bra_view_state)
        return combo

    def _new_runway_end_combo(self, selected: str = "") -> QComboBox:
        combo = QComboBox()
        combo.addItem("", "")
        for label, value in self._ils_bra_runway_end_options():
            combo.addItem(label, value)
        index = combo.findData(selected)
        combo.setCurrentIndex(index if index >= 0 else 0)
        combo.currentIndexChanged.connect(self._update_ils_bra_view_state)
        return combo

    def refresh_ils_bra_runway_options(self) -> None:
        table = getattr(self, "table_ils_bra", None)
        if table is None:
            return
        for row in range(table.rowCount()):
            current = table.cellWidget(row, 1)
            selected = current.currentData() if isinstance(current, QComboBox) else ""
            table.setCellWidget(row, 1, self._new_runway_end_combo(str(selected or "")))

    def add_ils_bra_row(self, row_data: Optional[Dict[str, Any]] = None) -> None:
        table = getattr(self, "table_ils_bra", None)
        if table is None:
            return
        data = row_data if isinstance(row_data, dict) else {}
        row = table.rowCount()
        table.insertRow(row)
        table.setCellWidget(row, 0, self._new_component_combo(str(data.get("component", ""))))
        runway_ref = str(data.get("runway_ref", ""))
        if not runway_ref and data.get("runway_index") is not None and data.get("runway_end") is not None:
            runway_ref = f'{data.get("runway_index")}:{data.get("runway_end")}'
        table.setCellWidget(row, 1, self._new_runway_end_combo(runway_ref))
        values = [
            data.get("id", ""),
            data.get("easting", ""),
            data.get("northing", ""),
            data.get("ground_elevation", ""),
            data.get("vehicle_critical_area_source", ""),
            data.get("vehicle_critical_area_wkt", ""),
        ]
        for column, value in enumerate(values, start=2):
            table.setItem(row, column, QTableWidgetItem(str(value or "")))
        self._update_ils_bra_view_state()

    def remove_ils_bra_rows(self) -> None:
        table = getattr(self, "table_ils_bra", None)
        if table is None or table.selectionModel() is None:
            return
        rows = sorted({index.row() for index in table.selectionModel().selectedRows()}, reverse=True)
        for row in rows:
            table.removeRow(row)
        self._update_ils_bra_view_state()

    def _update_ils_bra_view_state(self) -> None:
        table = getattr(self, "table_ils_bra", None)
        if table is None:
            return
        row_count = table.rowCount()
        selected = table.selectionModel().selectedRows() if table.selectionModel() else []
        remove_button = getattr(self, "pushButton_remove_ILS_BRA", None)
        if remove_button:
            remove_button.setEnabled(bool(selected))
        status_helper = getattr(self, "_set_small_status_chip", None)
        if callable(status_helper):
            status_helper(
                "label_ils_bra_status",
                f"ILS installations: {row_count}" if row_count else "ILS installations: none",
                "ready" if row_count else "neutral",
            )
        else:
            status = getattr(self, "label_ils_bra_status", None)
            if status:
                status.setText(f"ILS installations: {row_count}" if row_count else "ILS installations: none")

    @staticmethod
    def _ils_bra_item_text(table, row: int, column: int) -> str:
        item = table.item(row, column)
        return item.text().strip() if item else ""

    def get_ils_bra_save_rows(self) -> List[Dict[str, Any]]:
        table = getattr(self, "table_ils_bra", None)
        if table is None:
            return []
        rows: List[Dict[str, Any]] = []
        for row in range(table.rowCount()):
            component = table.cellWidget(row, 0)
            runway = table.cellWidget(row, 1)
            runway_ref = str(runway.currentData() or "") if isinstance(runway, QComboBox) else ""
            runway_index, runway_end = self._split_runway_ref(runway_ref)
            rows.append(
                {
                    "component": str(component.currentData() or "") if isinstance(component, QComboBox) else "",
                    "runway_ref": runway_ref,
                    "runway_index": runway_index,
                    "runway_end": runway_end,
                    "id": self._ils_bra_item_text(table, row, 2),
                    "easting": self._ils_bra_item_text(table, row, 3),
                    "northing": self._ils_bra_item_text(table, row, 4),
                    "ground_elevation": self._ils_bra_item_text(table, row, 5),
                    "vehicle_critical_area_source": self._ils_bra_item_text(table, row, 6),
                    "vehicle_critical_area_wkt": self._ils_bra_item_text(table, row, 7),
                }
            )
        return rows

    @staticmethod
    def _split_runway_ref(runway_ref: str) -> Tuple[Optional[int], Optional[int]]:
        try:
            runway_index_text, runway_end_text = runway_ref.split(":", 1)
            runway_index = int(runway_index_text)
            runway_end = int(runway_end_text)
            if runway_end not in {1, 2}:
                raise ValueError
            return runway_index, runway_end
        except (AttributeError, TypeError, ValueError):
            return None, None

    def load_ils_bra_rows(self, loaded_rows: Any) -> None:
        table = getattr(self, "table_ils_bra", None)
        if table is None:
            return
        table.setRowCount(0)
        if isinstance(loaded_rows, list):
            for row_data in loaded_rows:
                if isinstance(row_data, dict):
                    self.add_ils_bra_row(row_data)
        self._update_ils_bra_view_state()

    def get_ils_bra_input_data(
        self,
        validated_runways: List[Dict[str, Any]],
        errors: List[str],
    ) -> List[Dict[str, Any]]:
        save_rows = self.get_ils_bra_save_rows()
        valid_runway_refs = {
            f'{runway.get("original_index")}:{end}'
            for runway in validated_runways
            for end in (1, 2)
        }
        installations: List[Dict[str, Any]] = []
        seen_ids = set()
        for row_number, row in enumerate(save_rows, start=1):
            values = [
                str(row.get(key, "") or "").strip()
                for key in (
                    "component",
                    "runway_ref",
                    "id",
                    "easting",
                    "northing",
                    "ground_elevation",
                    "vehicle_critical_area_source",
                    "vehicle_critical_area_wkt",
                )
            ]
            if not any(values):
                continue
            prefix = f"ILS BRA row {row_number}"
            component = str(row.get("component", ""))
            runway_ref = str(row.get("runway_ref", ""))
            facility_id = str(row.get("id", "")).strip()
            source = str(row.get("vehicle_critical_area_source", "")).strip()
            wkt = str(row.get("vehicle_critical_area_wkt", "")).strip()
            if component not in {value for _, value in ILS_BRA_COMPONENTS}:
                errors.append(f"{prefix}: select glide path or localiser.")
            if runway_ref not in valid_runway_refs:
                errors.append(f"{prefix}: select a valid runway approach end.")
            if not facility_id:
                errors.append(f"{prefix}: facility ID is required.")
            elif facility_id.casefold() in seen_ids:
                errors.append(f"{prefix}: facility ID '{facility_id}' is duplicated.")
            else:
                seen_ids.add(facility_id.casefold())

            numbers: Dict[str, float] = {}
            for key, label in [
                ("easting", "easting"),
                ("northing", "northing"),
                ("ground_elevation", "ground elevation"),
            ]:
                try:
                    numbers[key] = float(str(row.get(key, "")).strip())
                except (TypeError, ValueError):
                    errors.append(f"{prefix}: valid {label} is required.")
            if not source:
                errors.append(f"{prefix}: vehicle-critical-area source/reference is required.")

            geometry = QgsGeometry.fromWkt(wkt) if wkt else QgsGeometry()
            if (
                not wkt
                or geometry.isNull()
                or geometry.isEmpty()
                or geometry.type() != QgsWkbTypes.PolygonGeometry
                or not geometry.isGeosValid()
            ):
                errors.append(f"{prefix}: vehicle critical area must be valid polygon WKT in the project CRS.")

            row_error_prefix = f"{prefix}:"
            if any(message.startswith(row_error_prefix) for message in errors):
                continue
            runway_index, runway_end = self._split_runway_ref(runway_ref)
            installations.append(
                {
                    "id": facility_id,
                    "component": component,
                    "runway_index": runway_index,
                    "runway_end": runway_end,
                    "easting": numbers["easting"],
                    "northing": numbers["northing"],
                    "point": QgsPointXY(numbers["easting"], numbers["northing"]),
                    "ground_elevation": numbers["ground_elevation"],
                    "vehicle_critical_area_source": source,
                    "vehicle_critical_area_wkt": wkt,
                    "vehicle_critical_area": geometry,
                }
            )
        return installations
