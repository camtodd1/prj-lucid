"""Provisional NASF glide-path Building Restricted Area construction."""

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


__all__ = [
    "construct_provisional_glide_path_bra",
    "GP_BRA_FORWARD_EXTENT_M",
    "GP_BRA_HORIZONTAL_LENGTH_M",
]
