# -*- coding: utf-8 -*-
"""Generated UK candidate-screening layers."""

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
    """Generate source-labelled outputs for UK-only safeguarding mechanisms."""

    def process_uk_crane_screening(
        self,
        arp_point: QgsPointXY,
        icao_code: str,
        target_crs: QgsCoordinateReferenceSystem,
        layer_group: QgsLayerTreeGroup,
    ) -> bool:
        del target_crs
        options = getattr(self, "safeguarding_options", {}) or {}
        crane = options.get("crane", {})
        if not isinstance(crane, dict) or not crane.get("enabled"):
            return False
        candidate = QgsPointXY(float(crane["easting"]), float(crane["northing"]))
        distance_m = QgsGeometry.fromPointXY(candidate).distance(QgsGeometry.fromPointXY(arp_point))
        result = self.get_active_framework().screen_crane_notification(
            distance_m,
            float(crane["height_agl_m"]),
            bool(crane.get("shielded_by_surroundings", False)),
            float(crane.get("surrounding_height_agl_m", 0.0)),
            int(crane.get("in_situ_days", 0)),
        )
        fields = QgsFields(
            [
                QgsField("candidate", QVariant.String),
                QgsField("distance_m", QVariant.Double),
                QgsField("height_agl", QVariant.Double),
                QgsField("surround_h", QVariant.Double),
                QgsField("duration_d", QVariant.Int),
                QgsField("notify", QVariant.Bool),
                QgsField("local_6km", QVariant.Bool),
                QgsField("national", QVariant.Bool),
                QgsField("notify_dgc", QVariant.Bool),
                QgsField("lighting", QVariant.String),
                QgsField("light_cd", QVariant.Double),
                QgsField("reasons", QVariant.String, "", 250),
                QgsField("profile_id", QVariant.String),
                QgsField("source_id", QVariant.String),
                QgsField("source_ref", QVariant.String),
                QgsField("geometry_status", QVariant.String),
                QgsField("assessment_result", QVariant.String),
                QgsField("distance_basis", QVariant.String),
                QgsField("caveat", QVariant.String, "", 500),
            ]
        )
        feature = QgsFeature(fields)
        feature.setGeometry(QgsGeometry.fromPointXY(candidate))
        feature.setAttributes(
            [
                str(crane.get("name") or "Crane candidate"),
                distance_m,
                float(crane["height_agl_m"]),
                float(crane.get("surrounding_height_agl_m", 0.0)),
                int(crane.get("in_situ_days", 0)),
                result["notification_required"],
                result["local_trigger"],
                result["national_trigger"],
                result["dgc_notification"],
                result["lighting_status"],
                result["lighting_intensity_cd"],
                ";".join(result["reason_codes"]),
                result["profile_id"],
                result["source_id"],
                result["source_ref"],
                result["geometry_status"],
                result["assessment_result"],
                "ARP proxy",
                result["caveat"],
            ]
        )
        candidate_layer = self._create_and_add_layer(
            "Point",
            f"UK_CraneScreening_{icao_code}",
            f"{icao_code} Crane Notification Candidate",
            fields,
            [feature],
            layer_group,
            "Default Point",
        )

        area_fields = QgsFields(
            [
                QgsField("radius_m", QVariant.Double),
                QgsField("distance_basis", QVariant.String),
                QgsField("source_id", QVariant.String),
                QgsField("geometry_status", QVariant.String),
            ]
        )
        area_feature = QgsFeature(area_fields)
        area_feature.setGeometry(QgsGeometry.fromPointXY(arp_point).buffer(6000.0, 144))
        area_feature.setAttributes([6000.0, "ARP proxy", result["source_id"], "screening_proxy"])
        area_layer = self._create_and_add_layer(
            "Polygon",
            f"UK_CraneLocalArea_{icao_code}",
            f"{icao_code} Crane Local Notification Area (6km ARP proxy)",
            area_fields,
            [area_feature],
            layer_group,
            "Default Polygon",
        )
        return candidate_layer is not None and area_layer is not None


__all__ = ["UkSafeguardingMixin"]
