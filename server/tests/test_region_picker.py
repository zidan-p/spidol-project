"""Tests for `draw_region_overlay` (docs/specs/0002-adjustable-tracking-
region.md): the pure pixel-drawing half of the Adjustable Tracking Region
setup flow's real-I/O wrapper. `pick_tracking_region`'s actual interactive
loop (`cv2.namedWindow`/`imshow`/`waitKey`/`setMouseCallback`) is real
OpenCV GUI I/O and, same as `vision/debug_preview.py`'s
`DebugPreviewTracker`, is not unit tested here -- verified manually.
"""
import numpy as np

from vision.region_picker import draw_region_overlay
from vision.region_selector import Point

FRAME_WIDTH = 640
FRAME_HEIGHT = 480


def _blank_frame():
    return np.zeros((FRAME_HEIGHT, FRAME_WIDTH, 3), dtype=np.uint8)


def _frame_corners():
    return (
        Point(0, 0),
        Point(FRAME_WIDTH - 1, 0),
        Point(FRAME_WIDTH - 1, FRAME_HEIGHT - 1),
        Point(0, FRAME_HEIGHT - 1),
    )


def test_draw_region_overlay_draws_the_quad():
    frame = _blank_frame()

    annotated = draw_region_overlay(frame, _frame_corners())

    assert annotated.shape == frame.shape
    assert not np.array_equal(annotated, frame)


def test_draw_region_overlay_does_not_mutate_the_original_frame():
    frame = _blank_frame()
    original = frame.copy()

    draw_region_overlay(frame, _frame_corners())

    assert np.array_equal(frame, original)


def test_draw_region_overlay_draws_a_non_rectangular_quad_too():
    frame = _blank_frame()
    trapezoid = (Point(200, 50), Point(400, 50), Point(500, 400), Point(100, 400))

    annotated = draw_region_overlay(frame, trapezoid)

    assert annotated.shape == frame.shape
    assert not np.array_equal(annotated, frame)
