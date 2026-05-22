"""MOS-derived Airfield Ground Lighting dimensions and rules."""

from typing import Dict

MOS_PART_139_2019 = "Part 139 MOS 2019"
MOS_REF_RUNWAY_EDGE = "Part 139 MOS 2019 s 9.51"
MOS_REF_THRESHOLD_LOCATION = "Part 139 MOS 2019 s 9.54"
MOS_REF_THRESHOLD_NON_PRECISION = "Part 139 MOS 2019 s 9.55"
MOS_REF_THRESHOLD_PRECISION = "Part 139 MOS 2019 s 9.56"
MOS_REF_APPROACH_SALS = "Part 139 MOS 2019 ss 9.39-9.40"
MOS_REF_APPROACH_CAT_I = "Part 139 MOS 2019 s 9.41"
MOS_REF_APPROACH_CAT_II_III = "Part 139 MOS 2019 s 9.42"

RUNWAY_EDGE_INSTRUMENT_SPACING_M = 60.0
RUNWAY_EDGE_NON_INSTRUMENT_SPACING_M = 90.0
RUNWAY_LIGHTING_MIN_WIDTH_M = 30.0
PRECISION_THRESHOLD_MAX_SPACING_M = 3.0
NON_PRECISION_THRESHOLD_MIN_LIGHTS = 6
APPROACH_STANDARD_SPACING_M = 30.0
SALS_STANDARD_SPACING_M = 60.0
SALS_ENHANCED_SPACING_M = 30.0
SALS_CROSSBAR_DISTANCE_M = 300.0
SALS_CROSSBAR_LENGTH_NARROW_M = 18.0
SALS_CROSSBAR_LENGTH_STANDARD_M = 30.0
PRECISION_APPROACH_DESIGN_LENGTH_M = 900.0
PRECISION_APPROACH_MIN_FULL_LENGTH_M = 720.0
PRECISION_APPROACH_POINT_A_M = 150.0
PRECISION_APPROACH_POINT_B_M = 300.0
PRECISION_APPROACH_POINT_C_M = 450.0
PRECISION_APPROACH_POINT_D_M = 600.0
PRECISION_APPROACH_POINT_E_M = 750.0
PRECISION_CROSSBAR_LENGTH_M = 30.0
CAT_II_III_SIDE_ROW_INNER_SPACING_M = 18.0


def runway_is_precision(runway_type: str) -> bool:
    return "Precision Approach" in (runway_type or "")


def runway_is_instrument(runway_type: str) -> bool:
    value = runway_type or ""
    return "Non-Precision" in value or runway_is_precision(value)


def runway_edge_spacing_for_end(runway_type: str) -> float:
    if runway_is_instrument(runway_type):
        return RUNWAY_EDGE_INSTRUMENT_SPACING_M
    return RUNWAY_EDGE_NON_INSTRUMENT_SPACING_M


def runway_edge_start_offset_for_end(runway_type: str, edge_threshold_replaced: bool = False) -> float:
    spacing_m = runway_edge_spacing_for_end(runway_type)
    if runway_is_precision(runway_type) or edge_threshold_replaced:
        return spacing_m
    return 0.0


def threshold_light_count_for_end(runway_type: str, runway_width_m: float) -> int:
    lit_width_m = max(float(runway_width_m), RUNWAY_LIGHTING_MIN_WIDTH_M)
    if runway_is_precision(runway_type):
        return int(lit_width_m // PRECISION_THRESHOLD_MAX_SPACING_M) + 1
    return NON_PRECISION_THRESHOLD_MIN_LIGHTS


def approach_profile_for_end(runway_type: str) -> Dict[str, object]:
    if "Precision Approach CAT II/III" in (runway_type or ""):
        return {
            "system": "Precision Approach CAT II/III",
            "length_m": PRECISION_APPROACH_DESIGN_LENGTH_M,
            "spacing_m": APPROACH_STANDARD_SPACING_M,
            "crossbars_m": [
                PRECISION_APPROACH_POINT_A_M,
                PRECISION_APPROACH_POINT_B_M,
                PRECISION_APPROACH_POINT_C_M,
                PRECISION_APPROACH_POINT_D_M,
                PRECISION_APPROACH_POINT_E_M,
            ],
            "crossbar_length_m": PRECISION_CROSSBAR_LENGTH_M,
            "side_rows_to_m": PRECISION_APPROACH_POINT_B_M,
            "side_row_inner_spacing_m": CAT_II_III_SIDE_ROW_INNER_SPACING_M,
            "ref_mos": MOS_REF_APPROACH_CAT_II_III,
        }
    if "Precision Approach CAT I" in (runway_type or ""):
        return {
            "system": "Precision Approach CAT I",
            "length_m": PRECISION_APPROACH_DESIGN_LENGTH_M,
            "spacing_m": APPROACH_STANDARD_SPACING_M,
            "crossbars_m": [
                PRECISION_APPROACH_POINT_A_M,
                PRECISION_APPROACH_POINT_B_M,
                PRECISION_APPROACH_POINT_C_M,
                PRECISION_APPROACH_POINT_D_M,
                PRECISION_APPROACH_POINT_E_M,
            ],
            "crossbar_length_m": PRECISION_CROSSBAR_LENGTH_M,
            "side_rows_to_m": 0.0,
            "side_row_inner_spacing_m": 0.0,
            "ref_mos": MOS_REF_APPROACH_CAT_I,
        }
    if "Non-Precision" in (runway_type or ""):
        return {
            "system": "Simple Approach Lighting System",
            "length_m": 420.0,
            "spacing_m": SALS_STANDARD_SPACING_M,
            "crossbars_m": [SALS_CROSSBAR_DISTANCE_M],
            "crossbar_length_m": SALS_CROSSBAR_LENGTH_STANDARD_M,
            "side_rows_to_m": 0.0,
            "side_row_inner_spacing_m": 0.0,
            "ref_mos": MOS_REF_APPROACH_SALS,
        }
    return {
        "system": "None",
        "length_m": 0.0,
        "spacing_m": 0.0,
        "crossbars_m": [],
        "crossbar_length_m": 0.0,
        "side_rows_to_m": 0.0,
        "side_row_inner_spacing_m": 0.0,
        "ref_mos": "",
    }
