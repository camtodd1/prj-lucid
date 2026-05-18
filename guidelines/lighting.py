# -*- coding: utf-8 -*-
"""Guideline E lighting control zone generation."""

import traceback
from typing import Dict, Optional

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

from .constants import (
    GUIDELINE_C_BUFFER_SEGMENTS,
    GUIDELINE_E_ZONE_ORDER,
    GUIDELINE_E_ZONE_PARAMS,
    MOS_REF_GUIDELINE_E,
    NASF_REF_GUIDELINE_E,
)

PLUGIN_TAG = "SafeguardingBuilder"


class LightingGuidelineMixin:
    def process_guideline_e(
        self, runway_data: dict, layer_group: QgsLayerTreeGroup
    ) -> bool:
        """Processes Guideline E: Lighting Control Zone and LCZ Area circle."""
        runway_name = runway_data.get(
            "short_name", f"RWY_{runway_data.get('original_index','?')}"
        )
        thr_point = runway_data.get("thr_point")
        rec_thr_point = runway_data.get("rec_thr_point")

        if thr_point is None or rec_thr_point is None or layer_group is None:
            QgsMessageLog.logMessage(
                f"Guideline E skipped for {runway_name}: Missing threshold points or layer group.",
                PLUGIN_TAG,
                level=Qgis.Warning,
            )
            return False
        if thr_point.compare(rec_thr_point, 1e-6):
            QgsMessageLog.logMessage(
                f"Guideline E skipped for {runway_name}: Threshold points are identical.",
                PLUGIN_TAG,
                level=Qgis.Warning,
            )
            return False

        full_geoms: Dict[str, Optional[QgsGeometry]] = {}
        final_geoms: Dict[str, Optional[QgsGeometry]] = {}
        overall_success = False

        try:
            def create_lcz_layer(
                zone_letter: str, geom: Optional[QgsGeometry]
            ) -> bool:
                if not geom:
                    return False
                params = GUIDELINE_E_ZONE_PARAMS[zone_letter]
                display_name = f"{self.tr('LCZ')} {zone_letter} {runway_name}"
                internal_name = f"LCZ_{zone_letter}_{runway_name.replace('/', '_')}"
                fields = QgsFields(
                    [
                        QgsField("rwy", QVariant.String),
                        QgsField("zone", QVariant.String),
                        QgsField("desc", QVariant.String),
                        QgsField("inner_extent_m", QVariant.Double),
                        QgsField("outer_extent_m", QVariant.Double),
                        QgsField("wid_m", QVariant.Double),
                        QgsField("max_intensity", QVariant.String),
                        QgsField("ref_mos", QVariant.String),
                        QgsField("ref_nasf", QVariant.String),
                    ]
                )

                inner_extent_val = 0.0
                zone_index = GUIDELINE_E_ZONE_ORDER.index(zone_letter)
                if zone_index > 0:
                    previous_zone_id = GUIDELINE_E_ZONE_ORDER[zone_index - 1]
                    inner_extent_val = GUIDELINE_E_ZONE_PARAMS[previous_zone_id]["ext"]

                feature = QgsFeature(fields)
                feature.setGeometry(geom)
                feature.setAttributes(
                    [
                        runway_name,
                        zone_letter,
                        params["desc"],
                        inner_extent_val,
                        params["ext"],
                        params["half_w"] * 2,
                        params["max_intensity"],
                        MOS_REF_GUIDELINE_E,
                        NASF_REF_GUIDELINE_E,
                    ]
                )
                layer = self._create_and_add_layer(
                    "Polygon",
                    internal_name,
                    display_name,
                    fields,
                    [feature],
                    layer_group,
                    f"LCZ {zone_letter}",
                )
                return layer is not None

            for zone_id_geom_gen in GUIDELINE_E_ZONE_ORDER:
                params_geom = GUIDELINE_E_ZONE_PARAMS[zone_id_geom_gen]
                geom_full = self._create_runway_aligned_rectangle(
                    thr_point,
                    rec_thr_point,
                    params_geom["ext"],
                    params_geom["half_w"],
                    f"LCZ Full {zone_id_geom_gen} {runway_name}",
                )
                full_geoms[zone_id_geom_gen] = (
                    geom_full.makeValid()
                    if geom_full and not geom_full.isGeosValid()
                    else geom_full
                )

            final_geoms["A"] = full_geoms.get("A")

            for i, zone_id_diff in enumerate(GUIDELINE_E_ZONE_ORDER[1:]):
                geom_curr_for_diff = full_geoms.get(zone_id_diff)
                prev_zone_id_for_diff = GUIDELINE_E_ZONE_ORDER[i]
                geom_prev_valid_for_diff = full_geoms.get(prev_zone_id_for_diff)

                if geom_curr_for_diff and geom_prev_valid_for_diff:
                    diff_geom = geom_curr_for_diff.difference(geom_prev_valid_for_diff)
                    final_geoms[zone_id_diff] = (
                        diff_geom.makeValid()
                        if diff_geom and not diff_geom.isGeosValid()
                        else diff_geom
                    )
                elif geom_curr_for_diff:
                    final_geoms[zone_id_diff] = geom_curr_for_diff
                else:
                    final_geoms[zone_id_diff] = None

            for zone_id_create in GUIDELINE_E_ZONE_ORDER:
                if final_geoms.get(zone_id_create):
                    if create_lcz_layer(zone_id_create, final_geoms[zone_id_create]):
                        overall_success = True
        except Exception as e:
            QgsMessageLog.logMessage(
                f"Error processing standard LCZ zones for {runway_name}: {e}\n{traceback.format_exc()}",
                PLUGIN_TAG,
                level=Qgis.Critical,
            )

        try:
            midpoint = self._get_runway_midpoint(thr_point, rec_thr_point)
            if midpoint:
                midpoint_geom = QgsGeometry.fromPointXY(midpoint)
                if not midpoint_geom.isNull():
                    radius_m = 6000.0
                    lcz_area_circle_geom = midpoint_geom.buffer(
                        radius_m, GUIDELINE_C_BUFFER_SEGMENTS
                    )

                    if lcz_area_circle_geom and not lcz_area_circle_geom.isEmpty():
                        valid_lcz_area_geom = lcz_area_circle_geom.makeValid()
                        if valid_lcz_area_geom and valid_lcz_area_geom.isGeosValid():
                            lcz_area_fields = QgsFields(
                                [
                                    QgsField(
                                        "rwy",
                                        QVariant.String,
                                        self.tr("Runway Name"),
                                        30,
                                    ),
                                    QgsField(
                                        "desc",
                                        QVariant.String,
                                        self.tr("Description"),
                                        50,
                                    ),
                                    QgsField(
                                        "radius_m",
                                        QVariant.Double,
                                        self.tr("Radius (m)"),
                                        10,
                                        1,
                                    ),
                                    QgsField(
                                        "ref_mos",
                                        QVariant.String,
                                        self.tr("MOS Reference"),
                                        50,
                                    ),
                                    QgsField(
                                        "ref_nasf",
                                        QVariant.String,
                                        self.tr("NASF Guideline Reference"),
                                        50,
                                    ),
                                ]
                            )

                            feature = QgsFeature(lcz_area_fields)
                            feature.setGeometry(valid_lcz_area_geom)
                            feature.setAttributes(
                                [
                                    runway_name,
                                    "Lighting Control Area (6km Radius)",
                                    radius_m,
                                    "MOS 9.144(2)",
                                    NASF_REF_GUIDELINE_E,
                                ]
                            )

                            display_name = f"{self.tr('LCZ Area')} {runway_name}"
                            internal_name = f"LCZ_Area_{runway_name.replace('/', '_')}"
                            style_key_lcz_area = "LCZ Area"
                            if style_key_lcz_area not in self.style_map:
                                self.style_map[style_key_lcz_area] = (
                                    "default_zone_polygon.qml"
                                )

                            layer = self._create_and_add_layer(
                                "Polygon",
                                internal_name,
                                display_name,
                                lcz_area_fields,
                                [feature],
                                layer_group,
                                style_key_lcz_area,
                            )
                            if layer is not None:
                                overall_success = True
                        else:
                            QgsMessageLog.logMessage(
                                f"Failed to create valid LCZ Area circle geometry for {runway_name} after makeValid.",
                                PLUGIN_TAG,
                                level=Qgis.Warning,
                            )
                    else:
                        QgsMessageLog.logMessage(
                            f"Failed to buffer LCZ Area circle for {runway_name}.",
                            PLUGIN_TAG,
                            level=Qgis.Warning,
                        )
                else:
                    QgsMessageLog.logMessage(
                        f"Failed to create geometry from midpoint for LCZ Area {runway_name}.",
                        PLUGIN_TAG,
                        level=Qgis.Warning,
                    )
            else:
                QgsMessageLog.logMessage(
                    f"Failed to calculate midpoint for LCZ Area {runway_name}.",
                    PLUGIN_TAG,
                    level=Qgis.Warning,
                )
        except Exception as e_lcz_area:
            QgsMessageLog.logMessage(
                f"Error processing LCZ Area (6km circle) for {runway_name}: {e_lcz_area}\n{traceback.format_exc()}",
                PLUGIN_TAG,
                level=Qgis.Critical,
            )

        return overall_success
