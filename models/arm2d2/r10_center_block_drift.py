"""Arm2D2 r10 center goal with block borders and nondeterministic drift."""

from models.arm2d2.common import build_random_drift_nfa
from models.arm2d2.standard_variants import standard_parameters


def build_nfa():
    parameters = standard_parameters("r10", "center", "block")
    return build_random_drift_nfa(
        parameters,
        drift_action="drift",
        drift_outcomes=(10, 20, 30),
        break_state="Break",
        goal_configurations=parameters.goal_configurations(),
    )
