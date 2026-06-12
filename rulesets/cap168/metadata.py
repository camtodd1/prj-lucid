"""UK CAA CAP 168 profile metadata and capability declarations."""

RULESET_ID = "uk_caa_cap168_edition_13"
DISPLAY_NAME = "UK CAA CAP 168 (Edition 13)"
EDITION = "CAP 168 Edition 13"
STATUS = "draft"
DESCRIPTION = "Draft UK CAA CAP 168 Edition 13 ruleset framework."
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
    "physical.strip": "unsupported",
    "physical.resa": "unsupported",
    "physical.clearway": "supported",
    "physical.stopway": "supported",
    "physical.taxiway_separation": "unsupported",
    "physical.parallel_runway_separation": "supported",
    "ols.airport_wide": "unsupported",
    "ols.runway_approach": "unsupported",
    "ols.takeoff_climb": "unsupported",
    "ols.ofz": "unsupported",
    "ols.controlling_lower_envelope": "unsupported",
    "markings.runway": "unsupported",
    "lighting.runway": "unsupported",
    "lighting.approach": "unsupported",
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
