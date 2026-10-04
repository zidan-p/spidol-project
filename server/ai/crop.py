"""Crops the AI Trigger Region (a normalized stroke bounding box, from
`ai/stroke_region.py`) out of a captured frame (`hal/image_source.py`), with
a small margin so stroke edges aren't clipped, and encodes the result for
the vision model call.
"""
import cv2
import numpy as np

from .stroke_region import Region

MARGIN = 0.03


def crop_region_from_frame(frame: np.ndarray, region: Region | None) -> np.ndarray:
    """Returns the sub-image of `frame` covering `region` (normalized
    [0..1] bbox), or the whole frame if no region is known yet (e.g. an AI
    Trigger fired with no strokes drawn).
    """
    height, width = frame.shape[:2]
    if region is None:
        return frame

    min_x = max(0.0, region.min_x - MARGIN)
    min_y = max(0.0, region.min_y - MARGIN)
    max_x = min(1.0, region.max_x + MARGIN)
    max_y = min(1.0, region.max_y + MARGIN)

    x0 = int(min_x * width)
    y0 = int(min_y * height)
    x1 = max(x0 + 1, int(max_x * width))
    y1 = max(y0 + 1, int(max_y * height))
    x1 = min(x1, width)
    y1 = min(y1, height)

    return frame[y0:y1, x0:x1]


def encode_png(image: np.ndarray) -> bytes:
    ok, buffer = cv2.imencode(".png", image)
    if not ok:
        raise ValueError("Failed to encode crop as PNG")
    return buffer.tobytes()
