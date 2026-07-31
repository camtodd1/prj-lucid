# -*- coding: utf-8 -*-
"""UK safeguarding zone generators."""

from qgis.PyQt.QtCore import QVariant  # type: ignore
from qgis.core import (  # type: ignore
    QgsCoordinateReferenceSystem,
    QgsFeature,
    QgsField,
    QgsFields,
    QgsGeometry,
    QgsLayerTreeGroup,
    QgsPointXY,
)


class UkSafeguardingMixin:
    def process_uk_crane_notification_zone(
        self,
        arp_point: QgsPointXY,
        icao_code: str,
        target_crs: QgsCoordinateReferenceSystem,
        layer_group: QgsLayerTreeGroup,
    ) -> bool:
        """Generate the fixed 6 km ARP-centred crane notification zone."""
        del target_crs
        params = self.get_active_framework().crane_notification_zone_parameters()
        geometry = QgsGeometry.fromPointXY(arp_point).buffer(
            float(params["radius_m"]), int(params["buffer_segments"])
        )
        if geometry is None or geometry.isEmpty():
            return False
        fields = QgsFields(
            [
                QgsField("zone", QVariant.String),
                QgsField("radius_km", QVariant.Double),
                QgsField("family_id", QVariant.String),
                QgsField("profile_id", QVariant.String),
                QgsField("source_id", QVariant.String),
                QgsField("source_ref", QVariant.String),
                QgsField("geometry_status", QVariant.String),
                QgsField("assessment_result", QVariant.String),
                QgsField("caveat", QVariant.String, "", 500),
            ]
        )
        feature = QgsFeature(fields)
        feature.setGeometry(geometry)
        feature.setAttributes(
            [
                "Crane notification zone",
                float(params["radius_m"]) / 1000.0,
                params["family_id"],
                params["profile_id"],
                params["source_id"],
                params["source_ref"],
                params["geometry_status"],
                params["assessment_result"],
                params["caveat"],
            ]
        )
        return self._create_and_add_layer(
            "Polygon",
            f"UK_CraneNotificationZone_{icao_code}",
            f"{icao_code} Crane Notification Zone (6km)",
            fields,
            [feature],
            layer_group,
            "Default Polygon",
        ) is not None


__all__ = ["UkSafeguardingMixin"]
