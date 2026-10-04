// Main canvas layout (hand-rolled, per SPEC.md 3.3). Kept deliberately
// minimal for ticket 01: just the WebSocket-driven canvas and a bare
// connection-status readout. Tool dock / property sidebar / blackout mode /
// kiosk mode are ticket 02's concern (UI chrome beyond a basic canvas).
import { Canvas } from './components/Canvas'
import { useSpidolSocket } from './hooks/useSpidolSocket'
import './styles/excalidraw.css'

const WEBSOCKET_URL = `ws://${window.location.hostname}:8765`

function App() {
  const { latestTrackRef, connectionState } = useSpidolSocket(WEBSOCKET_URL)

  return (
    <div className="spidol-app">
      <div className="status-capsule" data-connection-state={connectionState}>
        WS: {connectionState}
      </div>
      <Canvas latestTrackRef={latestTrackRef} />
    </div>
  )
}

export default App
