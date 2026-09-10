"""Portable, metre-scale preview of the current solved OLS candidates."""
import json
import math
import struct
from pathlib import Path

from qgis.core import QgsGeometry, QgsPointXY, QgsRectangle, QgsTessellator


def candidate_mesh(candidate, origin, spacing=150.0):
    """Clip a display grid to the domain, retaining holes; evaluate every vertex."""
    footprint = candidate.footprint
    bounds = footprint.boundingBox()
    # Planar models need no interior subdivision. Curved models use a bounded grid.
    step = max(spacing, max(bounds.width(), bounds.height()) / 100)
    pieces = [footprint]
    if candidate.model not in ('constant', 'axis', 'plane'):
        pieces = []
        for row in range(max(1, math.ceil(bounds.height() / step))):
            for col in range(max(1, math.ceil(bounds.width() / step))):
                x, y = bounds.xMinimum() + col * step, bounds.yMinimum() + row * step
                part = footprint.intersection(QgsGeometry.fromRect(QgsRectangle(x, y, x + step, y + step)))
                if not part.isEmpty():
                    pieces.append(part)
    vertices = []
    for piece in pieces:
        for polygon in piece.constParts():
            if not hasattr(polygon, 'exteriorRing'):
                continue
            tess = QgsTessellator(origin[0], origin[1], False, False, False, True)
            tess.addPolygon(polygon, 0)
            if tess.error():
                raise ValueError(f'{candidate.surface_id}: {tess.error()}')
            # QGIS returns float32 mesh coordinates. Evaluate heights at the
            # original double-precision vertices, before that display rounding
            # can move a boundary point outside a bounded surface evaluator.
            source_points = {
                struct.unpack('ff', struct.pack('ff', point.x() - origin[0], origin[1] - point.y())):
                QgsPointXY(point.x(), point.y())
                for point in polygon.vertices()
            }
            data = tess.data()
            for i in range(0, len(data), 3):
                x, north = float(data[i]), -float(data[i + 2])
                point = source_points.get((x, -north))
                if point is None:
                    raise ValueError(f'{candidate.surface_id}: triangulation introduced an unverified vertex')
                z = candidate.elevation_at_xy(point)
                x, north = point.x() - origin[0], point.y() - origin[1]
                if z is None or not math.isfinite(float(z)):
                    raise ValueError(f'{candidate.surface_id}: missing elevation')
                vertices.extend((x, float(z), -north))
    if not vertices:
        raise ValueError(f'{candidate.surface_id}: no triangles generated')
    return vertices


def terrain_mesh(dem, crs, bounds, origin, resolution=96):
    from qgis.core import QgsCoordinateTransform, QgsProject
    transform = QgsCoordinateTransform(crs, dem.crs(), QgsProject.instance())
    points = []
    for row in range(resolution + 1):
        line = []
        for col in range(resolution + 1):
            x = bounds.xMinimum() + bounds.width() * col / resolution
            y = bounds.yMinimum() + bounds.height() * row / resolution
            point = transform.transform(QgsPointXY(x, y))
            value, valid = dem.dataProvider().sample(point, 1)
            line.append((x-origin[0], float(value), origin[1]-y) if valid and math.isfinite(value) else None)
        points.append(line)
    vertices = []
    for row in range(resolution):
        for col in range(resolution):
            a,b,c,d = points[row][col],points[row][col+1],points[row+1][col],points[row+1][col+1]
            for triangle in ((a,b,c),(b,d,c)):
                if all(point is not None for point in triangle):
                    for point in triangle:
                        vertices.extend(point)
    if not vertices:
        raise ValueError('The DEM has no valid samples in the OLS extent.')
    return vertices


def export_scene(engines, crs, output_path, title='Safeguarding 3D', dem=None):
    from qgis.core import Qgis
    if not crs.isValid() or crs.isGeographic() or crs.mapUnits() != Qgis.DistanceUnit.Meters:
        raise ValueError('Use a projected project coordinate system in metres before export.')
    candidates = [(str(family), candidate) for family, engine in engines.items() for candidate in engine.candidates]
    if not candidates:
        raise ValueError('Generate OLS surfaces in this session before exporting the 3D view.')
    bounds = QgsRectangle(candidates[0][1].footprint.boundingBox())
    for _, candidate in candidates[1:]:
        bounds.combineExtentWith(candidate.footprint.boundingBox())
    origin = (bounds.center().x(), bounds.center().y())
    layers = []
    for family, candidate in candidates:
        layers.append({'name': f'{family} · {candidate.surface_type} · {candidate.surface_id}',
                       'model': candidate.model, 'metadata': candidate.metadata,
                       'vertices': candidate_mesh(candidate, origin)})
    if dem is not None:
        layers.append({'name': 'Terrain · '+dem.name(), 'model': 'terrain', 'metadata': {'source': dem.name(), 'datum': 'User confirmed compatible with OLS elevations', 'sampling': '96 × 96 display cells'}, 'vertices': terrain_mesh(dem, crs, bounds, origin)})
    payload = {'title': title, 'crs': crs.authid(), 'origin': origin, 'layers': layers,
               'note': 'Prototype • actual elevations, 1× vertical scale • curved surfaces approximated by a display mesh • no vertical datum transformation'}
    assets = Path(__file__).resolve().parents[1] / 'web_viewer'
    html = (assets / 'viewer.html').read_text()
    html = html.replace('/*LICENSE*/', (assets / 'THREE-LICENSE.txt').read_text())
    html = html.replace('/*THREE*/', (assets / 'three.min.js').read_text())
    html = html.replace('/*ORBIT*/', (assets / 'OrbitControls.js').read_text())
    html = html.replace('/*SCENE*/', json.dumps(payload, default=str, allow_nan=False).replace('<', '\\u003c'))
    with open(output_path, 'x', encoding='utf-8') as stream:
        stream.write(html)
    return len(layers)


def export_dialog(plugin):
    from qgis.PyQt.QtWidgets import QFileDialog, QMessageBox, QDialog, QVBoxLayout, QComboBox, QCheckBox, QDialogButtonBox, QLabel
    from qgis.PyQt.QtCore import QUrl
    from qgis.PyQt.QtGui import QDesktopServices
    from qgis.core import QgsProject
    engines = getattr(plugin, '_terrain_ols_engines', {})
    if not engines:
        QMessageBox.information(plugin.iface.mainWindow(), '3D safeguarding', 'Generate OLS surfaces in this session first.')
        return
    dialog = QDialog(plugin.iface.mainWindow())
    dialog.setWindowTitle('3D safeguarding prototype')
    layout = QVBoxLayout(dialog)
    layout.addWidget(QLabel('Optional terrain DEM (band 1):'))
    choice = QComboBox()
    choice.addItem('No terrain', None)
    from qgis.core import QgsRasterLayer
    for layer in QgsProject.instance().mapLayers().values():
        if isinstance(layer, QgsRasterLayer) and layer.isValid():
            choice.addItem(layer.name(), layer)
    layout.addWidget(choice)
    datum = QCheckBox('I have checked that this DEM uses metres and the same vertical datum as the OLS.')
    layout.addWidget(datum)
    buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
    buttons.accepted.connect(dialog.accept)
    buttons.rejected.connect(dialog.reject)
    layout.addWidget(buttons)
    def update():
        buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(choice.currentData() is None or datum.isChecked())
    choice.currentIndexChanged.connect(update)
    datum.toggled.connect(update)
    if not dialog.exec():
        return
    dem = choice.currentData()
    path, _ = QFileDialog.getSaveFileName(plugin.iface.mainWindow(), 'Export 3D safeguarding prototype', 'safeguarding_3d.html', 'HTML (*.html)')
    if not path:
        return
    if not path.lower().endswith('.html'):
        path += '.html'
    try:
        export_scene(engines, QgsProject.instance().crs(), path, f'{getattr(plugin, "icao_code", "")} Safeguarding 3D', dem=dem)
    except Exception as error:
        QMessageBox.warning(plugin.iface.mainWindow(), '3D export failed', str(error))
        return
    QDesktopServices.openUrl(QUrl.fromLocalFile(path))
