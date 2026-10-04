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
The press/release state of the Tip Contact Switch, carried from firmware to server as a custom BLE GATT characteristic notification (consumed by `BleTouchProvider`), never as an HID mouse click. Fully decoupled from Pen Tip position, which arrives separately over the camera/WebSocket path.
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
The set of strokes submitted to the AI pipeline on an AI Trigger: every stroke drawn since the last AI Trigger or canvas clear, not a fixed time window. Matches the user's mental model of "read this batch I just drew."
_Avoid_: Recent strokes, time-windowed selection

**Simulation Type**:
One of a fixed, hand-built set of 3–4 `SimulationWidget` renderers (e.g. spring-mass, pendulum, projectile motion), each driven by a hand-written RK4 integrator rather than a general physics library. The AI pipeline classifies a formula into one of these and extracts its parameters; it never invents a new renderer. An unrecognized type surfaces a "concept detected but not yet supported" state instead of failing.
_Avoid_: Generative simulation, dynamic renderer, rigid-body physics engine

**Tracking Loss**:
A brief (under ~150ms) failure of `OpticalColorTracker` to locate the Pen Tip, most commonly caused by the writer's own hand/wrist occluding it during normal strokes — distinct from the Projector Shadow Principle, which only addresses the instructor's body blocking the projector beam. Bridged by interpolating a straight line between the last-known and reacquired points; beyond the threshold, the stroke ends (pen-up) rather than guessing across a long gap.
_Avoid_: Tracking dropout, occlusion (ambiguous with projector shadow)
