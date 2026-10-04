// Tests for the generic RK4 step and the three fixed Simulation Type
// accelerations (SPEC.md 3.3 Simulation Widgets / GLOSSARY.md: Simulation
// Type). Expected values come from independent physical reasoning (energy
// conservation, known analytic solutions), not by re-deriving the code's
// own arithmetic, per the TDD skill's anti-pattern guidance.
import { describe, expect, it } from 'vitest'
import {
  pendulumAccel,
  projectileStep,
  rk4Step,
  springMassAccel,
} from '../rk4'

describe('rk4Step', () => {
  it('integrates a constant acceleration exactly (projectile-style free fall)', () => {
    // a = -10 constant; after t=1s with dt=1, exact kinematics:
    // v = v0 + a*t = -10, x = x0 + v0*t + 0.5*a*t^2 = -5.
    // RK4 is exact for any polynomial up to degree <=3 in the a(x,v,t)
    // formulation used here, so this is a precise, independently-derivable
    // check, not a tautology against the implementation.
    const result = rk4Step(0, 0, 0, 1, () => -10)
    expect(result.position).toBeCloseTo(-5, 10)
    expect(result.velocity).toBeCloseTo(-10, 10)
  })

  it('conserves energy (approximately) for simple harmonic motion over many steps', () => {
    const k = 40
    const m = 1
    const accel = springMassAccel(k, m)
    let position = 1 // initial displacement
    let velocity = 0
    const dt = 1 / 240
    const steps = 240 * 2 // 2 seconds

    for (let i = 0; i < steps; i += 1) {
      const next = rk4Step(position, velocity, i * dt, dt, accel)
      position = next.position
      velocity = next.velocity
    }

    const energy = 0.5 * k * position * position + 0.5 * m * velocity * velocity
    const initialEnergy = 0.5 * k * 1 * 1
    expect(energy).toBeCloseTo(initialEnergy, 2)
  })
})

describe('springMassAccel', () => {
  it('computes a = -(k/m) * x', () => {
    const accel = springMassAccel(40, 2)
    expect(accel(3, 0, 0)).toBeCloseTo(-(40 / 2) * 3, 10)
  })
})

describe('pendulumAccel', () => {
  it('computes the full nonlinear a = -(g/L) * sin(theta)', () => {
    const g = 9.8
    const L = 1
    const accel = pendulumAccel(g, L)
    const theta = Math.PI / 4
    expect(accel(theta, 0, 0)).toBeCloseTo(-(g / L) * Math.sin(theta), 10)
  })

  it('is at equilibrium (zero acceleration) hanging straight down', () => {
    const accel = pendulumAccel(9.8, 1)
    expect(accel(0, 0, 0)).toBeCloseTo(0, 10)
  })
})

describe('projectileStep', () => {
  it('advances x at constant velocity (no horizontal acceleration) and y under gravity', () => {
    const state = { x: 0, vx: 5, y: 0, vy: 0, t: 0 }
    const next = projectileStep(state, 1, 10)

    expect(next.x).toBeCloseTo(5, 10) // no horizontal accel -> x = vx * t
    expect(next.vx).toBeCloseTo(5, 10)
    expect(next.y).toBeCloseTo(-5, 10) // y = -0.5*g*t^2
    expect(next.vy).toBeCloseTo(-10, 10)
    expect(next.t).toBeCloseTo(1, 10)
  })
})
