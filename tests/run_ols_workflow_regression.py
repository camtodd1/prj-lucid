"""Explicit QGIS 4 regression and benchmark runner for complete OLS workflows."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import statistics
import sys
import time
from collections import defaultdict
from contextlib import ExitStack
from pathlib import Path
from typing import Dict, Iterable, List, Optional
from unittest.mock import patch

from qgis.PyQt.QtCore import QCoreApplication
from qgis.core import (
    Qgis,
    QgsApplication,
    QgsCoordinateReferenceSystem,
    QgsGeometry,
    QgsMessageLog,
    QgsPointXY,
    QgsProject,
)


FIXTURE_DIR = Path(__file__).parent / "fixtures" / "ols"
MANIFEST_PATH = FIXTURE_DIR / "manifest.json"
MOS139_LOCK_PATH = FIXTURE_DIR / "mos139_controlling_lock_qgis4_2026-07-12.json"


class _MessageBar:
    def __init__(self):
        self.messages: List[List[str]] = []

    def pushMessage(self, *args, **_kwargs):
        self.messages.append([str(value) for value in args])


class _Iface:
    def __init__(self):
        self.bar = _MessageBar()

    def messageBar(self):
        return self.bar

    def mainWindow(self):
        return None


def _geometry_union(geometries: Iterable[QgsGeometry]) -> QgsGeometry:
    valid = [
        QgsGeometry(geometry)
        for geometry in geometries
        if geometry is not None and not geometry.isEmpty()
    ]
    return QgsGeometry.unaryUnion(valid) if valid else QgsGeometry()


def _area(geometry: Optional[QgsGeometry]) -> float:
    return 0.0 if geometry is None or geometry.isEmpty() else geometry.area()


def _engine_lock_signature(engine) -> Dict[str, object]:
    """Fingerprint exact controller identity and geometry for a locked ruleset."""
    records = []
    controller_ids = []
    total_area = 0.0
    for candidate, geometry in engine._controlling_region_geometries():
        controller_ids.append(candidate.surface_id)
        total_area += geometry.area()
        record_hash = hashlib.sha256()
        record_hash.update(candidate.surface_id.encode("utf-8"))
        record_hash.update(b"\0")
        record_hash.update(bytes(geometry.asWkb()))
        records.append(record_hash.hexdigest())
    return {
        "regions": len(records),
        "controller_ids_digest": hashlib.sha256(
            "\0".join(sorted(controller_ids)).encode("utf-8")
        ).hexdigest(),
        "area_m2": total_area,
        "geometry_digest": hashlib.sha256(
            "".join(sorted(records)).encode("ascii")
        ).hexdigest(),
    }


def _axis_conical_transition_metrics(engine) -> Dict[str, object]:
    """Measure equality residual, analytic deviation, and visible line kinks."""
    candidates = {candidate.surface_id: candidate for candidate in engine.candidates}
    feature_count = 0
    pair_ids = set()
    vertex_count = 0
    total_length_m = 0.0
    equality_residuals = []
    analytic_deviations = []
    shared_elevations = []
    turn_angles = []
    curvatures_per_m = []
    curvature_changes_per_m2 = []
    transition_parts_by_pair = defaultdict(list)
    transition_segment_counts = defaultdict(int)
    short_component_count = 0
    reversal_count = 0

    def _boundary(geometry):
        lines = [
            QgsGeometry.fromPolylineXY(points)
            for points in engine._polygon_boundary_parts(geometry)
            if len(points) >= 2
        ]
        if not lines:
            return QgsGeometry()
        return QgsGeometry.unaryUnion(lines) if len(lines) > 1 else lines[0]

    boundary_records = engine._region_boundary_records()
    has_projected_axis_conical_output = any(
        len(attributes) > 5 and attributes[5] == "projected_axis_conical_transition"
        for _geometry, attributes in boundary_records
    )
    for geometry, attributes in boundary_records:
        if (
            has_projected_axis_conical_output
            and (len(attributes) <= 5 or attributes[5] != "projected_axis_conical_transition")
        ):
            continue
        pair_id = str(attributes[4] or "")
        surface_ids = pair_id.split("|")
        if len(surface_ids) != 2:
            continue
        first = candidates.get(surface_ids[0])
        second = candidates.get(surface_ids[1])
        if first is None or second is None or {first.model, second.model} != {"axis", "conical"}:
            continue
        axis = first if first.model == "axis" else second
        conical = first if first.model == "conical" else second
        if axis.surface_type not in {"Approach", "TOCS"}:
            continue

        for output_points in engine._line_parts(geometry):
            if len(output_points) < 2:
                continue
            output_part = QgsGeometry.fromPolylineXY(output_points)
            transition_parts_by_pair[pair_id].append(output_part)
            if output_part.length() < 1.0:
                short_component_count += 1
            for start_point, end_point in zip(output_points[:-1], output_points[1:]):
                segment = tuple(
                    sorted(
                        (
                            (round(start_point.x(), 3), round(start_point.y(), 3)),
                            (round(end_point.x(), 3), round(end_point.y(), 3)),
                        )
                    )
                )
                transition_segment_counts[(pair_id, segment)] += 1
            for previous, current, following in zip(
                output_points[:-2], output_points[1:-1], output_points[2:]
            ):
                first_dx = current.x() - previous.x()
                first_dy = current.y() - previous.y()
                second_dx = following.x() - current.x()
                second_dy = following.y() - current.y()
                denominator = math.hypot(first_dx, first_dy) * math.hypot(second_dx, second_dy)
                if denominator <= 1e-12:
                    continue
                cosine = max(
                    -1.0,
                    min(1.0, ((first_dx * second_dx) + (first_dy * second_dy)) / denominator),
                )
                if math.degrees(math.acos(cosine)) >= 150.0:
                    reversal_count += 1

        axis_boundary = _boundary(axis.footprint)
        conical_boundary = _boundary(conical.footprint)
        interior_parts = []

        def _equality_residual(point_xy):
            axis_z = axis.elevation_at_xy(point_xy)
            conical_z = conical.elevation_at_xy(point_xy)
            if axis_z is None or conical_z is None:
                return None
            return abs(float(axis_z) - float(conical_z))

        for points in engine._line_parts(geometry):
            current_points = []
            for start_point, end_point in zip(points[:-1], points[1:]):
                segment = QgsGeometry.fromPolylineXY([start_point, end_point])
                midpoint = segment.interpolate(segment.length() / 2.0)
                if midpoint is None or midpoint.isEmpty():
                    qualifies = False
                else:
                    midpoint_point = midpoint.asPoint()
                    midpoint_xy = QgsPointXY(midpoint_point.x(), midpoint_point.y())
                    residuals = [
                        _equality_residual(start_point),
                        _equality_residual(midpoint_xy),
                        _equality_residual(end_point),
                    ]
                    qualifies = (
                        axis_boundary.distance(midpoint) > 0.5
                        and conical_boundary.distance(midpoint) > 0.5
                        and all(residual is not None and residual <= 0.5 for residual in residuals)
                    )
                if qualifies:
                    if not current_points:
                        current_points.append(start_point)
                    current_points.append(end_point)
                elif len(current_points) >= 2:
                    interior_parts.append(
                        (QgsGeometry.fromPolylineXY(current_points), current_points)
                    )
                    current_points = []
                else:
                    current_points = []
            if len(current_points) >= 2:
                interior_parts.append((QgsGeometry.fromPolylineXY(current_points), current_points))
        if not interior_parts:
            continue

        feature_count += len(interior_parts)
        pair_ids.add(pair_id)
        total_length_m += sum(part.length() for part, _points in interior_parts)
        vertex_count += sum(len(points) for _part, points in interior_parts)
        for _part, points in interior_parts:
            for previous, current, following in zip(points[:-2], points[1:-1], points[2:]):
                first_dx = current.x() - previous.x()
                first_dy = current.y() - previous.y()
                second_dx = following.x() - current.x()
                second_dy = following.y() - current.y()
                denominator = math.hypot(first_dx, first_dy) * math.hypot(second_dx, second_dy)
                if denominator <= 1e-12:
                    continue
                cosine = max(
                    -1.0,
                    min(1.0, ((first_dx * second_dx) + (first_dy * second_dy)) / denominator),
                )
                turn_angles.append(math.degrees(math.acos(cosine)))

            part_length = _part.length()
            if part_length <= 10.0:
                continue
            sample_spacing_m = 5.0
            sample_count = max(2, int(math.ceil(part_length / sample_spacing_m)))
            sampled_points = []
            for sample_index in range(sample_count + 1):
                point_geometry = _part.interpolate(
                    part_length * sample_index / sample_count
                )
                if point_geometry is None or point_geometry.isEmpty():
                    continue
                point = point_geometry.asPoint()
                sampled_points.append(QgsPointXY(point.x(), point.y()))
            part_curvatures = []
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
                if local_spacing_m <= 1e-9:
                    continue
                curvature = heading_change / local_spacing_m
                part_curvatures.append(curvature)
                curvatures_per_m.append(curvature)
            for first_curvature, second_curvature in zip(
                part_curvatures[:-1],
                part_curvatures[1:],
            ):
                curvature_changes_per_m2.append(
                    (second_curvature - first_curvature) / sample_spacing_m
                )

        try:
            overlap = axis.footprint.intersection(conical.footprint)
            analytic = engine._axis_conical_transition_curve(
                engine._axis_model(axis),
                engine._conical_model(conical),
                overlap,
            )
        except Exception:
            analytic = None

        for part, _points in interior_parts:
            try:
                sampled_geometry = part.densifyByDistance(5.0)
            except Exception:
                sampled_geometry = part
            sampled_parts = engine._line_parts(sampled_geometry)
            if not sampled_parts:
                continue
            points = sampled_parts[0]
            for point_xy in points:
                axis_z = axis.elevation_at_xy(point_xy)
                conical_z = conical.elevation_at_xy(point_xy)
                if axis_z is None or conical_z is None:
                    continue
                if not math.isfinite(axis_z) or not math.isfinite(conical_z):
                    continue
                equality_residuals.append(abs(float(axis_z) - float(conical_z)))
                shared_elevations.append((float(axis_z) + float(conical_z)) / 2.0)
                if analytic is not None and not analytic.isEmpty():
                    analytic_deviations.append(
                        analytic.distance(QgsGeometry.fromPointXY(point_xy))
                    )

    def _rms(values):
        return math.sqrt(sum(value * value for value in values) / len(values)) if values else None

    topology_excess_length_m = 0.0
    for parts in transition_parts_by_pair.values():
        original_length = sum(part.length() for part in parts)
        try:
            linework = QgsGeometry.unaryUnion(parts) if len(parts) > 1 else parts[0]
        except Exception:
            linework = parts[0]
        cleaned_length = sum(
            sum(start.distance(end) for start, end in zip(points[:-1], points[1:]))
            for points in engine._topology_clean_transition_line_parts(linework)
        )
        topology_excess_length_m += max(0.0, original_length - cleaned_length)
    duplicate_segment_count = sum(
        count - 1 for count in transition_segment_counts.values() if count > 1
    )

    return {
        "features": feature_count,
        "pairs": len(pair_ids),
        "vertices": vertex_count,
        "length_m": total_length_m,
        "sample_points": len(equality_residuals),
        "shared_elevation_min_m": min(shared_elevations) if shared_elevations else None,
        "shared_elevation_max_m": max(shared_elevations) if shared_elevations else None,
        "shared_elevation_range_m": (
            max(shared_elevations) - min(shared_elevations) if shared_elevations else None
        ),
        "maximum_equality_residual_m": max(equality_residuals) if equality_residuals else None,
        "rms_equality_residual_m": _rms(equality_residuals),
        "maximum_analytic_deviation_m": max(analytic_deviations) if analytic_deviations else None,
        "rms_analytic_deviation_m": _rms(analytic_deviations),
        "maximum_vertex_turn_degrees": max(turn_angles) if turn_angles else None,
        "rms_vertex_turn_degrees": _rms(turn_angles),
        "maximum_abs_curvature_per_m": (
            max(abs(value) for value in curvatures_per_m)
            if curvatures_per_m
            else None
        ),
        "rms_curvature_per_m": _rms(curvatures_per_m),
        "maximum_abs_curvature_change_per_m2": (
            max(abs(value) for value in curvature_changes_per_m2)
            if curvature_changes_per_m2
            else None
        ),
        "rms_curvature_change_per_m2": _rms(curvature_changes_per_m2),
        "reversal_count": reversal_count,
        "duplicate_segment_count": duplicate_segment_count,
        "short_component_count": short_component_count,
        "topology_excess_length_m": topology_excess_length_m,
    }


def _comparison_metrics(engine, result) -> Dict[str, object]:
    baseline_regions = engine.baseline_engine._controlling_region_geometries()
    future_regions = engine.future_engine._controlling_region_geometries()
    baseline_union = _geometry_union(geometry for _candidate, geometry in baseline_regions)
    future_union = _geometry_union(geometry for _candidate, geometry in future_regions)
    common_domain = baseline_union.intersection(future_union)
    change_unions = {
        change: _geometry_union(geometry for _baseline, _future, geometry in result[change])
        for change in ("gain", "loss", "no_change")
    }
    classified_union = _geometry_union(change_unions.values())
    unclassified = common_domain.difference(classified_union)
    unclassified_parts = []
    for part in engine.baseline_engine._polygon_parts(unclassified):
        if part.area() <= 1e-3:
            continue
        point = part.pointOnSurface().asPoint()
        point_xy = QgsPointXY(point.x(), point.y())
        baseline_controller = engine.baseline_engine.controlling_candidate_at_xy(point_xy)
        future_controller = engine.future_engine.controlling_candidate_at_xy(point_xy)
        delta_min = delta_max = delta_sample = None
        if baseline_controller is not None and future_controller is not None:
            delta_min, delta_max, delta_sample = engine.delta_range(
                part,
                baseline_controller[0],
                future_controller[0],
            )
        affine_delta = None
        if baseline_controller is not None and future_controller is not None:
            baseline_plane = engine._candidate_affine_coefficients(baseline_controller[0])
            future_plane = engine._candidate_affine_coefficients(future_controller[0])
            if baseline_plane is not None and future_plane is not None:
                affine_delta = sum(
                    (future_plane[index] - baseline_plane[index]) * value
                    for index, value in enumerate((point_xy.x(), point_xy.y(), 1.0))
                )
        bounds = part.boundingBox()
        unclassified_parts.append(
            {
                "area_m2": part.area(),
                "bbox": [
                    bounds.xMinimum(),
                    bounds.yMinimum(),
                    bounds.xMaximum(),
                    bounds.yMaximum(),
                ],
                "point": [point_xy.x(), point_xy.y()],
                "baseline_surface_id": (
                    baseline_controller[0].surface_id if baseline_controller is not None else None
                ),
                "future_surface_id": (
                    future_controller[0].surface_id if future_controller is not None else None
                ),
                "delta_min_m": delta_min,
                "delta_max_m": delta_max,
                "delta_sample_m": delta_sample,
                "affine_delta_at_sample_m": affine_delta,
            }
        )
    feature_area_sum = sum(
        _area(geometry)
        for change in ("gain", "loss", "no_change")
        for _baseline, _future, geometry in result[change]
    )
    family = next(
        (
            str((candidate.metadata or {}).get("annex14_family") or "").upper()
            for candidate in (
                list(engine.future_engine.candidates)
                + list(engine.baseline_engine.candidates)
            )
            if (candidate.metadata or {}).get("annex14_family")
        ),
        "OLS",
    )
    no_change_parts = []
    for baseline, future, geometry in result["no_change"]:
        delta_min, delta_max, delta_sample = engine.delta_range(
            geometry,
            baseline,
            future,
            "no_change",
        )
        perimeter = geometry.length()
        no_change_parts.append(
            {
                "area_m2": _area(geometry),
                "strip_width_proxy_m": (
                    (2.0 * _area(geometry) / perimeter) if perimeter > 0.0 else None
                ),
                "delta_min_m": delta_min,
                "delta_max_m": delta_max,
                "delta_sample_m": delta_sample,
                "baseline_surface_id": baseline.surface_id,
                "future_surface_id": future.surface_id,
            }
        )
    return {
        "family": family,
        "baseline_regions": len(baseline_regions),
        "baseline_invalid_regions": sum(
            1 for _candidate, geometry in baseline_regions if not geometry.isGeosValid()
        ),
        "future_regions": len(future_regions),
        "future_invalid_regions": sum(
            1 for _candidate, geometry in future_regions if not geometry.isGeosValid()
        ),
        "common_domain_area_m2": _area(common_domain),
        "classified_union_area_m2": _area(classified_union),
        "classified_overlap_area_m2": max(0.0, feature_area_sum - _area(classified_union)),
        "unclassified_common_area_m2": _area(unclassified),
        "unclassified_parts": sorted(
            unclassified_parts,
            key=lambda item: item["area_m2"],
            reverse=True,
        )[:20],
        "classified_outside_common_area_m2": _area(classified_union.difference(common_domain)),
        "gain_loss_overlap_m2": _area(change_unions["gain"].intersection(change_unions["loss"])),
        "gain_no_change_overlap_m2": _area(change_unions["gain"].intersection(change_unions["no_change"])),
        "loss_no_change_overlap_m2": _area(change_unions["loss"].intersection(change_unions["no_change"])),
        "feature_counts": {change: len(result[change]) for change in result},
        "no_change_parts": sorted(
            no_change_parts,
            key=lambda item: item["area_m2"],
        ),
    }


def _layer_metrics(project: QgsProject) -> Dict[str, object]:
    style_counts: Dict[str, int] = defaultdict(int)
    styles_to_geometries: Dict[str, List[QgsGeometry]] = defaultdict(list)
    invalid = 0
    empty = 0
    comparison_ids: List[str] = []
    layer_count = 0
    feature_count = 0
    deterministic_records = []
    controlling_region_layers = []
    for node in project.layerTreeRoot().findLayers():
        layer = node.layer()
        if layer is None:
            continue
        layer_count += 1
        style_key = str(layer.customProperty("safeguarding_style_key") or "")
        fields = layer.fields().names()
        layer_regions = []
        for feature in layer.getFeatures():
            feature_count += 1
            geometry = feature.geometry()
            if geometry is None or geometry.isNull() or geometry.isEmpty():
                empty += 1
                continue
            if layer.geometryType() == Qgis.GeometryType.Polygon and not geometry.isGeosValid():
                invalid += 1
            if style_key:
                style_counts[style_key] += 1
                styles_to_geometries[style_key].append(QgsGeometry(geometry))
            if "comparison_id" in fields:
                comparison_id = str(feature.attribute("comparison_id") or "")
                if comparison_id:
                    comparison_ids.append(comparison_id)
            if "surface_id" in fields or "comparison_id" in fields:
                identifiers = tuple(
                    str(feature.attribute(name) or "")
                    for name in ("surface_id", "comparison_id", "region_id")
                    if name in fields
                )
                record_hash = hashlib.sha256()
                record_hash.update(style_key.encode("utf-8"))
                record_hash.update(b"\0")
                record_hash.update("\0".join(identifiers).encode("utf-8"))
                record_hash.update(b"\0")
                record_hash.update(bytes(geometry.asWkb()))
                deterministic_records.append(record_hash.hexdigest())
            if "region_id" in fields and "surface" in fields:
                layer_regions.append((
                    int(feature.attribute("region_id") or 0),
                    str(feature.attribute("surface") or ""),
                    str(feature.attribute("surface_id") or ""),
                    QgsGeometry(geometry),
                ))

        if layer_regions:
            overlap_pairs = []
            overlap_area = 0.0
            for index, first in enumerate(layer_regions):
                for second in layer_regions[index + 1 :]:
                    if not first[3].boundingBox().intersects(second[3].boundingBox()):
                        continue
                    overlap = first[3].intersection(second[3])
                    area = _area(overlap)
                    if area <= 1e-3:
                        continue
                    overlap_area += area
                    overlap_pairs.append({
                        "first_region_id": first[0],
                        "first_surface": first[1],
                        "first_surface_id": first[2],
                        "second_region_id": second[0],
                        "second_surface": second[1],
                        "second_surface_id": second[2],
                        "area_m2": area,
                    })
            controlling_region_layers.append({
                "layer": layer.name(),
                "regions": len(layer_regions),
                "overlap_area_m2": overlap_area,
                "overlap_pairs": overlap_pairs,
            })

    controlling = {}
    for family in ("OFS", "OES"):
        candidate_style = f"Annex 14 Candidate {family}"
        controlling_style = f"Annex 14 Controlling {family}"
        candidate_union = _geometry_union(styles_to_geometries[candidate_style])
        controlling_geometries = styles_to_geometries[controlling_style]
        controlling_union = _geometry_union(controlling_geometries)
        if candidate_union.isEmpty():
            coverage_difference = QgsGeometry(controlling_union)
        elif controlling_union.isEmpty():
            coverage_difference = QgsGeometry(candidate_union)
        else:
            coverage_difference = candidate_union.symDifference(controlling_union)
        controlling[family] = {
            "candidate_area_m2": _area(candidate_union),
            "controlling_area_m2": _area(controlling_union),
            "coverage_difference_m2": _area(coverage_difference),
            "region_overlap_m2": max(
                0.0,
                sum(_area(geometry) for geometry in controlling_geometries) - _area(controlling_union),
            ),
        }

    return {
        "layers": layer_count,
        "features": feature_count,
        "invalid_geometries": invalid,
        "empty_geometries": empty,
        "style_feature_counts": dict(sorted(style_counts.items())),
        "comparison_ids": len(comparison_ids),
        "duplicate_comparison_ids": len(comparison_ids) - len(set(comparison_ids)),
        "determinism_digest": hashlib.sha256(
            "".join(sorted(deterministic_records)).encode("ascii")
        ).hexdigest(),
        "controlling": controlling,
        "controlling_region_layers": controlling_region_layers,
    }


def _case_failures(case, manifest, comparisons, layers) -> List[str]:
    tolerances = manifest["accuracy_tolerances"]
    failures: List[str] = []
    if int(case.get("runway_count", -1)) != int(case["payload_runway_count"]):
        failures.append("fixture runway count does not match manifest")
    if layers["invalid_geometries"] > tolerances["maximum_invalid_geometries"]:
        failures.append(f"{layers['invalid_geometries']} invalid geometries")
    if layers["empty_geometries"] > tolerances["maximum_empty_geometries"]:
        failures.append(f"{layers['empty_geometries']} empty geometries")
    if layers["duplicate_comparison_ids"]:
        failures.append(f"{layers['duplicate_comparison_ids']} duplicate comparison IDs")
    maximum_region_overlap_m2 = float(case.get("maximum_region_overlap_m2", 1e-3))
    for region_layer in layers.get("controlling_region_layers", []):
        if float(region_layer["overlap_area_m2"]) > maximum_region_overlap_m2:
            failures.append(
                f"{region_layer['layer']} has {region_layer['overlap_area_m2']:.6f} m2 "
                "of cross-controller overlap"
            )
    expected_comparison_families = set(
        case.get("expected_comparison_families", ["OFS", "OES"])
    )
    if set(comparisons) != expected_comparison_families:
        failures.append(
            f"comparison families were {sorted(comparisons)}; "
            f"expected {sorted(expected_comparison_families)}"
        )

    for family, metrics in comparisons.items():
        area_tolerance = max(
            float(tolerances["minimum_area_m2"]),
            float(metrics["common_domain_area_m2"]) * float(tolerances["relative_area"]),
        )
        for key in (
            "classified_overlap_area_m2",
            "unclassified_common_area_m2",
            "classified_outside_common_area_m2",
            "gain_loss_overlap_m2",
            "gain_no_change_overlap_m2",
            "loss_no_change_overlap_m2",
        ):
            if float(metrics[key]) > area_tolerance:
                failures.append(f"{family} {key}={metrics[key]:.6f} m2 exceeds {area_tolerance:.6f} m2")

    for family, metrics in layers["controlling"].items():
        area_tolerance = max(
            float(tolerances["minimum_area_m2"]),
            float(metrics["candidate_area_m2"]) * 1e-7,
        )
        if float(metrics["candidate_area_m2"]) > 0.0 and float(metrics["controlling_area_m2"]) <= 0.0:
            failures.append(f"{family} controlling output is missing")
        elif float(metrics["coverage_difference_m2"]) > area_tolerance:
            failures.append(f"{family} controlling coverage differs by {metrics['coverage_difference_m2']:.6f} m2")
        if float(metrics["region_overlap_m2"]) > area_tolerance:
            failures.append(f"{family} controlling regions overlap by {metrics['region_overlap_m2']:.6f} m2")
    return failures


def _run_case(
    case, manifest, builder_cls, dialog_cls, controlling_cls, comparison_cls,
    production_gates=False,
):
    fixture_path = FIXTURE_DIR / case["file"]
    payload = json.loads(fixture_path.read_text(encoding="utf-8"))
    case = {**case, "payload_runway_count": len(payload.get("runways", []))}
    project = QgsProject.instance()
    project.clear()
    project.setCrs(QgsCoordinateReferenceSystem(case["project_crs"]))
    dialog = dialog_cls()
    dialog._runtime_test_context = {
        "test_case_id": fixture_path.stem,
        "test_case_name": case["description"],
        "input_filename": fixture_path.name,
        "runway_configuration": case["runway_configuration"],
    }
    if hasattr(dialog, "_airport_lookup_timer"):
        dialog._airport_lookup_timer.stop()
    dialog._apply_loaded_payload(payload)
    QCoreApplication.processEvents()
    if hasattr(dialog, "_airport_lookup_timer"):
        dialog._airport_lookup_timer.stop()
    if dialog.get_all_input_data() is None:
        raise RuntimeError(f"{case['file']} failed dialog validation")

    stage_totals = defaultdict(lambda: {"calls": 0, "seconds": 0.0})
    comparison_results = {}
    engine_instances = {}

    def timed(name, original):
        def wrapper(*args, **kwargs):
            start = time.perf_counter()
            try:
                result = original(*args, **kwargs)
                if isinstance(result, bool):
                    item = stage_totals[name]
                    result_key = "true_results" if result else "false_results"
                    item[result_key] = item.get(result_key, 0) + 1
                elif isinstance(result, list):
                    input_count = len(args[1]) if len(args) > 1 and isinstance(args[1], list) else None
                    stage_totals[name].setdefault("item_counts", []).append(
                        {"input": input_count, "output": len(result)}
                    )
                if name == "_build_controlling_region_geometries" and args:
                    engine_instances[id(args[0])] = args[0]
                elif name == "_repair_final_controlling_partition" and len(args) > 2:
                    engine_instances[id(args[2])] = args[2]
                return result
            finally:
                item = stage_totals[name]
                item["calls"] += 1
                item["seconds"] += time.perf_counter() - start
        return wrapper

    original_comparison_parts = comparison_cls.comparison_parts

    def captured_comparison_parts(engine):
        start = time.perf_counter()
        result = original_comparison_parts(engine)
        elapsed = time.perf_counter() - start
        metrics = _comparison_metrics(engine, result)
        metrics["diagnostics"] = engine.comparison_diagnostics()
        comparison_results[metrics["family"]] = metrics
        engine_instances[id(engine.baseline_engine)] = engine.baseline_engine
        engine_instances[id(engine.future_engine)] = engine.future_engine
        item = stage_totals["comparison_parts"]
        item["calls"] += 1
        item["seconds"] += elapsed
        return result

    builder_methods = (
        "_create_controlling_ols_layers",
        "_create_annex14_controlling_surface_layers",
        "_create_controlling_region_layer",
        "_partition_controlling_region_features",
        "_dissolve_coplanar_controlling_regions",
        "_repair_final_controlling_partition",
        "_create_ols_modernisation_comparison_layers",
        "_run_modernisation_comparison",
    )
    engine_methods = ("_build_controlling_region_geometries", "region_boundary_features")
    iface = _Iface()
    builder = builder_cls(iface)
    builder.dlg = dialog
    qgis_logs = []

    def capture_log(message, tag, level):
        text = str(message)
        if int(level) >= int(Qgis.Warning) or "Controlling" in text or "controlling" in text:
            qgis_logs.append({"message": text, "tag": str(tag), "level": int(level)})

    QgsApplication.messageLog().messageReceived.connect(capture_log)
    with ExitStack() as stack:
        original_log_message = QgsMessageLog.logMessage

        def recorded_log_message(message, tag="", level=Qgis.Info, notifyUser=False):
            text = str(message)
            if int(level) >= int(Qgis.Warning) or "Controlling" in text or "controlling" in text:
                qgis_logs.append({"message": text, "tag": str(tag), "level": int(level)})
            return original_log_message(message, tag, level, notifyUser)

        stack.enter_context(patch.object(QgsMessageLog, "logMessage", recorded_log_message))
        for name in builder_methods:
            original = getattr(builder_cls, name)
            stack.enter_context(patch.object(builder_cls, name, timed(name, original)))
        for name in engine_methods:
            original = getattr(controlling_cls, name)
            stack.enter_context(patch.object(controlling_cls, name, timed(name, original)))
        stack.enter_context(patch.object(comparison_cls, "comparison_parts", captured_comparison_parts))
        original_change_contours = comparison_cls.change_contour_parts
        stack.enter_context(
            patch.object(
                comparison_cls,
                "change_contour_parts",
                timed("change_contour_parts", original_change_contours),
            )
        )
        start = time.perf_counter()
        builder.run_safeguarding_processing()
        total_seconds = time.perf_counter() - start
    QgsApplication.messageLog().messageReceived.disconnect(capture_log)

    layers = _layer_metrics(project)
    solver_diagnostics = []
    baseline_ruleset_id = getattr(
        getattr(builder, "baseline_ols_ruleset", None), "id", "conventional_ols"
    )
    conventional_family = (
        "MOS139" if baseline_ruleset_id == "mos139_2019" else baseline_ruleset_id
    )
    for engine in engine_instances.values():
        engine.ensure_adjacency_diagnostics()
        families = sorted({
            str((candidate.metadata or {}).get("annex14_family") or conventional_family)
            for candidate in engine.candidates
        })
        diagnostics = {
            "families": families,
            "candidate_count": len(engine.candidates),
            **engine.solver_diagnostics(),
        }
        transition_metrics = _axis_conical_transition_metrics(engine)
        if transition_metrics["features"]:
            diagnostics["axis_conical_transitions"] = transition_metrics
        if (
            families == ["MOS139"]
            and getattr(getattr(builder, "baseline_ols_ruleset", None), "id", "")
            == "mos139_2019"
        ):
            diagnostics["mos139_lock"] = _engine_lock_signature(engine)
        solver_diagnostics.append(diagnostics)
    failures = _case_failures(case, manifest, comparison_results, layers)
    if production_gates:
        for index, diagnostics in enumerate(solver_diagnostics, start=1):
            exceptional = diagnostics["exceptional_recovery"]
            if any(
                float(value) > 0.0
                for value in exceptional.values()
                if isinstance(value, (int, float))
            ):
                failures.append(f"solver {index} activated exceptional recovery: {exceptional}")
            if diagnostics["comparisons"]["unresolved"]:
                failures.append(f"solver {index} has unresolved candidate comparisons")
            if diagnostics["cells"]["unassigned"]:
                failures.append(f"solver {index} has unassigned global cells")
            if diagnostics["cells"]["ambiguous_gap_parts"]:
                failures.append(f"solver {index} has ambiguous subdivision coverage gaps")
            if diagnostics["cells"]["unanimous_gap_parts"]:
                failures.append(f"solver {index} has unapplied unanimous subdivision gaps")
            if diagnostics["topology"]["transition_method"] != "cell_adjacency":
                failures.append(f"solver {index} did not derive transitions from adjacency")
            if (
                diagnostics["geometry"]["invalid_input_candidates"]
                or diagnostics["geometry"]["invalid_output_regions"]
            ):
                failures.append(f"solver {index} has invalid input/output geometry")
            approximation = diagnostics["approximations"]
            approximation_calls = (
                int(approximation["triangulation_calls"])
                + int(approximation["zero_contour_calls"])
            )
            if approximation_calls and approximation["vertical_error_bound_m"] is None:
                failures.append(f"solver {index} used an approximation without a vertical error bound")
            if approximation["smoothed_zero_contours"]:
                if float(approximation["smoothing_max_endpoint_shift_m"]) > float(
                    approximation["smoothing_max_allowed_endpoint_shift_m"]
                ):
                    failures.append(
                        f"solver {index} shifted a smoothed transition endpoint"
                    )
                if float(approximation["smoothing_max_deviation_m"]) > float(
                    approximation["smoothing_max_allowed_deviation_m"]
                ):
                    failures.append(
                        f"solver {index} exceeded the smoothing deviation bound"
                    )
                if float(
                    approximation["smoothing_max_equality_residual_m"]
                ) > float(
                    approximation["smoothing_max_allowed_equality_residual_m"]
                ):
                    failures.append(
                        f"solver {index} exceeded the smoothing equality bound"
                    )
            transition_topology = diagnostics.get("axis_conical_transitions")
            if transition_topology:
                for key in (
                    "reversal_count",
                    "duplicate_segment_count",
                    "short_component_count",
                ):
                    if int(transition_topology[key]):
                        failures.append(
                            f"solver {index} axis/conical transitions have {key}: "
                            f"{transition_topology[key]}"
                        )
                if float(transition_topology["topology_excess_length_m"]) > 1e-6:
                    failures.append(
                        f"solver {index} axis/conical transitions retain "
                        f"{transition_topology['topology_excess_length_m']:.6f} m of excess topology"
                    )
        for family, metrics in comparison_results.items():
            diagnostics = metrics["diagnostics"]
            exceptional = diagnostics["exceptional_recovery"]
            if any(
                float(value) > 0.0
                for value in exceptional.values()
                if isinstance(value, (int, float))
            ):
                failures.append(f"{family} comparison activated exceptional recovery: {exceptional}")
            if diagnostics["unresolved_comparisons"]:
                failures.append(f"{family} comparison has unresolved comparisons")
            approximation = diagnostics["bounded_approximations"]
            approximation_calls = (
                int(approximation["fallback_lower_region_calls"])
                + int(approximation["sampled_whole_overlap_calls"])
            )
            if approximation_calls and approximation["vertical_error_bound_m"] is None:
                failures.append(f"{family} comparison used an unbounded approximation")
    result = {
        "fixture": case["file"],
        "description": case["description"],
        "icao_code": case["icao_code"],
        "runways": case["payload_runway_count"],
        "baseline_ruleset": getattr(getattr(builder, "baseline_ols_ruleset", None), "id", None),
        "comparison_ruleset": getattr(getattr(builder, "comparison_ols_ruleset", None), "id", None),
        "total_seconds": total_seconds,
        "stages": dict(sorted(stage_totals.items())),
        "comparisons": comparison_results,
        "layers": layers,
        "messages": iface.bar.messages,
        "qgis_logs": qgis_logs,
        "solver_diagnostics": solver_diagnostics,
        "mos139_lock": next(
            (
                diagnostics["mos139_lock"]
                for diagnostics in solver_diagnostics
                if "mos139_lock" in diagnostics
            ),
            None,
        ),
        "production_gates": production_gates,
        "failures": failures,
        "passed": not failures,
    }
    dialog.deleteLater()
    project.clear()
    return result


def _parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--fixture",
        action="append",
        help="Fixture filename from tests/fixtures/ols; repeat to select multiple cases.",
    )
    parser.add_argument("--output", type=Path, help="Optional JSON report path.")
    parser.add_argument("--repeat", type=int, default=1, help="Runs per fixture; use 3 or more for release gates.")
    parser.add_argument("--baseline", type=Path, help="Performance baseline JSON used for release gates.")
    parser.add_argument(
        "--production-gates",
        action="store_true",
        help="Fail on any exceptional recovery repair or unresolved comparison.",
    )
    parser.add_argument(
        "--maximum-runtime-regression",
        type=float,
        default=0.20,
        help="Maximum permitted median runtime regression as a fraction.",
    )
    return parser.parse_args()


def _stable_signature(result: Dict[str, object]) -> Dict[str, object]:
    """Accuracy-sensitive metrics which must remain identical across runs."""
    layers = result["layers"]
    return {
        key: layers[key]
        for key in (
            "layers", "features", "invalid_geometries", "empty_geometries",
            "duplicate_comparison_ids", "style_feature_counts", "controlling",
            "determinism_digest",
        )
    } | {
        "solver_diagnostics": result.get("solver_diagnostics", []),
        "comparisons": {
            family: {
                key: metrics[key]
                for key in (
                    "feature_counts", "common_domain_area_m2",
                    "unclassified_common_area_m2", "classified_overlap_area_m2", "diagnostics",
                )
            }
            for family, metrics in sorted(result["comparisons"].items())
        }
    }


def _release_gate_failures(fixture, runs, baseline, maximum_regression):
    failures = []
    signatures = [_stable_signature(run) for run in runs]
    if any(signature != signatures[0] for signature in signatures[1:]):
        failures.append("repeated runs produced non-deterministic accuracy/output metrics")
    if baseline is None:
        return failures
    expected = baseline.get("fixtures", {}).get(fixture)
    if expected is None:
        return failures + ["fixture is missing from the selected baseline"]
    median_seconds = statistics.median(float(run["total_seconds"]) for run in runs)
    limit = float(expected["total_seconds"]) * (1.0 + maximum_regression)
    if median_seconds > limit:
        failures.append(f"median runtime {median_seconds:.3f}s exceeds {limit:.3f}s gate")
    actual = runs[0]["layers"]
    for key, value in expected.get("output", {}).items():
        if key in actual and actual[key] != value:
            failures.append(f"{key} changed from {value} to {actual[key]}")
    for family, expected_metrics in expected.get("comparisons", {}).items():
        metrics = runs[0]["comparisons"].get(family)
        if metrics is None:
            failures.append(f"comparison family {family} is missing")
        elif metrics["feature_counts"] != expected_metrics.get("feature_counts"):
            failures.append(f"{family} feature counts changed from baseline")
        else:
            domain_tolerance = max(
                0.1, float(expected_metrics["common_domain_area_m2"]) * 1e-9
            )
            domain_delta = abs(
                float(metrics["common_domain_area_m2"])
                - float(expected_metrics["common_domain_area_m2"])
            )
            if domain_delta > domain_tolerance:
                failures.append(f"{family} common-domain area changed by {domain_delta:.6f} m2")
            for key in ("unclassified_common_area_m2", "classified_overlap_area_m2"):
                if float(metrics[key]) > float(expected_metrics[key]) + 0.1:
                    failures.append(f"{family} {key} regressed from baseline")
    return failures


def main() -> int:
    args = _parse_args()
    if args.repeat < 1:
        raise SystemExit("--repeat must be at least 1")
    if args.maximum_runtime_regression < 0.0:
        raise SystemExit("--maximum-runtime-regression must be non-negative")
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    baseline = json.loads(args.baseline.read_text(encoding="utf-8")) if args.baseline else None
    mos139_lock = (
        json.loads(MOS139_LOCK_PATH.read_text(encoding="utf-8"))
        if MOS139_LOCK_PATH.exists()
        else None
    )
    cases = manifest["cases"]
    if args.fixture:
        requested = set(args.fixture)
        cases = [case for case in cases if case["file"] in requested]
        missing = requested - {case["file"] for case in cases}
        if missing:
            raise SystemExit(f"Unknown fixture(s): {', '.join(sorted(missing))}")

    workspace = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(workspace.parent))
    from safeguarding_builder.safeguarding_builder import SafeguardingBuilder
    from safeguarding_builder.safeguarding_builder_dialog import SafeguardingBuilderDialog
    from safeguarding_builder.guidelines.controlling_ols_engine import PlanarControllingOlsEngine
    from safeguarding_builder.guidelines.ols_modernisation_comparison import OlsEnvelopeComparisonEngine

    app = QgsApplication([], True)
    app.setPrefixPath("/Applications/QGIS-4.0.app/Contents/MacOS", True)
    app.initQgis()
    report = {
        "qgis_version": Qgis.QGIS_VERSION,
        "repeat": args.repeat,
        "baseline": str(args.baseline) if args.baseline else None,
        "maximum_runtime_regression": args.maximum_runtime_regression,
        "fixtures": [],
    }
    for case in cases:
        runs = [
            _run_case(
                case,
                manifest,
                SafeguardingBuilder,
                SafeguardingBuilderDialog,
                PlanarControllingOlsEngine,
                OlsEnvelopeComparisonEngine,
                production_gates=args.production_gates,
            )
            for _run_number in range(args.repeat)
        ]
        gate_failures = _release_gate_failures(
            case["file"], runs, baseline, args.maximum_runtime_regression
        )
        if mos139_lock is not None and case.get("mos139_lock_required", True):
            expected_lock = mos139_lock.get("fixtures", {}).get(case["file"])
            for run in runs:
                if expected_lock is None:
                    run["failures"].append("fixture is missing from the MOS139 controlling lock")
                elif run.get("mos139_lock") != expected_lock:
                    run["failures"].append(
                        "MOS139 controlling geometry differs from the locked contract"
                    )
                run["passed"] = not run["failures"]
        if args.repeat == 1 and baseline is None:
            report["fixtures"].append(runs[0])
        else:
            report["fixtures"].append({
                "fixture": case["file"],
                "median_total_seconds": statistics.median(run["total_seconds"] for run in runs),
                "runs": runs,
                "gate_failures": gate_failures,
                "passed": all(run["passed"] for run in runs) and not gate_failures,
            })
    report["passed"] = all(case["passed"] for case in report["fixtures"])
    if args.output:
        args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    app.exitQgis()
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
