"""Tests for the dynamically discovered Arm2D2 model runner."""

from plan_automata import discover_arm2d2_models, load_arm2d2_model


def test_discovers_only_runnable_arm2d2_models():
    models = discover_arm2d2_models()

    assert "30d_goalMid_softBorder" in models
    assert "5d_goalMid_softBorder" in models
    assert "common" not in models


def test_loads_arm2d2_model_from_models_directory():
    nfa = load_arm2d2_model("30d_goalMid_softBorder")

    assert nfa.initial_state in nfa.states
    assert nfa.final_states <= nfa.states
    assert nfa.input_symbols


if __name__ == "__main__":
    test_discovers_only_runnable_arm2d2_models()
    test_loads_arm2d2_model_from_models_directory()
    print("PASS  Arm2D2 model discovery and loading")
