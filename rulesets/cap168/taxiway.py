"""UK CAA CAP 168 taxiway and runway separation policy."""

from typing import Any, Dict, Optional

from .classification import get_runway_type_abbr

SOURCE_PUBLICATION = "UK CAA CAP 168 Licensing of Aerodromes, Edition 13"
SOURCE_URL = "https://www.caa.co.uk/CAP168"
CAP168_PARALLEL_NON_INSTRUMENT_RUNWAY_REF = "CAP 168 3.21"
CAP168_PARALLEL_INSTRUMENT_RUNWAY_REF = "CAP 168 3.24-3.25"
CAP168_TAXIWAY_RUNWAY_SEPARATION_REF = "CAP 168 3.163 Table 3.4(a)-(b)"
CAP168_TAXIWAY_MINIMUM_SEPARATION_REF = "CAP 168 3.163 Table 3.4(c)"

TAXIWAY_RUNWAY_SEPARATION_PARAMS: Dict[tuple, Dict[str, Any]] = {
    (1, "A", "INSTR"): {"offset_m": 77.5, "ref": CAP168_TAXIWAY_RUNWAY_SEPARATION_REF},
    (2, "A", "INSTR"): {"offset_m": 77.5, "ref": CAP168_TAXIWAY_RUNWAY_SEPARATION_REF},
    (1, "B", "INSTR"): {"offset_m": 82.0, "ref": CAP168_TAXIWAY_RUNWAY_SEPARATION_REF},
    (2, "B", "INSTR"): {"offset_m": 82.0, "ref": CAP168_TAXIWAY_RUNWAY_SEPARATION_REF},
    (3, "B", "INSTR"): {"offset_m": 152.0, "ref": CAP168_TAXIWAY_RUNWAY_SEPARATION_REF},
    (1, "C", "INSTR"): {"offset_m": 88.0, "ref": CAP168_TAXIWAY_RUNWAY_SEPARATION_REF},
    (2, "C", "INSTR"): {"offset_m": 88.0, "ref": CAP168_TAXIWAY_RUNWAY_SEPARATION_REF},
    (3, "C", "INSTR"): {"offset_m": 158.0, "ref": CAP168_TAXIWAY_RUNWAY_SEPARATION_REF},
    (4, "C", "INSTR"): {"offset_m": 158.0, "ref": CAP168_TAXIWAY_RUNWAY_SEPARATION_REF},
    (3, "D", "INSTR"): {"offset_m": 166.0, "ref": CAP168_TAXIWAY_RUNWAY_SEPARATION_REF},
    (4, "D", "INSTR"): {"offset_m": 166.0, "ref": CAP168_TAXIWAY_RUNWAY_SEPARATION_REF},
    (3, "E", "INSTR"): {"offset_m": 172.5, "ref": CAP168_TAXIWAY_RUNWAY_SEPARATION_REF},
    (4, "E", "INSTR"): {"offset_m": 172.5, "ref": CAP168_TAXIWAY_RUNWAY_SEPARATION_REF},
    (3, "F", "INSTR"): {"offset_m": 180.0, "ref": CAP168_TAXIWAY_RUNWAY_SEPARATION_REF},
    (4, "F", "INSTR"): {"offset_m": 180.0, "ref": CAP168_TAXIWAY_RUNWAY_SEPARATION_REF},
    (1, "A", "NI"): {"offset_m": 37.5, "ref": CAP168_TAXIWAY_RUNWAY_SEPARATION_REF},
    (2, "A", "NI"): {"offset_m": 47.5, "ref": CAP168_TAXIWAY_RUNWAY_SEPARATION_REF},
    (1, "B", "NI"): {"offset_m": 42.0, "ref": CAP168_TAXIWAY_RUNWAY_SEPARATION_REF},
    (2, "B", "NI"): {"offset_m": 52.0, "ref": CAP168_TAXIWAY_RUNWAY_SEPARATION_REF},
    (3, "B", "NI"): {"offset_m": 67.0, "ref": CAP168_TAXIWAY_RUNWAY_SEPARATION_REF},
    (1, "C", "NI"): {"offset_m": 48.0, "ref": CAP168_TAXIWAY_RUNWAY_SEPARATION_REF},
    (2, "C", "NI"): {"offset_m": 58.0, "ref": CAP168_TAXIWAY_RUNWAY_SEPARATION_REF},
    (3, "C", "NI"): {"offset_m": 73.0, "ref": CAP168_TAXIWAY_RUNWAY_SEPARATION_REF},
    (4, "C", "NI"): {"offset_m": 93.0, "ref": CAP168_TAXIWAY_RUNWAY_SEPARATION_REF},
    (3, "D", "NI"): {"offset_m": 81.0, "ref": CAP168_TAXIWAY_RUNWAY_SEPARATION_REF},
    (4, "D", "NI"): {"offset_m": 101.0, "ref": CAP168_TAXIWAY_RUNWAY_SEPARATION_REF},
    (3, "E", "NI"): {"offset_m": 81.0, "ref": CAP168_TAXIWAY_RUNWAY_SEPARATION_REF},
    (4, "E", "NI"): {"offset_m": 101.0, "ref": CAP168_TAXIWAY_RUNWAY_SEPARATION_REF},
    (3, "F", "NI"): {"offset_m": 95.0, "ref": CAP168_TAXIWAY_RUNWAY_SEPARATION_REF},
    (4, "F", "NI"): {"offset_m": 115.0, "ref": CAP168_TAXIWAY_RUNWAY_SEPARATION_REF},
}

TAXIWAY_TO_TAXIWAY_SEPARATION_PARAMS: Dict[str, Dict[str, Any]] = {
    "A": {"offset_m": 23.0, "ref": CAP168_TAXIWAY_MINIMUM_SEPARATION_REF},
    "B": {"offset_m": 32.0, "ref": CAP168_TAXIWAY_MINIMUM_SEPARATION_REF},
    "C": {"offset_m": 44.0, "ref": CAP168_TAXIWAY_MINIMUM_SEPARATION_REF},
    "D": {"offset_m": 63.0, "ref": CAP168_TAXIWAY_MINIMUM_SEPARATION_REF},
    "E": {"offset_m": 76.0, "ref": CAP168_TAXIWAY_MINIMUM_SEPARATION_REF},
    "F": {"offset_m": 91.0, "ref": CAP168_TAXIWAY_MINIMUM_SEPARATION_REF},
}

TAXIWAY_OBJECT_SEPARATION_PARAMS: Dict[str, Dict[str, Any]] = {
    "A": {"offset_m": 15.5, "ref": CAP168_TAXIWAY_MINIMUM_SEPARATION_REF},
    "B": {"offset_m": 20.0, "ref": CAP168_TAXIWAY_MINIMUM_SEPARATION_REF},
    "C": {"offset_m": 26.0, "ref": CAP168_TAXIWAY_MINIMUM_SEPARATION_REF},
    "D": {"offset_m": 37.0, "ref": CAP168_TAXIWAY_MINIMUM_SEPARATION_REF},
    "E": {"offset_m": 43.5, "ref": CAP168_TAXIWAY_MINIMUM_SEPARATION_REF},
    "F": {"offset_m": 51.0, "ref": CAP168_TAXIWAY_MINIMUM_SEPARATION_REF},
}

STAND_TAXILANE_TO_STAND_TAXILANE_SEPARATION_PARAMS: Dict[str, Dict[str, Any]] = {
    "A": {"offset_m": 19.5, "ref": CAP168_TAXIWAY_MINIMUM_SEPARATION_REF},
    "B": {"offset_m": 28.5, "ref": CAP168_TAXIWAY_MINIMUM_SEPARATION_REF},
    "C": {"offset_m": 40.5, "ref": CAP168_TAXIWAY_MINIMUM_SEPARATION_REF},
    "D": {"offset_m": 59.5, "ref": CAP168_TAXIWAY_MINIMUM_SEPARATION_REF},
    "E": {"offset_m": 72.5, "ref": CAP168_TAXIWAY_MINIMUM_SEPARATION_REF},
    "F": {"offset_m": 87.5, "ref": CAP168_TAXIWAY_MINIMUM_SEPARATION_REF},
}

STAND_TAXILANE_OBJECT_SEPARATION_PARAMS: Dict[str, Dict[str, Any]] = {
    "A": {"offset_m": 15.0, "ref": CAP168_TAXIWAY_MINIMUM_SEPARATION_REF},
    "B": {"offset_m": 16.5, "ref": CAP168_TAXIWAY_MINIMUM_SEPARATION_REF},
    "C": {"offset_m": 22.5, "ref": CAP168_TAXIWAY_MINIMUM_SEPARATION_REF},
    "D": {"offset_m": 33.5, "ref": CAP168_TAXIWAY_MINIMUM_SEPARATION_REF},
    "E": {"offset_m": 40.0, "ref": CAP168_TAXIWAY_MINIMUM_SEPARATION_REF},
    "F": {"offset_m": 47.5, "ref": CAP168_TAXIWAY_MINIMUM_SEPARATION_REF},
}

TAXIWAY_OBJECT_HEIGHT_RESTRICTION_PARAMS = {
    "edge_distance_by_code_letter_m": {
        "A": 7.5,
        "B": 7.5,
        "C": 11.0,
        "D": 18.0,
        "E": 18.0,
        "F": 22.0,
    },
    "inner_height_limit_m": 0.36,
    "outer_height_limit_m": 1.5,
    "temporary_obstacle_wingtip_clearance_factor": 0.2,
    "ref": "CAP 168 3.164-3.167",
}

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
    "source_publication": SOURCE_PUBLICATION,
    "source_url": SOURCE_URL,
    "items": {
        "taxiway_runway_separation": {
            "source": CAP168_TAXIWAY_RUNWAY_SEPARATION_REF,
            "status": "operational_verified",
            "implementation": "TAXIWAY_RUNWAY_SEPARATION_PARAMS",
            "notes": "Table 3.4(a)-(b), keyed by runway code number, code letter, and runway instrument group.",
        },
        "taxiway_to_taxiway_separation": {
            "source": CAP168_TAXIWAY_MINIMUM_SEPARATION_REF,
            "status": "operational_verified",
            "implementation": "TAXIWAY_TO_TAXIWAY_SEPARATION_PARAMS",
            "notes": "Table 3.4(c) taxiway centreline to taxiway centreline values.",
        },
        "taxiway_object_separation": {
            "source": CAP168_TAXIWAY_MINIMUM_SEPARATION_REF,
            "status": "operational_verified",
            "implementation": "TAXIWAY_OBJECT_SEPARATION_PARAMS",
            "notes": "Table 3.4(c) taxiway/apron taxiway centreline to object values.",
        },
        "stand_taxilane_to_stand_taxilane_separation": {
            "source": CAP168_TAXIWAY_MINIMUM_SEPARATION_REF,
            "status": "operational_verified",
            "implementation": "STAND_TAXILANE_TO_STAND_TAXILANE_SEPARATION_PARAMS",
            "notes": "Table 3.4(c) aircraft stand taxilane centreline values.",
        },
        "stand_taxilane_object_separation": {
            "source": CAP168_TAXIWAY_MINIMUM_SEPARATION_REF,
            "status": "operational_verified",
            "implementation": "STAND_TAXILANE_OBJECT_SEPARATION_PARAMS",
            "notes": "Table 3.4(c) aircraft stand taxilane centreline to object values.",
        },
        "taxiway_object_height_restrictions": {
            "source": "CAP 168 3.164-3.167",
            "status": "operational_verified",
            "implementation": "TAXIWAY_OBJECT_HEIGHT_RESTRICTION_PARAMS",
            "notes": "Object-height restrictions near taxiway edges and temporary-obstacle wingtip clearance.",
        },
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
    if not isinstance(arc_num, int) or arc_num not in [1, 2, 3, 4]:
        return None
    arc_let_str = _arc_letter(arc_let)
    if not arc_let_str:
        return None
    params = TAXIWAY_RUNWAY_SEPARATION_PARAMS.get((arc_num, arc_let_str, _runway_instrument_group(runway_type_str)))
    return params.copy() if params else None


def get_taxiway_to_taxiway_separation(arc_let: Optional[str]):
    return _copy_by_letter(TAXIWAY_TO_TAXIWAY_SEPARATION_PARAMS, arc_let)


def get_taxiway_object_separation(arc_let: Optional[str]):
    return _copy_by_letter(TAXIWAY_OBJECT_SEPARATION_PARAMS, arc_let)


def get_stand_taxilane_to_stand_taxilane_separation(arc_let: Optional[str]):
    return _copy_by_letter(STAND_TAXILANE_TO_STAND_TAXILANE_SEPARATION_PARAMS, arc_let)


def get_stand_taxilane_object_separation(arc_let: Optional[str]):
    return _copy_by_letter(STAND_TAXILANE_OBJECT_SEPARATION_PARAMS, arc_let)


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


def _arc_letter(arc_let: Optional[str]) -> str:
    return arc_let.strip().upper() if arc_let else ""


def _copy_by_letter(params_by_letter: Dict[str, Dict[str, Any]], arc_let: Optional[str]):
    params = params_by_letter.get(_arc_letter(arc_let))
    return params.copy() if params else None


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
    "SOURCE_PUBLICATION",
    "SOURCE_URL",
    "CAP168_PARALLEL_NON_INSTRUMENT_RUNWAY_REF",
    "CAP168_PARALLEL_INSTRUMENT_RUNWAY_REF",
    "CAP168_TAXIWAY_RUNWAY_SEPARATION_REF",
    "CAP168_TAXIWAY_MINIMUM_SEPARATION_REF",
    "TAXIWAY_RUNWAY_SEPARATION_PARAMS",
    "TAXIWAY_TO_TAXIWAY_SEPARATION_PARAMS",
    "TAXIWAY_OBJECT_SEPARATION_PARAMS",
    "STAND_TAXILANE_TO_STAND_TAXILANE_SEPARATION_PARAMS",
    "STAND_TAXILANE_OBJECT_SEPARATION_PARAMS",
    "TAXIWAY_OBJECT_HEIGHT_RESTRICTION_PARAMS",
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
