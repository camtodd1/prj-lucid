# -*- coding: utf-8 -*-
"""Small Overpass client for downloading OSM aeroway features."""

from typing import Callable, Optional
from urllib.parse import urlencode
from xml.etree import ElementTree

from qgis.PyQt.QtCore import QByteArray, QUrl  # type: ignore
from qgis.PyQt.QtGui import QColor, QFont  # type: ignore
from qgis.PyQt.QtNetwork import QNetworkRequest  # type: ignore
from qgis.core import (  # type: ignore
    QgsBlockingNetworkRequest,
    QgsCategorizedSymbolRenderer,
    QgsFillSymbol,
    QgsLineSymbol,
    QgsMarkerSymbol,
    QgsPalLayerSettings,
    QgsRendererCategory,
    QgsSimpleLineSymbolLayer,
    QgsSingleSymbolRenderer,
    QgsTextBufferSettings,
    QgsTextFormat,
    QgsVectorLayer,
    QgsVectorLayerSimpleLabeling,
    QgsWkbTypes,
)


OVERPASS_ENDPOINTS = (
    "https://overpass-api.de/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
)
AEROWAY_RADIUS_M = 5_000
OSM_SUBLAYERS = (
    ("points", "points"),
    ("lines", "lines"),
    ("multilinestrings", "multilinestrings"),
    ("multipolygons", "multipolygons"),
)

AEROWAY_STYLES = {
    "aerodrome": {
        "fill": "#E8EDF2",
        "outline": "#788896",
        "opacity": "0.18",
    },
    "aerodrome_marking": {
        "line_color": "#F2C230",
        "width": "0.35",
        "fill": "#F2C230",
        "outline": "#A77900",
        "opacity": "0.90",
    },
    "apron": {
        "fill": "#C7CDD2",
        "outline": "#89939C",
        "opacity": "0.68",
    },
    "beacon": {
        "color": "#B83B78",
        "outline": "#FFFFFF",
        "shape": "star",
        "size": "2.6",
    },
    "extended-takeoff_area": {
        "line_color": "#747E87",
        "width": "1.8",
        "line_style": "dash",
        "fill": "#B7BEC4",
        "outline": "#747E87",
        "opacity": "0.50",
    },
    "gate": {
        "color": "#F8FBFD",
        "outline": "#2E6F9E",
        "shape": "square",
        "size": "2.0",
    },
    "hangar": {
        "fill": "#87929C",
        "outline": "#5E6871",
        "opacity": "0.86",
    },
    "helipad": {
        "color": "#C43D4D",
        "outline": "#FFFFFF",
        "shape": "cross2",
        "size": "2.8",
    },
    "holding_position": {
        "color": "#F2C230",
        "outline": "#2F343A",
        "shape": "square",
        "size": "2.2",
    },
    "jet_bridge": {
        "line_color": "#687886",
        "width": "0.65",
    },
    "navigationaid": {
        "color": "#7557B8",
        "outline": "#FFFFFF",
        "shape": "diamond",
        "size": "2.5",
    },
    "parking_position": {
        "color": "#E8EDF2",
        "outline": "#3D8791",
        "shape": "circle",
        "size": "1.8",
        "line_color": "#7D98A0",
        "width": "0.45",
    },
    "runway": {
        "line_color": "#454C54",
        "width": "3.4",
        "center_color": "#F7F7F3",
        "center_width": "0.28",
        "center_style": "dash",
        "fill": "#454C54",
        "outline": "#242A30",
        "opacity": "0.96",
    },
    "stopway": {
        "line_color": "#69727B",
        "width": "2.7",
        "line_style": "dash",
        "fill": "#AAB1B7",
        "outline": "#69727B",
        "opacity": "0.58",
    },
    "taxilane": {
        "line_color": "#9AA3AC",
        "width": "1.2",
        "center_color": "#F2C230",
        "center_width": "0.22",
        "center_style": "dash",
        "fill": "#A4ACB3",
        "outline": "#737C84",
        "opacity": "0.82",
    },
    "taxiway": {
        "line_color": "#7C858E",
        "width": "15.0",
        "center_color": "#F2C230",
        "center_width": "0.45",
        "center_style": "solid",
        "width_unit": "MapUnit",
        "capstyle": "round",
        "joinstyle": "round",
        "symbol_levels": True,
        "fill": "#858E97",
        "outline": "#626A71",
        "opacity": "0.90",
    },
    "terminal": {
        "fill": "#566575",
        "outline": "#35424D",
        "opacity": "0.92",
    },
    "windsock": {
        "color": "#E87516",
        "outline": "#FFFFFF",
        "shape": "triangle",
        "size": "2.6",
    },
}
DEFAULT_AEROWAY_STYLE = {
    "color": "#647985",
    "outline": "#40525C",
    "fill": "#AEB8BE",
    "line_color": "#647985",
    "shape": "circle",
    "size": "2.2",
    "width": "0.8",
    "width_unit": "MM",
    "line_style": "solid",
    "capstyle": "square",
    "joinstyle": "bevel",
    "symbol_levels": False,
    "opacity": "0.72",
}

NAVIGATIONAID_STYLES = {
    "als": {
        "color": "#D18B00",
        "outline": "#D18B00",
        "shape": "cross2",
        "size": "2.4",
    },
    "papi": {
        "color": "#7557B8",
        "outline": "#FFFFFF",
        "shape": "diamond",
        "size": "2.5",
    },
    "vasi": {
        "color": "#9868C8",
        "outline": "#FFFFFF",
        "shape": "diamond",
        "size": "2.5",
    },
}

AEROWAY_DRAW_PRIORITY = {
    "aerodrome": 0,
    "apron": 10,
    "runway": 20,
    "stopway": 21,
    "extended-takeoff_area": 22,
    "taxiway": 30,
    "taxilane": 31,
    "hangar": 40,
    "terminal": 41,
    "jet_bridge": 50,
    "aerodrome_marking": 60,
    "parking_position": 70,
    "gate": 71,
    "holding_position": 80,
    "navigationaid": 81,
    "helipad": 82,
    "windsock": 83,
    "beacon": 84,
}

AEROWAY_MINIMUM_SCALES = {
    "taxilane": 25_000,
    "holding_position": 25_000,
    "navigationaid": 25_000,
    "helipad": 25_000,
    "windsock": 25_000,
    "beacon": 25_000,
    "aerodrome_marking": 10_000,
    "parking_position": 10_000,
    "gate": 10_000,
    "jet_bridge": 10_000,
}

AEROWAY_LABEL_STYLES = {
    "taxiway": {
        "fields": ("ref", "name"),
        "size": 8.0,
        "color": "#303840",
        "merge_lines": False,
    },
    "parking_position": {
        "fields": ("ref", "name"),
        "size": 7.5,
        "color": "#315664",
    },
    "gate": {
        "fields": ("ref", "name"),
        "size": 7.5,
        "color": "#2E5E80",
    },
    "terminal": {
        "fields": ("name", "ref"),
        "size": 9.0,
        "color": "#29343E",
    },
}
AEROWAY_LABEL_MINIMUM_SCALE = 3_000


def _marker_symbol(style: dict) -> QgsMarkerSymbol:
    """Create a compact marker with color and shape differentiation."""
    return QgsMarkerSymbol.createSimple(
        {
            "name": style["shape"],
            "color": style["color"],
            "outline_color": style["outline"],
            "outline_width": "0.35",
            "size": style["size"],
        }
    )


def _apply_navigationaid_style(layer: QgsVectorLayer, style: dict) -> bool:
    """Categorize navigation aids by their preserved subtype attribute."""
    field_index = layer.fields().indexOf("navigationaid")
    if field_index < 0:
        return False
    values = sorted(
        {
            str(value).strip().lower()
            for value in layer.uniqueValues(field_index)
            if value is not None and str(value).strip()
        }
    )
    if not values:
        return False
    categories = []
    for value in values:
        category_style = dict(style)
        category_style.update(NAVIGATIONAID_STYLES.get(value, {}))
        categories.append(
            QgsRendererCategory(
                value,
                _marker_symbol(category_style),
                value.upper().replace("_", " "),
            )
        )
    layer.setRenderer(QgsCategorizedSymbolRenderer("navigationaid", categories))
    return True


def _label_expression(layer: QgsVectorLayer, field_names: tuple[str, ...]) -> str:
    """Build a first-nonempty expression from fields present on the layer."""
    fields = [
        field_name
        for field_name in field_names
        if layer.fields().indexOf(field_name) >= 0
    ]
    values = [
        f'nullif(trim(to_string("{field_name}")), \'\')'
        for field_name in fields
    ]
    if not values:
        return ""
    if len(values) == 1:
        return values[0]
    return f"coalesce({', '.join(values)})"


def _apply_aeroway_labels(layer: QgsVectorLayer, category: str) -> None:
    """Enable collision-aware labels only at close working scales."""
    label_style = AEROWAY_LABEL_STYLES.get(category)
    if label_style is None:
        return
    expression = _label_expression(layer, label_style["fields"])
    if not expression:
        return

    settings = QgsPalLayerSettings()
    settings.fieldName = expression
    settings.isExpression = True
    settings.scaleVisibility = True
    settings.minimumScale = float(AEROWAY_LABEL_MINIMUM_SCALE)
    settings.maximumScale = 1.0
    settings.priority = 7
    settings.obstacle = False

    geometry_type = layer.geometryType()
    if geometry_type == QgsWkbTypes.LineGeometry:
        settings.placement = QgsPalLayerSettings.Line
        try:
            line_settings = settings.lineSettings()
            if hasattr(line_settings, "setMergeLines"):
                line_settings.setMergeLines(
                    bool(label_style.get("merge_lines", True))
                )
            if hasattr(settings, "labelPerPart"):
                settings.labelPerPart = False
        except Exception:
            pass
    elif geometry_type == QgsWkbTypes.PolygonGeometry:
        settings.placement = QgsPalLayerSettings.Horizontal
        settings.centroidInside = True
        settings.centroidWhole = False
    else:
        settings.placement = QgsPalLayerSettings.OrderedPositionsAroundPoint

    text_format = QgsTextFormat()
    text_format.setFont(QFont("Helvetica", int(label_style["size"])))
    text_format.setSize(float(label_style["size"]))
    text_format.setColor(QColor(label_style["color"]))
    buffer = QgsTextBufferSettings()
    buffer.setEnabled(True)
    buffer.setSize(0.75)
    buffer.setColor(QColor(255, 255, 255, 225))
    text_format.setBuffer(buffer)
    settings.setFormat(text_format)

    layer.setLabeling(QgsVectorLayerSimpleLabeling(settings))
    layer.setLabelsEnabled(True)


def apply_aeroway_style(layer: QgsVectorLayer, category: str) -> None:
    """Apply a restrained, airport-plan style for an OSM aeroway category."""
    style = dict(DEFAULT_AEROWAY_STYLE)
    style.update(AEROWAY_STYLES.get(category, {}))
    geometry_type = layer.geometryType()

    if geometry_type == QgsWkbTypes.PointGeometry:
        if category == "navigationaid" and _apply_navigationaid_style(
            layer,
            style,
        ):
            symbol = None
        else:
            symbol = _marker_symbol(style)
    elif geometry_type == QgsWkbTypes.LineGeometry:
        symbol = QgsLineSymbol.createSimple(
            {
                "color": style["line_color"],
                "width": style["width"],
                "line_width_unit": style["width_unit"],
                "line_style": style["line_style"],
                "capstyle": style["capstyle"],
                "joinstyle": style["joinstyle"],
            }
        )
        center_color = style.get("center_color")
        if symbol is not None and center_color:
            center_line = QgsSimpleLineSymbolLayer.create(
                {
                    "color": center_color,
                    "width": style["center_width"],
                    "line_width_unit": style["width_unit"],
                    "line_style": style["center_style"],
                    "capstyle": style["capstyle"],
                    "joinstyle": style["joinstyle"],
                }
            )
            if center_line is not None:
                if style["symbol_levels"]:
                    symbol.symbolLayer(0).setRenderingPass(0)
                    center_line.setRenderingPass(1)
                symbol.appendSymbolLayer(center_line)
    elif geometry_type == QgsWkbTypes.PolygonGeometry:
        symbol = QgsFillSymbol.createSimple(
            {
                "color": style["fill"],
                "outline_color": style["outline"],
                "outline_width": "0.45",
            }
        )
        if symbol is not None:
            symbol.setOpacity(float(style["opacity"]))
    else:
        return

    if symbol is not None:
        renderer = QgsSingleSymbolRenderer(symbol)
        if style["symbol_levels"]:
            renderer.setUsingSymbolLevels(True)
        layer.setRenderer(renderer)
    minimum_scale = AEROWAY_MINIMUM_SCALES.get(category)
    if minimum_scale is not None:
        layer.setScaleBasedVisibility(True)
        layer.setMinimumScale(float(minimum_scale))
        layer.setMaximumScale(0.0)
    _apply_aeroway_labels(layer, category)
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
        "[out:xml][timeout:45];\n"
        "(\n"
        f'  node["aeroway"]({around});\n'
        f'  way["aeroway"]({around});\n'
        f'  relation["aeroway"]({around});\n'
        ");\n"
        "(._;>;);\n"
        "out body qt;"
    )


def _post_overpass(endpoint: str, payload: QByteArray) -> bytes:
    """Post one query to an Overpass endpoint and validate its OSM response."""
    request = QNetworkRequest(QUrl(endpoint))
    if hasattr(request, "setTransferTimeout"):
        request.setTransferTimeout(50_000)
    known_headers = getattr(QNetworkRequest, "KnownHeaders", QNetworkRequest)
    request.setHeader(
        known_headers.ContentTypeHeader,
        "application/x-www-form-urlencoded",
    )
    request.setRawHeader(
        QByteArray(b"User-Agent"),
        QByteArray(
            b"SafeguardingBuilder-QGIS/0.1 "
            b"(https://github.com/camtodd1/prj-lucid)"
        ),
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


def fetch_aeroway_osm(
    latitude: float,
    longitude: float,
    attempt_callback: Optional[Callable[[int, int], None]] = None,
) -> bytes:
    """Download OSM XML, failing over when a public Overpass instance is busy."""
    payload = QByteArray(
        urlencode({"data": build_aeroway_query(latitude, longitude)}).encode("utf-8")
    )
    errors = []
    endpoint_count = len(OVERPASS_ENDPOINTS)
    for attempt, endpoint in enumerate(OVERPASS_ENDPOINTS, start=1):
        if attempt_callback is not None:
            attempt_callback(attempt, endpoint_count)
        try:
            return _post_overpass(endpoint, payload)
        except RuntimeError as exc:
            errors.append(f"{endpoint}: {exc}")
    raise RuntimeError("All Overpass endpoints failed. " + " | ".join(errors))
