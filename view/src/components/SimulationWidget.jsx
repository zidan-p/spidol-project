// Fixed-enum physics/math widget (SPEC.md 3.3 Simulation Widgets,
// GLOSSARY.md: Simulation Type). spring_mass/pendulum/projectile are each
// rendered by their own hand-written RK4 integrator (no general physics
// library, see lib/rk4.js); linear_function is pure algebra (no RK4, see
// LinearFunctionWidget) with an interactive x slider instead of time-based
// animation. All four have real-time parameter sliders editable via mouse.
// A distinct "concept detected but not yet supported" state is rendered for
// AI_WIDGET_UNSUPPORTED (and, defensively, for any AI_WIDGET_SPAWN whose
// sim_type somehow isn't one of the four fixed renderers) rather than
// crashing or doing nothing.
import { useEffect, useRef, useState } from 'react'
import { decimalPlacesForStep, niceStep } from '../lib/niceStep'
import { pendulumAccel, projectileStep, rk4Step, springMassAccel } from '../lib/rk4'

const SUPPORTED_SIM_TYPES = new Set(['spring_mass', 'pendulum', 'projectile', 'linear_function'])

function parametersToState(parameters) {
  const state = {}
  for (const param of parameters) {
    state[param.key] = param.val
  }
  return state
}

function ParameterSliders({ parameters, values, onChange }) {
  return (
    <div className="sim-widget-sliders">
      {parameters.map((param) => {
        // A "nice" (1/2/5 x 10^n) step instead of the raw (max-min)/200:
        // that produced awkward steps like 0.45, so dragging the slider
        // drifted unpredictably between clean integers and long decimal
        // tails. See lib/niceStep.js.
        const step = niceStep(param.min, param.max)
        const decimals = decimalPlacesForStep(step)
        return (
          <div className="sim-widget-slider-row" key={param.key}>
            <label htmlFor={`sim-param-${param.key}`}>{param.label}</label>
            <input
              id={`sim-param-${param.key}`}
              type="range"
              min={param.min}
              max={param.max}
              step={step}
              value={values[param.key]}
              onChange={(event) =>
                onChange(param.key, Number(Number(event.target.value).toFixed(decimals)))
              }
            />
            <span data-testid={`param-value-${param.key}`}>{values[param.key]}</span>
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
  return <canvas ref={canvasRef} width={240} height={160} className="sim-widget-canvas" />
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
  return <canvas ref={canvasRef} width={240} height={160} className="sim-widget-canvas" />
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
  return <canvas ref={canvasRef} width={240} height={160} className="sim-widget-canvas" />
}

// Linear Function (y = m*x + b) isn't a differential equation -- no RK4
// integrator applies here, just algebra -- so instead of animating over
// time like the physics widgets above, it's a static line plot with an
// interactive `x` slider (local UI state, not one of the AI-returned
// `parameters`) that moves a point along the line and shows the live y
// value. The `m`/`b` sliders from `parameters` still reshape the line
// itself via the shared `ParameterSliders` rendered in `SimulationWidget`.
const LINEAR_FUNCTION_DOMAIN = 10

function LinearFunctionWidget({ values }) {
  const { m, b } = values
  const [x, setX] = useState(0)
  const y = m * x + b
  const canvasRef = useRef(null)

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext && canvas.getContext('2d')
    if (!ctx) return
    const { width, height } = canvas
    const domain = LINEAR_FUNCTION_DOMAIN
    const toPx = (vx, vy) => [
      (vx + domain) * (width / (2 * domain)),
      height - (vy + domain) * (height / (2 * domain)),
    ]

    ctx.clearRect(0, 0, width, height)

    ctx.strokeStyle = '#555'
    ctx.beginPath()
    const [axX0, axY0] = toPx(-domain, 0)
    const [axX1, axY1] = toPx(domain, 0)
    ctx.moveTo(axX0, axY0)
    ctx.lineTo(axX1, axY1)
    const [ayX0, ayY0] = toPx(0, -domain)
    const [ayX1, ayY1] = toPx(0, domain)
    ctx.moveTo(ayX0, ayY0)
    ctx.lineTo(ayX1, ayY1)
    ctx.stroke()

    ctx.strokeStyle = '#c792ea'
    ctx.beginPath()
    const [lineX0, lineY0] = toPx(-domain, m * -domain + b)
    const [lineX1, lineY1] = toPx(domain, m * domain + b)
    ctx.moveTo(lineX0, lineY0)
    ctx.lineTo(lineX1, lineY1)
    ctx.stroke()

    const [pointX, pointY] = toPx(x, y)
    ctx.fillStyle = '#ffd166'
    ctx.beginPath()
    ctx.arc(pointX, pointY, 6, 0, Math.PI * 2)
    ctx.fill()
  }, [m, b, x, y])

  return (
    <div className="sim-widget-linear-function">
      <canvas ref={canvasRef} width={240} height={160} className="sim-widget-canvas" />
      <div className="sim-widget-slider-row">
        <label htmlFor="sim-linear-function-x">x</label>
        <input
          id="sim-linear-function-x"
          type="range"
          min={-LINEAR_FUNCTION_DOMAIN}
          max={LINEAR_FUNCTION_DOMAIN}
          step={0.1}
          value={x}
          onChange={(event) => setX(Number(event.target.value))}
        />
        <span data-testid="linear-function-y-value">y = {y.toFixed(2)}</span>
      </div>
    </div>
  )
}

function SimulationCanvas({ simType, values }) {
  switch (simType) {
    case 'spring_mass':
      return <SpringMassWidget values={values} />
    case 'pendulum':
      return <PendulumWidget values={values} />
    case 'projectile':
      return <ProjectileWidget values={values} />
    case 'linear_function':
      return <LinearFunctionWidget values={values} />
    default:
      return null
  }
}

function UnsupportedWidget({ widget }) {
  const title = widget.title ?? 'Unknown concept'
  const formula = widget.formula_latex
  const attemptedSimType = widget.attempted_sim_type ?? widget.sim_type

  return (
    <div className="sim-widget sim-widget-unsupported" data-widget-id={widget.widget_id}>
      <h3>{title}</h3>
      {formula && <div className="sim-widget-formula">{formula}</div>}
      <p className="sim-widget-unsupported-message">
        Concept detected, but not yet supported ({attemptedSimType}).
      </p>
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
    <div className="sim-widget" data-widget-id={widget.widget_id}>
      <h3>{widget.title}</h3>
      <div className="sim-widget-formula">{widget.formula_latex}</div>
      <SimulationCanvas simType={widget.sim_type} values={values} />
      <ParameterSliders parameters={widget.parameters} values={values} onChange={handleChange} />
    </div>
  )
}
