"""
PLTS to NFA Converter

Converts Probabilistic Labeled Transition Systems (PLTS) specifications
from .kr files to Non-deterministic Finite Automata (NFA).

Optimizations applied:
1. Avoid duplicate successors when variable already set (v_i=1)
2. Use tuple operations directly (avoid list conversions)
3. Pre-compile regex patterns at module level
4. Use frozenset for enabled states (faster membership testing)
5. Direct dict construction (avoid defaultdict overhead)
6. Inline clamp logic
"""

import re
from collections import deque
from dataclasses import dataclass, field
from typing import Dict, FrozenSet, Set, Tuple, Optional

from automata.fa.nfa import NFA


# Type alias for state representation
State = Tuple[int, int, Tuple[int, ...]]  # (s, c, (v1..vn))


@dataclass(frozen=True)
class ActionSpec:
    """
    ActionSpec captures one PLTS command family of the form:

      [label] (s in from_s) -> (s'=to_s) & (v[idx]'=1) &
            (c' = min(Cmax, c + (1 - v[idx])))   OR   (c' = c)

    Where idx is 1-based (v1 is idx=1).
    """
    label: str
    from_s: FrozenSet[int]  # Use frozenset for faster lookup
    to_s: int
    v_idx: int  # 1-based index


# Pre-compiled regex patterns (module level for reuse)
_V_INDEX_RE = re.compile(r"\bv(\d+)\b")
_C_RANGE_RE = re.compile(r"\bc\s*:\s*\[0\.\.(\d+)\]\s*;")
_COMPLETE_RE = re.compile(r"formula\s+complete\s*=\s*\(c\s*>=\s*(\d+)\)\s*;")
_COMMAND_RE = re.compile(
    r"\[(?P<label>[^\]]+)\]\s*\(s\s*=\s*(?P<from>\d+)\)\s*->\s*"
    r".*?\(s'\s*=\s*(?P<to>\d+)\).*?"
    r"\(c'\s*=\s*min\(\s*(?P<cmax>\d+)\s*,\s*c\s*\+\s*\(1\s*-\s*v(?P<vidx>\d+)\)\s*\)\s*\)"
    r".*?\(v(?P=vidx)'\s*=\s*1\)",
    re.DOTALL
)


def compute_successors(
    st: State,
    spec: ActionSpec,
    c_max: int,
    n: int,
    deterministic: bool = False
) -> Optional[Tuple[State, ...]]:
    """
    Compute successor states for a given state and action.
    
    Args:
        st: Current state
        spec: Action specification
        c_max: Maximum value for c
        n: Number of variables
        deterministic: If True, only create the c-incrementing branch (no non-determinism)
    
    Optimizations:
    - Return None if action not enabled (faster than empty set)
    - Return single state when v_i already set (both branches identical)
    - Use tuple slicing instead of list conversion
    """
    s, c, v = st
    
    # Check if action is enabled
    if s not in spec.from_s:
        return None
    
    i = spec.v_idx - 1  # Convert to 0-based index
    
    v_current = v[i]
    
    # Build new v tuple with v[i] = 1
    v_new = v[:i] + (1,) + v[i+1:]
    
    if v_current == 1:
        # Variable already set - c doesn't change
        return ((spec.to_s, c, v_new),)
    else:
        # Variable was 0 - c increments
        c_incremented = c + 1 if c < c_max else c_max
        
        if deterministic:
            # Deterministic mode: only the incrementing branch
            return ((spec.to_s, c_incremented, v_new),)
        else:
            # Non-deterministic mode: both branches (models probabilistic choice)
            return (
                (spec.to_s, c_incremented, v_new),
                (spec.to_s, c, v_new),
            )


def parse_plts_actions(plts_text: str) -> Tuple[int, int, int, Dict[str, ActionSpec]]:
    """
    Parse a PLTS text and extract:
      - n: number of v variables (v1..vn)
      - c_max: max value of c from "c : [0..Cmax];"
      - complete_threshold: value from "formula complete = (c>=X);"
      - action specs keyed by label (one/two/three/...)

    This parser is tailored to your PLTS style where each label corresponds to some v_k
    and each command uses min(Cmax, c+(1-vk)) and sets vk'=1.
    """
    # Infer n from "v1", "v2", ..., "vn"
    v_indices = {int(m.group(1)) for m in _V_INDEX_RE.finditer(plts_text)}
    if not v_indices:
        raise ValueError("No v1..vn variables found in the PLTS text.")
    n = max(v_indices)

    # Parse c range
    m_c = _C_RANGE_RE.search(plts_text)
    if not m_c:
        raise ValueError("Could not find c range like: c : [0..4];")
    c_max = int(m_c.group(1))

    # Parse complete threshold from "formula complete = (c>=X);"
    m_complete = _COMPLETE_RE.search(plts_text)
    if not m_complete:
        raise ValueError("Could not find complete formula like: formula complete = (c>=2);")
    complete_threshold = int(m_complete.group(1))

    # Parse commands and build action specs
    tmp: Dict[str, Dict] = {}
    
    for m in _COMMAND_RE.finditer(plts_text):
        label = m.group("label").strip()
        from_s = int(m.group("from"))
        to_s = int(m.group("to"))
        vidx = int(m.group("vidx"))
        cmax_in_cmd = int(m.group("cmax"))
        
        # Sanity check
        if cmax_in_cmd != c_max:
            raise ValueError(f"Command uses min({cmax_in_cmd}, ...) but c_max parsed is {c_max}.")

        if label not in tmp:
            tmp[label] = {"from_s": set(), "to_s": to_s, "v_idx": vidx}
        
        tmp[label]["from_s"].add(from_s)
        
        # Ensure consistent mapping for label
        if tmp[label]["to_s"] != to_s or tmp[label]["v_idx"] != vidx:
            raise ValueError(
                f"Label [{label}] maps inconsistently across commands. "
                f"Existing to_s={tmp[label]['to_s']}, v_idx={tmp[label]['v_idx']}; "
                f"New to_s={to_s}, v_idx={vidx}."
            )

    if not tmp:
        raise ValueError("No matching commands found. This parser expects the same pattern as your PLTS.")

    # Convert to ActionSpec with frozenset for from_s
    actions: Dict[str, ActionSpec] = {
        label: ActionSpec(
            label=label,
            from_s=frozenset(vals["from_s"]),
            to_s=vals["to_s"],
            v_idx=vals["v_idx"]
        )
        for label, vals in tmp.items()
    }
    
    return n, c_max, complete_threshold, actions


def build_nfa_from_plts_text(
    plts_text: str,
    reachable_only: bool = True,
    deterministic: bool = False
) -> NFA:
    """
    Builds an NFA from PLTS text.
      - Initial state = launch: s=0, c=0, all v_i=0
      - Accepting states = c >= complete_threshold (parsed from "formula complete = (c>=X);")
      - Input symbols = action labels [one],[two],...

    Args:
        plts_text: The PLTS model text
        reachable_only: Only build reachable states (recommended)
        deterministic: If True, actions always increment c when visiting new variable
                      (no non-determinism from probabilistic branches)
    """
    n, c_max, complete_threshold, actions = parse_plts_actions(plts_text)
    alphabet = set(actions.keys())

    # Initial state: s=0, c=0, all v_i=0
    start: State = (0, 0, (0,) * n)

    if not reachable_only:
        raise NotImplementedError("Use reachable_only=True to avoid state explosion.")

    # BFS exploration
    queue = deque([start])
    seen: Set[State] = {start}
    transitions: Dict[State, Dict[str, Set[State]]] = {}

    while queue:
        st = queue.popleft()
        st_trans: Dict[str, Set[State]] = {}
        
        for label, spec in actions.items():
            successors = compute_successors(st, spec, c_max, n, deterministic)
            
            if successors:
                succ_set = set(successors)
                st_trans[label] = succ_set
                
                for ns in successors:
                    if ns not in seen:
                        seen.add(ns)
                        queue.append(ns)
        
        if st_trans:
            transitions[st] = st_trans

    # Compute final states: c >= complete_threshold (parsed from file)
    finals = {st for st in seen if st[1] >= complete_threshold}

    return NFA(
        states=seen,
        input_symbols=alphabet,
        transitions=transitions,
        initial_state=start,
        final_states=finals
    )


def build_nfa_with_stats(plts_text: str, deterministic: bool = False) -> Tuple[NFA, Dict]:
    """Build NFA and return statistics about the construction."""
    import time
    
    # Parse to get complete_threshold for stats
    n, c_max, complete_threshold, _ = parse_plts_actions(plts_text)
    
    start_time = time.perf_counter()
    nfa = build_nfa_from_plts_text(plts_text, deterministic=deterministic)
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
        'num_actions': len(nfa.input_symbols),
        'num_variables': n,
        'c_max': c_max,
        'complete_threshold': complete_threshold,
        'deterministic': deterministic,
        'build_time_ms': build_time * 1000,
    }
    
    return nfa, stats


def read_plts_from_file(filepath: str) -> str:
    """
    Read PLTS model from a .kr file.
    
    Args:
        filepath: Path to the .kr file containing the PLTS model
        
    Returns:
        The PLTS text content as a string
        
    Raises:
        FileNotFoundError: If the file doesn't exist
        IOError: If there's an error reading the file
    """
    with open(filepath, 'r', encoding='utf-8') as f:
        return f.read()


def build_nfa_from_file(filepath: str, deterministic: bool = False) -> NFA:
    """
    Build NFA from a .kr file containing a PLTS model.
    
    The complete threshold is parsed from the "formula complete = (c>=X);" in the file.
    
    Args:
        filepath: Path to the .kr file
        deterministic: If True, actions always increment c (no non-determinism)
        
    Returns:
        The constructed NFA
    """
    plts_text = read_plts_from_file(filepath)
    return build_nfa_from_plts_text(plts_text, deterministic=deterministic)


def build_nfa_from_file_with_stats(filepath: str, deterministic: bool = False) -> Tuple[NFA, Dict]:
    """
    Build NFA from a .kr file and return statistics.
    
    The complete threshold is parsed from the "formula complete = (c>=X);" in the file.
    
    Args:
        filepath: Path to the .kr file
        deterministic: If True, actions always increment c (no non-determinism)
        
    Returns:
        Tuple of (NFA, statistics dict)
    """
    plts_text = read_plts_from_file(filepath)
    return build_nfa_with_stats(plts_text, deterministic=deterministic)


# Default PLTS text for testing when no file is provided
DEFAULT_PLTS_TEXT = r"""
plts:
    formula launch   = (s=0)
                     & (c=0)
                     & (v1=0)
                     & (v2=0)
                     & (v3=0)
                     & (v4=0);

    formula complete = (c>=2);

    module plts
        s  : [0..4];
        c  : [0..4];
        v1 : [0..1];
        v2 : [0..1];
        v3 : [0..1];
        v4 : [0..1];

        [one] (s=0) -> 0.83:(s'=1)&(c'=min(4,c+(1-v1)))&(v1'=1) + 0.17:(s'=1)&(c'=c)&(v1'=1);
        [two] (s=0) -> 0.29:(s'=2)&(c'=min(4,c+(1-v2)))&(v2'=1) + 0.71:(s'=2)&(c'=c)&(v2'=1);
        [two] (s=1) -> 0.29:(s'=2)&(c'=min(4,c+(1-v2)))&(v2'=1) + 0.71:(s'=2)&(c'=c)&(v2'=1);
        [three] (s=1) -> 0.31:(s'=3)&(c'=min(4,c+(1-v3)))&(v3'=1) + 0.69:(s'=3)&(c'=c)&(v3'=1);
        [one] (s=2) -> 0.83:(s'=1)&(c'=min(4,c+(1-v1)))&(v1'=1) + 0.17:(s'=1)&(c'=c)&(v1'=1);
        [four] (s=2) -> 0.17:(s'=4)&(c'=min(4,c+(1-v4)))&(v4'=1) + 0.83:(s'=4)&(c'=c)&(v4'=1);
        [one] (s=3) -> 0.83:(s'=1)&(c'=min(4,c+(1-v1)))&(v1'=1) + 0.17:(s'=1)&(c'=c)&(v1'=1);
        [four] (s=3) -> 0.17:(s'=4)&(c'=min(4,c+(1-v4)))&(v4'=1) + 0.83:(s'=4)&(c'=c)&(v4'=1);
        [two] (s=4) -> 0.29:(s'=2)&(c'=min(4,c+(1-v2)))&(v2'=1) + 0.71:(s'=2)&(c'=c)&(v2'=1);
        [three] (s=4) -> 0.31:(s'=3)&(c'=min(4,c+(1-v3)))&(v3'=1) + 0.69:(s'=3)&(c'=c)&(v3'=1);
    endmodule
endplts
"""


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Convert PLTS model (.kr file) to NFA')
    parser.add_argument('file', nargs='?', help='Path to .kr file (uses default if not provided)')
    parser.add_argument('-o', '--output', help='Output path for NFA diagram (optional)')
    parser.add_argument('-d', '--deterministic', action='store_true',
                        help='Deterministic mode: c always increments when visiting new variable')
    args = parser.parse_args()
    
    # Read PLTS from file or use default
    if args.file:
        print(f"Reading PLTS from: {args.file}")
        plts_text = read_plts_from_file(args.file)
    else:
        print("Using default PLTS model")
        plts_text = DEFAULT_PLTS_TEXT
    
    # Build NFA with statistics
    nfa, stats = build_nfa_with_stats(plts_text, deterministic=args.deterministic)
    
    print("\n" + "="*50)
    print("PLTS TO NFA CONVERSION")
    print("="*50)
    print(f"Variables (n): {stats['num_variables']}")
    print(f"c_max: {stats['c_max']}")
    print(f"Complete threshold: c >= {stats['complete_threshold']}")
    print(f"Deterministic mode: {stats.get('deterministic', False)}")
    print(f"Alphabet: {nfa.input_symbols}")
    print(f"Reachable states: {stats['num_states']}")
    print(f"Accepting states: {stats['num_final_states']}")
    print(f"Total transitions: {stats['num_transitions']}")
    print(f"Build time: {stats['build_time_ms']:.2f} ms")
    
    # Test acceptance
    print("\n" + "="*50)
    print("ACCEPTANCE TESTS")
    print("="*50)
    
    test_words = [
        ["one", "three"],
        ["one", "three", "four", "two"],
        ["two", "four", "three", "one"],
        ["one", "two"],
        ["two", "one", "three", "four"],
        ["one","three","five","seven","nine","eleven","twelve","ten","eight"],
    ]
    
    for w in test_words:
        result = nfa.accepts_input(w)
        print(f"  {' -> '.join(w)}: {'accepted' if result else 'rejected'}")
    
    # Generate diagram if output path provided
    if args.output:
        print(f"\nGenerating diagram: {args.output}")
        nfa.show_diagram(path=args.output)
        print("Done.")