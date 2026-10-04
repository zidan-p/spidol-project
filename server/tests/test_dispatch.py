"""Tests for the AI_WIDGET_SPAWN / AI_WIDGET_UNSUPPORTED wire-message
builder (SPEC.md section 4.B).
"""
import json

from ai.dispatch import build_widget_message
from ai.vision_pipeline import FormulaAnalysis, Parameter


def test_recognized_simulation_type_builds_ai_widget_spawn():
    analysis = FormulaAnalysis(
        formula_latex="F = -kx",
        concept_title="Spring-Mass Harmonic Oscillation",
        simulation_type="spring_mass",
        parameters=[
            Parameter(key="k", label="Spring Stiffness (N/m)", min=10, max=100, val=45),
            Parameter(key="m", label="Bob Mass (kg)", min=0.5, max=5.0, val=1.2),
        ],
    )

    raw = build_widget_message(
        analysis, widget_id="widget_oscillator_01", anchor_x=0.55, anchor_y=0.30
    )
    payload = json.loads(raw)

    assert payload == {
        "type": "AI_WIDGET_SPAWN",
        "widget_id": "widget_oscillator_01",
        "anchor_x": 0.55,
        "anchor_y": 0.30,
        "formula_latex": "F = -kx",
        "title": "Spring-Mass Harmonic Oscillation",
        "sim_type": "spring_mass",
        "parameters": [
            {"key": "k", "label": "Spring Stiffness (N/m)", "min": 10, "max": 100, "val": 45},
            {"key": "m", "label": "Bob Mass (kg)", "min": 0.5, "max": 5.0, "val": 1.2},
        ],
    }


def test_unrecognized_simulation_type_builds_ai_widget_unsupported():
    analysis = FormulaAnalysis(
        formula_latex="\\nabla^2 \\psi = 0",
        concept_title="Wave Equation",
        simulation_type="quantum_tunneling",
        parameters=[],
    )

    raw = build_widget_message(analysis, widget_id="widget_02", anchor_x=0.1, anchor_y=0.2)
    payload = json.loads(raw)

    assert payload["type"] == "AI_WIDGET_UNSUPPORTED"
    assert payload["widget_id"] == "widget_02"
    assert payload["formula_latex"] == "\\nabla^2 \\psi = 0"
    assert payload["attempted_sim_type"] == "quantum_tunneling"
