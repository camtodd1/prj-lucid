"""Layer-tree labels for the implemented UK safeguarding mechanisms."""

try:
    from ...core import output_structure
except ImportError:
    from core import output_structure

SAFEGUARDING_GROUP_NAME = output_structure.EXTERNAL_SAFEGUARDING
SUMMARY_SECTION_NAME = output_structure.EXTERNAL_SAFEGUARDING
GENERATION_STATUS_MESSAGE = "Generating UK safeguarding consultation and planning layers..."

GUIDELINE_GROUPS = {
    "C": "Wildlife Consultation",
    "D": "Wind Turbine Safeguarding",
    "I": "Public Safety Zones",
}

GUIDELINE_F_SUBGROUPS = {
    "airport_wide": output_structure.AIRPORT_WIDE_OLS,
    "runway": output_structure.RUNWAY_APPROACH_AND_TAKE_OFF,
    "ofz": output_structure.OBSTACLE_FREE_ZONE,
}

GUIDELINE_F_CHECKLIST_LABELS = {
    "airport_wide": "Airport-wide OLS",
    "runway": "Runway Approach And Take-off OLS",
    "ofz": "Obstacle Free Zone",
}

EMPTY_GROUP_REASONS = {
    SAFEGUARDING_GROUP_NAME: "no UK safeguarding layers generated; check framework options and prerequisite inputs",
    GUIDELINE_GROUPS["C"]: "ARP missing or wildlife consultation circle generation failed",
    GUIDELINE_GROUPS["D"]: "ARP missing or wind-turbine consultation circle generation failed",
    GUIDELINE_GROUPS["I"]: "PSZ applicability was not selected, or runway inputs are incomplete",
}


def guideline_group_definitions(include_cns: bool = True) -> dict:
    del include_cns
    return dict(GUIDELINE_GROUPS)


def guideline_group_names(include_cns: bool = True) -> list:
    return list(guideline_group_definitions(include_cns).values())


def empty_group_reason(group_name: str) -> str:
    if group_name in EMPTY_GROUP_REASONS:
        return EMPTY_GROUP_REASONS[group_name]
    for guideline_name, reason in EMPTY_GROUP_REASONS.items():
        if group_name.startswith(guideline_name):
            return reason
    return ""
