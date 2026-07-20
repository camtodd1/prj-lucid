# -*- coding: utf-8 -*-
"""Layer, style, and layer-tree helpers shared by safeguarding processors."""

import os.path
import re
import traceback
from typing import Dict, List, Optional

from qgis.PyQt.QtGui import QColor, QFont  # type: ignore
from qgis.core import (  # type: ignore
    Qgis,
    QgsCategorizedSymbolRenderer,
    QgsFeature,
    QgsFeatureRequest,
    QgsFillSymbol,
    QgsFields,
    QgsLayerTreeGroup,
    QgsLayerTreeLayer,
    QgsLayerTreeNode,
    QgsLineSymbol,
    QgsPalLayerSettings,
    QgsProject,
    QgsRendererCategory,
    QgsRuleBasedLabeling,
    QgsRuleBasedRenderer,
    QgsSingleSymbolRenderer,
    QgsTextBufferSettings,
    QgsTextFormat,
    QgsVectorLayerSimpleLabeling,
    QgsVectorFileWriter,
    QgsVectorLayer,
    QgsWkbTypes,
)

from .constants import LAYER_FEATURE_BATCH_SIZE
from .run_log import QgsMessageLog

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
                failed_features = 0
                first_geometry_detail = None
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
                    if first_geometry_detail is None:
                        first_geometry_detail = f"index={batch_index}, {geom_details}"
                if failed_features:
                    QgsMessageLog.logMessage(
                        f"Layer '{display_name}' omitted: {failed_features}/{len(batch)} "
                        f"features could not be written; first failure: {first_geometry_detail}.",
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

                # Display names are intentionally reused in parallel layer-tree
                # groups (for example, OFS and OES both contain a layer named
                # "Change Contours").  The internal name is the stable, unique
                # output identifier; using the display name here caused the
                # later family to overwrite the earlier family on disk.
                output_name = internal_name_base or os.path.splitext(display_name)[0]
                # Conventional baseline and comparison rulesets intentionally
                # reuse the same construction helpers and internal layer names.
                # Keep their datasources separate: otherwise the later
                # comparison write replaces the file still referenced by the
                # already-loaded baseline layer.
                if str(
                    getattr(self, "_contour_interval_ruleset_role", "baseline")
                    or "baseline"
                ).casefold() == "comparison":
                    output_name = f"Comparison_{output_name}"
                safe_name = self._sanitize_filename(output_name)
                full_path = os.path.join(self.output_path, f"{safe_name}{self.output_format_extension}")

                result = QgsVectorFileWriter.writeAsVectorFormat(
                    layer,
                    full_path,
                    "UTF-8",
                    layer.crs(),
                    self.output_format_driver,
                )

                if isinstance(result, tuple) and result[0] == QgsVectorFileWriter.NoError:
                    # Build and style the reloaded layer before adding its tree
                    # node.  Adding it through iface first exposes QGIS' default
                    # renderer to the layer-tree model; replacing that renderer
                    # afterwards can leave a stale legend/render cache until the
                    # user opens the Symbology panel.
                    loaded_layer = QgsVectorLayer(full_path, display_name, "ogr")
                    if loaded_layer is not None and loaded_layer.isValid():
                        loaded_layer.setCustomProperty("safeguarding_style_key", style_key)
                        self._apply_style(loaded_layer, self.style_map)
                        project.addMapLayer(loaded_layer, False)
                        loaded_node = layer_group.insertLayer(0, loaded_layer)
                        self._stage_layer_tree_node(loaded_node)
                        loaded_layer.triggerRepaint()
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
                    if str(style_key) in {
                        "Annex 14 OFS Surface",
                        "Annex 14 OES Surface",
                        "Annex 14 OFS Contour",
                        "Annex 14 OES Contour",
                        "Annex 14 Controlling OFS",
                        "Annex 14 Controlling OES",
                        "Annex 14 Candidate OFS",
                        "Annex 14 Candidate OES",
                    }:
                        self._prune_annex14_renderer_rules(layer)
                    if str(style_key) in {"Annex 14 Controlling OFS", "Annex 14 Controlling OES"}:
                        self._apply_controlling_region_labels(layer)
                    if str(style_key) in {"Annex 14 OFS Contour", "Annex 14 OES Contour"}:
                        if str(layer.name()).startswith("Controlling "):
                            self._apply_controlling_contour_style(
                                layer,
                                palette="ofs" if str(style_key) == "Annex 14 OFS Contour" else "default",
                            )
                        else:
                            self._apply_controlling_contour_labels(
                                layer,
                                '"contour_elev_am" IS NOT NULL',
                            )
                    if str(style_key) == "Parallel Runway Standards Line":
                        self._apply_parallel_runway_standards_style(layer)
                    if str(style_key) in {
                        "OLS Modernisation Gain",
                        "OLS Modernisation Loss",
                        "OLS Modernisation No Change",
                        "OLS Modernisation No Future Overlay",
                    }:
                        self._apply_modernisation_comparison_style(layer, str(style_key))
                    if str(style_key) in {
                        "OLS Modernisation Baseline Wireframe",
                        "OLS Modernisation Future Wireframe",
                    }:
                        self._apply_modernisation_wireframe_style(layer, str(style_key))
                    if str(style_key) == "OLS Modernisation Transition":
                        self._apply_modernisation_transition_style(layer)
                    if str(style_key) == "OLS Modernisation Change Contour":
                        self._apply_modernisation_change_contour_style(layer)
                    if str(style_key) in {"OLS IHS", "OLS OHS"}:
                        self._apply_horizontal_surface_labels(layer, decimal_places=1)
                    if str(style_key) == "OLS Approach":
                        self._apply_horizontal_surface_labels(
                            layer,
                            filter_expression='"section_desc" = \'Horizontal\'',
                            decimal_places=2,
                        )
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

    def _apply_modernisation_comparison_style(self, layer: QgsVectorLayer, style_key: str) -> None:
        """Apply readable gain/loss/no-overlay comparison symbols and delta labels."""
        if style_key == "OLS Modernisation Gain":
            fill = QColor(55, 168, 82, 95)
            outline = QColor(27, 112, 52, 230)
        elif style_key == "OLS Modernisation Loss":
            fill = QColor(214, 63, 63, 95)
            outline = QColor(155, 32, 32, 230)
        elif style_key == "OLS Modernisation No Change":
            fill = QColor(138, 145, 148, 58)
            outline = QColor(92, 99, 103, 190)
        elif style_key == "OLS Modernisation No Future Overlay":
            fill = QColor(112, 118, 121, 42)
            outline = QColor(78, 85, 89, 175)
        else:
            fill = QColor(150, 150, 150, 45)
            outline = QColor(95, 95, 95, 210)
        symbol_options = {
            "color": fill.name(QColor.NameFormat.HexArgb),
            "outline_color": outline.name(QColor.NameFormat.HexArgb),
            "outline_width": "0.45",
            "outline_width_unit": "MM",
        }
        if style_key == "OLS Modernisation No Change":
            symbol_options.update(
                {
                    "style": "diagonal_x",
                    "outline_width": "0.35",
                    "outline_style": "dash",
                }
            )
        elif style_key == "OLS Modernisation No Future Overlay":
            symbol_options.update(
                {
                    "style": "b_diagonal",
                    "outline_width": "0.32",
                    "outline_style": "dot",
                }
            )
        symbol = QgsFillSymbol.createSimple(symbol_options)
        symbol.setColor(fill)
        layer.setRenderer(QgsSingleSymbolRenderer(symbol))
        self._apply_modernisation_comparison_labels(layer, style_key)

    def _apply_modernisation_wireframe_style(self, layer: QgsVectorLayer, style_key: str) -> None:
        """Render comparison envelope polygons as outline-only wireframes."""
        if style_key == "OLS Modernisation Baseline Wireframe":
            outline = QColor(45, 76, 109, 235)
            line_style = "solid"
        else:
            outline = QColor(128, 68, 170, 235)
            line_style = "dash"
        symbol = QgsFillSymbol.createSimple(
            {
                "color": "0,0,0,0",
                "outline_color": outline.name(QColor.NameFormat.HexArgb),
                "outline_width": "0.34",
                "outline_width_unit": "MM",
                "outline_style": line_style,
            }
        )
        symbol.setColor(QColor(0, 0, 0, 0))
        layer.setRenderer(QgsSingleSymbolRenderer(symbol))

    def _apply_modernisation_transition_style(self, layer: QgsVectorLayer) -> None:
        """Render baseline/future equal-height breaklines as dashed transition guides."""
        symbol = QgsLineSymbol.createSimple(
            {
                "line_color": "32,32,32,245",
                "line_width": "0.46",
                "line_width_unit": "MM",
                "line_style": "dash",
            }
        )
        layer.setRenderer(QgsSingleSymbolRenderer(symbol))

    @staticmethod
    def _persisted_field_name(layer: QgsVectorLayer, requested_name: str) -> str:
        """Resolve a source field after formats such as Shapefile truncate it."""
        field_names = [field.name() for field in layer.fields()]
        requested_folded = str(requested_name).casefold()
        for field_name in field_names:
            if field_name.casefold() == requested_folded:
                return field_name

        # The ESRI Shapefile driver launders names to ten characters.  Prefer
        # that deterministic form, then accept it as a unique prefix so this
        # also works with providers that use a shorter limit.
        truncated = requested_folded[:10]
        for field_name in field_names:
            if field_name.casefold() == truncated:
                return field_name
        prefix_matches = [
            field_name
            for field_name in field_names
            if requested_folded.startswith(field_name.casefold())
        ]
        if len(prefix_matches) == 1:
            return prefix_matches[0]
        return requested_name

    def _apply_modernisation_change_contour_style(self, layer: QgsVectorLayer) -> None:
        """Render signed change contours by direction and primary/intermediate class."""
        change_field = self._persisted_field_name(layer, "change")
        contour_class_field = self._persisted_field_name(layer, "contour_class")
        root = QgsRuleBasedRenderer.Rule(None)
        symbol_definitions = (
            ("transition", "primary", "76,84,88,235", "0.38", "dash", "0.0 m / equal height"),
            ("gain", "primary", "27,112,52,245", "0.42", "solid", "Raised — primary"),
            ("gain", "intermediate", "55,168,82,205", "0.22", "solid", "Raised — intermediate"),
            ("loss", "primary", "155,32,32,245", "0.42", "solid", "Lowered — primary"),
            ("loss", "intermediate", "214,63,63,205", "0.22", "solid", "Lowered — intermediate"),
        )
        for change, contour_class, color, width, line_style, label in symbol_definitions:
            symbol = QgsLineSymbol.createSimple(
                {
                    "line_color": color,
                    "line_width": width,
                    "line_width_unit": "MM",
                    "line_style": line_style,
                }
            )
            rule = QgsRuleBasedRenderer.Rule(symbol)
            rule.setFilterExpression(
                f'"{change_field}" = \'{change}\' AND '
                f'"{contour_class_field}" = \'{contour_class}\''
            )
            rule.setLabel(label)
            root.appendChild(rule)
        layer.setRenderer(QgsRuleBasedRenderer(root))
        self._apply_modernisation_change_contour_labels(
            layer,
            contour_class_field=contour_class_field,
        )

    def _apply_modernisation_change_contour_labels(
        self,
        layer: QgsVectorLayer,
        contour_class_field: Optional[str] = None,
    ) -> None:
        """Label signed change isolines while allowing QGIS to suppress collisions."""
        label_field = self._persisted_field_name(layer, "label_txt")
        if layer.fields().indexFromName(label_field) < 0:
            return
        contour_class_field = contour_class_field or self._persisted_field_name(
            layer,
            "contour_class",
        )
        try:
            settings = QgsPalLayerSettings()
            settings.fieldName = label_field
            settings.placement = QgsPalLayerSettings.Line
            try:
                line_settings = settings.lineSettings()
                if hasattr(line_settings, "setMergeLines"):
                    line_settings.setMergeLines(True)
                if hasattr(settings, "labelPerPart"):
                    settings.labelPerPart = False
            except Exception:
                pass
            settings.priority = 7
            settings.obstacle = False

            text_format = QgsTextFormat()
            text_format.setFont(QFont("Helvetica", 8))
            text_format.setSize(8)
            text_format.setColor(QColor(47, 52, 55))
            buffer = QgsTextBufferSettings()
            buffer.setEnabled(True)
            buffer.setSize(0.8)
            buffer.setColor(QColor(255, 255, 255))
            text_format.setBuffer(buffer)
            settings.setFormat(text_format)

            root = QgsRuleBasedLabeling.Rule(None)
            rule = QgsRuleBasedLabeling.Rule(settings)
            rule.setFilterExpression(
                f'"{contour_class_field}" = \'primary\' AND '
                f'"{label_field}" IS NOT NULL AND "{label_field}" <> \'\''
            )
            root.appendChild(rule)
            layer.setLabeling(QgsRuleBasedLabeling(root))
            layer.setLabelsEnabled(True)
        except Exception as exc:
            QgsMessageLog.logMessage(
                f"Warning: failed to apply OLS modernisation change-contour labels: {exc}",
                PLUGIN_TAG,
                level=Qgis.Warning,
            )

    def _apply_modernisation_comparison_labels(self, layer: QgsVectorLayer, style_key: str) -> None:
        """Label larger comparison polygons with their sampled height-change range."""
        if layer.fields().indexFromName("label_txt") < 0:
            return
        try:
            settings = QgsPalLayerSettings()
            settings.fieldName = "label_txt"
            settings.placement = QgsPalLayerSettings.Horizontal
            settings.centroidInside = True
            settings.centroidWhole = False
            settings.fitInPolygonOnly = True
            try:
                settings.setPolygonPlacementFlags(Qgis.LabelPolygonPlacementFlag.AllowPlacementInsideOfPolygon)
            except Exception:
                pass
            settings.priority = 7
            settings.obstacle = False

            text_format = QgsTextFormat()
            text_format.setFont(QFont("Helvetica", 9))
            text_format.setSize(9)
            if style_key == "OLS Modernisation Gain":
                text_format.setColor(QColor(20, 94, 42))
            elif style_key == "OLS Modernisation Loss":
                text_format.setColor(QColor(132, 29, 29))
            elif style_key == "OLS Modernisation No Change":
                text_format.setColor(QColor(74, 82, 86))
            elif style_key == "OLS Modernisation No Future Overlay":
                text_format.setColor(QColor(68, 74, 78))
            else:
                text_format.setColor(QColor(80, 80, 80))

            buffer = QgsTextBufferSettings()
            buffer.setEnabled(True)
            buffer.setSize(0.9)
            buffer.setColor(QColor(255, 255, 255))
            text_format.setBuffer(buffer)
            settings.setFormat(text_format)

            root = QgsRuleBasedLabeling.Rule(None)
            rule = QgsRuleBasedLabeling.Rule(settings)
            rule.setFilterExpression('"label_txt" IS NOT NULL AND "label_txt" <> \'\' AND $area >= 2500')
            root.appendChild(rule)
            layer.setLabeling(QgsRuleBasedLabeling(root))
            layer.setLabelsEnabled(True)
        except Exception as exc:
            QgsMessageLog.logMessage(
                f"Warning: failed to apply OLS modernisation comparison labels: {exc}",
                PLUGIN_TAG,
                level=Qgis.Warning,
            )

    def _prune_annex14_renderer_rules(self, layer: QgsVectorLayer):
        """Keep only Annex 14 legend rules matching non-empty layer features."""
        if layer is None or not layer.isValid() or layer.fields().indexOf("surface") < 0:
            return
        renderer = layer.renderer()
        if renderer is None or renderer.type() != "RuleRenderer":
            return
        root_rule = renderer.rootRule()
        for rule in list(root_rule.children()):
            if rule.isElse():
                root_rule.removeChild(rule)
                continue
            expression = str(rule.filterExpression() or "").strip()
            request = QgsFeatureRequest()
            if expression:
                request.setFilterExpression(expression)
            represented = False
            try:
                for feature in layer.getFeatures(request):
                    geometry = feature.geometry()
                    if geometry is not None and not geometry.isEmpty():
                        represented = True
                        break
            except Exception:
                represented = False
            if not represented:
                root_rule.removeChild(rule)
        remaining_rules = list(root_rule.children())
        if (
            len(remaining_rules) == 1
            and not str(layer.name()).startswith("Controlling ")
        ):
            symbol = remaining_rules[0].symbol()
            if symbol is not None:
                layer.setRenderer(QgsSingleSymbolRenderer(symbol.clone()))
                return
        # Assign a distinct renderer instance so the QGIS layer-tree model
        # invalidates legend nodes created when the full QML was first loaded.
        # Reassigning the same mutated object can leave absent surface rules
        # visible in the legend even though the renderer no longer contains
        # matching features.
        layer.setRenderer(renderer.clone())

    def _apply_controlling_region_style(self, layer: QgsVectorLayer):
        """Apply complementary solid fills for controlling OLS regions."""
        if layer is None or not layer.isValid():
            return
        try:
            categories = []
            for surface, fill_color, outline_color in [
                ("Approach", "42,157,181,115", "22,98,116,230"),
                ("TOCS", "240,166,76,115", "150,85,31,230"),
                ("Transitional", "88,178,124,105", "42,105,65,230"),
                ("Conical", "160,105,194,100", "95,58,125,230"),
                ("IHS", "236,205,91,100", "145,118,37,230"),
                ("OHS", "119,135,158,85", "70,84,105,220"),
            ]:
                symbol = QgsFillSymbol.createSimple(
                    {
                        "color": fill_color,
                        "outline_color": outline_color,
                        "outline_width": "0.22",
                        "outline_width_unit": "MM",
                        "style": "solid",
                    }
                )
                categories.append(QgsRendererCategory(surface, symbol, surface))
            layer.setRenderer(QgsCategorizedSymbolRenderer("surface", categories))
            self._apply_controlling_region_labels(layer)
        except Exception as exc:
            QgsMessageLog.logMessage(
                f"Warning: failed to apply controlling OLS region style: {exc}",
                PLUGIN_TAG,
                level=Qgis.Warning,
            )

    def _apply_controlling_region_labels(self, layer: QgsVectorLayer):
        """Label flat controlling regions with their horizontal-plane elevation."""
        if layer is None or not layer.isValid():
            return
        if layer.fields().indexFromName("elev_min") < 0 or layer.fields().indexFromName("elev_max") < 0:
            return
        has_surface = layer.fields().indexFromName("surface") >= 0
        try:
            settings = QgsPalLayerSettings()
            if has_surface:
                settings.fieldName = (
                    "'HP' || '\n' || "
                    'CASE WHEN "surface" = \'Approach\' '
                    'THEN format_number("elev_max", 2) '
                    'ELSE format_number("elev_max", 1) '
                    "END"
                )
            else:
                settings.fieldName = (
                    "'HP' || '\n' || "
                    'format_number("elev_max", 1)'
                )
            settings.isExpression = True
            settings.placement = QgsPalLayerSettings.Horizontal
            settings.centroidInside = True
            settings.centroidWhole = False
            settings.fitInPolygonOnly = True
            try:
                settings.setPolygonPlacementFlags(Qgis.LabelPolygonPlacementFlag.AllowPlacementInsideOfPolygon)
            except Exception:
                pass
            settings.priority = 5
            settings.obstacle = False

            text_format = QgsTextFormat()
            text_format.setFont(QFont("Helvetica", 10))
            text_format.setSize(10)
            text_format.setColor(QColor(50, 50, 50))

            buffer = QgsTextBufferSettings()
            buffer.setEnabled(True)
            buffer.setSize(1)
            buffer.setColor(QColor(250, 250, 250))
            text_format.setBuffer(buffer)
            settings.setFormat(text_format)

            root = QgsRuleBasedLabeling.Rule(None)
            rule = QgsRuleBasedLabeling.Rule(settings)
            rule.setFilterExpression(
                '"elev_min" IS NOT NULL AND "elev_max" IS NOT NULL '
                'AND abs("elev_min" - "elev_max") <= 0.01 '
                "AND $area >= 10000"
            )
            root.appendChild(rule)
            layer.setLabeling(QgsRuleBasedLabeling(root))
            layer.setLabelsEnabled(True)
        except Exception as exc:
            QgsMessageLog.logMessage(
                f"Warning: failed to apply controlling OLS region labels: {exc}",
                PLUGIN_TAG,
                level=Qgis.Warning,
            )

    def _apply_controlling_contour_style(self, layer: QgsVectorLayer, palette: str = "default"):
        """Keep controlling contours visually distinct and label-ready."""
        if layer is None or not layer.isValid():
            return
        try:
            surface_values = {
                str(feature.attribute("surface") or "")
                for feature in layer.getFeatures()
            } if layer.fields().indexFromName("surface") >= 0 else set()
            contour_classes = {
                str(feature.attribute("contour_class") or "")
                for feature in layer.getFeatures()
            } if layer.fields().indexFromName("contour_class") >= 0 else set()
            if layer.fields().indexFromName("contour_class") >= 0:
                index_expression = '"contour_class" = \'primary\''
            else:
                index_expression = (
                    '"contour_elev_am" IS NOT NULL AND '
                    'abs(("contour_elev_am" / 50.0) - round("contour_elev_am" / 50.0)) <= 0.001'
                )
            root = QgsRuleBasedRenderer.Rule(None)
            primary_filter = f'("surface" IS NULL OR "surface" <> \'Transition\') AND ({index_expression})'
            if palette == "ofs":
                primary_color = "174,68,45,245"
                intermediate_color = "190,103,36,185"
            else:
                primary_color = "18,75,82,240"
                intermediate_color = "38,111,117,175"

            if "Transition" in surface_values:
                transition_symbol = QgsLineSymbol.createSimple(
                    {
                        "line_color": "196,59,77,245",
                        "line_width": "0.44",
                        "line_width_unit": "MM",
                        "line_style": "dash",
                    }
                )
                transition_rule = QgsRuleBasedRenderer.Rule(transition_symbol)
                transition_rule.setFilterExpression('"surface" = \'Transition\'')
                transition_rule.setLabel("Transition / intersection")
                root.appendChild(transition_rule)

            index_symbol = QgsLineSymbol.createSimple(
                {
                    "line_color": primary_color,
                    "line_width": "0.40",
                    "line_width_unit": "MM",
                    "line_style": "solid",
                }
            )
            index_rule = QgsRuleBasedRenderer.Rule(index_symbol)
            index_rule.setFilterExpression(primary_filter)
            index_rule.setLabel("Primary contour")
            if not contour_classes or "primary" in contour_classes:
                root.appendChild(index_rule)

            normal_symbol = QgsLineSymbol.createSimple(
                {
                    "line_color": intermediate_color,
                    "line_width": "0.20",
                    "line_width_unit": "MM",
                    "line_style": "solid",
                }
            )
            normal_rule = QgsRuleBasedRenderer.Rule(normal_symbol)
            normal_rule.setFilterExpression(
                f'("surface" IS NULL OR "surface" <> \'Transition\') AND NOT ({index_expression})'
            )
            normal_rule.setLabel("Intermediate contour")
            if not contour_classes or "intermediate" in contour_classes:
                root.appendChild(normal_rule)

            layer.setRenderer(QgsRuleBasedRenderer(root))
            self._apply_controlling_contour_labels(layer, primary_filter)
        except Exception as exc:
            QgsMessageLog.logMessage(
                f"Warning: failed to apply controlling contour line style: {exc}",
                PLUGIN_TAG,
                level=Qgis.Warning,
            )

    def _apply_controlling_contour_labels(self, layer: QgsVectorLayer, index_expression: str):
        """Label only index controlling contours to keep dense areas readable."""
        if layer is None or not layer.isValid() or layer.fields().indexFromName("contour_elev_am") < 0:
            return
        try:
            settings = QgsPalLayerSettings()
            settings.fieldName = (
                "CASE "
                "WHEN round(\"contour_elev_am\" * 2) / 2 = floor(round(\"contour_elev_am\" * 2) / 2) "
                "THEN format_number(round(\"contour_elev_am\" * 2) / 2, 0) "
                "ELSE format_number(round(\"contour_elev_am\" * 2) / 2, 1) "
                "END"
            )
            settings.isExpression = True
            settings.placement = QgsPalLayerSettings.Line
            try:
                line_settings = settings.lineSettings()
                qgis_core = __import__("qgis.core").core
                placement_flag_owner = getattr(qgis_core, "QgsLabelLineSettings", None)
                on_line = None
                if placement_flag_owner is not None:
                    on_line = getattr(placement_flag_owner, "OnLine", None)
                    if on_line is None and hasattr(placement_flag_owner, "LinePlacementFlag"):
                        on_line = getattr(placement_flag_owner.LinePlacementFlag, "OnLine", None)
                if on_line is None:
                    on_line = getattr(QgsPalLayerSettings, "OnLine", None)
                if on_line is not None:
                    if hasattr(line_settings, "setPlacementFlags"):
                        line_settings.setPlacementFlags(on_line)
                    elif hasattr(settings, "placementFlags"):
                        settings.placementFlags = on_line
                if hasattr(line_settings, "setMergeLines"):
                    line_settings.setMergeLines(True)
                if hasattr(settings, "labelPerPart"):
                    settings.labelPerPart = False
            except Exception:
                pass
            settings.priority = 6
            settings.obstacle = False

            text_format = QgsTextFormat()
            text_format.setFont(QFont("Helvetica", 9))
            text_format.setSize(9)
            text_format.setColor(QColor(47, 52, 55))

            buffer = QgsTextBufferSettings()
            buffer.setEnabled(True)
            buffer.setSize(0.8)
            buffer.setColor(QColor(255, 255, 255))
            text_format.setBuffer(buffer)
            settings.setFormat(text_format)

            root = QgsRuleBasedLabeling.Rule(None)
            rule = QgsRuleBasedLabeling.Rule(settings)
            rule.setFilterExpression(f"({index_expression})")
            root.appendChild(rule)
            layer.setLabeling(QgsRuleBasedLabeling(root))
            layer.setLabelsEnabled(True)
        except Exception as exc:
            QgsMessageLog.logMessage(
                f"Warning: failed to apply controlling contour labels: {exc}",
                PLUGIN_TAG,
                level=Qgis.Warning,
            )

    def _apply_parallel_runway_standards_style(self, layer: QgsVectorLayer):
        """Apply operation categories and centred on-line labels for runway separation guides."""
        if layer is None or not layer.isValid():
            return
        try:
            def line_symbol(color: str, line_style: str = "solid") -> QgsLineSymbol:
                return QgsLineSymbol.createSimple(
                    {
                        "line_color": color,
                        "line_width": "0.32",
                        "line_width_unit": "MM",
                        "line_style": line_style,
                    }
                )

            layer.setRenderer(
                QgsCategorizedSymbolRenderer(
                    "op_cat",
                    [
                        QgsRendererCategory(
                            "Simultaneous use",
                            line_symbol("227,187,50,230"),
                            "Simultaneous use",
                        ),
                        QgsRendererCategory(
                            "Independent approaches",
                            line_symbol("38,122,181,230"),
                            "Independent approaches",
                        ),
                        QgsRendererCategory(
                            "Dependent approaches",
                            line_symbol("74,145,204,230"),
                            "Dependent approaches",
                        ),
                        QgsRendererCategory(
                            "Independent departures",
                            line_symbol("38,122,181,230"),
                            "Independent departures",
                        ),
                        QgsRendererCategory(
                            "Segregated operations",
                            line_symbol("38,122,181,230", "dash"),
                            "Segregated operations",
                        ),
                    ],
                )
            )

            if layer.fields().indexFromName("label_txt") >= 0:
                settings = QgsPalLayerSettings()
                settings.fieldName = "label_txt"
                settings.placement = QgsPalLayerSettings.Line
                for distance_attr in ("dist", "xOffset", "yOffset"):
                    if hasattr(settings, distance_attr):
                        setattr(settings, distance_attr, 0)
                try:
                    line_settings = settings.lineSettings()
                    qgis_core = __import__("qgis.core").core
                    placement_flag_owner = getattr(qgis_core, "QgsLabelLineSettings", None)
                    on_line = None
                    if placement_flag_owner is not None:
                        on_line = getattr(placement_flag_owner, "OnLine", None)
                        if on_line is None and hasattr(placement_flag_owner, "LinePlacementFlag"):
                            on_line = getattr(placement_flag_owner.LinePlacementFlag, "OnLine", None)
                    if on_line is None:
                        on_line = getattr(QgsPalLayerSettings, "OnLine", None)
                    if on_line is not None:
                        if hasattr(line_settings, "setPlacementFlags"):
                            line_settings.setPlacementFlags(on_line)
                        elif hasattr(settings, "placementFlags"):
                            settings.placementFlags = on_line
                    if hasattr(line_settings, "setAnchorPercent"):
                        line_settings.setAnchorPercent(0.5)
                    if hasattr(line_settings, "setAnchorType"):
                        anchor_type = None
                        if placement_flag_owner is not None and hasattr(placement_flag_owner, "AnchorType"):
                            anchor_type = getattr(placement_flag_owner.AnchorType, "Strict", None)
                        if anchor_type is not None:
                            line_settings.setAnchorType(anchor_type)
                    if hasattr(line_settings, "setMergeLines"):
                        line_settings.setMergeLines(True)
                    if hasattr(settings, "labelPerPart"):
                        settings.labelPerPart = False
                except Exception:
                    pass
                settings.priority = 6
                settings.obstacle = False

                text_format = QgsTextFormat()
                text_format.setFont(QFont("Lato", 9))
                text_format.setSize(9)
                text_format.setColor(QColor(35, 70, 100))

                buffer = QgsTextBufferSettings()
                buffer.setEnabled(True)
                buffer.setSize(0.9)
                buffer.setColor(QColor(255, 255, 255))
                text_format.setBuffer(buffer)

                settings.setFormat(text_format)
                layer.setLabeling(QgsVectorLayerSimpleLabeling(settings))
                layer.setLabelsEnabled(True)
        except Exception as exc:
            QgsMessageLog.logMessage(
                f"Warning: failed to apply parallel runway standards style: {exc}",
                PLUGIN_TAG,
                level=Qgis.Warning,
            )

    def _apply_horizontal_surface_labels(
        self,
        layer: QgsVectorLayer,
        filter_expression: Optional[str] = None,
        decimal_places: int = 1,
    ) -> None:
        """Label a horizontal polygon surface at its centroid with elevation."""
        if layer is None or not layer.isValid():
            return
        has_elev_max = layer.fields().indexFromName("elev_max") >= 0
        has_elev_m = layer.fields().indexFromName("elev_m") >= 0
        if not has_elev_max and not has_elev_m:
            return

        try:
            elevation_expression = '"elev_max"' if has_elev_max else '"elev_m"'
            settings = QgsPalLayerSettings()
            settings.fieldName = (
                "'HP' || '\n' || "
                f"format_number({elevation_expression}, {max(0, int(decimal_places))})"
            )
            settings.isExpression = True
            settings.placement = QgsPalLayerSettings.Horizontal
            settings.centroidInside = True
            settings.centroidWhole = False
            settings.fitInPolygonOnly = True
            try:
                settings.setPolygonPlacementFlags(Qgis.LabelPolygonPlacementFlag.AllowPlacementInsideOfPolygon)
            except Exception:
                pass
            settings.priority = 5
            settings.obstacle = False

            text_format = QgsTextFormat()
            text_format.setFont(QFont("Lato", 10))
            text_format.setSize(10)
            text_format.setColor(QColor(50, 50, 50))

            buffer = QgsTextBufferSettings()
            buffer.setEnabled(True)
            buffer.setSize(1)
            buffer.setColor(QColor(250, 250, 250))
            text_format.setBuffer(buffer)

            settings.setFormat(text_format)

            if filter_expression:
                root = QgsRuleBasedLabeling.Rule(None)
                rule = QgsRuleBasedLabeling.Rule(settings)
                rule.setFilterExpression(filter_expression)
                root.appendChild(rule)
                layer.setLabeling(QgsRuleBasedLabeling(root))
            else:
                layer.setLabeling(QgsVectorLayerSimpleLabeling(settings))
            layer.setLabelsEnabled(True)
        except Exception as exc:
            QgsMessageLog.logMessage(
                f"Warning: failed to apply horizontal surface labels for '{layer.name()}': {exc}",
                PLUGIN_TAG,
                level=Qgis.Warning,
            )

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
