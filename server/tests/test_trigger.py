"""Tests for the full AI Trigger orchestration: region -> crop -> vision
model -> dispatch (SPEC.md 3.2.D steps 1-5).
"""
import json

from ai.trigger import handle_ai_trigger
from ai.stroke_region import StrokeRegionTracker
from hal.image_source import BlankCanvasImageSource


class _FakeCompletions:
    def __init__(self, response_text):
        self._response_text = response_text
        self.call_count = 0

    def create(self, *, model, messages, response_format):
        self.call_count += 1
        return _FakeResponse(self._response_text)


class _FakeMessage:
    def __init__(self, content):
        self.content = content


class _FakeChoice:
    def __init__(self, content):
        self.message = _FakeMessage(content)


class _FakeResponse:
    def __init__(self, content):
        self.choices = [_FakeChoice(content)]


class _FakeClient:
    def __init__(self, response_text):
        self.completions = _FakeCompletions(response_text)
        self.chat = type("Chat", (), {"completions": self.completions})()


SPRING_MASS_JSON = json.dumps(
    {
        "formula_latex": "F = -kx",
        "concept_title": "Spring-Mass Harmonic Oscillation",
        "simulation_type": "spring_mass",
        "parameters": [
            {"key": "k", "label": "Spring Stiffness (N/m)", "min": 10, "max": 100, "val": 45},
        ],
    }
)


def _drawn_stroke_tracker():
    tracker = StrokeRegionTracker()
    tracker.ingest(x=0.3, y=0.3, is_touching=True, is_detected=True)
    tracker.ingest(x=0.6, y=0.5, is_touching=True, is_detected=True)
    tracker.ingest(x=0.6, y=0.5, is_touching=False, is_detected=True)
    return tracker


def test_handle_ai_trigger_spawns_widget_for_recognized_formula():
    tracker = _drawn_stroke_tracker()
    client = _FakeClient(SPRING_MASS_JSON)
    image_source = BlankCanvasImageSource(width=640, height=480)

    raw = handle_ai_trigger(
        stroke_tracker=tracker,
        image_source=image_source,
        vision_client=client,
        timeout_s=1.0,
    )
    payload = json.loads(raw)

    assert payload["type"] == "AI_WIDGET_SPAWN"
    assert payload["sim_type"] == "spring_mass"
    assert payload["formula_latex"] == "F = -kx"
    assert isinstance(payload["widget_id"], str) and payload["widget_id"]


def test_handle_ai_trigger_marks_trigger_so_region_resets():
    tracker = _drawn_stroke_tracker()
    client = _FakeClient(SPRING_MASS_JSON)
    image_source = BlankCanvasImageSource()

    handle_ai_trigger(
        stroke_tracker=tracker, image_source=image_source, vision_client=client, timeout_s=1.0
    )

    assert tracker.region_since_last_trigger() is None


def test_handle_ai_trigger_with_no_strokes_serves_dummy_graph_without_calling_the_vision_model():
    tracker = StrokeRegionTracker()
    client = _FakeClient(SPRING_MASS_JSON)
    image_source = BlankCanvasImageSource()

    raw = handle_ai_trigger(
        stroke_tracker=tracker, image_source=image_source, vision_client=client, timeout_s=1.0
    )
    payload = json.loads(raw)

    assert payload["type"] == "AI_WIDGET_SPAWN"
    assert payload["sim_type"] == "function_graph"
    # The whole point: an empty AI Trigger Region never spends a vision
    # model call (and its tokens) on a press that can't possibly contain a
    # real formula.
    assert client.completions.call_count == 0


def test_handle_ai_trigger_with_no_client_falls_back_to_cached_schema_and_still_spawns():
    tracker = _drawn_stroke_tracker()
    image_source = BlankCanvasImageSource()

    raw = handle_ai_trigger(
        stroke_tracker=tracker, image_source=image_source, vision_client=None, timeout_s=1.0
    )
    payload = json.loads(raw)

    assert payload["type"] == "AI_WIDGET_SPAWN"
    assert payload["sim_type"] == "spring_mass"  # the Cached Fallback Schema's sim type
