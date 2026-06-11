# -*- coding: utf-8 -*-
# rulesets/easa/ols_surfaces.py
"""
EASA CS-ADR-DSN Issue 7 OLS surface parameters.

This module stores Obstacle Limitation Surface (OLS) parameters derived
from EASA CS-ADR-DSN Issue 7, Chapters H and J:

- Chapter H defines the geometry and purpose of each OLS surface.
- Chapter J specifies which surfaces apply to each runway type, and gives
  the controlling dimensions and slopes in Table J-1 and Table J-2.

The structure mirrors the MOS139 `ols_surfaces.py` module so it can be
used as a ruleset replacement. Values are expressed as metres and slopes
as gradients, for example 5% is stored as 0.05.

Runway type abbreviations used by this module:
- NI: Non-instrument runway
- NPA: Non-precision approach runway
- PA_I: Precision approach Category I runway
- PA_II_III: Precision approach Category II or III runway

Notes on EASA interpretation:
- Table J-1 gives inner approach and balked landing surfaces for
  precision approach Category I, as well as for Category II/III. The OFZ
  requirement in CS ADR-DSN.H.445 is aimed at Category II/III operations,
  but GM1 ADR-DSN.J.480(a) also identifies the inner approach, inner
  transitional and balked landing surfaces for precision approach
  Category I. This module therefore includes these surfaces for PA_I.
- Table J-1 footnote (c) gives the PA_I Code 1/2 balked landing distance
  as "distance to the end of strip". Because that is runway-length
  dependent, the numeric field is None and a rule string is supplied.
- Table J-1 footnote (d) gives the PA_I Code 3/4 and PA_II/III balked
  landing distance as 1 800 m or the end of runway, whichever is less.
  The numeric field is 1800.0 and a rule string is supplied.
- Table J-2 gives the Code 3/4 take-off climb final width as 1 200 m, or
  1 800 m where the intended track includes heading changes greater than
  15 degrees for operations conducted in IMC or VMC by night. The default
  final_width is 1200.0 and the conditional value is stored separately.
- Table J-2 footnote (e) increases the take-off climb inner edge width to
  150 m where a clearway is provided. The normal value and clearway value
  are both retained.
- Chapter H treats the outer horizontal surface as guidance material rather
  than as a Table J-1 requirement. The OHS values included here are
  guidance-only defaults based on GM1 ADR-DSN.H.410: 150 m above aerodrome
  elevation within 15 000 m for code number 3 or 4 aerodromes.
"""

import logging
import re
from typing import Any, Dict, List, Optional, Tuple

try:
    from .classification import get_runway_type_abbr
except Exception:  # pragma: no cover - allows standalone inspection/testing
    def get_runway_type_abbr(runway_type_str: Optional[str]) -> str:
        """Fallback runway type classifier for standalone use."""
        value = (runway_type_str or "").upper().replace("-", "_").replace(" ", "_")
        if value in {"NI", "NON_INSTRUMENT", "NONINSTRUMENT"}:
            return "NI"
        if value in {"NPA", "NON_PRECISION", "NONPRECISION", "NON_PRECISION_APPROACH"}:
            return "NPA"
        if value in {"PA_I", "CAT_I", "CATI", "PRECISION_APPROACH_CAT_I"}:
            return "PA_I"
        if value in {
            "PA_II_III", "CAT_II_III", "CATIIIII", "CAT_II", "CAT_III",
            "PRECISION_APPROACH_CAT_II_III",
        }:
            return "PA_II_III"
        if "II" in value or "III" in value:
            return "PA_II_III"
        if "PRECISION" in value or "CAT_I" in value or "CATI" in value:
            return "PA_I"
        if "NON_PRECISION" in value or "NPA" in value:
            return "NPA"
        return "NI"

LOGGER = logging.getLogger(__name__)


def _normalize_surface_type(surface_type: str) -> str:
    """Normalize caller surface labels to compact lookup keys."""
    return re.sub(r"[^A-Z0-9]", "", (surface_type or "").upper())

# =========================================================================
# Basic constants and references
# =========================================================================

EASA_OLS_REF = "CS-ADR-DSN Issue 7, Chapters H and J"
TABLE_J1_REF = "CS ADR-DSN.J.470/J.475/J.480 Table J-1"
TABLE_J2_REF = "CS ADR-DSN.J.485 Table J-2"
OHS_GUIDANCE_REF = "GM1 ADR-DSN.H.410"
SOURCE_PUBLICATION = "EASA Easy Access Rules for Aerodromes, CS-ADR-DSN Issue 7"
SOURCE_URL = (
    "https://www.easa.europa.eu/en/document-library/easy-access-rules/"
    "online-publications/easy-access-rules-aerodromes-regulation-eu"
)
TABLE_J1_SOURCE_URL = f"{SOURCE_URL}?erules-id=ERULES-1963177438-2238"
TABLE_J2_SOURCE_URL = f"{SOURCE_URL}?erules-id=ERULES-1963177438-2239"
OHS_GUIDANCE_SOURCE_URL = f"{SOURCE_URL}?erules-id=ERULES-1963177438-2214"

IHS_BASE_HEIGHT_AGL = 45.0
OHS_GUIDANCE_HEIGHT_AGL = 150.0
OHS_GUIDANCE_RADIUS_M = 15000.0
OHS_GUIDANCE_LOCAL_OBJECT_HEIGHT_M = 30.0

# =========================================================================
# Approach surface parameters, Table J-1
# =========================================================================

APPROACH_PARAMS: Dict[Tuple[int, str], List[Dict[str, Any]]] = {
    # Non-instrument runways
    (1, "NI"): [
        {
            "length": 1600.0,
            "slope": 0.05,
            "divergence": 0.10,
            "start_dist_from_thr": 30.0,
            "start_width": 60.0,
            "section": "first",
            "total_length": 1600.0,
            "ref": f"{TABLE_J1_REF} (NI Code 1 Approach)",
        }
    ],
    (2, "NI"): [
        {
            "length": 2500.0,
            "slope": 0.04,
            "divergence": 0.10,
            "start_dist_from_thr": 60.0,
            "start_width": 80.0,
            "section": "first",
            "total_length": 2500.0,
            "ref": f"{TABLE_J1_REF} (NI Code 2 Approach)",
        }
    ],
    (3, "NI"): [
        {
            "length": 3000.0,
            "slope": 0.0333,
            "divergence": 0.10,
            "start_dist_from_thr": 60.0,
            "start_width": 150.0,
            "section": "first",
            "total_length": 3000.0,
            "ref": f"{TABLE_J1_REF} (NI Code 3 Approach)",
        }
    ],
    (4, "NI"): [
        {
            "length": 3000.0,
            "slope": 0.025,
            "divergence": 0.10,
            "start_dist_from_thr": 60.0,
            "start_width": 150.0,
            "section": "first",
            "total_length": 3000.0,
            "ref": f"{TABLE_J1_REF} (NI Code 4 Approach)",
        }
    ],
    # Non-precision approach runways
    (1, "NPA"): [
        {
            "length": 2500.0,
            "slope": 0.0333,
            "divergence": 0.15,
            "start_dist_from_thr": 60.0,
            "start_width": 140.0,
            "section": "first",
            "total_length": 2500.0,
            "ref": f"{TABLE_J1_REF} (NPA Code 1/2 Approach)",
        }
    ],
    (2, "NPA"): [
        {
            "length": 2500.0,
            "slope": 0.0333,
            "divergence": 0.15,
            "start_dist_from_thr": 60.0,
            "start_width": 140.0,
            "section": "first",
            "total_length": 2500.0,
            "ref": f"{TABLE_J1_REF} (NPA Code 1/2 Approach)",
        }
    ],
    (3, "NPA"): [
        {
            "length": 3000.0,
            "slope": 0.02,
            "divergence": 0.15,
            "start_dist_from_thr": 60.0,
            "start_width": 280.0,
            "section": "first",
            "ref": f"{TABLE_J1_REF} (NPA Code 3 First Section)",
        },
        {
            "length": 3600.0,
            "slope": 0.025,
            "divergence": 0.15,
            "section": "second",
            "variable_length": True,
            "variable_length_rule": "Length is variable under CS ADR-DSN.J.475(c); horizontal beyond the point where the 2.5% slope intersects the controlling horizontal plane.",
            "ref": f"{TABLE_J1_REF} (NPA Code 3 Second Section)",
        },
        {
            "length": 8400.0,
            "slope": 0.0,
            "divergence": 0.15,
            "section": "horizontal",
            "variable_length": True,
            "total_length": 15000.0,
            "ref": f"{TABLE_J1_REF} (NPA Code 3 Horizontal Section)",
        },
    ],
    (4, "NPA"): [
        {
            "length": 3000.0,
            "slope": 0.02,
            "divergence": 0.15,
            "start_dist_from_thr": 60.0,
            "start_width": 280.0,
            "section": "first",
            "ref": f"{TABLE_J1_REF} (NPA Code 4 First Section)",
        },
        {
            "length": 3600.0,
            "slope": 0.025,
            "divergence": 0.15,
            "section": "second",
            "variable_length": True,
            "variable_length_rule": "Length is variable under CS ADR-DSN.J.475(c); horizontal beyond the point where the 2.5% slope intersects the controlling horizontal plane.",
            "ref": f"{TABLE_J1_REF} (NPA Code 4 Second Section)",
        },
        {
            "length": 8400.0,
            "slope": 0.0,
            "divergence": 0.15,
            "section": "horizontal",
            "variable_length": True,
            "total_length": 15000.0,
            "ref": f"{TABLE_J1_REF} (NPA Code 4 Horizontal Section)",
        },
    ],
    # Precision approach Category I runways
    (1, "PA_I"): [
        {
            "length": 3000.0,
            "slope": 0.025,
            "divergence": 0.15,
            "start_dist_from_thr": 60.0,
            "start_width": 140.0,
            "section": "first",
            "ref": f"{TABLE_J1_REF} (PA CAT I Code 1/2 First Section)",
        },
        {
            "length": 12000.0,
            "slope": 0.03,
            "divergence": 0.15,
            "section": "second",
            "total_length": 15000.0,
            "ref": f"{TABLE_J1_REF} (PA CAT I Code 1/2 Second Section)",
        },
    ],
    (2, "PA_I"): [
        {
            "length": 3000.0,
            "slope": 0.025,
            "divergence": 0.15,
            "start_dist_from_thr": 60.0,
            "start_width": 140.0,
            "section": "first",
            "ref": f"{TABLE_J1_REF} (PA CAT I Code 1/2 First Section)",
        },
        {
            "length": 12000.0,
            "slope": 0.03,
            "divergence": 0.15,
            "section": "second",
            "total_length": 15000.0,
            "ref": f"{TABLE_J1_REF} (PA CAT I Code 1/2 Second Section)",
        },
    ],
    (3, "PA_I"): [
        {
            "length": 3000.0,
            "slope": 0.02,
            "divergence": 0.15,
            "start_dist_from_thr": 60.0,
            "start_width": 280.0,
            "section": "first",
            "ref": f"{TABLE_J1_REF} (PA CAT I Code 3/4 First Section)",
        },
        {
            "length": 3600.0,
            "slope": 0.025,
            "divergence": 0.15,
            "section": "second",
            "variable_length": True,
            "variable_length_rule": "Length is variable under CS ADR-DSN.J.480(d); horizontal beyond the point where the 2.5% slope intersects the controlling horizontal plane.",
            "ref": f"{TABLE_J1_REF} (PA CAT I Code 3/4 Second Section)",
        },
        {
            "length": 8400.0,
            "slope": 0.0,
            "divergence": 0.15,
            "section": "horizontal",
            "variable_length": True,
            "total_length": 15000.0,
            "ref": f"{TABLE_J1_REF} (PA CAT I Code 3/4 Horizontal Section)",
        },
    ],
    (4, "PA_I"): [
        {
            "length": 3000.0,
            "slope": 0.02,
            "divergence": 0.15,
            "start_dist_from_thr": 60.0,
            "start_width": 280.0,
            "section": "first",
            "ref": f"{TABLE_J1_REF} (PA CAT I Code 3/4 First Section)",
        },
        {
            "length": 3600.0,
            "slope": 0.025,
            "divergence": 0.15,
            "section": "second",
            "variable_length": True,
            "variable_length_rule": "Length is variable under CS ADR-DSN.J.480(d); horizontal beyond the point where the 2.5% slope intersects the controlling horizontal plane.",
            "ref": f"{TABLE_J1_REF} (PA CAT I Code 3/4 Second Section)",
        },
        {
            "length": 8400.0,
            "slope": 0.0,
            "divergence": 0.15,
            "section": "horizontal",
            "variable_length": True,
            "total_length": 15000.0,
            "ref": f"{TABLE_J1_REF} (PA CAT I Code 3/4 Horizontal Section)",
        },
    ],
    # Precision approach Category II/III runways, Code 3/4 only
    (3, "PA_II_III"): [
        {
            "length": 3000.0,
            "slope": 0.02,
            "divergence": 0.15,
            "start_dist_from_thr": 60.0,
            "start_width": 280.0,
            "section": "first",
            "ref": f"{TABLE_J1_REF} (PA CAT II/III Code 3/4 First Section)",
        },
        {
            "length": 3600.0,
            "slope": 0.025,
            "divergence": 0.15,
            "section": "second",
            "variable_length": True,
            "variable_length_rule": "Length is variable under CS ADR-DSN.J.480(d); horizontal beyond the point where the 2.5% slope intersects the controlling horizontal plane.",
            "ref": f"{TABLE_J1_REF} (PA CAT II/III Code 3/4 Second Section)",
        },
        {
            "length": 8400.0,
            "slope": 0.0,
            "divergence": 0.15,
            "section": "horizontal",
            "variable_length": True,
            "total_length": 15000.0,
            "ref": f"{TABLE_J1_REF} (PA CAT II/III Code 3/4 Horizontal Section)",
        },
    ],
    (4, "PA_II_III"): [
        {
            "length": 3000.0,
            "slope": 0.02,
            "divergence": 0.15,
            "start_dist_from_thr": 60.0,
            "start_width": 280.0,
            "section": "first",
            "ref": f"{TABLE_J1_REF} (PA CAT II/III Code 3/4 First Section)",
        },
        {
            "length": 3600.0,
            "slope": 0.025,
            "divergence": 0.15,
            "section": "second",
            "variable_length": True,
            "variable_length_rule": "Length is variable under CS ADR-DSN.J.480(d); horizontal beyond the point where the 2.5% slope intersects the controlling horizontal plane.",
            "ref": f"{TABLE_J1_REF} (PA CAT II/III Code 3/4 Second Section)",
        },
        {
            "length": 8400.0,
            "slope": 0.0,
            "divergence": 0.15,
            "section": "horizontal",
            "variable_length": True,
            "total_length": 15000.0,
            "ref": f"{TABLE_J1_REF} (PA CAT II/III Code 3/4 Horizontal Section)",
        },
    ],
}

# =========================================================================
# OFZ-related precision approach surfaces, Table J-1
# =========================================================================

INNER_APPROACH_PARAMS: Dict[Tuple[int, str], Dict[str, Any]] = {
    (1, "PA_I"): {
        "width": 90.0,
        "start_dist_from_thr": 60.0,
        "length": 900.0,
        "slope": 0.025,
        "code_letter_f_width": None,
        "ref": f"{TABLE_J1_REF} (Inner Approach PA CAT I Code 1/2)",
    },
    (2, "PA_I"): {
        "width": 90.0,
        "start_dist_from_thr": 60.0,
        "length": 900.0,
        "slope": 0.025,
        "code_letter_f_width": None,
        "ref": f"{TABLE_J1_REF} (Inner Approach PA CAT I Code 1/2)",
    },
    (3, "PA_I"): {
        "width": 120.0,
        "start_dist_from_thr": 60.0,
        "length": 900.0,
        "slope": 0.02,
        "code_letter_f_width": 140.0,
        "ref": f"{TABLE_J1_REF} (Inner Approach PA CAT I Code 3/4)",
    },
    (4, "PA_I"): {
        "width": 120.0,
        "start_dist_from_thr": 60.0,
        "length": 900.0,
        "slope": 0.02,
        "code_letter_f_width": 140.0,
        "ref": f"{TABLE_J1_REF} (Inner Approach PA CAT I Code 3/4)",
    },
    (3, "PA_II_III"): {
        "width": 120.0,
        "start_dist_from_thr": 60.0,
        "length": 900.0,
        "slope": 0.02,
        "code_letter_f_width": 140.0,
        "ref": f"{TABLE_J1_REF} (Inner Approach PA CAT II/III Code 3/4)",
    },
    (4, "PA_II_III"): {
        "width": 120.0,
        "start_dist_from_thr": 60.0,
        "length": 900.0,
        "slope": 0.02,
        "code_letter_f_width": 140.0,
        "ref": f"{TABLE_J1_REF} (Inner Approach PA CAT II/III Code 3/4)",
    },
}

INNER_TRANSITIONAL_PARAMS: Dict[Tuple[int, str], Dict[str, Any]] = {
    (1, "PA_I"): {"slope": 0.40, "ref": f"{TABLE_J1_REF} (Inner Transitional PA CAT I Code 1/2)"},
    (2, "PA_I"): {"slope": 0.40, "ref": f"{TABLE_J1_REF} (Inner Transitional PA CAT I Code 1/2)"},
    (3, "PA_I"): {"slope": 0.333, "ref": f"{TABLE_J1_REF} (Inner Transitional PA CAT I Code 3/4)"},
    (4, "PA_I"): {"slope": 0.333, "ref": f"{TABLE_J1_REF} (Inner Transitional PA CAT I Code 3/4)"},
    (3, "PA_II_III"): {"slope": 0.333, "ref": f"{TABLE_J1_REF} (Inner Transitional PA CAT II/III Code 3/4)"},
    (4, "PA_II_III"): {"slope": 0.333, "ref": f"{TABLE_J1_REF} (Inner Transitional PA CAT II/III Code 3/4)"},
}

BALKED_LANDING_PARAMS: Dict[Tuple[int, str], Dict[str, Any]] = {
    (1, "PA_I"): {
        "width": 90.0,
        "start_dist_from_thr": None,
        "start_dist_rule": "Distance to the end of strip.",
        "divergence": 0.10,
        "slope": 0.04,
        "code_letter_f_width": None,
        "ref": f"{TABLE_J1_REF} (Balked Landing PA CAT I Code 1/2)",
    },
    (2, "PA_I"): {
        "width": 90.0,
        "start_dist_from_thr": None,
        "start_dist_rule": "Distance to the end of strip.",
        "divergence": 0.10,
        "slope": 0.04,
        "code_letter_f_width": None,
        "ref": f"{TABLE_J1_REF} (Balked Landing PA CAT I Code 1/2)",
    },
    (3, "PA_I"): {
        "width": 120.0,
        "start_dist_from_thr": 1800.0,
        "start_dist_rule": "1 800 m or end of runway, whichever is less.",
        "divergence": 0.10,
        "slope": 0.0333,
        "code_letter_f_width": 140.0,
        "ref": f"{TABLE_J1_REF} (Balked Landing PA CAT I Code 3/4)",
    },
    (4, "PA_I"): {
        "width": 120.0,
        "start_dist_from_thr": 1800.0,
        "start_dist_rule": "1 800 m or end of runway, whichever is less.",
        "divergence": 0.10,
        "slope": 0.0333,
        "code_letter_f_width": 140.0,
        "ref": f"{TABLE_J1_REF} (Balked Landing PA CAT I Code 3/4)",
    },
    (3, "PA_II_III"): {
        "width": 120.0,
        "start_dist_from_thr": 1800.0,
        "start_dist_rule": "1 800 m or end of runway, whichever is less.",
        "divergence": 0.10,
        "slope": 0.0333,
        "code_letter_f_width": 140.0,
        "ref": f"{TABLE_J1_REF} (Balked Landing PA CAT II/III Code 3/4)",
    },
    (4, "PA_II_III"): {
        "width": 120.0,
        "start_dist_from_thr": 1800.0,
        "start_dist_rule": "1 800 m or end of runway, whichever is less.",
        "divergence": 0.10,
        "slope": 0.0333,
        "code_letter_f_width": 140.0,
        "ref": f"{TABLE_J1_REF} (Balked Landing PA CAT II/III Code 3/4)",
    },
}

# UK/Australian spelling alias retained for compatibility with existing code.
BAULKED_LANDING_PARAMS = BALKED_LANDING_PARAMS

# =========================================================================
# Take-off climb surface, Table J-2
# =========================================================================

TOCS_PARAMS: Dict[int, Dict[str, Any]] = {
    1: {
        "inner_edge_width": 60.0,
        "inner_edge_width_clearway": 150.0,
        "origin_offset": 30.0,
        "origin_offset_rule": "Starts at the end of the clearway if the clearway length exceeds the specified distance.",
        "divergence": 0.10,
        "final_width": 380.0,
        "length": 1600.0,
        "slope": 0.05,
        "ref": f"{TABLE_J2_REF} (Take-off Climb Code 1)",
    },
    2: {
        "inner_edge_width": 80.0,
        "inner_edge_width_clearway": 150.0,
        "origin_offset": 60.0,
        "origin_offset_rule": "Starts at the end of the clearway if the clearway length exceeds the specified distance.",
        "divergence": 0.10,
        "final_width": 580.0,
        "length": 2500.0,
        "slope": 0.04,
        "ref": f"{TABLE_J2_REF} (Take-off Climb Code 2)",
    },
    3: {
        "inner_edge_width": 180.0,
        "inner_edge_width_clearway": 180.0,
        "origin_offset": 60.0,
        "origin_offset_rule": "Starts at the end of the clearway if the clearway length exceeds the specified distance.",
        "divergence": 0.125,
        "final_width": 1200.0,
        "final_width_turning": 1800.0,
        "final_width_turning_rule": "Use 1 800 m where the intended track includes heading changes greater than 15 degrees for operations in IMC or VMC by night.",
        "length": 15000.0,
        "slope": 0.02,
        "slope_reduced_guidance": 0.016,
        "slope_reduced_guidance_rule": "If no object reaches the 2% surface, GM1 ADR-DSN.J.485 recommends an obstacle-free surface of 1.6%.",
        "ref": f"{TABLE_J2_REF} (Take-off Climb Code 3/4)",
    },
    4: {
        "inner_edge_width": 180.0,
        "inner_edge_width_clearway": 180.0,
        "origin_offset": 60.0,
        "origin_offset_rule": "Starts at the end of the clearway if the clearway length exceeds the specified distance.",
        "divergence": 0.125,
        "final_width": 1200.0,
        "final_width_turning": 1800.0,
        "final_width_turning_rule": "Use 1 800 m where the intended track includes heading changes greater than 15 degrees for operations in IMC or VMC by night.",
        "length": 15000.0,
        "slope": 0.02,
        "slope_reduced_guidance": 0.016,
        "slope_reduced_guidance_rule": "If no object reaches the 2% surface, GM1 ADR-DSN.J.485 recommends an obstacle-free surface of 1.6%.",
        "ref": f"{TABLE_J2_REF} (Take-off Climb Code 3/4)",
    },
}

# =========================================================================
# Inner horizontal surface, conical surface and optional outer horizontal surface
# =========================================================================

IHS_PARAMS: Dict[Tuple[int, str], Dict[str, Any]] = {
    (1, "NI"): {"height_agl": 45.0, "radius": 2000.0, "ref": f"{TABLE_J1_REF} (IHS NI Code 1)"},
    (2, "NI"): {"height_agl": 45.0, "radius": 2500.0, "ref": f"{TABLE_J1_REF} (IHS NI Code 2)"},
    (3, "NI"): {"height_agl": 45.0, "radius": 4000.0, "ref": f"{TABLE_J1_REF} (IHS NI Code 3)"},
    (4, "NI"): {"height_agl": 45.0, "radius": 4000.0, "ref": f"{TABLE_J1_REF} (IHS NI Code 4)"},
    (1, "NPA"): {"height_agl": 45.0, "radius": 3500.0, "ref": f"{TABLE_J1_REF} (IHS NPA Code 1/2)"},
    (2, "NPA"): {"height_agl": 45.0, "radius": 3500.0, "ref": f"{TABLE_J1_REF} (IHS NPA Code 1/2)"},
    (3, "NPA"): {"height_agl": 45.0, "radius": 4000.0, "ref": f"{TABLE_J1_REF} (IHS NPA Code 3)"},
    (4, "NPA"): {"height_agl": 45.0, "radius": 4000.0, "ref": f"{TABLE_J1_REF} (IHS NPA Code 4)"},
    (1, "PA_I"): {"height_agl": 45.0, "radius": 3500.0, "ref": f"{TABLE_J1_REF} (IHS PA CAT I Code 1/2)"},
    (2, "PA_I"): {"height_agl": 45.0, "radius": 3500.0, "ref": f"{TABLE_J1_REF} (IHS PA CAT I Code 1/2)"},
    (3, "PA_I"): {"height_agl": 45.0, "radius": 4000.0, "ref": f"{TABLE_J1_REF} (IHS PA CAT I Code 3/4)"},
    (4, "PA_I"): {"height_agl": 45.0, "radius": 4000.0, "ref": f"{TABLE_J1_REF} (IHS PA CAT I Code 3/4)"},
    (3, "PA_II_III"): {"height_agl": 45.0, "radius": 4000.0, "ref": f"{TABLE_J1_REF} (IHS PA CAT II/III Code 3/4)"},
    (4, "PA_II_III"): {"height_agl": 45.0, "radius": 4000.0, "ref": f"{TABLE_J1_REF} (IHS PA CAT II/III Code 3/4)"},
}

CONICAL_PARAMS: Dict[Tuple[int, str], Dict[str, Any]] = {
    (1, "NI"): {"slope": 0.05, "height_extent_agl": 35.0, "ref": f"{TABLE_J1_REF} (Conical NI Code 1)"},
    (2, "NI"): {"slope": 0.05, "height_extent_agl": 55.0, "ref": f"{TABLE_J1_REF} (Conical NI Code 2)"},
    (3, "NI"): {"slope": 0.05, "height_extent_agl": 75.0, "ref": f"{TABLE_J1_REF} (Conical NI Code 3)"},
    (4, "NI"): {"slope": 0.05, "height_extent_agl": 100.0, "ref": f"{TABLE_J1_REF} (Conical NI Code 4)"},
    (1, "NPA"): {"slope": 0.05, "height_extent_agl": 60.0, "ref": f"{TABLE_J1_REF} (Conical NPA Code 1/2)"},
    (2, "NPA"): {"slope": 0.05, "height_extent_agl": 60.0, "ref": f"{TABLE_J1_REF} (Conical NPA Code 1/2)"},
    (3, "NPA"): {"slope": 0.05, "height_extent_agl": 75.0, "ref": f"{TABLE_J1_REF} (Conical NPA Code 3)"},
    (4, "NPA"): {"slope": 0.05, "height_extent_agl": 100.0, "ref": f"{TABLE_J1_REF} (Conical NPA Code 4)"},
    (1, "PA_I"): {"slope": 0.05, "height_extent_agl": 60.0, "ref": f"{TABLE_J1_REF} (Conical PA CAT I Code 1/2)"},
    (2, "PA_I"): {"slope": 0.05, "height_extent_agl": 60.0, "ref": f"{TABLE_J1_REF} (Conical PA CAT I Code 1/2)"},
    (3, "PA_I"): {"slope": 0.05, "height_extent_agl": 100.0, "ref": f"{TABLE_J1_REF} (Conical PA CAT I Code 3/4)"},
    (4, "PA_I"): {"slope": 0.05, "height_extent_agl": 100.0, "ref": f"{TABLE_J1_REF} (Conical PA CAT I Code 3/4)"},
    (3, "PA_II_III"): {"slope": 0.05, "height_extent_agl": 100.0, "ref": f"{TABLE_J1_REF} (Conical PA CAT II/III Code 3/4)"},
    (4, "PA_II_III"): {"slope": 0.05, "height_extent_agl": 100.0, "ref": f"{TABLE_J1_REF} (Conical PA CAT II/III Code 3/4)"},
}

# Guidance-only outer horizontal surface. Not a Table J-1 certification surface.
OHS_PARAMS: Dict[Tuple[int, str], Dict[str, Any]] = {
    (3, "NI"): {"height_agl": 150.0, "radius": 15000.0, "local_object_height_agl": 30.0, "guidance_only": True, "ref": OHS_GUIDANCE_REF},
    (4, "NI"): {"height_agl": 150.0, "radius": 15000.0, "local_object_height_agl": 30.0, "guidance_only": True, "ref": OHS_GUIDANCE_REF},
    (3, "NPA"): {"height_agl": 150.0, "radius": 15000.0, "local_object_height_agl": 30.0, "guidance_only": True, "ref": OHS_GUIDANCE_REF},
    (4, "NPA"): {"height_agl": 150.0, "radius": 15000.0, "local_object_height_agl": 30.0, "guidance_only": True, "ref": OHS_GUIDANCE_REF},
    (3, "PA_I"): {"height_agl": 150.0, "radius": 15000.0, "local_object_height_agl": 30.0, "guidance_only": True, "ref": OHS_GUIDANCE_REF},
    (4, "PA_I"): {"height_agl": 150.0, "radius": 15000.0, "local_object_height_agl": 30.0, "guidance_only": True, "ref": OHS_GUIDANCE_REF},
    (3, "PA_II_III"): {"height_agl": 150.0, "radius": 15000.0, "local_object_height_agl": 30.0, "guidance_only": True, "ref": OHS_GUIDANCE_REF},
    (4, "PA_II_III"): {"height_agl": 150.0, "radius": 15000.0, "local_object_height_agl": 30.0, "guidance_only": True, "ref": OHS_GUIDANCE_REF},
}

# =========================================================================
# Transitional surface, Table J-1
# =========================================================================

TRANSITIONAL_PARAMS: Dict[Tuple[int, str], Dict[str, Any]] = {
    (1, "NI"): {"slope": 0.20, "ref": f"{TABLE_J1_REF} (Transitional NI Code 1)"},
    (2, "NI"): {"slope": 0.20, "ref": f"{TABLE_J1_REF} (Transitional NI Code 2)"},
    (3, "NI"): {"slope": 0.143, "ref": f"{TABLE_J1_REF} (Transitional NI Code 3)"},
    (4, "NI"): {"slope": 0.143, "ref": f"{TABLE_J1_REF} (Transitional NI Code 4)"},
    (1, "NPA"): {"slope": 0.20, "ref": f"{TABLE_J1_REF} (Transitional NPA Code 1/2)"},
    (2, "NPA"): {"slope": 0.20, "ref": f"{TABLE_J1_REF} (Transitional NPA Code 1/2)"},
    (3, "NPA"): {"slope": 0.143, "ref": f"{TABLE_J1_REF} (Transitional NPA Code 3)"},
    (4, "NPA"): {"slope": 0.143, "ref": f"{TABLE_J1_REF} (Transitional NPA Code 4)"},
    (1, "PA_I"): {"slope": 0.143, "ref": f"{TABLE_J1_REF} (Transitional PA CAT I Code 1/2)"},
    (2, "PA_I"): {"slope": 0.143, "ref": f"{TABLE_J1_REF} (Transitional PA CAT I Code 1/2)"},
    (3, "PA_I"): {"slope": 0.143, "ref": f"{TABLE_J1_REF} (Transitional PA CAT I Code 3/4)"},
    (4, "PA_I"): {"slope": 0.143, "ref": f"{TABLE_J1_REF} (Transitional PA CAT I Code 3/4)"},
    (3, "PA_II_III"): {"slope": 0.143, "ref": f"{TABLE_J1_REF} (Transitional PA CAT II/III Code 3/4)"},
    (4, "PA_II_III"): {"slope": 0.143, "ref": f"{TABLE_J1_REF} (Transitional PA CAT II/III Code 3/4)"},
}

# =========================================================================
# Source traceability
# =========================================================================

OLS_TRACEABILITY_ITEMS = {
    "approach_surface": {
        "source": TABLE_J1_REF,
        "status": "operational_verified",
        "implementation": "APPROACH_PARAMS",
        "notes": "Table J-1 approach inner edge, threshold distance, divergence, section lengths, slopes, and total lengths.",
    },
    "inner_approach_surface": {
        "source": TABLE_J1_REF,
        "status": "operational_verified",
        "implementation": "INNER_APPROACH_PARAMS",
        "notes": "Table J-1 inner approach dimensions for precision approach runway columns.",
    },
    "inner_transitional_surface": {
        "source": TABLE_J1_REF,
        "status": "operational_verified",
        "implementation": "INNER_TRANSITIONAL_PARAMS",
        "notes": "Table J-1 inner transitional slopes for precision approach runway columns.",
    },
    "balked_landing_surface": {
        "source": TABLE_J1_REF,
        "status": "operational_verified",
        "implementation": "BALKED_LANDING_PARAMS",
        "notes": "Table J-1 balked landing dimensions, including distance and code letter F footnotes.",
    },
    "inner_horizontal_surface": {
        "source": TABLE_J1_REF,
        "status": "operational_verified",
        "implementation": "IHS_PARAMS",
        "notes": "Table J-1 inner horizontal height and radius values.",
    },
    "conical_surface": {
        "source": TABLE_J1_REF,
        "status": "operational_verified",
        "implementation": "CONICAL_PARAMS",
        "notes": "Table J-1 conical slope and height values.",
    },
    "transitional_surface": {
        "source": TABLE_J1_REF,
        "status": "operational_verified",
        "implementation": "TRANSITIONAL_PARAMS",
        "notes": "Table J-1 transitional slopes.",
    },
    "take_off_climb_surface": {
        "source": TABLE_J2_REF,
        "status": "operational_verified",
        "implementation": "TOCS_PARAMS",
        "notes": "Table J-2 take-off climb dimensions, slopes, and footnotes for clearways and turning tracks.",
    },
    "outer_horizontal_surface": {
        "source": OHS_GUIDANCE_REF,
        "status": "guidance_only",
        "implementation": "OHS_PARAMS",
        "notes": "GM1 ADR-DSN.H.410 broad specification, not a Table J-1 certification surface.",
    },
    "pa_cat_i_ofz_family_applicability": {
        "source": "GM1 ADR-DSN.J.480(a)",
        "status": "interpretive",
        "implementation": "INNER_APPROACH_PARAMS / INNER_TRANSITIONAL_PARAMS / BALKED_LANDING_PARAMS for PA_I",
        "notes": "CS J.480(a) establishes conical/IHS/approach/transitional for CAT I; GM1 identifies inner approach, inner transitional, and balked landing surfaces for precision approach CAT I.",
    },
}

OLS_TRACEABILITY = {
    "source_publication": SOURCE_PUBLICATION,
    "source_url": SOURCE_URL,
    "table_j1_source_url": TABLE_J1_SOURCE_URL,
    "table_j2_source_url": TABLE_J2_SOURCE_URL,
    "outer_horizontal_source_url": OHS_GUIDANCE_SOURCE_URL,
    "items": OLS_TRACEABILITY_ITEMS,
}

# =========================================================================
# Helper functions
# =========================================================================


def get_ihs_base_height() -> Optional[float]:
    """Return the standard Inner Horizontal Surface height above datum."""
    return IHS_BASE_HEIGHT_AGL


def get_ols_traceability() -> Dict[str, Any]:
    """Return source traceability metadata for EASA OLS rules."""
    return OLS_TRACEABILITY.copy()


def get_tocs_params(
    arc_num: int,
    *,
    clearway_provided: bool = False,
    turning_track_gt_15_deg: bool = False,
) -> Optional[Dict[str, Any]]:
    """Return take-off climb surface parameters with EASA footnotes applied.

    Args:
        arc_num: Aerodrome reference code number, 1 to 4.
        clearway_provided: If True and code 1 or 2, applies the Table J-2
            footnote increasing the inner edge width to 150 m. For code 3/4,
            the normal inner edge is already 180 m.
        turning_track_gt_15_deg: If True for code 3/4, applies the Table J-2
            footnote increasing final width from 1 200 m to 1 800 m where the
            intended track includes heading changes greater than 15 degrees for
            operations in IMC or VMC by night.
    """
    if not isinstance(arc_num, int) or arc_num not in [1, 2, 3, 4]:
        LOGGER.warning("Invalid ARC Number %r for TOCS lookup.", arc_num)
        return None
    params = TOCS_PARAMS.get(arc_num)
    if not params:
        return None
    result = params.copy()
    if clearway_provided:
        result["inner_edge_width"] = result.get("inner_edge_width_clearway", result["inner_edge_width"])
    if turning_track_gt_15_deg and arc_num in [3, 4]:
        result["final_width"] = result.get("final_width_turning", result["final_width"])
    return result


def get_ols_params(
    arc_num: int,
    runway_type_str: Optional[str],
    surface_type: str,
) -> Optional[Dict[str, Any]]:
    """Return OLS parameters for an ARC number, runway type and surface type.

    The return object is a shallow copy of the relevant dictionary so callers
    can modify it without changing the ruleset constants. For the approach
    surface, the return value is a list of section dictionaries, consistent
    with the MOS139 template.
    """
    if not isinstance(arc_num, int) or arc_num not in [1, 2, 3, 4]:
        LOGGER.warning("Invalid ARC Number %r for OLS lookup.", arc_num)
        return None

    rwy_abbr = get_runway_type_abbr(runway_type_str)
    key_arc_type = (arc_num, rwy_abbr)
    surface_type_upper = _normalize_surface_type(surface_type)

    if surface_type_upper == "APPROACH":
        params = APPROACH_PARAMS.get(key_arc_type)
        if not params and rwy_abbr.startswith("PA"):
            params = APPROACH_PARAMS.get((arc_num, "NPA")) or APPROACH_PARAMS.get((arc_num, "NI"))
        return [section.copy() for section in params] if params else None

    if surface_type_upper == "INNERAPPROACH":
        params_dict = INNER_APPROACH_PARAMS
        lookup_key: Any = key_arc_type
    elif surface_type_upper in {"BALKEDLANDING", "BAULKEDLANDING"}:
        params_dict = BALKED_LANDING_PARAMS
        lookup_key = key_arc_type
    elif surface_type_upper in {"TOCS", "TAKEOFFCLIMB", "TAKEOFFCLIMBSURFACE"}:
        return get_tocs_params(arc_num)
    elif surface_type_upper == "IHS":
        params_dict = IHS_PARAMS
        lookup_key = key_arc_type
    elif surface_type_upper in {"CONICAL", "CONICALSURFACE"}:
        params_dict = CONICAL_PARAMS
        lookup_key = key_arc_type
    elif surface_type_upper in {"OHS", "OUTERHORIZONTAL", "OUTERHORIZONTALSURFACE"}:
        params_dict = OHS_PARAMS
        lookup_key = key_arc_type
    elif surface_type_upper in {"TRANSITIONAL", "TRANSITIONALSURFACE"}:
        params_dict = TRANSITIONAL_PARAMS
        lookup_key = key_arc_type
    elif surface_type_upper == "INNERTRANSITIONAL":
        params_dict = INNER_TRANSITIONAL_PARAMS
        lookup_key = key_arc_type
    else:
        LOGGER.warning("Unknown OLS surface type %r requested.", surface_type)
        return None

    params = params_dict.get(lookup_key)
    return params.copy() if params else None


__all__ = [
    "EASA_OLS_REF",
    "TABLE_J1_REF",
    "TABLE_J2_REF",
    "SOURCE_PUBLICATION",
    "SOURCE_URL",
    "TABLE_J1_SOURCE_URL",
    "TABLE_J2_SOURCE_URL",
    "OHS_GUIDANCE_SOURCE_URL",
    "IHS_BASE_HEIGHT_AGL",
    "APPROACH_PARAMS",
    "INNER_APPROACH_PARAMS",
    "INNER_TRANSITIONAL_PARAMS",
    "BALKED_LANDING_PARAMS",
    "BAULKED_LANDING_PARAMS",
    "TOCS_PARAMS",
    "IHS_PARAMS",
    "CONICAL_PARAMS",
    "OHS_PARAMS",
    "TRANSITIONAL_PARAMS",
    "OLS_TRACEABILITY",
    "OLS_TRACEABILITY_ITEMS",
    "get_ihs_base_height",
    "get_ols_traceability",
    "get_tocs_params",
    "get_ols_params",
]
