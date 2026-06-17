"""Output option setup and validation helpers for the dialog."""

from qgis.PyQt import QtWidgets  # type: ignore
from qgis.core import QgsMessageLog, Qgis  # type: ignore

from .dialog_constants import (
    CONTOUR_INTERVAL_KEYS,
    CONTOUR_INTERVAL_LABELS,
    DEFAULT_CONTOUR_INTERVAL,
    DEFAULT_PRIMARY_CONTOUR_INTERVAL,
    DEFAULT_OUTPUT_FORMAT,
    DIALOG_LOG_TAG,
    OUTPUT_FORMATS,
)


class OutputOptionsMixin:
    """Mixin containing output option widget setup and state helpers."""

    def _setup_output_options_ui_connections(self):
        missing_widgets = []
        if not hasattr(self, "radioMemoryOutput"):
            missing_widgets.append("radioMemoryOutput")
        if not hasattr(self, "radioFileOutput"):
            missing_widgets.append("radioFileOutput")
        if not hasattr(self, "fileWidgetOutputPath"):
            missing_widgets.append("fileWidgetOutputPath")
        if not hasattr(self, "comboOutputFormat"):
            missing_widgets.append("comboOutputFormat")

        if missing_widgets:
            QgsMessageLog.logMessage(
                f"Output options UI setup incomplete. Missing widgets: {', '.join(missing_widgets)}",
                DIALOG_LOG_TAG,
                level=Qgis.Critical,
            )
            if hasattr(self, "pushButton_Generate"):
                self.pushButton_Generate.setEnabled(False)
                self.pushButton_Generate.setToolTip("Output options UI is misconfigured.")
            return

        self.comboOutputFormat.clear()
        for display_name in OUTPUT_FORMATS.keys():
            self.comboOutputFormat.addItem(display_name)
        self.comboOutputFormat.setToolTip(self.tr("File format used for permanent output."))
        self.fileWidgetOutputPath.setToolTip(self.tr("Directory used for permanent output files."))
        output_fields = getattr(self, "gridLayout_outputFields", None)
        if isinstance(output_fields, QtWidgets.QGridLayout):
            output_fields.setHorizontalSpacing(12)
            output_fields.setVerticalSpacing(8)
            output_fields.setColumnStretch(0, 0)
            output_fields.setColumnStretch(1, 1)

        if DEFAULT_OUTPUT_FORMAT in OUTPUT_FORMATS:
            self.comboOutputFormat.setCurrentText(DEFAULT_OUTPUT_FORMAT)

        self._setup_controlling_ols_control()
        self._setup_contour_interval_controls()

        self.radioMemoryOutput.setChecked(True)
        file_widget_cls = type(self.fileWidgetOutputPath)
        directory_mode = getattr(
            getattr(file_widget_cls, "StorageMode", file_widget_cls),
            "GetDirectory",
            1,
        )
        self.fileWidgetOutputPath.setStorageMode(directory_mode)
        if hasattr(self.fileWidgetOutputPath, "setDialogTitle"):
            self.fileWidgetOutputPath.setDialogTitle(self.tr("Select Output Directory"))
        self._update_file_widget_filter()

        self.radioMemoryOutput.toggled.connect(self._on_output_option_changed)
        self.comboOutputFormat.currentIndexChanged.connect(self._update_file_widget_filter)
        if hasattr(self, "checkBox_generateControllingOls"):
            self.checkBox_generateControllingOls.toggled.connect(self._on_output_option_changed)
        self._on_output_option_changed()

    def _setup_controlling_ols_control(self):
        """Add the development controlling OLS output toggle to the Output tab."""
        checkbox = getattr(self, "checkBox_generateControllingOls", None)
        parent_layout = getattr(self, "verticalLayout_controllingOls", getattr(self, "verticalLayout_olsTab", getattr(self, "verticalLayout_5", None)))
        if parent_layout is None:
            QgsMessageLog.logMessage(
                "Controlling OLS output control setup skipped: output options layout missing.",
                DIALOG_LOG_TAG,
                level=Qgis.Warning,
            )
            return

        if checkbox is None:
            checkbox = QtWidgets.QCheckBox(self.tr("Generate controlling OLS surfaces"))
            checkbox.setObjectName("checkBox_generateControllingOls")
            parent_layout.addWidget(checkbox)
            self.checkBox_generateControllingOls = checkbox
        checkbox.setChecked(True)
        checkbox.setToolTip(self.tr("Include the development controlling OLS lower-envelope output layers."))

    def _setup_contour_interval_controls(self):
        """Add contour interval controls to the Output tab."""
        parent_layout = getattr(self, "verticalLayout_olsTab", getattr(self, "verticalLayout_5", None))
        if parent_layout is None:
            QgsMessageLog.logMessage(
                "Contour interval UI setup skipped: output options layout missing.",
                DIALOG_LOG_TAG,
                level=Qgis.Warning,
            )
            return
        group = getattr(self, "groupBox_contourIntervals", None)
        if group is None:
            group = QtWidgets.QGroupBox(self.tr("OLS Contour Intervals"))
            group.setObjectName("groupBox_contourIntervals")
            parent_layout.addWidget(group)

        grid = group.layout()
        if grid is None:
            grid = QtWidgets.QGridLayout(group)
            grid.setObjectName("gridLayout_contourIntervals")
        if isinstance(grid, QtWidgets.QGridLayout):
            grid.setHorizontalSpacing(12)
            grid.setVerticalSpacing(6)
            grid.setColumnStretch(0, 1)
            grid.setColumnStretch(1, 0)
            grid.setColumnStretch(2, 0)

        primary_header = getattr(self, "labelContourPrimaryHeader", None)
        if primary_header is None:
            primary_header = QtWidgets.QLabel(self.tr("Primary"))
            primary_header.setObjectName("labelContourPrimaryHeader")
            grid.addWidget(primary_header, 0, 1)
        intermediate_header = getattr(self, "labelContourIntermediateHeader", None)
        if intermediate_header is None:
            intermediate_header = QtWidgets.QLabel(self.tr("Intermediate"))
            intermediate_header.setObjectName("labelContourIntermediateHeader")
            grid.addWidget(intermediate_header, 0, 2)

        self._contour_primary_interval_spinboxes = {}
        self._contour_interval_spinboxes = {}
        default_label = getattr(self, "labelContourDefault", None)
        if default_label is None:
            default_label = QtWidgets.QLabel(self.tr("Default contour interval"))
            default_label.setObjectName("labelContourDefault")
            grid.addWidget(default_label, 1, 0)
        self.doubleSpinBoxContourDefaultPrimary = getattr(
            self,
            "doubleSpinBoxContourDefaultPrimary",
            None,
        ) or self._create_contour_interval_spinbox(
            "doubleSpinBoxContourDefaultPrimary",
            DEFAULT_PRIMARY_CONTOUR_INTERVAL,
        )
        self.doubleSpinBoxContourDefault = getattr(
            self,
            "doubleSpinBoxContourDefault",
            None,
        ) or self._create_contour_interval_spinbox("doubleSpinBoxContourDefault")
        grid.addWidget(self.doubleSpinBoxContourDefaultPrimary, 1, 1)
        grid.addWidget(self.doubleSpinBoxContourDefault, 1, 2)

        for row, key in enumerate(CONTOUR_INTERVAL_KEYS, start=2):
            label_name = f"labelContour{key.title()}"
            primary_spin_name = f"doubleSpinBoxContour{key.title()}Primary"
            intermediate_spin_name = f"doubleSpinBoxContour{key.title()}Intermediate"
            label = getattr(self, label_name, None)
            if label is None:
                label = QtWidgets.QLabel(self.tr(CONTOUR_INTERVAL_LABELS[key]))
                label.setObjectName(label_name)
                grid.addWidget(label, row, 0)
            primary_spinbox = getattr(self, primary_spin_name, None)
            if primary_spinbox is None:
                primary_spinbox = self._create_contour_interval_spinbox(
                    primary_spin_name,
                    DEFAULT_PRIMARY_CONTOUR_INTERVAL,
                )
            intermediate_spinbox = getattr(self, intermediate_spin_name, None)
            if intermediate_spinbox is None:
                intermediate_spinbox = self._create_contour_interval_spinbox(intermediate_spin_name)
            self._contour_primary_interval_spinboxes[key] = primary_spinbox
            self._contour_interval_spinboxes[key] = intermediate_spinbox
            grid.addWidget(primary_spinbox, row, 1)
            grid.addWidget(intermediate_spinbox, row, 2)

        self.doubleSpinBoxContourDefaultPrimary.valueChanged.connect(
            lambda value: self._apply_default_contour_interval("primary", value)
        )
        self.doubleSpinBoxContourDefault.valueChanged.connect(
            lambda value: self._apply_default_contour_interval("intermediate", value)
        )
        for spinbox in self._contour_primary_interval_spinboxes.values():
            spinbox.valueChanged.connect(self._on_contour_interval_changed)
        for spinbox in self._contour_interval_spinboxes.values():
            spinbox.valueChanged.connect(self._on_contour_interval_changed)

    def _create_contour_interval_spinbox(self, object_name: str, default_value: float = DEFAULT_CONTOUR_INTERVAL):
        spinbox = QtWidgets.QDoubleSpinBox()
        spinbox.setObjectName(object_name)
        spinbox.setRange(0.1, 10000.0)
        spinbox.setDecimals(2)
        spinbox.setSingleStep(1.0)
        spinbox.setSuffix(" m")
        spinbox.setValue(default_value)
        return spinbox

    def _apply_default_contour_interval(self, role: str, value: float):
        attr_name = (
            "_contour_primary_interval_spinboxes"
            if role == "primary"
            else "_contour_interval_spinboxes"
        )
        for spinbox in getattr(self, attr_name, {}).values():
            spinbox.blockSignals(True)
            spinbox.setValue(value)
            spinbox.blockSignals(False)
        self._on_contour_interval_changed()

    def _on_contour_interval_changed(self):
        if hasattr(self, "update_dialog_status"):
            self.update_dialog_status()

    def get_contour_interval_options(self):
        primary_spinboxes = getattr(self, "_contour_primary_interval_spinboxes", {})
        intermediate_spinboxes = getattr(self, "_contour_interval_spinboxes", {})
        default_primary = (
            self.doubleSpinBoxContourDefaultPrimary.value()
            if hasattr(self, "doubleSpinBoxContourDefaultPrimary")
            else DEFAULT_PRIMARY_CONTOUR_INTERVAL
        )
        default_intermediate = (
            self.doubleSpinBoxContourDefault.value()
            if hasattr(self, "doubleSpinBoxContourDefault")
            else DEFAULT_CONTOUR_INTERVAL
        )
        return {
            "default": {
                "primary": default_primary,
                "intermediate": default_intermediate,
            },
            **{
                key: {
                    "primary": primary_spinboxes[key].value()
                    if key in primary_spinboxes
                    else default_primary,
                    "intermediate": intermediate_spinboxes[key].value()
                    if key in intermediate_spinboxes
                    else default_intermediate,
                }
                for key in CONTOUR_INTERVAL_KEYS
            },
        }

    def set_contour_interval_options(self, contour_options):
        if not isinstance(contour_options, dict):
            contour_options = {}
        default_primary = self._coerce_contour_interval_value(
            contour_options,
            "default",
            "primary",
            DEFAULT_PRIMARY_CONTOUR_INTERVAL,
        )
        default_intermediate = self._coerce_contour_interval_value(
            contour_options,
            "default",
            "intermediate",
            DEFAULT_CONTOUR_INTERVAL,
        )
        if hasattr(self, "doubleSpinBoxContourDefaultPrimary"):
            self.doubleSpinBoxContourDefaultPrimary.setValue(default_primary)
        if hasattr(self, "doubleSpinBoxContourDefault"):
            self.doubleSpinBoxContourDefault.setValue(default_intermediate)

        primary_spinboxes = getattr(self, "_contour_primary_interval_spinboxes", {})
        intermediate_spinboxes = getattr(self, "_contour_interval_spinboxes", {})
        for key in CONTOUR_INTERVAL_KEYS:
            primary_value = self._coerce_contour_interval_value(
                contour_options,
                key,
                "primary",
                default_primary,
            )
            intermediate_value = self._coerce_contour_interval_value(
                contour_options,
                key,
                "intermediate",
                default_intermediate,
            )
            if key in primary_spinboxes:
                primary_spinboxes[key].setValue(primary_value)
            if key in intermediate_spinboxes:
                intermediate_spinboxes[key].setValue(intermediate_value)

    def _coerce_contour_interval_value(
        self,
        contour_options,
        key: str,
        role: str,
        fallback: float,
    ) -> float:
        raw_value = contour_options.get(key)
        if isinstance(raw_value, dict):
            return self._coerce_contour_interval(raw_value.get(role), fallback)
        if role == "intermediate":
            return self._coerce_contour_interval(raw_value, fallback)
        legacy_primary = contour_options.get(f"{key}_{role}")
        return self._coerce_contour_interval(legacy_primary, fallback)

    def _coerce_contour_interval(self, value, fallback: float) -> float:
        try:
            numeric_value = float(value)
        except (TypeError, ValueError):
            return fallback
        return numeric_value if numeric_value > 0 else fallback

    def _on_output_option_changed(self):
        is_file_output = self.radioFileOutput.isChecked()
        self.fileWidgetOutputPath.setEnabled(is_file_output)
        self.comboOutputFormat.setEnabled(is_file_output)
        if hasattr(self, "update_dialog_status"):
            self.update_dialog_status()

    def _update_file_widget_filter(self):
        selected_format_name = self.comboOutputFormat.currentText()
        if selected_format_name in OUTPUT_FORMATS:
            _driver, user_name, extension = OUTPUT_FORMATS[selected_format_name]
            filter_string = f"{user_name} (*{extension})"
            other_formats = []
            for key, (_drv, usr_name, ext) in OUTPUT_FORMATS.items():
                if key != selected_format_name:
                    other_formats.append(f"{usr_name} (*{ext})")
            if other_formats:
                filter_string += ";;" + ";;".join(other_formats)
            self.fileWidgetOutputPath.setFilter(filter_string)
        else:
            self.fileWidgetOutputPath.setFilter(self.tr("All files (*.*)"))
