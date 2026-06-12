"""UK CAA CAP 168 aeronautical ground lighting policy."""

from typing import Any, Dict

SOURCE_PUBLICATION = "UK CAA CAP 168 Licensing of Aerodromes, Edition 13"
SOURCE_URL = "https://www.caa.co.uk/CAP168"

CAP168_REF_APPROACH = "CAP 168 6.39-6.46"
CAP168_REF_SIMPLE_APPROACH = "CAP 168 6.47-6.53"
CAP168_REF_RUNWAY_EDGE = "CAP 168 6.112-6.121"
CAP168_REF_THRESHOLD_END = "CAP 168 6.122-6.128 Figure 6.10"
CAP168_REF_STARTER_EXTENSION = "CAP 168 6.129-6.131"
CAP168_REF_RUNWAY_CENTRELINE = "CAP 168 6.132-6.143"
CAP168_REF_TDZ = "CAP 168 6.144-6.160"
CAP168_REF_INTENSITY_BALANCE = "CAP 168 6.314-6.318"

RUNWAY_EDGE_SPACING_M = 60.0
RUNWAY_EDGE_SPACING_TOLERANCE_M = 6.0
RUNWAY_EDGE_CAA_REVIEW_WIDTH_M = 50.0
RUNWAY_LIGHTING_MIN_WIDTH_M = 30.0

THRESHOLD_MAX_SPACING_M = 3.0
RUNWAY_END_MIN_LIGHTS = 6
THRESHOLD_WING_BAR_RECOMMENDED_SCALES = ("L3", "L4")
THRESHOLD_WING_BAR_REQUIRED_SCALES = ("L1", "L2")

PRECISION_APPROACH_DESIGN_LENGTH_M = 900.0
PRECISION_APPROACH_CROSSBAR_STATIONS_M = [150.0, 300.0, 450.0, 600.0, 750.0]
PRECISION_APPROACH_CROSSBAR_INTERVAL_M = 150.0
PRECISION_APPROACH_CROSSBAR_LENGTH_M = 30.0
APPROACH_STANDARD_SPACING_M = 30.0

SALS_DESIGN_LENGTH_M = 420.0
SALS_STANDARD_SPACING_M = 60.0
SALS_CROSSBAR_DISTANCE_M = 300.0
SALS_CROSSBAR_LENGTH_M = 30.0

STROBE_APPROACH_LIGHT_COUNT = 7
STROBE_APPROACH_CENTRELINE_LIGHT_COUNT = 5
STROBE_APPROACH_THRESHOLD_LIGHT_COUNT = 2
STROBE_MAX_DISCHARGE_DURATION_S = 0.2
STROBE_MAX_SEQUENCE_INTERVAL_S = 1.2

CAT_II_III_SUPPLEMENTARY_CENTRELINE_TO_M = 300.0
CAT_II_III_SIDE_ROWS_TO_M = 270.0
CAT_II_III_CENTRELINE_BARRETTE_LIGHTS_EACH_SIDE = 2
CAT_II_III_CENTRELINE_BARRETTE_SPACING_M = 1.2
CAT_II_III_SIDE_ROW_LIGHTS_PER_BARRETTE = 4
CAT_II_III_SIDE_ROW_BARRETTE_SPACING_M = 1.5
CAT_II_III_SIDE_ROW_INNER_SPACING_M = 18.0
CAT_II_III_SIDE_ROW_HALF_INNER_SPACING_M = CAT_II_III_SIDE_ROW_INNER_SPACING_M / 2.0
CAT_II_III_POINT_B_CROSSBAR_HALF_WIDTH_M = 15.0
CAT_II_III_CROSSBAR_MAX_SPACING_M = 2.7

RUNWAY_CENTRELINE_DEFAULT_SPACING_M = 15.0
RUNWAY_CENTRELINE_RELAXED_SPACING_M = 30.0
RUNWAY_CENTRELINE_MAX_OFFSET_M = 0.6
RUNWAY_CENTRELINE_RED_ZONE_M = 300.0
RUNWAY_CENTRELINE_ALTERNATING_ZONE_M = 600.0
RUNWAY_CENTRELINE_WHITE_ZONE_TO_UPWIND_END_M = 900.0

TDZ_LENGTH_M = 900.0
TDZ_ROW_SPACING_M = 60.0
TDZ_ROW_SPACING_TOLERANCE_M = 6.0
TDZ_BARRETTE_LIGHTS = 4
TDZ_BARRETTE_SPACING_MAX_M = 1.5
TDZ_BARRETTE_SPACING_M = TDZ_BARRETTE_SPACING_MAX_M
TDZ_INNER_OFFSET_MIN_M = 9.0
TDZ_INNER_OFFSET_MAX_M = 11.5
TDZ_INNER_OFFSET_M = TDZ_INNER_OFFSET_MIN_M
TDZ_FIRST_ROW_OFFSET_M = TDZ_ROW_SPACING_M
TDZ_MARKING_LENGTH_M = 22.5

SIMPLE_TDZ_LIGHT_PAIRS = 2
SIMPLE_TDZ_OFFSET_BEYOND_FINAL_TDZ_MARKING_M = 0.3

THRESHOLD_WING_BAR_LIGHTS_PER_SIDE = 5
THRESHOLD_WING_BAR_SPACING_M = 2.5
RTIL_DEFAULT_LATERAL_FROM_EDGE_LIGHTS_M = 12.0
TEMP_DISPLACED_THRESHOLD_SPACING_M = 2.5
STOPWAY_END_MIN_LIGHTS = 2

LIGHT_COLOUR_WHITE = "white"
LIGHT_COLOUR_VARIABLE_WHITE = "variable white"
LIGHT_COLOUR_YELLOW = "yellow"
LIGHT_COLOUR_GREEN = "green"
LIGHT_COLOUR_RED = "red"
LIGHT_COLOUR_BLUE = "blue"
LIGHT_COLOUR_FLASHING_WHITE = "flashing white"

MOS_REF_RUNWAY_EDGE = CAP168_REF_RUNWAY_EDGE
MOS_REF_DISPLACED_THRESHOLD_EDGE = CAP168_REF_RUNWAY_EDGE
MOS_REF_THRESHOLD_LOCATION = CAP168_REF_THRESHOLD_END
MOS_REF_THRESHOLD_PRECISION = CAP168_REF_THRESHOLD_END
MOS_REF_THRESHOLD_NON_PRECISION = CAP168_REF_THRESHOLD_END
MOS_REF_THRESHOLD_WING_BARS = CAP168_REF_THRESHOLD_END
MOS_REF_RTIL = CAP168_REF_SIMPLE_APPROACH
MOS_REF_TEMP_DISPLACED_THRESHOLD = CAP168_REF_THRESHOLD_END
MOS_REF_RUNWAY_END = CAP168_REF_THRESHOLD_END
MOS_REF_STOPWAY = CAP168_REF_THRESHOLD_END
MOS_REF_RUNWAY_CENTRELINE = CAP168_REF_RUNWAY_CENTRELINE
MOS_REF_TDZ = CAP168_REF_TDZ

APPROACH_PROFILE_NONE = {
    "system": "None",
    "length_m": 0.0,
    "spacing_m": 0.0,
    "crossbars_m": [],
    "crossbar_length_m": 0.0,
    "side_rows_to_m": 0.0,
    "side_row_inner_spacing_m": 0.0,
    "approach_type": "none",
    "ref_cap168": "",
    "ref_mos": "",
}

APPROACH_PROFILES = (
    (
        "Precision Approach CAT II/III",
        {
            "system": "Precision Approach CAT II/III",
            "length_m": PRECISION_APPROACH_DESIGN_LENGTH_M,
            "spacing_m": APPROACH_STANDARD_SPACING_M,
            "crossbars_m": list(PRECISION_APPROACH_CROSSBAR_STATIONS_M),
            "crossbar_length_m": PRECISION_APPROACH_CROSSBAR_LENGTH_M,
            "side_rows_to_m": CAT_II_III_SIDE_ROWS_TO_M,
            "side_row_inner_spacing_m": CAT_II_III_SIDE_ROW_INNER_SPACING_M,
            "approach_type": "cat_ii_iii",
            "ref_cap168": f"{CAP168_REF_APPROACH}; {CAP168_REF_TDZ}",
            "ref_mos": f"{CAP168_REF_APPROACH}; {CAP168_REF_TDZ}",
        },
    ),
    (
        "Precision Approach CAT I",
        {
            "system": "Precision Approach CAT I",
            "length_m": PRECISION_APPROACH_DESIGN_LENGTH_M,
            "spacing_m": APPROACH_STANDARD_SPACING_M,
            "crossbars_m": list(PRECISION_APPROACH_CROSSBAR_STATIONS_M),
            "crossbar_length_m": PRECISION_APPROACH_CROSSBAR_LENGTH_M,
            "side_rows_to_m": 0.0,
            "side_row_inner_spacing_m": 0.0,
            "approach_type": "cat_i",
            "ref_cap168": CAP168_REF_APPROACH,
            "ref_mos": CAP168_REF_APPROACH,
        },
    ),
    (
        "Non-Precision",
        {
            "system": "Simple Approach Lighting System",
            "length_m": SALS_DESIGN_LENGTH_M,
            "spacing_m": SALS_STANDARD_SPACING_M,
            "crossbars_m": [SALS_CROSSBAR_DISTANCE_M],
            "crossbar_length_m": SALS_CROSSBAR_LENGTH_M,
            "side_rows_to_m": 0.0,
            "side_row_inner_spacing_m": 0.0,
            "approach_type": "sals",
            "ref_cap168": CAP168_REF_SIMPLE_APPROACH,
            "ref_mos": CAP168_REF_SIMPLE_APPROACH,
        },
    ),
)

THRESHOLD_WING_BAR_PARAMS = {
    "required_for_scales": THRESHOLD_WING_BAR_REQUIRED_SCALES,
    "required_when_threshold_displaced": True,
    "recommended_for_scales": THRESHOLD_WING_BAR_RECOMMENDED_SCALES,
    "colour": LIGHT_COLOUR_GREEN,
    "ref": CAP168_REF_THRESHOLD_END,
}

STARTER_EXTENSION_LIGHTING_PARAMS = {
    "narrower_than_runway": {"edge_colour": LIGHT_COLOUR_BLUE, "ref": "CAP 168 6.129"},
    "pre_threshold_same_width": {
        "approach_direction_colour": LIGHT_COLOUR_RED,
        "opposite_direction_colour": LIGHT_COLOUR_WHITE,
        "spacing_m": RUNWAY_EDGE_SPACING_M,
        "ref": "CAP 168 6.130",
    },
    "centreline_guidance": {
        "acceptable_sources": ("approach_lighting_system", "runway_centreline_lights"),
        "ref": "CAP 168 6.131",
    },
}

TDZ_LIGHTING_PARAMS = {
    "length_m": TDZ_LENGTH_M,
    "length_rule": "900_m_or_runway_midpoint_whichever_is_less",
    "row_spacing_m": TDZ_ROW_SPACING_M,
    "row_spacing_tolerance_m": TDZ_ROW_SPACING_TOLERANCE_M,
    "barrette_lights": TDZ_BARRETTE_LIGHTS,
    "barrette_spacing_max_m": TDZ_BARRETTE_SPACING_MAX_M,
    "inner_offset_min_m": TDZ_INNER_OFFSET_MIN_M,
    "inner_offset_max_m": TDZ_INNER_OFFSET_MAX_M,
    "cat_ii_setting_angle_deg": 3.0,
    "cat_iii_setting_angle_deg": 5.5,
    "ref": CAP168_REF_TDZ,
}

SIMPLE_TDZ_LIGHTING_PARAMS = {
    "light_pairs": SIMPLE_TDZ_LIGHT_PAIRS,
    "offset_beyond_final_tdz_marking_m": SIMPLE_TDZ_OFFSET_BEYOND_FINAL_TDZ_MARKING_M,
    "same_lateral_spacing_as_tdz_marking": True,
    "pair_spacing_max_m": TDZ_BARRETTE_SPACING_MAX_M,
    "colour": LIGHT_COLOUR_VARIABLE_WHITE,
    "separate_circuit_good_practice": True,
    "ref": "CAP 168 6.152-6.160",
}

RUNWAY_EDGE_LIGHTING_PARAMS = {
    "spacing_m": RUNWAY_EDGE_SPACING_M,
    "spacing_tolerance_m": RUNWAY_EDGE_SPACING_TOLERANCE_M,
    "caa_review_if_width_exceeds_m": RUNWAY_EDGE_CAA_REVIEW_WIDTH_M,
    "yellow_caution_zone_m": RUNWAY_CENTRELINE_ALTERNATING_ZONE_M,
    "yellow_caution_zone_max_fraction": 1 / 3,
    "displaced_threshold_pre_threshold_colour": LIGHT_COLOUR_RED,
    "exit_taxiway_optional_colour": LIGHT_COLOUR_BLUE,
    "ref": CAP168_REF_RUNWAY_EDGE,
}

STROBE_APPROACH_PARAMS = {
    "light_count": STROBE_APPROACH_LIGHT_COUNT,
    "centreline_light_count": STROBE_APPROACH_CENTRELINE_LIGHT_COUNT,
    "threshold_light_count": STROBE_APPROACH_THRESHOLD_LIGHT_COUNT,
    "max_discharge_duration_s": STROBE_MAX_DISCHARGE_DURATION_S,
    "max_sequence_interval_s": STROBE_MAX_SEQUENCE_INTERVAL_S,
    "ref": "CAP 168 6.49-6.53",
}

LIGHTING_TRACEABILITY_ITEMS = {
    "approach_lighting": {
        "source": CAP168_REF_APPROACH,
        "status": "operational_verified",
        "implementation": "APPROACH_PROFILES[cat_i/cat_ii_iii]",
        "notes": "900 m high-intensity coded centreline and five crossbars at 150 m intervals.",
    },
    "simple_approach_lighting": {
        "source": CAP168_REF_SIMPLE_APPROACH,
        "status": "operational_verified",
        "implementation": "APPROACH_PROFILES[sals] and STROBE_APPROACH_PARAMS",
        "notes": "Simple approach row at 60 m intervals to at least 420 m, 300 m crossbar, and strobe alternative.",
    },
    "runway_edge_lights": {
        "source": CAP168_REF_RUNWAY_EDGE,
        "status": "operational_verified",
        "implementation": "RUNWAY_EDGE_LIGHTING_PARAMS / runway_edge_spacing_for_end",
        "notes": "60 m +/- 6 m spacing for runways up to 50 m wide; wider runways may require closer CAA-agreed spacing.",
    },
    "threshold_lights": {
        "source": CAP168_REF_THRESHOLD_END,
        "status": "operational_verified",
        "implementation": "threshold_light_count_for_end and THRESHOLD_WING_BAR_PARAMS",
        "notes": "Threshold light count is derived from runway width with 3 m maximum spacing.",
    },
    "runway_end_lights": {
        "source": CAP168_REF_THRESHOLD_END,
        "status": "operational_verified",
        "implementation": "runway_end_light_count_for_end",
        "notes": "Runway end lights delineate the manoeuvring extremity; six-light minimum retained as the planning helper.",
    },
    "starter_extension_lighting": {
        "source": CAP168_REF_STARTER_EXTENSION,
        "status": "operational_verified",
        "implementation": "STARTER_EXTENSION_LIGHTING_PARAMS",
        "notes": "Blue edge lights for narrow starter extensions; red/white pre-threshold edge lights for same-width pre-threshold runway.",
    },
    "runway_centreline_lights": {
        "source": CAP168_REF_RUNWAY_CENTRELINE,
        "status": "operational_verified_with_applicability_policy",
        "implementation": "RUNWAY_CENTRELINE_* / runway_centreline_*",
        "notes": "15 m normal spacing, 30 m allowed for RVR >=300 m when maintenance objectives are met; CAT II/III and low-RVR take-off are required cases.",
    },
    "touchdown_zone_lights": {
        "source": CAP168_REF_TDZ,
        "status": "operational_verified",
        "implementation": "TDZ_LIGHTING_PARAMS and SIMPLE_TDZ_LIGHTING_PARAMS",
        "notes": "TDZ barrettes have four lights, 60 m +/- 6 m spacing, and 9-11.5 m inner offset.",
    },
    "intensity_balance": {
        "source": CAP168_REF_INTENSITY_BALANCE,
        "status": "operational_verified",
        "implementation": "CAP168_REF_INTENSITY_BALANCE",
        "notes": "Overall approach/runway lighting pattern should be balanced around 2:1; IRVR requires at least 10% runway edge intensity below 1500 m observed visibility.",
    },
}

LIGHTING_TRACEABILITY = {
    "source_publication": SOURCE_PUBLICATION,
    "source_url": SOURCE_URL,
    "items": LIGHTING_TRACEABILITY_ITEMS,
}


def agl_value(name: str):
    return globals()[name]


def get_lighting_traceability() -> Dict[str, Any]:
    return LIGHTING_TRACEABILITY.copy()


def runway_is_precision(runway_type: str) -> bool:
    value = runway_type or ""
    return "Precision Approach" in value and "Non-Precision" not in value


def runway_type_supports_agl(runway_type: str) -> bool:
    value = runway_type or ""
    return "Non-Instrument" in value or "Non-Precision" in value or runway_is_precision(value)


def runway_is_instrument(runway_type: str) -> bool:
    value = runway_type or ""
    return "Non-Precision" in value or runway_is_precision(value)


def runway_edge_spacing_for_end(runway_type: str) -> float:
    del runway_type
    return RUNWAY_EDGE_SPACING_M


def runway_edge_start_offset_for_end(runway_type: str, edge_threshold_replaced: bool = False) -> float:
    spacing_m = runway_edge_spacing_for_end(runway_type)
    if runway_is_precision(runway_type) or edge_threshold_replaced:
        return spacing_m
    return 0.0


def threshold_light_count_for_end(runway_type: str, runway_width_m: float) -> int:
    del runway_type
    lit_width_m = max(float(runway_width_m), RUNWAY_LIGHTING_MIN_WIDTH_M)
    return int(lit_width_m // THRESHOLD_MAX_SPACING_M) + 1


def runway_end_light_count_for_end(runway_type: str, runway_width_m: float) -> int:
    del runway_type, runway_width_m
    return RUNWAY_END_MIN_LIGHTS


def temp_displaced_threshold_lights_per_side(runway_width_m: float) -> int:
    if float(runway_width_m) <= RUNWAY_LIGHTING_MIN_WIDTH_M:
        return 3
    return 5


def runway_centreline_required(runway_type_1: str, runway_type_2: str, rvr_below_350: bool = False) -> bool:
    if rvr_below_350:
        return True
    return "Precision Approach CAT II/III" in (runway_type_1 or "") or "Precision Approach CAT II/III" in (
        runway_type_2 or ""
    )


def runway_centreline_recommended(runway_type_1: str, runway_type_2: str, edge_light_width_m: float) -> bool:
    if float(edge_light_width_m) > RUNWAY_EDGE_CAA_REVIEW_WIDTH_M:
        return True
    return "Precision Approach CAT I" in (runway_type_1 or "") or "Precision Approach CAT I" in (runway_type_2 or "")


def runway_centreline_spacing(rvr_below_350: bool) -> float:
    if rvr_below_350:
        return RUNWAY_CENTRELINE_DEFAULT_SPACING_M
    return RUNWAY_CENTRELINE_RELAXED_SPACING_M


def approach_profile_for_runway(runway_type: str) -> Dict[str, object]:
    value = runway_type or ""
    for trigger, profile in APPROACH_PROFILES:
        if trigger in value:
            return {key: list(val) if isinstance(val, list) else val for key, val in profile.items()}
    if "Non-Precision" in value or "Non-Instrument" in value:
        profile = APPROACH_PROFILES[2][1]
        return {key: list(val) if isinstance(val, list) else val for key, val in profile.items()}
    return {key: list(val) if isinstance(val, list) else val for key, val in APPROACH_PROFILE_NONE.items()}


def approach_profile_for_end(runway_type: str) -> Dict[str, object]:
    return approach_profile_for_runway(runway_type)


__all__ = [
    "SOURCE_PUBLICATION",
    "SOURCE_URL",
    "CAP168_REF_APPROACH",
    "CAP168_REF_SIMPLE_APPROACH",
    "CAP168_REF_RUNWAY_EDGE",
    "CAP168_REF_THRESHOLD_END",
    "CAP168_REF_STARTER_EXTENSION",
    "CAP168_REF_RUNWAY_CENTRELINE",
    "CAP168_REF_TDZ",
    "CAP168_REF_INTENSITY_BALANCE",
    "RUNWAY_EDGE_SPACING_M",
    "RUNWAY_EDGE_SPACING_TOLERANCE_M",
    "RUNWAY_LIGHTING_MIN_WIDTH_M",
    "THRESHOLD_MAX_SPACING_M",
    "RUNWAY_END_MIN_LIGHTS",
    "APPROACH_PROFILES",
    "APPROACH_PROFILE_NONE",
    "THRESHOLD_WING_BAR_PARAMS",
    "STARTER_EXTENSION_LIGHTING_PARAMS",
    "TDZ_LIGHTING_PARAMS",
    "SIMPLE_TDZ_LIGHTING_PARAMS",
    "RUNWAY_EDGE_LIGHTING_PARAMS",
    "STROBE_APPROACH_PARAMS",
    "LIGHTING_TRACEABILITY",
    "LIGHTING_TRACEABILITY_ITEMS",
    "agl_value",
    "get_lighting_traceability",
    "runway_is_precision",
    "runway_type_supports_agl",
    "runway_is_instrument",
    "runway_edge_spacing_for_end",
    "runway_edge_start_offset_for_end",
    "threshold_light_count_for_end",
    "runway_end_light_count_for_end",
    "temp_displaced_threshold_lights_per_side",
    "runway_centreline_required",
    "runway_centreline_recommended",
    "runway_centreline_spacing",
    "approach_profile_for_runway",
    "approach_profile_for_end",
]
