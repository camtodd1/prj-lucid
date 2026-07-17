import math
import unittest
from unittest.mock import patch

from qgis.PyQt.QtCore import QVariant
from qgis.core import (
    QgsFeature,
    QgsField,
    QgsFields,
    QgsGeometry,
    QgsLayerTreeGroup,
    QgsPointXY,
    QgsRectangle,
    QgsVectorLayer,
)

from guidelines.controlling_ols_engine import (
    CONTROLLING_ZERO_CONTOUR_SEED_TOLERANCE_M,
    ControllingOlsCandidate,
    ControllingOlsContour,
    ControllingOlsEngineMixin,
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


class _ControllingLayerCapture(ControllingOlsEngineMixin):
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

    def test_identical_axis_conical_envelopes_use_domain_stable_transition(self):
        base = QgsGeometry.fromRect(QgsRectangle(0.0, 0.0, 100.0, 100.0))
        origin = QgsPointXY(100.0, 100.0)
        baseline_domain = QgsGeometry.fromRect(
            QgsRectangle(100.0, 100.0, 250.0, 250.0)
        )
        comparison_domain = QgsGeometry.fromRect(
            QgsRectangle(90.0, 90.0, 250.0, 250.0)
        )

        def candidates(prefix, domain):
            axis = ControllingOlsCandidate(
                f"{prefix}-axis",
                "Approach",
                domain,
                axis_elevation_evaluator(
                    origin,
                    90.0,
                    105.0,
                    0.02,
                    150.0,
                ),
                "axis",
                {
                    "origin_x": 100.0,
                    "origin_y": 100.0,
                    "origin_elevation_m": 105.0,
                    "slope": 0.02,
                    "max_distance_m": 150.0,
                    "azimuth_degrees": 90.0,
                },
            )
            conical = ControllingOlsCandidate(
                f"{prefix}-conical",
                "Conical",
                domain,
                conical_elevation_evaluator(base, 100.0, 0.05, 200.0),
                "conical",
                {
                    "base_footprint": base,
                    "base_elevation_m": 100.0,
                    "slope": 0.05,
                    "max_distance_m": 200.0,
                },
            )
            return [axis, conical]

        comparison = OlsEnvelopeComparisonEngine(
            PlanarControllingOlsEngine(
                candidates("baseline", baseline_domain),
                ruleset_id="mos139_2019",
            ),
            PlanarControllingOlsEngine(
                candidates("comparison", comparison_domain),
                ruleset_id="uk_caa_cap168_edition_13",
            ),
        )

        parts = comparison.comparison_parts()

        self.assertEqual(parts["gain"], [])
        self.assertEqual(parts["loss"], [])
        self.assertTrue(parts["no_change"])
        self.assertTrue(all(
            baseline.surface_type == future.surface_type
            for baseline, future, _geometry in parts["no_change"]
        ))
        coverage = QgsGeometry.unaryUnion(
            [geometry for _baseline, _future, geometry in parts["no_change"]]
        )
        self.assertLessEqual(
            baseline_domain.symDifference(coverage).area(),
            0.01,
        )

    def test_axis_conical_exact_split_does_not_resimplify_canonical_curve(self):
        origin = QgsPointXY(0.0, 0.0)
        axis = ControllingOlsCandidate(
            "axis",
            "Approach",
            QgsGeometry(self.domain),
            axis_elevation_evaluator(origin, 90.0, 100.0, 0.02, 100.0),
            "axis",
            {
                "origin_x": 0.0,
                "origin_y": 0.0,
                "origin_elevation_m": 100.0,
                "slope": 0.02,
                "max_distance_m": 100.0,
                "azimuth_degrees": 90.0,
            },
        )
        conical = ControllingOlsCandidate(
            "conical",
            "Conical",
            QgsGeometry(self.domain),
            conical_elevation_evaluator(self.domain, 100.0, 0.05, 100.0),
            "conical",
            {
                "base_footprint": QgsGeometry(self.domain),
                "base_elevation_m": 100.0,
                "slope": 0.05,
                "max_distance_m": 100.0,
            },
        )
        engine = PlanarControllingOlsEngine([axis, conical])
        canonical_curve = QgsGeometry.fromPolylineXY(
            [QgsPointXY(50.0, 0.0), QgsPointXY(50.0, 100.0)]
        )

        with patch.object(
            engine,
            "_axis_conical_transition_curves_for_solver",
            return_value=[canonical_curve],
        ), patch.object(
            engine,
            "_candidate_lower_region_from_transition_curve",
            return_value=QgsGeometry(),
        ) as split:
            engine._axis_conical_exact_axis_lower_region(
                axis,
                conical,
                engine._axis_model(axis),
                self.domain,
            )

        self.assertEqual(split.call_count, 1)
        self.assertEqual(split.call_args.kwargs["simplify_tolerance_m"], 0.0)

    def test_zero_contour_seeding_is_independent_of_controller_tie_tolerance(self):
        candidate = self.constant("candidate", 100.0)
        exact = PlanarControllingOlsEngine([candidate], tie_tolerance_m=0.0)
        controller = PlanarControllingOlsEngine(
            [candidate],
            tie_tolerance_m=0.01,
        )
        points = [
            QgsPointXY(0.0, 0.0),
            QgsPointXY(1.0, 0.0),
            QgsPointXY(1.0, 1.0),
            QgsPointXY(0.0, 1.0),
        ]
        values = [0.005, 1.0, -1.0, -0.005]

        self.assertNotEqual(
            len(exact._zero_crossings_for_grid_cell(points, values)),
            len(controller._zero_crossings_for_grid_cell(points, values)),
        )
        exact_crossings = exact._zero_crossings_for_grid_cell(
            points,
            values,
            zero_tolerance_m=CONTROLLING_ZERO_CONTOUR_SEED_TOLERANCE_M,
        )
        controller_crossings = controller._zero_crossings_for_grid_cell(
            points,
            values,
            zero_tolerance_m=CONTROLLING_ZERO_CONTOUR_SEED_TOLERANCE_M,
        )

        self.assertEqual(
            [(point.x(), point.y()) for point in exact_crossings],
            [(point.x(), point.y()) for point in controller_crossings],
        )

    def test_conical_conical_comparison_uses_one_accurate_shared_transition(self):
        domain = QgsGeometry.fromRect(QgsRectangle(250.0, 100.0, 650.0, 900.0))
        baseline_base = QgsGeometry.fromPolylineXY(
            [QgsPointXY(100.0, 200.0), QgsPointXY(100.0, 800.0)]
        ).buffer(120.0, 48)
        future_base = QgsGeometry.fromPointXY(QgsPointXY(800.0, 500.0)).buffer(
            120.0, 48
        )
        baseline = ControllingOlsCandidate(
            "baseline-conical",
            "Conical",
            QgsGeometry(domain),
            conical_elevation_evaluator(baseline_base, 100.0, 0.05, 1200.0),
            "conical",
            {
                "base_footprint": baseline_base,
                "base_elevation_m": 100.0,
                "slope": 0.05,
                "max_distance_m": 1200.0,
            },
        )
        future = ControllingOlsCandidate(
            "future-conical",
            "Conical",
            QgsGeometry(domain),
            conical_elevation_evaluator(future_base, 100.3, 0.05, 1200.0),
            "conical",
            {
                "base_footprint": future_base,
                "base_elevation_m": 100.3,
                "slope": 0.05,
                "max_distance_m": 1200.0,
            },
        )
        pair_engine = PlanarControllingOlsEngine(
            [baseline, future],
            tie_tolerance_m=0.0,
        )

        equality = pair_engine._equality_line_for_pair(domain, baseline, future)

        self.assertIsNotNone(equality)
        self.assertFalse(equality.isEmpty())
        turns = []
        for points in pair_engine._line_parts(equality):
            for previous, current, following in zip(
                points[:-2], points[1:-1], points[2:]
            ):
                first_dx = current.x() - previous.x()
                first_dy = current.y() - previous.y()
                second_dx = following.x() - current.x()
                second_dy = following.y() - current.y()
                denominator = math.hypot(first_dx, first_dy) * math.hypot(
                    second_dx, second_dy
                )
                if denominator <= 1e-12:
                    continue
                cosine = max(
                    -1.0,
                    min(
                        1.0,
                        (
                            (first_dx * second_dx)
                            + (first_dy * second_dy)
                        )
                        / denominator,
                    ),
                )
                turns.append(math.degrees(math.acos(cosine)))
        self.assertTrue(turns)
        self.assertLess(max(turns), 1.0)
        comparison = OlsEnvelopeComparisonEngine(
            PlanarControllingOlsEngine(
                [baseline], ruleset_id="mos139_2019"
            ),
            PlanarControllingOlsEngine(
                [future], ruleset_id="uk_caa_cap168_edition_13"
            ),
        )
        parts = comparison.comparison_parts()
        self.assertEqual(
            comparison.comparison_diagnostics()["bounded_approximations"][
                "fallback_lower_region_calls"
            ],
            0,
        )
        self.assertTrue(parts["gain"])
        self.assertTrue(parts["loss"])
        self.assertTrue(parts["transition"])

        gain = QgsGeometry.unaryUnion([item[2] for item in parts["gain"]])
        loss = QgsGeometry.unaryUnion([item[2] for item in parts["loss"]])
        transitions = QgsGeometry.unaryUnion(
            [item[2] for item in parts["transition"]]
        )
        gain_boundary = QgsGeometry.unaryUnion(
            [
                QgsGeometry.fromPolylineXY(ring)
                for ring in pair_engine._polygon_boundary_parts(gain)
            ]
        )
        loss_boundary = QgsGeometry.unaryUnion(
            [
                QgsGeometry.fromPolylineXY(ring)
                for ring in pair_engine._polygon_boundary_parts(loss)
            ]
        )
        shared_boundary = gain_boundary.intersection(loss_boundary)
        coverage = gain.combine(loss)

        self.assertLessEqual(domain.symDifference(coverage).area(), 0.01)
        self.assertGreater(shared_boundary.length(), 500.0)
        self.assertAlmostEqual(
            shared_boundary.length(), transitions.length(), delta=0.05
        )
        self.assertLessEqual(shared_boundary.hausdorffDistance(transitions), 0.01)

        residuals = []
        sampled = transitions.densifyByDistance(1.0)
        for point in sampled.vertices():
            point_xy = QgsPointXY(point.x(), point.y())
            residuals.append(
                abs(
                    baseline.elevation_at_xy(point_xy)
                    - future.elevation_at_xy(point_xy)
                )
            )
        self.assertTrue(residuals)
        self.assertLessEqual(max(residuals), 0.01)

    def test_final_conical_remainder_is_split_at_zero_height(self):
        """Coverage repair must not classify a mixed-sign remainder as one side."""
        domain = QgsGeometry.fromRect(QgsRectangle(250.0, 100.0, 650.0, 900.0))
        baseline_base = QgsGeometry.fromPolylineXY(
            [QgsPointXY(100.0, 200.0), QgsPointXY(100.0, 800.0)]
        ).buffer(120.0, 48)
        future_base = QgsGeometry.fromPointXY(QgsPointXY(800.0, 500.0)).buffer(
            120.0, 48
        )
        baseline = ControllingOlsCandidate(
            "baseline-conical",
            "Conical",
            QgsGeometry(domain),
            conical_elevation_evaluator(baseline_base, 100.0, 0.05, 1200.0),
            "conical",
            {
                "base_footprint": baseline_base,
                "base_elevation_m": 100.0,
                "slope": 0.05,
                "max_distance_m": 1200.0,
            },
        )
        future = ControllingOlsCandidate(
            "future-conical",
            "Conical",
            QgsGeometry(domain),
            conical_elevation_evaluator(future_base, 100.3, 0.05, 1200.0),
            "conical",
            {
                "base_footprint": future_base,
                "base_elevation_m": 100.3,
                "slope": 0.05,
                "max_distance_m": 1200.0,
            },
        )
        engine = OlsEnvelopeComparisonEngine(
            PlanarControllingOlsEngine([baseline]),
            PlanarControllingOlsEngine([future]),
        )
        result = {"gain": [], "loss": [], "no_change": [], "transition": []}

        engine._append_final_common_domain_remainders(
            result,
            [(baseline, domain)],
            [(future, domain)],
        )

        self.assertTrue(result["gain"])
        self.assertTrue(result["loss"])
        self.assertTrue(result["transition"])
        coverage = QgsGeometry.unaryUnion(
            [item[2] for change in ("gain", "loss") for item in result[change]]
        )
        self.assertLessEqual(domain.symDifference(coverage).area(), 0.01)
        for _baseline, _future, geometry in result["gain"]:
            delta_min, _delta_max, _sample = engine.delta_range(
                geometry, baseline, future, "gain"
            )
            self.assertGreaterEqual(delta_min, -0.01)
        for _baseline, _future, geometry in result["loss"]:
            _delta_min, delta_max, _sample = engine.delta_range(
                geometry, baseline, future, "loss"
            )
            self.assertLessEqual(delta_max, 0.01)

        repaired = {
            "gain": [],
            "loss": [(baseline, future, QgsGeometry(domain))],
            "no_change": [],
            "transition": [],
        }
        engine._enforce_final_height_signs(repaired)
        self.assertTrue(repaired["gain"])
        self.assertTrue(repaired["loss"])
        repaired_coverage = QgsGeometry.unaryUnion(
            [item[2] for change in ("gain", "loss") for item in repaired[change]]
        )
        self.assertLessEqual(domain.symDifference(repaired_coverage).area(), 0.01)
        self.assertTrue(repaired["transition"])

    def test_conical_conical_regularisation_removes_sampling_wave(self):
        domain = QgsGeometry.fromRect(QgsRectangle(0.0, 10.0, 100.0, 90.0))
        first_base = QgsGeometry.fromRect(QgsRectangle(-10.0, 0.0, 0.0, 100.0))
        second_base = QgsGeometry.fromRect(QgsRectangle(100.0, 0.0, 110.0, 100.0))
        first = ControllingOlsCandidate(
            "first-conical",
            "Conical",
            QgsGeometry(domain),
            conical_elevation_evaluator(first_base, 100.0, 0.05),
            "conical",
            {
                "base_footprint": first_base,
                "base_elevation_m": 100.0,
                "slope": 0.05,
            },
        )
        second = ControllingOlsCandidate(
            "second-conical",
            "Conical",
            QgsGeometry(domain),
            conical_elevation_evaluator(second_base, 100.0, 0.05),
            "conical",
            {
                "base_footprint": second_base,
                "base_elevation_m": 100.0,
                "slope": 0.05,
            },
        )
        sampled_wave = QgsGeometry.fromPolylineXY(
            [
                QgsPointXY(
                    50.0
                    if index in {0, 8}
                    else 50.5
                    if index % 2
                    else 49.5,
                    10.0 + index * 10.0,
                )
                for index in range(9)
            ]
        )
        engine = PlanarControllingOlsEngine([first, second])

        regularised = engine._smoothed_conical_conical_contour(
            sampled_wave,
            first,
            second,
            domain,
        )

        self.assertIsNotNone(regularised)
        points = [QgsPointXY(point.x(), point.y()) for point in regularised.vertices()]
        self.assertEqual(len(points), 2)
        self.assertTrue(all(abs(point.x() - 50.0) <= 1e-9 for point in points))
        self.assertLessEqual(
            engine._maximum_candidate_pair_curve_residual(
                regularised,
                first,
                second,
            ),
            0.01,
        )

    def test_conical_contour_uses_fair_fit_when_accurate_chord_is_too_distant(self):
        domain = QgsGeometry.fromRect(QgsRectangle(-10.0, -10.0, 110.0, 30.0))
        first = ControllingOlsCandidate(
            "first-conical",
            "Conical",
            QgsGeometry(domain),
            constant_elevation_evaluator(100.0),
            "conical",
        )
        second = ControllingOlsCandidate(
            "second-conical",
            "Conical",
            QgsGeometry(domain),
            constant_elevation_evaluator(100.0),
            "conical",
        )
        sampled = QgsGeometry.fromPolylineXY(
            [QgsPointXY(0.0, 0.0), QgsPointXY(50.0, 20.0), QgsPointXY(100.0, 0.0)]
        )
        guide_points = [
            QgsPointXY(0.0, 0.0),
            QgsPointXY(50.0, 10.0),
            QgsPointXY(100.0, 0.0),
        ]
        engine = PlanarControllingOlsEngine([first, second])

        with patch.object(
            engine,
            "_least_squares_bspline_guide_points",
            return_value=(guide_points, {}),
        ):
            regularised = engine._smoothed_conical_conical_contour(
                sampled,
                first,
                second,
                domain,
            )

        self.assertIsNotNone(regularised)
        points = [QgsPointXY(point.x(), point.y()) for point in regularised.vertices()]
        self.assertEqual(points, guide_points)

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

    def test_controlling_contours_clip_to_exact_region_without_buffer_overshoot(self):
        region = QgsGeometry.fromRect(QgsRectangle(0.0, 0.0, 100.0, 100.0))
        candidate = ControllingOlsCandidate(
            "transition",
            "Transitional",
            QgsGeometry(region),
            constant_elevation_evaluator(125.0),
            "constant",
        )
        engine = PlanarControllingOlsEngine([candidate])
        engine._controlling_region_geometries_cache = [
            (candidate, QgsGeometry(region))
        ]
        source = QgsGeometry.fromPolylineXY(
            [QgsPointXY(-10.0, 50.0), QgsPointXY(110.0, 50.0)]
        )
        contour = ControllingOlsContour(
            surface_id=candidate.surface_id,
            surface_type=candidate.surface_type,
            geometry=source,
            contour_elevation_m=125.0,
            source_layer="test",
        )

        for strict_clip in (False, True):
            with self.subTest(strict_clip=strict_clip):
                capture = _ControllingLayerCapture()
                created = capture._create_controlling_contour_layer(
                    "TEST",
                    None,
                    engine,
                    [contour],
                    strict_clip=strict_clip,
                )

                self.assertTrue(created)
                feature = capture.layers[0][4][0]
                clipped = feature.geometry()
                self.assertEqual(feature["method"], "clip_to_controlling_region")
                self.assertAlmostEqual(clipped.length(), 100.0, places=9)
                self.assertAlmostEqual(clipped.boundingBox().xMinimum(), 0.0, places=9)
                self.assertAlmostEqual(clipped.boundingBox().xMaximum(), 100.0, places=9)
                self.assertTrue(clipped.difference(region).isEmpty())

    def test_controlling_contours_recover_near_coincident_region_boundary(self):
        region = QgsGeometry.fromRect(QgsRectangle(0.0, 0.0, 100.0, 100.0))
        candidate = ControllingOlsCandidate(
            "approach",
            "Precision Approach",
            QgsGeometry(region),
            constant_elevation_evaluator(5.3),
            "constant",
        )
        engine = PlanarControllingOlsEngine([candidate])
        engine._controlling_region_geometries_cache = [(candidate, QgsGeometry(region))]
        contour = ControllingOlsContour(
            surface_id=candidate.surface_id,
            surface_type=candidate.surface_type,
            geometry=QgsGeometry.fromPolylineXY(
                [QgsPointXY(10.0, -0.01), QgsPointXY(90.0, -0.01)]
            ),
            contour_elevation_m=5.3,
            source_layer="test",
        )

        capture = _ControllingLayerCapture()
        self.assertTrue(
            capture._create_controlling_contour_layer("TEST", None, engine, [contour])
        )
        recovered = capture.layers[0][4][0].geometry()
        self.assertGreater(recovered.length(), 79.9)
        self.assertLess(recovered.length(), 80.1)
        self.assertAlmostEqual(recovered.boundingBox().yMinimum(), 0.0, places=9)
        self.assertAlmostEqual(recovered.boundingBox().yMaximum(), 0.0, places=9)
        self.assertTrue(recovered.difference(region).isEmpty())

    def test_controlling_contour_registration_rejects_null_elevation_edges(self):
        class _SourceFeature:
            @staticmethod
            def geometry():
                return QgsGeometry.fromPolylineXY(
                    [QgsPointXY(0.0, 0.0), QgsPointXY(100.0, 0.0)]
                )

            @staticmethod
            def attribute(name):
                return None if name == "contour_elev_am" else ""

        capture = _ControllingLayerCapture()
        capture._register_controlling_ols_contour(
            "transition",
            "Transitional",
            _SourceFeature(),
            "test",
        )
        self.assertEqual(capture._controlling_ols_contours, [])

    def test_change_contour_group_reconciliation_uses_feature_family(self):
        ofs_group = QgsLayerTreeGroup("OFS")
        oes_group = QgsLayerTreeGroup("OES")
        ofs_layer = QgsVectorLayer(
            "LineString?field=future_family:string&field=delta_m:double",
            "Change Contours",
            "memory",
        )
        feature = QgsFeature(ofs_layer.fields())
        feature.setGeometry(
            QgsGeometry.fromPolylineXY(
                [QgsPointXY(0.0, 0.0), QgsPointXY(100.0, 0.0)]
            )
        )
        feature.setAttributes(["OFS", 5.0])
        self.assertTrue(ofs_layer.dataProvider().addFeature(feature))

        # Reproduce the reported tree state: an OFS-attributed contour layer
        # has been reparented beneath the OES result group.
        oes_group.addLayer(ofs_layer)
        capture = _ComparisonLayerCapture()
        capture._reconcile_modernisation_change_contour_groups(
            {"OFS": ofs_group, "OES": oes_group}
        )

        self.assertEqual(len(ofs_group.children()), 1)
        self.assertEqual(len(oes_group.children()), 0)
        moved_layer = ofs_group.children()[0].layer()
        self.assertIs(moved_layer, ofs_layer)

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

    def test_final_exclusive_boundary_normalisation_removes_complementary_hairpins(self):
        shared_boundary = [
            QgsPointXY(50.0, 0.0),
            QgsPointXY(50.0, 40.0),
            QgsPointXY(49.995, 50.0),
            QgsPointXY(49.99475, 49.0),
            QgsPointXY(49.99, 60.0),
            QgsPointXY(50.0, 100.0),
        ]
        left_geometry = QgsGeometry.fromPolygonXY(
            [[
                QgsPointXY(0.0, 0.0),
                *shared_boundary,
                QgsPointXY(0.0, 100.0),
                QgsPointXY(0.0, 0.0),
            ]]
        )
        right_geometry = QgsGeometry.fromPolygonXY(
            [[
                QgsPointXY(100.0, 0.0),
                QgsPointXY(100.0, 100.0),
                *reversed(shared_boundary),
                QgsPointXY(100.0, 0.0),
            ]]
        )
        left = ControllingOlsCandidate(
            "left", "TOCS", left_geometry, constant_elevation_evaluator(100.0), "axis"
        )
        right = ControllingOlsCandidate(
            "right", "Conical", right_geometry, constant_elevation_evaluator(110.0), "conical"
        )
        engine = PlanarControllingOlsEngine([left, right])
        original_union = left_geometry.combine(right_geometry)

        normalised = engine._normalise_exclusive_region_boundaries(
            [(left, left_geometry), (right, right_geometry)]
        )

        self.assertEqual(len(normalised), 2)
        self.assertGreater(
            engine._region_solve_stats["exclusive_boundary_normalisation_count"],
            0.0,
        )
        self.assertLessEqual(
            engine._region_solve_stats["exclusive_boundary_coverage_change_m2"],
            0.01,
        )
        self.assertAlmostEqual(
            normalised[0][1].intersection(normalised[1][1]).area(),
            0.0,
            places=6,
        )
        normalised_union = normalised[0][1].combine(normalised[1][1])
        self.assertLessEqual(
            original_union.symDifference(normalised_union).area(),
            0.01,
        )
        for _candidate, geometry in normalised:
            for ring in engine._polygon_boundary_parts(geometry):
                for previous, current, following in zip(ring[:-2], ring[1:-1], ring[2:]):
                    first_dx = current.x() - previous.x()
                    first_dy = current.y() - previous.y()
                    second_dx = following.x() - current.x()
                    second_dy = following.y() - current.y()
                    denominator = math.hypot(first_dx, first_dy) * math.hypot(
                        second_dx,
                        second_dy,
                    )
                    if denominator <= 1e-12:
                        continue
                    cosine = max(
                        -1.0,
                        min(1.0, ((first_dx * second_dx) + (first_dy * second_dy)) / denominator),
                    )
                    self.assertLess(math.degrees(math.acos(cosine)), 150.0)

    def test_numeric_sliver_is_reclassified_to_verified_near_tie_controller(self):
        needle = QgsGeometry.fromRect(QgsRectangle(40.0, 49.99, 95.0, 50.01))
        assigned = ControllingOlsCandidate(
            "assigned",
            "Assigned Surface",
            needle,
            constant_elevation_evaluator(100.005),
            "plane",
            {
                "plane_a": 0.0,
                "plane_b": 0.0,
                "plane_c": 100.005,
                "annex14_family": "OES",
            },
        )
        controller = ControllingOlsCandidate(
            "controller",
            "Controller Surface",
            needle,
            constant_elevation_evaluator(100.0),
            "plane",
            {
                "plane_a": 0.0,
                "plane_b": 0.0,
                "plane_c": 100.0,
                "annex14_family": "OES",
            },
        )
        engine = PlanarControllingOlsEngine([assigned, controller])

        corrected = engine._reassign_numeric_sliver_parts([(assigned, needle)])

        self.assertEqual(corrected[0][0].surface_id, "controller")
        self.assertTrue(corrected[0][1].equals(needle))
        self.assertEqual(
            engine._region_solve_stats["numeric_sliver_reassigned_part_count"],
            1.0,
        )
        self.assertAlmostEqual(
            engine._region_solve_stats["numeric_sliver_reassigned_area_m2"],
            needle.area(),
            places=6,
        )

    def test_final_partition_preserves_an_existing_solved_narrow_region(self):
        fields = QgsFields(
            [
                QgsField("region_id", QVariant.Int),
                QgsField("surface_id", QVariant.String),
                QgsField("surface", QVariant.String),
                QgsField("elev_min", QVariant.Double),
                QgsField("elev_max", QVariant.Double),
            ]
        )
        main = QgsGeometry.fromRect(QgsRectangle(0.0, 0.0, 40.0, 100.0))
        needle = QgsGeometry.fromRect(QgsRectangle(40.0, 49.99, 95.0, 50.01))
        solved = QgsGeometry.unaryUnion([main, needle])
        candidate = ControllingOlsCandidate(
            "solved",
            "Solved Surface",
            solved,
            constant_elevation_evaluator(90.0),
            "plane",
            {
                "plane_a": 0.0,
                "plane_b": 0.0,
                "plane_c": 90.0,
                "annex14_family": "OES",
            },
        )
        competitor = ControllingOlsCandidate(
            "competitor",
            "Competitor Surface",
            needle,
            constant_elevation_evaluator(100.0),
            "plane",
            {
                "plane_a": 0.0,
                "plane_b": 0.0,
                "plane_c": 100.0,
                "annex14_family": "OES",
            },
        )
        engine = PlanarControllingOlsEngine([candidate, competitor])
        item = QgsFeature(fields)
        item.setAttributes(
            [1, candidate.surface_id, candidate.surface_type, 90.0, 90.0]
        )
        item.setGeometry(solved)

        corrected = engine._reassign_numeric_sliver_parts([(candidate, needle)])

        repaired = _ControllingLayerCapture()._repair_final_controlling_partition(
            [item], engine
        )

        self.assertEqual(corrected[0][0].surface_id, "solved")
        self.assertEqual(len(repaired), 1)
        self.assertAlmostEqual(repaired[0].geometry().area(), solved.area(), places=6)
        self.assertNotIn("repair_sliver_reassigned_part_count", engine._region_solve_stats)

    def test_final_partition_suppresses_numeric_line_spike(self):
        fields = QgsFields(
            [
                QgsField("region_id", QVariant.Int),
                QgsField("surface_id", QVariant.String),
                QgsField("surface", QVariant.String),
            ]
        )
        base = QgsGeometry.fromRect(QgsRectangle(0.0, 0.0, 40.0, 100.0))
        spike = QgsGeometry.fromRect(QgsRectangle(40.0, 49.995, 41.0, 50.005))
        coverage = QgsGeometry.unaryUnion([base, spike])
        candidate = ControllingOlsCandidate(
            "surface",
            "Surface",
            coverage,
            constant_elevation_evaluator(90.0),
            "plane",
            {"plane_a": 0.0, "plane_b": 0.0, "plane_c": 90.0},
        )
        engine = PlanarControllingOlsEngine([candidate])
        item = QgsFeature(fields)
        item.setAttributes([1, candidate.surface_id, candidate.surface_type])
        item.setGeometry(base)

        repaired = _ControllingLayerCapture()._repair_final_controlling_partition(
            [item], engine
        )

        self.assertEqual(len(repaired), 1)
        self.assertAlmostEqual(repaired[0].geometry().area(), base.area(), places=6)
        self.assertEqual(
            engine._region_solve_stats["repair_sliver_suppressed_part_count"],
            1.0,
        )

    def test_final_partition_retains_numeric_gap_closure(self):
        fields = QgsFields(
            [
                QgsField("region_id", QVariant.Int),
                QgsField("surface_id", QVariant.String),
                QgsField("surface", QVariant.String),
                QgsField("elev_min", QVariant.Double),
                QgsField("elev_max", QVariant.Double),
            ]
        )
        coverage = QgsGeometry.fromRect(QgsRectangle(0.0, 0.0, 100.0, 100.0))
        notch = QgsGeometry.fromRect(QgsRectangle(40.0, 99.99, 41.0, 100.0))
        solved = coverage.difference(notch)
        candidate = ControllingOlsCandidate(
            "surface",
            "Surface",
            coverage,
            constant_elevation_evaluator(90.0),
            "plane",
            {"plane_a": 0.0, "plane_b": 0.0, "plane_c": 90.0},
        )
        engine = PlanarControllingOlsEngine([candidate])
        item = QgsFeature(fields)
        item.setAttributes(
            [1, candidate.surface_id, candidate.surface_type, 90.0, 90.0]
        )
        item.setGeometry(solved)

        repaired = _ControllingLayerCapture()._repair_final_controlling_partition(
            [item], engine
        )

        self.assertEqual(len(repaired), 1)
        self.assertAlmostEqual(repaired[0].geometry().area(), coverage.area(), places=6)
        self.assertNotIn(
            "repair_sliver_suppressed_part_count",
            engine._region_solve_stats,
        )

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

    def test_recovery_sliver_reattaches_to_one_adjacent_part_only(self):
        baseline = self.constant("baseline", 100.0)
        future = self.constant("future", 99.0)
        comparison = OlsEnvelopeComparisonEngine(
            PlanarControllingOlsEngine([baseline]),
            PlanarControllingOlsEngine([future]),
        )
        target = QgsGeometry.fromRect(QgsRectangle(0.0, 0.0, 50.0, 100.0))
        sliver = QgsGeometry.fromRect(QgsRectangle(50.0, 0.0, 50.05, 100.0))
        unrelated = QgsGeometry.fromRect(QgsRectangle(75.0, 0.0, 100.0, 100.0))
        result = {
            "gain": [],
            "loss": [
                (baseline, future, target),
                (baseline, future, unrelated),
            ],
            "no_change": [(baseline, future, sliver)],
            "transition": [],
        }
        comparison._track_recovered_sliver_geometry(sliver)

        comparison._reattach_tracked_recovered_sliver_parts(result)

        self.assertEqual(result["no_change"], [])
        self.assertEqual(len(result["loss"]), 2)
        self.assertAlmostEqual(
            sum(geometry.area() for _baseline, _future, geometry in result["loss"]),
            target.area() + sliver.area() + unrelated.area(),
            places=6,
        )
        self.assertTrue(any(
            abs(geometry.area() - unrelated.area()) <= 1e-6
            for _baseline, _future, geometry in result["loss"]
        ))
        diagnostics = comparison.comparison_diagnostics()[
            "local_recovery_normalisation"
        ]
        self.assertEqual(diagnostics["reattached_parts"], 1)
        self.assertEqual(diagnostics["reclassified_parts"], 1)

    def test_untracked_narrow_part_is_not_dissolved(self):
        baseline = self.constant("baseline", 100.0)
        future = self.constant("future", 99.0)
        comparison = OlsEnvelopeComparisonEngine(
            PlanarControllingOlsEngine([baseline]),
            PlanarControllingOlsEngine([future]),
        )
        target = QgsGeometry.fromRect(QgsRectangle(0.0, 0.0, 50.0, 100.0))
        narrow = QgsGeometry.fromRect(QgsRectangle(50.0, 0.0, 50.05, 100.0))
        result = {
            "gain": [],
            "loss": [(baseline, future, target)],
            "no_change": [(baseline, future, narrow)],
            "transition": [],
        }

        comparison._reattach_tracked_recovered_sliver_parts(result)

        self.assertEqual(len(result["loss"]), 1)
        self.assertEqual(len(result["no_change"]), 1)
        self.assertAlmostEqual(result["no_change"][0][2].area(), narrow.area())

    def test_wide_recovery_part_is_not_absorbed(self):
        baseline = self.constant("baseline", 100.0)
        future = self.constant("future", 99.0)
        comparison = OlsEnvelopeComparisonEngine(
            PlanarControllingOlsEngine([baseline]),
            PlanarControllingOlsEngine([future]),
        )
        target = QgsGeometry.fromRect(QgsRectangle(0.0, 0.0, 50.0, 100.0))
        wide = QgsGeometry.fromRect(QgsRectangle(50.0, 0.0, 51.0, 100.0))
        result = {
            "gain": [],
            "loss": [(baseline, future, target)],
            "no_change": [(baseline, future, wide)],
            "transition": [],
        }
        comparison._track_recovered_sliver_geometry(wide)

        comparison._reattach_tracked_recovered_sliver_parts(result)

        self.assertEqual(len(result["loss"]), 1)
        self.assertEqual(len(result["no_change"]), 1)
        self.assertAlmostEqual(result["no_change"][0][2].area(), wide.area())

    def test_ambiguous_recovery_sliver_keeps_canonical_classification(self):
        baseline = self.constant("baseline", 100.0)
        future = self.constant("future", 100.0)
        comparison = OlsEnvelopeComparisonEngine(
            PlanarControllingOlsEngine([baseline]),
            PlanarControllingOlsEngine([future]),
        )
        gain_side = QgsGeometry.fromRect(QgsRectangle(0.0, 0.0, 49.95, 100.0))
        sliver = QgsGeometry.fromRect(QgsRectangle(49.95, 0.0, 50.05, 100.0))
        loss_side = QgsGeometry.fromRect(QgsRectangle(50.05, 0.0, 100.0, 100.0))
        result = {
            "gain": [(baseline, future, gain_side)],
            "loss": [(baseline, future, loss_side)],
            "no_change": [(baseline, future, sliver)],
            "transition": [],
        }
        comparison._track_recovered_sliver_geometry(sliver)

        comparison._reattach_tracked_recovered_sliver_parts(result)

        self.assertEqual(len(result["gain"]), 1)
        self.assertEqual(len(result["loss"]), 1)
        self.assertEqual(len(result["no_change"]), 1)
        self.assertAlmostEqual(result["no_change"][0][2].area(), sliver.area())

    def test_recovery_source_is_consumed_after_one_local_attachment(self):
        baseline = self.constant("baseline", 100.0)
        future = self.constant("future", 99.0)
        comparison = OlsEnvelopeComparisonEngine(
            PlanarControllingOlsEngine([baseline]),
            PlanarControllingOlsEngine([future]),
        )
        left = QgsGeometry.fromRect(QgsRectangle(0.0, 0.0, 0.05, 100.0))
        sliver = QgsGeometry.fromRect(QgsRectangle(0.05, 0.0, 0.10, 100.0))
        right = QgsGeometry.fromRect(QgsRectangle(0.10, 0.0, 0.15, 30.0))
        result = {
            "gain": [],
            "loss": [
                (baseline, future, left),
                (baseline, future, right),
            ],
            "no_change": [(baseline, future, sliver)],
            "transition": [],
        }
        comparison._track_recovered_sliver_geometry(sliver)

        comparison._reattach_tracked_recovered_sliver_parts(result)

        self.assertEqual(result["no_change"], [])
        self.assertEqual(len(result["loss"]), 2)
        self.assertAlmostEqual(
            sum(geometry.area() for _baseline, _future, geometry in result["loss"]),
            left.area() + sliver.area() + right.area(),
            places=6,
        )
        diagnostics = comparison.comparison_diagnostics()[
            "local_recovery_normalisation"
        ]
        self.assertEqual(diagnostics["reattached_parts"], 1)
        self.assertAlmostEqual(diagnostics["reattached_area_m2"], sliver.area())

    def test_tracked_recovery_cannot_absorb_untracked_merged_tail(self):
        baseline = self.constant("baseline", 100.0)
        future = self.constant("future", 99.0)
        comparison = OlsEnvelopeComparisonEngine(
            PlanarControllingOlsEngine([baseline]),
            PlanarControllingOlsEngine([future]),
        )
        target = QgsGeometry.fromRect(QgsRectangle(0.0, 0.0, 50.0, 100.0))
        tracked = QgsGeometry.fromRect(QgsRectangle(50.0, 0.0, 50.05, 95.0))
        untracked = QgsGeometry.fromRect(
            QgsRectangle(50.0, 95.0, 50.05, 100.0)
        )
        merged = QgsGeometry.unaryUnion([tracked, untracked])
        result = {
            "gain": [],
            "loss": [(baseline, future, target)],
            "no_change": [(baseline, future, merged)],
            "transition": [],
        }
        comparison._track_recovered_sliver_geometry(tracked)

        comparison._reattach_tracked_recovered_sliver_parts(result)

        self.assertEqual(len(result["no_change"]), 1)
        self.assertEqual(len(result["loss"]), 1)

    def test_recovery_crossing_actual_controller_boundary_is_not_attached_whole(self):
        baseline_left = self.constant("b1", 100.0)
        baseline_right = self.plane("b2", -1.0, 0.0, 150.0)
        future = self.constant("future", 90.0)
        baseline_engine = PlanarControllingOlsEngine(
            [baseline_left, baseline_right]
        )
        comparison = OlsEnvelopeComparisonEngine(
            baseline_engine,
            PlanarControllingOlsEngine([future]),
        )
        left = QgsGeometry.fromRect(QgsRectangle(0.0, 0.0, 49.95, 100.0))
        right = QgsGeometry.fromRect(
            QgsRectangle(50.05, 0.0, 100.0, 100.0)
        )
        sliver = QgsGeometry.fromRect(
            QgsRectangle(49.95, 0.0, 50.05, 100.0)
        )
        self.assertEqual(
            baseline_engine.controlling_candidate_at_xy(
                QgsPointXY(49.95, 50.0)
            )[0].surface_id,
            "b1",
        )
        self.assertEqual(
            baseline_engine.controlling_candidate_at_xy(
                QgsPointXY(50.05, 50.0)
            )[0].surface_id,
            "b2",
        )
        result = {
            "gain": [],
            "loss": [
                (baseline_left, future, left),
                (baseline_right, future, right),
            ],
            "no_change": [(baseline_left, future, sliver)],
            "transition": [],
        }
        comparison._track_recovered_sliver_geometry(sliver)

        comparison._reattach_tracked_recovered_sliver_parts(result)

        self.assertEqual(len(result["no_change"]), 1)
        self.assertAlmostEqual(
            result["no_change"][0][2].area(),
            sliver.area(),
            places=6,
        )

    def test_recovery_overlap_perimeter_is_not_shared_boundary_contact(self):
        baseline = self.constant("baseline", 100.0)
        future = self.constant("future", 99.0)
        comparison = OlsEnvelopeComparisonEngine(
            PlanarControllingOlsEngine([baseline]),
            PlanarControllingOlsEngine([future]),
        )
        target = QgsGeometry.fromRect(QgsRectangle(0.0, 0.0, 50.0, 100.0))
        sliver = QgsGeometry.fromRect(QgsRectangle(49.96, 0.0, 50.04, 100.0))
        result = {
            "gain": [],
            "loss": [(baseline, future, target)],
            "no_change": [(baseline, future, sliver)],
            "transition": [],
        }
        comparison._track_recovered_sliver_geometry(sliver)

        comparison._reattach_tracked_recovered_sliver_parts(result)

        self.assertEqual(len(result["loss"]), 1)
        self.assertEqual(len(result["no_change"]), 1)

    def test_equal_same_class_recovery_contacts_are_left_unchanged(self):
        baseline = self.constant("baseline", 100.0)
        future = self.constant("future", 99.0)

        def normalise(targets):
            comparison = OlsEnvelopeComparisonEngine(
                PlanarControllingOlsEngine([baseline]),
                PlanarControllingOlsEngine([future]),
            )
            sliver = QgsGeometry.fromRect(
                QgsRectangle(49.95, 0.0, 50.05, 100.0)
            )
            result = {
                "gain": [],
                "loss": [(baseline, future, geometry) for geometry in targets],
                "no_change": [(baseline, future, sliver)],
                "transition": [],
            }
            comparison._track_recovered_sliver_geometry(sliver)
            comparison._reattach_tracked_recovered_sliver_parts(result)
            return result

        left = QgsGeometry.fromRect(QgsRectangle(0.0, 0.0, 49.95, 100.0))
        right = QgsGeometry.fromRect(QgsRectangle(50.05, 0.0, 100.0, 100.0))
        forward = normalise([left, right])
        reverse = normalise([right, left])

        self.assertEqual(len(forward["no_change"]), 1)
        self.assertEqual(len(reverse["no_change"]), 1)
        self.assertEqual(len(forward["loss"]), 2)
        self.assertEqual(len(reverse["loss"]), 2)

    def test_final_recovery_mutation_is_closed_by_sign_and_partition_audit(self):
        baseline = self.constant("baseline", 100.0)
        future = self.constant("future", 90.0)
        comparison = OlsEnvelopeComparisonEngine(
            PlanarControllingOlsEngine([baseline]),
            PlanarControllingOlsEngine([future]),
        )
        original_reattach = comparison._reattach_tracked_recovered_sliver_parts
        call_count = 0

        def inject_after_last_retry(result):
            nonlocal call_count
            call_count += 1
            original_reattach(result)
            if call_count == 3:
                wrong_sign = QgsGeometry.fromRect(
                    QgsRectangle(0.0, 0.0, 1.0, 100.0)
                )
                result["gain"].append((baseline, future, wrong_sign))

        with patch.object(
            comparison,
            "_reattach_tracked_recovered_sliver_parts",
            side_effect=inject_after_last_retry,
        ):
            parts = comparison.comparison_parts()

        self.assertEqual(call_count, 3)
        self.assertEqual(parts["gain"], [])
        self.assertAlmostEqual(
            sum(geometry.area() for _baseline, _future, geometry in parts["loss"]),
            self.domain.area(),
            places=6,
        )

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

        final_parts = {
            "gain": [],
            "loss": [(baseline, future, spiked_loss)],
            "no_change": [],
        }
        engine._remove_final_boundary_backtracks(final_parts)
        final_cleaned = final_parts["loss"][0][2]
        final_vertices = [
            (round(vertex.x(), 6), round(vertex.y(), 6))
            for vertex in final_cleaned.vertices()
        ]
        self.assertNotIn((293.097156, 633.241381), final_vertices)
        self.assertAlmostEqual(final_cleaned.symDifference(spiked_loss).area(), 0.0, places=6)

    def test_final_boundary_cleanup_retains_nonzero_narrow_wedge(self):
        baseline = self.constant("baseline", 100.0)
        future = self.constant("future", 90.0)
        engine = OlsEnvelopeComparisonEngine(
            PlanarControllingOlsEngine([baseline]),
            PlanarControllingOlsEngine([future]),
        )
        narrow_wedge = QgsGeometry.fromPolygonXY([[
            QgsPointXY(0.0, 0.0),
            QgsPointXY(100.0, 0.0),
            QgsPointXY(100.0, 100.0),
            QgsPointXY(50.25, 100.0),
            QgsPointXY(50.0, 400.0),
            QgsPointXY(49.75, 100.0),
            QgsPointXY(0.0, 100.0),
            QgsPointXY(0.0, 0.0),
        ]])

        cleaned = engine._remove_zero_area_boundary_backtracks(narrow_wedge)

        cleaned_vertices = [
            (round(vertex.x(), 3), round(vertex.y(), 3))
            for vertex in cleaned.vertices()
        ]
        self.assertIn((50.0, 400.0), cleaned_vertices)
        self.assertAlmostEqual(cleaned.symDifference(narrow_wedge).area(), 0.0, places=6)

    def test_ybbn_axis_conical_boundary_parts_retain_signed_change(self):
        narrow = QgsGeometry.fromRect(QgsRectangle(0.0, 0.0, 0.2, 100.0))
        cases = (
            ("TOCS", "gain", 100.016),
            ("Approach", "loss", 99.984),
        )
        for surface_type, expected_change, future_elevation in cases:
            with self.subTest(surface_type=surface_type, change=expected_change):
                baseline = ControllingOlsCandidate(
                    f"baseline-{surface_type.lower()}",
                    surface_type,
                    narrow,
                    constant_elevation_evaluator(100.0),
                    "axis",
                )
                future = ControllingOlsCandidate(
                    "comparison-conical",
                    "Conical",
                    narrow,
                    constant_elevation_evaluator(future_elevation),
                    "conical",
                )
                comparison = OlsEnvelopeComparisonEngine(
                    PlanarControllingOlsEngine(
                        [baseline],
                        ruleset_id="mos139_2019",
                    ),
                    PlanarControllingOlsEngine(
                        [future],
                        ruleset_id="uk_caa_cap168_edition_13",
                    ),
                )

                parts = comparison.comparison_parts()

                opposite_change = "loss" if expected_change == "gain" else "gain"
                self.assertEqual(parts["no_change"], [])
                self.assertEqual(parts[opposite_change], [])
                self.assertEqual(len(parts[expected_change]), 1)
                self.assertAlmostEqual(
                    parts[expected_change][0][2].area(),
                    narrow.area(),
                    places=6,
                )

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

        self.assertEqual([item[3] for item in contours], [1.0, 2.0])
        self.assertEqual([item[4] for item in contours], ["intermediate", "intermediate"])
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

        self.assertEqual(line_builder.call_count, 2)
        self.assertEqual(len(contours), 4)
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

    def test_gap_repair_does_not_recover_the_same_numerical_overlap_twice(self):
        baseline_first = self.constant("baseline-first", 100.0)
        baseline_second = self.constant("baseline-second", 100.0)
        future = self.constant("future", 90.0)
        baseline_engine = PlanarControllingOlsEngine(
            [baseline_first, baseline_second]
        )
        future_engine = PlanarControllingOlsEngine([future])
        baseline_regions = [
            (baseline_first, QgsGeometry(self.domain)),
            (baseline_second, QgsGeometry(self.domain)),
        ]
        future_regions = [(future, QgsGeometry(self.domain))]
        engine = OlsEnvelopeComparisonEngine(baseline_engine, future_engine)
        result = {"gain": [], "loss": [], "no_change": [], "transition": []}

        engine._append_common_domain_gap_parts(
            result,
            baseline_regions,
            future_regions,
        )

        self.assertEqual(len(result["loss"]), 1)
        self.assertAlmostEqual(result["loss"][0][2].area(), self.domain.area())

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
        overlap = QgsGeometry.fromRect(QgsRectangle(100.0, 100.0, 250.0, 250.0))
        origin = QgsPointXY(100.0, 100.0)
        axis = ControllingOlsCandidate(
            "axis",
            "Approach",
            overlap,
            axis_elevation_evaluator(origin, 90.0, 105.0, 0.02, 150.0),
            "axis",
            {
                "origin_x": 100.0,
                "origin_y": 100.0,
                "origin_elevation_m": 105.0,
                "slope": 0.02,
                "max_distance_m": 150.0,
                "azimuth_degrees": 90.0,
            },
        )
        conical = ControllingOlsCandidate(
            "conical",
            "Conical",
            overlap,
            conical_elevation_evaluator(base, 100.0, 0.05, 200.0),
            "conical",
            {
                "base_footprint": base,
                "base_elevation_m": 100.0,
                "slope": 0.05,
                "max_distance_m": 200.0,
            },
        )
        engine = PlanarControllingOlsEngine([axis, conical])
        axis_model = engine._axis_model(axis)
        conical_model = engine._conical_model(conical)
        sampled_reference = engine._axis_conical_transition_curve(
            axis_model,
            conical_model,
            overlap,
        )
        self.assertIsNotNone(sampled_reference)
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

        exact_points = []
        # Span enough distance to exercise the configured cubic-guide path;
        # short curves are supplied the minimum three control segments.
        stations = list(range(0, 81, 10))
        for station in stations:
            required_distance = 100.0 + (0.4 * station)
            lateral = math.sqrt(
                (required_distance * required_distance) - (station * station)
            )
            exact_points.append(QgsPointXY(100.0 + station, 100.0 + lateral))
        smoothed_reference = engine._smoothed_axis_conical_zero_contour(
            QgsGeometry.fromPolylineXY(exact_points),
            axis,
            conical,
            axis_model,
            conical_model,
            overlap,
        )
        self.assertIsNotNone(
            smoothed_reference,
            msg=str(engine._region_solve_stats),
        )
        self.assertGreater(
            engine._region_solve_stats.get("axis_curve_smoothing_accepted", 0.0),
            0.0,
        )
        self.assertEqual(
            engine._region_solve_stats["axis_curve_smoothing_max_endpoint_shift_m"],
            0.0,
        )

    def test_clamped_cubic_bspline_preserves_endpoints_and_reduces_turns(self):
        controls = [
            QgsPointXY(0.0, 0.0),
            QgsPointXY(10.0, 2.0),
            QgsPointXY(20.0, 0.5),
            QgsPointXY(30.0, 4.0),
            QgsPointXY(40.0, 2.5),
            QgsPointXY(50.0, 5.0),
        ]

        smoothed = PlanarControllingOlsEngine._clamped_cubic_bspline_points(
            controls,
            4,
        )

        def maximum_turn(points):
            turns = []
            for previous, current, following in zip(
                points[:-2],
                points[1:-1],
                points[2:],
            ):
                first_heading = math.atan2(
                    current.y() - previous.y(),
                    current.x() - previous.x(),
                )
                second_heading = math.atan2(
                    following.y() - current.y(),
                    following.x() - current.x(),
                )
                turns.append(
                    abs(
                        math.atan2(
                            math.sin(second_heading - first_heading),
                            math.cos(second_heading - first_heading),
                        )
                    )
                )
            return max(turns)

        self.assertEqual(smoothed[0], controls[0])
        self.assertEqual(smoothed[-1], controls[-1])
        self.assertGreater(len(smoothed), len(controls))
        self.assertLess(maximum_turn(smoothed), maximum_turn(controls))

    def test_least_squares_bspline_fairs_noise_without_interpolating_it(self):
        engine = PlanarControllingOlsEngine([self.constant("base", 100.0)])
        observations = []
        for index in range(41):
            x = float(index * 10)
            fair_y = 0.002 * x * x
            noise = 0.0 if index in {0, 40} else (0.45 if index % 2 else -0.45)
            observations.append(QgsPointXY(x, fair_y + noise))
        source_line = QgsGeometry.fromPolylineXY(observations)

        result = engine._least_squares_bspline_guide_points(
            observations,
            source_line,
        )

        self.assertIsNotNone(result)
        guide_points, diagnostics = result
        self.assertEqual(guide_points[0], observations[0])
        self.assertEqual(guide_points[-1], observations[-1])
        self.assertLess(diagnostics["control_points"], diagnostics["source_vertices"])
        self.assertGreater(diagnostics["maximum_point_error_m"], 0.1)
        source_peak, source_rms = engine._curve_curvature_continuity_metrics(source_line)
        fitted_peak, fitted_rms = engine._curve_curvature_continuity_metrics(
            QgsGeometry.fromPolylineXY(guide_points)
        )
        self.assertLess(fitted_peak, source_peak)
        self.assertLess(fitted_rms, source_rms)

    def test_axis_conical_output_collapses_sliver_loops_and_reverse_segments(self):
        engine = PlanarControllingOlsEngine([self.constant("base", 100.0)])
        root = QgsPointXY(0.0, 0.0)
        near_root = QgsPointXY(0.2, 0.1)
        tip = QgsPointXY(4.0, 1.0)
        far = QgsPointXY(20.0, 5.0)
        linework = [
            QgsGeometry.fromPolylineXY([root, tip]),
            QgsGeometry.fromPolylineXY([tip, near_root]),
            QgsGeometry.fromPolylineXY([near_root, root]),
            QgsGeometry.fromPolylineXY([tip, far]),
            QgsGeometry.fromPolylineXY([far, tip]),
            QgsGeometry.fromPolylineXY(
                [
                    QgsPointXY(30.0, 30.0),
                    QgsPointXY(31.0, 30.0),
                    QgsPointXY(30.0, 31.0),
                    QgsPointXY(30.0, 30.0),
                ]
            ),
            QgsGeometry.fromPolylineXY([QgsPointXY(40.0, 40.0), QgsPointXY(40.8, 40.0)]),
        ]
        geometry = QgsGeometry.unaryUnion(linework)

        parts = engine._topology_clean_transition_line_parts(geometry)

        self.assertEqual(len(parts), 1)
        self.assertEqual(len(parts[0]), 3)
        endpoints = {
            (round(parts[0][0].x(), 1), round(parts[0][0].y(), 1)),
            (round(parts[0][-1].x(), 1), round(parts[0][-1].y(), 1)),
        }
        self.assertEqual(endpoints, {(0.0, 0.0), (20.0, 5.0)})
        segment_keys = {
            engine._undirected_segment_key(start, end)
            for start, end in zip(parts[0][:-1], parts[0][1:])
        }
        self.assertEqual(len(segment_keys), len(parts[0]) - 1)

    def test_axis_conical_output_erases_hairpins_but_preserves_ordinary_corners(self):
        points = [
            QgsPointXY(0.0, 0.0),
            QgsPointXY(10.0, 0.0),
            QgsPointXY(9.0, 0.05),
            QgsPointXY(20.0, 0.0),
            QgsPointXY(20.0, 10.0),
        ]

        cleaned = PlanarControllingOlsEngine._remove_transition_curve_backtracking(points)

        self.assertEqual(len(cleaned), 4)
        self.assertAlmostEqual(cleaned[1].x(), 9.0)
        self.assertAlmostEqual(cleaned[-1].y(), 10.0)

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

    def test_comparison_generation_uses_selected_ofs_change_contour_intervals(self):
        baseline = self.constant("baseline", 100.0)
        future = ControllingOlsCandidate(
            surface_id="future-ofs",
            surface_type="Future OFS",
            footprint=QgsGeometry(self.domain),
            elevation_at_xy=constant_elevation_evaluator(110.0),
            model="constant",
            metadata={"elevation_m": 110.0, "annex14_family": "OFS"},
        )
        capture = _ComparisonLayerCapture()
        capture._get_contour_interval = lambda key, fallback: (
            0.25 if key == "modernisation_ofs_change" else fallback
        )
        capture._get_primary_contour_interval = lambda key, fallback: (
            2.0 if key == "modernisation_ofs_change" else fallback
        )

        with patch.object(
            OlsEnvelopeComparisonEngine,
            "change_contour_parts",
            return_value=[],
        ) as change_contours:
            created = capture._create_ols_modernisation_comparison_layers(
                "TEST",
                "baseline-rules",
                [baseline],
                [],
                [future],
                object(),
                object(),
            )

        self.assertTrue(created)
        self.assertEqual(change_contours.call_count, 2)
        for call in change_contours.call_args_list:
            self.assertEqual(call.kwargs["interval_m"], 0.25)
            self.assertEqual(call.kwargs["primary_interval_m"], 2.0)

    def test_generic_ruleset_adapter_preserves_selected_baseline_direction(self):
        annex_baseline = ControllingOlsCandidate(
            surface_id="annex-ofs",
            surface_type="Annex OFS",
            footprint=QgsGeometry(self.domain),
            elevation_at_xy=constant_elevation_evaluator(110.0),
            model="constant",
            metadata={"elevation_m": 110.0, "annex14_family": "OFS"},
        )
        mos_comparison = self.constant("mos-ols", 100.0)
        capture = _ComparisonLayerCapture()

        created = capture._create_ols_ruleset_comparison_layers(
            icao_code="TEST",
            baseline_ruleset_id="annex",
            comparison_ruleset_id="mos",
            baseline_model="annex14_modernised_ofs_oes",
            comparison_model="ols_current",
            baseline_candidates=[annex_baseline],
            baseline_exclusions=[],
            comparison_candidates=[mos_comparison],
            comparison_exclusions=[],
            output_groups={"OFS": object(), "OES": object(), "OLS": None},
        )

        self.assertTrue(created)
        loss_layer = next(layer for layer in capture.layers if layer[2] == "Height Loss")
        feature = loss_layer[4][0]
        self.assertEqual(feature["baseline_ruleset"], "annex")
        self.assertEqual(feature["comparison_ruleset"], "mos")
        self.assertEqual(feature["change"], "loss")
        self.assertEqual(feature["delta_sample_m"], -10.0)

    def test_generic_ruleset_adapter_compares_two_conventional_ols_envelopes(self):
        capture = _ComparisonLayerCapture()

        created = capture._create_ols_ruleset_comparison_layers(
            icao_code="TEST",
            baseline_ruleset_id="cap168",
            comparison_ruleset_id="mos139",
            baseline_model="ols_current",
            comparison_model="ols_current",
            baseline_candidates=[self.constant("cap", 90.0)],
            baseline_exclusions=[],
            comparison_candidates=[self.constant("mos", 100.0)],
            comparison_exclusions=[],
            output_groups={"OFS": None, "OES": None, "OLS": object()},
        )

        self.assertTrue(created)
        gain_layer = next(layer for layer in capture.layers if layer[2] == "Height Gain")
        feature = gain_layer[4][0]
        self.assertEqual(feature["future_family"], "OLS")
        self.assertEqual(feature["baseline_ruleset"], "cap168")
        self.assertEqual(feature["comparison_ruleset"], "mos139")
        self.assertEqual(feature["delta_sample_m"], 10.0)

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
            contour_interval_m=0.25,
            primary_interval_m=2.0,
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
        self.assertEqual(contour_feature["contour_interval_m"], 0.25)
        self.assertEqual(contour_feature["primary_interval_m"], 2.0)
        self.assertEqual(len(comparison_ids), 5)
        self.assertEqual(len(set(comparison_ids)), 5)
        self.assertIn("OFS-GAIN-000001", comparison_ids)


if __name__ == "__main__":
    unittest.main()
