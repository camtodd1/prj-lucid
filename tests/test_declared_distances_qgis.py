"""Source-backed declared-distance and stopway geometry checks."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

from qgis.core import QgsPointXY, QgsSymbolLayer, QgsVectorLayer

WORKSPACE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORKSPACE.parent))

from safeguarding_builder.safeguarding_builder import SafeguardingBuilder  # noqa: E402
from safeguarding_builder.rulesets.cap168.physical_data import (  # noqa: E402
    CLEARWAY_CAP168_REF,
    DECLARED_DISTANCE_CAP168_REF,
    STOPWAY_CAP168_REF,
)
from safeguarding_builder.rulesets.cap168.profile import CAP168_PROFILE  # noqa: E402
from safeguarding_builder.rulesets.mos139.profile import MOS139_PROFILE  # noqa: E402


FIXTURE_DIR = WORKSPACE / "tests" / "fixtures" / "ols"
CHECKPOINT_PATH = FIXTURE_DIR / "declared_distances_v1.json"


class DeclaredDistanceQgisTests(unittest.TestCase):
    @staticmethod
    def _builder():
        builder = object.__new__(SafeguardingBuilder)
        builder.ruleset = CAP168_PROFILE
        builder.translator = None
        builder._run_log = None
        builder.plugin_dir = str(WORKSPACE)
        return builder

    @staticmethod
    def _source_runway(case):
        payload = json.loads(
            (FIXTURE_DIR / case["input_fixture"]).read_text(encoding="utf-8")
        )
        source = dict(payload["runways"][case["runway_index"]])
        source["short_name"] = case["runway_name"]
        source["thr_point"] = QgsPointXY(
            float(source.pop("thr_easting")),
            float(source.pop("thr_northing")),
        )
        source["rec_thr_point"] = QgsPointXY(
            float(source.pop("rec_easting")),
            float(source.pop("rec_northing")),
        )
        source["original_index"] = case["runway_index"] + 1
        for key in (
            "width",
            "shoulder",
            "thr_displaced_1",
            "thr_displaced_2",
            "thr_pre_area_1",
            "thr_pre_area_2",
        ):
            source[key] = float(source.get(key) or 0.0)
        return source

    def test_checkpoint_source_references_match_cap168_policy(self):
        checkpoint = json.loads(CHECKPOINT_PATH.read_text(encoding="utf-8"))
        self.assertEqual(checkpoint["source"]["declared_distances"], DECLARED_DISTANCE_CAP168_REF)
        self.assertEqual(checkpoint["source"]["clearway"], CLEARWAY_CAP168_REF)
        self.assertEqual(checkpoint["source"]["stopway"], STOPWAY_CAP168_REF)

    def test_starter_extension_only_adds_length_beyond_displaced_runway_end(self):
        runway = {
            "short_name": "09/27",
            "thr_point": QgsPointXY(0.0, 0.0),
            "rec_thr_point": QgsPointXY(1000.0, 0.0),
            "thr_displaced_1": 100.0,
            "thr_displaced_2": 0.0,
            "starter_extension_length_1": 150.0,
            "starter_extension_length_2": 0.0,
        }

        records = self._builder()._calculate_declared_distances(
            runway, ruleset=CAP168_PROFILE
        )
        by_direction = {record["direction"]: record for record in records}

        self.assertEqual(by_direction["primary"]["physical_len_m"], 1100.0)
        self.assertEqual(by_direction["primary"]["tora_m"], 1150.0)
        self.assertEqual(by_direction["reciprocal"]["tora_m"], 1100.0)

    def test_starter_extension_generates_pre_threshold_styled_polygon(self):
        runway = {
            "short_name": "09/27",
            "thr_point": QgsPointXY(0.0, 0.0),
            "rec_thr_point": QgsPointXY(1000.0, 0.0),
            "thr_displaced_1": 100.0,
            "thr_displaced_2": 0.0,
            "starter_extension_length_1": 150.0,
            "starter_extension_width_1": 45.0,
            "width": 45.0,
        }

        generated = self._builder().generate_physical_geometry(runway)
        extension = next(
            (geometry, attrs)
            for kind, geometry, attrs in generated
            if kind == "StarterExtension"
        )
        pre_threshold = next(
            geometry
            for kind, geometry, _attrs in generated
            if kind == "PreThresholdRunway"
        )

        geometry, attrs = extension
        self.assertAlmostEqual(geometry.area(), 150.0 * 45.0, places=6)
        self.assertAlmostEqual(geometry.centroid().asPoint().x(), -75.0, places=6)
        self.assertAlmostEqual(
            geometry.intersection(pre_threshold).area(), 100.0 * 45.0, places=6
        )
        self.assertEqual(attrs["end_desig"], "09")
        self.assertEqual(attrs["len_m"], 150.0)
        self.assertEqual(attrs["wid_m"], 45.0)

    def test_mos139_starter_extension_attaches_boundary_width_and_generates_arrows(self):
        builder = self._builder()
        builder.ruleset = MOS139_PROFILE
        runway = {
            "short_name": "09/27",
            "thr_point": QgsPointXY(0.0, 0.0),
            "rec_thr_point": QgsPointXY(1000.0, 0.0),
            "width": 45.0,
            "surface_category": "Sealed",
            "arc_num": 4,
            "type1": "Precision Approach CAT II/III",
            "type2": "Non-Instrument (NI)",
            "starter_extension_length_1": 150.0,
            "starter_extension_width_1": 45.0,
        }

        markings = [
            (geometry, attrs)
            for kind, geometry, attrs in builder.generate_detailed_runway_markings(runway)
            if kind == "DetailedStarterExtensionMarking"
        ]
        extension_attrs = next(
            attrs
            for kind, _geometry, attrs in builder.generate_physical_geometry(runway)
            if kind == "StarterExtension"
        )

        self.assertEqual(extension_attrs["mark_w_m"], 0.9)
        self.assertEqual(len(markings), 3)
        self.assertTrue(all(attrs["sub_type"] == "Arrow" for _geometry, attrs in markings))
        self.assertTrue(all(attrs["end_desig"] == "09" for _geometry, attrs in markings))
        self.assertEqual(
            sorted(attrs["offset_m"] for _geometry, attrs in markings),
            [37.2, 87.2, 137.2],
        )
        self.assertTrue(all(not attrs["mandatory"] for _geometry, attrs in markings))
        self.assertTrue(
            all(
                geometry.boundingBox().xMinimum() >= -150.0 - 1e-6
                and geometry.boundingBox().xMaximum() <= 1e-6
                for geometry, _attrs in markings
            )
        )

    def test_starter_extension_polygon_outline_uses_marking_width_field(self):
        builder = self._builder()
        layer = QgsVectorLayer(
            "Polygon?crs=EPSG:3857&field=mark_w_m:double",
            "Starter Extension",
            "memory",
        )
        layer.loadNamedStyle(str(WORKSPACE / "styles" / "physical_prethreshold_runway.qml"))

        builder._style_starter_extension_layer(layer)

        line_layer = layer.renderer().symbol().symbolLayer(1)
        width_property = line_layer.dataDefinedProperties().property(
            QgsSymbolLayer.PropertyStrokeWidth
        )
        self.assertTrue(width_property.isActive())
        self.assertEqual(width_property.expressionString(), 'coalesce("mark_w_m", 0.5)')

    def test_declared_distances_and_stopways_match_source_checkpoints(self):
        checkpoint = json.loads(CHECKPOINT_PATH.read_text(encoding="utf-8"))
        for case in checkpoint["cases"]:
            with self.subTest(
                fixture=case["input_fixture"],
                runway=case["runway_name"],
            ):
                builder = self._builder()
                runway = self._source_runway(case)
                expected = case["expected"]
                records = builder._calculate_declared_distances(
                    runway,
                    ruleset=CAP168_PROFILE,
                )
                by_end = {record["end_desig"]: record for record in records}

                self.assertAlmostEqual(
                    records[0]["threshold_len_m"],
                    expected["threshold_length_m"],
                    places=6,
                )
                self.assertAlmostEqual(
                    records[0]["physical_len_m"],
                    expected["physical_length_m"],
                    places=6,
                )
                self.assertEqual(set(by_end), set(expected["directions"]))
                for end_desig, expected_record in expected["directions"].items():
                    record = by_end[end_desig]
                    for key, expected_value in expected_record.items():
                        with self.subTest(end=end_desig, field=key):
                            self.assertAlmostEqual(record[key], expected_value, places=6)
                    self.assertAlmostEqual(
                        record["toda_m"] - record["tora_m"],
                        record["clearway_m"],
                        places=6,
                    )
                    self.assertAlmostEqual(
                        record["asda_m"] - record["tora_m"],
                        record["stopway_m"],
                        places=6,
                    )

                generated = builder.generate_physical_geometry(runway)
                self.assertIsNotNone(generated)
                runway_geometry = next(
                    geometry for kind, geometry, _ in generated if kind == "rwy"
                )
                stopway_elements = {
                    attrs["end_desig"]: (geometry, attrs)
                    for kind, geometry, attrs in generated
                    if kind == "Stopway"
                }
                self.assertEqual(
                    set(stopway_elements),
                    {item["end_desig"] for item in expected["stopways"]},
                )
                params = builder._get_runway_parameters(
                    runway["thr_point"], runway["rec_thr_point"]
                )
                endpoints = builder._get_physical_runway_endpoints(
                    runway["thr_point"],
                    runway["rec_thr_point"],
                    runway["thr_displaced_1"],
                    runway["thr_displaced_2"],
                    params,
                )
                primary_end, reciprocal_end, _ = endpoints
                primary_desig, reciprocal_desig = case["runway_name"].split("/", 1)
                for expected_stopway in expected["stopways"]:
                    end_desig = expected_stopway["end_desig"]
                    geometry, attrs = stopway_elements[end_desig]
                    endpoint = (
                        primary_end if end_desig == primary_desig else reciprocal_end
                    )
                    self.assertEqual(attrs["ref_mos"], STOPWAY_CAP168_REF)
                    self.assertAlmostEqual(attrs["len_m"], expected_stopway["length_m"], places=6)
                    self.assertAlmostEqual(attrs["wid_m"], expected_stopway["width_m"], places=6)
                    self.assertAlmostEqual(geometry.area(), expected_stopway["area_m2"], places=5)
                    self.assertAlmostEqual(
                        geometry.centroid().asPoint().distance(endpoint),
                        expected_stopway["centroid_distance_from_physical_end_m"],
                        places=5,
                    )
                    self.assertLessEqual(
                        geometry.intersection(runway_geometry).area(),
                        1e-5,
                    )


if __name__ == "__main__":
    unittest.main()
