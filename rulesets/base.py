"""Base ruleset profile models.

The first ruleset pass deliberately keeps this module free of QGIS imports so
registry and policy lookup behaviour can be tested outside the QGIS runtime.
"""

from dataclasses import dataclass, field
from typing import Dict, Mapping, Optional


CapabilityStatus = str


@dataclass(frozen=True)
class RulesetCapability:
    """Advertised support level for an output family or policy service."""

    key: str
    status: CapabilityStatus
    notes: str = ""


@dataclass(frozen=True)
class RulesetProfile:
    """Metadata for an aerodrome standard implementation."""

    id: str
    display_name: str
    edition: str
    status: str
    description: str = ""
    aliases: tuple[str, ...] = field(default_factory=tuple)
    capabilities: Mapping[str, RulesetCapability] = field(default_factory=dict)

    def capability_status(self, key: str) -> Optional[CapabilityStatus]:
        capability = self.capabilities.get(key)
        return capability.status if capability else None

    def supports(self, key: str) -> bool:
        return self.capability_status(key) == "supported"


def capability_map(status_by_key: Dict[str, str]) -> Dict[str, RulesetCapability]:
    """Build a capability dictionary from compact key/status pairs."""
    return {
        key: RulesetCapability(key=key, status=status)
        for key, status in status_by_key.items()
    }
