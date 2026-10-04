"""Orchestrates the full AI Trigger pipeline end-to-end (SPEC.md 3.2.D):

    1. Compute the AI Trigger Region (every stroke since the last trigger
       or clear) from the server-side `StrokeRegionTracker`.
    2. Crop that region out of the current camera frame (today: the
       `BlankCanvasImageSource` stub -- see hal/image_source.py).
    3. Call Gemini (with the Cached Fallback Schema on error/timeout).
    4. Dispatch AI_WIDGET_SPAWN / AI_WIDGET_UNSUPPORTED.

This module is what `server_app.py`'s WS message handler calls when it
receives the dev-mode `{"type": "AI_TRIGGER"}` message (see that module's
docstring for the trigger-hook mechanism decision).
"""
import itertools

from hal.image_source import BaseImageSource

from .crop import crop_region_from_frame, encode_png
from .dispatch import build_widget_message
from .gemini_pipeline import DEFAULT_TIMEOUT_S, analyze_formula_crop
from .stroke_region import StrokeRegionTracker

_widget_id_counter = itertools.count(1)


def handle_ai_trigger(
    *,
    stroke_tracker: StrokeRegionTracker,
    image_source: BaseImageSource,
    gemini_client,
    timeout_s: float = DEFAULT_TIMEOUT_S,
) -> str:
    """Runs one full AI Trigger cycle and returns the wire message (JSON
    string) to broadcast to clients.
    """
    region = stroke_tracker.region_since_last_trigger()
    # Mark the trigger boundary immediately, before the (potentially slow)
    # Gemini call, so strokes drawn *during* that call start a fresh region
    # rather than being silently folded into this one.
    stroke_tracker.mark_trigger()

    frame = image_source.capture_frame()
    crop = crop_region_from_frame(frame, region)
    image_bytes = encode_png(crop)

    analysis = analyze_formula_crop(image_bytes, gemini_client, timeout_s=timeout_s)

    widget_id = f"widget_{next(_widget_id_counter):02d}"
    if region is not None:
        anchor_x = region.max_x
        anchor_y = region.min_y
    else:
        anchor_x, anchor_y = 0.5, 0.5

    return build_widget_message(analysis, widget_id=widget_id, anchor_x=anchor_x, anchor_y=anchor_y)
