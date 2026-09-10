"""
Run the Arm2D2 NFA through the automata-based plan computation pipeline
(plan_automata.automata_based_plan_computation).

Arm2D2 model
------------
Two-joint planar arm.
  x1 in {0, 5, 10, ..., 180}      (shoulder, clamped to [0, 180])
  x2 in {-30, -25, ..., 210}      (elbow,    clamped to [-30, 210])

Actions (each action is a *nondeterministic* rotation by either 10 or 15
degrees, clamped at the joint limits):
  rr1: rotate joint 1 clockwise         (x1 -> sat1(x1 - 10)  |  sat1(x1 - 15))
  rl1: rotate joint 1 counterclockwise  (x1 -> sat1(x1 + 10)  |  sat1(x1 + 15))
  rr2: rotate joint 2 clockwise         (x2 -> sat2(x2 - 10)  |  sat2(x2 - 15))
  rl2: rotate joint 2 counterclockwise  (x2 -> sat2(x2 + 10)  |  sat2(x2 + 15))

Initial state:  (60, 30)
Goal region:    85 <= x1 <= 100 and 40 <= x2 <= 60
"""

from time import perf_counter

from automata.fa.nfa import NFA

from plan_automata import automata_based_plan_computation


# ---------------------------------------------------------
# Arm2D2 parameters
# ---------------------------------------------------------

X1 = list(range(0, 181, 5))
X2 = list(range(-30, 211, 5))

INITIAL_X1 = 60
INITIAL_X2 = 30

ACTIONS = {"rr1", "rl1", "rr2", "rl2"}


# ---------------------------------------------------------
# Helper functions
# ---------------------------------------------------------

def state_name(x1, x2):
    """Encode a joint configuration as a string state name."""
    def fmt(x):
        return f"m{abs(x)}" if x < 0 else str(x)
    return f"q_{fmt(x1)}_{fmt(x2)}"


def sat1(x):
    """Clamp shoulder angle to [0, 180]."""
    return min(180, max(0, x))


def sat2(x):
    """Clamp elbow angle to [-30, 210]."""
    return min(210, max(-30, x))


# ---------------------------------------------------------
# Construct the NFA
# ---------------------------------------------------------

def build_arm2d2_nfa():
    states = {state_name(x1, x2) for x1 in X1 for x2 in X2}

    transitions = {}
    for x1 in X1:
        for x2 in X2:
            current = state_name(x1, x2)
            transitions[current] = {
                "rr1": {
                    state_name(sat1(x1 - 10), x2),
                    state_name(sat1(x1 - 15), x2),
                },
                "rl1": {
                    state_name(sat1(x1 + 10), x2),
                    state_name(sat1(x1 + 15), x2),
                },
                "rr2": {
                    state_name(x1, sat2(x2 - 10)),
                    state_name(x1, sat2(x2 - 15)),
                },
                "rl2": {
                    state_name(x1, sat2(x2 + 10)),
                    state_name(x1, sat2(x2 + 15)),
                },
            }

    initial_state = state_name(INITIAL_X1, INITIAL_X2)

    final_states = {
        state_name(x1, x2)
        for x1 in X1
        for x2 in X2
        if 85 <= x1 <= 100 and 40 <= x2 <= 60
    }

    return NFA(
        states=states,
        input_symbols=ACTIONS,
        transitions=transitions,
        initial_state=initial_state,
        final_states=final_states,
    )


# ---------------------------------------------------------
# Main
# ---------------------------------------------------------

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Run the Arm2D2 NFA through plan_automata."
    )
    parser.add_argument(
        "--enumerate",
        action="store_true",
        help=(
            "Enumerate all valid plan words up to the default length bound. "
            "For Arm2D2 this can be extremely large; off by default."
        ),
    )
    parser.add_argument(
        "--max-dfa-p1-states",
        type=int,
        default=None,
        help=(
            "Hard cap on DFA_P1 macro-states. If crossed, the pipeline "
            "returns an 'inconclusive within budget' verdict instead of "
            "continuing. Default: no cap (full construction)."
        ),
    )
    parser.add_argument(
        "--max-product-states",
        type=int,
        default=None,
        help="Hard cap on product states. Default: no cap.",
    )
    args = parser.parse_args()

    print("=" * 60)
    print("Arm2D2 NFA")
    print("=" * 60)
    t0 = perf_counter()
    arm2d2 = build_arm2d2_nfa()
    build_secs = perf_counter() - t0

    nfa_trans = sum(
        len(succs)
        for trans in arm2d2.transitions.values()
        for succs in trans.values()
    )

    print(f"Build time:            {build_secs:.2f} s")
    print(f"Number of states:      {len(arm2d2.states)}")
    print(f"Number of transitions: {nfa_trans}")
    print(f"Initial state:         {arm2d2.initial_state}")
    print(f"Number of final states:{len(arm2d2.final_states):>4}")
    print(f"Alphabet:              {sorted(arm2d2.input_symbols)}")

    t0 = perf_counter()
    result = automata_based_plan_computation(
        arm2d2,
        verbose=True,
        enumerate_plans=args.enumerate,
        max_dfa_p1_states=args.max_dfa_p1_states,
        max_product_states=args.max_product_states,
    )
    pipeline_secs = perf_counter() - t0

    print("\n" + "=" * 70)
    print("SUMMARY (Arm2D2)")
    print("=" * 70)
    stats = result["stats"]
    print(
        f"{'Component':<28} {'States':>12} {'Transitions':>14} {'Finals':>10}"
    )
    print("-" * 70)
    print(
        f"{'Input NFA':<28} "
        f"{stats['nfa_states']:>12} {stats['nfa_transitions']:>14} "
        f"{stats['nfa_finals']:>10}"
    )
    print(
        f"{'DFA_P1':<28} "
        f"{stats['dfa_p1_states']:>12} {stats['dfa_p1_transitions']:>14} "
        f"{stats['dfa_p1_finals']:>10}"
    )
    print(
        f"{'Product (NFA x DFA_P1)':<28} "
        f"{stats['product_states']:>12} {stats['product_transitions']:>14} "
        f"{stats['product_finals']:>10}"
    )
    print(
        f"{'NFA_P2 (reachable)':<28} "
        f"{stats['nfa_p2_reachable']:>12} {stats['nfa_p2_transitions']:>14} "
        f"{stats['nfa_p2_finals']:>10}"
    )
    print(
        f"{'NFA_P2 (unreachable)':<28} "
        f"{stats['nfa_p2_unreachable']:>12} {'-':>14} {'-':>10}"
    )
    print("-" * 70)
    print(f"L(NFA_P2) non-empty:       {stats['language_nonempty']}")
    print(f"Shortest valid plan length:{stats['shortest_plan_length']}")
    print(f"Pipeline wall time:        {pipeline_secs:.2f} s")
    if result.get("short_circuit_reason"):
        tag = "INCONCLUSIVE" if result["inconclusive"] else "SHORT-CIRCUIT"
        print(f"{tag}: {result['short_circuit_reason']}")

    if args.enumerate and result["valid_plans"] is not None:
        plans = sorted(result["valid_plans"], key=lambda w: (len(w), w))
        print(f"\nEnumerated {len(plans)} plan words (default max length).")
        for p in plans[:10]:
            print(f"  {p}")
        if len(plans) > 10:
            print(f"  ... and {len(plans) - 10} more")
