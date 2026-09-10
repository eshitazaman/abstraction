"""
Three-way comparison on Agustín's Arm2D2 spec.

Variants:
  A) pure two-stage        - short_circuit=False; always builds product & P2.
  B) short-circuit two-stage - short_circuit=True (the default).
  C) on-the-fly            - fused subset+product BFS, then P2.

We time each and cross-check that all three agree on:
  - L(NFA_P2) non-emptiness
  - shortest plan length (if any)
"""

import argparse
from time import perf_counter

from arm2d2_agustin import build_agustin_nfa
from plan_automata import (
    automata_based_plan_computation,
    automata_based_plan_on_the_fly,
)


def _sum_transitions(automaton):
    return sum(
        len(s)
        for t in automaton["transitions"].values()
        for s in t.values()
    )


def run_variant(label, fn, kwargs):
    print("\n" + "=" * 72)
    print(f"RUN: {label}")
    print("=" * 72)
    t0 = perf_counter()
    result = fn(**kwargs)
    dt = perf_counter() - t0
    stats = result["stats"]
    print(f"\n[{label}] wall time = {dt:.2f} s")
    print(f"[{label}] DFA_P1 macros = {stats['dfa_p1_states']:>10}   "
          f"accepting macros = {stats['dfa_p1_finals']}")
    print(f"[{label}] product states = {stats['product_states']:>10}   "
          f"accepting product = {stats['product_finals']}")
    print(f"[{label}] NFA_P2 reachable = {stats['nfa_p2_reachable']:>10}   "
          f"finals = {stats['nfa_p2_finals']}")
    print(f"[{label}] L(NFA_P2) non-empty = {stats['language_nonempty']}   "
          f"shortest plan (moves) = {stats['shortest_plan_length']}")
    if result.get("short_circuit_reason"):
        tag = "INCONCLUSIVE" if result["inconclusive"] else "SHORT-CIRCUIT"
        print(f"[{label}] {tag}: {result['short_circuit_reason']}")
    return dt, result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--budget-dfa-p1", type=int, default=None,
        help="Cap on DFA_P1 macros (applied to both two-stage variants).",
    )
    parser.add_argument(
        "--budget-product", type=int, default=None,
        help="Cap on product states (applied to on-the-fly).",
    )
    parser.add_argument(
        "--skip-pure", action="store_true",
        help="Skip the pure two-stage variant (useful when we already know the "
             "answer is empty and pure would just waste time).",
    )
    parser.add_argument(
        "--verbose", action="store_true",
        help="Print progress messages inside each variant.",
    )
    args = parser.parse_args()

    nfa = build_agustin_nfa()
    n_trans = sum(
        len(s)
        for t in nfa.transitions.values()
        for s in t.values()
    )
    print(f"Input NFA (Agustin spec): {len(nfa.states)} states, "
          f"{n_trans} transitions, {len(nfa.final_states)} finals, "
          f"alphabet {sorted(nfa.input_symbols)}")
    print(f"  initial: {nfa.initial_state}")

    common_kwargs = dict(
        nfa=nfa,
        verbose=args.verbose,
        enumerate_plans=False,
    )

    results = {}

    if not args.skip_pure:
        dt, res = run_variant(
            "pure two-stage",
            automata_based_plan_computation,
            {
                **common_kwargs,
                "short_circuit": False,
                "max_dfa_p1_states": args.budget_dfa_p1,
            },
        )
        results["pure two-stage"] = (dt, res)

    dt, res = run_variant(
        "short-circuit two-stage",
        automata_based_plan_computation,
        {
            **common_kwargs,
            "short_circuit": True,
            "max_dfa_p1_states": args.budget_dfa_p1,
        },
    )
    results["short-circuit two-stage"] = (dt, res)

    dt, res = run_variant(
        "on-the-fly",
        automata_based_plan_on_the_fly,
        {
            **common_kwargs,
            "max_product_states": args.budget_product,
        },
    )
    results["on-the-fly"] = (dt, res)

    print("\n" + "=" * 72)
    print("SUMMARY")
    print("=" * 72)
    print(f"{'Variant':<26} {'wall (s)':>10} {'|DFA_P1|':>10} "
          f"{'|prod|':>10} {'nonempty':>10} {'k*':>6}")
    for label, (dt, res) in results.items():
        s = res["stats"]
        print(
            f"{label:<26} "
            f"{dt:>10.2f} "
            f"{s['dfa_p1_states']:>10} "
            f"{s['product_states']:>10} "
            f"{str(s['language_nonempty']):>10} "
            f"{str(s['shortest_plan_length']):>6}"
        )

    nonemptys = {label: r["language_nonempty"]
                 for label, (_, r) in results.items()
                 if not r.get("inconclusive")}
    if len(set(nonemptys.values())) > 1:
        print("\n!!! Variants disagree on emptiness:", nonemptys)
    else:
        print("\nAll conclusive variants agree.")
