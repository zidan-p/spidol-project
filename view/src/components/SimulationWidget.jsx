// Simulation Type widget (SPEC.md 3.3 Simulation Widgets, GLOSSARY.md:
// Simulation Type). spring_mass/pendulum/projectile are real time-evolving
// physics simulations, each rendered by its own hand-written RK4
// integrator (no general physics library, see lib/rk4.js) -- these stay a
// fixed, closed set (docs/adr/0004). function_graph is the one
// deliberately generative exception (docs/adr/0006): the AI returns an
// arbitrary single-variable expression (any math that can be graphed as
// y = f(x) -- linear, quadratic, trig, exponential, ...), evaluated via
// mathjs (lib/functionGraph.js) and rendered by a hand-rolled canvas (axis
// ticks via lib/axisTicks.js) -- a `function-plot` (d3-based) integration
// was tried first but dropped (docs/adr/0006) after it failed silently in
// ways that couldn't be fully diagnosed without real-browser access; a
// renderer we fully control and can actually verify end-to-end won out
// over a nicer-looking but unverifiable third-party one.
// Per-formula parameter sliders (m/b, radius, k/m, ...) are deliberately
// not rendered -- the curve/simulation always uses the AI's own default
// values. A distinct "concept detected but not yet supported" state is rendered for
// AI_WIDGET_UNSUPPORTED (and, defensively, for any AI_WIDGET_SPAWN whose
// sim_type isn't one of these) rather than crashing or doing nothing.
import { useEffect, useMemo, useRef, useState } from 'react'
import { niceTicks } from '../lib/axisTicks'
import {
  autoscaleX,
  autoscaleY,
  compileExpression,
  sampleFunction,
  sampleParametric,
} from '../lib/functionGraph'
import { panViewport, zoomViewport } from '../lib/graphViewport'
import { pendulumAccel, projectileStep, rk4Step, springMassAccel } from '../lib/rk4'

const SUPPORTED_SIM_TYPES = new Set(['spring_mass', 'pendulum', 'projectile', 'function_graph'])

const CARD_CLASS =
  'pointer-events-auto absolute  bottom-[2%] right-[1%] w-100 rounded-2xl border border-chrome-border bg-chrome-bg text-[13px] text-chrome-text shadow-[0_8px_24px_rgba(0,0,0,0.45)] backdrop-blur-lg accent-accent'
const FORMULA_CLASS = 'my-1.5 font-mono text-chrome-muted'
const SLIDER_ROW_CLASS = 'my-2.5 px-2'
const SLIDER_ROW_HEADER_CLASS = 'mb-1 flex items-baseline justify-between gap-2'
const SLIDER_LABEL_CLASS = 'text-[11px] text-chrome-muted'
const SLIDER_VALUE_CLASS = 'text-xs font-semibold text-chrome-text'
const CANVAS_CLASS = 'my-0 block rounded bg-[#0a0a0a]'

function parametersToState(parameters) {
  const state = {}
  for (const param of parameters) {
    state[param.key] = param.val
  }
  return state
}


// Shared canvas render loop: draws whatever `draw(ctx, state, width, height)`
// wants, advancing `state` one RK4 sub-step at a time via `step`. Kept
// generic so each sim type only supplies its own step/draw functions,
// mirroring the "one generic rk4Step, three accel functions" structure in
// lib/rk4.js.
function useSimulationCanvas(step, draw, deps) {
  const canvasRef = useRef(null)
  const stateRef = useRef(null)

  useEffect(() => {
    stateRef.current = null // reset on parameter change
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps)

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return undefined
    const ctx = canvas.getContext && canvas.getContext('2d')
    let rafId

    const frame = () => {
      stateRef.current = step(stateRef.current)
      if (ctx) {
        draw(ctx, stateRef.current, canvas.width, canvas.height)
      }
      rafId = requestAnimationFrame(frame)
    }
    rafId = requestAnimationFrame(frame)
    return () => cancelAnimationFrame(rafId)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps)

  return canvasRef
}

const SUBSTEPS_PER_FRAME = 4
const FRAME_DT = 1 / 60 / SUBSTEPS_PER_FRAME

function SpringMassWidget({ values }) {
  const { k, m } = values
  const canvasRef = useSimulationCanvas(
    (state) => {
      let position = state?.position ?? 1
      let velocity = state?.velocity ?? 0
      const accel = springMassAccel(k, m)
      for (let i = 0; i < SUBSTEPS_PER_FRAME; i += 1) {
        const next = rk4Step(position, velocity, 0, FRAME_DT, accel)
        position = next.position
        velocity = next.velocity
      }
      return { position, velocity }
    },
    (ctx, state, width, height) => {
      ctx.clearRect(0, 0, width, height)
      const centerX = width / 2
      const centerY = height / 2
      const bobX = centerX + state.position * (width / 6)
      ctx.strokeStyle = '#8ab4f8'
      ctx.beginPath()
      ctx.moveTo(centerX, 10)
      ctx.lineTo(bobX, centerY)
      ctx.stroke()
      ctx.fillStyle = '#8ab4f8'
      ctx.beginPath()
      ctx.arc(bobX, centerY, 10, 0, Math.PI * 2)
      ctx.fill()
    },
    [k, m]
  )
  return <canvas ref={canvasRef} width={240} height={250} className={CANVAS_CLASS} />
}

function PendulumWidget({ values }) {
  const { g, L } = values
  const canvasRef = useSimulationCanvas(
    (state) => {
      let theta = state?.theta ?? Math.PI / 3
      let thetaDot = state?.thetaDot ?? 0
      const accel = pendulumAccel(g, L)
      for (let i = 0; i < SUBSTEPS_PER_FRAME; i += 1) {
        const next = rk4Step(theta, thetaDot, 0, FRAME_DT, accel)
        theta = next.position
        thetaDot = next.velocity
      }
      return { theta, thetaDot }
    },
    (ctx, state, width, height) => {
      ctx.clearRect(0, 0, width, height)
      const pivotX = width / 2
      const pivotY = 20
      const armLength = Math.min(width, height) * 0.6
      const bobX = pivotX + armLength * Math.sin(state.theta)
      const bobY = pivotY + armLength * Math.cos(state.theta)
      ctx.strokeStyle = '#f6a776'
      ctx.beginPath()
      ctx.moveTo(pivotX, pivotY)
      ctx.lineTo(bobX, bobY)
      ctx.stroke()
      ctx.fillStyle = '#f6a776'
      ctx.beginPath()
      ctx.arc(bobX, bobY, 10, 0, Math.PI * 2)
      ctx.fill()
    },
    [g, L]
  )
  return <canvas ref={canvasRef} width={240} height={160} className={CANVAS_CLASS} />
}

function ProjectileWidget({ values }) {
  const { v0, angle, g } = values
  const canvasRef = useSimulationCanvas(
    (state) => {
      if (!state || state.y < 0) {
        const radians = (angle * Math.PI) / 180
        return {
          x: 0,
          vx: v0 * Math.cos(radians),
          y: 0,
          vy: v0 * Math.sin(radians),
          t: 0,
          trail: [],
        }
      }
      let next = state
      for (let i = 0; i < SUBSTEPS_PER_FRAME; i += 1) {
        next = projectileStep(next, FRAME_DT, g)
      }
      const trail = [...state.trail, { x: next.x, y: next.y }].slice(-200)
      return { ...next, trail }
    },
    (ctx, state, width, height) => {
      ctx.clearRect(0, 0, width, height)
      const scale = 4
      const originX = 10
      const originY = height - 10
      ctx.strokeStyle = '#8bd3a0'
      ctx.beginPath()
      state.trail.forEach((point, index) => {
        const px = originX + point.x * scale
        const py = originY - point.y * scale
        if (index === 0) ctx.moveTo(px, py)
        else ctx.lineTo(px, py)
      })
      ctx.stroke()
    },
    [v0, angle, g]
  )
  return <canvas ref={canvasRef} width={240} height={160} className={CANVAS_CLASS} />
}

// function_graph (any math expressible as y = f(x) OR, for curves that
// fail the vertical-line test like a circle, as a parametric x(t)/y(t) --
// docs/adr/0006) isn't a differential equation -- no RK4 integrator
// applies, just algebra -- so instead of animating over time like the
// physics widgets above, it's a static curve plot (lib/functionGraph.js
// evaluates expressions via mathjs) with an interactive x/t slider (local
// UI state, not one of the AI-returned `parameters`) that moves a point
// along the curve. The non-x/t `parameters` (e.g. a/b/c for a quadratic,
// or r for a circle) still reshape the curve via the shared
// `ParameterSliders` rendered in `SimulationWidget`. Pan (drag) and zoom
// (wheel) are supported directly on the canvas -- see useGraphInteraction.
const DEFAULT_X_DOMAIN = 10
const PARAMETRIC_T_RANGE = [0, 2 * Math.PI]
const ZOOM_IN_FACTOR = 0.85
const ZOOM_OUT_FACTOR = 1 / ZOOM_IN_FACTOR
// Double-tap-to-zoom (the marker-compatible zoom gesture, see
// useMarkerGraphInteraction): a single tracked device has no "scroll
// wheel" signal, so zoom instead triggers on two touch-downs close
// together in both time and position.
const DOUBLE_TAP_WINDOW_MS = 400
const DOUBLE_TAP_MAX_DISTANCE_PX = 30
const DOUBLE_TAP_ZOOM_FACTOR = 0.5

// Evaluates `compiled` with the given scope (parameter values merged with
// whichever independent variable applies -- `x` for an explicit y = f(x),
// `t` for a parametric curve) -- shared by the live cursor readout and the
// canvas renderer's curve sampling so there's exactly one evaluation path,
// not two that could disagree.
function evaluateAt(compiled, scope) {
  try {
    const result = compiled.evaluate(scope)
    return Number.isFinite(result) ? result : NaN
  } catch {
    return NaN
  }
}

const GRAPH_MARGIN = 28 // px reserved for axis tick labels

// A single, shared pixel<->data-space projection -- used by both the
// drawing code and the pan/zoom interaction handlers below, so they can
// never disagree about where a data point lands on screen.
function makeProjection(viewport, plotLeft, plotRight, plotTop, plotBottom) {
  const { xMin, xMax, yMin, yMax } = viewport
  const xSpan = xMax - xMin || 1
  const ySpan = yMax - yMin || 1
  const plotWidth = plotRight - plotLeft
  const plotHeight = plotBottom - plotTop

  return {
    toPx(vx, vy) {
      return [plotLeft + ((vx - xMin) / xSpan) * plotWidth, plotBottom - ((vy - yMin) / ySpan) * plotHeight]
    },
    toData(px, py) {
      return [xMin + ((px - plotLeft) / plotWidth) * xSpan, yMin + ((plotBottom - py) / plotHeight) * ySpan]
    },
  }
}

// Traces `pixelPoints` ([px, py] pairs, already projected) as a smooth
// curve instead of straight segments between raw samples -- the classic
// "quadratic curve through midpoints" technique: each sampled point
// becomes a control point pulling the curve toward it, while the curve
// itself passes through the midpoint of each consecutive pair, so corners
// get rounded rather than kinked. Purely cosmetic -- the underlying sample
// points (and therefore the math) are unchanged; only the strokeback
// path between them is smoothed. `closed` additionally smooths the
// wrap-around segment (parametric curves like a circle) instead of
// leaving a sharp seam where the path loops back to its start.
function traceSmoothPath(ctx, pixelPoints, closed) {
  const n = pixelPoints.length
  if (n === 0) return
  if (n === 1) {
    ctx.moveTo(...pixelPoints[0])
    return
  }
  const mid = (a, b) => [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2]

  if (closed) {
    ctx.moveTo(...mid(pixelPoints[n - 1], pixelPoints[0]))
    for (let i = 0; i < n; i += 1) {
      const next = pixelPoints[(i + 1) % n]
      ctx.quadraticCurveTo(...pixelPoints[i], ...mid(pixelPoints[i], next))
    }
  } else {
    ctx.moveTo(...pixelPoints[0])
    for (let i = 1; i < n - 1; i += 1) {
      ctx.quadraticCurveTo(...pixelPoints[i], ...mid(pixelPoints[i], pixelPoints[i + 1]))
    }
    ctx.lineTo(...pixelPoints[n - 1])
  }
}

function drawFunctionGraph(canvas, { points, cursor, viewport, closed }) {
  const ctx = canvas.getContext('2d')
  if (!ctx) return
  const { width, height } = canvas
  const plotLeft = GRAPH_MARGIN
  const plotRight = width
  const plotTop = 4
  const plotBottom = height - GRAPH_MARGIN
  const { xMin, xMax, yMin, yMax } = viewport
  const { toPx } = makeProjection(viewport, plotLeft, plotRight, plotTop, plotBottom)

  ctx.clearRect(0, 0, width, height)
  ctx.font = '9px ui-sans-serif, system-ui, sans-serif'
  ctx.fillStyle = '#6b7280'

  // Grid + tick labels, computed from the current (possibly zoomed/panned)
  // viewport so they're always meaningful.
  for (const tick of niceTicks(xMin, xMax, 5)) {
    const [px] = toPx(tick, 0)
    ctx.strokeStyle = '#222'
    ctx.beginPath()
    ctx.moveTo(px, plotTop)
    ctx.lineTo(px, plotBottom)
    ctx.stroke()
    ctx.textAlign = 'center'
    ctx.fillText(String(tick), px, plotBottom + 12)
  }
  for (const tick of niceTicks(yMin, yMax, 4)) {
    const [, py] = toPx(0, tick)
    ctx.strokeStyle = '#222'
    ctx.beginPath()
    ctx.moveTo(plotLeft, py)
    ctx.lineTo(plotRight, py)
    ctx.stroke()
    ctx.textAlign = 'right'
    ctx.fillText(String(tick), plotLeft - 4, py + 3)
  }

  if (yMin <= 0 && yMax >= 0) {
    ctx.strokeStyle = '#6b7280'
    ctx.beginPath()
    const [axX0, axY0] = toPx(xMin, 0)
    const [axX1, axY1] = toPx(xMax, 0)
    ctx.moveTo(axX0, axY0)
    ctx.lineTo(axX1, axY1)
    ctx.stroke()
  }

  ctx.strokeStyle = '#c792ea'
  ctx.lineWidth = 2
  ctx.lineJoin = 'round'
  ctx.lineCap = 'round'
  ctx.beginPath()
  traceSmoothPath(ctx, points.map((p) => toPx(p.x, p.y)), closed)
  ctx.stroke()

  if (cursor && Number.isFinite(cursor.x) && Number.isFinite(cursor.y)) {
    const [pointX, pointY] = toPx(cursor.x, cursor.y)
    ctx.fillStyle = '#ffd166'
    ctx.beginPath()
    ctx.arc(pointX, pointY, 5, 0, Math.PI * 2)
    ctx.fill()
  }
}

// Wheel-to-zoom only (centered on the cursor, not just the viewport
// center) -- a genuine local DOM event on this specific element, unrelated
// to useDrawSuppression's concern (which only gates the *whiteboard*
// canvas's ink). Drag-to-pan is deliberately NOT a native pointer listener
// here -- see useMarkerGraphInteraction below for why panning instead goes
// through the same TRACK_UPDATE stream the whiteboard itself uses, so the
// real Stylus (which has no OS-level pointer events at all, only a
// position broadcast) can pan the same way a mouse does, instead of only
// ever working for whichever input happens to fire real DOM events.
function useWheelZoom(canvasRef, viewport, setViewport) {
  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return undefined

    const onWheel = (event) => {
      event.preventDefault()
      const rect = canvas.getBoundingClientRect()
      const px = event.clientX - rect.left
      const py = event.clientY - rect.top
      const { toData } = makeProjection(viewport, GRAPH_MARGIN, canvas.width, 4, canvas.height - GRAPH_MARGIN)
      const [cx, cy] = toData(px, py)
      const factor = event.deltaY < 0 ? ZOOM_IN_FACTOR : ZOOM_OUT_FACTOR
      setViewport((current) => zoomViewport(current, { cx, cy, factor }))
    }

    canvas.addEventListener('wheel', onWheel, { passive: false })
    return () => canvas.removeEventListener('wheel', onWheel)
  }, [canvasRef, viewport, setViewport])
}

// Pans the graph via the SAME TRACK_UPDATE stream that draws ink on the
// whiteboard, not a native DOM pointer listener -- the real Stylus has no
// OS-level pointer events at all (its position arrives only as this
// broadcast), so a native-events-only pan would simply never work once
// real hardware replaces mouse-fallback. Reading `latestTrackRef` on a
// requestAnimationFrame loop (not React state) matches Canvas.jsx's own
// pattern for the same 60fps stream. Double-tap (two touch-downs close in
// time and position) zooms, since a single tracked point has no "scroll
// wheel" equivalent -- see the DOUBLE_TAP_* constants.
function useMarkerGraphInteraction(canvasRef, latestTrackRef, viewportRef, setViewport) {
  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas || !latestTrackRef) return undefined

    let rafId
    let wasTouchingGlobally = false
    // Whether the CURRENT touch gesture (from press to release) belongs to
    // this widget -- decided ONCE at the true rising edge of `is_touching`
    // (a fresh press, not merely "position re-entered the bounds"), and
    // held fixed for the gesture's whole duration. Without this, a
    // whiteboard stroke that starts elsewhere and merely sweeps across the
    // widget's on-screen area mid-drag would be misread as a fresh press
    // here on every frame its position happens to overlap, hijacking pan
    // with the stroke's own movement -- exactly the bug this guards
    // against. Mirrors useDrawSuppression's "decided once at pointerdown"
    // principle for the analogous whiteboard-vs-chrome ambiguity.
    let gestureOwnsWidget = false
    let lastScreen = null
    let lastTap = null // { time, x, y }

    const loop = () => {
      const message = latestTrackRef.current
      const touchingNow = Boolean(message?.is_detected && message.is_touching)

      if (touchingNow && !wasTouchingGlobally) {
        const rect = canvas.getBoundingClientRect()
        const screenX = message.x * window.innerWidth
        const screenY = message.y * window.innerHeight
        gestureOwnsWidget =
          screenX >= rect.left && screenX <= rect.right && screenY >= rect.top && screenY <= rect.bottom

        if (gestureOwnsWidget) {
          const now = performance.now()
          if (
            lastTap &&
            now - lastTap.time < DOUBLE_TAP_WINDOW_MS &&
            Math.hypot(screenX - lastTap.x, screenY - lastTap.y) < DOUBLE_TAP_MAX_DISTANCE_PX
          ) {
            const { toData } = makeProjection(
              viewportRef.current,
              GRAPH_MARGIN,
              canvas.width,
              4,
              canvas.height - GRAPH_MARGIN
            )
            const [cx, cy] = toData(screenX - rect.left, screenY - rect.top)
            setViewport((current) => zoomViewport(current, { cx, cy, factor: DOUBLE_TAP_ZOOM_FACTOR }))
            lastTap = null
            // The double-tap itself isn't a drag -- don't also start
            // panning from this same press.
            gestureOwnsWidget = false
          } else {
            lastTap = { time: now, x: screenX, y: screenY }
          }
        }
        lastScreen = gestureOwnsWidget ? { x: screenX, y: screenY } : null
      } else if (touchingNow && gestureOwnsWidget && lastScreen) {
        // Continuing a gesture this widget already owns -- pan regardless
        // of whether the position has since drifted outside the bounds
        // (normal drag behavior); bounds are never re-checked mid-gesture.
        const screenX = message.x * window.innerWidth
        const screenY = message.y * window.innerHeight
        const plotWidth = canvas.width - GRAPH_MARGIN
        const plotHeight = canvas.height - GRAPH_MARGIN - 4
        const dxPx = screenX - lastScreen.x
        const dyPx = screenY - lastScreen.y
        lastScreen = { x: screenX, y: screenY }
        setViewport((current) => {
          const xSpan = current.xMax - current.xMin
          const ySpan = current.yMax - current.yMin
          const dx = -(dxPx / plotWidth) * xSpan
          const dy = (dyPx / plotHeight) * ySpan
          return panViewport(current, { dx, dy })
        })
      } else if (!touchingNow) {
        gestureOwnsWidget = false
        lastScreen = null
      }

      wasTouchingGlobally = touchingNow
      rafId = requestAnimationFrame(loop)
    }
    rafId = requestAnimationFrame(loop)
    return () => cancelAnimationFrame(rafId)
  }, [canvasRef, latestTrackRef, viewportRef, setViewport])
}

function FunctionGraphWidget({ expression, parametricX, parametricY, values, latestTrackRef }) {
  const isParametric = !expression && parametricX && parametricY
  const [t, setT] = useState(0)
  const canvasRef = useRef(null)

  const compiled = useMemo(() => compileExpression(expression ?? ''), [expression])
  const compiledX = useMemo(() => (isParametric ? compileExpression(parametricX) : null), [isParametric, parametricX])
  const compiledY = useMemo(() => (isParametric ? compileExpression(parametricY) : null), [isParametric, parametricY])
  const ready = isParametric ? compiledX && compiledY : Boolean(compiled)

  // Lazy initializer: computed once on mount (i.e. once per widget_id,
  // since SimulationWidget is keyed by it), not on every parameter-slider
  // change -- otherwise a manual pan/zoom would snap back to the default
  // view the instant a slider was nudged.
  const [viewport, setViewport] = useState(() => {
    if (isParametric && compiledX && compiledY) {
      const initial = sampleParametric(compiledX, compiledY, values, ...PARAMETRIC_T_RANGE)
      const [xMin, xMax] = autoscaleX(initial)
      const [yMin, yMax] = autoscaleY(initial)
      return { xMin, xMax, yMin, yMax }
    }
    if (compiled) {
      const initial = sampleFunction(compiled, values, -DEFAULT_X_DOMAIN, DEFAULT_X_DOMAIN)
      const [yMin, yMax] = autoscaleY(initial)
      return { xMin: -DEFAULT_X_DOMAIN, xMax: DEFAULT_X_DOMAIN, yMin, yMax }
    }
    return { xMin: -DEFAULT_X_DOMAIN, xMax: DEFAULT_X_DOMAIN, yMin: -DEFAULT_X_DOMAIN, yMax: DEFAULT_X_DOMAIN }
  })

  const points = useMemo(() => {
    if (isParametric) {
      return compiledX && compiledY ? sampleParametric(compiledX, compiledY, values, ...PARAMETRIC_T_RANGE) : []
    }
    return compiled ? sampleFunction(compiled, values, viewport.xMin, viewport.xMax) : []
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isParametric, compiled, compiledX, compiledY, values, viewport.xMin, viewport.xMax])

  const cursor = useMemo(() => {
    if (!ready) return null
    if (isParametric) {
      return {
        x: evaluateAt(compiledX, { ...values, t }),
        y: evaluateAt(compiledY, { ...values, t }),
      }
    }
    return { x: t, y: evaluateAt(compiled, { ...values, x: t }) }
  }, [ready, isParametric, compiled, compiledX, compiledY, values, t])

  const viewportRef = useRef(viewport)
  viewportRef.current = viewport

  useWheelZoom(canvasRef, viewport, setViewport)
  useMarkerGraphInteraction(canvasRef, latestTrackRef, viewportRef, setViewport)

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas || !ready) return undefined

    // Sized to the parent card's actual available width (not a hardcoded
    // constant) so the graph never overflows its container regardless of
    // widget card width -- re-measured on resize since the widget is
    // positioned with percentage offsets (SPEC.md 3.3) that can change
    // with the viewport.
    const draw = () => {
      canvas.width = canvas.clientWidth
      canvas.height = 160
      drawFunctionGraph(canvas, { points, cursor, viewport, closed: isParametric })
    }
    draw()

    window.addEventListener('resize', draw)
    return () => window.removeEventListener('resize', draw)
  }, [ready, points, cursor, viewport, isParametric])

  if (!ready) {
    return (
      <div className="text-[13px] text-amber-400">
        Couldn't render this function — the AI's expression didn't parse.
      </div>
    )
  }

  const sliderMin = isParametric ? PARAMETRIC_T_RANGE[0] : viewport.xMin
  const sliderMax = isParametric ? PARAMETRIC_T_RANGE[1] : viewport.xMax

  return (
    <div>
      <canvas
        ref={canvasRef}
        height={200}
        className={`${CANVAS_CLASS} h-100 w-full touch-none`}
      />
      <div className={SLIDER_ROW_CLASS}>
        <div className={SLIDER_ROW_HEADER_CLASS}>
          <label htmlFor="sim-function-graph-x" className={SLIDER_LABEL_CLASS}>
            {isParametric ? 't' : 'x'}
          </label>
          <span data-testid="function-graph-y-value" className={SLIDER_VALUE_CLASS}>
            {isParametric
              ? `(x, y) = (${Number.isFinite(cursor.x) ? cursor.x.toFixed(2) : 'undefined'}, ${Number.isFinite(cursor.y) ? cursor.y.toFixed(2) : 'undefined'
              })`
              : `y = ${Number.isFinite(cursor.y) ? cursor.y.toFixed(2) : 'undefined'}`}
          </span>
        </div>
        <input
          id="sim-function-graph-x"
          type="range"
          className="block w-full"
          min={sliderMin}
          max={sliderMax}
          step={(sliderMax - sliderMin) / 200 || 0.1}
          value={t}
          onChange={(event) => setT(Number(event.target.value))}
        />
      </div>
    </div>
  )
}

function SimulationCanvas({ simType, values, expression, parametricX, parametricY, latestTrackRef }) {
  switch (simType) {
    case 'spring_mass':
      return <SpringMassWidget values={values} />
    case 'pendulum':
      return <PendulumWidget values={values} />
    case 'projectile':
      return <ProjectileWidget values={values} />
    case 'function_graph':
      return (
        <FunctionGraphWidget
          expression={expression}
          parametricX={parametricX}
          parametricY={parametricY}
          values={values}
          latestTrackRef={latestTrackRef}
        />
      )
    default:
      return null
  }
}

function UnsupportedWidget({ widget }) {
  const title = widget.title ?? 'Unknown concept'
  const formula = widget.formula_latex
  const attemptedSimType = widget.attempted_sim_type ?? widget.sim_type

  return (
    <div className={`${CARD_CLASS} border-amber-800 text-amber-400`} data-widget-id={widget.widget_id}>
      <h3 className="font-semibold">{title}</h3>
      {formula && <div className={FORMULA_CLASS}>{formula}</div>}
      <p className="text-[13px]">Concept detected, but not yet supported ({attemptedSimType}).</p>
    </div>
  )
}

export function SimulationWidget({ widget, latestTrackRef }) {
  // No slider controls for the formula's own parameters (m/b, radius, k/m,
  // ...) -- the curve/simulation always runs with the AI's own default
  // values, so this never needs to change after mount.
  const values = parametersToState(widget.parameters ?? [])

  const isSpawnable =
    widget.type === 'AI_WIDGET_SPAWN' && SUPPORTED_SIM_TYPES.has(widget.sim_type)

  if (!isSpawnable) {
    return <UnsupportedWidget widget={widget} />
  }

  return (
    <div className={CARD_CLASS} data-widget-id={widget.widget_id}>
      <SimulationCanvas
        simType={widget.sim_type}
        values={values}
        expression={widget.expression}
        parametricX={widget.parametric_x}
        parametricY={widget.parametric_y}
        latestTrackRef={latestTrackRef}
      />
      <div className="px-2">
        <h3 className="font-semibold">{widget.title}</h3>
        <div className={FORMULA_CLASS}>{widget.formula_latex}</div>
      </div>
    </div>
  )
}
