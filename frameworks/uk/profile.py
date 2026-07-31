"""United Kingdom CAA/DfT safeguarding framework profile."""

from typing import Mapping, Optional

from ..base import FrameworkProfile, capability_map
from . import guidelines, layer_tree, metadata


class UkFrameworkProfile(FrameworkProfile):
    """UK services implemented as source-scoped safeguarding mechanisms."""

    def wildlife_parameters(self, options: Optional[Mapping[str, object]] = None) -> dict:
        return guidelines.wildlife_parameters(options)

    def wind_turbine_parameters(self, options: Optional[Mapping[str, object]] = None) -> dict:
        return guidelines.wind_turbine_parameters(options)

    def public_safety_area_parameters(
        self, options: Optional[Mapping[str, object]] = None
    ) -> dict:
        return guidelines.public_safety_area_parameters(options)

    def crane_notification_parameters(self) -> dict:
        return guidelines.crane_notification_parameters()

    def screen_crane_notification(
        self,
        distance_to_aerodrome_m: float,
        height_agl_m: float,
        shielded_by_surroundings: bool = False,
        surrounding_height_agl_m: float = 0.0,
        in_situ_days: int = 0,
    ) -> dict:
        return guidelines.screen_crane_notification(
            distance_to_aerodrome_m,
            height_agl_m,
            shielded_by_surroundings,
            surrounding_height_agl_m,
            in_situ_days,
        )

    def safeguarding_group_name(self) -> str:
        return layer_tree.SAFEGUARDING_GROUP_NAME

    def safeguarding_summary_section(self) -> str:
        return layer_tree.SUMMARY_SECTION_NAME

    def generation_status_message(self) -> str:
        return layer_tree.GENERATION_STATUS_MESSAGE

    def guideline_group_definitions(
        self,
        include_cns: bool = True,
        options: Optional[Mapping[str, object]] = None,
    ) -> dict:
        definitions = layer_tree.guideline_group_definitions(include_cns)
        if options is not None and not self.public_safety_area_parameters(options)["enabled"]:
            definitions.pop("I", None)
        crane = options.get("crane", {}) if isinstance(options, Mapping) else {}
        if not isinstance(crane, Mapping) or not bool(crane.get("enabled", False)):
            definitions.pop("K", None)
        return definitions

    def guideline_group_name(self, guideline_key: str) -> str:
        return layer_tree.GUIDELINE_GROUPS[guideline_key]

    def guideline_group_names(self, include_cns: bool = True) -> list:
        return layer_tree.guideline_group_names(include_cns)

    def guideline_f_subgroup_names(self) -> dict:
        return dict(layer_tree.GUIDELINE_F_SUBGROUPS)

    def guideline_f_checklist_labels(self) -> dict:
        return dict(layer_tree.GUIDELINE_F_CHECKLIST_LABELS)

    def empty_group_reason(self, group_name: str) -> str:
        return layer_tree.empty_group_reason(group_name)


UK_PROFILE = UkFrameworkProfile(
    id=metadata.FRAMEWORK_ID,
    display_name=metadata.DISPLAY_NAME,
    edition=metadata.EDITION,
    status=metadata.STATUS,
    description=metadata.DESCRIPTION,
    aliases=metadata.ALIASES,
    capabilities=capability_map(metadata.CAPABILITY_STATUS_BY_KEY),
)

__all__ = ["UK_PROFILE", "UkFrameworkProfile"]
