"""UK CAA CAP 168 physical runway dimension policy."""

from typing import Any, Dict, Optional

SOURCE_PUBLICATION = "UK CAA CAP 168 Licensing of Aerodromes, Edition 13"
SOURCE_URL = "https://www.caa.co.uk/CAP168"

RUNWAY_WIDTH_CAP168_REF = "CAP 168 3.20 Table 3.2"
STRIP_PURPOSE_CAP168_REF = "CAP 168 3.69"
STRIP_CONSTRUCTION_CAP168_REF = "CAP 168 3.71-3.73"
STRIP_LENGTH_CAP168_REF = "CAP 168 3.76-3.77"
STRIP_WIDTH_CAP168_REF = "CAP 168 3.78-3.84"
STRIP_GRADED_AREA_CAP168_REF = "CAP 168 3.91-3.94"
STRIP_STRENGTH_CAP168_REF = "CAP 168 3.95-3.97"
STRIP_SLOPES_CAP168_REF = "CAP 168 3.98-3.101"
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

STRIP_EXTENSION_PARAMS = {
    "1_NI": {"length": 30.0, "ref": "CAP 168 3.76(2)"},
    "DEFAULT": {"length": 60.0, "ref": "CAP 168 3.76(1)"},
}

VISUAL_STRIP_LATERAL_PARAMS = {
    1: {"distance_each_side_m": 30.0, "ref": "CAP 168 3.78(4)"},
    2: {"distance_each_side_m": 40.0, "ref": "CAP 168 3.78(3)"},
    3: {"distance_each_side_m": 55.0, "ref": "CAP 168 3.78(2)"},
    4: {"distance_each_side_m": 75.0, "ref": "CAP 168 3.78(1)"},
}

INSTRUMENT_STRIP_LATERAL_PARAMS = {
    1: {"distance_each_side_m": 70.0, "ref": "CAP 168 3.81(2)"},
    2: {"distance_each_side_m": 70.0, "ref": "CAP 168 3.81(2)"},
    3: {"distance_each_side_m": 140.0, "ref": "CAP 168 3.81(1)"},
    4: {"distance_each_side_m": 140.0, "ref": "CAP 168 3.81(1)"},
}

GRADED_AREA_LATERAL_PARAMS = {
    "PA_3_4": {"distance_each_side_m": 75.0, "ref": "CAP 168 3.91"},
    "PA_1_2": {"distance_each_side_m": 40.0, "ref": "CAP 168 3.93"},
    "NI_NPA": VISUAL_STRIP_LATERAL_PARAMS,
}

STRIP_VARIATION_PARAMS = {
    "code_3_non_instrument_rnp_apch": {
        "distance_each_side_m": 75.0,
        "ref": "CAP 168 3.79",
        "approval": "CAA approval required to reduce to 55 m each side",
    },
    "wide_non_instrument_runway": {
        1: {"edge_margin_m": 21.0, "ref": "CAP 168 3.80(2)"},
        2: {"edge_margin_m": 28.0, "ref": "CAP 168 3.80(1)"},
    },
    "starter_extension": {
        "safety_margin_m": 7.5,
        "wingspan_factor": 0.2,
        "splay_each_side": 0.2,
        "ref": "CAP 168 3.77, 3.83-3.84",
    },
    "precision_code_3_4_optional_end_graded_area": {
        "start_width_each_side_m": 75.0,
        "increased_width_each_side_m": 105.0,
        "start_length_m": 150.0,
        "transition_complete_by_m": 300.0,
        "ref": "CAP 168 3.92",
        "condition": "Subject to a satisfactory safety assessment.",
    },
}

STRIP_CONSTRUCTION_PARAMS = {
    "delethalisation": {
        "slope": "1:10",
        "below_ground_depth_m": 0.3,
        "ref": "CAP 168 3.71-3.72",
    },
    "emergency_vehicle_access": {"required": True, "ref": "CAP 168 3.73"},
    "flush_edges": {
        "requirement": "flush_with_runway_shoulder_and_stopway_common_edges",
        "ref": "CAP 168 3.95",
    },
    "blast_erosion_before_threshold_m": {"distance_m": 30.0, "ref": "CAP 168 3.96"},
    "bearing_strength": {
        "requirement": "minimise_hazards_from_load_bearing_capacity_differences",
        "ref": "CAP 168 3.95, 3.97",
    },
}

STRIP_SLOPE_PARAMS = {
    1: {"max_longitudinal_slope": 0.02, "max_transverse_slope": 0.03, "ref": STRIP_SLOPES_CAP168_REF},
    2: {"max_longitudinal_slope": 0.02, "max_transverse_slope": 0.03, "ref": STRIP_SLOPES_CAP168_REF},
    3: {"max_longitudinal_slope": 0.0175, "max_transverse_slope": 0.025, "ref": STRIP_SLOPES_CAP168_REF},
    4: {"max_longitudinal_slope": 0.015, "max_transverse_slope": 0.025, "ref": STRIP_SLOPES_CAP168_REF},
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
        "strip_length": {
            "source": STRIP_LENGTH_CAP168_REF,
            "status": "operational_verified",
            "implementation": "STRIP_EXTENSION_PARAMS",
            "notes": "Stores strip extension before threshold and beyond runway/stopway end.",
        },
        "strip_width": {
            "source": STRIP_WIDTH_CAP168_REF,
            "status": "operational_verified",
            "implementation": "VISUAL_STRIP_LATERAL_PARAMS and INSTRUMENT_STRIP_LATERAL_PARAMS",
            "notes": "CAP168 gives lateral distances each side; returned widths are total widths.",
        },
        "strip_graded_area": {
            "source": STRIP_GRADED_AREA_CAP168_REF,
            "status": "operational_verified",
            "implementation": "GRADED_AREA_LATERAL_PARAMS",
            "notes": "Cleared-and-graded widths are returned as total widths.",
        },
        "strip_construction_variations": {
            "source": f"{STRIP_CONSTRUCTION_CAP168_REF}, {STRIP_STRENGTH_CAP168_REF}, {STRIP_SLOPES_CAP168_REF}",
            "status": "operational_verified",
            "implementation": "STRIP_VARIATION_PARAMS, STRIP_CONSTRUCTION_PARAMS, STRIP_SLOPE_PARAMS",
            "notes": "Captures starter-extension, wide non-instrument runway, Code 3 RNP APCH, graded-area, construction, strength, and slope variations.",
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


def get_strip_params(
    arc_num: int,
    type_abbr: str,
    runway_width: Optional[float],
    has_rnp_apch: bool = False,
    minimum_runway_width_m: Optional[float] = None,
    starter_extension: bool = False,
    wingspan_m: Optional[float] = None,
    wing_overhang_m: Optional[float] = None,
) -> dict:
    results = {
        "overall_width": None,
        "graded_width": None,
        "extension_length": None,
        "overall_width_ref": "N/A",
        "graded_width_ref": "N/A",
        "extension_length_ref": "N/A",
        "cap168_overall_width_ref": "N/A",
        "cap168_graded_width_ref": "N/A",
        "cap168_extension_length_ref": "N/A",
        "construction": dict(STRIP_CONSTRUCTION_PARAMS),
        "slope_limits": None,
        "variations": dict(STRIP_VARIATION_PARAMS),
    }

    if not isinstance(arc_num, int) or arc_num not in [1, 2, 3, 4]:
        return results

    type_abbr = (type_abbr or "").upper()
    is_ni = type_abbr == "NI"

    ext_key = "1_NI" if arc_num == 1 and is_ni else "DEFAULT"
    ext_params = STRIP_EXTENSION_PARAMS[ext_key]
    results["extension_length"] = ext_params["length"]
    results["cap168_extension_length_ref"] = ext_params["ref"]
    results["extension_length_ref"] = results["cap168_extension_length_ref"]

    overall = _overall_strip_lateral_params(arc_num, type_abbr, has_rnp_apch)
    if overall:
        overall_lateral = float(overall["distance_each_side_m"])
        overall_width = overall_lateral * 2.0
        wide_variation = _wide_non_instrument_strip_width(arc_num, type_abbr, runway_width, minimum_runway_width_m)
        if wide_variation and wide_variation["overall_width"] > overall_width:
            overall_width = wide_variation["overall_width"]
            results["wide_non_instrument_variation"] = wide_variation
        results["overall_width"] = round(overall_width, 3)
        results["cap168_overall_width_ref"] = overall["ref"]
        results["overall_width_ref"] = results["cap168_overall_width_ref"]

    graded = _graded_area_lateral_params(arc_num, type_abbr, has_rnp_apch)
    if graded:
        results["graded_width"] = round(float(graded["distance_each_side_m"]) * 2.0, 3)
        results["cap168_graded_width_ref"] = graded["ref"]
        results["graded_width_ref"] = results["cap168_graded_width_ref"]

    slope_params = STRIP_SLOPE_PARAMS.get(arc_num)
    if slope_params:
        results["slope_limits"] = {
            **slope_params,
            "outer_area_max_upward_transverse_slope": 0.05,
            "first_3m_negative_transverse_slope_max": 0.05,
        }

    starter_params = _starter_extension_params(starter_extension, wingspan_m, wing_overhang_m)
    if starter_params:
        results["starter_extension"] = starter_params

    return results


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


def _overall_strip_lateral_params(arc_num: int, type_abbr: str, has_rnp_apch: bool):
    if type_abbr == "NI":
        if arc_num == 3 and has_rnp_apch:
            return STRIP_VARIATION_PARAMS["code_3_non_instrument_rnp_apch"]
        return VISUAL_STRIP_LATERAL_PARAMS.get(arc_num)
    return INSTRUMENT_STRIP_LATERAL_PARAMS.get(arc_num)


def _graded_area_lateral_params(arc_num: int, type_abbr: str, has_rnp_apch: bool):
    if type_abbr == "NI":
        if arc_num == 3 and has_rnp_apch:
            return STRIP_VARIATION_PARAMS["code_3_non_instrument_rnp_apch"]
        return VISUAL_STRIP_LATERAL_PARAMS.get(arc_num)
    if type_abbr == "NPA":
        return VISUAL_STRIP_LATERAL_PARAMS.get(arc_num)
    if type_abbr in {"PA_I", "PA_II_III"} and arc_num in [3, 4]:
        return GRADED_AREA_LATERAL_PARAMS["PA_3_4"]
    if type_abbr in {"PA_I", "PA_II_III"} and arc_num in [1, 2]:
        return GRADED_AREA_LATERAL_PARAMS["PA_1_2"]
    return None


def _wide_non_instrument_strip_width(
    arc_num: int,
    type_abbr: str,
    runway_width: Optional[float],
    minimum_runway_width_m: Optional[float],
):
    if type_abbr != "NI" or arc_num not in [1, 2]:
        return None
    width = _positive_or_none(runway_width)
    if width is None:
        return None
    minimum_width = _positive_or_none(minimum_runway_width_m) or _minimum_table_width_for_code(arc_num)
    if minimum_width is None or width < minimum_width * 1.1:
        return None
    variation = STRIP_VARIATION_PARAMS["wide_non_instrument_runway"][arc_num]
    return {
        "overall_width": round(width + 2.0 * variation["edge_margin_m"], 3),
        "runway_width_m": round(width, 3),
        "minimum_runway_width_m": round(minimum_width, 3),
        "edge_margin_m": variation["edge_margin_m"],
        "ref": variation["ref"],
    }


def _starter_extension_params(
    starter_extension: bool,
    wingspan_m: Optional[float],
    wing_overhang_m: Optional[float],
):
    if not starter_extension:
        return None
    params = STRIP_VARIATION_PARAMS["starter_extension"]
    margin = params["safety_margin_m"]
    wingspan = _positive_or_none(wingspan_m)
    if wingspan is not None:
        margin = max(margin, wingspan * params["wingspan_factor"])
    overhang = _non_negative_float(wing_overhang_m, 0.0)
    return {
        "lateral_margin_from_extension_edge_m": round(overhang + margin, 3),
        "wing_overhang_m": round(overhang, 3),
        "safety_margin_m": round(margin, 3),
        "splay_each_side": params["splay_each_side"],
        "ref": params["ref"],
    }


def _minimum_table_width_for_code(arc_num: int) -> Optional[float]:
    params = RUNWAY_WIDTH_PARAMS.get(arc_num)
    if not params:
        return None
    widths = [
        value
        for key, value in params.items()
        if key.endswith("_m") and isinstance(value, (float, int)) and key != "precision_min_width_m"
    ]
    return min(widths) if widths else None


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
    "STRIP_PURPOSE_CAP168_REF",
    "STRIP_CONSTRUCTION_CAP168_REF",
    "STRIP_LENGTH_CAP168_REF",
    "STRIP_WIDTH_CAP168_REF",
    "STRIP_GRADED_AREA_CAP168_REF",
    "STRIP_STRENGTH_CAP168_REF",
    "STRIP_SLOPES_CAP168_REF",
    "DECLARED_DISTANCE_CAP168_REF",
    "CLEARWAY_CAP168_REF",
    "STOPWAY_CAP168_REF",
    "PAVEMENT_CAP168_REF",
    "SHOULDER_CAP168_REF",
    "RUNWAY_WIDTH_PARAMS",
    "STRIP_EXTENSION_PARAMS",
    "VISUAL_STRIP_LATERAL_PARAMS",
    "INSTRUMENT_STRIP_LATERAL_PARAMS",
    "GRADED_AREA_LATERAL_PARAMS",
    "STRIP_VARIATION_PARAMS",
    "STRIP_CONSTRUCTION_PARAMS",
    "STRIP_SLOPE_PARAMS",
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
