"""Australian NASF framework profile."""

from ..base import FrameworkProfile, capability_map
from . import metadata


NASF_PROFILE = FrameworkProfile(
    id=metadata.FRAMEWORK_ID,
    display_name=metadata.DISPLAY_NAME,
    edition=metadata.EDITION,
    status=metadata.STATUS,
    description=metadata.DESCRIPTION,
    aliases=metadata.ALIASES,
    capabilities=capability_map(metadata.CAPABILITY_STATUS_BY_KEY),
)

__all__ = ["NASF_PROFILE"]
