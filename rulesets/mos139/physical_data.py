"""MOS139 physical runway dimension policy."""

from typing import Optional

PAVEMENT_MOS_REF = "MOS 4.01"
SHOULDER_MOS_REF = "MOS 6.11"

STRIP_WIDTH_PARAMS = {
    1: {
        "graded": 60.0,
        "overall_ni_npa": 140.0,
        "overall_pa": 280.0,
        "ref_graded": "MOS T6.17(1) Code 1",
        "ref_overall": "MOS T6.17(4) Code 1/2",
    },
    2: {
        "graded": 80.0,
        "overall_ni_npa": 140.0,
        "overall_pa": 280.0,
        "ref_graded": "MOS T6.17(1) Code 2",
        "ref_overall": "MOS T6.17(4) Code 1/2",
    },
    3: {
        "graded_lt_45": 90.0,
        "graded_ge_45": 150.0,
        "overall": 280.0,
        "ref_graded": "MOS T6.17(1) Code 3/4",
        "ref_overall": "MOS T6.17(4) Code 3/4",
    },
    4: {
        "graded_lt_45": 90.0,
        "graded_ge_45": 150.0,
        "overall": 280.0,
        "ref_graded": "MOS T6.17(1) Code 3/4",
        "ref_overall": "MOS T6.17(4) Code 3/4",
    },
}

STRIP_EXTENSION_PARAMS = {
    "NI_1_2": {"length": 30.0, "ref": "MOS 6.16(a) NI Code 1/2"},
    "OTHER": {"length": 60.0, "ref": "MOS 6.16(b)"},
}

RESA_PARAMS = {
    "width_ref": "MOS 6.26(6) (Width)",
    "length_rules": {
        "1_2": {"length": 120.0, "ref": "MOS 6.26(5) (Code 1/2 Preferred length)"},
        "3_4": {"length": 240.0, "ref": "MOS 6.26(5) (Code 3/4 Preferred length)"},
    },
    "applicability_refs": {
        "required_3_4": "MOS 6.26(1) (Code 3/4)",
        "required_1_2_instr": "6.26(1) (Code 1/2 Instr)",
        "not_required": "6.26(2) (Not Required)",
    },
}


def get_physical_refs():
    return {"pavement": PAVEMENT_MOS_REF, "shoulder": SHOULDER_MOS_REF}


def get_strip_params(arc_num: int, type_abbr: str, runway_width: Optional[float]):
    results = {
        "overall_width": None,
        "graded_width": None,
        "extension_length": None,
        "overall_width_ref": "N/A",
        "graded_width_ref": "N/A",
        "extension_length_ref": "N/A",
        "mos_overall_width_ref": "N/A",
        "mos_graded_width_ref": "N/A",
        "mos_extension_length_ref": "N/A",
    }
    if not isinstance(arc_num, int) or arc_num not in [1, 2, 3, 4]:
        return results

    width_rules = STRIP_WIDTH_PARAMS.get(arc_num, {})
    results["mos_graded_width_ref"] = width_rules.get("ref_graded", "N/A")
    results["mos_overall_width_ref"] = width_rules.get("ref_overall", "N/A")
    results["graded_width_ref"] = results["mos_graded_width_ref"]
    results["overall_width_ref"] = results["mos_overall_width_ref"]

    if "graded" in width_rules:
        results["graded_width"] = width_rules["graded"]
    elif "graded_lt_45" in width_rules:
        if runway_width is not None and runway_width < 45.0:
            results["graded_width"] = width_rules["graded_lt_45"]
            results["mos_graded_width_ref"] += " (<45m)"
            results["graded_width_ref"] = results["mos_graded_width_ref"]
        else:
            results["graded_width"] = width_rules["graded_ge_45"]
            results["mos_graded_width_ref"] += " (>=45m)"
            results["graded_width_ref"] = results["mos_graded_width_ref"]

    is_ni_or_npa = type_abbr in ["NI", "NPA"]
    if arc_num in [1, 2] and is_ni_or_npa:
        results["overall_width"] = width_rules.get("overall_ni_npa")
        results["mos_overall_width_ref"] += " (Code 1/2 NI/NPA)"
        results["overall_width_ref"] = results["mos_overall_width_ref"]
    elif arc_num in [1, 2] and type_abbr.startswith("PA"):
        results["overall_width"] = width_rules.get("overall_pa")
        results["mos_overall_width_ref"] += " (Code 1/2 PA)"
        results["overall_width_ref"] = results["mos_overall_width_ref"]
    elif arc_num in [3, 4]:
        results["overall_width"] = width_rules.get("overall")
        results["mos_overall_width_ref"] += " (Code 3/4)"
        results["overall_width_ref"] = results["mos_overall_width_ref"]

    is_ni_code_1_or_2 = type_abbr == "NI" and arc_num in [1, 2]
    ext_key = "NI_1_2" if is_ni_code_1_or_2 else "OTHER"
    ext_params = STRIP_EXTENSION_PARAMS.get(ext_key)
    if ext_params:
        results["extension_length"] = ext_params.get("length")
        results["mos_extension_length_ref"] = ext_params.get("ref", "N/A")
        results["extension_length_ref"] = results["mos_extension_length_ref"]

    return results


def get_resa_params(arc_num: int, type1_abbr: str, type2_abbr: str):
    results = {
        "required": False,
        "length": None,
        "applicability_ref": "N/A",
        "length_ref": "N/A",
        "width_ref": RESA_PARAMS.get("width_ref", "N/A"),
        "mos_applicability_ref": "N/A",
        "mos_length_ref": "N/A",
        "mos_width_ref": RESA_PARAMS.get("width_ref", "N/A"),
    }

    is_instrument = type1_abbr in ["NPA", "PA_I", "PA_II_III"] or type2_abbr in [
        "NPA",
        "PA_I",
        "PA_II_III",
    ]

    applicability_refs = RESA_PARAMS.get("applicability_refs", {})
    length_rules = RESA_PARAMS.get("length_rules", {})

    if arc_num in [3, 4]:
        results["required"] = True
        results["mos_applicability_ref"] = applicability_refs.get("required_3_4", "N/A")
    elif arc_num in [1, 2] and is_instrument:
        results["required"] = True
        results["mos_applicability_ref"] = applicability_refs.get("required_1_2_instr", "N/A")
    else:
        results["required"] = False
        results["mos_applicability_ref"] = applicability_refs.get("not_required", "N/A")
    results["applicability_ref"] = results["mos_applicability_ref"]

    if results["required"]:
        len_key = "1_2" if arc_num in [1, 2] else "3_4"
        len_params = length_rules.get(len_key)
        if len_params:
            results["length"] = len_params.get("length")
            results["mos_length_ref"] = len_params.get("ref", "N/A")
            results["length_ref"] = results["mos_length_ref"]
    results["width_ref"] = results["mos_width_ref"]

    return results


__all__ = [
    "PAVEMENT_MOS_REF",
    "SHOULDER_MOS_REF",
    "STRIP_WIDTH_PARAMS",
    "STRIP_EXTENSION_PARAMS",
    "RESA_PARAMS",
    "get_physical_refs",
    "get_strip_params",
    "get_resa_params",
]
