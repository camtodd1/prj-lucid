# -*- coding: utf-8 -*-
"""NASF airport-centred guideline processors."""

import math
import traceback
from typing import List, Optional

from qgis.PyQt.QtCore import QVariant  # type: ignore
from qgis.core import (  # type: ignore
    Qgis,
    QgsCoordinateReferenceSystem,
    QgsFeature,
    QgsField,
    QgsFields,
    QgsGeometry,
    QgsLayerTreeGroup,
    QgsMessageLog,
    QgsPointXY,
)

from .processor_base import NasfGuidelineProcessorBase

PLUGIN_TAG = "SafeguardingBuilder"


class NasfAirportGuidelinesMixin(NasfGuidelineProcessorBase):
    def process_guideline_c(
        self,
        arp_point: QgsPointXY,
        icao_code: str,
        target_crs: QgsCoordinateReferenceSystem,
        layer_group: QgsLayerTreeGroup,
    ) -> bool:
        """Processes Guideline C: Wildlife Management Zone."""
        if arp_point is None or not icao_code or target_crs is None or not target_crs.isValid() or layer_group is None:
            return False
        overall_success = False
        framework = self._active_safeguarding_framework()
        wildlife = framework.wildlife_parameters()
        radius_a_m = wildlife["radius_a_m"]
        radius_b_m = wildlife["radius_b_m"]
        radius_c_m = wildlife["radius_c_m"]
        buffer_segments = wildlife["buffer_segments"]
        try:
            arp_geom = QgsGeometry.fromPointXY(arp_point)
            if arp_geom.isNull():
                QgsMessageLog.logMessage(
                    "Guideline C Wildlife failed: ARP geometry is null.",
                    PLUGIN_TAG,
                    level=Qgis.Warning,
                )
                return False
            created_zones: List[str] = []
            failed_zones: List[str] = []

            def create_wzm_layer(
                zone: str,
                geom: Optional[QgsGeometry],
                desc: str,
                r_in: float,
                r_out: float,
            ) -> bool:
                if not geom or geom.isEmpty():
                    QgsMessageLog.logMessage(
                        f"Guideline C Wildlife zone {zone} failed: geometry is empty.",
                        PLUGIN_TAG,
                        level=Qgis.Warning,
                    )
                    failed_zones.append(zone)
                    return False
                display_name = f"{self.tr('WMZ')} {zone} ({r_in:.0f}-{r_out:.0f}km)"
                internal_name = f"WMZ_{zone}_{icao_code}"
                fields = QgsFields(
                    [
                        QgsField("zone", QVariant.String),
                        QgsField("desc", QVariant.String),
                        QgsField("inner_rad_km", QVariant.Double),
                        QgsField("outer_rad_km", QVariant.Double),
                        QgsField("ref_mos", QVariant.String),
                        QgsField("ref_nasf", QVariant.String),
                    ]
                )
                feature = QgsFeature(fields)
                feature.setGeometry(geom)
                feature.setAttributes(
                    [
                        f"Area {zone}",
                        desc,
                        r_in,
                        r_out,
                        wildlife["ref_mos"],
                        wildlife["ref_nasf"],
                    ]
                )
                layer = self._create_and_add_layer(
                    "Polygon",
                    internal_name,
                    display_name,
                    fields,
                    [feature],
                    layer_group,
                    f"WMZ {zone}",
                )
                if layer is None:
                    QgsMessageLog.logMessage(
                        f"Guideline C Wildlife zone {zone} failed: layer was not created.",
                        PLUGIN_TAG,
                        level=Qgis.Warning,
                    )
                    failed_zones.append(zone)
                    return False
                created_zones.append(zone)
                return True

            def circular_ring_points(radius_m: float, clockwise: bool = False) -> List[QgsPointXY]:
                segment_count = max(8, buffer_segments)
                angle_step = 2.0 * math.pi / segment_count
                points = []
                for i in range(segment_count):
                    angle = i * angle_step
                    if clockwise:
                        angle = -angle
                    points.append(
                        QgsPointXY(
                            arp_point.x() + radius_m * math.cos(angle),
                            arp_point.y() + radius_m * math.sin(angle),
                        )
                    )
                points.append(QgsPointXY(points[0].x(), points[0].y()))
                return points

            def create_wzm_geometry(
                outer_radius_m: float, inner_radius_m: Optional[float] = None
            ) -> Optional[QgsGeometry]:
                rings = [circular_ring_points(outer_radius_m)]
                if inner_radius_m is not None and inner_radius_m > 0:
                    rings.append(circular_ring_points(inner_radius_m, clockwise=True))
                geom = QgsGeometry.fromPolygonXY(rings)
                if geom is None or geom.isEmpty():
                    return None
                return geom.makeValid() if not geom.isGeosValid() else geom

            geom_a = create_wzm_geometry(radius_a_m)
            geom_b = create_wzm_geometry(radius_b_m, radius_a_m)
            geom_c = create_wzm_geometry(radius_c_m, radius_b_m)

            if create_wzm_layer(
                "A",
                geom_a,
                self.tr("Wildlife Management Zone A (0-3km)"),
                0.0,
                radius_a_m / 1000.0,
            ):
                overall_success = True
            if create_wzm_layer(
                "B",
                geom_b,
                self.tr("Wildlife Management Zone B (3-8km)"),
                radius_a_m / 1000.0,
                radius_b_m / 1000.0,
            ):
                overall_success = True
            if create_wzm_layer(
                "C",
                geom_c,
                self.tr("Wildlife Management Zone C (8-13km)"),
                radius_b_m / 1000.0,
                radius_c_m / 1000.0,
            ):
                overall_success = True
            if created_zones:
                QgsMessageLog.logMessage(
                    "Guideline C Wildlife: created zone layer(s) "
                    f"{', '.join(created_zones)} from ARP "
                    f"({arp_point.x():.3f}, {arp_point.y():.3f}).",
                    PLUGIN_TAG,
                    level=Qgis.Success,
                )
            if failed_zones:
                QgsMessageLog.logMessage(
                    "Guideline C Wildlife partial failure: failed zone layer(s) " f"{', '.join(failed_zones)}.",
                    PLUGIN_TAG,
                    level=Qgis.Warning,
                )
            return overall_success
        except Exception as e:
            QgsMessageLog.logMessage(f"Guideline C Wildlife failed: {e}", PLUGIN_TAG, level=Qgis.Critical)
            return False

    def process_guideline_d(
        self,
        arp_point: QgsPointXY,
        icao_code: str,
        target_crs: QgsCoordinateReferenceSystem,
        layer_group: QgsLayerTreeGroup,
    ) -> bool:
        """Processes Guideline D: Wind Turbine Assessment Zone."""
        plugin_tag = PLUGIN_TAG
        if arp_point is None or not icao_code or layer_group is None:
            QgsMessageLog.logMessage(
                "Guideline D (Wind Turbine) skipped: Missing ARP point, ICAO code, or layer group.",
                plugin_tag,
                level=Qgis.Warning,
            )
            return False

        try:
            arp_geom = QgsGeometry.fromPointXY(arp_point)
            if arp_geom.isNull():
                QgsMessageLog.logMessage(
                    "Guideline D (Wind Turbine) skipped: ARP geometry is null.",
                    plugin_tag,
                    level=Qgis.Warning,
                )
                return False

            framework = self._active_safeguarding_framework()
            wind_turbine = framework.wind_turbine_parameters()
            turbine_radius_m = wind_turbine["radius_m"]
            turbine_zone_geom = arp_geom.buffer(turbine_radius_m, wind_turbine["buffer_segments"])
            if not turbine_zone_geom or turbine_zone_geom.isEmpty():
                QgsMessageLog.logMessage(
                    "Guideline D: Failed to create turbine zone buffer.",
                    plugin_tag,
                    level=Qgis.Warning,
                )
                return False

            valid_geom = turbine_zone_geom.makeValid()
            if not valid_geom or not valid_geom.isGeosValid() or valid_geom.isEmpty():
                QgsMessageLog.logMessage(
                    "Guideline D: Turbine zone geometry invalid after makeValid.",
                    plugin_tag,
                    level=Qgis.Warning,
                )
                return False

            fields = QgsFields(
                [
                    QgsField("icao_code", QVariant.String, self.tr("ICAO Code"), 10),
                    QgsField("description", QVariant.String, self.tr("Description"), 100),
                    QgsField("radius_km", QVariant.Double, self.tr("Radius (km)"), 8, 2),
                    QgsField("ref_nasf", QVariant.String, self.tr("Guideline Ref."), 50),
                ]
            )

            feature = QgsFeature(fields)
            feature.setGeometry(valid_geom)
            feature.setAttributes(
                [
                    icao_code,
                    self.tr("Wind Turbine Assessment Zone (30km Radius)"),
                    turbine_radius_m / 1000.0,
                    self.tr(wind_turbine["ref_nasf"]),
                ]
            )

            layer_display_name = f"{icao_code} {self.tr('Wind Turbine Assessment Zone')}"
            internal_name_base = f"Guideline_D_TurbineZone_{icao_code}"
            style_key = "Wind Turbine Assessment Zone"

            layer_created = self._create_and_add_layer(
                "Polygon",
                internal_name_base,
                layer_display_name,
                fields,
                [feature],
                layer_group,
                style_key,
            )
            return layer_created is not None
        except Exception as e:
            QgsMessageLog.logMessage(
                f"Error processing Guideline D (Wind Turbine): {e}\n{traceback.format_exc()}",
                plugin_tag,
                level=Qgis.Critical,
            )
            return False
