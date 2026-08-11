"""Declared-distance source mode checks."""

import unittest

from reports.declared_distances import apply_declared_distance_overrides


class DeclaredDistanceModeTests(unittest.TestCase):
    def test_calculated_mode_ignores_retained_published_values(self):
        records = [{"direction": "primary", "tora_m": 3704.653}]

        result = apply_declared_distance_overrides(
            {
                "declared_distance_mode": "calculated",
                "tora_override_1": 3700.0,
            },
            records,
        )[0]

        self.assertEqual(result["tora_m"], 3704.653)
        self.assertEqual(result["calc_tora_m"], 3704.653)
        self.assertEqual(result["calc_src"], "calculated")

    def test_published_mode_retains_calculated_value_for_comparison(self):
        records = [{"direction": "primary", "tora_m": 3704.653}]

        result = apply_declared_distance_overrides(
            {
                "declared_distance_mode": "published",
                "tora_override_1": 3700.0,
            },
            records,
        )[0]

        self.assertEqual(result["tora_m"], 3700.0)
        self.assertEqual(result["calc_tora_m"], 3704.653)
        self.assertEqual(result["calc_src"], "override")


if __name__ == "__main__":
    unittest.main()
