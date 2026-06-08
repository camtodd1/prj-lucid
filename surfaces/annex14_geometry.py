# -*- coding: utf-8 -*-
"""Annex 14 OFS/OES plan-view geometry generation."""

import traceback
from typing import Dict, Iterable, List, Optional

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
        return [
            {
                "end_desig": primary_desig,
                "threshold": runway_data.get("thr_point"),
                "opposite_threshold": runway_data.get("rec_thr_point"),
                "approach_azimuth": rwy_params["azimuth_r_p"],
                "takeoff_azimuth": rwy_params["azimuth_p_r"],
                "takeoff_start": runway_data.get("rec_thr_point"),
                "runway_type": runway_data.get("type1", ""),
                "takeoff_mass_kg": runway_data.get("takeoff_mass_1_kg") or runway_data.get("max_takeoff_mass_kg"),
            },
            {
                "end_desig": reciprocal_desig,
                "threshold": runway_data.get("rec_thr_point"),
                "opposite_threshold": runway_data.get("thr_point"),
                "approach_azimuth": rwy_params["azimuth_p_r"],
                "takeoff_azimuth": rwy_params["azimuth_r_p"],
                "takeoff_start": runway_data.get("thr_point"),
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
    ) -> Optional[QgsGeometry]:
        return self._create_trapezoid(
            start_point,
            azimuth,
            length_m,
            inner_width_m / 2.0,
            outer_width_m / 2.0,
            description,
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
    ) -> None:
        current_start = start_point
        current_width = inner_width_m
        for section in sections:
            length_m = float(section.get("length_m") or 0.0)
            divergence = float(section.get("divergence") or 0.0)
            if length_m <= 0:
                continue
            outer_width = current_width + (2.0 * divergence * length_m)
            geom = self._annex14_trapezoid_from_widths(
                current_start,
                azimuth,
                length_m,
                current_width,
                outer_width,
                f"{surface} {component} {section.get('section')}",
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
            next_start = current_start.project(length_m, azimuth)
            if next_start is None:
                break
            current_start = next_start
            current_width = outer_width

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
        ofs_features: List[QgsFeature] = []
        oes_features: List[QgsFeature] = []
        code_f_no_digital = bool(runway_data.get("code_letter_f_without_digital_avionics", False))

        for end_config in self._annex14_runway_end_configs(runway_data, rwy_params):
            threshold = end_config["threshold"]
            if threshold is None:
                continue
            end_desig = end_config["end_desig"]
            runway_type = end_config["runway_type"]
            approach_az = end_config["approach_azimuth"]
            takeoff_az = end_config["takeoff_azimuth"]

            ofs = ruleset.obstacle_free_surfaces(
                design_group=design_group,
                runway_type=runway_type,
                runway_width_m=runway_data.get("runway_width"),
                code_letter_f_without_digital_avionics=code_f_no_digital,
            )
            approach = next((s for s in ofs["groups"]["general"] if s.get("surface") == "approach"), None)
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

            inner_approach = next((s for s in ofs["groups"]["inner"] if s.get("surface") == "inner_approach"), None)
            if inner_approach and approach:
                start = threshold.project(float(approach["distance_from_threshold_m"]), approach_az)
                if start is not None:
                    geom = self._annex14_trapezoid_from_widths(
                        start,
                        approach_az,
                        float(inner_approach["length_m"]),
                        float(inner_approach["inner_edge_length_m"]),
                        float(inner_approach["inner_edge_length_m"]),
                        f"Annex 14 OFS Inner Approach {end_desig}",
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

            balked = next((s for s in ofs["groups"]["inner"] if s.get("surface") == "balked_landing"), None)
            if balked:
                distance = balked.get("distance_from_threshold_m")
                if distance is not None:
                    start = threshold.project(float(distance), takeoff_az)
                    if start is not None:
                        length_m = 60.0 / float(balked.get("slope") or 1.0)
                        inner_width = float(balked["inner_edge_length_m"])
                        divergence = float(balked["divergence"])
                        outer_width = inner_width + 2.0 * divergence * length_m
                        geom = self._annex14_trapezoid_from_widths(
                            start,
                            takeoff_az,
                            length_m,
                            inner_width,
                            outer_width,
                            f"Annex 14 OFS Balked Landing {end_desig}",
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
                )
            missed = precision["components"]["missed_approach"]
            missed_start = threshold.project(float(missed["distance_after_threshold_m"]), takeoff_az)
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
                )

        straight_in = ruleset.straight_in_instrument_approach_surface_parameters()
        upper = straight_in["upper_section"]
        upper_extension = float(upper["longer_side_length_from_threshold_or_thresholds_m"])
        rect_start = thr_point.project(upper_extension, rwy_params["azimuth_r_p"])
        if rect_start is not None:
            total_len = upper_extension * 2.0 + float(rwy_params["length"])
            geom = self._create_rectangle_from_start(
                rect_start,
                rwy_params["azimuth_p_r"],
                total_len,
                float(upper["shorter_side_length_m"]) / 2.0,
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
            self._annex14_add_polygon_feature(
                oes_features,
                fields,
                geom,
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

                if end_ofs_features:
                    ofs_group = self._annex14_surface_group(layer_group, end_desig, "Obstacle Free Surfaces")
                    for surface, surface_features in self._annex14_features_by_surface(end_ofs_features).items():
                        safe_surface = self._sanitize_filename(surface)
                        surface_label = self._annex14_surface_label(surface)
                        layer = self._create_and_add_layer(
                            "Polygon",
                            f"Annex14_OFS_{runway_name.replace('/', '_')}_{safe_end_desig}_{safe_surface}",
                            f"Annex 14 OFS {surface_label} RWY {end_desig}",
                            fields,
                            surface_features,
                            ofs_group,
                            "OLS Approach",
                        )
                        created = created or layer is not None

                if end_oes_features:
                    oes_group = self._annex14_surface_group(layer_group, end_desig, "Obstacle Evaluation Surfaces")
                    for surface, surface_features in self._annex14_features_by_surface(end_oes_features).items():
                        safe_surface = self._sanitize_filename(surface)
                        surface_label = self._annex14_surface_label(surface)
                        layer = self._create_and_add_layer(
                            "Polygon",
                            f"Annex14_OES_{runway_name.replace('/', '_')}_{safe_end_desig}_{safe_surface}",
                            f"Annex 14 OES {surface_label} RWY {end_desig}",
                            fields,
                            surface_features,
                            oes_group,
                            "OLS TOCS",
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
                        "Polygon",
                        f"Annex14_OES_{runway_name.replace('/', '_')}_{safe_surface}",
                        f"Annex 14 OES {surface_label} RWY {runway_name}",
                        fields,
                        surface_features,
                        runway_wide_group,
                        "OLS TOCS",
                    )
                    created = created or layer is not None
        except Exception as exc:
            QgsMessageLog.logMessage(
                f"Annex 14 geometry failed for {runway_name}: {exc}\n{traceback.format_exc()}",
                PLUGIN_TAG,
                Qgis.Critical,
            )
        return created
