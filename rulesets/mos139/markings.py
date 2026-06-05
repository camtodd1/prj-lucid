"""MOS139 runway marking policy."""

from typing import List, Optional, Tuple

from . import ols

THRESHOLD_MARKING_PARAMS_BY_WIDTH = {
    18.0: (4, 1.5),
    23.0: (6, 1.5),
    30.0: (8, 1.5),
    45.0: (12, 1.7),
    60.0: (16, 1.7),
}

PRECISION_AIMING_POINT_RULES = (
    (800.0, 150.0, 30.0, 4.0, 6.0, "MOS 8.22(3)"),
    (1200.0, 250.0, 30.0, 6.0, 9.0, "MOS 8.22(3)"),
    (2400.0, 300.0, 45.0, 9.0, 23.0, "MOS 8.22(3)"),
    (None, 400.0, 45.0, 9.0, 23.0, "MOS 8.22(3)"),
)

TOUCHDOWN_ZONE_OFFSET_RULES = (
    (900.0, [300.0]),
    (1200.0, [150.0, 450.0]),
    (1500.0, [150.0, 300.0, 450.0, 600.0]),
    (2400.0, [150.0, 300.0, 450.0, 600.0, 750.0]),
    (None, [150.0, 300.0, 450.0, 600.0, 750.0, 900.0]),
)

RUNWAY_HOLDING_POSITION_TABLE = {
    1: {"NI": 30.0, "NPA": 40.0, "PA_I": 60.0, "PA_II_III": None},
    2: {"NI": 40.0, "NPA": 40.0, "PA_I": 60.0, "PA_II_III": None},
    3: {"NI": 75.0, "NPA": 75.0, "PA_I": 90.0, "PA_II_III": 90.0},
    4: {"NI": 75.0, "NPA": 75.0, "PA_I": 90.0, "PA_II_III": 90.0},
}
RUNWAY_HOLDING_POSITION_REF = "MOS 8.39(7); Table 6.56(1)"


def threshold_marking_params(runway_width: float) -> Optional[Tuple[int, float]]:
    for width_m, params in THRESHOLD_MARKING_PARAMS_BY_WIDTH.items():
        if abs(float(runway_width) - width_m) <= 0.01:
            return params
    return None


def centreline_marking_width(arc_num: int, type_primary: str, type_reciprocal: str) -> float:
    widths = []
    for runway_type in (type_primary, type_reciprocal):
        type_abbr = ols.classify_runway_type(runway_type)
        if type_abbr == "PA_II_III":
            widths.append(0.9)
        elif type_abbr == "PA_I" or (type_abbr == "NPA" and arc_num in (3, 4)):
            widths.append(0.45)
        else:
            widths.append(0.3)
    return max(widths) if widths else 0.3


def aiming_point_rule(
    runway_width: float, lda_m: float, runway_type: str
) -> Optional[Tuple[float, float, float, float, str]]:
    type_abbr = ols.classify_runway_type(runway_type)
    if type_abbr in {"PA_I", "PA_II_III"}:
        for max_lda_m, offset_m, length_m, width_m, spacing_m, ref in PRECISION_AIMING_POINT_RULES:
            if max_lda_m is None or lda_m < max_lda_m:
                return offset_m, length_m, width_m, spacing_m, ref

    if abs(runway_width - 30.0) <= 0.01:
        return 300.0, 45.0, 6.0, 17.0, "MOS 8.22(8)"
    if runway_width >= 45.0:
        return 300.0, 45.0, 9.0, 23.0, "MOS 8.22(8)"
    return None


def touchdown_zone_offsets(lda_m: float) -> List[float]:
    for max_lda_m, offsets in TOUCHDOWN_ZONE_OFFSET_RULES:
        if max_lda_m is None or lda_m < max_lda_m:
            return list(offsets)
    return []


def runway_holding_position_rule(runway_code_num: int, runway_type: str) -> Optional[Tuple[float, str]]:
    type_abbr = ols.classify_runway_type(runway_type)
    if runway_code_num not in RUNWAY_HOLDING_POSITION_TABLE:
        return None
    if type_abbr not in RUNWAY_HOLDING_POSITION_TABLE[runway_code_num]:
        return None
    distance = RUNWAY_HOLDING_POSITION_TABLE[runway_code_num][type_abbr]
    if distance is None:
        return None
    return distance, RUNWAY_HOLDING_POSITION_REF


__all__ = [
    "threshold_marking_params",
    "centreline_marking_width",
    "aiming_point_rule",
    "touchdown_zone_offsets",
    "runway_holding_position_rule",
]
