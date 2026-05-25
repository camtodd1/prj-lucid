"""Optional Airfield Ground Lighting point generation."""

import math
import traceback
from typing import Dict, List

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

from ..dimensions.agl_dimensions import (
    LIGHT_COLOUR_FLASHING_WHITE,
    LIGHT_COLOUR_GREEN,
    LIGHT_COLOUR_RED,
    LIGHT_COLOUR_VARIABLE_WHITE,
    LIGHT_COLOUR_WHITE,
    LIGHT_COLOUR_YELLOW,
    MOS_REF_DISPLACED_THRESHOLD_EDGE,
    MOS_REF_RUNWAY_EDGE,
    MOS_REF_RUNWAY_CENTRELINE,
    MOS_REF_RUNWAY_END,
    MOS_REF_RTIL,
    MOS_REF_STOPWAY,
    MOS_REF_TDZ,
    MOS_REF_TEMP_DISPLACED_THRESHOLD,
    MOS_REF_THRESHOLD_LOCATION,
    MOS_REF_THRESHOLD_NON_PRECISION,
    MOS_REF_THRESHOLD_PRECISION,
    MOS_REF_THRESHOLD_WING_BARS,
    RUNWAY_LIGHTING_MIN_WIDTH_M,
    RUNWAY_CENTRELINE_MAX_OFFSET_M,
    RTIL_DEFAULT_LATERAL_FROM_EDGE_LIGHTS_M,
    STOPWAY_END_MIN_LIGHTS,
    TDZ_BARRETTE_LIGHTS,
    TDZ_BARRETTE_SPACING_M,
    TDZ_FIRST_ROW_OFFSET_M,
    TDZ_INNER_OFFSET_M,
    TDZ_LENGTH_M,
    TDZ_MARKING_LENGTH_M,
    TDZ_ROW_SPACING_M,
    TEMP_DISPLACED_THRESHOLD_SPACING_M,
    THRESHOLD_WING_BAR_LIGHTS_PER_SIDE,
    THRESHOLD_WING_BAR_SPACING_M,
    approach_profile_for_end,
    runway_centreline_required,
    runway_centreline_recommended,
    runway_centreline_spacing,
    runway_edge_spacing_for_end,
    runway_is_precision,
    temp_displaced_threshold_lights_per_side,
    runway_end_light_count_for_end,
    threshold_light_count_for_end,
)

PLUGIN_TAG = "SafeguardingBuilder"


class AirfieldGroundLightingMixin:
    """Generate opt-in AGL point layers from runway geometry and lighting inputs."""

    def process_airfield_ground_lighting(
        self,
        processed_runway_data_list: List[dict],
        agl_options: Dict[str, object],
        layer_group: QgsLayerTreeGroup,
    ) -> bool:
        if not agl_options or not agl_options.get("enabled"):
            QgsMessageLog.logMessage("Airfield Ground Lighting skipped: option not enabled.", PLUGIN_TAG, Qgis.Info)
            return False
        if layer_group is None:
            QgsMessageLog.logMessage("Airfield Ground Lighting skipped: layer group missing.", PLUGIN_TAG, Qgis.Warning)
            return False

        threshold_inset_m = float(agl_options.get("threshold_inset_m") or 0.0)
        centreline_offset_m = min(
            float(agl_options.get("centreline_offset_m") or 0.0),
            RUNWAY_CENTRELINE_MAX_OFFSET_M,
        )
        default_approach_spacing_m = float(agl_options.get("approach_spacing_m") or 30.0)
        approach_rows = self._agl_rows_by_runway_end(agl_options.get("approach_lighting", []))
        for option_name in [
            "runway_end_lights",
            "threshold_wing_bars",
            "rtil",
            "temp_displaced_threshold",
            "stopway_lights",
            "centreline_lights",
            "centreline_low_visibility",
            "cat_i_centreline_lights",
            "tdz_lights",
            "cat_i_tdz_lights",
        ]:
            approach_rows[("__options__", option_name)] = bool(agl_options.get(option_name, False))

        overall_success = False
        for runway_data in processed_runway_data_list:
            try:
                runway_success = self._create_agl_layer_for_runway(
                    runway_data,
                    layer_group,
                    threshold_inset_m,
                    centreline_offset_m,
                    default_approach_spacing_m,
                    approach_rows,
                )
                overall_success = overall_success or runway_success
            except Exception as e:
                runway_name = runway_data.get("short_name", f"RWY_{runway_data.get('original_index', '?')}")
                QgsMessageLog.logMessage(
                    f"Error generating AGL for {runway_name}: {e}\n{traceback.format_exc()}",
                    PLUGIN_TAG,
                    level=Qgis.Critical,
                )
        return overall_success

    def _create_agl_layer_for_runway(
        self,
        runway_data: dict,
        layer_group: QgsLayerTreeGroup,
        threshold_inset_m: float,
        centreline_offset_m: float,
        default_approach_spacing_m: float,
        approach_rows: Dict[tuple, Dict[str, object]],
    ) -> bool:
        runway_name = runway_data.get("short_name", f"RWY_{runway_data.get('original_index', '?')}")
        runway_index = runway_data.get("original_index")
        thr_point = runway_data.get("thr_point")
        rec_thr_point = runway_data.get("rec_thr_point")
        runway_width = runway_data.get("width")
        if thr_point is None or rec_thr_point is None or not runway_width:
            QgsMessageLog.logMessage(
                f"AGL skipped for {runway_name}: threshold points or runway width missing.",
                PLUGIN_TAG,
                level=Qgis.Warning,
            )
            return False

        params = self._get_runway_parameters(thr_point, rec_thr_point)
        if not params:
            return False

        fields = self._agl_fields()
        features: List[QgsFeature] = []
        lit_half_width = max(float(runway_width), RUNWAY_LIGHTING_MIN_WIDTH_M) / 2.0
        primary_desig, reciprocal_desig = self._agl_end_designators(runway_name)
        primary_type = runway_data.get("type1", "")
        reciprocal_type = runway_data.get("type2", "")
        disp_primary = self._non_negative_float(runway_data.get("thr_displaced_1"), 0.0)
        disp_reciprocal = self._non_negative_float(runway_data.get("thr_displaced_2"), 0.0)
        physical_endpoints = self._get_physical_runway_endpoints(
            thr_point,
            rec_thr_point,
            disp_primary,
            disp_reciprocal,
            params,
        )
        phys_primary, phys_reciprocal, physical_length = (
            physical_endpoints if physical_endpoints is not None else (thr_point, rec_thr_point, params["length"])
        )
        edge_spacing_m = min(
            runway_edge_spacing_for_end(primary_type),
            runway_edge_spacing_for_end(reciprocal_type),
        )
        precision_runway = runway_is_precision(primary_type) or runway_is_precision(reciprocal_type)
        edge_start_offset_m = edge_spacing_m if precision_runway else 0.0
        edge_end_offset_m = edge_spacing_m if precision_runway else 0.0
        physical_params = {**params, "length": physical_length}

        self._append_runway_edge_lights(
            features,
            fields,
            runway_name,
            phys_primary,
            physical_params,
            lit_half_width,
            edge_spacing_m,
            edge_start_offset_m,
            edge_end_offset_m,
            disp_primary,
            disp_reciprocal,
            precision_runway,
        )
        self._append_threshold_lights(
            features,
            fields,
            runway_name,
            primary_desig,
            primary_type,
            thr_point,
            params["azimuth_perp_l"],
            params["azimuth_perp_r"],
            params["azimuth_r_p"],
            lit_half_width,
            threshold_inset_m,
        )

        if self._agl_option_enabled(approach_rows, "runway_end_lights"):
            self._append_runway_end_lights(
                features,
                fields,
                runway_name,
                primary_desig,
                primary_type,
                phys_primary,
                params["azimuth_perp_l"],
                params["azimuth_perp_r"],
                params["azimuth_p_r"],
                lit_half_width,
            )
            self._append_runway_end_lights(
                features,
                fields,
                runway_name,
                reciprocal_desig,
                reciprocal_type,
                phys_reciprocal,
                params["azimuth_perp_l"],
                params["azimuth_perp_r"],
                params["azimuth_r_p"],
                lit_half_width,
            )

        if approach_rows.get(("__options__", "threshold_wing_bars")):
            for end_desig, runway_type, point in [
                (primary_desig, primary_type, thr_point),
                (reciprocal_desig, reciprocal_type, rec_thr_point),
            ]:
                if runway_is_precision(runway_type):
                    self._append_threshold_wing_bars(
                        features,
                        fields,
                        runway_name,
                        end_desig,
                        point,
                        params["azimuth_perp_l"],
                        params["azimuth_perp_r"],
                        lit_half_width,
                    )

        if approach_rows.get(("__options__", "rtil")):
            for end_desig, point, displacement_m in [
                (primary_desig, thr_point, disp_primary),
                (reciprocal_desig, rec_thr_point, disp_reciprocal),
            ]:
                if displacement_m > 0:
                    self._append_rtil(
                        features,
                        fields,
                        runway_name,
                        end_desig,
                        point,
                        params["azimuth_perp_l"],
                        params["azimuth_perp_r"],
                        lit_half_width,
                    )

        if approach_rows.get(("__options__", "temp_displaced_threshold")):
            for end_desig, point, displacement_m in [
                (primary_desig, thr_point, disp_primary),
                (reciprocal_desig, rec_thr_point, disp_reciprocal),
            ]:
                if displacement_m > 0:
                    self._append_temp_displaced_threshold_lights(
                        features,
                        fields,
                        runway_name,
                        end_desig,
                        point,
                        params["azimuth_perp_l"],
                        params["azimuth_perp_r"],
                        lit_half_width,
                    )

        if approach_rows.get(("__options__", "stopway_lights")):
            self._append_stopway_lights(
                features,
                fields,
                runway_name,
                primary_desig,
                phys_primary,
                params["azimuth_r_p"],
                params["azimuth_perp_l"],
                params["azimuth_perp_r"],
                lit_half_width,
                self._non_negative_float(runway_data.get("stopway1_len"), 0.0),
                edge_spacing_m,
            )
            self._append_stopway_lights(
                features,
                fields,
                runway_name,
                reciprocal_desig,
                phys_reciprocal,
                params["azimuth_p_r"],
                params["azimuth_perp_l"],
                params["azimuth_perp_r"],
                lit_half_width,
                self._non_negative_float(runway_data.get("stopway2_len"), 0.0),
                edge_spacing_m,
            )

        centreline_low_visibility = bool(approach_rows.get(("__options__", "centreline_low_visibility")))
        centreline_required = runway_centreline_required(primary_type, reciprocal_type, centreline_low_visibility)
        centreline_recommended = bool(approach_rows.get(("__options__", "cat_i_centreline_lights"))) and (
            runway_centreline_recommended(primary_type, reciprocal_type, lit_half_width * 2.0)
        )
        if approach_rows.get(("__options__", "centreline_lights")) and (centreline_required or centreline_recommended):
            self._append_runway_centreline_lights(
                features,
                fields,
                runway_name,
                phys_primary,
                params["azimuth_p_r"],
                params["azimuth_perp_l"],
                physical_length,
                runway_centreline_spacing(centreline_low_visibility),
                centreline_offset_m,
            )

        if approach_rows.get(("__options__", "tdz_lights")):
            for end_role, end_desig, runway_type, origin, azimuth in [
                ("primary", primary_desig, primary_type, thr_point, params["azimuth_p_r"]),
                ("reciprocal", reciprocal_desig, reciprocal_type, rec_thr_point, params["azimuth_r_p"]),
            ]:
                cat_ii_iii = "Precision Approach CAT II/III" in (runway_type or "")
                cat_i_optional = "Precision Approach CAT I" in (runway_type or "") and approach_rows.get(
                    ("__options__", "cat_i_tdz_lights")
                )
                if cat_ii_iii or cat_i_optional:
                    self._append_tdz_lights(
                        features,
                        fields,
                        runway_name,
                        end_desig,
                        origin,
                        azimuth,
                        params["azimuth_perp_l"],
                        params["azimuth_perp_r"],
                        self._tdz_lighting_extent(runway_data, end_desig, runway_type, physical_length),
                    )
        self._append_threshold_lights(
            features,
            fields,
            runway_name,
            reciprocal_desig,
            reciprocal_type,
            rec_thr_point,
            params["azimuth_perp_l"],
            params["azimuth_perp_r"],
            params["azimuth_p_r"],
            lit_half_width,
            threshold_inset_m,
        )

        for end_role, end_desig, runway_type, origin, outward_azimuth in [
            ("primary", primary_desig, primary_type, thr_point, params["azimuth_r_p"]),
            ("reciprocal", reciprocal_desig, reciprocal_type, rec_thr_point, params["azimuth_p_r"]),
        ]:
            row = approach_rows.get((runway_index, end_role))
            profile = approach_profile_for_end(runway_type)
            if not row and not profile.get("length_m"):
                continue
            length_m = float(row.get("length_m") if row else profile.get("length_m") or 0.0)
            spacing_m = float(row.get("spacing_m") if row else profile.get("spacing_m") or default_approach_spacing_m)
            self._append_approach_lights(
                features,
                fields,
                runway_name,
                end_desig,
                origin,
                outward_azimuth,
                length_m,
                spacing_m,
                profile,
            )

        features = self._resolve_overlapping_agl_features(features, fields)
        layer = self._create_and_add_layer(
            "Point",
            f"AGL_{runway_name.replace('/', '_')}",
            f"{self.tr('AGL Lights')} {runway_name}",
            fields,
            features,
            layer_group,
            "AGL Light",
        )
        return layer is not None

    def _append_runway_edge_lights(
        self,
        features: List[QgsFeature],
        fields: QgsFields,
        runway_name: str,
        thr_point: QgsPointXY,
        params: dict,
        half_width: float,
        spacing_m: float,
        start_offset_m: float,
        end_offset_m: float,
        disp_primary_m: float,
        disp_reciprocal_m: float,
        precision_runway: bool,
    ) -> None:
        available_length_m = max(0.0, params["length"] - start_offset_m - end_offset_m)
        if available_length_m <= 0:
            return
        count = self._agl_interval_count(available_length_m, spacing_m)
        for index in range(count + 1):
            offset_m = min(start_offset_m + index * spacing_m, params["length"] - end_offset_m)
            centre = thr_point.project(offset_m, params["azimuth_p_r"])
            if centre is None:
                continue
            left = centre.project(half_width, params["azimuth_perp_l"])
            right = centre.project(half_width, params["azimuth_perp_r"])
            primary_colour_raw = self._runway_edge_light_colour_for_direction(
                offset_m,
                params["length"],
                disp_primary_m,
                landing_from_primary=True,
            )
            reciprocal_colour_raw = self._runway_edge_light_colour_for_direction(
                offset_m,
                params["length"],
                disp_reciprocal_m,
                landing_from_primary=False,
            )
            primary_colour = self._runway_edge_display_colour(primary_colour_raw, reciprocal_colour_raw)
            reciprocal_colour = self._runway_edge_display_colour(reciprocal_colour_raw, primary_colour_raw)
            colour = self._combined_light_colour(primary_colour, reciprocal_colour)
            ref_mos = (
                MOS_REF_DISPLACED_THRESHOLD_EDGE
                if LIGHT_COLOUR_RED in {primary_colour_raw, reciprocal_colour_raw}
                else MOS_REF_RUNWAY_EDGE
            )
            if left is not None:
                features.append(
                    self._agl_feature(
                        fields,
                        left,
                        runway_name,
                        "",
                        "Runway Edge",
                        "Left",
                        spacing_m,
                        offset_m,
                        colour,
                        ref_mos,
                        colour_primary=primary_colour,
                        colour_reciprocal=reciprocal_colour,
                        angle_deg=params["azimuth_r_p"],
                        symbol_angle_deg=params["azimuth_r_p"],
                    )
                )
            if right is not None:
                features.append(
                    self._agl_feature(
                        fields,
                        right,
                        runway_name,
                        "",
                        "Runway Edge",
                        "Right",
                        spacing_m,
                        offset_m,
                        colour,
                        ref_mos,
                        colour_primary=primary_colour,
                        colour_reciprocal=reciprocal_colour,
                        angle_deg=params["azimuth_r_p"],
                        symbol_angle_deg=params["azimuth_r_p"],
                    )
                )

    def _append_threshold_lights(
        self,
        features: List[QgsFeature],
        fields: QgsFields,
        runway_name: str,
        end_desig: str,
        runway_type: str,
        threshold_point: QgsPointXY,
        azimuth_left: float,
        azimuth_right: float,
        observable_azimuth: float,
        half_width: float,
        inset_m: float,
    ) -> None:
        usable_half_width = max(0.0, half_width - inset_m)
        if usable_half_width <= 0:
            return
        light_count = threshold_light_count_for_end(runway_type, half_width * 2.0)
        ref_mos = (
            f"{MOS_REF_THRESHOLD_LOCATION}; {MOS_REF_THRESHOLD_PRECISION}"
            if runway_is_precision(runway_type)
            else f"{MOS_REF_THRESHOLD_LOCATION}; {MOS_REF_THRESHOLD_NON_PRECISION}"
        )
        spacing_m = (usable_half_width * 2.0) / max(1, light_count - 1)
        positions = self._agl_lateral_offsets_by_count(usable_half_width, light_count)
        for lateral_m in positions:
            side = "Centre" if abs(lateral_m) < 1e-6 else ("Left" if lateral_m < 0 else "Right")
            azimuth = azimuth_left if lateral_m < 0 else azimuth_right
            point = threshold_point if abs(lateral_m) < 1e-6 else threshold_point.project(abs(lateral_m), azimuth)
            if point is not None:
                features.append(
                    self._agl_feature(
                        fields,
                        point,
                        runway_name,
                        end_desig,
                        "Threshold",
                        side,
                        spacing_m,
                        abs(lateral_m),
                        LIGHT_COLOUR_GREEN,
                        ref_mos,
                        angle_deg=observable_azimuth,
                        symbol_angle_deg=observable_azimuth,
                    )
                )

    def _append_approach_lights(
        self,
        features: List[QgsFeature],
        fields: QgsFields,
        runway_name: str,
        end_desig: str,
        threshold_point: QgsPointXY,
        outward_azimuth: float,
        length_m: float,
        spacing_m: float,
        profile: Dict[str, object],
    ) -> None:
        if length_m <= 0 or spacing_m <= 0:
            return
        ref_mos = str(profile.get("ref_mos", ""))
        count = self._agl_interval_count(length_m, spacing_m)
        for index in range(1, count + 1):
            offset_m = min(index * spacing_m, length_m)
            point = threshold_point.project(offset_m, outward_azimuth)
            if point is not None:
                features.append(
                    self._agl_feature(
                        fields,
                        point,
                        runway_name,
                        end_desig,
                        "Approach Centreline",
                        "Centre",
                        spacing_m,
                        offset_m,
                        LIGHT_COLOUR_WHITE,
                        ref_mos,
                    )
                )
        for crossbar_m in profile.get("crossbars_m", []):
            crossbar_offset_m = float(crossbar_m)
            if crossbar_offset_m > length_m:
                continue
            crossbar_center = threshold_point.project(crossbar_offset_m, outward_azimuth)
            if crossbar_center is None:
                continue
            crossbar_half_width_m = float(profile.get("crossbar_length_m") or 0.0) / 2.0
            for lateral_m in self._agl_lateral_offsets(crossbar_half_width_m, 3.0):
                azimuth = (
                    (outward_azimuth - 90.0 + 360.0) % 360.0 if lateral_m < 0 else (outward_azimuth + 90.0) % 360.0
                )
                point = crossbar_center if abs(lateral_m) < 1e-6 else crossbar_center.project(abs(lateral_m), azimuth)
                if point is not None:
                    features.append(
                        self._agl_feature(
                            fields,
                            point,
                            runway_name,
                            end_desig,
                            "Approach Crossbar",
                            "Centre",
                            3.0,
                            crossbar_offset_m,
                            LIGHT_COLOUR_WHITE,
                            ref_mos,
                        )
                    )

    def _append_runway_end_lights(
        self,
        features: List[QgsFeature],
        fields: QgsFields,
        runway_name: str,
        end_desig: str,
        runway_type: str,
        runway_end_point: QgsPointXY,
        azimuth_left: float,
        azimuth_right: float,
        observable_azimuth: float,
        half_width: float,
    ) -> None:
        light_count = runway_end_light_count_for_end(runway_type, half_width * 2.0)
        spacing_m = (half_width * 2.0) / max(1, light_count - 1)
        for lateral_m in self._agl_lateral_offsets_by_count(half_width, light_count):
            side = "Centre" if abs(lateral_m) < 1e-6 else ("Left" if lateral_m < 0 else "Right")
            azimuth = azimuth_left if lateral_m < 0 else azimuth_right
            point = runway_end_point if abs(lateral_m) < 1e-6 else runway_end_point.project(abs(lateral_m), azimuth)
            if point is not None:
                features.append(
                    self._agl_feature(
                        fields,
                        point,
                        runway_name,
                        end_desig,
                        "Runway End",
                        side,
                        spacing_m,
                        abs(lateral_m),
                        LIGHT_COLOUR_RED,
                        MOS_REF_RUNWAY_END,
                        angle_deg=observable_azimuth,
                        symbol_angle_deg=observable_azimuth,
                    )
                )

    def _append_threshold_wing_bars(
        self,
        features: List[QgsFeature],
        fields: QgsFields,
        runway_name: str,
        end_desig: str,
        threshold_point: QgsPointXY,
        azimuth_left: float,
        azimuth_right: float,
        half_width: float,
    ) -> None:
        for side_name, azimuth in [("Left", azimuth_left), ("Right", azimuth_right)]:
            for index in range(THRESHOLD_WING_BAR_LIGHTS_PER_SIDE):
                lateral_m = half_width + index * THRESHOLD_WING_BAR_SPACING_M
                point = threshold_point.project(lateral_m, azimuth)
                if point is not None:
                    features.append(
                        self._agl_feature(
                            fields,
                            point,
                            runway_name,
                            end_desig,
                            "Threshold Wing Bar",
                            side_name,
                            THRESHOLD_WING_BAR_SPACING_M,
                            lateral_m,
                            LIGHT_COLOUR_GREEN,
                            MOS_REF_THRESHOLD_WING_BARS,
                        )
                    )

    def _append_rtil(
        self,
        features: List[QgsFeature],
        fields: QgsFields,
        runway_name: str,
        end_desig: str,
        threshold_point: QgsPointXY,
        azimuth_left: float,
        azimuth_right: float,
        half_width: float,
    ) -> None:
        lateral_m = half_width + RTIL_DEFAULT_LATERAL_FROM_EDGE_LIGHTS_M
        for side_name, azimuth in [("Left", azimuth_left), ("Right", azimuth_right)]:
            point = threshold_point.project(lateral_m, azimuth)
            if point is not None:
                features.append(
                    self._agl_feature(
                        fields,
                        point,
                        runway_name,
                        end_desig,
                        "RTIL",
                        side_name,
                        0.0,
                        lateral_m,
                        LIGHT_COLOUR_FLASHING_WHITE,
                        MOS_REF_RTIL,
                    )
                )

    def _append_temp_displaced_threshold_lights(
        self,
        features: List[QgsFeature],
        fields: QgsFields,
        runway_name: str,
        end_desig: str,
        threshold_point: QgsPointXY,
        azimuth_left: float,
        azimuth_right: float,
        half_width: float,
    ) -> None:
        lights_per_side = temp_displaced_threshold_lights_per_side(half_width * 2.0)
        for side_name, azimuth in [("Left", azimuth_left), ("Right", azimuth_right)]:
            for index in range(lights_per_side):
                lateral_m = half_width + index * TEMP_DISPLACED_THRESHOLD_SPACING_M
                point = threshold_point.project(lateral_m, azimuth)
                if point is not None:
                    features.append(
                        self._agl_feature(
                            fields,
                            point,
                            runway_name,
                            end_desig,
                            "Temporary Displaced Threshold",
                            side_name,
                            TEMP_DISPLACED_THRESHOLD_SPACING_M,
                            lateral_m,
                            LIGHT_COLOUR_GREEN,
                            MOS_REF_TEMP_DISPLACED_THRESHOLD,
                        )
                    )

    def _append_stopway_lights(
        self,
        features: List[QgsFeature],
        fields: QgsFields,
        runway_name: str,
        end_desig: str,
        start_point: QgsPointXY,
        outward_azimuth: float,
        azimuth_left: float,
        azimuth_right: float,
        half_width: float,
        stopway_length_m: float,
        spacing_m: float,
    ) -> None:
        if stopway_length_m <= 0:
            return
        count = self._agl_interval_count(stopway_length_m, spacing_m)
        for index in range(1, count + 1):
            longitudinal_m = min(index * spacing_m, stopway_length_m)
            centre = start_point.project(longitudinal_m, outward_azimuth)
            if centre is None:
                continue
            for side_name, azimuth in [("Left", azimuth_left), ("Right", azimuth_right)]:
                point = centre.project(half_width, azimuth)
                if point is not None:
                    features.append(
                        self._agl_feature(
                            fields,
                            point,
                            runway_name,
                            end_desig,
                            "Stopway Edge",
                            side_name,
                            spacing_m,
                            longitudinal_m,
                            LIGHT_COLOUR_RED,
                            MOS_REF_STOPWAY,
                        )
                    )
        stopway_end = start_point.project(stopway_length_m, outward_azimuth)
        if stopway_end is None:
            return
        for lateral_m in self._agl_lateral_offsets_by_count(half_width, STOPWAY_END_MIN_LIGHTS):
            azimuth = azimuth_left if lateral_m < 0 else azimuth_right
            point = stopway_end if abs(lateral_m) < 1e-6 else stopway_end.project(abs(lateral_m), azimuth)
            if point is not None:
                features.append(
                    self._agl_feature(
                        fields,
                        point,
                        runway_name,
                        end_desig,
                        "Stopway End",
                        "Centre",
                        half_width * 2.0,
                        stopway_length_m,
                        LIGHT_COLOUR_RED,
                        MOS_REF_STOPWAY,
                    )
                )

    def _append_runway_centreline_lights(
        self,
        features: List[QgsFeature],
        fields: QgsFields,
        runway_name: str,
        start_point: QgsPointXY,
        azimuth: float,
        azimuth_left: float,
        length_m: float,
        spacing_m: float,
        lateral_offset_m: float,
    ) -> None:
        count = self._agl_interval_count(length_m, spacing_m)
        for index in range(count + 1):
            offset_m = min(index * spacing_m, length_m)
            point = start_point.project(offset_m, azimuth)
            if point is not None and lateral_offset_m > 0:
                point = point.project(lateral_offset_m, azimuth_left)
            if point is None:
                continue
            primary_colour = self._runway_centreline_colour_for_direction(
                distance_to_end=max(0.0, length_m - offset_m),
                sequence_index=index,
            )
            reciprocal_colour = self._runway_centreline_colour_for_direction(
                distance_to_end=offset_m,
                sequence_index=int(round((length_m - offset_m) / spacing_m)) if spacing_m > 0 else index,
            )
            colour = self._combined_light_colour(primary_colour, reciprocal_colour)
            features.append(
                self._agl_feature(
                    fields,
                    point,
                    runway_name,
                    "",
                    "Runway Centreline",
                    "Centre",
                    spacing_m,
                    offset_m,
                    colour,
                    MOS_REF_RUNWAY_CENTRELINE,
                    colour_primary=primary_colour,
                    colour_reciprocal=reciprocal_colour,
                    angle_deg=azimuth + 180.0,
                    symbol_angle_deg=azimuth + 180.0,
                )
            )

    def _runway_centreline_colour_for_direction(self, distance_to_end: float, sequence_index: int) -> str:
        if distance_to_end <= 300.0:
            return LIGHT_COLOUR_RED
        if distance_to_end <= 900.0:
            return LIGHT_COLOUR_RED if (sequence_index // 2) % 2 == 0 else LIGHT_COLOUR_WHITE
        return LIGHT_COLOUR_WHITE

    def _combined_light_colour(self, primary_colour: str, reciprocal_colour: str) -> str:
        if primary_colour == reciprocal_colour:
            return primary_colour
        return f"{primary_colour}/{reciprocal_colour}"

    def _append_tdz_lights(
        self,
        features: List[QgsFeature],
        fields: QgsFields,
        runway_name: str,
        end_desig: str,
        threshold_point: QgsPointXY,
        runway_azimuth: float,
        azimuth_left: float,
        azimuth_right: float,
        length_m: float,
    ) -> None:
        if length_m < TDZ_FIRST_ROW_OFFSET_M:
            return
        row_count = self._agl_interval_count(length_m - TDZ_FIRST_ROW_OFFSET_M, TDZ_ROW_SPACING_M)
        for row_index in range(row_count + 1):
            longitudinal_m = TDZ_FIRST_ROW_OFFSET_M + row_index * TDZ_ROW_SPACING_M
            if longitudinal_m > length_m:
                continue
            row_center = threshold_point.project(longitudinal_m, runway_azimuth)
            if row_center is None:
                continue
            for side_name, side_azimuth in [("Left", azimuth_left), ("Right", azimuth_right)]:
                for light_index in range(TDZ_BARRETTE_LIGHTS):
                    lateral_m = TDZ_INNER_OFFSET_M + light_index * TDZ_BARRETTE_SPACING_M
                    point = row_center.project(lateral_m, side_azimuth)
                    if point is not None:
                        features.append(
                            self._agl_feature(
                                fields,
                                point,
                                runway_name,
                                end_desig,
                                "TDZ Barrette",
                                side_name,
                                TDZ_BARRETTE_SPACING_M,
                                longitudinal_m,
                                LIGHT_COLOUR_VARIABLE_WHITE,
                                MOS_REF_TDZ,
                            )
                        )

    def _tdz_lighting_extent(
        self,
        runway_data: dict,
        end_desig: str,
        runway_type: str,
        runway_length_m: float,
    ) -> float:
        """Return MOS 9.72 TDZ light extent: lesser of 900 m and MOS 8.24 TDZ marking length."""
        rendered_extents = runway_data.get("tdz_marking_extents") or {}
        rendered_extent = rendered_extents.get(end_desig)
        if rendered_extent is not None:
            try:
                return min(TDZ_LENGTH_M, float(rendered_extent))
            except (TypeError, ValueError):
                pass

        lda_m = self._declared_lda_for_end(runway_data, end_desig, runway_length_m)
        touchdown_offsets = self._touchdown_zone_offsets(lda_m)
        if not touchdown_offsets:
            return 0.0

        aim_offset = None
        aim_rule = self._aiming_point_rule(runway_data.get("width") or 0.0, lda_m, runway_type)
        if aim_rule is not None:
            aim_offset = aim_rule[0]

        valid_offsets = []
        midpoint_zone_start = runway_length_m / 2.0 - 275.0
        midpoint_zone_end = runway_length_m / 2.0 + 275.0
        for offset in touchdown_offsets:
            if aim_offset is not None and abs(offset - aim_offset) <= 50.0:
                continue
            block_start = offset
            block_end = offset + TDZ_MARKING_LENGTH_M
            if block_start < midpoint_zone_end and block_end > midpoint_zone_start:
                continue
            valid_offsets.append(offset)

        if not valid_offsets:
            return 0.0
        tdz_marking_length_m = max(valid_offsets) + TDZ_MARKING_LENGTH_M
        QgsMessageLog.logMessage(
            (
                f"AGL TDZ extent for {runway_data.get('short_name', 'runway')} {end_desig} "
                "used calculated MOS 8.24 extent because rendered TDZ marking extent metadata was unavailable."
            ),
            PLUGIN_TAG,
            level=Qgis.Info,
        )
        return min(TDZ_LENGTH_M, tdz_marking_length_m)

    def _agl_feature(
        self,
        fields: QgsFields,
        point: QgsPointXY,
        runway_name: str,
        end_desig: str,
        light_type: str,
        side: str,
        spacing_m: float,
        offset_m: float,
        colour: str,
        ref_mos: str,
        colour_primary: str = "",
        colour_reciprocal: str = "",
        angle_deg: float = 0.0,
        symbol_angle_deg: float = 0.0,
    ) -> QgsFeature:
        feature = QgsFeature(fields)
        feature.setGeometry(QgsGeometry.fromPointXY(point))
        feature.setAttributes(
            [
                runway_name,
                end_desig,
                light_type,
                side,
                colour,
                colour_primary or colour,
                colour_reciprocal or colour,
                round(float(spacing_m), 3),
                round(float(offset_m), 3),
                round(float(angle_deg) % 360.0, 3),
                round(float(symbol_angle_deg) % 360.0, 3),
                ref_mos,
                "MOS-derived",
            ]
        )
        return feature

    def _resolve_overlapping_agl_features(self, features: List[QgsFeature], fields: QgsFields) -> List[QgsFeature]:
        grouped_features: Dict[tuple, List[QgsFeature]] = {}
        for feature in features:
            point = feature.geometry().asPoint()
            key = (
                feature.attribute("rwy"),
                round(float(point.x()), 3),
                round(float(point.y()), 3),
            )
            grouped_features.setdefault(key, []).append(feature)

        resolved_features = []
        for group in grouped_features.values():
            if len(group) == 1:
                resolved_features.extend(group)
                continue

            threshold_feature = self._first_agl_feature_of_type(group, "Threshold")
            runway_end_feature = self._first_agl_feature_of_type(group, "Runway End")
            if threshold_feature is not None and runway_end_feature is not None:
                resolved_features.append(
                    self._combined_threshold_runway_end_feature(fields, threshold_feature, runway_end_feature)
                )
                continue

            highest_priority = max(self._agl_overlap_priority(feature) for feature in group)
            kept_signatures = set()
            for feature in group:
                if self._agl_overlap_priority(feature) != highest_priority:
                    continue
                signature = (
                    feature.attribute("light_type"),
                    feature.attribute("side"),
                    feature.attribute("colour"),
                    feature.attribute("end_desig"),
                )
                if signature in kept_signatures:
                    continue
                kept_signatures.add(signature)
                resolved_features.append(feature)

        return resolved_features

    def _first_agl_feature_of_type(self, features: List[QgsFeature], light_type: str) -> QgsFeature | None:
        for feature in features:
            if feature.attribute("light_type") == light_type:
                return feature
        return None

    def _combined_threshold_runway_end_feature(
        self,
        fields: QgsFields,
        threshold_feature: QgsFeature,
        runway_end_feature: QgsFeature,
    ) -> QgsFeature:
        point = threshold_feature.geometry().asPoint()
        ref_mos = f"{threshold_feature.attribute('ref_mos')}; {runway_end_feature.attribute('ref_mos')}"
        return self._agl_feature(
            fields,
            QgsPointXY(point),
            threshold_feature.attribute("rwy"),
            threshold_feature.attribute("end_desig") or runway_end_feature.attribute("end_desig"),
            "Threshold / Runway End",
            threshold_feature.attribute("side"),
            threshold_feature.attribute("spacing_m") or runway_end_feature.attribute("spacing_m") or 0.0,
            threshold_feature.attribute("offset_m") or runway_end_feature.attribute("offset_m") or 0.0,
            "green/red",
            ref_mos,
            colour_primary=LIGHT_COLOUR_GREEN,
            colour_reciprocal=LIGHT_COLOUR_RED,
            angle_deg=float(threshold_feature.attribute("angle_deg") or 0.0),
            symbol_angle_deg=float(
                threshold_feature.attribute("symbol_ang") or threshold_feature.attribute("angle_deg") or 0.0
            ),
        )

    def _agl_overlap_priority(self, feature: QgsFeature) -> int:
        light_type = feature.attribute("light_type")
        priorities = {
            "Stopway End": 90,
            "Threshold / Runway End": 85,
            "Runway End": 80,
            "Threshold": 80,
            "Temporary Displaced Threshold": 75,
            "RTIL": 75,
            "Threshold Wing Bar": 70,
            "TDZ Barrette": 65,
            "Runway Centreline": 60,
            "Approach Crossbar": 55,
            "Approach Centreline": 50,
            "Stopway Edge": 40,
            "Runway Edge": 30,
        }
        return priorities.get(str(light_type), 10)

    def _agl_fields(self) -> QgsFields:
        return QgsFields(
            [
                QgsField("rwy", QVariant.String, self.tr("Runway Name"), 30),
                QgsField("end_desig", QVariant.String, self.tr("End Designator"), 10),
                QgsField("light_type", QVariant.String, self.tr("Light Type"), 30),
                QgsField("side", QVariant.String, self.tr("Side"), 12),
                QgsField("colour", QVariant.String, self.tr("Colour"), 20),
                QgsField("colour_p", QVariant.String, self.tr("Primary Direction Colour"), 20),
                QgsField("colour_r", QVariant.String, self.tr("Reciprocal Direction Colour"), 20),
                QgsField("spacing_m", QVariant.Double, self.tr("Spacing (m)"), 12, 3),
                QgsField("offset_m", QVariant.Double, self.tr("Offset (m)"), 12, 3),
                QgsField("angle_deg", QVariant.Double, self.tr("Display Angle (deg)"), 12, 3),
                QgsField("symbol_ang", QVariant.Double, self.tr("Symbol Angle (deg)"), 12, 3),
                QgsField("ref_mos", QVariant.String, self.tr("MOS Reference"), 80),
                QgsField("source", QVariant.String, self.tr("Source"), 80),
            ]
        )

    def _agl_rows_by_runway_end(self, approach_rows) -> Dict[tuple, Dict[str, object]]:
        rows = {}
        if not isinstance(approach_rows, list):
            return rows
        for row in approach_rows:
            if not isinstance(row, dict):
                continue
            try:
                rows[(int(row.get("runway_index")), str(row.get("end", "primary")))] = row
            except (TypeError, ValueError):
                continue
        return rows

    def _agl_option_enabled(self, rows: Dict[tuple, object], option_name: str) -> bool:
        return bool(rows.get(("__options__", option_name)))

    def _agl_end_designators(self, runway_name: str) -> tuple[str, str]:
        if "/" in runway_name:
            primary, reciprocal = runway_name.split("/", 1)
            return primary, reciprocal
        return runway_name, "Reciprocal"

    def _agl_interval_count(self, length_m: float, spacing_m: float) -> int:
        if length_m <= 0 or spacing_m <= 0:
            return 0
        return max(1, int(math.ceil(length_m / spacing_m)))

    def _agl_lateral_offsets(self, usable_half_width: float, spacing_m: float) -> List[float]:
        steps = max(1, int(math.floor((usable_half_width * 2.0) / spacing_m)))
        if steps == 1:
            return [-usable_half_width, usable_half_width]
        return [-usable_half_width + (idx * (2.0 * usable_half_width / steps)) for idx in range(steps + 1)]

    def _agl_lateral_offsets_by_count(self, usable_half_width: float, light_count: int) -> List[float]:
        light_count = max(2, int(light_count))
        if light_count == 2:
            return [-usable_half_width, usable_half_width]
        spacing_m = (usable_half_width * 2.0) / (light_count - 1)
        return [-usable_half_width + (idx * spacing_m) for idx in range(light_count)]

    def _runway_edge_light_colour_for_direction(
        self,
        offset_m: float,
        runway_length_m: float,
        displaced_threshold_m: float,
        landing_from_primary: bool,
    ) -> str:
        distance_from_threshold_m = offset_m if landing_from_primary else max(0.0, runway_length_m - offset_m)
        distance_to_runway_end_m = max(0.0, runway_length_m - offset_m) if landing_from_primary else offset_m
        if displaced_threshold_m > 0 and distance_from_threshold_m < displaced_threshold_m:
            return LIGHT_COLOUR_RED
        if distance_to_runway_end_m <= 600.0:
            return LIGHT_COLOUR_YELLOW
        return LIGHT_COLOUR_VARIABLE_WHITE

    def _runway_edge_display_colour(self, colour: str, other_direction_colour: str) -> str:
        if colour == LIGHT_COLOUR_VARIABLE_WHITE and other_direction_colour != LIGHT_COLOUR_VARIABLE_WHITE:
            return LIGHT_COLOUR_WHITE
        return colour
