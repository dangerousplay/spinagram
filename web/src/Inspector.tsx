// CSS inspector: hit-testing in scene coordinates, the highlight overlay and the styles panel.
import type { CssDecl, CssElement, CssTrace, Geometry, StyleReport } from "./api";
import { chip, elementLabel } from "./inspect";

type Box = [number, number, number, number];

const inBox = ([x, y, w, h]: Box, px: number, py: number) => px >= x && px <= x + w && py >= y && py <= y + h;

function segDist(px: number, py: number, [x1, y1]: [number, number], [x2, y2]: [number, number]) {
  const dx = x2 - x1;
  const dy = y2 - y1;
  const len = dx * dx + dy * dy;
  const t = len ? Math.max(0, Math.min(1, ((px - x1) * dx + (py - y1) * dy) / len)) : 0;
  return Math.hypot(px - (x1 + t * dx), py - (y1 + t * dy));
}

/** Points along an edge: quadratic curves are sampled, polylines kept. */
function edgePoints(g: Geometry): [number, number][] {
  const p = g.points ?? [];
  if (g.route !== "curve" || p.length !== 3) return p;
  const [[x0, y0], [qx, qy], [x2, y2]] = p;
  return Array.from({ length: 17 }, (_, i) => {
    const t = i / 16;
    return [(1 - t) ** 2 * x0 + 2 * (1 - t) * t * qx + t * t * x2, (1 - t) ** 2 * y0 + 2 * (1 - t) * t * qy + t * t * y2];
  });
}

const area = (b: Box) => b[2] * b[3];

/** The element under (x, y): nodes, then edge labels and lines, then the innermost group, then the diagram. */
export function hitTest(report: StyleReport, x: number, y: number, tol: number): string | null {
  const g = report.geometry;
  const smallest = (prefix: string) =>
    Object.entries(g)
      .filter(([k, v]) => k.startsWith(prefix) && v.box && inBox(v.box, x, y))
      .sort((a, b) => area(a[1].box!) - area(b[1].box!))[0]?.[0];
  const node = smallest("node:");
  if (node) return node;
  let best: [string, number] | null = null;
  for (const [k, v] of Object.entries(g)) {
    if (!k.startsWith("edge:")) continue;
    if (v.label && inBox(v.label, x, y)) return k;
    const pts = edgePoints(v);
    for (let i = 1; i < pts.length; i++) {
      const d = segDist(x, y, pts[i - 1], pts[i]);
      if (d <= tol && (!best || d < best[1])) best = [k, d];
    }
  }
  if (best) return best[0];
  return smallest("group:") ?? (g.diagram ? "diagram" : null);
}

export function Overlay({ report, hover, selected, scale }: { report: StyleReport; hover: string | null; selected: string | null; scale: number }) {
  const [w, h] = report.size;
  const shape = (key: string, cls: string) => {
    const g = report.geometry[key];
    if (!g) return null;
    if (g.box) {
      const [x, y, bw, bh] = g.box;
      return <rect key={cls} x={x - 3} y={y - 3} width={bw + 6} height={bh + 6} rx={6} className={cls} />;
    }
    const pts = edgePoints(g)
      .map((p) => p.join(","))
      .join(" ");
    return (
      <g key={cls}>
        <polyline points={pts} className={`${cls.replace(/fill-\S+/g, "")} fill-none`} />
        {g.label && <rect x={g.label[0] - 2} y={g.label[1] - 2} width={g.label[2] + 4} height={g.label[3] + 4} rx={6} className={cls} />}
      </g>
    );
  };
  const c = hover ? chip(report, hover, scale) : null;
  const px = 1 / scale; // one screen pixel in scene units: the chip keeps its size at any zoom
  return (
    <svg className="pointer-events-none absolute inset-0 overflow-visible" width={w} height={h} viewBox={`0 0 ${w} ${h}`}>
      {selected && shape(selected, "fill-blue-500/10 stroke-blue-600 [stroke-width:3]")}
      {hover && hover !== selected && shape(hover, "fill-sky-400/25 stroke-sky-500 [stroke-width:2]")}
      {c && (
        <g>
          <rect x={c.x} y={c.y} width={(c.text.length * 7.2 + 16) * px} height={c.h} rx={4 * px} className="fill-slate-900/90" />
          <text x={c.x + 8 * px} y={c.y + c.h / 2} dominantBaseline="central" fontSize={12 * px} className="fill-white font-mono">
            {c.text}
          </text>
        </g>
      )}
    </svg>
  );
}

// panel ------------------------------------------------------------------------------------------
const HEX = /#[0-9a-fA-F]{6}\b/g;

function Value({ v }: { v: string }) {
  const parts: React.ReactNode[] = [];
  let last = 0;
  for (const m of v.matchAll(HEX)) {
    parts.push(v.slice(last, m.index));
    parts.push(
      <span key={m.index} className="inline-flex items-center gap-1">
        <span className="inline-block size-3 rounded-sm ring-1 ring-black/20" style={{ background: m[0] }} />
        {m[0]}
      </span>,
    );
    last = m.index! + m[0].length;
  }
  parts.push(v.slice(last));
  return <>{parts}</>;
}

function fmt(v: unknown): string {
  if (typeof v === "number") return String(Math.round(v * 1000) / 1000);
  if (Array.isArray(v)) {
    if (v.length === 5 && typeof v[3] === "string") return `${v[0]} ${v[1]} ${v[2]} ${v[3]} / ${v[4]}`;
    return v.length ? v.map(fmt).join(" ") : "none";
  }
  return String(v);
}

const short = (origin: string) => (origin === "inline" ? "inline" : origin.split("/").pop()!);

/** Declarations grouped by rule, winning rule first (same order as `check --styles`). */
function rules(decls: CssDecl[]): [CssDecl, CssDecl[]][] {
  const groups = new Map<string, CssDecl[]>();
  for (const d of [...decls].reverse()) {
    const k = `${d.origin}|${d.rule_line}|${d.selector}|${d.important}`;
    groups.set(k, [...(groups.get(k) ?? []), d]);
  }
  return [...groups.values()].map((ds) => [ds[0], ds.reverse()]);
}

function Rules({ t, labels }: { t: CssTrace; labels: Record<string, string> }) {
  const bySrc = new Map<string, typeof t.inherited>();
  for (const i of t.inherited) bySrc.set(i.from ?? "?", [...(bySrc.get(i.from ?? "?") ?? []), i]);
  return (
    <div className="space-y-2">
      {rules(t.decls).map(([head, ds]) => (
        <div key={`${head.origin}${head.rule_line}${head.selector}${head.important}`} className="rounded-md border border-slate-200 dark:border-slate-800">
          <div className="flex items-baseline justify-between gap-2 border-b border-slate-100 px-2 py-1 dark:border-slate-800">
            <span className="font-mono text-xs text-cyan-700 dark:text-cyan-400">{head.selector ?? "inline css"}</span>
            <span className="shrink-0 font-mono text-[10px] text-slate-400" title={head.origin + (head.rule_line ? `:${head.rule_line}` : "")}>
              {short(head.origin)}
              {head.rule_line ? `:${head.rule_line}` : ""}
              {head.specificity && ` (${head.specificity.join(",")})`}
            </span>
          </div>
          <ul className="px-2 py-1 font-mono text-xs leading-5">
            {ds.map((d, i) => (
              <li
                key={i}
                className={d.status === "overridden" ? "text-slate-400 line-through" : d.status === "applied" ? "" : "text-red-600 dark:text-red-400"}
                title={d.message ?? (d.status === "overridden" ? "overridden by a rule above" : undefined)}
              >
                <span className={d.status === "applied" ? "text-fuchsia-700 dark:text-fuchsia-400" : ""}>{d.property}</span>:{" "}
                <Value v={d.value} />
                {d.resolved !== d.value && (
                  <span className="text-slate-400">
                    {" → "}
                    <Value v={d.resolved} />
                  </span>
                )}
                {d.important && <span className="text-amber-600"> !important</span>}
                {(d.status === "invalid" || d.status === "unknown") && <span className="ml-1 not-italic">⚠ {d.message}</span>}
              </li>
            ))}
          </ul>
        </div>
      ))}
      {[...bySrc.entries()].map(([src, items]) => (
        <div key={src} className="px-1 text-xs">
          <p className="text-slate-500">
            inherited from <span className="font-mono text-cyan-700 dark:text-cyan-400">{labels[src] ?? src}</span>
          </p>
          <ul className="mt-0.5 pl-3 font-mono leading-5">
            {items.map((i) => (
              <li key={i.property}>
                <span className="text-fuchsia-700 dark:text-fuchsia-400">{i.property}</span>: <Value v={fmt(i.value)} />
              </li>
            ))}
          </ul>
        </div>
      ))}
    </div>
  );
}

function Computed({ values }: { values: Record<string, unknown> }) {
  const entries = Object.entries(values).filter(([k]) => !k.startsWith("--"));
  if (!entries.length) return <p className="text-xs text-slate-500">No computed values.</p>;
  return (
    <table className="w-full font-mono text-xs leading-5">
      <tbody>
        {entries.map(([k, v]) => (
          <tr key={k}>
            <td className="w-1/2 pr-2 text-fuchsia-700 dark:text-fuchsia-400">{k}</td>
            <td>
              <Value v={fmt(v)} />
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function Declaration({ el, specPath, onShow }: { el: CssElement; specPath: string | undefined; onShow: (line: number) => void }) {
  const d = el.declaration;
  if (!d) return <p className="text-xs text-slate-500">Declaration not found in {specPath ?? "the spec"}</p>;
  return (
    <div className="rounded-md border border-slate-200 dark:border-slate-800">
      <div className="flex items-center justify-between gap-2 border-b border-slate-100 px-2 py-1 dark:border-slate-800">
        <span className="font-mono text-[10px] text-slate-400">
          {d.file}:{d.line}
        </span>
        <button className="text-xs text-blue-600 hover:underline" onClick={() => onShow(d.line)} title="Open the code panel on this line">
          Show in code
        </button>
      </div>
      <pre className="overflow-x-auto px-2 py-1 font-mono text-xs leading-5">{d.text}</pre>
    </div>
  );
}

function H({ children }: { children: React.ReactNode }) {
  return <h3 className="mt-4 mb-1.5 text-[11px] font-semibold tracking-wider text-slate-500 uppercase">{children}</h3>;
}

type PanelProps = {
  report: StyleReport | null;
  specPath: string | undefined; // named when an element's declaration is not found
  onShow: (line: number) => void; // open the code panel on this spec line
  error: string | null;
  selected: string | null;
  onSelect: (key: string | null) => void;
  onHover: (key: string | null) => void;
  onClose: () => void;
};

export function InspectorPanel({ report, specPath, onShow, error, selected, onSelect, onHover, onClose }: PanelProps) {
  const el = report?.elements.find((e) => e.key === selected);
  const labels = Object.fromEntries((report?.elements ?? []).map((e) => [e.key, elementLabel(e)]));
  return (
    <aside className="flex w-96 shrink-0 flex-col border-l border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-950">
      <div className="flex h-10 shrink-0 items-center gap-2 border-b border-slate-200 px-3 dark:border-slate-800">
        <span className="text-sm font-medium">Styles</span>
        {el && (
          <button className="text-xs text-blue-600 hover:underline" onClick={() => onSelect(null)}>
            all elements
          </button>
        )}
        <button className="ml-auto text-slate-400 hover:text-slate-700 dark:hover:text-slate-200" onClick={onClose} title="Close inspector (i)">
          ✕
        </button>
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto p-3">
        {error && <p className="rounded-md bg-red-50 p-2 text-xs text-red-800 dark:bg-red-950 dark:text-red-300">{error}</p>}
        {report && !report.styled && (
          <p className="mb-3 text-xs text-slate-500">
            This diagram uses no stylesheet and no inline <code>css</code>. Add <code>stylesheets:</code> or <code>class:</code> to style it.
          </p>
        )}
        {report && !el && (
          <>
            <p className="mb-2 text-xs text-slate-500">Click an element in the diagram, or pick one:</p>
            <ul className="space-y-0.5">
              {report.elements.map((e) => {
                const n = e.trace[""]?.decls.length ?? 0;
                const depth = depthOf(e, report.elements);
                return (
                  <li key={e.key}>
                    <button
                      className="flex w-full items-center gap-2 rounded px-1.5 py-0.5 text-left font-mono text-xs hover:bg-slate-100 dark:hover:bg-slate-900"
                      style={{ paddingLeft: 6 + depth * 12 }}
                      onClick={() => onSelect(e.key)}
                      onMouseEnter={() => onHover(e.key)}
                      onMouseLeave={() => onHover(null)}
                    >
                      <span className={report.styled && !Object.keys(e.trace).length ? "text-slate-400" : ""}>{labels[e.key]}</span>
                      {n > 0 && <span className="ml-auto text-[10px] text-slate-400">{n}</span>}
                    </button>
                  </li>
                );
              })}
            </ul>
            {report.styled && <H>Cascade</H>}
            <ol className="space-y-0.5 font-mono text-xs">
              {report.sheets.map((s, i) => (
                <li key={i} title={s.origin}>
                  {i + 1}. {short(s.origin)} <span className="text-slate-400">{s.theme ? "theme · " : ""}{s.rules} rules</span>
                </li>
              ))}
            </ol>
            {report.unused.length > 0 && (
              <>
                <H>Unused selectors</H>
                <ul className="font-mono text-xs text-slate-500">
                  {report.unused.map((u, i) => (
                    <li key={i}>
                      {u.selector} <span className="text-slate-400">{short(u.origin)}:{u.line}</span>
                    </li>
                  ))}
                </ul>
              </>
            )}
          </>
        )}
        {el && (
          <>
            <p className="font-mono text-sm font-semibold break-all">{labels[el.key]}</p>
            {el.attrs.label && <p className="text-xs text-slate-500">“{el.attrs.label}”</p>}
            <div className="mt-2 flex flex-wrap gap-1">
              {[el.type, ...el.kinds.filter((k) => k !== el.type)].map((t) => (
                <span key={t} className="rounded bg-slate-100 px-1.5 font-mono text-[11px] dark:bg-slate-800">
                  {t}
                </span>
              ))}
              {el.classes.map((c) => (
                <span key={c} className="rounded bg-blue-50 px-1.5 font-mono text-[11px] text-blue-800 dark:bg-blue-950 dark:text-blue-300">
                  .{c}
                </span>
              ))}
              {Object.entries(el.attrs)
                .filter(([k]) => k !== "label")
                .map(([k, v]) => (
                  <span key={k} className="rounded bg-slate-50 px-1.5 font-mono text-[11px] text-slate-500 dark:bg-slate-900">
                    [{k}={v}]
                  </span>
                ))}
            </div>
            <H>Declaration</H>
            <Declaration el={el} specPath={specPath} onShow={onShow} />
            <H>Computed</H>
            <Computed values={el.styles[""] ?? {}} />
            <H>Rules</H>
            {el.trace[""] ? <Rules t={el.trace[""]} labels={labels} /> : <p className="text-xs text-slate-500">No rule matches this element.</p>}
            {(["title", "body", "label"] as const).map((pe) =>
              el.trace[pe]?.decls.length ? (
                <div key={pe}>
                  <H>::{pe}</H>
                  <Computed values={el.styles[pe] ?? {}} />
                  <div className="mt-2">
                    <Rules t={el.trace[pe]} labels={labels} />
                  </div>
                </div>
              ) : null,
            )}
          </>
        )}
        {report && report.warnings.length > 0 && (
          <>
            <H>Warnings</H>
            <ul className="space-y-1 text-xs text-amber-700 dark:text-amber-300">
              {report.warnings.map((w, i) => (
                <li key={i} className="font-mono break-all">
                  {w}
                </li>
              ))}
            </ul>
          </>
        )}
      </div>
    </aside>
  );
}

function depthOf(e: CssElement, all: CssElement[]): number {
  let d = 0;
  let p = e.parent;
  while (p) {
    d++;
    p = all.find((x) => x.key === p)?.parent ?? null;
  }
  return d;
}
