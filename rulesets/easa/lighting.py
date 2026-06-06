"""EASA CS‑ADR‑DSN airfield ground lighting dimensions and policy.

This module defines a set of constants and helper functions that describe
the aerodrome ground lighting (AGL) requirements contained in EASA's
Certification Specifications for Aerodromes Design (CS‑ADR‑DSN), Issue 6,
Chapter M – Visual aids for navigation (lights).  The constants capture
dimensional criteria for runway and approach lighting systems under
European conditions.  These values are drawn from Chapter M of CS‑ADR‑DSN
and are intended to mirror the structure of the `lighting.py` schema used
for Australian MOS 139 regulations.  They provide a convenient way to
compute or verify lighting layouts when planning an aerodrome to meet
EASA requirements.

NOTE: The constants in this file are based on the following CS‑ADR‑DSN
references (Issue 6):

* CS ADR‑DSN.M.626 – Simple approach lighting systems
* CS ADR‑DSN.M.630 – Precision approach Category I lighting system
* CS ADR‑DSN.M.635 – Precision approach Category II and III lighting system
* CS ADR‑DSN.M.675 – Runway edge lights
* CS ADR‑DSN.M.680 – Runway threshold and wing bar lights
* CS ADR‑DSN.M.685 – Runway end lights
* CS ADR‑DSN.M.690 – Runway centre line lights
* CS ADR‑DSN.M.695 – Runway touchdown zone lights

Where the specification provides a range (e.g. spacing between lights),
the most common or preferred value is encoded here to support typical
planning assumptions.  See the referenced CS‑ADR‑DSN paragraphs for
permitted tolerances.
"""

from typing import Dict

CS_ADR_DSN = "CS‑ADR‑DSN Issue 6"
# References to the relevant CS‑ADR‑DSN sections.  These strings are
# included with constants to allow traceability back to the regulation.
EASA_REF_RUNWAY_EDGE = "CS ADR‑DSN.M.675"
EASA_REF_THRESHOLD = "CS ADR‑DSN.M.680"
EASA_REF_RUNWAY_END = "CS ADR‑DSN.M.685"
EASA_REF_RUNWAY_CENTRELINE = "CS ADR‑DSN.M.690"
EASA_REF_TDZ = "CS ADR‑DSN.M.695"
EASA_REF_SIMPLE_APPROACH = "CS ADR‑DSN.M.626"
EASA_REF_APPROACH_CAT_I = "CS ADR‑DSN.M.630"
EASA_REF_APPROACH_CAT_II_III = "CS ADR‑DSN.M.635"

# ---------------------------------------------------------------------------
# Runway edge lights
# Under CS ADR‑DSN.M.675 the maximum interval between runway edge lights is
# 60 m for an instrument runway and 100 m for a non‑instrument runway【734774195983807†L2240-L2278】.
RUNWAY_EDGE_INSTRUMENT_SPACING_M = 60.0
RUNWAY_EDGE_NON_INSTRUMENT_SPACING_M = 100.0

# Minimum width of runway used to determine the number of threshold and end
# lights.  CS‑ADR‑DSN does not specify a minimum lighting width, so 30 m is
# retained from MOS 139 as a pragmatic lower bound when calculating light
# counts.
RUNWAY_LIGHTING_MIN_WIDTH_M = 30.0

# ---------------------------------------------------------------------------
# Threshold lighting
# CS ADR‑DSN.M.680 requires at least six threshold lights on a non‑instrument
# or non‑precision runway and threshold lights on precision runways spaced
# not more than 3 m between the runway edge light rows【734774195983807†L2350-L2372】.
PRECISION_THRESHOLD_MAX_SPACING_M = 3.0
NON_PRECISION_THRESHOLD_MIN_LIGHTS = 6

# Wing bar lights consist of at least five lights extending at least 10 m
# outward from the runway edge line【734774195983807†L2399-L2407】.  Uniform spacing
# over 10 m yields a nominal 2.5 m spacing between lights.
THRESHOLD_WING_BAR_LIGHTS_PER_SIDE = 5
THRESHOLD_WING_BAR_EXTEND_M = 10.0
THRESHOLD_WING_BAR_SPACING_M = THRESHOLD_WING_BAR_EXTEND_M / (THRESHOLD_WING_BAR_LIGHTS_PER_SIDE - 1)

# ---------------------------------------------------------------------------
# Runway end lights
# CS ADR‑DSN.M.685 requires at least six runway end lights, with a maximum
# spacing of 6 m for Category III runways【734774195983807†L2467-L2470】.
RUNWAY_END_MIN_LIGHTS = 6
CAT_III_RUNWAY_END_MAX_SPACING_M = 6.0

# ---------------------------------------------------------------------------
# Simple approach lighting system (SALS)
# CS ADR‑DSN.M.626 describes a row of lights on the extended centre line
# extending preferably 420 m from the threshold with a crossbar at
# 300 m【734774195983807†L796-L806】.  Centreline lights are spaced at 60 m
# intervals, but 30 m may be used for improved guidance【734774195983807†L836-L840】.
# The crossbar may be 18 m or 30 m long【734774195983807†L804-L807】.
SALS_STANDARD_SPACING_M = 60.0
SALS_ENHANCED_SPACING_M = 30.0
SALS_CROSSBAR_DISTANCE_M = 300.0
SALS_CROSSBAR_LENGTH_NARROW_M = 18.0
SALS_CROSSBAR_LENGTH_STANDARD_M = 30.0
SALS_DESIGN_LENGTH_M = 420.0

# ---------------------------------------------------------------------------
# Precision approach lighting systems
# Both Category I and Category II/III systems extend up to 900 m from the
# threshold【734774195983807†L955-L960】【734774195983807†L1126-L1133】.  Crossbars are
# provided at 150 m and 300 m, with additional crossbars at 450 m, 600 m and
# 750 m for systems using single light sources【734774195983807†L1030-L1057】.
PRECISION_APPROACH_DESIGN_LENGTH_M = 900.0
PRECISION_APPROACH_MIN_FULL_LENGTH_M = 720.0  # used as a recommended minimum
PRECISION_APPROACH_POINT_A_M = 150.0
PRECISION_APPROACH_POINT_B_M = 300.0
PRECISION_APPROACH_POINT_C_M = 450.0
PRECISION_APPROACH_POINT_D_M = 600.0
PRECISION_APPROACH_POINT_E_M = 750.0

# The standard crossbar length is 30 m for both Category I and Category II/III
# systems【734774195983807†L955-L961】【734774195983807†L1169-L1172】.  For Category II/III
# systems the crossbar at 300 m extends 15 m from the centre line on each
# side【734774195983807†L1169-L1172】.
PRECISION_CROSSBAR_LENGTH_M = 30.0
CAT_II_III_SIDE_ROW_INNER_SPACING_M = 18.0  # preferred gauge between side rows【734774195983807†L1158-L1162】
CAT_II_III_SIDE_ROW_HALF_INNER_SPACING_M = CAT_II_III_SIDE_ROW_INNER_SPACING_M / 2.0
CAT_II_III_POINT_B_CROSSBAR_HALF_WIDTH_M = 15.0  # half‑length of 300 m crossbar
CAT_II_III_CROSSBAR_MAX_SPACING_M = 2.7  # maximum spacing of lights on crossbars【734774195983807†L1294-L1303】

# Side rows for Category II/III approaches extend 270 m from the threshold
# (240 m if higher serviceability is demonstrated)【734774195983807†L1126-L1140】.
CAT_II_III_SIDE_ROWS_TO_M = 270.0

# ---------------------------------------------------------------------------
# Runway centre line lights
# CS ADR‑DSN.M.690 specifies centreline lights at approximately 15 m
# intervals, increasing to 30 m when runway visual range is ≥ 350 m and
# sufficient serviceability is demonstrated【734774195983807†L2528-L2551】.
RUNWAY_CENTRELINE_DEFAULT_SPACING_M = 15.0
RUNWAY_CENTRELINE_LOW_VIS_SPACING_M = 30.0

# Maximum lateral offset from the runway centre line is 0.6 m (60 cm)
#【734774195983807†L2528-L2534】.
RUNWAY_CENTRELINE_MAX_OFFSET_M = 0.6

# Colour zones along the runway for centreline lights: variable white from
# threshold to 900 m from the runway end, alternating red and white from
# 900 m to 300 m from the runway end, and red from 300 m to the end【734774195983807†L2555-L2561】.
RUNWAY_CENTRELINE_RED_ZONE_M = 300.0
RUNWAY_CENTRELINE_ALTERNATING_ZONE_M = 900.0

# ---------------------------------------------------------------------------
# Touchdown zone lights (TDZ)
# CS ADR‑DSN.M.695 requires touchdown zone lights to extend 900 m from the
# threshold (or to the midpoint of shorter runways)【734774195983807†L2645-L2651】.
TDZ_LENGTH_M = 900.0
# Pairs of barrettes are spaced at 30 m or 60 m intervals【734774195983807†L2652-L2660】.
TDZ_ROW_SPACING_M = 60.0
# Each barrette has at least three lights with a spacing of ≤ 1.5 m and a
# length between 3 m and 4.5 m【734774195983807†L2646-L2669】.
TDZ_BARRETTE_LIGHTS = 3
TDZ_BARRETTE_SPACING_M = 1.5
TDZ_BARRETTE_LENGTH_MIN_M = 3.0
TDZ_BARRETTE_LENGTH_MAX_M = 4.5
# The lateral offset between the runway centre line and the innermost lights
# of a TDZ barrette equals half the gauge selected for the touchdown zone
# marking.  A nominal 9 m offset is provided here for typical 18 m gauge.
TDZ_INNER_OFFSET_M = 9.0

# ---------------------------------------------------------------------------
# Light colours used in EASA systems
LIGHT_COLOUR_VARIABLE_WHITE = "variable white"
LIGHT_COLOUR_YELLOW = "yellow"
LIGHT_COLOUR_GREEN = "green"
LIGHT_COLOUR_RED = "red"
LIGHT_COLOUR_BLUE = "blue"
LIGHT_COLOUR_FLASHING_WHITE = "flashing white"

# ---------------------------------------------------------------------------
# Approach profiles
# Each approach profile dictionary captures the salient features of the
# approach lighting system for a given runway type.  These are organised
# similarly to the MOS 139 profile definitions to facilitate comparisons.

APPROACH_PROFILE_NONE = {
    "system": "None",
    "length_m": 0.0,
    "spacing_m": 0.0,
    "crossbars_m": [],
    "crossbar_length_m": 0.0,
    "side_rows_to_m": 0.0,
    "side_row_inner_spacing_m": 0.0,
    "approach_type": "none",
    "ref_easa": "",
}

APPROACH_PROFILES = (
    (
        "Precision Approach CAT II/III",
        {
            "system": "Precision Approach CAT II/III",
            "length_m": PRECISION_APPROACH_DESIGN_LENGTH_M,
            "spacing_m": RUNWAY_CENTRELINE_LOW_VIS_SPACING_M,
            "crossbars_m": [
                PRECISION_APPROACH_POINT_A_M,
                PRECISION_APPROACH_POINT_B_M,
                PRECISION_APPROACH_POINT_C_M,
                PRECISION_APPROACH_POINT_D_M,
                PRECISION_APPROACH_POINT_E_M,
            ],
            "crossbar_length_m": PRECISION_CROSSBAR_LENGTH_M,
            "side_rows_to_m": CAT_II_III_SIDE_ROWS_TO_M,
            "side_row_inner_spacing_m": CAT_II_III_SIDE_ROW_INNER_SPACING_M,
            "approach_type": "cat_ii_iii",
            "ref_easa": EASA_REF_APPROACH_CAT_II_III,
        },
    ),
    (
        "Precision Approach CAT I",
        {
            "system": "Precision Approach CAT I",
            "length_m": PRECISION_APPROACH_DESIGN_LENGTH_M,
            "spacing_m": RUNWAY_CENTRELINE_LOW_VIS_SPACING_M,
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
            "approach_type": "cat_i",
            "ref_easa": EASA_REF_APPROACH_CAT_I,
        },
    ),
    (
        "Non‑Precision",
        {
            "system": "Simple Approach Lighting System",
            "length_m": SALS_DESIGN_LENGTH_M,
            "spacing_m": SALS_STANDARD_SPACING_M,
            "crossbars_m": [SALS_CROSSBAR_DISTANCE_M],
            "crossbar_length_m": SALS_CROSSBAR_LENGTH_STANDARD_M,
            "side_rows_to_m": 0.0,
            "side_row_inner_spacing_m": 0.0,
            "approach_type": "sals",
            "ref_easa": EASA_REF_SIMPLE_APPROACH,
        },
    ),
)


def agl_value(name: str):
    """Return the value of a constant defined in this module.

    This helper mirrors the function in lighting.py to simplify lookups from
    external code.  Passing the name of any globally defined constant will
    return its value.  A KeyError is raised if the name is unknown.
    """
    return globals()[name]


def runway_is_precision(runway_type: str) -> bool:
    """Return True if the runway type indicates a precision approach.

    Precision approach runways include Category I, II and III.  The check
    is case sensitive on the substring 'Precision Approach'.  A None
    argument yields False.
    """
    return "Precision Approach" in (runway_type or "")


def runway_type_supports_agl(runway_type: str) -> bool:
    """Return True if AGL should be provided for the given runway type.

    Under CS‑ADR‑DSN, AGL is required for non‑instrument, non‑precision and
    precision runways where operations take place at night or under low
    visibility.  The helper mirrors the logic in lighting.py to decide
    whether the lighting functions apply to a given runway description.
    """
    value = runway_type or ""
    return (
        "Non-Instrument" in value
        or "Non‑Instrument" in value
        or "Non-Precision" in value
        or "Non‑Precision" in value
        or runway_is_precision(value)
    )


def runway_is_instrument(runway_type: str) -> bool:
    """Return True if the runway is an instrument or precision runway.

    Non‑precision and precision approach runways are considered
    instrument runways for the purpose of edge light spacing.
    """
    value = runway_type or ""
    return "Non-Precision" in value or "Non‑Precision" in value or runway_is_precision(value)


def runway_edge_spacing_for_end(runway_type: str) -> float:
    """Return the maximum spacing (in metres) between runway edge lights.

    Instrument runways (non‑precision or precision) use 60 m spacing,
    whereas non‑instrument runways use 100 m spacing【734774195983807†L2240-L2278】.
    """
    if runway_is_instrument(runway_type):
        return RUNWAY_EDGE_INSTRUMENT_SPACING_M
    return RUNWAY_EDGE_NON_INSTRUMENT_SPACING_M


def runway_edge_start_offset_for_end(runway_type: str, edge_threshold_replaced: bool = False) -> float:
    """Return the longitudinal offset from the runway end to the first edge light.

    For precision runways (or where threshold lights replace the edge
    threshold), the first edge light is one spacing interval from the end.
    Otherwise there is no offset.  This mirrors the MOS 139 logic.
    """
    spacing_m = runway_edge_spacing_for_end(runway_type)
    if runway_is_precision(runway_type) or edge_threshold_replaced:
        return spacing_m
    return 0.0


def threshold_light_count_for_end(runway_type: str, runway_width_m: float) -> int:
    """Return the number of threshold lights required for a runway end.

    Non‑precision and non‑instrument runways require at least six lights
    regardless of runway width【734774195983807†L2350-L2372】.  Precision runways use
    a spacing requirement (≤ 3 m) to determine the number of lights.  The
    lit width is at least 30 m to avoid under‑counting lights for narrow
    runways.
    """
    lit_width_m = max(float(runway_width_m), RUNWAY_LIGHTING_MIN_WIDTH_M)
    if runway_is_precision(runway_type):
        # Number of lights = floor(width/spacing) + 1
        return int(lit_width_m // PRECISION_THRESHOLD_MAX_SPACING_M) + 1
    return NON_PRECISION_THRESHOLD_MIN_LIGHTS


def runway_end_light_count_for_end(runway_type: str, runway_width_m: float) -> int:
    """Return the number of runway end lights required.

    Category III runways must not exceed 6 m spacing between runway end
    lights, which determines the count based on runway width.  Other
    runways require at least six end lights【734774195983807†L2467-L2470】.
    """
    lit_width_m = max(float(runway_width_m), RUNWAY_LIGHTING_MIN_WIDTH_M)
    runway_type = runway_type or ""
    if "CAT III" in runway_type or "CAT II/III" in runway_type:
        return int(lit_width_m // CAT_III_RUNWAY_END_MAX_SPACING_M) + 1
    return RUNWAY_END_MIN_LIGHTS


def temp_displaced_threshold_lights_per_side(runway_width_m: float) -> int:
    """Return the number of temporary displaced threshold lights per side.

    CS‑ADR‑DSN does not give specific guidance for displaced threshold
    lighting bars.  The values from MOS 139 are adopted here: five lights
    per side for standard widths and three lights per side for narrow
    runway widths (≤ 30 m).
    """
    if float(runway_width_m) <= RUNWAY_LIGHTING_MIN_WIDTH_M:
        return 3
    return 5


def runway_centreline_required(runway_type_1: str, runway_type_2: str, rvr_below_350: bool = False) -> bool:
    """Return True if runway centre line lights should be provided.

    Centre line lights are required on precision runways Category II/III
    (always) and on Category I runways when high landing speeds or wide
    runways warrant them【734774195983807†L2608-L2623】.  They are also required
    for take‑off in low visibility conditions.  The simple heuristic used
    here matches the MOS 139 logic: centre line lights are provided when
    either runway end type is precision and the runway visual range is
    below 350 m.
    """
    if rvr_below_350:
        return True
    # Provide centre line lights if either runway end is a precision approach.
    return runway_is_precision(runway_type_1) or runway_is_precision(runway_type_2)


def runway_centreline_recommended(runway_type_1: str, runway_type_2: str, edge_light_width_m: float) -> bool:
    """Return True if runway centre line lights are recommended."""
    return runway_is_precision(runway_type_1) or runway_is_precision(runway_type_2) or float(edge_light_width_m) > 50.0


def runway_centreline_spacing(rvr_below_350: bool) -> float:
    """Return the runway centre line light spacing in metres."""
    if rvr_below_350:
        return RUNWAY_CENTRELINE_DEFAULT_SPACING_M
    return RUNWAY_CENTRELINE_LOW_VIS_SPACING_M


def approach_profile_for_runway(runway_type: str) -> Dict:
    """Return the approach lighting profile applicable to the given runway type.

    The returned dictionary comes from APPROACH_PROFILES.  If no matching
    profile exists, APPROACH_PROFILE_NONE is returned.  This helper uses
    keyword matching on the runway type string.
    """
    value = runway_type or ""
    for key, profile in APPROACH_PROFILES:
        if key in value:
            return profile
    # Non‑precision runways should fall back to simple SALS.
    if "Non-Precision" in value or "Non‑Precision" in value or "Non-Instrument" in value or "Non‑Instrument" in value:
        return APPROACH_PROFILES[2][1]  # Simple approach
    return APPROACH_PROFILE_NONE


def approach_profile_for_end(runway_type: str) -> Dict:
    """Return the approach lighting profile applicable to a runway end."""
    return approach_profile_for_runway(runway_type)


__all__ = [
    "agl_value",
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
