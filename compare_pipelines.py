"""
Side-by-side comparison of the two-stage vs on-the-fly automata pipelines
on a chosen NFA.

Usage:
    .venv/bin/python compare_pipelines.py --instance small
    .venv/bin/python compare_pipelines.py --instance full --budget 2000000
    .venv/bin/python compare_pipelines.py --instance paper
"""

import argparse
from time import perf_counter

from automata.fa.nfa import NFA

from plan_automata import (
    automata_based_plan_computation,
    automata_based_plan_on_the_fly,
)


def build_paper_example():
    """Tiny 4-state example (L(NFA_P2) = {b, ba})."""
    return NFA(
        states={"s0", "s1", "s2", "s3"},
        input_symbols={"a", "b"},
        transitions={
            "s0": {"a": {"s1", "s2"}, "b": {"s2"}},
            "s1": {},
            "s2": {"a": {"s3"}},
            "s3": {},
        },
        initial_state="s0",
        final_states={"s2", "s3"},
    )


def build_instance(kind):
    if kind == "small":
        from arm2d2_small_plan import build_nfa
        return build_nfa(), "small Arm2D2 (169 states, expects non-empty)"
    if kind == "full":
        from arm2d2_plan import build_arm2d2_nfa
        return build_arm2d2_nfa(), "full Arm2D2 (1813 states, expects empty)"
    if kind == "paper":
        return build_paper_example(), "paper example (4 states, non-empty)"
    raise ValueError(f"unknown instance kind: {kind}")


def run(name, fn, kwargs):
    print("\n" + "=" * 70)
    print(f"RUN: {name}")
    print("=" * 70)
    t0 = perf_counter()
    result = fn(**kwargs)
    dt = perf_counter() - t0
    stats = result["stats"]
    print(f"\n[{name}] wall time = {dt:.2f} s")
    print(
        f"[{name}] DFA_P1 macros seen = {stats['dfa_p1_states']:>10}   "
        f"accepting macros = {stats['dfa_p1_finals']}"
    )
    print(
        f"[{name}] product states     = {stats['product_states']:>10}   "
        f"accepting product = {stats['product_finals']}"
    )
    print(
        f"[{name}] NFA_P2 reachable   = {stats['nfa_p2_reachable']:>10}   "
        f"finals = {stats['nfa_p2_finals']}"
    )
    print(
        f"[{name}] L(NFA_P2) non-empty = {stats['language_nonempty']}   "
        f"shortest plan (moves) = {stats['shortest_plan_length']}"
    )
    if result.get("short_circuit_reason"):
        tag = "INCONCLUSIVE" if result["inconclusive"] else "SHORT-CIRCUIT"
        print(f"[{name}] {tag}: {result['short_circuit_reason']}")
    return dt, result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--instance",
        default="small",
        choices=("paper", "small", "full"),
        help="Benchmark to run (default: small).",
    )
    parser.add_argument(
        "--budget",
        type=int,
        default=None,
        help=(
            "Optional cap. Applied to DFA_P1 macros for two-stage and to "
            "product states for on-the-fly. Default: no cap."
        ),
    )
    parser.add_argument(
        "--verbose", action="store_true",
        help="Print intermediate progress messages.",
    )
    args = parser.parse_args()

    nfa, label = build_instance(args.instance)
    n_trans = sum(
        len(s)
        for t in nfa.transitions.values()
        for s in t.values()
    )
    print(f"Instance: {label}")
    print(f"  states: {len(nfa.states)}  transitions: {n_trans}  "
          f"finals: {len(nfa.final_states)}  alphabet: {sorted(nfa.input_symbols)}")

    two_stage_kwargs = dict(
        nfa=nfa,
        verbose=args.verbose,
        enumerate_plans=False,
        max_dfa_p1_states=args.budget,
    )
    otf_kwargs = dict(
        nfa=nfa,
        verbose=args.verbose,
        enumerate_plans=False,
        max_product_states=args.budget,
    )

    dt_two, r_two = run("two-stage",
                         automata_based_plan_computation, two_stage_kwargs)
    dt_otf, r_otf = run("on-the-fly",
                         automata_based_plan_on_the_fly, otf_kwargs)

    print("\n" + "=" * 70)
    print("COMPARISON")
    print("=" * 70)
    print(f"two-stage  : {dt_two:8.2f} s")
    print(f"on-the-fly : {dt_otf:8.2f} s")
    if dt_two > 0 and dt_otf > 0:
        if dt_otf < dt_two:
            print(f"→ on-the-fly is {dt_two / dt_otf:.2f}× faster")
        else:
            print(f"→ two-stage is {dt_otf / dt_two:.2f}× faster")

    assert r_two["language_nonempty"] == r_otf["language_nonempty"], (
        "Pipelines disagree on emptiness! two-stage=%s otf=%s"
        % (r_two["language_nonempty"], r_otf["language_nonempty"])
    )
    if r_two["shortest_plan_length"] is not None:
        assert (
            r_two["shortest_plan_length"] == r_otf["shortest_plan_length"]
        ), (
            "Pipelines disagree on shortest plan length! "
            f"two-stage={r_two['shortest_plan_length']} "
            f"otf={r_otf['shortest_plan_length']}"
        )
    print("Sanity check: both pipelines agree on the verdict ✓")
