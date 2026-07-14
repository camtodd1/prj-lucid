"""Output option setup and validation helpers for the dialog."""

from qgis.PyQt import QtCore, QtWidgets  # type: ignore
from qgis.core import QgsMessageLog, Qgis  # type: ignore

try:
    from ..rulesets.registry import (
        DEFAULT_RULESET_ID,
        get_ruleset_profile,
        iter_ruleset_profiles,
    )
except ImportError:
    from rulesets.registry import DEFAULT_RULESET_ID, get_ruleset_profile, iter_ruleset_profiles  # type: ignore

from .dialog_constants import (
    ANNEX14_FAMILY_CONTOUR_KEYS,
    ANNEX14_OES_SURFACE_CONTOUR_KEYS,
    ANNEX14_OFS_SURFACE_CONTOUR_KEYS,
    ANNEX14_SURFACE_CONTOUR_KEYS,
    COMPARISON_SURFACE_CONTOUR_KEYS,
    CONTOUR_INTERVAL_KEYS,
    CONTOUR_INTERVAL_KEY_DEFAULTS,
    CONTOUR_INTERVAL_LABELS,
    CONVENTIONAL_SURFACE_CONTOUR_KEYS,
    DEFAULT_CONTOUR_INTERVAL,
    DEFAULT_PRIMARY_CONTOUR_INTERVAL,
    DEFAULT_OUTPUT_FORMAT,
    DIALOG_LOG_TAG,
    MODERNISATION_CHANGE_CONTOUR_KEYS,
    OUTPUT_FORMATS,
    SURFACE_CONTOUR_KEYS,
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
        """Create side-by-side baseline and comparison OLS selectors."""
        parent_layout = getattr(self, "verticalLayout_olsTab", None)
        legacy_combo = getattr(self, "protected_airspace_policy_combo", None)
        if parent_layout is None:
            QgsMessageLog.logMessage(
                "OLS workflow setup skipped: tab layout missing.",
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
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)

        if legacy_combo is not None:
            old_layout = (
                legacy_combo.parentWidget().layout()
                if legacy_combo.parentWidget() is not None
                else None
            )
            if old_layout is not None:
                old_layout.removeWidget(legacy_combo)
            legacy_combo.hide()
        old_label = getattr(self, "label_protected_airspace_policy", None)
        if old_label is not None:
            old_label.hide()

        baseline_label = QtWidgets.QLabel(self.tr("Baseline OLS"))
        baseline_label.setObjectName("label_baselineOlsRuleset")
        baseline_label.setStyleSheet("font-weight: 600;")
        comparison_label = QtWidgets.QLabel(self.tr("Comparison OLS"))
        comparison_label.setObjectName("label_comparisonOlsRuleset")
        comparison_label.setStyleSheet("font-weight: 600;")

        baseline_combo = QtWidgets.QComboBox()
        baseline_combo.setObjectName("comboBox_baseline_ols_ruleset")
        comparison_combo = QtWidgets.QComboBox()
        comparison_combo.setObjectName("comboBox_comparison_ols_ruleset")
        comparison_combo.addItem(self.tr("None — baseline only"), userData="")
        self._available_ols_ruleset_ids = set()
        profiles = tuple(iter_ruleset_profiles())
        for profile in profiles:
            available = self._ols_profile_available(profile)
            label = profile.display_name
            if not available:
                label = self.tr(f"{label} — controlling OLS unavailable")
            baseline_combo.addItem(label, userData=profile.id)
            comparison_combo.addItem(label, userData=profile.id)
            if available:
                self._available_ols_ruleset_ids.add(profile.id)
            for ruleset_combo in (baseline_combo, comparison_combo):
                item = ruleset_combo.model().item(ruleset_combo.count() - 1)
                if item is not None:
                    item.setEnabled(available)
                    if not available:
                        item.setToolTip(
                            self.tr(
                                "This ruleset will become selectable when its controlling OLS capability is available."
                            )
                        )

        initial_ruleset = DEFAULT_RULESET_ID
        design_combo = getattr(self, "ruleset_combo", None)
        if design_combo is not None and design_combo.currentData():
            initial_ruleset = str(design_combo.currentData())
        initial_index = baseline_combo.findData(initial_ruleset)
        if initial_ruleset not in self._available_ols_ruleset_ids:
            initial_index = baseline_combo.findData(DEFAULT_RULESET_ID)
        baseline_combo.setCurrentIndex(max(0, initial_index))

        baseline_combo.setMinimumWidth(280)
        comparison_combo.setMinimumWidth(280)
        baseline_combo.setToolTip(
            self.tr(
                "Ruleset used to generate the reference controlling OLS envelope."
            )
        )
        comparison_combo.setToolTip(
            self.tr(
                "Optional second controlling OLS envelope. Select None to generate only the baseline."
            )
        )
        grid.addWidget(baseline_label, 0, 0)
        grid.addWidget(comparison_label, 0, 1)
        grid.addWidget(baseline_combo, 1, 0)
        grid.addWidget(comparison_combo, 1, 1)

        description = QtWidgets.QLabel()
        description.setObjectName("label_olsModeDescription")
        description.setWordWrap(True)
        description.setStyleSheet("color: #3f4852;")
        grid.addWidget(description, 2, 0, 1, 2)

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
        grid.addWidget(family_frame, 3, 0, 1, 2)

        status = QtWidgets.QLabel()
        status.setObjectName("label_olsInlineStatus")
        status.setWordWrap(True)
        status.setMinimumHeight(30)
        grid.addWidget(status, 4, 0, 1, 2)

        self.baseline_ols_ruleset_combo = baseline_combo
        self.comparison_ols_ruleset_combo = comparison_combo
        self.label_baselineOlsRuleset = baseline_label
        self.label_comparisonOlsRuleset = comparison_label
        self.label_olsModeDescription = description
        self.frame_olsFamilyExplanation = family_frame
        self.label_olsOfsTitle = ofs_title
        self.label_olsOfsDetail = ofs_detail
        self.label_olsOesTitle = oes_title
        self.label_olsOesDetail = oes_detail
        self.label_olsInlineStatus = status
        baseline_combo.currentIndexChanged.connect(self._on_ols_ruleset_selection_changed)
        comparison_combo.currentIndexChanged.connect(self._on_ols_ruleset_selection_changed)
        self._update_comparison_ols_ruleset_items()
        self._sync_legacy_ols_policy()

    @staticmethod
    def _ols_profile_available(profile) -> bool:
        """Return whether a ruleset can currently produce a controlling envelope."""
        try:
            return profile.capability_status("ols.controlling_lower_envelope") in {
                "supported",
                "partial",
                "experimental",
            }
        except Exception:
            return False

    def _current_ols_ruleset_ids(self):
        baseline_combo = getattr(self, "baseline_ols_ruleset_combo", None)
        comparison_combo = getattr(self, "comparison_ols_ruleset_combo", None)
        baseline_id = (
            str(baseline_combo.currentData() or DEFAULT_RULESET_ID)
            if baseline_combo is not None
            else DEFAULT_RULESET_ID
        )
        comparison_id = (
            str(comparison_combo.currentData() or "")
            if comparison_combo is not None
            else ""
        )
        return baseline_id, comparison_id

    def _legacy_ols_policy_for_selection(self) -> str:
        """Map explicit ruleset choices onto legacy processing policy identifiers."""
        baseline_id, comparison_id = self._current_ols_ruleset_ids()
        modernised_id = "icao_annex14_vol1_modernised_ofs_oes"
        if not comparison_id:
            return (
                "future_annex14_ofs_oes"
                if baseline_id == modernised_id
                else "ruleset_aligned"
            )
        if comparison_id == modernised_id and baseline_id != modernised_id:
            return "modernisation_comparison"
        return "ruleset_comparison"

    def _sync_legacy_ols_policy(self) -> None:
        legacy_combo = getattr(self, "protected_airspace_policy_combo", None)
        if legacy_combo is None:
            return
        policy = self._legacy_ols_policy_for_selection()
        index = legacy_combo.findData(policy)
        if index < 0:
            legacy_combo.addItem(policy, userData=policy)
            index = legacy_combo.count() - 1
        blocked = legacy_combo.blockSignals(True)
        legacy_combo.setCurrentIndex(index)
        legacy_combo.blockSignals(blocked)

    def _update_comparison_ols_ruleset_items(self) -> None:
        baseline_id, comparison_id = self._current_ols_ruleset_ids()
        comparison_combo = getattr(self, "comparison_ols_ruleset_combo", None)
        if comparison_combo is None:
            return
        if comparison_id and not self._ols_pair_available(baseline_id, comparison_id):
            comparison_combo.setCurrentIndex(0)
            comparison_id = ""
        available_ids = getattr(self, "_available_ols_ruleset_ids", set())
        for index in range(1, comparison_combo.count()):
            ruleset_id = str(comparison_combo.itemData(index) or "")
            item = comparison_combo.model().item(index)
            if item is not None:
                item.setEnabled(
                    ruleset_id in available_ids
                    and self._ols_pair_available(baseline_id, ruleset_id)
                )

    @staticmethod
    def _ols_pair_available(baseline_id: str, comparison_id: str) -> bool:
        """Return whether the current comparison adapter supports the pair."""
        if not comparison_id:
            return True
        return baseline_id != comparison_id

    def _on_ols_ruleset_selection_changed(self, *_args) -> None:
        self._update_comparison_ols_ruleset_items()
        self._sync_legacy_ols_policy()
        self._update_ols_workflow_ui()
        if hasattr(self, "update_dialog_status"):
            self.update_dialog_status()

    def _set_ols_ruleset_selection(self, baseline_id, comparison_id="") -> None:
        """Apply saved explicit OLS ruleset IDs to the selector pair."""
        baseline_combo = getattr(self, "baseline_ols_ruleset_combo", None)
        comparison_combo = getattr(self, "comparison_ols_ruleset_combo", None)
        if baseline_combo is None or comparison_combo is None:
            return
        baseline_id = str(baseline_id or DEFAULT_RULESET_ID)
        comparison_id = str(comparison_id or "")
        baseline_index = baseline_combo.findData(baseline_id)
        if baseline_index < 0 or baseline_id not in getattr(self, "_available_ols_ruleset_ids", set()):
            baseline_index = baseline_combo.findData(DEFAULT_RULESET_ID)
        baseline_blocked = baseline_combo.blockSignals(True)
        comparison_blocked = comparison_combo.blockSignals(True)
        baseline_combo.setCurrentIndex(max(0, baseline_index))
        comparison_index = comparison_combo.findData(comparison_id)
        comparison_combo.setCurrentIndex(comparison_index if comparison_index >= 0 else 0)
        baseline_combo.blockSignals(baseline_blocked)
        comparison_combo.blockSignals(comparison_blocked)
        self._update_comparison_ols_ruleset_items()
        self._sync_legacy_ols_policy()
        self._update_ols_workflow_ui()

    def _update_ols_workflow_ui(self, *_args, dependency_status=None, runway_count=None):
        """Apply mode-specific guidance, controls, and inline readiness state."""
        baseline_id, comparison_id = self._current_ols_ruleset_ids()
        count = len(getattr(self, "_runway_groups", {})) if runway_count is None else int(runway_count)
        baseline_profile = get_ruleset_profile(baseline_id)
        comparison_profile = get_ruleset_profile(comparison_id) if comparison_id else None
        if comparison_profile is None:
            description_text = self.tr(
                f"{baseline_profile.display_name} baseline for {count} runway(s), with no comparison. Standard workload."
            )
        else:
            description_text = self.tr(
                f"{baseline_profile.display_name} baseline compared with {comparison_profile.display_name} "
                f"for {count} runway(s). Highest workload."
            )
        if hasattr(self, "label_olsModeDescription"):
            self.label_olsModeDescription.setText(description_text)
        modernised_id = "icao_annex14_vol1_modernised_ofs_oes"
        annex_selected = modernised_id in {baseline_id, comparison_id}
        if hasattr(self, "frame_olsFamilyExplanation"):
            self.frame_olsFamilyExplanation.setVisible(annex_selected)

        checkbox = getattr(self, "checkBox_generateControllingOls", None)
        if checkbox is not None:
            comparison_required = bool(comparison_id)
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
                self.tr("Required because comparison polygons use both solved controlling envelopes.")
                if comparison_required
                else self.tr("Include solved controlling regions, transitions, and clipped controlling contours.")
            )
        controlling_group = getattr(self, "groupBox_controllingOls", None)
        if controlling_group is not None:
            controlling_group.setTitle(self.tr("Generated Outputs"))
        contour_group = getattr(self, "groupBox_contourIntervals", None)
        if contour_group is not None:
            contour_group.setTitle(
                self.tr("Contours — Baseline and Comparison")
                if comparison_id
                else self.tr("Contours — Baseline OLS")
            )

        overrides_button = getattr(self, "toolButtonContourOverrides", None)
        if overrides_button is not None:
            overrides_button.setVisible(True)
        overrides_widget = getattr(self, "widgetContourOverrides", None)
        if overrides_widget is not None:
            overrides_widget.setVisible(
                bool(overrides_button and overrides_button.isChecked())
            )

        baseline_is_annex = (
            getattr(baseline_profile, "protected_airspace_model", "")
            == "annex14_modernised_ofs_oes"
        )
        comparison_is_annex = (
            comparison_profile is not None
            and getattr(comparison_profile, "protected_airspace_model", "")
            == "annex14_modernised_ofs_oes"
        )
        baseline_keys = set(
            ANNEX14_SURFACE_CONTOUR_KEYS
            if baseline_is_annex
            else CONVENTIONAL_SURFACE_CONTOUR_KEYS
        )
        comparison_keys = (
            {
                f"comparison_{key}"
                for key in (
                    ANNEX14_SURFACE_CONTOUR_KEYS
                    if comparison_is_annex
                    else CONVENTIONAL_SURFACE_CONTOUR_KEYS
                )
            }
            if comparison_profile is not None
            else set()
        )
        visible_keys = baseline_keys | comparison_keys
        if comparison_profile is not None and annex_selected:
            visible_keys.update(MODERNISATION_CHANGE_CONTOUR_KEYS)

        header_labels = getattr(self, "_contour_column_headers", {})
        if "baseline" in header_labels:
            header_labels["baseline"].setText(
                self.tr(f"Baseline OLS — {baseline_profile.display_name}")
            )
        if "comparison" in header_labels:
            header_labels["comparison"].setText(
                self.tr(f"Comparison OLS — {comparison_profile.display_name}")
                if comparison_profile is not None
                else self.tr("Comparison OLS — None")
            )
        empty_labels = getattr(self, "_contour_column_empty_labels", {})
        if "baseline" in empty_labels:
            empty_labels["baseline"].setVisible(False)
        if "comparison" in empty_labels:
            empty_labels["comparison"].setVisible(comparison_profile is None)
        for label in getattr(self, "_contour_column_interval_headers", {}).get(
            "comparison", ()
        ):
            label.setVisible(comparison_profile is not None)
        for label in getattr(self, "_contour_change_section_labels", []):
            label.setVisible(comparison_profile is not None and annex_selected)
        annex_sections = getattr(self, "_contour_annex_section_labels", {})
        for label in annex_sections.get("baseline", {}).values():
            label.setVisible(baseline_is_annex)
        for label in annex_sections.get("comparison", {}).values():
            label.setVisible(comparison_is_annex)

        for key, label in getattr(self, "_contour_interval_labels", {}).items():
            visible = key in visible_keys
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

        overrides_button = getattr(self, "toolButtonContourOverrides", None)
        if overrides_button is None:
            overrides_button = QtWidgets.QToolButton()
            overrides_button.setObjectName("toolButtonContourOverrides")
            overrides_button.setText(self.tr("Individual contour settings"))
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
            grid.addWidget(overrides_button, 2, 0, 1, 4)
            self.toolButtonContourOverrides = overrides_button

        overrides_widget = getattr(self, "widgetContourOverrides", None)
        if overrides_widget is None:
            overrides_widget = QtWidgets.QWidget(group)
            overrides_widget.setObjectName("widgetContourOverrides")
            overrides_grid = QtWidgets.QGridLayout(overrides_widget)
            overrides_grid.setObjectName("gridLayoutContourOverrides")
            overrides_grid.setContentsMargins(0, 2, 0, 2)
            overrides_grid.setHorizontalSpacing(12)
            overrides_grid.setVerticalSpacing(0)
            overrides_grid.setColumnStretch(0, 1)
            overrides_grid.setColumnStretch(1, 1)
            grid.addWidget(overrides_widget, 3, 0, 1, 4)
            self.widgetContourOverrides = overrides_widget
            self.gridLayoutContourOverrides = overrides_grid
        else:
            overrides_grid = overrides_widget.layout()

        self._contour_column_widgets = {}
        self._contour_column_headers = {}
        self._contour_column_interval_headers = {}
        self._contour_column_empty_labels = {}
        self._contour_annex_section_labels = {}
        self._contour_change_section_labels = []
        surface_rows = {}
        next_row = 2
        for key in CONVENTIONAL_SURFACE_CONTOUR_KEYS + ANNEX14_FAMILY_CONTOUR_KEYS:
            surface_rows[key] = next_row
            next_row += 1
        annex_section_rows = {"OES": next_row}
        next_row += 1
        for key in ANNEX14_OES_SURFACE_CONTOUR_KEYS:
            surface_rows[key] = next_row
            next_row += 1
        annex_section_rows["OFS"] = next_row
        next_row += 1
        for key in ANNEX14_OFS_SURFACE_CONTOUR_KEYS:
            surface_rows[key] = next_row
            next_row += 1
        change_section_row = next_row
        column_grids = {}
        for column, role in enumerate(("baseline", "comparison")):
            title = (
                self.tr("Baseline OLS")
                if role == "baseline"
                else self.tr("Comparison OLS")
            )
            frame = QtWidgets.QFrame(overrides_widget)
            frame.setObjectName(f"frame{role.title()}ContourSettings")
            frame.setStyleSheet(
                f"QFrame#frame{role.title()}ContourSettings {{ background: #f5f8fb; "
                "border: 1px solid #d9e2ea; border-radius: 4px; }"
            )
            column_grid = QtWidgets.QGridLayout(frame)
            column_grid.setObjectName(f"gridLayout{role.title()}ContourSettings")
            column_grid.setContentsMargins(10, 8, 10, 8)
            column_grid.setHorizontalSpacing(10)
            column_grid.setVerticalSpacing(5)
            column_grid.setColumnStretch(0, 1)
            column_grid.setColumnStretch(1, 0)
            column_grid.setColumnStretch(2, 0)
            column_grid.setRowStretch(
                change_section_row + len(MODERNISATION_CHANGE_CONTOUR_KEYS) + 1,
                1,
            )
            ruleset_header = QtWidgets.QLabel(title)
            ruleset_header.setObjectName(f"label{role.title()}ContourRuleset")
            ruleset_header.setWordWrap(True)
            ruleset_header.setStyleSheet("font-weight: 600; color: #234b68;")
            primary = QtWidgets.QLabel(self.tr("Primary"))
            primary.setStyleSheet("color: #59636e; font-size: 10px;")
            intermediate = QtWidgets.QLabel(self.tr("Intermediate"))
            intermediate.setStyleSheet("color: #59636e; font-size: 10px;")
            empty = QtWidgets.QLabel(self.tr("No comparison selected — baseline only."))
            empty.setObjectName(f"label{role.title()}ContourEmpty")
            empty.setWordWrap(True)
            empty.setStyleSheet("color: #6b7580; padding: 8px 0;")
            column_grid.addWidget(ruleset_header, 0, 0, 1, 3)
            column_grid.addWidget(primary, 1, 1)
            column_grid.addWidget(intermediate, 1, 2)
            column_grid.addWidget(empty, 2, 0, 1, 3)
            annex_labels = {}
            for family, section_row in annex_section_rows.items():
                section_label = QtWidgets.QLabel(self.tr(family))
                section_label.setObjectName(
                    f"label{role.title()}Annex14{family}ContourSection"
                )
                section_label.setStyleSheet(
                    "font-weight: 600; color: #234b68; padding-top: 4px;"
                )
                column_grid.addWidget(section_label, section_row, 0, 1, 3)
                annex_labels[family] = section_label
            overrides_grid.addWidget(frame, 0, column)
            self._contour_column_widgets[role] = frame
            self._contour_column_headers[role] = ruleset_header
            self._contour_column_interval_headers[role] = (primary, intermediate)
            self._contour_column_empty_labels[role] = empty
            self._contour_annex_section_labels[role] = annex_labels
            column_grids[role] = column_grid
            setattr(self, f"frame{role.title()}ContourSettings", frame)
            setattr(self, f"label{role.title()}ContourRuleset", ruleset_header)
            setattr(self, f"label{role.title()}ContourEmpty", empty)

        overrides_button.toggled.connect(self._toggle_contour_overrides)
        self._toggle_contour_overrides(overrides_button.isChecked())

        for key in CONTOUR_INTERVAL_KEYS:
            is_change = key in MODERNISATION_CHANGE_CONTOUR_KEYS
            if key.startswith("comparison_") or is_change:
                role = "comparison"
                base_key = key.removeprefix("comparison_")
            else:
                role = "baseline"
                base_key = key
            target_grid = column_grids[role]
            if is_change and not self._contour_change_section_labels:
                change_header = QtWidgets.QLabel(self.tr("Signed change contours"))
                change_header.setObjectName("labelComparisonChangeContourSettings")
                change_header.setStyleSheet(
                    "font-weight: 600; color: #234b68; padding-top: 4px;"
                )
                target_grid.addWidget(change_header, change_section_row, 0, 1, 3)
                self._contour_change_section_labels.append(change_header)
            row = (
                change_section_row
                + 1
                + list(MODERNISATION_CHANGE_CONTOUR_KEYS).index(key)
                if is_change
                else surface_rows[base_key]
            )
            label_name = f"labelContour{key.title()}"
            primary_spin_name = f"doubleSpinBoxContour{key.title()}Primary"
            intermediate_spin_name = f"doubleSpinBoxContour{key.title()}Intermediate"
            label = getattr(self, label_name, None)
            if label is None:
                label = QtWidgets.QLabel(self.tr(CONTOUR_INTERVAL_LABELS[key]))
                label.setObjectName(label_name)
                target_grid.addWidget(label, row, 0)
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
            target_grid.addWidget(primary_spinbox, row, 1)
            target_grid.addWidget(intermediate_spinbox, row, 2)

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
                self.tr("Hide individual baseline and comparison contour intervals.")
                if expanded
                else self.tr("Show individual baseline and comparison contour intervals.")
            )
        if widget is not None:
            widget.setVisible(bool(expanded))

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
        key = key.removeprefix("comparison_")
        label = CONTOUR_INTERVAL_LABELS.get(key, key.replace("_", " ").title())
        family_note = ""
        if key == "annex14_ofs":
            family_note = " Overrides Annex 14 obstacle free surface contours after surface-level defaults."
        elif key == "annex14_oes":
            family_note = " Overrides Annex 14 obstacle evaluation surface contours after surface-level defaults."
        elif key.startswith("annex14_ofs_"):
            family_note = " Controls this Annex 14 obstacle free surface only."
        elif key.startswith("annex14_oes_"):
            family_note = " Controls this Annex 14 obstacle evaluation surface only."
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
        for key in CONTOUR_INTERVAL_KEYS:
            key_defaults = CONTOUR_INTERVAL_KEY_DEFAULTS.get(key, {})
            source_key = self._contour_interval_source_key(contour_options, key)
            primary_value = self._coerce_contour_interval_value(
                contour_options,
                source_key,
                "primary",
                key_defaults.get("primary", default_primary),
            )
            intermediate_value = self._coerce_contour_interval_value(
                contour_options,
                source_key,
                "intermediate",
                key_defaults.get("intermediate", default_intermediate),
            )
            if key in primary_spinboxes:
                primary_spinboxes[key].setValue(primary_value)
            if key in intermediate_spinboxes:
                intermediate_spinboxes[key].setValue(intermediate_value)
        has_surface_overrides = any(
            abs(primary_spinboxes[key].value() - default_primary) > 1e-9
            or abs(intermediate_spinboxes[key].value() - default_intermediate) > 1e-9
            for key in CONTOUR_INTERVAL_KEYS
            if key not in MODERNISATION_CHANGE_CONTOUR_KEYS
            if key in primary_spinboxes and key in intermediate_spinboxes
        )
        if hasattr(self, "toolButtonContourOverrides"):
            self.toolButtonContourOverrides.setChecked(has_surface_overrides)

    @staticmethod
    def _contour_interval_source_key(contour_options, key: str) -> str:
        """Return the saved key to use, including legacy Annex family fallbacks."""
        if key in contour_options:
            return key
        comparison = key.startswith("comparison_")
        base_key = key.removeprefix("comparison_")
        candidates = []
        if base_key.startswith("annex14_oes_"):
            candidates.append("comparison_annex14_oes" if comparison else "annex14_oes")
            if comparison:
                candidates.append("annex14_oes")
        elif base_key.startswith("annex14_ofs_"):
            candidates.append("comparison_annex14_ofs" if comparison else "annex14_ofs")
            if comparison:
                candidates.append("annex14_ofs")
        elif comparison and key in COMPARISON_SURFACE_CONTOUR_KEYS:
            candidates.append(base_key)
        return next(
            (candidate for candidate in candidates if candidate in contour_options),
            key,
        )

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
