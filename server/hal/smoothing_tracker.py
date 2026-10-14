"""Jitter smoothing for any `BasePositionTracker` (dev request: `--tracker
optical-color` reported a visibly jittery position even when the physical
marker was held still). `OpticalColorTracker`'s centroid is inherently
noisy frame to frame -- lighting flicker, JPEG-ish compression artifacts,
blob-edge antialiasing -- even with no real movement at all.

`SmoothingPositionTracker` wraps any `BasePositionTracker`, mirroring
`vision/debug_preview.py`'s `DebugPreviewTracker` "wrap and stay
transparent to callers" pattern -- a cross-cutting concern that could
equally apply to a future tracker, not something specific to color
detection, so it lives as its own decorator rather than being baked into
`OpticalColorTracker` itself.
"""
from hal.interfaces import BasePositionTracker


class SmoothingPositionTracker(BasePositionTracker):
    """Applies an exponential moving average (EMA) to the wrapped
    tracker's `(x, y)`: `smoothed = alpha * raw + (1 - alpha) * previous`.
    Lower `alpha` means more smoothing (less jitter, more lag); higher
    `alpha` tracks the raw value more closely.

    Resets its smoothing state whenever tracking is lost
    (`is_detected=False`) or had never started -- so a lost-then-reacquired
    detection reports exactly where it is, the same as the very first
    detection ever would, rather than blending toward a stale prior
    position from before the gap.
    """

    def __init__(self, inner: BasePositionTracker, alpha: float = 0.3):
        self._inner = inner
        self._alpha = alpha
        self._smoothed_x: float | None = None
        self._smoothed_y: float | None = None

    @property
    def inner(self):
        return self._inner

    @property
    def search_region(self):
        # Forwards to the wrapped tracker (e.g. OpticalColorTracker) so
        # main.py's existing `tracker.search_region`/`tracker.inner.search_
        # region` access patterns keep working regardless of where in the
        # wrapper chain this sits.
        return self._inner.search_region

    def get_position(self, frame=None) -> tuple[float, float, bool]:
        raw_x, raw_y, is_detected = self._inner.get_position(frame)

        if not is_detected:
            self._smoothed_x = None
            self._smoothed_y = None
            return raw_x, raw_y, is_detected

        if self._smoothed_x is None:
            self._smoothed_x, self._smoothed_y = raw_x, raw_y
        else:
            self._smoothed_x = self._alpha * raw_x + (1 - self._alpha) * self._smoothed_x
            self._smoothed_y = self._alpha * raw_y + (1 - self._alpha) * self._smoothed_y

        return self._smoothed_x, self._smoothed_y, True
