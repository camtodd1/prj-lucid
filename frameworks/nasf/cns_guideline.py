# -*- coding: utf-8 -*-
"""NASF Guideline G CNS building restricted area processor."""

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
)

from .processor_base import NasfGuidelineProcessorBase

PLUGIN_TAG = "SafeguardingBuilder"


class NasfCnsGuidelineMixin(NasfGuidelineProcessorBase):
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
                    layer_display_name = (
                        f"{fac_acronym} {surface_name}" if fac_acronym else f"{facility_type} {surface_name}"
                    )
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
