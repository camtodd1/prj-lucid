"""Base safeguarding framework profile models."""

from dataclasses import dataclass, field
from typing import Dict, Mapping, Optional


CapabilityStatus = str


@dataclass(frozen=True)
class FrameworkCapability:
    """Advertised support level for a safeguarding framework service."""

    key: str
    status: CapabilityStatus
    notes: str = ""


@dataclass(frozen=True)
class FrameworkProfile:
    """Metadata for a planning/safeguarding framework implementation."""

    id: str
    display_name: str
    edition: str
    status: str
    description: str = ""
    aliases: tuple[str, ...] = field(default_factory=tuple)
    capabilities: Mapping[str, FrameworkCapability] = field(default_factory=dict)

    def capability_status(self, key: str) -> Optional[CapabilityStatus]:
        capability = self.capabilities.get(key)
        return capability.status if capability else None

    def supports(self, key: str) -> bool:
        return self.capability_status(key) == "supported"


def capability_map(status_by_key: Dict[str, str]) -> Dict[str, FrameworkCapability]:
    """Build a capability dictionary from compact key/status pairs."""
    return {
        key: FrameworkCapability(key=key, status=status)
        for key, status in status_by_key.items()
    }
