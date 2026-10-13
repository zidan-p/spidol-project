"""Tests for `draw_region_overlay` (docs/specs/0002-adjustable-tracking-
region.md, ticket 3): the pure pixel-drawing half of the Adjustable
Tracking Region setup flow's real-I/O wrapper. `pick_tracking_region`'s
actual interactive loop (`cv2.namedWindow`/`imshow`/`waitKey`/
`setMouseCallback`) is real OpenCV GUI I/O and, same as
`vision/debug_preview.py`'s `DebugPreviewTracker`, is not unit tested here
-- verified manually.
"""
import numpy as np

from vision.region_picker import draw_region_overlay
from vision.region_selector import Rect

FRAME_WIDTH = 640
FRAME_HEIGHT = 480


def _blank_frame():
    return np.zeros((FRAME_HEIGHT, FRAME_WIDTH, 3), dtype=np.uint8)


def test_draw_region_overlay_draws_the_rect_when_given_one():
    frame = _blank_frame()
    rect = Rect(x=50, y=50, width=200, height=150)

    annotated = draw_region_overlay(frame, rect)

    assert annotated.shape == frame.shape
    assert not np.array_equal(annotated, frame)


def test_draw_region_overlay_does_not_mutate_the_original_frame():
    frame = _blank_frame()
    original = frame.copy()
    rect = Rect(x=50, y=50, width=200, height=150)

    draw_region_overlay(frame, rect)

    assert np.array_equal(frame, original)


def test_draw_region_overlay_with_no_rect_returns_an_unmodified_copy():
    frame = _blank_frame()

    annotated = draw_region_overlay(frame, None)

    assert annotated.shape == frame.shape
    assert np.array_equal(annotated, frame)
    assert annotated is not frame
