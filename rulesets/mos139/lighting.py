"""MOS139 airfield ground lighting policy wrappers."""

try:
    from ...dimensions import agl_dimensions
except ImportError:
    from dimensions import agl_dimensions  # type: ignore


def agl_value(name: str):
    return getattr(agl_dimensions, name)


def runway_type_supports_agl(runway_type: str) -> bool:
    return agl_dimensions.runway_type_supports_agl(runway_type)


def runway_is_precision(runway_type: str) -> bool:
    return agl_dimensions.runway_is_precision(runway_type)


def runway_edge_spacing_for_end(runway_type: str) -> float:
    return agl_dimensions.runway_edge_spacing_for_end(runway_type)


def threshold_light_count_for_end(runway_type: str, runway_width_m: float) -> int:
    return agl_dimensions.threshold_light_count_for_end(runway_type, runway_width_m)


def runway_end_light_count_for_end(runway_type: str, runway_width_m: float) -> int:
    return agl_dimensions.runway_end_light_count_for_end(runway_type, runway_width_m)


def temp_displaced_threshold_lights_per_side(runway_width_m: float) -> int:
    return agl_dimensions.temp_displaced_threshold_lights_per_side(runway_width_m)


def runway_centreline_required(runway_type_1: str, runway_type_2: str, rvr_below_350: bool = False) -> bool:
    return agl_dimensions.runway_centreline_required(runway_type_1, runway_type_2, rvr_below_350)


def runway_centreline_recommended(runway_type_1: str, runway_type_2: str, edge_light_width_m: float) -> bool:
    return agl_dimensions.runway_centreline_recommended(runway_type_1, runway_type_2, edge_light_width_m)


def runway_centreline_spacing(rvr_below_350: bool) -> float:
    return agl_dimensions.runway_centreline_spacing(rvr_below_350)


def approach_profile_for_end(runway_type: str):
    return agl_dimensions.approach_profile_for_end(runway_type)


__all__ = [
    "agl_value",
    "runway_type_supports_agl",
    "runway_is_precision",
    "runway_edge_spacing_for_end",
    "threshold_light_count_for_end",
    "runway_end_light_count_for_end",
    "temp_displaced_threshold_lights_per_side",
    "runway_centreline_required",
    "runway_centreline_recommended",
    "runway_centreline_spacing",
    "approach_profile_for_end",
]
