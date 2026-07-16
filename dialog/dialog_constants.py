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
ANNEX14_FAMILY_CONTOUR_KEYS = (
    "annex14_ofs",
    "annex14_oes",
)
ANNEX14_OES_SURFACE_CONTOUR_KEYS = (
    "annex14_oes_precision_approach",
    "annex14_oes_take_off_climb",
    "annex14_oes_instrument_departure",
)
ANNEX14_OFS_SURFACE_CONTOUR_KEYS = (
    "annex14_ofs_approach",
    "annex14_ofs_transitional",
    "annex14_ofs_balked_landing",
    "annex14_ofs_inner_approach",
    "annex14_ofs_inner_transitional",
)
ANNEX14_SURFACE_CONTOUR_KEYS = (
    ANNEX14_OES_SURFACE_CONTOUR_KEYS + ANNEX14_OFS_SURFACE_CONTOUR_KEYS
)
CONVENTIONAL_CONTOUR_SECTIONS = (
    (
        "Obstacle Free Zone",
        ("inner_approach", "inner_transitional", "baulked_landing"),
    ),
    (
        "Primary Surfaces",
        ("approach", "tocs", "transitional"),
    ),
    ("Secondary", ("conical",)),
)
CONVENTIONAL_SURFACE_CONTOUR_KEYS = tuple(
    key
    for _section, section_keys in CONVENTIONAL_CONTOUR_SECTIONS
    for key in section_keys
)
SURFACE_CONTOUR_KEYS = (
    CONVENTIONAL_SURFACE_CONTOUR_KEYS
    + ANNEX14_FAMILY_CONTOUR_KEYS
    + ANNEX14_SURFACE_CONTOUR_KEYS
)
COMPARISON_SURFACE_CONTOUR_KEYS = tuple(
    f"comparison_{key}" for key in SURFACE_CONTOUR_KEYS
)
MODERNISATION_CHANGE_CONTOUR_KEYS = (
    "modernisation_ofs_change",
    "modernisation_oes_change",
)
COMPARISON_CHANGE_CONTOUR_KEYS = (
    "comparison_change",
    *MODERNISATION_CHANGE_CONTOUR_KEYS,
)
CONTOUR_INTERVAL_KEY_DEFAULTS = {
    "comparison_change": {"primary": 5.0, "intermediate": 1.0},
    "modernisation_ofs_change": {"primary": 5.0, "intermediate": 1.0},
    "modernisation_oes_change": {"primary": 5.0, "intermediate": 1.0},
}
CONTOUR_INTERVAL_KEYS = (
    SURFACE_CONTOUR_KEYS
    + COMPARISON_SURFACE_CONTOUR_KEYS
    + COMPARISON_CHANGE_CONTOUR_KEYS
)
CONTOUR_INTERVAL_LABELS = {
    "approach": "Approach",
    "tocs": "Take-off climb",
    "transitional": "Transitional",
    "conical": "Conical",
    "inner_approach": "Inner approach",
    "inner_transitional": "Inner transitional",
    "baulked_landing": "Balked landing",
    "annex14_ofs": "Annex 14 obstacle free surfaces",
    "annex14_oes": "Annex 14 obstacle evaluation surfaces",
    "annex14_oes_precision_approach": "Precision Approach",
    "annex14_oes_take_off_climb": "Take-off Climb",
    "annex14_oes_instrument_departure": "Instrument Departure",
    "annex14_ofs_approach": "Approach",
    "annex14_ofs_transitional": "Transitional",
    "annex14_ofs_balked_landing": "Balked Landing",
    "annex14_ofs_inner_approach": "Inner Approach",
    "annex14_ofs_inner_transitional": "Inner Transitional",
    "comparison_change": "OLS change contours",
    "modernisation_ofs_change": "OFS change contours",
    "modernisation_oes_change": "OES change contours",
}
CONTOUR_INTERVAL_LABELS.update(
    {
        f"comparison_{key}": CONTOUR_INTERVAL_LABELS[key]
        for key in SURFACE_CONTOUR_KEYS
    }
)
