"""Structured, concise logging for Safeguarding Builder runs.

The QGIS message log is intentionally treated as a human-readable operational
trace.  Detailed implementation diagnostics use a separate tag and are opt-in.
Legacy emitters are routed through the adapter while they are migrated to the
structured API.
"""

from __future__ import annotations

import os
import re
import time
import logging
import traceback
from collections import OrderedDict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, Mapping, Optional, Tuple

from qgis.core import Qgis, QgsMessageLog as _QgsMessageLog  # type: ignore


PLUGIN_TAG = "SafeguardingBuilder"
DIAGNOSTIC_TAG = "SafeguardingBuilder.Diagnostics"
DIAGNOSTICS_ENV_VAR = "SAFEGUARDING_BUILDER_DIAGNOSTICS"


class EventKind(str, Enum):
    START = "START"
    PHASE = "PHASE"
    SKIP = "SKIP"
    OUTPUT = "OUTPUT"
    WARN = "WARN"
    ERROR = "ERROR"
    DONE = "DONE"
    CANCELLED = "CANCELLED"
    FAILED = "FAILED"
    DIAG = "DIAG"


class OutcomeStatus(str, Enum):
    GENERATED = "generated"
    SKIPPED_MISSING_INPUT = "skipped_missing_input"
    SKIPPED_NOT_APPLICABLE = "skipped_not_applicable"
    DEGRADED = "degraded"
    FAILED = "failed"


@dataclass(frozen=True)
class LogEvent:
    kind: EventKind
    scope: Optional[str] = None
    reason: Optional[str] = None
    consequence: Optional[str] = None
    action: Optional[str] = None
    phase_step: Optional[int] = None
    phase_total: Optional[int] = None
    phase_key: Optional[str] = None
    title: Optional[str] = None
    facts: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class GenerationOutcome:
    scope: str
    status: OutcomeStatus
    reason: Optional[str] = None
    layers: Optional[int] = None
    features: Optional[int] = None
    facts: Mapping[str, Any] = field(default_factory=dict)

    def __bool__(self) -> bool:
        return self.status in {OutcomeStatus.GENERATED, OutcomeStatus.DEGRADED}


_FACT_ORDER = (
    "airport",
    "crs",
    "runways",
    "runway",
    "end",
    "surface",
    "ruleset",
    "baseline",
    "comparison",
    "framework",
    "layers",
    "features",
    "files",
    "output",
    "value_m",
    "basis",
    "count",
    "skips",
    "warnings",
    "errors",
    "elapsed_s",
)


def _one_line(value: Any) -> str:
    text = str(value).replace("\r", " ").replace("\n", " ")
    return re.sub(r"\s+", " ", text).strip()


def _ordered_facts(facts: Mapping[str, Any]):
    yielded = set()
    for key in _FACT_ORDER:
        value = facts.get(key)
        if value is not None and value != "":
            yielded.add(key)
            yield key, value
    for key in sorted(facts):
        value = facts[key]
        if key not in yielded and value is not None and value != "":
            yield key, value


def render_event(event: LogEvent) -> str:
    if event.kind == EventKind.PHASE:
        if event.phase_step is not None and event.phase_total is not None:
            head = f"PHASE {event.phase_step}/{event.phase_total}"
        else:
            head = "PHASE"
        parts = [head]
        if event.title:
            parts.append(_one_line(event.title).rstrip("."))
    else:
        parts = [event.kind.value]
        if event.scope:
            parts.append(f"scope={_one_line(event.scope)}")

    if event.reason:
        parts.append(f"reason={_one_line(event.reason)}")
    if event.consequence:
        parts.append(f"consequence={_one_line(event.consequence)}")
    if event.action:
        parts.append(f"action={_one_line(event.action)}")
    parts.extend(f"{key}={_one_line(value)}" for key, value in _ordered_facts(event.facts))
    return " | ".join(parts)


def _event_level(kind: EventKind):
    if kind == EventKind.DONE:
        return Qgis.Success
    if kind == EventKind.WARN:
        return Qgis.Warning
    if kind in {EventKind.ERROR, EventKind.FAILED}:
        return Qgis.Critical
    return Qgis.Info


def _qgis_sink(message: str, tag: str, level) -> None:
    try:
        _QgsMessageLog.logMessage(message, tag, level=level, notifyUser=False)
    except TypeError:
        _QgsMessageLog.logMessage(message, tag, level=level)


def diagnostics_enabled_from_environment() -> bool:
    return os.environ.get(DIAGNOSTICS_ENV_VAR, "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


class RunLog:
    """Run-scoped event logger with phase deduplication and aggregation."""

    def __init__(
        self,
        sink: Optional[Callable[[str, str, Any], None]] = None,
        *,
        diagnostics_enabled: Optional[bool] = None,
    ) -> None:
        self._sink = sink or _qgis_sink
        self.diagnostics_enabled = (
            diagnostics_enabled_from_environment()
            if diagnostics_enabled is None
            else bool(diagnostics_enabled)
        )
        self.started_at = time.perf_counter()
        self.started = False
        self.terminal = False
        self.current_phase: Optional[str] = None
        self.context: Dict[str, Any] = {}
        self.events = []
        self._pending: "OrderedDict[Tuple[Any, ...], Tuple[LogEvent, int]]" = OrderedDict()
        self.skip_count = 0
        self.warning_count = 0
        self.error_count = 0
        configure_standard_logging(self.diagnostics_enabled)

    def _emit(self, event: LogEvent, *, diagnostic: bool = False) -> None:
        if diagnostic and not self.diagnostics_enabled:
            return
        self.events.append(event)
        tag = DIAGNOSTIC_TAG if diagnostic else PLUGIN_TAG
        self._sink(render_event(event), tag, _event_level(event.kind))

    def start(self, **facts: Any) -> None:
        self.context.update({key: value for key, value in facts.items() if value is not None})
        if self.started:
            return
        self.started = True
        self._emit(LogEvent(EventKind.START, facts=dict(self.context)))

    def update_context(self, **facts: Any) -> None:
        self.context.update({key: value for key, value in facts.items() if value is not None})

    def phase(self, step: int, total: int, key: str, title: str) -> None:
        if self.current_phase == key:
            return
        self.flush()
        self.current_phase = key
        self._emit(
            LogEvent(
                EventKind.PHASE,
                phase_step=step,
                phase_total=total,
                phase_key=key,
                title=title,
            )
        )

    def _queue(self, event: LogEvent) -> None:
        key = (
            self.current_phase,
            event.kind,
            event.scope,
            event.reason,
            event.consequence,
            event.action,
            tuple(sorted((str(k), _one_line(v)) for k, v in event.facts.items())),
        )
        existing = self._pending.get(key)
        self._pending[key] = (event, 1 if existing is None else existing[1] + 1)

    def flush(self) -> None:
        for event, count in self._pending.values():
            if count > 1:
                facts = dict(event.facts)
                facts["count"] = count
                event = LogEvent(
                    event.kind,
                    scope=event.scope,
                    reason=event.reason,
                    consequence=event.consequence,
                    action=event.action,
                    phase_key=event.phase_key,
                    facts=facts,
                )
            self._emit(event)
        self._pending.clear()

    def skip(self, scope: str, reason: str, **facts: Any) -> None:
        self.skip_count += 1
        self._queue(LogEvent(EventKind.SKIP, scope=scope, reason=reason, facts=facts))

    def output(
        self,
        scope: str,
        *,
        layers: Optional[int] = None,
        features: Optional[int] = None,
        **facts: Any,
    ) -> None:
        payload = dict(facts)
        if layers is not None:
            payload["layers"] = layers
        if features is not None:
            payload["features"] = features
        self._emit(LogEvent(EventKind.OUTPUT, scope=scope, facts=payload))

    def warning(
        self,
        scope: str,
        consequence: str,
        *,
        action: Optional[str] = None,
        aggregate: bool = True,
        **facts: Any,
    ) -> None:
        self.warning_count += 1
        event = LogEvent(
            EventKind.WARN,
            scope=scope,
            consequence=consequence,
            action=action,
            facts=facts,
        )
        if aggregate:
            self._queue(event)
        else:
            self._emit(event)

    def error(
        self,
        scope: str,
        reason: str,
        *,
        consequence: Optional[str] = None,
        action: Optional[str] = None,
        **facts: Any,
    ) -> None:
        self.error_count += 1
        self._emit(
            LogEvent(
                EventKind.ERROR,
                scope=scope,
                reason=reason,
                consequence=consequence,
                action=action,
                facts=facts,
            )
        )

    def diagnostic(self, scope: str, detail: str, **facts: Any) -> None:
        self._emit(
            LogEvent(EventKind.DIAG, scope=scope, reason=detail, facts=facts),
            diagnostic=True,
        )

    def record_outcome(self, outcome: GenerationOutcome) -> None:
        facts = dict(outcome.facts)
        if outcome.status == OutcomeStatus.GENERATED:
            self.output(
                outcome.scope,
                layers=outcome.layers,
                features=outcome.features,
                **facts,
            )
            return
        if outcome.layers is not None:
            facts["layers"] = outcome.layers
        if outcome.features is not None:
            facts["features"] = outcome.features
        if outcome.status in {
            OutcomeStatus.SKIPPED_MISSING_INPUT,
            OutcomeStatus.SKIPPED_NOT_APPLICABLE,
        }:
            self.skip(outcome.scope, outcome.reason or outcome.status.value, **facts)
        elif outcome.status == OutcomeStatus.DEGRADED:
            self.warning(
                outcome.scope,
                outcome.reason or "output was generated with a recoverable degradation",
                **facts,
            )
        else:
            self.error(
                outcome.scope,
                outcome.reason or "output generation failed",
                consequence="requested output was not generated",
                **facts,
            )

    def finish(self, status: str, **facts: Any) -> None:
        if self.terminal:
            return
        self.flush()
        self.terminal = True
        payload = dict(self.context)
        payload.update({key: value for key, value in facts.items() if value is not None})
        payload["skips"] = self.skip_count
        payload["warnings"] = self.warning_count
        payload["errors"] = self.error_count
        payload.setdefault("elapsed_s", f"{time.perf_counter() - self.started_at:.2f}")
        layers = payload.get("layers")
        if status == "completed" and layers == 0:
            status = "failed"
            payload.setdefault("reason", "no usable layers were generated")
        if status == "completed":
            kind = EventKind.DONE
        elif status == "cancelled":
            kind = EventKind.CANCELLED
            payload.setdefault("reason", "cancelled by user")
        else:
            kind = EventKind.FAILED
            payload.setdefault("reason", "generation did not complete")
        reason = payload.pop("reason", None)
        self._emit(LogEvent(kind, reason=reason, facts=payload))

    def legacy(self, message: Any, level=Qgis.Info) -> None:
        original_text = str(message)
        summary_text, traceback_separator, traceback_detail = original_text.partition(
            "\nTraceback"
        )
        raw_text = _one_line(summary_text)
        explicit_skip = bool(re.match(r"^\[skip\]", raw_text, flags=re.IGNORECASE))
        text = _strip_legacy_prefixes(raw_text)
        if not text:
            return
        if traceback_separator:
            self.diagnostic(
                "exception",
                text,
                traceback="Traceback" + traceback_detail,
            )
        lowered = text.lower()
        if _is_vestigial(text):
            self.diagnostic("legacy", text)
            return
        if _is_level(level, Qgis.Critical):
            self.error("generation", text, consequence="requested output may be incomplete")
            return
        if _is_level(level, Qgis.Warning):
            skip = _legacy_skip(text, explicit=explicit_skip)
            if skip is not None:
                self.skip(*skip)
            else:
                self.warning("generation", text)
            return
        if _is_level(level, Qgis.Success):
            self.diagnostic("generation", text)
            return
        skip = _legacy_skip(text, explicit=explicit_skip)
        if skip is not None:
            if "no features generated" in lowered or "report not written" in lowered:
                self.diagnostic(skip[0], skip[1])
            else:
                self.skip(*skip)
            return
        self.diagnostic("generation", text)


def _is_level(actual, expected) -> bool:
    try:
        return int(actual) == int(expected)
    except (TypeError, ValueError):
        return actual == expected


def _strip_legacy_prefixes(text: str) -> str:
    text = re.sub(
        r"^\[(?:step|done|skip|diagnostics|repair|normalise|temporary debug(?::[^]]+)?)\]\s*",
        "",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(
        r"^(?:info|warning|critical error|critical|error)\s*:\s*",
        "",
        text,
        flags=re.IGNORECASE,
    )
    return text.strip()


def _is_vestigial(text: str) -> bool:
    lowered = text.lower()
    return any(
        marker in lowered
        for marker in (
            "runtime test record appended",
            "dialog shown",
            "dialog finished signal received",
            "entered _generate_",
            "display_name =",
            "[diagnostics]",
            "[repair]",
            "[normalise]",
        )
    )


def _legacy_skip(text: str, *, explicit: bool = False) -> Optional[Tuple[str, str]]:
    lowered = text.lower()
    if "failed" in lowered and not lowered.startswith("skipping"):
        return None
    candidates = (
        "skipping ",
        "skip ",
    )
    body = text
    matched = False
    for prefix in candidates:
        if lowered.startswith(prefix):
            body = text[len(prefix) :]
            matched = True
            break
    if not matched and not explicit and not any(
        marker in lowered
        for marker in (
            " skipped",
            " not applicable",
            " not required",
            " no features generated",
        )
    ):
        return None
    scope, separator, reason = body.partition(":")
    if not separator:
        scope = body
        reason = "not applicable" if "not applicable" in lowered else "not required"
    return _one_line(scope).rstrip("."), _one_line(reason).rstrip(".")


_active_run_log: Optional[RunLog] = None


class QgisLogHandler(logging.Handler):
    """Bridge package-local stdlib records without configuring the root logger."""

    _safeguarding_builder_handler = True

    def emit(self, record: logging.LogRecord) -> None:
        try:
            message = _one_line(record.getMessage())
            run_log = _active_run_log
            if record.levelno >= logging.ERROR:
                if run_log is not None:
                    run_log.error(record.name, message)
                else:
                    _qgis_sink(
                        render_event(LogEvent(EventKind.ERROR, scope=record.name, reason=message)),
                        PLUGIN_TAG,
                        Qgis.Critical,
                    )
            elif record.levelno >= logging.WARNING:
                if run_log is not None:
                    run_log.warning(record.name, message)
                else:
                    _qgis_sink(
                        render_event(LogEvent(EventKind.WARN, scope=record.name, consequence=message)),
                        PLUGIN_TAG,
                        Qgis.Warning,
                    )
            elif run_log is not None:
                run_log.diagnostic(record.name, message)
            if record.exc_info and run_log is not None:
                run_log.diagnostic(
                    record.name,
                    "exception traceback",
                    traceback="".join(traceback.format_exception(*record.exc_info)),
                )
        except Exception:
            self.handleError(record)


def configure_standard_logging(diagnostics_enabled: bool = False) -> None:
    package_logger = logging.getLogger("safeguarding_builder")
    if not any(
        getattr(handler, "_safeguarding_builder_handler", False)
        for handler in package_logger.handlers
    ):
        package_logger.addHandler(QgisLogHandler())
    package_logger.setLevel(logging.DEBUG if diagnostics_enabled else logging.INFO)
    package_logger.propagate = False


def set_active_run_log(run_log: Optional[RunLog]) -> None:
    global _active_run_log
    _active_run_log = run_log


def active_run_log() -> Optional[RunLog]:
    return _active_run_log


def emit_legacy(message: Any, level=Qgis.Info) -> None:
    if _active_run_log is not None:
        _active_run_log.legacy(message, level)
        return
    standalone = RunLog(diagnostics_enabled=diagnostics_enabled_from_environment())
    standalone.legacy(message, level)
    standalone.flush()


class QgsMessageLog:
    """Compatibility proxy routing legacy plugin calls through the event schema."""

    @staticmethod
    def logMessage(message, tag=PLUGIN_TAG, level=Qgis.Info, notifyUser=False):
        del tag, notifyUser
        emit_legacy(message, level)


__all__ = [
    "DIAGNOSTIC_TAG",
    "DIAGNOSTICS_ENV_VAR",
    "EventKind",
    "GenerationOutcome",
    "LogEvent",
    "OutcomeStatus",
    "PLUGIN_TAG",
    "QgsMessageLog",
    "RunLog",
    "active_run_log",
    "diagnostics_enabled_from_environment",
    "configure_standard_logging",
    "emit_legacy",
    "render_event",
    "set_active_run_log",
]
