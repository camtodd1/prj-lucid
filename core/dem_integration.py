"""Optional DEM download and elevation-polygon processing helpers."""

from math import ceil, isfinite, sqrt
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
from urllib.parse import urlencode

from qgis.PyQt.QtCore import QByteArray, QSaveFile, QTemporaryDir, QUrl  # type: ignore
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
    QgsLineSymbol,
    QgsPointXY,
    QgsProject,
    QgsRectangle,
    QgsRendererCategory,
    QgsRasterBandStats,
    QgsColorRampShader,
    QgsRasterLayer,
    QgsRasterShader,
    QgsVectorLayer,
    QgsSingleBandPseudoColorRenderer,
    QgsSingleSymbolRenderer,
)

from . import output_structure


OPEN_TOPOGRAPHY_ALGORITHM_ID = (
    "OTDEMDownloader:OpenTopography DEM Downloader"
)
CONTOUR_POLYGON_ALGORITHM_ID = "gdal:contour_polygon"
GA_WCS_TRANSFER_TIMEOUT_MS = 120_000
# ArcGIS advertises 4096 px, but large float GeoTIFF coverages fail well below
# that image limit. Keep each WCS response near 16 MB uncompressed.
GA_WCS_TILE_SIZE = 2000
# Temporarily disabled to permit oversized WCS requests during terrain testing.
GA_MAX_DOWNLOAD_PIXELS: Optional[int] = None

ELEVATION_TERRAIN_COLORS = (
    "#41644A",  # deep valley green
    "#78966A",  # sage green
    "#B7AD72",  # pale olive-sand
    "#B58A55",  # warm ochre
    "#7A5940",  # umber
    "#D5D0C4",  # exposed rock
)
ELEVATION_CONTOUR_COLOR = "#4E5147"
TERRAIN_ANALYSIS_NODATA = -9999.0
TERRAIN_ANALYSIS_MAX_CELLS = 750_000
HEADROOM_CLASSES = (
    (1, "Terrain penetration (< 0 m)", "#B2182B"),
    (2, "0–5 m", "#EF8A62"),
    (3, "5–15 m", "#FDB863"),
    (4, "15–30 m", "#A6D96A"),
    (5, "> 30 m", "#1A9850"),
)

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


def _build_ga_wcs_url(source: Dict[str, Any], bbox: Tuple[float, float, float, float]) -> str:
    xmin, ymin, xmax, ymax = bbox
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


def build_ga_wcs_urls(extent_layer: Any, source_key: str) -> Tuple[str, ...]:
    """Build service-safe tiled WCS requests covering one terrain extent."""
    source = ga_dem_source(source_key)
    xmin, ymin, xmax, ymax = ga_extent_bbox(extent_layer, source["crs"])
    width = max(1, int((xmax - xmin) / float(source["resx"])) + 1)
    height = max(1, int((ymax - ymin) / float(source["resy"])) + 1)
    pixels = width * height
    if GA_MAX_DOWNLOAD_PIXELS is not None and pixels > GA_MAX_DOWNLOAD_PIXELS:
        raise ValueError(
            f"{source['short_label']} would contain about {pixels:,} cells. "
            "Choose a smaller extent or the 30 m source."
        )
    column_tiles = ceil(width / GA_WCS_TILE_SIZE)
    row_tiles = ceil(height / GA_WCS_TILE_SIZE)
    urls = []
    for row in range(row_tiles):
        tile_ymin = ymin + row * GA_WCS_TILE_SIZE * float(source["resy"])
        tile_ymax = min(
            ymax,
            ymin + (row + 1) * GA_WCS_TILE_SIZE * float(source["resy"]),
        )
        for column in range(column_tiles):
            tile_xmin = xmin + column * GA_WCS_TILE_SIZE * float(source["resx"])
            tile_xmax = min(
                xmax,
                xmin + (column + 1) * GA_WCS_TILE_SIZE * float(source["resx"]),
            )
            urls.append(
                _build_ga_wcs_url(
                    source,
                    (tile_xmin, tile_ymin, tile_xmax, tile_ymax),
                )
            )
    return tuple(urls)


def build_ga_wcs_url(extent_layer: Any, source_key: str) -> str:
    """Build the first bounded WCS request; retained for API compatibility."""
    return build_ga_wcs_urls(extent_layer, source_key)[0]


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
    output = Path(str(output_path))
    output.parent.mkdir(parents=True, exist_ok=True)
    urls = build_ga_wcs_urls(extent_layer, source_key)
    temporary = QTemporaryDir()
    if not temporary.isValid():
        raise RuntimeError("Could not create temporary storage for GA DEM tiles.")
    tile_paths = []
    for index, url in enumerate(urls, start=1):
        tile_path = Path(temporary.path()) / f"tile_{index:03d}.tif"
        content = _download_ga_wcs(url)
        save_file = QSaveFile(str(tile_path))
        if not save_file.open(QSaveFile.OpenModeFlag.WriteOnly):
            raise RuntimeError(f"Could not create DEM tile: {tile_path}")
        if save_file.write(content) != len(content) or not save_file.commit():
            raise RuntimeError(f"Could not save downloaded DEM tile: {tile_path}")
        tile_paths.append(str(tile_path))

    if len(tile_paths) == 1:
        source_file = QSaveFile(str(output))
        if not source_file.open(QSaveFile.OpenModeFlag.WriteOnly):
            raise RuntimeError(f"Could not create DEM output: {output}")
        content = Path(tile_paths[0]).read_bytes()
        if source_file.write(content) != len(content) or not source_file.commit():
            raise RuntimeError(f"Could not save downloaded DEM: {output}")
    else:
        import processing  # type: ignore

        result = processing.run(
            "gdal:merge",
            {
                "INPUT": tile_paths,
                "PCT": False,
                "SEPARATE": False,
                "NODATA_INPUT": None,
                "NODATA_OUTPUT": None,
                "OPTIONS": "COMPRESS=DEFLATE|TILED=YES",
                "EXTRA": "",
                "DATA_TYPE": 0,
                "OUTPUT": str(output),
            },
        )
        merged = result.get("OUTPUT") if isinstance(result, dict) else None
        if not merged or not Path(str(merged)).is_file():
            raise RuntimeError("QGIS could not merge the downloaded GA DEM tiles.")
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
    """Apply a deterministic natural-terrain style to elevation-band polygons."""
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
        palette_position = ratio * (len(ELEVATION_TERRAIN_COLORS) - 1)
        lower_stop = min(int(palette_position), len(ELEVATION_TERRAIN_COLORS) - 1)
        upper_stop = min(lower_stop + 1, len(ELEVATION_TERRAIN_COLORS) - 1)
        blend = palette_position - lower_stop
        start = QColor(ELEVATION_TERRAIN_COLORS[lower_stop])
        end = QColor(ELEVATION_TERRAIN_COLORS[upper_stop])
        fill = QColor(
            round(start.red() + (end.red() - start.red()) * blend),
            round(start.green() + (end.green() - start.green()) * blend),
            round(start.blue() + (end.blue() - start.blue()) * blend),
        )
        fill.setAlphaF(0.58)
        outline = QColor(ELEVATION_CONTOUR_COLOR)
        outline.setAlphaF(0.9)
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


def _terrain_analysis_path(directory: Path, stem: str, suffix: str) -> Path:
    candidate = directory / f"{stem}{suffix}"
    sequence = 2
    while candidate.exists():
        candidate = directory / f"{stem}_{sequence}{suffix}"
        sequence += 1
    return candidate


def _terrain_analysis_extent(dem_layer, ols_engine) -> QgsRectangle:
    project_crs = QgsProject.instance().crs()
    dem_crs = dem_layer.crs()
    if not project_crs.isValid() or not dem_crs.isValid():
        raise ValueError("Terrain and project layers require valid coordinate reference systems.")

    candidate_extent = None
    for candidate in list(getattr(ols_engine, "candidates", []) or []):
        footprint = getattr(candidate, "footprint", None)
        if footprint is None or footprint.isEmpty():
            continue
        extent = footprint.boundingBox()
        if candidate_extent is None:
            candidate_extent = QgsRectangle(extent)
        else:
            candidate_extent.combineExtentWith(extent)
    if candidate_extent is None or candidate_extent.isEmpty():
        raise ValueError("The controlling OLS envelope has no usable extent.")

    if project_crs != dem_crs:
        transform = QgsCoordinateTransform(project_crs, dem_crs, QgsProject.instance())
        candidate_extent = transform.transformBoundingBox(candidate_extent)
    analysis_extent = candidate_extent.intersect(dem_layer.extent())
    if analysis_extent.isEmpty():
        raise ValueError("The DEM does not overlap the controlling OLS envelope.")
    return analysis_extent


def _write_analysis_raster(path, values, extent, crs, data_type, nodata) -> None:
    from osgeo import gdal  # type: ignore

    height, width = values.shape
    dataset = gdal.GetDriverByName("GTiff").Create(
        str(path),
        int(width),
        int(height),
        1,
        data_type,
        options=["COMPRESS=DEFLATE", "TILED=YES"],
    )
    if dataset is None:
        raise RuntimeError(f"Could not create terrain analysis raster: {path}")
    dataset.SetGeoTransform(
        (
            extent.xMinimum(),
            extent.width() / width,
            0.0,
            extent.yMaximum(),
            0.0,
            -(extent.height() / height),
        )
    )
    dataset.SetProjection(crs.toWkt())
    band = dataset.GetRasterBand(1)
    band.SetNoDataValue(nodata)
    band.WriteArray(values)
    band.FlushCache()
    dataset.FlushCache()
    dataset = None


def _write_zero_clearance_contours(clearance_path: Path, contour_path: Path, crs) -> None:
    from osgeo import gdal, ogr, osr  # type: ignore

    source = gdal.Open(str(clearance_path), gdal.GA_ReadOnly)
    if source is None:
        raise RuntimeError("Could not reopen the terrain clearance raster.")
    data_source = ogr.GetDriverByName("GPKG").CreateDataSource(str(contour_path))
    if data_source is None:
        raise RuntimeError("Could not create the terrain penetration boundary layer.")
    spatial_reference = osr.SpatialReference()
    spatial_reference.ImportFromWkt(crs.toWkt())
    spatial_reference.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    contour_layer = data_source.CreateLayer(
        "zero_clearance",
        spatial_reference,
        ogr.wkbLineString,
    )
    contour_layer.CreateField(ogr.FieldDefn("id", ogr.OFTInteger))
    contour_layer.CreateField(ogr.FieldDefn("clearance_m", ogr.OFTReal))
    result = gdal.ContourGenerateEx(
        source.GetRasterBand(1),
        contour_layer,
        options=[
            "FIXED_LEVELS=0",
            f"NODATA={TERRAIN_ANALYSIS_NODATA:g}",
            "ID_FIELD=0",
            "ELEV_FIELD=1",
        ],
    )
    data_source = None
    source = None
    if result != 0:
        raise RuntimeError("Could not derive the zero-clearance penetration boundary.")


def create_terrain_analysis_outputs(
    dem_layer: QgsRasterLayer,
    ols_engine,
    output_directory: str,
    airport_code: str = "",
    *,
    max_cells: int = TERRAIN_ANALYSIS_MAX_CELLS,
    progress_callback=None,
) -> Dict[str, Any]:
    """Compare DEM cells with the exact controlling OLS lower envelope."""
    from osgeo import gdal, osr  # type: ignore
    import numpy as np  # type: ignore

    if dem_layer is None or not dem_layer.isValid():
        raise ValueError("Select a valid DEM before running terrain analysis.")
    if ols_engine is None or not getattr(ols_engine, "candidates", None):
        raise ValueError("Generate a controlling OLS envelope before running terrain analysis.")
    max_cells = max(1, int(max_cells))
    analysis_extent = _terrain_analysis_extent(dem_layer, ols_engine)

    native_x = abs(float(dem_layer.rasterUnitsPerPixelX()))
    native_y = abs(float(dem_layer.rasterUnitsPerPixelY()))
    if native_x <= 0.0 or native_y <= 0.0:
        raise ValueError("The DEM pixel size is invalid.")
    native_columns = max(1, ceil(analysis_extent.width() / native_x))
    native_rows = max(1, ceil(analysis_extent.height() / native_y))
    scale = max(1.0, sqrt((native_columns * native_rows) / max_cells))
    width = max(1, ceil(analysis_extent.width() / (native_x * scale)))
    height = max(1, ceil(analysis_extent.height() / (native_y * scale)))

    provider = dem_layer.dataProvider()
    block = provider.block(1, analysis_extent, width, height)
    if block is None or not block.isValid():
        raise RuntimeError("Could not read DEM values for the OLS analysis extent.")

    clearance = np.full((height, width), TERRAIN_ANALYSIS_NODATA, dtype=np.float32)
    headroom = np.zeros((height, width), dtype=np.uint8)
    cell_width = analysis_extent.width() / width
    cell_height = analysis_extent.height() / height

    dem_crs = dem_layer.crs()
    project_crs = QgsProject.instance().crs()
    coordinate_transform = None
    if dem_crs != project_crs:
        source_reference = osr.SpatialReference()
        source_reference.ImportFromWkt(dem_crs.toWkt())
        source_reference.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
        target_reference = osr.SpatialReference()
        target_reference.ImportFromWkt(project_crs.toWkt())
        target_reference.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
        coordinate_transform = osr.CoordinateTransformation(
            source_reference,
            target_reference,
        )

    x_coordinates = [
        analysis_extent.xMinimum() + ((column + 0.5) * cell_width)
        for column in range(width)
    ]
    for row in range(height):
        y_coordinate = analysis_extent.yMaximum() - ((row + 0.5) * cell_height)
        if coordinate_transform is None:
            project_points = [(x_coordinate, y_coordinate) for x_coordinate in x_coordinates]
        else:
            project_points = coordinate_transform.TransformPoints(
                [(x_coordinate, y_coordinate) for x_coordinate in x_coordinates]
            )
        for column, point in enumerate(project_points):
            if block.isNoData(row, column):
                continue
            try:
                ground_elevation = float(block.value(row, column))
            except (TypeError, ValueError):
                continue
            if not isfinite(ground_elevation):
                continue
            result = ols_engine.controlling_candidate_at_xy(
                QgsPointXY(float(point[0]), float(point[1]))
            )
            if result is None:
                continue
            _candidate, ols_elevation = result
            if ols_elevation is None or not isfinite(float(ols_elevation)):
                continue
            value = float(ols_elevation) - ground_elevation
            clearance[row, column] = value
            if value < 0.0:
                headroom[row, column] = 1
            elif value < 5.0:
                headroom[row, column] = 2
            elif value < 15.0:
                headroom[row, column] = 3
            elif value < 30.0:
                headroom[row, column] = 4
            else:
                headroom[row, column] = 5
        if callable(progress_callback):
            progress_callback(row + 1, height)

    directory = Path(output_directory)
    directory.mkdir(parents=True, exist_ok=True)
    safe_airport = "".join(
        character.lower() if character.isalnum() else "_"
        for character in str(airport_code or "airport")
    ).strip("_") or "airport"
    clearance_path = _terrain_analysis_path(
        directory,
        f"{safe_airport}_terrain_ols_clearance",
        ".tif",
    )
    headroom_path = _terrain_analysis_path(
        directory,
        f"{safe_airport}_obstacle_headroom",
        ".tif",
    )
    contour_path = _terrain_analysis_path(
        directory,
        f"{safe_airport}_terrain_penetration_boundary",
        ".gpkg",
    )
    _write_analysis_raster(
        clearance_path,
        clearance,
        analysis_extent,
        dem_crs,
        gdal.GDT_Float32,
        TERRAIN_ANALYSIS_NODATA,
    )
    _write_analysis_raster(
        headroom_path,
        headroom,
        analysis_extent,
        dem_crs,
        gdal.GDT_Byte,
        0,
    )
    _write_zero_clearance_contours(clearance_path, contour_path, dem_crs)
    valid_cells = int(np.count_nonzero(clearance != TERRAIN_ANALYSIS_NODATA))
    penetration_cells = int(
        np.count_nonzero(
            (clearance < 0.0) & (clearance != TERRAIN_ANALYSIS_NODATA)
        )
    )
    return {
        "clearance": str(clearance_path),
        "headroom": str(headroom_path),
        "penetration_boundary": str(contour_path),
        "width": width,
        "height": height,
        "cell_width": cell_width,
        "cell_height": cell_height,
        "valid_cells": valid_cells,
        "penetration_cells": penetration_cells,
    }


def _apply_raster_color_items(layer, items, ramp_type) -> bool:
    if layer is None or not layer.isValid():
        return False
    color_shader = QgsColorRampShader()
    color_shader.setColorRampType(ramp_type)
    color_shader.setColorRampItemList(
        [
            QgsColorRampShader.ColorRampItem(value, QColor(color), label)
            for value, color, label in items
        ]
    )
    raster_shader = QgsRasterShader()
    raster_shader.setRasterShaderFunction(color_shader)
    layer.setRenderer(
        QgsSingleBandPseudoColorRenderer(layer.dataProvider(), 1, raster_shader)
    )
    layer.triggerRepaint()
    return True


def apply_terrain_clearance_style(layer: QgsRasterLayer) -> bool:
    """Style signed clearance: penetration red, low clearance amber, then green."""
    return _apply_raster_color_items(
        layer,
        [
            (-30.0, "#67001F", "≤ −30 m"),
            (-10.0, "#B2182B", "−10 m"),
            (0.0, "#D6604D", "0 m — OLS boundary"),
            (5.0, "#F4A582", "5 m"),
            (15.0, "#FDD97E", "15 m"),
            (30.0, "#A6D96A", "30 m"),
            (100.0, "#1A9850", "≥ 100 m"),
        ],
        QgsColorRampShader.Type.Linear,
    )


def apply_headroom_style(layer: QgsRasterLayer) -> bool:
    """Style the five discrete obstacle-headroom classes."""
    return _apply_raster_color_items(
        layer,
        [(value, color, label) for value, label, color in HEADROOM_CLASSES],
        QgsColorRampShader.Type.Exact,
    )


def apply_penetration_boundary_style(layer: QgsVectorLayer) -> bool:
    """Style the zero-clearance terrain/OLS intersection line."""
    if layer is None or not layer.isValid():
        return False
    symbol = QgsLineSymbol.createSimple(
        {
            "color": "#8B0000",
            "width": "0.7",
            "width_unit": "MM",
        }
    )
    layer.setRenderer(QgsSingleSymbolRenderer(symbol))
    layer.triggerRepaint()
    return True


__all__ = [
    "CONTOUR_POLYGON_ALGORITHM_ID",
    "GA_DEM_SOURCES",
    "GA_MAX_DOWNLOAD_PIXELS",
    "HEADROOM_CLASSES",
    "OPEN_TOPOGRAPHY_ALGORITHM_ID",
    "TERRAIN_ANALYSIS_MAX_CELLS",
    "apply_elevation_polygon_style",
    "apply_headroom_style",
    "apply_penetration_boundary_style",
    "apply_terrain_clearance_style",
    "build_ga_wcs_url",
    "build_ga_wcs_urls",
    "contour_polygon_algorithm",
    "create_elevation_polygons",
    "create_terrain_analysis_outputs",
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
