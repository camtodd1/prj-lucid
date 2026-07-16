"""Registry for available safeguarding rulesets."""

from typing import Dict, Iterable, Mapping, Optional

from .base import RulesetProfile
from .annex14 import ANNEX14_CURRENT_OLS_PROFILE, ANNEX14_MODERNISED_OFS_OES_PROFILE
from .cap168 import CAP168_PROFILE
from .easa import EASA_PROFILE
from .mos139 import MOS139_PROFILE

DEFAULT_RULESET_ID = MOS139_PROFILE.id

_PROFILES: Dict[str, RulesetProfile] = {
    MOS139_PROFILE.id: MOS139_PROFILE,
    EASA_PROFILE.id: EASA_PROFILE,
    CAP168_PROFILE.id: CAP168_PROFILE,
    ANNEX14_CURRENT_OLS_PROFILE.id: ANNEX14_CURRENT_OLS_PROFILE,
    ANNEX14_MODERNISED_OFS_OES_PROFILE.id: ANNEX14_MODERNISED_OFS_OES_PROFILE,
}

_ALIASES: Dict[str, str] = {}
for _profile in _PROFILES.values():
    _ALIASES[_profile.id.lower()] = _profile.id
    for _alias in _profile.aliases:
        _ALIASES[_alias.lower()] = _profile.id


def _ruleset_id_from_payload(value) -> str:
    """Extract a ruleset id from legacy strings or future structured payloads."""
    if isinstance(value, Mapping):
        raw_id = value.get("id") or value.get("design_standard") or value.get("ruleset") or value.get("aerodrome_standard")
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


def iter_design_standard_profiles() -> Iterable[RulesetProfile]:
    """Yield profiles that represent selectable aerodrome design standards."""

    return tuple(
        profile
        for profile in _PROFILES.values()
        if profile.selectable_as_design_standard
    )


def normalize_design_standard_id(value) -> str:
    """Return a selectable design standard for current and legacy payloads."""

    ruleset_id = normalize_ruleset_id(value)
    profile = _PROFILES.get(ruleset_id)
    if profile is not None and profile.selectable_as_design_standard:
        return ruleset_id
    if ruleset_id == ANNEX14_MODERNISED_OFS_OES_PROFILE.id:
        return ANNEX14_CURRENT_OLS_PROFILE.id
    return DEFAULT_RULESET_ID


def is_known_ruleset(value) -> bool:
    return normalize_ruleset_id(value) in _PROFILES
