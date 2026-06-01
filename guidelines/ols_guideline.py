# -*- coding: utf-8 -*-
"""Guideline F and airport-wide OLS generation."""

import math
import traceback
from typing import List, Optional, Tuple

from qgis.PyQt.QtCore import QVariant  # type: ignore
from qgis.core import (  # type: ignore
    Qgis,
    QgsCoordinateReferenceSystem,
    QgsDistanceArea,
    QgsFeature,
    QgsField,
    QgsFields,
    QgsGeometry,
    QgsLayerTreeGroup,
    QgsLineString,
    QgsMessageLog,
    QgsPoint,
    QgsPointXY,
    QgsProject,
    QgsWkbTypes,
)

from ..dimensions import ols_dimensions
from .guideline_constants import (
    APPROACH_CONTOUR_INTERVAL,
    CONICAL_CONTOUR_INTERVAL,
    TOCS_CONTOUR_INTERVAL,
    TRANSITIONAL_CONTOUR_INTERVAL,
)
from .controlling_ols_engine import (
    ControllingOlsCandidate,
    axis_elevation_evaluator,
    conical_elevation_evaluator,
    constant_elevation_evaluator,
    plane_elevation_evaluator,
)

PLUGIN_TAG = "SafeguardingBuilder"


class OlsGuidelineMixin:
    def _get_contour_interval(self, surface_key: str, fallback: float) -> float:
        """Return a positive contour interval from dialog options, or the default fallback."""
        intervals = getattr(self, "contour_intervals", {}) or {}
        try:
            value = float(intervals.get(surface_key, fallback))
        except (TypeError, ValueError):
            return fallback
        return value if value > 0 else fallback

    def _generate_airport_wide_ols(
        self,
        processed_runway_data_list: List[dict],
        ols_layer_group: QgsLayerTreeGroup,
        reference_elevation_datum: float,
        icao_code: str,
    ) -> bool:
        """
        Generates airport-wide OLS: IHS, Conical (with contours), OHS, Transitional.
        Accounts for displaced thresholds when calculating IHS base strip outlines.
        Requires processed runway data, RED, group, and ICAO code.
        Logs start/end, key parameters, warnings, and critical errors.
        """
        plugin_tag = PLUGIN_TAG
        # Constants for this method
        BUFFER_SEGMENTS = 36  # Segments for geometry buffers

        QgsMessageLog.logMessage(
            f"Starting Airport-Wide OLS Generation (Transitional, IHS, Conical, OHS - Applying RED: {reference_elevation_datum:.2f}m)",
            plugin_tag,
            level=Qgis.Info,
        )
        overall_success = False  # Tracks if *any* airport-wide OLS layer was successfully created

        # --- Get IHS Parameters ---
        ihs_base_height_agl = ols_dimensions.get_ihs_base_height()
        if ihs_base_height_agl is None:
            QgsMessageLog.logMessage(
                "Cannot generate Airport-Wide OLS: Failed to retrieve IHS base height parameter.",
                plugin_tag,
                level=Qgis.Critical,
            )
            return False
        IHS_ELEVATION_AMSL = reference_elevation_datum + ihs_base_height_agl

        # --- Initialize Variables ---
        ihs_base_geom: Optional[QgsGeometry] = None
        outer_conical_geom: Optional[QgsGeometry] = None
        highest_arc_num = 0
        highest_precision_type_str = "Non-Instrument (NI)"  # Default lowest precision

        # --- 1. Generate Individual Strip Outline Geometries ---
        strip_outline_geoms: List[QgsGeometry] = []
        # QgsMessageLog.logMessage(
        #     "Generating individual runway strip outlines for IHS base...",
        #     plugin_tag,
        #     level=Qgis.Info,
        # )

        if not processed_runway_data_list:
            QgsMessageLog.logMessage(
                "Cannot generate IHS base: No processed runway data available.",
                plugin_tag,
                level=Qgis.Warning,
            )

        for i, rwy_data in enumerate(processed_runway_data_list):
            try:  # Broad try block for processing a single runway's outline
                rwy_name = rwy_data.get("short_name", f"RWY_{rwy_data.get('original_index', '?')}")
                thr_point = rwy_data.get("thr_point")
                rec_thr_point = rwy_data.get("rec_thr_point")
                arc_num_str = rwy_data.get("arc_num")
                type1_str = rwy_data.get("type1")
                type2_str = rwy_data.get("type2")
                rwy_data.get("width")

                # Robustly get displacement values
                disp_val_1 = rwy_data.get("thr_displaced_1")
                disp_val_2 = rwy_data.get("thr_displaced_2")
                disp_thr_1 = float(disp_val_1) if disp_val_1 is not None else 0.0
                disp_thr_2 = float(disp_val_2) if disp_val_2 is not None else 0.0

                # Check Essential Data
                if not all([thr_point, rec_thr_point, arc_num_str]):
                    # Use Warning level for skips that prevent outline generation
                    QgsMessageLog.logMessage(
                        f"Skipping {rwy_name} strip outline - Missing essential data (Points/ARC Str).",
                        plugin_tag,
                        level=Qgis.Warning,
                    )
                    continue

                # Check ARC Number
                try:
                    arc_num = int(arc_num_str)
                    highest_arc_num = max(highest_arc_num, arc_num)
                except (ValueError, TypeError):
                    QgsMessageLog.logMessage(
                        f"Skipping {rwy_name} strip outline - Invalid ARC number '{arc_num_str}'.",
                        plugin_tag,
                        level=Qgis.Warning,
                    )
                    continue

                # Track highest precision type
                type_order = [
                    "",
                    "Non-Instrument (NI)",
                    "Non-Precision Approach (NPA)",
                    "Precision Approach CAT I",
                    "Precision Approach CAT II/III",
                ]
                current_type1_idx = type_order.index(type1_str) if type1_str in type_order else 1
                current_type2_idx = type_order.index(type2_str) if type2_str in type_order else 1
                current_max_type_str = type_order[max(current_type1_idx, current_type2_idx)]
                highest_idx_overall = (
                    type_order.index(highest_precision_type_str) if highest_precision_type_str in type_order else 1
                )
                if max(current_type1_idx, current_type2_idx) > highest_idx_overall:
                    highest_precision_type_str = current_max_type_str

                # Check Runway Parameters
                rwy_params = self._get_runway_parameters(thr_point, rec_thr_point)
                if not rwy_params:
                    QgsMessageLog.logMessage(
                        f"Skipping {rwy_name} strip outline - Failed runway params.",
                        plugin_tag,
                        level=Qgis.Warning,
                    )
                    continue

                # Check Physical Endpoints
                physical_endpoints_result = self._get_physical_runway_endpoints(
                    thr_point, rec_thr_point, disp_thr_1, disp_thr_2, rwy_params
                )
                if physical_endpoints_result is None:
                    QgsMessageLog.logMessage(
                        f"Skipping {rwy_name} strip outline - Failed physical endpoints calc.",
                        plugin_tag,
                        level=Qgis.Warning,
                    )
                    continue
                phys_p_start, phys_p_end, _ = physical_endpoints_result

                # Check Strip Dimensions
                strip_dims = rwy_data.get("calculated_strip_dims")
                if not strip_dims:
                    QgsMessageLog.logMessage(
                        f"Skipping {rwy_name} strip outline - 'calculated_strip_dims' was not found or invalid: {repr(strip_dims)}.",
                        plugin_tag,
                        level=Qgis.Warning,
                    )
                    continue

                # Check Strip Dimensions Content
                strip_width = strip_dims.get("overall_width")
                strip_ext = strip_dims.get("extension_length")
                is_width_valid = isinstance(strip_width, (int, float)) and strip_width > 0
                is_ext_valid = isinstance(strip_ext, (int, float)) and strip_ext >= 0
                if not is_width_valid or not is_ext_valid:
                    QgsMessageLog.logMessage(
                        f"Skipping {rwy_name} strip outline - invalid content in strip_dims (W:{strip_width}, E:{strip_ext}).",
                        plugin_tag,
                        level=Qgis.Warning,
                    )
                    continue

                # Check Strip Endpoint Projection
                strip_end_p = phys_p_start.project(strip_ext, rwy_params["azimuth_r_p"])
                strip_end_r = phys_p_end.project(strip_ext, rwy_params["azimuth_p_r"])
                if not strip_end_p or not strip_end_r:
                    QgsMessageLog.logMessage(
                        f"Skipping {rwy_name} strip outline - failed strip end point projection.",
                        plugin_tag,
                        level=Qgis.Warning,
                    )
                    continue

                # Check IHS Radius Calculation
                ihs_params = ols_dimensions.get_ols_params(arc_num, current_max_type_str, "IHS")
                ihs_end_radius = ihs_params.get("radius") if ihs_params else None
                if ihs_end_radius is None or not isinstance(ihs_end_radius, (int, float)) or ihs_end_radius <= 0:
                    if isinstance(strip_width, (int, float)) and strip_width > 0:
                        ihs_end_radius = strip_width / 2.0
                        # Info log for using fallback radius might be useful even in production
                        QgsMessageLog.logMessage(
                            f"Info: Using fallback radius {ihs_end_radius:.2f}m for {rwy_name} IHS outline (based on strip width).",
                            plugin_tag,
                            level=Qgis.Info,
                        )
                    else:
                        QgsMessageLog.logMessage(
                            f"Skipping {rwy_name} strip outline - Cannot determine valid IHS radius (Params:{ihs_params}, Width:{strip_width}).",
                            plugin_tag,
                            level=Qgis.Warning,
                        )
                        continue

                # --- Geometry Generation ---
                try:  # Generate the geometry
                    buffer_p = QgsGeometry.fromPointXY(strip_end_p).buffer(ihs_end_radius, BUFFER_SEGMENTS)
                    buffer_r = QgsGeometry.fromPointXY(strip_end_r).buffer(ihs_end_radius, BUFFER_SEGMENTS)

                    corner_p_l = strip_end_p.project(ihs_end_radius, rwy_params["azimuth_perp_l"])
                    corner_p_r = strip_end_p.project(ihs_end_radius, rwy_params["azimuth_perp_r"])
                    corner_r_l = strip_end_r.project(ihs_end_radius, rwy_params["azimuth_perp_l"])
                    corner_r_r = strip_end_r.project(ihs_end_radius, rwy_params["azimuth_perp_r"])
                    connector = None
                    if all([corner_p_l, corner_p_r, corner_r_l, corner_r_r]):
                        connector = self._create_polygon_from_corners(
                            [corner_p_l, corner_p_r, corner_r_r, corner_r_l],
                            f"Strip Connector {rwy_name}",
                        )

                    components = [g for g in [buffer_p, buffer_r, connector] if g and not g.isEmpty()]

                    if len(components) >= 2:
                        runway_strip_geom = QgsGeometry.unaryUnion(components)
                        if runway_strip_geom is None or runway_strip_geom.isEmpty():
                            runway_strip_geom = None  # Ensure it's None if union failed

                        if runway_strip_geom:  # Check if union produced something
                            valid_geom = self._ensure_valid_geometry(runway_strip_geom, f"strip outline {rwy_name}")
                            if valid_geom is not None:
                                strip_outline_geoms.append(valid_geom)
                            else:
                                QgsMessageLog.logMessage(
                                    f"Warning: Generated strip outline for {rwy_name} is invalid, skipping.",
                                    plugin_tag,
                                    level=Qgis.Warning,
                                )
                    elif not components:
                        QgsMessageLog.logMessage(
                            f"Warning: Skipping strip outline for {rwy_name}: Failed to generate valid buffer/connector components.",
                            plugin_tag,
                            level=Qgis.Warning,
                        )
                    # else: Only one component was valid, cannot form outline.

                except Exception as e_strip_geom:
                    QgsMessageLog.logMessage(
                        f"Error generating strip outline geom for {rwy_name}: {e_strip_geom}",
                        plugin_tag,
                        level=Qgis.Warning,
                    )

            except Exception as loop_body_error:
                current_rwy_id = rwy_data.get("short_name", rwy_data.get("original_index", f"Unknown Index {i}"))
                QgsMessageLog.logMessage(
                    f"CRITICAL: Unexpected error processing runway {current_rwy_id} (Loop Index {i}) in Airport OLS strip outline loop: {loop_body_error}\n{traceback.format_exc()}",
                    plugin_tag,
                    level=Qgis.Critical,
                )
                continue  # Process next runway if possible

        # --- End of loop ---

        # --- 2. Combine Outlines & Calculate Convex Hull ---
        if not strip_outline_geoms:
            QgsMessageLog.logMessage(
                "IHS Generation Failed: No valid runway strip outlines were generated.",
                plugin_tag,
                level=Qgis.Critical,
            )
            QgsMessageLog.logMessage(
                f"(Info: Highest runway precision type detected: {highest_precision_type_str}, ARC: {highest_arc_num})",
                plugin_tag,
                level=Qgis.Info,
            )
            return False

        QgsMessageLog.logMessage(
            f"Creating IHS base polygon from Convex Hull of {len(strip_outline_geoms)} strip outline(s)...",
            plugin_tag,
            level=Qgis.Info,
        )
        try:
            merged_geom = QgsGeometry.unaryUnion(strip_outline_geoms)
            if not merged_geom or merged_geom.isEmpty():
                raise ValueError("unaryUnion of strip outlines failed.")
            ihs_base_geom = merged_geom.convexHull()
            if not ihs_base_geom or ihs_base_geom.isEmpty():
                raise ValueError("convexHull calculation failed.")
            ihs_base_geom = self._ensure_valid_geometry(ihs_base_geom, "IHS base convex hull")
            if ihs_base_geom is None:
                raise ValueError("IHS base geometry invalid after validation.")
            strip_outline_geoms.clear()
        except Exception as e_hull:
            QgsMessageLog.logMessage(
                f"IHS Generation Failed: Error during Convex Hull creation: {e_hull}",
                plugin_tag,
                level=Qgis.Critical,
            )
            return False

        # --- 3. Create IHS Layer ---
        if ihs_base_geom:
            try:
                ihs_ref_params = ols_dimensions.get_ols_params(highest_arc_num, highest_precision_type_str, "IHS")
                ref_text = ihs_ref_params.get("ref", "MOS 8.2.18") if ihs_ref_params else "MOS 8.2.18"
                fields = self._get_ols_fields("IHS")
                feature = QgsFeature(fields)
                feature.setGeometry(ihs_base_geom)
                attr_map = {
                    "rwy_name": self.tr("Airport Wide"),
                    "surface": "IHS",
                    "section_desc": "Inner Horizontal Surface",
                    "elev_m": IHS_ELEVATION_AMSL,
                    "height_agl": ihs_base_height_agl,
                    "ref_mos": ref_text,
                }
                for name, value in attr_map.items():
                    idx = fields.indexFromName(name)
                    if idx != -1:
                        feature.setAttribute(idx, value)
                layer = self._create_and_add_layer(
                    "Polygon",
                    f"OLS_IHS_{icao_code}",
                    f"{self.tr('OLS')} IHS {icao_code}",
                    fields,
                    [feature],
                    ols_layer_group,
                    "OLS IHS",
                )
                if layer is not None:
                    overall_success = True
                if hasattr(self, "_register_controlling_ols_candidate"):
                    self._register_controlling_ols_candidate(
                        ControllingOlsCandidate(
                            surface_id=f"IHS:{icao_code}",
                            surface_type="IHS",
                            footprint=QgsGeometry(ihs_base_geom),
                            elevation_at_xy=constant_elevation_evaluator(IHS_ELEVATION_AMSL),
                            model="constant",
                            metadata={"elevation_m": IHS_ELEVATION_AMSL},
                        )
                    )
            except Exception as e_ihs_layer:
                QgsMessageLog.logMessage(
                    f"Critical error creating IHS Feature/Layer: {e_ihs_layer}\n{traceback.format_exc()}",
                    plugin_tag,
                    level=Qgis.Critical,
                )
                ihs_base_geom = None

        # --- 4. Generate Conical Surface & Contours ---
        conical_layer_created = False
        if ihs_base_geom:
            conical_params = ols_dimensions.get_ols_params(highest_arc_num, highest_precision_type_str, "CONICAL")
            if conical_params:
                height_extent_agl = conical_params.get("height_extent_agl")
                slope = conical_params.get("slope")
                ref = conical_params.get("ref", "MOS 8.2.19")
                if slope is not None and slope > 0 and height_extent_agl is not None and height_extent_agl > 0:
                    ohs_params_for_conical = ols_dimensions.get_ols_params(
                        highest_arc_num, highest_precision_type_str, "OHS"
                    )
                    if ohs_params_for_conical:
                        ohs_height_agl = ohs_params_for_conical.get("height_agl")
                        if isinstance(ohs_height_agl, (int, float)):
                            height_extent_to_ohs = float(ohs_height_agl) - ihs_base_height_agl
                            if height_extent_to_ohs > height_extent_agl:
                                QgsMessageLog.logMessage(
                                    "Extending Conical Surface per MOS 7.06(3): "
                                    f"base height extent {height_extent_agl:.1f}m does not reach "
                                    f"OHS at {float(ohs_height_agl):.1f}m above RED; "
                                    f"using {height_extent_to_ohs:.1f}m above IHS.",
                                    plugin_tag,
                                    level=Qgis.Info,
                                )
                                height_extent_agl = height_extent_to_ohs
                    horizontal_extent = height_extent_agl / slope
                    conical_outer_elevation = IHS_ELEVATION_AMSL + height_extent_agl
                    QgsMessageLog.logMessage(
                        f"Generating Conical Surface: Slope={slope*100:.1f}%, H Ext={height_extent_agl:.1f}m, Horiz Ext={horizontal_extent:.1f}m, Top Elev AMSL={conical_outer_elevation:.2f}m",
                        plugin_tag,
                        level=Qgis.Info,
                    )
                    try:
                        outer_conical_geom = self._ensure_valid_geometry(
                            ihs_base_geom.buffer(horizontal_extent, BUFFER_SEGMENTS),
                            "outer Conical buffer",
                        )
                        if outer_conical_geom is not None:
                            temp_conical_geom = self._ensure_valid_geometry(
                                outer_conical_geom.difference(ihs_base_geom),
                                "Conical ring",
                            )
                            if temp_conical_geom is not None:
                                fields = self._get_ols_fields("Conical")
                                feature = QgsFeature(fields)
                                feature.setGeometry(temp_conical_geom)
                                conical_total_height_agl = ihs_base_height_agl + height_extent_agl
                                attr_map = {
                                    "rwy_name": self.tr("Airport Wide"),
                                    "surface": "Conical",
                                    "section_desc": "Conical Surface",
                                    "elev_m": conical_outer_elevation,
                                    "height_agl": conical_total_height_agl,
                                    "slope_perc": slope * 100.0,
                                    "ref_mos": ref,
                                    "height_extent": height_extent_agl,
                                }
                                for name, value in attr_map.items():
                                    idx = fields.indexFromName(name)
                                    if idx != -1:
                                        feature.setAttribute(idx, value)
                                layer = self._create_and_add_layer(
                                    "Polygon",
                                    f"OLS_Conical_{icao_code}",
                                    f"{self.tr('OLS')} Conical {icao_code}",
                                    fields,
                                    [feature],
                                    ols_layer_group,
                                    "OLS Conical",
                                )
                                if layer is not None:
                                    overall_success = True
                                    conical_layer_created = True
                                if hasattr(self, "_register_controlling_ols_candidate"):
                                    self._register_controlling_ols_candidate(
                                        ControllingOlsCandidate(
                                            surface_id=f"CONICAL:{icao_code}",
                                            surface_type="Conical",
                                            footprint=QgsGeometry(temp_conical_geom),
                                            elevation_at_xy=conical_elevation_evaluator(
                                                ihs_base_geom,
                                                IHS_ELEVATION_AMSL,
                                                slope,
                                                horizontal_extent,
                                            ),
                                            model="conical",
                                            metadata={
                                                "base_footprint": QgsGeometry(ihs_base_geom),
                                                "base_elevation_m": IHS_ELEVATION_AMSL,
                                                "slope": slope,
                                                "max_distance_m": horizontal_extent,
                                                "height_extent_agl": height_extent_agl,
                                            },
                                        )
                                    )
                            else:
                                QgsMessageLog.logMessage(
                                    "Failed generate valid Conical ring geometry.",
                                    plugin_tag,
                                    level=Qgis.Warning,
                                )
                        else:
                            QgsMessageLog.logMessage(
                                "Failed generate valid outer Conical buffer.",
                                plugin_tag,
                                level=Qgis.Warning,
                            )
                    except Exception as e_conical:
                        QgsMessageLog.logMessage(
                            f"Error during Conical Surface generation: {e_conical}",
                            plugin_tag,
                            level=Qgis.Warning,
                        )
                elif height_extent_agl is not None and height_extent_agl <= 0:
                    QgsMessageLog.logMessage(
                        "Skipping Conical Surface: Height extent zero or negative.",
                        plugin_tag,
                        level=Qgis.Info,
                    )
                else:
                    QgsMessageLog.logMessage(
                        "Skipping Conical Surface: Invalid parameters (Slope/Height Extent).",
                        plugin_tag,
                        level=Qgis.Warning,
                    )
            else:
                QgsMessageLog.logMessage(
                    f"Skipping Conical Surface: No params found for Code {highest_arc_num}, Type {highest_precision_type_str}.",
                    plugin_tag,
                    level=Qgis.Warning,
                )

        # --- 4b. Generate Conical CONTOURS ---
        if (
            conical_layer_created
            and ihs_base_geom
            and outer_conical_geom
            and slope
            and height_extent_agl
            and height_extent_agl > 0
            and conical_outer_elevation is not None
        ):
            conical_contour_interval = self._get_contour_interval("conical", CONICAL_CONTOUR_INTERVAL)
            QgsMessageLog.logMessage(
                f"Generating Conical Contours at {conical_contour_interval}m intervals...",
                plugin_tag,
                level=Qgis.Info,
            )
            contour_features: List[QgsFeature] = []
            ref = conical_params.get("ref", "MOS 8.2.19")
            fields = self._get_conical_contour_fields()
            conical_surface_id = f"CONICAL:{icao_code}"

            def _extract_exterior_ring_line(geom: QgsGeometry) -> Optional[QgsGeometry]:
                # Returns a LineString geometry of the exterior ring, or None if not available.
                poly = geom.asPolygon()
                if poly and len(poly) > 0 and len(poly[0]) > 1:
                    return QgsGeometry.fromPolylineXY(poly[0])
                multipoly = geom.asMultiPolygon()
                if multipoly and len(multipoly) > 0 and len(multipoly[0]) > 0:
                    return QgsGeometry.fromPolylineXY(multipoly[0][0])
                return None

            # 1. Start contour at IHS base
            start_geom = QgsGeometry(ihs_base_geom)
            if start_geom and not start_geom.isEmpty() and start_geom.isGeosValid():
                line_geom = _extract_exterior_ring_line(start_geom)
                if line_geom and not line_geom.isEmpty() and line_geom.isGeosValid():
                    feat = QgsFeature(fields)
                    feat.setGeometry(line_geom)
                    feat.setAttribute(
                        fields.indexFromName("surface"),
                        f"Conical Contour {IHS_ELEVATION_AMSL:.0f}m",
                    )
                    feat.setAttribute(fields.indexFromName("contour_elev_am"), IHS_ELEVATION_AMSL)
                    feat.setAttribute(fields.indexFromName("contour_hgt_abv"), 0)
                    feat.setAttribute(fields.indexFromName("ref_mos"), ref)
                    feat.setAttribute(fields.indexFromName("surface_id"), conical_surface_id)
                    contour_features.append(feat)
                    # QgsMessageLog.logMessage(
                    #     f"Conical start contour at {IHS_ELEVATION_AMSL:.2f}m AMSL.",
                    #     plugin_tag,
                    #     Qgis.Info,
                    # )
                else:
                    QgsMessageLog.logMessage(
                        "Failed to extract exterior ring for IHS base.",
                        plugin_tag,
                        Qgis.Warning,
                    )

            # 2. Interval contours (main loop)
            if IHS_ELEVATION_AMSL % conical_contour_interval == 0:
                first_contour_elev_amsl = IHS_ELEVATION_AMSL + conical_contour_interval
            else:
                first_contour_elev_amsl = (
                    math.ceil(IHS_ELEVATION_AMSL / conical_contour_interval) * conical_contour_interval
                )
            current_target_contour_elev_amsl = first_contour_elev_amsl

            while current_target_contour_elev_amsl < conical_outer_elevation - 1e-6:
                contour_h_above_ihs = min(
                    current_target_contour_elev_amsl - IHS_ELEVATION_AMSL,
                    height_extent_agl,
                )
                if contour_h_above_ihs < 1e-6:
                    current_target_contour_elev_amsl += conical_contour_interval
                    continue
                try:
                    horizontal_dist = contour_h_above_ihs / slope
                    outer_geom = self._ensure_valid_geometry(
                        ihs_base_geom.buffer(horizontal_dist, BUFFER_SEGMENTS),
                        f"Conical contour buffer {current_target_contour_elev_amsl}",
                    )
                    if outer_geom is not None:
                        line_geom = _extract_exterior_ring_line(outer_geom)
                        if line_geom and not line_geom.isEmpty() and line_geom.isGeosValid():
                            feat = QgsFeature(fields)
                            feat.setGeometry(line_geom)
                            feat.setAttribute(
                                fields.indexFromName("surface"),
                                f"Conical Contour {current_target_contour_elev_amsl:.0f}m",
                            )
                            feat.setAttribute(
                                fields.indexFromName("contour_elev_am"),
                                current_target_contour_elev_amsl,
                            )
                            feat.setAttribute(
                                fields.indexFromName("contour_hgt_abv"),
                                contour_h_above_ihs,
                            )
                            feat.setAttribute(fields.indexFromName("ref_mos"), ref)
                            feat.setAttribute(fields.indexFromName("surface_id"), conical_surface_id)
                            contour_features.append(feat)
                            # QgsMessageLog.logMessage(
                            #     f"Conical interval contour at {current_target_contour_elev_amsl:.2f}m AMSL.", plugin_tag, Qgis.Info
                            # )
                except Exception as e_contour:
                    QgsMessageLog.logMessage(
                        f"Error generating conical interval contour at elev={current_target_contour_elev_amsl}: {e_contour}",
                        plugin_tag,
                        Qgis.Warning,
                    )
                current_target_contour_elev_amsl += conical_contour_interval

            # 3. End contour at conical outer elevation
            end_geom = outer_conical_geom
            if end_geom and not end_geom.isEmpty() and end_geom.isGeosValid():
                line_geom = _extract_exterior_ring_line(end_geom)
                if line_geom and not line_geom.isEmpty() and line_geom.isGeosValid():
                    # Avoid duplicate (shouldn't happen but check)
                    if not any(
                        abs(f.attribute("contour_elev_am") - conical_outer_elevation) < 1e-3 for f in contour_features
                    ):
                        feat = QgsFeature(fields)
                        feat.setGeometry(line_geom)
                        feat.setAttribute(
                            fields.indexFromName("surface"),
                            f"Conical Contour {conical_outer_elevation:.0f}m",
                        )
                        feat.setAttribute(
                            fields.indexFromName("contour_elev_am"),
                            conical_outer_elevation,
                        )
                        feat.setAttribute(fields.indexFromName("contour_hgt_abv"), height_extent_agl)
                        feat.setAttribute(fields.indexFromName("ref_mos"), ref)
                        feat.setAttribute(fields.indexFromName("surface_id"), conical_surface_id)
                        contour_features.append(feat)
                        # QgsMessageLog.logMessage(
                        #     f"Conical end contour at {conical_outer_elevation:.2f}m AMSL.",
                        #     plugin_tag,
                        #     Qgis.Info,
                        # )
                else:
                    QgsMessageLog.logMessage(
                        "Failed to extract exterior ring for conical outer edge.",
                        plugin_tag,
                        Qgis.Warning,
                    )

            # 4. Layer creation
            if contour_features:
                if hasattr(self, "_register_controlling_ols_contour"):
                    for contour_feature in contour_features:
                        self._register_controlling_ols_contour(
                            conical_surface_id,
                            "Conical",
                            contour_feature,
                            "OLS Conical Contour",
                        )
                conical_contour_count = len(contour_features)
                contour_layer = self._create_and_add_layer(
                    "LineString",
                    f"OLS_Conical_Contours_{icao_code}",
                    f"{self.tr('OLS')} Conical Contours {icao_code}",
                    fields,
                    contour_features,
                    ols_layer_group,
                    "OLS Conical Contour",
                )
                if contour_layer is not None:
                    overall_success = True
                    QgsMessageLog.logMessage(
                        f"Created conical contour layer for {icao_code}, {conical_contour_count} features.",
                        plugin_tag,
                        Qgis.Info,
                    )
            else:
                QgsMessageLog.logMessage(
                    f"No conical contours generated for {icao_code}.",
                    plugin_tag,
                    Qgis.Warning,
                )

        # --- 5. Generate Outer Horizontal Surface (OHS) ---
        ohs_params = ols_dimensions.get_ols_params(highest_arc_num, highest_precision_type_str, "OHS")
        if ohs_params:
            radius = ohs_params.get("radius")
            height_agl = ohs_params.get("height_agl")
            ref = ohs_params.get("ref", "MOS 8.2.20")
            QgsMessageLog.logMessage(
                f"OHS required (Code {highest_arc_num}, Type {highest_precision_type_str}). Radius={radius}m, Height={height_agl}m AGL.",
                plugin_tag,
                level=Qgis.Info,
            )
            if radius is not None and height_agl is not None and radius > 0:
                ohs_elevation_amsl = reference_elevation_datum + height_agl
                arp_point_xy: Optional[QgsPointXY] = None
                project = QgsProject.instance()
                # Construct the expected ARP layer name that your plugin creates
                expected_arp_layer_name = f"{icao_code} {self.tr('ARP')}"  # Match display name from create_arp_layer

                arp_layer_candidates = project.mapLayersByName(expected_arp_layer_name)

                found_arp_point_layer = None
                for lyr in arp_layer_candidates:
                    if lyr.isValid() and lyr.geometryType() == QgsWkbTypes.PointGeometry:  # Check for Point geometry
                        found_arp_point_layer = lyr
                        break  # Found a suitable point layer

                if found_arp_point_layer is not None:
                    arp_feat = next(found_arp_point_layer.getFeatures(), None)
                    if arp_feat and arp_feat.hasGeometry() and not arp_feat.geometry().isNull():
                        geom = arp_feat.geometry()
                        actual_wkb_type = geom.wkbType()

                        # QgsMessageLog.logMessage(
                        #     f"ARP feature for OHS: Layer='{found_arp_point_layer.name()}', "
                        #     f"Geom valid? {geom.isGeosValid()}, "
                        #     f"WKBType Int: {actual_wkb_type} ({QgsWkbTypes.displayString(actual_wkb_type)})",
                        #     PLUGIN_TAG,
                        #     Qgis.Info,
                        # )

                        acceptable_point_wkb_types = {
                            QgsWkbTypes.Point,
                            QgsWkbTypes.PointZ,
                            QgsWkbTypes.PointM,
                            QgsWkbTypes.PointZM,
                            QgsWkbTypes.MultiPoint,
                            QgsWkbTypes.MultiPointZ,
                            QgsWkbTypes.MultiPointM,
                            QgsWkbTypes.MultiPointZM,
                        }

                        if actual_wkb_type in acceptable_point_wkb_types:
                            if QgsWkbTypes.isMultiType(actual_wkb_type):
                                multi_point_geom = geom.constGet()
                                if multi_point_geom and multi_point_geom.numGeometries() > 0:
                                    point_part = multi_point_geom.geometryN(0)
                                    if point_part:
                                        arp_point_xy = QgsPointXY(point_part.x(), point_part.y())
                            else:
                                arp_point_xy = geom.asPoint()
                        else:
                            QgsMessageLog.logMessage(
                                f"ARP layer '{found_arp_point_layer.name()}' feature has WKBType {QgsWkbTypes.displayString(actual_wkb_type)}, NOT an acceptable Point type for OHS.",
                                PLUGIN_TAG,
                                level=Qgis.Warning,
                            )

                    else:
                        QgsMessageLog.logMessage(
                            f"ARP layer '{found_arp_point_layer.name()}' found, but no valid features/geometry for OHS.",
                            PLUGIN_TAG,
                            level=Qgis.Warning,
                        )
                else:
                    QgsMessageLog.logMessage(
                        f"Could not find a valid POINT layer named '{expected_arp_layer_name}' for OHS.",
                        PLUGIN_TAG,
                        level=Qgis.Warning,
                    )

                if arp_point_xy:  # Only proceed if arp_point_xy was successfully set
                    try:
                        center_geom = QgsGeometry.fromPointXY(arp_point_xy)
                        ohs_full_circle_geom = self._ensure_valid_geometry(
                            center_geom.buffer(radius, 144), "OHS full circle"
                        )
                        if ohs_full_circle_geom is not None:
                            ohs_final_geom = ohs_full_circle_geom
                            if outer_conical_geom and outer_conical_geom.isGeosValid():
                                # QgsMessageLog.logMessage(
                                #     "Attempting to difference Conical outer boundary from OHS circle.",
                                #     plugin_tag,
                                #     level=Qgis.Info,
                                # )
                                try:
                                    difference_geom = self._ensure_valid_geometry(
                                        ohs_full_circle_geom.difference(outer_conical_geom),
                                        "OHS minus Conical",
                                    )
                                    if difference_geom is not None:
                                        ohs_final_geom = difference_geom
                                    else:
                                        QgsMessageLog.logMessage(
                                            "Warning: Difference op for OHS resulted in invalid/empty geometry. Using full circle.",
                                            plugin_tag,
                                            level=Qgis.Warning,
                                        )
                                except Exception as e_diff:
                                    QgsMessageLog.logMessage(
                                        f"Warning: Error during OHS difference operation: {e_diff}. Using full circle.",
                                        plugin_tag,
                                        level=Qgis.Warning,
                                    )
                            else:
                                QgsMessageLog.logMessage(
                                    "Info: Conical outer boundary not available or invalid for OHS difference. Using full OHS circle.",
                                    plugin_tag,
                                    level=Qgis.Info,
                                )

                            fields = self._get_ols_fields("OHS")
                            feature = QgsFeature(fields)
                            feature.setGeometry(ohs_final_geom)
                            attr_map = {
                                "surface": "OHS",
                                "section_desc": "Outer Horizontal Surface",
                                "elev_m": ohs_elevation_amsl,
                                "height_agl": height_agl,
                                "ref_mos": ref,
                                "radius_m": radius,
                            }
                            if fields.indexFromName("rwy_name") != -1:
                                attr_map["rwy_name"] = self.tr("Airport Wide")
                            for name, value in attr_map.items():
                                idx = fields.indexFromName(name)
                                if idx != -1:
                                    feature.setAttribute(idx, value)
                            layer = self._create_and_add_layer(
                                "Polygon",
                                f"OLS_OHS_{icao_code}",
                                f"{self.tr('OLS')} OHS {icao_code}",
                                fields,
                                [feature],
                                ols_layer_group,
                                "OLS OHS",
                            )
                            if layer is not None:
                                overall_success = True
                            if hasattr(self, "_register_controlling_ols_candidate"):
                                self._register_controlling_ols_candidate(
                                    ControllingOlsCandidate(
                                        surface_id=f"OHS:{icao_code}",
                                        surface_type="OHS",
                                        footprint=QgsGeometry(ohs_final_geom),
                                        elevation_at_xy=constant_elevation_evaluator(ohs_elevation_amsl),
                                        model="constant",
                                        metadata={"elevation_m": ohs_elevation_amsl},
                                    )
                                )
                        else:
                            QgsMessageLog.logMessage(
                                "Failed create valid OHS full circle geom.",
                                plugin_tag,
                                level=Qgis.Warning,
                            )
                    except Exception as e_ohs:
                        QgsMessageLog.logMessage(
                            f"Error generating OHS: {e_ohs}",
                            plugin_tag,
                            level=Qgis.Critical,
                        )
                else:
                    QgsMessageLog.logMessage(
                        "Skipping OHS generation: Could not find ARP point.",
                        plugin_tag,
                        level=Qgis.Warning,
                    )
            else:
                QgsMessageLog.logMessage(
                    "Skipping OHS generation: Invalid parameters (Radius/Height AGL).",
                    plugin_tag,
                    level=Qgis.Warning,
                )
        else:
            QgsMessageLog.logMessage(
                "Outer Horizontal Surface not required for this airport configuration.",
                plugin_tag,
                level=Qgis.Info,
            )

        # --- 6. Generate Transitional Surfaces ---
        if ihs_base_geom and IHS_ELEVATION_AMSL is not None:
            # Note: Transitional feature generation logs its own start/finish messages inside the helper now
            # QgsMessageLog.logMessage("Generating Transitional Surface features...", plugin_tag, level=Qgis.Info) # Removed from here
            transitional_features = []
            try:
                target_crs = QgsProject.instance().crs()
                if target_crs and target_crs.isValid():
                    transitional_features, transitional_contour_features = self._generate_transitional_features(
                        processed_runway_data_list,
                        IHS_ELEVATION_AMSL,
                        target_crs,
                    )
                    if transitional_features:
                        transitional_fields = self._get_ols_fields("Transitional")
                        poly_layer = self._create_and_add_layer(
                            "Polygon",
                            f"OLS_Transitional_{icao_code}",
                            f"{self.tr('OLS')} Transitional {icao_code}",
                            transitional_fields,
                            transitional_features,
                            ols_layer_group,
                            "OLS Transitional",
                        )
                        if poly_layer is not None:
                            overall_success = True
                            # QgsMessageLog.logMessage(
                            #     f"Created Transitional Polygon Layer: {poly_layer.name()} ({len(transitional_features)} features)",
                            #     PLUGIN_TAG,
                            #     level=Qgis.Info,
                            # )

                    # --- Create Transitional Contour Line Layer ---
                    if transitional_contour_features:
                        contour_fields = self._get_transitional_contour_fields()
                        contour_layer = self._create_and_add_layer(
                            "LineString",
                            f"OLS_Transitional_Contours_{icao_code}",
                            f"{self.tr('OLS')} Transitional Contours {icao_code}",
                            contour_fields,
                            transitional_contour_features,
                            ols_layer_group,
                            "OLS Transitional Contour",
                        )
                        if contour_layer is not None:
                            overall_success = True
                            # QgsMessageLog.logMessage(
                            #     f"Created Transitional Contour Layer: {contour_layer.name()} ({len(transitional_contour_features)} features)",
                            #     PLUGIN_TAG,
                            #     level=Qgis.Info,
                            # )
                    else:
                        QgsMessageLog.logMessage(
                            f"No Transitional Contour features created for {icao_code}.",
                            PLUGIN_TAG,
                            level=Qgis.Warning,
                        )
                else:
                    QgsMessageLog.logMessage(
                        "Skipping Transitional: Invalid Project CRS.",
                        plugin_tag,
                        level=Qgis.Warning,
                    )
            except Exception as e_trans:
                QgsMessageLog.logMessage(
                    f"Error during Transitional Surface generation/layer addition: {e_trans}\n{traceback.format_exc()}",
                    plugin_tag,
                    level=Qgis.Critical,
                )
        else:
            QgsMessageLog.logMessage(
                "Skipping Transitional Surface generation: IHS geometry or elevation not available/valid.",
                plugin_tag,
                level=Qgis.Info,
            )

        # --- Final Log ---
        QgsMessageLog.logMessage("Finished Airport-Wide OLS Generation.", plugin_tag, level=Qgis.Info)
        return overall_success

    # --- Geometry Helper Methods ---

    def _get_elevation_at_point_along_gradient(
        self,
        point_xy: QgsPointXY,  # Input is QgsPointXY
        line_start_pt: QgsPointXY,
        line_end_pt: QgsPointXY,
        line_start_elev: float,
        line_end_elev: float,
        target_crs: QgsCoordinateReferenceSystem,
    ) -> Optional[float]:
        """Calculates elevation by projecting point onto line defined by start/end points/elevs."""
        plugin_tag = PLUGIN_TAG
        if None in [
            point_xy,
            line_start_pt,
            line_end_pt,
            line_start_elev,
            line_end_elev,
            target_crs,
        ]:
            return None

        epsilon = 1e-6
        if abs(line_start_pt.x() - line_end_pt.x()) < epsilon and abs(line_start_pt.y() - line_end_pt.y()) < epsilon:
            return line_start_elev

        try:
            dist_area = QgsDistanceArea()
            transform_context = QgsProject.instance().transformContext()
            dist_area.setSourceCrs(target_crs, transform_context)

            line_geom = QgsGeometry.fromPolylineXY([line_start_pt, line_end_pt])
            if line_geom.isNull():
                QgsMessageLog.logMessage(
                    "Failed elevation interpolation: Line geometry is null.",
                    plugin_tag,
                    level=Qgis.Warning,
                )
                return None

            line_length = dist_area.measureLine(line_start_pt, line_end_pt)
            if line_length < epsilon:
                return line_start_elev

            # Get the underlying primitive (should be QgsAbstractGeometry, likely QgsLineString)
            line_primitive = line_geom.constGet()  # Use constGet() for read-only access if possible
            if line_primitive is None:
                QgsMessageLog.logMessage(
                    "Failed elevation interpolation: Could not get geometry primitive.",
                    plugin_tag,
                    level=Qgis.Warning,
                )
                return None

            # Convert input point_xy to QgsPoint for closestSegment
            point_qgsp = QgsPoint(point_xy.x(), point_xy.y())

            # Call closestSegment on the primitive
            result_tuple = line_primitive.closestSegment(point_qgsp)

            if result_tuple is None or len(result_tuple) < 2:
                QgsMessageLog.logMessage(
                    "Failed elevation interpolation: closestSegment returned None or invalid tuple.",
                    plugin_tag,
                    level=Qgis.Warning,
                )
                return None

            closest_point_qgsp = result_tuple[1]

            if not isinstance(closest_point_qgsp, QgsPoint):
                QgsMessageLog.logMessage(
                    f"Failed elevation interpolation: closestSegment did not return QgsPoint as second element (got {type(closest_point_qgsp)}).",
                    plugin_tag,
                    level=Qgis.Warning,
                )
                return None

            projected_point_xy = QgsPointXY(closest_point_qgsp.x(), closest_point_qgsp.y())

            dist_along = dist_area.measureLine(line_start_pt, projected_point_xy)
            dist_along = max(0.0, min(dist_along, line_length))
            fraction_along = dist_along / line_length

            elevation_diff = line_end_elev - line_start_elev
            interpolated_elev = line_start_elev + (fraction_along * elevation_diff)

            return interpolated_elev

        except AttributeError as e_attr:
            # Specific catch for attribute errors like 'closestSegment' not found
            QgsMessageLog.logMessage(
                f"AttributeError in elevation interpolation: {e_attr}. API mismatch?",
                plugin_tag,
                level=Qgis.Critical,
            )
            return None
        except TypeError as e_type:
            QgsMessageLog.logMessage(
                f"Critical TypeError in elevation interpolation: {e_type}. Check code.",
                plugin_tag,
                level=Qgis.Critical,
            )
            return None
        except Exception as e:
            QgsMessageLog.logMessage(
                f"Warning: Error in elevation interpolation: {e}",
                plugin_tag,
                level=Qgis.Warning,
            )
            return None

    # Add this new helper function to your SafeguardingBuilder class

    def _get_polygon_side_3d_points(
        self,
        surface_geom_2d: QgsGeometry,  # The 2D polygon of IA or BLS
        centerline_start_pt_xy: QgsPointXY,
        centerline_end_pt_xy: QgsPointXY,  # For IA, this is its own end; for BLS, its own end
        start_elevation_amsl: float,  # Elevation at centerline_start_pt_xy
        end_elevation_amsl: float,  # Elevation at centerline_end_pt_xy
        start_half_width: float,
        end_half_width: float,
        side_label: str,  # 'L' or 'R'
    ) -> Optional[Tuple[QgsPoint, QgsPoint]]:  # Returns (inner_3d_pt, outer_3d_pt) for the specified side
        """
        Calculates the 3D coordinates of the inner and outer points of one side
        of a sloped trapezoidal or rectangular surface (like IA or BLS).
        'inner' means closer to the reference threshold from which the surface originates.
        'outer' means further from that reference threshold.
        """
        if not surface_geom_2d or surface_geom_2d.isEmpty() or not surface_geom_2d.isGeosValid():
            return None
        if None in [start_elevation_amsl, end_elevation_amsl]:
            return None

        # Determine the azimuth of the surface centerline
        surface_centerline_az = centerline_start_pt_xy.azimuth(centerline_end_pt_xy)
        if centerline_start_pt_xy.compare(centerline_end_pt_xy, 1e-3):
            surface_centerline_az = 0

        perp_az: float
        # This is the version that worked for your IA panels:
        side_label = side_label.upper()
        if side_label == "L":
            perp_az = (surface_centerline_az + 90.0) % 360.0  # Your "effective Left"
        elif side_label == "R":
            perp_az = (surface_centerline_az - 90.0 + 360.0) % 360.0  # Your "effective Right"
        else:
            return None

        p_inner_side_xy = centerline_start_pt_xy.project(start_half_width, perp_az)
        p_outer_side_xy = centerline_end_pt_xy.project(end_half_width, perp_az)

        if not p_inner_side_xy or not p_outer_side_xy:
            return None

        p_inner_3d = QgsPoint(p_inner_side_xy.x(), p_inner_side_xy.y(), start_elevation_amsl)
        p_outer_3d = QgsPoint(p_outer_side_xy.x(), p_outer_side_xy.y(), end_elevation_amsl)

        return p_inner_3d, p_outer_3d

    def _flip_side_label(self, side_label: str) -> str:
        return "R" if side_label.upper() == "L" else "L"

    def _define_strip_edge_segment_3d(
        self,
        p_align_ia_inner_xy: QgsPointXY,  # XY point near IA inner edge (e.g., centerline of IA inner edge)
        p_align_bls_inner_xy: QgsPointXY,  # XY point near BLS inner edge (e.g., centerline of BLS inner edge)
        strip_half_width: float,
        outward_perp_az_from_rwy_cl: float,  # Azimuth from rwy CL to this strip edge (L or R)
        rwy_primary_thr_pt: QgsPointXY,  # For overall runway gradient
        rwy_reciprocal_thr_pt: QgsPointXY,
        rwy_primary_thr_elev: float,
        rwy_reciprocal_thr_elev: float,
    ) -> Optional[Tuple[QgsPoint, QgsPoint]]:  # Returns (start_3d_on_strip, end_3d_on_strip)
        """Defines the 3D segment of the ITS base along the runway strip edge."""

        if None in [rwy_primary_thr_elev, rwy_reciprocal_thr_elev]:
            return None

        # Project to strip edge
        strip_p1_xy = p_align_ia_inner_xy.project(strip_half_width, outward_perp_az_from_rwy_cl)
        strip_p2_xy = p_align_bls_inner_xy.project(strip_half_width, outward_perp_az_from_rwy_cl)

        if not strip_p1_xy or not strip_p2_xy:
            return None

        # Get elevations along runway gradient
        z1_strip = self._get_elevation_at_point_along_gradient(
            strip_p1_xy,
            rwy_primary_thr_pt,
            rwy_reciprocal_thr_pt,
            rwy_primary_thr_elev,
            rwy_reciprocal_thr_elev,
            QgsProject.instance().crs(),
        )
        z2_strip = self._get_elevation_at_point_along_gradient(
            strip_p2_xy,
            rwy_primary_thr_pt,
            rwy_reciprocal_thr_pt,
            rwy_primary_thr_elev,
            rwy_reciprocal_thr_elev,
            QgsProject.instance().crs(),
        )

        if z1_strip is None or z2_strip is None:
            return None

        p1_strip_3d = QgsPoint(strip_p1_xy.x(), strip_p1_xy.y(), z1_strip)
        p2_strip_3d = QgsPoint(strip_p2_xy.x(), strip_p2_xy.y(), z2_strip)

        return p1_strip_3d, p2_strip_3d

    def _generate_inner_transitional_surface(
        self,
        arc_num,
        rwy_type,
        thr_point,
        azimuth,
        origin_elev,
        ofz_params,
        end_desig,
        runway_name,
    ):
        width = ofz_params.get("width")
        length = ofz_params.get("length")
        slope = ofz_params.get("slope")
        start_dist_from_thr = ofz_params.get("start_dist_from_thr")
        ref = ofz_params.get("ref", "MOS (Verify)")

        QgsMessageLog.logMessage(
            f"Entered _generate_inner_transitional_surface for {runway_name} {end_desig}",
            PLUGIN_TAG,
            Qgis.Info,
        )

        if None in [width, length, slope, start_dist_from_thr]:
            return None

        start_point = thr_point.project(start_dist_from_thr, azimuth)
        azimuth_perp_l = (azimuth - 90) % 360
        azimuth_perp_r = (azimuth + 90) % 360

        half_width = width / 2.0
        app_left = start_point.project(half_width, azimuth_perp_l)
        app_right = start_point.project(half_width, azimuth_perp_r)
        surf_left = app_left.project(length, azimuth_perp_l)
        surf_right = app_right.project(length, azimuth_perp_r)

        poly_points = [app_left, app_right, surf_right, surf_left, app_left]
        poly_geom = QgsGeometry.fromPolygonXY([poly_points])
        fields = self._get_ols_fields("InnerTransitional")
        feat = QgsFeature(fields)
        feat.setGeometry(poly_geom)
        height_agl = length * slope
        attr_map = {
            "rwy_name": runway_name,
            "surface": "Inner Transitional",
            "end_desig": end_desig,
            "elev_m": origin_elev + height_agl if origin_elev is not None else None,
            "height_agl": height_agl,
            "slope_perc": slope * 100.0,
            "ref_mos": ref,
            "len_m": length,
            "innerw_m": width,
            "outerw_m": width + 2 * length,
            "origin_offset": start_dist_from_thr,
        }
        for name, value in attr_map.items():
            idx = fields.indexFromName(name)
            if idx != -1:
                feat.setAttribute(idx, value)
        return feat

    def _generate_baulked_landing_surface(
        self,
        runway_data: dict,
        rwy_params: dict,
        thr_point: QgsPointXY,
        outward_azimuth: float,
        bls_param_dict: dict,
        end_desig: str,
        IHS_ELEVATION_AMSL: float,  # Changed from Optional to required
    ) -> Optional[Tuple[QgsFeature, QgsGeometry, float, float, QgsPointXY, float]]:
        runway_name = runway_data.get("short_name", "N/A")

        width = bls_param_dict.get("width")
        start_dist_from_thr = bls_param_dict.get("start_dist_from_thr")
        divergence = bls_param_dict.get("divergence")
        slope = bls_param_dict.get("slope")
        ref = bls_param_dict.get("ref", "MOS (Verify)")

        # Consolidate missing param check for clarity
        missing_params_list = []
        if width is None:
            missing_params_list.append("width")
        if start_dist_from_thr is None:
            missing_params_list.append("start_dist_from_thr")
        if divergence is None:
            missing_params_list.append("divergence")
        if slope is None:
            missing_params_list.append("slope")
        if IHS_ELEVATION_AMSL is None:
            missing_params_list.append("IHS_ELEVATION_AMSL")  # Should not be None if type hint is enforced

        if missing_params_list:
            self._log_debug(f"BLS {end_desig} skipped: missing inputs {', '.join(missing_params_list)}.")
            return None

        inner_edge_center_pt = thr_point.project(start_dist_from_thr, outward_azimuth)
        if not inner_edge_center_pt:
            self._log_debug(f"BLS {end_desig} skipped: failed to calculate inner edge centre.")
            return None

        required_rwy_keys = ["thr_point", "rec_thr_point", "threshold_elev_1", "threshold_elev_2"]
        if not all(key in runway_data and runway_data[key] is not None for key in required_rwy_keys):
            self._log_debug(f"BLS {end_desig} skipped: runway data missing keys for elevation calculation.")
            return None

        inner_edge_elev_amsl = self._get_elevation_at_point_along_gradient(
            inner_edge_center_pt,
            runway_data.get("thr_point"),
            runway_data.get("rec_thr_point"),
            runway_data.get("threshold_elev_1"),
            runway_data.get("threshold_elev_2"),
            QgsProject.instance().crs(),
        )
        if inner_edge_elev_amsl is None:
            self._log_debug(f"BLS {end_desig} skipped: inner edge elevation unavailable.")
            return None

        height_to_gain = IHS_ELEVATION_AMSL - inner_edge_elev_amsl
        calculated_length: float
        if height_to_gain <= 0:
            calculated_length = 0.0
        elif slope <= 1e-9:  # Using a small epsilon for float comparison
            return None
        else:
            calculated_length = height_to_gain / slope

        if (
            calculated_length < -1e-9
        ):  # Allow for very small negative due to float precision if height_to_gain is near zero
            self._log_debug(f"BLS {end_desig} skipped: negative calculated length {calculated_length:.3f} m.")
            return None

        # If calculated_length is 0 (starts at/above IHS), still create a degenerate feature or handle as per requirements.
        # For now, let's assume a zero-length surface is acceptable if it starts at/above IHS.

        half_width_inner = width / 2.0
        # If calculated_length is 0, final_width will be equal to width.
        final_width = width + (2 * calculated_length * divergence)
        half_width_outer = final_width / 2.0

        bls_geom = self._create_trapezoid(
            inner_edge_center_pt,
            outward_azimuth,
            calculated_length,
            half_width_inner,
            half_width_outer,
            f"Baulked Landing {end_desig}",
        )

        if not bls_geom or bls_geom.isEmpty() or not bls_geom.isGeosValid():
            # If calculated_length was 0, _create_trapezoid might return None or an empty/invalid geometry.
            # Decide if this is an error or if a degenerate (e.g., line) feature should be made.
            # For now, if it's not a valid polygon, we return None.
            if calculated_length <= 1e-9:  # If length was effectively zero
                self._log_debug(f"BLS {end_desig} skipped: calculated length is zero.")
            else:
                self._log_debug(f"BLS {end_desig} skipped: generated polygon is invalid.")
            return None

        # --- Feature Creation ---
        fields = self._get_ols_fields("BaulkedLanding")
        feature = QgsFeature(fields)
        feature.setGeometry(bls_geom)

        height_agl_val = calculated_length * slope
        elev_m_val = IHS_ELEVATION_AMSL  # Outer edge is at IHS

        attr_map = {
            "rwy_name": runway_name,
            "surface": "Baulked Landing",
            "end_desig": end_desig,
            "elev_m": elev_m_val,
            "height_agl": height_agl_val,
            "slope_perc": slope * 100.0,
            "ref_mos": ref,
            "len_m": calculated_length,
            "innerw_m": width,
            "outerw_m": final_width,
            "divergence_perc": divergence * 100.0,
            "origin_offset": start_dist_from_thr,
        }
        for name, value in attr_map.items():
            idx = fields.indexFromName(name)
            if idx != -1:
                feature.setAttribute(idx, value)

        return (
            feature,
            bls_geom,
            calculated_length,
            inner_edge_elev_amsl,
            inner_edge_center_pt,
            final_width,
        )

    def _generate_its_panel_feature(
        self,
        base_p1_3d: QgsPoint,
        base_p2_3d: QgsPoint,
        its_slope: float,
        IHS_ELEVATION_AMSL: float,
        outward_projection_azimuth: float,
        runway_name: str,
        end_desig: str,
        side_label: str,
        panel_description: str,
        ref_mos: str,
        ols_fields: QgsFields,
    ) -> Optional[QgsFeature]:
        plugin_tag = PLUGIN_TAG

        # --- CORRECTED Z CHECK ---
        z1_base_val = base_p1_3d.z()
        z2_base_val = base_p2_3d.z()

        # Check if Z values are None or not finite (e.g., NaN, Inf)
        # math.isfinite() is good for this.
        if not (
            isinstance(z1_base_val, (int, float))
            and math.isfinite(z1_base_val)
            and isinstance(z2_base_val, (int, float))
            and math.isfinite(z2_base_val)
        ):
            QgsMessageLog.logMessage(
                f"ITS Panel Gen Error for {panel_description} {end_desig} {side_label}: Base points have invalid or missing Z values (P1_Z: {z1_base_val}, P2_Z: {z2_base_val}).",
                plugin_tag,
                Qgis.Warning,
            )
            return None
        # --- END CORRECTED Z CHECK ---

        p1_base_xy = QgsPointXY(base_p1_3d.x(), base_p1_3d.y())
        p2_base_xy = QgsPointXY(base_p2_3d.x(), base_p2_3d.y())
        # z1_base and z2_base are now confirmed to be valid floats
        z1_base = z1_base_val
        z2_base = z2_base_val

        if z1_base >= IHS_ELEVATION_AMSL - 1e-6 and z2_base >= IHS_ELEVATION_AMSL - 1e-6:
            return None

        if its_slope <= 1e-9:
            QgsMessageLog.logMessage(
                f"ITS Panel Gen Error for {panel_description} {end_desig} {side_label}: ITS slope is zero or negative.",
                plugin_tag,
                Qgis.Warning,
            )
            return None

        h_dist1 = (IHS_ELEVATION_AMSL - z1_base) / its_slope if z1_base < IHS_ELEVATION_AMSL else 0.0
        h_dist2 = (IHS_ELEVATION_AMSL - z2_base) / its_slope if z2_base < IHS_ELEVATION_AMSL else 0.0
        h_dist1 = max(0.0, h_dist1)
        h_dist2 = max(0.0, h_dist2)

        p1_top_xy = p1_base_xy.project(h_dist1, outward_projection_azimuth)
        p2_top_xy = p2_base_xy.project(h_dist2, outward_projection_azimuth)

        if not p1_top_xy or not p2_top_xy:
            QgsMessageLog.logMessage(
                f"ITS Panel Gen Error for {panel_description} {end_desig} {side_label}: Failed to project top points.",
                plugin_tag,
                Qgis.Warning,
            )
            return None

        if p1_base_xy.compare(p2_base_xy, epsilon=1e-3):
            if h_dist1 <= 1e-3 and h_dist2 <= 1e-3:
                return None

        if h_dist1 < 1e-3 and h_dist2 < 1e-3 and p1_base_xy.distance(p2_base_xy) < 1e-3:
            return None

        panel_corners_xy = [p1_base_xy, p2_base_xy, p2_top_xy, p1_top_xy]
        panel_geom = self._create_polygon_from_corners(
            panel_corners_xy, f"ITS Panel {panel_description} {end_desig} {side_label}"
        )

        if not panel_geom or panel_geom.isEmpty() or not panel_geom.isGeosValid():
            return None

        feature = QgsFeature(ols_fields)
        feature.setGeometry(panel_geom)
        avg_base_elev = (z1_base + z2_base) / 2.0
        height_gain_panel = IHS_ELEVATION_AMSL - avg_base_elev if avg_base_elev < IHS_ELEVATION_AMSL else 0.0

        attr_map = {
            "rwy_name": runway_name,
            "surface": "Inner Transitional",
            "end_desig": end_desig,
            "section_desc": panel_description,
            "elev_m": IHS_ELEVATION_AMSL,
            "height_agl": height_gain_panel,
            "slope_perc": its_slope * 100.0,
            "ref_mos": ref_mos,
            "side": side_label,
        }
        final_attr_map = {k: v for k, v in attr_map.items() if ols_fields.indexFromName(k) != -1}
        for name, value in final_attr_map.items():
            feature.setAttribute(ols_fields.indexFromName(name), value)

        return feature

    def _generate_parallel_contours_in_panel(
        self,
        top_start: QgsPointXY,
        top_end: QgsPointXY,
        IHS_ELEVATION_AMSL: float,
        base_start: QgsPointXY,
        base_end: QgsPointXY,
        z_start: float,
        z_end: float,
        transitional_slope: float,
        contour_fields: QgsFields,
        contour_interval: float,
        panel_geom: QgsGeometry,
        section_desc: str,
        side_label: str,
        runway_name: str,
        end_desig: str,
        transitional_ref: str,
        surface_id: Optional[str] = None,
    ) -> list:
        """
        For an approach-adjacent panel, generate contour lines at regular intervals parallel to the top edge,
        clipped to the panel polygon. Dynamically detects the 'downhill' direction.
        """
        contours = []
        min_panel_elev = min(z_start, z_end)
        max_panel_elev = IHS_ELEVATION_AMSL

        # Top edge direction vector (from top_start to top_end)
        dx = top_end.x() - top_start.x()
        dy = top_end.y() - top_start.y()
        top_len = (dx**2 + dy**2) ** 0.5
        if top_len == 0:
            return []  # Avoid division by zero
        ux, uy = dx / top_len, dy / top_len

        # Two possible normals: one points 'down', the other 'up'
        normals = [(-uy, ux), (uy, -ux)]
        extra = 2 * top_len

        # Figure out which normal points inside the polygon by testing the first contour
        first_contour_elev = max(
            contour_interval,
            contour_interval * (int(min_panel_elev // contour_interval) + 1),
        )
        direction_found = False
        for nx, ny in normals:
            delta_z = max_panel_elev - first_contour_elev
            offset = delta_z / transitional_slope
            long_pt1 = QgsPointXY(
                top_start.x() + nx * offset - ux * extra,
                top_start.y() + ny * offset - uy * extra,
            )
            long_pt2 = QgsPointXY(
                top_end.x() + nx * offset + ux * extra,
                top_end.y() + ny * offset + uy * extra,
            )
            test_geom = QgsGeometry.fromPolylineXY([long_pt1, long_pt2])
            clipped = test_geom.intersection(panel_geom)
            if not clipped.isEmpty():
                # This normal points into the panel
                direction_found = True
                break
        if not direction_found:
            # If neither normal yields a valid contour, return nothing
            return contours

        # Now generate all contours in the selected direction
        current_z = first_contour_elev
        while current_z < max_panel_elev - 1e-6:
            delta_z = max_panel_elev - current_z
            offset = delta_z / transitional_slope
            pt1 = QgsPointXY(
                top_start.x() + nx * offset - ux * extra,
                top_start.y() + ny * offset - uy * extra,
            )
            pt2 = QgsPointXY(
                top_end.x() + nx * offset + ux * extra,
                top_end.y() + ny * offset + uy * extra,
            )
            line_geom = QgsGeometry.fromPolylineXY([pt1, pt2])
            clipped = line_geom.intersection(panel_geom)
            if clipped.isEmpty():
                current_z += contour_interval
                continue

            # Handle multipart or single part
            geoms = []
            if clipped.isMultipart():
                geoms = [QgsGeometry.fromPolylineXY(line) for line in clipped.asMultiPolyline()]
            elif clipped.type() == QgsWkbTypes.LineGeometry:
                geoms = [clipped]
            else:
                current_z += contour_interval
                continue

            for g in geoms:
                if g.length() < 1e-3:
                    continue
                feat = QgsFeature(contour_fields)
                feat.setGeometry(g)
                attr_map = {
                    "rwy_name": runway_name,
                    "surface": "Transitional",
                    "section_desc": section_desc,
                    "side": side_label,
                    "end_desig": end_desig,
                    "contour_elev_am": current_z,
                    "ref_mos": transitional_ref,
                    "surface_id": surface_id,
                }
                for name, value in attr_map.items():
                    idx = contour_fields.indexFromName(name)
                    if idx != -1:
                        feat.setAttribute(idx, value)
                contours.append(feat)

            current_z += contour_interval

        return contours

    def _make_transitional_contour_feature(
        self,
        geom: QgsGeometry,
        contour_fields: QgsFields,
        runway_name: str,
        section_desc: str,
        contour_elevation: Optional[float],
        side_label: Optional[str] = None,
        end_desig: Optional[str] = None,
        transitional_ref: Optional[str] = None,
        surface_id: Optional[str] = None,
    ) -> Optional[QgsFeature]:
        """Create a labelled transitional contour/edge feature."""
        if geom is None or geom.isEmpty():
            return None
        feat = QgsFeature(contour_fields)
        feat.setGeometry(geom)
        attr_map = {
            "rwy_name": runway_name,
            "surface": "Transitional",
            "section_desc": section_desc,
            "side": side_label,
            "end_desig": end_desig,
            "contour_elev_am": contour_elevation,
            "ref_mos": transitional_ref,
            "surface_id": surface_id,
        }
        for name, value in attr_map.items():
            idx = contour_fields.indexFromName(name)
            if idx != -1:
                feat.setAttribute(idx, value)
        return feat

    def _plane_coefficients_from_points(
        self,
        first_xy: QgsPointXY,
        first_z: float,
        second_xy: QgsPointXY,
        second_z: float,
        third_xy: QgsPointXY,
        third_z: float,
    ) -> Optional[Tuple[float, float, float]]:
        """Return z = ax + by + c through three non-collinear 3D points."""
        determinant = (
            first_xy.x() * (second_xy.y() - third_xy.y())
            + second_xy.x() * (third_xy.y() - first_xy.y())
            + third_xy.x() * (first_xy.y() - second_xy.y())
        )
        if abs(determinant) <= 1e-9:
            return None

        a = (
            first_z * (second_xy.y() - third_xy.y())
            + second_z * (third_xy.y() - first_xy.y())
            + third_z * (first_xy.y() - second_xy.y())
        ) / determinant
        b = (
            first_xy.x() * (second_z - third_z)
            + second_xy.x() * (third_z - first_z)
            + third_xy.x() * (first_z - second_z)
        ) / determinant
        c = (
            first_xy.x() * (second_xy.y() * third_z - third_xy.y() * second_z)
            + second_xy.x() * (third_xy.y() * first_z - first_xy.y() * third_z)
            + third_xy.x() * (first_xy.y() * second_z - second_xy.y() * first_z)
        ) / determinant
        return a, b, c

    def _register_transitional_controlling_candidate(
        self,
        geom: QgsGeometry,
        runway_name: str,
        section_desc: str,
        side_label: str,
        sequence: int,
        first_xy: QgsPointXY,
        first_z: float,
        second_xy: QgsPointXY,
        second_z: float,
        third_xy: QgsPointXY,
        third_z: float,
        metadata: Optional[dict] = None,
    ) -> Optional[str]:
        """Register a generated transitional panel as a generic planar controlling candidate."""
        if not hasattr(self, "_register_controlling_ols_candidate"):
            return None
        if geom is None or geom.isEmpty():
            return None
        if any(value is None for value in [first_xy, second_xy, third_xy, first_z, second_z, third_z]):
            return None
        plane = self._plane_coefficients_from_points(first_xy, first_z, second_xy, second_z, third_xy, third_z)
        if plane is None:
            return None
        safe_runway_name = str(runway_name or "RWY").replace("/", "-").replace(" ", "_")
        safe_side = str(side_label or "").replace(" ", "_")
        surface_id = f"TRANS:{safe_runway_name}:{safe_side}:{sequence}"
        candidate_metadata = {
            "plane_a": plane[0],
            "plane_b": plane[1],
            "plane_c": plane[2],
            "runway_name": runway_name,
            "section_desc": section_desc,
            "side": side_label,
        }
        if metadata:
            candidate_metadata.update(metadata)
        self._register_controlling_ols_candidate(
            ControllingOlsCandidate(
                surface_id=surface_id,
                surface_type="Transitional",
                footprint=QgsGeometry(geom),
                elevation_at_xy=plane_elevation_evaluator(*plane),
                model="plane",
                metadata=candidate_metadata,
            )
        )
        return surface_id

    def _generate_transitional_features(
        self,
        processed_runway_data_list: List[dict],
        IHS_ELEVATION_AMSL: float,
        target_crs: QgsCoordinateReferenceSystem,
    ) -> Tuple[List[QgsFeature], List[QgsFeature]]:
        """
        Generates polygon features for main Transitional OLS and contour line features.
        Returns (polygon_features, contour_features)
        """
        plugin_tag = PLUGIN_TAG
        QgsMessageLog.logMessage(
            "Starting Transitional Surface feature generation...",
            plugin_tag,
            level=Qgis.Info,
        )

        transitional_features: List[QgsFeature] = []
        transitional_contour_features: List[QgsFeature] = []
        transitional_fields = self._get_ols_fields("Transitional")
        contour_fields = self._get_transitional_contour_fields()
        contour_interval = self._get_contour_interval("transitional", TRANSITIONAL_CONTOUR_INTERVAL)
        transitional_candidate_sequence = 0

        if IHS_ELEVATION_AMSL is None:
            QgsMessageLog.logMessage(
                "Skipping Transitional features: IHS Elevation is missing.",
                plugin_tag,
                level=Qgis.Warning,
            )
            return [], []

        approach_edges_cache = {}

        # --- Pass 1: Pre-calculate Approach Section Edge Geometries for Lookups ---
        for runway_data in processed_runway_data_list:
            runway_name = runway_data.get("short_name")
            thr_point = runway_data.get("thr_point")
            rec_thr_point = runway_data.get("rec_thr_point")
            arc_num_str = runway_data.get("arc_num")
            type1_str = runway_data.get("type1")
            type2_str = runway_data.get("type2")
            if not all([runway_name, thr_point, rec_thr_point, arc_num_str]):
                continue
            try:
                arc_num = int(arc_num_str)
            except ValueError:
                continue
            rwy_params = self._get_runway_parameters(thr_point, rec_thr_point)
            if not rwy_params:
                continue
            primary_desig, reciprocal_desig = runway_name.split("/") if "/" in runway_name else ("THR1", "THR2")
            for end_idx, (end_desig, end_type, end_thr_pt, outward_az) in enumerate(
                [
                    (primary_desig, type1_str, thr_point, rwy_params["azimuth_r_p"]),
                    (
                        reciprocal_desig,
                        type2_str,
                        rec_thr_point,
                        rwy_params["azimuth_p_r"],
                    ),
                ]
            ):
                approach_sections_params = ols_dimensions.get_ols_params(arc_num, end_type, "APPROACH")
                if not approach_sections_params:
                    continue
                current_section_start_pt = None
                current_section_start_width = 0.0
                for i, section_params in enumerate(approach_sections_params):
                    length = section_params.get("length", 0.0)
                    divergence = section_params.get("divergence", 0.0)
                    if length <= 0:
                        continue
                    if i == 0:
                        start_dist = section_params.get("start_dist_from_thr", 0.0)
                        start_width = section_params.get("start_width", 0.0)
                        if start_width <= 0:
                            break
                        current_section_start_pt = end_thr_pt.project(start_dist, outward_az)
                        current_section_start_width = start_width
                    else:
                        if current_section_start_pt is None:
                            break
                    if not current_section_start_pt:
                        break
                    start_hw = current_section_start_width / 2.0
                    end_width = current_section_start_width + (2 * length * divergence)
                    end_hw = end_width / 2.0
                    end_pt = current_section_start_pt.project(length, outward_az)
                    if not end_pt:
                        break
                    az_perp_l = (outward_az + 270.0) % 360.0
                    az_perp_r = (outward_az + 90.0) % 360.0
                    p_start_l = current_section_start_pt.project(start_hw, az_perp_l)
                    p_start_r = current_section_start_pt.project(start_hw, az_perp_r)
                    p_end_l = end_pt.project(end_hw, az_perp_l)
                    p_end_r = end_pt.project(end_hw, az_perp_r)
                    if all([p_start_l, p_end_l, p_start_r, p_end_r]):
                        edge_l = QgsLineString([p_start_l, p_end_l])
                        edge_r = QgsLineString([p_start_r, p_end_r])
                        approach_edges_cache[(runway_name, end_desig, i, "L")] = edge_l
                        approach_edges_cache[(runway_name, end_desig, i, "R")] = edge_r
                    current_section_start_pt = end_pt
                    current_section_start_width = end_width

        # --- Pass 2: Generate Transitional Features ---

        for runway_data in processed_runway_data_list:
            runway_name = runway_data.get("short_name")
            thr_point = runway_data.get("thr_point")
            rec_thr_point = runway_data.get("rec_thr_point")
            thr_elev = runway_data.get("threshold_elev_1")
            rec_thr_elev = runway_data.get("threshold_elev_2")
            runway_end_elev = runway_data.get("runway_end_elev_1")
            rec_runway_end_elev = runway_data.get("runway_end_elev_2")
            arc_num_str = runway_data.get("arc_num")
            type1_str = runway_data.get("type1")
            type2_str = runway_data.get("type2")
            calculated_strip_dims = runway_data.get("calculated_strip_dims")
            disp_at_primary_thr = float(runway_data.get("thr_displaced_1", 0.0) or 0.0)
            disp_at_reciprocal_thr = float(runway_data.get("thr_displaced_2", 0.0) or 0.0)
            stopway_at_primary_end = float(runway_data.get("stopway1_len", 0.0) or 0.0)
            stopway_at_reciprocal_end = float(runway_data.get("stopway2_len", 0.0) or 0.0)

            if not all(
                [
                    runway_name,
                    thr_point,
                    rec_thr_point,
                    arc_num_str,
                    calculated_strip_dims,
                    thr_elev is not None,
                    rec_thr_elev is not None,
                    runway_end_elev is not None,
                    rec_runway_end_elev is not None,
                ]
            ):
                QgsMessageLog.logMessage(
                    f"Skipping Transitional features for {runway_name}: Missing required data.",
                    plugin_tag,
                    level=Qgis.Warning,
                )
                continue
            try:
                arc_num = int(arc_num_str)
            except ValueError:
                QgsMessageLog.logMessage(
                    f"Skipping Transitional features for {runway_name}: Invalid ARC.",
                    plugin_tag,
                    level=Qgis.Warning,
                )
                continue
            rwy_params = self._get_runway_parameters(thr_point, rec_thr_point)
            if not rwy_params or rwy_params["length"] < 1e-6:
                QgsMessageLog.logMessage(
                    f"Skipping Transitional features for {runway_name}: Invalid runway params.",
                    plugin_tag,
                    level=Qgis.Warning,
                )
                continue
            physical_endpoints = self._get_physical_runway_endpoints(
                thr_point,
                rec_thr_point,
                disp_at_primary_thr,
                disp_at_reciprocal_thr,
                rwy_params,
            )
            if physical_endpoints is None:
                QgsMessageLog.logMessage(
                    f"Skipping Transitional features for {runway_name}: Failed physical runway end points.",
                    plugin_tag,
                    level=Qgis.Warning,
                )
                continue
            phys_end_p, phys_end_r, _ = physical_endpoints
            primary_desig, reciprocal_desig = runway_name.split("/") if "/" in runway_name else ("THR1", "THR2")

            # --- Get Transitional Slope ---
            type_abbr_1 = ols_dimensions.get_runway_type_abbr(type1_str)
            type_abbr_2 = ols_dimensions.get_runway_type_abbr(type2_str)
            type_order_abbr = ["", "NI", "NPA", "PA_I", "PA_II_III"]
            type_order_full = [
                "",
                "Non-Instrument (NI)",
                "Non-Precision Approach (NPA)",
                "Precision Approach CAT I",
                "Precision Approach CAT II/III",
            ]
            try:
                idx1 = type_order_abbr.index(type_abbr_1)
            except ValueError:
                idx1 = 1
            try:
                idx2 = type_order_abbr.index(type_abbr_2)
            except ValueError:
                idx2 = 1
            governing_type_index = max(idx1, idx2)
            if governing_type_index < len(type_order_full):
                governing_type_str_full = (
                    type_order_full[governing_type_index]
                    if type_order_full[governing_type_index]
                    else "Non-Instrument (NI)"
                )
            else:
                governing_type_str_full = "Non-Instrument (NI)"
            trans_params = ols_dimensions.get_ols_params(arc_num, governing_type_str_full, "Transitional")
            if not trans_params or "slope" not in trans_params or trans_params["slope"] <= 1e-9:
                QgsMessageLog.logMessage(
                    f"Skipping Transitional features for {runway_name}: No valid slope found for classification ('{governing_type_str_full}').",
                    plugin_tag,
                    level=Qgis.Warning,
                )
                continue
            transitional_slope = trans_params["slope"]
            transitional_ref = trans_params.get("ref", "MOS 8.2.17 (Verify)")

            # --- Strip-Adjacent Sides (original rectangular logic) ---
            strip_overall_width = calculated_strip_dims.get("overall_width")
            strip_extension = calculated_strip_dims.get("extension_length")
            if strip_overall_width is None or strip_extension is None:
                QgsMessageLog.logMessage(
                    f"Skipping Transitional features for {runway_name}: Missing calc strip dims.",
                    plugin_tag,
                    level=Qgis.Warning,
                )
                continue
            strip_overall_half_width = strip_overall_width / 2.0
            strip_end_p = phys_end_p.project(strip_extension, rwy_params["azimuth_r_p"])
            strip_end_r = phys_end_r.project(strip_extension, rwy_params["azimuth_p_r"])
            if not strip_end_p or not strip_end_r:
                QgsMessageLog.logMessage(
                    f"Skipping Transitional features for {runway_name}: Failed strip end points.",
                    plugin_tag,
                    level=Qgis.Warning,
                )
                continue
            primary_stopway_end = (
                phys_end_p.project(min(stopway_at_primary_end, strip_extension), rwy_params["azimuth_r_p"])
                if stopway_at_primary_end > 1e-6
                else None
            )
            reciprocal_stopway_end = (
                phys_end_r.project(min(stopway_at_reciprocal_end, strip_extension), rwy_params["azimuth_p_r"])
                if stopway_at_reciprocal_end > 1e-6
                else None
            )

            def _approach_inner_boundary(
                end_type: str,
                end_thr_pt: QgsPointXY,
                end_thr_elev: float,
                outward_az: float,
                end_desig: str,
            ) -> Optional[Tuple[QgsPointXY, float]]:
                approach_params = ols_dimensions.get_ols_params(arc_num, end_type, "APPROACH")
                if not approach_params:
                    QgsMessageLog.logMessage(
                        f"Transitional strip clipping skipped for {runway_name} {end_desig}: no approach params.",
                        plugin_tag,
                        level=Qgis.Warning,
                    )
                    return None
                start_dist = approach_params[0].get("start_dist_from_thr", 0.0)
                boundary_pt = end_thr_pt.project(start_dist, outward_az)
                if not boundary_pt:
                    QgsMessageLog.logMessage(
                        f"Transitional strip clipping skipped for {runway_name} {end_desig}: failed approach inner-edge projection.",
                        plugin_tag,
                        level=Qgis.Warning,
                    )
                    return None
                return boundary_pt, end_thr_elev

            primary_approach_inner = _approach_inner_boundary(
                type1_str,
                thr_point,
                thr_elev,
                rwy_params["azimuth_r_p"],
                primary_desig,
            )
            reciprocal_approach_inner = _approach_inner_boundary(
                type2_str,
                rec_thr_point,
                rec_thr_elev,
                rwy_params["azimuth_p_r"],
                reciprocal_desig,
            )

            strip_breakpoints = [
                (strip_end_p, runway_end_elev),
                (primary_stopway_end, runway_end_elev),
                (phys_end_p, runway_end_elev),
                primary_approach_inner if primary_approach_inner else (None, None),
                (thr_point, thr_elev),
                (rec_thr_point, rec_thr_elev),
                reciprocal_approach_inner if reciprocal_approach_inner else (None, None),
                (phys_end_r, rec_runway_end_elev),
                (reciprocal_stopway_end, rec_runway_end_elev),
                (strip_end_r, rec_runway_end_elev),
            ]
            axis_azimuth_rad = math.radians(rwy_params["azimuth_p_r"])
            axis_x = math.sin(axis_azimuth_rad)
            axis_y = math.cos(axis_azimuth_rad)

            def _strip_station(point_xy: QgsPointXY) -> float:
                return ((point_xy.x() - strip_end_p.x()) * axis_x) + ((point_xy.y() - strip_end_p.y()) * axis_y)

            ordered_strip_breakpoints = []
            for point_xy, elev in sorted(
                ((pt, elev) for pt, elev in strip_breakpoints if pt is not None and elev is not None),
                key=lambda item: _strip_station(item[0]),
            ):
                if ordered_strip_breakpoints:
                    prev_pt, _ = ordered_strip_breakpoints[-1]
                    if point_xy.distance(prev_pt) < 1e-3:
                        ordered_strip_breakpoints[-1] = (point_xy, elev)
                        continue
                ordered_strip_breakpoints.append((point_xy, elev))

            if primary_approach_inner and reciprocal_approach_inner:
                primary_limit = _strip_station(primary_approach_inner[0])
                reciprocal_limit = _strip_station(reciprocal_approach_inner[0])
                lower_limit = min(primary_limit, reciprocal_limit)
                upper_limit = max(primary_limit, reciprocal_limit)
                ordered_strip_breakpoints = [
                    (point_xy, elev)
                    for point_xy, elev in ordered_strip_breakpoints
                    if lower_limit - 1e-3 <= _strip_station(point_xy) <= upper_limit + 1e-3
                ]

            if len(ordered_strip_breakpoints) < 2:
                QgsMessageLog.logMessage(
                    f"Skipping Transitional features for {runway_name}: Failed strip segment points.",
                    plugin_tag,
                    level=Qgis.Warning,
                )
                continue

            if hasattr(self, "_register_controlling_ols_exclusion_geometry"):
                for exclusion_index, ((cl_start, _), (cl_end, _)) in enumerate(
                    zip(ordered_strip_breakpoints[:-1], ordered_strip_breakpoints[1:]),
                    start=1,
                ):
                    if cl_start.distance(cl_end) < 1e-3:
                        continue
                    start_left = cl_start.project(strip_overall_half_width, rwy_params["azimuth_perp_l"])
                    end_left = cl_end.project(strip_overall_half_width, rwy_params["azimuth_perp_l"])
                    end_right = cl_end.project(strip_overall_half_width, rwy_params["azimuth_perp_r"])
                    start_right = cl_start.project(strip_overall_half_width, rwy_params["azimuth_perp_r"])
                    if not all([start_left, end_left, end_right, start_right]):
                        continue
                    exclusion_geom = self._create_polygon_from_corners(
                        [start_left, end_left, end_right, start_right],
                        f"No OLS strip core {runway_name} S{exclusion_index}",
                    )
                    if exclusion_geom and not exclusion_geom.isEmpty():
                        self._register_controlling_ols_exclusion_geometry(exclusion_geom)

            # --- Generate Strip Transitional Sides ---
            for side_label, outward_azimuth in [
                ("L", rwy_params["azimuth_perp_l"]),
                ("R", rwy_params["azimuth_perp_r"]),
            ]:
                for segment_index, ((cl_start, z_start), (cl_end, z_end)) in enumerate(
                    zip(ordered_strip_breakpoints[:-1], ordered_strip_breakpoints[1:]),
                    start=1,
                ):
                    if cl_start.distance(cl_end) < 1e-3:
                        continue
                    p_start_xy = cl_start.project(strip_overall_half_width, outward_azimuth)
                    p_end_xy = cl_end.project(strip_overall_half_width, outward_azimuth)
                    if not p_start_xy or not p_end_xy:
                        continue
                    if z_start >= IHS_ELEVATION_AMSL and z_end >= IHS_ELEVATION_AMSL:
                        continue
                    h_dist_start = max(0.0, (IHS_ELEVATION_AMSL - z_start) / transitional_slope)
                    h_dist_end = max(0.0, (IHS_ELEVATION_AMSL - z_end) / transitional_slope)
                    p_upper_start = p_start_xy.project(h_dist_start, outward_azimuth)
                    p_upper_end = p_end_xy.project(h_dist_end, outward_azimuth)
                    if not p_upper_start or not p_upper_end:
                        continue
                    corners = [p_start_xy, p_end_xy, p_upper_end, p_upper_start]
                    poly_geom = self._create_polygon_from_corners(
                        corners, f"Trans Strip {side_label} {runway_name} S{segment_index}"
                    )
                    if poly_geom:
                        feat = QgsFeature(transitional_fields)
                        feat.setGeometry(poly_geom)
                        attr_map = {
                            "rwy_name": runway_name,
                            "surface": "Transitional",
                            "section_desc": "Transitional Strip Adjacent Surface",
                            "elev_m": IHS_ELEVATION_AMSL,
                            "height_agl": IHS_ELEVATION_AMSL - min(z_start, z_end),
                            "side": side_label,
                            "slope_perc": transitional_slope * 100.0,
                            "ref_mos": transitional_ref,
                        }
                        for name, value in attr_map.items():
                            idx = transitional_fields.indexFromName(name)
                            if idx != -1:
                                feat.setAttribute(idx, value)
                        transitional_features.append(feat)
                        transitional_candidate_sequence += 1
                        transitional_surface_id = self._register_transitional_controlling_candidate(
                            poly_geom,
                            runway_name,
                            "Transitional Strip Adjacent Surface",
                            side_label,
                            transitional_candidate_sequence,
                            p_start_xy,
                            z_start,
                            p_end_xy,
                            z_end,
                            p_upper_start,
                            IHS_ELEVATION_AMSL,
                            metadata={
                                "slope": transitional_slope,
                                "ref_mos": transitional_ref,
                                "segment_index": segment_index,
                            },
                        )

                        lower_edge = self._make_transitional_contour_feature(
                            QgsGeometry.fromPolylineXY([p_start_xy, p_end_xy]),
                            contour_fields,
                            runway_name,
                            "Transitional Strip Adjacent Surface",
                            z_start if abs(z_start - z_end) < 0.05 else None,
                            side_label=side_label,
                            transitional_ref=transitional_ref,
                            surface_id=transitional_surface_id,
                        )
                        upper_edge = self._make_transitional_contour_feature(
                            QgsGeometry.fromPolylineXY([p_upper_start, p_upper_end]),
                            contour_fields,
                            runway_name,
                            "Transitional Strip Adjacent Surface",
                            IHS_ELEVATION_AMSL,
                            side_label=side_label,
                            transitional_ref=transitional_ref,
                            surface_id=transitional_surface_id,
                        )
                        edge_contours = [feature for feature in [lower_edge, upper_edge] if feature is not None]
                        if transitional_surface_id and hasattr(self, "_register_controlling_ols_contour"):
                            for contour_feature in edge_contours:
                                self._register_controlling_ols_contour(
                                    transitional_surface_id,
                                    "Transitional",
                                    contour_feature,
                                    "OLS Transitional Contour",
                                )
                        transitional_contour_features.extend(edge_contours)

                        strip_contours = self._generate_transitional_strip_contours(
                            base_start=p_start_xy,
                            base_end=p_end_xy,
                            top_start=p_upper_start,
                            top_end=p_upper_end,
                            z_start=z_start,
                            z_end=z_end,
                            IHS_ELEVATION_AMSL=IHS_ELEVATION_AMSL,
                            contour_fields=contour_fields,
                            contour_interval=contour_interval,
                            section_desc="Transitional Strip Adjacent Surface",
                            side_label=side_label,
                            runway_name=runway_name,
                            transitional_ref=transitional_ref,
                            bounding_polygon=poly_geom,
                            surface_id=transitional_surface_id,
                        )
                        if transitional_surface_id and hasattr(self, "_register_controlling_ols_contour"):
                            for contour_feature in strip_contours:
                                self._register_controlling_ols_contour(
                                    transitional_surface_id,
                                    "Transitional",
                                    contour_feature,
                                    "OLS Transitional Contour",
                                )
                        transitional_contour_features.extend(strip_contours)

            # --- Approach-Adjacent Transitional Surfaces (this section is updated) ---
            for end_idx, (
                end_desig,
                end_type,
                end_thr_pt,
                end_thr_elev,
                outward_az,
            ) in enumerate(
                [
                    (
                        primary_desig,
                        type1_str,
                        thr_point,
                        thr_elev,
                        rwy_params["azimuth_r_p"],
                    ),
                    (
                        reciprocal_desig,
                        type2_str,
                        rec_thr_point,
                        rec_thr_elev,
                        rwy_params["azimuth_p_r"],
                    ),
                ]
            ):
                approach_sections_params = ols_dimensions.get_ols_params(arc_num, end_type, "APPROACH")
                if not approach_sections_params:
                    continue

                current_section_start_elev = end_thr_elev
                current_section_start_pt_ctr = None
                prev_section_length = 0.0

                for i, section_params in enumerate(approach_sections_params):
                    section_length = section_params.get("length", 0.0)
                    section_slope = section_params.get("slope", 0.0)
                    section_params.get("divergence", 0.0)
                    if section_length <= 0:
                        continue
                    if i == 0:
                        start_dist = section_params.get("start_dist_from_thr", 0.0)
                        current_section_start_pt_ctr = end_thr_pt.project(start_dist, outward_az)
                    else:
                        if current_section_start_pt_ctr:
                            current_section_start_pt_ctr = current_section_start_pt_ctr.project(
                                prev_section_length, outward_az
                            )
                        else:
                            break
                    if not current_section_start_pt_ctr:
                        break
                    section_end_elev = (
                        (current_section_start_elev + section_length * section_slope)
                        if current_section_start_elev is not None
                        else None
                    )
                    if section_end_elev is None:
                        continue
                    for side_label, outward_perp_azimuth in [
                        ("L", (outward_az + 270.0) % 360.0),
                        ("R", (outward_az + 90.0) % 360.0),
                    ]:
                        approach_edge = approach_edges_cache.get((runway_name, end_desig, i, side_label))
                        if not approach_edge or approach_edge.isEmpty():
                            continue
                        pa_start = approach_edge.startPoint()
                        pa_end = approach_edge.endPoint()
                        za_start = current_section_start_elev
                        za_end = section_end_elev

                        # --- Clip approach side at IHS elevation ---
                        pa_start_clipped = pa_start
                        pa_end_clipped = pa_end
                        za_start_clipped = za_start
                        za_end_clipped = za_end

                        if za_start < IHS_ELEVATION_AMSL and za_end > IHS_ELEVATION_AMSL:
                            # Crossing from below to above IHS: interpolate where it meets
                            frac = (IHS_ELEVATION_AMSL - za_start) / (za_end - za_start)
                            pa_end_clipped = QgsPoint(
                                pa_start.x() + frac * (pa_end.x() - pa_start.x()),
                                pa_start.y() + frac * (pa_end.y() - pa_start.y()),
                                IHS_ELEVATION_AMSL,
                            )
                            za_end_clipped = IHS_ELEVATION_AMSL
                        elif za_end < IHS_ELEVATION_AMSL and za_start > IHS_ELEVATION_AMSL:
                            frac = (IHS_ELEVATION_AMSL - za_end) / (za_start - za_end)
                            pa_start_clipped = QgsPoint(
                                pa_end.x() + frac * (pa_start.x() - pa_end.x()),
                                pa_end.y() + frac * (pa_start.y() - pa_end.y()),
                                IHS_ELEVATION_AMSL,
                            )
                            za_start_clipped = IHS_ELEVATION_AMSL
                        elif za_start >= IHS_ELEVATION_AMSL and za_end >= IHS_ELEVATION_AMSL:
                            continue

                        # --- Generate panel corners ---
                        points_base = [
                            QgsPointXY(pa_start_clipped.x(), pa_start_clipped.y()),
                            QgsPointXY(pa_end_clipped.x(), pa_end_clipped.y()),
                        ]
                        elevations_base = [za_start_clipped, za_end_clipped]
                        points_top = []
                        for base_pt, base_elev in zip(points_base, elevations_base):
                            h_dist = max(
                                0.0,
                                (IHS_ELEVATION_AMSL - base_elev) / transitional_slope,
                            )
                            top_pt = base_pt.project(h_dist, outward_perp_azimuth)
                            points_top.append(top_pt)

                        corners = [
                            points_base[0],
                            points_base[1],
                            points_top[1],
                            points_top[0],
                        ]
                        poly_geom = self._create_polygon_from_corners(
                            corners,
                            f"Trans App {end_desig} Sec{i+1} {side_label}",
                        )
                        if poly_geom:
                            feat = QgsFeature(transitional_fields)
                            feat.setGeometry(poly_geom)
                            attr_map = {
                                "rwy_name": runway_name,
                                "surface": "Transitional",
                                "end_desig": end_desig,
                                "section_desc": f"Transitional {end_desig} Approach Adjacent Surface",
                                "elev_m": IHS_ELEVATION_AMSL,
                                "height_agl": IHS_ELEVATION_AMSL - min(za_start_clipped, za_end_clipped),
                                "side": side_label,
                                "slope_perc": transitional_slope * 100.0,
                                "ref_mos": transitional_ref,
                            }
                            for name, value in attr_map.items():
                                idx = transitional_fields.indexFromName(name)
                                if idx != -1:
                                    feat.setAttribute(idx, value)
                            transitional_features.append(feat)
                            transitional_candidate_sequence += 1
                            transitional_surface_id = self._register_transitional_controlling_candidate(
                                poly_geom,
                                runway_name,
                                f"Transitional {end_desig} Approach Adjacent Surface",
                                side_label,
                                transitional_candidate_sequence,
                                points_base[0],
                                za_start_clipped,
                                points_base[1],
                                za_end_clipped,
                                points_top[0],
                                IHS_ELEVATION_AMSL,
                                metadata={
                                    "slope": transitional_slope,
                                    "ref_mos": transitional_ref,
                                    "end_desig": end_desig,
                                    "approach_section_index": i + 1,
                                },
                            )

                            top_start = points_top[0]
                            top_end = points_top[1]
                            lower_edge = self._make_transitional_contour_feature(
                                QgsGeometry.fromPolylineXY([points_base[0], points_base[1]]),
                                contour_fields,
                                runway_name,
                                f"Transitional {end_desig} Approach Adjacent Surface",
                                None,
                                side_label=side_label,
                                end_desig=end_desig,
                                transitional_ref=transitional_ref,
                                surface_id=transitional_surface_id,
                            )
                            upper_edge = self._make_transitional_contour_feature(
                                QgsGeometry.fromPolylineXY([top_start, top_end]),
                                contour_fields,
                                runway_name,
                                f"Transitional {end_desig} Approach Adjacent Surface",
                                IHS_ELEVATION_AMSL,
                                side_label=side_label,
                                end_desig=end_desig,
                                transitional_ref=transitional_ref,
                                surface_id=transitional_surface_id,
                            )
                            edge_contours = [feature for feature in [lower_edge, upper_edge] if feature is not None]
                            if transitional_surface_id and hasattr(self, "_register_controlling_ols_contour"):
                                for contour_feature in edge_contours:
                                    self._register_controlling_ols_contour(
                                        transitional_surface_id,
                                        "Transitional",
                                        contour_feature,
                                        "OLS Transitional Contour",
                                    )
                            transitional_contour_features.extend(edge_contours)

                            approach_contours = self._generate_parallel_contours_in_panel(
                                top_start=top_start,
                                top_end=top_end,
                                IHS_ELEVATION_AMSL=IHS_ELEVATION_AMSL,
                                base_start=points_base[0],
                                base_end=points_base[1],
                                z_start=za_start_clipped,
                                z_end=za_end_clipped,
                                transitional_slope=transitional_slope,
                                contour_fields=contour_fields,
                                contour_interval=contour_interval,
                                panel_geom=poly_geom,
                                section_desc=f"Transitional {end_desig} Approach Adjacent Surface",
                                side_label=side_label,
                                runway_name=runway_name,
                                end_desig=end_desig,
                                transitional_ref=transitional_ref,
                                surface_id=transitional_surface_id,
                            )
                            if transitional_surface_id and hasattr(self, "_register_controlling_ols_contour"):
                                for contour_feature in approach_contours:
                                    self._register_controlling_ols_contour(
                                        transitional_surface_id,
                                        "Transitional",
                                        contour_feature,
                                        "OLS Transitional Contour",
                                    )
                            transitional_contour_features.extend(approach_contours)

                    current_section_start_elev = section_end_elev
                    prev_section_length = section_length

        QgsMessageLog.logMessage(
            f"Finished Transitional Surface feature generation. Created {len(transitional_features)} polygons, {len(transitional_contour_features)} contours.",
            plugin_tag,
            level=Qgis.Info,
        )
        return transitional_features, transitional_contour_features

    # --- Guideline Processing Functions (Using Helper) ---
    def _generate_transitional_strip_contours(
        self,
        base_start: QgsPointXY,
        base_end: QgsPointXY,
        top_start: QgsPointXY,
        top_end: QgsPointXY,
        z_start: float,
        z_end: float,
        IHS_ELEVATION_AMSL: float,
        contour_fields: QgsFields,
        contour_interval: float,
        section_desc: str,
        side_label: str,
        runway_name: str,
        transitional_ref: str,
        bounding_polygon=None,
        surface_id: Optional[str] = None,
    ) -> List[QgsFeature]:
        """
        Generates contour lines for a rectangular (strip-adjacent) transitional surface section.
        Returns a list of QgsFeature line features.
        """
        contours = []
        min_z = min(z_start, z_end)
        max_z = IHS_ELEVATION_AMSL
        first_contour = math.ceil(min_z / contour_interval) * contour_interval
        current_z = first_contour
        while current_z < max_z:
            # Linear interpolation for contour endpoints along base->top lines
            t_start = (current_z - z_start) / (max_z - z_start) if max_z > z_start else 1.0
            t_end = (current_z - z_end) / (max_z - z_end) if max_z > z_end else 1.0
            pt_left = QgsPointXY(
                base_start.x() + t_start * (top_start.x() - base_start.x()),
                base_start.y() + t_start * (top_start.y() - base_start.y()),
            )
            pt_right = QgsPointXY(
                base_end.x() + t_end * (top_end.x() - base_end.x()),
                base_end.y() + t_end * (top_end.y() - base_end.y()),
            )
            line_geom = QgsGeometry.fromPolylineXY([pt_left, pt_right])

            # --- CLIP to rectangle polygon if provided ---
            if bounding_polygon is not None and line_geom is not None:
                clipped_geom = line_geom.intersection(bounding_polygon)
                if clipped_geom.isEmpty():
                    current_z += contour_interval
                    continue  # Skip if completely outside
                line_geom = clipped_geom  # Use the clipped geometry

            feat = QgsFeature(contour_fields)
            feat.setGeometry(line_geom)
            # Assign attributes (add/remove fields as appropriate)
            attr_map = {
                "rwy_name": runway_name,
                "surface": "Transitional",
                "section_desc": section_desc,
                "side": side_label,
                "contour_elev_am": current_z,
                "ref_mos": transitional_ref,
                "surface_id": surface_id,
            }
            #     QgsMessageLog.logMessage(
            #     f"Setting contour_elev_am for contour: current_z={current_z} (type={type(current_z)})",
            #     PLUGIN_TAG,
            #     level=Qgis.Info,
            # )
            for name, value in attr_map.items():
                idx = contour_fields.indexFromName(name)
                if idx != -1:
                    feat.setAttribute(idx, value)
            contours.append(feat)
            current_z += contour_interval
        return contours

    # Guideline F: OLS Processing Helpers
    # ============================================================
    def _get_conical_contour_fields(self) -> QgsFields:
        """Returns the QgsFields definition for the Conical Contour layer."""
        fields = QgsFields(
            [
                QgsField("surface", QVariant.String, self.tr("Surface Type"), 30),
                QgsField(
                    "contour_elev_am",
                    QVariant.Double,
                    self.tr("Contour Elev (AMSL)"),
                    10,
                    2,
                ),
                QgsField(
                    "contour_hgt_abv",
                    QVariant.Double,
                    self.tr("Height Above IHS (m)"),
                    10,
                    2,
                ),
                QgsField("ref_mos", QVariant.String, self.tr("Reference"), 100),
                QgsField("surface_id", QVariant.String, self.tr("Surface ID"), 160),
            ]
        )
        return fields

    def _get_approach_contour_fields(self) -> QgsFields:
        """Returns the QgsFields definition for the Approach Contour layer."""
        fields = QgsFields(
            [
                QgsField("rwy_name", QVariant.String, self.tr("rwy"), 50),
                QgsField("end_desig", QVariant.String, self.tr("End Designator"), 10),
                QgsField("surface", QVariant.String, self.tr("Surface Type"), 30),
                QgsField(
                    "contour_elev_am",
                    QVariant.Double,
                    self.tr("Contour Elev (AMSL)"),
                    10,
                    2,
                ),
                QgsField("side", QVariant.String, self.tr("Side"), 5),
                QgsField("end_desig", QVariant.String, self.tr("End Designator"), 10),
                QgsField("ref_mos", QVariant.String, self.tr("Reference"), 100),
                QgsField("surface_id", QVariant.String, self.tr("Surface ID"), 160),
            ]
        )
        return fields

    def _get_tocs_contour_fields(self) -> QgsFields:
        return QgsFields(
            [
                QgsField("rwy_name", QVariant.String),
                QgsField("end_desig", QVariant.String),
                QgsField("surface", QVariant.String),
                QgsField("contour_elev_am", QVariant.Double),
                QgsField("surface_id", QVariant.String),
            ]
        )

    def _get_transitional_contour_fields(self) -> QgsFields:
        """
        Returns minimal fields for the Transitional Contour lines.
        """
        return QgsFields(
            [
                QgsField("rwy_name", QVariant.String, self.tr("Runway"), 50),
                QgsField("surface", QVariant.String, self.tr("Surface Type"), 30),
                QgsField("section_desc", QVariant.String, self.tr("Section Desc"), 50),
                QgsField(
                    "contour_elev_am",
                    QVariant.Double,
                    self.tr("Contour Elev (AMSL)"),
                    10,
                    2,
                ),
                QgsField("side", QVariant.String, self.tr("Side"), 5),
                QgsField("end_desig", QVariant.String, self.tr("End Designator"), 10),
                QgsField("ref_mos", QVariant.String, self.tr("Reference"), 100),
                QgsField("surface_id", QVariant.String, self.tr("Surface ID"), 160),
            ]
        )

    def _get_ols_fields(self, surface_type: str) -> QgsFields:
        """Returns the QgsFields definition for a given OLS surface type."""
        # Base fields common to most OLS layers
        fields_list = [
            QgsField("rwy_name", QVariant.String, self.tr("rwy"), 50),
            QgsField("surface", QVariant.String, self.tr("Surface Type"), 50),
            QgsField("end_desig", QVariant.String, self.tr("End Designator"), 10),
            QgsField("section_desc", QVariant.String, self.tr("Section Desc"), 50),
            QgsField(
                "elev_m", QVariant.Double, self.tr("Outer Elev (AMSL)"), 10, 2
            ),  # Clarify: Elevation at outer edge of this section
            QgsField(
                "height_agl", QVariant.Double, self.tr("Height Gain (m)"), 10, 2
            ),  # Clarify: Height gain across this section
            QgsField("slope_perc", QVariant.Double, self.tr("Slope (%)"), 6, 3),
            QgsField("ref_mos", QVariant.String, self.tr("Reference"), 100),
        ]
        # Add specific fields based on type
        if surface_type in [
            "Approach",
            "TOCS",
            "InnerApproach",
            "InnerTransitional",
            "BaulkedLanding",
        ]:
            fields_list.extend(
                [
                    QgsField(
                        "len_m", QVariant.Double, self.tr("Section Length (m)"), 12, 2
                    ),  # Clarify: Length of this section
                    QgsField(
                        "innerw_m",
                        QVariant.Double,
                        self.tr("Section Start W (m)"),
                        10,
                        2,
                    ),  # Clarify: Width at start of this section
                    QgsField(
                        "outerw_m", QVariant.Double, self.tr("Section End W (m)"), 10, 2
                    ),  # Clarify: Width at end of this section
                    QgsField("diverg_perc", QVariant.Double, self.tr("Divergence (%)"), 6, 3),
                    QgsField(
                        "origin_offset",
                        QVariant.Double,
                        self.tr("Start Dist THR (m)"),
                        10,
                        2,
                    ),  # Clarify: Dist from THR to start of this section
                ]
            )
        elif surface_type == "Conical":
            fields_list.extend(
                [
                    QgsField(
                        "height_extent",
                        QVariant.Double,
                        self.tr("Height Extent (AGL)"),
                        10,
                        2,
                    ),  # Above IHS
                ]
            )
        elif surface_type == "OHS":
            fields_list.extend(
                [
                    QgsField("radius_m", QVariant.Double, self.tr("Radius (m)"), 12, 2),
                ]
            )
        elif surface_type == "Transitional":
            fields_list.extend(
                [
                    QgsField("side", QVariant.String, self.tr("Side (L/R)"), 5),
                ]
            )

        # Conditionally remove fields not applicable to the specific surface type
        final_fields = []
        # Define which fields to REMOVE for each type
        remove_map = {
            "IHS": [
                "end_desig",
                "len_m",
                "innerw_m",
                "outerw_m",
                "diverg_perc",
                "origin_offset",
                "height_extent",
                "radius_m",
                "side",
                "slope_perc",
            ],
            "Conical": [
                "end_desig",
                "len_m",
                "innerw_m",
                "outerw_m",
                "diverg_perc",
                "origin_offset",
                "shape_desc",
                "radius_m",
                "side",
            ],
            "OHS": [
                "end_desig",
                "len_m",
                "innerw_m",
                "outerw_m",
                "diverg_perc",
                "origin_offset",
                "shape_desc",
                "height_extent",
                "side",
                "slope_perc",
            ],
            "Transitional": [
                "end_desig",
                "len_m",
                "innerw_m",
                "outerw_m",
                "diverg_perc",
                "origin_offset",
                "shape_desc",
                "height_extent",
                "radius_m",
            ],
            "Approach": [
                "shape_desc",
                "height_extent",
                "radius_m",
                "side",
            ],  # Keep App/TOCS specific + base + Section_Desc
            "InnerApproach": [
                "shape_desc",
                "height_extent",
                "radius_m",
                "side",
                "diverg_perc",
                "section_desc",
            ],  # Inner Approach is single section
            "TOCS": [
                "shape_desc",
                "height_extent",
                "radius_m",
                "side",
            ],  # Keep App/TOCS specific + base
            "InnerTransitional": [
                "shape_desc",
                "height_extent",
                "radius_m",
                "side",
                "diverg_perc",
                "section_desc",
            ],
            "BaulkedLanding": [
                "shape_desc",
                "height_extent",
                "radius_m",
                "side",
                "section_desc",
            ],
        }
        fields_to_remove = set(remove_map.get(surface_type, []))

        for field in fields_list:
            if field.name() not in fields_to_remove:
                # Update labels for clarity
                if field.name() == "elev_m":
                    field.setAlias(self.tr("Section Upper Elev (AMSL)"))
                elif field.name() == "height_agl":
                    field.setAlias(self.tr("Section Height Gain (m)"))
                elif field.name() == "len_m":
                    field.setAlias(self.tr("Section Length (m)"))
                elif field.name() == "innerw_m":
                    field.setAlias(self.tr("Section Start W (m)"))
                elif field.name() == "outerw_m":
                    field.setAlias(self.tr("Section End W (m)"))
                elif field.name() == "origin_offset":
                    field.setAlias(self.tr("Section Start Dist THR (m)"))
                final_fields.append(field)

        return QgsFields(final_fields)

    def _generate_approach_surface(
        self,
        runway_data: dict,
        rwy_params: dict,
        arc_num: int,
        end_type: str,
        thr_point: QgsPointXY,
        outward_azimuth: float,
        end_desig: str,
        threshold_elevation: Optional[float],
    ) -> Tuple[List[QgsFeature], List[QgsFeature]]:
        """
        Generates a list of Approach Surface section features (polygons)
        and a list of contour line features.
        Returns a tuple: (list_of_main_polygon_features, list_of_contour_features)
        """

        # --- Get Section Parameters ---
        sections = ols_dimensions.get_ols_params(arc_num, end_type, "APPROACH")
        if not sections:
            QgsMessageLog.logMessage(
                f"No Approach params found for {end_desig} (Code {arc_num}, Type {end_type})",
                PLUGIN_TAG,
                level=Qgis.Warning,
            )
            return [], []

        # --- Initialize Variables ---
        main_polygon_features: List[QgsFeature] = []
        contour_line_features: List[QgsFeature] = []
        approach_contour_interval = self._get_contour_interval("approach", APPROACH_CONTOUR_INTERVAL)
        # calculated_total_length = 0.0 # No longer needed for overall feature
        # final_outer_width = 0.0     # No longer needed for overall feature
        # final_outer_elevation = threshold_elevation # No longer needed for overall feature

        if threshold_elevation is None:
            QgsMessageLog.logMessage(
                f"Warning: Threshold elevation missing for Approach {end_desig}. Contour/Section AMSL values will be None.",
                PLUGIN_TAG,
                level=Qgis.Warning,
            )

        # --- Loop Through Sections ---
        current_start_point: Optional[QgsPointXY] = None
        current_start_width: float = 0.0
        current_elevation_amsl = threshold_elevation
        current_dist_from_thr = 0.0  # Keep track of cumulative distance for Origin_Offset

        for i, section_params in enumerate(sections):
            section_surface_id = f"APP:{runway_data.get('short_name', 'N/A')}:{end_desig}:S{i + 1}"
            # --- Get section parameters ---
            section_length = section_params.get("length", 0.0)
            section_slope = section_params.get("slope", 0.0)
            section_divergence = section_params.get("divergence", 0.0)  # Per side
            ref = section_params.get("ref", "MOS T8.2-1 (Check)")

            if section_length <= 0:
                continue  # Skip sections with no length

            # --- Determine Start Point, Width, and Origin Offset for this section ---
            section_start_dist_thr: Optional[float] = None
            if i == 0:  # First section
                start_dist_offset = section_params.get("start_dist_from_thr", 0.0)
                start_width = section_params.get("start_width", 0.0)
                if start_width <= 0:
                    QgsMessageLog.logMessage(
                        f"Error: Invalid start_width {start_width} for Approach {end_desig} Section 1.",
                        PLUGIN_TAG,
                        level=Qgis.Critical,
                    )
                    return [], []
                current_start_point = thr_point.project(start_dist_offset, outward_azimuth)
                current_start_width = start_width
                current_dist_from_thr = start_dist_offset  # Initialize cumulative distance
                section_start_dist_thr = start_dist_offset  # Store for attribute
            else:  # Subsequent sections start where previous ended
                if current_start_point is None or current_start_width <= 0:
                    QgsMessageLog.logMessage(
                        f"Error: Cannot start Approach {end_desig} Section {i+1}, previous section failed.",
                        PLUGIN_TAG,
                        level=Qgis.Critical,
                    )
                    return [], []
                # Start point, width, and elevation carry over
                section_start_dist_thr = current_dist_from_thr  # Distance to *start* of this section

            # --- Calculate End Point and Width for this section ---
            current_start_hw = current_start_width / 2.0
            section_end_width = current_start_width + (2 * section_length * section_divergence)
            end_hw = section_end_width / 2.0
            end_point = current_start_point.project(section_length, outward_azimuth)

            if not end_point:
                QgsMessageLog.logMessage(
                    f"Error calculating end point for Approach {end_desig} Section {i+1}.",
                    PLUGIN_TAG,
                    level=Qgis.Warning,
                )
                continue  # Skip this section

            # --- Generate Section Geometry ---
            section_geom: Optional[QgsGeometry] = None
            # Determine Section Description
            section_desc = f"Section {i+1}"
            if abs(section_slope) < 1e-9 and i > 0:  # If slope is effectively zero and not the first section
                section_desc = "Horizontal"

            section_name_log = f"Approach {end_desig} {section_desc}"

            if abs(section_divergence) < 1e-9:  # Horizontal section or parallel sides
                section_geom = self._create_rectangle_from_start(
                    current_start_point,
                    outward_azimuth,
                    section_length,
                    current_start_hw,
                    section_name_log,
                )
            else:  # Diverging section
                section_geom = self._create_trapezoid(
                    current_start_point,
                    outward_azimuth,
                    section_length,
                    current_start_hw,
                    end_hw,
                    section_name_log,
                )

            valid_geom: Optional[QgsGeometry] = None
            if section_geom and not section_geom.isEmpty():
                valid_geom = section_geom.makeValid()
                if not valid_geom or valid_geom.isEmpty() or not valid_geom.isGeosValid():
                    QgsMessageLog.logMessage(
                        f"Warning: Invalid geometry generated for {section_name_log}.",
                        PLUGIN_TAG,
                        level=Qgis.Warning,
                    )
                    valid_geom = None  # Invalidate if makeValid failed
            else:
                QgsMessageLog.logMessage(
                    f"Warning: Failed to generate geometry for {section_name_log}.",
                    PLUGIN_TAG,
                    level=Qgis.Warning,
                )

            # --- Create Feature for THIS Section ---
            if valid_geom:
                try:
                    fields = self._get_ols_fields("Approach")
                    feature = QgsFeature(fields)
                    feature.setGeometry(valid_geom)

                    # Calculate section-specific elevations/heights
                    section_outer_elevation = (
                        (current_elevation_amsl + section_length * section_slope)
                        if current_elevation_amsl is not None
                        else None
                    )
                    section_height_gain = section_length * section_slope  # Height gain over this section

                    attr_map = {
                        "rwy_name": runway_data.get("short_name", "N/A"),
                        "surface": "Approach",
                        "end_desig": end_desig,
                        "section_desc": section_desc,
                        "elev_m": section_outer_elevation,  # Elevation at outer edge of this section
                        "height_agl": section_height_gain,  # Height gain over this section
                        "slope_perc": (section_slope * 100.0 if section_slope is not None else None),
                        "ref_mos": ref,
                        "len_m": section_length,  # Length of this section
                        "innerw_m": current_start_width,  # Width at start of this section
                        "outerw_m": section_end_width,  # Width at end of this section
                        "diverg_perc": (section_divergence * 100.0 if section_divergence is not None else None),
                        "origin_offset": section_start_dist_thr,  # Distance from THR to start of this section
                    }
                    for name, value in attr_map.items():
                        idx = fields.indexFromName(name)
                        if idx != -1:
                            feature.setAttribute(idx, value)

                    main_polygon_features.append(feature)  # Add section feature to the list
                    if (
                        hasattr(self, "_register_controlling_ols_candidate")
                        and current_elevation_amsl is not None
                        and current_start_point is not None
                    ):
                        self._register_controlling_ols_candidate(
                            ControllingOlsCandidate(
                                surface_id=section_surface_id,
                                surface_type="Approach",
                                footprint=QgsGeometry(valid_geom),
                                elevation_at_xy=axis_elevation_evaluator(
                                    current_start_point,
                                    outward_azimuth,
                                    current_elevation_amsl,
                                    section_slope,
                                    section_length,
                                ),
                                model="axis",
                                metadata={
                                    "origin_x": current_start_point.x(),
                                    "origin_y": current_start_point.y(),
                                    "azimuth_degrees": outward_azimuth,
                                    "origin_elevation_m": current_elevation_amsl,
                                    "slope": section_slope,
                                    "max_distance_m": section_length,
                                    "runway": runway_data.get("short_name", "N/A"),
                                    "end": end_desig,
                                    "section": i + 1,
                                },
                            )
                        )

                except Exception as e_feat:
                    QgsMessageLog.logMessage(
                        f"Error creating feature for {section_name_log}: {e_feat}",
                        PLUGIN_TAG,
                        level=Qgis.Critical,
                    )
                    # Optionally decide whether to halt all processing for this approach end
                    # return [], contour_line_features # Example: Stop if one section fails

            # --- Generate Contours within this Section ---
            if current_elevation_amsl is not None and section_outer_elevation is not None:
                start_elev = current_elevation_amsl
                end_elev = section_outer_elevation

                contour_elevs = set()

                if abs(section_slope) < 1e-9 and i > 0:
                    # Horizontal section (non-initial): add start and end
                    contour_elevs.add(round(start_elev, 6))
                    contour_elevs.add(round(end_elev, 6))
                else:
                    # Sloped section: intervals + start
                    first_contour = math.ceil(start_elev / approach_contour_interval) * approach_contour_interval
                    if first_contour < start_elev - 1e-6:
                        first_contour += approach_contour_interval

                    c_elev = first_contour
                    while c_elev <= end_elev + 1e-6:
                        contour_elevs.add(round(c_elev, 6))
                        c_elev += approach_contour_interval

                    contour_elevs.add(round(start_elev, 6))

                # --- Add a contour at the very end of the final section if it's horizontal ---
                if abs(section_slope) < 1e-9 and i == len(sections) - 1:
                    contour_elevs.add(round(end_elev, 6))

                contour_elevs = sorted(contour_elevs)

                for target_elev in contour_elevs:
                    delta_h = target_elev - start_elev
                    max_delta_h = section_length * section_slope

                    if abs(section_slope) < 1e-9:
                        dist_along = 0
                    else:
                        if delta_h < -1e-6 or delta_h > max_delta_h + 1e-6:
                            continue  # Skip contours outside this section
                        dist_along = delta_h / section_slope

                    cl_point = current_start_point.project(dist_along, outward_azimuth)
                    current_width_at_dist = current_start_width + (2 * dist_along * section_divergence)
                    half_width = current_width_at_dist / 2.0

                    if cl_point and half_width > 0:
                        az_perp_l = (outward_azimuth - 90.0 + 360.0) % 360.0
                        az_perp_r = (outward_azimuth + 90.0) % 360.0
                        pt_l = cl_point.project(half_width, az_perp_l)
                        pt_r = cl_point.project(half_width, az_perp_r)

                        if pt_l and pt_r:
                            contour_geom = QgsGeometry.fromPolylineXY([pt_l, pt_r])
                            if contour_geom and not contour_geom.isEmpty():
                                # --- CLIP CONTOUR TO CURRENT SECTION POLYGON ---
                                if valid_geom:  # Clip to current section
                                    clipped_geom = contour_geom.intersection(valid_geom)
                                    if clipped_geom and not clipped_geom.isEmpty():
                                        contour_fields = self._get_approach_contour_fields()
                                        contour_feature = QgsFeature(contour_fields)
                                        contour_feature.setGeometry(clipped_geom)
                                        contour_attr_map = {
                                            "rwy_name": runway_data.get("short_name", "N/A"),
                                            "end_desig": end_desig,
                                            "surface": "Approach",
                                            "contour_elev_am": target_elev,
                                            "surface_id": section_surface_id,
                                        }
                                        for name, value in contour_attr_map.items():
                                            idx = contour_fields.indexFromName(name)
                                            if idx != -1:
                                                contour_feature.setAttribute(idx, value)
                                        if hasattr(self, "_register_controlling_ols_contour"):
                                            self._register_controlling_ols_contour(
                                                section_surface_id,
                                                "Approach",
                                                contour_feature,
                                                "OLS Approach Contour",
                                            )
                                        contour_line_features.append(contour_feature)

            # --- Update for next iteration ---
            current_start_point = end_point
            current_start_width = section_end_width
            # Use calculated outer elevation for the start of the next section
            current_elevation_amsl = section_outer_elevation
            current_dist_from_thr += section_length  # Update cumulative distance

        # --- Return lists of features ---
        return (
            main_polygon_features,
            contour_line_features,
        )

    def _generate_tocs(
        self,
        runway_data: dict,
        rwy_params: dict,
        arc_num: int,
        end_type: str,
        runway_phys_end_point: QgsPointXY,
        clearway_len: float,
        outward_azimuth: float,
        end_desig: str,
        origin_elevation: Optional[float],
    ) -> Tuple[Optional[QgsFeature], List[QgsFeature]]:
        """
        Generates a single Take-Off Climb Surface (TOCS) feature and a list of contour features.
        Shape can be a composite trapezoid + rectangle based on parameters.
        """

        # Always define these!
        final_geom = None
        tocs_contour_features = []
        tocs_contour_interval = self._get_contour_interval("tocs", TOCS_CONTOUR_INTERVAL)

        # 1. Get Parameters
        params = ols_dimensions.get_ols_params(arc_num, None, "TOCS")
        if not params:
            QgsMessageLog.logMessage(
                f"No TOCS params found for {end_desig} (Code {arc_num})",
                PLUGIN_TAG,
                level=Qgis.Warning,
            )
            return None, []

        try:
            origin_offset = params.get("origin_offset")
            inner_width = params.get("inner_edge_width")
            divergence = params.get("divergence")
            overall_length = params.get("length")
            final_width = params.get("final_width")
            slope = params.get("slope")
            ref = params.get("ref", "MOS T8.2-1 (Check)")

            essential_params = [
                origin_offset,
                inner_width,
                divergence,
                overall_length,
                final_width,
                slope,
            ]
            if any(p is None for p in essential_params):
                missing_keys = [
                    k
                    for k, v in params.items()
                    if v is None
                    and k
                    in [
                        "origin_offset",
                        "inner_edge_width",
                        "divergence",
                        "length",
                        "final_width",
                        "slope",
                    ]
                ]
                QgsMessageLog.logMessage(
                    f"Essential TOCS parameters missing or None ({', '.join(missing_keys)}) for Code {arc_num}, End {end_desig}.",
                    PLUGIN_TAG,
                    level=Qgis.Critical,
                )
                return None, []

            origin_offset = float(origin_offset)
            inner_width = float(inner_width)
            divergence = float(divergence)
            overall_length = float(overall_length)
            final_width = float(final_width)
            slope = float(slope)

        except (ValueError, TypeError, KeyError) as e_param:
            QgsMessageLog.logMessage(
                f"Error processing/converting TOCS parameters for Code {arc_num}, End {end_desig}: {e_param}",
                PLUGIN_TAG,
                level=Qgis.Critical,
            )
            return None, []

        inner_hw = inner_width / 2.0
        final_hw = final_width / 2.0

        if overall_length <= 0 or inner_width <= 0 or divergence is None or divergence < 0 or final_width <= 0:
            QgsMessageLog.logMessage(
                f"Invalid TOCS dimensions/params for {end_desig} (L={overall_length}, IW={inner_width}, FW={final_width}, Div={divergence})",
                PLUGIN_TAG,
                level=Qgis.Warning,
            )
            return None, []

        # 2. Calculate Start Point of TOCS Inner Edge
        effective_takeoff_start = runway_phys_end_point
        if clearway_len > 1e-6:
            projected_clearway_end = effective_takeoff_start.project(clearway_len, outward_azimuth)
            if not projected_clearway_end:
                QgsMessageLog.logMessage(
                    f"Failed calc TOCS clearway end point {end_desig}",
                    PLUGIN_TAG,
                    level=Qgis.Warning,
                )
                return None, []
            effective_takeoff_start = projected_clearway_end

        start_point = effective_takeoff_start.project(origin_offset, outward_azimuth)
        if not start_point:
            QgsMessageLog.logMessage(
                f"Failed calc TOCS start point after offset {end_desig}",
                PLUGIN_TAG,
                level=Qgis.Warning,
            )
            return None, []

        # 3. Calculate Length of Divergence Section
        width_increase_per_side = final_hw - inner_hw
        length_divergence = width_increase_per_side / divergence if width_increase_per_side > 0 else 0.0

        # 4. Generate Geometry
        try:
            if length_divergence >= overall_length - 1e-6:
                outer_hw_at_overall = inner_hw + (overall_length * divergence)
                final_geom = self._create_trapezoid(
                    start_point,
                    outward_azimuth,
                    overall_length,
                    inner_hw,
                    outer_hw_at_overall,
                    f"TOCS Trapezoid {end_desig}",
                )
            else:
                trap_geom = self._create_trapezoid(
                    start_point,
                    outward_azimuth,
                    length_divergence,
                    inner_hw,
                    final_hw,
                    f"TOCS Trapezoid Part {end_desig}",
                )
                rect_start_point = start_point.project(length_divergence, outward_azimuth)
                length_rectangle = overall_length - length_divergence

                if not rect_start_point or length_rectangle < 1e-6:
                    final_geom = trap_geom
                else:
                    rect_geom = self._create_rectangle_from_start(
                        rect_start_point,
                        outward_azimuth,
                        length_rectangle,
                        final_hw,
                        f"TOCS Rectangle Part {end_desig}",
                    )
                    if trap_geom and rect_geom:
                        combined = QgsGeometry.unaryUnion([trap_geom, rect_geom])
                        if combined and not combined.isEmpty():
                            final_geom = combined.makeValid()
                        else:
                            final_geom = trap_geom
                    elif trap_geom:
                        final_geom = trap_geom
                    else:
                        final_geom = None

        except Exception as e_geom:
            QgsMessageLog.logMessage(
                f"Error generating TOCS geometry for {end_desig}: {e_geom}",
                PLUGIN_TAG,
                level=Qgis.Critical,
            )
            return None, []

        if not final_geom or final_geom.isEmpty() or not final_geom.isGeosValid():
            QgsMessageLog.logMessage(
                f"Failed create valid TOCS geometry for {end_desig}",
                PLUGIN_TAG,
                level=Qgis.Warning,
            )
            return None, []

        # 5. Create TOCS Polygon Feature
        height_agl = overall_length * slope
        elevation_amsl = (origin_elevation + height_agl) if origin_elevation is not None else None

        fields = self._get_ols_fields("TOCS")
        feature = QgsFeature(fields)
        feature.setGeometry(final_geom)
        tocs_surface_id = f"TOCS:{runway_data.get('short_name', 'N/A')}:{end_desig}"
        attr_map = {
            "rwy_name": runway_data.get("short_name", "N/A"),
            "surface": "TOCS",
            "end_desig": end_desig,
            "elev_m": elevation_amsl,
            "height_agl": height_agl,
            "slope_perc": slope * 100.0 if slope is not None else None,
            "ref_mos": ref,
            "len_m": overall_length,
            "innerw_m": inner_width,
            "outerw_m": final_width,
            "diverg_perc": divergence * 100.0 if divergence is not None else None,
            "origin_offset": origin_offset,
        }
        for name, value in attr_map.items():
            idx = fields.indexFromName(name)
            if idx != -1:
                feature.setAttribute(idx, value)
        if hasattr(self, "_register_controlling_ols_candidate") and origin_elevation is not None:
            self._register_controlling_ols_candidate(
                ControllingOlsCandidate(
                    surface_id=tocs_surface_id,
                    surface_type="TOCS",
                    footprint=QgsGeometry(final_geom),
                    elevation_at_xy=axis_elevation_evaluator(
                        start_point,
                        outward_azimuth,
                        origin_elevation,
                        slope,
                        overall_length,
                    ),
                    model="axis",
                    metadata={
                        "origin_x": start_point.x(),
                        "origin_y": start_point.y(),
                        "azimuth_degrees": outward_azimuth,
                        "origin_elevation_m": origin_elevation,
                        "slope": slope,
                        "max_distance_m": overall_length,
                        "runway": runway_data.get("short_name", "N/A"),
                        "end": end_desig,
                    },
                )
            )

        # ---- TOCS Contour Features with Clipping ----
        # TOCS_CONTOUR_INTERVAL = 10.0  # Adjust as needed
        tocs_contour_features = []
        if origin_elevation is not None and overall_length > 0:
            start_elev = origin_elevation
            end_elev = origin_elevation + height_agl

            contour_elevs = set()

            # Add interval contours
            first_contour = math.ceil(start_elev / tocs_contour_interval) * tocs_contour_interval
            if first_contour < start_elev - 1e-6:
                first_contour += tocs_contour_interval

            c_elev = first_contour
            while c_elev <= end_elev + 1e-6:
                contour_elevs.add(round(c_elev, 6))
                c_elev += tocs_contour_interval

            # Always add start and end elevation
            contour_elevs.add(round(start_elev, 6))
            contour_elevs.add(round(end_elev, 6))

            contour_elevs = sorted(contour_elevs)

            for target_elev in contour_elevs:
                delta_h = target_elev - start_elev
                if slope == 0:
                    dist_along = 0
                else:
                    if delta_h < -1e-6 or delta_h > height_agl + 1e-6:
                        continue
                    dist_along = delta_h / slope

                is_last_contour = abs(target_elev - end_elev) < 1e-6

                if is_last_contour:
                    # At the end: use polygon outer width, no clipping
                    cl_point = start_point.project(overall_length, outward_azimuth)
                    current_width_at_dist = final_width
                    half_width = current_width_at_dist / 2.0

                    if cl_point and half_width > 0:
                        az_perp_l = (outward_azimuth - 90.0 + 360.0) % 360.0
                        az_perp_r = (outward_azimuth + 90.0) % 360.0
                        pt_l = cl_point.project(half_width, az_perp_l)
                        pt_r = cl_point.project(half_width, az_perp_r)

                        if pt_l and pt_r:
                            contour_geom = QgsGeometry.fromPolylineXY([pt_l, pt_r])
                            # No clipping for the last contour
                            final_contour_geom = contour_geom
                else:
                    # Intermediate contours: project as normal, then clip
                    cl_point = start_point.project(dist_along, outward_azimuth)
                    current_width_at_dist = inner_width + (2 * dist_along * divergence)
                    half_width = current_width_at_dist / 2.0

                    if cl_point and half_width > 0:
                        az_perp_l = (outward_azimuth - 90.0 + 360.0) % 360.0
                        az_perp_r = (outward_azimuth + 90.0) % 360.0
                        pt_l = cl_point.project(half_width, az_perp_l)
                        pt_r = cl_point.project(half_width, az_perp_r)

                        if pt_l and pt_r:
                            contour_geom = QgsGeometry.fromPolylineXY([pt_l, pt_r])
                            # Clip to TOCS polygon
                            final_contour_geom = contour_geom.intersection(final_geom)
                # If valid, create the feature
                if "final_contour_geom" in locals() and final_contour_geom and not final_contour_geom.isEmpty():
                    contour_fields = self._get_tocs_contour_fields()
                    contour_feature = QgsFeature(contour_fields)
                    contour_feature.setGeometry(final_contour_geom)
                    contour_attr_map = {
                        "rwy_name": runway_data.get("short_name", "N/A"),
                        "end_desig": end_desig,
                        "surface": "TOCS",
                        "contour_elev_am": target_elev,
                        "surface_id": tocs_surface_id,
                    }
                    for name, value in contour_attr_map.items():
                        idx = contour_fields.indexFromName(name)
                        if idx != -1:
                            contour_feature.setAttribute(idx, value)
                    if hasattr(self, "_register_controlling_ols_contour"):
                        self._register_controlling_ols_contour(
                            tocs_surface_id,
                            "TOCS",
                            contour_feature,
                            "OLS TOCS Contour",
                        )
                    tocs_contour_features.append(contour_feature)
                # Clean up variable for next loop
                if "final_contour_geom" in locals():
                    del final_contour_geom

        # Return both the polygon and the contour features list
        return feature, tocs_contour_features

    def process_guideline_f(
        self,
        runway_data: dict,
        layer_group: QgsLayerTreeGroup,
        ofz_group: Optional[QgsLayerTreeGroup] = None,
    ) -> bool:
        plugin_tag = PLUGIN_TAG

        # --- Get Core Data from runway_data ---
        runway_name = runway_data.get("short_name", f"RWY_{runway_data.get('original_index', '?')}")
        primary_threshold_point = runway_data.get("thr_point")
        reciprocal_threshold_point = runway_data.get("rec_thr_point")
        arc_num_str = runway_data.get("arc_num")
        primary_approach_type_str = runway_data.get("type1", "")
        reciprocal_approach_type_str = runway_data.get("type2", "")
        primary_thr_elev = runway_data.get("threshold_elev_1")
        reciprocal_thr_elev = runway_data.get("threshold_elev_2")
        primary_runway_end_elev = runway_data.get("runway_end_elev_1")
        reciprocal_runway_end_elev = runway_data.get("runway_end_elev_2")

        runway_actual_width_val = runway_data.get("width")
        if runway_actual_width_val is None:
            QgsMessageLog.logMessage(
                f"Runway OLS for {runway_name} SKIPPED: Missing 'width' in runway_data.",
                plugin_tag,
                Qgis.Warning,
            )
            return False
        try:
            runway_actual_width = float(runway_actual_width_val)
            if runway_actual_width <= 0:
                QgsMessageLog.logMessage(
                    f"Runway OLS for {runway_name} SKIPPED: Runway 'width' ({runway_actual_width}) must be positive.",
                    plugin_tag,
                    Qgis.Warning,
                )
                return False
        except (ValueError, TypeError):
            QgsMessageLog.logMessage(
                f"Runway OLS for {runway_name} SKIPPED: Invalid 'width' ('{runway_actual_width_val}') in runway_data.",
                plugin_tag,
                Qgis.Warning,
            )
            return False

        QgsMessageLog.logMessage(
            f"Starting Runway OLS processing (OFZ components, Approach, TOCS) for {runway_name}",
            plugin_tag,
            level=Qgis.Info,
        )

        if not all(
            [
                primary_threshold_point,
                reciprocal_threshold_point,
                layer_group,
                arc_num_str,
            ]
        ):
            QgsMessageLog.logMessage(
                f"Runway OLS for {runway_name} SKIPPED: Missing essential base data.",
                plugin_tag,
                Qgis.Warning,
            )
            return False
        try:
            arc_num = int(arc_num_str)
        except (ValueError, TypeError):
            QgsMessageLog.logMessage(
                f"Runway OLS for {runway_name} SKIPPED: Invalid ARC number '{arc_num_str}'.",
                plugin_tag,
                Qgis.Warning,
            )
            return False

        primary_desig, reciprocal_desig = runway_name.split("/") if "/" in runway_name else ("THR1", "THR2")

        rwy_params = self._get_runway_parameters(primary_threshold_point, reciprocal_threshold_point)
        if rwy_params is None:
            return False  # Error logged in helper

        az_primary_to_reciprocal = rwy_params["azimuth_p_r"]
        az_reciprocal_to_primary = rwy_params["azimuth_r_p"]

        clearway_len_at_primary_end = float(runway_data.get("clearway1_len", 0.0) or 0.0)
        clearway_len_at_reciprocal_end = float(runway_data.get("clearway2_len", 0.0) or 0.0)
        disp_at_primary_thr = float(runway_data.get("thr_displaced_1", 0.0) or 0.0)
        disp_at_reciprocal_thr = float(runway_data.get("thr_displaced_2", 0.0) or 0.0)

        physical_endpoints_result_tuple = self._get_physical_runway_endpoints(
            primary_threshold_point,
            reciprocal_threshold_point,
            disp_at_primary_thr,
            disp_at_reciprocal_thr,
            rwy_params,
        )
        if physical_endpoints_result_tuple is None:
            return False  # Error logged in helper
        phys_pavement_end_near_primary_thr, phys_pavement_end_near_reciprocal_thr, _ = physical_endpoints_result_tuple

        overall_success = False
        inner_approach_features, approach_poly_features, approach_contour_features = (
            [],
            [],
            [],
        )
        (
            tocs_poly_features,
            tocs_contour_features,
            ofz_inner_trans_features,
            ofz_bls_features,
        ) = ([], [], [], [])

        IHS_ELEVATION_AMSL: Optional[float] = None
        if self.reference_elevation_datum is not None:
            ihs_base_height_agl = ols_dimensions.get_ihs_base_height()
            if ihs_base_height_agl is not None:
                IHS_ELEVATION_AMSL = self.reference_elevation_datum + ihs_base_height_agl
        if IHS_ELEVATION_AMSL is None:
            QgsMessageLog.logMessage(
                f"Runway OLS for {runway_name}: IHS Elevation could not be determined.",
                plugin_tag,
                Qgis.Warning,
            )

        runway_end_configurations = [
            {
                "current_desig": primary_desig,
                "landing_threshold_pt": primary_threshold_point,
                "landing_threshold_elev": primary_thr_elev,
                "approach_type_str": primary_approach_type_str,
                "approach_surface_outward_azimuth": az_reciprocal_to_primary,
                "baulked_landing_origin_thr_pt": primary_threshold_point,
                "baulked_landing_flight_path_azimuth": az_primary_to_reciprocal,
                "tocs_departure_pavement_end_pt": phys_pavement_end_near_reciprocal_thr,
                "tocs_flight_path_azimuth": az_primary_to_reciprocal,
                "tocs_clearway_len_at_departure_end": clearway_len_at_reciprocal_end,
                "runway_orientation_azimuth_for_its_perp": az_primary_to_reciprocal,
            },
            {
                "current_desig": reciprocal_desig,
                "landing_threshold_pt": reciprocal_threshold_point,
                "landing_threshold_elev": reciprocal_thr_elev,
                "approach_type_str": reciprocal_approach_type_str,
                "approach_surface_outward_azimuth": az_primary_to_reciprocal,
                "baulked_landing_origin_thr_pt": reciprocal_threshold_point,
                "baulked_landing_flight_path_azimuth": az_reciprocal_to_primary,
                "tocs_departure_pavement_end_pt": phys_pavement_end_near_primary_thr,
                "tocs_flight_path_azimuth": az_reciprocal_to_primary,
                "tocs_clearway_len_at_departure_end": clearway_len_at_primary_end,
                "runway_orientation_azimuth_for_its_perp": az_reciprocal_to_primary,
            },
        ]

        for config in runway_end_configurations:
            current_desig = config["current_desig"]

            ia_geom_for_its: Optional[QgsGeometry] = None
            ia_cl_start_xy: Optional[QgsPointXY] = None
            ia_cl_end_xy: Optional[QgsPointXY] = None
            ia_start_elev: Optional[float] = None
            ia_end_elev: Optional[float] = None
            ia_width: Optional[float] = None
            ia_length_param_val: Optional[float] = None

            bls_geom_for_its: Optional[QgsGeometry] = None
            bls_cl_start_xy: Optional[QgsPointXY] = None
            bls_cl_end_xy: Optional[QgsPointXY] = None
            bls_start_elev: Optional[float] = None
            bls_start_width: Optional[float] = None
            bls_end_width: Optional[float] = None
            bls_len: Optional[float] = None

            # --- Inner Approach ---
            try:
                ia_params = ols_dimensions.get_ols_params(arc_num, config["approach_type_str"], "InnerApproach")
                if ia_params:
                    ia_slope_param = ia_params.get("slope")
                    ia_start_dist_param = ia_params.get("start_dist_from_thr")
                    ia_length_param_val = ia_params.get("length")
                    ia_width_param_val = ia_params.get("width")
                    ia_ref_param = ia_params.get("ref")
                    if all(
                        v is not None
                        for v in [
                            ia_slope_param,
                            ia_start_dist_param,
                            ia_length_param_val,
                            ia_width_param_val,
                        ]
                    ):
                        ia_cl_start_xy = config["landing_threshold_pt"].project(
                            ia_start_dist_param,
                            config["approach_surface_outward_azimuth"],
                        )
                        if ia_cl_start_xy:
                            ia_geom_for_its = self._create_rectangle_from_start(
                                ia_cl_start_xy,
                                config["approach_surface_outward_azimuth"],
                                ia_length_param_val,
                                ia_width_param_val / 2.0,
                                f"IA {current_desig}",
                            )
                            if ia_geom_for_its and ia_geom_for_its.isGeosValid():
                                ia_width = ia_width_param_val
                                ia_start_elev = self._get_elevation_at_point_along_gradient(
                                    ia_cl_start_xy,
                                    primary_threshold_point,
                                    reciprocal_threshold_point,
                                    primary_thr_elev,
                                    reciprocal_thr_elev,
                                    QgsProject.instance().crs(),
                                )
                                if ia_start_elev is not None:
                                    ia_end_elev = ia_start_elev + (ia_length_param_val * ia_slope_param)
                                    ia_cl_end_xy = ia_cl_start_xy.project(
                                        ia_length_param_val,
                                        config["approach_surface_outward_azimuth"],
                                    )
                                else:
                                    ia_end_elev = None
                                    QgsMessageLog.logMessage(
                                        f"Warning: IA {current_desig} start elevation is None.",
                                        plugin_tag,
                                        Qgis.Warning,
                                    )

                                fields = self._get_ols_fields("InnerApproach")
                                feat = QgsFeature(fields)
                                feat.setGeometry(ia_geom_for_its)
                                h_agl = ia_length_param_val * ia_slope_param
                                attrs = {
                                    "rwy_name": runway_name,
                                    "surface": "Inner Approach",
                                    "end_desig": current_desig,
                                    "elev_m": ia_end_elev,
                                    "height_agl": h_agl,
                                    "slope_perc": ia_slope_param * 100.0,
                                    "ref_mos": ia_ref_param,
                                    "len_m": ia_length_param_val,
                                    "innerw_m": ia_width_param_val,
                                    "outerw_m": ia_width_param_val,
                                    "origin_offset": ia_start_dist_param,
                                }
                                for n, v_attr in attrs.items():
                                    if fields.indexFromName(n) != -1:
                                        feat.setAttribute(fields.indexFromName(n), v_attr)
                                inner_approach_features.append(feat)

            except Exception as e_ia:
                QgsMessageLog.logMessage(
                    f"ERROR generating Inner Approach for {current_desig}: {e_ia}\n{traceback.format_exc()}",
                    plugin_tag,
                    Qgis.Critical,
                )

            # --- Baulked Landing ---
            try:
                bls_params_dict = ols_dimensions.get_ols_params(arc_num, config["approach_type_str"], "BaulkedLanding")
                if bls_params_dict and IHS_ELEVATION_AMSL is not None:
                    bls_result_tuple = self._generate_baulked_landing_surface(
                        runway_data,
                        rwy_params,
                        config["baulked_landing_origin_thr_pt"],
                        config["baulked_landing_flight_path_azimuth"],
                        bls_params_dict,
                        current_desig,
                        IHS_ELEVATION_AMSL,
                    )
                    if bls_result_tuple:
                        feat_bls, bls_g, bls_l, bls_se, bls_cl_s_xy, bls_ew = bls_result_tuple
                        bls_geom_for_its = bls_g
                        bls_len = bls_l
                        bls_start_elev = bls_se
                        bls_cl_start_xy = bls_cl_s_xy
                        bls_end_width = bls_ew
                        bls_start_width = bls_params_dict.get("width")
                        if bls_cl_start_xy and bls_len is not None:
                            bls_cl_end_xy = bls_cl_start_xy.project(
                                bls_len, config["baulked_landing_flight_path_azimuth"]
                            )
                        if feat_bls:
                            ofz_bls_features.append(feat_bls)
                        else:
                            self._log_debug(f"BLS {current_desig} skipped: helper returned no feature.")
                    else:
                        self._log_debug(f"BLS {current_desig} skipped: helper returned no result.")
                elif not bls_params_dict:
                    self._log_debug(f"BLS {current_desig} skipped: no baulked landing parameters.")
                elif IHS_ELEVATION_AMSL is None:
                    self._log_debug(f"BLS {current_desig} skipped: IHS elevation unavailable.")
            except Exception as e_bls:
                QgsMessageLog.logMessage(
                    f"ERROR generating Baulked Landing for {current_desig}: {e_bls}\n{traceback.format_exc()}",
                    plugin_tag,
                    Qgis.Critical,
                )

            # --- Inner Transitional Surface ---
            if IHS_ELEVATION_AMSL is not None:
                it_params_dict = ols_dimensions.get_ols_params(
                    arc_num, config["approach_type_str"], "InnerTransitional"
                )
                if it_params_dict:
                    its_slope = it_params_dict.get("slope")
                    its_ref_mos = it_params_dict.get("ref", "MOS Ref ITS")

                    if its_slope is not None and its_slope > 1e-9:
                        its_fields = self._get_ols_fields("InnerTransitional")
                        strip_params_for_its = ols_dimensions.get_strip_params(
                            arc_num, config["approach_type_str"], runway_actual_width
                        )
                        graded_strip_total_width = 150.0
                        if strip_params_for_its and strip_params_for_its.get("graded_width") is not None:
                            graded_strip_total_width = strip_params_for_its.get("graded_width")
                        else:
                            self._log_debug(
                                f"ITS {current_desig}: using default strip width {graded_strip_total_width} m."
                            )
                        graded_strip_half_width = graded_strip_total_width / 2.0

                        main_centerline_orient_az = config["runway_orientation_azimuth_for_its_perp"]
                        # This definition of L/R for ITS projection is based on the main runway orientation
                        outward_az_L_ITS_projection = (main_centerline_orient_az - 90.0 + 360.0) % 360.0
                        outward_az_R_ITS_projection = (main_centerline_orient_az + 90.0) % 360.0

                        for side_label_its_panel, outward_projection_az_for_panel in [
                            ("L", outward_az_L_ITS_projection),
                            ("R", outward_az_R_ITS_projection),
                        ]:

                            P_IA_inner_3d_side, P_IA_outer_3d_side = None, None
                            P_BLS_inner_3d_side, P_BLS_outer_3d_side = None, None

                            # Define which side of IA/BLS corresponds to this ITS panel side
                            # If _get_polygon_side_3d_points uses (L=surface_az+90, R=surface_az-90)
                            # And IA surface az points "inwards" while BLS surface az points "outwards"
                            # then for the "L" ITS panel:
                            #   - We need the "L" side of IA (using side_label_its_panel 'L')
                            #   - We need the "L" side of BLS (using side_label_its_panel 'L')
                            # The helper _get_polygon_side_3d_points handles L/R relative to *its input surface's centerline*

                            if all(
                                v is not None
                                for v in [
                                    ia_geom_for_its,
                                    ia_cl_start_xy,
                                    ia_cl_end_xy,
                                    ia_start_elev,
                                    ia_end_elev,
                                    ia_width,
                                ]
                            ):
                                ia_side_pts_tuple = self._get_polygon_side_3d_points(
                                    ia_geom_for_its,
                                    ia_cl_start_xy,
                                    ia_cl_end_xy,
                                    ia_start_elev,
                                    ia_end_elev,
                                    ia_width / 2.0,
                                    ia_width / 2.0,
                                    side_label_its_panel,
                                )
                                if ia_side_pts_tuple:
                                    P_IA_inner_3d_side, P_IA_outer_3d_side = ia_side_pts_tuple

                            if (
                                all(
                                    v is not None
                                    for v in [
                                        bls_geom_for_its,
                                        bls_cl_start_xy,
                                        bls_cl_end_xy,
                                        bls_start_elev,
                                        bls_start_width,
                                        bls_end_width,
                                    ]
                                )
                                and bls_len is not None
                                and bls_len > 1e-6
                            ):
                                bls_side_pts_tuple = self._get_polygon_side_3d_points(
                                    bls_geom_for_its,
                                    bls_cl_start_xy,
                                    bls_cl_end_xy,
                                    bls_start_elev,
                                    IHS_ELEVATION_AMSL,
                                    bls_start_width / 2.0,
                                    bls_end_width / 2.0,
                                    self._flip_side_label(side_label_its_panel),
                                )
                                if bls_side_pts_tuple:
                                    P_BLS_inner_3d_side, P_BLS_outer_3d_side = bls_side_pts_tuple

                            if P_IA_outer_3d_side and P_IA_inner_3d_side:
                                panel_feat = self._generate_its_panel_feature(
                                    P_IA_outer_3d_side,
                                    P_IA_inner_3d_side,
                                    its_slope,
                                    IHS_ELEVATION_AMSL,
                                    outward_projection_az_for_panel,
                                    runway_name,
                                    current_desig,
                                    side_label_its_panel,
                                    "IA Adjacent",
                                    its_ref_mos,
                                    its_fields,
                                )
                                if panel_feat:
                                    ofz_inner_trans_features.append(panel_feat)
                            else:
                                QgsMessageLog.logMessage(
                                    f"ITS IA-Adjacent Panel {current_desig} {side_label_its_panel} SKIPPED: Missing 3D base points from IA.",
                                    plugin_tag,
                                    Qgis.Warning,
                                )

                            if P_BLS_inner_3d_side and P_BLS_outer_3d_side:
                                panel_feat = self._generate_its_panel_feature(
                                    P_BLS_inner_3d_side,
                                    P_BLS_outer_3d_side,
                                    its_slope,
                                    IHS_ELEVATION_AMSL,
                                    outward_projection_az_for_panel,
                                    runway_name,
                                    current_desig,
                                    side_label_its_panel,
                                    "BLS Adjacent",
                                    its_ref_mos,
                                    its_fields,
                                )
                                if panel_feat:
                                    ofz_inner_trans_features.append(panel_feat)
                            else:
                                QgsMessageLog.logMessage(
                                    f"ITS BLS-Adjacent Panel {current_desig} {side_label_its_panel} SKIPPED: Missing 3D base points from BLS.",
                                    plugin_tag,
                                    Qgis.Warning,
                                )

                            if P_IA_inner_3d_side and P_BLS_inner_3d_side and ia_cl_start_xy and bls_cl_start_xy:
                                strip_base_seg_3d = self._define_strip_edge_segment_3d(
                                    ia_cl_start_xy,
                                    bls_cl_start_xy,
                                    graded_strip_half_width,
                                    outward_projection_az_for_panel,
                                    primary_threshold_point,
                                    reciprocal_threshold_point,
                                    primary_thr_elev,
                                    reciprocal_thr_elev,
                                )
                                if strip_base_seg_3d:
                                    strip_p1_3d, strip_p2_3d = strip_base_seg_3d
                                    panel_feat = self._generate_its_panel_feature(
                                        strip_p1_3d,
                                        strip_p2_3d,
                                        its_slope,
                                        IHS_ELEVATION_AMSL,
                                        outward_projection_az_for_panel,
                                        runway_name,
                                        current_desig,
                                        side_label_its_panel,
                                        "Strip Adjacent",
                                        its_ref_mos,
                                        its_fields,
                                    )
                                    if panel_feat:
                                        ofz_inner_trans_features.append(panel_feat)
                                else:
                                    QgsMessageLog.logMessage(
                                        f"ITS Strip Panel {current_desig} {side_label_its_panel} SKIPPED: _define_strip_edge_segment_3d None.",
                                        plugin_tag,
                                        Qgis.Warning,
                                    )
                            else:
                                QgsMessageLog.logMessage(
                                    f"ITS Strip Panel {current_desig} {side_label_its_panel} SKIPPED: Missing required alignment points.",
                                    plugin_tag,
                                    Qgis.Warning,
                                )
                    else:
                        QgsMessageLog.logMessage(
                            f"ITS for {current_desig} SKIPPED: Invalid ITS slope.",
                            plugin_tag,
                            Qgis.Warning,
                        )
                else:
                    QgsMessageLog.logMessage(
                        f"ITS for {current_desig} SKIPPED: No ITS parameters found.",
                        plugin_tag,
                        Qgis.Info,
                    )
            else:
                QgsMessageLog.logMessage(
                    f"ITS for {current_desig} SKIPPED: IHS_ELEVATION_AMSL is None.",
                    plugin_tag,
                    Qgis.Warning,
                )

            # --- Main Approach ---
            try:
                app_sections, app_contours = self._generate_approach_surface(
                    runway_data,
                    rwy_params,
                    arc_num,
                    config["approach_type_str"],
                    config["landing_threshold_pt"],
                    config["approach_surface_outward_azimuth"],
                    current_desig,
                    config["landing_threshold_elev"],
                )
                if app_sections:
                    approach_poly_features.extend(app_sections)
                if app_contours:
                    approach_contour_features.extend(app_contours)
            except Exception as e_app:
                QgsMessageLog.logMessage(
                    f"ERROR generating Main Approach for {current_desig}: {e_app}\n{traceback.format_exc()}",
                    plugin_tag,
                    Qgis.Critical,
                )

            # --- Take-off Climb Surface (TOCS) ---
            try:
                tocs_plane_origin_pt = config["tocs_departure_pavement_end_pt"]
                tocs_params_for_offset = ols_dimensions.get_ols_params(arc_num, None, "TOCS")
                origin_offset_param_val = 60.0
                if tocs_params_for_offset:
                    origin_offset_param_val = tocs_params_for_offset.get("origin_offset", 60.0)

                if config["tocs_clearway_len_at_departure_end"] > 1e-6:
                    tocs_plane_origin_pt = tocs_plane_origin_pt.project(
                        config["tocs_clearway_len_at_departure_end"],
                        config["tocs_flight_path_azimuth"],
                    )
                if tocs_plane_origin_pt:
                    tocs_plane_origin_pt = tocs_plane_origin_pt.project(
                        origin_offset_param_val, config["tocs_flight_path_azimuth"]
                    )

                tocs_actual_start_elevation = None
                if tocs_plane_origin_pt:
                    tocs_actual_start_elevation = self._get_elevation_at_point_along_gradient(
                        tocs_plane_origin_pt,
                        phys_pavement_end_near_primary_thr,
                        phys_pavement_end_near_reciprocal_thr,
                        primary_runway_end_elev,
                        reciprocal_runway_end_elev,
                        QgsProject.instance().crs(),
                    )

                if tocs_actual_start_elevation is not None and tocs_plane_origin_pt is not None:
                    tocs_feat, tocs_conts = self._generate_tocs(
                        runway_data,
                        rwy_params,
                        arc_num,
                        config["approach_type_str"],
                        config["tocs_departure_pavement_end_pt"],
                        config["tocs_clearway_len_at_departure_end"],
                        config["tocs_flight_path_azimuth"],
                        current_desig,
                        tocs_actual_start_elevation,
                    )
                    if tocs_feat:
                        tocs_poly_features.append(tocs_feat)
                    if tocs_conts:
                        tocs_contour_features.extend(tocs_conts)
                else:
                    self._log_debug(f"TOCS {current_desig} skipped: missing origin point or elevation.")
            except Exception as e_tocs:
                QgsMessageLog.logMessage(
                    f"ERROR generating TOCS for {current_desig}: {e_tocs}\n{traceback.format_exc()}",
                    plugin_tag,
                    Qgis.Critical,
                )

        # --- END OF LOOP for runway_end_configurations ---

        QgsMessageLog.logMessage(
            f"Finished Runway OFZ processing for {runway_name}. Total BLS features: {len(ofz_bls_features)}, Total ITS features: {len(ofz_inner_trans_features)}",
            plugin_tag,
            Qgis.Success,
        )

        # --- Layer Creation ---
        target_ofz_group = ofz_group if ofz_group is not None else layer_group
        had_ofz_inner_trans_features = bool(ofz_inner_trans_features)

        # Inner Approach Layer
        if inner_approach_features:
            fields = self._get_ols_fields("InnerApproach")
            descriptive_style_key = "OLS Inner Approach"  # Use the descriptive key
            if self._create_and_add_layer(
                "Polygon",
                f"OLS_InnerApproach_{runway_name.replace('/', '_')}",
                f"{self.tr('OLS')} Inner Approach {runway_name}",
                fields,
                inner_approach_features,
                target_ofz_group,
                descriptive_style_key,  # Pass the descriptive key
            ):
                overall_success = True

        # Inner Transitional Layer
        if ofz_inner_trans_features:
            fields = self._get_ols_fields("InnerTransitional")
            descriptive_style_key = "OLS Inner Transitional"  # Use the descriptive key
            if self._create_and_add_layer(
                "Polygon",
                f"OLS_InnerTransitional_{runway_name.replace('/', '_')}",
                f"{self.tr('OLS')} Inner Transitional {runway_name}",
                fields,
                ofz_inner_trans_features,
                target_ofz_group,
                descriptive_style_key,  # Pass the descriptive key
            ):
                overall_success = True

        # Logging for empty ITS on Precision Approach runways
        is_precision_runway = False
        if hasattr(ols_dimensions, "PRECISION_APPROACH_TYPES"):
            current_runway_type_abbrs = {
                ols_dimensions.get_runway_type_abbr(s.get("approach_type_str"))
                for s in runway_end_configurations
                if s.get("approach_type_str")
            }
            is_precision_runway = any(
                abbr in ols_dimensions.PRECISION_APPROACH_TYPES for abbr in current_runway_type_abbrs
            )
        else:
            QgsMessageLog.logMessage(
                "Warning: ols_dimensions.PRECISION_APPROACH_TYPES not found for ITS logging.",
                plugin_tag,
                Qgis.Warning,
            )

        if not had_ofz_inner_trans_features and is_precision_runway:
            QgsMessageLog.logMessage(
                f"Warning: Inner Transitional layer for PA runway {runway_name} is empty. Check ITS generation logic and data extraction.",
                plugin_tag,
                Qgis.Warning,
            )
        elif not had_ofz_inner_trans_features:  # General info if not a PA runway and still empty
            QgsMessageLog.logMessage(
                f"Info: Inner Transitional layer for {runway_name} is empty (may be normal for non-PA or if generation is placeholder).",
                plugin_tag,
                Qgis.Info,
            )

        if ofz_bls_features:
            fields = self._get_ols_fields("BaulkedLanding")
            descriptive_style_key = "OLS Baulked Landing"
            bls_layer = self._create_and_add_layer(
                "Polygon",
                f"OLS_BaulkedLanding_{runway_name.replace('/', '_')}",
                f"{self.tr('OLS')} Baulked Landing {runway_name}",
                fields,
                ofz_bls_features,
                target_ofz_group,
                descriptive_style_key,
            )
            if bls_layer is not None:
                overall_success = True
            else:
                QgsMessageLog.logMessage(
                    f"BLS layer for {runway_name} failed: generated features could not be added to a layer.",
                    plugin_tag,
                    Qgis.Warning,
                )
        else:
            self._log_debug(f"BLS layer for {runway_name} skipped: no features generated.")

        # Approach Sections Layer
        if approach_poly_features:
            fields = self._get_ols_fields("Approach")
            descriptive_style_key = "OLS Approach"
            if self._create_and_add_layer(
                "Polygon",
                f"OLS_Approach_{runway_name.replace('/', '_')}",
                f"{self.tr('OLS')} Approach Sections {runway_name}",
                fields,
                approach_poly_features,
                layer_group,  # Main Approach usually goes in the general OLS group
                descriptive_style_key,
            ):
                overall_success = True

        # Approach Contours Layer
        if approach_contour_features:
            fields = self._get_approach_contour_fields()
            descriptive_style_key = "OLS Approach Contour"
            if self._create_and_add_layer(
                "LineString",
                f"OLS_ApproachContours_{runway_name.replace('/', '_')}",
                f"{self.tr('OLS')} Approach Contours {runway_name}",
                fields,
                approach_contour_features,
                layer_group,
                descriptive_style_key,
            ):
                overall_success = True

        # TOCS Polygons Layer
        if tocs_poly_features:
            fields = self._get_ols_fields("TOCS")
            descriptive_style_key = "OLS TOCS"
            if self._create_and_add_layer(
                "Polygon",
                f"OLS_TOCS_{runway_name.replace('/', '_')}",
                f"{self.tr('OLS')} TOCS {runway_name}",
                fields,
                tocs_poly_features,
                layer_group,
                descriptive_style_key,
            ):
                overall_success = True

        # TOCS Contours Layer
        if tocs_contour_features:
            fields = self._get_tocs_contour_fields()
            descriptive_style_key = "OLS TOCS Contour"
            if self._create_and_add_layer(
                "LineString",
                f"OLS_TOCS_Contours_{runway_name.replace('/', '_')}",
                f"{self.tr('OLS')} TOCS Contours {runway_name}",
                fields,
                tocs_contour_features,
                layer_group,
                descriptive_style_key,
            ):
                overall_success = True

        ols_feature_counts = [
            f"BLS={len(ofz_bls_features)}",
            f"ITS={len(ofz_inner_trans_features)}",
            f"Approach={len(approach_poly_features)}",
            f"Approach contours={len(approach_contour_features)}",
            f"TOCS={len(tocs_poly_features)}",
            f"TOCS contours={len(tocs_contour_features)}",
        ]
        runway_data["ols_feature_counts"] = {
            "OLS BLS": len(ofz_bls_features),
            "OLS ITS": len(ofz_inner_trans_features),
            "OLS Approach": len(approach_poly_features),
            "OLS Approach contours": len(approach_contour_features),
            "OLS TOCS": len(tocs_poly_features),
            "OLS TOCS contours": len(tocs_contour_features),
        }
        generated_feature_counts = dict(runway_data.get("generated_feature_counts", {}))
        generated_feature_counts.update(runway_data["ols_feature_counts"])
        runway_data["generated_feature_counts"] = generated_feature_counts
        QgsMessageLog.logMessage(
            f"Runway OLS {runway_name}: {', '.join(ols_feature_counts)}.",
            plugin_tag,
            level=Qgis.Success if overall_success else Qgis.Warning,
        )
        return overall_success
