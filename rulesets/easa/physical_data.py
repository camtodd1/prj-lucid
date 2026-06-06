"""EASA CS-ADR‑DSN Chapter B physical runway dimension policy.

This module defines constants and helper functions that encapsulate the
physical dimensions for runways, runway strips, shoulders and runway end
safety areas (RESA) as defined in European Union Aviation Safety Agency
(EASA) CS‑ADR‑DSN Issue 6, Chapter B (Runways) and Chapter C (RESA).

The structure and function signatures mirror those in the MOS‑based
``physical_data.py`` so that existing code can seamlessly switch
between Australian MOS139 rules and EASA rules. Where EASA guidance
differs from MOS, the constants and logic in this file reflect the
EASA requirements. Citations below reference the relevant CS‑ADR‑DSN
paragraphs.

Key highlights from the specifications include:

* **Runway strip widths:**  CS ADR‑DSN.B.160 specifies that a runway
  strip including a precision or non‑precision approach runway must
  extend laterally from the centre line of the runway by at least
  140 m for code numbers 3 and 4 and 70 m for code numbers 1 and 2.
  For non‑instrument runways the lateral distances are 75 m (codes 3/4),
  40 m (code 2) and 30 m (code 1).  These
  lateral distances are doubled in the tables below to yield the
  overall strip width.

* **Graded portion of runway strip:**  CS ADR‑DSN.B.175 requires a graded
  area on each side of the runway to at least 75 m for code numbers 3/4
  and 40 m for code numbers 1/2 on instrument runways, and 75 m
  (codes 3/4), 40 m (code 2) and 30 m (code 1) on non‑instrument
  runways.  These distances are doubled in
  the ``graded_width`` entries.

* **Runway strip extensions:**  CS ADR‑DSN.B.155 states that a runway
  strip should extend before the threshold and beyond the end of the
  runway for at least 60 m for code numbers 2, 3 and 4, and also for
  code 1 instrument runways, but only 30 m for code 1 non‑instrument
  runways.

* **Runway shoulders:**  CS ADR‑DSN.B.125 and CS ADR‑DSN.B.135 describe
  the provision and width of runway shoulders.  Shoulders are required
  for runways with code letters D, E or F and the overall width of the
  runway including shoulders should not be less than 60 m for code
  letters D or E and 75 m for code letter F with four or more
  engines.  These references are stored in
  ``SHOULDER_EASA_REF``.

* **Runway end safety areas (RESA):**  Chapter C of the CS‑ADR‑DSN sets
  out the requirements for RESA.  A RESA must be provided at each
  runway end for code numbers 3/4 and for code numbers 1/2 when the
  runway is an instrument runway.  CS ADR‑DSN.C.215
  further specifies that the RESA should extend from the end of the
  runway strip for at least 90 m and, where practicable, to
  240 m for code numbers 3/4 or 120 m for code numbers 1/2 instrument
  runways, with a width at least twice the runway width.

The tables and functions below translate these specifications into
Python constants and helper routines.
"""

from typing import Optional

# References for pavement and shoulder requirements.  These strings
# identify the CS‑ADR‑DSN paragraphs containing the relevant text.
PAVEMENT_EASA_REF = "CS ADR‑DSN.B.090"  # Surface of runways
SHOULDER_EASA_REF = "CS ADR‑DSN.B.125/B.135"  # Runway shoulders

# Width and grading parameters for runway strips by code number.  Each
# entry contains separate values for instrument (includes non‑precision
# and precision approach) and non‑instrument runways.  The numeric
# values are overall widths and graded widths in metres.
STRIP_WIDTH_PARAMS = {
    1: {
        # Graded width (total) for code 1 instrument and non‑instrument runways
        "graded_widths": {
            "NI": 60.0,  # 2 × 30 m
            "NPA": 80.0,  # 2 × 40 m
            "PA_I": 80.0,  # 2 × 40 m
            "PA_II_III": 80.0,  # 2 × 40 m
        },
        # Overall strip width (total) for code 1 instrument and non‑instrument runways
        "overall_widths": {
            "NI": 60.0,  # 2 × 30 m
            "NPA": 140.0,  # 2 × 70 m
            "PA_I": 140.0,  # 2 × 70 m
            "PA_II_III": 140.0,  # 2 × 70 m
        },
        # References for graded and overall widths
        "ref_graded": {
            "NI": "CS ADR‑DSN.B.175(b)(3) Code 1 non‑instrument",
            "INSTR": "CS ADR‑DSN.B.175(a)(2) Code 1 instrument",
        },
        "ref_overall": {
            "NI": "CS ADR‑DSN.B.160(c)(3) Code 1 non‑instrument",
            "INSTR": "CS ADR‑DSN.B.160(a)(2) Code 1 instrument",
        },
    },
    2: {
        "graded_widths": {
            "NI": 80.0,  # 2 × 40 m
            "NPA": 80.0,  # 2 × 40 m
            "PA_I": 80.0,  # 2 × 40 m
            "PA_II_III": 80.0,  # 2 × 40 m
        },
        "overall_widths": {
            "NI": 80.0,  # 2 × 40 m
            "NPA": 140.0,  # 2 × 70 m
            "PA_I": 140.0,  # 2 × 70 m
            "PA_II_III": 140.0,  # 2 × 70 m
        },
        "ref_graded": {
            "NI": "CS ADR‑DSN.B.175(b)(2) Code 2 non‑instrument",
            "INSTR": "CS ADR‑DSN.B.175(a)(2) Code 2 instrument",
        },
        "ref_overall": {
            "NI": "CS ADR‑DSN.B.160(c)(2) Code 2 non‑instrument",
            "INSTR": "CS ADR‑DSN.B.160(a)(2) Code 2 instrument",
        },
    },
    3: {
        "graded_widths": {
            "NI": 150.0,  # 2 × 75 m
            "NPA": 150.0,  # 2 × 75 m
            "PA_I": 150.0,  # 2 × 75 m
            "PA_II_III": 150.0,  # 2 × 75 m
        },
        "overall_widths": {
            "NI": 150.0,  # 2 × 75 m
            "NPA": 280.0,  # 2 × 140 m
            "PA_I": 280.0,  # 2 × 140 m
            "PA_II_III": 280.0,  # 2 × 140 m
        },
        "ref_graded": {
            "NI": "CS ADR‑DSN.B.175(b)(1) Code 3 non‑instrument",
            "INSTR": "CS ADR‑DSN.B.175(a)(1) Code 3 instrument",
        },
        "ref_overall": {
            "NI": "CS ADR‑DSN.B.160(c)(1) Code 3 non‑instrument",
            "INSTR": "CS ADR‑DSN.B.160(a)(1) Code 3 instrument",
        },
    },
    4: {
        "graded_widths": {
            "NI": 150.0,  # 2 × 75 m
            "NPA": 150.0,  # 2 × 75 m
            "PA_I": 150.0,  # 2 × 75 m
            "PA_II_III": 150.0,  # 2 × 75 m
        },
        "overall_widths": {
            "NI": 150.0,  # 2 × 75 m
            "NPA": 280.0,  # 2 × 140 m
            "PA_I": 280.0,  # 2 × 140 m
            "PA_II_III": 280.0,  # 2 × 140 m
        },
        "ref_graded": {
            "NI": "CS ADR‑DSN.B.175(b)(1) Code 4 non‑instrument",
            "INSTR": "CS ADR‑DSN.B.175(a)(1) Code 4 instrument",
        },
        "ref_overall": {
            "NI": "CS ADR‑DSN.B.160(c)(1) Code 4 non‑instrument",
            "INSTR": "CS ADR‑DSN.B.160(a)(1) Code 4 instrument",
        },
    },
}

# Extension lengths for runway strips based on code number and runway type.
# For code 1 non‑instrument runways the strip extension is 30 m; for all
# other cases the extension is 60 m.
STRIP_EXTENSION_PARAMS = {
    "1_NI": {"length": 30.0, "ref": "CS ADR‑DSN.B.155(a)(3)"},
    "DEFAULT": {"length": 60.0, "ref": "CS ADR‑DSN.B.155(a)(1)-(2)"},
}

# Runway end safety area (RESA) parameters.  The RESA is required for
# code numbers 3/4 and for code numbers 1/2 when the runway is an
# instrument runway.  The recommended lengths are
# 240 m for code numbers 3/4 and 120 m for code numbers 1/2 instrument
# runways, with a minimum of 90 m.  The width
# should be at least twice the width of the runway or, where practicable,
# equal to the graded portion of the runway strip.
RESA_PARAMS = {
    "width_ref": "CS ADR‑DSN.C.215(c) (Width of RESA)",
    "length_rules": {
        "1_2": {
            "length": 120.0,
            "ref": "CS ADR‑DSN.C.215(a)(2) (Recommended length for code 1/2 instrument)",
        },
        "3_4": {
            "length": 240.0,
            "ref": "CS ADR‑DSN.C.215(a)(1) (Recommended length for code 3/4)",
        },
    },
    "minimum_length": 90.0,
    "minimum_length_ref": "CS ADR‑DSN.C.215(a) (Minimum 90 m)",
    "applicability_refs": {
        "required_3_4": "CS ADR‑DSN.C.210(b)(1) (RESA required for code 3/4)",
        "required_1_2_instr": "CS ADR‑DSN.C.210(b)(2) (RESA required for code 1/2 instrument)",
        "not_required": "CS ADR‑DSN.C.210(b) (Not required for code 1/2 non‑instrument)",
    },
}


def get_physical_refs() -> dict:
    """Return reference strings for pavement and shoulder requirements.

    Returns:
        A dictionary with keys ``pavement`` and ``shoulder`` whose values
        are reference strings to the CS‑ADR‑DSN paragraphs covering
        pavement surface and shoulder provision.
    """
    return {"pavement": PAVEMENT_EASA_REF, "shoulder": SHOULDER_EASA_REF}


def get_strip_params(arc_num: int, type_abbr: str, runway_width: Optional[float]) -> dict:
    """Return strip width and extension parameters for a given runway code and type.

    Arguments:
        arc_num: The ICAO code number (1–4) of the runway.
        type_abbr: An abbreviation of the runway type.  ``NI`` denotes
            non‑instrument; ``NPA`` denotes non‑precision approach;
            ``PA_I`` denotes precision approach Category I; and
            ``PA_II_III`` denotes precision approach Categories II/III.
        runway_width: The physical runway width in metres (unused in the
            EASA rules but accepted for compatibility with the MOS function).

    Returns:
        A dictionary containing:
            ``overall_width`` (float): the overall runway strip width in metres;
            ``graded_width`` (float): the width of the graded portion of the
                runway strip in metres;
            ``extension_length`` (float): the strip extension length beyond
                the threshold in metres;
            ``easa_overall_width_ref`` (str): the CS‑ADR‑DSN reference for the
                overall width;
            ``easa_graded_width_ref`` (str): the CS‑ADR‑DSN reference for the
                graded width;
            ``easa_extension_length_ref`` (str): the CS‑ADR‑DSN reference for
                the strip extension.

        Unknown or invalid ``arc_num`` values will result in ``None`` values
        and ``N/A`` references.
    """
    # initialise default results
    results = {
        "overall_width": None,
        "graded_width": None,
        "extension_length": None,
        "easa_overall_width_ref": "N/A",
        "easa_graded_width_ref": "N/A",
        "easa_extension_length_ref": "N/A",
    }

    # Validate arc number
    if not isinstance(arc_num, int) or arc_num not in [1, 2, 3, 4]:
        return results

    type_abbr = (type_abbr or "").upper()
    # Determine if the runway is non‑instrument or instrument
    is_ni = type_abbr == "NI"
    is_instrument = not is_ni  # includes NPA, PA_I, PA_II_III

    width_rules = STRIP_WIDTH_PARAMS.get(arc_num)
    if not width_rules:
        return results

    # graded width
    graded_dict = width_rules["graded_widths"]
    if is_ni:
        results["graded_width"] = graded_dict.get("NI")
        results["easa_graded_width_ref"] = width_rules["ref_graded"].get("NI")
    else:
        # use instrument reference for all instrument types
        results["graded_width"] = graded_dict.get(type_abbr, graded_dict.get("NPA"))
        results["easa_graded_width_ref"] = width_rules["ref_graded"].get("INSTR")

    # overall width
    overall_dict = width_rules["overall_widths"]
    if is_ni:
        results["overall_width"] = overall_dict.get("NI")
        results["easa_overall_width_ref"] = width_rules["ref_overall"].get("NI")
    else:
        results["overall_width"] = overall_dict.get(type_abbr, overall_dict.get("NPA"))
        results["easa_overall_width_ref"] = width_rules["ref_overall"].get("INSTR")

    # extension length
    if arc_num == 1 and is_ni:
        ext_key = "1_NI"
    else:
        ext_key = "DEFAULT"
    ext_params = STRIP_EXTENSION_PARAMS.get(ext_key)
    if ext_params:
        results["extension_length"] = ext_params.get("length")
        results["easa_extension_length_ref"] = ext_params.get("ref")

    return results


def get_resa_params(arc_num: int, type1_abbr: str, type2_abbr: str) -> dict:
    """Return RESA requirement and dimensions for a runway end.

    Arguments:
        arc_num: The ICAO code number (1–4) of the runway.
        type1_abbr: The type of runway for the primary direction (e.g. "NI", "NPA", "PA_I", "PA_II_III").
        type2_abbr: The type of runway for the opposite direction.

    Returns:
        A dictionary with keys:
            ``required`` (bool): whether a RESA is required;
            ``length`` (float or None): recommended RESA length in metres if required;
            ``easa_applicability_ref`` (str): CS‑ADR‑DSN reference for the applicability;
            ``easa_length_ref`` (str): CS‑ADR‑DSN reference for the length;
            ``easa_width_ref`` (str): CS‑ADR‑DSN reference for the width.

        RESA is required at both runway ends when the code number is 3 or 4, or
        when the code number is 1 or 2 and at least one runway direction is an
        instrument runway.
    """
    results = {
        "required": False,
        "length": None,
        "easa_applicability_ref": "N/A",
        "easa_length_ref": "N/A",
        "easa_width_ref": RESA_PARAMS.get("width_ref", "N/A"),
    }

    # Validate arc number
    if not isinstance(arc_num, int) or arc_num not in [1, 2, 3, 4]:
        return results

    type1_abbr = (type1_abbr or "").upper()
    type2_abbr = (type2_abbr or "").upper()
    is_instr_1 = type1_abbr in ["NPA", "PA_I", "PA_II_III"]
    is_instr_2 = type2_abbr in ["NPA", "PA_I", "PA_II_III"]

    applicability_refs = RESA_PARAMS.get("applicability_refs", {})
    length_rules = RESA_PARAMS.get("length_rules", {})

    # Determine if RESA is required
    if arc_num in [3, 4]:
        results["required"] = True
        results["easa_applicability_ref"] = applicability_refs.get("required_3_4", "N/A")
    elif arc_num in [1, 2] and (is_instr_1 or is_instr_2):
        results["required"] = True
        results["easa_applicability_ref"] = applicability_refs.get("required_1_2_instr", "N/A")
    else:
        results["required"] = False
        results["easa_applicability_ref"] = applicability_refs.get("not_required", "N/A")

    # If required, assign the recommended length
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
    return results


__all__ = [
    "PAVEMENT_EASA_REF",
    "SHOULDER_EASA_REF",
    "STRIP_WIDTH_PARAMS",
    "STRIP_EXTENSION_PARAMS",
    "RESA_PARAMS",
    "get_physical_refs",
    "get_strip_params",
    "get_resa_params",
]