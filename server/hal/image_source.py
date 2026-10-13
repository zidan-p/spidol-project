"""Camera-frame source abstraction (HAL, mirroring `BasePositionTracker` /
`BaseTouchProvider` in `hal/interfaces.py`).

Documented stub decision (ticket 04): ticket 02 (real `OpticalColorTracker` +
camera capture) wasn't built yet at the time, so there was no real camera
image to crop for the AI Trigger pipeline. `BlankCanvasImageSource` stood in,
returning a fixed blank (white) frame, and remains the default / mouse-dev-mode
fallback. `CameraImageSource` below is ticket 02's real camera-backed
implementation, wired in `main.py` as the one-line swap this docstring always
anticipated -- when `--tracker=optical-color` is selected, `main.py` passes a
`CameraImageSource` instead, so both the telemetry loop's tracker input and
the AI Trigger crop see a real frame. No change to the trigger pipeline
itself was needed; it was already written against `BaseImageSource`.
"""
from abc import ABC, abstractmethod

import numpy as np


class BaseImageSource(ABC):
    """Supplies the current camera frame (BGR, uint8) for the AI Trigger
    pipeline to crop."""

    @abstractmethod
    def capture_frame(self) -> np.ndarray:
        """Returns the current frame as an (height, width, 3) uint8 array."""


class BlankCanvasImageSource(BaseImageSource):
    """Stub `BaseImageSource`: always returns a fixed blank white canvas.
    See module docstring for why this exists instead of a real camera feed.
    """

    def __init__(self, width: int = 1280, height: int = 720):
        self._width = width
        self._height = height

    def capture_frame(self) -> np.ndarray:
        return np.full((self._height, self._width, 3), 255, dtype=np.uint8)


class CameraImageSource(BaseImageSource):
    """Real-camera `BaseImageSource` (ticket 02): wraps a video capture
    device -- RemoteCam (docs/adr/0003) exposes itself as a standard UVC
    webcam over USB, so a plain `cv2.VideoCapture(camera_index)` is the real
    capture seam, no RemoteCam-specific client needed.

    `capture_factory` defaults to `cv2.VideoCapture` but is a constructor
    parameter precisely so tests can inject a fake capture object (no real
    camera/RemoteCam hardware needed), mirroring `BleTouchProvider`'s
    `client_factory` seam in `hal/providers.py`.
    """

    def __init__(
        self,
        camera_index: int = 0,
        width: int = 1280,
        height: int = 720,
        capture_factory=None,
    ):
        if capture_factory is None:
            import cv2

            capture_factory = cv2.VideoCapture

        self._width = width
        self._height = height
        self._capture = capture_factory(camera_index)

    def capture_frame(self) -> np.ndarray:
        ok, frame = self._capture.read()
        if not ok or frame is None:
            # Camera hiccup (disconnected RemoteCam link, USB hiccup, etc.) --
            # fall back to a blank frame rather than raising, so one dropped
            # frame doesn't crash the telemetry loop or an AI Trigger crop.
            return np.full((self._height, self._width, 3), 255, dtype=np.uint8)
        return frame

    def release(self) -> None:
        self._capture.release()


class HttpCameraImageSource(BaseImageSource):
    """Real-camera `BaseImageSource` for a camera streamed over HTTP --
    e.g. a phone running an "IP Webcam"-style Android app, exposing an
    MJPEG stream at a URL like `http://127.0.0.1:8081/video` -- rather than
    a USB/UVC device (`CameraImageSource`'s `camera_index`). `cv2.VideoCapture`
    opens an MJPEG-over-HTTP URL the same way it opens a device index (same
    `read()`/`release()` interface via its FFMPEG backend), so this is
    structurally identical to `CameraImageSource`, just opened by URL.

    `capture_factory` defaults to `cv2.VideoCapture` but is a constructor
    parameter precisely so tests can inject a fake capture object (no real
    network camera needed), mirroring `CameraImageSource`'s own seam.
    """

    def __init__(
        self,
        url: str,
        width: int = 1280,
        height: int = 720,
        capture_factory=None,
    ):
        if capture_factory is None:
            import cv2

            capture_factory = cv2.VideoCapture

        self._width = width
        self._height = height
        self._capture = capture_factory(url)

    def capture_frame(self) -> np.ndarray:
        ok, frame = self._capture.read()
        if not ok or frame is None:
            # Stream hiccup (dropped WiFi, phone app backgrounded, etc.) --
            # fall back to a blank frame rather than raising, same as
            # CameraImageSource, so one dropped frame doesn't crash the
            # telemetry loop or an AI Trigger crop.
            return np.full((self._height, self._width, 3), 255, dtype=np.uint8)
        return frame

    def release(self) -> None:
        self._capture.release()


class BrowserCanvasImageSource(BaseImageSource):
    """`BaseImageSource` fed by the frontend's own canvas pixels over the
    WebSocket (`set_frame_from_png_bytes`, called from the server's
    `CANVAS_SNAPSHOT`/`AI_TRIGGER` message handling), rather than a physical
    camera.

    This is what lets the AI Trigger pipeline actually see what was drawn
    when testing in mouse-fallback dev mode (`--tracker=mouse`, no real
    camera wired) -- without it, `BlankCanvasImageSource`'s fixed blank frame
    meant the AI Trigger Region crop was always empty, so the live vision
    model call could never recognize anything actually drawn on the canvas,
    only ever exercising the Cached Fallback Schema path. Camera mode
    (`--tracker=optical-color`) still uses `CameraImageSource` instead; this
    class is the mouse-mode counterpart.
    """

    def __init__(self, width: int = 1280, height: int = 720):
        self._width = width
        self._height = height
        self._frame = np.full((height, width, 3), 255, dtype=np.uint8)

    def set_frame_from_png_bytes(self, png_bytes: bytes) -> None:
        import cv2

        array = np.frombuffer(png_bytes, dtype=np.uint8)
        decoded = cv2.imdecode(array, cv2.IMREAD_COLOR)
        if decoded is not None:
            self._frame = decoded

    def capture_frame(self) -> np.ndarray:
        return self._frame
