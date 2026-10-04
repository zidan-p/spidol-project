// Hand-rolled HTML5 2D canvas (per SPEC.md 3.3: not @excalidraw/excalidraw).
// Ink is driven entirely by the stroke buffer, which is itself driven only
// by incoming TRACK_UPDATE messages -- this component never reads native
// pointer events to draw. Redraw is driven by requestAnimationFrame reading
// refs, not React state, to avoid a re-render per 60fps message.
import { useEffect, useRef } from 'react'
import { createStrokeBuffer, ingestTrackUpdate } from '../lib/strokeBuffer'

function drawStroke(ctx, stroke, width, height) {
  if (stroke.length < 2) return
  ctx.beginPath()
  ctx.moveTo(stroke[0].x * width, stroke[0].y * height)
  for (let i = 1; i < stroke.length; i += 1) {
    ctx.lineTo(stroke[i].x * width, stroke[i].y * height)
  }
  ctx.stroke()
}

export function Canvas({ latestTrackRef }) {
  const canvasRef = useRef(null)
  const bufferRef = useRef(createStrokeBuffer())
  const lastSeenMessageRef = useRef(null)

  useEffect(() => {
    const canvas = canvasRef.current
    const ctx = canvas.getContext('2d')
    // jsdom (used by component tests that render <App/> around this canvas,
    // e.g. App.test.jsx's AI Trigger wiring tests) doesn't implement
    // getContext('2d') without the optional `canvas` native package, and
    // returns null -- guard so those tests can mount the tree without
    // pulling in that dependency. Real browsers always return a context.
    if (!ctx) return undefined
    ctx.strokeStyle = '#ffffff'
    ctx.lineWidth = 4
    ctx.lineJoin = 'round'
    ctx.lineCap = 'round'

    let rafId

    const draw = () => {
      const message = latestTrackRef.current
      if (message && message !== lastSeenMessageRef.current) {
        lastSeenMessageRef.current = message
        bufferRef.current = ingestTrackUpdate(bufferRef.current, message)
      }

      const { width, height } = canvas
      ctx.clearRect(0, 0, width, height)

      const { strokes, activeStroke } = bufferRef.current
      for (const stroke of strokes) {
        drawStroke(ctx, stroke, width, height)
      }
      if (activeStroke) {
        drawStroke(ctx, activeStroke, width, height)
      }

      rafId = requestAnimationFrame(draw)
    }

    const resize = () => {
      canvas.width = canvas.clientWidth
      canvas.height = canvas.clientHeight
    }
    resize()
    window.addEventListener('resize', resize)

    rafId = requestAnimationFrame(draw)
    return () => {
      cancelAnimationFrame(rafId)
      window.removeEventListener('resize', resize)
    }
  }, [latestTrackRef])

  return <canvas ref={canvasRef} className="spidol-canvas" />
}
