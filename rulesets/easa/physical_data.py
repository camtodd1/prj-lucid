"""EASA CS-ADR-DSN physical runway dimension policy."""

from typing import Optional

SOURCE_PUBLICATION = "EASA Easy Access Rules for Aerodromes, CS-ADR-DSN Issue 7"
SOURCE_URL = (
    "https://www.easa.europa.eu/en/document-library/easy-access-rules/"
    "online-publications/easy-access-rules-aerodromes-regulation-eu"
)

PAVEMENT_EASA_REF = "CS ADR-DSN.B.090"
SHOULDER_EASA_REF = "CS ADR-DSN.B.125/B.135"

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


__all__ = [
    "PAVEMENT_EASA_REF",
    "SHOULDER_EASA_REF",
    "SOURCE_PUBLICATION",
    "SOURCE_URL",
    "PHYSICAL_TRACEABILITY",
    "STRIP_WIDTH_PARAMS",
    "STRIP_EXTENSION_PARAMS",
    "RESA_PARAMS",
    "get_physical_refs",
    "get_physical_traceability",
    "get_strip_params",
    "get_resa_params",
]
