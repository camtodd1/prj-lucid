"""Feature-family identifiers and dependency signatures."""

from typing import Mapping, Tuple

from .run_history import input_mapping_fingerprint


FAMILY_AIRPORT = "airport"
FAMILY_RUNWAYS = "runways"
FAMILY_CNS = "cns"
FAMILY_OLS = "ols"
FAMILY_LIGHTING = "lighting"

GENERATABLE_FAMILIES: Tuple[str, ...] = (
    FAMILY_AIRPORT,
    FAMILY_RUNWAYS,
    FAMILY_CNS,
    FAMILY_OLS,
    FAMILY_LIGHTING,
)

FAMILY_LABELS = {
    FAMILY_AIRPORT: "Airport",
    FAMILY_RUNWAYS: "Runways",
    FAMILY_CNS: "CNS",
    FAMILY_OLS: "OLS",
    FAMILY_LIGHTING: "Lighting",
}

FAMILY_INPUT_KEYS = {
    FAMILY_AIRPORT: (
        "icao_code",
        "arp_easting",
        "arp_northing",
        "arp_elevation",
        "met_easting",
        "met_northing",
        "met_elevation",
        "safeguarding_framework",
        "safeguarding_options",
    ),
    FAMILY_RUNWAYS: (
        "icao_code",
        "design_standard",
        "safeguarding_framework",
        "safeguarding_options",
        "runway_configuration",
        "runways",
    ),
    FAMILY_CNS: (
        "icao_code",
        "safeguarding_framework",
        "runways",
        "cns_facilities",
        "ils_bra_installations",
        "cns_contour_intervals",
    ),
    FAMILY_OLS: (
        "icao_code",
        "arp_easting",
        "arp_northing",
        "arp_elevation",
        "design_standard",
        "protected_airspace_policy",
        "baseline_ols_ruleset",
        "comparison_ols_ruleset",
        "runway_configuration",
        "runways",
        "contour_intervals",
    ),
    FAMILY_LIGHTING: (
        "icao_code",
        "design_standard",
        "runway_configuration",
        "runways",
        "agl_options",
    ),
}


def family_input_signature(
    input_data: Mapping[str, object],
    family_id: str,
    crs_authid: str,
) -> str:
    """Return a stable signature for inputs that affect one feature family."""

    if family_id not in FAMILY_INPUT_KEYS:
        raise ValueError(f"Unknown feature family: {family_id}")
    payload = dict(input_data)
    payload["project_crs"] = str(crs_authid or "")
    return input_mapping_fingerprint(
        payload,
        (*FAMILY_INPUT_KEYS[family_id], "project_crs"),
    )


__all__ = [
    "FAMILY_AIRPORT",
    "FAMILY_CNS",
    "FAMILY_INPUT_KEYS",
    "FAMILY_LABELS",
    "FAMILY_LIGHTING",
    "FAMILY_OLS",
    "FAMILY_RUNWAYS",
    "GENERATABLE_FAMILIES",
    "family_input_signature",
]
