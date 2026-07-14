"""EASA runway type classification policy."""

import logging
from typing import Optional

LOGGER = logging.getLogger(__name__)

RUNWAY_TYPE_MAP = {
    "": "NI",
    "Non-Instrument (NI)": "NI",
    "Non-Instrument": "NI",
    "Non-Precision Approach (NPA)": "NPA",
    "Non-Precision": "NPA",
    "Precision Approach CAT I": "PA_I",
    "Precision Approach Category I": "PA_I",
    "Precision Approach CAT II/III": "PA_II_III",
    "Precision Approach Category II/III": "PA_II_III",
}

PRECISION_APPROACH_TYPES = {"PA_I", "PA_II_III"}


def get_runway_type_abbr(runway_type_str: Optional[str]) -> str:
    """Map the UI runway type string to the EASA runway type abbreviation."""
    if runway_type_str is None:
        return "NI"

    value = runway_type_str.strip()
    if value in {"NI", "NPA", "PA_I", "PA_II_III"}:
        return value
    abbr = RUNWAY_TYPE_MAP.get(value)
    if abbr is not None:
        return abbr

    if "CAT II" in value or "CAT III" in value:
        return "PA_II_III"
    if "Precision Approach" in value:
        return "PA_I"
    if "Non-Precision" in value or "Non‑Precision" in value:
        return "NPA"
    if "Non-Instrument" in value or "Non‑Instrument" in value:
        return "NI"

    LOGGER.warning(
        "Unknown EASA runway type string %r could not be mapped, defaulting to NI.",
        runway_type_str,
    )
    return "NI"


__all__ = [
    "RUNWAY_TYPE_MAP",
    "PRECISION_APPROACH_TYPES",
    "get_runway_type_abbr",
]
