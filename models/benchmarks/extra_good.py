"""Figure 6 N5 benchmark.

An ``a``-branching NFA whose right branch can reach a dead state.
P2-language: ab+aab
"""

from automata.fa.nfa import NFA


def build_nfa() -> NFA:
    """Build the Figure 6 N5 NFA."""

    return NFA(
        states={
            "s0", "s1", "s2", "s3", "s4", "s5", 
            "s6", "s7", "s8", "s9", "s10"
        },
        input_symbols={"a", "b"},
        transitions={
            "s0": {"a": {"s1", "s2"}},
            "s1": {"a": {"s1"}, "b": {"s3"}},
            "s2": {"a": {"s4"}, "b": {"s7"}},
            "s3": {"b": {"s5"}},
            "s4": {"a": {"s8"}, "b": {"s6"}},
            "s6": {"b": {"s5"}},
            "s7": {"b": {"s7"}},
            "s8": {"a": {"s9"}, "b": {"s7"}},
            "s9": {"b": {"s10"}}
        },
        initial_state="s0",
        final_states={"s3", "s5", "s10"},
    )
