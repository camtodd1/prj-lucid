"""Runway marking placeholders for ICAO Annex 14 Volume I."""


def centreline_marking_width(arc_num: int, type_primary: str, type_reciprocal: str):
    return None


def threshold_marking_params(runway_width: float):
    return None


def aiming_point_rule(runway_width: float, lda_m: float, runway_type: str):
    return None


def touchdown_zone_offsets(lda_m: float):
    return None


def runway_holding_position_rule(runway_code_num: int, runway_type: str):
    return None


__all__ = [
    "centreline_marking_width",
    "threshold_marking_params",
    "aiming_point_rule",
    "touchdown_zone_offsets",
    "runway_holding_position_rule",
]
