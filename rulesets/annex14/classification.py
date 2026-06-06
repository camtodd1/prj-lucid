"""Classification helpers for the ICAO Annex 14 Volume I scaffold."""

from typing import Optional

RUNWAY_TYPE_MAP = {
    "Non-Instrument (NI)": "NI",
    "Non-Precision Approach (NPA)": "NPA",
    "Precision Approach CAT I": "PA_I",
    "Precision Approach CAT II/III": "PA_II_III",
    None: "NI",
}

PRECISION_APPROACH_TYPES = {"PA_I", "PA_II_III"}

DESIGN_GROUP_STATUS = "pending_source_input"


def get_runway_type_abbr(runway_type: Optional[str]) -> str:
    """Return the internal runway type code used by ruleset policy tables."""
    return RUNWAY_TYPE_MAP.get(runway_type, "NI")


def classify_design_group(
    wingspan_m: Optional[float] = None,
    outer_main_gear_wheel_span_m: Optional[float] = None,
    tail_height_m: Optional[float] = None,
):
    """Placeholder for Annex 14 design group classification inputs.

    Annex 14 primarily uses aerodrome reference code number/letter. The app may
    also need an FAA-style ADG compatibility layer for OES workflows, so this
    intentionally keeps both input families explicit until source tables are
    captured.
    """
    return None


__all__ = [
    "RUNWAY_TYPE_MAP",
    "PRECISION_APPROACH_TYPES",
    "DESIGN_GROUP_STATUS",
    "get_runway_type_abbr",
    "classify_design_group",
]
