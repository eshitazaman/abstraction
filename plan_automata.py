"""
Automata-Based Plan Computation

This module implements the automata-based approach for computing valid plans
for an NFA, following the P1 and P2 conditions from the plan definition.

The approach:
1. Build DFA_P1 (P1-determinization) - DFA where a state is final only if ALL NFA states are final
2. Build NFA x DFA_P1 (product automaton) - NFA where a state is final only if the NFA state is final and the DFA_P1 state is final
3. Compute NFA_P2 (maximal P2-restriction, Lemma 9 / Algorithm 2: iterative transition removal + greatest fixpoint)
4. L(NFA_P2) = all valid plans
"""

from collections import deque

from automata.fa.nfa import NFA
from plts_to_nfa import build_nfa_from_file


class BudgetExhausted(Exception):
    """
    Raised by ``nfa_to_dfa_p1`` / ``build_product_nfa_dfa_p1`` when 
    supplied a size cap and the construction crossed it.

    The exception carries a ``partial`` dict with whatever was built so far,
    a ``stage`` label ("dfa_p1" or "product"), and the ``cap`` that was hit,
    so wrappers can return a well-formed "inconclusive within budget" result
    instead of losing the intermediate state.
    """

    def __init__(self, stage, cap, partial):
        super().__init__(
            f"{stage} construction exceeded budget of {cap} states"
        )
        self.stage = stage
        self.cap = cap
        self.partial = partial


def compute_reach_F(nfa):
    """
    Set of NFA states from which a final state is reachable in some number
    of steps (backward BFS on the transition graph).

    Correctness of using this for pruning:
        Any state s with s not in Reach_F cannot appear in a run that ends
        inside F. Under P1 (universal acceptance) the final macro-state
        must be a subset of F, so if a run through s survives inside a
        macro-state M until the end, then M ⊄ F and the plan is rejected.
        Under P2 the (state, action) pair that produces s must be dropped
        anyway.  Precomputing Reach_F lets us skip that work.
    """
    reverse = {s: [] for s in nfa.states}
    for s, trans in nfa.transitions.items():
        for _, succs in trans.items():
            for t in succs:
                if t in reverse:
                    reverse[t].append(s)

    reach = set(nfa.final_states)
    q = deque(reach)
    while q:
        t = q.popleft()
        for s in reverse.get(t, ()):
            if s not in reach:
                reach.add(s)
                q.append(s)
    return reach


def prune_dfa_p1_co_reachable(
    dfa_p1: dict,
) -> dict:
    """
    Drop **whole failing traces** (infinite-horizon), not one-step checks.

    A finite word / prefix corresponds to ending in some DFA_P1 macro-state. If
    from that state **no** continuation reaches **any** accepting macro-state, that
    prefix cannot be extended into a word in L(DFA_P1). Those macro-states and all
    transitions into them are removed. This is backward reachability from finals,
    not "the next cell isn't a goal."

    If there are no accepting DFA_P1 states (possible under P1 when no macro-state
    is all-goals), backward reachability is empty and pruning would erase the
    whole diagram — that would break product synchronization even when the
    original construction still matters. In that case we return the automaton
    unchanged.
    """
    finals = dfa_p1["finals"]
    if not finals:
        return dfa_p1

    transitions = dfa_p1["transitions"]

    rev = {}
    for s, symap in transitions.items():
        for a, t in symap.items():
            rev.setdefault(t, set()).add(s)

    live = set(finals)
    q = deque(finals)
    while q:
        t = q.popleft()
        for s in rev.get(t, ()):
            if s not in live:
                live.add(s)
                q.append(s)

    new_states = live
    new_finals = finals & new_states
    new_transitions = {}
    for s in new_states:
        symap = transitions.get(s, {})
        nt = {a: t for a, t in symap.items() if t in new_states}
        # Keep sinks (e.g. accepting states with no outgoing letters)
        new_transitions[s] = nt

    return {
        "states": new_states,
        "initial": dfa_p1["initial"],
        "finals": new_finals,
        "transitions": new_transitions,
        "input_symbols": dfa_p1["input_symbols"],
        "truncated": dfa_p1.get("truncated", False),
    }


def nfa_to_dfa_p1(nfa, verbose=False, max_states=None):
    """
    P1-Determinization: Builds DFA_P1 where a state is final only if ALL 
    NFA states it contains are final (satisfying P1 condition).

    Args:
        nfa: The input NFA.
        verbose: Print progress every 10K macro-states discovered.
        max_states: Optional hard cap on discovered macro-states. If the
            cap is crossed, ``BudgetExhausted`` is raised with the partial
            construction attached.

    Returns internal data structures for product construction.
    """
    # Precompute action successors once per NFA state; this dominates cost
    # for large NFAs with many actions per state. We do NOT prune here based
    # on Reach_F: intersecting successor sets with Reach_F silently drops
    # the "leaking" branches that P1's universal acceptance must see and
    # reject, which is unsound. Any Reach_F-based reasoning is done at the
    # pipeline level (checking whether s_init itself can reach F).
    succs_of = {}
    for s in nfa.states:
        smap = nfa.transitions.get(s, {})
        succs_of[s] = {
            a: frozenset(succs) for a, succs in smap.items() if succs
        }

    def dfa_transition(dfa_state, symbol):
        result = set()
        for nfa_state in dfa_state:
            sm = succs_of.get(nfa_state)
            if sm is not None:
                r = sm.get(symbol)
                if r:
                    result.update(r)
        return frozenset(result)

    initial_dfa_state = frozenset({nfa.initial_state})
    dfa_states = set()
    dfa_transitions = {}
    worklist = deque([initial_dfa_state])
    # Track whether any accepting macro has been seen mid-construction
    # (useful for early inspection of unbounded runs).
    accepting_seen = 0

    while worklist:
        current = worklist.popleft()
        if current in dfa_states:
            continue

        if max_states is not None and len(dfa_states) >= max_states:
            partial = {
                "states": dfa_states,
                "initial": initial_dfa_state,
                "finals": {
                    s for s in dfa_states
                    if s and s.issubset(nfa.final_states)
                },
                "transitions": dfa_transitions,
                "input_symbols": nfa.input_symbols,
                "truncated": True,
                "accepting_seen_so_far": accepting_seen,
            }
            raise BudgetExhausted("dfa_p1", max_states, partial)

        dfa_states.add(current)
        if current and current.issubset(nfa.final_states):
            accepting_seen += 1
        if verbose and len(dfa_states) % 10000 == 0:
            print(
                f"   ... DFA_P1 determinization in progress: "
                f"{len(dfa_states)} states discovered "
                f"(queued {len(worklist)}, "
                f"accepting-so-far {accepting_seen})"
            )
        dfa_transitions[current] = {}

        for symbol in nfa.input_symbols:
            next_state = dfa_transition(current, symbol)
            if next_state:
                dfa_transitions[current][symbol] = next_state
                if next_state not in dfa_states:
                    worklist.append(next_state)

    # P1 condition: final only if ALL states are final
    dfa_final_states = {
        s for s in dfa_states if s and s.issubset(nfa.final_states)
    }

    dfa_p1 = {
        "states": dfa_states,
        "initial": initial_dfa_state,
        "finals": dfa_final_states,
        "transitions": dfa_transitions,
        "input_symbols": nfa.input_symbols,
        "truncated": False,
    }
    return prune_dfa_p1_co_reachable(dfa_p1)


def build_product_nfa_dfa_p1(nfa, dfa_p1, verbose=False, max_states=None):
    """
    Builds the product automaton NFA x DFA_P1.
    
    States are pairs (s, ŝ) where s ∈ NFA states, ŝ ∈ DFA_P1 states.
    Transitions: ((s, ŝ), a, (s', ŝ')) exists iff (s, a, s') ∈ δ_NFA and (ŝ, a, ŝ') ∈ δ_DFA
    Final states: (s, ŝ) is final iff s ∈ F_NFA AND ŝ ∈ F_DFA_P1

    ``max_states`` optionally caps the reachable product state count and
    raises ``BudgetExhausted`` with a partial product attached if crossed.
    """
    def get_nfa_transitions(state, symbol):
        if state in nfa.transitions and symbol in nfa.transitions[state]:
            return nfa.transitions[state][symbol]
        return set()
    
    def get_dfa_transition(dfa_state, symbol):
        if dfa_state in dfa_p1['transitions'] and symbol in dfa_p1['transitions'][dfa_state]:
            return dfa_p1['transitions'][dfa_state][symbol]
        return None
    
    # Initial state of product
    initial_product = (nfa.initial_state, dfa_p1['initial'])
    
    # Explore reachable states
    product_states = set()
    product_transitions = {}
    worklist = deque([initial_product])
    
    while worklist:
        current = worklist.popleft()
        if current in product_states:
            continue

        if max_states is not None and len(product_states) >= max_states:
            partial_finals = {
                p for p in product_states
                if p[0] in nfa.final_states and p[1] in dfa_p1["finals"]
            }
            partial = {
                "states": product_states,
                "initial": initial_product,
                "finals": partial_finals,
                "transitions": product_transitions,
                "input_symbols": nfa.input_symbols,
                "truncated": True,
            }
            raise BudgetExhausted("product", max_states, partial)

        s_nfa, s_dfa = current
        product_states.add(current)
        if verbose and len(product_states) % 25000 == 0:
            print(
                f"   ... NFA×DFA_P1 product in progress: {len(product_states)} states "
                f"(queued {len(worklist)})"
            )
        product_transitions[current] = {}
        
        for symbol in nfa.input_symbols:
            nfa_successors = get_nfa_transitions(s_nfa, symbol)
            dfa_successor = get_dfa_transition(s_dfa, symbol)
            
            if nfa_successors and dfa_successor:
                product_transitions[current][symbol] = set()
                for s_prime in nfa_successors:
                    next_product = (s_prime, dfa_successor)
                    product_transitions[current][symbol].add(next_product)
                    if next_product not in product_states:
                        worklist.append(next_product)
    
    # Final states: (s, ŝ) final iff s ∈ F_NFA AND ŝ ∈ F_DFA_P1
    product_finals = set()
    for (s_nfa, s_dfa) in product_states:
        if s_nfa in nfa.final_states and s_dfa in dfa_p1['finals']:
            product_finals.add((s_nfa, s_dfa))
    
    return {
        'states': product_states,
        'initial': initial_product,
        'finals': product_finals,
        'transitions': product_transitions,
        'input_symbols': nfa.input_symbols
    }


def build_product_on_the_fly(nfa, verbose=False, max_states=None):
    """
    On-the-fly build of the NFA × DFA_P1 product.

    Runs a single BFS from (s_init, {s_init}), computing DFA_P1 macro
    successors ``ŝ' = ⋃_{s ∈ ŝ} δ(s, a)`` lazily on demand and caching
    them in ``dfa_transitions``. Avoids the separate ``nfa_to_dfa_p1``
    pass entirely and never visits DFA_P1 macros that don't appear in
    some reachable product pair.

    Returns the same shape as ``build_product_nfa_dfa_p1``, plus:
        * ``dfa_macros``      — the set of DFA_P1 macros encountered
        * ``accepting_macros``— macros in dfa_macros that are subsets of F
        * ``dfa_transitions`` — the cached δ_DFA[ŝ][a] table

    Complexity is the same worst case as the two-stage pipeline (each
    reachable product pair (s, ŝ) is visited once and each DFA transition
    δ_DFA(ŝ, a) is computed once), but there is no wasted DFA_P1 pass
    over macros that are unreachable in the product.
    """
    # Same successor precomputation trick as nfa_to_dfa_p1
    succs_of = {}
    for s in nfa.states:
        succs_of[s] = {
            a: frozenset(succs)
            for a, succs in nfa.transitions.get(s, {}).items()
            if succs
        }

    initial_macro = frozenset({nfa.initial_state})
    initial_product = (nfa.initial_state, initial_macro)

    product_states = set()
    product_transitions = {}
    dfa_transitions = {}
    dfa_macros = set()
    accepting_macros = set()
    worklist = deque([initial_product])

    while worklist:
        current = worklist.popleft()
        if current in product_states:
            continue

        if max_states is not None and len(product_states) >= max_states:
            partial_finals = {
                (s, m)
                for (s, m) in product_states
                if s in nfa.final_states and m in accepting_macros
            }
            partial = {
                "states": product_states,
                "initial": initial_product,
                "finals": partial_finals,
                "transitions": product_transitions,
                "input_symbols": nfa.input_symbols,
                "dfa_macros": dfa_macros,
                "accepting_macros": accepting_macros,
                "dfa_transitions": dfa_transitions,
                "truncated": True,
            }
            raise BudgetExhausted("product-otf", max_states, partial)

        s_nfa, s_dfa = current
        product_states.add(current)

        if s_dfa not in dfa_macros:
            dfa_macros.add(s_dfa)
            if s_dfa and s_dfa.issubset(nfa.final_states):
                accepting_macros.add(s_dfa)

        if verbose and len(product_states) % 25000 == 0:
            print(
                f"   ... on-the-fly product: {len(product_states)} states, "
                f"{len(dfa_macros)} DFA macros, "
                f"queued {len(worklist)}, "
                f"accepting-macros-so-far {len(accepting_macros)}"
            )

        product_transitions[current] = {}
        s_nfa_map = succs_of.get(s_nfa, {})

        for symbol, nfa_succs in s_nfa_map.items():
            # Lazy DFA transition: compute δ_DFA(ŝ, a) once and cache
            dt = dfa_transitions.setdefault(s_dfa, {})
            s_dfa_next = dt.get(symbol)
            if s_dfa_next is None:
                acc = set()
                for s in s_dfa:
                    sm = succs_of.get(s, {})
                    r = sm.get(symbol)
                    if r:
                        acc |= r
                s_dfa_next = frozenset(acc)
                dt[symbol] = s_dfa_next

            if not s_dfa_next:
                continue

            transitions_here = product_transitions[current].setdefault(
                symbol, set()
            )
            for s_prime in nfa_succs:
                new_pair = (s_prime, s_dfa_next)
                transitions_here.add(new_pair)
                if new_pair not in product_states:
                    worklist.append(new_pair)

    product_finals = {
        (s, m)
        for (s, m) in product_states
        if s in nfa.final_states and m in accepting_macros
    }

    return {
        "states": product_states,
        "initial": initial_product,
        "finals": product_finals,
        "transitions": product_transitions,
        "input_symbols": nfa.input_symbols,
        "dfa_macros": dfa_macros,
        "accepting_macros": accepting_macros,
        "dfa_transitions": dfa_transitions,
        "truncated": False,
    }


def compute_nfa_p2(product_nfa, verbose=False):
    """
    Compute NFA_P2: the maximal P2-restriction of the product NFA × DFA_P1.

    Implements Lemma 9 / Algorithm 2 (iterative transition removal): alternate
    backward reachability to finals, greatest-fixpoint validity (non-final states
    need some action whose successors are all valid), then drop violating
    (state, action) pairs until stable.

    Uses a GREATEST fixpoint so self-loops are valid only when a path to finals
    still exists.

    Returns:
        dict with 'states', 'initial', 'finals', 'transitions', 'input_symbols',
        and 'iterations' (outer refinement rounds).
    """
    states = set(product_nfa['states'])
    finals = set(product_nfa['finals'])
    initial = product_nfa['initial']
    input_symbols = product_nfa['input_symbols']
    
    # Deep copy transitions (we'll modify them iteratively)
    transitions = {}
    for s, trans in product_nfa['transitions'].items():
        transitions[s] = {}
        for a, succs in trans.items():
            transitions[s][a] = set(succs)
    
    iteration = 0
    changed = True
    
    while changed:
        iteration += 1
        changed = False
        if verbose and (iteration <= 30 or iteration % 50 == 0):
            print(
                f"   ... NFA_P2: outer iteration {iteration} "
                f"(states in working graph ≈ {len(states)})"
            )

        # Step 1: Compute states that can reach finals (backward reachability)
        can_reach_final = set(finals)
        inner_changed = True
        while inner_changed:
            inner_changed = False
            for s in states:
                if s in can_reach_final:
                    continue
                if s in transitions:
                    for a, succs in transitions[s].items():
                        if succs & can_reach_final:
                            can_reach_final.add(s)
                            inner_changed = True
                            break
        
        # Step 2: Use GREATEST fixpoint to compute valid states
        valid_states = set(can_reach_final)
        inner_changed = True
        while inner_changed:
            inner_changed = False
            to_remove = set()
            for s in valid_states:
                if s in finals:
                    continue
                has_valid_action = False
                if s in transitions:
                    for a, succs in transitions[s].items():
                        if succs and all(succ in valid_states for succ in succs):
                            has_valid_action = True
                            break
                if not has_valid_action:
                    to_remove.add(s)
            if to_remove:
                valid_states -= to_remove
                inner_changed = True
        
        # Invalid states
        invalid_states = states - valid_states
        
        if not invalid_states:
            break  # All remaining states are valid
        
        # Step 3: Remove only product transitions that violate P2 *locally*.
        #
        # P2 is universal over nondeterministic successors at each product state (s, ŝ):
        # symbol a may stay only if every a-successor lies in valid_states. Grouping by
        # DFA macro-state and banning an action for *all* pairs (s', ŝ) in that class
        # is unsound: different s' can legitimately keep different letters under the
        # same ŝ. Build closure as explicit (state, action) pairs.
        closure = set()
        for s in states:
            if s not in transitions:
                continue
            for a, succs in transitions[s].items():
                if not succs or not all(succ in valid_states for succ in succs):
                    closure.add((s, a))
        
        # Step 4: Remove transitions δ_{i+1} = δ_i \ closure
        for s, a in closure:
            if s in transitions and a in transitions[s]:
                del transitions[s][a]
                changed = True
        
        # Clean up empty transition dictionaries
        transitions = {s: t for s, t in transitions.items() if t}
        
        # Update reachable states (remove unreachable states)
        if initial:
            reachable = {initial}
            worklist = deque([initial])
            while worklist:
                state = worklist.popleft()
                if state in transitions:
                    for a, succs in transitions[state].items():
                        for succ in succs:
                            if succ not in reachable:
                                reachable.add(succ)
                                worklist.append(succ)
            states = reachable
            finals = finals & reachable
    
    # Final result
    if not initial or initial not in states:
        return {
            'states': set(),
            'initial': None,
            'finals': set(),
            'transitions': {},
            'input_symbols': input_symbols,
            'iterations': iteration
        }
    
    # Convert transition sets back to lists for consistency
    final_transitions = {}
    for s in states:
        if s in transitions:
            final_transitions[s] = {a: list(succs) for a, succs in transitions[s].items()}
    
    return {
        'states': states,
        'initial': initial,
        'finals': finals & states,
        'transitions': final_transitions,
        'input_symbols': input_symbols,
        'iterations': iteration
    }


def enumerate_valid_plans(nfa_p2, max_length=10):
    """
    Enumerates all valid plans (words) accepted by NFA_P2 up to max_length.
    These are all words that satisfy both P1 and P2.
    """
    if nfa_p2['initial'] is None:
        return set()
    
    valid_words = set()
    
    def dfs(state, word):
        if len(word) > max_length:
            return
        if state in nfa_p2['finals']:
            valid_words.add(word)
        if state in nfa_p2['transitions']:
            for symbol, successors in nfa_p2['transitions'][state].items():
                for succ in successors:
                    dfs(succ, word + symbol)
    
    dfs(nfa_p2['initial'], "")
    return valid_words


def nfa_p2_language_nonempty(nfa_p2):
    """
    True iff L(NFA_P2) is non-empty: some path from initial to a final state exists.

    This answers whether there exists *any* P1∧P2-valid plan (no length bound),
    without enumerating all words.
    """
    from collections import deque

    if nfa_p2.get("initial") is None:
        return False
    init = nfa_p2["initial"]
    finals = nfa_p2["finals"]
    if init in finals:
        return True
    q = deque([init])
    seen = {init}
    while q:
        s = q.popleft()
        if s in finals:
            return True
        for succs in nfa_p2.get("transitions", {}).get(s, {}).values():
            for t in succs:
                if t not in seen:
                    seen.add(t)
                    q.append(t)
    return False


def nfa_p2_shortest_accepting_length(nfa_p2):
    """
    Minimum number of symbols (moves) in any word accepted by NFA_P2, or None if L(NFA_P2)
    is empty. Uses BFS on the underlying graph (each transition is one symbol).
    """
    from collections import deque

    if nfa_p2.get("initial") is None:
        return None
    init = nfa_p2["initial"]
    finals = nfa_p2["finals"]
    if init in finals:
        return 0
    q = deque([(init, 0)])
    seen = {init}
    while q:
        s, d = q.popleft()
        for succs in nfa_p2.get("transitions", {}).get(s, {}).values():
            for t in succs:
                nd = d + 1
                if t in finals:
                    return nd
                if t not in seen:
                    seen.add(t)
                    q.append((t, nd))
    return None


def _empty_verdict(nfa, dfa_p1, product, reason, enumerate_plans, verbose,
                   inconclusive=False):
    """Build a fully-formed return dict for the "no valid plans" outcomes."""
    empty_nfa_p2 = {
        "states": set(),
        "initial": None,
        "finals": set(),
        "transitions": {},
        "input_symbols": nfa.input_symbols,
        "iterations": 0,
    }
    stats = {
        "nfa_states": len(nfa.states),
        "nfa_transitions": sum(
            len(succs)
            for trans in nfa.transitions.values()
            for succs in trans.values()
        ),
        "nfa_finals": len(nfa.final_states),
        "dfa_p1_states": len(dfa_p1["states"]) if dfa_p1 else 0,
        "dfa_p1_transitions": (
            sum(len(t) for t in dfa_p1["transitions"].values()) if dfa_p1 else 0
        ),
        "dfa_p1_finals": len(dfa_p1["finals"]) if dfa_p1 else 0,
        "product_states": len(product["states"]) if product else 0,
        "product_transitions": (
            sum(
                len(s)
                for t in product["transitions"].values()
                for s in t.values()
            )
            if product
            else 0
        ),
        "product_finals": len(product["finals"]) if product else 0,
        "nfa_p2_reachable": 0,
        "nfa_p2_unreachable": (
            len(product["states"]) if product else 0
        ),
        "nfa_p2_transitions": 0,
        "nfa_p2_finals": 0,
        "language_nonempty": False,
        "shortest_plan_length": None,
        "short_circuit_reason": reason,
        "inconclusive": inconclusive,
    }
    if verbose:
        tag = "INCONCLUSIVE" if inconclusive else "L(NFA_P2) = ∅"
        print(f"\n>>> {tag}: {reason}")
    return {
        "dfa_p1": dfa_p1
        or {
            "states": set(),
            "initial": None,
            "finals": set(),
            "transitions": {},
            "input_symbols": nfa.input_symbols,
        },
        "product": product
        or {
            "states": set(),
            "initial": None,
            "finals": set(),
            "transitions": {},
            "input_symbols": nfa.input_symbols,
        },
        "nfa_p2": empty_nfa_p2,
        "valid_plans": set() if enumerate_plans and not inconclusive else None,
        "language_nonempty": False,
        "shortest_plan_length": None,
        "stats": stats,
        "unreachable_states": (
            product["states"] if product else set()
        ),
        "short_circuit_reason": reason,
        "inconclusive": inconclusive,
    }


def automata_based_plan_computation(
    nfa,
    verbose=True,
    enumerate_plans=True,
    filter_dead_states=True,
    max_dfa_p1_states=None,
    max_product_states=None,
    short_circuit=True,
):
    """
    Computes all valid plans using the automata-based approach:
    1. (opt.) Prune NFA states that cannot reach F (correctness-preserving).
    2. Build DFA_P1 (P1-determinization).
    3. If DFA_P1 has no accepting macro-states, short-circuit: L(NFA_P2)=∅.
    4. Build NFA x DFA_P1 (product automaton).
    5. Compute NFA_P2 (maximal P2-restriction; Lemma 9 / Algorithm 2).
    6. L(NFA_P2) = all valid plans (optional: skip enumeration).

    Args:
        nfa: The input NFA.
        verbose: If True, print progress information.
        enumerate_plans: If False, skip DFS enumeration of all words; use
            ``language_nonempty`` for existence.
        filter_dead_states: If True (default), precompute Reach_F and prune
            successors that can never lead to acceptance. Fast, sound.
        max_dfa_p1_states: Optional cap on subset-construction size. If the
            cap is crossed, the pipeline returns an "inconclusive" verdict
            with partial DFA_P1 attached instead of running to completion.
        max_product_states: Analogous cap on the product construction.

    Returns:
        Dictionary containing:
        - 'dfa_p1': The P1-determinization (possibly partial if truncated)
        - 'product': The product automaton NFA × DFA_P1 (possibly partial)
        - 'nfa_p2': The maximal P2-restriction (empty on short-circuit)
        - 'valid_plans': Set of valid plan words, or None
        - 'language_nonempty': True iff some P1∧P2 valid plan exists
        - 'shortest_plan_length': Min number of moves in any accepting word
        - 'short_circuit_reason': Explanation string when we bailed early
        - 'inconclusive': True iff we bailed out due to a budget cap
    """
    if verbose:
        print("\n" + "="*60)
        print("AUTOMATA-BASED PLAN COMPUTATION [NFA_P2: Lemma 9 / Algorithm 2]")
        print("="*60)

    if filter_dead_states:
        reach_F = compute_reach_F(nfa)
        if verbose:
            n_dead = len(nfa.states) - len(reach_F)
            print(
                f"\n0. Reach_F check: "
                f"{len(reach_F)} states can reach F, "
                f"{n_dead} cannot."
            )
        if nfa.initial_state not in reach_F:
            return _empty_verdict(
                nfa,
                dfa_p1=None,
                product=None,
                reason=(
                    "initial state cannot reach any final state in NFA "
                    "(Reach_F does not contain s_init)"
                ),
                enumerate_plans=enumerate_plans,
                verbose=verbose,
            )

    # Step 1: Build DFA_P1 (optionally budget-capped)
    if verbose:
        print("\n1. Building DFA_P1 (P1-determinization)...")
    try:
        dfa_p1 = nfa_to_dfa_p1(
            nfa,
            verbose=verbose,
            max_states=max_dfa_p1_states,
        )
    except BudgetExhausted as e:
        return _empty_verdict(
            nfa,
            dfa_p1=e.partial,
            product=None,
            reason=(
                f"DFA_P1 construction exceeded budget of "
                f"{e.cap} macro-states"
            ),
            enumerate_plans=enumerate_plans,
            verbose=verbose,
            inconclusive=True,
        )
    if verbose:
        print(f"   States: {len(dfa_p1['states'])}")
        print(f"   Final states: {len(dfa_p1['finals'])}")

    # Short-circuit: no accepting DFA_P1 macro ⇒ L(NFA_P2) is empty.
    # (Skipped when short_circuit=False so we can benchmark the pure two-stage
    # pipeline that always builds the product regardless of emptiness.)
    if short_circuit and not dfa_p1["finals"]:
        return _empty_verdict(
            nfa,
            dfa_p1=dfa_p1,
            product=None,
            reason=(
                "DFA_P1 has 0 accepting macro-states "
                "(no reachable subset of F under universal P1)"
            ),
            enumerate_plans=enumerate_plans,
            verbose=verbose,
        )

    # Step 2: Build product NFA × DFA_P1 (optionally budget-capped)
    if verbose:
        print("\n2. Building NFA x DFA_P1 (product automaton)...")
    try:
        product = build_product_nfa_dfa_p1(
            nfa, dfa_p1, verbose=verbose, max_states=max_product_states
        )
    except BudgetExhausted as e:
        return _empty_verdict(
            nfa,
            dfa_p1=dfa_p1,
            product=e.partial,
            reason=(
                f"Product construction exceeded budget of "
                f"{e.cap} states"
            ),
            enumerate_plans=enumerate_plans,
            verbose=verbose,
            inconclusive=True,
        )
    product_trans = sum(len(succs) for trans in product['transitions'].values() for succs in trans.values())
    if verbose:
        print(f"   States: {len(product['states'])}")
        print(f"   Final states: {len(product['finals'])}")
        print(f"   Transitions: {product_trans}")

    # If the product has no accepting states, L(NFA_P2)=∅ as well
    # (accepting requires s in F_NFA AND ŝ in F_DFA_P1, so this is a
    # slightly stricter check than the DFA_P1-only test above). Skipped
    # under short_circuit=False so pure two-stage still runs the P2 fixpoint.
    if short_circuit and not product["finals"]:
        return _empty_verdict(
            nfa,
            dfa_p1=dfa_p1,
            product=product,
            reason=(
                "Product NFA × DFA_P1 has 0 accepting states"
            ),
            enumerate_plans=enumerate_plans,
            verbose=verbose,
        )

    # Step 3: Compute NFA_P2
    if verbose:
        print("\n3. Computing NFA_P2 (iterative P2 restriction)...")

    nfa_p2 = compute_nfa_p2(product, verbose=verbose)
    
    # Count transitions in NFA_P2
    nfa_p2_trans = 0
    for state, trans in nfa_p2['transitions'].items():
        for action, succs in trans.items():
            if isinstance(succs, (list, set)):
                nfa_p2_trans += len(succs)
            else:
                nfa_p2_trans += 1
    
    # Compute reachable/unreachable states
    reachable_states = nfa_p2['states']
    unreachable_states = product['states'] - reachable_states
    
    if verbose:
        print(f"   Reachable states: {len(reachable_states)}")
        print(f"   Unreachable states: {len(unreachable_states)}")
        print(f"   Total states: {len(product['states'])}")
        print(f"   Transitions: {nfa_p2_trans}")
        print(f"   Final states: {len(nfa_p2['finals'])}")
        if "iterations" in nfa_p2:
            print(f"   Iterations: {nfa_p2['iterations']}")
        if not nfa_p2['initial']:
            print("   No valid plans exist!")
    
    language_nonempty = nfa_p2_language_nonempty(nfa_p2)
    shortest_plan_length = nfa_p2_shortest_accepting_length(nfa_p2)

    # Step 4: Enumerate valid plans (optional)
    if enumerate_plans:
        if verbose:
            print("\n4. Enumerating valid plans from L(NFA_P2)...")
        valid_plans = enumerate_valid_plans(nfa_p2)
        if verbose:
            print(f"   Valid plans: {valid_plans if valid_plans else 'None'}")
    else:
        valid_plans = None
        if verbose:
            print("\n4. Skipping plan enumeration (enumerate_plans=False).")
            print(
                f"   L(NFA_P2) non-empty (exists some P1∧P2 plan): {language_nonempty}"
            )
            if language_nonempty:
                print(
                    f"   Shortest valid plan length (moves): {shortest_plan_length}"
                )

    # Store statistics
    stats = {
        'nfa_states': len(nfa.states),
        'nfa_transitions': sum(len(succs) for trans in nfa.transitions.values() for succs in trans.values()),
        'nfa_finals': len(nfa.final_states),
        'dfa_p1_states': len(dfa_p1['states']),
        'dfa_p1_transitions': sum(len(t) for t in dfa_p1['transitions'].values()),  # DFA: 1 successor per (state,action)
        'dfa_p1_finals': len(dfa_p1['finals']),
        'product_states': len(product['states']),
        'product_transitions': product_trans,  # Use pre-computed count
        'product_finals': len(product['finals']),
        'nfa_p2_reachable': len(reachable_states),
        'nfa_p2_unreachable': len(unreachable_states),
        'nfa_p2_transitions': nfa_p2_trans,
        'nfa_p2_finals': len(nfa_p2['finals']),
        'language_nonempty': language_nonempty,
        'shortest_plan_length': shortest_plan_length,
        'short_circuit_reason': None,
        'inconclusive': False,
    }

    return {
        'dfa_p1': dfa_p1,
        'product': product,
        'nfa_p2': nfa_p2,
        'valid_plans': valid_plans,
        'language_nonempty': language_nonempty,
        'shortest_plan_length': shortest_plan_length,
        'stats': stats,
        'unreachable_states': unreachable_states,
        'short_circuit_reason': None,
        'inconclusive': False,
    }


def automata_based_plan_on_the_fly(
    nfa,
    verbose=True,
    enumerate_plans=True,
    filter_dead_states=True,
    max_product_states=None,
):
    """
    On-the-fly variant of :func:`automata_based_plan_computation`.

    Fuses DFA_P1 subset construction and product BFS into a single pass
    (:func:`build_product_on_the_fly`), then runs the same P2 fixpoint
    (:func:`compute_nfa_p2`) on the result.

    Same guarantees, same return shape as ``automata_based_plan_computation``.
    On empty inputs the empty-accepting-macros short-circuit still applies,
    but here it can only fire *after* the full on-the-fly product has been
    built (since we cannot know DFA_P1 has no accepting macros until we
    have explored every reachable macro from ``s_init``).
    """
    if verbose:
        print("\n" + "=" * 60)
        print("AUTOMATA-BASED PLAN COMPUTATION [on-the-fly product]")
        print("=" * 60)

    if filter_dead_states:
        reach_F = compute_reach_F(nfa)
        if verbose:
            n_dead = len(nfa.states) - len(reach_F)
            print(
                f"\n0. Reach_F check: "
                f"{len(reach_F)} states can reach F, "
                f"{n_dead} cannot."
            )
        if nfa.initial_state not in reach_F:
            return _empty_verdict(
                nfa,
                dfa_p1=None,
                product=None,
                reason=(
                    "initial state cannot reach any final state in NFA "
                    "(Reach_F does not contain s_init)"
                ),
                enumerate_plans=enumerate_plans,
                verbose=verbose,
            )

    if verbose:
        print(
            "\n1+2. Building product on-the-fly (fused subset + product BFS)..."
        )
    try:
        product = build_product_on_the_fly(
            nfa, verbose=verbose, max_states=max_product_states
        )
    except BudgetExhausted as e:
        partial_dfa_p1 = {
            "states": e.partial.get("dfa_macros", set()),
            "initial": frozenset({nfa.initial_state}),
            "finals": e.partial.get("accepting_macros", set()),
            "transitions": {
                m: dict(t)
                for m, t in e.partial.get("dfa_transitions", {}).items()
            },
            "input_symbols": nfa.input_symbols,
            "truncated": True,
        }
        return _empty_verdict(
            nfa,
            dfa_p1=partial_dfa_p1,
            product=e.partial,
            reason=(
                f"On-the-fly product construction exceeded budget of "
                f"{e.cap} states"
            ),
            enumerate_plans=enumerate_plans,
            verbose=verbose,
            inconclusive=True,
        )

    # Synthesize a DFA_P1-shaped dict from the on-the-fly by-product so
    # that callers depending on ``result['dfa_p1']`` still work.
    dfa_p1 = {
        "states": product["dfa_macros"],
        "initial": frozenset({nfa.initial_state}),
        "finals": product["accepting_macros"],
        "transitions": product["dfa_transitions"],
        "input_symbols": nfa.input_symbols,
        "truncated": False,
    }
    product_trans = sum(
        len(s)
        for t in product["transitions"].values()
        for s in t.values()
    )
    if verbose:
        print(
            f"   Product states: {len(product['states'])}, "
            f"DFA macros seen: {len(product['dfa_macros'])}, "
            f"accepting macros: {len(product['accepting_macros'])}, "
            f"product finals: {len(product['finals'])}, "
            f"transitions: {product_trans}"
        )

    if not product["accepting_macros"]:
        return _empty_verdict(
            nfa,
            dfa_p1=dfa_p1,
            product=product,
            reason=(
                "on-the-fly DFA_P1 has 0 accepting macro-states "
                "(no reachable subset of F under universal P1)"
            ),
            enumerate_plans=enumerate_plans,
            verbose=verbose,
        )

    if not product["finals"]:
        return _empty_verdict(
            nfa,
            dfa_p1=dfa_p1,
            product=product,
            reason="on-the-fly product has 0 accepting states",
            enumerate_plans=enumerate_plans,
            verbose=verbose,
        )

    if verbose:
        print("\n3. Computing NFA_P2 (iterative P2 restriction)...")
    nfa_p2 = compute_nfa_p2(product, verbose=verbose)

    nfa_p2_trans = 0
    for state, trans in nfa_p2["transitions"].items():
        for _, succs in trans.items():
            if isinstance(succs, (list, set)):
                nfa_p2_trans += len(succs)
            else:
                nfa_p2_trans += 1

    reachable_states = nfa_p2["states"]
    unreachable_states = product["states"] - reachable_states

    if verbose:
        print(f"   Reachable states: {len(reachable_states)}")
        print(f"   Unreachable states: {len(unreachable_states)}")
        print(f"   Total states: {len(product['states'])}")
        print(f"   Transitions: {nfa_p2_trans}")
        print(f"   Final states: {len(nfa_p2['finals'])}")
        if "iterations" in nfa_p2:
            print(f"   Iterations: {nfa_p2['iterations']}")

    language_nonempty = nfa_p2_language_nonempty(nfa_p2)
    shortest_plan_length = nfa_p2_shortest_accepting_length(nfa_p2)

    if enumerate_plans:
        if verbose:
            print("\n4. Enumerating valid plans from L(NFA_P2)...")
        valid_plans = enumerate_valid_plans(nfa_p2)
        if verbose:
            print(f"   Valid plans: {valid_plans if valid_plans else 'None'}")
    else:
        valid_plans = None
        if verbose:
            print("\n4. Skipping plan enumeration (enumerate_plans=False).")
            print(
                f"   L(NFA_P2) non-empty (exists some P1∧P2 plan): "
                f"{language_nonempty}"
            )
            if language_nonempty:
                print(
                    f"   Shortest valid plan length (moves): "
                    f"{shortest_plan_length}"
                )

    stats = {
        "nfa_states": len(nfa.states),
        "nfa_transitions": sum(
            len(succs)
            for trans in nfa.transitions.values()
            for succs in trans.values()
        ),
        "nfa_finals": len(nfa.final_states),
        "dfa_p1_states": len(product["dfa_macros"]),
        "dfa_p1_transitions": sum(
            len(t) for t in product["dfa_transitions"].values()
        ),
        "dfa_p1_finals": len(product["accepting_macros"]),
        "product_states": len(product["states"]),
        "product_transitions": product_trans,
        "product_finals": len(product["finals"]),
        "nfa_p2_reachable": len(reachable_states),
        "nfa_p2_unreachable": len(unreachable_states),
        "nfa_p2_transitions": nfa_p2_trans,
        "nfa_p2_finals": len(nfa_p2["finals"]),
        "language_nonempty": language_nonempty,
        "shortest_plan_length": shortest_plan_length,
        "short_circuit_reason": None,
        "inconclusive": False,
    }

    return {
        "dfa_p1": dfa_p1,
        "product": product,
        "nfa_p2": nfa_p2,
        "valid_plans": valid_plans,
        "language_nonempty": language_nonempty,
        "shortest_plan_length": shortest_plan_length,
        "stats": stats,
        "unreachable_states": unreachable_states,
        "short_circuit_reason": None,
        "inconclusive": False,
    }


def product_state_name(state):
    """Convert product state (s, frozenset) to readable string."""
    s_nfa, s_dfa = state
    dfa_str = "{" + ",".join(sorted(s_dfa)) + "}"
    return f"({s_nfa},{dfa_str})"


def nfa_p2_to_nfa_object(nfa_p2, original_nfa):
    """
    Converts the NFA_P2 dictionary to an NFA object for visualization.
    
    Args:
        nfa_p2: The NFA_P2 dictionary from compute_nfa_p2
        original_nfa: The original NFA (for input_symbols)
        
    Returns:
        An NFA object that can be visualized, or None if NFA_P2 is empty
    """
    if not nfa_p2['states'] or nfa_p2['initial'] is None:
        return None
    
    # Convert states to string names
    state_names = {s: product_state_name(s) for s in nfa_p2['states']}
    
    states = set(state_names.values())
    initial = state_names[nfa_p2['initial']]
    finals = {state_names[s] for s in nfa_p2['finals']}
    
    transitions = {}
    for state, trans in nfa_p2['transitions'].items():
        state_name = state_names[state]
        transitions[state_name] = {}
        for symbol, successors in trans.items():
            transitions[state_name][symbol] = {state_names[s] for s in successors}
    
    return NFA(
        states=states,
        input_symbols=original_nfa.input_symbols,
        transitions=transitions,
        initial_state=initial,
        final_states=finals
    )


def build_np2_automaton(nfa: NFA, verbose: bool = False):
    """
    Build the NP2 automaton (i.e., NFA_P2 that enforces P1 ∧ P2) from an input NFA.

    This is a convenience wrapper around:
      - P1-determinization (DFA_P1)
      - product construction (NFA × DFA_P1)
      - maximal P2 restriction (NFA_P2 via Lemma 9 / Algorithm 2)

    Returns:
        (np2_nfa_object, nfa_p2_dict, product_dict, dfa_p1_dict)
    """
    if verbose:
        print(
            "Building DFA_P1 (this can dominate runtime; nondeterministic NFAs explode here)..."
        )
    dfa_p1 = nfa_to_dfa_p1(nfa, verbose=verbose)

    dfa_p1_n_states = len(dfa_p1["states"])
    dfa_p1_n_trans = sum(len(t) for t in dfa_p1["transitions"].values())
    dfa_p1_n_finals = len(dfa_p1["finals"])
    print(
        f"DFA_P1 complete (before product × NFA_P2): "
        f"{dfa_p1_n_states} states, "
        f"{dfa_p1_n_trans} transitions (state,symbol pairs), "
        f"{dfa_p1_n_finals} finals",
        flush=True,
    )

    if verbose:
        print("Building product NFA × DFA_P1...", flush=True)
    product = build_product_nfa_dfa_p1(nfa, dfa_p1, verbose=verbose)

    if verbose:
        print("Computing NFA_P2 (Lemma 9 / Algorithm 2)...", flush=True)
    nfa_p2 = compute_nfa_p2(product, verbose=verbose)

    np2_obj = nfa_p2_to_nfa_object(nfa_p2, nfa)
    return np2_obj, nfa_p2, product, dfa_p1


def is_word_valid(nfa_p2, word):
    """
    Check if a word is accepted by NFA_P2 (i.e., is a valid plan element).
    
    Args:
        nfa_p2: The NFA_P2 dictionary
        word: The word to check
        
    Returns:
        True if the word is a valid plan element, False otherwise
    """
    if nfa_p2['initial'] is None:
        return False
    
    current_states = {nfa_p2['initial']}
    for symbol in word:
        next_states = set()
        for state in current_states:
            if state in nfa_p2['transitions'] and symbol in nfa_p2['transitions'][state]:
                next_states.update(nfa_p2['transitions'][state][symbol])
        current_states = next_states
        if not current_states:
            return False
    
    return bool(current_states.intersection(nfa_p2['finals']))


def is_plan_valid(nfa_p2, plan):
    """
    Check if a plan (set of words) is valid using NFA_P2.
    
    Args:
        nfa_p2: The NFA_P2 dictionary
        plan: A set of words
        
    Returns:
        True if all words in the plan are valid, False otherwise
    """
    return all(is_word_valid(nfa_p2, word) for word in plan)


# ============================================================================
# Main - Demo of Automata-Based Plan Computation
# ============================================================================

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Automata-based plan computation')
    parser.add_argument('--example', action='store_true', 
                        help='Use the example NFA instead of loading from file')
    parser.add_argument('--file', type=str, default='salon-4-0.25.kr',
                        help='Path to .kr file (default: salon-4-0.25.kr)')
    parser.add_argument('--deterministic', '-d', action='store_true',
                        help='Use deterministic NFA generation')
    args = parser.parse_args()
    
    # Build the NFA
    if args.example:
        # Example NFA from the paper's figure
        # L(NFA) = {a, aa, b, ba}
        # Valid plans: {b}, {ba}, {b, ba}
        #example 1
        # my_nfa = NFA(
        #     states={"s0", "s1", "s2", "s3"},
        #     input_symbols={"a", "b"},
        #     transitions={
        #         "s0": {"a": {"s1", "s2"}, "b": {"s2"}},
        #         "s1": {},
        #         "s2": {"a": {"s3"}},
        #         "s3": {},
        #     },
        #     initial_state="s0",
        #     final_states={"s2", "s3"},
        # )
        #example 2
        my_nfa = NFA(
            states={"s0", "s1", "s2", "s3", "s4"},
            input_symbols={"a", "b"},
            transitions={
                "s0": {"a": {"s1", "s2"}},
                "s1": {"a": {"s1"}},
                "s2": {"a": {"s2","s3"}},
                "s3": {"b": {"s4"}},
                "s4": {},
            },
            initial_state="s0",
            final_states={"s1", "s4"},
        )
        #example 3
        # my_nfa = NFA(
        #     states={"s0", "s1", "s2", "s3", "s4","s5","s6"},
        #     input_symbols={"a", "b", "c"},
        #     transitions={
        #         "s0": {"a": {"s1", "s2"}},
        #         "s1": {"a": {"s1","s3"}},
        #         "s2": {"a": {"s4"}},
        #         "s3": {"b": {"s5"}},
        #         "s4": {"c": {"s6"}},   
        #         "s5": {},
        #         "s6": {},
        #     },
        #     initial_state="s0",
        #     final_states={"s1", "s4", "s5", "s6"},
        # )
        #example 4
        # my_nfa = NFA(
        #     states={"s0", "s1", "s2", "s3", "s4"},
        #     input_symbols={"a", "b"},
        #     transitions={
        #         "s0": {"a": {"s1", "s2"}},
        #         "s1": {"a": {"s1"},"b": {"s3"}},
        #         "s2": {"a": {"s4"}},
        #         "s3": {},
        #         "s4": {"b": {"s3"}},   
        #     },
        #     initial_state="s0",
        #     final_states={"s3"},
        # )
        #example 5
        # my_nfa = NFA(
        #     states={"s0", "s1", "s2", "s3", "s4","s5"},
        #     input_symbols={"a", "b","c"},
        #     transitions={
        #         "s0": {"a": {"s1", "s2"}},
        #         "s1": {"a": {"s1"},"b": {"s5"},"c": {"s3"}},
        #         "s2": {"a": {"s4"}},
        #         "s3": {},
        #         "s4": {"c": {"s3"}}, 
        #         "s5": {},
        #     },
        #     initial_state="s0",
        #     final_states={"s1","s4","s3"},
        # )
        #example 6
        # my_nfa = NFA(
        #     states={"s0", "s1", "s2", "s3", "s4","s5","s6","s7","s8"},
        #     input_symbols={"a", "b"},
        #     transitions={
        #         "s0": {"a": {"s2","s3"},"b": {"s1","s3"}},
        #         "s1": {"a": {"s4"}},
        #         "s2": {"b": {"s4"}},
        #         "s3": {"a": {"s7"},"b": {"s6"}},
        #         "s4": {"b": {"s5"}}, 
        #         "s5": {},
        #         "s6": {"b": {"s8"}},
        #         "s7": {},
        #         "s8": {},
        #     },
        #     initial_state="s0",
        #     final_states={"s2","s4","s5","s7"},
        # )
        #example 7
        # my_nfa = NFA(
        #     states={"s0", "s1", "s2", "s3", "s4","s5"},
        #     input_symbols={"a", "b"},
        #     transitions={
        #         "s0": {"a": {"s1","s2"}},
        #         "s1": {"a": {"s1"},"b":{"s3"}},
        #         "s2": {"a": {"s4"}},
        #         "s3": {},
        #         "s4": {"b": {"s3"},"a":{"s5"}}, 
        #         "s5": {},
        #     },
        #     initial_state="s0",
        #     final_states={"s3"},
        # )
        #example 8
        # my_nfa = NFA(
        #     states={"s0", "s1", "s2", "s3", "s4"},
        #     input_symbols={"a", "b"},
        #     transitions={
        #         "s0": {"a": {"s1","s2"}},
        #         "s1": {"a": {"s1"},"b":{"s3"}},
        #         "s2": {"a": {"s4"}},
        #         "s3": {},
        #         "s4": {"a":{"s2"},"b":{"s3"}},
        #     },
        #     initial_state="s0",
        #     final_states={"s3"},
        # )
        #example 9
        # my_nfa = NFA(
        #     states={"s0", "s1", "s2", "s3", "s4"},
        #     input_symbols={"a", "b"},
        #     transitions={
        #         "s0": {"a": {"s1","s2"}},
        #         "s1": {"a": {"s1"},"b":{"s3"}},
        #         "s2": {"a": {"s4"},"b":{"s1"}},
        #         "s3": {},
        #         "s4": {"b": {"s3"}}, 
        #     },
        #     initial_state="s0",
        #     final_states={"s3"},
        # )

        print("=" * 60)
        print("EXAMPLE NFA")
        print("=" * 60)
        print(f"States: {my_nfa.states}")
        print(f"Initial: {my_nfa.initial_state}")
        print(f"Finals: {my_nfa.final_states}")
        print("L(NFA) = {a^n b | n >= 1} = {ab, aab, aaab, ...}")
    else:
        from plts_to_nfa import build_nfa_from_file_with_stats
        my_nfa, stats = build_nfa_from_file_with_stats(args.file, deterministic=args.deterministic)
        print("=" * 60)
        print(f"NFA FROM {args.file}")
        print("=" * 60)
        print(f"Variables: {stats['num_variables']}")
        print(f"Complete threshold: c >= {stats['complete_threshold']}")
        print(f"Deterministic: {stats.get('deterministic', False)}")
        print(f"States: {stats['num_states']}")
        print(f"Final states: {stats['num_final_states']}")
        print(f"Transitions: {stats['num_transitions']}")
    
    result = automata_based_plan_computation(my_nfa, verbose=True)

    # Print summary table
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    stats = result['stats']
    print(f"{'Component':<30} {'States':>12} {'Transitions':>12} {'Finals':>10}")
    print("-" * 70)
    print(f"{'Input NFA':<30} {stats['nfa_states']:>12} {stats['nfa_transitions']:>12} {stats['nfa_finals']:>10}")
    print(f"{'DFA_P1':<30} {stats['dfa_p1_states']:>12} {stats['dfa_p1_transitions']:>12} {stats['dfa_p1_finals']:>10}")
    print(f"{'Product (NFA × DFA_P1)':<30} {stats['product_states']:>12} {stats['product_transitions']:>12} {stats['product_finals']:>10}")
    print(f"{'NFA_P2 (reachable)':<30} {stats['nfa_p2_reachable']:>12} {stats['nfa_p2_transitions']:>12} {stats['nfa_p2_finals']:>10}")
    print(f"{'NFA_P2 (unreachable)':<30} {stats['nfa_p2_unreachable']:>12} {'-':>12} {'-':>10}")

    # Show unreachable states if any
    if result['unreachable_states']:
        print(f"\nUnreachable states ({len(result['unreachable_states'])}):")
        for s in sorted(result['unreachable_states'], key=str)[:10]:
            print(f"  {s}")
        if len(result['unreachable_states']) > 10:
            print(f"  ... and {len(result['unreachable_states']) - 10} more")

    print("\n" + "=" * 70)
    print("VALID PLANS")
    print("=" * 70)
    if result['valid_plans']:
        plans = sorted(result['valid_plans'], key=lambda x: (len(x), x))
        print(f"L(NFA_P2): {len(plans)} words")
        for p in plans[:15]:
            print(f"  {p}")
        if len(plans) > 15:
            print(f"  ... and {len(plans) - 15} more")
    else:
        print("No valid plans found.")
