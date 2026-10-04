"""Camera-frame source abstraction (HAL, mirroring `BasePositionTracker` /
`BaseTouchProvider` in `hal/interfaces.py`).

Documented stub decision (ticket 04): ticket 02 (real `OpticalColorTracker` +
camera capture) isn't built yet, so there is no real camera image to crop
for the AI Trigger pipeline. Rather than block this ticket on that one,
`BlankCanvasImageSource` stands in, returning a fixed blank (white) frame.
The AI trigger pipeline (`ai/trigger.py`) is written against the
`BaseImageSource` ABC, exactly like the existing tracker/touch-provider
seams, so ticket 02 supplies a real camera-backed implementation later as a
one-line swap in `main.py` -- no change to the trigger pipeline itself. The
tradeoff this accepts: Gemini will "see" a blank crop until ticket 02 lands,
so the live call will not usefully transcribe a real formula until then;
the Cached Fallback Schema path is what actually demos correctly until a
real camera source exists (see also ai/gemini_pipeline.py).
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
