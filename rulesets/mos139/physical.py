"""MOS139 physical-infrastructure policy wrappers."""

from typing import Optional

try:
    from . import physical_data
    from . import taxiway
except ImportError:
    from rulesets.mos139 import physical_data  # type: ignore
    from rulesets.mos139 import taxiway  # type: ignore


def physical_refs() -> dict:
    return physical_data.get_physical_refs()


def strip_parameters(arc_num: int, type_abbr: str, runway_width: Optional[float]):
    return physical_data.get_strip_params(arc_num, type_abbr, runway_width)


def resa_parameters(arc_num: int, type1_abbr: str, type2_abbr: str):
    return physical_data.get_resa_params(arc_num, type1_abbr, type2_abbr)


def taxiway_separation_offset(arc_num: int, arc_let: Optional[str], runway_type: Optional[str]):
    return taxiway.get_taxiway_separation_offset(arc_num, arc_let, runway_type)


def taxiway_to_taxiway_separation(arc_let: Optional[str]):
    return taxiway.get_taxiway_to_taxiway_separation(arc_let)


def taxiway_object_separation(arc_let: Optional[str]):
    return taxiway.get_taxiway_object_separation(arc_let)


def stand_taxilane_to_stand_taxilane_separation(arc_let: Optional[str]):
    return taxiway.get_stand_taxilane_to_stand_taxilane_separation(arc_let)


def stand_taxilane_object_separation(arc_let: Optional[str]):
    return taxiway.get_stand_taxilane_object_separation(arc_let)


def parallel_runway_separation(
    arc_num_1: Optional[int] = None,
    arc_num_2: Optional[int] = None,
    runway_type_1: Optional[str] = None,
    runway_type_2: Optional[str] = None,
    operation_type: Optional[str] = None,
    arrival_threshold_stagger_m: Optional[float] = None,
):
    return taxiway.get_parallel_runway_separation(
        arc_num_1=arc_num_1,
        arc_num_2=arc_num_2,
        runway_type_1=runway_type_1,
        runway_type_2=runway_type_2,
        operation_type=operation_type,
        arrival_threshold_stagger_m=arrival_threshold_stagger_m,
    )


__all__ = [
    "physical_refs",
    "strip_parameters",
    "resa_parameters",
    "taxiway_separation_offset",
    "taxiway_to_taxiway_separation",
    "taxiway_object_separation",
    "stand_taxilane_to_stand_taxilane_separation",
    "stand_taxilane_object_separation",
    "parallel_runway_separation",
]
