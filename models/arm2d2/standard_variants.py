"""Shared definitions for the Arm2D2 center/right benchmark matrix."""

from __future__ import annotations

from models.arm2d2.common import Arm2D2Parameters, build_joint_nfa


_RESOLUTIONS = {
    "r1": {"step": 1, "moves": (3, 5, 7), "center_goal": "tight", "center_start": (90, 0)},
    "r3": {"step": 3, "moves": (6, 9, 12), "center_goal": "wide", "center_start": (90, 0)},
    "r4": {"step": 4, "moves": (8, 12, 16), "center_goal": "wide", "center_start": (88, 0)},
    "r5": {"step": 5, "moves": (10, 15, 20), "center_goal": "tight", "center_start": (90, 0)},
    "r10": {"step": 10, "moves": (20, 30, 40), "center_goal": "tight", "center_start": (90, 0)},
}

_GOALS = {
    "center-tight": (-0.2, 0.2, 0.7, 1.1),
    "center-wide": (-0.5, 0.5, 0.5, 1.5),
    "right": (1.7, 2.0, 0.3, 0.7),
    "left": (-1.7, -1.3, 0.7, 1.0),
}

_ACTIONS = {
    "shoulder_negative": "shoulder_down", "shoulder_positive": "shoulder_up",
    "elbow_negative": "elbow_decrease", "elbow_positive": "elbow_increase",
}

_BORDER_ACTIONS = {
    "shoulder_negative": "shoulder_at_min", "shoulder_positive": "shoulder_at_max",
    "elbow_negative": "elbow_at_min", "elbow_positive": "elbow_at_max",
}


def standard_parameters(
    resolution: str,
    goal: str,
    border: str,
    *,
    move_outcomes: tuple[int, ...] | None = None,
) -> Arm2D2Parameters:
    """Return the canonical parameters for an Arm2D2 variant.

    Model modules are deliberately thin wrappers around this function.  The
    optional movement tuple exists only for explicitly named nonstandard
    variants; the regular matrix always uses the resolution default.
    """
    spec = _RESOLUTIONS[resolution]
    if goal == "center":
        goal_name = f"center-{spec['center_goal']}"
        initial = spec["center_start"]
    elif goal == "right":
        goal_name = "right"
        initial = (180, 0)
    elif goal == "left":
        goal_name = "left"
        initial = (120, -90)
    else:
        raise ValueError(f"unknown goal {goal!r}")
    if border not in {"clamp", "block", "action"}:
        raise ValueError(f"unknown border policy {border!r}")
    min_x, max_x, min_y, max_y = _GOALS[goal_name]
    return Arm2D2Parameters(
        angle_increment_degrees=spec["step"],
        shoulder_min_degrees=0, shoulder_max_degrees=180,
        elbow_rel_min_degrees=-120, elbow_rel_max_degrees=120,
        initial_shoulder_degrees=initial[0], initial_elbow_rel_degrees=initial[1],
        upper_arm_length=1.0, forearm_length=1.0,
        goal_min_x=min_x, goal_max_x=max_x, goal_min_y=min_y, goal_max_y=max_y,
        move_outcomes_degrees=spec["moves"] if move_outcomes is None else move_outcomes,
        border_mode={"clamp": "soft", "block": "hard", "action": "action"}[border],
        action_labels=_ACTIONS,
        border_action_labels=_BORDER_ACTIONS if border == "action" else None,
    )


def build_standard_variant(
    resolution: str,
    goal: str,
    border: str,
    *,
    move_outcomes: tuple[int, ...] | None = None,
):
    """Build a canonical Arm2D2 NFA from its short variant descriptor."""
    parameters = standard_parameters(
        resolution, goal, border, move_outcomes=move_outcomes
    )
    return build_joint_nfa(parameters, parameters.goal_configurations())
