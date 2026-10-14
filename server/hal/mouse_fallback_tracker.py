"""Mouse-position fallback for any `BasePositionTracker` -- lets painting
work purely off a real mouse-down/up gesture (left click) even while the
camera tracker hasn't (or can't) detect the Pen Tip, instead of every
undetected frame reporting a meaningless, usually-(0, 0) position.

Mirrors `SmoothingPositionTracker`/`vision/debug_preview.py`'s "wrap and
stay transparent to callers" pattern. Deliberately still reports whatever
`is_detected` the wrapped tracker reported (never forces it to `True`) --
callers that *do* care about real detection (homography's camera-space
transform, `OsCursorController`'s real-OS-cursor movement) must keep
skipping on `is_detected=False` exactly as before; only the frontend's
ink-drawing path no longer gates on it (see `strokeBuffer.js`'s
`ingestTrackUpdate`), so substituting a real mouse position here is what
actually makes that difference visible as a drawable line instead of a
single dot stuck at the origin.
"""
from typing import Callable

from hal.interfaces import BasePositionTracker
from hal.trackers import _clamp, detect_screen_size


def _default_position_source() -> tuple[float, float]:
    from pynput.mouse import Controller

    return Controller().position


class MouseFallbackPositionTracker(BasePositionTracker):
    def __init__(
        self,
        inner: BasePositionTracker,
        position_source: Callable[[], tuple[float, float]] | None = None,
        screen_size: tuple[float, float] | None = None,
    ):
        self._inner = inner
        self._position_source = position_source or _default_position_source
        self._screen_size = screen_size or detect_screen_size()

    @property
    def inner(self):
        return self._inner

    @property
    def search_region(self):
        return self._inner.search_region

    def get_position(self, frame=None) -> tuple[float, float, bool]:
        x, y, is_detected = self._inner.get_position(frame)
        if is_detected:
            return x, y, is_detected

        raw_x, raw_y = self._position_source()
        width, height = self._screen_size
        fallback_x = _clamp(raw_x / width, 0.0, 1.0)
        fallback_y = _clamp(raw_y / height, 0.0, 1.0)
        return fallback_x, fallback_y, is_detected
