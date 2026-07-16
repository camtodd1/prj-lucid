"""MOS139 profile metadata and capability declarations."""

RULESET_ID = "mos139_2019"
DISPLAY_NAME = "MOS139 (C.07 2026)"
EDITION = "Part 139 MOS 2019, Compilation No. 7 (2026)"
STATUS = "stable"
DESCRIPTION = (
    "CASA Part 139 MOS 2019, Compilation No. 7 (2026), behaviour "
    "implemented by the plugin."
)
ALIASES = ("MOS139", "mos139", "CASA_MOS139", "casa_part139_mos_2019")

CAPABILITY_STATUS_BY_KEY = {
    "classification.runway_type_mapping": "supported",
    "physical.pavement": "supported",
    "physical.shoulder": "supported",
    "physical.strip": "supported",
    "physical.resa": "supported",
    "physical.clearway": "supported",
    "physical.stopway": "partial",
    "physical.taxiway_separation": "partial",
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
