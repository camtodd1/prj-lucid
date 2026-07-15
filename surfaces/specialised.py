# -*- coding: utf-8 -*-
"""Specialised safeguarding surfaces such as RAOA and taxiway separation."""

import traceback
from typing import List

from qgis.PyQt.QtCore import QVariant  # type: ignore
from qgis.core import (  # type: ignore
    Qgis,
    QgsFeature,
    QgsField,
    QgsFields,
    QgsGeometry,
    QgsLayerTreeGroup,
)

from .constants import RAOA_MOS_REF_VAL, MOS_REF_TAXIWAY_SEPARATION

try:
    from ..core.run_log import QgsMessageLog
except ImportError:
    from core.run_log import QgsMessageLog  # type: ignore

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

    def _get_runway_separation_assessment_fields(self) -> QgsFields:
        """Returns the QgsFields definition for the Parallel Runway Standards layer."""
        fields = QgsFields(
            [
                QgsField("rwy", QVariant.String, self.tr("Runway"), 50),
                QgsField("operation", QVariant.String, self.tr("Operation"), 50),
                QgsField("op_cat", QVariant.String, self.tr("Operation Category"), 50),
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

    def _runway_separation_operation_specs(self, runway_data: dict) -> List[dict]:
        ruleset = self.get_active_ruleset()
        try:
            int(runway_data.get("arc_num"))
        except (TypeError, ValueError):
            return []

        governing_type = self._governing_runway_type(runway_data)
        type_abbr = ruleset.classify_runway_type(governing_type)

        if type_abbr == "NI":
            return [
                {
                    "operation_type": "simultaneous",
                    "label_prefix": "Simultaneous",
                    "category_label": "Simultaneous use",
                    "arrival": None,
                    "dashed": False,
                    "stagger_m": None,
                }
            ]

        specs = [
            {
                "operation_type": "independent_parallel_approaches",
                "label_prefix": "Independent approaches",
                "category_label": "Independent approaches",
                "arrival": None,
                "dashed": False,
                "stagger_m": None,
            },
            {
                "operation_type": "dependent_parallel_approaches",
                "label_prefix": "Dependent approaches",
                "category_label": "Dependent approaches",
                "arrival": None,
                "dashed": False,
                "stagger_m": None,
            },
            {
                "operation_type": "independent_parallel_departures",
                "label_prefix": "Independent departures",
                "category_label": "Independent departures",
                "arrival": None,
                "dashed": False,
                "stagger_m": None,
            },
        ]
        stagger_m = runway_data.get("arrival_threshold_stagger_m")
        specs.append(
            {
                "operation_type": "segregated_parallel_operations",
                "label_prefix": "Segregated ops",
                "category_label": "Segregated operations",
                "arrival": runway_data,
                "dashed": True,
                "stagger_m": stagger_m,
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

    def process_runway_separation_assessment(self, runway_data_list: List[dict], layer_group: QgsLayerTreeGroup) -> bool:
        """Generate what-if runway separation guide lines for every runway."""
        plugin_tag = PLUGIN_TAG
        if layer_group is None or not runway_data_list:
            return False

        features_to_add: List[QgsFeature] = []
        fields = self._get_runway_separation_assessment_fields()
        ruleset = self.get_active_ruleset()

        for runway_data in runway_data_list:
            runway_name = runway_data.get("short_name", f"RWY_{runway_data.get('original_index', '?')}")
            thr_point = runway_data.get("thr_point")
            rec_thr_point = runway_data.get("rec_thr_point")
            if thr_point is None or rec_thr_point is None:
                continue
            params = self._get_runway_parameters(thr_point, rec_thr_point)
            if not params or params.get("length") is None or params["length"] <= 0:
                continue
            try:
                arc_num = int(runway_data.get("arc_num"))
            except (TypeError, ValueError):
                continue

            line_length = params["length"] * 1.5
            extension = (line_length - params["length"]) / 2.0
            line_start = thr_point.project(extension, params["azimuth_r_p"])
            line_end = line_start.project(line_length, params["azimuth_p_r"]) if line_start else None
            if not line_start or not line_end:
                continue

            governing_type = self._governing_runway_type(runway_data)

            for spec in self._runway_separation_operation_specs(runway_data):
                sep = ruleset.parallel_runway_separation(
                    arc_num,
                    arc_num,
                    governing_type,
                    governing_type,
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

                for side, side_az in [
                    ("L", params["azimuth_perp_l"]),
                    ("R", params["azimuth_perp_r"]),
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
                        "rwy": runway_name,
                        "operation": spec["operation_type"],
                        "op_cat": spec["category_label"],
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
            QgsMessageLog.logMessage(
                "Parallel runway standards layer skipped: no applicable runway data.",
                plugin_tag,
                level=Qgis.Info,
            )
            return False

        layer_created = self._create_and_add_layer(
            "LineString",
            "ParallelRunwayStandards",
            "Parallel Runway Standards",
            fields,
            features_to_add,
            layer_group,
            "Parallel Runway Standards Line",
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
