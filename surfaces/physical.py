# -*- coding: utf-8 -*-
"""Physical runway geometry generation."""

import os
import re
import math
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
    QgsPointXY,
    QgsProject,
    QgsVectorLayer,
    QgsWkbTypes,
)

from ..reports.runway_summary import summarize_generated_elements

PLUGIN_TAG = "SafeguardingBuilder"


class PhysicalGeometryMixin:
    def _policy_ref(self, values: Optional[dict], generic_key: str, *fallback_keys: str) -> str:
        """Return a ruleset-neutral policy reference with legacy-key fallbacks."""
        if not values:
            return ""
        for key in (generic_key, *fallback_keys):
            value = values.get(key)
            if value:
                return str(value)
        return ""

    def _join_policy_refs(self, *refs: str) -> str:
        parts = [str(ref).strip() for ref in refs if str(ref or "").strip()]
        return "; ".join(parts)

    def _process_physical_and_protection_layers(
        self,
        main_group: QgsLayerTreeGroup,
        icao_code: str,
        processed_runway_data_list: List[dict],
        any_runway_base_data_ok: bool,
        layer_groups: Optional[Dict[str, Optional[QgsLayerTreeGroup]]] = None,
    ) -> Tuple[Optional[QgsLayerTreeGroup], bool]:
        plugin_tag = PLUGIN_TAG
        specialised_safeguarding_group = None
        physical_geom_group = None
        detailed_marking_group = None
        protection_area_group = None
        physical_layer_specs = {}
        physical_features: Dict[str, List[QgsFeature]] = {}
        any_physical_or_protection_ok = False

        if processed_runway_data_list and any_runway_base_data_ok:
            layer_groups = layer_groups or {}
            detailed_marking_group = layer_groups.get("markings")
            if detailed_marking_group is None:
                detailed_marking_group = main_group.addGroup(self.tr("Markings"))
            self._stage_layer_tree_node(detailed_marking_group)
            physical_geom_group = layer_groups.get("physical_geometry")
            if physical_geom_group is None:
                physical_geom_group = main_group.addGroup(self.tr("Physical Geometry"))
            self._stage_layer_tree_node(physical_geom_group)
            protection_area_group = layer_groups.get("runway_protection_areas")
            if protection_area_group is None:
                protection_area_group = main_group.addGroup(self.tr("Runway Protection Areas"))
            self._stage_layer_tree_node(protection_area_group)
            specialised_safeguarding_group = layer_groups.get("specialised_safeguarding")
            if specialised_safeguarding_group is None:
                specialised_safeguarding_group = main_group.findGroup(self.tr("Specialised Runway Safeguarding"))
            if specialised_safeguarding_group is None:
                specialised_safeguarding_group = main_group.addGroup(self.tr("Specialised Runway Safeguarding"))
            self._stage_layer_tree_node(specialised_safeguarding_group)

            if (
                physical_geom_group is not None
                and protection_area_group is not None
                and specialised_safeguarding_group is not None
            ):
                common_fields = [
                    QgsField("rwy", QVariant.String, self.tr("Runway Name"), 30),
                    QgsField("desc", QVariant.String, self.tr("Element Type"), 50),
                    QgsField(
                        "surf_cat",
                        QVariant.String,
                        self.tr("Surface Category"),
                        20,
                    ),
                    QgsField(
                        "surf_mat",
                        QVariant.String,
                        self.tr("Surface Material"),
                        30,
                    ),
                    QgsField("len_m", QVariant.Double, self.tr("len_m"), 12, 3),
                    QgsField("wid_m", QVariant.Double, self.tr("wid_m"), 12, 3),
                    QgsField("ref_mos", QVariant.String, self.tr("MOS Reference"), 250),
                ]
                stopway_resa_fields = common_fields + [
                    QgsField("end_desig", QVariant.String, self.tr("End Designator"), 10)
                ]
                pre_threshold_fields = common_fields + [
                    QgsField("end_desig", QVariant.String, self.tr("End Designator"), 10)
                ]
                declared_distance_fields = [
                    QgsField("rwy", QVariant.String, self.tr("Runway Name"), 30),
                    QgsField("end_desig", QVariant.String, self.tr("End Designator"), 10),
                    QgsField("direction", QVariant.String, self.tr("Direction"), 12),
                    QgsField(
                        "bearing_deg",
                        QVariant.Double,
                        self.tr("Runway Bearing (deg)"),
                        10,
                        3,
                    ),
                    QgsField(
                        "phys_len_m",
                        QVariant.Double,
                        self.tr("Physical Length (m)"),
                        12,
                        3,
                    ),
                    QgsField(
                        "thr_len_m",
                        QVariant.Double,
                        self.tr("Threshold Length (m)"),
                        12,
                        3,
                    ),
                    QgsField(
                        "disp_thr_m",
                        QVariant.Double,
                        self.tr("Displaced Threshold (m)"),
                        12,
                        3,
                    ),
                    QgsField(
                        "clearway_m",
                        QVariant.Double,
                        self.tr("Clearway (m)"),
                        12,
                        3,
                    ),
                    QgsField(
                        "stopway_m",
                        QVariant.Double,
                        self.tr("Stopway (m)"),
                        12,
                        3,
                    ),
                    QgsField(
                        "takeoff_ok",
                        QVariant.Bool,
                        self.tr("Takeoff Available"),
                    ),
                    QgsField(
                        "landing_ok",
                        QVariant.Bool,
                        self.tr("Landing Available"),
                    ),
                    QgsField("tora_m", QVariant.Double, self.tr("TORA (m)"), 12, 3),
                    QgsField("toda_m", QVariant.Double, self.tr("TODA (m)"), 12, 3),
                    QgsField("asda_m", QVariant.Double, self.tr("ASDA (m)"), 12, 3),
                    QgsField("lda_m", QVariant.Double, self.tr("LDA (m)"), 12, 3),
                    QgsField(
                        "calc_src",
                        QVariant.String,
                        self.tr("Calculation Source"),
                        40,
                    ),
                    QgsField("notes", QVariant.String, self.tr("Notes"), 250),
                ]
                detailed_marking_fields = [
                    QgsField("rwy", QVariant.String, self.tr("Runway Name"), 30),
                    QgsField("end_desig", QVariant.String, self.tr("End Designator"), 10),
                    QgsField("mark_type", QVariant.String, self.tr("Marking"), 40),
                    QgsField("sub_type", QVariant.String, self.tr("Subtype"), 40),
                    QgsField("side", QVariant.String, self.tr("Side"), 10),
                    QgsField("stripe_no", QVariant.Int, self.tr("Stripe No.")),
                    QgsField("len_m", QVariant.Double, self.tr("len_m"), 12, 3),
                    QgsField("wid_m", QVariant.Double, self.tr("wid_m"), 12, 3),
                    QgsField("offset_m", QVariant.Double, self.tr("offset_m"), 12, 3),
                    QgsField("spacing_m", QVariant.Double, self.tr("spacing_m"), 12, 3),
                    QgsField("lda_m", QVariant.Double, self.tr("lda_m"), 12, 3),
                    QgsField("mandatory", QVariant.Bool, self.tr("Mandatory")),
                    QgsField("ref_mos", QVariant.String, self.tr("MOS Reference"), 250),
                    QgsField("notes", QVariant.String, self.tr("Notes"), 250),
                ]
                designation_fields = [
                    QgsField("rwy", QVariant.String, self.tr("Runway Name"), 30),
                    QgsField("end_desig", QVariant.String, self.tr("End Designator"), 10),
                    QgsField("text", QVariant.String, self.tr("Designation"), 10),
                    QgsField("bearing", QVariant.Double, self.tr("Bearing"), 10, 3),
                    QgsField(
                        "label_rot",
                        QVariant.Double,
                        self.tr("Label Rotation"),
                        10,
                        3,
                    ),
                    QgsField("glyph", QVariant.String, self.tr("Glyph"), 2),
                    QgsField("glyph_no", QVariant.Int, self.tr("Glyph No.")),
                    QgsField(
                        "glyph_size",
                        QVariant.Double,
                        self.tr("Glyph Size (m)"),
                        12,
                        3,
                    ),
                    QgsField(
                        "glyph_w_m",
                        QVariant.Double,
                        self.tr("Glyph Width (m)"),
                        12,
                        3,
                    ),
                    QgsField(
                        "angle_deg",
                        QVariant.Double,
                        self.tr("Angle (deg)"),
                        10,
                        3,
                    ),
                    QgsField("offset_m", QVariant.Double, self.tr("offset_m"), 12, 3),
                    QgsField("height_m", QVariant.Double, self.tr("height_m"), 12, 3),
                    QgsField("mandatory", QVariant.Bool, self.tr("Mandatory")),
                    QgsField("ref_mos", QVariant.String, self.tr("MOS Reference"), 250),
                    QgsField("notes", QVariant.String, self.tr("Notes"), 250),
                ]
                marking_qa_fields = [
                    QgsField("rwy", QVariant.String, self.tr("Runway Name"), 30),
                    QgsField("end_desig", QVariant.String, self.tr("End Designator"), 10),
                    QgsField(
                        "mandatory",
                        QVariant.String,
                        self.tr("Mandatory Markings Generated"),
                        1000,
                    ),
                    QgsField(
                        "optional",
                        QVariant.String,
                        self.tr("Optional/Recommended Markings Generated"),
                        1000,
                    ),
                    QgsField(
                        "assumptions",
                        QVariant.String,
                        self.tr("Assumptions Used"),
                        1000,
                    ),
                    QgsField(
                        "skipped",
                        QVariant.String,
                        self.tr("Skipped Markings / Reasons"),
                        1000,
                    ),
                    QgsField("ref_mos", QVariant.String, self.tr("MOS Reference"), 250),
                    QgsField("notes", QVariant.String, self.tr("Notes"), 250),
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
                    "Shoulder": {
                        "name": self.tr("Runway Shoulders"),
                        "fields": common_fields,
                        "group": physical_geom_group,
                    },
                    "DeclaredDistance": {
                        "name": self.tr("Declared Distances"),
                        "fields": declared_distance_fields,
                        "geom_type": "Point",
                        "group": physical_geom_group,
                    },
                    "DetailedThresholdMarking": {
                        "name": self.tr("Threshold Markings"),
                        "fields": detailed_marking_fields,
                        "group": detailed_marking_group,
                    },
                    "DetailedDesignationMarking": {
                        "name": self.tr("Runway Designation Markings"),
                        "fields": designation_fields,
                        "geom_type": "Point",
                        "group": detailed_marking_group,
                    },
                    "DetailedCentrelineMarking": {
                        "name": self.tr("Runway Centreline Markings"),
                        "fields": detailed_marking_fields,
                        "group": detailed_marking_group,
                    },
                    "DetailedAimingPointMarking": {
                        "name": self.tr("Aiming Point Markings"),
                        "fields": detailed_marking_fields,
                        "group": detailed_marking_group,
                    },
                    "DetailedTouchdownZoneMarking": {
                        "name": self.tr("Touchdown Zone Markings"),
                        "fields": detailed_marking_fields,
                        "group": detailed_marking_group,
                    },
                    "DetailedDisplacedThresholdMarking": {
                        "name": self.tr("Displaced Threshold Markings"),
                        "fields": detailed_marking_fields,
                        "group": detailed_marking_group,
                    },
                    "DetailedPreThresholdAreaMarking": {
                        "name": self.tr("Pre-Threshold Area Markings"),
                        "fields": detailed_marking_fields,
                        "group": detailed_marking_group,
                    },
                    "DetailedRunwayHoldingPositionMarking": {
                        "name": self.tr("Runway Holding Position Markings"),
                        "fields": detailed_marking_fields,
                        "group": detailed_marking_group,
                    },
                    "DetailedSideStripeMarking": {
                        "name": self.tr("Runway Side-Stripe Markings"),
                        "fields": detailed_marking_fields,
                        "group": detailed_marking_group,
                    },
                    "DetailedMarkingQA": {
                        "name": self.tr("Runway Marking QA"),
                        "fields": marking_qa_fields,
                        "geom_type": "Point",
                        "group": detailed_marking_group,
                    },
                    "Stopway": {
                        "name": self.tr("Stopways"),
                        "fields": stopway_resa_fields,
                        "group": protection_area_group,
                    },
                    "Clearway": {
                        "name": self.tr("Clearways"),
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
                    "Shoulder": "Runway Shoulders",
                    "DeclaredDistance": "Default Point",
                    "DetailedThresholdMarking": "Runway Marking White",
                    "DetailedDesignationMarking": "Runway Designation Text",
                    "DetailedCentrelineMarking": "Runway Marking White",
                    "DetailedAimingPointMarking": "Runway Marking White",
                    "DetailedTouchdownZoneMarking": "Runway Marking White",
                    "DetailedDisplacedThresholdMarking": "Runway Marking White",
                    "DetailedPreThresholdAreaMarking": "Runway Marking Yellow",
                    "DetailedRunwayHoldingPositionMarking": "Runway Marking Yellow",
                    "DetailedSideStripeMarking": "Runway Marking White",
                    "DetailedMarkingQA": "Default Point",
                    "Stopway": "Stopways",
                    "Clearway": "Clearways",
                    "GradedStrip": "Runway Graded Strips",
                    "FlyoverStrip": "Runway Strip Flyover Area",
                    "OverallStrip": "Runway Overall Strips",
                    "RESA": "Runway End Safety Areas (RESA)",
                }
                layer_creation_order = [
                    "rwy",
                    "PreThresholdRunway",
                    "PreThresholdArea",
                    "Shoulder",
                    "DeclaredDistance",
                    "DetailedThresholdMarking",
                    "DetailedDesignationMarking",
                    "DetailedCentrelineMarking",
                    "DetailedAimingPointMarking",
                    "DetailedTouchdownZoneMarking",
                    "DetailedDisplacedThresholdMarking",
                    "DetailedPreThresholdAreaMarking",
                    "DetailedRunwayHoldingPositionMarking",
                    "DetailedSideStripeMarking",
                    "DetailedMarkingQA",
                    "Stopway",
                    "Clearway",
                    "GradedStrip",
                    "FlyoverStrip",
                    "OverallStrip",
                    "RESA",
                ]

                for element_type in layer_creation_order:
                    definition = layer_definitions[element_type]
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
                    if geom_type_str not in {"LineString", "Point", "Polygon"}:
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
                        "style_key": style_key_map.get(element_type, "Default Polygon"),
                    }
                    physical_features[element_type] = []

                QgsMessageLog.logMessage(
                    "Populating physical geometry & protection area layers...",
                    plugin_tag,
                    level=Qgis.Info,
                )
                runway_marking_contexts = {}
                for rwy_data in processed_runway_data_list:
                    runway_name_log = rwy_data.get("short_name", f"RWY_{rwy_data.get('original_index', '?')}")
                    rwy_data["_all_runways"] = processed_runway_data_list
                    try:
                        declared_spec = physical_layer_specs.get("DeclaredDistance")
                        if declared_spec is not None:
                            for declared_record in rwy_data.get("declared_distances", []):
                                declared_point = declared_record.get("point")
                                if declared_point is None:
                                    continue

                                declared_feature = QgsFeature(declared_spec["fields"])
                                declared_feature.setGeometry(QgsGeometry.fromPointXY(declared_point))
                                declared_attrs = {
                                    "rwy": declared_record.get("rwy"),
                                    "end_desig": declared_record.get("end_desig"),
                                    "direction": declared_record.get("direction"),
                                    "bearing_deg": declared_record.get("bearing_deg"),
                                    "phys_len_m": declared_record.get("physical_len_m"),
                                    "thr_len_m": declared_record.get("threshold_len_m"),
                                    "disp_thr_m": declared_record.get("disp_thr_m"),
                                    "clearway_m": declared_record.get("clearway_m"),
                                    "stopway_m": declared_record.get("stopway_m"),
                                    "takeoff_ok": declared_record.get("takeoff_available"),
                                    "landing_ok": declared_record.get("landing_available"),
                                    "tora_m": declared_record.get("tora_m"),
                                    "toda_m": declared_record.get("toda_m"),
                                    "asda_m": declared_record.get("asda_m"),
                                    "lda_m": declared_record.get("lda_m"),
                                    "calc_src": declared_record.get("calc_src", "calculated"),
                                    "notes": declared_record.get("notes", ""),
                                }
                                for field_name, value in declared_attrs.items():
                                    idx = declared_feature.fieldNameIndex(field_name)
                                    if idx != -1:
                                        declared_feature.setAttribute(idx, value)
                                physical_features["DeclaredDistance"].append(declared_feature)
                                any_physical_or_protection_ok = True

                        generated_elements_list = self.generate_physical_geometry(rwy_data)
                        if generated_elements_list is None:
                            continue

                        generated_summary = summarize_generated_elements(generated_elements_list)
                        rwy_data["generated_feature_counts"] = {
                            **rwy_data.get("generated_feature_counts", {}),
                            **generated_summary.get("counts", {}),
                        }
                        existing_refs = list(rwy_data.get("generated_mos_refs", []))
                        existing_refs.extend(generated_summary.get("mos_refs", []))
                        rwy_data["generated_mos_refs"] = sorted(set(existing_refs))

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
                            if geometry is None or geometry.isEmpty() or not geometry.isGeosValid():
                                continue

                            if element_type == "rwy":
                                try:
                                    runway_marking_contexts[attributes.get("rwy", runway_name_log)] = {
                                        "geom": QgsGeometry(geometry),
                                        "rank": self._runway_precedence_rank(
                                            rwy_data,
                                            float(attributes.get("len_m") or 0.0),
                                        ),
                                    }
                                except Exception as ctx_error:
                                    QgsMessageLog.logMessage(
                                        "Warning: Could not prepare runway "
                                        f"intersection context for {runway_name_log}: {ctx_error}",
                                        plugin_tag,
                                        level=Qgis.Warning,
                                    )

                            feature = QgsFeature(target_spec["fields"])
                            feature.setGeometry(geometry)
                            for field_name, value in attributes.items():
                                idx = feature.fieldNameIndex(field_name)
                                if idx != -1:
                                    feature.setAttribute(idx, value)

                            physical_features[element_type].append(feature)
                            any_physical_or_protection_ok = True

                        detailed_markings = self.generate_detailed_runway_markings(rwy_data)
                        for element_type, geometry, attributes in detailed_markings:
                            target_spec = physical_layer_specs.get(element_type)
                            if target_spec is None:
                                continue
                            if geometry is None or geometry.isEmpty():
                                continue
                            if not geometry.isGeosValid():
                                geometry = geometry.makeValid()
                            if geometry is None or geometry.isEmpty() or not geometry.isGeosValid():
                                continue

                            feature = QgsFeature(target_spec["fields"])
                            feature.setGeometry(geometry)
                            for field_name, value in attributes.items():
                                idx = feature.fieldNameIndex(field_name)
                                if idx != -1:
                                    feature.setAttribute(idx, value)

                            physical_features[element_type].append(feature)
                            any_physical_or_protection_ok = True

                    except Exception as e_phys:
                        QgsMessageLog.logMessage(
                            f"Critical Error populating layers for {runway_name_log}: {e_phys}\n{traceback.format_exc()}",
                            plugin_tag,
                            level=Qgis.Critical,
                        )
                        continue

                clipped_marking_count = self._apply_intersecting_runway_clipping(
                    physical_features,
                    runway_marking_contexts,
                    (
                        "DetailedThresholdMarking",
                        "DetailedAimingPointMarking",
                        "DetailedTouchdownZoneMarking",
                        "DetailedDisplacedThresholdMarking",
                        "DetailedPreThresholdAreaMarking",
                    ),
                )
                clipped_side_stripe_count = self._apply_side_stripe_crossing_runway_clipping(
                    physical_features,
                    runway_marking_contexts,
                )
                if clipped_marking_count:
                    QgsMessageLog.logMessage(
                        "Applied MOS 8.15 runway-intersection clipping to "
                        f"{clipped_marking_count} detailed runway marking feature(s).",
                        plugin_tag,
                        level=Qgis.Info,
                    )
                if clipped_side_stripe_count:
                    QgsMessageLog.logMessage(
                        "Applied MOS 8.21 intersecting-runway clipping to "
                        f"{clipped_side_stripe_count} side-stripe marking feature(s).",
                        plugin_tag,
                        level=Qgis.Info,
                    )

                QgsMessageLog.logMessage(
                    "Finalizing and saving physical geometry & protection area layers...",
                    plugin_tag,
                    level=Qgis.Info,
                )
                any_layer_successfully_processed_in_this_block = False

                for element_type in layer_creation_order:
                    spec = physical_layer_specs.get(element_type)
                    if spec is None:
                        continue
                    features_to_write = physical_features.get(element_type, [])
                    if element_type == "DetailedSideStripeMarking":
                        features_to_write[:] = self._normalise_side_stripe_features_for_layer(features_to_write)
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
                            if element_type == "DetailedDesignationMarking":
                                self._style_runway_designation_layer(final_layer)
                            any_physical_or_protection_ok = True
                            any_layer_successfully_processed_in_this_block = True
                        features_to_write.clear()

                if not any_layer_successfully_processed_in_this_block and physical_layer_specs:
                    QgsMessageLog.logMessage(
                        "Warning: No physical geometry or protection area layers were successfully processed/saved in this block.",
                        plugin_tag,
                        Qgis.Warning,
                    )

                if physical_geom_group is not None:
                    project_root = QgsProject.instance().layerTreeRoot()
                    centreline_insert_index = 0
                    for rwy_data in processed_runway_data_list:
                        cl_layer = rwy_data.get("centreline_layer")
                        if cl_layer is not None:
                            cl_node = project_root.findLayer(cl_layer.id())
                            if cl_node is not None:
                                cloned_node = cl_node.clone()
                                self._stage_layer_tree_node(cloned_node)
                                physical_geom_group.insertChildNode(centreline_insert_index, cloned_node)
                                centreline_insert_index += 1
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

    def _runway_precedence_rank(self, runway_data: dict, runway_length: float) -> Tuple[int, int, float]:
        """Rank runways for MOS 8.15 marking precedence."""
        try:
            arc_number = int(float(runway_data.get("arc_num") or 0))
        except (TypeError, ValueError):
            arc_number = 0

        arc_letter = str(runway_data.get("arc_let") or "").strip().upper()
        letter_rank = "ABCDEF".find(arc_letter[:1]) + 1 if arc_letter else 0
        return arc_number, letter_rank, float(runway_length or 0.0)

    def _append_feature_note(self, feature: QgsFeature, note: str) -> None:
        notes_idx = feature.fieldNameIndex("notes")
        if notes_idx == -1:
            return
        existing_note = feature.attribute(notes_idx) or ""
        if existing_note:
            feature.setAttribute(notes_idx, f"{existing_note} {note}")
        else:
            feature.setAttribute(notes_idx, note)

    def _apply_intersecting_runway_clipping(
        self,
        physical_features: Dict[str, List[QgsFeature]],
        runway_contexts: dict,
        detailed_polygon_keys: Tuple[str, ...],
    ) -> int:
        """Interrupt lower-precedence detailed markings at runway intersections."""
        if len(runway_contexts) < 2:
            return 0

        clipped_count = 0
        for element_type in detailed_polygon_keys:
            updated_features = []
            for feature in physical_features.get(element_type, []):
                runway_name = feature.attribute("rwy")
                current_context = runway_contexts.get(runway_name)
                if current_context is None:
                    updated_features.append(feature)
                    continue

                geom = feature.geometry()
                if geom is None or geom.isEmpty():
                    continue

                current_rank = current_context.get("rank", (0, 0, 0.0))
                interrupted_by = []
                for other_name, other_context in runway_contexts.items():
                    if other_name == runway_name:
                        continue
                    other_rank = other_context.get("rank", (0, 0, 0.0))
                    if current_rank >= other_rank:
                        continue

                    other_geom = other_context.get("geom")
                    if other_geom is None or other_geom.isEmpty():
                        continue
                    if not geom.intersects(other_geom):
                        continue

                    clipped_geom = geom.difference(other_geom)
                    if clipped_geom is None:
                        continue
                    if not clipped_geom.isEmpty() and not clipped_geom.isGeosValid():
                        clipped_geom = clipped_geom.makeValid()
                    geom = clipped_geom
                    interrupted_by.append(other_name)

                    if geom is None or geom.isEmpty():
                        break

                if not interrupted_by:
                    updated_features.append(feature)
                    continue
                if geom is None or geom.isEmpty():
                    feature.setGeometry(QgsGeometry())
                else:
                    feature.setGeometry(geom)
                self._append_feature_note(
                    feature,
                    "Interrupted at intersecting runway pavement under MOS 8.15 " f"by {', '.join(interrupted_by)}.",
                )
                clipped_count += 1
                if geom is None or geom.isEmpty():
                    continue
                updated_features.append(feature)

            physical_features[element_type] = updated_features

        return clipped_count

    def _polygonal_layer_geometries(self, geom: Optional[QgsGeometry], description: str) -> List[QgsGeometry]:
        """Return single-part polygon geometries suitable for polygon layer writes."""
        if geom is None or geom.isEmpty():
            return []

        try:
            if not geom.isGeosValid():
                geom = geom.makeValid()
            if geom is None or geom.isEmpty():
                return []

            polygon_parts = []

            def collect_polygon_parts(source_geom: QgsGeometry) -> None:
                if source_geom is None or source_geom.isEmpty():
                    return
                if source_geom.type() == QgsWkbTypes.PolygonGeometry:
                    if source_geom.isMultipart():
                        polygon_parts.extend(part for part in source_geom.asMultiPolygon() if part and part[0])
                    else:
                        polygon = source_geom.asPolygon()
                        if polygon and polygon[0]:
                            polygon_parts.append(polygon)
                    return
                if hasattr(source_geom, "asGeometryCollection"):
                    for part_geom in source_geom.asGeometryCollection():
                        collect_polygon_parts(part_geom)

            collect_polygon_parts(geom)
            if not polygon_parts:
                return []

            polygonal_geometries = []
            for polygon_part in polygon_parts:
                polygonal_geom = QgsGeometry.fromPolygonXY(polygon_part)
                if polygonal_geom is None or polygonal_geom.isEmpty():
                    continue
                if not polygonal_geom.isGeosValid():
                    polygonal_geom = polygonal_geom.makeValid()
                if (
                    polygonal_geom is None
                    or polygonal_geom.isEmpty()
                    or polygonal_geom.type() != QgsWkbTypes.PolygonGeometry
                    or polygonal_geom.isMultipart()
                    or not polygonal_geom.isGeosValid()
                ):
                    continue
                polygonal_geometries.append(polygonal_geom)
            return polygonal_geometries
        except Exception as poly_error:
            QgsMessageLog.logMessage(
                f"Warning: Could not normalise polygon geometry for {description}: {poly_error}",
                PLUGIN_TAG,
                level=Qgis.Warning,
            )
            return []

    def _clone_feature_with_geometry(self, source_feature: QgsFeature, geometry: QgsGeometry) -> QgsFeature:
        """Clone attributes onto a fresh feature to avoid reusing feature ids."""
        cloned_feature = QgsFeature(source_feature.fields())
        cloned_feature.setAttributes(source_feature.attributes())
        cloned_feature.setGeometry(geometry)
        return cloned_feature

    def _normalise_side_stripe_features_for_layer(self, features: List[QgsFeature]) -> List[QgsFeature]:
        """Prepare side-stripe features as fresh single-part polygons."""
        normalised_features: List[QgsFeature] = []
        for feature in features:
            runway_name = feature.attribute("rwy")
            side = feature.attribute("side")
            geometries = self._polygonal_layer_geometries(feature.geometry(), f"side-stripe {runway_name} {side}")
            for geometry in geometries:
                normalised_features.append(self._clone_feature_with_geometry(feature, geometry))
        return normalised_features

    def _apply_side_stripe_crossing_runway_clipping(
        self,
        physical_features: Dict[str, List[QgsFeature]],
        runway_contexts: dict,
    ) -> int:
        """Remove side stripes where they pass over intersecting runway pavement."""
        if len(runway_contexts) < 2:
            return 0

        clipped_count = 0
        updated_features = []
        for feature in physical_features.get("DetailedSideStripeMarking", []):
            runway_name = feature.attribute("rwy")
            if runway_name not in runway_contexts:
                updated_features.append(feature)
                continue

            geom = feature.geometry()
            if geom is None or geom.isEmpty():
                continue

            try:
                stripe_width = float(feature.attribute("wid_m") or 0.0)
            except (TypeError, ValueError):
                stripe_width = 0.0

            interrupted_by = []
            for other_name, other_context in runway_contexts.items():
                if other_name == runway_name:
                    continue

                other_geom = other_context.get("geom")
                if other_geom is None or other_geom.isEmpty():
                    continue
                if not geom.intersects(other_geom):
                    continue

                clipping_geom = other_geom
                if stripe_width > 0.0:
                    inset_geom = other_geom.buffer(-stripe_width, 8)
                    if inset_geom is not None and not inset_geom.isEmpty():
                        if not inset_geom.isGeosValid():
                            inset_geom = inset_geom.makeValid()
                        if inset_geom is not None and not inset_geom.isEmpty():
                            clipping_geom = inset_geom

                clipped_geom = geom.difference(clipping_geom)
                if clipped_geom is None:
                    continue
                if not clipped_geom.isEmpty() and not clipped_geom.isGeosValid():
                    clipped_geom = clipped_geom.makeValid()
                geom = clipped_geom
                interrupted_by.append(other_name)

                if geom is None or geom.isEmpty():
                    break

            if not interrupted_by:
                updated_features.append(feature)
                continue

            clipped_geometries = self._polygonal_layer_geometries(
                geom, f"side-stripe clipped by {', '.join(interrupted_by)}"
            )
            self._append_feature_note(
                feature,
                "Interrupted at intersecting runway pavement under MOS 8.21 "
                "with one stripe-width extension "
                f"by {', '.join(interrupted_by)}.",
            )
            clipped_count += 1
            if not clipped_geometries:
                continue
            for geom_index, clipped_geometry in enumerate(clipped_geometries):
                updated_features.append(self._clone_feature_with_geometry(feature, clipped_geometry))

        physical_features["DetailedSideStripeMarking"] = updated_features
        return clipped_count

    def _style_runway_designation_layer(self, layer: QgsVectorLayer) -> None:
        """Apply categorized SVG glyph symbols for runway designations."""
        if layer is None or not layer.isValid():
            return

        try:
            from qgis.core import (  # type: ignore
                QgsCategorizedSymbolRenderer,
                QgsMarkerSymbol,
                QgsProperty,
                QgsRendererCategory,
                QgsSymbolLayer,
                QgsSvgMarkerSymbolLayer,
                QgsUnitTypes,
            )

            svg_dir = os.path.join(self.plugin_dir, "styles", "svg", "runway_designations")
            categories = []
            for glyph in "0123456789LCR":
                svg_path = os.path.join(svg_dir, f"runway_designation_{glyph}.svg")
                if not os.path.exists(svg_path):
                    QgsMessageLog.logMessage(
                        f"Runway designation SVG missing: {svg_path}",
                        PLUGIN_TAG,
                        level=Qgis.Warning,
                    )
                    continue

                svg_layer = QgsSvgMarkerSymbolLayer(svg_path)
                svg_layer.setSize(9.0)
                svg_layer.setSizeUnit(QgsUnitTypes.RenderMapUnits)
                try:
                    size_prop = getattr(QgsSvgMarkerSymbolLayer, "PropertySize", None)
                    if size_prop is None:
                        size_prop = getattr(QgsSymbolLayer, "PropertySize")
                    angle_prop = getattr(QgsSvgMarkerSymbolLayer, "PropertyAngle", None)
                    if angle_prop is None:
                        angle_prop = getattr(QgsSymbolLayer, "PropertyAngle")
                    svg_layer.dataDefinedProperties().setProperty(
                        size_prop,
                        QgsProperty.fromField("glyph_size"),
                    )
                    svg_layer.dataDefinedProperties().setProperty(
                        angle_prop,
                        QgsProperty.fromField("angle_deg"),
                    )
                except Exception as dd_error:
                    QgsMessageLog.logMessage(
                        "Warning: Could not apply SVG glyph data-defined " f"properties: {dd_error}",
                        PLUGIN_TAG,
                        level=Qgis.Warning,
                    )

                symbol = QgsMarkerSymbol()
                symbol.changeSymbolLayer(0, svg_layer)
                categories.append(QgsRendererCategory(glyph, symbol, glyph))

            if categories:
                layer.setRenderer(QgsCategorizedSymbolRenderer("glyph", categories))
            layer.setLabelsEnabled(False)
            layer.triggerRepaint()
        except Exception as style_error:
            QgsMessageLog.logMessage(
                f"Warning: Could not apply runway designation SVG styling: {style_error}",
                PLUGIN_TAG,
                level=Qgis.Warning,
            )

    def _runway_designators(self, runway_name: str) -> Tuple[str, str]:
        if "/" in runway_name:
            primary, reciprocal = runway_name.split("/", 1)
            return primary.strip(), reciprocal.strip()
        return runway_name, "Reciprocal"

    def _runway_designation_length(self, designator: str) -> float:
        number_height = 9.5 if any(char in designator for char in ("6", "9")) else 9.0
        suffix_height = 9.0 if designator[-1:] in {"L", "C", "R"} else 0.0
        return number_height + (6.0 + suffix_height if suffix_height else 0.0)

    def _runway_designation_start_offset(self) -> float:
        threshold_line_width = 1.2
        piano_key_gap_after_threshold = 6.0
        piano_key_length = 30.0
        designation_gap_after_piano_keys = 12.0
        return (
            threshold_line_width + piano_key_gap_after_threshold + piano_key_length + designation_gap_after_piano_keys
        )

    def _runway_designation_glyph_width(self, glyph: str) -> float:
        glyph_height = 9.5 if glyph in {"6", "9"} else 9.0
        svg_path = os.path.join(
            self.plugin_dir,
            "styles",
            "svg",
            "runway_designations",
            f"runway_designation_{glyph}.svg",
        )
        try:
            with open(svg_path, "r", encoding="utf-8") as svg_file:
                svg_text = svg_file.read(1000)
            width_match = re.search(r'\bwidth="([0-9.]+)', svg_text)
            height_match = re.search(r'\bheight="([0-9.]+)', svg_text)
            if width_match and height_match:
                svg_width = float(width_match.group(1))
                svg_height = float(height_match.group(1))
                if svg_width > 0 and svg_height > 0:
                    return glyph_height * svg_width / svg_height
        except Exception:
            pass

        return 3.0

    def _runway_designation_glyphs(self, designator: str) -> List[Tuple[str, float, float, float]]:
        """Return glyph, longitudinal centre, lateral centre and glyph height."""
        suffix = designator[-1:] if designator[-1:] in {"L", "C", "R"} else ""
        number_text = designator[:-1] if suffix else designator
        number_height = 9.5 if any(char in number_text for char in ("6", "9")) else 9.0
        digit_gap = 2.2
        glyphs: List[Tuple[str, float, float, float]] = []
        number_row_center = number_height / 2.0
        if suffix:
            number_row_center = 9.0 + 6.0 + number_height / 2.0

        widths = [self._runway_designation_glyph_width(char) for char in number_text]
        total_width = sum(widths) + max(0, len(widths) - 1) * digit_gap
        lateral_cursor = -total_width / 2.0
        for char, width in zip(number_text, widths):
            lateral_center = lateral_cursor + width / 2.0
            glyph_height = 9.5 if char in {"6", "9"} else 9.0
            glyphs.append((char, number_row_center, lateral_center, glyph_height))
            lateral_cursor += width + digit_gap

        if suffix:
            glyphs.append((suffix, 4.5, 0.0, 9.0))

        return glyphs

    def _project_lateral(self, point: QgsPointXY, lateral_m: float, azimuth_degrees: float) -> QgsPointXY:
        if abs(lateral_m) <= 1e-9:
            return point
        azimuth = (azimuth_degrees + 90.0) % 360.0 if lateral_m > 0 else (azimuth_degrees - 90.0 + 360.0) % 360.0
        return point.project(abs(lateral_m), azimuth)

    def _create_runway_marking_rectangle(
        self,
        origin: QgsPointXY,
        runway_azimuth: float,
        start_offset_m: float,
        length_m: float,
        lateral_center_m: float,
        width_m: float,
        description: str,
    ) -> Optional[QgsGeometry]:
        if length_m <= 0 or width_m <= 0:
            return None
        start_center = origin.project(start_offset_m, runway_azimuth)
        end_center = origin.project(start_offset_m + length_m, runway_azimuth)
        if start_center is None or end_center is None:
            return None

        start_center = self._project_lateral(start_center, lateral_center_m, runway_azimuth)
        end_center = self._project_lateral(end_center, lateral_center_m, runway_azimuth)
        half_width = width_m / 2.0
        az_l = (runway_azimuth - 90.0 + 360.0) % 360.0
        az_r = (runway_azimuth + 90.0) % 360.0
        corners = [
            start_center.project(half_width, az_l),
            start_center.project(half_width, az_r),
            end_center.project(half_width, az_r),
            end_center.project(half_width, az_l),
        ]
        if not all(corners):
            return None
        return self._create_polygon_from_corners(corners, description)

    def _create_pre_threshold_chevron_polygon(
        self,
        apex_point: QgsPointXY,
        left_endpoint: QgsPointXY,
        right_endpoint: QgsPointXY,
        width_m: float,
        description: str,
    ) -> Optional[QgsGeometry]:
        if width_m <= 0:
            return None

        left_leg_len = math.hypot(
            left_endpoint.x() - apex_point.x(),
            left_endpoint.y() - apex_point.y(),
        )
        right_leg_len = math.hypot(
            right_endpoint.x() - apex_point.x(),
            right_endpoint.y() - apex_point.y(),
        )
        if left_leg_len <= 1e-9 or right_leg_len <= 1e-9:
            return None

        half_width = width_m / 2.0
        left_unit = (
            (left_endpoint.x() - apex_point.x()) / left_leg_len,
            (left_endpoint.y() - apex_point.y()) / left_leg_len,
        )
        right_unit = (
            (right_endpoint.x() - apex_point.x()) / right_leg_len,
            (right_endpoint.y() - apex_point.y()) / right_leg_len,
        )
        bisector = (
            left_unit[0] + right_unit[0],
            left_unit[1] + right_unit[1],
        )
        bisector_len = math.hypot(bisector[0], bisector[1])
        if bisector_len <= 1e-9:
            return None
        bisector = (bisector[0] / bisector_len, bisector[1] / bisector_len)
        miter_len = half_width / math.sin(math.radians(45.0))

        left_perp = (-left_unit[1], left_unit[0])
        right_perp = (-right_unit[1], right_unit[0])

        forward = QgsPointXY(
            apex_point.x() - bisector[0] * miter_len,
            apex_point.y() - bisector[1] * miter_len,
        )
        inner_apex = QgsPointXY(
            apex_point.x() + bisector[0] * miter_len,
            apex_point.y() + bisector[1] * miter_len,
        )
        left_outer = QgsPointXY(
            left_endpoint.x() + left_perp[0] * half_width,
            left_endpoint.y() + left_perp[1] * half_width,
        )
        left_inner = QgsPointXY(
            left_endpoint.x() - left_perp[0] * half_width,
            left_endpoint.y() - left_perp[1] * half_width,
        )
        right_inner = QgsPointXY(
            right_endpoint.x() + right_perp[0] * half_width,
            right_endpoint.y() + right_perp[1] * half_width,
        )
        right_outer = QgsPointXY(
            right_endpoint.x() - right_perp[0] * half_width,
            right_endpoint.y() - right_perp[1] * half_width,
        )

        return self._create_polygon_from_corners(
            [forward, left_outer, left_inner, inner_apex, right_inner, right_outer],
            description,
        )

    def _create_marking_segment_between_points(
        self,
        start_point: QgsPointXY,
        end_point: QgsPointXY,
        width_m: float,
        description: str,
    ) -> Optional[QgsGeometry]:
        if width_m <= 0:
            return None
        dx = end_point.x() - start_point.x()
        dy = end_point.y() - start_point.y()
        segment_len = math.hypot(dx, dy)
        if segment_len <= 1e-9:
            return None

        half_width = width_m / 2.0
        perp_x = -dy / segment_len * half_width
        perp_y = dx / segment_len * half_width
        corners = [
            QgsPointXY(start_point.x() + perp_x, start_point.y() + perp_y),
            QgsPointXY(start_point.x() - perp_x, start_point.y() - perp_y),
            QgsPointXY(end_point.x() - perp_x, end_point.y() - perp_y),
            QgsPointXY(end_point.x() + perp_x, end_point.y() + perp_y),
        ]
        return self._create_polygon_from_corners(corners, description)

    def _create_displaced_threshold_arrow_polygon(
        self,
        origin: QgsPointXY,
        runway_azimuth: float,
        arrow_tip_offset_m: float,
        stem_width_m: float,
        description: str,
    ) -> Optional[QgsGeometry]:
        head_length = 10.0
        stem_length = 20.0
        head_half_width = 1.75
        head_line_width = 0.9

        tip = origin.project(arrow_tip_offset_m, runway_azimuth)
        head_base = origin.project(arrow_tip_offset_m - head_length, runway_azimuth)
        tail = origin.project(arrow_tip_offset_m - head_length - stem_length, runway_azimuth)
        if not tip or not head_base or not tail:
            return None

        head_left = self._project_lateral(head_base, -head_half_width, runway_azimuth)
        head_right = self._project_lateral(head_base, head_half_width, runway_azimuth)
        if not head_left or not head_right:
            return None

        stem = self._create_marking_segment_between_points(
            tail,
            head_base,
            float(stem_width_m or 0.3),
            f"{description} stem",
        )
        left_head = self._create_marking_segment_between_points(
            tip,
            head_left,
            head_line_width,
            f"{description} left head",
        )
        right_head = self._create_marking_segment_between_points(
            tip,
            head_right,
            head_line_width,
            f"{description} right head",
        )
        if not stem or not left_head or not right_head:
            return None

        arrow_geom = stem.combine(left_head)
        if not arrow_geom or arrow_geom.isEmpty():
            return None
        arrow_geom = arrow_geom.combine(right_head)
        if not arrow_geom or arrow_geom.isEmpty():
            return None
        if not arrow_geom.isGeosValid():
            arrow_geom = arrow_geom.makeValid()
        return arrow_geom

    def _detail_marking_attrs(
        self,
        runway_name: str,
        end_desig: str,
        mark_type: str,
        sub_type: str,
        len_m: float,
        wid_m: float,
        ref_mos: str,
        side: str = "",
        stripe_no: Optional[int] = None,
        offset_m: Optional[float] = None,
        spacing_m: Optional[float] = None,
        lda_m: Optional[float] = None,
        mandatory: bool = True,
        notes: str = "",
    ) -> dict:
        return {
            "rwy": runway_name,
            "end_desig": end_desig,
            "mark_type": mark_type,
            "sub_type": sub_type,
            "side": side,
            "stripe_no": stripe_no,
            "len_m": round(len_m, 3),
            "wid_m": round(wid_m, 3),
            "offset_m": round(offset_m, 3) if offset_m is not None else None,
            "spacing_m": round(spacing_m, 3) if spacing_m is not None else None,
            "lda_m": round(lda_m, 3) if lda_m is not None else None,
            "mandatory": mandatory,
            "ref_mos": ref_mos,
            "notes": notes,
        }

    def _runway_surface_description(self, runway_data: dict) -> str:
        category = str(runway_data.get("surface_category") or "").strip()
        material = str(runway_data.get("surface_material") or "").strip()
        if category and material:
            return f"{category} / {material}"
        if category:
            return category
        return "not selected"

    def _is_marking_surface_applicable(self, runway_data: dict) -> bool:
        """Return True when selected runway surface supports sealed-surface markings."""
        return str(runway_data.get("surface_category") or "").strip() == "Sealed"

    def _surface_trigger_note(self, mos_ref: str, runway_data: dict) -> str:
        surface_desc = self._runway_surface_description(runway_data)
        if self._is_marking_surface_applicable(runway_data):
            return f"{mos_ref} surface trigger met: selected runway surface is " f"{surface_desc}."
        return (
            f"{mos_ref} surface trigger not met: selected runway surface is " f"{surface_desc}; marking not generated."
        )

    def _marking_qa_attrs(
        self,
        runway_name: str,
        end_desig: str,
        mandatory: List[str],
        optional: List[str],
        assumptions: List[str],
        skipped: List[str],
    ) -> dict:
        return {
            "rwy": runway_name,
            "end_desig": end_desig,
            "mandatory": "; ".join(sorted(set(mandatory))) or "None",
            "optional": "; ".join(sorted(set(optional))) or "None",
            "assumptions": "; ".join(sorted(set(assumptions))) or "None",
            "skipped": "; ".join(skipped) or "None",
            "ref_mos": "MOS 8.15; MOS 8.17-8.25",
            "notes": "Generated from detailed runway marking pass.",
        }

    def _append_marking_qa_records(
        self,
        generated: List[Tuple[str, QgsGeometry, dict]],
        runway_name: str,
        qa_records: dict,
        whole_runway_mandatory: List[str],
        whole_runway_optional: List[str],
    ) -> None:
        family_by_layer = {
            "DetailedThresholdMarking": "Threshold markings",
            "DetailedDesignationMarking": "Runway designation markings",
            "DetailedAimingPointMarking": "Aiming point markings",
            "DetailedTouchdownZoneMarking": "Touchdown zone markings",
            "DetailedDisplacedThresholdMarking": "Displaced threshold markings",
            "DetailedPreThresholdAreaMarking": "Pre-threshold area markings",
            "DetailedCentrelineMarking": "Centreline markings",
            "DetailedSideStripeMarking": "Side-stripe markings",
        }

        for end_desig, qa in qa_records.items():
            mandatory = list(whole_runway_mandatory)
            optional = list(whole_runway_optional)
            for element_type, _, attrs in generated:
                family = family_by_layer.get(element_type)
                if family is None:
                    continue
                feature_end = attrs.get("end_desig")
                if feature_end not in {end_desig, ""}:
                    continue
                if attrs.get("mandatory", True):
                    mandatory.append(family)
                else:
                    optional.append(family)

            point = qa.get("point")
            if point is None:
                continue
            generated.append(
                (
                    "DetailedMarkingQA",
                    QgsGeometry.fromPointXY(point),
                    self._marking_qa_attrs(
                        runway_name,
                        end_desig,
                        mandatory,
                        optional,
                        list(qa.get("assumptions", [])),
                        list(qa.get("skipped", [])),
                    ),
                )
            )

    def _threshold_marking_params(self, runway_width: float) -> Optional[Tuple[int, float]]:
        return self.get_active_ruleset().threshold_marking_params(runway_width)

    def _centreline_marking_width(self, arc_num: int, type_primary: str, type_reciprocal: str) -> float:
        return self.get_active_ruleset().centreline_marking_width(arc_num, type_primary, type_reciprocal)

    def _declared_lda_for_end(self, runway_data: dict, end_desig: str, fallback_length: float) -> float:
        for record in runway_data.get("declared_distances", []):
            if record.get("end_desig") == end_desig and record.get("lda_m") is not None:
                try:
                    return float(record.get("lda_m"))
                except (TypeError, ValueError):
                    break
        return fallback_length

    def _aiming_point_rule(
        self, runway_width: float, lda_m: float, runway_type: str
    ) -> Optional[Tuple[float, float, float, float, str]]:
        return self.get_active_ruleset().aiming_point_rule(runway_width, lda_m, runway_type)

    def _touchdown_zone_offsets(self, lda_m: float) -> List[float]:
        return self.get_active_ruleset().touchdown_zone_offsets(lda_m)

    def _line_segment_intersection_point(
        self,
        a_start: QgsPointXY,
        a_end: QgsPointXY,
        b_start: QgsPointXY,
        b_end: QgsPointXY,
    ) -> Optional[QgsPointXY]:
        """Return the intersection point for two line segments if one exists."""
        x1, y1 = a_start.x(), a_start.y()
        x2, y2 = a_end.x(), a_end.y()
        x3, y3 = b_start.x(), b_start.y()
        x4, y4 = b_end.x(), b_end.y()

        denom = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
        if abs(denom) <= 1e-9:
            return None

        det_a = x1 * y2 - y1 * x2
        det_b = x3 * y4 - y3 * x4
        px = (det_a * (x3 - x4) - (x1 - x2) * det_b) / denom
        py = (det_a * (y3 - y4) - (y1 - y2) * det_b) / denom

        def within(value: float, bound_1: float, bound_2: float) -> bool:
            low = min(bound_1, bound_2) - 1e-6
            high = max(bound_1, bound_2) + 1e-6
            return low <= value <= high

        if not (
            within(px, x1, x2)
            and within(py, y1, y2)
            and within(px, x3, x4)
            and within(py, y3, y4)
        ):
            return None

        return QgsPointXY(px, py)

    def _runway_holding_position_rule(
        self, runway_code_num: int, runway_type: str
    ) -> Optional[Tuple[float, str]]:
        """Return the minimum holding-position distance from Table 6.56(1)."""
        return self.get_active_ruleset().runway_holding_position_rule(runway_code_num, runway_type)

    def _build_runway_holding_position_pattern(
        self,
        origin: QgsPointXY,
        runway_azimuth: float,
        runway_width: float,
        start_offset_m: float,
        runway_name: str,
        end_desig: str,
        intersecting_runway_name: str,
        distance_m: float,
    ) -> List[Tuple[str, QgsGeometry, dict]]:
        """Build a Pattern A runway holding position marking."""
        generated: List[Tuple[str, QgsGeometry, dict]] = []
        line_width = 0.3
        line_spacing = 0.3
        dashed_segment_len = 0.95
        dashed_gap_len = 0.95
        bar_count = 4

        def create_transverse_bar(bar_offset: float, dashed: bool, bar_no: int) -> None:
            if not dashed:
                geom = self._create_runway_marking_rectangle(
                    origin,
                    runway_azimuth,
                    bar_offset,
                    line_width,
                    0.0,
                    runway_width,
                    f"Runway holding position {runway_name} {end_desig} {bar_no}",
                )
                if geom is None:
                    return
                generated.append(
                    (
                        "DetailedRunwayHoldingPositionMarking",
                        geom,
                        self._detail_marking_attrs(
                            runway_name,
                            end_desig,
                            "Runway Holding Position",
                            "Pattern A",
                            line_width,
                            runway_width,
                            "MOS 8.39(2); MOS 8.39(7); Table 6.56(1)",
                            stripe_no=bar_no,
                            offset_m=round(bar_offset, 3),
                            spacing_m=line_spacing,
                            mandatory=True,
                            notes=(
                                f"Pattern A solid bar {bar_no} of {bar_count}. "
                                f"Nearest edge offset {distance_m:.1f} m from intersecting runway centreline. "
                                f"Intersecting runway: {intersecting_runway_name}."
                            ),
                        ),
                    )
                )
                return

            segment_start = 0.0
            segment_no = 1
            while segment_start < runway_width - 1e-6:
                segment_width = min(dashed_segment_len, runway_width - segment_start)
                lateral_center = -runway_width / 2.0 + segment_start + segment_width / 2.0
                geom = self._create_runway_marking_rectangle(
                    origin,
                    runway_azimuth,
                    bar_offset,
                    line_width,
                    lateral_center,
                    segment_width,
                    f"Runway holding position {runway_name} {end_desig} {bar_no} dash {segment_no}",
                )
                if geom is not None:
                    generated.append(
                        (
                            "DetailedRunwayHoldingPositionMarking",
                            geom,
                            self._detail_marking_attrs(
                                runway_name,
                                end_desig,
                                "Runway Holding Position",
                                "Pattern A",
                                line_width,
                                segment_width,
                                "MOS 8.39(2); MOS 8.39(7); Table 6.56(1)",
                                stripe_no=bar_no,
                                offset_m=round(bar_offset, 3),
                                spacing_m=dashed_gap_len,
                                mandatory=True,
                                notes=(
                                    f"Pattern A dashed bar {bar_no} of {bar_count}; "
                                    f"dash/gap length {dashed_segment_len:.2f} m. "
                                    f"Nearest edge offset {distance_m:.1f} m from intersecting runway centreline. "
                                    f"Intersecting runway: {intersecting_runway_name}."
                                ),
                            ),
                        )
                    )
                segment_start += dashed_segment_len + dashed_gap_len
                segment_no += 1

        for bar_no in range(bar_count):
            bar_offset = start_offset_m + bar_no * (line_width + line_spacing)
            create_transverse_bar(bar_offset, bar_no >= bar_count - 2, bar_no + 1)
        return generated

    def generate_detailed_runway_markings(self, runway_data: dict) -> List[Tuple[str, QgsGeometry, dict]]:
        """Generate MOS139 runway marking polygons in a separate layer group."""
        plugin_tag = PLUGIN_TAG
        generated: List[Tuple[str, QgsGeometry, dict]] = []

        thr_point = runway_data.get("thr_point")
        rec_thr_point = runway_data.get("rec_thr_point")
        runway_width = runway_data.get("width")
        if not thr_point or not rec_thr_point or not runway_width or runway_width <= 0:
            return generated

        rwy_params = self._get_runway_parameters(thr_point, rec_thr_point)
        if rwy_params is None:
            return generated

        def non_negative_number(value, default=0.0):
            try:
                parsed = float(value)
                return parsed if parsed >= 0 else default
            except (TypeError, ValueError):
                return default

        runway_name = runway_data.get("short_name", f"RWY_{runway_data.get('original_index', '?')}")
        runway_data["tdz_marking_extents"] = {}
        primary_desig, reciprocal_desig = self._runway_designators(runway_name)
        runway_length = float(rwy_params["length"])
        disp_primary = non_negative_number(runway_data.get("thr_displaced_1"), 0.0)
        disp_reciprocal = non_negative_number(runway_data.get("thr_displaced_2"), 0.0)
        physical_endpoints = self._get_physical_runway_endpoints(
            thr_point, rec_thr_point, disp_primary, disp_reciprocal, rwy_params
        )
        if physical_endpoints:
            phys_p_start, phys_p_end, _ = physical_endpoints
        else:
            phys_p_start, phys_p_end = thr_point, rec_thr_point
        try:
            arc_num = int(float(runway_data.get("arc_num") or 0))
        except (TypeError, ValueError):
            arc_num = 0
        type_primary = runway_data.get("type1", "")
        type_reciprocal = runway_data.get("type2", "")
        centreline_width = self._centreline_marking_width(arc_num, type_primary, type_reciprocal)
        surface_markings_applicable = self._is_marking_surface_applicable(runway_data)

        end_specs = [
            (
                primary_desig,
                thr_point,
                rwy_params["azimuth_p_r"],
                type_primary,
                phys_p_start,
                rwy_params["azimuth_r_p"],
                non_negative_number(runway_data.get("thr_pre_area_1"), 0.0),
                disp_primary,
                self._bool_from_runway_data(runway_data.get("landing_available_1", True)),
                self._bool_from_runway_data(runway_data.get("lahso_applied_1", False)),
            ),
            (
                reciprocal_desig,
                rec_thr_point,
                rwy_params["azimuth_r_p"],
                type_reciprocal,
                phys_p_end,
                rwy_params["azimuth_p_r"],
                non_negative_number(runway_data.get("thr_pre_area_2"), 0.0),
                disp_reciprocal,
                self._bool_from_runway_data(runway_data.get("landing_available_2", True)),
                self._bool_from_runway_data(runway_data.get("lahso_applied_2", False)),
            ),
        ]
        default_assumptions = {
            f"Runway surface selected: {self._runway_surface_description(runway_data)}.",
            "Piano keys start 6 m after the 1.2 m threshold line.",
            "Runway designations use SVG glyphs; polygon glyph generation deferred.",
            "Centreline uses default 30 m stripe / 20 m gap pattern.",
            "Take-off RVR < 550 m centreline-width trigger not modelled.",
            "Taxiway marking breaks are out of scope.",
            "MOS 8.15 intersecting-runway clipping is applied after QA capture; centreline markings remain continuous.",
            "MOS 8.21 side stripes are removed where they cross intersecting runway pavement.",
        }
        qa_records = {
            end_desig: {
                "point": origin,
                "assumptions": set(default_assumptions),
                "skipped": [],
            }
            for end_desig, origin, _, _, _, _, _, _, _, _ in end_specs
        }
        for qa in qa_records.values():
            qa["assumptions"].update(
                {
                    self._surface_trigger_note("MOS 8.17", runway_data),
                    self._surface_trigger_note("MOS 8.21", runway_data),
                    self._surface_trigger_note("MOS 8.22", runway_data),
                    self._surface_trigger_note("MOS 8.23", runway_data),
                }
            )
        whole_runway_mandatory: List[str] = []
        whole_runway_optional: List[str] = []

        # Threshold transverse bars, piano keys, designation anchor points,
        # aiming points, and touchdown-zone markings are generated per runway end.
        for (
            end_desig,
            origin,
            azimuth,
            runway_type,
            pre_area_start,
            pre_area_outward_azimuth,
            pre_area_len,
            displaced_len,
            landing_available,
            lahso_applied,
        ) in end_specs:
            skipped = qa_records[end_desig]["skipped"]
            if displaced_len > 1e-6:
                first_arrow_tip_offset = displaced_len + 7.2 - 20.0
                arrow_tip_offset = first_arrow_tip_offset
                arrow_no = 1
                while arrow_tip_offset - 30.0 >= -1e-6:
                    geom = self._create_displaced_threshold_arrow_polygon(
                        pre_area_start,
                        azimuth,
                        arrow_tip_offset,
                        centreline_width,
                        f"Displaced threshold arrow {runway_name} {end_desig} {arrow_no}",
                    )
                    if geom:
                        generated.append(
                            (
                                "DetailedDisplacedThresholdMarking",
                                geom,
                                self._detail_marking_attrs(
                                    runway_name,
                                    end_desig,
                                    "Displaced Threshold",
                                    "Arrow",
                                    30.0,
                                    3.5,
                                    "MOS 8.26",
                                    stripe_no=arrow_no,
                                    offset_m=arrow_tip_offset,
                                    spacing_m=50.0,
                                    mandatory=True,
                                    notes=(
                                        "Head 10 m, stem 20 m, total arrow length 30 m. First tip is 20 m before "
                                        "the displaced-threshold piano-key commencement; "
                                        "preceding complete arrows repeat at 50 m intervals."
                                    ),
                                ),
                            )
                        )
                    else:
                        skipped.append(f"Displaced threshold arrow {arrow_no}: geometry generation failed.")
                    arrow_tip_offset -= 50.0
                    arrow_no += 1

            if surface_markings_applicable:
                threshold_bar = self._create_runway_marking_rectangle(
                    origin,
                    azimuth,
                    0.0,
                    1.2,
                    0.0,
                    runway_width,
                    f"Threshold bar {runway_name} {end_desig}",
                )
                if threshold_bar:
                    generated.append(
                        (
                            "DetailedThresholdMarking",
                            threshold_bar,
                            self._detail_marking_attrs(
                                runway_name,
                                end_desig,
                                "Threshold",
                                "Transverse Line",
                                1.2,
                                runway_width,
                                "MOS 8.17(2)(a)",
                                offset_m=0.0,
                                mandatory=True,
                                notes=self._surface_trigger_note("MOS 8.17", runway_data),
                            ),
                        )
                    )
                else:
                    skipped.append("Threshold transverse line: geometry generation failed.")

                threshold_params = self._threshold_marking_params(runway_width)
                if threshold_params is not None:
                    stripe_count, gap_m = threshold_params
                    stripe_width = 1.8
                    central_gap_m = 2.0 * stripe_width
                    total_marked_width = stripe_count * stripe_width + (stripe_count - 2) * gap_m + central_gap_m
                    edge_space = (runway_width - total_marked_width) / 2.0
                    if edge_space < gap_m:
                        stripe_width = max(
                            0.1,
                            (runway_width - stripe_count * gap_m) / (stripe_count + 2),
                        )
                        central_gap_m = 2.0 * stripe_width
                        edge_space = gap_m
                    left_edge = -runway_width / 2.0 + edge_space
                    piano_start = 1.2 + 6.0
                    stripe_left = left_edge
                    for stripe_idx in range(stripe_count):
                        lateral_center = stripe_left + stripe_width / 2.0
                        geom = self._create_runway_marking_rectangle(
                            origin,
                            azimuth,
                            piano_start,
                            30.0,
                            lateral_center,
                            stripe_width,
                            f"Piano key {runway_name} {end_desig} {stripe_idx + 1}",
                        )
                        if geom:
                            generated.append(
                                (
                                    "DetailedThresholdMarking",
                                    geom,
                                    self._detail_marking_attrs(
                                        runway_name,
                                        end_desig,
                                        "Threshold",
                                        "Piano Key",
                                        30.0,
                                        stripe_width,
                                        "MOS 8.17(2)(b); Table 8.17(2)",
                                        stripe_no=stripe_idx + 1,
                                        offset_m=piano_start,
                                        spacing_m=gap_m,
                                        mandatory=True,
                                        notes=(
                                            self._surface_trigger_note("MOS 8.17", runway_data)
                                            + f" Edge space {edge_space:.3f} m; central gap {central_gap_m:.3f} m; "
                                            "stripe width 1.8 m unless adjusted to keep edge spaces >= a."
                                        ),
                                    ),
                                )
                            )
                        stripe_left += stripe_width
                        if stripe_idx < stripe_count - 1:
                            stripe_left += central_gap_m if stripe_idx == stripe_count // 2 - 1 else gap_m
                else:
                    skipped.append(
                        "Threshold piano keys: unsupported runway width " f"{runway_width} m for Table 8.17(2)."
                    )
                    QgsMessageLog.logMessage(
                        f"Detailed threshold piano keys not generated for {runway_name}: unsupported width {runway_width}.",
                        plugin_tag,
                        level=Qgis.Info,
                    )
            else:
                skipped.append("Threshold markings: MOS 8.17 sealed-surface trigger not met.")

            designation_edge_offset = self._runway_designation_start_offset()
            angle_deg = azimuth % 360.0
            for glyph_no, (
                glyph,
                longitudinal_center,
                lateral_center,
                glyph_height,
            ) in enumerate(self._runway_designation_glyphs(end_desig), start=1):
                glyph_width = self._runway_designation_glyph_width(glyph)
                glyph_center = origin.project(designation_edge_offset + longitudinal_center, azimuth)
                if glyph_center:
                    glyph_center = self._project_lateral(glyph_center, lateral_center, azimuth)
                if not glyph_center:
                    skipped.append(f"Runway designation glyph {glyph}: anchor projection failed.")
                    continue
                generated.append(
                    (
                        "DetailedDesignationMarking",
                        QgsGeometry.fromPointXY(glyph_center),
                        {
                            "rwy": runway_name,
                            "end_desig": end_desig,
                            "text": end_desig,
                            "bearing": round(azimuth, 3),
                            "label_rot": round(angle_deg, 3),
                            "glyph": glyph,
                            "glyph_no": glyph_no,
                            "glyph_size": round(glyph_width, 3),
                            "glyph_w_m": round(glyph_width, 3),
                            "angle_deg": round(angle_deg, 3),
                            "offset_m": round(designation_edge_offset, 3),
                            "height_m": round(glyph_height, 3),
                            "mandatory": True,
                            "ref_mos": "MOS 8.18",
                            "notes": "SVG glyph test implementation.",
                        },
                    )
                )

            if not landing_available:
                skipped.append("Aiming point and touchdown zone markings: landing not available for this runway end.")
            lda_m = self._declared_lda_for_end(runway_data, end_desig, runway_length) if landing_available else None
            aiming_rule = self._aiming_point_rule(runway_width, lda_m, runway_type) if landing_available else None
            if not surface_markings_applicable:
                skipped.append(
                    "Aiming point and touchdown zone markings: MOS 8.22/8.23 " "sealed-surface triggers not met."
                )
            elif landing_available and aiming_rule is not None:
                aim_offset, aim_len, aim_width, aim_spacing, aim_ref = aiming_rule
                for side_name, sign in (("L", -1.0), ("R", 1.0)):
                    lateral_center = sign * (aim_spacing / 2.0 + aim_width / 2.0)
                    geom = self._create_runway_marking_rectangle(
                        origin,
                        azimuth,
                        aim_offset,
                        aim_len,
                        lateral_center,
                        aim_width,
                        f"Aiming point {runway_name} {end_desig} {side_name}",
                    )
                    if geom:
                        generated.append(
                            (
                                "DetailedAimingPointMarking",
                                geom,
                                self._detail_marking_attrs(
                                    runway_name,
                                    end_desig,
                                    "Aiming Point",
                                    "Stripe",
                                    aim_len,
                                    aim_width,
                                    aim_ref,
                                    side=side_name,
                                    offset_m=aim_offset,
                                    spacing_m=aim_spacing,
                                    lda_m=lda_m,
                                    mandatory=True,
                                    notes=self._surface_trigger_note("MOS 8.22", runway_data),
                                ),
                            )
                        )

                type_abbr = self.get_active_ruleset().classify_runway_type(runway_type)
                if type_abbr in {"PA_I", "PA_II_III"}:
                    touchdown_offsets = self._touchdown_zone_offsets(lda_m)
                    midpoint_zone_start = runway_length / 2.0 - 275.0
                    midpoint_zone_end = runway_length / 2.0 + 275.0
                    for offset in touchdown_offsets:
                        if abs(offset - aim_offset) <= 50.0:
                            skipped.append(
                                "ICAO A touchdown zone pair " f"at {offset:g} m: within 50 m of aiming point."
                            )
                            continue
                        block_start = offset
                        block_end = offset + 22.5
                        if block_start < midpoint_zone_end and block_end > midpoint_zone_start:
                            skipped.append(
                                "ICAO A touchdown zone pair "
                                f"at {offset:g} m: intersects 550 m midpoint exclusion zone."
                            )
                            continue
                        for side_name, sign in (("L", -1.0), ("R", 1.0)):
                            lateral_center = sign * (aim_spacing / 2.0 + 1.5)
                            geom = self._create_runway_marking_rectangle(
                                origin,
                                azimuth,
                                offset,
                                22.5,
                                lateral_center,
                                3.0,
                                f"TDZ ICAO A {runway_name} {end_desig} {offset}",
                            )
                            if geom:
                                rendered_extent = offset + 22.5
                                runway_data["tdz_marking_extents"][end_desig] = max(
                                    runway_data["tdz_marking_extents"].get(end_desig, 0.0),
                                    rendered_extent,
                                )
                                generated.append(
                                    (
                                        "DetailedTouchdownZoneMarking",
                                        geom,
                                        self._detail_marking_attrs(
                                            runway_name,
                                            end_desig,
                                            "Touchdown Zone",
                                            "ICAO A",
                                            22.5,
                                            3.0,
                                            "MOS 8.23; MOS 8.24",
                                            side=side_name,
                                            offset_m=offset,
                                            spacing_m=aim_spacing,
                                            lda_m=lda_m,
                                            mandatory=(
                                                surface_markings_applicable
                                                and runway_width >= 30.0
                                                and runway_length >= 1500.0
                                            ),
                                            notes=(
                                                self._surface_trigger_note("MOS 8.23", runway_data)
                                                + " Table 8.24 selection uses LDA for this initial implementation."
                                            ),
                                        ),
                                    )
                                )
                else:
                    for offset in (150.0, 450.0):
                        for side_name, sign in (("L", -1.0), ("R", 1.0)):
                            lateral_center = sign * (aim_spacing / 2.0 + 1.5)
                            geom = self._create_runway_marking_rectangle(
                                origin,
                                azimuth,
                                offset,
                                22.5,
                                lateral_center,
                                3.0,
                                f"TDZ simple {runway_name} {end_desig} {offset}",
                            )
                            if geom:
                                rendered_extent = offset + 22.5
                                runway_data["tdz_marking_extents"][end_desig] = max(
                                    runway_data["tdz_marking_extents"].get(end_desig, 0.0),
                                    rendered_extent,
                                )
                                generated.append(
                                    (
                                        "DetailedTouchdownZoneMarking",
                                        geom,
                                        self._detail_marking_attrs(
                                            runway_name,
                                            end_desig,
                                            "Touchdown Zone",
                                            "Simple",
                                            22.5,
                                            3.0,
                                            "MOS 8.23; MOS 8.25",
                                            side=side_name,
                                            offset_m=offset,
                                            spacing_m=aim_spacing,
                                            lda_m=lda_m,
                                            mandatory=(
                                                surface_markings_applicable
                                                and runway_width >= 30.0
                                                and runway_length >= 1500.0
                                            ),
                                            notes=(
                                                self._surface_trigger_note("MOS 8.23", runway_data)
                                                + " 450 m pair generated by default "
                                                "even when runway length is under 1500 m."
                                            ),
                                        ),
                                    )
                                )
            else:
                if landing_available:
                    skipped.append(
                        "Aiming point and dependent touchdown zone markings: no "
                        "current rule for this runway width/type combination."
                    )

            if pre_area_len >= 30.0:
                qa_records[end_desig]["assumptions"].add(
                    "Pre-threshold area entered in dialog is assumed sealed and not suitable for normal aircraft usage."
                )
                chevron_leg_run = max(15.0, runway_width / 2.0 - 7.5)
                pre_area_clip = self._create_rectangle_from_start(
                    pre_area_start,
                    pre_area_outward_azimuth,
                    pre_area_len,
                    runway_width / 2.0,
                    f"Pre-threshold area clip {runway_name} {end_desig}",
                )
                apex_offset = -7.5
                chevron_no = 1
                while apex_offset < pre_area_len - 1e-6:
                    base_offset = min(apex_offset + chevron_leg_run, pre_area_len)
                    if base_offset <= 0.0:
                        apex_offset += 30.0
                        chevron_no += 1
                        continue
                    chevron_run = base_offset - apex_offset
                    if chevron_run <= 1e-6:
                        break
                    apex_point = pre_area_start.project(apex_offset, pre_area_outward_azimuth)
                    base_center = pre_area_start.project(base_offset, pre_area_outward_azimuth)
                    if not apex_point or not base_center:
                        skipped.append(f"Pre-threshold area chevron {chevron_no}: projection failed.")
                        apex_offset += 30.0
                        chevron_no += 1
                        continue

                    left_endpoint = self._project_lateral(
                        base_center,
                        -chevron_run,
                        pre_area_outward_azimuth,
                    )
                    right_endpoint = self._project_lateral(
                        base_center,
                        chevron_run,
                        pre_area_outward_azimuth,
                    )
                    if not left_endpoint or not right_endpoint:
                        skipped.append(f"Pre-threshold area chevron {chevron_no}: endpoint projection failed.")
                        apex_offset += 30.0
                        chevron_no += 1
                        continue
                    geom = self._create_pre_threshold_chevron_polygon(
                        apex_point,
                        left_endpoint,
                        right_endpoint,
                        0.9,
                        f"Pre-threshold area chevron {runway_name} {end_desig} {chevron_no}",
                    )
                    if geom and pre_area_clip:
                        geom = geom.intersection(pre_area_clip)
                        if geom and not geom.isEmpty() and not geom.isGeosValid():
                            geom = geom.makeValid()
                    if geom:
                        generated.append(
                            (
                                "DetailedPreThresholdAreaMarking",
                                geom,
                                self._detail_marking_attrs(
                                    runway_name,
                                    end_desig,
                                    "Pre-Threshold Area",
                                    "Chevron",
                                    math.hypot(
                                        left_endpoint.x() - apex_point.x(),
                                        left_endpoint.y() - apex_point.y(),
                                    ),
                                    0.9,
                                    "MOS 8.16(1); MOS 8.16(2)",
                                    stripe_no=chevron_no,
                                    offset_m=apex_offset,
                                    spacing_m=30.0,
                                    mandatory=True,
                                    notes=(
                                        "Single generated yellow chevron polygon; "
                                        "first chevron is clipped at the runway end marking; "
                                        "line ends target <= 7.5 m from runway edges where width permits."
                                    ),
                                ),
                            )
                        )
                    apex_offset += 30.0
                    chevron_no += 1
            elif pre_area_len > 1e-6:
                skipped.append("Pre-threshold area markings: area length is less than 30 m.")

        # One centreline stripe set for the whole runway, measured primary to
        # reciprocal, with the last stripe truncated if needed.
        designation_start = self._runway_designation_start_offset()
        primary_protect = designation_start + self._runway_designation_length(primary_desig) + 12.0
        reciprocal_protect = designation_start + self._runway_designation_length(reciprocal_desig) + 12.0
        centreline_end = runway_length - reciprocal_protect
        offset = primary_protect
        stripe_no = 1
        while offset < centreline_end - 1e-6:
            stripe_len = min(30.0, centreline_end - offset)
            if stripe_len <= 1.0:
                break
            geom = self._create_runway_marking_rectangle(
                thr_point,
                rwy_params["azimuth_p_r"],
                offset,
                stripe_len,
                0.0,
                centreline_width,
                f"Centreline stripe {runway_name} {stripe_no}",
            )
            if geom:
                generated.append(
                    (
                        "DetailedCentrelineMarking",
                        geom,
                        self._detail_marking_attrs(
                            runway_name,
                            "",
                            "Centreline",
                            "Stripe",
                            stripe_len,
                            centreline_width,
                            "MOS 8.19",
                            stripe_no=stripe_no,
                            offset_m=offset,
                            spacing_m=20.0,
                            mandatory=True,
                            notes=("Single whole-runway set; final reciprocal-end stripe may be truncated."),
                        ),
                    )
                )
            stripe_no += 1
            offset += 50.0
        if stripe_no > 1:
            whole_runway_mandatory.append("Centreline markings")
        else:
            for qa in qa_records.values():
                qa["skipped"].append("Centreline markings: runway too short after designation clearances.")

        side_stripe_count = 0
        if surface_markings_applicable:
            # Side stripes between runway thresholds. Intersecting runway clipping is
            # applied later as a cross-runway post-processing pass.
            for side_name, lateral_center in (
                ("L", -runway_width / 2.0 + centreline_width / 2.0),
                ("R", runway_width / 2.0 - centreline_width / 2.0),
            ):
                geom = self._create_runway_marking_rectangle(
                    thr_point,
                    rwy_params["azimuth_p_r"],
                    0.0,
                    runway_length,
                    lateral_center,
                    centreline_width,
                    f"Side stripe {runway_name} {side_name}",
                )
                if geom:
                    generated.append(
                        (
                            "DetailedSideStripeMarking",
                            geom,
                            self._detail_marking_attrs(
                                runway_name,
                                "",
                                "Side Stripe",
                                "Continuous",
                                runway_length,
                                centreline_width,
                                "MOS 8.21; MOS 8.15",
                                side=side_name,
                                offset_m=0.0,
                                mandatory=True,
                                notes=(
                                    self._surface_trigger_note("MOS 8.21", runway_data)
                                    + " Taxiway breaks out of scope; intersecting runway pavement is clipped after generation."
                                ),
                            ),
                        )
                    )
                    side_stripe_count += 1
        else:
            for qa in qa_records.values():
                qa["skipped"].append("Side-stripe markings: MOS 8.21 sealed-surface trigger not met.")

        if side_stripe_count:
            whole_runway_mandatory.append("Side-stripe markings")
        elif surface_markings_applicable:
            for qa in qa_records.values():
                qa["skipped"].append("Side-stripe markings: geometry generation failed.")

        if surface_markings_applicable:
            all_runways = runway_data.get("_all_runways", [])
            try:
                runway_code_num = int(float(runway_data.get("arc_num") or 0))
            except (TypeError, ValueError):
                runway_code_num = 0
            for (
                end_desig,
                origin,
                azimuth,
                runway_type,
                _pre_area_start,
                _pre_area_outward_azimuth,
                _pre_area_len,
                _displaced_len,
                landing_available,
                lahso_applied,
            ) in end_specs:
                if not (landing_available and lahso_applied):
                    continue
                rule = self._runway_holding_position_rule(runway_code_num, runway_type)
                if rule is None:
                    qa_records[end_desig]["skipped"].append(
                        "Runway holding position markings: no supported Table 6.56(1) distance "
                        "for this runway code/type combination."
                    )
                    continue
                distance_m, _rule_ref = rule
                intersecting_count = 0
                generated_holding_position = False
                for other_rwy in all_runways:
                    if other_rwy is runway_data:
                        continue
                    other_thr = other_rwy.get("thr_point")
                    other_rec = other_rwy.get("rec_thr_point")
                    if other_thr is None or other_rec is None:
                        continue
                    crossing_point = self._line_segment_intersection_point(
                        thr_point if end_desig == primary_desig else rec_thr_point,
                        rec_thr_point if end_desig == primary_desig else thr_point,
                        other_thr,
                        other_rec,
                    )
                    if crossing_point is None:
                        continue
                    intersecting_count += 1
                    distance_to_crossing = math.hypot(
                        crossing_point.x() - origin.x(),
                        crossing_point.y() - origin.y(),
                    )
                    if distance_to_crossing <= distance_m + 1e-6:
                        qa_records[end_desig]["skipped"].append(
                            "Runway holding position markings: intersecting runway centreline is "
                            "inside the minimum Table 6.56(1) distance."
                        )
                        continue
                    start_offset_m = max(0.0, distance_to_crossing - distance_m)
                    holding_position_features = self._build_runway_holding_position_pattern(
                        origin,
                        azimuth,
                        runway_width,
                        start_offset_m,
                        runway_name,
                        end_desig,
                        other_rwy.get("short_name", f"RWY_{other_rwy.get('original_index', '?')}"),
                        distance_m,
                    )
                    for element_type, geometry, attributes in holding_position_features:
                        generated.append((element_type, geometry, attributes))
                        generated_holding_position = True
                if generated_holding_position:
                    whole_runway_mandatory.append("Runway holding position markings")
                elif intersecting_count:
                    qa_records[end_desig]["skipped"].append(
                        "Runway holding position markings: intersecting runway found, but no valid "
                        "Table 6.56(1) placement could be generated."
                    )
                else:
                    qa_records[end_desig]["skipped"].append(
                        "Runway holding position markings: no intersecting runway centreline found."
                    )

        self._append_marking_qa_records(
            generated,
            runway_name,
            qa_records,
            whole_runway_mandatory,
            whole_runway_optional,
        )
        return generated

    def generate_physical_geometry(self, runway_data: dict) -> Optional[List[Tuple[str, QgsGeometry, dict]]]:
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
        log_name = runway_name if runway_name != "RWY" else f"RWY_{runway_data.get('original_index', '?')}"

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
                        physical_refs = self.get_active_ruleset().physical_refs()
                        pavement_ref = physical_refs.get("pavement", "MOS 6.2.3")
                        # Use correct field names: 'rwy', 'desc', 'ref_mos'
                        attributes = {
                            "rwy": runway_name,
                            "desc": "Runway Pavement",
                            "surf_cat": runway_data.get("surface_category") or "",
                            "surf_mat": runway_data.get("surface_material") or "",
                            "wid_m": runway_width,
                            "len_m": round(landing_length, 3),
                            "ref_mos": pavement_ref,
                        }
                        generated_elements.append(("rwy", landing_pavement_geom, attributes))
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
            primary_desig = runway_name.split("/")[0] if "/" in runway_name else "Primary"
            reciprocal_desig = runway_name.split("/")[1] if "/" in runway_name else "Reciprocal"

            if disp_thr_1 > 1e-6:
                try:
                    start_point = phys_p_start
                    end_point = thr_point
                    p_start_l = start_point.project(half_width, rwy_params["azimuth_perp_l"])
                    p_start_r = start_point.project(half_width, rwy_params["azimuth_perp_r"])
                    p_end_l = end_point.project(half_width, rwy_params["azimuth_perp_l"])
                    p_end_r = end_point.project(half_width, rwy_params["azimuth_perp_r"])
                    if all([p_start_l, p_start_r, p_end_l, p_end_r]):
                        geom = self._create_polygon_from_corners(
                            [p_start_l, p_start_r, p_end_r, p_end_l],
                            f"Pre-Threshold {primary_desig}",
                        )
                        if geom:
                            physical_refs = self.get_active_ruleset().physical_refs()
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
                            pre_threshold_features.append(("PreThresholdRunway", geom, attributes))
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
                    r_start_l = start_point.project(half_width, rwy_params["azimuth_perp_l"])
                    r_start_r = start_point.project(half_width, rwy_params["azimuth_perp_r"])
                    r_end_l = end_point.project(half_width, rwy_params["azimuth_perp_l"])
                    r_end_r = end_point.project(half_width, rwy_params["azimuth_perp_r"])
                    if all([r_start_l, r_start_r, r_end_l, r_end_r]):
                        geom = self._create_polygon_from_corners(
                            [r_start_l, r_start_r, r_end_r, r_end_l],
                            f"Pre-Threshold {reciprocal_desig}",
                        )
                        if geom:
                            physical_refs = self.get_active_ruleset().physical_refs()
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
                            pre_threshold_features.append(("PreThresholdRunway", geom, attributes))
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
            primary_desig = runway_name.split("/")[0] if "/" in runway_name else "Primary"
            reciprocal_desig = runway_name.split("/")[1] if "/" in runway_name else "Reciprocal"

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
                        pre_threshold_area_features.append(("PreThresholdArea", geom, attributes))
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
                        pre_threshold_area_features.append(("PreThresholdArea", geom, attributes))
                except Exception as e:
                    QgsMessageLog.logMessage(
                        f"Warning: Error generating Pre-Threshold Area {reciprocal_desig}: {e}",
                        plugin_tag,
                        level=Qgis.Warning,
                    )

            generated_elements.extend(pre_threshold_area_features)

        # --- 2. Runway Shoulders ---
        if shoulder_width is not None and shoulder_width > 0 and runway_width is not None and runway_width > 0:
            try:
                half_width = runway_width / 2.0
                phys_start_l = phys_p_start.project(half_width, rwy_params["azimuth_perp_l"])
                phys_start_r = phys_p_start.project(half_width, rwy_params["azimuth_perp_r"])
                phys_end_l = phys_p_end.project(half_width, rwy_params["azimuth_perp_l"])
                phys_end_r = phys_p_end.project(half_width, rwy_params["azimuth_perp_r"])
                if not all([phys_start_l, phys_start_r, phys_end_l, phys_end_r]):
                    raise ValueError("Failed to calculate physical pavement corners for shoulders.")

                outer_start_l = phys_start_l.project(shoulder_width, rwy_params["azimuth_perp_l"])
                outer_start_r = phys_start_r.project(shoulder_width, rwy_params["azimuth_perp_r"])
                outer_end_l = phys_end_l.project(shoulder_width, rwy_params["azimuth_perp_l"])
                outer_end_r = phys_end_r.project(shoulder_width, rwy_params["azimuth_perp_r"])

                physical_refs = self.get_active_ruleset().physical_refs()
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
                    left_shoulder_poly = self._create_polygon_from_corners(left_corners, f"Left Shoulder {log_name}")
                    if left_shoulder_poly:
                        generated_elements.append(("Shoulder", left_shoulder_poly, shoulder_attrs.copy()))
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
                    right_shoulder_poly = self._create_polygon_from_corners(right_corners, f"Right Shoulder {log_name}")
                    if right_shoulder_poly:
                        generated_elements.append(("Shoulder", right_shoulder_poly, shoulder_attrs.copy()))
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
            ruleset = self.get_active_ruleset()
            type1_abbr = ruleset.classify_runway_type(runway_data.get("type1"))
            runway_width_for_strip = runway_data.get("width")

            strip_dims = ruleset.strip_parameters(arc_num, type1_abbr, runway_width_for_strip)
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
                strip_dims.get(dim) is not None for dim in ["overall_width", "graded_width", "extension_length"]
            ):
                extension = strip_dims["extension_length"]
                graded_width = strip_dims["graded_width"]
                overall_width = strip_dims["overall_width"]
                graded_half_width = graded_width / 2.0
                overall_half_width = overall_width / 2.0
                stopway_primary_end = self._non_negative_float(runway_data.get("stopway1_len"), 0.0)
                stopway_reciprocal_end = self._non_negative_float(runway_data.get("stopway2_len"), 0.0)
                primary_strip_extension = extension + stopway_primary_end
                reciprocal_strip_extension = extension + stopway_reciprocal_end

                strip_end_center_p = phys_p_start.project(primary_strip_extension, rwy_params["azimuth_r_p"])
                strip_end_center_r = phys_p_end.project(reciprocal_strip_extension, rwy_params["azimuth_p_r"])

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
                        graded_ref = self._join_policy_refs(
                            self._policy_ref(
                                strip_dims,
                                "graded_width_ref",
                                "mos_graded_width_ref",
                                "easa_graded_width_ref",
                            ),
                            self._policy_ref(
                                strip_dims,
                                "extension_length_ref",
                                "mos_extension_length_ref",
                                "easa_extension_length_ref",
                            ),
                        )
                        # Use correct field names: 'rwy', 'desc', 'ref_mos'
                        graded_attrs = {
                            "rwy": runway_name,
                            "desc": "Graded Strip",
                            "wid_m": graded_width,
                            "len_m": round(strip_length, 3),
                            "ref_mos": graded_ref,
                        }
                        generated_elements.append(("GradedStrip", graded_strip_geom, graded_attrs))

                    overall_strip_geom = self._create_runway_aligned_rectangle(
                        strip_end_center_p,
                        strip_end_center_r,
                        0.0,
                        overall_half_width,
                        f"Overall Strip {log_name}",
                    )
                    if overall_strip_geom:
                        overall_ref = self._join_policy_refs(
                            self._policy_ref(
                                strip_dims,
                                "overall_width_ref",
                                "mos_overall_width_ref",
                                "easa_overall_width_ref",
                            ),
                            self._policy_ref(
                                strip_dims,
                                "extension_length_ref",
                                "mos_extension_length_ref",
                                "easa_extension_length_ref",
                            ),
                        )
                        # Use correct field names: 'rwy', 'desc', 'ref_mos'
                        overall_attrs = {
                            "rwy": runway_name,
                            "desc": "Overall Strip",
                            "wid_m": overall_width,
                            "len_m": round(strip_length, 3),
                            "ref_mos": overall_ref,
                        }
                        generated_elements.append(("OverallStrip", overall_strip_geom, overall_attrs))

                    flyover_width = (overall_width - graded_width) / 2.0
                    if flyover_width > 1e-6:
                        flyover_ref = self._join_policy_refs(
                            self._policy_ref(
                                strip_dims,
                                "overall_width_ref",
                                "mos_overall_width_ref",
                                "easa_overall_width_ref",
                            ),
                            self._policy_ref(
                                strip_dims,
                                "graded_width_ref",
                                "mos_graded_width_ref",
                                "easa_graded_width_ref",
                            ),
                            self._policy_ref(
                                strip_dims,
                                "extension_length_ref",
                                "mos_extension_length_ref",
                                "easa_extension_length_ref",
                            ),
                        )
                        flyover_attrs = {
                            "rwy": runway_name,
                            "desc": "Flyover Strip Area",
                            "wid_m": flyover_width,
                            "len_m": round(strip_length, 3),
                            "ref_mos": flyover_ref,
                        }

                        left_inner_p = strip_end_center_p.project(graded_half_width, rwy_params["azimuth_perp_l"])
                        left_outer_p = strip_end_center_p.project(overall_half_width, rwy_params["azimuth_perp_l"])
                        left_outer_r = strip_end_center_r.project(overall_half_width, rwy_params["azimuth_perp_l"])
                        left_inner_r = strip_end_center_r.project(graded_half_width, rwy_params["azimuth_perp_l"])
                        if all([left_inner_p, left_outer_p, left_outer_r, left_inner_r]):
                            left_flyover_geom = self._create_polygon_from_corners(
                                [
                                    left_inner_p,
                                    left_outer_p,
                                    left_outer_r,
                                    left_inner_r,
                                ],
                                f"Left Flyover Strip {log_name}",
                            )
                            if left_flyover_geom:
                                generated_elements.append(
                                    (
                                        "FlyoverStrip",
                                        left_flyover_geom,
                                        flyover_attrs.copy(),
                                    )
                                )

                        right_inner_p = strip_end_center_p.project(graded_half_width, rwy_params["azimuth_perp_r"])
                        right_inner_r = strip_end_center_r.project(graded_half_width, rwy_params["azimuth_perp_r"])
                        right_outer_r = strip_end_center_r.project(overall_half_width, rwy_params["azimuth_perp_r"])
                        right_outer_p = strip_end_center_p.project(overall_half_width, rwy_params["azimuth_perp_r"])
                        if all(
                            [
                                right_inner_p,
                                right_inner_r,
                                right_outer_r,
                                right_outer_p,
                            ]
                        ):
                            right_flyover_geom = self._create_polygon_from_corners(
                                [
                                    right_inner_p,
                                    right_inner_r,
                                    right_outer_r,
                                    right_outer_p,
                                ],
                                f"Right Flyover Strip {log_name}",
                            )
                            if right_flyover_geom:
                                generated_elements.append(
                                    (
                                        "FlyoverStrip",
                                        right_flyover_geom,
                                        flyover_attrs.copy(),
                                    )
                                )
                    elif overall_width <= graded_width:
                        QgsMessageLog.logMessage(
                            f"Info: Skipping FlyoverStrip for {log_name}: Overall strip width is not greater than graded strip width.",
                            plugin_tag,
                            level=Qgis.Info,
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
            ruleset = self.get_active_ruleset()
            type1_abbr = ruleset.classify_runway_type(runway_data.get("type1"))
            type2_abbr = ruleset.classify_runway_type(runway_data.get("type2"))
            resa_dims = ruleset.resa_parameters(int(runway_data.get("arc_num", 0)), type1_abbr, type2_abbr)

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

                primary_desig = runway_name.split("/")[0] if "/" in runway_name else "Primary"
                reciprocal_desig = runway_name.split("/")[1] if "/" in runway_name else "Reciprocal"
                resa_ref = self._join_policy_refs(
                    self._policy_ref(
                        resa_dims,
                        "applicability_ref",
                        "mos_applicability_ref",
                        "easa_applicability_ref",
                    ),
                    self._policy_ref(
                        resa_dims,
                        "width_ref",
                        "mos_width_ref",
                        "easa_width_ref",
                    ),
                    self._policy_ref(
                        resa_dims,
                        "length_ref",
                        "mos_length_ref",
                        "easa_length_ref",
                    ),
                )
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

        # --- 5. Stopways and clearways ---
        try:
            primary_desig = runway_name.split("/")[0] if "/" in runway_name else "Primary"
            reciprocal_desig = runway_name.split("/")[1] if "/" in runway_name else "Reciprocal"
            clearway_specs = self._calculate_effective_clearway_specs(
                runway_data,
                physical_length,
            )

            stopway_specs = []
            if runway_width is not None and runway_width > 0:
                stopway_specs = [
                    (
                        "Stopway",
                        "Stopway",
                        self._non_negative_float(runway_data.get("stopway1_len"), 0.0),
                        runway_width,
                        phys_p_start,
                        rwy_params["azimuth_r_p"],
                        primary_desig,
                        "MOS 6.25",
                    ),
                    (
                        "Stopway",
                        "Stopway",
                        self._non_negative_float(runway_data.get("stopway2_len"), 0.0),
                        runway_width,
                        phys_p_end,
                        rwy_params["azimuth_p_r"],
                        reciprocal_desig,
                        "MOS 6.25",
                    ),
                ]
            elif self._non_negative_float(runway_data.get("stopway1_len"), 0.0) > 1e-6 or self._non_negative_float(
                runway_data.get("stopway2_len"), 0.0
            ) > 1e-6:
                QgsMessageLog.logMessage(
                    f"Info: Skipping stopway geometry for {log_name}: Runway width missing.",
                    plugin_tag,
                    level=Qgis.Info,
                )

            clearway_area_specs = [
                (
                    "Clearway",
                    "Clearway",
                    clearway_specs["primary"]["length_m"],
                    clearway_specs["primary"]["width_m"],
                    phys_p_start,
                    rwy_params["azimuth_r_p"],
                    primary_desig,
                    clearway_specs["primary"]["ref_mos"],
                ),
                (
                    "Clearway",
                    "Clearway",
                    clearway_specs["reciprocal"]["length_m"],
                    clearway_specs["reciprocal"]["width_m"],
                    phys_p_end,
                    rwy_params["azimuth_p_r"],
                    reciprocal_desig,
                    clearway_specs["reciprocal"]["ref_mos"],
                ),
            ]

            for (
                element_type,
                desc,
                length_m,
                width_m,
                start_point,
                outward_azimuth,
                end_desig,
                ref_mos,
            ) in stopway_specs + clearway_area_specs:
                if length_m <= 1e-6:
                    continue
                if width_m <= 1e-6:
                    QgsMessageLog.logMessage(
                        f"Info: Skipping {desc.lower()} geometry for {log_name} {end_desig}: width unavailable.",
                        plugin_tag,
                        level=Qgis.Info,
                    )
                    continue
                geom = self._create_rectangle_from_start(
                    start_point,
                    outward_azimuth,
                    length_m,
                    width_m / 2.0,
                    f"{desc} {end_desig}",
                )
                if geom:
                    generated_elements.append(
                        (
                            element_type,
                            geom,
                            {
                                "rwy": runway_name,
                                "desc": f"{desc} ({end_desig})",
                                "surf_cat": runway_data.get("surface_category") or "",
                                "surf_mat": runway_data.get("surface_material") or "",
                                "len_m": round(length_m, 3),
                                "wid_m": round(width_m, 3),
                                "ref_mos": ref_mos,
                                "end_desig": end_desig,
                            },
                        )
                    )
        except Exception as e_diag:
            QgsMessageLog.logMessage(
                f"Warning: Error generating stopway/clearway geometry for {log_name}: {e_diag}",
                plugin_tag,
                level=Qgis.Warning,
            )

        QgsMessageLog.logMessage(
            f"Finished physical geometry processing for {log_name}. Generated {len(generated_elements)} element features.",
            plugin_tag,
            level=Qgis.Success,
        )

        return generated_elements if generated_elements else None
