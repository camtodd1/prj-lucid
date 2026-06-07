"""Current Annex 14 protected-airspace OLS scaffold.

The OFS/OES model captured in this package is part of the Annex 14
modernisation package effective from 21 November 2030. This module marks the
currently enforceable protected-airspace family as a separate guideline stream.
"""

CURRENT_OLS_REF = "Annex 14 Vol I current OLS"
PROTECTED_AIRSPACE_MODEL = "annex14_current_ols"

CURRENT_OLS_SURFACE_FAMILIES = {
    "approach": {
        "status": "pending_source_input",
        "notes": "Current Annex 14 OLS approach surface dimensions still need to be entered.",
    },
    "transitional": {
        "status": "pending_source_input",
        "notes": "Current Annex 14 OLS transitional surface dimensions still need to be entered.",
    },
    "inner_horizontal": {
        "status": "pending_source_input",
        "notes": "Current Annex 14 OLS inner horizontal surface dimensions still need to be entered.",
    },
    "conical": {
        "status": "pending_source_input",
        "notes": "Current Annex 14 OLS conical surface dimensions still need to be entered.",
    },
    "take_off_climb": {
        "status": "pending_source_input",
        "notes": "Current Annex 14 OLS take-off climb surface dimensions still need to be entered.",
    },
}


def protected_airspace_model():
    return PROTECTED_AIRSPACE_MODEL


def current_ols_surface_families():
    return dict(CURRENT_OLS_SURFACE_FAMILIES)


__all__ = [
    "CURRENT_OLS_REF",
    "PROTECTED_AIRSPACE_MODEL",
    "CURRENT_OLS_SURFACE_FAMILIES",
    "protected_airspace_model",
    "current_ols_surface_families",
]
