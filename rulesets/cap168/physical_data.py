"""UK CAA CAP 168 physical runway dimension policy."""

from typing import Any, Dict, Optional

SOURCE_PUBLICATION = "UK CAA CAP 168 Licensing of Aerodromes, Edition 13"
SOURCE_URL = "https://www.caa.co.uk/CAP168"

RUNWAY_WIDTH_CAP168_REF = "CAP 168 3.20 Table 3.2"
DECLARED_DISTANCE_CAP168_REF = "CAP 168 3.19"
CLEARWAY_CAP168_REF = "CAP 168 3.176-3.185"
STOPWAY_CAP168_REF = "CAP 168 3.186-3.195"
PAVEMENT_CAP168_REF = "CAP 168 Chapter 3"
SHOULDER_CAP168_REF = "CAP 168 3.37-3.45"

RUNWAY_WIDTH_PARAMS: Dict[int, Dict[str, Any]] = {
    1: {
        "lt_4_5_m": 18.0,
        "ge_4_5_lt_6_m": 18.0,
        "ge_6_lt_9_m": 23.0,
        "ge_9_lt_15_m": None,
        "precision_min_width_m": 30.0,
        "ref": RUNWAY_WIDTH_CAP168_REF,
    },
    2: {
        "lt_4_5_m": 23.0,
        "ge_4_5_lt_6_m": 23.0,
        "ge_6_lt_9_m": 30.0,
        "ge_9_lt_15_m": None,
        "precision_min_width_m": 30.0,
        "ref": RUNWAY_WIDTH_CAP168_REF,
    },
    3: {
        "lt_4_5_m": 30.0,
        "ge_4_5_lt_6_m": 30.0,
        "ge_6_lt_9_m": 30.0,
        "ge_9_lt_15_m": 45.0,
        "precision_min_width_m": None,
        "ref": RUNWAY_WIDTH_CAP168_REF,
    },
    4: {
        "lt_4_5_m": None,
        "ge_4_5_lt_6_m": None,
        "ge_6_lt_9_m": 45.0,
        "ge_9_lt_15_m": 45.0,
        "precision_min_width_m": None,
        "ref": RUNWAY_WIDTH_CAP168_REF,
    },
}

DECLARED_DISTANCE_PARAMS = {
    "distance_keys": ("tora_m", "toda_m", "asda_m", "lda_m"),
    "approval": "approved_and_promulgated_by_caa",
    "ref": DECLARED_DISTANCE_CAP168_REF,
}

CLEARWAY_PARAMS = {
    "origin_width_m": 150.0,
    "final_width_by_code_number_m": {1: 150.0, 2: 150.0, 3: 180.0, 4: 180.0},
    "max_length_factor_tora": 0.5,
    "default_length_m": 0.0,
    "slope": 0.0125,
    "slope_code_1_2": 0.02,
    "origin": "end_of_takeoff_run_available",
    "ref": CLEARWAY_CAP168_REF,
}

STOPWAY_PARAMS = {
    "width": "same_as_runway",
    "ref": STOPWAY_CAP168_REF,
}

PHYSICAL_TRACEABILITY = {
    "source_publication": SOURCE_PUBLICATION,
    "source_url": SOURCE_URL,
    "items": {
        "runway_width": {
            "source": RUNWAY_WIDTH_CAP168_REF,
            "status": "operational_verified",
            "implementation": "RUNWAY_WIDTH_PARAMS and runway_minimum_width",
            "notes": "Selected by code number and outer main gear wheel span band.",
        },
        "declared_distances": {
            "source": DECLARED_DISTANCE_CAP168_REF,
            "status": "operational_verified",
            "implementation": "DECLARED_DISTANCE_PARAMS",
            "notes": "TORA, TODA, ASDA, and LDA are declared for each runway direction and approved/promulgated by the CAA.",
        },
        "clearway": {
            "source": CLEARWAY_CAP168_REF,
            "status": "operational_verified",
            "implementation": "CLEARWAY_PARAMS and get_clearway_params",
            "notes": "Clearway length is capped at 50% TORA; width is selected conservatively from the end-of-TODA width by code number.",
        },
        "stopway": {
            "source": STOPWAY_CAP168_REF,
            "status": "operational_verified",
            "implementation": "STOPWAY_PARAMS and get_stopway_params",
            "notes": "Stopway width follows the associated runway width; entered length contributes to ASDA.",
        },
    },
}


def get_physical_refs() -> dict:
    return {"pavement": PAVEMENT_CAP168_REF, "shoulder": SHOULDER_CAP168_REF}


def get_physical_traceability() -> dict:
    return PHYSICAL_TRACEABILITY.copy()


def runway_minimum_width(
    code_number: Optional[int],
    outer_main_gear_wheel_span_m: Optional[float] = None,
    runway_type: Optional[str] = None,
):
    if not isinstance(code_number, int) or code_number not in RUNWAY_WIDTH_PARAMS:
        return None

    band_key = _omgws_band_key(outer_main_gear_wheel_span_m)
    if not band_key:
        return None

    params = RUNWAY_WIDTH_PARAMS[code_number]
    width_m = params.get(band_key)
    if width_m is None:
        return None

    precision_min = params.get("precision_min_width_m")
    if precision_min and _runway_is_precision(runway_type):
        width_m = max(float(width_m), float(precision_min))

    return {
        "width_m": float(width_m),
        "code_number": code_number,
        "outer_main_gear_wheel_span_band": band_key,
        "ref": params["ref"],
        "ref_cap168": params["ref"],
    }


def get_strip_params(arc_num: int, type_abbr: str, runway_width: Optional[float]) -> dict:
    del arc_num, type_abbr, runway_width
    return {
        "overall_width": None,
        "graded_width": None,
        "extension_length": None,
        "overall_width_ref": "N/A",
        "graded_width_ref": "N/A",
        "extension_length_ref": "N/A",
    }


def get_resa_params(arc_num: int, type1_abbr: str, type2_abbr: str) -> dict:
    del arc_num, type1_abbr, type2_abbr
    return {
        "required": False,
        "length": None,
        "applicability_ref": "N/A",
        "length_ref": "N/A",
        "width_ref": "N/A",
    }


def get_declared_distance_params() -> dict:
    return dict(DECLARED_DISTANCE_PARAMS)


def get_clearway_params(
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
    del runway_width, strip_extension, strip_overall_width, stopway_primary, stopway_reciprocal, is_instrument_runway

    max_length = _positive_or_none(physical_length)
    if max_length is not None:
        max_length *= CLEARWAY_PARAMS["max_length_factor_tora"]

    final_width = _clearway_final_width(arc_num)
    return {
        "primary": _clearway_end_params(clearway_primary_input, max_length, final_width),
        "reciprocal": _clearway_end_params(clearway_reciprocal_input, max_length, final_width),
    }


def get_stopway_params(runway_width: Optional[float] = None, stopway_length: Optional[float] = None) -> Dict[str, Any]:
    width = _non_negative_float(runway_width, 0.0)
    length = _non_negative_float(stopway_length, 0.0)
    return {
        "length_m": round(length, 3),
        "width_m": round(width, 3),
        "ref": STOPWAY_CAP168_REF,
        "ref_cap168": STOPWAY_CAP168_REF,
    }


def _clearway_end_params(input_length: Optional[float], max_length: Optional[float], final_width: float) -> Dict[str, Any]:
    input_length_m = _non_negative_float(input_length, 0.0)
    effective_length = input_length_m
    source = "input" if input_length_m > 1e-6 else "none"
    capped = False

    if max_length is not None and effective_length > max_length:
        effective_length = max_length
        capped = True
        source = f"{source}; capped"

    slope = CLEARWAY_PARAMS["slope"]
    if final_width <= CLEARWAY_PARAMS["origin_width_m"]:
        slope = CLEARWAY_PARAMS["slope_code_1_2"]

    return {
        "length_m": round(effective_length, 3),
        "width_m": round(final_width, 3),
        "origin_width_m": CLEARWAY_PARAMS["origin_width_m"],
        "input_length_m": round(input_length_m, 3),
        "default_length_m": CLEARWAY_PARAMS["default_length_m"],
        "source": source,
        "capped": capped,
        "max_length_m": round(max_length, 3) if max_length is not None else None,
        "max_slope": slope,
        "ref": CLEARWAY_CAP168_REF,
        "ref_cap168": CLEARWAY_CAP168_REF,
    }


def _clearway_final_width(arc_num: Optional[int]) -> float:
    try:
        code_number = int(arc_num)
    except (TypeError, ValueError):
        code_number = 1
    return float(CLEARWAY_PARAMS["final_width_by_code_number_m"].get(code_number, CLEARWAY_PARAMS["origin_width_m"]))


def _omgws_band_key(outer_main_gear_wheel_span_m: Optional[float]) -> Optional[str]:
    try:
        omgws = float(outer_main_gear_wheel_span_m)
    except (TypeError, ValueError):
        return None
    if omgws < 0:
        return None
    if omgws < 4.5:
        return "lt_4_5_m"
    if omgws < 6.0:
        return "ge_4_5_lt_6_m"
    if omgws < 9.0:
        return "ge_6_lt_9_m"
    if omgws < 15.0:
        return "ge_9_lt_15_m"
    return None


def _runway_is_precision(runway_type: Optional[str]) -> bool:
    value = (runway_type or "").strip().upper()
    return value in {"PA_I", "PA_II_III", "PRECISION APPROACH CAT I", "PRECISION APPROACH CAT II/III"}


def _non_negative_float(value: Optional[float], default: float = 0.0) -> float:
    try:
        parsed = float(value)
        return parsed if parsed >= 0 else default
    except (TypeError, ValueError):
        return default


def _positive_or_none(value: Optional[float]) -> Optional[float]:
    parsed = _non_negative_float(value, 0.0)
    return parsed if parsed > 0 else None


__all__ = [
    "SOURCE_PUBLICATION",
    "SOURCE_URL",
    "RUNWAY_WIDTH_CAP168_REF",
    "DECLARED_DISTANCE_CAP168_REF",
    "CLEARWAY_CAP168_REF",
    "STOPWAY_CAP168_REF",
    "PAVEMENT_CAP168_REF",
    "SHOULDER_CAP168_REF",
    "RUNWAY_WIDTH_PARAMS",
    "DECLARED_DISTANCE_PARAMS",
    "CLEARWAY_PARAMS",
    "STOPWAY_PARAMS",
    "PHYSICAL_TRACEABILITY",
    "get_physical_refs",
    "get_physical_traceability",
    "runway_minimum_width",
    "get_strip_params",
    "get_resa_params",
    "get_declared_distance_params",
    "get_clearway_params",
    "get_stopway_params",
]
