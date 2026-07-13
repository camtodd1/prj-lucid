import math
import unittest
from unittest.mock import patch

from qgis.core import QgsGeometry, QgsPointXY, QgsRectangle

from guidelines.controlling_ols_engine import (
    ControllingOlsCandidate,
    PlanarControllingOlsEngine,
    axis_elevation_evaluator,
    conical_elevation_evaluator,
    constant_elevation_evaluator,
    plane_elevation_evaluator,
)
from guidelines.ols_modernisation_comparison import (
    OlsEnvelopeComparisonEngine,
    OlsModernisationComparisonMixin,
)


class _ComparisonLayerCapture(OlsModernisationComparisonMixin):
    def __init__(self):
        self.layers = []

    @staticmethod
    def tr(value):
        return value

    def _create_and_add_layer(self, *args):
        self.layers.append(args)
        return object()


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
        no_change_area = sum(part[2].area() for part in parts["no_change"])
        self.assertAlmostEqual(gain_area, 5000.0, delta=1.0)
        self.assertAlmostEqual(loss_area, 5000.0, delta=1.0)
        self.assertAlmostEqual(no_change_area, 0.0, delta=1e-6)
        self.assertGreater(sum(part[2].length() for part in parts["transition"]), 0.0)

    def test_equal_height_line_does_not_create_a_no_change_strip(self):
        baseline = self.constant("baseline", 100.0)
        future = self.plane("future", 0.142857, 0.0, 92.85715)

        parts = self.compare(baseline, future)

        self.assertEqual(parts["no_change"], [])
        self.assertAlmostEqual(
            sum(part[2].area() for part in parts["gain"]),
            5000.0,
            delta=1.0,
        )
        self.assertAlmostEqual(
            sum(part[2].area() for part in parts["loss"]),
            5000.0,
            delta=1.0,
        )

    def test_diagnostics_classify_recovery_and_normalisation(self):
        engine = PlanarControllingOlsEngine([self.constant("surface", 100.0)])
        engine._controlling_region_geometries()

        diagnostics = engine.solver_diagnostics()

        self.assertEqual(diagnostics["solver"], "global_cell")
        self.assertEqual(diagnostics["cells"]["unassigned"], 0)
        self.assertEqual(
            diagnostics["operation_classes"]["same_controller_dissolve"],
            "canonical_normalisation",
        )

    def test_transition_topology_uses_shared_region_adjacency(self):
        left_domain = QgsGeometry.fromRect(QgsRectangle(0.0, 0.0, 50.0, 100.0))
        right_domain = QgsGeometry.fromRect(QgsRectangle(50.0, 0.0, 100.0, 100.0))
        left = ControllingOlsCandidate(
            "left", "Left", left_domain, constant_elevation_evaluator(100.0), "constant"
        )
        right = ControllingOlsCandidate(
            "right", "Right", right_domain, constant_elevation_evaluator(100.0), "constant"
        )
        engine = PlanarControllingOlsEngine([left, right])
        engine._controlling_region_geometries_cache = [
            (left, QgsGeometry(left_domain)),
            (right, QgsGeometry(right_domain)),
        ]

        with patch.object(engine, "_controllers_across_segment", side_effect=AssertionError):
            records = engine._adjacency_region_boundary_records(
                engine._controlling_region_geometries_cache
            )

        self.assertTrue(records)
        self.assertTrue(all(record[1][-1] == "cell_adjacency_boundary" for record in records))

    def test_mos_tocs_conical_overlap_is_assigned_once(self):
        conical = ControllingOlsCandidate(
            "conical", "Conical", QgsGeometry.fromRect(QgsRectangle(40, 0, 100, 100)),
            constant_elevation_evaluator(110.0), "conical",
        )
        tocs = ControllingOlsCandidate(
            "tocs", "TOCS", QgsGeometry.fromRect(QgsRectangle(0, 0, 60, 100)),
            constant_elevation_evaluator(100.0), "axis",
        )
        engine = PlanarControllingOlsEngine([tocs, conical])
        regions = engine._enforce_exclusive_merged_regions([
            (tocs, QgsGeometry(tocs.footprint)),
            (conical, QgsGeometry(conical.footprint)),
        ])

        self.assertEqual(len(regions), 2)
        self.assertAlmostEqual(regions[0][1].intersection(regions[1][1]).area(), 0.0, places=6)
        self.assertAlmostEqual(regions[0][1].area(), 6000.0, places=6)
        self.assertAlmostEqual(regions[1][1].area(), 4000.0, places=6)

    def test_one_sided_surface_with_tolerance_edge_is_entirely_gain(self):
        baseline = self.constant("baseline", 100.0)
        future = self.plane("future", 0.001, 0.0, 100.005)

        parts = self.compare(baseline, future)

        self.assertEqual(parts["no_change"], [])
        self.assertEqual(parts["loss"], [])
        self.assertAlmostEqual(
            sum(part[2].area() for part in parts["gain"]),
            self.domain.area(),
            places=3,
        )

    def test_equal_surfaces_emit_no_change(self):
        parts = self.compare(self.constant("baseline", 100.0), self.constant("future", 100.0))
        self.assertEqual(len(parts["gain"]), 0)
        self.assertEqual(len(parts["loss"]), 0)
        self.assertEqual(len(parts["transition"]), 0)
        self.assertEqual(len(parts["no_change"]), 1)
        self.assertAlmostEqual(parts["no_change"][0][2].area(), 10000.0, places=3)

    def test_post_merge_coverage_repair_restores_trimmed_domain(self):
        baseline = self.constant("baseline", 100.0)
        future = self.constant("future", 110.0)
        engine = OlsEnvelopeComparisonEngine(
            PlanarControllingOlsEngine([baseline]),
            PlanarControllingOlsEngine([future]),
        )
        original_merge = engine._merge_classified_parts

        def trim_after_merge(result):
            original_merge(result)
            result["gain"] = []

        with patch.object(engine, "_merge_classified_parts", side_effect=trim_after_merge):
            parts = engine.comparison_parts()

        self.assertAlmostEqual(
            sum(part[2].area() for part in parts["gain"]),
            self.domain.area(),
            places=3,
        )

    def test_same_class_repair_overlap_is_partitioned(self):
        baseline = self.constant("baseline", 100.0)
        future = self.constant("future", 110.0)
        engine = OlsEnvelopeComparisonEngine(
            PlanarControllingOlsEngine([baseline]),
            PlanarControllingOlsEngine([future]),
        )
        result = {
            "gain": [
                (baseline, future, QgsGeometry(self.domain)),
                (baseline, future, QgsGeometry(self.domain)),
            ],
            "loss": [],
            "no_change": [],
            "transition": [],
        }

        engine._partition_classified_parts(result)

        self.assertEqual(len(result["gain"]), 1)
        self.assertAlmostEqual(result["gain"][0][2].area(), self.domain.area(), places=3)

    def test_tolerance_band_owns_numerical_cross_class_overlap(self):
        baseline = self.constant("baseline", 100.0)
        future = self.constant("future", 110.0)
        engine = OlsEnvelopeComparisonEngine(
            PlanarControllingOlsEngine([baseline]),
            PlanarControllingOlsEngine([future]),
        )
        result = {
            "gain": [(baseline, future, QgsGeometry(self.domain))],
            "loss": [],
            "no_change": [(baseline, future, QgsGeometry(self.domain))],
            "transition": [],
        }

        engine._partition_classified_parts(result)

        self.assertEqual(len(result["no_change"]), 1)
        self.assertEqual(result["gain"], [])

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

        raw_min, raw_max, _raw_sample = engine.delta_range(spiked_loss, baseline, future)
        self.assertAlmostEqual(raw_min, -50.0, places=3)
        self.assertAlmostEqual(raw_max, 10.0, places=3)

        loss_min, loss_max, loss_sample = engine.delta_range(spiked_loss, baseline, future, "loss")
        self.assertAlmostEqual(loss_min, -50.0, places=3)
        self.assertEqual(loss_max, 0.0)
        self.assertLess(loss_sample, 0.0)

        cleaned = engine._clean_comparison_part(spiked_loss, baseline, future, "loss")
        cleaned_vertices = [(round(vertex.x(), 3), round(vertex.y(), 3)) for vertex in cleaned.vertices()]
        self.assertNotIn((40.0, 50.0), cleaned_vertices)
        cleaned_min, cleaned_max, cleaned_sample = engine.delta_range(
            cleaned,
            baseline,
            future,
            "loss",
        )
        self.assertAlmostEqual(cleaned_min, -50.0, places=3)
        self.assertEqual(cleaned_max, 0.0)
        self.assertLess(cleaned_sample, 0.0)

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

    def test_cleanup_removes_long_collinear_wrong_side_backtracks(self):
        """Regression for the zero-area tendrils observed in the YSWS OES loss output."""
        footprint = QgsGeometry.fromRect(QgsRectangle(-400.0, 0.0, 400.0, 700.0))
        baseline = ControllingOlsCandidate(
            surface_id="baseline-transitional",
            surface_type="Transitional",
            footprint=footprint,
            elevation_at_xy=constant_elevation_evaluator(0.0),
            model="constant",
            metadata={"elevation_m": 0.0},
        )
        future = ControllingOlsCandidate(
            surface_id="future-transitional",
            surface_type="Precision Approach",
            footprint=footprint,
            elevation_at_xy=plane_elevation_evaluator(
                0.00430694973574651,
                0.00264455906691988,
                -0.9112100789025135,
            ),
            model="plane",
            metadata={
                "plane_a": 0.00430694973574651,
                "plane_b": 0.00264455906691988,
                "plane_c": -0.9112100789025135,
            },
        )
        spiked_loss = QgsGeometry.fromPolygonXY([[
            QgsPointXY(76.6874097953, 219.6665851884),
            QgsPointXY(166.0694389999, 274.5490589999),
            QgsPointXY(-164.4281789796, 71.6164670130),
            QgsPointXY(-276.9461980000, 254.8641999997),
            QgsPointXY(293.0971557299, 633.2413809653),
            QgsPointXY(-41.0631547095, 411.4360824255),
            QgsPointXY(76.6874097953, 219.6665851884),
        ]])
        engine = OlsEnvelopeComparisonEngine(
            PlanarControllingOlsEngine([baseline]),
            PlanarControllingOlsEngine([future]),
        )

        raw_deltas = [
            future.elevation_at_xy(QgsPointXY(vertex.x(), vertex.y()))
            - baseline.elevation_at_xy(QgsPointXY(vertex.x(), vertex.y()))
            for vertex in spiked_loss.vertices()
        ]
        self.assertGreater(max(raw_deltas), engine.tolerance_m)

        cleaned = engine._clean_comparison_part(spiked_loss, baseline, future, "loss")
        cleaned_deltas = [
            future.elevation_at_xy(QgsPointXY(vertex.x(), vertex.y()))
            - baseline.elevation_at_xy(QgsPointXY(vertex.x(), vertex.y()))
            for vertex in cleaned.vertices()
        ]
        self.assertTrue(cleaned.isGeosValid())
        self.assertLessEqual(max(cleaned_deltas), engine.tolerance_m)
        self.assertAlmostEqual(cleaned.area(), spiked_loss.area(), places=3)

    def test_final_merge_clips_non_collinear_wrong_side_loss_area(self):
        """A final loss feature must satisfy its height sign, regardless of spike shape."""
        footprint = QgsGeometry.fromRect(QgsRectangle(-30.0, -5.0, 20.0, 15.0))
        baseline = ControllingOlsCandidate(
            surface_id="baseline",
            surface_type="Baseline",
            footprint=footprint,
            elevation_at_xy=constant_elevation_evaluator(0.0),
            model="constant",
            metadata={"elevation_m": 0.0},
        )
        future = ControllingOlsCandidate(
            surface_id="future",
            surface_type="Future",
            footprint=footprint,
            elevation_at_xy=plane_elevation_evaluator(1.0, 0.0, 0.0),
            model="plane",
            metadata={"plane_a": 1.0, "plane_b": 0.0, "plane_c": 0.0},
        )
        mixed_loss = QgsGeometry.fromPolygonXY([[
            QgsPointXY(-20.0, 0.0),
            QgsPointXY(-10.0, 0.0),
            QgsPointXY(10.0, 5.0),
            QgsPointXY(-10.0, 10.0),
            QgsPointXY(-20.0, 10.0),
            QgsPointXY(-20.0, 0.0),
        ]])
        engine = OlsEnvelopeComparisonEngine(
            PlanarControllingOlsEngine([baseline]),
            PlanarControllingOlsEngine([future]),
        )
        result = {
            "gain": [],
            "loss": [(baseline, future, mixed_loss)],
            "no_change": [],
            "transition": [],
        }

        engine._merge_classified_parts(result)

        self.assertEqual(len(result["loss"]), 1)
        corrected = result["loss"][0][2]
        self.assertTrue(corrected.isGeosValid())
        self.assertLess(corrected.area(), mixed_loss.area())
        deltas = [
            future.elevation_at_xy(QgsPointXY(vertex.x(), vertex.y()))
            - baseline.elevation_at_xy(QgsPointXY(vertex.x(), vertex.y()))
            for vertex in corrected.vertices()
        ]
        self.assertLessEqual(max(deltas), engine.tolerance_m)

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

    def test_comparison_repairs_invalid_controller_region_before_overlay(self):
        invalid_region = QgsGeometry.fromPolygonXY([[
            QgsPointXY(0.0, 0.0),
            QgsPointXY(100.0, 100.0),
            QgsPointXY(0.0, 100.0),
            QgsPointXY(100.0, 0.0),
            QgsPointXY(0.0, 0.0),
        ]])
        baseline = self.constant("baseline", 100.0)
        future = self.constant("future", 110.0)
        baseline_engine = PlanarControllingOlsEngine([baseline])
        future_engine = PlanarControllingOlsEngine([future])
        baseline_engine._controlling_region_geometries_cache = [(baseline, invalid_region)]
        future_engine._controlling_region_geometries_cache = [(future, self.domain)]

        result = OlsEnvelopeComparisonEngine(baseline_engine, future_engine).comparison_parts()

        gain_union = QgsGeometry.unaryUnion([item[2] for item in result["gain"]])
        self.assertFalse(gain_union.isEmpty())
        self.assertTrue(gain_union.isGeosValid())
        self.assertAlmostEqual(gain_union.area(), 5000.0, places=3)

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

        delta_min, delta_max, delta_sample = engine.delta_range(self.domain, baseline, future)
        self.assertEqual(delta_min, 0.0)
        self.assertEqual(delta_max, 0.0)
        self.assertEqual(delta_sample, 0.0)

    def test_change_contours_are_signed_clipped_isolines_and_omit_zero(self):
        baseline = self.constant("baseline", 100.0)
        future = self.plane("future", 0.02, 0.0, 100.0)
        engine = OlsEnvelopeComparisonEngine(
            PlanarControllingOlsEngine([baseline]),
            PlanarControllingOlsEngine([future]),
        )

        contours = engine.change_contour_parts(
            [(baseline, future, self.domain)],
            "gain",
        )

        self.assertEqual([item[3] for item in contours], [0.5, 1.0, 1.5, 2.0])
        self.assertEqual([item[4] for item in contours], ["intermediate", "primary", "intermediate", "primary"])
        for _baseline, _future, geometry, delta_m, _contour_class, parent_sequence in contours:
            self.assertEqual(parent_sequence, 1)
            self.assertGreater(geometry.length(), 99.9)
            for vertex in geometry.vertices():
                self.assertAlmostEqual(vertex.x(), delta_m / 0.02, places=5)

    def test_affine_change_contour_lines_are_reused_by_pair_and_level(self):
        baseline = self.constant("baseline", 100.0)
        future = self.plane("future", 0.02, 0.0, 100.0)
        lower = QgsGeometry.fromRect(QgsRectangle(0.0, 0.0, 100.0, 50.0))
        upper = QgsGeometry.fromRect(QgsRectangle(0.0, 50.0, 100.0, 100.0))
        engine = OlsEnvelopeComparisonEngine(
            PlanarControllingOlsEngine([baseline]),
            PlanarControllingOlsEngine([future]),
        )

        with patch.object(
            engine,
            "_affine_change_line",
            wraps=engine._affine_change_line,
        ) as line_builder:
            contours = engine.change_contour_parts(
                [(baseline, future, lower), (baseline, future, upper)],
                "gain",
            )

        self.assertEqual(line_builder.call_count, 4)
        self.assertEqual(len(contours), 8)
        self.assertEqual({item[5] for item in contours}, {1, 2})

    def test_curved_change_contour_uses_surface_evaluators(self):
        base = QgsGeometry.fromRect(QgsRectangle(40.0, 40.0, 60.0, 60.0))
        baseline = ControllingOlsCandidate(
            surface_id="baseline-conical",
            surface_type="Conical",
            footprint=QgsGeometry(self.domain),
            elevation_at_xy=conical_elevation_evaluator(base, 100.0, 0.05),
            model="conical",
            metadata={
                "base_footprint": base,
                "base_elevation_m": 100.0,
                "slope": 0.05,
            },
        )
        future = self.constant("future", 102.0)
        engine = OlsEnvelopeComparisonEngine(
            PlanarControllingOlsEngine([baseline]),
            PlanarControllingOlsEngine([future]),
        )

        contour = engine._change_contour_geometry(self.domain, baseline, future, 0.5)

        self.assertIsNotNone(contour)
        self.assertFalse(contour.isEmpty())
        self.assertGreater(contour.length(), 100.0)
        sampled_deltas = [
            future.elevation_at_xy(QgsPointXY(vertex.x(), vertex.y()))
            - baseline.elevation_at_xy(QgsPointXY(vertex.x(), vertex.y()))
            for vertex in contour.vertices()
        ]
        self.assertLessEqual(max(abs(value - 0.5) for value in sampled_deltas), 0.05)

    def test_comparison_labels_report_the_delta_range_not_the_interior_sample(self):
        capture = _ComparisonLayerCapture()

        self.assertEqual(
            capture._comparison_label("loss", -1.43, 0.0),
            "-1.4 to 0.0 m loss",
        )
        self.assertEqual(
            capture._comparison_label("gain", 0.0, 1.43),
            "0.0 to +1.4 m gain",
        )
        self.assertEqual(
            capture._comparison_label("no_change", -0.005, 0.005),
            "0.0 m no change",
        )

    def test_gap_part_classification_does_not_require_preselected_change(self):
        baseline = self.constant("baseline", 100.0)
        future = self.constant("future", 90.0)
        engine = OlsEnvelopeComparisonEngine(
            PlanarControllingOlsEngine([baseline]),
            PlanarControllingOlsEngine([future]),
        )

        self.assertEqual(engine._classify_change_for_part(self.domain, baseline, future), "loss")

    def test_gap_repair_partitions_remainder_by_controller_pair(self):
        left_domain = QgsGeometry.fromRect(QgsRectangle(0.0, 0.0, 50.0, 100.0))
        right_domain = QgsGeometry.fromRect(QgsRectangle(50.0, 0.0, 100.0, 100.0))
        baseline_left = ControllingOlsCandidate(
            surface_id="baseline-left",
            surface_type="Left",
            footprint=left_domain,
            elevation_at_xy=constant_elevation_evaluator(100.0),
            model="constant",
        )
        baseline_right = ControllingOlsCandidate(
            surface_id="baseline-right",
            surface_type="Right",
            footprint=right_domain,
            elevation_at_xy=constant_elevation_evaluator(120.0),
            model="constant",
        )
        future = self.constant("future", 110.0)
        baseline_engine = PlanarControllingOlsEngine([baseline_left, baseline_right])
        future_engine = PlanarControllingOlsEngine([future])
        baseline_regions = [
            (baseline_left, left_domain),
            (baseline_right, right_domain),
        ]
        future_regions = [(future, self.domain)]
        baseline_engine._controlling_region_geometries_cache = baseline_regions
        future_engine._controlling_region_geometries_cache = future_regions
        engine = OlsEnvelopeComparisonEngine(baseline_engine, future_engine)
        result = {"gain": [], "loss": [], "no_change": [], "transition": []}

        engine._append_common_domain_gap_parts(result, baseline_regions, future_regions)
        engine._merge_classified_parts(result)

        self.assertAlmostEqual(sum(item[2].area() for item in result["gain"]), 5000.0, places=3)
        self.assertAlmostEqual(sum(item[2].area() for item in result["loss"]), 5000.0, places=3)
        self.assertEqual(len(result["no_change"]), 0)
        self.assertEqual(result["gain"][0][0].surface_id, "baseline-left")
        self.assertEqual(result["loss"][0][0].surface_id, "baseline-right")

    def test_unresolved_mixed_overlap_uses_triangulated_fallback(self):
        baseline = self.constant("baseline", 100.0)
        future = self.plane("future", 0.2, 0.0, 90.0)
        baseline_engine = PlanarControllingOlsEngine([baseline])
        future_engine = PlanarControllingOlsEngine([future])
        baseline_engine._controlling_region_geometries_cache = [(baseline, self.domain)]
        future_engine._controlling_region_geometries_cache = [(future, self.domain)]
        engine = OlsEnvelopeComparisonEngine(baseline_engine, future_engine)

        with patch.object(engine, "_affine_change_regions", return_value=None):
            with patch.object(PlanarControllingOlsEngine, "_candidate_lower_region", return_value=None):
                result = engine.comparison_parts()

        gain_area = sum(item[2].area() for item in result["gain"])
        loss_area = sum(item[2].area() for item in result["loss"])
        self.assertAlmostEqual(gain_area, 5000.0, delta=2.0)
        self.assertAlmostEqual(loss_area, 5000.0, delta=2.0)
        self.assertAlmostEqual(gain_area + loss_area, self.domain.area(), delta=2.0)

    def test_region_boundary_records_are_reused_across_output_layers(self):
        baseline = self.constant("baseline", 100.0)
        future = self.plane("future", 0.2, 0.0, 90.0)
        engine = PlanarControllingOlsEngine([baseline, future])

        with patch.object(
            engine,
            "_controllers_across_segment",
            wraps=engine._controllers_across_segment,
        ) as controller_probe:
            first = engine._region_boundary_records()
            first_call_count = controller_probe.call_count
            second = engine._region_boundary_records()

        self.assertTrue(first)
        self.assertIs(first, second)
        self.assertGreater(first_call_count, 0)
        self.assertEqual(controller_probe.call_count, first_call_count)

    def test_shared_region_edge_controller_probe_is_reused(self):
        left_geometry = QgsGeometry.fromRect(QgsRectangle(0.0, 0.0, 50.0, 100.0))
        right_geometry = QgsGeometry.fromRect(QgsRectangle(50.0, 0.0, 100.0, 100.0))
        left = ControllingOlsCandidate(
            surface_id="left",
            surface_type="Test",
            footprint=left_geometry,
            elevation_at_xy=constant_elevation_evaluator(90.0),
            model="constant",
            metadata={"elevation_m": 90.0},
        )
        right = ControllingOlsCandidate(
            surface_id="right",
            surface_type="Test",
            footprint=right_geometry,
            elevation_at_xy=constant_elevation_evaluator(100.0),
            model="constant",
            metadata={"elevation_m": 100.0},
        )
        engine = PlanarControllingOlsEngine([left, right])
        engine._controlling_region_geometries_cache = [
            (left, left_geometry),
            (right, right_geometry),
        ]

        with patch.object(
            engine,
            "_controllers_across_segment",
            return_value=(left, right),
        ) as controller_probe:
            records = engine._region_boundary_records()

        self.assertEqual(controller_probe.call_count, 7)
        self.assertLess(len(records), controller_probe.call_count)
        self.assertTrue(all(record[1][5] == "region_boundary_merged" for record in records))

    def test_axis_conical_output_uses_smooth_equal_height_curve(self):
        base = QgsGeometry.fromRect(QgsRectangle(0.0, 0.0, 100.0, 100.0))
        overlap = QgsGeometry.fromRect(QgsRectangle(100.0, 100.0, 150.0, 150.0))
        origin = QgsPointXY(100.0, 100.0)
        axis = ControllingOlsCandidate(
            "axis",
            "Approach",
            overlap,
            axis_elevation_evaluator(origin, 90.0, 101.0, 0.02, 100.0),
            "axis",
            {
                "origin_x": 100.0,
                "origin_y": 100.0,
                "origin_elevation_m": 101.0,
                "slope": 0.02,
                "max_distance_m": 100.0,
                "azimuth_degrees": 90.0,
            },
        )
        conical = ControllingOlsCandidate(
            "conical",
            "Conical",
            overlap,
            conical_elevation_evaluator(base, 100.0, 0.05, 100.0),
            "conical",
            {
                "base_footprint": base,
                "base_elevation_m": 100.0,
                "slope": 0.05,
                "max_distance_m": 100.0,
            },
        )
        engine = PlanarControllingOlsEngine([axis, conical])
        sampled_reference = engine._axis_conical_transition_curve(
            engine._axis_model(axis),
            engine._conical_model(conical),
            overlap,
        )
        curves = engine._axis_conical_output_transition_lines(
            axis,
            conical,
            sampled_reference,
        )

        self.assertTrue(curves)
        residuals = []
        shared_elevations = []
        maximum_turn = 0.0
        for curve in curves:
            sampled = curve.densifyByDistance(1.0)
            for points in engine._line_parts(sampled):
                for point in points:
                    axis_z = axis.elevation_at_xy(point)
                    conical_z = conical.elevation_at_xy(point)
                    self.assertIsNotNone(axis_z)
                    self.assertIsNotNone(conical_z)
                    residuals.append(abs(axis_z - conical_z))
                    shared_elevations.append((axis_z + conical_z) / 2.0)
            for points in engine._line_parts(curve):
                for previous, current, following in zip(points[:-2], points[1:-1], points[2:]):
                    first_dx = current.x() - previous.x()
                    first_dy = current.y() - previous.y()
                    second_dx = following.x() - current.x()
                    second_dy = following.y() - current.y()
                    first_length = (first_dx * first_dx + first_dy * first_dy) ** 0.5
                    second_length = (second_dx * second_dx + second_dy * second_dy) ** 0.5
                    if first_length <= 1e-9 or second_length <= 1e-9:
                        continue
                    cosine = max(
                        -1.0,
                        min(
                            1.0,
                            ((first_dx * second_dx) + (first_dy * second_dy))
                            / (first_length * second_length),
                        ),
                    )
                    maximum_turn = max(maximum_turn, math.degrees(math.acos(cosine)))

        self.assertLess(max(residuals), 0.01)
        self.assertLess(maximum_turn, 15.0)
        self.assertGreater(max(shared_elevations) - min(shared_elevations), 0.1)

    def test_axis_conical_chord_error_does_not_create_second_cell_boundary(self):
        axis = ControllingOlsCandidate(
            "axis", "Approach", self.domain,
            constant_elevation_evaluator(100.0), "axis",
        )
        conical = ControllingOlsCandidate(
            "conical", "Conical", self.domain,
            constant_elevation_evaluator(100.05), "conical",
        )
        engine = PlanarControllingOlsEngine([axis, conical])
        point = QgsPointXY(50.0, 50.0)

        with patch.object(engine, "_global_cell_validation_points", return_value=[point]):
            with patch.object(engine, "controlling_candidate_at_xy", return_value=(conical, 100.05)):
                candidates = engine._global_cell_refinement_candidates(self.domain, axis)

        self.assertEqual(candidates, [])
        self.assertEqual(engine._region_solve_stats["axis_conical_chord_refinement_suppressed"], 1.0)

    def test_region_owned_edge_only_probes_the_opposite_side(self):
        left_geometry = QgsGeometry.fromRect(QgsRectangle(0.0, 0.0, 50.0, 100.0))
        left = ControllingOlsCandidate(
            surface_id="left",
            surface_type="Test",
            footprint=left_geometry,
            elevation_at_xy=constant_elevation_evaluator(90.0),
            model="constant",
        )
        right = self.constant("right", 100.0)
        engine = PlanarControllingOlsEngine([left, right])

        with patch.object(
            engine,
            "controlling_candidate_at_xy",
            return_value=(right, 100.0),
        ) as controller_probe:
            controllers = engine._controllers_across_segment(
                QgsPointXY(50.0, 0.0),
                QgsPointXY(50.0, 100.0),
                known_candidate=left,
                known_region=left_geometry,
            )

        self.assertEqual(controllers, (left, right))
        self.assertEqual(controller_probe.call_count, 1)

    def test_candidate_spatial_index_is_an_exact_query_prefilter(self):
        near = self.constant("near", 90.0)
        far_footprint = QgsGeometry.fromRect(QgsRectangle(1000.0, 1000.0, 1100.0, 1100.0))
        far = ControllingOlsCandidate(
            surface_id="far",
            surface_type="Test",
            footprint=far_footprint,
            elevation_at_xy=constant_elevation_evaluator(10.0),
            model="constant",
            metadata={"elevation_m": 10.0},
        )
        engine = PlanarControllingOlsEngine([far, near])

        candidates = engine._candidates_intersecting_rectangle(
            QgsRectangle(49.0, 49.0, 51.0, 51.0)
        )
        controller = engine.controlling_candidate_at_xy(QgsPointXY(50.0, 50.0))

        self.assertEqual([candidate.surface_id for candidate in candidates], ["near"])
        self.assertIsNotNone(controller)
        self.assertEqual(controller[0].surface_id, "near")

    def test_candidate_spatial_index_keeps_exact_footprint_boundary_points(self):
        candidate = self.constant("boundary", 90.0)
        engine = PlanarControllingOlsEngine([candidate])

        controller = engine.controlling_candidate_at_xy(QgsPointXY(100.0, 50.0))

        self.assertIsNotNone(controller)
        self.assertEqual(controller[0].surface_id, "boundary")

    def test_comparison_reuses_supplied_solved_engines(self):
        baseline = self.constant("baseline", 100.0)
        future = ControllingOlsCandidate(
            surface_id="future-ofs",
            surface_type="Future OFS",
            footprint=QgsGeometry(self.domain),
            elevation_at_xy=constant_elevation_evaluator(110.0),
            model="constant",
            metadata={"elevation_m": 110.0, "annex14_family": "OFS"},
        )
        baseline_engine = PlanarControllingOlsEngine([baseline])
        future_engine = PlanarControllingOlsEngine([future])
        capture = _ComparisonLayerCapture()
        created_engine_sizes = []
        real_engine = PlanarControllingOlsEngine

        def create_engine(candidates, *args, **kwargs):
            candidate_list = list(candidates)
            created_engine_sizes.append(len(candidate_list))
            return real_engine(candidate_list, *args, **kwargs)

        with patch(
            "guidelines.ols_modernisation_comparison.PlanarControllingOlsEngine",
            side_effect=create_engine,
        ):
            created = capture._create_ols_modernisation_comparison_layers(
                "TEST",
                "baseline-rules",
                [baseline],
                [],
                [future],
                object(),
                object(),
                solved_baseline_engine=baseline_engine,
                solved_future_engines={"OFS": future_engine},
            )

        self.assertTrue(created)
        self.assertNotIn(1, created_engine_sizes)

    def test_all_comparison_output_features_receive_unique_ids(self):
        baseline = self.constant("baseline", 100.0)
        future = self.constant("future", 110.0)
        comparison = OlsEnvelopeComparisonEngine(
            PlanarControllingOlsEngine([baseline]),
            PlanarControllingOlsEngine([future]),
        )
        capture = _ComparisonLayerCapture()
        change_parts = [(baseline, future, self.domain)]

        capture._create_modernisation_change_layer(
            "TEST", "baseline-rules", "OFS", "gain", "Height Gain",
            change_parts, comparison, object(),
        )
        capture._create_modernisation_wireframe_layer(
            "TEST", "baseline-rules", "OFS", "baseline", "Baseline OLS Wireframe",
            [(baseline, self.domain)], object(),
        )
        contour_geometry = QgsGeometry.fromPolylineXY(
            [QgsPointXY(0.0, 50.0), QgsPointXY(100.0, 50.0)]
        )
        capture._create_modernisation_change_contour_layer(
            "TEST",
            "baseline-rules",
            "OFS",
            [("gain", baseline, future, contour_geometry, 10.0, "primary", 1)],
            object(),
        )
        capture._create_modernisation_transition_layer(
            "TEST", "baseline-rules", "OFS", change_parts, comparison, object(),
        )
        capture._create_modernisation_baseline_only_layer(
            "TEST", "baseline-rules", "OFS", [(baseline, self.domain)], object(),
        )

        comparison_ids = []
        for layer_args in capture.layers:
            fields = layer_args[3]
            features = layer_args[4]
            self.assertIn("comparison_id", fields.names())
            comparison_ids.extend(feature["comparison_id"] for feature in features)
        change_fields = capture.layers[0][3]
        change_feature = capture.layers[0][4][0]
        self.assertIn("delta_sample_m", change_fields.names())
        self.assertNotIn("delta_rep_m", change_fields.names())
        self.assertEqual(change_feature["delta_sample_m"], 10.0)
        self.assertEqual(change_feature["label_txt"], "+10.0 m gain")
        contour_layer_args = next(
            layer_args for layer_args in capture.layers
            if "delta_m" in layer_args[3].names()
        )
        contour_fields = contour_layer_args[3]
        contour_feature = contour_layer_args[4][0]
        self.assertIn("delta_m", contour_fields.names())
        self.assertEqual(contour_feature["comparison_id"], "OFS-CHANGE-CONTOUR-000001")
        self.assertEqual(contour_feature["parent_id"], "OFS-GAIN-000001")
        self.assertEqual(contour_feature["label_txt"], "+10.0 m")
        self.assertEqual(len(comparison_ids), 5)
        self.assertEqual(len(set(comparison_ids)), 5)
        self.assertIn("OFS-GAIN-000001", comparison_ids)


if __name__ == "__main__":
    unittest.main()
