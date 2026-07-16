"""Current ICAO Annex 14 Volume I conventional OLS parameters.

These parameters apply until 20 November 2030. They are deliberately separate
from the future OFS/OES tables in :mod:`rulesets.annex14.ols_surfaces`.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from ..ols_utils import lookup_detached, normalize_surface_type
from .classification import get_runway_type_abbr

SOURCE_PUBLICATION = "ICAO Annex 14, Volume I, Ninth Edition, Amendment 18"
SOURCE_APPLICABILITY_END = "2030-11-20"
TABLE_4_1_REF = "Annex 14 Vol I 4.1-4.2, Table 4-1, printed page 4-8, supplied PDF page 11"
TABLE_4_2_REF = "Annex 14 Vol I 4.2.22-4.2.27, Table 4-2, printed page 4-11, supplied PDF page 14"

IHS_BASE_HEIGHT_AGL = 45.0


def _approach_sections(
    width: float,
    offset: float,
    divergence: float,
    sections: Tuple[Tuple[float, float], ...],
    reference: str,
) -> List[Dict[str, Any]]:
    result: List[Dict[str, Any]] = []
    for index, (length, slope) in enumerate(sections):
        section = {
            "length": length,
            "slope": slope,
            "divergence": divergence,
            "ref": reference,
        }
        if index == 0:
            section.update(
                start_width=width,
                start_dist_from_thr=offset,
            )
        result.append(section)
    return result


APPROACH_PARAMS: Dict[Tuple[int, str], List[Dict[str, Any]]] = {
    (1, "NI"): _approach_sections(60.0, 30.0, 0.10, ((1600.0, 0.05),), TABLE_4_1_REF),
    (2, "NI"): _approach_sections(80.0, 60.0, 0.10, ((2500.0, 0.04),), TABLE_4_1_REF),
    (3, "NI"): _approach_sections(110.0, 60.0, 0.10, ((3000.0, 0.0333),), TABLE_4_1_REF),
    (4, "NI"): _approach_sections(150.0, 60.0, 0.10, ((3000.0, 0.025),), TABLE_4_1_REF),
    (1, "NPA"): _approach_sections(140.0, 60.0, 0.15, ((2500.0, 0.0333),), TABLE_4_1_REF),
    (2, "NPA"): _approach_sections(140.0, 60.0, 0.15, ((2500.0, 0.0333),), TABLE_4_1_REF),
    (3, "NPA"): _approach_sections(
        280.0, 60.0, 0.15, ((3000.0, 0.02), (3600.0, 0.025), (8400.0, 0.0)), TABLE_4_1_REF
    ),
    (4, "NPA"): _approach_sections(
        280.0, 60.0, 0.15, ((3000.0, 0.02), (3600.0, 0.025), (8400.0, 0.0)), TABLE_4_1_REF
    ),
    (1, "PA_I"): _approach_sections(
        140.0, 60.0, 0.15, ((3000.0, 0.025), (12000.0, 0.03)), TABLE_4_1_REF
    ),
    (2, "PA_I"): _approach_sections(
        140.0, 60.0, 0.15, ((3000.0, 0.025), (12000.0, 0.03)), TABLE_4_1_REF
    ),
}
for _runway_type in ("PA_I", "PA_II_III"):
    for _code in (3, 4):
        APPROACH_PARAMS[(_code, _runway_type)] = _approach_sections(
            280.0,
            60.0,
            0.15,
            ((3000.0, 0.02), (3600.0, 0.025), (8400.0, 0.0)),
            TABLE_4_1_REF,
        )


CONICAL_PARAMS: Dict[Tuple[int, str], Dict[str, Any]] = {}
IHS_PARAMS: Dict[Tuple[int, str], Dict[str, Any]] = {}
_CONICAL_HEIGHTS = {
    (1, "NI"): 35.0,
    (2, "NI"): 55.0,
    (3, "NI"): 75.0,
    (4, "NI"): 100.0,
    (1, "NPA"): 60.0,
    (2, "NPA"): 60.0,
    (3, "NPA"): 75.0,
    (4, "NPA"): 100.0,
    (1, "PA_I"): 60.0,
    (2, "PA_I"): 60.0,
    (3, "PA_I"): 100.0,
    (4, "PA_I"): 100.0,
    (3, "PA_II_III"): 100.0,
    (4, "PA_II_III"): 100.0,
}
_IHS_RADII = {
    (1, "NI"): 2000.0,
    (2, "NI"): 2500.0,
    (3, "NI"): 4000.0,
    (4, "NI"): 4000.0,
    (1, "NPA"): 3500.0,
    (2, "NPA"): 3500.0,
    (3, "NPA"): 4000.0,
    (4, "NPA"): 4000.0,
    (1, "PA_I"): 3500.0,
    (2, "PA_I"): 3500.0,
    (3, "PA_I"): 4000.0,
    (4, "PA_I"): 4000.0,
    (3, "PA_II_III"): 4000.0,
    (4, "PA_II_III"): 4000.0,
}
for _key, _height in _CONICAL_HEIGHTS.items():
    CONICAL_PARAMS[_key] = {
        "slope": 0.05,
        "height_extent_agl": _height,
        "ref": TABLE_4_1_REF,
    }
for _key, _radius in _IHS_RADII.items():
    IHS_PARAMS[_key] = {
        "height_agl": IHS_BASE_HEIGHT_AGL,
        "radius": _radius,
        "ref": TABLE_4_1_REF,
    }


TRANSITIONAL_PARAMS: Dict[Tuple[int, str], Dict[str, Any]] = {}
for _code in (1, 2, 3, 4):
    for _runway_type in ("NI", "NPA", "PA_I", "PA_II_III"):
        _slope = 0.20 if _code in (1, 2) and _runway_type in ("NI", "NPA") else 0.143
        TRANSITIONAL_PARAMS[(_code, _runway_type)] = {
            "slope": _slope,
            "ref": TABLE_4_1_REF,
        }


INNER_APPROACH_PARAMS: Dict[Tuple[int, str], Dict[str, Any]] = {
    (1, "PA_I"): {"width": 90.0, "start_dist_from_thr": 60.0, "length": 900.0, "slope": 0.025, "ref": TABLE_4_1_REF},
    (2, "PA_I"): {"width": 90.0, "start_dist_from_thr": 60.0, "length": 900.0, "slope": 0.025, "ref": TABLE_4_1_REF},
}
for _runway_type in ("PA_I", "PA_II_III"):
    for _code in (3, 4):
        INNER_APPROACH_PARAMS[(_code, _runway_type)] = {
            "width": 120.0,
            "code_letter_f_width": 140.0,
            "start_dist_from_thr": 60.0,
            "length": 900.0,
            "slope": 0.02,
            "ref": TABLE_4_1_REF,
        }


INNER_TRANSITIONAL_PARAMS: Dict[Tuple[int, str], Dict[str, Any]] = {
    (1, "PA_I"): {"slope": 0.40, "ref": TABLE_4_1_REF},
    (2, "PA_I"): {"slope": 0.40, "ref": TABLE_4_1_REF},
}
for _runway_type in ("PA_I", "PA_II_III"):
    for _code in (3, 4):
        INNER_TRANSITIONAL_PARAMS[(_code, _runway_type)] = {
            "slope": 0.333,
            "ref": TABLE_4_1_REF,
        }


BALKED_LANDING_PARAMS: Dict[Tuple[int, str], Dict[str, Any]] = {
    (1, "PA_I"): {
        "width": 90.0,
        "start_dist_from_thr": None,
        "start_dist_rule": "distance_to_end_of_runway_strip",
        "divergence": 0.10,
        "slope": 0.04,
        "ref": TABLE_4_1_REF,
    },
    (2, "PA_I"): {
        "width": 90.0,
        "start_dist_from_thr": None,
        "start_dist_rule": "distance_to_end_of_runway_strip",
        "divergence": 0.10,
        "slope": 0.04,
        "ref": TABLE_4_1_REF,
    },
}
for _runway_type in ("PA_I", "PA_II_III"):
    for _code in (3, 4):
        BALKED_LANDING_PARAMS[(_code, _runway_type)] = {
            "width": 120.0,
            "code_letter_f_width": 140.0,
            "start_dist_from_thr": 1800.0,
            "start_dist_rule": "1800_m_or_end_of_runway_strip_whichever_is_less",
            "divergence": 0.10,
            "slope": 0.0333,
            "ref": TABLE_4_1_REF,
        }


TOCS_PARAMS: Dict[int, Dict[str, Any]] = {
    1: {"inner_edge_width": 60.0, "origin_offset": 30.0, "divergence": 0.10, "final_width": 380.0, "length": 1600.0, "slope": 0.05, "ref": TABLE_4_2_REF},
    2: {"inner_edge_width": 80.0, "origin_offset": 60.0, "divergence": 0.10, "final_width": 580.0, "length": 2500.0, "slope": 0.04, "ref": TABLE_4_2_REF},
    3: {"inner_edge_width": 180.0, "origin_offset": 60.0, "divergence": 0.125, "final_width": 1200.0, "heading_change_gt_15_final_width": 1800.0, "length": 15000.0, "slope": 0.02, "ref": TABLE_4_2_REF},
    4: {"inner_edge_width": 180.0, "origin_offset": 60.0, "divergence": 0.125, "final_width": 1200.0, "heading_change_gt_15_final_width": 1800.0, "length": 15000.0, "slope": 0.02, "ref": TABLE_4_2_REF},
}


def ihs_base_height() -> float:
    return IHS_BASE_HEIGHT_AGL


def current_ols_surface_families() -> dict:
    return {
        "approach": {"status": "source_loaded", "ref": TABLE_4_1_REF},
        "transitional": {"status": "source_loaded", "ref": TABLE_4_1_REF},
        "inner_horizontal": {"status": "source_loaded", "ref": TABLE_4_1_REF},
        "conical": {"status": "source_loaded", "ref": TABLE_4_1_REF},
        "take_off_climb": {"status": "source_loaded", "ref": TABLE_4_2_REF},
        "ofz": {"status": "source_loaded", "ref": TABLE_4_1_REF},
    }


def get_ols_params(arc_num: int, runway_type: Optional[str], surface_type: str):
    try:
        code = int(arc_num)
    except (TypeError, ValueError):
        return None
    if code not in {1, 2, 3, 4}:
        return None
    runway_type_abbr = get_runway_type_abbr(runway_type)
    key = (code, runway_type_abbr)
    surface = normalize_surface_type(surface_type)
    if surface in {"APPROACH", "APPROACHSURFACE"}:
        return lookup_detached(APPROACH_PARAMS, key)
    if surface in {"TOCS", "TAKEOFFCLIMB", "TAKEOFFCLIMBSURFACE"}:
        return lookup_detached(TOCS_PARAMS, code)
    if surface in {"TRANSITIONAL", "TRANSITIONALSURFACE"}:
        return lookup_detached(TRANSITIONAL_PARAMS, key)
    if surface in {"INNERAPPROACH", "INNERAPPROACHSURFACE"}:
        return lookup_detached(INNER_APPROACH_PARAMS, key)
    if surface in {"INNERTRANSITIONAL", "INNERTRANSITIONALSURFACE"}:
        return lookup_detached(INNER_TRANSITIONAL_PARAMS, key)
    if surface in {"BALKEDLANDING", "BALKEDLANDINGSURFACE", "BAULKEDLANDING", "BAULKEDLANDINGSURFACE"}:
        return lookup_detached(BALKED_LANDING_PARAMS, key)
    if surface in {"IHS", "INNERHORIZONTAL", "INNERHORIZONTALSURFACE"}:
        return lookup_detached(IHS_PARAMS, key)
    if surface in {"CONICAL", "CONICALSURFACE"}:
        return lookup_detached(CONICAL_PARAMS, key)
    return None


def ols_parameters(arc_num: int, runway_type: Optional[str], surface_type: str):
    return get_ols_params(arc_num, runway_type, surface_type)


CURRENT_OLS_REF = "Annex 14 Vol I current OLS, applicable until 20 November 2030"
PROTECTED_AIRSPACE_MODEL = "annex14_current_ols"


def protected_airspace_model():
    return PROTECTED_AIRSPACE_MODEL


__all__ = [
    "APPROACH_PARAMS",
    "BALKED_LANDING_PARAMS",
    "CONICAL_PARAMS",
    "CURRENT_OLS_REF",
    "IHS_PARAMS",
    "INNER_APPROACH_PARAMS",
    "INNER_TRANSITIONAL_PARAMS",
    "PROTECTED_AIRSPACE_MODEL",
    "SOURCE_APPLICABILITY_END",
    "SOURCE_PUBLICATION",
    "TABLE_4_1_REF",
    "TABLE_4_2_REF",
    "TOCS_PARAMS",
    "TRANSITIONAL_PARAMS",
    "current_ols_surface_families",
    "get_ols_params",
    "ihs_base_height",
    "ols_parameters",
    "protected_airspace_model",
]
