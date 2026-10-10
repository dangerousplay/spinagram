import { useCallback, useEffect, useState } from "react";
import { api, type Pack, type ThemeEntry, type UiEvent, type Workspace } from "./api";
import DiagramView from "./DiagramView";
import { href, useEvents, useRoute, type Route } from "./hooks";
import PackView from "./PackView";
import ThemeView from "./ThemeView";

export type Revs = { diagrams: Record<string, number>; theme: number; packs: number };

export default function App() {
  const [route, go] = useRoute();
  const [ws, setWs] = useState<Workspace | null>(null);
  const [wsError, setWsError] = useState<string | null>(null);
  const [themes, setThemes] = useState<ThemeEntry[]>([]);
  const [packs, setPacks] = useState<{ offline: boolean; packs: Pack[] }>({ offline: false, packs: [] });
  const [revs, setRevs] = useState<Revs>({ diagrams: {}, theme: 0, packs: 0 });
  const [layout, setLayout] = useState<string | null>(null);
  const [layoutInit, setLayoutInit] = useState(false);

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

  // land on the first diagram (or the first theme when there are no specs)
  useEffect(() => {
    if (!ws || route.kind !== "none") return;
    const first = ws.files.flatMap((f) => f.diagrams)[0];
    if (first) go({ kind: "diagram", key: first.key }, true);
    else if (themes[0]) go({ kind: "theme", ref: themes[0].ref }, true);
  }, [ws, themes, route.kind, go]);

  const current =
    route.kind === "diagram" ? ws?.files.flatMap((f) => f.diagrams).find((d) => d.key === route.key) : undefined;

  return (
    <div className="flex h-full flex-col">
      <header className="flex h-12 shrink-0 items-center gap-4 border-b border-slate-200 px-4 dark:border-slate-800">
        <span className="font-semibold tracking-tight">
          spina<span className="text-accent">gram</span>
        </span>
        <span className="truncate text-xs text-slate-500" title={ws?.paths.join("\n")}>
          {ws ? `${ws.paths.map((p) => p.split("/").pop()).join(", ")} · theme ${ws.theme_name}` : ""}
        </span>
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
        <Nav route={route} ws={ws} themes={themes} packs={packs.packs} />
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
          ) : ws ? (
            <Empty title="No diagrams" body={`No *.yaml, *.yml or *.py specs in ${ws.paths.join(", ")}.`} />
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

function NavLink({ to, active, children, title }: { to: Route; active: boolean; children: React.ReactNode; title?: string }) {
  return (
    <a
      href={href(to)}
      title={title}
      className={`flex items-center gap-2 rounded-md px-2 py-1 text-sm ${
        active
          ? "bg-accent-soft font-medium text-blue-900 dark:bg-blue-950 dark:text-blue-200"
          : "text-slate-700 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-900"
      }`}
    >
      {children}
    </a>
  );
}

function Section({ title, count, children }: { title: string; count?: number; children: React.ReactNode }) {
  return (
    <section className="mb-5">
      <h2 className="mb-1 flex items-center justify-between px-2 text-[11px] font-semibold tracking-wider text-slate-500 uppercase">
        {title}
        {count !== undefined && <span className="font-normal">{count}</span>}
      </h2>
      {children}
    </section>
  );
}

function Nav({ route, ws, themes, packs }: { route: Route; ws: Workspace | null; themes: ThemeEntry[]; packs: Pack[] }) {
  const nDiagrams = ws?.files.reduce((n, f) => n + f.diagrams.length, 0);
  return (
    <nav className="w-72 shrink-0 overflow-y-auto border-r border-slate-200 p-3 dark:border-slate-800">
      <Section title="Diagrams" count={nDiagrams}>
        {ws?.files.length === 0 && <p className="px-2 text-xs text-slate-500">No specs found.</p>}
        {ws?.files.map((f) => (
          <div key={f.path} className="mb-2">
            <div
              className={`flex items-center gap-1 px-2 font-mono text-[11px] ${f.error ? "text-red-600" : "text-slate-500"}`}
              title={f.error ?? f.path}
            >
              {f.error && <span aria-label="error">●</span>}
              <span className="truncate">{f.path}</span>
            </div>
            {f.diagrams.map((d) => (
              <NavLink
                key={d.key}
                to={{ kind: "diagram", key: d.key }}
                active={route.kind === "diagram" && route.key === d.key}
                title={`${d.id} — ${d.title}${d.auto ? " (auto layout)" : ""}`}
              >
                <span className="shrink-0 font-mono text-[11px] text-slate-400">{d.id}</span>
                <span className="truncate">{d.title}</span>
              </NavLink>
            ))}
          </div>
        ))}
      </Section>
      <Section title="Themes" count={themes.length}>
        {themes.map((t) => (
          <NavLink key={t.ref} to={{ kind: "theme", ref: t.ref }} active={route.kind === "theme" && route.ref === t.ref}>
            <span className="truncate">{t.name}</span>
            {t.active && (
              <span className="ml-auto rounded bg-emerald-100 px-1.5 text-[10px] text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300">
                active
              </span>
            )}
            {t.error && <span className="text-red-600">●</span>}
          </NavLink>
        ))}
      </Section>
      <Section title="Icon packs" count={packs.length}>
        {packs.map((p) => (
          <NavLink key={p.name} to={{ kind: "pack", name: p.name }} active={route.kind === "pack" && route.name === p.name}>
            <span
              className={`size-1.5 shrink-0 rounded-full ${
                p.fetching ? "animate-pulse bg-amber-500" : p.error ? "bg-red-500" : p.fetched ? "bg-emerald-500" : "bg-slate-300 dark:bg-slate-600"
              }`}
            />
            <span className="truncate">{p.name}</span>
            <span className="ml-auto text-[11px] text-slate-400">{p.fetched ? p.count : "—"}</span>
          </NavLink>
        ))}
      </Section>
    </nav>
  );
}
