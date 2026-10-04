# 05: Firmware: BLE touch + AI-trigger stylus

**What to build:** The physical Stylus firmware and its BLE link to the server, replacing the mouse as both the touch signal source and the AI Trigger source. No OS-level HID mouse profile is used — this is a custom GATT service.

**Blocked by:** 01, 04

**Status:** ready-for-agent

- [ ] ESP32-C3 firmware (NimBLE stack) exposes a custom BLE GATT service with a characteristic that notifies `touching: bool`, driven by the Tip Contact Switch (GPIO4, pull-up, debounced) — no HID mouse profile, no movement deltas, no OS cursor involvement
- [ ] A second characteristic (or event on the same service) notifies on AI Trigger button presses (GPIO5)
- [ ] The Pen Tip is a passive high-contrast colored tip; no laser or active emitter is used
- [ ] `BleTouchProvider` implemented against the existing `BaseTouchProvider` interface, consuming the touch GATT notification via `bleak`, replacing `SystemMouseFallbackTracker`'s click-based touch stub for drawing
- [ ] The AI Trigger button's GATT notification is wired to the AI Trigger event hook built in ticket 04
- [ ] On a breadboard prototype: pressing the Tip Contact Switch starts a stroke and releasing it ends the stroke, with no mouse involved; pressing the AI Trigger button fires the real AI pipeline end-to-end
