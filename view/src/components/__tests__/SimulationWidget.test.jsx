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

  it('renders a linear function_graph with an m/b slider pair and an interactive x slider', () => {
    const linearFunction = {
      ...springMassWidget,
      sim_type: 'function_graph',
      expression: 'm*x + b',
      title: 'Linear Function',
      formula_latex: 'y = 2x',
      parameters: [
        { key: 'm', label: 'Slope (m)', min: -10, max: 10, val: 2 },
        { key: 'b', label: 'Intercept (b)', min: -10, max: 10, val: 0 },
      ],
    }
    const { container } = render(<SimulationWidget widget={linearFunction} />)

    // function-plot renders into this container (a <svg>, not a <canvas>);
    // jsdom can't fully execute its d3 internals (see FunctionGraphWidget's
    // try/catch), so only the container's presence is asserted here --
    // the actual curve rendering isn't unit-tested, consistent with this
    // project's existing canvas-rendering precedent.
    expect(container.querySelector('.sim-widget-function-plot')).toBeTruthy()
    expect(screen.getByLabelText('Slope (m)')).toHaveValue('2')
    expect(screen.getByLabelText('Intercept (b)')).toHaveValue('0')

    const xSlider = screen.getByLabelText('x')
    expect(xSlider).toHaveAttribute('type', 'range')
    expect(screen.getByTestId('function-graph-y-value')).toHaveTextContent('y = 0.00')

    fireEvent.change(xSlider, { target: { value: '3' } })
    expect(screen.getByTestId('function-graph-y-value')).toHaveTextContent('y = 6.00')
  })

  it('renders a quadratic function_graph (any math that can be graphed, not just linear)', () => {
    const quadratic = {
      ...springMassWidget,
      sim_type: 'function_graph',
      expression: 'a*x^2 + b*x + c',
      title: 'Quadratic Function',
      formula_latex: 'y = x^2',
      parameters: [
        { key: 'a', label: 'a', min: -5, max: 5, val: 1 },
        { key: 'b', label: 'b', min: -10, max: 10, val: 0 },
        { key: 'c', label: 'c', min: -10, max: 10, val: 0 },
      ],
    }
    render(<SimulationWidget widget={quadratic} />)

    const xSlider = screen.getByLabelText('x')
    fireEvent.change(xSlider, { target: { value: '3' } })
    expect(screen.getByTestId('function-graph-y-value')).toHaveTextContent('y = 9.00')
  })

  it('renders a fallback message instead of crashing when the expression fails to parse', () => {
    const malformedExpression = {
      ...springMassWidget,
      sim_type: 'function_graph',
      expression: 'a*x^2 +* b',
      title: 'Broken Expression',
    }
    render(<SimulationWidget widget={malformedExpression} />)

    expect(screen.getByText(/couldn't render this function/i)).toBeInTheDocument()
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
