# -*- coding: utf-8 -*-
"""Derived comparison products for current and modernised OLS envelopes."""

import math
from typing import Dict, List, Optional, Sequence, Tuple

from qgis.PyQt.QtCore import QVariant  # type: ignore
from qgis.core import (  # type: ignore
    Qgis,
    QgsFeature,
    QgsField,
    QgsFields,
    QgsGeometry,
    QgsMessageLog,
    QgsPointXY,
)

from .controlling_ols_engine import ControllingOlsCandidate, PlanarControllingOlsEngine

PLUGIN_TAG = "SafeguardingBuilder"
COMPARISON_TOLERANCE_M = 0.01
COMPARISON_MIN_AREA_M2 = 0.01


class OlsEnvelopeComparisonEngine:
    """Compare two already-solved lower envelopes over their common domain."""

    def __init__(
        self,
        baseline_engine: PlanarControllingOlsEngine,
        future_engine: PlanarControllingOlsEngine,
        tolerance_m: float = COMPARISON_TOLERANCE_M,
    ):
        self.baseline_engine = baseline_engine
        self.future_engine = future_engine
        self.tolerance_m = max(0.0, float(tolerance_m))

    def comparison_parts(
        self,
    ) -> Dict[str, List[Tuple[ControllingOlsCandidate, ControllingOlsCandidate, QgsGeometry]]]:
        """Return gain/loss polygons attributed to their two controlling surfaces."""
        result = {"gain": [], "loss": []}
        baseline_regions = self.baseline_engine._controlling_region_geometries()
        future_regions = self.future_engine._controlling_region_geometries()

        for baseline_candidate, baseline_region in baseline_regions:
            for future_candidate, future_region in future_regions:
                if not self._bounding_boxes_intersect(baseline_region, future_region):
                    continue
                try:
                    overlap = baseline_region.intersection(future_region)
                except Exception:
                    continue
                if not self._has_area(overlap):
                    continue

                pair_engine = PlanarControllingOlsEngine([baseline_candidate, future_candidate])
                # A higher future surface is a gain, so the baseline is the lower
                # candidate on the gain side of the equality boundary.
                baseline_lower = pair_engine._candidate_lower_region(
                    baseline_candidate,
                    future_candidate,
                    overlap,
                )
                if baseline_lower is None:
                    self._append_sampled_whole_overlap(
                        result, baseline_candidate, future_candidate, overlap
                    )
                    continue
                try:
                    if baseline_lower.isEmpty():
                        future_lower = QgsGeometry(overlap)
                    else:
                        baseline_lower = pair_engine._clip_lower_region_to_overlap(baseline_lower, overlap)
                        if baseline_lower is None:
                            raise ValueError("comparison lower region could not be clipped")
                        future_lower = overlap.difference(baseline_lower)
                except Exception:
                    self._append_sampled_whole_overlap(
                        result, baseline_candidate, future_candidate, overlap
                    )
                    continue

                self._append_parts(result["gain"], baseline_candidate, future_candidate, baseline_lower, "gain")
                self._append_parts(result["loss"], baseline_candidate, future_candidate, future_lower, "loss")
        return result

    def delta_range(
        self,
        geometry: QgsGeometry,
        baseline_candidate: ControllingOlsCandidate,
        future_candidate: ControllingOlsCandidate,
    ) -> Tuple[Optional[float], Optional[float], Optional[float]]:
        values: List[float] = []
        for point in self._sample_points(geometry):
            baseline_z = baseline_candidate.elevation_at_xy(point)
            future_z = future_candidate.elevation_at_xy(point)
            if baseline_z is None or future_z is None:
                continue
            delta = float(future_z) - float(baseline_z)
            if math.isfinite(delta):
                values.append(delta)
        if not values:
            return None, None, None
        # The first sample is pointOnSurface(), giving a stable representative
        # value without presenting a vertex sample as an area-weighted mean.
        return min(values), max(values), values[0]

    def _append_sampled_whole_overlap(self, result, baseline, future, overlap) -> None:
        delta_min, delta_max, delta_representative = self.delta_range(overlap, baseline, future)
        if delta_representative is None:
            return
        if delta_min is not None and delta_min > self.tolerance_m:
            self._append_parts(result["gain"], baseline, future, overlap, "gain")
        elif delta_max is not None and delta_max < -self.tolerance_m:
            self._append_parts(result["loss"], baseline, future, overlap, "loss")

    def _append_parts(self, destination, baseline, future, geometry, change: str) -> None:
        if geometry is None or geometry.isEmpty():
            return
        for part in self.baseline_engine._polygon_parts(geometry):
            if not self._has_area(part):
                continue
            delta_min, delta_max, delta_representative = self.delta_range(part, baseline, future)
            if delta_representative is None:
                continue
            if change == "gain" and delta_representative <= self.tolerance_m:
                continue
            if change == "loss" and delta_representative >= -self.tolerance_m:
                continue
            destination.append((baseline, future, QgsGeometry(part)))

    def _sample_points(self, geometry: QgsGeometry) -> List[QgsPointXY]:
        points: List[QgsPointXY] = []
        try:
            representative = geometry.pointOnSurface()
            if representative is not None and not representative.isEmpty():
                point = representative.asPoint()
                points.append(QgsPointXY(point.x(), point.y()))
        except Exception:
            pass
        try:
            vertices = list(geometry.vertices())
            if len(vertices) > 48:
                step = max(1, len(vertices) // 48)
                vertices = vertices[::step]
            points.extend(QgsPointXY(vertex.x(), vertex.y()) for vertex in vertices)
        except Exception:
            pass
        return points

    @staticmethod
    def _bounding_boxes_intersect(first: QgsGeometry, second: QgsGeometry) -> bool:
        try:
            return first.boundingBox().intersects(second.boundingBox())
        except Exception:
            return True

    @staticmethod
    def _has_area(geometry: Optional[QgsGeometry]) -> bool:
        return bool(
            geometry is not None
            and not geometry.isEmpty()
            and geometry.area() > COMPARISON_MIN_AREA_M2
        )


class OlsModernisationComparisonMixin:
    """Create user-facing OFS/OES modernisation comparison layers."""

    def _create_ols_modernisation_comparison_layers(
        self,
        icao_code: str,
        baseline_ruleset_id: str,
        baseline_candidates: Sequence[ControllingOlsCandidate],
        baseline_exclusions: Sequence[QgsGeometry],
        future_candidates: Sequence[ControllingOlsCandidate],
        ofs_group,
        oes_group,
    ) -> bool:
        baseline_planar = [
            candidate for candidate in baseline_candidates
            if candidate.model in {"constant", "axis", "plane", "conical"}
        ]
        if not baseline_planar:
            QgsMessageLog.logMessage(
                "[skip] OLS modernisation comparison: baseline has no controlling candidates.",
                PLUGIN_TAG,
                Qgis.Warning,
            )
            return False

        baseline_engine = PlanarControllingOlsEngine(
            baseline_planar,
            exclusion_geometries=list(baseline_exclusions or []),
        )
        created = False
        for family, family_group in (("OFS", ofs_group), ("OES", oes_group)):
            family_candidates = [
                candidate for candidate in future_candidates
                if candidate.model in {"constant", "axis", "plane", "conical"}
                and str((candidate.metadata or {}).get("annex14_family") or "").upper() == family
            ]
            if not family_candidates or family_group is None:
                QgsMessageLog.logMessage(
                    f"[skip] OLS modernisation {family} comparison: no future candidates.",
                    PLUGIN_TAG,
                    Qgis.Warning,
                )
                continue
            future_engine = PlanarControllingOlsEngine(family_candidates)
            comparison = OlsEnvelopeComparisonEngine(baseline_engine, future_engine)
            parts = comparison.comparison_parts()
            gain_name = "Height Gain" if family == "OFS" else "Trigger Height Raised"
            loss_name = "Height Loss" if family == "OFS" else "Trigger Height Lowered"
            created = self._create_modernisation_change_layer(
                icao_code, baseline_ruleset_id, family, "gain", gain_name,
                parts["gain"], comparison, family_group,
            ) or created
            created = self._create_modernisation_change_layer(
                icao_code, baseline_ruleset_id, family, "loss", loss_name,
                parts["loss"], comparison, family_group,
            ) or created
        return created

    def _create_modernisation_change_layer(
        self,
        icao_code,
        baseline_ruleset_id,
        family,
        change,
        display_name,
        parts,
        comparison,
        output_group,
    ) -> bool:
        fields = QgsFields([
            QgsField("change", QVariant.String, self.tr("Change"), 24),
            QgsField("future_family", QVariant.String, self.tr("Future Family"), 8),
            QgsField("delta_min_m", QVariant.Double, self.tr("Minimum Change (m)"), 12, 3),
            QgsField("delta_max_m", QVariant.Double, self.tr("Maximum Change (m)"), 12, 3),
            QgsField("delta_rep_m", QVariant.Double, self.tr("Representative Change (m)"), 12, 3),
            QgsField("baseline_ruleset", QVariant.String, self.tr("Baseline Ruleset"), 80),
            QgsField("baseline_id", QVariant.String, self.tr("Baseline Surface ID"), 160),
            QgsField("baseline_surface", QVariant.String, self.tr("Baseline Surface"), 50),
            QgsField("future_id", QVariant.String, self.tr("Future Surface ID"), 160),
            QgsField("future_surface", QVariant.String, self.tr("Future Surface"), 50),
            QgsField("meaning", QVariant.String, self.tr("Regulatory Meaning"), 160),
        ])
        features: List[QgsFeature] = []
        if family == "OFS":
            meaning = (
                "Future obstacle-free reference surface is higher than baseline"
                if change == "gain"
                else "Future obstacle-free reference surface is lower than baseline"
            )
        else:
            meaning = (
                "Future aeronautical-study trigger is raised; this is not an approval limit"
                if change == "gain"
                else "Future aeronautical-study trigger is lowered; this is not an approval limit"
            )
        for baseline, future, geometry in parts:
            delta_min, delta_max, delta_representative = comparison.delta_range(geometry, baseline, future)
            feature = QgsFeature(fields)
            feature.setGeometry(geometry)
            feature.setAttributes([
                change,
                family,
                delta_min,
                delta_max,
                delta_representative,
                baseline_ruleset_id,
                baseline.surface_id,
                baseline.surface_type,
                future.surface_id,
                future.surface_type,
                meaning,
            ])
            features.append(feature)
        layer = self._create_and_add_layer(
            "MultiPolygon",
            f"OLS_Modernisation_{family}_{change}_{icao_code}",
            display_name,
            fields,
            features,
            output_group,
            "OLS Modernisation Gain" if change == "gain" else "OLS Modernisation Loss",
        )
        return layer is not None


__all__ = ["OlsEnvelopeComparisonEngine", "OlsModernisationComparisonMixin"]
