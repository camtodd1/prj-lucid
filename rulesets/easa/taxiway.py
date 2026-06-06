"""EASA taxiway and runway separation policy."""

import logging
from typing import Any, Dict, Optional, Tuple

from .classification import get_runway_type_abbr

LOGGER = logging.getLogger(__name__)

EASA_TAXIWAY_SEPARATION_REF = "CS ADR-DSN.D.260 Table D-1"

TAXIWAY_RUNWAY_SEPARATION_PARAMS: Dict[Tuple[int, str, str], Dict[str, Any]] = {
    (1, "A", "INSTR"): {"offset_m": 77.5, "ref": EASA_TAXIWAY_SEPARATION_REF},
    (2, "A", "INSTR"): {"offset_m": 77.5, "ref": EASA_TAXIWAY_SEPARATION_REF},
    (1, "B", "INSTR"): {"offset_m": 82.0, "ref": EASA_TAXIWAY_SEPARATION_REF},
    (2, "B", "INSTR"): {"offset_m": 82.0, "ref": EASA_TAXIWAY_SEPARATION_REF},
    (3, "B", "INSTR"): {"offset_m": 152.0, "ref": EASA_TAXIWAY_SEPARATION_REF},
    (1, "C", "INSTR"): {"offset_m": 88.0, "ref": EASA_TAXIWAY_SEPARATION_REF},
    (2, "C", "INSTR"): {"offset_m": 88.0, "ref": EASA_TAXIWAY_SEPARATION_REF},
    (3, "C", "INSTR"): {"offset_m": 158.0, "ref": EASA_TAXIWAY_SEPARATION_REF},
    (4, "C", "INSTR"): {"offset_m": 158.0, "ref": EASA_TAXIWAY_SEPARATION_REF},
    (3, "D", "INSTR"): {"offset_m": 166.0, "ref": EASA_TAXIWAY_SEPARATION_REF},
    (4, "D", "INSTR"): {"offset_m": 166.0, "ref": EASA_TAXIWAY_SEPARATION_REF},
    (3, "E", "INSTR"): {"offset_m": 172.5, "ref": EASA_TAXIWAY_SEPARATION_REF},
    (4, "E", "INSTR"): {"offset_m": 172.5, "ref": EASA_TAXIWAY_SEPARATION_REF},
    (3, "F", "INSTR"): {"offset_m": 180.0, "ref": EASA_TAXIWAY_SEPARATION_REF},
    (4, "F", "INSTR"): {"offset_m": 180.0, "ref": EASA_TAXIWAY_SEPARATION_REF},
    (1, "A", "NI"): {"offset_m": 37.5, "ref": EASA_TAXIWAY_SEPARATION_REF},
    (2, "A", "NI"): {"offset_m": 47.5, "ref": EASA_TAXIWAY_SEPARATION_REF},
    (1, "B", "NI"): {"offset_m": 42.0, "ref": EASA_TAXIWAY_SEPARATION_REF},
    (2, "B", "NI"): {"offset_m": 52.0, "ref": EASA_TAXIWAY_SEPARATION_REF},
    (3, "B", "NI"): {"offset_m": 87.0, "ref": EASA_TAXIWAY_SEPARATION_REF},
    (1, "C", "NI"): {"offset_m": 48.0, "ref": EASA_TAXIWAY_SEPARATION_REF},
    (2, "C", "NI"): {"offset_m": 58.0, "ref": EASA_TAXIWAY_SEPARATION_REF},
    (3, "C", "NI"): {"offset_m": 93.0, "ref": EASA_TAXIWAY_SEPARATION_REF},
    (4, "C", "NI"): {"offset_m": 93.0, "ref": EASA_TAXIWAY_SEPARATION_REF},
    (3, "D", "NI"): {"offset_m": 101.0, "ref": EASA_TAXIWAY_SEPARATION_REF},
    (4, "D", "NI"): {"offset_m": 101.0, "ref": EASA_TAXIWAY_SEPARATION_REF},
    (3, "E", "NI"): {"offset_m": 107.5, "ref": EASA_TAXIWAY_SEPARATION_REF},
    (4, "E", "NI"): {"offset_m": 107.5, "ref": EASA_TAXIWAY_SEPARATION_REF},
    (3, "F", "NI"): {"offset_m": 115.0, "ref": EASA_TAXIWAY_SEPARATION_REF},
    (4, "F", "NI"): {"offset_m": 115.0, "ref": EASA_TAXIWAY_SEPARATION_REF},
}

TAXIWAY_TO_TAXIWAY_SEPARATION_PARAMS: Dict[str, Dict[str, Any]] = {
    "A": {"offset_m": 23.0, "ref": EASA_TAXIWAY_SEPARATION_REF},
    "B": {"offset_m": 32.0, "ref": EASA_TAXIWAY_SEPARATION_REF},
    "C": {"offset_m": 44.0, "ref": EASA_TAXIWAY_SEPARATION_REF},
    "D": {"offset_m": 63.0, "ref": EASA_TAXIWAY_SEPARATION_REF},
    "E": {"offset_m": 76.0, "ref": EASA_TAXIWAY_SEPARATION_REF},
    "F": {"offset_m": 91.0, "ref": EASA_TAXIWAY_SEPARATION_REF},
}

TAXIWAY_OBJECT_SEPARATION_PARAMS: Dict[str, Dict[str, Any]] = {
    "A": {"offset_m": 15.5, "ref": EASA_TAXIWAY_SEPARATION_REF},
    "B": {"offset_m": 20.0, "ref": EASA_TAXIWAY_SEPARATION_REF},
    "C": {"offset_m": 26.0, "ref": EASA_TAXIWAY_SEPARATION_REF},
    "D": {"offset_m": 37.0, "ref": EASA_TAXIWAY_SEPARATION_REF},
    "E": {"offset_m": 43.5, "ref": EASA_TAXIWAY_SEPARATION_REF},
    "F": {"offset_m": 51.0, "ref": EASA_TAXIWAY_SEPARATION_REF},
}

STAND_TAXILANE_TO_STAND_TAXILANE_SEPARATION_PARAMS: Dict[str, Dict[str, Any]] = {
    "A": {"offset_m": 19.5, "ref": EASA_TAXIWAY_SEPARATION_REF},
    "B": {"offset_m": 28.5, "ref": EASA_TAXIWAY_SEPARATION_REF},
    "C": {"offset_m": 40.5, "ref": EASA_TAXIWAY_SEPARATION_REF},
    "D": {"offset_m": 59.5, "ref": EASA_TAXIWAY_SEPARATION_REF},
    "E": {"offset_m": 72.5, "ref": EASA_TAXIWAY_SEPARATION_REF},
    "F": {"offset_m": 87.5, "ref": EASA_TAXIWAY_SEPARATION_REF},
}

STAND_TAXILANE_OBJECT_SEPARATION_PARAMS: Dict[str, Dict[str, Any]] = {
    "A": {"offset_m": 12.0, "ref": EASA_TAXIWAY_SEPARATION_REF},
    "B": {"offset_m": 16.5, "ref": EASA_TAXIWAY_SEPARATION_REF},
    "C": {"offset_m": 22.5, "ref": EASA_TAXIWAY_SEPARATION_REF},
    "D": {"offset_m": 33.5, "ref": EASA_TAXIWAY_SEPARATION_REF},
    "E": {"offset_m": 40.0, "ref": EASA_TAXIWAY_SEPARATION_REF},
    "F": {"offset_m": 47.5, "ref": EASA_TAXIWAY_SEPARATION_REF},
}

PARALLEL_RUNWAY_SEPARATION_PARAMS: Dict[Tuple[Any, ...], Dict[str, Any]] = {}


def _arc_letter(arc_let: Optional[str]) -> str:
    return arc_let.strip().upper() if arc_let else ""


def _runway_instrument_group(runway_type_str: Optional[str]) -> str:
    return "NI" if get_runway_type_abbr(runway_type_str) == "NI" else "INSTR"


def _copy_by_letter(params_by_letter: Dict[str, Dict[str, Any]], arc_let: Optional[str]) -> Optional[Dict[str, Any]]:
    params = params_by_letter.get(_arc_letter(arc_let))
    return params.copy() if params else None


def get_taxiway_separation_offset(
    arc_num: int, arc_let: Optional[str], runway_type_str: Optional[str]
) -> Optional[Dict[str, Any]]:
    """Return taxiway centre line to runway centre line separation."""
    if not isinstance(arc_num, int) or arc_num not in [1, 2, 3, 4]:
        LOGGER.warning("Invalid ARC Number %r for EASA Taxiway Sep lookup.", arc_num)
        return None

    arc_let_str = _arc_letter(arc_let)
    if not arc_let_str:
        LOGGER.info("Missing ARC Letter for EASA Taxiway Sep lookup (Code %s).", arc_num)
        return None

    key = (arc_num, arc_let_str, _runway_instrument_group(runway_type_str))
    params = TAXIWAY_RUNWAY_SEPARATION_PARAMS.get(key)
    return params.copy() if params else None


def get_taxiway_to_taxiway_separation(arc_let: Optional[str]) -> Optional[Dict[str, Any]]:
    return _copy_by_letter(TAXIWAY_TO_TAXIWAY_SEPARATION_PARAMS, arc_let)


def get_taxiway_object_separation(arc_let: Optional[str]) -> Optional[Dict[str, Any]]:
    return _copy_by_letter(TAXIWAY_OBJECT_SEPARATION_PARAMS, arc_let)


def get_stand_taxilane_to_stand_taxilane_separation(arc_let: Optional[str]) -> Optional[Dict[str, Any]]:
    return _copy_by_letter(STAND_TAXILANE_TO_STAND_TAXILANE_SEPARATION_PARAMS, arc_let)


def get_stand_taxilane_object_separation(arc_let: Optional[str]) -> Optional[Dict[str, Any]]:
    return _copy_by_letter(STAND_TAXILANE_OBJECT_SEPARATION_PARAMS, arc_let)


def get_parallel_runway_separation(
    arc_num_1: Optional[int] = None,
    arc_num_2: Optional[int] = None,
    runway_type_1: Optional[str] = None,
    runway_type_2: Optional[str] = None,
    operation_type: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Placeholder for minimum parallel runway separation rules."""
    return None


__all__ = [
    "EASA_TAXIWAY_SEPARATION_REF",
    "TAXIWAY_RUNWAY_SEPARATION_PARAMS",
    "TAXIWAY_TO_TAXIWAY_SEPARATION_PARAMS",
    "TAXIWAY_OBJECT_SEPARATION_PARAMS",
    "STAND_TAXILANE_TO_STAND_TAXILANE_SEPARATION_PARAMS",
    "STAND_TAXILANE_OBJECT_SEPARATION_PARAMS",
    "PARALLEL_RUNWAY_SEPARATION_PARAMS",
    "get_taxiway_separation_offset",
    "get_taxiway_to_taxiway_separation",
    "get_taxiway_object_separation",
    "get_stand_taxilane_to_stand_taxilane_separation",
    "get_stand_taxilane_object_separation",
    "get_parallel_runway_separation",
]
