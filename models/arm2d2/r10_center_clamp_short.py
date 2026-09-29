"""Arm2D2 r10 center goal with clamp borders and two move outcomes."""

from models.arm2d2.standard_variants import build_standard_variant


def build_nfa():
    return build_standard_variant("r10", "center", "clamp", move_outcomes=(20, 30))
