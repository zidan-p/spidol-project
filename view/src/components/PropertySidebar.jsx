// Left property sidebar (SPEC.md 3.3): color palette, stroke-weight
// increments (2px/4px/8px), dash styles. Fully controlled -- style state
// lives in App.jsx so it can be threaded into new strokes via strokeBuffer's
// `style` argument.
import { Palette, PenTool, SeparatorHorizontal } from 'lucide-react'

// Deliberately violet, not blue (#0a84ff was hue 105 -- dead center in
// OpticalColorTracker's tracked Pen Tip hue range, 90-120, and at full
// saturation/value -- drawing with it risked the ink itself being
// detected as the marker). Hue ~132, safely clear of that range.
const COLORS = ['#ffffff', '#ff3b30', '#34c759', '#6d28d9', '#ffd60a']
const WIDTHS = [2, 4, 8]
const DASH_STYLES = [
  { id: 'solid', label: 'Solid' },
  { id: 'dashed', label: 'Dashed' },
  { id: 'dotted', label: 'Dotted' },
]

const LEGEND_CLASS =
  'flex items-center gap-1.5 text-[11px] font-semibold tracking-wide text-chrome-muted uppercase mb-2'
const OPTION_BUTTON_CLASS =
  'rounded-lg border border-transparent bg-white/6 px-2.5 py-1.5 text-xs text-chrome-muted transition-colors hover:bg-white/10 hover:text-chrome-text aria-checked:border-accent aria-checked:bg-accent-soft aria-checked:text-accent'

export function PropertySidebar({ color, onColorChange, width, onWidthChange, dash, onDashChange }) {
  return (
    <div className="absolute top-20 left-4 z-10 flex flex-col gap-3.5 rounded-2xl border border-chrome-border bg-chrome-bg p-3.5 shadow-[0_8px_24px_rgba(0,0,0,0.45)] backdrop-blur-md">
      {/* <fieldset className="m-0 flex flex-col gap-2 border-none p-0">
        <legend className={LEGEND_CLASS}>
          <Palette size={14} aria-hidden="true" /> Color
        </legend>
        <div className="flex flex-wrap gap-1.5">
          {COLORS.map((swatch) => (
            <button
              key={swatch}
              type="button"
              role="radio"
              aria-checked={color === swatch}
              aria-label={swatch}
              onClick={() => onColorChange(swatch)}
              className="h-5.5 w-5.5 cursor-pointer rounded-full border-2 border-transparent transition-transform hover:scale-110 aria-checked:border-white aria-checked:shadow-[0_0_0_2px_var(--color-accent)]"
              style={{ backgroundColor: swatch }}
            />
          ))}
        </div>
      </fieldset> */}

      <fieldset className="m-0 flex flex-col gap-2 border-none p-0">
        <legend className={LEGEND_CLASS}>
          <PenTool size={14} aria-hidden="true" /> Stroke width
        </legend>
        <div className="flex flex-wrap gap-1.5">
          {WIDTHS.map((option) => (
            <button
              key={option}
              type="button"
              role="radio"
              aria-checked={width === option}
              aria-label={`${option}px`}
              onClick={() => onWidthChange(option)}
              className={OPTION_BUTTON_CLASS}
            >
              {option}px
            </button>
          ))}
        </div>
      </fieldset>

      <fieldset className="m-0 flex flex-col gap-2 border-none p-0">
        <legend className={LEGEND_CLASS}>
          <SeparatorHorizontal size={14} aria-hidden="true" /> Dash style
        </legend>
        <div className="flex flex-wrap gap-1.5">
          {DASH_STYLES.map(({ id, label }) => (
            <button
              key={id}
              type="button"
              role="radio"
              aria-checked={dash === id}
              aria-label={label}
              onClick={() => onDashChange(id)}
              className={OPTION_BUTTON_CLASS}
            >
              {label}
            </button>
          ))}
        </div>
      </fieldset>
    </div>
  )
}
