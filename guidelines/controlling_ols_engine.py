# -*- coding: utf-8 -*-
"""Planar lower-envelope engine for controlling OLS outputs."""

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
    QgsSpatialIndex,
    QgsWkbTypes,
)

try:
    from ..core import output_structure
except ImportError:
    from core import output_structure

PLUGIN_TAG = "SafeguardingBuilder"
CONTROLLING_REGION_GEOMETRY_REPAIR_SEGMENTS = 8
CONTROLLING_REGION_MAX_NEW_SEGMENT_M = 50.0
CONTROLLING_REGION_BOUNDARY_DISTANCE_TOLERANCE_M = 0.02
CONTROLLING_REGION_RING_TOUCH_TOLERANCE_M = 0.05
CONTROLLING_REGION_DISSOLVE_GRID_M = 1e-6
CONTROLLING_REGION_DISSOLVE_RETRY_GRID_M = 2e-6
CONTROLLING_REGION_DISSOLVE_MAX_AREA_CHANGE_M2 = 0.01
CONTROLLING_REGION_MIN_INTERIOR_RING_AREA_M2 = 0.01
CONTROLLING_CONTOUR_CLIP_TOLERANCE_M = 0.05
CONTROLLING_CONTOUR_STRICT_BOUNDARY_TOLERANCE_M = 0.001
CONTROLLING_CONTOUR_CLIP_BUFFER_SEGMENTS = 4
CONTROLLING_GLOBAL_CELL_SOLVER_ENABLED = True
CONTROLLING_GLOBAL_CELL_MIN_AREA_M2 = 1.0
CONTROLLING_MOS139_CONICAL_CELL_MIN_AREA_M2 = 1e-3
AXIS_CONICAL_EXACT_SOLVER_ENABLED = True
AXIS_CONICAL_TRIANGULATION_FALLBACK_ENABLED = True
AXIS_CONICAL_VERTEX_CURVE_CHORD_TOLERANCE_M = 0.25
AXIS_CONICAL_VERTEX_CURVE_STATION_STEP_M = 5.0
AXIS_CONICAL_CURVE_FILTER_TOLERANCE_M = 0.5
AXIS_CONICAL_CURVE_SIMPLIFY_TOLERANCE_M = 0.5
AXIS_CONICAL_CURVE_ENDPOINT_SNAP_TOLERANCE_M = 2.0
AXIS_CONICAL_CURVE_ENDPOINT_EXTENSION_M = 100.0
AXIS_CONICAL_ZERO_CONTOUR_ENABLED = True
AXIS_CONICAL_ZERO_CONTOUR_MIN_GRID_M = 20.0
AXIS_CONICAL_ZERO_CONTOUR_MAX_GRID_M = 75.0
AXIS_CONICAL_ZERO_CONTOUR_TARGET_STEPS = 160.0
AXIS_CONICAL_ZERO_CONTOUR_MAX_CELLS = 80000
AXIS_CONICAL_CURVE_SMOOTHING_ENABLED = True
AXIS_CONICAL_CURVE_SMOOTHING_CONTROL_SPACING_M = 15.0
AXIS_CONICAL_CURVE_SMOOTHING_SAMPLES_PER_SPAN = 2
AXIS_CONICAL_CURVE_SMOOTHING_MAX_DEVIATION_M = 0.5
AXIS_CONICAL_CURVE_SMOOTHING_MAX_EQUALITY_RESIDUAL_M = 0.01
AXIS_CONICAL_CURVE_SMOOTHING_MAX_RESIDUAL_INCREASE_M = 1e-3
AXIS_CONICAL_CURVE_SMOOTHING_MIN_CURVATURE_IMPROVEMENT = 0.01
AXIS_CONICAL_CURVE_SMOOTHING_DOMAIN_TOLERANCE_M = 0.05
AXIS_CONICAL_CURVE_SMOOTHING_HAUSDORFF_DENSIFY_FRACTION = 0.25
AXIS_CONICAL_CURVE_SMOOTHING_MAX_ENDPOINT_SHIFT_M = 1e-9
AXIS_CONICAL_GLOBAL_CELL_CHORD_ERROR_M = 0.10
AXIS_CONICAL_OUTPUT_EQUALITY_FILTER_M = 0.01
AXIS_CONICAL_OUTPUT_SIMPLIFY_TOLERANCE_M = 0.05
AXIS_CONICAL_OUTPUT_TOPOLOGY_SNAP_M = 0.5
AXIS_CONICAL_OUTPUT_MIN_COMPONENT_LENGTH_M = 1.0
AXIS_CONICAL_OUTPUT_MIN_CLOSED_LOOP_DIAMETER_M = 2.0

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


@dataclass(frozen=True)
class ControllingOlsContour:
    """A source contour line linked to its parent controlling OLS candidate."""

    surface_id: str
    surface_type: str
    geometry: QgsGeometry
    contour_elevation_m: Optional[float]
    source_layer: str
    contour_class: Optional[str] = None
    contour_interval_m: Optional[float] = None
    primary_interval_m: Optional[float] = None


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
        input_candidates = list(candidates)
        self.candidates = [
            candidate
            for candidate in input_candidates
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
        self._candidate_spatial_index: Optional[QgsSpatialIndex] = None
        self._candidate_by_spatial_id: Dict[int, ControllingOlsCandidate] = {}
        self._controlling_region_geometries_cache: Optional[List[Tuple[ControllingOlsCandidate, QgsGeometry]]] = None
        self._region_boundary_records_cache: Optional[List[Tuple[QgsGeometry, List[object]]]] = None
        self._region_solve_stats: Dict[str, float] = {}
        self._final_partition_repair_by_surface: Dict[str, Dict[str, object]] = {}
        self._invalid_input_candidate_count = len(input_candidates) - len(self.candidates)
        self.tie_tolerance_m = max(0.0, float(tie_tolerance_m))
        self.bounds = self._combined_bounds(self.candidates)

    def solver_diagnostics(self) -> Dict[str, object]:
        """Return stable, structured diagnostics without exposing timing as correctness data."""
        stats = self._region_solve_stats or {}
        cells = int(stats.get("global_cell_count", 0.0))
        return {
            "solver": "global_cell" if stats.get("global_cell_solver_used", 0.0) else "pairwise_subtract",
            "cells": {
                "total": cells,
                "unassigned": int(stats.get("global_unassigned_cell_count", 0.0)),
                "refined": int(stats.get("global_refined_cell_count", 0.0)),
                "unanimous_gap_parts": int(stats.get("global_unanimous_gap_part_count", 0.0)),
                "unanimous_gap_area_m2": stats.get("global_unanimous_gap_area_m2", 0.0),
                "ambiguous_gap_parts": int(stats.get("global_ambiguous_gap_part_count", 0.0)),
                "ambiguous_gap_area_m2": stats.get("global_ambiguous_gap_area_m2", 0.0),
            },
            "comparisons": {
                "unresolved": int(stats.get("axis_exact_unresolved", 0.0)),
                "axis_conical_fallback": int(stats.get("axis_exact_fallback", 0.0)),
            },
            "topology": {
                "transition_method": (
                    "cell_adjacency"
                    if stats.get("adjacency_transition_record_count", 0.0)
                    else "rounded_probe_fallback"
                ),
                "transition_records": int(stats.get("adjacency_transition_record_count", 0.0)),
                "merged_overlap_resolved": int(stats.get("merged_overlap_resolved_count", 0.0)),
                "merged_overlap_resolved_area_m2": stats.get("merged_overlap_resolved_area_m2", 0.0),
                "merged_overlap_unresolved": int(stats.get("merged_overlap_unresolved_count", 0.0)),
                "merged_overlap_unanimous": int(stats.get("merged_overlap_unanimous_count", 0.0)),
                "merged_overlap_triangulated": int(stats.get("merged_overlap_triangulated_count", 0.0)),
                "merged_overlap_representative": int(stats.get("merged_overlap_representative_count", 0.0)),
                "exclusive_boundaries_normalised": int(
                    stats.get("exclusive_boundary_normalisation_count", 0.0)
                ),
                "exclusive_boundary_reassigned_area_m2": stats.get(
                    "exclusive_boundary_reassigned_area_m2", 0.0
                ),
                "exclusive_boundary_coverage_change_m2": stats.get(
                    "exclusive_boundary_coverage_change_m2", 0.0
                ),
                "exclusive_boundary_overlap_change_m2": stats.get(
                    "exclusive_boundary_overlap_change_m2", 0.0
                ),
            },
            "approximations": {
                "triangulation_calls": int(stats.get("triangulation_calls", 0.0)),
                "zero_contour_calls": int(stats.get("axis_zero_contour_calls", 0.0)),
                "smoothed_zero_contours": int(
                    stats.get("axis_curve_smoothing_accepted", 0.0)
                ),
                "zero_contour_smoothing_method": (
                    "clamped_cubic_bspline_equality_projected"
                    if AXIS_CONICAL_CURVE_SMOOTHING_ENABLED
                    else "disabled"
                ),
                "rejected_zero_contour_smoothing": int(
                    stats.get("axis_curve_smoothing_rejected", 0.0)
                ),
                "smoothing_max_allowed_deviation_m": (
                    AXIS_CONICAL_CURVE_SMOOTHING_MAX_DEVIATION_M
                ),
                "smoothing_max_allowed_equality_residual_m": (
                    AXIS_CONICAL_CURVE_SMOOTHING_MAX_EQUALITY_RESIDUAL_M
                ),
                "smoothing_max_allowed_endpoint_shift_m": (
                    AXIS_CONICAL_CURVE_SMOOTHING_MAX_ENDPOINT_SHIFT_M
                ),
                "smoothing_max_deviation_m": stats.get(
                    "axis_curve_smoothing_max_deviation_m", 0.0
                ),
                "smoothing_max_equality_residual_m": stats.get(
                    "axis_curve_smoothing_max_equality_residual_m", 0.0
                ),
                "smoothing_max_endpoint_shift_m": stats.get(
                    "axis_curve_smoothing_max_endpoint_shift_m", 0.0
                ),
                "chord_refinements_suppressed": int(
                    stats.get("axis_conical_chord_refinement_suppressed", 0.0)
                ),
                "horizontal_chord_tolerance_m": AXIS_CONICAL_VERTEX_CURVE_CHORD_TOLERANCE_M,
                "vertical_error_bound_m": (
                    AXIS_CONICAL_GLOBAL_CELL_CHORD_ERROR_M
                    if stats.get("axis_zero_contour_calls", 0.0)
                    and not stats.get("triangulation_calls", 0.0)
                    else None
                ),
            },
            "geometry": {
                "invalid_input_candidates": self._invalid_input_candidate_count,
                "invalid_output_regions": int(stats.get("invalid_output_region_count", 0.0)),
                "raw_output_union_area_m2": stats.get("raw_output_union_area_m2", 0.0),
                "partitioned_output_union_area_m2": stats.get("partitioned_output_union_area_m2", 0.0),
                "dissolved_output_union_area_m2": stats.get("dissolved_output_union_area_m2", 0.0),
            },
            "exceptional_recovery": {
                "pairwise_solver_fallbacks": int(stats.get("pairwise_solver_fallback_count", 0.0)),
                "coverage_repair_parts": int(stats.get("coverage_repair_part_count", 0.0)),
                "coverage_repair_area_m2": stats.get("coverage_repair_area_m2", 0.0),
                "final_partition_repair_parts": int(stats.get("final_partition_repair_part_count", 0.0)),
                "final_partition_repair_area_m2": stats.get("final_partition_repair_area_m2", 0.0),
                "partition_make_valid_calls": int(stats.get("partition_make_valid_count", 0.0)),
                "dissolve_geometry_repair_calls": int(stats.get("dissolve_geometry_repair_count", 0.0)),
                "final_partition_by_surface": dict(sorted(self._final_partition_repair_by_surface.items())),
            },
            "operation_classes": {
                "same_controller_dissolve": "canonical_normalisation",
                "unanimous_gap_audit": "qa_diagnostic",
                "merged_conical_overlap_assignment": "accepted_compatibility_correction",
                "axis_conical_isoline": "bounded_c2_guide_equality_projection",
                "pairwise_solver_fallback": "exceptional_recovery",
                "coverage_gap_fill": "exceptional_recovery",
                "final_partition_gap_fill": "exceptional_recovery",
            },
        }

    def ensure_adjacency_diagnostics(self) -> None:
        """Build authoritative adjacency QA separately from diagnostic layer output."""
        if self._region_solve_stats.get("adjacency_transition_record_count", 0.0):
            return
        records = self._adjacency_region_boundary_records(
            self._controlling_region_geometries()
        )
        self._region_solve_stats["adjacency_transition_record_count"] = float(len(records))

    def controlling_candidate_at_xy(self, point_xy: QgsPointXY) -> Optional[Tuple[ControllingOlsCandidate, float]]:
        """Return the lowest applicable planar candidate at a point."""
        evaluated: List[Tuple[ControllingOlsCandidate, float]] = []
        point_geometry = QgsGeometry.fromPointXY(point_xy)
        query_tolerance = 1e-6
        candidates = self._candidates_intersecting_rectangle(
            QgsRectangle(
                point_xy.x() - query_tolerance,
                point_xy.y() - query_tolerance,
                point_xy.x() + query_tolerance,
                point_xy.y() + query_tolerance,
            )
        )
        for candidate in candidates:
            footprint = self._effective_footprint(candidate)
            if footprint is None or footprint.isEmpty() or not footprint.intersects(point_geometry):
                continue
            elevation = candidate.elevation_at_xy(point_xy)
            if elevation is None or not math.isfinite(elevation):
                continue
            evaluated.append((candidate, elevation))
        if not evaluated:
            return None
        minimum_elevation = min(item[1] for item in evaluated)
        tied = [
            item for item in evaluated
            if item[1] <= minimum_elevation + self.tie_tolerance_m
        ]
        tied_families = {
            str((item[0].metadata or {}).get("annex14_family") or "").strip().upper()
            for item in tied
        }
        if "OFS" in tied_families and "OES" in tied_families:
            tied.sort(key=lambda item: self._candidate_tie_priority(item[0]))
            return tied[0]
        tied_surface_types = {item[0].surface_type for item in tied}
        if {"Inner Approach", "Approach"} <= tied_surface_types:
            tied.sort(key=lambda item: self._candidate_tie_priority(item[0]))
            return tied[0]
        evaluated.sort(key=lambda item: item[1])
        return evaluated[0]

    def _ensure_candidate_spatial_index(self) -> QgsSpatialIndex:
        """Build a lazy footprint index used only as an exact-query prefilter."""
        if self._candidate_spatial_index is not None:
            return self._candidate_spatial_index

        spatial_index = QgsSpatialIndex()
        candidates_by_id: Dict[int, ControllingOlsCandidate] = {}
        for spatial_id, candidate in enumerate(self.candidates, start=1):
            footprint = self._effective_footprint(candidate)
            if footprint is None or footprint.isEmpty():
                continue
            feature = QgsFeature()
            feature.setId(spatial_id)
            feature.setGeometry(footprint)
            if spatial_index.addFeature(feature):
                candidates_by_id[spatial_id] = candidate
        self._candidate_by_spatial_id = candidates_by_id
        self._candidate_spatial_index = spatial_index
        return spatial_index

    def _candidates_intersecting_rectangle(
        self,
        rectangle: QgsRectangle,
    ) -> List[ControllingOlsCandidate]:
        """Return bbox candidates in their original deterministic solve order."""
        if rectangle is None or rectangle.isEmpty():
            return []
        spatial_ids = set(self._ensure_candidate_spatial_index().intersects(rectangle))
        return [
            candidate
            for spatial_id, candidate in self._candidate_by_spatial_id.items()
            if spatial_id in spatial_ids
        ]

    def _candidates_intersecting_geometry(
        self,
        geometry: Optional[QgsGeometry],
    ) -> List[ControllingOlsCandidate]:
        if geometry is None or geometry.isEmpty():
            return []
        return self._candidates_intersecting_rectangle(geometry.boundingBox())

    @staticmethod
    def _candidate_tie_priority(candidate: ControllingOlsCandidate) -> Tuple[int, int, str]:
        """Apply explicit family and nested-surface priorities to tied elevations."""
        family = str((candidate.metadata or {}).get("annex14_family") or "").strip().upper()
        family_priority = {"OFS": 0, "OES": 1}.get(family, 2)
        surface_priority = {"Inner Approach": 0, "Approach": 1}.get(candidate.surface_type, 2)
        return family_priority, surface_priority, candidate.surface_id

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
        features: List[QgsFeature] = []
        for geometry, attributes in self._region_boundary_records():
            feature = QgsFeature(fields)
            feature.setGeometry(QgsGeometry(geometry))
            feature.setAttributes(list(attributes)[: fields.count()])
            features.append(feature)
        return features

    def _region_boundary_records(self) -> List[Tuple[QgsGeometry, List[object]]]:
        """Cache field-independent transition geometry for all output consumers."""
        if self._region_boundary_records_cache is not None:
            return self._region_boundary_records_cache

        region_parts = self._controlling_region_geometries()
        records: List[Tuple[QgsGeometry, List[object]]] = []
        pair_segments: Dict[
            Tuple[str, str],
            Tuple[ControllingOlsCandidate, ControllingOlsCandidate, List[QgsGeometry]],
        ] = {}
        segment_controller_cache: Dict[
            Tuple[Tuple[float, float], Tuple[float, float]],
            Optional[Tuple[ControllingOlsCandidate, ControllingOlsCandidate]],
        ] = {}
        seen_keys = set()
        for region_candidate, region in region_parts:
            for line_points in self._polygon_boundary_parts(region):
                for start_point, end_point in zip(line_points[:-1], line_points[1:]):
                    segment_key = self._undirected_segment_key(start_point, end_point)
                    if segment_key not in segment_controller_cache:
                        segment_controller_cache[segment_key] = self._controllers_across_segment(
                            start_point,
                            end_point,
                            known_candidate=region_candidate,
                            known_region=region,
                        )
                    controllers = segment_controller_cache[segment_key]
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
                    segment = QgsGeometry.fromPolylineXY(segment_points)
                    if segment is None or segment.isEmpty():
                        continue
                    ordered = sorted(
                        (first_controller, second_controller),
                        key=lambda candidate: candidate.surface_id,
                    )
                    pair_key = (ordered[0].surface_id, ordered[1].surface_id)
                    pair_segments.setdefault(pair_key, (ordered[0], ordered[1], []))[2].append(segment)

        for pair_key in sorted(pair_segments):
            first_controller, second_controller, segments = pair_segments[pair_key]
            try:
                merged = QgsGeometry.unaryUnion(segments) if len(segments) > 1 else segments[0]
                line_merged = merged.mergeLines()
                if line_merged is not None and not line_merged.isEmpty():
                    merged = line_merged
            except Exception:
                merged = segments[0]
            output_geometries = [(merged, "region_boundary_merged")]
            sampled_equality = self._axis_conical_boundary_segments(
                merged,
                first_controller,
                second_controller,
                keep_equality=True,
            )
            projected_transitions = self._axis_conical_output_transition_lines(
                first_controller,
                second_controller,
                sampled_equality,
            )
            if projected_transitions:
                retained_boundary = self._remove_sampled_axis_conical_equality_segments(
                    merged,
                    first_controller,
                    second_controller,
                )
                output_geometries = [
                    (retained_boundary, "region_boundary_merged"),
                    *[
                        (transition, "projected_axis_conical_transition")
                        for transition in projected_transitions
                    ],
                ]
            for output_geometry, method in output_geometries:
                if output_geometry is None or output_geometry.isEmpty():
                    continue
                for line_points in self._line_parts(output_geometry):
                    if len(line_points) < 2:
                        continue
                    z_values = self._transition_z_values(line_points, first_controller, second_controller)
                    z_line = self._line_points_to_z_geometry(line_points, z_values)
                    if z_line is None or z_line.isEmpty():
                        continue
                    pair_id = f"{first_controller.surface_id}|{second_controller.surface_id}"
                    records.append(
                        (
                            QgsGeometry(z_line),
                            [
                                pair_id[:160],
                                "Transition",
                                min(z_values),
                                max(z_values),
                                pair_id[:254],
                                method,
                                (
                                    self._transition_max_equality_residual(
                                        line_points,
                                        first_controller,
                                        second_controller,
                                    )
                                    if method == "projected_axis_conical_transition"
                                    else None
                                ),
                            ],
                        )
                    )
        self._region_boundary_records_cache = records
        return records

    def _axis_conical_output_transition_lines(
        self,
        first_candidate: ControllingOlsCandidate,
        second_candidate: ControllingOlsCandidate,
        sampled_equality: Optional[QgsGeometry] = None,
    ) -> List[QgsGeometry]:
        """Project the continuous sampled transition laterally onto the modeled zero contour."""
        if {first_candidate.model, second_candidate.model} != {"axis", "conical"}:
            return []
        axis_candidate = first_candidate if first_candidate.model == "axis" else second_candidate
        conical_candidate = first_candidate if first_candidate.model == "conical" else second_candidate
        if axis_candidate.surface_type not in {"Approach", "TOCS"}:
            return []
        axis = self._axis_model(axis_candidate)
        conical_model = self._conical_model(conical_candidate)
        if axis is None or conical_model is None:
            return []
        if sampled_equality is None or sampled_equality.isEmpty():
            return []
        output: List[QgsGeometry] = []
        reference_parts = self._topology_clean_transition_line_parts(sampled_equality)
        for reference_points in reference_parts:
            if len(reference_points) < 2:
                continue
            reference = QgsGeometry.fromPolylineXY(reference_points)
            try:
                densified = reference.densifyByDistance(5.0)
            except Exception:
                densified = reference
            densified_parts = self._line_parts(densified)
            if not densified_parts:
                continue
            source_points = densified_parts[0]
            projected: List[QgsPointXY] = []
            for index, point_xy in enumerate(source_points):
                equality_point = (
                    point_xy
                    if index in {0, len(source_points) - 1}
                    else self._project_axis_conical_point_to_equality(
                        axis,
                        conical_model,
                        point_xy,
                    )
                )
                if not projected or equality_point.distance(projected[-1]) > 1e-6:
                    projected.append(equality_point)
            projected = self._remove_transition_curve_backtracking(projected)
            projected = self._simplify_transition_curve_points(
                projected,
                AXIS_CONICAL_OUTPUT_SIMPLIFY_TOLERANCE_M,
            )
            if len(projected) >= 2:
                output.append(QgsGeometry.fromPolylineXY(projected))
        return output

    @staticmethod
    def _remove_transition_curve_backtracking(
        points: Sequence[QgsPointXY],
        minimum_reversal_degrees: float = 150.0,
    ) -> List[QgsPointXY]:
        """Erase local hairpins without changing ordinary corners or smooth curvature."""
        cleaned: List[QgsPointXY] = []
        for point in points:
            if cleaned and point.distance(cleaned[-1]) <= 1e-6:
                continue
            cleaned.append(QgsPointXY(point))
            while len(cleaned) >= 3:
                previous, current, following = cleaned[-3:]
                first_dx = current.x() - previous.x()
                first_dy = current.y() - previous.y()
                second_dx = following.x() - current.x()
                second_dy = following.y() - current.y()
                denominator = math.hypot(first_dx, first_dy) * math.hypot(second_dx, second_dy)
                if denominator <= 1e-12:
                    del cleaned[-2]
                    continue
                cosine = max(
                    -1.0,
                    min(1.0, ((first_dx * second_dx) + (first_dy * second_dy)) / denominator),
                )
                turn_degrees = math.degrees(math.acos(cosine))
                if turn_degrees < minimum_reversal_degrees:
                    break
                del cleaned[-2]
                if len(cleaned) >= 2 and cleaned[-1].distance(cleaned[-2]) <= 1e-6:
                    cleaned.pop()
                    break
        return cleaned

    def _topology_clean_transition_line_parts(
        self,
        geometry: QgsGeometry,
        snap_tolerance_m: float = AXIS_CONICAL_OUTPUT_TOPOLOGY_SNAP_M,
    ) -> List[List[QgsPointXY]]:
        """Collapse sliver topology into simple, non-repeating transition paths."""
        source_parts = self._line_parts(geometry)
        if not source_parts:
            return []

        unique_points: List[QgsPointXY] = []
        point_indexes: Dict[Tuple[float, float], int] = {}
        indexed_parts: List[List[int]] = []
        for part in source_parts:
            indexed_part: List[int] = []
            for point in part:
                key = (round(point.x(), 9), round(point.y(), 9))
                point_index = point_indexes.get(key)
                if point_index is None:
                    point_index = len(unique_points)
                    point_indexes[key] = point_index
                    unique_points.append(QgsPointXY(point))
                indexed_part.append(point_index)
            if len(indexed_part) >= 2:
                indexed_parts.append(indexed_part)
        if not indexed_parts:
            return []

        parents = list(range(len(unique_points)))

        def _find(index: int) -> int:
            while parents[index] != index:
                parents[index] = parents[parents[index]]
                index = parents[index]
            return index

        def _union(first_index: int, second_index: int) -> None:
            first_root = _find(first_index)
            second_root = _find(second_index)
            if first_root == second_root:
                return
            if first_root < second_root:
                parents[second_root] = first_root
            else:
                parents[first_root] = second_root

        tolerance = max(0.0, float(snap_tolerance_m))
        for first_index, first_point in enumerate(unique_points):
            for second_index in range(first_index):
                if first_point.distance(unique_points[second_index]) <= tolerance:
                    _union(first_index, second_index)

        clusters: Dict[int, List[int]] = {}
        for point_index in range(len(unique_points)):
            clusters.setdefault(_find(point_index), []).append(point_index)

        node_points: Dict[int, QgsPointXY] = {}
        point_nodes: Dict[int, int] = {}
        for node_index, member_indexes in enumerate(
            sorted(clusters.values(), key=lambda members: min(members))
        ):
            centroid_x = sum(
                unique_points[index].x() for index in member_indexes
            ) / len(member_indexes)
            centroid_y = sum(
                unique_points[index].y() for index in member_indexes
            ) / len(member_indexes)
            representative_index = min(
                member_indexes,
                key=lambda index: (
                    math.hypot(
                        unique_points[index].x() - centroid_x,
                        unique_points[index].y() - centroid_y,
                    ),
                    unique_points[index].x(),
                    unique_points[index].y(),
                ),
            )
            node_points[node_index] = QgsPointXY(unique_points[representative_index])
            for point_index in member_indexes:
                point_nodes[point_index] = node_index

        edges = set()
        adjacency: Dict[int, set] = {node_index: set() for node_index in node_points}
        for part in indexed_parts:
            for first_index, second_index in zip(part[:-1], part[1:]):
                first_node = point_nodes[first_index]
                second_node = point_nodes[second_index]
                if first_node == second_node:
                    continue
                edge = tuple(sorted((first_node, second_node)))
                if edge in edges:
                    continue
                edges.add(edge)
                adjacency[first_node].add(second_node)
                adjacency[second_node].add(first_node)
        if not edges:
            return []

        components: List[set] = []
        unvisited = {node for node, neighbours in adjacency.items() if neighbours}
        while unvisited:
            start = min(unvisited)
            component = set()
            stack = [start]
            while stack:
                node = stack.pop()
                if node in component:
                    continue
                component.add(node)
                stack.extend(sorted(adjacency[node] - component, reverse=True))
            unvisited -= component
            components.append(component)

        def _trace_simple_component(component: set) -> List[int]:
            endpoints = sorted(node for node in component if len(adjacency[node]) == 1)
            start = endpoints[0] if endpoints else min(component)
            path = [start]
            previous = None
            current = start
            while True:
                choices = sorted(
                    neighbour for neighbour in adjacency[current] if neighbour != previous
                )
                if not choices:
                    break
                following = choices[0]
                if following == start:
                    path.append(following)
                    break
                if following in path:
                    break
                path.append(following)
                previous, current = current, following
            return path

        def _shortest_paths(start: int, component: set):
            distances = {node: math.inf for node in component}
            previous: Dict[int, int] = {}
            distances[start] = 0.0
            remaining = set(component)
            while remaining:
                current = min(remaining, key=lambda node: (distances[node], node))
                if not math.isfinite(distances[current]):
                    break
                remaining.remove(current)
                for neighbour in adjacency[current]:
                    if neighbour not in component:
                        continue
                    distance = distances[current] + node_points[current].distance(
                        node_points[neighbour]
                    )
                    if distance + 1e-12 < distances[neighbour]:
                        distances[neighbour] = distance
                        previous[neighbour] = current
            return distances, previous

        def _principal_branched_path(component: set) -> List[int]:
            endpoints = sorted(node for node in component if len(adjacency[node]) == 1)
            candidates = endpoints if len(endpoints) >= 2 else sorted(component)
            best = None
            best_previous = None
            for start in candidates:
                distances, previous = _shortest_paths(start, component)
                for end in candidates:
                    if end <= start or not math.isfinite(distances[end]):
                        continue
                    score = (distances[end], -start, -end)
                    if best is None or score > best[0]:
                        best = (score, start, end)
                        best_previous = previous
            if best is None or best_previous is None:
                return []
            _score, start, end = best
            reversed_path = [end]
            current = end
            while current != start:
                current = best_previous.get(current)
                if current is None:
                    return []
                reversed_path.append(current)
            return list(reversed(reversed_path))

        cleaned: List[List[QgsPointXY]] = []
        for component in sorted(components, key=lambda nodes: min(nodes)):
            maximum_degree = max(len(adjacency[node]) for node in component)
            node_path = (
                _trace_simple_component(component)
                if maximum_degree <= 2
                else _principal_branched_path(component)
            )
            if len(node_path) < 2:
                continue
            points = [QgsPointXY(node_points[node]) for node in node_path]
            path_length = sum(
                start.distance(end) for start, end in zip(points[:-1], points[1:])
            )
            if path_length < AXIS_CONICAL_OUTPUT_MIN_COMPONENT_LENGTH_M:
                continue
            if node_path[0] == node_path[-1]:
                bounds = QgsGeometry.fromPolylineXY(points).boundingBox()
                diameter = math.hypot(bounds.width(), bounds.height())
                if diameter < AXIS_CONICAL_OUTPUT_MIN_CLOSED_LOOP_DIAMETER_M:
                    continue
            cleaned.append(points)
        return cleaned

    def _project_axis_conical_point_to_equality(
        self,
        axis: dict,
        conical_model: dict,
        point_xy: QgsPointXY,
    ) -> QgsPointXY:
        """Project a near-equality sampled point laterally onto the modeled zero contour."""
        base_footprint = conical_model.get("base_footprint")
        conical_slope = float(conical_model.get("slope", 0.0))
        if base_footprint is None or base_footprint.isEmpty() or conical_slope <= 0.0:
            return point_xy
        station, lateral = self._axis_local_coordinates(axis, point_xy)
        required_distance = (
            (float(axis["origin_elevation_m"]) - float(conical_model["base_elevation_m"]))
            / conical_slope
        ) + ((float(axis["slope"]) / conical_slope) * station)

        def _point_at(value: float) -> QgsPointXY:
            return self._axis_point_from_local(axis, station, value)

        def _difference(value: float) -> float:
            return QgsGeometry.fromPointXY(_point_at(value)).distance(base_footprint) - required_distance

        try:
            initial_value = _difference(lateral)
        except Exception:
            return point_xy
        if abs(initial_value) <= 1e-4:
            return point_xy

        for radius in (0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0, 25.0, 50.0, 100.0):
            for direction in (-1.0, 1.0):
                candidate_lateral = lateral + (direction * radius)
                try:
                    candidate_value = _difference(candidate_lateral)
                except Exception:
                    continue
                if initial_value * candidate_value > 0.0:
                    continue
                lower_l, upper_l = sorted((lateral, candidate_lateral))
                projected_lateral = self._axis_conical_bisect_lateral_root(
                    _difference,
                    lower_l,
                    upper_l,
                )
                projected = _point_at(projected_lateral)
                try:
                    if abs(_difference(projected_lateral)) <= 0.01:
                        return projected
                except Exception:
                    pass
        return point_xy

    def _remove_sampled_axis_conical_equality_segments(
        self,
        geometry: QgsGeometry,
        first_candidate: ControllingOlsCandidate,
        second_candidate: ControllingOlsCandidate,
    ) -> QgsGeometry:
        """Keep footprint edges while removing sampled interior equality chords."""
        return self._axis_conical_boundary_segments(
            geometry,
            first_candidate,
            second_candidate,
            keep_equality=False,
        )

    def _axis_conical_boundary_segments(
        self,
        geometry: QgsGeometry,
        first_candidate: ControllingOlsCandidate,
        second_candidate: ControllingOlsCandidate,
        keep_equality: bool,
    ) -> QgsGeometry:
        """Select sampled equality chords or the complementary footprint boundaries."""
        if {first_candidate.model, second_candidate.model} != {"axis", "conical"}:
            return QgsGeometry()
        retained: List[QgsGeometry] = []
        for line_points in self._line_parts(geometry):
            current: List[QgsPointXY] = []
            for start_point, end_point in zip(line_points[:-1], line_points[1:]):
                midpoint = QgsPointXY(
                    (start_point.x() + end_point.x()) / 2.0,
                    (start_point.y() + end_point.y()) / 2.0,
                )
                residuals = []
                for point_xy in (start_point, midpoint, end_point):
                    first_z = first_candidate.elevation_at_xy(point_xy)
                    second_z = second_candidate.elevation_at_xy(point_xy)
                    if first_z is None or second_z is None:
                        residuals = []
                        break
                    residuals.append(abs(float(first_z) - float(second_z)))
                is_sampled_equality = (
                    bool(residuals)
                    and max(residuals) <= AXIS_CONICAL_OUTPUT_EQUALITY_FILTER_M
                )
                retain_segment = is_sampled_equality if keep_equality else not is_sampled_equality
                if retain_segment:
                    if not current:
                        current.append(start_point)
                    current.append(end_point)
                elif len(current) >= 2:
                    retained.append(QgsGeometry.fromPolylineXY(current))
                    current = []
                else:
                    current = []
            if len(current) >= 2:
                retained.append(QgsGeometry.fromPolylineXY(current))
        if not retained:
            return QgsGeometry()
        try:
            merged = QgsGeometry.unaryUnion(retained) if len(retained) > 1 else retained[0]
            line_merged = merged.mergeLines()
            return line_merged if line_merged is not None and not line_merged.isEmpty() else merged
        except Exception:
            return retained[0]

    def _transition_max_equality_residual(
        self,
        line_points: Sequence[QgsPointXY],
        first_candidate: ControllingOlsCandidate,
        second_candidate: ControllingOlsCandidate,
    ) -> Optional[float]:
        """Return the sampled maximum absolute height difference along a transition."""
        residuals: List[float] = []
        for start_point, end_point in zip(line_points[:-1], line_points[1:]):
            segment_length = start_point.distance(end_point)
            steps = max(1, int(math.ceil(segment_length / 5.0)))
            for step in range(steps + 1):
                fraction = step / steps
                point_xy = QgsPointXY(
                    start_point.x() + ((end_point.x() - start_point.x()) * fraction),
                    start_point.y() + ((end_point.y() - start_point.y()) * fraction),
                )
                first_z = first_candidate.elevation_at_xy(point_xy)
                second_z = second_candidate.elevation_at_xy(point_xy)
                if first_z is None or second_z is None:
                    continue
                if not math.isfinite(first_z) or not math.isfinite(second_z):
                    continue
                residuals.append(abs(float(first_z) - float(second_z)))
        return max(residuals) if residuals else None

    def _adjacency_region_boundary_records(
        self,
        region_parts: Sequence[Tuple[ControllingOlsCandidate, QgsGeometry]],
    ) -> List[Tuple[QgsGeometry, List[object]]]:
        """Derive controller transitions from exact shared region edges."""
        records: List[Tuple[QgsGeometry, List[object]]] = []
        boundaries = []
        for candidate, region in region_parts:
            linework = [
                QgsGeometry.fromPolylineXY(points)
                for points in self._polygon_boundary_parts(region)
                if len(points) >= 2
            ]
            try:
                boundary = QgsGeometry.unaryUnion(linework) if linework else None
            except Exception:
                boundary = linework[0] if linework else None
            boundaries.append((candidate, region, boundary))
        for index, (first, first_region, first_boundary) in enumerate(boundaries):
            if first_boundary is None or first_boundary.isEmpty():
                continue
            for second, second_region, second_boundary in boundaries[index + 1 :]:
                if first.surface_id == second.surface_id:
                    continue
                try:
                    first_box = first_region.boundingBox()
                    second_box = second_region.boundingBox()
                    separated = (
                        first_box.xMaximum() < second_box.xMinimum()
                        or second_box.xMaximum() < first_box.xMinimum()
                        or first_box.yMaximum() < second_box.yMinimum()
                        or second_box.yMaximum() < first_box.yMinimum()
                    )
                except Exception:
                    separated = False
                if separated:
                    continue
                if second_boundary is None or second_boundary.isEmpty():
                    continue
                try:
                    shared = first_boundary.intersection(second_boundary)
                except Exception:
                    continue
                source_vertices = [
                    point
                    for region in (first_region, second_region)
                    for ring in self._polygon_boundary_parts(region)
                    for point in ring
                ]
                for line_points in self._line_parts(shared):
                    for start_point, end_point in zip(line_points[:-1], line_points[1:]):
                        split_points = self._source_vertices_on_segment(
                            start_point, end_point, source_vertices
                        )
                        for segment_start, segment_end in zip(split_points[:-1], split_points[1:]):
                            if segment_start.distance(segment_end) <= 1e-6:
                                continue
                            segment_points = [segment_start, segment_end]
                            z_values = self._transition_z_values(segment_points, first, second)
                            z_line = self._line_points_to_z_geometry(segment_points, z_values)
                            if z_line is None or z_line.isEmpty():
                                continue
                            records.append(
                                (
                                    QgsGeometry(z_line),
                                    [
                                        f"{first.surface_id}|{second.surface_id}"[:160],
                                        "Transition",
                                        min(z_values),
                                        max(z_values),
                                        f"{first.surface_id}|{second.surface_id}"[:254],
                                        "cell_adjacency_boundary",
                                    ],
                                )
                            )
        return records

    @staticmethod
    def _source_vertices_on_segment(
        start: QgsPointXY,
        end: QgsPointXY,
        source_vertices: Sequence[QgsPointXY],
    ) -> List[QgsPointXY]:
        dx = end.x() - start.x()
        dy = end.y() - start.y()
        length_squared = (dx * dx) + (dy * dy)
        if length_squared <= 1e-12:
            return [start, end]
        located = [(0.0, start), (1.0, end)]
        seen = {(start.x(), start.y()), (end.x(), end.y())}
        for point in source_vertices:
            key = (point.x(), point.y())
            if key in seen:
                continue
            t = (((point.x() - start.x()) * dx) + ((point.y() - start.y()) * dy)) / length_squared
            if t <= 1e-12 or t >= 1.0 - 1e-12:
                continue
            projected = QgsPointXY(start.x() + (t * dx), start.y() + (t * dy))
            if projected.distance(point) > 1e-7:
                continue
            seen.add(key)
            located.append((t, point))
        located.sort(key=lambda item: item[0])
        return [point for _t, point in located]

    @staticmethod
    def _undirected_segment_key(
        start_point: QgsPointXY,
        end_point: QgsPointXY,
    ) -> Tuple[Tuple[float, float], Tuple[float, float]]:
        """Return a direction-independent key for reusing shared-edge probes."""
        start = (round(start_point.x(), 9), round(start_point.y(), 9))
        end = (round(end_point.x(), 9), round(end_point.y(), 9))
        return (start, end) if start <= end else (end, start)

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
        known_candidate: Optional[ControllingOlsCandidate] = None,
        known_region: Optional[QgsGeometry] = None,
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
            left_point = QgsPointXY(mid_point.x() + (nx * offset), mid_point.y() + (ny * offset))
            right_point = QgsPointXY(mid_point.x() - (nx * offset), mid_point.y() - (ny * offset))
            if known_candidate is not None and known_region is not None and not known_region.isEmpty():
                try:
                    left_inside = known_region.intersects(QgsGeometry.fromPointXY(left_point))
                    right_inside = known_region.intersects(QgsGeometry.fromPointXY(right_point))
                except Exception:
                    left_inside = right_inside = False
                if left_inside != right_inside:
                    outside_point = right_point if left_inside else left_point
                    outside = self.controlling_candidate_at_xy(outside_point)
                    if outside is not None and outside[0].surface_id != known_candidate.surface_id:
                        return known_candidate, outside[0]
                    continue

            left = self.controlling_candidate_at_xy(left_point)
            right = self.controlling_candidate_at_xy(right_point)
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
        if self._controlling_region_geometries_cache is None:
            self._controlling_region_geometries_cache = self._build_controlling_region_geometries()
        return [
            (candidate, QgsGeometry(region))
            for candidate, region in self._controlling_region_geometries_cache
        ]

    def _build_controlling_region_geometries(self) -> List[Tuple[ControllingOlsCandidate, QgsGeometry]]:
        solve_start = time.perf_counter()
        self._region_solve_stats = {
            "pair_checks": 0.0,
            "bbox_skips": 0.0,
            "geos_intersections": 0.0,
            "geos_intersection_time_s": 0.0,
            "lower_region_calls": 0.0,
            "linear_lower_time_s": 0.0,
            "curved_lower_time_s": 0.0,
            "curved_conical_conical_calls": 0.0,
            "curved_conical_constant_calls": 0.0,
            "curved_axis_conical_calls": 0.0,
            "curved_conical_plane_calls": 0.0,
            "curved_other_calls": 0.0,
            "sampled_lower_region_time_s": 0.0,
            "conical_constant_time_s": 0.0,
            "axis_conical_time_s": 0.0,
            "conical_plane_triangulated_time_s": 0.0,
            "triangulation_time_s": 0.0,
            "axis_station_band_time_s": 0.0,
            "axis_sample_decision_time_s": 0.0,
            "axis_band_triangulation_time_s": 0.0,
            "axis_exact_calls": 0.0,
            "axis_exact_success": 0.0,
            "axis_exact_fallback": 0.0,
            "axis_exact_unresolved": 0.0,
            "axis_exact_bad_model": 0.0,
            "axis_exact_no_curve": 0.0,
            "axis_exact_no_curve_mixed": 0.0,
            "axis_exact_split_invalid": 0.0,
            "axis_exact_union_failed": 0.0,
            "axis_exact_exception": 0.0,
            "axis_exact_polygonize_success": 0.0,
            "axis_exact_splitgeometry_used": 0.0,
            "axis_exact_manual_split_used": 0.0,
            "axis_exact_curve_vertices_raw": 0.0,
            "axis_exact_curve_vertices_simplified": 0.0,
            "axis_exact_curve_time_s": 0.0,
            "axis_zero_contour_calls": 0.0,
            "axis_zero_contour_success": 0.0,
            "axis_zero_contour_no_curve": 0.0,
            "axis_zero_contour_cells": 0.0,
            "axis_zero_contour_segments": 0.0,
            "axis_zero_contour_time_s": 0.0,
            "axis_exact_split_time_s": 0.0,
            "axis_exact_classify_time_s": 0.0,
            "axis_exact_total_time_s": 0.0,
            "axis_all_lower_bands": 0.0,
            "axis_all_higher_bands": 0.0,
            "axis_mixed_bands": 0.0,
            "axis_refined_bands": 0.0,
            "axis_triangulated_bands": 0.0,
            "triangulation_calls": 0.0,
            "triangulation_points_total": 0.0,
            "triangulation_points_max": 0.0,
            "losing_difference_time_s": 0.0,
            "region_difference_time_s": 0.0,
            "cleanup_time_s": 0.0,
            "repair_time_s": 0.0,
            "merge_time_s": 0.0,
            "total_time_s": 0.0,
        }
        if CONTROLLING_GLOBAL_CELL_SOLVER_ENABLED:
            global_start = time.perf_counter()
            global_region_parts = self._build_global_cell_region_geometries()
            self._region_solve_stats["global_cell_time_s"] = time.perf_counter() - global_start
            if global_region_parts:
                self._region_solve_stats["global_cell_solver_used"] = 1.0
                self._region_solve_stats["total_time_s"] = time.perf_counter() - solve_start
                return global_region_parts
            self._region_solve_stats["pairwise_solver_fallback_count"] = 1.0

        region_parts: List[Tuple[ControllingOlsCandidate, QgsGeometry]] = []
        for candidate in self.candidates:
            region = self._effective_footprint(candidate)
            for competitor in self._candidates_intersecting_geometry(region):
                if competitor.surface_id == candidate.surface_id:
                    continue
                self._region_solve_stats["pair_checks"] += 1.0
                if region is None or region.isEmpty():
                    break
                overlap = None
                try:
                    competitor_footprint = self._effective_footprint(competitor)
                    if competitor_footprint is None or competitor_footprint.isEmpty():
                        continue
                    if not self._bounding_boxes_intersect(region, competitor_footprint):
                        self._region_solve_stats["bbox_skips"] += 1.0
                        continue
                    intersection_start = time.perf_counter()
                    overlap = region.intersection(competitor_footprint)
                    self._region_solve_stats["geos_intersections"] += 1.0
                    self._region_solve_stats["geos_intersection_time_s"] += time.perf_counter() - intersection_start
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
                        if lower_region.isEmpty():
                            losing_area = overlap
                        else:
                            difference_start = time.perf_counter()
                            losing_area = overlap.difference(lower_region)
                            self._region_solve_stats["losing_difference_time_s"] += time.perf_counter() - difference_start
                    if losing_area is not None and not losing_area.isEmpty() and self._has_polygon_area(losing_area):
                        difference_start = time.perf_counter()
                        region = region.difference(losing_area)
                        self._region_solve_stats["region_difference_time_s"] += time.perf_counter() - difference_start
                except Exception:
                    region = QgsGeometry()
                    break

            cleanup_start = time.perf_counter()
            for region_part in self._polygon_parts(region):
                for final_part in self._polygon_parts(region_part):
                    for clean_part in self._clean_region_polygon_parts(final_part, candidate):
                        if clean_part.area() <= 1e-3:
                            continue
                        region_parts.append((candidate, clean_part))
            self._region_solve_stats["cleanup_time_s"] += time.perf_counter() - cleanup_start

        repair_start = time.perf_counter()
        self._repair_region_coverage(region_parts)
        self._region_solve_stats["repair_time_s"] = time.perf_counter() - repair_start
        merge_start = time.perf_counter()
        region_parts = self._merge_region_parts_by_candidate(region_parts)
        self._region_solve_stats["merge_time_s"] = time.perf_counter() - merge_start
        self._region_solve_stats["total_time_s"] = time.perf_counter() - solve_start
        return region_parts

    def region_solve_timing_summary(self) -> str:
        stats = self._region_solve_stats or {}
        if not stats:
            return "region solve stats unavailable"
        pair_checks = int(stats.get("pair_checks", 0.0))
        bbox_skips = int(stats.get("bbox_skips", 0.0))
        intersections = int(stats.get("geos_intersections", 0.0))
        lower_calls = int(stats.get("lower_region_calls", 0.0))
        triangulation_calls = int(stats.get("triangulation_calls", 0.0))
        avg_tri_points = (
            stats.get("triangulation_points_total", 0.0) / triangulation_calls
            if triangulation_calls
            else 0.0
        )
        global_summary = ""
        if stats.get("global_linework_count", 0.0) or stats.get("global_cell_count", 0.0):
            global_summary = (
                f"global[raw_linework={int(stats.get('global_raw_linework_count', 0.0))}, "
                f"linework={int(stats.get('global_linework_count', 0.0))}, "
                f"cells={int(stats.get('global_cell_count', 0.0))}, "
                f"assigned={int(stats.get('global_assigned_cell_count', 0.0))}, "
                f"refined={int(stats.get('global_refined_cell_count', 0.0))}, "
                f"regions={int(stats.get('global_region_count', 0.0))}, "
                f"time={stats.get('global_cell_time_s', 0.0):.2f}s], "
            )
        return (
            f"region solve: {global_summary}pairs={pair_checks}, bbox_skips={bbox_skips}, "
            f"intersections={intersections} ({stats.get('geos_intersection_time_s', 0.0):.2f}s), "
            f"lower_calls={lower_calls}, linear={stats.get('linear_lower_time_s', 0.0):.2f}s, "
            f"curved={stats.get('curved_lower_time_s', 0.0):.2f}s, "
            f"curved_calls[cc={int(stats.get('curved_conical_conical_calls', 0.0))}, "
            f"const={int(stats.get('curved_conical_constant_calls', 0.0))}, "
            f"axis={int(stats.get('curved_axis_conical_calls', 0.0))}, "
            f"plane={int(stats.get('curved_conical_plane_calls', 0.0))}, "
            f"other={int(stats.get('curved_other_calls', 0.0))}], "
            f"curved_time[sampled={stats.get('sampled_lower_region_time_s', 0.0):.2f}s, "
            f"const={stats.get('conical_constant_time_s', 0.0):.2f}s, "
            f"axis={stats.get('axis_conical_time_s', 0.0):.2f}s, "
            f"axis_exact[calls={int(stats.get('axis_exact_calls', 0.0))}, "
            f"success={int(stats.get('axis_exact_success', 0.0))}, "
            f"fallback={int(stats.get('axis_exact_fallback', 0.0))}, "
            f"unresolved={int(stats.get('axis_exact_unresolved', 0.0))}, "
            f"reasons[bad_model={int(stats.get('axis_exact_bad_model', 0.0))}, "
            f"no_curve={int(stats.get('axis_exact_no_curve', 0.0))}, "
            f"no_curve_mixed={int(stats.get('axis_exact_no_curve_mixed', 0.0))}, "
            f"split_invalid={int(stats.get('axis_exact_split_invalid', 0.0))}, "
            f"union_failed={int(stats.get('axis_exact_union_failed', 0.0))}, "
            f"exception={int(stats.get('axis_exact_exception', 0.0))}], "
            f"split_method[polygonize={int(stats.get('axis_exact_polygonize_success', 0.0))}, "
            f"manual={int(stats.get('axis_exact_manual_split_used', 0.0))}, "
            f"splitGeometry={int(stats.get('axis_exact_splitgeometry_used', 0.0))}], "
            f"curve_vertices[raw={int(stats.get('axis_exact_curve_vertices_raw', 0.0))}, "
            f"simplified={int(stats.get('axis_exact_curve_vertices_simplified', 0.0))}], "
            f"curve={stats.get('axis_exact_curve_time_s', 0.0):.2f}s, "
            f"zero_contour[calls={int(stats.get('axis_zero_contour_calls', 0.0))}, "
            f"success={int(stats.get('axis_zero_contour_success', 0.0))}, "
            f"none={int(stats.get('axis_zero_contour_no_curve', 0.0))}, "
            f"cells={int(stats.get('axis_zero_contour_cells', 0.0))}, "
            f"segments={int(stats.get('axis_zero_contour_segments', 0.0))}, "
            f"time={stats.get('axis_zero_contour_time_s', 0.0):.2f}s], "
            f"split={stats.get('axis_exact_split_time_s', 0.0):.2f}s, "
            f"classify={stats.get('axis_exact_classify_time_s', 0.0):.2f}s, "
            f"total={stats.get('axis_exact_total_time_s', 0.0):.2f}s], "
            f"plane_tri={stats.get('conical_plane_triangulated_time_s', 0.0):.2f}s, "
            f"tri_total={stats.get('triangulation_time_s', 0.0):.2f}s, "
            f"axis_band={stats.get('axis_station_band_time_s', 0.0):.2f}s, "
            f"axis_decision={stats.get('axis_sample_decision_time_s', 0.0):.2f}s, "
            f"axis_tri={stats.get('axis_band_triangulation_time_s', 0.0):.2f}s], "
            f"axis_bands[lower={int(stats.get('axis_all_lower_bands', 0.0))}, "
            f"higher={int(stats.get('axis_all_higher_bands', 0.0))}, "
            f"mixed={int(stats.get('axis_mixed_bands', 0.0))}, "
            f"refined={int(stats.get('axis_refined_bands', 0.0))}, "
            f"triangulated={int(stats.get('axis_triangulated_bands', 0.0))}], "
            f"tri_points[calls={triangulation_calls}, avg={avg_tri_points:.1f}, "
            f"max={int(stats.get('triangulation_points_max', 0.0))}], "
            f"losing_diff={stats.get('losing_difference_time_s', 0.0):.2f}s, "
            f"region_diff={stats.get('region_difference_time_s', 0.0):.2f}s, "
            f"cleanup={stats.get('cleanup_time_s', 0.0):.2f}s, "
            f"repair={stats.get('repair_time_s', 0.0):.2f}s, "
            f"merge={stats.get('merge_time_s', 0.0):.2f}s, "
            f"total={stats.get('total_time_s', 0.0):.2f}s"
        )

    def _build_global_cell_region_geometries(self) -> List[Tuple[ControllingOlsCandidate, QgsGeometry]]:
        """Build one global arrangement, then label each cell by lowest candidate."""
        if not hasattr(QgsGeometry, "polygonize"):
            return []

        raw_linework = self._global_cell_linework()
        self._region_solve_stats["global_raw_linework_count"] = float(len(raw_linework))
        linework = self._noded_global_linework(raw_linework)
        self._region_solve_stats["global_linework_count"] = float(len(linework))
        if len(linework) < 3:
            return []

        try:
            polygonized = QgsGeometry.polygonize(linework)
        except Exception as exc:
            QgsMessageLog.logMessage(
                f"Controlling OLS global cell solver polygonize failed: {exc}",
                PLUGIN_TAG,
                level=Qgis.Warning,
            )
            return []
        if not self._has_polygon_area(polygonized):
            return []

        cell_parts: List[Tuple[ControllingOlsCandidate, QgsGeometry]] = []
        cell_count = 0
        assigned_count = 0
        unassigned_count = 0
        refined_count = 0
        minimum_cell_area_m2 = (
            CONTROLLING_MOS139_CONICAL_CELL_MIN_AREA_M2
            if any(
                candidate.model == "conical"
                and not str((candidate.metadata or {}).get("annex14_family") or "").strip()
                for candidate in self.candidates
            )
            else CONTROLLING_GLOBAL_CELL_MIN_AREA_M2
        )
        for cell in self._polygon_parts(polygonized):
            if not self._has_polygon_area(cell, min_area=minimum_cell_area_m2):
                continue
            cell_count += 1
            controller = self._controlling_candidate_for_cell(cell)
            if controller is None:
                unassigned_count += 1
                continue
            candidate, _elevation = controller
            refinement_candidates = self._global_cell_refinement_candidates(cell, candidate)
            if refinement_candidates:
                refined_parts = self._lower_envelope_parts_for_candidates(cell, refinement_candidates)
                if refined_parts:
                    for refined_candidate, refined_geometry in refined_parts:
                        if not self._has_polygon_area(
                            refined_geometry,
                            min_area=minimum_cell_area_m2,
                        ):
                            continue
                        cell_parts.append((refined_candidate, refined_geometry))
                        assigned_count += 1
                    refined_count += 1
                    continue
            try:
                clipped_cell = cell.intersection(self._effective_footprint(candidate))
            except Exception:
                clipped_cell = QgsGeometry(cell)
            for part in self._polygon_parts(clipped_cell):
                if not self._has_polygon_area(
                    part,
                    min_area=minimum_cell_area_m2,
                ):
                    continue
                cell_parts.append((candidate, part))
                assigned_count += 1

        self._region_solve_stats["global_cell_count"] = float(cell_count)
        self._region_solve_stats["global_assigned_cell_count"] = float(assigned_count)
        self._region_solve_stats["global_unassigned_cell_count"] = float(unassigned_count)
        self._region_solve_stats["global_refined_cell_count"] = float(refined_count)
        if not cell_parts:
            return []

        cell_parts.extend(self._global_subdivision_completion_parts(cell_parts))

        merge_start = time.perf_counter()
        merged_parts = self._merge_region_parts_by_candidate(cell_parts)
        merged_parts = self._enforce_exclusive_merged_regions(merged_parts)
        merged_parts = self._normalise_exclusive_region_boundaries(merged_parts)
        self._region_solve_stats["merge_time_s"] = time.perf_counter() - merge_start
        self._region_solve_stats["global_region_count"] = float(len(merged_parts))
        self._region_solve_stats["invalid_output_region_count"] = float(sum(
            1 for _candidate, geometry in merged_parts if not geometry.isGeosValid()
        ))
        return merged_parts

    def _enforce_exclusive_merged_regions(
        self,
        regions: Sequence[Tuple[ControllingOlsCandidate, QgsGeometry]],
    ) -> List[Tuple[ControllingOlsCandidate, QgsGeometry]]:
        """Assign every merged overlap from one shared lower-envelope solution."""
        exclusive = [(candidate, QgsGeometry(geometry)) for candidate, geometry in regions]
        for first_index in range(len(exclusive)):
            first_candidate, first_geometry = exclusive[first_index]
            if not self._has_polygon_area(first_geometry):
                continue
            for second_index in range(first_index + 1, len(exclusive)):
                second_candidate, second_geometry = exclusive[second_index]
                families = {
                    str((candidate.metadata or {}).get("annex14_family") or "").strip().upper()
                    for candidate in (first_candidate, second_candidate)
                }
                if families != {""} or "conical" not in {
                    first_candidate.model,
                    second_candidate.model,
                }:
                    continue
                if not self._has_polygon_area(second_geometry):
                    continue
                if not self._bounding_boxes_intersect(first_geometry, second_geometry):
                    continue
                try:
                    overlap = first_geometry.intersection(second_geometry)
                except Exception:
                    overlap = None
                if not self._has_polygon_area(overlap):
                    continue
                lower = self._unanimous_pair_lower_region(
                    first_candidate, second_candidate, overlap
                )
                if lower is None:
                    lower = self._candidate_lower_region(
                        first_candidate,
                        second_candidate,
                        overlap,
                    )
                lower = self._clip_lower_region_to_overlap(lower, overlap) if lower is not None else None
                if lower is None:
                    try:
                        lower = self._triangulated_candidate_lower_region(
                            first_candidate,
                            second_candidate,
                            overlap,
                        )
                    except Exception:
                        lower = None
                    lower = (
                        self._clip_lower_region_to_overlap(lower, overlap)
                        if lower is not None
                        else None
                    )
                    if lower is not None:
                        self._region_solve_stats["merged_overlap_triangulated_count"] = (
                            self._region_solve_stats.get("merged_overlap_triangulated_count", 0.0)
                            + 1.0
                        )
                if lower is None:
                    try:
                        point = overlap.pointOnSurface().asPoint()
                        point_xy = QgsPointXY(point.x(), point.y())
                        first_z = first_candidate.elevation_at_xy(point_xy)
                        second_z = second_candidate.elevation_at_xy(point_xy)
                    except Exception:
                        first_z = second_z = None
                    if first_z is not None and second_z is not None:
                        lower = (
                            QgsGeometry(overlap)
                            if first_z <= second_z
                            else QgsGeometry()
                        )
                        self._region_solve_stats["merged_overlap_representative_count"] = (
                            self._region_solve_stats.get("merged_overlap_representative_count", 0.0)
                            + 1.0
                        )
                if lower is None:
                    self._region_solve_stats["merged_overlap_unresolved_count"] = (
                        self._region_solve_stats.get("merged_overlap_unresolved_count", 0.0) + 1.0
                    )
                    self._region_solve_stats["merged_overlap_unresolved_area_m2"] = (
                        self._region_solve_stats.get("merged_overlap_unresolved_area_m2", 0.0)
                        + overlap.area()
                    )
                    continue
                try:
                    first_losing = overlap if lower.isEmpty() else overlap.difference(lower)
                    second_losing = lower
                    if self._has_polygon_area(first_losing):
                        first_geometry = first_geometry.difference(first_losing)
                    if self._has_polygon_area(second_losing):
                        second_geometry = second_geometry.difference(second_losing)
                except Exception:
                    self._region_solve_stats["merged_overlap_unresolved_count"] = (
                        self._region_solve_stats.get("merged_overlap_unresolved_count", 0.0) + 1.0
                    )
                    continue
                exclusive[first_index] = (first_candidate, first_geometry)
                exclusive[second_index] = (second_candidate, second_geometry)
                self._region_solve_stats["merged_overlap_resolved_count"] = (
                    self._region_solve_stats.get("merged_overlap_resolved_count", 0.0) + 1.0
                )
                self._region_solve_stats["merged_overlap_resolved_area_m2"] = (
                    self._region_solve_stats.get("merged_overlap_resolved_area_m2", 0.0)
                    + overlap.area()
                )
        return [
            (candidate, geometry)
            for candidate, geometry in exclusive
            if self._has_polygon_area(geometry)
        ]

    def _normalise_exclusive_region_boundaries(
        self,
        regions: Sequence[Tuple[ControllingOlsCandidate, QgsGeometry]],
    ) -> List[Tuple[ControllingOlsCandidate, QgsGeometry]]:
        """Remove complementary ring hairpins without changing partition coverage."""
        original = [
            (candidate, QgsGeometry(geometry))
            for candidate, geometry in regions
            if self._has_polygon_area(geometry)
        ]
        normalised: List[Tuple[ControllingOlsCandidate, QgsGeometry]] = []
        changed_count = 0
        reassigned_area_m2 = 0.0
        for candidate, geometry in original:
            opened = self._open_boundary_touching_holes_geometry(geometry)
            cleaned = self._despiked_polygon_geometry(
                opened if opened is not None else geometry
            )
            if not self._has_polygon_area(cleaned) or not cleaned.isGeosValid():
                return original
            length_change = abs(cleaned.length() - geometry.length())
            area_change = abs(cleaned.area() - geometry.area())
            if length_change > 1e-6 or area_change > 1e-9:
                changed_count += 1
                reassigned_area_m2 += area_change
            normalised.append((candidate, cleaned))

        if not changed_count:
            return original
        original_geometries = [geometry for _candidate, geometry in original]
        normalised_geometries = [geometry for _candidate, geometry in normalised]
        try:
            original_union = QgsGeometry.unaryUnion(original_geometries)
            normalised_union = QgsGeometry.unaryUnion(normalised_geometries)
            coverage_change_m2 = original_union.symDifference(normalised_union).area()
            original_overlap_proxy_m2 = max(
                0.0,
                sum(geometry.area() for geometry in original_geometries)
                - original_union.area(),
            )
            normalised_overlap_proxy_m2 = max(
                0.0,
                sum(geometry.area() for geometry in normalised_geometries)
                - normalised_union.area(),
            )
        except Exception:
            return original
        tolerance_m2 = CONTROLLING_REGION_DISSOLVE_MAX_AREA_CHANGE_M2
        if coverage_change_m2 > tolerance_m2:
            return original
        if normalised_overlap_proxy_m2 > original_overlap_proxy_m2 + tolerance_m2:
            return original

        self._region_solve_stats["exclusive_boundary_normalisation_count"] = float(
            changed_count
        )
        self._region_solve_stats["exclusive_boundary_reassigned_area_m2"] = float(
            reassigned_area_m2 / 2.0
        )
        self._region_solve_stats["exclusive_boundary_coverage_change_m2"] = float(
            coverage_change_m2
        )
        self._region_solve_stats["exclusive_boundary_overlap_change_m2"] = float(
            normalised_overlap_proxy_m2 - original_overlap_proxy_m2
        )
        return normalised

    def _unanimous_pair_lower_region(
        self,
        first: ControllingOlsCandidate,
        second: ControllingOlsCandidate,
        overlap: QgsGeometry,
    ) -> Optional[QgsGeometry]:
        """Resolve a wholly one-sided overlap without rebuilding its equality curve."""
        differences = []
        for point in self._geometry_sample_points(overlap):
            first_z = first.elevation_at_xy(point)
            second_z = second.elevation_at_xy(point)
            if first_z is None or second_z is None:
                continue
            differences.append(float(first_z) - float(second_z))
        if not differences:
            return None
        if max(differences) < -1e-9:
            self._region_solve_stats["merged_overlap_unanimous_count"] = (
                self._region_solve_stats.get("merged_overlap_unanimous_count", 0.0) + 1.0
            )
            return QgsGeometry(overlap)
        if min(differences) > 1e-9:
            self._region_solve_stats["merged_overlap_unanimous_count"] = (
                self._region_solve_stats.get("merged_overlap_unanimous_count", 0.0) + 1.0
            )
            return QgsGeometry()
        return None


    def _global_subdivision_completion_parts(
        self,
        cell_parts: Sequence[Tuple[ControllingOlsCandidate, QgsGeometry]],
    ) -> List[Tuple[ControllingOlsCandidate, QgsGeometry]]:
        """Complete polygonize omissions only when all topology checkpoints agree."""
        coverage_parts = [
            self._effective_footprint(candidate)
            for candidate in self.candidates
            if self._has_polygon_area(self._effective_footprint(candidate))
        ]
        solved_parts = [geometry for _candidate, geometry in cell_parts if self._has_polygon_area(geometry)]
        try:
            coverage = QgsGeometry.unaryUnion(coverage_parts)
            solved = QgsGeometry.unaryUnion(solved_parts)
            gaps = coverage.difference(solved)
        except Exception:
            return []

        completed = []
        for gap in self._polygon_parts(gaps):
            if not self._has_polygon_area(gap, min_area=1e-3):
                continue
            controller = self._unanimous_controller_for_cell(gap)
            if controller is None:
                self._region_solve_stats["global_ambiguous_gap_part_count"] = (
                    self._region_solve_stats.get("global_ambiguous_gap_part_count", 0.0) + 1.0
                )
                self._region_solve_stats["global_ambiguous_gap_area_m2"] = (
                    self._region_solve_stats.get("global_ambiguous_gap_area_m2", 0.0) + gap.area()
                )
                continue
            try:
                owned = gap.intersection(self._effective_footprint(controller))
            except Exception:
                owned = None
            if not self._has_polygon_area(owned) or not self._areas_match(owned, gap, tolerance_m2=1e-3):
                self._region_solve_stats["global_ambiguous_gap_part_count"] = (
                    self._region_solve_stats.get("global_ambiguous_gap_part_count", 0.0) + 1.0
                )
                self._region_solve_stats["global_ambiguous_gap_area_m2"] = (
                    self._region_solve_stats.get("global_ambiguous_gap_area_m2", 0.0) + gap.area()
                )
                continue
            completed.append((controller, owned))
            self._region_solve_stats["global_unanimous_gap_part_count"] = (
                self._region_solve_stats.get("global_unanimous_gap_part_count", 0.0) + 1.0
            )
            self._region_solve_stats["global_unanimous_gap_area_m2"] = (
                self._region_solve_stats.get("global_unanimous_gap_area_m2", 0.0) + owned.area()
            )
        return completed

    def _unanimous_controller_for_cell(
        self,
        cell: QgsGeometry,
    ) -> Optional[ControllingOlsCandidate]:
        points = self._global_cell_validation_points(cell)
        try:
            vertices = [QgsPointXY(vertex.x(), vertex.y()) for vertex in cell.vertices()]
        except Exception:
            vertices = []
        points.extend(vertices)
        for first, second in zip(vertices, vertices[1:]):
            points.append(QgsPointXY((first.x() + second.x()) / 2.0, (first.y() + second.y()) / 2.0))
        controller_by_id = {}
        for point in points:
            result = self.controlling_candidate_at_xy(point)
            if result is None:
                return None
            controller_by_id[result[0].surface_id] = result[0]
            if len(controller_by_id) > 1:
                return None
        return next(iter(controller_by_id.values()), None)

    def _global_cell_refinement_candidates(
        self,
        cell: QgsGeometry,
        assigned_candidate: ControllingOlsCandidate,
    ) -> List[ControllingOlsCandidate]:
        """Return a small candidate set when interior samples disagree with a cell's controller."""
        if cell is None or cell.isEmpty() or assigned_candidate is None:
            return []
        try:
            boundary = cell.boundary()
        except Exception:
            boundary = None

        candidates_by_id: Dict[str, ControllingOlsCandidate] = {assigned_candidate.surface_id: assigned_candidate}
        disagreement_magnitudes: List[float] = []
        for point_xy in self._global_cell_validation_points(cell):
            try:
                if boundary is not None and not boundary.isEmpty():
                    if QgsGeometry.fromPointXY(point_xy).distance(boundary) <= 0.05:
                        continue
                controller = self.controlling_candidate_at_xy(point_xy)
            except Exception:
                continue
            if controller is None:
                continue
            candidate, _elevation = controller
            if candidate.surface_id != assigned_candidate.surface_id:
                candidates_by_id[candidate.surface_id] = candidate
                difference = self._candidate_difference(
                    assigned_candidate,
                    candidate,
                    point_xy,
                )
                if difference is not None and math.isfinite(difference):
                    disagreement_magnitudes.append(abs(float(difference)))

        candidates = list(candidates_by_id.values())
        if len(candidates) <= 1:
            return []
        if (
            len(candidates) == 2
            and {candidate.model for candidate in candidates} == {"axis", "conical"}
            and any(
                candidate.model == "axis"
                and self._axis_conical_zero_contour_applies(candidate)
                for candidate in candidates
            )
            and disagreement_magnitudes
            and max(disagreement_magnitudes) <= AXIS_CONICAL_GLOBAL_CELL_CHORD_ERROR_M
        ):
            # The cell was already split by the shared sampled zero contour. A
            # second TIN solve follows a slightly different chord and creates
            # narrow, non-contiguous wedges along stronger conical curvature.
            # Keep the one polygonization boundary when the sampled elevation
            # residual is within its explicit chord-error allowance.
            self._region_solve_stats["axis_conical_chord_refinement_suppressed"] = (
                self._region_solve_stats.get("axis_conical_chord_refinement_suppressed", 0.0)
                + 1.0
            )
            return []
        return candidates

    def _lower_envelope_parts_for_candidates(
        self,
        domain: QgsGeometry,
        candidates: Sequence[ControllingOlsCandidate],
    ) -> List[Tuple[ControllingOlsCandidate, QgsGeometry]]:
        refined_parts: List[Tuple[ControllingOlsCandidate, QgsGeometry]] = []
        for candidate in candidates:
            try:
                candidate_footprint = self._effective_footprint(candidate)
                if not self._bounding_boxes_intersect(domain, candidate_footprint):
                    continue
                candidate_region = domain.intersection(candidate_footprint)
            except Exception:
                candidate_region = None
            if not self._has_polygon_area(candidate_region):
                continue
            for competitor in candidates:
                if competitor.surface_id == candidate.surface_id:
                    continue
                if candidate_region is None or candidate_region.isEmpty():
                    break
                try:
                    competitor_footprint = self._effective_footprint(competitor)
                    if not self._bounding_boxes_intersect(candidate_region, competitor_footprint):
                        continue
                    overlap = candidate_region.intersection(competitor_footprint)
                except Exception:
                    overlap = None
                if not self._has_polygon_area(overlap):
                    continue
                lower_region = self._local_refinement_lower_region(candidate, competitor, overlap)
                if lower_region is None:
                    continue
                if lower_region.isEmpty():
                    losing_area = overlap
                else:
                    lower_region = self._clip_lower_region_to_overlap(lower_region, overlap)
                    if lower_region is None:
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
                        refined_parts.append((candidate, clean_part))
        return refined_parts

    def _local_refinement_lower_region(
        self,
        candidate: ControllingOlsCandidate,
        competitor: ControllingOlsCandidate,
        overlap: QgsGeometry,
    ) -> Optional[QgsGeometry]:
        """Resolve a small mixed global cell without invoking broad axis/conical station bands."""
        if (
            {candidate.model, competitor.model} == {"axis", "conical"}
            and self._has_polygon_area(overlap)
        ):
            return self._triangulated_candidate_lower_region(candidate, competitor, overlap)
        return self._candidate_lower_region(candidate, competitor, overlap)

    def _global_cell_validation_points(self, cell: QgsGeometry) -> List[QgsPointXY]:
        sample_points: List[QgsPointXY] = []
        seen = set()

        def _add(point_xy: QgsPointXY) -> None:
            key = (round(point_xy.x(), 3), round(point_xy.y(), 3))
            if key in seen:
                return
            seen.add(key)
            sample_points.append(point_xy)

        try:
            point = cell.pointOnSurface().asPoint()
            _add(QgsPointXY(point.x(), point.y()))
        except Exception:
            pass
        try:
            bbox = cell.boundingBox()
            for fx in (0.2, 0.4, 0.6, 0.8):
                for fy in (0.2, 0.4, 0.6, 0.8):
                    point_xy = QgsPointXY(
                        bbox.xMinimum() + (bbox.width() * fx),
                        bbox.yMinimum() + (bbox.height() * fy),
                    )
                    if cell.intersects(QgsGeometry.fromPointXY(point_xy)):
                        _add(point_xy)
        except Exception:
            pass
        return sample_points

    def _global_cell_linework(self) -> List[QgsGeometry]:
        linework: List[QgsGeometry] = []
        effective_footprints: Dict[str, QgsGeometry] = {}
        for candidate in self.candidates:
            footprint = self._effective_footprint(candidate)
            if not self._has_polygon_area(footprint):
                continue
            effective_footprints[candidate.surface_id] = footprint
            self._append_polygon_boundary_linework(linework, footprint)

        for index, first_candidate in enumerate(self.candidates):
            first_footprint = effective_footprints.get(first_candidate.surface_id)
            if not self._has_polygon_area(first_footprint):
                continue
            for second_candidate in self.candidates[index + 1 :]:
                second_footprint = effective_footprints.get(second_candidate.surface_id)
                if not self._has_polygon_area(second_footprint):
                    continue
                if not self._bounding_boxes_intersect(first_footprint, second_footprint):
                    continue
                try:
                    overlap = first_footprint.intersection(second_footprint)
                except Exception:
                    overlap = None
                if not self._has_polygon_area(overlap):
                    continue
                for overlap_part in self._polygon_parts(overlap):
                    self._append_pair_construction_linework(
                        linework,
                        overlap_part,
                        first_candidate,
                        second_candidate,
                    )
        return [geometry for geometry in linework if geometry is not None and not geometry.isEmpty()]

    def _noded_global_linework(self, linework: Sequence[QgsGeometry]) -> List[QgsGeometry]:
        valid_linework = [QgsGeometry(geometry) for geometry in linework if geometry is not None and not geometry.isEmpty()]
        if not valid_linework:
            return []
        try:
            noded = QgsGeometry.unaryUnion(valid_linework) if len(valid_linework) > 1 else valid_linework[0]
        except Exception as exc:
            QgsMessageLog.logMessage(
                f"Controlling OLS global cell solver line noding failed: {exc}",
                PLUGIN_TAG,
                level=Qgis.Warning,
            )
            return valid_linework
        if noded is None or noded.isEmpty():
            return valid_linework

        noded_segments: List[QgsGeometry] = []
        for line_points in self._line_parts(noded):
            for start_point, end_point in zip(line_points[:-1], line_points[1:]):
                if start_point.distance(end_point) <= 1e-6:
                    continue
                segment = QgsGeometry.fromPolylineXY([start_point, end_point])
                if segment is not None and not segment.isEmpty():
                    noded_segments.append(segment)
        return noded_segments if len(noded_segments) >= 3 else valid_linework

    def _append_polygon_boundary_linework(self, linework: List[QgsGeometry], polygon_geometry: QgsGeometry) -> None:
        for ring_points in self._polygon_boundary_parts(polygon_geometry):
            if len(ring_points) < 2:
                continue
            line = QgsGeometry.fromPolylineXY(ring_points)
            if line is not None and not line.isEmpty():
                linework.append(line)

    def _append_pair_construction_linework(
        self,
        linework: List[QgsGeometry],
        domain: QgsGeometry,
        first_candidate: ControllingOlsCandidate,
        second_candidate: ControllingOlsCandidate,
    ) -> None:
        equality = self._global_equality_geometry_for_pair(domain, first_candidate, second_candidate)
        if equality is not None and not equality.isEmpty():
            self._append_linework_geometry(linework, equality, domain=domain)
            return

        fallback = self._fallback_pair_boundary_geometry(domain, first_candidate, second_candidate)
        if fallback is not None and not fallback.isEmpty():
            self._append_linework_geometry(linework, fallback, domain=domain)

    def _append_linework_geometry(
        self,
        linework: List[QgsGeometry],
        geometry: QgsGeometry,
        domain: Optional[QgsGeometry] = None,
    ) -> None:
        for line_points in self._line_parts(geometry):
            if domain is not None:
                line_points = self._condition_transition_curve_for_polygonize(line_points, domain)
            if len(line_points) < 2:
                continue
            line = QgsGeometry.fromPolylineXY(line_points)
            if line is not None and not line.isEmpty():
                linework.append(line)

    def _global_equality_geometry_for_pair(
        self,
        domain: QgsGeometry,
        first_candidate: ControllingOlsCandidate,
        second_candidate: ControllingOlsCandidate,
    ) -> Optional[QgsGeometry]:
        first_conical = first_candidate.model == "conical"
        second_conical = second_candidate.model == "conical"
        if not first_conical and not second_conical:
            return self._plane_plane_line(domain, first_candidate, second_candidate)

        if first_conical and second_conical:
            return None

        conical_candidate = first_candidate if first_conical else second_candidate
        other_candidate = second_candidate if first_conical else first_candidate
        if other_candidate.model == "constant":
            return self._conical_constant_equality_geometry(domain, conical_candidate, other_candidate)
        if other_candidate.model == "axis":
            conical_model = self._conical_model(conical_candidate)
            axis = self._axis_model(other_candidate)
            if conical_model is None or axis is None:
                return None
            sampled_curve = self._axis_conical_sampled_transition_curve(
                other_candidate,
                conical_candidate,
                axis,
                conical_model,
                domain,
            )
            if sampled_curve is not None and not sampled_curve.isEmpty():
                return sampled_curve
            return self._axis_conical_transition_curve(axis, conical_model, domain)
        return None

    def _conical_constant_equality_geometry(
        self,
        domain: QgsGeometry,
        conical_candidate: ControllingOlsCandidate,
        constant_candidate: ControllingOlsCandidate,
    ) -> Optional[QgsGeometry]:
        conical_model = self._conical_model(conical_candidate)
        constant_elevation = self._constant_elevation(constant_candidate)
        if conical_model is None or constant_elevation is None:
            return None
        slope = float(conical_model.get("slope", 0.0))
        if slope <= 0.0:
            return None
        distance = (constant_elevation - float(conical_model["base_elevation_m"])) / slope
        if distance < -self.tie_tolerance_m:
            return None
        max_distance = conical_model.get("max_distance_m")
        if max_distance is not None and distance > float(max_distance) + self.tie_tolerance_m:
            return None
        distance = max(0.0, distance)
        base_footprint = conical_model.get("base_footprint")
        if base_footprint is None or base_footprint.isEmpty():
            return None
        try:
            offset_geometry = (
                QgsGeometry(base_footprint).boundary()
                if distance <= 1e-6
                else QgsGeometry(base_footprint).buffer(distance, CONTROLLING_REGION_GEOMETRY_REPAIR_SEGMENTS).boundary()
            )
            return offset_geometry.intersection(domain)
        except Exception:
            return None

    def _fallback_pair_boundary_geometry(
        self,
        domain: QgsGeometry,
        first_candidate: ControllingOlsCandidate,
        second_candidate: ControllingOlsCandidate,
    ) -> Optional[QgsGeometry]:
        lower_region = self._candidate_lower_region(first_candidate, second_candidate, domain)
        if lower_region is None or lower_region.isEmpty():
            return None
        clipped_lower = self._clip_lower_region_to_overlap(lower_region, domain)
        if clipped_lower is None or clipped_lower.isEmpty():
            return None
        if self._areas_match(clipped_lower, domain):
            return None
        try:
            return clipped_lower.boundary().intersection(domain)
        except Exception:
            return None

    def _areas_match(self, first: QgsGeometry, second: QgsGeometry, tolerance_m2: float = 1.0) -> bool:
        if not self._has_polygon_area(first) or not self._has_polygon_area(second):
            return False
        try:
            first_area = abs(first.area())
            second_area = abs(second.area())
        except Exception:
            return False
        return abs(first_area - second_area) <= max(tolerance_m2, second_area * 1e-10)

    def _controlling_candidate_for_cell(
        self,
        cell: QgsGeometry,
    ) -> Optional[Tuple[ControllingOlsCandidate, float]]:
        sample_points: List[QgsPointXY] = []
        try:
            point = cell.pointOnSurface().asPoint()
            sample_points.append(QgsPointXY(point.x(), point.y()))
        except Exception:
            pass
        sample_points.extend(self._geometry_sample_points(cell)[:5])

        for point_xy in sample_points:
            result = self.controlling_candidate_at_xy(point_xy)
            if result is not None:
                return result
        return None

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
        for candidate in self.candidates:
            grouped_entry = grouped.get(candidate.surface_id)
            if grouped_entry is None:
                continue
            _, geometries = grouped_entry
            dissolve_geometries = [self._region_dissolve_geometry(geometry) for geometry in geometries]
            try:
                merged = (
                    QgsGeometry.unaryUnion(dissolve_geometries)
                    if len(dissolve_geometries) > 1
                    else QgsGeometry(dissolve_geometries[0])
                )
            except Exception:
                merged = QgsGeometry()
            if not self._has_polygon_area(merged):
                continue
            source_boundary = self._combined_boundary_geometry(geometries)
            cleaned_merged = self._clean_merged_region_geometry(merged, candidate, source_boundary)
            if self._has_polygon_area(cleaned_merged):
                merged_parts.append((candidate, cleaned_merged))
        return merged_parts

    def _region_dissolve_geometry(self, geometry: QgsGeometry) -> QgsGeometry:
        """Remove sub-micrometre coordinate noise before same-candidate dissolve."""
        try:
            snapped = geometry.snappedToGrid(
                CONTROLLING_REGION_DISSOLVE_GRID_M,
                CONTROLLING_REGION_DISSOLVE_GRID_M,
            )
            if self._has_polygon_area(snapped) and snapped.isGeosValid():
                return snapped
        except Exception:
            pass
        return QgsGeometry(geometry)

    def _clean_merged_region_geometry(
        self,
        geometry: QgsGeometry,
        candidate: ControllingOlsCandidate,
        source_boundary: Optional[QgsGeometry] = None,
    ) -> Optional[QgsGeometry]:
        """Clean dissolved same-candidate regions while preserving multipart output."""
        cleaned_parts: List[QgsGeometry] = []
        for polygon_part in self._polygon_parts(geometry):
            for clean_part in self._clean_region_polygon_parts(polygon_part, candidate):
                if clean_part.area() <= 1e-3:
                    continue
                cleaned_parts.append(clean_part)
        if not cleaned_parts:
            return None
        if len(cleaned_parts) == 1:
            return cleaned_parts[0]
        try:
            dissolved = QgsGeometry.unaryUnion(cleaned_parts)
        except Exception:
            dissolved = None
        if source_boundary is None:
            source_boundary = self._combined_boundary_geometry(cleaned_parts)
        dissolved = self._finalize_dissolved_region_geometry(dissolved, source_boundary=source_boundary)
        if self._has_polygon_area(dissolved):
            return dissolved

        multi_polygon = []
        for clean_part in cleaned_parts:
            try:
                polygon = clean_part.asPolygon()
            except Exception:
                polygon = []
            if polygon:
                multi_polygon.append(polygon)
        return QgsGeometry.fromMultiPolygonXY(multi_polygon) if multi_polygon else None

    def _finalize_dissolved_region_geometry(
        self,
        geometry: Optional[QgsGeometry],
        source_boundary: Optional[QgsGeometry] = None,
    ) -> Optional[QgsGeometry]:
        """Collapse shared internal multipart boundaries without offsetting solved edges."""
        if not self._has_polygon_area(geometry):
            return geometry
        candidates: List[QgsGeometry] = []
        if not self._introduces_long_new_boundary_segment(geometry, source_boundary):
            candidates.append(geometry)
        if self._polygon_part_count(geometry) > 1:
            try:
                retry_dissolved = geometry.snappedToGrid(
                    CONTROLLING_REGION_DISSOLVE_RETRY_GRID_M,
                    CONTROLLING_REGION_DISSOLVE_RETRY_GRID_M,
                ).buffer(0.0, 8)
                area_change = abs(retry_dissolved.area() - geometry.area())
                if (
                    self._has_polygon_area(retry_dissolved)
                    and area_change <= CONTROLLING_REGION_DISSOLVE_MAX_AREA_CHANGE_M2
                    and not self._introduces_long_new_boundary_segment(retry_dissolved, source_boundary)
                ):
                    candidates.append(retry_dissolved)
            except Exception:
                pass
        try:
            buffered = geometry.buffer(0.0, 8)
            if self._has_polygon_area(buffered) and not self._introduces_long_new_boundary_segment(buffered, source_boundary):
                candidates.append(buffered)
        except Exception:
            pass
        try:
            repaired = geometry.makeValid() if not geometry.isGeosValid() else QgsGeometry(geometry)
            if self._has_polygon_area(repaired) and not self._introduces_long_new_boundary_segment(repaired, source_boundary):
                candidates.append(repaired)
        except Exception:
            pass

        return min(candidates, key=self._polygon_part_count) if candidates else None

    def _polygon_part_count(self, geometry: Optional[QgsGeometry]) -> int:
        parts = self._polygon_parts(geometry)
        return len(parts) if parts else 999999

    def _normalised_polygon_geometry(self, geometry: Optional[QgsGeometry]) -> Optional[QgsGeometry]:
        if not self._has_polygon_area(geometry):
            return geometry
        try:
            if not geometry.isGeosValid():
                geometry = geometry.makeValid()
        except Exception:
            pass
        try:
            buffered = geometry.buffer(0.0, CONTROLLING_REGION_GEOMETRY_REPAIR_SEGMENTS)
            if self._has_polygon_area(buffered):
                return buffered
        except Exception:
            pass
        return geometry

    def _introduces_long_new_boundary_segment(
        self,
        geometry: QgsGeometry,
        source_boundary: Optional[QgsGeometry],
    ) -> bool:
        """Reject geometry repairs that shortcut boundaries with new long chords."""
        if source_boundary is None or source_boundary.isEmpty():
            return False
        max_new_segment_length = CONTROLLING_REGION_MAX_NEW_SEGMENT_M
        distance_tolerance = CONTROLLING_REGION_BOUNDARY_DISTANCE_TOLERANCE_M
        for ring in self._polygon_boundary_parts(geometry):
            for start_point, end_point in zip(ring, ring[1:]):
                segment_length = start_point.distance(end_point)
                if segment_length <= max_new_segment_length:
                    continue
                if self._segment_has_sample_away_from_boundary(
                    start_point,
                    end_point,
                    source_boundary,
                    distance_tolerance,
                ):
                    return True
        return False

    def _combined_boundary_geometry(self, geometries: Sequence[QgsGeometry]) -> Optional[QgsGeometry]:
        boundaries: List[QgsGeometry] = []
        for geometry in geometries:
            boundary = self._normalised_boundary_geometry(geometry)
            if boundary is not None and not boundary.isEmpty():
                boundaries.append(boundary)
        if not boundaries:
            return None
        try:
            combined = QgsGeometry.unaryUnion(boundaries) if len(boundaries) > 1 else QgsGeometry(boundaries[0])
        except Exception:
            combined = QgsGeometry(boundaries[0])
        return combined if combined is not None and not combined.isEmpty() else None

    def _normalised_boundary_geometry(self, geometry: QgsGeometry) -> Optional[QgsGeometry]:
        try:
            boundary = geometry.boundary()
        except Exception:
            return None
        if boundary is None or boundary.isEmpty():
            return None
        return boundary

    def _segment_has_sample_away_from_boundary(
        self,
        start_point: QgsPointXY,
        end_point: QgsPointXY,
        boundary: QgsGeometry,
        distance_tolerance: float,
    ) -> bool:
        for fraction in (0.25, 0.5, 0.75):
            sample = QgsPointXY(
                start_point.x() + ((end_point.x() - start_point.x()) * fraction),
                start_point.y() + ((end_point.y() - start_point.y()) * fraction),
            )
            try:
                if QgsGeometry.fromPointXY(sample).distance(boundary) > distance_tolerance:
                    return True
            except Exception:
                continue
        return False

    def _unresolved_comparison_removes_candidate(
        self,
        candidate: ControllingOlsCandidate,
        competitor: ControllingOlsCandidate,
        overlap: Optional[QgsGeometry],
    ) -> bool:
        """Avoid retaining axis surfaces over conical regions when the exact solve is inconclusive."""
        if candidate.model == "axis" and competitor.model == "conical":
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

        for gap_part in self._polygon_parts(gaps):
            if gap_part.area() <= 1.0:
                continue
            repaired_parts = self._gap_lower_envelope_parts(gap_part)
            if not repaired_parts:
                continue
            for candidate, clean_part in repaired_parts:
                region_parts.append((candidate, clean_part))
                self._region_solve_stats["coverage_repair_part_count"] = (
                    self._region_solve_stats.get("coverage_repair_part_count", 0.0) + 1.0
                )
                self._region_solve_stats["coverage_repair_area_m2"] = (
                    self._region_solve_stats.get("coverage_repair_area_m2", 0.0) + clean_part.area()
                )

    def _gap_lower_envelope_parts(
        self,
        gap_geometry: QgsGeometry,
    ) -> List[Tuple[ControllingOlsCandidate, QgsGeometry]]:
        repaired_parts: List[Tuple[ControllingOlsCandidate, QgsGeometry]] = []
        for candidate in self.candidates:
            try:
                candidate_footprint = self._effective_footprint(candidate)
                if not self._bounding_boxes_intersect(gap_geometry, candidate_footprint):
                    continue
                candidate_region = gap_geometry.intersection(candidate_footprint)
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
                    competitor_footprint = self._effective_footprint(competitor)
                    if not self._bounding_boxes_intersect(candidate_region, competitor_footprint):
                        continue
                    overlap = candidate_region.intersection(competitor_footprint)
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
        if candidate.surface_type not in {"Approach", "IHS", "OHS", "TOCS", "Transitional"}:
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
        opened = self._open_boundary_touching_holes_geometry(geometry)
        if opened is not None and not opened.isEmpty():
            candidates.append(opened)
        despiked = self._despiked_polygon_geometry(opened if opened is not None else geometry)
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
                elif len(cleaned_ring) >= 4 and abs(self._ring_signed_area(cleaned_ring)) > 1.0:
                    cleaned_polygon.append(cleaned_ring)
                elif len(cleaned_ring) >= 4:
                    changed = True
            if cleaned_polygon:
                cleaned_parts.append(cleaned_polygon)
        if not cleaned_parts:
            return None
        if not changed:
            return QgsGeometry(geometry)
        if len(cleaned_parts) == 1:
            return QgsGeometry.fromPolygonXY(cleaned_parts[0])
        return QgsGeometry.fromMultiPolygonXY(cleaned_parts)

    def _open_boundary_touching_holes_geometry(self, geometry: QgsGeometry) -> Optional[QgsGeometry]:
        """Convert holes touching an exterior edge into open notches."""
        changed = False
        rebuilt_polygons = []
        try:
            polygons = geometry.asMultiPolygon() if geometry.isMultipart() else [geometry.asPolygon()]
        except Exception:
            return None
        for polygon in polygons:
            if not polygon or not polygon[0]:
                continue
            exterior = list(polygon[0])
            remaining_holes = []
            for hole in polygon[1:]:
                opened_exterior = self._open_boundary_touching_hole(exterior, list(hole))
                if opened_exterior is None:
                    remaining_holes.append(list(hole))
                    continue
                exterior = opened_exterior
                changed = True
            rebuilt_polygons.append([exterior] + remaining_holes)
        if not changed or not rebuilt_polygons:
            return None
        if len(rebuilt_polygons) == 1:
            return QgsGeometry.fromPolygonXY(rebuilt_polygons[0])
        return QgsGeometry.fromMultiPolygonXY(rebuilt_polygons)

    def _open_boundary_touching_hole(
        self,
        exterior_ring: Sequence[QgsPointXY],
        hole_ring: Sequence[QgsPointXY],
    ) -> Optional[List[QgsPointXY]]:
        exterior_points = list(exterior_ring[:-1]) if exterior_ring and exterior_ring[0].distance(exterior_ring[-1]) <= 1e-9 else list(exterior_ring)
        hole_points = list(hole_ring[:-1]) if hole_ring and hole_ring[0].distance(hole_ring[-1]) <= 1e-9 else list(hole_ring)
        if len(exterior_points) < 3 or len(hole_points) < 3:
            return None

        for exterior_index, start_point in enumerate(exterior_points):
            end_point = exterior_points[(exterior_index + 1) % len(exterior_points)]
            segment_length = start_point.distance(end_point)
            if segment_length <= CONTROLLING_REGION_RING_TOUCH_TOLERANCE_M:
                continue
            for hole_index, hole_start in enumerate(hole_points):
                hole_end = hole_points[(hole_index + 1) % len(hole_points)]
                start_projection = self._point_projection_fraction(start_point, end_point, hole_start)
                end_projection = self._point_projection_fraction(start_point, end_point, hole_end)
                if start_projection is None or end_projection is None:
                    continue
                if not self._point_lies_on_segment(start_point, end_point, hole_start, start_projection):
                    continue
                if not self._point_lies_on_segment(start_point, end_point, hole_end, end_projection):
                    continue
                if abs(start_projection - end_projection) * segment_length <= CONTROLLING_REGION_RING_TOUCH_TOLERANCE_M:
                    continue
                if start_projection <= end_projection:
                    notch_start = hole_start
                    notch_end = hole_end
                    notch_path = self._indirect_ring_path(hole_points, hole_index, (hole_index + 1) % len(hole_points))
                else:
                    notch_start = hole_end
                    notch_end = hole_start
                    notch_path = self._indirect_ring_path(hole_points, (hole_index + 1) % len(hole_points), hole_index)
                opened = self._replace_exterior_segment_with_notch(
                    exterior_points,
                    exterior_index,
                    notch_start,
                    notch_path,
                    notch_end,
                )
                if opened is not None and len(opened) >= 4:
                    return opened
        return None

    def _replace_exterior_segment_with_notch(
        self,
        exterior_points: Sequence[QgsPointXY],
        exterior_index: int,
        notch_start: QgsPointXY,
        notch_path: Sequence[QgsPointXY],
        notch_end: QgsPointXY,
    ) -> Optional[List[QgsPointXY]]:
        if not notch_path:
            return None
        rebuilt: List[QgsPointXY] = []
        point_count = len(exterior_points)
        for index in range(point_count):
            point = exterior_points[index]
            if not rebuilt or rebuilt[-1].distance(point) > 1e-9:
                rebuilt.append(point)
            if index != exterior_index:
                continue
            if rebuilt[-1].distance(notch_start) > 1e-9:
                rebuilt.append(QgsPointXY(notch_start))
            for notch_point in notch_path[1:]:
                if rebuilt[-1].distance(notch_point) > 1e-9:
                    rebuilt.append(QgsPointXY(notch_point))
            if rebuilt[-1].distance(notch_end) > 1e-9:
                rebuilt.append(QgsPointXY(notch_end))
            next_exterior = exterior_points[(index + 1) % point_count]
            if rebuilt[-1].distance(next_exterior) > 1e-9:
                rebuilt.append(QgsPointXY(next_exterior))
        if rebuilt and rebuilt[0].distance(rebuilt[-1]) > 1e-9:
            rebuilt.append(rebuilt[0])
        return rebuilt

    def _indirect_ring_path(
        self,
        ring_points: Sequence[QgsPointXY],
        start_index: int,
        end_index: int,
    ) -> List[QgsPointXY]:
        forward = self._ring_path(ring_points, start_index, end_index)
        backward = self._ring_path(ring_points, end_index, start_index)
        backward = list(reversed(backward))
        return max((forward, backward), key=self._path_length)

    def _ring_path(
        self,
        ring_points: Sequence[QgsPointXY],
        start_index: int,
        end_index: int,
    ) -> List[QgsPointXY]:
        if not ring_points:
            return []
        path = [QgsPointXY(ring_points[start_index])]
        index = start_index
        while index != end_index:
            index = (index + 1) % len(ring_points)
            path.append(QgsPointXY(ring_points[index]))
            if len(path) > len(ring_points) + 1:
                return []
        return path

    def _path_length(self, points: Sequence[QgsPointXY]) -> float:
        return sum(start.distance(end) for start, end in zip(points, points[1:]))

    def _point_projection_fraction(
        self,
        segment_start: QgsPointXY,
        segment_end: QgsPointXY,
        point: QgsPointXY,
    ) -> Optional[float]:
        dx = segment_end.x() - segment_start.x()
        dy = segment_end.y() - segment_start.y()
        length_squared = (dx * dx) + (dy * dy)
        if length_squared <= 1e-12:
            return None
        return (((point.x() - segment_start.x()) * dx) + ((point.y() - segment_start.y()) * dy)) / length_squared

    def _point_lies_on_segment(
        self,
        segment_start: QgsPointXY,
        segment_end: QgsPointXY,
        point: QgsPointXY,
        projection_fraction: float,
    ) -> bool:
        tolerance = CONTROLLING_REGION_RING_TOUCH_TOLERANCE_M
        if projection_fraction < -1e-6 or projection_fraction > 1.0 + 1e-6:
            return False
        projected = QgsPointXY(
            segment_start.x() + ((segment_end.x() - segment_start.x()) * projection_fraction),
            segment_start.y() + ((segment_end.y() - segment_start.y()) * projection_fraction),
        )
        return projected.distance(point) <= tolerance

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

    def _ring_signed_area(self, ring: Sequence[QgsPointXY]) -> float:
        if len(ring) < 3:
            return 0.0
        points = ring[:-1] if ring[0].distance(ring[-1]) <= 1e-9 else list(ring)
        area = 0.0
        for start_point, end_point in zip(points, points[1:] + points[:1]):
            area += (start_point.x() * end_point.y()) - (end_point.x() * start_point.y())
        return area / 2.0

    def _candidate_lower_region(
        self,
        candidate: ControllingOlsCandidate,
        competitor: ControllingOlsCandidate,
        overlap: Optional[QgsGeometry] = None,
    ) -> Optional[QgsGeometry]:
        """Return the geometry where candidate elevation is <= competitor elevation."""
        start_time = time.perf_counter()
        self._region_solve_stats["lower_region_calls"] = self._region_solve_stats.get("lower_region_calls", 0.0) + 1.0
        if candidate.model == "conical" or competitor.model == "conical":
            try:
                return self._curved_candidate_lower_region(candidate, competitor, overlap)
            finally:
                self._region_solve_stats["curved_lower_time_s"] = (
                    self._region_solve_stats.get("curved_lower_time_s", 0.0)
                    + (time.perf_counter() - start_time)
                )
        try:
            return self._candidate_lower_halfplane(candidate, competitor, overlap)
        finally:
            self._region_solve_stats["linear_lower_time_s"] = (
                self._region_solve_stats.get("linear_lower_time_s", 0.0)
                + (time.perf_counter() - start_time)
            )

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
            self._region_solve_stats["curved_conical_conical_calls"] = (
                self._region_solve_stats.get("curved_conical_conical_calls", 0.0) + 1.0
            )
            start_time = time.perf_counter()
            try:
                return self._sampled_candidate_lower_region(candidate, competitor, overlap)
            finally:
                self._region_solve_stats["sampled_lower_region_time_s"] = (
                    self._region_solve_stats.get("sampled_lower_region_time_s", 0.0)
                    + (time.perf_counter() - start_time)
                )
        if candidate.model == "conical":
            return self._conical_linear_lower_region(candidate, competitor, overlap, conical_is_candidate=True)
        if competitor.model == "conical":
            return self._conical_linear_lower_region(competitor, candidate, overlap, conical_is_candidate=False)
        self._region_solve_stats["curved_other_calls"] = (
            self._region_solve_stats.get("curved_other_calls", 0.0) + 1.0
        )
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
            self._region_solve_stats["curved_conical_constant_calls"] = (
                self._region_solve_stats.get("curved_conical_constant_calls", 0.0) + 1.0
            )
            start_time = time.perf_counter()
            try:
                return self._conical_constant_lower_region(
                    conical_model,
                    float(linear_plane[2]),
                    overlap,
                    conical_is_candidate,
                )
            finally:
                self._region_solve_stats["conical_constant_time_s"] = (
                    self._region_solve_stats.get("conical_constant_time_s", 0.0)
                    + (time.perf_counter() - start_time)
                )

        if linear_candidate.model == "axis":
            self._region_solve_stats["curved_axis_conical_calls"] = (
                self._region_solve_stats.get("curved_axis_conical_calls", 0.0) + 1.0
            )
            start_time = time.perf_counter()
            try:
                return self._axis_conical_lower_region(
                    conical_candidate,
                    linear_candidate,
                    overlap,
                    conical_is_candidate,
                )
            finally:
                self._region_solve_stats["axis_conical_time_s"] = (
                    self._region_solve_stats.get("axis_conical_time_s", 0.0)
                    + (time.perf_counter() - start_time)
                )

        self._region_solve_stats["curved_conical_plane_calls"] = (
            self._region_solve_stats.get("curved_conical_plane_calls", 0.0) + 1.0
        )
        start_time = time.perf_counter()
        try:
            return self._triangulated_candidate_lower_region(
                conical_candidate if conical_is_candidate else linear_candidate,
                linear_candidate if conical_is_candidate else conical_candidate,
                overlap,
            )
        finally:
            self._region_solve_stats["conical_plane_triangulated_time_s"] = (
                self._region_solve_stats.get("conical_plane_triangulated_time_s", 0.0)
                + (time.perf_counter() - start_time)
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
        return conical_lower if self._has_polygon_area(conical_lower) else QgsGeometry()

    def _axis_lower_than_conical_region(
        self,
        axis_candidate: ControllingOlsCandidate,
        conical_candidate: ControllingOlsCandidate,
        axis: dict,
        overlap: QgsGeometry,
    ) -> Optional[QgsGeometry]:
        if AXIS_CONICAL_EXACT_SOLVER_ENABLED:
            exact_region = self._axis_conical_exact_axis_lower_region(axis_candidate, conical_candidate, axis, overlap)
            if exact_region is not None:
                return exact_region
            if not AXIS_CONICAL_TRIANGULATION_FALLBACK_ENABLED:
                self._region_solve_stats["axis_exact_unresolved"] = (
                    self._region_solve_stats.get("axis_exact_unresolved", 0.0) + 1.0
                )
                return None

        station_range = self._axis_station_range(axis, overlap)
        if station_range is None:
            return None
        min_station, max_station = station_range
        if max_station - min_station <= 1e-6:
            return None

        stations = self._axis_conical_sample_stations(axis, overlap, min_station, max_station)
        if len(stations) < 2:
            return None

        pieces: List[QgsGeometry] = []
        for start_station, end_station in zip(stations[:-1], stations[1:]):
            if end_station - start_station <= 1e-6:
                continue
            band_start = time.perf_counter()
            station_band = self._axis_station_interval_geometry(axis, start_station, end_station, overlap)
            self._region_solve_stats["axis_station_band_time_s"] = (
                self._region_solve_stats.get("axis_station_band_time_s", 0.0)
                + (time.perf_counter() - band_start)
            )
            if station_band is None or not self._has_polygon_area(station_band):
                continue
            decision_start = time.perf_counter()
            decision = self._sampled_lower_decision(
                axis_candidate,
                conical_candidate,
                station_band,
            )
            self._region_solve_stats["axis_sample_decision_time_s"] = (
                self._region_solve_stats.get("axis_sample_decision_time_s", 0.0)
                + (time.perf_counter() - decision_start)
            )
            if decision == "all_lower":
                self._region_solve_stats["axis_all_lower_bands"] = (
                    self._region_solve_stats.get("axis_all_lower_bands", 0.0) + 1.0
                )
                pieces.append(station_band)
                continue
            if decision == "all_higher":
                self._region_solve_stats["axis_all_higher_bands"] = (
                    self._region_solve_stats.get("axis_all_higher_bands", 0.0) + 1.0
                )
                continue
            self._region_solve_stats["axis_mixed_bands"] = (
                self._region_solve_stats.get("axis_mixed_bands", 0.0) + 1.0
            )
            self._region_solve_stats["axis_triangulated_bands"] = (
                self._region_solve_stats.get("axis_triangulated_bands", 0.0) + 1.0
            )
            triangulation_start = time.perf_counter()
            lower_band = self._triangulated_candidate_lower_region(axis_candidate, conical_candidate, station_band)
            self._region_solve_stats["axis_band_triangulation_time_s"] = (
                self._region_solve_stats.get("axis_band_triangulation_time_s", 0.0)
                + (time.perf_counter() - triangulation_start)
            )
            if lower_band is not None and self._has_polygon_area(lower_band):
                pieces.append(lower_band)
        if not pieces:
            decision_start = time.perf_counter()
            fallback_decision = self._sampled_lower_decision(
                axis_candidate,
                conical_candidate,
                overlap,
                all_higher_margin_m=2.0,
            )
            self._region_solve_stats["axis_sample_decision_time_s"] = (
                self._region_solve_stats.get("axis_sample_decision_time_s", 0.0)
                + (time.perf_counter() - decision_start)
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
        return combined if self._has_polygon_area(combined) else QgsGeometry()

    def _axis_conical_exact_axis_lower_region(
        self,
        axis_candidate: ControllingOlsCandidate,
        conical_candidate: ControllingOlsCandidate,
        axis: dict,
        overlap: QgsGeometry,
    ) -> Optional[QgsGeometry]:
        """Try to solve axis-vs-conical by splitting on the equal-height curve."""
        self._region_solve_stats["axis_exact_calls"] = (
            self._region_solve_stats.get("axis_exact_calls", 0.0) + 1.0
        )
        total_start = time.perf_counter()
        try:
            conical_model = self._conical_model(conical_candidate)
            if conical_model is None or float(conical_model.get("slope", 0.0)) <= 0.0:
                return self._record_axis_exact_fallback(total_start, "bad_model")

            curve_start = time.perf_counter()
            transition_curves = self._axis_conical_transition_curves_for_solver(
                axis_candidate,
                conical_candidate,
                axis,
                conical_model,
                overlap,
            )
            self._region_solve_stats["axis_exact_curve_time_s"] = (
                self._region_solve_stats.get("axis_exact_curve_time_s", 0.0)
                + (time.perf_counter() - curve_start)
            )

            if not transition_curves:
                self._region_solve_stats["axis_exact_no_curve"] = (
                    self._region_solve_stats.get("axis_exact_no_curve", 0.0) + 1.0
                )
                decision_start = time.perf_counter()
                decision = self._sampled_lower_decision(axis_candidate, conical_candidate, overlap, dense=True)
                self._region_solve_stats["axis_exact_classify_time_s"] = (
                    self._region_solve_stats.get("axis_exact_classify_time_s", 0.0)
                    + (time.perf_counter() - decision_start)
                )
                if decision == "all_lower":
                    self._record_axis_exact_success(total_start)
                    return QgsGeometry(overlap)
                if decision == "all_higher":
                    self._record_axis_exact_success(total_start)
                    return QgsGeometry()
                return self._record_axis_exact_fallback(total_start, "no_curve_mixed")

            for transition_curve in transition_curves:
                combined = self._axis_conical_region_from_transition_curve(
                    axis_candidate,
                    conical_candidate,
                    overlap,
                    transition_curve,
                )
                if combined is not None:
                    self._record_axis_exact_success(total_start)
                    return combined if self._has_polygon_area(combined) else QgsGeometry()
            return self._record_axis_exact_fallback(total_start, "split_invalid")
        except Exception:
            return self._record_axis_exact_fallback(total_start, "exception")

    def _axis_conical_region_from_transition_curve(
        self,
        axis_candidate: ControllingOlsCandidate,
        conical_candidate: ControllingOlsCandidate,
        overlap: QgsGeometry,
        transition_curve: QgsGeometry,
    ) -> Optional[QgsGeometry]:
        split_start = time.perf_counter()
        split_parts = self._split_overlap_by_transition_curve(overlap, transition_curve)
        self._region_solve_stats["axis_exact_split_time_s"] = (
            self._region_solve_stats.get("axis_exact_split_time_s", 0.0)
            + (time.perf_counter() - split_start)
        )
        if len(split_parts) <= 1 or not self._split_parts_are_valid(overlap, split_parts):
            return None

        classify_start = time.perf_counter()
        kept_parts: List[QgsGeometry] = []
        for part in split_parts:
            if not self._has_polygon_area(part):
                continue
            try:
                point = part.pointOnSurface().asPoint()
                point_xy = QgsPointXY(point.x(), point.y())
            except Exception:
                continue
            difference = self._candidate_difference(axis_candidate, conical_candidate, point_xy)
            if difference is not None and difference <= self.tie_tolerance_m:
                kept_parts.append(part)
        self._region_solve_stats["axis_exact_classify_time_s"] = (
            self._region_solve_stats.get("axis_exact_classify_time_s", 0.0)
            + (time.perf_counter() - classify_start)
        )
        if not kept_parts:
            return QgsGeometry()
        try:
            combined = QgsGeometry.unaryUnion(kept_parts) if len(kept_parts) > 1 else QgsGeometry(kept_parts[0])
        except Exception:
            return None
        if combined is None:
            return None
        return combined if self._has_polygon_area(combined) else QgsGeometry()

    def _axis_conical_transition_curves_for_solver(
        self,
        axis_candidate: ControllingOlsCandidate,
        conical_candidate: ControllingOlsCandidate,
        axis: dict,
        conical_model: dict,
        overlap: QgsGeometry,
    ) -> List[QgsGeometry]:
        """Return preferred conical/axis transition curves for splitting controlling regions."""
        curves: List[QgsGeometry] = []
        sampled_curve = self._axis_conical_sampled_transition_curve(
            axis_candidate,
            conical_candidate,
            axis,
            conical_model,
            overlap,
        )
        if sampled_curve is not None and not sampled_curve.isEmpty():
            curves.append(sampled_curve)
        analytic_curve = self._axis_conical_transition_curve(axis, conical_model, overlap)
        if analytic_curve is not None and not analytic_curve.isEmpty():
            curves.append(analytic_curve)
        return curves

    def _axis_conical_sampled_transition_curve(
        self,
        axis_candidate: ControllingOlsCandidate,
        conical_candidate: ControllingOlsCandidate,
        axis: dict,
        conical_model: dict,
        overlap: QgsGeometry,
    ) -> Optional[QgsGeometry]:
        """Build a zero-contour of axis elevation minus conical elevation over the overlap."""
        if not AXIS_CONICAL_ZERO_CONTOUR_ENABLED:
            return None
        if not self._axis_conical_zero_contour_applies(axis_candidate):
            return None
        if overlap is None or overlap.isEmpty() or axis is None or conical_model is None:
            return None

        self._region_solve_stats["axis_zero_contour_calls"] = (
            self._region_solve_stats.get("axis_zero_contour_calls", 0.0) + 1.0
        )
        start_time = time.perf_counter()
        try:
            spacing = self._axis_conical_zero_contour_spacing(overlap)
            bbox = overlap.boundingBox()
            if spacing <= 0.0 or bbox.width() <= 0.0 or bbox.height() <= 0.0:
                self._region_solve_stats["axis_zero_contour_no_curve"] = (
                    self._region_solve_stats.get("axis_zero_contour_no_curve", 0.0) + 1.0
                )
                return None

            columns = max(1, int(math.ceil(bbox.width() / spacing)))
            rows = max(1, int(math.ceil(bbox.height() / spacing)))
            cell_count = columns * rows
            if cell_count > AXIS_CONICAL_ZERO_CONTOUR_MAX_CELLS:
                scale = math.sqrt(cell_count / AXIS_CONICAL_ZERO_CONTOUR_MAX_CELLS)
                spacing *= scale
                columns = max(1, int(math.ceil(bbox.width() / spacing)))
                rows = max(1, int(math.ceil(bbox.height() / spacing)))
                cell_count = columns * rows
            self._region_solve_stats["axis_zero_contour_cells"] = (
                self._region_solve_stats.get("axis_zero_contour_cells", 0.0) + float(cell_count)
            )

            value_cache: Dict[Tuple[int, int], Optional[float]] = {}

            def _point_at(column: int, row: int) -> QgsPointXY:
                return QgsPointXY(
                    min(bbox.xMaximum(), bbox.xMinimum() + (column * spacing)),
                    min(bbox.yMaximum(), bbox.yMinimum() + (row * spacing)),
                )

            def _value_at(column: int, row: int) -> Optional[float]:
                key = (column, row)
                if key not in value_cache:
                    point_xy = _point_at(column, row)
                    difference = self._candidate_difference(axis_candidate, conical_candidate, point_xy)
                    value_cache[key] = difference if difference is not None and math.isfinite(difference) else None
                return value_cache[key]

            segments: List[QgsGeometry] = []
            for column in range(columns):
                for row in range(rows):
                    corners = [
                        (column, row),
                        (column + 1, row),
                        (column + 1, row + 1),
                        (column, row + 1),
                    ]
                    points = [_point_at(corner_column, corner_row) for corner_column, corner_row in corners]
                    values = [_value_at(corner_column, corner_row) for corner_column, corner_row in corners]
                    zero_points = self._zero_crossings_for_grid_cell(points, values)
                    if len(zero_points) < 2:
                        continue
                    for start_index in range(0, len(zero_points) - 1, 2):
                        segment = QgsGeometry.fromPolylineXY([zero_points[start_index], zero_points[start_index + 1]])
                        if segment is None or segment.isEmpty():
                            continue
                        try:
                            clipped_segment = segment.intersection(overlap)
                        except Exception:
                            clipped_segment = segment
                        for line_points in self._line_parts(clipped_segment):
                            if len(line_points) < 2:
                                continue
                            line = QgsGeometry.fromPolylineXY(line_points)
                            if line is not None and not line.isEmpty():
                                segments.append(line)

            if not segments:
                self._region_solve_stats["axis_zero_contour_no_curve"] = (
                    self._region_solve_stats.get("axis_zero_contour_no_curve", 0.0) + 1.0
                )
                return None

            self._region_solve_stats["axis_zero_contour_segments"] = (
                self._region_solve_stats.get("axis_zero_contour_segments", 0.0) + float(len(segments))
            )
            self._region_solve_stats["axis_zero_contour_success"] = (
                self._region_solve_stats.get("axis_zero_contour_success", 0.0) + 1.0
            )
            try:
                sampled_curve = (
                    QgsGeometry.unaryUnion(segments)
                    if len(segments) > 1
                    else segments[0]
                )
            except Exception:
                sampled_curve = segments[0]
            if AXIS_CONICAL_CURVE_SMOOTHING_ENABLED:
                smoothed_curve = self._smoothed_axis_conical_zero_contour(
                    sampled_curve,
                    axis_candidate,
                    conical_candidate,
                    axis,
                    conical_model,
                    overlap,
                )
                if smoothed_curve is not None and not smoothed_curve.isEmpty():
                    return smoothed_curve
            return sampled_curve
        finally:
            self._region_solve_stats["axis_zero_contour_time_s"] = (
                self._region_solve_stats.get("axis_zero_contour_time_s", 0.0)
                + (time.perf_counter() - start_time)
            )

    def _smoothed_axis_conical_zero_contour(
        self,
        sampled_curve: QgsGeometry,
        axis_candidate: ControllingOlsCandidate,
        conical_candidate: ControllingOlsCandidate,
        axis: dict,
        conical_model: dict,
        overlap: QgsGeometry,
    ) -> Optional[QgsGeometry]:
        """Create an endpoint-clamped C2 guide and project it back to equality."""
        self._region_solve_stats["axis_curve_smoothing_calls"] = (
            self._region_solve_stats.get("axis_curve_smoothing_calls", 0.0) + 1.0
        )
        source_parts = self._topology_clean_transition_line_parts(sampled_curve)
        if not source_parts:
            self._record_axis_curve_smoothing_rejection("topology")
            return None

        smoothed_parts: List[QgsGeometry] = []
        maximum_deviation_m = 0.0
        maximum_residual_m = 0.0
        maximum_endpoint_shift_m = 0.0
        for source_points in source_parts:
            if len(source_points) < 2:
                self._record_axis_curve_smoothing_rejection("short")
                return None
            source_line = QgsGeometry.fromPolylineXY(source_points)
            source_residual_m = self._maximum_axis_conical_curve_residual(
                source_line,
                axis_candidate,
                conical_candidate,
            )
            source_curvature_change, source_rms_curvature_change = (
                self._curve_curvature_continuity_metrics(source_line)
            )
            if source_residual_m is None:
                self._record_axis_curve_smoothing_rejection("residual")
                return None
            control_points = self._uniform_curve_control_points(
                source_line,
                AXIS_CONICAL_CURVE_SMOOTHING_CONTROL_SPACING_M,
            )
            if len(control_points) < 4:
                self._record_axis_curve_smoothing_rejection("short")
                return None
            guide_points = self._clamped_cubic_bspline_points(
                control_points,
                AXIS_CONICAL_CURVE_SMOOTHING_SAMPLES_PER_SPAN,
            )
            if len(guide_points) < 2:
                self._record_axis_curve_smoothing_rejection("short")
                return None

            projected_points: List[QgsPointXY] = []
            for index, guide_point in enumerate(guide_points):
                projected_point = (
                    QgsPointXY(source_points[0])
                    if index == 0
                    else QgsPointXY(source_points[-1])
                    if index == len(guide_points) - 1
                    else self._project_axis_conical_point_to_equality(
                        axis,
                        conical_model,
                        guide_point,
                    )
                )
                if not projected_points or projected_point.distance(projected_points[-1]) > 1e-6:
                    projected_points.append(projected_point)
            projected_points = self._remove_transition_curve_backtracking(projected_points)
            if len(projected_points) < 2:
                self._record_axis_curve_smoothing_rejection("backtracking")
                return None

            endpoint_shift_m = max(
                projected_points[0].distance(source_points[0]),
                projected_points[-1].distance(source_points[-1]),
            )
            if endpoint_shift_m > AXIS_CONICAL_CURVE_SMOOTHING_MAX_ENDPOINT_SHIFT_M:
                self._record_axis_curve_smoothing_rejection("endpoint")
                return None
            maximum_endpoint_shift_m = max(maximum_endpoint_shift_m, endpoint_shift_m)
            smoothed_line = QgsGeometry.fromPolylineXY(projected_points)
            if smoothed_line is None or smoothed_line.isEmpty() or not smoothed_line.isSimple():
                self._record_axis_curve_smoothing_rejection("simple")
                return None
            try:
                part_maximum_deviation_m = source_line.hausdorffDistanceDensify(
                    smoothed_line,
                    AXIS_CONICAL_CURVE_SMOOTHING_HAUSDORFF_DENSIFY_FRACTION,
                )
            except Exception:
                part_maximum_deviation_m = float("nan")
            if (
                not math.isfinite(part_maximum_deviation_m)
                or part_maximum_deviation_m < 0.0
                or part_maximum_deviation_m
                > AXIS_CONICAL_CURVE_SMOOTHING_MAX_DEVIATION_M
            ):
                self._record_axis_curve_smoothing_rejection("deviation")
                return None
            try:
                domain = overlap.buffer(
                    AXIS_CONICAL_CURVE_SMOOTHING_DOMAIN_TOLERANCE_M,
                    CONTROLLING_CONTOUR_CLIP_BUFFER_SEGMENTS,
                )
                outside = smoothed_line.difference(domain)
            except Exception:
                outside = None
            if outside is None or (not outside.isEmpty() and outside.length() > 1e-6):
                self._record_axis_curve_smoothing_rejection("domain")
                return None

            part_maximum_residual_m = self._maximum_axis_conical_curve_residual(
                smoothed_line,
                axis_candidate,
                conical_candidate,
            )
            if part_maximum_residual_m is None:
                self._record_axis_curve_smoothing_rejection("residual")
                return None
            if (
                part_maximum_residual_m
                > AXIS_CONICAL_CURVE_SMOOTHING_MAX_EQUALITY_RESIDUAL_M
            ):
                self._record_axis_curve_smoothing_rejection("residual")
                return None
            if (
                part_maximum_residual_m
                > source_residual_m
                + AXIS_CONICAL_CURVE_SMOOTHING_MAX_RESIDUAL_INCREASE_M
            ):
                self._record_axis_curve_smoothing_rejection("residual_regression")
                return None

            smoothed_curvature_change, smoothed_rms_curvature_change = (
                self._curve_curvature_continuity_metrics(smoothed_line)
            )
            required_curvature_change = source_curvature_change * (
                1.0 - AXIS_CONICAL_CURVE_SMOOTHING_MIN_CURVATURE_IMPROVEMENT
            )
            required_rms_curvature_change = source_rms_curvature_change * (
                1.0 - AXIS_CONICAL_CURVE_SMOOTHING_MIN_CURVATURE_IMPROVEMENT
            )
            if (
                source_curvature_change <= 1e-12
                or smoothed_curvature_change > required_curvature_change
                or smoothed_rms_curvature_change
                > required_rms_curvature_change
            ):
                self._record_axis_curve_smoothing_rejection("continuity")
                return None

            maximum_deviation_m = max(
                maximum_deviation_m,
                part_maximum_deviation_m,
            )
            maximum_residual_m = max(maximum_residual_m, part_maximum_residual_m)
            smoothed_parts.append(smoothed_line)

        if not smoothed_parts:
            self._record_axis_curve_smoothing_rejection("short")
            return None
        try:
            smoothed_curve = (
                QgsGeometry.unaryUnion(smoothed_parts)
                if len(smoothed_parts) > 1
                else smoothed_parts[0]
            )
        except Exception:
            self._record_axis_curve_smoothing_rejection("union")
            return None
        self._region_solve_stats["axis_curve_smoothing_accepted"] = (
            self._region_solve_stats.get("axis_curve_smoothing_accepted", 0.0) + 1.0
        )
        self._region_solve_stats["axis_curve_smoothing_max_deviation_m"] = max(
            self._region_solve_stats.get("axis_curve_smoothing_max_deviation_m", 0.0),
            maximum_deviation_m,
        )
        self._region_solve_stats["axis_curve_smoothing_max_equality_residual_m"] = max(
            self._region_solve_stats.get(
                "axis_curve_smoothing_max_equality_residual_m",
                0.0,
            ),
            maximum_residual_m,
        )
        self._region_solve_stats["axis_curve_smoothing_max_endpoint_shift_m"] = max(
            self._region_solve_stats.get("axis_curve_smoothing_max_endpoint_shift_m", 0.0),
            maximum_endpoint_shift_m,
        )
        return smoothed_curve

    def _record_axis_curve_smoothing_rejection(self, reason: str) -> None:
        self._region_solve_stats["axis_curve_smoothing_rejected"] = (
            self._region_solve_stats.get("axis_curve_smoothing_rejected", 0.0) + 1.0
        )
        key = f"axis_curve_smoothing_rejected_{reason}"
        self._region_solve_stats[key] = self._region_solve_stats.get(key, 0.0) + 1.0

    def _maximum_axis_conical_curve_residual(
        self,
        line: QgsGeometry,
        axis_candidate: ControllingOlsCandidate,
        conical_candidate: ControllingOlsCandidate,
    ) -> Optional[float]:
        try:
            sampled_geometry = line.densifyByDistance(
                AXIS_CONICAL_CURVE_SMOOTHING_CONTROL_SPACING_M / 4.0
            )
        except Exception:
            sampled_geometry = line
        residuals = []
        for points in self._line_parts(sampled_geometry):
            for point_xy in points:
                difference = self._candidate_difference(
                    axis_candidate,
                    conical_candidate,
                    point_xy,
                )
                if difference is None or not math.isfinite(difference):
                    return None
                residuals.append(abs(difference))
        return max(residuals) if residuals else None

    @staticmethod
    def _curve_curvature_continuity_metrics(
        line: QgsGeometry,
        sample_spacing_m: float = 5.0,
    ) -> Tuple[float, float]:
        length = line.length() if line is not None and not line.isEmpty() else 0.0
        if length <= sample_spacing_m * 2.0:
            return 0.0, 0.0
        sample_count = max(2, int(math.ceil(length / sample_spacing_m)))
        sampled_points = []
        for index in range(sample_count + 1):
            point_geometry = line.interpolate(length * index / sample_count)
            if point_geometry is None or point_geometry.isEmpty():
                continue
            point = point_geometry.asPoint()
            sampled_points.append(QgsPointXY(point.x(), point.y()))
        curvatures = []
        for previous, current, following in zip(
            sampled_points[:-2],
            sampled_points[1:-1],
            sampled_points[2:],
        ):
            first_heading = math.atan2(
                current.y() - previous.y(),
                current.x() - previous.x(),
            )
            second_heading = math.atan2(
                following.y() - current.y(),
                following.x() - current.x(),
            )
            heading_change = math.atan2(
                math.sin(second_heading - first_heading),
                math.cos(second_heading - first_heading),
            )
            local_spacing_m = (
                previous.distance(current) + current.distance(following)
            ) / 2.0
            if local_spacing_m > 1e-9:
                curvatures.append(heading_change / local_spacing_m)
        changes = [
            (second - first) / sample_spacing_m
            for first, second in zip(curvatures[:-1], curvatures[1:])
        ]
        if not changes:
            return 0.0, 0.0
        return (
            max(abs(value) for value in changes),
            math.sqrt(sum(value * value for value in changes) / len(changes)),
        )

    def _uniform_curve_control_points(
        self,
        line: QgsGeometry,
        spacing_m: float,
    ) -> List[QgsPointXY]:
        if line is None or line.isEmpty() or spacing_m <= 0.0:
            return []
        length = line.length()
        if length <= 1e-9:
            return []
        segment_count = max(1, int(math.ceil(length / spacing_m)))
        controls: List[QgsPointXY] = []
        for index in range(segment_count + 1):
            point_geometry = line.interpolate(length * index / segment_count)
            if point_geometry is None or point_geometry.isEmpty():
                return []
            point = point_geometry.asPoint()
            point_xy = QgsPointXY(point.x(), point.y())
            if not controls or point_xy.distance(controls[-1]) > 1e-6:
                controls.append(point_xy)
        return controls

    @staticmethod
    def _clamped_cubic_bspline_points(
        control_points: Sequence[QgsPointXY],
        samples_per_span: int,
    ) -> List[QgsPointXY]:
        """Evaluate an open uniform cubic B-spline with clamped endpoints."""
        controls = [QgsPointXY(point) for point in control_points]
        if len(controls) < 4:
            return controls
        sample_count = max(1, int(samples_per_span))
        padded = [QgsPointXY(controls[0]), QgsPointXY(controls[0])]
        padded.extend(controls)
        padded.extend([QgsPointXY(controls[-1]), QgsPointXY(controls[-1])])
        output: List[QgsPointXY] = []
        for span in range(len(padded) - 3):
            p0, p1, p2, p3 = padded[span : span + 4]
            for sample in range(sample_count):
                t = sample / sample_count
                one_minus_t = 1.0 - t
                weights = (
                    one_minus_t ** 3 / 6.0,
                    ((3.0 * t ** 3) - (6.0 * t * t) + 4.0) / 6.0,
                    ((-3.0 * t ** 3) + (3.0 * t * t) + (3.0 * t) + 1.0)
                    / 6.0,
                    t ** 3 / 6.0,
                )
                point = QgsPointXY(
                    sum(weight * source.x() for weight, source in zip(weights, (p0, p1, p2, p3))),
                    sum(weight * source.y() for weight, source in zip(weights, (p0, p1, p2, p3))),
                )
                if not output or point.distance(output[-1]) > 1e-6:
                    output.append(point)
        if not output or output[-1].distance(controls[-1]) > 1e-6:
            output.append(QgsPointXY(controls[-1]))
        output[0] = QgsPointXY(controls[0])
        output[-1] = QgsPointXY(controls[-1])
        return output

    def _axis_conical_zero_contour_applies(self, axis_candidate: ControllingOlsCandidate) -> bool:
        """Apply the GeoJSON surface-intersection style sampler to runway axis surfaces."""
        return axis_candidate.model == "axis" and axis_candidate.surface_type in {"Approach", "TOCS"}

    def _axis_conical_zero_contour_spacing(self, overlap: QgsGeometry) -> float:
        bbox = overlap.boundingBox()
        max_dimension = max(float(bbox.width()), float(bbox.height()), 1.0)
        adaptive_spacing = max_dimension / AXIS_CONICAL_ZERO_CONTOUR_TARGET_STEPS
        return max(
            AXIS_CONICAL_ZERO_CONTOUR_MIN_GRID_M,
            min(AXIS_CONICAL_ZERO_CONTOUR_MAX_GRID_M, adaptive_spacing),
        )

    def _zero_crossings_for_grid_cell(
        self,
        points: Sequence[QgsPointXY],
        values: Sequence[Optional[float]],
    ) -> List[QgsPointXY]:
        zero_points: List[QgsPointXY] = []

        def _add(point_xy: QgsPointXY) -> None:
            key = (round(point_xy.x(), 3), round(point_xy.y(), 3))
            for existing in zero_points:
                if (round(existing.x(), 3), round(existing.y(), 3)) == key:
                    return
            zero_points.append(point_xy)

        for start_index, end_index in ((0, 1), (1, 2), (2, 3), (3, 0)):
            start_value = values[start_index]
            end_value = values[end_index]
            if start_value is None or end_value is None:
                continue
            start_point = points[start_index]
            end_point = points[end_index]
            start_is_zero = abs(start_value) <= self.tie_tolerance_m
            end_is_zero = abs(end_value) <= self.tie_tolerance_m
            if start_is_zero:
                _add(start_point)
            if end_is_zero:
                _add(end_point)
            if start_is_zero or end_is_zero:
                continue
            if start_value * end_value < 0.0:
                _add(self._interpolated_zero_crossing(start_point, end_point, start_value, end_value))
        return zero_points

    def _record_axis_exact_success(self, start_time: float) -> None:
        self._region_solve_stats["axis_exact_success"] = (
            self._region_solve_stats.get("axis_exact_success", 0.0) + 1.0
        )
        self._region_solve_stats["axis_exact_total_time_s"] = (
            self._region_solve_stats.get("axis_exact_total_time_s", 0.0)
            + (time.perf_counter() - start_time)
        )

    def _record_axis_exact_fallback(self, start_time: float, reason: str) -> None:
        self._region_solve_stats["axis_exact_fallback"] = (
            self._region_solve_stats.get("axis_exact_fallback", 0.0) + 1.0
        )
        reason_key = f"axis_exact_{reason}"
        self._region_solve_stats[reason_key] = self._region_solve_stats.get(reason_key, 0.0) + 1.0
        self._region_solve_stats["axis_exact_total_time_s"] = (
            self._region_solve_stats.get("axis_exact_total_time_s", 0.0)
            + (time.perf_counter() - start_time)
        )
        return None

    def _axis_conical_transition_curve(
        self,
        axis: dict,
        conical_model: dict,
        overlap: QgsGeometry,
    ) -> Optional[QgsGeometry]:
        station_range = self._axis_station_range(axis, overlap)
        conical_slope = float(conical_model["slope"])
        base_footprint = conical_model.get("base_footprint")
        if station_range is None or base_footprint is None or conical_slope <= 0.0:
            return None
        min_station, max_station = station_range
        if max_station - min_station <= 1e-6:
            return None

        a_offset = (float(axis["origin_elevation_m"]) - float(conical_model["base_elevation_m"])) / conical_slope
        b_slope = float(axis["slope"]) / conical_slope
        max_distance = conical_model.get("max_distance_m")
        max_distance = float(max_distance) if max_distance is not None else None

        curve_pieces: List[QgsGeometry] = []
        for ring in self._polygon_boundary_parts(base_footprint):
            points = ring[:-1] if len(ring) > 1 and ring[0].distance(ring[-1]) <= 1e-6 else ring
            if len(points) < 2:
                continue
            for index, start_point in enumerate(points):
                end_point = points[(index + 1) % len(points)]
                curve_pieces.extend(
                    self._axis_conical_edge_transition_pieces(
                        axis,
                        base_footprint,
                        start_point,
                        end_point,
                        a_offset,
                        b_slope,
                        max_distance,
                        overlap,
                    )
                )
            for vertex in points:
                curve_pieces.extend(
                    self._axis_conical_vertex_transition_pieces(
                        axis,
                        base_footprint,
                        vertex,
                        a_offset,
                        b_slope,
                        max_distance,
                        min_station,
                        max_station,
                        overlap,
                    )
                )

        if not curve_pieces:
            return None
        try:
            return QgsGeometry.unaryUnion(curve_pieces) if len(curve_pieces) > 1 else curve_pieces[0]
        except Exception:
            return curve_pieces[0]

    def _axis_conical_edge_transition_pieces(
        self,
        axis: dict,
        base_footprint: QgsGeometry,
        edge_start: QgsPointXY,
        edge_end: QgsPointXY,
        a_offset: float,
        b_slope: float,
        max_distance: Optional[float],
        overlap: QgsGeometry,
    ) -> List[QgsGeometry]:
        edge_length = edge_start.distance(edge_end)
        if edge_length <= 1e-6:
            return []
        ex = (edge_end.x() - edge_start.x()) / edge_length
        ey = (edge_end.y() - edge_start.y()) / edge_length
        pieces: List[QgsGeometry] = []
        for nx, ny in ((-ey, ex), (ey, -ex)):
            ux = float(axis["ux"])
            uy = float(axis["uy"])
            origin_dot = (ux * float(axis["origin_x"])) + (uy * float(axis["origin_y"]))
            a = nx - (b_slope * ux)
            b = ny - (b_slope * uy)
            c = -((nx * edge_start.x()) + (ny * edge_start.y())) - a_offset + (b_slope * origin_dot)
            point_on_line = self._point_on_line_near_geometry(overlap, a, b, c)
            if point_on_line is None:
                continue
            line = self._clip_long_line_to_domain(overlap, point_on_line, -b, a)
            if line is None or line.isEmpty():
                continue
            for line_points in self._line_parts(line):
                pieces.extend(
                    self._filtered_axis_conical_curve_segments(
                        axis,
                        base_footprint,
                        line_points,
                        a_offset,
                        b_slope,
                        max_distance,
                        overlap,
                        edge_start=edge_start,
                        edge_end=edge_end,
                    )
                )
        return pieces

    def _axis_conical_vertex_transition_pieces(
        self,
        axis: dict,
        base_footprint: QgsGeometry,
        vertex: QgsPointXY,
        a_offset: float,
        b_slope: float,
        max_distance: Optional[float],
        min_station: float,
        max_station: float,
        overlap: QgsGeometry,
    ) -> List[QgsGeometry]:
        tv, lv = self._axis_local_coordinates(axis, vertex)
        station_step = AXIS_CONICAL_VERTEX_CURVE_STATION_STEP_M
        curves: List[QgsGeometry] = []
        for sign in (-1.0, 1.0):
            current_points: List[QgsPointXY] = []
            t = min_station
            while t <= max_station + 1e-6:
                point_xy = self._axis_conical_vertex_curve_point(axis, tv, lv, a_offset, b_slope, t, sign)
                if point_xy is not None and self._axis_conical_curve_point_is_valid(
                    axis,
                    base_footprint,
                    point_xy,
                    a_offset,
                    b_slope,
                    max_distance,
                    overlap,
                    vertex=vertex,
                ):
                    current_points.append(point_xy)
                else:
                    if len(current_points) >= 2:
                        curves.extend(
                            self._densified_axis_conical_vertex_curve(
                                axis,
                                base_footprint,
                                current_points,
                                tv,
                                lv,
                                a_offset,
                                b_slope,
                                max_distance,
                                overlap,
                                vertex,
                                sign,
                            )
                        )
                    current_points = []
                t += station_step
            if len(current_points) >= 2:
                curves.extend(
                    self._densified_axis_conical_vertex_curve(
                        axis,
                        base_footprint,
                        current_points,
                        tv,
                        lv,
                        a_offset,
                        b_slope,
                        max_distance,
                        overlap,
                        vertex,
                        sign,
                    )
                )
        return curves

    def _axis_local_coordinates(self, axis: dict, point_xy: QgsPointXY) -> Tuple[float, float]:
        ux = float(axis["ux"])
        uy = float(axis["uy"])
        vx = -uy
        vy = ux
        dx = point_xy.x() - float(axis["origin_x"])
        dy = point_xy.y() - float(axis["origin_y"])
        return (dx * ux) + (dy * uy), (dx * vx) + (dy * vy)

    def _axis_point_from_local(self, axis: dict, station: float, lateral: float) -> QgsPointXY:
        ux = float(axis["ux"])
        uy = float(axis["uy"])
        vx = -uy
        vy = ux
        return QgsPointXY(
            float(axis["origin_x"]) + (station * ux) + (lateral * vx),
            float(axis["origin_y"]) + (station * uy) + (lateral * vy),
        )

    def _axis_conical_vertex_curve_point(
        self,
        axis: dict,
        vertex_station: float,
        vertex_lateral: float,
        a_offset: float,
        b_slope: float,
        station: float,
        sign: float,
    ) -> Optional[QgsPointXY]:
        required_distance = a_offset + (b_slope * station)
        discriminant = (required_distance * required_distance) - ((station - vertex_station) ** 2)
        if discriminant < -1e-9:
            return None
        lateral = vertex_lateral + (sign * math.sqrt(max(0.0, discriminant)))
        return self._axis_point_from_local(axis, station, lateral)

    def _axis_conical_curve_point_is_valid(
        self,
        axis: dict,
        base_footprint: QgsGeometry,
        point_xy: QgsPointXY,
        a_offset: float,
        b_slope: float,
        max_distance: Optional[float],
        overlap: QgsGeometry,
        edge_start: Optional[QgsPointXY] = None,
        edge_end: Optional[QgsPointXY] = None,
        vertex: Optional[QgsPointXY] = None,
    ) -> bool:
        try:
            point_geometry = QgsGeometry.fromPointXY(point_xy)
            if not overlap.intersects(point_geometry):
                return False
            station = self._axis_station(axis, point_xy)
            required_distance = max(0.0, a_offset + (b_slope * station))
            if max_distance is not None and required_distance > max_distance + self.tie_tolerance_m:
                return False
            actual_distance = point_geometry.distance(base_footprint)
            if abs(actual_distance - required_distance) > AXIS_CONICAL_CURVE_FILTER_TOLERANCE_M:
                return False
            if edge_start is not None and edge_end is not None:
                edge_length = edge_start.distance(edge_end)
                if edge_length <= 1e-6:
                    return False
                projection = (
                    ((point_xy.x() - edge_start.x()) * (edge_end.x() - edge_start.x()))
                    + ((point_xy.y() - edge_start.y()) * (edge_end.y() - edge_start.y()))
                ) / (edge_length * edge_length)
                if projection < -1e-6 or projection > 1.0 + 1e-6:
                    return False
            if vertex is not None:
                vertex_distance = point_xy.distance(vertex)
                if abs(vertex_distance - actual_distance) > AXIS_CONICAL_CURVE_FILTER_TOLERANCE_M:
                    return False
        except Exception:
            return False
        return True

    def _filtered_axis_conical_curve_segments(
        self,
        axis: dict,
        base_footprint: QgsGeometry,
        line_points: Sequence[QgsPointXY],
        a_offset: float,
        b_slope: float,
        max_distance: Optional[float],
        overlap: QgsGeometry,
        edge_start: Optional[QgsPointXY] = None,
        edge_end: Optional[QgsPointXY] = None,
        vertex: Optional[QgsPointXY] = None,
    ) -> List[QgsGeometry]:
        pieces: List[QgsGeometry] = []
        current: List[QgsPointXY] = []
        for start_point, end_point in zip(line_points[:-1], line_points[1:]):
            segment_length = start_point.distance(end_point)
            steps = max(1, int(math.ceil(segment_length / 2.0)))
            for step in range(steps + 1):
                fraction = step / steps
                point_xy = QgsPointXY(
                    start_point.x() + ((end_point.x() - start_point.x()) * fraction),
                    start_point.y() + ((end_point.y() - start_point.y()) * fraction),
                )
                if self._axis_conical_curve_point_is_valid(
                    axis,
                    base_footprint,
                    point_xy,
                    a_offset,
                    b_slope,
                    max_distance,
                    overlap,
                    edge_start=edge_start,
                    edge_end=edge_end,
                    vertex=vertex,
                ):
                    if not current or point_xy.distance(current[-1]) > 1e-6:
                        current.append(point_xy)
                else:
                    if len(current) >= 2:
                        pieces.append(QgsGeometry.fromPolylineXY(current))
                    current = []
        if len(current) >= 2:
            pieces.append(QgsGeometry.fromPolylineXY(current))
        return [piece for piece in pieces if piece is not None and not piece.isEmpty()]

    def _densified_axis_conical_vertex_curve(
        self,
        axis: dict,
        base_footprint: QgsGeometry,
        seed_points: Sequence[QgsPointXY],
        vertex_station: float,
        vertex_lateral: float,
        a_offset: float,
        b_slope: float,
        max_distance: Optional[float],
        overlap: QgsGeometry,
        vertex: QgsPointXY,
        sign: float,
    ) -> List[QgsGeometry]:
        densified: List[QgsPointXY] = []
        for start_point, end_point in zip(seed_points[:-1], seed_points[1:]):
            start_station = self._axis_station(axis, start_point)
            end_station = self._axis_station(axis, end_point)
            segment_points = self._axis_conical_vertex_curve_segment_points(
                axis,
                vertex_station,
                vertex_lateral,
                a_offset,
                b_slope,
                start_station,
                end_station,
                sign,
            )
            for point_xy in segment_points:
                if not self._axis_conical_curve_point_is_valid(
                    axis,
                    base_footprint,
                    point_xy,
                    a_offset,
                    b_slope,
                    max_distance,
                    overlap,
                    vertex=vertex,
                ):
                    continue
                if not densified or point_xy.distance(densified[-1]) > 1e-6:
                    densified.append(point_xy)
        if len(densified) < 2:
            return []
        return [QgsGeometry.fromPolylineXY(densified)]

    def _axis_conical_vertex_curve_segment_points(
        self,
        axis: dict,
        vertex_station: float,
        vertex_lateral: float,
        a_offset: float,
        b_slope: float,
        start_station: float,
        end_station: float,
        sign: float,
        depth: int = 0,
    ) -> List[QgsPointXY]:
        start_point = self._axis_conical_vertex_curve_point(
            axis, vertex_station, vertex_lateral, a_offset, b_slope, start_station, sign
        )
        end_point = self._axis_conical_vertex_curve_point(
            axis, vertex_station, vertex_lateral, a_offset, b_slope, end_station, sign
        )
        if start_point is None or end_point is None:
            return []
        mid_station = (start_station + end_station) / 2.0
        mid_point = self._axis_conical_vertex_curve_point(
            axis, vertex_station, vertex_lateral, a_offset, b_slope, mid_station, sign
        )
        if mid_point is None:
            return [start_point, end_point]
        chord_distance = self._point_to_segment_distance(mid_point, start_point, end_point)
        if chord_distance <= AXIS_CONICAL_VERTEX_CURVE_CHORD_TOLERANCE_M or depth >= 8:
            return [start_point, end_point]
        left = self._axis_conical_vertex_curve_segment_points(
            axis,
            vertex_station,
            vertex_lateral,
            a_offset,
            b_slope,
            start_station,
            mid_station,
            sign,
            depth + 1,
        )
        right = self._axis_conical_vertex_curve_segment_points(
            axis,
            vertex_station,
            vertex_lateral,
            a_offset,
            b_slope,
            mid_station,
            end_station,
            sign,
            depth + 1,
        )
        return left[:-1] + right if left and right else left + right

    def _point_to_segment_distance(
        self,
        point_xy: QgsPointXY,
        segment_start: QgsPointXY,
        segment_end: QgsPointXY,
    ) -> float:
        projection = self._point_projection_fraction(segment_start, segment_end, point_xy)
        if projection is None:
            return point_xy.distance(segment_start)
        projection = max(0.0, min(1.0, projection))
        projected = QgsPointXY(
            segment_start.x() + ((segment_end.x() - segment_start.x()) * projection),
            segment_start.y() + ((segment_end.y() - segment_start.y()) * projection),
        )
        return point_xy.distance(projected)

    def _axis_lateral_bounds(self, axis: dict, bbox: QgsRectangle) -> Tuple[float, float]:
        ux = float(axis["ux"])
        uy = float(axis["uy"])
        vx = -uy
        vy = ux
        origin_x = float(axis["origin_x"])
        origin_y = float(axis["origin_y"])
        values = []
        for x, y in (
            (bbox.xMinimum(), bbox.yMinimum()),
            (bbox.xMinimum(), bbox.yMaximum()),
            (bbox.xMaximum(), bbox.yMinimum()),
            (bbox.xMaximum(), bbox.yMaximum()),
        ):
            values.append(((x - origin_x) * vx) + ((y - origin_y) * vy))
        padding = max(25.0, (max(values) - min(values)) * 0.05)
        return min(values) - padding, max(values) + padding

    def _axis_conical_lateral_roots(
        self,
        axis: dict,
        base_footprint: QgsGeometry,
        station: float,
        required_distance: float,
        l_min: float,
        l_max: float,
        lateral_step: float,
    ) -> List[QgsPointXY]:
        roots: List[QgsPointXY] = []

        def _point_at(lateral: float) -> QgsPointXY:
            ux = float(axis["ux"])
            uy = float(axis["uy"])
            vx = -uy
            vy = ux
            return QgsPointXY(
                float(axis["origin_x"]) + (station * ux) + (lateral * vx),
                float(axis["origin_y"]) + (station * uy) + (lateral * vy),
            )

        def _difference(lateral: float) -> float:
            point_xy = _point_at(lateral)
            return QgsGeometry.fromPointXY(point_xy).distance(base_footprint) - required_distance

        previous_l = l_min
        try:
            previous_value = _difference(previous_l)
        except Exception:
            return []
        l_value = l_min + lateral_step
        while l_value <= l_max + 1e-6:
            try:
                current_value = _difference(l_value)
            except Exception:
                previous_l = l_value
                l_value += lateral_step
                continue
            if previous_value == 0.0 or current_value == 0.0 or previous_value * current_value < 0.0:
                root_l = self._axis_conical_bisect_lateral_root(_difference, previous_l, l_value)
                point_xy = _point_at(root_l)
                if not roots or point_xy.distance(roots[-1]) > 0.5:
                    roots.append(point_xy)
            previous_l = l_value
            previous_value = current_value
            l_value += lateral_step
        return roots

    def _axis_conical_bisect_lateral_root(
        self,
        difference_fn: Callable[[float], float],
        lower_l: float,
        upper_l: float,
    ) -> float:
        lower_value = difference_fn(lower_l)
        upper_value = difference_fn(upper_l)
        for _ in range(12):
            mid_l = (lower_l + upper_l) / 2.0
            mid_value = difference_fn(mid_l)
            if abs(mid_value) <= 0.01:
                return mid_l
            if lower_value * mid_value <= 0.0:
                upper_l = mid_l
                upper_value = mid_value
            else:
                lower_l = mid_l
                lower_value = mid_value
        return (lower_l + upper_l) / 2.0

    def _split_overlap_by_transition_curve(
        self,
        overlap: QgsGeometry,
        transition_curve: QgsGeometry,
    ) -> List[QgsGeometry]:
        polygonized_parts = self._polygonize_overlap_by_transition_curve(overlap, transition_curve)
        if polygonized_parts:
            self._region_solve_stats["axis_exact_polygonize_success"] = (
                self._region_solve_stats.get("axis_exact_polygonize_success", 0.0) + 1.0
            )
            return polygonized_parts

        manual_parts = self._manual_split_overlap_by_transition_curve(overlap, transition_curve)
        if manual_parts:
            self._region_solve_stats["axis_exact_manual_split_used"] = (
                self._region_solve_stats.get("axis_exact_manual_split_used", 0.0) + 1.0
            )
            return manual_parts

        parts = self._polygon_parts(overlap)
        for line_points in self._line_parts(transition_curve):
            if len(line_points) < 2:
                continue
            next_parts: List[QgsGeometry] = []
            for part in parts:
                split_result = self._split_polygon_part_by_line(part, line_points)
                next_parts.extend(split_result if split_result else [part])
            parts = next_parts
        split_parts = [part for part in parts if self._has_polygon_area(part)]
        if len(split_parts) > 1:
            self._region_solve_stats["axis_exact_splitgeometry_used"] = (
                self._region_solve_stats.get("axis_exact_splitgeometry_used", 0.0) + 1.0
            )
        return split_parts

    def _polygonize_overlap_by_transition_curve(
        self,
        overlap: QgsGeometry,
        transition_curve: QgsGeometry,
    ) -> List[QgsGeometry]:
        if not hasattr(QgsGeometry, "polygonize"):
            return []
        linework: List[QgsGeometry] = []
        try:
            for boundary_points in self._polygon_boundary_parts(overlap):
                if len(boundary_points) >= 2:
                    linework.append(QgsGeometry.fromPolylineXY(boundary_points))
            for curve_points in self._line_parts(transition_curve):
                self._region_solve_stats["axis_exact_curve_vertices_raw"] = (
                    self._region_solve_stats.get("axis_exact_curve_vertices_raw", 0.0)
                    + float(len(curve_points))
                )
                curve_points = self._simplify_transition_curve_points(
                    curve_points,
                    AXIS_CONICAL_CURVE_SIMPLIFY_TOLERANCE_M,
                )
                self._region_solve_stats["axis_exact_curve_vertices_simplified"] = (
                    self._region_solve_stats.get("axis_exact_curve_vertices_simplified", 0.0)
                    + float(len(curve_points))
                )
                curve_points = self._condition_transition_curve_for_polygonize(curve_points, overlap)
                if len(curve_points) >= 2:
                    linework.append(QgsGeometry.fromPolylineXY(curve_points))
            linework = [geometry for geometry in linework if geometry is not None and not geometry.isEmpty()]
            if len(linework) < 2:
                return []
            polygonized = QgsGeometry.polygonize(linework)
        except Exception:
            return []
        faces: List[QgsGeometry] = []
        for face in self._polygon_parts(polygonized):
            try:
                clipped = face.intersection(overlap)
            except Exception:
                clipped = None
            for part in self._polygon_parts(clipped):
                if self._has_polygon_area(part):
                    faces.append(part)
        return faces if self._split_parts_are_valid(overlap, faces) else []

    def _manual_split_overlap_by_transition_curve(
        self,
        overlap: QgsGeometry,
        transition_curve: QgsGeometry,
    ) -> List[QgsGeometry]:
        parts = self._polygon_parts(overlap)
        if not parts:
            return []
        for curve_points in self._line_parts(transition_curve):
            if len(curve_points) < 2:
                continue
            curve_points = self._simplify_transition_curve_points(
                curve_points,
                AXIS_CONICAL_CURVE_SIMPLIFY_TOLERANCE_M,
            )
            curve_points = self._condition_transition_curve_for_polygonize(curve_points, overlap)
            next_parts: List[QgsGeometry] = []
            changed = False
            for part in parts:
                split_parts = self._manual_split_polygon_part_by_curve(part, curve_points)
                if split_parts:
                    next_parts.extend(split_parts)
                    changed = True
                else:
                    next_parts.append(part)
            if changed:
                parts = next_parts
        parts = [part for part in parts if self._has_polygon_area(part)]
        return parts if self._split_parts_are_valid(overlap, parts) else []

    def _manual_split_polygon_part_by_curve(
        self,
        polygon: QgsGeometry,
        curve_points: Sequence[QgsPointXY],
    ) -> List[QgsGeometry]:
        if polygon is None or polygon.isEmpty() or len(curve_points) < 2:
            return []
        try:
            if polygon.isMultipart():
                return []
            polygon_rings = polygon.asPolygon()
        except Exception:
            return []
        if not polygon_rings or not polygon_rings[0] or len(polygon_rings) > 1:
            return []
        exterior = (
            list(polygon_rings[0][:-1])
            if polygon_rings[0][0].distance(polygon_rings[0][-1]) <= 1e-9
            else list(polygon_rings[0])
        )
        if len(exterior) < 3:
            return []
        start_location = self._ring_location_for_point(exterior, curve_points[0])
        end_location = self._ring_location_for_point(exterior, curve_points[-1])
        if start_location is None or end_location is None:
            return []
        if start_location[0] == end_location[0] and abs(start_location[1] - end_location[1]) <= 1e-6:
            return []
        forward_boundary = self._ring_path_between_locations(exterior, start_location, end_location)
        backward_boundary = self._ring_path_between_locations(exterior, end_location, start_location)
        if len(forward_boundary) < 2 or len(backward_boundary) < 2:
            return []
        curve_forward = [QgsPointXY(point.x(), point.y()) for point in curve_points]
        curve_backward = list(reversed(curve_forward))
        first_ring = self._closed_ring_from_paths(forward_boundary, curve_backward)
        second_ring = self._closed_ring_from_paths(backward_boundary, curve_forward)
        split_parts: List[QgsGeometry] = []
        for ring in (first_ring, second_ring):
            if len(ring) < 4:
                continue
            geom = QgsGeometry.fromPolygonXY([ring])
            if geom is None or not self._has_polygon_area(geom):
                continue
            try:
                geom = geom.intersection(polygon)
            except Exception:
                return []
            for part in self._polygon_parts(geom):
                if self._has_polygon_area(part):
                    split_parts.append(part)
        return split_parts if self._split_parts_are_valid(polygon, split_parts) else []

    def _ring_location_for_point(
        self,
        ring_points: Sequence[QgsPointXY],
        point_xy: QgsPointXY,
    ) -> Optional[Tuple[int, float, QgsPointXY]]:
        best_location: Optional[Tuple[int, float, QgsPointXY]] = None
        best_distance = math.inf
        point_count = len(ring_points)
        for index in range(point_count):
            start_point = ring_points[index]
            end_point = ring_points[(index + 1) % point_count]
            projection = self._point_projection_fraction(start_point, end_point, point_xy)
            if projection is None:
                continue
            clamped_projection = max(0.0, min(1.0, projection))
            projected = QgsPointXY(
                start_point.x() + ((end_point.x() - start_point.x()) * clamped_projection),
                start_point.y() + ((end_point.y() - start_point.y()) * clamped_projection),
            )
            distance = projected.distance(point_xy)
            if distance < best_distance:
                best_distance = distance
                best_location = (index, clamped_projection, projected)
        if best_distance > max(AXIS_CONICAL_CURVE_ENDPOINT_SNAP_TOLERANCE_M, CONTROLLING_REGION_RING_TOUCH_TOLERANCE_M):
            return None
        return best_location

    def _ring_path_between_locations(
        self,
        ring_points: Sequence[QgsPointXY],
        start_location: Tuple[int, float, QgsPointXY],
        end_location: Tuple[int, float, QgsPointXY],
    ) -> List[QgsPointXY]:
        point_count = len(ring_points)
        if point_count < 3:
            return []
        start_segment, _, start_point = start_location
        end_segment, _, end_point = end_location
        path = [QgsPointXY(start_point)]
        index = (start_segment + 1) % point_count
        guard = 0
        while index != (end_segment + 1) % point_count:
            candidate = ring_points[index]
            if path[-1].distance(candidate) > 1e-9:
                path.append(QgsPointXY(candidate))
            index = (index + 1) % point_count
            guard += 1
            if guard > point_count + 1:
                return []
        if path[-1].distance(end_point) > 1e-9:
            path.append(QgsPointXY(end_point))
        return path

    def _closed_ring_from_paths(
        self,
        first_path: Sequence[QgsPointXY],
        second_path: Sequence[QgsPointXY],
    ) -> List[QgsPointXY]:
        ring: List[QgsPointXY] = []
        for point in list(first_path) + list(second_path):
            point_xy = QgsPointXY(point.x(), point.y())
            if not ring or ring[-1].distance(point_xy) > 1e-9:
                ring.append(point_xy)
        if ring and ring[0].distance(ring[-1]) > 1e-9:
            ring.append(QgsPointXY(ring[0]))
        return ring

    def _simplify_transition_curve_points(
        self,
        curve_points: Sequence[QgsPointXY],
        tolerance_m: float,
    ) -> List[QgsPointXY]:
        points = [QgsPointXY(point.x(), point.y()) for point in curve_points]
        if len(points) <= 2 or tolerance_m <= 0.0:
            return points
        keep_indexes = {0, len(points) - 1}
        stack: List[Tuple[int, int]] = [(0, len(points) - 1)]
        while stack:
            start_index, end_index = stack.pop()
            if end_index - start_index <= 1:
                continue
            start_point = points[start_index]
            end_point = points[end_index]
            max_distance = -1.0
            max_index: Optional[int] = None
            for index in range(start_index + 1, end_index):
                distance = self._point_to_segment_distance(points[index], start_point, end_point)
                if distance > max_distance:
                    max_distance = distance
                    max_index = index
            if max_index is not None and max_distance > tolerance_m:
                keep_indexes.add(max_index)
                stack.append((start_index, max_index))
                stack.append((max_index, end_index))
        return [points[index] for index in sorted(keep_indexes)]

    def _condition_transition_curve_for_polygonize(
        self,
        curve_points: Sequence[QgsPointXY],
        overlap: QgsGeometry,
    ) -> List[QgsPointXY]:
        conditioned = [QgsPointXY(point.x(), point.y()) for point in curve_points]
        if len(conditioned) < 2 or overlap is None or overlap.isEmpty():
            return conditioned
        conditioned[0] = self._condition_transition_curve_endpoint(
            conditioned[0],
            conditioned[1],
            overlap,
        )
        conditioned[-1] = self._condition_transition_curve_endpoint(
            conditioned[-1],
            conditioned[-2],
            overlap,
        )
        return conditioned

    def _condition_transition_curve_endpoint(
        self,
        endpoint: QgsPointXY,
        adjacent_point: QgsPointXY,
        overlap: QgsGeometry,
    ) -> QgsPointXY:
        nearest_boundary_point, nearest_distance = self._nearest_boundary_point(overlap, endpoint)
        if (
            nearest_boundary_point is not None
            and nearest_distance <= AXIS_CONICAL_CURVE_ENDPOINT_SNAP_TOLERANCE_M
        ):
            return nearest_boundary_point

        dx = endpoint.x() - adjacent_point.x()
        dy = endpoint.y() - adjacent_point.y()
        length = math.hypot(dx, dy)
        if length <= 1e-9:
            return endpoint
        direction = QgsPointXY(dx / length, dy / length)
        boundary_point = self._first_boundary_intersection_along_ray(
            endpoint,
            direction,
            overlap,
            AXIS_CONICAL_CURVE_ENDPOINT_EXTENSION_M,
        )
        if boundary_point is not None:
            return boundary_point
        return endpoint

    def _nearest_boundary_point(
        self,
        geometry: QgsGeometry,
        point_xy: QgsPointXY,
    ) -> Tuple[Optional[QgsPointXY], float]:
        nearest_point: Optional[QgsPointXY] = None
        nearest_distance = math.inf
        for ring in self._polygon_boundary_parts(geometry):
            for start_point, end_point in zip(ring[:-1], ring[1:]):
                projected = self._project_point_to_segment(start_point, end_point, point_xy)
                if projected is None:
                    continue
                distance = projected.distance(point_xy)
                if distance < nearest_distance:
                    nearest_point = projected
                    nearest_distance = distance
        return nearest_point, nearest_distance

    def _project_point_to_segment(
        self,
        segment_start: QgsPointXY,
        segment_end: QgsPointXY,
        point_xy: QgsPointXY,
    ) -> Optional[QgsPointXY]:
        projection = self._point_projection_fraction(segment_start, segment_end, point_xy)
        if projection is None:
            return None
        projection = max(0.0, min(1.0, projection))
        return QgsPointXY(
            segment_start.x() + ((segment_end.x() - segment_start.x()) * projection),
            segment_start.y() + ((segment_end.y() - segment_start.y()) * projection),
        )

    def _first_boundary_intersection_along_ray(
        self,
        origin: QgsPointXY,
        direction: QgsPointXY,
        geometry: QgsGeometry,
        max_distance: float,
    ) -> Optional[QgsPointXY]:
        best_t = math.inf
        best_point: Optional[QgsPointXY] = None
        for ring in self._polygon_boundary_parts(geometry):
            for start_point, end_point in zip(ring[:-1], ring[1:]):
                intersection = self._ray_segment_intersection(origin, direction, start_point, end_point)
                if intersection is None:
                    continue
                t, point_xy = intersection
                if 1e-6 < t <= max_distance and t < best_t:
                    best_t = t
                    best_point = point_xy
        return best_point

    def _ray_segment_intersection(
        self,
        origin: QgsPointXY,
        direction: QgsPointXY,
        segment_start: QgsPointXY,
        segment_end: QgsPointXY,
    ) -> Optional[Tuple[float, QgsPointXY]]:
        sx = segment_end.x() - segment_start.x()
        sy = segment_end.y() - segment_start.y()
        denominator = (direction.x() * sy) - (direction.y() * sx)
        if abs(denominator) <= 1e-12:
            return None
        ox = segment_start.x() - origin.x()
        oy = segment_start.y() - origin.y()
        t = ((ox * sy) - (oy * sx)) / denominator
        u = ((ox * direction.y()) - (oy * direction.x())) / denominator
        if t < -1e-9 or u < -1e-9 or u > 1.0 + 1e-9:
            return None
        return (
            t,
            QgsPointXY(
                origin.x() + (direction.x() * t),
                origin.y() + (direction.y() * t),
            ),
        )

    def _split_polygon_part_by_line(
        self,
        polygon: QgsGeometry,
        line_points: Sequence[QgsPointXY],
    ) -> List[QgsGeometry]:
        try:
            split_target = QgsGeometry(polygon)
            result = split_target.splitGeometry(list(line_points), False)
        except Exception:
            return []
        new_geometries = []
        if isinstance(result, tuple):
            if len(result) >= 2 and isinstance(result[1], list):
                new_geometries = result[1]
        if not new_geometries:
            return []
        split_parts = [split_target]
        split_parts.extend(QgsGeometry(geometry) for geometry in new_geometries)
        return [part for part in split_parts if self._has_polygon_area(part)]

    def _split_parts_are_valid(self, overlap: QgsGeometry, parts: Sequence[QgsGeometry]) -> bool:
        valid_parts = [part for part in parts if self._has_polygon_area(part)]
        if len(valid_parts) <= 1 or not self._has_polygon_area(overlap):
            return False
        try:
            overlap_area = abs(overlap.area())
            part_area_sum = sum(abs(part.area()) for part in valid_parts)
            union = QgsGeometry.unaryUnion(valid_parts) if len(valid_parts) > 1 else QgsGeometry(valid_parts[0])
            if not self._has_polygon_area(union):
                return False
            union_area = abs(union.area())
        except Exception:
            return False
        tolerance = max(1.0, overlap_area * 1e-6)
        if abs(union_area - overlap_area) > tolerance:
            return False
        if abs(part_area_sum - union_area) > tolerance:
            return False
        return True

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
        start_time = time.perf_counter()
        try:
            points = self._triangulation_sample_points(geometry)
            point_count = len(points)
            self._region_solve_stats["triangulation_calls"] = (
                self._region_solve_stats.get("triangulation_calls", 0.0) + 1.0
            )
            self._region_solve_stats["triangulation_points_total"] = (
                self._region_solve_stats.get("triangulation_points_total", 0.0) + float(point_count)
            )
            self._region_solve_stats["triangulation_points_max"] = max(
                self._region_solve_stats.get("triangulation_points_max", 0.0),
                float(point_count),
            )
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
        finally:
            self._region_solve_stats["triangulation_time_s"] = (
                self._region_solve_stats.get("triangulation_time_s", 0.0)
                + (time.perf_counter() - start_time)
            )

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

    def _triangulation_sample_points(
        self,
        geometry: QgsGeometry,
    ) -> List[QgsPointXY]:
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
            if not self._bounding_boxes_intersect(first_candidate.footprint, second_candidate.footprint):
                return []
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

    def _bounding_boxes_intersect(self, first: Optional[QgsGeometry], second: Optional[QgsGeometry]) -> bool:
        if first is None or second is None or first.isEmpty() or second.isEmpty():
            return False
        try:
            return bool(first.boundingBox().intersects(second.boundingBox()))
        except Exception:
            return True

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
        self._controlling_ols_contours: List[ControllingOlsContour] = []

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

    def _register_controlling_ols_contour(
        self,
        surface_id: str,
        surface_type: str,
        contour_feature: QgsFeature,
        source_layer: str,
    ) -> None:
        geometry = contour_feature.geometry()
        if geometry is None or geometry.isEmpty():
            return
        if not hasattr(self, "_controlling_ols_contours"):
            self._controlling_ols_contours = []
        try:
            contour_elevation = contour_feature.attribute("contour_elev_am")
            contour_elevation = float(contour_elevation) if contour_elevation is not None else None
        except (KeyError, TypeError, ValueError):
            contour_elevation = None

        def _feature_attr(name: str):
            try:
                return contour_feature.attribute(name)
            except (KeyError, TypeError):
                return None

        contour_class = _feature_attr("contour_class")
        contour_class = str(contour_class) if contour_class not in (None, "") else None

        def _float_attr(name: str) -> Optional[float]:
            try:
                value = _feature_attr(name)
                return float(value) if value not in (None, "") else None
            except (TypeError, ValueError):
                return None

        contour_interval_m = _float_attr("contour_interval_m")
        primary_interval_m = _float_attr("primary_interval_m")
        if contour_class is None and hasattr(self, "_contour_attribute_values"):
            surface_key = str(surface_type or "").strip().lower().replace("-", "_").replace(" ", "_")
            if surface_key == "balked_landing":
                surface_key = "baulked_landing"
            metadata = self._contour_attribute_values(surface_key, contour_elevation)
            contour_class = metadata.get("contour_class")  # type: ignore[assignment]
            contour_interval_m = contour_interval_m or metadata.get("contour_interval_m")  # type: ignore[assignment]
            primary_interval_m = primary_interval_m or metadata.get("primary_interval_m")  # type: ignore[assignment]
        self._controlling_ols_contours.append(
            ControllingOlsContour(
                surface_id=surface_id,
                surface_type=surface_type,
                geometry=QgsGeometry(geometry),
                contour_elevation_m=contour_elevation,
                source_layer=source_layer,
                contour_class=contour_class,
                contour_interval_m=contour_interval_m,
                primary_interval_m=primary_interval_m,
            )
        )

    def _create_controlling_ols_layers(
        self,
        icao_code: str,
        debug_group: QgsLayerTreeGroup,
        controlling_surfaces_group: Optional[QgsLayerTreeGroup] = None,
        controlling_contours_group: Optional[QgsLayerTreeGroup] = None,
        solved_engines: Optional[Dict[str, PlanarControllingOlsEngine]] = None,
    ) -> bool:
        overall_start = time.perf_counter()
        candidates = list(getattr(self, "_controlling_ols_candidates", []) or [])
        exclusion_geometries = list(getattr(self, "_controlling_ols_exclusion_geometries", []) or [])
        contours = list(getattr(self, "_controlling_ols_contours", []) or [])
        planar_candidates = [
            candidate
            for candidate in candidates
            if candidate.model in {"constant", "axis", "plane", "conical"}
        ]
        if not planar_candidates:
            QgsMessageLog.logMessage(
                "[skip] Controlling OLS: no planar candidate surfaces were registered.",
                PLUGIN_TAG,
                Qgis.Info,
            )
            return False

        diagnostic_group = self._controlling_ols_diagnostic_group(debug_group)
        region_output_group = controlling_surfaces_group if controlling_surfaces_group is not None else diagnostic_group
        contour_output_group = controlling_contours_group if controlling_contours_group is not None else diagnostic_group
        engine = PlanarControllingOlsEngine(planar_candidates, exclusion_geometries=exclusion_geometries)
        if solved_engines is not None:
            solved_engines["baseline"] = engine
        timing_splits: Dict[str, float] = {}

        if not self._controlling_ols_subphase("Controlling OLS: preparing candidate surfaces..."):
            return False
        step_start = time.perf_counter()
        candidate_layer_ok = self._create_controlling_candidate_layer(icao_code, diagnostic_group, planar_candidates)
        timing_splits["candidates"] = time.perf_counter() - step_start

        if not self._controlling_ols_subphase("Controlling OLS: solving lower-envelope regions..."):
            return candidate_layer_ok
        step_start = time.perf_counter()
        region_layer_ok = self._create_controlling_region_layer(icao_code, region_output_group, engine)
        timing_splits["regions"] = time.perf_counter() - step_start

        if not self._controlling_ols_subphase("Controlling OLS: constructing transition boundaries..."):
            return candidate_layer_ok or region_layer_ok
        step_start = time.perf_counter()
        transition_layer_ok = self._create_controlling_transition_layer(icao_code, diagnostic_group, engine)
        timing_splits["transitions"] = time.perf_counter() - step_start

        if not self._controlling_ols_subphase("Controlling OLS: clipping source contours..."):
            return candidate_layer_ok or region_layer_ok or transition_layer_ok
        step_start = time.perf_counter()
        contour_layer_ok = self._create_controlling_contour_layer(
            icao_code,
            contour_output_group,
            engine,
            contours,
        )
        timing_splits["contours"] = time.perf_counter() - step_start

        QgsMessageLog.logMessage(
            "[done] Controlling OLS summary: "
            f"candidates={timing_splits['candidates']:.2f}s, "
            f"regions={timing_splits['regions']:.2f}s, "
            f"transitions={timing_splits['transitions']:.2f}s, "
            f"contours={timing_splits['contours']:.2f}s, "
            f"total={time.perf_counter() - overall_start:.2f}s; "
            f"inputs={len(planar_candidates)} candidates, {len(exclusion_geometries)} exclusion masks, "
            f"{len(contours)} source contours.",
            PLUGIN_TAG,
            Qgis.Info,
        )
        return candidate_layer_ok or region_layer_ok or transition_layer_ok or contour_layer_ok

    def _create_annex14_controlling_surface_layers(
        self,
        icao_code: str,
        ofs_group: QgsLayerTreeGroup,
        oes_group: QgsLayerTreeGroup,
        debug_group: QgsLayerTreeGroup,
        solved_engines: Optional[Dict[str, PlanarControllingOlsEngine]] = None,
    ) -> bool:
        """Create independent future Annex 14 OFS and OES lower envelopes."""
        candidates = list(getattr(self, "_controlling_ols_candidates", []) or [])
        contours = list(getattr(self, "_controlling_ols_contours", []) or [])
        created = False
        for family, output_group in (("OFS", ofs_group), ("OES", oes_group)):
            family_candidates = [
                candidate
                for candidate in candidates
                if candidate.model in {"constant", "axis", "plane", "conical"}
                and str((candidate.metadata or {}).get("annex14_family") or "").upper() == family
            ]
            if not family_candidates:
                QgsMessageLog.logMessage(
                    f"[skip] Controlling {family}: no future Annex 14 planar candidates were registered.",
                    PLUGIN_TAG,
                    Qgis.Info,
                )
                continue
            engine = PlanarControllingOlsEngine(family_candidates)
            if solved_engines is not None:
                solved_engines[family] = engine
            family_debug_group = self._ensure_layer_group(debug_group, f"Annex 14 {family} Controlling")
            if not self._controlling_ols_subphase(
                f"Controlling {family}: preparing candidates and transition boundaries..."
            ):
                return created
            self._create_controlling_candidate_layer(
                icao_code,
                family_debug_group,
                family_candidates,
                internal_name=f"Annex14_{family}_Planar_Candidates_{icao_code}",
                display_name=f"{family} — Planar Candidates",
                style_key=f"Annex 14 Candidate {family}",
            )
            self._create_controlling_transition_layer(
                icao_code,
                family_debug_group,
                engine,
                internal_name=f"Annex14_{family}_Planar_Transitions_{icao_code}",
                display_name=f"{family} — Planar Transitions",
                style_key=f"Annex 14 Transition {family}",
            )
            if not self._controlling_ols_subphase(f"Controlling {family}: writing solved regions..."):
                return created
            region_created = self._create_controlling_region_layer(
                icao_code,
                output_group,
                engine,
                internal_name=f"Annex14_Controlling_{family}_{icao_code}",
                display_name=f"Controlling {family} — Surface",
                style_key=f"Annex 14 Controlling {family}",
                partition_overlaps=True,
            )
            family_surface_ids = {candidate.surface_id for candidate in family_candidates}
            family_contours = [
                contour for contour in contours if contour.surface_id in family_surface_ids
            ]
            if not self._controlling_ols_subphase(f"Controlling {family}: clipping contours..."):
                return region_created or created
            contour_created = self._create_controlling_contour_layer(
                icao_code,
                output_group,
                engine,
                family_contours,
                internal_name=f"Annex14_Controlling_{family}_Contours_{icao_code}",
                display_name=f"Controlling {family} — Contours",
                style_key=f"Annex 14 {family} Contour",
                strict_clip=True,
            )
            created = region_created or contour_created or created
        return created

    def _controlling_ols_diagnostic_group(self, layer_group: QgsLayerTreeGroup) -> QgsLayerTreeGroup:
        """Return the dedicated diagnostic group for non-user-facing solver products."""
        group_name = self.tr(output_structure.DEBUG_DEVELOPMENT)
        if layer_group is not None and layer_group.name() == group_name:
            return layer_group
        return self._ensure_controlling_ols_diagnostic_group(layer_group, group_name) or layer_group

    def _ensure_controlling_ols_diagnostic_group(
        self,
        parent_group: QgsLayerTreeGroup,
        group_name: str,
    ) -> Optional[QgsLayerTreeGroup]:
        """Keep the diagnostic group at the end of generated outputs."""
        if parent_group is None:
            return None

        existing_group = self._find_direct_child_group(parent_group, group_name)
        children = list(parent_group.children())
        target_index = len(children)

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
        internal_name: Optional[str] = None,
        display_name: Optional[str] = None,
        style_key: str = "Default Polygon",
    ) -> bool:
        start_time = time.perf_counter()
        fields = QgsFields(
            [
                QgsField("surface_id", QVariant.String, self.tr("Surface ID"), 160),
                QgsField("surface", QVariant.String, self.tr("Surface Type"), 50),
                QgsField("model", QVariant.String, self.tr("Model"), 30),
                QgsField("elev_min", QVariant.Double, self.tr("Min Elev AMSL"), 12, 3),
                QgsField("elev_max", QVariant.Double, self.tr("Max Elev AMSL"), 12, 3),
                QgsField("vertical_model", QVariant.String, self.tr("Vertical Model"), 40),
                QgsField("height_ref", QVariant.String, self.tr("Height Reference"), 30),
                QgsField("lower_role", QVariant.String, self.tr("Lower Edge Role"), 40),
                QgsField("lower_z_m", QVariant.Double, self.tr("Lower Edge Elev (m)"), 12, 3),
                QgsField("upper_role", QVariant.String, self.tr("Upper Edge Role"), 40),
                QgsField("upper_z_m", QVariant.Double, self.tr("Upper Edge Elev (m)"), 12, 3),
                QgsField("surface_axis", QVariant.String, self.tr("Surface Axis"), 60),
                QgsField("edge_src", QVariant.String, self.tr("Edge Elevation Source"), 80),
            ]
        )
        features: List[QgsFeature] = []
        for candidate in candidates:
            feature = QgsFeature(fields)
            feature.setGeometry(QgsGeometry(candidate.footprint))
            min_elev, max_elev = self._candidate_elevation_range(candidate)
            metadata = candidate.metadata or {}
            feature.setAttributes(
                [
                    candidate.surface_id,
                    candidate.surface_type,
                    candidate.model,
                    min_elev,
                    max_elev,
                    metadata.get("vertical_model"),
                    metadata.get("height_reference"),
                    metadata.get("lower_edge_role"),
                    metadata.get("lower_edge_z_m"),
                    metadata.get("upper_edge_role"),
                    metadata.get("upper_edge_z_m"),
                    metadata.get("surface_axis"),
                    metadata.get("edge_elevation_source"),
                ]
            )
            features.append(feature)

        layer = self._create_and_add_layer(
            "Polygon",
            internal_name or f"OLS_Controlling_Planar_Candidates_{icao_code}",
            display_name or f"{self.tr('OLS')} Controlling Candidate Surfaces {icao_code}",
            fields,
            features,
            output_group,
            style_key,
        )
        if layer is not None:
            QgsMessageLog.logMessage(
                f"[done] Controlling OLS candidates layer: {len(candidates)} surfaces "
                f"({time.perf_counter() - start_time:.2f}s).",
                PLUGIN_TAG,
                Qgis.Info,
            )
            return True
        return False

    def _create_controlling_region_layer(
        self,
        icao_code: str,
        output_group: QgsLayerTreeGroup,
        engine: PlanarControllingOlsEngine,
        internal_name: Optional[str] = None,
        display_name: Optional[str] = None,
        style_key: str = "OLS Controlling Planar Region",
        partition_overlaps: bool = False,
    ) -> bool:
        start_time = time.perf_counter()
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
        if display_name is not None:
            for field in [
                QgsField("family", QVariant.String, self.tr("Family"), 10),
                QgsField("runway", QVariant.String, self.tr("Runway"), 50),
                QgsField("rwy_end", QVariant.String, self.tr("Runway End"), 10),
                QgsField("component", QVariant.String, self.tr("Component"), 80),
                QgsField("ref", QVariant.String, self.tr("Reference"), 120),
                QgsField("plane_a", QVariant.Double, self.tr("Plane A"), 20, 12),
                QgsField("plane_b", QVariant.Double, self.tr("Plane B"), 20, 12),
                QgsField("plane_c", QVariant.Double, self.tr("Plane C"), 20, 5),
            ]:
                fields.append(field)
        features = engine.region_features(fields)
        engine._region_solve_stats["raw_output_union_area_m2"] = self._feature_union_area(features)
        if partition_overlaps:
            features = self._partition_controlling_region_features(features, engine)
            engine._region_solve_stats["partitioned_output_union_area_m2"] = self._feature_union_area(features)
        if display_name is not None:
            candidates_by_id = {candidate.surface_id: candidate for candidate in engine.candidates}
            for feature in features:
                attributes = list(feature.attributes())
                if len(attributes) < fields.count():
                    feature.setAttributes(attributes + [None] * (fields.count() - len(attributes)))
                candidate = candidates_by_id.get(str(feature.attribute("surface_id") or ""))
                metadata = candidate.metadata if candidate is not None else {}
                feature.setAttribute("family", metadata.get("annex14_family"))
                feature.setAttribute("runway", metadata.get("runway"))
                feature.setAttribute("rwy_end", metadata.get("runway_end"))
                feature.setAttribute("component", metadata.get("component"))
                feature.setAttribute("ref", metadata.get("ref"))
                feature.setAttribute("plane_a", metadata.get("plane_a"))
                feature.setAttribute("plane_b", metadata.get("plane_b"))
                feature.setAttribute("plane_c", metadata.get("plane_c"))
        if partition_overlaps:
            features = self._dissolve_coplanar_controlling_regions(features, engine)
            engine._region_solve_stats["dissolved_output_union_area_m2"] = self._feature_union_area(features)
            features = self._repair_final_controlling_partition(features, engine)
        solve_summary = engine.region_solve_timing_summary()
        diagnostics = engine.solver_diagnostics()
        recovery = diagnostics["exceptional_recovery"]
        QgsMessageLog.logMessage(
            "[diagnostics] Controlling OLS solver: "
            f"cells={diagnostics['cells']['total']}, "
            f"unassigned={diagnostics['cells']['unassigned']}, "
            f"refined={diagnostics['cells']['refined']}, "
            f"unresolved={diagnostics['comparisons']['unresolved']}, "
            "recovery_activations="
            f"{sum(1 for value in recovery.values() if isinstance(value, (int, float)) and float(value) > 0.0)}.",
            PLUGIN_TAG,
            Qgis.Info,
        )
        if not features:
            QgsMessageLog.logMessage(
                "[skip] Controlling OLS regions layer: no controlling planar regions were produced "
                f"({time.perf_counter() - start_time:.2f}s).",
                PLUGIN_TAG,
                Qgis.Info,
            )
            debug_log = getattr(self, "_log_dev_debug", None)
            if callable(debug_log):
                debug_log(f"Controlling OLS regions solver details: {solve_summary}", "controlling-ols")
            return False
        feature_count = len(features)
        layer = self._create_and_add_layer(
            "MultiPolygon",
            internal_name or f"OLS_Controlling_Planar_Regions_{icao_code}",
            display_name or f"{self.tr('OLS')} Controlling Regions {icao_code}",
            fields,
            features,
            output_group,
            style_key,
        )
        if layer is not None:
            QgsMessageLog.logMessage(
                f"[done] Controlling OLS regions layer: {feature_count} regions "
                f"({time.perf_counter() - start_time:.2f}s).",
                PLUGIN_TAG,
                Qgis.Info,
            )
            debug_log = getattr(self, "_log_dev_debug", None)
            if callable(debug_log):
                debug_log(f"Controlling OLS regions solver details: {solve_summary}", "controlling-ols")
            return True
        return False

    @staticmethod
    def _feature_union_area(features: Sequence[QgsFeature]) -> float:
        geometries = [
            QgsGeometry(feature.geometry())
            for feature in features
            if feature.geometry() is not None and not feature.geometry().isEmpty()
        ]
        if not geometries:
            return 0.0
        try:
            union = QgsGeometry.unaryUnion(geometries)
            return union.area() if union is not None and not union.isEmpty() else 0.0
        except Exception:
            return 0.0

    def _partition_controlling_region_features(
        self,
        features: List[QgsFeature],
        engine: Optional[PlanarControllingOlsEngine] = None,
    ) -> List[QgsFeature]:
        """Remove tied-region overlaps while preserving the complete envelope domain."""
        partitioned: List[QgsFeature] = []
        assigned = QgsGeometry()
        family_priority = {"OFS": 0, "OES": 1}
        surface_priority = {"Inner Approach": 0, "Approach": 1}
        ordered = sorted(
            features,
            key=lambda feature: (
                family_priority.get(str(feature.attribute("family") or "").strip().upper(), 2),
                surface_priority.get(str(feature.attribute("surface") or ""), 2),
                str(feature.attribute("surface_id") or ""),
            ),
        )
        for feature in ordered:
            geometry = QgsGeometry(feature.geometry())
            if geometry.isNull() or geometry.isEmpty():
                continue
            if not assigned.isNull() and not assigned.isEmpty():
                geometry = geometry.difference(assigned)
            if geometry.isNull() or geometry.isEmpty():
                continue
            if not geometry.isGeosValid():
                if engine is not None:
                    engine._region_solve_stats["partition_make_valid_count"] = (
                        engine._region_solve_stats.get("partition_make_valid_count", 0.0) + 1.0
                    )
                geometry = geometry.makeValid()
            if geometry.isNull() or geometry.isEmpty():
                continue
            feature.setGeometry(geometry)
            feature.setAttribute("region_id", len(partitioned) + 1)
            partitioned.append(feature)
            assigned = (
                QgsGeometry(geometry)
                if assigned.isNull() or assigned.isEmpty()
                else QgsGeometry.unaryUnion([assigned, geometry])
            )
        return partitioned

    def _dissolve_coplanar_controlling_regions(
        self,
        features: List[QgsFeature],
        engine: PlanarControllingOlsEngine,
    ) -> List[QgsFeature]:
        """Dissolve disjoint solved pieces sharing a surface type and elevation plane."""
        candidates_by_id = {candidate.surface_id: candidate for candidate in engine.candidates}
        grouped: Dict[Tuple[object, ...], List[QgsFeature]] = {}
        for feature in features:
            candidate = candidates_by_id.get(str(feature.attribute("surface_id") or ""))
            key = self._controlling_candidate_dissolve_key(candidate, feature)
            grouped.setdefault(key, []).append(feature)

        dissolved: List[QgsFeature] = []
        for group_features in grouped.values():
            geometries = [QgsGeometry(feature.geometry()) for feature in group_features]
            source_area = sum(geometry.area() for geometry in geometries)
            geometry = QgsGeometry.unaryUnion(geometries) if len(geometries) > 1 else QgsGeometry(geometries[0])
            if geometry.isNull() or geometry.isEmpty():
                continue
            if not geometry.isGeosValid():
                engine._region_solve_stats["dissolve_geometry_repair_count"] = (
                    engine._region_solve_stats.get("dissolve_geometry_repair_count", 0.0) + 1.0
                )
                repair_candidates: List[QgsGeometry] = []
                try:
                    repair_candidates.append(geometry.makeValid())
                except Exception:
                    pass
                try:
                    repair_candidates.append(geometry.buffer(0.0, 8))
                except Exception:
                    pass
                try:
                    repair_candidates.append(
                        geometry.snappedToGrid(
                            CONTROLLING_REGION_DISSOLVE_RETRY_GRID_M,
                            CONTROLLING_REGION_DISSOLVE_RETRY_GRID_M,
                        ).buffer(0.0, 8)
                    )
                except Exception:
                    pass
                repair_candidates = [
                    candidate
                    for candidate in repair_candidates
                    if candidate is not None
                    and not candidate.isNull()
                    and not candidate.isEmpty()
                    and candidate.isGeosValid()
                ]
                if repair_candidates:
                    geometry = min(
                        repair_candidates,
                        key=lambda candidate: (
                            abs(candidate.area() - source_area),
                            engine._polygon_part_count(candidate),
                        ),
                    )
            if geometry.isNull() or geometry.isEmpty():
                continue
            try:
                cleaned_geometry = geometry.removeInteriorRings(
                    CONTROLLING_REGION_MIN_INTERIOR_RING_AREA_M2
                )
            except Exception:
                cleaned_geometry = None
            if (
                cleaned_geometry is not None
                and not cleaned_geometry.isNull()
                and not cleaned_geometry.isEmpty()
                and cleaned_geometry.isGeosValid()
            ):
                geometry = cleaned_geometry
            output = QgsFeature(group_features[0])
            output.setGeometry(geometry)
            source_candidate = candidates_by_id.get(str(group_features[0].attribute("surface_id") or ""))
            if source_candidate is not None:
                elev_min, elev_max = engine._geometry_elevation_range(geometry, source_candidate)
                output.setAttribute("elev_min", elev_min)
                output.setAttribute("elev_max", elev_max)
            if len(group_features) > 1:
                source_ids = sorted({str(feature.attribute("surface_id") or "") for feature in group_features})
                components = sorted({str(feature.attribute("component") or "") for feature in group_features})
                runway_ends = sorted({str(feature.attribute("rwy_end") or "") for feature in group_features})
                output.setAttribute("surface_id", "|".join(source_ids)[:160])
                output.setAttribute("component", "|".join(filter(None, components))[:80])
                output.setAttribute("rwy_end", "|".join(filter(None, runway_ends))[:10])
                output.setAttribute("method", "exact_planar_halfplane_coplanar_dissolve")
            dissolved.append(output)
        dissolved.sort(key=lambda feature: str(feature.attribute("surface_id") or ""))
        for region_id, feature in enumerate(dissolved, start=1):
            feature.setAttribute("region_id", region_id)
        return dissolved

    def _controlling_candidate_dissolve_key(
        self,
        candidate: Optional[ControllingOlsCandidate],
        feature: Optional[QgsFeature] = None,
    ) -> Tuple[object, ...]:
        """Return the stable plane key used by Annex 14 output normalisation."""
        metadata = candidate.metadata if candidate is not None else {}
        plane = tuple(metadata.get(name) for name in ("plane_a", "plane_b", "plane_c"))
        if any(value is None for value in plane):
            surface_id = (
                candidate.surface_id
                if candidate is not None
                else feature.attribute("surface_id") if feature is not None else ""
            )
            return ("candidate", str(surface_id or ""))
        surface_type = (
            candidate.surface_type
            if candidate is not None
            else feature.attribute("surface") if feature is not None else ""
        )
        return (
            "plane",
            str(surface_type or ""),
            round(float(plane[0]), 11),
            round(float(plane[1]), 11),
            round(float(plane[2]), 5),
        )

    def _repair_final_controlling_partition(
        self,
        features: List[QgsFeature],
        engine: PlanarControllingOlsEngine,
    ) -> List[QgsFeature]:
        """Close topology gaps introduced by output partitioning and coplanar dissolve."""
        if not features:
            return features

        candidates_by_id = {candidate.surface_id: candidate for candidate in engine.candidates}
        features_by_key: Dict[Tuple[object, ...], QgsFeature] = {}
        for feature in features:
            source_id = str(feature.attribute("surface_id") or "").split("|", 1)[0]
            candidate = candidates_by_id.get(source_id)
            features_by_key[self._controlling_candidate_dissolve_key(candidate, feature)] = feature

        coverage_parts = []
        for candidate in engine.candidates:
            footprint = engine._effective_footprint(candidate)
            if engine._has_polygon_area(footprint):
                coverage_parts.append(footprint)
        solved_parts = [feature.geometry() for feature in features if engine._has_polygon_area(feature.geometry())]
        try:
            coverage = QgsGeometry.unaryUnion(coverage_parts)
            solved = QgsGeometry.unaryUnion(solved_parts)
            gaps = coverage.difference(solved)
        except Exception:
            return features
        if not engine._has_polygon_area(gaps):
            return features

        repaired_count = 0
        repaired_area = 0.0
        for gap in engine._polygon_parts(gaps):
            if gap.area() <= 1e-3:
                continue
            repairs = engine._gap_lower_envelope_parts(gap)
            if not repairs:
                try:
                    point = gap.pointOnSurface().asPoint()
                    result = engine.controlling_candidate_at_xy(QgsPointXY(point.x(), point.y()))
                    candidate = result[0] if result is not None else None
                except Exception:
                    candidate = None
                repairs = [(candidate, gap)] if candidate is not None else []
            for candidate, repair in repairs:
                key = self._controlling_candidate_dissolve_key(candidate)
                target = features_by_key.get(key)
                if target is None or not engine._has_polygon_area(repair):
                    continue
                try:
                    combined = QgsGeometry.unaryUnion([target.geometry(), repair])
                except Exception:
                    combined = None
                if combined is None or combined.isNull() or combined.isEmpty():
                    continue
                try:
                    if not combined.isGeosValid() or combined.validateGeometry():
                        normalized = combined.buffer(0.0, CONTROLLING_REGION_GEOMETRY_REPAIR_SEGMENTS)
                        if normalized is not None and not normalized.isNull() and not normalized.isEmpty():
                            combined = normalized
                except Exception:
                    pass
                target.setGeometry(combined)
                elev_min, elev_max = engine._geometry_elevation_range(combined, candidate)
                target.setAttribute("elev_min", elev_min)
                target.setAttribute("elev_max", elev_max)
                repaired_count += 1
                repaired_area += repair.area()
                surface_key = f"{candidate.surface_type}:{candidate.surface_id}"
                surface_stats = engine._final_partition_repair_by_surface.setdefault(
                    surface_key,
                    {"parts": 0, "area_m2": 0.0},
                )
                surface_stats["parts"] = int(surface_stats["parts"]) + 1
                surface_stats["area_m2"] = float(surface_stats["area_m2"]) + repair.area()

        if repaired_count:
            engine._region_solve_stats["final_partition_repair_part_count"] = (
                engine._region_solve_stats.get("final_partition_repair_part_count", 0.0)
                + float(repaired_count)
            )
            engine._region_solve_stats["final_partition_repair_area_m2"] = (
                engine._region_solve_stats.get("final_partition_repair_area_m2", 0.0)
                + repaired_area
            )
            QgsMessageLog.logMessage(
                f"[repair] Controlling output partition: restored {repaired_area:.6f} m² "
                f"across {repaired_count} lower-envelope gap part(s).",
                PLUGIN_TAG,
                Qgis.Info,
            )
        valid_features = [
            feature
            for feature in features
            if engine._has_polygon_area(feature.geometry())
        ]
        # Geometry normalisation can very slightly expand a repaired boundary.
        # Repartition once so the delivered lower envelope remains exclusive.
        valid_features = self._partition_controlling_region_features(valid_features, engine)
        polygon_features: List[QgsFeature] = []
        for feature in valid_features:
            polygon_parts = engine._polygon_parts(feature.geometry())
            polygons = [part.asPolygon() for part in polygon_parts if part.asPolygon()]
            if not polygons:
                continue
            geometry = QgsGeometry.fromMultiPolygonXY(polygons)
            if geometry is None or geometry.isNull() or geometry.isEmpty():
                continue
            feature.setGeometry(geometry)
            polygon_features.append(feature)
        valid_features = polygon_features
        valid_features.sort(key=lambda feature: str(feature.attribute("surface_id") or ""))
        for region_id, feature in enumerate(valid_features, start=1):
            feature.setAttribute("region_id", region_id)
        return valid_features

    def _create_controlling_transition_layer(
        self,
        icao_code: str,
        output_group: QgsLayerTreeGroup,
        engine: PlanarControllingOlsEngine,
        internal_name: Optional[str] = None,
        display_name: Optional[str] = None,
        style_key: str = "Default Line",
    ) -> bool:
        start_time = time.perf_counter()
        fields = QgsFields(
            [
                QgsField("transition_id", QVariant.String, self.tr("Transition ID"), 160),
                QgsField("surface", QVariant.String, self.tr("Surface"), 50),
                QgsField("elev_min", QVariant.Double, self.tr("Min Elev AMSL"), 12, 3),
                QgsField("elev_max", QVariant.Double, self.tr("Max Elev AMSL"), 12, 3),
                QgsField("adjacent", QVariant.String, self.tr("Adjacent Surfaces"), 254),
                QgsField("method", QVariant.String, self.tr("Method"), 50),
                QgsField("eq_res_max", QVariant.Double, self.tr("Max Equality Residual"), 12, 6),
            ]
        )
        features = engine.region_boundary_features(fields)
        features = self._deduplicate_controlling_transition_features(features)
        if not features:
            QgsMessageLog.logMessage(
                "[skip] Controlling OLS transitions layer: no region boundary transition edges were produced "
                f"({time.perf_counter() - start_time:.2f}s).",
                PLUGIN_TAG,
                Qgis.Info,
            )
            return False
        feature_count = len(features)
        layer = self._create_and_add_layer(
            "LineStringZ",
            internal_name or f"OLS_Controlling_Planar_Transitions_{icao_code}",
            display_name or f"{self.tr('OLS')} Controlling Transition Boundaries {icao_code}",
            fields,
            features,
            output_group,
            style_key,
        )
        if layer is not None:
            QgsMessageLog.logMessage(
                f"[done] Controlling OLS transitions layer: {feature_count} region boundary edges "
                f"({time.perf_counter() - start_time:.2f}s).",
                PLUGIN_TAG,
                Qgis.Info,
            )
            return True
        return False

    def _create_controlling_contour_layer(
        self,
        icao_code: str,
        output_group: QgsLayerTreeGroup,
        engine: PlanarControllingOlsEngine,
        contours: Sequence[ControllingOlsContour],
        internal_name: Optional[str] = None,
        display_name: Optional[str] = None,
        style_key: str = "OLS Controlling Contour",
        strict_clip: bool = False,
    ) -> bool:
        start_time = time.perf_counter()
        if not contours:
            QgsMessageLog.logMessage(
                "[skip] Controlling OLS contours: no source contours were registered; "
                "targeted horizontal transition contours will still be checked "
                f"({time.perf_counter() - start_time:.2f}s).",
                PLUGIN_TAG,
                Qgis.Info,
            )

        region_parts = [
            (candidate, region)
            for candidate, region in engine._controlling_region_geometries()
        ]
        if not region_parts:
            QgsMessageLog.logMessage(
                "[skip] Controlling OLS contours layer: no controlling regions were produced "
                f"({time.perf_counter() - start_time:.2f}s).",
                PLUGIN_TAG,
                Qgis.Info,
            )
            return False

        regions_by_surface_id: Dict[str, List[QgsGeometry]] = {}
        candidates_by_surface_id = {candidate.surface_id: candidate for candidate in engine.candidates}
        regions_by_coplanar_key: Dict[Tuple[object, ...], List[QgsGeometry]] = {}
        for candidate, region in region_parts:
            regions_by_surface_id.setdefault(candidate.surface_id, []).append(region)
            coplanar_key = self._controlling_candidate_dissolve_key(candidate)
            regions_by_coplanar_key.setdefault(coplanar_key, []).append(region)

        fields = QgsFields(
            [
                QgsField("contour_id", QVariant.Int, self.tr("Contour ID"), 10),
                QgsField("surface_id", QVariant.String, self.tr("Surface ID"), 160),
                QgsField("surface", QVariant.String, self.tr("Surface Type"), 50),
                QgsField("contour_elev_am", QVariant.Double, self.tr("Contour Elev AMSL"), 12, 3),
                QgsField("source_layer", QVariant.String, self.tr("Source Layer"), 80),
                QgsField("method", QVariant.String, self.tr("Method"), 50),
                QgsField("contour_class", QVariant.String, self.tr("Contour Class"), 20),
                QgsField("contour_interval_m", QVariant.Double, self.tr("Intermediate Interval (m)"), 10, 2),
                QgsField("primary_interval_m", QVariant.Double, self.tr("Primary Interval (m)"), 10, 2),
            ]
        )
        features: List[QgsFeature] = []
        contour_id = 1
        for contour in contours:
            contour_candidate = candidates_by_surface_id.get(contour.surface_id)
            if contour_candidate is not None:
                matching_regions = regions_by_coplanar_key.get(
                    self._controlling_candidate_dissolve_key(contour_candidate),
                    [],
                )
            else:
                matching_regions = regions_by_surface_id.get(contour.surface_id, [])
            if not matching_regions:
                continue
            clip_geometry = self._controlling_contour_clip_geometry(
                contour.surface_type,
                matching_regions,
                strict=strict_clip,
            )
            if clip_geometry is None or clip_geometry.isEmpty():
                continue
            clipped_line_parts: List[List[QgsPointXY]] = []
            seen_part_keys = set()
            used_tolerant_clip = False

            def _add_clipped_parts(geometry: Optional[QgsGeometry]) -> None:
                if geometry is None or geometry.isEmpty():
                    return
                for line_points in engine._line_parts(geometry):
                    if len(line_points) < 2:
                        continue
                    part_key = self._controlling_contour_part_key(line_points)
                    if part_key in seen_part_keys:
                        continue
                    seen_part_keys.add(part_key)
                    clipped_line_parts.append(line_points)

            try:
                clipped = contour.geometry.intersection(clip_geometry)
            except Exception:
                clipped = None
            _add_clipped_parts(clipped)

            if not strict_clip and contour.surface_type in {"Approach", "Conical", "TOCS", "Transitional"}:
                try:
                    tolerant_clip_geometry = clip_geometry.buffer(
                        CONTROLLING_CONTOUR_CLIP_TOLERANCE_M,
                        CONTROLLING_CONTOUR_CLIP_BUFFER_SEGMENTS,
                    )
                except Exception:
                    tolerant_clip_geometry = None
                if tolerant_clip_geometry is not None and not tolerant_clip_geometry.isEmpty():
                    try:
                        tolerant_clipped = contour.geometry.intersection(tolerant_clip_geometry)
                    except Exception:
                        tolerant_clipped = None
                    before_tolerant_count = len(clipped_line_parts)
                    _add_clipped_parts(tolerant_clipped)
                    used_tolerant_clip = len(clipped_line_parts) > before_tolerant_count
            method = "clip_to_controlling_region_tolerant" if used_tolerant_clip else "clip_to_controlling_region"
            line_geometry = self._controlling_contour_geometry_from_parts(clipped_line_parts)
            if line_geometry is None or line_geometry.isEmpty():
                continue
            feature = QgsFeature(fields)
            feature.setGeometry(line_geometry)
            feature.setAttributes(
                [
                    contour_id,
                    contour.surface_id,
                    contour.surface_type,
                    contour.contour_elevation_m,
                    contour.source_layer,
                    method,
                    contour.contour_class,
                    contour.contour_interval_m,
                    contour.primary_interval_m,
                ]
            )
            features.append(feature)
            contour_id += 1

        transition_fields = QgsFields(
            [
                QgsField("transition_id", QVariant.String, self.tr("Transition ID"), 160),
                QgsField("surface", QVariant.String, self.tr("Surface"), 50),
                QgsField("elev_min", QVariant.Double, self.tr("Min Elev AMSL"), 12, 3),
                QgsField("elev_max", QVariant.Double, self.tr("Max Elev AMSL"), 12, 3),
                QgsField("adjacent", QVariant.String, self.tr("Adjacent Surfaces"), 254),
                QgsField("method", QVariant.String, self.tr("Method"), 50),
                QgsField("eq_res_max", QVariant.Double, self.tr("Max Equality Residual"), 12, 6),
            ]
        )
        surface_type_by_id = {candidate.surface_id: candidate.surface_type for candidate in engine.candidates}
        targeted_pairs = {
            frozenset(("Approach", "TOCS")),
            frozenset(("TOCS", "OHS")),
        }
        seen_transition_contours = set()
        transition_features = self._deduplicate_controlling_transition_features(
            engine.region_boundary_features(transition_fields)
        )
        for transition_feature in transition_features:
            adjacent = str(transition_feature.attribute("adjacent") or "")
            adjacent_ids = adjacent.split("|")
            if len(adjacent_ids) != 2:
                continue
            adjacent_surface_types = [
                surface_type_by_id.get(surface_id)
                for surface_id in adjacent_ids
            ]
            if None in adjacent_surface_types:
                continue
            if frozenset(adjacent_surface_types) not in targeted_pairs:
                continue
            try:
                elev_min = float(transition_feature.attribute("elev_min"))
                elev_max = float(transition_feature.attribute("elev_max"))
            except (TypeError, ValueError):
                continue
            if not math.isfinite(elev_min) or not math.isfinite(elev_max):
                continue
            if abs(elev_max - elev_min) > 0.01:
                continue
            geometry = transition_feature.geometry()
            if geometry is None or geometry.isEmpty():
                continue
            line_geometry = self._controlling_contour_geometry_from_parts(engine._line_parts(geometry))
            if line_geometry is None or line_geometry.isEmpty():
                continue
            contour_elevation = (elev_min + elev_max) / 2.0
            try:
                geometry_key = line_geometry.asWkt(3)
            except Exception:
                geometry_key = str(id(line_geometry))
            transition_key = (adjacent, int(round(contour_elevation * 1000.0)), geometry_key)
            if transition_key in seen_transition_contours:
                continue
            seen_transition_contours.add(transition_key)
            feature = QgsFeature(fields)
            feature.setGeometry(line_geometry)
            feature.setAttributes(
                [
                    contour_id,
                    adjacent[:160],
                    "Transition",
                    contour_elevation,
                    "OLS Controlling Planar Transitions",
                    "targeted_horizontal_transition",
                    "transition",
                    None,
                    None,
                ]
            )
            features.append(feature)
            contour_id += 1

        if not features:
            QgsMessageLog.logMessage(
                "[skip] Controlling OLS contours layer: registered contours did not intersect matching regions "
                "and no targeted horizontal transition contours were produced "
                f"({time.perf_counter() - start_time:.2f}s).",
                PLUGIN_TAG,
                Qgis.Info,
            )
            return False

        feature_count = len(features)
        layer = self._create_and_add_layer(
            "MultiLineString",
            internal_name or f"OLS_Controlling_Contours_{icao_code}",
            display_name or f"{self.tr('OLS')} Controlling Contours {icao_code}",
            fields,
            features,
            output_group,
            style_key,
        )
        if layer is not None:
            QgsMessageLog.logMessage(
                f"[done] Controlling OLS contours layer: {feature_count} contour features "
                f"({time.perf_counter() - start_time:.2f}s).",
                PLUGIN_TAG,
                Qgis.Info,
            )
            return True
        return False

    def _controlling_contour_clip_geometry(
        self,
        surface_type: str,
        regions: Sequence[QgsGeometry],
        strict: bool = False,
    ) -> Optional[QgsGeometry]:
        valid_regions = [QgsGeometry(region) for region in regions if region is not None and not region.isEmpty()]
        if not valid_regions:
            return None
        try:
            clip_geometry = QgsGeometry.unaryUnion(valid_regions) if len(valid_regions) > 1 else valid_regions[0]
        except Exception:
            clip_geometry = valid_regions[0]
        if clip_geometry is None or clip_geometry.isEmpty():
            return None
        if strict:
            try:
                buffered = clip_geometry.buffer(
                    CONTROLLING_CONTOUR_STRICT_BOUNDARY_TOLERANCE_M,
                    CONTROLLING_CONTOUR_CLIP_BUFFER_SEGMENTS,
                )
                if buffered is not None and not buffered.isEmpty():
                    return buffered
            except Exception:
                pass
        if not strict and surface_type == "Transitional":
            try:
                buffered = clip_geometry.buffer(CONTROLLING_CONTOUR_CLIP_TOLERANCE_M, CONTROLLING_CONTOUR_CLIP_BUFFER_SEGMENTS)
                if buffered is not None and not buffered.isEmpty():
                    return buffered
            except Exception:
                pass
        return clip_geometry

    def _controlling_contour_geometry_from_parts(
        self,
        line_parts: Sequence[Sequence[QgsPointXY]],
    ) -> Optional[QgsGeometry]:
        valid_parts = [list(part) for part in line_parts if len(part) >= 2]
        if not valid_parts:
            return None
        try:
            return QgsGeometry.fromMultiPolylineXY(valid_parts)
        except Exception:
            if len(valid_parts) == 1:
                return QgsGeometry.fromPolylineXY(valid_parts[0])
        return None

    def _controlling_contour_part_key(self, line_points: Sequence[QgsPointXY]) -> Tuple[Tuple[int, int], ...]:
        rounded_points = tuple((int(round(point.x() * 1000.0)), int(round(point.y() * 1000.0))) for point in line_points)
        reversed_points = tuple(reversed(rounded_points))
        return rounded_points if rounded_points <= reversed_points else reversed_points

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

    def _controlling_ols_subphase(self, message: str) -> bool:
        """Report an internal OLS phase and return false after a queued cancellation."""
        status = getattr(self, "_set_processing_status", None)
        if callable(status):
            status(self.tr(message))
        cancelled = getattr(self, "_processing_cancel_requested", None)
        return not (callable(cancelled) and cancelled())
