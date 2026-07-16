"""Tests for the append-only GUI/headless runtime ledger."""

from __future__ import annotations

import csv
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core.run_history import (
    RUN_HISTORY_COLUMNS,
    RuntimeRunRecorder,
    classify_runway_configuration,
    detect_run_agent,
    migrate_history_file,
    runtime_input_fingerprint,
    validate_runway_configuration,
)


def _rows(history_path: Path):
    return list(
        csv.DictReader(
            io.StringIO(history_path.read_text(encoding="utf-8")),
            delimiter="\t",
        )
    )


class RunHistoryTests(unittest.TestCase):
    def test_agent_detection_distinguishes_gui_headless_and_override(self):
        self.assertEqual(detect_run_agent({}), "qgis user")
        self.assertEqual(detect_run_agent({"QT_QPA_PLATFORM": "offscreen"}), "codex headless")
        self.assertEqual(
            detect_run_agent({"SAFEGUARDING_BUILDER_RUN_AGENT": "release workstation"}),
            "release workstation",
        )

    def test_finish_appends_versioned_tabular_row_with_context_and_timings(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "metadata.txt").write_text("[general]\nversion=2.4\n", encoding="utf-8")
            history_path = root / "runs.txt"
            recorder = RuntimeRunRecorder(
                root,
                qgis_version="4.0-test",
                history_path=history_path,
                agent="codex headless",
            )
            recorder.set_context(
                airport="ybbn",
                design_ruleset="mos139_2019",
                baseline_ruleset="mos139_2019",
                comparison_ruleset="easa_cs_adr_dsn_issue_7",
                design_ruleset_label="MOS139 (C.07 2026)",
                baseline_ruleset_label="MOS139 (C.07 2026)",
                comparison_ruleset_label="EASA CS-ADR-DSN Issue 7",
                test_case_id="ybbn_1rwy_single",
                test_case_name="ybbn single runway",
                input_filename="ybbn_1rwy_single.json",
                runway_count=1,
                runway_configuration="single",
                input_fingerprint="abc123",
            )
            recorder.start_phase("inputs")
            recorder.start_phase("controlling_envelope")
            recorder.add_timing("controlling_ols.regions", 1.25)
            recorder.set_output_counts(185, 9973)
            with patch.dict("os.environ", {"SAFEGUARDING_BUILDER_COMMIT": "abc123def456"}):
                record = recorder.finish("completed")

            stored = _rows(history_path)[0]
            self.assertEqual(record["schema_version"], 4)
            self.assertEqual(stored["schema_version"], "4")
            self.assertEqual(stored["agent"], "codex headless")
            self.assertEqual(stored["airport"], "YBBN")
            self.assertEqual(stored["commit_ref"], "abc123def456")
            self.assertEqual(stored["plugin_version"], "2.4")
            self.assertEqual(stored["qgis_version"], "4.0-test")
            self.assertEqual(stored["comparison_ols_ruleset"], "easa_cs_adr_dsn_issue_7")
            self.assertEqual(stored["design_ruleset_label"], "MOS139 (C.07 2026)")
            self.assertEqual(stored["test_case_id"], "ybbn_1rwy_single")
            self.assertEqual(stored["test_case_name"], "YBBN single runway")
            self.assertEqual(stored["input_filename"], "ybbn_1rwy_single.json")
            self.assertEqual(stored["runway_count"], "1")
            self.assertEqual(stored["runway_configuration"], "single")
            self.assertEqual(stored["input_fingerprint"], "abc123")
            timings = json.loads(stored["module_timings_json"])
            self.assertEqual(timings["controlling_ols.regions"]["elapsed_seconds"], 1.25)
            self.assertEqual(stored["controlling_regions_seconds"], "1.25")
            self.assertEqual(stored["layers_created"], "185")
            self.assertEqual(stored["features_created"], "9973")
            self.assertIn("phase.inputs", timings)
            self.assertIn("phase.controlling_envelope", timings)

    def test_each_finish_appends_a_separate_record(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            history_path = root / "runs.txt"
            with patch.dict("os.environ", {"SAFEGUARDING_BUILDER_COMMIT": "test-ref"}):
                for status in ("aborted", "cancelled"):
                    RuntimeRunRecorder(root, history_path=history_path).finish(status)
            records = _rows(history_path)
            self.assertEqual([record["status"] for record in records], ["aborted", "cancelled"])

    def test_legacy_json_lines_are_migrated_without_losing_module_data(self):
        with tempfile.TemporaryDirectory() as directory:
            history_path = Path(directory) / "runs.txt"
            legacy = {
                "schema_version": 1,
                "timestamp_utc": "2026-07-13T12:00:00+00:00",
                "agent": "qgis user",
                "status": "completed",
                "airport": "YMML",
                "rulesets": {"design": "mos139_2019", "baseline_ols": "cap168", "comparison_ols": None},
                "ruleset_labels": {},
                "commit_ref": "legacy-ref",
                "working_tree_dirty": False,
                "plugin_version": "2.3",
                "qgis_version": "4.0",
                "elapsed_seconds": 9.5,
                "modules": [{"name": "phase.runway_ols", "calls": 1, "elapsed_seconds": 2.75}],
            }
            history_path.write_text(json.dumps(legacy) + "\n", encoding="utf-8")

            self.assertTrue(migrate_history_file(history_path))
            self.assertFalse(migrate_history_file(history_path))
            stored = _rows(history_path)[0]
            self.assertEqual(stored["schema_version"], "1")
            self.assertEqual(stored["airport"], "YMML")
            self.assertEqual(stored["baseline_ols_ruleset"], "cap168")
            self.assertEqual(stored["phase_runway_ols_seconds"], "2.75")
            self.assertEqual(
                json.loads(stored["module_timings_json"])["phase.runway_ols"]["calls"],
                1,
            )

    def test_older_tabular_header_is_extended_before_append(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            history_path = root / "runs.txt"
            old_columns = RUN_HISTORY_COLUMNS[: RUN_HISTORY_COLUMNS.index("test_case_id")]
            old_values = [""] * len(old_columns)
            old_values[old_columns.index("schema_version")] = "2"
            old_values[old_columns.index("airport")] = "YMML"
            old_values[old_columns.index("module_timings_json")] = "{}"
            history_path.write_text(
                "\t".join(old_columns) + "\n" + "\t".join(old_values) + "\n",
                encoding="utf-8",
            )

            recorder = RuntimeRunRecorder(root, history_path=history_path)
            recorder.set_output_counts(12, 345)
            with patch.dict("os.environ", {"SAFEGUARDING_BUILDER_COMMIT": "test-ref"}):
                recorder.finish("completed")

            records = _rows(history_path)
            self.assertEqual(tuple(records[0]), RUN_HISTORY_COLUMNS)
            self.assertEqual(records[0]["airport"], "YMML")
            self.assertEqual(records[0]["layers_created"], "")
            self.assertEqual(records[1]["layers_created"], "12")
            self.assertEqual(records[1]["features_created"], "345")
            self.assertIsNone(records[0]["test_case_id"])
            self.assertEqual(records[1]["test_case_id"], "")

    def test_runway_configuration_uses_actual_centreline_geometry(self):
        runway = lambda start, end: {"thr_point": start, "rec_thr_point": end}
        self.assertEqual(classify_runway_configuration([runway((0, 0), (10, 0))]), "single")
        self.assertEqual(
            classify_runway_configuration(
                [runway((0, 0), (10, 0)), runway((0, 2), (10, 2))]
            ),
            "parallel",
        )
        self.assertEqual(
            classify_runway_configuration(
                [runway((0, 0), (10, 10)), runway((0, 10), (10, 0))]
            ),
            "intersecting",
        )
        self.assertEqual(
            classify_runway_configuration(
                [runway((0, 0), (10, 0)), runway((20, 20), (30, 30))]
            ),
            "intersecting",
        )
        self.assertEqual(
            classify_runway_configuration(
                [
                    runway((0, 0), (10, 0)),
                    runway((0, 2), (10, 2)),
                    runway((5, -5), (5, 5)),
                ]
            ),
            "mixed",
        )

    def test_runway_configuration_enforces_supported_scenario_counts(self):
        accepted = (
            ("single", 1),
            ("parallel", 2),
            ("intersecting", 2),
            ("mixed", 3),
            ("parallel", 4),
        )
        for scenario, count in accepted:
            with self.subTest(scenario=scenario, count=count):
                self.assertEqual(
                    validate_runway_configuration(scenario.upper(), count),
                    scenario,
                )

        rejected = (
            ("single", 2),
            ("parallel", 1),
            ("intersecting", 1),
            ("mixed", 2),
            ("multiple", 3),
        )
        for scenario, count in rejected:
            with self.subTest(scenario=scenario, count=count):
                with self.assertRaises(ValueError):
                    validate_runway_configuration(scenario, count)

    def test_input_fingerprint_is_stable_and_changes_with_parameters(self):
        first = {
            "icao_code": "YTEST",
            "runways": [{"thr_point": (0, 0), "rec_thr_point": (10, 0)}],
            "baseline_ols_ruleset": "mos139_2019",
        }
        reordered = {
            "baseline_ols_ruleset": "mos139_2019",
            "runways": [{"rec_thr_point": (10, 0), "thr_point": (0, 0)}],
            "icao_code": "YTEST",
        }
        changed = {**first, "baseline_ols_ruleset": "uk_caa_cap168_edition_13"}
        self.assertEqual(runtime_input_fingerprint(first), runtime_input_fingerprint(reordered))
        self.assertNotEqual(runtime_input_fingerprint(first), runtime_input_fingerprint(changed))


if __name__ == "__main__":
    unittest.main()
