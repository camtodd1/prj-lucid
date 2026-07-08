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
    "annex14_ofs",
    "annex14_oes",
)
CONTOUR_INTERVAL_LABELS = {
    "approach": "Approach",
    "tocs": "Take-off climb / departure",
    "transitional": "Transitional",
    "conical": "Conical",
    "inner_approach": "Inner approach",
    "inner_transitional": "Inner transitional",
    "baulked_landing": "Balked / baulked landing",
    "annex14_ofs": "Annex 14 obstacle free surfaces",
    "annex14_oes": "Annex 14 obstacle evaluation surfaces",
}
