"""EASA profile metadata and capability declarations."""

RULESET_ID = "easa_cs_adr_dsn_issue_6"
DISPLAY_NAME = "EASA CS-ADR-DSN (Issue 6)"
EDITION = "CS-ADR-DSN Issue 6"
STATUS = "draft"
DESCRIPTION = "Draft EASA CS-ADR-DSN Issue 6 ruleset framework."
ALIASES = (
    "EASA",
    "easa",
    "CS-ADR-DSN",
    "cs_adr_dsn",
    "cs_adr_dsn_issue_6",
    "easa_cs_adr_dsn",
)

CAPABILITY_STATUS_BY_KEY = {
    "classification.runway_type_mapping": "supported",
    "physical.pavement": "partial",
    "physical.shoulder": "partial",
    "physical.strip": "supported",
    "physical.resa": "supported",
    "physical.clearway": "unsupported",
    "physical.stopway": "unsupported",
    "physical.taxiway_separation": "unsupported",
    "ols.airport_wide": "partial",
    "ols.runway_approach": "partial",
    "ols.takeoff_climb": "partial",
    "ols.ofz": "partial",
    "ols.controlling_lower_envelope": "unsupported",
    "markings.runway": "partial",
    "lighting.runway": "partial",
    "lighting.approach": "partial",
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
