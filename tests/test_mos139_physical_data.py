"""MOS 139 physical-dimension policy tests."""

import unittest

from rulesets.mos139.physical_data import get_strip_params


class Mos139PhysicalDataTests(unittest.TestCase):
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
