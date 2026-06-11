"""EASA taxiway and runway separation policy."""

import logging
from typing import Any, Dict, Optional, Tuple

from .classification import get_runway_type_abbr

LOGGER = logging.getLogger(__name__)

EASA_TAXIWAY_SEPARATION_REF = "CS ADR-DSN.D.260 Table D-1"
EASA_PARALLEL_NON_INSTRUMENT_RUNWAY_REF = "CS ADR-DSN.B.050"
EASA_PARALLEL_INSTRUMENT_RUNWAY_REF = "CS ADR-DSN.B.055"
SOURCE_PUBLICATION = "EASA Easy Access Rules for Aerodromes, CS-ADR-DSN Issue 7"
SOURCE_URL = (
    "https://www.easa.europa.eu/en/document-library/easy-access-rules/"
    "online-publications/easy-access-rules-aerodromes-regulation-eu"
)
TAXIWAY_SOURCE_URL = f"{SOURCE_URL}?erules-id=ERULES-1963177438-2194"
PARALLEL_NON_INSTRUMENT_SOURCE_URL = f"{SOURCE_URL}?erules-id=ERULES-1963177438-2151"
PARALLEL_INSTRUMENT_SOURCE_URL = f"{SOURCE_URL}?erules-id=ERULES-1963177438-2152"

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

TABLE_D1_TRACEABILITY_ITEMS = {
    "taxiway_runway_separation": {
        "source": EASA_TAXIWAY_SEPARATION_REF,
        "status": "operational_verified",
        "implementation": "TAXIWAY_RUNWAY_SEPARATION_PARAMS",
        "notes": "Table D-1 columns 2-9. Keyed by code number, code letter, and runway instrument group.",
    },
    "taxiway_to_taxiway_separation": {
        "source": EASA_TAXIWAY_SEPARATION_REF,
        "status": "operational_verified",
        "implementation": "TAXIWAY_TO_TAXIWAY_SEPARATION_PARAMS",
        "notes": "Table D-1 column 10.",
    },
    "taxiway_object_separation": {
        "source": EASA_TAXIWAY_SEPARATION_REF,
        "status": "operational_verified",
        "implementation": "TAXIWAY_OBJECT_SEPARATION_PARAMS",
        "notes": "Table D-1 column 11.",
    },
    "stand_taxilane_to_stand_taxilane_separation": {
        "source": EASA_TAXIWAY_SEPARATION_REF,
        "status": "operational_verified",
        "implementation": "STAND_TAXILANE_TO_STAND_TAXILANE_SEPARATION_PARAMS",
        "notes": "Table D-1 column 12.",
    },
    "stand_taxilane_object_separation": {
        "source": EASA_TAXIWAY_SEPARATION_REF,
        "status": "operational_verified",
        "implementation": "STAND_TAXILANE_OBJECT_SEPARATION_PARAMS",
        "notes": "Table D-1 column 13.",
    },
}

PARALLEL_RUNWAY_SEPARATION_PARAMS: Dict[Tuple[str, int], Dict[str, Any]] = {
    ("NI_SIMULTANEOUS", 1): {
        "distance_m": 120.0,
        "ref": EASA_PARALLEL_NON_INSTRUMENT_RUNWAY_REF,
        "condition": "Parallel non-instrument runways intended for simultaneous use; higher code number is 1.",
    },
    ("NI_SIMULTANEOUS", 2): {
        "distance_m": 150.0,
        "ref": EASA_PARALLEL_NON_INSTRUMENT_RUNWAY_REF,
        "condition": "Parallel non-instrument runways intended for simultaneous use; higher code number is 2.",
    },
    ("NI_SIMULTANEOUS", 3): {
        "distance_m": 210.0,
        "ref": EASA_PARALLEL_NON_INSTRUMENT_RUNWAY_REF,
        "condition": "Parallel non-instrument runways intended for simultaneous use; higher code number is 3 or 4.",
    },
    ("NI_SIMULTANEOUS", 4): {
        "distance_m": 210.0,
        "ref": EASA_PARALLEL_NON_INSTRUMENT_RUNWAY_REF,
        "condition": "Parallel non-instrument runways intended for simultaneous use; higher code number is 3 or 4.",
    },
    ("INSTR_INDEPENDENT_APPROACHES", 0): {
        "distance_m": 1035.0,
        "ref": EASA_PARALLEL_INSTRUMENT_RUNWAY_REF,
        "condition": "Parallel instrument runways intended for independent parallel approaches.",
    },
    ("INSTR_DEPENDENT_APPROACHES", 0): {
        "distance_m": 915.0,
        "ref": EASA_PARALLEL_INSTRUMENT_RUNWAY_REF,
        "condition": "Parallel instrument runways intended for dependent parallel approaches.",
    },
    ("INSTR_INDEPENDENT_DEPARTURES", 0): {
        "distance_m": 760.0,
        "ref": EASA_PARALLEL_INSTRUMENT_RUNWAY_REF,
        "condition": "Parallel instrument runways intended for independent parallel departures.",
    },
    ("INSTR_SEGREGATED", 0): {
        "distance_m": 760.0,
        "ref": EASA_PARALLEL_INSTRUMENT_RUNWAY_REF,
        "condition": "Parallel instrument runways intended for segregated parallel operations.",
    },
}

PARALLEL_RUNWAY_TRACEABILITY_ITEMS = {
    "parallel_non_instrument_runways": {
        "source": EASA_PARALLEL_NON_INSTRUMENT_RUNWAY_REF,
        "status": "operational_verified",
        "implementation": "PARALLEL_RUNWAY_SEPARATION_PARAMS[NI_SIMULTANEOUS]",
        "notes": "Minimum distance is selected by the higher code number of the two non-instrument runways.",
    },
    "parallel_instrument_runways": {
        "source": EASA_PARALLEL_INSTRUMENT_RUNWAY_REF,
        "status": "operational_verified",
        "implementation": "PARALLEL_RUNWAY_SEPARATION_PARAMS[INSTR_*]",
        "notes": "Minimum distance is selected by parallel operation type. Segregated operations apply threshold stagger adjustments.",
    },
}

TAXIWAY_TRACEABILITY = {
    "source_publication": SOURCE_PUBLICATION,
    "source_url": SOURCE_URL,
    "items": {
        **TABLE_D1_TRACEABILITY_ITEMS,
        **PARALLEL_RUNWAY_TRACEABILITY_ITEMS,
    },
}


def _arc_letter(arc_let: Optional[str]) -> str:
    return arc_let.strip().upper() if arc_let else ""


def _runway_instrument_group(runway_type_str: Optional[str]) -> str:
    return "NI" if get_runway_type_abbr(runway_type_str) == "NI" else "INSTR"


def _operation_key(operation_type: Optional[str]) -> str:
    value = (operation_type or "simultaneous").strip().lower().replace("-", "_").replace(" ", "_")
    if value in {"simultaneous", "simultaneous_use", "simultaneous_operations"}:
        return "NI_SIMULTANEOUS"
    if value in {"independent_parallel_approaches", "independent_approaches", "independent_parallel_approach"}:
        return "INSTR_INDEPENDENT_APPROACHES"
    if value in {"dependent_parallel_approaches", "dependent_approaches", "dependent_parallel_approach"}:
        return "INSTR_DEPENDENT_APPROACHES"
    if value in {"independent_parallel_departures", "independent_departures", "independent_parallel_departure"}:
        return "INSTR_INDEPENDENT_DEPARTURES"
    if value in {"segregated_parallel_operations", "segregated_operations", "segregated"}:
        return "INSTR_SEGREGATED"
    return value.upper()


def _segregated_parallel_distance(base_distance_m: float, arrival_threshold_stagger_m: Optional[float]) -> Dict[str, Any]:
    """Apply B.055 segregated-operations stagger adjustment.

    Positive stagger means the arrival runway threshold is staggered toward
    the arriving aircraft. Negative stagger means it is staggered away.
    """
    if arrival_threshold_stagger_m is None:
        return {
            "distance_m": base_distance_m,
            "base_distance_m": base_distance_m,
            "threshold_stagger_m": None,
            "stagger_adjustment_m": 0.0,
        }

    stagger_m = float(arrival_threshold_stagger_m)
    adjustment_steps = int(abs(stagger_m) // 150.0)
    adjustment_m = adjustment_steps * 30.0
    if stagger_m > 0:
        distance_m = max(300.0, base_distance_m - adjustment_m)
        signed_adjustment_m = -adjustment_m
    elif stagger_m < 0:
        distance_m = base_distance_m + adjustment_m
        signed_adjustment_m = adjustment_m
    else:
        distance_m = base_distance_m
        signed_adjustment_m = 0.0

    return {
        "distance_m": distance_m,
        "base_distance_m": base_distance_m,
        "threshold_stagger_m": stagger_m,
        "stagger_adjustment_m": signed_adjustment_m,
    }


def _copy_by_letter(params_by_letter: Dict[str, Dict[str, Any]], arc_let: Optional[str]) -> Optional[Dict[str, Any]]:
    params = params_by_letter.get(_arc_letter(arc_let))
    return params.copy() if params else None


def get_taxiway_traceability() -> Dict[str, Any]:
    """Return source traceability metadata for EASA taxiway/separation rules."""
    return TAXIWAY_TRACEABILITY.copy()


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
    arrival_threshold_stagger_m: Optional[float] = None,
) -> Optional[Dict[str, Any]]:
    """Return minimum centre line separation for parallel runways."""
    if not isinstance(arc_num_1, int) or not isinstance(arc_num_2, int):
        return None
    if arc_num_1 not in [1, 2, 3, 4] or arc_num_2 not in [1, 2, 3, 4]:
        LOGGER.warning(
            "Invalid ARC Numbers %r/%r for EASA parallel runway separation lookup.",
            arc_num_1,
            arc_num_2,
        )
        return None

    runway_1_is_ni = _runway_instrument_group(runway_type_1) == "NI"
    runway_2_is_ni = _runway_instrument_group(runway_type_2) == "NI"
    operation_key = _operation_key(operation_type)

    if runway_1_is_ni and runway_2_is_ni:
        higher_code = max(arc_num_1, arc_num_2)
        params = PARALLEL_RUNWAY_SEPARATION_PARAMS.get((operation_key, higher_code))
    elif not runway_1_is_ni and not runway_2_is_ni:
        higher_code = max(arc_num_1, arc_num_2)
        params = PARALLEL_RUNWAY_SEPARATION_PARAMS.get((operation_key, 0))
    else:
        return None

    if not params:
        return None

    result = params.copy()
    result["higher_code_number"] = higher_code
    result["operation_type"] = operation_type or "simultaneous"
    if operation_key == "INSTR_SEGREGATED":
        result.update(_segregated_parallel_distance(float(params["distance_m"]), arrival_threshold_stagger_m))

    if runway_1_is_ni and runway_2_is_ni:
        result["notes"] = (
            "Independent parallel approach combinations may use other minimum distances and associated "
            "conditions when determined not to adversely affect safety. Wake turbulence categorisation and "
            "separation minima are addressed in PANS-ATM Doc 4444, Chapter 4.9 and Chapter 5.8."
        )
    else:
        result["notes"] = (
            "Other combinations of minimum distances should account for ATM and operational aspects. "
            "Guidance on procedures and facilities for simultaneous operations is in ICAO PANS-ATM "
            "Doc 4444 Chapter 6, PANS-OPS Doc 8168, and ICAO Doc 9643 SOIR."
        )
    return result


__all__ = [
    "EASA_TAXIWAY_SEPARATION_REF",
    "EASA_PARALLEL_NON_INSTRUMENT_RUNWAY_REF",
    "EASA_PARALLEL_INSTRUMENT_RUNWAY_REF",
    "SOURCE_PUBLICATION",
    "SOURCE_URL",
    "TAXIWAY_SOURCE_URL",
    "PARALLEL_NON_INSTRUMENT_SOURCE_URL",
    "PARALLEL_INSTRUMENT_SOURCE_URL",
    "TAXIWAY_RUNWAY_SEPARATION_PARAMS",
    "TAXIWAY_TO_TAXIWAY_SEPARATION_PARAMS",
    "TAXIWAY_OBJECT_SEPARATION_PARAMS",
    "STAND_TAXILANE_TO_STAND_TAXILANE_SEPARATION_PARAMS",
    "STAND_TAXILANE_OBJECT_SEPARATION_PARAMS",
    "PARALLEL_RUNWAY_SEPARATION_PARAMS",
    "TAXIWAY_TRACEABILITY",
    "TABLE_D1_TRACEABILITY_ITEMS",
    "PARALLEL_RUNWAY_TRACEABILITY_ITEMS",
    "get_taxiway_traceability",
    "get_taxiway_separation_offset",
    "get_taxiway_to_taxiway_separation",
    "get_taxiway_object_separation",
    "get_stand_taxilane_to_stand_taxilane_separation",
    "get_stand_taxilane_object_separation",
    "get_parallel_runway_separation",
]
