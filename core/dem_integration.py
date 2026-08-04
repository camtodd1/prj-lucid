"""Optional integration with the OpenTopography DEM Downloader plugin."""

from typing import Any, Optional

from qgis.core import QgsApplication  # type: ignore


OPEN_TOPOGRAPHY_ALGORITHM_ID = (
    "OTDEMDownloader:OpenTopography DEM Downloader"
)


def open_topography_algorithm() -> Optional[Any]:
    """Return the installed OpenTopography processing algorithm, if enabled."""
    try:
        return QgsApplication.processingRegistry().algorithmById(
            OPEN_TOPOGRAPHY_ALGORITHM_ID
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


__all__ = [
    "OPEN_TOPOGRAPHY_ALGORITHM_ID",
    "open_topography_algorithm",
    "open_topography_dialog",
]
