"""CASA Part 139 MOS 2019 profile metadata."""

from ..base import RulesetProfile, capability_map


MOS139_PROFILE = RulesetProfile(
    id="mos139_2019",
    display_name="MOS139 (current)",
    edition="Part 139 MOS 2019",
    status="stable",
    description="Current CASA Part 139 MOS behaviour implemented by the plugin.",
    aliases=("MOS139", "mos139", "CASA_MOS139", "casa_part139_mos_2019"),
    capabilities=capability_map(
        {
            "classification.runway_type_mapping": "supported",
            "physical.pavement": "supported",
            "physical.shoulder": "supported",
            "physical.strip": "supported",
            "physical.resa": "supported",
            "physical.clearway": "supported",
            "physical.stopway": "partial",
            "physical.taxiway_separation": "partial",
            "ols.airport_wide": "supported",
            "ols.runway_approach": "supported",
            "ols.takeoff_climb": "supported",
            "ols.ofz": "supported",
            "ols.controlling_lower_envelope": "experimental",
            "markings.runway": "supported",
            "lighting.runway": "supported",
            "lighting.approach": "supported",
            "declared_distances.calculated": "supported",
        }
    ),
)
