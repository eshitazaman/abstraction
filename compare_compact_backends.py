"""Compare the dense-mask and sparse-CSR compact planner backends."""

import argparse
import json
from pathlib import Path
import resource
import subprocess
import sys
from time import perf_counter


BACKENDS = ("compact", "compact-csr")


def run_worker(model_file, backend):
    from plan_automata import automata_based_plan_computation
    from plts_to_nfa import build_nfa_from_file

    started = perf_counter()
    nfa = build_nfa_from_file(model_file)
    result = automata_based_plan_computation(
        nfa,
        backend=backend,
        enumerate_plans=False,
        verbose=False,
    )
    return {
        "backend": backend,
        "elapsed_seconds": perf_counter() - started,
        "peak_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        "transition_storage_bytes": result["transition_storage_bytes"],
        "stats": result["stats"],
    }


def run_isolated(model_file, backend):
    command = [
        sys.executable,
        str(Path(__file__).resolve()),
        "--worker",
        "--file",
        model_file,
        "--backend",
        backend,
    ]
    completed = subprocess.run(
        command,
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(completed.stdout)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", default="salon-12-0.25.kr")
    parser.add_argument("--backend", choices=BACKENDS)
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()

    if args.worker:
        print(json.dumps(run_worker(args.file, args.backend)))
        return

    results = [run_isolated(args.file, backend) for backend in BACKENDS]
    reference = results[0]["stats"]
    if any(result["stats"] != reference for result in results[1:]):
        raise SystemExit("backend results differ")

    print(f"Model: {args.file}")
    print("Results: identical")
    print(f"{'Backend':<14} {'Time (s)':>10} {'Peak RSS':>12} {'Transitions':>14}")
    for result in results:
        rss_mib = result["peak_rss_kib"] / 1024
        storage_mib = result["transition_storage_bytes"] / (1024 * 1024)
        print(
            f"{result['backend']:<14} {result['elapsed_seconds']:>10.3f} "
            f"{rss_mib:>9.1f} MiB {storage_mib:>11.2f} MiB"
        )


if __name__ == "__main__":
    main()
