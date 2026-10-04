"""Tests for the camera-frame source stub (ticket 02 isn't built yet; see
`hal/image_source.py` docstring for the documented stand-in decision).
"""
import numpy as np

from hal.image_source import BaseImageSource, BlankCanvasImageSource, CameraImageSource


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


class _FakeVideoCapture:
    """Stands in for `cv2.VideoCapture` (ticket 02's real camera -- see
    docs/adr/0003: RemoteCam exposes itself as a standard UVC webcam, so a
    plain `cv2.VideoCapture(index)` is the real capture seam). Injected via
    `capture_factory`, mirroring `BleTouchProvider`'s `client_factory` seam,
    so this is exercised with no real camera/RemoteCam hardware required.
    """

    def __init__(self, index, frame=None):
        self.index = index
        self._frame = frame if frame is not None else np.zeros((480, 640, 3), dtype=np.uint8)
        self.released = False

    def read(self):
        return True, self._frame

    def release(self):
        self.released = True


def test_camera_image_source_is_a_base_image_source():
    source = CameraImageSource(camera_index=0, capture_factory=_FakeVideoCapture)
    assert isinstance(source, BaseImageSource)


def test_camera_image_source_opens_the_requested_camera_index():
    captured = {}

    def factory(index):
        captured["index"] = index
        return _FakeVideoCapture(index)

    CameraImageSource(camera_index=3, capture_factory=factory)

    assert captured["index"] == 3


def test_camera_image_source_returns_the_captured_frame():
    frame = np.full((480, 640, 3), 42, dtype=np.uint8)
    source = CameraImageSource(
        camera_index=0, capture_factory=lambda index: _FakeVideoCapture(index, frame=frame)
    )

    result = source.capture_frame()

    assert result is frame


def test_camera_image_source_falls_back_to_blank_frame_when_read_fails():
    class _FailingCapture(_FakeVideoCapture):
        def read(self):
            return False, None

    source = CameraImageSource(
        camera_index=0, capture_factory=lambda index: _FailingCapture(index)
    )

    frame = source.capture_frame()

    assert isinstance(frame, np.ndarray)
    assert frame.shape == (720, 1280, 3)
