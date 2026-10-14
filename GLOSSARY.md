# SPIDOL

Interactive whiteboard system that turns a standard projector + dry-erase whiteboard into a tracked drawing surface, using a handheld stylus, an observer camera, and an AI pipeline that turns hand-drawn formulas into interactive simulations.

## Language

**Pen Tip**:
The passive, high-contrast colored tip on the stylus nib that the observer camera locates via color/blob tracking to determine on-screen draw position. Houses the tactile microswitch but is not itself the switch.
_Avoid_: Optical marker, laser dot, emitter

**Tip Contact Switch**:
The tactile microswitch inside the Pen Tip (wired to the firmware) that fires when the nib is pressed against the whiteboard, independent of the camera's visual tracking of the tip's position.
_Avoid_: Touch sensor, pressure sensor

**OpticalColorTracker**:
The only position-tracking driver shipping in v1; locates the Pen Tip by color/blob detection in the camera frame. `ArucoMarkerTracker` is out of scope for v1.
_Avoid_: Marker tracker, fiducial tracker

**Stylus**:
The single handheld input device for v1. The system is designed for exactly one Stylus at a time; multi-stylus fields in the wire schema (`device_id`) are forward-looking affordances, not a v1 feature.
_Avoid_: Pen (ambiguous with Pen Tip), marker

**Kiosk Mode**:
The frontend's true fullscreen, nothing-else-clickable browser state with the real OS cursor hidden (`cursor: none`). A defense-in-depth nicety now that the Touch Signal no longer touches the OS cursor at all, rather than a load-bearing mitigation.
_Avoid_: Blackout mode (that's the visual pitch-black rendering state, a separate concept), fullscreen

**Touch Signal**:
The press/release state of the Tip Contact Switch, carried from firmware to server as a custom BLE GATT characteristic notification (consumed by `BleTouchProvider`), never as an HID mouse click. Fully decoupled from Pen Tip position, which arrives separately over the camera/WebSocket path. A WiFi/TCP firmware variant (`spidol/src/main.cpp`, `server/hal/providers.py`'s `WifiTouchProvider`) carries the same Touch Signal over a plain TCP connection instead -- the ESP32 connects out to the server and sends newline-terminated "1"/"0" lines on each transition -- and, over that same connection, a "TRIGGER" line once per AI Trigger button press; still never an HID mouse click either way.
_Avoid_: BLE mouse click, HID click

**AI Trigger**:
The body button press (GPIO5) that explicitly submits the current region of interest to the AI pipeline. Never fires automatically from contour detection alone — closed-contour detection only narrows which strokes make up the region, it doesn't invoke the AI by itself.
_Avoid_: Auto-detect, gesture trigger

**Calibration Hotkey**:
A manual, operator-triggered action (not automatic drift detection) that re-runs the 4-point homography calibration. Expected to be used once per session/demo run, since the rig may be bumped or re-aimed between runs.
_Avoid_: Auto-calibration, drift correction

**Cached Fallback Schema**:
A pre-baked AI pipeline response for the specific formula used in the competition demo, served if the live Gemini call errors or exceeds a timeout, so a dropped venue connection never visibly breaks the live run.
_Avoid_: Mock response, offline mode

**AI Trigger Region**:
The set of strokes submitted to the AI pipeline on an AI Trigger: every stroke drawn since the last AI Trigger or canvas clear, not a fixed time window. Matches the user's mental model of "read this batch I just drew." When this region is empty (nothing drawn since the last trigger/clear), `handle_ai_trigger` (`server/ai/trigger.py`) skips the vision model call entirely and serves a dummy `function_graph` widget instead -- an "Analyze drawing" press on a blank board can't contain a real formula, so there's no reason to spend a real API call (and its tokens) finding that out.
_Avoid_: Recent strokes, time-windowed selection

**Simulation Type**:
Either a fixed physics type (`spring_mass`, `pendulum`, `projectile`, each driven by a hand-written RK4 integrator — never a general physics engine) or `function_graph` (docs/adr/0006): a deliberately generative exception covering any graphable math, where the AI returns either an `expression` (explicit `y = f(x)`, evaluated via mathjs in terms of `x`) or, for a curve that fails the vertical-line test (a circle, ellipse, or other closed/implicit curve — never forced into `expression`, which can only ever draw half of it), `parametric_x`/`parametric_y` (two expressions in terms of a parameter `t`). An unrecognized type (one that isn't a physics type and isn't expressible as `function_graph`) surfaces a "concept detected but not yet supported" state instead of failing.
_Avoid_: Generative physics simulation, rigid-body physics engine

**Graph Viewport**:
The function_graph canvas's current `{xMin, xMax, yMin, yMax}` view window (`view/src/lib/graphViewport.js`), distinct from the AI-returned parameter values — pan and zoom on the canvas manipulate only the Graph Viewport, never the curve's own parameters. Initialized once per widget from an auto-scaled default (widened to include the Definite Integral's bounds, if any) and persists afterward. Zoom is mouse-wheel-only (no Touch Signal equivalent to "scroll"); pan goes through the same TRACK_UPDATE stream that draws whiteboard ink (not a native pointer listener), so it works identically for mouse-fallback and the real Stylus, with double-tap (two touch-downs close in time and position) as the Stylus-compatible zoom gesture. Gesture ownership (whether a given touch-down belongs to the whiteboard or a widget) is decided once, at the press, and held for that gesture's duration — never re-evaluated against the position mid-drag, which previously let a whiteboard stroke that merely swept across a widget hijack its viewport.
_Avoid_: Canvas bounds, plot domain

**Definite Integral**:
A `function_graph` whose handwritten formula was an explicit definite integral with numeric bounds (e.g. `\int_{0}^{1} (2x+1)\,dx`) — the AI returns the integrand as the usual `expression`, plus `integral_lower`/`integral_upper` (set as a pair, or not at all). The frontend shades the area under the curve between those bounds and computes its numeric value via the composite trapezoidal rule (`view/src/lib/functionGraph.js`'s `definiteIntegral`) — a cosmetic/display feature layered on top of the ordinary explicit-function rendering path, not a new Simulation Type of its own.
_Avoid_: Area under the curve (fine in prose, not as the canonical term), shaded region

**Tracking Loss**:
A brief (under ~150ms) failure of `OpticalColorTracker` to locate the Pen Tip, most commonly caused by the writer's own hand/wrist occluding it during normal strokes — distinct from the Projector Shadow Principle, which only addresses the instructor's body blocking the projector beam. Bridged by interpolating a straight line between the last-known and reacquired points; beyond the threshold, the stroke ends (pen-up) rather than guessing across a long gap.
_Avoid_: Tracking dropout, occlusion (ambiguous with projector shadow)
