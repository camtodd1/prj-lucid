"""OLS surface lookups for ICAO Annex 14 Volume I."""

from copy import deepcopy
from typing import Optional

from .classification import get_runway_type_abbr

APPROACH_SURFACE_REF = "Annex 14 Vol I 4.2.1"
APPROACH_NON_INSTRUMENT_REF = "Annex 14 Vol I Table 4-1"
APPROACH_INSTRUMENT_REF = "Annex 14 Vol I Table 4-2"
TRANSITIONAL_SURFACE_REF = "Annex 14 Vol I 4.2.2"
INNER_APPROACH_SURFACE_REF = "Annex 14 Vol I 4.2.3"
INNER_APPROACH_NON_INSTRUMENT_REF = "Annex 14 Vol I Table 4-3"
INNER_APPROACH_NON_PRECISION_REF = "Annex 14 Vol I Table 4-4"
INNER_APPROACH_PRECISION_REF = "Annex 14 Vol I Table 4-5"
INNER_TRANSITIONAL_SURFACE_REF = "Annex 14 Vol I 4.2.4"
INNER_TRANSITIONAL_NON_INSTRUMENT_REF = "Annex 14 Vol I Table 4-6"
INNER_TRANSITIONAL_NON_PRECISION_REF = "Annex 14 Vol I Table 4-7"
INNER_TRANSITIONAL_PRECISION_REF = "Annex 14 Vol I Table 4-8"
BALKED_LANDING_SURFACE_REF = "Annex 14 Vol I 4.2.5"
BALKED_LANDING_REF = "Annex 14 Vol I Table 4-9"

TRANSITIONAL_SURFACE = {
    "surface": "transitional",
    "slope": 0.20,
    "upper_edge_height_above_highest_threshold_m": 60.0,
    "lower_edge_ref": "Annex 14 Vol I 4.2.2.2 and 4.2.2.3",
    "slope_ref": "Annex 14 Vol I 4.2.2.5",
    "ref": TRANSITIONAL_SURFACE_REF,
}

NON_INSTRUMENT_APPROACH_SURFACE = {
    "I": {
        "distance_from_threshold_m": 30.0,
        "inner_edge_length_m": 60.0,
        "divergence": 0.10,
        "length_m": 1600.0,
        "slope": 0.05,
        "ref": APPROACH_NON_INSTRUMENT_REF,
    },
    "IIA-IIB": {
        "distance_from_threshold_m": 60.0,
        "inner_edge_length_m": 80.0,
        "divergence": 0.10,
        "length_m": 2500.0,
        "slope": 0.04,
        "ref": APPROACH_NON_INSTRUMENT_REF,
    },
    "IIC": {
        "distance_from_threshold_m": 60.0,
        "inner_edge_length_m": 100.0,
        "divergence": 0.10,
        "length_m": 2500.0,
        "slope": 0.0333,
        "ref": APPROACH_NON_INSTRUMENT_REF,
    },
    "III": {
        "distance_from_threshold_m": 60.0,
        "inner_edge_length_m": 125.0,
        "divergence": 0.10,
        "length_m": 2500.0,
        "slope": 0.0333,
        "ref": APPROACH_NON_INSTRUMENT_REF,
    },
    "IV": {
        "distance_from_threshold_m": 60.0,
        "inner_edge_length_m": 135.0,
        "divergence": 0.10,
        "length_m": 2500.0,
        "slope": 0.0333,
        "ref": APPROACH_NON_INSTRUMENT_REF,
    },
    "V": {
        "distance_from_threshold_m": 60.0,
        "inner_edge_length_m": 150.0,
        "divergence": 0.10,
        "length_m": 2500.0,
        "slope": 0.0333,
        "ref": APPROACH_NON_INSTRUMENT_REF,
    },
}

INSTRUMENT_APPROACH_SURFACE = {
    "I": {
        "distance_from_threshold_m": 60.0,
        "inner_edge_length_m": 110.0,
        "divergence": 0.10,
        "length_m": 4500.0,
        "slope": 0.0333,
        "ref": APPROACH_INSTRUMENT_REF,
    },
    "IIA-IIB": {
        "distance_from_threshold_m": 60.0,
        "inner_edge_length_m": 125.0,
        "divergence": 0.10,
        "length_m": 4500.0,
        "slope": 0.0333,
        "ref": APPROACH_INSTRUMENT_REF,
    },
    "IIC": {
        "distance_from_threshold_m": 60.0,
        "inner_edge_length_m": 155.0,
        "divergence": 0.10,
        "length_m": 4500.0,
        "slope": 0.0333,
        "ref": APPROACH_INSTRUMENT_REF,
    },
    "III": {
        "distance_from_threshold_m": 60.0,
        "inner_edge_length_m": 175.0,
        "divergence": 0.10,
        "length_m": 4500.0,
        "slope": 0.0333,
        "ref": APPROACH_INSTRUMENT_REF,
    },
    "IV": {
        "distance_from_threshold_m": 60.0,
        "inner_edge_length_m": 185.0,
        "divergence": 0.10,
        "length_m": 4500.0,
        "slope": 0.0333,
        "ref": APPROACH_INSTRUMENT_REF,
    },
    "V": {
        "distance_from_threshold_m": 60.0,
        "inner_edge_length_m": 200.0,
        "divergence": 0.10,
        "length_m": 4500.0,
        "slope": 0.0333,
        "ref": APPROACH_INSTRUMENT_REF,
    },
}

NON_INSTRUMENT_INNER_APPROACH_SURFACE = {
    "I": {"inner_edge_length_m": 60.0, "length_m": 900.0, "ref": INNER_APPROACH_NON_INSTRUMENT_REF},
    "IIA-IIB": {"inner_edge_length_m": 80.0, "length_m": 1125.0, "ref": INNER_APPROACH_NON_INSTRUMENT_REF},
    "IIC": {"inner_edge_length_m": 100.0, "length_m": 1350.0, "ref": INNER_APPROACH_NON_INSTRUMENT_REF},
    "III": {"inner_edge_length_m": 110.0, "length_m": 1350.0, "ref": INNER_APPROACH_NON_INSTRUMENT_REF},
    "IV": {"inner_edge_length_m": 120.0, "length_m": 1350.0, "ref": INNER_APPROACH_NON_INSTRUMENT_REF},
    "V": {"inner_edge_length_m": 120.0, "length_m": 1350.0, "ref": INNER_APPROACH_NON_INSTRUMENT_REF},
}

NON_PRECISION_INNER_APPROACH_SURFACE = {
    "I": {"inner_edge_length_m": 80.0, "length_m": 1350.0, "ref": INNER_APPROACH_NON_PRECISION_REF},
    "IIA-IIB": {"inner_edge_length_m": 80.0, "length_m": 1350.0, "ref": INNER_APPROACH_NON_PRECISION_REF},
    "IIC": {"inner_edge_length_m": 120.0, "length_m": 1350.0, "ref": INNER_APPROACH_NON_PRECISION_REF},
    "III": {"inner_edge_length_m": 120.0, "length_m": 1350.0, "ref": INNER_APPROACH_NON_PRECISION_REF},
    "IV": {"inner_edge_length_m": 120.0, "length_m": 1350.0, "ref": INNER_APPROACH_NON_PRECISION_REF},
    "V": {"inner_edge_length_m": 120.0, "length_m": 1350.0, "ref": INNER_APPROACH_NON_PRECISION_REF},
}

PRECISION_INNER_APPROACH_SURFACE = {
    "I": {"inner_edge_length_m": 90.0, "length_m": 1350.0, "ref": INNER_APPROACH_PRECISION_REF},
    "IIA-IIB": {"inner_edge_length_m": 90.0, "length_m": 1350.0, "ref": INNER_APPROACH_PRECISION_REF},
    "IIC": {"inner_edge_length_m": 120.0, "length_m": 1350.0, "ref": INNER_APPROACH_PRECISION_REF},
    "III": {"inner_edge_length_m": 120.0, "length_m": 1350.0, "ref": INNER_APPROACH_PRECISION_REF},
    "IV": {"inner_edge_length_m": 120.0, "length_m": 1350.0, "ref": INNER_APPROACH_PRECISION_REF},
    "V": {"inner_edge_length_m": 120.0, "length_m": 1350.0, "ref": INNER_APPROACH_PRECISION_REF},
}

NON_INSTRUMENT_INNER_TRANSITIONAL_SURFACE = {
    "I": {
        "vertical_section_height_m": 6.0,
        "inclined_section_slope": 0.40,
        "length_m": None,
        "length_rule": "to_end_of_strip",
        "length_ref": f"{INNER_TRANSITIONAL_NON_INSTRUMENT_REF} note a",
        "ref": INNER_TRANSITIONAL_NON_INSTRUMENT_REF,
    },
    "IIA-IIB": {
        "vertical_section_height_m": 6.0,
        "inclined_section_slope": 0.40,
        "length_m": None,
        "length_rule": "to_end_of_strip",
        "length_ref": f"{INNER_TRANSITIONAL_NON_INSTRUMENT_REF} note a",
        "ref": INNER_TRANSITIONAL_NON_INSTRUMENT_REF,
    },
    "IIC": {
        "vertical_section_height_m": 8.4,
        "inclined_section_slope": 0.333,
        "length_m": 1800.0,
        "length_rule": "1800_m_or_end_of_runway_whichever_is_less",
        "length_ref": f"{INNER_TRANSITIONAL_NON_INSTRUMENT_REF} note b",
        "ref": INNER_TRANSITIONAL_NON_INSTRUMENT_REF,
    },
    "III": {
        "vertical_section_height_m": 10.0,
        "inclined_section_slope": 0.333,
        "length_m": 1800.0,
        "length_rule": "1800_m_or_end_of_runway_whichever_is_less",
        "length_ref": f"{INNER_TRANSITIONAL_NON_INSTRUMENT_REF} note b",
        "ref": INNER_TRANSITIONAL_NON_INSTRUMENT_REF,
    },
    "IV": {
        "vertical_section_height_m": 5.0,
        "inclined_section_slope": 0.333,
        "length_m": 1800.0,
        "length_rule": "1800_m_or_end_of_runway_whichever_is_less",
        "length_ref": f"{INNER_TRANSITIONAL_NON_INSTRUMENT_REF} note b",
        "ref": INNER_TRANSITIONAL_NON_INSTRUMENT_REF,
    },
    "V": {
        "vertical_section_height_m": 5.0,
        "inclined_section_slope": 0.333,
        "length_m": 1800.0,
        "length_rule": "1800_m_or_end_of_runway_whichever_is_less",
        "length_ref": f"{INNER_TRANSITIONAL_NON_INSTRUMENT_REF} note b",
        "ref": INNER_TRANSITIONAL_NON_INSTRUMENT_REF,
    },
}

NON_PRECISION_INNER_TRANSITIONAL_SURFACE = {
    "I": {
        "vertical_section_height_m": 6.0,
        "inclined_section_slope": 0.40,
        "length_m": None,
        "length_rule": "to_end_of_strip",
        "length_ref": f"{INNER_TRANSITIONAL_NON_PRECISION_REF} note a",
        "ref": INNER_TRANSITIONAL_NON_PRECISION_REF,
    },
    "IIA-IIB": {
        "vertical_section_height_m": 6.0,
        "inclined_section_slope": 0.40,
        "length_m": None,
        "length_rule": "to_end_of_strip",
        "length_ref": f"{INNER_TRANSITIONAL_NON_PRECISION_REF} note a",
        "ref": INNER_TRANSITIONAL_NON_PRECISION_REF,
    },
    "IIC": {
        "vertical_section_height_m": 5.0,
        "inclined_section_slope": 0.333,
        "length_m": 1800.0,
        "length_rule": "1800_m_or_end_of_runway_whichever_is_less",
        "length_ref": f"{INNER_TRANSITIONAL_NON_PRECISION_REF} note b",
        "ref": INNER_TRANSITIONAL_NON_PRECISION_REF,
    },
    "III": {
        "vertical_section_height_m": 5.0,
        "inclined_section_slope": 0.333,
        "length_m": 1800.0,
        "length_rule": "1800_m_or_end_of_runway_whichever_is_less",
        "length_ref": f"{INNER_TRANSITIONAL_NON_PRECISION_REF} note b",
        "ref": INNER_TRANSITIONAL_NON_PRECISION_REF,
    },
    "IV": {
        "vertical_section_height_m": 5.0,
        "inclined_section_slope": 0.333,
        "length_m": 1800.0,
        "length_rule": "1800_m_or_end_of_runway_whichever_is_less",
        "length_ref": f"{INNER_TRANSITIONAL_NON_PRECISION_REF} note b",
        "ref": INNER_TRANSITIONAL_NON_PRECISION_REF,
    },
    "V": {
        "vertical_section_height_m": 5.0,
        "inclined_section_slope": 0.333,
        "length_m": 1800.0,
        "length_rule": "1800_m_or_end_of_runway_whichever_is_less",
        "length_ref": f"{INNER_TRANSITIONAL_NON_PRECISION_REF} note b",
        "ref": INNER_TRANSITIONAL_NON_PRECISION_REF,
    },
}

PRECISION_INNER_TRANSITIONAL_SURFACE = {
    "I": {
        "slope": 0.40,
        "length_m": None,
        "length_rule": "per_4_2_4_3",
        "length_ref": "Annex 14 Vol I 4.2.4.3",
        "ref": INNER_TRANSITIONAL_PRECISION_REF,
    },
    "IIA-IIB": {
        "slope": 0.40,
        "length_m": None,
        "length_rule": "per_4_2_4_3",
        "length_ref": "Annex 14 Vol I 4.2.4.3",
        "ref": INNER_TRANSITIONAL_PRECISION_REF,
    },
    "IIC": {
        "slope": 0.333,
        "length_m": None,
        "length_rule": "per_4_2_4_3",
        "length_ref": "Annex 14 Vol I 4.2.4.3",
        "ref": INNER_TRANSITIONAL_PRECISION_REF,
    },
    "III": {
        "slope": 0.333,
        "length_m": None,
        "length_rule": "per_4_2_4_3",
        "length_ref": "Annex 14 Vol I 4.2.4.3",
        "ref": INNER_TRANSITIONAL_PRECISION_REF,
    },
    "IV": {
        "slope": 0.333,
        "length_m": None,
        "length_rule": "per_4_2_4_3",
        "length_ref": "Annex 14 Vol I 4.2.4.3",
        "ref": INNER_TRANSITIONAL_PRECISION_REF,
    },
    "V": {
        "slope": 0.333,
        "length_m": None,
        "length_rule": "per_4_2_4_3",
        "length_ref": "Annex 14 Vol I 4.2.4.3",
        "ref": INNER_TRANSITIONAL_PRECISION_REF,
    },
}

BALKED_LANDING_SURFACE = {
    "I": {
        "distance_from_threshold_m": None,
        "distance_rule": "end_of_strip",
        "distance_ref": f"{BALKED_LANDING_REF} note a",
        "inner_edge_length_m": 90.0,
        "divergence": 0.10,
        "slope": 0.05,
        "ref": BALKED_LANDING_REF,
    },
    "IIA-IIB": {
        "distance_from_threshold_m": None,
        "distance_rule": "end_of_strip",
        "distance_ref": f"{BALKED_LANDING_REF} note a",
        "inner_edge_length_m": 90.0,
        "divergence": 0.10,
        "slope": 0.04,
        "ref": BALKED_LANDING_REF,
    },
    "IIC": {
        "distance_from_threshold_m": 1800.0,
        "distance_rule": "1800_m_or_end_of_runway_whichever_is_less",
        "distance_ref": f"{BALKED_LANDING_REF} note b",
        "inner_edge_length_m": 120.0,
        "divergence": 0.10,
        "slope": 0.0333,
        "ref": BALKED_LANDING_REF,
    },
    "III": {
        "distance_from_threshold_m": 1800.0,
        "distance_rule": "1800_m_or_end_of_runway_whichever_is_less",
        "distance_ref": f"{BALKED_LANDING_REF} note b",
        "inner_edge_length_m": 120.0,
        "divergence": 0.10,
        "slope": 0.0333,
        "ref": BALKED_LANDING_REF,
    },
    "IV": {
        "distance_from_threshold_m": 1800.0,
        "distance_rule": "1800_m_or_end_of_runway_whichever_is_less",
        "distance_ref": f"{BALKED_LANDING_REF} note b",
        "inner_edge_length_m": 120.0,
        "divergence": 0.10,
        "slope": 0.0333,
        "ref": BALKED_LANDING_REF,
    },
    "V": {
        "distance_from_threshold_m": 1800.0,
        "distance_rule": "1800_m_or_end_of_runway_whichever_is_less",
        "distance_ref": f"{BALKED_LANDING_REF} note b",
        "inner_edge_length_m": 120.0,
        "divergence": 0.10,
        "slope": 0.0333,
        "ref": BALKED_LANDING_REF,
    },
}


def _normalize_surface_type(surface_type: str) -> str:
    return (surface_type or "").strip().replace("_", " ").replace("-", " ").lower()


def _normalize_design_group(design_group: Optional[str]):
    if design_group is None:
        return None
    value = str(design_group).strip().upper().replace("ADG", "").replace("_", "").replace(" ", "")
    if value in {"IIA", "IIB"}:
        return "IIA-IIB"
    return value or None


def _is_instrument_runway(runway_type: Optional[str]) -> bool:
    return get_runway_type_abbr(runway_type) != "NI"


def _inner_approach_table_for_runway_type(runway_type: Optional[str]):
    runway_type_abbr = get_runway_type_abbr(runway_type)
    if runway_type_abbr == "NI":
        return NON_INSTRUMENT_INNER_APPROACH_SURFACE
    if runway_type_abbr == "NPA":
        return NON_PRECISION_INNER_APPROACH_SURFACE
    return PRECISION_INNER_APPROACH_SURFACE


def _inner_transitional_table_for_runway_type(runway_type: Optional[str]):
    runway_type_abbr = get_runway_type_abbr(runway_type)
    if runway_type_abbr == "NI":
        return NON_INSTRUMENT_INNER_TRANSITIONAL_SURFACE
    if runway_type_abbr == "NPA":
        return NON_PRECISION_INNER_TRANSITIONAL_SURFACE
    return PRECISION_INNER_TRANSITIONAL_SURFACE


def _apply_non_instrument_inner_edge_adjustments(params: dict, design_group: str, runway_width_m: Optional[float]):
    if runway_width_m is None:
        return
    if design_group == "I":
        if runway_width_m > 30.0:
            params["inner_edge_length_m"] = 100.0
            params["inner_edge_adjustment_ref"] = f"{APPROACH_NON_INSTRUMENT_REF} note b"
        elif runway_width_m > 23.0:
            params["inner_edge_length_m"] = 80.0
            params["inner_edge_adjustment_ref"] = f"{APPROACH_NON_INSTRUMENT_REF} note a"
    elif design_group == "IIA-IIB":
        if runway_width_m > 45.0:
            params["inner_edge_length_m"] = 110.0
            params["inner_edge_adjustment_ref"] = f"{APPROACH_NON_INSTRUMENT_REF} note d"
        elif runway_width_m > 30.0:
            params["inner_edge_length_m"] = 100.0
            params["inner_edge_adjustment_ref"] = f"{APPROACH_NON_INSTRUMENT_REF} note c"
    elif design_group == "IIC" and runway_width_m > 45.0:
        params["inner_edge_length_m"] = 110.0
        params["inner_edge_adjustment_ref"] = f"{APPROACH_NON_INSTRUMENT_REF} note d"


def _apply_instrument_inner_edge_adjustments(params: dict, design_group: str, runway_width_m: Optional[float]):
    if runway_width_m is None:
        return
    if design_group == "I" and runway_width_m > 30.0:
        params["inner_edge_length_m"] = 125.0
        params["inner_edge_adjustment_ref"] = f"{APPROACH_INSTRUMENT_REF} note a"
    elif design_group == "IIA-IIB" and runway_width_m > 30.0:
        params["inner_edge_length_m"] = 140.0
        params["inner_edge_adjustment_ref"] = f"{APPROACH_INSTRUMENT_REF} note b"
    elif design_group == "IIC" and runway_width_m <= 30.0:
        params["inner_edge_length_m"] = 140.0
        params["inner_edge_adjustment_ref"] = f"{APPROACH_INSTRUMENT_REF} note c"


def _apply_length_adjustments(
    params: dict,
    is_instrument: bool,
    slope: Optional[float],
    obstacle_clearance_height_m: Optional[float],
):
    base_length = params["length_m"]
    base_slope = params["slope"]
    effective_slope = slope if slope is not None else base_slope
    params["slope"] = effective_slope

    if effective_slope <= 0:
        return

    target_height_m = base_length * base_slope
    if slope is not None and slope < base_slope:
        params["length_m"] = max(params["length_m"], target_height_m / effective_slope)
        params["length_adjustment_ref"] = "Annex 14 Vol I 4.2.1.10"

    if is_instrument and obstacle_clearance_height_m is not None and obstacle_clearance_height_m > 150.0:
        params["length_m"] = max(params["length_m"], obstacle_clearance_height_m / effective_slope)
        params["length_adjustment_ref"] = "Annex 14 Vol I 4.2.1.11"


def get_approach_surface_params(
    design_group: Optional[str],
    runway_type: Optional[str],
    runway_width_m: Optional[float] = None,
    slope: Optional[float] = None,
    obstacle_clearance_height_m: Optional[float] = None,
):
    """Return Annex 14 approach surface parameters from Tables 4-1 and 4-2."""
    normalized_design_group = _normalize_design_group(design_group)
    if normalized_design_group is None:
        return None

    is_instrument = _is_instrument_runway(runway_type)
    table = INSTRUMENT_APPROACH_SURFACE if is_instrument else NON_INSTRUMENT_APPROACH_SURFACE
    base_params = table.get(normalized_design_group)
    if base_params is None:
        return None

    params = deepcopy(base_params)
    params["surface"] = "approach"
    params["section_ref"] = APPROACH_SURFACE_REF
    params["design_group"] = normalized_design_group
    params["runway_type_abbr"] = get_runway_type_abbr(runway_type)

    if is_instrument:
        _apply_instrument_inner_edge_adjustments(params, normalized_design_group, runway_width_m)
    else:
        _apply_non_instrument_inner_edge_adjustments(params, normalized_design_group, runway_width_m)

    _apply_length_adjustments(params, is_instrument, slope, obstacle_clearance_height_m)
    return params


def get_transitional_surface_params():
    """Return Annex 14 transitional surface parameters from 4.2.2."""
    return deepcopy(TRANSITIONAL_SURFACE)


def get_inner_approach_surface_params(
    design_group: Optional[str],
    runway_type: Optional[str],
    approach_surface_slope: Optional[float] = None,
    code_letter_f_without_digital_avionics: bool = False,
):
    """Return Annex 14 inner approach surface parameters from Tables 4-3 to 4-5."""
    normalized_design_group = _normalize_design_group(design_group)
    if normalized_design_group is None:
        return None

    table = _inner_approach_table_for_runway_type(runway_type)
    base_params = table.get(normalized_design_group)
    if base_params is None:
        return None

    params = deepcopy(base_params)
    params["surface"] = "inner_approach"
    params["family"] = "obstacle_free_surfaces"
    params["shape"] = "rectangle"
    params["section_ref"] = INNER_APPROACH_SURFACE_REF
    params["design_group"] = normalized_design_group
    params["runway_type_abbr"] = get_runway_type_abbr(runway_type)
    params["inner_edge_location"] = "coincident_with_approach_inner_edge"
    params["length_adjustment_height_m"] = 45.0

    if normalized_design_group == "V" and code_letter_f_without_digital_avionics:
        params["inner_edge_length_m"] = 140.0
        params["inner_edge_adjustment_ref"] = f"{params['ref']} note a"

    if approach_surface_slope is not None and approach_surface_slope > 0:
        adjusted_length = 45.0 / approach_surface_slope
        if adjusted_length > params["length_m"]:
            params["length_m"] = adjusted_length
            params["length_adjustment_ref"] = "Annex 14 Vol I 4.2.3.7"

    return params


def get_inner_transitional_surface_params(
    design_group: Optional[str],
    runway_type: Optional[str],
):
    """Return Annex 14 inner transitional surface parameters from Tables 4-6 to 4-8."""
    normalized_design_group = _normalize_design_group(design_group)
    if normalized_design_group is None:
        return None

    table = _inner_transitional_table_for_runway_type(runway_type)
    base_params = table.get(normalized_design_group)
    if base_params is None:
        return None

    runway_type_abbr = get_runway_type_abbr(runway_type)
    params = deepcopy(base_params)
    params["surface"] = "inner_transitional"
    params["family"] = "obstacle_free_surfaces"
    params["section_ref"] = INNER_TRANSITIONAL_SURFACE_REF
    params["design_group"] = normalized_design_group
    params["runway_type_abbr"] = runway_type_abbr
    params["upper_edge_height_above_highest_threshold_m"] = 60.0
    params["upper_edge_ref"] = "Annex 14 Vol I 4.2.4.2 and 4.2.4.3"
    params["configuration"] = "precision_single_section" if runway_type_abbr in {"PA_I", "PA_II_III"} else "vertical_then_inclined"
    return params


def get_balked_landing_surface_params(
    design_group: Optional[str],
    code_letter_f_without_digital_avionics: bool = False,
):
    """Return Annex 14 balked landing surface parameters from Table 4-9."""
    normalized_design_group = _normalize_design_group(design_group)
    if normalized_design_group is None:
        return None

    base_params = BALKED_LANDING_SURFACE.get(normalized_design_group)
    if base_params is None:
        return None

    params = deepcopy(base_params)
    params["surface"] = "balked_landing"
    params["family"] = "obstacle_free_surfaces"
    params["section_ref"] = BALKED_LANDING_SURFACE_REF
    params["design_group"] = normalized_design_group
    params["upper_edge_height_above_highest_threshold_m"] = 60.0
    params["upper_edge_ref"] = "Annex 14 Vol I 4.2.5.2"

    if normalized_design_group == "V" and code_letter_f_without_digital_avionics:
        params["inner_edge_length_m"] = 140.0
        params["inner_edge_adjustment_ref"] = f"{BALKED_LANDING_REF} note c"

    return params


def get_obstacle_free_surfaces(
    design_group: Optional[str],
    runway_type: Optional[str],
    runway_width_m: Optional[float] = None,
    approach_surface_slope: Optional[float] = None,
    obstacle_clearance_height_m: Optional[float] = None,
    code_letter_f_without_digital_avionics: bool = False,
):
    """Return a coordinated Annex 14 obstacle free surfaces parameter package."""
    approach = get_approach_surface_params(
        design_group=design_group,
        runway_type=runway_type,
        runway_width_m=runway_width_m,
        slope=approach_surface_slope,
        obstacle_clearance_height_m=obstacle_clearance_height_m,
    )
    transitional = get_transitional_surface_params()
    inner_approach = get_inner_approach_surface_params(
        design_group=design_group,
        runway_type=runway_type,
        approach_surface_slope=approach_surface_slope,
        code_letter_f_without_digital_avionics=code_letter_f_without_digital_avionics,
    )
    inner_transitional = get_inner_transitional_surface_params(
        design_group=design_group,
        runway_type=runway_type,
    )

    runway_type_abbr = get_runway_type_abbr(runway_type)
    inner_surfaces = [inner_approach, inner_transitional]
    if runway_type_abbr in {"PA_I", "PA_II_III"}:
        inner_surfaces.append(
            get_balked_landing_surface_params(
                design_group=design_group,
                code_letter_f_without_digital_avionics=code_letter_f_without_digital_avionics,
            )
        )

    general_surfaces = [approach, transitional]
    return {
        "family": "obstacle_free_surfaces",
        "status": "data_capture_complete",
        "runway_type_abbr": runway_type_abbr,
        "design_group": _normalize_design_group(design_group),
        "section_ref": "Annex 14 Vol I 4.2",
        "groups": {
            "general": [surface for surface in general_surfaces if surface is not None],
            "inner": [surface for surface in inner_surfaces if surface is not None],
        },
    }


def get_ols_params(arc_num: int, runway_type: Optional[str], surface_type: str):
    if _normalize_surface_type(surface_type) == "approach":
        return None
    if _normalize_surface_type(surface_type) == "transitional":
        return get_transitional_surface_params()
    return None


__all__ = [
    "APPROACH_SURFACE_REF",
    "APPROACH_NON_INSTRUMENT_REF",
    "APPROACH_INSTRUMENT_REF",
    "TRANSITIONAL_SURFACE_REF",
    "INNER_APPROACH_SURFACE_REF",
    "INNER_APPROACH_NON_INSTRUMENT_REF",
    "INNER_APPROACH_NON_PRECISION_REF",
    "INNER_APPROACH_PRECISION_REF",
    "INNER_TRANSITIONAL_SURFACE_REF",
    "INNER_TRANSITIONAL_NON_INSTRUMENT_REF",
    "INNER_TRANSITIONAL_NON_PRECISION_REF",
    "INNER_TRANSITIONAL_PRECISION_REF",
    "BALKED_LANDING_SURFACE_REF",
    "BALKED_LANDING_REF",
    "NON_INSTRUMENT_APPROACH_SURFACE",
    "INSTRUMENT_APPROACH_SURFACE",
    "TRANSITIONAL_SURFACE",
    "NON_INSTRUMENT_INNER_APPROACH_SURFACE",
    "NON_PRECISION_INNER_APPROACH_SURFACE",
    "PRECISION_INNER_APPROACH_SURFACE",
    "NON_INSTRUMENT_INNER_TRANSITIONAL_SURFACE",
    "NON_PRECISION_INNER_TRANSITIONAL_SURFACE",
    "PRECISION_INNER_TRANSITIONAL_SURFACE",
    "BALKED_LANDING_SURFACE",
    "get_approach_surface_params",
    "get_transitional_surface_params",
    "get_inner_approach_surface_params",
    "get_inner_transitional_surface_params",
    "get_balked_landing_surface_params",
    "get_obstacle_free_surfaces",
    "get_ols_params",
]
