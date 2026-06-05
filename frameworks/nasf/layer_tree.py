# -*- coding: utf-8 -*-
"""NASF layer tree labels and grouping metadata."""

SAFEGUARDING_GROUP_NAME = "04 NASF Safeguarding Guidelines"
SUMMARY_SECTION_NAME = "NASF Safeguarding Guidelines"
GENERATION_STATUS_MESSAGE = "Generating NASF guideline layers..."

GUIDELINE_GROUPS = {
    "B": "Guideline B - Windshear",
    "C": "Guideline C - Wildlife",
    "D": "Guideline D - Wind Turbine",
    "E": "Guideline E - Lighting Control",
    "F": "Guideline F - Airspace / OLS",
    "G": "Guideline G - CNS",
    "I": "Guideline I - Public Safety Areas",
}

GUIDELINE_F_SUBGROUPS = {
    "airport_wide": "Airport-wide OLS",
    "runway": "Runway Approach And Take-off",
    "ofz": "Obstacle Free Zone",
}

GUIDELINE_F_CHECKLIST_LABELS = {
    "airport_wide": "Guideline F - Airport-wide OLS",
    "runway": "Guideline F - Runway Approach And Take-off",
    "ofz": "Guideline F - Obstacle Free Zone",
}

EMPTY_GROUP_REASONS = {
    SAFEGUARDING_GROUP_NAME: "no NASF guideline layers generated; check prerequisite ARP, runway, and CNS inputs",
    GUIDELINE_GROUPS["B"]: "no windshear layers generated; check runway inputs and preceding warnings",
    GUIDELINE_GROUPS["C"]: "ARP missing or wildlife zone generation failed; check preceding Wildlife warnings",
    GUIDELINE_GROUPS["D"]: "ARP missing or wind turbine zone generation failed",
    GUIDELINE_GROUPS["E"]: "no lighting layers generated; check runway inputs and preceding warnings",
    GUIDELINE_GROUPS["F"]: "no airspace/OLS layers generated; check runway, approach, and RED inputs",
    GUIDELINE_GROUPS["G"]: "no CNS layers generated, or CNS input was not provided",
    GUIDELINE_GROUPS["I"]: "no public safety area layers generated; check runway inputs and preceding warnings",
}


def guideline_group_definitions(include_cns: bool = True) -> dict:
    """Return guideline folder labels keyed by NASF guideline letter."""
    definitions = dict(GUIDELINE_GROUPS)
    if not include_cns:
        definitions.pop("G", None)
    return definitions


def guideline_group_names(include_cns: bool = True) -> list:
    """Return guideline folder labels in NASF display order."""
    return list(guideline_group_definitions(include_cns).values())


def guideline_f_subgroup_names() -> dict:
    """Return Guideline F subfolder labels keyed by output type."""
    return dict(GUIDELINE_F_SUBGROUPS)


def guideline_f_checklist_labels() -> dict:
    """Return Guideline F checklist labels keyed by output type."""
    return dict(GUIDELINE_F_CHECKLIST_LABELS)


def empty_group_reason(group_name: str) -> str:
    """Return a NASF-specific reason for an empty generated group, if known."""
    if group_name in EMPTY_GROUP_REASONS:
        return EMPTY_GROUP_REASONS[group_name]
    for guideline_name, reason in EMPTY_GROUP_REASONS.items():
        if group_name.startswith(guideline_name):
            return reason
    return ""
