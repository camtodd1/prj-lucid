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

        group = QtWidgets.QGroupBox("Terrain data source")
        group.setObjectName("groupBox_dem_tools")
        group_layout = QtWidgets.QVBoxLayout(group)
        group_layout.setContentsMargins(10, 12, 10, 10)
        group_layout.setSpacing(8)

        description = QtWidgets.QLabel(
            "Download Australian bare-earth terrain directly from Geoscience "
            "Australia, or use OpenTopography for global datasets."
        )
        description.setObjectName("label_dem_description")
        description.setWordWrap(True)
        group_layout.addWidget(description)

        source_row = QtWidgets.QHBoxLayout()
        source_row.setSpacing(8)
        source_label = QtWidgets.QLabel("Terrain source")
        self.comboBox_dem_source = QtWidgets.QComboBox(group)
        self.comboBox_dem_source.setObjectName("comboBox_dem_source")
        self.comboBox_dem_source.addItem(
            "GA best available (5 m, then 30 m)", "ga_best"
        )
        self.comboBox_dem_source.addItem(
            "GA LiDAR bare-earth DEM 5 m", "ga_lidar_5m"
        )
        self.comboBox_dem_source.addItem(
            "GA SRTM bare-earth DEM 30 m", "ga_srtm_30m"
        )
        self.comboBox_dem_source.addItem(
            "OpenTopography DEM Downloader…", "open_topography"
        )
        source_row.addWidget(source_label)
        source_row.addWidget(self.comboBox_dem_source, 1)
        group_layout.addLayout(source_row)

        extent_row = QtWidgets.QHBoxLayout()
        extent_row.setSpacing(8)
        extent_label = QtWidgets.QLabel("Extent layer")
        extent_label.setObjectName("label_dem_extent_layer")
        extent_row.addWidget(extent_label)

        self.comboBox_dem_extent_layer = QgsMapLayerComboBox(group)
        self.comboBox_dem_extent_layer.setObjectName("comboBox_dem_extent_layer")
        self.comboBox_dem_extent_layer.setAllowEmptyLayer(True)
        self.comboBox_dem_extent_layer.setFilters(QgsMapLayerProxyModel.VectorLayer)
        extent_row.addWidget(self.comboBox_dem_extent_layer, 1)
        group_layout.addLayout(extent_row)

        self.label_dem_tool_status = QtWidgets.QLabel()
        self.label_dem_tool_status.setObjectName("label_dem_tool_status")
        self.label_dem_tool_status.setWordWrap(True)
        group_layout.addWidget(self.label_dem_tool_status)

        self.pushButton_DownloadDem = QtWidgets.QPushButton("Download terrain")
        self.pushButton_DownloadDem.setObjectName("pushButton_DownloadDem")
        self.pushButton_DownloadDem.setMinimumHeight(32)
        group_layout.addWidget(
            self.pushButton_DownloadDem,
            0,
            QtCore.Qt.AlignmentFlag.AlignRight,
        )

        layout.addWidget(group)

        contour_group = QtWidgets.QGroupBox("Elevation polygons")
        contour_group.setObjectName("groupBox_dem_contours")
        contour_layout = QtWidgets.QGridLayout(contour_group)
        contour_layout.setContentsMargins(10, 12, 10, 10)
        contour_layout.setHorizontalSpacing(12)
        contour_layout.setVerticalSpacing(8)

        self.label_downloaded_dem = QtWidgets.QLabel(
            "Download a DEM to enable elevation polygons."
        )
        self.label_downloaded_dem.setObjectName("label_downloaded_dem")
        self.label_downloaded_dem.setWordWrap(True)
        contour_layout.addWidget(self.label_downloaded_dem, 0, 0, 1, 2)

        interval_label = QtWidgets.QLabel("Elevation interval")
        self.doubleSpinBox_dem_contour_interval = QtWidgets.QDoubleSpinBox()
        self.doubleSpinBox_dem_contour_interval.setObjectName(
            "doubleSpinBox_dem_contour_interval"
        )
        self.doubleSpinBox_dem_contour_interval.setRange(0.1, 1000.0)
        self.doubleSpinBox_dem_contour_interval.setDecimals(1)
        self.doubleSpinBox_dem_contour_interval.setValue(5.0)
        self.doubleSpinBox_dem_contour_interval.setSuffix(" m")
        contour_layout.addWidget(interval_label, 1, 0)
        contour_layout.addWidget(self.doubleSpinBox_dem_contour_interval, 1, 1)

        output_label = QtWidgets.QLabel("Polygon output")
        self.comboBox_dem_contour_output = QtWidgets.QComboBox()
        self.comboBox_dem_contour_output.setObjectName(
            "comboBox_dem_contour_output"
        )
        self.comboBox_dem_contour_output.addItem("Temporary layer", "temporary")
        self.comboBox_dem_contour_output.addItem("Save GeoPackage", "file")
        contour_layout.addWidget(output_label, 2, 0)
        contour_layout.addWidget(self.comboBox_dem_contour_output, 2, 1)

        self.label_dem_contour_status = QtWidgets.QLabel()
        self.label_dem_contour_status.setObjectName("label_dem_contour_status")
        self.label_dem_contour_status.setWordWrap(True)
        contour_layout.addWidget(self.label_dem_contour_status, 3, 0, 1, 2)

        datum_note = QtWidgets.QLabel(
            "Before comparing terrain with OLS elevations, confirm that the "
            "DEM vertical datum is compatible with the airport AMSL datum."
        )
        datum_note.setObjectName("label_dem_vertical_datum_note")
        datum_note.setWordWrap(True)
        datum_note.setStyleSheet("color: #8a4b08;")
        self.label_dem_vertical_datum_note = datum_note
        contour_layout.addWidget(datum_note, 4, 0, 1, 2)

        self.pushButton_CreateDemContours = QtWidgets.QPushButton(
            "Create elevation polygons"
        )
        self.pushButton_CreateDemContours.setObjectName(
            "pushButton_CreateDemContours"
        )
        self.pushButton_CreateDemContours.setMinimumHeight(32)
        self.pushButton_CreateDemContours.setEnabled(False)
        contour_layout.addWidget(
            self.pushButton_CreateDemContours,
            5,
            0,
            1,
            2,
            QtCore.Qt.AlignmentFlag.AlignRight,
        )

        self._downloaded_dem_source = None
        self.groupBox_dem_contours = contour_group
        layout.addWidget(contour_group)
        layout.addStretch(1)
        self.groupBox_dem_tools = group
        tab_widget.addTab(self.tab_terrain, "Terrain")

        self.comboBox_dem_extent_layer.layerChanged.connect(
            self.refresh_dem_tool_state
        )
        self.comboBox_dem_source.currentIndexChanged.connect(
            self.refresh_dem_tool_state
        )
        self.refresh_dem_tool_state()

    def selected_dem_extent_layer(self):
        combo = getattr(self, "comboBox_dem_extent_layer", None)
        return combo.currentLayer() if combo is not None else None

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

        source_key = self.selected_dem_source()
        is_open_topography = source_key == "open_topography"
        button.setText(
            "Open DEM downloader…" if is_open_topography else "Download terrain"
        )

        if is_open_topography and open_topography_algorithm() is None:
            status.setText(
                "OpenTopography DEM Downloader is not installed or enabled."
            )
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

        if self.selected_dem_extent_layer() is None:
            status.setText("Select a vector layer to define the download extent.")
            status.setStyleSheet("color: #56616d;")
            button.setEnabled(False)
            button.setToolTip("Select an extent layer first.")
            self._set_dem_workflow_state(
                "Select layer",
                "optional",
                "Select a vector layer to define the optional DEM download extent.",
            )
            return

        if is_open_topography:
            status.setText(
                "Ready. The selected layer extent will be pre-filled in the downloader."
            )
            tooltip = "Open the OpenTopography downloader with this layer as its extent."
        elif source_key == "ga_best":
            status.setText(
                "Ready. GA 5 m LiDAR will be used where available, with 30 m terrain fallback."
            )
            tooltip = "Download the best available GA bare-earth DEM for this extent."
        else:
            resolution = "5 m LiDAR" if source_key == "ga_lidar_5m" else "30 m SRTM"
            status.setText(f"Ready to download GA {resolution} terrain for this extent.")
            tooltip = f"Download GA {resolution} bare-earth terrain."
        status.setStyleSheet("color: #356b3d;")
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
