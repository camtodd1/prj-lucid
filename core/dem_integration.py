"""Optional DEM download and elevation-polygon processing helpers."""

from pathlib import Path
from typing import Any, Optional

from qgis.PyQt.QtGui import QColor  # type: ignore
from qgis.core import (  # type: ignore
    QgsApplication,
    QgsCategorizedSymbolRenderer,
    QgsFillSymbol,
    QgsRendererCategory,
    QgsVectorLayer,
)


OPEN_TOPOGRAPHY_ALGORITHM_ID = (
    "OTDEMDownloader:OpenTopography DEM Downloader"
)
CONTOUR_POLYGON_ALGORITHM_ID = "gdal:contour_polygon"


def open_topography_algorithm() -> Optional[Any]:
    """Return the installed OpenTopography processing algorithm, if enabled."""
    try:
        return QgsApplication.processingRegistry().algorithmById(
            OPEN_TOPOGRAPHY_ALGORITHM_ID
        )
    except Exception:
        return None


def contour_polygon_algorithm() -> Optional[Any]:
    """Return QGIS's GDAL contour-polygon algorithm, if available."""
    try:
        return QgsApplication.processingRegistry().algorithmById(
            CONTOUR_POLYGON_ALGORITHM_ID
        )
    except Exception:
        return None


def open_topography_dialog(extent_layer: Any) -> Any:
    """Open the downloader dialog with a project layer supplied as its extent."""
    if extent_layer is None or not extent_layer.isValid():
        raise ValueError("Select a valid project layer to define the DEM extent.")
    if open_topography_algorithm() is None:
        raise RuntimeError(
            "OpenTopography DEM Downloader is not installed or enabled."
        )

    import processing  # type: ignore

    return processing.execAlgorithmDialog(
        OPEN_TOPOGRAPHY_ALGORITHM_ID,
        {"Extent": extent_layer},
    )


def elevation_polygon_output_path(
    dem_source: str,
    output_directory: Optional[str] = None,
) -> str:
    """Return a new GeoPackage path without overwriting an existing result."""
    dem_path = Path(str(dem_source or ""))
    directory = (
        Path(output_directory)
        if str(output_directory or "").strip()
        else dem_path.parent
    )
    if not directory.is_dir():
        raise ValueError("Select a valid directory for saved elevation polygons.")

    stem = dem_path.stem or "DEM"
    candidate = directory / f"{stem}_elevation_bands.gpkg"
    suffix = 2
    while candidate.exists():
        candidate = directory / f"{stem}_elevation_bands_{suffix}.gpkg"
        suffix += 1
    return str(candidate)


def create_elevation_polygons(
    dem_source: Any,
    interval: float,
    output: str = "TEMPORARY_OUTPUT",
) -> Any:
    """Create polygon elevation bands from a DEM with QGIS Processing."""
    interval_value = float(interval)
    if interval_value <= 0:
        raise ValueError("Elevation interval must be greater than zero.")
    if contour_polygon_algorithm() is None:
        raise RuntimeError("QGIS GDAL Contour Polygons is unavailable.")

    import processing  # type: ignore

    results = processing.run(
        CONTOUR_POLYGON_ALGORITHM_ID,
        {
            "INPUT": dem_source,
            "BAND": 1,
            "INTERVAL": interval_value,
            "OFFSET": 0.0,
            "FIELD_NAME_MIN": "ELEV_MIN",
            "FIELD_NAME_MAX": "ELEV_MAX",
            "CREATE_3D": False,
            "IGNORE_NODATA": False,
            "NODATA": None,
            "EXTRA": "",
            "OUTPUT": output,
        },
    )
    result = results.get("OUTPUT") if isinstance(results, dict) else None
    if result is None:
        raise RuntimeError("Contour polygon processing returned no output.")
    return result


def apply_elevation_polygon_style(layer: QgsVectorLayer) -> bool:
    """Apply a deterministic blue-to-red style to elevation-band polygons."""
    if layer is None or not layer.isValid():
        return False
    field_names = {field.name() for field in layer.fields()}
    if "ELEV_MIN" not in field_names or "ELEV_MAX" not in field_names:
        return False

    bands = {}
    for feature in layer.getFeatures():
        try:
            lower = float(feature["ELEV_MIN"])
            upper = float(feature["ELEV_MAX"])
        except (TypeError, ValueError):
            continue
        bands[lower] = max(upper, bands.get(lower, upper))
    if not bands:
        return False

    categories = []
    ordered = sorted(bands.items())
    denominator = max(1, len(ordered) - 1)
    for index, (lower, upper) in enumerate(ordered):
        ratio = index / denominator
        hue = (210.0 * (1.0 - ratio)) / 360.0
        fill = QColor.fromHsvF(hue, 0.58, 0.92, 0.58)
        outline = QColor.fromHsvF(hue, 0.72, 0.58, 0.9)
        symbol = QgsFillSymbol.createSimple(
            {
                "color": fill.name(QColor.NameFormat.HexArgb),
                "outline_color": outline.name(QColor.NameFormat.HexArgb),
                "outline_width": "0.2",
                "outline_width_unit": "MM",
            }
        )
        symbol.setColor(fill)
        categories.append(
            QgsRendererCategory(
                lower,
                symbol,
                f"{lower:g}–{upper:g} m",
            )
        )

    layer.setRenderer(QgsCategorizedSymbolRenderer("ELEV_MIN", categories))
    layer.triggerRepaint()
    return True


__all__ = [
    "CONTOUR_POLYGON_ALGORITHM_ID",
    "OPEN_TOPOGRAPHY_ALGORITHM_ID",
    "apply_elevation_polygon_style",
    "contour_polygon_algorithm",
    "create_elevation_polygons",
    "elevation_polygon_output_path",
    "open_topography_algorithm",
    "open_topography_dialog",
]
