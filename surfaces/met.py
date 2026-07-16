# -*- coding: utf-8 -*-
"""Meteorological instrument station surface generation."""

from typing import List, Optional, Tuple

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
    QgsVectorLayer,
)

try:
    from ..core.run_log import QgsMessageLog
except ImportError:
    from core.run_log import QgsMessageLog  # type: ignore

PLUGIN_TAG = "SafeguardingBuilder"


class MetSurfacesMixin:
    def process_met_station_surfaces(
        self,
        met_point_proj_crs: QgsPointXY,
        icao_code: str,
        target_crs: QgsCoordinateReferenceSystem,
        layer_group: QgsLayerTreeGroup,
    ) -> Tuple[bool, List[QgsVectorLayer]]:
        """Generates MET station layers (point, enclosure, buffers)."""
        any_layer_ok = False
        enclosure_geom: Optional[QgsGeometry] = None
        met_geom_target_crs = QgsGeometry.fromPointXY(met_point_proj_crs)
        if met_geom_target_crs.isNull():
            return False, []

        try:
            fields = QgsFields()
            fields.append(QgsField("desc", QVariant.String))
            fields.append(QgsField("coord_east", QVariant.Double))
            fields.append(QgsField("coord_north", QVariant.Double))
            fields.append(QgsField("elev_m", QVariant.Double))
            fields.append(QgsField("ref_mos", QVariant.String, "MOS Reference", 20))

            feat = QgsFeature(fields)
            feat.setGeometry(met_geom_target_crs)
            feat.setAttributes(
                [
                    self.tr("MET Station Location"),
                    met_point_proj_crs.x(),
                    met_point_proj_crs.y(),
                    0.0,
                    "MOS 19.17",
                ]
            )
            if self._create_and_add_layer(
                "Point",
                f"met_loc_{icao_code}",
                self.tr("MET Station Location"),
                fields,
                [feat],
                layer_group,
                "MET Station Location",
            ):
                any_layer_ok = True
        except Exception as e:
            QgsMessageLog.logMessage(f"Error MET Point: {e}", PLUGIN_TAG, level=Qgis.Critical)

        try:
            side = 16.0
            name = self.tr("MET Instrument Enclosure")
            geom = self._create_centered_oriented_square(met_point_proj_crs, side, name)
            if geom:
                enclosure_geom = geom
                fields = QgsFields(
                    [
                        QgsField("desc", QVariant.String),
                        QgsField("coord_east", QVariant.Double),
                        QgsField("coord_north", QVariant.Double),
                        QgsField("side_m", QVariant.Double),
                        QgsField("ref_mos", QVariant.String, "MOS Reference", 20),
                    ]
                )
                feat = QgsFeature(fields)
                feat.setGeometry(geom)
                feat.setAttributes(
                    [
                        "MET Instrument Enclosure",
                        met_point_proj_crs.x(),
                        met_point_proj_crs.y(),
                        side,
                        "MOS 19.18(2)(a)",
                    ]
                )
            if self._create_and_add_layer(
                "Polygon",
                f"met_enc_{icao_code}",
                name,
                fields,
                [feat],
                layer_group,
                "MET Instrument Enclosure",
            ):
                any_layer_ok = True
        except Exception as e:
            QgsMessageLog.logMessage(f"Error MET Enclosure: {e}", PLUGIN_TAG, level=Qgis.Critical)

        try:
            side = 30.0
            name = self.tr("MET Buffer Zone")
            geom = self._create_centered_oriented_square(met_point_proj_crs, side, name)
            if geom:
                fields = QgsFields(
                    [
                        QgsField("desc", QVariant.String),
                        QgsField("coord_east", QVariant.Double),
                        QgsField("coord_north", QVariant.Double),
                        QgsField("side_m", QVariant.Double),
                        QgsField("ref_mos", QVariant.String, "MOS Reference", 20),
                    ]
                )
                feat = QgsFeature(fields)
                feat.setGeometry(geom)
                feat.setAttributes(
                    [
                        "MET Buffer Zone",
                        met_point_proj_crs.x(),
                        met_point_proj_crs.y(),
                        side,
                        "MOS 19.18(2)(a)",
                    ]
                )
            if self._create_and_add_layer(
                "Polygon",
                f"met_buf_{icao_code}",
                name,
                fields,
                [feat],
                layer_group,
                "MET Buffer Zone",
            ):
                any_layer_ok = True
        except Exception as e:
            QgsMessageLog.logMessage(f"Error MET Buffer: {e}", PLUGIN_TAG, level=Qgis.Critical)

        if enclosure_geom:
            try:
                dist = 80.0
                name = self.tr("MET Obstacle Buffer Zone")
                buffered_geom = enclosure_geom.buffer(dist, 12)
                buffered_geom = (
                    buffered_geom.makeValid() if buffered_geom and not buffered_geom.isGeosValid() else buffered_geom
                )
                if buffered_geom and not buffered_geom.isEmpty():
                    fields = QgsFields(
                        [
                            QgsField("desc", QVariant.String),
                            QgsField("coord_east", QVariant.Double),
                            QgsField("coord_north", QVariant.Double),
                            QgsField("buffer_m", QVariant.Double),
                            QgsField("ref_mos", QVariant.String, "MOS Reference", 20),
                        ]
                    )
                    feat = QgsFeature(fields)
                    feat.setGeometry(buffered_geom)
                    feat.setAttributes(
                        [
                            "MET Obstacle Buffer Zone",
                            met_point_proj_crs.x(),
                            met_point_proj_crs.y(),
                            dist,
                            "MOS 19.18(2)(a)",
                        ]
                    )
                if self._create_and_add_layer(
                    "Polygon",
                    f"met_obs_{icao_code}",
                    name,
                    fields,
                    [feat],
                    layer_group,
                    "MET Obstacle Buffer Zone",
                ):
                    any_layer_ok = True
            except Exception as e:
                QgsMessageLog.logMessage(
                    f"Error MET Obstruction Buffer: {e}",
                    PLUGIN_TAG,
                    level=Qgis.Critical,
                )

        return any_layer_ok, []
