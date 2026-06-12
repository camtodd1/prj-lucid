"""EASA CS-ADR-DSN physical runway dimension policy."""

from typing import Any, Dict, Optional

SOURCE_PUBLICATION = "EASA Easy Access Rules for Aerodromes, CS-ADR-DSN Issue 7"
SOURCE_URL = (
    "https://www.easa.europa.eu/en/document-library/easy-access-rules/"
    "online-publications/easy-access-rules-aerodromes-regulation-eu"
)

PAVEMENT_EASA_REF = "CS ADR-DSN.B.090"
SHOULDER_EASA_REF = "CS ADR-DSN.B.125/B.135"
DECLARED_DISTANCE_EASA_REF = "CS ADR-DSN.B.035"
CLEARWAY_EASA_REF = "CS ADR-DSN.B.195"
STOPWAY_EASA_REF = "CS ADR-DSN.B.200"

STRIP_WIDTH_PARAMS = {
    1: {
        "graded_widths": {
            "NI": 60.0,
            "NPA": 80.0,
            "PA_I": 80.0,
            "PA_II_III": 80.0,
        },
        "overall_widths": {
            "NI": 60.0,
            "NPA": 140.0,
            "PA_I": 140.0,
            "PA_II_III": 140.0,
        },
        "ref_graded": {
            "NI": "CS ADR-DSN.B.175(b)(3) Code 1 non-instrument",
            "INSTR": "CS ADR-DSN.B.175(a)(2) Code 1 instrument",
        },
        "ref_overall": {
            "NI": "CS ADR-DSN.B.160(c)(3) Code 1 non-instrument",
            "NPA": "CS ADR-DSN.B.160(b)(2) Code 1 non-precision approach",
            "PA": "CS ADR-DSN.B.160(a)(2) Code 1 precision approach",
        },
    },
    2: {
        "graded_widths": {
            "NI": 80.0,
            "NPA": 80.0,
            "PA_I": 80.0,
            "PA_II_III": 80.0,
        },
        "overall_widths": {
            "NI": 80.0,
            "NPA": 140.0,
            "PA_I": 140.0,
            "PA_II_III": 140.0,
        },
        "ref_graded": {
            "NI": "CS ADR-DSN.B.175(b)(2) Code 2 non-instrument",
            "INSTR": "CS ADR-DSN.B.175(a)(2) Code 2 instrument",
        },
        "ref_overall": {
            "NI": "CS ADR-DSN.B.160(c)(2) Code 2 non-instrument",
            "NPA": "CS ADR-DSN.B.160(b)(2) Code 2 non-precision approach",
            "PA": "CS ADR-DSN.B.160(a)(2) Code 2 precision approach",
        },
    },
    3: {
        "graded_widths": {
            "NI": 150.0,
            "NPA": 150.0,
            "PA_I": 150.0,
            "PA_II_III": 150.0,
        },
        "overall_widths": {
            "NI": 150.0,
            "NPA": 280.0,
            "PA_I": 280.0,
            "PA_II_III": 280.0,
        },
        "ref_graded": {
            "NI": "CS ADR-DSN.B.175(b)(1) Code 3 non-instrument",
            "INSTR": "CS ADR-DSN.B.175(a)(1) Code 3 instrument",
        },
        "ref_overall": {
            "NI": "CS ADR-DSN.B.160(c)(1) Code 3 non-instrument",
            "NPA": "CS ADR-DSN.B.160(b)(1) Code 3 non-precision approach",
            "PA": "CS ADR-DSN.B.160(a)(1) Code 3 precision approach",
        },
    },
    4: {
        "graded_widths": {
            "NI": 150.0,
            "NPA": 150.0,
            "PA_I": 150.0,
            "PA_II_III": 150.0,
        },
        "overall_widths": {
            "NI": 150.0,
            "NPA": 280.0,
            "PA_I": 280.0,
            "PA_II_III": 280.0,
        },
        "ref_graded": {
            "NI": "CS ADR-DSN.B.175(b)(1) Code 4 non-instrument",
            "INSTR": "CS ADR-DSN.B.175(a)(1) Code 4 instrument",
        },
        "ref_overall": {
            "NI": "CS ADR-DSN.B.160(c)(1) Code 4 non-instrument",
            "NPA": "CS ADR-DSN.B.160(b)(1) Code 4 non-precision approach",
            "PA": "CS ADR-DSN.B.160(a)(1) Code 4 precision approach",
        },
    },
}

STRIP_EXTENSION_PARAMS = {
    "1_NI": {"length": 30.0, "ref": "CS ADR-DSN.B.155(a)(3)"},
    "DEFAULT": {"length": 60.0, "ref": "CS ADR-DSN.B.155(a)(1)-(2)"},
}

RESA_PARAMS = {
    "width_ref": "CS ADR-DSN.C.215(c) (Width of RESA)",
    "length_rules": {
        "1_2": {
            "length": 120.0,
            "ref": "CS ADR-DSN.C.215(a)(2) (Recommended length for code 1/2 instrument)",
        },
        "3_4": {
            "length": 240.0,
            "ref": "CS ADR-DSN.C.215(a)(1) (Recommended length for code 3/4)",
        },
    },
    "minimum_length": 90.0,
    "minimum_length_ref": "CS ADR-DSN.C.215(a) (Minimum 90 m)",
    "applicability_refs": {
        "required_3_4": "CS ADR-DSN.C.210(b)(1) (RESA required for code 3/4)",
        "required_1_2_instr": "CS ADR-DSN.C.210(b)(2) (RESA required for code 1/2 instrument)",
        "not_required": "CS ADR-DSN.C.210(b) (Not required for code 1/2 non-instrument)",
    },
}

DECLARED_DISTANCE_PARAMS = {
    "distance_keys": ("tora_m", "toda_m", "asda_m", "lda_m"),
    "rounding": "nearest_metre",
    "ref": DECLARED_DISTANCE_EASA_REF,
}

CLEARWAY_PARAMS = {
    "width_m": 150.0,
    "max_length_factor_tora": 0.5,
    "default_length_m": 0.0,
    "origin": "end_of_takeoff_run_available",
    "ref": CLEARWAY_EASA_REF,
}

STOPWAY_PARAMS = {
    "width": "same_as_runway",
    "ref": STOPWAY_EASA_REF,
}


PHYSICAL_TRACEABILITY = {
    "source_publication": SOURCE_PUBLICATION,
    "source_url": SOURCE_URL,
    "items": {
        "strip_length": {
            "source": "CS ADR-DSN.B.155",
            "status": "operational_verified",
            "implementation": "STRIP_EXTENSION_PARAMS",
            "notes": "Stores runway-strip extension before threshold and beyond runway/stopway end.",
        },
        "strip_overall_width": {
            "source": "CS ADR-DSN.B.160",
            "status": "operational_verified",
            "implementation": "STRIP_WIDTH_PARAMS[*].overall_widths",
            "notes": "Stored as total strip width; EASA source gives lateral distance on each side.",
        },
        "strip_graded_width": {
            "source": "CS ADR-DSN.B.175",
            "status": "operational_verified",
            "implementation": "STRIP_WIDTH_PARAMS[*].graded_widths",
            "notes": "Stored as total graded width; EASA source gives lateral distance on each side.",
        },
        "resa_applicability": {
            "source": "CS ADR-DSN.C.210",
            "status": "operational_verified",
            "implementation": "RESA_PARAMS.applicability_refs",
            "notes": "Determines whether RESA is required by code number and runway type.",
        },
        "resa_dimensions": {
            "source": "CS ADR-DSN.C.215",
            "status": "operational_verified",
            "implementation": "RESA_PARAMS.length_rules and width_ref",
            "notes": "Stores recommended RESA lengths and width basis.",
        },
        "declared_distances": {
            "source": DECLARED_DISTANCE_EASA_REF,
            "status": "operational_verified",
            "implementation": "DECLARED_DISTANCE_PARAMS",
            "notes": "TORA, TODA, ASDA, and LDA are calculated for each runway direction.",
        },
        "clearway": {
            "source": CLEARWAY_EASA_REF,
            "status": "operational_verified",
            "implementation": "CLEARWAY_PARAMS and get_clearway_params",
            "notes": "Clearways are optional; width is 150 m total and length is capped at half TORA.",
        },
        "stopway": {
            "source": STOPWAY_EASA_REF,
            "status": "operational_verified",
            "implementation": "STOPWAY_PARAMS and get_stopway_params",
            "notes": "Stopway width follows the associated runway width; entered length contributes to ASDA.",
        },
    },
}


def get_physical_refs() -> dict:
    return {"pavement": PAVEMENT_EASA_REF, "shoulder": SHOULDER_EASA_REF}


def get_physical_traceability() -> dict:
    """Return source traceability metadata for EASA physical rules."""
    return PHYSICAL_TRACEABILITY.copy()


def _overall_width_ref_key(type_abbr: str) -> str:
    if type_abbr == "NI":
        return "NI"
    if type_abbr == "NPA":
        return "NPA"
    return "PA"


def get_strip_params(arc_num: int, type_abbr: str, runway_width: Optional[float]) -> dict:
    results = {
        "overall_width": None,
        "graded_width": None,
        "extension_length": None,
        "overall_width_ref": "N/A",
        "graded_width_ref": "N/A",
        "extension_length_ref": "N/A",
        "easa_overall_width_ref": "N/A",
        "easa_graded_width_ref": "N/A",
        "easa_extension_length_ref": "N/A",
    }

    if not isinstance(arc_num, int) or arc_num not in [1, 2, 3, 4]:
        return results

    type_abbr = (type_abbr or "").upper()
    is_ni = type_abbr == "NI"

    width_rules = STRIP_WIDTH_PARAMS.get(arc_num)
    if not width_rules:
        return results

    graded_dict = width_rules["graded_widths"]
    if is_ni:
        results["graded_width"] = graded_dict.get("NI")
        results["easa_graded_width_ref"] = width_rules["ref_graded"].get("NI")
    else:
        results["graded_width"] = graded_dict.get(type_abbr, graded_dict.get("NPA"))
        results["easa_graded_width_ref"] = width_rules["ref_graded"].get("INSTR")
    results["graded_width_ref"] = results["easa_graded_width_ref"]

    overall_dict = width_rules["overall_widths"]
    if is_ni:
        results["overall_width"] = overall_dict.get("NI")
        results["easa_overall_width_ref"] = width_rules["ref_overall"].get("NI")
    else:
        results["overall_width"] = overall_dict.get(type_abbr, overall_dict.get("NPA"))
        results["easa_overall_width_ref"] = width_rules["ref_overall"].get(_overall_width_ref_key(type_abbr))
    results["overall_width_ref"] = results["easa_overall_width_ref"]

    if arc_num == 1 and is_ni:
        ext_key = "1_NI"
    else:
        ext_key = "DEFAULT"
    ext_params = STRIP_EXTENSION_PARAMS.get(ext_key)
    if ext_params:
        results["extension_length"] = ext_params.get("length")
        results["easa_extension_length_ref"] = ext_params.get("ref")
        results["extension_length_ref"] = results["easa_extension_length_ref"]

    return results


def get_resa_params(arc_num: int, type1_abbr: str, type2_abbr: str) -> dict:
    results = {
        "required": False,
        "length": None,
        "applicability_ref": "N/A",
        "length_ref": "N/A",
        "width_ref": RESA_PARAMS.get("width_ref", "N/A"),
        "easa_applicability_ref": "N/A",
        "easa_length_ref": "N/A",
        "easa_width_ref": RESA_PARAMS.get("width_ref", "N/A"),
    }

    if not isinstance(arc_num, int) or arc_num not in [1, 2, 3, 4]:
        return results

    type1_abbr = (type1_abbr or "").upper()
    type2_abbr = (type2_abbr or "").upper()
    is_instr_1 = type1_abbr in ["NPA", "PA_I", "PA_II_III"]
    is_instr_2 = type2_abbr in ["NPA", "PA_I", "PA_II_III"]

    applicability_refs = RESA_PARAMS.get("applicability_refs", {})
    length_rules = RESA_PARAMS.get("length_rules", {})

    if arc_num in [3, 4]:
        results["required"] = True
        results["easa_applicability_ref"] = applicability_refs.get("required_3_4", "N/A")
    elif arc_num in [1, 2] and (is_instr_1 or is_instr_2):
        results["required"] = True
        results["easa_applicability_ref"] = applicability_refs.get("required_1_2_instr", "N/A")
    else:
        results["required"] = False
        results["easa_applicability_ref"] = applicability_refs.get("not_required", "N/A")
    results["applicability_ref"] = results["easa_applicability_ref"]

    if results["required"]:
        len_key = "1_2" if arc_num in [1, 2] else "3_4"
        len_params = length_rules.get(len_key)
        if len_params:
            results["length"] = len_params.get("length")
            results["easa_length_ref"] = len_params.get("ref")
        else:
            # fallback to minimum length if no rule found
            results["length"] = RESA_PARAMS.get("minimum_length")
            results["easa_length_ref"] = RESA_PARAMS.get("minimum_length_ref", "N/A")
        results["length_ref"] = results["easa_length_ref"]
    results["width_ref"] = results["easa_width_ref"]
    return results


def get_declared_distance_params() -> dict:
    return dict(DECLARED_DISTANCE_PARAMS)


def get_clearway_params(
    runway_width: Optional[float] = None,
    strip_extension: Optional[float] = None,
    strip_overall_width: Optional[float] = None,
    physical_length: Optional[float] = None,
    clearway_primary_input: Optional[float] = None,
    clearway_reciprocal_input: Optional[float] = None,
    stopway_primary: Optional[float] = None,
    stopway_reciprocal: Optional[float] = None,
    is_instrument_runway: bool = False,
) -> Dict[str, Dict[str, Any]]:
    del runway_width, strip_extension, strip_overall_width, stopway_primary, stopway_reciprocal, is_instrument_runway

    max_length = _positive_or_none(physical_length)
    if max_length is not None:
        max_length *= CLEARWAY_PARAMS["max_length_factor_tora"]

    return {
        "primary": _clearway_end_params(clearway_primary_input, max_length),
        "reciprocal": _clearway_end_params(clearway_reciprocal_input, max_length),
    }


def get_stopway_params(runway_width: Optional[float] = None, stopway_length: Optional[float] = None) -> Dict[str, Any]:
    width = _non_negative_float(runway_width, 0.0)
    length = _non_negative_float(stopway_length, 0.0)
    return {
        "length_m": round(length, 3),
        "width_m": round(width, 3),
        "ref": STOPWAY_EASA_REF,
        "ref_easa": STOPWAY_EASA_REF,
    }


def _clearway_end_params(input_length: Optional[float], max_length: Optional[float]) -> Dict[str, Any]:
    input_length_m = _non_negative_float(input_length, 0.0)
    effective_length = input_length_m
    source = "input" if input_length_m > 1e-6 else "none"
    capped = False

    if max_length is not None and effective_length > max_length:
        effective_length = max_length
        capped = True
        source = f"{source}; capped"

    return {
        "length_m": round(effective_length, 3),
        "width_m": round(CLEARWAY_PARAMS["width_m"], 3),
        "input_length_m": round(input_length_m, 3),
        "default_length_m": CLEARWAY_PARAMS["default_length_m"],
        "source": source,
        "capped": capped,
        "max_length_m": round(max_length, 3) if max_length is not None else None,
        "ref": CLEARWAY_EASA_REF,
        "ref_easa": CLEARWAY_EASA_REF,
        "ref_mos": CLEARWAY_EASA_REF,
    }


def _non_negative_float(value: Optional[float], default: float = 0.0) -> float:
    try:
        parsed = float(value)
        return parsed if parsed >= 0 else default
    except (TypeError, ValueError):
        return default


def _positive_or_none(value: Optional[float]) -> Optional[float]:
    parsed = _non_negative_float(value, 0.0)
    return parsed if parsed > 0 else None


__all__ = [
    "PAVEMENT_EASA_REF",
    "SHOULDER_EASA_REF",
    "DECLARED_DISTANCE_EASA_REF",
    "CLEARWAY_EASA_REF",
    "STOPWAY_EASA_REF",
    "SOURCE_PUBLICATION",
    "SOURCE_URL",
    "PHYSICAL_TRACEABILITY",
    "STRIP_WIDTH_PARAMS",
    "STRIP_EXTENSION_PARAMS",
    "RESA_PARAMS",
    "DECLARED_DISTANCE_PARAMS",
    "CLEARWAY_PARAMS",
    "STOPWAY_PARAMS",
    "get_physical_refs",
    "get_physical_traceability",
    "get_strip_params",
    "get_resa_params",
    "get_declared_distance_params",
    "get_clearway_params",
    "get_stopway_params",
]
