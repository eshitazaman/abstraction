"""Nondeterministic Tireworld benchmark (IPPC 2006, FOND family).

The classical Tireworld domain is a probabilistic planning benchmark: a
truck drives along a road graph, and each ``drive`` action stochastically
either arrives with the tire intact or flat.  A ``fix`` action repairs a
flat tire.

Following the recipe "convert probability -> nondeterminism, remove
failure paths":

  * Every probabilistic outcome of ``drive`` becomes a *nondeterministic*
    branch (each ``drive`` from an ok-tire state yields *both* an ok
    successor and a flat successor at the next city).
  * The "flat + no spare -> dead end" failure of the original benchmark
    is removed by giving ``fix`` a total-applicability transition:
    ``fix`` is defined at every state and always normalizes the tire
    to OK.  Thus no plan branch is ever stuck.

Faithful semantics is preserved by making ``drive`` a *partial* action
that is undefined when the tire is flat or when we are already at the
destination -- exactly the IPPC precondition ``tire=ok``.  Under
universal P2 this forces every valid plan to interleave ``fix`` between
``drive`` steps as needed, matching the FOND "strong plan" semantics.

Model
-----
* States           : ``(city_index, tire_status)`` for
                     ``city_index in [0, N-1]`` and ``tire_status in {ok, flat}``.
* Alphabet        : ``{drive, fix}``.
* Initial          : ``(0, ok)``.
* Accepting states : ``(N-1, ok)`` only.  Arriving with a flat tire is not
                     enough; the last ``drive`` must be followed by ``fix``.

Transitions
-----------
  * ``drive`` at ``(c, ok)`` with ``c < N-1``:
        {(c+1, ok), (c+1, flat)}    -- move forward, tire outcome nondet.
  * ``drive`` at ``(c, flat)``:
        {fail}                      -- the original "cannot drive on a flat"
                                       failure, kept as an explicit sink so
                                       that a P1 macro which still contains a
                                       flat city is poisoned and cannot be
                                       accepting.  This forces ``fix`` after
                                       every ``drive``.
  * ``drive`` at the destination or at ``fail``: undefined.
  * ``fix`` at any ``(c, *)``:
        {(c, ok)}                   -- deterministic repair (idempotent).
  * ``fail`` has no ``fix`` (cannot recover).

Shortest strong plan
--------------------
``(drive . fix)^{N-1}`` -- length ``2N - 2``.
Each ``drive`` spreads the macro to {ok, flat} at the next city; ``fix``
collapses it back to {ok} before the next ``drive``.

Sizes (analytic)
----------------
``|S| = 2N + 1`` (plus the fail sink), ``|delta| = 4N - 2``.
"""

from automata.fa.nfa import NFA


TIRE_OK = 0
TIRE_FLAT = 1
TIRE_LABELS = {TIRE_OK: "ok", TIRE_FLAT: "flat"}

ACTIONS = frozenset({"drive", "fix"})
FAIL_STATE = "fail"


def state_name(city, tire):
    return f"c{city}_{TIRE_LABELS[tire]}"


def build_tireworld_nfa(num_cities):
    """Return an NFA modelling the ``num_cities``-city chain Tireworld."""
    if num_cities < 2:
        raise ValueError("num_cities must be >= 2")

    states = {
        state_name(c, t)
        for c in range(num_cities)
        for t in (TIRE_OK, TIRE_FLAT)
    }
    states.add(FAIL_STATE)

    transitions = {
        FAIL_STATE: {a: {FAIL_STATE} for a in ACTIONS},
    }
    for c in range(num_cities):
        for t in (TIRE_OK, TIRE_FLAT):
            here = state_name(c, t)
            per_state = {}

            if t == TIRE_OK and c < num_cities - 1:
                # Nondeterministic tire outcome at the next city
                # (probability converted to a two-way branch).
                per_state["drive"] = {
                    state_name(c + 1, TIRE_OK),
                    state_name(c + 1, TIRE_FLAT),
                }
            elif t == TIRE_FLAT and c < num_cities - 1:
                # Driving on a flat tire is the original failure path,
                # kept as a sink so P1 sees it in the macro.
                per_state["drive"] = {FAIL_STATE}

            per_state["fix"] = {state_name(c, TIRE_OK)}
            transitions[here] = per_state

    initial = state_name(0, TIRE_OK)
    finals = {state_name(num_cities - 1, TIRE_OK)}

    return NFA(
        states=states,
        input_symbols=ACTIONS,
        transitions=transitions,
        initial_state=initial,
        final_states=finals,
    )


def expected_shortest_plan_length(num_cities):
    """Analytic minimum ``|w|`` for the interleaved ``(drive fix)^{N-1}`` plan."""
    return 2 * num_cities - 2


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=5)
    args = ap.parse_args()

    nfa = build_tireworld_nfa(args.n)
    n_trans = sum(
        len(s) for t in nfa.transitions.values() for s in t.values()
    )
    print(
        f"Tireworld (N={args.n}): |S|={len(nfa.states)}, |delta|={n_trans}, "
        f"|F|={len(nfa.final_states)}, alphabet={sorted(nfa.input_symbols)}"
    )
    print(f"initial: {nfa.initial_state}")
    print(f"finals: {sorted(nfa.final_states)}")
    print(f"analytic shortest strong plan length: "
          f"{expected_shortest_plan_length(args.n)}")
