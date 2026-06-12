"""EASA CS-ADR-DSN runway marking policy."""

from typing import Any, Dict, List, Optional, Tuple

from . import ols

SOURCE_PUBLICATION = "EASA Easy Access Rules for Aerodromes, CS-ADR-DSN Issue 7"
SOURCE_URL = (
    "https://www.easa.europa.eu/en/document-library/easy-access-rules/"
    "online-publications/easy-access-rules-aerodromes-regulation-eu"
)
RUNWAY_CENTRELINE_SOURCE_URL = f"{SOURCE_URL}?erules-id=ERULES-1963177438-2250"
THRESHOLD_SOURCE_URL = f"{SOURCE_URL}?erules-id=ERULES-1963177438-2251"
AIMING_POINT_SOURCE_URL = f"{SOURCE_URL}?erules-id=ERULES-1963177438-2252"
TOUCHDOWN_ZONE_SOURCE_URL = f"{SOURCE_URL}?erules-id=ERULES-1963177438-2253"
RUNWAY_HOLDING_SOURCE_URL = f"{SOURCE_URL}?erules-id=ERULES-1963177438-2265"

EASA_RUNWAY_CENTRELINE_MARKING_REF = "CS ADR-DSN.L.530"
EASA_THRESHOLD_MARKING_REF = "CS ADR-DSN.L.535"
EASA_AIMING_POINT_MARKING_REF = "CS ADR-DSN.L.540 Table L-1"
EASA_TOUCHDOWN_ZONE_MARKING_REF = "CS ADR-DSN.L.545"
EASA_RUNWAY_HOLDING_POSITION_MARKING_REF = "CS ADR-DSN.L.575"
EASA_RUNWAY_HOLDING_POSITION_LOCATION_REF = "CS ADR-DSN.D.335"

THRESHOLD_MARKING_PARAMS_BY_WIDTH = {
    18.0: (4, 1.8),
    23.0: (6, 1.8),
    30.0: (8, 1.8),
    45.0: (12, 1.8),
    60.0: (16, 1.8),
}

AIMING_POINT_RULES = (
    (800.0, 150.0, 30.0, 4.0, 6.0, "CS ADR-DSN.L.540 Table L-1"),
    (1200.0, 250.0, 30.0, 6.0, 9.0, "CS ADR-DSN.L.540 Table L-1"),
    (2400.0, 300.0, 45.0, 9.0, 18.0, "CS ADR-DSN.L.540 Table L-1"),
    (None, 400.0, 45.0, 9.0, 18.0, "CS ADR-DSN.L.540 Table L-1"),
)

TOUCHDOWN_ZONE_OFFSET_RULES = (
    (900.0, [300.0]),
    (1200.0, [150.0, 450.0]),
    (1500.0, [150.0, 450.0, 600.0]),
    (2400.0, [150.0, 450.0, 600.0, 750.0]),
    (None, [150.0, 300.0, 600.0, 750.0, 900.0, 1050.0]),
)

MARKING_TRACEABILITY_ITEMS = {
    "runway_centreline_marking_width": {
        "source": EASA_RUNWAY_CENTRELINE_MARKING_REF,
        "status": "operational_verified",
        "implementation": "centreline_marking_width",
        "notes": "Minimum stripe widths by runway type and code number.",
    },
    "threshold_marking_stripe_count": {
        "source": EASA_THRESHOLD_MARKING_REF,
        "status": "operational_verified",
        "implementation": "THRESHOLD_MARKING_PARAMS_BY_WIDTH",
        "notes": "Runway width to threshold stripe count table.",
    },
    "threshold_marking_representative_stripe_width": {
        "source": EASA_THRESHOLD_MARKING_REF,
        "status": "interpretive",
        "implementation": "THRESHOLD_MARKING_PARAMS_BY_WIDTH",
        "notes": "Uses the approximately 1.80 m stripe width stated for continued/displaced threshold markings as a representative value.",
    },
    "aiming_point_marking_table": {
        "source": EASA_AIMING_POINT_MARKING_REF,
        "status": "operational_verified",
        "implementation": "AIMING_POINT_RULES",
        "notes": "Table L-1 LDA bands and representative minimum values for permitted ranges.",
    },
    "aiming_point_non_instrument_policy": {
        "source": EASA_RUNWAY_CENTRELINE_MARKING_REF.replace(".L.530", ".L.540"),
        "status": "interpretive",
        "implementation": "aiming_point_rule",
        "notes": "Additional-conspicuity case is exposed using the 1200 m to <2400 m representative dimensions when runway width is at least 30 m.",
    },
    "touchdown_zone_pair_counts": {
        "source": EASA_TOUCHDOWN_ZONE_MARKING_REF,
        "status": "operational_verified",
        "implementation": "TOUCHDOWN_ZONE_OFFSET_RULES",
        "notes": "LDA bands and required pair counts are source verified.",
    },
    "touchdown_zone_offsets": {
        "source": EASA_TOUCHDOWN_ZONE_MARKING_REF,
        "status": "derived_verified",
        "implementation": "TOUCHDOWN_ZONE_OFFSET_RULES",
        "notes": "Offsets are generated at 150 m intervals with pairs coincident with or within 50 m of the aiming point omitted.",
    },
    "runway_holding_position_marking": {
        "source": EASA_RUNWAY_HOLDING_POSITION_MARKING_REF,
        "status": "accepted_unsupported",
        "implementation": "runway_holding_position_rule",
        "notes": "Chapter L defines marking patterns, while fixed holding-position distance is a Chapter D location/design criterion.",
    },
}

MARKING_TRACEABILITY = {
    "source_publication": SOURCE_PUBLICATION,
    "source_url": SOURCE_URL,
    "items": MARKING_TRACEABILITY_ITEMS,
}


def get_marking_traceability() -> Dict[str, Any]:
    """Return source traceability metadata for EASA runway marking rules."""
    return MARKING_TRACEABILITY.copy()


def threshold_marking_params(runway_width: float) -> Optional[Tuple[int, float]]:
    """Return the threshold marking parameters for a given runway width.

    Parameters
    ----------
    runway_width : float
        The physical width of the runway in metres.

    Returns
    -------
    Optional[Tuple[int, float]]
        A tuple containing the number of stripes and the width of each
        stripe.  Returns ``None`` if the width is not one of the
        standard values (18, 23, 30, 45 or 60 m).
    """
    for width_m, params in THRESHOLD_MARKING_PARAMS_BY_WIDTH.items():
        if abs(float(runway_width) - width_m) <= 0.01:
            return params
    return None


def centreline_marking_width(arc_num: int, type_primary: str, type_reciprocal: str) -> float:
    """Determine the centreline marking stripe width.

    EASA specifies minimum widths for centreline stripes based on the
    approach category and aerodrome code number.

    Parameters
    ----------
    arc_num : int
        The aerodrome reference code number (1-4) associated with the
        runway in question.
    type_primary : str
        The operation type of the primary runway direction (e.g.,
        "NI", "NPA", "PA_I", "PA_II_III").
    type_reciprocal : str
        The operation type of the reciprocal runway direction.

    Returns
    -------
    float
        The required stripe width in metres.  If the two directions
        require different widths, the greater (more demanding)
        requirement is returned.
    """
    widths: List[float] = []
    for runway_type in (type_primary, type_reciprocal):
        type_abbr = ols.classify_runway_type(runway_type)
        if type_abbr == "PA_II_III":
            widths.append(0.9)
        elif type_abbr == "PA_I" or (type_abbr == "NPA" and arc_num in (3, 4)):
            widths.append(0.45)
        else:
            widths.append(0.3)
    return max(widths) if widths else 0.3


def aiming_point_rule(
    runway_width: float, lda_m: float, runway_type: str
) -> Optional[Tuple[float, float, float, float, str]]:
    """Return the aiming point marking parameters.

    On instrument runways, the location and dimensions of the
    aiming point marking depend on the landing distance available
    (LDA).  This function returns the first
    applicable rule from :data:`AIMING_POINT_RULES` when the runway
    type corresponds to an instrument runway (NPA, PA_I or PA_II_III).

    On non-instrument or non-precision runways, EASA permits the
    provision of aiming point markings where increased conspicuity is
    desired.  For runways 30 m in width or
    greater, a default rule is returned that mirrors the values for
    the 1 200 m-<2 400 m LDA band (offset 300 m, length 45 m, width
    9 m, spacing 18 m).  In other cases, ``None`` is returned.

    Parameters
    ----------
    runway_width : float
        The physical width of the runway in metres.
    lda_m : float
        Landing distance available in metres.
    runway_type : str
        The operational classification of the runway (e.g., "NI",
        "NPA", "PA_I", "PA_II_III").

    Returns
    -------
    Optional[Tuple[float, float, float, float, str]]
        A tuple containing (offset from threshold, stripe length,
        stripe width, lateral spacing between stripes, reference).
        Returns ``None`` if no aiming point marking is required.
    """
    type_abbr = ols.classify_runway_type(runway_type)
    # Apply instrument runway rules. The interface does not carry code
    # number, so the code 1 additional-conspicuity distinction is handled
    # by callers/policy rather than this dimensional table lookup.
    if type_abbr in {"NPA", "PA_I", "PA_II_III"}:
        for max_lda_m, offset_m, length_m, width_m, spacing_m, ref in AIMING_POINT_RULES:
            if max_lda_m is None or lda_m < max_lda_m:
                return offset_m, length_m, width_m, spacing_m, ref
    # For non-instrument and non-precision runways of substantial width,
    # provide a default aiming point marking to enhance conspicuity.
    if runway_width >= 30.0:
        return 300.0, 45.0, 9.0, 18.0, "CS ADR-DSN.L.540 (default)"
    return None


def touchdown_zone_offsets(lda_m: float) -> List[float]:
    """Return the touchdown zone marking offsets.

    Parameters
    ----------
    lda_m : float
        Landing distance available in metres.

    Returns
    -------
    List[float]
        A list of offset distances (in metres from the threshold) for
        the centres of each pair of touchdown-zone markings.  The
        offsets correspond to the number of pairs prescribed for the
        given LDA band.
    """
    for max_lda_m, offsets in TOUCHDOWN_ZONE_OFFSET_RULES:
        if max_lda_m is None or lda_m < max_lda_m:
            return list(offsets)
    return []


def runway_holding_position_rule(runway_code_num: int, runway_type: str) -> Optional[Tuple[float, str]]:
    """Return the distance from the threshold to a runway-holding position.

    Unlike MOS139, CS ADR-DSN Chapter L does not prescribe fixed
    distances for runway-holding positions.  The location of a
    runway-holding position is determined by the design and obstacle
    clearance requirements in Chapter D (see CS ADR-DSN.D.335) and
    therefore lies outside the scope of the markings chapter.

    Parameters
    ----------
    runway_code_num : int
        The aerodrome reference code number (1-4).
    runway_type : str
        The operational classification (e.g., "NI", "NPA", "PA_I",
        "PA_II_III").  Included for interface compatibility.

    Returns
    -------
    Optional[Tuple[float, str]]
        Always returns ``None`` for EASA since distances are not
        specified in Chapter L.  The second element would normally
        contain a reference string.
    """
    return None


__all__ = [
    "SOURCE_PUBLICATION",
    "SOURCE_URL",
    "RUNWAY_CENTRELINE_SOURCE_URL",
    "THRESHOLD_SOURCE_URL",
    "AIMING_POINT_SOURCE_URL",
    "TOUCHDOWN_ZONE_SOURCE_URL",
    "RUNWAY_HOLDING_SOURCE_URL",
    "EASA_RUNWAY_CENTRELINE_MARKING_REF",
    "EASA_THRESHOLD_MARKING_REF",
    "EASA_AIMING_POINT_MARKING_REF",
    "EASA_TOUCHDOWN_ZONE_MARKING_REF",
    "EASA_RUNWAY_HOLDING_POSITION_MARKING_REF",
    "EASA_RUNWAY_HOLDING_POSITION_LOCATION_REF",
    "THRESHOLD_MARKING_PARAMS_BY_WIDTH",
    "AIMING_POINT_RULES",
    "TOUCHDOWN_ZONE_OFFSET_RULES",
    "MARKING_TRACEABILITY",
    "MARKING_TRACEABILITY_ITEMS",
    "get_marking_traceability",
    "threshold_marking_params",
    "centreline_marking_width",
    "aiming_point_rule",
    "touchdown_zone_offsets",
    "runway_holding_position_rule",
]
