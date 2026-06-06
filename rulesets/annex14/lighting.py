"""Aeronautical ground lighting placeholders for ICAO Annex 14 Volume I."""

PRECISION_APPROACH_TYPES = {"PA_I", "PA_II_III"}


def agl_value(name: str):
    raise KeyError(name)


def runway_type_supports_agl(runway_type: str) -> bool:
    return False


def runway_is_precision(runway_type: str) -> bool:
    return runway_type in PRECISION_APPROACH_TYPES or runway_type in {
        "Precision Approach CAT I",
        "Precision Approach CAT II/III",
    }


def runway_edge_spacing_for_end(runway_type: str):
    return None


def threshold_light_count_for_end(runway_type: str, runway_width_m: float):
    return None


def runway_end_light_count_for_end(runway_type: str, runway_width_m: float):
    return None


def temp_displaced_threshold_lights_per_side(runway_width_m: float):
    return None


def runway_centreline_required(runway_type_1: str, runway_type_2: str, rvr_below_350: bool = False) -> bool:
    return False


def runway_centreline_recommended(runway_type_1: str, runway_type_2: str, edge_light_width_m: float) -> bool:
    return False


def runway_centreline_spacing(rvr_below_350: bool):
    return None


def approach_profile_for_end(runway_type: str):
    return None


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
