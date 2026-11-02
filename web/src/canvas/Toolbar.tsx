// The canvas toolbar: tools on top (the pointer's mode), actions below. Built from the tool and action tables
// (tools.ts), so a tool added there shows up here, in the key table and in the icon check.
import { EditorIcon } from "./icons";
import { otherDock, type Dock } from "./paletteState";
import { ACTIONS, TOOLS, dockLayout, type ActionId } from "./tools";
import type { useCanvas } from "./useCanvas";

type Canvas = ReturnType<typeof useCanvas>;

type Props = { canvas: Canvas; dock: Dock; paletteOpen: boolean; elementsOpen: boolean; sheetOpen: boolean; onPalette: () => void; onElements: () => void; onHelp: () => void; onDock: (dock: Dock) => void };

const base = "grid size-8 place-items-center rounded-md text-slate-700 transition-colors dark:text-slate-200";
const idle = "hover:bg-slate-100 dark:hover:bg-slate-700";
const on = "bg-blue-600 text-white hover:bg-blue-700 dark:text-white";
const off = "cursor-not-allowed opacity-35";

export default function Toolbar({ canvas, dock, paletteOpen, elementsOpen, sheetOpen, onPalette, onElements, onHelp, onDock }: Props) {
  if (!canvas.shown) return null; // stays mounted while a save re-fetches the scene (`active` false): buttons just disable
  const live = canvas.active;
  const nodes = canvas.selected.filter((s) => s.kind === "node").length;
  const hasContainer = canvas.selected.some((s) => s.kind === "container");
  const removable = canvas.selected.some((s) => s.kind !== "container");
  const enabled: Partial<Record<ActionId, boolean>> = { "group-row": live && nodes >= 2, "group-column": live && nodes >= 2, ungroup: live && hasContainer, delete: live && removable, undo: live, redo: live };
  const run: Record<ActionId, () => void> = {
    "group-row": () => canvas.group("row"),
    "group-column": () => canvas.group("column"),
    ungroup: canvas.ungroup,
    delete: canvas.remove,
    undo: canvas.undo,
    redo: canvas.redo,
    palette: onPalette,
    elements: onElements,
    help: onHelp,
    dock: () => onDock(otherDock(dock)),
  };
  const pressed: Partial<Record<ActionId, boolean>> = { palette: paletteOpen, elements: elementsOpen, help: sheetOpen };
  const layout = dockLayout(dock);
  const tip = (text: string) => (
    <span
      role="tooltip"
      className={`pointer-events-none absolute z-20 hidden rounded bg-slate-900 px-2 py-1 text-xs whitespace-nowrap text-white shadow group-focus-within:block group-hover:block ${layout.tip}`}
    >
      {text}
    </span>
  );
  const hint: Partial<Record<ActionId, string>> = { "group-row": "Ctrl/Cmd+G", delete: "Delete", undo: "Ctrl/Cmd+Z", redo: "Shift+Ctrl/Cmd+Z", palette: "/", help: "?" };
  const titleOf = (id: ActionId, label: string) => (id === "dock" ? `Dock the toolbar ${dock === "left" ? "at the bottom" : "on the left"}` : hint[id] ? `${label} (${hint[id]})` : label);
  return (
    <div
      role="toolbar"
      aria-label="Canvas tools"
      aria-orientation={layout.orientation}
      onPointerDown={(e) => e.stopPropagation()}
      className={`absolute ${layout.bar} z-10 flex items-center gap-1 rounded-xl bg-white/95 p-1.5 shadow-lg ring-1 ring-black/10 dark:bg-slate-800/95`}
    >
      {TOOLS.map((t) => (
        <div key={t.id} className="group relative">
          <button
            type="button"
            disabled={!live}
            className={`${base} ${!live ? off : canvas.tool === t.id ? on : idle}`}
            aria-pressed={canvas.tool === t.id}
            aria-label={t.label}
            onClick={() => canvas.setTool(t.id)}
          >
            <EditorIcon name={t.id} size={18} />
          </button>
          {tip(`${t.label} (${t.key.toUpperCase()})`)}
        </div>
      ))}
      <div className={`${layout.separator} bg-slate-200 dark:bg-slate-600`} />
      {ACTIONS.map((a) => {
        const ok = enabled[a.id] ?? true;
        const hot = pressed[a.id] ?? false;
        return (
          <div key={a.id} className="group relative">
            <button
              type="button"
              disabled={!ok}
              className={`${base} ${!ok ? off : hot ? on : idle}`}
              aria-pressed={a.id === "palette" || a.id === "elements" || a.id === "help" ? hot : undefined}
              aria-label={a.label}
              onClick={run[a.id]}
            >
              <EditorIcon name={a.id} size={18} />
            </button>
            {tip(titleOf(a.id, a.label))}
          </div>
        );
      })}
    </div>
  );
}
