# -*- coding: utf-8 -*-
"""Physical runway geometry generation."""

import traceback
from typing import Dict, List, Optional, Tuple

from qgis.PyQt.QtCore import QVariant  # type: ignore
from qgis.core import (  # type: ignore
    Qgis,
    QgsFeature,
    QgsField,
    QgsFields,
    QgsGeometry,
    QgsLayerTreeGroup,
    QgsMessageLog,
    QgsProject,
)

from .. import ols_dimensions

PLUGIN_TAG = "SafeguardingBuilder"


class PhysicalGeometryMixin:

    def _process_physical_and_protection_layers(
        self,
        main_group: QgsLayerTreeGroup,
        icao_code: str,
        processed_runway_data_list: List[dict],
        any_runway_base_data_ok: bool,
    ) -> Tuple[Optional[QgsLayerTreeGroup], bool]:
        plugin_tag = PLUGIN_TAG
        specialised_safeguarding_group = None
        physical_geom_group = None
        protection_area_group = None
        physical_layer_specs = {}
        physical_features: Dict[str, List[QgsFeature]] = {}
        any_physical_or_protection_ok = False

        if processed_runway_data_list and any_runway_base_data_ok:
            physical_geom_group = main_group.addGroup(self.tr("Physical Geometry"))
            self._stage_layer_tree_node(physical_geom_group)
            protection_area_group = main_group.addGroup(
                self.tr("Runway Protection Areas")
            )
            self._stage_layer_tree_node(protection_area_group)
            specialised_safeguarding_group = main_group.findGroup(
                self.tr("Specialised Safeguarding")
            )
            if (
                specialised_safeguarding_group is None
            ):  # Should have been created earlier
                specialised_safeguarding_group = main_group.addGroup(
                    self.tr("Specialised Safeguarding")
                )
            self._stage_layer_tree_node(specialised_safeguarding_group)

            if (
                physical_geom_group is not None
                and protection_area_group is not None
                and specialised_safeguarding_group is not None
            ):
                common_fields = [
                    QgsField("rwy", QVariant.String, self.tr("Runway Name"), 30),
                    QgsField("desc", QVariant.String, self.tr("Element Type"), 50),
                    QgsField("len_m", QVariant.Double, self.tr("len_m"), 12, 3),
                    QgsField("wid_m", QVariant.Double, self.tr("wid_m"), 12, 3),
                    QgsField(
                        "ref_mos", QVariant.String, self.tr("MOS Reference"), 250
                    ),
                ]
                stopway_resa_fields = common_fields + [
                    QgsField(
                        "end_desig", QVariant.String, self.tr("End Designator"), 10
                    )
                ]
                pre_threshold_fields = common_fields + [
                    QgsField(
                        "end_desig", QVariant.String, self.tr("End Designator"), 10
                    )
                ]
                marking_fields = [
                    QgsField("rwy", QVariant.String, self.tr("Runway Name"), 30),
                    QgsField("desc", QVariant.String, self.tr("Element Type"), 50),
                    QgsField("len_m", QVariant.Double, self.tr("len_m"), 12, 3),
                    QgsField(
                        "end_desig", QVariant.String, self.tr("End Designator"), 10
                    ),
                    QgsField(
                        "ref_mos", QVariant.String, self.tr("MOS Reference"), 250
                    ),
                ]

                layer_definitions = {
                    "rwy": {
                        "name": self.tr("Runway Pavement"),
                        "fields": common_fields,
                        "group": physical_geom_group,
                    },
                    "PreThresholdRunway": {
                        "name": self.tr("Pre-Threshold Runway"),
                        "fields": pre_threshold_fields,
                        "group": physical_geom_group,
                    },
                    "PreThresholdArea": {
                        "name": self.tr("Pre-Threshold Area"),
                        "fields": pre_threshold_fields,
                        "group": physical_geom_group,
                    },
                    "DisplacedThresholdMarking": {
                        "name": self.tr("Displaced Threshold Markings"),
                        "fields": marking_fields,
                        "geom_type": "LineString",
                        "group": physical_geom_group,
                    },
                    "PreThresholdAreaMarking": {
                        "name": self.tr("Pre-Threshold Area Markings"),
                        "fields": marking_fields,
                        "geom_type": "LineString",
                        "group": physical_geom_group,
                    },
                    "Shoulder": {
                        "name": self.tr("Runway Shoulders"),
                        "fields": common_fields,
                        "group": physical_geom_group,
                    },
                    "Stopway": {
                        "name": self.tr("Stopways"),
                        "fields": stopway_resa_fields,
                        "group": protection_area_group,
                    },
                    "GradedStrip": {
                        "name": self.tr("Runway Graded Strip"),
                        "fields": common_fields,
                        "group": protection_area_group,
                    },
                    "FlyoverStrip": {
                        "name": self.tr("Runway Strip Flyover Area"),
                        "fields": common_fields,
                        "group": protection_area_group,
                    },
                    "OverallStrip": {
                        "name": self.tr("Runway Overall Strip"),
                        "fields": common_fields,
                        "group": protection_area_group,
                    },
                    "RESA": {
                        "name": self.tr("Runway End Safety Area (RESA)"),
                        "fields": stopway_resa_fields,
                        "group": protection_area_group,
                    },
                }
                style_key_map = {
                    "rwy": "Runway Pavement",
                    "PreThresholdRunway": "PreThreshold Runway",
                    "PreThresholdArea": "PreThreshold Area",
                    "DisplacedThresholdMarking": "DisplacedThresholdMarking",
                    "PreThresholdAreaMarking": "PreThresholdAreaMarking",
                    "Shoulder": "Runway Shoulders",
                    "Stopway": "Stopways",
                    "GradedStrip": "Runway Graded Strips",
                    "FlyoverStrip": "Runway Strip Flyover Area",
                    "OverallStrip": "Runway Overall Strips",
                    "RESA": "Runway End Safety Areas (RESA)",
                }

                for element_type, definition in layer_definitions.items():
                    target_group = definition.get("group")
                    if target_group is None:
                        QgsMessageLog.logMessage(
                            f"Warning: No target group defined for {element_type}, skipping layer setup.",
                            plugin_tag,
                            level=Qgis.Warning,
                        )
                        continue
                    geom_type_str = definition.get("geom_type", "Polygon")
                    layer_display_name = f"{icao_code} {definition['name']}"
                    if geom_type_str not in {"LineString", "Polygon"}:
                        QgsMessageLog.logMessage(
                            f"Warning: Unsupported geometry type '{geom_type_str}' for layer URI.",
                            plugin_tag,
                            level=Qgis.Warning,
                        )
                        continue

                    fields_copy = QgsFields()
                    for field in definition["fields"]:
                        fields_copy.append(field)
                    physical_layer_specs[element_type] = {
                        "display_name": layer_display_name,
                        "fields": fields_copy,
                        "geom_type": geom_type_str,
                        "group": target_group,
                        "style_key": style_key_map.get(
                            element_type, "Default Polygon"
                        ),
                    }
                    physical_features[element_type] = []

                QgsMessageLog.logMessage(
                    "Populating physical geometry & protection area layers...",
                    plugin_tag,
                    level=Qgis.Info,
                )
                for rwy_data in processed_runway_data_list:
                    runway_name_log = rwy_data.get(
                        "short_name", f"RWY_{rwy_data.get('original_index','?')}"
                    )
                    try:
                        generated_elements_list = self.generate_physical_geometry(
                            rwy_data
                        )
                        if generated_elements_list is None:
                            continue

                        graded_strip_geom: Optional[QgsGeometry] = None
                        overall_strip_geom: Optional[QgsGeometry] = None
                        graded_strip_attrs: Optional[dict] = None
                        overall_strip_attrs: Optional[dict] = None

                        for (
                            element_type,
                            geometry,
                            attributes,
                        ) in generated_elements_list:
                            target_spec = physical_layer_specs.get(element_type)
                            if target_spec is None:
                                continue
                            if geometry is None or geometry.isEmpty():
                                continue
                            if not geometry.isGeosValid():
                                geometry = geometry.makeValid()
                            if (
                                geometry is None
                                or geometry.isEmpty()
                                or not geometry.isGeosValid()
                            ):
                                continue

                            if element_type == "GradedStrip":
                                graded_strip_geom = geometry
                                graded_strip_attrs = attributes
                            elif element_type == "OverallStrip":
                                overall_strip_geom = geometry
                                overall_strip_attrs = attributes

                            feature = QgsFeature(target_spec["fields"])
                            feature.setGeometry(geometry)
                            for field_name, value in attributes.items():
                                idx = feature.fieldNameIndex(field_name)
                                if idx != -1:
                                    feature.setAttribute(idx, value)

                            physical_features[element_type].append(feature)
                            any_physical_or_protection_ok = True

                        flyover_spec = physical_layer_specs.get("FlyoverStrip")
                        if (
                            flyover_spec is not None
                            and graded_strip_geom is not None
                            and overall_strip_geom is not None
                        ):
                            try:
                                # Ensure inputs are valid before difference
                                if not graded_strip_geom.isGeosValid():
                                    graded_strip_geom = (
                                        graded_strip_geom.makeValid()
                                    )
                                if not overall_strip_geom.isGeosValid():
                                    overall_strip_geom = (
                                        overall_strip_geom.makeValid()
                                    )

                                if (
                                    graded_strip_geom
                                    and overall_strip_geom
                                    and graded_strip_geom.isGeosValid()
                                    and overall_strip_geom.isGeosValid()
                                ):
                                    flyover_geom = overall_strip_geom.difference(
                                        graded_strip_geom
                                    )
                                    if flyover_geom and not flyover_geom.isEmpty():
                                        flyover_geom = (
                                            flyover_geom.makeValid()
                                        )  # Validate result
                                        if (
                                            flyover_geom
                                            and not flyover_geom.isEmpty()
                                            and flyover_geom.isGeosValid()
                                        ):
                                            # Create feature for flyover area
                                            flyover_feat = QgsFeature(
                                                flyover_spec["fields"]
                                            )
                                            flyover_feat.setGeometry(flyover_geom)

                                            # --- MODIFIED ATTRIBUTE CALCULATION FOR FLYOVER ---
                                            flyover_attrs = (
                                                {}
                                            )  # Start with an empty dict for flyover-specific attributes

                                            # 'rwy' and 'ref_mos' can be taken from overall_strip_attrs if available
                                            if overall_strip_attrs:
                                                flyover_attrs["rwy"] = (
                                                    overall_strip_attrs.get("rwy")
                                                )
                                                flyover_attrs["ref_mos"] = (
                                                    overall_strip_attrs.get(
                                                        "ref_mos"
                                                    )
                                                )

                                            flyover_attrs["desc"] = (
                                                "Flyover Strip Area"
                                            )

                                            # Calculate len_m and wid_m as per your logic
                                            # len_m can be taken from either graded or overall strip length
                                            if (
                                                graded_strip_attrs
                                                and "len_m" in graded_strip_attrs
                                            ):
                                                flyover_attrs["len_m"] = (
                                                    graded_strip_attrs["len_m"]
                                                )
                                            elif (
                                                overall_strip_attrs
                                                and "len_m" in overall_strip_attrs
                                            ):  # Fallback to overall
                                                flyover_attrs["len_m"] = (
                                                    overall_strip_attrs["len_m"]
                                                )
                                            else:
                                                flyover_attrs["len_m"] = (
                                                    None  # Or some default if neither is available
                                                )

                                            if (
                                                graded_strip_attrs
                                                and overall_strip_attrs
                                                and "wid_m" in graded_strip_attrs
                                                and "wid_m" in overall_strip_attrs
                                                and isinstance(
                                                    graded_strip_attrs["wid_m"],
                                                    (int, float),
                                                )
                                                and isinstance(
                                                    overall_strip_attrs["wid_m"],
                                                    (int, float),
                                                )
                                            ):

                                                overall_w = overall_strip_attrs[
                                                    "wid_m"
                                                ]
                                                graded_w = graded_strip_attrs[
                                                    "wid_m"
                                                ]
                                                if overall_w > graded_w:
                                                    flyover_attrs["wid_m"] = (
                                                        overall_w - graded_w
                                                    ) / 2.0
                                                else:
                                                    flyover_attrs["wid_m"] = (
                                                        0.0  # Or None, if width is not positive
                                                    )
                                                    QgsMessageLog.logMessage(
                                                        f"Warning: Overall strip width not greater than graded strip width for {runway_name_log}. Flyover width set to 0.",
                                                        plugin_tag,
                                                        level=Qgis.Warning,
                                                    )
                                            else:
                                                flyover_attrs["wid_m"] = None

                                            for (
                                                field_name,
                                                value,
                                            ) in flyover_attrs.items():
                                                idx = flyover_feat.fieldNameIndex(
                                                    field_name
                                                )
                                                if idx != -1:
                                                    flyover_feat.setAttribute(
                                                        idx, value
                                                    )

                                            physical_features[
                                                "FlyoverStrip"
                                            ].append(flyover_feat)
                                            any_physical_or_protection_ok = True
                                        else:
                                            QgsMessageLog.logMessage(
                                                f"Warning: FlyoverStrip geometry invalid after difference/makeValid for {runway_name_log}.",
                                                plugin_tag,
                                                level=Qgis.Warning,
                                            )
                                    else:
                                        QgsMessageLog.logMessage(
                                            f"Warning: FlyoverStrip geometry is empty after difference for {runway_name_log}.",
                                            plugin_tag,
                                            level=Qgis.Warning,
                                        )
                                else:
                                    QgsMessageLog.logMessage(
                                        f"Warning: Cannot calculate FlyoverStrip difference due to invalid input strip geometries for {runway_name_log}.",
                                        plugin_tag,
                                        level=Qgis.Warning,
                                    )
                            except Exception as e_diff:
                                QgsMessageLog.logMessage(
                                    f"Warning: Error calculating FlyoverStrip difference for {runway_name_log}: {e_diff}",
                                    plugin_tag,
                                    level=Qgis.Warning,
                                )
                        elif flyover_spec is not None:
                            QgsMessageLog.logMessage(
                                f"Info: Skipping FlyoverStrip for {runway_name_log}: Graded or Overall strip geometry missing.",
                                plugin_tag,
                                level=Qgis.Info,
                            )

                    except Exception as e_phys:
                        QgsMessageLog.logMessage(
                            f"Critical Error populating layers for {runway_name_log}: {e_phys}\n{traceback.format_exc()}",
                            plugin_tag,
                            level=Qgis.Critical,
                        )
                        continue

                QgsMessageLog.logMessage(
                    "Finalizing and saving physical geometry & protection area layers...",
                    plugin_tag,
                    level=Qgis.Info,
                )
                any_layer_successfully_processed_in_this_block = False

                for element_type, spec in physical_layer_specs.items():
                    features_to_write = physical_features.get(element_type, [])
                    if features_to_write:
                        final_layer = self._create_and_add_layer(
                            geometry_type_str=spec["geom_type"],
                            internal_name_base=element_type,
                            display_name=spec["display_name"],
                            fields=spec["fields"],
                            features=features_to_write,
                            layer_group=spec["group"],
                            style_key=spec["style_key"],
                        )
                        if final_layer is not None:
                            any_physical_or_protection_ok = True
                            any_layer_successfully_processed_in_this_block = True
                        features_to_write.clear()

                if (
                    not any_layer_successfully_processed_in_this_block
                    and physical_layer_specs
                ):
                    QgsMessageLog.logMessage(
                        "Warning: No physical geometry or protection area layers were successfully processed/saved in this block.",
                        plugin_tag,
                        Qgis.Warning,
                    )

                if physical_geom_group is not None:
                    project_root = QgsProject.instance().layerTreeRoot()
                    for rwy_data in processed_runway_data_list:
                        cl_layer = rwy_data.get("centreline_layer")
                        if cl_layer is not None:
                            cl_node = project_root.findLayer(cl_layer.id())
                            if cl_node is not None:
                                cloned_node = cl_node.clone()
                                self._stage_layer_tree_node(cloned_node)
                                physical_geom_group.insertChildNode(0, cloned_node)
                                if cl_node.parent() is not None:
                                    cl_node.parent().removeChildNode(cl_node)

            else:
                if physical_geom_group is None:
                    QgsMessageLog.logMessage(
                        "Failed to create 'Physical Geometry' subgroup.",
                        plugin_tag,
                        level=Qgis.Warning,
                    )
                if protection_area_group is None:
                    QgsMessageLog.logMessage(
                        "Failed to create 'Runway Protection Areas' subgroup.",
                        plugin_tag,
                        level=Qgis.Warning,
                    )

        return specialised_safeguarding_group, any_physical_or_protection_ok

    def generate_physical_geometry(
        self, runway_data: dict
    ) -> Optional[List[Tuple[str, QgsGeometry, dict]]]:
        """
        Calculates geometry and attributes for physical runway components.
        Returns a list of tuples: (element_type_key, geometry, attributes)
        or None if basic parameters are missing or calculation fails critically.
        Logs warnings for non-critical issues (e.g., single element failure).
        """
        plugin_tag = PLUGIN_TAG

        thr_point = runway_data.get("thr_point")
        rec_thr_point = runway_data.get("rec_thr_point")
        runway_width = runway_data.get("width")
        shoulder_width = runway_data.get("shoulder")
        runway_name = runway_data.get("short_name", "RWY")
        log_name = (
            runway_name
            if runway_name != "RWY"
            else f"RWY_{runway_data.get('original_index','?')}"
        )

        disp_val_1 = runway_data.get("thr_displaced_1")
        disp_val_2 = runway_data.get("thr_displaced_2")
        pre_val_1 = runway_data.get("thr_pre_area_1")
        pre_val_2 = runway_data.get("thr_pre_area_2")

        disp_thr_1: float = 0.0
        disp_thr_2: float = 0.0
        pre_area_len_1: float = 0.0
        pre_area_len_2: float = 0.0

        try:
            if disp_val_1 is not None:
                disp_thr_1 = float(disp_val_1)
        except (ValueError, TypeError):
            QgsMessageLog.logMessage(
                f"Warning: Invalid Displacement 1 value '{disp_val_1}' for {log_name}, using 0.0.",
                plugin_tag,
                level=Qgis.Warning,
            )
        try:
            if disp_val_2 is not None:
                disp_thr_2 = float(disp_val_2)
        except (ValueError, TypeError):
            QgsMessageLog.logMessage(
                f"Warning: Invalid Displacement 2 value '{disp_val_2}' for {log_name}, using 0.0.",
                plugin_tag,
                level=Qgis.Warning,
            )
        try:
            if pre_val_1 is not None:
                pre_area_len_1 = float(pre_val_1)
        except (ValueError, TypeError):
            QgsMessageLog.logMessage(
                f"Warning: Invalid Pre-Threshold Area 1 length '{pre_val_1}' for {log_name}, using 0.0.",
                plugin_tag,
                level=Qgis.Warning,
            )
        try:
            if pre_val_2 is not None:
                pre_area_len_2 = float(pre_val_2)
        except (ValueError, TypeError):
            QgsMessageLog.logMessage(
                f"Warning: Invalid Pre-Threshold Area 2 length '{pre_val_2}' for {log_name}, using 0.0.",
                plugin_tag,
                level=Qgis.Warning,
            )

        if not thr_point or not rec_thr_point:
            QgsMessageLog.logMessage(
                f"Skipping physical geom generation for {log_name}: Missing threshold points.",
                plugin_tag,
                level=Qgis.Warning,
            )
            return None

        rwy_params = self._get_runway_parameters(thr_point, rec_thr_point)
        if rwy_params is None:
            QgsMessageLog.logMessage(
                f"Skipping physical geom generation for {log_name}: Failed to get base runway parameters.",
                plugin_tag,
                level=Qgis.Warning,
            )
            return None

        physical_endpoints_result = self._get_physical_runway_endpoints(
            thr_point, rec_thr_point, disp_thr_1, disp_thr_2, rwy_params
        )
        if physical_endpoints_result is None:
            QgsMessageLog.logMessage(
                f"Skipping physical geom generation for {log_name}: Failed to calculate physical endpoints.",
                plugin_tag,
                level=Qgis.Warning,
            )
            return None
        phys_p_start, phys_p_end, physical_length = physical_endpoints_result

        generated_elements: List[Tuple[str, QgsGeometry, dict]] = []

        # --- 1. Runway Pavement (Landing Area: Between Thresholds) ---
        if runway_width is not None and runway_width > 0:
            try:
                half_width = runway_width / 2.0
                thr_l = thr_point.project(half_width, rwy_params["azimuth_perp_l"])
                thr_r = thr_point.project(half_width, rwy_params["azimuth_perp_r"])
                rec_l = rec_thr_point.project(half_width, rwy_params["azimuth_perp_l"])
                rec_r = rec_thr_point.project(half_width, rwy_params["azimuth_perp_r"])
                if all([thr_l, thr_r, rec_l, rec_r]):
                    landing_pavement_geom = self._create_polygon_from_corners(
                        [thr_l, thr_r, rec_r, rec_l], f"Landing Pavement {log_name}"
                    )
                    if landing_pavement_geom:
                        landing_length = rwy_params["length"]
                        physical_refs = ols_dimensions.get_physical_refs()
                        pavement_ref = physical_refs.get("pavement", "MOS 6.2.3")
                        # Use correct field names: 'rwy', 'desc', 'ref_mos'
                        attributes = {
                            "rwy": runway_name,
                            "desc": "Runway Pavement",
                            "wid_m": runway_width,
                            "len_m": round(landing_length, 3),
                            "ref_mos": pavement_ref,
                        }
                        generated_elements.append(
                            ("rwy", landing_pavement_geom, attributes)
                        )
                else:
                    QgsMessageLog.logMessage(
                        f"Warning: Failed to calculate landing pavement corners for {log_name}.",
                        plugin_tag,
                        level=Qgis.Warning,
                    )
            except Exception as e:
                QgsMessageLog.logMessage(
                    f"Warning: Error calculating Landing Pavement for {log_name}: {e}",
                    plugin_tag,
                    level=Qgis.Warning,
                )
        else:
            QgsMessageLog.logMessage(
                f"Info: Skipping Landing Pavement for {log_name}: Width ({runway_width}) not specified or invalid.",
                plugin_tag,
                level=Qgis.Info,
            )

        # --- 1b. Pre-Threshold Runway Areas (Displaced Areas) ---
        if runway_width is not None and runway_width > 0:
            pre_threshold_features = []
            half_width = runway_width / 2.0
            primary_desig = (
                runway_name.split("/")[0] if "/" in runway_name else "Primary"
            )
            reciprocal_desig = (
                runway_name.split("/")[1] if "/" in runway_name else "Reciprocal"
            )

            if disp_thr_1 > 1e-6:
                try:
                    start_point = phys_p_start
                    end_point = thr_point
                    p_start_l = start_point.project(
                        half_width, rwy_params["azimuth_perp_l"]
                    )
                    p_start_r = start_point.project(
                        half_width, rwy_params["azimuth_perp_r"]
                    )
                    p_end_l = end_point.project(
                        half_width, rwy_params["azimuth_perp_l"]
                    )
                    p_end_r = end_point.project(
                        half_width, rwy_params["azimuth_perp_r"]
                    )
                    if all([p_start_l, p_start_r, p_end_l, p_end_r]):
                        geom = self._create_polygon_from_corners(
                            [p_start_l, p_start_r, p_end_r, p_end_l],
                            f"Pre-Threshold {primary_desig}",
                        )
                        if geom:
                            physical_refs = ols_dimensions.get_physical_refs()
                            pavement_ref = physical_refs.get("pavement", "MOS 6.04")
                            # Use correct field names: 'rwy', 'desc', 'ref_mos', and add 'end_desig'
                            attributes = {
                                "rwy": runway_name,
                                "desc": f"Pre-Threshold Pavement ({primary_desig})",
                                "wid_m": runway_width,
                                "len_m": round(disp_thr_1, 3),
                                "ref_mos": pavement_ref,
                                "end_desig": primary_desig,
                            }
                            pre_threshold_features.append(
                                ("PreThresholdRunway", geom, attributes)
                            )
                    else:
                        QgsMessageLog.logMessage(
                            f"Warning: Failed calculate corners for Pre-Threshold Pavement {primary_desig}.",
                            plugin_tag,
                            level=Qgis.Warning,
                        )
                except Exception as e:
                    QgsMessageLog.logMessage(
                        f"Warning: Error generating Pre-Threshold Pavement {primary_desig}: {e}",
                        plugin_tag,
                        level=Qgis.Warning,
                    )

            if disp_thr_2 > 1e-6:
                try:
                    start_point = phys_p_end
                    end_point = rec_thr_point
                    r_start_l = start_point.project(
                        half_width, rwy_params["azimuth_perp_l"]
                    )
                    r_start_r = start_point.project(
                        half_width, rwy_params["azimuth_perp_r"]
                    )
                    r_end_l = end_point.project(
                        half_width, rwy_params["azimuth_perp_l"]
                    )
                    r_end_r = end_point.project(
                        half_width, rwy_params["azimuth_perp_r"]
                    )
                    if all([r_start_l, r_start_r, r_end_l, r_end_r]):
                        geom = self._create_polygon_from_corners(
                            [r_start_l, r_start_r, r_end_r, r_end_l],
                            f"Pre-Threshold {reciprocal_desig}",
                        )
                        if geom:
                            physical_refs = ols_dimensions.get_physical_refs()
                            pavement_ref = physical_refs.get("pavement", "MOS 6.04")
                            # Use correct field names: 'rwy', 'desc', 'ref_mos', and add 'end_desig'
                            attributes = {
                                "rwy": runway_name,
                                "desc": f"Pre-Threshold Pavement ({reciprocal_desig})",
                                "wid_m": runway_width,
                                "len_m": round(disp_thr_2, 3),
                                "ref_mos": pavement_ref,
                                "end_desig": reciprocal_desig,
                            }
                            pre_threshold_features.append(
                                ("PreThresholdRunway", geom, attributes)
                            )
                    else:
                        QgsMessageLog.logMessage(
                            f"Warning: Failed calculate corners for Pre-Threshold Pavement {reciprocal_desig}.",
                            plugin_tag,
                            level=Qgis.Warning,
                        )
                except Exception as e:
                    QgsMessageLog.logMessage(
                        f"Warning: Error generating Pre-Threshold Pavement {reciprocal_desig}: {e}",
                        plugin_tag,
                        level=Qgis.Warning,
                    )

            generated_elements.extend(pre_threshold_features)

        # --- 1c. Pre-Threshold Area (Blast Pad, etc.) ---
        if runway_width is not None and runway_width > 0:
            pre_threshold_area_features = []
            half_width = runway_width / 2.0
            primary_desig = (
                runway_name.split("/")[0] if "/" in runway_name else "Primary"
            )
            reciprocal_desig = (
                runway_name.split("/")[1] if "/" in runway_name else "Reciprocal"
            )

            if pre_area_len_1 > 1e-6:
                try:
                    area_start_point = phys_p_start
                    outward_azimuth = rwy_params["azimuth_r_p"]
                    geom = self._create_rectangle_from_start(
                        area_start_point,
                        outward_azimuth,
                        pre_area_len_1,
                        half_width,
                        f"Pre-Threshold Area {primary_desig}",
                    )
                    if geom:
                        # Use correct field names: 'rwy', 'desc', 'ref_mos', and add 'end_desig'
                        attributes = {
                            "rwy": runway_name,
                            "desc": f"Pre-Threshold Area ({primary_desig})",
                            "wid_m": runway_width,
                            "len_m": round(pre_area_len_1, 3),
                            "ref_mos": "MOS 8.16",
                            "end_desig": primary_desig,
                        }
                        pre_threshold_area_features.append(
                            ("PreThresholdArea", geom, attributes)
                        )
                except Exception as e:
                    QgsMessageLog.logMessage(
                        f"Warning: Error generating Pre-Threshold Area {primary_desig}: {e}",
                        plugin_tag,
                        level=Qgis.Warning,
                    )

            if pre_area_len_2 > 1e-6:
                try:
                    area_start_point = phys_p_end
                    outward_azimuth = rwy_params["azimuth_p_r"]
                    geom = self._create_rectangle_from_start(
                        area_start_point,
                        outward_azimuth,
                        pre_area_len_2,
                        half_width,
                        f"Pre-Threshold Area {reciprocal_desig}",
                    )
                    if geom:
                        # Use correct field names: 'rwy', 'desc', 'ref_mos', and add 'end_desig'
                        attributes = {
                            "rwy": runway_name,
                            "desc": f"Pre-Threshold Area ({reciprocal_desig})",
                            "wid_m": runway_width,
                            "len_m": round(pre_area_len_2, 3),
                            "ref_mos": "MOS 8.16",
                            "end_desig": reciprocal_desig,
                        }
                        pre_threshold_area_features.append(
                            ("PreThresholdArea", geom, attributes)
                        )
                except Exception as e:
                    QgsMessageLog.logMessage(
                        f"Warning: Error generating Pre-Threshold Area {reciprocal_desig}: {e}",
                        plugin_tag,
                        level=Qgis.Warning,
                    )

            generated_elements.extend(pre_threshold_area_features)

        # --- 1d. Displaced Threshold Markings ---
        displaced_marking_features = []
        primary_desig = runway_name.split("/")[0] if "/" in runway_name else "Primary"
        reciprocal_desig = (
            runway_name.split("/")[1] if "/" in runway_name else "Reciprocal"
        )
        marking_ref = "MOS 8.26"
        displaced_marking_end_clearance_m = 15.0
        pre_area_marking_end_clearance_m = 15.0

        def _create_marking_line(
            start_point, end_point, start_clearance_m=0.0, end_clearance_m=0.0
        ):
            line = QgsGeometry.fromPolylineXY([start_point, end_point])
            if not line or line.isEmpty():
                return None

            line_len = line.length()
            if line_len is None:
                return None

            usable_len = line_len - start_clearance_m - end_clearance_m
            if usable_len <= 1e-6:
                return None

            if start_clearance_m <= 0 and end_clearance_m <= 0:
                return line

            start_geom = line.interpolate(start_clearance_m)
            end_geom = line.interpolate(line_len - end_clearance_m)
            if (
                not start_geom
                or start_geom.isEmpty()
                or not end_geom
                or end_geom.isEmpty()
            ):
                return None

            return QgsGeometry.fromPolylineXY(
                [start_geom.asPoint(), end_geom.asPoint()]
            )

        if disp_thr_1 > 1e-6:
            try:
                line_geom = _create_marking_line(
                    phys_p_start,
                    thr_point,
                    end_clearance_m=displaced_marking_end_clearance_m,
                )
                if line_geom and not line_geom.isEmpty():
                    # Use correct field names: 'rwy', 'desc', 'ref_mos'
                    attributes = {
                        "rwy": runway_name,
                        "desc": "Displaced Threshold Marking",
                        "end_desig": primary_desig,
                        "len_m": round(disp_thr_1, 3),
                        "ref_mos": marking_ref,
                    }
                    displaced_marking_features.append(
                        ("DisplacedThresholdMarking", line_geom, attributes)
                    )
                else:
                    QgsMessageLog.logMessage(
                        f"Warning: Failed generate geometry for Primary Displaced Marking {log_name}.",
                        plugin_tag,
                        level=Qgis.Warning,
                    )
            except Exception as e:
                QgsMessageLog.logMessage(
                    f"Warning: Error generating Primary Displaced Marking {log_name}: {e}",
                    plugin_tag,
                    level=Qgis.Warning,
                )

        if disp_thr_2 > 1e-6:
            try:
                line_geom = _create_marking_line(
                    phys_p_end,
                    rec_thr_point,
                    end_clearance_m=displaced_marking_end_clearance_m,
                )
                if line_geom and not line_geom.isEmpty():
                    # Use correct field names: 'rwy', 'desc', 'ref_mos'
                    attributes = {
                        "rwy": runway_name,
                        "desc": "Displaced Threshold Marking",
                        "end_desig": reciprocal_desig,
                        "len_m": round(disp_thr_2, 3),
                        "ref_mos": marking_ref,
                    }
                    displaced_marking_features.append(
                        ("DisplacedThresholdMarking", line_geom, attributes)
                    )
                else:
                    QgsMessageLog.logMessage(
                        f"Warning: Failed generate geometry for Reciprocal Displaced Marking {log_name}.",
                        plugin_tag,
                        level=Qgis.Warning,
                    )
            except Exception as e:
                QgsMessageLog.logMessage(
                    f"Warning: Error generating Reciprocal Displaced Marking {log_name}: {e}",
                    plugin_tag,
                    level=Qgis.Warning,
                )

        generated_elements.extend(displaced_marking_features)

        # --- 1e. Pre-Threshold Area Markings ---
        pre_area_marking_features = []
        if pre_area_len_1 > 1e-6:
            try:
                outermost_p = phys_p_start.project(
                    pre_area_len_1, rwy_params["azimuth_r_p"]
                )
                if not outermost_p:
                    raise ValueError("Projection failed")
                line_geom = _create_marking_line(
                    phys_p_start,
                    outermost_p,
                    end_clearance_m=pre_area_marking_end_clearance_m,
                )
                if line_geom and not line_geom.isEmpty():
                    # Use correct field names: 'rwy', 'desc', 'ref_mos'
                    attributes = {
                        "rwy": runway_name,
                        "desc": "Pre-Threshold Area Marking",
                        "end_desig": primary_desig,
                        "len_m": round(pre_area_len_1, 3),
                        "ref_mos": "MOS 8.16(2)",
                    }
                    pre_area_marking_features.append(
                        ("PreThresholdAreaMarking", line_geom, attributes)
                    )
                else:
                    QgsMessageLog.logMessage(
                        f"Warning: Failed generate geometry for Primary Pre-Area Marking {log_name}.",
                        plugin_tag,
                        level=Qgis.Warning,
                    )
            except Exception as e:
                QgsMessageLog.logMessage(
                    f"Warning: Error generating Primary Pre-Area Marking {log_name}: {e}",
                    plugin_tag,
                    level=Qgis.Warning,
                )

        if pre_area_len_2 > 1e-6:
            try:
                outermost_r = phys_p_end.project(
                    pre_area_len_2, rwy_params["azimuth_p_r"]
                )
                if not outermost_r:
                    raise ValueError("Projection failed")
                line_geom = _create_marking_line(
                    phys_p_end,
                    outermost_r,
                    end_clearance_m=pre_area_marking_end_clearance_m,
                )
                if line_geom and not line_geom.isEmpty():
                    # Use correct field names: 'rwy', 'desc', 'ref_mos'
                    attributes = {
                        "rwy": runway_name,
                        "desc": "Pre-Threshold Area Marking",
                        "end_desig": reciprocal_desig,
                        "len_m": round(pre_area_len_2, 3),
                        "ref_mos": "MOS 8.16(2)",
                    }
                    pre_area_marking_features.append(
                        ("PreThresholdAreaMarking", line_geom, attributes)
                    )
                else:
                    QgsMessageLog.logMessage(
                        f"Warning: Failed generate geometry for Reciprocal Pre-Area Marking {log_name}.",
                        plugin_tag,
                        level=Qgis.Warning,
                    )
            except Exception as e:
                QgsMessageLog.logMessage(
                    f"Warning: Error generating Reciprocal Pre-Area Marking {log_name}: {e}",
                    plugin_tag,
                    level=Qgis.Warning,
                )

        generated_elements.extend(pre_area_marking_features)

        # --- 2. Runway Shoulders ---
        if (
            shoulder_width is not None
            and shoulder_width > 0
            and runway_width is not None
            and runway_width > 0
        ):
            try:
                half_width = runway_width / 2.0
                phys_start_l = phys_p_start.project(
                    half_width, rwy_params["azimuth_perp_l"]
                )
                phys_start_r = phys_p_start.project(
                    half_width, rwy_params["azimuth_perp_r"]
                )
                phys_end_l = phys_p_end.project(
                    half_width, rwy_params["azimuth_perp_l"]
                )
                phys_end_r = phys_p_end.project(
                    half_width, rwy_params["azimuth_perp_r"]
                )
                if not all([phys_start_l, phys_start_r, phys_end_l, phys_end_r]):
                    raise ValueError(
                        "Failed to calculate physical pavement corners for shoulders."
                    )

                outer_start_l = phys_start_l.project(
                    shoulder_width, rwy_params["azimuth_perp_l"]
                )
                outer_start_r = phys_start_r.project(
                    shoulder_width, rwy_params["azimuth_perp_r"]
                )
                outer_end_l = phys_end_l.project(
                    shoulder_width, rwy_params["azimuth_perp_l"]
                )
                outer_end_r = phys_end_r.project(
                    shoulder_width, rwy_params["azimuth_perp_r"]
                )

                physical_refs = ols_dimensions.get_physical_refs()
                shoulder_ref = physical_refs.get("shoulder", "MOS 6.2.4")
                # Use correct field names: 'rwy', 'desc', 'ref_mos'
                shoulder_attrs = {
                    "rwy": runway_name,
                    "desc": "Runway Shoulder",
                    "wid_m": shoulder_width,
                    "len_m": round(physical_length, 3),
                    "ref_mos": shoulder_ref,
                }

                if all([outer_start_l, outer_end_l]):
                    left_corners = [
                        phys_start_l,
                        outer_start_l,
                        outer_end_l,
                        phys_end_l,
                    ]
                    left_shoulder_poly = self._create_polygon_from_corners(
                        left_corners, f"Left Shoulder {log_name}"
                    )
                    if left_shoulder_poly:
                        generated_elements.append(
                            ("Shoulder", left_shoulder_poly, shoulder_attrs.copy())
                        )
                else:
                    QgsMessageLog.logMessage(
                        f"Warning: Failed calculate outer corners for left shoulder for {log_name}.",
                        plugin_tag,
                        level=Qgis.Warning,
                    )

                if all([outer_start_r, outer_end_r]):
                    right_corners = [
                        phys_start_r,
                        phys_end_r,
                        outer_end_r,
                        outer_start_r,
                    ]
                    right_shoulder_poly = self._create_polygon_from_corners(
                        right_corners, f"Right Shoulder {log_name}"
                    )
                    if right_shoulder_poly:
                        generated_elements.append(
                            ("Shoulder", right_shoulder_poly, shoulder_attrs.copy())
                        )
                else:
                    QgsMessageLog.logMessage(
                        f"Warning: Failed calculate outer corners for right shoulder for {log_name}.",
                        plugin_tag,
                        level=Qgis.Warning,
                    )

            except Exception as e_shld:
                QgsMessageLog.logMessage(
                    f"Warning: Error calculating Shoulders {log_name}: {e_shld}",
                    plugin_tag,
                    level=Qgis.Warning,
                )
        elif shoulder_width is not None and shoulder_width > 0:
            QgsMessageLog.logMessage(
                f"Info: Skipping Shoulders for {log_name}: Runway width missing.",
                plugin_tag,
                level=Qgis.Info,
            )

        # --- 3. Runway Strips ---
        strip_dims = None
        strip_end_center_p = None
        strip_end_center_r = None
        strip_length = None
        try:
            arc_num_val = runway_data.get("arc_num")
            arc_num = int(arc_num_val) if arc_num_val is not None else 0
            type1_abbr = ols_dimensions.get_runway_type_abbr(runway_data.get("type1"))
            runway_width_for_strip = runway_data.get("width")

            strip_dims = ols_dimensions.get_strip_params(
                arc_num, type1_abbr, runway_width_for_strip
            )
            runway_data["calculated_strip_dims"] = strip_dims

            if strip_dims is None:
                QgsMessageLog.logMessage(
                    f"Warning (Physical Geom): Failed to calculate strip parameters for {log_name} "
                    f"(ARC={arc_num}, Type={type1_abbr}, Width={runway_width_for_strip}). "
                    "Dependent elements (Strips, RESA, IHS Base) may fail.",
                    plugin_tag,
                    level=Qgis.Warning,
                )

            if strip_dims and all(
                strip_dims.get(dim) is not None
                for dim in ["overall_width", "graded_width", "extension_length"]
            ):
                extension = strip_dims["extension_length"]
                graded_width = strip_dims["graded_width"]
                overall_width = strip_dims["overall_width"]
                graded_half_width = graded_width / 2.0
                overall_half_width = overall_width / 2.0

                strip_end_center_p = phys_p_start.project(
                    extension, rwy_params["azimuth_r_p"]
                )
                strip_end_center_r = phys_p_end.project(
                    extension, rwy_params["azimuth_p_r"]
                )

                if strip_end_center_p and strip_end_center_r:
                    strip_length = strip_end_center_p.distance(strip_end_center_r)
                    if strip_length is None:
                        raise ValueError("Failed to calculate strip length.")

                    graded_strip_geom = self._create_runway_aligned_rectangle(
                        strip_end_center_p,
                        strip_end_center_r,
                        0.0,
                        graded_half_width,
                        f"Graded Strip {log_name}",
                    )
                    if graded_strip_geom:
                        graded_ref = f"{strip_dims.get('mos_graded_width_ref','')}; {strip_dims.get('mos_extension_length_ref','')}"
                        # Use correct field names: 'rwy', 'desc', 'ref_mos'
                        graded_attrs = {
                            "rwy": runway_name,
                            "desc": "Graded Strip",
                            "wid_m": graded_width,
                            "len_m": round(strip_length, 3),
                            "ref_mos": graded_ref,
                        }
                        generated_elements.append(
                            ("GradedStrip", graded_strip_geom, graded_attrs)
                        )

                    overall_strip_geom = self._create_runway_aligned_rectangle(
                        strip_end_center_p,
                        strip_end_center_r,
                        0.0,
                        overall_half_width,
                        f"Overall Strip {log_name}",
                    )
                    if overall_strip_geom:
                        overall_ref = f"{strip_dims.get('mos_overall_width_ref','')}; {strip_dims.get('mos_extension_length_ref','')}"
                        # Use correct field names: 'rwy', 'desc', 'ref_mos'
                        overall_attrs = {
                            "rwy": runway_name,
                            "desc": "Overall Strip",
                            "wid_m": overall_width,
                            "len_m": round(strip_length, 3),
                            "ref_mos": overall_ref,
                        }
                        generated_elements.append(
                            ("OverallStrip", overall_strip_geom, overall_attrs)
                        )
                else:
                    QgsMessageLog.logMessage(
                        f"Warning: Skipping Strips for {log_name}: Invalid strip end points calculation.",
                        plugin_tag,
                        level=Qgis.Warning,
                    )
                    strip_dims = None
            else:
                QgsMessageLog.logMessage(
                    f"Info: Skipping Strips for {log_name}: Strip dimensions calculation failed or incomplete.",
                    plugin_tag,
                    level=Qgis.Info,
                )
                strip_dims = None
        except Exception as e:
            QgsMessageLog.logMessage(
                f"Warning: Error calculating Strips for {log_name}: {e}",
                plugin_tag,
                level=Qgis.Warning,
            )
            strip_dims = None

        # --- 4. RESAs ---
        try:
            type1_abbr = ols_dimensions.get_runway_type_abbr(runway_data.get("type1"))
            type2_abbr = ols_dimensions.get_runway_type_abbr(runway_data.get("type2"))
            resa_dims = ols_dimensions.get_resa_params(
                int(runway_data.get("arc_num", 0)), type1_abbr, type2_abbr
            )

            if (
                resa_dims
                and resa_dims.get("required")
                and strip_end_center_p
                and strip_end_center_r
                and runway_width is not None
                and runway_width > 0
            ):
                resa_length = resa_dims.get("length")
                resa_width_val = 2.0 * runway_width
                resa_half_width = resa_width_val / 2.0

                if resa_length is None or resa_length <= 0:
                    raise ValueError("Required RESA length missing or invalid.")

                primary_desig = (
                    runway_name.split("/")[0] if "/" in runway_name else "Primary"
                )
                reciprocal_desig = (
                    runway_name.split("/")[1] if "/" in runway_name else "Reciprocal"
                )
                resa_ref = f"{resa_dims.get('mos_applicability_ref','')}; {resa_dims.get('mos_width_ref','')}; {resa_dims.get('mos_length_ref','')}"
                # Use correct field names: 'rwy', 'desc', 'ref_mos'
                resa_base_attrs = {
                    "rwy": runway_name,
                    "desc": "RESA",
                    "len_m": resa_length,
                    "wid_m": resa_width_val,
                    "ref_mos": resa_ref,
                }

                try:
                    resa1_geom = self._create_rectangle_from_start(
                        strip_end_center_p,
                        rwy_params["azimuth_r_p"],
                        resa_length,
                        resa_half_width,
                        f"RESA {primary_desig}",
                    )
                    if resa1_geom:
                        resa1_attrs = resa_base_attrs.copy()
                        resa1_attrs["end_desig"] = primary_desig
                        generated_elements.append(("RESA", resa1_geom, resa1_attrs))
                except Exception as e_resa1:
                    QgsMessageLog.logMessage(
                        f"Warning: Error RESA {primary_desig} for {log_name}: {e_resa1}",
                        plugin_tag,
                        level=Qgis.Warning,
                    )

                try:
                    resa2_geom = self._create_rectangle_from_start(
                        strip_end_center_r,
                        rwy_params["azimuth_p_r"],
                        resa_length,
                        resa_half_width,
                        f"RESA {reciprocal_desig}",
                    )
                    if resa2_geom:
                        resa2_attrs = resa_base_attrs.copy()
                        resa2_attrs["end_desig"] = reciprocal_desig
                        generated_elements.append(("RESA", resa2_geom, resa2_attrs))
                except Exception as e_resa2:
                    QgsMessageLog.logMessage(
                        f"Warning: Error RESA {reciprocal_desig} for {log_name}: {e_resa2}",
                        plugin_tag,
                        level=Qgis.Warning,
                    )

            elif resa_dims and resa_dims.get("required"):
                QgsMessageLog.logMessage(
                    f"Info: Skipping RESAs for {log_name}: Required but prerequisite data (strip ends/runway width) incomplete.",
                    plugin_tag,
                    level=Qgis.Info,
                )

        except Exception as e_resa_section:
            QgsMessageLog.logMessage(
                f"Warning: Error processing RESA Section for {log_name}: {e_resa_section}",
                plugin_tag,
                level=Qgis.Warning,
            )

        # --- 5. Stopways ---
        # Placeholder: Add logic here if needed.
        # If Stopways are implemented, ensure attribute keys match 'stopway_resa_fields':
        # e.g., attributes = {'rwy': runway_name, 'desc': 'Stopway', ..., 'end_desig': ..., 'ref_mos': ...}

        QgsMessageLog.logMessage(
            f"Finished physical geometry processing for {log_name}. Generated {len(generated_elements)} element features.",
            plugin_tag,
            level=Qgis.Success,
        )

        return generated_elements if generated_elements else None
