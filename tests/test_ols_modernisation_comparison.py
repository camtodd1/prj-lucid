import unittest

from qgis.core import QgsGeometry, QgsPointXY, QgsRectangle

from guidelines.controlling_ols_engine import (
    ControllingOlsCandidate,
    PlanarControllingOlsEngine,
    constant_elevation_evaluator,
    plane_elevation_evaluator,
)
from guidelines.ols_modernisation_comparison import OlsEnvelopeComparisonEngine


class OlsModernisationComparisonTests(unittest.TestCase):
    def setUp(self):
        self.domain = QgsGeometry.fromRect(QgsRectangle(0.0, 0.0, 100.0, 100.0))

    def constant(self, surface_id, elevation):
        return ControllingOlsCandidate(
            surface_id=surface_id,
            surface_type="Test",
            footprint=QgsGeometry(self.domain),
            elevation_at_xy=constant_elevation_evaluator(elevation),
            model="constant",
            metadata={"elevation_m": elevation},
        )

    def plane(self, surface_id, a, b, c):
        return ControllingOlsCandidate(
            surface_id=surface_id,
            surface_type="Test Plane",
            footprint=QgsGeometry(self.domain),
            elevation_at_xy=plane_elevation_evaluator(a, b, c),
            model="plane",
            metadata={"plane_a": a, "plane_b": b, "plane_c": c},
        )

    def compare(self, baseline, future):
        return OlsEnvelopeComparisonEngine(
            PlanarControllingOlsEngine([baseline]),
            PlanarControllingOlsEngine([future]),
        ).comparison_parts()

    def test_higher_future_surface_is_gain(self):
        parts = self.compare(self.constant("baseline", 100.0), self.constant("future", 110.0))
        self.assertEqual(len(parts["gain"]), 1)
        self.assertEqual(len(parts["loss"]), 0)
        self.assertEqual(len(parts["no_change"]), 0)
        self.assertAlmostEqual(parts["gain"][0][2].area(), 10000.0, places=3)

    def test_lower_future_surface_is_loss(self):
        parts = self.compare(self.constant("baseline", 100.0), self.constant("future", 90.0))
        self.assertEqual(len(parts["gain"]), 0)
        self.assertEqual(len(parts["loss"]), 1)
        self.assertEqual(len(parts["no_change"]), 0)
        self.assertAlmostEqual(parts["loss"][0][2].area(), 10000.0, places=3)

    def test_crossing_surface_splits_gain_and_loss(self):
        parts = self.compare(self.constant("baseline", 100.0), self.plane("future", 0.2, 0.0, 90.0))
        gain_area = sum(part[2].area() for part in parts["gain"])
        loss_area = sum(part[2].area() for part in parts["loss"])
        self.assertAlmostEqual(gain_area, 5000.0, delta=1.0)
        self.assertAlmostEqual(loss_area, 5000.0, delta=1.0)
        self.assertGreater(sum(part[2].length() for part in parts["transition"]), 0.0)

    def test_equal_surfaces_emit_no_change(self):
        parts = self.compare(self.constant("baseline", 100.0), self.constant("future", 100.0))
        self.assertEqual(len(parts["gain"]), 0)
        self.assertEqual(len(parts["loss"]), 0)
        self.assertEqual(len(parts["transition"]), 0)
        self.assertEqual(len(parts["no_change"]), 1)
        self.assertAlmostEqual(parts["no_change"][0][2].area(), 10000.0, places=3)

    def test_nearly_equal_surfaces_emit_no_change(self):
        parts = self.compare(self.constant("baseline", 100.0), self.constant("future", 100.005))
        self.assertEqual(len(parts["gain"]), 0)
        self.assertEqual(len(parts["loss"]), 0)
        self.assertEqual(len(parts["no_change"]), 1)

    def test_baseline_only_parts_show_missing_future_overlay(self):
        baseline = self.constant("baseline", 100.0)
        future = ControllingOlsCandidate(
            surface_id="future",
            surface_type="Future",
            footprint=QgsGeometry.fromRect(QgsRectangle(50.0, 0.0, 100.0, 100.0)),
            elevation_at_xy=constant_elevation_evaluator(110.0),
            model="constant",
            metadata={"elevation_m": 110.0},
        )
        engine = OlsEnvelopeComparisonEngine(
            PlanarControllingOlsEngine([baseline]),
            PlanarControllingOlsEngine([future]),
        )
        parts = engine.baseline_only_parts()
        self.assertEqual(len(parts), 1)
        self.assertAlmostEqual(parts[0][1].area(), 5000.0, places=3)

    def test_baseline_only_ignores_tiny_boundary_sliver(self):
        baseline = self.constant("baseline", 100.0)
        future = ControllingOlsCandidate(
            surface_id="future",
            surface_type="Future",
            footprint=QgsGeometry.fromRect(QgsRectangle(0.2, 0.0, 100.0, 100.0)),
            elevation_at_xy=constant_elevation_evaluator(110.0),
            model="constant",
            metadata={"elevation_m": 110.0},
        )
        engine = OlsEnvelopeComparisonEngine(
            PlanarControllingOlsEngine([baseline]),
            PlanarControllingOlsEngine([future]),
        )
        self.assertEqual(engine.baseline_only_parts(), [])

    def test_loss_delta_range_ignores_wrong_side_boundary_spike_samples(self):
        baseline = self.plane("baseline", 1.0, 0.0, 0.0)
        future = self.constant("future", 50.0)
        engine = OlsEnvelopeComparisonEngine(
            PlanarControllingOlsEngine([baseline]),
            PlanarControllingOlsEngine([future]),
        )
        spiked_loss = QgsGeometry.fromPolygonXY([
            [
                QgsPointXY(50.0, 0.0),
                QgsPointXY(100.0, 0.0),
                QgsPointXY(100.0, 100.0),
                QgsPointXY(50.0, 100.0),
                QgsPointXY(50.0, 51.0),
                QgsPointXY(40.0, 50.0),
                QgsPointXY(50.0, 49.0),
                QgsPointXY(50.0, 0.0),
            ]
        ])

        raw_min, raw_max, _raw_rep = engine.delta_range(spiked_loss, baseline, future)
        self.assertAlmostEqual(raw_min, -50.0, places=3)
        self.assertAlmostEqual(raw_max, 10.0, places=3)

        loss_min, loss_max, loss_rep = engine.delta_range(spiked_loss, baseline, future, "loss")
        self.assertAlmostEqual(loss_min, -50.0, places=3)
        self.assertEqual(loss_max, 0.0)
        self.assertLess(loss_rep, 0.0)

        cleaned = engine._clean_comparison_part(spiked_loss, baseline, future, "loss")
        cleaned_vertices = [(round(vertex.x(), 3), round(vertex.y(), 3)) for vertex in cleaned.vertices()]
        self.assertNotIn((40.0, 50.0), cleaned_vertices)
        cleaned_min, cleaned_max, cleaned_rep = engine.delta_range(cleaned, baseline, future, "loss")
        self.assertAlmostEqual(cleaned_min, -50.0, places=3)
        self.assertEqual(cleaned_max, 0.0)
        self.assertLess(cleaned_rep, 0.0)

        spike_remainder = QgsGeometry.fromPolygonXY([
            [QgsPointXY(50.0, 51.0), QgsPointXY(40.0, 50.0), QgsPointXY(50.0, 49.0), QgsPointXY(50.0, 51.0)]
        ])
        self.assertEqual(engine._classify_change_for_part(spike_remainder, baseline, future), "gain")
        repaired_parts = []
        engine._append_parts(repaired_parts, baseline, future, spike_remainder, "gain", clean_spikes=False)
        self.assertEqual(len(repaired_parts), 1)

    def test_final_cleanup_removes_same_side_severe_boundary_spike(self):
        baseline = self.constant("baseline", 100.0)
        future = self.constant("future", 90.0)
        engine = OlsEnvelopeComparisonEngine(
            PlanarControllingOlsEngine([baseline]),
            PlanarControllingOlsEngine([future]),
        )
        spiked_loss = QgsGeometry.fromPolygonXY([
            [
                QgsPointXY(0.0, 0.0),
                QgsPointXY(100.0, 0.0),
                QgsPointXY(100.0, 100.0),
                QgsPointXY(51.0, 100.0),
                QgsPointXY(50.0, 400.0),
                QgsPointXY(49.0, 100.0),
                QgsPointXY(0.0, 100.0),
                QgsPointXY(0.0, 0.0),
            ]
        ])

        cleaned = engine._clean_comparison_part(spiked_loss, baseline, future, "loss")
        cleaned_vertices = [(round(vertex.x(), 3), round(vertex.y(), 3)) for vertex in cleaned.vertices()]
        self.assertNotIn((50.0, 400.0), cleaned_vertices)
        self.assertAlmostEqual(cleaned.area(), 10000.0, places=3)

        parts = {"gain": [], "loss": [(baseline, future, spiked_loss)], "no_change": []}
        engine._finalise_comparison_parts(parts)
        final_vertices = [
            (round(vertex.x(), 3), round(vertex.y(), 3))
            for vertex in parts["loss"][0][2].vertices()
        ]
        self.assertNotIn((50.0, 400.0), final_vertices)
        self.assertAlmostEqual(parts["loss"][0][2].area(), 10000.0, places=3)

    def test_comparison_cleanup_cannot_expand_a_concave_part(self):
        concave_part = QgsGeometry.fromPolygonXY([
            [
                QgsPointXY(0.0, 0.0),
                QgsPointXY(100.0, 0.0),
                QgsPointXY(100.0, 100.0),
                QgsPointXY(51.0, 100.0),
                QgsPointXY(50.0, 20.0),
                QgsPointXY(49.0, 100.0),
                QgsPointXY(0.0, 100.0),
                QgsPointXY(0.0, 0.0),
            ]
        ])
        baseline = self.constant("baseline", 100.0)
        future = self.constant("future", 90.0)
        engine = OlsEnvelopeComparisonEngine(
            PlanarControllingOlsEngine([baseline]),
            PlanarControllingOlsEngine([future]),
        )

        cleaned = engine._clean_comparison_part(concave_part, baseline, future, "loss")
        self.assertLessEqual(cleaned.difference(concave_part).area(), 0.01)

    def test_union_geometries_repairs_invalid_polygon_parts(self):
        invalid = QgsGeometry.fromPolygonXY([
            [
                QgsPointXY(0.0, 0.0),
                QgsPointXY(100.0, 100.0),
                QgsPointXY(0.0, 100.0),
                QgsPointXY(100.0, 0.0),
                QgsPointXY(0.0, 0.0),
            ]
        ])
        engine = OlsEnvelopeComparisonEngine(
            PlanarControllingOlsEngine([self.constant("baseline", 100.0)]),
            PlanarControllingOlsEngine([self.constant("future", 90.0)]),
        )

        union = engine._union_geometries([self.domain, invalid])
        self.assertIsNotNone(union)
        self.assertFalse(union.isEmpty())
        self.assertTrue(union.isGeosValid())
        self.assertGreaterEqual(union.area(), self.domain.area() - 0.01)

    def test_gap_repair_keeps_valid_collinear_base_taper_after_final_cleanup(self):
        """A cleaned tapered overlap is restored after final cleanup."""
        tapered_domain = QgsGeometry.fromPolygonXY([[
            QgsPointXY(0.0, 300.0),
            QgsPointXY(-100.0, 0.0),
            QgsPointXY(-90.0, 10.0),
            QgsPointXY(-80.0, 20.0),
            QgsPointXY(-70.0, 30.0),
            QgsPointXY(0.0, 300.0),
        ]])
        baseline = ControllingOlsCandidate(
            surface_id="baseline-transitional",
            surface_type="Transitional",
            footprint=QgsGeometry(tapered_domain),
            elevation_at_xy=constant_elevation_evaluator(100.0),
            model="constant",
        )
        future = ControllingOlsCandidate(
            surface_id="future-transitional",
            surface_type="Transitional",
            footprint=QgsGeometry(tapered_domain),
            elevation_at_xy=constant_elevation_evaluator(110.0),
            model="constant",
        )
        baseline_engine = PlanarControllingOlsEngine([baseline])
        future_engine = PlanarControllingOlsEngine([future])
        baseline_engine._controlling_region_geometries_cache = [
            (baseline, QgsGeometry(tapered_domain))
        ]
        future_engine._controlling_region_geometries_cache = [
            (future, QgsGeometry(tapered_domain))
        ]
        engine = OlsEnvelopeComparisonEngine(baseline_engine, future_engine)

        self.assertTrue(tapered_domain.isGeosValid())
        self.assertFalse(engine._has_area(
            engine._clean_comparison_part(tapered_domain, baseline, future, "gain")
        ))
        parts = engine.comparison_parts()

        self.assertEqual(len(parts["gain"]), 1)
        self.assertEqual(len(parts["loss"]), 0)
        self.assertEqual(len(parts["no_change"]), 0)
        self.assertAlmostEqual(parts["gain"][0][2].area(), tapered_domain.area(), places=3)

    def test_delta_range_rounds_to_published_precision(self):
        baseline = self.constant("baseline", 100.0)
        future = self.constant("future", 100.000000523)
        engine = OlsEnvelopeComparisonEngine(
            PlanarControllingOlsEngine([baseline]),
            PlanarControllingOlsEngine([future]),
        )

        delta_min, delta_max, delta_rep = engine.delta_range(self.domain, baseline, future)
        self.assertEqual(delta_min, 0.0)
        self.assertEqual(delta_max, 0.0)
        self.assertEqual(delta_rep, 0.0)

    def test_gap_part_classification_does_not_require_preselected_change(self):
        baseline = self.constant("baseline", 100.0)
        future = self.constant("future", 90.0)
        engine = OlsEnvelopeComparisonEngine(
            PlanarControllingOlsEngine([baseline]),
            PlanarControllingOlsEngine([future]),
        )

        self.assertEqual(engine._classify_change_for_part(self.domain, baseline, future), "loss")


if __name__ == "__main__":
    unittest.main()
