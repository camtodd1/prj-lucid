"""Australian NASF framework metadata and capability declarations."""

FRAMEWORK_ID = "nasf_aus"
DISPLAY_NAME = "NASF (Australia)"
EDITION = "National Airports Safeguarding Framework"
STATUS = "stable"
DESCRIPTION = "Australian planning and safeguarding framework currently implemented by the plugin."
ALIASES = ("NASF", "nasf", "australia_nasf")

CAPABILITY_STATUS_BY_KEY = {
    "framework.windshear": "supported",
    "framework.wildlife": "supported",
    "framework.wind_turbine": "supported",
    "framework.lighting_control": "supported",
    "framework.ols_planning": "supported",
    "framework.cns.bra": "partial",
    "framework.public_safety": "supported",
    "framework.met.station": "partial",
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
