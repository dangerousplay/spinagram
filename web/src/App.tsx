import { useCallback, useEffect, useMemo, useState } from "react";
import { api, type DiagramRef, type Pack, type ThemeEntry, type UiEvent, type Workspace } from "./api";
import { pushRecent, recentStore, visibleRecents } from "./catalog";
import DiagramsPage from "./DiagramsPage";
import DiagramView from "./DiagramView";
import { href, useEvents, useRoute, type Route } from "./hooks";
import PacksPage from "./PacksPage";
import PackView from "./PackView";
import ThemesPage from "./ThemesPage";
import ThemeView from "./ThemeView";

export type Revs = { diagrams: Record<string, number>; theme: number; packs: number };

const DOCS_URL = "https://dangerousplay.github.io/spinagram/docs/";
const SECTION = { diagrams: "diagrams", diagram: "diagrams", themes: "themes", theme: "themes", packs: "packs", pack: "packs" } as const;

export default function App() {
  const [route] = useRoute();
  const [ws, setWs] = useState<Workspace | null>(null);
  const [wsError, setWsError] = useState<string | null>(null);
  const [themes, setThemes] = useState<ThemeEntry[]>([]);
  const [packs, setPacks] = useState<{ offline: boolean; packs: Pack[] }>({ offline: false, packs: [] });
  const [revs, setRevs] = useState<Revs>({ diagrams: {}, theme: 0, packs: 0 });
  const [layout, setLayout] = useState<string | null>(null);
  const [layoutInit, setLayoutInit] = useState(false);
  const store = useMemo(() => recentStore(), []);
  const [recents, setRecents] = useState<string[]>(() => store.load());
  const section = SECTION[route.kind];

  // opening a diagram makes it the newest recent entry
  useEffect(() => {
    if (route.kind !== "diagram") return;
    setRecents((keys) => {
      const next = pushRecent(keys, route.key);
      store.save(next);
      return next;
    });
  }, [route, store]);

  const loadWs = useCallback(() => {
    api
      .workspace()
      .then((w) => {
        setWs(w);
        setWsError(null);
      })
      .catch((e: Error) => setWsError(e.message));
  }, []);
  const loadThemes = useCallback(() => void api.themes().then(setThemes).catch(() => {}), []);
  const loadPacks = useCallback(() => void api.packs().then(setPacks).catch(() => {}), []);

  const onEvent = useCallback(
    (e: UiEvent) => {
      switch (e.type) {
        case "hello":
          loadWs();
          loadThemes();
          loadPacks();
          setRevs((r) => ({ ...r, theme: r.theme + 1, packs: r.packs + 1 }));
          break;
        case "workspace":
          loadWs();
          break;
        case "diagram":
          setRevs((r) => {
            const d = { ...r.diagrams };
            for (const k of e.keys) d[k] = (d[k] ?? 0) + 1;
            return { ...r, diagrams: d };
          });
          break;
        case "theme":
          loadThemes();
          setRevs((r) => ({ ...r, theme: r.theme + 1 }));
          break;
        case "pack":
          loadPacks();
          if (e.status !== "fetching") setRevs((r) => ({ ...r, packs: r.packs + 1 }));
          break;
      }
    },
    [loadWs, loadThemes, loadPacks],
  );
  const connected = useEvents(onEvent);

  useEffect(() => {
    if (ws && !layoutInit) {
      setLayout(ws.layout);
      setLayoutInit(true);
    }
  }, [ws, layoutInit]);

  const current =
    route.kind === "diagram" ? ws?.files.flatMap((f) => f.diagrams).find((d) => d.key === route.key) : undefined;

  const allDiagrams = useMemo(() => ws?.files.flatMap((f) => f.diagrams) ?? [], [ws]);
  const recentKeys = useMemo(
    () => (ws ? visibleRecents(recents, new Set(allDiagrams.map((d) => d.key))) : []),
    [ws, recents, allDiagrams],
  );
  const recentDiagrams = recentKeys.map((k) => allDiagrams.find((d) => d.key === k)!);

  return (
    <div className="flex h-full flex-col">
      <header className="flex h-12 shrink-0 items-center gap-6 border-b border-slate-200 px-4 dark:border-slate-800">
        <a href={href({ kind: "diagrams" })} className="font-semibold tracking-tight">
          spina<span className="text-accent">gram</span>
        </a>
        <nav className="flex items-center gap-1" aria-label="Sections">
          <TopLink to={{ kind: "diagrams" }} active={section === "diagrams"}>
            Diagrams
          </TopLink>
          <TopLink to={{ kind: "themes" }} active={section === "themes"}>
            Themes
          </TopLink>
          <TopLink to={{ kind: "packs" }} active={section === "packs"}>
            Icon packs
          </TopLink>
          <a
            href={DOCS_URL}
            target="_blank"
            rel="noopener noreferrer"
            className="rounded-md px-2.5 py-1 text-sm text-slate-600 hover:bg-slate-100 hover:text-slate-900 dark:text-slate-300 dark:hover:bg-slate-900"
          >
            Docs <span aria-hidden>↗</span>
          </a>
        </nav>
        <div className="ml-auto flex items-center gap-3">
          {route.kind === "diagram" && ws && (
            <label className="flex items-center gap-2 text-xs text-slate-500">
              Layout
              <select
                className="rounded-md border border-slate-300 bg-white px-2 py-1 text-xs text-slate-800 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200"
                value={layout ?? ""}
                onChange={(e) => setLayout(e.target.value || null)}
                disabled={current ? !current.auto : false}
                title={current && !current.auto ? "fixed layout: this diagram has explicit coordinates" : undefined}
              >
                <option value="">spec default</option>
                {ws.engines.map((en) => (
                  <option key={en.name} value={en.name} disabled={!!en.hint} title={en.hint ?? undefined}>
                    {en.name}
                    {en.hint ? " (unavailable)" : ""}
                  </option>
                ))}
              </select>
            </label>
          )}
          <span
            className={`flex items-center gap-1.5 text-xs ${connected ? "text-emerald-600" : "text-amber-600"}`}
            title={connected ? "live: changes on disk re-render here" : "reconnecting to spinagram serve…"}
          >
            <span className={`size-2 rounded-full ${connected ? "bg-emerald-500" : "animate-pulse bg-amber-500"}`} />
            {connected ? "live" : "offline"}
          </span>
        </div>
      </header>
      <div className="flex min-h-0 flex-1">
        <Recents route={route} diagrams={recentDiagrams} ws={ws} />
        <main className="min-w-0 flex-1">
          {wsError && !ws ? (
            <Empty title="Cannot reach spinagram serve" body={wsError} />
          ) : route.kind === "diagram" ? (
            <DiagramView
              key={route.key}
              diagram={current}
              diagramKey={route.key}
              file={ws?.files.find((f) => route.key.startsWith(`${f.path}#`))}
              themeError={ws?.theme_error ?? null}
              layout={current?.auto ? layout : null}
              rev={revs.diagrams[route.key] ?? 0}
            />
          ) : route.kind === "theme" ? (
            <ThemeView key={route.ref} themeRef={route.ref} rev={revs.theme} />
          ) : route.kind === "pack" ? (
            <PackView
              key={route.name}
              pack={packs.packs.find((p) => p.name === route.name)}
              offline={packs.offline}
              rev={revs.packs}
              onFetched={loadPacks}
            />
          ) : route.kind === "themes" ? (
            <ThemesPage themes={themes} rev={revs.theme} />
          ) : route.kind === "packs" ? (
            <PacksPage packs={packs.packs} rev={revs.packs} />
          ) : ws ? (
            <DiagramsPage ws={ws} revs={revs.diagrams} />
          ) : null}
        </main>
      </div>
    </div>
  );
}

function Empty({ title, body }: { title: string; body: string }) {
  return (
    <div className="grid h-full place-items-center p-8 text-center">
      <div>
        <p className="font-medium">{title}</p>
        <p className="mt-1 text-sm text-slate-500">{body}</p>
      </div>
    </div>
  );
}

function TopLink({ to, active, children }: { to: Route; active: boolean; children: React.ReactNode }) {
  return (
    <a
      href={href(to)}
      aria-current={active ? "page" : undefined}
      className={`rounded-md px-2.5 py-1 text-sm ${
        active
          ? "bg-accent-soft font-medium text-blue-900 dark:bg-blue-950 dark:text-blue-200"
          : "text-slate-600 hover:bg-slate-100 hover:text-slate-900 dark:text-slate-300 dark:hover:bg-slate-900"
      }`}
    >
      {children}
    </a>
  );
}

function Recents({ route, diagrams, ws }: { route: Route; diagrams: DiagramRef[]; ws: Workspace | null }) {
  return (
    <aside className="flex w-64 shrink-0 flex-col border-r border-slate-200 dark:border-slate-800" aria-label="Recent diagrams">
      <div className="flex-1 overflow-y-auto p-3">
        <h2 className="mb-1 px-2 text-[11px] font-semibold tracking-wider text-slate-500 uppercase">Recent</h2>
        {diagrams.length === 0 && <p className="px-2 text-xs text-slate-500">Diagrams you open appear here.</p>}
        {diagrams.map((d) => {
          const active = route.kind === "diagram" && route.key === d.key;
          return (
            <a
              key={d.key}
              href={href({ kind: "diagram", key: d.key })}
              title={`${d.id} — ${d.title}`}
              className={`flex items-center gap-2 rounded-md px-2 py-1 text-sm ${
                active
                  ? "bg-accent-soft font-medium text-blue-900 dark:bg-blue-950 dark:text-blue-200"
                  : "text-slate-700 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-900"
              }`}
            >
              <span className="shrink-0 font-mono text-[11px] text-slate-400">{d.id}</span>
              <span className="truncate">{d.title}</span>
            </a>
          );
        })}
      </div>
      {ws && (
        <p className="truncate border-t border-slate-200 px-4 py-2 text-[11px] text-slate-500 dark:border-slate-800" title={ws.paths.join("\n")}>
          {ws.paths.map((p) => p.split("/").pop()).join(", ")} · theme {ws.theme_name}
        </p>
      )}
    </aside>
  );
}
