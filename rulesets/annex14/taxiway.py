"""Taxiway and parallel runway separation placeholders for ICAO Annex 14."""

from typing import Optional


def get_taxiway_separation_offset(arc_num: int, arc_let: Optional[str], runway_type: Optional[str]):
    return None


def get_taxiway_to_taxiway_separation(arc_let: Optional[str]):
    return None


def get_taxiway_object_separation(arc_let: Optional[str]):
    return None


def get_stand_taxilane_to_stand_taxilane_separation(arc_let: Optional[str]):
    return None


def get_stand_taxilane_object_separation(arc_let: Optional[str]):
    return None


def get_parallel_runway_separation(
    arc_num_1: Optional[int] = None,
    arc_num_2: Optional[int] = None,
    runway_type_1: Optional[str] = None,
    runway_type_2: Optional[str] = None,
    operation_type: Optional[str] = None,
    arrival_threshold_stagger_m: Optional[float] = None,
):
    return None


__all__ = [
    "get_taxiway_separation_offset",
    "get_taxiway_to_taxiway_separation",
    "get_taxiway_object_separation",
    "get_stand_taxilane_to_stand_taxilane_separation",
    "get_stand_taxilane_object_separation",
    "get_parallel_runway_separation",
]
