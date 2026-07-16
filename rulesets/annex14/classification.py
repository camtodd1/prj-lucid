"""Classification helpers for the ICAO Annex 14 Volume I scaffold."""

from typing import Optional

RUNWAY_TYPE_MAP = {
    "Non-Instrument (NI)": "NI",
    "Non-Precision Approach (NPA)": "NPA",
    "Precision Approach CAT I": "PA_I",
    "Precision Approach CAT II/III": "PA_II_III",
    None: "NI",
}

PRECISION_APPROACH_TYPES = {"PA_I", "PA_II_III"}

DESIGN_GROUP_STATUS = "implemented_from_table_1_2"
ADG_APPLICABLE_FROM = "2030-11-21"

REFERENCE_CODE_NUMBER_TABLE = (
    {"code_number": 1, "min_field_length_m": None, "max_field_length_m": 800.0},
    {"code_number": 2, "min_field_length_m": 800.0, "max_field_length_m": 1200.0},
    {"code_number": 3, "min_field_length_m": 1200.0, "max_field_length_m": 1800.0},
    {"code_number": 4, "min_field_length_m": 1800.0, "max_field_length_m": None},
)

REFERENCE_CODE_LETTER_TABLE = (
    {"code_letter": "A", "min_wingspan_m": None, "max_wingspan_m": 15.0},
    {"code_letter": "B", "min_wingspan_m": 15.0, "max_wingspan_m": 24.0},
    {"code_letter": "C", "min_wingspan_m": 24.0, "max_wingspan_m": 36.0},
    {"code_letter": "D", "min_wingspan_m": 36.0, "max_wingspan_m": 52.0},
    {"code_letter": "E", "min_wingspan_m": 52.0, "max_wingspan_m": 65.0},
    {"code_letter": "F", "min_wingspan_m": 65.0, "max_wingspan_m": 80.0},
)

ADG_TABLE = (
    {"design_group": "I", "min_vat_kmh": None, "max_vat_kmh": 169.0, "min_wingspan_m": None, "max_wingspan_m": 24.0},
    {"design_group": "IIA", "min_vat_kmh": None, "max_vat_kmh": 169.0, "min_wingspan_m": 24.0, "max_wingspan_m": 36.0},
    {"design_group": "IIB", "min_vat_kmh": 169.0, "max_vat_kmh": 224.0, "min_wingspan_m": None, "max_wingspan_m": 36.0},
    {"design_group": "IIC", "min_vat_kmh": 224.0, "max_vat_kmh": 307.0, "min_wingspan_m": None, "max_wingspan_m": 36.0},
    {"design_group": "III", "min_vat_kmh": None, "max_vat_kmh": 307.0, "min_wingspan_m": 36.0, "max_wingspan_m": 52.0},
    {"design_group": "IV", "min_vat_kmh": None, "max_vat_kmh": 307.0, "min_wingspan_m": 52.0, "max_wingspan_m": 65.0},
    {"design_group": "V", "min_vat_kmh": None, "max_vat_kmh": 307.0, "min_wingspan_m": 65.0, "max_wingspan_m": 80.0},
)

ADG_SPEED_AXIS = (
    {"design_group": "I", "min_vat_kmh": None, "max_vat_kmh": 169.0},
    {"design_group": "IIB", "min_vat_kmh": 169.0, "max_vat_kmh": 224.0},
    {"design_group": "IIC", "min_vat_kmh": 224.0, "max_vat_kmh": 307.0},
)

ADG_WINGSPAN_AXIS = (
    {"design_group": "I", "min_wingspan_m": None, "max_wingspan_m": 24.0},
    {"design_group": "IIA", "min_wingspan_m": 24.0, "max_wingspan_m": 36.0},
    {"design_group": "III", "min_wingspan_m": 36.0, "max_wingspan_m": 52.0},
    {"design_group": "IV", "min_wingspan_m": 52.0, "max_wingspan_m": 65.0},
    {"design_group": "V", "min_wingspan_m": 65.0, "max_wingspan_m": 80.0},
)

ADG_ORDER = {"I": 1, "IIA": 2, "IIB": 3, "IIC": 4, "III": 5, "IV": 6, "V": 7}


def get_runway_type_abbr(runway_type: Optional[str]) -> str:
    """Return the internal runway type code used by ruleset policy tables."""
    if runway_type in {"NI", "NPA", "PA_I", "PA_II_III"}:
        return str(runway_type)
    return RUNWAY_TYPE_MAP.get(runway_type, "NI")


def _in_range(value: float, lower: Optional[float], upper: Optional[float]) -> bool:
    if lower is not None and value < lower:
        return False
    if upper is not None and value >= upper:
        return False
    return True


def classify_code_number(aeroplane_reference_field_length_m: Optional[float]):
    """Classify Annex 14 aerodrome reference code number from Table 1-1."""
    if aeroplane_reference_field_length_m is None:
        return None
    for row in REFERENCE_CODE_NUMBER_TABLE:
        if _in_range(
            aeroplane_reference_field_length_m,
            row["min_field_length_m"],
            row["max_field_length_m"],
        ):
            return {
                "code_number": row["code_number"],
                "source": "Annex 14 Vol I Table 1-1",
                "criteria": row,
            }
    return None


def classify_code_letter(wingspan_m: Optional[float]):
    """Classify Annex 14 aerodrome reference code letter from Table 1-1."""
    if wingspan_m is None:
        return None
    for row in REFERENCE_CODE_LETTER_TABLE:
        if _in_range(wingspan_m, row["min_wingspan_m"], row["max_wingspan_m"]):
            return {
                "code_letter": row["code_letter"],
                "source": "Annex 14 Vol I Table 1-1",
                "criteria": row,
            }
    return None


def _adg_candidate_for_speed(indicated_airspeed_at_threshold_kmh: float):
    for row in ADG_SPEED_AXIS:
        if _in_range(indicated_airspeed_at_threshold_kmh, row["min_vat_kmh"], row["max_vat_kmh"]):
            return row
    return None


def _adg_candidate_for_wingspan(wingspan_m: float):
    for row in ADG_WINGSPAN_AXIS:
        if _in_range(wingspan_m, row["min_wingspan_m"], row["max_wingspan_m"]):
            return row
    return None


def classify_design_group(
    wingspan_m: Optional[float] = None,
    indicated_airspeed_at_threshold_kmh: Optional[float] = None,
    indicated_airspeed_at_threshold_kt: Optional[float] = None,
    outer_main_gear_wheel_span_m: Optional[float] = None,
    tail_height_m: Optional[float] = None,
):
    """Classify ADG from Annex 14 Table 1-2.

    The table requires selecting the ADG corresponding to the highest values of
    indicated airspeed at threshold and wingspan. Values outside the captured
    table return None so callers can flag compatibility-study cases explicitly.
    """
    if indicated_airspeed_at_threshold_kmh is None and indicated_airspeed_at_threshold_kt is not None:
        indicated_airspeed_at_threshold_kmh = indicated_airspeed_at_threshold_kt * 1.852

    candidates = []
    if indicated_airspeed_at_threshold_kmh is not None:
        candidate = _adg_candidate_for_speed(indicated_airspeed_at_threshold_kmh)
        if candidate is None:
            return None
        candidates.append(candidate)

    if wingspan_m is not None:
        candidate = _adg_candidate_for_wingspan(wingspan_m)
        if candidate is None:
            return None
        candidates.append(candidate)

    if not candidates:
        return None

    selected = max(candidates, key=lambda row: ADG_ORDER[row["design_group"]])
    return {
        "design_group": selected["design_group"],
        "source": "Annex 14 Vol I Table 1-2",
        "applicable_from": ADG_APPLICABLE_FROM,
        "criteria": selected,
        "inputs": {
            "wingspan_m": wingspan_m,
            "indicated_airspeed_at_threshold_kmh": indicated_airspeed_at_threshold_kmh,
            "outer_main_gear_wheel_span_m": outer_main_gear_wheel_span_m,
            "tail_height_m": tail_height_m,
        },
    }


__all__ = [
    "RUNWAY_TYPE_MAP",
    "PRECISION_APPROACH_TYPES",
    "DESIGN_GROUP_STATUS",
    "ADG_APPLICABLE_FROM",
    "REFERENCE_CODE_NUMBER_TABLE",
    "REFERENCE_CODE_LETTER_TABLE",
    "ADG_TABLE",
    "ADG_SPEED_AXIS",
    "ADG_WINGSPAN_AXIS",
    "get_runway_type_abbr",
    "classify_code_number",
    "classify_code_letter",
    "classify_design_group",
]
