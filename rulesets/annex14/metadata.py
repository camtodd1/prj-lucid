"""ICAO Annex 14 Volume I profile metadata and capability declarations."""

CURRENT_RULESET_ID = "icao_annex14_vol1_current_ols"
CURRENT_DISPLAY_NAME = "ICAO Annex 14 Vol I - Current OLS"
CURRENT_EDITION = "Annex 14 Volume I current OLS"
CURRENT_STATUS = "scaffold"
CURRENT_DESCRIPTION = "Current enforceable ICAO Annex 14 Volume I protected-airspace OLS scaffold."
CURRENT_ALIASES = (
    "Annex 14",
    "ANNEX14",
    "annex14",
    "ICAO Annex 14",
    "icao_annex14",
    "annex14_current",
    "annex14_current_ols",
    "icao_annex14_vol1",
    "icao_annex14_vol1_current",
)

MODERNISED_RULESET_ID = "icao_annex14_vol1_modernised_ofs_oes"
MODERNISED_DISPLAY_NAME = "ICAO Annex 14 Vol I - Modernised OFS/OES (from 21 Nov 2030)"
MODERNISED_EDITION = "Annex 14 Volume I modernised OFS/OES"
MODERNISED_STATUS = "draft"
MODERNISED_DESCRIPTION = (
    "Future ICAO Annex 14 Volume I protected-airspace model using OFS/OES and ADG, "
    "not enforceable until 21 November 2030."
)
MODERNISED_ALIASES = (
    "Annex 14 Modernised",
    "Annex 14 Modernized",
    "Annex 14 OFS/OES",
    "ICAO Annex 14 Modernised",
    "icao_annex14_modernised",
    "icao_annex14_modernized",
    "icao_annex14_ofs_oes",
    "icao_annex14_vol1_modernised",
)

RULESET_ID = MODERNISED_RULESET_ID
DISPLAY_NAME = MODERNISED_DISPLAY_NAME
EDITION = "Annex 14 Volume I"
STATUS = "scaffold"
DESCRIPTION = MODERNISED_DESCRIPTION
ALIASES = MODERNISED_ALIASES

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
    "oes.take_off_climb": "supported",
    "obstacle_limitation.requirements": "supported",
    "obstacle_limitation.surface_establishment": "supported",
    "markings.runway": "unsupported",
    "lighting.runway": "unsupported",
    "lighting.approach": "unsupported",
    "declared_distances.calculated": "unsupported",
}

CURRENT_CAPABILITY_STATUS_BY_KEY = {
    **CAPABILITY_STATUS_BY_KEY,
    "classification.design_group": "unsupported",
    "ols.airport_wide": "scaffold",
    "ols.obstacle_free_surfaces": "unsupported",
    "ols.runway_approach": "scaffold",
    "ols.takeoff_climb": "scaffold",
    "ols.ofz": "scaffold",
    "oes.airport_wide": "unsupported",
    "oes.design_group_driven": "unsupported",
    "oes.horizontal": "unsupported",
    "oes.straight_in_instrument_approach": "unsupported",
    "oes.precision_approach": "unsupported",
    "oes.instrument_departure": "unsupported",
    "oes.take_off_climb": "unsupported",
    "obstacle_limitation.requirements": "unsupported",
    "obstacle_limitation.surface_establishment": "unsupported",
}

MODERNISED_CAPABILITY_STATUS_BY_KEY = CAPABILITY_STATUS_BY_KEY

__all__ = [
    "CURRENT_RULESET_ID",
    "CURRENT_DISPLAY_NAME",
    "CURRENT_EDITION",
    "CURRENT_STATUS",
    "CURRENT_DESCRIPTION",
    "CURRENT_ALIASES",
    "CURRENT_CAPABILITY_STATUS_BY_KEY",
    "MODERNISED_RULESET_ID",
    "MODERNISED_DISPLAY_NAME",
    "MODERNISED_EDITION",
    "MODERNISED_STATUS",
    "MODERNISED_DESCRIPTION",
    "MODERNISED_ALIASES",
    "MODERNISED_CAPABILITY_STATUS_BY_KEY",
    "RULESET_ID",
    "DISPLAY_NAME",
    "EDITION",
    "STATUS",
    "DESCRIPTION",
    "ALIASES",
    "CAPABILITY_STATUS_BY_KEY",
]
