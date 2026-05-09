"""
Convert an NFA_P2 automaton (dict from plan_automata: ``compute_nfa_p2`` / Algorithm 2) into a
PRISM discrete-time Markov chain (dtmc).

Nondeterminism: for each (state, action), if the NFA has k successor states,
the DTMC uses uniform choice with probability 1/k for each successor.

Optional: make accepting (goal) states absorbing so "expected cost to reach goal"
is well-defined and does not continue after the first visit.

Typical property (file includes a comment with example):

  R{"steps"}=? [F "goal" ]
"""

from __future__ import annotations

import argparse
from typing import Any, Dict, List, Set, Tuple, Union

# ---------------------------------------------------------------------------
# PRISM text generation
# ---------------------------------------------------------------------------


def _product_state_key(state: Any) -> Tuple:
    """Stable sort key for product NFA states (robot state + DFA subset)."""
    if isinstance(state, tuple) and len(state) == 2:
        a, b = state
        if isinstance(b, frozenset):
            return (0, a, tuple(sorted(b)))
    return (1, str(state))


def _norm_successors(succ: Union[Set, List, Any]) -> List[Any]:
    if succ is None:
        return []
    if isinstance(succ, (set, frozenset)):
        return sorted(succ, key=_product_state_key)
    if isinstance(succ, list):
        return sorted(frozenset(succ), key=_product_state_key)
    return [succ]


def nfa_p2_to_prism_dtmc(
    nfa_p2: dict,
    *,
    model_name: str = "nfa_p2_dtmc",
    var_name: str = "q",
    reward_name: str = "steps",
    label_goal: str = "goal",
    absorbing_finals: bool = True,
    include_state_map_header: bool = True,
    max_map_lines: int = 30,
) -> str:
    """
    Return PRISM model source (dtmc) for the given NFA_P2 dictionary.

    nfa_p2 keys: states (set), initial, finals (set), transitions (state -> {sym: {succ, ...}}), input_symbols (set)
    """
    if not nfa_p2.get("states") or nfa_p2.get("initial") is None:
        return f"// {model_name}: empty NFA_P2 (no states / no initial)\n"

    states: Set = set(nfa_p2["states"])
    finals: Set = set(nfa_p2.get("finals", set()))
    initial = nfa_p2["initial"]
    input_symbols: List[str] = sorted(nfa_p2.get("input_symbols", set()))
    if not input_symbols:
        return f"// {model_name}: NFA_P2 has no input symbols\n"

    ordered = sorted(states, key=_product_state_key)
    id_of: Dict[Any, int] = {s: i for i, s in enumerate(ordered)}
    n_states = len(ordered)
    q_max = n_states - 1
    init_id = id_of[initial]
    final_ids = sorted(id_of[s] for s in finals if s in id_of)

    # PRISM action names: single-letter U/D/L/R; otherwise unique sym_0, sym_1, …
    action_label: Dict[str, str] = {}
    used_labs: Set[str] = set()
    for i, sym in enumerate(input_symbols):
        s = str(sym)
        if len(s) == 1 and s in "UDLR" and s not in used_labs:
            lab = s
        else:
            j = i
            lab = f"sym_{j}"
            while lab in used_labs:
                j += 1
                lab = f"sym_{j}"
        used_labs.add(lab)
        action_label[sym] = lab

    # Build transition relation (optionally make finals absorbing)
    trans_lines: List[str] = []
    for s in ordered:
        sid = id_of[s]
        is_final = s in finals
        tr = nfa_p2.get("transitions", {}).get(s, {})

        if absorbing_finals and is_final:
            for sym in input_symbols:
                al = action_label[sym]
                trans_lines.append(
                    f"\t\t[{al}] {var_name}={sid} -> 1:({var_name}'={sid});\n"
                )
            continue

        for sym in input_symbols:
            if sym not in tr:
                continue
            succs = _norm_successors(tr[sym])
            if not succs:
                continue
            k = len(succs)
            al = action_label[sym]
            parts = []
            for t in succs:
                if t not in id_of:
                    continue
                tid = id_of[t]
                parts.append(f"1/{k}:({var_name}'={tid})")
            if not parts:
                continue
            rhs = " + ".join(parts)
            trans_lines.append(f"\t\t[{al}] {var_name}={sid} -> {rhs};\n")

    # Goal label
    if not final_ids:
        goal_label_expr = "false"
    elif len(final_ids) == 1:
        goal_label_expr = f"({var_name}={final_ids[0]})"
    else:
        goal_label_expr = "(" + " | ".join(f"({var_name}={g})" for g in final_ids) + ")"

    goal_line = f'label "{label_goal}" = {goal_label_expr};\n'

    if not final_ids:
        not_in_goal_expr = "true"
    elif len(final_ids) == 1:
        not_in_goal_expr = f"!({var_name}={final_ids[0]})"
    else:
        or_goal = " | ".join(f"({var_name}={g})" for g in final_ids)
        not_in_goal_expr = f"!({or_goal})"

    reward_lines = ""
    for sym in input_symbols:
        al = action_label[sym]
        reward_lines += f'\t\t[{al}] not_in_goal : 1;\n'

    lines: List[str] = []
    lines.append(f"// {model_name} — generated from NFA_P2 as a dtmc\n")
    lines.append(
        f"// Nondeterministic NFA transitions resolved uniformly per (state, action).\n"
    )
    if absorbing_finals:
        lines.append(
            f"// Accepting states are absorbing (self-loop on every action in alphabet).\n"
        )
    lines.append("dtmc\n\n")

    if include_state_map_header and max_map_lines > 0:
        lines.append("// id -> NFA_P2 state (truncated if long)\n")
        for i, s in enumerate(ordered[:max_map_lines]):
            srepr = repr(s)
            if len(srepr) > 120:
                srepr = srepr[:117] + "..."
            lines.append(f"// {i}: {srepr}\n")
        if n_states > max_map_lines:
            lines.append(f"// ... ({n_states - max_map_lines} more states)\n")
        lines.append("\n")

    lines.append(f"const int {var_name}_max = {q_max};\n\n")
    lines.append(f"module {model_name}\n")
    lines.append(
        f"\t{var_name} : [0..{var_name}_max] init {init_id};\n\n"
    )
    if not trans_lines:
        lines.append("\t// (no transitions)\n")
    else:
        lines.extend(trans_lines)
    lines.append("endmodule\n\n")
    lines.append(
        f"// True while not in any accepting (goal) NFA_P2 state (for step rewards)\n"
    )
    lines.append(f"formula not_in_goal = {not_in_goal_expr};\n\n")
    lines.append(goal_line)
    lines.append("\n")
    lines.append('rewards "' + reward_name + '"\n')
    if final_ids:
        lines.append(f"\t// one reward unit per move while not in a goal state\n")
    lines.append(reward_lines)
    lines.append("endrewards\n\n")
    lines.append(
        f'// Example: expected number of steps until first visit to a goal state\n'
        f'// (reward accrues on commands whose guard is "not in goal" — see rewards block)\n'
        f'// {{"{reward_name}"}}=? [F "{label_goal}"]\n'
    )
    return "".join(lines)


def _write_path(path: str, text: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


# ---------------------------------------------------------------------------
# CLI: build from grid world + export
# ---------------------------------------------------------------------------


def _build_grid_nfa_p2(
    n: int,
    robot_start: Tuple[int, int],
    goal: Union[Tuple[int, int], Set[Tuple[int, int]]],
    obstacles: Set[Tuple[int, int]],
):
    from grid_world_nfa import generate_grid_world_nfa
    from plan_automata import build_np2_automaton

    nfa, _ = generate_grid_world_nfa(
        n=n, robot_start=robot_start, goal=goal, obstacles=obstacles, verbose=False
    )
    _, nfa_p2, _, _ = build_np2_automaton(nfa, verbose=False)
    return nfa, nfa_p2


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Export NFA_P2 to a PRISM dtmc (uniform branching)"
    )
    parser.add_argument(
        "-n", "--grid-size", type=int, help="grid size n×n (build grid NFA then NFA_P2)"
    )
    parser.add_argument("--robot-start", type=str, default="1,1")
    parser.add_argument("--goal", type=str, default=None, help="x,y (default: n,n)")
    parser.add_argument("--obstacles", type=str, default=None, help="x,y;x2,y2;...")
    parser.add_argument(
        "--no-absorbing-goal",
        action="store_true",
        help="do not make accepting states absorbing (not recommended for step rewards to goal)",
    )
    parser.add_argument(
        "--map-lines", type=int, default=30, help="max state id comments at top (0 = none)"
    )
    parser.add_argument(
        "-o", "--out", type=str, required=True, help="output .prism file"
    )
    args = parser.parse_args()

    if args.grid_size is None:
        parser.error("provide -n / --grid-size to build the grid world and export")

    from grid_world_nfa import parse_obstacle_list

    rs = tuple(map(int, args.robot_start.split(",")))
    g = args.goal
    if g is None:
        g = (args.grid_size, args.grid_size)
    elif ";" in g:
        g = parse_obstacle_list(g)
    else:
        g = tuple(map(int, g.split(",")))
    obs = parse_obstacle_list(args.obstacles) if args.obstacles else set()

    nfa, nfa_p2 = _build_grid_nfa_p2(args.grid_size, rs, g, obs)
    if not nfa_p2.get("initial"):
        text = f"// NFA_P2 is empty; no PRISM model.\n"
        _write_path(args.out, text)
        print(f"Wrote (empty) {args.out}")
        return

    text = nfa_p2_to_prism_dtmc(
        nfa_p2,
        model_name="robot_dtmc",
        absorbing_finals=not args.no_absorbing_goal,
        include_state_map_header=args.map_lines > 0,
        max_map_lines=args.map_lines,
    )
    _write_path(args.out, text)
    print(f"Wrote {args.out} ({len(nfa_p2.get('states', ()))} states)")


if __name__ == "__main__":
    main()
