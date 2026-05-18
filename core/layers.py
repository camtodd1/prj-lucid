# -*- coding: utf-8 -*-
"""Layer, style, and layer-tree helpers shared by safeguarding processors."""

import os.path
import re
import traceback
from typing import Dict, List, Optional

from qgis.core import (  # type: ignore
    Qgis,
    QgsFeature,
    QgsFields,
    QgsLayerTreeGroup,
    QgsLayerTreeLayer,
    QgsLayerTreeNode,
    QgsMessageLog,
    QgsProject,
    QgsVectorFileWriter,
    QgsVectorLayer,
)

from ..guidelines.constants import LAYER_FEATURE_BATCH_SIZE

PLUGIN_TAG = "SafeguardingBuilder"


class LayerMixin:
    def _setup_main_group(
        self, root_node: QgsLayerTreeNode, group_name: str, project: QgsProject
    ) -> Optional[QgsLayerTreeGroup]:
        """Finds and clears or creates the main layer group."""
        existing_group = root_node.findGroup(group_name)
        if existing_group is not None:
            QgsMessageLog.logMessage(
                f"Removing existing group: {group_name}", PLUGIN_TAG, level=Qgis.Info
            )
            self._remove_group_recursively(existing_group, project)
            parent_node = existing_group.parent()
            if parent_node is not None:
                parent_node.removeChildNode(existing_group)
        main_group = root_node.addGroup(group_name)
        if main_group is None:
            QgsMessageLog.logMessage(
                f"Failed create group: {group_name}", PLUGIN_TAG, level=Qgis.Critical
            )
            return None
        self._stage_layer_tree_node(main_group)
        return main_group

    def _stage_layer_tree_node(self, node: Optional[QgsLayerTreeNode]):
        """Keep generated layer tree nodes from rendering immediately."""
        if node is None:
            return
        try:
            if hasattr(node, "setItemVisibilityChecked"):
                node.setItemVisibilityChecked(False)
            if hasattr(node, "setExpanded"):
                node.setExpanded(False)
        except Exception as e:
            QgsMessageLog.logMessage(
                f"Warning: Failed to stage layer tree node visibility: {e}",
                PLUGIN_TAG,
                level=Qgis.Warning,
            )

    def _remove_group_recursively(
        self, group_node: QgsLayerTreeGroup, project: QgsProject
    ):
        """Helper to remove layers within a group and its subgroups."""
        if group_node is None:
            return
        children_copy = list(group_node.children())
        for node in children_copy:
            if isinstance(node, QgsLayerTreeLayer):
                layer_id = node.layerId()
                if layer_id and project.mapLayer(layer_id):
                    project.removeMapLayer(layer_id)
            elif isinstance(node, QgsLayerTreeGroup):
                self._remove_group_recursively(node, project)
                group_node.removeChildNode(node)

    def _sanitize_filename(self, name: str, replace_char: str = "_") -> str:
        """Removes or replaces characters invalid for filenames."""
        name = name.strip()
        name = re.sub(r'[<>:"/\\|?* ]+', replace_char, name)
        name = re.sub(f"{replace_char}+", replace_char, name)
        name = name.strip(replace_char)
        if not name:
            name = "unnamed_layer"

        return name.rstrip(".") or "unnamed_layer"

    def _add_features_in_batches(
        self,
        provider,
        features: List[QgsFeature],
        display_name: str,
        batch_size: int = LAYER_FEATURE_BATCH_SIZE,
    ) -> bool:
        """
        Adds features to a provider in small batches and releases Python references.

        The input list is intentionally consumed after successful batch writes. This
        keeps large generated geometries from lingering in Python after the memory
        layer provider has accepted them.
        """
        plugin_tag = PLUGIN_TAG
        if not features:
            return True

        batch_size = max(1, int(batch_size))
        while features:
            batch = features[:batch_size]
            add_ok, _ = provider.addFeatures(batch)
            if not add_ok:
                QgsMessageLog.logMessage(
                    f"Failed to add feature batch to layer '{display_name}'",
                    plugin_tag,
                    Qgis.Critical,
                )
                return False
            del features[: len(batch)]
        return True

    def _create_and_add_layer(
        self,
        geometry_type_str: str,
        internal_name_base: str,
        display_name: str,
        fields: QgsFields,
        features: List[QgsFeature],
        layer_group: QgsLayerTreeGroup,
        style_key: str,
    ) -> Optional[QgsVectorLayer]:
        """
        Helper to create/populate a layer, add to project/group, and apply style.
        Handles both memory layer creation and file writing based on self.output_mode.
        Logs warnings or errors on failure. Returns the added layer or None.
        Consumes the features list after successful provider writes to lower peak memory.
        """
        plugin_tag = PLUGIN_TAG
        project = QgsProject.instance()
        target_crs = project.crs()
        target_crs.authid()

        if not features:
            QgsMessageLog.logMessage(
                f"Skipping layer '{display_name}': No features generated.",
                plugin_tag,
                level=Qgis.Info,
            )
            return None

        try:
            uri = f"{geometry_type_str}?crs={target_crs.authid()}"
            layer = QgsVectorLayer(uri, display_name, "memory")
            if not layer.isValid():
                QgsMessageLog.logMessage(
                    f"Failed to create layer '{display_name}' with URI '{uri}'",
                    plugin_tag,
                    Qgis.Critical,
                )
                return None

            provider = layer.dataProvider()
            if provider is None:
                QgsMessageLog.logMessage(
                    f"Failed to get data provider for layer '{display_name}'",
                    plugin_tag,
                    Qgis.Critical,
                )
                return None

            if not provider.addAttributes(fields):
                QgsMessageLog.logMessage(
                    f"Failed to add fields to layer '{display_name}'",
                    plugin_tag,
                    Qgis.Critical,
                )
                return None
            layer.updateFields()
            if not self._add_features_in_batches(provider, features, display_name):
                return None
            layer.updateExtents()

            if style_key in self.style_map:
                style_filename = self.style_map[style_key]
                style_path = os.path.join(self.plugin_dir, "styles", style_filename)
                if os.path.exists(style_path):
                    try:
                        layer.loadNamedStyle(style_path)
                        layer.triggerRepaint()
                    except Exception as e:
                        QgsMessageLog.logMessage(
                            f"Exception during loadNamedStyle for '{style_path}' on layer '{display_name}': {e}",
                            plugin_tag,
                            level=Qgis.Warning,
                        )
                else:
                    QgsMessageLog.logMessage(
                        f"Style file not found: '{style_path}' for key '{style_key}'",
                        plugin_tag,
                        Qgis.Warning,
                    )

            if self.output_mode == "file":
                if not all(
                    [
                        self.output_path,
                        self.output_format_driver,
                        self.output_format_extension,
                    ]
                ):
                    QgsMessageLog.logMessage(
                        f"Skipping file save for '{display_name}': Output path/driver/extension missing.",
                        plugin_tag,
                        level=Qgis.Critical,
                    )
                    return layer

                QgsMessageLog.logMessage(
                    f"display_name = '{display_name}'", plugin_tag, Qgis.Info
                )

                name_without_ext = os.path.splitext(display_name)[0]
                safe_name = self._sanitize_filename(name_without_ext)
                full_path = os.path.join(
                    self.output_path, f"{safe_name}{self.output_format_extension}"
                )

                result = QgsVectorFileWriter.writeAsVectorFormat(
                    layer,
                    full_path,
                    "UTF-8",
                    layer.crs(),
                    self.output_format_driver,
                )

                if (
                    isinstance(result, tuple)
                    and result[0] == QgsVectorFileWriter.NoError
                ):
                    QgsMessageLog.logMessage(
                        f"Layer '{display_name}' successfully written to '{full_path}'.",
                        plugin_tag,
                        Qgis.Info,
                    )
                    loaded_layer = self.iface.addVectorLayer(
                        full_path, display_name, "ogr"
                    )
                    if loaded_layer is not None and loaded_layer.isValid():
                        root = project.layerTreeRoot()
                        loaded_node = root.findLayer(loaded_layer.id())
                        if loaded_node is not None:
                            cloned_node = loaded_node.clone()
                            self._stage_layer_tree_node(cloned_node)
                            layer_group.insertChildNode(0, cloned_node)
                            if loaded_node.parent() is not None:
                                loaded_node.parent().removeChildNode(loaded_node)
                        loaded_layer.setCustomProperty(
                            "safeguarding_style_key", style_key
                        )
                        self._apply_style(loaded_layer, self.style_map)
                        self.successfully_generated_layers.append(loaded_layer)
                        return loaded_layer
                    else:
                        QgsMessageLog.logMessage(
                            f"Failed to reload written layer '{display_name}' from '{full_path}'.",
                            plugin_tag,
                            Qgis.Warning,
                        )
                else:
                    QgsMessageLog.logMessage(
                        f"Error writing layer '{display_name}' to file: {result}",
                        plugin_tag,
                        Qgis.Warning,
                    )

            QgsProject.instance().addMapLayer(layer, False)
            layer_node = layer_group.addLayer(layer)
            self._stage_layer_tree_node(layer_node)
            self.successfully_generated_layers.append(layer)

            return layer

        except Exception as e:
            QgsMessageLog.logMessage(
                f"Error creating/adding layer '{display_name}': {e}",
                plugin_tag,
                Qgis.Critical,
            )
            return None

    def _apply_style(self, layer: QgsVectorLayer, style_map: Dict[str, str]):
        """
        Applies QML style based on custom property.
        Minimal checking: Attempts load, logs only critical exceptions.
        """
        plugin_tag = PLUGIN_TAG
        if layer is None or not layer.isValid():
            return
        layer_name = layer.name() or f"Layer {layer.id()}"
        qml_filename = None
        style_key = layer.customProperty("safeguarding_style_key")
        try:
            if style_key:
                qml_filename = style_map.get(str(style_key))
            if not qml_filename:
                geom_type = layer.geometryType()
                default_key_map = {
                    Qgis.GeometryType.Polygon: "Default Polygon",
                    Qgis.GeometryType.Line: "Default Line",
                    Qgis.GeometryType.Point: "Default Point",
                }
                default_key = default_key_map.get(geom_type)
                if default_key:
                    qml_filename = style_map.get(default_key)

            if qml_filename:
                qml_path = os.path.join(self.plugin_dir, "styles", qml_filename)

                try:
                    layer.loadNamedStyle(qml_path)
                    layer.triggerRepaint()
                except Exception as e_load:
                    QgsMessageLog.logMessage(
                        f"Exception during loadNamedStyle for '{qml_path}' on layer '{layer_name}': {e_load}",
                        plugin_tag,
                        level=Qgis.Warning,
                    )

            else:
                QgsMessageLog.logMessage(
                    f"Info: No specific or default style key found for layer '{layer_name}'. QGIS default will apply.",
                    plugin_tag,
                    level=Qgis.Info,
                )

        except Exception as e:
            QgsMessageLog.logMessage(
                f"Critical Error applying style logic to '{layer_name}': {e}\n{traceback.format_exc()}",
                plugin_tag,
                level=Qgis.Critical,
            )
