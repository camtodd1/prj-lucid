#!/usr/bin/env python3
"""Sample known conical-edge lines against registered controlling OLS candidates."""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


QGIS_APP = Path("/Applications/QGIS-4.0.app")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("PROJ_DATA", str(QGIS_APP / "Contents/Resources/qgis/proj"))
os.environ.setdefault("GDAL_DATA", str(QGIS_APP / "Contents/Resources/gdal"))

from qgis.core import (  # type: ignore  # noqa: E402
    Qgis,
    QgsApplication,
    QgsCoordinateReferenceSystem,
    QgsFeature,
    QgsGeometry,
    QgsPointXY,
    QgsProject,
    QgsRectangle,
    QgsVectorLayer,
)


REPO_PACKAGE_DIR = Path(__file__).resolve().parents[1]
REPO_PARENT_DIR = REPO_PACKAGE_DIR.parent
if str(REPO_PARENT_DIR) not in sys.path:
    sys.path.insert(0, str(REPO_PARENT_DIR))
if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from qgis_controlling_ols_probe import _Iface, _Dialog, _build_input_data  # type: ignore  # noqa: E402
from safeguarding_builder.safeguarding_builder import SafeguardingBuilder  # type: ignore  # noqa: E402
from safeguarding_builder.guidelines.controlling_ols_engine import (  # type: ignore  # noqa: E402
    PlanarControllingOlsEngine,
)


def _feature_attr(feature: QgsFeature, name: str) -> Optional[str]:
    try:
        value = feature.attribute(name)
    except Exception:
        return None
    if value is None:
        return None
    text = str(value)
    return text if text else None


def _line_points(engine: PlanarControllingOlsEngine, geometry: QgsGeometry, step_m: float) -> Iterable[QgsPointXY]:
    for line in engine._line_parts(geometry):
        if len(line) < 2:
            continue
        for start, end in zip(line[:-1], line[1:]):
            segment_length = start.distance(end)
            steps = max(1, int(math.ceil(segment_length / step_m)))
            for index in range(steps):
                fraction = index / steps
                yield QgsPointXY(
                    start.x() + ((end.x() - start.x()) * fraction),
                    start.y() + ((end.y() - start.y()) * fraction),
                )
        yield QgsPointXY(line[-1].x(), line[-1].y())


def _z_line_points(geometry: QgsGeometry, step_m: float) -> Iterable[Tuple[QgsPointXY, Optional[float]]]:
    for line in geometry.constParts():
        try:
            vertices = [vertex for vertex in line.vertices()]
        except Exception:
            vertices = []
        if len(vertices) < 2:
            continue
        for start, end in zip(vertices[:-1], vertices[1:]):
            start_xy = QgsPointXY(start.x(), start.y())
            end_xy = QgsPointXY(end.x(), end.y())
            segment_length = start_xy.distance(end_xy)
            steps = max(1, int(math.ceil(segment_length / step_m)))
            start_z = start.z() if start.is3D() else None
            end_z = end.z() if end.is3D() else None
            for index in range(steps):
                fraction = index / steps
                z_value = None
                if start_z is not None and end_z is not None:
                    z_value = start_z + ((end_z - start_z) * fraction)
                yield (
                    QgsPointXY(
                        start.x() + ((end.x() - start.x()) * fraction),
                        start.y() + ((end.y() - start.y()) * fraction),
                    ),
                    z_value,
                )
        end_z = vertices[-1].z() if vertices[-1].is3D() else None
        yield QgsPointXY(vertices[-1].x(), vertices[-1].y()), end_z


def _stats(values: Sequence[float]) -> Tuple[float, float, float, float]:
    if not values:
        return math.nan, math.nan, math.nan, math.nan
    ordered = sorted(values)
    return min(values), max(values), sum(values) / len(values), ordered[len(ordered) // 2]


def _run(args: argparse.Namespace) -> int:
    QgsApplication.setPrefixPath(str(QGIS_APP / "Contents/MacOS"), True)
    app = QgsApplication([], False)
    app.initQgis()

    project = QgsProject.instance()
    project.clear()
    crs = QgsCoordinateReferenceSystem(args.crs)
    if not crs.isValid():
        raise RuntimeError(f"Invalid CRS: {args.crs}")
    project.setCrs(crs)

    raw = json.loads(Path(args.input).read_text(encoding="utf-8"))
    input_data = _build_input_data(raw)
    plugin = SafeguardingBuilder(_Iface())
    plugin.dlg = _Dialog(input_data)
    plugin.run_safeguarding_processing()

    candidates = list(getattr(plugin, "_controlling_ols_candidates", []) or [])
    exclusions = list(getattr(plugin, "_controlling_ols_exclusion_geometries", []) or [])
    engine = PlanarControllingOlsEngine(candidates, exclusion_geometries=exclusions)
    by_id = {candidate.surface_id: candidate for candidate in candidates}
    conical = next((candidate for candidate in candidates if candidate.model == "conical"), None)
    if conical is None:
        raise RuntimeError("No conical candidate was registered.")
    conical_model = engine._conical_model(conical)
    if conical_model is None:
        raise RuntimeError("Registered conical candidate has no conical model.")
    base_footprint = conical_model["base_footprint"]
    base_elevation = float(conical_model["base_elevation_m"])
    conical_slope = float(conical_model["slope"])

    edge_layer = QgsVectorLayer(args.edges, "edge_probe", "ogr")
    if not edge_layer.isValid():
        raise RuntimeError(f"Could not load edge layer: {args.edges}")
    bounds = None
    if args.bounds:
        values = [float(value) for value in args.bounds.split(",")]
        if len(values) != 4:
            raise ValueError("--bounds must be minx,miny,maxx,maxy")
        bounds = QgsGeometry.fromRect(QgsRectangle(values[0], values[1], values[2], values[3]))

    print(f"QGIS: {Qgis.QGIS_VERSION}")
    print(f"CRS: {project.crs().authid()} {project.crs().description()}")
    print(f"CONICAL {conical.surface_id} base_elev={base_elevation:.3f} slope={conical_slope:.8f}")
    if args.axis_id and args.axis_id in by_id:
        axis_candidate = by_id[args.axis_id]
        metadata = axis_candidate.metadata or {}
        print(
            "AXIS "
            f"{axis_candidate.surface_id} surface={axis_candidate.surface_type} model={axis_candidate.model} "
            f"origin=({float(metadata.get('origin_x', math.nan)):.3f},"
            f"{float(metadata.get('origin_y', math.nan)):.3f}) "
            f"azimuth={float(metadata.get('azimuth_degrees', math.nan)):.8f} "
            f"origin_elev={float(metadata.get('origin_elevation_m', math.nan)):.6f} "
            f"slope={float(metadata.get('slope', math.nan)):.8f} "
            f"max_distance={float(metadata.get('max_distance_m', math.nan)):.3f}"
        )

    for feature in edge_layer.getFeatures():
        if bounds is not None:
            try:
                if not feature.geometry().intersects(bounds):
                    continue
            except Exception:
                continue
        axis_id = args.axis_id or _feature_attr(feature, args.axis_attr)
        if not axis_id:
            adjacent = _feature_attr(feature, "adjacent")
            if adjacent:
                axis_id = next((part for part in adjacent.split("|") if not part.startswith("CONICAL:")), None)
        if not axis_id or axis_id not in by_id:
            continue
        axis_candidate = by_id[axis_id]
        diffs: List[float] = []
        distance_residuals: List[float] = []
        known_axis_residuals: List[float] = []
        known_conical_residuals: List[float] = []
        controlling_hits = 0
        sample_count = 0
        for point_xy, known_z in _z_line_points(feature.geometry(), args.step):
            axis_z = axis_candidate.elevation_at_xy(point_xy)
            conical_z = conical.elevation_at_xy(point_xy)
            if axis_z is None or conical_z is None:
                continue
            sample_count += 1
            diff = axis_z - conical_z
            diffs.append(diff)
            if known_z is not None and math.isfinite(known_z):
                known_axis_residuals.append(known_z - axis_z)
                known_conical_residuals.append(known_z - conical_z)
            point_geometry = QgsGeometry.fromPointXY(point_xy)
            actual_distance = point_geometry.distance(base_footprint)
            required_distance = (axis_z - base_elevation) / conical_slope
            distance_residuals.append(actual_distance - required_distance)
            controlling = engine.controlling_candidate_at_xy(point_xy)
            if controlling is not None and controlling[0].surface_id == axis_id:
                controlling_hits += 1
        diff_stats = _stats(diffs)
        distance_stats = _stats(distance_residuals)
        known_axis_stats = _stats(known_axis_residuals)
        known_conical_stats = _stats(known_conical_residuals)
        print(
            "EDGE "
            f"fid={feature.id()} axis={axis_id} surface={axis_candidate.surface_type} "
            f"samples={sample_count} axis_controls={controlling_hits} "
            f"z_diff[min,max,mean,median]=[{diff_stats[0]:.4f},{diff_stats[1]:.4f},"
            f"{diff_stats[2]:.4f},{diff_stats[3]:.4f}] "
            f"distance_residual[min,max,mean,median]=[{distance_stats[0]:.4f},"
            f"{distance_stats[1]:.4f},{distance_stats[2]:.4f},{distance_stats[3]:.4f}]"
            f" known_minus_axis[min,max,mean,median]=[{known_axis_stats[0]:.4f},"
            f"{known_axis_stats[1]:.4f},{known_axis_stats[2]:.4f},{known_axis_stats[3]:.4f}]"
            f" known_minus_conical[min,max,mean,median]=[{known_conical_stats[0]:.4f},"
            f"{known_conical_stats[1]:.4f},{known_conical_stats[2]:.4f},{known_conical_stats[3]:.4f}]"
        )

    app.exitQgis()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="Saved Safeguarding Builder JSON input file.")
    parser.add_argument("--crs", default="EPSG:32756", help="Projected CRS to use for the QGIS project.")
    parser.add_argument("--edges", required=True, help="Known/missing edge GeoJSON to sample.")
    parser.add_argument("--axis-attr", default="axis_id", help="Attribute containing the non-conical surface id.")
    parser.add_argument("--axis-id", help="Force all sampled edge features to use this candidate surface id.")
    parser.add_argument("--bounds", help="Optional map bounds as minx,miny,maxx,maxy.")
    parser.add_argument("--step", type=float, default=20.0, help="Sampling step along edge lines in metres.")
    return _run(parser.parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
