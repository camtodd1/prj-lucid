"""EASA CS-ADR-DSN Issue 6 profile facade."""

from typing import Optional

from ..base import RulesetProfile, capability_map
from . import metadata
from .services import ClassificationService, LightingService, MarkingService, OlsService, PhysicalService


class EasaRulesetProfile(RulesetProfile):
    """Public ruleset API for the EASA CS-ADR-DSN Issue 6 implementation."""

    classification = ClassificationService()
    ols = OlsService()
    physical = PhysicalService()
    markings = MarkingService()
    lighting = LightingService()

    def classify_runway_type(self, runway_type: Optional[str]) -> str:
        return self.classification.classify_runway_type(runway_type)

    def precision_type_codes(self) -> set[str]:
        return self.classification.precision_type_codes()

    def physical_refs(self) -> dict:
        return self.physical.refs()

    def strip_parameters(self, arc_num: int, type_abbr: str, runway_width: Optional[float]):
        return self.physical.strip_parameters(arc_num, type_abbr, runway_width)

    def resa_parameters(self, arc_num: int, type1_abbr: str, type2_abbr: str):
        return self.physical.resa_parameters(arc_num, type1_abbr, type2_abbr)

    def ihs_base_height(self):
        return self.ols.ihs_base_height()

    def ols_parameters(self, arc_num: int, runway_type: Optional[str], surface_type: str):
        return self.ols.parameters(arc_num, runway_type, surface_type)

    def taxiway_separation_offset(self, arc_num: int, arc_let: Optional[str], runway_type: Optional[str]):
        return self.physical.taxiway_separation_offset(arc_num, arc_let, runway_type)

    def centreline_marking_width(self, arc_num: int, type_primary: str, type_reciprocal: str) -> float:
        return self.markings.centreline_marking_width(arc_num, type_primary, type_reciprocal)

    def threshold_marking_params(self, runway_width: float):
        return self.markings.threshold_marking_params(runway_width)

    def aiming_point_rule(self, runway_width: float, lda_m: float, runway_type: str):
        return self.markings.aiming_point_rule(runway_width, lda_m, runway_type)

    def touchdown_zone_offsets(self, lda_m: float):
        return self.markings.touchdown_zone_offsets(lda_m)

    def runway_holding_position_rule(self, runway_code_num: int, runway_type: str):
        return self.markings.runway_holding_position_rule(runway_code_num, runway_type)

    def agl_value(self, name: str):
        return self.lighting.value(name)

    def runway_type_supports_agl(self, runway_type: str) -> bool:
        return self.lighting.runway_type_supports_agl(runway_type)

    def runway_is_precision(self, runway_type: str) -> bool:
        return self.lighting.runway_is_precision(runway_type)

    def runway_edge_spacing_for_end(self, runway_type: str) -> float:
        return self.lighting.runway_edge_spacing_for_end(runway_type)

    def threshold_light_count_for_end(self, runway_type: str, runway_width_m: float) -> int:
        return self.lighting.threshold_light_count_for_end(runway_type, runway_width_m)

    def runway_end_light_count_for_end(self, runway_type: str, runway_width_m: float) -> int:
        return self.lighting.runway_end_light_count_for_end(runway_type, runway_width_m)

    def temp_displaced_threshold_lights_per_side(self, runway_width_m: float) -> int:
        return self.lighting.temp_displaced_threshold_lights_per_side(runway_width_m)

    def runway_centreline_required(
        self, runway_type_1: str, runway_type_2: str, rvr_below_350: bool = False
    ) -> bool:
        return self.lighting.runway_centreline_required(runway_type_1, runway_type_2, rvr_below_350)

    def runway_centreline_recommended(self, runway_type_1: str, runway_type_2: str, edge_light_width_m: float) -> bool:
        return self.lighting.runway_centreline_recommended(runway_type_1, runway_type_2, edge_light_width_m)

    def runway_centreline_spacing(self, rvr_below_350: bool) -> float:
        return self.lighting.runway_centreline_spacing(rvr_below_350)

    def approach_profile_for_end(self, runway_type: str):
        return self.lighting.approach_profile_for_end(runway_type)


EASA_PROFILE = EasaRulesetProfile(
    id=metadata.RULESET_ID,
    display_name=metadata.DISPLAY_NAME,
    edition=metadata.EDITION,
    status=metadata.STATUS,
    description=metadata.DESCRIPTION,
    aliases=metadata.ALIASES,
    capabilities=capability_map(metadata.CAPABILITY_STATUS_BY_KEY),
)

__all__ = ["EASA_PROFILE", "EasaRulesetProfile"]
