"""MOS 139 physical-dimension policy tests."""

import unittest

from rulesets.mos139.markings import (
    STARTER_EXTENSION_MARKING_REF,
    starter_extension_marking_rule,
)
from rulesets.mos139.physical_data import get_strip_params


class Mos139PhysicalDataTests(unittest.TestCase):
    def test_starter_extension_markings_use_the_runway_side_stripe_width(self):
        self.assertEqual(
            starter_extension_marking_rule(4, "Precision Approach CAT II/III", "Non-Instrument (NI)"),
            (0.9, STARTER_EXTENSION_MARKING_REF),
        )

    def test_non_instrument_overall_width_is_the_graded_strip_width(self):
        cases = {
            (1, 18.0): 60.0,
            (2, 23.0): 80.0,
            (3, 30.0): 90.0,
            (3, 45.0): 150.0,
            (4, 30.0): 150.0,
            (4, 45.0): 150.0,
        }
        for (code, runway_width), expected in cases.items():
            with self.subTest(code=code, runway_width=runway_width):
                params = get_strip_params(code, "NI", runway_width)
                self.assertEqual(params["graded_width"], expected)
                self.assertEqual(params["overall_width"], expected)
                self.assertIn(
                    "NI graded strip boundary",
                    params["overall_width_ref"],
                )

    def test_instrument_strip_retains_flyover_width(self):
        for runway_type in ("NPA", "PA_I", "PA_II_III"):
            for code, expected in ((1, 140.0), (2, 140.0), (3, 280.0), (4, 280.0)):
                with self.subTest(runway_type=runway_type, code=code):
                    params = get_strip_params(code, runway_type, 30.0)
                    self.assertEqual(params["overall_width"], expected)

    def test_precision_code_1_and_2_strip_width_is_140_metres(self):
        for code in (1, 2):
            with self.subTest(code=code):
                params = get_strip_params(code, "PA_I", 30.0)
                self.assertEqual(params["overall_width"], 140.0)

    def test_only_non_instrument_code_1_has_30_metre_extension(self):
        cases = {
            (1, "NI"): 30.0,
            (2, "NI"): 60.0,
            (1, "NPA"): 60.0,
            (1, "PA_I"): 60.0,
        }
        for (code, runway_type), expected in cases.items():
            with self.subTest(code=code, runway_type=runway_type):
                params = get_strip_params(code, runway_type, 30.0)
                self.assertEqual(params["extension_length"], expected)


if __name__ == "__main__":
    unittest.main()
