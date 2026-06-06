"""Obstacle limitation requirements for ICAO Annex 14 Volume I."""

from copy import deepcopy
from typing import Optional

OBSTACLE_LIMITATION_REF = "Annex 14 Vol I 4.4"
SURFACE_ESTABLISHMENT_REF = "Annex 14 Vol I 4.5"

OBSTACLE_FREE_SURFACE_REQUIREMENTS = {
    "family": "obstacle_free_surfaces",
    "section_ref": "Annex 14 Vol I 4.4.1-4.4.7",
    "inner_surfaces": {
        "surfaces": [
            "inner_approach",
            "inner_transitional",
            "balked_landing",
            "complex_surface_between_inner_transitional_lower_edges",
        ],
        "fixed_objects": {
            "rule": "not_permitted_above_surface",
            "exceptions": ["visual_aids_required_for_air_navigation", "objects_required_for_aircraft_safety"],
            "ref": "Annex 14 Vol I 4.4.1",
        },
        "permitted_objects": {
            "requirements": ["frangible", "mounted_as_low_as_possible"],
            "ref": "Annex 14 Vol I 4.4.2",
        },
        "mobile_objects": {
            "rule": "not_permitted_above_surface_during_runway_use_for_landing",
            "ref": "Annex 14 Vol I 4.4.3",
        },
    },
    "general_surfaces": {
        "surfaces": [
            "approach",
            "transitional",
            "complex_surface_between_transitional_lower_edges",
        ],
        "new_objects_or_extensions": {
            "rule": "not_permitted_above_surface",
            "exceptions": ["air_navigation_equipment", "aircraft_safety_equipment_or_installations"],
            "ref": "Annex 14 Vol I 4.4.4",
        },
        "permitted_objects": {
            "requirements": ["frangible", "mounted_as_low_as_possible"],
            "ref": "Annex 14 Vol I 4.4.5",
        },
        "existing_obstacles": {
            "recommendation": "remove_as_far_as_practicable",
            "retention_rule": "permitted_only_after_aeronautical_study",
            "ref": "Annex 14 Vol I 4.4.6-4.4.7",
        },
    },
}

OBSTACLE_EVALUATION_SURFACE_REQUIREMENTS = {
    "family": "obstacle_evaluation_surfaces",
    "section_ref": "Annex 14 Vol I 4.4.8",
    "penetrating_obstacles": {
        "rule": "permitted_only_after_aeronautical_study",
        "study_outcome": "must_not_adversely_affect_safety_or_significantly_affect_regularity",
        "ref": "Annex 14 Vol I 4.4.8",
    },
}

OBSTACLE_FREE_SURFACE_ESTABLISHMENT = {
    "family": "obstacle_free_surfaces",
    "section_ref": "Annex 14 Vol I 4.5.1",
    "non_instrument": {
        "runway_type_abbr": "NI",
        "surfaces": ["approach", "transitional", "inner_approach", "inner_transitional"],
        "ref": "Annex 14 Vol I 4.5.1.1",
    },
    "non_precision": {
        "runway_type_abbr": "NPA",
        "surfaces": ["approach", "transitional", "inner_approach", "inner_transitional"],
        "ref": "Annex 14 Vol I 4.5.1.1",
    },
    "precision": {
        "runway_type_abbr": "PA",
        "surfaces": ["approach", "transitional", "inner_approach", "inner_transitional", "balked_landing"],
        "ref": "Annex 14 Vol I 4.5.1.2",
    },
}

OBSTACLE_EVALUATION_SURFACE_ESTABLISHMENT = {
    "family": "obstacle_evaluation_surfaces",
    "section_ref": "Annex 14 Vol I 4.5.2",
    "operations": {
        "circling_approach_or_visual_circuits": {
            "surfaces": ["horizontal", "specific_oes"],
            "ref": "Annex 14 Vol I 4.5.2.1(a)",
        },
        "straight_in_instrument_non_precision_without_horizontal_surface": {
            "surfaces": ["straight_in_instrument_approach", "specific_oes"],
            "ref": "Annex 14 Vol I 4.5.2.1(b)",
        },
        "precision_approach": {
            "surfaces": ["precision_approach", "specific_oes"],
            "ref": "Annex 14 Vol I 4.5.2.1(c)",
        },
        "instrument_departure": {
            "surfaces": ["instrument_departure", "specific_oes"],
            "ref": "Annex 14 Vol I 4.5.2.1(d)",
        },
        "take_off_operations": {
            "surfaces": ["take_off_climb", "specific_oes"],
            "ref": "Annex 14 Vol I 4.5.2.1(e)",
        },
        "other_operations": {
            "surfaces": ["specific_oes"],
            "examples": ["curved_approach", "vfr_circuit_patterns"],
            "ref": "Annex 14 Vol I 4.5.2.1(f)",
        },
    },
    "overlap_rule": "each_individual_oes_must_be_considered_when_surfaces_overlap",
}


def obstacle_free_surface_requirements():
    return deepcopy(OBSTACLE_FREE_SURFACE_REQUIREMENTS)


def obstacle_evaluation_surface_requirements():
    return deepcopy(OBSTACLE_EVALUATION_SURFACE_REQUIREMENTS)


def obstacle_limitation_requirements(family: Optional[str] = None):
    normalized_family = (family or "").strip().replace("_", " ").replace("-", " ").lower()
    if normalized_family in {"obstacle free surfaces", "ofs"}:
        return obstacle_free_surface_requirements()
    if normalized_family in {"obstacle evaluation surfaces", "oes"}:
        return obstacle_evaluation_surface_requirements()
    return {
        "section_ref": OBSTACLE_LIMITATION_REF,
        "obstacle_free_surfaces": obstacle_free_surface_requirements(),
        "obstacle_evaluation_surfaces": obstacle_evaluation_surface_requirements(),
    }


def obstacle_free_surface_establishment(runway_type_abbr: Optional[str] = None):
    if runway_type_abbr is None:
        return deepcopy(OBSTACLE_FREE_SURFACE_ESTABLISHMENT)
    normalized_type = str(runway_type_abbr).strip().upper()
    if normalized_type == "NI":
        return deepcopy(OBSTACLE_FREE_SURFACE_ESTABLISHMENT["non_instrument"])
    if normalized_type == "NPA":
        return deepcopy(OBSTACLE_FREE_SURFACE_ESTABLISHMENT["non_precision"])
    if normalized_type in {"PA", "PA_I", "PA_II_III"}:
        return deepcopy(OBSTACLE_FREE_SURFACE_ESTABLISHMENT["precision"])
    return None


def obstacle_evaluation_surface_establishment(operation: Optional[str] = None):
    if operation is None:
        return deepcopy(OBSTACLE_EVALUATION_SURFACE_ESTABLISHMENT)
    normalized_operation = str(operation).strip().replace("-", "_").replace(" ", "_").lower()
    return deepcopy(OBSTACLE_EVALUATION_SURFACE_ESTABLISHMENT["operations"].get(normalized_operation))


def surface_establishment_requirements():
    return {
        "section_ref": SURFACE_ESTABLISHMENT_REF,
        "obstacle_free_surfaces": obstacle_free_surface_establishment(),
        "obstacle_evaluation_surfaces": obstacle_evaluation_surface_establishment(),
    }


__all__ = [
    "OBSTACLE_LIMITATION_REF",
    "SURFACE_ESTABLISHMENT_REF",
    "OBSTACLE_FREE_SURFACE_REQUIREMENTS",
    "OBSTACLE_EVALUATION_SURFACE_REQUIREMENTS",
    "OBSTACLE_FREE_SURFACE_ESTABLISHMENT",
    "OBSTACLE_EVALUATION_SURFACE_ESTABLISHMENT",
    "obstacle_free_surface_requirements",
    "obstacle_evaluation_surface_requirements",
    "obstacle_limitation_requirements",
    "obstacle_free_surface_establishment",
    "obstacle_evaluation_surface_establishment",
    "surface_establishment_requirements",
]
