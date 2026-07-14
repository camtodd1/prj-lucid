"""Append-only runtime history for GUI and headless safeguarding runs."""

from __future__ import annotations

import configparser
import json
import os
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Mapping, Optional


RUN_HISTORY_SCHEMA_VERSION = 1
RUN_HISTORY_FILENAME = "runtime_test_runs.txt"
AGENT_ENV_VAR = "SAFEGUARDING_BUILDER_RUN_AGENT"
COMMIT_ENV_VAR = "SAFEGUARDING_BUILDER_COMMIT"
HISTORY_PATH_ENV_VAR = "SAFEGUARDING_BUILDER_RUN_HISTORY"


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
        self.history_path = Path(history_path) if history_path else default_history_path(self.plugin_dir)
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
    ) -> None:
        self.airport = str(airport or "unknown")
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

    def add_timing(self, name: str, elapsed_seconds: float, calls: int = 1) -> None:
        key = str(name).strip()
        if not key:
            return
        item = self._timings.setdefault(key, {"calls": 0.0, "elapsed_seconds": 0.0})
        item["calls"] += max(0, int(calls))
        item["elapsed_seconds"] += max(0.0, float(elapsed_seconds))

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
            "modules": modules,
        }
        self.history_path.parent.mkdir(parents=True, exist_ok=True)
        payload = (json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
        descriptor = os.open(
            self.history_path,
            os.O_APPEND | os.O_CREAT | os.O_WRONLY,
            0o644,
        )
        try:
            os.write(descriptor, payload)
        finally:
            os.close(descriptor)
        return record


__all__ = [
    "AGENT_ENV_VAR",
    "COMMIT_ENV_VAR",
    "HISTORY_PATH_ENV_VAR",
    "RUN_HISTORY_FILENAME",
    "RUN_HISTORY_SCHEMA_VERSION",
    "RuntimeRunRecorder",
    "default_history_path",
    "detect_run_agent",
    "git_revision",
    "plugin_version",
]
