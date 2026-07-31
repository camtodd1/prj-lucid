"""UK CAA and DfT safeguarding framework metadata."""

FRAMEWORK_ID = "uk_caa_safeguarding"
DISPLAY_NAME = "UK CAA / DfT Safeguarding"
EDITION = "CAP 738 v3; CAP 764 v7; DfT PSZ policy 2021"
STATUS = "beta"
DESCRIPTION = (
    "UK consultation-map and public-safety-zone mechanisms. Generated geometry is "
    "indicative and does not replace an aerodrome's officially lodged safeguarding map."
)
ALIASES = ("uk", "uk_caa", "uk_dft", "uk_safeguarding")

CAPABILITY_STATUS_BY_KEY = {
    "framework.windshear": "unsupported",
    "framework.wildlife": "supported",
    "framework.wind_turbine": "supported",
    "framework.lighting_control": "unsupported",
    "framework.ols_planning": "supported",
    "framework.cns.bra": "unsupported",
    "framework.public_safety": "supported",
    "framework.temporary_obstacle.notification": "partial",
    "framework.met.station": "unsupported",
}

__all__ = [
    "FRAMEWORK_ID",
    "DISPLAY_NAME",
    "EDITION",
    "STATUS",
    "DESCRIPTION",
    "ALIASES",
    "CAPABILITY_STATUS_BY_KEY",
]
