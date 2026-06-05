"""Australian NASF framework profile."""

from ..base import FrameworkProfile, capability_map
from . import cns, guidelines
from . import metadata


class NasfFrameworkProfile(FrameworkProfile):
    """NASF framework services for planning and safeguarding outputs."""

    def windshear_parameters(self) -> dict:
        return guidelines.windshear_parameters()

    def wildlife_parameters(self) -> dict:
        return guidelines.wildlife_parameters()

    def wind_turbine_parameters(self) -> dict:
        return guidelines.wind_turbine_parameters()

    def lighting_control_parameters(self) -> dict:
        return guidelines.lighting_control_parameters()

    def public_safety_area_parameters(self) -> dict:
        return guidelines.public_safety_area_parameters()

    def cns_spec(self, facility_type: str):
        return cns.get_cns_spec(facility_type)


NASF_PROFILE = NasfFrameworkProfile(
    id=metadata.FRAMEWORK_ID,
    display_name=metadata.DISPLAY_NAME,
    edition=metadata.EDITION,
    status=metadata.STATUS,
    description=metadata.DESCRIPTION,
    aliases=metadata.ALIASES,
    capabilities=capability_map(metadata.CAPABILITY_STATUS_BY_KEY),
)

__all__ = ["NASF_PROFILE", "NasfFrameworkProfile"]
