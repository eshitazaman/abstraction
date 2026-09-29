"""Figure 6 N2 benchmark.

An ``a``-branching NFA with separate ``b`` and ``c`` paths to final states.
P2-language: aac + aaa*b
"""

from automata.fa.nfa import NFA


def build_nfa() -> NFA:
    """Build the Figure 6 N2 NFA."""

    return NFA(
        states={"s0", "s1", "s2", "s3", "s4", "s5", "s6"},
        input_symbols={"a", "b", "c"},
        transitions={
            "s0": {"a": {"s1", "s2"}},
            "s1": {"a": {"s1", "s3"}},
            "s2": {"a": {"s4"}},
            "s3": {"b": {"s5"}},
            "s4": {"c": {"s6"}},
        },
        initial_state="s0",
        final_states={"s5", "s6"},
    )
