"""EASA OLS/classification policy wrappers."""

from typing import Optional

from . import classification


def classify_runway_type(runway_type: Optional[str]) -> str:
    return classification.get_runway_type_abbr(runway_type)


def precision_type_codes() -> set[str]:
    return set(classification.PRECISION_APPROACH_TYPES)


def ihs_base_height():
    return None


def ols_parameters(arc_num: int, runway_type: Optional[str], surface_type: str):
    return None


__all__ = [
    "classify_runway_type",
    "precision_type_codes",
    "ihs_base_height",
    "ols_parameters",
]
