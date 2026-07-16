"""UK CAA CAP 168 profile metadata and capability declarations."""

RULESET_ID = "uk_caa_cap168_edition_13"
DISPLAY_NAME = "UK CAA CAP 168 (Edition 13)"
EDITION = "CAP 168 Edition 13"
STATUS = "stable"
DESCRIPTION = (
    "Production-supported UK CAA CAP 168 Edition 13 conventional OLS, "
    "including nominated offset and curved approach/take-off tracks."
)
ALIASES = (
    "CAP168",
    "CAP 168",
    "UK CAA CAP168",
    "UK CAA CAP 168",
    "CAA CAP168",
    "caa_cap168",
    "uk_caa_cap168",
)

CAPABILITY_STATUS_BY_KEY = {
    "classification.reference_code": "supported",
    "classification.runway_type_mapping": "supported",
    "physical.pavement": "partial",
    "physical.shoulder": "partial",
    "physical.runway_width": "supported",
    "physical.strip": "supported",
    "physical.resa": "unsupported",
    "physical.clearway": "supported",
    "physical.stopway": "supported",
    "physical.taxiway_separation": "supported",
    "physical.parallel_runway_separation": "supported",
    "ols.airport_wide": "supported",
    "ols.runway_approach": "supported",
    "ols.takeoff_climb": "supported",
    "ols.ofz": "supported",
    "ols.controlling_lower_envelope": "supported",
    "markings.runway": "supported",
    "lighting.runway": "supported",
    "lighting.approach": "supported",
    "declared_distances.calculated": "supported",
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
