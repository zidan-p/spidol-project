// Hand-rolled HTML5 2D canvas (per SPEC.md 3.3: not @excalidraw/excalidraw).
// Ink *position* is driven entirely by the stroke buffer, which is itself
// driven only by incoming TRACK_UPDATE messages -- this component never
// reads native pointer events to draw. Redraw is driven by
// requestAnimationFrame reading refs, not React state, to avoid a
// re-render per 60fps message.
//
// Ticket 03 adds: tool/style-aware rendering (shapes/eraser/text, per
// strokeGeometry.js), an undo/redo history (strokeHistory.js) exposed via
// an imperative handle so App.jsx's Ctrl+Z/Ctrl+Y hotkeys can drive it
// without this component re-rendering on every stroke point, and a
// callback for the Text tool's one native-keyboard exception (placing the
// *position* still comes from the TRACK_UPDATE stream; only the caption
// string itself is native keyboard input, handled by App.jsx's overlay).
import { forwardRef, useEffect, useImperativeHandle, useRef } from 'react'
import { createStrokeBuffer, ingestTrackUpdate } from '../lib/strokeBuffer'
import { strokeSegments } from '../lib/strokeGeometry'
import { canRedo, canUndo, commitAction, createHistory, redo, undo } from '../lib/strokeHistory'

const DASH_PATTERNS = {
  solid: [],
  dashed: [14, 8],
  dotted: [2, 7],
}

function pathForSegments(ctx, segments, width, height) {
  for (const [a, b] of segments) {
    ctx.beginPath()
    ctx.moveTo(a.x * width, a.y * height)
    ctx.lineTo(b.x * width, b.y * height)
    ctx.stroke()
  }
}

function drawArrowhead(ctx, from, to, width, height) {
  const fx = from.x * width
  const fy = from.y * height
  const tx = to.x * width
  const ty = to.y * height
  const angle = Math.atan2(ty - fy, tx - fx)
  const size = 14
  ctx.beginPath()
  ctx.moveTo(tx, ty)
  ctx.lineTo(tx - size * Math.cos(angle - Math.PI / 6), ty - size * Math.sin(angle - Math.PI / 6))
  ctx.moveTo(tx, ty)
  ctx.lineTo(tx - size * Math.cos(angle + Math.PI / 6), ty - size * Math.sin(angle + Math.PI / 6))
  ctx.stroke()
}

function drawStroke(ctx, stroke, width, height) {
  if (stroke.tool === 'eraser') return // never rendered; it only removes other strokes
  if (stroke.points.length === 0) return

  if (stroke.tool === 'text') {
    const [p] = stroke.points
    ctx.save()
    ctx.fillStyle = stroke.color
    ctx.font = `${12 + stroke.width * 3}px sans-serif`
    ctx.textBaseline = 'top'
    ctx.fillText(stroke.text ?? '', p.x * width, p.y * height)
    ctx.restore()
    return
  }

  ctx.save()
  ctx.strokeStyle = stroke.color
  ctx.lineWidth = stroke.width
  ctx.setLineDash(DASH_PATTERNS[stroke.dash] ?? [])

  const segments = strokeSegments(stroke)
  pathForSegments(ctx, segments, width, height)

  if (stroke.tool === 'arrow' && stroke.points.length >= 2) {
    drawArrowhead(ctx, stroke.points[0], stroke.points[1], width, height)
  }

  ctx.restore()
}

export const Canvas = forwardRef(function Canvas(
  { latestTrackRef, tool, style, onHistoryChange, onTextPlacement, onTouchChange },
  ref
) {
  const canvasRef = useRef(null)
  const bufferRef = useRef(createStrokeBuffer())
  const historyRef = useRef(createHistory())
  const lastSeenMessageRef = useRef(null)
  const lastTouchStateRef = useRef(false)
  const toolRef = useRef(tool)
  const styleRef = useRef(style)

  toolRef.current = tool
  styleRef.current = style

  const notifyHistoryChange = () => {
    onHistoryChange?.({ canUndo: canUndo(historyRef.current), canRedo: canRedo(historyRef.current) })
  }

  useImperativeHandle(
    ref,
    () => ({
      undo() {
        historyRef.current = undo(historyRef.current)
        bufferRef.current = { ...bufferRef.current, strokes: historyRef.current.strokes }
        notifyHistoryChange()
      },
      redo() {
        historyRef.current = redo(historyRef.current)
        bufferRef.current = { ...bufferRef.current, strokes: historyRef.current.strokes }
        notifyHistoryChange()
      },
      setTextForLastStroke(text) {
        const strokes = historyRef.current.strokes
        const last = strokes[strokes.length - 1]
        if (!last || last.tool !== 'text') return
        last.text = text
      },
      clear() {
        bufferRef.current = createStrokeBuffer()
        historyRef.current = createHistory()
        notifyHistoryChange()
      },
    }),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    []
  )

  useEffect(() => {
    const canvas = canvasRef.current
    const ctx = canvas.getContext('2d')
    ctx.lineJoin = 'round'
    ctx.lineCap = 'round'

    let rafId

    const draw = () => {
      const message = latestTrackRef.current
      if (message && message !== lastSeenMessageRef.current) {
        lastSeenMessageRef.current = message
        if (Boolean(message.is_touching) !== lastTouchStateRef.current) {
          lastTouchStateRef.current = Boolean(message.is_touching)
          onTouchChange?.(lastTouchStateRef.current)
        }
        const result = ingestTrackUpdate(bufferRef.current, message, styleRef.current)
        bufferRef.current = { strokes: result.strokes, activeStroke: result.activeStroke }
        if (result.lastAction) {
          historyRef.current = commitAction(historyRef.current, result.lastAction)
          bufferRef.current = { ...bufferRef.current, strokes: historyRef.current.strokes }
          notifyHistoryChange()
          if (result.lastAction.type === 'add' && result.lastAction.stroke.tool === 'text') {
            onTextPlacement?.(result.lastAction.stroke)
          }
        }
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
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [latestTrackRef])

  return <canvas ref={canvasRef} className="spidol-canvas" />
})
