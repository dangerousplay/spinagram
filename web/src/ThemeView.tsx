import { useEffect, useState } from "react";
import { api, type FontRole, type StyleRow, type ThemeSheet } from "./api";

export default function ThemeView({ themeRef, rev }: { themeRef: string; rev: number }) {
  const [sheet, setSheet] = useState<ThemeSheet | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let live = true;
    api
      .theme(themeRef)
      .then((s) => live && (setSheet(s), setError(null)))
      .catch((e: Error) => live && setError(e.message));
    return () => {
      live = false;
    };
  }, [themeRef, rev]);

  if (error)
    return (
      <div className="p-8">
        <p className="font-semibold text-red-700 dark:text-red-400">Theme failed to load</p>
        <pre className="mt-2 font-mono text-xs whitespace-pre-wrap text-red-900 dark:text-red-300">{error}</pre>
      </div>
    );
  if (!sheet) return <p className="p-8 text-sm text-slate-500">Loading…</p>;

  return (
    <div className="h-full overflow-y-auto">
      <div className="mx-auto max-w-6xl space-y-10 p-8">
        <header>
          <h1 className="text-2xl font-semibold tracking-tight">{sheet.name}</h1>
          <p className="mt-1 text-sm text-slate-500">
            {sheet.extends ? (
              <>
                extends <code className="font-mono">{sheet.extends}</code> ·{" "}
              </>
            ) : null}
            <span className="font-mono text-xs">{sheet.root}</span>
          </p>
        </header>

        <Block title="Colours" note={`${sheet.colors.length} tokens`}>
          <div className="grid grid-cols-[repeat(auto-fill,minmax(150px,1fr))] gap-3">
            {sheet.colors.map((c) => (
              <div key={c.token} className="overflow-hidden rounded-lg border border-slate-200 dark:border-slate-800">
                <div className="h-14" style={{ background: c.hex ?? "transparent" }} />
                <div className="p-2 text-xs">
                  <div className="truncate font-mono font-medium" title={c.token}>
                    {c.token}
                  </div>
                  <div className="font-mono text-slate-500">{c.hex ?? "unresolved"}</div>
                  {c.via && <div className="truncate text-slate-400">→ {c.via}</div>}
                </div>
              </div>
            ))}
          </div>
        </Block>

        <Block title="Fonts">
          <div className="grid gap-3 md:grid-cols-2">
            {sheet.fonts.map((f) => (
              <FontCard key={f.role} font={f} themeRef={themeRef} sample={sheet.sample} rev={rev} />
            ))}
          </div>
        </Block>

        {Object.entries(sheet.styles).map(([kind, rows]) => (
          <Block key={kind} title={`Styles · ${kind}`} note={`${rows.length}`}>
            <div className="grid grid-cols-[repeat(auto-fill,minmax(220px,1fr))] gap-3">
              {rows.map((r) => (
                <StyleCard key={r.name} kind={kind} row={r} themeRef={themeRef} rev={rev} />
              ))}
            </div>
          </Block>
        ))}

        <div className="grid gap-10 md:grid-cols-2">
          <Block title="Defaults">
            <Tree value={sheet.defaults} />
          </Block>
          <Block title="Chrome & canvas">
            <Tree value={{ canvas: sheet.canvas, ...sheet.chrome, icons: sheet.icons }} />
          </Block>
        </div>
      </div>
    </div>
  );
}

function Block({ title, note, children }: { title: string; note?: string; children: React.ReactNode }) {
  return (
    <section>
      <h2 className="mb-3 flex items-baseline gap-2 text-sm font-semibold tracking-wider text-slate-500 uppercase">
        {title}
        {note && <span className="text-xs font-normal normal-case">{note}</span>}
      </h2>
      {children}
    </section>
  );
}

function FontCard({ font, themeRef, sample, rev }: { font: FontRole; themeRef: string; sample: string; rev: number }) {
  const family = `dk-${themeRef}-${font.role}-${rev}`;
  const files = font.files.filter((f) => f.available);
  useEffect(() => {
    const faces = files.map(
      (f) =>
        new FontFace(family, `url(${api.font(themeRef, font.role, f.key, rev)})`, {
          weight: String(f.weight),
          style: f.italic ? "italic" : "normal",
        }),
    );
    faces.forEach((ff) => {
      document.fonts.add(ff);
      ff.load().catch(() => {});
    });
    return () => faces.forEach((ff) => document.fonts.delete(ff));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [family, themeRef, font.role, rev]);
  const stack = `${files.length ? `"${family}", ` : ""}"${font.family}", ${font.fallback ?? "sans-serif"}`;
  const weights = files.length ? [...new Set(files.map((f) => f.weight))].sort() : Object.keys(font.figma).map(Number);
  return (
    <div className="rounded-lg border border-slate-200 p-4 dark:border-slate-800">
      <div className="flex items-baseline justify-between text-xs text-slate-500">
        <span className="font-mono font-medium text-slate-700 dark:text-slate-300">{font.role}</span>
        <span>
          {font.family}
          {files.length ? ` · ${files.length} file(s) embedded` : " · system font"}
        </span>
      </div>
      {(weights.length ? weights : [400]).map((w) => (
        <p key={w} className="mt-2 truncate text-xl" style={{ fontFamily: stack, fontWeight: w }}>
          <span className="mr-2 font-mono text-[10px] text-slate-400" style={{ fontFamily: "monospace" }}>
            {w}
          </span>
          {sample}
        </p>
      ))}
      {font.fallback && <p className="mt-2 text-[11px] text-slate-400">fallback: {font.fallback}</p>}
    </div>
  );
}

function StyleCard({ kind, row, themeRef, rev }: { kind: string; row: StyleRow; themeRef: string; rev: number }) {
  return (
    <div className="overflow-hidden rounded-lg border border-slate-200 dark:border-slate-800">
      {row.preview && (
        <div className="checker flex h-28 items-center justify-center bg-white p-2">
          <img src={api.preview(themeRef, kind, row.name, rev)} alt={`${kind} ${row.name}`} className="max-h-full max-w-full" />
        </div>
      )}
      <div className="p-2 text-xs">
        <div className="mb-1 font-mono font-medium">{row.name}</div>
        <div className="flex flex-wrap gap-1.5">
          {Object.entries(row.swatches).map(([k, hex]) => (
            <span key={k} className="flex items-center gap-1 text-slate-500" title={`${k}: ${hex}`}>
              <span className="size-3 rounded-sm ring-1 ring-black/10" style={{ background: hex }} />
              {k}
            </span>
          ))}
        </div>
        {typeof row.value !== "object" && <div className="mt-1 font-mono text-slate-500">{String(row.value)}</div>}
        {typeof row.value === "object" && row.value !== null && (
          <div className="mt-1 font-mono text-[11px] break-words text-slate-500">
            {Object.entries(row.value as Record<string, unknown>)
              .filter(([k]) => !(k in row.swatches))
              .map(([k, v]) => `${k}: ${JSON.stringify(v)}`)
              .join(" · ")}
          </div>
        )}
      </div>
    </div>
  );
}

function Tree({ value }: { value: unknown }) {
  if (value === null || typeof value !== "object")
    return <span className="font-mono text-xs text-slate-600 dark:text-slate-400">{JSON.stringify(value)}</span>;
  if (Array.isArray(value)) return <span className="font-mono text-xs text-slate-600 dark:text-slate-400">{JSON.stringify(value)}</span>;
  return (
    <dl className="space-y-1 border-l border-slate-200 pl-3 dark:border-slate-800">
      {Object.entries(value as Record<string, unknown>).map(([k, v]) => (
        <div key={k} className={typeof v === "object" && v !== null && !Array.isArray(v) ? "" : "flex gap-2"}>
          <dt className="font-mono text-xs font-medium">{k}</dt>
          <dd>
            <Tree value={v} />
          </dd>
        </div>
      ))}
    </dl>
  );
}
