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
DEFAULT_RUNWAY_SURFACE_CATEGORY = "Sealed"
DEFAULT_RUNWAY_SURFACE_MATERIAL = "Asphalt"

OUTPUT_FORMATS = {
    "GeoPackage": ("GPKG", "GeoPackage", ".gpkg"),
    "ESRI Shapefile": ("ESRI Shapefile", "ESRI Shapefile", ".shp"),
    "GeoJSON": ("GeoJSON", "GeoJSON", ".geojson"),
}
DEFAULT_OUTPUT_FORMAT = "ESRI Shapefile"

DEFAULT_CONTOUR_INTERVAL = 10.0
DEFAULT_PRIMARY_CONTOUR_INTERVAL = 50.0
CONTOUR_INTERVAL_KEYS = (
    "approach",
    "tocs",
    "transitional",
    "conical",
    "inner_approach",
    "inner_transitional",
    "baulked_landing",
)
CONTOUR_INTERVAL_LABELS = {
    "approach": "OLS Approach",
    "tocs": "OLS TOCS",
    "transitional": "OLS Transitional",
    "conical": "OLS Conical",
    "inner_approach": "OFZ Inner Approach",
    "inner_transitional": "OFZ Inner Transitional",
    "baulked_landing": "OFZ Baulked Landing",
}
