import { useMemo, useState } from "react";
import { api, type ThemeEntry } from "./api";
import { filterThemes, themeSections } from "./catalog";
import { CardSection, CatalogShell, cardClass, NoMatch } from "./CatalogShell";
import { href } from "./hooks";

/** Every theme as a card with its sample diagram, Built-in then Custom, narrowed by a search box. */
export default function ThemesPage({ themes, rev }: { themes: ThemeEntry[]; rev: number }) {
  const [query, setQuery] = useState("");
  const shown = useMemo(() => filterThemes(themes, query), [themes, query]);
  return (
    <CatalogShell
      query={query}
      onQuery={setQuery}
      placeholder="Search themes by name"
      label="Search themes"
      shown={shown.length}
      total={themes.length}
      noun="theme"
      filtering={query.trim() !== ""}
    >
      {themes.length > 0 && shown.length === 0 && <NoMatch what="themes" onClear={() => setQuery("")} />}
      {themeSections(shown).map((s) => (
        <CardSection key={s.label} label={s.label} count={s.items.length}>
          {s.items.map((t) => (
            <ThemeCard key={t.ref} t={t} rev={rev} />
          ))}
        </CardSection>
      ))}
    </CatalogShell>
  );
}

function ThemeCard({ t, rev }: { t: ThemeEntry; rev: number }) {
  const [failed, setFailed] = useState(false);
  return (
    <a href={href({ kind: "theme", ref: t.ref })} className={cardClass}>
      <div className="aspect-video border-b border-slate-100 bg-white dark:border-slate-800">
        {failed || t.error ? (
          <div className="grid h-full place-items-center px-4 text-center text-xs text-red-600">
            {t.error ? "theme failed to load" : "preview unavailable"}
          </div>
        ) : (
          <img
            src={api.themeThumbnail(t.ref, rev)}
            alt=""
            loading="lazy"
            onError={() => setFailed(true)}
            className="h-full w-full object-contain"
          />
        )}
      </div>
      <div className="flex items-center gap-2 px-3 py-2.5">
        <span className="truncate text-sm font-medium group-hover:text-accent">{t.name}</span>
        <span className="truncate font-mono text-[11px] text-slate-400">{t.builtin ? "built-in" : t.ref}</span>
        {t.active && (
          <span className="ml-auto rounded bg-emerald-100 px-1.5 text-[10px] text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300">
            active
          </span>
        )}
      </div>
    </a>
  );
}
