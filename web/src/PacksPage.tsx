import { useEffect, useMemo, useState } from "react";
import { api, type Pack, type PackIcon } from "./api";
import { filterPacks, packSections, sampleIcons } from "./catalog";
import { CardSection, CatalogShell, cardClass, NoMatch } from "./CatalogShell";
import { href } from "./hooks";

/** Every icon pack as a card with sample icons, Downloaded then Not downloaded, narrowed by a search box. */
export default function PacksPage({ packs, rev }: { packs: Pack[]; rev: number }) {
  const [query, setQuery] = useState("");
  const shown = useMemo(() => filterPacks(packs, query), [packs, query]);
  return (
    <CatalogShell
      query={query}
      onQuery={setQuery}
      placeholder="Search icon packs by name"
      label="Search icon packs"
      shown={shown.length}
      total={packs.length}
      noun="pack"
      filtering={query.trim() !== ""}
    >
      {packs.length > 0 && shown.length === 0 && <NoMatch what="packs" onClear={() => setQuery("")} />}
      {packSections(shown).map((s) => (
        <CardSection key={s.label} label={s.label} count={s.items.length}>
          {s.items.map((p) => (
            <PackCard key={p.name} p={p} rev={rev} />
          ))}
        </CardSection>
      ))}
    </CatalogShell>
  );
}

function PackCard({ p, rev }: { p: Pack; rev: number }) {
  const [icons, setIcons] = useState<PackIcon[] | null>(null);

  useEffect(() => {
    if (!p.fetched) {
      setIcons(null);
      return;
    }
    let live = true;
    api
      .packIcons(p.name)
      .then((xs) => live && setIcons(sampleIcons([...xs].sort((a, b) => a.name.localeCompare(b.name)))))
      .catch(() => live && setIcons([]));
    return () => {
      live = false;
    };
  }, [p.name, p.fetched, rev]);

  return (
    <a href={href({ kind: "pack", name: p.name })} className={cardClass} title={p.title}>
      <div className="aspect-video border-b border-slate-100 bg-white p-3 dark:border-slate-800 dark:bg-slate-900">
        {!p.fetched ? (
          <div className="grid h-full place-items-center text-xs text-slate-400">
            {p.fetching ? "Downloading…" : "Not downloaded"}
          </div>
        ) : (
          <div className="grid h-full grid-cols-6 grid-rows-2 place-items-center gap-2">
            {(icons ?? []).map((i) => (
              <img
                key={i.name}
                src={api.icon(p.name, i.name)}
                alt={i.name}
                title={`${p.name}:${i.name}`}
                loading="lazy"
                className="size-8 object-contain"
              />
            ))}
          </div>
        )}
      </div>
      <div className="flex items-center gap-2 px-3 py-2.5">
        <span
          className={`size-2 shrink-0 rounded-full ${
            p.fetching ? "animate-pulse bg-amber-500" : p.error ? "bg-red-500" : p.fetched ? "bg-emerald-500" : "bg-slate-300 dark:bg-slate-600"
          }`}
        />
        <span className="text-sm font-medium group-hover:text-accent">{p.name}</span>
        <span className="truncate text-xs text-slate-500">{p.title}</span>
        <span className="ml-auto shrink-0 text-[11px] text-slate-400">{p.fetched ? `${p.count} icons` : "—"}</span>
      </div>
    </a>
  );
}
