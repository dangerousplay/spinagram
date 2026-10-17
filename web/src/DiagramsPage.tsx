import { useMemo, useState } from "react";
import { api, type DiagramRef, type Workspace } from "./api";
import { allTags, filterDiagrams, groupByCategory } from "./catalog";
import { CardSection, CatalogShell, cardClass } from "./CatalogShell";
import { href } from "./hooks";

type Props = { ws: Workspace; revs: Record<string, number> };

/** Every diagram as a card, grouped by category, narrowed by a search box and tag chips. */
export default function DiagramsPage({ ws, revs }: Props) {
  const [query, setQuery] = useState("");
  const [tags, setTags] = useState<string[]>([]);
  const all = useMemo(() => ws.files.flatMap((f) => f.diagrams), [ws]);
  const tagCounts = useMemo(() => allTags(all), [all]);
  const shown = useMemo(() => filterDiagrams(all, query, tags), [all, query, tags]);
  const groups = useMemo(() => groupByCategory(shown), [shown]);
  const broken = ws.files.filter((f) => f.error);
  const filtering = query.trim() !== "" || tags.length > 0;
  const toggle = (t: string) => setTags((cur) => (cur.includes(t) ? cur.filter((x) => x !== t) : [...cur, t]));
  const clear = () => {
    setQuery("");
    setTags([]);
  };

  return (
    <CatalogShell
      query={query}
      onQuery={setQuery}
      placeholder="Search diagrams by id, title, category or tag"
      label="Search diagrams"
      shown={shown.length}
      total={all.length}
      noun="diagram"
      filtering={filtering}
    >
      {tagCounts.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-1.5" role="group" aria-label="Filter by tag">
          {tagCounts.map(({ tag, count }) => {
            const on = tags.includes(tag);
            return (
              <button
                key={tag}
                type="button"
                aria-pressed={on}
                onClick={() => toggle(tag)}
                className={`rounded-full border px-2.5 py-0.5 text-xs transition-colors ${
                  on
                    ? "border-accent bg-accent text-white"
                    : "border-slate-300 text-slate-600 hover:border-slate-400 hover:bg-slate-50 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-900"
                }`}
              >
                {tag}
                <span className={`ml-1 ${on ? "text-blue-100" : "text-slate-400"}`}>{count}</span>
              </button>
            );
          })}
          {filtering && (
            <button type="button" onClick={clear} className="px-2 text-xs text-accent hover:underline">
              Clear filters
            </button>
          )}
        </div>
      )}

      {broken.length > 0 && (
        <section className="mt-6" aria-label="Specs with errors">
          <h2 className="mb-2 text-[11px] font-semibold tracking-wider text-red-600 uppercase">
            Specs that failed to load
          </h2>
          <ul className="space-y-2">
            {broken.map((f) => (
              <li
                key={f.path}
                className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-xs dark:border-red-900 dark:bg-red-950/40"
              >
                <span className="font-mono font-medium text-red-700 dark:text-red-300">{f.path}</span>
                <pre className="mt-1 whitespace-pre-wrap text-red-800 dark:text-red-200">{f.error}</pre>
              </li>
            ))}
          </ul>
        </section>
      )}

      {ws.truncated && (
        <p className="mt-4 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-900 dark:border-amber-900 dark:bg-amber-950 dark:text-amber-200" role="status">
          This folder holds more specs than spinagram loads at once; only the first 2,000 are shown. Open a subfolder to see the rest.
        </p>
      )}

      {all.length === 0 && broken.length === 0 && (
        <p className="mt-16 text-center text-sm text-slate-500">
          No diagrams in {ws.paths.join(", ")} (specs are *.yaml, *.yml and *.py files, subfolders included).
        </p>
      )}

      {all.length > 0 && shown.length === 0 && (
        <div className="mt-16 text-center">
          <p className="font-medium">No diagrams match</p>
          <button type="button" onClick={clear} className="mt-2 text-sm text-accent hover:underline">
            Clear search and tags
          </button>
        </div>
      )}

      {groups.map((g) => (
        <CardSection key={g.category} label={g.label} count={g.diagrams.length}>
          {g.diagrams.map((d) => (
            <Card key={d.key} d={d} rev={revs[d.key] ?? 0} />
          ))}
        </CardSection>
      ))}
    </CatalogShell>
  );
}

function Card({ d, rev }: { d: DiagramRef; rev: number }) {
  const [failed, setFailed] = useState(false);
  return (
    <a
      href={href({ kind: "diagram", key: d.key })}
      title={d.subtitle ? `${d.title} — ${d.subtitle}` : d.title}
      className={cardClass}
    >
      <div className="aspect-video border-b border-slate-100 bg-white dark:border-slate-800">
        {failed ? (
          <div className="grid h-full place-items-center text-xs text-slate-400">preview unavailable</div>
        ) : (
          <img
            src={api.thumbnail(d.key, rev)}
            alt=""
            loading="lazy"
            onError={() => setFailed(true)}
            className="h-full w-full object-contain"
          />
        )}
      </div>
      <div className="px-3 py-2.5">
        <div className="flex items-baseline gap-2">
          <span className="shrink-0 font-mono text-[11px] text-slate-400">{d.id}</span>
          <span className="truncate text-sm font-medium group-hover:text-accent">{d.title}</span>
        </div>
        <p className="mt-0.5 truncate font-mono text-[10px] text-slate-400" title={d.key.slice(0, d.key.lastIndexOf("#"))}>
          {d.key.slice(0, d.key.lastIndexOf("#"))}
        </p>
        {d.tags.length > 0 && (
          <div className="mt-1.5 flex flex-wrap gap-1">
            {d.tags.map((t) => (
              <span
                key={t}
                className="rounded bg-slate-100 px-1.5 py-px text-[10px] text-slate-600 dark:bg-slate-800 dark:text-slate-300"
              >
                {t}
              </span>
            ))}
          </div>
        )}
      </div>
    </a>
  );
}
