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
    <div
      role="toolbar"
      aria-label="Drawing tools"
      className="absolute top-4 left-1/2 z-10 flex -translate-x-[65%] gap-0.5 rounded-2xl border border-chrome-border bg-chrome-bg p-1.5 shadow-[0_8px_24px_rgba(0,0,0,0.45)] backdrop-blur-md"
    >
      {TOOLS.map(({ id, label, Icon }) => (
        <button
          key={id}
          type="button"
          aria-pressed={tool === id}
          title={label}
          onClick={() => onSelectTool(id)}
          className={`flex flex-col items-center gap-0.5 rounded-xl px-3 py-2 transition-colors ${
            tool === id
              ? 'bg-accent-soft text-accent'
              : 'text-chrome-muted hover:bg-white/6 hover:text-chrome-text'
          }`}
        >
          <Icon size={18} aria-hidden="true" />
          <span className="text-[10px] font-medium">{label}</span>
        </button>
      ))}
    </div>
  )
}
