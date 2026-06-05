"""MOS139 physical-infrastructure policy wrappers."""

from typing import Optional

try:
    from ...dimensions import ols_dimensions
except ImportError:
    from dimensions import ols_dimensions  # type: ignore


def physical_refs() -> dict:
    return ols_dimensions.get_physical_refs()


def strip_parameters(arc_num: int, type_abbr: str, runway_width: Optional[float]):
    return ols_dimensions.get_strip_params(arc_num, type_abbr, runway_width)


def resa_parameters(arc_num: int, type1_abbr: str, type2_abbr: str):
    return ols_dimensions.get_resa_params(arc_num, type1_abbr, type2_abbr)


def taxiway_separation_offset(arc_num: int, arc_let: Optional[str], runway_type: Optional[str]):
    return ols_dimensions.get_taxiway_separation_offset(arc_num, arc_let, runway_type)


__all__ = [
    "physical_refs",
    "strip_parameters",
    "resa_parameters",
    "taxiway_separation_offset",
]
