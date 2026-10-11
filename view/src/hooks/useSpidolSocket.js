// Reads the SPIDOL WebSocket telemetry stream (TRACK_UPDATE @ ~60fps, plus
// low-frequency AI_WIDGET_SPAWN events from later tickets).
//
// The 60fps TRACK_UPDATE stream is stashed in a ref, not React state: a
// setState-per-message would schedule up to 60 re-renders/sec, which is
// wasteful and can visibly stutter. Canvas.jsx reads the ref on its own
// requestAnimationFrame schedule instead. Connection state (and the rare
// AI widget events) go through useState since those genuinely need to
// trigger a UI re-render.
import { useEffect, useRef, useState } from 'react'

export function useSpidolSocket(url) {
  const latestTrackRef = useRef({ x: 0, y: 0, is_touching: false, is_detected: false })
  const socketRef = useRef(null)
  const [connectionState, setConnectionState] = useState('connecting')
  const [widgets, setWidgets] = useState([])

  useEffect(() => {
    const ws = new WebSocket(url)
    socketRef.current = ws

    ws.onopen = () => setConnectionState('open')
    ws.onclose = () => setConnectionState('closed')

    ws.onmessage = (event) => {
      const message = JSON.parse(event.data)
      switch (message.type) {
        case 'TRACK_UPDATE':
          latestTrackRef.current = message
          break
        case 'AI_WIDGET_SPAWN':
        case 'AI_WIDGET_UNSUPPORTED':
          // Out of scope for ticket 01 (no AI pipeline yet), but the switch
          // is wired so later tickets don't have to touch this hook again.
          setWidgets((prev) => [...prev, message])
          break
        default:
          break
      }
    }

    return () => ws.close()
  }, [url])

  // Dev-mode AI Trigger hook (ticket 04): any input source can call this to
  // submit the current AI Trigger Region for analysis -- for this ticket,
  // the frontend calls it from a keyboard shortcut (see App.jsx), sending
  // `{"type": "AI_TRIGGER"}` over the same socket the TRACK_UPDATE stream
  // arrives on. The real Stylus body button (ticket 05) triggers the same
  // server-side handler without going through this WS message at all.
  const sendMessage = (message) => {
    socketRef.current?.send(JSON.stringify(message))
  }

  // Dismisses a widget locally (closing its card) -- purely a frontend
  // concern, no server message: the server's AI Trigger Region tracking is
  // keyed off strokes, not spawned widgets, so there's nothing server-side
  // to reconcile when one is closed.
  const removeWidget = (widgetId) => {
    setWidgets((prev) => prev.filter((widget) => widget.widget_id !== widgetId))
  }

  return { latestTrackRef, connectionState, widgets, sendMessage, removeWidget }
}
