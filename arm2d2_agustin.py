"""Arm2D2 NFA with a Cartesian goal rectangle above the arm base.

The shoulder angle ``x1`` ranges from 0° to 180° and the relative elbow
angle ``x2`` ranges from -120° to 120°.  Each requested rotation has two
nondeterministic outcomes, moving the selected joint by either 20° or 30°
(nominal 30° minus a possible 10° short-error); motion saturates at the
joint limits.

The launch pose is (90°, 0°).  With two unit-length links and the shoulder at
the origin, the hand must finish in the closed rectangle directly above the
base: x in [-0.2, 0.2] and y in [0.7, 1.1].  The rectangle is compiled into
``GOAL_CONFIGURATIONS`` on the joint grid.

Scaling
-------
``build_agustin_nfa(scale=N)`` refines both the grid step and the leg
magnitudes by an integer factor N so that the physical geometry (joint
ranges, leg proportions, hand kinematics, goal box) is preserved while the
raw NFA grows in state count:

    N = 1  : grid 10°, legs {20°, 30°},  |S|  = 475
    N = 2  : grid  5°, legs {10°, 15°},  |S|  = 1 813
    N = 5  : grid  2°, legs { 4°,  6°},  |S|  = 11 011
    N = 10 : grid  1°, legs { 2°,  3°},  |S|  = 43 621

Because leg magnitudes stay integer multiples of the grid step, all reachable
successors land on the grid at every N.
"""

from math import cos, radians, sin

from automata.fa.nfa import NFA


# Physical model constants (degrees).
X1_MIN, X1_MAX = 0, 180
X2_MIN, X2_MAX = -120, 120

INITIAL_X1 = 90
INITIAL_X2 = 0

LINK_1_LENGTH = 1.0
LINK_2_LENGTH = 1.0

GOAL_X_MIN, GOAL_X_MAX = -0.2, 0.2
GOAL_Y_MIN, GOAL_Y_MAX = 0.7, 1.1

BASE_GRID_STEP = 10
BASE_LEG_SHORT = 20   # nominal 30° − short-error 10°
BASE_LEG_LONG = 30    # nominal 30°

ACTIONS = frozenset({"rr1", "rl1", "rr2", "rl2"})


def hand_position(x1, x2):
    """Return the Cartesian hand position for a joint configuration."""

    shoulder = radians(x1)
    second_link = radians(x1 + x2)
    return (
        LINK_1_LENGTH * cos(shoulder) + LINK_2_LENGTH * cos(second_link),
        LINK_1_LENGTH * sin(shoulder) + LINK_2_LENGTH * sin(second_link),
    )


def is_goal_configuration(x1, x2):
    hand_x, hand_y = hand_position(x1, x2)
    return (
        GOAL_X_MIN <= hand_x <= GOAL_X_MAX
        and GOAL_Y_MIN <= hand_y <= GOAL_Y_MAX
    )


def _grid_step(scale):
    if scale <= 0 or BASE_GRID_STEP % scale != 0:
        raise ValueError(
            f"scale must be a positive divisor of {BASE_GRID_STEP}; got {scale}"
        )
    return BASE_GRID_STEP // scale


def _grid_axes(scale):
    step = _grid_step(scale)
    return (
        list(range(X1_MIN, X1_MAX + 1, step)),
        list(range(X2_MIN, X2_MAX + 1, step)),
    )


def _legs(scale):
    step = _grid_step(scale)
    return BASE_LEG_SHORT * step // BASE_GRID_STEP, BASE_LEG_LONG * step // BASE_GRID_STEP


def state_name(x1, x2):
    def fmt(x):
        return f"m{abs(x)}" if x < 0 else str(x)
    return f"q_{fmt(x1)}_{fmt(x2)}"


def sat1(x):
    return min(X1_MAX, max(X1_MIN, x))


def sat2(x):
    return min(X2_MAX, max(X2_MIN, x))


def goal_configurations(scale=1):
    x1_axis, x2_axis = _grid_axes(scale)
    return frozenset(
        (x1, x2)
        for x1 in x1_axis
        for x2 in x2_axis
        if is_goal_configuration(x1, x2)
    )


# Convenience alias for the default (scale=1) grid, preserving the previous
# module-level constants that other scripts import.
GRID_STEP = BASE_GRID_STEP
X1, X2 = _grid_axes(1)
LEG_SHORT, LEG_LONG = _legs(1)
GOAL_CONFIGURATIONS = goal_configurations(1)


def build_agustin_nfa(scale=1):
    x1_axis, x2_axis = _grid_axes(scale)
    leg_short, leg_long = _legs(scale)

    states = {state_name(x1, x2) for x1 in x1_axis for x2 in x2_axis}

    transitions = {}
    for x1 in x1_axis:
        for x2 in x2_axis:
            current = state_name(x1, x2)
            transitions[current] = {
                "rr1": {
                    state_name(sat1(x1 - leg_short), x2),
                    state_name(sat1(x1 - leg_long), x2),
                },
                "rl1": {
                    state_name(sat1(x1 + leg_short), x2),
                    state_name(sat1(x1 + leg_long), x2),
                },
                "rr2": {
                    state_name(x1, sat2(x2 - leg_short)),
                    state_name(x1, sat2(x2 - leg_long)),
                },
                "rl2": {
                    state_name(x1, sat2(x2 + leg_short)),
                    state_name(x1, sat2(x2 + leg_long)),
                },
            }

    initial_state = state_name(INITIAL_X1, INITIAL_X2)
    goals = goal_configurations(scale)
    final_states = {state_name(x1, x2) for x1, x2 in goals}

    return NFA(
        states=states,
        input_symbols=ACTIONS,
        transitions=transitions,
        initial_state=initial_state,
        final_states=final_states,
    )


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--scale", type=int, default=1,
                    help="Grid refinement factor (must divide 10).")
    ap.add_argument("--show-goals", action="store_true")
    args = ap.parse_args()

    step = _grid_step(args.scale)
    leg_short, leg_long = _legs(args.scale)
    goals = goal_configurations(args.scale)

    nfa = build_agustin_nfa(scale=args.scale)
    n_trans = sum(
        len(s) for t in nfa.transitions.values() for s in t.values()
    )
    print(
        f"Arm2D2 (scale={args.scale}): |S|={len(nfa.states)}, "
        f"|δ|={n_trans}, |F|={len(nfa.final_states)}, "
        f"grid_step={step}°, legs={{{leg_short}°, {leg_long}°}}"
    )
    print(f"Initial: {nfa.initial_state}")
    print(
        f"Cartesian goal: x∈[{GOAL_X_MIN},{GOAL_X_MAX}], "
        f"y∈[{GOAL_Y_MIN},{GOAL_Y_MAX}]"
    )
    print(f"Grid goal configurations: {len(goals)}")
    if args.show_goals:
        for g in sorted(goals):
            hx, hy = hand_position(*g)
            print(f"  {g}: hand=({hx:+.3f}, {hy:+.3f})")
