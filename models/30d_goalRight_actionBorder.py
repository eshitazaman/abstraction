"""30° arm model with an upper-right goal and explicit border actions.

At an outward limit, the regular joint command is unavailable and its ``n...``
counterpart self-loops to report the border condition.
"""

from arm2d2_models.common import Arm2D2Parameters, build_joint_nfa


MOVE_OUTCOMES = (20, 30, 40)
MODEL = Arm2D2Parameters(
    angle_increment_degrees=10,
    shoulder_min_degrees=0,
    shoulder_max_degrees=180,
    elbow_rel_min_degrees=-120,
    elbow_rel_max_degrees=120,
    initial_shoulder_degrees=180,
    initial_elbow_rel_degrees=0,
    upper_arm_length=1.0,
    forearm_length=1.0,
    goal_min_x=1.7,
    goal_max_x=2,
    goal_min_y=0.3,
    goal_max_y=1,
    move_outcomes_degrees=MOVE_OUTCOMES,
    border_mode="action",
    action_labels={
        "shoulder_negative": "shoulder_down", "shoulder_positive": "shoulder_up",
        "elbow_negative": "elbow_decrease", "elbow_positive": "elbow_increase",
    },
    border_action_labels={
        "shoulder_negative": "shoulder_at_min", "shoulder_positive": "shoulder_at_max",
        "elbow_negative": "elbow_at_min", "elbow_positive": "elbow_at_max",
    },
)
GOAL_CONFIGURATIONS = MODEL.goal_configurations()
ACTIONS = MODEL.input_symbols


def build_arm2d2_nfa():
    return build_joint_nfa(MODEL, GOAL_CONFIGURATIONS)


def build_agustin_nfa():
    return build_arm2d2_nfa()
