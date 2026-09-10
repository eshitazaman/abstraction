"""First-responders (IPPC / FOND), two independent hazards.

IPPC first-responders mixes fire fighting with victim rescue.  We keep a
chain of N sites.  Advancing exposes *two* independent uncertainties at
the next site -- fire intensity and victim status -- so ``advance`` is
6-way, not a single tire-style coin flip.

    fire    in {out, smoldering, blazing}     (3)
    victim  in {safe, trapped}                (2)

``douse`` deterministically extinguishes any fire intensity (does not
touch the victim).  ``rescue`` deterministically frees a trapped victim
(does not touch the fire).  Neither action alone restores every branch.

Nondeterministic action
-----------------------
``advance`` at ``(s, out, safe)``, ``s < N-1``:
    all 6 (fire, victim) combinations at site s+1.

Recovery
--------
``douse``  : fire -> out,     victim unchanged
``rescue`` : victim -> safe,  fire unchanged

Advancing while fire is not out or a victim is still trapped goes to
``fail``.

Goal: ``(N-1, out, safe)``.
Shortest plan: ``(advance . douse . rescue)^{N-1}``, length ``3N - 3``.
"""

from automata.fa.nfa import NFA


OUT, SMOLDERING, BLAZING = "out", "smoldering", "blazing"
FIRES = (OUT, SMOLDERING, BLAZING)
SAFE, TRAPPED = "safe", "trapped"
VICTIMS = (SAFE, TRAPPED)

ACTIONS = frozenset({"advance", "douse", "rescue"})
FAIL_STATE = "fail"


def state_name(site, fire, victim):
    return f"s{site}_{fire}_{victim}"


def build_first_responders_nfa(num_sites):
    if num_sites < 2:
        raise ValueError("num_sites must be >= 2")

    states = {
        state_name(s, f, v)
        for s in range(num_sites)
        for f in FIRES
        for v in VICTIMS
    }
    states.add(FAIL_STATE)

    transitions = {
        FAIL_STATE: {a: {FAIL_STATE} for a in ACTIONS},
    }
    for s in range(num_sites):
        for f in FIRES:
            for v in VICTIMS:
                here = state_name(s, f, v)
                per_state = {
                    "douse": {state_name(s, OUT, v)},
                    "rescue": {state_name(s, f, SAFE)},
                }
                ready = (f == OUT and v == SAFE)
                if ready and s < num_sites - 1:
                    per_state["advance"] = {
                        state_name(s + 1, nf, nv)
                        for nf in FIRES
                        for nv in VICTIMS
                    }
                elif s < num_sites - 1:
                    per_state["advance"] = {FAIL_STATE}
                transitions[here] = per_state

    return NFA(
        states=states,
        input_symbols=ACTIONS,
        transitions=transitions,
        initial_state=state_name(0, OUT, SAFE),
        final_states={state_name(num_sites - 1, OUT, SAFE)},
    )


def expected_shortest_plan_length(num_sites):
    return 3 * num_sites - 3
