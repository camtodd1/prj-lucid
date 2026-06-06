"""Obstacle evaluation surface lookups for ICAO Annex 14 Volume I."""

from copy import deepcopy
from typing import Iterable, Optional

OES_STATUS = "partial"

HORIZONTAL_SURFACE_REF = "Annex 14 Vol I 4.3.2"
HORIZONTAL_SURFACE_TABLE_REF = "Annex 14 Vol I Table 4-10"
STRAIGHT_IN_INSTRUMENT_REF = "Annex 14 Vol I 4.3.3"
STRAIGHT_IN_INSTRUMENT_TABLE_REF = "Annex 14 Vol I Table 4-11"
PRECISION_APPROACH_REF = "Annex 14 Vol I 4.3.4"
PRECISION_APPROACH_TABLE_REF = "Annex 14 Vol I Table 4-12"
INSTRUMENT_DEPARTURE_REF = "Annex 14 Vol I 4.3.5"
INSTRUMENT_DEPARTURE_TABLE_REF = "Annex 14 Vol I Table 4-13"

HORIZONTAL_SURFACE = {
    "I-IIA": {
        "radius_m": 3350.0,
        "height_above_aerodrome_elevation_m": 45.0,
        "ref": HORIZONTAL_SURFACE_TABLE_REF,
    },
    "IIB": {
        "radius_m": 5350.0,
        "height_above_aerodrome_elevation_m": 60.0,
        "ref": HORIZONTAL_SURFACE_TABLE_REF,
    },
    "IIC": {
        "radius_m": 10750.0,
        "height_above_aerodrome_elevation_m": 90.0,
        "ref": HORIZONTAL_SURFACE_TABLE_REF,
    },
    "III": {
        "radius_m": 10750.0,
        "height_above_aerodrome_elevation_m": 90.0,
        "ref": HORIZONTAL_SURFACE_TABLE_REF,
    },
    "IV": {
        "radius_m": 10750.0,
        "height_above_aerodrome_elevation_m": 90.0,
        "ref": HORIZONTAL_SURFACE_TABLE_REF,
    },
    "V": {
        "radius_m": 10750.0,
        "height_above_aerodrome_elevation_m": 90.0,
        "ref": HORIZONTAL_SURFACE_TABLE_REF,
    },
}

STRAIGHT_IN_INSTRUMENT_SURFACE = {
    "surface": "straight_in_instrument_approach",
    "family": "obstacle_evaluation_surfaces",
    "section_ref": STRAIGHT_IN_INSTRUMENT_REF,
    "ref": STRAIGHT_IN_INSTRUMENT_TABLE_REF,
    "applicable_design_groups": "I to V",
    "lower_section": {
        "height_above_aerodrome_elevation_m": 45.0,
        "length_rule": "horizontal_oes_as_per_adg_i",
        "horizontal_surface_design_group": "I-IIA",
    },
    "upper_section": {
        "height_above_aerodrome_elevation_m": 60.0,
        "shorter_side_length_m": 7410.0,
        "longer_side_length_from_threshold_or_thresholds_m": 5350.0,
    },
}

PRECISION_APPROACH_SURFACE = {
    "surface": "precision_approach",
    "family": "obstacle_evaluation_surfaces",
    "section_ref": PRECISION_APPROACH_REF,
    "ref": PRECISION_APPROACH_TABLE_REF,
    "applicable_design_groups": "I to V",
    "components": {
        "approach": {
            "inner_edge_elevation": "threshold_midpoint",
            "distance_from_threshold_m": 60.0,
            "inner_edge_length_m": 300.0,
            "sections": [
                {
                    "section": "first",
                    "length_m": 3000.0,
                    "divergence": 0.15,
                    "slope": 0.02,
                },
                {
                    "section": "second",
                    "length_m": 9600.0,
                    "divergence": 0.15,
                    "slope": 0.025,
                },
            ],
            "slope_measurement": "runway_centreline_vertical_plane",
        },
        "missed_approach": {
            "inner_edge_elevation": "threshold_midpoint",
            "distance_after_threshold_m": 900.0,
            "inner_edge_length_m": 300.0,
            "sections": [
                {
                    "section": "first",
                    "length_m": 1800.0,
                    "divergence": 0.1748,
                    "slope": 0.025,
                },
                {
                    "section": "second",
                    "length_m": 10200.0,
                    "divergence": 0.25,
                    "slope": 0.025,
                },
            ],
            "slope_measurement": "runway_centreline_vertical_plane",
        },
        "transitional": {
            "count": 2,
            "slope": 0.143,
            "upper_edge_height_above_threshold_m": 300.0,
            "lower_edge_rule": "follows_approach_lower_component_and_missed_approach",
            "slope_measurement": "perpendicular_to_runway_centreline",
        },
        "lower": {
            "shape": "rectangle",
            "elevation": "threshold_midpoint",
            "shorter_sides": "approach_and_missed_approach_inner_edges",
            "longer_sides": "inner_edges_of_transitional_components",
        },
    },
}

INSTRUMENT_DEPARTURE_SURFACE = {
    "surface": "instrument_departure",
    "family": "obstacle_evaluation_surfaces",
    "section_ref": INSTRUMENT_DEPARTURE_REF,
    "ref": INSTRUMENT_DEPARTURE_TABLE_REF,
    "applicable_design_groups": "I to V",
    "inner_edge_location": "end_of_takeoff_distance_available",
    "inner_edge_elevation": "5_m_above_runway_centreline_at_end_of_toda",
    "inner_edge_elevation_offset_m": 5.0,
    "inner_edge_length_m": 300.0,
    "slope": 0.025,
    "slope_measurement": "runway_centreline_vertical_plane",
    "sections": [
        {
            "section": "first",
            "length_m": 3500.0,
            "divergence": 0.268,
        },
        {
            "section": "second",
            "length_m": 8300.0,
            "divergence": 0.578,
        },
    ],
}


def _normalize_surface_type(surface_type: Optional[str]) -> str:
    return (surface_type or "").strip().replace("_", " ").replace("-", " ").lower()


def _normalize_design_group(design_group: Optional[str]):
    if design_group is None:
        return None
    value = str(design_group).strip().upper().replace("ADG", "").replace("_", "").replace(" ", "")
    if value in {"I", "IIA"}:
        return "I-IIA"
    return value or None


def surface_families() -> tuple:
    return (
        "horizontal",
        "straight_in_instrument_approach",
        "precision_approach",
        "instrument_departure",
    )


def horizontal_surface_parameters(design_group: Optional[str]):
    """Return Annex 14 horizontal surface parameters from Table 4-10."""
    normalized_design_group = _normalize_design_group(design_group)
    if normalized_design_group is None:
        return None
    base_params = HORIZONTAL_SURFACE.get(normalized_design_group)
    if base_params is None:
        return None

    params = deepcopy(base_params)
    params["surface"] = "horizontal"
    params["family"] = "obstacle_evaluation_surfaces"
    params["section_ref"] = HORIZONTAL_SURFACE_REF
    params["design_group"] = normalized_design_group
    params["outer_limits_rule"] = "circular_arcs_centred_on_runway_thresholds_joined_tangentially_by_straight_lines"
    params["height_datum"] = "aerodrome_elevation"
    return params


def horizontal_surfaces(design_groups: Iterable[str]):
    """Return retained horizontal surfaces for all supplied ADGs."""
    retained = []
    seen = set()
    for design_group in design_groups or ():
        params = horizontal_surface_parameters(design_group)
        if params is None:
            continue
        key = params["design_group"]
        if key in seen:
            continue
        retained.append(params)
        seen.add(key)
    return {
        "surface": "horizontal",
        "family": "obstacle_evaluation_surfaces",
        "section_ref": HORIZONTAL_SURFACE_REF,
        "composition_rule": "retain_all_horizontal_surfaces_for_runways_intended_for_multiple_adgs",
        "surfaces": retained,
    }


def straight_in_instrument_approach_surface_parameters():
    """Return Annex 14 straight-in instrument approach OES parameters from Table 4-11."""
    params = deepcopy(STRAIGHT_IN_INSTRUMENT_SURFACE)
    params["lower_section"]["horizontal_surface"] = horizontal_surface_parameters("I")
    return params


def precision_approach_surface_parameters():
    """Return Annex 14 precision approach OES parameters from Table 4-12."""
    return deepcopy(PRECISION_APPROACH_SURFACE)


def instrument_departure_surface_parameters():
    """Return Annex 14 instrument departure OES parameters from Table 4-13."""
    return deepcopy(INSTRUMENT_DEPARTURE_SURFACE)


def parameters(
    design_group: Optional[str] = None,
    runway_type: Optional[str] = None,
    operation_type: Optional[str] = None,
    surface_type: Optional[str] = None,
):
    normalized_surface_type = _normalize_surface_type(surface_type)
    if normalized_surface_type == "horizontal":
        return horizontal_surface_parameters(design_group)
    if normalized_surface_type in {
        "straight in instrument approach",
        "straight in instrument",
        "straight in",
        "instrument approach",
    }:
        return straight_in_instrument_approach_surface_parameters()
    if normalized_surface_type in {
        "precision approach",
        "precision",
        "precision approach surface",
    }:
        return precision_approach_surface_parameters()
    if normalized_surface_type in {
        "instrument departure",
        "departure",
        "instrument departure surface",
    }:
        return instrument_departure_surface_parameters()
    return None


__all__ = [
    "OES_STATUS",
    "HORIZONTAL_SURFACE_REF",
    "HORIZONTAL_SURFACE_TABLE_REF",
    "STRAIGHT_IN_INSTRUMENT_REF",
    "STRAIGHT_IN_INSTRUMENT_TABLE_REF",
    "PRECISION_APPROACH_REF",
    "PRECISION_APPROACH_TABLE_REF",
    "INSTRUMENT_DEPARTURE_REF",
    "INSTRUMENT_DEPARTURE_TABLE_REF",
    "HORIZONTAL_SURFACE",
    "STRAIGHT_IN_INSTRUMENT_SURFACE",
    "PRECISION_APPROACH_SURFACE",
    "INSTRUMENT_DEPARTURE_SURFACE",
    "surface_families",
    "horizontal_surface_parameters",
    "horizontal_surfaces",
    "straight_in_instrument_approach_surface_parameters",
    "precision_approach_surface_parameters",
    "instrument_departure_surface_parameters",
    "parameters",
]
