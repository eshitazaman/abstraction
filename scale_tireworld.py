"""Scaling benchmark: nondeterministic Tireworld (IPPC family).

Sweeps the number of cities N and records pipeline metrics for the two-stage
NFA_P2 pipeline (short-circuit variant).  For every N we assert that the
pipeline's shortest plan length equals the analytic 2N-3.

Usage:
    python scale_tireworld.py --scales 5 10 20 50 100 200 500 --csv tw_scaling.csv
"""

import argparse
import csv
import os
from time import perf_counter

from tireworld import build_tireworld_nfa, expected_shortest_plan_length
from plan_automata import (
    automata_based_plan_computation,
    automata_based_plan_on_the_fly,
)


VARIANTS = {
    "pure": ("pure two-stage",
             lambda nfa, **kw: automata_based_plan_computation(
                 nfa, short_circuit=False, **kw)),
    "short-circuit": ("short-circuit two-stage",
                      lambda nfa, **kw: automata_based_plan_computation(
                          nfa, short_circuit=True, **kw)),
    "otf": ("on-the-fly",
            lambda nfa, **kw: automata_based_plan_on_the_fly(nfa, **kw)),
}


def _nfa_transitions(nfa):
    return sum(
        len(s) for t in nfa.transitions.values() for s in t.values()
    )


def run_one(N, variant, budget_dfa_p1, budget_product, verbose):
    label, runner = VARIANTS[variant]

    nfa = build_tireworld_nfa(N)
    n_trans = _nfa_transitions(nfa)

    kw = {"verbose": verbose, "enumerate_plans": False}
    if variant in ("pure", "short-circuit"):
        kw["max_dfa_p1_states"] = budget_dfa_p1
        kw["max_product_states"] = budget_product
    else:
        kw["max_product_states"] = budget_product

    t0 = perf_counter()
    result = runner(nfa, **kw)
    wall = perf_counter() - t0

    s = result["stats"]
    row = {
        "N": N,
        "|S|": len(nfa.states),
        "|delta|": n_trans,
        "|F|": len(nfa.final_states),
        "variant": variant,
        "wall_s": round(wall, 4),
        "|DFA_P1|": s["dfa_p1_states"],
        "DFA_P1_finals": s["dfa_p1_finals"],
        "|product|": s["product_states"],
        "product_finals": s["product_finals"],
        "|NFA_P2|": s["nfa_p2_reachable"],
        "language_nonempty": s["language_nonempty"],
        "shortest_plan": s["shortest_plan_length"],
        "analytic": expected_shortest_plan_length(N),
    }

    ok = row["shortest_plan"] == row["analytic"]
    tag = "OK" if ok else "MISMATCH"
    print(
        f"N={N:>4}  |S|={row['|S|']:>5}  |DFA_P1|={row['|DFA_P1|']:>7}  "
        f"|prod|={row['|product|']:>9}  |NFA_P2|={row['|NFA_P2|']:>9}  "
        f"k*={row['shortest_plan']:>5}  analytic={row['analytic']:>5}  "
        f"{tag}  wall={wall:>8.3f}s",
        flush=True,
    )
    return row


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--scales", type=int, nargs="+",
                   default=[5, 10, 20, 50, 100, 200, 500, 1000])
    p.add_argument("--variant", choices=sorted(VARIANTS),
                   default="short-circuit")
    p.add_argument("--budget-dfa-p1", type=int, default=None)
    p.add_argument("--budget-product", type=int, default=None)
    p.add_argument("--verbose", action="store_true")
    p.add_argument("--csv", type=str, default=None)
    args = p.parse_args()

    rows = []
    print(f"variant: {args.variant}\n")
    for N in args.scales:
        try:
            row = run_one(
                N=N,
                variant=args.variant,
                budget_dfa_p1=args.budget_dfa_p1,
                budget_product=args.budget_product,
                verbose=args.verbose,
            )
        except Exception as exc:  # noqa: BLE001
            print(f"  !! N={N} raised {type(exc).__name__}: {exc}")
            continue
        rows.append(row)

    if args.csv and rows:
        write_header = not os.path.exists(args.csv)
        with open(args.csv, "a", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            if write_header:
                w.writeheader()
            for r in rows:
                w.writerow(r)
        print(f"\nappended {len(rows)} rows to {args.csv}")


if __name__ == "__main__":
    main()
