"""Equivalence tests for the compact bitmask planner."""

import random
import unittest

from automata.fa.nfa import NFA

from compact_plan_automata import (
    build_compact_dfa_p1,
    build_compact_dfa_p1_from_index,
    build_compact_product,
    compute_compact_nfa_p2,
    enumerate_valid_plans as enumerate_compact_plans,
    shortest_accepting_word,
)
from compact_csr_plan_automata import index_nfa_csr
from plan_automata import (
    automata_based_plan_computation,
    build_product_nfa_dfa_p1,
    compute_nfa_p2,
    enumerate_valid_plans as enumerate_explicit_plans,
    nfa_p2_language_nonempty,
    nfa_p2_shortest_accepting_length,
    nfa_to_dfa_p1,
    load_arm2d2_model,
)


def random_nfa(seed):
    rng = random.Random(seed)
    states = set(range(5))
    actions = {"a", "long_action", "z"}
    transitions = {}
    for source in states:
        transitions[source] = {}
        for action in actions:
            if rng.random() < 0.7:
                degree = rng.randint(1, 3)
                transitions[source][action] = set(rng.sample(tuple(states), degree))
    finals = {state for state in states if rng.random() < 0.4} or {4}
    return NFA(
        states=states,
        input_symbols=actions,
        transitions=transitions,
        initial_state=0,
        final_states=finals,
    )


def normalized_transitions(transitions):
    return {
        source: {
            action: frozenset(targets)
            for action, targets in action_map.items()
            if targets
        }
        for source, action_map in transitions.items()
        if any(action_map.values())
    }


class CompactPlannerParityTests(unittest.TestCase):
    def assert_automata_equal(self, explicit, compact):
        self.assertEqual(explicit["states"], compact["states"])
        self.assertEqual(explicit["initial"], compact["initial"])
        self.assertEqual(explicit["finals"], compact["finals"])
        self.assertEqual(
            normalized_transitions(explicit["transitions"]),
            normalized_transitions(compact["transitions"]),
        )

    def assert_pipeline_equal(self, nfa):
        explicit_dfa = nfa_to_dfa_p1(nfa, verbose=False)
        explicit_product = build_product_nfa_dfa_p1(
            nfa, explicit_dfa, verbose=False
        )
        explicit_p2 = compute_nfa_p2(explicit_product, verbose=False)

        compact_dfa = build_compact_dfa_p1(nfa)
        compact_product = build_compact_product(compact_dfa)
        compact_p2 = compute_compact_nfa_p2(compact_product)
        csr_dfa = build_compact_dfa_p1_from_index(index_nfa_csr(nfa))
        csr_product = build_compact_product(csr_dfa)
        csr_p2 = compute_compact_nfa_p2(csr_product)

        self.assert_automata_equal(explicit_dfa, compact_dfa.materialize())
        self.assert_automata_equal(explicit_product, compact_product.materialize())
        self.assert_automata_equal(explicit_p2, compact_p2.materialize())
        self.assert_automata_equal(explicit_dfa, csr_dfa.materialize())
        self.assert_automata_equal(explicit_product, csr_product.materialize())
        self.assert_automata_equal(explicit_p2, csr_p2.materialize())
        self.assertEqual(
            nfa_p2_language_nonempty(explicit_p2),
            compact_p2.language_nonempty,
        )
        self.assertEqual(
            enumerate_explicit_plans(explicit_p2, 4),
            enumerate_compact_plans(compact_p2, 4),
        )
        self.assertEqual(
            enumerate_explicit_plans(explicit_p2, 4),
            enumerate_compact_plans(csr_p2, 4),
        )
        shortest = shortest_accepting_word(compact_p2)
        self.assertEqual(
            None if shortest is None else len(shortest),
            nfa_p2_shortest_accepting_length(explicit_p2),
        )

    def test_seeded_random_automata_match_explicit_pipeline(self):
        for seed in range(20):
            with self.subTest(seed=seed):
                self.assert_pipeline_equal(random_nfa(seed))

    def test_public_backend_matches_explicit_result(self):
        nfa = random_nfa(42)
        explicit = automata_based_plan_computation(
            nfa, verbose=False, enumerate_plans=False
        )
        compact = automata_based_plan_computation(
            nfa, verbose=False, enumerate_plans=False, backend="compact"
        )

        self.assertEqual(explicit["language_nonempty"], compact["language_nonempty"])
        self.assertEqual(
            explicit["shortest_plan_length"], compact["shortest_plan_length"]
        )
        for metric in (
            "dfa_p1_states",
            "product_states",
            "nfa_p2_reachable",
            "nfa_p2_transitions",
        ):
            self.assertEqual(explicit["stats"][metric], compact["stats"][metric])

    def test_action_border_model_matches_explicit_backend(self):
        nfa = load_arm2d2_model("30d_goalRight_actionBorder")
        explicit = automata_based_plan_computation(
            nfa, verbose=False, enumerate_plans=False
        )
        compact = automata_based_plan_computation(
            nfa, verbose=False, enumerate_plans=False, backend="compact"
        )

        shared_metrics = explicit["stats"].keys() & compact["stats"].keys()
        self.assertEqual(
            {key: explicit["stats"][key] for key in shared_metrics},
            {key: compact["stats"][key] for key in shared_metrics},
        )


if __name__ == "__main__":
    unittest.main()
