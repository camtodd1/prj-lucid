"""ICAO Annex 14 Volume I profile metadata and capability declarations."""

RULESET_ID = "icao_annex14_vol1"
DISPLAY_NAME = "ICAO Annex 14 Vol I"
EDITION = "Annex 14 Volume I"
STATUS = "scaffold"
DESCRIPTION = "Scaffold for an ICAO Annex 14 Volume I aerodrome design standards ruleset."
ALIASES = (
    "Annex 14",
    "ANNEX14",
    "annex14",
    "ICAO Annex 14",
    "icao_annex14",
    "icao_annex14_vol1",
)

CAPABILITY_STATUS_BY_KEY = {
    "classification.runway_type_mapping": "supported",
    "classification.reference_code": "partial",
    "classification.design_group": "partial",
    "physical.pavement": "unsupported",
    "physical.shoulder": "unsupported",
    "physical.strip": "unsupported",
    "physical.resa": "unsupported",
    "physical.clearway": "unsupported",
    "physical.stopway": "unsupported",
    "physical.taxiway_separation": "unsupported",
    "physical.parallel_runway_separation": "scaffold",
    "ols.airport_wide": "scaffold",
    "ols.obstacle_free_surfaces": "supported",
    "ols.runway_approach": "partial",
    "ols.takeoff_climb": "scaffold",
    "ols.ofz": "scaffold",
    "ols.controlling_lower_envelope": "unsupported",
    "oes.airport_wide": "partial",
    "oes.design_group_driven": "partial",
    "oes.horizontal": "supported",
    "oes.straight_in_instrument_approach": "supported",
    "oes.precision_approach": "supported",
    "oes.instrument_departure": "supported",
    "markings.runway": "unsupported",
    "lighting.runway": "unsupported",
    "lighting.approach": "unsupported",
    "declared_distances.calculated": "unsupported",
}

__all__ = [
    "RULESET_ID",
    "DISPLAY_NAME",
    "EDITION",
    "STATUS",
    "DESCRIPTION",
    "ALIASES",
    "CAPABILITY_STATUS_BY_KEY",
]
