// The canvas toolbar: tools on top (the pointer's mode), actions below. Built from the tool and action tables
// (tools.ts), so a tool added there shows up here, in the key table and in the icon check.
import { EditorIcon } from "./icons";
import { ACTIONS, TOOLS, type ActionId } from "./tools";
import type { useCanvas } from "./useCanvas";

type Canvas = ReturnType<typeof useCanvas>;

type Props = { canvas: Canvas; paletteOpen: boolean; sheetOpen: boolean; onPalette: () => void; onHelp: () => void };

const base = "grid size-8 place-items-center rounded-md text-slate-700 transition-colors dark:text-slate-200";
const idle = "hover:bg-slate-100 dark:hover:bg-slate-700";
const on = "bg-blue-600 text-white hover:bg-blue-700 dark:text-white";
const off = "cursor-not-allowed opacity-35";

export default function Toolbar({ canvas, paletteOpen, sheetOpen, onPalette, onHelp }: Props) {
  if (!canvas.active) return null;
  const nodes = canvas.selected.filter((s) => s.kind === "node").length;
  const hasContainer = canvas.selected.some((s) => s.kind === "container");
  const removable = canvas.selected.some((s) => s.kind !== "container");
  const enabled: Partial<Record<ActionId, boolean>> = { "group-row": nodes >= 2, "group-column": nodes >= 2, ungroup: hasContainer, delete: removable };
  const run: Record<ActionId, () => void> = {
    "group-row": () => canvas.group("row"),
    "group-column": () => canvas.group("column"),
    ungroup: canvas.ungroup,
    delete: canvas.remove,
    undo: canvas.undo,
    redo: canvas.redo,
    palette: onPalette,
    help: onHelp,
  };
  const pressed: Partial<Record<ActionId, boolean>> = { palette: paletteOpen, help: sheetOpen };
  const hint: Partial<Record<ActionId, string>> = { "group-row": "Ctrl/Cmd+G", delete: "Delete", undo: "Ctrl/Cmd+Z", redo: "Shift+Ctrl/Cmd+Z", palette: "/", help: "?" };
  return (
    <div
      role="toolbar"
      aria-label="Canvas tools"
      aria-orientation="vertical"
      onPointerDown={(e) => e.stopPropagation()}
      className="absolute top-1/2 left-3 z-10 flex -translate-y-1/2 flex-col items-center gap-1 rounded-xl bg-white/95 p-1.5 shadow-lg ring-1 ring-black/10 dark:bg-slate-800/95"
    >
      {TOOLS.map((t) => (
        <button
          key={t.id}
          type="button"
          className={`${base} ${canvas.tool === t.id ? on : idle}`}
          aria-pressed={canvas.tool === t.id}
          aria-label={t.label}
          title={`${t.label} (${t.key.toUpperCase()})`}
          onClick={() => canvas.setTool(t.id)}
        >
          <EditorIcon name={t.id} size={18} />
        </button>
      ))}
      <div className="my-0.5 h-px w-6 bg-slate-200 dark:bg-slate-600" />
      {ACTIONS.map((a) => {
        const ok = enabled[a.id] ?? true;
        const hot = pressed[a.id] ?? false;
        return (
          <button
            key={a.id}
            type="button"
            disabled={!ok}
            className={`${base} ${!ok ? off : hot ? on : idle}`}
            aria-pressed={a.id === "palette" || a.id === "help" ? hot : undefined}
            aria-label={a.label}
            title={hint[a.id] ? `${a.label} (${hint[a.id]})` : a.label}
            onClick={run[a.id]}
          >
            <EditorIcon name={a.id} size={18} />
          </button>
        );
      })}
    </div>
  );
}
