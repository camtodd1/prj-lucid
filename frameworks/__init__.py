"""Safeguarding framework profiles and registry."""

from .registry import (
    DEFAULT_FRAMEWORK_ID,
    get_framework_profile,
    is_known_framework,
    iter_framework_profiles,
    normalize_framework_id,
)

__all__ = [
    "DEFAULT_FRAMEWORK_ID",
    "get_framework_profile",
    "is_known_framework",
    "iter_framework_profiles",
    "normalize_framework_id",
]
