"""Tests for `BleTouchProvider` (ticket 05): the real-hardware touch-signal
and AI-trigger source, bridging `bleak`'s async GATT notification callbacks
into the synchronous `BaseTouchProvider.is_touching()` seam the 60fps
telemetry loop calls every tick (see research notes section 3 / bleak's
usage docs).

No real BLE radio is exercised here -- `_FakeBleakClient` stands in for
`bleak.BleakClient` via the `client_factory` constructor parameter, and
tests simulate GATT notifications by directly invoking the callback that
`start_notify` captured, exactly as bleak's own internal event loop would.
"""
import asyncio

import pytest

from hal.interfaces import BaseTouchProvider
from hal.providers import BleTouchProvider

TOUCH_CHAR_UUID = "a1b2c3d4-0001-1000-8000-00805f9b34fb"
AI_TRIGGER_CHAR_UUID = "a1b2c3d4-0002-1000-8000-00805f9b34fb"


class _FakeBleakClient:
    """Stands in for `bleak.BleakClient`: records `start_notify` callbacks
    by characteristic UUID instead of talking to a real GATT server, and
    makes `connect`/`disconnect` no-ops so tests never touch a radio.
    """

    def __init__(self, device_address):
        self.device_address = device_address
        self.is_connected = False
        self._notify_callbacks = {}

    async def connect(self):
        self.is_connected = True

    async def disconnect(self):
        self.is_connected = False

    async def start_notify(self, char_uuid, callback):
        self._notify_callbacks[char_uuid] = callback

    def simulate_notify(self, char_uuid, data: bytes):
        self._notify_callbacks[char_uuid](None, bytearray(data))


def _make_provider(on_ai_trigger=None):
    fake_clients = []

    def client_factory(device_address):
        client = _FakeBleakClient(device_address)
        fake_clients.append(client)
        return client

    provider = BleTouchProvider(
        device_address="AA:BB:CC:DD:EE:FF",
        touch_char_uuid=TOUCH_CHAR_UUID,
        ai_trigger_char_uuid=AI_TRIGGER_CHAR_UUID,
        on_ai_trigger=on_ai_trigger,
        client_factory=client_factory,
    )
    return provider, fake_clients


def test_ble_touch_provider_is_a_base_touch_provider():
    provider, _ = _make_provider()
    assert isinstance(provider, BaseTouchProvider)


def test_ble_touch_provider_defaults_to_not_touching_before_any_notification():
    provider, _ = _make_provider()
    assert provider.is_touching() is False


@pytest.mark.asyncio
async def test_ble_touch_provider_updates_is_touching_from_touch_notification():
    provider, fake_clients = _make_provider()

    await provider.connect()
    client = fake_clients[0]

    client.simulate_notify(TOUCH_CHAR_UUID, b"\x01")
    assert provider.is_touching() is True

    client.simulate_notify(TOUCH_CHAR_UUID, b"\x00")
    assert provider.is_touching() is False


@pytest.mark.asyncio
async def test_ble_touch_provider_invokes_sync_on_ai_trigger_callback_on_notification():
    calls = []
    provider, fake_clients = _make_provider(on_ai_trigger=lambda: calls.append(1))

    await provider.connect()
    fake_clients[0].simulate_notify(AI_TRIGGER_CHAR_UUID, b"\x01")

    assert calls == [1]


@pytest.mark.asyncio
async def test_ble_touch_provider_schedules_async_on_ai_trigger_callback_on_notification():
    calls = []

    async def on_ai_trigger():
        calls.append(1)

    provider, fake_clients = _make_provider(on_ai_trigger=on_ai_trigger)

    await provider.connect()
    fake_clients[0].simulate_notify(AI_TRIGGER_CHAR_UUID, b"\x01")

    # The callback is scheduled via asyncio.create_task, not awaited inline
    # by the (sync) notification handler -- let the event loop run it.
    await asyncio.sleep(0)

    assert calls == [1]


@pytest.mark.asyncio
async def test_ble_touch_provider_touch_notification_does_not_fire_ai_trigger():
    calls = []
    provider, fake_clients = _make_provider(on_ai_trigger=lambda: calls.append(1))

    await provider.connect()
    fake_clients[0].simulate_notify(TOUCH_CHAR_UUID, b"\x01")

    assert calls == []


def test_ble_touch_provider_with_no_on_ai_trigger_callback_does_not_raise():
    provider, _ = _make_provider(on_ai_trigger=None)
    # Directly exercise the internal notification handler the same way
    # bleak would -- this is the "no callback configured" branch, which is
    # a legitimate construction (e.g. a touch-only deployment).
    provider._on_ai_trigger_notify(None, bytearray(b"\x01"))


@pytest.mark.asyncio
async def test_ble_touch_provider_set_on_ai_trigger_wires_callback_after_construction():
    # main.py's wiring need: the server object (and its fire_ai_trigger
    # method) only exists *after* create_server has started, but the touch
    # provider must be constructed *before* that call so the telemetry loop
    # can use it from the start -- so `on_ai_trigger` has to be settable
    # after construction, not only via the constructor.
    calls = []
    provider, fake_clients = _make_provider(on_ai_trigger=None)
    provider.set_on_ai_trigger(lambda: calls.append(1))

    await provider.connect()
    fake_clients[0].simulate_notify(AI_TRIGGER_CHAR_UUID, b"\x01")

    assert calls == [1]


@pytest.mark.asyncio
async def test_ble_touch_provider_run_forever_reconnects_after_a_disconnect():
    provider, fake_clients = _make_provider()

    task = asyncio.create_task(provider.run_forever(retry_delay_s=0.01))
    await asyncio.sleep(0.02)
    assert len(fake_clients) == 1
    assert provider.is_touching() is False

    # Simulate the link dropping -- run_forever should notice and reconnect,
    # producing a second client via client_factory.
    fake_clients[0].is_connected = False
    await asyncio.sleep(0.05)

    assert len(fake_clients) >= 2

    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
