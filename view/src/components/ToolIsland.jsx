// Floating top tool dock (SPEC.md 3.3: "Floating Island Dock (Center-Top)").
// Purely controlled: the active tool and the select callback live in
// App.jsx's state, this component only renders the dock and reports clicks.
import { ArrowUpRight, Circle, Eraser, Minus, Pencil, Square, Type } from 'lucide-react'

const TOOLS = [
  { id: 'pen', label: 'Pen', Icon: Pencil },
  { id: 'eraser', label: 'Eraser', Icon: Eraser },
  { id: 'rectangle', label: 'Rectangle', Icon: Square },
  { id: 'ellipse', label: 'Ellipse', Icon: Circle },
  { id: 'arrow', label: 'Arrow', Icon: ArrowUpRight },
  { id: 'line', label: 'Line', Icon: Minus },
  { id: 'text', label: 'Text', Icon: Type },
]

export function ToolIsland({ tool, onSelectTool }) {
  return (
    <div className="tool-island" role="toolbar" aria-label="Drawing tools">
      {TOOLS.map(({ id, label, Icon }) => (
        <button
          key={id}
          type="button"
          className="tool-island__button"
          aria-pressed={tool === id}
          title={label}
          onClick={() => onSelectTool(id)}
        >
          <Icon size={18} aria-hidden="true" />
          <span className="tool-island__label">{label}</span>
        </button>
      ))}
    </div>
  )
}
