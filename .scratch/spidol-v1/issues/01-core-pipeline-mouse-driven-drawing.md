# 01: Core pipeline tracer bullet: mouse-driven drawing over WebSocket

**What to build:** The full server-to-WebSocket-to-frontend path working end-to-end using a mouse as the input source, with no camera or BLE hardware involved yet. A user can move the mouse and click-drag in the browser and see ink drawn in real time, driven entirely through the real `TRACK_UPDATE` WebSocket contract rather than native browser drawing — this proves out the whole pipeline skeleton that every later ticket plugs into. Includes standing up the monorepo scaffolding (`spidol/`, `server/`, `view/`) since none of it exists yet.

**Blocked by:** None (can start immediately)

**Status:** done (merged to integration/spidol-v1 at a95351b)

- [ ] `server/` scaffolded with the `BasePositionTracker`/`BaseTouchProvider` HAL interfaces, a `SystemMouseFallbackTracker` and `KeyboardMockProvider` (or equivalent mouse-click-based touch stub) implementation, and a WebSocket server broadcasting `TRACK_UPDATE` messages at ~60 FPS per the documented contract (`x`, `y`, `is_touching`, `is_detected`, `fps`, `device_id`)
- [ ] `view/` scaffolded with a hand-rolled canvas (not `@excalidraw/excalidraw`) that connects to the WebSocket and renders a stroke buffer driven purely by incoming `TRACK_UPDATE` messages, not native pointer events directly
- [ ] Moving the mouse over the tracked window updates the server's reported position; clicking and dragging produces a continuous stroke on the canvas that starts/ends correctly on mouse down/up
- [ ] `python main.py --dev` starts the WebSocket server and allows the frontend to run via the Vite dev server independently
- [ ] `python main.py` (production mode) serves the compiled `view/dist` bundle and starts the WebSocket server together behind a single command
