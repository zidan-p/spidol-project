/*
 * SPIDOL Stylus firmware -- ESP32-C3, NimBLE-Arduino, custom GATT only.
 *
 * ============================================================================
 * UNVERIFIED AGAINST REAL HARDWARE / THE ARDUINO TOOLCHAIN.
 *
 * This file was written to the fullest extent possible from SPEC.md section
 * 3.1, GLOSSARY.md, ADR-0001, and the NimBLE-Arduino API as documented at
 * https://github.com/h2zero/NimBLE-Arduino (research notes section 4), but it
 * has NOT been compiled, flashed, or exercised against a physical ESP32-C3,
 * microswitches, or a BLE central. No Arduino toolchain is available in this
 * environment. Before relying on this in a demo:
 *   1. Compile it in Arduino IDE / arduino-cli with board "ESP32C3 Dev Module"
 *      and the NimBLE-Arduino library installed, and fix any compile errors
 *      (API surface across NimBLE-Arduino versions has changed historically,
 *      e.g. `NimBLECharacteristic::setValue`/`notify` signatures).
 *   2. Flash it to a real ESP32-C3 wired per the schematic (GPIO4 = Tip
 *      Contact Switch to GND, GPIO5 = AI Trigger button to GND, both using
 *      the internal pull-up -- no external resistors required).
 *   3. Verify with a BLE scanner (e.g. nRF Connect) that "SPIDOL_Stylus"
 *      advertises the service UUID below and that both characteristics
 *      notify on button press/release as expected.
 *   4. Verify end-to-end against the real `BleTouchProvider` (server/hal/
 *      providers.py), per ticket 05's hardware-dependent acceptance criterion.
 * ============================================================================
 *
 * Design constraints (ADR-0001 / GLOSSARY.md -- do not violate these):
 *   - NO BLE HID mouse profile anywhere in this firmware. No `BleMouse.h`,
 *     no `press()`/`release()`/movement deltas, no OS-level cursor
 *     involvement. The Touch Signal and AI Trigger are custom GATT
 *     characteristic notifications only.
 *   - The Pen Tip is a passive, high-contrast colored tip. No laser, no
 *     active emitter, anywhere in this design.
 *   - Position is NOT reported by this firmware at all -- the observer
 *     camera (OpticalColorTracker, server-side) is the sole source of Pen
 *     Tip position. This firmware only ever reports two booleans: the Tip
 *     Contact Switch state (level-triggered, both edges) and the AI Trigger
 *     button (press-edge only).
 *
 * GATT layout: one custom service, two NOTIFY-only characteristics.
 *   - TOUCH_CHAR_UUID:       notifies a single byte, 1 = pressed / touching,
 *                            0 = released, on every debounced state change
 *                            (both press and release).
 *   - AI_TRIGGER_CHAR_UUID:  notifies a single byte (always 1) on the
 *                            debounced press edge only -- a momentary event,
 *                            not a held-state value, matching GLOSSARY.md's
 *                            "AI Trigger: the body button press ... that
 *                            explicitly submits the current region".
 *
 * UUIDs below are placeholders generated for this project (format matches
 * `python -c "import uuid; print(uuid.uuid4())"` output per research notes
 * section 4) -- regenerate real random UUIDs before production use if these
 * ever collide with another project's BLE devices in the same room.
 */

#include <NimBLEDevice.h>

// ---- GATT UUIDs -- must match server/main.py's BLE_TOUCH_CHAR_UUID /
// ---- BLE_AI_TRIGGER_CHAR_UUID constants exactly.
#define SERVICE_UUID         "a1b2c3d4-0000-1000-8000-00805f9b34fb"
#define TOUCH_CHAR_UUID       "a1b2c3d4-0001-1000-8000-00805f9b34fb"
#define AI_TRIGGER_CHAR_UUID  "a1b2c3d4-0002-1000-8000-00805f9b34fb"

#define DEVICE_NAME "SPIDOL_Stylus"

// ---- GPIO pin assignments (SPEC.md 3.1) ----
// Tip Contact Switch: tactile microswitch inside the Pen Tip, wired to
// GND, internal pull-up -> pressed reads LOW.
#define TIP_SWITCH_PIN 4
// AI Trigger: momentary body button, wired to GND, internal pull-up ->
// pressed reads LOW.
#define AI_BUTTON_PIN  5

// ---- Debounce ----
// Debounced entirely in firmware (never rely on the Python side to filter
// bounce -- research notes section 4 gotcha). 30ms is a standard debounce
// window for tactile microswitches/momentary buttons; revisit only if real
// hardware testing shows chatter past this window.
static const unsigned long DEBOUNCE_MS = 30;

NimBLECharacteristic *touchChar = nullptr;
NimBLECharacteristic *aiTriggerChar = nullptr;

bool lastTouchState = false;      // debounced, published state
bool lastButtonRawState = false;  // debounced, published *raw* reading (for edge detection)
unsigned long lastTouchDebounceAt = 0;
unsigned long lastButtonDebounceAt = 0;

void setupBle() {
  NimBLEDevice::init(DEVICE_NAME);

  NimBLEServer *server = NimBLEDevice::createServer();
  NimBLEService *service = server->createService(SERVICE_UUID);

  touchChar = service->createCharacteristic(TOUCH_CHAR_UUID, NIMBLE_PROPERTY::NOTIFY);
  aiTriggerChar = service->createCharacteristic(AI_TRIGGER_CHAR_UUID, NIMBLE_PROPERTY::NOTIFY);

  // Seed both characteristics with a defined initial value (not-touching /
  // no-trigger) so a central that reads before the first notify still sees
  // a sane value, rather than whatever garbage NimBLE initializes to.
  uint8_t initialTouch = 0;
  touchChar->setValue(&initialTouch, 1);
  uint8_t initialTrigger = 0;
  aiTriggerChar->setValue(&initialTrigger, 1);

  service->start();

  NimBLEAdvertising *advertising = NimBLEDevice::getAdvertising();
  advertising->addServiceUUID(SERVICE_UUID);
  advertising->start();
}

void setup() {
  // Internal pull-ups: both switches wired active-LOW to GND, no external
  // resistors needed (SPEC.md 3.1).
  pinMode(TIP_SWITCH_PIN, INPUT_PULLUP);
  pinMode(AI_BUTTON_PIN, INPUT_PULLUP);

  setupBle();
}

void loop() {
  unsigned long now = millis();

  // --- Tip Contact Switch: notify on EVERY debounced state change (both
  // --- press and release), since this is the live press/release Touch
  // --- Signal a stroke's start/end hinges on -- not a momentary event.
  bool rawTouch = (digitalRead(TIP_SWITCH_PIN) == LOW);  // active-LOW -> pressed == LOW
  if (rawTouch != lastTouchState && (now - lastTouchDebounceAt) > DEBOUNCE_MS) {
    lastTouchState = rawTouch;
    lastTouchDebounceAt = now;

    uint8_t value = lastTouchState ? 1 : 0;
    touchChar->setValue(&value, 1);
    touchChar->notify();  // no-op if no central is subscribed yet -- harmless.
  }

  // --- AI Trigger button: notify only on the debounced PRESS edge, not the
  // --- release -- this is a momentary "fire the pipeline now" event, per
  // --- GLOSSARY.md's AI Trigger definition, not a held-state value.
  bool rawButton = (digitalRead(AI_BUTTON_PIN) == LOW);  // active-LOW -> pressed == LOW
  if (rawButton != lastButtonRawState && (now - lastButtonDebounceAt) > DEBOUNCE_MS) {
    lastButtonRawState = rawButton;
    lastButtonDebounceAt = now;

    if (rawButton) {  // press edge only
      uint8_t value = 1;
      aiTriggerChar->setValue(&value, 1);
      aiTriggerChar->notify();
    }
  }

  // No delay() here -- keeping loop() non-blocking is what keeps the
  // debounce timing accurate for both GPIOs (research notes section 4
  // gotcha).
}
