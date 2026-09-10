"""Beam-walk (FOND-SAT suite; Jensen & Veloso).

An agent walks a beam of N positions.  In the original domain
``walk-on-beam`` is a 2-way ``oneof`` (stay up / fall) and recovery is a
*policy*: walk back to a ladder.  We keep the IPC action but give it a
richer 3-way outcome -- stay up, land on the beam's edge, or fall to the
ground -- and replace the ladder dead-end by a *graded* ``climb``:

    fallen  --climb-->  edge
    edge    --climb-->  up
    up      --climb-->  up

One climb is not enough to restore every branch, so the shortest strong
word uses two climbs after every walk.  That is a different plan shape
from Tireworld's single ``fix``.

Nondeterministic action
-----------------------
``walk-on-beam`` at ``(i, up)``, ``i < N-1``:
    {(i+1, up), (i+1, edge), (i+1, fallen)}

Recovery
--------
``climb`` as above (deterministic, not fully collapsing in one step).

Walking while not up goes to an absorbing ``fail`` sink.

Goal: ``(N-1, up)``.
Shortest plan: ``(walk-on-beam . climb . climb)^{N-1}``, length ``3N - 3``.
"""

from automata.fa.nfa import NFA


UP, EDGE, FALLEN = "up", "edge", "fallen"
HEIGHTS = (UP, EDGE, FALLEN)
ACTIONS = frozenset({"walk-on-beam", "climb"})
FAIL_STATE = "fail"

_CLIMB = {UP: UP, EDGE: UP, FALLEN: EDGE}


def state_name(pos, height):
    return f"p{pos}_{height}"


def build_beam_walk_nfa(num_positions):
    if num_positions < 2:
        raise ValueError("num_positions must be >= 2")

    states = {
        state_name(i, h) for i in range(num_positions) for h in HEIGHTS
    }
    states.add(FAIL_STATE)

    transitions = {
        FAIL_STATE: {a: {FAIL_STATE} for a in ACTIONS},
    }
    for i in range(num_positions):
        for h in HEIGHTS:
            here = state_name(i, h)
            per_state = {"climb": {state_name(i, _CLIMB[h])}}
            if h == UP and i < num_positions - 1:
                per_state["walk-on-beam"] = {
                    state_name(i + 1, hh) for hh in HEIGHTS
                }
            elif h != UP and i < num_positions - 1:
                per_state["walk-on-beam"] = {FAIL_STATE}
            transitions[here] = per_state

    return NFA(
        states=states,
        input_symbols=ACTIONS,
        transitions=transitions,
        initial_state=state_name(0, UP),
        final_states={state_name(num_positions - 1, UP)},
    )


def expected_shortest_plan_length(num_positions):
    return 3 * num_positions - 3
