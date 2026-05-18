# -*- coding: utf-8 -*-
"""Smaller NASF guideline processors extracted from the main plugin class."""

import math
import traceback
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
    QgsMessageLog,
    QgsPointXY,
)

from .. import cns_dimensions
from .constants import (
    GUIDELINE_B_FAR_EDGE_OFFSET,
    GUIDELINE_B_ZONE_HALF_WIDTH,
    GUIDELINE_B_ZONE_LENGTH_BACKWARD,
    GUIDELINE_C_BUFFER_SEGMENTS,
    GUIDELINE_C_RADIUS_A_M,
    GUIDELINE_C_RADIUS_B_M,
    GUIDELINE_C_RADIUS_C_M,
    GUIDELINE_D_BUFFER_SEGMENTS,
    GUIDELINE_D_TURBINE_RADIUS_M,
    GUIDELINE_I_MOS_REF_VAL,
    GUIDELINE_I_NASF_REF_VAL,
    GUIDELINE_I_PSA_INNER_WIDTH,
    GUIDELINE_I_PSA_LENGTH,
    GUIDELINE_I_PSA_OUTER_WIDTH,
)

PLUGIN_TAG = "SafeguardingBuilder"


class SimpleGuidelinesMixin:
    def process_guideline_a(
        self, runway_data: dict, layer_group: QgsLayerTreeGroup
    ) -> bool:
        """Placeholder for Guideline A: Aircraft Noise processing."""
        QgsMessageLog.logMessage(
            "Guideline A processing not implemented.", PLUGIN_TAG, level=Qgis.Info
        )
        return False

    def process_guideline_b(
        self, runway_data: dict, layer_group: QgsLayerTreeGroup
    ) -> bool:
        """Processes Guideline B: Windshear Assessment Zone."""
        runway_name = runway_data.get(
            "short_name", f"RWY_{runway_data.get('original_index','?')}"
        )
        thr_point = runway_data.get("thr_point")
        rec_thr_point = runway_data.get("rec_thr_point")
        if thr_point is None or rec_thr_point is None or layer_group is None:
            return False
        params = self._get_runway_parameters(thr_point, rec_thr_point)
        if params is None:
            return False

        fields = QgsFields(
            [
                QgsField("rwy_name", QVariant.String),
                QgsField("desc", QVariant.String),
                QgsField("end_desig", QVariant.String),
                QgsField("ref_nasf", QVariant.String),
            ]
        )
        features_to_add = []
        primary_desig, reciprocal_desig = (
            runway_name.split("/") if "/" in runway_name else ("Primary", "Reciprocal")
        )
        try:
            geom_p = self._create_offset_rectangle(
                thr_point,
                params["azimuth_p_r"],
                GUIDELINE_B_FAR_EDGE_OFFSET,
                GUIDELINE_B_ZONE_LENGTH_BACKWARD,
                GUIDELINE_B_ZONE_HALF_WIDTH,
                f"WSZ {primary_desig}",
            )
            if geom_p:
                feat = QgsFeature(fields)
                feat.setGeometry(geom_p)
                feat.setAttributes(
                    [
                        runway_name,
                        "Windshear Assessment Zone",
                        primary_desig,
                        "NASF Guideline B",
                    ]
                )
                features_to_add.append(feat)
        except Exception as e:
            QgsMessageLog.logMessage(
                f"Error WSZ Primary {runway_name}: {e}", PLUGIN_TAG, level=Qgis.Warning
            )
        try:
            geom_r = self._create_offset_rectangle(
                rec_thr_point,
                params["azimuth_r_p"],
                GUIDELINE_B_FAR_EDGE_OFFSET,
                GUIDELINE_B_ZONE_LENGTH_BACKWARD,
                GUIDELINE_B_ZONE_HALF_WIDTH,
                f"WSZ {reciprocal_desig}",
            )
            if geom_r:
                feat = QgsFeature(fields)
                feat.setGeometry(geom_r)
                feat.setAttributes(
                    [
                        runway_name,
                        "Windshear Assessment Zone",
                        reciprocal_desig,
                        "NASF Guideline B",
                    ]
                )
                features_to_add.append(feat)
        except Exception as e:
            QgsMessageLog.logMessage(
                f"Error WSZ Reciprocal {runway_name}: {e}",
                PLUGIN_TAG,
                level=Qgis.Warning,
            )

        layer_created = self._create_and_add_layer(
            "Polygon",
            f"WSZ_{runway_name.replace('/', '_')}",
            f"WSZ {self.tr('RWY')} {runway_name}",
            fields,
            features_to_add,
            layer_group,
            "WSZ Runway",
        )
        return layer_created is not None

    def process_guideline_c(
        self,
        arp_point: QgsPointXY,
        icao_code: str,
        target_crs: QgsCoordinateReferenceSystem,
        layer_group: QgsLayerTreeGroup,
    ) -> bool:
        """Processes Guideline C: Wildlife Management Zone."""
        if not all(
            [arp_point, icao_code, target_crs, target_crs.isValid(), layer_group]
        ):
            return False
        overall_success = False
        try:
            arp_geom = QgsGeometry.fromPointXY(arp_point)
            if arp_geom.isNull():
                return False

            def create_wzm_layer(
                zone: str,
                geom: Optional[QgsGeometry],
                desc: str,
                r_in: float,
                r_out: float,
            ) -> bool:
                if not geom or geom.isEmpty():
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
                        "MOS 17.01(2)",
                        "NASF Guideline C",
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
                return layer is not None

            def circular_ring_points(
                radius_m: float, clockwise: bool = False
            ) -> List[QgsPointXY]:
                segment_count = max(8, GUIDELINE_C_BUFFER_SEGMENTS)
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

            geom_a = create_wzm_geometry(GUIDELINE_C_RADIUS_A_M)
            geom_b = create_wzm_geometry(
                GUIDELINE_C_RADIUS_B_M, GUIDELINE_C_RADIUS_A_M
            )
            geom_c = create_wzm_geometry(
                GUIDELINE_C_RADIUS_C_M, GUIDELINE_C_RADIUS_B_M
            )

            if create_wzm_layer(
                "A",
                geom_a,
                self.tr("Wildlife Management Zone A (0-3km)"),
                0.0,
                GUIDELINE_C_RADIUS_A_M / 1000.0,
            ):
                overall_success = True
            if create_wzm_layer(
                "B",
                geom_b,
                self.tr("Wildlife Management Zone B (3-8km)"),
                GUIDELINE_C_RADIUS_A_M / 1000.0,
                GUIDELINE_C_RADIUS_B_M / 1000.0,
            ):
                overall_success = True
            if create_wzm_layer(
                "C",
                geom_c,
                self.tr("Wildlife Management Zone C (8-13km)"),
                GUIDELINE_C_RADIUS_B_M / 1000.0,
                GUIDELINE_C_RADIUS_C_M / 1000.0,
            ):
                overall_success = True
            return overall_success
        except Exception as e:
            QgsMessageLog.logMessage(
                f"Error Guideline C: {e}", PLUGIN_TAG, level=Qgis.Critical
            )
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

            turbine_zone_geom = arp_geom.buffer(
                GUIDELINE_D_TURBINE_RADIUS_M, GUIDELINE_D_BUFFER_SEGMENTS
            )
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
                    QgsField(
                        "description", QVariant.String, self.tr("Description"), 100
                    ),
                    QgsField(
                        "radius_km", QVariant.Double, self.tr("Radius (km)"), 8, 2
                    ),
                    QgsField(
                        "ref_nasf", QVariant.String, self.tr("Guideline Ref."), 50
                    ),
                ]
            )

            feature = QgsFeature(fields)
            feature.setGeometry(valid_geom)
            feature.setAttributes(
                [
                    icao_code,
                    self.tr("Wind Turbine Assessment Zone (30km Radius)"),
                    GUIDELINE_D_TURBINE_RADIUS_M / 1000.0,
                    self.tr("NASF Guideline D"),
                ]
            )

            layer_display_name = (
                f"{icao_code} {self.tr('Wind Turbine Assessment Zone')}"
            )
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

    def process_guideline_g(
        self,
        cns_facilities_data: List[dict],
        icao_code: str,
        target_crs: QgsCoordinateReferenceSystem,
        layer_group: QgsLayerTreeGroup,
    ) -> bool:
        """Processes Guideline G: CNS Facilities BRAs using pre-validated data."""
        if not cns_facilities_data:
            QgsMessageLog.logMessage(
                "Guideline G skipped: No valid CNS facilities provided.",
                PLUGIN_TAG,
                level=Qgis.Info,
            )
            return False
        overall_success = False
        fields = QgsFields(
            [
                QgsField("sourcefacid", QVariant.String),
                QgsField("factype", QVariant.String),
                QgsField("surfname", QVariant.String),
                QgsField("reqheight", QVariant.Double),
                QgsField("guideline", QVariant.String),
                QgsField("shape", QVariant.String),
                QgsField("innerrad_m", QVariant.Double),
                QgsField("outerrad_m", QVariant.Double),
                QgsField("heightrule", QVariant.String),
            ]
        )

        for facility_data in cns_facilities_data:
            facility_id = facility_data.get("id", "N/A")
            facility_type = facility_data.get("type", "Unknown")
            facility_geom = facility_data.get("geom")
            facility_elev = facility_data.get("elevation")
            if not facility_geom or not facility_geom.isGeosValid():
                continue
            bra_specs_list = cns_dimensions.get_cns_spec(facility_type)
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
                        fac_acronym = predefined_acronyms.get(
                            facility_type.upper(), facility_type.split(" ")[0]
                        )
                    layer_display_name = (
                        f"{fac_acronym} {surface_name}"
                        if fac_acronym
                        else f"{facility_type} {surface_name}"
                    )
                    fac_identifier = (
                        facility_id
                        if facility_id != "N/A"
                        else facility_type.replace(" ", "_")[:10]
                    )
                    internal_name_base = f"G_CNS_{icao_code}_{fac_identifier}_{surface_name.replace(' ', '_')}"
                    internal_name_base = "".join(
                        c if c.isalnum() else "_" for c in internal_name_base
                    )
                    surface_geom = self._generate_circular_or_donut(
                        facility_geom,
                        surface_spec,
                        f"{surface_name} for {facility_type} ID {facility_id}",
                    )
                    if not surface_geom:
                        continue
                    height_rule = surface_spec.get(
                        "HeightRule", surface_spec.get("heightrule", "TBD")
                    )
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
                            facility_type,
                            surface_name,
                            req_height,
                            "G",
                            shape_type,
                            surface_spec.get("InnerRadius_m"),
                            surface_spec.get("OuterRadius_m"),
                            height_rule,
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
                        overall_success = True
                except Exception as e_spec:
                    QgsMessageLog.logMessage(
                        f"Error processing CNS surface '{surface_name}' for '{facility_type}': {e_spec}",
                        PLUGIN_TAG,
                        level=Qgis.Critical,
                    )

        if not overall_success:
            QgsMessageLog.logMessage(
                "Guideline G: No CNS layers generated or added.",
                PLUGIN_TAG,
                level=Qgis.Info,
            )
        return overall_success

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
        if (
            outer_radius is None
            or not isinstance(outer_radius, (int, float))
            or outer_radius <= 0
        ):
            return None
        if (
            inner_radius is None
            or not isinstance(inner_radius, (int, float))
            or inner_radius < 0
        ):
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
                    return (
                        fixed_donut
                        if fixed_donut and fixed_donut.isGeosValid()
                        else None
                    )
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
            elif rule == "FacilityElevation + AGL":
                return (
                    facility_elevation + float(value)
                    if value is not None
                    else facility_elevation
                )
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

    def process_guideline_i(
        self, runway_data: dict, layer_group: QgsLayerTreeGroup
    ) -> bool:
        """Processes Guideline I: Public Safety Area (PSA) Trapezoids."""
        runway_name = runway_data.get(
            "short_name", f"RWY_{runway_data.get('original_index','?')}"
        )
        thr_point = runway_data.get("thr_point")
        rec_thr_point = runway_data.get("rec_thr_point")
        if thr_point is None or rec_thr_point is None or layer_group is None:
            return False
        params = self._get_runway_parameters(thr_point, rec_thr_point)
        if params is None:
            return False
        psa_inner_half_w = GUIDELINE_I_PSA_INNER_WIDTH / 2.0
        psa_outer_half_w = GUIDELINE_I_PSA_OUTER_WIDTH / 2.0
        if psa_inner_half_w < 0 or psa_outer_half_w < 0:
            return False

        fields = QgsFields(
            [
                QgsField("rwy", QVariant.String),
                QgsField("desc", QVariant.String),
                QgsField("end_desig", QVariant.String),
                QgsField("len_m", QVariant.Double),
                QgsField("inner_width", QVariant.Double),
                QgsField("outer_width", QVariant.Double),
                QgsField("ref_mos", QVariant.String),
                QgsField("ref_nasf", QVariant.String),
            ]
        )
        features_to_add = []
        primary_desig, reciprocal_desig = (
            runway_name.split("/") if "/" in runway_name else ("Primary", "Reciprocal")
        )
        try:
            geom_p = self._create_trapezoid(
                thr_point,
                params["azimuth_r_p"],
                GUIDELINE_I_PSA_LENGTH,
                psa_inner_half_w,
                psa_outer_half_w,
                f"PSA {primary_desig}",
            )
            if geom_p:
                feat = QgsFeature(fields)
                feat.setGeometry(geom_p)
                feat.setAttributes(
                    [
                        runway_name,
                        f"Public Safety Area {primary_desig}",
                        primary_desig,
                        GUIDELINE_I_PSA_LENGTH,
                        GUIDELINE_I_PSA_INNER_WIDTH,
                        GUIDELINE_I_PSA_OUTER_WIDTH,
                        GUIDELINE_I_MOS_REF_VAL,
                        GUIDELINE_I_NASF_REF_VAL,
                    ]
                )
                features_to_add.append(feat)
        except Exception as e:
            QgsMessageLog.logMessage(
                f"Error PSA Primary {runway_name}: {e}", PLUGIN_TAG, level=Qgis.Warning
            )
        try:
            geom_r = self._create_trapezoid(
                rec_thr_point,
                params["azimuth_p_r"],
                GUIDELINE_I_PSA_LENGTH,
                psa_inner_half_w,
                psa_outer_half_w,
                f"PSA {reciprocal_desig}",
            )
            if geom_r:
                feat = QgsFeature(fields)
                feat.setGeometry(geom_r)
                feat.setAttributes(
                    [
                        runway_name,
                        f"Public Safety Area {reciprocal_desig}",
                        reciprocal_desig,
                        GUIDELINE_I_PSA_LENGTH,
                        GUIDELINE_I_PSA_INNER_WIDTH,
                        GUIDELINE_I_PSA_OUTER_WIDTH,
                        GUIDELINE_I_MOS_REF_VAL,
                        GUIDELINE_I_NASF_REF_VAL,
                    ]
                )
                features_to_add.append(feat)
        except Exception as e:
            QgsMessageLog.logMessage(
                f"Error PSA Reciprocal {runway_name}: {e}",
                PLUGIN_TAG,
                level=Qgis.Warning,
            )

        layer_created = self._create_and_add_layer(
            "Polygon",
            f"PSA_{runway_name.replace('/', '_')}",
            f"PSA {self.tr('RWY')} {runway_name}",
            fields,
            features_to_add,
            layer_group,
            "PSA Runway",
        )
        return layer_created is not None
