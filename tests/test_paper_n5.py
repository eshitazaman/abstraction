"""Figure 6 N5 must have the P2-language reported in the paper."""

import unittest

from models.benchmarks.f6_n5 import build_nfa
from plan_automata import automata_based_plan_computation


class PaperN5Tests(unittest.TestCase):
    def test_all_representations_remove_dead_belief_closure(self):
        nfa = build_nfa()
        for backend in ("explicit", "compact"):
            with self.subTest(backend=backend):
                result = automata_based_plan_computation(
                    nfa, backend=backend, verbose=False
                )
                self.assertEqual(result["valid_plans"], {"a b", "a a b"})
                self.assertEqual(result["stats"]["nfa_p2_reachable"], 6)
                self.assertEqual(result["stats"]["nfa_p2_transitions"], 7)


if __name__ == "__main__":
    unittest.main()
