"""Headless QGIS integration audit for a saved Safeguarding Builder input."""

import json
import os
import sys

from qgis.PyQt.QtCore import QCoreApplication, QSize
from qgis.PyQt.QtGui import QColor
from qgis.core import (
    Qgis,
    QgsApplication,
    QgsCoordinateReferenceSystem,
    QgsGeometry,
    QgsLayerTreeGroup,
    QgsLayerTreeLayer,
    QgsMapRendererParallelJob,
    QgsMapSettings,
    QgsProject,
    QgsRectangle,
)


class _MessageBar:
    def __init__(self):
        self.messages = []

    def pushMessage(self, *args, **kwargs):
        self.messages.append([str(arg) for arg in args])


class _Iface:
    def __init__(self):
        self.bar = _MessageBar()

    def messageBar(self):
        return self.bar

    def mainWindow(self):
        return None


def _group_at(root, path):
    node = root
    for name in path:
        node = next(
            (child for child in node.children() if isinstance(child, QgsLayerTreeGroup) and child.name() == name),
            None,
        )
        if node is None:
            return None
    return node


def _child_names(group):
    return [child.name() for child in group.children()]


def _layer_records(group, path=()):
    records = []
    for child in group.children():
        if isinstance(child, QgsLayerTreeGroup):
            records.extend(_layer_records(child, path + (child.name(),)))
            continue
        if not isinstance(child, QgsLayerTreeLayer) or child.layer() is None:
            continue
        layer = child.layer()
        invalid = empty = 0
        for feature in layer.getFeatures():
            geometry = feature.geometry()
            if geometry is None or geometry.isNull() or geometry.isEmpty():
                empty += 1
            elif layer.geometryType() == Qgis.GeometryType.Polygon and not geometry.isGeosValid():
                invalid += 1
        renderer = layer.renderer()
        rules = []
        if renderer is not None and renderer.type() == "RuleRenderer":
            rules = [rule.label() for rule in renderer.rootRule().children()]
        records.append(
            {
                "path": list(path),
                "name": layer.name(),
                "features": layer.featureCount(),
                "style_key": str(layer.customProperty("safeguarding_style_key") or ""),
                "renderer": renderer.type() if renderer is not None else None,
                "rules": rules,
                "invalid": invalid,
                "empty": empty,
                "fields": layer.fields().names(),
            }
        )
    return records


def _union(layer):
    geometries = [feature.geometry() for feature in layer.getFeatures() if feature.hasGeometry()]
    return QgsGeometry.unaryUnion(geometries) if geometries else QgsGeometry()


def run(input_path, audit_path, preview_path):
    workspace = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sys.path.insert(0, os.path.dirname(workspace))
    from safeguarding_builder.safeguarding_builder import SafeguardingBuilder
    from safeguarding_builder.safeguarding_builder_dialog import SafeguardingBuilderDialog

    app = QgsApplication([], True)
    app.setPrefixPath("/Applications/QGIS-4.0.app/Contents/MacOS", True)
    app.initQgis()
    logs = []
    QgsApplication.messageLog().messageReceived.connect(
        lambda message, tag, level: logs.append({"message": message, "tag": tag, "level": int(level)})
    )
    project = QgsProject.instance()
    project.clear()
    project.setCrs(QgsCoordinateReferenceSystem("EPSG:28356"))

    with open(input_path, "r", encoding="utf-8") as handle:
        payload = json.load(handle)
    dialog = SafeguardingBuilderDialog()
    if hasattr(dialog, "_airport_lookup_timer"):
        dialog._airport_lookup_timer.stop()
    dialog._apply_loaded_payload(payload)
    QCoreApplication.processEvents()
    if hasattr(dialog, "_airport_lookup_timer"):
        dialog._airport_lookup_timer.stop()
    if dialog.get_all_input_data() is None:
        raise RuntimeError("Input failed dialog validation")

    iface = _Iface()
    builder = SafeguardingBuilder(iface)
    builder.dlg = dialog
    builder.run_safeguarding_processing()

    root = project.layerTreeRoot()
    main = _group_at(root, [f"{payload['icao_code']} Safeguarding Builder"])
    ols = _group_at(main, ["04 Obstacle Limitation Surfaces"])
    debug = _group_at(main, ["99 Debug / Development"])
    if main is None or ols is None or debug is None:
        raise AssertionError("Generated root, OLS, or debug group is missing")
    assert _child_names(ols) == ["OFS", "OES"], _child_names(ols)
    ofs = _group_at(ols, ["OFS"])
    oes = _group_at(ols, ["OES"])
    for family_group in (ofs, oes):
        for child in family_group.children():
            if isinstance(child, QgsLayerTreeGroup) and child.name().startswith("RWY "):
                assert all(isinstance(grandchild, QgsLayerTreeLayer) for grandchild in child.children())

    records = _layer_records(main)
    annex = [record for record in records if record["style_key"].startswith("Annex 14")]
    expected_styles = {
        "Annex 14 OFS Surface", "Annex 14 OES Surface",
        "Annex 14 OFS Contour", "Annex 14 OES Contour",
        "Annex 14 Controlling OFS", "Annex 14 Controlling OES",
        "Annex 14 Candidate OFS", "Annex 14 Candidate OES",
        "Annex 14 Transition OFS", "Annex 14 Transition OES",
    }
    assert expected_styles <= {record["style_key"] for record in annex}
    assert all(record["renderer"] == "RuleRenderer" for record in annex)
    assert all(record["features"] > 0 and record["invalid"] == 0 and record["empty"] == 0 for record in annex)
    assert {"Annex 14 OFS Controlling", "Annex 14 OES Controlling"} <= set(_child_names(debug))

    coverage = {}
    for family, family_group in (("OFS", ofs), ("OES", oes)):
        debug_family = _group_at(debug, [f"Annex 14 {family} Controlling"])
        layers = {
            child.name(): child.layer()
            for child in list(family_group.children()) + list(debug_family.children())
            if isinstance(child, QgsLayerTreeLayer)
        }
        if f"Controlling {family} — Surface" not in layers:
            print(json.dumps({"family": family, "available": sorted(layers), "records": annex, "logs": logs}, indent=2))
        controlling = layers[f"Controlling {family} — Surface"]
        candidates = layers[f"{family} — Planar Candidates"]
        transitions = layers[f"{family} — Planar Transitions"]
        controlling_union = _union(controlling)
        candidate_union = _union(candidates)
        difference = controlling_union.symDifference(candidate_union)
        difference_area = 0.0 if difference.isEmpty() else difference.area()
        candidate_area = candidate_union.area()
        overlap = max(0.0, sum(f.geometry().area() for f in controlling.getFeatures()) - controlling_union.area())
        coverage[family] = {
            "candidates": candidates.featureCount(),
            "transitions": transitions.featureCount(),
            "regions": controlling.featureCount(),
            "candidate_area_m2": candidate_area,
            "coverage_difference_m2": difference_area,
            "coverage_difference_ratio": difference_area / candidate_area if candidate_area else None,
            "region_overlap_m2": overlap,
        }
        assert difference_area <= max(0.1, candidate_area * 1e-7), coverage[family]
        assert overlap <= max(0.1, candidate_area * 1e-7), coverage[family]

    preview_style_keys = {
        "Annex 14 OFS Surface", "Annex 14 OES Surface",
        "Annex 14 OFS Contour", "Annex 14 OES Contour",
    }
    annex_layers = [
        node.layer()
        for node in root.findLayers()
        if node.layer() and str(node.layer().customProperty("safeguarding_style_key") or "") in preview_style_keys
    ]
    extent = QgsRectangle()
    for layer in annex_layers:
        extent.combineExtentWith(layer.extent())
    settings = QgsMapSettings()
    settings.setDestinationCrs(project.crs())
    settings.setLayers(annex_layers)
    settings.setExtent(extent)
    settings.setOutputSize(QSize(1800, 1200))
    settings.setBackgroundColor(QColor("#f6f4ef"))
    job = QgsMapRendererParallelJob(settings)
    job.start()
    job.waitForFinished()
    job.renderedImage().save(preview_path)

    audit = {
        "input": input_path,
        "crs": project.crs().authid(),
        "ols_children": _child_names(ols),
        "ofs_children": _child_names(ofs),
        "oes_children": _child_names(oes),
        "debug_children": _child_names(debug),
        "annex_layers": len(annex),
        "annex_features": sum(record["features"] for record in annex),
        "coverage": coverage,
        "layers": annex,
        "warnings": [entry for entry in logs if entry["level"] >= int(Qgis.Warning)],
        "message_bar": iface.bar.messages,
        "preview": preview_path,
    }
    with open(audit_path, "w", encoding="utf-8") as handle:
        json.dump(audit, handle, indent=2)
    print(json.dumps(audit, indent=2))
    dialog.deleteLater()
    project.clear()
    app.exitQgis()


if __name__ == "__main__":
    run(sys.argv[1], sys.argv[2], sys.argv[3])
