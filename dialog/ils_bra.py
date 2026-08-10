"""ILS Building Restricted Area installation inputs."""

import math
from typing import Any, Dict, List, Optional, Tuple

from qgis.core import QgsPointXY  # type: ignore
from qgis.PyQt import QtWidgets  # type: ignore
from qgis.PyQt.QtCore import Qt  # type: ignore
from qgis.PyQt.QtWidgets import QAbstractItemView, QComboBox, QTableWidgetItem  # type: ignore

from .cns_table import CNS_ENTRY_TABLE_STYLE


ILS_BRA_COMPONENTS: List[Tuple[str, str]] = [
    ("Glide path", "glide_path"),
    ("Localiser", "localiser"),
]

ILS_BRA_POSITION_MODES: List[Tuple[str, str]] = [
    ("Derived from runway", "runway_offset"),
    ("Direct antenna coordinates", "direct"),
]


class IlsBraInputsMixin:
    """Manage provisional ILS BRA inputs and runway-relative positioning."""

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
                "Position mode",
                "Antenna Easting",
                "Antenna Northing",
                "Distance from threshold (m)",
                "Distance from runway centreline (m)",
                "Ground elev (AMSL)",
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
            for column in range(8):
                header.setSectionResizeMode(column, QtWidgets.QHeaderView.ResizeMode.Interactive)
        for column, width in enumerate([115, 170, 175, 125, 125, 170, 190, 135]):
            table.setColumnWidth(column, width)
        table.setMinimumHeight(168)
        table.setMaximumHeight(168)
        table.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding,
            QtWidgets.QSizePolicy.Policy.Fixed,
        )
        table.setStyleSheet(CNS_ENTRY_TABLE_STYLE)
        table.setToolTip(
            "For glide path, distance from threshold is measured into the runway and centreline "
            "distance is right-positive looking into the runway. For localiser, distance from "
            "threshold is measured beyond the opposite runway end and the antenna is constrained "
            "to the extended centreline."
        )

        add_button.clicked.connect(self.add_ils_bra_row)
        remove_button.clicked.connect(self.remove_ils_bra_rows)
        add_button.setToolTip("Add a provisional glide-path or localiser installation.")
        remove_button.setToolTip("Remove the selected ILS installation row(s).")
        add_button.setMinimumWidth(130)
        add_button.setMaximumWidth(170)
        remove_button.setMinimumWidth(140)
        remove_button.setMaximumWidth(180)
        remove_button.setEnabled(False)
        table.itemSelectionChanged.connect(self._update_ils_bra_view_state)
        if table.model() is not None:
            table.model().rowsInserted.connect(lambda *_: self._update_ils_bra_view_state())
            table.model().rowsRemoved.connect(lambda *_: self._update_ils_bra_view_state())

        self._update_ils_bra_view_state()

    @staticmethod
    def _runway_designations(data: Dict[str, Any]) -> Tuple[str, str]:
        try:
            primary_number = int(
                str(
                    data.get("designator_str")
                    or data.get("designator_num", "")
                ).strip()
            )
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
                    (f"RWY {primary} Approach", f"{runway_index}:1"),
                    (f"RWY {reciprocal} Approach", f"{runway_index}:2"),
                ]
            )
        return options

    def _new_component_combo(self, selected: str = "") -> QComboBox:
        combo = QComboBox()
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

    def _new_position_mode_combo(self, selected: str = "") -> QComboBox:
        combo = QComboBox()
        for label, value in ILS_BRA_POSITION_MODES:
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
        table.setCellWidget(row, 0, self._new_component_combo(str(data.get("component", "glide_path"))))
        runway_ref = str(data.get("runway_ref", ""))
        if not runway_ref and data.get("runway_index") is not None and data.get("runway_end") is not None:
            runway_ref = f'{data.get("runway_index")}:{data.get("runway_end")}'
        table.setCellWidget(row, 1, self._new_runway_end_combo(runway_ref))
        position_mode = str(data.get("position_mode", ""))
        if not position_mode:
            position_mode = "direct" if data.get("easting") or data.get("northing") else "runway_offset"
        table.setCellWidget(row, 2, self._new_position_mode_combo(position_mode))
        values = {
            3: data.get("easting", ""),
            4: data.get("northing", ""),
            5: data.get(
                "runway_relative_distance",
                data.get(
                    "distance_beyond_runway_end",
                    data.get("distance_inside_threshold", "300"),
                ),
            ),
            6: data.get("signed_offset", ""),
            7: data.get("ground_elevation", ""),
        }
        for column, value in values.items():
            table.setItem(row, column, QTableWidgetItem(str(value if value is not None else "")))
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
        for row in range(row_count):
            component = table.cellWidget(row, 0)
            position_mode = table.cellWidget(row, 2)
            component_value = (
                str(component.currentData() or "")
                if isinstance(component, QComboBox)
                else ""
            )
            position_value = (
                str(position_mode.currentData() or "")
                if isinstance(position_mode, QComboBox)
                else ""
            )
            direct = position_value == "direct"
            self._set_ils_bra_item_enabled(table, row, 3, direct)
            self._set_ils_bra_item_enabled(table, row, 4, direct)
            self._set_ils_bra_item_enabled(table, row, 5, not direct)
            self._set_ils_bra_item_enabled(
                table,
                row,
                6,
                not direct and component_value == "glide_path",
            )
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

        header_height = table.horizontalHeader().height() if table.horizontalHeader() else 28
        row_heights = sum(table.rowHeight(row) for row in range(row_count))
        target_height = header_height + row_heights + 10
        if row_count == 0:
            target_height = 168
        else:
            target_height = min(max(target_height, 168), 320)
        table.setMinimumHeight(target_height)
        table.setMaximumHeight(target_height)

    @staticmethod
    def _set_ils_bra_item_enabled(table, row: int, column: int, enabled: bool) -> None:
        item = table.item(row, column)
        if item is None:
            return
        flags = item.flags()
        if enabled:
            item.setFlags(flags | Qt.ItemFlag.ItemIsEnabled)
        else:
            item.setFlags(flags & ~Qt.ItemFlag.ItemIsEnabled)

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
            position_mode = table.cellWidget(row, 2)
            runway_ref = str(runway.currentData() or "") if isinstance(runway, QComboBox) else ""
            runway_index, runway_end = self._split_runway_ref(runway_ref)
            rows.append(
                {
                    "component": str(component.currentData() or "") if isinstance(component, QComboBox) else "",
                    "runway_ref": runway_ref,
                    "runway_index": runway_index,
                    "runway_end": runway_end,
                    "position_mode": (
                        str(position_mode.currentData() or "")
                        if isinstance(position_mode, QComboBox)
                        else ""
                    ),
                    "easting": self._ils_bra_item_text(table, row, 3),
                    "northing": self._ils_bra_item_text(table, row, 4),
                    "runway_relative_distance": self._ils_bra_item_text(table, row, 5),
                    "signed_offset": self._ils_bra_item_text(table, row, 6),
                    "ground_elevation": self._ils_bra_item_text(table, row, 7),
                    "provisional": True,
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

    @staticmethod
    def _runway_frame(runway: Dict[str, Any], runway_end: int) -> Optional[Dict[str, Any]]:
        threshold = runway.get("thr_point") if runway_end == 1 else runway.get("rec_thr_point")
        opposite = runway.get("rec_thr_point") if runway_end == 1 else runway.get("thr_point")
        if threshold is None or opposite is None:
            return None
        delta_e = opposite.x() - threshold.x()
        delta_n = opposite.y() - threshold.y()
        length = math.hypot(delta_e, delta_n)
        if length <= 1e-9:
            return None
        unit_e = delta_e / length
        unit_n = delta_n / length
        return {
            "threshold": QgsPointXY(threshold),
            "opposite_threshold": QgsPointXY(opposite),
            "interior_unit": (unit_e, unit_n),
            "right_unit": (unit_n, -unit_e),
            "runway_length": length,
            "approach_type": runway.get("type1" if runway_end == 1 else "type2", ""),
        }

    @staticmethod
    def _localiser_category(approach_type: Any) -> Optional[str]:
        normalised = str(approach_type or "").strip().upper().replace(" ", "")
        if "CATII/III" in normalised:
            return "cat_ii_iii"
        if "CATI" in normalised:
            return "cat_i"
        return None

    def get_ils_bra_input_data(
        self,
        validated_runways: List[Dict[str, Any]],
        errors: List[str],
    ) -> List[Dict[str, Any]]:
        runway_by_index = {
            runway.get("original_index"): runway for runway in validated_runways
        }
        installations: List[Dict[str, Any]] = []
        seen_ids = set()
        for row_number, row in enumerate(self.get_ils_bra_save_rows(), start=1):
            if not any(str(value or "").strip() for value in row.values() if value is not True):
                continue
            prefix = f"ILS BRA row {row_number}"
            component = str(row.get("component", ""))
            runway_index, runway_end = self._split_runway_ref(str(row.get("runway_ref", "")))
            runway = runway_by_index.get(runway_index)
            frame = self._runway_frame(runway, runway_end) if runway and runway_end else None
            position_mode = str(row.get("position_mode", ""))
            designations = self._runway_designations(runway) if runway else ("", "")
            designation = designations[runway_end - 1] if runway_end in {1, 2} else ""
            facility_prefix = "GP" if component == "glide_path" else "LOC"
            facility_id_base = f"{facility_prefix}-{designation or row_number}"
            source_reference = "Provisional ILS BRA worked-example construction"

            if component not in {value for _, value in ILS_BRA_COMPONENTS}:
                errors.append(f"{prefix}: select glide path or localiser.")
            if frame is None:
                errors.append(f"{prefix}: select a valid runway approach end.")
            if position_mode not in {value for _, value in ILS_BRA_POSITION_MODES}:
                errors.append(f"{prefix}: select a valid position mode.")
            try:
                ground_elevation = float(str(row.get("ground_elevation", "")).strip())
            except (TypeError, ValueError):
                ground_elevation = None
                errors.append(f"{prefix}: valid ground elevation is required.")

            point = None
            distance_inside = None
            distance_beyond_runway_end = None
            signed_offset = None
            if frame is not None and position_mode == "direct":
                try:
                    easting = float(str(row.get("easting", "")).strip())
                    northing = float(str(row.get("northing", "")).strip())
                    point = QgsPointXY(easting, northing)
                    if component == "localiser":
                        delta_e = easting - frame["opposite_threshold"].x()
                        delta_n = northing - frame["opposite_threshold"].y()
                        distance_beyond_runway_end = (
                            delta_e * frame["interior_unit"][0]
                            + delta_n * frame["interior_unit"][1]
                        )
                        signed_offset = (
                            delta_e * frame["right_unit"][0]
                            + delta_n * frame["right_unit"][1]
                        )
                    else:
                        delta_e = easting - frame["threshold"].x()
                        delta_n = northing - frame["threshold"].y()
                        distance_inside = (
                            delta_e * frame["interior_unit"][0]
                            + delta_n * frame["interior_unit"][1]
                        )
                        signed_offset = (
                            delta_e * frame["right_unit"][0]
                            + delta_n * frame["right_unit"][1]
                        )
                except (TypeError, ValueError):
                    errors.append(f"{prefix}: valid antenna easting and northing are required.")
            elif frame is not None and position_mode == "runway_offset":
                try:
                    runway_relative_distance = float(
                        str(row.get("runway_relative_distance", "")).strip()
                    )
                    if component == "localiser":
                        distance_beyond_runway_end = runway_relative_distance
                        signed_offset = 0.0
                        point = QgsPointXY(
                            frame["opposite_threshold"].x()
                            + distance_beyond_runway_end * frame["interior_unit"][0],
                            frame["opposite_threshold"].y()
                            + distance_beyond_runway_end * frame["interior_unit"][1],
                        )
                    else:
                        distance_inside = runway_relative_distance
                        signed_offset = float(str(row.get("signed_offset", "")).strip())
                        if distance_inside < 0:
                            raise ValueError("distance must not be negative")
                        if abs(signed_offset) <= 1e-9:
                            raise ValueError("offset must not be zero")
                        point = QgsPointXY(
                            frame["threshold"].x()
                            + distance_inside * frame["interior_unit"][0]
                            + signed_offset * frame["right_unit"][0],
                            frame["threshold"].y()
                            + distance_inside * frame["interior_unit"][1]
                            + signed_offset * frame["right_unit"][1],
                        )
                except (TypeError, ValueError) as error:
                    requirement = (
                        "valid localiser setback beyond the opposite runway end"
                        if component == "localiser"
                        else "valid non-negative threshold distance and non-zero signed offset"
                    )
                    errors.append(f"{prefix}: {requirement} is required ({error}).")

            if component == "glide_path" and signed_offset is not None:
                if not 120.0 <= abs(signed_offset) <= 175.0:
                    errors.append(
                        f"{prefix}: provisional glide-path offset must be between 120 m and 175 m from runway centreline."
                    )
            localiser_category = None
            if component == "localiser" and frame is not None:
                localiser_category = self._localiser_category(frame["approach_type"])
                if localiser_category is None:
                    errors.append(
                        f"{prefix}: selected runway end must be Precision Approach CAT I or CAT II/III."
                    )
                if distance_beyond_runway_end is not None and not 200.0 <= distance_beyond_runway_end <= 400.0:
                    errors.append(
                        f"{prefix}: provisional localiser setback must be between 200 m and 400 m beyond the opposite runway end."
                    )
                if signed_offset is not None and abs(signed_offset) > 1.0:
                    errors.append(
                        f"{prefix}: localiser antenna must lie on the extended runway centreline (1 m tolerance)."
                    )

            row_error_prefix = f"{prefix}:"
            if any(message.startswith(row_error_prefix) for message in errors):
                continue
            facility_id = facility_id_base
            duplicate_number = 2
            while facility_id.casefold() in seen_ids:
                facility_id = f"{facility_id_base}-{duplicate_number}"
                duplicate_number += 1
            seen_ids.add(facility_id.casefold())
            installations.append(
                {
                    "id": facility_id,
                    "component": component,
                    "runway_index": runway_index,
                    "runway_end": runway_end,
                    "runway_designation": designation,
                    "position_mode": position_mode,
                    "easting": point.x(),
                    "northing": point.y(),
                    "point": point,
                    "front_face_point": point,
                    "distance_inside_threshold": distance_inside,
                    "distance_beyond_runway_end": distance_beyond_runway_end,
                    "signed_offset": signed_offset,
                    "antenna_offset": abs(signed_offset),
                    "runway_interior_unit": frame["interior_unit"],
                    "runway_length": frame["runway_length"],
                    "localiser_category": localiser_category,
                    "ground_elevation": ground_elevation,
                    "source_reference": source_reference,
                    "provisional": True,
                }
            )
        return installations
