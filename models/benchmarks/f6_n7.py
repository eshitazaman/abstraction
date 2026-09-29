"""Figure 6 N7 benchmark.

A looping ``a`` route with an alternative ``c`` path to a final state.
P2-language: aa*(aa + c)
"""

from automata.fa.nfa import NFA


def build_nfa() -> NFA:
    """Build the Figure 6 N7 NFA."""

    return NFA(
        states={"s0", "s1", "s2", "s3", "s4", "s5"},
        input_symbols={"a", "b", "c"},
        transitions={
            "s0": {"a": {"s1", "s2"}},
            "s1": {"a": {"s1"}, "b": {"s5"}, "c": {"s3"}},
            "s2": {"a": {"s4"}},
            "s4": {"c": {"s3"}},
        },
        initial_state="s0",
        final_states={"s3", "s1"},
    )
