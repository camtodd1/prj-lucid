# -*- coding: utf-8 -*-
"""Small Overpass client for downloading OSM aeroway features."""

from urllib.parse import urlencode
from xml.etree import ElementTree

from qgis.PyQt.QtCore import QByteArray, QUrl  # type: ignore
from qgis.PyQt.QtNetwork import QNetworkRequest  # type: ignore
from qgis.core import (  # type: ignore
    QgsBlockingNetworkRequest,
    QgsFillSymbol,
    QgsLineSymbol,
    QgsMarkerSymbol,
    QgsSingleSymbolRenderer,
    QgsVectorLayer,
    QgsWkbTypes,
)


OVERPASS_ENDPOINT = "https://overpass-api.de/api/interpreter"
AEROWAY_RADIUS_M = 10_000
OSM_SUBLAYERS = (
    ("points", "points"),
    ("lines", "lines"),
    ("multilinestrings", "multilinestrings"),
    ("multipolygons", "multipolygons"),
)

AEROWAY_STYLES = {
    "aerodrome": {"color": "#2563EB", "shape": "circle", "size": "4.0"},
    "apron": {"color": "#8FA3B5", "outline": "#526678"},
    "beacon": {"color": "#DB2777", "shape": "star", "size": "4.0"},
    "gate": {"color": "#2563EB", "shape": "square", "size": "3.4"},
    "hangar": {"color": "#64748B", "outline": "#334155"},
    "helipad": {"color": "#DC2626", "shape": "cross2", "size": "4.0"},
    "holding_position": {
        "color": "#D1495B",
        "shape": "triangle",
        "size": "4.0",
    },
    "navigationaid": {
        "color": "#7C3AED",
        "shape": "diamond",
        "size": "3.8",
    },
    "parking_position": {
        "color": "#1496A5",
        "shape": "circle",
        "size": "3.4",
    },
    "runway": {"color": "#4B5563", "outline": "#F8FAFC", "width": "2.4"},
    "taxilane": {
        "color": "#EAB308",
        "outline": "#A16207",
        "width": "1.2",
        "line_style": "dash",
    },
    "taxiway": {"color": "#D99A14", "outline": "#8A5E00", "width": "1.7"},
    "terminal": {"color": "#475569", "outline": "#1E293B"},
    "windsock": {"color": "#F97316", "shape": "triangle", "size": "4.0"},
}
DEFAULT_AEROWAY_STYLE = {
    "color": "#2D7F78",
    "outline": "#18534F",
    "shape": "circle",
    "size": "3.2",
    "width": "1.2",
    "line_style": "solid",
}


def apply_aeroway_style(layer: QgsVectorLayer, category: str) -> None:
    """Apply a compact geometry-aware style for an OSM aeroway category."""
    style = dict(DEFAULT_AEROWAY_STYLE)
    style.update(AEROWAY_STYLES.get(category, {}))
    geometry_type = layer.geometryType()

    if geometry_type == QgsWkbTypes.PointGeometry:
        symbol = QgsMarkerSymbol.createSimple(
            {
                "name": style["shape"],
                "color": style["color"],
                "outline_color": "#FFFFFF",
                "outline_width": "0.4",
                "size": style["size"],
            }
        )
    elif geometry_type == QgsWkbTypes.LineGeometry:
        symbol = QgsLineSymbol.createSimple(
            {
                "color": style["color"],
                "width": style["width"],
                "line_style": style["line_style"],
            }
        )
    elif geometry_type == QgsWkbTypes.PolygonGeometry:
        symbol = QgsFillSymbol.createSimple(
            {
                "color": style["color"],
                "outline_color": style["outline"],
                "outline_width": "0.7",
            }
        )
        if symbol is not None:
            symbol.setOpacity(0.55)
    else:
        return

    if symbol is not None:
        layer.setRenderer(QgsSingleSymbolRenderer(symbol))
        layer.setCustomProperty("safeguarding_builder/osm_aeroway_style", category)


def build_aeroway_query(latitude: float, longitude: float) -> str:
    """Return an Overpass query for every aeroway-tagged element near an ARP."""
    latitude = float(latitude)
    longitude = float(longitude)
    if not -90.0 <= latitude <= 90.0:
        raise ValueError("Latitude must be between -90 and 90 degrees.")
    if not -180.0 <= longitude <= 180.0:
        raise ValueError("Longitude must be between -180 and 180 degrees.")

    around = f"around:{AEROWAY_RADIUS_M},{latitude:.7f},{longitude:.7f}"
    return (
        "[out:xml][timeout:60];\n"
        "(\n"
        f'  node["aeroway"]({around});\n'
        f'  way["aeroway"]({around});\n'
        f'  relation["aeroway"]({around});\n'
        ");\n"
        "(._;>;);\n"
        "out body;"
    )


def fetch_aeroway_osm(latitude: float, longitude: float) -> bytes:
    """Download an OSM XML response using QGIS network/proxy settings."""
    request = QNetworkRequest(QUrl(OVERPASS_ENDPOINT))
    if hasattr(request, "setTransferTimeout"):
        request.setTransferTimeout(70_000)
    known_headers = getattr(QNetworkRequest, "KnownHeaders", QNetworkRequest)
    request.setHeader(
        known_headers.ContentTypeHeader,
        "application/x-www-form-urlencoded",
    )
    request.setRawHeader(
        QByteArray(b"User-Agent"),
        QByteArray(b"SafeguardingBuilder-QGIS/0.1 (OSM aeroway import)"),
    )
    payload = QByteArray(
        urlencode({"data": build_aeroway_query(latitude, longitude)}).encode("utf-8")
    )

    network = QgsBlockingNetworkRequest()
    error = network.post(request, payload, forceRefresh=True)
    if error != QgsBlockingNetworkRequest.NoError:
        raise RuntimeError(network.errorMessage() or "Overpass request failed.")

    content = bytes(network.reply().content())
    if not content:
        raise RuntimeError("Overpass returned an empty response.")
    try:
        root = ElementTree.fromstring(content)
    except ElementTree.ParseError as exc:
        raise RuntimeError("Overpass returned an invalid OSM response.") from exc
    remark = root.find("remark")
    if root.tag != "osm" or remark is not None:
        detail = remark.text.strip() if remark is not None and remark.text else "unknown error"
        raise RuntimeError(f"Overpass could not complete the query: {detail}")
    return content
