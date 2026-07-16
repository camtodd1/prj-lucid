"""Append-only runtime history for GUI and headless safeguarding runs."""

from __future__ import annotations

import configparser
import csv
import hashlib
import io
import json
import math
import os
import re
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, Mapping, Optional

try:
    import fcntl
except ImportError:  # pragma: no cover - QGIS production targets are Unix-like.
    fcntl = None


RUN_HISTORY_SCHEMA_VERSION = 4
RUN_HISTORY_FILENAME = "runtime_test_runs.txt"
AGENT_ENV_VAR = "SAFEGUARDING_BUILDER_RUN_AGENT"
COMMIT_ENV_VAR = "SAFEGUARDING_BUILDER_COMMIT"
HISTORY_PATH_ENV_VAR = "SAFEGUARDING_BUILDER_RUN_HISTORY"
RUNWAY_CONFIGURATIONS = ("single", "parallel", "intersecting", "mixed")


def _uppercase_icao_reference(value: object, icao_code: object) -> str:
    text = str(value or "").strip()
    code = str(icao_code or "").strip().upper()
    if len(code) == 4 and code.isalpha():
        return re.sub(rf"\b{re.escape(code)}\b", code, text, flags=re.IGNORECASE)
    return text

KEY_MODULE_COLUMNS = (
    ("phase_startup_seconds", "phase.startup"),
    ("phase_inputs_seconds", "phase.inputs"),
    ("phase_output_setup_seconds", "phase.output_setup"),
    ("phase_runway_reference_geometry_seconds", "phase.runway_reference_geometry"),
    ("phase_physical_and_protection_seconds", "phase.physical_and_protection"),
    ("phase_runway_ols_seconds", "phase.runway_ols"),
    ("phase_airport_wide_ols_seconds", "phase.airport_wide_ols"),
    ("phase_controlling_envelope_seconds", "phase.controlling_envelope"),
    ("phase_ruleset_comparison_seconds", "phase.ruleset_comparison"),
    ("phase_supporting_safeguarding_seconds", "phase.supporting_safeguarding"),
    ("phase_finalisation_seconds", "phase.finalisation"),
    ("controlling_candidates_seconds", "controlling_ols.candidates"),
    ("controlling_regions_seconds", "controlling_ols.regions"),
    ("controlling_transitions_seconds", "controlling_ols.transitions"),
    ("controlling_contours_seconds", "controlling_ols.contours"),
    ("controlling_total_seconds", "controlling_ols.total"),
)

RUN_HISTORY_COLUMNS = (
    "schema_version",
    "timestamp_utc",
    "agent",
    "status",
    "airport",
    "design_ruleset",
    "baseline_ols_ruleset",
    "comparison_ols_ruleset",
    "design_ruleset_label",
    "baseline_ols_ruleset_label",
    "comparison_ols_ruleset_label",
    "commit_ref",
    "working_tree_dirty",
    "plugin_version",
    "qgis_version",
    "elapsed_seconds",
    *(column for column, _module in KEY_MODULE_COLUMNS),
    "module_timings_json",
    "layers_created",
    "features_created",
    "test_case_id",
    "test_case_name",
    "input_filename",
    "runway_count",
    "runway_configuration",
    "input_fingerprint",
)


def _xy(point: object) -> Optional[tuple[float, float]]:
    """Read an x/y pair from QGIS point-like objects or simple sequences."""
    if point is None:
        return None
    try:
        x_value = point.x() if callable(getattr(point, "x", None)) else getattr(point, "x")
        y_value = point.y() if callable(getattr(point, "y", None)) else getattr(point, "y")
        return float(x_value), float(y_value)
    except (AttributeError, TypeError, ValueError):
        pass
    if isinstance(point, (list, tuple)) and len(point) >= 2:
        try:
            return float(point[0]), float(point[1])
        except (TypeError, ValueError):
            return None
    return None


def _runway_segment(
    runway: Mapping[str, object],
) -> Optional[tuple[tuple[float, float], tuple[float, float]]]:
    start = _xy(runway.get("thr_point"))
    end = _xy(runway.get("rec_thr_point"))
    if start is None:
        try:
            start = (float(runway["thr_easting"]), float(runway["thr_northing"]))
        except (KeyError, TypeError, ValueError):
            start = None
    if end is None:
        try:
            end = (float(runway["rec_easting"]), float(runway["rec_northing"]))
        except (KeyError, TypeError, ValueError):
            end = None
    if start is None or end is None or start == end:
        return None
    return start, end


def _segments_intersect(
    first: tuple[tuple[float, float], tuple[float, float]],
    second: tuple[tuple[float, float], tuple[float, float]],
) -> bool:
    def orientation(a, b, c) -> float:
        return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])

    a, b = first
    c, d = second
    return (
        orientation(a, b, c) * orientation(a, b, d) <= 0
        and orientation(c, d, a) * orientation(c, d, b) <= 0
    )


def classify_runway_configuration(runways: Iterable[Mapping[str, object]]) -> str:
    """Return the supported scenario derived from runway centreline geometry."""
    runway_list = list(runways)
    if not runway_list:
        raise ValueError("A runway scenario requires at least one runway.")
    if len(runway_list) == 1:
        return "single"
    segments = [segment for segment in (_runway_segment(item) for item in runway_list) if segment]
    if len(segments) != len(runway_list):
        raise ValueError("Runway scenario cannot be determined from incomplete centrelines.")

    parallel_pairs = 0
    intersecting_pairs = 0
    pair_count = 0
    for index, first in enumerate(segments):
        first_dx = first[1][0] - first[0][0]
        first_dy = first[1][1] - first[0][1]
        first_length = math.hypot(first_dx, first_dy)
        for second in segments[index + 1 :]:
            pair_count += 1
            second_dx = second[1][0] - second[0][0]
            second_dy = second[1][1] - second[0][1]
            second_length = math.hypot(second_dx, second_dy)
            sine = abs(first_dx * second_dy - first_dy * second_dx) / (
                first_length * second_length
            )
            if sine <= math.sin(math.radians(5.0)):
                parallel_pairs += 1
            elif _segments_intersect(first, second):
                intersecting_pairs += 1

    if parallel_pairs == pair_count:
        return "parallel"
    if len(runway_list) == 2:
        # The supported two-runway taxonomy is deliberately binary: a pair is
        # parallel within tolerance, otherwise it is the intersecting scenario.
        return "intersecting"
    if intersecting_pairs == pair_count:
        return "intersecting"
    return "mixed"


def validate_runway_configuration(value: object, runway_count: Optional[int] = None) -> str:
    """Normalize a scenario and enforce its permitted runway count."""
    scenario = str(value or "").strip().lower()
    if scenario not in RUNWAY_CONFIGURATIONS:
        allowed = ", ".join(RUNWAY_CONFIGURATIONS)
        raise ValueError(f"Runway configuration must be one of: {allowed}.")
    if runway_count is None:
        return scenario

    count = int(runway_count)
    if count < 1:
        raise ValueError("Runway count must be at least 1.")
    if scenario == "single" and count != 1:
        raise ValueError("The single scenario requires exactly 1 runway.")
    if scenario in {"parallel", "intersecting"} and count < 2:
        raise ValueError(f"The {scenario} scenario requires at least 2 runways.")
    if scenario == "mixed" and count < 3:
        raise ValueError("The mixed scenario requires at least 3 runways.")
    return scenario


def _fingerprint_value(value: object) -> object:
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        return round(value, 9)
    if isinstance(value, Mapping):
        return {
            str(key): _fingerprint_value(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
            if not str(key).startswith("_")
        }
    if isinstance(value, (list, tuple)):
        return [_fingerprint_value(item) for item in value]
    point = _xy(value)
    if point is not None:
        return [round(point[0], 6), round(point[1], 6)]
    return str(value)


def runtime_input_fingerprint(input_data: Mapping[str, object]) -> str:
    """Fingerprint inputs that can materially change a safeguarding runtime."""
    relevant_keys = (
        "icao_code",
        "design_standard",
        "safeguarding_framework",
        "protected_airspace_policy",
        "baseline_ols_ruleset",
        "comparison_ols_ruleset",
        "runway_configuration",
        "runways",
        "cns_facilities",
        "agl_options",
        "contour_intervals",
        "output_mode",
        "output_format_driver",
    )
    payload = {
        key: _fingerprint_value(input_data.get(key))
        for key in relevant_keys
        if key in input_data
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()[:12]


def _module_timings(record: Mapping[str, object]) -> Dict[str, Dict[str, object]]:
    timings: Dict[str, Dict[str, object]] = {}
    modules = record.get("modules", [])
    if not isinstance(modules, list):
        return timings
    for module in modules:
        if not isinstance(module, Mapping):
            continue
        name = str(module.get("name", "")).strip()
        if not name:
            continue
        timings[name] = {
            "calls": int(module.get("calls", 0)),
            "elapsed_seconds": module.get("elapsed_seconds", 0),
        }
    return timings


def _table_row(record: Mapping[str, object]) -> Dict[str, object]:
    rulesets = record.get("rulesets", {})
    labels = record.get("ruleset_labels", {})
    rulesets = rulesets if isinstance(rulesets, Mapping) else {}
    labels = labels if isinstance(labels, Mapping) else {}
    timings = _module_timings(record)
    dirty = record.get("working_tree_dirty")
    row: Dict[str, object] = {
        "schema_version": record.get("schema_version", ""),
        "timestamp_utc": record.get("timestamp_utc", ""),
        "agent": record.get("agent", ""),
        "status": record.get("status", ""),
        "airport": record.get("airport", ""),
        "design_ruleset": rulesets.get("design", "") or "",
        "baseline_ols_ruleset": rulesets.get("baseline_ols", "") or "",
        "comparison_ols_ruleset": rulesets.get("comparison_ols", "") or "",
        "design_ruleset_label": labels.get("design", "") or "",
        "baseline_ols_ruleset_label": labels.get("baseline_ols", "") or "",
        "comparison_ols_ruleset_label": labels.get("comparison_ols", "") or "",
        "commit_ref": record.get("commit_ref", ""),
        "working_tree_dirty": "" if dirty is None else str(bool(dirty)).lower(),
        "plugin_version": record.get("plugin_version", ""),
        "qgis_version": record.get("qgis_version", ""),
        "elapsed_seconds": record.get("elapsed_seconds", ""),
        "module_timings_json": json.dumps(timings, sort_keys=True, separators=(",", ":")),
        "layers_created": record.get("layers_created", ""),
        "features_created": record.get("features_created", ""),
        "test_case_id": record.get("test_case_id", "") or "",
        "test_case_name": record.get("test_case_name", "") or "",
        "input_filename": record.get("input_filename", "") or "",
        "runway_count": record.get("runway_count", "") or "",
        "runway_configuration": record.get("runway_configuration", "") or "",
        "input_fingerprint": record.get("input_fingerprint", "") or "",
    }
    for column, module_name in KEY_MODULE_COLUMNS:
        timing = timings.get(module_name)
        row[column] = timing.get("elapsed_seconds", "") if timing else ""
    return row


def _table_payload(records: Iterable[Mapping[str, object]], *, header: bool) -> bytes:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(
        stream,
        fieldnames=RUN_HISTORY_COLUMNS,
        delimiter="\t",
        lineterminator="\n",
        extrasaction="ignore",
    )
    if header:
        writer.writeheader()
    for record in records:
        writer.writerow(_table_row(record))
    return stream.getvalue().encode("utf-8")


def _legacy_records(content: str) -> Optional[list[Dict[str, object]]]:
    if not content.strip().startswith("{"):
        return None
    records = []
    for line in content.splitlines():
        if line.strip():
            records.append(json.loads(line))
    return records


def _upgrade_tabular_header(content: str) -> Optional[bytes]:
    """Append newly introduced trailing columns to an older tabular header."""
    if not content or content.lstrip().startswith("{"):
        return None
    first_line, separator, remainder = content.partition("\n")
    existing_columns = tuple(first_line.rstrip("\r").split("\t"))
    if existing_columns == RUN_HISTORY_COLUMNS:
        return None
    if existing_columns != RUN_HISTORY_COLUMNS[: len(existing_columns)]:
        return None
    header = "\t".join(RUN_HISTORY_COLUMNS)
    upgraded = header + ("\n" + remainder if separator else "\n")
    return upgraded.encode("utf-8")


def _lock(descriptor: int) -> None:
    if fcntl is not None:
        fcntl.flock(descriptor, fcntl.LOCK_EX)


def _unlock(descriptor: int) -> None:
    if fcntl is not None:
        fcntl.flock(descriptor, fcntl.LOCK_UN)


def migrate_history_file(history_path: Path) -> bool:
    """Convert the former JSON-lines ledger to the tabular schema in place."""
    path = Path(history_path)
    if not path.exists():
        return False
    descriptor = os.open(path, os.O_RDWR)
    try:
        _lock(descriptor)
        os.lseek(descriptor, 0, os.SEEK_SET)
        content = os.read(descriptor, os.fstat(descriptor).st_size).decode("utf-8")
        records = _legacy_records(content)
        if records is not None:
            payload = _table_payload(records, header=True)
        else:
            payload = _upgrade_tabular_header(content)
            if payload is None:
                return False
        os.ftruncate(descriptor, 0)
        os.lseek(descriptor, 0, os.SEEK_SET)
        os.write(descriptor, payload)
        return True
    finally:
        _unlock(descriptor)
        os.close(descriptor)


def _append_record(history_path: Path, record: Mapping[str, object]) -> None:
    descriptor = os.open(history_path, os.O_CREAT | os.O_RDWR, 0o644)
    try:
        _lock(descriptor)
        size = os.fstat(descriptor).st_size
        os.lseek(descriptor, 0, os.SEEK_SET)
        prefix = os.read(descriptor, min(size, 4096)).decode("utf-8") if size else ""
        legacy = None
        if prefix.strip().startswith("{"):
            os.lseek(descriptor, 0, os.SEEK_SET)
            legacy = _legacy_records(os.read(descriptor, size).decode("utf-8"))
        if legacy is not None:
            payload = _table_payload([*legacy, record], header=True)
            os.ftruncate(descriptor, 0)
            os.lseek(descriptor, 0, os.SEEK_SET)
            os.write(descriptor, payload)
            return
        if size:
            os.lseek(descriptor, 0, os.SEEK_SET)
            content = os.read(descriptor, size).decode("utf-8")
            upgraded = _upgrade_tabular_header(content)
            if upgraded is not None:
                os.ftruncate(descriptor, 0)
                os.lseek(descriptor, 0, os.SEEK_SET)
                os.write(descriptor, upgraded)
                size = len(upgraded)
        os.lseek(descriptor, 0, os.SEEK_END)
        os.write(descriptor, _table_payload([record], header=not bool(size)))
    finally:
        _unlock(descriptor)
        os.close(descriptor)


def detect_run_agent(environ: Optional[Mapping[str, str]] = None) -> str:
    """Identify the normal GUI user or an explicitly/offscreen headless run."""
    env = os.environ if environ is None else environ
    explicit = str(env.get(AGENT_ENV_VAR, "")).strip()
    if explicit:
        return explicit
    if str(env.get("QT_QPA_PLATFORM", "")).strip().lower() == "offscreen" or env.get("CI"):
        return "codex headless"
    return "qgis user"


def default_history_path(plugin_dir: Path) -> Path:
    configured = str(os.environ.get(HISTORY_PATH_ENV_VAR, "")).strip()
    return Path(configured).expanduser() if configured else plugin_dir / RUN_HISTORY_FILENAME


def plugin_version(plugin_dir: Path) -> str:
    parser = configparser.ConfigParser()
    try:
        parser.read(plugin_dir / "metadata.txt", encoding="utf-8")
        return parser.get("general", "version", fallback="unknown")
    except (OSError, configparser.Error):
        return "unknown"


def git_revision(plugin_dir: Path) -> Dict[str, object]:
    """Return the build override or local Git revision and dirty state."""
    override = str(os.environ.get(COMMIT_ENV_VAR, "")).strip()
    if override:
        return {"commit_ref": override, "working_tree_dirty": None}
    try:
        commit = subprocess.run(
            ["git", "-C", str(plugin_dir), "rev-parse", "--short=12", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
            timeout=2.0,
        ).stdout.strip()
        dirty = bool(
            subprocess.run(
                ["git", "-C", str(plugin_dir), "status", "--porcelain"],
                check=True,
                capture_output=True,
                text=True,
                timeout=2.0,
            ).stdout.strip()
        )
        return {"commit_ref": commit or "unknown", "working_tree_dirty": dirty}
    except (OSError, subprocess.SubprocessError):
        return {"commit_ref": "unknown", "working_tree_dirty": None}


class RuntimeRunRecorder:
    """Collect phase/module durations and append one self-contained run record."""

    def __init__(
        self,
        plugin_dir: Path,
        *,
        qgis_version: str = "unknown",
        history_path: Optional[Path] = None,
        agent: Optional[str] = None,
    ) -> None:
        self.plugin_dir = Path(plugin_dir)
        self.history_path = (
            Path(history_path) if history_path else default_history_path(self.plugin_dir)
        )
        self.agent = agent or detect_run_agent()
        self.qgis_version = str(qgis_version or "unknown")
        self.started_at = time.perf_counter()
        self._phase_name: Optional[str] = None
        self._phase_started_at = self.started_at
        self._timings: Dict[str, Dict[str, float]] = {}
        self.airport = "unknown"
        self.rulesets: Dict[str, Optional[str]] = {
            "design": None,
            "baseline_ols": None,
            "comparison_ols": None,
        }
        self.ruleset_labels: Dict[str, Optional[str]] = dict(self.rulesets)
        self.test_case_id: Optional[str] = None
        self.test_case_name: Optional[str] = None
        self.input_filename: Optional[str] = None
        self.runway_count: Optional[int] = None
        self.runway_configuration: Optional[str] = None
        self.input_fingerprint: Optional[str] = None
        self.layers_created = 0
        self.features_created = 0
        self._output_counts_set = False

    def set_context(
        self,
        *,
        airport: Optional[str],
        design_ruleset: Optional[str],
        baseline_ruleset: Optional[str],
        comparison_ruleset: Optional[str],
        design_ruleset_label: Optional[str] = None,
        baseline_ruleset_label: Optional[str] = None,
        comparison_ruleset_label: Optional[str] = None,
        test_case_id: Optional[str] = None,
        test_case_name: Optional[str] = None,
        input_filename: Optional[str] = None,
        runway_count: Optional[int] = None,
        runway_configuration: Optional[str] = None,
        input_fingerprint: Optional[str] = None,
    ) -> None:
        airport_text = str(airport or "unknown").strip()
        self.airport = (
            airport_text.upper()
            if len(airport_text) == 4 and airport_text.isalpha()
            else airport_text
        )
        self.rulesets = {
            "design": str(design_ruleset) if design_ruleset else None,
            "baseline_ols": str(baseline_ruleset) if baseline_ruleset else None,
            "comparison_ols": str(comparison_ruleset) if comparison_ruleset else None,
        }
        self.ruleset_labels = {
            "design": str(design_ruleset_label) if design_ruleset_label else None,
            "baseline_ols": str(baseline_ruleset_label) if baseline_ruleset_label else None,
            "comparison_ols": (
                str(comparison_ruleset_label) if comparison_ruleset_label else None
            ),
        }
        if test_case_id is not None:
            self.test_case_id = str(test_case_id).strip() or None
        if test_case_name is not None:
            self.test_case_name = (
                _uppercase_icao_reference(test_case_name, self.airport) or None
            )
        if input_filename is not None:
            self.input_filename = Path(str(input_filename)).name or None
        if runway_count is not None:
            self.runway_count = max(0, int(runway_count))
        if runway_configuration is not None:
            self.runway_configuration = validate_runway_configuration(
                runway_configuration,
                self.runway_count,
            )
        if input_fingerprint is not None:
            self.input_fingerprint = str(input_fingerprint).strip() or None

    def add_timing(self, name: str, elapsed_seconds: float, calls: int = 1) -> None:
        key = str(name).strip()
        if not key:
            return
        item = self._timings.setdefault(key, {"calls": 0.0, "elapsed_seconds": 0.0})
        item["calls"] += max(0, int(calls))
        item["elapsed_seconds"] += max(0.0, float(elapsed_seconds))

    def set_output_counts(self, layers_created: int, features_created: int) -> None:
        """Record the generated output totals reported at completion."""
        self.layers_created = max(0, int(layers_created))
        self.features_created = max(0, int(features_created))
        self._output_counts_set = True

    def start_phase(self, name: str) -> None:
        key = str(name).strip()
        if not key or key == self._phase_name:
            return
        now = time.perf_counter()
        if self._phase_name is not None:
            self.add_timing(f"phase.{self._phase_name}", now - self._phase_started_at)
        self._phase_name = key
        self._phase_started_at = now

    def finish(self, status: str) -> Dict[str, object]:
        finished_at = time.perf_counter()
        if self._phase_name is not None:
            self.add_timing(f"phase.{self._phase_name}", finished_at - self._phase_started_at)
            self._phase_name = None
        revision = git_revision(self.plugin_dir)
        modules = [
            {
                "name": name,
                "calls": int(values["calls"]),
                "elapsed_seconds": round(values["elapsed_seconds"], 6),
            }
            for name, values in sorted(self._timings.items())
        ]
        record: Dict[str, object] = {
            "schema_version": RUN_HISTORY_SCHEMA_VERSION,
            "timestamp_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "agent": self.agent,
            "status": str(status or "unknown"),
            "airport": self.airport,
            "rulesets": self.rulesets,
            "ruleset_labels": self.ruleset_labels,
            "commit_ref": revision["commit_ref"],
            "working_tree_dirty": revision["working_tree_dirty"],
            "plugin_version": plugin_version(self.plugin_dir),
            "qgis_version": self.qgis_version,
            "elapsed_seconds": round(finished_at - self.started_at, 6),
            "test_case_id": self.test_case_id,
            "test_case_name": self.test_case_name,
            "input_filename": self.input_filename,
            "runway_count": self.runway_count,
            "runway_configuration": self.runway_configuration,
            "input_fingerprint": self.input_fingerprint,
            "layers_created": self.layers_created,
            "features_created": self.features_created,
            "modules": modules,
        }
        self.history_path.parent.mkdir(parents=True, exist_ok=True)
        _append_record(self.history_path, record)
        return record


__all__ = [
    "AGENT_ENV_VAR",
    "COMMIT_ENV_VAR",
    "HISTORY_PATH_ENV_VAR",
    "KEY_MODULE_COLUMNS",
    "RUN_HISTORY_COLUMNS",
    "RUN_HISTORY_FILENAME",
    "RUN_HISTORY_SCHEMA_VERSION",
    "RUNWAY_CONFIGURATIONS",
    "RuntimeRunRecorder",
    "classify_runway_configuration",
    "default_history_path",
    "detect_run_agent",
    "git_revision",
    "migrate_history_file",
    "plugin_version",
    "runtime_input_fingerprint",
    "validate_runway_configuration",
]
