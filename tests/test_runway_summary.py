"""Tests for the Markdown runway summary report."""

from __future__ import annotations

import unittest
from datetime import datetime

from reports.runway_summary import render_markdown_report


class RunwaySummaryTests(unittest.TestCase):
    def test_icao_code_is_uppercase_in_report_title(self):
        report = render_markdown_report(
            "ymml",
            None,
            [],
            generated_at=datetime(2026, 1, 1, 12, 0),
        )

        self.assertIn("Critical Runway Information Summary - YMML", report)
        self.assertNotIn("ymml", report)


if __name__ == "__main__":
    unittest.main()
