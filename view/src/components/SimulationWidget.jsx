// Fixed-enum physics widget (SPEC.md 3.3 Simulation Widgets, GLOSSARY.md:
// Simulation Type). Each Simulation Type is rendered by its own
// hand-written RK4 integrator (no general physics library, see
// lib/rk4.js), with real-time parameter sliders editable via mouse. A
// distinct "concept detected but not yet supported" state is rendered for
// AI_WIDGET_UNSUPPORTED (and, defensively, for any AI_WIDGET_SPAWN whose
// sim_type somehow isn't one of the three fixed renderers) rather than
// crashing or doing nothing.
import { useEffect, useRef, useState } from 'react'
import { pendulumAccel, projectileStep, rk4Step, springMassAccel } from '../lib/rk4'

const SUPPORTED_SIM_TYPES = new Set(['spring_mass', 'pendulum', 'projectile'])

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
      {parameters.map((param) => (
        <div className="sim-widget-slider-row" key={param.key}>
          <label htmlFor={`sim-param-${param.key}`}>{param.label}</label>
          <input
            id={`sim-param-${param.key}`}
            type="range"
            min={param.min}
            max={param.max}
            step={(param.max - param.min) / 200 || 1}
            value={values[param.key]}
            onChange={(event) => onChange(param.key, Number(event.target.value))}
          />
          <span data-testid={`param-value-${param.key}`}>{values[param.key]}</span>
        </div>
      ))}
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

function SimulationCanvas({ simType, values }) {
  switch (simType) {
    case 'spring_mass':
      return <SpringMassWidget values={values} />
    case 'pendulum':
      return <PendulumWidget values={values} />
    case 'projectile':
      return <ProjectileWidget values={values} />
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
