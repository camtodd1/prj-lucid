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
COMPARISON_COLLINEAR_BACKTRACK_ANGLE_DEGREES = 0.1
COMPARISON_SPIKE_MAX_AREA_CHANGE_RATIO = 0.01
COMPARISON_SPIKE_MAX_AREA_CHANGE_M2 = 25.0
COMPARISON_DELTA_DECIMALS = 3
COMPARISON_CONTOUR_INTERVAL_M = 0.5
COMPARISON_PRIMARY_CONTOUR_INTERVAL_M = 1.0
COMPARISON_CONTOUR_MIN_LENGTH_M = 0.01


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
                overlap = self._safe_intersection(baseline_region, future_region)
                if not self._has_area(overlap):
                    continue
                self._append_classified_overlap(
                    result,
                    baseline_candidate,
                    future_candidate,
                    overlap,
                )
        self._finalise_comparison_parts(result)
        # Final cleanup can legitimately remove split artefacts.  Repair the
        # remaining common domain afterwards so that cleanup cannot leave a
        # valid comparison region unclassified.
        self._append_common_domain_gap_parts(result, baseline_regions, future_regions)
        self._merge_classified_parts(result)
        # Pair-level dissolves re-check the height-sign invariant and can trim
        # narrow residual strips. Repair once more after that destructive pass;
        # do not merge again, because doing so would repeat the same clipping.
        self._append_common_domain_gap_parts(result, baseline_regions, future_regions)
        self._append_final_common_domain_remainders(result, baseline_regions, future_regions)
        self._partition_classified_parts(result)
        return result

    def _append_classified_overlap(
        self,
        result,
        baseline_candidate: ControllingOlsCandidate,
        future_candidate: ControllingOlsCandidate,
        overlap: QgsGeometry,
        clean_spikes: bool = True,
        include_transition: bool = True,
    ) -> None:
        """Classify one controller-pair overlap without losing mixed fallback areas."""
        if not self._has_area(overlap):
            return
        if self._append_no_change_if_equal(
            result["no_change"],
            baseline_candidate,
            future_candidate,
            overlap,
            clean_spikes=clean_spikes,
        ):
            return

        pair_engine = PlanarControllingOlsEngine([baseline_candidate, future_candidate])
        affine_regions = self._affine_change_regions(
            pair_engine,
            baseline_candidate,
            future_candidate,
            overlap,
        )
        if affine_regions is not None:
            gain_geometry, loss_geometry, no_change_geometry = affine_regions
            self._append_parts(
                result["gain"], baseline_candidate, future_candidate, gain_geometry, "gain", clean_spikes
            )
            self._append_parts(
                result["loss"], baseline_candidate, future_candidate, loss_geometry, "loss", clean_spikes
            )
            self._append_parts(
                result["no_change"],
                baseline_candidate,
                future_candidate,
                no_change_geometry,
                "no_change",
                clean_spikes,
            )
            if include_transition:
                self._append_transition_parts(
                    result["transition"],
                    pair_engine,
                    baseline_candidate,
                    future_candidate,
                    overlap,
                    gain_geometry,
                    loss_geometry,
                )
            return

        # A higher future surface is a gain, so the baseline is the lower
        # candidate on the gain side of the equality boundary.
        try:
            baseline_lower = pair_engine._candidate_lower_region(
                baseline_candidate,
                future_candidate,
                overlap,
            )
        except Exception:
            baseline_lower = None
        if baseline_lower is None:
            baseline_lower = self._fallback_lower_region(
                pair_engine,
                baseline_candidate,
                future_candidate,
                overlap,
            )
        if baseline_lower is None:
            self._append_sampled_whole_overlap(
                result,
                baseline_candidate,
                future_candidate,
                overlap,
                clean_spikes=clean_spikes,
            )
            return

        if baseline_lower.isEmpty():
            future_lower = QgsGeometry(overlap)
        else:
            baseline_lower = self._safe_intersection(baseline_lower, overlap)
            if baseline_lower is None:
                self._append_sampled_whole_overlap(
                    result,
                    baseline_candidate,
                    future_candidate,
                    overlap,
                    clean_spikes=clean_spikes,
                )
                return
            future_lower = self._safe_difference(overlap, baseline_lower)
            if future_lower is None:
                self._append_sampled_whole_overlap(
                    result,
                    baseline_candidate,
                    future_candidate,
                    overlap,
                    clean_spikes=clean_spikes,
                )
                return

        self._append_parts(
            result["gain"], baseline_candidate, future_candidate, baseline_lower, "gain", clean_spikes
        )
        self._append_parts(
            result["loss"], baseline_candidate, future_candidate, future_lower, "loss", clean_spikes
        )
        self._append_parts(
            result["no_change"],
            baseline_candidate,
            future_candidate,
            baseline_lower,
            "no_change",
            clean_spikes,
        )
        self._append_parts(
            result["no_change"],
            baseline_candidate,
            future_candidate,
            future_lower,
            "no_change",
            clean_spikes,
        )
        if include_transition:
            self._append_transition_parts(
                result["transition"],
                pair_engine,
                baseline_candidate,
                future_candidate,
                overlap,
                baseline_lower,
                future_lower,
            )

    def _affine_change_regions(
        self,
        pair_engine: PlanarControllingOlsEngine,
        baseline: ControllingOlsCandidate,
        future: ControllingOlsCandidate,
        overlap: QgsGeometry,
    ) -> Optional[Tuple[QgsGeometry, QgsGeometry, QgsGeometry]]:
        """Split an affine comparison exactly into gain, loss and tolerance band."""
        baseline_plane = self._candidate_affine_coefficients(baseline)
        future_plane = self._candidate_affine_coefficients(future)
        if baseline_plane is None or future_plane is None:
            return None
        delta_min, delta_max, _delta_sample = self.delta_range(overlap, baseline, future)
        if delta_min is None or delta_max is None:
            return None
        if delta_min > self.tolerance_m:
            return QgsGeometry(overlap), QgsGeometry(), QgsGeometry()
        if delta_max < -self.tolerance_m:
            return QgsGeometry(), QgsGeometry(overlap), QgsGeometry()
        if delta_min >= -self.tolerance_m and delta_max <= self.tolerance_m:
            return QgsGeometry(), QgsGeometry(), QgsGeometry(overlap)

        coefficients = tuple(
            future_plane[index] - baseline_plane[index]
            for index in range(3)
        )
        threshold_lines = []
        for level in (-self.tolerance_m, self.tolerance_m):
            line = self._affine_change_contour(overlap, coefficients, level)
            if line is not None and not line.isEmpty():
                threshold_lines.append(line)
        if not threshold_lines:
            return None
        try:
            thresholds = (
                QgsGeometry.unaryUnion(threshold_lines)
                if len(threshold_lines) > 1
                else threshold_lines[0]
            )
            split_parts = pair_engine._split_overlap_by_transition_curve(overlap, thresholds)
        except Exception:
            return None
        if len(split_parts) <= 1:
            return None

        classified = {"gain": [], "loss": [], "no_change": []}
        for part in split_parts:
            point = part.pointOnSurface().asPoint()
            delta = self._delta_at_point(QgsPointXY(point.x(), point.y()), baseline, future)
            if delta is None:
                continue
            change = (
                "gain"
                if delta > self.tolerance_m
                else "loss"
                if delta < -self.tolerance_m
                else "no_change"
            )
            classified[change].append(part)
        gain_geometry = self._union_geometries(classified["gain"])
        loss_geometry = self._union_geometries(classified["loss"])
        no_change_geometry = self._union_geometries(classified["no_change"])
        gain = gain_geometry if gain_geometry is not None else QgsGeometry()
        loss = loss_geometry if loss_geometry is not None else QgsGeometry()
        no_change = no_change_geometry if no_change_geometry is not None else QgsGeometry()
        coverage = self._union_geometries([gain, loss, no_change])
        if coverage is None:
            return None
        remainder = self._safe_difference(overlap, coverage)
        if remainder is not None and self._has_area(remainder):
            return None
        return gain, loss, no_change

    def _fallback_lower_region(
        self,
        pair_engine: PlanarControllingOlsEngine,
        baseline_candidate: ControllingOlsCandidate,
        future_candidate: ControllingOlsCandidate,
        overlap: QgsGeometry,
    ) -> Optional[QgsGeometry]:
        """Resolve an otherwise unresolved overlap with dense tests and a local TIN."""
        try:
            decision = pair_engine._sampled_lower_decision(
                baseline_candidate,
                future_candidate,
                overlap,
                dense=True,
            )
        except Exception:
            decision = None
        if decision == "all_lower":
            return QgsGeometry(overlap)
        if decision == "all_higher":
            return QgsGeometry()
        try:
            triangulated = pair_engine._triangulated_candidate_lower_region(
                baseline_candidate,
                future_candidate,
                overlap,
            )
        except Exception:
            triangulated = None
        return self._safe_intersection(triangulated, overlap) if triangulated is not None else None

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
                remaining = self._safe_difference(baseline_region, future_union)
                if remaining is None:
                    continue
                tolerant_remaining = (
                    self._safe_difference(baseline_region, future_coverage)
                    if future_coverage is not None and not future_coverage.isEmpty()
                    else QgsGeometry(remaining)
                )
                if tolerant_remaining is None:
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
        # The first sample is pointOnSurface().  It is an interior classification
        # sample only; it is not an area-weighted or otherwise representative value.
        return min(values), max(values), values[0]

    def change_contour_parts(
        self,
        parts: Sequence[Tuple[ControllingOlsCandidate, ControllingOlsCandidate, QgsGeometry]],
        change: str,
        interval_m: float = COMPARISON_CONTOUR_INTERVAL_M,
        primary_interval_m: float = COMPARISON_PRIMARY_CONTOUR_INTERVAL_M,
    ) -> List[
        Tuple[
            ControllingOlsCandidate,
            ControllingOlsCandidate,
            QgsGeometry,
            float,
            str,
            int,
        ]
    ]:
        """Return signed change isolines clipped to finalized gain/loss polygons."""
        if change not in {"gain", "loss"}:
            return []
        try:
            interval_m = float(interval_m)
            primary_interval_m = float(primary_interval_m)
        except (TypeError, ValueError):
            return []
        if interval_m <= 0.0 or primary_interval_m <= 0.0:
            return []

        contours = []
        for parent_sequence, (baseline, future, geometry) in enumerate(parts, start=1):
            baseline_plane = self._candidate_affine_coefficients(baseline)
            future_plane = self._candidate_affine_coefficients(future)
            generated: List[Tuple[float, QgsGeometry]] = []
            if baseline_plane is not None and future_plane is not None:
                delta_min, delta_max, _delta_sample = self.delta_range(
                    geometry,
                    baseline,
                    future,
                    change,
                )
                if delta_min is None or delta_max is None:
                    continue
                coefficients = tuple(
                    future_plane[index] - baseline_plane[index]
                    for index in range(3)
                )
                for delta_m in self._change_contour_levels(delta_min, delta_max, interval_m):
                    contour = self._affine_change_contour(geometry, coefficients, delta_m)
                    if contour is not None:
                        generated.append((delta_m, contour))
            else:
                generated = self._triangulated_change_contours(
                    geometry,
                    baseline,
                    future,
                    interval_m=interval_m,
                )

            for delta_m, contour in generated:
                if contour is None or contour.isEmpty() or contour.length() <= COMPARISON_CONTOUR_MIN_LENGTH_M:
                    continue
                ratio = delta_m / primary_interval_m
                contour_class = (
                    "primary"
                    if abs(ratio - round(ratio)) <= 10 ** (-COMPARISON_DELTA_DECIMALS)
                    else "intermediate"
                )
                contours.append(
                    (baseline, future, contour, delta_m, contour_class, parent_sequence)
                )
        return contours

    def _change_contour_levels(
        self,
        delta_min: float,
        delta_max: float,
        interval_m: float,
    ) -> List[float]:
        lower = min(float(delta_min), float(delta_max))
        upper = max(float(delta_min), float(delta_max))
        start = int(math.ceil((lower - self.tolerance_m) / interval_m))
        end = int(math.floor((upper + self.tolerance_m) / interval_m))
        levels: List[float] = []
        for multiple in range(start, end + 1):
            level = self._round_delta(multiple * interval_m)
            if abs(level) <= self.tolerance_m:
                continue
            if level < lower - self.tolerance_m or level > upper + self.tolerance_m:
                continue
            levels.append(level)
        return levels

    def _change_contour_geometry(
        self,
        geometry: QgsGeometry,
        baseline: ControllingOlsCandidate,
        future: ControllingOlsCandidate,
        delta_m: float,
    ) -> Optional[QgsGeometry]:
        baseline_plane = self._candidate_affine_coefficients(baseline)
        future_plane = self._candidate_affine_coefficients(future)
        if baseline_plane is not None and future_plane is not None:
            coefficients = tuple(
                future_plane[index] - baseline_plane[index]
                for index in range(3)
            )
            return self._affine_change_contour(geometry, coefficients, delta_m)
        return self._triangulated_change_contour(geometry, baseline, future, delta_m)

    @staticmethod
    def _candidate_affine_coefficients(
        candidate: ControllingOlsCandidate,
    ) -> Optional[Tuple[float, float, float]]:
        metadata = candidate.metadata or {}
        try:
            if candidate.model == "plane":
                return (
                    float(metadata["plane_a"]),
                    float(metadata["plane_b"]),
                    float(metadata["plane_c"]),
                )
            if candidate.model == "axis":
                azimuth = math.radians(float(metadata["azimuth_degrees"]))
                slope = float(metadata["slope"])
                a = slope * math.sin(azimuth)
                b = slope * math.cos(azimuth)
                origin_x = float(metadata["origin_x"])
                origin_y = float(metadata["origin_y"])
                origin_z = float(metadata["origin_elevation_m"])
                return a, b, origin_z - (a * origin_x) - (b * origin_y)
            if candidate.model == "constant":
                elevation = metadata.get("elevation_m")
                if elevation is None:
                    point_geometry = candidate.footprint.pointOnSurface()
                    if point_geometry is None or point_geometry.isEmpty():
                        return None
                    point = point_geometry.asPoint()
                    elevation = candidate.elevation_at_xy(QgsPointXY(point.x(), point.y()))
                if elevation is not None and math.isfinite(float(elevation)):
                    return 0.0, 0.0, float(elevation)
        except (KeyError, TypeError, ValueError, RuntimeError):
            return None
        return None

    def _affine_change_contour(
        self,
        geometry: QgsGeometry,
        coefficients: Tuple[float, float, float],
        delta_m: float,
    ) -> Optional[QgsGeometry]:
        a, b, c = coefficients
        gradient_squared = (a * a) + (b * b)
        if gradient_squared <= 1e-18:
            return None
        bbox = geometry.boundingBox()
        centre_x = (bbox.xMinimum() + bbox.xMaximum()) / 2.0
        centre_y = (bbox.yMinimum() + bbox.yMaximum()) / 2.0
        displacement = (float(delta_m) - ((a * centre_x) + (b * centre_y) + c)) / gradient_squared
        origin = QgsPointXY(centre_x + (a * displacement), centre_y + (b * displacement))
        gradient_length = math.sqrt(gradient_squared)
        direction_x = -b / gradient_length
        direction_y = a / gradient_length
        extent = max(math.hypot(bbox.width(), bbox.height()) * 2.0, 1.0)
        line = QgsGeometry.fromPolylineXY(
            [
                QgsPointXY(origin.x() - (direction_x * extent), origin.y() - (direction_y * extent)),
                QgsPointXY(origin.x() + (direction_x * extent), origin.y() + (direction_y * extent)),
            ]
        )
        try:
            clipped = line.intersection(geometry)
        except Exception:
            return None
        return self._merged_change_contour_lines([clipped])

    def _triangulated_change_contour(
        self,
        geometry: QgsGeometry,
        baseline: ControllingOlsCandidate,
        future: ControllingOlsCandidate,
        delta_m: float,
    ) -> Optional[QgsGeometry]:
        contours = self._triangulated_change_contours(
            geometry,
            baseline,
            future,
            requested_levels=[float(delta_m)],
        )
        return contours[0][1] if contours else None

    def _triangulated_change_contours(
        self,
        geometry: QgsGeometry,
        baseline: ControllingOlsCandidate,
        future: ControllingOlsCandidate,
        interval_m: float = COMPARISON_CONTOUR_INTERVAL_M,
        requested_levels: Optional[Sequence[float]] = None,
    ) -> List[Tuple[float, QgsGeometry]]:
        points = self.baseline_engine._triangulation_sample_points(geometry)
        if len(points) < 3:
            return []

        value_cache: Dict[Tuple[float, float], Optional[float]] = {}

        def _value(point: QgsPointXY) -> Optional[float]:
            key = (round(point.x(), 3), round(point.y(), 3))
            if key not in value_cache:
                value_cache[key] = self._delta_at_point(point, baseline, future)
            return value_cache[key]

        if requested_levels is None:
            sampled_values = [value for value in (_value(point) for point in points) if value is not None]
            if not sampled_values:
                return []
            levels = self._change_contour_levels(
                min(sampled_values),
                max(sampled_values),
                interval_m,
            )
        else:
            levels = sorted({self._round_delta(level) for level in requested_levels})
        if not levels:
            return []

        try:
            triangles = QgsGeometry.fromMultiPointXY(points).delaunayTriangulation(0.0, False)
        except Exception:
            return []
        prepared_geometry = None
        try:
            prepared_geometry = QgsGeometry.createGeometryEngine(geometry.constGet())
            prepared_geometry.prepareGeometry()
        except Exception:
            prepared_geometry = None
        segments_by_level: Dict[float, List[QgsGeometry]] = {level: [] for level in levels}
        for triangle in self.baseline_engine._polygon_parts(triangles):
            try:
                ring = triangle.asPolygon()[0]
            except (IndexError, TypeError):
                continue
            triangle_points = [QgsPointXY(point) for point in ring[:3]]
            if len(triangle_points) < 3:
                continue
            values = [_value(point) for point in triangle_points]
            if any(value is None for value in values):
                continue
            numeric_values = [float(value) for value in values]
            triangle_min = min(numeric_values)
            triangle_max = max(numeric_values)
            for level in levels:
                if level < triangle_min - 1e-9 or level > triangle_max + 1e-9:
                    continue
                for segment in self._triangle_change_contour_segments(
                    triangle_points,
                    numeric_values,
                    level,
                ):
                    try:
                        wholly_inside = bool(
                            prepared_geometry is not None
                            and prepared_geometry.contains(segment.constGet())
                        )
                        clipped = segment if wholly_inside else segment.intersection(geometry)
                    except Exception:
                        try:
                            clipped = segment.intersection(geometry)
                        except Exception:
                            clipped = segment
                    if clipped is not None and not clipped.isEmpty():
                        segments_by_level[level].append(clipped)
        contours: List[Tuple[float, QgsGeometry]] = []
        for level in levels:
            merged = self._merged_change_contour_lines(segments_by_level[level])
            if merged is not None and not merged.isEmpty():
                contours.append((level, merged))
        return contours

    @staticmethod
    def _triangle_change_contour_segments(
        points: Sequence[QgsPointXY],
        values: Sequence[float],
        delta_m: float,
    ) -> List[QgsGeometry]:
        epsilon = 1e-9
        crossings: List[QgsPointXY] = []
        coincident: List[QgsGeometry] = []

        def _add_crossing(point: QgsPointXY) -> None:
            if any(point.distance(existing) <= 1e-7 for existing in crossings):
                return
            crossings.append(QgsPointXY(point))

        for start_index, end_index in ((0, 1), (1, 2), (2, 0)):
            start_point = points[start_index]
            end_point = points[end_index]
            start_difference = values[start_index] - delta_m
            end_difference = values[end_index] - delta_m
            start_is_level = abs(start_difference) <= epsilon
            end_is_level = abs(end_difference) <= epsilon
            if start_is_level and end_is_level:
                coincident.append(QgsGeometry.fromPolylineXY([start_point, end_point]))
                continue
            if start_is_level:
                _add_crossing(start_point)
            elif end_is_level:
                _add_crossing(end_point)
            elif start_difference * end_difference < 0.0:
                denominator = abs(start_difference) + abs(end_difference)
                fraction = 0.5 if denominator <= epsilon else abs(start_difference) / denominator
                _add_crossing(
                    QgsPointXY(
                        start_point.x() + ((end_point.x() - start_point.x()) * fraction),
                        start_point.y() + ((end_point.y() - start_point.y()) * fraction),
                    )
                )
        if coincident:
            return coincident
        if len(crossings) < 2:
            return []
        if len(crossings) > 2:
            crossings = max(
                (
                    [first, second]
                    for first_index, first in enumerate(crossings)
                    for second in crossings[first_index + 1 :]
                ),
                key=lambda pair: pair[0].distance(pair[1]),
            )
        return [QgsGeometry.fromPolylineXY(crossings[:2])]

    @classmethod
    def _merged_change_contour_lines(
        cls,
        geometries: Sequence[QgsGeometry],
    ) -> Optional[QgsGeometry]:
        line_parts: List[QgsGeometry] = []
        for geometry in geometries:
            for part in cls._line_parts(geometry):
                if part.length() > COMPARISON_CONTOUR_MIN_LENGTH_M:
                    line_parts.append(part)
        if not line_parts:
            return None
        try:
            merged = QgsGeometry.unaryUnion(line_parts) if len(line_parts) > 1 else line_parts[0]
        except Exception:
            merged = line_parts[0]
        try:
            line_merged = merged.mergeLines()
            if line_merged is not None and not line_merged.isEmpty():
                merged = line_merged
        except Exception:
            pass
        return merged

    def _append_sampled_whole_overlap(
        self,
        result,
        baseline,
        future,
        overlap,
        clean_spikes: bool = True,
    ) -> None:
        delta_min, delta_max, delta_sample = self.delta_range(overlap, baseline, future)
        if delta_sample is None:
            return
        if delta_min is not None and delta_min > self.tolerance_m:
            self._append_parts(result["gain"], baseline, future, overlap, "gain", clean_spikes)
        elif delta_max is not None and delta_max < -self.tolerance_m:
            self._append_parts(result["loss"], baseline, future, overlap, "loss", clean_spikes)
        elif (
            delta_min is not None
            and delta_max is not None
            and abs(delta_min) <= self.tolerance_m
            and abs(delta_max) <= self.tolerance_m
        ):
            self._append_parts(result["no_change"], baseline, future, overlap, "no_change", clean_spikes)

    def _append_no_change_if_equal(
        self,
        destination,
        baseline,
        future,
        overlap,
        clean_spikes: bool = True,
    ) -> bool:
        delta_min, delta_max, _delta_sample = self.delta_range(overlap, baseline, future)
        if delta_min is None or delta_max is None:
            return False
        if abs(delta_min) > self.tolerance_m or abs(delta_max) > self.tolerance_m:
            return False
        self._append_parts(destination, baseline, future, overlap, "no_change", clean_spikes)
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
            delta_min, delta_max, delta_sample = self.delta_range(part, baseline, future, change)
            if delta_sample is None:
                continue
            if change == "gain":
                if delta_sample <= self.tolerance_m:
                    continue
            if change == "loss":
                if delta_sample >= -self.tolerance_m:
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
        classified_geometries = [
            geometry
            for change in ("gain", "loss", "no_change")
            for _baseline, _future, geometry in result.get(change, [])
            if geometry is not None and not geometry.isEmpty()
        ]
        classified_union = self._union_geometries(classified_geometries)
        # Repair within each original controller-pair overlap.  A union-wide
        # remainder may span several controlling regions; assigning one sampled
        # controller pair to that whole polygon is the source of dropped and
        # incorrectly attributed comparison features.
        for baseline_candidate, baseline_region in baseline_regions:
            for future_candidate, future_region in future_regions:
                if not self._bounding_boxes_intersect(baseline_region, future_region):
                    continue
                pair_domain = self._safe_intersection(baseline_region, future_region)
                if not self._has_area(pair_domain):
                    continue
                pair_remainder = (
                    self._safe_difference(pair_domain, classified_union)
                    if classified_union is not None and not classified_union.isEmpty()
                    else QgsGeometry(pair_domain)
                )
                if not self._has_area(pair_remainder):
                    continue
                for part in self.baseline_engine._polygon_parts(pair_remainder):
                    if not self._has_area(part):
                        continue
                    self._append_classified_overlap(
                        result,
                        baseline_candidate,
                        future_candidate,
                        part,
                        clean_spikes=False,
                        include_transition=False,
                    )

    def _append_final_common_domain_remainders(
        self,
        result,
        baseline_regions: Sequence[Tuple[ControllingOlsCandidate, QgsGeometry]],
        future_regions: Sequence[Tuple[ControllingOlsCandidate, QgsGeometry]],
    ) -> None:
        """Assign numerical residuals after all destructive cleanup has finished."""
        baseline_union = self._union_geometries([geometry for _candidate, geometry in baseline_regions])
        future_union = self._union_geometries([geometry for _candidate, geometry in future_regions])
        if baseline_union is None or future_union is None:
            return
        common_domain = self._safe_intersection(baseline_union, future_union)
        classified_union = self._union_geometries(
            [
                geometry
                for change in ("gain", "loss", "no_change")
                for _baseline, _future, geometry in result.get(change, [])
            ]
        )
        remaining = (
            self._safe_difference(common_domain, classified_union)
            if classified_union is not None
            else common_domain
        )
        if not self._has_area(remaining):
            return

        for baseline, baseline_region in baseline_regions:
            if not self._has_area(remaining):
                break
            for future, future_region in future_regions:
                if not self._has_area(remaining):
                    break
                if not self._bounding_boxes_intersect(baseline_region, future_region):
                    continue
                pair_domain = self._safe_intersection(baseline_region, future_region)
                pair_remaining = self._safe_intersection(remaining, pair_domain)
                if not self._has_area(pair_remaining):
                    continue
                assigned_parts = []
                for part in self.baseline_engine._polygon_parts(pair_remaining):
                    change = self._classify_change_for_part(part, baseline, future)
                    if change is None:
                        continue
                    result[change].append((baseline, future, QgsGeometry(part)))
                    assigned_parts.append(part)
                assigned = self._union_geometries(assigned_parts)
                if assigned is not None:
                    remaining = self._safe_difference(remaining, assigned)

    def _partition_classified_parts(self, result) -> None:
        """Remove repair overlap without changing the combined classified coverage."""
        assigned = QgsGeometry()
        # No-change is inclusive at +/- tolerance, so it owns numerical overlap
        # on those boundaries before the strict gain/loss classes are applied.
        for change in ("no_change", "gain", "loss"):
            partitioned = []
            for baseline, future, geometry in result.get(change, []):
                if not self._has_area(geometry):
                    continue
                unique = (
                    self._safe_difference(geometry, assigned)
                    if not assigned.isEmpty()
                    else QgsGeometry(geometry)
                )
                if not self._has_area(unique):
                    continue
                for part in self.baseline_engine._polygon_parts(unique):
                    if not self._has_area(part):
                        continue
                    partitioned.append((baseline, future, QgsGeometry(part)))
                if assigned.isEmpty():
                    assigned = QgsGeometry(unique)
                else:
                    merged_assigned = self._union_geometries([assigned, unique])
                    if merged_assigned is not None:
                        assigned = merged_assigned
            result[change] = partitioned

    def _merge_classified_parts(self, result) -> None:
        """Dissolve repaired fragments so spike remainders join their proper side."""
        for change in ("gain", "loss", "no_change"):
            grouped: Dict[Tuple[str, str], list] = {}
            controllers: Dict[Tuple[str, str], Tuple[ControllingOlsCandidate, ControllingOlsCandidate]] = {}
            for baseline, future, geometry in result.get(change, []):
                if not self._has_area(geometry):
                    continue
                key = (baseline.surface_id, future.surface_id)
                grouped.setdefault(key, []).append(geometry)
                controllers[key] = (baseline, future)
            merged_parts = []
            for key, geometries in grouped.items():
                merged = self._union_geometries(geometries)
                if not self._has_area(merged):
                    continue
                baseline, future = controllers[key]
                for part in self.baseline_engine._polygon_parts(merged):
                    if not self._has_area(part):
                        continue
                    classified = self._clip_geometry_to_change(part, baseline, future, change)
                    for classified_part in self.baseline_engine._polygon_parts(classified):
                        if not self._has_area(classified_part):
                            continue
                        delta_min, delta_max, delta_sample = self.delta_range(
                            classified_part,
                            baseline,
                            future,
                            change,
                        )
                        if delta_sample is None:
                            continue
                        if change == "gain" and delta_sample <= self.tolerance_m:
                            continue
                        if change == "loss" and delta_sample >= -self.tolerance_m:
                            continue
                        if change == "no_change" and (
                            delta_min is None
                            or delta_max is None
                            or abs(delta_min) > self.tolerance_m
                            or abs(delta_max) > self.tolerance_m
                        ):
                            continue
                        merged_parts.append((baseline, future, QgsGeometry(classified_part)))
            result[change] = merged_parts

    def _clip_geometry_to_change(
        self,
        geometry: QgsGeometry,
        baseline: ControllingOlsCandidate,
        future: ControllingOlsCandidate,
        change: str,
    ) -> QgsGeometry:
        """Enforce the height-sign invariant on a final gain or loss polygon."""
        if geometry is None or geometry.isEmpty() or change not in {"gain", "loss"}:
            return geometry
        lower_candidate, upper_candidate = (
            (baseline, future) if change == "gain" else (future, baseline)
        )
        pair_engine = PlanarControllingOlsEngine([lower_candidate, upper_candidate])
        try:
            decision = pair_engine._sampled_lower_decision(
                lower_candidate,
                upper_candidate,
                geometry,
                dense=True,
            )
        except Exception:
            decision = None
        if decision == "all_lower":
            return geometry
        if decision == "all_higher":
            return QgsGeometry()

        try:
            lower_region = pair_engine._candidate_lower_region(
                lower_candidate,
                upper_candidate,
                geometry,
            )
        except Exception:
            lower_region = None
        if lower_region is not None:
            if lower_region.isEmpty():
                return QgsGeometry()
            clipped = self._safe_intersection(geometry, lower_region)
            if self._has_area(clipped):
                # The direct lower-region solver is exact for supported linear
                # and conical pairings. Trust that equation-based clip instead
                # of densifying it through an unnecessary triangulation pass.
                return clipped
        else:
            clipped = None

        # Curved or topologically awkward rings can remain mixed after an
        # unresolved analytic comparison. Rebuild only that residual part from
        # locally clipped triangles; this is independent of map scale/CRS.
        source = geometry
        try:
            triangulated = pair_engine._triangulated_candidate_lower_region(
                lower_candidate,
                upper_candidate,
                source,
            )
        except Exception:
            triangulated = None
        triangulated = self._safe_intersection(source, triangulated) if triangulated is not None else None
        if self._has_area(triangulated):
            return triangulated
        return clipped if clipped is not None else geometry

    def _finalise_comparison_parts(self, result) -> None:
        """Apply final geometry hygiene before common-domain coverage repair."""
        for change in ("gain", "loss", "no_change"):
            final_parts = []
            for baseline, future, geometry in result.get(change, []):
                cleaned = self._clean_comparison_part(geometry, baseline, future, change)
                if not self._has_area(cleaned):
                    continue
                delta_min, delta_max, delta_sample = self.delta_range(
                    cleaned,
                    baseline,
                    future,
                    change,
                )
                if delta_sample is None:
                    continue
                if change == "gain" and delta_sample <= self.tolerance_m:
                    continue
                if change == "loss" and delta_sample >= -self.tolerance_m:
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
        delta_min, delta_max, delta_sample = self.delta_range(
            geometry,
            baseline_candidate,
            future_candidate,
        )
        if delta_sample is None:
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
        if delta_sample > self.tolerance_m:
            return "gain"
        if delta_sample < -self.tolerance_m:
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
        try:
            source_geometry = QgsGeometry(geometry)
            if not source_geometry.isGeosValid():
                source_geometry = source_geometry.makeValid()
            cleaned = cleaned.intersection(source_geometry)
            if cleaned is not None and not cleaned.isEmpty() and not cleaned.isGeosValid():
                cleaned = cleaned.makeValid()
        except Exception:
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
        _detour_ratio, angle_degrees, _height, _base_length = metrics
        current_delta = self._delta_at_point(current_point, baseline, future)
        previous_delta = self._delta_at_point(previous_point, baseline, future)
        next_delta = self._delta_at_point(next_point, baseline, future)
        neighbour_values = [
            value for value in (previous_delta, next_delta)
            if value is not None and math.isfinite(value)
        ]
        # GEOS polygon differences can retain a zero-area boundary tendril: the
        # ring overshoots onto the wrong side of the equality boundary and then
        # reverses along the same line.  Its 0-degree turn is definitive, so it
        # must not be constrained by the general spike base-length thresholds.
        if (
            angle_degrees <= COMPARISON_COLLINEAR_BACKTRACK_ANGLE_DEGREES
            and current_delta is not None
            and neighbour_values
        ):
            if change == "loss" and current_delta > self.tolerance_m and any(
                value <= self.tolerance_m for value in neighbour_values
            ):
                return "backtrack"
            if change == "gain" and current_delta < -self.tolerance_m and any(
                value >= -self.tolerance_m for value in neighbour_values
            ):
                return "backtrack"
            if change == "no_change" and abs(current_delta) > self.tolerance_m and any(
                abs(value) <= self.tolerance_m for value in neighbour_values
            ):
                return "backtrack"
        if self._is_severe_comparison_spike_shape(metrics):
            return "severe"
        if not self._is_delta_comparison_spike_shape(metrics):
            return None
        if current_delta is None:
            return None
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

    def _prepare_overlay_geometry(self, geometry: Optional[QgsGeometry]) -> Optional[QgsGeometry]:
        """Return valid polygonal geometry suitable for a retrying GEOS overlay."""
        if geometry is None or geometry.isEmpty():
            return geometry
        prepared = QgsGeometry(geometry)
        try:
            if not prepared.isGeosValid():
                prepared = prepared.makeValid()
        except Exception:
            pass
        parts = self.baseline_engine._polygon_parts(prepared)
        if not parts:
            return None
        try:
            prepared = QgsGeometry.unaryUnion(parts) if len(parts) > 1 else QgsGeometry(parts[0])
        except Exception:
            prepared = QgsGeometry(parts[0])
            for part in parts[1:]:
                try:
                    combined = prepared.combine(part)
                    if combined is not None and not combined.isEmpty():
                        prepared = combined
                except Exception:
                    continue
        try:
            if prepared is not None and not prepared.isEmpty() and not prepared.isGeosValid():
                prepared = prepared.makeValid()
        except Exception:
            pass
        return prepared

    def _safe_intersection(
        self,
        first: Optional[QgsGeometry],
        second: Optional[QgsGeometry],
    ) -> Optional[QgsGeometry]:
        if first is None or second is None or first.isEmpty() or second.isEmpty():
            return QgsGeometry()
        intersection = None
        try:
            inputs_valid = first.isGeosValid() and second.isGeosValid()
        except Exception:
            inputs_valid = False
        if inputs_valid:
            try:
                intersection = first.intersection(second)
                if intersection is not None and (intersection.isEmpty() or intersection.isGeosValid()):
                    return intersection
            except Exception:
                intersection = None
        prepared_first = self._prepare_overlay_geometry(first)
        prepared_second = self._prepare_overlay_geometry(second)
        if prepared_first is None or prepared_second is None:
            return intersection
        try:
            return prepared_first.intersection(prepared_second)
        except Exception:
            return intersection

    def _safe_difference(
        self,
        first: Optional[QgsGeometry],
        second: Optional[QgsGeometry],
    ) -> Optional[QgsGeometry]:
        if first is None or first.isEmpty():
            return QgsGeometry()
        if second is None or second.isEmpty():
            return QgsGeometry(first)
        difference = None
        try:
            inputs_valid = first.isGeosValid() and second.isGeosValid()
        except Exception:
            inputs_valid = False
        if inputs_valid:
            try:
                difference = first.difference(second)
                if difference is not None and (difference.isEmpty() or difference.isGeosValid()):
                    return difference
            except Exception:
                difference = None
        prepared_first = self._prepare_overlay_geometry(first)
        prepared_second = self._prepare_overlay_geometry(second)
        if prepared_first is None:
            return difference
        if prepared_second is None:
            return QgsGeometry(prepared_first)
        try:
            return prepared_first.difference(prepared_second)
        except Exception:
            return difference

    def _union_geometries(self, geometries: Sequence[QgsGeometry]) -> Optional[QgsGeometry]:
        """Union valid polygon parts, repairing invalid inputs before coverage tests."""
        non_empty: List[QgsGeometry] = []
        for geometry in geometries:
            if geometry is None or geometry.isEmpty():
                continue
            non_empty.extend(self.baseline_engine._polygon_parts(QgsGeometry(geometry)))
        if not non_empty:
            return None
        try:
            merged = QgsGeometry.unaryUnion(non_empty)
            if merged is not None and not merged.isEmpty():
                return merged
        except Exception:
            pass
        merged = QgsGeometry(non_empty[0])
        for geometry in non_empty[1:]:
            try:
                combined = merged.combine(geometry)
                if combined is not None and not combined.isEmpty():
                    merged = combined
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

    @staticmethod
    def _modernisation_feature_id(family: str, output_kind: str, sequence: int) -> str:
        """Return a readable ID unique across all modernisation output layers."""
        safe_kind = str(output_kind).strip().upper().replace("_", "-")
        return f"{str(family).strip().upper()}-{safe_kind}-{int(sequence):06d}"

    def _create_ols_modernisation_comparison_layers(
        self,
        icao_code: str,
        baseline_ruleset_id: str,
        baseline_candidates: Sequence[ControllingOlsCandidate],
        baseline_exclusions: Sequence[QgsGeometry],
        future_candidates: Sequence[ControllingOlsCandidate],
        ofs_group,
        oes_group,
        solved_baseline_engine: Optional[PlanarControllingOlsEngine] = None,
        solved_future_engines: Optional[Dict[str, PlanarControllingOlsEngine]] = None,
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

        baseline_ids = {candidate.surface_id for candidate in baseline_planar}
        if (
            solved_baseline_engine is None
            or {candidate.surface_id for candidate in solved_baseline_engine.candidates} != baseline_ids
        ):
            baseline_engine = PlanarControllingOlsEngine(
                baseline_planar,
                exclusion_geometries=list(baseline_exclusions or []),
            )
        else:
            baseline_engine = solved_baseline_engine
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
            future_engine = (solved_future_engines or {}).get(family)
            if (
                future_engine is None
                or {candidate.surface_id for candidate in future_engine.candidates}
                != {candidate.surface_id for candidate in family_candidates}
            ):
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
            contour_parts = []
            for change in ("gain", "loss"):
                contour_parts.extend(
                    (change, *contour_part)
                    for contour_part in comparison.change_contour_parts(parts[change], change)
                )
            created = self._create_modernisation_change_contour_layer(
                icao_code,
                baseline_ruleset_id,
                family,
                contour_parts,
                family_group,
            ) or created
            created = self._create_modernisation_transition_layer(
                icao_code, baseline_ruleset_id, family, parts["transition"], comparison, family_group,
            ) or created
            created = self._create_modernisation_baseline_only_layer(
                icao_code, baseline_ruleset_id, family,
                comparison.baseline_only_parts(), family_group,
            ) or created
        return created

    @staticmethod
    def _comparison_label_delta(value: float) -> str:
        rounded = round(float(value), 1)
        if rounded == 0:
            rounded = 0.0
        sign = "+" if rounded > 0 else ""
        return f"{sign}{rounded:.1f}"

    def _comparison_label(
        self,
        change: str,
        delta_min: Optional[float],
        delta_max: Optional[float],
    ) -> str:
        if delta_min is None or delta_max is None:
            return ""
        suffix = "no change" if change == "no_change" else change
        minimum = self._comparison_label_delta(delta_min)
        maximum = self._comparison_label_delta(delta_max)
        if minimum == maximum:
            return f"{minimum} m {suffix}"
        return f"{minimum} to {maximum} m {suffix}"

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
            QgsField("comparison_id", QVariant.String, self.tr("Comparison Feature ID"), 48),
            QgsField("change", QVariant.String, self.tr("Change"), 24),
            QgsField("future_family", QVariant.String, self.tr("Future Family"), 8),
            QgsField("delta_min_m", QVariant.Double, self.tr("Minimum Change (m)"), 12, 3),
            QgsField("delta_max_m", QVariant.Double, self.tr("Maximum Change (m)"), 12, 3),
            QgsField("delta_sample_m", QVariant.Double, self.tr("Interior Sample Change (m)"), 12, 3),
            QgsField("baseline_ruleset", QVariant.String, self.tr("Baseline Ruleset"), 80),
            QgsField("baseline_id", QVariant.String, self.tr("Baseline Surface ID"), 160),
            QgsField("baseline_surface", QVariant.String, self.tr("Baseline Surface"), 50),
            QgsField("future_id", QVariant.String, self.tr("Future Surface ID"), 160),
            QgsField("future_surface", QVariant.String, self.tr("Future Surface"), 50),
            QgsField("meaning", QVariant.String, self.tr("Regulatory Meaning"), 160),
            QgsField("label_txt", QVariant.String, self.tr("Map Label"), 48),
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
        for sequence, (baseline, future, geometry) in enumerate(parts, start=1):
            delta_min, delta_max, delta_sample = comparison.delta_range(
                geometry,
                baseline,
                future,
                change,
            )
            feature = QgsFeature(fields)
            feature.setGeometry(geometry)
            feature.setAttributes([
                self._modernisation_feature_id(family, change, sequence),
                change,
                family,
                delta_min,
                delta_max,
                delta_sample,
                baseline_ruleset_id,
                baseline.surface_id,
                baseline.surface_type,
                future.surface_id,
                future.surface_type,
                meaning,
                self._comparison_label(change, delta_min, delta_max),
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

    def _create_modernisation_change_contour_layer(
        self,
        icao_code,
        baseline_ruleset_id,
        family,
        contour_parts,
        output_group,
    ) -> bool:
        fields = QgsFields([
            QgsField("comparison_id", QVariant.String, self.tr("Comparison Feature ID"), 48),
            QgsField("parent_id", QVariant.String, self.tr("Parent Comparison ID"), 48),
            QgsField("change", QVariant.String, self.tr("Change"), 24),
            QgsField("future_family", QVariant.String, self.tr("Future Family"), 8),
            QgsField("delta_m", QVariant.Double, self.tr("Change Contour (m)"), 12, 3),
            QgsField("contour_class", QVariant.String, self.tr("Contour Class"), 20),
            QgsField("contour_interval_m", QVariant.Double, self.tr("Intermediate Interval (m)"), 10, 2),
            QgsField("primary_interval_m", QVariant.Double, self.tr("Primary Interval (m)"), 10, 2),
            QgsField("baseline_ruleset", QVariant.String, self.tr("Baseline Ruleset"), 80),
            QgsField("baseline_id", QVariant.String, self.tr("Baseline Surface ID"), 160),
            QgsField("baseline_surface", QVariant.String, self.tr("Baseline Surface"), 50),
            QgsField("future_id", QVariant.String, self.tr("Future Surface ID"), 160),
            QgsField("future_surface", QVariant.String, self.tr("Future Surface"), 50),
            QgsField("label_txt", QVariant.String, self.tr("Map Label"), 24),
        ])
        features: List[QgsFeature] = []
        for sequence, contour_part in enumerate(contour_parts, start=1):
            (
                change,
                baseline,
                future,
                geometry,
                delta_m,
                contour_class,
                parent_sequence,
            ) = contour_part
            feature = QgsFeature(fields)
            feature.setGeometry(geometry)
            feature.setAttributes([
                self._modernisation_feature_id(family, "change_contour", sequence),
                self._modernisation_feature_id(family, change, parent_sequence),
                change,
                family,
                delta_m,
                contour_class,
                COMPARISON_CONTOUR_INTERVAL_M,
                COMPARISON_PRIMARY_CONTOUR_INTERVAL_M,
                baseline_ruleset_id,
                baseline.surface_id,
                baseline.surface_type,
                future.surface_id,
                future.surface_type,
                f"{self._comparison_label_delta(delta_m)} m",
            ])
            features.append(feature)
        layer = self._create_and_add_layer(
            "MultiLineString",
            f"OLS_Modernisation_{family}_change_contours_{icao_code}",
            "Change Contours",
            fields,
            features,
            output_group,
            "OLS Modernisation Change Contour",
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
            QgsField("comparison_id", QVariant.String, self.tr("Comparison Feature ID"), 48),
            QgsField("source", QVariant.String, self.tr("Source"), 24),
            QgsField("family", QVariant.String, self.tr("Family"), 8),
            QgsField("baseline_ruleset", QVariant.String, self.tr("Baseline Ruleset"), 80),
            QgsField("surface_id", QVariant.String, self.tr("Surface ID"), 160),
            QgsField("surface", QVariant.String, self.tr("Surface"), 50),
        ])
        features: List[QgsFeature] = []
        sequence = 0
        for candidate, geometry in candidate_regions:
            for part in self._modernisation_polygon_parts(geometry):
                if not OlsEnvelopeComparisonEngine._has_area(part):
                    continue
                sequence += 1
                feature = QgsFeature(fields)
                feature.setGeometry(part)
                feature.setAttributes([
                    self._modernisation_feature_id(family, f"{source_kind}_wireframe", sequence),
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
            QgsField("comparison_id", QVariant.String, self.tr("Comparison Feature ID"), 48),
            QgsField("future_family", QVariant.String, self.tr("Future Family"), 8),
            QgsField("baseline_ruleset", QVariant.String, self.tr("Baseline Ruleset"), 80),
            QgsField("baseline_id", QVariant.String, self.tr("Baseline Surface ID"), 160),
            QgsField("baseline_surface", QVariant.String, self.tr("Baseline Surface"), 50),
            QgsField("future_id", QVariant.String, self.tr("Future Surface ID"), 160),
            QgsField("future_surface", QVariant.String, self.tr("Future Surface"), 50),
            QgsField("meaning", QVariant.String, self.tr("Regulatory Meaning"), 160),
        ])
        features: List[QgsFeature] = []
        for sequence, (baseline, future, geometry) in enumerate(parts, start=1):
            feature = QgsFeature(fields)
            feature.setGeometry(geometry)
            feature.setAttributes([
                self._modernisation_feature_id(family, "transition", sequence),
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
            QgsField("comparison_id", QVariant.String, self.tr("Comparison Feature ID"), 48),
            QgsField("change", QVariant.String, self.tr("Change"), 32),
            QgsField("future_family", QVariant.String, self.tr("Future Family"), 8),
            QgsField("baseline_ruleset", QVariant.String, self.tr("Baseline Ruleset"), 80),
            QgsField("baseline_id", QVariant.String, self.tr("Baseline Surface ID"), 160),
            QgsField("baseline_surface", QVariant.String, self.tr("Baseline Surface"), 50),
            QgsField("meaning", QVariant.String, self.tr("Regulatory Meaning"), 160),
            QgsField("label_txt", QVariant.String, self.tr("Map Label"), 32),
        ])
        features: List[QgsFeature] = []
        for sequence, (baseline, geometry) in enumerate(parts, start=1):
            feature = QgsFeature(fields)
            feature.setGeometry(geometry)
            feature.setAttributes([
                self._modernisation_feature_id(family, "no_future_overlay", sequence),
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
