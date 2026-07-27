# -*- coding: utf-8 -*-
"""CNS building restricted area generator backed by NASF policy parameters."""

from typing import Any, List, Optional

from qgis.PyQt.QtCore import QVariant  # type: ignore
from qgis.core import (  # type: ignore
    Qgis,
    QgsCoordinateReferenceSystem,
    QgsFeature,
    QgsField,
    QgsFields,
    QgsGeometry,
    QgsLayerTreeGroup,
    QgsPointXY,
)

from .cns import (
    RADIO_LINK_POLICY,
    RADAR_SITE_MONITOR_TYPE_A_POLICY,
    RADAR_SITE_MONITOR_TYPE_B_POLICY,
    slope_contour_levels,
)
from .processor_base import NasfGuidelineProcessorBase

try:
    from ...core.run_log import QgsMessageLog
except ImportError:
    from core.run_log import QgsMessageLog  # type: ignore

PLUGIN_TAG = "SafeguardingBuilder"


class NasfCnsGuidelineMixin(NasfGuidelineProcessorBase):
    def process_cns_building_restricted_areas(
        self,
        cns_facilities_data: List[dict],
        icao_code: str,
        target_crs: QgsCoordinateReferenceSystem,
        layer_group: QgsLayerTreeGroup,
    ) -> bool:
        """Generate CNS building restricted areas using pre-validated data."""
        if not cns_facilities_data:
            QgsMessageLog.logMessage(
                "CNS building restricted areas skipped: no valid CNS facilities provided.",
                PLUGIN_TAG,
                level=Qgis.Info,
            )
            return False
        overall_success = False
        fields = QgsFields(
            [
                QgsField("sourcefacid", QVariant.String),
                QgsField("link_id", QVariant.String),
                QgsField("factype", QVariant.String),
                QgsField("surfname", QVariant.String),
                QgsField("reqheight", QVariant.Double),
                QgsField("guideline", QVariant.String),
                QgsField("shape", QVariant.String),
                QgsField("innerrad_m", QVariant.Double),
                QgsField("outerrad_m", QVariant.Double),
                QgsField("heightrule", QVariant.String),
                QgsField("heightbase", QVariant.String),
                QgsField("minagl_m", QVariant.Double),
                QgsField("maxagl_m", QVariant.Double),
                QgsField("minant_m", QVariant.Double),
                QgsField("heightcmp", QVariant.String),
                QgsField("slope_deg", QVariant.Double),
                QgsField("actionreq", QVariant.String),
                QgsField("condition", QVariant.String),
                QgsField("source_ref", QVariant.String),
                QgsField("guidance", QVariant.String),
            ]
        )

        if self._process_radio_link_areas(cns_facilities_data, icao_code, layer_group, fields):
            overall_success = True
        for monitor_policy in (
            RADAR_SITE_MONITOR_TYPE_A_POLICY,
            RADAR_SITE_MONITOR_TYPE_B_POLICY,
        ):
            if self._process_radar_site_monitor_areas(
                cns_facilities_data, icao_code, layer_group, fields, monitor_policy
            ):
                overall_success = True

        for facility_data in cns_facilities_data:
            facility_id = facility_data.get("id", "N/A")
            facility_type = facility_data.get("type", "Unknown")
            if str(facility_type).strip().casefold() in {
                "radio link",
                RADAR_SITE_MONITOR_TYPE_A_POLICY["MonitorType"].casefold(),
                RADAR_SITE_MONITOR_TYPE_B_POLICY["MonitorType"].casefold(),
            }:
                continue
            facility_geom = facility_data.get("geom")
            facility_elev = facility_data.get("elevation")
            if not facility_geom or not facility_geom.isGeosValid():
                continue
            bra_specs_list = self._active_safeguarding_framework().cns_spec(facility_type)
            if not bra_specs_list:
                continue

            for surface_spec in bra_specs_list:
                try:
                    surface_name = surface_spec.get("SurfaceName", "Unkn")
                    shape_type = surface_spec.get("shape", "Unkn").upper()
                    type_parts = facility_type.split("(")
                    fac_acronym = ""
                    if len(type_parts) > 1 and type_parts[1].strip().endswith(")"):
                        fac_acronym = type_parts[1].strip()[:-1].strip()
                    else:
                        predefined_acronyms = {
                            "NON-DIRECTIONAL BEACON": "NDB",
                            "VHF OMNI-DIRECTIONAL RANGE": "VOR",
                            "DISTANCE MEASURING EQUIPMENT": "DME",
                            "PRIMARY SURVEILLANCE RADAR": "PSR",
                            "SECONDARY SURVEILLANCE RADAR": "SSR",
                            "GROUND BASED AUGMENTATION SYSTEM": "GBAS",
                        }
                        fac_acronym = predefined_acronyms.get(facility_type.upper(), facility_type.split(" ")[0])
                    facility_label = surface_spec.get("FacilityLabel") or fac_acronym or facility_type
                    layer_display_name = f"{facility_label} {surface_name}"
                    fac_identifier = facility_id if facility_id != "N/A" else facility_type.replace(" ", "_")[:10]
                    internal_name_base = f"G_CNS_{icao_code}_{fac_identifier}_{surface_name.replace(' ', '_')}"
                    internal_name_base = "".join(c if c.isalnum() else "_" for c in internal_name_base)
                    surface_geom = self._generate_circular_or_donut(
                        facility_geom,
                        surface_spec,
                        f"{surface_name} for {facility_type} ID {facility_id}",
                    )
                    if not surface_geom:
                        continue
                    height_rule = surface_spec.get("HeightRule", surface_spec.get("heightrule", "TBD"))
                    height_value = surface_spec.get("HeightValue")
                    req_height = self._calculate_cns_height(
                        facility_elev,
                        height_rule,
                        height_value,
                        surface_geom,
                        facility_geom,
                    )
                    feature = QgsFeature(fields)
                    feature.setGeometry(surface_geom)
                    feature.setAttributes(
                        [
                            facility_id,
                            self._radio_link_id(facility_data),
                            facility_type,
                            surface_name,
                            req_height,
                            "G",
                            shape_type,
                            surface_spec.get("InnerRadius_m"),
                            surface_spec.get("OuterRadius_m"),
                            height_rule,
                            surface_spec.get("HeightBasis"),
                            surface_spec.get("MinHeightAGL_m"),
                            surface_spec.get("MaxHeightAGL_m"),
                            surface_spec.get("MinHeightAboveAntenna_m"),
                            surface_spec.get("HeightComparator"),
                            surface_spec.get("SlopeDegrees"),
                            surface_spec.get("ActionRequired"),
                            surface_spec.get("Condition"),
                            surface_spec.get("SourceRef"),
                            surface_spec.get("Guidance"),
                        ]
                    )
                    if shape_type == "CIRCLE":
                        style_key = "CNS Circle Zone"
                    elif shape_type == "DONUT":
                        style_key = "CNS Donut Zone"
                    else:
                        style_key = "Default CNS"
                    layer_created = self._create_and_add_layer(
                        "Polygon",
                        internal_name_base,
                        layer_display_name,
                        fields,
                        [feature],
                        layer_group,
                        style_key,
                    )
                    if layer_created:
                        self._set_cns_field_alias(layer_created, "actionreq", "Action required")
                        overall_success = True
                    if self._create_cns_slope_contours(
                        facility_geom,
                        facility_id,
                        facility_type,
                        surface_spec,
                        internal_name_base,
                        layer_display_name,
                        layer_group,
                    ):
                        overall_success = True
                except Exception as e_spec:
                    QgsMessageLog.logMessage(
                        f"Error processing CNS surface '{surface_name}' for '{facility_type}': {e_spec}",
                        PLUGIN_TAG,
                        level=Qgis.Critical,
                    )

        if not overall_success:
            QgsMessageLog.logMessage(
                "CNS building restricted areas: no CNS layers generated or added.",
                PLUGIN_TAG,
                level=Qgis.Info,
            )
        return overall_success

    def _process_radio_link_areas(
        self,
        facilities: List[dict],
        icao_code: str,
        layer_group: QgsLayerTreeGroup,
        fields: QgsFields,
    ) -> bool:
        """Generate the all-height 30 m corridor for paired radio-link dishes."""
        grouped: dict[str, List[dict]] = {}
        for facility in facilities:
            if str(facility.get("type", "")).strip().casefold() != "radio link":
                continue
            link_id = self._radio_link_id(facility)
            if link_id:
                grouped.setdefault(link_id, []).append(facility)

        created = False
        for link_id, endpoints in sorted(grouped.items()):
            if len(endpoints) != 2:
                QgsMessageLog.logMessage(
                    f"Radio Link '{link_id}' skipped: exactly two endpoints are required.",
                    PLUGIN_TAG,
                    level=Qgis.Warning,
                )
                continue
            try:
                points = []
                for endpoint in endpoints:
                    geometry = endpoint.get("geom")
                    if geometry is None or geometry.isNull() or geometry.isEmpty():
                        raise ValueError("endpoint geometry is missing")
                    point = geometry.asPoint()
                    points.append(QgsPointXY(point.x(), point.y()))
                link_line = QgsGeometry.fromPolylineXY(points)
                corridor = link_line.buffer(float(RADIO_LINK_POLICY["Width_m"]), 36)
                if corridor is None or corridor.isEmpty() or not corridor.isGeosValid():
                    raise ValueError("could not create a valid 30 m corridor")

                feature = QgsFeature(fields)
                feature.setGeometry(corridor)
                feature.setAttributes(
                    [
                        link_id,
                        link_id,
                        "Radio Link",
                        RADIO_LINK_POLICY["SurfaceName"],
                        None,
                        "G",
                        "CORRIDOR",
                        None,
                        RADIO_LINK_POLICY["Width_m"],
                        RADIO_LINK_POLICY["HeightRule"],
                        RADIO_LINK_POLICY["HeightBasis"],
                        None,
                        None,
                        None,
                        None,
                        None,
                        RADIO_LINK_POLICY["ActionRequired"],
                        RADIO_LINK_POLICY["Condition"],
                        RADIO_LINK_POLICY["SourceRef"],
                        RADIO_LINK_POLICY["Guidance"],
                    ]
                )
                safe_link_id = "".join(char if char.isalnum() else "_" for char in link_id)
                layer = self._create_and_add_layer(
                    "Polygon",
                    f"G_CNS_{icao_code}_Radio_Link_{safe_link_id}_Zone_A",
                    f"Radio Link {link_id} Zone A",
                    fields,
                    [feature],
                    layer_group,
                    "Default CNS",
                )
                if layer:
                    self._set_cns_field_alias(layer, "actionreq", "Action required")
                    self._set_cns_field_alias(layer, "link_id", "Link ID")
                    created = True
            except Exception as error:
                QgsMessageLog.logMessage(
                    f"Radio Link '{link_id}' skipped: {error}",
                    PLUGIN_TAG,
                    level=Qgis.Warning,
                )
        return created

    def _process_radar_site_monitor_areas(
        self,
        facilities: List[dict],
        icao_code: str,
        layer_group: QgsLayerTreeGroup,
        fields: QgsFields,
        policy: dict,
    ) -> bool:
        """Generate paired line-of-sight and monitor areas for a radar site-monitor type."""
        monitor_label = policy["MonitorType"]
        monitor_type = policy["MonitorType"].casefold()
        radar_types = {facility_type.casefold() for facility_type in policy["RadarTypes"]}
        grouped: dict[str, List[dict]] = {}
        for facility in facilities:
            link_id = self._radio_link_id(facility)
            if link_id:
                grouped.setdefault(link_id, []).append(facility)

        created = False
        for link_id, endpoints in sorted(grouped.items()):
            monitors = [
                facility
                for facility in endpoints
                if str(facility.get("type", "")).strip().casefold() == monitor_type
            ]
            if not monitors:
                continue
            radars = [
                facility
                for facility in endpoints
                if str(facility.get("type", "")).strip().casefold() in radar_types
            ]
            if len(monitors) != 1 or len(radars) != 1:
                QgsMessageLog.logMessage(
                    f"{monitor_label} '{link_id}' skipped: exactly one monitor and one PSR or SSR endpoint are required.",
                    PLUGIN_TAG,
                    level=Qgis.Warning,
                )
                continue
            try:
                monitor, radar = monitors[0], radars[0]
                monitor_geom = monitor.get("geom")
                radar_geom = radar.get("geom")
                if any(
                    geometry is None or geometry.isNull() or geometry.isEmpty()
                    for geometry in (monitor_geom, radar_geom)
                ):
                    raise ValueError("paired endpoint geometry is missing")
                monitor_point = monitor_geom.asPoint()
                radar_point = radar_geom.asPoint()
                line_of_sight = QgsGeometry.fromPolylineXY(
                    [
                        QgsPointXY(radar_point.x(), radar_point.y()),
                        QgsPointXY(monitor_point.x(), monitor_point.y()),
                    ]
                )
                zone_a = line_of_sight.buffer(float(policy["LineOfSightWidth_m"]), 36)
                zone_b = monitor_geom.buffer(float(policy["ZoneBRadius_m"]), 36)
                if any(
                    geometry is None or geometry.isEmpty() or not geometry.isGeosValid()
                    for geometry in (zone_a, zone_b)
                ):
                    raise ValueError("could not create valid site-monitor geometry")

                monitor_id = monitor.get("id", "N/A")
                safe_link_id = "".join(char if char.isalnum() else "_" for char in link_id)
                safe_monitor_type = "".join(
                    char if char.isalnum() else "_" for char in monitor_label
                )
                zone_definitions = (
                    ("Zone A", zone_a, "CORRIDOR", policy["LineOfSightWidth_m"], policy["ZoneACondition"]),
                    ("Zone B", zone_b, "CIRCLE", policy["ZoneBRadius_m"], policy["ZoneBCondition"]),
                )
                for surface_name, geometry, shape, outer_radius, condition in zone_definitions:
                    feature = QgsFeature(fields)
                    feature.setGeometry(geometry)
                    feature.setAttributes(
                        [
                            monitor_id,
                            link_id,
                            policy["MonitorType"],
                            surface_name,
                            None,
                            "G",
                            shape,
                            None,
                            outer_radius,
                            policy["HeightRule"],
                            policy["HeightBasis"],
                            None,
                            None,
                            None,
                            None,
                            None,
                            policy["ActionRequired"],
                            condition,
                            policy["SourceRef"],
                            policy["Guidance"],
                        ]
                    )
                    layer = self._create_and_add_layer(
                        "Polygon",
                        f"G_CNS_{icao_code}_{safe_monitor_type}_{safe_link_id}_{surface_name.replace(' ', '_')}",
                        f"{monitor_label} {link_id} {surface_name}",
                        fields,
                        [feature],
                        layer_group,
                        "Default CNS",
                    )
                    if layer:
                        self._set_cns_field_alias(layer, "actionreq", "Action required")
                        self._set_cns_field_alias(layer, "link_id", "Link ID")
                        created = True
            except Exception as error:
                QgsMessageLog.logMessage(
                    f"{monitor_label} '{link_id}' skipped: {error}",
                    PLUGIN_TAG,
                    level=Qgis.Warning,
                )
        return created

    @staticmethod
    def _radio_link_id(facility: dict) -> str:
        """Return a Radio Link identifier from current or persisted CNS input."""
        link_id = facility.get("link_id")
        if not link_id and isinstance(facility.get("params"), dict):
            link_id = facility["params"].get("link_id")
        return str(link_id or "").strip()

    def _create_cns_slope_contours(
        self,
        facility_geom: QgsGeometry,
        facility_id: str,
        facility_type: str,
        surface_spec: dict,
        internal_name_base: str,
        layer_display_name: str,
        layer_group: QgsLayerTreeGroup,
    ) -> bool:
        """Create plan-view contour rings for a radial CNS slope surface."""
        primary_interval, intermediate_interval = self._cns_contour_intervals()
        contours = slope_contour_levels(
            surface_spec,
            primary_interval_m=primary_interval,
            intermediate_interval_m=intermediate_interval,
        )
        if not contours:
            return False

        contour_fields = QgsFields(
            [
                QgsField("sourcefacid", QVariant.String),
                QgsField("factype", QVariant.String),
                QgsField("surfname", QVariant.String),
                QgsField("contagl_m", QVariant.Double),
                QgsField("heightbase", QVariant.String),
                QgsField("radius_m", QVariant.Double),
                QgsField("slope_deg", QVariant.Double),
                QgsField("contclass", QVariant.String),
                QgsField("contint_m", QVariant.Double),
                QgsField("primint_m", QVariant.Double),
                QgsField("actionreq", QVariant.String),
                QgsField("source_ref", QVariant.String),
            ]
        )
        features: List[QgsFeature] = []
        for contour in contours:
            ring = facility_geom.buffer(contour["radius_m"], 36)
            if not ring or not ring.isGeosValid():
                ring = ring.makeValid() if ring else None
            if not ring or not ring.isGeosValid():
                continue
            polygon_rings = ring.asPolygon()
            if not polygon_rings:
                continue
            boundary = QgsGeometry.fromPolylineXY(
                [QgsPointXY(point.x(), point.y()) for point in polygon_rings[0]]
            )
            if not boundary or boundary.isEmpty():
                continue
            feature = QgsFeature(contour_fields)
            feature.setGeometry(boundary)
            feature.setAttributes(
                [
                    facility_id,
                    facility_type,
                    surface_spec.get("SurfaceName"),
                    contour["height_agl_m"],
                    surface_spec.get("HeightBasis"),
                    contour["radius_m"],
                    surface_spec.get("SlopeDegrees"),
                    contour["contour_class"],
                    contour["intermediate_interval_m"],
                    contour["primary_interval_m"],
                    surface_spec.get("ActionRequired"),
                    surface_spec.get("SourceRef"),
                ]
            )
            features.append(feature)

        if not features:
            return False
        contour_layer = self._create_and_add_layer(
            "LineString",
            f"{internal_name_base}_Contours",
            f"{layer_display_name} Contours",
            contour_fields,
            features,
            layer_group,
            "CNS Contour",
        )
        self._set_cns_field_alias(contour_layer, "actionreq", "Action required")
        return contour_layer is not None

    def _cns_contour_intervals(self) -> tuple[float, float]:
        """Return positive shared CNS primary and intermediate contour intervals."""
        options = getattr(self, "cns_contour_intervals", {}) or {}
        try:
            primary = float(options.get("primary", 10.0))
        except (AttributeError, TypeError, ValueError):
            primary = 10.0
        try:
            intermediate = float(options.get("intermediate", 5.0))
        except (AttributeError, TypeError, ValueError):
            intermediate = 5.0
        return (
            primary if primary > 0 else 10.0,
            intermediate if intermediate > 0 else 5.0,
        )

    @staticmethod
    def _set_cns_field_alias(layer: Any, field_name: str, field_alias: str) -> None:
        """Apply readable QGIS aliases while preserving portable field names."""
        if layer is None:
            return
        fields = getattr(layer, "fields", None)
        set_alias = getattr(layer, "setFieldAlias", None)
        if not callable(fields) or not callable(set_alias):
            return
        field_index = fields().indexFromName(field_name)
        if field_index >= 0:
            set_alias(field_index, field_alias)

    def _generate_circular_or_donut(
        self, facility_point_geom: QgsGeometry, surface_spec: dict, description: str
    ) -> Optional[QgsGeometry]:
        """Generates a QgsGeometry (Circle or Donut) based on the surface spec."""
        if (
            not facility_point_geom
            or not facility_point_geom.isGeosValid()
            or not facility_point_geom.wkbType()
            in [
                Qgis.WkbType.Point,
                Qgis.WkbType.PointZ,
                Qgis.WkbType.PointM,
                Qgis.WkbType.PointZM,
            ]
        ):
            return None
        shape = surface_spec.get("shape", "").upper()
        outer_radius = surface_spec.get("OuterRadius_m")
        inner_radius = surface_spec.get("InnerRadius_m", 0.0)
        if outer_radius is None or not isinstance(outer_radius, (int, float)) or outer_radius <= 0:
            return None
        if inner_radius is None or not isinstance(inner_radius, (int, float)) or inner_radius < 0:
            inner_radius = 0.0
        buffer_segments = 36
        outer_geom = facility_point_geom.buffer(outer_radius, buffer_segments)
        if not outer_geom or not outer_geom.isGeosValid():
            outer_geom = outer_geom.makeValid() if outer_geom else None
        if not outer_geom or not outer_geom.isGeosValid():
            QgsMessageLog.logMessage(
                f"Error: Invalid outer buffer {outer_radius}m for '{description}'.",
                PLUGIN_TAG,
                level=Qgis.Warning,
            )
            return None
        if shape == "CIRCLE":
            return outer_geom if inner_radius <= 1e-6 else None
        if shape == "DONUT":
            if inner_radius >= outer_radius:
                return None
            if inner_radius <= 1e-6:
                return outer_geom
            inner_geom = facility_point_geom.buffer(inner_radius, buffer_segments)
            if not inner_geom or not inner_geom.isGeosValid():
                inner_geom = inner_geom.makeValid() if inner_geom else None
            if not inner_geom or not inner_geom.isGeosValid():
                QgsMessageLog.logMessage(
                    f"Error: Invalid inner buffer {inner_radius}m for DONUT '{description}'.",
                    PLUGIN_TAG,
                    level=Qgis.Warning,
                )
                return None
            try:
                donut_geom = outer_geom.difference(inner_geom)
                if donut_geom and donut_geom.isGeosValid():
                    return donut_geom
                elif donut_geom:
                    fixed_donut = donut_geom.makeValid()
                    return fixed_donut if fixed_donut and fixed_donut.isGeosValid() else None
                else:
                    return None
            except Exception as e:
                QgsMessageLog.logMessage(
                    f"Error difference DONUT '{description}': {e}",
                    PLUGIN_TAG,
                    level=Qgis.Critical,
                )
                return None
        else:
            QgsMessageLog.logMessage(
                f"Warning: Unknown shape '{shape}' for '{description}'.",
                PLUGIN_TAG,
                level=Qgis.Warning,
            )
            return None

    def _calculate_cns_height(
        self,
        facility_elevation: Optional[float],
        rule: Optional[str],
        value: Any,
        geometry: QgsGeometry,
        facility_geom: QgsGeometry,
    ) -> Optional[float]:
        """Calculates the controlling height for the BRA surface. Placeholder."""
        if facility_elevation is None and rule in ["FacilityElevation + AGL", "Slope"]:
            return None
        try:
            if rule == "TBD" or rule is None:
                return facility_elevation
            elif rule in {
                "All Heights",
                "Maximum Height",
                "Minimum Height",
                "Radial Slope",
                "Below Radial Slope",
                "Does Not Cross Zone Boundary",
                "No Additional Height Limit",
            }:
                # These Guideline G limits are expressed as AGL conditions.
                # A single AMSL value would be misleading without terrain data.
                return None
            elif rule == "FacilityElevation + AGL":
                return facility_elevation + float(value) if value is not None else facility_elevation
            elif rule == "Fixed_AMSL":
                return float(value) if value is not None else None
            elif rule == "Slope":
                QgsMessageLog.logMessage(
                    f"Warning: Slope height rule '{rule}' not implemented.",
                    PLUGIN_TAG,
                    level=Qgis.Warning,
                )
                return facility_elevation
            else:
                QgsMessageLog.logMessage(
                    f"Warning: Unknown height rule '{rule}'.",
                    PLUGIN_TAG,
                    level=Qgis.Warning,
                )
                return None
        except (ValueError, TypeError, Exception) as e:
            QgsMessageLog.logMessage(
                f"Error calculating CNS height (Rule: {rule}, Val: {value}): {e}",
                PLUGIN_TAG,
                level=Qgis.Warning,
            )
            return None
