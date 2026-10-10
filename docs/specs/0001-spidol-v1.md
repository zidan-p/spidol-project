# SPIDOL v1: Interactive Whiteboard System

**Status:** ready-for-agent (manually applied — no issue tracker configured in this session; see note at bottom)

## Problem Statement

Teachers in under-resourced schools present STEM material on ordinary whiteboards lit by a standard projector. They have no way to interact with the projected content directly on the wall: they're tied to a laptop podium, slides are static, and there's no affordable way to turn abstract formulas (a differential equation, a force law) into something students can see move and respond to parameter changes. Commercial interactive whiteboards solve this but cost 150-300x more than this project's target budget, putting them out of reach for the vast majority of classrooms.

## Solution

A handheld battery-powered Stylus, a repurposed smartphone acting as an observer camera, and a laptop running a Python vision/AI server and a React canvas frontend, together turn any projector + whiteboard pair into a tracked, AI-augmented drawing surface for under $12 in parts. The teacher draws directly on the whiteboard with the Stylus; ink appears under the physical nib in real time. Circling a formula and pressing the Stylus's body button crops that formula, sends it to a vision-language model, and spawns a live, slider-driven physics simulation anchored next to the formula on the wall.

## User Stories

1. As a teacher, I want to draw freehand on the whiteboard with the Stylus, so that ink appears directly under my pen without needing to touch a laptop.
2. As a teacher, I want the ink to track my pen tip with low, imperceptible-enough latency, so that the interaction feels like writing with a real marker, not a laggy remote cursor.
3. As a teacher, I want to lift the Stylus off the whiteboard and have the line stop, so that I can make distinct separate strokes rather than one continuous line.
4. As a teacher, I want my pen strokes to keep tracking smoothly even when my own hand briefly covers the pen tip from the camera's view, so that normal handwriting doesn't produce broken or glitchy lines.
5. As a teacher, I want the system to stop guessing at my pen position if it loses tracking for too long, so that the pen doesn't draw a wild stray line across the board when I walk away or the camera loses the pen entirely.
6. As a teacher, I want to select different tools (pen, eraser, rectangle, ellipse, arrow, line, text) from a floating dock, so that I can illustrate concepts beyond freehand ink.
7. As a teacher, I want to pick a stroke color and thickness from a sidebar, so that I can differentiate between concepts or highlight key parts of a diagram.
8. As a teacher, I want to undo and redo my last strokes with keyboard shortcuts, so that I can correct mistakes without erasing everything.
9. As a teacher, I want a one-key "blackout" mode that hides all UI chrome and sets the background to pure black, so that only my ink and simulations are visible when projected, with no UI clutter competing with the whiteboard.
10. As a teacher, I want to circle a handwritten formula and press a single button on the Stylus, so that I can trigger AI analysis of exactly that formula without needing to touch a keyboard or mouse.
11. As a teacher, I want only the strokes I drew since my last AI request (or since I last cleared the board) sent to the AI, so that an old, unrelated diagram elsewhere on the board doesn't get swept into the analysis.
12. As a teacher, I want the formula I circled to remain visible on the board after I trigger the AI, so that students can see the formula and its live simulation side by side.
13. As a teacher, I want the AI to recognize common physics formulas (e.g. spring-mass, pendulum, projectile motion) and spawn an appropriate interactive simulation next to the formula, so that abstract equations become a visual, manipulable demonstration.
14. As a teacher, I want to adjust simulation parameters (e.g. spring constant, mass) using sliders, so that students can see cause and effect in real time.
15. As a teacher or student, I want to adjust those same sliders using the Stylus directly on the projected widget, so that interacting with the simulation feels the same as drawing — no need to switch to a mouse.
16. As a teacher, I want a clear "not supported yet" message if the AI recognizes a formula outside the handful of built-in simulation types, so that the system fails gracefully instead of silently doing nothing or crashing.
17. As a teacher presenting during a live competition demo, I want the system to keep working with a pre-baked response if the internet connection drops at the worst moment, so that a flaky venue network doesn't visibly break my demonstration.
18. As a teacher, I want to recalibrate the camera-to-projector mapping with a single hotkey before each class/session, so that if the camera or projector gets bumped between uses, I can quickly realign without a complex setup flow.
19. As a developer setting up the system for the first time, I want a `--dev` mode that runs the backend and a hot-reloading frontend separately, so that I can iterate on vision algorithms or UI without rebuilding the whole bundle each time.
20. As a developer preparing for a live demo, I want a single production command that serves the compiled frontend and starts all backend services together, so that there's one command to run on competition day with no separate terminals.
21. As a developer, I want the pen-tip tracking driver and the touch-detection driver to be swappable behind a shared interface, so that a fallback (mouse-driven) implementation can stand in during development or if the camera setup fails, without touching the rest of the server.
22. As a developer, I want the Stylus's touch signal delivered over a dedicated BLE notification rather than emulating an OS-level HID mouse, so that a pen press never risks triggering a stray click on whatever happens to have OS focus, and isn't at risk of being silently dropped by a zero-movement-delta HID quirk.
23. As a judge/user unfamiliar with the system, I want the pitch materials and demo narration to state an honest, qualitative "low-latency" claim rather than an unverified specific number, so that the team's credibility isn't at risk if asked a technical follow-up.

## Implementation Decisions

**Firmware (`spidol/`)**
- ESP32-C3 SuperMini running a custom BLE GATT service (NimBLE stack) — not a BLE HID mouse profile. See [ADR-0001](../adr/0001-ble-touch-signal-is-custom-gatt-not-hid-clicks.md).
- One GATT characteristic notifies `touching: bool`, driven by the Tip Contact Switch (GPIO4, pull-up, debounced).
- A second GATT characteristic (or the same service) notifies on AI Trigger button presses (GPIO5).
- The Pen Tip is a passive high-contrast colored tip; no laser or active emitter of any kind is used. See GLOSSARY.md.
- No position data originates from the firmware — only the two boolean signals above. Position is entirely a server/camera concern.

**Server (`server/`)**
- HAL boundary unchanged in shape from the existing `BasePositionTracker` / `BaseTouchProvider` interfaces; v1 concrete implementations are `OpticalColorTracker` + `SystemMouseFallbackTracker` (position) and `BleTouchProvider` (touch, consuming the GATT notification via `bleak`). `ArucoMarkerTracker` and any multi-device touch provider are out of scope for v1. See [ADR-0004](../adr/0004-v1-scope-single-stylus-no-aruco.md).
- Camera input is a phone connected via RemoteCam over USB, not DroidCam. See [ADR-0003](../adr/0003-remotecam-over-droidcam-and-scrcpy.md).
- Homography calibration is manual and session-scoped: a Calibration Hotkey re-runs the 4-point `cv2.findHomography` flow; no automatic drift detection.
- Tracking Loss handling: position reports under ~150ms of lost detection are bridged by linear interpolation between last-known and reacquired points; beyond that, the current stroke ends (pen-up signal emitted) rather than interpolating indefinitely.
- AI Trigger flow: the contour detector is a pure ROI-selection helper (returns the bounding region of the last closed contour, if any), never an autonomous trigger. The actual trigger is the AI Trigger button notification arriving from the firmware. See [ADR-0002](../adr/0002-ai-trigger-is-explicit-button-press.md).
- The submitted AI Trigger Region is defined as all strokes recorded since the previous AI Trigger (or since the last canvas clear), tracked by stroke timestamp/ID server-side — not a fixed time window.
- AI pipeline calls a configurable OpenAI-compatible vision endpoint via the `openai` SDK (ADR-0005), defaulting to Gemini's own OpenAI-compatible endpoint and Gemini 3.1 Flash-Lite (or newer at implementation time — `gemini-1.5-flash` is retired, `gemini-3.5-flash-lite` does not exist), overridable to OpenRouter or another provider via `AI_BASE_URL`/`AI_MODEL`, with a `response_format={"type": "json_schema", ...}` constraining output to `{formula_latex, concept_title, simulation_type, parameters[]}`.
- `simulation_type` is validated against a fixed enum: `spring_mass`, `pendulum`, `projectile`, `linear_function`. Unrecognized/unvalidated types produce a distinct `AI_WIDGET_UNSUPPORTED` broadcast rather than a malformed `AI_WIDGET_SPAWN`.
- A Cached Fallback Schema (pre-baked response for the known demo formula) is served if the live Gemini call errors or exceeds a ~3s timeout; the real call is always attempted first.
- WebSocket contract unchanged from current draft: `TRACK_UPDATE` at 60fps (`x`, `y`, `is_touching`, `is_detected`, `fps`, `device_id`), `AI_WIDGET_SPAWN` on successful AI Trigger resolution. New: `AI_WIDGET_UNSUPPORTED` message type for the unrecognized-simulation-type case (shape TBD at implementation time, minimally needs `widget_id`/anchor so the frontend can render the "not yet supported" state in place).
- `device_id` stays in the wire schema for forward compatibility but v1 server logic is hard-coded to a single stylus session; no multi-device disambiguation logic is implemented.

**Frontend (`view/`)**
- Hand-rolled canvas (not the `@excalidraw/excalidraw` package) — "Excalidraw" in this project refers only to the visual style being imitated.
- Single unified stroke buffer fed by both native pointer events and WebSocket `TRACK_UPDATE`/touch-state messages (`useDualInput.js`).
- Kiosk Mode (true fullscreen, nothing else clickable, `cursor: none`) is a defense-in-depth UI concern, independent of Blackout Mode (the `#000000` background / UI-hiding hotkey `F`) — these are two separate, composable states, not one toggle.
- `SimulationWidget` renders one of the fixed Simulation Types, each with its own hand-written RK4 integrator (no general-purpose physics library dependency) driven by the `parameters[]` array from the AI pipeline, with sliders bound to those same parameters and editable via mouse or Stylus-driven pointer events.
- An unsupported-simulation-type UI state (triggered by the new `AI_WIDGET_UNSUPPORTED` message) renders in place of a normal `SimulationWidget`.

## Testing Decisions

Good tests here assert on externally observable behavior at each seam's boundary (messages in/out, rendered state) — never on internal call counts, private helper functions, or vision/physics intermediate values that aren't part of the public contract.

- **Server seam** (new — no prior art in this repo): integration-style tests exercise `main.py`'s WebSocket boundary with fake `BasePositionTracker`/`BaseTouchProvider` implementations (feeding scripted position/touch sequences, including simulated Tracking Loss gaps) and a faked Gemini client (returning canned schema responses, a timeout, and an error, to exercise the Cached Fallback Schema path). Assertions are made purely on the `TRACK_UPDATE`/`AI_WIDGET_SPAWN`/`AI_WIDGET_UNSUPPORTED` messages emitted over the socket. This one seam covers: homography mapping correctness, interpolation/pen-up behavior on Tracking Loss, the AI Trigger Region stroke-boundary rule, Simulation Type validation, and the cached-fallback path.
- **Frontend seam** (new — no prior art in this repo): integration-style tests mount the app with a fake WebSocket (feeding scripted `TRACK_UPDATE`/`AI_WIDGET_SPAWN`/`AI_WIDGET_UNSUPPORTED` messages) plus simulated native pointer events, asserting on rendered canvas/widget state. Covers the dual-input sync engine, Kiosk/Blackout mode toggles, and `SimulationWidget` rendering (including the unsupported-type state) for a given parameter set.
- **Firmware:** no automated test seam. Verification is manual hardware-in-loop (flash, physically press the Tip Contact Switch and AI Trigger button, confirm the expected GATT notifications arrive at a real or scripted BLE central). A host-side unit test of just the debounce logic (compiled independently of the `.ino` sketch) is possible future work but not required for v1.

## Out of Scope

- `ArucoMarkerTracker` and any fiducial-marker-based tracking driver.
- Multi-stylus / collaborative simultaneous tracking and any conflict-resolution logic for more than one active device.
- Automatic homography drift detection or recalibration.
- Any BLE HID mouse profile implementation (superseded by the custom GATT approach).
- A general-purpose physics engine dependency (e.g. `matter.js`) for `SimulationWidget` — only hand-written per-type integrators.
- Automated/hardware-in-loop testing of the firmware.
- Any specific numeric latency claim in pitch materials ("sub-10ms" or similar) ahead of actual end-to-end benchmarking.

## Further Notes

- This spec reflects the full set of decisions resolved in the preceding grilling session; see [GLOSSARY.md](../../GLOSSARY.md) for canonical terminology and [docs/adr/](../adr/) for the reasoning behind each architecturally significant choice referenced above.
- **No issue tracker or triage label vocabulary is configured in this session.** Per this skill's instructions, publishing to a tracker and applying the `ready-for-agent` label requires `/setup-matt-pocock-skills`, which isn't installed here. This spec has been written to `docs/specs/0001-spidol-v1.md` instead; move/paste it into the real tracker once that's set up.
