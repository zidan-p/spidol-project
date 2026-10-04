// Hand-written RK4 integrators for the three fixed Simulation Types
// (SPEC.md 3.3 Simulation Widgets, GLOSSARY.md: Simulation Type). No
// general physics library is used -- this is deliberate, per spec.
//
// Transcribed directly from the implementation research notes (section 6),
// not re-derived: a single generic `rk4Step` (position/velocity in, next
// position/velocity out, given an acceleration function) backs all three
// SimulationWidget renderers, since spring-mass and pendulum are both
// scalar 2nd-order ODEs and projectile motion decomposes into two
// independent 1D integrations (no drag coupling the axes).

// Generic RK4 step for state = [position, velocity], given an acceleration
// function. accel(position, velocity, t) -> number (the 2nd derivative,
// i.e. force/mass or equivalent).
export function rk4Step(position, velocity, t, dt, accel) {
  const k1v = accel(position, velocity, t)
  const k1x = velocity

  const k2v = accel(position + 0.5 * dt * k1x, velocity + 0.5 * dt * k1v, t + 0.5 * dt)
  const k2x = velocity + 0.5 * dt * k1v

  const k3v = accel(position + 0.5 * dt * k2x, velocity + 0.5 * dt * k2v, t + 0.5 * dt)
  const k3x = velocity + 0.5 * dt * k2v

  const k4v = accel(position + dt * k3x, velocity + dt * k3v, t + dt)
  const k4x = velocity + dt * k3v

  const newPosition = position + (dt / 6) * (k1x + 2 * k2x + 2 * k3x + k4x)
  const newVelocity = velocity + (dt / 6) * (k1v + 2 * k2v + 2 * k3v + k4v)

  return { position: newPosition, velocity: newVelocity }
}

// Spring-mass: F = -kx  =>  a = -(k/m) * x
export function springMassAccel(k, m) {
  return (position, _velocity, _t) => -(k / m) * position
}

// Simple pendulum, FULL nonlinear (not small-angle): theta'' = -(g/L) sin(theta)
// position here represents theta (radians), velocity represents theta' (angular velocity).
export function pendulumAccel(g, L) {
  return (theta, _thetaDot, _t) => -(g / L) * Math.sin(theta)
}

// Projectile motion, gravity only, no drag: two decoupled 1D integrations.
// x-axis: no horizontal acceleration. y-axis: constant downward acceleration -g.
export function projectileStep(state, dt, g) {
  const nextX = rk4Step(state.x, state.vx, state.t, dt, () => 0)
  const nextY = rk4Step(state.y, state.vy, state.t, dt, () => -g)
  return {
    x: nextX.position,
    vx: nextX.velocity,
    y: nextY.position,
    vy: nextY.velocity,
    t: state.t + dt,
  }
}
