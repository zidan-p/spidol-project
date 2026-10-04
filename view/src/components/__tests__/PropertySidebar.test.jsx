// PropertySidebar: left sidebar for color/stroke-weight/dash-style (SPEC.md
// 3.3, "Left Property Sidebar"). Controlled component: current values come
// in as props, selecting a new value calls back with just that value.
import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { PropertySidebar } from '../PropertySidebar'

function renderSidebar(overrides = {}) {
  const props = {
    color: '#ffffff',
    onColorChange: vi.fn(),
    width: 4,
    onWidthChange: vi.fn(),
    dash: 'solid',
    onDashChange: vi.fn(),
    ...overrides,
  }
  render(<PropertySidebar {...props} />)
  return props
}

describe('PropertySidebar', () => {
  it('renders a swatch per preset color and marks the active one selected', () => {
    renderSidebar({ color: '#ff3b30' })
    const active = screen.getByRole('radio', { name: /#ff3b30/i })
    expect(active).toBeChecked()
  })

  it('calls onColorChange when a different swatch is clicked', () => {
    const props = renderSidebar({ color: '#ffffff' })
    fireEvent.click(screen.getByRole('radio', { name: /#ff3b30/i }))
    expect(props.onColorChange).toHaveBeenCalledWith('#ff3b30')
  })

  it('renders the three stroke-width options (2/4/8) and marks the active one', () => {
    renderSidebar({ width: 8 })
    expect(screen.getByRole('radio', { name: '2px' })).not.toBeChecked()
    expect(screen.getByRole('radio', { name: '8px' })).toBeChecked()
  })

  it('calls onWidthChange with a number when a width option is picked', () => {
    const props = renderSidebar({ width: 2 })
    fireEvent.click(screen.getByRole('radio', { name: '4px' }))
    expect(props.onWidthChange).toHaveBeenCalledWith(4)
  })

  it('renders dash style options and marks the active one', () => {
    renderSidebar({ dash: 'dashed' })
    expect(screen.getByRole('radio', { name: 'Dashed' })).toBeChecked()
    expect(screen.getByRole('radio', { name: 'Solid' })).not.toBeChecked()
  })

  it('calls onDashChange when a dash style is picked', () => {
    const props = renderSidebar({ dash: 'solid' })
    fireEvent.click(screen.getByRole('radio', { name: 'Dotted' }))
    expect(props.onDashChange).toHaveBeenCalledWith('dotted')
  })
})
