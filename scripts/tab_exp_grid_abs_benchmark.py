#!/usr/bin/env python3
"""Benchmark the random-obstacle grid models used in the experiment table.

By default this reports NFA and DFA_P1 sizes. Pass ``--p2`` to run the full
P1/P2 pipeline; this can require substantial time and memory at grid size 10
and above because DFA_P1 is a subset construction.

P2 runs decide only whether a valid plan exists. Pass ``--shortest-plan`` to
also calculate and print one shortest plan.
"""

from __future__ import annotations

import argparse
import json
import secrets
import sys
from collections import deque
from pathlib import Path
from time import perf_counter

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from models.grid_world.grid_world_nfa import ACTION_PRESETS, generate_grid_world_nfa, sample_random_obstacles
from plan_automata import automata_based_plan_computation, nfa_to_dfa_p1


ROWS = ((5, 5), (10, 20), (15, 90), (20, 40), (25, 50))


def shortest_plan(nfa_p2: dict) -> list[str] | None:
    """Return one shortest accepted action sequence."""
    initial = nfa_p2["initial"]
    if initial is None:
        return None
    parents = {initial: None}
    queue = deque([initial])
    while queue:
        state = queue.popleft()
        if state in nfa_p2["finals"]:
            actions = []
            while parents[state] is not None:
                state, action = parents[state]
                actions.append(action)
            return list(reversed(actions))
        for action, successors in sorted(nfa_p2["transitions"].get(state, {}).items()):
            for successor in sorted(successors, key=str):
                if successor not in parents:
                    parents[successor] = (state, action)
                    queue.append(successor)
    return None


def run_row(
    n: int,
    m: int,
    seed: int,
    model: str,
    include_p2: bool,
    backend: str,
    compute_shortest_plan: bool,
) -> dict:
    """Build and measure one benchmark row in the current process."""
    start = perf_counter()
    obstacles = sample_random_obstacles(n, m, {(1, 1), (n, n)}, seed)
    nfa, _ = generate_grid_world_nfa(
        n=n,
        robot_start=(1, 1),
        goal=(n, n),
        obstacles=obstacles,
        action_mode=model,
        verbose=False,
    )
    record = {
        "n": n,
        "m": m,
        "seed": seed,
        "model": model,
        "nfa_states": len(nfa.states),
        "nfa_transitions": sum(len(targets) for edges in nfa.transitions.values() for targets in edges.values()),
    }
    if not include_p2:
        dfa = nfa_to_dfa_p1(nfa)
        record.update({
            "dfa_p1_states": len(dfa["states"]),
            "dfa_p1_transitions": sum(len(edges) for edges in dfa["transitions"].values()),
        })
    else:
        result = automata_based_plan_computation(
            nfa,
            verbose=False,
            enumerate_plans=False,
            backend=backend,
            compute_shortest_plan=compute_shortest_plan,
        )
        stats = result["stats"]
        record.update({key: stats[key] for key in (
            "dfa_p1_states", "dfa_p1_transitions", "nfa_p2_reachable",
            "nfa_p2_transitions", "language_nonempty", "shortest_plan_length",
        )})
        if compute_shortest_plan:
            record["shortest_plan"] = (
                result.get("shortest_plan_actions")
                if backend == "compact" else shortest_plan(result["nfa_p2"])
            )
    record["runtime_seconds"] = round(perf_counter() - start, 3)
    return record


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", choices=sorted(ACTION_PRESETS), default="north-bias")
    parser.add_argument("--only-n", type=int, choices=[n for n, _ in ROWS])
    seed_group = parser.add_mutually_exclusive_group()
    seed_group.add_argument("--seed", type=int, default=42,
                            help="Obstacle-layout seed (default: 42).")
    seed_group.add_argument("--random-seed", action="store_true",
                            help="Generate and print a fresh obstacle-layout seed.")
    parser.add_argument("--p2", action="store_true", help="Run the full P1/P2 pipeline.")
    parser.add_argument("--shortest-plan", action="store_true",
                        help="With --p2, also calculate and print one shortest plan.")
    parser.add_argument("--backend", choices=("explicit", "compact"), default="explicit",
                        help="P2 representation (used only with --p2).")
    parser.add_argument("--json-out", type=Path)
    args = parser.parse_args()
    if args.shortest_plan and not args.p2:
        parser.error("--shortest-plan requires --p2")

    seed = secrets.randbits(64) if args.random_seed else args.seed
    rows = [(n, m) for n, m in ROWS if args.only_n is None or n == args.only_n]
    records = []
    print(f"seed={seed}  model={args.model}  p2={args.p2}", flush=True)
    print("n  m  N(states,trans)  DFA_P1(states,trans)  NFA_P2(states,trans)  runtime", flush=True)
    for n, m in rows:
        record = run_row(
            n, m, seed, args.model, args.p2, args.backend, args.shortest_plan
        )
        records.append(record)
        p2 = (
            f"{record['nfa_p2_reachable']},{record['nfa_p2_transitions']}"
            if args.p2 else "—"
        )
        print(f"{n:<2} {m:<2} {record['nfa_states']},{record['nfa_transitions']}  "
              f"{record['dfa_p1_states']},{record['dfa_p1_transitions']}  "
              f"{p2}  {record['runtime_seconds']:.3f}s", flush=True)
        if args.p2 and args.shortest_plan:
            print(f"  nonempty={record['language_nonempty']}  "
                  f"shortest={record['shortest_plan_length']}  "
                  f"plan={record['shortest_plan']}", flush=True)
        elif args.p2:
            print(f"  nonempty={record['language_nonempty']}", flush=True)
    if args.json_out:
        args.json_out.write_text(json.dumps(records, indent=2) + "\n", encoding="utf-8")
        print(f"Wrote {args.json_out}")


if __name__ == "__main__":
    main()
