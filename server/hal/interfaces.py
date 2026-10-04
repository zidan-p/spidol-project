"""Hardware Abstraction Layer contracts (Open-Closed Principle).

Every position-tracking or touch-sensing driver -- mouse-based today,
camera/BLE-based in later tickets -- implements one of these ABCs. Callers
(the telemetry loop in main.py) depend only on these interfaces, never on a
concrete driver class, so new drivers slot in without touching the loop.
"""
from abc import ABC, abstractmethod

import numpy as np


class BasePositionTracker(ABC):
    """Reports the Pen Tip's on-screen position as normalized coordinates."""

    @abstractmethod
    def get_position(self, frame: np.ndarray | None) -> tuple[float, float, bool]:
        """Returns normalized (x [0..1], y [0..1], is_detected).

        `frame` is the current camera frame for vision-based trackers; mouse-
        based trackers ignore it (accepted for interface symmetry so the
        telemetry loop can call every tracker the same way).
        """


class BaseTouchProvider(ABC):
    """Reports whether the Tip Contact Switch is currently pressed."""

    @abstractmethod
    def is_touching(self) -> bool:
        """Returns True if the Tip Contact Switch is currently pressed."""
