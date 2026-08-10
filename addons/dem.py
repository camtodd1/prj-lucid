"""Optional DEM download and elevation-polygon workflow controller."""

import traceback
from pathlib import Path
from typing import Optional

from qgis.PyQt.QtCore import QCoreApplication, QFile  # type: ignore
from qgis.PyQt.QtWidgets import QMessageBox, QPushButton  # type: ignore
from qgis.core import (  # type: ignore
    Qgis,
    QgsLayerTreeGroup,
    QgsLayerTreeLayer,
    QgsProject,
    QgsProcessingUtils,
    QgsRasterLayer,
    QgsVectorLayer,
)

from ..core.dem_integration import (
    apply_elevation_polygon_style,
    apply_headroom_style,
    apply_penetration_boundary_style,
    apply_terrain_clearance_style,
    create_elevation_polygons,
    create_ols_square_extent_layer,
    create_terrain_analysis_outputs,
    download_ga_dem,
    elevation_polygon_output_path,
    open_topography_dialog,
    raster_has_terrain_values,
)
from ..core import output_structure
from ..guidelines.controlling_ols_engine import PlanarControllingOlsEngine


class DemIntegrationMixin:
    """Coordinate the optional Terrain tab without affecting core generation."""

    def open_dem_downloader(self):
        """Download terrain from the selected optional source."""
        if self.dlg is None:
            return
        try:
            extent_layer = (
                self.dlg.selected_dem_extent_layer()
                or create_ols_square_extent_layer(self._terrain_airport_code())
            )
        except ValueError as exc:
            self.dlg.set_dem_contour_status(str(exc), error=True)
            QMessageBox.warning(self.dlg, self.tr("OLS extent unavailable"), str(exc))
            return
        source_key = self.dlg.selected_dem_source()
        if source_key != "open_topography":
            self._download_ga_terrain(extent_layer, source_key)
            return
        try:
            results = open_topography_dialog(extent_layer)
            dem_result = results.get("OUTPUT") if isinstance(results, dict) else None
            if dem_result is None:
                self.dlg.set_dem_contour_status(
                    "DEM download was cancelled or produced no output."
                )
                return
            metadata = {
                "source_key": "open_topography",
                "source_service": "OpenTopography",
                "short_label": "OpenTopography",
                "vertical_datum": "Depends on the selected OpenTopography dataset",
                "vertical_epsg": "",
            }
            dem_layer = self._ensure_terrain_raster_layer(dem_result, metadata)
            if dem_layer is None:
                raise RuntimeError("The downloaded DEM could not be loaded.")
            self.dlg.set_downloaded_dem(dem_layer, metadata)
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

    def _download_ga_terrain(self, extent_layer, source_key: str) -> None:
        button = self.dlg.findChild(QPushButton, "pushButton_DownloadDem")
        original_text = button.text() if button is not None else ""
        if button is not None:
            button.setEnabled(False)
            button.setText(self.tr("Downloading…"))
        self.dlg.set_dem_contour_status("Downloading Geoscience Australia terrain…")
        QCoreApplication.processEvents()

        source_keys = (
            ("ga_lidar_5m", "ga_srtm_30m")
            if source_key == "ga_best"
            else (source_key,)
        )
        errors = []
        try:
            for candidate_key in source_keys:
                output_path = self._terrain_download_path(candidate_key)
                try:
                    metadata = download_ga_dem(
                        extent_layer,
                        candidate_key,
                        output_path,
                    )
                    if not raster_has_terrain_values(output_path):
                        QFile.remove(output_path)
                        raise RuntimeError(
                            f"{metadata['short_label']} has no terrain coverage for this extent."
                        )
                    dem_layer = self._ensure_terrain_raster_layer(
                        output_path,
                        metadata,
                    )
                    if dem_layer is None:
                        raise RuntimeError("The downloaded GA DEM could not be loaded.")
                    self.dlg.set_downloaded_dem(dem_layer, metadata)
                    self._log(
                        f"GA terrain ready: {dem_layer.source()} "
                        f"({metadata['short_label']})."
                    )
                    self.iface.messageBar().pushMessage(
                        self.tr("Terrain"),
                        self.tr(f"Downloaded {metadata['short_label']} terrain."),
                        level=Qgis.Success,
                        duration=6,
                    )
                    return
                except (RuntimeError, ValueError) as exc:
                    errors.append(str(exc))
                    if source_key != "ga_best":
                        raise
                    self._log_warning(
                        f"GA terrain source {candidate_key} unavailable: {exc}",
                        notify_user=False,
                    )
            raise RuntimeError(" | ".join(errors) or "No GA terrain source succeeded.")
        except (RuntimeError, ValueError) as exc:
            self.dlg.set_dem_contour_status(str(exc), error=True)
            QMessageBox.warning(
                self.dlg,
                self.tr("GA terrain unavailable"),
                str(exc),
            )
        except Exception as exc:
            self.dlg.set_dem_contour_status(
                "GA terrain download failed. See the QGIS log.",
                error=True,
            )
            self._log_warning(
                f"GA terrain download failed: {exc}\n{traceback.format_exc()}"
            )
            QMessageBox.critical(
                self.dlg,
                self.tr("GA terrain error"),
                self.tr("Could not download GA terrain. See the QGIS log for details."),
            )
        finally:
            if button is not None:
                button.setText(original_text)
            self.dlg.refresh_dem_tool_state()

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
            for key in (
                "source_service",
                "dataset",
                "vertical_datum",
                "vertical_epsg",
                "dataset_url",
            ):
                value = dem_source.customProperty(f"safeguarding_builder/{key}")
                if value not in (None, ""):
                    contour_layer.setCustomProperty(
                        f"safeguarding_builder/{key}", value
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

    def create_terrain_analysis_layers(self):
        """Explicitly create terrain penetration and obstacle-headroom layers."""
        if self.dlg is None:
            return
        dem_source = self.dlg.downloaded_dem_source()
        if dem_source is None:
            QMessageBox.warning(
                self.dlg,
                self.tr("DEM required"),
                self.tr("Download a DEM before creating terrain analysis layers."),
            )
            return

        engines = dict(getattr(self, "_terrain_ols_engines", {}) or {})
        engine = engines.get("baseline") or engines.get("OFS")
        if engine is None:
            candidates = [
                candidate
                for candidate in list(
                    getattr(self, "_controlling_ols_candidates", []) or []
                )
                if getattr(candidate, "model", None)
                in {"constant", "axis", "plane", "conical"}
            ]
            exclusions = list(
                getattr(self, "_controlling_ols_exclusion_geometries", []) or []
            )
            if candidates:
                engine = PlanarControllingOlsEngine(
                    candidates,
                    exclusion_geometries=exclusions,
                )
        if engine is None:
            QMessageBox.warning(
                self.dlg,
                self.tr("Controlling OLS required"),
                self.tr(
                    "Generate the OLS and its controlling envelope before creating "
                    "terrain analysis layers."
                ),
            )
            return

        button = self.dlg.findChild(
            QPushButton,
            "pushButton_CreateTerrainAnalysis",
        )
        original_text = button.text() if button is not None else ""
        if button is not None:
            button.setEnabled(False)
            button.setText(self.tr("Analysing…"))
        self.dlg.set_dem_contour_status("Comparing DEM cells with the controlling OLS…")
        QCoreApplication.processEvents()

        try:
            output_directory = self._terrain_output_directory() or str(
                Path(QgsProcessingUtils.tempFolder())
                / "safeguarding_builder_terrain_analysis"
            )
            last_percent = -1

            def update_progress(completed: int, total: int) -> None:
                nonlocal last_percent
                percent = int((completed * 100) / max(1, total))
                if percent == last_percent:
                    return
                last_percent = percent
                self.dlg.set_dem_contour_status(
                    f"Comparing DEM cells with the controlling OLS… {percent}%"
                )
                QCoreApplication.processEvents()

            outputs = create_terrain_analysis_outputs(
                dem_source,
                engine,
                output_directory,
                self._terrain_airport_code(),
                progress_callback=update_progress,
            )
            airport = self._terrain_airport_code()
            prefix = f"{airport} " if airport else ""
            clearance_layer = QgsRasterLayer(
                outputs["clearance"],
                f"{prefix}Terrain–OLS Clearance (m)",
            )
            headroom_layer = QgsRasterLayer(
                outputs["headroom"],
                f"{prefix}Obstacle Headroom",
            )
            boundary_layer = QgsVectorLayer(
                f"{outputs['penetration_boundary']}|layername=zero_clearance",
                f"{prefix}Terrain Penetration Boundary",
                "ogr",
            )
            if not all(
                layer.isValid()
                for layer in (clearance_layer, headroom_layer, boundary_layer)
            ):
                raise RuntimeError("One or more terrain analysis outputs could not be loaded.")

            apply_terrain_clearance_style(clearance_layer)
            apply_headroom_style(headroom_layer)
            apply_penetration_boundary_style(boundary_layer)
            self._remove_existing_terrain_analysis_layers()
            project = QgsProject.instance()
            for layer, analysis_type in (
                (clearance_layer, "signed_clearance"),
                (headroom_layer, "obstacle_headroom"),
                (boundary_layer, "zero_clearance_boundary"),
            ):
                layer.setCustomProperty(
                    "safeguarding_builder/terrain_analysis_type",
                    analysis_type,
                )
                layer.setCustomProperty(
                    "safeguarding_builder/dem_source",
                    self._terrain_source_path(dem_source),
                )
                layer.setCustomProperty(
                    "safeguarding_builder/analysis_cell_width",
                    outputs["cell_width"],
                )
                layer.setCustomProperty(
                    "safeguarding_builder/analysis_cell_height",
                    outputs["cell_height"],
                )
                project.addMapLayer(layer, False)

            terrain_group = self._terrain_output_group()
            for layer in (clearance_layer, headroom_layer, boundary_layer):
                terrain_group.insertLayer(0, layer)

            missing_layers = [
                layer.name()
                for layer in (clearance_layer, headroom_layer, boundary_layer)
                if terrain_group.findLayer(layer.id()) is None
            ]
            if missing_layers:
                raise RuntimeError(
                    "Terrain analysis completed but these output layers could not "
                    f"be added to the project: {', '.join(missing_layers)}"
                )

            clearance_node = terrain_group.findLayer(clearance_layer.id())
            if clearance_node is not None:
                clearance_node.setItemVisibilityChecked(False)

            self.dlg.set_dem_contour_status(
                "Created terrain clearance, penetration boundary and obstacle-headroom layers."
            )
            self._log(
                "Terrain analysis ready: "
                f"{outputs['valid_cells']} analysed cells, "
                f"{outputs['penetration_cells']} penetration cells."
            )
            self.iface.messageBar().pushMessage(
                self.tr("Terrain analysis"),
                self.tr("Clearance and obstacle-headroom layers created."),
                level=Qgis.Success,
                duration=6,
            )
        except (RuntimeError, ValueError) as exc:
            self.dlg.set_dem_contour_status(str(exc), error=True)
            QMessageBox.warning(
                self.dlg,
                self.tr("Terrain analysis unavailable"),
                str(exc),
            )
        except Exception as exc:
            self.dlg.set_dem_contour_status(
                "Terrain analysis failed. See the QGIS log.",
                error=True,
            )
            self._log_warning(
                f"Terrain analysis failed: {exc}\n{traceback.format_exc()}"
            )
            QMessageBox.critical(
                self.dlg,
                self.tr("Terrain analysis error"),
                self.tr("Could not create terrain analysis layers. See the QGIS log."),
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
        main_name = f"{airport} Safeguarding Builder" if airport else "Safeguarding Builder"
        main_group = next(
            (
                child
                for child in root.children()
                if isinstance(child, QgsLayerTreeGroup) and child.name() == main_name
            ),
            None,
        )
        if main_group is None:
            main_group = root.addGroup(main_name)
        group = next(
            (
                child
                for child in main_group.children()
                if isinstance(child, QgsLayerTreeGroup)
                and child.name() == output_structure.TERRAIN_ANALYSIS
            ),
            None,
        )
        if group is None:
            insert_index = len(main_group.children())
            for index, child in enumerate(main_group.children()):
                if isinstance(child, QgsLayerTreeGroup) and child.name() in {
                    output_structure.IMPORTED_AIRPORT_MAP,
                    output_structure.DEBUG_DEVELOPMENT,
                }:
                    insert_index = index
                    break
            group = main_group.insertGroup(
                insert_index,
                output_structure.TERRAIN_ANALYSIS,
            )

        legacy_names = {
            "Terrain Analysis",
            f"{airport} Terrain Analysis" if airport else "Terrain Analysis",
        }
        existing_layer_ids = {node.layerId() for node in group.findLayers()}
        for legacy_group in list(root.children()):
            if not isinstance(legacy_group, QgsLayerTreeGroup):
                continue
            if legacy_group.name() not in legacy_names:
                continue
            for layer_node in legacy_group.findLayers():
                layer = layer_node.layer()
                if layer is not None and layer.id() not in existing_layer_ids:
                    group.addLayer(layer)
                    existing_layer_ids.add(layer.id())
            root.removeChildNode(legacy_group)
        group.setItemVisibilityChecked(True)
        group.setExpanded(True)
        return group

    @staticmethod
    def _consolidate_terrain_group(
        root,
        group_name: str,
    ) -> Optional[QgsLayerTreeGroup]:
        matching_groups = [
            child
            for child in root.children()
            if isinstance(child, QgsLayerTreeGroup) and child.name() == group_name
        ]
        if not matching_groups:
            return None
        group = max(matching_groups, key=lambda candidate: len(candidate.children()))
        existing_layer_ids = {
            child.layerId()
            for child in group.children()
            if isinstance(child, QgsLayerTreeLayer)
        }
        for duplicate_group in matching_groups:
            if duplicate_group == group:
                continue
            for child in list(duplicate_group.children()):
                if not isinstance(child, QgsLayerTreeLayer):
                    continue
                layer = child.layer()
                if layer is not None and layer.id() not in existing_layer_ids:
                    group.addLayer(layer)
                    existing_layer_ids.add(layer.id())
            root.removeChildNode(duplicate_group)
        seen_layer_ids = set()
        for child in list(group.children()):
            if not isinstance(child, QgsLayerTreeLayer):
                continue
            if child.layerId() in seen_layer_ids:
                group.removeChildNode(child)
            else:
                seen_layer_ids.add(child.layerId())
        return group

    def _repair_existing_terrain_output_groups(self) -> None:
        root = QgsProject.instance().layerTreeRoot()
        group_names = {
            child.name()
            for child in root.children()
            if isinstance(child, QgsLayerTreeGroup)
            and (
                child.name() == "Terrain Analysis"
                or child.name().endswith(" Terrain Analysis")
            )
        }
        for group_name in group_names:
            self._consolidate_terrain_group(root, group_name)

    @staticmethod
    def _remove_existing_terrain_analysis_layers() -> None:
        project = QgsProject.instance()
        analysis_types = {
            "signed_clearance",
            "obstacle_headroom",
            "zero_clearance_boundary",
        }
        layer_ids = [
            layer.id()
            for layer in project.mapLayers().values()
            if layer.customProperty(
                "safeguarding_builder/terrain_analysis_type"
            )
            in analysis_types
        ]
        if layer_ids:
            project.removeMapLayers(layer_ids)

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

    def _terrain_download_path(self, source_key: str) -> str:
        directory = Path(
            self._terrain_output_directory() or QgsProcessingUtils.tempFolder()
        )
        directory.mkdir(parents=True, exist_ok=True)
        airport = self._terrain_airport_code().lower() or "airport"
        safe_airport = "".join(
            character if character.isalnum() else "_" for character in airport
        ).strip("_") or "airport"
        stem = f"{safe_airport}_{source_key}_dem"
        candidate = directory / f"{stem}.tif"
        suffix = 2
        while candidate.exists():
            candidate = directory / f"{stem}_{suffix}.tif"
            suffix += 1
        return str(candidate)

    def _ensure_terrain_raster_layer(
        self,
        result,
        metadata=None,
    ) -> Optional[QgsRasterLayer]:
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
        source_label = str((metadata or {}).get("short_label", "")).strip()
        name_suffix = f" {source_label}" if source_label else ""
        layer.setName(f"{self._terrain_airport_code()}{name_suffix} DEM".strip())
        for key, value in (metadata or {}).items():
            if key == "output" or value in (None, ""):
                continue
            layer.setCustomProperty(f"safeguarding_builder/{key}", value)
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
