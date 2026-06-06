"""Physical characteristics placeholders for ICAO Annex 14 Volume I."""

from typing import Optional

PHYSICAL_REFS = {
    "status": "pending_source_input",
    "notes": "Annex 14 physical characteristic tables have not yet been entered.",
}


def get_physical_refs() -> dict:
    return dict(PHYSICAL_REFS)


def get_strip_params(arc_num: int, type_abbr: str, runway_width: Optional[float]):
    return None


def get_resa_params(arc_num: int, type1_abbr: str, type2_abbr: str):
    return None


__all__ = ["get_physical_refs", "get_strip_params", "get_resa_params"]
