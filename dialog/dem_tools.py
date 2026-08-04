"""Dock widgets for optional DEM acquisition tools."""

from qgis.PyQt import QtCore, QtWidgets  # type: ignore
from qgis.core import QgsMapLayerProxyModel  # type: ignore
from qgis.gui import QgsMapLayerComboBox  # type: ignore

try:
    from ..core.dem_integration import open_topography_algorithm
except ImportError:
    from core.dem_integration import open_topography_algorithm  # type: ignore


class DemToolsMixin:
    """Build and maintain the optional Terrain/DEM dock tab."""

    def _setup_dem_tools_ui(self) -> None:
        tab_widget = getattr(self, "tabWidget_workflow", None)
        if tab_widget is None:
            return

        self.tab_terrain = QtWidgets.QWidget()
        self.tab_terrain.setObjectName("tab_terrain")
        layout = QtWidgets.QVBoxLayout(self.tab_terrain)
        layout.setObjectName("verticalLayout_terrainTab")
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)
        layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignTop)

        group = QtWidgets.QGroupBox("Terrain workflow")
        group.setObjectName("groupBox_dem_tools")
        group_layout = QtWidgets.QGridLayout(group)
        group_layout.setContentsMargins(10, 12, 10, 10)
        group_layout.setHorizontalSpacing(10)
        group_layout.setVerticalSpacing(10)
        group_layout.setColumnMinimumWidth(0, 200)
        group_layout.setColumnStretch(1, 1)

        download_heading = QtWidgets.QLabel("1  Download terrain")
        download_heading.setStyleSheet("font-weight: 600;")
        group_layout.addWidget(download_heading, 0, 0, 1, 3)

        source_label = QtWidgets.QLabel("Terrain source")
        self.comboBox_dem_source = QtWidgets.QComboBox(group)
        self.comboBox_dem_source.setObjectName("comboBox_dem_source")
        self.comboBox_dem_source.setFixedHeight(26)
        self.comboBox_dem_source.addItem(
            "GA best available (5 m, then 30 m)", "ga_best"
        )
        self.comboBox_dem_source.addItem("GA LiDAR bare-earth DEM 5 m", "ga_lidar_5m")
        self.comboBox_dem_source.addItem("GA SRTM bare-earth DEM 30 m", "ga_srtm_30m")
        self.comboBox_dem_source.addItem(
            "OpenTopography DEM Downloader…", "open_topography"
        )
        group_layout.addWidget(source_label, 1, 0)
        group_layout.addWidget(self.comboBox_dem_source, 1, 1, 1, 2)

        extent_label = QtWidgets.QLabel("OLS coverage")

        self.frame_dem_extent_auto = QtWidgets.QFrame(group)
        self.frame_dem_extent_auto.setObjectName("frame_dem_extent_auto")
        self.frame_dem_extent_auto.setStyleSheet(
            "QFrame#frame_dem_extent_auto { background: #f7f8fa; "
            "border: 1px solid #c9cdd2; border-radius: 4px; }"
        )
        self.frame_dem_extent_auto.setFixedHeight(26)
        auto_layout = QtWidgets.QHBoxLayout(self.frame_dem_extent_auto)
        auto_layout.setContentsMargins(9, 5, 9, 5)
        auto_text = QtWidgets.QLabel("Automatic — OLS square", self.frame_dem_extent_auto)
        auto_text.setStyleSheet("color: #343a40;")
        auto_layout.addWidget(auto_text)
        auto_layout.addStretch(1)

        self.pushButton_dem_extent_override = QtWidgets.QPushButton(
            "Override…"
        )
        self.pushButton_dem_extent_override.setObjectName(
            "pushButton_dem_extent_override"
        )
        self.pushButton_dem_extent_override.setCheckable(True)
        self.pushButton_dem_extent_override.setFixedHeight(26)
        self.pushButton_dem_extent_override.setFixedWidth(126)
        self.pushButton_dem_extent_override.setToolTip(
            "Override the automatic square enclosing all generated OLS layers."
        )
        self.comboBox_dem_extent_layer = QgsMapLayerComboBox(group)
        self.comboBox_dem_extent_layer.setObjectName("comboBox_dem_extent_layer")
        self.comboBox_dem_extent_layer.setAllowEmptyLayer(True)
        self.comboBox_dem_extent_layer.setFilters(QgsMapLayerProxyModel.VectorLayer)
        self.comboBox_dem_extent_layer.setVisible(False)
        self.comboBox_dem_extent_layer.setFixedHeight(26)
        self.widget_dem_extent_row = QtWidgets.QWidget(group)
        self.widget_dem_extent_row.setObjectName("widget_dem_extent_row")
        extent_row_layout = QtWidgets.QHBoxLayout(self.widget_dem_extent_row)
        extent_row_layout.setContentsMargins(0, 0, 0, 0)
        extent_row_layout.setSpacing(10)
        extent_row_layout.addWidget(self.frame_dem_extent_auto, 1)
        extent_row_layout.addWidget(self.comboBox_dem_extent_layer, 1)
        extent_row_layout.addWidget(self.pushButton_dem_extent_override)
        group_layout.addWidget(extent_label, 2, 0)
        group_layout.addWidget(
            self.widget_dem_extent_row,
            2,
            1,
            1,
            2,
        )

        self.label_dem_tool_status = QtWidgets.QLabel()
        self.label_dem_tool_status.setObjectName("label_dem_tool_status")
        self.label_dem_tool_status.setWordWrap(True)
        self.label_dem_tool_status.setVisible(False)
        group_layout.addWidget(self.label_dem_tool_status, 3, 1, 1, 2)

        divider = QtWidgets.QFrame(group)
        divider.setFrameShape(QtWidgets.QFrame.Shape.HLine)
        divider.setFrameShadow(QtWidgets.QFrame.Shadow.Sunken)
        group_layout.addWidget(divider, 4, 0, 1, 3)

        self.pushButton_DownloadDem = QtWidgets.QPushButton("Download terrain")
        self.pushButton_DownloadDem.setObjectName("pushButton_DownloadDem")
        self.pushButton_DownloadDem.setFixedHeight(32)
        self.pushButton_DownloadDem.setFixedWidth(198)
        self.pushButton_DownloadDem.setStyleSheet(
            "QPushButton { background: #1769c2; color: white; border: 1px solid #125aa8; "
            "border-radius: 4px; padding: 7px 14px; font-weight: 600; }"
            "QPushButton:hover { background: #125da9; }"
            "QPushButton:pressed { background: #0f4f91; }"
            "QPushButton:disabled { background: #d7dbe0; color: #7c838a; border-color: #c8ccd1; }"
        )
        group_layout.addWidget(
            self.pushButton_DownloadDem,
            5,
            2,
            QtCore.Qt.AlignmentFlag.AlignRight,
        )

        workflow_divider = QtWidgets.QFrame(group)
        workflow_divider.setFrameShape(QtWidgets.QFrame.Shape.HLine)
        workflow_divider.setFrameShadow(QtWidgets.QFrame.Shadow.Sunken)
        group_layout.addWidget(workflow_divider, 6, 0, 1, 3)

        polygon_heading = QtWidgets.QLabel("2  Create elevation polygons")
        polygon_heading.setStyleSheet("font-weight: 600;")
        group_layout.addWidget(polygon_heading, 7, 0, 1, 3)

        self.label_downloaded_dem = QtWidgets.QLabel(
            "Available after terrain has been downloaded."
        )
        self.label_downloaded_dem.setObjectName("label_downloaded_dem")
        self.label_downloaded_dem.setWordWrap(True)
        self.label_downloaded_dem.setStyleSheet("color: #56616d;")
        group_layout.addWidget(self.label_downloaded_dem, 8, 0, 1, 3)

        interval_label = QtWidgets.QLabel("Elevation interval")
        self.doubleSpinBox_dem_contour_interval = QtWidgets.QDoubleSpinBox()
        self.doubleSpinBox_dem_contour_interval.setObjectName(
            "doubleSpinBox_dem_contour_interval"
        )
        self.doubleSpinBox_dem_contour_interval.setRange(0.1, 1000.0)
        self.doubleSpinBox_dem_contour_interval.setDecimals(1)
        self.doubleSpinBox_dem_contour_interval.setValue(5.0)
        self.doubleSpinBox_dem_contour_interval.setSuffix(" m")
        self.doubleSpinBox_dem_contour_interval.setEnabled(False)
        group_layout.addWidget(interval_label, 9, 0)
        group_layout.addWidget(self.doubleSpinBox_dem_contour_interval, 9, 1, 1, 2)

        output_label = QtWidgets.QLabel("Polygon output")
        self.comboBox_dem_contour_output = QtWidgets.QComboBox()
        self.comboBox_dem_contour_output.setObjectName(
            "comboBox_dem_contour_output"
        )
        self.comboBox_dem_contour_output.addItem("Temporary layer", "temporary")
        self.comboBox_dem_contour_output.addItem("Save GeoPackage", "file")
        self.comboBox_dem_contour_output.setEnabled(False)
        group_layout.addWidget(output_label, 10, 0)
        group_layout.addWidget(self.comboBox_dem_contour_output, 10, 1, 1, 2)

        self.label_dem_contour_status = QtWidgets.QLabel()
        self.label_dem_contour_status.setObjectName("label_dem_contour_status")
        self.label_dem_contour_status.setWordWrap(True)
        group_layout.addWidget(self.label_dem_contour_status, 11, 0, 1, 3)

        datum_frame = QtWidgets.QFrame(group)
        datum_frame.setObjectName("frame_dem_vertical_datum_note")
        datum_frame.setStyleSheet(
            "QFrame#frame_dem_vertical_datum_note { color: #7a4b00; "
            "background: #fff8e8; border: 1px solid #ecd49b; "
            "border-radius: 4px; }"
        )
        datum_layout = QtWidgets.QVBoxLayout(datum_frame)
        datum_layout.setContentsMargins(8, 6, 8, 6)
        datum_note = QtWidgets.QLabel(
            "Vertical datum must match the airport AMSL datum.", datum_frame
        )
        datum_note.setObjectName("label_dem_vertical_datum_note")
        datum_note.setWordWrap(True)
        datum_note.setStyleSheet("border: none; background: transparent;")
        datum_layout.addWidget(datum_note)
        self.label_dem_vertical_datum_note = datum_note
        group_layout.addWidget(datum_frame, 12, 0, 1, 3)

        self.pushButton_CreateDemContours = QtWidgets.QPushButton(
            "Create elevation polygons"
        )
        self.pushButton_CreateDemContours.setObjectName(
            "pushButton_CreateDemContours"
        )
        self.pushButton_CreateDemContours.setFixedHeight(32)
        self.pushButton_CreateDemContours.setFixedWidth(198)
        self.pushButton_CreateDemContours.setEnabled(False)
        group_layout.addWidget(
            self.pushButton_CreateDemContours,
            13,
            2,
            QtCore.Qt.AlignmentFlag.AlignRight,
        )

        self._downloaded_dem_source = None
        self.groupBox_dem_tools = group
        layout.addWidget(group)
        layout.addStretch(1)
        tab_widget.addTab(self.tab_terrain, "Terrain")

        self.comboBox_dem_extent_layer.layerChanged.connect(
            self.refresh_dem_tool_state
        )
        self.comboBox_dem_source.currentIndexChanged.connect(
            self.refresh_dem_tool_state
        )
        self.pushButton_dem_extent_override.toggled.connect(
            self._toggle_dem_extent_override
        )
        self.refresh_dem_tool_state()

    def selected_dem_extent_layer(self):
        override = getattr(self, "pushButton_dem_extent_override", None)
        if override is None or not override.isChecked():
            return None
        combo = getattr(self, "comboBox_dem_extent_layer", None)
        return combo.currentLayer() if combo is not None else None

    def _toggle_dem_extent_override(self, enabled: bool) -> None:
        combo = getattr(self, "comboBox_dem_extent_layer", None)
        if combo is not None:
            combo.setVisible(bool(enabled))
        automatic = getattr(self, "frame_dem_extent_auto", None)
        if automatic is not None:
            automatic.setVisible(not bool(enabled))
        button = getattr(self, "pushButton_dem_extent_override", None)
        if button is not None:
            button.setText("Automatic" if enabled else "Override…")
        self.refresh_dem_tool_state()

    def selected_dem_source(self) -> str:
        combo = getattr(self, "comboBox_dem_source", None)
        return str(combo.currentData() or "ga_best") if combo is not None else "ga_best"

    def set_downloaded_dem(self, source, metadata=None) -> None:
        """Retain a completed DEM result and enable polygon processing."""
        self._downloaded_dem_source = source
        label = getattr(self, "label_downloaded_dem", None)
        button = getattr(self, "pushButton_CreateDemContours", None)
        if label is not None:
            display_name = (
                source.name()
                if hasattr(source, "name") and callable(source.name)
                else str(source)
            )
            source_label = str((metadata or {}).get("short_label", "")).strip()
            suffix = f" — {source_label}" if source_label else ""
            label.setText(f"Downloaded DEM: {display_name}{suffix}")
            label.setToolTip(str(source))
        if button is not None:
            button.setEnabled(source is not None)
        self.doubleSpinBox_dem_contour_interval.setEnabled(source is not None)
        self.comboBox_dem_contour_output.setEnabled(source is not None)
        self.set_dem_contour_status(
            "Choose an interval, then create styled elevation polygons."
        )
        datum_note = getattr(self, "label_dem_vertical_datum_note", None)
        if datum_note is not None and metadata:
            datum = str(metadata.get("vertical_datum", "Unconfirmed"))
            epsg = str(metadata.get("vertical_epsg", "")).strip()
            datum_note.setText(
                f"Vertical reference: {datum}{f' ({epsg})' if epsg else ''}. "
                "Confirm compatibility with the airport AMSL datum before OLS comparison."
            )

    def downloaded_dem_source(self):
        return getattr(self, "_downloaded_dem_source", None)

    def dem_contour_interval(self) -> float:
        widget = getattr(self, "doubleSpinBox_dem_contour_interval", None)
        return float(widget.value()) if widget is not None else 5.0

    def dem_contour_output_mode(self) -> str:
        combo = getattr(self, "comboBox_dem_contour_output", None)
        return (
            str(combo.currentData() or "temporary")
            if combo is not None
            else "temporary"
        )

    def set_dem_contour_status(self, message: str, *, error: bool = False) -> None:
        label = getattr(self, "label_dem_contour_status", None)
        if label is None:
            return
        label.setText(str(message or ""))
        label.setStyleSheet("color: #8a1f11;" if error else "color: #56616d;")

    def refresh_dem_tool_state(self, *_args) -> None:
        status = getattr(self, "label_dem_tool_status", None)
        button = getattr(self, "pushButton_DownloadDem", None)
        if status is None or button is None:
            return
        status.clear()
        status.setVisible(False)

        source_key = self.selected_dem_source()
        is_open_topography = source_key == "open_topography"
        button.setText(
            "Open DEM downloader…" if is_open_topography else "Download terrain"
        )
        if is_open_topography and open_topography_algorithm() is None:
            status.setText(
                "OpenTopography DEM Downloader is not installed or enabled."
            )
            status.setVisible(True)
            status.setStyleSheet("color: #8a4b08;")
            button.setEnabled(False)
            button.setToolTip(
                "Install or enable OpenTopography DEM Downloader in QGIS."
            )
            self._set_dem_workflow_state(
                "Unavailable",
                "optional",
                "Install or enable OpenTopography DEM Downloader to use terrain tools.",
            )
            return

        override_enabled = self.pushButton_dem_extent_override.isChecked()
        if override_enabled and self.selected_dem_extent_layer() is None:
            status.setText("Choose a custom extent layer.")
            status.setStyleSheet("color: #56616d;")
            status.setVisible(True)
            button.setEnabled(False)
            button.setToolTip("Choose a custom extent layer or use the automatic extent.")
            self._set_dem_workflow_state(
                "Select extent",
                "optional",
                "Choose a custom extent layer or return to the automatic OLS extent.",
            )
            return

        if is_open_topography:
            tooltip = "Open the downloader using the automatic or overridden extent."
        elif source_key == "ga_best":
            tooltip = "Download the best available GA bare-earth DEM for this extent."
        else:
            resolution = "5 m LiDAR" if source_key == "ga_lidar_5m" else "30 m SRTM"
            tooltip = f"Download GA {resolution} bare-earth terrain."
        button.setEnabled(True)
        button.setToolTip(tooltip)
        self._set_dem_workflow_state(
            "Ready",
            "ready",
            "A vector layer is ready to define the optional DEM download extent.",
        )

    def _set_dem_workflow_state(
        self,
        text: str,
        state: str,
        tooltip: str,
    ) -> None:
        if hasattr(self, "_set_workflow_tab_state"):
            self._set_workflow_tab_state("tab_terrain", state, tooltip)
        if hasattr(self, "_update_workflow_context_statuses"):
            self._update_workflow_context_statuses(
                {"tab_terrain": (text, state)}
            )


__all__ = ["DemToolsMixin"]
