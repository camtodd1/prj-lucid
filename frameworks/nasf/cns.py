# -*- coding: utf-8 -*-
"""NASF Guideline G CNS building restricted area specifications."""

import math

from typing import Any, Dict, List, Optional

# Airservices Australia, Building Restricted Areas for Aviation Facilities,
# Attachment 3.  Values are retained as policy data so the generator can expose
# the vertical condition and referral outcome alongside the plan geometry.

CNS_BRA_SPECIFICATIONS: Dict[str, List[Dict[str, Any]]] = {
    # Facility Type Key (MUST match values from dialog table ComboBox)
    "High Frequency (HF) Transmit Site": [
        {
            "SurfaceName": "Zone A - Inner",
            "shape": "Circle",
            "OuterRadius_m": 100,
            "InnerRadius_m": 0,
            "HeightRule": "All Heights",
            "HeightBasis": "AGL",
            "ActionRequired": "All applications must be referred to Airservices Australia for assessment.",
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
            "ActionRequired": "All applications must be referred to Airservices Australia for assessment.",
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
            "ActionRequired": "All applications must be referred to Airservices Australia for assessment.",
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
            "ActionRequired": "No requirements. Airservices Australia should be advised of proposals for large obstructions.",
            "Condition": "Between 100 m and 2,000 m from the transmit antenna and does not cross the Zone A boundary.",
            "FacilityLabel": "HF Transmit",
            "SourceRef": "Airservices Building Restrictions Guide, Attachment 3, p. 13",
        },
    ],
    "High Frequency (HF) Receiver Site": [
        {
            "SurfaceName": "Zone A - Inner",
            "shape": "Circle",
            "OuterRadius_m": 100,
            "InnerRadius_m": 0,
            "HeightRule": "All Heights",
            "HeightBasis": "AGL",
            "ActionRequired": "All applications must be referred to Airservices Australia for assessment.",
            "Condition": "Within 100 m of the High Frequency receive antenna, regardless of height.",
            "FacilityLabel": "HF Receiver",
            "SourceRef": "Airservices Building Restrictions Guide, Attachment 3, p. 14",
            "Guidance": "Substantial structures are generally limited within 100 m of the antenna; Area of Interest proposals are assessed case by case.",
        },
        {
            "SurfaceName": "Zone A - 2.5 Degree Slope",
            "shape": "Donut",
            "OuterRadius_m": 6000,
            "InnerRadius_m": 100,
            "HeightRule": "Radial Slope",
            "HeightBasis": "AGL",
            "SlopeDegrees": 2.5,
            "SlopeStartHeightAGL_m": 10,
            "SlopeStartDistance_m": 100,
            "ContourInterval_m": 5,
            "ActionRequired": "All applications must be referred to Airservices Australia for assessment.",
            "Condition": "Crosses the 2.5 degree zone boundary, starting at 10 m AGL.",
            "FacilityLabel": "HF Receiver",
            "SourceRef": "Airservices Building Restrictions Guide, Attachment 3, p. 14",
            "Guidance": "Substantial structures are generally limited within 100 m of the antenna; Area of Interest proposals are assessed case by case.",
        },
        {
            "SurfaceName": "Area of Interest - Below Zone A",
            "shape": "Donut",
            "OuterRadius_m": 6000,
            "InnerRadius_m": 100,
            "HeightRule": "Below Radial Slope",
            "HeightBasis": "AGL",
            "ActionRequired": "All applications must be referred to Airservices Australia for assessment.",
            "Condition": "Between 100 m and 6,000 m from the receive antenna and below the Zone A height.",
            "FacilityLabel": "HF Receiver",
            "SourceRef": "Airservices Building Restrictions Guide, Attachment 3, p. 14",
            "Guidance": "Area of Interest proposals are assessed case by case for adverse impacts to the High Frequency receiver site.",
        },
        {
            "SurfaceName": "Area of Interest - Above 267 m",
            "shape": "Donut",
            "OuterRadius_m": 10000,
            "InnerRadius_m": 6000,
            "HeightRule": "Minimum Height",
            "HeightBasis": "Above Antenna",
            "MinHeightAboveAntenna_m": 267,
            "HeightComparator": ">",
            "ActionRequired": "All applications must be referred to Airservices Australia for assessment.",
            "Condition": "Between 6,000 m and 10,000 m from the receive antenna and more than 267 m above the High Frequency antenna.",
            "FacilityLabel": "HF Receiver",
            "SourceRef": "Airservices Building Restrictions Guide, Attachment 3, p. 14",
            "Guidance": "Area of Interest proposals are assessed case by case for adverse impacts to the High Frequency receiver site.",
        },
        {
            "SurfaceName": "Zone B",
            "shape": "Donut",
            "OuterRadius_m": 10000,
            "InnerRadius_m": 6000,
            "HeightRule": "Does Not Cross Zone Boundary",
            "HeightBasis": "Above Antenna",
            "ActionRequired": "No requirements. Airservices Australia should be advised of proposals for large obstructions.",
            "Condition": "Between 6,000 m and 10,000 m from the receiver antenna and does not cross the Zone A boundary.",
            "FacilityLabel": "HF Receiver",
            "SourceRef": "Airservices Building Restrictions Guide, Attachment 3, p. 14",
            "Guidance": "Area of Interest proposals are assessed case by case for adverse impacts to the High Frequency receiver site.",
        },
    ],
    "Very High Frequency (VHF)": [
        {
            "SurfaceName": "Zone A - Inner",
            "shape": "Circle",
            "OuterRadius_m": 100,
            "InnerRadius_m": 0,
            "HeightRule": "All Heights",
            "HeightBasis": "AGL",
            "ActionRequired": "All applications must be referred to Airservices Australia for assessment.",
            "Condition": "Within 100 m of the Very High Frequency antenna, regardless of height.",
            "FacilityLabel": "VHF",
            "SourceRef": "Airservices Building Restrictions Guide, Attachment 3, p. 15",
            "Guidance": "Substantial structures are generally prohibited within Zone A.",
        },
        {
            "SurfaceName": "Zone A - 2 Percent Slope",
            "shape": "Donut",
            "OuterRadius_m": 2000,
            "InnerRadius_m": 100,
            "HeightRule": "Radial Slope",
            "HeightBasis": "AGL",
            "SlopePercent": 2,
            "SlopeDegrees": math.degrees(math.atan(0.02)),
            "SlopeStartHeightAGL_m": 10,
            "SlopeStartDistance_m": 100,
            "ContourInterval_m": 5,
            "ActionRequired": "All applications must be referred to Airservices Australia for assessment.",
            "Condition": "Crosses the 2% zone boundary, starting at 10 m AGL.",
            "FacilityLabel": "VHF",
            "SourceRef": "Airservices Building Restrictions Guide, Attachment 3, p. 15",
            "Guidance": "Substantial structures are generally prohibited within Zone A.",
        },
        {
            "SurfaceName": "Zone B",
            "shape": "Donut",
            "OuterRadius_m": 600,
            "InnerRadius_m": 100,
            "HeightRule": "Does Not Cross Zone Boundary",
            "HeightBasis": "AGL",
            "ActionRequired": "No requirements. Airservices Australia should be advised of proposals for large obstructions.",
            "Condition": "Between 100 m and 600 m from the VHF antenna and does not cross the Zone A boundary.",
            "FacilityLabel": "VHF",
            "SourceRef": "Airservices Building Restrictions Guide, Attachment 3, p. 15",
            "Guidance": "VHF propagation is governed by antenna line of sight; advise Airservices Australia of large obstructions.",
        },
        {
            "SurfaceName": "Area of Interest",
            "shape": "Donut",
            "OuterRadius_m": 2000,
            "InnerRadius_m": 600,
            "HeightRule": "No Additional Height Limit",
            "HeightBasis": "AGL",
            "ActionRequired": "No requirements. Airservices Australia should be advised of proposals for large obstructions.",
            "Condition": "Between 600 m and 2,000 m from the VHF antenna.",
            "FacilityLabel": "VHF",
            "SourceRef": "Airservices Building Restrictions Guide, Attachment 3, p. 15",
            "Guidance": "VHF propagation is governed by antenna line of sight; advise Airservices Australia of large obstructions.",
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
            "ActionRequired": "All applications must be referred to Airservices Australia for assessment.",
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
            "ActionRequired": "No requirements.",
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
            "ActionRequired": "All applications must be referred to Airservices Australia for assessment.",
            "Condition": "Between 30 m and 150 m from the site and greater than 10 m in height.",
            "SourceRef": "Airservices Building Restrictions Guide, Attachment 3, p. 10",
        },
    ],
    "Non-Directional Beacon (NDB)": [
        {
            "SurfaceName": "Zone A - Inner",
            "shape": "Circle",
            "OuterRadius_m": 60,
            "InnerRadius_m": 0,
            "HeightRule": "All Heights",
            "HeightBasis": "AGL",
            "ActionRequired": "All applications must be referred to Airservices Australia for assessment.",
            "Condition": "Within 60 m of the Non-Directional Beacon antenna, regardless of height.",
            "FacilityLabel": "NDB",
            "SourceRef": "Airservices Building Restrictions Guide, Attachment 3, p. 16",
            "Guidance": "Within 60 m, vegetation should be kept below 60 cm; 33 kV or greater overhead powerlines should be at least 300 m from the antenna centre.",
        },
        {
            "SurfaceName": "Zone A - 5 Degree Slope",
            "shape": "Donut",
            "OuterRadius_m": 300,
            "InnerRadius_m": 60,
            "HeightRule": "Radial Slope",
            "HeightBasis": "AGL",
            "SlopeDegrees": 5,
            "SlopeStartHeightAGL_m": 60 * math.tan(math.radians(5)),
            "SlopeStartDistance_m": 60,
            "ContourInterval_m": 5,
            "ActionRequired": "All applications must be referred to Airservices Australia for assessment.",
            "Condition": "Crosses the 5 degree zone boundary measured from ground level at the NDB antenna centre.",
            "FacilityLabel": "NDB",
            "SourceRef": "Airservices Building Restrictions Guide, Attachment 3, p. 16",
            "Guidance": "Within 60 m, vegetation should be kept below 60 cm; 33 kV or greater overhead powerlines should be at least 300 m from the antenna centre.",
        },
        {
            "SurfaceName": "Zone B",
            "shape": "Donut",
            "OuterRadius_m": 300,
            "InnerRadius_m": 60,
            "HeightRule": "Does Not Cross Zone Boundary",
            "HeightBasis": "AGL",
            "ActionRequired": "No requirements.",
            "Condition": "Between 60 m and 300 m from the NDB antenna and does not cross the Zone A boundary.",
            "FacilityLabel": "NDB",
            "SourceRef": "Airservices Building Restrictions Guide, Attachment 3, p. 16",
            "Guidance": "Within 60 m, vegetation should be kept below 60 cm; 33 kV or greater overhead powerlines should be at least 300 m from the antenna centre.",
        },
    ],
    "Distance Measuring Equipment (DME)": [
        {
            "SurfaceName": "Zone A - Horizontal Plane",
            "shape": "Circle",
            "OuterRadius_m": 100,
            "InnerRadius_m": 0,
            "HeightRule": "Minimum Height",
            "HeightBasis": "Above Antenna",
            "MinHeightAboveAntenna_m": -4,
            "HeightComparator": ">",
            "ActionRequired": "All applications must be referred to Airservices Australia for assessment.",
            "Condition": "Within 100 m of the DME antenna and above a horizontal plane 4 m below the antenna centre.",
            "FacilityLabel": "DME",
            "SourceRef": "Airservices Building Restrictions Guide, Attachment 3, p. 17",
            "Guidance": "33 kV or greater overhead powerlines crossing the boundary should be at least 300 m from the antenna. Where co-located with VOR, Localizer, or Glidepath, use that facility's restricted area.",
        },
        {
            "SurfaceName": "Zone A - 2 Degree Slope",
            "shape": "Donut",
            "OuterRadius_m": 1500,
            "InnerRadius_m": 100,
            "HeightRule": "Radial Slope",
            "HeightBasis": "Above Antenna",
            "SlopeDegrees": 2,
            "SlopeStartHeightAGL_m": -4 + 100 * math.tan(math.radians(2)),
            "SlopeStartDistance_m": 100,
            "ContourInterval_m": 5,
            "ActionRequired": "All applications must be referred to Airservices Australia for assessment.",
            "Condition": "Crosses the 2 degree zone boundary measured from the horizontal plane 4 m below the DME antenna centre.",
            "FacilityLabel": "DME",
            "SourceRef": "Airservices Building Restrictions Guide, Attachment 3, p. 17",
            "Guidance": "33 kV or greater overhead powerlines crossing the boundary should be at least 300 m from the antenna. Where co-located with VOR, Localizer, or Glidepath, use that facility's restricted area.",
        },
        {
            "SurfaceName": "Zone B",
            "shape": "Donut",
            "OuterRadius_m": 1500,
            "InnerRadius_m": 100,
            "HeightRule": "Does Not Cross Zone Boundary",
            "HeightBasis": "Above Antenna",
            "ActionRequired": "No requirements.",
            "Condition": "Between 100 m and 1,500 m from the DME antenna and does not cross the Zone A boundary.",
            "FacilityLabel": "DME",
            "SourceRef": "Airservices Building Restrictions Guide, Attachment 3, p. 17",
            "Guidance": "33 kV or greater overhead powerlines crossing the boundary should be at least 300 m from the antenna. Where co-located with VOR, Localizer, or Glidepath, use that facility's restricted area.",
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
            "SurfaceName": "Zone A - Inner",
            "shape": "Circle",
            "OuterRadius_m": 200,
            "InnerRadius_m": 0,
            "HeightRule": "All Heights",
            "HeightBasis": "AGL",
            "ActionRequired": "All applications must be referred to Airservices Australia for assessment.",
            "Condition": "Within 200 m of the ground-mounted CVOR antenna, regardless of height.",
            "FacilityLabel": "Ground CVOR",
            "SourceRef": "Airservices Building Restrictions Guide, Attachment 3, p. 18",
            "Guidance": "No obstructions should extend above the horizontal plane within 150 m; necessary fencing above it should be wooden; between 150 m and 200 m, obstacles should generally not cross the boundary; 33 kV or greater powerlines crossing the boundary should be at least 600 m away.",
        },
        {
            "SurfaceName": "Zone A - 1 Degree Slope",
            "shape": "Donut",
            "OuterRadius_m": 1500,
            "InnerRadius_m": 200,
            "HeightRule": "Radial Slope",
            "HeightBasis": "AGL",
            "SlopeDegrees": 1,
            "SlopeStartHeightAGL_m": 200 * math.tan(math.radians(1)),
            "SlopeStartDistance_m": 200,
            "ContourInterval_m": 5,
            "ActionRequired": "All applications must be referred to Airservices Australia for assessment.",
            "Condition": "Crosses the 1 degree zone boundary measured from ground level at the CVOR antenna centre.",
            "FacilityLabel": "Ground CVOR",
            "SourceRef": "Airservices Building Restrictions Guide, Attachment 3, p. 18",
            "Guidance": "No obstructions should extend above the horizontal plane within 150 m; necessary fencing above it should be wooden; between 150 m and 200 m, obstacles should generally not cross the boundary; 33 kV or greater powerlines crossing the boundary should be at least 600 m away.",
        },
        {
            "SurfaceName": "Zone B",
            "shape": "Donut",
            "OuterRadius_m": 1500,
            "InnerRadius_m": 200,
            "HeightRule": "Does Not Cross Zone Boundary",
            "HeightBasis": "AGL",
            "ActionRequired": "No requirements.",
            "Condition": "Between 200 m and 1,500 m from the ground-mounted CVOR antenna and does not cross the Zone A boundary.",
            "FacilityLabel": "Ground CVOR",
            "SourceRef": "Airservices Building Restrictions Guide, Attachment 3, p. 18",
            "Guidance": "No obstructions should extend above the horizontal plane within 150 m; necessary fencing above it should be wooden; between 150 m and 200 m, obstacles should generally not cross the boundary; 33 kV or greater powerlines crossing the boundary should be at least 600 m away.",
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

RADIO_LINK_POLICY: Dict[str, Any] = {
    "SurfaceName": "Zone A",
    "Width_m": 30,
    "HeightRule": "All Heights",
    "HeightBasis": "AGL",
    "ActionRequired": "All applications must be referred to Airservices Australia for assessment.",
    "Condition": "Within 30 m of the radio link.",
    "SourceRef": "Airservices Building Restrictions Guide, Attachment 3, p. 12",
    "Guidance": "No temporary or permanent obstructions should infringe Zone A.",
}

LEGACY_CNS_FACILITY_TYPE_ALIASES = {
    "HIGH FREQUENCY (HF)": "High Frequency (HF) Transmit Site",
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
    alias = LEGACY_CNS_FACILITY_TYPE_ALIASES.get(search_type)
    if alias:
        return CNS_BRA_SPECIFICATIONS[alias]
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
