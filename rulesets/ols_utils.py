"""Shared helpers for ruleset OLS parameter lookups."""

from copy import deepcopy
from typing import Any, Mapping, Optional


VALID_ARC_NUMBERS = frozenset({1, 2, 3, 4})


def is_valid_arc_number(arc_num: Any) -> bool:
    """Return True when ``arc_num`` is one of the OLS ARC numbers."""
    return isinstance(arc_num, int) and arc_num in VALID_ARC_NUMBERS


def normalize_surface_type(surface_type: Optional[str]) -> str:
    """Normalize free-text OLS surface labels for lookup dispatch."""
    return "".join(char for char in str(surface_type or "").upper() if char.isalnum())


def detached_params(params: Any) -> Any:
    """Return a copy callers can mutate without changing ruleset constants."""
    return deepcopy(params)


def lookup_detached(mapping: Mapping[Any, Any], key: Any) -> Any:
    """Return a detached lookup value, or None if the key is absent."""
    params = mapping.get(key)
    return detached_params(params) if params is not None else None
