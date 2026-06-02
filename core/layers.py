# -*- coding: utf-8 -*-
"""Layer, style, and layer-tree helpers shared by safeguarding processors."""

import os.path
import re
import traceback
from typing import Dict, List, Optional

from qgis.PyQt.QtCore import QPointF  # type: ignore
from qgis.PyQt.QtGui import QColor  # type: ignore
from qgis.core import (  # type: ignore
    Qgis,
    QgsCategorizedSymbolRenderer,
    QgsFeature,
    QgsFillSymbol,
    QgsGradientFillSymbolLayer,
    QgsFields,
    QgsLayerTreeGroup,
    QgsLayerTreeLayer,
    QgsLayerTreeNode,
    QgsLineSymbol,
    QgsMessageLog,
    QgsProperty,
    QgsProject,
    QgsRendererCategory,
    QgsShapeburstFillSymbolLayer,
    QgsSimpleFillSymbolLayer,
    QgsSingleSymbolRenderer,
    QgsSymbolLayer,
    QgsVectorFileWriter,
    QgsVectorLayer,
    QgsWkbTypes,
)

from ..guidelines.guideline_constants import LAYER_FEATURE_BATCH_SIZE

PLUGIN_TAG = "SafeguardingBuilder"


class LayerMixin:
    def _setup_main_group(
        self, root_node: QgsLayerTreeNode, group_name: str, project: QgsProject
    ) -> Optional[QgsLayerTreeGroup]:
        """Finds and clears or creates the main layer group."""
        existing_group = root_node.findGroup(group_name)
        if existing_group is not None:
            QgsMessageLog.logMessage(f"Removing existing group: {group_name}", PLUGIN_TAG, level=Qgis.Info)
            self._remove_group_recursively(existing_group, project)
            parent_node = existing_group.parent()
            if parent_node is not None:
                parent_node.removeChildNode(existing_group)
        main_group = root_node.addGroup(group_name)
        if main_group is None:
            QgsMessageLog.logMessage(f"Failed create group: {group_name}", PLUGIN_TAG, level=Qgis.Critical)
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

    def _remove_group_recursively(self, group_node: QgsLayerTreeGroup, project: QgsProject):
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
        provider_fields = provider.fields()
        for feature in features:
            normalised_attrs = []
            attrs = feature.attributes()
            for field_index in range(provider_fields.count()):
                value = attrs[field_index] if field_index < len(attrs) else None
                field = provider_fields.at(field_index)
                if isinstance(value, str) and field.length() > 0:
                    value = value[: field.length()]
                normalised_attrs.append(value)
            feature.setFields(provider_fields)
            feature.setAttributes(normalised_attrs)

        while features:
            batch = features[:batch_size]
            add_ok, _ = provider.addFeatures(batch)
            if not add_ok:
                QgsMessageLog.logMessage(
                    f"Failed to add feature batch to layer '{display_name}'. "
                    "Retrying feature-by-feature for diagnostics.",
                    plugin_tag,
                    Qgis.Warning,
                )
                failed_features = 0
                for batch_index, feature in enumerate(batch):
                    single_ok, _ = provider.addFeatures([feature])
                    if single_ok:
                        continue
                    failed_features += 1
                    geom = feature.geometry()
                    if geom is None:
                        geom_details = "geometry=None"
                    else:
                        try:
                            geom_details = (
                                f"wkb={QgsWkbTypes.displayString(geom.wkbType())}, "
                                f"type={geom.type()}, multipart={geom.isMultipart()}, "
                                f"empty={geom.isEmpty()}, valid={geom.isGeosValid()}, "
                                f"area={geom.area():.6f}"
                            )
                        except Exception as geom_error:
                            geom_details = f"geometry detail error: {geom_error}"
                    QgsMessageLog.logMessage(
                        f"Failed to add feature {batch_index} to layer "
                        f"'{display_name}': {geom_details}; "
                        f"attr_count={len(feature.attributes())}; "
                        f"attrs={feature.attributes()}",
                        plugin_tag,
                        Qgis.Critical,
                    )
                if failed_features:
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

            if style_key:
                layer.setCustomProperty("safeguarding_style_key", style_key)

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

                QgsMessageLog.logMessage(f"display_name = '{display_name}'", plugin_tag, Qgis.Info)

                name_without_ext = os.path.splitext(display_name)[0]
                safe_name = self._sanitize_filename(name_without_ext)
                full_path = os.path.join(self.output_path, f"{safe_name}{self.output_format_extension}")

                result = QgsVectorFileWriter.writeAsVectorFormat(
                    layer,
                    full_path,
                    "UTF-8",
                    layer.crs(),
                    self.output_format_driver,
                )

                if isinstance(result, tuple) and result[0] == QgsVectorFileWriter.NoError:
                    QgsMessageLog.logMessage(
                        f"Layer '{display_name}' successfully written to '{full_path}'.",
                        plugin_tag,
                        Qgis.Info,
                    )
                    loaded_layer = self.iface.addVectorLayer(full_path, display_name, "ogr")
                    if loaded_layer is not None and loaded_layer.isValid():
                        root = project.layerTreeRoot()
                        loaded_node = root.findLayer(loaded_layer.id())
                        if loaded_node is not None:
                            cloned_node = loaded_node.clone()
                            self._stage_layer_tree_node(cloned_node)
                            layer_group.insertChildNode(0, cloned_node)
                            if loaded_node.parent() is not None:
                                loaded_node.parent().removeChildNode(loaded_node)
                        loaded_layer.setCustomProperty("safeguarding_style_key", style_key)
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
            self._apply_style(layer, self.style_map)
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
            if not style_key and "Centreline" in layer_name and layer_name.startswith("RWY "):
                style_key = "Runway Centreline"

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
                if not os.path.exists(qml_path):
                    QgsMessageLog.logMessage(
                        f"Style file not found: '{qml_path}' for layer '{layer_name}'",
                        plugin_tag,
                        level=Qgis.Warning,
                    )
                    return

                try:
                    load_result = layer.loadNamedStyle(qml_path)
                    if isinstance(load_result, tuple):
                        result_flag = next(
                            (item for item in load_result if isinstance(item, bool)),
                            True,
                        )
                        message = next(
                            (item for item in load_result if isinstance(item, str) and item),
                            "",
                        )
                        if not result_flag:
                            QgsMessageLog.logMessage(
                                f"Failed to apply style '{qml_filename}' to '{layer_name}': {message}",
                                plugin_tag,
                                level=Qgis.Warning,
                            )
                            return
                    if str(style_key) == "AGL Light":
                        self._apply_agl_rotation_field(layer)
                    if str(style_key) == "OLS Controlling Planar Region":
                        self._apply_controlling_region_style(layer)
                    if str(style_key) == "OLS Controlling Contour":
                        self._apply_controlling_contour_style(layer)
                    if str(style_key) in {"OLS Transitional Contour", "OLS Controlling Contour"}:
                        layer.setLabelsEnabled(True)
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

    def _apply_controlling_region_style(self, layer: QgsVectorLayer):
        """Apply the controlling OLS palette with axis and conical gradient fills."""
        if layer is None or not layer.isValid():
            return
        try:
            categories = []
            for surface, colors, fill_mode in [
                ("Approach", ("54,160,180,165", "255,177,94,130", "29,92,110,255"), "axis"),
                ("TOCS", ("91,125,218,160", "247,194,80,125", "43,70,145,255"), "axis"),
                ("Transitional", ("91,184,132,150", "205,93,153,125", "46,105,70,255"), "plane"),
                ("Conical", ("238,139,58,150", "84,97,188,105", "143,75,31,255"), "shapeburst"),
                ("IHS", ("112,176,149,120", "246,207,113,100", "48,112,88,255"), "solid"),
                ("OHS", ("125,134,148,105", "232,185,107,95", "79,87,100,255"), "solid"),
            ]:
                symbol = self._controlling_region_symbol(colors, fill_mode)
                categories.append(QgsRendererCategory(surface, symbol, surface))
            layer.setRenderer(QgsCategorizedSymbolRenderer("surface", categories))
        except Exception as exc:
            QgsMessageLog.logMessage(
                f"Warning: failed to apply controlling OLS region gradient style: {exc}",
                PLUGIN_TAG,
                level=Qgis.Warning,
            )

    def _controlling_region_symbol(self, colors, fill_mode: str):
        fill_color, secondary_color, outline_color = colors
        symbol = QgsFillSymbol.createSimple(
            {
                "color": fill_color,
                "outline_color": outline_color,
                "outline_width": "0.22",
                "outline_width_unit": "MM",
                "style": "solid",
            }
        )
        if fill_mode == "solid":
            return symbol

        fill_layer = None
        if fill_mode == "shapeburst":
            fill_layer = self._controlling_shapeburst_fill(fill_color, secondary_color)
        else:
            fill_layer = self._controlling_axis_gradient_fill(fill_color, secondary_color, fill_mode == "axis")

        if fill_layer is not None:
            symbol.changeSymbolLayer(0, fill_layer)
            outline_layer = QgsSimpleFillSymbolLayer.create(
                {
                    "color": "0,0,0,0",
                    "outline_color": outline_color,
                    "outline_width": "0.22",
                    "outline_width_unit": "MM",
                    "style": "no",
                }
            )
            if outline_layer is not None:
                symbol.appendSymbolLayer(outline_layer)
        return symbol

    def _controlling_axis_gradient_fill(self, fill_color: str, secondary_color: str, use_axis_angle: bool):
        try:
            fill_layer = QgsGradientFillSymbolLayer(self._qcolor(fill_color), self._qcolor(secondary_color))
            self._set_qgis_enum(fill_layer, "setGradientColorType", "GradientColorSource", "SimpleTwoColor")
            self._set_qgis_enum(fill_layer, "setGradientType", "GradientType", "Linear")
            self._set_qgis_enum(fill_layer, "setCoordinateMode", "SymbolCoordinateReference", "Feature")
            self._set_qgis_enum(fill_layer, "setGradientSpread", "GradientSpread", "Pad")
            fill_layer.setReferencePoint1(QPointF(0.05, 0.5))
            fill_layer.setReferencePoint2(QPointF(0.95, 0.5))
            if use_axis_angle and hasattr(QgsSymbolLayer, "PropertyGradientReference1X"):
                properties = fill_layer.dataDefinedProperties()
                angle = 'coalesce("style_angle", 0)'
                properties.setProperty(
                    QgsSymbolLayer.PropertyGradientReference1X,
                    QgsProperty.fromExpression(f"0.5 - 0.45 * sin(radians({angle}))"),
                )
                properties.setProperty(
                    QgsSymbolLayer.PropertyGradientReference1Y,
                    QgsProperty.fromExpression(f"0.5 + 0.45 * cos(radians({angle}))"),
                )
                properties.setProperty(
                    QgsSymbolLayer.PropertyGradientReference2X,
                    QgsProperty.fromExpression(f"0.5 + 0.45 * sin(radians({angle}))"),
                )
                properties.setProperty(
                    QgsSymbolLayer.PropertyGradientReference2Y,
                    QgsProperty.fromExpression(f"0.5 - 0.45 * cos(radians({angle}))"),
                )
            return fill_layer
        except Exception:
            return None

    def _controlling_shapeburst_fill(self, fill_color: str, secondary_color: str):
        try:
            fill_layer = QgsShapeburstFillSymbolLayer(self._qcolor(fill_color), self._qcolor(secondary_color))
            self._set_qgis_enum(fill_layer, "setColorType", "GradientColorSource", "SimpleTwoColor")
            fill_layer.setBlurRadius(1)
            fill_layer.setUseWholeShape(True)
            fill_layer.setIgnoreRings(False)
            return fill_layer
        except Exception:
            return None

    def _apply_controlling_contour_style(self, layer: QgsVectorLayer):
        """Keep controlling contours visually distinct and label-ready."""
        if layer is None or not layer.isValid():
            return
        try:
            symbol = QgsLineSymbol.createSimple(
                {
                    "line_color": "18,166,142,255",
                    "line_width": "0.32",
                    "line_width_unit": "MM",
                    "line_style": "solid",
                }
            )
            layer.setRenderer(QgsSingleSymbolRenderer(symbol))
            layer.setLabelsEnabled(True)
        except Exception as exc:
            QgsMessageLog.logMessage(
                f"Warning: failed to apply controlling contour line style: {exc}",
                PLUGIN_TAG,
                level=Qgis.Warning,
            )

    def _set_qgis_enum(self, target, setter_name: str, enum_name: str, value_name: str):
        enum_value = getattr(getattr(Qgis, enum_name, None), value_name, None)
        if enum_value is not None and hasattr(target, setter_name):
            getattr(target, setter_name)(enum_value)

    def _qcolor(self, rgba_text: str) -> QColor:
        parts = [int(float(part)) for part in rgba_text.split(",")[:4]]
        while len(parts) < 4:
            parts.append(255)
        return QColor(parts[0], parts[1], parts[2], parts[3])

    def _apply_agl_rotation_field(self, layer: QgsVectorLayer) -> None:
        """Apply QGIS' renderer-level marker rotation for dual-aspect AGL point symbols."""
        if layer.fields().indexFromName("symbol_ang") < 0:
            return
        renderer = layer.renderer()
        if renderer is None or renderer.type() != "categorizedSymbol":
            return
        try:
            for category in renderer.categories():
                symbol = category.symbol()
                if symbol is not None:
                    QgsCategorizedSymbolRenderer.convertSymbolRotation(symbol, "symbol_ang")
            layer.setRenderer(renderer)
        except Exception as exc:
            QgsMessageLog.logMessage(
                f"Unable to apply AGL symbol rotation field for '{layer.name()}': {exc}",
                PLUGIN_TAG,
                level=Qgis.Warning,
            )
