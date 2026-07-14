"""Tests for the append-only GUI/headless runtime ledger."""

from __future__ import annotations

import csv
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core.run_history import RuntimeRunRecorder, detect_run_agent, migrate_history_file


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
                airport="YBBN",
                design_ruleset="mos139_2019",
                baseline_ruleset="mos139_2019",
                comparison_ruleset="easa_cs_adr_dsn_issue_7",
                design_ruleset_label="MOS139 (C.07 2026)",
                baseline_ruleset_label="MOS139 (C.07 2026)",
                comparison_ruleset_label="EASA CS-ADR-DSN Issue 7",
            )
            recorder.start_phase("inputs")
            recorder.start_phase("controlling_envelope")
            recorder.add_timing("controlling_ols.regions", 1.25)
            with patch.dict("os.environ", {"SAFEGUARDING_BUILDER_COMMIT": "abc123def456"}):
                record = recorder.finish("completed")

            stored = _rows(history_path)[0]
            self.assertEqual(record["schema_version"], 2)
            self.assertEqual(stored["schema_version"], "2")
            self.assertEqual(stored["agent"], "codex headless")
            self.assertEqual(stored["airport"], "YBBN")
            self.assertEqual(stored["commit_ref"], "abc123def456")
            self.assertEqual(stored["plugin_version"], "2.4")
            self.assertEqual(stored["qgis_version"], "4.0-test")
            self.assertEqual(stored["comparison_ols_ruleset"], "easa_cs_adr_dsn_issue_7")
            self.assertEqual(stored["design_ruleset_label"], "MOS139 (C.07 2026)")
            timings = json.loads(stored["module_timings_json"])
            self.assertEqual(timings["controlling_ols.regions"]["elapsed_seconds"], 1.25)
            self.assertEqual(stored["controlling_regions_seconds"], "1.25")
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


if __name__ == "__main__":
    unittest.main()
