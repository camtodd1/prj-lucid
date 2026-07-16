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
        self.assertEqual(run["testCase"], "YTEST parallel runways")
        self.assertEqual(run["runwayCount"], 2)
        self.assertEqual(run["scenario"], "Parallel")
        self.assertEqual(run["runBy"], "Automated test")
        self.assertTrue(run["exactSetupRecorded"])
        self.assertIn("MOS139", run["primaryOls"])
        self.assertIn("Annex 14 Modernised", run["comparedWith"])

        html = build_html(
            runs,
            generated_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
        )
        for control in (
            "filterTestCase",
            "filterAirport",
            "filterRunways",
            "filterScenario",
            "filterBuiltTo",
            "filterPrimary",
            "filterComparison",
            "lastFive",
            "trendChart",
            "pivotBody",
        ):
            self.assertIn(f'id="{control}"', html)
        payload = re.search(
            r'<script id="runData" type="application/json">(.*?)</script>',
            html,
            re.DOTALL,
        )
        self.assertIsNotNone(payload)
        self.assertEqual(json.loads(payload.group(1))[0]["fingerprint"], "setup123")

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
