# -*- coding: utf-8 -*-
"""Shared constants for NASF guideline and safeguarding surface generation."""

GUIDELINE_B_FAR_EDGE_OFFSET = 500.0
GUIDELINE_B_ZONE_LENGTH_BACKWARD = 1400.0
GUIDELINE_B_ZONE_HALF_WIDTH = 1200.0

GUIDELINE_C_RADIUS_A_M = 3000.0
GUIDELINE_C_RADIUS_B_M = 8000.0
GUIDELINE_C_RADIUS_C_M = 13000.0
GUIDELINE_C_BUFFER_SEGMENTS = 144

GUIDELINE_D_TURBINE_RADIUS_M = 30000.0
GUIDELINE_D_BUFFER_SEGMENTS = 144

LAYER_FEATURE_BATCH_SIZE = 100

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
MOS_REF_GUIDELINE_E = "MOS 9.144(2)"
NASF_REF_GUIDELINE_E = "NASF Guideline E"

GUIDELINE_I_PSA_LENGTH = 1000.0
GUIDELINE_I_PSA_INNER_WIDTH = 350.0
GUIDELINE_I_PSA_OUTER_WIDTH = 250.0
GUIDELINE_I_MOS_REF_VAL = "n/a"
GUIDELINE_I_NASF_REF_VAL = "NASF Guideline I"

RAOA_MOS_REF_VAL = "MOS 6.20"
MOS_REF_TAXIWAY_SEPARATION = "MOS 6.53"

CONICAL_CONTOUR_INTERVAL = 10.0
APPROACH_CONTOUR_INTERVAL = 10.0
TOCS_CONTOUR_INTERVAL = 10.0
TRANSITIONAL_CONTOUR_INTERVAL = 10.0
