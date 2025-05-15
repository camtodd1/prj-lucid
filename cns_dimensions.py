# ./plugins/your_plugin_dir/cns_dimensions.py

from typing import Union, Dict, Optional, List, Any  # Added type hinting

# NASF Guideline G BRA Dimensions based on provided table Figure 2
# IMPORTANT: Height rules and values are NOT specified in the table image.
#            Placeholders are used below and MUST be replaced with actual
#            Guideline G specifications for height restrictions.

CNS_BRA_SPECIFICATIONS: Dict[str, List[Dict[str, Any]]] = {
    # Facility Type Key (MUST match values from dialog table ComboBox)
    "High Frequency (HF)": [
        {
            "SurfaceName": "Zone A",
            "Shape": "Circle",
            "OuterRadius_m": 100,
            "InnerRadius_m": 0,
            "HeightRule": "TBD",
            "HeightValue": None,
        },
        {
            "SurfaceName": "Zone A/B",
            "Shape": "Donut",
            "OuterRadius_m": 6000,
            "InnerRadius_m": 100,
            "HeightRule": "TBD",
            "HeightValue": None,
        },
        {
            "SurfaceName": "Area of Interest",
            "Shape": "Donut",
            "OuterRadius_m": 10000,
            "InnerRadius_m": 6000,
            "HeightRule": "TBD",
            "HeightValue": None,
        },
    ],
    "Very High Frequency (VHF)": [
        {
            "SurfaceName": "Zone A",
            "Shape": "Circle",
            "OuterRadius_m": 100,
            "InnerRadius_m": 0,
            "HeightRule": "TBD",
            "HeightValue": None,
        },
        {
            "SurfaceName": "Zone A/B",
            "Shape": "Donut",
            "OuterRadius_m": 600,
            "InnerRadius_m": 100,
            "HeightRule": "TBD",
            "HeightValue": None,
        },
        {
            "SurfaceName": "Area of Interest",
            "Shape": "Donut",
            "OuterRadius_m": 2000,
            "InnerRadius_m": 100,
            "HeightRule": "TBD",
            "HeightValue": None,
        },
    ],
    "Satellite Ground Station (SGS)": [
        {
            "SurfaceName": "Zone A",
            "Shape": "Circle",
            "OuterRadius_m": 30,
            "InnerRadius_m": 0,
            "HeightRule": "TBD",
            "HeightValue": None,
        },
        {
            "SurfaceName": "Zone A/B",
            "Shape": "Donut",
            "OuterRadius_m": 150,
            "InnerRadius_m": 30,
            "HeightRule": "TBD",
            "HeightValue": None,
        },
    ],
    "Non-Directional Beacon (NDB)": [
        {
            "SurfaceName": "Zone A",
            "Shape": "Circle",
            "OuterRadius_m": 60,
            "InnerRadius_m": 0,
            "HeightRule": "TBD",
            "HeightValue": None,
        },
        {
            "SurfaceName": "Zone A/B",
            "Shape": "Donut",
            "OuterRadius_m": 300,
            "InnerRadius_m": 60,
            "HeightRule": "TBD",
            "HeightValue": None,
        },
    ],
    "Distance Measuring Equipment (DME)": [
        {
            "SurfaceName": "Zone A",
            "Shape": "Circle",
            "OuterRadius_m": 100,
            "InnerRadius_m": 0,
            "HeightRule": "TBD",
            "HeightValue": None,
        },
        {
            "SurfaceName": "Zone A/B",
            "Shape": "Donut",
            "OuterRadius_m": 1500,
            "InnerRadius_m": 100,
            "HeightRule": "TBD",
            "HeightValue": None,
        },
    ],
    "VHF Omni-Directional Range (VOR)": [
        {
            "SurfaceName": "Zone A",
            "Shape": "Circle",
            "OuterRadius_m": 100,
            "InnerRadius_m": 0,
            "HeightRule": "TBD",
            "HeightValue": None,
        },
        {
            "SurfaceName": "Zone A/B",
            "Shape": "Donut",
            "OuterRadius_m": 1500,
            "InnerRadius_m": 100,
            "HeightRule": "TBD",
            "HeightValue": None,
        },
    ],
    "Conventional VHF Omni-Directional Range (CVOR)": [
        {
            "SurfaceName": "Zone A",
            "Shape": "Circle",
            "OuterRadius_m": 200,
            "InnerRadius_m": 0,
            "HeightRule": "TBD",
            "HeightValue": None,
        },
        {
            "SurfaceName": "Zone A/B",
            "Shape": "Donut",
            "OuterRadius_m": 1500,
            "InnerRadius_m": 200,
            "HeightRule": "TBD",
            "HeightValue": None,
        },
    ],
    "Doppler VHF Omni-Directional Range (DVOR) - Elevated": [
        {
            "SurfaceName": "Zone A",
            "Shape": "Circle",
            "OuterRadius_m": 100,
            "InnerRadius_m": 0,
            "HeightRule": "TBD",
            "HeightValue": None,
        },
        {
            "SurfaceName": "Zone A/B",
            "Shape": "Donut",
            "OuterRadius_m": 1500,
            "InnerRadius_m": 100,
            "HeightRule": "TBD",
            "HeightValue": None,
        },  # Assuming contiguous
    ],
    "Doppler VHF Omni-Directional Range (DVOR) - Ground Mounted": [
        {
            "SurfaceName": "Zone A",
            "Shape": "Circle",
            "OuterRadius_m": 150,
            "InnerRadius_m": 0,
            "HeightRule": "TBD",
            "HeightValue": None,
        },
        {
            "SurfaceName": "Zone A/B",
            "Shape": "Donut",
            "OuterRadius_m": 1500,
            "InnerRadius_m": 150,
            "HeightRule": "TBD",
            "HeightValue": None,
        },
    ],
    "Middle and Outer Marker": [
        {
            "SurfaceName": "Zone A",
            "Shape": "Circle",
            "OuterRadius_m": 5,
            "InnerRadius_m": 0,
            "HeightRule": "TBD",
            "HeightValue": None,
        },
        {
            "SurfaceName": "Zone A/B",
            "Shape": "Donut",
            "OuterRadius_m": 50,
            "InnerRadius_m": 5,
            "HeightRule": "TBD",
            "HeightValue": None,
        },
    ],
    "Glide Path (GP)": [],  # Needs different geometry logic, leave empty for now
    "Localiser (LOC)": [],  # Needs different geometry logic, leave empty for now
    "Automatic Dependent Surveillance Broadcast (ADS-B)": [
        {
            "SurfaceName": "Zone A",
            "Shape": "Circle",
            "OuterRadius_m": 100,
            "InnerRadius_m": 0,
            "HeightRule": "TBD",
            "HeightValue": None,
        },
        {
            "SurfaceName": "Zone A/B",
            "Shape": "Donut",
            "OuterRadius_m": 1500,
            "InnerRadius_m": 100,
            "HeightRule": "TBD",
            "HeightValue": None,
        },
    ],
    "Wide Area Multilateration (WAM)": [
        {
            "SurfaceName": "Zone A",
            "Shape": "Circle",
            "OuterRadius_m": 100,
            "InnerRadius_m": 0,
            "HeightRule": "TBD",
            "HeightValue": None,
        },
        {
            "SurfaceName": "Zone A/B",
            "Shape": "Donut",
            "OuterRadius_m": 1500,
            "InnerRadius_m": 100,
            "HeightRule": "TBD",
            "HeightValue": None,
        },
    ],
    "Primary Surveillance Radar (PSR)": [
        {
            "SurfaceName": "Zone A",
            "Shape": "Circle",
            "OuterRadius_m": 500,
            "InnerRadius_m": 0,
            "HeightRule": "TBD",
            "HeightValue": None,
        },
        {
            "SurfaceName": "Zone A/B",
            "Shape": "Donut",
            "OuterRadius_m": 4000,
            "InnerRadius_m": 500,
            "HeightRule": "TBD",
            "HeightValue": None,
        },
        {
            "SurfaceName": "Area of Interest",
            "Shape": "Donut",
            "OuterRadius_m": 15000,
            "InnerRadius_m": 4000,
            "HeightRule": "TBD",
            "HeightValue": None,
        },
    ],
    "Secondary Surveillance Radar (SSR)": [
        {
            "SurfaceName": "Zone A",
            "Shape": "Circle",
            "OuterRadius_m": 500,
            "InnerRadius_m": 0,
            "HeightRule": "TBD",
            "HeightValue": None,
        },
        {
            "SurfaceName": "Zone A/B",
            "Shape": "Donut",
            "OuterRadius_m": 4000,
            "InnerRadius_m": 500,
            "HeightRule": "TBD",
            "HeightValue": None,
        },
        {
            "SurfaceName": "Area of Interest",
            "Shape": "Donut",
            "OuterRadius_m": 15000,
            "InnerRadius_m": 4000,
            "HeightRule": "TBD",
            "HeightValue": None,
        },
    ],
    "Ground Based Augmentation System (GBAS) - RSMU": [
        {
            "SurfaceName": "Zone A",
            "Shape": "Circle",
            "OuterRadius_m": 155,
            "InnerRadius_m": 0,
            "HeightRule": "TBD",
            "HeightValue": None,
        },
        {
            "SurfaceName": "Zone A/B",
            "Shape": "Donut",
            "OuterRadius_m": 3000,
            "InnerRadius_m": 155,
            "HeightRule": "TBD",
            "HeightValue": None,
        },
    ],
    "GBAS - VDB": [
        {
            "SurfaceName": "Zone A",
            "Shape": "Circle",
            "OuterRadius_m": 200,
            "InnerRadius_m": 0,
            "HeightRule": "TBD",
            "HeightValue": None,
        },
        {
            "SurfaceName": "Zone A/B",
            "Shape": "Donut",
            "OuterRadius_m": 3000,
            "InnerRadius_m": 200,
            "HeightRule": "TBD",
            "HeightValue": None,
        },
    ],
    "Link Dishes": [
        {
            "SurfaceName": "Zone A",
            "Shape": "Circle",
            "OuterRadius_m": 30,
            "InnerRadius_m": 0,
            "HeightRule": "TBD",
            "HeightValue": None,
        },
    ],
    "Radar Site Monitor - Type A": [
        {
            "SurfaceName": "Zone A",
            "Shape": "Circle",
            "OuterRadius_m": 30,
            "InnerRadius_m": 0,
            "HeightRule": "TBD",
            "HeightValue": None,
        },
        {
            "SurfaceName": "Zone A/B",
            "Shape": "Circle",
            "OuterRadius_m": 500,
            "InnerRadius_m": 0,
            "HeightRule": "TBD",
            "HeightValue": None,
        },
    ],
    "Radar Site Monitor - Type B": [
        {
            "SurfaceName": "Zone A",
            "Shape": "Circle",
            "OuterRadius_m": 70,
            "InnerRadius_m": 0,
            "HeightRule": "TBD",
            "HeightValue": None,
        },
        {
            "SurfaceName": "Zone A/B",
            "Shape": "Circle",
            "OuterRadius_m": 500,
            "InnerRadius_m": 0,
            "HeightRule": "TBD",
            "HeightValue": None,
        },
    ],
}


def get_cns_spec(facility_type: str) -> Optional[List[Dict[str, Any]]]:
    """
    Helper function to get BRA specs for a given facility type.
    Performs a case-insensitive lookup after stripping whitespace.
    Returns the list of surface specs or None if not found.
    """
    if not isinstance(facility_type, str):  # Basic type check
        return None
    search_type = facility_type.strip().upper()
    for key, value in CNS_BRA_SPECIFICATIONS.items():
        if key.strip().upper() == search_type:
            return value  # Return the list of spec dictionaries
    return None  # Not found
