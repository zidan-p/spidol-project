# 04: AI Trigger pipeline: formula capture → simulation widget

**What to build:** The full path from "a formula has been drawn and the user wants it analyzed" to a live, interactive simulation widget rendered on the canvas — demoable via a dev-mode mock trigger (e.g. a keyboard shortcut), with no real stylus hardware required for this ticket.

**Blocked by:** 01

**Status:** ready-for-agent

- [ ] An abstracted AI Trigger event hook exists that any input source can call (satisfied in this ticket by a dev-mode mock, e.g. a keyboard shortcut; satisfied later by the real Stylus button in ticket 05)
- [ ] On AI Trigger, the server computes the AI Trigger Region: all strokes recorded since the previous AI Trigger or the last canvas clear (tracked by stroke timestamp/ID), not a fixed time window
- [ ] The contour detector provides ROI-selection help (returns the bounding region of the last closed contour, if one exists) but never fires the AI pipeline on its own
- [ ] The AI Trigger Region is cropped and sent to Gemini 3.1 Flash-Lite (or newer — verify via `client.models.list()` at implementation time; not `gemini-1.5-flash`, retired, and not `gemini-3.5-flash-lite`, which doesn't exist) via the `google-genai` SDK, with a `response_schema` constraining output to `{formula_latex, concept_title, simulation_type, parameters[]}`
- [ ] `simulation_type` is validated against a fixed enum (3-4 types, e.g. `spring_mass`, `pendulum`, `projectile`); a recognized type broadcasts `AI_WIDGET_SPAWN`, an unrecognized/invalid one broadcasts `AI_WIDGET_UNSUPPORTED`
- [ ] If the live Gemini call errors or exceeds a ~3s timeout, a Cached Fallback Schema (pre-baked response for the known demo formula) is served instead, after the real call was attempted first
- [ ] Frontend `SimulationWidget` renders each fixed Simulation Type using its own hand-written RK4 integrator (no general physics library), with sliders bound to the returned `parameters[]` and editable via mouse
- [ ] Frontend renders a distinct "concept detected but not yet supported" state when `AI_WIDGET_UNSUPPORTED` is received, instead of crashing or silently doing nothing
- [ ] Submitted strokes remain visible on the canvas after the AI Trigger resolves (formula and simulation appear side by side)
