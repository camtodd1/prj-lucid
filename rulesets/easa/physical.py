"""EASA physical-infrastructure policy wrappers."""

from typing import Optional

from . import physical_data
from . import taxiway


def physical_refs() -> dict:
    return physical_data.get_physical_refs()


def strip_parameters(arc_num: int, type_abbr: str, runway_width: Optional[float]):
    return physical_data.get_strip_params(arc_num, type_abbr, runway_width)


def resa_parameters(arc_num: int, type1_abbr: str, type2_abbr: str):
    return physical_data.get_resa_params(arc_num, type1_abbr, type2_abbr)


def taxiway_separation_offset(arc_num: int, arc_let: Optional[str], runway_type: Optional[str]):
    return taxiway.get_taxiway_separation_offset(arc_num, arc_let, runway_type)


__all__ = [
    "physical_refs",
    "strip_parameters",
    "resa_parameters",
    "taxiway_separation_offset",
]
