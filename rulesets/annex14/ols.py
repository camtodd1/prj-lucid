"""Obstacle limitation surface facade for the ICAO Annex 14 scaffold."""

from typing import Optional

from . import ols_surfaces


def ihs_base_height():
    return None


def ols_parameters(arc_num: int, runway_type: Optional[str], surface_type: str):
    return ols_surfaces.get_ols_params(arc_num, runway_type, surface_type)


__all__ = ["ihs_base_height", "ols_parameters"]
