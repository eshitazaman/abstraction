"""Scaling benchmark for the Arm2D2 model.

Sweeps the grid-refinement factor ``scale`` and reports pipeline metrics
(|DFA_P1|, |product|, |NFA_P2|, wall time, shortest plan length) so we can
plot algorithmic behaviour vs raw NFA size.

The physical geometry is fixed across scales: same joint ranges, same
Cartesian goal box, same initial pose.  Only the grid step and the leg
magnitudes shrink by ``1/scale``.

Usage
-----
    python scale_arm2d2.py --scales 1 2 5 --variant otf
    python scale_arm2d2.py --scales 1 2   --variant short-circuit
    python scale_arm2d2.py --scales 1     --variant pure
"""

import argparse
import csv
import sys
from time import perf_counter

from arm2d2_agustin import build_agustin_nfa, _grid_step, _legs
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


def run_one(scale, variant, budget_dfa_p1, budget_product, verbose):
    label, runner = VARIANTS[variant]

    nfa = build_agustin_nfa(scale=scale)
    step = _grid_step(scale)
    ls, ll = _legs(scale)
    n_trans = _nfa_transitions(nfa)

    print(
        f"\n=== scale={scale}  step={step}°  legs=({ls}°,{ll}°)  "
        f"|S|={len(nfa.states)}  |δ|={n_trans}  |F|={len(nfa.final_states)}"
        f"  variant={label} ===",
        flush=True,
    )

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
        "scale": scale,
        "grid_step_deg": step,
        "leg_short_deg": ls,
        "leg_long_deg": ll,
        "|S|": len(nfa.states),
        "|delta|": n_trans,
        "|F|": len(nfa.final_states),
        "variant": variant,
        "wall_s": round(wall, 3),
        "|DFA_P1|": s["dfa_p1_states"],
        "DFA_P1_finals": s["dfa_p1_finals"],
        "|product|": s["product_states"],
        "product_finals": s["product_finals"],
        "|NFA_P2|": s["nfa_p2_reachable"],
        "language_nonempty": s["language_nonempty"],
        "shortest_plan": s["shortest_plan_length"],
        "short_circuit_reason": result.get("short_circuit_reason"),
        "inconclusive": bool(result.get("inconclusive")),
    }
    print(
        f"    wall={wall:8.2f}s  "
        f"|DFA_P1|={row['|DFA_P1|']:>8}  acc={row['DFA_P1_finals']:>4}  "
        f"|prod|={row['|product|']:>10}  acc={row['product_finals']:>4}  "
        f"|NFA_P2|={row['|NFA_P2|']:>10}  "
        f"nonempty={row['language_nonempty']}  "
        f"k*={row['shortest_plan']}",
        flush=True,
    )
    if row["short_circuit_reason"]:
        tag = "INCONCLUSIVE" if row["inconclusive"] else "SHORT-CIRCUIT"
        print(f"    {tag}: {row['short_circuit_reason']}")
    return row


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--scales", type=int, nargs="+", default=[1, 2],
                   help="Scale factors to sweep (each must divide 10).")
    p.add_argument("--variant", choices=sorted(VARIANTS), default="otf",
                   help="Pipeline variant to benchmark.")
    p.add_argument("--budget-dfa-p1", type=int, default=None)
    p.add_argument("--budget-product", type=int, default=None)
    p.add_argument("--verbose", action="store_true")
    p.add_argument("--csv", type=str, default=None,
                   help="Append results as CSV to this file.")
    args = p.parse_args()

    rows = []
    for scale in args.scales:
        try:
            row = run_one(
                scale=scale,
                variant=args.variant,
                budget_dfa_p1=args.budget_dfa_p1,
                budget_product=args.budget_product,
                verbose=args.verbose,
            )
        except Exception as exc:  # noqa: BLE001
            print(f"  !! scale={scale} raised {type(exc).__name__}: {exc}",
                  file=sys.stderr)
            continue
        rows.append(row)

    print("\n" + "=" * 96)
    print("SUMMARY")
    print("=" * 96)
    hdr = ("scale", "|S|", "|delta|", "|F|", "|DFA_P1|", "|product|",
           "|NFA_P2|", "k*", "wall_s")
    print(("{:>5} " * 4 + "{:>10} {:>12} {:>12} {:>4} {:>10}").format(*hdr))
    for r in rows:
        print(("{:>5} {:>5} {:>5} {:>5} {:>10} {:>12} {:>12} {:>4} "
               "{:>10.2f}").format(
            r["scale"], r["|S|"], r["|delta|"], r["|F|"],
            r["|DFA_P1|"], r["|product|"], r["|NFA_P2|"],
            r["shortest_plan"] if r["shortest_plan"] is not None else "-",
            r["wall_s"],
        ))

    if args.csv:
        import os
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
