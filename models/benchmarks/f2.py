"""Figure 2 benchmark.

A four-state NFA with nondeterministic ``a`` and ``c`` transitions.
P2-language: (ab + aab)(ab)*
"""

from automata.fa.nfa import NFA


def build_nfa() -> NFA:
    """Build the Figure 2 NFA."""

    return NFA(
        states={"s0", "s1", "s2", "s3"},
        input_symbols={"a", "b", "c"},
        transitions={
            "s0": {"a": {"s2", "s3"}, "c": {"s1", "s2"}},
            "s2": {"a": {"s3"}},
            "s3": {"b": {"s2"}},
        },
        initial_state="s0",
        final_states={"s2"},
    )
