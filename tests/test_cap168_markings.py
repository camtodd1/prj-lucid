import unittest

from rulesets.cap168.markings import (
    CAP168_THRESHOLD_MARKING_REF,
    threshold_marking_params,
    threshold_marking_ref,
)
from rulesets.cap168.profile import CAP168_PROFILE


class Cap168MarkingTests(unittest.TestCase):
    def test_threshold_table_uses_cap168_standard_widths(self):
        self.assertEqual(
            [threshold_marking_params(width)[0] for width in (18.0, 23.0, 30.0, 45.0)],
            [4, 6, 8, 12],
        )
        self.assertIsNone(threshold_marking_params(60.0))
        self.assertEqual(threshold_marking_params(30.0, "Non-Precision Approach (NPA)"), (6, 0.9))

    def test_threshold_reference_is_exposed_by_profile(self):
        self.assertEqual(threshold_marking_ref(), CAP168_THRESHOLD_MARKING_REF)
        self.assertEqual(CAP168_PROFILE.threshold_marking_ref(), CAP168_THRESHOLD_MARKING_REF)


if __name__ == "__main__":
    unittest.main()
