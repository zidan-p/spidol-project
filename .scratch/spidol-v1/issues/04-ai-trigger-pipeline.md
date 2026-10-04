# 04: AI Trigger pipeline: formula capture → simulation widget

**What to build:** The full path from "a formula has been drawn and the user wants it analyzed" to a live, interactive simulation widget rendered on the canvas — demoable via a dev-mode mock trigger (e.g. a keyboard shortcut), with no real stylus hardware required for this ticket.

**Blocked by:** 01

**Status:** code-complete, Gemini live-call unverified (merged to integration/spidol-v1)

- [x] An abstracted AI Trigger event hook exists that any input source can call — implemented as a `{"type": "AI_TRIGGER"}` WebSocket message any connected client can send; frontend dev-mode mock is a "T" keydown; ticket 05's real Stylus button will call the same server-side `handle_ai_trigger`
- [x] On AI Trigger, the server computes the AI Trigger Region: all strokes recorded since the previous AI Trigger or the last canvas clear (tracked by stroke timestamp/ID), not a fixed time window — `StrokeRegionTracker`
- [x] The contour detector provides ROI-selection help (returns the bounding region of the last closed contour, if one exists) but never fires the AI pipeline on its own
- [x] The AI Trigger Region is cropped and sent to Gemini 3.1 Flash-Lite via the `google-genai` SDK, with a `response_schema` constraining output to `{formula_latex, concept_title, simulation_type, parameters[]}` — **implemented against the real SDK call shape but only tested against a faked client; no `GEMINI_API_KEY` was available to verify the live call. Re-verify the model string via `client.models.list()` before the demo, since this family churns.**
- [x] `simulation_type` is validated against a fixed enum (`spring_mass`, `pendulum`, `projectile`); a recognized type broadcasts `AI_WIDGET_SPAWN`, an unrecognized/invalid one broadcasts `AI_WIDGET_UNSUPPORTED`
- [x] If the live Gemini call errors or exceeds a ~3s timeout, a Cached Fallback Schema (pre-baked spring-mass response) is served instead, after the real call was attempted first
- [x] Frontend `SimulationWidget` renders each fixed Simulation Type using its own hand-written RK4 integrator (no general physics library), with sliders bound to the returned `parameters[]` and editable via mouse
- [x] Frontend renders a distinct "concept detected but not yet supported" state when `AI_WIDGET_UNSUPPORTED` is received, instead of crashing or silently doing nothing
- [x] Submitted strokes remain visible on the canvas after the AI Trigger resolves (formula and simulation appear side by side)

**Known gap, now closed (see ticket 02's checklist and `main.py`'s `make_camera_resources`):** the AI pipeline used to always crop a `BlankCanvasImageSource` stub. `main.py --tracker=optical-color` now passes a real `CameraImageSource` into `create_server`, which both the telemetry loop and `handle_ai_trigger`'s crop share — so the AI Trigger Region is cropped from a real camera frame whenever the camera tracker is active. In mouse/dev mode (`--tracker=mouse`, the default), `BlankCanvasImageSource` is still used, so only the Cached Fallback Schema demos meaningfully in that mode — expected, since there's no real Pen Tip camera feed in mouse-fallback dev mode at all.
