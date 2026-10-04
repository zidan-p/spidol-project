"""Tests for 4-point homography calibration (`vision/homography.py`).

SPEC 3.2.B: maps camera-space coordinates to canvas-space coordinates via
`cv2.findHomography` / `cv2.perspectiveTransform`, recomputed on demand by
the Calibration Hotkey (GLOSSARY: manual, operator-triggered -- never
automatic drift detection).
"""
import pytest

from vision.homography import HomographyCalibrator

# An oblique quadrilateral in camera-pixel space (arbitrary camera angle),
# correlating to the canvas's four corners in normalized [0, 1] space.
CAMERA_CORNERS = [(50, 40), (590, 10), (600, 460), (20, 430)]
CANVAS_CORNERS = [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)]


def test_calibrator_starts_uncalibrated():
    calibrator = HomographyCalibrator()
    assert calibrator.is_calibrated is False


def test_transform_before_calibration_raises():
    calibrator = HomographyCalibrator()
    with pytest.raises(RuntimeError):
        calibrator.transform((100, 100))


def test_calibrate_requires_exactly_four_point_correspondences():
    calibrator = HomographyCalibrator()
    with pytest.raises(ValueError):
        calibrator.calibrate(CAMERA_CORNERS[:3], CANVAS_CORNERS[:3])


def test_calibrate_maps_known_correspondence_points_back_to_their_target():
    calibrator = HomographyCalibrator()
    calibrator.calibrate(CAMERA_CORNERS, CANVAS_CORNERS)

    assert calibrator.is_calibrated is True
    for src, dst in zip(CAMERA_CORNERS, CANVAS_CORNERS):
        x, y = calibrator.transform(src)
        assert x == pytest.approx(dst[0], abs=1e-3)
        assert y == pytest.approx(dst[1], abs=1e-3)


def test_axis_aligned_rectangle_maps_center_proportionally():
    # Degenerate (non-perspective) case: an axis-aligned rectangle mapped to
    # the unit square is a pure affine scale, so the expected output for an
    # interior point can be derived independently by hand.
    calibrator = HomographyCalibrator()
    calibrator.calibrate(
        src_points=[(0, 0), (200, 0), (200, 100), (0, 100)],
        dst_points=[(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)],
    )

    x, y = calibrator.transform((100, 50))

    assert x == pytest.approx(0.5, abs=1e-6)
    assert y == pytest.approx(0.5, abs=1e-6)


def test_recalibrate_is_the_calibration_hotkey_entry_point_and_updates_mapping():
    calibrator = HomographyCalibrator()
    calibrator.calibrate(
        src_points=[(0, 0), (200, 0), (200, 100), (0, 100)],
        dst_points=[(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)],
    )
    before_x, before_y = calibrator.transform((100, 50))

    # Operator presses the Calibration Hotkey: rig was bumped/re-aimed, new
    # 4-point correspondence is captured and the matrix is recomputed.
    calibrator.recalibrate(
        src_points=[(0, 0), (400, 0), (400, 200), (0, 200)],
        dst_points=[(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)],
    )
    after_x, after_y = calibrator.transform((100, 50))

    assert (before_x, before_y) == pytest.approx((0.5, 0.5), abs=1e-6)
    assert (after_x, after_y) == pytest.approx((0.25, 0.25), abs=1e-6)
    assert (after_x, after_y) != pytest.approx((before_x, before_y))
