"""Tests for cropping the AI Trigger Region out of a captured frame, and
encoding the crop for the vision model call.
"""
import numpy as np

from ai.crop import crop_region_from_frame, encode_png
from ai.stroke_region import Region


def test_crop_with_no_region_returns_whole_frame():
    frame = np.zeros((100, 200, 3), dtype=np.uint8)

    crop = crop_region_from_frame(frame, None)

    assert crop.shape == frame.shape


def test_crop_extracts_normalized_bbox_in_pixel_space():
    frame = np.zeros((100, 200, 3), dtype=np.uint8)
    region = Region(min_x=0.25, max_x=0.5, min_y=0.2, max_y=0.6, stroke_ids=(1,))

    crop = crop_region_from_frame(frame, region)

    # width = 200, region spans [0.25,0.5] -> ~50px wide (plus margin);
    # height = 100, region spans [0.2,0.6] -> ~40px tall (plus margin).
    assert 40 <= crop.shape[1] <= 70
    assert 30 <= crop.shape[0] <= 60


def test_crop_clamps_to_frame_bounds_near_edges():
    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    region = Region(min_x=0.0, max_x=0.02, min_y=0.0, max_y=0.02, stroke_ids=(1,))

    crop = crop_region_from_frame(frame, region)

    assert crop.shape[0] >= 1
    assert crop.shape[1] >= 1
    assert crop.shape[0] <= 100
    assert crop.shape[1] <= 100


def test_encode_png_round_trips_to_nonempty_bytes():
    frame = np.full((20, 20, 3), 128, dtype=np.uint8)

    encoded = encode_png(frame)

    assert isinstance(encoded, bytes)
    assert len(encoded) > 0
    assert encoded[:8] == b"\x89PNG\r\n\x1a\n"
