"""Builds the AI_WIDGET_SPAWN / AI_WIDGET_UNSUPPORTED wire messages
documented in SPEC.md section 4.B, from a parsed `FormulaAnalysis`.
"""
import json

from .vision_pipeline import FormulaAnalysis, is_supported_simulation_type


def build_widget_message(
    analysis: FormulaAnalysis, *, widget_id: str, anchor_x: float, anchor_y: float
) -> str:
    if is_supported_simulation_type(analysis.simulation_type):
        return json.dumps(
            {
                "type": "AI_WIDGET_SPAWN",
                "widget_id": widget_id,
                "anchor_x": anchor_x,
                "anchor_y": anchor_y,
                "formula_latex": analysis.formula_latex,
                "title": analysis.concept_title,
                "sim_type": analysis.simulation_type,
                "parameters": [p.model_dump() for p in analysis.parameters],
            }
        )

    return json.dumps(
        {
            "type": "AI_WIDGET_UNSUPPORTED",
            "widget_id": widget_id,
            "anchor_x": anchor_x,
            "anchor_y": anchor_y,
            "formula_latex": analysis.formula_latex,
            "title": analysis.concept_title,
            "attempted_sim_type": analysis.simulation_type,
        }
    )
