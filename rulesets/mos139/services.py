"""Grouped MOS139 ruleset service adapters."""

from typing import Optional

from . import classification as classification_policy
from . import lighting as lighting_policy
from . import markings as marking_policy
from . import ols_surfaces
from . import physical_data
from . import taxiway


class ClassificationService:
    def classify_runway_type(self, runway_type: Optional[str]) -> str:
        return classification_policy.get_runway_type_abbr(runway_type)

    def precision_type_codes(self) -> set[str]:
        return set(classification_policy.PRECISION_APPROACH_TYPES)


class OlsService:
    def ihs_base_height(self):
        return ols_surfaces.get_ihs_base_height()

    def parameters(self, arc_num: int, runway_type: Optional[str], surface_type: str):
        return ols_surfaces.get_ols_params(arc_num, runway_type, surface_type)


class PhysicalService:
    def refs(self) -> dict:
        return physical_data.get_physical_refs()

    def strip_parameters(self, arc_num: int, type_abbr: str, runway_width: Optional[float]):
        return physical_data.get_strip_params(arc_num, type_abbr, runway_width)

    def resa_parameters(self, arc_num: int, type1_abbr: str, type2_abbr: str):
        return physical_data.get_resa_params(arc_num, type1_abbr, type2_abbr)

    def taxiway_separation_offset(self, arc_num: int, arc_let: Optional[str], runway_type: Optional[str]):
        return taxiway.get_taxiway_separation_offset(arc_num, arc_let, runway_type)


class MarkingService:
    def centreline_marking_width(self, arc_num: int, type_primary: str, type_reciprocal: str) -> float:
        return marking_policy.centreline_marking_width(arc_num, type_primary, type_reciprocal)

    def threshold_marking_params(self, runway_width: float):
        return marking_policy.threshold_marking_params(runway_width)

    def aiming_point_rule(self, runway_width: float, lda_m: float, runway_type: str):
        return marking_policy.aiming_point_rule(runway_width, lda_m, runway_type)

    def touchdown_zone_offsets(self, lda_m: float):
        return marking_policy.touchdown_zone_offsets(lda_m)

    def runway_holding_position_rule(self, runway_code_num: int, runway_type: str):
        return marking_policy.runway_holding_position_rule(runway_code_num, runway_type)


class LightingService:
    def value(self, name: str):
        return lighting_policy.agl_value(name)

    def runway_type_supports_agl(self, runway_type: str) -> bool:
        return lighting_policy.runway_type_supports_agl(runway_type)

    def runway_is_precision(self, runway_type: str) -> bool:
        return lighting_policy.runway_is_precision(runway_type)

    def runway_edge_spacing_for_end(self, runway_type: str) -> float:
        return lighting_policy.runway_edge_spacing_for_end(runway_type)

    def threshold_light_count_for_end(self, runway_type: str, runway_width_m: float) -> int:
        return lighting_policy.threshold_light_count_for_end(runway_type, runway_width_m)

    def runway_end_light_count_for_end(self, runway_type: str, runway_width_m: float) -> int:
        return lighting_policy.runway_end_light_count_for_end(runway_type, runway_width_m)

    def temp_displaced_threshold_lights_per_side(self, runway_width_m: float) -> int:
        return lighting_policy.temp_displaced_threshold_lights_per_side(runway_width_m)

    def runway_centreline_required(
        self, runway_type_1: str, runway_type_2: str, rvr_below_350: bool = False
    ) -> bool:
        return lighting_policy.runway_centreline_required(runway_type_1, runway_type_2, rvr_below_350)

    def runway_centreline_recommended(
        self, runway_type_1: str, runway_type_2: str, edge_light_width_m: float
    ) -> bool:
        return lighting_policy.runway_centreline_recommended(runway_type_1, runway_type_2, edge_light_width_m)

    def runway_centreline_spacing(self, rvr_below_350: bool) -> float:
        return lighting_policy.runway_centreline_spacing(rvr_below_350)

    def approach_profile_for_end(self, runway_type: str):
        return lighting_policy.approach_profile_for_end(runway_type)


__all__ = [
    "ClassificationService",
    "OlsService",
    "PhysicalService",
    "MarkingService",
    "LightingService",
]
