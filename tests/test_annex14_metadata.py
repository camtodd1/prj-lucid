"""Annex 14 profile metadata tests."""

import unittest

from rulesets.annex14.profile import ANNEX14_MODERNISED_OFS_OES_PROFILE


class Annex14MetadataTests(unittest.TestCase):
    def test_modernised_profile_records_automatic_workflow_policy(self):
        assumptions = " ".join(
            ANNEX14_MODERNISED_OFS_OES_PROFILE.assumptions
        )
        limitations = " ".join(
            ANNEX14_MODERNISED_OFS_OES_PROFILE.limitations
        )

        self.assertIn("straight-in", assumptions)
        self.assertIn("above-5,700 kg", assumptions)
        self.assertIn("ARC letter F", assumptions)
        self.assertIn("design ruleset", assumptions)
        self.assertIn("unadjusted standard table", assumptions)
        self.assertIn("Circling", limitations)
        self.assertIn("specific OES", limitations)
        self.assertIn("21 November 2030", limitations)


if __name__ == "__main__":
    unittest.main()
