"""Optional DEM download and elevation-polygon processing helpers."""

from pathlib import Path
from typing import Any, Dict, Optional, Tuple
from urllib.parse import urlencode

from qgis.PyQt.QtCore import QByteArray, QSaveFile, QUrl  # type: ignore
from qgis.PyQt.QtGui import QColor  # type: ignore
from qgis.PyQt.QtNetwork import QNetworkRequest  # type: ignore
from qgis.core import (  # type: ignore
    QgsApplication,
    QgsBlockingNetworkRequest,
    QgsCategorizedSymbolRenderer,
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsFeature,
    QgsFillSymbol,
    QgsGeometry,
    QgsLayerTreeGroup,
    QgsProject,
    QgsRectangle,
    QgsRendererCategory,
    QgsRasterBandStats,
    QgsRasterLayer,
    QgsVectorLayer,
)

from . import output_structure


OPEN_TOPOGRAPHY_ALGORITHM_ID = (
    "OTDEMDownloader:OpenTopography DEM Downloader"
)
CONTOUR_POLYGON_ALGORITHM_ID = "gdal:contour_polygon"
GA_WCS_TRANSFER_TIMEOUT_MS = 120_000
GA_MAX_DOWNLOAD_PIXELS = 25_000_000

GA_DEM_SOURCES: Dict[str, Dict[str, Any]] = {
    "ga_lidar_5m": {
        "label": "GA LiDAR bare-earth DEM 5 m",
        "short_label": "GA LiDAR 5 m",
        "service_url": (
            "https://services.ga.gov.au/gis/services/"
            "DEM_LiDAR_5m_2025/MapServer/WCSServer"
        ),
        "coverage": "1",
        "crs": "EPSG:4283",
        "resx": 5.5063478185957097e-05,
        "resy": 5.1601232527787033e-05,
        "resolution_m": 5,
        "vertical_datum": "Australian source survey datum; verify AHD metadata",
        "vertical_epsg": "",
        "dataset_url": "https://doi.org/10.26186/89644",
    },
    "ga_srtm_30m": {
        "label": "GA SRTM bare-earth DEM 30 m",
        "short_label": "GA SRTM 30 m",
        "service_url": (
            "https://services.ga.gov.au/gis/services/"
            "DEM_SRTM_1Second_2024/MapServer/WCSServer"
        ),
        "coverage": "1",
        "crs": "EPSG:4326",
        "resx": 1.0 / 3600.0,
        "resy": 1.0 / 3600.0,
        "resolution_m": 30,
        "vertical_datum": "EGM96 orthometric height",
        "vertical_epsg": "EPSG:5773",
        "dataset_url": "https://pid.geoscience.gov.au/dataset/ga/72759",
    },
}


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


def ga_dem_source(source_key: str) -> Dict[str, Any]:
    """Return a copy of one supported Geoscience Australia DEM definition."""
    try:
        return dict(GA_DEM_SOURCES[str(source_key)])
    except KeyError as exc:
        raise ValueError("Select a supported Geoscience Australia DEM source.") from exc


def ga_extent_bbox(extent_layer: Any, target_crs: str) -> Tuple[float, float, float, float]:
    """Transform a vector layer extent into the WCS request CRS."""
    if extent_layer is None or not extent_layer.isValid():
        raise ValueError("Select a valid project layer to define the DEM extent.")
    extent = extent_layer.extent()
    if extent.isEmpty():
        raise ValueError("The selected extent layer has no usable extent.")
    destination = QgsCoordinateReferenceSystem(target_crs)
    if not destination.isValid():
        raise RuntimeError(f"DEM service CRS is invalid: {target_crs}")
    if extent_layer.crs() != destination:
        transform = QgsCoordinateTransform(
            extent_layer.crs(),
            destination,
            QgsProject.instance(),
        )
        extent = transform.transformBoundingBox(extent)
    return (
        float(extent.xMinimum()),
        float(extent.yMinimum()),
        float(extent.xMaximum()),
        float(extent.yMaximum()),
    )


def ols_square_extent(
    airport_code: str = "",
) -> Tuple[QgsRectangle, QgsCoordinateReferenceSystem, int]:
    """Return the smallest axis-aligned square containing all generated OLS layers."""
    root = QgsProject.instance().layerTreeRoot()
    main_group = None
    code = str(airport_code or "").strip().upper()
    if code:
        main_group = root.findGroup(f"{code} Safeguarding Builder")
    if main_group is None:
        candidates = [
            child
            for child in root.children()
            if isinstance(child, QgsLayerTreeGroup)
            and child.name().endswith(" Safeguarding Builder")
        ]
        if len(candidates) == 1:
            main_group = candidates[0]
    if main_group is None:
        raise ValueError("Generate OLS layers before downloading terrain.")

    ols_group = main_group.findGroup(output_structure.PROTECTED_AIRSPACE)
    if ols_group is None:
        raise ValueError("The generated OLS layer group could not be found.")
    layers = [
        node.layer()
        for node in ols_group.findLayers()
        if node.layer() is not None
        and node.layer().isValid()
        and not node.layer().extent().isEmpty()
    ]
    if not layers:
        raise ValueError("The generated OLS group contains no layers with an extent.")

    project_crs = QgsProject.instance().crs()
    target_crs = project_crs if project_crs.isValid() and not project_crs.isGeographic() else None
    if target_crs is None:
        target_crs = next(
            (layer.crs() for layer in layers if layer.crs().isValid() and not layer.crs().isGeographic()),
            layers[0].crs(),
        )
    combined = None
    for layer in layers:
        extent = QgsRectangle(layer.extent())
        if layer.crs() != target_crs:
            transform = QgsCoordinateTransform(
                layer.crs(), target_crs, QgsProject.instance()
            )
            extent = transform.transformBoundingBox(extent)
        if combined is None:
            combined = QgsRectangle(extent)
        else:
            combined.combineExtentWith(extent)
    if combined is None or combined.isEmpty():
        raise ValueError("The generated OLS layers have no usable combined extent.")

    side = max(combined.width(), combined.height())
    if side <= 0:
        raise ValueError("The generated OLS extent has no area.")
    centre = combined.center()
    half_side = side / 2.0
    square = QgsRectangle(
        centre.x() - half_side,
        centre.y() - half_side,
        centre.x() + half_side,
        centre.y() + half_side,
    )
    return square, target_crs, len(layers)


def create_ols_square_extent_layer(airport_code: str = "") -> QgsVectorLayer:
    """Create an in-memory polygon representing the automatic OLS terrain extent."""
    square, crs, layer_count = ols_square_extent(airport_code)
    layer = QgsVectorLayer(
        f"Polygon?crs={crs.authid()}",
        "Automatic OLS Terrain Extent",
        "memory",
    )
    feature = QgsFeature(layer.fields())
    feature.setGeometry(QgsGeometry.fromRect(square))
    layer.dataProvider().addFeature(feature)
    layer.updateExtents()
    layer.setCustomProperty("safeguarding_builder/ols_extent_layer_count", layer_count)
    return layer


def build_ga_wcs_url(extent_layer: Any, source_key: str) -> str:
    """Build a bounded WCS 1.0 GeoTIFF request for a GA terrain source."""
    source = ga_dem_source(source_key)
    xmin, ymin, xmax, ymax = ga_extent_bbox(extent_layer, source["crs"])
    width = max(1, int((xmax - xmin) / float(source["resx"])) + 1)
    height = max(1, int((ymax - ymin) / float(source["resy"])) + 1)
    pixels = width * height
    if pixels > GA_MAX_DOWNLOAD_PIXELS:
        raise ValueError(
            f"{source['short_label']} would contain about {pixels:,} cells. "
            "Choose a smaller extent or the 30 m source."
        )
    parameters = (
        ("service", "WCS"),
        ("version", "1.0.0"),
        ("request", "GetCoverage"),
        ("coverage", source["coverage"]),
        ("format", "GeoTIFF"),
        ("crs", source["crs"]),
        ("response_crs", source["crs"]),
        ("bbox", f"{xmin:.12f},{ymin:.12f},{xmax:.12f},{ymax:.12f}"),
        ("resx", f"{float(source['resx']):.15g}"),
        ("resy", f"{float(source['resy']):.15g}"),
    )
    return f"{source['service_url']}?{urlencode(parameters)}"


def _download_ga_wcs(url: str) -> bytes:
    request = QNetworkRequest(QUrl(url))
    if hasattr(request, "setTransferTimeout"):
        request.setTransferTimeout(GA_WCS_TRANSFER_TIMEOUT_MS)
    request.setRawHeader(
        QByteArray(b"User-Agent"),
        QByteArray(b"SafeguardingBuilder-QGIS/0.1"),
    )
    network = QgsBlockingNetworkRequest()
    error = network.get(request, forceRefresh=True)
    if error != QgsBlockingNetworkRequest.NoError:
        raise RuntimeError(network.errorMessage() or "GA terrain request failed.")
    content = bytes(network.reply().content())
    if content[:4] not in (b"II*\x00", b"MM\x00*"):
        detail = content[:300].decode("utf-8", errors="ignore").strip()
        raise RuntimeError(
            "Geoscience Australia did not return a GeoTIFF."
            + (f" Response: {detail}" if detail else "")
        )
    return content


def download_ga_dem(extent_layer: Any, source_key: str, output_path: str) -> Dict[str, Any]:
    """Download a clipped GA elevation GeoTIFF and return its source metadata."""
    source = ga_dem_source(source_key)
    content = _download_ga_wcs(build_ga_wcs_url(extent_layer, source_key))
    output = Path(str(output_path))
    output.parent.mkdir(parents=True, exist_ok=True)
    save_file = QSaveFile(str(output))
    if not save_file.open(QSaveFile.OpenModeFlag.WriteOnly):
        raise RuntimeError(f"Could not create DEM output: {output}")
    if save_file.write(content) != len(content) or not save_file.commit():
        raise RuntimeError(f"Could not save downloaded DEM: {output}")
    source.update(
        {
            "dataset": source["label"],
            "source_key": source_key,
            "source_service": "Geoscience Australia WCS",
            "output": str(output),
        }
    )
    return source


def raster_has_terrain_values(path: str) -> bool:
    """Return whether a downloaded raster contains plausible terrain cells."""
    layer = QgsRasterLayer(str(path), "GA DEM coverage check")
    if not layer.isValid():
        return False
    provider = layer.dataProvider()
    stats = provider.bandStatistics(
        1,
        QgsRasterBandStats.Stats.Min | QgsRasterBandStats.Stats.Max,
        layer.extent(),
        10000,
    )
    return float(stats.maximumValue) > -15000.0 and float(stats.minimumValue) < 10000.0


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
    "GA_DEM_SOURCES",
    "GA_MAX_DOWNLOAD_PIXELS",
    "OPEN_TOPOGRAPHY_ALGORITHM_ID",
    "apply_elevation_polygon_style",
    "build_ga_wcs_url",
    "contour_polygon_algorithm",
    "create_elevation_polygons",
    "create_ols_square_extent_layer",
    "download_ga_dem",
    "elevation_polygon_output_path",
    "ga_dem_source",
    "ga_extent_bbox",
    "open_topography_algorithm",
    "open_topography_dialog",
    "ols_square_extent",
    "raster_has_terrain_values",
]
