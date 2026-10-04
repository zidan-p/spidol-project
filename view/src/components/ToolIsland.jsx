// Floating top tool dock (SPEC.md 3.3: "Floating Island Dock (Center-Top)").
// Purely controlled: the active tool and the select callback live in
// App.jsx's state, this component only renders the dock and reports clicks.
const TOOLS = [
  { id: 'pen', label: 'Pen' },
  { id: 'eraser', label: 'Eraser' },
  { id: 'rectangle', label: 'Rectangle' },
  { id: 'ellipse', label: 'Ellipse' },
  { id: 'arrow', label: 'Arrow' },
  { id: 'line', label: 'Line' },
  { id: 'text', label: 'Text' },
]

export function ToolIsland({ tool, onSelectTool }) {
  return (
    <div className="tool-island" role="toolbar" aria-label="Drawing tools">
      {TOOLS.map(({ id, label }) => (
        <button
          key={id}
          type="button"
          className="tool-island__button"
          aria-pressed={tool === id}
          onClick={() => onSelectTool(id)}
        >
          {label}
        </button>
      ))}
    </div>
  )
}
