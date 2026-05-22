"""Airfield Ground Lighting option widgets and validation."""

from typing import Dict, List, Optional

from qgis.PyQt import QtGui, QtWidgets  # type: ignore
from qgis.PyQt.QtWidgets import QComboBox, QTableWidgetItem  # type: ignore


class AglOptionsMixin:
    """Mixin for optional Airfield Ground Lighting inputs."""

    AGL_DEFAULTS = {
        "edge_spacing_m": "60",
        "threshold_spacing_m": "3",
        "threshold_inset_m": "0",
        "approach_spacing_m": "30",
    }

    def _setup_agl_options_ui(self) -> None:
        tab_widget = getattr(self, "tabWidget_workflow", None)
        if tab_widget is None:
            return

        self.tab_lighting = QtWidgets.QWidget()
        self.tab_lighting.setObjectName("tab_lighting")
        tab_layout = QtWidgets.QVBoxLayout(self.tab_lighting)

        group = QtWidgets.QGroupBox("Airfield Ground Lighting (optional)")
        group.setObjectName("groupBox_agl_options")
        group_layout = QtWidgets.QVBoxLayout(group)

        self.checkBox_agl_enabled = QtWidgets.QCheckBox("Generate Airfield Ground Lighting layers")
        self.checkBox_agl_enabled.setObjectName("checkBox_agl_enabled")
        group_layout.addWidget(self.checkBox_agl_enabled)

        self.label_agl_status = QtWidgets.QLabel("AGL: disabled")
        self.label_agl_status.setObjectName("label_agl_status")
        group_layout.addWidget(self.label_agl_status)

        spacing_group = QtWidgets.QGroupBox("Generated runway lighting")
        spacing_group.setObjectName("groupBox_agl_generated")
        spacing_layout = QtWidgets.QGridLayout(spacing_group)

        self.lineEdit_agl_edge_spacing = self._agl_line_edit("lineEdit_agl_edge_spacing", "60")
        self.lineEdit_agl_threshold_spacing = self._agl_line_edit("lineEdit_agl_threshold_spacing", "3")
        self.lineEdit_agl_threshold_inset = self._agl_line_edit("lineEdit_agl_threshold_inset", "0")
        self.lineEdit_agl_approach_spacing = self._agl_line_edit("lineEdit_agl_approach_spacing", "30")

        for row, (label, widget) in enumerate(
            [
                ("Edge light spacing (m)", self.lineEdit_agl_edge_spacing),
                ("Threshold light spacing (m)", self.lineEdit_agl_threshold_spacing),
                ("Threshold bar inset from runway edge (m)", self.lineEdit_agl_threshold_inset),
                ("Default approach light spacing (m)", self.lineEdit_agl_approach_spacing),
            ]
        ):
            spacing_layout.addWidget(QtWidgets.QLabel(label), row, 0)
            spacing_layout.addWidget(widget, row, 1)

        group_layout.addWidget(spacing_group)

        approach_group = QtWidgets.QGroupBox("Per-end approach lighting")
        approach_group.setObjectName("groupBox_agl_approach")
        approach_layout = QtWidgets.QVBoxLayout(approach_group)

        self.table_agl_approach = QtWidgets.QTableWidget()
        self.table_agl_approach.setObjectName("table_agl_approach")
        self.table_agl_approach.setColumnCount(4)
        self.table_agl_approach.setHorizontalHeaderLabels(
            ["Runway", "End", "Approach length (m)", "Spacing override (m)"]
        )
        self.table_agl_approach.setAlternatingRowColors(True)
        self.table_agl_approach.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.table_agl_approach.verticalHeader().setVisible(False)
        self.table_agl_approach.horizontalHeader().setStretchLastSection(True)
        approach_layout.addWidget(self.table_agl_approach)

        button_layout = QtWidgets.QHBoxLayout()
        self.pushButton_add_agl_approach = QtWidgets.QPushButton("Add Approach Row")
        self.pushButton_add_agl_approach.setObjectName("pushButton_add_agl_approach")
        self.pushButton_remove_agl_approach = QtWidgets.QPushButton("Remove Selected")
        self.pushButton_remove_agl_approach.setObjectName("pushButton_remove_agl_approach")
        button_layout.addWidget(self.pushButton_add_agl_approach)
        button_layout.addWidget(self.pushButton_remove_agl_approach)
        approach_layout.addLayout(button_layout)
        group_layout.addWidget(approach_group)

        tab_layout.addWidget(group)
        tab_layout.addStretch(1)

        output_tab = getattr(self, "tab_output", None)
        output_index = tab_widget.indexOf(output_tab) if output_tab is not None else -1
        insert_index = output_index if output_index >= 0 else tab_widget.count()
        tab_widget.insertTab(insert_index, self.tab_lighting, "Lighting")

    def _setup_agl_options_ui_connections(self) -> None:
        if not hasattr(self, "checkBox_agl_enabled"):
            return
        self.checkBox_agl_enabled.toggled.connect(self._on_agl_option_changed)
        for widget in [
            self.lineEdit_agl_edge_spacing,
            self.lineEdit_agl_threshold_spacing,
            self.lineEdit_agl_threshold_inset,
            self.lineEdit_agl_approach_spacing,
        ]:
            widget.textChanged.connect(self._on_agl_option_changed)
        self.table_agl_approach.itemChanged.connect(self._on_agl_option_changed)
        self.pushButton_add_agl_approach.clicked.connect(self._add_agl_approach_row)
        self.pushButton_remove_agl_approach.clicked.connect(self._remove_selected_agl_approach_rows)
        self._on_agl_option_changed()

    def _agl_line_edit(self, object_name: str, default_text: str) -> QtWidgets.QLineEdit:
        widget = QtWidgets.QLineEdit(default_text)
        widget.setObjectName(object_name)
        validator = QtGui.QDoubleValidator(0.0, 99999.0, 2, widget)
        validator.setNotation(QtGui.QDoubleValidator.Notation.StandardNotation)
        widget.setValidator(validator)
        widget.setMaximumWidth(120)
        return widget

    def _add_agl_approach_row(self, row_data: Optional[Dict[str, str]] = None) -> None:
        if not hasattr(self, "table_agl_approach"):
            return
        table = self.table_agl_approach
        row = table.rowCount()
        table.insertRow(row)

        runway_combo = QComboBox()
        runway_combo.setObjectName(f"comboBox_agl_runway_{row}")
        runway_combo.addItem("", userData="")
        for index in sorted(self._runway_groups.keys()):
            group = self._runway_groups[index]
            label = group.rwy_name_lbl.text() if hasattr(group, "rwy_name_lbl") else f"Runway {index}"
            runway_combo.addItem(f"{index}: {label}", userData=index)
        runway_combo.currentIndexChanged.connect(self._on_agl_option_changed)

        end_combo = QComboBox()
        end_combo.setObjectName(f"comboBox_agl_end_{row}")
        end_combo.addItem("Primary", userData="primary")
        end_combo.addItem("Reciprocal", userData="reciprocal")
        end_combo.currentIndexChanged.connect(self._on_agl_option_changed)

        table.setCellWidget(row, 0, runway_combo)
        table.setCellWidget(row, 1, end_combo)
        table.setItem(row, 2, QTableWidgetItem(""))
        table.setItem(row, 3, QTableWidgetItem(""))

        if row_data:
            self._set_combo_data(runway_combo, row_data.get("runway_index", ""))
            self._set_combo_data(end_combo, row_data.get("end", "primary"))
            table.item(row, 2).setText(str(row_data.get("length_m", "")))
            table.item(row, 3).setText(str(row_data.get("spacing_m", "")))

        self._on_agl_option_changed()

    def _remove_selected_agl_approach_rows(self) -> None:
        table = getattr(self, "table_agl_approach", None)
        if table is None:
            return
        selected_rows = sorted({index.row() for index in table.selectedIndexes()}, reverse=True)
        for row in selected_rows:
            table.removeRow(row)
        self._on_agl_option_changed()

    def _get_agl_options(self, errors: Optional[List[str]] = None) -> Dict[str, object]:
        enabled = bool(getattr(self, "checkBox_agl_enabled", None) and self.checkBox_agl_enabled.isChecked())
        options: Dict[str, object] = {"enabled": enabled, "approach_lighting": []}
        if not enabled:
            return options

        options["edge_spacing_m"] = self._agl_float(
            "lineEdit_agl_edge_spacing", "AGL edge light spacing", errors, minimum=0.01
        )
        options["threshold_spacing_m"] = self._agl_float(
            "lineEdit_agl_threshold_spacing", "AGL threshold light spacing", errors, minimum=0.01
        )
        options["threshold_inset_m"] = self._agl_float(
            "lineEdit_agl_threshold_inset", "AGL threshold bar inset", errors, minimum=0.0
        )
        options["approach_spacing_m"] = self._agl_float(
            "lineEdit_agl_approach_spacing", "AGL default approach light spacing", errors, minimum=0.01
        )
        options["approach_lighting"] = self._get_agl_approach_rows(errors)
        return options

    def _get_agl_save_options(self) -> Dict[str, object]:
        options = {
            "enabled": bool(getattr(self, "checkBox_agl_enabled", None) and self.checkBox_agl_enabled.isChecked()),
            "edge_spacing_m": self._line_text("lineEdit_agl_edge_spacing"),
            "threshold_spacing_m": self._line_text("lineEdit_agl_threshold_spacing"),
            "threshold_inset_m": self._line_text("lineEdit_agl_threshold_inset"),
            "approach_spacing_m": self._line_text("lineEdit_agl_approach_spacing"),
            "approach_lighting": [],
        }
        rows = []
        table = getattr(self, "table_agl_approach", None)
        if table is not None:
            for row in range(table.rowCount()):
                runway_combo = table.cellWidget(row, 0)
                end_combo = table.cellWidget(row, 1)
                rows.append(
                    {
                        "runway_index": runway_combo.currentData() if isinstance(runway_combo, QComboBox) else "",
                        "end": end_combo.currentData() if isinstance(end_combo, QComboBox) else "primary",
                        "length_m": self._table_text(table, row, 2),
                        "spacing_m": self._table_text(table, row, 3),
                    }
                )
        options["approach_lighting"] = rows
        return options

    def _load_agl_options(self, agl_options) -> None:
        if not isinstance(agl_options, dict) or not hasattr(self, "checkBox_agl_enabled"):
            return
        self.checkBox_agl_enabled.setChecked(bool(agl_options.get("enabled", False)))
        self._set_line_text("lineEdit_agl_edge_spacing", str(agl_options.get("edge_spacing_m", "60")))
        self._set_line_text("lineEdit_agl_threshold_spacing", str(agl_options.get("threshold_spacing_m", "3")))
        self._set_line_text("lineEdit_agl_threshold_inset", str(agl_options.get("threshold_inset_m", "0")))
        self._set_line_text("lineEdit_agl_approach_spacing", str(agl_options.get("approach_spacing_m", "30")))
        table = getattr(self, "table_agl_approach", None)
        if table is not None:
            table.setRowCount(0)
            for row_data in agl_options.get("approach_lighting", []):
                if isinstance(row_data, dict):
                    self._add_agl_approach_row(row_data)
        self._on_agl_option_changed()

    def _reset_agl_options(self) -> None:
        if not hasattr(self, "checkBox_agl_enabled"):
            return
        self.checkBox_agl_enabled.setChecked(False)
        self._set_line_text("lineEdit_agl_edge_spacing", self.AGL_DEFAULTS["edge_spacing_m"])
        self._set_line_text("lineEdit_agl_threshold_spacing", self.AGL_DEFAULTS["threshold_spacing_m"])
        self._set_line_text("lineEdit_agl_threshold_inset", self.AGL_DEFAULTS["threshold_inset_m"])
        self._set_line_text("lineEdit_agl_approach_spacing", self.AGL_DEFAULTS["approach_spacing_m"])
        if hasattr(self, "table_agl_approach"):
            self.table_agl_approach.setRowCount(0)
        self._on_agl_option_changed()

    def _agl_options_changed(self) -> bool:
        if not hasattr(self, "checkBox_agl_enabled"):
            return False
        if self.checkBox_agl_enabled.isChecked():
            return True
        table = getattr(self, "table_agl_approach", None)
        if table is not None and table.rowCount() > 0:
            return True
        for widget_name, default in [
            ("lineEdit_agl_edge_spacing", self.AGL_DEFAULTS["edge_spacing_m"]),
            ("lineEdit_agl_threshold_spacing", self.AGL_DEFAULTS["threshold_spacing_m"]),
            ("lineEdit_agl_threshold_inset", self.AGL_DEFAULTS["threshold_inset_m"]),
            ("lineEdit_agl_approach_spacing", self.AGL_DEFAULTS["approach_spacing_m"]),
        ]:
            widget = self._line_edit(widget_name)
            if widget and widget.text().strip() != default:
                return True
        return False

    def _get_agl_approach_rows(self, errors: Optional[List[str]]) -> List[Dict[str, object]]:
        rows = []
        table = getattr(self, "table_agl_approach", None)
        if table is None:
            return rows
        default_spacing = self._parse_agl_number(self._line_text("lineEdit_agl_approach_spacing"), minimum=0.01) or 30.0
        for row in range(table.rowCount()):
            runway_combo = table.cellWidget(row, 0)
            end_combo = table.cellWidget(row, 1)
            runway_index = runway_combo.currentData() if isinstance(runway_combo, QComboBox) else None
            end_role = end_combo.currentData() if isinstance(end_combo, QComboBox) else "primary"
            length_text = self._table_text(table, row, 2).strip()
            spacing_text = self._table_text(table, row, 3).strip()
            if not runway_index and not length_text and not spacing_text:
                continue
            if not runway_index:
                self._agl_error(errors, f"AGL approach row {row + 1}: runway is required.")
                continue
            try:
                runway_index_int = int(runway_index)
            except (TypeError, ValueError):
                self._agl_error(errors, f"AGL approach row {row + 1}: runway is invalid.")
                continue
            if runway_index_int not in self._runway_groups:
                self._agl_error(errors, f"AGL approach row {row + 1}: selected runway no longer exists.")
                continue
            length_m = self._parse_agl_number(length_text, minimum=0.01)
            if length_m is None:
                self._agl_error(errors, f"AGL approach row {row + 1}: approach length must be positive.")
                continue
            spacing_m = default_spacing if not spacing_text else self._parse_agl_number(spacing_text, minimum=0.01)
            if spacing_m is None:
                self._agl_error(errors, f"AGL approach row {row + 1}: spacing override must be positive.")
                continue
            rows.append(
                {
                    "runway_index": runway_index_int,
                    "end": str(end_role),
                    "length_m": float(length_m),
                    "spacing_m": float(spacing_m),
                }
            )
        return rows

    def _agl_float(self, widget_name: str, label: str, errors: Optional[List[str]], minimum: float) -> float:
        value = self._parse_agl_number(self._line_text(widget_name), minimum=minimum)
        if value is None:
            self._agl_error(errors, f"{label} must be {minimum:g} or greater.")
            return minimum
        return value

    def _parse_agl_number(self, text: str, minimum: float) -> Optional[float]:
        try:
            value = float(str(text).strip())
            if value < minimum:
                return None
            return value
        except (TypeError, ValueError):
            return None

    def _agl_error(self, errors: Optional[List[str]], message: str) -> None:
        if errors is not None:
            errors.append(message)

    def _set_combo_data(self, combo: QComboBox, value) -> None:
        idx = combo.findData(value)
        if idx < 0:
            idx = combo.findData(str(value))
        combo.setCurrentIndex(idx if idx >= 0 else 0)

    def _on_agl_option_changed(self) -> None:
        if hasattr(self, "label_agl_status"):
            if self.checkBox_agl_enabled.isChecked():
                rows = self.table_agl_approach.rowCount() if hasattr(self, "table_agl_approach") else 0
                self.label_agl_status.setText(f"AGL: enabled, {rows} approach row(s)")
            else:
                self.label_agl_status.setText("AGL: disabled")
        if hasattr(self, "update_dialog_status"):
            self.update_dialog_status()
