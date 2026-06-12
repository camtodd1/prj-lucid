"""UK CAA CAP 168 taxiway and runway separation policy."""

from typing import Any, Dict, Optional

from .classification import get_runway_type_abbr

CAP168_PARALLEL_NON_INSTRUMENT_RUNWAY_REF = "CAP 168 3.21"
CAP168_PARALLEL_INSTRUMENT_RUNWAY_REF = "CAP 168 3.24-3.25"

PARALLEL_RUNWAY_SEPARATION_PARAMS: Dict[tuple, Dict[str, Any]] = {
    ("NI_SIMULTANEOUS", 1): {
        "distance_m": 120.0,
        "ref": CAP168_PARALLEL_NON_INSTRUMENT_RUNWAY_REF,
        "condition": "Parallel non-instrument runways intended for simultaneous use; higher code number is 1.",
    },
    ("NI_SIMULTANEOUS", 2): {
        "distance_m": 150.0,
        "ref": CAP168_PARALLEL_NON_INSTRUMENT_RUNWAY_REF,
        "condition": "Parallel non-instrument runways intended for simultaneous use; higher code number is 2.",
    },
    ("NI_SIMULTANEOUS", 3): {
        "distance_m": 210.0,
        "ref": CAP168_PARALLEL_NON_INSTRUMENT_RUNWAY_REF,
        "condition": "Parallel non-instrument runways intended for simultaneous use; higher code number is 3 or 4.",
    },
    ("NI_SIMULTANEOUS", 4): {
        "distance_m": 210.0,
        "ref": CAP168_PARALLEL_NON_INSTRUMENT_RUNWAY_REF,
        "condition": "Parallel non-instrument runways intended for simultaneous use; higher code number is 3 or 4.",
    },
    ("INSTR_INDEPENDENT_APPROACHES", 0): {
        "distance_m": 1035.0,
        "ref": CAP168_PARALLEL_INSTRUMENT_RUNWAY_REF,
        "condition": "Parallel instrument runways intended for independent parallel approaches.",
    },
    ("INSTR_DEPENDENT_APPROACHES", 0): {
        "distance_m": 915.0,
        "ref": CAP168_PARALLEL_INSTRUMENT_RUNWAY_REF,
        "condition": "Parallel instrument runways intended for dependent parallel approaches.",
    },
    ("INSTR_INDEPENDENT_DEPARTURES", 0): {
        "distance_m": 760.0,
        "ref": CAP168_PARALLEL_INSTRUMENT_RUNWAY_REF,
        "condition": "Parallel instrument runways intended for independent parallel departures.",
    },
    ("INSTR_SEGREGATED", 0): {
        "distance_m": 760.0,
        "ref": CAP168_PARALLEL_INSTRUMENT_RUNWAY_REF,
        "condition": "Parallel instrument runways intended for segregated parallel operations.",
    },
}

TAXIWAY_TRACEABILITY = {
    "items": {
        "parallel_non_instrument_runways": {
            "source": CAP168_PARALLEL_NON_INSTRUMENT_RUNWAY_REF,
            "status": "operational_verified",
            "implementation": "PARALLEL_RUNWAY_SEPARATION_PARAMS[NI_SIMULTANEOUS]",
            "notes": "Minimum distance is selected by the higher code number.",
        },
        "parallel_instrument_runways": {
            "source": CAP168_PARALLEL_INSTRUMENT_RUNWAY_REF,
            "status": "operational_verified",
            "implementation": "PARALLEL_RUNWAY_SEPARATION_PARAMS[INSTR_*]",
            "notes": "Minimum distance is selected by simultaneous operation type. Segregated operations apply threshold stagger adjustments.",
        },
    }
}


def get_taxiway_traceability() -> Dict[str, Any]:
    return TAXIWAY_TRACEABILITY.copy()


def get_taxiway_separation_offset(arc_num: int, arc_let: Optional[str], runway_type_str: Optional[str]):
    del arc_num, arc_let, runway_type_str
    return None


def get_taxiway_to_taxiway_separation(arc_let: Optional[str]):
    del arc_let
    return None


def get_taxiway_object_separation(arc_let: Optional[str]):
    del arc_let
    return None


def get_stand_taxilane_to_stand_taxilane_separation(arc_let: Optional[str]):
    del arc_let
    return None


def get_stand_taxilane_object_separation(arc_let: Optional[str]):
    del arc_let
    return None


def get_parallel_runway_separation(
    arc_num_1: Optional[int] = None,
    arc_num_2: Optional[int] = None,
    runway_type_1: Optional[str] = None,
    runway_type_2: Optional[str] = None,
    operation_type: Optional[str] = None,
    arrival_threshold_stagger_m: Optional[float] = None,
):
    if not isinstance(arc_num_1, int) or not isinstance(arc_num_2, int):
        return None
    if arc_num_1 not in [1, 2, 3, 4] or arc_num_2 not in [1, 2, 3, 4]:
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
    return result


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


__all__ = [
    "CAP168_PARALLEL_NON_INSTRUMENT_RUNWAY_REF",
    "CAP168_PARALLEL_INSTRUMENT_RUNWAY_REF",
    "PARALLEL_RUNWAY_SEPARATION_PARAMS",
    "TAXIWAY_TRACEABILITY",
    "get_taxiway_traceability",
    "get_taxiway_separation_offset",
    "get_taxiway_to_taxiway_separation",
    "get_taxiway_object_separation",
    "get_stand_taxilane_to_stand_taxilane_separation",
    "get_stand_taxilane_object_separation",
    "get_parallel_runway_separation",
]
