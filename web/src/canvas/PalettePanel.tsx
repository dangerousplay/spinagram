// The icon palette panel of the canvas: fuzzy search over every cached pack, built-in shapes, Zone, Row and
// Column; drag an item onto the canvas, or press Enter to add it at the centre (PAL-01..07).
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api, type Pack } from "../api";
import { buildCorpus, noMatch, search, type IconEntry, type PaletteItem } from "./palette";

export const PALETTE_MIME = "application/x-spinagram-palette";

type Props = {
  rev: number; // bumps when the packs change on disk
  focusRef: React.MutableRefObject<(() => void) | null>; // `/` and Ctrl/Cmd+K call this (the panel must be open)
  onClose: () => void; // the « button and Esc
  onAdd: (item: PaletteItem) => void; // Enter and double-click: add at the centre of the canvas
};

const iconCache = new Map<string, IconEntry[]>();

async function loadIcons(packs: Pack[]): Promise<IconEntry[]> {
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

// Rendered only while open: DiagramView owns the open state, so a save (which re-renders the canvas) keeps it.
export default function PalettePanel({ rev, focusRef, onClose, onAdd }: Props) {
  const [packs, setPacks] = useState<{ offline: boolean; packs: Pack[] } | null>(null);
  const [icons, setIcons] = useState<IconEntry[]>([]);
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const input = useRef<HTMLInputElement>(null);
  const list = useRef<HTMLUListElement>(null);

  const refresh = useCallback(() => {
    api
      .packs()
      .then(async (r) => {
        setPacks(r);
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

  const corpus = useMemo(() => buildCorpus(icons), [icons]);
  const results = useMemo(() => search(corpus, query), [corpus, query]);
  useEffect(() => setActive(0), [query]);
  useEffect(() => {
    list.current?.children[active]?.scrollIntoView({ block: "nearest" });
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
      setActive((a) => Math.min(a + 1, results.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActive((a) => Math.max(a - 1, 0));
    } else if (e.key === "Enter" && results[active]) {
      e.preventDefault();
      onAdd(results[active]);
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
      <ul ref={list} className="min-h-0 flex-1 overflow-y-auto px-1 pb-1" role="listbox" aria-label="Palette results">
        {results.map((it, i) => (
          <li
            key={`${it.type}-${"ref" in it ? it.ref : "kind" in it ? it.kind : it.type}`}
            role="option"
            aria-selected={i === active}
            draggable
            onDragStart={(e) => {
              e.dataTransfer.setData(PALETTE_MIME, JSON.stringify(it));
              e.dataTransfer.effectAllowed = "copy";
            }}
            onClick={() => setActive(i)}
            onDoubleClick={() => onAdd(it)}
            className={`flex cursor-grab items-center gap-2 rounded px-2 py-1 text-sm ${i === active ? "bg-blue-100 dark:bg-blue-900/50" : "hover:bg-slate-100 dark:hover:bg-slate-700"}`}
          >
            <span className="flex h-7 w-14 shrink-0 items-center justify-center">
              {it.type === "icon" ? (
                <img src={api.icon(it.pack, it.name)} alt="" loading="lazy" className="max-h-full max-w-full" />
              ) : (
                <span className="w-14 rounded border border-slate-400 px-1 text-center text-[10px] uppercase">{it.type === "shape" ? "box" : it.type}</span>
              )}
            </span>
            <span className="min-w-0 flex-1 truncate">{it.title}</span>
            <span className="shrink-0 font-mono text-[10px] text-slate-500">{it.type === "icon" ? it.pack : it.type === "shape" ? "shape" : "item"}</span>
          </li>
        ))}
        {query.trim() !== "" && results.length === 0 && <li className="px-2 py-3 text-sm text-slate-500">{noMatch(query)}</li>}
      </ul>
      {error && <p className="px-3 py-1 text-xs text-red-600">{error}</p>}
      {missing.length > 0 && (
        <div className="border-t border-slate-200 px-3 py-2 text-xs dark:border-slate-700">
          <p className="mb-1 font-medium text-slate-500">Not downloaded</p>
          {missing.map((p) => (
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
