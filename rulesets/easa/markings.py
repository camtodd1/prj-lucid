"""EASA CS-ADR-DSN Chapter L runway marking policy.

This module provides functions to compute runway marking parameters in
accordance with the European Union Aviation Safety Agency (EASA)
Certification Specifications for Aerodromes Design (CS-ADR-DSN),
Issue 6, Chapter L (Markings).  These functions mirror the interface
exposed by the MOS139-based :mod:`markings` module but use
dimensions and criteria extracted from Chapter L of the CS-ADR-DSN.

The following regulatory provisions informed the values used here:

* **Threshold markings** - The number of longitudinal stripes is
  related to runway width.  CS ADR-DSN.L.535 stipulates that 18 m,
  23 m, 30 m, 45 m and 60 m wide runways should have 4, 6, 8, 12
  and 16 stripes respectively.  Although
  the EASA standard does not prescribe a specific stripe width for
  threshold markings, guidance for displaced thresholds indicates
  stripes should be "approximately 1.80 m wide".
  In the absence of a definitive value, this implementation adopts
  1.8 m as a representative width for all runway categories.

* **Centreline markings** - CS ADR-DSN.L.530 requires that
  centreline stripes on Category II/III precision approach runways
  be at least 0.90 m wide, on non-precision runways with code
  numbers 3/4 and Category I precision runways 0.45 m, and on
  code 1/2 non-precision and non-instrument runways 0.30 m.
  The function :func:`centreline_marking_width` reflects these
  minima.

* **Aiming point markings** - Table L-1 of CS ADR-DSN.L.540 sets
  distances from the threshold to the beginning of the aiming
  point marking and specifies stripe lengths, widths and lateral
  spacings according to landing distance available (LDA) bands
  (<800 m, 800 m-<1 200 m, 1 200 m-<2 400 m and >=2 400 m).
  The :data:`AIMING_POINT_RULES` constant encodes a representative
  value from each range (choosing the lower bound for lengths and
  lateral spacings where ranges are permitted) and these values are
  returned by :func:`aiming_point_rule` for instrument runways.

* **Touchdown-zone markings** - CS ADR-DSN.L.545 specifies that
  pairs of rectangular touchdown-zone markings be placed at 150 m
  intervals from the threshold and that any pair within 50 m of
  the aiming point should be omitted.  The
  number of pairs increases with LDA: one pair for LDA < 900 m,
  two for 900 m-<1 200 m, three for 1 200 m-<1 500 m, four for
  1 500 m-<2 400 m, and six for LDA >= 2 400 m.
  The :data:`TOUCHDOWN_ZONE_OFFSET_RULES` constant contains
  representative offsets (in metres from the threshold) for each
  LDA band after removing offsets that conflict with the aiming
  point location.

* **Runway-holding position marking** - CS ADR-DSN.L.575 defines the
  patterns (A and B) for runway-holding position markings but does
  not prescribe a fixed distance from the runway threshold.  Distances
  are determined by runway design criteria in CS-ADR-DSN.D.335,
  therefore :func:`runway_holding_position_rule` returns
  ``None``.

Note that where the EASA specification provides a range of values
for stripe length, width or spacing, this module opts for a
representative minimum within that range.  Users should consult
CS-ADR-DSN if increased conspicuity or alternative dimensions are
required.
"""

from typing import List, Optional, Tuple

from . import ols

# Mapping of runway width to (number of threshold stripes, stripe width).
# CS ADR-DSN.L.535 prescribes the number of stripes; stripe width is
# inferred from guidance for displaced thresholds, which indicates
# stripes should be approximately 1.80 m wide.
THRESHOLD_MARKING_PARAMS_BY_WIDTH = {
    18.0: (4, 1.8),
    23.0: (6, 1.8),
    30.0: (8, 1.8),
    45.0: (12, 1.8),
    60.0: (16, 1.8),
}

# Aiming point rules derived from CS ADR-DSN.L.540 Table L-1.  Each tuple
# contains:
#   (max LDA (m), offset from threshold (m), stripe length (m), stripe
#    width (m), lateral spacing between inner edges (m), reference)
# where ``max LDA`` is ``None`` for the open-ended category.  Stripe
# lengths and lateral spacings are chosen at the lower bound of the
# ranges permitted by the specification.
AIMING_POINT_RULES = (
    (800.0, 150.0, 30.0, 4.0, 6.0, "CS ADR-DSN.L.540 Table L-1"),
    (1200.0, 250.0, 30.0, 6.0, 9.0, "CS ADR-DSN.L.540 Table L-1"),
    (2400.0, 300.0, 45.0, 9.0, 18.0, "CS ADR-DSN.L.540 Table L-1"),
    (None, 400.0, 45.0, 9.0, 18.0, "CS ADR-DSN.L.540 Table L-1"),
)

# Touchdown zone offsets for each LDA band.  Offsets are measured
# from the threshold and are spaced at 150 m intervals; offsets
# located within 50 m of the aiming point for the corresponding LDA
# band have been omitted.
TOUCHDOWN_ZONE_OFFSET_RULES = (
    # LDA < 900 m: one pair.  The 300 m offset remains after deleting
    # the 150 m offset, which would coincide with the aiming point on
    # runways less than 800 m long.
    (900.0, [300.0]),
    # 900 m <= LDA < 1 200 m: two pairs.  Offsets at 150 m and 450 m
    # remain after removing the 300 m offset (50 m from the 250 m
    # aiming point).
    (1200.0, [150.0, 450.0]),
    # 1 200 m <= LDA < 1 500 m: three pairs.  Offsets at 150 m, 450 m
    # and 600 m remain after removing the 300 m offset.
    (1500.0, [150.0, 450.0, 600.0]),
    # 1 500 m <= LDA < 2 400 m: four pairs.  Offsets at 150 m, 450 m,
    # 600 m and 750 m remain after removing the 300 m offset.
    (2400.0, [150.0, 450.0, 600.0, 750.0]),
    # LDA >= 2 400 m: six pairs.  Offsets at 150 m, 300 m, 600 m,
    # 750 m, 900 m and 1 050 m remain after removing the 450 m offset
    # (50 m from the 400 m aiming point).  Additional offsets beyond
    # 1 050 m are available at 1 200 m etc., but only the first six
    # pairs are required.
    (None, [150.0, 300.0, 600.0, 750.0, 900.0, 1050.0]),
)

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
    type corresponds to an instrument runway (PA_I or PA_II_III).

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
    # Apply instrument runway rules
    if type_abbr in {"PA_I", "PA_II_III"}:
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
    "threshold_marking_params",
    "centreline_marking_width",
    "aiming_point_rule",
    "touchdown_zone_offsets",
    "runway_holding_position_rule",
]