"""Tests for the camera-frame source stub (ticket 02 isn't built yet; see
`hal/image_source.py` docstring for the documented stand-in decision).
"""
import numpy as np

from hal.image_source import BlankCanvasImageSource


def test_blank_canvas_image_source_returns_frame_of_requested_size():
    source = BlankCanvasImageSource(width=640, height=480)

    frame = source.capture_frame()

    assert isinstance(frame, np.ndarray)
    assert frame.shape == (480, 640, 3)
    assert frame.dtype == np.uint8


def test_blank_canvas_image_source_is_blank_white():
    source = BlankCanvasImageSource(width=10, height=10)

    frame = source.capture_frame()

    assert (frame == 255).all()
