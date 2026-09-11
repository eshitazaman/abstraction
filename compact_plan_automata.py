"""Exact bitmask backend for the P1/P2 planning pipeline.

P1 beliefs are integer masks over indexed NFA states.  A reachable product
pair always satisfies ``state in belief``, so product and P2 state sets are
stored as one concrete-state mask per belief instead of Python ``(state,
belief)`` tuples.  This preserves the explicit algorithm's semantics while
avoiding its dominant object-allocation cost.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
import sys
from typing import Hashable, Iterator, Sequence


MISSING = -1


def iter_bits(mask: int) -> Iterator[int]:
    """Yield indexes of set bits, from least to most significant."""

    while mask:
        bit = mask & -mask
        yield bit.bit_length() - 1
        mask ^= bit


def _stable_key(value) -> tuple[str, str]:
    return type(value).__name__, repr(value)


@dataclass(frozen=True, slots=True)
class IndexedNFA:
    states: tuple[Hashable, ...]
    state_ids: dict[Hashable, int]
    actions: tuple[Hashable, ...]
    action_ids: dict[Hashable, int]
    successors: tuple[tuple[int, ...], ...]
    predecessors: tuple[tuple[int, ...], ...]
    enabled_sources: tuple[int, ...]
    initial: int
    finals: int

    @property
    def full_mask(self) -> int:
        return (1 << len(self.states)) - 1

    @property
    def transition_count(self) -> int:
        return sum(mask.bit_count() for row in self.successors for mask in row)

    @property
    def storage_bytes(self) -> int:
        """Approximate bytes owned by forward/reverse transition tables."""

        tables = (self.successors, self.predecessors)
        containers = sum(
            sys.getsizeof(table) + sum(sys.getsizeof(row) for row in table)
            for table in tables
        )
        masks = sum(
            sys.getsizeof(mask)
            for table in tables
            for row in table
            for mask in row
            if mask
        )
        return containers + masks

    def successor_mask(self, source: int, action: int) -> int:
        return self.successors[source][action]

    def successor_count(self, source: int, action: int) -> int:
        return self.successors[source][action].bit_count()

    def successors_within(self, source: int, action: int, target_mask: int) -> bool:
        return not (self.successors[source][action] & (self.full_mask ^ target_mask))

    def post(self, sources: int, action: int) -> int:
        targets = 0
        for source in iter_bits(sources):
            targets |= self.successor_mask(source, action)
        return targets

    def pre(self, targets: int, action: int) -> int:
        sources = 0
        for target in iter_bits(targets):
            sources |= self.predecessors[action][target]
        return sources

    def decode(self, mask: int) -> frozenset[Hashable]:
        return frozenset(self.states[index] for index in iter_bits(mask))


@dataclass(frozen=True, slots=True)
class CompactDFA:
    nfa: IndexedNFA
    beliefs: tuple[int, ...]
    transitions: tuple[tuple[int, ...], ...]
    predecessors: tuple[tuple[tuple[int, int], ...], ...]
    present: tuple[bool, ...]
    initial: int
    finals: frozenset[int]

    @property
    def state_count(self) -> int:
        return sum(self.present)

    @property
    def transition_count(self) -> int:
        return sum(
            target != MISSING
            for source, row in enumerate(self.transitions)
            if self.present[source]
            for target in row
        )

    def materialize(self) -> dict:
        decoded = [self.nfa.decode(mask) for mask in self.beliefs]
        states = {
            decoded[index]
            for index, present in enumerate(self.present)
            if present
        }
        transitions = {
            decoded[source]: {
                self.nfa.actions[action]: decoded[target]
                for action, target in enumerate(row)
                if target != MISSING
            }
            for source, row in enumerate(self.transitions)
            if self.present[source]
        }
        return {
            "states": states,
            "initial": decoded[self.initial],
            "finals": {decoded[index] for index in self.finals},
            "transitions": transitions,
            "input_symbols": set(self.nfa.actions),
        }


@dataclass(frozen=True, slots=True)
class CompactProduct:
    dfa: CompactDFA
    reachable: tuple[int, ...]
    allowed: tuple[tuple[int, ...], ...]

    @property
    def state_count(self) -> int:
        return sum(mask.bit_count() for mask in self.reachable)

    @property
    def final_count(self) -> int:
        return sum(self.reachable[belief].bit_count() for belief in self.dfa.finals)

    @property
    def transition_count(self) -> int:
        return _transition_count(self.dfa, self.reachable, self.allowed)

    def materialize(self) -> dict:
        return _materialize(self.dfa, self.reachable, self.allowed)


@dataclass(frozen=True, slots=True)
class CompactP2:
    product: CompactProduct
    reachable: tuple[int, ...]
    allowed: tuple[tuple[int, ...], ...]
    coreachable: tuple[int, ...]
    iterations: int

    @property
    def dfa(self) -> CompactDFA:
        return self.product.dfa

    @property
    def state_count(self) -> int:
        return sum(mask.bit_count() for mask in self.reachable)

    @property
    def final_count(self) -> int:
        return sum(self.reachable[belief].bit_count() for belief in self.dfa.finals)

    @property
    def transition_count(self) -> int:
        return _transition_count(self.dfa, self.reachable, self.allowed)

    @property
    def language_nonempty(self) -> bool:
        initial = 1 << self.dfa.nfa.initial
        return bool(self.coreachable[self.dfa.initial] & initial)

    def materialize(self) -> dict:
        result = _materialize(self.dfa, self.reachable, self.allowed)
        result["iterations"] = self.iterations
        return result


def index_nfa(nfa) -> IndexedNFA:
    """Encode an automata-lib NFA's transition relation as integer masks."""

    states = tuple(sorted(nfa.states, key=_stable_key))
    actions = tuple(sorted(nfa.input_symbols, key=_stable_key))
    state_ids = {state: index for index, state in enumerate(states)}
    action_ids = {action: index for index, action in enumerate(actions)}
    if nfa.initial_state not in state_ids:
        raise ValueError("NFA initial state is not present in nfa.states")

    successors = [[0] * len(actions) for _ in states]
    predecessors = [[0] * len(states) for _ in actions]
    enabled_sources = [0] * len(actions)
    for source, action_map in nfa.transitions.items():
        if source not in state_ids:
            continue
        source_id = state_ids[source]
        for action, targets in action_map.items():
            if action not in action_ids:
                continue
            action_id = action_ids[action]
            target_mask = 0
            for target in targets:
                if target not in state_ids:
                    raise ValueError(
                        f"transition target {target!r} is not present in nfa.states"
                    )
                target_id = state_ids[target]
                target_mask |= 1 << target_id
                predecessors[action_id][target_id] |= 1 << source_id
            successors[source_id][action_id] = target_mask
            if target_mask:
                enabled_sources[action_id] |= 1 << source_id

    finals = 0
    for state in nfa.final_states:
        finals |= 1 << state_ids[state]
    return IndexedNFA(
        states=states,
        state_ids=state_ids,
        actions=actions,
        action_ids=action_ids,
        successors=tuple(tuple(row) for row in successors),
        predecessors=tuple(tuple(row) for row in predecessors),
        enabled_sources=tuple(enabled_sources),
        initial=state_ids[nfa.initial_state],
        finals=finals,
    )


def build_compact_dfa_p1(nfa) -> CompactDFA:
    """Index an NFA and build its compact P1 determinization."""

    return build_compact_dfa_p1_from_index(index_nfa(nfa))


def build_compact_dfa_p1_from_index(indexed) -> CompactDFA:
    """Build compact P1 from an indexed transition-storage implementation."""

    initial_mask = 1 << indexed.initial
    beliefs = [initial_mask]
    belief_ids = {initial_mask: 0}
    transitions: list[list[int]] = []
    queue = deque([0])
    while queue:
        belief = queue.popleft()
        row = [MISSING] * len(indexed.actions)
        for action in range(len(indexed.actions)):
            target_mask = indexed.post(beliefs[belief], action)
            if not target_mask:
                continue
            target = belief_ids.get(target_mask)
            if target is None:
                target = len(beliefs)
                belief_ids[target_mask] = target
                beliefs.append(target_mask)
                queue.append(target)
            row[action] = target
        transitions.append(row)

    finals = {
        belief
        for belief, mask in enumerate(beliefs)
        if mask and not (mask & ~indexed.finals)
    }
    live = set(range(len(beliefs)))
    if finals:
        reverse = [[] for _ in beliefs]
        for source, row in enumerate(transitions):
            for target in row:
                if target != MISSING:
                    reverse[target].append(source)
        live = set(finals)
        queue = deque(finals)
        while queue:
            target = queue.popleft()
            for source in reverse[target]:
                if source not in live:
                    live.add(source)
                    queue.append(source)

    # Reachable subset construction normally keeps the initial belief whenever
    # any final is live. Retaining a sentinel also matches the explicit helper's
    # behavior for unusual externally supplied automata.
    kept = sorted(live | {0})
    remap = {old: new for new, old in enumerate(kept)}
    compact_transitions = []
    for old_source in kept:
        row = [MISSING] * len(indexed.actions)
        if old_source in live:
            for action, old_target in enumerate(transitions[old_source]):
                if old_target in live:
                    row[action] = remap[old_target]
        compact_transitions.append(row)

    predecessors: list[list[tuple[int, int]]] = [[] for _ in kept]
    for source, row in enumerate(compact_transitions):
        if kept[source] not in live:
            continue
        for action, target in enumerate(row):
            if target != MISSING:
                predecessors[target].append((source, action))
    return CompactDFA(
        nfa=indexed,
        beliefs=tuple(beliefs[old] for old in kept),
        transitions=tuple(tuple(row) for row in compact_transitions),
        predecessors=tuple(tuple(row) for row in predecessors),
        present=tuple(old in live for old in kept),
        initial=remap[0],
        finals=frozenset(remap[old] for old in finals if old in live),
    )


def _forward_reachable(
    dfa: CompactDFA, allowed: Sequence[Sequence[int]]
) -> list[int]:
    reachable = [0] * len(dfa.beliefs)
    pending = [0] * len(dfa.beliefs)
    initial = 1 << dfa.nfa.initial
    reachable[dfa.initial] = pending[dfa.initial] = initial
    queue = deque([dfa.initial])
    queued = {dfa.initial}
    while queue:
        belief = queue.popleft()
        queued.discard(belief)
        delta, pending[belief] = pending[belief], 0
        for action, target in enumerate(dfa.transitions[belief]):
            if target == MISSING:
                continue
            sources = delta & allowed[belief][action]
            added = dfa.nfa.post(sources, action) & ~reachable[target]
            if added:
                reachable[target] |= added
                pending[target] |= added
                if target not in queued:
                    queued.add(target)
                    queue.append(target)
    return reachable


def build_compact_product(dfa: CompactDFA) -> CompactProduct:
    """Construct reachable product fibers without allocating pair objects."""

    allowed = []
    for belief, mask in enumerate(dfa.beliefs):
        allowed.append(
            [
                mask & dfa.nfa.enabled_sources[action]
                if target != MISSING else 0
                for action, target in enumerate(dfa.transitions[belief])
            ]
        )
    reachable = _forward_reachable(dfa, allowed)
    return CompactProduct(
        dfa=dfa,
        reachable=tuple(reachable),
        allowed=tuple(tuple(row) for row in allowed),
    )


def _backward_coreachable(
    dfa: CompactDFA,
    reachable: Sequence[int],
    allowed: Sequence[Sequence[int]],
) -> list[int]:
    coreachable = [0] * len(dfa.beliefs)
    pending = [0] * len(dfa.beliefs)
    queue = deque()
    queued = set()
    for belief in dfa.finals:
        coreachable[belief] = pending[belief] = reachable[belief]
        if pending[belief]:
            queue.append(belief)
            queued.add(belief)
    while queue:
        target = queue.popleft()
        queued.discard(target)
        delta, pending[target] = pending[target], 0
        pre_cache = {}
        for source, action in dfa.predecessors[target]:
            pre = pre_cache.get(action)
            if pre is None:
                pre = dfa.nfa.pre(delta, action)
                pre_cache[action] = pre
            added = reachable[source] & allowed[source][action] & pre
            added &= ~coreachable[source]
            if added:
                coreachable[source] |= added
                pending[source] |= added
                if source not in queued:
                    queue.append(source)
                    queued.add(source)
    return coreachable


def _universal_sources(
    nfa: IndexedNFA, candidates: int, target_valid: int, action: int
) -> int:
    valid_sources = 0
    for source in iter_bits(candidates):
        if nfa.successors_within(source, action, target_valid):
            valid_sources |= 1 << source
    return valid_sources


def _greatest_fixpoint(
    dfa: CompactDFA,
    reachable: Sequence[int],
    allowed: Sequence[Sequence[int]],
    coreachable: Sequence[int],
) -> list[int]:
    valid = list(coreachable)
    queue = deque(index for index, mask in enumerate(valid) if mask)
    queued = set(queue)
    while queue:
        belief = queue.popleft()
        queued.discard(belief)
        old = valid[belief]
        keep = reachable[belief] if belief in dfa.finals else 0
        if belief not in dfa.finals:
            for action, target in enumerate(dfa.transitions[belief]):
                if target == MISSING:
                    continue
                candidates = old & allowed[belief][action]
                keep |= _universal_sources(
                    dfa.nfa, candidates, valid[target], action
                )
        new = old & keep
        if new == old:
            continue
        valid[belief] = new
        for predecessor, _ in dfa.predecessors[belief]:
            if predecessor not in queued:
                queued.add(predecessor)
                queue.append(predecessor)
        if belief not in queued:
            queued.add(belief)
            queue.append(belief)
    return valid


def compute_compact_nfa_p2(product: CompactProduct) -> CompactP2:
    """Apply the exact P2 refinement to compact product fibers."""

    dfa = product.dfa
    reachable = list(product.reachable)
    allowed = [list(row) for row in product.allowed]
    iterations = 0
    while True:
        iterations += 1
        coreachable = _backward_coreachable(dfa, reachable, allowed)
        valid = _greatest_fixpoint(dfa, reachable, allowed, coreachable)
        if not any(mask & ~valid[i] for i, mask in enumerate(reachable)):
            break

        changed = False
        for belief, mask in enumerate(reachable):
            for action, target in enumerate(dfa.transitions[belief]):
                if target == MISSING:
                    continue
                old = allowed[belief][action]
                active = old & mask
                good = _universal_sources(dfa.nfa, active, valid[target], action)
                new = (old & ~mask) | good
                if new != old:
                    allowed[belief][action] = new
                    changed = True
        reachable = _forward_reachable(dfa, allowed)
        if not changed:
            coreachable = _backward_coreachable(dfa, reachable, allowed)
            break
    return CompactP2(
        product=product,
        reachable=tuple(reachable),
        allowed=tuple(tuple(row) for row in allowed),
        coreachable=tuple(coreachable),
        iterations=iterations,
    )


def build_compact_nfa_p2(nfa) -> CompactP2:
    dfa = build_compact_dfa_p1(nfa)
    return compute_compact_nfa_p2(build_compact_product(dfa))


def enumerate_valid_plans(p2: CompactP2, max_length=10, *, as_strings=True):
    """Enumerate accepted words up to an action-count bound."""

    if max_length < 0:
        raise ValueError("max_length must be non-negative")
    if as_strings and any(not isinstance(action, str) for action in p2.dfa.nfa.actions):
        raise TypeError("string serialization requires string action labels")
    results = set()
    stack = [(p2.dfa.initial, 1 << p2.dfa.nfa.initial, ())]
    while stack:
        belief, states, word = stack.pop()
        if belief in p2.dfa.finals and states:
            results.add("".join(word) if as_strings else word)
        if len(word) == max_length:
            continue
        for action, target in enumerate(p2.dfa.transitions[belief]):
            if target == MISSING:
                continue
            sources = states & p2.allowed[belief][action]
            targets = p2.dfa.nfa.post(sources, action) & p2.reachable[target]
            if targets:
                stack.append((target, targets, word + (p2.dfa.nfa.actions[action],)))
    return results


def shortest_accepting_word(p2: CompactP2):
    """Return one shortest accepted word as a tuple of action symbols."""

    if not p2.language_nonempty:
        return None
    initial = 1 << p2.dfa.nfa.initial
    layers = []
    first = [0] * len(p2.dfa.beliefs)
    for belief in p2.dfa.finals:
        first[belief] = p2.reachable[belief]
    layers.append(first)
    while not (layers[-1][p2.dfa.initial] & initial):
        previous = layers[-1]
        current = list(previous)
        for belief, reachable in enumerate(p2.reachable):
            for action, target in enumerate(p2.dfa.transitions[belief]):
                if target == MISSING or not previous[target]:
                    continue
                current[belief] |= (
                    reachable
                    & p2.allowed[belief][action]
                    & p2.dfa.nfa.pre(previous[target], action)
                )
        if current == previous:
            return None
        layers.append(current)

    belief = p2.dfa.initial
    state = p2.dfa.nfa.initial
    word = []
    for remaining in range(len(layers) - 1, 0, -1):
        source_bit = 1 << state
        for action, target in enumerate(p2.dfa.transitions[belief]):
            if target == MISSING or not (p2.allowed[belief][action] & source_bit):
                continue
            targets = (
                p2.dfa.nfa.successor_mask(state, action)
                & layers[remaining - 1][target]
            )
            if targets:
                word.append(p2.dfa.nfa.actions[action])
                belief, state = target, next(iter_bits(targets))
                break
        else:  # pragma: no cover - internal invariant
            raise RuntimeError("failed to reconstruct shortest compact plan")
    return tuple(word)


def compact_statistics(p2: CompactP2, shortest_word=None) -> dict:
    if shortest_word is None and p2.language_nonempty:
        shortest_word = shortest_accepting_word(p2)
    product = p2.product
    return {
        "nfa_states": len(p2.dfa.nfa.states),
        "nfa_transitions": p2.dfa.nfa.transition_count,
        "nfa_finals": p2.dfa.nfa.finals.bit_count(),
        "dfa_p1_states": p2.dfa.state_count,
        "dfa_p1_transitions": p2.dfa.transition_count,
        "dfa_p1_finals": len(p2.dfa.finals),
        "product_states": product.state_count,
        "product_transitions": product.transition_count,
        "product_finals": product.final_count,
        "nfa_p2_reachable": p2.state_count,
        "nfa_p2_unreachable": product.state_count - p2.state_count,
        "nfa_p2_transitions": p2.transition_count,
        "nfa_p2_finals": p2.final_count,
        "language_nonempty": p2.language_nonempty,
        "shortest_plan_length": None if shortest_word is None else len(shortest_word),
        "p2_iterations": p2.iterations,
    }


def compact_plan_computation(
    nfa,
    *,
    enumerate_plans=True,
    max_length=10,
    verbose=True,
    indexed_nfa=None,
    representation="compact",
):
    """Run the complete bitmask pipeline and return native compact objects."""

    dfa = (
        build_compact_dfa_p1(nfa)
        if indexed_nfa is None
        else build_compact_dfa_p1_from_index(indexed_nfa)
    )
    product = build_compact_product(dfa)
    p2 = compute_compact_nfa_p2(product)
    shortest = shortest_accepting_word(p2)
    plans = enumerate_valid_plans(p2, max_length) if enumerate_plans else None
    stats = compact_statistics(p2, shortest)
    if verbose:
        print(
            "[compact] "
            f"DFA_P1={dfa.state_count}, product={product.state_count}, "
            f"NFA_P2={p2.state_count}, nonempty={p2.language_nonempty}, "
            f"shortest={stats['shortest_plan_length']}"
        )
    return {
        "dfa_p1": dfa,
        "product": product,
        "nfa_p2": p2,
        "valid_plans": plans,
        "language_nonempty": p2.language_nonempty,
        "shortest_plan_length": stats["shortest_plan_length"],
        "shortest_plan_actions": shortest,
        "stats": stats,
        "transition_storage_bytes": dfa.nfa.storage_bytes,
        "unreachable_states": None,
        "unreachable_product_states": product.state_count - p2.state_count,
        "short_circuit_reason": None,
        "inconclusive": False,
        "representation": representation,
    }


def _transition_count(dfa, reachable, allowed) -> int:
    total = 0
    for belief, mask in enumerate(reachable):
        for action, source_mask in enumerate(allowed[belief]):
            for source in iter_bits(mask & source_mask):
                total += dfa.nfa.successor_count(source, action)
    return total


def _materialize(dfa, reachable, allowed) -> dict:
    beliefs = [dfa.nfa.decode(mask) for mask in dfa.beliefs]
    final_beliefs = {beliefs[index] for index in dfa.finals}
    states = {
        (dfa.nfa.states[state], beliefs[belief])
        for belief, mask in enumerate(reachable)
        for state in iter_bits(mask)
    }
    transitions = {}
    for belief, mask in enumerate(reachable):
        for source in iter_bits(mask):
            pair = (dfa.nfa.states[source], beliefs[belief])
            action_map = {}
            for action, target in enumerate(dfa.transitions[belief]):
                if target == MISSING or not (allowed[belief][action] & (1 << source)):
                    continue
                targets = dfa.nfa.successor_mask(source, action) & reachable[target]
                if targets:
                    action_map[dfa.nfa.actions[action]] = {
                        (dfa.nfa.states[state], beliefs[target])
                        for state in iter_bits(targets)
                    }
            if action_map:
                transitions[pair] = action_map
    initial = (dfa.nfa.states[dfa.nfa.initial], beliefs[dfa.initial])
    finals = {pair for pair in states if pair[1] in final_beliefs}
    return {
        "states": states,
        "initial": initial if initial in states else None,
        "finals": finals,
        "transitions": transitions,
        "input_symbols": set(dfa.nfa.actions),
    }
