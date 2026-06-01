# -*- coding: utf-8 -*-
"""Planar lower-envelope engine for controlling OLS proof-of-concept outputs."""

import math
import time
from dataclasses import dataclass, field
from typing import Callable, Dict, Iterable, List, Optional, Sequence, Tuple

from qgis.PyQt.QtCore import QVariant  # type: ignore
from qgis.core import (  # type: ignore
    Qgis,
    QgsFeature,
    QgsField,
    QgsFields,
    QgsGeometry,
    QgsLayerTreeGroup,
    QgsLineString,
    QgsMessageLog,
    QgsPoint,
    QgsPointXY,
    QgsRectangle,
    QgsWkbTypes,
)

PLUGIN_TAG = "SafeguardingBuilder"
CONTROLLING_OLS_ENGINE_BUILD = "controlling-ols-gap-lower-envelope-2026-06-01"

ElevationEvaluator = Callable[[QgsPointXY], Optional[float]]


@dataclass(frozen=True)
class ControllingOlsCandidate:
    """A candidate OLS surface represented by a 2D domain and an elevation function."""

    surface_id: str
    surface_type: str
    footprint: QgsGeometry
    elevation_at_xy: ElevationEvaluator
    model: str
    metadata: Dict[str, object] = field(default_factory=dict)

    def contains_xy(self, point_xy: QgsPointXY) -> bool:
        if self.footprint is None or self.footprint.isEmpty():
            return False
        return bool(self.footprint.intersects(QgsGeometry.fromPointXY(point_xy)))


def constant_elevation_evaluator(elevation_m: float) -> ElevationEvaluator:
    """Return an evaluator for a flat OLS plane."""

    def _evaluate(_point_xy: QgsPointXY) -> Optional[float]:
        return elevation_m

    return _evaluate


def axis_elevation_evaluator(
    origin_xy: QgsPointXY,
    azimuth_degrees: float,
    origin_elevation_m: float,
    slope: float,
    max_distance_m: Optional[float] = None,
) -> ElevationEvaluator:
    """Return an evaluator for a planar surface rising along an axis."""
    azimuth_radians = math.radians(azimuth_degrees)
    ux = math.sin(azimuth_radians)
    uy = math.cos(azimuth_radians)

    def _evaluate(point_xy: QgsPointXY) -> Optional[float]:
        distance_along = ((point_xy.x() - origin_xy.x()) * ux) + ((point_xy.y() - origin_xy.y()) * uy)
        if distance_along < -1e-6:
            return None
        if max_distance_m is not None and distance_along > max_distance_m + 1e-6:
            return None
        clamped = max(0.0, distance_along)
        if max_distance_m is not None:
            clamped = min(max_distance_m, clamped)
        return origin_elevation_m + (clamped * slope)

    return _evaluate


def plane_elevation_evaluator(a: float, b: float, c: float) -> ElevationEvaluator:
    """Return an evaluator for a generic planar surface z = ax + by + c."""

    def _evaluate(point_xy: QgsPointXY) -> Optional[float]:
        return (a * point_xy.x()) + (b * point_xy.y()) + c

    return _evaluate


def conical_elevation_evaluator(
    base_footprint: QgsGeometry,
    base_elevation_m: float,
    slope: float,
    max_distance_m: Optional[float] = None,
) -> ElevationEvaluator:
    """Return an evaluator for a conical surface rising outwards from an IHS footprint."""
    base_geometry = QgsGeometry(base_footprint)

    def _evaluate(point_xy: QgsPointXY) -> Optional[float]:
        if base_geometry is None or base_geometry.isEmpty() or slope <= 0:
            return None
        point_geometry = QgsGeometry.fromPointXY(point_xy)
        distance = base_geometry.distance(point_geometry)
        if max_distance_m is not None and distance > max_distance_m + 1e-6:
            return None
        distance = max(0.0, distance)
        if max_distance_m is not None:
            distance = min(max_distance_m, distance)
        return base_elevation_m + (distance * slope)

    return _evaluate


class PlanarControllingOlsEngine:
    """Compute exact transition edges between planar OLS candidates."""

    def __init__(
        self,
        candidates: Sequence[ControllingOlsCandidate],
        tie_tolerance_m: float = 0.01,
        exclusion_geometries: Optional[Sequence[QgsGeometry]] = None,
    ):
        self.candidates = [
            candidate
            for candidate in candidates
            if candidate.model in {"constant", "axis", "plane", "conical"}
            and candidate.footprint is not None
            and not candidate.footprint.isEmpty()
        ]
        self.exclusion_geometries = [
            QgsGeometry(geometry)
            for geometry in (exclusion_geometries or [])
            if geometry is not None and not geometry.isEmpty()
        ]
        self._effective_footprint_cache: Dict[str, QgsGeometry] = {}
        self._conical_buffer_cache: Dict[Tuple[str, int], QgsGeometry] = {}
        self._diagnostics: List[str] = [f"engine_build={CONTROLLING_OLS_ENGINE_BUILD}"]
        self._candidate_loss_diagnostics: Dict[str, List[Tuple[float, str, str, float, Optional[float]]]] = {}
        self._candidate_unknown_diagnostics: Dict[str, List[Tuple[float, str, str]]] = {}
        self.tie_tolerance_m = max(0.0, float(tie_tolerance_m))
        self.bounds = self._combined_bounds(self.candidates)

    def controlling_candidate_at_xy(self, point_xy: QgsPointXY) -> Optional[Tuple[ControllingOlsCandidate, float]]:
        """Return the lowest applicable planar candidate at a point."""
        evaluated: List[Tuple[ControllingOlsCandidate, float]] = []
        for candidate in self.candidates:
            footprint = self._effective_footprint(candidate)
            if footprint is None or footprint.isEmpty() or not footprint.intersects(QgsGeometry.fromPointXY(point_xy)):
                continue
            elevation = candidate.elevation_at_xy(point_xy)
            if elevation is None or not math.isfinite(elevation):
                continue
            evaluated.append((candidate, elevation))
        if not evaluated:
            return None
        evaluated.sort(key=lambda item: item[1])
        return evaluated[0]

    def transition_features(self, fields: QgsFields) -> List[QgsFeature]:
        """Return exact line features where supported planar candidates exchange control."""
        features: List[QgsFeature] = []
        for index, first_candidate in enumerate(self.candidates):
            for second_candidate in self.candidates[index + 1 :]:
                for transition_line in self._candidate_transition_lines(first_candidate, second_candidate):
                    for line_points in self._line_parts(transition_line):
                        if len(line_points) < 2:
                            continue
                        z_values = self._transition_z_values(line_points, first_candidate, second_candidate)
                        z_line = self._line_points_to_z_geometry(line_points, z_values)
                        if z_line is None or z_line.isEmpty():
                            continue
                        feature = QgsFeature(fields)
                        feature.setGeometry(z_line)
                        feature.setAttributes(
                            [
                                f"{first_candidate.surface_id}|{second_candidate.surface_id}"[:160],
                                "Transition",
                                min(z_values),
                                max(z_values),
                                f"{first_candidate.surface_id}|{second_candidate.surface_id}"[:254],
                                "exact_planar_transition",
                            ]
                        )
                        features.append(feature)
        return features

    def region_features(self, fields: QgsFields) -> List[QgsFeature]:
        """Return regions where each planar candidate is lower than all overlapping candidates."""
        features: List[QgsFeature] = []
        for region_id, (candidate, region_part) in enumerate(self._controlling_region_geometries(), start=1):
            feature = QgsFeature(fields)
            feature.setGeometry(region_part)
            min_elev, max_elev = self._geometry_elevation_range(region_part, candidate)
            feature.setAttributes(
                [
                    region_id,
                    candidate.surface_id,
                    candidate.surface_type,
                    candidate.model,
                    min_elev,
                    max_elev,
                    "exact_planar_halfplane",
                ]
            )
            features.append(feature)
        return features

    def region_boundary_features(self, fields: QgsFields) -> List[QgsFeature]:
        """Return line features where solved controlling region boundaries change controller."""
        region_parts = self._controlling_region_geometries()
        features: List[QgsFeature] = []
        seen_keys = set()
        for region_candidate, region in region_parts:
            for line_points in self._polygon_boundary_parts(region):
                for start_point, end_point in zip(line_points[:-1], line_points[1:]):
                    controllers = self._controllers_across_segment(start_point, end_point)
                    if controllers is None:
                        continue
                    first_controller, second_controller = controllers
                    if first_controller.surface_id == second_controller.surface_id:
                        continue
                    segment_points = [start_point, end_point]
                    key = self._line_key(
                        segment_points,
                        first_controller.surface_id,
                        second_controller.surface_id,
                    )
                    if key in seen_keys:
                        continue
                    seen_keys.add(key)
                    z_values = self._transition_z_values(segment_points, first_controller, second_controller)
                    z_line = self._line_points_to_z_geometry(segment_points, z_values)
                    if z_line is None or z_line.isEmpty():
                        continue
                    feature = QgsFeature(fields)
                    feature.setGeometry(z_line)
                    feature.setAttributes(
                        [
                            f"{first_controller.surface_id}|{second_controller.surface_id}"[:160],
                            "Transition",
                            min(z_values),
                            max(z_values),
                            f"{first_controller.surface_id}|{second_controller.surface_id}"[:254],
                            "region_boundary",
                        ]
                    )
                    features.append(feature)
        return features

    def _polygon_boundary_parts(self, geometry: QgsGeometry) -> List[List[QgsPointXY]]:
        """Return exterior and interior polygon rings as line point lists."""
        if geometry is None or geometry.isEmpty():
            return []
        rings: List[List[QgsPointXY]] = []
        try:
            if geometry.type() != QgsWkbTypes.PolygonGeometry:
                return []
            polygons = geometry.asMultiPolygon() if geometry.isMultipart() else [geometry.asPolygon()]
            for polygon in polygons:
                for ring in polygon:
                    if len(ring) >= 2:
                        rings.append(ring)
        except Exception:
            return []
        return rings

    def _controllers_across_segment(
        self,
        start_point: QgsPointXY,
        end_point: QgsPointXY,
    ) -> Optional[Tuple[ControllingOlsCandidate, ControllingOlsCandidate]]:
        dx = end_point.x() - start_point.x()
        dy = end_point.y() - start_point.y()
        length = math.hypot(dx, dy)
        if length <= 1e-6:
            return None
        mid_point = QgsPointXY((start_point.x() + end_point.x()) / 2.0, (start_point.y() + end_point.y()) / 2.0)
        nx = -dy / length
        ny = dx / length
        for offset in [0.05, 0.1, 0.25, 0.5, 1.0, max(min(length * 0.02, 5.0), 0.25), 10.0]:
            left = self.controlling_candidate_at_xy(
                QgsPointXY(mid_point.x() + (nx * offset), mid_point.y() + (ny * offset))
            )
            right = self.controlling_candidate_at_xy(
                QgsPointXY(mid_point.x() - (nx * offset), mid_point.y() - (ny * offset))
            )
            if left is None or right is None:
                continue
            if left[0].surface_id != right[0].surface_id:
                return left[0], right[0]
        return None

    def _legacy_shared_boundary_features(
        self,
        fields: QgsFields,
        region_parts: List[Tuple[ControllingOlsCandidate, QgsGeometry]],
        seen_keys: set,
    ) -> List[QgsFeature]:
        features: List[QgsFeature] = []
        for index, (first_candidate, first_region) in enumerate(region_parts):
            for second_candidate, second_region in region_parts[index + 1 :]:
                if first_candidate.surface_id == second_candidate.surface_id:
                    continue
                try:
                    boundary = first_region.boundary().intersection(second_region.boundary())
                except Exception:
                    continue
                for line_points in self._line_parts(boundary):
                    if len(line_points) < 2:
                        continue
                    key = self._line_key(line_points, first_candidate.surface_id, second_candidate.surface_id)
                    if key in seen_keys:
                        continue
                    seen_keys.add(key)
                    z_values = self._transition_z_values(line_points, first_candidate, second_candidate)
                    z_line = self._line_points_to_z_geometry(line_points, z_values)
                    if z_line is None or z_line.isEmpty():
                        continue
                    feature = QgsFeature(fields)
                    feature.setGeometry(z_line)
                    feature.setAttributes(
                        [
                            f"{first_candidate.surface_id}|{second_candidate.surface_id}"[:160],
                            "Transition",
                            min(z_values),
                            max(z_values),
                            f"{first_candidate.surface_id}|{second_candidate.surface_id}"[:254],
                            "exact_region_boundary",
                        ]
                    )
                    features.append(feature)
        return features

    def _controlling_region_geometries(self) -> List[Tuple[ControllingOlsCandidate, QgsGeometry]]:
        region_parts: List[Tuple[ControllingOlsCandidate, QgsGeometry]] = []
        started_at = time.perf_counter()
        for candidate in self.candidates:
            region = self._effective_footprint(candidate)
            initial_area = region.area() if region is not None and not region.isEmpty() else 0.0
            for competitor in self.candidates:
                if competitor.surface_id == candidate.surface_id:
                    continue
                if region is None or region.isEmpty():
                    break
                overlap = None
                try:
                    competitor_footprint = self._effective_footprint(competitor)
                    if competitor_footprint is None or competitor_footprint.isEmpty():
                        continue
                    overlap = region.intersection(competitor_footprint)
                except Exception:
                    overlap = None
                if not self._has_polygon_area(overlap):
                    continue
                lower_region = self._candidate_lower_region(candidate, competitor, overlap)
                try:
                    if lower_region is None:
                        if self._unresolved_comparison_removes_candidate(candidate, competitor, overlap):
                            lower_region = QgsGeometry()
                        else:
                            self._record_candidate_unknown(candidate, competitor, overlap)
                            continue
                    if lower_region.isEmpty():
                        losing_area = overlap
                    else:
                        lower_region = self._clip_lower_region_to_overlap(lower_region, overlap)
                        if lower_region is None:
                            if self._unresolved_comparison_removes_candidate(candidate, competitor, overlap):
                                lower_region = QgsGeometry()
                            else:
                                self._record_candidate_unknown(candidate, competitor, overlap)
                                continue
                        if lower_region.isEmpty():
                            losing_area = overlap
                        else:
                            losing_area = overlap.difference(lower_region)
                    if losing_area is not None and not losing_area.isEmpty() and self._has_polygon_area(losing_area):
                        self._record_candidate_loss(candidate, competitor, losing_area, overlap, lower_region)
                        region = region.difference(losing_area)
                except Exception:
                    region = QgsGeometry()
                    break

            final_area = region.area() if region is not None and not region.isEmpty() else 0.0
            if initial_area > 0.0 and final_area < initial_area * 0.05:
                self._diagnostics.append(
                    "candidate nearly removed: "
                    f"{candidate.surface_id}; initial_area={initial_area:.3f}; final_area={final_area:.3f}"
                )
            for region_part in self._polygon_parts(region):
                for final_part in self._polygon_parts(region_part):
                    for clean_part in self._clean_region_polygon_parts(final_part, candidate):
                        if clean_part.area() <= 1e-3:
                            continue
                        region_parts.append((candidate, clean_part))
        self._repair_region_coverage(region_parts)
        region_parts = self._merge_region_parts_by_candidate(region_parts)
        self._log_region_diagnostics(time.perf_counter() - started_at)
        return region_parts

    def _merge_region_parts_by_candidate(
        self,
        region_parts: List[Tuple[ControllingOlsCandidate, QgsGeometry]],
    ) -> List[Tuple[ControllingOlsCandidate, QgsGeometry]]:
        """Dissolve adjacent solved parts for the same controlling candidate."""
        grouped: Dict[str, Tuple[ControllingOlsCandidate, List[QgsGeometry]]] = {}
        for candidate, geometry in region_parts:
            if not self._has_polygon_area(geometry):
                continue
            if candidate.surface_id not in grouped:
                grouped[candidate.surface_id] = (candidate, [])
            grouped[candidate.surface_id][1].append(geometry)

        merged_parts: List[Tuple[ControllingOlsCandidate, QgsGeometry]] = []
        merged_count = 0
        for candidate in self.candidates:
            grouped_entry = grouped.get(candidate.surface_id)
            if grouped_entry is None:
                continue
            _, geometries = grouped_entry
            try:
                merged = QgsGeometry.unaryUnion(geometries) if len(geometries) > 1 else QgsGeometry(geometries[0])
            except Exception:
                merged = QgsGeometry()
            if not self._has_polygon_area(merged):
                continue
            output_count_before = len(merged_parts)
            for polygon_part in self._polygon_parts(merged):
                for clean_part in self._clean_region_polygon_parts(polygon_part, candidate):
                    if clean_part.area() <= 1e-3:
                        continue
                    merged_parts.append((candidate, clean_part))
            merged_count += max(0, len(geometries) - (len(merged_parts) - output_count_before))
        if merged_count:
            self._diagnostics.append(f"same-candidate dissolve removed {merged_count} internal region part(s)")
        return merged_parts

    def _unresolved_comparison_removes_candidate(
        self,
        candidate: ControllingOlsCandidate,
        competitor: ControllingOlsCandidate,
        overlap: Optional[QgsGeometry],
    ) -> bool:
        """Avoid retaining axis surfaces over conical regions when the exact solve is inconclusive."""
        if candidate.model == "axis" and competitor.model == "conical":
            overlap_area = overlap.area() if overlap is not None and not overlap.isEmpty() else 0.0
            self._diagnostics.append(
                "axis/conical unresolved comparison clipped candidate: "
                f"axis={candidate.surface_id}; conical={competitor.surface_id}; overlap={overlap_area:.3f}"
            )
            return True
        return False

    def _repair_region_coverage(self, region_parts: List[Tuple[ControllingOlsCandidate, QgsGeometry]]) -> None:
        coverage_parts = []
        for candidate in self.candidates:
            footprint = self._effective_footprint(candidate)
            if self._has_polygon_area(footprint):
                coverage_parts.append(footprint)
        if not coverage_parts:
            return
        try:
            coverage = QgsGeometry.unaryUnion(coverage_parts) if len(coverage_parts) > 1 else QgsGeometry(coverage_parts[0])
        except Exception:
            return
        if not self._has_polygon_area(coverage):
            return

        solved_parts = [geometry for _, geometry in region_parts if self._has_polygon_area(geometry)]
        try:
            solved = QgsGeometry.unaryUnion(solved_parts) if solved_parts else QgsGeometry()
        except Exception:
            solved = QgsGeometry()
        try:
            gaps = coverage.difference(solved) if solved is not None and not solved.isEmpty() else coverage
        except Exception:
            return

        repaired_count = 0
        repaired_area = 0.0
        for gap_part in self._polygon_parts(gaps):
            if gap_part.area() <= 1.0:
                continue
            repaired_parts = self._gap_lower_envelope_parts(gap_part)
            if not repaired_parts:
                self._diagnostics.append(
                    f"coverage gap retained empty: area={gap_part.area():.3f}"
                )
                continue
            for candidate, clean_part in repaired_parts:
                region_parts.append((candidate, clean_part))
                repaired_count += 1
                repaired_area += clean_part.area()
        if repaired_count:
            self._diagnostics.append(
                f"coverage repair added {repaired_count} gap region(s); area={repaired_area:.3f}"
            )

    def _gap_lower_envelope_parts(
        self,
        gap_geometry: QgsGeometry,
    ) -> List[Tuple[ControllingOlsCandidate, QgsGeometry]]:
        repaired_parts: List[Tuple[ControllingOlsCandidate, QgsGeometry]] = []
        for candidate in self.candidates:
            try:
                candidate_region = gap_geometry.intersection(self._effective_footprint(candidate))
            except Exception:
                candidate_region = None
            if not self._has_polygon_area(candidate_region):
                continue
            for competitor in self.candidates:
                if competitor.surface_id == candidate.surface_id:
                    continue
                if candidate_region is None or candidate_region.isEmpty():
                    break
                try:
                    overlap = candidate_region.intersection(self._effective_footprint(competitor))
                except Exception:
                    overlap = None
                if not self._has_polygon_area(overlap):
                    continue
                lower_region = self._candidate_lower_region(candidate, competitor, overlap)
                if lower_region is None:
                    if self._unresolved_comparison_removes_candidate(candidate, competitor, overlap):
                        lower_region = QgsGeometry()
                    else:
                        continue
                if lower_region.isEmpty():
                    losing_area = overlap
                else:
                    lower_region = self._clip_lower_region_to_overlap(lower_region, overlap)
                    if lower_region is None:
                        if self._unresolved_comparison_removes_candidate(candidate, competitor, overlap):
                            lower_region = QgsGeometry()
                        else:
                            continue
                    losing_area = overlap if lower_region.isEmpty() else overlap.difference(lower_region)
                if self._has_polygon_area(losing_area):
                    try:
                        candidate_region = candidate_region.difference(losing_area)
                    except Exception:
                        candidate_region = QgsGeometry()
                        break
            for region_part in self._polygon_parts(candidate_region):
                for clean_part in self._clean_region_polygon_parts(region_part, candidate):
                    if clean_part.area() > 1.0:
                        repaired_parts.append((candidate, clean_part))
        return repaired_parts

    def _candidate_for_gap(self, gap_geometry: QgsGeometry) -> Optional[ControllingOlsCandidate]:
        sample_points: List[QgsPointXY] = []
        try:
            point = gap_geometry.pointOnSurface().asPoint()
            sample_points.append(QgsPointXY(point.x(), point.y()))
        except Exception:
            pass
        sample_points.extend(self._geometry_sample_points(gap_geometry))
        for point_xy in sample_points:
            result = self.controlling_candidate_at_xy(point_xy)
            if result is not None:
                return result[0]
        return None

    def _record_candidate_loss(
        self,
        candidate: ControllingOlsCandidate,
        competitor: ControllingOlsCandidate,
        losing_area: QgsGeometry,
        overlap: Optional[QgsGeometry],
        lower_region: Optional[QgsGeometry],
    ) -> None:
        loss_area = losing_area.area() if losing_area is not None and not losing_area.isEmpty() else 0.0
        if loss_area <= 1e-3:
            return
        overlap_area = overlap.area() if overlap is not None and not overlap.isEmpty() else 0.0
        lower_area = lower_region.area() if lower_region is not None and not lower_region.isEmpty() else None
        entries = self._candidate_loss_diagnostics.setdefault(candidate.surface_id, [])
        entries.append((loss_area, competitor.surface_id, competitor.surface_type, overlap_area, lower_area))
        entries.sort(key=lambda item: item[0], reverse=True)
        del entries[4:]

    def _record_candidate_unknown(
        self,
        candidate: ControllingOlsCandidate,
        competitor: ControllingOlsCandidate,
        overlap: Optional[QgsGeometry],
    ) -> None:
        overlap_area = overlap.area() if overlap is not None and not overlap.isEmpty() else 0.0
        if overlap_area <= 1e-3:
            return
        entries = self._candidate_unknown_diagnostics.setdefault(candidate.surface_id, [])
        entries.append((overlap_area, competitor.surface_id, competitor.surface_type))
        entries.sort(key=lambda item: item[0], reverse=True)
        del entries[4:]

    def _log_region_diagnostics(self, elapsed_seconds: float) -> None:
        if not self._diagnostics and not self._candidate_loss_diagnostics and not self._candidate_unknown_diagnostics:
            return
        lines = [f"Controlling OLS diagnostics: region solve elapsed={elapsed_seconds:.3f}s"]
        lines.extend(self._diagnostics[:40])
        for surface_id, entries in sorted(self._candidate_loss_diagnostics.items()):
            if not entries:
                continue
            formatted_entries = []
            for loss_area, competitor_id, competitor_type, overlap_area, lower_area in entries:
                lower_text = "None" if lower_area is None else f"{lower_area:.3f}"
                formatted_entries.append(
                    f"{competitor_id}({competitor_type}) loss={loss_area:.3f} "
                    f"overlap={overlap_area:.3f} lower={lower_text}"
                )
            lines.append(f"loss summary for {surface_id}: " + "; ".join(formatted_entries))
        for surface_id, entries in sorted(self._candidate_unknown_diagnostics.items()):
            if not entries:
                continue
            formatted_entries = [
                f"{competitor_id}({competitor_type}) overlap={overlap_area:.3f}"
                for overlap_area, competitor_id, competitor_type in entries
            ]
            lines.append(f"unknown comparison retained for {surface_id}: " + "; ".join(formatted_entries))
        QgsMessageLog.logMessage("\n".join(lines), PLUGIN_TAG, Qgis.Info)

    def _clip_lower_region_to_overlap(
        self,
        lower_region: QgsGeometry,
        overlap: QgsGeometry,
    ) -> Optional[QgsGeometry]:
        if lower_region is None or lower_region.isEmpty() or overlap is None or overlap.isEmpty():
            return None
        try:
            clipped = overlap.intersection(lower_region)
        except Exception:
            return lower_region
        return clipped if clipped is not None and not clipped.isEmpty() else QgsGeometry()

    def _effective_footprint(self, candidate: ControllingOlsCandidate) -> QgsGeometry:
        cached = self._effective_footprint_cache.get(candidate.surface_id)
        if cached is not None:
            return QgsGeometry(cached)
        footprint = QgsGeometry(candidate.footprint)
        for exclusion in self._exclusions_for_candidate(candidate):
            try:
                if exclusion.intersects(footprint):
                    footprint = footprint.difference(exclusion)
            except Exception:
                footprint = QgsGeometry()
                break
            if footprint is None or footprint.isEmpty():
                footprint = QgsGeometry()
                break
        self._effective_footprint_cache[candidate.surface_id] = QgsGeometry(footprint)
        return footprint

    def _exclusions_for_candidate(self, candidate: ControllingOlsCandidate) -> List[QgsGeometry]:
        """Return no-OLS exclusion masks that apply to this candidate surface."""
        if candidate.surface_type not in {"Approach", "IHS", "TOCS", "Transitional"}:
            return []
        return self.exclusion_geometries

    def _clean_region_polygon_parts(
        self,
        geometry: QgsGeometry,
        candidate: Optional[ControllingOlsCandidate] = None,
    ) -> List[QgsGeometry]:
        """Rebuild solved region polygons without changing solved boundaries."""
        if geometry is None or geometry.isEmpty():
            return []
        candidates = []
        despiked = self._despiked_polygon_geometry(geometry)
        if despiked is not None and not despiked.isEmpty():
            candidates.append(despiked)
        candidates.append(geometry)
        for candidate in candidates:
            try:
                if not candidate.isGeosValid():
                    candidate = candidate.makeValid()
            except Exception:
                continue
            parts = self._polygon_parts(candidate)
            if parts:
                return parts
        try:
            buffered = geometry.buffer(0.0, 8)
            if buffered is not None and not buffered.isEmpty():
                parts = self._polygon_parts(buffered)
                if parts:
                    return parts
        except Exception:
            pass
        return []

    def _despiked_polygon_geometry(self, geometry: QgsGeometry) -> Optional[QgsGeometry]:
        """Remove zero-width out-and-back ring spikes without buffering corners."""
        cleaned_parts = []
        changed = False
        try:
            polygons = geometry.asMultiPolygon() if geometry.isMultipart() else [geometry.asPolygon()]
        except Exception:
            return None
        for polygon in polygons:
            if not polygon or not polygon[0]:
                continue
            cleaned_polygon = []
            for ring_index, ring in enumerate(polygon):
                cleaned_ring, ring_changed = self._despiked_ring(ring)
                changed = changed or ring_changed
                if ring_index == 0:
                    if len(cleaned_ring) < 4:
                        cleaned_polygon = []
                        break
                    cleaned_polygon.append(cleaned_ring)
                elif len(cleaned_ring) >= 4:
                    cleaned_polygon.append(cleaned_ring)
            if cleaned_polygon:
                cleaned_parts.append(cleaned_polygon)
        if not cleaned_parts:
            return None
        if not changed:
            return QgsGeometry(geometry)
        if len(cleaned_parts) == 1:
            return QgsGeometry.fromPolygonXY(cleaned_parts[0])
        return QgsGeometry.fromMultiPolygonXY(cleaned_parts)

    def _despiked_ring(self, ring: List[QgsPointXY]) -> Tuple[List[QgsPointXY], bool]:
        if len(ring) < 4:
            return ring, False
        tolerance = 0.05
        angle_tolerance_degrees = 1.0
        points = ring[:-1] if ring[0].distance(ring[-1]) <= tolerance else list(ring)
        changed = False

        def _dedupe(vertices: List[QgsPointXY]) -> Tuple[List[QgsPointXY], bool]:
            deduped: List[QgsPointXY] = []
            did_change = False
            for point in vertices:
                if deduped and point.distance(deduped[-1]) <= tolerance:
                    did_change = True
                    continue
                deduped.append(point)
            if len(deduped) > 1 and deduped[0].distance(deduped[-1]) <= tolerance:
                deduped.pop()
                did_change = True
            return deduped, did_change

        points, did_change = _dedupe(points)
        changed = changed or did_change
        while len(points) >= 3:
            removed = False
            for index, point in enumerate(points):
                previous_point = points[index - 1]
                next_point = points[(index + 1) % len(points)]
                if previous_point.distance(next_point) <= tolerance:
                    points.pop(index)
                    changed = True
                    removed = True
                    break
                ux = previous_point.x() - point.x()
                uy = previous_point.y() - point.y()
                vx = next_point.x() - point.x()
                vy = next_point.y() - point.y()
                u_length = math.hypot(ux, uy)
                v_length = math.hypot(vx, vy)
                if u_length <= tolerance or v_length <= tolerance:
                    points.pop(index)
                    changed = True
                    removed = True
                    break
                cosine = max(-1.0, min(1.0, ((ux * vx) + (uy * vy)) / (u_length * v_length)))
                angle = math.degrees(math.acos(cosine))
                if angle <= angle_tolerance_degrees:
                    points.pop(index)
                    changed = True
                    removed = True
                    break
            if not removed:
                break
            points, did_change = _dedupe(points)
            changed = changed or did_change
        if len(points) < 3:
            return [], True
        cleaned = list(points)
        cleaned.append(cleaned[0])
        return cleaned, changed

    def _candidate_lower_region(
        self,
        candidate: ControllingOlsCandidate,
        competitor: ControllingOlsCandidate,
        overlap: Optional[QgsGeometry] = None,
    ) -> Optional[QgsGeometry]:
        """Return the geometry where candidate elevation is <= competitor elevation."""
        if candidate.model == "conical" or competitor.model == "conical":
            return self._curved_candidate_lower_region(candidate, competitor, overlap)
        return self._candidate_lower_halfplane(candidate, competitor, overlap)

    def _candidate_lower_halfplane(
        self,
        candidate: ControllingOlsCandidate,
        competitor: ControllingOlsCandidate,
        overlap: Optional[QgsGeometry] = None,
    ) -> Optional[QgsGeometry]:
        """Return a large polygon where candidate elevation is <= competitor elevation."""
        candidate_plane = self._linear_plane(candidate)
        competitor_plane = self._linear_plane(competitor)
        if candidate_plane is None or competitor_plane is None:
            return None

        return self._coefficient_lower_region(
            candidate_plane[0] - competitor_plane[0],
            candidate_plane[1] - competitor_plane[1],
            candidate_plane[2] - competitor_plane[2],
            overlap,
        )

    def _coefficient_lower_region(
        self,
        a: float,
        b: float,
        c: float,
        overlap: Optional[QgsGeometry] = None,
    ) -> Optional[QgsGeometry]:
        """Return a large polygon where ax + by + c <= tolerance."""
        if abs(a) <= 1e-12 and abs(b) <= 1e-12:
            return self._all_overlap_lower_region(overlap) if c <= self.tie_tolerance_m else QgsGeometry()

        sampled_differences = self._plane_difference_samples(overlap, a, b, c)
        if sampled_differences:
            max_diff = max(sampled_differences)
            min_diff = min(sampled_differences)
            if max_diff <= self.tie_tolerance_m:
                return self._all_overlap_lower_region(overlap)
            if min_diff > self.tie_tolerance_m:
                return QgsGeometry()

        point_on_line = self._point_on_line_near_geometry(overlap, a, b, c)
        if point_on_line is None:
            return None

        normal_length = math.hypot(a, b)
        nx = a / normal_length
        ny = b / normal_length
        dx = -ny
        dy = nx
        span = self._global_span()

        p1 = QgsPointXY(point_on_line.x() - (dx * span), point_on_line.y() - (dy * span))
        p2 = QgsPointXY(point_on_line.x() + (dx * span), point_on_line.y() + (dy * span))
        # The negative normal side has candidate - competitor <= 0.
        p3 = QgsPointXY(p2.x() - (nx * span * 2.0), p2.y() - (ny * span * 2.0))
        p4 = QgsPointXY(p1.x() - (nx * span * 2.0), p1.y() - (ny * span * 2.0))
        return QgsGeometry.fromPolygonXY([[p1, p2, p3, p4, p1]])

    def _curved_candidate_lower_region(
        self,
        candidate: ControllingOlsCandidate,
        competitor: ControllingOlsCandidate,
        overlap: Optional[QgsGeometry],
    ) -> Optional[QgsGeometry]:
        """Return conical-vs-planar lower geometry using IHS-offset buffer clips."""
        if overlap is None or overlap.isEmpty():
            return None
        if candidate.model == "conical" and competitor.model == "conical":
            return self._sampled_candidate_lower_region(candidate, competitor, overlap)
        if candidate.model == "conical":
            return self._conical_linear_lower_region(candidate, competitor, overlap, conical_is_candidate=True)
        if competitor.model == "conical":
            return self._conical_linear_lower_region(competitor, candidate, overlap, conical_is_candidate=False)
        return None

    def _conical_linear_lower_region(
        self,
        conical_candidate: ControllingOlsCandidate,
        linear_candidate: ControllingOlsCandidate,
        overlap: QgsGeometry,
        conical_is_candidate: bool,
    ) -> Optional[QgsGeometry]:
        conical_model = self._conical_model(conical_candidate)
        linear_plane = self._linear_plane(linear_candidate)
        if conical_model is None or linear_plane is None:
            return None

        if abs(linear_plane[0]) <= 1e-12 and abs(linear_plane[1]) <= 1e-12:
            return self._conical_constant_lower_region(
                conical_model,
                float(linear_plane[2]),
                overlap,
                conical_is_candidate,
            )

        if linear_candidate.model == "axis":
            return self._axis_conical_lower_region(
                conical_candidate,
                linear_candidate,
                overlap,
                conical_is_candidate,
            )

        return self._triangulated_candidate_lower_region(
            conical_candidate if conical_is_candidate else linear_candidate,
            linear_candidate if conical_is_candidate else conical_candidate,
            overlap,
        )

    def _axis_conical_lower_region(
        self,
        conical_candidate: ControllingOlsCandidate,
        axis_candidate: ControllingOlsCandidate,
        overlap: QgsGeometry,
        conical_is_candidate: bool,
    ) -> Optional[QgsGeometry]:
        """Resolve axis-rising surface vs conical by station, not by lateral TIN cuts."""
        axis = self._axis_model(axis_candidate)
        if axis is None or overlap is None or overlap.isEmpty():
            return None

        axis_lower = self._axis_lower_than_conical_region(axis_candidate, conical_candidate, axis, overlap)
        if not conical_is_candidate:
            return axis_lower

        if axis_lower is None:
            return None
        if axis_lower.isEmpty():
            return self._all_overlap_lower_region(overlap)
        try:
            conical_lower = overlap.difference(axis_lower)
        except Exception:
            return None
        return conical_lower if self._has_polygon_area(conical_lower) else None

    def _axis_lower_than_conical_region(
        self,
        axis_candidate: ControllingOlsCandidate,
        conical_candidate: ControllingOlsCandidate,
        axis: dict,
        overlap: QgsGeometry,
    ) -> Optional[QgsGeometry]:
        station_range = self._axis_station_range(axis, overlap)
        if station_range is None:
            return None
        min_station, max_station = station_range
        if max_station - min_station <= 1e-6:
            return None

        stations = self._axis_conical_sample_stations(axis, overlap, min_station, max_station)
        if len(stations) < 2:
            return None

        started_at = time.perf_counter()
        pieces: List[QgsGeometry] = []
        band_count = 0
        lower_count = 0
        higher_count = 0
        mixed_count = 0
        triangulated_count = 0
        triangulated_area = 0.0
        output_area = 0.0
        for start_station, end_station in zip(stations[:-1], stations[1:]):
            if end_station - start_station <= 1e-6:
                continue
            station_band = self._axis_station_interval_geometry(axis, start_station, end_station, overlap)
            if station_band is None or not self._has_polygon_area(station_band):
                continue
            band_count += 1
            decision = self._sampled_lower_decision(
                axis_candidate,
                conical_candidate,
                station_band,
            )
            if decision == "all_lower":
                pieces.append(station_band)
                lower_count += 1
                output_area += station_band.area()
                continue
            if decision == "all_higher":
                higher_count += 1
                continue
            mixed_count += 1
            lower_band = self._triangulated_candidate_lower_region(axis_candidate, conical_candidate, station_band)
            if lower_band is not None and self._has_polygon_area(lower_band):
                triangulated_count += 1
                lower_area = lower_band.area()
                triangulated_area += lower_area
                output_area += lower_area
                pieces.append(lower_band)
        if not pieces:
            fallback_decision, sample_count, min_difference, max_difference = self._sampled_lower_summary(
                axis_candidate,
                conical_candidate,
                overlap,
                all_higher_margin_m=2.0,
            )
            self._diagnostics.append(
                "axis/conical comparison produced no axis-lower area: "
                f"axis={axis_candidate.surface_id}; conical={conical_candidate.surface_id}; "
                f"overlap_area={overlap.area():.3f}; stations={len(stations)}; bands={band_count}; "
                f"lower={lower_count}; higher={higher_count}; mixed={mixed_count}; "
                f"triangulated={triangulated_count}; fallback={fallback_decision}; samples={sample_count}; "
                f"min_diff={min_difference if min_difference is not None else 'None'}; "
                f"max_diff={max_difference if max_difference is not None else 'None'}; "
                f"elapsed={time.perf_counter() - started_at:.3f}s"
            )
            if fallback_decision == "all_higher":
                return QgsGeometry()
            if fallback_decision == "all_lower":
                return QgsGeometry(overlap)
            return None
        try:
            combined = QgsGeometry.unaryUnion(pieces) if len(pieces) > 1 else QgsGeometry(pieces[0])
        except Exception:
            combined = None
        self._diagnostics.append(
            "axis/conical comparison: "
            f"axis={axis_candidate.surface_id}; conical={conical_candidate.surface_id}; "
            f"overlap_area={overlap.area():.3f}; result_area={combined.area() if combined is not None and not combined.isEmpty() else 0.0:.3f}; "
            f"stations={len(stations)}; bands={band_count}; lower={lower_count}; higher={higher_count}; "
            f"mixed={mixed_count}; triangulated={triangulated_count}; triangulated_area={triangulated_area:.3f}; "
            f"piece_area_sum={output_area:.3f}; elapsed={time.perf_counter() - started_at:.3f}s"
        )
        return combined if self._has_polygon_area(combined) else QgsGeometry()

    def _axis_station_range(self, axis: dict, geometry: QgsGeometry) -> Optional[Tuple[float, float]]:
        stations: List[float] = []
        for ring in self._polygon_boundary_parts(geometry):
            for point_xy in ring:
                stations.append(self._axis_station(axis, point_xy))
        if not stations:
            try:
                point = geometry.pointOnSurface().asPoint()
                stations.append(self._axis_station(axis, QgsPointXY(point.x(), point.y())))
            except Exception:
                return None
        max_distance = axis.get("max_distance_m")
        min_station = max(0.0, min(stations))
        max_station = max(stations)
        if max_distance is not None:
            max_station = min(float(max_distance), max_station)
        if max_station < min_station:
            return None
        return min_station, max_station

    def _axis_conical_sample_stations(
        self,
        axis: dict,
        geometry: QgsGeometry,
        min_station: float,
        max_station: float,
    ) -> List[float]:
        stations = {round(min_station, 6), round(max_station, 6)}
        for ring in self._densified_polygon_boundary_parts(geometry, max_segment_length=25.0):
            for point_xy in ring:
                station = self._axis_station(axis, point_xy)
                if min_station - 1e-6 <= station <= max_station + 1e-6:
                    stations.add(round(max(min_station, min(max_station, station)), 6))
        spacing = max(10.0, min((max_station - min_station) / 80.0, 50.0))
        station = min_station
        while station <= max_station + 1e-6:
            stations.add(round(max(min_station, min(max_station, station)), 6))
            station += spacing
        return sorted(stations)

    def _axis_station_interval_geometry(
        self,
        axis: dict,
        start_station: float,
        end_station: float,
        domain: QgsGeometry,
    ) -> Optional[QgsGeometry]:
        ux = float(axis["ux"])
        uy = float(axis["uy"])
        origin_dot = (float(axis["origin_x"]) * ux) + (float(axis["origin_y"]) * uy)
        lower_half = self._coefficient_lower_region(-ux, -uy, origin_dot + start_station, domain)
        upper_half = self._coefficient_lower_region(ux, uy, -(origin_dot + end_station), domain)
        if lower_half is None or upper_half is None:
            return None
        try:
            interval = domain.intersection(lower_half).intersection(upper_half)
        except Exception:
            return None
        return interval if self._has_polygon_area(interval) else None

    def _axis_station(self, axis: dict, point_xy: QgsPointXY) -> float:
        return ((point_xy.x() - float(axis["origin_x"])) * float(axis["ux"])) + (
            (point_xy.y() - float(axis["origin_y"])) * float(axis["uy"])
        )

    def _conical_constant_lower_region(
        self,
        conical_model: dict,
        constant_elevation: float,
        overlap: QgsGeometry,
        conical_is_candidate: bool,
    ) -> Optional[QgsGeometry]:
        threshold_distance = (constant_elevation - conical_model["base_elevation_m"]) / conical_model["slope"]
        max_distance = conical_model.get("max_distance_m")
        if max_distance is not None:
            max_distance = float(max_distance)
        if conical_is_candidate:
            if threshold_distance < -self.tie_tolerance_m:
                return QgsGeometry()
            if max_distance is not None and threshold_distance >= max_distance - 1e-6:
                return self._all_overlap_lower_region(overlap)
            return self._distance_region_from_conical_base(conical_model, max(0.0, threshold_distance), overlap)

        if threshold_distance < -self.tie_tolerance_m:
            return self._all_overlap_lower_region(overlap)
        if max_distance is not None and threshold_distance >= max_distance - 1e-6:
            return QgsGeometry()
        return self._conical_distance_lower_region(
            conical_model,
            max(0.0, threshold_distance),
            overlap,
            conical_is_candidate,
        )

    def _conical_distance_lower_region(
        self,
        conical_model: dict,
        threshold_distance: float,
        overlap: QgsGeometry,
        conical_is_candidate: bool,
    ) -> Optional[QgsGeometry]:
        max_distance = conical_model.get("max_distance_m")
        if max_distance is not None:
            max_distance = float(max_distance)
        threshold_distance = max(0.0, threshold_distance)
        if conical_is_candidate:
            if max_distance is not None and threshold_distance >= max_distance - 1e-6:
                return self._all_overlap_lower_region(overlap)
            return self._distance_region_from_conical_base(conical_model, threshold_distance, overlap)

        if max_distance is not None and threshold_distance >= max_distance - 1e-6:
            return QgsGeometry()
        lower_conical = self._distance_region_from_conical_base(conical_model, max(0.0, threshold_distance), overlap)
        if lower_conical is None or lower_conical.isEmpty():
            return self._all_overlap_lower_region(overlap)
        try:
            return overlap.difference(lower_conical)
        except Exception:
            return None

    def _distance_region_from_conical_base(
        self,
        conical_model: dict,
        distance_m: float,
        overlap: QgsGeometry,
    ) -> Optional[QgsGeometry]:
        try:
            distance_region = self._conical_buffer(conical_model, distance_m)
            if distance_region is None or distance_region.isEmpty():
                return None
            return overlap.intersection(distance_region)
        except Exception:
            return None

    def _conical_buffer(self, conical_model: dict, distance_m: float) -> Optional[QgsGeometry]:
        key = (str(conical_model.get("surface_id", "conical")), int(round(max(0.0, distance_m) * 1000.0)))
        cached = self._conical_buffer_cache.get(key)
        if cached is not None:
            return QgsGeometry(cached)
        try:
            buffered = conical_model["base_footprint"].buffer(max(0.0, distance_m), 48)
        except Exception:
            return None
        if buffered is not None and not buffered.isEmpty():
            self._conical_buffer_cache[key] = QgsGeometry(buffered)
        return buffered

    def _triangulated_candidate_lower_region(
        self,
        candidate: ControllingOlsCandidate,
        competitor: ControllingOlsCandidate,
        geometry: QgsGeometry,
    ) -> Optional[QgsGeometry]:
        points = self._triangulation_sample_points(geometry)
        if len(points) < 3:
            return None
        try:
            tin = QgsGeometry.fromMultiPointXY(points).delaunayTriangulation(0.0, False)
        except Exception:
            return None
        pieces: List[QgsGeometry] = []
        for triangle in self._polygon_parts(tin):
            try:
                clipped_triangle = triangle.intersection(geometry)
            except Exception:
                clipped_triangle = None
            for polygon_part in self._polygon_parts(clipped_triangle):
                for lower_ring in self._lower_polygon_rings(polygon_part, candidate, competitor):
                    if len(lower_ring) < 4:
                        continue
                    lower_geom = QgsGeometry.fromPolygonXY([lower_ring])
                    if lower_geom is not None and not lower_geom.isEmpty() and lower_geom.area() > 1e-3:
                        pieces.append(lower_geom)
        if not pieces:
            return None
        try:
            combined = QgsGeometry.unaryUnion(pieces)
        except Exception:
            combined = None
        if combined is not None and not combined.isEmpty():
            try:
                normalized = combined.buffer(0.0, 8)
                if normalized is not None and not normalized.isEmpty():
                    combined = normalized
            except Exception:
                pass
            try:
                combined = combined.intersection(geometry)
            except Exception:
                pass
        return combined if self._has_polygon_area(combined) else None

    def _lower_polygon_rings(
        self,
        geometry: QgsGeometry,
        candidate: ControllingOlsCandidate,
        competitor: ControllingOlsCandidate,
    ) -> List[List[QgsPointXY]]:
        rings: List[List[QgsPointXY]] = []
        try:
            polygons = geometry.asMultiPolygon() if geometry.isMultipart() else [geometry.asPolygon()]
        except Exception:
            return rings
        for polygon in polygons:
            if not polygon or not polygon[0]:
                continue
            clipped = self._clip_ring_by_elevation_difference(polygon[0], candidate, competitor)
            if len(clipped) >= 3:
                if clipped[0].distance(clipped[-1]) > 1e-6:
                    clipped.append(clipped[0])
                rings.append(clipped)
        return rings

    def _clip_ring_by_elevation_difference(
        self,
        ring: List[QgsPointXY],
        candidate: ControllingOlsCandidate,
        competitor: ControllingOlsCandidate,
    ) -> List[QgsPointXY]:
        points = ring[:-1] if len(ring) > 1 and ring[0].distance(ring[-1]) <= 1e-6 else ring
        if not points:
            return []
        output: List[QgsPointXY] = []
        previous_point = points[-1]
        previous_difference = self._candidate_difference(candidate, competitor, previous_point)
        previous_inside = previous_difference is not None and previous_difference <= self.tie_tolerance_m
        for current_point in points:
            current_difference = self._candidate_difference(candidate, competitor, current_point)
            current_inside = current_difference is not None and current_difference <= self.tie_tolerance_m
            if current_difference is None or previous_difference is None:
                if current_inside:
                    output.append(current_point)
                previous_point = current_point
                previous_difference = current_difference
                previous_inside = current_inside
                continue
            if current_inside != previous_inside:
                output.append(
                    self._interpolated_zero_crossing(
                        previous_point,
                        current_point,
                        previous_difference,
                        current_difference,
                    )
                )
            if current_inside:
                output.append(current_point)
            previous_point = current_point
            previous_difference = current_difference
            previous_inside = current_inside
        return output

    def _candidate_difference(
        self,
        candidate: ControllingOlsCandidate,
        competitor: ControllingOlsCandidate,
        point_xy: QgsPointXY,
    ) -> Optional[float]:
        candidate_elevation = candidate.elevation_at_xy(point_xy)
        competitor_elevation = competitor.elevation_at_xy(point_xy)
        candidate_valid = candidate_elevation is not None and math.isfinite(candidate_elevation)
        competitor_valid = competitor_elevation is not None and math.isfinite(competitor_elevation)
        if not candidate_valid and not competitor_valid:
            return None
        if not candidate_valid:
            return math.inf
        if not competitor_valid:
            return -math.inf
        return float(candidate_elevation) - float(competitor_elevation)

    def _interpolated_zero_crossing(
        self,
        start_point: QgsPointXY,
        end_point: QgsPointXY,
        start_difference: float,
        end_difference: float,
    ) -> QgsPointXY:
        denominator = abs(start_difference) + abs(end_difference)
        fraction = 0.5 if denominator <= 1e-12 else abs(start_difference) / denominator
        return QgsPointXY(
            start_point.x() + ((end_point.x() - start_point.x()) * fraction),
            start_point.y() + ((end_point.y() - start_point.y()) * fraction),
        )

    def _triangulation_sample_points(self, geometry: QgsGeometry) -> List[QgsPointXY]:
        points: List[QgsPointXY] = []
        seen = set()

        def _add(point_xy: QgsPointXY) -> None:
            key = (round(point_xy.x(), 3), round(point_xy.y(), 3))
            if key in seen:
                return
            seen.add(key)
            points.append(point_xy)

        for ring_points in self._densified_polygon_boundary_parts(geometry, max_segment_length=15.0):
            for point_xy in ring_points:
                _add(point_xy)
        try:
            bbox = geometry.boundingBox()
            spacing = max(15.0, min(max(bbox.width(), bbox.height()) / 35.0, 60.0))
            x = bbox.xMinimum()
            while x <= bbox.xMaximum() + 1e-6:
                y = bbox.yMinimum()
                while y <= bbox.yMaximum() + 1e-6:
                    point_xy = QgsPointXY(x, y)
                    if geometry.intersects(QgsGeometry.fromPointXY(point_xy)):
                        _add(point_xy)
                    y += spacing
                x += spacing
            point_on_surface = geometry.pointOnSurface()
            if point_on_surface is not None and not point_on_surface.isEmpty():
                point = point_on_surface.asPoint()
                _add(QgsPointXY(point.x(), point.y()))
        except Exception:
            pass
        return points

    def _densified_polygon_boundary_parts(
        self,
        geometry: QgsGeometry,
        max_segment_length: float = 25.0,
    ) -> List[List[QgsPointXY]]:
        densified_parts: List[List[QgsPointXY]] = []
        for ring in self._polygon_boundary_parts(geometry):
            if len(ring) < 2:
                continue
            densified: List[QgsPointXY] = []
            for start_point, end_point in zip(ring[:-1], ring[1:]):
                if not densified:
                    densified.append(start_point)
                length = start_point.distance(end_point)
                steps = max(1, int(math.ceil(length / max_segment_length)))
                for step in range(1, steps + 1):
                    fraction = step / steps
                    densified.append(
                        QgsPointXY(
                            start_point.x() + ((end_point.x() - start_point.x()) * fraction),
                            start_point.y() + ((end_point.y() - start_point.y()) * fraction),
                        )
                    )
            if len(densified) >= 2:
                densified_parts.append(densified)
        return densified_parts

    def _sampled_candidate_lower_region(
        self,
        candidate: ControllingOlsCandidate,
        competitor: ControllingOlsCandidate,
        overlap: QgsGeometry,
    ) -> Optional[QgsGeometry]:
        decision = self._sampled_lower_decision(candidate, competitor, overlap)
        if decision == "all_lower":
            return self._all_overlap_lower_region(overlap)
        if decision == "all_higher":
            return QgsGeometry()
        return None

    def _sampled_lower_decision(
        self,
        candidate: ControllingOlsCandidate,
        competitor: ControllingOlsCandidate,
        overlap: QgsGeometry,
        dense: bool = False,
        all_higher_margin_m: float = 0.0,
    ) -> str:
        return self._sampled_lower_summary(
            candidate,
            competitor,
            overlap,
            dense=dense,
            all_higher_margin_m=all_higher_margin_m,
        )[0]

    def _sampled_lower_summary(
        self,
        candidate: ControllingOlsCandidate,
        competitor: ControllingOlsCandidate,
        overlap: QgsGeometry,
        dense: bool = False,
        all_higher_margin_m: float = 0.0,
    ) -> Tuple[str, int, Optional[float], Optional[float]]:
        differences = []
        sample_points = self._geometry_sample_points(overlap)
        if dense:
            for ring_points in self._densified_polygon_boundary_parts(overlap, max_segment_length=5.0):
                sample_points.extend(ring_points)
        for point_xy in sample_points:
            difference = self._candidate_difference(candidate, competitor, point_xy)
            if difference is None:
                continue
            differences.append(difference)
        if not differences:
            return "unknown", 0, None, None
        min_difference = min(differences)
        max_difference = max(differences)
        if max_difference <= self.tie_tolerance_m:
            return "all_lower", len(differences), min_difference, max_difference
        if min_difference > self.tie_tolerance_m + max(0.0, all_higher_margin_m):
            return "all_higher", len(differences), min_difference, max_difference
        return "mixed", len(differences), min_difference, max_difference

    def _candidate_transition_lines(
        self,
        first_candidate: ControllingOlsCandidate,
        second_candidate: ControllingOlsCandidate,
    ) -> List[QgsGeometry]:
        try:
            overlap = first_candidate.footprint.intersection(second_candidate.footprint)
        except Exception:
            overlap = None
        if overlap is None or overlap.isEmpty():
            return []

        lines: List[QgsGeometry] = []
        for overlap_part in self._polygon_parts(overlap):
            line = self._equality_line_for_pair(overlap_part, first_candidate, second_candidate)
            if line is None or line.isEmpty():
                continue
            if self._line_separates_controllers(line, first_candidate, second_candidate):
                lines.append(line)
        return lines

    def _equality_line_for_pair(
        self,
        domain: QgsGeometry,
        first_candidate: ControllingOlsCandidate,
        second_candidate: ControllingOlsCandidate,
    ) -> Optional[QgsGeometry]:
        return self._plane_plane_line(domain, first_candidate, second_candidate)

    def _plane_plane_line(
        self,
        domain: QgsGeometry,
        first_candidate: ControllingOlsCandidate,
        second_candidate: ControllingOlsCandidate,
    ) -> Optional[QgsGeometry]:
        first_plane = self._linear_plane(first_candidate)
        second_plane = self._linear_plane(second_candidate)
        if first_plane is None or second_plane is None:
            return None

        a = first_plane[0] - second_plane[0]
        b = first_plane[1] - second_plane[1]
        c = first_plane[2] - second_plane[2]
        if abs(a) <= 1e-12 and abs(b) <= 1e-12:
            return None

        point_on_line = self._point_on_line_near_geometry(domain, a, b, c)
        if point_on_line is None:
            return None
        return self._clip_long_line_to_domain(domain, point_on_line, -b, a)

    def _axis_constant_line(
        self,
        domain: QgsGeometry,
        axis_candidate: ControllingOlsCandidate,
        constant_candidate: ControllingOlsCandidate,
    ) -> Optional[QgsGeometry]:
        axis = self._axis_model(axis_candidate)
        constant_elevation = self._constant_elevation(constant_candidate)
        if axis is None or constant_elevation is None or abs(axis["slope"]) <= 1e-12:
            return None

        station = (constant_elevation - axis["origin_elevation_m"]) / axis["slope"]
        max_distance = axis.get("max_distance_m")
        if station < -1e-6:
            return None
        if max_distance is not None and station > max_distance + 1e-6:
            return None

        point_on_axis = QgsPointXY(
            axis["origin_x"] + (axis["ux"] * station),
            axis["origin_y"] + (axis["uy"] * station),
        )
        return self._clip_long_line_to_domain(domain, point_on_axis, -axis["uy"], axis["ux"])

    def _axis_axis_line(
        self,
        domain: QgsGeometry,
        first_candidate: ControllingOlsCandidate,
        second_candidate: ControllingOlsCandidate,
    ) -> Optional[QgsGeometry]:
        first_axis = self._axis_model(first_candidate)
        second_axis = self._axis_model(second_candidate)
        if first_axis is None or second_axis is None:
            return None

        a = (first_axis["slope"] * first_axis["ux"]) - (second_axis["slope"] * second_axis["ux"])
        b = (first_axis["slope"] * first_axis["uy"]) - (second_axis["slope"] * second_axis["uy"])
        c = (
            first_axis["origin_elevation_m"]
            - (first_axis["slope"] * ((first_axis["origin_x"] * first_axis["ux"]) + (first_axis["origin_y"] * first_axis["uy"])))
            - second_axis["origin_elevation_m"]
            + (second_axis["slope"] * ((second_axis["origin_x"] * second_axis["ux"]) + (second_axis["origin_y"] * second_axis["uy"])))
        )

        if abs(a) <= 1e-12 and abs(b) <= 1e-12:
            return None

        if abs(a) >= abs(b):
            point_on_line = QgsPointXY(-c / a, 0.0)
        else:
            point_on_line = QgsPointXY(0.0, -c / b)
        return self._clip_long_line_to_domain(domain, point_on_line, -b, a)

    def _line_separates_controllers(
        self,
        line: QgsGeometry,
        first_candidate: ControllingOlsCandidate,
        second_candidate: ControllingOlsCandidate,
    ) -> bool:
        expected_ids = {first_candidate.surface_id, second_candidate.surface_id}
        for points in self._line_parts(line):
            for start_point, end_point in zip(points[:-1], points[1:]):
                dx = end_point.x() - start_point.x()
                dy = end_point.y() - start_point.y()
                length = math.hypot(dx, dy)
                if length <= 1e-6:
                    continue
                mid_point = QgsPointXY((start_point.x() + end_point.x()) / 2.0, (start_point.y() + end_point.y()) / 2.0)
                nx = -dy / length
                ny = dx / length
                offset = max(min(length * 0.05, 5.0), 0.5)
                left = self.controlling_candidate_at_xy(QgsPointXY(mid_point.x() + nx * offset, mid_point.y() + ny * offset))
                right = self.controlling_candidate_at_xy(QgsPointXY(mid_point.x() - nx * offset, mid_point.y() - ny * offset))
                if left is None or right is None:
                    continue
                observed_ids = {left[0].surface_id, right[0].surface_id}
                if observed_ids == expected_ids and left[0].surface_id != right[0].surface_id:
                    return True
        return False

    def _transition_z_values(
        self,
        line_points: List[QgsPointXY],
        first_candidate: ControllingOlsCandidate,
        second_candidate: ControllingOlsCandidate,
    ) -> List[float]:
        values: List[float] = []
        for point_xy in line_points:
            elevations = []
            for candidate in (first_candidate, second_candidate):
                elevation = candidate.elevation_at_xy(point_xy)
                if elevation is not None and math.isfinite(elevation):
                    elevations.append(float(elevation))
            values.append(sum(elevations) / len(elevations) if elevations else 0.0)
        return values

    def _line_key(
        self,
        line_points: List[QgsPointXY],
        first_surface_id: str,
        second_surface_id: str,
    ) -> Tuple[str, str, Tuple[Tuple[int, int], ...]]:
        surface_ids = tuple(sorted([first_surface_id, second_surface_id]))
        rounded_points = tuple((round(point.x(), 3), round(point.y(), 3)) for point in line_points)
        reversed_points = tuple(reversed(rounded_points))
        canonical_points = rounded_points if rounded_points <= reversed_points else reversed_points
        integer_points = tuple((int(round(x * 1000)), int(round(y * 1000))) for x, y in canonical_points)
        return surface_ids[0], surface_ids[1], integer_points

    def _has_polygon_area(self, geometry: Optional[QgsGeometry], min_area: float = 1e-3) -> bool:
        if geometry is None or geometry.isEmpty():
            return False
        try:
            for part in self._polygon_parts(geometry):
                if part.area() > min_area:
                    return True
        except Exception:
            return False
        return False

    def _point_on_line_near_geometry(
        self,
        geometry: Optional[QgsGeometry],
        a: float,
        b: float,
        c: float,
    ) -> Optional[QgsPointXY]:
        normal_squared = (a * a) + (b * b)
        if normal_squared <= 1e-24:
            return None
        if geometry is not None and not geometry.isEmpty():
            bbox = geometry.boundingBox()
        elif self.bounds is not None and not self.bounds.isEmpty():
            bbox = self.bounds
        else:
            return None
        center_x = (bbox.xMinimum() + bbox.xMaximum()) / 2.0
        center_y = (bbox.yMinimum() + bbox.yMaximum()) / 2.0
        signed_distance_factor = ((a * center_x) + (b * center_y) + c) / normal_squared
        return QgsPointXY(
            center_x - (a * signed_distance_factor),
            center_y - (b * signed_distance_factor),
        )

    def _plane_difference_samples(
        self,
        geometry: Optional[QgsGeometry],
        a: float,
        b: float,
        c: float,
    ) -> List[float]:
        if geometry is None or geometry.isEmpty():
            return []
        sample_points: List[QgsPointXY] = []
        try:
            for polygon_part in self._polygon_parts(geometry):
                point_on_surface = polygon_part.pointOnSurface()
                if point_on_surface is not None and not point_on_surface.isEmpty():
                    point = point_on_surface.asPoint()
                    sample_points.append(QgsPointXY(point.x(), point.y()))
                bbox = polygon_part.boundingBox()
                for fx, fy in [(0.0, 0.0), (0.0, 1.0), (1.0, 0.0), (1.0, 1.0), (0.5, 0.5)]:
                    point_xy = QgsPointXY(
                        bbox.xMinimum() + (bbox.width() * fx),
                        bbox.yMinimum() + (bbox.height() * fy),
                    )
                    if polygon_part.intersects(QgsGeometry.fromPointXY(point_xy)):
                        sample_points.append(point_xy)
                polygons = polygon_part.asMultiPolygon() if polygon_part.isMultipart() else [polygon_part.asPolygon()]
                for polygon in polygons:
                    for ring in polygon:
                        sample_points.extend(QgsPointXY(point.x(), point.y()) for point in ring)
        except Exception:
            return []
        return [(a * point.x()) + (b * point.y()) + c for point in sample_points]

    def _clip_long_line_to_domain(
        self,
        domain: QgsGeometry,
        point_on_line: QgsPointXY,
        direction_x: float,
        direction_y: float,
    ) -> Optional[QgsGeometry]:
        direction_length = math.hypot(direction_x, direction_y)
        if domain is None or domain.isEmpty() or direction_length <= 1e-12:
            return None
        direction_x /= direction_length
        direction_y /= direction_length
        bbox = domain.boundingBox()
        length = max(bbox.width(), bbox.height(), 1.0) * 4.0
        line = QgsGeometry.fromPolylineXY(
            [
                QgsPointXY(point_on_line.x() - (direction_x * length), point_on_line.y() - (direction_y * length)),
                QgsPointXY(point_on_line.x() + (direction_x * length), point_on_line.y() + (direction_y * length)),
            ]
        )
        clipped = line.intersection(domain)
        return clipped if clipped is not None and not clipped.isEmpty() else None

    def _axis_model(self, candidate: ControllingOlsCandidate) -> Optional[dict]:
        try:
            azimuth = math.radians(float(candidate.metadata["azimuth_degrees"]))
            max_distance_raw = candidate.metadata.get("max_distance_m")
            return {
                "origin_x": float(candidate.metadata["origin_x"]),
                "origin_y": float(candidate.metadata["origin_y"]),
                "origin_elevation_m": float(candidate.metadata["origin_elevation_m"]),
                "slope": float(candidate.metadata["slope"]),
                "max_distance_m": float(max_distance_raw) if max_distance_raw is not None else None,
                "ux": math.sin(azimuth),
                "uy": math.cos(azimuth),
            }
        except (KeyError, TypeError, ValueError):
            return None

    def _conical_model(self, candidate: ControllingOlsCandidate) -> Optional[dict]:
        try:
            base_footprint = candidate.metadata["base_footprint"]
            if base_footprint is None or base_footprint.isEmpty():
                return None
            max_distance_raw = candidate.metadata.get("max_distance_m")
            return {
                "surface_id": candidate.surface_id,
                "base_footprint": QgsGeometry(base_footprint),
                "base_elevation_m": float(candidate.metadata["base_elevation_m"]),
                "slope": float(candidate.metadata["slope"]),
                "max_distance_m": float(max_distance_raw) if max_distance_raw is not None else None,
            }
        except (KeyError, TypeError, ValueError, AttributeError):
            return None

    def _linear_plane(self, candidate: ControllingOlsCandidate) -> Optional[Tuple[float, float, float]]:
        """Return z = ax + by + c for supported planar candidates."""
        if candidate.model == "constant":
            elevation = self._constant_elevation(candidate)
            return (0.0, 0.0, elevation) if elevation is not None else None
        if candidate.model != "axis":
            if candidate.model == "plane":
                try:
                    return (
                        float(candidate.metadata["plane_a"]),
                        float(candidate.metadata["plane_b"]),
                        float(candidate.metadata["plane_c"]),
                    )
                except (KeyError, TypeError, ValueError):
                    return None
            return None
        axis = self._axis_model(candidate)
        if axis is None:
            return None
        a = axis["slope"] * axis["ux"]
        b = axis["slope"] * axis["uy"]
        c = axis["origin_elevation_m"] - (
            axis["slope"] * ((axis["origin_x"] * axis["ux"]) + (axis["origin_y"] * axis["uy"]))
        )
        return (a, b, c)

    def _constant_elevation(self, candidate: ControllingOlsCandidate) -> Optional[float]:
        try:
            return float(candidate.metadata["elevation_m"])
        except (KeyError, TypeError, ValueError):
            return None

    def _line_points_to_z_geometry(self, points: List[QgsPointXY], z_values: List[float]) -> Optional[QgsGeometry]:
        if len(points) < 2 or len(points) != len(z_values):
            return None
        line = QgsLineString()
        for point_xy, z_value in zip(points, z_values):
            line.addVertex(QgsPoint(point_xy.x(), point_xy.y(), z_value))
        geometry = QgsGeometry(line)
        return geometry if geometry is not None and not geometry.isEmpty() else None

    def _geometry_elevation_range(
        self,
        geometry: QgsGeometry,
        candidate: ControllingOlsCandidate,
    ) -> Tuple[Optional[float], Optional[float]]:
        sample_points = self._geometry_sample_points(geometry)
        values = []
        for point_xy in sample_points:
            elevation = candidate.elevation_at_xy(point_xy)
            if elevation is not None and math.isfinite(elevation):
                values.append(float(elevation))
        return (min(values), max(values)) if values else (None, None)

    def _geometry_sample_points(self, geometry: QgsGeometry) -> List[QgsPointXY]:
        sample_points: List[QgsPointXY] = []
        try:
            point_on_surface = geometry.pointOnSurface()
            if point_on_surface is not None and not point_on_surface.isEmpty():
                point = point_on_surface.asPoint()
                sample_points.append(QgsPointXY(point.x(), point.y()))
            bbox = geometry.boundingBox()
            for fx, fy in [(0.25, 0.25), (0.25, 0.75), (0.75, 0.25), (0.75, 0.75), (0.5, 0.5)]:
                point_xy = QgsPointXY(
                    bbox.xMinimum() + (bbox.width() * fx),
                    bbox.yMinimum() + (bbox.height() * fy),
                )
                if geometry.intersects(QgsGeometry.fromPointXY(point_xy)):
                    sample_points.append(point_xy)
            for polygon_part in self._polygon_parts(geometry):
                polygons = polygon_part.asMultiPolygon() if polygon_part.isMultipart() else [polygon_part.asPolygon()]
                for polygon in polygons:
                    for ring in polygon:
                        sample_points.extend(QgsPointXY(point.x(), point.y()) for point in ring)
        except Exception:
            return []
        return sample_points

    def _combined_bounds(self, candidates: Iterable[ControllingOlsCandidate]) -> Optional[QgsRectangle]:
        combined: Optional[QgsRectangle] = None
        for candidate in candidates:
            try:
                candidate_bounds = candidate.footprint.boundingBox()
            except Exception:
                continue
            if combined is None:
                combined = QgsRectangle(candidate_bounds)
            else:
                combined.combineExtentWith(candidate_bounds)
        return combined

    def _global_span(self) -> float:
        if self.bounds is None or self.bounds.isEmpty():
            return 100000.0
        return max(self.bounds.width(), self.bounds.height(), 1.0) * 8.0

    def _global_extent_polygon(self) -> QgsGeometry:
        if self.bounds is None or self.bounds.isEmpty():
            span = self._global_span()
            return QgsGeometry.fromPolygonXY(
                [[QgsPointXY(-span, -span), QgsPointXY(span, -span), QgsPointXY(span, span), QgsPointXY(-span, span), QgsPointXY(-span, -span)]]
            )
        span = self._global_span()
        return QgsGeometry.fromPolygonXY(
            [
                [
                    QgsPointXY(self.bounds.xMinimum() - span, self.bounds.yMinimum() - span),
                    QgsPointXY(self.bounds.xMaximum() + span, self.bounds.yMinimum() - span),
                    QgsPointXY(self.bounds.xMaximum() + span, self.bounds.yMaximum() + span),
                    QgsPointXY(self.bounds.xMinimum() - span, self.bounds.yMaximum() + span),
                    QgsPointXY(self.bounds.xMinimum() - span, self.bounds.yMinimum() - span),
                ]
            ]
        )

    def _all_overlap_lower_region(self, overlap: Optional[QgsGeometry]) -> QgsGeometry:
        if overlap is not None and self._has_polygon_area(overlap):
            return QgsGeometry(overlap)
        return self._global_extent_polygon()

    def _line_parts(self, geometry: QgsGeometry) -> List[List[QgsPointXY]]:
        if geometry is None or geometry.isEmpty():
            return []
        try:
            if geometry.type() == QgsWkbTypes.LineGeometry:
                if geometry.isMultipart():
                    return [part for part in geometry.asMultiPolyline() if len(part) >= 2]
                line = geometry.asPolyline()
                return [line] if len(line) >= 2 else []
            if hasattr(geometry, "asGeometryCollection"):
                parts: List[List[QgsPointXY]] = []
                for part_geom in geometry.asGeometryCollection():
                    parts.extend(self._line_parts(part_geom))
                return parts
        except Exception:
            return []
        return []

    def _polygon_parts(self, geometry: Optional[QgsGeometry]) -> List[QgsGeometry]:
        if geometry is None or geometry.isEmpty():
            return []
        parts: List[QgsGeometry] = []
        try:
            if not geometry.isGeosValid():
                geometry = geometry.makeValid()
            if geometry is None or geometry.isEmpty():
                return []
            if geometry.type() == QgsWkbTypes.PolygonGeometry:
                if geometry.isMultipart():
                    for polygon in geometry.asMultiPolygon():
                        part = QgsGeometry.fromPolygonXY(polygon)
                        if part is not None and not part.isEmpty() and part.area() > 1e-3:
                            parts.append(part)
                else:
                    parts.append(geometry)
            elif hasattr(geometry, "asGeometryCollection"):
                for part_geom in geometry.asGeometryCollection():
                    parts.extend(self._polygon_parts(part_geom))
        except Exception:
            return []
        return parts


class ControllingOlsEngineMixin:
    """Register planar OLS candidates and emit milestone-1 controlling outputs."""

    def _reset_controlling_ols_engine(self) -> None:
        self._controlling_ols_candidates: List[ControllingOlsCandidate] = []
        self._controlling_ols_exclusion_geometries: List[QgsGeometry] = []

    def _register_controlling_ols_candidate(self, candidate: ControllingOlsCandidate) -> None:
        if candidate.footprint is None or candidate.footprint.isEmpty():
            return
        if not hasattr(self, "_controlling_ols_candidates"):
            self._reset_controlling_ols_engine()
        self._controlling_ols_candidates.append(candidate)

    def _register_controlling_ols_exclusion_geometry(self, geometry: QgsGeometry) -> None:
        if geometry is None or geometry.isEmpty():
            return
        if not hasattr(self, "_controlling_ols_exclusion_geometries"):
            self._controlling_ols_exclusion_geometries = []
        self._controlling_ols_exclusion_geometries.append(QgsGeometry(geometry))

    def _create_controlling_ols_planar_poc_layers(
        self,
        icao_code: str,
        layer_group: QgsLayerTreeGroup,
    ) -> bool:
        candidates = list(getattr(self, "_controlling_ols_candidates", []) or [])
        exclusion_geometries = list(getattr(self, "_controlling_ols_exclusion_geometries", []) or [])
        planar_candidates = [
            candidate
            for candidate in candidates
            if candidate.model in {"constant", "axis", "plane", "conical"}
        ]
        if not planar_candidates:
            QgsMessageLog.logMessage(
                "Controlling OLS planar POC skipped: no planar candidate surfaces were registered.",
                PLUGIN_TAG,
                Qgis.Info,
            )
            return False

        output_group = self._controlling_ols_poc_group(layer_group)
        candidate_layer_ok = self._create_controlling_candidate_layer(icao_code, output_group, planar_candidates)
        region_layer_ok = self._create_controlling_region_layer(icao_code, output_group, planar_candidates, exclusion_geometries)
        transition_layer_ok = self._create_controlling_transition_layer(icao_code, output_group, planar_candidates, exclusion_geometries)
        return candidate_layer_ok or region_layer_ok or transition_layer_ok

    def _controlling_ols_poc_group(self, layer_group: QgsLayerTreeGroup) -> QgsLayerTreeGroup:
        group_name = self.tr("Controlling OLS POC")
        if layer_group is not None and layer_group.name() == group_name:
            return layer_group
        return self._ensure_controlling_ols_poc_group(layer_group, group_name) or layer_group

    def _ensure_controlling_ols_poc_group(
        self,
        parent_group: QgsLayerTreeGroup,
        group_name: str,
    ) -> Optional[QgsLayerTreeGroup]:
        """Keep the POC group as a top-level generated group after NASF."""
        if parent_group is None:
            return None

        existing_group = self._find_direct_child_group(parent_group, group_name)
        children = list(parent_group.children())

        nasf_group = None
        for child in children:
            if isinstance(child, QgsLayerTreeGroup) and child.name() == self.tr("04 NASF Safeguarding Guidelines"):
                nasf_group = child
                break
        target_index = children.index(nasf_group) + 1 if nasf_group is not None else len(children)

        if existing_group is None:
            try:
                output_group = parent_group.insertGroup(target_index, group_name)
            except AttributeError:
                output_group = parent_group.addGroup(group_name)
            self._stage_layer_tree_node(output_group)
            return output_group

        try:
            current_index = children.index(existing_group)
        except ValueError:
            return existing_group
        if current_index == target_index:
            return existing_group

        cloned_group = existing_group.clone()
        self._stage_layer_tree_node(cloned_group)
        parent_group.insertChildNode(target_index, cloned_group)
        parent_group.removeChildNode(existing_group)
        return cloned_group

    def _create_controlling_candidate_layer(
        self,
        icao_code: str,
        output_group: QgsLayerTreeGroup,
        candidates: Sequence[ControllingOlsCandidate],
    ) -> bool:
        fields = QgsFields(
            [
                QgsField("surface_id", QVariant.String, self.tr("Surface ID"), 160),
                QgsField("surface", QVariant.String, self.tr("Surface Type"), 50),
                QgsField("model", QVariant.String, self.tr("Model"), 30),
                QgsField("elev_min", QVariant.Double, self.tr("Min Elev AMSL"), 12, 3),
                QgsField("elev_max", QVariant.Double, self.tr("Max Elev AMSL"), 12, 3),
            ]
        )
        features: List[QgsFeature] = []
        for candidate in candidates:
            feature = QgsFeature(fields)
            feature.setGeometry(QgsGeometry(candidate.footprint))
            min_elev, max_elev = self._candidate_elevation_range(candidate)
            feature.setAttributes([candidate.surface_id, candidate.surface_type, candidate.model, min_elev, max_elev])
            features.append(feature)

        layer = self._create_and_add_layer(
            "Polygon",
            f"OLS_Controlling_Planar_Candidates_{icao_code}",
            f"{self.tr('OLS')} Controlling Planar Candidates POC {icao_code}",
            fields,
            features,
            output_group,
            "Default Polygon",
        )
        if layer is not None:
            QgsMessageLog.logMessage(
                f"Created controlling OLS planar candidate POC with {len(candidates)} candidate surface(s).",
                PLUGIN_TAG,
                Qgis.Info,
            )
            return True
        return False

    def _create_controlling_region_layer(
        self,
        icao_code: str,
        output_group: QgsLayerTreeGroup,
        candidates: Sequence[ControllingOlsCandidate],
        exclusion_geometries: Sequence[QgsGeometry],
    ) -> bool:
        fields = QgsFields(
            [
                QgsField("region_id", QVariant.Int, self.tr("Region ID"), 10),
                QgsField("surface_id", QVariant.String, self.tr("Surface ID"), 160),
                QgsField("surface", QVariant.String, self.tr("Surface Type"), 50),
                QgsField("model", QVariant.String, self.tr("Model"), 30),
                QgsField("elev_min", QVariant.Double, self.tr("Min Elev AMSL"), 12, 3),
                QgsField("elev_max", QVariant.Double, self.tr("Max Elev AMSL"), 12, 3),
                QgsField("method", QVariant.String, self.tr("Method"), 50),
            ]
        )
        engine = PlanarControllingOlsEngine(candidates, exclusion_geometries=exclusion_geometries)
        features = engine.region_features(fields)
        if not features:
            QgsMessageLog.logMessage(
                "Controlling OLS planar regions POC skipped: no controlling planar regions were produced.",
                PLUGIN_TAG,
                Qgis.Info,
            )
            return False
        feature_count = len(features)
        layer = self._create_and_add_layer(
            "Polygon",
            f"OLS_Controlling_Planar_Regions_{icao_code}",
            f"{self.tr('OLS')} Controlling Planar Regions POC {icao_code}",
            fields,
            features,
            output_group,
            "OLS Controlling Planar Region",
        )
        if layer is not None:
            QgsMessageLog.logMessage(
                f"Created controlling OLS planar regions POC with {feature_count} region feature(s).",
                PLUGIN_TAG,
                Qgis.Info,
            )
            return True
        return False

    def _create_controlling_transition_layer(
        self,
        icao_code: str,
        output_group: QgsLayerTreeGroup,
        candidates: Sequence[ControllingOlsCandidate],
        exclusion_geometries: Sequence[QgsGeometry],
    ) -> bool:
        fields = QgsFields(
            [
                QgsField("transition_id", QVariant.String, self.tr("Transition ID"), 160),
                QgsField("surface", QVariant.String, self.tr("Surface"), 50),
                QgsField("elev_min", QVariant.Double, self.tr("Min Elev AMSL"), 12, 3),
                QgsField("elev_max", QVariant.Double, self.tr("Max Elev AMSL"), 12, 3),
                QgsField("adjacent", QVariant.String, self.tr("Adjacent Surfaces"), 254),
                QgsField("method", QVariant.String, self.tr("Method"), 50),
            ]
        )
        engine = PlanarControllingOlsEngine(candidates, exclusion_geometries=exclusion_geometries)
        features = engine.region_boundary_features(fields)
        features = self._deduplicate_controlling_transition_features(features)
        if not features:
            QgsMessageLog.logMessage(
                "Controlling OLS planar transition POC skipped: no region boundary transition edges were produced.",
                PLUGIN_TAG,
                Qgis.Info,
            )
            return False
        feature_count = len(features)
        layer = self._create_and_add_layer(
            "LineStringZ",
            f"OLS_Controlling_Planar_Transitions_{icao_code}",
            f"{self.tr('OLS')} Controlling Planar Transitions POC {icao_code}",
            fields,
            features,
            output_group,
            "Default Line",
        )
        if layer is not None:
            QgsMessageLog.logMessage(
                f"Created controlling OLS planar transition POC with {feature_count} region boundary edge(s).",
                PLUGIN_TAG,
                Qgis.Info,
            )
            return True
        return False

    def _deduplicate_controlling_transition_features(self, features: List[QgsFeature]) -> List[QgsFeature]:
        deduplicated: List[QgsFeature] = []
        seen = set()
        for feature in features:
            geom = feature.geometry()
            if geom is None or geom.isEmpty():
                continue
            try:
                key = geom.asWkt(3)
            except Exception:
                key = str(id(feature))
            adjacent = feature.attribute("adjacent") if feature.fields().indexFromName("adjacent") != -1 else None
            compound_key = (adjacent, key)
            if compound_key in seen:
                continue
            seen.add(compound_key)
            deduplicated.append(feature)
        return deduplicated

    def _candidate_elevation_range(self, candidate: ControllingOlsCandidate) -> Tuple[Optional[float], Optional[float]]:
        if candidate.model == "constant":
            try:
                elevation = float(candidate.metadata["elevation_m"])
                return elevation, elevation
            except (KeyError, TypeError, ValueError):
                return None, None
        if candidate.model == "axis":
            try:
                origin_elevation = float(candidate.metadata["origin_elevation_m"])
                slope = float(candidate.metadata["slope"])
                max_distance = float(candidate.metadata["max_distance_m"])
                end_elevation = origin_elevation + (slope * max_distance)
                return min(origin_elevation, end_elevation), max(origin_elevation, end_elevation)
            except (KeyError, TypeError, ValueError):
                return None, None
        sample_points: List[QgsPointXY] = []
        try:
            point_on_surface = candidate.footprint.pointOnSurface()
            if point_on_surface is not None and not point_on_surface.isEmpty():
                point = point_on_surface.asPoint()
                sample_points.append(QgsPointXY(point.x(), point.y()))
            if candidate.footprint.type() == QgsWkbTypes.PolygonGeometry:
                polygons = candidate.footprint.asMultiPolygon() if candidate.footprint.isMultipart() else [candidate.footprint.asPolygon()]
                for polygon in polygons:
                    if polygon and polygon[0]:
                        sample_points.extend(QgsPointXY(point.x(), point.y()) for point in polygon[0])
            bbox = candidate.footprint.boundingBox()
            sample_points.extend(
                [
                    QgsPointXY(bbox.xMinimum(), bbox.yMinimum()),
                    QgsPointXY(bbox.xMinimum(), bbox.yMaximum()),
                    QgsPointXY(bbox.xMaximum(), bbox.yMinimum()),
                    QgsPointXY(bbox.xMaximum(), bbox.yMaximum()),
                    QgsPointXY((bbox.xMinimum() + bbox.xMaximum()) / 2.0, (bbox.yMinimum() + bbox.yMaximum()) / 2.0),
                ]
            )
        except Exception:
            return None, None
        values = []
        for point_xy in sample_points:
            if not candidate.contains_xy(point_xy):
                continue
            elevation = candidate.elevation_at_xy(point_xy)
            if elevation is not None and math.isfinite(elevation):
                values.append(float(elevation))
        return (min(values), max(values)) if values else (None, None)
