"""Integration test for the dev-mode AI Trigger hook over the WebSocket
connection (ticket 04): a client sends `{"type": "AI_TRIGGER"}`, and every
connected client receives the resulting AI_WIDGET_SPAWN broadcast. This is
the chosen trigger-hook mechanism -- see server_app.py's docstring for the
reasoning (any input source, including the future real Stylus body button
over BLE in ticket 05, can call the same server-side handler; this ticket
exposes it as a WS message any client can also send for dev-mode testing
without stylus hardware).
"""
import asyncio
import json

import pytest
import websockets

from hal.providers import KeyboardMockProvider
from hal.trackers import SystemMouseFallbackTracker
from server_app import create_server


class _FakeModels:
    def __init__(self, response_text):
        self._response_text = response_text

    def generate_content(self, *, model, contents, config):
        return _FakeResponse(self._response_text)


class _FakeResponse:
    def __init__(self, text):
        self.text = text


class _FakeClient:
    def __init__(self, response_text):
        self.models = _FakeModels(response_text)


SPRING_MASS_JSON = json.dumps(
    {
        "formula_latex": "F = -kx",
        "concept_title": "Spring-Mass Harmonic Oscillation",
        "simulation_type": "spring_mass",
        "parameters": [
            {"key": "k", "label": "Spring Stiffness (N/m)", "min": 10, "max": 100, "val": 45}
        ],
    }
)


async def _free_port() -> int:
    import socket

    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.mark.asyncio
async def test_ai_trigger_message_broadcasts_ai_widget_spawn_to_all_clients():
    port = await _free_port()
    tracker = SystemMouseFallbackTracker(position_source=lambda: (0, 0), screen_size=(1000, 1000))
    touch_provider = KeyboardMockProvider()
    gemini_client = _FakeClient(SPRING_MASS_JSON)

    async with create_server(
        tracker, touch_provider, host="127.0.0.1", port=port, fps=60, gemini_client=gemini_client
    ):
        async with websockets.connect(f"ws://127.0.0.1:{port}") as sender, websockets.connect(
            f"ws://127.0.0.1:{port}"
        ) as observer:
            await sender.send(json.dumps({"type": "AI_TRIGGER"}))

            async def _next_widget_message(ws):
                while True:
                    raw = await asyncio.wait_for(ws.recv(), timeout=2)
                    message = json.loads(raw)
                    if message["type"] in ("AI_WIDGET_SPAWN", "AI_WIDGET_UNSUPPORTED"):
                        return message

            sender_msg = await _next_widget_message(sender)
            observer_msg = await _next_widget_message(observer)

    assert sender_msg["type"] == "AI_WIDGET_SPAWN"
    assert sender_msg["sim_type"] == "spring_mass"
    assert observer_msg == sender_msg


@pytest.mark.asyncio
async def test_ai_trigger_with_no_gemini_client_still_spawns_from_cached_fallback():
    port = await _free_port()
    tracker = SystemMouseFallbackTracker(position_source=lambda: (0, 0), screen_size=(1000, 1000))
    touch_provider = KeyboardMockProvider()

    async with create_server(tracker, touch_provider, host="127.0.0.1", port=port, fps=60):
        async with websockets.connect(f"ws://127.0.0.1:{port}") as client:
            await client.send(json.dumps({"type": "AI_TRIGGER"}))

            while True:
                raw = await asyncio.wait_for(client.recv(), timeout=2)
                message = json.loads(raw)
                if message["type"] in ("AI_WIDGET_SPAWN", "AI_WIDGET_UNSUPPORTED"):
                    break

    assert message["type"] == "AI_WIDGET_SPAWN"
