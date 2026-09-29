"""Figure 6 N1 benchmark.

An ``a``-branching NFA with a self-loop and a final ``b`` transition.
P2-language: ⌀
"""

from automata.fa.nfa import NFA


def build_nfa() -> NFA:
    """Build the Figure 6 N1 NFA."""

    return NFA(
        states={"s0", "s1", "s2", "s3", "s4"},
        input_symbols={"a", "b"},
        transitions={
            "s0": {"a": {"s1", "s2"}},
            "s1": {"a": {"s1"}},
            "s2": {"a": {"s2", "s3"}},
            "s3": {"b": {"s4"}},
        },
        initial_state="s0",
        final_states={"s1", "s4"},
    )
