# -*- coding: utf-8 -*-
"""Specialised safeguarding surfaces such as RAOA and taxiway separation."""

import math
import traceback
from typing import List, Optional, Tuple

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
)

from .constants import RAOA_MOS_REF_VAL, MOS_REF_TAXIWAY_SEPARATION

PLUGIN_TAG = "SafeguardingBuilder"


class SpecialisedSurfacesMixin:
    def _get_raoa_fields(self) -> QgsFields:
        """Returns the QgsFields definition for the RAOA layer."""
        fields = QgsFields(
            [
                QgsField("rwy", QVariant.String, self.tr("rwy"), 50),
                QgsField("desc", QVariant.String, self.tr("desc"), 50),
                QgsField("end_desig", QVariant.String, self.tr("end_desig"), 10),
                QgsField("len_m", QVariant.Double, self.tr("len_m"), 10, 2),
                QgsField("wid_m", QVariant.Double, self.tr("wid_m"), 10, 2),
                QgsField("ref_mos", QVariant.String, self.tr("MOS Reference"), 100),
            ]
        )
        return fields

    def process_raoa(self, runway_data: dict, layer_group: QgsLayerTreeGroup) -> bool:
        """Generates RAOA if applicable (Precision Approach runways)."""
        plugin_tag = PLUGIN_TAG
        runway_name = runway_data.get("short_name", f"RWY_{runway_data.get('original_index', '?')}")
        thr_point = runway_data.get("thr_point")
        rec_thr_point = runway_data.get("rec_thr_point")
        type1_str = runway_data.get("type1", "")
        type2_str = runway_data.get("type2", "")

        if thr_point is None or rec_thr_point is None or layer_group is None:
            return False  # Basic check
        rwy_params = self._get_runway_parameters(thr_point, rec_thr_point)
        if rwy_params is None:
            return False  # Helper logs error

        RAOA_LENGTH = 300.0
        RAOA_WIDTH = 120.0
        RAOA_HALF_WIDTH = RAOA_WIDTH / 2.0
        APPLICABLE_TYPES = ["Precision Approach CAT I", "Precision Approach CAT II/III"]
        features_to_add: List[QgsFeature] = []
        primary_desig, reciprocal_desig = runway_name.split("/") if "/" in runway_name else ("THR1", "THR2")

        # Check Primary End
        if type1_str in APPLICABLE_TYPES:
            try:
                outward_azimuth = rwy_params["azimuth_r_p"]
                geom = self._create_rectangle_from_start(
                    thr_point,
                    outward_azimuth,
                    RAOA_LENGTH,
                    RAOA_HALF_WIDTH,
                    f"RAOA {primary_desig}",
                )
                if geom:
                    fields = self._get_raoa_fields()
                    feature = QgsFeature(fields)
                    feature.setGeometry(geom)
                    attributes = [
                        runway_name,
                        f"RAOA {primary_desig}",
                        primary_desig,
                        RAOA_LENGTH,
                        RAOA_WIDTH,
                        RAOA_MOS_REF_VAL,
                    ]
                    feature.setAttributes(attributes)
                    features_to_add.append(feature)
            except Exception as e:
                QgsMessageLog.logMessage(
                    f"Warning: Error generating RAOA for {primary_desig}: {e}",
                    plugin_tag,
                    level=Qgis.Warning,
                )

        # Check Reciprocal End
        if type2_str in APPLICABLE_TYPES:
            try:
                outward_azimuth = rwy_params["azimuth_p_r"]
                geom = self._create_rectangle_from_start(
                    rec_thr_point,
                    outward_azimuth,
                    RAOA_LENGTH,
                    RAOA_HALF_WIDTH,
                    f"RAOA {reciprocal_desig}",
                )
                if geom:
                    fields = self._get_raoa_fields()
                    feature = QgsFeature(fields)
                    feature.setGeometry(geom)
                    attributes = [
                        runway_name,
                        f"RAOA {reciprocal_desig}",
                        reciprocal_desig,
                        RAOA_LENGTH,
                        RAOA_WIDTH,
                        RAOA_MOS_REF_VAL,
                    ]
                    feature.setAttributes(attributes)
                    features_to_add.append(feature)
            except Exception as e:
                QgsMessageLog.logMessage(
                    f"Warning: Error generating RAOA for {reciprocal_desig}: {e}",
                    plugin_tag,
                    level=Qgis.Warning,
                )

        # Create Layer if Features Exist
        if features_to_add:
            layer_name_display = f"RAOA {runway_name}"
            internal_name_base = f"RAOA_{runway_name.replace('/', '_')}"
            fields = self._get_raoa_fields()
            style_key = "RAOA"  # Ensure this matches style_map
            layer_created = self._create_and_add_layer(
                "Polygon",
                internal_name_base,
                layer_name_display,
                fields,
                features_to_add,
                layer_group,
                style_key,
            )
            # No final success log needed here, helper logs errors.
            return layer_created is not None
        else:
            # Keep this Info log - useful to know why layer wasn't created
            QgsMessageLog.logMessage(
                f"RAOA not applicable or failed for {runway_name}",
                plugin_tag,
                level=Qgis.Info,
            )
            return False

    def _get_taxiway_separation_fields(self) -> QgsFields:
        """Returns the QgsFields definition for the Taxiway Separation layer."""
        fields = QgsFields(
            [
                QgsField("rwy", QVariant.String, self.tr("Runway Name"), 50),
                QgsField("desc", QVariant.String, self.tr("desc"), 100),
                QgsField("offset_m", QVariant.Double, self.tr("offset_m"), 10, 2),
                QgsField("ref_mos", QVariant.String, self.tr("MOS Reference"), 100),
                QgsField("appr_type", QVariant.String, self.tr("appr_type"), 50),
                QgsField("arc_num", QVariant.String, self.tr("arc_num"), 5),
                QgsField("arc_let", QVariant.String, self.tr("arc_let"), 5),
                QgsField("side", QVariant.String, self.tr("Side (L/R)"), 5),
            ]
        )
        return fields

    def _get_parallel_runway_separation_fields(self) -> QgsFields:
        """Returns the QgsFields definition for the Parallel Runway Separation layer."""
        fields = QgsFields(
            [
                QgsField("rwy_pair", QVariant.String, self.tr("Runway Pair"), 100),
                QgsField("rwy_ref", QVariant.String, self.tr("Reference Runway"), 50),
                QgsField("rwy_other", QVariant.String, self.tr("Other Runway"), 50),
                QgsField("operation", QVariant.String, self.tr("Operation"), 50),
                QgsField("label_txt", QVariant.String, self.tr("Label"), 80),
                QgsField("distance_m", QVariant.Double, self.tr("Distance (m)"), 10, 2),
                QgsField("base_dist_m", QVariant.Double, self.tr("Base Distance (m)"), 10, 2),
                QgsField("stagger_m", QVariant.Double, self.tr("Arrival Threshold Stagger (m)"), 10, 2),
                QgsField("adjust_m", QVariant.Double, self.tr("Stagger Adjustment (m)"), 10, 2),
                QgsField("ref_mos", QVariant.String, self.tr("Reference"), 100),
                QgsField("line_style", QVariant.String, self.tr("Line Style"), 20),
                QgsField("side", QVariant.String, self.tr("Side"), 10),
            ]
        )
        return fields

    def _runway_midpoint(self, runway_data: dict) -> Optional[QgsPointXY]:
        thr_point = runway_data.get("thr_point")
        rec_thr_point = runway_data.get("rec_thr_point")
        if thr_point is None or rec_thr_point is None:
            return None
        return QgsPointXY((thr_point.x() + rec_thr_point.x()) / 2.0, (thr_point.y() + rec_thr_point.y()) / 2.0)

    def _parallel_runway_axis_diff(self, azimuth_a: float, azimuth_b: float) -> float:
        diff = abs((azimuth_a - azimuth_b + 180.0) % 360.0 - 180.0)
        return min(diff, 180.0 - diff)

    def _side_toward_other_runway(
        self,
        ref_midpoint: QgsPointXY,
        other_midpoint: QgsPointXY,
        ref_params: dict,
    ) -> Tuple[str, float]:
        vector_x = other_midpoint.x() - ref_midpoint.x()
        vector_y = other_midpoint.y() - ref_midpoint.y()
        left_azimuth = math.radians(ref_params["azimuth_perp_l"])
        left_x = math.sin(left_azimuth)
        left_y = math.cos(left_azimuth)
        if vector_x * left_x + vector_y * left_y >= 0:
            return "L", ref_params["azimuth_perp_l"]
        return "R", ref_params["azimuth_perp_r"]

    def _parallel_threshold_stagger(self, arrival_runway: dict, other_runway: dict) -> Optional[float]:
        arrival_thr = arrival_runway.get("thr_point")
        arrival_rec = arrival_runway.get("rec_thr_point")
        other_thr = other_runway.get("thr_point")
        if arrival_thr is None or arrival_rec is None or other_thr is None:
            return None
        params = self._get_runway_parameters(arrival_thr, arrival_rec)
        if not params:
            return None
        axis_azimuth = math.radians(params["azimuth_r_p"])
        axis_x = math.sin(axis_azimuth)
        axis_y = math.cos(axis_azimuth)
        return (arrival_thr.x() - other_thr.x()) * axis_x + (arrival_thr.y() - other_thr.y()) * axis_y

    def _parallel_runway_operation_specs(self, runway_a: dict, runway_b: dict) -> List[dict]:
        ruleset = self.get_active_ruleset()
        try:
            arc_num_a = int(runway_a.get("arc_num"))
            arc_num_b = int(runway_b.get("arc_num"))
        except (TypeError, ValueError):
            return []

        type_a = self._governing_runway_type(runway_a)
        type_b = self._governing_runway_type(runway_b)
        type_a_abbr = ruleset.classify_runway_type(type_a)
        type_b_abbr = ruleset.classify_runway_type(type_b)
        both_non_instrument = type_a_abbr == "NI" and type_b_abbr == "NI"
        both_instrument = type_a_abbr != "NI" and type_b_abbr != "NI"

        if both_non_instrument:
            return [
                {
                    "operation_type": "simultaneous",
                    "label_prefix": "Simultaneous",
                    "arrival": None,
                    "dashed": False,
                    "stagger_m": None,
                }
            ]
        if not both_instrument:
            return []

        specs = [
            {
                "operation_type": "independent_parallel_approaches",
                "label_prefix": "Independent approaches",
                "arrival": None,
                "dashed": False,
                "stagger_m": None,
            },
            {
                "operation_type": "dependent_parallel_approaches",
                "label_prefix": "Dependent approaches",
                "arrival": None,
                "dashed": False,
                "stagger_m": None,
            },
            {
                "operation_type": "independent_parallel_departures",
                "label_prefix": "Independent departures",
                "arrival": None,
                "dashed": False,
                "stagger_m": None,
            },
        ]
        for arrival, other in [(runway_a, runway_b), (runway_b, runway_a)]:
            arrival_name = arrival.get("short_name", "RWY")
            specs.append(
                {
                    "operation_type": "segregated_parallel_operations",
                    "label_prefix": f"Segregated ops {arrival_name} arrival",
                    "arrival": arrival,
                    "dashed": True,
                    "stagger_m": self._parallel_threshold_stagger(arrival, other),
                }
            )
        return specs

    def _governing_runway_type(self, runway_data: dict) -> str:
        type_order = [
            "",
            "Non-Instrument (NI)",
            "Non-Precision Approach (NPA)",
            "Precision Approach CAT I",
            "Precision Approach CAT II/III",
        ]
        type1_str = runway_data.get("type1", "")
        type2_str = runway_data.get("type2", "")
        idx1 = type_order.index(type1_str) if type1_str in type_order else 1
        idx2 = type_order.index(type2_str) if type2_str in type_order else 1
        return type_order[max(idx1, idx2)]

    def process_parallel_runway_separation(self, runway_data_list: List[dict], layer_group: QgsLayerTreeGroup) -> bool:
        """Generate minimum parallel runway separation guide lines."""
        plugin_tag = PLUGIN_TAG
        if layer_group is None or not runway_data_list or len(runway_data_list) < 2:
            return False

        features_to_add: List[QgsFeature] = []
        fields = self._get_parallel_runway_separation_fields()
        ruleset = self.get_active_ruleset()

        for idx_a, runway_a in enumerate(runway_data_list):
            for runway_b in runway_data_list[idx_a + 1 :]:
                name_a = runway_a.get("short_name", f"RWY_{runway_a.get('original_index', '?')}")
                name_b = runway_b.get("short_name", f"RWY_{runway_b.get('original_index', '?')}")
                thr_a = runway_a.get("thr_point")
                rec_a = runway_a.get("rec_thr_point")
                thr_b = runway_b.get("thr_point")
                rec_b = runway_b.get("rec_thr_point")
                if thr_a is None or rec_a is None or thr_b is None or rec_b is None:
                    continue

                params_a = self._get_runway_parameters(thr_a, rec_a)
                params_b = self._get_runway_parameters(thr_b, rec_b)
                mid_a = self._runway_midpoint(runway_a)
                mid_b = self._runway_midpoint(runway_b)
                if not params_a or not params_b or mid_a is None or mid_b is None:
                    continue

                if self._parallel_runway_axis_diff(params_a["azimuth_p_r"], params_b["azimuth_p_r"]) > 15.0:
                    continue

                try:
                    arc_num_a = int(runway_a.get("arc_num"))
                    arc_num_b = int(runway_b.get("arc_num"))
                except (TypeError, ValueError):
                    continue

                line_length = max(params_a.get("length", 0.0), params_b.get("length", 0.0)) * 1.5
                if line_length <= 0:
                    continue
                extension = (line_length - params_a["length"]) / 2.0
                start_a = thr_a.project(extension, params_a["azimuth_r_p"])
                end_a = start_a.project(line_length, params_a["azimuth_p_r"]) if start_a else None
                extension_b = (line_length - params_b["length"]) / 2.0
                start_b = thr_b.project(extension_b, params_b["azimuth_r_p"])
                end_b = start_b.project(line_length, params_b["azimuth_p_r"]) if start_b else None
                if not all([start_a, end_a, start_b, end_b]):
                    continue

                side_a, side_az_a = self._side_toward_other_runway(mid_a, mid_b, params_a)
                side_b, side_az_b = self._side_toward_other_runway(mid_b, mid_a, params_b)

                type_a = self._governing_runway_type(runway_a)
                type_b = self._governing_runway_type(runway_b)
                pair_name = f"{name_a} / {name_b}"

                for spec in self._parallel_runway_operation_specs(runway_a, runway_b):
                    sep = ruleset.parallel_runway_separation(
                        arc_num_a,
                        arc_num_b,
                        type_a,
                        type_b,
                        spec["operation_type"],
                        arrival_threshold_stagger_m=spec.get("stagger_m"),
                    )
                    if not sep:
                        continue
                    distance_m = sep.get("distance_m")
                    if distance_m is None or distance_m <= 0:
                        continue
                    label_txt = f"{spec['label_prefix']} {float(distance_m):.0f} m"
                    line_style = "dashed" if spec.get("dashed") else "solid"

                    for ref_name, other_name, line_start, line_end, side, side_az in [
                        (name_a, name_b, start_a, end_a, side_a, side_az_a),
                        (name_b, name_a, start_b, end_b, side_b, side_az_b),
                    ]:
                        p_start = line_start.project(distance_m, side_az)
                        p_end = line_end.project(distance_m, side_az)
                        if not p_start or not p_end:
                            continue
                        geom = QgsGeometry.fromPolylineXY([p_start, p_end])
                        if geom is None or geom.isEmpty():
                            continue
                        feat = QgsFeature(fields)
                        feat.setGeometry(geom)
                        attr_map = {
                            "rwy_pair": pair_name,
                            "rwy_ref": ref_name,
                            "rwy_other": other_name,
                            "operation": spec["operation_type"],
                            "label_txt": label_txt,
                            "distance_m": distance_m,
                            "base_dist_m": sep.get("base_distance_m", distance_m),
                            "stagger_m": sep.get("threshold_stagger_m"),
                            "adjust_m": sep.get("stagger_adjustment_m"),
                            "ref_mos": sep.get("ref"),
                            "line_style": line_style,
                            "side": side,
                        }
                        for name, value in attr_map.items():
                            field_idx = fields.indexFromName(name)
                            if field_idx != -1:
                                feat.setAttribute(field_idx, value)
                        features_to_add.append(feat)

        if not features_to_add:
            QgsMessageLog.logMessage("Parallel runway separation layer skipped: no applicable runway pairs.", plugin_tag, level=Qgis.Info)
            return False

        layer_created = self._create_and_add_layer(
            "LineString",
            "ParallelRunwaySeparation",
            "Parallel Runway Separation",
            fields,
            features_to_add,
            layer_group,
            "Parallel Runway Separation Line",
        )
        return layer_created is not None

    def process_taxiway_separation(self, runway_data: dict, layer_group: QgsLayerTreeGroup) -> bool:
        """Generates Taxiway Minimum Separation lines."""
        plugin_tag = PLUGIN_TAG
        runway_name = runway_data.get("short_name", f"RWY_{runway_data.get('original_index', '?')}")
        thr_point = runway_data.get("thr_point")
        rec_thr_point = runway_data.get("rec_thr_point")
        arc_num_str = runway_data.get("arc_num")
        arc_let_raw = runway_data.get("arc_let")
        type1_str = runway_data.get("type1", "")
        type2_str = runway_data.get("type2", "")

        # Essential Checks
        if thr_point is None or rec_thr_point is None or layer_group is None or not arc_num_str:
            QgsMessageLog.logMessage(
                f"Taxiway Sep skipped {runway_name}: Missing essential data.",
                plugin_tag,
                level=Qgis.Warning,
            )
            return False
        try:
            arc_num = int(arc_num_str)  # Keep as int for logic, convert to str for attribute
        except (ValueError, TypeError):
            QgsMessageLog.logMessage(
                f"Taxiway Sep skipped {runway_name}: Invalid ARC Number '{arc_num_str}'.",
                plugin_tag,
                level=Qgis.Warning,
            )
            return False

        # Validate ARC Letter
        if not arc_let_raw or not isinstance(arc_let_raw, str) or not arc_let_raw.strip():
            QgsMessageLog.logMessage(
                f"Taxiway Sep skipped {runway_name}: ARC Letter not provided or invalid ('{arc_let_raw}').",
                plugin_tag,
                level=Qgis.Warning,
            )
            return False
        arc_let = arc_let_raw.strip().upper()  # Use cleaned letter

        rwy_params = self._get_runway_parameters(thr_point, rec_thr_point)
        if rwy_params is None or rwy_params.get("length") is None or rwy_params["length"] <= 0:
            QgsMessageLog.logMessage(
                f"Taxiway Sep skipped {runway_name}: Invalid runway parameters or length.",
                plugin_tag,
                level=Qgis.Warning,
            )
            return False

        # Determine Governing Type (keep logic)
        type_order = [
            "",
            "Non-Instrument (NI)",
            "Non-Precision Approach (NPA)",
            "Precision Approach CAT I",
            "Precision Approach CAT II/III",
        ]
        idx1 = type_order.index(type1_str) if type1_str in type_order else 1
        idx2 = type_order.index(type2_str) if type2_str in type_order else 1
        governing_type_str = type_order[max(idx1, idx2)]

        # Get Offset Parameter
        offset_params = self.get_active_ruleset().taxiway_separation_offset(arc_num, arc_let, governing_type_str)
        if not offset_params:
            QgsMessageLog.logMessage(
                f"Skipping Taxiway Sep for {runway_name}: No offset parameters found for classification (ARC={arc_num}, Let='{arc_let}', Type='{governing_type_str}').",
                plugin_tag,
                level=Qgis.Warning,
            )
            return False
        offset_m = offset_params.get("offset_m")
        if offset_m is None or offset_m <= 0:
            QgsMessageLog.logMessage(
                f"Skipping Taxiway Sep for {runway_name}: Invalid offset value ({offset_m}).",
                plugin_tag,
                level=Qgis.Warning,
            )
            return False

        # Calculate Geometry (keep logic)
        runway_length = rwy_params["length"]
        line_length = runway_length * 1.5
        extension = (line_length - runway_length) / 2.0
        line_start_cl = thr_point.project(extension, rwy_params["azimuth_r_p"])
        line_end_cl = line_start_cl.project(line_length, rwy_params["azimuth_p_r"])
        if not line_start_cl or not line_end_cl:
            QgsMessageLog.logMessage(
                f"Failed calc taxiway sep line start/end points for {runway_name}",
                plugin_tag,
                level=Qgis.Warning,
            )
            return False

        features_to_add: List[QgsFeature] = []
        geom_ok = True
        surface_description = f"Minimum Taxiway Separation {runway_name}"
        attr_runway_name = runway_name if runway_name and runway_name.strip() else "N/A"
        attr_surface_description = surface_description if surface_description.strip() else "N/A"
        attr_mos_ref = MOS_REF_TAXIWAY_SEPARATION
        attr_app_type = governing_type_str if governing_type_str and governing_type_str.strip() else "N/A"
        attr_arc_num_str = str(arc_num)
        attr_arc_let = arc_let if arc_let and arc_let.strip() else "N/A"

        # Left Line
        try:
            pt_start_l = line_start_cl.project(offset_m, rwy_params["azimuth_perp_l"])
            pt_end_l = line_end_cl.project(offset_m, rwy_params["azimuth_perp_l"])
            if pt_start_l and pt_end_l:
                geom_l = QgsGeometry.fromPolylineXY([pt_start_l, pt_end_l])
                if geom_l and not geom_l.isEmpty():
                    fields = self._get_taxiway_separation_fields()
                    feat_l = QgsFeature(fields)
                    feat_l.setGeometry(geom_l)

                    attr_map = {
                        "rwy": attr_runway_name,
                        "desc": attr_surface_description,
                        "offset_m": offset_m,
                        "ref_mos": attr_mos_ref,
                        "appr_type": attr_app_type,
                        "arc_num": attr_arc_num_str,
                        "arc_let": attr_arc_let,
                        "side": "L",
                    }
                    # QgsMessageLog.logMessage(f"Taxiway Sep Left Attr Map for {runway_name}: {attr_map}", plugin_tag, level=Qgis.Info)

                    for name, value in attr_map.items():
                        idx = fields.indexFromName(name)
                        if idx != -1:
                            feat_l.setAttribute(idx, value)
                        else:
                            QgsMessageLog.logMessage(
                                f"Warning: Field '{name}' not found in layer for Taxiway Separation (Left Line).",
                                plugin_tag,
                                level=Qgis.Warning,
                            )
                    features_to_add.append(feat_l)
                else:
                    geom_ok = False
            else:
                geom_ok = False
        except Exception as e:
            geom_ok = False
            QgsMessageLog.logMessage(
                f"Warning: Error generating Left Taxi Sep line for {runway_name}: {e}\n{traceback.format_exc()}",
                plugin_tag,
                level=Qgis.Warning,
            )

        # Right Line (similar try-except block and attribute setting)
        try:
            pt_start_r = line_start_cl.project(offset_m, rwy_params["azimuth_perp_r"])
            pt_end_r = line_end_cl.project(offset_m, rwy_params["azimuth_perp_r"])
            if pt_start_r and pt_end_r:
                geom_r = QgsGeometry.fromPolylineXY([pt_start_r, pt_end_r])
                if geom_r and not geom_r.isEmpty():
                    fields = self._get_taxiway_separation_fields()
                    feat_r = QgsFeature(fields)
                    feat_r.setGeometry(geom_r)

                    # Reuse defensively prepared variables from the Left Line section as they are identical for the Right Line
                    attr_map_right = {
                        "rwy": attr_runway_name,
                        "desc": attr_surface_description,
                        "offset_m": offset_m,
                        "ref_mos": attr_mos_ref,
                        "appr_type": attr_app_type,
                        "arc_num": attr_arc_num_str,
                        "arc_let": attr_arc_let,
                        "side": "R",
                    }
                    # QgsMessageLog.logMessage(f"Taxiway Sep Right Attr Map for {runway_name}: {attr_map_right}", plugin_tag, level=Qgis.Info)

                    for name, value in attr_map_right.items():
                        idx = fields.indexFromName(name)
                        if idx != -1:
                            feat_r.setAttribute(idx, value)
                        else:
                            QgsMessageLog.logMessage(
                                f"Warning: Field '{name}' not found in layer for Taxiway Separation (Right Line).",
                                plugin_tag,
                                level=Qgis.Warning,
                            )
                    features_to_add.append(feat_r)
                else:
                    geom_ok = False
            else:
                geom_ok = False
        except Exception as e:
            geom_ok = False
            QgsMessageLog.logMessage(
                f"Warning: Error generating Right Taxi Sep line for {runway_name}: {e}\n{traceback.format_exc()}",
                plugin_tag,
                level=Qgis.Warning,
            )

        if not geom_ok and not features_to_add:  # If geometry failed AND no features were added
            QgsMessageLog.logMessage(
                f"Failed to generate taxiway separation line geometries for {runway_name}",
                plugin_tag,
                level=Qgis.Warning,
            )
            return False

        # Create Layer
        if features_to_add:
            layer_name_display = f"Taxiway Separation {runway_name}"
            internal_name_base = f"TaxiwaySep_{runway_name.replace('/', '_')}"
            fields = self._get_taxiway_separation_fields()
            style_key = "Taxiway Separation Line"
            layer_created = self._create_and_add_layer(
                "LineString",
                internal_name_base,
                layer_name_display,
                fields,
                features_to_add,
                layer_group,
                style_key,
            )
            return layer_created is not None
        else:
            return False
