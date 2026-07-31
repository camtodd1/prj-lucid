"""Tests for the per-run obstacle limitation surface table report."""

from __future__ import annotations

import unittest
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory

from reports.ols_table import (
    build_ols_table_values,
    render_ols_table_markdown,
    write_ols_table_markdown,
)
from rulesets.mos139.profile import MOS139_PROFILE
from rulesets.ols_construction import (
    OlsConstructionContext,
    OlsRunwayContext,
    OlsRunwayEndContext,
)


def runway(
    name: str,
    index: int,
    length: float,
    width: float,
    primary_threshold: float,
    reciprocal_threshold: float,
    primary_end: float,
    reciprocal_end: float,
) -> OlsRunwayContext:
    primary_name, reciprocal_name = name.split("/")
    primary = OlsRunwayEndContext(
        direction="primary",
        designator=primary_name,
        threshold_point=None,
        threshold_elevation_m=primary_threshold,
        runway_end_elevation_m=primary_end,
        approach_type="Precision Approach CAT I",
        classified_type="PA_I",
    )
    reciprocal = OlsRunwayEndContext(
        direction="reciprocal",
        designator=reciprocal_name,
        threshold_point=None,
        threshold_elevation_m=reciprocal_threshold,
        runway_end_elevation_m=reciprocal_end,
        approach_type="Precision Approach CAT I",
        classified_type="PA_I",
    )
    return OlsRunwayContext(
        runway_id=name,
        original_index=index,
        arc_number=4,
        arc_letter="F",
        width_m=width,
        physical_length_m=length,
        threshold_length_m=length,
        primary_threshold_point=None,
        reciprocal_threshold_point=None,
        primary_physical_end_point=None,
        reciprocal_physical_end_point=None,
        strip_parameters={"overall_width": 300.0, "extension_length": 60.0},
        ends=(primary, reciprocal),
    )


class OlsTableReportTests(unittest.TestCase):
    def setUp(self):
        self.context = OlsConstructionContext(
            ruleset_id=MOS139_PROFILE.id,
            runways=(
                runway("01L/19R", 0, 3300.0, 60.0, 4.066, 4.066, 4.066, 4.066),
                runway("01R/19L", 1, 3560.0, 45.0, 3.6, 3.2, 3.3, 3.8),
            ),
            arp_elevation_m=3.962,
            reference_elevation_datum_m=3.5,
        )

    def test_report_resolves_values_used_by_current_mos139_construction(self):
        report = build_ols_table_values(
            "ybbn",
            MOS139_PROFILE,
            self.context,
            generated_at=datetime(2026, 7, 31, 9, 30),
            run_id="20260731T093000Z-a4f29c1e",
            test_case_id="ybbn_2rwy_parallel_mos_cap",
            input_fingerprint="abc123def456",
        )

        self.assertEqual(report["icao_code"], "YBBN")
        self.assertEqual(report["horizontal"]["outer_elevation"], 153.5)
        self.assertEqual(report["horizontal"]["inner_elevation"], 48.5)
        self.assertEqual(report["horizontal"]["inner_radius"], 4000.0)
        self.assertEqual(report["approach"][0]["first_section_length"], 3000.0)
        self.assertEqual(report["approach"][0]["second_section_length"], 3600.0)
        self.assertEqual(report["approach"][0]["horizontal_section_length"], 8400.0)
        self.assertEqual(report["approach"][0]["total_length"], 15000.0)
        self.assertEqual(report["takeoff"][0]["overall_length"], 15000.0)
        self.assertEqual(report["takeoff"][0]["slope"], 0.02)
        self.assertEqual(report["run_id"], "20260731T093000Z-a4f29c1e")

    def test_markdown_contains_all_table_sections_and_run_metadata(self):
        report = build_ols_table_values(
            "YBBN",
            MOS139_PROFILE,
            self.context,
            generated_at=datetime(2026, 7, 31, 9, 30),
            run_id="20260731T093000Z-a4f29c1e",
            test_case_id="ybbn_2rwy_parallel_mos_cap",
            input_fingerprint="abc123def456",
        )
        markdown = render_ols_table_markdown(report)

        for heading in (
            "### Horizontal surfaces",
            "### Approach surfaces",
            "### Transitional surfaces",
            "### Take-off climb surfaces",
        ):
            self.assertIn(heading, markdown)
        self.assertIn("01L/19R", markdown)
        self.assertIn("15,000", markdown)
        self.assertIn("2%", markdown)
        self.assertIn("2026-07-31 09:30:00", markdown)
        self.assertIn("20260731T093000Z-a4f29c1e", markdown)
        self.assertIn("ybbn_2rwy_parallel_mos_cap", markdown)
        self.assertIn("abc123def456", markdown)

    def test_markdown_writer_creates_utf8_report(self):
        report = build_ols_table_values(
            "YBBN",
            MOS139_PROFILE,
            self.context,
            generated_at=datetime(2026, 7, 31, 9, 30),
            run_id="20260731T093000Z-a4f29c1e",
        )
        with TemporaryDirectory() as temp_directory:
            output = Path(temp_directory) / "reports" / "YBBN_OLS_Table_of_Values.md"
            written = write_ols_table_markdown(report, output)

            self.assertEqual(written, str(output))
            self.assertIn(
                "# Obstacle Restriction and Limitation Surfaces Table of Values",
                output.read_text(encoding="utf-8"),
            )


if __name__ == "__main__":
    unittest.main()
