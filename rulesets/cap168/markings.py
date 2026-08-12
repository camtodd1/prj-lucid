"""UK CAA CAP 168 runway marking policy."""

from typing import List, Optional, Tuple

from .classification import get_runway_type_abbr

SOURCE_PUBLICATION = "UK CAA CAP 168 Licensing of Aerodromes, Edition 13"
SOURCE_URL = "https://www.caa.co.uk/CAP168"

CAP168_RUNWAY_CENTRELINE_MARKING_REF = "CAP 168 7.192-7.206 Table 7.3"
CAP168_THRESHOLD_MARKING_REF = "CAP 168 7.207-7.210 Table 7.3"
CAP168_AIMING_POINT_MARKING_REF = "CAP 168 7.211-7.214 Table 7.24"
CAP168_TOUCHDOWN_ZONE_MARKING_REF = "CAP 168 7.215-7.223"
CAP168_RUNWAY_SIDE_STRIPE_MARKING_REF = "CAP 168 7.224-7.229 Table 7.26"
CAP168_RUNWAY_HOLDING_POSITION_MARKING_REF = "CAP 168 7.256-7.265"
CAP168_RUNWAY_HOLDING_POSITION_LOCATION_REF = "CAP 168 3.161 Table 3.3"

RUNWAY_CENTRELINE_MARKING_PARAMS = {
    "stripe_gap_min_m": 50.0,
    "stripe_gap_max_m": 75.0,
    "stripe_min_length_m": 30.0,
    "stripe_widths_m": {
        "PA_II_III": 0.9,
        "PA_I": 0.45,
        "NPA_CODE_3_4": 0.45,
        "NPA_CODE_1_2": 0.3,
        "NI": 0.3,
    },
    "ref": CAP168_RUNWAY_CENTRELINE_MARKING_REF,
}

THRESHOLD_MARKING_PARAMS_BY_WIDTH = {
    18.0: {
        "precision": {"stripe_count": 4, "gap_m": 1.8, "character_height_m": 12.0},
        "non_precision": {"stripe_count": 4, "gap_m": 0.3, "character_height_m": 9.0},
        "stripe_length_m": 24.0,
        "centre_gap_m": 3.6,
        "ref": CAP168_THRESHOLD_MARKING_REF,
    },
    23.0: {
        "precision": {"stripe_count": 6, "gap_m": 1.8, "character_height_m": 12.0},
        "non_precision": {"stripe_count": 6, "gap_m": 0.6, "character_height_m": 9.0},
        "stripe_length_m": 24.0,
        "centre_gap_m": 3.6,
        "ref": CAP168_THRESHOLD_MARKING_REF,
    },
    30.0: {
        "precision": {"stripe_count": 8, "gap_m": 1.8, "character_height_m": 15.0},
        "non_precision": {"stripe_count": 6, "gap_m": 0.9, "character_height_m": 12.0},
        "stripe_length_m": 30.0,
        "centre_gap_m": 3.6,
        "ref": CAP168_THRESHOLD_MARKING_REF,
    },
    45.0: {
        "precision": {"stripe_count": 12, "gap_m": 1.8, "character_height_m": 15.0},
        "non_precision": {"stripe_count": 6, "gap_m": 1.8, "character_height_m": 15.0},
        "stripe_length_m": 30.0,
        "centre_gap_m": 3.6,
        "ref": CAP168_THRESHOLD_MARKING_REF,
    },
}

AIMING_POINT_RULES = (
    (800.0, 150.0, 30.0, 4.0, 6.0, CAP168_AIMING_POINT_MARKING_REF),
    (1200.0, 250.0, 30.0, 6.0, 9.0, CAP168_AIMING_POINT_MARKING_REF),
    (2400.0, 300.0, 45.0, 6.0, 18.0, CAP168_AIMING_POINT_MARKING_REF),
    (None, 400.0, 45.0, 6.0, 18.0, CAP168_AIMING_POINT_MARKING_REF),
)

TOUCHDOWN_ZONE_OFFSET_RULES = (
    (900.0, [300.0]),
    (1200.0, [150.0, 450.0]),
    (1500.0, [150.0, 450.0, 600.0]),
    (2400.0, [150.0, 450.0, 600.0, 750.0]),
    (None, [150.0, 300.0, 600.0, 750.0, 900.0, 1050.0]),
)

RUNWAY_HOLDING_POSITION_TABLE = {
    1: {"NI": 30.0, "NPA": 30.0, "TAKEOFF": 30.0, "PA_I": 60.0, "PA_II_III": None},
    2: {"NI": 40.0, "NPA": 40.0, "TAKEOFF": 40.0, "PA_I": 60.0, "PA_II_III": None},
    3: {"NI": 55.0, "NPA": 75.0, "TAKEOFF": 55.0, "PA_I": 90.0, "PA_II_III": 90.0},
    4: {"NI": 75.0, "NPA": 75.0, "TAKEOFF": 75.0, "PA_I": 90.0, "PA_II_III": 90.0},
}

def threshold_marking_params(
    runway_width: float, runway_type: Optional[str] = None
) -> Optional[Tuple[int, float]]:
    params = threshold_marking_params_for_type(
        runway_width, runway_type or "Precision Approach CAT I"
    )
    if not params:
        return None
    return params["stripe_count"], params["gap_m"]


def threshold_marking_ref() -> str:
    """Return the CAP 168 source for threshold markings."""
    return CAP168_THRESHOLD_MARKING_REF


def threshold_marking_params_for_type(runway_width: float, runway_type: str):
    width_params = _threshold_width_params(runway_width)
    if not width_params:
        return None
    key = "precision" if get_runway_type_abbr(runway_type) in {"PA_I", "PA_II_III"} else "non_precision"
    selected = width_params[key]
    return {
        **selected,
        "stripe_length_m": width_params["stripe_length_m"],
        "centre_gap_m": width_params["centre_gap_m"],
        "ref": width_params["ref"],
    }


def centreline_marking_width(arc_num: int, type_primary: str, type_reciprocal: str) -> float:
    widths: List[float] = []
    for runway_type in (type_primary, type_reciprocal):
        type_abbr = get_runway_type_abbr(runway_type)
        if type_abbr == "PA_II_III":
            widths.append(RUNWAY_CENTRELINE_MARKING_PARAMS["stripe_widths_m"]["PA_II_III"])
        elif type_abbr == "PA_I":
            widths.append(RUNWAY_CENTRELINE_MARKING_PARAMS["stripe_widths_m"]["PA_I"])
        elif type_abbr == "NPA" and arc_num in (3, 4):
            widths.append(RUNWAY_CENTRELINE_MARKING_PARAMS["stripe_widths_m"]["NPA_CODE_3_4"])
        elif type_abbr == "NPA":
            widths.append(RUNWAY_CENTRELINE_MARKING_PARAMS["stripe_widths_m"]["NPA_CODE_1_2"])
        else:
            widths.append(RUNWAY_CENTRELINE_MARKING_PARAMS["stripe_widths_m"]["NI"])
    return max(widths) if widths else RUNWAY_CENTRELINE_MARKING_PARAMS["stripe_widths_m"]["NI"]


def aiming_point_rule(
    runway_width: float, lda_m: float, runway_type: str
) -> Optional[Tuple[float, float, float, float, str]]:
    type_abbr = get_runway_type_abbr(runway_type)
    if type_abbr in {"NPA", "PA_I", "PA_II_III"}:
        for max_lda_m, offset_m, length_m, width_m, spacing_m, ref in AIMING_POINT_RULES:
            if max_lda_m is None or lda_m < max_lda_m:
                return offset_m, length_m, width_m, spacing_m, ref
    if type_abbr == "NI" and runway_width >= 30.0:
        return 300.0, 45.0, 6.0, 18.0, "CAP 168 7.212-7.213; Table 7.24"
    return None


def touchdown_zone_offsets(lda_m: float) -> List[float]:
    for max_lda_m, offsets in TOUCHDOWN_ZONE_OFFSET_RULES:
        if max_lda_m is None or lda_m < max_lda_m:
            return list(offsets)
    return []


def runway_holding_position_rule(runway_code_num: int, runway_type: str) -> Optional[Tuple[float, str]]:
    type_abbr = get_runway_type_abbr(runway_type)
    if runway_code_num not in RUNWAY_HOLDING_POSITION_TABLE:
        return None
    if type_abbr not in RUNWAY_HOLDING_POSITION_TABLE[runway_code_num]:
        return None
    distance = RUNWAY_HOLDING_POSITION_TABLE[runway_code_num][type_abbr]
    if distance is None:
        return None
    return distance, f"{CAP168_RUNWAY_HOLDING_POSITION_MARKING_REF}; {CAP168_RUNWAY_HOLDING_POSITION_LOCATION_REF}"


def _threshold_width_params(runway_width: float):
    for width_m, params in THRESHOLD_MARKING_PARAMS_BY_WIDTH.items():
        if abs(float(runway_width) - width_m) <= 0.01:
            return params
    return None


__all__ = [
    "SOURCE_PUBLICATION",
    "SOURCE_URL",
    "CAP168_RUNWAY_CENTRELINE_MARKING_REF",
    "CAP168_THRESHOLD_MARKING_REF",
    "CAP168_AIMING_POINT_MARKING_REF",
    "CAP168_TOUCHDOWN_ZONE_MARKING_REF",
    "CAP168_RUNWAY_SIDE_STRIPE_MARKING_REF",
    "CAP168_RUNWAY_HOLDING_POSITION_MARKING_REF",
    "CAP168_RUNWAY_HOLDING_POSITION_LOCATION_REF",
    "RUNWAY_CENTRELINE_MARKING_PARAMS",
    "THRESHOLD_MARKING_PARAMS_BY_WIDTH",
    "AIMING_POINT_RULES",
    "TOUCHDOWN_ZONE_OFFSET_RULES",
    "RUNWAY_HOLDING_POSITION_TABLE",
    "threshold_marking_params",
    "threshold_marking_ref",
    "threshold_marking_params_for_type",
    "centreline_marking_width",
    "aiming_point_rule",
    "touchdown_zone_offsets",
    "runway_holding_position_rule",
]
