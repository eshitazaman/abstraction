#!/usr/bin/env python3
"""Compute the complete valid-plan regex for every benchmark model.

Run from the repository root, for example:

    .venv/bin/python scripts/benchmark_regexes.py
    .venv/bin/python scripts/benchmark_regexes.py --backend compact
"""

from __future__ import annotations

import argparse
import ast
from importlib import import_module
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
BENCHMARKS = ROOT / "models" / "benchmarks"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def benchmark_modules() -> list[str]:
    """Return benchmark module names that expose ``build_nfa``."""

    return sorted(
        path.stem
        for path in BENCHMARKS.glob("*.py")
        if path.name != "__init__.py" and any(
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name == "build_nfa"
            for node in ast.parse(
                path.read_text(encoding="utf-8"), filename=path.name
            ).body
        )
    )


def regex_for(module_name: str, backend: str) -> str:
    """Build one benchmark NFA and return its complete plan regex."""

    from plan_automata import automata_based_plan_computation, nfa_p2_to_regex

    module = import_module(f"models.benchmarks.{module_name}")
    result = automata_based_plan_computation(
        module.build_nfa(),
        backend=backend,
        enumerate_plans=False,
        verbose=False,
    )
    return nfa_p2_to_regex(result["nfa_p2"])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--backend",
        choices=("all", "explicit", "compact"),
        default="compact",
        help="planner representation to use (default: both)",
    )
    args = parser.parse_args()
    backends = ("explicit", "compact") if args.backend == "all" else (args.backend,)

    for module_name in benchmark_modules():
        for backend in backends:
            print(f"{module_name} [{backend}]: {regex_for(module_name, backend)}")


if __name__ == "__main__":
    main()
