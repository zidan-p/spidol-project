# 03: Drawing tools & UI chrome

**What to build:** The full drawing UI a teacher interacts with beyond raw freehand ink — tool selection, styling, undo/redo, and the two display modes needed for projecting onto a whiteboard (Blackout Mode for the visual background, Kiosk Mode for input safety). Usable and fully demoable with mouse input alone.

**Blocked by:** 01

**Status:** done (merged to integration/spidol-v1 at d3327c4)

- [x] `ToolIsland` floating dock offers Pen (default), Eraser, Rectangle, Ellipse, Arrow, Line, and Text tools, each producing the correct shape/behavior on the canvas (eraser is whole-stroke, not pixel-level — documented judgment call)
- [x] `PropertySidebar` offers color swatches, stroke thickness (2px/4px/8px), and dash style selection, applied to new strokes
- [x] Undo (`Ctrl+Z`) and Redo (`Ctrl+Y`) correctly step backward/forward through the stroke history
- [x] Blackout Mode (hotkey `F`) hides all UI chrome and sets the canvas background to pure `#000000` — kept strictly separate from fullscreen per GLOSSARY.md, does not force Kiosk Mode
- [x] Kiosk Mode runs the browser truly fullscreen with nothing else clickable and the real OS cursor hidden (`cursor: none`)
- [x] `StatusCapsule` displays real-time telemetry: WebSocket link state, camera status, and touch state
