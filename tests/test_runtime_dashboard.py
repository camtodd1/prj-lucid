"""Tests for the filterable AeroSense runtime explorer."""

from __future__ import annotations

import csv
import json
import re
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from dashboard.runtime_dashboard import build_html, load_runs, recent_window_change


COLUMNS = (
    "timestamp_utc",
    "status",
    "airport",
    "design_ruleset",
    "baseline_ols_ruleset",
    "comparison_ols_ruleset",
    "design_ruleset_label",
    "baseline_ols_ruleset_label",
    "comparison_ols_ruleset_label",
    "commit_ref",
    "working_tree_dirty",
    "agent",
    "elapsed_seconds",
    "test_case_id",
    "test_case_name",
    "input_filename",
    "runway_count",
    "runway_configuration",
    "input_fingerprint",
)


def _write_ledger(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=COLUMNS, delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)


class RuntimeDashboardTests(unittest.TestCase):
    def test_scenario_dimensions_are_available_to_every_dashboard_control(self):
        row = {
            "timestamp_utc": "2026-01-01T00:00:00Z",
            "status": "completed",
            "airport": "YTEST",
            "design_ruleset": "mos139_2019",
            "baseline_ols_ruleset": "mos139_2019",
            "comparison_ols_ruleset": "icao_annex14_vol1_modernised_ofs_oes",
            "commit_ref": "abc123def456",
            "working_tree_dirty": "false",
            "agent": "codex headless",
            "elapsed_seconds": "12.5",
            "test_case_id": "ytest_parallel",
            "test_case_name": "YTEST parallel runways",
            "input_filename": "ytest_parallel.json",
            "runway_count": "2",
            "runway_configuration": "parallel",
            "input_fingerprint": "setup123",
        }
        with tempfile.TemporaryDirectory() as directory:
            ledger = Path(directory) / "runs.tsv"
            _write_ledger(ledger, [row])
            runs = load_runs(ledger)

        run = runs[0]
        self.assertEqual(run["testCase"], "YTEST 2Rwy Parallel")
        self.assertEqual(run["runwayCount"], 2)
        self.assertEqual(run["scenario"], "Parallel")
        self.assertEqual(run["scenarioSlice"], "Dual Parallel")
        self.assertEqual(run["runBy"], "Codex")
        self.assertTrue(run["exactSetupRecorded"])
        self.assertIn("MOS139", run["primaryOls"])
        self.assertEqual(
            run["comparedWith"],
            "ICAO Annex 14 Vol I - Modernised OLS",
        )

        html = build_html(
            runs,
            generated_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
        )
        for control in (
            "filterScenarioSlice",
            "filterAirport",
            "filterBuiltTo",
            "filterPrimary",
            "filterComparison",
            "filterRunBy",
            "lastFive",
            "trendChart",
            "pivotBody",
        ):
            self.assertIn(f'id="{control}"', html)
        self.assertIn('class="run-owner', html)
        self.assertNotIn("run-owner user", html)
        self.assertNotIn("run-owner codex", html)
        self.assertIn("${escapeHtml(run.runBy)}", html)
        self.assertIn("priorComparable(run, runs)", html)
        self.assertIn('"Multiple Intersecting"', html)
        self.assertIn("runsMatchingOtherFilters", html)
        self.assertIn("refreshFilterOptions", html)
        self.assertIn("buildSeriesStyles", html)
        self.assertIn('class="series-marker', html)
        self.assertIn("groupPrimary.value = 'trendSeries'", html)
        self.assertNotIn('id="filterTestCase"', html)
        self.assertNotIn('id="filterOlsSelection"', html)
        payload = re.search(
            r'<script id="runData" type="application/json">(.*?)</script>',
            html,
            re.DOTALL,
        )
        self.assertIsNotNone(payload)
        self.assertEqual(json.loads(payload.group(1))[0]["fingerprint"], "setup123")

    def test_historical_case_names_and_ruleset_labels_use_dashboard_standard(self):
        row = {
            "timestamp_utc": "2026-01-01T00:00:00Z",
            "status": "completed",
            "airport": "YBBN",
            "comparison_ols_ruleset": "icao_annex14_vol1_modernised_ofs_oes",
            "comparison_ols_ruleset_label": "Future Annex 14",
            "commit_ref": "standard1",
            "elapsed_seconds": "30",
            "test_case_name": "Brisbane parallel runway performance check",
            "runway_count": "2",
            "runway_configuration": "parallel",
        }
        with tempfile.TemporaryDirectory() as directory:
            ledger = Path(directory) / "runs.tsv"
            _write_ledger(ledger, [row])
            run = load_runs(ledger)[0]

        self.assertEqual(run["testCase"], "YBBN 2Rwy Parallel")
        self.assertEqual(
            run["comparedWith"],
            "ICAO Annex 14 Vol I - Modernised OLS",
        )

    def test_top_level_scenario_slice_distinguishes_dual_and_mixed_layouts(self):
        cases = (
            ("2", "parallel", "Dual Parallel"),
            ("2", "intersecting", "Dual Intersecting"),
            ("3", "parallel", "Multiple Parallel"),
            ("3", "mixed", "Multiple Intersecting"),
            ("3", "intersecting", "Multiple Intersecting"),
        )
        rows = [
            {
                "timestamp_utc": f"2026-01-0{index}T00:00:00Z",
                "status": "completed",
                "airport": f"YTE{index}T",
                "commit_ref": f"scenario{index}",
                "elapsed_seconds": "30",
                "runway_count": count,
                "runway_configuration": layout,
            }
            for index, (count, layout, _) in enumerate(cases, start=1)
        ]
        with tempfile.TemporaryDirectory() as directory:
            ledger = Path(directory) / "runs.tsv"
            _write_ledger(ledger, rows)
            runs = load_runs(ledger)

        self.assertEqual(
            [run["scenarioSlice"] for run in runs],
            [expected for _, _, expected in cases],
        )

    def test_legacy_rows_are_not_mislabelled_as_known_scenarios(self):
        row = {
            "timestamp_utc": "2026-01-01T00:00:00Z",
            "status": "completed",
            "airport": "YSSY",
            "baseline_ols_ruleset": "mos139_2019",
            "commit_ref": "legacy1",
            "elapsed_seconds": "30",
        }
        with tempfile.TemporaryDirectory() as directory:
            ledger = Path(directory) / "runs.tsv"
            _write_ledger(ledger, [row])
            run = load_runs(ledger)[0]

        self.assertEqual(run["testCase"], "Not recorded")
        self.assertIsNone(run["runwayCount"])
        self.assertEqual(run["scenario"], "Not recorded")
        self.assertFalse(run["exactSetupRecorded"])
        self.assertTrue(str(run["exactSetup"]).startswith("legacy:"))

    def test_invalid_scenario_count_is_not_offered_as_a_dashboard_scenario(self):
        row = {
            "timestamp_utc": "2026-01-01T00:00:00Z",
            "status": "completed",
            "airport": "YTEST",
            "commit_ref": "invalid1",
            "elapsed_seconds": "30",
            "runway_count": "2",
            "runway_configuration": "mixed",
        }
        with tempfile.TemporaryDirectory() as directory:
            ledger = Path(directory) / "runs.tsv"
            _write_ledger(ledger, [row])
            run = load_runs(ledger)[0]

        self.assertEqual(run["scenario"], "Not recorded")

    def test_icao_references_are_uppercase_in_dashboard_labels(self):
        row = {
            "timestamp_utc": "2026-01-01T00:00:00Z",
            "status": "completed",
            "airport": "ymml",
            "commit_ref": "case123",
            "elapsed_seconds": "30",
            "test_case_id": "ymml_2rwy_intersecting",
            "test_case_name": "ymml intersecting runway check",
        }
        with tempfile.TemporaryDirectory() as directory:
            ledger = Path(directory) / "runs.tsv"
            _write_ledger(ledger, [row])
            run = load_runs(ledger)[0]

        self.assertEqual(run["airport"], "YMML")
        self.assertEqual(run["testCase"], "YMML intersecting runway check")
        self.assertEqual(run["runBy"], "User")

    def test_recent_window_compares_last_five_with_previous_five(self):
        runs = [
            {"status": "Completed", "elapsed": value}
            for value in [20, 20, 20, 20, 20, 15, 15, 15, 15, 15]
        ]
        summary = recent_window_change(runs)
        self.assertEqual(summary["previous_median"], 20)
        self.assertEqual(summary["recent_median"], 15)
        self.assertEqual(summary["change"], -0.25)


if __name__ == "__main__":
    unittest.main()
