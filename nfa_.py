from automata.fa.nfa import NFA
from automata.fa.dfa import DFA

from plan_automata import (
    automata_based_plan_computation,
    nfa_p2_to_nfa_object,
    is_plan_valid,
    is_word_valid,
)


def nfa_to_dfa(nfa):
    """
    Converts an NFA to an equivalent DFA using the subset construction algorithm.
    
    Following the formal definition:
    - Ŝ = 2^S (reachable subset of power set)
    - ŝ_init = {s_init}
    - δ'(ŝ, a) = ∪_{s∈ŝ} δ(s, a) for all ŝ ∈ Ŝ and a ∈ Σ
    - F̂ = {ŝ ∈ Ŝ | ŝ ∩ F ≠ ∅}
    
    Args:
        nfa: An NFA object with states, input_symbols, transitions, initial_state, final_states
        
    Returns:
        A DFA object that accepts the same language as the input NFA
    """
    # Helper function to get NFA transitions for a state and symbol
    def get_nfa_transitions(state, symbol):
        """Returns the set of states reachable from 'state' on 'symbol'."""
        if state in nfa.transitions and symbol in nfa.transitions[state]:
            return nfa.transitions[state][symbol]
        return set()
    
    # Helper function to compute δ'(ŝ, a) = ∪_{s∈ŝ} δ(s, a)
    def dfa_transition(dfa_state, symbol):
        """Computes the union of all NFA transitions for states in dfa_state on symbol."""
        result = set()
        for nfa_state in dfa_state:
            result = result.union(get_nfa_transitions(nfa_state, symbol))
        return frozenset(result)
    
    # Initialize DFA components
    # ŝ_init = {s_init}
    initial_dfa_state = frozenset({nfa.initial_state})
    
    # Worklist algorithm to compute reachable DFA states
    dfa_states = set()
    dfa_transitions = {}
    worklist = [initial_dfa_state]
    
    while worklist:
        current_dfa_state = worklist.pop(0)
        
        if current_dfa_state in dfa_states:
            continue
        
        dfa_states.add(current_dfa_state)
        dfa_transitions[current_dfa_state] = {}
        
        # Compute transitions for each input symbol
        for symbol in nfa.input_symbols:
            next_dfa_state = dfa_transition(current_dfa_state, symbol)
            
            # Only add non-empty transitions
            if next_dfa_state:
                dfa_transitions[current_dfa_state][symbol] = next_dfa_state
                
                if next_dfa_state not in dfa_states:
                    worklist.append(next_dfa_state)
    
    # A DFA state is final only if ALL NFA states it contains are final states
    dfa_final_states = set()
    for dfa_state in dfa_states:
        if dfa_state and dfa_state.issubset(nfa.final_states):
            dfa_final_states.add(dfa_state)
    
    # Convert frozensets to strings for DFA state names (for readability)
    def state_name(fs):
        if not fs:
            return "{}"
        return "{" + ",".join(sorted(fs)) + "}"
    
    # Build the DFA with string state names
    dfa_states_str = {state_name(s) for s in dfa_states}
    dfa_initial_str = state_name(initial_dfa_state)
    dfa_final_str = {state_name(s) for s in dfa_final_states}
    
    dfa_transitions_str = {}
    for dfa_state, trans in dfa_transitions.items():
        state_str = state_name(dfa_state)
        dfa_transitions_str[state_str] = {}
        for symbol, next_state in trans.items():
            dfa_transitions_str[state_str][symbol] = state_name(next_state)
    
    # Create and return the DFA (allow_partial=True for incomplete transitions)
    return DFA(
        states=dfa_states_str,
        input_symbols=nfa.input_symbols,
        transitions=dfa_transitions_str,
        initial_state=dfa_initial_str,
        final_states=dfa_final_str,
        allow_partial=True,
    )


import random


# ============================================================================
# NFA Helper Functions
# ============================================================================

def delta(nfa, state, action):
    """
    Returns δ(s, a) - the set of successor states from 'state' on 'action'.
    """
    if state in nfa.transitions and action in nfa.transitions[state]:
        return nfa.transitions[state][action]
    return set()


def delta_star(nfa, state, word):
    """
    Returns δ*(s, w) - the set of states reachable from 'state' after reading 'word'.
    """
    current_states = {state}
    for symbol in word:
        next_states = set()
        for s in current_states:
            next_states = next_states.union(delta(nfa, s, symbol))
        current_states = next_states
    return current_states


def delta_star_from_set(nfa, states, word):
    """
    Returns δ*(S, w) - the set of states reachable from any state in 'states' after reading 'word'.
    """
    result = set()
    for s in states:
        result = result.union(delta_star(nfa, s, word))
    return result


# ============================================================================
# Plan Helper Functions
# ============================================================================

def first(word):
    """
    Returns first(w) - the first symbol of word, or ε (empty string) if word is empty.
    """
    if word:
        return word[0]
    return ""  # ε (epsilon)


def prefixes(plan):
    """
    Returns prefixes(π) - the set of all prefixes of words in the plan.
    Includes the empty prefix and the words themselves.
    """
    prefix_set = set()
    for word in plan:
        for i in range(len(word) + 1):
            prefix_set.add(word[:i])
    return prefix_set


# ============================================================================
# Plan Validation (Definition: Plan) - Direct Approach
# ============================================================================

def check_p1(nfa, plan):
    """
    Checks condition P1: For all w ∈ π, δ*(s_init, w) ⊆ F
    All states reachable after reading any word in the plan must be final states.
    """
    for word in plan:
        reachable_states = delta_star(nfa, nfa.initial_state, word)
        if not reachable_states.issubset(nfa.final_states):
            print(f"P1 violated: word '{word}' reaches states {reachable_states}, "
                  f"but not all are in F={nfa.final_states}")
            return False
    return True


def check_p2(nfa, plan):
    """
    Checks condition P2: For every w in prefixes(plan) minus plan and each s in delta*(s_init, w),
    there is an action a in Sigma with wa in prefixes(plan) and delta(s, a) != empty.
    
    For every proper prefix and every state reachable by that prefix,
    there must be an action that extends the prefix AND has a transition.
    """
    all_prefixes = prefixes(plan)
    proper_prefixes = all_prefixes - plan  # prefixes(π) \ π
    
    for w in proper_prefixes:
        reachable_states = delta_star(nfa, nfa.initial_state, w)
        
        for s in reachable_states:
            found_action = False
            for a in nfa.input_symbols:
                wa = w + a
                if wa in all_prefixes and delta(nfa, s, a):
                    found_action = True
                    break
            
            if not found_action:
                print(f"P2 violated: prefix '{w}', state '{s}' has no valid action")
                return False
    
    return True


def is_valid_plan(nfa, plan):
    """
    Validates that the plan satisfies both P1 and P2.
    """
    print("Checking P1...")
    p1_ok = check_p1(nfa, plan)
    print(f"P1: {'PASSED' if p1_ok else 'FAILED'}")
    
    print("Checking P2...")
    p2_ok = check_p2(nfa, plan)
    print(f"P2: {'PASSED' if p2_ok else 'FAILED'}")
    
    return p1_ok and p2_ok


# ============================================================================
# Algorithm: Execute Plan on NFA
# ============================================================================

def execute_plan(nfa, plan):
    """
    Algorithm for using a plan to reach an accepting state in an NFA.
    
    Args:
        nfa: The NFA (S, s_init, Σ, δ, F)
        plan: A valid plan π₀ ⊆ Σ* for the NFA
        
    Returns:
        A tuple (final_state, executed_word) representing the run
    """
    s = nfa.initial_state  # s := s_init
    current_plan = set(plan)  # π := π₀
    executed_word = ""
    
    print(f"\n--- Executing Plan ---")
    print(f"Initial state: {s}")
    print(f"Initial plan: {current_plan}")
    
    while True:
        # Σ' := {first(w) | w ∈ π} - actions allowed by plan
        sigma_prime = {first(w) for w in current_plan}
        print(f"\nΣ' (actions allowed by plan): {sigma_prime}")
        
        # Σ'' := {a ∈ Σ' | a = ε ∨ ∃s' ∈ S: (s, a, s') ∈ δ}
        # Actions that are both allowed by plan AND available at current state
        sigma_double_prime = set()
        for a in sigma_prime:
            if a == "":  # a = ε
                sigma_double_prime.add(a)
            elif delta(nfa, s, a):  # ∃s' ∈ S: (s, a, s') ∈ δ
                sigma_double_prime.add(a)
        
        print(f"Σ'' (available at state {s}): {sigma_double_prime}")
        
        if not sigma_double_prime:
            print("ERROR: Σ'' is empty - no valid actions!")
            break
        
        # a :∈ Σ'' - system chooses arbitrary action from Σ''
        a = random.choice(list(sigma_double_prime))
        print(f"Chosen action: '{a}' (ε means empty)")
        
        if a == "":  # a = ε - termination condition
            print(f"\nTerminated with ε")
            break
        
        # s :∈ {s' ∈ S | (s, a, s') ∈ δ} - system chooses successor state
        successor_states = delta(nfa, s, a)
        s = random.choice(list(successor_states))
        print(f"New state: {s}")
        
        executed_word += a
        
        # π := {w ∈ Σ* | aw ∈ π} - restrict plan according to executed action
        current_plan = {w[1:] for w in current_plan if w and w[0] == a}
        print(f"Updated plan: {current_plan}")
    
    print(f"\n--- Execution Complete ---")
    print(f"Final state: {s}")
    print(f"Executed word: '{executed_word}'")
    print(f"Is final state: {s in nfa.final_states}")
    
    return s, executed_word


def read_user_input(my_automaton):
    try:
        while True:
            if my_automaton.accepts_input(input("Please enter your input: ")):
                print("Accepted")
            else:
                print("Rejected")
    except KeyboardInterrupt:
        print("")
# ============================================================================
# Example NFA from Figure (matching the paper's example)
# ============================================================================
# NFA with L(NFA) = {a, aa, b, ba}
# - "a" violates P1: s2 ∈ δ*(s0, a) but s2 is not accepting
# - "aa" violates P2: for prefix "a", s1 ∈ δ*(s0, a) but δ(s1, a) = ∅
# - Valid plans: {b}, {ba}, {b, ba}

my_nfa = NFA(
    states={"s0", "s1", "s2", "s3"},
    input_symbols={"a", "b"},
    transitions={
        "s0": {"a": {"s1", "s2"}, "b": {"s2"}},
        "s1": {},  # no outgoing transitions (this causes P2 violations)
        "s2": {"a": {"s3"}},
        "s3": {},  # final state, no outgoing transitions
    },
    initial_state="s0",
    final_states={"s2", "s3"},  # s2 and s3 are final (double-framed in figure)
)

print("="*60)
print("NFA (from Figure)")
print("="*60)
print(f"States: {my_nfa.states}")
print(f"Initial: {my_nfa.initial_state}")
print(f"Final: {my_nfa.final_states}")
print(f"L(NFA) = {{a, aa, b, ba}}")
my_nfa.show_diagram(path='nfa_diagram.png')

# ============================================================================
# Standard DFA (for comparison)
# ============================================================================
print("\n" + "="*60)
print("Standard DFA (determinization)")
print("="*60)
my_dfa = nfa_to_dfa(my_nfa)
print(f"States: {my_dfa.states}")
print(f"Initial: {my_dfa.initial_state}")
print(f"Final (P1 condition - all states must be final): {my_dfa.final_states}")
my_dfa.show_diagram(path='dfa_diagram.png')

# ============================================================================
# Automata-Based Plan Computation
# ============================================================================
result = automata_based_plan_computation(my_nfa, verbose=True)

# Visualize NFA_P2
nfa_p2_obj = nfa_p2_to_nfa_object(result['nfa_p2'], my_nfa)
if nfa_p2_obj:
    nfa_p2_obj.show_diagram(path='nfa_p2_diagram.png')
    print("\nNFA_P2 diagram saved to 'nfa_p2_diagram.png'")

# ============================================================================
# Compare with Direct Plan Validation
# ============================================================================
print("\n" + "="*60)
print("VERIFICATION: Direct Plan Validation")
print("="*60)

test_plans = [
    {"a"},      # Should fail P1
    {"aa"},     # Should fail P2
    {"b"},      # Should pass
    {"ba"},     # Should pass
    {"b", "ba"} # Should pass
]

for plan in test_plans:
    print(f"\nPlan: {plan}")
    valid = is_valid_plan(my_nfa, plan)
    in_nfa_p2 = plan.issubset(result['valid_plans'])
    print(f"Direct validation: {valid}")
    print(f"In L(NFA_P2): {in_nfa_p2}")
    assert valid == in_nfa_p2, "Mismatch between direct and automata-based!"

print("\n" + "="*60)
print("All validations match! Automata-based approach is correct.")
print("="*60)