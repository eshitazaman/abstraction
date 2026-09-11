"""Shared Arm2D2 geometry and automaton construction.

Each model supplies an :class:`Arm2D2Parameters` instance.  The builder below
contains only mechanics shared by all variants; it does not choose a goal,
joint limits, move sizes, or border policy for a model.
"""

from dataclasses import dataclass
from math import cos, radians, sin
from typing import Literal, Mapping

from automata.fa.nfa import NFA


BorderMode = Literal["soft", "hard", "action"]

_JOINT_ACTIONS = (
    ("shoulder_negative", "shoulder", -1),
    ("shoulder_positive", "shoulder", 1),
    ("elbow_negative", "elbow", -1),
    ("elbow_positive", "elbow", 1),
)


@dataclass(frozen=True)
class Arm2D2Parameters:
    """Configuration owned by one Arm2D2 model variant."""

    angle_increment_degrees: int
    shoulder_min_degrees: int
    shoulder_max_degrees: int
    elbow_rel_min_degrees: int
    elbow_rel_max_degrees: int
    initial_shoulder_degrees: int
    initial_elbow_rel_degrees: int
    upper_arm_length: float
    forearm_length: float
    goal_min_x: float
    goal_max_x: float
    goal_min_y: float
    goal_max_y: float
    move_outcomes_degrees: tuple[int, ...]
    border_mode: BorderMode
    action_labels: Mapping[str, str]
    border_action_labels: Mapping[str, str] | None = None
    labeled_state_names: bool = False

    def __post_init__(self) -> None:
        if self.angle_increment_degrees <= 0:
            raise ValueError("angle_increment_degrees must be positive")
        if self.border_mode not in {"soft", "hard", "action"}:
            raise ValueError(f"unknown border mode: {self.border_mode}")
        required = {name for name, _, _ in _JOINT_ACTIONS}
        if set(self.action_labels) != required:
            raise ValueError("action_labels must name every joint direction")
        if self.border_mode == "action":
            if self.border_action_labels is None or set(self.border_action_labels) != required:
                raise ValueError("action borders require a label for every joint direction")
        elif self.border_action_labels is not None:
            raise ValueError("only action-border models may define border action labels")

    @property
    def shoulder_bounds(self) -> tuple[int, int]:
        return self.shoulder_min_degrees, self.shoulder_max_degrees

    @property
    def elbow_rel_bounds(self) -> tuple[int, int]:
        return self.elbow_rel_min_degrees, self.elbow_rel_max_degrees

    @property
    def initial_configuration(self) -> tuple[int, int]:
        return self.initial_shoulder_degrees, self.initial_elbow_rel_degrees

    @property
    def shoulder_angles(self) -> range:
        """All permitted absolute shoulder angles, inclusive."""
        return range(
            self.shoulder_min_degrees,
            self.shoulder_max_degrees + self.angle_increment_degrees,
            self.angle_increment_degrees,
        )

    @property
    def elbow_rel_angles(self) -> range:
        """All permitted elbow angles relative to the shoulder, inclusive."""
        return range(
            self.elbow_rel_min_degrees,
            self.elbow_rel_max_degrees + self.angle_increment_degrees,
            self.angle_increment_degrees,
        )

    @property
    def input_symbols(self) -> frozenset[str]:
        symbols = set(self.action_labels.values())
        if self.border_action_labels is not None:
            symbols.update(self.border_action_labels.values())
        return frozenset(symbols)

    def hand_position(self, shoulder_angle: int, elbow_rel_angle: int) -> tuple[float, float]:
        """Return the end-effector position for a joint configuration."""
        elbow_absolute = shoulder_angle + elbow_rel_angle
        x = self.upper_arm_length * cos(radians(shoulder_angle)) + self.forearm_length * cos(radians(elbow_absolute))
        y = self.upper_arm_length * sin(radians(shoulder_angle)) + self.forearm_length * sin(radians(elbow_absolute))
        return x, y

    def is_goal_configuration(self, shoulder_angle: int, elbow_rel_angle: int) -> bool:
        """Whether the end effector lies in this model's rectangular goal."""
        x, y = self.hand_position(shoulder_angle, elbow_rel_angle)
        return self.goal_min_x <= x <= self.goal_max_x and self.goal_min_y <= y <= self.goal_max_y

    def goal_configurations(self) -> set[tuple[int, int]]:
        return {
            (shoulder, elbow_rel)
            for shoulder in self.shoulder_angles
            for elbow_rel in self.elbow_rel_angles
            if self.is_goal_configuration(shoulder, elbow_rel)
        }

    def state_name(self, shoulder_angle: int, elbow_rel_angle: int) -> str:
        if self.labeled_state_names:
            return f"q_b{shoulder_angle}_e{elbow_rel_angle}"
        return f"q{shoulder_angle}_{elbow_rel_angle}"

    def within_joint_limits(self, shoulder_angle: int, elbow_rel_angle: int) -> bool:
        return (
            self.shoulder_min_degrees <= shoulder_angle <= self.shoulder_max_degrees
            and self.elbow_rel_min_degrees <= elbow_rel_angle <= self.elbow_rel_max_degrees
        )


def _clamp(value: int, bounds: tuple[int, int]) -> int:
    return max(bounds[0], min(value, bounds[1]))


def build_joint_nfa(
    parameters: Arm2D2Parameters,
    goal_configurations: set[tuple[int, int]] | None = None,
) -> NFA:
    """Build the nondeterministic joint-motion automaton for ``parameters``."""
    goals = parameters.goal_configurations() if goal_configurations is None else goal_configurations
    states = {
        parameters.state_name(shoulder, elbow_rel)
        for shoulder in parameters.shoulder_angles
        for elbow_rel in parameters.elbow_rel_angles
    }
    # Transitions is a dict containing: source -> { action: {successors}, ...}
    transitions: dict[str, dict[str, set[str]]] = {state: {} for state in states}

    # This double loop checks every possible state
    for shoulder in parameters.shoulder_angles:
        for elbow_rel in parameters.elbow_rel_angles:
            source = parameters.state_name(shoulder, elbow_rel)
            # This loop considers every possible action for a certain state
            for action_key, joint, direction in _JOINT_ACTIONS:
                # Choose which joint we are looking at
                current = shoulder if joint == "shoulder" else elbow_rel
                # Define the bounds for that specific joint
                bounds = parameters.shoulder_bounds if joint == "shoulder" else parameters.elbow_rel_bounds
                border = bounds[0] if direction < 0 else bounds[1]
                at_border = current == border

                # Do not add actions towards a border if the mode is hard.
                if parameters.border_mode == "hard" and at_border:
                    continue
                # Add "negative" actions when we are at a border.
                if parameters.border_mode == "action" and at_border:
                    assert parameters.border_action_labels is not None
                    label = parameters.border_action_labels[action_key]
                    transitions[source][label] = {source}
                    continue

                # Add every action for this particular state (considering all posible succesors)
                label = parameters.action_labels[action_key]
                destinations: set[str] = set()
                # This loop goes over every possible movement (under, expected, over)
                for move in parameters.move_outcomes_degrees:
                    candidate = current + direction * move
                    # Clamp movements to avoid surpassing the borders.
                    target = _clamp(candidate, bounds)
                    # Calculate the target state
                    target_shoulder, target_elbow = (target, elbow_rel) if joint == "shoulder" else (shoulder, target)
                    destinations.add(parameters.state_name(target_shoulder, target_elbow))
                # Add all possible destinations under the transition name
                transitions[source][label] = destinations

    return NFA(
        states=states,
        input_symbols=parameters.input_symbols,
        transitions=transitions,
        initial_state=parameters.state_name(*parameters.initial_configuration),
        final_states={parameters.state_name(*configuration) for configuration in goals},
    )


def build_random_drift_nfa(
    parameters: Arm2D2Parameters,
    drift_action: str,
    drift_outcomes: tuple[int, ...],
    break_state: str = "Break",
    goal_configurations: set[tuple[int, int]] | None = None,
) -> NFA:
    """Build a hard-border model with an additional random joint-drift action."""
    if parameters.border_mode != "hard":
        raise ValueError("random drift requires hard joint borders")
    base = build_joint_nfa(parameters, goal_configurations)
    transitions = {state: dict(actions) for state, actions in base.transitions.items()}
    for shoulder in parameters.shoulder_angles:
        for elbow_rel in parameters.elbow_rel_angles:
            source = parameters.state_name(shoulder, elbow_rel)
            destinations = set()
            for drift in drift_outcomes:
                for joint, direction, bounds in (
                    ("shoulder", -1, parameters.shoulder_bounds),
                    ("shoulder", 1, parameters.shoulder_bounds),
                    ("elbow", -1, parameters.elbow_rel_bounds),
                    ("elbow", 1, parameters.elbow_rel_bounds),
                ):
                    target = (shoulder if joint == "shoulder" else elbow_rel) + direction * drift
                    if bounds[0] <= target <= bounds[1]:
                        target_shoulder, target_elbow = (target, elbow_rel) if joint == "shoulder" else (shoulder, target)
                        destinations.add(parameters.state_name(target_shoulder, target_elbow))
                    else:
                        destinations.add(break_state)
            transitions[source][drift_action] = destinations

    transitions[break_state] = {}
    return NFA(
        states=set(base.states) | {break_state},
        input_symbols=set(base.input_symbols) | {drift_action},
        transitions=transitions,
        initial_state=base.initial_state,
        final_states=base.final_states,
    )
