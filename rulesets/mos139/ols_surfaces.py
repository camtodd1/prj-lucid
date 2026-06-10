# -*- coding: utf-8 -*-
# rulesets/mos139/ols_surfaces.py
"""
Stores Obstacle Limitation Surface (OLS) parameters based on CASA MOS Part 139.

Structure:
Dictionaries map a tuple key (ARC Number, Runway Type Abbreviation) to a
dictionary of parameters for each surface type.

Runway Type Abbreviations Used:
- 'NI': Non-Instrument
- 'NPA': Non-Precision Approach
- 'PA_I': Precision Approach CAT I
- 'PA_II_III': Precision Approach CAT II / III
"""

import logging
from typing import Optional, Dict, Any, Tuple, List

from .classification import PRECISION_APPROACH_TYPES, RUNWAY_TYPE_MAP, get_runway_type_abbr
from .physical_data import (
    PAVEMENT_MOS_REF,
    RESA_PARAMS,
    SHOULDER_MOS_REF,
    STRIP_EXTENSION_PARAMS,
    STRIP_WIDTH_PARAMS,
    get_physical_refs,
    get_resa_params,
    get_strip_params,
)
from .taxiway import TAXIWAY_SEPARATION_PARAMS, get_taxiway_separation_offset

LOGGER = logging.getLogger(__name__)

# =========================================================================
# == Constant Definitions (Basic Refs, etc. - MUST come BEFORE functions)
# =========================================================================
IHS_BASE_HEIGHT_AGL = 45.0  # Standard IHS height - MOS 7.07 Table 7.15(1)

# =========================================================================
# == OLS Parameter Dictionaries
# =========================================================================

# --- Approach Surface ---
# Dimensions based on Code Number and Runway Type.

APPROACH_PARAMS: Dict[Tuple[int, str], List[Dict[str, Any]]] = {
    # --- Non-Instrument (NI) ---
    (1, "NI"): [
        {
            "length": 1600.0,
            "slope": 0.05,
            "divergence": 0.10,
            "start_dist_from_thr": 30.0,
            "start_width": 60.0,
            "ref": "MOS 7.08 Table 7.15(1) (1-NI)",
        }
    ],
    (2, "NI"): [
        {
            "length": 2500.0,
            "slope": 0.04,
            "divergence": 0.10,
            "start_dist_from_thr": 60.0,
            "start_width": 80.0,
            "ref": "MOS 7.08 Table 7.15(1) (2-NI)",
        }
    ],
    (3, "NI"): [
        # Footnote 'a' on width 150m - check text
        {
            "length": 3000.0,
            "slope": 0.0333,
            "divergence": 0.10,
            "start_dist_from_thr": 60.0,
            "start_width": 150.0,
            "ref": "MOS 7.08 Table 7.15(1) (3-NI)",
        }
    ],
    (4, "NI"): [
        {
            "length": 3000.0,
            "slope": 0.025,
            "divergence": 0.10,
            "start_dist_from_thr": 60.0,
            "start_width": 150.0,
            "ref": "MOS 7.08 Table 7.15(1) (4-NI)",
        }
    ],
    # --- Non-Precision Approach (NPA) ---
    (1, "NPA"): [
        {
            "length": 2500.0,
            "slope": 0.0333,
            "divergence": 0.15,
            "start_dist_from_thr": 60.0,
            "start_width": 140.0,
            "ref": "MOS 7.08 Table 7.15(1) (1/2-NPA)",
        }
    ],
    (2, "NPA"): [  # Same as Code 1
        {
            "length": 2500.0,
            "slope": 0.0333,
            "divergence": 0.15,
            "start_dist_from_thr": 60.0,
            "start_width": 140.0,
            "ref": "MOS 7.08 Table 7.15(1) (1/2-NPA)",
        }
    ],
    (3, "NPA"): [
        # Section 1
        {
            "length": 3000.0,
            "slope": 0.02,
            "divergence": 0.15,
            "start_dist_from_thr": 60.0,
            "start_width": 280.0,
            "ref": "MOS 7.08 Table 7.15(1) (3-NPA S1)",
        },
        # Section 2
        {
            "length": 3600.0,
            "slope": 0.025,
            "divergence": 0.15,
            "ref": "MOS 7.08 Table 7.15(1) (3-NPA S2)",
        },  # Footnote c?
        # Horizontal Section (Section 3)
        {
            "length": 8400.0,
            "slope": 0.0,
            "divergence": 0.15,
            "ref": "MOS 7.08 Table 7.15(1) (3-NPA S3/Horiz)",
        },  # Footnote c? Check Total Length d=15000 -> 3000+3600+8400 = 15000
    ],
    (4, "NPA"): [
        # Section 1
        {
            "length": 3000.0,
            "slope": 0.02,
            "divergence": 0.15,
            "start_dist_from_thr": 60.0,
            "start_width": 280.0,
            "ref": "MOS 7.08 Table 7.15(1) (4-NPA S1)",
        },
        # Section 2
        {
            "length": 3600.0,
            "slope": 0.025,
            "divergence": 0.15,
            "ref": "MOS 7.08 Table 7.15(1) (4-NPA S2)",
        },
        # Horizontal Section (Section 3)
        {
            "length": 8400.0,
            "slope": 0.0,
            "divergence": 0.15,
            "ref": "MOS 7.08 Table 7.15(1) (4-NPA S3/Horiz)",
        },  # Check Total Length 15000 -> 3000+3600+8400 = 15000
    ],
    # --- Precision Approach CAT I (PA_I) ---
    (1, "PA_I"): [
        # Section 1
        {
            "length": 3000.0,
            "slope": 0.025,
            "divergence": 0.15,
            "start_dist_from_thr": 60.0,
            "start_width": 140.0,
            "ref": "MOS 7.08 Table 7.15(1) (1/2-PA-CatI S1)",
        },
        # Section 2
        {
            "length": 12000.0,
            "slope": 0.03,
            "divergence": 0.15,
            "ref": "MOS 7.08 Table 7.15(1) (1/2-PA-CatI S2)",
        },  # Check Total Length 15000 -> 3000+12000 = 15000. No horizontal section.
    ],
    (2, "PA_I"): [  # Same as Code 1
        # Section 1
        {
            "length": 3000.0,
            "slope": 0.025,
            "divergence": 0.15,
            "start_dist_from_thr": 60.0,
            "start_width": 140.0,
            "ref": "MOS 7.08 Table 7.15(1) (1/2-PA-CatI S1)",
        },
        # Section 2
        {
            "length": 12000.0,
            "slope": 0.03,
            "divergence": 0.15,
            "ref": "MOS 7.08 Table 7.15(1) (1/2-PA-CatI S2)",
        },
    ],
    (3, "PA_I"): [
        # Section 1
        {
            "length": 3000.0,
            "slope": 0.02,
            "divergence": 0.15,
            "start_dist_from_thr": 60.0,
            "start_width": 280.0,
            "ref": "MOS 7.08 Table 7.15(1) (3/4-PA-CatI S1)",
        },
        # Section 2
        {
            "length": 3600.0,
            "slope": 0.025,
            "divergence": 0.15,
            "ref": "MOS 7.08 Table 7.15(1) (3/4-PA-CatI S2)",
        },
        # Horizontal Section (Section 3)
        {
            "length": 8400.0,
            "slope": 0.0,
            "divergence": 0.15,
            "ref": "MOS 7.08 Table 7.15(1) (3/4-PA-CatI S3/Horiz)",
        },  # Check Total Length 15000 -> 3000+3600+8400 = 15000
    ],
    (4, "PA_I"): [  # Same as Code 3
        # Section 1
        {
            "length": 3000.0,
            "slope": 0.02,
            "divergence": 0.15,
            "start_dist_from_thr": 60.0,
            "start_width": 280.0,
            "ref": "MOS 7.08 Table 7.15(1) (3/4-PA-CatI S1)",
        },
        # Section 2
        {
            "length": 3600.0,
            "slope": 0.025,
            "divergence": 0.15,
            "ref": "MOS 7.08 Table 7.15(1) (3/4-PA-CatI S2)",
        },
        # Horizontal Section (Section 3)
        {
            "length": 8400.0,
            "slope": 0.0,
            "divergence": 0.15,
            "ref": "MOS 7.08 Table 7.15(1) (3/4-PA-CatI S3/Horiz)",
        },
    ],
    # --- Precision Approach CAT II/III (PA_II_III) ---
    # Codes 1 & 2 not applicable
    (3, "PA_II_III"): [
        # Section 1
        {
            "length": 3000.0,
            "slope": 0.02,
            "divergence": 0.15,
            "start_dist_from_thr": 60.0,
            "start_width": 280.0,
            "ref": "MOS 7.08 Table 7.15(1) (3/4-PA-CatII/III S1)",
        },
        # Section 2
        {
            "length": 3600.0,
            "slope": 0.025,
            "divergence": 0.15,
            "ref": "MOS 7.08 Table 7.15(1) (3/4-PA-CatII/III S2)",
        },
        # Horizontal Section (Section 3)
        {
            "length": 8400.0,
            "slope": 0.0,
            "divergence": 0.15,
            "ref": "MOS 7.08 Table 7.15(1) (3/4-PA-CatII/III S3/Horiz)",
        },  # Check Total Length 15000 -> 3000+3600+8400 = 15000
    ],
    (4, "PA_II_III"): [  # Same as Code 3
        # Section 1
        {
            "length": 3000.0,
            "slope": 0.02,
            "divergence": 0.15,
            "start_dist_from_thr": 60.0,
            "start_width": 280.0,
            "ref": "MOS 7.08 Table 7.15(1) (3/4-PA-CatII/III S1)",
        },
        # Section 2
        {
            "length": 3600.0,
            "slope": 0.025,
            "divergence": 0.15,
            "ref": "MOS 7.08 Table 7.15(1) (3/4-PA-CatII/III S2)",
        },
        # Horizontal Section (Section 3)
        {
            "length": 8400.0,
            "slope": 0.0,
            "divergence": 0.15,
            "ref": "MOS 7.08 Table 7.15(1) (3/4-PA-CatII/III S3/Horiz)",
        },
    ],
}

# --- Inner Approach Surface ---
# Applicable only for Precision Approach runways. Based on Table 7.15(1)
INNER_APPROACH_PARAMS: Dict[Tuple[int, str], Dict[str, Any]] = {
    # Precision CAT I
    (1, "PA_I"): {
        "width": 90.0,
        "start_dist_from_thr": 60.0,
        "length": 900.0,
        "slope": 0.025,  # 2.5%
        "ref": "MOS 7.10 (PA-CatI, 1/2)",
    },
    (2, "PA_I"): {  # Same as Code 1
        "width": 90.0,
        "start_dist_from_thr": 60.0,
        "length": 900.0,
        "slope": 0.025,  # 2.5%
        "ref": "MOS 7.10 (PA-CatI, 1/2)",
    },
    (3, "PA_I"): {
        "width": 120.0,
        "start_dist_from_thr": 60.0,
        "length": 900.0,
        "slope": 0.020,  # 2.0%
        "ref": "MOS 7.10 (PA-CatI, 3/4)",
    },
    (4, "PA_I"): {  # Same as Code 3
        "width": 120.0,
        "start_dist_from_thr": 60.0,
        "length": 900.0,
        "slope": 0.020,  # 2.0%
        "ref": "MOS 7.10 (PA-CatI, 3/4)",
    },
    # Precision CAT II & III
    (3, "PA_II_III"): {
        "width": 120.0,
        "start_dist_from_thr": 60.0,
        "length": 900.0,
        "slope": 0.020,  # 2.0%
        "ref": "MOS 7.10 (PA-CatII/III, 3/4)",
    },
    (4, "PA_II_III"): {  # Same as Code 3
        "width": 120.0,
        "start_dist_from_thr": 60.0,
        "length": 900.0,
        "slope": 0.020,  # 2.0%
        "ref": "MOS 7.10 (PA-CatII/III, 3/4)",
    },
    # Non-Instrument ('NI') and Non-Precision ('NPA') types are not listed as the Inner Approach Surface does not apply
    # The get_ols_params function will return None if lookup fails.
}

# --- Inner Transitional Surface (only applies to instrument runways) ---
INNER_TRANSITIONAL_PARAMS: Dict[Tuple[int, str], Dict[str, Any]] = {
    (1, "PA_I"): {"slope": 0.40, "ref": "MOS 7.11/Table 7.15 (1) (PA-CatI, 1/2)"},  # 40%
    (2, "PA_I"): {"slope": 0.40, "ref": "MOS 7.11/Table 7.15 (1) (PA-CatI, 1/2)"},  # 40%
    (3, "PA_I"): {"slope": 0.333, "ref": "MOS 7.11/Table 7.15 (1) (PA-CatI, 3/4)"},  # 33.3%
    (4, "PA_I"): {"slope": 0.333, "ref": "MOS 7.11/Table 7.15 (1) (PA-CatI, 3/4)"},  # 33.3%
    (3, "PA_II_III"): {"slope": 0.333, "ref": "MOS 7.11/Table 7.15 (1) (PA-CatII/III, 3/4)"},  # 33.3%
    (4, "PA_II_III"): {"slope": 0.333, "ref": "MOS 7.11/Table 7.15 (1) (PA-CatII/III, 3/4)"},  # 33.3%
}

# --- Baulked Landing Surface (precision approach runways only) ---
BAULKED_LANDING_PARAMS: Dict[Tuple[int, str], Dict[str, Any]] = {
    # Key: (ARC_Number, Runway_Type_Abbreviation)
    # Runway_Type_Abbreviation: "PA_I" (Precision Approach CAT I), "PA_II_III" (Precision Approach CAT II/III)
    (1, "PA_I"): {
        "width": 90.0,  # Inner width of the Baulked Landing surface (metres)
        "start_dist_from_thr": None,
        "start_dist_rule": "distance_to_end_of_runway_strip",
        "start_dist_ref": "MOS 7.12 Table 7.15(1) note e",
        "divergence": 0.10,  # Divergence per side (e.g., 0.10 for 10%)
        "slope": 0.04,  # Slope (e.g., 0.04 for 4%)
        "ref": "MOS 7.12/Table 7.15 (1) (PA-CatI, 1/2)",
    },
    (2, "PA_I"): {
        "width": 90.0,
        "start_dist_from_thr": None,
        "start_dist_rule": "distance_to_end_of_runway_strip",
        "start_dist_ref": "MOS 7.12 Table 7.15(1) note e",
        "divergence": 0.10,
        "slope": 0.04,
        "ref": "MOS 7.12/Table 7.15 (1) (PA-CatI, 1/2)",
    },
    (3, "PA_I"): {
        "width": 120.0,
        "start_dist_from_thr": 1800.0,
        "start_dist_rule": "1800_m_or_end_of_runway_strip_whichever_is_less",
        "start_dist_ref": "MOS 7.12 Table 7.15(1) note f",
        "divergence": 0.10,
        "slope": 0.033,  # 3.3%
        "code_letter_f_width": 140.0,
        "code_letter_f_width_ref": "MOS 7.12 Table 7.15(1) note g",
        "ref": "MOS 7.12/Table 7.15 (1) (PA-CatI, 3/4)",
    },
    (4, "PA_I"): {
        "width": 120.0,
        "start_dist_from_thr": 1800.0,
        "start_dist_rule": "1800_m_or_end_of_runway_strip_whichever_is_less",
        "start_dist_ref": "MOS 7.12 Table 7.15(1) note f",
        "divergence": 0.10,
        "slope": 0.033,
        "code_letter_f_width": 140.0,
        "code_letter_f_width_ref": "MOS 7.12 Table 7.15(1) note g",
        "ref": "MOS 7.12/Table 7.15 (1) (PA-CatI, 3/4)",
    },
    (3, "PA_II_III"): {
        "width": 120.0,
        "start_dist_from_thr": 1800.0,
        "start_dist_rule": "1800_m_or_end_of_runway_strip_whichever_is_less",
        "start_dist_ref": "MOS 7.12 Table 7.15(1) note f",
        "divergence": 0.10,
        "slope": 0.033,
        "code_letter_f_width": 140.0,
        "code_letter_f_width_ref": "MOS 7.12 Table 7.15(1) note g",
        "ref": "MOS 7.12/Table 7.15 (1) (PA-CatII/III, 3/4)",
    },
    (4, "PA_II_III"): {
        "width": 120.0,
        "start_dist_from_thr": 1800.0,
        "start_dist_rule": "1800_m_or_end_of_runway_strip_whichever_is_less",
        "start_dist_ref": "MOS 7.12 Table 7.15(1) note f",
        "divergence": 0.10,
        "slope": 0.033,
        "code_letter_f_width": 140.0,
        "code_letter_f_width_ref": "MOS 7.12 Table 7.15(1) note g",
        "ref": "MOS 7.12/Table 7.15 (1) (PA-CatII/III, 3/4)",
    },
}

# --- Take-Off Climb Surface (TOCS) ---
# Dimensions vary by Code Number only

TOCS_PARAMS: Dict[int, Dict[str, Any]] = {
    # Key: ARC Number (Code 1, 2, 3, 4)
    # Note: Code 4 uses the same parameters as Code 3
    1: {
        "inner_edge_width": 60.0,  # Length of inner edge (m)
        "origin_offset": 30.0,  # Minimum distance of inner edge from runway end/clearway (m)
        "divergence": 0.10,  # Rate of divergence (each side) as gradient (10% = 0.10)
        "final_width": 380.0,  # Final width (m)
        "length": 1600.0,  # Overall length (m)
        "slope": 0.05,  # Slope as gradient (5% = 0.05)
        "ref": "MOS 7.16 (Code 1)",
    },
    2: {
        "inner_edge_width": 80.0,
        "origin_offset": 60.0,
        "divergence": 0.10,  # 10% = 0.10
        "final_width": 580.0,
        "length": 2500.0,
        "slope": 0.04,  # 4% = 0.04
        "ref": "MOS 7.16 (Code 2)",
    },
    3: {
        "inner_edge_width": 180.0,
        "origin_offset": 60.0,
        "divergence": 0.125,  # 12.5% = 0.125
        "final_width": 1800.0,  # Note 'b' in table, regarding reduced width exception
        "length": 15000.0,  # Overall length (m)
        "slope": 0.02,  # 2% = 0.02
        "ref": "MOS 7.16 (Code 3/4)",
    },
    4: {  # Code 4 uses the same values as Code 3 according to the table
        "inner_edge_width": 180.0,
        "origin_offset": 60.0,
        "divergence": 0.125,  # 12.5% = 0.125
        "final_width": 1800.0,
        "length": 15000.0,
        "slope": 0.02,  # 2% = 0.02 - See note above re: PA runways 1.2% possibility
        "ref": "MOS 7.16 (Code 3/4)",
    },
}

# --- Inner Horizontal Surface (IHS) ---
# Height is 45m above RED (MOS 8.2.18).
# Shape derived from strip ends (MOS 8.2.18).
# Radius values from Table 8.2-1 are stored for reference only.
IHS_PARAMS: Dict[Tuple[int, str], Dict[str, Any]] = {
    # Non-Instrument
    (1, "NI"): {
        "height_agl": 45.0,
        "radius": 2000.0,
        "ref": "MOS 7.07 Table 7.15(1)",
    },
    (2, "NI"): {
        "height_agl": 45.0,
        "radius": 2500.0,
        "ref": "MOS 7.07 Table 7.15(1)",
    },
    (3, "NI"): {
        "height_agl": 45.0,
        "radius": 4000.0,
        "ref": "MOS 7.07 Table 7.15(1)",
    },
    (4, "NI"): {
        "height_agl": 45.0,
        "radius": 4000.0,
        "ref": "MOS 7.07 Table 7.15(1)",
    },
    # Non-Precision Instrument
    (1, "NPA"): {
        "height_agl": 45.0,
        "radius": 3500.0,
        "ref": "MOS 7.07 Table 7.15(1)",
    },
    (2, "NPA"): {
        "height_agl": 45.0,
        "radius": 3500.0,
        "ref": "MOS 7.07 Table 7.15(1)",
    },
    (3, "NPA"): {
        "height_agl": 45.0,
        "radius": 4000.0,
        "ref": "MOS 7.07 Table 7.15(1)",
    },
    (4, "NPA"): {
        "height_agl": 45.0,
        "radius": 4000.0,
        "ref": "MOS 7.07 Table 7.15(1)",
    },
    # Precision CAT I Instrument
    (1, "PA_I"): {
        "height_agl": 45.0,
        "radius": 3500.0,
        "ref": "MOS 7.07 Table 7.15(1)",
    },
    (2, "PA_I"): {
        "height_agl": 45.0,
        "radius": 3500.0,
        "ref": "MOS 7.07 Table 7.15(1)",
    },
    (3, "PA_I"): {
        "height_agl": 45.0,
        "radius": 4000.0,
        "ref": "MOS 7.07 Table 7.15(1)",
    },
    (4, "PA_I"): {
        "height_agl": 45.0,
        "radius": 4000.0,
        "ref": "MOS 7.07 Table 7.15(1)",
    },
    # Precision CAT II & III Instrument
    (3, "PA_II_III"): {
        "height_agl": 45.0,
        "radius": 4000.0,
        "ref": "MOS 7.07 Table 7.15(1)",
    },
    (4, "PA_II_III"): {
        "height_agl": 45.0,
        "radius": 4000.0,
        "ref": "MOS 7.07 Table 7.15(1)",
    },
}

# --- Conical Surface ---
# Starts at periphery of IHS (45m above RED), slopes outwards at 5% (0.05).
# Extends until reaching height specified in Table 8.2-1 ('Height (m)' column for Conical),
# which is interpreted here as height *above the IHS*.
# 'height_extent_agl' is this height difference above the IHS.
# If an OHS is present and this height does not reach the OHS elevation, the
# generator extends the conical on the same plane until it meets OHS per MOS 7.06(3).
CONICAL_PARAMS: Dict[Tuple[int, str], Dict[str, Any]] = {
    # Non-Instrument
    (1, "NI"): {
        "slope": 0.05,
        "height_extent_agl": 35.0,
        "ref": "MOS 7.06 Table 7.15(1)",
    },  # 35m above IHS
    (2, "NI"): {
        "slope": 0.05,
        "height_extent_agl": 55.0,
        "ref": "MOS 7.06 Table 7.15(1)",
    },  # 55m above IHS
    (3, "NI"): {
        "slope": 0.05,
        "height_extent_agl": 75.0,
        "ref": "MOS 7.06 Table 7.15(1)",
    },  # 75m above IHS
    (4, "NI"): {
        "slope": 0.05,
        "height_extent_agl": 100.0,
        "ref": "MOS 7.06 Table 7.15(1)",
    },  # 100m above IHS
    # Non-Precision Instrument
    (1, "NPA"): {
        "slope": 0.05,
        "height_extent_agl": 60.0,
        "ref": "MOS 7.06 Table 7.15(1)",
    },  # 60m above IHS
    (2, "NPA"): {
        "slope": 0.05,
        "height_extent_agl": 60.0,
        "ref": "MOS 7.06 Table 7.15(1)",
    },  # 60m above IHS
    (3, "NPA"): {
        "slope": 0.05,
        "height_extent_agl": 75.0,
        "ref": "MOS 7.06 Table 7.15(1)",
    },  # 75m above IHS
    (4, "NPA"): {
        "slope": 0.05,
        "height_extent_agl": 100.0,
        "ref": "MOS 7.06 Table 7.15(1)",
    },  # 100m above IHS
    # Precision CAT I Instrument
    (1, "PA_I"): {
        "slope": 0.05,
        "height_extent_agl": 60.0,
        "ref": "MOS 7.06 Table 7.15(1)",
    },  # 60m above IHS
    (2, "PA_I"): {
        "slope": 0.05,
        "height_extent_agl": 60.0,
        "ref": "MOS 7.06 Table 7.15(1)",
    },  # 60m above IHS
    (3, "PA_I"): {
        "slope": 0.05,
        "height_extent_agl": 100.0,
        "ref": "MOS 7.06 Table 7.15(1)",
    },  # 100m above IHS
    (4, "PA_I"): {
        "slope": 0.05,
        "height_extent_agl": 100.0,
        "ref": "MOS 7.06 Table 7.15(1)",
    },  # 100m above IHS
    # Precision CAT II & III Instrument
    (3, "PA_II_III"): {
        "slope": 0.05,
        "height_extent_agl": 100.0,
        "ref": "MOS 7.06 Table 7.15(1)",
    },  # 100m above IHS
    (4, "PA_II_III"): {
        "slope": 0.05,
        "height_extent_agl": 100.0,
        "ref": "MOS 7.06 Table 7.15(1)",
    },  # 100m above IHS
}

# --- Outer Horizontal Surface (OHS) ---
# Applies only to Precision runways Code 3 & 4 (MOS 139 7.05 Table 7.15(1)).
# Height is 150m above RED. Radius is 15000m from ARP.
OHS_PARAMS: Dict[Tuple[int, str], Dict[str, Any]] = {
    # Precision CAT I Instrument
    (3, "PA_I"): {"height_agl": 150.0, "radius": 15000.0, "ref": "MOS 7.05 Table 7.15(1)"},
    (4, "PA_I"): {"height_agl": 150.0, "radius": 15000.0, "ref": "MOS 7.05 Table 7.15(1)"},
    # Precision CAT II & III Instrument
    (3, "PA_II_III"): {"height_agl": 150.0, "radius": 15000.0, "ref": "MOS 7.05 Table 7.15(1)"},
    (4, "PA_II_III"): {"height_agl": 150.0, "radius": 15000.0, "ref": "MOS 7.05 Table 7.15(1)"},
}

# --- Transitional Surface ---
# This dictionary holds the slope for the *main* transitional surface.

TRANSITIONAL_PARAMS: Dict[Tuple[int, str], Dict[str, Any]] = {
    # Non-Instrument
    (1, "NI"): {"slope": 0.20, "ref": "MOS 7.09 Table 7.15(1) (NI-1)"},  # 20%
    (2, "NI"): {"slope": 0.20, "ref": "MOS 7.09 Table 7.15(1) (NI-2)"},  # 20%
    (3, "NI"): {"slope": 0.143, "ref": "MOS 7.09 Table 7.15(1) (NI-3)"},  # 14.3% (1:7)
    (4, "NI"): {"slope": 0.143, "ref": "MOS 7.09 Table 7.15(1) (NI-4)"},  # 14.3% (1:7)
    # Non-Precision Approach
    (1, "NPA"): {"slope": 0.20, "ref": "MOS 7.09 Table 7.15(1) (NPA-1/2)"},  # 20%
    (2, "NPA"): {"slope": 0.20, "ref": "MOS 7.09 Table 7.15(1) (NPA-1/2)"},  # 20%
    (3, "NPA"): {"slope": 0.143, "ref": "MOS 7.09 Table 7.15(1) (NPA-3)"},  # 14.3%
    (4, "NPA"): {"slope": 0.143, "ref": "MOS 7.09 Table 7.15(1) (NPA-4)"},  # 14.3%
    # Precision Approach CAT I
    (1, "PA_I"): {"slope": 0.143, "ref": "MOS 7.09 Table 7.15(1) (PA-CatI-1/2)"},  # 14.3%
    (2, "PA_I"): {"slope": 0.143, "ref": "MOS 7.09 Table 7.15(1) (PA-CatI-1/2)"},  # 14.3%
    (3, "PA_I"): {"slope": 0.143, "ref": "MOS 7.09 Table 7.15(1) (PA-CatI-3/4)"},  # 14.3%
    (4, "PA_I"): {"slope": 0.143, "ref": "MOS 7.09 Table 7.15(1) (PA-CatI-3/4)"},  # 14.3%
    # Precision Approach CAT II & III
    # Codes 1 & 2 not applicable for PA CAT II/III in general
    (3, "PA_II_III"): {"slope": 0.143, "ref": "MOS 7.09 Table 7.15(1) (PA-CatII/III-3/4)"},  # 14.3%
    (4, "PA_II_III"): {"slope": 0.143, "ref": "MOS 7.09 Table 7.15(1) (PA-CatII/III-3/4)"},  # 14.3%
}

# =========================================================================
# == Helper Functions
# =========================================================================


def get_ihs_base_height() -> Optional[float]:
    """Returns the standard base height (AGL) for the Inner Horizontal Surface."""
    try:
        return IHS_BASE_HEIGHT_AGL
    except NameError:
        LOGGER.error("IHS_BASE_HEIGHT_AGL constant is not defined.")
        return None


def get_baulked_landing_params(
    arc_num: int,
    runway_type_str: Optional[str],
    arc_let: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Return MOS139 baulked landing parameters with Table 7.15(1) notes applied."""
    if not isinstance(arc_num, int) or arc_num not in [1, 2, 3, 4]:
        LOGGER.warning("Invalid ARC Number %r for Baulked Landing lookup.", arc_num)
        return None

    key = (arc_num, get_runway_type_abbr(runway_type_str))
    params = BAULKED_LANDING_PARAMS.get(key)
    if not params:
        return None

    result = params.copy()
    if (arc_let or "").strip().upper() == "F" and result.get("code_letter_f_width") is not None:
        result["width"] = result["code_letter_f_width"]
        result["width_ref"] = result.get("code_letter_f_width_ref")

    return result


def get_ols_params(arc_num: int, runway_type_str: Optional[str], surface_type: str) -> Optional[Dict[str, Any]]:
    """
    Retrieves OLS parameters based on ARC number, runway type, and surface type.
    Returns None if parameters are not found for the specific combination.
    Handles simplified runway type mapping and potential fallbacks for Approach.
    """
    if not isinstance(arc_num, int) or arc_num not in [1, 2, 3, 4]:
        LOGGER.warning("Invalid ARC Number %r for OLS lookup.", arc_num)
        return None

    rwy_abbr = get_runway_type_abbr(runway_type_str)
    # Default key is (arc_num, rwy_abbr), used for most surfaces
    # Some surfaces like TOCS might only use arc_num.
    key_arc_type = (arc_num, rwy_abbr)
    surface_type_upper = surface_type.upper()

    params_dict: Optional[Dict] = None
    lookup_key: Any = key_arc_type

    if surface_type_upper == "APPROACH":
        params_dict = APPROACH_PARAMS
        # Fallback logic specifically for Approach
        params = params_dict.get(key_arc_type)
        if not params and rwy_abbr.startswith("PA"):  # If PA type not found, try NPA then NI for same ARC
            key_npa = (arc_num, "NPA")
            params = params_dict.get(key_npa)
            if not params:
                key_ni = (arc_num, "NI")
                params = params_dict.get(key_ni)
        return params.copy() if params else None

    elif surface_type_upper == "INNERAPPROACH":
        params_dict = INNER_APPROACH_PARAMS
        # lookup_key remains key_arc_type

    elif surface_type_upper == "BAULKEDLANDING":
        return get_baulked_landing_params(arc_num, runway_type_str)

    elif surface_type_upper == "TOCS":
        params_dict = TOCS_PARAMS
        lookup_key = arc_num  # TOCS params keyed only by ARC number

    elif surface_type_upper == "IHS":
        params_dict = IHS_PARAMS
        # lookup_key remains key_arc_type

    elif surface_type_upper == "CONICAL":
        params_dict = CONICAL_PARAMS
        # lookup_key remains key_arc_type

    elif surface_type_upper == "OHS":
        params_dict = OHS_PARAMS
        # lookup_key remains key_arc_type

    elif surface_type_upper == "TRANSITIONAL":  # Main Transitional
        params_dict = TRANSITIONAL_PARAMS
        # lookup_key remains key_arc_type

    elif surface_type_upper == "INNERTRANSITIONAL":  # Placeholder for specific Inner Transitional params
        params_dict = INNER_TRANSITIONAL_PARAMS  # If you have specific params for it
        # lookup_key remains key_arc_type

    else:
        LOGGER.warning("Unknown OLS surface type %r requested.", surface_type)
        return None

    # Common lookup for most types (except Approach which returned earlier)
    if params_dict is not None:
        params = params_dict.get(lookup_key)
        return params.copy() if params else None
    else:
        # This path should ideally not be reached if surface_type_upper matched a known type
        # and params_dict was assigned. Could happen if a params_dict (e.g. BAULKED_LANDING_PARAMS)
        # was not defined at the module level.
        LOGGER.warning(
            "Parameter dictionary is missing for known OLS surface type %r.",
            surface_type_upper,
        )
        return None


# =========================================================================
# == End of File
# =========================================================================
