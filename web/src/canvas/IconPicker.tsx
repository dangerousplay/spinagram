// "Change…" for a node's icon: a small search over the icons of the downloaded packs (the palette's corpus and fuzzy
// search), a pick writes `icon: pack:name`.
import { useEffect, useMemo, useRef, useState } from "react";
import { api } from "../api";
import { loadIcons } from "./PalettePanel";
import { buildCorpus, noMatch, search, type IconEntry } from "./palette";

type Props = { onPick: (ref: string) => void; onClose: () => void };

const LIMIT = 40;

export default function IconPicker({ onPick, onClose }: Props) {
  const [icons, setIcons] = useState<IconEntry[] | null>(null);
  const [query, setQuery] = useState("");
  const input = useRef<HTMLInputElement>(null);
  useEffect(() => {
    input.current?.focus();
    let live = true;
    api
      .packs()
      .then((r) => loadIcons(r.packs))
      .then((l) => live && setIcons(l))
      .catch(() => live && setIcons([]));
    return () => {
      live = false;
    };
  }, []);
  const corpus = useMemo(() => buildCorpus(icons ?? []), [icons]);
  const results = useMemo(() => (query.trim() ? search(corpus, query, LIMIT) : []).filter((i) => i.type === "icon"), [corpus, query]);
  return (
    <div role="dialog" aria-label="Choose an icon" className="absolute right-2 bottom-2 left-2 z-20 rounded-lg border border-slate-300 bg-white p-2 shadow-xl dark:border-slate-700 dark:bg-slate-900">
      <div className="mb-1 flex items-center gap-1">
        <input
          ref={input}
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => {
            e.stopPropagation();
            if (e.key === "Escape") onClose();
            if (e.key === "Enter" && results[0]?.type === "icon") onPick(results[0].ref);
          }}
          placeholder="Search icons"
          aria-label="Search icons"
          className="min-w-0 flex-1 rounded border border-slate-300 bg-white px-2 py-1 text-sm text-slate-900 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-100"
        />
        <button type="button" onClick={onClose} aria-label="Close the icon picker" className="rounded px-2 text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-800">
          ×
        </button>
      </div>
      <div className="max-h-52 overflow-y-auto">
        {icons === null && <p className="px-1 py-2 text-xs text-slate-500">Loading icons…</p>}
        {results.map((it) =>
          it.type === "icon" ? (
            <button key={it.ref} type="button" onClick={() => onPick(it.ref)} className="flex w-full items-center gap-2 rounded px-1 py-1 text-left text-sm hover:bg-slate-100 dark:hover:bg-slate-800">
              <img src={api.icon(it.pack, it.name)} alt="" loading="lazy" className="size-5 shrink-0" />
              <span className="min-w-0 flex-1 truncate">{it.title}</span>
              <span className="font-mono text-[10px] text-slate-500">{it.pack}</span>
            </button>
          ) : null,
        )}
        {icons !== null && query.trim() !== "" && results.length === 0 && <p className="px-1 py-2 text-xs text-slate-500">{noMatch(query)}</p>}
      </div>
    </div>
  );
}
