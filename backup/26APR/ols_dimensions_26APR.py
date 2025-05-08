# -*- coding: utf-8 -*-
# ols_dimensions.py
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

from typing import Optional, Dict, Any, Tuple, List

# =========================================================================
# == Runway Approach Types
# =========================================================================

RUNWAY_TYPE_MAP = {
    "": "NI", # Treat empty string as Non-Instrument
    "Non-Instrument (NI)": "NI",
    "Non-Precision Approach (NPA)": "NPA",
    "Precision Approach CAT I": "PA_I",
    "Precision Approach CAT II/III": "PA_II_III",
}

# =========================================================================
# == OLS Parameter Dictionaries
# =========================================================================

# --- Approach Surface ---
# Dimensions based on Code Number and Runway Type.

APPROACH_PARAMS: Dict[Tuple[int, str], List[Dict[str, Any]]] = {
    # --- Non-Instrument (NI) ---
    (1, 'NI'): [
        {'length': 1600.0, 'slope': 0.05, 'divergence': 0.10, 'start_dist_from_thr': 30.0, 'start_width': 60.0, 'ref': "MOS T8.2-1 (1-NI)"}
    ],
    (2, 'NI'): [
        {'length': 2500.0, 'slope': 0.04, 'divergence': 0.10, 'start_dist_from_thr': 60.0, 'start_width': 80.0, 'ref': "MOS T8.2-1 (2-NI)"}
    ],
    (3, 'NI'): [
        # Footnote 'a' on width 150m - check text
        {'length': 3000.0, 'slope': 0.0333, 'divergence': 0.10, 'start_dist_from_thr': 60.0, 'start_width': 150.0, 'ref': "MOS T8.2-1 (3-NI)"}
    ],
    (4, 'NI'): [
        {'length': 3000.0, 'slope': 0.025, 'divergence': 0.10, 'start_dist_from_thr': 60.0, 'start_width': 150.0, 'ref': "MOS T8.2-1 (4-NI)"}
    ],
    
    # --- Non-Precision Approach (NPA) ---
    (1, 'NPA'): [
        {'length': 2500.0, 'slope': 0.0333, 'divergence': 0.15, 'start_dist_from_thr': 60.0, 'start_width': 140.0, 'ref': "MOS T8.2-1 (1/2-NPA)"}
    ],
    (2, 'NPA'): [ # Same as Code 1
        {'length': 2500.0, 'slope': 0.0333, 'divergence': 0.15, 'start_dist_from_thr': 60.0, 'start_width': 140.0, 'ref': "MOS T8.2-1 (1/2-NPA)"}
    ],
    (3, 'NPA'): [
        # Section 1
        {'length': 3000.0, 'slope': 0.02, 'divergence': 0.15, 'start_dist_from_thr': 60.0, 'start_width': 280.0, 'ref': "MOS T8.2-1 (3-NPA S1)"},
        # Section 2
        {'length': 3600.0, 'slope': 0.025, 'divergence': 0.15, 'ref': "MOS T8.2-1 (3-NPA S2)"}, # Footnote c?
        # Horizontal Section (Section 3)
        {'length': 8400.0, 'slope': 0.0, 'divergence': 0.15, 'ref': "MOS T8.2-1 (3-NPA S3/Horiz)"} # Footnote c? Check Total Length d=15000 -> 3000+3600+8400 = 15000
    ],
    (4, 'NPA'): [
        # Section 1
        {'length': 3000.0, 'slope': 0.02, 'divergence': 0.15, 'start_dist_from_thr': 60.0, 'start_width': 280.0, 'ref': "MOS T8.2-1 (4-NPA S1)"},
        # Section 2
        {'length': 3600.0, 'slope': 0.025, 'divergence': 0.15, 'ref': "MOS T8.2-1 (4-NPA S2)"},
        # Horizontal Section (Section 3)
        {'length': 8400.0, 'slope': 0.0, 'divergence': 0.15, 'ref': "MOS T8.2-1 (4-NPA S3/Horiz)"} # Check Total Length 15000 -> 3000+3600+8400 = 15000
    ],
    
    # --- Precision Approach CAT I (PA_I) ---
    (1, 'PA_I'): [
        # Section 1
        {'length': 3000.0, 'slope': 0.025, 'divergence': 0.15, 'start_dist_from_thr': 60.0, 'start_width': 140.0, 'ref': "MOS T8.2-1 (1/2-PAI S1)"},
        # Section 2
        {'length': 12000.0, 'slope': 0.03, 'divergence': 0.15, 'ref': "MOS T8.2-1 (1/2-PAI S2)"} # Check Total Length 15000 -> 3000+12000 = 15000. No horizontal section.
    ],
    (2, 'PA_I'): [ # Same as Code 1
        # Section 1
        {'length': 3000.0, 'slope': 0.025, 'divergence': 0.15, 'start_dist_from_thr': 60.0, 'start_width': 140.0, 'ref': "MOS T8.2-1 (1/2-PAI S1)"},
        # Section 2
        {'length': 12000.0, 'slope': 0.03, 'divergence': 0.15, 'ref': "MOS T8.2-1 (1/2-PAI S2)"}
    ],
    (3, 'PA_I'): [
        # Section 1
        {'length': 3000.0, 'slope': 0.02, 'divergence': 0.15, 'start_dist_from_thr': 60.0, 'start_width': 280.0, 'ref': "MOS T8.2-1 (3/4-PAI S1)"},
        # Section 2
        {'length': 3600.0, 'slope': 0.025, 'divergence': 0.15, 'ref': "MOS T8.2-1 (3/4-PAI S2)"},
        # Horizontal Section (Section 3)
        {'length': 8400.0, 'slope': 0.0, 'divergence': 0.15, 'ref': "MOS T8.2-1 (3/4-PAI S3/Horiz)"} # Check Total Length 15000 -> 3000+3600+8400 = 15000
    ],
    (4, 'PA_I'): [ # Same as Code 3
        # Section 1
        {'length': 3000.0, 'slope': 0.02, 'divergence': 0.15, 'start_dist_from_thr': 60.0, 'start_width': 280.0, 'ref': "MOS T8.2-1 (3/4-PAI S1)"},
        # Section 2
        {'length': 3600.0, 'slope': 0.025, 'divergence': 0.15, 'ref': "MOS T8.2-1 (3/4-PAI S2)"},
        # Horizontal Section (Section 3)
        {'length': 8400.0, 'slope': 0.0, 'divergence': 0.15, 'ref': "MOS T8.2-1 (3/4-PAI S3/Horiz)"}
    ],
    
    # --- Precision Approach CAT II/III (PA_II_III) ---
    # Codes 1 & 2 not applicable
    (3, 'PA_II_III'): [
        # Section 1
        {'length': 3000.0, 'slope': 0.02, 'divergence': 0.15, 'start_dist_from_thr': 60.0, 'start_width': 280.0, 'ref': "MOS T8.2-1 (3/4-PAII/III S1)"},
        # Section 2
        {'length': 3600.0, 'slope': 0.025, 'divergence': 0.15, 'ref': "MOS T8.2-1 (3/4-PAII/III S2)"},
        # Horizontal Section (Section 3)
        {'length': 8400.0, 'slope': 0.0, 'divergence': 0.15, 'ref': "MOS T8.2-1 (3/4-PAII/III S3/Horiz)"} # Check Total Length 15000 -> 3000+3600+8400 = 15000
    ],
    (4, 'PA_II_III'): [ # Same as Code 3
        # Section 1
        {'length': 3000.0, 'slope': 0.02, 'divergence': 0.15, 'start_dist_from_thr': 60.0, 'start_width': 280.0, 'ref': "MOS T8.2-1 (3/4-PAII/III S1)"},
        # Section 2
        {'length': 3600.0, 'slope': 0.025, 'divergence': 0.15, 'ref': "MOS T8.2-1 (3/4-PAII/III S2)"},
        # Horizontal Section (Section 3)
        {'length': 8400.0, 'slope': 0.0, 'divergence': 0.15, 'ref': "MOS T8.2-1 (3/4-PAII/III S3/Horiz)"}
    ]
}

# --- Inner Approach Surface ---
# Applicable only for Precision Approach runways. Based on Table 7.15(1)
INNER_APPROACH_PARAMS: Dict[Tuple[int, str], Dict[str, Any]] = {
    # Precision CAT I
    (1, 'PA_I'): {
        'width': 90.0,
        'start_dist_from_thr': 60.0,
        'length': 900.0,
        'slope': 0.025, # 2.5%
        'ref': "MOS 139 7.10 (Inner App, PA-I, 1/2)"
    },
    (2, 'PA_I'): { # Same as Code 1
        'width': 90.0,
        'start_dist_from_thr': 60.0,
        'length': 900.0,
        'slope': 0.025, # 2.5%
        'ref': "MOS 139 7.10 (Inner App, PA-I, 1/2)"
    },
    (3, 'PA_I'): {
        'width': 120.0,
        'start_dist_from_thr': 60.0,
        'length': 900.0,
        'slope': 0.020, # 2.0%
        'ref': "MOS 139 7.10 (Inner App, PA-I, 3/4)"
    },
    (4, 'PA_I'): { # Same as Code 3
        'width': 120.0,
        'start_dist_from_thr': 60.0,
        'length': 900.0,
        'slope': 0.020, # 2.0%
        'ref': "MOS 139 7.10 (Inner App, PA-I, 3/4)"
    },
    
    # Precision CAT II & III
    (3, 'PA_II_III'): {
        'width': 120.0,
        'start_dist_from_thr': 60.0,
        'length': 900.0,
        'slope': 0.020, # 2.0%
        'ref': "MOS 139 7.10 (Inner App, PA-II/III, 3/4)"
    },
    (4, 'PA_II_III'): { # Same as Code 3
        'width': 120.0,
        'start_dist_from_thr': 60.0,
        'length': 900.0,
        'slope': 0.020, # 2.0%
        'ref': "MOS 139 7.10 (Inner App, PA-II/III, 3/4)"
    },
    
    # Non-Instrument ('NI') and Non-Precision ('NPA') types are not listed as the Inner Approach Surface does not apply
    # The get_ols_params function will return None if lookup fails.
}

# --- Take-Off Climb Surface (TOCS) ---
# Dimensions vary by Code Number only

TOCS_PARAMS: Dict[int, Dict[str, Any]] = {
    # Key: ARC Number (Code 1, 2, 3, 4)
    # Note: Code 4 uses the same parameters as Code 3
    
    1: {
        'inner_edge_width': 60.0,             # Length of inner edge (m)
        'origin_offset': 30.0,              # Minimum distance of inner edge from runway end/clearway (m)
        'divergence': 0.10,                 # Rate of divergence (each side) as gradient (10% = 0.10)
        'final_width': 380.0,               # Final width (m)
        'length': 1600.0,                   # Overall length (m)
        'slope': 0.05,                      # Slope as gradient (5% = 0.05)
        'ref': "MOS 139 7.16 (Code 1)"
        },
    2: {
        'inner_edge_width': 80.0,
        'origin_offset': 60.0,
        'divergence': 0.10,                 # 10% = 0.10
        'final_width': 580.0,
        'length': 2500.0,
        'slope': 0.04,                      # 4% = 0.04
        'ref': "MOS 139 7.16 (Code 2)"
        },
    3: {
        'inner_edge_width': 180.0,
        'origin_offset': 60.0,
        'divergence': 0.125,                # 12.5% = 0.125
        'final_width': 1800.0,              # Note 'b' in table, regarding reduced width exception
        'length': 15000.0,                  # Overall length (m)
        'slope': 0.02,                      # 2% = 0.02
        'ref': "MOS 139 7.16 (Code 3/4)"
        },
    4: { # Code 4 uses the same values as Code 3 according to the table
        'inner_edge_width': 180.0,
        'origin_offset': 60.0,
        'divergence': 0.125,                # 12.5% = 0.125
        'final_width': 1800.0,
        'length': 15000.0,
        'slope': 0.02,                      # 2% = 0.02 - See note above re: PA runways 1.2% possibility
        'ref': "MOS 139 7.16 (Code 3/4)"
        }
}

# --- Inner Horizontal Surface (IHS) ---
# Height is 45m above RED (MOS 139 8.2.18).
# Shape derived from strip ends (MOS 139 8.2.18).
# Radius values from Table 8.2-1 are stored for reference only.
IHS_PARAMS: Dict[Tuple[int, str], Dict[str, Any]] = {
    # Non-Instrument
    (1, 'NI'): {'height_agl': 45.0, 'radius': 2000.0, 'ref': "MOS 139 8.2.18 / T8.2-1 (Verify)"},
    (2, 'NI'): {'height_agl': 45.0, 'radius': 2500.0, 'ref': "MOS 139 8.2.18 / T8.2-1 (Verify)"},
    (3, 'NI'): {'height_agl': 45.0, 'radius': 4000.0, 'ref': "MOS 139 8.2.18 / T8.2-1 (Verify)"},
    (4, 'NI'): {'height_agl': 45.0, 'radius': 4000.0, 'ref': "MOS 139 8.2.18 / T8.2-1 (Verify)"},
    # Non-Precision Instrument
    (1, 'NPA'): {'height_agl': 45.0, 'radius': 3500.0, 'ref': "MOS 139 8.2.18 / T8.2-1 (Verify)"},
    (2, 'NPA'): {'height_agl': 45.0, 'radius': 3500.0, 'ref': "MOS 139 8.2.18 / T8.2-1 (Verify)"},
    (3, 'NPA'): {'height_agl': 45.0, 'radius': 4000.0, 'ref': "MOS 139 8.2.18 / T8.2-1 (Verify)"},
    (4, 'NPA'): {'height_agl': 45.0, 'radius': 4000.0, 'ref': "MOS 139 8.2.18 / T8.2-1 (Verify)"},
    # Precision CAT I Instrument
    (1, 'PA_I'): {'height_agl': 45.0, 'radius': 3500.0, 'ref': "MOS 139 8.2.18 / T8.2-1 (Verify)"},
    (2, 'PA_I'): {'height_agl': 45.0, 'radius': 3500.0, 'ref': "MOS 139 8.2.18 / T8.2-1 (Verify)"},
    (3, 'PA_I'): {'height_agl': 45.0, 'radius': 4000.0, 'ref': "MOS 139 8.2.18 / T8.2-1 (Verify)"},
    (4, 'PA_I'): {'height_agl': 45.0, 'radius': 4000.0, 'ref': "MOS 139 8.2.18 / T8.2-1 (Verify)"},
    # Precision CAT II & III Instrument
    (3, 'PA_II_III'): {'height_agl': 45.0, 'radius': 4000.0, 'ref': "MOS 139 8.2.18 / T8.2-1 (Verify)"},
    (4, 'PA_II_III'): {'height_agl': 45.0, 'radius': 4000.0, 'ref': "MOS 139 8.2.18 / T8.2-1 (Verify)"},
}

# --- Conical Surface ---
# Starts at periphery of IHS (45m above RED), slopes outwards at 5% (0.05).
# Extends until reaching height specified in Table 8.2-1 ('Height (m)' column for Conical),
# which is interpreted here as height *above the IHS*.
# 'height_extent_agl' is this height difference above the IHS.
# VERIFY interpretation against MOS 139 8.2.19.
CONICAL_PARAMS: Dict[Tuple[int, str], Dict[str, Any]] = {
    # Non-Instrument
    (1, 'NI'): {'slope': 0.05, 'height_extent_agl': 35.0, 'ref': "MOS 139 8.2.19 / T8.2-1 (Verify Height)"}, # 35m above IHS
    (2, 'NI'): {'slope': 0.05, 'height_extent_agl': 55.0, 'ref': "MOS 139 8.2.19 / T8.2-1 (Verify Height)"}, # 55m above IHS
    (3, 'NI'): {'slope': 0.05, 'height_extent_agl': 75.0, 'ref': "MOS 139 8.2.19 / T8.2-1 (Verify Height)"}, # 75m above IHS
    (4, 'NI'): {'slope': 0.05, 'height_extent_agl': 100.0, 'ref': "MOS 139 8.2.19 / T8.2-1 (Verify Height)"},# 100m above IHS
    # Non-Precision Instrument
    (1, 'NPA'): {'slope': 0.05, 'height_extent_agl': 60.0, 'ref': "MOS 139 8.2.19 / T8.2-1 (Verify Height)"}, # 60m above IHS
    (2, 'NPA'): {'slope': 0.05, 'height_extent_agl': 60.0, 'ref': "MOS 139 8.2.19 / T8.2-1 (Verify Height)"}, # 60m above IHS
    (3, 'NPA'): {'slope': 0.05, 'height_extent_agl': 75.0, 'ref': "MOS 139 8.2.19 / T8.2-1 (Verify Height)"}, # 75m above IHS
    (4, 'NPA'): {'slope': 0.05, 'height_extent_agl': 100.0, 'ref': "MOS 139 8.2.19 / T8.2-1 (Verify Height)"},# 100m above IHS
    # Precision CAT I Instrument
    (1, 'PA_I'): {'slope': 0.05, 'height_extent_agl': 60.0, 'ref': "MOS 139 8.2.19 / T8.2-1 (Verify Height)"}, # 60m above IHS
    (2, 'PA_I'): {'slope': 0.05, 'height_extent_agl': 60.0, 'ref': "MOS 139 8.2.19 / T8.2-1 (Verify Height)"}, # 60m above IHS
    (3, 'PA_I'): {'slope': 0.05, 'height_extent_agl': 100.0, 'ref': "MOS 139 8.2.19 / T8.2-1 (Verify Height)"},# 100m above IHS
    (4, 'PA_I'): {'slope': 0.05, 'height_extent_agl': 100.0, 'ref': "MOS 139 8.2.19 / T8.2-1 (Verify Height)"},# 100m above IHS
    # Precision CAT II & III Instrument
    (3, 'PA_II_III'): {'slope': 0.05, 'height_extent_agl': 100.0, 'ref': "MOS 139 8.2.19 / T8.2-1 (Verify Height)"},# 100m above IHS
    (4, 'PA_II_III'): {'slope': 0.05, 'height_extent_agl': 100.0, 'ref': "MOS 139 8.2.19 / T8.2-1 (Verify Height)"},# 100m above IHS
}

# --- Outer Horizontal Surface (OHS) ---
# Applies only to Precision runways Code 3 & 4 (MOS 139 8.2.20).
# Height is 150m above RED. Radius is 15000m from ARP.
OHS_PARAMS: Dict[Tuple[int, str], Dict[str, Any]] = {
    # Precision CAT I Instrument
    (3, 'PA_I'): {'height_agl': 150.0, 'radius': 15000.0, 'ref': "MOS 139 8.2.20"},
    (4, 'PA_I'): {'height_agl': 150.0, 'radius': 15000.0, 'ref': "MOS 139 8.2.20"},
    # Precision CAT II & III Instrument
    (3, 'PA_II_III'): {'height_agl': 150.0, 'radius': 15000.0, 'ref': "MOS 139 8.2.20"},
    (4, 'PA_II_III'): {'height_agl': 150.0, 'radius': 15000.0, 'ref': "MOS 139 8.2.20"},
}

# --- Transitional Surface ---
# Main transitional slope depends on Code Number (MOS 139 8.2.17).
# Inner transitional surface applies for PA CAT II/III (MOS 139 8.2.16) - NOT FULLY IMPLEMENTED HERE.
# VERIFY ALL VALUES AGAINST MOS 139.
TRANSITIONAL_PARAMS: Dict[int, Dict[str, Any]] = {
    # Key: ARC Number
    1: {'slope': 0.200, 'ref': "MOS 139 8.2.17 (Code 1/2)"}, # 1:5
    2: {'slope': 0.200, 'ref': "MOS 139 8.2.17 (Code 1/2)"}, # 1:5
    3: {'slope': 0.143, 'ref': "MOS 139 8.2.17 (Code 3/4)"}, # 1:7
    4: {'slope': 0.143, 'ref': "MOS 139 8.2.17 (Code 3/4)"}, # 1:7
    # Inner Transitional for PA CAT II/III has slope 1:3 (0.333) - see 8.2.16(b)
    # Need logic in get_ols_params or calling function to handle this.
}

# =========================================================================
# == Taxiway Minimum Separation Parameters
# =========================================================================

# Stores offset distance (m) from runway centerline to parallel taxiway centerline.
# Key: (ARC Num, ARC Letter, Runway Type Abbreviation)
# VERIFY ALL VALUES AGAINST MOS 139 Section 9.3 / Table 9.1
TAXIWAY_SEPARATION_PARAMS: Dict[Tuple[int, str, str], Dict[str, Any]] = {
    # --- Precision Approach Runways (CAT I, II, III) ---
    # ARC Code 1
    (1, 'A', 'PA_I'): {'offset_m': 77.5, 'ref': "MOS 139 T9.1 (Verify 1A-PA)"},
    (1, 'B', 'PA_I'): {'offset_m': 82.0, 'ref': "MOS 139 T9.1 (Verify 1B-PA)"},
    (1, 'C', 'PA_I'): {'offset_m': 88.0, 'ref': "MOS 139 T9.1 (Verify 1C-PA)"},
    (1, 'A', 'PA_II_III'): {'offset_m': 77.5, 'ref': "MOS 139 T9.1 (Verify 1A-PA)"},
    (1, 'B', 'PA_II_III'): {'offset_m': 82.0, 'ref': "MOS 139 T9.1 (Verify 1B-PA)"},
    (1, 'C', 'PA_II_III'): {'offset_m': 88.0, 'ref': "MOS 139 T9.1 (Verify 1C-PA)"},
    # ARC Code 2
    (2, 'A', 'PA_I'): {'offset_m': 77.5, 'ref': "MOS 139 T9.1 (Verify 2A-PA)"},
    (2, 'B', 'PA_I'): {'offset_m': 82.0, 'ref': "MOS 139 T9.1 (Verify 2B-PA)"},
    (2, 'C', 'PA_I'): {'offset_m': 88.0, 'ref': "MOS 139 T9.1 (Verify 2C-PA)"},
    (2, 'A', 'PA_II_III'): {'offset_m': 77.5, 'ref': "MOS 139 T9.1 (Verify 2A-PA)"},
    (2, 'B', 'PA_II_III'): {'offset_m': 82.0, 'ref': "MOS 139 T9.1 (Verify 2B-PA)"},
    (2, 'C', 'PA_II_III'): {'offset_m': 88.0, 'ref': "MOS 139 T9.1 (Verify 2C-PA)"},
    # ARC Code 3
    (3, 'A', 'PA_I'): {'offset_m': 152.0, 'ref': "MOS 139 T9.1 (Verify 3A-PA)"},
    (3, 'B', 'PA_I'): {'offset_m': 152.0, 'ref': "MOS 139 T9.1 (Verify 3B-PA)"},
    (3, 'C', 'PA_I'): {'offset_m': 158.0, 'ref': "MOS 139 T9.1 (Verify 3C-PA)"},
    (3, 'D', 'PA_I'): {'offset_m': 166.0, 'ref': "MOS 139 T9.1 (Verify 3D-PA)"},
    (3, 'E', 'PA_I'): {'offset_m': 172.5, 'ref': "MOS 139 T9.1 (Verify 3E-PA)"},
    (3, 'F', 'PA_I'): {'offset_m': 180.0, 'ref': "MOS 139 T9.1 (Verify 3F-PA)"},
    (3, 'A', 'PA_II_III'): {'offset_m': 152.0, 'ref': "MOS 139 T9.1 (Verify 3A-PA)"},
    (3, 'B', 'PA_II_III'): {'offset_m': 152.0, 'ref': "MOS 139 T9.1 (Verify 3B-PA)"},
    (3, 'C', 'PA_II_III'): {'offset_m': 158.0, 'ref': "MOS 139 T9.1 (Verify 3C-PA)"},
    (3, 'D', 'PA_II_III'): {'offset_m': 166.0, 'ref': "MOS 139 T9.1 (Verify 3D-PA)"},
    (3, 'E', 'PA_II_III'): {'offset_m': 172.5, 'ref': "MOS 139 T9.1 (Verify 3E-PA)"},
    (3, 'F', 'PA_II_III'): {'offset_m': 180.0, 'ref': "MOS 139 T9.1 (Verify 3F-PA)"},
    # ARC Code 4
    (4, 'C', 'PA_I'): {'offset_m': 158.0, 'ref': "MOS 139 T9.1 (Verify 4C-PA)"},
    (4, 'D', 'PA_I'): {'offset_m': 166.0, 'ref': "MOS 139 T9.1 (Verify 4D-PA)"},
    (4, 'E', 'PA_I'): {'offset_m': 172.5, 'ref': "MOS 139 T9.1 (Verify 4E-PA)"},
    (4, 'F', 'PA_I'): {'offset_m': 180.0, 'ref': "MOS 139 T9.1 (Verify 4F-PA)"},
    (4, 'C', 'PA_II_III'): {'offset_m': 158.0, 'ref': "MOS 139 T9.1 (Verify 4C-PA)"},
    (4, 'D', 'PA_II_III'): {'offset_m': 166.0, 'ref': "MOS 139 T9.1 (Verify 4D-PA)"},
    (4, 'E', 'PA_II_III'): {'offset_m': 172.5, 'ref': "MOS 139 T9.1 (Verify 4E-PA)"},
    (4, 'F', 'PA_II_III'): {'offset_m': 180.0, 'ref': "MOS 139 T9.1 (Verify 4F-PA)"},
    
    # --- Non-Precision Approach (NPA) Runways ---
    # ARC Code 1
    (1, 'A', 'NPA'): {'offset_m': 77.5, 'ref': "MOS 139 T9.1 (Verify 1A-NPA)"},
    (1, 'B', 'NPA'): {'offset_m': 82.0, 'ref': "MOS 139 T9.1 (Verify 1B-NPA)"},
    (1, 'C', 'NPA'): {'offset_m': 88.0, 'ref': "MOS 139 T9.1 (Verify 1C-NPA)"},
    # ARC Code 2
    (2, 'A', 'NPA'): {'offset_m': 77.5, 'ref': "MOS 139 T9.1 (Verify 2A-NPA)"},
    (2, 'B', 'NPA'): {'offset_m': 82.0, 'ref': "MOS 139 T9.1 (Verify 2B-NPA)"},
    (2, 'C', 'NPA'): {'offset_m': 88.0, 'ref': "MOS 139 T9.1 (Verify 2C-NPA)"},
    # ARC Code 3
    (3, 'A', 'NPA'): {'offset_m': 152.0, 'ref': "MOS 139 T9.1 (Verify 3A-NPA)"},
    (3, 'B', 'NPA'): {'offset_m': 152.0, 'ref': "MOS 139 T9.1 (Verify 3B-NPA)"},
    (3, 'C', 'NPA'): {'offset_m': 158.0, 'ref': "MOS 139 T9.1 (Verify 3C-NPA)"},
    (3, 'D', 'NPA'): {'offset_m': 166.0, 'ref': "MOS 139 T9.1 (Verify 3D-NPA)"},
    (3, 'E', 'NPA'): {'offset_m': 172.5, 'ref': "MOS 139 T9.1 (Verify 3E-NPA)"},
    (3, 'F', 'NPA'): {'offset_m': 180.0, 'ref': "MOS 139 T9.1 (Verify 3F-NPA)"},
    # ARC Code 4
    (4, 'C', 'NPA'): {'offset_m': 158.0, 'ref': "MOS 139 T9.1 (Verify 4C-NPA)"},
    (4, 'D', 'NPA'): {'offset_m': 166.0, 'ref': "MOS 139 T9.1 (Verify 4D-NPA)"},
    (4, 'E', 'NPA'): {'offset_m': 172.5, 'ref': "MOS 139 T9.1 (Verify 4E-NPA)"},
    (4, 'F', 'NPA'): {'offset_m': 180.0, 'ref': "MOS 139 T9.1 (Verify 4F-NPA)"},
    
    # --- Non-Instrument (NI) Runways --- <<< ADD THIS SECTION >>>
    # ARC Code 1
    (1, 'A', 'NI'): {'offset_m': 37.5, 'ref': "MOS 139 T9.1 (Verify 1A-NI)"},
    (1, 'B', 'NI'): {'offset_m': 42.0, 'ref': "MOS 139 T9.1 (Verify 1B-NI)"},
    (1, 'C', 'NI'): {'offset_m': 48.0, 'ref': "MOS 139 T9.1 (Verify 1C-NI)"},
    # ARC Code 2
    (2, 'A', 'NI'): {'offset_m': 47.5, 'ref': "MOS 139 T9.1 (Verify 2A-NI)"},
    (2, 'B', 'NI'): {'offset_m': 52.0, 'ref': "MOS 139 T9.1 (Verify 2B-NI)"},
    (2, 'C', 'NI'): {'offset_m': 58.0, 'ref': "MOS 139 T9.1 (Verify 2C-NI)"},
    # ARC Code 3
    (3, 'A', 'NI'): {'offset_m': 52.5, 'ref': "MOS 139 T9.1 (Verify 3A-NI)"},
    (3, 'B', 'NI'): {'offset_m': 87.0, 'ref': "MOS 139 T9.1 (Verify 3B-NI)"},
    (3, 'C', 'NI'): {'offset_m': 93.0, 'ref': "MOS 139 T9.1 (Verify 3C-NI)"},
    (3, 'D', 'NI'): {'offset_m': 101.0, 'ref': "MOS 139 T9.1 (Verify 3D-NI)"},
    (3, 'E', 'NI'): {'offset_m': 107.5, 'ref': "MOS 139 T9.1 (Verify 3E-NI)"},
    (3, 'F', 'NI'): {'offset_m': 115.0, 'ref': "MOS 139 T9.1 (Verify 3F-NI)"},
    # ARC Code 4
    (4, 'C', 'NI'): {'offset_m': 93.0, 'ref': "MOS 139 T9.1 (Verify 4C-NI)"},
    (4, 'D', 'NI'): {'offset_m': 101.0, 'ref': "MOS 139 T9.1 (Verify 4D-NI)"},
    (4, 'E', 'NI'): {'offset_m': 107.5, 'ref': "MOS 139 T9.1 (Verify 4E-NI)"},
    (4, 'F', 'NI'): {'offset_m': 115.0, 'ref': "MOS 139 T9.1 (Verify 4F-NI)"},
}

# =========================================================================
# == Helper Functions
# =========================================================================

def get_runway_type_abbr(runway_type_str: Optional[str]) -> str:
    """Maps the exact descriptive runway type string from UI to a simplified abbreviation."""
    if runway_type_str is None:
        return "NI" # Default if None is passed
    
    # Use .get() with a default value for safety, handle potential whitespace
    abbr = RUNWAY_TYPE_MAP.get(runway_type_str.strip())
    
    if abbr is None:
        # This case should ideally not happen if input comes only from the known combo box list
        # or if callers pass valid strings
        print(f"[ols_dimensions WARNING] Unknown runway type string '{runway_type_str}' could not be mapped, defaulting to NI.")
        return "NI"
    else:
        return abbr

def get_ols_params(arc_num: int, runway_type_str: Optional[str], surface_type: str) -> Optional[Dict[str, Any]]:
    """
    Retrieves OLS parameters based on ARC number, runway type, and surface type.
    Returns None if parameters are not found for the specific combination.
    Handles simplified runway type mapping and potential fallbacks for Approach.
    """
    # Add print/log at the beginning to see exact inputs received
    print(f"[ols_dimensions DEBUG] get_ols_params received: arc_num={arc_num!r}, type_str={runway_type_str!r}, surface={surface_type!r}")
    
    if not isinstance(arc_num, int) or arc_num not in [1, 2, 3, 4]:
        print(f"Error: Invalid ARC Number '{arc_num}' for OLS lookup.")
        return None

    rwy_abbr = get_runway_type_abbr(runway_type_str)
    key = (arc_num, rwy_abbr)
    surface_type_upper = surface_type.upper()
    print(f"[ols_dimensions DEBUG] Using key: {key!r} for surface: {surface_type_upper!r}") # Log the key being used

    params_dict: Optional[Dict] = None # The dictionary containing parameters for the surface type
    lookup_key: Any = key # The key to use for lookup (might change for TOCS/Transitional)

    if surface_type_upper == 'APPROACH':
        params_dict = APPROACH_PARAMS
        lookup_key = key
        params = params_dict.get(lookup_key)
        # Fallback logic specifically for Approach if PA type not found
        if not params and rwy_abbr.startswith('PA'):
             key_npa = (arc_num, 'NPA')
             params = params_dict.get(key_npa)
             if not params:
                 key_ni = (arc_num, 'NI')
                 params = params_dict.get(key_ni)
        # Return here for Approach after fallback check
        return params.copy() if params else None

    elif surface_type_upper == 'INNERAPPROACH':
        params_dict = INNER_APPROACH_PARAMS
        lookup_key = key # Keyed by ARC and Type
        params = params_dict.get(lookup_key) # Perform lookup
        # No fallback defined for inner approach based on table

    elif surface_type_upper == 'TOCS':
        params_dict = TOCS_PARAMS
        lookup_key = arc_num # TOCS params keyed only by ARC number in current dict
        # Add logic here if slope needs to vary for PA types based on MOS 139 8.2.14(d)

    elif surface_type_upper == 'IHS':
        params_dict = IHS_PARAMS
        lookup_key = key # Keyed by ARC and Type

    elif surface_type_upper == 'CONICAL':
        params_dict = CONICAL_PARAMS
        lookup_key = key # Keyed by ARC and Type

    elif surface_type_upper == 'OHS':
        params_dict = OHS_PARAMS
        lookup_key = key
        print(f"[ols_dimensions DEBUG] Attempting lookup in OHS_PARAMS with key {lookup_key!r}") # Log before lookup

    elif surface_type_upper == 'TRANSITIONAL':
        params_dict = TRANSITIONAL_PARAMS
        lookup_key = arc_num # Main transitional keyed only by ARC number
        # Add logic here to check for rwy_abbr == 'PA_II_III' and potentially return
        # specific inner transitional parameters if defined separately.

    else:
        print(f"Error: Unknown OLS surface type '{surface_type}' requested.")
        return None # Unknown surface type

    # Perform the lookup for non-Approach types
    if params_dict:
        params = params_dict.get(lookup_key)
        return params.copy() if params else None
    else:
        # Should not happen if surface_type_upper matched a known type
        return None
    
def get_taxiway_separation_offset(arc_num: int, arc_let: Optional[str], runway_type_str: Optional[str]) -> Optional[Dict[str, Any]]:
    """
    Retrieves Taxiway Minimum Separation offset based on classification.
    Returns None if parameters are not found.
    """
    if not isinstance(arc_num, int) or arc_num not in [1, 2, 3, 4]:
        print(f"Error: Invalid ARC Number '{arc_num}' for Taxiway Sep lookup.")
        return None
    
    # Use most restrictive type if different ends provided (relevant if called outside loop)
    # For per-runway call, runway_type_str should represent the governing type already
    rwy_abbr = get_runway_type_abbr(runway_type_str)
    
    # Handle missing ARC Letter - Default to empty string or highest possible? Check standard. Assume empty for now.
    arc_let_str = arc_let.strip().upper() if arc_let else ""
    if not arc_let_str:
        print(f"[ols_dimensions WARNING] Missing ARC Letter for Taxiway Sep lookup (Code {arc_num}, Type {rwy_abbr}). Lookup might fail if parameters require a letter.")
        
    key = (arc_num, arc_let_str, rwy_abbr)
    print(f"[ols_dimensions DEBUG] Using key: {key!r} for surface: TAXIWAY_SEPARATION")
    
    params = TAXIWAY_SEPARATION_PARAMS.get(key)
    
    # Basic Fallback attempt: If key with letter fails, try without letter (key = (arc_num, '', rwy_abbr))
    if not params and arc_let_str != "":
        print(f"[ols_dimensions DEBUG] Taxiway Sep lookup failed for key {key!r}. Trying without ARC Letter.")
        key_no_letter = (arc_num, '', rwy_abbr)
        params = TAXIWAY_SEPARATION_PARAMS.get(key_no_letter)
        
    # Another Fallback: Try falling back to a less restrictive type if specific type missing? (e.g., PA_I -> NPA -> NI)
    # Requires more complex logic - omit for now unless necessary based on MOS 139 data structure.
        
    return params.copy() if params else None

# =========================================================================
# == End of File
# =========================================================================