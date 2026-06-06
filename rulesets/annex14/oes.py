"""Obstacle evaluation surface scaffold for ICAO Annex 14 derived workflows."""

from typing import Optional

OES_STATUS = "pending_source_input"


def surface_families() -> tuple:
    """Return implemented OES families once Annex 14/ADG tables are captured."""
    return tuple()


def parameters(
    design_group: Optional[str] = None,
    runway_type: Optional[str] = None,
    operation_type: Optional[str] = None,
    surface_type: Optional[str] = None,
):
    return None


__all__ = ["OES_STATUS", "surface_families", "parameters"]
