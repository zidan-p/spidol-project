"""Formula crop -> Gemini Vision -> Simulation Type + params (SPEC.md
3.2.D, `ai/gemini_pipeline.py`).

Model name note (per the implementation research notes, section 5 --
overriding stale SPEC.md/ticket text): the real current Flash-Lite model as
of this writing is `gemini-3.1-flash-lite`, not `gemini-1.5-flash` (retired)
and not `gemini-3.5-flash-lite` (doesn't exist). Re-verify via
`client.models.list()` at deploy time if this drifts again; the model
family churns every few months.

SDK note: `google-genai` (`from google import genai`), not the legacy/
deprecated `google-generativeai`.
"""
import logging
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from enum import Enum

from pydantic import BaseModel, ValidationError

logger = logging.getLogger(__name__)

GEMINI_MODEL = "gemini-3.1-flash-lite"
DEFAULT_TIMEOUT_S = 3.0

PROMPT_TEXT = (
    "Extract the handwritten physics/math formula in this image. "
    "Classify it as one of: spring_mass, pendulum, projectile -- or, if it "
    "doesn't match any of those, your best short snake_case label for the "
    "concept. Return its LaTeX, a short concept title, and reasonable "
    "adjustable parameters with min/max/default values."
)


class SimulationType(str, Enum):
    """The fixed, hand-built Simulation Type enum (GLOSSARY.md: Simulation
    Type). Used for validation in application code, not as the Pydantic
    field type on `FormulaAnalysis.simulation_type` -- see that class's
    docstring for why.
    """

    SPRING_MASS = "spring_mass"
    PENDULUM = "pendulum"
    PROJECTILE = "projectile"


def is_supported_simulation_type(value: str) -> bool:
    return value in {member.value for member in SimulationType}


class Parameter(BaseModel):
    key: str
    label: str
    min: float
    max: float
    val: float


class FormulaAnalysis(BaseModel):
    formula_latex: str
    concept_title: str
    # Deliberately `str`, not `SimulationType`: response_schema constrains
    # shape/types but typing this as the Enum would make Gemini's SDK/schema
    # layer reject (or coerce) an out-of-enum value before it ever reaches
    # application code. Ticket 04 instead wants an unrecognized value to
    # parse successfully and be routed to AI_WIDGET_UNSUPPORTED -- so the
    # enum check happens explicitly, after parsing, via
    # `is_supported_simulation_type`.
    simulation_type: str
    parameters: list[Parameter]


CACHED_FALLBACK_SCHEMA = FormulaAnalysis(
    formula_latex=r"\frac{d^2x}{dt^2} + \frac{k}{m}x = 0",
    concept_title="Simple Harmonic Motion",
    simulation_type=SimulationType.SPRING_MASS.value,
    parameters=[
        Parameter(key="k", label="Spring Constant (N/m)", min=10, max=100, val=40),
        Parameter(key="m", label="Mass (kg)", min=0.5, max=5.0, val=1.0),
    ],
)
"""GLOSSARY.md: Cached Fallback Schema -- the pre-baked response for the
known competition demo formula, served if the live Gemini call errors or
times out, so a dropped venue connection never visibly breaks the live run.
"""


def make_live_client(api_key: str | None = None):
    """Constructs a real `google-genai` client. Imported lazily so modules/
    tests that only exercise the fake-client path never need the SDK
    importable to succeed.
    """
    from google import genai

    return genai.Client(api_key=api_key)


def _call_gemini(client, image_bytes: bytes) -> FormulaAnalysis:
    from google.genai import types

    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=[
            types.Part.from_bytes(data=image_bytes, mime_type="image/png"),
            PROMPT_TEXT,
        ],
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=FormulaAnalysis,
        ),
    )
    return FormulaAnalysis.model_validate_json(response.text)


def analyze_formula_crop(
    image_bytes: bytes, client, timeout_s: float = DEFAULT_TIMEOUT_S
) -> FormulaAnalysis:
    """Always attempts the live Gemini call first (SPEC.md 3.2.D: "the real
    API call is always attempted first, never skipped"). Falls back to the
    Cached Fallback Schema on any SDK error, a malformed/unparseable
    response, a missing client (no GEMINI_API_KEY configured), or exceeding
    `timeout_s` (~3s per spec).
    """
    if client is None:
        logger.warning("No Gemini client configured; serving Cached Fallback Schema")
        return CACHED_FALLBACK_SCHEMA

    pool = ThreadPoolExecutor(max_workers=1)
    try:
        future = pool.submit(_call_gemini, client, image_bytes)
        try:
            return future.result(timeout=timeout_s)
        except FutureTimeoutError:
            logger.warning(
                "Gemini call exceeded %.1fs timeout; serving Cached Fallback Schema", timeout_s
            )
            return CACHED_FALLBACK_SCHEMA
        except (ValidationError, ValueError) as exc:
            logger.warning("Gemini response failed to parse (%s); serving Cached Fallback Schema", exc)
            return CACHED_FALLBACK_SCHEMA
        except Exception:
            logger.exception("Gemini call failed; serving Cached Fallback Schema")
            return CACHED_FALLBACK_SCHEMA
    finally:
        # Don't block the response path waiting for a hung call thread to
        # finish once we've already decided to fall back.
        pool.shutdown(wait=False)
