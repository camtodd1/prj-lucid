"""Contract tests for the operational and diagnostic run logs."""

from __future__ import annotations

import ast
import unittest
from pathlib import Path

from qgis.core import Qgis

from core.run_log import (
    DIAGNOSTIC_TAG,
    PLUGIN_TAG,
    EventKind,
    GenerationOutcome,
    LogEvent,
    OutcomeStatus,
    RunLog,
    render_event,
)


class RunLogTests(unittest.TestCase):
    def setUp(self):
        self.records = []

    def sink(self, message, tag, level):
        self.records.append((message, tag, int(level)))

    def test_event_rendering_is_one_line_and_uses_stable_field_order(self):
        event = LogEvent(
            EventKind.WARN,
            scope="file output\nwriter",
            consequence="one layer was not written",
            action="inspect destination",
            facts={"features": 9, "airport": "YBBN", "layers": 1, "zeta": "last"},
        )

        self.assertEqual(
            render_event(event),
            "WARN | scope=file output writer | consequence=one layer was not written | "
            "action=inspect destination | airport=YBBN | layers=1 | features=9 | zeta=last",
        )

    def test_run_has_one_start_one_terminal_and_exact_qgis_severities(self):
        run_log = RunLog(self.sink, diagnostics_enabled=False)
        run_log.start(crs="EPSG:28356")
        run_log.phase(1, 2, "inputs", "Reading inputs")
        run_log.skip("AGL", "option not enabled")
        run_log.warning("CNS", "one facility was omitted", aggregate=False)
        run_log.error("report", "writer rejected destination")
        run_log.finish("completed", airport="YBBN", layers=12, features=30)
        run_log.finish("completed", layers=12)

        messages = [record[0] for record in self.records]
        self.assertEqual(sum(message.startswith("START") for message in messages), 1)
        self.assertEqual(sum(message.startswith("DONE") for message in messages), 1)
        levels = {message.split(" ", 1)[0]: level for message, _tag, level in self.records}
        self.assertEqual(levels["START"], int(Qgis.Info))
        self.assertEqual(levels["SKIP"], int(Qgis.Info))
        self.assertEqual(levels["WARN"], int(Qgis.Warning))
        self.assertEqual(levels["ERROR"], int(Qgis.Critical))
        self.assertEqual(levels["DONE"], int(Qgis.Success))
        self.assertTrue(all(tag == PLUGIN_TAG for _message, tag, _level in self.records))

    def test_repeated_skips_are_aggregated_with_a_count(self):
        run_log = RunLog(self.sink, diagnostics_enabled=False)
        run_log.start()
        run_log.phase(1, 1, "outputs", "Writing outputs")
        run_log.skip("empty layer", "no features generated", surface="RESA")
        run_log.skip("empty layer", "no features generated", surface="RESA")
        run_log.finish("completed", layers=1)

        skip_messages = [
            message for message, _tag, _level in self.records if message.startswith("SKIP")
        ]
        self.assertEqual(len(skip_messages), 1)
        self.assertIn("count=2", skip_messages[0])
        self.assertIn("skips=2", self.records[-1][0])

    def test_diagnostics_are_opt_in_and_use_a_separate_tag(self):
        quiet = RunLog(self.sink, diagnostics_enabled=False)
        quiet.diagnostic("geometry", "candidate details")
        self.assertEqual(self.records, [])

        verbose = RunLog(self.sink, diagnostics_enabled=True)
        verbose.diagnostic("geometry", "candidate\ndetails")
        self.assertEqual(len(self.records), 1)
        self.assertEqual(self.records[0][1], DIAGNOSTIC_TAG)
        self.assertTrue(self.records[0][0].startswith("DIAG"))
        self.assertNotIn("\n", self.records[0][0])

    def test_legacy_messages_are_downgraded_or_normalised(self):
        run_log = RunLog(self.sink, diagnostics_enabled=False)
        run_log.legacy("[done] Created an intermediate layer", Qgis.Success)
        run_log.legacy("[skip] AGL: option not enabled", Qgis.Warning)
        run_log.legacy(
            "Critical error: report failed\nTraceback (most recent call last): details",
            Qgis.Critical,
        )
        run_log.flush()

        self.assertEqual(len(self.records), 2)
        self.assertTrue(self.records[0][0].startswith("ERROR"))
        self.assertNotIn("Traceback", self.records[0][0])
        self.assertTrue(self.records[1][0].startswith("SKIP"))
        self.assertEqual(self.records[1][2], int(Qgis.Info))

    def test_generation_outcomes_map_to_scan_friendly_events(self):
        run_log = RunLog(self.sink, diagnostics_enabled=False)
        run_log.record_outcome(
            GenerationOutcome("runway surfaces", OutcomeStatus.GENERATED, layers=3, features=8)
        )
        run_log.record_outcome(
            GenerationOutcome(
                "lighting",
                OutcomeStatus.SKIPPED_MISSING_INPUT,
                reason="no lighting inputs supplied",
            )
        )
        run_log.flush()

        self.assertTrue(self.records[0][0].startswith("OUTPUT"))
        self.assertTrue(self.records[1][0].startswith("SKIP"))

    def test_generation_outcome_can_be_retained_without_duplicate_event(self):
        run_log = RunLog(self.sink, diagnostics_enabled=False)
        outcome = GenerationOutcome(
            "controlling envelope",
            OutcomeStatus.GENERATED,
            layers=2,
            features=12,
        )

        run_log.record_outcome(outcome, emit=False)

        self.assertEqual(run_log.outcomes, [outcome])
        self.assertEqual(self.records, [])

    def test_failed_zero_output_terminal_explains_the_omission(self):
        run_log = RunLog(self.sink, diagnostics_enabled=False)
        run_log.start()
        run_log.finish("completed", layers=0, features=0)

        message, _tag, level = self.records[-1]
        self.assertTrue(message.startswith("FAILED"))
        self.assertIn("reason=no usable layers were generated", message)
        self.assertEqual(level, int(Qgis.Critical))

    def test_production_modules_do_not_bypass_the_logging_adapter(self):
        root = Path(__file__).resolve().parents[1]
        bypasses = []
        for path in root.rglob("*.py"):
            if "tests" in path.parts or path == root / "core" / "run_log.py":
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.module == "qgis.core":
                    if any(alias.name == "QgsMessageLog" for alias in node.names):
                        bypasses.append(str(path.relative_to(root)))
        self.assertEqual(bypasses, [])


if __name__ == "__main__":
    unittest.main()
