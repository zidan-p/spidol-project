"""Orchestrates the full AI Trigger pipeline end-to-end (SPEC.md 3.2.D):

    1. Compute the AI Trigger Region (every stroke since the last trigger
       or clear) from the server-side `StrokeRegionTracker`.
    2. Crop that region out of the current frame (`CameraImageSource` in
       camera mode, `BlankCanvasImageSource` otherwise -- see
       hal/image_source.py).
    3. Call the vision model (with the Cached Fallback Schema on error/timeout).
    4. Dispatch AI_WIDGET_SPAWN / AI_WIDGET_UNSUPPORTED.

This module is what `server_app.py`'s WS message handler calls when it
receives the dev-mode `{"type": "AI_TRIGGER"}` message (see that module's
docstring for the trigger-hook mechanism decision).
"""
import itertools

from hal.image_source import BaseImageSource

from .crop import crop_region_from_frame, encode_png
from .dispatch import build_widget_message
from .vision_pipeline import DEFAULT_MODEL, DEFAULT_TIMEOUT_S, DUMMY_EMPTY_BOARD_SCHEMA, analyze_formula_crop
from .stroke_region import StrokeRegionTracker

_widget_id_counter = itertools.count(1)


def handle_ai_trigger(
    *,
    stroke_tracker: StrokeRegionTracker,
    image_source: BaseImageSource,
    vision_client,
    timeout_s: float = DEFAULT_TIMEOUT_S,
    model: str = DEFAULT_MODEL,
) -> str:
    """Runs one full AI Trigger cycle and returns the wire message (JSON
    string) to broadcast to clients.
    """
    region = stroke_tracker.region_since_last_trigger()
    # Mark the trigger boundary immediately, before the (potentially slow)
    # vision model call, so strokes drawn *during* that call start a fresh region
    # rather than being silently folded into this one.
    stroke_tracker.mark_trigger()

    widget_id = f"widget_{next(_widget_id_counter):02d}"

    if region is None:
        # Nothing has been drawn since the last trigger/clear -- an "Analyze
        # drawing" press here can't possibly be a real formula, so skip the
        # vision model call entirely (no crop, no image, no API tokens
        # spent) and serve a dummy function_graph widget instead.
        return build_widget_message(
            DUMMY_EMPTY_BOARD_SCHEMA, widget_id=widget_id, anchor_x=0.5, anchor_y=0.5
        )

    frame = image_source.capture_frame()
    crop = crop_region_from_frame(frame, region)
    image_bytes = encode_png(crop)

    analysis = analyze_formula_crop(image_bytes, vision_client, timeout_s=timeout_s, model=model)

    return build_widget_message(analysis, widget_id=widget_id, anchor_x=region.max_x, anchor_y=region.min_y)
