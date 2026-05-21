"""Shared constants for the Safeguarding Builder dialog."""

CALC_PLACEHOLDER = "(Calculated)"
NA_PLACEHOLDER = "N/A"
ENTER_COORDS_MSG = "Enter Coords"
INVALID_COORDS_MSG = "Invalid Coords"
CALC_ERROR_MSG = "Calc Error"
SAME_POINT_MSG = "Same Point"
NEAR_POINTS_MSG = "Near Points"
WIDGET_MISSING_MSG = "Widget?"

DIALOG_LOG_TAG = "SafeguardingBuilderDialog"

RUNWAY_SURFACE_MATERIALS = {
    "Sealed": ["Asphalt", "Bitumen", "Concrete"],
    "Unsealed": ["Gravel", "Grass", "Sand", "Coral", "Clay", "Soil", "Salt"],
}

OUTPUT_FORMATS = {
    "GeoPackage": ("GPKG", "GeoPackage", ".gpkg"),
    "ESRI Shapefile": ("ESRI Shapefile", "ESRI Shapefile", ".shp"),
    "GeoJSON": ("GeoJSON", "GeoJSON", ".geojson"),
}
DEFAULT_OUTPUT_FORMAT = "ESRI Shapefile"
