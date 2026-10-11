# TECHNICAL SPECIFICATION & SYSTEM ARCHITECTURE: PROJECT SPIDOL

**Competition:** Hackathon JOINTS UGM 2026 (FMIPA Universitas Gadjah Mada — Track: Education)
**Host Organization:** HMEI (Electronics & Instrumentation) x HIMAKOM (Computer Science)
**Institution:** Universitas Brawijaya
**Team Members:**
1. **Zidan Putra Rahman** (Student ID: 255060300111001) — Lead Firmware ESP32 BLE, Server Orchestrator & AI Pipeline
2. **Azkawira Umaro** (Student ID: 255060307111079) — Hardware Assembly, Electronic Instrumentation & Stylus Mechanics
3. **Fahrizal Eka Sunaryo** (Student ID: 255060307111040) — Frontend Canvas Engineering, UI/UX & Demonstration Media

See [GLOSSARY.md](./GLOSSARY.md) for canonical terminology, and [docs/adr/](./docs/adr/) for the reasoning behind decisions marked **(ADR-000N)** below.

---

## 1. Executive Summary & Value Proposition

- **Product Name:** **SPIDOL** (*Sistem Pena Interaktif Deteksi Optik & Low-Cost untuk Edukasi Transformatif* / Smart Pointer & Optical Detection System for Transformative Education)
- **Conceptual Subtitle:** **GRID** (*Gestural & Recognition Interactive Didactics*)
- **Core Problem:** Commercial interactive whiteboards / smartboards cost between $2,000 and $4,000 (IDR 30M-60M), rendering them financially unattainable for over 90% of public schools and underprivileged learning institutions in Indonesia. Classrooms remain constrained to passive, non-interactive LCD projectors where teachers are chained to laptop podiums and STEM subjects are taught through static, non-engaging slides.
- **The Solution:** SPIDOL transforms standard, pre-existing classroom projectors and ordinary dry-erase whiteboards into responsive, AI-augmented interactive surfaces at a total Bill of Materials (BOM) cost of **under $12 USD (< IDR 200,000)**.
- **Key User Journey:**
  1. An instructor holds the ergonomic, battery-powered SPIDOL Stylus in front of a standard whiteboard illuminated by an ordinary projector.
  2. Pressing the stylus tip against the whiteboard depresses the internal Tip Contact Switch, which wirelessly fires a Touch Signal over a custom BLE GATT notification **(ADR-0001)**.
  3. A co-located observer camera detects the Pen Tip via `OpticalColorTracker`, while the server maps coordinates through a 4-point Homography matrix to project digital ink directly underneath the physical nib with low latency.
  4. The instructor circles a handwritten STEM formula (e.g., a harmonic oscillator or differential equation) and presses the body button — the AI Trigger.
  5. The AI Trigger Region (every stroke drawn since the last trigger or clear) is cropped and streamed to the Gemini Vision API, which extracts the mathematical expression and returns one of a fixed set of Simulation Types with its parameters.
  6. The `SimulationWidget` renders dynamically beside the formula on the whiteboard, letting both teacher and students manipulate physical parameters directly on the wall using the Stylus or via the laptop mouse.

---

## 2. Monorepo Directory Architecture

The repository is partitioned into three decoupled, independently testable subprojects:

```text
spidol-project/
├── GLOSSARY.md
├── SPEC.md
├── docs/adr/                    # Architectural decision records
│
├── spidol/                      # Subproject 1: Embedded Stylus Firmware (C++ / Arduino)
│   ├── spidol_firmware.ino      # ESP32-C3 BLE GATT touch notify + NimBLE stack
│   └── schematics/              # Circuit schematics, BOM, and wiring diagrams
│
├── server/                      # Subproject 2: Core Vision & AI Engine (Python 3.10+ / .venv)
│   ├── pyproject.toml           # uv / pip manifest
│   ├── requirements.txt
│   ├── config.py                # Camera parameters, ports, HSV bounds, calibration storage
│   ├── main.py                  # Dual-purpose entrypoint: WS Server + CV + Static Host (:5000)
│   ├── hal/                     # Hardware Abstraction Layer (Open-Closed Principle)
│   │   ├── interfaces.py        # BasePositionTracker, BaseTouchProvider contracts
│   │   ├── trackers.py          # OpticalColorTracker, SystemMouseFallbackTracker
│   │   └── providers.py         # BleTouchProvider (GATT notify), KeyboardMockProvider
│   ├── vision/
│   │   ├── homography.py        # 4-point projector corner calibration & planar warping
│   │   └── contour_detector.py  # ROI-selection helper for the AI Trigger (not an autonomous trigger)
│   └── ai/
│       └── vision_pipeline.py   # Formula crop -> vision model -> Simulation Type + params
│
└── view/                        # Subproject 3: Interactive Canvas Web App (React + Vite + pnpm)
    ├── package.json             # pnpm package manifest
    ├── vite.config.js           # Development proxy routing to backend (:5000 & :8765)
    ├── index.html
    └── src/
        ├── main.jsx
        ├── App.jsx              # Main canvas layout, hand-rolled (not @excalidraw/excalidraw)
        ├── components/
        │   ├── ToolIsland.jsx       # Floating top tool dock (Pen, Eraser, Shapes, Text)
        │   ├── PropertySidebar.jsx  # Color swatches, stroke thickness, line style selectors
        │   ├── StatusCapsule.jsx    # Real-time telemetry (WS link, Camera status, Touch state)
        │   ├── Canvas.jsx           # Hand-rolled HTML5 2D rendering canvas
        │   └── SimulationWidget.jsx # Fixed-enum physics widget (hand-written RK4 integrators)
        ├── hooks/
        │   ├── useSpidolSocket.js   # WebSocket client reading telemetry at 60 FPS
        │   └── useDualInput.js      # Unified input pipeline (Mouse pointer + SPIDOL events)
        └── index.css                # Tailwind entry point + theme tokens (dark/pitch-black palette)
```

---

## 3. Subproject Technical Specifications

### 3.1 Subproject `./spidol` (Firmware & Hardware)
- **Microcontroller:** ESP32-C3 SuperMini (Single-core 32-bit RISC-V @ 160 MHz, integrated BLE 5.0, NimBLE stack).
- **Power Management:** 3.7V 18650/14500 Li-ion battery paired with a TP4056 USB-C charging module featuring over-discharge protection.
- **Physical Sensing Mechanisms:**
  - *Pen Tip:* a passive, high-contrast colored tip housing the Tip Contact Switch (a tactile microswitch, spring-loaded nib assembly) wired to `GPIO4` with an internal pull-up resistor. The color is what `OpticalColorTracker` locates in-frame; it is **not** a laser — no laser is used anywhere in this design.
  - *Body Interaction Button:* Momentary tactile button wired to `GPIO5`, the AI Trigger.
- **Wireless Protocol: custom BLE GATT service, not HID** **(ADR-0001)**.
  - A single characteristic notifies `touching: bool` whenever the Tip Contact Switch changes state. There is no HID mouse profile, no movement deltas, and no OS-level cursor involvement at all.
  - The AI Trigger (body button) notifies a separate characteristic on press.
- **Advantages:** no dependence on OS HID-stack quirks or zero-delta-click edge cases; immune to local campus Wi-Fi congestion and captive portals (BLE only, no Wi-Fi dependency for the stylus link).

---

### 3.2 Subproject `./server` (Python Engine & Pluggable Architecture)
- **Environment:** Isolated Python Virtual Environment (`.venv`) using Python 3.10+.
- **Key Dependencies:** `opencv-python>=4.8.0`, `websockets>=12.0`, `numpy>=1.24.0`, `openai` (OpenAI-compatible client, used against Gemini's own OpenAI-compatible endpoint by default — see ADR-0005), `bleak` (BLE GATT client).

#### A. Hardware Abstraction Layer (HAL / Open-Closed Architecture)
```python
class BasePositionTracker(ABC):
    @abstractmethod
    def get_position(self, frame: np.ndarray) -> tuple[float, float, bool]:
        """Returns normalized (x [0..1], y [0..1], is_detected)"""
        pass

class BaseTouchProvider(ABC):
    @abstractmethod
    def is_touching(self) -> bool:
        """Returns True if the Tip Contact Switch is currently pressed"""
        pass
```
- v1 tracker drivers: `OpticalColorTracker`, `SystemMouseFallbackTracker`. `ArucoMarkerTracker` and multi-stylus support are explicitly out of scope for v1 **(ADR-0004)**.
- v1 touch driver: `BleTouchProvider`, consuming the custom GATT notification directly (not OS mouse clicks) **(ADR-0001)**. `KeyboardMockProvider` remains available for headless testing.

#### B. Spatial Perspective Correction via 4-Point Homography (`vision/homography.py`)
- Solves optical distortion arising from arbitrary camera placement angles.
- Computed via a **Calibration Hotkey** — a manual, operator-triggered action, expected once per session/demo run since the rig may be bumped or re-aimed between runs. No automatic drift detection in v1.
- Coordinates extracted in runtime are mapped through $H$ using `cv2.perspectiveTransform`.

#### C. Camera Input & Latency
- The observer camera is a smartphone connected via **RemoteCam** (USB, open-source) rather than DroidCam **(ADR-0003)**.
- Latency claims are stated as **"low-latency,"** not a specific millisecond figure, until the real end-to-end pipeline is benchmarked. The originally-claimed "sub-10ms" figure is not achievable with a phone-as-camera signal path and must not appear in pitch materials.
- **Tracking Loss:** when `OpticalColorTracker` loses the Pen Tip — most commonly the writer's own hand/wrist occluding it during normal strokes, distinct from the Projector Shadow Principle below — the server interpolates a straight line between the last-known and reacquired points for losses under ~150ms. Beyond that threshold, the stroke ends (pen-up) rather than guessing across a longer gap.
- **Projector Shadow Principle:** the camera is co-located immediately adjacent to the projector lens or mounted overhead. Because instructors instinctively stand to the side to avoid blocking the projected light beam with their own shadow, the camera maintains an unobstructed line-of-sight to the whiteboard for most of a session.

#### D. Gesture Recognition & Multimodal AI Pipeline (`ai/vision_pipeline.py`)
- The AI Trigger is the body-button press — **not** automatic closed-contour detection **(ADR-0002)**. Contour detection only helps select the ROI (the last-closed contour if one exists).
- The **AI Trigger Region** submitted is every stroke drawn since the last AI Trigger or canvas clear, not a fixed time window, so a mid-formula pause never clips it. Submitted strokes remain visible on the canvas afterward.
- On AI Trigger:
  1. The server extracts a sub-image (ROI) from the camera buffer covering the AI Trigger Region.
  2. The image is passed to a configurable OpenAI-compatible vision endpoint via the **`openai`** Python package (**ADR-0005**) — defaults to Gemini's own OpenAI-compatible endpoint with **Gemini 3.1 Flash-Lite** (or newer — verify at implementation time, as this model family churns every few months; `gemini-1.5-flash` is retired as of Sept 2025 and `gemini-3.5-flash-lite` does not exist, neither must be referenced in code), but `AI_BASE_URL`/`AI_MODEL`/`--ai-base-url`/`--ai-model` can point it at OpenRouter or any other OpenAI-compatible provider instead — with a structured `response_format={"type": "json_schema", ...}` constraint.
  3. Response payload:
     ```json
     {
       "formula_latex": "\\frac{d^2x}{dt^2} + \\frac{k}{m}x = 0",
       "concept_title": "Simple Harmonic Motion",
       "simulation_type": "spring_mass",
       "parameters": [
         { "key": "k", "label": "Spring Constant (N/m)", "min": 10, "max": 100, "val": 40 },
         { "key": "m", "label": "Mass (kg)", "min": 0.5, "max": 5.0, "val": 1.0 }
       ]
     }
     ```
  4. **Simulation Type** is either a fixed physics type — `spring_mass`, `pendulum`, `projectile`, each with a hand-written RK4 integrator **(ADR-0004)** — or the deliberately generative `function_graph` **(ADR-0006)**: any graphable math, evaluated via `mathjs` as either an explicit `expression` (`y = f(x)`: linear, quadratic, trig, exponential, ...) or, for a curve failing the vertical-line test (circle, ellipse, ...), `parametric_x`/`parametric_y` (two expressions in a parameter `t`). The canvas supports pan (via the same TRACK_UPDATE stream that draws whiteboard ink, so it works for both mouse-fallback and the real Stylus) and zoom (mouse wheel, or double-tap as the Stylus-compatible gesture), manipulating a **Graph Viewport** independent of the curve's own parameters (GLOSSARY.md). The curve is drawn as a smooth path (quadratic-through-midpoints) rather than raw straight segments between samples. An unrecognized type surfaces a "concept detected but not yet supported" state in the UI rather than failing.
  5. Dispatches an `AI_WIDGET_SPAWN` broadcast to the frontend via WebSocket.
- **Cached Fallback Schema:** if the live Gemini call errors or exceeds a timeout (~3s), the server serves a pre-baked schema for the specific demo formula, so a dropped venue connection never visibly breaks the live run. The real API call is always attempted first.

#### E. Unified Execution Runner (`main.py`)
- `python main.py --dev`: WebSocket broadcaster (`ws://127.0.0.1:8765`) + OpenCV tracking loop, frontend via Vite dev server (`:5173`).
- `python main.py` (Production): WebSocket engine + optical tracker + integrated HTTP server serving `./view/dist` at `http://127.0.0.1:5000`.

---

### 3.3 Subproject `./view` (React Canvas Frontend)
- **Stack:** React 18/19, Vite, `pnpm`, Tailwind CSS v4 (via `@tailwindcss/vite`) for all UI chrome styling. A **hand-rolled** canvas, not the `@excalidraw/excalidraw` package — "Excalidraw" refers only to the visual inspiration **(see GLOSSARY)**. Owning the render loop matters here because of the dual-input stream and the `SimulationWidget` overlay.
- **UI System:**
  - *Floating Island Dock (Center-Top):* Tool selectors (Freehand Pen [Default], Eraser, Rectangle, Ellipse, Arrow, Line, Text).
  - *Left Property Sidebar:* Color palettes, stroke weight increments (2px, 4px, 8px), dash styles.
  - *Bottom-Left HUD:* Undo (`Ctrl+Z`), Redo (`Ctrl+Y`), canvas clear.
  - *Blackout Mode (Hotkey `F`):* Full-screen, auto-hides UI controls, canvas background pure `#000000` so black pixels emit zero lumens and the physical whiteboard shows through as the background.
  - *Kiosk Mode:* separately, the browser runs truly fullscreen with nothing else clickable and the real OS cursor hidden (`cursor: none`). Defense-in-depth now that the Touch Signal no longer touches the OS cursor at all **(ADR-0001)**.
- **Dual-Input Synchronization Engine:** a single unified vector stroke buffer (`strokes[]`) ingests native pointer events (mouse) and normalized coordinates + Touch Signal state streamed from the server over WebSocket (`useSpidolSocket.js`). v1 is hard-coded for exactly one Stylus end-to-end **(ADR-0004)**; `device_id` rides along in the schema unused.
- **Simulation Widgets:** each Simulation Type has its own hand-written RK4 integrator (no general physics library). Per-formula parameter sliders (m/b, radius, k/m, ...) are not rendered — the curve/simulation always runs with the AI's own default values; only the x/t exploration slider and (for `function_graph`) the Graph Viewport's pan/zoom are interactive. A `function_graph` whose formula was a Definite Integral additionally shades the area under the curve between its bounds and displays the computed numeric value.

---

## 4. WebSocket Communication Contracts (`ws://127.0.0.1:8765`)

### A. Continuous Telemetry Stream (Server -> Client @ 60 FPS)
```json
{
  "type": "TRACK_UPDATE",
  "device_id": "spidol_main",
  "x": 0.482,
  "y": 0.315,
  "is_touching": true,
  "is_detected": true,
  "fps": 59.8
}
```

### B. AI Simulation Spawn Event (Server -> Client)
```json
{
  "type": "AI_WIDGET_SPAWN",
  "widget_id": "widget_oscillator_01",
  "anchor_x": 0.55,
  "anchor_y": 0.30,
  "formula_latex": "F = -kx",
  "title": "Spring-Mass Harmonic Oscillation",
  "sim_type": "spring_mass",
  "parameters": [
    { "key": "k", "label": "Spring Stiffness (N/m)", "min": 10, "max": 100, "val": 45 },
    { "key": "m", "label": "Bob Mass (kg)", "min": 0.5, "max": 5.0, "val": 1.2 }
  ]
}
```

---

## 5. Developer Workflows & Execution Modes

### Mode 1: Development Workflow (Active UI / Algorithm Iteration)
```bash
# Terminal 1 — Python Backend (Virtual Environment)
cd server
python -m venv .venv
source .venv/Scripts/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python main.py --dev

# Terminal 2 — React Frontend (Vite HMR)
cd view
pnpm install
pnpm run dev
# Access development canvas at: http://localhost:5173
```

### Mode 2: Production / Competition Demonstration Workflow (1-Command All-in-One)
```bash
# Step 1: Compile the frontend bundle (one-time command)
cd view
pnpm run build

# Step 2: Launch the unified application via Python
cd ../server
source .venv/Scripts/activate
python main.py
# Automatically initializes WebSocket (:8765), camera vision, and serves http://localhost:5000
```

---

## 6. Bill of Materials (BOM) & Hardware Procurement

Procurement is consolidated into two verified, active Tokopedia official merchant storefronts:
1. **CNC Store Bandung:** ESP32-C3 SuperMini, TP4056 USB-C Charger with protection, 18650 Li-ion battery cell, momentary pushbuttons, 936 60W temperature-controlled soldering station, 50g rosin flux paste, 4-channel 3.3V-5V logic level converter, SYB-170 mini breadboard, Dupont jumper ribbon cables.
2. **Arduino Official Store (Arduinoid):** 16mm SPDT micro limit switches with arm lever, 0.8mm 63/37 rosin-core solder wire.
- No laser diode is procured — the Pen Tip is a passive colored tip, not an active emitter.
- **Combined BOM Total:** **~IDR 166,500 (~$11 USD)**.

---

## 7. Competition Submission Deliverables (Due: October 15–16, 2026)
1. **Source Code Repository (GitHub):** Clean modular layout (`/spidol`, `/server`, `/view`) accompanied by architectural diagrams, circuit schematics, and setup guides.
2. **Product Demonstration Video (YouTube):** Strictly $\le$ 2:00 duration detailing the educational gap, live whiteboard interaction demo, technical architecture, and cost breakdown. Latency claims: "low-latency," never an unverified specific millisecond figure.
3. **Pitchdeck Presentation (PDF):** 8–10 slides structured for evaluation by academic judges.
4. **Interactive Software Prototype:** Live canvas integration with real-time camera tracking.
5. **Technical Proposal (PDF, $\le$ 10 Pages):** Formatted following Universitas Brawijaya Capstone standards and styled using the Anthropic Editorial Research aesthetic (Warm Parchment `#FAF9F5`, Earth Tones, Full-Serif typography). Include the actual measured latency number once benchmarked.

---

## 8. MVP Priority Order (11-day runway, see ADR-0004)

- **Must work live:** Pen Tip tracking + drawing + AI Trigger -> formula capture -> Simulation Widget. This is the core differentiator and cannot be faked.
- **Video-backup acceptable:** anything multi-stylus (not actually built in v1, but if asked about roadmap).
- **Cut from v1 entirely:** `ArucoMarkerTracker`.
