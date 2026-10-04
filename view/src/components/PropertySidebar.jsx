// Left property sidebar (SPEC.md 3.3): color palette, stroke-weight
// increments (2px/4px/8px), dash styles. Fully controlled -- style state
// lives in App.jsx so it can be threaded into new strokes via strokeBuffer's
// `style` argument.
const COLORS = ['#ffffff', '#ff3b30', '#34c759', '#0a84ff', '#ffd60a']
const WIDTHS = [2, 4, 8]
const DASH_STYLES = [
  { id: 'solid', label: 'Solid' },
  { id: 'dashed', label: 'Dashed' },
  { id: 'dotted', label: 'Dotted' },
]

export function PropertySidebar({ color, onColorChange, width, onWidthChange, dash, onDashChange }) {
  return (
    <div className="property-sidebar">
      <fieldset className="property-sidebar__group">
        <legend>Color</legend>
        {COLORS.map((swatch) => (
          <button
            key={swatch}
            type="button"
            role="radio"
            aria-checked={color === swatch}
            aria-label={swatch}
            className="property-sidebar__swatch"
            style={{ backgroundColor: swatch }}
            onClick={() => onColorChange(swatch)}
          />
        ))}
      </fieldset>

      <fieldset className="property-sidebar__group">
        <legend>Stroke width</legend>
        {WIDTHS.map((option) => (
          <button
            key={option}
            type="button"
            role="radio"
            aria-checked={width === option}
            aria-label={`${option}px`}
            onClick={() => onWidthChange(option)}
          >
            {option}px
          </button>
        ))}
      </fieldset>

      <fieldset className="property-sidebar__group">
        <legend>Dash style</legend>
        {DASH_STYLES.map(({ id, label }) => (
          <button
            key={id}
            type="button"
            role="radio"
            aria-checked={dash === id}
            aria-label={label}
            onClick={() => onDashChange(id)}
          >
            {label}
          </button>
        ))}
      </fieldset>
    </div>
  )
}
