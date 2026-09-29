"""Figure 6 N5 benchmark.

An ``a``-branching NFA whose right branch can reach a dead state.
P2-language: ab+aab
"""

from automata.fa.nfa import NFA


def build_nfa() -> NFA:
    """Build the Figure 6 N5 NFA."""

    return NFA(
        states={"s0", "s1", "s2", "s3", "s4", "s5"},
        input_symbols={"a", "b"},
        transitions={
            "s0": {"a": {"s1", "s2"}},
            "s1": {"a": {"s1"}, "b": {"s3"}},
            "s2": {"a": {"s4"}},
            "s4": {"a": {"s5"}, "b": {"s3"}},
        },
        initial_state="s0",
        final_states={"s3"},
    )
