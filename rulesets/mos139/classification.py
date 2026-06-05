"""MOS139 runway type classification policy."""

import logging
from typing import Optional

LOGGER = logging.getLogger(__name__)

RUNWAY_TYPE_MAP = {
    "": "NI",
    "Non-Instrument (NI)": "NI",
    "Non-Precision Approach (NPA)": "NPA",
    "Precision Approach CAT I": "PA_I",
    "Precision Approach CAT II/III": "PA_II_III",
}

PRECISION_APPROACH_TYPES = {"PA_I", "PA_II_III"}


def get_runway_type_abbr(runway_type_str: Optional[str]) -> str:
    """Map the UI runway type string to the MOS139 abbreviation."""
    if runway_type_str is None:
        return "NI"

    abbr = RUNWAY_TYPE_MAP.get(runway_type_str.strip())
    if abbr is None:
        LOGGER.warning(
            "Unknown runway type string %r could not be mapped, defaulting to NI.",
            runway_type_str,
        )
        return "NI"
    return abbr


__all__ = [
    "RUNWAY_TYPE_MAP",
    "PRECISION_APPROACH_TYPES",
    "get_runway_type_abbr",
]
