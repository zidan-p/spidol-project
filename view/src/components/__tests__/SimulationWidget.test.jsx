// Tests for SimulationWidget: renders each fixed Simulation Type with
// mouse-editable parameter sliders (SPEC.md 3.3 Simulation Widgets), and a
// distinct state for AI_WIDGET_UNSUPPORTED (ticket 04) instead of crashing
// or silently doing nothing.
import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { SimulationWidget } from '../SimulationWidget'

const springMassWidget = {
  type: 'AI_WIDGET_SPAWN',
  widget_id: 'widget_01',
  anchor_x: 0.5,
  anchor_y: 0.3,
  formula_latex: 'F = -kx',
  title: 'Spring-Mass Harmonic Oscillation',
  sim_type: 'spring_mass',
  parameters: [
    { key: 'k', label: 'Spring Stiffness (N/m)', min: 10, max: 100, val: 45 },
    { key: 'm', label: 'Bob Mass (kg)', min: 0.5, max: 5.0, val: 1.2 },
  ],
}

const unsupportedWidget = {
  type: 'AI_WIDGET_UNSUPPORTED',
  widget_id: 'widget_02',
  anchor_x: 0.1,
  anchor_y: 0.2,
  formula_latex: '\\nabla^2 \\psi = 0',
  title: 'Wave Equation',
  attempted_sim_type: 'wave_equation',
}

describe('SimulationWidget', () => {
  it('renders the formula and title for a recognized sim_type', () => {
    render(<SimulationWidget widget={springMassWidget} />)

    expect(screen.getByText('Spring-Mass Harmonic Oscillation')).toBeInTheDocument()
    expect(screen.getByText('F = -kx')).toBeInTheDocument()
  })

  it('renders one slider per parameter, bound to its min/max/default value', () => {
    render(<SimulationWidget widget={springMassWidget} />)

    const kSlider = screen.getByLabelText('Spring Stiffness (N/m)')
    expect(kSlider).toHaveAttribute('type', 'range')
    expect(kSlider).toHaveAttribute('min', '10')
    expect(kSlider).toHaveAttribute('max', '100')
    expect(kSlider.value).toBe('45')

    const mSlider = screen.getByLabelText('Bob Mass (kg)')
    expect(mSlider.value).toBe('1.2')
  })

  it('updates the displayed parameter value when a slider is dragged', () => {
    render(<SimulationWidget widget={springMassWidget} />)

    const kSlider = screen.getByLabelText('Spring Stiffness (N/m)')
    fireEvent.change(kSlider, { target: { value: '80' } })

    expect(screen.getByTestId('param-value-k')).toHaveTextContent('80')
  })

  it('renders a canvas for the live simulation render', () => {
    const { container } = render(<SimulationWidget widget={springMassWidget} />)
    expect(container.querySelector('canvas')).toBeTruthy()
  })

  it('renders pendulum and projectile sim types too', () => {
    const pendulum = { ...springMassWidget, sim_type: 'pendulum', parameters: [
      { key: 'g', label: 'Gravity (m/s^2)', min: 1, max: 20, val: 9.8 },
      { key: 'L', label: 'Length (m)', min: 0.1, max: 3, val: 1 },
    ] }
    const { rerender, container } = render(<SimulationWidget widget={pendulum} />)
    expect(container.querySelector('canvas')).toBeTruthy()
    expect(screen.getByLabelText('Gravity (m/s^2)')).toBeInTheDocument()

    const projectile = { ...springMassWidget, sim_type: 'projectile', parameters: [
      { key: 'v0', label: 'Launch Speed (m/s)', min: 1, max: 50, val: 20 },
      { key: 'angle', label: 'Launch Angle (deg)', min: 0, max: 90, val: 45 },
      { key: 'g', label: 'Gravity (m/s^2)', min: 1, max: 20, val: 9.8 },
    ] }
    rerender(<SimulationWidget widget={projectile} />)
    expect(container.querySelector('canvas')).toBeTruthy()
    expect(screen.getByLabelText('Launch Angle (deg)')).toBeInTheDocument()
  })

  it('renders a distinct "concept detected but not yet supported" state for AI_WIDGET_UNSUPPORTED', () => {
    render(<SimulationWidget widget={unsupportedWidget} />)

    expect(screen.getByText(/not yet supported/i)).toBeInTheDocument()
    expect(screen.getByText('Wave Equation')).toBeInTheDocument()
    expect(screen.getByText('\\nabla^2 \\psi = 0')).toBeInTheDocument()
    expect(screen.queryByRole('slider')).not.toBeInTheDocument()
  })

  it('falls back to the unsupported state (never crashes) for an unknown sim_type even on AI_WIDGET_SPAWN', () => {
    const malformed = { ...springMassWidget, sim_type: 'something_unexpected' }
    render(<SimulationWidget widget={malformed} />)

    expect(screen.getByText(/not yet supported/i)).toBeInTheDocument()
  })
})
