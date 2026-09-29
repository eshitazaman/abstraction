"""Arm2D2 r5, center goal, action joint borders."""

from models.arm2d2.standard_variants import build_standard_variant


def build_nfa():
    return build_standard_variant("r5", "center", "action")
