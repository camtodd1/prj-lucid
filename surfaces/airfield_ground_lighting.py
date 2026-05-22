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
    MOS_REF_RUNWAY_EDGE,
    MOS_REF_THRESHOLD_LOCATION,
    MOS_REF_THRESHOLD_NON_PRECISION,
    MOS_REF_THRESHOLD_PRECISION,
    RUNWAY_LIGHTING_MIN_WIDTH_M,
    approach_profile_for_end,
    runway_edge_spacing_for_end,
    runway_is_precision,
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
        default_approach_spacing_m = float(agl_options.get("approach_spacing_m") or 30.0)
        approach_rows = self._agl_rows_by_runway_end(agl_options.get("approach_lighting", []))

        overall_success = False
        for runway_data in processed_runway_data_list:
            try:
                runway_success = self._create_agl_layer_for_runway(
                    runway_data,
                    layer_group,
                    threshold_inset_m,
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
        edge_spacing_m = min(
            runway_edge_spacing_for_end(primary_type),
            runway_edge_spacing_for_end(reciprocal_type),
        )
        precision_runway = runway_is_precision(primary_type) or runway_is_precision(reciprocal_type)
        edge_start_offset_m = edge_spacing_m if precision_runway else 0.0
        edge_end_offset_m = edge_spacing_m if precision_runway else 0.0

        self._append_runway_edge_lights(
            features,
            fields,
            runway_name,
            thr_point,
            params,
            lit_half_width,
            edge_spacing_m,
            edge_start_offset_m,
            edge_end_offset_m,
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
            lit_half_width,
            threshold_inset_m,
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
                        MOS_REF_RUNWAY_EDGE,
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
                        MOS_REF_RUNWAY_EDGE,
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
                        ref_mos,
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
                            ref_mos,
                        )
                    )

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
        ref_mos: str,
    ) -> QgsFeature:
        feature = QgsFeature(fields)
        feature.setGeometry(QgsGeometry.fromPointXY(point))
        feature.setAttributes(
            [
                runway_name,
                end_desig,
                light_type,
                side,
                round(float(spacing_m), 3),
                round(float(offset_m), 3),
                ref_mos,
                "MOS-derived",
            ]
        )
        return feature

    def _agl_fields(self) -> QgsFields:
        return QgsFields(
            [
                QgsField("rwy", QVariant.String, self.tr("Runway Name"), 30),
                QgsField("end_desig", QVariant.String, self.tr("End Designator"), 10),
                QgsField("light_type", QVariant.String, self.tr("Light Type"), 30),
                QgsField("side", QVariant.String, self.tr("Side"), 12),
                QgsField("spacing_m", QVariant.Double, self.tr("Spacing (m)"), 12, 3),
                QgsField("offset_m", QVariant.Double, self.tr("Offset (m)"), 12, 3),
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
