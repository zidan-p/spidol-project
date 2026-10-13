"""Tests for the camera-frame source stub (ticket 02 isn't built yet; see
`hal/image_source.py` docstring for the documented stand-in decision).
"""
import cv2
import numpy as np

from hal.image_source import (
    BaseImageSource,
    BlankCanvasImageSource,
    BrowserCanvasImageSource,
    CameraImageSource,
    HttpCameraImageSource,
)


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


# HttpCameraImageSource (a phone running an "IP Webcam"-style app, streaming
# MJPEG over HTTP -- e.g. http://127.0.0.1:8081/video -- rather than a
# USB/UVC device). Reuses `_FakeVideoCapture` since `cv2.VideoCapture` opens
# both a device index and a stream URL through the same `read()`/`release()`
# interface -- only what's passed to `capture_factory` differs.


def test_http_camera_image_source_is_a_base_image_source():
    source = HttpCameraImageSource(url="http://127.0.0.1:8081/video", capture_factory=_FakeVideoCapture)
    assert isinstance(source, BaseImageSource)


def test_http_camera_image_source_opens_the_requested_url():
    captured = {}

    def factory(url):
        captured["url"] = url
        return _FakeVideoCapture(url)

    HttpCameraImageSource(url="http://127.0.0.1:8081/video", capture_factory=factory)

    assert captured["url"] == "http://127.0.0.1:8081/video"


def test_http_camera_image_source_returns_the_captured_frame():
    frame = np.full((480, 640, 3), 42, dtype=np.uint8)
    source = HttpCameraImageSource(
        url="http://127.0.0.1:8081/video",
        capture_factory=lambda url: _FakeVideoCapture(url, frame=frame),
    )

    result = source.capture_frame()

    assert result is frame


def test_http_camera_image_source_falls_back_to_blank_frame_when_read_fails():
    class _FailingCapture(_FakeVideoCapture):
        def read(self):
            return False, None

    source = HttpCameraImageSource(
        url="http://127.0.0.1:8081/video",
        capture_factory=lambda url: _FailingCapture(url),
    )

    frame = source.capture_frame()

    assert isinstance(frame, np.ndarray)
    assert frame.shape == (720, 1280, 3)


def test_browser_canvas_image_source_returns_blank_frame_before_any_snapshot():
    source = BrowserCanvasImageSource(width=640, height=480)

    frame = source.capture_frame()

    assert isinstance(frame, np.ndarray)
    assert frame.shape == (480, 640, 3)
    assert (frame == 255).all()


def test_browser_canvas_image_source_decodes_a_submitted_png_snapshot():
    source = BrowserCanvasImageSource()
    original = np.full((300, 400, 3), 17, dtype=np.uint8)
    ok, encoded = cv2.imencode(".png", original)
    assert ok

    source.set_frame_from_png_bytes(encoded.tobytes())
    frame = source.capture_frame()

    assert frame.shape == (300, 400, 3)
    assert (frame == 17).all()


def test_browser_canvas_image_source_ignores_corrupt_png_bytes():
    source = BrowserCanvasImageSource(width=10, height=10)

    source.set_frame_from_png_bytes(b"not a real png")
    frame = source.capture_frame()

    # Corrupt/undecodable bytes must not crash the AI Trigger crop -- falls
    # back to the last good frame (the initial blank one here).
    assert (frame == 255).all()
