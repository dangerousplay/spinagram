import { useVirtualizer } from "@tanstack/react-virtual";
import { useEffect, useMemo, useRef, useState } from "react";
import { api, type Pack, type PackIcon } from "./api";

const CELL = 116;
const ROW = 112;

type Props = { pack: Pack | undefined; offline: boolean; rev: number; onFetched: () => void };

export default function PackView({ pack, offline, rev, onFetched }: Props) {
  const [icons, setIcons] = useState<PackIcon[] | null>(null);
  const [query, setQuery] = useState("");
  const [fetchError, setFetchError] = useState<string | null>(null);

  useEffect(() => {
    if (!pack?.fetched) {
      setIcons(null);
      return;
    }
    let live = true;
    api
      .packIcons(pack.name)
      .then((xs) => live && setIcons(xs))
      .catch(() => live && setIcons(null));
    return () => {
      live = false;
    };
  }, [pack?.name, pack?.fetched, rev]);

  const shown = useMemo(() => {
    const words = query.toLowerCase().split(/\s+/).filter(Boolean);
    if (!icons || !words.length) return icons ?? [];
    return icons.filter((i) => words.every((w) => i.name.includes(w) || i.aliases.some((a) => a.includes(w))));
  }, [icons, query]);

  if (!pack) return <p className="p-8 text-sm text-slate-500">Unknown pack.</p>;

  const fetchNow = () => {
    setFetchError(null);
    api
      .fetchPack(pack.name)
      .then(onFetched)
      .catch((e: Error) => setFetchError(e.message));
  };
  const error = fetchError ?? pack.error;

  return (
    <div className="flex h-full flex-col">
      <div className="border-b border-slate-200 p-6 dark:border-slate-800">
        <div className="flex flex-wrap items-start gap-4">
          <div className="min-w-0">
            <h1 className="text-xl font-semibold tracking-tight">
              {pack.title} <span className="font-mono text-sm font-normal text-slate-500">{pack.name}</span>
            </h1>
            <p className="mt-1 text-xs text-slate-500">
              {pack.source} · version <span className="font-mono">{pack.version}</span> · {pack.origin}
              {pack.homepage && (
                <>
                  {" · "}
                  <a className="text-accent hover:underline" href={pack.homepage} target="_blank" rel="noreferrer">
                    homepage
                  </a>
                </>
              )}
            </p>
            {pack.license && <p className="mt-1 text-xs text-slate-400">{pack.license}</p>}
          </div>
          <div className="ml-auto flex items-center gap-3">
            {pack.fetched && <span className="text-sm text-slate-500">{pack.count} icons</span>}
            <button
              onClick={fetchNow}
              disabled={offline || pack.fetching}
              title={offline ? "SPINAGRAM_OFFLINE=1: downloads are disabled" : undefined}
              className={`rounded-md px-3 py-1.5 text-sm font-medium disabled:cursor-not-allowed disabled:opacity-50 ${
                pack.fetched
                  ? "border border-slate-300 hover:bg-slate-100 dark:border-slate-700 dark:hover:bg-slate-800"
                  : "bg-accent text-white hover:bg-blue-700"
              }`}
            >
              {pack.fetching ? "Fetching…" : pack.fetched ? "Re-fetch" : "Fetch"}
            </button>
          </div>
        </div>
        {error && <p className="mt-3 rounded-md bg-red-50 p-2 font-mono text-xs text-red-800 dark:bg-red-950 dark:text-red-300">{error}</p>}
        {pack.fetched && (
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder={`Search ${pack.count} icons by name or alias…`}
            className="mt-4 w-full max-w-md rounded-md border border-slate-300 bg-white px-3 py-1.5 text-sm outline-none focus:border-accent focus:ring-2 focus:ring-accent-soft dark:border-slate-700 dark:bg-slate-900 dark:focus:ring-blue-900"
          />
        )}
      </div>
      {pack.fetching && !pack.fetched ? (
        <p className="animate-pulse p-8 text-sm text-slate-500">Downloading {pack.name}… this can take a minute.</p>
      ) : !pack.fetched ? (
        <p className="p-8 text-sm text-slate-500">
          Not downloaded yet. {offline ? "Downloads are disabled (SPINAGRAM_OFFLINE=1)." : "Press Fetch to download it into the icon cache."}
        </p>
      ) : (
        <IconGrid pack={pack.name} icons={shown} rev={rev} />
      )}
    </div>
  );
}

function IconGrid({ pack, icons, rev }: { pack: string; icons: PackIcon[]; rev: number }) {
  const scroller = useRef<HTMLDivElement>(null);
  const [cols, setCols] = useState(6);
  useEffect(() => {
    const el = scroller.current;
    if (!el) return;
    const ro = new ResizeObserver(() => setCols(Math.max(1, Math.floor((el.clientWidth - 32) / CELL))));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  const rows = Math.ceil(icons.length / cols);
  const v = useVirtualizer({ count: rows, getScrollElement: () => scroller.current, estimateSize: () => ROW, overscan: 4 });

  return (
    <div ref={scroller} className="min-h-0 flex-1 overflow-y-auto px-4 py-4">
      {!icons.length && <p className="p-4 text-sm text-slate-500">No icons match.</p>}
      <div className="relative" style={{ height: v.getTotalSize() }}>
        {v.getVirtualItems().map((row) => (
          <div key={row.key} className="absolute inset-x-0 flex" style={{ top: row.start, height: ROW }}>
            {icons.slice(row.index * cols, row.index * cols + cols).map((i) => (
              <figure
                key={i.name}
                className="flex flex-col items-center gap-1.5 rounded-lg p-2 hover:bg-slate-100 dark:hover:bg-slate-900"
                style={{ width: CELL }}
                title={`${pack}:${i.name}${i.aliases.length ? `\naliases: ${i.aliases.join(", ")}` : ""}\n${i.ext}${
                  i.tones.includes("dark") ? " · dark variant" : ""
                }`}
              >
                <div className="flex size-14 items-center justify-center rounded-md bg-white p-1.5 ring-1 ring-slate-200 dark:ring-slate-800">
                  <img src={`${api.icon(pack, i.name)}?rev=${rev}`} alt="" loading="lazy" className="max-h-full max-w-full" />
                </div>
                <figcaption className="w-full truncate text-center font-mono text-[10px] text-slate-600 dark:text-slate-400">
                  {i.name}
                </figcaption>
              </figure>
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}
