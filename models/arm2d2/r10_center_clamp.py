"""Arm2D2 r10, center goal, clamp joint borders."""

from models.arm2d2.standard_variants import build_standard_variant


def build_nfa():
    return build_standard_variant("r10", "center", "clamp")
