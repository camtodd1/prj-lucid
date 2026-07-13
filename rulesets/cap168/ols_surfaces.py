"""Source-loaded obstacle limitation parameters for UK CAA CAP 168 Chapter 4.

The constants in this module describe the current CAP 168 OLS that applies
until 20 November 2030.  They are deliberately separate from the geometry
constructor: CAP 168 bases the inner horizontal surface on the *lowest runway
threshold*, varies its plan form with main-runway length, and varies outer
horizontal applicability with actual runway length.  The existing generic OLS
constructor does not yet accept all of that context.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

from ..ols_utils import is_valid_arc_number, lookup_detached, normalize_surface_type
from .classification import get_runway_type_abbr

LOGGER = logging.getLogger(__name__)

SOURCE_PUBLICATION = "UK CAA CAP 168 Licensing of Aerodromes, Thirteenth Edition, July 2025"
SOURCE_APPLICABILITY_END = "2030-11-20"

# CAP 168 4.47.  The datum is material: this is not stated relative to RED.
IHS_HEIGHT_RULE: Dict[str, Any] = {
    "height_m": 45.0,
    "datum": "lowest_runway_threshold",
    "ref": "CAP 168 4.47",
}

# CAP 168 4.49-4.51.  The printed Code 2 NI radius of 250 m was confirmed by
# the user as a misprint for 2500 m on 13 July 2026.
IHS_PLAN_RULES: Dict[str, Any] = {
    "main_runway_at_least_1800_m": {
        "shape": "strip_end_racetrack",
        "radius": 4000.0,
        "ref": "CAP 168 4.49",
    },
    "main_runway_below_1800_m_default": {
        "shape": "runway_midpoint_circle",
        "radius": 4000.0,
        "ref": "CAP 168 4.50",
    },
    "main_runway_below_1800_m_ni_code_1": {
        "shape": "runway_midpoint_circle",
        "radius": 2000.0,
        "ref": "CAP 168 4.50",
    },
    "main_runway_below_1800_m_ni_code_2": {
        "shape": "runway_midpoint_circle",
        "radius": 2500.0,
        "printed_radius": 250.0,
        "correction_status": "user_confirmed",
        "correction_date": "2026-07-13",
        "ref": "CAP 168 4.50, printed page 240, supplied PDF page 17",
    },
    "subsidiary_runway_over_1800_m": {
        "shape": "strip_end_circle_joined_by_common_tangents",
        "radius": 3000.0,
        "proximity_trigger_m": 3000.0,
        "ref": "CAP 168 4.51",
    },
}

# Table 4.2.  The user confirmed on 13 July 2026 that the printed 6 m and
# 360 m values are misprints for 60 m and 3600 m.  The corrections also agree
# with 4.23, the 150 m instrument cap in 4.26 and the 15000 m section total.
APPROACH_PARAMS: Dict[Tuple[int, str], List[Dict[str, Any]]] = {
    (1, "NI"): [
        {
            "length": 1600.0,
            "slope": 0.05,
            "divergence": 0.10,
            "start_dist_from_thr": 30.0,
            "start_width": 60.0,
            "ref": "CAP 168 4.23-4.26 Table 4.2 (NI-1)",
        }
    ],
    (2, "NI"): [
        {
            "length": 2500.0,
            "slope": 0.04,
            "divergence": 0.10,
            "start_dist_from_thr": 60.0,
            "start_width": 80.0,
            "ref": "CAP 168 4.23-4.26 Table 4.2 (NI-2)",
        }
    ],
    (3, "NI"): [
        {
            "length": 3000.0,
            "slope": 0.0333,
            "divergence": 0.10,
            "start_dist_from_thr": 60.0,
            "start_width": 150.0,
            "ref": "CAP 168 4.23-4.26 Table 4.2 (NI-3)",
        }
    ],
    (4, "NI"): [
        {
            "length": 3000.0,
            "slope": 0.025,
            "divergence": 0.10,
            "start_dist_from_thr": 60.0,
            "start_width": 150.0,
            "ref": "CAP 168 4.23-4.26 Table 4.2 (NI-4)",
        }
    ],
    (1, "NPA"): [
        {
            "length": 2500.0,
            "slope": 0.0333,
            "divergence": 0.15,
            "start_dist_from_thr": 60.0,
            "start_width": 140.0,
            "ref": "CAP 168 4.23-4.26 Table 4.2 (NPA-1/2)",
        }
    ],
    (2, "NPA"): [
        {
            "length": 2500.0,
            "slope": 0.0333,
            "divergence": 0.15,
            "start_dist_from_thr": 60.0,
            "start_width": 140.0,
            "ref": "CAP 168 4.23-4.26 Table 4.2 (NPA-1/2)",
        }
    ],
    (3, "NPA"): [
        {
            "length": 3000.0,
            "slope": 0.02,
            "divergence": 0.15,
            "start_dist_from_thr": 60.0,
            "start_width": 280.0,
            "ref": "CAP 168 4.23-4.26 Table 4.2 (NPA-3/4 S1)",
        },
        {
            "length": 3600.0,
            "slope": 0.025,
            "divergence": 0.15,
            "ref": "CAP 168 4.26 Table 4.2 (NPA-3/4 S2)",
        },
        {"length": 8400.0, "slope": 0.0, "divergence": 0.15, "ref": "CAP 168 4.26 Table 4.2 (NPA-3/4 horizontal)"},
    ],
    (4, "NPA"): [
        {
            "length": 3000.0,
            "slope": 0.02,
            "divergence": 0.15,
            "start_dist_from_thr": 60.0,
            "start_width": 280.0,
            "ref": "CAP 168 4.23-4.26 Table 4.2 (NPA-3/4 S1)",
        },
        {
            "length": 3600.0,
            "slope": 0.025,
            "divergence": 0.15,
            "ref": "CAP 168 4.26 Table 4.2 (NPA-3/4 S2)",
        },
        {"length": 8400.0, "slope": 0.0, "divergence": 0.15, "ref": "CAP 168 4.26 Table 4.2 (NPA-3/4 horizontal)"},
    ],
    (1, "PA_I"): [
        {
            "length": 3000.0,
            "slope": 0.025,
            "divergence": 0.15,
            "start_dist_from_thr": 60.0,
            "start_width": 140.0,
            "ref": "CAP 168 4.23-4.26 Table 4.2 (PA-1/2 S1)",
        },
        {"length": 2500.0, "slope": 0.03, "divergence": 0.15, "ref": "CAP 168 4.26 Table 4.2 (PA-1/2 S2)"},
        {"length": 9500.0, "slope": 0.0, "divergence": 0.15, "ref": "CAP 168 4.26 Table 4.2 (PA-1/2 horizontal)"},
    ],
    (2, "PA_I"): [
        {
            "length": 3000.0,
            "slope": 0.025,
            "divergence": 0.15,
            "start_dist_from_thr": 60.0,
            "start_width": 140.0,
            "ref": "CAP 168 4.23-4.26 Table 4.2 (PA-1/2 S1)",
        },
        {"length": 2500.0, "slope": 0.03, "divergence": 0.15, "ref": "CAP 168 4.26 Table 4.2 (PA-1/2 S2)"},
        {"length": 9500.0, "slope": 0.0, "divergence": 0.15, "ref": "CAP 168 4.26 Table 4.2 (PA-1/2 horizontal)"},
    ],
}

for _runway_type in ("PA_I", "PA_II_III"):
    for _code in (3, 4):
        APPROACH_PARAMS[(_code, _runway_type)] = [
            {
                "length": 3000.0,
                "slope": 0.02,
                "divergence": 0.15,
                "start_dist_from_thr": 60.0,
                "start_width": 280.0,
                "ref": "CAP 168 4.23-4.26 Table 4.2 (PA-3/4 S1; corrected 60 m)",
            },
            {
                "length": 3600.0,
                "slope": 0.025,
                "divergence": 0.15,
                "ref": "CAP 168 4.26 Table 4.2 (PA-3/4 S2; corrected 3600 m)",
            },
            {"length": 8400.0, "slope": 0.0, "divergence": 0.15, "ref": "CAP 168 4.26 Table 4.2 (PA-3/4 horizontal)"},
        ]

# Table 4.1.  The normal final width is 1200 m for Codes 3/4; 1800 m
# applies only when the intended track changes heading by more than 15 degrees.
TOCS_PARAMS: Dict[int, Dict[str, Any]] = {
    1: {
        "inner_edge_width": 60.0,
        "clearway_inner_edge_width": 150.0,
        "origin_offset": 30.0,
        "divergence": 0.10,
        "final_width": 380.0,
        "length": 1600.0,
        "slope": 0.05,
        "ref": "CAP 168 4.8-4.20 Table 4.1 (Code 1)",
    },
    2: {
        "inner_edge_width": 80.0,
        "clearway_inner_edge_width": 150.0,
        "origin_offset": 60.0,
        "divergence": 0.10,
        "final_width": 580.0,
        "length": 2500.0,
        "slope": 0.04,
        "ref": "CAP 168 4.8-4.20 Table 4.1 (Code 2)",
    },
    3: {
        "inner_edge_width": 180.0,
        "origin_offset": 60.0,
        "divergence": 0.125,
        "final_width": 1200.0,
        "heading_change_gt_15_final_width": 1800.0,
        "length": 15000.0,
        "slope": 0.02,
        "ref": "CAP 168 4.8-4.20 Table 4.1 (Code 3/4)",
    },
    4: {
        "inner_edge_width": 180.0,
        "origin_offset": 60.0,
        "divergence": 0.125,
        "final_width": 1200.0,
        "heading_change_gt_15_final_width": 1800.0,
        "length": 15000.0,
        "slope": 0.02,
        "ref": "CAP 168 4.8-4.20 Table 4.1 (Code 3/4)",
    },
}

TAKE_OFF_CLIMB_CONSTRUCTION_RULES: Dict[str, Any] = {
    "inner_edge_station_rule": "max(clearway_end,tora_plus_code_offset)",
    "inner_edge_elevation_rule": "clearway_end_or_runway_centreline_at_inner_edge",
    "code_3_4_reduced_slope_floor": 0.016,
    "code_3_4_reduced_slope_rule": "first_immovable_object_or_1_6_percent_whichever_steeper",
    "reduced_slope_protection_height_ft": 1000.0,
    "maximum_edge_slew_degrees": 15.0,
    "wide_runway_minimum_width_ratio": 1.10,
    "wide_runway_inner_edge_rule": "not_less_than_strip_width_then_parallel_to_normal_diverging_sides",
    "ref": "CAP 168 4.10-4.20",
}

APPROACH_CONSTRUCTION_RULES: Dict[str, Any] = {
    "inner_edge_elevation_datum": "landing_threshold_midpoint",
    "instrument_horizontal_height_above_threshold_m": 150.0,
    "wide_runway_minimum_width_ratio": 1.10,
    "wide_runway_inner_edge_rule": "not_less_than_strip_width_then_parallel_to_normal_diverging_sides",
    "offset_or_curved_approach_rule": "diverge_from_extended_lateral_offset_or_curved_ground_track",
    "ref": "CAP 168 4.23-4.27",
}

TRANSITIONAL_PARAMS: Dict[Tuple[int, str], Dict[str, Any]] = {}
for _code in (1, 2, 3, 4):
    for _runway_type in ("NI", "NPA", "PA_I", "PA_II_III"):
        _slope = 0.20 if _code in (1, 2) and _runway_type in ("NI", "NPA") else 0.143
        TRANSITIONAL_PARAMS[(_code, _runway_type)] = {"slope": _slope, "ref": "CAP 168 4.34-4.39, especially 4.36"}

# OFZ components from 4.59-4.73.  CAP 168 describes the inner approach as a
# rectangular portion of the instrument approach surface, hence its slope is
# the corresponding first-section approach slope.
INNER_APPROACH_PARAMS: Dict[Tuple[int, str], Dict[str, Any]] = {
    (1, "PA_I"): {
        "width": 90.0,
        "start_dist_from_thr": 60.0,
        "length": 1500.0,
        "slope": 0.025,
        "ref": "CAP 168 4.59-4.62, 4.72",
    },
    (2, "PA_I"): {
        "width": 90.0,
        "start_dist_from_thr": 60.0,
        "length": 1500.0,
        "slope": 0.025,
        "ref": "CAP 168 4.59-4.62, 4.72",
    },
    (3, "PA_I"): {
        "width": 120.0,
        "start_dist_from_thr": 60.0,
        "length": 1500.0,
        "slope": 0.02,
        "code_letter_f_width": 140.0,
        "ref": "CAP 168 4.59-4.62, 4.70",
    },
    (4, "PA_I"): {
        "width": 120.0,
        "start_dist_from_thr": 60.0,
        "length": 1500.0,
        "slope": 0.02,
        "code_letter_f_width": 140.0,
        "ref": "CAP 168 4.59-4.62, 4.70",
    },
    (3, "PA_II_III"): {
        "width": 120.0,
        "start_dist_from_thr": 60.0,
        "length": 1500.0,
        "slope": 0.02,
        "code_letter_f_width": 140.0,
        "ref": "CAP 168 4.59-4.62, 4.70",
    },
    (4, "PA_II_III"): {
        "width": 120.0,
        "start_dist_from_thr": 60.0,
        "length": 1500.0,
        "slope": 0.02,
        "code_letter_f_width": 140.0,
        "ref": "CAP 168 4.59-4.62, 4.70",
    },
}

INNER_TRANSITIONAL_PARAMS: Dict[Tuple[int, str], Dict[str, Any]] = {
    (1, "PA_I"): {"slope": 0.40, "ref": "CAP 168 4.72-4.73"},
    (2, "PA_I"): {"slope": 0.40, "ref": "CAP 168 4.72-4.73"},
    (3, "PA_I"): {"slope": 0.333, "ref": "CAP 168 4.70-4.71"},
    (4, "PA_I"): {"slope": 0.333, "ref": "CAP 168 4.70-4.71"},
    (3, "PA_II_III"): {"slope": 0.333, "ref": "CAP 168 4.70-4.71"},
    (4, "PA_II_III"): {"slope": 0.333, "ref": "CAP 168 4.70-4.71"},
}

BAULKED_LANDING_PARAMS: Dict[Tuple[int, str], Dict[str, Any]] = {
    (1, "PA_I"): {
        "width": 90.0,
        "start_dist_from_thr": None,
        "start_dist_rule": "60_m_beyond_lda",
        "divergence": 0.10,
        "slope": 0.04,
        "ref": "CAP 168 4.72-4.73",
    },
    (2, "PA_I"): {
        "width": 90.0,
        "start_dist_from_thr": None,
        "start_dist_rule": "60_m_beyond_lda",
        "divergence": 0.10,
        "slope": 0.04,
        "ref": "CAP 168 4.72-4.73",
    },
    (3, "PA_I"): {
        "width": 120.0,
        "start_dist_from_thr": 1800.0,
        "divergence": 0.10,
        "slope": 0.0333,
        "code_letter_f_width": 140.0,
        "ref": "CAP 168 4.70-4.71",
    },
    (4, "PA_I"): {
        "width": 120.0,
        "start_dist_from_thr": 1800.0,
        "divergence": 0.10,
        "slope": 0.0333,
        "code_letter_f_width": 140.0,
        "ref": "CAP 168 4.70-4.71",
    },
    (3, "PA_II_III"): {
        "width": 120.0,
        "start_dist_from_thr": 1800.0,
        "divergence": 0.10,
        "slope": 0.0333,
        "code_letter_f_width": 140.0,
        "ref": "CAP 168 4.70-4.71",
    },
    (4, "PA_II_III"): {
        "width": 120.0,
        "start_dist_from_thr": 1800.0,
        "divergence": 0.10,
        "slope": 0.0333,
        "code_letter_f_width": 140.0,
        "ref": "CAP 168 4.70-4.71",
    },
}

OFZ_APPLICABILITY_RULES: Dict[str, Any] = {
    "precision_cat_ii_iii": "shall_establish_and_maintain_during_operations",
    "precision_cat_i": "should_establish_and_maintain_during_operations",
    "code_3_4_design_wingspan_m": 60.0,
    "code_1_2_design_wingspan_m": 30.0,
    "ref": "CAP 168 4.62-4.73, especially 4.64, 4.68 and 4.69",
}

CONICAL_RULES: Dict[str, Any] = {
    "slope": 0.05,
    "default_height_extent_above_ihs_m": 105.0,
    "ni_code_2_height_extent_above_ihs_m": 55.0,
    "ni_code_1_height_extent_above_ihs_m": 35.0,
    "ref": "CAP 168 4.53-4.55",
}

OUTER_HORIZONTAL_RULES: Dict[str, Any] = {
    "minimum_main_runway_length_m": 1100.0,
    "radius_if_main_runway_at_least_1860_m": 15000.0,
    "radius_if_main_runway_1100_to_below_1860_m": 10000.0,
    "ref": "CAP 168 4.56-4.58",
}


def get_ihs_base_height() -> float:
    """Return the sourced 45 m height; callers must honour its threshold datum."""

    return float(IHS_HEIGHT_RULE["height_m"])


def _ofz_params(mapping: Dict[Tuple[int, str], Dict[str, Any]], key: Tuple[int, str]):
    return lookup_detached(mapping, key)


def get_ols_params(arc_num: int, runway_type_str: Optional[str], surface_type: str):
    """Return source-loaded parameters that fit the existing lookup contract.

    Airport-wide IHS/conical/OHS plan parameters are intentionally not exposed
    through this legacy lookup because the constructor needs runway-length and
    threshold-datum inputs first.  Their complete source rules remain available
    above for the forthcoming constructor adaptation.
    """

    if not is_valid_arc_number(arc_num):
        LOGGER.warning("Invalid ARC Number %r for CAP 168 OLS lookup.", arc_num)
        return None
    runway_type = get_runway_type_abbr(runway_type_str)
    key = (arc_num, runway_type)
    surface = normalize_surface_type(surface_type)

    if surface in {"APPROACH", "APPROACHSURFACE"}:
        return lookup_detached(APPROACH_PARAMS, key)
    if surface in {"TOCS", "TAKEOFFCLIMB", "TAKEOFFCLIMBSURFACE"}:
        return lookup_detached(TOCS_PARAMS, arc_num)
    if surface in {"TRANSITIONAL", "TRANSITIONALSURFACE"}:
        return lookup_detached(TRANSITIONAL_PARAMS, key)
    if surface in {"INNERAPPROACH", "INNERAPPROACHSURFACE"}:
        return _ofz_params(INNER_APPROACH_PARAMS, key)
    if surface in {"INNERTRANSITIONAL", "INNERTRANSITIONALSURFACE"}:
        return _ofz_params(INNER_TRANSITIONAL_PARAMS, key)
    if surface in {"BALKEDLANDING", "BALKEDLANDINGSURFACE", "BAULKEDLANDING", "BAULKEDLANDINGSURFACE"}:
        return _ofz_params(BAULKED_LANDING_PARAMS, key)
    if surface in {
        "IHS",
        "INNERHORIZONTAL",
        "INNERHORIZONTALSURFACE",
        "CONICAL",
        "CONICALSURFACE",
        "OHS",
        "OUTERHORIZONTAL",
        "OUTERHORIZONTALSURFACE",
    }:
        LOGGER.warning("CAP 168 %s requires constructor context not present in the legacy OLS lookup.", surface)
        return None
    LOGGER.warning("Unknown CAP 168 OLS surface type %r requested.", surface_type)
    return None


__all__ = [
    "APPROACH_PARAMS",
    "APPROACH_CONSTRUCTION_RULES",
    "BAULKED_LANDING_PARAMS",
    "CONICAL_RULES",
    "IHS_HEIGHT_RULE",
    "IHS_PLAN_RULES",
    "INNER_APPROACH_PARAMS",
    "INNER_TRANSITIONAL_PARAMS",
    "OUTER_HORIZONTAL_RULES",
    "OFZ_APPLICABILITY_RULES",
    "SOURCE_APPLICABILITY_END",
    "SOURCE_PUBLICATION",
    "TOCS_PARAMS",
    "TAKE_OFF_CLIMB_CONSTRUCTION_RULES",
    "TRANSITIONAL_PARAMS",
    "get_ihs_base_height",
    "get_ols_params",
]
