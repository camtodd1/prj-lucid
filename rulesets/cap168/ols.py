"""Obstacle limitation placeholders for UK CAA CAP 168."""


def ihs_base_height():
    return None


def ols_parameters(arc_num: int, runway_type, surface_type: str):
    del arc_num, runway_type, surface_type
    return None


__all__ = ["ihs_base_height", "ols_parameters"]
