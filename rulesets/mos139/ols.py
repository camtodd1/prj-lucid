"""MOS139 OLS/classification policy wrappers."""

from typing import Optional

try:
    from . import classification
    from . import ols_surfaces
except ImportError:
    from rulesets.mos139 import classification  # type: ignore
    from rulesets.mos139 import ols_surfaces  # type: ignore


def classify_runway_type(runway_type: Optional[str]) -> str:
    return classification.get_runway_type_abbr(runway_type)


def precision_type_codes() -> set[str]:
    return set(classification.PRECISION_APPROACH_TYPES)


def ihs_base_height():
    return ols_surfaces.get_ihs_base_height()


def ols_parameters(arc_num: int, runway_type: Optional[str], surface_type: str):
    return ols_surfaces.get_ols_params(arc_num, runway_type, surface_type)


__all__ = [
    "classify_runway_type",
    "precision_type_codes",
    "ihs_base_height",
    "ols_parameters",
]
