"""Figure 6 N4 benchmark.

Two ``a`` branches that converge through a final ``b`` transition.
P2-language: aa*b
"""

from automata.fa.nfa import NFA


def build_nfa() -> NFA:
    """Build the Figure 6 N4 NFA."""

    return NFA(
        states={"s0", "s1", "s2", "s3", "s4"},
        input_symbols={"a", "b"},
        transitions={
            "s0": {"a": {"s1", "s2"}},
            "s1": {"a": {"s1"}, "b": {"s3"}},
            "s2": {"a": {"s4"}},
            "s4": {"b": {"s3"}},
        },
        initial_state="s0",
        final_states={"s3"},
    )
