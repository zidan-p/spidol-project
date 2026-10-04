"""Tests for the TRACK_UPDATE message builder: the pure-function seam between
the HAL (tracker + touch provider) and the wire format documented in SPEC.md
section 4.A.
"""
import json

from telemetry import build_track_update


def test_build_track_update_has_correct_type_and_device_id():
    message = build_track_update(
        device_id="spidol_main", x=0.482, y=0.315, is_touching=True, is_detected=True, fps=59.8
    )
    payload = json.loads(message)

    assert payload["type"] == "TRACK_UPDATE"
    assert payload["device_id"] == "spidol_main"


def test_build_track_update_carries_all_documented_fields():
    message = build_track_update(
        device_id="spidol_main", x=0.1, y=0.9, is_touching=False, is_detected=True, fps=60.0
    )
    payload = json.loads(message)

    assert payload == {
        "type": "TRACK_UPDATE",
        "device_id": "spidol_main",
        "x": 0.1,
        "y": 0.9,
        "is_touching": False,
        "is_detected": True,
        "fps": 60.0,
    }
