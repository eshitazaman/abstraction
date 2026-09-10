"""Scaling sweep over IPC / FOND chain domains.

Usage:
    python scale_fond.py --domain beam-walk --scales 5 50 100 500 1000
    python scale_fond.py --domain all --scales 5 50 100 500 --csv fond_scaling.csv
"""

import argparse
import csv
import os
from time import perf_counter

from beam_walk import (
    build_beam_walk_nfa,
    expected_shortest_plan_length as beam_k,
)
from doors import (
    build_doors_nfa,
    expected_shortest_plan_length as doors_k,
)
from first_responders import (
    build_first_responders_nfa,
    expected_shortest_plan_length as fr_k,
)
from tireworld import (
    build_tireworld_nfa,
    expected_shortest_plan_length as tw_k,
)
from plan_automata import automata_based_plan_computation


DOMAINS = {
    "tireworld": (build_tireworld_nfa, tw_k, "IPPC 2006 Tireworld"),
    "beam-walk": (build_beam_walk_nfa, beam_k, "FOND-SAT beam-walk"),
    "doors": (build_doors_nfa, doors_k, "FOND-SAT doors"),
    "first-responders": (
        build_first_responders_nfa, fr_k, "IPPC first-responders"
    ),
}


def _nfa_transitions(nfa):
    return sum(
        len(s) for t in nfa.transitions.values() for s in t.values()
    )


def run_one(domain, N):
    builder, analytic_fn, _ = DOMAINS[domain]
    nfa = builder(N)
    t0 = perf_counter()
    result = automata_based_plan_computation(
        nfa, verbose=False, enumerate_plans=False, short_circuit=True,
    )
    wall = perf_counter() - t0
    s = result["stats"]
    analytic = analytic_fn(N)
    ok = s["shortest_plan_length"] == analytic
    print(
        f"{domain:<18} N={N:>5}  |S|={len(nfa.states):>6}  "
        f"|DFA_P1|={s['dfa_p1_states']:>6}  |prod|={s['product_states']:>7}  "
        f"k*={s['shortest_plan_length']:>6}  analytic={analytic:>6}  "
        f"{'OK' if ok else 'MISMATCH':<9}  wall={wall:8.3f}s",
        flush=True,
    )
    return {
        "domain": domain,
        "N": N,
        "|S|": len(nfa.states),
        "|delta|": _nfa_transitions(nfa),
        "|DFA_P1|": s["dfa_p1_states"],
        "|product|": s["product_states"],
        "|NFA_P2|": s["nfa_p2_reachable"],
        "k*": s["shortest_plan_length"],
        "analytic": analytic,
        "nonempty": s["language_nonempty"],
        "wall_s": round(wall, 4),
        "ok": ok,
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument(
        "--domain",
        choices=list(DOMAINS) + ["all"],
        default="all",
    )
    p.add_argument(
        "--scales", type=int, nargs="+",
        default=[5, 10, 50, 100, 500, 1000],
    )
    p.add_argument("--csv", type=str, default=None)
    args = p.parse_args()

    names = list(DOMAINS) if args.domain == "all" else [args.domain]
    rows = []
    for name in names:
        _, _, title = DOMAINS[name]
        print(f"\n=== {title} ===", flush=True)
        for N in args.scales:
            rows.append(run_one(name, N))

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
