// Main canvas layout (hand-rolled, per SPEC.md 3.3). Kept deliberately
// minimal for ticket 01: just the WebSocket-driven canvas and a bare
// connection-status readout. Tool dock / property sidebar / blackout mode /
// kiosk mode are ticket 02/03's concern (UI chrome beyond a basic canvas).
//
// Ticket 04 adds the dev-mode AI Trigger hook: pressing "T" sends
// {"type": "AI_TRIGGER"} over the WebSocket (see server_app.py's docstring
// for the full trigger-hook mechanism decision -- any input source,
// including the real Stylus body button later, can call the same
// server-side handler; this is the dev-mode stand-in for that button), and
// spawned/unsupported widgets render alongside the canvas so the formula
// and its simulation appear side by side.
import { useEffect } from 'react'
import { Canvas } from './components/Canvas'
import { SimulationWidget } from './components/SimulationWidget'
import { useSpidolSocket } from './hooks/useSpidolSocket'
import './styles/excalidraw.css'

const WEBSOCKET_URL = `ws://${window.location.hostname}:8765`
const AI_TRIGGER_KEY = 't'

function App() {
  const { latestTrackRef, connectionState, widgets, sendMessage } = useSpidolSocket(WEBSOCKET_URL)

  useEffect(() => {
    const onKeyDown = (event) => {
      if (event.key.toLowerCase() === AI_TRIGGER_KEY) {
        sendMessage({ type: 'AI_TRIGGER' })
      }
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [sendMessage])

  return (
    <div className="spidol-app">
      <div className="status-capsule" data-connection-state={connectionState}>
        WS: {connectionState}
      </div>
      <Canvas latestTrackRef={latestTrackRef} />
      <div className="sim-widget-layer">
        {widgets.map((widget) => (
          <SimulationWidget key={widget.widget_id} widget={widget} />
        ))}
      </div>
    </div>
  )
}

export default App
