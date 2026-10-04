"""Builds the TRACK_UPDATE wire message (SPEC.md section 4.A) from HAL output.

Kept as a pure function so the WebSocket broadcast loop, the HAL, and the
wire-format serialization are three independently testable concerns.
"""
import json


def build_track_update(
    *, device_id: str, x: float, y: float, is_touching: bool, is_detected: bool, fps: float
) -> str:
    return json.dumps(
        {
            "type": "TRACK_UPDATE",
            "device_id": device_id,
            "x": x,
            "y": y,
            "is_touching": is_touching,
            "is_detected": is_detected,
            "fps": fps,
        }
    )
