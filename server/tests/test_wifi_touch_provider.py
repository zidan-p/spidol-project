"""Tests for `WifiTouchProvider`: the touch-signal source for the WiFi/TCP
firmware variant (spidol/spidol_firmware.ino's `WiFiClient`-based main.cpp),
which connects out to this process as a plain TCP client and sends
newline-terminated "1"/"0" lines on each Tip Contact Switch transition.

Uses real loopback TCP sockets (`asyncio.open_connection` standing in for
the ESP32) rather than mocking anything -- cheap and exercises the real
`asyncio.start_server` read loop, unlike BLE where no real radio is
available to test against.
"""
import asyncio

import pytest

from hal.interfaces import BaseTouchProvider
from hal.providers import WifiTouchProvider


async def _free_port() -> int:
    import socket

    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def test_wifi_touch_provider_is_a_base_touch_provider():
    provider = WifiTouchProvider()
    assert isinstance(provider, BaseTouchProvider)


def test_wifi_touch_provider_defaults_to_not_touching_before_any_connection():
    provider = WifiTouchProvider()
    assert provider.is_touching() is False


@pytest.mark.asyncio
async def test_wifi_touch_provider_updates_is_touching_from_stylus_lines():
    port = await _free_port()
    provider = WifiTouchProvider(host="127.0.0.1", port=port)
    task = asyncio.create_task(provider.run_forever())
    await asyncio.sleep(0.05)  # let the listening socket actually open

    reader, writer = await asyncio.open_connection("127.0.0.1", port)
    try:
        writer.write(b"1\n")
        await writer.drain()
        await asyncio.sleep(0.05)
        assert provider.is_touching() is True

        writer.write(b"0\n")
        await writer.drain()
        await asyncio.sleep(0.05)
        assert provider.is_touching() is False
    finally:
        writer.close()
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


@pytest.mark.asyncio
async def test_wifi_touch_provider_ignores_unrecognized_lines():
    port = await _free_port()
    provider = WifiTouchProvider(host="127.0.0.1", port=port)
    task = asyncio.create_task(provider.run_forever())
    await asyncio.sleep(0.05)

    reader, writer = await asyncio.open_connection("127.0.0.1", port)
    try:
        writer.write(b"garbage\n")
        await writer.drain()
        await asyncio.sleep(0.05)
        assert provider.is_touching() is False
    finally:
        writer.close()
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


@pytest.mark.asyncio
async def test_wifi_touch_provider_resets_to_not_touching_when_stylus_disconnects():
    # If the link drops mid-touch, assume released rather than keep
    # drawing with a stale "still touching" forever.
    port = await _free_port()
    provider = WifiTouchProvider(host="127.0.0.1", port=port)
    task = asyncio.create_task(provider.run_forever())
    await asyncio.sleep(0.05)

    reader, writer = await asyncio.open_connection("127.0.0.1", port)
    writer.write(b"1\n")
    await writer.drain()
    await asyncio.sleep(0.05)
    assert provider.is_touching() is True

    writer.close()
    await asyncio.sleep(0.05)
    assert provider.is_touching() is False

    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


@pytest.mark.asyncio
async def test_wifi_touch_provider_accepts_a_reconnect_after_a_disconnect():
    port = await _free_port()
    provider = WifiTouchProvider(host="127.0.0.1", port=port)
    task = asyncio.create_task(provider.run_forever())
    await asyncio.sleep(0.05)

    _, writer1 = await asyncio.open_connection("127.0.0.1", port)
    writer1.write(b"1\n")
    await writer1.drain()
    await asyncio.sleep(0.05)
    assert provider.is_touching() is True

    writer1.close()
    await asyncio.sleep(0.05)
    assert provider.is_touching() is False

    _, writer2 = await asyncio.open_connection("127.0.0.1", port)
    try:
        writer2.write(b"1\n")
        await writer2.drain()
        await asyncio.sleep(0.05)
        assert provider.is_touching() is True
    finally:
        writer2.close()
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
