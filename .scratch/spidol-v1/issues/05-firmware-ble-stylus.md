# 05: Firmware: BLE touch + AI-trigger stylus

**What to build:** The physical Stylus firmware and its BLE link to the server, replacing the mouse as both the touch signal source and the AI Trigger source. No OS-level HID mouse profile is used — this is a custom GATT service.

**Blocked by:** 01, 04

**Status:** code-complete, hardware-unverified (merged to integration/spidol-v1 at 7e4b9ca)

- [x] ESP32-C3 firmware (NimBLE stack) exposes a custom BLE GATT service with a characteristic that notifies `touching: bool`, driven by the Tip Contact Switch (GPIO4, pull-up, debounced) — no HID mouse profile, no movement deltas, no OS cursor involvement. Written in `spidol/spidol_firmware.ino`, carefully reasoned from SPEC.md/ADR-0001/the NimBLE-Arduino API, but **UNVERIFIED against a real ESP32-C3 or the Arduino toolchain** (no hardware/compiler available in this environment).
- [x] A second characteristic notifies on AI Trigger button presses (GPIO5), press-edge only, debounced — same caveat as above (firmware unverified on real hardware).
- [x] The Pen Tip is a passive high-contrast colored tip; no laser or active emitter is used anywhere in the firmware or docs.
- [x] `BleTouchProvider` implemented against the existing `BaseTouchProvider` interface (`server/hal/providers.py`), consuming the touch GATT notification via `bleak`, bridging the async notify callback into synchronous `is_touching()`. Fully unit-tested against a faked `bleak` client (`server/tests/test_ble_touch_provider.py`) — no real radio needed, verified working.
- [x] The AI Trigger button's GATT notification is wired to the AI Trigger event hook built in ticket 04, via a new direct server-side call path (`server.fire_ai_trigger()` in `server_app.py`) rather than a self-directed WebSocket message — see that module's docstring for the reasoning. Wired in `main.py` behind `--ble-address`. Integration-tested in `server/tests/test_server_ai_trigger.py` (direct-call path, no WebSocket sender) — verified working.
- [ ] **NOT DONE — requires real hardware.** On a breadboard prototype: pressing the Tip Contact Switch starts a stroke and releasing it ends the stroke, with no mouse involved; pressing the AI Trigger button fires the real AI pipeline end-to-end. This needs a real ESP32-C3, real microswitches, and a BLE scanner/central bring-up session that could not be performed in this code-only environment.
