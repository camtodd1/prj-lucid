# -*- coding: utf-8 -*-
"""Physical runway geometry generation."""

from typing import List, Optional, Tuple

from qgis.core import Qgis, QgsGeometry, QgsMessageLog  # type: ignore

from .. import ols_dimensions

PLUGIN_TAG = "SafeguardingBuilder"


class PhysicalGeometryMixin:
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

        if disp_thr_1 > 1e-6:
            try:
                line_geom = QgsGeometry.fromPolylineXY([phys_p_start, thr_point])
                if line_geom and not line_geom.isEmpty():
                    line_len = line_geom.length()
                    # Use correct field names: 'rwy', 'desc', 'ref_mos'
                    attributes = {
                        "rwy": runway_name,
                        "desc": "Displaced Threshold Marking",
                        "end_desig": primary_desig,
                        "len_m": round(line_len, 3) if line_len else None,
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
                line_geom = QgsGeometry.fromPolylineXY([phys_p_end, rec_thr_point])
                if line_geom and not line_geom.isEmpty():
                    line_len = line_geom.length()
                    # Use correct field names: 'rwy', 'desc', 'ref_mos'
                    attributes = {
                        "rwy": runway_name,
                        "desc": "Displaced Threshold Marking",
                        "end_desig": reciprocal_desig,
                        "len_m": round(line_len, 3) if line_len else None,
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
                line_geom = QgsGeometry.fromPolylineXY([outermost_p, phys_p_start])
                if line_geom and not line_geom.isEmpty():
                    line_len = line_geom.length()
                    # Use correct field names: 'rwy', 'desc', 'ref_mos'
                    attributes = {
                        "rwy": runway_name,
                        "desc": "Pre-Threshold Area Marking",
                        "end_desig": primary_desig,
                        "len_m": round(line_len, 3) if line_len else None,
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
                line_geom = QgsGeometry.fromPolylineXY([outermost_r, phys_p_end])
                if line_geom and not line_geom.isEmpty():
                    line_len = line_geom.length()
                    # Use correct field names: 'rwy', 'desc', 'ref_mos'
                    attributes = {
                        "rwy": runway_name,
                        "desc": "Pre-Threshold Area Marking",
                        "end_desig": reciprocal_desig,
                        "len_m": round(line_len, 3) if line_len else None,
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

