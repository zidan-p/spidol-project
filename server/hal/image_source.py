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
import threading
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

    `flip_horizontal` mirrors every captured frame left-right -- a PC
    webcam typically faces the user directly (unlike the rig's intended
    overhead/angled observer camera), so a raw frame moves opposite to the
    user's real-world left/right, like a security camera rather than a
    mirror. Defaults to `False` (the rig's normal camera placement needs no
    correction).
    """

    def __init__(
        self,
        camera_index: int = 0,
        width: int = 1280,
        height: int = 720,
        capture_factory=None,
        flip_horizontal: bool = False,
    ):
        if capture_factory is None:
            import cv2

            capture_factory = cv2.VideoCapture

        self._width = width
        self._height = height
        self._flip_horizontal = flip_horizontal
        self._capture = capture_factory(camera_index)

    @property
    def flip_horizontal(self) -> bool:
        return self._flip_horizontal

    def capture_frame(self) -> np.ndarray:
        ok, frame = self._capture.read()
        if not ok or frame is None:
            # Camera hiccup (disconnected RemoteCam link, USB hiccup, etc.) --
            # fall back to a blank frame rather than raising, so one dropped
            # frame doesn't crash the telemetry loop or an AI Trigger crop.
            return np.full((self._height, self._width, 3), 255, dtype=np.uint8)
        if self._flip_horizontal:
            frame = frame[:, ::-1, :]
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
    structurally similar to `CameraImageSource`, just opened by URL -- but
    with one deliberate difference, see below.

    A background thread continuously drains `read()` as fast as the stream
    delivers frames and keeps only the most recently read one. Without
    this, `capture_frame()` calling `read()` directly, once per telemetry
    tick, hits a well-known `cv2.VideoCapture` + network-stream gotcha: each
    individual `read()` call is fast, but if the stream produces frames
    faster than the tick rate drains them, a backlog queues up internally
    and `read()` returns the *oldest* unread frame, not the newest -- so the
    displayed/tracked video lags further and further behind real time, even
    though every call itself measures as fast. A local USB/UVC device
    (`CameraImageSource`) doesn't typically buffer this way, so it's kept
    simpler; this class exists specifically because a phone's network
    stream does.

    `capture_factory` defaults to `cv2.VideoCapture` but is a constructor
    parameter precisely so tests can inject a fake capture object (no real
    network camera needed), mirroring `CameraImageSource`'s own seam.
    `start_reader_thread` defaults to `True` for real use; tests pass
    `False` to drive `_read_once()` directly and deterministically instead.
    """

    def __init__(
        self,
        url: str,
        width: int = 1280,
        height: int = 720,
        capture_factory=None,
        start_reader_thread: bool = True,
    ):
        if capture_factory is None:
            import cv2

            capture_factory = cv2.VideoCapture

        self._width = width
        self._height = height
        self._capture = capture_factory(url)

        self._lock = threading.Lock()
        self._latest_frame: np.ndarray | None = None
        self._stop = threading.Event()
        self._reader_thread: threading.Thread | None = None
        if start_reader_thread:
            self._reader_thread = threading.Thread(target=self._reader_loop, daemon=True)
            self._reader_thread.start()

    def _read_once(self) -> bool:
        """Reads one frame and stores it as the latest if successful;
        returns whether a frame was captured. Exposed separately from
        `_reader_loop` so tests can drive it directly, with no real
        threading involved.
        """
        ok, frame = self._capture.read()
        if ok and frame is not None:
            with self._lock:
                self._latest_frame = frame
            return True
        return False

    def _reader_loop(self) -> None:
        while not self._stop.is_set():
            if not self._read_once():
                # Back off on a failed read (stream hiccup, dropped WiFi)
                # instead of busy-retrying at full speed.
                self._stop.wait(0.01)

    def capture_frame(self) -> np.ndarray:
        with self._lock:
            frame = self._latest_frame
        if frame is None:
            # No frame read yet (or every read so far has failed) -- fall
            # back to a blank frame rather than raising, same as
            # CameraImageSource, so this never crashes the telemetry loop
            # or an AI Trigger crop.
            return np.full((self._height, self._width, 3), 255, dtype=np.uint8)
        return frame

    def release(self) -> None:
        self._stop.set()
        if self._reader_thread is not None:
            self._reader_thread.join(timeout=1.0)
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
