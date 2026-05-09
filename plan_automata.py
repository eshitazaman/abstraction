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

    **Stricter P2:** P1-only co-reachability is necessary but not sufficient for a
    valid plan. Words that die under P2 form a (typically) **larger** set of bad
    prefixes than P1-dead alone. That stricter cut is applied later on the
    **product** NFA × DFA_P1 in ``compute_nfa_p2``, where universal /
    branching constraints live—not on DFA_P1 in isolation.

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
    }


def nfa_to_dfa_p1(nfa, verbose=False):
    """
    P1-Determinization: Builds DFA_P1 where a state is final only if ALL 
    NFA states it contains are final (satisfying P1 condition).
    
    Returns internal data structures for product construction.
    """
    def get_nfa_transitions(state, symbol):
        if state in nfa.transitions and symbol in nfa.transitions[state]:
            return nfa.transitions[state][symbol]
        return set()
    
    def dfa_transition(dfa_state, symbol):
        result = set()
        for nfa_state in dfa_state:
            result = result.union(get_nfa_transitions(nfa_state, symbol))
        return frozenset(result)
    
    initial_dfa_state = frozenset({nfa.initial_state})
    dfa_states = set()
    dfa_transitions = {}
    worklist = deque([initial_dfa_state])
    
    while worklist:
        current = worklist.popleft()
        if current in dfa_states:
            continue
        dfa_states.add(current)
        if verbose and len(dfa_states) % 10000 == 0:
            print(
                f"   ... DFA_P1 determinization in progress: {len(dfa_states)} states discovered "
                f"(queued {len(worklist)})"
            )
        dfa_transitions[current] = {}
        
        for symbol in nfa.input_symbols:
            next_state = dfa_transition(current, symbol)
            if next_state:
                dfa_transitions[current][symbol] = next_state
                if next_state not in dfa_states:
                    worklist.append(next_state)
    
    # P1 condition: final only if ALL states are final
    dfa_final_states = {s for s in dfa_states if s and s.issubset(nfa.final_states)}

    dfa_p1 = {
        "states": dfa_states,
        "initial": initial_dfa_state,
        "finals": dfa_final_states,
        "transitions": dfa_transitions,
        "input_symbols": nfa.input_symbols,
    }
    return prune_dfa_p1_co_reachable(dfa_p1)


def build_product_nfa_dfa_p1(nfa, dfa_p1, verbose=False):
    """
    Builds the product automaton NFA x DFA_P1.
    
    States are pairs (s, ŝ) where s ∈ NFA states, ŝ ∈ DFA_P1 states.
    Transitions: ((s, ŝ), a, (s', ŝ')) exists iff (s, a, s') ∈ δ_NFA and (ŝ, a, ŝ') ∈ δ_DFA
    Final states: (s, ŝ) is final iff s ∈ F_NFA AND ŝ ∈ F_DFA_P1
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


def automata_based_plan_computation(
    nfa, verbose=True, enumerate_plans=True
):
    """
    Computes all valid plans using the automata-based approach:
    1. Build DFA_P1 (P1-determinization)
    2. Build NFA x DFA_P1 (product automaton)
    3. Compute NFA_P2 (maximal P2-restriction; Lemma 9 / Algorithm 2)
    4. L(NFA_P2) = all valid plans (optional: skip enumeration)

    Args:
        nfa: The input NFA
        verbose: If True, print progress information
        enumerate_plans: If False, skip DFS enumeration of all words; use
            ``language_nonempty`` for existence.

    Returns:
        Dictionary containing:
        - 'dfa_p1': The P1-determinization
        - 'product': The product automaton NFA × DFA_P1
        - 'nfa_p2': The maximal P2-restriction
        - 'valid_plans': Set of valid plan words, or None if enumerate_plans is False
        - 'language_nonempty': True iff some P1∧P2 valid plan exists (any length)
        - 'shortest_plan_length': Min number of moves in any accepting word, or None if empty
    """
    if verbose:
        print("\n" + "="*60)
        print("AUTOMATA-BASED PLAN COMPUTATION [NFA_P2: Lemma 9 / Algorithm 2]")
        print("="*60)
    
    # Step 1: Build DFA_P1
    if verbose:
        print("\n1. Building DFA_P1 (P1-determinization)...")
    dfa_p1 = nfa_to_dfa_p1(nfa, verbose=verbose)
    if verbose:
        print(f"   States: {len(dfa_p1['states'])}")
        print(f"   Final states: {dfa_p1['finals']}")
    
    # Step 2: Build product NFA × DFA_P1
    if verbose:
        print("\n2. Building NFA x DFA_P1 (product automaton)...")
    product = build_product_nfa_dfa_p1(nfa, dfa_p1, verbose=verbose)
    # Count actual transitions (state, action, successor) triples
    product_trans = sum(len(succs) for trans in product['transitions'].values() for succs in trans.values())
    if verbose:
        print(f"   States: {len(product['states'])}")
        print(f"   Final states: {product['finals']}")
        print(f"   Transitions: {product_trans}")
    
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
    }

    return {
        'dfa_p1': dfa_p1,
        'product': product,
        'nfa_p2': nfa_p2,
        'valid_plans': valid_plans,
        'language_nonempty': language_nonempty,
        'shortest_plan_length': shortest_plan_length,
        'stats': stats,
        'unreachable_states': unreachable_states
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