"""Obstacle limitation surface facade for the ICAO Annex 14 scaffold."""

from typing import Optional

from . import ols_surfaces


def ihs_base_height():
    return None


def ols_parameters(arc_num: int, runway_type: Optional[str], surface_type: str):
    return ols_surfaces.get_ols_params(arc_num, runway_type, surface_type)


def approach_surface_parameters(
    design_group: Optional[str],
    runway_type: Optional[str],
    runway_width_m: Optional[float] = None,
    slope: Optional[float] = None,
    obstacle_clearance_height_m: Optional[float] = None,
):
    return ols_surfaces.get_approach_surface_params(
        design_group=design_group,
        runway_type=runway_type,
        runway_width_m=runway_width_m,
        slope=slope,
        obstacle_clearance_height_m=obstacle_clearance_height_m,
    )


def transitional_surface_parameters():
    return ols_surfaces.get_transitional_surface_params()


def inner_approach_surface_parameters(
    design_group: Optional[str],
    runway_type: Optional[str],
    approach_surface_slope: Optional[float] = None,
    code_letter_f_without_digital_avionics: bool = False,
):
    return ols_surfaces.get_inner_approach_surface_params(
        design_group=design_group,
        runway_type=runway_type,
        approach_surface_slope=approach_surface_slope,
        code_letter_f_without_digital_avionics=code_letter_f_without_digital_avionics,
    )


def inner_transitional_surface_parameters(
    design_group: Optional[str],
    runway_type: Optional[str],
):
    return ols_surfaces.get_inner_transitional_surface_params(
        design_group=design_group,
        runway_type=runway_type,
    )


def balked_landing_surface_parameters(
    design_group: Optional[str],
    code_letter_f_without_digital_avionics: bool = False,
):
    return ols_surfaces.get_balked_landing_surface_params(
        design_group=design_group,
        code_letter_f_without_digital_avionics=code_letter_f_without_digital_avionics,
    )


def obstacle_free_surfaces(
    design_group: Optional[str],
    runway_type: Optional[str],
    runway_width_m: Optional[float] = None,
    approach_surface_slope: Optional[float] = None,
    obstacle_clearance_height_m: Optional[float] = None,
    code_letter_f_without_digital_avionics: bool = False,
):
    return ols_surfaces.get_obstacle_free_surfaces(
        design_group=design_group,
        runway_type=runway_type,
        runway_width_m=runway_width_m,
        approach_surface_slope=approach_surface_slope,
        obstacle_clearance_height_m=obstacle_clearance_height_m,
        code_letter_f_without_digital_avionics=code_letter_f_without_digital_avionics,
    )


__all__ = [
    "ihs_base_height",
    "ols_parameters",
    "approach_surface_parameters",
    "transitional_surface_parameters",
    "inner_approach_surface_parameters",
    "inner_transitional_surface_parameters",
    "balked_landing_surface_parameters",
    "obstacle_free_surfaces",
]
