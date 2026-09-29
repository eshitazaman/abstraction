#!/usr/bin/env python3
"""Run Arm2D2 models once each and checkpoint their planning results.

With no positional arguments, runs every Arm2D2 model. Provide one or more
dotted model names to select a subset. Each model is deterministic, so it is
run only once. Completed rows in the CSV are checkpoints and are skipped when
the command is run again.

Examples:
    .venv/bin/python scripts/tab_exp_arm2d2_benchmark.py
    .venv/bin/python scripts/tab_exp_arm2d2_benchmark.py \
        arm2d2.r10_center_clamp
"""

from __future__ import annotations

import argparse
import csv
import gc
import os
import re
import resource
import sys
import threading
from pathlib import Path
from time import perf_counter

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from plan_automata import automata_based_plan_computation, discover_models, load_model


CSV_COLUMNS = (
    "model", "backend", "classification", "shortest_plan_length", "runtime_seconds", "rss_mib_before",
    "rss_mib_after", "rss_mib_delta", "run_peak_rss_mib",
    "run_peak_rss_increase_mib", "process_peak_rss_mib", "nfa_states",
    "dfa_p1_states", "product_states", "nfa_p2_states",
    "nfa_states_transitions", "dfa_p1_transitions", "product_transitions",
    "nfa_p2_transitions", "nfa_final_states", "dfa_p1_final_states",
    "product_final_states", "nfa_p2_final_states", "p2_iterations", "error",
)

# Keep the standard 24-model center/right comparison matrix. The r1 model and
# three r10 variants are special cases outside that matrix.
EXCLUDED_MODELS = frozenset({
    "arm2d2.r1_center_clamp",
    "arm2d2.r10_center_clamp_short",
    "arm2d2.r10_left_block",
    "arm2d2.r10_center_block_drift",
    "arm2d2.one_joint",
})


def arm2d2_model_order(model_id: str) -> tuple[int, str]:
    """Order Arm2D2 models from the smallest resolution to the largest."""
    match = re.fullmatch(r"arm2d2\.r(\d+)_.+", model_id)
    if match is None:
        raise ValueError(f"Arm2D2 model name has no grid resolution: {model_id}")
    # In this model family r10 is the smallest abstraction and r1 the largest.
    return -int(match.group(1)), model_id


def current_rss_mib() -> float:
    """Return this process's current resident memory on Linux."""
    pages = int(Path("/proc/self/statm").read_text().split()[1])
    return pages * os.sysconf("SC_PAGE_SIZE") / (1024 * 1024)


def peak_rss_mib() -> float:
    """Return the process high-water RSS in MiB (Linux ru_maxrss is KiB)."""
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024


class PeakMemorySampler:
    """Sample RSS while one model executes to capture its observed peak."""

    def __init__(self, initial_rss_mib: float, interval_seconds: float = 0.01):
        self.peak_rss_mib = initial_rss_mib
        self.interval_seconds = interval_seconds
        self.stop_event = threading.Event()
        self.thread = threading.Thread(target=self._sample, daemon=True)

    def _sample(self) -> None:
        while not self.stop_event.wait(self.interval_seconds):
            self.peak_rss_mib = max(self.peak_rss_mib, current_rss_mib())

    def start(self) -> None:
        self.thread.start()

    def stop(self) -> float:
        self.stop_event.set()
        self.thread.join()
        self.peak_rss_mib = max(self.peak_rss_mib, current_rss_mib())
        return self.peak_rss_mib


def empty_statistics() -> dict:
    """Return blank CSV values for a model that raises an exception."""
    return {column: "" for column in CSV_COLUMNS if column not in {
        "model", "backend", "classification", "runtime_seconds", "rss_mib_before",
        "rss_mib_after", "rss_mib_delta", "run_peak_rss_mib",
        "run_peak_rss_increase_mib", "process_peak_rss_mib", "error",
    }}


def run_model(model_id: str, backend: str) -> dict:
    """Build one Arm2D2 model, run the planner, and return its metrics."""
    nfa = load_model(model_id)
    result = automata_based_plan_computation(
        nfa, verbose=False, enumerate_plans=False, backend=backend,
        compute_shortest_plan=True,
    )
    stats = result["stats"]
    return {
        "classification": "has plan" if result["language_nonempty"] else "does not have plan",
        "shortest_plan_length": result["shortest_plan_length"],
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
    """Persist one row before beginning the next model."""
    writer.writerow(row)
    handle.flush()
    os.fsync(handle.fileno())


def checkpointed_models(csv_path: Path, backend: str) -> set[str]:
    """Return model IDs already recorded by a compatible checkpoint table."""
    if not csv_path.exists() or csv_path.stat().st_size == 0:
        return set()
    with csv_path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != CSV_COLUMNS:
            raise ValueError(
                f"{csv_path} does not have the Arm2D2 experiment CSV header; "
                "choose a new --csv path or remove the incompatible file"
            )
        rows = list(reader)
        saved_backends = {row.get("backend") for row in rows if row.get("model")}
        if saved_backends and saved_backends != {backend}:
            raise ValueError(
                f"{csv_path} contains checkpoints for backend(s) "
                f"{', '.join(sorted(saved_backends))}; choose a new --csv path"
            )
        return {row["model"] for row in rows if row.get("model")}


def main() -> None:
    arm2d2_models = tuple(sorted(
        (
            model for model in discover_models()
            if model.startswith("arm2d2.") and model not in EXCLUDED_MODELS
        ),
        key=arm2d2_model_order,
    ))
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("models", nargs="*", choices=arm2d2_models,
                        help="Models to run (default: every Arm2D2 model)")
    parser.add_argument("--backend", choices=("compact", "explicit"), default="compact",
                        help="Planner representation (default: compact)")
    parser.add_argument("--csv", type=Path, default=Path("arm2d2_experiment.csv"),
                        help="Checkpoint table to append to (default: arm2d2_experiment.csv)")
    args = parser.parse_args()

    selected = args.models or list(arm2d2_models)
    try:
        completed_models = checkpointed_models(args.csv, args.backend)
    except ValueError as exc:
        parser.error(str(exc))
    pending_models = [model for model in selected if model not in completed_models]
    new_file = not args.csv.exists() or args.csv.stat().st_size == 0

    total_start = perf_counter()
    checkpointed_runs = 0
    print(f"backend={args.backend}; models={len(selected)}; pending={len(pending_models)}", flush=True)
    with args.csv.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_COLUMNS)
        if new_file:
            writer.writeheader()
            handle.flush()
            os.fsync(handle.fileno())

        for index, model_id in enumerate(pending_models, start=1):
            gc.collect()
            rss_before = current_rss_mib()
            started = perf_counter()
            memory_sampler = PeakMemorySampler(rss_before)
            memory_sampler.start()
            row = {
                "model": model_id,
                "backend": args.backend,
                "rss_mib_before": round(rss_before, 3),
            }
            try:
                row.update(run_model(model_id, args.backend))
                row["error"] = ""
            except Exception as exc:
                row.update(empty_statistics())
                row["classification"] = "error"
                row["error"] = f"{type(exc).__name__}: {exc}"
            finally:
                run_peak_rss = memory_sampler.stop()
                rss_after = current_rss_mib()
                row["runtime_seconds"] = round(perf_counter() - started, 6)
                row["rss_mib_after"] = round(rss_after, 3)
                row["rss_mib_delta"] = round(rss_after - rss_before, 3)
                row["run_peak_rss_mib"] = round(run_peak_rss, 3)
                row["run_peak_rss_increase_mib"] = round(run_peak_rss - rss_before, 3)
                row["process_peak_rss_mib"] = round(peak_rss_mib(), 3)
                write_checkpoint(writer, handle, row)
                checkpointed_runs += 1

            print(f"model {index}/{len(pending_models)}: {model_id}: {row['classification']} "
                  f"(saved; {row['runtime_seconds']:.3f}s)", flush=True)

    total_seconds = perf_counter() - total_start
    print(f"\nmodels requested: {len(selected)}")
    print(f"models already checkpointed: {len(selected) - len(pending_models)}")
    print(f"CSV rows saved: {checkpointed_runs}")
    print(f"total runtime: {total_seconds:.3f}s")
    print(f"CSV checkpoints: {args.csv}")


if __name__ == "__main__":
    main()
