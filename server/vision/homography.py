"""4-point homography calibration (SPEC 3.2.B).

Solves the optical distortion arising from arbitrary camera placement angles
by mapping camera-space coordinates onto canvas-space coordinates via
`cv2.findHomography` / `cv2.perspectiveTransform`.

Recomputation only ever happens through `recalibrate`, the Calibration
Hotkey's entry point (GLOSSARY: a manual, operator-triggered action -- there
is no automatic drift-detection logic in v1).
"""
from typing import Sequence

import cv2
import numpy as np

Point = tuple[float, float]


class HomographyCalibrator:
    """Maps camera-space points to canvas-space points via a 4-point homography."""

    def __init__(self):
        self._matrix: np.ndarray | None = None

    @property
    def is_calibrated(self) -> bool:
        return self._matrix is not None

    def calibrate(self, src_points: Sequence[Point], dst_points: Sequence[Point]) -> None:
        """Computes the homography matrix from 4 camera->canvas correspondences."""
        src = np.array(src_points, dtype=np.float32)
        dst = np.array(dst_points, dtype=np.float32)

        if src.shape != (4, 2) or dst.shape != (4, 2):
            raise ValueError(
                "Homography calibration requires exactly 4 correspondence points "
                f"each (got {len(src_points)} src, {len(dst_points)} dst)."
            )

        matrix, _ = cv2.findHomography(src, dst)
        if matrix is None:
            raise ValueError("cv2.findHomography failed to compute a matrix for the given points.")

        self._matrix = matrix

    def recalibrate(self, src_points: Sequence[Point], dst_points: Sequence[Point]) -> None:
        """Calibration Hotkey entry point: manually re-runs calibration with 4 new points.

        Operator-triggered only (e.g. bound to a keypress in the UI layer) --
        this method itself performs no automatic drift detection, it just
        recomputes the matrix from whatever fresh correspondences it's given.
        """
        self.calibrate(src_points, dst_points)

    def transform(self, point: Point) -> Point:
        """Maps a single camera-space point into canvas-space via the current matrix."""
        if self._matrix is None:
            raise RuntimeError("HomographyCalibrator.transform called before calibration.")

        src = np.array([[[point[0], point[1]]]], dtype=np.float32)
        dst = cv2.perspectiveTransform(src, self._matrix)
        x, y = dst[0, 0]
        return float(x), float(y)
