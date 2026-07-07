import unittest

from qgis.core import QgsGeometry, QgsRectangle

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
        self.assertAlmostEqual(parts[0][1].area(), 4950.0, delta=1.0)

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


if __name__ == "__main__":
    unittest.main()
