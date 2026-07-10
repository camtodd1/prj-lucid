"""Explicit QGIS 4 regression and benchmark runner for complete OLS workflows."""

from __future__ import annotations

import argparse
import json
import os
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
            for candidate in engine.future_engine.candidates
            if (candidate.metadata or {}).get("annex14_family")
        ),
        "UNKNOWN",
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
    }


def _layer_metrics(project: QgsProject) -> Dict[str, object]:
    style_counts: Dict[str, int] = defaultdict(int)
    styles_to_geometries: Dict[str, List[QgsGeometry]] = defaultdict(list)
    invalid = 0
    empty = 0
    comparison_ids: List[str] = []
    layer_count = 0
    feature_count = 0
    for node in project.layerTreeRoot().findLayers():
        layer = node.layer()
        if layer is None:
            continue
        layer_count += 1
        style_key = str(layer.customProperty("safeguarding_style_key") or "")
        fields = layer.fields().names()
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
        "controlling": controlling,
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
    if set(comparisons) != {"OFS", "OES"}:
        failures.append(f"comparison families were {sorted(comparisons)}")

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


def _run_case(case, manifest, builder_cls, dialog_cls, controlling_cls, comparison_cls):
    fixture_path = FIXTURE_DIR / case["file"]
    payload = json.loads(fixture_path.read_text(encoding="utf-8"))
    case = {**case, "payload_runway_count": len(payload.get("runways", []))}
    project = QgsProject.instance()
    project.clear()
    project.setCrs(QgsCoordinateReferenceSystem(case["project_crs"]))
    dialog = dialog_cls()
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
        comparison_results[metrics["family"]] = metrics
        item = stage_totals["comparison_parts"]
        item["calls"] += 1
        item["seconds"] += elapsed
        return result

    builder_methods = (
        "_create_controlling_ols_planar_poc_layers",
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
    failures = _case_failures(case, manifest, comparison_results, layers)
    result = {
        "fixture": case["file"],
        "description": case["description"],
        "icao_code": case["icao_code"],
        "runways": case["payload_runway_count"],
        "total_seconds": total_seconds,
        "stages": dict(sorted(stage_totals.items())),
        "comparisons": comparison_results,
        "layers": layers,
        "messages": iface.bar.messages,
        "qgis_logs": qgis_logs,
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
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
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
        "fixtures": [],
    }
    for case in cases:
        report["fixtures"].append(
            _run_case(
                case,
                manifest,
                SafeguardingBuilder,
                SafeguardingBuilderDialog,
                PlanarControllingOlsEngine,
                OlsEnvelopeComparisonEngine,
            )
        )
    report["passed"] = all(case["passed"] for case in report["fixtures"])
    if args.output:
        args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    app.exitQgis()
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
