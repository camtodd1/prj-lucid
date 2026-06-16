#!/usr/bin/env python3
"""Render a lightweight PNG overlay for controlling OLS regression checks."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Iterable, Iterator, List, Optional, Sequence, Tuple

from PIL import Image, ImageDraw

Point = Tuple[float, float]
Line = List[Point]


SURFACE_FILL = {
    "Approach": (75, 184, 198, 145),
    "TOCS": (246, 178, 100, 145),
    "Transitional": (100, 198, 145, 145),
    "Conical": (180, 125, 205, 145),
    "IHS": (238, 207, 102, 145),
    "OHS": (165, 181, 195, 145),
}
SURFACE_OUTLINE = {
    "Approach": (18, 108, 122, 220),
    "TOCS": (170, 104, 32, 220),
    "Transitional": (38, 130, 76, 220),
    "Conical": (105, 64, 128, 220),
    "IHS": (135, 111, 32, 220),
    "OHS": (84, 101, 118, 220),
}


def _load_geojson(path: Optional[str]) -> dict:
    if not path:
        return {"type": "FeatureCollection", "features": []}
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def _xy(raw: Sequence[float]) -> Point:
    return float(raw[0]), float(raw[1])


def _geometry_lines(geometry: dict) -> Iterator[Line]:
    geom_type = geometry.get("type")
    coords = geometry.get("coordinates") or []
    if geom_type == "LineString":
        yield [_xy(point) for point in coords]
    elif geom_type == "MultiLineString":
        for line in coords:
            yield [_xy(point) for point in line]
    elif geom_type == "Polygon":
        for ring in coords:
            yield [_xy(point) for point in ring]
    elif geom_type == "MultiPolygon":
        for polygon in coords:
            for ring in polygon:
                yield [_xy(point) for point in ring]
    elif geom_type == "GeometryCollection":
        for child in geometry.get("geometries") or []:
            yield from _geometry_lines(child)


def _geometry_polygons(geometry: dict) -> Iterator[List[Line]]:
    geom_type = geometry.get("type")
    coords = geometry.get("coordinates") or []
    if geom_type == "Polygon":
        yield [[_xy(point) for point in ring] for ring in coords]
    elif geom_type == "MultiPolygon":
        for polygon in coords:
            yield [[_xy(point) for point in ring] for ring in polygon]
    elif geom_type == "GeometryCollection":
        for child in geometry.get("geometries") or []:
            yield from _geometry_polygons(child)


def _all_points(feature_collections: Iterable[dict]) -> Iterator[Point]:
    for collection in feature_collections:
        for feature in collection.get("features") or []:
            geometry = feature.get("geometry")
            if not geometry:
                continue
            for line in _geometry_lines(geometry):
                yield from line


def _bounds(points: Iterable[Point]) -> Tuple[float, float, float, float]:
    xs: List[float] = []
    ys: List[float] = []
    for x, y in points:
        if math.isfinite(x) and math.isfinite(y):
            xs.append(x)
            ys.append(y)
    if not xs or not ys:
        raise ValueError("No finite geometry coordinates found.")
    return min(xs), min(ys), max(xs), max(ys)


def _transformer(bounds: Tuple[float, float, float, float], width: int, height: int, pad: int):
    min_x, min_y, max_x, max_y = bounds
    span_x = max(max_x - min_x, 1.0)
    span_y = max(max_y - min_y, 1.0)
    scale = min((width - (2 * pad)) / span_x, (height - (2 * pad)) / span_y)
    offset_x = (width - (span_x * scale)) / 2.0
    offset_y = (height - (span_y * scale)) / 2.0

    def _to_pixel(point: Point) -> Tuple[int, int]:
        x, y = point
        px = offset_x + ((x - min_x) * scale)
        py = height - (offset_y + ((y - min_y) * scale))
        return int(round(px)), int(round(py))

    return _to_pixel


def _draw_dashed_line(
    draw: ImageDraw.ImageDraw,
    points: Sequence[Tuple[int, int]],
    fill: Tuple[int, int, int, int],
    width: int,
    dash: int = 14,
    gap: int = 8,
) -> None:
    for start, end in zip(points[:-1], points[1:]):
        dx = end[0] - start[0]
        dy = end[1] - start[1]
        length = math.hypot(dx, dy)
        if length <= 0:
            continue
        ux = dx / length
        uy = dy / length
        cursor = 0.0
        while cursor < length:
            stop = min(length, cursor + dash)
            p1 = (int(round(start[0] + (ux * cursor))), int(round(start[1] + (uy * cursor))))
            p2 = (int(round(start[0] + (ux * stop))), int(round(start[1] + (uy * stop))))
            draw.line([p1, p2], fill=fill, width=width)
            cursor = stop + gap


def _draw_regions(draw: ImageDraw.ImageDraw, regions: dict, to_pixel) -> None:
    for feature in regions.get("features") or []:
        geometry = feature.get("geometry")
        if not geometry:
            continue
        surface = (feature.get("properties") or {}).get("surface", "")
        fill = SURFACE_FILL.get(surface, (180, 180, 180, 120))
        outline = SURFACE_OUTLINE.get(surface, (80, 80, 80, 220))
        for polygon in _geometry_polygons(geometry):
            if not polygon:
                continue
            exterior = [to_pixel(point) for point in polygon[0]]
            if len(exterior) >= 3:
                draw.polygon(exterior, fill=fill)
                draw.line(exterior, fill=outline, width=2, joint="curve")
            for hole in polygon[1:]:
                hole_pixels = [to_pixel(point) for point in hole]
                if len(hole_pixels) >= 3:
                    draw.polygon(hole_pixels, fill=(255, 255, 255, 255))
                    draw.line(hole_pixels, fill=outline, width=2)


def _draw_lines(
    draw: ImageDraw.ImageDraw,
    collection: dict,
    to_pixel,
    fill: Tuple[int, int, int, int],
    width: int,
    dashed: bool = False,
) -> None:
    for feature in collection.get("features") or []:
        geometry = feature.get("geometry")
        if not geometry:
            continue
        for line in _geometry_lines(geometry):
            pixels = [to_pixel(point) for point in line]
            if len(pixels) < 2:
                continue
            if dashed:
                _draw_dashed_line(draw, pixels, fill=fill, width=width)
            else:
                draw.line(pixels, fill=fill, width=width, joint="curve")


def render(args: argparse.Namespace) -> None:
    regions = _load_geojson(args.regions)
    known = _load_geojson(args.known_edges)
    missing = _load_geojson(args.missing_edges)
    extra = _load_geojson(args.extra_edges)
    collections = [regions, known, missing, extra]
    if args.bounds:
        values = [float(value) for value in args.bounds.split(",")]
        if len(values) != 4:
            raise ValueError("--bounds must be minx,miny,maxx,maxy")
        bounds = (values[0], values[1], values[2], values[3])
    else:
        bounds = _bounds(_all_points(collections))
    to_pixel = _transformer(bounds, args.width, args.height, args.padding)

    image = Image.new("RGBA", (args.width, args.height), (255, 255, 255, 255))
    draw = ImageDraw.Draw(image, "RGBA")
    _draw_regions(draw, regions, to_pixel)
    _draw_lines(draw, known, to_pixel, (0, 0, 0, 230), 3, dashed=True)
    _draw_lines(draw, extra, to_pixel, (255, 125, 0, 230), 4)
    _draw_lines(draw, missing, to_pixel, (225, 20, 45, 245), 6)
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    image.convert("RGB").save(args.output, "PNG")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--regions", required=True, help="Generated controlling region GeoJSON.")
    parser.add_argument("--known-edges", help="Optional known-good edge GeoJSON.")
    parser.add_argument("--missing-edges", help="Known-good segments not matched by generated output.")
    parser.add_argument("--extra-edges", help="Generated segments not matched by known-good output.")
    parser.add_argument("--output", required=True, help="Output PNG path.")
    parser.add_argument("--width", type=int, default=1800)
    parser.add_argument("--height", type=int, default=1600)
    parser.add_argument("--padding", type=int, default=60)
    parser.add_argument("--bounds", help="Optional map bounds as minx,miny,maxx,maxy.")
    render(parser.parse_args())


if __name__ == "__main__":
    main()
