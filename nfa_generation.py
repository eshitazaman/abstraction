"""
NFA Generation from PLTS (Probabilistic Labeled Transition Systems)

Optimizations applied:
1. Pre-computed enabled actions per s-value (avoids repeated set membership checks)
2. Avoid duplicate successors when variable is already set (v=1 means both branches identical)
3. Inline clamp logic (avoid function call overhead)
4. Use frozenset for ALPHABET (immutable, slightly faster iteration)
5. Direct dictionary construction (avoid defaultdict overhead in hot path)
6. Early termination when no successors possible
"""

from collections import deque
from automata.fa.nfa import NFA

# State representation: (s, c, v1, v2, v3, v4)
# Domains: s in [0..4], c in [0..4], v1..v4 in {0,1}

ALPHABET = frozenset({"one", "two", "three", "four"})

# Pre-computed: which s-values enable each action
ENABLED_S = {
    "one": frozenset({0, 2, 3}),
    "two": frozenset({0, 1, 4}),
    "three": frozenset({1, 4}),
    "four": frozenset({2, 3}),
}

# Pre-computed: which variable index each action modifies (0-indexed: v1=0, v2=1, v3=2, v4=3)
# and the target s-value
ACTION_CONFIG = {
    "one": (1, 0),    # s'=1, modifies v1 (index 0)
    "two": (2, 1),    # s'=2, modifies v2 (index 1)
    "three": (3, 2),  # s'=3, modifies v3 (index 2)
    "four": (4, 3),   # s'=4, modifies v4 (index 3)
}


def compute_successors(st, action):
    """
    Compute successor states for a given state and action.
    
    Optimizations:
    - Early return if action not enabled
    - Avoid duplicate states when variable already set
    - Inline min() for c clamping
    """
    s, c, v1, v2, v3, v4 = st
    
    # Check if action is enabled for current s
    if s not in ENABLED_S[action]:
        return None  # Return None instead of empty set (faster check)
    
    s_new, var_idx = ACTION_CONFIG[action]
    v_list = [v1, v2, v3, v4]
    v_current = v_list[var_idx]
    
    # Set the variable to 1
    v_list[var_idx] = 1
    
    if v_current == 1:
        # Variable already set - both branches produce same state
        return ((s_new, c, *v_list),)  # Return tuple (faster than set for small collections)
    else:
        # Variable was 0 - branches differ in c value
        c_incremented = c + 1 if c < 4 else 4  # Inline clamp
        return (
            (s_new, c_incremented, *v_list),
            (s_new, c, *v_list),
        )


def is_complete(st) -> bool:
    """Check if state satisfies complete formula (c >= 2)."""
    return st[1] >= 2


def build_nfa_reachable_only():
    """
    Build NFA by exploring only reachable states from initial state.
    Uses BFS with optimized transition computation.
    """
    start = (0, 0, 0, 0, 0, 0)  # launch formula
    
    # Use deque for BFS (O(1) popleft)
    queue = deque([start])
    seen = {start}
    
    # Build transitions directly as dict (avoid defaultdict overhead)
    transitions = {}
    
    while queue:
        st = queue.popleft()
        st_trans = {}
        
        for action in ALPHABET:
            successors = compute_successors(st, action)
            
            if successors:
                # Convert to set and add to transitions
                succ_set = set(successors)
                st_trans[action] = succ_set
                
                # Add unseen successors to queue
                for ns in successors:
                    if ns not in seen:
                        seen.add(ns)
                        queue.append(ns)
        
        if st_trans:  # Only add if state has outgoing transitions
            transitions[st] = st_trans
    
    # Compute final states (c >= 2)
    final_states = {st for st in seen if is_complete(st)}
    
    return NFA(
        states=seen,
        input_symbols=set(ALPHABET),  # Convert back to set for NFA
        transitions=transitions,
        initial_state=start,
        final_states=final_states,
    )


def build_nfa_with_stats():
    """Build NFA and return statistics about the construction."""
    import time
    
    start_time = time.perf_counter()
    nfa = build_nfa_reachable_only()
    build_time = time.perf_counter() - start_time
    
    # Compute statistics
    total_transitions = sum(
        sum(len(succs) for succs in sym_map.values())
        for sym_map in nfa.transitions.values()
    )
    
    stats = {
        'num_states': len(nfa.states),
        'num_final_states': len(nfa.final_states),
        'num_transitions': total_transitions,
        'build_time_ms': build_time * 1000,
    }
    
    return nfa, stats


if __name__ == "__main__":
    # Build NFA with timing
    nfa, stats = build_nfa_with_stats()
    
    print("="*50)
    print("NFA GENERATION STATISTICS")
    print("="*50)
    print(f"Reachable states: {stats['num_states']}")
    print(f"Accepting states: {stats['num_final_states']}")
    print(f"Total transitions: {stats['num_transitions']}")
    print(f"Build time: {stats['build_time_ms']:.2f} ms")
    
    # Test acceptance
    print("\n" + "="*50)
    print("ACCEPTANCE TESTS")
    print("="*50)
    
    test_words = [
        ["one", "three", "four", "two"],
        ["two", "four", "three", "one"],
        ["one", "two"],
        ["two", "one", "three", "four"],
    ]
    
    for w in test_words:
        result = nfa.accepts_input(w)
        print(f"  {' -> '.join(w)}: {'accepted' if result else 'rejected'}")
    
    # Generate diagram (optional - can be slow for large NFAs)
    print("\nGenerating diagram...")
    nfa.show_diagram(path='nfa_generated_diagram.png')
    print("Diagram saved to 'nfa_generated_diagram.png'")