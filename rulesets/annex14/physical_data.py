"""ICAO Annex 14 physical inputs required by current conventional OLS."""

from __future__ import annotations

from typing import Any, Dict, Optional

SOURCE_PUBLICATION = "ICAO Annex 14, Volume I, Ninth Edition, Amendment 18"
STRIP_LENGTH_REF = "Annex 14 Vol I 3.4.2, printed pages 3-10 to 3-11"
STRIP_WIDTH_REF = "Annex 14 Vol I 3.4.3-3.4.5, printed page 3-11"
STRIP_GRADED_REF = "Annex 14 Vol I 3.4.8-3.4.9, printed page 3-12"
CLEARWAY_REF = "Annex 14 Vol I 3.6.1-3.6.3, printed page 3-16"
STOPWAY_REF = "Annex 14 Vol I 3.7.1, printed page 3-16"

PHYSICAL_REFS = {
    "status": "current_ols_dependencies_source_loaded",
    "strip": f"{STRIP_LENGTH_REF}; {STRIP_WIDTH_REF}; {STRIP_GRADED_REF}",
    "clearway": CLEARWAY_REF,
    "stopway": STOPWAY_REF,
}


def get_physical_refs() -> dict:
    return dict(PHYSICAL_REFS)


def get_current_strip_params(
    arc_num: int,
    type_abbr: str,
    runway_width: Optional[float],
) -> Dict[str, Any]:
    del runway_width
    try:
        code = int(arc_num)
    except (TypeError, ValueError):
        code = 0
    runway_type = str(type_abbr or "NI").upper()
    instrument = runway_type in {"NPA", "PA_I", "PA_II_III"}
    if code not in {1, 2, 3, 4}:
        return {}

    extension = 30.0 if code == 1 and not instrument else 60.0
    if instrument:
        lateral = 140.0 if code in {3, 4} else 70.0
        graded_lateral = 75.0 if code in {3, 4} else 40.0
    else:
        lateral = {1: 30.0, 2: 40.0, 3: 55.0, 4: 75.0}[code]
        graded_lateral = lateral
    return {
        "overall_width": lateral * 2.0,
        "graded_width": graded_lateral * 2.0,
        "extension_length": extension,
        "overall_width_ref": STRIP_WIDTH_REF,
        "graded_width_ref": STRIP_GRADED_REF,
        "extension_length_ref": STRIP_LENGTH_REF,
        "ref": f"{STRIP_LENGTH_REF}; {STRIP_WIDTH_REF}; {STRIP_GRADED_REF}",
    }


def get_current_clearway_params(
    runway_width: Optional[float] = None,
    strip_extension: Optional[float] = None,
    strip_overall_width: Optional[float] = None,
    physical_length: Optional[float] = None,
    clearway_primary_input: Optional[float] = None,
    clearway_reciprocal_input: Optional[float] = None,
    stopway_primary: Optional[float] = None,
    stopway_reciprocal: Optional[float] = None,
    is_instrument_runway: bool = False,
    arc_num: Optional[int] = None,
) -> Dict[str, Dict[str, Any]]:
    del runway_width, strip_extension, stopway_primary, stopway_reciprocal, arc_num
    tora = _positive(physical_length)
    max_length = tora * 0.5 if tora is not None else None
    width = 150.0 if is_instrument_runway else float(strip_overall_width or 0.0)

    def end(value: Optional[float]) -> Dict[str, Any]:
        entered = max(0.0, float(value or 0.0))
        effective = min(entered, max_length) if max_length is not None else entered
        return {
            "length_m": round(effective, 3),
            "width_m": round(width, 3),
            "input_length_m": round(entered, 3),
            "default_length_m": 0.0,
            "source": "input" if entered > 0.0 else "none",
            "capped": effective < entered,
            "max_length_m": round(max_length, 3) if max_length is not None else None,
            "ref": CLEARWAY_REF,
        }

    return {
        "primary": end(clearway_primary_input),
        "reciprocal": end(clearway_reciprocal_input),
    }


def get_current_stopway_params(
    runway_width: Optional[float] = None,
    stopway_length: Optional[float] = None,
) -> Dict[str, Any]:
    return {
        "width_m": max(0.0, float(runway_width or 0.0)),
        "length_m": max(0.0, float(stopway_length or 0.0)),
        "ref": STOPWAY_REF,
    }


def get_strip_params(arc_num: int, type_abbr: str, runway_width: Optional[float]):
    """Future OFS/OES profile remains physically unsupported."""
    del arc_num, type_abbr, runway_width
    return None


def get_resa_params(arc_num: int, type1_abbr: str, type2_abbr: str):
    del arc_num, type1_abbr, type2_abbr
    return None


def _positive(value: Optional[float]) -> Optional[float]:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0.0 else None


__all__ = [
    "CLEARWAY_REF",
    "PHYSICAL_REFS",
    "STOPWAY_REF",
    "STRIP_GRADED_REF",
    "STRIP_LENGTH_REF",
    "STRIP_WIDTH_REF",
    "get_current_clearway_params",
    "get_current_stopway_params",
    "get_current_strip_params",
    "get_physical_refs",
    "get_resa_params",
    "get_strip_params",
]
