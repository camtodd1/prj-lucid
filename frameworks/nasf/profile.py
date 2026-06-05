"""Australian NASF framework profile."""

from ..base import FrameworkProfile, capability_map
from . import cns, guidelines, layer_tree
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

    def safeguarding_group_name(self) -> str:
        return layer_tree.SAFEGUARDING_GROUP_NAME

    def safeguarding_summary_section(self) -> str:
        return layer_tree.SUMMARY_SECTION_NAME

    def generation_status_message(self) -> str:
        return layer_tree.GENERATION_STATUS_MESSAGE

    def guideline_group_definitions(self, include_cns: bool = True) -> dict:
        return layer_tree.guideline_group_definitions(include_cns)

    def guideline_group_name(self, guideline_key: str) -> str:
        return layer_tree.GUIDELINE_GROUPS[guideline_key]

    def guideline_group_names(self, include_cns: bool = True) -> list:
        return layer_tree.guideline_group_names(include_cns)

    def guideline_f_subgroup_names(self) -> dict:
        return layer_tree.guideline_f_subgroup_names()

    def guideline_f_checklist_labels(self) -> dict:
        return layer_tree.guideline_f_checklist_labels()

    def empty_group_reason(self, group_name: str) -> str:
        return layer_tree.empty_group_reason(group_name)


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
