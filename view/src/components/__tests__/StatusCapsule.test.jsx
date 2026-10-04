// StatusCapsule: real-time telemetry readout (SPEC.md 3.3 directory
// listing: "WS link, Camera status, Touch state"). Camera tracking
// (ticket 02) and the BLE touch provider (ticket 05) don't exist yet, so
// this component just renders whatever placeholder/not-yet-wired fields
// the caller passes for those two -- the WS link state is the only one
// backed by a real, already-built subsystem (useSpidolSocket.js).
import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { StatusCapsule } from '../StatusCapsule'

describe('StatusCapsule', () => {
  it('renders the live WebSocket connection state', () => {
    render(
      <StatusCapsule
        connectionState="open"
        camera={{ status: 'not-wired' }}
        touch={{ status: 'not-wired' }}
      />
    )
    expect(screen.getByText(/ws/i)).toBeInTheDocument()
    expect(screen.getByText(/open/i)).toBeInTheDocument()
  })

  it('reflects a closed WS connection distinctly from open', () => {
    const { container, rerender } = render(
      <StatusCapsule connectionState="open" camera={{ status: 'not-wired' }} touch={{ status: 'not-wired' }} />
    )
    const openEl = container.querySelector('[data-field="ws"]')
    expect(openEl).toHaveAttribute('data-state', 'open')

    rerender(
      <StatusCapsule connectionState="closed" camera={{ status: 'not-wired' }} touch={{ status: 'not-wired' }} />
    )
    expect(container.querySelector('[data-field="ws"]')).toHaveAttribute('data-state', 'closed')
  })

  it('renders the placeholder camera status', () => {
    const { container } = render(
      <StatusCapsule connectionState="open" camera={{ status: 'not-wired' }} touch={{ status: 'not-wired' }} />
    )
    const cameraEl = container.querySelector('[data-field="camera"]')
    expect(cameraEl).toHaveTextContent(/camera/i)
    expect(cameraEl).toHaveTextContent(/not.wired/i)
  })

  it('renders live touch state when provided (is_touching from TRACK_UPDATE)', () => {
    render(
      <StatusCapsule
        connectionState="open"
        camera={{ status: 'not-wired' }}
        touch={{ status: 'ok', isTouching: true }}
      />
    )
    const touchEl = screen.getByTestId('status-touch')
    expect(touchEl).toHaveAttribute('data-touching', 'true')
  })
})
