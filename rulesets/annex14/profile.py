"""ICAO Annex 14 Volume I profile facade."""

from typing import Optional

from ..base import RulesetProfile, capability_map
from . import current_ols, metadata, physical_data
from .services import (
    ClassificationService,
    LightingService,
    MarkingService,
    ObstacleLimitationService,
    OesService,
    OlsService,
    PhysicalService,
)


class Annex14RulesetProfile(RulesetProfile):
    """Public ruleset API for the ICAO Annex 14 Volume I scaffold."""

    classification = ClassificationService()
    ols = OlsService()
    oes = OesService()
    obstacle_limitation = ObstacleLimitationService()
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

    def design_group(
        self,
        wingspan_m: Optional[float] = None,
        indicated_airspeed_at_threshold_kmh: Optional[float] = None,
        indicated_airspeed_at_threshold_kt: Optional[float] = None,
        outer_main_gear_wheel_span_m: Optional[float] = None,
        tail_height_m: Optional[float] = None,
    ):
        return self.classification.design_group(
            wingspan_m=wingspan_m,
            indicated_airspeed_at_threshold_kmh=indicated_airspeed_at_threshold_kmh,
            indicated_airspeed_at_threshold_kt=indicated_airspeed_at_threshold_kt,
            outer_main_gear_wheel_span_m=outer_main_gear_wheel_span_m,
            tail_height_m=tail_height_m,
        )

    def physical_refs(self) -> dict:
        return self.physical.refs()

    def strip_parameters(self, arc_num: int, type_abbr: str, runway_width: Optional[float]):
        if self.protected_airspace_model == "annex14_current_ols":
            return physical_data.get_current_strip_params(arc_num, type_abbr, runway_width)
        return self.physical.strip_parameters(arc_num, type_abbr, runway_width)

    def resa_parameters(self, arc_num: int, type1_abbr: str, type2_abbr: str):
        return self.physical.resa_parameters(arc_num, type1_abbr, type2_abbr)

    def ihs_base_height(self):
        if self.protected_airspace_model == "annex14_current_ols":
            return current_ols.ihs_base_height()
        return self.ols.ihs_base_height()

    def ols_parameters(self, arc_num: int, runway_type: Optional[str], surface_type: str):
        if self.protected_airspace_model == "annex14_current_ols":
            return current_ols.ols_parameters(arc_num, runway_type, surface_type)
        return self.ols.parameters(arc_num, runway_type, surface_type)

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
        if self.protected_airspace_model != "annex14_current_ols":
            return None
        return physical_data.get_current_clearway_params(
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

    def stopway_parameters(
        self,
        runway_width: Optional[float] = None,
        stopway_length: Optional[float] = None,
    ):
        if self.protected_airspace_model != "annex14_current_ols":
            return None
        return physical_data.get_current_stopway_params(runway_width, stopway_length)

    def approach_surface_parameters(
        self,
        design_group: Optional[str],
        runway_type: Optional[str],
        runway_width_m: Optional[float] = None,
        slope: Optional[float] = None,
        obstacle_clearance_height_m: Optional[float] = None,
    ):
        return self.ols.approach_surface_parameters(
            design_group=design_group,
            runway_type=runway_type,
            runway_width_m=runway_width_m,
            slope=slope,
            obstacle_clearance_height_m=obstacle_clearance_height_m,
        )

    def transitional_surface_parameters(self):
        return self.ols.transitional_surface_parameters()

    def inner_approach_surface_parameters(
        self,
        design_group: Optional[str],
        runway_type: Optional[str],
        approach_surface_slope: Optional[float] = None,
        code_letter_f_without_digital_avionics: bool = False,
    ):
        return self.ols.inner_approach_surface_parameters(
            design_group=design_group,
            runway_type=runway_type,
            approach_surface_slope=approach_surface_slope,
            code_letter_f_without_digital_avionics=code_letter_f_without_digital_avionics,
        )

    def inner_transitional_surface_parameters(
        self,
        design_group: Optional[str],
        runway_type: Optional[str],
    ):
        return self.ols.inner_transitional_surface_parameters(
            design_group=design_group,
            runway_type=runway_type,
        )

    def balked_landing_surface_parameters(
        self,
        design_group: Optional[str],
        code_letter_f_without_digital_avionics: bool = False,
    ):
        return self.ols.balked_landing_surface_parameters(
            design_group=design_group,
            code_letter_f_without_digital_avionics=code_letter_f_without_digital_avionics,
        )

    def obstacle_free_surfaces(
        self,
        design_group: Optional[str],
        runway_type: Optional[str],
        runway_width_m: Optional[float] = None,
        approach_surface_slope: Optional[float] = None,
        obstacle_clearance_height_m: Optional[float] = None,
        code_letter_f_without_digital_avionics: bool = False,
    ):
        return self.ols.obstacle_free_surfaces(
            design_group=design_group,
            runway_type=runway_type,
            runway_width_m=runway_width_m,
            approach_surface_slope=approach_surface_slope,
            obstacle_clearance_height_m=obstacle_clearance_height_m,
            code_letter_f_without_digital_avionics=code_letter_f_without_digital_avionics,
        )

    def oes_parameters(
        self,
        design_group: Optional[str] = None,
        runway_type: Optional[str] = None,
        operation_type: Optional[str] = None,
        surface_type: Optional[str] = None,
    ):
        return self.oes.parameters(
            design_group=design_group,
            runway_type=runway_type,
            operation_type=operation_type,
            surface_type=surface_type,
        )

    def horizontal_surface_parameters(self, design_group: Optional[str]):
        return self.oes.horizontal_surface_parameters(design_group)

    def horizontal_surfaces(self, design_groups):
        return self.oes.horizontal_surfaces(design_groups)

    def straight_in_instrument_approach_surface_parameters(self):
        return self.oes.straight_in_instrument_approach_surface_parameters()

    def precision_approach_surface_parameters(self):
        return self.oes.precision_approach_surface_parameters()

    def instrument_departure_surface_parameters(self):
        return self.oes.instrument_departure_surface_parameters()

    def take_off_climb_surface_parameters(
        self,
        design_group: Optional[str],
        max_certificated_takeoff_mass_kg: Optional[float] = None,
        slope: Optional[float] = None,
    ):
        return self.oes.take_off_climb_surface_parameters(
            design_group=design_group,
            max_certificated_takeoff_mass_kg=max_certificated_takeoff_mass_kg,
            slope=slope,
        )

    def obstacle_free_surface_requirements(self):
        return self.obstacle_limitation.obstacle_free_surface_requirements()

    def obstacle_evaluation_surface_requirements(self):
        return self.obstacle_limitation.obstacle_evaluation_surface_requirements()

    def obstacle_limitation_requirements(self, family: Optional[str] = None):
        return self.obstacle_limitation.requirements(family)

    def obstacle_free_surface_establishment(self, runway_type_abbr: Optional[str] = None):
        return self.obstacle_limitation.obstacle_free_surface_establishment(runway_type_abbr)

    def obstacle_evaluation_surface_establishment(self, operation: Optional[str] = None):
        return self.obstacle_limitation.obstacle_evaluation_surface_establishment(operation)

    def surface_establishment_requirements(self):
        return self.obstacle_limitation.surface_establishment_requirements()

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


ANNEX14_CURRENT_OLS_PROFILE = Annex14RulesetProfile(
    id=metadata.CURRENT_RULESET_ID,
    display_name=metadata.CURRENT_DISPLAY_NAME,
    edition=metadata.CURRENT_EDITION,
    status=metadata.CURRENT_STATUS,
    description=metadata.CURRENT_DESCRIPTION,
    aliases=metadata.CURRENT_ALIASES,
    capabilities=capability_map(metadata.CURRENT_CAPABILITY_STATUS_BY_KEY),
    protected_airspace_model="annex14_current_ols",
)

ANNEX14_MODERNISED_OFS_OES_PROFILE = Annex14RulesetProfile(
    id=metadata.MODERNISED_RULESET_ID,
    display_name=metadata.MODERNISED_DISPLAY_NAME,
    edition=metadata.MODERNISED_EDITION,
    status=metadata.MODERNISED_STATUS,
    description=metadata.MODERNISED_DESCRIPTION,
    aliases=metadata.MODERNISED_ALIASES,
    capabilities=capability_map(metadata.MODERNISED_CAPABILITY_STATUS_BY_KEY),
    protected_airspace_model="annex14_modernised_ofs_oes",
)

ANNEX14_PROFILE = ANNEX14_MODERNISED_OFS_OES_PROFILE

__all__ = [
    "ANNEX14_CURRENT_OLS_PROFILE",
    "ANNEX14_MODERNISED_OFS_OES_PROFILE",
    "ANNEX14_PROFILE",
    "Annex14RulesetProfile",
]
