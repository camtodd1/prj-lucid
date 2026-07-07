# -*- coding: utf-8 -*-
"""Declared-distance consistency checks."""

from typing import Any, Dict, Iterable, List, Optional


TOLERANCE_M = 1e-6


def annotate_declared_distance_warnings(
    runway_data: Dict[str, Any],
    records: Iterable[Dict[str, Any]],
) -> List[str]:
    """Annotate declared-distance records and return report-level warnings."""
    record_list = list(records)
    warnings: List[str] = []
    runway_name = str(runway_data.get("short_name") or runway_data.get("rwy") or "Runway")

    physical_length = _first_number(record.get("physical_len_m") for record in record_list)
    threshold_length = _first_number(record.get("threshold_len_m") for record in record_list)
    if physical_length is not None and physical_length <= TOLERANCE_M:
        warnings.append(f"{runway_name}: physical runway length is not positive.")
    if threshold_length is not None and threshold_length <= TOLERANCE_M:
        warnings.append(f"{runway_name}: threshold-to-threshold length is not positive.")

    disp_primary = _number_or_zero(runway_data.get("thr_displaced_1"))
    disp_reciprocal = _number_or_zero(runway_data.get("thr_displaced_2"))
    if physical_length is not None and physical_length > TOLERANCE_M:
        if disp_primary >= physical_length - TOLERANCE_M:
            warnings.append(
                f"{runway_name}: primary displaced threshold ({_format_m(disp_primary)}) "
                f"is not less than physical runway length ({_format_m(physical_length)})."
            )
        if disp_reciprocal >= physical_length - TOLERANCE_M:
            warnings.append(
                f"{runway_name}: reciprocal displaced threshold ({_format_m(disp_reciprocal)}) "
                f"is not less than physical runway length ({_format_m(physical_length)})."
            )
        if disp_primary + disp_reciprocal >= physical_length - TOLERANCE_M:
            warnings.append(
                f"{runway_name}: combined displaced thresholds ({_format_m(disp_primary + disp_reciprocal)}) "
                f"leave no positive threshold-to-threshold landing length."
            )

    for record in record_list:
        record_warnings = _record_warnings(runway_name, record)
        _merge_record_notes(record, record_warnings)
        warnings.extend(record_warnings)

    return _unique_preserving_order(warnings)


def _record_warnings(runway_name: str, record: Dict[str, Any]) -> List[str]:
    end = str(record.get("end_desig") or record.get("direction") or "direction")
    label = f"{runway_name} {end}"
    warnings: List[str] = []

    takeoff_available = _bool_value(record.get("takeoff_available"))
    landing_available = _bool_value(record.get("landing_available"))
    tora = _number_or_none(record.get("tora_m"))
    toda = _number_or_none(record.get("toda_m"))
    asda = _number_or_none(record.get("asda_m"))
    lda = _number_or_none(record.get("lda_m"))
    clearway_entered = _number_or_zero(record.get("clearway_input_m", record.get("clearway_m")))
    stopway_entered = _number_or_zero(record.get("stopway_input_m", record.get("stopway_m")))
    physical_length = _number_or_none(record.get("physical_len_m"))

    if takeoff_available:
        if not _positive(tora):
            warnings.append(f"{label}: takeoff is available but TORA is missing or non-positive.")
        if tora is not None and toda is not None and toda + TOLERANCE_M < tora:
            warnings.append(f"{label}: TODA is less than TORA.")
        if tora is not None and asda is not None and asda + TOLERANCE_M < tora:
            warnings.append(f"{label}: ASDA is less than TORA.")
    else:
        if _positive(tora) or _positive(toda) or _positive(asda):
            warnings.append(f"{label}: takeoff is unavailable but takeoff declared distances are populated.")
        if clearway_entered > TOLERANCE_M or stopway_entered > TOLERANCE_M:
            warnings.append(
                f"{label}: takeoff is unavailable but clearway/stopway values are entered; TODA/ASDA remain blank."
            )

    if landing_available:
        if not _positive(lda):
            warnings.append(f"{label}: landing is available but LDA is missing or non-positive.")
        if physical_length is not None and lda is not None and lda > physical_length + TOLERANCE_M:
            warnings.append(f"{label}: LDA exceeds physical runway length.")
    else:
        if _positive(lda):
            warnings.append(f"{label}: landing is unavailable but LDA is populated.")

    return warnings


def _merge_record_notes(record: Dict[str, Any], warnings: List[str]) -> None:
    existing = [part.strip() for part in str(record.get("notes") or "").split(";") if part.strip()]
    merged = _unique_preserving_order(existing + warnings)
    record["warnings"] = _unique_preserving_order(list(record.get("warnings") or []) + warnings)
    record["notes"] = "; ".join(merged)


def _first_number(values: Iterable[Any]) -> Optional[float]:
    for value in values:
        parsed = _number_or_none(value)
        if parsed is not None:
            return parsed
    return None


def _number_or_none(value: Any) -> Optional[float]:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _number_or_zero(value: Any) -> float:
    parsed = _number_or_none(value)
    return parsed if parsed is not None else 0.0


def _bool_value(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() not in {"0", "false", "no", "off", ""}


def _positive(value: Optional[float]) -> bool:
    return value is not None and value > TOLERANCE_M


def _format_m(value: float) -> str:
    return f"{value:.3f}".rstrip("0").rstrip(".") + " m"


def _unique_preserving_order(values: Iterable[str]) -> List[str]:
    seen = set()
    result = []
    for value in values:
        text = str(value).strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result
