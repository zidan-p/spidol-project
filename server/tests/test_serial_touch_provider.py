"""Tests for `SerialTouchProvider`: the classic Bluetooth SPP firmware
variant (spidol/src/main.cpp's `BluetoothSerial`-based firmware), read back
as a plain virtual COM port after pairing -- same newline-terminated
"1"/"0"/"TRIGGER" line protocol as `WifiTouchProvider`, just over a serial
connection instead of a TCP socket.

`pyserial`'s API is blocking, so the real read loop runs on a background
thread via `loop.run_in_executor` -- `_FakeSerial` stands in for a real
`serial.Serial` connection (injected via `serial_factory`) so tests never
open a real COM port, and `asyncio.sleep(...)` calls give that background
thread a chance to actually run between assertions.
"""
import asyncio

import pytest

from hal.interfaces import BaseTouchProvider
from hal.providers import SerialTouchProvider


class _FakeSerial:
    """A thread-safe, closeable FIFO of lines standing in for a real
    `serial.Serial` connection. `push_line` is called from the test
    (main) thread; `readline` is called from `SerialTouchProvider`'s
    background thread -- mirrors how a real connection would actually be
    driven from two different places.

    `readline` times out and returns `b""` after a short wait, exactly
    like real `pyserial` does with `timeout=1` -- this is what lets
    `SerialTouchProvider._read_loop`'s `_stop_event` check actually get
    reached periodically instead of blocking forever, so tests can
    cleanly stop the background thread instead of leaking it.
    """

    def __init__(self):
        import queue

        self._queue = queue.Queue()
        self.closed = False

    def push_line(self, line: bytes) -> None:
        self._queue.put(line)

    def readline(self) -> bytes:
        import queue

        try:
            return self._queue.get(timeout=0.02)
        except queue.Empty:
            return b""

    def close(self) -> None:
        self.closed = True


def _make_provider(on_ai_trigger=None):
    fake_connections = []

    def serial_factory(port, baudrate):
        connection = _FakeSerial()
        fake_connections.append(connection)
        return connection

    provider = SerialTouchProvider(
        port="COM9", on_ai_trigger=on_ai_trigger, serial_factory=serial_factory
    )
    return provider, fake_connections


def test_serial_touch_provider_is_a_base_touch_provider():
    provider, _ = _make_provider()
    assert isinstance(provider, BaseTouchProvider)


def test_serial_touch_provider_defaults_to_not_touching_before_any_line():
    provider, _ = _make_provider()
    assert provider.is_touching() is False


@pytest.mark.asyncio
async def test_updates_is_touching_from_1_and_0_lines():
    provider, fake_connections = _make_provider()
    task = asyncio.create_task(provider.run_forever(retry_delay_s=0.01))
    await asyncio.sleep(0.02)
    connection = fake_connections[0]

    connection.push_line(b"1\n")
    await asyncio.sleep(0.02)
    assert provider.is_touching() is True

    connection.push_line(b"0\n")
    await asyncio.sleep(0.02)
    assert provider.is_touching() is False

    provider.stop()
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


@pytest.mark.asyncio
async def test_invokes_sync_on_ai_trigger_callback_on_trigger_line():
    calls = []
    provider, fake_connections = _make_provider(on_ai_trigger=lambda: calls.append(1))
    task = asyncio.create_task(provider.run_forever(retry_delay_s=0.01))
    await asyncio.sleep(0.02)

    fake_connections[0].push_line(b"TRIGGER\n")
    await asyncio.sleep(0.02)

    assert calls == [1]

    provider.stop()
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


@pytest.mark.asyncio
async def test_invokes_async_on_ai_trigger_callback_on_trigger_line():
    calls = []

    async def on_ai_trigger():
        calls.append(1)

    provider, fake_connections = _make_provider(on_ai_trigger=on_ai_trigger)
    task = asyncio.create_task(provider.run_forever(retry_delay_s=0.01))
    await asyncio.sleep(0.02)

    fake_connections[0].push_line(b"TRIGGER\n")
    await asyncio.sleep(0.05)

    assert calls == [1]

    provider.stop()
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


def test_set_on_ai_trigger_wires_callback_after_construction():
    provider, _ = _make_provider(on_ai_trigger=None)
    calls = []
    provider.set_on_ai_trigger(lambda: calls.append(1))
    assert provider._on_ai_trigger is not None
