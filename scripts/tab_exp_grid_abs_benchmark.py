#!/usr/bin/env python3
"""
Reproduce tab:exp-grid rows for action preset north-bias+south:
    A = W ∪ N,  B = E ∪ N,  S = S only.

Uses the same random obstacle layouts as the paper experiments:
    sample_random_obstacles(..., seed=42), forbidding start (1,1) and goal (n,n).

By default prints NFA / DFA_P1 counts only --- finishing NFA_P2 on the full product can be
prohibitively expensive for (n,m)=(10,20) or (15,30) because |DFA_P1| can exceed millions.

Usage:
    .venv/bin/python scripts/tab_exp_grid_abs_benchmark.py
    .venv/bin/python scripts/tab_exp_grid_abs_benchmark.py --full-pipeline --only-n 5
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from grid_world_nfa import generate_grid_world_nfa, sample_random_obstacles  # noqa: E402
from plan_automata import automata_based_plan_computation, nfa_to_dfa_p1  # noqa: E402


SEED = 42


def latex_commas(n: int) -> str:
    return f"{n:,}".replace(",", "{,}")


def main() -> None:
    p = argparse.ArgumentParser(description="tab:exp-grid ABS (north-bias+south) benchmark")
    p.add_argument(
        "--full-pipeline",
        action="store_true",
        help="Also build product × NFA_P2 (can hang or exhaust memory at n≥10)",
    )
    p.add_argument(
        "--only-n",
        type=int,
        default=None,
        metavar="N",
        help="Run only grid side length N (5 / 10 / 15)",
    )
    p.add_argument(
        "--json-out",
        type=str,
        default=None,
        metavar="FILE",
        help="Write machine-readable summary JSON here",
    )
    args = p.parse_args()

    rows = [(5, 5), (10, 20), (15, 30)]
    if args.only_n is not None:
        rows = [(n, m) for (n, m) in rows if n == args.only_n]
        if not rows:
            raise SystemExit(f"No row for n={args.only_n}")

    records = []

    print(f"seed={SEED}  action_mode=north-bias+south\n")

    for n, m in rows:
        forbid = {(1, 1), (n, n)}
        obs = sample_random_obstacles(n=n, m=m, forbid=forbid, seed=SEED)
        nfa, _ = generate_grid_world_nfa(
            n=n,
            robot_start=(1, 1),
            goal=(n, n),
            obstacles=obs,
            action_mode="north-bias+south",
            verbose=False,
        )

        nfa_edges = sum(len(s) for t in nfa.transitions.values() for s in t.values())

        dfa = nfa_to_dfa_p1(nfa, verbose=False)
        dfa_groups = sum(len(t) for t in dfa["transitions"].values())

        rec = {
            "n": n,
            "m": m,
            "seed": SEED,
            "nfa_states": len(nfa.states),
            "nfa_transitions_edges": nfa_edges,
            "dfa_p1_states": len(dfa["states"]),
            "dfa_p1_transitions_groups": dfa_groups,
        }

        print(f">>> n={n} m={m}  |obs|={len(obs)}")
        print(
            f"    NFA    states={rec['nfa_states']:>8}  transitions(edges)={rec['nfa_transitions_edges']:>10}"
        )
        print(
            f"    DFA_P1 states={rec['dfa_p1_states']:>8}  transitions(groups)={rec['dfa_p1_transitions_groups']:>10}"
        )

        if args.full_pipeline:
            res = automata_based_plan_computation(
                nfa, verbose=True, enumerate_plans=False
            )
            st = res["stats"]
            rec.update(
                {
                    "nfa_p2_reachable": st["nfa_p2_reachable"],
                    "nfa_p2_unreachable": st["nfa_p2_unreachable"],
                    "nfa_p2_transitions_edges": st["nfa_p2_transitions"],
                    "language_nonempty": st["language_nonempty"],
                    "shortest_plan_length": st["shortest_plan_length"],
                }
            )
            r, u = st["nfa_p2_reachable"], st["nfa_p2_unreachable"]
            print(
                f"    NFA_P2 reachable={r} unreachable={u} trans(edges)={st['nfa_p2_transitions']} "
                f"nonempty={st['language_nonempty']} shortest={st['shortest_plan_length']}"
            )

            latex = (
                f"{n} & {m} & {st['nfa_states']} & {st['nfa_transitions']} & "
                f"{latex_commas(st['dfa_p1_states'])} & {latex_commas(st['dfa_p1_transitions'])} & "
                f"$[{r},{u}]$ & {st['nfa_p2_transitions']} \\\\"
            )
            print(f"    LaTeX: {latex}")

        records.append(rec)

    if args.json_out:
        Path(args.json_out).write_text(json.dumps(records, indent=2), encoding="utf-8")
        print(f"\nWrote {args.json_out}")

    if not args.full_pipeline:
        print(
            "\nNote: DFA_P1 counts above are exact for seed 42.\n"
            "Add --full-pipeline for NFA_P2 rows (safe at n=5; often infeasible at n≥10).\n"
            "Example:\n"
            "  .venv/bin/python scripts/tab_exp_grid_abs_benchmark.py --full-pipeline --only-n 5"
        )


if __name__ == "__main__":
    main()
