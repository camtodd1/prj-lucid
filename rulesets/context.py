"""Ruleset context helpers used during generation."""

from dataclasses import dataclass, field
from typing import Tuple

from .base import RulesetProfile


@dataclass(frozen=True)
class RulesetContext:
    """Active aerodrome standard plus optional supplementary frameworks."""

    aerodrome_standard: RulesetProfile
    supplementary_frameworks: Tuple[str, ...] = field(default_factory=tuple)

    @property
    def ruleset_id(self) -> str:
        return self.aerodrome_standard.id
