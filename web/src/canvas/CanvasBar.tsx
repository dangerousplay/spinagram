// Floating bar of the canvas: group the selected nodes, or ungroup and tune the selected container.
import type { useCanvas } from "./useCanvas";

type Canvas = ReturnType<typeof useCanvas>;

const btn = "rounded px-2 py-1 text-xs font-medium hover:bg-slate-100 dark:hover:bg-slate-700";

export default function CanvasBar({ canvas }: { canvas: Canvas }) {
  if (!canvas.active) return null;
  const nodes = canvas.selected.filter((s) => s.kind === "node").length;
  const p = canvas.containerProps;
  if (nodes < 2 && !p) return null;
  const commitGap = (v: string) => {
    const gap = Number(v);
    if (v.trim() !== "" && Number.isFinite(gap) && gap >= 0 && String(gap) !== p?.gap) canvas.setContainer({ gap });
  };
  return (
    <div
      role="toolbar"
      aria-label="Canvas selection"
      className="absolute bottom-14 left-1/2 flex -translate-x-1/2 items-center gap-1 rounded-lg bg-white/95 px-2 py-1 text-slate-700 shadow-lg ring-1 ring-black/10 dark:bg-slate-800/95 dark:text-slate-200"
    >
      {nodes >= 2 && (
        <>
          <button className={btn} onClick={() => canvas.group("row")} title="Group the selected nodes as a row (Ctrl/Cmd+G)">
            Group as row
          </button>
          <button className={btn} onClick={() => canvas.group("column")} title="Group the selected nodes as a column">
            Group as column
          </button>
        </>
      )}
      {p && (
        <>
          <button className={btn} onClick={canvas.ungroup} title="Remove the container; each member keeps its place">
            Ungroup
          </button>
          <label className="flex items-center gap-1 text-xs">
            Gap
            <input
              key={`${p.id}-${p.gap}`}
              type="number"
              min={0}
              defaultValue={p.gap}
              className="w-16 rounded border border-slate-300 bg-white px-1 py-0.5 text-slate-900 dark:border-slate-600 dark:bg-slate-900 dark:text-slate-100"
              onBlur={(e) => commitGap(e.currentTarget.value)}
              onKeyDown={(e) => {
                e.stopPropagation();
                if (e.key === "Enter") commitGap(e.currentTarget.value);
              }}
            />
          </label>
          {p.align !== null && (
            <label className="flex items-center gap-1 text-xs">
              Align
              <select
                key={`${p.id}-${p.align}`}
                defaultValue={p.align}
                className="rounded border border-slate-300 bg-white px-1 py-0.5 text-slate-900 dark:border-slate-600 dark:bg-slate-900 dark:text-slate-100"
                onChange={(e) => canvas.setContainer({ align: e.currentTarget.value })}
              >
                <option value="start">start</option>
                <option value="center">center</option>
                <option value="end">end</option>
              </select>
            </label>
          )}
        </>
      )}
    </div>
  );
}
