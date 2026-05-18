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
    QgsMessageLog,
)

from .. import ols_dimensions
from ..guidelines.constants import RAOA_MOS_REF_VAL, MOS_REF_TAXIWAY_SEPARATION

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
        runway_name = runway_data.get(
            "short_name", f"RWY_{runway_data.get('original_index','?')}"
        )
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
        primary_desig, reciprocal_desig = (
            runway_name.split("/") if "/" in runway_name else ("THR1", "THR2")
        )

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
                QgsField(
                    "desc", QVariant.String, self.tr("desc"), 100
                ),
                QgsField("offset_m", QVariant.Double, self.tr("offset_m"), 10, 2),
                QgsField(
                    "ref_mos", QVariant.String, self.tr("MOS Reference"), 100
                ),
                QgsField(
                    "appr_type", QVariant.String, self.tr("appr_type"), 50
                ),
                QgsField(
                    "arc_num", QVariant.String, self.tr("arc_num"), 5
                ),
                QgsField(
                    "arc_let", QVariant.String, self.tr("arc_let"), 5
                ),
                QgsField("side", QVariant.String, self.tr("Side (L/R)"), 5),
            ]
        )
        return fields

    def process_taxiway_separation(
        self, runway_data: dict, layer_group: QgsLayerTreeGroup
    ) -> bool:
        """Generates Taxiway Minimum Separation lines."""
        plugin_tag = PLUGIN_TAG
        runway_name = runway_data.get(
            "short_name", f"RWY_{runway_data.get('original_index','?')}"
        )
        thr_point = runway_data.get("thr_point")
        rec_thr_point = runway_data.get("rec_thr_point")
        arc_num_str = runway_data.get("arc_num")
        arc_let_raw = runway_data.get("arc_let")
        type1_str = runway_data.get("type1", "")
        type2_str = runway_data.get("type2", "")

        # Essential Checks
        if (
            thr_point is None
            or rec_thr_point is None
            or layer_group is None
            or not arc_num_str
        ):
            QgsMessageLog.logMessage(
                f"Taxiway Sep skipped {runway_name}: Missing essential data.",
                plugin_tag,
                level=Qgis.Warning,
            )
            return False
        try:
            arc_num = int(
                arc_num_str
            )  # Keep as int for logic, convert to str for attribute
        except (ValueError, TypeError):
            QgsMessageLog.logMessage(
                f"Taxiway Sep skipped {runway_name}: Invalid ARC Number '{arc_num_str}'.",
                plugin_tag,
                level=Qgis.Warning,
            )
            return False

        # Validate ARC Letter
        if (
            not arc_let_raw
            or not isinstance(arc_let_raw, str)
            or not arc_let_raw.strip()
        ):
            QgsMessageLog.logMessage(
                f"Taxiway Sep skipped {runway_name}: ARC Letter not provided or invalid ('{arc_let_raw}').",
                plugin_tag,
                level=Qgis.Warning,
            )
            return False
        arc_let = arc_let_raw.strip().upper()  # Use cleaned letter

        rwy_params = self._get_runway_parameters(thr_point, rec_thr_point)
        if (
            rwy_params is None
            or rwy_params.get("length") is None
            or rwy_params["length"] <= 0
        ):
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
        offset_params = ols_dimensions.get_taxiway_separation_offset(
            arc_num, arc_let, governing_type_str
        )
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
        attr_surface_description = (
            surface_description if surface_description.strip() else "N/A"
        )
        attr_mos_ref = MOS_REF_TAXIWAY_SEPARATION
        attr_app_type = (
            governing_type_str
            if governing_type_str and governing_type_str.strip()
            else "N/A"
        )
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

        if (
            not geom_ok and not features_to_add
        ):  # If geometry failed AND no features were added
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
