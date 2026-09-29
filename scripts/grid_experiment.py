#!/usr/bin/env python3
"""Run random grid-world instances and checkpoint their planning results.

Example:
    .venv/bin/python scripts/grid_experiment.py --n 5 --action-mode north-bias

The CSV is appended and flushed after every completed run, so completed rows
remain available if a later instance is expensive or the process is stopped.
"""

from __future__ import annotations

import argparse
import csv
import gc
import os
import resource
import secrets
import sys
import threading
from pathlib import Path
from time import perf_counter

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from models.grid_world.grid_world_nfa import ACTION_PRESETS, generate_grid_world_nfa, sample_random_obstacles
from plan_automata import automata_based_plan_computation


RUNS = 100
CSV_COLUMNS = (
    "run",
    "seed",
    "n",
    "obstacles",
    "action_mode",
    "backend",
    "classification",
    "runtime_seconds",
    "rss_mib_before",
    "rss_mib_after",
    "rss_mib_delta",
    "run_peak_rss_mib",
    "run_peak_rss_increase_mib",
    "process_peak_rss_mib",
    "nfa_states",
    "dfa_p1_states",
    "product_states",
    "nfa_p2_states",
    "nfa_states_transitions",
    "dfa_p1_transitions",
    "product_transitions",
    "nfa_p2_transitions",
    "nfa_final_states",
    "dfa_p1_final_states",
    "product_final_states",
    "nfa_p2_final_states",
    "p2_iterations",
    "error",
    "total_attempts",
    "total_runtime_seconds",
    "average_runtime_seconds",
    "checkpointed_runs",
    "has_plan_runs",
    "no_plan_runs",
)


def current_rss_mib() -> float:
    """Return this process's current resident memory on Linux."""
    pages = int(Path("/proc/self/statm").read_text().split()[1])
    return pages * os.sysconf("SC_PAGE_SIZE") / (1024 * 1024)


def peak_rss_mib() -> float:
    """Return the process high-water RSS in MiB (Linux ru_maxrss is KiB)."""
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024


class PeakMemorySampler:
    """Sample RSS while one run executes and retain its peak value."""

    def __init__(
        self,
        initial_rss_mib: float,
        interval_seconds: float = 0.01,
    ):
        self.peak_rss_mib = initial_rss_mib
        self.interval_seconds = interval_seconds
        self.stop_event = threading.Event()
        self.thread = threading.Thread(target=self._sample, daemon=True)

    def _record_rss(self, rss_mib: float) -> None:
        self.peak_rss_mib = max(self.peak_rss_mib, rss_mib)

    def _sample(self) -> None:
        while not self.stop_event.wait(self.interval_seconds):
            self._record_rss(current_rss_mib())

    def start(self) -> None:
        self.thread.start()

    def stop(self) -> float:
        self.stop_event.set()
        self.thread.join()
        self._record_rss(current_rss_mib())
        return self.peak_rss_mib


def empty_statistics() -> dict:
    """Return blank CSV values for an instance that raises an exception."""
    return {column: "" for column in CSV_COLUMNS if column not in {
        "run", "seed", "n", "obstacles", "action_mode", "backend", "classification",
        "runtime_seconds", "rss_mib_before", "rss_mib_after", "rss_mib_delta",
        "run_peak_rss_mib", "run_peak_rss_increase_mib", "process_peak_rss_mib", "error",
    }}


def run_instance(
    n: int,
    obstacle_count: int,
    action_mode: str,
    seed: int,
    backend: str,
) -> dict:
    """Build one random grid, run the selected planner, and return its metrics."""
    obstacles = sample_random_obstacles(n, obstacle_count, {(1, 1), (n, n)}, seed)
    nfa, _ = generate_grid_world_nfa(
        n=n,
        robot_start=(1, 1),
        goal=(n, n),
        obstacles=obstacles,
        action_mode=action_mode,
        verbose=False,
    )
    result = automata_based_plan_computation(
        nfa,
        verbose=False,
        enumerate_plans=False,
        backend=backend,
        compute_shortest_plan=False,
    )
    stats = result["stats"]
    return {
        "classification": "has plan" if result["language_nonempty"] else "does not have plan",
        "nfa_states": stats["nfa_states"],
        "dfa_p1_states": stats["dfa_p1_states"],
        "product_states": stats["product_states"],
        "nfa_p2_states": stats["nfa_p2_reachable"],
        "nfa_states_transitions": stats["nfa_transitions"],
        "dfa_p1_transitions": stats["dfa_p1_transitions"],
        "product_transitions": stats["product_transitions"],
        "nfa_p2_transitions": stats["nfa_p2_transitions"],
        "nfa_final_states": stats["nfa_finals"],
        "dfa_p1_final_states": stats["dfa_p1_finals"],
        "product_final_states": stats["product_finals"],
        "nfa_p2_final_states": stats["nfa_p2_finals"],
        "p2_iterations": stats.get("p2_iterations", ""),
    }


def write_checkpoint(writer: csv.DictWriter, handle, row: dict) -> None:
    """Persist one row before beginning the next instance."""
    writer.writerow(row)
    handle.flush()
    os.fsync(handle.fileno())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n", required=True, type=int, help="Grid side length.")
    parser.add_argument("--action-mode", choices=sorted(ACTION_PRESETS), default="north-bias")
    parser.add_argument("--backend", choices=("compact", "explicit"), default="compact",
                        help="Planner representation (default: compact).")
    parser.add_argument("--obstacles", type=int, help="Random obstacles per run (default: 2 × n).")
    run_count = parser.add_mutually_exclusive_group()
    run_count.add_argument(
        "--target-per-class",
        type=int,
        help=(
            "Required saved runs in each classification "
            f"(default: {RUNS})."
        ),
    )
    run_count.add_argument(
        "--runs",
        type=int,
        help="Run exactly this many instances and save every outcome.",
    )
    parser.add_argument("--csv", type=Path, default=Path("grid_experiment.csv"))
    args = parser.parse_args()

    obstacle_count = 2 * args.n if args.obstacles is None else args.obstacles
    if args.n < 2:
        parser.error("--n must be at least 2")
    if args.runs is not None and args.runs < 1:
        parser.error("--runs must be positive")
    if args.target_per_class is not None and args.target_per_class < 1:
        parser.error("--target-per-class must be positive")
    if not 0 <= obstacle_count <= args.n * args.n - 2:
        parser.error("--obstacles must leave the start and goal cells free")

    target_per_class = (
        RUNS if args.runs is None and args.target_per_class is None
        else args.target_per_class
    )
    new_file = not args.csv.exists() or args.csv.stat().st_size == 0
    has_plan = 0
    no_plan = 0
    checkpointed_runs = 0
    total_start = perf_counter()
    with args.csv.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_COLUMNS)
        if new_file:
            writer.writeheader()
            handle.flush()
            os.fsync(handle.fileno())

        run = 0
        while (
            run < args.runs
            if args.runs is not None
            else has_plan < target_per_class or no_plan < target_per_class
        ):
            run += 1
            gc.collect()
            seed = secrets.randbits(64)
            rss_before = current_rss_mib()
            started = perf_counter()
            memory_sampler = PeakMemorySampler(rss_before)
            memory_sampler.start()
            row = {
                "run": run,
                "seed": seed,
                "n": args.n,
                "obstacles": obstacle_count,
                "action_mode": args.action_mode,
                "backend": args.backend,
                "rss_mib_before": round(rss_before, 3),
            }
            keep_row = False
            try:
                row.update(run_instance(
                    args.n, obstacle_count, args.action_mode, seed, args.backend
                ))
                if args.runs is not None:
                    keep_row = True
                    if row["classification"] == "has plan":
                        has_plan += 1
                    else:
                        no_plan += 1
                elif row["classification"] == "has plan":
                    keep_row = has_plan < target_per_class
                    if keep_row:
                        has_plan += 1
                else:
                    keep_row = no_plan < target_per_class
                    if keep_row:
                        no_plan += 1
                row["error"] = ""
            except Exception as exc:
                row.update(empty_statistics())
                row["classification"] = "error"
                row["error"] = f"{type(exc).__name__}: {exc}"
                keep_row = True
            finally:
                run_peak_rss = memory_sampler.stop()
                rss_after = current_rss_mib()
                row["runtime_seconds"] = round(perf_counter() - started, 6)
                row["rss_mib_after"] = round(rss_after, 3)
                row["rss_mib_delta"] = round(rss_after - rss_before, 3)
                row["run_peak_rss_mib"] = round(run_peak_rss, 3)
                row["run_peak_rss_increase_mib"] = round(run_peak_rss - rss_before, 3)
                row["process_peak_rss_mib"] = round(peak_rss_mib(), 3)
                if keep_row:
                    elapsed_seconds = perf_counter() - total_start
                    row["total_attempts"] = run
                    row["total_runtime_seconds"] = round(elapsed_seconds, 6)
                    row["average_runtime_seconds"] = round(
                        elapsed_seconds / run, 6
                    )
                    row["checkpointed_runs"] = checkpointed_runs + 1
                    row["has_plan_runs"] = has_plan
                    row["no_plan_runs"] = no_plan
                    write_checkpoint(writer, handle, row)
                    checkpointed_runs += 1

            status = "saved" if keep_row else "discarded"
            if args.runs is not None:
                progress = f"runs={run}/{args.runs}"
            else:
                progress = (
                    f"has-plan={has_plan}/{target_per_class}; "
                    f"no-plan={no_plan}/{target_per_class}"
                )
            print(f"run {run}: {row['classification']} ({status}; "
                  f"{row['runtime_seconds']:.3f}s, seed={seed}; {progress})",
                  flush=True)

    total_seconds = perf_counter() - total_start
    print(f"\nhas plan: {has_plan}")
    print(f"does not have plan: {no_plan}")
    print(f"total attempts: {run}")
    print(f"CSV rows saved: {checkpointed_runs}")
    print(f"total runtime: {total_seconds:.3f}s")
    print(f"average runtime: {total_seconds / run:.3f}s")
    print(f"CSV checkpoints: {args.csv}")


if __name__ == "__main__":
    main()
