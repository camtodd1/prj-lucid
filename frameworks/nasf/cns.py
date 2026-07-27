# -*- coding: utf-8 -*-
"""NASF Guideline G CNS building restricted area specifications."""

import math

from typing import Any, Dict, List, Optional

# Airservices Australia, Building Restricted Areas for Aviation Facilities,
# Attachment 3.  Values are retained as policy data so the generator can expose
# the vertical condition and referral outcome alongside the plan geometry.

CNS_BRA_SPECIFICATIONS: Dict[str, List[Dict[str, Any]]] = {
    # Facility Type Key (MUST match values from dialog table ComboBox)
    "High Frequency (HF)": [
        {
            "SurfaceName": "Zone A - Inner",
            "shape": "Circle",
            "OuterRadius_m": 100,
            "InnerRadius_m": 0,
            "HeightRule": "All Heights",
            "HeightBasis": "AGL",
            "Referral": "Refer to Airservices Australia for assessment",
            "Condition": "Within 100 m of the High Frequency transmit antenna, regardless of height.",
            "FacilityLabel": "HF Transmit",
            "SourceRef": "Airservices Building Restrictions Guide, Attachment 3, p. 13",
        },
        {
            "SurfaceName": "Zone A - 2.5 Degree Slope",
            "shape": "Donut",
            "OuterRadius_m": 600,
            "InnerRadius_m": 100,
            "HeightRule": "Radial Slope",
            "HeightBasis": "AGL",
            "SlopeDegrees": 2.5,
            "SlopeStartHeightAGL_m": 10,
            "SlopeStartDistance_m": 100,
            "ContourInterval_m": 5,
            "Referral": "Refer to Airservices Australia for assessment",
            "Condition": "Crosses the 2.5 degree zone boundary, starting at 10 m AGL.",
            "FacilityLabel": "HF Transmit",
            "SourceRef": "Airservices Building Restrictions Guide, Attachment 3, p. 13",
        },
        {
            "SurfaceName": "Area of Interest",
            "shape": "Donut",
            "OuterRadius_m": 2000,
            "InnerRadius_m": 100,
            "HeightRule": "Minimum Height",
            "HeightBasis": "AGL",
            "MinHeightAGL_m": 10,
            "HeightComparator": ">",
            "Referral": "Refer to Airservices Australia for assessment",
            "Condition": "Between 100 m and 2,000 m from the transmit antenna and above 10 m AGL.",
            "FacilityLabel": "HF Transmit",
            "SourceRef": "Airservices Building Restrictions Guide, Attachment 3, p. 13",
        },
        {
            "SurfaceName": "Zone B",
            "shape": "Donut",
            "OuterRadius_m": 2000,
            "InnerRadius_m": 100,
            "HeightRule": "Does Not Cross Zone Boundary",
            "HeightBasis": "AGL",
            "Referral": "No requirements; advise Airservices Australia of large obstructions",
            "Condition": "Between 100 m and 2,000 m from the transmit antenna and does not cross the Zone A boundary.",
            "FacilityLabel": "HF Transmit",
            "SourceRef": "Airservices Building Restrictions Guide, Attachment 3, p. 13",
        },
    ],
    "Very High Frequency (VHF)": [
        {
            "SurfaceName": "Zone A",
            "shape": "Circle",
            "OuterRadius_m": 100,
            "InnerRadius_m": 0,
            "HeightRule": "TBD",
            "HeightValue": None,
        },
        {
            "SurfaceName": "Zone A/B",
            "shape": "Donut",
            "OuterRadius_m": 600,
            "InnerRadius_m": 100,
            "HeightRule": "TBD",
            "HeightValue": None,
        },
        {
            "SurfaceName": "Area of Interest",
            "shape": "Donut",
            "OuterRadius_m": 2000,
            "InnerRadius_m": 100,
            "HeightRule": "TBD",
            "HeightValue": None,
        },
    ],
    "Satellite Ground Station (SGS)": [
        {
            "SurfaceName": "Zone A",
            "shape": "Circle",
            "OuterRadius_m": 30,
            "InnerRadius_m": 0,
            "HeightRule": "All Heights",
            "HeightBasis": "AGL",
            "Referral": "Refer to Airservices Australia for assessment",
            "Condition": "Within 30 m of the Satellite Ground Station facility, regardless of height.",
            "SourceRef": "Airservices Building Restrictions Guide, Attachment 3, p. 10",
        },
        {
            "SurfaceName": "Zone B",
            "shape": "Donut",
            "OuterRadius_m": 150,
            "InnerRadius_m": 30,
            "HeightRule": "Maximum Height",
            "HeightBasis": "AGL",
            "MaxHeightAGL_m": 10,
            "HeightComparator": "<",
            "Referral": "No requirements",
            "Condition": "Between 30 m and 150 m from the site and less than 10 m in height.",
            "SourceRef": "Airservices Building Restrictions Guide, Attachment 3, p. 10",
        },
        {
            "SurfaceName": "Area of Interest",
            "shape": "Donut",
            "OuterRadius_m": 150,
            "InnerRadius_m": 30,
            "HeightRule": "Minimum Height",
            "HeightBasis": "AGL",
            "MinHeightAGL_m": 10,
            "HeightComparator": ">",
            "Referral": "Refer to Airservices Australia for assessment",
            "Condition": "Between 30 m and 150 m from the site and greater than 10 m in height.",
            "SourceRef": "Airservices Building Restrictions Guide, Attachment 3, p. 10",
        },
    ],
    "Non-Directional Beacon (NDB)": [
        {
            "SurfaceName": "Zone A",
            "shape": "Circle",
            "OuterRadius_m": 60,
            "InnerRadius_m": 0,
            "HeightRule": "TBD",
            "HeightValue": None,
        },
        {
            "SurfaceName": "Zone A/B",
            "shape": "Donut",
            "OuterRadius_m": 300,
            "InnerRadius_m": 60,
            "HeightRule": "TBD",
            "HeightValue": None,
        },
    ],
    "Distance Measuring Equipment (DME)": [
        {
            "SurfaceName": "Zone A",
            "shape": "Circle",
            "OuterRadius_m": 100,
            "InnerRadius_m": 0,
            "HeightRule": "TBD",
            "HeightValue": None,
        },
        {
            "SurfaceName": "Zone A/B",
            "shape": "Donut",
            "OuterRadius_m": 1500,
            "InnerRadius_m": 100,
            "HeightRule": "TBD",
            "HeightValue": None,
        },
    ],
    "VHF Omni-Directional Range (VOR)": [
        {
            "SurfaceName": "Zone A",
            "shape": "Circle",
            "OuterRadius_m": 100,
            "InnerRadius_m": 0,
            "HeightRule": "TBD",
            "HeightValue": None,
        },
        {
            "SurfaceName": "Zone A/B",
            "shape": "Donut",
            "OuterRadius_m": 1500,
            "InnerRadius_m": 100,
            "HeightRule": "TBD",
            "HeightValue": None,
        },
    ],
    "Conventional VHF Omni-Directional Range (CVOR)": [
        {
            "SurfaceName": "Zone A",
            "shape": "Circle",
            "OuterRadius_m": 200,
            "InnerRadius_m": 0,
            "HeightRule": "TBD",
            "HeightValue": None,
        },
        {
            "SurfaceName": "Zone A/B",
            "shape": "Donut",
            "OuterRadius_m": 1500,
            "InnerRadius_m": 200,
            "HeightRule": "TBD",
            "HeightValue": None,
        },
    ],
    "Doppler VHF Omni-Directional Range (DVOR) - Elevated": [
        {
            "SurfaceName": "Zone A",
            "shape": "Circle",
            "OuterRadius_m": 100,
            "InnerRadius_m": 0,
            "HeightRule": "TBD",
            "HeightValue": None,
        },
        {
            "SurfaceName": "Zone A/B",
            "shape": "Donut",
            "OuterRadius_m": 1500,
            "InnerRadius_m": 100,
            "HeightRule": "TBD",
            "HeightValue": None,
        },  # Assuming contiguous
    ],
    "Doppler VHF Omni-Directional Range (DVOR) - Ground Mounted": [
        {
            "SurfaceName": "Zone A",
            "shape": "Circle",
            "OuterRadius_m": 150,
            "InnerRadius_m": 0,
            "HeightRule": "TBD",
            "HeightValue": None,
        },
        {
            "SurfaceName": "Zone A/B",
            "shape": "Donut",
            "OuterRadius_m": 1500,
            "InnerRadius_m": 150,
            "HeightRule": "TBD",
            "HeightValue": None,
        },
    ],
    "Middle and Outer Marker": [
        {
            "SurfaceName": "Zone A",
            "shape": "Circle",
            "OuterRadius_m": 5,
            "InnerRadius_m": 0,
            "HeightRule": "TBD",
            "HeightValue": None,
        },
        {
            "SurfaceName": "Zone A/B",
            "shape": "Donut",
            "OuterRadius_m": 50,
            "InnerRadius_m": 5,
            "HeightRule": "TBD",
            "HeightValue": None,
        },
    ],
    "Glide Path (GP)": [],  # Specialised geometry tracked in docs/roadmap.md.
    "Localiser (LOC)": [],  # Specialised geometry tracked in docs/roadmap.md.
    "Automatic Dependent Surveillance Broadcast (ADS-B)": [
        {
            "SurfaceName": "Zone A",
            "shape": "Circle",
            "OuterRadius_m": 100,
            "InnerRadius_m": 0,
            "HeightRule": "TBD",
            "HeightValue": None,
        },
        {
            "SurfaceName": "Zone A/B",
            "shape": "Donut",
            "OuterRadius_m": 1500,
            "InnerRadius_m": 100,
            "HeightRule": "TBD",
            "HeightValue": None,
        },
    ],
    "Wide Area Multilateration (WAM)": [
        {
            "SurfaceName": "Zone A",
            "shape": "Circle",
            "OuterRadius_m": 100,
            "InnerRadius_m": 0,
            "HeightRule": "TBD",
            "HeightValue": None,
        },
        {
            "SurfaceName": "Zone A/B",
            "shape": "Donut",
            "OuterRadius_m": 1500,
            "InnerRadius_m": 100,
            "HeightRule": "TBD",
            "HeightValue": None,
        },
    ],
    "Primary Surveillance Radar (PSR)": [
        {
            "SurfaceName": "Zone A",
            "shape": "Circle",
            "OuterRadius_m": 500,
            "InnerRadius_m": 0,
            "HeightRule": "TBD",
            "HeightValue": None,
        },
        {
            "SurfaceName": "Zone A/B",
            "shape": "Donut",
            "OuterRadius_m": 4000,
            "InnerRadius_m": 500,
            "HeightRule": "TBD",
            "HeightValue": None,
        },
        {
            "SurfaceName": "Area of Interest",
            "shape": "Donut",
            "OuterRadius_m": 15000,
            "InnerRadius_m": 4000,
            "HeightRule": "TBD",
            "HeightValue": None,
        },
    ],
    "Secondary Surveillance Radar (SSR)": [
        {
            "SurfaceName": "Zone A",
            "shape": "Circle",
            "OuterRadius_m": 500,
            "InnerRadius_m": 0,
            "HeightRule": "TBD",
            "HeightValue": None,
        },
        {
            "SurfaceName": "Zone A/B",
            "shape": "Donut",
            "OuterRadius_m": 4000,
            "InnerRadius_m": 500,
            "HeightRule": "TBD",
            "HeightValue": None,
        },
        {
            "SurfaceName": "Area of Interest",
            "shape": "Donut",
            "OuterRadius_m": 15000,
            "InnerRadius_m": 4000,
            "HeightRule": "TBD",
            "HeightValue": None,
        },
    ],
    "Ground Based Augmentation System (GBAS) - RSMU": [
        {
            "SurfaceName": "Zone A",
            "shape": "Circle",
            "OuterRadius_m": 155,
            "InnerRadius_m": 0,
            "HeightRule": "TBD",
            "HeightValue": None,
        },
        {
            "SurfaceName": "Zone A/B",
            "shape": "Donut",
            "OuterRadius_m": 3000,
            "InnerRadius_m": 155,
            "HeightRule": "TBD",
            "HeightValue": None,
        },
    ],
    "GBAS - VDB": [
        {
            "SurfaceName": "Zone A",
            "shape": "Circle",
            "OuterRadius_m": 200,
            "InnerRadius_m": 0,
            "HeightRule": "TBD",
            "HeightValue": None,
        },
        {
            "SurfaceName": "Zone A/B",
            "shape": "Donut",
            "OuterRadius_m": 3000,
            "InnerRadius_m": 200,
            "HeightRule": "TBD",
            "HeightValue": None,
        },
    ],
    "Link Dishes": [
        {
            "SurfaceName": "Zone A",
            "shape": "Circle",
            "OuterRadius_m": 30,
            "InnerRadius_m": 0,
            "HeightRule": "TBD",
            "HeightValue": None,
        },
    ],
    "Radar Site Monitor - Type A": [
        {
            "SurfaceName": "Zone A",
            "shape": "Circle",
            "OuterRadius_m": 30,
            "InnerRadius_m": 0,
            "HeightRule": "TBD",
            "HeightValue": None,
        },
        {
            "SurfaceName": "Zone A/B",
            "shape": "Circle",
            "OuterRadius_m": 500,
            "InnerRadius_m": 0,
            "HeightRule": "TBD",
            "HeightValue": None,
        },
    ],
    "Radar Site Monitor - Type B": [
        {
            "SurfaceName": "Zone A",
            "shape": "Circle",
            "OuterRadius_m": 70,
            "InnerRadius_m": 0,
            "HeightRule": "TBD",
            "HeightValue": None,
        },
        {
            "SurfaceName": "Zone A/B",
            "shape": "Circle",
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


def slope_contour_levels(surface_spec: Dict[str, Any]) -> List[Dict[str, float]]:
    """Return AGL contour levels and radii for a radial CNS slope surface."""
    if surface_spec.get("HeightRule") != "Radial Slope":
        return []
    try:
        slope_degrees = float(surface_spec["SlopeDegrees"])
        start_height = float(surface_spec["SlopeStartHeightAGL_m"])
        start_distance = float(surface_spec["SlopeStartDistance_m"])
        outer_radius = float(surface_spec["OuterRadius_m"])
        interval = float(surface_spec["ContourInterval_m"])
    except (KeyError, TypeError, ValueError):
        return []
    slope_tangent = math.tan(math.radians(slope_degrees))
    if slope_tangent <= 0 or interval <= 0 or outer_radius <= start_distance:
        return []

    maximum_height = start_height + (outer_radius - start_distance) * slope_tangent
    contours: List[Dict[str, float]] = []
    height = start_height
    while height <= maximum_height + 1e-9:
        radius = start_distance + (height - start_height) / slope_tangent
        contours.append(
            {
                "height_agl_m": round(height, 6),
                "radius_m": round(radius, 6),
            }
        )
        height += interval
    return contours
