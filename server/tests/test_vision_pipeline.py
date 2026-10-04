"""Tests for the provider-agnostic vision pipeline (SPEC.md 3.2.D,
GLOSSARY.md: Cached Fallback Schema).

Seam under test: `analyze_formula_crop(image_bytes, client, timeout_s=...,
model=...)`, where `client` is anything duck-typing the OpenAI chat-
completions call shape (`client.chat.completions.create(...)` returning
`.choices[0].message.content`) -- a fake in all tests here, since no live
API key is available in this environment. The real OpenAI-compatible call
path exists in `_call_model` / `make_live_client` but is only exercised by a
fake client in this test suite.
"""
import time

import pytest

from ai.vision_pipeline import (
    CACHED_FALLBACK_SCHEMA,
    FormulaAnalysis,
    SimulationType,
    analyze_formula_crop,
    is_supported_simulation_type,
)


class _FakeCompletions:
    def __init__(self, response_text=None, *, raises=None, delay=0.0):
        self._response_text = response_text
        self._raises = raises
        self._delay = delay

    def create(self, *, model, messages, response_format):
        if self._delay:
            time.sleep(self._delay)
        if self._raises:
            raise self._raises
        return _FakeResponse(self._response_text)


class _FakeChat:
    def __init__(self, **kwargs):
        self.completions = _FakeCompletions(**kwargs)


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
    def __init__(self, **kwargs):
        self.chat = _FakeChat(**kwargs)


SPRING_MASS_JSON = """
{
  "formula_latex": "F = -kx",
  "concept_title": "Spring-Mass Harmonic Oscillation",
  "simulation_type": "spring_mass",
  "parameters": [
    {"key": "k", "label": "Spring Stiffness (N/m)", "min": 10, "max": 100, "val": 45},
    {"key": "m", "label": "Bob Mass (kg)", "min": 0.5, "max": 5.0, "val": 1.2}
  ]
}
"""


def test_successful_call_returns_parsed_formula_analysis():
    client = _FakeClient(response_text=SPRING_MASS_JSON)

    result = analyze_formula_crop(b"fake-png-bytes", client, timeout_s=3.0)

    assert isinstance(result, FormulaAnalysis)
    assert result.simulation_type == "spring_mass"
    assert result.concept_title == "Spring-Mass Harmonic Oscillation"
    assert len(result.parameters) == 2
    assert result.parameters[0].key == "k"


def test_sdk_error_falls_back_to_cached_schema():
    client = _FakeClient(raises=RuntimeError("API quota exceeded"))

    result = analyze_formula_crop(b"fake-png-bytes", client, timeout_s=3.0)

    assert result == CACHED_FALLBACK_SCHEMA


def test_timeout_falls_back_to_cached_schema():
    client = _FakeClient(response_text=SPRING_MASS_JSON, delay=0.3)

    result = analyze_formula_crop(b"fake-png-bytes", client, timeout_s=0.05)

    assert result == CACHED_FALLBACK_SCHEMA


def test_no_client_configured_falls_back_to_cached_schema_without_crashing():
    result = analyze_formula_crop(b"fake-png-bytes", client=None, timeout_s=3.0)

    assert result == CACHED_FALLBACK_SCHEMA


@pytest.mark.parametrize("sim_type", ["spring_mass", "pendulum", "projectile"])
def test_recognized_simulation_types(sim_type):
    assert is_supported_simulation_type(sim_type) is True


def test_unrecognized_simulation_type_is_not_supported():
    assert is_supported_simulation_type("quantum_tunneling") is False


def test_malformed_json_falls_back_to_cached_schema():
    client = _FakeClient(response_text="not valid json at all")

    result = analyze_formula_crop(b"fake-png-bytes", client, timeout_s=3.0)

    assert result == CACHED_FALLBACK_SCHEMA


def test_out_of_enum_simulation_type_still_parses_successfully():
    # The JSON schema constrains shape/types, not enum membership (unless the
    # Pydantic field itself is typed as the Enum, which we deliberately avoid
    # -- see vision_pipeline.py docstring). An out-of-enum value must parse
    # fine here so application code can route it to AI_WIDGET_UNSUPPORTED
    # rather than erroring out.
    body = SPRING_MASS_JSON.replace("spring_mass", "quantum_tunneling")
    client = _FakeClient(response_text=body)

    result = analyze_formula_crop(b"fake-png-bytes", client, timeout_s=3.0)

    assert result.simulation_type == "quantum_tunneling"
    assert is_supported_simulation_type(result.simulation_type) is False


def test_markdown_fenced_json_still_parses():
    # Some OpenAI-compatible routers/models wrap json_object output in a
    # ```json ... ``` code fence despite being asked not to -- observed
    # against a real local router during manual testing. Must not be
    # treated as malformed.
    fenced = "```json\n" + SPRING_MASS_JSON.strip() + "\n```"
    client = _FakeClient(response_text=fenced)

    result = analyze_formula_crop(b"fake-png-bytes", client, timeout_s=3.0)

    assert isinstance(result, FormulaAnalysis)
    assert result.simulation_type == "spring_mass"


def test_bare_markdown_fence_without_json_label_still_parses():
    fenced = "```\n" + SPRING_MASS_JSON.strip() + "\n```"
    client = _FakeClient(response_text=fenced)

    result = analyze_formula_crop(b"fake-png-bytes", client, timeout_s=3.0)

    assert isinstance(result, FormulaAnalysis)


def test_requests_json_object_mode_not_strict_json_schema():
    # json_schema strict mode is not reliably honored by all OpenAI-
    # compatible routers (observed: one silently ignored it and returned
    # prose) -- json_object is the broadly-compatible choice instead.
    seen = {}

    class _RecordingCompletions:
        def create(self, *, model, messages, response_format):
            seen["response_format"] = response_format
            return _FakeResponse(SPRING_MASS_JSON)

    class _RecordingClient:
        def __init__(self):
            self.chat = type("Chat", (), {"completions": _RecordingCompletions()})()

    analyze_formula_crop(b"fake-png-bytes", _RecordingClient(), timeout_s=3.0)

    assert seen["response_format"] == {"type": "json_object"}


def test_passes_requested_model_through_to_the_client():
    seen = {}

    class _RecordingCompletions:
        def create(self, *, model, messages, response_format):
            seen["model"] = model
            return _FakeResponse(SPRING_MASS_JSON)

    class _RecordingClient:
        def __init__(self):
            self.chat = type("Chat", (), {"completions": _RecordingCompletions()})()

    analyze_formula_crop(b"fake-png-bytes", _RecordingClient(), timeout_s=3.0, model="some/other-model")

    assert seen["model"] == "some/other-model"
