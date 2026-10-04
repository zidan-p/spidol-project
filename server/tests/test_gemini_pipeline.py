"""Tests for the Gemini structured-output pipeline (SPEC.md 3.2.D,
GLOSSARY.md: Cached Fallback Schema).

Seam under test: `analyze_formula_crop(image_bytes, client, timeout_s=...)`,
where `client` is anything duck-typing google-genai's
`client.models.generate_content(...)` call shape -- a fake in all tests
here, since no live GEMINI_API_KEY is available in this environment (see
report). The real `google-genai` call path exists in `_call_gemini` /
`make_live_client` but is only exercised by a fake client in this test
suite.
"""
import time

import pytest

from ai.gemini_pipeline import (
    CACHED_FALLBACK_SCHEMA,
    FormulaAnalysis,
    SimulationType,
    analyze_formula_crop,
    is_supported_simulation_type,
)


class _FakeModels:
    def __init__(self, response_text=None, *, raises=None, delay=0.0):
        self._response_text = response_text
        self._raises = raises
        self._delay = delay

    def generate_content(self, *, model, contents, config):
        if self._delay:
            time.sleep(self._delay)
        if self._raises:
            raise self._raises
        return _FakeResponse(self._response_text)


class _FakeResponse:
    def __init__(self, text):
        self.text = text


class _FakeClient:
    def __init__(self, **kwargs):
        self.models = _FakeModels(**kwargs)


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


def test_malformed_json_from_gemini_falls_back_to_cached_schema():
    client = _FakeClient(response_text="not valid json at all")

    result = analyze_formula_crop(b"fake-png-bytes", client, timeout_s=3.0)

    assert result == CACHED_FALLBACK_SCHEMA


def test_out_of_enum_simulation_type_still_parses_successfully():
    # response_schema constrains shape/types, not enum membership (unless the
    # Pydantic field itself is typed as the Enum, which we deliberately avoid
    # -- see gemini_pipeline.py docstring). An out-of-enum value must parse
    # fine here so application code can route it to AI_WIDGET_UNSUPPORTED
    # rather than erroring out.
    body = SPRING_MASS_JSON.replace("spring_mass", "quantum_tunneling")
    client = _FakeClient(response_text=body)

    result = analyze_formula_crop(b"fake-png-bytes", client, timeout_s=3.0)

    assert result.simulation_type == "quantum_tunneling"
    assert is_supported_simulation_type(result.simulation_type) is False
