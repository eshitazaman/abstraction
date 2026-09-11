"""Sparse-transition variant of the compact bitmask planning backend.

Beliefs and product fibers remain Python integer bitsets. Unlike the baseline
compact backend, successor and predecessor relations use CSR-style unsigned
integer arrays, so their storage is proportional to the number of cells and
edges rather than to the highest numbered state in every transition.
"""

from __future__ import annotations

from array import array
from dataclasses import dataclass
from typing import Hashable, Iterator

from compact_plan_automata import compact_plan_computation, iter_bits


UINT32_MAX = (1 << 32) - 1


def _stable_key(value) -> tuple[str, str]:
    return type(value).__name__, repr(value)


@dataclass(frozen=True, slots=True)
class CSRIndexedNFA:
    """NFA relation stored in forward and reverse compressed sparse rows."""

    states: tuple[Hashable, ...]
    state_ids: dict[Hashable, int]
    actions: tuple[Hashable, ...]
    action_ids: dict[Hashable, int]
    successor_offsets: array
    successor_targets: array
    predecessor_offsets: array
    predecessor_sources: array
    enabled_sources: tuple[int, ...]
    initial: int
    finals: int

    @property
    def full_mask(self) -> int:
        return (1 << len(self.states)) - 1

    @property
    def transition_count(self) -> int:
        return len(self.successor_targets)

    @property
    def storage_bytes(self) -> int:
        """Bytes occupied by the four raw CSR buffers."""

        return sum(
            len(values) * values.itemsize
            for values in (
                self.successor_offsets,
                self.successor_targets,
                self.predecessor_offsets,
                self.predecessor_sources,
            )
        )

    def _successor_span(self, source: int, action: int) -> tuple[int, int]:
        row = source * len(self.actions) + action
        return self.successor_offsets[row], self.successor_offsets[row + 1]

    def _predecessor_span(self, target: int, action: int) -> tuple[int, int]:
        row = action * len(self.states) + target
        return self.predecessor_offsets[row], self.predecessor_offsets[row + 1]

    def iter_successors(self, source: int, action: int) -> Iterator[int]:
        start, end = self._successor_span(source, action)
        for offset in range(start, end):
            yield self.successor_targets[offset]

    def successor_mask(self, source: int, action: int) -> int:
        result = 0
        for target in self.iter_successors(source, action):
            result |= 1 << target
        return result

    def successor_count(self, source: int, action: int) -> int:
        start, end = self._successor_span(source, action)
        return end - start

    def successors_within(self, source: int, action: int, target_mask: int) -> bool:
        return all(target_mask & (1 << target) for target in self.iter_successors(source, action))

    def post(self, sources: int, action: int) -> int:
        result = 0
        for source in iter_bits(sources):
            for target in self.iter_successors(source, action):
                result |= 1 << target
        return result

    def pre(self, targets: int, action: int) -> int:
        result = 0
        for target in iter_bits(targets):
            start, end = self._predecessor_span(target, action)
            for offset in range(start, end):
                result |= 1 << self.predecessor_sources[offset]
        return result

    def decode(self, mask: int) -> frozenset[Hashable]:
        return frozenset(self.states[index] for index in iter_bits(mask))


def index_nfa_csr(nfa) -> CSRIndexedNFA:
    """Build a pair of CSR relations directly from an automata-lib NFA."""

    states = tuple(sorted(nfa.states, key=_stable_key))
    actions = tuple(sorted(nfa.input_symbols, key=_stable_key))
    if len(states) > UINT32_MAX:
        raise ValueError("CSR backend supports at most 2^32 - 1 NFA states")
    state_ids = {state: index for index, state in enumerate(states)}
    action_ids = {action: index for index, action in enumerate(actions)}
    if nfa.initial_state not in state_ids:
        raise ValueError("NFA initial state is not present in nfa.states")

    cell_count = len(states) * len(actions)
    successor_offsets = array("I", [0])
    successor_targets = array("I")
    enabled_sources = [0] * len(actions)
    for source_id, source in enumerate(states):
        action_map = nfa.transitions.get(source, {})
        for action_id, action in enumerate(actions):
            targets = action_map.get(action, ())
            encoded = []
            for target in targets:
                if target not in state_ids:
                    raise ValueError(
                        f"transition target {target!r} is not present in nfa.states"
                    )
                encoded.append(state_ids[target])
            encoded.sort()
            successor_targets.extend(encoded)
            successor_offsets.append(len(successor_targets))
            if encoded:
                enabled_sources[action_id] |= 1 << source_id
    if len(successor_targets) > UINT32_MAX:
        raise ValueError("CSR backend supports at most 2^32 - 1 transition edges")
    if len(successor_offsets) != cell_count + 1:  # pragma: no cover - invariant
        raise RuntimeError("invalid successor CSR dimensions")

    predecessor_counts = array("I", [0]) * cell_count
    for source in range(len(states)):
        for action in range(len(actions)):
            row = source * len(actions) + action
            for offset in range(successor_offsets[row], successor_offsets[row + 1]):
                target = successor_targets[offset]
                predecessor_counts[action * len(states) + target] += 1

    predecessor_offsets = array("I", [0])
    for count in predecessor_counts:
        predecessor_offsets.append(predecessor_offsets[-1] + count)
    predecessor_sources = array("I", [0]) * len(successor_targets)
    cursors = array("I", predecessor_offsets[:-1])
    for source in range(len(states)):
        for action in range(len(actions)):
            row = source * len(actions) + action
            for offset in range(successor_offsets[row], successor_offsets[row + 1]):
                target = successor_targets[offset]
                reverse_row = action * len(states) + target
                predecessor_sources[cursors[reverse_row]] = source
                cursors[reverse_row] += 1

    finals = 0
    for state in nfa.final_states:
        finals |= 1 << state_ids[state]
    return CSRIndexedNFA(
        states=states,
        state_ids=state_ids,
        actions=actions,
        action_ids=action_ids,
        successor_offsets=successor_offsets,
        successor_targets=successor_targets,
        predecessor_offsets=predecessor_offsets,
        predecessor_sources=predecessor_sources,
        enabled_sources=tuple(enabled_sources),
        initial=state_ids[nfa.initial_state],
        finals=finals,
    )


def compact_csr_plan_computation(
    nfa, *, enumerate_plans=True, max_length=10, verbose=True
):
    """Run the compact planner using CSR transition storage."""

    indexed = index_nfa_csr(nfa)
    result = compact_plan_computation(
        nfa,
        enumerate_plans=enumerate_plans,
        max_length=max_length,
        verbose=verbose,
        indexed_nfa=indexed,
        representation="compact-csr",
    )
    result["transition_storage_bytes"] = indexed.storage_bytes
    return result
