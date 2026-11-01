// Floating bar of the canvas: group the selected nodes, or ungroup and tune the selected container.
import { useEffect, useMemo, useState } from "react";
import type { ZoneStyle } from "../api";
import { ZoneStyleIcon, ZoneSwatch } from "./PalettePanel";
import { zoneStyleItems } from "./palette";
import type { useCanvas } from "./useCanvas";

type Canvas = ReturnType<typeof useCanvas>;

const btn = "rounded px-2 py-1 text-xs font-medium hover:bg-slate-100 dark:hover:bg-slate-700";

/** The zone style picker: the current style with its icon, and a list of every provider style with its icon. */
function ZonePicker({ style, styles, onPick }: { style: string; styles: ZoneStyle[]; onPick: (style: string) => void }) {
  const [open, setOpen] = useState(false);
  const items = useMemo(() => zoneStyleItems(styles).flatMap((i) => (i.type === "zoneStyle" ? [i] : [])), [styles]);
  const generic = useMemo(() => styles.find((s) => s.name === "soft"), [styles]);
  useEffect(() => {
    if (!open) return;
    const close = () => setOpen(false);
    window.addEventListener("pointerdown", close);
    return () => window.removeEventListener("pointerdown", close);
  }, [open]);
  if (items.length === 0) return null;
  const cur = items.find((i) => i.style === style);
  const row = "flex w-full items-center gap-2 rounded px-2 py-1 text-left text-xs hover:bg-slate-100 dark:hover:bg-slate-700";
  const providers = [...new Set(items.map((i) => i.provider))];
  return (
    <div className="relative" onPointerDown={(e) => e.stopPropagation()}>
      <button type="button" aria-haspopup="listbox" aria-expanded={open} className={`${btn} flex items-center gap-1.5`} onClick={() => setOpen((o) => !o)} title="Zone style">
        <span className="grid size-5 place-items-center">{cur ? <ZoneStyleIcon item={cur} size={18} /> : null}</span>
        {cur?.title ?? (style === "soft" ? "Generic zone" : style)}
        <span aria-hidden>▾</span>
      </button>
      {open && (
        <div role="listbox" aria-label="Zone style" className="absolute bottom-full left-0 z-20 mb-1 max-h-80 w-60 overflow-y-auto rounded-lg bg-white p-1 shadow-xl ring-1 ring-black/10 dark:bg-slate-800">
          {generic && (
            <button type="button" role="option" aria-selected={style === "soft"} className={row} onClick={() => { setOpen(false); onPick("soft"); }}>
              <span className="grid size-5 place-items-center"><ZoneStyleIcon item={{ icon: null, stroke: generic.stroke }} size={18} /></span>
              <span className="flex-1">Generic zone</span>
            </button>
          )}
          {providers.map((p) => (
            <div key={p}>
              <div className="px-2 pt-1.5 pb-0.5 text-[10px] font-semibold tracking-wide text-slate-400 uppercase">{p}</div>
              {items.filter((i) => i.provider === p).map((i) => (
                <button key={i.style} type="button" role="option" aria-selected={i.style === style} className={`${row} ${i.style === style ? "bg-blue-100 dark:bg-blue-900/50" : ""}`} onClick={() => { setOpen(false); onPick(i.style); }}>
                  <span className="grid size-5 place-items-center"><ZoneStyleIcon item={i} size={18} /></span>
                  <span className="flex-1 truncate">{i.title}</span>
                  <ZoneSwatch item={i} />
                </button>
              ))}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default function CanvasBar({ canvas, zoneStyles }: { canvas: Canvas; zoneStyles: ZoneStyle[] }) {
  if (!canvas.active) return null;
  const nodes = canvas.selected.filter((s) => s.kind === "node").length;
  const p = canvas.containerProps;
  const zp = canvas.zoneProps;
  if (nodes < 2 && !p && !zp) return null;
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
      {zp && <ZonePicker style={zp.style} styles={zoneStyles} onPick={canvas.setZoneStyle} />}
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
