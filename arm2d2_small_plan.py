"""
Scaled-down Arm2D2 that DOES admit a P1 ∧ P2 valid plan.

Design idea
-----------
Keep the *same* nondeterministic action structure as the full Arm2D2 (each
action rotates by either 10 or 15 degrees), but:

  * shrink the joint ranges so the whole state space is small, and
  * place the goal region against the upper saturation wall.

The wall collapses the {+10, +15} spread back to a singleton, so a
macro-state of the form {50, 55, 60} × {50, 55, 60} — which sits inside the
goal band — is reachable. This macro-state is fully contained in the goal,
so it is an accepting DFA_P1 state and therefore L(NFA_P2) is non-empty.
"""

from collections import deque
from time import perf_counter

from automata.fa.nfa import NFA

from plan_automata import automata_based_plan_computation


def enumerate_plans_by_moves(nfa_p2, max_moves=12, max_plans=200):
    """
    Enumerate accepted plans of NFA_P2 as tuples of alphabet symbols
    (avoids the character-length bug of the built-in string-concatenation
    enumerator for multi-character alphabets like {'rr1','rl1',...}).

    Args:
        nfa_p2: the NFA_P2 dict returned by compute_nfa_p2.
        max_moves: maximum plan length in number of moves (not characters).
        max_plans: stop once this many distinct plans have been collected.

    Returns:
        Sorted list of plan tuples (shortest first).
    """
    if nfa_p2["initial"] is None:
        return []

    finals = nfa_p2["finals"]
    transitions = nfa_p2["transitions"]
    plans = set()

    def dfs(state, moves):
        if len(plans) >= max_plans:
            return
        if state in finals:
            plans.add(tuple(moves))
            if len(plans) >= max_plans:
                return
        if len(moves) >= max_moves:
            return
        for symbol, succs in transitions.get(state, {}).items():
            for succ in succs:
                moves.append(symbol)
                dfs(succ, moves)
                moves.pop()
                if len(plans) >= max_plans:
                    return

    dfs(nfa_p2["initial"], [])
    return sorted(plans, key=lambda w: (len(w), w))


X1 = list(range(0, 61, 5))
X2 = list(range(0, 61, 5))

INITIAL_X1 = 0
INITIAL_X2 = 0

X1_MIN, X1_MAX = 0, 60
X2_MIN, X2_MAX = 0, 60

GOAL_X1_LOW, GOAL_X1_HIGH = 50, 60
GOAL_X2_LOW, GOAL_X2_HIGH = 50, 60

ACTIONS = {"rr1", "rl1", "rr2", "rl2"}


def state_name(x1, x2):
    def fmt(x):
        return f"m{abs(x)}" if x < 0 else str(x)
    return f"q_{fmt(x1)}_{fmt(x2)}"


def sat1(x):
    return min(X1_MAX, max(X1_MIN, x))


def sat2(x):
    return min(X2_MAX, max(X2_MIN, x))


def build_nfa():
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
        if GOAL_X1_LOW <= x1 <= GOAL_X1_HIGH
        and GOAL_X2_LOW <= x2 <= GOAL_X2_HIGH
    }

    return NFA(
        states=states,
        input_symbols=ACTIONS,
        transitions=transitions,
        initial_state=initial_state,
        final_states=final_states,
    )


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Small Arm2D2 through the plan_automata pipeline."
    )
    parser.add_argument(
        "--no-enumerate",
        action="store_true",
        help="Skip enumeration of accepted plan words (default: enumerate).",
    )
    parser.add_argument(
        "--max-plan-length",
        type=int,
        default=12,
        help="How many plan words to preview (default 12).",
    )
    parser.add_argument(
        "--max-moves",
        type=int,
        default=10,
        help="Max plan length in moves for enumeration (default 10).",
    )
    parser.add_argument(
        "--max-plans",
        type=int,
        default=200,
        help="Stop enumeration after collecting this many plans (default 200).",
    )
    args = parser.parse_args()

    print("=" * 60)
    print("Arm2D2 (scaled-down, saturation-friendly)")
    print("=" * 60)

    t0 = perf_counter()
    nfa = build_nfa()
    build_secs = perf_counter() - t0

    nfa_trans = sum(
        len(succs)
        for trans in nfa.transitions.values()
        for succs in trans.values()
    )
    print(f"Build time:            {build_secs:.2f} s")
    print(f"x1 range:              {X1}")
    print(f"x2 range:              {X2}")
    print(
        f"Goal region:           "
        f"x1 in [{GOAL_X1_LOW}, {GOAL_X1_HIGH}], "
        f"x2 in [{GOAL_X2_LOW}, {GOAL_X2_HIGH}]"
    )
    print(f"Number of states:      {len(nfa.states)}")
    print(f"Number of transitions: {nfa_trans}")
    print(f"Initial state:         {nfa.initial_state}")
    print(f"Number of final states:{len(nfa.final_states):>4}")
    print(f"Alphabet:              {sorted(nfa.input_symbols)}")

    t0 = perf_counter()
    result = automata_based_plan_computation(
        nfa,
        verbose=True,
        enumerate_plans=False,
    )
    pipeline_secs = perf_counter() - t0

    print("\n" + "=" * 70)
    print("SUMMARY (small Arm2D2)")
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

    if not args.no_enumerate and stats["language_nonempty"]:
        max_moves = max(args.max_moves, stats["shortest_plan_length"] or 0)
        print(
            f"\nEnumerating accepted plans up to {max_moves} moves "
            f"(cap {args.max_plans} plans)..."
        )
        t0 = perf_counter()
        plans = enumerate_plans_by_moves(
            result["nfa_p2"],
            max_moves=max_moves,
            max_plans=args.max_plans,
        )
        enum_secs = perf_counter() - t0
        print(f"Found {len(plans)} plan(s) in {enum_secs:.2f} s.")
        preview = min(len(plans), args.max_plan_length)
        print(f"Showing first {preview} (shortest first):")
        for p in plans[:preview]:
            print(f"  {' '.join(p)}")
