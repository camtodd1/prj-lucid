#!/usr/bin/env python3
"""Run the Safeguarding Builder controlling OLS solve in headless QGIS.

This script is intentionally small and procedural: it lets us reproduce the
same QGIS geometry stack used by the plugin without opening the plugin dialog.
Run it with QGIS's bundled Python, for example:

    /Applications/QGIS-4.0.app/Contents/MacOS/python tools/qgis_controlling_ols_probe.py \
        --input "/Users/camtodd_to70/GitHub/Input test data/YMEN.json"
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, Optional


QGIS_APP = Path("/Applications/QGIS-4.0.app")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("PROJ_DATA", str(QGIS_APP / "Contents/Resources/qgis/proj"))
os.environ.setdefault("GDAL_DATA", str(QGIS_APP / "Contents/Resources/gdal"))

from qgis.core import (  # type: ignore  # noqa: E402
    Qgis,
    QgsApplication,
    QgsCoordinateReferenceSystem,
    QgsMessageLog,
    QgsPointXY,
    QgsProject,
    QgsVectorFileWriter,
    QgsVectorLayer,
    QgsWkbTypes,
)


REPO_PACKAGE_DIR = Path(__file__).resolve().parents[1]
REPO_PARENT_DIR = REPO_PACKAGE_DIR.parent
if str(REPO_PARENT_DIR) not in sys.path:
    sys.path.insert(0, str(REPO_PARENT_DIR))

from safeguarding_builder.safeguarding_builder import SafeguardingBuilder  # type: ignore  # noqa: E402
from safeguarding_builder.guidelines.controlling_ols_engine import (  # type: ignore  # noqa: E402
    PlanarControllingOlsEngine,
)


class _MessageBar:
    def pushMessage(self, *args: Any, **kwargs: Any) -> None:
        level = kwargs.get("level")
        duration = kwargs.get("duration")
        joined = " | ".join(str(arg) for arg in args)
        print(f"MESSAGE level={level} duration={duration}: {joined}")


class _Iface:
    def __init__(self) -> None:
        self._message_bar = _MessageBar()

    def mainWindow(self) -> None:
        return None

    def messageBar(self) -> _MessageBar:
        return self._message_bar

    def addVectorLayer(self, path: str, name: str, provider: str) -> Optional[QgsVectorLayer]:
        layer = QgsVectorLayer(path, name, provider)
        if layer.isValid():
            QgsProject.instance().addMapLayer(layer, False)
            return layer
        return None


class _Dialog:
    def __init__(self, input_data: Dict[str, Any]) -> None:
        self._input_data = input_data

    def get_all_input_data(self) -> Dict[str, Any]:
        return self._input_data

    def set_processing_status(self, message: str) -> None:
        print(f"STATUS: {message}")

    def clear_processing_status(self) -> None:
        print("STATUS: <clear>")

    def accept(self) -> None:
        print("DIALOG: accept")


def _to_float(value: Any, default: Optional[float] = None) -> Optional[float]:
    if value is None:
        return default
    text = str(value).strip()
    if not text:
        return default
    return float(text)


def _to_bool(value: Any, default: bool = True) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() not in {"0", "false", "no", "off"}


def _validated_runway(raw_runway: Dict[str, Any], index: int) -> Dict[str, Any]:
    runway = dict(raw_runway)
    designator_num = int(str(raw_runway.get("designator_str", "")).strip())
    runway.update(
        {
            "original_index": index,
            "designator_num": designator_num,
            "suffix": str(raw_runway.get("suffix", "") or ""),
            "thr_point": QgsPointXY(
                float(raw_runway["thr_easting"]),
                float(raw_runway["thr_northing"]),
            ),
            "rec_thr_point": QgsPointXY(
                float(raw_runway["rec_easting"]),
                float(raw_runway["rec_northing"]),
            ),
            "runway_end_elev_1": _to_float(raw_runway.get("runway_end_elev_1"), _to_float(raw_runway.get("thr_elev_1"))),
            "runway_end_elev_2": _to_float(raw_runway.get("runway_end_elev_2"), _to_float(raw_runway.get("thr_elev_2"))),
            "threshold_elev_1": _to_float(raw_runway.get("threshold_elev_1"), _to_float(raw_runway.get("thr_elev_1"))),
            "threshold_elev_2": _to_float(raw_runway.get("threshold_elev_2"), _to_float(raw_runway.get("thr_elev_2"))),
            "thr_displaced_1": _to_float(raw_runway.get("thr_displaced_1")),
            "thr_displaced_2": _to_float(raw_runway.get("thr_displaced_2")),
            "thr_pre_area_1": _to_float(raw_runway.get("thr_pre_area_1")),
            "thr_pre_area_2": _to_float(raw_runway.get("thr_pre_area_2")),
            "width": _to_float(raw_runway.get("width")),
            "shoulder": _to_float(raw_runway.get("shoulder")),
            "clearway1_len": _to_float(raw_runway.get("clearway1_len"), 0.0),
            "clearway2_len": _to_float(raw_runway.get("clearway2_len"), 0.0),
            "stopway1_len": _to_float(raw_runway.get("stopway1_len"), 0.0),
            "stopway2_len": _to_float(raw_runway.get("stopway2_len"), 0.0),
            "takeoff_available_1": _to_bool(raw_runway.get("takeoff_available_1"), True),
            "takeoff_available_2": _to_bool(raw_runway.get("takeoff_available_2"), True),
            "landing_available_1": _to_bool(raw_runway.get("landing_available_1"), True),
            "landing_available_2": _to_bool(raw_runway.get("landing_available_2"), True),
            "lahso_applied_1": _to_bool(raw_runway.get("lahso_applied_1"), False),
            "lahso_applied_2": _to_bool(raw_runway.get("lahso_applied_2"), False),
            "adg": str(raw_runway.get("adg", raw_runway.get("design_group", "")) or "").strip().upper(),
            "design_group": str(raw_runway.get("adg", raw_runway.get("design_group", "")) or "").strip().upper(),
            "surface_category": str(raw_runway.get("surface_category", "") or "").strip(),
            "surface_material": str(raw_runway.get("surface_material", "") or "").strip(),
            "type1": raw_runway.get("type1"),
            "type2": raw_runway.get("type2"),
            "ruleset": raw_runway.get("ruleset", "mos139_2019"),
        }
    )
    runway["thr_elev_1"] = runway["threshold_elev_1"]
    runway["thr_elev_2"] = runway["threshold_elev_2"]
    return runway


def _build_input_data(raw: Dict[str, Any]) -> Dict[str, Any]:
    arp_easting = _to_float(raw.get("arp_easting"))
    arp_northing = _to_float(raw.get("arp_northing"))
    if arp_easting is None or arp_northing is None:
        arp_point = None
    else:
        arp_point = QgsPointXY(arp_easting, arp_northing)

    met_easting = _to_float(raw.get("met_easting"))
    met_northing = _to_float(raw.get("met_northing"))
    met_point = None
    if met_easting is not None and met_northing is not None:
        met_point = QgsPointXY(met_easting, met_northing)

    output_options = raw.get("output_options") or {}
    return {
        "icao_code": raw.get("icao_code", "UNKNOWN"),
        "arp_point": arp_point,
        "arp_easting": arp_easting,
        "arp_northing": arp_northing,
        "arp_elevation": _to_float(raw.get("arp_elevation")),
        "met_point": met_point,
        "met_elevation": _to_float(raw.get("met_elevation")),
        "design_standard": raw.get("design_standard", raw.get("ruleset", "mos139_2019")),
        "ruleset": raw.get("ruleset", raw.get("design_standard", "mos139_2019")),
        "safeguarding_framework": raw.get("safeguarding_framework", "nasf_aus"),
        "protected_airspace_policy": raw.get("protected_airspace_policy", "ruleset_aligned"),
        "runways": [
            _validated_runway(runway, index)
            for index, runway in enumerate(raw.get("runways") or [], start=1)
        ],
        "agl_options": raw.get("agl_options", {"enabled": False}),
        "cns_facilities": raw.get("cns_facilities", []),
        "output_mode": "memory",
        "output_path": None,
        "output_format_driver": None,
        "output_format_extension": None,
        "contour_intervals": output_options.get("contour_intervals", {}),
        "generate_controlling_ols": True,
    }


def _message_level_name(level: Any) -> str:
    try:
        return Qgis.MessageLevel(level).name
    except Exception:
        return str(level)


def _connect_log_echo() -> None:
    def _echo(message: str, tag: str, level: Any) -> None:
        if tag != "SafeguardingBuilder":
            return
        print(f"LOG {tag} {_message_level_name(level)}: {message}")

    QgsApplication.messageLog().messageReceived.connect(_echo)


def _write_layer(layer: QgsVectorLayer, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        result = QgsVectorFileWriter.writeAsVectorFormat(
            layer,
            str(output_path),
            "UTF-8",
            layer.crs(),
            "GeoJSON",
        )
    except TypeError:
        result = QgsVectorFileWriter.writeAsVectorFormatV2(
            layer,
            str(output_path),
            QgsProject.instance().transformContext(),
            QgsVectorFileWriter.SaveVectorOptions(),
        )
    print(f"EXPORT {layer.name()} -> {output_path} result={result}")


def _iter_layers_by_name(names: Iterable[str]) -> Iterable[QgsVectorLayer]:
    wanted = set(names)
    for layer in QgsProject.instance().mapLayers().values():
        if layer.name() in wanted and isinstance(layer, QgsVectorLayer):
            yield layer


def _geometry_area(geometry: Any) -> float:
    if geometry is None or geometry.isEmpty():
        return 0.0
    try:
        return float(geometry.area())
    except Exception:
        return 0.0


def _line_part_count(engine: PlanarControllingOlsEngine, geometry: Any) -> int:
    if geometry is None or geometry.isEmpty():
        return 0
    return sum(1 for part in engine._line_parts(geometry) if len(part) >= 2)


def _linework_part_count(engine: PlanarControllingOlsEngine, geometry: Any) -> int:
    if geometry is None or geometry.isEmpty():
        return 0
    return sum(1 for part in engine._linework_parts(geometry) if len(part) >= 2)


def _geometry_desc(engine: PlanarControllingOlsEngine, geometry: Any) -> str:
    if geometry is None:
        return "None"
    try:
        wkb = QgsWkbTypes.displayString(geometry.wkbType())
    except Exception:
        wkb = "?"
    try:
        geom_type = int(geometry.type())
    except Exception:
        geom_type = -1
    return (
        f"empty={geometry.isEmpty()} type={geom_type} wkb={wkb} "
        f"area={_geometry_area(geometry):.2f} "
        f"line_parts={_line_part_count(engine, geometry)} "
        f"linework_parts={_linework_part_count(engine, geometry)}"
    )


def _diagnose_conical_overlaps(plugin: SafeguardingBuilder) -> None:
    candidates = list(getattr(plugin, "_controlling_ols_candidates", []) or [])
    exclusion_geometries = list(getattr(plugin, "_controlling_ols_exclusion_geometries", []) or [])
    engine = PlanarControllingOlsEngine(candidates, exclusion_geometries=exclusion_geometries)
    conical_candidates = [candidate for candidate in candidates if candidate.model == "conical"]
    if not conical_candidates:
        print("DIAG conical: no conical candidates")
        return
    conical = conical_candidates[0]
    conical_model = engine._conical_model(conical)
    conical_effective = engine._effective_footprint(conical)
    print(
        "DIAG conical: "
        f"id={conical.surface_id} area={_geometry_area(conical_effective):.2f} "
        f"model={'yes' if conical_model else 'no'}"
    )
    for candidate in candidates:
        if candidate.surface_type not in {"Approach", "TOCS"}:
            continue
        if candidate.model not in {"axis", "plane"}:
            continue
        candidate_effective = engine._effective_footprint(candidate)
        if not engine._has_polygon_area(candidate_effective) or not engine._has_polygon_area(conical_effective):
            continue
        try:
            overlap = candidate_effective.intersection(conical_effective)
        except Exception:
            overlap = None
        if not engine._has_polygon_area(overlap):
            continue

        candidate_summary = engine._sampled_lower_summary(candidate, conical, overlap, dense=True)
        conical_summary = engine._sampled_lower_summary(conical, candidate, overlap, dense=True)
        lower_region = engine._candidate_lower_region(candidate, conical, overlap)
        conical_lower_region = engine._candidate_lower_region(conical, candidate, overlap)
        fallback_boundary = engine._fallback_pair_boundary_geometry(overlap, candidate, conical)
        reverse_fallback_boundary = engine._fallback_pair_boundary_geometry(overlap, conical, candidate)
        lower_boundary = None
        conical_boundary = None
        try:
            lower_boundary = lower_region.boundary() if lower_region is not None and not lower_region.isEmpty() else None
        except Exception:
            lower_boundary = None
        try:
            conical_boundary = (
                conical_lower_region.boundary()
                if conical_lower_region is not None and not conical_lower_region.isEmpty()
                else None
            )
        except Exception:
            conical_boundary = None
        curve = None
        if candidate.model == "axis" and conical_model is not None:
            axis = engine._axis_model(candidate)
            if axis is not None:
                curve = engine._axis_conical_transition_curve(axis, conical_model, overlap)
        print(
            "DIAG conical_pair: "
            f"{candidate.surface_id} ({candidate.surface_type}/{candidate.model}) "
            f"overlap={_geometry_area(overlap):.2f} "
            f"candidate_lower={candidate_summary[0]} samples={candidate_summary[1]} "
            f"diff=[{candidate_summary[2]},{candidate_summary[3]}] "
            f"candidate_lower_area={_geometry_area(lower_region):.2f} "
            f"conical_lower={conical_summary[0]} "
            f"conical_lower_area={_geometry_area(conical_lower_region):.2f} "
            f"curve_parts={_line_part_count(engine, curve)} "
            f"fallback_parts={_line_part_count(engine, fallback_boundary)} "
            f"reverse_fallback_parts={_line_part_count(engine, reverse_fallback_boundary)}"
        )
        print(
            "DIAG lower_geom: "
            f"{candidate.surface_id} lower=({_geometry_desc(engine, lower_region)}) "
            f"lower_boundary=({_geometry_desc(engine, lower_boundary)}) "
            f"conical_lower=({_geometry_desc(engine, conical_lower_region)}) "
            f"conical_boundary=({_geometry_desc(engine, conical_boundary)})"
        )


def run_probe(args: argparse.Namespace) -> int:
    QgsApplication.setPrefixPath(str(QGIS_APP / "Contents/MacOS"), True)
    app = QgsApplication([], False)
    app.initQgis()
    _connect_log_echo()

    project = QgsProject.instance()
    project.clear()
    crs = QgsCoordinateReferenceSystem(args.crs)
    if not crs.isValid():
        raise RuntimeError(f"Invalid CRS: {args.crs}")
    project.setCrs(crs)
    print(f"QGIS: {Qgis.QGIS_VERSION}")
    print(f"CRS: {project.crs().authid()} {project.crs().description()}")

    raw = json.loads(Path(args.input).read_text(encoding="utf-8"))
    input_data = _build_input_data(raw)

    plugin = SafeguardingBuilder(_Iface())
    plugin.dlg = _Dialog(input_data)
    plugin.run_safeguarding_processing()
    if args.diagnose_conical:
        _diagnose_conical_overlaps(plugin)

    controlling_names = [
        f"OLS Controlling Planar Candidates POC {input_data['icao_code']}",
        f"OLS Controlling Planar Regions POC {input_data['icao_code']}",
        f"OLS Controlling Planar Transitions POC {input_data['icao_code']}",
        f"OLS Controlling Contours POC {input_data['icao_code']}",
    ]
    for layer in _iter_layers_by_name(controlling_names):
        print(f"LAYER {layer.name()}: features={layer.featureCount()} valid={layer.isValid()}")
        if args.output_dir:
            safe_name = layer.name().replace(" ", "_").replace("/", "_")
            _write_layer(layer, Path(args.output_dir) / f"{safe_name}.geojson")

    app.exitQgis()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="Saved Safeguarding Builder JSON input file.")
    parser.add_argument("--crs", default="EPSG:7855", help="Projected CRS to use for the QGIS project.")
    parser.add_argument("--output-dir", default="", help="Optional directory for exported controlling layers.")
    parser.add_argument(
        "--diagnose-conical",
        action="store_true",
        help="Print detailed Approach/TOCS-vs-conical lower-envelope diagnostics.",
    )
    return run_probe(parser.parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
