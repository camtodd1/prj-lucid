"""Registry for available safeguarding rulesets."""

from typing import Dict, Iterable, Mapping, Optional

from .base import RulesetProfile
from .mos139 import MOS139_PROFILE

DEFAULT_RULESET_ID = MOS139_PROFILE.id

_PROFILES: Dict[str, RulesetProfile] = {
    MOS139_PROFILE.id: MOS139_PROFILE,
}

_ALIASES: Dict[str, str] = {}
for _profile in _PROFILES.values():
    _ALIASES[_profile.id.lower()] = _profile.id
    for _alias in _profile.aliases:
        _ALIASES[_alias.lower()] = _profile.id


def _ruleset_id_from_payload(value) -> str:
    """Extract a ruleset id from legacy strings or future structured payloads."""
    if isinstance(value, Mapping):
        raw_id = value.get("id") or value.get("ruleset") or value.get("aerodrome_standard")
    else:
        raw_id = value
    return str(raw_id or DEFAULT_RULESET_ID).strip()


def normalize_ruleset_id(value) -> str:
    """Return the canonical ruleset id for a legacy or canonical value."""
    raw_id = _ruleset_id_from_payload(value)
    return _ALIASES.get(raw_id.lower(), raw_id)


def get_ruleset_profile(value=None) -> RulesetProfile:
    """Resolve a ruleset profile, falling back to the default profile."""
    ruleset_id = normalize_ruleset_id(value)
    return _PROFILES.get(ruleset_id, _PROFILES[DEFAULT_RULESET_ID])


def iter_ruleset_profiles() -> Iterable[RulesetProfile]:
    """Yield registered profiles in UI display order."""
    return tuple(_PROFILES.values())


def is_known_ruleset(value) -> bool:
    return normalize_ruleset_id(value) in _PROFILES
