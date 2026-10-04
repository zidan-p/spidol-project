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
import './styles/excalidraw.css'

const WEBSOCKET_URL = `ws://${window.location.hostname}:8765`
const AI_TRIGGER_KEY = 't'
const CALIBRATE_KEY = 'c'

function App() {
  const { latestTrackRef, connectionState, widgets, sendMessage } = useSpidolSocket(WEBSOCKET_URL)
  const canvasRef = useRef(null)

  const [tool, setTool] = useState('pen')
  const [color, setColor] = useState('#ffffff')
  const [width, setWidth] = useState(4)
  const [dash, setDash] = useState('solid')
  const style = { tool, color, width, dash }

  const [history, setHistory] = useState({ canUndo: false, canRedo: false })
  const [pendingText, setPendingText] = useState(null) // { x, y } in normalized 0..1 canvas coords
  const [isTouching, setIsTouching] = useState(false)

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

  useEffect(() => {
    const onKeyDown = (event) => {
      const key = event.key.toLowerCase()
      if (key === AI_TRIGGER_KEY) {
        sendMessage({ type: 'AI_TRIGGER' })
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
  }, [sendMessage])

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
    <div className="spidol-app" data-blackout={isBlackout} data-kiosk={isKiosk}>
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
          <div className="hud hud--bottom-left">
            <button type="button" onClick={handleUndo} disabled={!history.canUndo}>
              Undo
            </button>
            <button type="button" onClick={handleRedo} disabled={!history.canRedo}>
              Redo
            </button>
            <button type="button" onClick={handleClear}>
              Clear
            </button>
            <button type="button" onClick={toggleKiosk}>
              {isKiosk ? 'Exit kiosk' : 'Enter kiosk'}
            </button>
          </div>
          {pendingText && (
            <input
              type="text"
              autoFocus
              className="text-tool-input"
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
      <div className="sim-widget-layer">
        {widgets.map((widget) => (
          <SimulationWidget key={widget.widget_id} widget={widget} />
        ))}
      </div>
    </div>
  )
}

export default App
