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
    QgsWkbTypes,
)

from .controlling_ols_engine import ControllingOlsCandidate, PlanarControllingOlsEngine

PLUGIN_TAG = "SafeguardingBuilder"
COMPARISON_TOLERANCE_M = 0.01
COMPARISON_MIN_AREA_M2 = 0.01
COMPARISON_NO_OVERLAY_COVERAGE_TOLERANCE_M = 0.5
COMPARISON_NO_OVERLAY_MIN_AREA_M2 = 5.0
COMPARISON_NO_OVERLAY_GRID_M = 0.001
COMPARISON_SPIKE_ANGLE_DEGREES = 12.0
COMPARISON_SPIKE_DETOUR_RATIO = 1.8
COMPARISON_SPIKE_BASE_MAX_M = 175.0
COMPARISON_SPIKE_HEIGHT_MIN_M = 25.0
COMPARISON_SEVERE_SPIKE_DETOUR_RATIO = 8.0
COMPARISON_SEVERE_SPIKE_ANGLE_DEGREES = 15.0
COMPARISON_SPIKE_MAX_AREA_CHANGE_RATIO = 0.01
COMPARISON_SPIKE_MAX_AREA_CHANGE_M2 = 25.0
COMPARISON_DELTA_DECIMALS = 3


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
        """Return gain/loss/no-change polygons and transition lines for the common domain."""
        result = {"gain": [], "loss": [], "no_change": [], "transition": []}
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

                if self._append_no_change_if_equal(
                    result["no_change"],
                    baseline_candidate,
                    future_candidate,
                    overlap,
                ):
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
                self._append_parts(
                    result["no_change"],
                    baseline_candidate,
                    future_candidate,
                    baseline_lower,
                    "no_change",
                )
                self._append_parts(
                    result["no_change"],
                    baseline_candidate,
                    future_candidate,
                    future_lower,
                    "no_change",
                )
                self._append_transition_parts(
                    result["transition"],
                    pair_engine,
                    baseline_candidate,
                    future_candidate,
                    overlap,
                    baseline_lower,
                    future_lower,
                )
        self._append_common_domain_gap_parts(result, baseline_regions, future_regions)
        self._finalise_comparison_parts(result)
        return result

    def baseline_only_parts(self) -> List[Tuple[ControllingOlsCandidate, QgsGeometry]]:
        """Return baseline controlling regions outside the future envelope."""
        result: List[Tuple[ControllingOlsCandidate, QgsGeometry]] = []
        future_regions = [region for _, region in self.future_engine._controlling_region_geometries()]
        future_union = self._union_geometries(future_regions)
        future_coverage = self._comparison_coverage_geometry(future_union)
        for baseline_candidate, baseline_region in self.baseline_engine._controlling_region_geometries():
            if future_union is None or future_union.isEmpty():
                remaining = QgsGeometry(baseline_region)
                tolerant_remaining = QgsGeometry(baseline_region)
            else:
                try:
                    remaining = baseline_region.difference(future_union)
                except Exception:
                    continue
                try:
                    tolerant_remaining = (
                        baseline_region.difference(future_coverage)
                        if future_coverage is not None and not future_coverage.isEmpty()
                        else QgsGeometry(remaining)
                    )
                except Exception:
                    tolerant_remaining = QgsGeometry(remaining)
            remaining = self._normalise_no_overlay_geometry(remaining)
            tolerant_remaining = self._normalise_no_overlay_geometry(tolerant_remaining)
            for part in self.baseline_engine._polygon_parts(remaining):
                if not self._no_overlay_part_has_tolerant_core(part, tolerant_remaining):
                    continue
                part = self._clean_no_overlay_part(part)
                if self._has_no_overlay_area(part):
                    result.append((baseline_candidate, QgsGeometry(part)))
        return result

    def delta_range(
        self,
        geometry: QgsGeometry,
        baseline_candidate: ControllingOlsCandidate,
        future_candidate: ControllingOlsCandidate,
        change: Optional[str] = None,
    ) -> Tuple[Optional[float], Optional[float], Optional[float]]:
        values: List[float] = []
        for point in self._sample_points(geometry, baseline_candidate, future_candidate, change):
            baseline_z = baseline_candidate.elevation_at_xy(point)
            future_z = future_candidate.elevation_at_xy(point)
            if baseline_z is None or future_z is None:
                continue
            delta = float(future_z) - float(baseline_z)
            if math.isfinite(delta):
                values.append(self._round_delta(delta))
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
        elif (
            delta_min is not None
            and delta_max is not None
            and abs(delta_min) <= self.tolerance_m
            and abs(delta_max) <= self.tolerance_m
        ):
            self._append_parts(result["no_change"], baseline, future, overlap, "no_change")

    def _append_no_change_if_equal(self, destination, baseline, future, overlap) -> bool:
        delta_min, delta_max, _delta_representative = self.delta_range(overlap, baseline, future)
        if delta_min is None or delta_max is None:
            return False
        if abs(delta_min) > self.tolerance_m or abs(delta_max) > self.tolerance_m:
            return False
        self._append_parts(destination, baseline, future, overlap, "no_change")
        return True

    def _append_parts(
        self,
        destination,
        baseline,
        future,
        geometry,
        change: str,
        clean_spikes: bool = True,
    ) -> None:
        if geometry is None or geometry.isEmpty():
            return
        for part in self.baseline_engine._polygon_parts(geometry):
            if not self._has_area(part):
                continue
            if clean_spikes:
                part = self._clean_comparison_part(part, baseline, future, change)
            if not self._has_area(part):
                continue
            delta_min, delta_max, delta_representative = self.delta_range(part, baseline, future, change)
            if delta_representative is None:
                continue
            if change == "gain":
                if delta_representative <= self.tolerance_m:
                    continue
            if change == "loss":
                if delta_representative >= -self.tolerance_m:
                    continue
            if change == "no_change":
                if delta_min is None or delta_max is None:
                    continue
                if abs(delta_min) > self.tolerance_m or abs(delta_max) > self.tolerance_m:
                    continue
            destination.append((baseline, future, QgsGeometry(part)))

    def _append_transition_parts(
        self,
        destination,
        pair_engine,
        baseline,
        future,
        overlap,
        gain_geometry,
        loss_geometry,
    ) -> None:
        if (
            gain_geometry is None
            or gain_geometry.isEmpty()
            or loss_geometry is None
            or loss_geometry.isEmpty()
        ):
            return
        try:
            boundary = pair_engine._equality_line_for_pair(overlap, baseline, future)
        except Exception:
            boundary = None
        if boundary is None or boundary.isEmpty():
            try:
                boundary = gain_geometry.boundary().intersection(loss_geometry.boundary())
            except Exception:
                return
        if boundary is None or boundary.isEmpty():
            return
        for part in self._line_parts(boundary):
            try:
                if part.length() > 0.01:
                    destination.append((baseline, future, QgsGeometry(part)))
            except Exception:
                continue

    def _append_common_domain_gap_parts(
        self,
        result,
        baseline_regions: Sequence[Tuple[ControllingOlsCandidate, QgsGeometry]],
        future_regions: Sequence[Tuple[ControllingOlsCandidate, QgsGeometry]],
    ) -> None:
        baseline_union = self._union_geometries([geometry for _candidate, geometry in baseline_regions])
        future_union = self._union_geometries([geometry for _candidate, geometry in future_regions])
        if baseline_union is None or future_union is None or baseline_union.isEmpty() or future_union.isEmpty():
            return
        try:
            common_domain = baseline_union.intersection(future_union)
        except Exception:
            return
        if not self._has_area(common_domain):
            return

        classified_geometries = [
            geometry
            for change in ("gain", "loss", "no_change")
            for _baseline, _future, geometry in result.get(change, [])
            if geometry is not None and not geometry.isEmpty()
        ]
        classified_union = self._union_geometries(classified_geometries)
        if classified_union is None or classified_union.isEmpty():
            remainder = common_domain
        else:
            try:
                remainder = common_domain.difference(classified_union)
            except Exception:
                return
        if not self._has_area(remainder):
            return

        for part in self.baseline_engine._polygon_parts(remainder):
            if not self._has_area(part):
                continue
            controllers = self._controllers_for_gap_part(part)
            if controllers is None:
                continue
            baseline_candidate, future_candidate = controllers
            change = self._classify_change_for_part(part, baseline_candidate, future_candidate)
            if change is None:
                continue
            self._append_parts(
                result[change],
                baseline_candidate,
                future_candidate,
                part,
                change,
                clean_spikes=False,
            )

    def _finalise_comparison_parts(self, result) -> None:
        """Apply final geometry hygiene after gap repair has finished."""
        for change in ("gain", "loss", "no_change"):
            final_parts = []
            for baseline, future, geometry in result.get(change, []):
                cleaned = self._clean_comparison_part(geometry, baseline, future, change)
                if not self._has_area(cleaned):
                    continue
                delta_min, delta_max, delta_representative = self.delta_range(
                    cleaned,
                    baseline,
                    future,
                    change,
                )
                if delta_representative is None:
                    continue
                if change == "gain" and delta_representative <= self.tolerance_m:
                    continue
                if change == "loss" and delta_representative >= -self.tolerance_m:
                    continue
                if change == "no_change":
                    if delta_min is None or delta_max is None:
                        continue
                    if abs(delta_min) > self.tolerance_m or abs(delta_max) > self.tolerance_m:
                        continue
                final_parts.append((baseline, future, cleaned))
            result[change] = final_parts

    def _controllers_for_gap_part(
        self,
        geometry: QgsGeometry,
    ) -> Optional[Tuple[ControllingOlsCandidate, ControllingOlsCandidate]]:
        for point in self._sample_points(geometry):
            baseline = self.baseline_engine.controlling_candidate_at_xy(point)
            future = self.future_engine.controlling_candidate_at_xy(point)
            if baseline is not None and future is not None:
                return baseline[0], future[0]
        return None

    def _classify_change_for_part(
        self,
        geometry: QgsGeometry,
        baseline_candidate: ControllingOlsCandidate,
        future_candidate: ControllingOlsCandidate,
    ) -> Optional[str]:
        delta_min, delta_max, delta_representative = self.delta_range(
            geometry,
            baseline_candidate,
            future_candidate,
        )
        if delta_representative is None:
            return None
        if delta_min is not None and delta_min > self.tolerance_m:
            return "gain"
        if delta_max is not None and delta_max < -self.tolerance_m:
            return "loss"
        if (
            delta_min is not None
            and delta_max is not None
            and abs(delta_min) <= self.tolerance_m
            and abs(delta_max) <= self.tolerance_m
        ):
            return "no_change"
        if delta_representative > self.tolerance_m:
            return "gain"
        if delta_representative < -self.tolerance_m:
            return "loss"
        return "no_change"

    def _sample_points(
        self,
        geometry: QgsGeometry,
        baseline: Optional[ControllingOlsCandidate] = None,
        future: Optional[ControllingOlsCandidate] = None,
        change: Optional[str] = None,
    ) -> List[QgsPointXY]:
        points: List[QgsPointXY] = []
        try:
            representative = geometry.pointOnSurface()
            if representative is not None and not representative.isEmpty():
                point = representative.asPoint()
                points.append(QgsPointXY(point.x(), point.y()))
        except Exception:
            pass
        if baseline is not None and future is not None and change:
            comparison_vertices = self._comparison_sample_vertices(geometry, baseline, future, change)
            if comparison_vertices:
                points.extend(comparison_vertices)
                return points
        try:
            vertices = list(geometry.vertices())
            if len(vertices) > 48:
                step = max(1, len(vertices) // 48)
                vertices = vertices[::step]
            points.extend(QgsPointXY(vertex.x(), vertex.y()) for vertex in vertices)
        except Exception:
            pass
        return points

    def _comparison_sample_vertices(
        self,
        geometry: QgsGeometry,
        baseline: ControllingOlsCandidate,
        future: ControllingOlsCandidate,
        change: str,
    ) -> List[QgsPointXY]:
        try:
            if QgsWkbTypes.geometryType(geometry.wkbType()) != Qgis.GeometryType.Polygon:
                return []
            rings = []
            if geometry.isMultipart():
                for polygon in geometry.asMultiPolygon():
                    for ring_index, ring in enumerate(polygon):
                        rings.append((ring, ring_index == 0))
            else:
                for ring_index, ring in enumerate(geometry.asPolygon()):
                    rings.append((ring, ring_index == 0))
            vertices: List[QgsPointXY] = []
            for ring, is_exterior in rings:
                if not ring:
                    continue
                filtered = self._filtered_comparison_sample_ring(
                    ring,
                    is_exterior,
                    baseline,
                    future,
                    change,
                )
                vertices.extend(filtered)
            if len(vertices) > 48:
                step = max(1, len(vertices) // 48)
                vertices = vertices[::step]
            return vertices
        except Exception:
            return []

    def _filtered_comparison_sample_ring(
        self,
        ring,
        exterior: bool,
        baseline: ControllingOlsCandidate,
        future: ControllingOlsCandidate,
        change: str,
    ) -> List[QgsPointXY]:
        points = [QgsPointXY(point) for point in ring]
        if len(points) >= 2 and self._same_point(points[0], points[-1]):
            points = points[:-1]
        if len(points) < 3:
            return []
        if not exterior:
            return points
        filtered = list(points)
        for _ in range(24):
            removed = False
            count = len(filtered)
            if count < 4:
                break
            for index in range(count):
                previous_point = filtered[(index - 1) % count]
                current_point = filtered[index]
                next_point = filtered[(index + 1) % count]
                if self._comparison_spike_vertex_kind(
                    previous_point,
                    current_point,
                    next_point,
                    baseline,
                    future,
                    change,
                ):
                    filtered.pop(index)
                    removed = True
                    break
            if not removed:
                break
        return filtered

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

    @staticmethod
    def _has_no_overlay_area(geometry: Optional[QgsGeometry]) -> bool:
        return bool(
            geometry is not None
            and not geometry.isEmpty()
            and geometry.area() >= COMPARISON_NO_OVERLAY_MIN_AREA_M2
        )

    def _comparison_coverage_geometry(self, geometry: Optional[QgsGeometry]) -> Optional[QgsGeometry]:
        if geometry is None or geometry.isEmpty():
            return geometry
        coverage = QgsGeometry(geometry)
        try:
            coverage = coverage.buffer(COMPARISON_NO_OVERLAY_COVERAGE_TOLERANCE_M, 4)
        except Exception:
            pass
        return self._normalise_no_overlay_geometry(coverage)

    def _no_overlay_part_has_tolerant_core(
        self,
        exact_part: QgsGeometry,
        tolerant_remaining: Optional[QgsGeometry],
    ) -> bool:
        if not self._has_no_overlay_area(exact_part):
            return False
        if tolerant_remaining is None:
            return True
        if tolerant_remaining.isEmpty():
            return False
        try:
            core = exact_part.intersection(tolerant_remaining)
        except Exception:
            return True
        return self._has_no_overlay_area(core)

    def _normalise_no_overlay_geometry(self, geometry: Optional[QgsGeometry]) -> Optional[QgsGeometry]:
        if geometry is None or geometry.isEmpty():
            return geometry
        normalised = QgsGeometry(geometry)
        try:
            normalised = normalised.snappedToGrid(
                COMPARISON_NO_OVERLAY_GRID_M,
                COMPARISON_NO_OVERLAY_GRID_M,
            )
        except Exception:
            pass
        try:
            if normalised is not None and not normalised.isEmpty() and not normalised.isGeosValid():
                normalised = normalised.makeValid()
        except Exception:
            pass
        try:
            buffered = normalised.buffer(0.0, 8)
            if buffered is not None and not buffered.isEmpty():
                normalised = buffered
        except Exception:
            pass
        return normalised

    def _clean_comparison_part(
        self,
        geometry: QgsGeometry,
        baseline: ControllingOlsCandidate,
        future: ControllingOlsCandidate,
        change: str,
    ) -> QgsGeometry:
        """Remove split artefact spikes without treating removed area as classified."""
        if geometry is None or geometry.isEmpty():
            return geometry
        original_area = geometry.area()
        if original_area < COMPARISON_MIN_AREA_M2:
            return QgsGeometry()
        cleaned, removed_severe_spike = self._remove_comparison_ring_spikes(
            geometry,
            baseline,
            future,
            change,
        )
        if cleaned is None or cleaned.isEmpty():
            return geometry
        area_change = abs(cleaned.area() - original_area)
        allowed_change = max(
            COMPARISON_SPIKE_MAX_AREA_CHANGE_M2,
            original_area * COMPARISON_SPIKE_MAX_AREA_CHANGE_RATIO,
        )
        if removed_severe_spike or area_change <= allowed_change:
            return cleaned
        return geometry

    def _remove_comparison_ring_spikes(
        self,
        geometry: QgsGeometry,
        baseline: ControllingOlsCandidate,
        future: ControllingOlsCandidate,
        change: str,
    ) -> Tuple[Optional[QgsGeometry], bool]:
        try:
            if QgsWkbTypes.geometryType(geometry.wkbType()) != Qgis.GeometryType.Polygon:
                return geometry, False
            removed_severe_spike = False
            if geometry.isMultipart():
                cleaned_polygons = []
                for polygon in geometry.asMultiPolygon():
                    cleaned, removed = self._clean_comparison_polygon_rings(
                        polygon,
                        baseline,
                        future,
                        change,
                    )
                    removed_severe_spike = removed_severe_spike or removed
                    if cleaned:
                        cleaned_polygons.append(cleaned)
                geometry = (
                    QgsGeometry.fromMultiPolygonXY(cleaned_polygons)
                    if cleaned_polygons
                    else QgsGeometry()
                )
                return geometry, removed_severe_spike
            cleaned_polygon, removed_severe_spike = self._clean_comparison_polygon_rings(
                geometry.asPolygon(),
                baseline,
                future,
                change,
            )
            geometry = QgsGeometry.fromPolygonXY(cleaned_polygon) if cleaned_polygon else QgsGeometry()
            return geometry, removed_severe_spike
        except Exception:
            return geometry, False

    def _clean_comparison_polygon_rings(
        self,
        polygon,
        baseline: ControllingOlsCandidate,
        future: ControllingOlsCandidate,
        change: str,
    ) -> Tuple[list, bool]:
        if not polygon:
            return [], False
        exterior, removed_severe_spike = self._clean_comparison_ring(
            polygon[0],
            True,
            baseline,
            future,
            change,
        )
        cleaned = [exterior]
        for ring in polygon[1:]:
            cleaned_ring, removed = self._clean_comparison_ring(
                ring,
                False,
                baseline,
                future,
                change,
            )
            removed_severe_spike = removed_severe_spike or removed
            if len(cleaned_ring) >= 4:
                cleaned.append(cleaned_ring)
        return (cleaned if len(cleaned[0]) >= 4 else []), removed_severe_spike

    def _clean_comparison_ring(
        self,
        ring,
        exterior: bool,
        baseline: ControllingOlsCandidate,
        future: ControllingOlsCandidate,
        change: str,
    ) -> Tuple[list, bool]:
        if not ring:
            return [], False
        points = [QgsPointXY(point) for point in ring]
        if len(points) >= 2 and self._same_point(points[0], points[-1]):
            points = points[:-1]
        if len(points) < 3:
            return [], False
        if not exterior:
            return points + [points[0]], False
        removed_severe_spike = False
        for _ in range(24):
            removed = False
            count = len(points)
            if count < 4:
                break
            for index in range(count):
                previous_point = points[(index - 1) % count]
                current_point = points[index]
                next_point = points[(index + 1) % count]
                spike_kind = self._comparison_spike_vertex_kind(
                    previous_point,
                    current_point,
                    next_point,
                    baseline,
                    future,
                    change,
                )
                if spike_kind:
                    removed_severe_spike = removed_severe_spike or spike_kind == "severe"
                    points.pop(index)
                    removed = True
                    break
            if not removed:
                break
        return points + [points[0]], removed_severe_spike

    def _clean_no_overlay_part(self, geometry: QgsGeometry) -> QgsGeometry:
        """Remove small overlay artefacts without materially changing real no-overlay areas."""
        if geometry is None or geometry.isEmpty():
            return geometry
        original_area = geometry.area()
        if original_area < COMPARISON_NO_OVERLAY_MIN_AREA_M2:
            return QgsGeometry()
        cleaned = self._remove_no_overlay_ring_spikes(geometry)
        if cleaned is None or cleaned.isEmpty():
            return geometry
        area_change = abs(cleaned.area() - original_area)
        allowed_change = max(
            COMPARISON_SPIKE_MAX_AREA_CHANGE_M2,
            original_area * COMPARISON_SPIKE_MAX_AREA_CHANGE_RATIO,
        )
        if area_change <= allowed_change:
            return cleaned
        return geometry

    def _remove_no_overlay_ring_spikes(self, geometry: QgsGeometry) -> Optional[QgsGeometry]:
        try:
            if QgsWkbTypes.geometryType(geometry.wkbType()) != Qgis.GeometryType.Polygon:
                return geometry
            if geometry.isMultipart():
                polygons = geometry.asMultiPolygon()
                cleaned_polygons = []
                for polygon in polygons:
                    cleaned = self._clean_no_overlay_polygon_rings(polygon)
                    if cleaned:
                        cleaned_polygons.append(cleaned)
                return QgsGeometry.fromMultiPolygonXY(cleaned_polygons) if cleaned_polygons else QgsGeometry()
            polygon = geometry.asPolygon()
            cleaned_polygon = self._clean_no_overlay_polygon_rings(polygon)
            return QgsGeometry.fromPolygonXY(cleaned_polygon) if cleaned_polygon else QgsGeometry()
        except Exception:
            return geometry

    def _clean_no_overlay_polygon_rings(self, polygon) -> list:
        if not polygon:
            return []
        cleaned = [self._clean_no_overlay_ring(polygon[0], exterior=True)]
        for ring in polygon[1:]:
            cleaned_ring = self._clean_no_overlay_ring(ring, exterior=False)
            if len(cleaned_ring) >= 4:
                cleaned.append(cleaned_ring)
        return cleaned if len(cleaned[0]) >= 4 else []

    def _clean_no_overlay_ring(self, ring, exterior: bool) -> list:
        if not ring:
            return []
        points = [QgsPointXY(point) for point in ring]
        if len(points) >= 2 and self._same_point(points[0], points[-1]):
            points = points[:-1]
        if len(points) < 3:
            return []
        # Interior rings are left alone except for duplicate/near-duplicate
        # closure handling; removing hole vertices risks changing semantics.
        if not exterior:
            return points + [points[0]]
        for _ in range(12):
            removed = False
            count = len(points)
            if count < 4:
                break
            for index in range(count):
                previous_point = points[(index - 1) % count]
                current_point = points[index]
                next_point = points[(index + 1) % count]
                if self._is_no_overlay_spike_vertex(previous_point, current_point, next_point):
                    points.pop(index)
                    removed = True
                    break
            if not removed:
                break
        return points + [points[0]]

    @staticmethod
    def _same_point(first: QgsPointXY, second: QgsPointXY) -> bool:
        return (
            abs(first.x() - second.x()) <= 1e-9
            and abs(first.y() - second.y()) <= 1e-9
        )

    @staticmethod
    def _is_no_overlay_spike_vertex(
        previous_point: QgsPointXY,
        current_point: QgsPointXY,
        next_point: QgsPointXY,
    ) -> bool:
        first_length = math.hypot(
            previous_point.x() - current_point.x(),
            previous_point.y() - current_point.y(),
        )
        second_length = math.hypot(
            next_point.x() - current_point.x(),
            next_point.y() - current_point.y(),
        )
        base_length = math.hypot(
            previous_point.x() - next_point.x(),
            previous_point.y() - next_point.y(),
        )
        if first_length <= 1e-9 or second_length <= 1e-9 or base_length <= 1e-9:
            return False
        if base_length > COMPARISON_SPIKE_BASE_MAX_M:
            return False
        detour_ratio = (first_length + second_length) / base_length
        if detour_ratio < COMPARISON_SPIKE_DETOUR_RATIO:
            return False
        cosine = (
            (first_length * first_length)
            + (second_length * second_length)
            - (base_length * base_length)
        ) / (2.0 * first_length * second_length)
        angle_degrees = math.degrees(math.acos(max(-1.0, min(1.0, cosine))))
        if angle_degrees > COMPARISON_SPIKE_ANGLE_DEGREES:
            return False
        semi_perimeter = (first_length + second_length + base_length) / 2.0
        triangle_area = math.sqrt(
            max(
                0.0,
                semi_perimeter
                * (semi_perimeter - first_length)
                * (semi_perimeter - second_length)
                * (semi_perimeter - base_length),
            )
        )
        height = (2.0 * triangle_area / base_length) if base_length > 0.0 else 0.0
        return height >= COMPARISON_SPIKE_HEIGHT_MIN_M or angle_degrees <= 2.0

    def _comparison_spike_vertex_kind(
        self,
        previous_point: QgsPointXY,
        current_point: QgsPointXY,
        next_point: QgsPointXY,
        baseline: ControllingOlsCandidate,
        future: ControllingOlsCandidate,
        change: str,
    ) -> Optional[str]:
        metrics = self._comparison_spike_metrics(previous_point, current_point, next_point)
        if metrics is None:
            return None
        if self._is_severe_comparison_spike_shape(metrics):
            return "severe"
        if not self._is_delta_comparison_spike_shape(metrics):
            return None
        current_delta = self._delta_at_point(current_point, baseline, future)
        if current_delta is None:
            return None
        previous_delta = self._delta_at_point(previous_point, baseline, future)
        next_delta = self._delta_at_point(next_point, baseline, future)
        neighbour_values = [
            value for value in (previous_delta, next_delta)
            if value is not None and math.isfinite(value)
        ]
        if not neighbour_values:
            return None
        if change == "loss":
            return "delta" if (
                current_delta > self.tolerance_m
                and any(value <= self.tolerance_m for value in neighbour_values)
            ) else None
        if change == "gain":
            return "delta" if (
                current_delta < -self.tolerance_m
                and any(value >= -self.tolerance_m for value in neighbour_values)
            ) else None
        if change == "no_change":
            return "delta" if (
                abs(current_delta) > self.tolerance_m
                and any(abs(value) <= self.tolerance_m for value in neighbour_values)
            ) else None
        return None

    @staticmethod
    def _comparison_spike_metrics(
        previous_point: QgsPointXY,
        current_point: QgsPointXY,
        next_point: QgsPointXY,
    ) -> Optional[Tuple[float, float, float, float]]:
        first_length = math.hypot(
            previous_point.x() - current_point.x(),
            previous_point.y() - current_point.y(),
        )
        second_length = math.hypot(
            next_point.x() - current_point.x(),
            next_point.y() - current_point.y(),
        )
        base_length = math.hypot(
            previous_point.x() - next_point.x(),
            previous_point.y() - next_point.y(),
        )
        if first_length <= 1e-9 or second_length <= 1e-9 or base_length <= 1e-9:
            return None
        detour_ratio = (first_length + second_length) / base_length
        cosine = (
            (first_length * first_length)
            + (second_length * second_length)
            - (base_length * base_length)
        ) / (2.0 * first_length * second_length)
        angle_degrees = math.degrees(math.acos(max(-1.0, min(1.0, cosine))))
        semi_perimeter = (first_length + second_length + base_length) / 2.0
        triangle_area = math.sqrt(
            max(
                0.0,
                semi_perimeter
                * (semi_perimeter - first_length)
                * (semi_perimeter - second_length)
                * (semi_perimeter - base_length),
            )
        )
        height = (2.0 * triangle_area / base_length) if base_length > 0.0 else 0.0
        return detour_ratio, angle_degrees, height, base_length

    @staticmethod
    def _is_delta_comparison_spike_shape(metrics: Tuple[float, float, float, float]) -> bool:
        detour_ratio, angle_degrees, _height, base_length = metrics
        return (
            base_length <= COMPARISON_SPIKE_BASE_MAX_M
            and detour_ratio >= COMPARISON_SPIKE_DETOUR_RATIO
            and angle_degrees <= COMPARISON_SPIKE_ANGLE_DEGREES
        )

    @staticmethod
    def _is_severe_comparison_spike_shape(metrics: Tuple[float, float, float, float]) -> bool:
        detour_ratio, angle_degrees, height, _base_length = metrics
        if detour_ratio >= 1.5 and height >= 250.0 and angle_degrees <= 75.0:
            return True
        if detour_ratio >= 1.25 and height >= 250.0 and angle_degrees <= 60.0:
            return True
        if detour_ratio >= 4.0 and height >= 50.0 and angle_degrees <= 25.0:
            return True
        if (
            detour_ratio >= COMPARISON_SEVERE_SPIKE_DETOUR_RATIO
            and height >= COMPARISON_SPIKE_HEIGHT_MIN_M
            and angle_degrees <= COMPARISON_SEVERE_SPIKE_ANGLE_DEGREES
        ):
            return True
        if detour_ratio >= 20.0:
            return height >= 10.0 and angle_degrees <= COMPARISON_SPIKE_ANGLE_DEGREES
        return detour_ratio >= 50.0 and angle_degrees <= 2.0

    @staticmethod
    def _delta_at_point(
        point: QgsPointXY,
        baseline: ControllingOlsCandidate,
        future: ControllingOlsCandidate,
    ) -> Optional[float]:
        baseline_z = baseline.elevation_at_xy(point)
        future_z = future.elevation_at_xy(point)
        if baseline_z is None or future_z is None:
            return None
        delta = float(future_z) - float(baseline_z)
        return delta if math.isfinite(delta) else None

    @staticmethod
    def _round_delta(delta: float) -> float:
        rounded = round(float(delta), COMPARISON_DELTA_DECIMALS)
        return 0.0 if rounded == 0 else rounded

    @staticmethod
    def _union_geometries(geometries: Sequence[QgsGeometry]) -> Optional[QgsGeometry]:
        non_empty = [QgsGeometry(geometry) for geometry in geometries if geometry is not None and not geometry.isEmpty()]
        if not non_empty:
            return None
        try:
            return QgsGeometry.unaryUnion(non_empty)
        except Exception:
            merged = QgsGeometry(non_empty[0])
            for geometry in non_empty[1:]:
                try:
                    merged = merged.combine(geometry)
                except Exception:
                    pass
            return merged

    @staticmethod
    def _line_parts(geometry: QgsGeometry) -> List[QgsGeometry]:
        if geometry is None or geometry.isEmpty():
            return []
        try:
            if QgsWkbTypes.geometryType(geometry.wkbType()) != Qgis.GeometryType.Line:
                return []
        except Exception:
            return [geometry]
        if not geometry.isMultipart():
            return [geometry]
        parts: List[QgsGeometry] = []
        try:
            for line in geometry.asMultiPolyline():
                if line:
                    parts.append(QgsGeometry.fromPolylineXY(line))
        except Exception:
            pass
        return parts


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
            created = self._create_modernisation_wireframe_layer(
                icao_code, baseline_ruleset_id, family, "baseline",
                "Baseline OLS Wireframe", baseline_engine._controlling_region_geometries(),
                family_group,
            ) or created
            created = self._create_modernisation_wireframe_layer(
                icao_code, baseline_ruleset_id, family, "future",
                "Future Annex 14 Wireframe", future_engine._controlling_region_geometries(),
                family_group,
            ) or created
            gain_name = "Height Gain" if family == "OFS" else "Trigger Height Raised"
            loss_name = "Height Loss" if family == "OFS" else "Trigger Height Lowered"
            no_change_name = "No Height Change" if family == "OFS" else "Trigger Height Unchanged"
            created = self._create_modernisation_change_layer(
                icao_code, baseline_ruleset_id, family, "gain", gain_name,
                parts["gain"], comparison, family_group,
            ) or created
            created = self._create_modernisation_change_layer(
                icao_code, baseline_ruleset_id, family, "loss", loss_name,
                parts["loss"], comparison, family_group,
            ) or created
            created = self._create_modernisation_change_layer(
                icao_code, baseline_ruleset_id, family, "no_change", no_change_name,
                parts["no_change"], comparison, family_group,
            ) or created
            created = self._create_modernisation_transition_layer(
                icao_code, baseline_ruleset_id, family, parts["transition"], comparison, family_group,
            ) or created
            created = self._create_modernisation_baseline_only_layer(
                icao_code, baseline_ruleset_id, family,
                comparison.baseline_only_parts(), family_group,
            ) or created
        return created

    def _comparison_label(self, change: str, delta_representative: Optional[float]) -> str:
        if delta_representative is None:
            return ""
        if change == "no_change":
            return f"{delta_representative:.1f} m no change"
        sign = "+" if delta_representative > 0 else ""
        suffix = "gain" if change == "gain" else "loss"
        return f"{sign}{delta_representative:.1f} m {suffix}"

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
            QgsField("label_txt", QVariant.String, self.tr("Map Label"), 32),
        ])
        features: List[QgsFeature] = []
        if family == "OFS":
            if change == "gain":
                meaning = "Future obstacle-free reference surface is higher than baseline"
            elif change == "loss":
                meaning = "Future obstacle-free reference surface is lower than baseline"
            else:
                meaning = "Future obstacle-free reference surface is effectively equal to baseline"
        else:
            if change == "gain":
                meaning = "Future aeronautical-study trigger is raised; this is not an approval limit"
            elif change == "loss":
                meaning = "Future aeronautical-study trigger is lowered; this is not an approval limit"
            else:
                meaning = "Future aeronautical-study trigger is effectively unchanged; this is not an approval limit"
        for baseline, future, geometry in parts:
            delta_min, delta_max, delta_representative = comparison.delta_range(geometry, baseline, future, change)
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
                self._comparison_label(change, delta_representative),
            ])
            features.append(feature)
        layer = self._create_and_add_layer(
            "MultiPolygon",
            f"OLS_Modernisation_{family}_{change}_{icao_code}",
            display_name,
            fields,
            features,
            output_group,
            {
                "gain": "OLS Modernisation Gain",
                "loss": "OLS Modernisation Loss",
                "no_change": "OLS Modernisation No Change",
            }.get(change, "OLS Modernisation No Change"),
        )
        return layer is not None

    def _create_modernisation_wireframe_layer(
        self,
        icao_code,
        baseline_ruleset_id,
        family,
        source_kind,
        display_name,
        candidate_regions,
        output_group,
    ) -> bool:
        fields = QgsFields([
            QgsField("source", QVariant.String, self.tr("Source"), 24),
            QgsField("family", QVariant.String, self.tr("Family"), 8),
            QgsField("baseline_ruleset", QVariant.String, self.tr("Baseline Ruleset"), 80),
            QgsField("surface_id", QVariant.String, self.tr("Surface ID"), 160),
            QgsField("surface", QVariant.String, self.tr("Surface"), 50),
        ])
        features: List[QgsFeature] = []
        for candidate, geometry in candidate_regions:
            for part in self._modernisation_polygon_parts(geometry):
                if not OlsEnvelopeComparisonEngine._has_area(part):
                    continue
                feature = QgsFeature(fields)
                feature.setGeometry(part)
                feature.setAttributes([
                    source_kind,
                    family,
                    baseline_ruleset_id,
                    candidate.surface_id,
                    candidate.surface_type,
                ])
                features.append(feature)
        layer = self._create_and_add_layer(
            "MultiPolygon",
            f"OLS_Modernisation_{family}_{source_kind}_wireframe_{icao_code}",
            display_name,
            fields,
            features,
            output_group,
            "OLS Modernisation Baseline Wireframe"
            if source_kind == "baseline"
            else "OLS Modernisation Future Wireframe",
        )
        return layer is not None

    def _modernisation_polygon_parts(self, geometry: QgsGeometry) -> List[QgsGeometry]:
        if geometry is None or geometry.isEmpty():
            return []
        try:
            if QgsWkbTypes.geometryType(geometry.wkbType()) != Qgis.GeometryType.Polygon:
                return []
        except Exception:
            return [geometry]
        if not geometry.isMultipart():
            return [QgsGeometry(geometry)]
        parts: List[QgsGeometry] = []
        try:
            for polygon in geometry.asMultiPolygon():
                if polygon:
                    parts.append(QgsGeometry.fromPolygonXY(polygon))
        except Exception:
            pass
        return parts

    def _create_modernisation_transition_layer(
        self,
        icao_code,
        baseline_ruleset_id,
        family,
        parts,
        comparison,
        output_group,
    ) -> bool:
        fields = QgsFields([
            QgsField("future_family", QVariant.String, self.tr("Future Family"), 8),
            QgsField("baseline_ruleset", QVariant.String, self.tr("Baseline Ruleset"), 80),
            QgsField("baseline_id", QVariant.String, self.tr("Baseline Surface ID"), 160),
            QgsField("baseline_surface", QVariant.String, self.tr("Baseline Surface"), 50),
            QgsField("future_id", QVariant.String, self.tr("Future Surface ID"), 160),
            QgsField("future_surface", QVariant.String, self.tr("Future Surface"), 50),
            QgsField("meaning", QVariant.String, self.tr("Regulatory Meaning"), 160),
        ])
        features: List[QgsFeature] = []
        for baseline, future, geometry in parts:
            feature = QgsFeature(fields)
            feature.setGeometry(geometry)
            feature.setAttributes([
                family,
                baseline_ruleset_id,
                baseline.surface_id,
                baseline.surface_type,
                future.surface_id,
                future.surface_type,
                "Approximate line where the baseline and future controlling elevations are equal",
            ])
            features.append(feature)
        layer = self._create_and_add_layer(
            "MultiLineString",
            f"OLS_Modernisation_{family}_transition_{icao_code}",
            "Planar Transition / Equal Height",
            fields,
            features,
            output_group,
            "OLS Modernisation Transition",
        )
        return layer is not None

    def _create_modernisation_baseline_only_layer(
        self,
        icao_code,
        baseline_ruleset_id,
        family,
        parts,
        output_group,
    ) -> bool:
        fields = QgsFields([
            QgsField("change", QVariant.String, self.tr("Change"), 32),
            QgsField("future_family", QVariant.String, self.tr("Future Family"), 8),
            QgsField("baseline_ruleset", QVariant.String, self.tr("Baseline Ruleset"), 80),
            QgsField("baseline_id", QVariant.String, self.tr("Baseline Surface ID"), 160),
            QgsField("baseline_surface", QVariant.String, self.tr("Baseline Surface"), 50),
            QgsField("meaning", QVariant.String, self.tr("Regulatory Meaning"), 160),
            QgsField("label_txt", QVariant.String, self.tr("Map Label"), 32),
        ])
        features: List[QgsFeature] = []
        for baseline, geometry in parts:
            feature = QgsFeature(fields)
            feature.setGeometry(geometry)
            feature.setAttributes([
                "no_future_overlay",
                family,
                baseline_ruleset_id,
                baseline.surface_id,
                baseline.surface_type,
                "Baseline controlling OLS area with no overlapping future Annex 14 comparison surface",
                "no future overlay",
            ])
            features.append(feature)
        layer = self._create_and_add_layer(
            "MultiPolygon",
            f"OLS_Modernisation_{family}_no_future_overlay_{icao_code}",
            "No Future OLS Overlay",
            fields,
            features,
            output_group,
            "OLS Modernisation No Future Overlay",
        )
        return layer is not None


__all__ = ["OlsEnvelopeComparisonEngine", "OlsModernisationComparisonMixin"]
