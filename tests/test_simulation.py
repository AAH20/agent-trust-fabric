import copy
import json
import unittest
from pathlib import Path

from agent_trust_fabric.simulation import simulate, validate_scenario


FIXTURE = json.loads((Path(__file__).resolve().parents[1] / "fixtures/support-rollout-scenario.json").read_text())


class SimulationTests(unittest.TestCase):
    def test_replay_is_exact_and_budget_is_counted(self):
        first = simulate(FIXTURE)
        self.assertEqual(first, simulate(FIXTURE))
        self.assertEqual(first["agent_steps"], 240 * 12 * 40 * 3)
        self.assertEqual(set(first["arms"]), {"baseline", "quality-investment", "discount-campaign"})

    def test_zero_effect_arm_is_exactly_paired(self):
        case = copy.deepcopy(FIXTURE)
        case["runs"] = 3
        case["interventions"] = [{"name": "same", "start_step": 5, "changes": {"quality": case["baseline"]["quality"]}}]
        effects = simulate(case)["paired_effects"]["same"]
        self.assertTrue(all(values["mean"] == 0 for values in effects.values()))

    def test_budget_and_malformed_input_fail_closed(self):
        case = copy.deepcopy(FIXTURE)
        case["runs"] = 200
        case["population"] = 5000
        with self.assertRaisesRegex(ValueError, "exceeds"):
            validate_scenario(case)
        case = copy.deepcopy(FIXTURE)
        case["interventions"][0]["changes"]["quality"] = 1.1
        with self.assertRaises(ValueError):
            validate_scenario(case)
        case = copy.deepcopy(FIXTURE)
        case["segments"][0]["share"] = 0.4
        with self.assertRaisesRegex(ValueError, "sum to one"):
            validate_scenario(case)

    def test_observation_scoring_is_labeled_and_separate_from_counterfactuals(self):
        case = copy.deepcopy(FIXTURE)
        case["runs"] = 4
        case["observations"] = [{"step": 1, "active_share": 0.12}, {"step": 4, "active_share": 0.22}]
        result = simulate(case)
        self.assertEqual(result["backtest"]["points"], 2)
        self.assertGreaterEqual(result["backtest"]["model_mae"], 0)
        self.assertIn("provenance not verified", result["backtest"]["scope"])


if __name__ == "__main__":
    unittest.main()
