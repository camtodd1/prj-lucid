"""Output option setup and validation helpers for the dialog."""

from qgis.PyQt import QtWidgets  # type: ignore
from qgis.core import QgsMessageLog, Qgis  # type: ignore

from .dialog_constants import (
    CONTOUR_INTERVAL_KEYS,
    CONTOUR_INTERVAL_LABELS,
    DEFAULT_CONTOUR_INTERVAL,
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

        if DEFAULT_OUTPUT_FORMAT in OUTPUT_FORMATS:
            self.comboOutputFormat.setCurrentText(DEFAULT_OUTPUT_FORMAT)

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
        self._on_output_option_changed()

    def _setup_contour_interval_controls(self):
        """Add contour interval controls to the Output tab."""
        if hasattr(self, "groupBox_contourIntervals"):
            return

        parent_layout = getattr(self, "verticalLayout_5", None)
        if parent_layout is None:
            QgsMessageLog.logMessage(
                "Contour interval UI setup skipped: output options layout missing.",
                DIALOG_LOG_TAG,
                level=Qgis.Warning,
            )
            return

        group = QtWidgets.QGroupBox(self.tr("OLS Contour Intervals"))
        group.setObjectName("groupBox_contourIntervals")
        grid = QtWidgets.QGridLayout(group)
        grid.setObjectName("gridLayout_contourIntervals")

        default_label = QtWidgets.QLabel(self.tr("Default contour interval"))
        default_label.setObjectName("labelContourDefault")
        self.doubleSpinBoxContourDefault = self._create_contour_interval_spinbox("doubleSpinBoxContourDefault")
        grid.addWidget(default_label, 0, 0)
        grid.addWidget(self.doubleSpinBoxContourDefault, 0, 1)

        self._contour_interval_spinboxes = {}
        for row, key in enumerate(CONTOUR_INTERVAL_KEYS, start=1):
            label = QtWidgets.QLabel(self.tr(CONTOUR_INTERVAL_LABELS[key]))
            label.setObjectName(f"labelContour{key.title()}")
            spinbox = self._create_contour_interval_spinbox(f"doubleSpinBoxContour{key.title()}")
            self._contour_interval_spinboxes[key] = spinbox
            grid.addWidget(label, row, 0)
            grid.addWidget(spinbox, row, 1)

        self.doubleSpinBoxContourDefault.valueChanged.connect(self._apply_default_contour_interval)
        for spinbox in self._contour_interval_spinboxes.values():
            spinbox.valueChanged.connect(self._on_contour_interval_changed)

        parent_layout.addWidget(group)

    def _create_contour_interval_spinbox(self, object_name: str):
        spinbox = QtWidgets.QDoubleSpinBox()
        spinbox.setObjectName(object_name)
        spinbox.setRange(0.1, 10000.0)
        spinbox.setDecimals(2)
        spinbox.setSingleStep(1.0)
        spinbox.setSuffix(" m")
        spinbox.setValue(DEFAULT_CONTOUR_INTERVAL)
        return spinbox

    def _apply_default_contour_interval(self, value: float):
        for spinbox in getattr(self, "_contour_interval_spinboxes", {}).values():
            spinbox.blockSignals(True)
            spinbox.setValue(value)
            spinbox.blockSignals(False)
        self._on_contour_interval_changed()

    def _on_contour_interval_changed(self):
        if hasattr(self, "update_dialog_status"):
            self.update_dialog_status()

    def get_contour_interval_options(self):
        spinboxes = getattr(self, "_contour_interval_spinboxes", {})
        return {
            "default": self.doubleSpinBoxContourDefault.value()
            if hasattr(self, "doubleSpinBoxContourDefault")
            else DEFAULT_CONTOUR_INTERVAL,
            **{key: spinboxes[key].value() for key in CONTOUR_INTERVAL_KEYS if key in spinboxes},
        }

    def set_contour_interval_options(self, contour_options):
        if not isinstance(contour_options, dict):
            contour_options = {}
        default_value = self._coerce_contour_interval(contour_options.get("default"), DEFAULT_CONTOUR_INTERVAL)
        if hasattr(self, "doubleSpinBoxContourDefault"):
            self.doubleSpinBoxContourDefault.setValue(default_value)

        spinboxes = getattr(self, "_contour_interval_spinboxes", {})
        for key in CONTOUR_INTERVAL_KEYS:
            if key in spinboxes:
                value = self._coerce_contour_interval(contour_options.get(key), default_value)
                spinboxes[key].setValue(value)

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
