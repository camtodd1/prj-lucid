"""Registry for available safeguarding frameworks."""

from typing import Dict, Iterable, Mapping

from .base import FrameworkProfile
from .nasf import NASF_PROFILE

DEFAULT_FRAMEWORK_ID = NASF_PROFILE.id

_PROFILES: Dict[str, FrameworkProfile] = {
    NASF_PROFILE.id: NASF_PROFILE,
}

_ALIASES: Dict[str, str] = {}
for _profile in _PROFILES.values():
    _ALIASES[_profile.id.lower()] = _profile.id
    for _alias in _profile.aliases:
        _ALIASES[_alias.lower()] = _profile.id


def _framework_id_from_payload(value) -> str:
    """Extract a framework id from legacy strings or future structured payloads."""
    if isinstance(value, Mapping):
        raw_id = (
            value.get("id")
            or value.get("safeguarding_framework")
            or value.get("framework")
            or value.get("supplementary_framework")
        )
    else:
        raw_id = value
    return str(raw_id or DEFAULT_FRAMEWORK_ID).strip()


def normalize_framework_id(value) -> str:
    """Return the canonical framework id for a legacy or canonical value."""
    raw_id = _framework_id_from_payload(value)
    return _ALIASES.get(raw_id.lower(), raw_id)


def get_framework_profile(value=None) -> FrameworkProfile:
    """Resolve a framework profile, falling back to the default profile."""
    framework_id = normalize_framework_id(value)
    return _PROFILES.get(framework_id, _PROFILES[DEFAULT_FRAMEWORK_ID])


def iter_framework_profiles() -> Iterable[FrameworkProfile]:
    """Yield registered frameworks in UI display order."""
    return tuple(_PROFILES.values())


def is_known_framework(value) -> bool:
    return normalize_framework_id(value) in _PROFILES
