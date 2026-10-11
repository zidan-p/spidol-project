// Tests for SimulationWidget: renders each fixed Simulation Type (SPEC.md
// 3.3 Simulation Widgets), and a distinct state for AI_WIDGET_UNSUPPORTED
// (ticket 04) instead of crashing or silently doing nothing. Per-formula
// parameter sliders (m/b, radius, k/m, ...) are deliberately not rendered --
// the curve/simulation always uses the AI's own default values.
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
  it('renders the formula (as typeset math, not raw LaTeX source) and title for a recognized sim_type', () => {
    const { container } = render(<SimulationWidget widget={springMassWidget} />)

    expect(screen.getByText('Spring-Mass Harmonic Oscillation')).toBeInTheDocument()
    // formula_latex is rendered via KaTeX, not as a plain-text node -- assert
    // on the typeset math container (and its hidden MathML source, which
    // KaTeX always includes) rather than an exact rendered-text match, since
    // KaTeX fragments the glyphs across many nested spans.
    expect(container.querySelector('.katex')).toBeTruthy()
    expect(container.querySelector('annotation').textContent).toBe('F = -kx')
  })

  it('renders a canvas for the live simulation render', () => {
    const { container } = render(<SimulationWidget widget={springMassWidget} />)
    expect(container.querySelector('canvas')).toBeTruthy()
  })

  it('renders pendulum and projectile sim types too', () => {
    const pendulum = {
      ...springMassWidget,
      sim_type: 'pendulum',
      parameters: [
        { key: 'g', label: 'Gravity (m/s^2)', min: 1, max: 20, val: 9.8 },
        { key: 'L', label: 'Length (m)', min: 0.1, max: 3, val: 1 },
      ],
    }
    const { rerender, container } = render(<SimulationWidget widget={pendulum} />)
    expect(container.querySelector('canvas')).toBeTruthy()

    const projectile = {
      ...springMassWidget,
      sim_type: 'projectile',
      parameters: [
        { key: 'v0', label: 'Launch Speed (m/s)', min: 1, max: 50, val: 20 },
        { key: 'angle', label: 'Launch Angle (deg)', min: 0, max: 90, val: 45 },
        { key: 'g', label: 'Gravity (m/s^2)', min: 1, max: 20, val: 9.8 },
      ],
    }
    rerender(<SimulationWidget widget={projectile} />)
    expect(container.querySelector('canvas')).toBeTruthy()
  })

  it('renders a linear function_graph with an interactive x slider and live y readout', () => {
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

    expect(container.querySelector('canvas')).toBeTruthy()

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

  it('renders a full circle via parametric_x/parametric_y, not just the upper half (docs/adr/0006)', () => {
    const circle = {
      ...springMassWidget,
      sim_type: 'function_graph',
      expression: null,
      parametric_x: 'r*cos(t)',
      parametric_y: 'r*sin(t)',
      title: 'Circle',
      formula_latex: 'x^2 + y^2 = r^2',
      parameters: [{ key: 'r', label: 'Radius (r)', min: 1, max: 10, val: 2 }],
    }
    render(<SimulationWidget widget={circle} />)

    // The slider is "t" (the parametric parameter), not "x" -- a circle
    // has no single x-per-point to drag through.
    const tSlider = screen.getByLabelText('t')
    expect(tSlider).toHaveAttribute('min', '0')
    expect(Number(tSlider.getAttribute('max'))).toBeCloseTo(2 * Math.PI)

    // t=0 -> (x,y) = (r, 0) = (2, 0)
    fireEvent.change(tSlider, { target: { value: '0' } })
    expect(screen.getByTestId('function-graph-y-value')).toHaveTextContent('(2.00, 0.00)')
  })

  it('renders the computed value for a definite integral (matches the worked answer)', () => {
    const integral = {
      ...springMassWidget,
      sim_type: 'function_graph',
      expression: '2*x + 1',
      integral_lower: 0,
      integral_upper: 1,
      title: 'Definite Integral of a Linear Function',
      formula_latex: '\\int_{0}^{1} (2x + 1) \\, dx',
      parameters: [],
    }
    render(<SimulationWidget widget={integral} />)

    // integral of 2x+1 from 0 to 1 = [x^2 + x] from 0 to 1 = 2
    expect(screen.getByTestId('function-graph-integral-value')).toHaveTextContent('= 2.00')
  })

  it('does not render an integral readout for a plain function with no integral bounds', () => {
    const plain = {
      ...springMassWidget,
      sim_type: 'function_graph',
      expression: '2*x + 1',
      title: 'Linear Function',
      formula_latex: 'y = 2x + 1',
      parameters: [],
    }
    render(<SimulationWidget widget={plain} />)

    expect(screen.queryByTestId('function-graph-integral-value')).not.toBeInTheDocument()
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
    const { container } = render(<SimulationWidget widget={unsupportedWidget} />)

    expect(screen.getByText(/not yet supported/i)).toBeInTheDocument()
    expect(screen.getByText('Wave Equation')).toBeInTheDocument()
    expect(container.querySelector('.katex')).toBeTruthy()
    expect(container.querySelector('annotation').textContent).toBe('\\nabla^2 \\psi = 0')
    expect(screen.queryByRole('slider')).not.toBeInTheDocument()
  })

  it('falls back to the unsupported state (never crashes) for an unknown sim_type even on AI_WIDGET_SPAWN', () => {
    const malformed = { ...springMassWidget, sim_type: 'something_unexpected' }
    render(<SimulationWidget widget={malformed} />)

    expect(screen.getByText(/not yet supported/i)).toBeInTheDocument()
  })
})
