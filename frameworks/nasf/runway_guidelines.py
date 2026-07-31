# -*- coding: utf-8 -*-
"""Runway-based generators dispatched by the active safeguarding profile."""

from qgis.PyQt.QtCore import QVariant  # type: ignore
from qgis.core import (  # type: ignore
    Qgis,
    QgsFeature,
    QgsField,
    QgsFields,
    QgsLayerTreeGroup,
)

from .processor_base import NasfGuidelineProcessorBase

try:
    from ...core.run_log import QgsMessageLog
except ImportError:
    from core.run_log import QgsMessageLog  # type: ignore

PLUGIN_TAG = "SafeguardingBuilder"


class NasfRunwayGuidelinesMixin(NasfGuidelineProcessorBase):
    def process_windshear_safeguarding(self, runway_data: dict, layer_group: QgsLayerTreeGroup) -> bool:
        """Generate building-induced windshear assessment zones."""
        runway_name = runway_data.get("short_name", f"RWY_{runway_data.get('original_index', '?')}")
        thr_point = runway_data.get("thr_point")
        rec_thr_point = runway_data.get("rec_thr_point")
        if thr_point is None or rec_thr_point is None or layer_group is None:
            return False
        params = self._get_runway_parameters(thr_point, rec_thr_point)
        if params is None:
            return False
        framework = self._active_safeguarding_framework()
        windshear = framework.windshear_parameters()

        fields = QgsFields(
            [
                QgsField("rwy_name", QVariant.String),
                QgsField("desc", QVariant.String),
                QgsField("end_desig", QVariant.String),
                QgsField("ref_nasf", QVariant.String),
            ]
        )
        features_to_add = []
        primary_desig, reciprocal_desig = runway_name.split("/") if "/" in runway_name else ("Primary", "Reciprocal")
        try:
            geom_p = self._create_offset_rectangle(
                thr_point,
                params["azimuth_p_r"],
                windshear["far_edge_offset"],
                windshear["zone_length_backward"],
                windshear["zone_half_width"],
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
                        windshear["ref_nasf"],
                    ]
                )
                features_to_add.append(feat)
        except Exception as e:
            QgsMessageLog.logMessage(f"Error WSZ Primary {runway_name}: {e}", PLUGIN_TAG, level=Qgis.Warning)
        try:
            geom_r = self._create_offset_rectangle(
                rec_thr_point,
                params["azimuth_r_p"],
                windshear["far_edge_offset"],
                windshear["zone_length_backward"],
                windshear["zone_half_width"],
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
                        windshear["ref_nasf"],
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

    def process_public_safety_areas(self, runway_data: dict, layer_group: QgsLayerTreeGroup) -> bool:
        """Generate public safety area trapezoids."""
        runway_name = runway_data.get("short_name", f"RWY_{runway_data.get('original_index', '?')}")
        thr_point = runway_data.get("thr_point")
        rec_thr_point = runway_data.get("rec_thr_point")
        if thr_point is None or rec_thr_point is None or layer_group is None:
            return False
        params = self._get_runway_parameters(thr_point, rec_thr_point)
        if params is None:
            return False
        framework = self._active_safeguarding_framework()
        psa = framework.public_safety_area_parameters(
            getattr(self, "safeguarding_options", None)
        )
        if psa.get("model") == "uk_psz_triangles":
            return self._process_uk_public_safety_zones(
                runway_data,
                runway_name,
                thr_point,
                rec_thr_point,
                params,
                psa,
                layer_group,
            )
        psa_length = psa["length"]
        psa_inner_width = psa["inner_width"]
        psa_outer_width = psa["outer_width"]
        psa_inner_half_w = psa_inner_width / 2.0
        psa_outer_half_w = psa_outer_width / 2.0
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
        primary_desig, reciprocal_desig = runway_name.split("/") if "/" in runway_name else ("Primary", "Reciprocal")
        try:
            geom_p = self._create_trapezoid(
                thr_point,
                params["azimuth_r_p"],
                psa_length,
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
                        psa_length,
                        psa_inner_width,
                        psa_outer_width,
                        psa["mos_ref"],
                        psa["nasf_ref"],
                    ]
                )
                features_to_add.append(feat)
        except Exception as e:
            QgsMessageLog.logMessage(f"Error PSA Primary {runway_name}: {e}", PLUGIN_TAG, level=Qgis.Warning)
        try:
            geom_r = self._create_trapezoid(
                rec_thr_point,
                params["azimuth_p_r"],
                psa_length,
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
                        psa_length,
                        psa_inner_width,
                        psa_outer_width,
                        psa["mos_ref"],
                        psa["nasf_ref"],
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

    def _process_uk_public_safety_zones(
        self,
        runway_data: dict,
        runway_name: str,
        thr_point,
        rec_thr_point,
        params: dict,
        psz: dict,
        layer_group: QgsLayerTreeGroup,
    ) -> bool:
        """Generate explicitly enabled indicative DfT PSRZ and PSCZ triangles."""
        if not psz.get("enabled"):
            return False
        primary_desig, reciprocal_desig = (
            runway_name.split("/")
            if "/" in runway_name
            else ("Primary", "Reciprocal")
        )
        boolean_parser = getattr(self, "_bool_from_runway_data", None)

        def landing_available(value) -> bool:
            if callable(boolean_parser):
                return bool(boolean_parser(value))
            if isinstance(value, str):
                return value.strip().casefold() not in {"", "0", "false", "no", "off"}
            return bool(value)

        runway_ends = tuple(
            runway_end
            for runway_end, available in (
                (
                    (primary_desig, thr_point, params["azimuth_r_p"]),
                    landing_available(runway_data.get("landing_available_1", True)),
                ),
                (
                    (reciprocal_desig, rec_thr_point, params["azimuth_p_r"]),
                    landing_available(runway_data.get("landing_available_2", True)),
                ),
            )
            if available
        )
        if not runway_ends:
            return False
        overall_success = False
        for zone in psz["zones"]:
            length_m = float(zone["length_m"])
            if length_m <= 0:
                continue
            threshold_half_width = float(zone["threshold_half_width_m"])
            distal_half_width = float(zone["distal_half_width_m"])
            fields = QgsFields(
                [
                    QgsField("rwy", QVariant.String),
                    QgsField("desc", QVariant.String),
                    QgsField("end_desig", QVariant.String),
                    QgsField("zone_code", QVariant.String),
                    QgsField("len_m", QVariant.Double),
                    QgsField("thr_half_w", QVariant.Double),
                    QgsField("dist_half_w", QVariant.Double),
                    QgsField("family_id", QVariant.String),
                    QgsField("profile_id", QVariant.String),
                    QgsField("source_id", QVariant.String),
                    QgsField("source_version", QVariant.String),
                    QgsField("authority_level", QVariant.String),
                    QgsField("applicability", QVariant.String),
                    QgsField("geometry_status", QVariant.String),
                    QgsField("assessment_result", QVariant.String),
                    QgsField("caveat", QVariant.String, "", 500),
                ]
            )
            features = []
            for end_designator, threshold, outward_azimuth in runway_ends:
                try:
                    geometry = self._create_trapezoid(
                        threshold,
                        outward_azimuth,
                        length_m,
                        threshold_half_width,
                        distal_half_width,
                        f"{zone['zone_code']} {end_designator}",
                    )
                    if geometry is None:
                        continue
                    feature = QgsFeature(fields)
                    feature.setGeometry(geometry)
                    feature.setAttributes(
                        [
                            runway_name,
                            zone["description"],
                            end_designator,
                            zone["zone_code"],
                            length_m,
                            threshold_half_width,
                            distal_half_width,
                            zone["family_id"],
                            zone["profile_id"],
                            psz["source_id"],
                            psz["source_version"],
                            psz["authority_level"],
                            psz["applicability"],
                            psz["geometry_status"],
                            psz["assessment_result"],
                            psz["caveat"],
                        ]
                    )
                    features.append(feature)
                except Exception as error:
                    QgsMessageLog.logMessage(
                        f"Error generating {zone['zone_code']} {end_designator} for {runway_name}: {error}",
                        PLUGIN_TAG,
                        level=Qgis.Warning,
                    )
            layer = self._create_and_add_layer(
                "Polygon",
                f"UK_{zone['zone_code']}_{runway_name.replace('/', '_')}",
                f"{zone['zone_code']} {self.tr('RWY')} {runway_name}",
                fields,
                features,
                layer_group,
                f"UK {zone['zone_code']}",
            )
            overall_success = overall_success or layer is not None
        return overall_success
