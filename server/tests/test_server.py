"""Integration test for the WebSocket broadcast seam: a real server, a real
client connection, asserting the TRACK_UPDATE contract documented in
SPEC.md section 4.A arrives over the wire at the advertised rate.
"""
import asyncio
import json

import pytest
import websockets

from server_app import create_server
from hal.trackers import SystemMouseFallbackTracker
from hal.providers import KeyboardMockProvider


async def _free_port() -> int:
    import socket

    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.mark.asyncio
async def test_client_receives_track_update_messages_matching_contract():
    port = await _free_port()
    tracker = SystemMouseFallbackTracker(position_source=lambda: (100, 50), screen_size=(1000, 1000))
    touch_provider = KeyboardMockProvider()

    async with create_server(tracker, touch_provider, host="127.0.0.1", port=port, fps=60):
        async with websockets.connect(f"ws://127.0.0.1:{port}") as client:
            raw = await asyncio.wait_for(client.recv(), timeout=1)
            payload = json.loads(raw)

    assert payload["type"] == "TRACK_UPDATE"
    assert payload["device_id"] == "spidol_main"
    assert payload["x"] == pytest.approx(0.1)
    assert payload["y"] == pytest.approx(0.05)
    assert payload["is_touching"] is False
    assert payload["is_detected"] is True
    assert isinstance(payload["fps"], (int, float))


@pytest.mark.asyncio
async def test_touch_provider_state_is_reflected_in_next_broadcast():
    port = await _free_port()
    tracker = SystemMouseFallbackTracker(position_source=lambda: (0, 0), screen_size=(1000, 1000))
    touch_provider = KeyboardMockProvider()
    touch_provider.set_touching(True)

    async with create_server(tracker, touch_provider, host="127.0.0.1", port=port, fps=60):
        async with websockets.connect(f"ws://127.0.0.1:{port}") as client:
            raw = await asyncio.wait_for(client.recv(), timeout=1)
            payload = json.loads(raw)

    assert payload["is_touching"] is True


@pytest.mark.asyncio
async def test_multiple_clients_all_receive_broadcasts():
    port = await _free_port()
    tracker = SystemMouseFallbackTracker(position_source=lambda: (0, 0), screen_size=(1000, 1000))
    touch_provider = KeyboardMockProvider()

    async with create_server(tracker, touch_provider, host="127.0.0.1", port=port, fps=60):
        async with websockets.connect(f"ws://127.0.0.1:{port}") as client_a, websockets.connect(
            f"ws://127.0.0.1:{port}"
        ) as client_b:
            raw_a = await asyncio.wait_for(client_a.recv(), timeout=1)
            raw_b = await asyncio.wait_for(client_b.recv(), timeout=1)

    assert json.loads(raw_a)["type"] == "TRACK_UPDATE"
    assert json.loads(raw_b)["type"] == "TRACK_UPDATE"
