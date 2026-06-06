"""OLS surface lookups for ICAO Annex 14 Volume I."""

from copy import deepcopy
from typing import Optional

from .classification import get_runway_type_abbr

APPROACH_SURFACE_REF = "Annex 14 Vol I 4.2.1"
APPROACH_NON_INSTRUMENT_REF = "Annex 14 Vol I Table 4-1"
APPROACH_INSTRUMENT_REF = "Annex 14 Vol I Table 4-2"
TRANSITIONAL_SURFACE_REF = "Annex 14 Vol I 4.2.2"

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
    "NON_INSTRUMENT_APPROACH_SURFACE",
    "INSTRUMENT_APPROACH_SURFACE",
    "TRANSITIONAL_SURFACE",
    "get_approach_surface_params",
    "get_transitional_surface_params",
    "get_ols_params",
]
