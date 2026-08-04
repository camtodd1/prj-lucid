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

        group = QtWidgets.QGroupBox("OpenTopography DEM download")
        group.setObjectName("groupBox_dem_tools")
        group_layout = QtWidgets.QVBoxLayout(group)
        group_layout.setContentsMargins(10, 12, 10, 10)
        group_layout.setSpacing(8)

        description = QtWidgets.QLabel(
            "Choose a project layer whose extent should be supplied to the "
            "OpenTopography DEM Downloader."
        )
        description.setObjectName("label_dem_description")
        description.setWordWrap(True)
        group_layout.addWidget(description)

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

        self.pushButton_DownloadDem = QtWidgets.QPushButton(
            "Open DEM downloader…"
        )
        self.pushButton_DownloadDem.setObjectName("pushButton_DownloadDem")
        self.pushButton_DownloadDem.setMinimumHeight(32)
        group_layout.addWidget(
            self.pushButton_DownloadDem,
            0,
            QtCore.Qt.AlignmentFlag.AlignRight,
        )

        layout.addWidget(group)
        layout.addStretch(1)
        self.groupBox_dem_tools = group
        tab_widget.addTab(self.tab_terrain, "Terrain")

        self.comboBox_dem_extent_layer.layerChanged.connect(
            self.refresh_dem_tool_state
        )
        self.refresh_dem_tool_state()

    def selected_dem_extent_layer(self):
        combo = getattr(self, "comboBox_dem_extent_layer", None)
        return combo.currentLayer() if combo is not None else None

    def refresh_dem_tool_state(self, *_args) -> None:
        status = getattr(self, "label_dem_tool_status", None)
        button = getattr(self, "pushButton_DownloadDem", None)
        if status is None or button is None:
            return

        if open_topography_algorithm() is None:
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

        status.setText(
            "Ready. The selected layer extent will be pre-filled in the downloader."
        )
        status.setStyleSheet("color: #356b3d;")
        button.setEnabled(True)
        button.setToolTip(
            "Open the OpenTopography downloader with this layer as its extent."
        )
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
