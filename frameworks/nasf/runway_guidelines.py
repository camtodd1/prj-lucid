# -*- coding: utf-8 -*-
"""Runway-based safeguarding generators backed by NASF policy parameters."""

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
        psa = framework.public_safety_area_parameters()
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
