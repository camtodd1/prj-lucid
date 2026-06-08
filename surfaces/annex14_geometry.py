# -*- coding: utf-8 -*-
"""Annex 14 OFS/OES plan-view geometry generation."""

import math
import traceback
from typing import Dict, Iterable, List, Optional

from qgis.PyQt.QtCore import QVariant  # type: ignore
from qgis.core import (  # type: ignore
    Qgis,
    QgsFeature,
    QgsField,
    QgsFields,
    QgsGeometry,
    QgsLineString,
    QgsLayerTreeGroup,
    QgsMessageLog,
    QgsPoint,
    QgsPointXY,
    QgsPolygon,
    QgsWkbTypes,
)

PLUGIN_TAG = "SafeguardingBuilder"


class Annex14GeometryMixin:
    def _annex14_surface_fields(self) -> QgsFields:
        return QgsFields(
            [
                QgsField("rwy_name", QVariant.String, self.tr("Runway"), 50),
                QgsField("family", QVariant.String, self.tr("Family"), 50),
                QgsField("surface", QVariant.String, self.tr("Surface"), 80),
                QgsField("component", QVariant.String, self.tr("Component"), 80),
                QgsField("end_desig", QVariant.String, self.tr("End"), 10),
                QgsField("adg", QVariant.String, self.tr("ADG"), 20),
                QgsField("len_m", QVariant.Double, self.tr("Length"), 12, 2),
                QgsField("innerw_m", QVariant.Double, self.tr("Inner Width"), 12, 2),
                QgsField("outerw_m", QVariant.Double, self.tr("Outer Width"), 12, 2),
                QgsField("slope_pct", QVariant.Double, self.tr("Slope %"), 8, 3),
                QgsField("diverg_pct", QVariant.Double, self.tr("Divergence %"), 8, 3),
                QgsField("ref", QVariant.String, self.tr("Reference"), 120),
                QgsField("notes", QVariant.String, self.tr("Notes"), 254),
            ]
        )

    def _annex14_contour_fields(self) -> QgsFields:
        return QgsFields(
            [
                QgsField("rwy_name", QVariant.String, self.tr("Runway"), 50),
                QgsField("family", QVariant.String, self.tr("Family"), 50),
                QgsField("surface", QVariant.String, self.tr("Surface"), 80),
                QgsField("component", QVariant.String, self.tr("Component"), 80),
                QgsField("end_desig", QVariant.String, self.tr("End"), 10),
                QgsField("adg", QVariant.String, self.tr("ADG"), 20),
                QgsField("contour_elev_am", QVariant.Double, self.tr("Contour Elev (AMSL)"), 12, 2),
                QgsField("ref", QVariant.String, self.tr("Reference"), 120),
            ]
        )

    def _annex14_float_or_none(self, value) -> Optional[float]:
        try:
            if value in (None, ""):
                return None
            return float(value)
        except (TypeError, ValueError):
            return None

    def _annex14_runway_end_elevations(self, runway_data: dict) -> tuple:
        primary = (
            self._annex14_float_or_none(runway_data.get("threshold_elev_1"))
            or self._annex14_float_or_none(runway_data.get("thr_elev_1"))
            or self._annex14_float_or_none(runway_data.get("runway_end_elev_1"))
        )
        reciprocal = (
            self._annex14_float_or_none(runway_data.get("threshold_elev_2"))
            or self._annex14_float_or_none(runway_data.get("thr_elev_2"))
            or self._annex14_float_or_none(runway_data.get("runway_end_elev_2"))
        )
        if primary is None and reciprocal is not None:
            primary = reciprocal
        if reciprocal is None and primary is not None:
            reciprocal = primary
        return primary, reciprocal

    def _annex14_polygon_z_from_corners(
        self,
        corners: List[tuple],
        description: str,
    ) -> Optional[QgsGeometry]:
        if not corners or len(corners) < 3:
            return None
        try:
            points = [QgsPoint(point.x(), point.y(), float(z)) for point, z in corners]
            if abs(points[0].x() - points[-1].x()) > 1e-6 or abs(points[0].y() - points[-1].y()) > 1e-6:
                points.append(QgsPoint(points[0].x(), points[0].y(), points[0].z()))
            ring = QgsLineString(points)
            polygon = QgsPolygon(ring)
            geom = QgsGeometry(polygon)
            if geom.isNull() or geom.isEmpty():
                return None
            if not geom.isGeosValid():
                fixed = geom.makeValid()
                if fixed is not None and not fixed.isNull() and not fixed.isEmpty():
                    geom = fixed
            return geom
        except Exception as exc:
            QgsMessageLog.logMessage(
                f"Annex 14 3D polygon failed for {description}: {exc}",
                PLUGIN_TAG,
                Qgis.Warning,
            )
            return None

    def _annex14_flat_z_polygon(self, geom: Optional[QgsGeometry], z: Optional[float]) -> Optional[QgsGeometry]:
        if geom is None or geom.isNull() or geom.isEmpty() or z is None:
            return geom
        try:
            polygon = geom.asPolygon()
            if not polygon or not polygon[0]:
                return geom
            return self._annex14_polygon_z_from_corners(
                [(point, z) for point in polygon[0]],
                "Annex 14 flat Z polygon",
            ) or geom
        except Exception:
            return geom

    def _annex14_surface_z(self, base_z: Optional[float], distance_m: float, slope: Optional[float]) -> Optional[float]:
        if base_z is None:
            return None
        return float(base_z) + (float(distance_m or 0.0) * float(slope or 0.0))

    def _annex14_runway_axis_z(
        self,
        start_z: Optional[float],
        end_z: Optional[float],
        distance_from_start_m: float,
        runway_length_m: float,
    ) -> Optional[float]:
        if start_z is None:
            return None
        if end_z is None or runway_length_m <= 0:
            return start_z
        fraction = max(0.0, min(1.0, float(distance_from_start_m or 0.0) / float(runway_length_m)))
        return float(start_z) + ((float(end_z) - float(start_z)) * fraction)

    def _annex14_contour_interval(self, surface_key: str = "default") -> float:
        if hasattr(self, "_get_contour_interval"):
            return self._get_contour_interval(surface_key, 10.0)
        return 10.0

    def _annex14_contour_elevations(
        self,
        start_z: Optional[float],
        end_z: Optional[float],
        interval: float,
    ) -> List[float]:
        if start_z is None or end_z is None or interval <= 0 or abs(float(end_z) - float(start_z)) < 1e-6:
            return []
        z_min = min(float(start_z), float(end_z))
        z_max = max(float(start_z), float(end_z))
        elevations = {round(z_min, 6), round(z_max, 6)}
        current = math.ceil(z_min / interval) * interval
        if current < z_min + 1e-6:
            current += interval
        while current < z_max - 1e-6:
            elevations.add(round(current, 6))
            current += interval
        return sorted(elevations)

    def _annex14_add_contour_feature(
        self,
        contour_features: List[QgsFeature],
        contour_fields: QgsFields,
        start_point: QgsPointXY,
        end_point: QgsPointXY,
        runway_name: str,
        family: str,
        surface: str,
        component: str,
        end_desig: str,
        design_group: str,
        contour_elev_am: float,
        ref: str,
    ) -> None:
        geom = QgsGeometry.fromPolylineXY([start_point, end_point])
        if geom is None or geom.isNull() or geom.isEmpty():
            return
        feature = QgsFeature(contour_fields)
        feature.setGeometry(geom)
        feature.setAttributes(
            [
                runway_name,
                family,
                surface,
                component,
                end_desig,
                design_group,
                contour_elev_am,
                ref,
            ]
        )
        contour_features.append(feature)

    def _annex14_add_trapezoid_contours(
        self,
        contour_features: List[QgsFeature],
        contour_fields: QgsFields,
        start_point: QgsPointXY,
        azimuth: float,
        length_m: float,
        inner_width_m: float,
        outer_width_m: float,
        start_z: Optional[float],
        end_z: Optional[float],
        runway_name: str,
        family: str,
        surface: str,
        component: str,
        end_desig: str,
        design_group: str,
        ref: str,
        interval: float,
    ) -> None:
        if start_z is None or end_z is None or length_m <= 0:
            return
        az_perp_left = (azimuth - 90.0 + 360.0) % 360.0
        az_perp_right = (azimuth + 90.0) % 360.0
        for contour_z in self._annex14_contour_elevations(start_z, end_z, interval):
            t = (float(contour_z) - float(start_z)) / (float(end_z) - float(start_z))
            if t < -1e-6 or t > 1 + 1e-6:
                continue
            t = max(0.0, min(1.0, t))
            centre = start_point.project(length_m * t, azimuth)
            if centre is None:
                continue
            width = inner_width_m + ((outer_width_m - inner_width_m) * t)
            left = centre.project(width / 2.0, az_perp_left)
            right = centre.project(width / 2.0, az_perp_right)
            if left is None or right is None:
                continue
            self._annex14_add_contour_feature(
                contour_features,
                contour_fields,
                left,
                right,
                runway_name,
                family,
                surface,
                component,
                end_desig,
                design_group,
                contour_z,
                ref,
            )

    def _annex14_design_group_for_runway(self, runway_data: dict) -> Optional[str]:
        for key in ("adg", "design_group", "aeroplane_design_group", "airplane_design_group"):
            value = runway_data.get(key)
            if value:
                return str(value)

        wingspan = runway_data.get("wingspan_m") or runway_data.get("critical_wingspan_m")
        vat_kmh = runway_data.get("vat_kmh") or runway_data.get("indicated_airspeed_at_threshold_kmh")
        vat_kt = runway_data.get("vat_kt") or runway_data.get("indicated_airspeed_at_threshold_kt")
        if wingspan is not None or vat_kmh is not None or vat_kt is not None:
            try:
                result = self.get_active_ruleset().design_group(
                    wingspan_m=float(wingspan) if wingspan is not None else None,
                    indicated_airspeed_at_threshold_kmh=float(vat_kmh) if vat_kmh is not None else None,
                    indicated_airspeed_at_threshold_kt=float(vat_kt) if vat_kt is not None else None,
                )
                if result:
                    return result.get("design_group")
            except Exception:
                return None
        return None

    def _annex14_runway_end_configs(self, runway_data: dict, rwy_params: dict) -> List[dict]:
        runway_name = runway_data.get("short_name", f"RWY_{runway_data.get('original_index', '?')}")
        primary_desig, reciprocal_desig = runway_name.split("/") if "/" in runway_name else ("THR1", "THR2")
        primary_elev, reciprocal_elev = self._annex14_runway_end_elevations(runway_data)
        return [
            {
                "end_desig": primary_desig,
                "threshold": runway_data.get("thr_point"),
                "opposite_threshold": runway_data.get("rec_thr_point"),
                "threshold_elev": primary_elev,
                "opposite_threshold_elev": reciprocal_elev,
                "highest_threshold_elev": max(e for e in [primary_elev, reciprocal_elev] if e is not None)
                if primary_elev is not None or reciprocal_elev is not None
                else None,
                "approach_azimuth": rwy_params["azimuth_r_p"],
                "takeoff_azimuth": rwy_params["azimuth_p_r"],
                "takeoff_start": runway_data.get("rec_thr_point"),
                "takeoff_start_elev": reciprocal_elev,
                "runway_type": runway_data.get("type1", ""),
                "takeoff_mass_kg": runway_data.get("takeoff_mass_1_kg") or runway_data.get("max_takeoff_mass_kg"),
            },
            {
                "end_desig": reciprocal_desig,
                "threshold": runway_data.get("rec_thr_point"),
                "opposite_threshold": runway_data.get("thr_point"),
                "threshold_elev": reciprocal_elev,
                "opposite_threshold_elev": primary_elev,
                "highest_threshold_elev": max(e for e in [primary_elev, reciprocal_elev] if e is not None)
                if primary_elev is not None or reciprocal_elev is not None
                else None,
                "approach_azimuth": rwy_params["azimuth_p_r"],
                "takeoff_azimuth": rwy_params["azimuth_r_p"],
                "takeoff_start": runway_data.get("thr_point"),
                "takeoff_start_elev": primary_elev,
                "runway_type": runway_data.get("type2", ""),
                "takeoff_mass_kg": runway_data.get("takeoff_mass_2_kg") or runway_data.get("max_takeoff_mass_kg"),
            },
        ]

    def _annex14_add_polygon_feature(
        self,
        features: List[QgsFeature],
        fields: QgsFields,
        geom: Optional[QgsGeometry],
        runway_name: str,
        family: str,
        surface: str,
        component: str,
        end_desig: str,
        design_group: str,
        length_m: Optional[float],
        inner_width_m: Optional[float],
        outer_width_m: Optional[float],
        slope: Optional[float],
        divergence: Optional[float],
        ref: str,
        notes: str = "",
    ) -> None:
        if geom is None or geom.isNull() or geom.isEmpty():
            return
        feature = QgsFeature(fields)
        feature.setGeometry(geom)
        feature.setAttributes(
            [
                runway_name,
                family,
                surface,
                component,
                end_desig,
                design_group,
                length_m,
                inner_width_m,
                outer_width_m,
                slope * 100.0 if slope is not None else None,
                divergence * 100.0 if divergence is not None else None,
                ref,
                notes,
            ]
        )
        features.append(feature)

    def _annex14_trapezoid_from_widths(
        self,
        start_point: QgsPointXY,
        azimuth: float,
        length_m: float,
        inner_width_m: float,
        outer_width_m: float,
        description: str,
        start_z: Optional[float] = None,
        end_z: Optional[float] = None,
    ) -> Optional[QgsGeometry]:
        if start_z is not None and end_z is not None:
            end_point = start_point.project(length_m, azimuth)
            if end_point is None:
                return None
            az_perp_left = (azimuth - 90.0 + 360.0) % 360.0
            az_perp_right = (azimuth + 90.0) % 360.0
            inner_left = start_point.project(inner_width_m / 2.0, az_perp_left)
            inner_right = start_point.project(inner_width_m / 2.0, az_perp_right)
            outer_left = end_point.project(outer_width_m / 2.0, az_perp_left)
            outer_right = end_point.project(outer_width_m / 2.0, az_perp_right)
            if not all(point is not None for point in [inner_left, inner_right, outer_right, outer_left]):
                return None
            return self._annex14_polygon_z_from_corners(
                [
                    (inner_left, start_z),
                    (inner_right, start_z),
                    (outer_right, end_z),
                    (outer_left, end_z),
                ],
                description,
            )
        return self._create_trapezoid(
            start_point,
            azimuth,
            length_m,
            inner_width_m / 2.0,
            outer_width_m / 2.0,
            description,
        )

    def _annex14_rectangle_z_from_start(
        self,
        start_point: QgsPointXY,
        azimuth: float,
        length_m: float,
        width_m: float,
        z: Optional[float],
        description: str,
    ) -> Optional[QgsGeometry]:
        return self._annex14_trapezoid_from_widths(
            start_point,
            azimuth,
            length_m,
            width_m,
            width_m,
            description,
            start_z=z,
            end_z=z,
        )

    def _annex14_trapezoid_side_edges(
        self,
        start_point: QgsPointXY,
        azimuth: float,
        length_m: float,
        inner_width_m: float,
        outer_width_m: float,
    ) -> Dict[str, Optional[tuple]]:
        end_point = start_point.project(length_m, azimuth)
        if end_point is None:
            return {"left": None, "right": None}
        az_perp_left = (azimuth - 90.0 + 360.0) % 360.0
        az_perp_right = (azimuth + 90.0) % 360.0
        inner_left = start_point.project(inner_width_m / 2.0, az_perp_left)
        outer_left = end_point.project(outer_width_m / 2.0, az_perp_left)
        inner_right = start_point.project(inner_width_m / 2.0, az_perp_right)
        outer_right = end_point.project(outer_width_m / 2.0, az_perp_right)
        return {
            "left": (inner_left, outer_left, az_perp_left) if inner_left and outer_left else None,
            "right": (inner_right, outer_right, az_perp_right) if inner_right and outer_right else None,
        }

    def _annex14_add_side_panel_feature(
        self,
        features: List[QgsFeature],
        fields: QgsFields,
        lower_start: QgsPointXY,
        lower_end: QgsPointXY,
        outward_azimuth: float,
        horizontal_extent_m: float,
        runway_name: str,
        family: str,
        surface: str,
        component: str,
        end_desig: str,
        design_group: str,
        slope: Optional[float],
        ref: str,
        notes: str = "",
        lower_start_z: Optional[float] = None,
        lower_end_z: Optional[float] = None,
        upper_start_z: Optional[float] = None,
        upper_end_z: Optional[float] = None,
        contour_features: Optional[List[QgsFeature]] = None,
        contour_fields: Optional[QgsFields] = None,
        contour_interval: Optional[float] = None,
    ) -> None:
        if horizontal_extent_m <= 0 and (upper_start_z is None or slope in (None, 0)):
            return
        if (
            lower_start_z is not None
            and lower_end_z is not None
            and upper_start_z is not None
            and upper_end_z is not None
            and slope not in (None, 0)
        ):
            start_extent = max(0.0, (float(upper_start_z) - float(lower_start_z)) / float(slope))
            end_extent = max(0.0, (float(upper_end_z) - float(lower_end_z)) / float(slope))
        else:
            start_extent = horizontal_extent_m
            end_extent = horizontal_extent_m
            if lower_start_z is not None and slope is not None:
                upper_start_z = float(lower_start_z) + (float(start_extent) * float(slope))
            if lower_end_z is not None and slope is not None:
                upper_end_z = float(lower_end_z) + (float(end_extent) * float(slope))
        upper_start = lower_start.project(start_extent, outward_azimuth)
        upper_end = lower_end.project(end_extent, outward_azimuth)
        if upper_start is None or upper_end is None:
            return
        if None not in (lower_start_z, lower_end_z, upper_start_z, upper_end_z):
            geom = self._annex14_polygon_z_from_corners(
                [
                    (lower_start, lower_start_z),
                    (lower_end, lower_end_z),
                    (upper_end, upper_end_z),
                    (upper_start, upper_start_z),
                ],
                f"Annex 14 {surface} {component}",
            )
        else:
            geom = self._create_polygon_from_corners(
                [lower_start, lower_end, upper_end, upper_start],
                f"Annex 14 {surface} {component}",
            )
        self._annex14_add_polygon_feature(
            features,
            fields,
            geom,
            runway_name,
            family,
            surface,
            component,
            end_desig,
            design_group,
            lower_start.distance(lower_end),
            0.0,
            max(start_extent, end_extent),
            slope,
            0.0,
            ref,
            notes,
        )
        if contour_features is not None and contour_fields is not None and contour_interval is not None:
            if None in (lower_start_z, lower_end_z, upper_start_z, upper_end_z):
                return
            for contour_z in self._annex14_contour_elevations(
                min(float(lower_start_z), float(lower_end_z)),
                max(float(upper_start_z), float(upper_end_z)),
                contour_interval,
            ):
                def interp(lower_point, upper_point, lower_z, upper_z):
                    if abs(float(upper_z) - float(lower_z)) < 1e-6:
                        return None
                    t = (float(contour_z) - float(lower_z)) / (float(upper_z) - float(lower_z))
                    if t < -1e-6 or t > 1 + 1e-6:
                        return None
                    t = max(0.0, min(1.0, t))
                    return QgsPointXY(
                        lower_point.x() + ((upper_point.x() - lower_point.x()) * t),
                        lower_point.y() + ((upper_point.y() - lower_point.y()) * t),
                    )

                contour_start = interp(lower_start, upper_start, lower_start_z, upper_start_z)
                contour_end = interp(lower_end, upper_end, lower_end_z, upper_end_z)
                if contour_start is None or contour_end is None:
                    continue
                self._annex14_add_contour_feature(
                    contour_features,
                    contour_fields,
                    contour_start,
                    contour_end,
                    runway_name,
                    family,
                    surface,
                    component,
                    end_desig,
                    design_group,
                    contour_z,
                    ref,
                )

    def _annex14_add_side_panels_for_trapezoid(
        self,
        features: List[QgsFeature],
        fields: QgsFields,
        start_point: QgsPointXY,
        azimuth: float,
        length_m: float,
        inner_width_m: float,
        outer_width_m: float,
        horizontal_extent_m: float,
        runway_name: str,
        family: str,
        surface: str,
        component_prefix: str,
        end_desig: str,
        design_group: str,
        slope: Optional[float],
        ref: str,
        notes: str = "",
        lower_start_z: Optional[float] = None,
        lower_end_z: Optional[float] = None,
        upper_start_z: Optional[float] = None,
        upper_end_z: Optional[float] = None,
        contour_features: Optional[List[QgsFeature]] = None,
        contour_fields: Optional[QgsFields] = None,
        contour_interval: Optional[float] = None,
    ) -> None:
        for side, edge in self._annex14_trapezoid_side_edges(
            start_point,
            azimuth,
            length_m,
            inner_width_m,
            outer_width_m,
        ).items():
            if edge is None:
                continue
            lower_start, lower_end, outward_azimuth = edge
            self._annex14_add_side_panel_feature(
                features,
                fields,
                lower_start,
                lower_end,
                outward_azimuth,
                horizontal_extent_m,
                runway_name,
                family,
                surface,
                f"{component_prefix}_{side}",
                end_desig,
                design_group,
                slope,
                ref,
                notes,
                lower_start_z=lower_start_z,
                lower_end_z=lower_end_z,
                upper_start_z=upper_start_z,
                upper_end_z=upper_end_z,
                contour_features=contour_features,
                contour_fields=contour_fields,
                contour_interval=contour_interval,
            )

    def _annex14_append_approach_like_sections(
        self,
        features: List[QgsFeature],
        fields: QgsFields,
        runway_name: str,
        family: str,
        surface: str,
        component: str,
        end_desig: str,
        design_group: str,
        start_point: QgsPointXY,
        azimuth: float,
        inner_width_m: float,
        sections: Iterable[dict],
        ref: str,
        start_z: Optional[float] = None,
        contour_features: Optional[List[QgsFeature]] = None,
        contour_fields: Optional[QgsFields] = None,
        contour_interval: Optional[float] = None,
    ) -> None:
        current_start = start_point
        current_width = inner_width_m
        current_z = start_z
        for section in sections:
            length_m = float(section.get("length_m") or 0.0)
            divergence = float(section.get("divergence") or 0.0)
            if length_m <= 0:
                continue
            outer_width = current_width + (2.0 * divergence * length_m)
            end_z = self._annex14_surface_z(current_z, length_m, section.get("slope"))
            geom = self._annex14_trapezoid_from_widths(
                current_start,
                azimuth,
                length_m,
                current_width,
                outer_width,
                f"{surface} {component} {section.get('section')}",
                start_z=current_z,
                end_z=end_z,
            )
            self._annex14_add_polygon_feature(
                features,
                fields,
                geom,
                runway_name,
                family,
                surface,
                f"{component}_{section.get('section')}",
                end_desig,
                design_group,
                length_m,
                current_width,
                outer_width,
                section.get("slope"),
                divergence,
                ref,
            )
            if contour_features is not None and contour_fields is not None and contour_interval is not None:
                self._annex14_add_trapezoid_contours(
                    contour_features,
                    contour_fields,
                    current_start,
                    azimuth,
                    length_m,
                    current_width,
                    outer_width,
                    current_z,
                    end_z,
                    runway_name,
                    family,
                    surface,
                    f"{component}_{section.get('section')}",
                    end_desig,
                    design_group,
                    ref,
                    contour_interval,
                )
            next_start = current_start.project(length_m, azimuth)
            if next_start is None:
                break
            current_start = next_start
            current_width = outer_width
            current_z = end_z

    def _annex14_append_side_panels_for_approach_like_sections(
        self,
        features: List[QgsFeature],
        fields: QgsFields,
        runway_name: str,
        family: str,
        surface: str,
        component_prefix: str,
        end_desig: str,
        design_group: str,
        start_point: QgsPointXY,
        azimuth: float,
        inner_width_m: float,
        sections: Iterable[dict],
        horizontal_extent_m: float,
        side_slope: Optional[float],
        ref: str,
        notes: str = "",
        start_z: Optional[float] = None,
        upper_edge_z: Optional[float] = None,
        contour_features: Optional[List[QgsFeature]] = None,
        contour_fields: Optional[QgsFields] = None,
        contour_interval: Optional[float] = None,
    ) -> None:
        current_start = start_point
        current_width = inner_width_m
        current_z = start_z
        for section in sections:
            length_m = float(section.get("length_m") or 0.0)
            divergence = float(section.get("divergence") or 0.0)
            if length_m <= 0:
                continue
            outer_width = current_width + (2.0 * divergence * length_m)
            end_z = self._annex14_surface_z(current_z, length_m, section.get("slope"))
            self._annex14_add_side_panels_for_trapezoid(
                features,
                fields,
                current_start,
                azimuth,
                length_m,
                current_width,
                outer_width,
                horizontal_extent_m,
                runway_name,
                family,
                surface,
                f"{component_prefix}_{section.get('section')}",
                end_desig,
                design_group,
                side_slope,
                ref,
                notes,
                lower_start_z=current_z,
                lower_end_z=end_z,
                upper_start_z=upper_edge_z,
                upper_end_z=upper_edge_z,
                contour_features=contour_features,
                contour_fields=contour_fields,
                contour_interval=contour_interval,
            )
            next_start = current_start.project(length_m, azimuth)
            if next_start is None:
                break
            current_start = next_start
            current_width = outer_width
            current_z = end_z

    def _annex14_takeoff_climb_sections(self, params: dict) -> List[dict]:
        length_m = float(params.get("length_m") or 0.0)
        inner_width = float(params.get("inner_edge_length_m") or 0.0)
        final_width = float(params.get("final_width_m") or inner_width)
        divergence = float(params.get("divergence") or 0.0)
        if length_m <= 0 or divergence <= 0:
            return []
        distance_to_final = max(0.0, (final_width - inner_width) / (2.0 * divergence))
        if distance_to_final >= length_m:
            return [{"section": "divergent", "length_m": length_m, "divergence": divergence, "slope": params.get("slope")}]
        return [
            {"section": "divergent", "length_m": distance_to_final, "divergence": divergence, "slope": params.get("slope")},
            {"section": "constant_width", "length_m": length_m - distance_to_final, "divergence": 0.0, "slope": params.get("slope")},
        ]

    def _annex14_feature_attribute(self, feature: QgsFeature, field_name: str):
        try:
            idx = feature.fields().indexFromName(field_name)
            if idx != -1:
                return feature.attribute(idx)
        except Exception:
            pass
        return None

    def _annex14_features_for_end(self, features: List[QgsFeature], end_desig: str) -> List[QgsFeature]:
        return [
            feature
            for feature in features
            if str(self._annex14_feature_attribute(feature, "end_desig") or "") == end_desig
        ]

    def _annex14_runway_wide_features(self, features: List[QgsFeature]) -> List[QgsFeature]:
        return [
            feature
            for feature in features
            if not str(self._annex14_feature_attribute(feature, "end_desig") or "")
        ]

    def _annex14_features_by_surface(self, features: List[QgsFeature]) -> Dict[str, List[QgsFeature]]:
        grouped: Dict[str, List[QgsFeature]] = {}
        for feature in features:
            surface = str(self._annex14_feature_attribute(feature, "surface") or "surface").strip() or "surface"
            grouped.setdefault(surface, []).append(feature)
        return grouped

    def _annex14_surface_label(self, surface: str) -> str:
        return str(surface or "surface").replace("_", " ").title()

    def _annex14_polygon_layer_type(self, features: List[QgsFeature]) -> str:
        try:
            if features and all(QgsWkbTypes.hasZ(feature.geometry().wkbType()) for feature in features):
                return "PolygonZ"
        except Exception:
            return "Polygon"
        return "Polygon"

    def _annex14_contour_style_key(self, surface: str) -> str:
        surface_key = str(surface or "").strip().lower()
        if "transitional" in surface_key:
            return "OLS Transitional Contour"
        if surface_key in {"instrument_departure", "take_off_climb"}:
            return "OLS TOCS Contour"
        return "OLS Approach Contour"

    def _annex14_runway_group(self, parent_group: QgsLayerTreeGroup, runway_label: str) -> QgsLayerTreeGroup:
        return self._ensure_layer_group(parent_group, f"RWY {runway_label}")

    def _annex14_surface_group(
        self,
        parent_group: QgsLayerTreeGroup,
        runway_label: str,
        family_label: str,
    ) -> QgsLayerTreeGroup:
        runway_group = self._annex14_runway_group(parent_group, runway_label)
        return self._ensure_layer_group(runway_group, family_label)

    def process_annex14_geometry(self, runway_data: dict, layer_group: QgsLayerTreeGroup) -> bool:
        ruleset = self.get_active_protected_airspace_ruleset()
        if getattr(ruleset, "protected_airspace_model", "") != "annex14_modernised_ofs_oes":
            return False
        if layer_group is None:
            return False

        runway_name = runway_data.get("short_name", f"RWY_{runway_data.get('original_index', '?')}")
        thr_point = runway_data.get("thr_point")
        rec_thr_point = runway_data.get("rec_thr_point")
        if thr_point is None or rec_thr_point is None:
            return False
        rwy_params = self._get_runway_parameters(thr_point, rec_thr_point)
        if rwy_params is None:
            return False
        design_group = self._annex14_design_group_for_runway(runway_data)
        if not design_group:
            QgsMessageLog.logMessage(
                f"Annex 14 geometry skipped for {runway_name}: no ADG/design_group or critical aircraft data supplied.",
                PLUGIN_TAG,
                Qgis.Warning,
            )
            return False

        fields = self._annex14_surface_fields()
        contour_fields = self._annex14_contour_fields()
        ofs_features: List[QgsFeature] = []
        oes_features: List[QgsFeature] = []
        ofs_contour_features: List[QgsFeature] = []
        oes_contour_features: List[QgsFeature] = []
        approach_contour_interval = self._annex14_contour_interval("approach")
        tocs_contour_interval = self._annex14_contour_interval("tocs")
        transitional_contour_interval = self._annex14_contour_interval("transitional")
        code_f_no_digital = bool(runway_data.get("code_letter_f_without_digital_avionics", False))

        for end_config in self._annex14_runway_end_configs(runway_data, rwy_params):
            threshold = end_config["threshold"]
            if threshold is None:
                continue
            end_desig = end_config["end_desig"]
            runway_type = end_config["runway_type"]
            approach_az = end_config["approach_azimuth"]
            takeoff_az = end_config["takeoff_azimuth"]
            threshold_z = end_config.get("threshold_elev")
            opposite_threshold_z = end_config.get("opposite_threshold_elev")
            highest_threshold_z = end_config.get("highest_threshold_elev")
            takeoff_start_z = end_config.get("takeoff_start_elev")
            runway_length_m = float(rwy_params.get("length") or 0.0)

            ofs = ruleset.obstacle_free_surfaces(
                design_group=design_group,
                runway_type=runway_type,
                runway_width_m=runway_data.get("runway_width"),
                code_letter_f_without_digital_avionics=code_f_no_digital,
            )
            approach = next((s for s in ofs["groups"]["general"] if s.get("surface") == "approach"), None)
            approach_start = None
            approach_length_m = None
            approach_inner_width = None
            approach_outer_width = None
            if approach:
                start = threshold.project(float(approach["distance_from_threshold_m"]), approach_az)
                if start is not None:
                    length_m = float(approach["length_m"])
                    inner_width = float(approach["inner_edge_length_m"])
                    divergence = float(approach["divergence"])
                    outer_width = inner_width + 2.0 * divergence * length_m
                    geom = self._annex14_trapezoid_from_widths(
                        start,
                        approach_az,
                        length_m,
                        inner_width,
                        outer_width,
                        f"Annex 14 OFS Approach {end_desig}",
                        start_z=threshold_z,
                        end_z=self._annex14_surface_z(threshold_z, length_m, approach.get("slope")),
                    )
                    self._annex14_add_polygon_feature(
                        ofs_features,
                        fields,
                        geom,
                        runway_name,
                        "OFS",
                        "approach",
                        "approach",
                        end_desig,
                        design_group,
                        length_m,
                        inner_width,
                        outer_width,
                        approach.get("slope"),
                        divergence,
                        approach.get("ref", ""),
                    )
                    self._annex14_add_trapezoid_contours(
                        ofs_contour_features,
                        contour_fields,
                        start,
                        approach_az,
                        length_m,
                        inner_width,
                        outer_width,
                        threshold_z,
                        self._annex14_surface_z(threshold_z, length_m, approach.get("slope")),
                        runway_name,
                        "OFS",
                        "approach",
                        "approach",
                        end_desig,
                        design_group,
                        approach.get("ref", ""),
                        approach_contour_interval,
                    )
                    approach_start = start
                    approach_length_m = length_m
                    approach_inner_width = inner_width
                    approach_outer_width = outer_width

            transitional = next((s for s in ofs["groups"]["general"] if s.get("surface") == "transitional"), None)
            if transitional and approach_start is not None and approach_length_m is not None:
                trans_slope = float(transitional.get("slope") or 0.0)
                upper_height = float(transitional.get("upper_edge_height_above_highest_threshold_m") or 60.0)
                horizontal_extent = upper_height / trans_slope if trans_slope > 0 else 0.0
                upper_edge_z = (highest_threshold_z + upper_height) if highest_threshold_z is not None else None
                self._annex14_add_side_panels_for_trapezoid(
                    ofs_features,
                    fields,
                    approach_start,
                    approach_az,
                    approach_length_m,
                    approach_inner_width,
                    approach_outer_width,
                    horizontal_extent,
                    runway_name,
                    "OFS",
                    "transitional",
                    "approach_side",
                    end_desig,
                    design_group,
                    trans_slope,
                    transitional.get("ref", ""),
                    "Plan-view side panels from approach surface lower edges to 60 m upper edge.",
                    lower_start_z=threshold_z,
                    lower_end_z=self._annex14_surface_z(threshold_z, approach_length_m, approach.get("slope")),
                    upper_start_z=upper_edge_z,
                    upper_end_z=upper_edge_z,
                    contour_features=ofs_contour_features,
                    contour_fields=contour_fields,
                    contour_interval=transitional_contour_interval,
                )

            inner_approach = next((s for s in ofs["groups"]["inner"] if s.get("surface") == "inner_approach"), None)
            inner_approach_start = None
            inner_approach_length_m = None
            inner_approach_width = None
            inner_approach_end_z = None
            if inner_approach and approach:
                start = threshold.project(float(approach["distance_from_threshold_m"]), approach_az)
                if start is not None:
                    inner_approach_length_m = float(inner_approach["length_m"])
                    inner_approach_width = float(inner_approach["inner_edge_length_m"])
                    inner_approach_end_z = self._annex14_surface_z(
                        threshold_z,
                        inner_approach_length_m,
                        approach.get("slope"),
                    )
                    geom = self._annex14_trapezoid_from_widths(
                        start,
                        approach_az,
                        inner_approach_length_m,
                        inner_approach_width,
                        inner_approach_width,
                        f"Annex 14 OFS Inner Approach {end_desig}",
                        start_z=threshold_z,
                        end_z=inner_approach_end_z,
                    )
                    self._annex14_add_polygon_feature(
                        ofs_features,
                        fields,
                        geom,
                        runway_name,
                        "OFS",
                        "inner_approach",
                        "inner_approach",
                        end_desig,
                        design_group,
                        inner_approach.get("length_m"),
                        inner_approach.get("inner_edge_length_m"),
                        inner_approach.get("inner_edge_length_m"),
                        approach.get("slope"),
                        0.0,
                        inner_approach.get("ref", ""),
                    )
                    self._annex14_add_trapezoid_contours(
                        ofs_contour_features,
                        contour_fields,
                        start,
                        approach_az,
                        inner_approach_length_m,
                        inner_approach_width,
                        inner_approach_width,
                        threshold_z,
                        inner_approach_end_z,
                        runway_name,
                        "OFS",
                        "inner_approach",
                        "inner_approach",
                        end_desig,
                        design_group,
                        inner_approach.get("ref", ""),
                        approach_contour_interval,
                    )
                    inner_approach_start = start

            balked = next((s for s in ofs["groups"]["inner"] if s.get("surface") == "balked_landing"), None)
            balked_start = None
            balked_length_m = None
            balked_inner_width = None
            balked_outer_width = None
            balked_start_z = None
            balked_end_z = None
            if balked:
                distance = balked.get("distance_from_threshold_m")
                if distance is not None:
                    start = threshold.project(float(distance), takeoff_az)
                    if start is not None:
                        balked_start_z = self._annex14_runway_axis_z(
                            threshold_z,
                            opposite_threshold_z,
                            float(distance),
                            runway_length_m,
                        )
                        length_m = 60.0 / float(balked.get("slope") or 1.0)
                        inner_width = float(balked["inner_edge_length_m"])
                        divergence = float(balked["divergence"])
                        outer_width = inner_width + 2.0 * divergence * length_m
                        balked_end_z = self._annex14_surface_z(balked_start_z, length_m, balked.get("slope"))
                        geom = self._annex14_trapezoid_from_widths(
                            start,
                            takeoff_az,
                            length_m,
                            inner_width,
                            outer_width,
                            f"Annex 14 OFS Balked Landing {end_desig}",
                            start_z=balked_start_z,
                            end_z=balked_end_z,
                        )
                        self._annex14_add_polygon_feature(
                            ofs_features,
                            fields,
                            geom,
                            runway_name,
                            "OFS",
                            "balked_landing",
                            "balked_landing",
                            end_desig,
                            design_group,
                            length_m,
                            inner_width,
                            outer_width,
                            balked.get("slope"),
                            divergence,
                            balked.get("ref", ""),
                            balked.get("distance_rule", ""),
                        )
                        self._annex14_add_trapezoid_contours(
                            ofs_contour_features,
                            contour_fields,
                            start,
                            takeoff_az,
                            length_m,
                            inner_width,
                            outer_width,
                            balked_start_z,
                            balked_end_z,
                            runway_name,
                            "OFS",
                            "balked_landing",
                            "balked_landing",
                            end_desig,
                            design_group,
                            balked.get("ref", ""),
                            approach_contour_interval,
                        )
                        balked_start = start
                        balked_length_m = length_m
                        balked_inner_width = inner_width
                        balked_outer_width = outer_width

            inner_transitional = next(
                (s for s in ofs["groups"]["inner"] if s.get("surface") == "inner_transitional"),
                None,
            )
            if inner_transitional and inner_approach_start is not None and inner_approach_width is not None:
                inner_trans_slope = float(
                    inner_transitional.get("slope")
                    or inner_transitional.get("inclined_section_slope")
                    or 0.0
                )
                upper_height = float(inner_transitional.get("upper_edge_height_above_highest_threshold_m") or 60.0)
                vertical_height = float(inner_transitional.get("vertical_section_height_m") or 0.0)
                horizontal_extent = max(0.0, upper_height - vertical_height) / inner_trans_slope if inner_trans_slope > 0 else 0.0
                upper_edge_z = (highest_threshold_z + upper_height) if highest_threshold_z is not None else None
                self._annex14_add_side_panels_for_trapezoid(
                    ofs_features,
                    fields,
                    inner_approach_start,
                    approach_az,
                    inner_approach_length_m,
                    inner_approach_width,
                    inner_approach_width,
                    horizontal_extent,
                    runway_name,
                    "OFS",
                    "inner_transitional",
                    "inner_approach_side",
                    end_desig,
                    design_group,
                    inner_trans_slope,
                    inner_transitional.get("ref", ""),
                    f"Plan-view inner transitional side panels; vertical section height {vertical_height:g} m.",
                    lower_start_z=threshold_z,
                    lower_end_z=inner_approach_end_z,
                    upper_start_z=upper_edge_z,
                    upper_end_z=upper_edge_z,
                    contour_features=ofs_contour_features,
                    contour_fields=contour_fields,
                    contour_interval=transitional_contour_interval,
                )
                if balked_start is not None and balked_inner_width is not None:
                    half_width = max(inner_approach_width, balked_inner_width) / 2.0
                    for side, outward_azimuth in {
                        "left": (takeoff_az + 90.0) % 360.0,
                        "right": (takeoff_az - 90.0 + 360.0) % 360.0,
                    }.items():
                        lower_start = inner_approach_start.project(half_width, outward_azimuth)
                        lower_end = balked_start.project(half_width, outward_azimuth)
                        if lower_start is None or lower_end is None:
                            continue
                        self._annex14_add_side_panel_feature(
                            ofs_features,
                            fields,
                            lower_start,
                            lower_end,
                            outward_azimuth,
                            horizontal_extent,
                            runway_name,
                            "OFS",
                            "inner_transitional",
                            f"runway_side_{side}",
                            end_desig,
                            design_group,
                            inner_trans_slope,
                            inner_transitional.get("ref", ""),
                            "Precision runway inner transitional panel between inner approach and balked landing.",
                            lower_start_z=threshold_z,
                            lower_end_z=balked_start_z,
                            upper_start_z=upper_edge_z,
                            upper_end_z=upper_edge_z,
                            contour_features=ofs_contour_features,
                            contour_fields=contour_fields,
                            contour_interval=transitional_contour_interval,
                        )
                    self._annex14_add_side_panels_for_trapezoid(
                        ofs_features,
                        fields,
                        balked_start,
                        takeoff_az,
                        balked_length_m,
                        balked_inner_width,
                        balked_outer_width,
                        horizontal_extent,
                        runway_name,
                        "OFS",
                        "inner_transitional",
                        "balked_landing_side",
                        end_desig,
                        design_group,
                        inner_trans_slope,
                        inner_transitional.get("ref", ""),
                        "Precision runway inner transitional panels along balked landing surface.",
                        lower_start_z=balked_start_z,
                        lower_end_z=balked_end_z,
                        upper_start_z=upper_edge_z,
                        upper_end_z=upper_edge_z,
                        contour_features=ofs_contour_features,
                        contour_fields=contour_fields,
                        contour_interval=transitional_contour_interval,
                    )

            precision = ruleset.precision_approach_surface_parameters()
            approach_component = precision["components"]["approach"]
            pa_start = threshold.project(float(approach_component["distance_from_threshold_m"]), approach_az)
            if pa_start is not None:
                self._annex14_append_approach_like_sections(
                    oes_features,
                    fields,
                    runway_name,
                    "OES",
                    "precision_approach",
                    "approach",
                    end_desig,
                    design_group,
                    pa_start,
                    approach_az,
                    float(approach_component["inner_edge_length_m"]),
                    approach_component["sections"],
                    precision.get("ref", ""),
                    start_z=threshold_z,
                    contour_features=oes_contour_features,
                    contour_fields=contour_fields,
                    contour_interval=approach_contour_interval,
                )
            missed = precision["components"]["missed_approach"]
            missed_start = threshold.project(float(missed["distance_after_threshold_m"]), takeoff_az)
            missed_start_z = self._annex14_runway_axis_z(
                threshold_z,
                opposite_threshold_z,
                float(missed["distance_after_threshold_m"]),
                runway_length_m,
            )
            if missed_start is not None:
                self._annex14_append_approach_like_sections(
                    oes_features,
                    fields,
                    runway_name,
                    "OES",
                    "precision_approach",
                    "missed_approach",
                    end_desig,
                    design_group,
                    missed_start,
                    takeoff_az,
                    float(missed["inner_edge_length_m"]),
                    missed["sections"],
                    precision.get("ref", ""),
                    start_z=missed_start_z,
                    contour_features=oes_contour_features,
                    contour_fields=contour_fields,
                    contour_interval=approach_contour_interval,
                )
            transitional_component = precision["components"].get("transitional", {})
            transitional_slope = float(transitional_component.get("slope") or 0.0)
            transitional_upper_height = float(transitional_component.get("upper_edge_height_above_threshold_m") or 300.0)
            transitional_extent = (
                transitional_upper_height / transitional_slope if transitional_slope > 0 else 0.0
            )
            if pa_start is not None and missed_start is not None:
                lower_length = pa_start.distance(missed_start)
                lower_width = float(approach_component["inner_edge_length_m"])
                lower_component_geom = self._annex14_rectangle_z_from_start(
                    pa_start,
                    takeoff_az,
                    lower_length,
                    lower_width,
                    threshold_z,
                    f"Annex 14 OES Precision Lower Component {end_desig}",
                )
                self._annex14_add_polygon_feature(
                    oes_features,
                    fields,
                    lower_component_geom,
                    runway_name,
                    "OES",
                    "precision_approach",
                    "lower_component",
                    end_desig,
                    design_group,
                    lower_length,
                    lower_width,
                    lower_width,
                    None,
                    0.0,
                    precision.get("ref", ""),
                    "Lower component between approach and missed approach inner edges.",
                )
                if transitional_extent > 0:
                    half_width = lower_width / 2.0
                    for side, outward_azimuth in {
                        "left": (takeoff_az + 90.0) % 360.0,
                        "right": (takeoff_az - 90.0 + 360.0) % 360.0,
                    }.items():
                        lower_start = pa_start.project(half_width, outward_azimuth)
                        lower_end = missed_start.project(half_width, outward_azimuth)
                        if lower_start is None or lower_end is None:
                            continue
                        self._annex14_add_side_panel_feature(
                            oes_features,
                            fields,
                            lower_start,
                            lower_end,
                            outward_azimuth,
                            transitional_extent,
                            runway_name,
                            "OES",
                            "precision_approach",
                            f"transitional_lower_component_{side}",
                            end_desig,
                            design_group,
                            transitional_slope,
                            precision.get("ref", ""),
                            "Transitional component along precision lower component.",
                            lower_start_z=threshold_z,
                            lower_end_z=threshold_z,
                            upper_start_z=self._annex14_surface_z(threshold_z, transitional_upper_height, 1.0),
                            upper_end_z=self._annex14_surface_z(threshold_z, transitional_upper_height, 1.0),
                            contour_features=oes_contour_features,
                            contour_fields=contour_fields,
                            contour_interval=transitional_contour_interval,
                        )
            if pa_start is not None and transitional_extent > 0:
                self._annex14_append_side_panels_for_approach_like_sections(
                    oes_features,
                    fields,
                    runway_name,
                    "OES",
                    "precision_approach",
                    "transitional_approach",
                    end_desig,
                    design_group,
                    pa_start,
                    approach_az,
                    float(approach_component["inner_edge_length_m"]),
                    approach_component["sections"],
                    transitional_extent,
                    transitional_slope,
                    precision.get("ref", ""),
                    "Transitional component along precision approach component.",
                    start_z=threshold_z,
                    upper_edge_z=self._annex14_surface_z(threshold_z, transitional_upper_height, 1.0),
                    contour_features=oes_contour_features,
                    contour_fields=contour_fields,
                    contour_interval=transitional_contour_interval,
                )
            if missed_start is not None and transitional_extent > 0:
                self._annex14_append_side_panels_for_approach_like_sections(
                    oes_features,
                    fields,
                    runway_name,
                    "OES",
                    "precision_approach",
                    "transitional_missed_approach",
                    end_desig,
                    design_group,
                    missed_start,
                    takeoff_az,
                    float(missed["inner_edge_length_m"]),
                    missed["sections"],
                    transitional_extent,
                    transitional_slope,
                    precision.get("ref", ""),
                    "Transitional component along precision missed approach component.",
                    start_z=missed_start_z,
                    upper_edge_z=self._annex14_surface_z(threshold_z, transitional_upper_height, 1.0),
                    contour_features=oes_contour_features,
                    contour_fields=contour_fields,
                    contour_interval=transitional_contour_interval,
                )

            departure = ruleset.instrument_departure_surface_parameters()
            dep_start = end_config["takeoff_start"]
            if dep_start is not None:
                self._annex14_append_approach_like_sections(
                    oes_features,
                    fields,
                    runway_name,
                    "OES",
                    "instrument_departure",
                    "departure",
                    end_desig,
                    design_group,
                    dep_start,
                    takeoff_az,
                    float(departure["inner_edge_length_m"]),
                    departure["sections"],
                    departure.get("ref", ""),
                    start_z=self._annex14_surface_z(takeoff_start_z, 5.0, 1.0),
                    contour_features=oes_contour_features,
                    contour_fields=contour_fields,
                    contour_interval=tocs_contour_interval,
                )

            mass = end_config.get("takeoff_mass_kg")
            takeoff = ruleset.take_off_climb_surface_parameters(
                design_group,
                max_certificated_takeoff_mass_kg=float(mass) if mass is not None else None,
            )
            if takeoff and dep_start is not None:
                self._annex14_append_approach_like_sections(
                    oes_features,
                    fields,
                    runway_name,
                    "OES",
                    "take_off_climb",
                    "take_off_climb",
                    end_desig,
                    design_group,
                    dep_start,
                    takeoff_az,
                    float(takeoff["inner_edge_length_m"]),
                    self._annex14_takeoff_climb_sections(takeoff),
                    takeoff.get("ref", ""),
                    start_z=takeoff_start_z,
                    contour_features=oes_contour_features,
                    contour_fields=contour_fields,
                    contour_interval=tocs_contour_interval,
                )

        straight_in = ruleset.straight_in_instrument_approach_surface_parameters()
        aerodrome_elev = self._annex14_float_or_none(getattr(self, "arp_elevation_amsl", None))
        lower_horizontal = ruleset.horizontal_surface_parameters("I")
        if lower_horizontal:
            runway_axis = QgsGeometry.fromPolylineXY([thr_point, rec_thr_point])
            geom = runway_axis.buffer(float(lower_horizontal["radius_m"]), 72)
            lower_z = (
                aerodrome_elev + float(straight_in["lower_section"]["height_above_aerodrome_elevation_m"])
                if aerodrome_elev is not None
                else None
            )
            self._annex14_add_polygon_feature(
                oes_features,
                fields,
                self._annex14_flat_z_polygon(geom, lower_z),
                runway_name,
                "OES",
                "straight_in_instrument_approach",
                "lower_section",
                "",
                design_group,
                None,
                lower_horizontal["radius_m"] * 2.0,
                lower_horizontal["radius_m"] * 2.0,
                None,
                None,
                straight_in.get("ref", ""),
                "Lower section corresponding to horizontal OES as per ADG I.",
            )
        upper = straight_in["upper_section"]
        upper_extension = float(upper["longer_side_length_from_threshold_or_thresholds_m"])
        rect_start = thr_point.project(upper_extension, rwy_params["azimuth_r_p"])
        if rect_start is not None:
            total_len = upper_extension * 2.0 + float(rwy_params["length"])
            upper_z = (
                aerodrome_elev + float(upper["height_above_aerodrome_elevation_m"])
                if aerodrome_elev is not None
                else None
            )
            geom = self._annex14_rectangle_z_from_start(
                rect_start,
                rwy_params["azimuth_p_r"],
                total_len,
                float(upper["shorter_side_length_m"]),
                upper_z,
                f"Annex 14 OES Straight-in {runway_name}",
            )
            self._annex14_add_polygon_feature(
                oes_features,
                fields,
                geom,
                runway_name,
                "OES",
                "straight_in_instrument_approach",
                "upper_section",
                "",
                design_group,
                total_len,
                upper["shorter_side_length_m"],
                upper["shorter_side_length_m"],
                None,
                0.0,
                straight_in.get("ref", ""),
            )

        horizontal = ruleset.horizontal_surface_parameters(design_group)
        if horizontal:
            runway_axis = QgsGeometry.fromPolylineXY([thr_point, rec_thr_point])
            geom = runway_axis.buffer(float(horizontal["radius_m"]), 72)
            horizontal_z = (
                aerodrome_elev + float(horizontal["height_above_aerodrome_elevation_m"])
                if aerodrome_elev is not None
                else None
            )
            self._annex14_add_polygon_feature(
                oes_features,
                fields,
                self._annex14_flat_z_polygon(geom, horizontal_z),
                runway_name,
                "OES",
                "horizontal",
                "threshold_arcs_with_tangent_sides",
                "",
                design_group,
                None,
                horizontal["radius_m"] * 2.0,
                horizontal["radius_m"] * 2.0,
                None,
                None,
                horizontal.get("ref", ""),
                "runway-axis buffer: threshold-centred arcs joined tangentially",
            )

        created = False
        try:
            for end_config in self._annex14_runway_end_configs(runway_data, rwy_params):
                end_desig = end_config["end_desig"]
                safe_end_desig = str(end_desig).replace("/", "_")
                end_ofs_features = self._annex14_features_for_end(ofs_features, end_desig)
                end_oes_features = self._annex14_features_for_end(oes_features, end_desig)
                end_ofs_contours = self._annex14_features_for_end(ofs_contour_features, end_desig)
                end_oes_contours = self._annex14_features_for_end(oes_contour_features, end_desig)

                if end_ofs_features:
                    ofs_group = self._annex14_surface_group(layer_group, end_desig, "Obstacle Free Surfaces")
                    for surface, surface_features in self._annex14_features_by_surface(end_ofs_features).items():
                        safe_surface = self._sanitize_filename(surface)
                        surface_label = self._annex14_surface_label(surface)
                        layer = self._create_and_add_layer(
                            self._annex14_polygon_layer_type(surface_features),
                            f"Annex14_OFS_{runway_name.replace('/', '_')}_{safe_end_desig}_{safe_surface}",
                            f"Annex 14 OFS {surface_label} RWY {end_desig}",
                            fields,
                            surface_features,
                            ofs_group,
                            "OLS Approach",
                        )
                        created = created or layer is not None

                if end_ofs_contours:
                    ofs_group = self._annex14_surface_group(layer_group, end_desig, "Obstacle Free Surfaces")
                    for surface, surface_features in self._annex14_features_by_surface(end_ofs_contours).items():
                        safe_surface = self._sanitize_filename(surface)
                        surface_label = self._annex14_surface_label(surface)
                        layer = self._create_and_add_layer(
                            "LineString",
                            f"Annex14_OFS_{runway_name.replace('/', '_')}_{safe_end_desig}_{safe_surface}_Contours",
                            f"Annex 14 OFS {surface_label} Contours RWY {end_desig}",
                            contour_fields,
                            surface_features,
                            ofs_group,
                            self._annex14_contour_style_key(surface),
                        )
                        created = created or layer is not None

                if end_oes_features:
                    oes_group = self._annex14_surface_group(layer_group, end_desig, "Obstacle Evaluation Surfaces")
                    for surface, surface_features in self._annex14_features_by_surface(end_oes_features).items():
                        safe_surface = self._sanitize_filename(surface)
                        surface_label = self._annex14_surface_label(surface)
                        layer = self._create_and_add_layer(
                            self._annex14_polygon_layer_type(surface_features),
                            f"Annex14_OES_{runway_name.replace('/', '_')}_{safe_end_desig}_{safe_surface}",
                            f"Annex 14 OES {surface_label} RWY {end_desig}",
                            fields,
                            surface_features,
                            oes_group,
                            "OLS TOCS",
                        )
                        created = created or layer is not None

                if end_oes_contours:
                    oes_group = self._annex14_surface_group(layer_group, end_desig, "Obstacle Evaluation Surfaces")
                    for surface, surface_features in self._annex14_features_by_surface(end_oes_contours).items():
                        safe_surface = self._sanitize_filename(surface)
                        surface_label = self._annex14_surface_label(surface)
                        layer = self._create_and_add_layer(
                            "LineString",
                            f"Annex14_OES_{runway_name.replace('/', '_')}_{safe_end_desig}_{safe_surface}_Contours",
                            f"Annex 14 OES {surface_label} Contours RWY {end_desig}",
                            contour_fields,
                            surface_features,
                            oes_group,
                            self._annex14_contour_style_key(surface),
                        )
                        created = created or layer is not None

            runway_wide_oes_features = self._annex14_runway_wide_features(oes_features)
            if runway_wide_oes_features:
                runway_wide_group = self._annex14_surface_group(
                    layer_group,
                    runway_name,
                    "Obstacle Evaluation Surfaces",
                )
                for surface, surface_features in self._annex14_features_by_surface(runway_wide_oes_features).items():
                    safe_surface = self._sanitize_filename(surface)
                    surface_label = self._annex14_surface_label(surface)
                    layer = self._create_and_add_layer(
                        self._annex14_polygon_layer_type(surface_features),
                        f"Annex14_OES_{runway_name.replace('/', '_')}_{safe_surface}",
                        f"Annex 14 OES {surface_label} RWY {runway_name}",
                        fields,
                        surface_features,
                        runway_wide_group,
                        "OLS TOCS",
                    )
                    created = created or layer is not None

            runway_wide_oes_contours = self._annex14_runway_wide_features(oes_contour_features)
            if runway_wide_oes_contours:
                runway_wide_group = self._annex14_surface_group(
                    layer_group,
                    runway_name,
                    "Obstacle Evaluation Surfaces",
                )
                for surface, surface_features in self._annex14_features_by_surface(runway_wide_oes_contours).items():
                    safe_surface = self._sanitize_filename(surface)
                    surface_label = self._annex14_surface_label(surface)
                    layer = self._create_and_add_layer(
                        "LineString",
                        f"Annex14_OES_{runway_name.replace('/', '_')}_{safe_surface}_Contours",
                        f"Annex 14 OES {surface_label} Contours RWY {runway_name}",
                        contour_fields,
                        surface_features,
                        runway_wide_group,
                        self._annex14_contour_style_key(surface),
                    )
                    created = created or layer is not None
        except Exception as exc:
            QgsMessageLog.logMessage(
                f"Annex 14 geometry failed for {runway_name}: {exc}\n{traceback.format_exc()}",
                PLUGIN_TAG,
                Qgis.Critical,
            )
        return created
