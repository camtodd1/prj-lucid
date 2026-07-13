"""Output option setup and validation helpers for the dialog."""

from qgis.PyQt import QtCore, QtWidgets  # type: ignore
from qgis.core import QgsMessageLog, Qgis  # type: ignore

from .dialog_constants import (
    ANNEX14_FAMILY_CONTOUR_KEYS,
    CONTOUR_INTERVAL_KEYS,
    CONTOUR_INTERVAL_KEY_DEFAULTS,
    CONTOUR_INTERVAL_LABELS,
    DEFAULT_CONTOUR_INTERVAL,
    DEFAULT_PRIMARY_CONTOUR_INTERVAL,
    DEFAULT_OUTPUT_FORMAT,
    DIALOG_LOG_TAG,
    MODERNISATION_CHANGE_CONTOUR_KEYS,
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

        self._setup_ols_workflow_control()
        self._setup_controlling_ols_control()
        self._setup_contour_interval_controls()
        self._update_ols_workflow_ui()

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

    def _setup_ols_workflow_control(self):
        """Move the persisted OLS policy selector into a compact workflow card."""
        parent_layout = getattr(self, "verticalLayout_olsTab", None)
        combo = getattr(self, "protected_airspace_policy_combo", None)
        if parent_layout is None or combo is None:
            QgsMessageLog.logMessage(
                "OLS workflow mode setup skipped: tab layout or policy selector missing.",
                DIALOG_LOG_TAG,
                level=Qgis.Warning,
            )
            return

        group = getattr(self, "groupBox_olsWorkflow", None)
        if group is None:
            group = QtWidgets.QGroupBox(self.tr("Workflow"))
            group.setObjectName("groupBox_olsWorkflow")
            parent_layout.insertWidget(0, group)
            self.groupBox_olsWorkflow = group
        grid = group.layout()
        if grid is None:
            grid = QtWidgets.QGridLayout(group)
        grid.setContentsMargins(12, 14, 12, 12)
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(8)
        grid.setColumnStretch(0, 0)
        grid.setColumnStretch(1, 1)

        old_layout = combo.parentWidget().layout() if combo.parentWidget() is not None else None
        if old_layout is not None:
            old_layout.removeWidget(combo)
        old_label = getattr(self, "label_protected_airspace_policy", None)
        if old_label is not None:
            old_label.hide()

        mode_label = QtWidgets.QLabel(self.tr("Workflow mode"))
        mode_label.setObjectName("label_olsWorkflowMode")
        mode_label.setStyleSheet("font-weight: 600;")
        combo.setMinimumWidth(320)
        combo.setMaximumWidth(520)
        combo.setItemText(0, self.tr("Baseline — selected design standard"))
        combo.setItemText(1, self.tr("Future Annex 14 — OFS/OES only"))
        combo.setItemText(2, self.tr("Modernisation comparison — baseline vs future"))
        combo.setToolTip(
            self.tr(
                "Choose the protected-airspace calculation. The saved policy identifiers remain unchanged."
            )
        )
        grid.addWidget(mode_label, 0, 0)
        grid.addWidget(combo, 0, 1)

        description = QtWidgets.QLabel()
        description.setObjectName("label_olsModeDescription")
        description.setWordWrap(True)
        description.setStyleSheet("color: #3f4852;")
        grid.addWidget(description, 1, 0, 1, 2)

        family_frame = QtWidgets.QFrame()
        family_frame.setObjectName("frame_olsFamilyExplanation")
        family_frame.setMinimumHeight(82)
        family_frame.setStyleSheet(
            "QFrame#frame_olsFamilyExplanation { background: #f5f8fb; border: 1px solid #d9e2ea; border-radius: 4px; }"
        )
        family_layout = QtWidgets.QGridLayout(family_frame)
        family_layout.setContentsMargins(10, 8, 10, 8)
        family_layout.setHorizontalSpacing(12)
        family_layout.setVerticalSpacing(3)
        ofs_title = QtWidgets.QLabel(self.tr("OFS — protected airspace"))
        ofs_title.setObjectName("label_olsOfsTitle")
        ofs_title.setStyleSheet("font-weight: 600; color: #234b68;")
        ofs_detail = QtWidgets.QLabel(
            self.tr("Obstacle-free surface used to describe the future protected-airspace envelope.")
        )
        ofs_detail.setObjectName("label_olsOfsDetail")
        ofs_detail.setWordWrap(True)
        oes_title = QtWidgets.QLabel(self.tr("OES — assessment trigger"))
        oes_title.setObjectName("label_olsOesTitle")
        oes_title.setStyleSheet("font-weight: 600; color: #234b68;")
        oes_detail = QtWidgets.QLabel(
            self.tr("Obstacle evaluation surface indicating where aeronautical assessment may be required; not an approval limit.")
        )
        oes_detail.setObjectName("label_olsOesDetail")
        oes_detail.setWordWrap(True)
        family_layout.addWidget(ofs_title, 0, 0)
        family_layout.addWidget(ofs_detail, 0, 1)
        family_layout.addWidget(oes_title, 1, 0)
        family_layout.addWidget(oes_detail, 1, 1)
        grid.addWidget(family_frame, 2, 0, 1, 2)

        status = QtWidgets.QLabel()
        status.setObjectName("label_olsInlineStatus")
        status.setWordWrap(True)
        status.setMinimumHeight(30)
        grid.addWidget(status, 3, 0, 1, 2)

        self.label_olsModeDescription = description
        self.frame_olsFamilyExplanation = family_frame
        self.label_olsOfsTitle = ofs_title
        self.label_olsOfsDetail = ofs_detail
        self.label_olsOesTitle = oes_title
        self.label_olsOesDetail = oes_detail
        self.label_olsInlineStatus = status
        combo.currentIndexChanged.connect(self._update_ols_workflow_ui)

    def _update_ols_workflow_ui(self, *_args, dependency_status=None, runway_count=None):
        """Apply mode-specific guidance, controls, and inline readiness state."""
        combo = getattr(self, "protected_airspace_policy_combo", None)
        if combo is None:
            return
        mode = str(combo.currentData() or "ruleset_aligned")
        count = len(getattr(self, "_runway_groups", {})) if runway_count is None else int(runway_count)
        descriptions = {
            "ruleset_aligned": self.tr(
                f"Selected-standard protected airspace for {count} runway(s). Standard workload."
            ),
            "future_annex14_ofs_oes": self.tr(
                f"Future Annex 14 OFS/OES for {count} runway(s), without baseline comparison layers. Moderate workload."
            ),
            "modernisation_comparison": self.tr(
                f"Baseline, future OFS/OES, and gain/loss comparison products for {count} runway(s). Highest workload."
            ),
        }
        if hasattr(self, "label_olsModeDescription"):
            self.label_olsModeDescription.setText(descriptions.get(mode, descriptions["ruleset_aligned"]))
        if hasattr(self, "frame_olsFamilyExplanation"):
            self.frame_olsFamilyExplanation.setVisible(mode != "ruleset_aligned")

        checkbox = getattr(self, "checkBox_generateControllingOls", None)
        if checkbox is not None:
            comparison_required = mode == "modernisation_comparison"
            if comparison_required:
                checkbox.setChecked(True)
            checkbox.setEnabled(not comparison_required)
            checkbox.setStyleSheet(
                "QCheckBox:disabled { color: #4f5964; }"
                if comparison_required
                else ""
            )
            checkbox.setText(
                self.tr("Controlling envelopes and comparison layers")
                if comparison_required
                else self.tr("Controlling envelope layers")
            )
            checkbox.setToolTip(
                self.tr("Required because comparison polygons use the solved baseline and future controlling envelopes.")
                if comparison_required
                else self.tr("Include solved controlling regions, transitions, and clipped controlling contours.")
            )
        controlling_group = getattr(self, "groupBox_controllingOls", None)
        if controlling_group is not None:
            controlling_group.setTitle(self.tr("Generated Outputs"))
        contour_group = getattr(self, "groupBox_contourIntervals", None)
        if contour_group is not None:
            contour_group.setTitle(
                self.tr("Contours — Baseline and Future")
                if mode == "modernisation_comparison"
                else self.tr("Contours — Future OFS/OES")
                if mode == "future_annex14_ofs_oes"
                else self.tr("Contours — Baseline OLS")
            )

        future_family_widget = getattr(self, "widgetModernisationContourIntervals", None)
        if future_family_widget is not None:
            future_family_widget.setVisible(mode != "ruleset_aligned")
        for header_name in (
            "labelModernisationChangeIntervals",
            "labelModernisationChangePrimaryHeader",
            "labelModernisationChangeIntermediateHeader",
        ):
            header = getattr(self, header_name, None)
            if header is not None:
                header.setVisible(mode == "modernisation_comparison")
        overrides_button = getattr(self, "toolButtonContourOverrides", None)
        if overrides_button is not None:
            overrides_button.setVisible(mode != "future_annex14_ofs_oes")
        overrides_widget = getattr(self, "widgetContourOverrides", None)
        if overrides_widget is not None:
            overrides_widget.setVisible(
                mode != "future_annex14_ofs_oes"
                and bool(overrides_button and overrides_button.isChecked())
            )

        annex_keys = set(ANNEX14_FAMILY_CONTOUR_KEYS)
        comparison_keys = set(MODERNISATION_CHANGE_CONTOUR_KEYS)
        for key, label in getattr(self, "_contour_interval_labels", {}).items():
            visible = (
                key not in annex_keys | comparison_keys
                if mode == "ruleset_aligned"
                else key in annex_keys
                if mode == "future_annex14_ofs_oes"
                else True
            )
            label.setVisible(visible)
            primary = getattr(self, "_contour_primary_interval_spinboxes", {}).get(key)
            intermediate = getattr(self, "_contour_interval_spinboxes", {}).get(key)
            if primary is not None:
                primary.setVisible(visible)
            if intermediate is not None:
                intermediate.setVisible(visible)

        status_data = dependency_status or {
            "state": "neutral",
            "summary": self.tr("Complete airport and runway inputs to evaluate OLS readiness."),
        }
        state = str(status_data.get("state") or "neutral")
        colors = {
            "ready": ("#e8f5ec", "#2f7d45", "#235f34"),
            "warning": ("#fff7e0", "#b87a00", "#744d00"),
            "blocked": ("#fff0f0", "#c64545", "#7b2929"),
            "neutral": ("#f2f4f6", "#aab2bb", "#4f5964"),
        }
        background, border, foreground = colors.get(state, colors["neutral"])
        if hasattr(self, "label_olsInlineStatus"):
            self.label_olsInlineStatus.setText(str(status_data.get("summary") or ""))
            self.label_olsInlineStatus.setVisible(state in {"warning", "blocked"})
            self.label_olsInlineStatus.setStyleSheet(
                f"QLabel {{ background: {background}; border: 1px solid {border}; border-radius: 4px; "
                f"color: {foreground}; padding: 6px 8px; font-weight: 600; }}"
            )
        workflow_group = getattr(self, "groupBox_olsWorkflow", None)
        if workflow_group is not None:
            workflow_group.updateGeometry()

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
            group = QtWidgets.QGroupBox(self.tr("Protected Airspace Contour Intervals"))
            group.setObjectName("groupBox_contourIntervals")
            parent_layout.addWidget(group)
        group.setTitle(self.tr("Protected Airspace Contour Intervals"))
        group.setToolTip(
            self.tr(
                "Adjust contour spacing for protected-airspace outputs. Family rows override the matching surface rows."
            )
        )

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
        primary_header.setToolTip(self.tr("Interval used to classify major contours."))
        intermediate_header = getattr(self, "labelContourIntermediateHeader", None)
        if intermediate_header is None:
            intermediate_header = QtWidgets.QLabel(self.tr("Intermediate"))
            intermediate_header.setObjectName("labelContourIntermediateHeader")
            grid.addWidget(intermediate_header, 0, 2)
        intermediate_header.setToolTip(self.tr("Interval used to generate regular contour lines."))

        reset_button = getattr(self, "toolButtonResetContourIntervals", None)
        if reset_button is None:
            reset_button = QtWidgets.QToolButton()
            reset_button.setObjectName("toolButtonResetContourIntervals")
            reset_button.setText(self.tr("Reset"))
            reset_button.setToolButtonStyle(QtCore.Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
            reset_button.setIcon(reset_button.style().standardIcon(QtWidgets.QStyle.StandardPixmap.SP_BrowserReload))
            reset_button.clicked.connect(self._reset_contour_interval_controls)
            self.toolButtonResetContourIntervals = reset_button
            grid.addWidget(reset_button, 0, 3)
        reset_button.setToolTip(self.tr("Reset all contour intervals to the default values."))

        self._contour_primary_interval_spinboxes = {}
        self._contour_interval_spinboxes = {}
        self._contour_interval_labels = {}
        default_label = getattr(self, "labelContourDefault", None)
        if default_label is None:
            default_label = QtWidgets.QLabel(self.tr("Default contour interval"))
            default_label.setObjectName("labelContourDefault")
            grid.addWidget(default_label, 1, 0)
        default_label.setToolTip(self.tr("Fallback used when a surface or family does not have a specific override."))
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
        self.doubleSpinBoxContourDefaultPrimary.setToolTip(self.tr("Default major-contour interval."))
        self.doubleSpinBoxContourDefault.setToolTip(self.tr("Default regular contour interval."))
        grid.addWidget(self.doubleSpinBoxContourDefaultPrimary, 1, 1)
        grid.addWidget(self.doubleSpinBoxContourDefault, 1, 2)

        modernisation_widget = getattr(self, "widgetModernisationContourIntervals", None)
        if modernisation_widget is None:
            modernisation_widget = QtWidgets.QFrame(group)
            modernisation_widget.setObjectName("widgetModernisationContourIntervals")
            modernisation_widget.setStyleSheet(
                "QFrame#widgetModernisationContourIntervals { background: #f5f8fb; "
                "border: 1px solid #d9e2ea; border-radius: 4px; }"
            )
            modernisation_grid = QtWidgets.QGridLayout(modernisation_widget)
            modernisation_grid.setObjectName("gridLayoutModernisationContourIntervals")
            modernisation_grid.setContentsMargins(8, 1, 8, 1)
            modernisation_grid.setHorizontalSpacing(12)
            modernisation_grid.setVerticalSpacing(1)
            modernisation_grid.setColumnStretch(0, 1)
            modernisation_grid.setColumnStretch(1, 0)
            modernisation_grid.setColumnStretch(2, 0)
            modernisation_grid.setColumnStretch(3, 1)
            modernisation_grid.setColumnStretch(4, 0)
            modernisation_grid.setColumnStretch(5, 0)
            family_header = QtWidgets.QLabel(self.tr("Future surface contours"))
            family_header.setObjectName("labelModernisationContourIntervals")
            family_header.setStyleSheet("font-weight: 600; color: #234b68; font-size: 10px;")
            family_header.setToolTip(
                self.tr(
                    "Future surface intervals control elevation contours; change intervals control signed comparison isolines."
                )
            )
            family_primary_header = QtWidgets.QLabel(self.tr("Primary"))
            family_primary_header.setStyleSheet("color: #59636e; font-size: 9px;")
            family_intermediate_header = QtWidgets.QLabel(self.tr("Intermediate"))
            family_intermediate_header.setStyleSheet("color: #59636e; font-size: 9px;")
            change_header = QtWidgets.QLabel(self.tr("Comparison change contours"))
            change_header.setObjectName("labelModernisationChangeIntervals")
            change_header.setStyleSheet("font-weight: 600; color: #234b68; font-size: 10px;")
            change_primary_header = QtWidgets.QLabel(self.tr("Primary"))
            change_primary_header.setObjectName("labelModernisationChangePrimaryHeader")
            change_primary_header.setStyleSheet("color: #59636e; font-size: 9px;")
            change_intermediate_header = QtWidgets.QLabel(self.tr("Intermediate"))
            change_intermediate_header.setObjectName(
                "labelModernisationChangeIntermediateHeader"
            )
            change_intermediate_header.setStyleSheet("color: #59636e; font-size: 9px;")
            modernisation_grid.addWidget(family_header, 0, 0)
            modernisation_grid.addWidget(family_primary_header, 0, 1)
            modernisation_grid.addWidget(family_intermediate_header, 0, 2)
            modernisation_grid.addWidget(change_header, 0, 3)
            modernisation_grid.addWidget(change_primary_header, 0, 4)
            modernisation_grid.addWidget(change_intermediate_header, 0, 5)
            grid.addWidget(modernisation_widget, 2, 0, 1, 4)
            self.widgetModernisationContourIntervals = modernisation_widget
            self.gridLayoutModernisationContourIntervals = modernisation_grid
            self.labelModernisationContourIntervals = family_header
            self.labelModernisationChangeIntervals = change_header
            self.labelModernisationChangePrimaryHeader = change_primary_header
            self.labelModernisationChangeIntermediateHeader = change_intermediate_header
        else:
            modernisation_grid = modernisation_widget.layout()

        overrides_button = getattr(self, "toolButtonContourOverrides", None)
        if overrides_button is None:
            overrides_button = QtWidgets.QToolButton()
            overrides_button.setObjectName("toolButtonContourOverrides")
            overrides_button.setText(self.tr("Individual baseline surface settings"))
            overrides_button.setCheckable(True)
            overrides_button.setChecked(False)
            overrides_button.setArrowType(QtCore.Qt.ArrowType.RightArrow)
            overrides_button.setToolButtonStyle(QtCore.Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
            overrides_button.setSizePolicy(
                QtWidgets.QSizePolicy.Policy.Expanding,
                QtWidgets.QSizePolicy.Policy.Fixed,
            )
            overrides_button.setStyleSheet(
                "QToolButton { border: 1px solid #d4dbe2; border-radius: 4px; "
                "background: #f6f8fa; padding: 6px 8px; text-align: left; font-weight: 600; }"
                "QToolButton:hover { background: #eef3f7; }"
            )
            grid.addWidget(overrides_button, 3, 0, 1, 4)
            self.toolButtonContourOverrides = overrides_button

        overrides_widget = getattr(self, "widgetContourOverrides", None)
        if overrides_widget is None:
            overrides_widget = QtWidgets.QWidget(group)
            overrides_widget.setObjectName("widgetContourOverrides")
            overrides_grid = QtWidgets.QGridLayout(overrides_widget)
            overrides_grid.setObjectName("gridLayoutContourOverrides")
            overrides_grid.setContentsMargins(8, 6, 8, 4)
            overrides_grid.setHorizontalSpacing(12)
            overrides_grid.setVerticalSpacing(6)
            overrides_grid.setColumnStretch(0, 1)
            overrides_grid.setColumnStretch(1, 0)
            overrides_grid.setColumnStretch(2, 0)
            detail_primary_header = QtWidgets.QLabel(self.tr("Primary"))
            detail_primary_header.setStyleSheet("color: #59636e; font-size: 11px;")
            detail_intermediate_header = QtWidgets.QLabel(self.tr("Intermediate"))
            detail_intermediate_header.setStyleSheet("color: #59636e; font-size: 11px;")
            overrides_grid.addWidget(detail_primary_header, 0, 1)
            overrides_grid.addWidget(detail_intermediate_header, 0, 2)
            grid.addWidget(overrides_widget, 4, 0, 1, 4)
            self.widgetContourOverrides = overrides_widget
            self.gridLayoutContourOverrides = overrides_grid
        else:
            overrides_grid = overrides_widget.layout()

        overrides_button.toggled.connect(self._toggle_contour_overrides)
        self._toggle_contour_overrides(overrides_button.isChecked())

        regular_row = 1
        modernisation_keys = set(ANNEX14_FAMILY_CONTOUR_KEYS) | set(
            MODERNISATION_CHANGE_CONTOUR_KEYS
        )
        modernisation_positions = {
            "annex14_ofs": (1, 0, 1, 2),
            "annex14_oes": (2, 0, 1, 2),
            "modernisation_ofs_change": (1, 3, 4, 5),
            "modernisation_oes_change": (2, 3, 4, 5),
        }
        for key in CONTOUR_INTERVAL_KEYS:
            is_modernisation = key in modernisation_keys
            target_grid = modernisation_grid if is_modernisation else overrides_grid
            if is_modernisation:
                row, label_column, primary_column, intermediate_column = (
                    modernisation_positions[key]
                )
            else:
                row, label_column, primary_column, intermediate_column = (
                    regular_row,
                    0,
                    1,
                    2,
                )
            label_name = f"labelContour{key.title()}"
            primary_spin_name = f"doubleSpinBoxContour{key.title()}Primary"
            intermediate_spin_name = f"doubleSpinBoxContour{key.title()}Intermediate"
            label = getattr(self, label_name, None)
            if label is None:
                label = QtWidgets.QLabel(self.tr(CONTOUR_INTERVAL_LABELS[key]))
                label.setObjectName(label_name)
                target_grid.addWidget(label, row, label_column)
            self._contour_interval_labels[key] = label
            label.setToolTip(self._contour_interval_tooltip(key))
            primary_spinbox = getattr(self, primary_spin_name, None)
            if primary_spinbox is None:
                key_defaults = CONTOUR_INTERVAL_KEY_DEFAULTS.get(key, {})
                primary_spinbox = self._create_contour_interval_spinbox(
                    primary_spin_name,
                    key_defaults.get("primary", DEFAULT_PRIMARY_CONTOUR_INTERVAL),
                )
            intermediate_spinbox = getattr(self, intermediate_spin_name, None)
            if intermediate_spinbox is None:
                intermediate_spinbox = self._create_contour_interval_spinbox(
                    intermediate_spin_name,
                    CONTOUR_INTERVAL_KEY_DEFAULTS.get(key, {}).get(
                        "intermediate",
                        DEFAULT_CONTOUR_INTERVAL,
                    ),
                )
            primary_spinbox.setToolTip(self._contour_interval_tooltip(key, role="primary"))
            intermediate_spinbox.setToolTip(self._contour_interval_tooltip(key, role="intermediate"))
            self._contour_primary_interval_spinboxes[key] = primary_spinbox
            self._contour_interval_spinboxes[key] = intermediate_spinbox
            if is_modernisation:
                primary_spinbox.setFixedHeight(18)
                intermediate_spinbox.setFixedHeight(18)
            target_grid.addWidget(primary_spinbox, row, primary_column)
            target_grid.addWidget(intermediate_spinbox, row, intermediate_column)
            if not is_modernisation:
                regular_row += 1

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

    def _toggle_contour_overrides(self, expanded: bool):
        """Show or hide individual contour overrides while defaults stay visible."""
        button = getattr(self, "toolButtonContourOverrides", None)
        widget = getattr(self, "widgetContourOverrides", None)
        if button is not None:
            button.setArrowType(
                QtCore.Qt.ArrowType.DownArrow if expanded else QtCore.Qt.ArrowType.RightArrow
            )
            button.setToolTip(
                self.tr("Hide individual baseline surface contour intervals.")
                if expanded
                else self.tr("Show individual baseline surface contour intervals.")
            )
        if widget is not None:
            combo = getattr(self, "protected_airspace_policy_combo", None)
            mode = (
                str(combo.currentData() or "ruleset_aligned")
                if combo is not None
                else "ruleset_aligned"
            )
            widget.setVisible(bool(expanded) and mode != "future_annex14_ofs_oes")

    def _create_contour_interval_spinbox(self, object_name: str, default_value: float = DEFAULT_CONTOUR_INTERVAL):
        spinbox = QtWidgets.QDoubleSpinBox()
        spinbox.setObjectName(object_name)
        spinbox.setRange(0.1, 10000.0)
        spinbox.setDecimals(2)
        spinbox.setSingleStep(0.1 if default_value < 1.0 else 1.0)
        spinbox.setSuffix(" m")
        spinbox.setValue(default_value)
        return spinbox

    def _contour_interval_tooltip(self, key: str, role: str = "label") -> str:
        label = CONTOUR_INTERVAL_LABELS.get(key, key.replace("_", " ").title())
        family_note = ""
        if key == "annex14_ofs":
            family_note = " Overrides Annex 14 obstacle free surface contours after surface-level defaults."
        elif key == "annex14_oes":
            family_note = " Overrides Annex 14 obstacle evaluation surface contours after surface-level defaults."
        elif key in MODERNISATION_CHANGE_CONTOUR_KEYS:
            family = "OFS" if key == "modernisation_ofs_change" else "OES"
            family_note = f" Controls signed height-change isolines for the {family} comparison output."
        elif key.startswith("inner_") or key == "baulked_landing":
            family_note = " Used by precision inner-surface and OFZ-style outputs where available."
        if role == "primary":
            return self.tr(f"{label}: major-contour classification interval.{family_note}")
        if role == "intermediate":
            return self.tr(f"{label}: regular contour generation interval.{family_note}")
        return self.tr(f"Contour interval override for {label}.{family_note}")

    def _reset_contour_interval_controls(self):
        if hasattr(self, "doubleSpinBoxContourDefaultPrimary"):
            self.doubleSpinBoxContourDefaultPrimary.setValue(DEFAULT_PRIMARY_CONTOUR_INTERVAL)
        if hasattr(self, "doubleSpinBoxContourDefault"):
            self.doubleSpinBoxContourDefault.setValue(DEFAULT_CONTOUR_INTERVAL)
        self._apply_default_contour_interval("primary", DEFAULT_PRIMARY_CONTOUR_INTERVAL)
        self._apply_default_contour_interval("intermediate", DEFAULT_CONTOUR_INTERVAL)
        for key, defaults in CONTOUR_INTERVAL_KEY_DEFAULTS.items():
            primary = getattr(self, "_contour_primary_interval_spinboxes", {}).get(key)
            intermediate = getattr(self, "_contour_interval_spinboxes", {}).get(key)
            if primary is not None:
                primary.setValue(defaults["primary"])
            if intermediate is not None:
                intermediate.setValue(defaults["intermediate"])
        if hasattr(self, "toolButtonContourOverrides"):
            self.toolButtonContourOverrides.setChecked(False)

    def _apply_default_contour_interval(self, role: str, value: float):
        attr_name = (
            "_contour_primary_interval_spinboxes"
            if role == "primary"
            else "_contour_interval_spinboxes"
        )
        for key, spinbox in getattr(self, attr_name, {}).items():
            if key in MODERNISATION_CHANGE_CONTOUR_KEYS:
                continue
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
        modernisation_keys = set(ANNEX14_FAMILY_CONTOUR_KEYS) | set(
            MODERNISATION_CHANGE_CONTOUR_KEYS
        )
        for key in CONTOUR_INTERVAL_KEYS:
            key_defaults = CONTOUR_INTERVAL_KEY_DEFAULTS.get(key, {})
            primary_value = self._coerce_contour_interval_value(
                contour_options,
                key,
                "primary",
                key_defaults.get("primary", default_primary),
            )
            intermediate_value = self._coerce_contour_interval_value(
                contour_options,
                key,
                "intermediate",
                key_defaults.get("intermediate", default_intermediate),
            )
            if key in primary_spinboxes:
                primary_spinboxes[key].setValue(primary_value)
            if key in intermediate_spinboxes:
                intermediate_spinboxes[key].setValue(intermediate_value)
        has_regular_overrides = any(
            abs(primary_spinboxes[key].value() - default_primary) > 1e-9
            or abs(intermediate_spinboxes[key].value() - default_intermediate) > 1e-9
            for key in CONTOUR_INTERVAL_KEYS
            if key not in modernisation_keys
            if key in primary_spinboxes and key in intermediate_spinboxes
        )
        if hasattr(self, "toolButtonContourOverrides"):
            self.toolButtonContourOverrides.setChecked(has_regular_overrides)

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
