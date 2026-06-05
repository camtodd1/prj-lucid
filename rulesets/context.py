"""Policy context helpers used during generation."""

from dataclasses import dataclass, field
from typing import Tuple

try:
    from ..frameworks.base import FrameworkProfile
except ImportError:
    from frameworks.base import FrameworkProfile  # type: ignore

from .base import RulesetProfile


@dataclass(frozen=True)
class RulesetContext:
    """Active design standard plus safeguarding framework."""

    design_standard: RulesetProfile
    safeguarding_framework: FrameworkProfile
    supplementary_frameworks: Tuple[str, ...] = field(default_factory=tuple)

    @property
    def aerodrome_standard(self) -> RulesetProfile:
        return self.design_standard

    @property
    def ruleset_id(self) -> str:
        return self.design_standard.id

    @property
    def design_standard_id(self) -> str:
        return self.design_standard.id

    @property
    def framework_id(self) -> str:
        return self.safeguarding_framework.id
