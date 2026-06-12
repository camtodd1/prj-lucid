"""Runway marking placeholders for UK CAA CAP 168."""


def centreline_marking_width(arc_num: int, type_primary: str, type_reciprocal: str):
    del arc_num, type_primary, type_reciprocal
    return None


def threshold_marking_params(runway_width: float):
    del runway_width
    return None


def aiming_point_rule(runway_width: float, lda_m: float, runway_type: str):
    del runway_width, lda_m, runway_type
    return None


def touchdown_zone_offsets(lda_m: float):
    del lda_m
    return []


def runway_holding_position_rule(runway_code_num: int, runway_type: str):
    del runway_code_num, runway_type
    return None


__all__ = [
    "centreline_marking_width",
    "threshold_marking_params",
    "aiming_point_rule",
    "touchdown_zone_offsets",
    "runway_holding_position_rule",
]
