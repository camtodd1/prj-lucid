"""Provisional NASF ILS Building Restricted Area construction."""

import math
from typing import Any, Dict, List, Sequence, Tuple

from qgis.core import QgsGeometry, QgsLineString, QgsPoint, QgsPointXY, QgsPolygon  # type: ignore


GP_BRA_FORWARD_EXTENT_M = 1500.0
GP_BRA_HORIZONTAL_LENGTH_M = 300.0
GP_BRA_OUTER_MARGIN_M = 40.0
GP_BRA_REAR_LENGTH_M = 50.0
GP_BRA_REAR_HALF_WIDTH_M = 40.0
GP_BRA_PLAN_DIVERGENCE = 4.0
GP_BRA_LONGITUDINAL_SLOPE_DEG = 0.5
GP_BRA_LATERAL_SLOPE_DEG = 2.0

LOC_BRA_HORIZONTAL_LENGTH_M = 300.0
LOC_BRA_REAR_LENGTH_M = 50.0
LOC_BRA_HALF_WIDTH_M = 45.0
LOC_BRA_PLAN_DIVERGENCE = 4.0
LOC_BRA_LONGITUDINAL_SLOPE_DEG = 0.5
LOC_BRA_LATERAL_SLOPE_DEG = 2.0
LOC_BRA_BEYOND_THRESHOLD_M = 500.0
LOC_BRA_CATEGORY_HALF_WIDTH_M = {
    "cat_i": 500.0,
    "cat_ii_iii": 1000.0,
}


def _polygon_z(points: Sequence[Tuple[float, float, float]]) -> QgsGeometry:
    ring_points = [QgsPoint(float(x), float(y), float(z)) for x, y, z in points]
    first = ring_points[0]
    last = ring_points[-1]
    if abs(first.x() - last.x()) > 1e-9 or abs(first.y() - last.y()) > 1e-9:
        ring_points.append(QgsPoint(first.x(), first.y(), first.z()))
    return QgsGeometry(QgsPolygon(QgsLineString(ring_points)))


def construct_provisional_glide_path_bra(
    installation: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """Return the four worked-example GP BRA pieces as PolygonZ geometries.

    The local origin is the centre of the glide-path antenna front face. Local
    ``x`` points toward the selected runway threshold and local ``q`` points
    away from the runway centreline.
    """
    origin = installation.get("front_face_point") or installation.get("point")
    if not isinstance(origin, QgsPointXY):
        raise ValueError("front-face point is required")
    interior_unit = installation.get("runway_interior_unit")
    if not isinstance(interior_unit, (tuple, list)) or len(interior_unit) != 2:
        raise ValueError("runway interior unit vector is required")
    interior_e = float(interior_unit[0])
    interior_n = float(interior_unit[1])
    unit_length = math.hypot(interior_e, interior_n)
    if unit_length <= 1e-9:
        raise ValueError("runway interior unit vector is invalid")
    interior_e /= unit_length
    interior_n /= unit_length
    signed_offset = float(installation.get("signed_offset"))
    if abs(signed_offset) <= 1e-9:
        raise ValueError("non-zero glide-path offset is required")
    ground_elevation = float(installation.get("ground_elevation"))

    # Toward the associated threshold is opposite the runway-interior vector.
    forward_e = -interior_e
    forward_n = -interior_n
    right_e = interior_n
    right_n = -interior_e
    side_sign = 1.0 if signed_offset > 0 else -1.0
    away_e = side_sign * right_e
    away_n = side_sign * right_n
    antenna_offset = abs(signed_offset)
    divergence_width = (
        GP_BRA_FORWARD_EXTENT_M - GP_BRA_HORIZONTAL_LENGTH_M
    ) / GP_BRA_PLAN_DIVERGENCE
    longitudinal_slope = math.tan(math.radians(GP_BRA_LONGITUDINAL_SLOPE_DEG))
    lateral_slope = math.tan(math.radians(GP_BRA_LATERAL_SLOPE_DEG))

    def map_point(local_x: float, local_q: float, elevation: float) -> Tuple[float, float, float]:
        return (
            origin.x() + local_x * forward_e + local_q * away_e,
            origin.y() + local_x * forward_n + local_q * away_n,
            elevation,
        )

    base_inner_q = -antenna_offset
    base_outer_q = GP_BRA_OUTER_MARGIN_M
    forward_z = ground_elevation + (
        GP_BRA_FORWARD_EXTENT_M - GP_BRA_HORIZONTAL_LENGTH_M
    ) * longitudinal_slope
    lateral_outer_z = ground_elevation + divergence_width * lateral_slope

    definitions = [
        {
            "surface_name": "Horizontal base",
            "surface_role": "provisional_horizontal_base",
            "slope_degrees": 0.0,
            "geometry": _polygon_z(
                [
                    map_point(0.0, base_inner_q, ground_elevation),
                    map_point(GP_BRA_HORIZONTAL_LENGTH_M, base_inner_q, ground_elevation),
                    map_point(GP_BRA_HORIZONTAL_LENGTH_M, base_outer_q, ground_elevation),
                    map_point(0.0, base_outer_q, ground_elevation),
                ]
            ),
        },
        {
            "surface_name": "Rear horizontal area",
            "surface_role": "provisional_rear_horizontal",
            "slope_degrees": 0.0,
            "geometry": _polygon_z(
                [
                    map_point(-GP_BRA_REAR_LENGTH_M, -GP_BRA_REAR_HALF_WIDTH_M, ground_elevation),
                    map_point(0.0, -GP_BRA_REAR_HALF_WIDTH_M, ground_elevation),
                    map_point(0.0, GP_BRA_REAR_HALF_WIDTH_M, ground_elevation),
                    map_point(-GP_BRA_REAR_LENGTH_M, GP_BRA_REAR_HALF_WIDTH_M, ground_elevation),
                ]
            ),
        },
        {
            "surface_name": "Longitudinal 0.5 degree plane",
            "surface_role": "provisional_longitudinal",
            "slope_degrees": GP_BRA_LONGITUDINAL_SLOPE_DEG,
            "geometry": _polygon_z(
                [
                    map_point(GP_BRA_HORIZONTAL_LENGTH_M, base_inner_q, ground_elevation),
                    map_point(
                        GP_BRA_FORWARD_EXTENT_M,
                        base_inner_q - divergence_width,
                        forward_z,
                    ),
                    map_point(
                        GP_BRA_FORWARD_EXTENT_M,
                        base_outer_q + divergence_width,
                        forward_z,
                    ),
                    map_point(GP_BRA_HORIZONTAL_LENGTH_M, base_outer_q, ground_elevation),
                ]
            ),
        },
        {
            "surface_name": "Outer lateral 2 degree plane",
            "surface_role": "provisional_lateral_outer",
            "slope_degrees": GP_BRA_LATERAL_SLOPE_DEG,
            "geometry": _polygon_z(
                [
                    map_point(0.0, base_outer_q, ground_elevation),
                    map_point(
                        GP_BRA_HORIZONTAL_LENGTH_M,
                        base_outer_q + divergence_width,
                        lateral_outer_z,
                    ),
                    map_point(
                        GP_BRA_FORWARD_EXTENT_M,
                        base_outer_q + divergence_width,
                        lateral_outer_z,
                    ),
                    map_point(GP_BRA_HORIZONTAL_LENGTH_M, base_outer_q, ground_elevation),
                ]
            ),
        },
        {
            "surface_name": "Runway-side lateral 2 degree plane",
            "surface_role": "provisional_lateral_runway_side",
            "slope_degrees": GP_BRA_LATERAL_SLOPE_DEG,
            "geometry": _polygon_z(
                [
                    map_point(0.0, base_inner_q, ground_elevation),
                    map_point(
                        GP_BRA_HORIZONTAL_LENGTH_M,
                        base_inner_q - divergence_width,
                        lateral_outer_z,
                    ),
                    map_point(
                        GP_BRA_FORWARD_EXTENT_M,
                        base_inner_q - divergence_width,
                        lateral_outer_z,
                    ),
                    map_point(GP_BRA_HORIZONTAL_LENGTH_M, base_inner_q, ground_elevation),
                ]
            ),
        },
    ]

    for definition in definitions:
        geometry = definition["geometry"]
        if geometry.isNull() or geometry.isEmpty():
            raise ValueError(f"{definition['surface_name']} geometry is empty")
        definition.update(
            {
                "provisional": True,
                "source_reference": installation.get("source_reference", ""),
                "horizontal_length_m": GP_BRA_HORIZONTAL_LENGTH_M,
                "forward_extent_m": GP_BRA_FORWARD_EXTENT_M,
                "antenna_offset_m": antenna_offset,
                "outer_margin_m": GP_BRA_OUTER_MARGIN_M,
                "rear_length_m": GP_BRA_REAR_LENGTH_M,
                "rear_half_width_m": GP_BRA_REAR_HALF_WIDTH_M,
                "plan_divergence": GP_BRA_PLAN_DIVERGENCE,
            }
        )
    return definitions


def construct_provisional_localiser_bra(
    installation: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """Construct the runway-centred worked-example localiser BRA.

    The localiser origin is derived beyond the reciprocal runway end. Local
    ``x`` runs from the antenna through the runway toward the served approach
    threshold and continues 500 m beyond it; ``q`` is lateral to the extended
    runway centreline.
    """
    origin = installation.get("point") or installation.get("front_face_point")
    if not isinstance(origin, QgsPointXY):
        raise ValueError("localiser antenna point is required")
    interior_unit = installation.get("runway_interior_unit")
    if not isinstance(interior_unit, (tuple, list)) or len(interior_unit) != 2:
        raise ValueError("runway interior unit vector is required")
    interior_e = float(interior_unit[0])
    interior_n = float(interior_unit[1])
    unit_length = math.hypot(interior_e, interior_n)
    if unit_length <= 1e-9:
        raise ValueError("runway interior unit vector is invalid")
    interior_e /= unit_length
    interior_n /= unit_length
    runway_length = float(installation.get("runway_length"))
    setback = float(installation.get("distance_beyond_runway_end"))
    if runway_length <= 0:
        raise ValueError("positive runway length is required")
    if setback < 0:
        raise ValueError("localiser setback must not be negative")
    category = str(installation.get("localiser_category", ""))
    category_half_width = LOC_BRA_CATEGORY_HALF_WIDTH_M.get(category)
    if category_half_width is None:
        raise ValueError("localiser category must be CAT I or CAT II/III")
    ground_elevation = float(installation.get("ground_elevation"))
    forward_extent = runway_length + setback + LOC_BRA_BEYOND_THRESHOLD_M

    # From the localiser beyond the reciprocal end, forward points back through
    # the runway toward and then beyond the served approach threshold.
    forward_e = -interior_e
    forward_n = -interior_n
    lateral_e = interior_n
    lateral_n = -interior_e
    longitudinal_slope = math.tan(math.radians(LOC_BRA_LONGITUDINAL_SLOPE_DEG))
    lateral_slope = math.tan(math.radians(LOC_BRA_LATERAL_SLOPE_DEG))

    def map_point(local_x: float, local_q: float, elevation: float) -> Tuple[float, float, float]:
        return (
            origin.x() + local_x * forward_e + local_q * lateral_e,
            origin.y() + local_x * forward_n + local_q * lateral_n,
            elevation,
        )

    def unique_stations(values: Sequence[float]) -> List[float]:
        return sorted(
            {
                max(0.0, min(forward_extent, float(value)))
                for value in values
            }
        )

    inner_hit_x = LOC_BRA_HORIZONTAL_LENGTH_M + LOC_BRA_PLAN_DIVERGENCE * (
        category_half_width - LOC_BRA_HALF_WIDTH_M
    )
    longitudinal_stations = unique_stations(
        [LOC_BRA_HORIZONTAL_LENGTH_M, inner_hit_x, forward_extent]
    )

    def longitudinal_q(local_x: float) -> float:
        return min(
            category_half_width,
            LOC_BRA_HALF_WIDTH_M
            + max(0.0, local_x - LOC_BRA_HORIZONTAL_LENGTH_M)
            / LOC_BRA_PLAN_DIVERGENCE,
        )

    def longitudinal_z(local_x: float) -> float:
        return ground_elevation + max(
            0.0, local_x - LOC_BRA_HORIZONTAL_LENGTH_M
        ) * longitudinal_slope

    longitudinal_lower = [
        map_point(x, -longitudinal_q(x), longitudinal_z(x))
        for x in longitudinal_stations
    ]
    longitudinal_upper = [
        map_point(x, longitudinal_q(x), longitudinal_z(x))
        for x in reversed(longitudinal_stations)
    ]

    outer_hit_x = category_half_width - LOC_BRA_HALF_WIDTH_M
    lateral_extent = min(inner_hit_x, forward_extent)
    lateral_stations = sorted(
        {
            max(0.0, min(lateral_extent, float(value)))
            for value in (
                0.0,
                LOC_BRA_HORIZONTAL_LENGTH_M,
                outer_hit_x,
                lateral_extent,
            )
        }
    )

    def lateral_outer_q(local_x: float) -> float:
        return min(category_half_width, LOC_BRA_HALF_WIDTH_M + local_x)

    def lateral_inner_q(local_x: float) -> float:
        if local_x <= LOC_BRA_HORIZONTAL_LENGTH_M:
            return LOC_BRA_HALF_WIDTH_M
        return longitudinal_q(local_x)

    def lateral_z(local_q: float) -> float:
        return ground_elevation + max(
            0.0, local_q - LOC_BRA_HALF_WIDTH_M
        ) * lateral_slope

    positive_outer = [
        map_point(x, lateral_outer_q(x), lateral_z(lateral_outer_q(x)))
        for x in lateral_stations
    ]
    positive_inner = [
        map_point(x, lateral_inner_q(x), lateral_z(lateral_inner_q(x)))
        for x in reversed(lateral_stations)
    ]
    negative_outer = [
        map_point(x, -lateral_outer_q(x), lateral_z(lateral_outer_q(x)))
        for x in lateral_stations
    ]
    negative_inner = [
        map_point(x, -lateral_inner_q(x), lateral_z(lateral_inner_q(x)))
        for x in reversed(lateral_stations)
    ]

    definitions = [
        {
            "surface_name": "Horizontal base",
            "surface_role": "provisional_localiser_horizontal_base",
            "slope_degrees": 0.0,
            "geometry": _polygon_z(
                [
                    map_point(0.0, -LOC_BRA_HALF_WIDTH_M, ground_elevation),
                    map_point(LOC_BRA_HORIZONTAL_LENGTH_M, -LOC_BRA_HALF_WIDTH_M, ground_elevation),
                    map_point(LOC_BRA_HORIZONTAL_LENGTH_M, LOC_BRA_HALF_WIDTH_M, ground_elevation),
                    map_point(0.0, LOC_BRA_HALF_WIDTH_M, ground_elevation),
                ]
            ),
        },
        {
            "surface_name": "Rear horizontal area",
            "surface_role": "provisional_localiser_rear_horizontal",
            "slope_degrees": 0.0,
            "geometry": _polygon_z(
                [
                    map_point(-LOC_BRA_REAR_LENGTH_M, -LOC_BRA_HALF_WIDTH_M, ground_elevation),
                    map_point(0.0, -LOC_BRA_HALF_WIDTH_M, ground_elevation),
                    map_point(0.0, LOC_BRA_HALF_WIDTH_M, ground_elevation),
                    map_point(-LOC_BRA_REAR_LENGTH_M, LOC_BRA_HALF_WIDTH_M, ground_elevation),
                ]
            ),
        },
        {
            "surface_name": "Longitudinal 0.5 degree plane",
            "surface_role": "provisional_localiser_longitudinal",
            "slope_degrees": LOC_BRA_LONGITUDINAL_SLOPE_DEG,
            "geometry": _polygon_z(longitudinal_lower + longitudinal_upper),
        },
        {
            "surface_name": "Right lateral 2 degree plane",
            "surface_role": "provisional_localiser_lateral_right",
            "slope_degrees": LOC_BRA_LATERAL_SLOPE_DEG,
            "geometry": _polygon_z(positive_outer + positive_inner),
        },
        {
            "surface_name": "Left lateral 2 degree plane",
            "surface_role": "provisional_localiser_lateral_left",
            "slope_degrees": LOC_BRA_LATERAL_SLOPE_DEG,
            "geometry": _polygon_z(negative_outer + negative_inner),
        },
    ]

    for definition in definitions:
        geometry = definition["geometry"]
        if geometry.isNull() or geometry.isEmpty():
            raise ValueError(f"{definition['surface_name']} geometry is empty")
        definition.update(
            {
                "provisional": True,
                "source_reference": installation.get("source_reference", ""),
                "horizontal_length_m": LOC_BRA_HORIZONTAL_LENGTH_M,
                "forward_extent_m": forward_extent,
                "antenna_offset_m": 0.0,
                "setback_m": setback,
                "category": category,
                "category_half_width_m": category_half_width,
                "rear_length_m": LOC_BRA_REAR_LENGTH_M,
                "rear_half_width_m": LOC_BRA_HALF_WIDTH_M,
                "plan_divergence": LOC_BRA_PLAN_DIVERGENCE,
            }
        )
    return definitions


__all__ = [
    "construct_provisional_glide_path_bra",
    "construct_provisional_localiser_bra",
    "GP_BRA_FORWARD_EXTENT_M",
    "GP_BRA_HORIZONTAL_LENGTH_M",
]
