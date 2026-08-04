"""Optional DEM download and elevation-polygon workflow controller."""

import traceback
from pathlib import Path
from typing import Optional

from qgis.PyQt.QtCore import QCoreApplication  # type: ignore
from qgis.PyQt.QtWidgets import QMessageBox, QPushButton  # type: ignore
from qgis.core import (  # type: ignore
    Qgis,
    QgsLayerTreeGroup,
    QgsProject,
    QgsRasterLayer,
    QgsVectorLayer,
)

from ..core.dem_integration import (
    apply_elevation_polygon_style,
    create_elevation_polygons,
    elevation_polygon_output_path,
    open_topography_dialog,
)


class DemIntegrationMixin:
    """Coordinate the optional Terrain tab without affecting core generation."""

    def open_dem_downloader(self):
        """Open OpenTopography and retain a successfully downloaded DEM."""
        if self.dlg is None:
            return
        extent_layer = self.dlg.selected_dem_extent_layer()
        try:
            results = open_topography_dialog(extent_layer)
            dem_result = results.get("OUTPUT") if isinstance(results, dict) else None
            if dem_result is None:
                self.dlg.set_dem_contour_status(
                    "DEM download was cancelled or produced no output."
                )
                return
            dem_layer = self._ensure_terrain_raster_layer(dem_result)
            if dem_layer is None:
                raise RuntimeError("The downloaded DEM could not be loaded.")
            self.dlg.set_downloaded_dem(dem_layer)
            self._log(f"Downloaded DEM ready: {dem_layer.source()}")
        except (RuntimeError, ValueError) as exc:
            QMessageBox.warning(
                self.dlg,
                self.tr("DEM downloader unavailable"),
                str(exc),
            )
        except Exception as exc:
            self._log_warning(
                f"Could not open OpenTopography DEM Downloader: {exc}\n"
                f"{traceback.format_exc()}"
            )
            QMessageBox.critical(
                self.dlg,
                self.tr("DEM downloader error"),
                self.tr(
                    "Could not open OpenTopography DEM Downloader. "
                    "See the QGIS log for details."
                ),
            )

    def create_dem_elevation_polygons(self):
        """Create and style optional elevation-band polygons from the DEM."""
        if self.dlg is None:
            return
        dem_source = self.dlg.downloaded_dem_source()
        if dem_source is None:
            QMessageBox.warning(
                self.dlg,
                self.tr("DEM required"),
                self.tr("Download a DEM before creating elevation polygons."),
            )
            return

        button = self.dlg.findChild(
            QPushButton,
            "pushButton_CreateDemContours",
        )
        original_text = button.text() if button is not None else ""
        if button is not None:
            button.setEnabled(False)
            button.setText(self.tr("Creating polygons…"))
        self.dlg.set_dem_contour_status("Creating elevation polygons…")
        QCoreApplication.processEvents()

        try:
            output = "TEMPORARY_OUTPUT"
            if self.dlg.dem_contour_output_mode() == "file":
                output = elevation_polygon_output_path(
                    self._terrain_source_path(dem_source),
                    self._terrain_output_directory(),
                )
            result = create_elevation_polygons(
                dem_source,
                self.dlg.dem_contour_interval(),
                output,
            )
            contour_layer = self._ensure_terrain_vector_layer(result)
            if contour_layer is None:
                raise RuntimeError("The elevation polygons could not be loaded.")
            apply_elevation_polygon_style(contour_layer)
            contour_layer.setCustomProperty(
                "safeguarding_builder/dem_source",
                self._terrain_source_path(dem_source),
            )
            contour_layer.setCustomProperty(
                "safeguarding_builder/elevation_interval_m",
                self.dlg.dem_contour_interval(),
            )
            contour_layer.setName(
                f"{self._terrain_airport_code()} Elevation Bands".strip()
            )
            self.dlg.set_dem_contour_status(
                f"Created {contour_layer.featureCount()} styled elevation polygons."
            )
            self._log(
                f"Elevation polygons ready: {contour_layer.source()} "
                f"({contour_layer.featureCount()} features)."
            )
            self.iface.messageBar().pushMessage(
                self.tr("Terrain"),
                self.tr("Elevation polygons created and styled."),
                level=Qgis.Success,
                duration=6,
            )
        except (RuntimeError, ValueError) as exc:
            self.dlg.set_dem_contour_status(str(exc), error=True)
            QMessageBox.warning(
                self.dlg,
                self.tr("Elevation polygons unavailable"),
                str(exc),
            )
        except Exception as exc:
            self.dlg.set_dem_contour_status(
                "Elevation polygon processing failed. See the QGIS log.",
                error=True,
            )
            self._log_warning(
                f"Elevation polygon processing failed: {exc}\n"
                f"{traceback.format_exc()}"
            )
            QMessageBox.critical(
                self.dlg,
                self.tr("Elevation polygon error"),
                self.tr(
                    "Could not create elevation polygons. "
                    "See the QGIS log for details."
                ),
            )
        finally:
            if button is not None:
                button.setText(original_text)
                button.setEnabled(True)

    def _terrain_airport_code(self) -> str:
        code = str(getattr(self, "icao_code", "") or "").strip().upper()
        if not code and self.dlg is not None:
            widget = getattr(self.dlg, "lineEdit_airport_name", None)
            code = widget.text().strip().upper() if widget is not None else ""
        return code

    def _terrain_output_group(self) -> QgsLayerTreeGroup:
        root = QgsProject.instance().layerTreeRoot()
        airport = self._terrain_airport_code()
        group_name = f"{airport} Terrain Analysis" if airport else "Terrain Analysis"
        group = root.findGroup(group_name) or root.addGroup(group_name)
        group.setItemVisibilityChecked(True)
        group.setExpanded(True)
        return group

    @staticmethod
    def _terrain_source_path(source) -> str:
        value = source.source() if hasattr(source, "source") else source
        return str(value or "").split("|", 1)[0]

    def _terrain_output_directory(self) -> Optional[str]:
        if self.dlg is not None:
            file_widget = getattr(self.dlg, "fileWidgetOutputPath", None)
            file_path = file_widget.filePath() if file_widget is not None else ""
            if str(file_path or "").strip():
                return str(file_path)
        return None

    def _ensure_terrain_raster_layer(self, result) -> Optional[QgsRasterLayer]:
        project = QgsProject.instance()
        layer = result if isinstance(result, QgsRasterLayer) else None
        source_path = self._terrain_source_path(result)
        if layer is None:
            for candidate in project.mapLayers().values():
                if not isinstance(candidate, QgsRasterLayer):
                    continue
                if self._terrain_source_path(candidate) == source_path:
                    layer = candidate
                    break
        if layer is None and source_path:
            layer = QgsRasterLayer(source_path, Path(source_path).stem or "DEM")
        if layer is None or not layer.isValid():
            return None
        self._place_terrain_layer(layer)
        layer.setName(f"{self._terrain_airport_code()} DEM".strip())
        layer.setCustomProperty(
            "safeguarding_builder/source_service",
            "OpenTopography",
        )
        return layer

    def _ensure_terrain_vector_layer(self, result) -> Optional[QgsVectorLayer]:
        project = QgsProject.instance()
        layer = result if isinstance(result, QgsVectorLayer) else None
        source_path = self._terrain_source_path(result)
        if layer is None:
            for candidate in project.mapLayers().values():
                if not isinstance(candidate, QgsVectorLayer):
                    continue
                if self._terrain_source_path(candidate) == source_path:
                    layer = candidate
                    break
        if layer is None and source_path:
            layer = QgsVectorLayer(source_path, Path(source_path).stem, "ogr")
        if layer is None or not layer.isValid():
            return None
        self._place_terrain_layer(layer)
        return layer

    def _place_terrain_layer(self, layer) -> None:
        project = QgsProject.instance()
        if project.mapLayer(layer.id()) is None:
            project.addMapLayer(layer, False)
        group = self._terrain_output_group()
        node = project.layerTreeRoot().findLayer(layer.id())
        if node is None:
            group.addLayer(layer)
        elif node.parent() != group:
            self._move_layer_tree_node(node, group)


__all__ = ["DemIntegrationMixin"]
