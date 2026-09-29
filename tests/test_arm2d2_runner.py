"""Tests for Arm2D2 models using the common model interface."""

import json
from pathlib import Path

from plan_automata import discover_models, load_model


def test_discovers_only_runnable_arm2d2_models():
    models = discover_models()

    assert "arm2d2.r10_center_clamp" in models
    assert "arm2d2.r1_center_clamp" in models
    assert "arm2d2.common" not in models


def test_loads_arm2d2_model_from_models_directory():
    nfa = load_model("arm2d2.r10_center_clamp")

    assert nfa.initial_state in nfa.states
    assert nfa.final_states <= nfa.states
    assert nfa.input_symbols


def test_manifest_and_every_model_builder_agree():
    manifest_path = Path("models/arm2d2/model_manifest.json")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    expected_ids = {f"arm2d2.{entry['id']}" for entry in manifest["models"]}
    actual_ids = {
        model for model in discover_models() if model.startswith("arm2d2.")
    }
    assert actual_ids == expected_ids

    for entry in manifest["models"]:
        step = entry["resolution_deg"]
        shoulder_states = len(range(0, 180 + step, step))
        expected_states = shoulder_states
        if entry.get("joint_count", 2) == 2:
            expected_states *= len(range(-120, 120 + step, step))
        if "disturbance" in entry:
            expected_states += 1  # The deliberately explicit Break state.
        nfa = load_model(f"arm2d2.{entry['id']}")
        assert len(nfa.states) == expected_states


if __name__ == "__main__":
    test_discovers_only_runnable_arm2d2_models()
    test_loads_arm2d2_model_from_models_directory()
    test_manifest_and_every_model_builder_agree()
    print("PASS  Arm2D2 model discovery and loading")
