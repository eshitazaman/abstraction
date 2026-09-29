"""Figure 6 N3 benchmark.

A two-action NFA with branching paths to four final states.
P2-language: ba + bab
"""

from automata.fa.nfa import NFA


def build_nfa() -> NFA:
    """Build the Figure 6 N3 NFA."""

    return NFA(
        states={"s0", "s1", "s2", "s3", "s4", "s5", "s6", "s7", "s8"},
        input_symbols={"a", "b"},
        transitions={
            "s0": {"a": {"s2", "s3"}, "b": {"s1", "s3"}},
            "s1": {"a": {"s4"}},
            "s2": {"b": {"s4"}},
            "s3": {"a": {"s7"}, "b": {"s6"}},
            "s4": {"b": {"s5"}},
            "s6": {"b": {"s8"}},
        },
        initial_state="s0",
        final_states={"s2", "s4", "s5", "s7"},
    )
