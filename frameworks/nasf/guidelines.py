# -*- coding: utf-8 -*-
"""NASF planning and safeguarding guideline parameters."""

GUIDELINE_B_FAR_EDGE_OFFSET = 500.0
GUIDELINE_B_ZONE_LENGTH_BACKWARD = 1400.0
GUIDELINE_B_ZONE_HALF_WIDTH = 1200.0
GUIDELINE_B_NASF_REF = "NASF Guideline B"

GUIDELINE_C_RADIUS_A_M = 3000.0
GUIDELINE_C_RADIUS_B_M = 8000.0
GUIDELINE_C_RADIUS_C_M = 13000.0
GUIDELINE_C_BUFFER_SEGMENTS = 144
GUIDELINE_C_MOS_REF = "MOS 17.01(2)"
GUIDELINE_C_NASF_REF = "NASF Guideline C"

GUIDELINE_D_TURBINE_RADIUS_M = 30000.0
GUIDELINE_D_BUFFER_SEGMENTS = 144
GUIDELINE_D_NASF_REF = "NASF Guideline D"

GUIDELINE_E_ZONE_PARAMS = {
    "A": {
        "ext": 1000.0,
        "half_w": 300.0,
        "desc": "Lighting Control Zone A",
        "max_intensity": "0cd",
    },
    "B": {
        "ext": 2000.0,
        "half_w": 450.0,
        "desc": "Lighting Control Zone B",
        "max_intensity": "50cd",
    },
    "C": {
        "ext": 3000.0,
        "half_w": 600.0,
        "desc": "Lighting Control Zone C",
        "max_intensity": "150cd",
    },
    "D": {
        "ext": 4500.0,
        "half_w": 750.0,
        "desc": "Lighting Control Zone D",
        "max_intensity": "450cd",
    },
}
GUIDELINE_E_ZONE_ORDER = ["A", "B", "C", "D"]
GUIDELINE_E_AREA_RADIUS_M = 6000.0
MOS_REF_GUIDELINE_E = "MOS 9.144(2)"
NASF_REF_GUIDELINE_E = "NASF Guideline E"

GUIDELINE_I_PSA_LENGTH = 1000.0
GUIDELINE_I_PSA_INNER_WIDTH = 350.0
GUIDELINE_I_PSA_OUTER_WIDTH = 250.0
GUIDELINE_I_MOS_REF_VAL = "n/a"
GUIDELINE_I_NASF_REF_VAL = "NASF Guideline I"


def windshear_parameters() -> dict:
    """Return NASF Guideline B windshear assessment zone parameters."""
    return {
        "far_edge_offset": GUIDELINE_B_FAR_EDGE_OFFSET,
        "zone_length_backward": GUIDELINE_B_ZONE_LENGTH_BACKWARD,
        "zone_half_width": GUIDELINE_B_ZONE_HALF_WIDTH,
        "ref_nasf": GUIDELINE_B_NASF_REF,
    }


def wildlife_parameters() -> dict:
    """Return NASF Guideline C wildlife management zone parameters."""
    return {
        "radius_a_m": GUIDELINE_C_RADIUS_A_M,
        "radius_b_m": GUIDELINE_C_RADIUS_B_M,
        "radius_c_m": GUIDELINE_C_RADIUS_C_M,
        "buffer_segments": GUIDELINE_C_BUFFER_SEGMENTS,
        "ref_mos": GUIDELINE_C_MOS_REF,
        "ref_nasf": GUIDELINE_C_NASF_REF,
    }


def wind_turbine_parameters() -> dict:
    """Return NASF Guideline D wind turbine assessment zone parameters."""
    return {
        "radius_m": GUIDELINE_D_TURBINE_RADIUS_M,
        "buffer_segments": GUIDELINE_D_BUFFER_SEGMENTS,
        "ref_nasf": GUIDELINE_D_NASF_REF,
    }


def lighting_control_parameters() -> dict:
    """Return NASF Guideline E lighting control zone parameters."""
    return {
        "zones": GUIDELINE_E_ZONE_PARAMS,
        "zone_order": GUIDELINE_E_ZONE_ORDER,
        "area_radius_m": GUIDELINE_E_AREA_RADIUS_M,
        "buffer_segments": GUIDELINE_C_BUFFER_SEGMENTS,
        "mos_ref": MOS_REF_GUIDELINE_E,
        "nasf_ref": NASF_REF_GUIDELINE_E,
    }


def public_safety_area_parameters() -> dict:
    """Return NASF Guideline I public safety area parameters."""
    return {
        "length": GUIDELINE_I_PSA_LENGTH,
        "inner_width": GUIDELINE_I_PSA_INNER_WIDTH,
        "outer_width": GUIDELINE_I_PSA_OUTER_WIDTH,
        "mos_ref": GUIDELINE_I_MOS_REF_VAL,
        "nasf_ref": GUIDELINE_I_NASF_REF_VAL,
    }


__all__ = [
    "GUIDELINE_B_FAR_EDGE_OFFSET",
    "GUIDELINE_B_ZONE_HALF_WIDTH",
    "GUIDELINE_B_ZONE_LENGTH_BACKWARD",
    "GUIDELINE_C_BUFFER_SEGMENTS",
    "GUIDELINE_C_RADIUS_A_M",
    "GUIDELINE_C_RADIUS_B_M",
    "GUIDELINE_C_RADIUS_C_M",
    "GUIDELINE_D_BUFFER_SEGMENTS",
    "GUIDELINE_D_TURBINE_RADIUS_M",
    "GUIDELINE_E_ZONE_ORDER",
    "GUIDELINE_E_ZONE_PARAMS",
    "GUIDELINE_I_MOS_REF_VAL",
    "GUIDELINE_I_NASF_REF_VAL",
    "GUIDELINE_I_PSA_INNER_WIDTH",
    "GUIDELINE_I_PSA_LENGTH",
    "GUIDELINE_I_PSA_OUTER_WIDTH",
    "MOS_REF_GUIDELINE_E",
    "NASF_REF_GUIDELINE_E",
]
