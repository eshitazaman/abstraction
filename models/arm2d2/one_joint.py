"""One-joint planar-arm geometry and automaton construction.

This model has a shoulder joint only: the arm is one rigid segment of length
two, with its hand at the segment's endpoint.
"""

from dataclasses import dataclass
from math import cos, radians, sin
from typing import Literal, Mapping

from automata.fa.nfa import NFA


BorderMode = Literal["soft", "hard", "action"]
ARM_LENGTH = 2.0

_JOINT_ACTIONS = (
    ("shoulder_negative", -1),
    ("shoulder_positive", 1),
)


@dataclass(frozen=True)
class Arm2D2Parameters:
    """Configuration for a planar arm with one shoulder joint."""

    angle_increment_degrees: int
    shoulder_min_degrees: int
    shoulder_max_degrees: int
    initial_shoulder_degrees: int
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
        required = {name for name, _ in _JOINT_ACTIONS}
        if set(self.action_labels) != required:
            raise ValueError("action_labels must name every shoulder direction")
        if self.border_mode == "action":
            if self.border_action_labels is None or set(self.border_action_labels) != required:
                raise ValueError("action borders require a label for every shoulder direction")
        elif self.border_action_labels is not None:
            raise ValueError("only action-border models may define border action labels")

    @property
    def shoulder_bounds(self) -> tuple[int, int]:
        return self.shoulder_min_degrees, self.shoulder_max_degrees

    @property
    def shoulder_angles(self) -> range:
        """All permitted absolute shoulder angles, inclusive."""
        return range(
            self.shoulder_min_degrees,
            self.shoulder_max_degrees + self.angle_increment_degrees,
            self.angle_increment_degrees,
        )

    @property
    def input_symbols(self) -> frozenset[str]:
        symbols = set(self.action_labels.values())
        if self.border_action_labels is not None:
            symbols.update(self.border_action_labels.values())
        return frozenset(symbols)

    def hand_position(self, shoulder_angle: int) -> tuple[float, float]:
        """Return the endpoint of the length-two arm."""
        return (
            ARM_LENGTH * cos(radians(shoulder_angle)),
            ARM_LENGTH * sin(radians(shoulder_angle)),
        )

    def is_goal_configuration(self, shoulder_angle: int) -> bool:
        """Whether the hand lies in this model's rectangular goal."""
        x, y = self.hand_position(shoulder_angle)
        return self.goal_min_x <= x <= self.goal_max_x and self.goal_min_y <= y <= self.goal_max_y

    def goal_configurations(self) -> set[int]:
        return {angle for angle in self.shoulder_angles if self.is_goal_configuration(angle)}

    def state_name(self, shoulder_angle: int) -> str:
        return f"q_b{shoulder_angle}" if self.labeled_state_names else f"q{shoulder_angle}"

    def within_joint_limits(self, shoulder_angle: int) -> bool:
        return self.shoulder_min_degrees <= shoulder_angle <= self.shoulder_max_degrees


def _clamp(value: int, bounds: tuple[int, int]) -> int:
    return max(bounds[0], min(value, bounds[1]))


def build_joint_nfa(
    parameters: Arm2D2Parameters,
    goal_configurations: set[int] | None = None,
) -> NFA:
    """Build the nondeterministic shoulder-motion automaton."""
    goals = parameters.goal_configurations() if goal_configurations is None else goal_configurations
    states = {parameters.state_name(shoulder) for shoulder in parameters.shoulder_angles}
    transitions: dict[str, dict[str, set[str]]] = {state: {} for state in states}

    for shoulder in parameters.shoulder_angles:
        source = parameters.state_name(shoulder)
        for action_key, direction in _JOINT_ACTIONS:
            border = parameters.shoulder_bounds[0] if direction < 0 else parameters.shoulder_bounds[1]
            if parameters.border_mode == "hard" and shoulder == border:
                continue
            if parameters.border_mode == "action" and shoulder == border:
                assert parameters.border_action_labels is not None
                transitions[source][parameters.border_action_labels[action_key]] = {source}
                continue

            destinations = {
                parameters.state_name(
                    _clamp(shoulder + direction * move, parameters.shoulder_bounds)
                )
                for move in parameters.move_outcomes_degrees
            }
            transitions[source][parameters.action_labels[action_key]] = destinations

    return NFA(
        states=states,
        input_symbols=parameters.input_symbols,
        transitions=transitions,
        initial_state=parameters.state_name(parameters.initial_shoulder_degrees),
        final_states={parameters.state_name(shoulder) for shoulder in goals},
    )


def build_random_drift_nfa(
    parameters: Arm2D2Parameters,
    drift_action: str,
    drift_outcomes: tuple[int, ...],
    break_state: str = "Break",
    goal_configurations: set[int] | None = None,
) -> NFA:
    """Build a hard-border model with an additional random shoulder-drift action."""
    if parameters.border_mode != "hard":
        raise ValueError("random drift requires hard joint borders")
    base = build_joint_nfa(parameters, goal_configurations)
    transitions = {state: dict(actions) for state, actions in base.transitions.items()}
    for shoulder in parameters.shoulder_angles:
        destinations = set()
        for drift in drift_outcomes:
            for direction in (-1, 1):
                target = shoulder + direction * drift
                if parameters.within_joint_limits(target):
                    destinations.add(parameters.state_name(target))
                else:
                    destinations.add(break_state)
        transitions[parameters.state_name(shoulder)][drift_action] = destinations

    transitions[break_state] = {}
    return NFA(
        states=set(base.states) | {break_state},
        input_symbols=set(base.input_symbols) | {drift_action},
        transitions=transitions,
        initial_state=base.initial_state,
        final_states=base.final_states,
    )


def build_nfa() -> NFA:
    """Build the runnable one-joint Arm2D2 model.

    The hand starts upright and must rotate into the right-hand goal region.
    """
    parameters = Arm2D2Parameters(
        angle_increment_degrees=10,
        shoulder_min_degrees=0,
        shoulder_max_degrees=180,
        initial_shoulder_degrees=90,
        goal_min_x=1.7,
        goal_max_x=2.0,
        goal_min_y=0.3,
        goal_max_y=1,
        move_outcomes_degrees=(20, 30, 40),
        border_mode="soft",
        action_labels={
            "shoulder_negative": "shoulder_down",
            "shoulder_positive": "shoulder_up",
        },
    )
    return build_joint_nfa(parameters)
