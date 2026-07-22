"""UK CAA CAP 168 profile facade."""

from typing import Optional

from ..base import RulesetProfile, capability_map
from . import metadata
from .services import ClassificationService, LightingService, MarkingService, OlsService, PhysicalService


class Cap168RulesetProfile(RulesetProfile):
    """Public ruleset API for the UK CAA CAP 168 Edition 13 implementation."""

    classification = ClassificationService()
    ols = OlsService()
    physical = PhysicalService()
    markings = MarkingService()
    lighting = LightingService()

    def classify_runway_type(self, runway_type: Optional[str]) -> str:
        return self.classification.classify_runway_type(runway_type)

    def precision_type_codes(self) -> set[str]:
        return self.classification.precision_type_codes()

    def code_number(self, aeroplane_reference_field_length_m: Optional[float]):
        return self.classification.code_number(aeroplane_reference_field_length_m)

    def code_letter(self, wingspan_m: Optional[float]):
        return self.classification.code_letter(wingspan_m)

    def physical_refs(self) -> dict:
        return self.physical.refs()

    def runway_minimum_width(
        self,
        code_number: Optional[int],
        outer_main_gear_wheel_span_m: Optional[float] = None,
        runway_type: Optional[str] = None,
    ):
        return self.physical.runway_minimum_width(code_number, outer_main_gear_wheel_span_m, runway_type)

    def strip_parameters(
        self,
        arc_num: int,
        type_abbr: str,
        runway_width: Optional[float],
        has_rnp_apch: bool = False,
        minimum_runway_width_m: Optional[float] = None,
        starter_extension: bool = False,
        wingspan_m: Optional[float] = None,
        wing_overhang_m: Optional[float] = None,
    ):
        return self.physical.strip_parameters(
            arc_num,
            type_abbr,
            runway_width,
            has_rnp_apch=has_rnp_apch,
            minimum_runway_width_m=minimum_runway_width_m,
            starter_extension=starter_extension,
            wingspan_m=wingspan_m,
            wing_overhang_m=wing_overhang_m,
        )

    def resa_parameters(self, arc_num: int, type1_abbr: str, type2_abbr: str):
        return self.physical.resa_parameters(arc_num, type1_abbr, type2_abbr)

    def declared_distance_parameters(self):
        return self.physical.declared_distance_parameters()

    def clearway_parameters(
        self,
        runway_width: Optional[float] = None,
        strip_extension: Optional[float] = None,
        strip_overall_width: Optional[float] = None,
        physical_length: Optional[float] = None,
        clearway_primary_input: Optional[float] = None,
        clearway_reciprocal_input: Optional[float] = None,
        stopway_primary: Optional[float] = None,
        stopway_reciprocal: Optional[float] = None,
        is_instrument_runway: bool = False,
        arc_num: Optional[int] = None,
    ):
        return self.physical.clearway_parameters(
            runway_width=runway_width,
            strip_extension=strip_extension,
            strip_overall_width=strip_overall_width,
            physical_length=physical_length,
            clearway_primary_input=clearway_primary_input,
            clearway_reciprocal_input=clearway_reciprocal_input,
            stopway_primary=stopway_primary,
            stopway_reciprocal=stopway_reciprocal,
            is_instrument_runway=is_instrument_runway,
            arc_num=arc_num,
        )

    def stopway_parameters(self, runway_width: Optional[float] = None, stopway_length: Optional[float] = None):
        return self.physical.stopway_parameters(runway_width, stopway_length)

    def ihs_base_height(self):
        return self.ols.ihs_base_height()

    def ols_parameters(self, arc_num: int, runway_type: Optional[str], surface_type: str):
        return self.ols.parameters(arc_num, runway_type, surface_type)

    def taxiway_separation_offset(self, arc_num: int, arc_let: Optional[str], runway_type: Optional[str]):
        return self.physical.taxiway_separation_offset(arc_num, arc_let, runway_type)

    def taxiway_to_taxiway_separation(self, arc_let: Optional[str]):
        return self.physical.taxiway_to_taxiway_separation(arc_let)

    def taxiway_object_separation(self, arc_let: Optional[str]):
        return self.physical.taxiway_object_separation(arc_let)

    def stand_taxilane_to_stand_taxilane_separation(self, arc_let: Optional[str]):
        return self.physical.stand_taxilane_to_stand_taxilane_separation(arc_let)

    def stand_taxilane_object_separation(self, arc_let: Optional[str]):
        return self.physical.stand_taxilane_object_separation(arc_let)

    def parallel_runway_separation(
        self,
        arc_num_1: Optional[int] = None,
        arc_num_2: Optional[int] = None,
        runway_type_1: Optional[str] = None,
        runway_type_2: Optional[str] = None,
        operation_type: Optional[str] = None,
        arrival_threshold_stagger_m: Optional[float] = None,
    ):
        return self.physical.parallel_runway_separation(
            arc_num_1=arc_num_1,
            arc_num_2=arc_num_2,
            runway_type_1=runway_type_1,
            runway_type_2=runway_type_2,
            operation_type=operation_type,
            arrival_threshold_stagger_m=arrival_threshold_stagger_m,
        )

    def centreline_marking_width(self, arc_num: int, type_primary: str, type_reciprocal: str):
        return self.markings.centreline_marking_width(arc_num, type_primary, type_reciprocal)

    def threshold_marking_params(self, runway_width: float, runway_type: Optional[str] = None):
        return self.markings.threshold_marking_params(runway_width, runway_type)

    def threshold_marking_ref(self) -> str:
        return self.markings.threshold_marking_ref()

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

    def runway_edge_spacing_for_end(self, runway_type: str):
        return self.lighting.runway_edge_spacing_for_end(runway_type)

    def threshold_light_count_for_end(self, runway_type: str, runway_width_m: float):
        return self.lighting.threshold_light_count_for_end(runway_type, runway_width_m)

    def runway_end_light_count_for_end(self, runway_type: str, runway_width_m: float):
        return self.lighting.runway_end_light_count_for_end(runway_type, runway_width_m)

    def temp_displaced_threshold_lights_per_side(self, runway_width_m: float):
        return self.lighting.temp_displaced_threshold_lights_per_side(runway_width_m)

    def runway_centreline_required(
        self, runway_type_1: str, runway_type_2: str, rvr_below_350: bool = False
    ) -> bool:
        return self.lighting.runway_centreline_required(runway_type_1, runway_type_2, rvr_below_350)

    def runway_centreline_recommended(self, runway_type_1: str, runway_type_2: str, edge_light_width_m: float) -> bool:
        return self.lighting.runway_centreline_recommended(runway_type_1, runway_type_2, edge_light_width_m)

    def runway_centreline_spacing(self, rvr_below_350: bool):
        return self.lighting.runway_centreline_spacing(rvr_below_350)

    def approach_profile_for_end(self, runway_type: str):
        return self.lighting.approach_profile_for_end(runway_type)


CAP168_PROFILE = Cap168RulesetProfile(
    id=metadata.RULESET_ID,
    display_name=metadata.DISPLAY_NAME,
    edition=metadata.EDITION,
    status=metadata.STATUS,
    description=metadata.DESCRIPTION,
    aliases=metadata.ALIASES,
    capabilities=capability_map(metadata.CAPABILITY_STATUS_BY_KEY),
)

__all__ = ["CAP168_PROFILE", "Cap168RulesetProfile"]
