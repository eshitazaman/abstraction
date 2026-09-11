"""Compatibility package for Arm2D2 model variants stored in ``models/``.

The model files historically import shared helpers as ``arm2d2_models.common``.
Keeping this tiny package lets the repository keep the variants in the simpler
``models/`` directory while preserving those imports.
"""

from pathlib import Path


__path__ = [str(Path(__file__).resolve().parents[1] / "models")]
