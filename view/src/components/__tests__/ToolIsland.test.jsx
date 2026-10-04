// ToolIsland: the floating top tool dock (SPEC.md 3.3). Seam under test is
// the public props contract: which tool is active is rendered, and
// clicking a tool button calls back with that tool's id.
import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { ToolIsland } from '../ToolIsland'

describe('ToolIsland', () => {
  it('renders all seven tools', () => {
    render(<ToolIsland tool="pen" onSelectTool={() => {}} />)
    for (const name of ['Pen', 'Eraser', 'Rectangle', 'Ellipse', 'Arrow', 'Line', 'Text']) {
      expect(screen.getByRole('button', { name })).toBeInTheDocument()
    }
  })

  it('marks the active tool as pressed', () => {
    render(<ToolIsland tool="eraser" onSelectTool={() => {}} />)
    expect(screen.getByRole('button', { name: 'Eraser' })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByRole('button', { name: 'Pen' })).toHaveAttribute('aria-pressed', 'false')
  })

  it('calls onSelectTool with the tool id when a dock button is clicked', () => {
    const onSelectTool = vi.fn()
    render(<ToolIsland tool="pen" onSelectTool={onSelectTool} />)

    fireEvent.click(screen.getByRole('button', { name: 'Rectangle' }))

    expect(onSelectTool).toHaveBeenCalledWith('rectangle')
  })

  it('defaults to the Pen tool being active when tool="pen"', () => {
    render(<ToolIsland tool="pen" onSelectTool={() => {}} />)
    expect(screen.getByRole('button', { name: 'Pen' })).toHaveAttribute('aria-pressed', 'true')
  })
})
