import unittest

from qgis.core import QgsGeometry, QgsRectangle

from guidelines.controlling_ols_engine import (
    ControllingOlsCandidate,
    constant_elevation_evaluator,
)
from tests.run_ols_workflow_regression import (
    _build_outcome_failures,
    _controlling_metrics_from_engines,
    _length,
)


class _SolvedEngine:
    def __init__(self, candidates, regions):
        self.candidates = candidates
        self._regions = regions

    def _controlling_region_geometries(self):
        return self._regions


class OlsWorkflowRegressionMetricTests(unittest.TestCase):
    @staticmethod
    def candidate(surface_id, family, rectangle):
        footprint = QgsGeometry.fromRect(rectangle)
        return ControllingOlsCandidate(
            surface_id=surface_id,
            surface_type="Test",
            footprint=footprint,
            elevation_at_xy=constant_elevation_evaluator(100.0),
            model="constant",
            metadata={"annex14_family": family, "elevation_m": 100.0},
        )

    def test_solver_metrics_do_not_require_candidate_debug_layers(self):
        left = self.candidate("ofs-left", "OFS", QgsRectangle(0.0, 0.0, 50.0, 100.0))
        right = self.candidate("ofs-right", "OFS", QgsRectangle(50.0, 0.0, 100.0, 100.0))
        engine = _SolvedEngine(
            [left, right],
            [
                (left, QgsGeometry(left.footprint)),
                (right, QgsGeometry(right.footprint)),
            ],
        )

        metrics = _controlling_metrics_from_engines([engine])

        self.assertEqual(metrics["OFS"]["source"], "solver")
        self.assertEqual(metrics["OFS"]["candidates"], 2)
        self.assertEqual(metrics["OFS"]["regions"], 2)
        self.assertAlmostEqual(metrics["OFS"]["candidate_area_m2"], 10000.0)
        self.assertAlmostEqual(metrics["OFS"]["coverage_difference_m2"], 0.0)
        self.assertAlmostEqual(metrics["OFS"]["region_overlap_m2"], 0.0)

    def test_solver_metrics_report_real_coverage_gaps(self):
        candidate = self.candidate("oes", "OES", QgsRectangle(0.0, 0.0, 100.0, 100.0))
        covered = QgsGeometry.fromRect(QgsRectangle(0.0, 0.0, 90.0, 100.0))
        engine = _SolvedEngine([candidate], [(candidate, covered)])

        metrics = _controlling_metrics_from_engines([engine])

        self.assertAlmostEqual(metrics["OES"]["coverage_difference_m2"], 1000.0)
        self.assertAlmostEqual(metrics["OES"]["controlling_area_m2"], 9000.0)

    def test_published_regions_are_checked_against_solver_candidates(self):
        candidate = self.candidate("ofs", "OFS", QgsRectangle(0.0, 0.0, 100.0, 100.0))
        pre_output_region = QgsGeometry.fromRect(QgsRectangle(0.0, 0.0, 90.0, 100.0))
        published_region = QgsGeometry(candidate.footprint)
        engine = _SolvedEngine([candidate], [(candidate, pre_output_region)])

        metrics = _controlling_metrics_from_engines(
            [engine],
            {"OFS": [published_region], "OES": []},
        )

        self.assertEqual(
            metrics["OFS"]["source"],
            "solver_candidates+published_regions",
        )
        self.assertAlmostEqual(metrics["OFS"]["coverage_difference_m2"], 0.0)
        self.assertAlmostEqual(metrics["OFS"]["controlling_area_m2"], 10000.0)

    def test_empty_geometry_length_is_zero_not_qgis_sentinel(self):
        self.assertEqual(_length(QgsGeometry()), 0.0)

    def test_build_outcome_gate_uses_explicit_stage_results(self):
        outcomes = [
            {
                "scope": "controlling protected-airspace envelope",
                "status": "generated",
                "layers": 4,
                "features": 20,
            },
            {
                "scope": "OLS ruleset comparison",
                "status": "failed",
                "reason": "no comparison output was generated",
            },
        ]

        failures = _build_outcome_failures(
            outcomes,
            [
                "controlling protected-airspace envelope",
                "OLS ruleset comparison",
            ],
        )

        self.assertEqual(
            failures,
            [
                "OLS ruleset comparison build failed: "
                "no comparison output was generated"
            ],
        )

    def test_build_outcome_gate_requires_requested_stage(self):
        failures = _build_outcome_failures(
            [],
            ["controlling protected-airspace envelope"],
        )

        self.assertEqual(
            failures,
            [
                "explicit build outcome is missing for "
                "controlling protected-airspace envelope"
            ],
        )


if __name__ == "__main__":
    unittest.main()
