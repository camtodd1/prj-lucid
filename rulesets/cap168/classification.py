"""UK CAA CAP 168 runway classification policy."""

from typing import Optional

CAP168_REFERENCE_CODE_REF = "CAP 168 3.13-3.18 Table 3.1"
SOURCE_PUBLICATION = "UK CAA CAP 168 Licensing of Aerodromes, Edition 13"
SOURCE_URL = "https://www.caa.co.uk/CAP168"

RUNWAY_TYPE_MAP = {
    "Non-Instrument (NI)": "NI",
    "Non-Precision Approach (NPA)": "NPA",
    "Precision Approach CAT I": "PA_I",
    "Precision Approach CAT II/III": "PA_II_III",
}

PRECISION_APPROACH_TYPES = {"PA_I", "PA_II_III"}

CODE_NUMBER_PARAMS = (
    {"max_arfl_m": 800.0, "code_number": 1, "ref": CAP168_REFERENCE_CODE_REF},
    {"max_arfl_m": 1200.0, "code_number": 2, "ref": CAP168_REFERENCE_CODE_REF},
    {"max_arfl_m": 1800.0, "code_number": 3, "ref": CAP168_REFERENCE_CODE_REF},
    {"max_arfl_m": None, "code_number": 4, "ref": CAP168_REFERENCE_CODE_REF},
)

CODE_LETTER_PARAMS = (
    {"max_wingspan_m": 15.0, "code_letter": "A", "ref": CAP168_REFERENCE_CODE_REF},
    {"max_wingspan_m": 24.0, "code_letter": "B", "ref": CAP168_REFERENCE_CODE_REF},
    {"max_wingspan_m": 36.0, "code_letter": "C", "ref": CAP168_REFERENCE_CODE_REF},
    {"max_wingspan_m": 52.0, "code_letter": "D", "ref": CAP168_REFERENCE_CODE_REF},
    {"max_wingspan_m": 65.0, "code_letter": "E", "ref": CAP168_REFERENCE_CODE_REF},
    {"max_wingspan_m": 80.0, "code_letter": "F", "ref": CAP168_REFERENCE_CODE_REF},
)


def get_runway_type_abbr(runway_type_str: Optional[str]) -> str:
    if runway_type_str in RUNWAY_TYPE_MAP:
        return RUNWAY_TYPE_MAP[runway_type_str]
    value = (runway_type_str or "").strip().upper()
    if value in {"NI", "NPA", "PA_I", "PA_II_III"}:
        return value
    return "NI"


def code_number(aeroplane_reference_field_length_m: Optional[float]):
    try:
        arfl_m = float(aeroplane_reference_field_length_m)
    except (TypeError, ValueError):
        return None
    if arfl_m < 0:
        return None
    for params in CODE_NUMBER_PARAMS:
        max_arfl_m = params["max_arfl_m"]
        if max_arfl_m is None or arfl_m < max_arfl_m:
            return params.copy()
    return None


def code_letter(wingspan_m: Optional[float]):
    try:
        wingspan = float(wingspan_m)
    except (TypeError, ValueError):
        return None
    if wingspan < 0:
        return None
    for params in CODE_LETTER_PARAMS:
        if wingspan < params["max_wingspan_m"]:
            return params.copy()
    return None


__all__ = [
    "CAP168_REFERENCE_CODE_REF",
    "SOURCE_PUBLICATION",
    "SOURCE_URL",
    "RUNWAY_TYPE_MAP",
    "PRECISION_APPROACH_TYPES",
    "CODE_NUMBER_PARAMS",
    "CODE_LETTER_PARAMS",
    "get_runway_type_abbr",
    "code_number",
    "code_letter",
]
