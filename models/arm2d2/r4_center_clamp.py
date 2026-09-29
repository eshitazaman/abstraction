"""Arm2D2 r4, center goal, clamp joint borders."""

from models.arm2d2.standard_variants import build_standard_variant


def build_nfa():
    return build_standard_variant("r4", "center", "clamp")
