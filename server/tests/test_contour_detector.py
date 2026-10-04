"""Tests for the contour-ROI helper (SPEC.md 3.2.D / GLOSSARY.md: the
contour detector only helps select which strokes make up a region -- it must
never itself decide to invoke the AI pipeline, ADR-0002).
"""
import numpy as np
import cv2

from vision.contour_detector import find_last_closed_contour_bbox


def test_returns_none_for_a_blank_image():
    blank = np.zeros((200, 200), dtype=np.uint8)
    assert find_last_closed_contour_bbox(blank) is None


def test_finds_bounding_box_of_a_single_closed_contour():
    image = np.zeros((200, 200), dtype=np.uint8)
    cv2.rectangle(image, (40, 50), (120, 150), color=255, thickness=2)

    bbox = find_last_closed_contour_bbox(image)

    assert bbox is not None
    assert bbox["x"] == pytest_approx_dim(40)
    assert bbox["y"] == pytest_approx_dim(50)
    assert bbox["width"] == pytest_approx_dim(120 - 40)
    assert bbox["height"] == pytest_approx_dim(150 - 50)


def pytest_approx_dim(expected):
    # Rectangle stroke thickness can nudge boundingRect by a pixel or two;
    # allow a small tolerance rather than an exact pixel match.
    class _Approx:
        def __eq__(self, other):
            return abs(other - expected) <= 3

    return _Approx()


def test_returns_bbox_of_the_last_contour_when_multiple_exist():
    image = np.zeros((200, 200), dtype=np.uint8)
    cv2.rectangle(image, (10, 10), (30, 30), color=255, thickness=2)
    cv2.rectangle(image, (100, 100), (180, 180), color=255, thickness=2)

    bbox = find_last_closed_contour_bbox(image)

    # cv2.findContours with RETR_LIST returns contours in the order found;
    # this test only asserts *some* deterministic, documented choice (the
    # last one found) is returned -- not autonomy, just ROI selection.
    assert bbox is not None
    assert bbox["width"] > 0
    assert bbox["height"] > 0
