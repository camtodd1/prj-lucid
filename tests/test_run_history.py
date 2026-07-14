"""Tests for the append-only GUI/headless runtime ledger."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core.run_history import RuntimeRunRecorder, detect_run_agent


class RunHistoryTests(unittest.TestCase):
    def test_agent_detection_distinguishes_gui_headless_and_override(self):
        self.assertEqual(detect_run_agent({}), "qgis user")
        self.assertEqual(detect_run_agent({"QT_QPA_PLATFORM": "offscreen"}), "codex headless")
        self.assertEqual(
            detect_run_agent({"SAFEGUARDING_BUILDER_RUN_AGENT": "release workstation"}),
            "release workstation",
        )

    def test_finish_appends_versioned_json_line_with_context_and_timings(self):
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

            stored = json.loads(history_path.read_text(encoding="utf-8").strip())
            self.assertEqual(stored, record)
            self.assertEqual(stored["schema_version"], 1)
            self.assertEqual(stored["agent"], "codex headless")
            self.assertEqual(stored["airport"], "YBBN")
            self.assertEqual(stored["commit_ref"], "abc123def456")
            self.assertEqual(stored["plugin_version"], "2.4")
            self.assertEqual(stored["qgis_version"], "4.0-test")
            self.assertEqual(stored["rulesets"]["comparison_ols"], "easa_cs_adr_dsn_issue_7")
            self.assertEqual(stored["ruleset_labels"]["design"], "MOS139 (C.07 2026)")
            timings = {item["name"]: item for item in stored["modules"]}
            self.assertEqual(timings["controlling_ols.regions"]["elapsed_seconds"], 1.25)
            self.assertIn("phase.inputs", timings)
            self.assertIn("phase.controlling_envelope", timings)

    def test_each_finish_appends_a_separate_record(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            history_path = root / "runs.txt"
            with patch.dict("os.environ", {"SAFEGUARDING_BUILDER_COMMIT": "test-ref"}):
                for status in ("aborted", "cancelled"):
                    RuntimeRunRecorder(root, history_path=history_path).finish(status)
            records = [json.loads(line) for line in history_path.read_text(encoding="utf-8").splitlines()]
            self.assertEqual([record["status"] for record in records], ["aborted", "cancelled"])


if __name__ == "__main__":
    unittest.main()
