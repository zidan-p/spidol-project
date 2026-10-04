"""Integration test for the AI Trigger hook (ticket 04's WS-message path,
plus ticket 05's direct server-side call path): a client can send
`{"type": "AI_TRIGGER"}` over its WebSocket connection, OR server-side code
(e.g. a BLE notification callback) can call `server.fire_ai_trigger()`
directly -- either way, every connected client receives the resulting
AI_WIDGET_SPAWN broadcast, because both paths run the same shared
`_fire_ai_trigger` logic. See server_app.py's module docstring for the full
reasoning on why ticket 05 needed a direct, non-WebSocket call path (a real
BLE notification handler is already server-side code; it shouldn't have to
fake being its own WebSocket client just to reach `handle_ai_trigger`).
"""
import asyncio
import json

import pytest
import websockets

from hal.providers import KeyboardMockProvider
from hal.trackers import SystemMouseFallbackTracker
from server_app import create_server


class _FakeCompletions:
    def __init__(self, response_text):
        self._response_text = response_text

    def create(self, *, model, messages, response_format):
        return _FakeResponse(self._response_text)


class _FakeMessage:
    def __init__(self, content):
        self.content = content


class _FakeChoice:
    def __init__(self, content):
        self.message = _FakeMessage(content)


class _FakeResponse:
    def __init__(self, content):
        self.choices = [_FakeChoice(content)]


class _FakeClient:
    def __init__(self, response_text):
        self.chat = type("Chat", (), {"completions": _FakeCompletions(response_text)})()


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
    vision_client = _FakeClient(SPRING_MASS_JSON)

    async with create_server(
        tracker, touch_provider, host="127.0.0.1", port=port, fps=60, vision_client=vision_client
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
async def test_ai_trigger_with_no_vision_client_still_spawns_from_cached_fallback():
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


@pytest.mark.asyncio
async def test_server_fire_ai_trigger_broadcasts_without_any_websocket_sender():
    """The direct call path (ticket 05): no client ever sends the
    `{"type": "AI_TRIGGER"}` WS message -- server-side code calls
    `server.fire_ai_trigger()` directly, simulating what a BLE AI-trigger
    notification callback does in `main.py`. Connected observers still get
    the broadcast exactly as in the WS-message-triggered test above.
    """
    port = await _free_port()
    tracker = SystemMouseFallbackTracker(position_source=lambda: (0, 0), screen_size=(1000, 1000))
    touch_provider = KeyboardMockProvider()
    vision_client = _FakeClient(SPRING_MASS_JSON)

    async with create_server(
        tracker, touch_provider, host="127.0.0.1", port=port, fps=60, vision_client=vision_client
    ) as server:
        async with websockets.connect(f"ws://127.0.0.1:{port}") as observer:
            await server.fire_ai_trigger()

            while True:
                raw = await asyncio.wait_for(observer.recv(), timeout=2)
                message = json.loads(raw)
                if message["type"] in ("AI_WIDGET_SPAWN", "AI_WIDGET_UNSUPPORTED"):
                    break

    assert message["type"] == "AI_WIDGET_SPAWN"
    assert message["sim_type"] == "spring_mass"
