"""Position-tracker drivers.

v1 ships `SystemMouseFallbackTracker` only. `OpticalColorTracker` (camera/
color-blob based) is a later ticket's concern and slots in here as a sibling
class implementing the same `BasePositionTracker` ABC.
"""
from typing import Callable

from hal.interfaces import BasePositionTracker


def _default_position_source() -> tuple[int, int]:
    # Imported lazily so environments without a display (CI, headless
    # servers) can still import this module without pynput touching X11/Win32.
    from pynput.mouse import Controller

    controller = Controller()
    return controller.position


class SystemMouseFallbackTracker(BasePositionTracker):
    """Reports the real OS mouse cursor position, normalized to [0, 1].

    Used as the input source for ticket 01's mouse-driven tracer bullet, and
    as a no-camera-required fallback/dev mode going forward.
    """

    def __init__(
        self,
        position_source: Callable[[], tuple[float, float]] | None = None,
        screen_size: tuple[float, float] | None = None,
    ):
        self._position_source = position_source or _default_position_source
        self._screen_size = screen_size or self._detect_screen_size()

    @staticmethod
    def _detect_screen_size() -> tuple[float, float]:
        from pynput.mouse import Controller as _Unused  # noqa: F401 -- ensures pynput import errors surface early
        import ctypes

        try:
            user32 = ctypes.windll.user32
            return (user32.GetSystemMetrics(0), user32.GetSystemMetrics(1))
        except AttributeError:
            # Non-Windows fallback: a reasonable default; real multi-platform
            # screen-size detection is out of scope for this tracer bullet.
            return (1920, 1080)

    def get_position(self, frame=None) -> tuple[float, float, bool]:
        raw_x, raw_y = self._position_source()
        width, height = self._screen_size

        x = _clamp(raw_x / width, 0.0, 1.0)
        y = _clamp(raw_y / height, 0.0, 1.0)

        return x, y, True


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))
