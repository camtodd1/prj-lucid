"""Independent analytical helpers for source-backed OLS validation.

This module deliberately imports no production ruleset, surface, solver, or
QGIS code.  Expected inputs and results live in the accompanying source
manifest so that the validation does not calculate the answer from the system
under test.
"""

from __future__ import annotations

import math
from typing import Iterable, Mapping, Sequence


def piecewise_axis_elevation(
    base_elevation_m: float,
    station_m: float,
    sections: Sequence[Mapping[str, float]],
) -> float:
    """Return elevation along consecutive constant-slope axis sections."""
    if station_m < 0.0:
        raise ValueError("station_m must be non-negative")

    elevation_m = float(base_elevation_m)
    remaining_m = float(station_m)
    for section in sections:
        length_m = float(section["length_m"])
        slope = float(section["slope"])
        used_m = min(remaining_m, length_m)
        elevation_m += used_m * slope
        remaining_m -= used_m
        if remaining_m <= 1e-12:
            return elevation_m

    if remaining_m > 1e-9:
        raise ValueError("station_m lies beyond the supplied sections")
    return elevation_m


def first_station_for_elevation(
    base_elevation_m: float,
    target_elevation_m: float,
    sections: Sequence[Mapping[str, float]],
) -> float:
    """Return the first station at which a rising piecewise axis reaches Z."""
    current_elevation_m = float(base_elevation_m)
    current_station_m = 0.0
    target_elevation_m = float(target_elevation_m)
    if target_elevation_m < current_elevation_m:
        raise ValueError("target elevation is below the surface base")

    for section in sections:
        length_m = float(section["length_m"])
        slope = float(section["slope"])
        end_elevation_m = current_elevation_m + length_m * slope
        if slope > 0.0 and target_elevation_m <= end_elevation_m + 1e-12:
            return current_station_m + (target_elevation_m - current_elevation_m) / slope
        if slope == 0.0 and math.isclose(target_elevation_m, current_elevation_m, abs_tol=1e-12):
            return current_station_m
        current_elevation_m = end_elevation_m
        current_station_m += length_m

    raise ValueError("target elevation is not reached by the supplied sections")


def half_width_at_station(
    inner_edge_length_m: float,
    station_m: float,
    sections: Sequence[Mapping[str, float]],
) -> float:
    """Return half-width where each section divergence is measured per side."""
    if station_m < 0.0:
        raise ValueError("station_m must be non-negative")

    half_width_m = float(inner_edge_length_m) / 2.0
    remaining_m = float(station_m)
    for section in sections:
        length_m = float(section["length_m"])
        divergence = float(section.get("divergence", 0.0))
        used_m = min(remaining_m, length_m)
        half_width_m += used_m * divergence
        remaining_m -= used_m
        if remaining_m <= 1e-12:
            return half_width_m

    if remaining_m > 1e-9:
        raise ValueError("station_m lies beyond the supplied sections")
    return half_width_m


def conical_elevation(
    inner_horizontal_elevation_m: float,
    radial_offset_m: float,
    slope: float,
) -> float:
    """Return conical elevation at horizontal distance from the IHS edge."""
    if radial_offset_m < 0.0:
        raise ValueError("radial_offset_m must be non-negative")
    return float(inner_horizontal_elevation_m) + float(radial_offset_m) * float(slope)


def conical_offset_for_elevation(
    inner_horizontal_elevation_m: float,
    target_elevation_m: float,
    slope: float,
) -> float:
    """Return horizontal offset of a conical equal-height contour."""
    if slope <= 0.0:
        raise ValueError("slope must be positive")
    offset_m = (float(target_elevation_m) - float(inner_horizontal_elevation_m)) / float(slope)
    if offset_m < -1e-12:
        raise ValueError("target elevation is below the inner horizontal surface")
    return max(0.0, offset_m)


def transverse_elevation(lower_edge_elevation_m: float, offset_m: float, slope: float) -> float:
    """Return elevation along a surface rising perpendicular to its lower edge."""
    if offset_m < 0.0:
        raise ValueError("offset_m must be non-negative")
    return float(lower_edge_elevation_m) + float(offset_m) * float(slope)


def transverse_offset_for_elevation(
    lower_edge_elevation_m: float,
    target_elevation_m: float,
    slope: float,
) -> float:
    """Return horizontal offset of a transverse equal-height contour."""
    if slope <= 0.0:
        raise ValueError("slope must be positive")
    return (float(target_elevation_m) - float(lower_edge_elevation_m)) / float(slope)


def affine_delta(
    station_m: float,
    baseline_base_elevation_m: float,
    baseline_slope: float,
    future_base_elevation_m: float,
    future_slope: float,
) -> float:
    """Return future-minus-baseline elevation for two one-axis planes."""
    baseline_m = float(baseline_base_elevation_m) + float(baseline_slope) * float(station_m)
    future_m = float(future_base_elevation_m) + float(future_slope) * float(station_m)
    return future_m - baseline_m


def station_for_affine_delta(
    target_delta_m: float,
    baseline_base_elevation_m: float,
    baseline_slope: float,
    future_base_elevation_m: float,
    future_slope: float,
) -> float:
    """Return the station of a requested future-minus-baseline contour."""
    gradient = float(future_slope) - float(baseline_slope)
    if math.isclose(gradient, 0.0, abs_tol=1e-15):
        raise ValueError("parallel surfaces have no unique delta contour station")
    base_delta = float(future_base_elevation_m) - float(baseline_base_elevation_m)
    return (float(target_delta_m) - base_delta) / gradient


def controlling_identity(elevations_m: Mapping[str, float], tie_order: Iterable[str] = ()) -> str:
    """Return the lowest surface identity with an explicit deterministic tie order."""
    if not elevations_m:
        raise ValueError("at least one elevation is required")

    order = {surface_id: index for index, surface_id in enumerate(tie_order)}
    return min(
        elevations_m,
        key=lambda surface_id: (
            float(elevations_m[surface_id]),
            order.get(surface_id, len(order)),
            surface_id,
        ),
    )


def circular_axis_conical_intersection_y(
    station_m: float,
    circle_centre_x_m: float,
    inner_horizontal_radius_m: float,
    inner_horizontal_elevation_m: float,
    conical_slope: float,
    axis_base_elevation_m: float,
    axis_slope: float,
) -> float:
    """Return positive Y on an analytical axis-plane/conical equality curve.

    The IHS edge is a circle.  The conical surface rises with radial distance
    outside that circle, while the competing axis surface rises with station X.
    """
    if conical_slope <= 0.0:
        raise ValueError("conical_slope must be positive")

    station_m = float(station_m)
    axis_elevation_m = float(axis_base_elevation_m) + float(axis_slope) * station_m
    equality_radius_m = float(inner_horizontal_radius_m) + (
        axis_elevation_m - float(inner_horizontal_elevation_m)
    ) / float(conical_slope)
    dx_m = station_m - float(circle_centre_x_m)
    y_squared_m2 = equality_radius_m * equality_radius_m - dx_m * dx_m
    if y_squared_m2 < -1e-8:
        raise ValueError("station does not intersect the positive equality branch")
    return math.sqrt(max(0.0, y_squared_m2))


def circular_conical_elevation(
    x_m: float,
    y_m: float,
    circle_centre_x_m: float,
    inner_horizontal_radius_m: float,
    inner_horizontal_elevation_m: float,
    conical_slope: float,
) -> float:
    """Return elevation of a circular-IHS conical surface at X/Y."""
    radial_distance_m = math.hypot(float(x_m) - float(circle_centre_x_m), float(y_m))
    return float(inner_horizontal_elevation_m) + float(conical_slope) * (
        radial_distance_m - float(inner_horizontal_radius_m)
    )


__all__ = [
    "affine_delta",
    "circular_axis_conical_intersection_y",
    "circular_conical_elevation",
    "conical_elevation",
    "conical_offset_for_elevation",
    "controlling_identity",
    "first_station_for_elevation",
    "half_width_at_station",
    "piecewise_axis_elevation",
    "station_for_affine_delta",
    "transverse_elevation",
    "transverse_offset_for_elevation",
]
