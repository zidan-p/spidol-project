"""Tests for the camera debug-preview overlay (dev-only aid for verifying
`OpticalColorTracker` detection before hardware is fully wired -- see
`main.py --debug-camera`). `draw_debug_overlay` is pure (just pixel
drawing) and fully tested here; `DebugPreviewTracker`'s actual `cv2.imshow`
window is a thin, untestable GUI side effect, injected as `show_frame` so
tests never need a real display (same pattern as `BleTouchProvider`'s
`client_factory` / `CameraImageSource`'s `capture_factory`).
"""
import numpy as np

from vision.debug_preview import DebugPreviewTracker, draw_debug_overlay


class _FakeTracker:
    def __init__(self, result):
        self._result = result
        self.received_frames = []

    def get_position(self, frame):
        self.received_frames.append(frame)
        return self._result


def test_draw_debug_overlay_marks_the_detected_position():
    frame = np.zeros((480, 640, 3), dtype=np.uint8)

    annotated = draw_debug_overlay(frame, x=0.5, y=0.5, is_detected=True)

    assert annotated.shape == frame.shape
    # Something was actually drawn -- the overlay must not be a no-op.
    assert not np.array_equal(annotated, frame)


def test_draw_debug_overlay_does_not_mutate_the_original_frame():
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    original = frame.copy()

    draw_debug_overlay(frame, x=0.5, y=0.5, is_detected=True)

    assert np.array_equal(frame, original)


def test_draw_debug_overlay_handles_not_detected_without_crashing():
    frame = np.zeros((480, 640, 3), dtype=np.uint8)

    annotated = draw_debug_overlay(frame, x=0.0, y=0.0, is_detected=False)

    assert annotated.shape == frame.shape


def test_debug_preview_tracker_delegates_to_the_inner_tracker():
    inner = _FakeTracker((0.25, 0.75, True))
    shown = []
    tracker = DebugPreviewTracker(inner, show_frame=lambda name, frame: shown.append((name, frame)))

    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    result = tracker.get_position(frame)

    assert result == (0.25, 0.75, True)
    assert inner.received_frames == [frame]


def test_debug_preview_tracker_shows_an_annotated_frame_each_call():
    inner = _FakeTracker((0.1, 0.2, True))
    shown = []
    tracker = DebugPreviewTracker(inner, show_frame=lambda name, frame: shown.append((name, frame)))

    frame = np.zeros((10, 10, 3), dtype=np.uint8)
    tracker.get_position(frame)

    assert len(shown) == 1
    window_name, annotated = shown[0]
    assert isinstance(window_name, str) and window_name
    assert annotated.shape == frame.shape
    assert not np.array_equal(annotated, frame)


def test_debug_preview_tracker_exposes_the_wrapped_tracker_via_inner():
    inner = _FakeTracker((0.0, 0.0, False))
    tracker = DebugPreviewTracker(inner, show_frame=lambda name, frame: None)

    assert tracker.inner is inner


def test_debug_preview_tracker_handles_a_none_frame_without_crashing():
    inner = _FakeTracker((0.0, 0.0, False))
    shown = []
    tracker = DebugPreviewTracker(inner, show_frame=lambda name, frame: shown.append((name, frame)))

    result = tracker.get_position(None)

    assert result == (0.0, 0.0, False)
    assert shown == []
