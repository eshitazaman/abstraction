"""
Grid World Robot NFA Generator

Inspired by: https://www.prismmodelchecker.org/casestudies/robot.php

Model:
- n×n grid (coordinates 1..n in x and y)
- Robot starts at (1,1) (bottom-left), goal (n,n) (top-right) by default
- Input symbols and their semantics are selected by `action_mode`:
    "cardinal":   U, D, L, R — each is a single deterministic cardinal step
                  (U = N, D = S, L = W, R = E). No nondeterminism.
    "se-corners" (default): A = W ∪ N, B = E ∪ S.
        Two opposing diagonal corners; each B leg may regress in y.
    "north-bias":            A = W ∪ N, B = E ∪ N.
        Both actions have a North leg, biasing nondeterminism toward the goal.
  At every non-obstacle cell, an action's legs are taken nondeterministically
  iff in-grid and not on an obstacle. (For "cardinal" each action has just one
  leg, so the NFA is deterministic-shaped / partial.)
- If no leg of an action is feasible, the transition is omitted (NFA is partial).
  In multi-leg modes, at a wall the action collapses to the single feasible leg.
- Obstacle squares are forbidden: a leg landing on an obstacle drops that leg.
- No other agents.
"""

from automata.fa.nfa import NFA
from typing import Set, Tuple, Optional, Iterable, Union, Mapping
import argparse
import random


# Each preset maps an action symbol to its tuple of cardinal-step legs (dx, dy).
ACTION_PRESETS: Mapping[str, Mapping[str, Tuple[Tuple[int, int], ...]]] = {
    "cardinal": {
        "U": ((0, 1),),    # North
        "D": ((0, -1),),   # South
        "L": ((-1, 0),),   # West
        "R": ((1, 0),),    # East
    },
    "se-corners": {
        "A": ((-1, 0), (0, 1)),  # W or N
        "B": ((1, 0), (0, -1)),  # E or S
    },
    "north-bias": {
        "A": ((-1, 0), (0, 1)),  # W or N
        "B": ((1, 0), (0, 1)),   # E or N
    },
    "north-bias+south": {
        "A": ((-1, 0), (0, 1)),  # W or N
        "B": ((1, 0), (0, 1)),   # E or N
        "S": ((0, -1),),         # S only (deterministic retreat)
    },
}


def _legend_for_mode(mode: str) -> str:
    """Human-readable description of which legs each action expands to under `mode`."""
    leg_name = {(-1, 0): "W", (1, 0): "E", (0, 1): "N", (0, -1): "S"}
    parts = []
    multi_leg = False
    for sym, legs in ACTION_PRESETS[mode].items():
        if len(legs) > 1:
            multi_leg = True
        names = " ∪ ".join(leg_name[d] for d in legs)
        parts.append(f"{sym} = {names}")
    suffix = (
        " (nondeterministic; illegal legs dropped)"
        if multi_leg
        else " (deterministic; illegal moves drop the transition)"
    )
    return "; ".join(parts) + suffix


def find_dead_cells(
    n: int,
    obstacles: Iterable[Tuple[int, int]],
    action_mode: str,
) -> dict:
    """
    Map each action symbol to the set of non-obstacle, in-grid cells from which
    that action has *no* successor (every leg is OOB or lands on an obstacle).

    A run reaching such a cell with that letter as the next input gets stuck —
    under the universal P2 acceptance, that branch fails and rejects the plan.
    """
    obs: Set[Tuple[int, int]] = set(obstacles)
    deltas = ACTION_PRESETS[action_mode]

    def free(x: int, y: int) -> bool:
        return 1 <= x <= n and 1 <= y <= n and (x, y) not in obs

    dead: dict = {sym: set() for sym in deltas}
    for x in range(1, n + 1):
        for y in range(1, n + 1):
            if not free(x, y):
                continue
            for sym, legs in deltas.items():
                if all(not free(x + dx, y + dy) for dx, dy in legs):
                    dead[sym].add((x, y))
    return dead


def print_dead_cells_report(
    n: int,
    obstacles: Set[Tuple[int, int]],
    action_mode: str,
    reachable_cells: Optional[Set[Tuple[int, int]]] = None,
    goal_cells: Optional[Set[Tuple[int, int]]] = None,
) -> dict:
    """
    Pretty-print the dead-cell table.

    `reachable_cells` (optional) flags which dead cells are actually reachable
    from the start; cells *not* reachable cannot poison any plan and are noted
    only as "(unreachable)". `goal_cells` are excluded from the impact summary
    because acceptance ends the run before the dead letter is consumed.
    """
    dead = find_dead_cells(n, obstacles, action_mode)
    structural = find_dead_cells(n, set(), action_mode)
    goals = goal_cells or set()

    print("\n" + "-" * 70)
    print(f"Dead-cell analysis  [action_mode={action_mode}]")
    print("-" * 70)

    any_reachable_problem = False
    for sym in sorted(dead):
        cells = sorted(dead[sym])
        # "Problem" = the cells the seed-search penalises: reachable, non-goal,
        # *not* structural (i.e. the layout's obstacles caused the deadness).
        non_goal = [c for c in cells if c not in goals]
        non_structural = [c for c in non_goal if c not in structural[sym]]
        if reachable_cells is None:
            problem = non_structural
            problem_label = "non-goal & obstacle-induced"
        else:
            problem = [c for c in non_structural if c in reachable_cells]
            problem_label = "non-goal & obstacle-induced & reachable from start"
        if problem:
            any_reachable_problem = True

        print(
            f"  '{sym}' dead cells: {len(cells)} total, "
            f"{len(problem)} {problem_label}"
        )
        for c in cells:
            tags = []
            if c in goals:
                tags.append("goal — fine, run ends here")
            if c in structural[sym]:
                tags.append("structural (grid-edge, not obstacle-induced)")
            if reachable_cells is not None and c not in reachable_cells:
                tags.append("unreachable")
            suffix = f"  [{'; '.join(tags)}]" if tags else ""
            print(f"    {c}{suffix}")

    if any_reachable_problem:
        print(
            "\n  Note: each listed reachable, non-goal dead cell rules out "
            "exactly the plans whose execution may end up there with the "
            "named letter as the next input — those plans have a stuck "
            "branch under P2. Plans that never feed the dead letter from "
            "the dead cell can still be valid (e.g. only-B plans on an "
            "empty grid avoid A-dead corners trivially)."
        )
    else:
        print(
            "\n  No reachable non-goal dead cells; the dead-cell criterion "
            "imposes no constraints on plan existence."
        )
    return dead


def generate_grid_world_nfa(
    n: int = 4,
    robot_start: Tuple[int, int] = (1, 1),
    goal: Union[Tuple[int, int], Iterable[Tuple[int, int]], None] = None,
    obstacles: Optional[Iterable[Tuple[int, int]]] = None,
    action_mode: str = "se-corners",
    verbose: bool = False,
) -> Tuple[NFA, dict]:
    """
    Build an automaton for the robot navigating to the goal.

    State names: r{x}_{y}

    `action_mode` selects the action semantics; see ACTION_PRESETS for the mapping
    from each input symbol to its tuple of cardinal-step legs. Both legs blocked or
    out-of-bounds ⇒ no transition (partial NFA). Walls clamp an action to whichever
    leg remains feasible.
    """
    if action_mode not in ACTION_PRESETS:
        raise ValueError(
            f"Unknown action_mode {action_mode!r}; expected one of "
            f"{sorted(ACTION_PRESETS)}"
        )
    ACTION_DELTAS = ACTION_PRESETS[action_mode]

    obs: Set[Tuple[int, int]] = set(obstacles) if obstacles else set()

    if goal is None:
        goals: Set[Tuple[int, int]] = {(n, n)}
    elif isinstance(goal, tuple) and len(goal) == 2 and all(
        isinstance(v, int) for v in goal
    ):
        goals = {goal}
    else:
        goals = set(goal)

    if robot_start in obs:
        raise ValueError(f"robot_start {robot_start} cannot lie on an obstacle")
    for g in goals:
        if g in obs:
            raise ValueError(f"goal {g} cannot lie on an obstacle")

    def state_name(rx: int, ry: int) -> str:
        return f"r{rx}_{ry}"

    def in_grid(x: int, y: int) -> bool:
        return 1 <= x <= n and 1 <= y <= n

    def successors_for_cell(rx: int, ry: int, action: str) -> Set[Tuple[int, int]]:
        """Union of feasible legs for `action`; blocked / out-of-bounds legs are dropped."""
        out: Set[Tuple[int, int]] = set()
        for dx, dy in ACTION_DELTAS.get(action, ()):
            nx, ny = rx + dx, ry + dy
            if in_grid(nx, ny) and (nx, ny) not in obs:
                out.add((nx, ny))
        return out

    if verbose:
        print(f"Generating {n}×{n} grid world automaton...")
        print(f"  Action mode: {action_mode} ({_legend_for_mode(action_mode)})")
        print(f"  Robot start: {robot_start}")
        print(f"  Goal(s): {sorted(goals)}")
        if obs:
            print(f"  Obstacles ({len(obs)}): {sorted(obs)}")

    states: Set[str] = set()
    transitions: dict = {}
    final_states: Set[str] = set()
    input_symbols = set(ACTION_DELTAS.keys())

    rx0, ry0 = robot_start
    initial_state = state_name(rx0, ry0)
    visited: Set[Tuple[int, int]] = set()
    queue: list = [(rx0, ry0)]
    visited.add((rx0, ry0))

    while queue:
        rx, ry = queue.pop(0)
        current_state = state_name(rx, ry)
        states.add(current_state)

        if (rx, ry) in goals:
            final_states.add(current_state)

        for action in input_symbols:
            succs = successors_for_cell(rx, ry, action)
            if not succs:
                continue
            if current_state not in transitions:
                transitions[current_state] = {}
            if action not in transitions[current_state]:
                transitions[current_state][action] = set()

            for (nrx, nry) in succs:
                new_state = state_name(nrx, nry)
                transitions[current_state][action].add(new_state)
                if (nrx, nry) not in visited:
                    visited.add((nrx, nry))
                    queue.append((nrx, nry))

    for state in states:
        if state not in transitions:
            transitions[state] = {}

    if verbose:
        print(f"  States: {len(states)}")
        print(f"  Final states: {len(final_states)}")
        trans_count = sum(len(succs) for t in transitions.values() for succs in t.values())
        print(f"  Transitions: {trans_count}")

    nfa = NFA(
        states=states,
        input_symbols=input_symbols,
        transitions=transitions,
        initial_state=initial_state,
        final_states=final_states,
    )

    stats = {
        "grid_size": n,
        "num_states": len(states),
        "num_final_states": len(final_states),
        "num_transitions": sum(
            len(succs) for t in transitions.values() for succs in t.values()
        ),
        "robot_start": robot_start,
        "goals": goals,
        "obstacles": obs,
        "action_mode": action_mode,
    }

    return nfa, stats


def sample_random_obstacles(
    n: int,
    m: int,
    forbid: Iterable[Tuple[int, int]] = (),
    seed: Optional[int] = None,
) -> Set[Tuple[int, int]]:
    """
    Uniformly sample `m` distinct cells from the n×n grid as obstacles,
    excluding any cells in `forbid` (typically the start and goal).

    Returns the set of (x, y) coordinates. If `seed` is given, results are
    reproducible for that (n, m, forbid, seed).

    Raises ValueError if m exceeds the number of available (non-forbidden) cells.
    """
    forbidden = set(forbid)
    candidates = [
        (x, y)
        for x in range(1, n + 1)
        for y in range(1, n + 1)
        if (x, y) not in forbidden
    ]
    if m > len(candidates):
        raise ValueError(
            f"Cannot sample {m} obstacles from a {n}×{n} grid with "
            f"{len(forbidden)} forbidden cells; only {len(candidates)} cells available"
        )
    rng = random.Random(seed)
    return set(rng.sample(candidates, m))


def parse_obstacle_list(s: str) -> Set[Tuple[int, int]]:
    """Parse 'x,y;x2,y2' into a set of obstacle coordinates."""
    s = s.strip()
    if not s:
        return set()
    out = set()
    for part in s.split(";"):
        part = part.strip()
        if not part:
            continue
        a, b = part.split(",")
        out.add((int(a.strip()), int(b.strip())))
    return out


def format_dfa_p1_state(dfa_state) -> str:
    """Readable string for a DFA_P1 state (a frozenset of NFA state names)."""
    if not dfa_state:
        return "{}"
    inner = ",".join(sorted(dfa_state))
    return "{" + inner + "}"


def dfa_p1_stats(dfa_p1: dict) -> Tuple[int, int]:
    """
    Return (num_states, num_transitions) for a DFA_P1 dict from plan_automata.nfa_to_dfa_p1.

    Here a 'transition' is one (state, action, successor) triple (successor is unique in a DFA).
    """
    states = dfa_p1["states"]
    transitions = 0
    for s in states:
        if s in dfa_p1["transitions"]:
            transitions += len(dfa_p1["transitions"][s])
    return len(states), transitions


def print_dfa_p1_summary(dfa_p1: dict) -> None:
    """Print only aggregate statistics for DFA_P1 (no state listing)."""
    n_states, n_trans = dfa_p1_stats(dfa_p1)
    n_finals = len(dfa_p1.get("finals", set()))
    print(f"DFA_P1 states: {n_states}")
    print(f"DFA_P1 transitions: {n_trans}")
    print(f"DFA_P1 final states: {n_finals}")


def print_dfa_p1_transitions(
    dfa_p1: dict, *, max_lines: Optional[int] = None
) -> None:
    """
    Print the DFA_P1 transition table (sorted, stable). If max_lines is set, only print
    the first max_lines lines.
    """
    syms = sorted(dfa_p1.get("input_symbols", set()))
    lines: list = []
    for s in sorted(dfa_p1["states"], key=lambda st: (len(st), sorted(st) if st else [])):
        if s not in dfa_p1.get("transitions", {}):
            continue
        for a in syms:
            if a not in dfa_p1["transitions"][s]:
                continue
            sp = dfa_p1["transitions"][s][a]
            lines.append(
                f"  {format_dfa_p1_state(s)}  --{a}-->  {format_dfa_p1_state(sp)}"
            )

    if max_lines is not None and len(lines) > max_lines:
        print(
            f"\nDFA_P1 transition list (first {max_lines} of {len(lines)} lines; sorted):"
        )
        for line in lines[:max_lines]:
            print(line)
        print(f"  ... ({len(lines) - max_lines} more lines omitted)")
    else:
        print(f"\nDFA_P1 transition list ({len(lines)} lines; sorted):")
        for line in lines:
            print(line)


def print_grid(
    n: int,
    robot_start: Tuple[int, int],
    goal: Union[Tuple[int, int], Set[Tuple[int, int]]],
    obstacles: Set[Tuple[int, int]],
    action_mode: str = "se-corners",
) -> None:
    """ASCII map: . free, # obstacle, S start, G goal."""
    goals = {goal} if isinstance(goal, tuple) else set(goal)
    print("\nGrid map (x right, y up; (1,1) bottom-left):")
    for y in range(n, 0, -1):
        row_chars = []
        for x in range(1, n + 1):
            c = (x, y)
            if c == robot_start:
                ch = "S"
            elif c in goals:
                ch = "G"
            elif c in obstacles:
                ch = "#"
            else:
                ch = "."
            row_chars.append(ch)
        print("  " + " ".join(row_chars) + f"  y={y}")
    print("  " + " ".join(str(i) for i in range(1, n + 1)) + "  x")
    print(f"  Legend [{action_mode}]: {_legend_for_mode(action_mode)}")


def main():
    parser = argparse.ArgumentParser(description="Grid World Robot NFA Generator")
    parser.add_argument(
        "-n", "--grid-size", type=int, default=4, help="Grid size (n×n), default: 4"
    )
    parser.add_argument(
        "--robot-start",
        type=str,
        default="1,1",
        help="Robot start position as x,y (default: 1,1)",
    )
    parser.add_argument(
        "--goal",
        type=str,
        default=None,
        help='Goal position as x,y or a semicolon list "x1,y1;x2,y2" (default: n,n)',
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")
    parser.add_argument(
        "--exists-only",
        action="store_true",
        help="Only test whether some P1∧P2 valid plan exists (skip enumerating all words; much faster)",
    )
    parser.add_argument(
        "--np2-only",
        action="store_true",
        help="Build and report the NP2 automaton (the NFA_P2 enforcing P1 ∧ P2); do not enumerate plans",
    )
    parser.add_argument(
        "--print-dfa-p1",
        dest="print_dfa_p1",
        action="store_true",
        help="With --np2-only, print DFA_P1 counts only: |states|, |transitions|, |finals| (default: on for --np2-only)",
    )
    parser.add_argument(
        "--no-print-dfa-p1",
        dest="print_dfa_p1",
        action="store_false",
        help="With --np2-only, skip printing DFA_P1 details",
    )
    parser.set_defaults(print_dfa_p1=None)
    parser.add_argument(
        "--list-dfa-p1-transitions",
        action="store_true",
        help="With --np2-only, also print the DFA_P1 transition table (can be huge)",
    )
    parser.add_argument(
        "--dfa-p1-max-lines",
        type=int,
        default=200,
        metavar="N",
        help="With --list-dfa-p1-transitions, cap printed transition lines (default: 200; use 0 for no cap)",
    )
    parser.add_argument(
        "--dfa-p1-out",
        type=str,
        default=None,
        metavar="FILE",
        help="With --np2-only, write the full DFA_P1 transition list to FILE (does not print the list unless --list-dfa-p1-transitions)",
    )
    parser.add_argument(
        "--prism-out",
        type=str,
        default=None,
        metavar="FILE",
        help="With --np2-only, write NFA_P2 as a PRISM dtmc (uniform branching) to FILE",
    )
    parser.add_argument(
        "--prism-no-absorbing-goal",
        action="store_true",
        help="With --prism-out, do not make accepting NFA_P2 states absorbing (default: absorbing)",
    )
    parser.add_argument(
        "--obstacles",
        type=str,
        default=None,
        help='Semicolon-separated obstacle positions, e.g. "2,2;3,4"',
    )
    parser.add_argument(
        "--random-obstacles",
        type=int,
        default=0,
        metavar="M",
        help=(
            "Sample M obstacles uniformly at random from the grid (excluding "
            "start and goal cells, and any cells given via --obstacles). Combined "
            "with --obstacles if both are supplied."
        ),
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        metavar="S",
        help="Seed for --random-obstacles (default: nondeterministic).",
    )
    parser.add_argument(
        "--action-mode",
        choices=sorted(ACTION_PRESETS.keys()),
        default="se-corners",
        help=(
            "Action semantics: 'cardinal' = deterministic U/D/L/R single-leg moves; "
            "'se-corners' (default) = (A:W∪N, B:E∪S); "
            "'north-bias' = (A:W∪N, B:E∪N, both actions can step toward the goal)"
        ),
    )
    parser.add_argument(
        "--check-dead-cells",
        action="store_true",
        help=(
            "Print, before any DFA_P1/NFA_P2 work, every cell where some action "
            "has no successors. Reachable non-goal dead cells are flagged because "
            "they typically force L(NFA_P2) to be empty."
        ),
    )

    args = parser.parse_args()

    if args.print_dfa_p1 is None:
        args.print_dfa_p1 = bool(args.np2_only)

    robot_start = tuple(map(int, args.robot_start.split(",")))

    if args.goal:
        if ";" in args.goal:
            goal = parse_obstacle_list(args.goal)
        else:
            goal = tuple(map(int, args.goal.split(",")))
    else:
        goal = (args.grid_size, args.grid_size)

    obstacle_set: Set[Tuple[int, int]] = set()
    if args.obstacles:
        obstacle_set |= parse_obstacle_list(args.obstacles)

    if args.random_obstacles > 0:
        forbid = {robot_start} | (
            {goal} if isinstance(goal, tuple) else set(goal)
        ) | obstacle_set
        sampled = sample_random_obstacles(
            n=args.grid_size,
            m=args.random_obstacles,
            forbid=forbid,
            seed=args.seed,
        )
        obstacle_set |= sampled
        print(
            f"\nSampled {len(sampled)} random obstacles "
            f"(seed={args.seed}): "
            f"{sorted(sampled)}"
        )

    print("=" * 70)
    print("GRID WORLD ROBOT")
    print("=" * 70)

    nfa, stats = generate_grid_world_nfa(
        n=args.grid_size,
        robot_start=robot_start,
        goal=goal,
        obstacles=obstacle_set,
        action_mode=args.action_mode,
        verbose=True,
    )

    print_grid(
        stats["grid_size"],
        stats["robot_start"],
        stats["goals"],
        stats["obstacles"],
        action_mode=stats["action_mode"],
    )

    print(f"\nGrid: {stats['grid_size']}×{stats['grid_size']}")
    print(f"Robot start: {stats['robot_start']}")
    print(f"Goal(s): {sorted(stats['goals'])}")
    if stats["obstacles"]:
        print(f"Obstacles: {sorted(stats['obstacles'])}")
    print(f"States: {stats['num_states']}")
    print(f"Final states: {stats['num_final_states']}")
    print(f"Transitions: {stats['num_transitions']}")

    if args.check_dead_cells:
        # `nfa.states` are the reachable subgraph from robot_start (BFS in
        # generate_grid_world_nfa), so we use them as the reachability oracle.
        reachable = {
            tuple(int(v) for v in s[1:].split("_"))
            for s in nfa.states
        }
        print_dead_cells_report(
            n=stats["grid_size"],
            obstacles=stats["obstacles"],
            action_mode=stats["action_mode"],
            reachable_cells=reachable,
            goal_cells=stats["goals"],
        )

    from plan_automata import (
        automata_based_plan_computation,
        build_np2_automaton,
    )

    if args.np2_only:
        print("\n" + "=" * 70)
        print("BUILDING NP2 (P1 ∧ P2 AUTOMATON)")
        print("=" * 70)

        np2_obj, nfa_p2_dict, _, dfa_p1 = build_np2_automaton(
            nfa, verbose=True
        )

        if args.print_dfa_p1 or args.list_dfa_p1_transitions:
            print("\n" + "-" * 70)
            print("DFA_P1 (P1-determinization of the grid NFA)")
            print("-" * 70)
        if args.print_dfa_p1:
            print_dfa_p1_summary(dfa_p1)
        if args.list_dfa_p1_transitions:
            cap = None if args.dfa_p1_max_lines == 0 else args.dfa_p1_max_lines
            print_dfa_p1_transitions(dfa_p1, max_lines=cap)
        if args.prism_out:
            from nfa_p2_to_prism import nfa_p2_to_prism_dtmc

            prism_text = nfa_p2_to_prism_dtmc(
                nfa_p2_dict,
                model_name="robot_dtmc",
                absorbing_finals=not args.prism_no_absorbing_goal,
                max_map_lines=30,
            )
            with open(args.prism_out, "w", encoding="utf-8") as pf:
                pf.write(prism_text)
            print(f"\nWrote PRISM dtmc to: {args.prism_out}")

        if args.dfa_p1_out:
            n_states, n_trans = dfa_p1_stats(dfa_p1)
            with open(args.dfa_p1_out, "w", encoding="utf-8") as f:
                f.write(
                    f"# DFA_P1 for grid world robot\n"
                    f"# states: {n_states}\n"
                    f"# transitions: {n_trans}\n"
                )
                syms = sorted(dfa_p1.get("input_symbols", set()))
                lines: list = []
                for s in sorted(
                    dfa_p1["states"], key=lambda st: (len(st), sorted(st) if st else [])
                ):
                    if s not in dfa_p1.get("transitions", {}):
                        continue
                    for a in syms:
                        if a not in dfa_p1["transitions"][s]:
                            continue
                        sp = dfa_p1["transitions"][s][a]
                        lines.append(
                            f"{format_dfa_p1_state(s)}  --{a}-->  {format_dfa_p1_state(sp)}\n"
                        )
                f.writelines(lines)
            print(f"\nWrote full DFA_P1 transition list to: {args.dfa_p1_out}")

        if np2_obj is None:
            print("\nNP2 is empty (no valid P1 ∧ P2 plan exists).")
        else:
            trans_count = sum(
                len(succs) for t in np2_obj.transitions.values() for succs in t.values()
            )
            print("\nNP2 (NFA_P2) constructed.")
            print(f"States: {len(np2_obj.states)}")
            print(f"Final states: {len(np2_obj.final_states)}")
            print(f"Transitions: {trans_count}")
            print(f"Initial state: {np2_obj.initial_state}")
    else:
        result = automata_based_plan_computation(
            nfa,
            verbose=True,
            enumerate_plans=not args.exists_only,
        )

        print("\n" + "=" * 70)
        print("SUMMARY")
        print("=" * 70)
        stats_result = result["stats"]
        print(f"{'Component':<30} {'States':>12} {'Transitions':>12} {'Finals':>10}")
        print("-" * 70)
        print(
            f"{'Input NFA':<30} {stats_result['nfa_states']:>12} {stats_result['nfa_transitions']:>12} {stats_result['nfa_finals']:>10}"
        )
        print(
            f"{'DFA_P1':<30} {stats_result['dfa_p1_states']:>12} {stats_result['dfa_p1_transitions']:>12} {stats_result['dfa_p1_finals']:>10}"
        )
        print(
            f"{'Product (NFA × DFA_P1)':<30} {stats_result['product_states']:>12} {stats_result['product_transitions']:>12} {stats_result['product_finals']:>10}"
        )
        print(
            f"{'NFA_P2 (reachable)':<30} {stats_result['nfa_p2_reachable']:>12} {stats_result['nfa_p2_transitions']:>12} {stats_result['nfa_p2_finals']:>10}"
        )
        print(
            f"{'NFA_P2 (unreachable)':<30} {stats_result['nfa_p2_unreachable']:>12} {'-':>12} {'-':>10}"
        )

        print("\n" + "=" * 70)
        print("EXISTENCE (P1 ∧ P2)")
        print("=" * 70)
        print(f"Some valid plan exists: {result['language_nonempty']}")
        if result["language_nonempty"]:
            print(
                f"Shortest valid plan length (moves): {result['shortest_plan_length']}"
            )
        else:
            print("(No accepting path in NFA_P2; L(NFA_P2) is empty.)")

        if not args.exists_only:
            print("\n" + "=" * 70)
            print("VALID PLANS (enumerated, length ≤ 15)")
            print("=" * 70)

            if result["valid_plans"]:
                plans = sorted(result["valid_plans"], key=lambda x: (len(x), x))
                print(f"Found {len(plans)} valid plans (P1 ∧ P2)")
                print("\nShortest plans:")
                for p in plans[:10]:
                    decoded = " → ".join(list(p))
                    print(f"  {p} (length {len(p)}): {decoded}")
                if len(plans) > 10:
                    print(f"  ... and {len(plans) - 10} more")
            else:
                print("No valid plans found in enumeration (words of length ≤ 15).")
                print(
                    "\nThere may still be longer valid plans; see EXISTENCE above "
                    "or increase max_length in enumerate_valid_plans."
                )


if __name__ == "__main__":
    import sys
    sys.exit(main() or 0)
