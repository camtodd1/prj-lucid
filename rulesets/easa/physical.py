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


def declared_distance_parameters():
    return physical_data.get_declared_distance_params()


def clearway_parameters(
    runway_width: Optional[float] = None,
    strip_extension: Optional[float] = None,
    strip_overall_width: Optional[float] = None,
    physical_length: Optional[float] = None,
    clearway_primary_input: Optional[float] = None,
    clearway_reciprocal_input: Optional[float] = None,
    stopway_primary: Optional[float] = None,
    stopway_reciprocal: Optional[float] = None,
    is_instrument_runway: bool = False,
    arc_num: Optional[int] = None,
):
    return physical_data.get_clearway_params(
        runway_width=runway_width,
        strip_extension=strip_extension,
        strip_overall_width=strip_overall_width,
        physical_length=physical_length,
        clearway_primary_input=clearway_primary_input,
        clearway_reciprocal_input=clearway_reciprocal_input,
        stopway_primary=stopway_primary,
        stopway_reciprocal=stopway_reciprocal,
        is_instrument_runway=is_instrument_runway,
        arc_num=arc_num,
    )


def stopway_parameters(runway_width: Optional[float] = None, stopway_length: Optional[float] = None):
    return physical_data.get_stopway_params(runway_width, stopway_length)


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
    "declared_distance_parameters",
    "clearway_parameters",
    "stopway_parameters",
    "taxiway_separation_offset",
    "taxiway_to_taxiway_separation",
    "taxiway_object_separation",
    "stand_taxilane_to_stand_taxilane_separation",
    "stand_taxilane_object_separation",
    "parallel_runway_separation",
]
