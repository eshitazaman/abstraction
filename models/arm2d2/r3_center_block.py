"""Arm2D2 r3, center goal, block joint borders."""

from models.arm2d2.standard_variants import build_standard_variant


def build_nfa():
    return build_standard_variant("r3", "center", "block")
