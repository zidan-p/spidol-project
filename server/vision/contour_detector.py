"""ROI-selection helper for the AI Trigger (SPEC.md 3.2.D, GLOSSARY.md:
AI Trigger). This module is a pure selection aid only: it answers "where is
the last closed contour in this image?" so the trigger pipeline can narrow
its crop. It never decides whether to fire the AI pipeline -- that decision
belongs exclusively to the explicit AI Trigger event (ADR-0002) -- and it is
only ever consulted *after* a trigger has already happened.
"""
import cv2
import numpy as np


def find_last_closed_contour_bbox(binary_image: np.ndarray) -> dict | None:
    """Returns the bounding box of the last closed contour found in a
    single-channel (grayscale/binary) image, or None if no contour exists.

    Shape: {"x": int, "y": int, "width": int, "height": int} in pixel space,
    relative to `binary_image`'s own coordinate frame.
    """
    contours, _hierarchy = cv2.findContours(
        binary_image, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE
    )

    closed = [c for c in contours if cv2.contourArea(c) > 0 or len(c) >= 3]
    if not closed:
        return None

    x, y, w, h = cv2.boundingRect(closed[-1])
    return {"x": x, "y": y, "width": w, "height": h}
