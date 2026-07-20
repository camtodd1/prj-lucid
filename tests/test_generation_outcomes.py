import sys
import unittest
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORKSPACE.parent))

from safeguarding_builder.core.run_log import OutcomeStatus, RunLog  # noqa: E402
from safeguarding_builder.safeguarding_builder import SafeguardingBuilder  # noqa: E402


class _Layer:
    def __init__(self, features):
        self._features = features

    def featureCount(self):
        return self._features


class GenerationOutcomeTests(unittest.TestCase):
    def builder(self):
        builder = SafeguardingBuilder.__new__(SafeguardingBuilder)
        builder._generation_outcomes = []
        builder._run_log = RunLog(lambda *_args: None)
        builder.successfully_generated_layers = []
        return builder

    def test_builder_retains_json_safe_generation_outcome(self):
        builder = self.builder()

        outcome = builder._record_generation_outcome(
            "OLS ruleset comparison",
            OutcomeStatus.GENERATED,
            layers=8,
            features=120,
            facts={"baseline_ruleset": "baseline", "comparison_ruleset": "future"},
        )

        self.assertEqual(builder._run_log.outcomes, [outcome])
        self.assertEqual(
            builder.generation_outcome_snapshot(),
            [
                {
                    "scope": "OLS ruleset comparison",
                    "status": "generated",
                    "reason": None,
                    "layers": 8,
                    "features": 120,
                    "facts": {
                        "baseline_ruleset": "baseline",
                        "comparison_ruleset": "future",
                    },
                }
            ],
        )

    def test_generated_output_delta_counts_only_new_layers(self):
        builder = self.builder()
        builder.successfully_generated_layers = [_Layer(3), _Layer(5), _Layer(7)]

        self.assertEqual(builder._generated_output_delta(1), (2, 12))


if __name__ == "__main__":
    unittest.main()
