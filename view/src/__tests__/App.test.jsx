// Tests for the dev-mode AI Trigger wiring in App.jsx: pressing the
// trigger keyboard shortcut sends {"type": "AI_TRIGGER", image_png_base64}
// over the socket (the canvas snapshot lets the server's AI pipeline see
// what was actually drawn in mouse-fallback dev mode -- jsdom has no real
// canvas context, so it's always null in these tests, see Canvas.jsx's
// exportPngBase64 guard), and incoming AI_WIDGET_SPAWN /
// AI_WIDGET_UNSUPPORTED events render a SimulationWidget.
import { act, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import App from '../App'

class FakeWebSocket {
  static instances = []

  constructor(url) {
    this.url = url
    this.onopen = null
    this.onclose = null
    this.onmessage = null
    this.sent = []
    FakeWebSocket.instances.push(this)
  }

  send(data) {
    this.sent.push(data)
  }

  close() {}

  simulateMessage(data) {
    this.onmessage?.({ data: JSON.stringify(data) })
  }
}

beforeEach(() => {
  FakeWebSocket.instances = []
  vi.stubGlobal('WebSocket', FakeWebSocket)
})

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('App AI Trigger dev-mode hook', () => {
  it('sends an AI_TRIGGER message when the trigger shortcut (T) is pressed', () => {
    render(<App />)
    const socket = FakeWebSocket.instances[0]

    fireEvent.keyDown(window, { key: 't' })

    expect(socket.sent).toEqual([
      JSON.stringify({ type: 'AI_TRIGGER', image_png_base64: null }),
    ])
  })

  it('renders a SimulationWidget when AI_WIDGET_SPAWN arrives', () => {
    render(<App />)
    const socket = FakeWebSocket.instances[0]

    act(() => {
      socket.simulateMessage({
        type: 'AI_WIDGET_SPAWN',
        widget_id: 'widget_01',
        anchor_x: 0.5,
        anchor_y: 0.3,
        formula_latex: 'F = -kx',
        title: 'Spring-Mass Harmonic Oscillation',
        sim_type: 'spring_mass',
        parameters: [{ key: 'k', label: 'Spring Stiffness (N/m)', min: 10, max: 100, val: 45 }],
      })
    })

    expect(screen.getByText('Spring-Mass Harmonic Oscillation')).toBeInTheDocument()
  })

  it('sends a CANVAS_CLEAR message when the Clear button is pressed', () => {
    render(<App />)
    const socket = FakeWebSocket.instances[0]

    fireEvent.click(screen.getByRole('button', { name: 'Clear' }))

    expect(socket.sent).toContainEqual(JSON.stringify({ type: 'CANVAS_CLEAR' }))
  })

  it('sends a CALIBRATE message when the Calibration Hotkey (C) is pressed', () => {
    render(<App />)
    const socket = FakeWebSocket.instances[0]

    fireEvent.keyDown(window, { key: 'c' })

    expect(socket.sent).toContainEqual(JSON.stringify({ type: 'CALIBRATE' }))
  })

  it('renders the unsupported state when AI_WIDGET_UNSUPPORTED arrives', () => {
    render(<App />)
    const socket = FakeWebSocket.instances[0]

    act(() => {
      socket.simulateMessage({
        type: 'AI_WIDGET_UNSUPPORTED',
        widget_id: 'widget_02',
        anchor_x: 0.1,
        anchor_y: 0.2,
        formula_latex: '\\nabla^2 \\psi = 0',
        title: 'Wave Equation',
        attempted_sim_type: 'wave_equation',
      })
    })

    expect(screen.getByText(/not yet supported/i)).toBeInTheDocument()
  })
})
