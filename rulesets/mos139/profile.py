"""CASA Part 139 MOS 2019 profile facade."""

from typing import Optional

from ..base import RulesetProfile, capability_map
from . import classification, lighting, markings, metadata, ols_surfaces, physical_data, taxiway


class Mos139RulesetProfile(RulesetProfile):
    """Public ruleset API for the MOS139 C.07 2026 implementation."""

    def classify_runway_type(self, runway_type: Optional[str]) -> str:
        return classification.get_runway_type_abbr(runway_type)

    def precision_type_codes(self) -> set[str]:
        return set(classification.PRECISION_APPROACH_TYPES)

    def physical_refs(self) -> dict:
        return physical_data.get_physical_refs()

    def strip_parameters(self, arc_num: int, type_abbr: str, runway_width: Optional[float]):
        return physical_data.get_strip_params(arc_num, type_abbr, runway_width)

    def resa_parameters(self, arc_num: int, type1_abbr: str, type2_abbr: str):
        return physical_data.get_resa_params(arc_num, type1_abbr, type2_abbr)

    def ihs_base_height(self):
        return ols_surfaces.get_ihs_base_height()

    def ols_parameters(self, arc_num: int, runway_type: Optional[str], surface_type: str):
        return ols_surfaces.get_ols_params(arc_num, runway_type, surface_type)

    def inner_approach_parameters(self, arc_num: int, runway_type: Optional[str], arc_let: Optional[str] = None):
        return ols_surfaces.get_inner_approach_params(arc_num, runway_type, arc_let)

    def baulked_landing_parameters(self, arc_num: int, runway_type: Optional[str], arc_let: Optional[str] = None):
        return ols_surfaces.get_baulked_landing_params(arc_num, runway_type, arc_let)

    def taxiway_separation_offset(self, arc_num: int, arc_let: Optional[str], runway_type: Optional[str]):
        return taxiway.get_taxiway_separation_offset(arc_num, arc_let, runway_type)

    def taxiway_to_taxiway_separation(self, arc_let: Optional[str]):
        return taxiway.get_taxiway_to_taxiway_separation(arc_let)

    def taxiway_object_separation(self, arc_let: Optional[str]):
        return taxiway.get_taxiway_object_separation(arc_let)

    def stand_taxilane_to_stand_taxilane_separation(self, arc_let: Optional[str]):
        return taxiway.get_stand_taxilane_to_stand_taxilane_separation(arc_let)

    def stand_taxilane_object_separation(self, arc_let: Optional[str]):
        return taxiway.get_stand_taxilane_object_separation(arc_let)

    def parallel_runway_separation(
        self,
        arc_num_1: Optional[int] = None,
        arc_num_2: Optional[int] = None,
        runway_type_1: Optional[str] = None,
        runway_type_2: Optional[str] = None,
        operation_type: Optional[str] = None,
        arrival_threshold_stagger_m: Optional[float] = None,
    ):
        return taxiway.get_parallel_runway_separation(
            arc_num_1=arc_num_1,
            arc_num_2=arc_num_2,
            runway_type_1=runway_type_1,
            runway_type_2=runway_type_2,
            operation_type=operation_type,
            arrival_threshold_stagger_m=arrival_threshold_stagger_m,
        )

    def centreline_marking_width(self, arc_num: int, type_primary: str, type_reciprocal: str) -> float:
        return markings.centreline_marking_width(arc_num, type_primary, type_reciprocal)

    def threshold_marking_params(self, runway_width: float):
        return markings.threshold_marking_params(runway_width)

    def starter_extension_marking_rule(self, arc_num: int, type_primary: str, type_reciprocal: str):
        return markings.starter_extension_marking_rule(arc_num, type_primary, type_reciprocal)

    def aiming_point_rule(self, runway_width: float, lda_m: float, runway_type: str):
        return markings.aiming_point_rule(runway_width, lda_m, runway_type)

    def touchdown_zone_offsets(self, lda_m: float):
        return markings.touchdown_zone_offsets(lda_m)

    def runway_holding_position_rule(self, runway_code_num: int, runway_type: str):
        return markings.runway_holding_position_rule(runway_code_num, runway_type)

    def agl_value(self, name: str):
        return lighting.agl_value(name)

    def runway_type_supports_agl(self, runway_type: str) -> bool:
        return lighting.runway_type_supports_agl(runway_type)

    def runway_is_precision(self, runway_type: str) -> bool:
        return lighting.runway_is_precision(runway_type)

    def runway_edge_spacing_for_end(self, runway_type: str) -> float:
        return lighting.runway_edge_spacing_for_end(runway_type)

    def threshold_light_count_for_end(self, runway_type: str, runway_width_m: float) -> int:
        return lighting.threshold_light_count_for_end(runway_type, runway_width_m)

    def runway_end_light_count_for_end(self, runway_type: str, runway_width_m: float) -> int:
        return lighting.runway_end_light_count_for_end(runway_type, runway_width_m)

    def temp_displaced_threshold_lights_per_side(self, runway_width_m: float) -> int:
        return lighting.temp_displaced_threshold_lights_per_side(runway_width_m)

    def runway_centreline_required(
        self, runway_type_1: str, runway_type_2: str, rvr_below_350: bool = False
    ) -> bool:
        return lighting.runway_centreline_required(runway_type_1, runway_type_2, rvr_below_350)

    def runway_centreline_recommended(self, runway_type_1: str, runway_type_2: str, edge_light_width_m: float) -> bool:
        return lighting.runway_centreline_recommended(runway_type_1, runway_type_2, edge_light_width_m)

    def runway_centreline_spacing(self, rvr_below_350: bool) -> float:
        return lighting.runway_centreline_spacing(rvr_below_350)

    def approach_profile_for_end(self, runway_type: str):
        return lighting.approach_profile_for_end(runway_type)


MOS139_PROFILE = Mos139RulesetProfile(
    id=metadata.RULESET_ID,
    display_name=metadata.DISPLAY_NAME,
    edition=metadata.EDITION,
    status=metadata.STATUS,
    description=metadata.DESCRIPTION,
    aliases=metadata.ALIASES,
    capabilities=capability_map(metadata.CAPABILITY_STATUS_BY_KEY),
)

__all__ = ["MOS139_PROFILE", "Mos139RulesetProfile"]
