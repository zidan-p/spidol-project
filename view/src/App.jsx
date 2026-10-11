// Main canvas layout (hand-rolled, per SPEC.md 3.3). Ticket 01 built the
// bare WebSocket-driven canvas; ticket 03 added the UI chrome around it:
// ToolIsland, PropertySidebar, undo/redo, Blackout Mode, Kiosk Mode, and
// StatusCapsule.
//
// Ticket 04 adds the dev-mode AI Trigger hook: pressing "T" sends
// {"type": "AI_TRIGGER"} over the WebSocket (see server_app.py's docstring
// for the full trigger-hook mechanism decision -- any input source,
// including the real Stylus body button later, can call the same
// server-side handler; this is the dev-mode stand-in for that button), and
// spawned/unsupported widgets render alongside the canvas so the formula
// and its simulation appear side by side.
//
// Ticket 02 adds the Calibration Hotkey: pressing "C" sends {"type":
// "CALIBRATE"} over the same WebSocket, which server_app.py's handler uses
// to call HomographyCalibrator.recalibrate(...) (dev-mode stub: no real
// 4-corner point-picking UX yet, see server_app.py's docstring). The Clear
// button additionally sends {"type": "CANVAS_CLEAR"} so the server-side AI
// Trigger Region (StrokeRegionTracker) resets in lockstep with the local
// canvas clear.
import { Loader2, Maximize2, Minimize2, Redo2, Sparkles, Trash2, Undo2 } from 'lucide-react'
import { useCallback, useEffect, useRef, useState } from 'react'
import { Canvas } from './components/Canvas'
import { PropertySidebar } from './components/PropertySidebar'
import { SimulationWidget } from './components/SimulationWidget'
import { StatusCapsule } from './components/StatusCapsule'
import { ToolIsland } from './components/ToolIsland'
import { useBlackoutMode } from './hooks/useBlackoutMode'
import { useKioskMode } from './hooks/useKioskMode'
import { useSpidolSocket } from './hooks/useSpidolSocket'
import { useUndoRedoHotkeys } from './hooks/useUndoRedoHotkeys'

const HUD_BUTTON_CLASS =
  'flex items-center gap-1.5 rounded-xl border border-transparent px-3 py-2 text-[13px] font-medium text-chrome-muted transition-colors hover:not-disabled:bg-white/8 hover:not-disabled:text-chrome-text disabled:cursor-default disabled:opacity-35'

// Safety upper bound on the processing indicator: the server always
// eventually broadcasts something (a real analysis or the Cached Fallback
// Schema) on every AI Trigger, but if the WebSocket itself drops mid-call
// there'd otherwise be no signal to clear it -- this is strictly larger
// than the server's own AI_TIMEOUT_S default so it never fires first in
// the normal case.
const AI_PROCESSING_SAFETY_TIMEOUT_MS = 30000

const WEBSOCKET_URL = `ws://${window.location.hostname}:8765`
const AI_TRIGGER_KEY = 't'
const CALIBRATE_KEY = 'c'

function App() {
  const { latestTrackRef, connectionState, widgets, sendMessage, removeWidget } = useSpidolSocket(WEBSOCKET_URL)
  const canvasRef = useRef(null)

  const [tool, setTool] = useState('pen')
  const [color, setColor] = useState('#ffffff')
  const [width, setWidth] = useState(4)
  const [dash, setDash] = useState('solid')
  const style = { tool, color, width, dash }

  const [history, setHistory] = useState({ canUndo: false, canRedo: false })
  const [pendingText, setPendingText] = useState(null) // { x, y } in normalized 0..1 canvas coords
  const [isTouching, setIsTouching] = useState(false)
  const [isAiProcessing, setIsAiProcessing] = useState(false)
  const aiProcessingTimeoutRef = useRef(null)

  const { isBlackout } = useBlackoutMode()
  const { isKiosk, toggleKiosk } = useKioskMode()

  const handleUndo = useCallback(() => canvasRef.current?.undo(), [])
  const handleRedo = useCallback(() => canvasRef.current?.redo(), [])
  useUndoRedoHotkeys({ onUndo: handleUndo, onRedo: handleRedo })

  const handleClear = useCallback(() => {
    canvasRef.current?.clear()
    // Also resets the server-side AI Trigger Region (StrokeRegionTracker),
    // matching the existing AI_TRIGGER message-handling pattern below --
    // otherwise a cleared canvas could still have "old" strokes folded into
    // the next AI Trigger Region server-side.
    sendMessage({ type: 'CANVAS_CLEAR' })
  }, [sendMessage])

  const handleTextPlacement = useCallback((stroke) => {
    setPendingText({ x: stroke.x, y: stroke.y })
  }, [])

  const commitPendingText = (text) => {
    canvasRef.current?.setTextForLastStroke(text)
    setPendingText(null)
  }

  const handleAiTrigger = useCallback(() => {
    // Sends the current canvas pixels along with the trigger so the
    // server's BrowserCanvasImageSource has a real frame to crop in
    // mouse-fallback dev mode (no real camera) -- see Canvas.jsx's
    // exportPngBase64 and server_app.py's AI_TRIGGER handler.
    const image_png_base64 = canvasRef.current?.exportPngBase64() ?? null
    sendMessage({ type: 'AI_TRIGGER', image_png_base64 })

    setIsAiProcessing(true)
    clearTimeout(aiProcessingTimeoutRef.current)
    aiProcessingTimeoutRef.current = setTimeout(
      () => setIsAiProcessing(false),
      AI_PROCESSING_SAFETY_TIMEOUT_MS
    )
  }, [sendMessage])

  // Clears the processing indicator as soon as any widget (recognized or
  // AI_WIDGET_UNSUPPORTED) arrives -- the server always eventually responds
  // to an AI Trigger with one or the other. Adjusted directly during render
  // (React's recommended pattern for "state derived from this component's
  // own state changing"), not in a useEffect -- an effect here would
  // trigger an extra cascading render for no benefit. The safety timeout
  // (above) is left to fire on its own schedule; calling setIsAiProcessing
  // (false) again once it's already false is a harmless no-op.
  const [lastWidgetCount, setLastWidgetCount] = useState(widgets.length)
  if (widgets.length !== lastWidgetCount) {
    setLastWidgetCount(widgets.length)
    if (isAiProcessing) setIsAiProcessing(false)
  }

  useEffect(() => {
    const onKeyDown = (event) => {
      const key = event.key.toLowerCase()
      if (key === AI_TRIGGER_KEY) {
        handleAiTrigger()
      } else if (key === CALIBRATE_KEY) {
        // Calibration Hotkey (GLOSSARY.md): manual, operator-triggered
        // re-run of the 4-point homography calibration -- never automatic
        // drift detection. Dev-mode stub: no real 4-corner point-picking UX
        // yet, so this just asks the server to recalibrate against its own
        // fixed/last-known correspondence (see server_app.py); a real
        // point-picking UI can later send src_points/dst_points here.
        sendMessage({ type: 'CALIBRATE' })
      }
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [handleAiTrigger, sendMessage])

  // Camera (ticket 02) and the BLE touch provider (ticket 05) don't exist
  // yet. Touch state is already available today from the TRACK_UPDATE
  // stream's is_touching field, so that part is wired live; camera stays a
  // flat "not-wired" placeholder until ticket 02 lands.
  const camera = { status: 'not-wired' }
  const touch = {
    status: connectionState === 'open' ? 'ok' : 'not-wired',
    isTouching,
  }

  return (
    <div
      className="relative h-screen w-screen overflow-hidden bg-black data-[kiosk=true]:cursor-none data-[kiosk=true]:**:cursor-none!"
      data-blackout={isBlackout}
      data-kiosk={isKiosk}
    >
      {!isBlackout && (
        <>
          <ToolIsland tool={tool} onSelectTool={setTool} />
          <PropertySidebar
            color={color}
            onColorChange={setColor}
            width={width}
            onWidthChange={setWidth}
            dash={dash}
            onDashChange={setDash}
          />
          <StatusCapsule connectionState={connectionState} camera={camera} touch={touch} />
          {isAiProcessing && (
            <div
              role="status"
              className="pointer-events-none absolute top-25 left-1/2 z-11 flex -translate-x-1/2 items-center gap-2 rounded-full border border-accent/35 bg-accent-soft px-4 py-2 text-[13px] font-medium text-accent shadow-[0_8px_24px_rgba(0,0,0,0.45)]"
            >
              <Loader2 className="animate-spin" aria-hidden="true" size={16} />
              Analyzing your drawing…
            </div>
          )}
          <div className="absolute bottom-4 left-4 z-10 flex gap-1.5 rounded-2xl border border-chrome-border bg-chrome-bg p-1.5 shadow-[0_8px_24px_rgba(0,0,0,0.45)] backdrop-blur-md">
            <button type="button" onClick={handleUndo} disabled={!history.canUndo} className={HUD_BUTTON_CLASS}>
              <Undo2 size={16} aria-hidden="true" />
              Undo
            </button>
            <button type="button" onClick={handleRedo} disabled={!history.canRedo} className={HUD_BUTTON_CLASS}>
              <Redo2 size={16} aria-hidden="true" />
              Redo
            </button>
            <button type="button" onClick={handleClear} className={HUD_BUTTON_CLASS}>
              <Trash2 size={16} aria-hidden="true" />
              Clear
            </button>
            <button
              type="button"
              onClick={handleAiTrigger}
              disabled={isAiProcessing}
              className={`${HUD_BUTTON_CLASS} border-accent/35! bg-accent-soft! font-semibold! text-accent! hover:not-disabled:bg-accent/28!`}
            >
              {isAiProcessing ? (
                <Loader2 size={16} aria-hidden="true" className="animate-spin" />
              ) : (
                <Sparkles size={16} aria-hidden="true" />
              )}
              {isAiProcessing ? 'Analyzing…' : 'Analyze drawing'}
            </button>
            <button type="button" onClick={toggleKiosk} className={HUD_BUTTON_CLASS}>
              {isKiosk ? (
                <Minimize2 size={16} aria-hidden="true" />
              ) : (
                <Maximize2 size={16} aria-hidden="true" />
              )}
              {isKiosk ? 'Exit kiosk' : 'Enter kiosk'}
            </button>
          </div>
          {pendingText && (
            <input
              type="text"
              autoFocus
              className="absolute z-10 -translate-y-1 border border-dashed border-chrome-muted bg-transparent font-sans text-base text-white"
              style={{ left: `${pendingText.x * 100}%`, top: `${pendingText.y * 100}%` }}
              onKeyDown={(event) => {
                if (event.key === 'Enter') commitPendingText(event.currentTarget.value)
                if (event.key === 'Escape') commitPendingText('')
              }}
              onBlur={(event) => commitPendingText(event.currentTarget.value)}
            />
          )}
        </>
      )}
      <Canvas
        ref={canvasRef}
        latestTrackRef={latestTrackRef}
        tool={tool}
        style={style}
        onHistoryChange={setHistory}
        onTextPlacement={handleTextPlacement}
        onTouchChange={setIsTouching}
      />
      <div className="pointer-events-none absolute inset-0 z-5">
        {widgets.map((widget) => (
          <SimulationWidget
            key={widget.widget_id}
            widget={widget}
            latestTrackRef={latestTrackRef}
            onClose={() => removeWidget(widget.widget_id)}
          />
        ))}
      </div>
    </div>
  )
}

export default App
