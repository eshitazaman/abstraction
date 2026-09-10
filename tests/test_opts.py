"""
Smoke tests for the correctness of the optimizations added to
`plan_automata.automata_based_plan_computation`.
"""

from automata.fa.nfa import NFA

from plan_automata import automata_based_plan_computation, compute_reach_F


def _stats(nfa, **kwargs):
    return automata_based_plan_computation(nfa, verbose=False, **kwargs)


def test_leak_counter_example():
    """
    s0 --a--> {t1, t2}, t1 in F, t2 dead outside F.
    Original semantics: word "a" reaches {t1, t2} which is NOT a subset of F,
    so P1 rejects.  L(NFA_P2) must be empty.

    (Historically an unsound successor-filter shortcut wrongly accepted "a".)
    """
    nfa = NFA(
        states={"s0", "t1", "t2"},
        input_symbols={"a"},
        transitions={"s0": {"a": {"t1", "t2"}}, "t1": {}, "t2": {}},
        initial_state="s0",
        final_states={"t1"},
    )
    result = _stats(nfa, filter_dead_states=True)
    assert result["language_nonempty"] is False, result
    assert result["short_circuit_reason"] is not None
    return "PASS  leak counter-example ⇒ empty language"


def test_isolated_initial():
    """
    Initial state can't reach any final ⇒ pipeline short-circuits at the
    Reach_F check without touching subset construction.
    """
    nfa = NFA(
        states={"s0", "s1", "sf"},
        input_symbols={"a"},
        transitions={"s0": {"a": {"s1"}}, "s1": {"a": {"s0"}}, "sf": {}},
        initial_state="s0",
        final_states={"sf"},
    )
    result = _stats(nfa, filter_dead_states=True)
    assert result["language_nonempty"] is False, result
    assert result["stats"]["dfa_p1_states"] == 0, result["stats"]
    return "PASS  isolated initial ⇒ empty, DFA_P1 not built"


def test_paper_example_still_accepts_b():
    """
    The 'ab / aa / b / ba' NFA from the paper: L(NFA_P2) = {"b", "ba"}.
    """
    nfa = NFA(
        states={"s0", "s1", "s2", "s3"},
        input_symbols={"a", "b"},
        transitions={
            "s0": {"a": {"s1", "s2"}, "b": {"s2"}},
            "s1": {},
            "s2": {"a": {"s3"}},
            "s3": {},
        },
        initial_state="s0",
        final_states={"s2", "s3"},
    )
    result = _stats(nfa, filter_dead_states=True, enumerate_plans=True)
    assert result["language_nonempty"] is True
    assert result["valid_plans"] == {"b", "ba"}, result["valid_plans"]
    return "PASS  paper example ⇒ {b, ba}"


def test_budget_cap():
    """
    A tiny NFA whose DFA_P1 exceeds a 1-state cap. We should return
    'inconclusive' rather than crash.
    """
    nfa = NFA(
        states={"s0", "s1", "s2"},
        input_symbols={"a"},
        transitions={"s0": {"a": {"s1", "s2"}}, "s1": {}, "s2": {}},
        initial_state="s0",
        final_states={"s1", "s2"},
    )
    result = _stats(nfa, filter_dead_states=False, max_dfa_p1_states=1)
    assert result["inconclusive"] is True, result
    assert "DFA_P1 construction exceeded budget" in result[
        "short_circuit_reason"
    ]
    return "PASS  DFA_P1 budget cap ⇒ inconclusive, not crash"


if __name__ == "__main__":
    for t in (
        test_leak_counter_example,
        test_isolated_initial,
        test_paper_example_still_accepts_b,
        test_budget_cap,
    ):
        print(t())
