"""
Arm2D2 model per peer's spec:
  - Actions rl* nominally +30°, rr* nominally -30°, both with ±10° error,
    so each action has two legs at the tolerance endpoints:
        rl* successors: {x + 20, x + 40}
        rr* successors: {x - 20, x - 40}
  - Joint 1 (shoulder): x1 in [0°, 180°]
  - Joint 2 (elbow):    x2 in [-120°, 120°]           (0° = fully extended)
  - Initial: (60°, 30°)
  - Goal region: x1 in [85°, 100°], x2 in [40°, 60°]

Grid step is 10°. Legs are multiples of 20 (gcd(20, 40) = 20), but because
initial x2 = 30 sits at offset 10 mod 20 while initial x1 = 60 sits at offset
0 mod 20, the two reachable lattices are shifted. Using a uniform 10° grid
covers both offsets and the saturation walls at ±120° / 0° / 180;
unreachable (x1, x2) states are never visited
by the DFA_P1 / product BFS, so they cost only raw-NFA memory.

"""

from automata.fa.nfa import NFA


GRID_STEP = 10

X1 = list(range(0, 181, GRID_STEP))
X2 = list(range(-120, 121, GRID_STEP))

INITIAL_X1 = 60
INITIAL_X2 = 30

X1_MIN, X1_MAX = 0, 180
X2_MIN, X2_MAX = -120, 120

GOAL_X1_LOW, GOAL_X1_HIGH = 85, 100
GOAL_X2_LOW, GOAL_X2_HIGH = 40, 60

LEG_SHORT = 20   # nominal 30° − error 10°
LEG_LONG = 40    # nominal 30° + error 10°

ACTIONS = {"rr1", "rl1", "rr2", "rl2"}


def state_name(x1, x2):
    def fmt(x):
        return f"m{abs(x)}" if x < 0 else str(x)
    return f"q_{fmt(x1)}_{fmt(x2)}"


def sat1(x):
    return min(X1_MAX, max(X1_MIN, x))


def sat2(x):
    return min(X2_MAX, max(X2_MIN, x))


def build_agustin_nfa():
    states = {state_name(x1, x2) for x1 in X1 for x2 in X2}

    transitions = {}
    for x1 in X1:
        for x2 in X2:
            current = state_name(x1, x2)
            transitions[current] = {
                "rr1": {
                    state_name(sat1(x1 - LEG_SHORT), x2),
                    state_name(sat1(x1 - LEG_LONG), x2),
                },
                "rl1": {
                    state_name(sat1(x1 + LEG_SHORT), x2),
                    state_name(sat1(x1 + LEG_LONG), x2),
                },
                "rr2": {
                    state_name(x1, sat2(x2 - LEG_SHORT)),
                    state_name(x1, sat2(x2 - LEG_LONG)),
                },
                "rl2": {
                    state_name(x1, sat2(x2 + LEG_SHORT)),
                    state_name(x1, sat2(x2 + LEG_LONG)),
                },
            }

    initial_state = state_name(INITIAL_X1, INITIAL_X2)
    final_states = {
        state_name(x1, x2)
        for x1 in X1
        for x2 in X2
        if GOAL_X1_LOW <= x1 <= GOAL_X1_HIGH
        and GOAL_X2_LOW <= x2 <= GOAL_X2_HIGH
    }

    return NFA(
        states=states,
        input_symbols=ACTIONS,
        transitions=transitions,
        initial_state=initial_state,
        final_states=final_states,
    )


if __name__ == "__main__":
    nfa = build_agustin_nfa()
    n_trans = sum(
        len(s) for t in nfa.transitions.values() for s in t.values()
    )
    print(
        f"Arm2D2: |S|={len(nfa.states)}, "
        f"|δ|={n_trans}, "
        f"|F|={len(nfa.final_states)}, "
        f"legs={{±{LEG_SHORT}°, ±{LEG_LONG}°}}, "
        f"x2 range=[{X2_MIN}, {X2_MAX}]"
    )
    print(f"Initial: {nfa.initial_state}")
    print(f"Goal region: x1∈[{GOAL_X1_LOW},{GOAL_X1_HIGH}], "
          f"x2∈[{GOAL_X2_LOW},{GOAL_X2_HIGH}]")
