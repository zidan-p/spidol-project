"""Formula crop -> vision model -> Simulation Type + params (SPEC.md
3.2.D, `ai/vision_pipeline.py`).

Provider-agnostic by design: talks to any OpenAI-compatible chat-completions
endpoint (`client.chat.completions.create(...)`), not a provider-specific
SDK. This is what lets the same code point at Gemini's own OpenAI-compatible
endpoint, OpenRouter, a local router/proxy, or any other OpenAI-compatible
provider -- only `base_url`/`api_key`/`model` change, never this module.

Structured output uses the loose `response_format={"type": "json_object"}`
mode, not `{"type": "json_schema", ...}` -- deliberately. Strict json_schema
mode is not reliably honored across OpenAI-compatible routers/proxies in
practice (observed: a local router silently ignored it and returned prose
instead of JSON); `json_object` mode is far more broadly supported, at the
cost of only guaranteeing valid JSON syntax, not the specific field shape --
so `PROMPT_TEXT` spells out the exact required JSON shape in the prompt
itself, and `_strip_markdown_fence` below handles the common case of a model
wrapping its JSON in a ```json ... ``` code fence despite being asked not to
(also observed against the same router).

Default endpoint/model (used when no override is configured): Gemini's
OpenAI-compatible endpoint (`DEFAULT_BASE_URL`) with `DEFAULT_MODEL`. Per the
implementation research notes (section 5), the real current Flash-Lite model
as of this writing is `gemini-3.1-flash-lite`, not `gemini-1.5-flash`
(retired) and not `gemini-3.5-flash-lite` (doesn't exist) -- re-verify at
deploy time if this drifts again, the model family churns every few months.
To route through OpenRouter, a local router, or another OpenAI-compatible
provider instead, override `base_url`/`model` (see `main.py`'s
`AI_BASE_URL`/`AI_MODEL` env vars) and set the matching API key.
"""
import base64
import logging
import re
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from enum import Enum

from pydantic import BaseModel, ValidationError

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"
DEFAULT_MODEL = "gemini-3.1-flash-lite"
DEFAULT_TIMEOUT_S = 3.0

_MARKDOWN_FENCE_RE = re.compile(r"^```(?:json)?\s*(.*?)\s*```$", re.DOTALL)

PROMPT_TEXT = (
    "Extract the handwritten physics/math formula in this image. "
    "Classify it as one of: spring_mass, pendulum, projectile (real "
    "time-evolving physics simulations) -- or, for ANY other math formula, "
    "classify it as function_graph. For function_graph you must then pick "
    "ONE of two mutually-exclusive representations, choosing based on "
    "whether the relationship passes the vertical-line test (each x has "
    "at most one y):\n"
    "(1) EXPLICIT -- if it's a genuine single-variable function y = f(x) "
    "(linear, quadratic, cubic, trigonometric, exponential, logarithmic, "
    "rational, etc.): return an \"expression\" field, a single-variable "
    "algebraic expression SOLVED FOR y, in terms of x and your chosen "
    "parameter keys. If the handwritten formula is implicit or not "
    'already isolated for y (e.g. "2y = 3x", "ax + by = c"), '
    "algebraically rearrange it into explicit y = ... form first -- never "
    "return an expression in terms of the original un-isolated "
    "coefficients. Use conventional names for the parameters of the "
    'SOLVED form: linear -> "expression": "m*x + b" with parameters '
    'keyed "m" (slope), "b" (intercept); quadratic -> "expression": '
    '"a*x^2 + b*x + c" with parameters keyed "a", "b", "c". Leave '
    '"parametric_x"/"parametric_y" null.\n'
    "(2) PARAMETRIC -- if it FAILS the vertical-line test (a circle, "
    "ellipse, or any other closed/implicit curve where some x has two or "
    "more y values -- e.g. x^2 + y^2 = r^2 is NOT a function and must "
    'NEVER be forced into "expression" form, which can only ever draw '
    "half of it): instead return \"parametric_x\" and \"parametric_y\", "
    "two mathjs expressions in terms of a parameter t (conventionally "
    'ranging over [0, 2*pi]) that trace the FULL curve, e.g. a circle '
    'of radius r -> "parametric_x": "r*cos(t)", "parametric_y": '
    '"r*sin(t)", with a single parameter keyed "r". Leave "expression" '
    "null in this case.\n\n"
    "Either way, written in standard math notation parseable by mathjs "
    "(operators + - * / ^, functions like sin cos tan sqrt abs exp log, "
    "constants pi e). Return the formula's LaTeX (showing the ORIGINAL "
    "handwritten form, not any rearranged one), a short concept title, "
    "and reasonable adjustable parameters with min/max/default values "
    "for every constant that appears (x and t are never parameters -- "
    "they're sliders the UI already provides).\n\n"
    "DEFINITE INTEGRAL -- if, and only if, the handwritten formula is an "
    'explicit definite integral with numeric bounds (e.g. "\\int_{0}^{1} '
    '(2x+1)\\,dx"): use the EXPLICIT representation above for the '
    'integrand (e.g. "expression": "2*x + 1"), and additionally return '
    '"integral_lower" and "integral_upper" as the two numeric bounds '
    "(e.g. 0 and 1). Leave both null for every other formula, including "
    "an explicit function with no integral notation at all -- never "
    "invent bounds that weren't actually drawn.\n\n"
    "Respond with ONLY a single JSON object (no prose, no markdown code "
    "fence), matching exactly this shape:\n"
    '{"formula_latex": "<latex string>", "concept_title": "<short title>", '
    '"simulation_type": "<snake_case label>", '
    '"expression": "<mathjs expression, or null>", '
    '"parametric_x": "<mathjs expression, or null>", '
    '"parametric_y": "<mathjs expression, or null>", '
    '"integral_lower": <number, or null>, '
    '"integral_upper": <number, or null>, '
    '"parameters": [{"key": "<param key>", "label": "<display label>", '
    '"min": <number>, "max": <number>, "val": <number>}, ...]}'
)


def _strip_markdown_fence(content: str) -> str:
    """Strips a ```json ... ``` (or bare ``` ... ```) wrapper some models
    add around JSON output despite being asked not to -- a no-op if `content`
    isn't fenced.
    """
    match = _MARKDOWN_FENCE_RE.match(content.strip())
    return match.group(1) if match else content


class SimulationType(str, Enum):
    """The fixed, hand-built Simulation Type enum (GLOSSARY.md: Simulation
    Type). Used for validation in application code, not as the Pydantic
    field type on `FormulaAnalysis.simulation_type` -- see that class's
    docstring for why.
    """

    SPRING_MASS = "spring_mass"
    PENDULUM = "pendulum"
    PROJECTILE = "projectile"
    # Generic: any single-variable y = f(x) math function (linear,
    # quadratic, cubic, trig, exponential, ...), not a fixed per-formula
    # renderer -- see FormulaAnalysis.expression and
    # view/src/components/SimulationWidget.jsx's FunctionGraphWidget, which
    # evaluates it via mathjs rather than a hand-written RK4 integrator
    # (there's no ODE here, just algebra). docs/adr/0006 records why this
    # one type is generative where the other three deliberately aren't.
    FUNCTION_GRAPH = "function_graph"


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
    # Deliberately `str`, not `SimulationType`: the JSON schema constrains
    # shape/types but typing this as the Enum would make the schema layer
    # reject (or coerce) an out-of-enum value before it ever reaches
    # application code. Ticket 04 instead wants an unrecognized value to
    # parse successfully and be routed to AI_WIDGET_UNSUPPORTED -- so the
    # enum check happens explicitly, after parsing, via
    # `is_supported_simulation_type`.
    simulation_type: str
    # Only meaningful (non-None) for simulation_type == "function_graph": a
    # mathjs-parseable expression in terms of `x` and the returned
    # `parameters` keys. None for spring_mass/pendulum/projectile, whose
    # behavior is fully determined by their hand-written RK4 integrators
    # and don't have (or need) an algebraic expression. Also None (in
    # favor of parametric_x/parametric_y) for function_graph curves that
    # aren't functions of x -- a circle fails the vertical-line test, so
    # it can never be a single `expression`; see those fields below.
    expression: str | None = None
    # Mutually exclusive with `expression`: for a function_graph curve
    # that isn't a function of x (circle, ellipse, and other closed/
    # implicit curves), the AI instead returns a parametric form -- two
    # mathjs expressions in terms of a parameter `t` (conventionally
    # ranging over [0, 2*pi]), e.g. a circle of radius r becomes
    # parametric_x="r*cos(t)", parametric_y="r*sin(t)".
    parametric_x: str | None = None
    parametric_y: str | None = None
    # Set (both, or neither -- never just one) when the handwritten formula
    # is an explicit DEFINITE integral with numeric bounds (e.g.
    # "\int_{0}^{1} (2x+1) dx"): `expression` is still the integrand
    # ("2*x + 1"), solved/simplified the same way as any other explicit
    # function_graph; these two carry the integral's lower/upper bounds so
    # the frontend can shade the area under the curve and compute its
    # numeric value, instead of just plotting the integrand as a plain
    # line with no indication an integral was asked for at all. None for
    # every other formula, including an explicit function with no integral
    # notation.
    integral_lower: float | None = None
    integral_upper: float | None = None
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
known competition demo formula, served if the live model call errors or
times out, so a dropped venue connection never visibly breaks the live run.
"""


def make_live_client(api_key: str | None = None, base_url: str = DEFAULT_BASE_URL):
    """Constructs a real OpenAI-compatible client pointed at `base_url`
    (defaults to Gemini's own OpenAI-compatible endpoint; pass OpenRouter's
    `https://openrouter.ai/api/v1` or any other OpenAI-compatible endpoint
    instead to switch providers). Imported lazily so modules/tests that only
    exercise the fake-client path never need the SDK importable to succeed.
    """
    from openai import OpenAI

    return OpenAI(api_key=api_key, base_url=base_url)


def _image_data_url(image_bytes: bytes) -> str:
    return f"data:image/png;base64,{base64.b64encode(image_bytes).decode('ascii')}"


def _call_model(client, image_bytes: bytes, model: str) -> FormulaAnalysis:
    response = client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": PROMPT_TEXT},
                    {"type": "image_url", "image_url": {"url": _image_data_url(image_bytes)}},
                ],
            }
        ],
        response_format={"type": "json_object"},
    )
    content = response.choices[0].message.content
    return FormulaAnalysis.model_validate_json(_strip_markdown_fence(content))


def analyze_formula_crop(
    image_bytes: bytes,
    client,
    timeout_s: float = DEFAULT_TIMEOUT_S,
    model: str = DEFAULT_MODEL,
) -> FormulaAnalysis:
    """Always attempts the live model call first (SPEC.md 3.2.D: "the real
    API call is always attempted first, never skipped"). Falls back to the
    Cached Fallback Schema on any SDK error, a malformed/unparseable
    response, a missing client (no API key configured), or exceeding
    `timeout_s` (~3s per spec).
    """
    if client is None:
        logger.warning("No vision model client configured; serving Cached Fallback Schema")
        return CACHED_FALLBACK_SCHEMA

    pool = ThreadPoolExecutor(max_workers=1)
    try:
        future = pool.submit(_call_model, client, image_bytes, model)
        try:
            return future.result(timeout=timeout_s)
        except FutureTimeoutError:
            logger.warning(
                "Vision model call exceeded %.1fs timeout; serving Cached Fallback Schema", timeout_s
            )
            return CACHED_FALLBACK_SCHEMA
        except (ValidationError, ValueError) as exc:
            logger.warning("Vision model response failed to parse (%s); serving Cached Fallback Schema", exc)
            return CACHED_FALLBACK_SCHEMA
        except Exception:
            logger.exception("Vision model call failed; serving Cached Fallback Schema")
            return CACHED_FALLBACK_SCHEMA
    finally:
        # Don't block the response path waiting for a hung call thread to
        # finish once we've already decided to fall back.
        pool.shutdown(wait=False)
