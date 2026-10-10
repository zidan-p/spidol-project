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
// All sim types have real-time parameter sliders editable via mouse. A
// distinct "concept detected but not yet supported" state is rendered for
// AI_WIDGET_UNSUPPORTED (and, defensively, for any AI_WIDGET_SPAWN whose
// sim_type isn't one of these) rather than crashing or doing nothing.
import { useEffect, useMemo, useRef, useState } from 'react'
import { niceTicks } from '../lib/axisTicks'
import { autoscaleY, compileExpression, sampleFunction } from '../lib/functionGraph'
import { decimalPlacesForStep, niceStep } from '../lib/niceStep'
import { pendulumAccel, projectileStep, rk4Step, springMassAccel } from '../lib/rk4'

const SUPPORTED_SIM_TYPES = new Set(['spring_mass', 'pendulum', 'projectile', 'function_graph'])

const CARD_CLASS =
  'pointer-events-auto absolute top-[10%] right-[5%] w-70 rounded-2xl border border-chrome-border bg-chrome-bg p-4 px-4.5 text-[13px] text-chrome-text shadow-[0_8px_24px_rgba(0,0,0,0.45)] backdrop-blur-lg accent-accent'
const FORMULA_CLASS = 'my-1.5 font-mono text-chrome-muted'
const SLIDER_ROW_CLASS = 'my-2.5'
const SLIDER_ROW_HEADER_CLASS = 'mb-1 flex items-baseline justify-between gap-2'
const SLIDER_LABEL_CLASS = 'text-[11px] text-chrome-muted'
const SLIDER_VALUE_CLASS = 'text-xs font-semibold text-chrome-text'
const CANVAS_CLASS = 'my-2 block rounded bg-[#0a0a0a]'

function parametersToState(parameters) {
  const state = {}
  for (const param of parameters) {
    state[param.key] = param.val
  }
  return state
}

function ParameterSliders({ parameters, values, onChange }) {
  return (
    <div>
      {parameters.map((param) => {
        // A "nice" (1/2/5 x 10^n) step instead of the raw (max-min)/200:
        // that produced awkward steps like 0.45, so dragging the slider
        // drifted unpredictably between clean integers and long decimal
        // tails. See lib/niceStep.js.
        const step = niceStep(param.min, param.max)
        const decimals = decimalPlacesForStep(step)
        return (
          <div className={SLIDER_ROW_CLASS} key={param.key}>
            <div className={SLIDER_ROW_HEADER_CLASS}>
              <label htmlFor={`sim-param-${param.key}`} className={SLIDER_LABEL_CLASS}>
                {param.label}
              </label>
              <span data-testid={`param-value-${param.key}`} className={SLIDER_VALUE_CLASS}>
                {values[param.key]}
              </span>
            </div>
            <input
              id={`sim-param-${param.key}`}
              type="range"
              className="block w-full"
              min={param.min}
              max={param.max}
              step={step}
              value={values[param.key]}
              onChange={(event) =>
                onChange(param.key, Number(Number(event.target.value).toFixed(decimals)))
              }
            />
          </div>
        )
      })}
    </div>
  )
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
  return <canvas ref={canvasRef} width={240} height={160} className={CANVAS_CLASS} />
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

// function_graph (any y = f(x): linear, quadratic, trig, exponential, ...)
// isn't a differential equation -- no RK4 integrator applies, just
// algebra -- so instead of animating over time like the physics widgets
// above, it's a static curve plot (lib/functionGraph.js evaluates
// `expression` via mathjs) with an interactive `x` slider (local UI state,
// not one of the AI-returned `parameters`) that moves a point along the
// curve and shows the live y value. The non-x `parameters` (e.g. a/b/c for
// a quadratic) still reshape the curve via the shared `ParameterSliders`
// rendered in `SimulationWidget`.
const FUNCTION_GRAPH_X_DOMAIN = 10

// Evaluates `compiled` at a given x, merging in the current parameter
// values -- shared by the live y-readout and the canvas renderer's curve
// sampling so there's exactly one evaluation path, not two that could
// disagree.
function evaluateAt(compiled, values, x) {
  try {
    const result = compiled.evaluate({ ...values, x })
    return Number.isFinite(result) ? result : NaN
  } catch {
    return NaN
  }
}

const GRAPH_MARGIN = 28 // px reserved for axis tick labels

function drawFunctionGraph(canvas, { points, x, y, xDomain, yMin, yMax }) {
  const ctx = canvas.getContext('2d')
  if (!ctx) return
  const { width, height } = canvas
  const plotLeft = GRAPH_MARGIN
  const plotRight = width
  const plotTop = 4
  const plotBottom = height - GRAPH_MARGIN

  const toPx = (vx, vy) => [
    plotLeft + ((vx + xDomain) / (2 * xDomain)) * (plotRight - plotLeft),
    plotBottom - ((vy - yMin) / (yMax - yMin || 1)) * (plotBottom - plotTop),
  ]

  ctx.clearRect(0, 0, width, height)
  ctx.font = '9px ui-sans-serif, system-ui, sans-serif'
  ctx.fillStyle = '#6b7280'

  // Grid + tick labels, computed from the actual plotted range so they're
  // always meaningful even as parameter sliders reshape the curve (unlike
  // a fixed domain, which would make slider changes hard to perceive).
  for (const tick of niceTicks(-xDomain, xDomain, 5)) {
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
    const [axX0, axY0] = toPx(-xDomain, 0)
    const [axX1, axY1] = toPx(xDomain, 0)
    ctx.moveTo(axX0, axY0)
    ctx.lineTo(axX1, axY1)
    ctx.stroke()
  }

  ctx.strokeStyle = '#c792ea'
  ctx.lineWidth = 2
  ctx.beginPath()
  points.forEach((point, index) => {
    const [px, py] = toPx(point.x, point.y)
    if (index === 0) ctx.moveTo(px, py)
    else ctx.lineTo(px, py)
  })
  ctx.stroke()

  if (Number.isFinite(y)) {
    const [pointX, pointY] = toPx(x, y)
    ctx.fillStyle = '#ffd166'
    ctx.beginPath()
    ctx.arc(pointX, pointY, 5, 0, Math.PI * 2)
    ctx.fill()
  }
}

function FunctionGraphWidget({ expression, values }) {
  const [x, setX] = useState(0)
  const canvasRef = useRef(null)

  const compiled = useMemo(() => compileExpression(expression ?? ''), [expression])

  const points = useMemo(
    () =>
      compiled
        ? sampleFunction(compiled, values, -FUNCTION_GRAPH_X_DOMAIN, FUNCTION_GRAPH_X_DOMAIN)
        : [],
    [compiled, values]
  )

  const y = useMemo(() => (compiled ? evaluateAt(compiled, values, x) : NaN), [compiled, values, x])

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas || !compiled) return undefined

    const [yMin, yMax] = autoscaleY(points)

    // Sized to the parent card's actual available width (not a hardcoded
    // constant) so the graph never overflows its container regardless of
    // widget card width -- re-measured on resize since the widget is
    // positioned with percentage offsets (SPEC.md 3.3) that can change
    // with the viewport.
    const draw = () => {
      canvas.width = canvas.clientWidth
      canvas.height = 160
      drawFunctionGraph(canvas, { points, x, y, xDomain: FUNCTION_GRAPH_X_DOMAIN, yMin, yMax })
    }
    draw()

    window.addEventListener('resize', draw)
    return () => window.removeEventListener('resize', draw)
  }, [compiled, points, x, y])

  if (!compiled) {
    return <div className="text-[13px] text-amber-400">Couldn't render this function — the AI's expression didn't parse.</div>
  }

  return (
    <div>
      <canvas ref={canvasRef} height={160} className={`${CANVAS_CLASS} h-40 w-full`} />
      <div className={SLIDER_ROW_CLASS}>
        <div className={SLIDER_ROW_HEADER_CLASS}>
          <label htmlFor="sim-function-graph-x" className={SLIDER_LABEL_CLASS}>
            x
          </label>
          <span data-testid="function-graph-y-value" className={SLIDER_VALUE_CLASS}>
            y = {Number.isFinite(y) ? y.toFixed(2) : 'undefined'}
          </span>
        </div>
        <input
          id="sim-function-graph-x"
          type="range"
          className="block w-full"
          min={-FUNCTION_GRAPH_X_DOMAIN}
          max={FUNCTION_GRAPH_X_DOMAIN}
          step={0.1}
          value={x}
          onChange={(event) => setX(Number(event.target.value))}
        />
      </div>
    </div>
  )
}

function SimulationCanvas({ simType, values, expression }) {
  switch (simType) {
    case 'spring_mass':
      return <SpringMassWidget values={values} />
    case 'pendulum':
      return <PendulumWidget values={values} />
    case 'projectile':
      return <ProjectileWidget values={values} />
    case 'function_graph':
      return <FunctionGraphWidget expression={expression} values={values} />
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

export function SimulationWidget({ widget }) {
  const [values, setValues] = useState(() => parametersToState(widget.parameters ?? []))

  const isSpawnable =
    widget.type === 'AI_WIDGET_SPAWN' && SUPPORTED_SIM_TYPES.has(widget.sim_type)

  if (!isSpawnable) {
    return <UnsupportedWidget widget={widget} />
  }

  const handleChange = (key, value) => {
    setValues((prev) => ({ ...prev, [key]: value }))
  }

  return (
    <div className={CARD_CLASS} data-widget-id={widget.widget_id}>
      <h3 className="font-semibold">{widget.title}</h3>
      <div className={FORMULA_CLASS}>{widget.formula_latex}</div>
      <SimulationCanvas simType={widget.sim_type} values={values} expression={widget.expression} />
      <ParameterSliders parameters={widget.parameters} values={values} onChange={handleChange} />
    </div>
  )
}
