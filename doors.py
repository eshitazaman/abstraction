"""Doors corridor (FOND-SAT / PRP-FOND), with *two independent* oneofs.

The original FOND-SAT ``doors`` PDDL slams two doors independently after
each crossing (two ``oneof`` effects, four outcomes).  We keep that
4-way nondeterminism on a corridor of N rooms.  Each room has two bits
``(door_in, door_out)``.  Opening is *not* a single Tireworld-style
reset: the two bits are repaired by two different actions, each
idempotent on its own bit.

Nondeterministic action
-----------------------
``move`` at ``(c, in=open, out=open)``, ``c < N-1``:
    all four combinations of (in, out) at room c+1.

Recovery
--------
``open-in``  sets door_in  = open  (door_out unchanged)
``open-out`` sets door_out = open  (door_in unchanged)

From the 4-way macro the word ``open-in . open-out`` (either order)
collapses to (open, open).  Moving with a closed in-door goes to
``fail``.

Goal: ``(N-1, open, open)``.
Shortest plan: ``(move . open-in . open-out)^{N-1}``, length ``3N - 3``.
"""

from automata.fa.nfa import NFA


ACTIONS = frozenset({"move", "open-in", "open-out"})
FAIL_STATE = "fail"


def state_name(room, door_in, door_out):
    def bit(v):
        return "O" if v else "C"
    return f"r{room}_{bit(door_in)}{bit(door_out)}"


def build_doors_nfa(num_rooms):
    if num_rooms < 2:
        raise ValueError("num_rooms must be >= 2")

    bits = (False, True)
    states = {
        state_name(c, din, dout)
        for c in range(num_rooms)
        for din in bits
        for dout in bits
    }
    states.add(FAIL_STATE)

    transitions = {
        FAIL_STATE: {a: {FAIL_STATE} for a in ACTIONS},
    }
    for c in range(num_rooms):
        for din in bits:
            for dout in bits:
                here = state_name(c, din, dout)
                per_state = {
                    "open-in": {state_name(c, True, dout)},
                    "open-out": {state_name(c, din, True)},
                }
                if din and dout and c < num_rooms - 1:
                    per_state["move"] = {
                        state_name(c + 1, ndin, ndout)
                        for ndin in bits
                        for ndout in bits
                    }
                elif c < num_rooms - 1:
                    per_state["move"] = {FAIL_STATE}
                transitions[here] = per_state

    return NFA(
        states=states,
        input_symbols=ACTIONS,
        transitions=transitions,
        initial_state=state_name(0, True, True),
        final_states={state_name(num_rooms - 1, True, True)},
    )


def expected_shortest_plan_length(num_rooms):
    return 3 * num_rooms - 3
