"""30° arm model with a centred goal and blocking (hard) joint borders."""

from arm2d2_models.common import Arm2D2Parameters, build_joint_nfa


MOVE_OUTCOMES = (20, 30, 40)
MODEL = Arm2D2Parameters(
    angle_increment_degrees=10,
    shoulder_min_degrees=0,
    shoulder_max_degrees=180,
    elbow_rel_min_degrees=-120,
    elbow_rel_max_degrees=120,
    initial_shoulder_degrees=90,
    initial_elbow_rel_degrees=0,
    upper_arm_length=1.0,
    forearm_length=1.0,
    goal_min_x=-0.2,
    goal_max_x=0.2,
    goal_min_y=0.7,
    goal_max_y=1.1,
    move_outcomes_degrees=MOVE_OUTCOMES,
    border_mode="hard",
    action_labels={
        "shoulder_negative": "shoulder_down", "shoulder_positive": "shoulder_up",
        "elbow_negative": "elbow_decrease", "elbow_positive": "elbow_increase",
    },
)
GOAL_CONFIGURATIONS = MODEL.goal_configurations()
ACTIONS = MODEL.input_symbols


def build_arm2d2_nfa():
    return build_joint_nfa(MODEL, GOAL_CONFIGURATIONS)


def build_agustin_nfa():
    return build_arm2d2_nfa()
