"""Airfield Ground Lighting option widgets and validation."""

from typing import Dict, List, Optional

from qgis.PyQt import QtCore, QtGui, QtWidgets  # type: ignore

try:
    from ..rulesets.registry import DEFAULT_RULESET_ID, get_ruleset_profile
except ImportError:
    from rulesets.registry import DEFAULT_RULESET_ID, get_ruleset_profile  # type: ignore


class AglOptionsMixin:
    """Mixin for optional Airfield Ground Lighting inputs."""

    EASA_RULESET_ID = "easa_cs_adr_dsn_issue_7"
    MOS139_RULESET_ID = "mos139_2019"
    CAP168_RULESET_ID = "uk_caa_cap168_edition_13"

    AGL_DEFAULTS = {
        "edge_spacing_m": "60",
        "threshold_spacing_m": "3",
        "threshold_inset_m": "0",
    }

    def _agl_ruleset(self):
        ruleset_combo = getattr(self, "_ruleset_combo_widget", lambda: None)()
        ruleset_id = ruleset_combo.currentData() if ruleset_combo is not None else DEFAULT_RULESET_ID
        return get_ruleset_profile(ruleset_id)

    def _setup_agl_options_ui(self) -> None:
        tab_widget = getattr(self, "tabWidget_workflow", None)
        if tab_widget is None:
            return

        self.tab_lighting = QtWidgets.QWidget()
        self.tab_lighting.setObjectName("tab_lighting")
        tab_layout = QtWidgets.QVBoxLayout(self.tab_lighting)
        tab_layout.setContentsMargins(8, 8, 8, 8)
        tab_layout.setSpacing(8)
        tab_layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignTop)

        scroll_area = QtWidgets.QScrollArea(self.tab_lighting)
        scroll_area.setObjectName("scrollArea_agl_options")
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        scroll_area.setMinimumHeight(0)
        scroll_area.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding,
            QtWidgets.QSizePolicy.Policy.Expanding,
        )
        self.scrollArea_agl_options = scroll_area

        scroll_content = QtWidgets.QWidget(scroll_area)
        scroll_content.setObjectName("widget_agl_options_scroll_content")
        scroll_content.setMinimumHeight(0)
        content_layout = QtWidgets.QVBoxLayout(scroll_content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(8)
        content_layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignTop)

        group = QtWidgets.QGroupBox("Airfield Ground Lighting (optional)")
        group.setObjectName("groupBox_agl_options")
        group.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding,
            QtWidgets.QSizePolicy.Policy.Maximum,
        )
        group_layout = QtWidgets.QVBoxLayout(group)
        group_layout.setContentsMargins(10, 12, 10, 10)
        group_layout.setSpacing(8)

        control_layout = QtWidgets.QHBoxLayout()
        control_layout.setContentsMargins(0, 0, 0, 0)
        control_layout.setSpacing(8)

        self.checkBox_agl_enabled = QtWidgets.QCheckBox("Generate Airfield Ground Lighting layers")
        self.checkBox_agl_enabled.setObjectName("checkBox_agl_enabled")
        self.checkBox_agl_enabled.setToolTip("Generate AGL point layers from the runway definitions.")
        control_layout.addWidget(self.checkBox_agl_enabled)
        control_layout.addStretch(1)
        group_layout.addLayout(control_layout)

        self.lineEdit_agl_edge_spacing = self._agl_line_edit("lineEdit_agl_edge_spacing", "60")
        self.lineEdit_agl_threshold_spacing = self._agl_line_edit("lineEdit_agl_threshold_spacing", "3")
        self.lineEdit_agl_threshold_inset = self._agl_line_edit("lineEdit_agl_threshold_inset", "0")
        self.lineEdit_agl_edge_spacing.setReadOnly(True)
        self.lineEdit_agl_threshold_spacing.setReadOnly(True)

        self.label_agl_edge_spacing = QtWidgets.QLabel()
        self.label_agl_threshold_spacing = QtWidgets.QLabel()
        self.label_agl_threshold_inset = QtWidgets.QLabel(
            "Threshold bar inset from runway edge (m)"
        )
        self.label_agl_edge_spacing.setObjectName("label_agl_edge_spacing")
        self.label_agl_threshold_spacing.setObjectName("label_agl_threshold_spacing")
        self.label_agl_threshold_inset.setObjectName("label_agl_threshold_inset")

        def light_type_group(title: str, object_name: str):
            layer_group = QtWidgets.QGroupBox(title)
            layer_group.setObjectName(object_name)
            layer_layout = QtWidgets.QGridLayout(layer_group)
            layer_layout.setHorizontalSpacing(8)
            layer_layout.setVerticalSpacing(6)
            layer_layout.setColumnStretch(0, 1)
            setattr(self, object_name, layer_group)
            return layer_group, layer_layout

        spacing_group = QtWidgets.QGroupBox("Generated light type layers")
        spacing_group.setObjectName("groupBox_agl_generated")
        self.groupBox_agl_generated = spacing_group
        spacing_layout = QtWidgets.QGridLayout(spacing_group)
        spacing_layout.setHorizontalSpacing(12)
        spacing_layout.setVerticalSpacing(8)
        spacing_layout.setColumnStretch(0, 1)
        spacing_layout.setColumnStretch(1, 1)

        edge_group, edge_layout = light_type_group(
            "Runway Edge", "groupBox_agl_layer_runway_edge"
        )
        edge_layout.addWidget(self.label_agl_edge_spacing, 0, 0)
        edge_layout.addWidget(self.lineEdit_agl_edge_spacing, 0, 1)

        threshold_group, threshold_layout = light_type_group(
            "Threshold", "groupBox_agl_layer_threshold"
        )
        threshold_layout.addWidget(self.label_agl_threshold_spacing, 0, 0)
        threshold_layout.addWidget(self.lineEdit_agl_threshold_spacing, 0, 1)
        threshold_layout.addWidget(self.label_agl_threshold_inset, 1, 0)
        threshold_layout.addWidget(self.lineEdit_agl_threshold_inset, 1, 1)

        spacing_layout.addWidget(edge_group, 0, 0)
        spacing_layout.addWidget(threshold_group, 0, 1)

        group_layout.addWidget(spacing_group)

        content_layout.addWidget(group)
        content_layout.addStretch(1)
        scroll_area.setWidget(scroll_content)
        tab_layout.addWidget(scroll_area)

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
        ]:
            widget.textChanged.connect(self._on_agl_option_changed)
        ruleset_combo = self._ruleset_combo_widget()
        if ruleset_combo is not None:
            ruleset_combo.currentIndexChanged.connect(self._update_agl_ruleset_view)
        self._update_agl_ruleset_view()
        self._on_agl_option_changed()

    def _agl_line_edit(self, object_name: str, default_text: str) -> QtWidgets.QLineEdit:
        widget = QtWidgets.QLineEdit(default_text)
        widget.setObjectName(object_name)
        validator = QtGui.QDoubleValidator(0.0, 99999.0, 2, widget)
        validator.setNotation(QtGui.QDoubleValidator.Notation.StandardNotation)
        widget.setValidator(validator)
        widget.setMaximumWidth(120)
        return widget

    def _get_agl_options(self, errors: Optional[List[str]] = None) -> Dict[str, object]:
        enabled = bool(getattr(self, "checkBox_agl_enabled", None) and self.checkBox_agl_enabled.isChecked())
        options: Dict[str, object] = {"enabled": enabled}
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
        return options

    def _get_agl_save_options(self) -> Dict[str, object]:
        options = {
            "enabled": bool(getattr(self, "checkBox_agl_enabled", None) and self.checkBox_agl_enabled.isChecked()),
            "edge_spacing_m": self._line_text("lineEdit_agl_edge_spacing"),
            "threshold_spacing_m": self._line_text("lineEdit_agl_threshold_spacing"),
            "threshold_inset_m": self._line_text("lineEdit_agl_threshold_inset"),
        }
        return options

    def _load_agl_options(self, agl_options) -> None:
        if not isinstance(agl_options, dict) or not hasattr(self, "checkBox_agl_enabled"):
            return
        self.checkBox_agl_enabled.setChecked(bool(agl_options.get("enabled", False)))
        self._set_line_text("lineEdit_agl_edge_spacing", str(agl_options.get("edge_spacing_m", "60")))
        self._set_line_text("lineEdit_agl_threshold_spacing", str(agl_options.get("threshold_spacing_m", "3")))
        self._set_line_text("lineEdit_agl_threshold_inset", str(agl_options.get("threshold_inset_m", "0")))
        self._on_agl_option_changed()

    def _reset_agl_options(self) -> None:
        if not hasattr(self, "checkBox_agl_enabled"):
            return
        self.checkBox_agl_enabled.setChecked(False)
        self._set_line_text("lineEdit_agl_edge_spacing", self.AGL_DEFAULTS["edge_spacing_m"])
        self._set_line_text("lineEdit_agl_threshold_spacing", self.AGL_DEFAULTS["threshold_spacing_m"])
        self._set_line_text("lineEdit_agl_threshold_inset", self.AGL_DEFAULTS["threshold_inset_m"])
        self._on_agl_option_changed()

    def _agl_options_changed(self) -> bool:
        if not hasattr(self, "checkBox_agl_enabled"):
            return False
        if self.checkBox_agl_enabled.isChecked():
            return True
        for widget_name, default in [
            ("lineEdit_agl_edge_spacing", self.AGL_DEFAULTS["edge_spacing_m"]),
            ("lineEdit_agl_threshold_spacing", self.AGL_DEFAULTS["threshold_spacing_m"]),
            ("lineEdit_agl_threshold_inset", self.AGL_DEFAULTS["threshold_inset_m"]),
        ]:
            widget = self._line_edit(widget_name)
            if widget and widget.text().strip() != default:
                return True
        return False

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

    def _on_agl_option_changed(self) -> None:
        enabled = self.checkBox_agl_enabled.isChecked()
        for group_name in ["groupBox_agl_generated"]:
            group = getattr(self, group_name, None)
            if group is not None:
                group.setEnabled(enabled)
        self._update_agl_ruleset_view()
        self._update_agl_view_state()
        if hasattr(self, "update_dialog_status"):
            self.update_dialog_status()

    def _update_agl_ruleset_view(self, *_args) -> None:
        """Present source context for the selected design standard."""
        profile = self._agl_ruleset()
        is_easa = profile.id == self.EASA_RULESET_ID
        is_mos139 = profile.id == self.MOS139_RULESET_ID
        is_cap168 = profile.id == self.CAP168_RULESET_ID

        if is_easa:
            self.label_agl_edge_spacing.setText("EASA instrument runway edge spacing (m)")
            self.label_agl_threshold_spacing.setText("EASA precision threshold max spacing (m)")
        else:
            self.label_agl_edge_spacing.setText(
                "MOS edge spacing baseline (m)" if is_mos139 else "Edge spacing baseline (m)"
            )
            self.label_agl_threshold_spacing.setText(
                "MOS precision threshold max spacing (m)"
                if is_mos139
                else "Precision threshold max spacing (m)"
            )

            if is_cap168:
                self.label_agl_edge_spacing.setText("CAP 168 runway edge spacing baseline (m)")
                self.label_agl_threshold_spacing.setText(
                    "CAP 168 precision threshold max spacing (m)"
                )

    def _update_agl_view_state(self) -> None:
        """Refresh the shared tab status after AGL controls change."""
        if hasattr(self, "update_dialog_status"):
            self.update_dialog_status()
