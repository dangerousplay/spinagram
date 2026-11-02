// The icon palette panel of the canvas: fuzzy search over every cached pack, built-in shapes, Zone, Row and
// Column; drag an item onto the canvas, or press Enter to add it at the centre (PAL-01..07). With the search box
// empty the items are grouped into collapsible categories (Basics, Shapes, one per icon pack); with a query the
// results are one ranked list, each row tagged with its category.
import { useVirtualizer } from "@tanstack/react-virtual";
import { ChevronDown, ChevronRight } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api, type Pack, type ZoneStyle } from "../api";
import { EditorIcon, iconNameOf } from "./icons";
import { buildCorpus, categorize, categoryOf, defaultCollapsed, noMatch, paletteRows, search, type IconEntry, type PaletteItem, type PaletteRow } from "./palette";
import { readCollapsed, writeCollapsed, type CollapsedState } from "./paletteState";

export const PALETTE_MIME = "application/x-spinagram-palette";

type Props = {
  rev: number; // bumps when the packs change on disk
  focusRef: React.MutableRefObject<(() => void) | null>; // `/` and Ctrl/Cmd+K call this (the panel must be open)
  onClose: () => void; // the « button and Esc
  onAdd: (item: PaletteItem) => void; // Enter and double-click: add at the centre of the canvas
};

const iconCache = new Map<string, IconEntry[]>();

export async function loadIcons(packs: Pack[]): Promise<IconEntry[]> {
  const out: IconEntry[] = [];
  await Promise.all(
    packs
      .filter((p) => p.fetched)
      .map(async (p) => {
        const key = `${p.name}@${p.version}:${p.count}`;
        let list = iconCache.get(key);
        if (!list) {
          list = (await api.packIcons(p.name)).map((i) => ({ pack: p.name, name: i.name, aliases: i.aliases }));
          iconCache.set(key, list);
        }
        out.push(...list);
      }),
  );
  return out;
}

/** The colour swatch of a provider zone: its outline colour (dashed where the style is), and its fill. */
export function ZoneSwatch({ item }: { item: { stroke: string | null; fill: string | null; dashed: boolean } }) {
  return (
    <span
      aria-hidden
      className="size-3.5 shrink-0 rounded-[2px]"
      style={{ background: item.fill ?? "transparent", border: `1.5px ${item.dashed ? "dashed" : "solid"} ${item.stroke ?? "#94a3b8"}` }}
    />
  );
}

/** The real header icon of a zone style (its pack image), or the generic zone icon in the outline colour when the
 * style has none or the pack is not downloaded. */
export function ZoneStyleIcon({ item, size }: { item: { icon: string | null; stroke: string | null }; size: number }) {
  const [failed, setFailed] = useState(false);
  const [pack, name] = item.icon?.split(":", 2) ?? [];
  if (pack && name && !failed)
    return <img src={api.icon(pack, name)} alt="" loading="lazy" width={size} height={size} onError={() => setFailed(true)} className="max-h-full max-w-full" />;
  return <span style={{ color: item.stroke ?? undefined }}><EditorIcon name="zone" size={size - 2} /></span>;
}

// Rendered only while open: DiagramView owns the open state, so a save (which re-renders the canvas) keeps it.
export default function PalettePanel({ rev, focusRef, onClose, onAdd }: Props) {
  const [packs, setPacks] = useState<{ offline: boolean; packs: Pack[] } | null>(null);
  const [icons, setIcons] = useState<IconEntry[]>([]);
  const [zoneStyles, setZoneStyles] = useState<ZoneStyle[]>([]);
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const input = useRef<HTMLInputElement>(null);
  const list = useRef<HTMLDivElement>(null);
  const [collapsed, setCollapsed] = useState<CollapsedState>(readCollapsed);
  const isCollapsed = useCallback((id: string) => collapsed[id] ?? defaultCollapsed(id), [collapsed]);
  const toggle = useCallback((id: string) => {
    setCollapsed((c) => {
      const next = { ...c, [id]: !(c[id] ?? defaultCollapsed(id)) };
      writeCollapsed(next);
      return next;
    });
  }, []);

  const refresh = useCallback(() => {
    api
      .packs()
      .then(async (r) => {
        setPacks(r);
        setZoneStyles(await api.zoneStyles().catch(() => []));
        setIcons(await loadIcons(r.packs));
        setError(null);
      })
      .catch((e: unknown) => setError(e instanceof Error ? e.message : String(e)));
  }, []);
  useEffect(refresh, [refresh, rev]);
  // a fetch runs in the background: look again while one is running
  const fetching = packs?.packs.some((p) => p.fetching) ?? false;
  useEffect(() => {
    if (!fetching) return;
    const t = setInterval(refresh, 1500);
    return () => clearInterval(t);
  }, [fetching, refresh]);

  useEffect(() => {
    focusRef.current = () => {
      input.current?.focus();
      input.current?.select();
    };
    return () => {
      focusRef.current = null;
    };
  }, [focusRef]);

  const corpus = useMemo(() => buildCorpus(icons, zoneStyles), [icons, zoneStyles]);
  const results = useMemo(() => search(corpus, query), [corpus, query]);
  const cats = useMemo(() => categorize(corpus.items), [corpus]);
  const searching = query.trim() !== "";
  const rows = useMemo<PaletteRow[]>(
    () => (searching ? results.map((item): PaletteRow => ({ type: "item", item, cat: categoryOf(item) })) : paletteRows(cats, isCollapsed)),
    [searching, results, cats, isCollapsed],
  );
  // the items in view, in order: what the arrow keys walk and Enter adds
  const entries = useMemo(() => rows.flatMap((r, row) => (r.type === "item" ? [{ item: r.item, row }] : [])), [rows]);
  const virt = useVirtualizer({ count: rows.length, getScrollElement: () => list.current, estimateSize: (i) => (rows[i]?.type === "item" ? 36 : 32), overscan: 8 });
  useEffect(() => setActive(0), [query]);
  useEffect(() => {
    const row = entries[active]?.row;
    if (row !== undefined) virt.scrollToIndex(row, { align: "auto" });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [active]);

  const missing = packs?.packs.filter((p) => !p.fetched) ?? [];
  const fetchPack = (name: string) => {
    api
      .fetchPack(name)
      .then(refresh)
      .catch((e: Error) => setError(e.message));
  };

  const onKey = (e: React.KeyboardEvent) => {
    e.stopPropagation(); // typing here must not trigger canvas shortcuts
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActive((a) => Math.min(a + 1, entries.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActive((a) => Math.max(a - 1, 0));
    } else if (e.key === "Enter" && entries[active]) {
      e.preventDefault();
      onAdd(entries[active].item);
    } else if (e.key === "Escape") {
      onClose();
    }
  };

  return (
    <div
      className="relative z-10 flex h-full w-72 shrink-0 flex-col overflow-hidden border-r border-slate-200 bg-white text-slate-700 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200"
      onPointerDown={(e) => e.stopPropagation()}
      onDoubleClick={(e) => e.stopPropagation()}
      onWheel={(e) => e.stopPropagation()}
    >
      <button
        onClick={onClose}
        aria-label="Hide the palette"
        title="Hide the palette"
        className="absolute top-2 right-2 z-10 rounded px-1.5 text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-700"
      >
        «
      </button>
      <input
        ref={input}
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        onKeyDown={onKey}
        placeholder="Search icons and shapes ( / )"
        aria-label="Search the palette"
        className="m-2 mr-8 rounded border border-slate-300 bg-white px-2 py-1.5 text-sm text-slate-900 outline-none focus:border-blue-500 dark:border-slate-600 dark:bg-slate-900 dark:text-slate-100"
      />
      <div ref={list} className="min-h-0 flex-1 overflow-y-auto px-1 pb-1" role="listbox" aria-label="Palette results">
        <div className="relative w-full" style={{ height: virt.getTotalSize() }}>
          {virt.getVirtualItems().map((vr) => {
            const r = rows[vr.index];
            if (!r) return null;
            const pos = { top: vr.start, height: vr.size };
            if (r.type === "subheader")
              return (
                <div key={`s-${vr.index}`} className="absolute inset-x-0 flex items-end px-3 pb-0.5 text-[10px] font-semibold tracking-wide text-slate-400 uppercase" style={pos}>
                  {r.title}
                </div>
              );
            if (r.type === "header")
              return (
                <button
                  key={`h-${r.cat.id}`}
                  type="button"
                  aria-expanded={!r.collapsed}
                  onClick={() => toggle(r.cat.id)}
                  className="absolute inset-x-0 flex items-center gap-1 rounded px-1 text-left text-xs font-semibold tracking-wide text-slate-500 uppercase hover:bg-slate-100 dark:hover:bg-slate-700"
                  style={pos}
                >
                  {r.collapsed ? <ChevronRight size={14} aria-hidden /> : <ChevronDown size={14} aria-hidden />}
                  <span className="flex-1 truncate">{r.cat.title}</span>
                  <span className="font-mono text-[10px] font-normal">{r.cat.items.length}</span>
                </button>
              );
            const it = r.item;
            const i = entries.findIndex((e) => e.row === vr.index);
            const name = iconNameOf(it);
            return (
              <div
                key={`i-${r.cat.id}-${it.type}-${"ref" in it ? it.ref : "style" in it ? it.style : "kind" in it ? it.kind : it.type}`}
                role="option"
                aria-selected={i === active}
                draggable
                onDragStart={(e) => {
                  e.dataTransfer.setData(PALETTE_MIME, JSON.stringify(it));
                  e.dataTransfer.effectAllowed = "copy";
                }}
                onClick={() => setActive(i)}
                onDoubleClick={() => onAdd(it)}
                className={`absolute inset-x-0 flex cursor-grab items-center gap-2 rounded px-2 text-sm ${i === active ? "bg-blue-100 dark:bg-blue-900/50" : "hover:bg-slate-100 dark:hover:bg-slate-700"}`}
                style={pos}
              >
                <span className="flex h-7 w-8 shrink-0 items-center justify-center text-slate-600 dark:text-slate-300">
                  {it.type === "zoneStyle" ? (
                    <ZoneStyleIcon item={it} size={22} />
                  ) : name ? (
                    <EditorIcon name={name} size={20} />
                  ) : it.type === "icon" ? (
                    <img src={api.icon(it.pack, it.name)} alt="" loading="lazy" className="max-h-full max-w-full" />
                  ) : null}
                </span>
                <span className="min-w-0 flex-1 truncate">{it.title}</span>
                {it.type === "zoneStyle" && <ZoneSwatch item={it} />}
                {searching && <span className="shrink-0 font-mono text-[10px] text-slate-500">{r.cat.title}</span>}
              </div>
            );
          })}
        </div>
        {searching && results.length === 0 && <p className="px-2 py-3 text-sm text-slate-500">{noMatch(query)}</p>}
      </div>
      {error && <p className="px-3 py-1 text-xs text-red-600">{error}</p>}
      {missing.length > 0 && (
        <div className="border-t border-slate-200 px-3 py-2 text-xs dark:border-slate-700">
          <button
            type="button"
            aria-expanded={!isCollapsed("missing")}
            onClick={() => toggle("missing")}
            className="mb-1 flex w-full items-center gap-1 text-left text-xs font-semibold tracking-wide text-slate-500 uppercase"
          >
            {isCollapsed("missing") ? <ChevronRight size={14} aria-hidden /> : <ChevronDown size={14} aria-hidden />}
            <span className="flex-1">Not downloaded</span>
            <span className="font-mono text-[10px] font-normal">{missing.length}</span>
          </button>
          {!isCollapsed("missing") && missing.map((p) => (
            <div key={p.name} className="flex items-center justify-between py-0.5">
              <span className="truncate font-mono">{p.name}</span>
              <button
                onClick={() => fetchPack(p.name)}
                disabled={packs?.offline || p.fetching}
                title={packs?.offline ? "SPINAGRAM_OFFLINE=1: downloads are disabled" : `Download the ${p.name} icon pack`}
                className="rounded px-2 py-0.5 font-medium text-blue-700 hover:bg-blue-50 disabled:opacity-50 dark:text-blue-300 dark:hover:bg-slate-700"
              >
                {p.fetching ? "Fetching…" : "Fetch"}
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
