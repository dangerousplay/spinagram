import { useEffect, useMemo, useRef, useState } from "react";
import { api, ApiError, type DiagramInfo, type DiagramRef, type SpecFile } from "./api";
import { href, useKey, usePanZoom } from "./hooks";

type Props = {
  diagramKey: string;
  diagram: DiagramRef | undefined;
  file: SpecFile | undefined;
  themeError: string | null;
  layout: string | null;
  rev: number;
};

function svgSize(svg: string): { w: number; h: number } | null {
  const m = svg.match(/<svg[^>]*\swidth="([\d.]+)"[^>]*\sheight="([\d.]+)"/);
  return m ? { w: parseFloat(m[1]), h: parseFloat(m[2]) } : null;
}

export default function DiagramView({ diagramKey, diagram, file, themeError, layout, rev }: Props) {
  const [svg, setSvg] = useState<string | null>(null);
  const [error, setError] = useState<{ message: string; file?: string } | null>(null);
  const [info, setInfo] = useState<DiagramInfo | null>(null);
  const [loading, setLoading] = useState(true);
  const size = useMemo(() => (svg ? svgSize(svg) : null), [svg]);
  const { ref, view, fit, actual, zoomBy } = usePanZoom(size);
  const fitted = useRef(false);

  useEffect(() => {
    const ctl = new AbortController();
    setLoading(true);
    api
      .diagram(diagramKey, layout, ctl.signal)
      .then((r) => {
        setSvg(r.svg); // keep zoom/pan: only the first render of this view fits
        setInfo(r.info);
        setError(null);
      })
      .catch((e: unknown) => {
        if (ctl.signal.aborted) return;
        if (e instanceof ApiError) setError({ message: e.message, file: e.file });
        else setError({ message: String(e) });
      })
      .finally(() => !ctl.signal.aborted && setLoading(false));
    return () => ctl.abort();
  }, [diagramKey, layout, rev]);

  useEffect(() => {
    if (size && !fitted.current) {
      fitted.current = true;
      fit();
    }
  }, [size, fit]);

  useKey("f", fit);
  useKey("0", actual);
  useKey("+", () => zoomBy(1.25));
  useKey("-", () => zoomBy(0.8));

  const fileError = file?.error && !diagram;
  return (
    <div className="relative h-full overflow-hidden bg-slate-100 dark:bg-slate-900">
      <div ref={ref} className="absolute inset-0 cursor-grab touch-none select-none">
        {svg && (
          <div
            className={`absolute top-0 left-0 origin-top-left shadow-xl ring-1 ring-black/5 transition-opacity ${
              error ? "opacity-30 grayscale" : ""
            }`}
            style={{ transform: `translate(${view.x}px, ${view.y}px) scale(${view.scale})`, width: size?.w, height: size?.h }}
            dangerouslySetInnerHTML={{ __html: svg }}
          />
        )}
      </div>

      {(error || fileError || themeError) && (
        <div className="absolute inset-x-6 top-6 rounded-lg border border-red-300 bg-red-50 p-4 shadow-lg dark:border-red-800 dark:bg-red-950/90">
          <p className="text-sm font-semibold text-red-800 dark:text-red-300">
            {themeError ? "Theme failed to load" : `Cannot render ${error?.file ?? file?.path ?? diagramKey}`}
          </p>
          <pre className="mt-2 max-h-64 overflow-auto font-mono text-xs whitespace-pre-wrap text-red-900 dark:text-red-200">
            {themeError ?? error?.message ?? file?.error}
          </pre>
          {svg && <p className="mt-2 text-xs text-red-700 dark:text-red-400">Showing the last good render. Save a fix to refresh.</p>}
        </div>
      )}

      <div className="absolute bottom-4 left-4 flex items-center gap-2 text-xs">
        {diagram && (
          <span className="rounded-md bg-white/90 px-2 py-1 text-slate-600 shadow dark:bg-slate-800/90 dark:text-slate-300">
            <b className="font-mono">{diagram.id}</b> {diagram.title}
            {!diagram.auto && <span className="ml-2 text-slate-400">fixed layout</span>}
          </span>
        )}
        {info?.overflow && !error && (
          <span className="rounded-md bg-amber-100 px-2 py-1 text-amber-900 shadow dark:bg-amber-950 dark:text-amber-200">
            layout overflows the canvas by {info.overflow[0]} × {info.overflow[1]} px
          </span>
        )}
        {!error &&
          info?.missing_packs.map((p) => (
            <a
              key={p}
              href={href({ kind: "pack", name: p })}
              className="rounded-md bg-amber-100 px-2 py-1 text-amber-900 shadow hover:underline dark:bg-amber-950 dark:text-amber-200"
            >
              icon pack <b className="font-mono">{p}</b> not downloaded — fetch it
            </a>
          ))}
        {!error && info && info.warnings.length > 0 && (
          <span
            className="cursor-help rounded-md bg-white/90 px-2 py-1 text-amber-700 shadow dark:bg-slate-800/90 dark:text-amber-300"
            title={info.warnings.join("\n")}
          >
            {info.warnings.length} warning{info.warnings.length > 1 ? "s" : ""}
          </span>
        )}
        {loading && <span className="animate-pulse text-slate-500">rendering…</span>}
      </div>

      <div className="absolute right-4 bottom-4 flex items-center overflow-hidden rounded-md bg-white/90 text-xs shadow dark:bg-slate-800/90">
        <ToolButton onClick={() => zoomBy(0.8)} title="Zoom out (-)">−</ToolButton>
        <button className="w-14 py-1 tabular-nums hover:bg-slate-100 dark:hover:bg-slate-700" onClick={actual} title="Actual size (0)">
          {Math.round(view.scale * 100)}%
        </button>
        <ToolButton onClick={() => zoomBy(1.25)} title="Zoom in (+)">+</ToolButton>
        <button className="border-l border-slate-200 px-3 py-1 hover:bg-slate-100 dark:border-slate-700 dark:hover:bg-slate-700" onClick={fit} title="Fit (f)">
          Fit
        </button>
      </div>
    </div>
  );
}

function ToolButton({ onClick, title, children }: { onClick: () => void; title: string; children: React.ReactNode }) {
  return (
    <button className="w-8 py-1 text-base leading-none hover:bg-slate-100 dark:hover:bg-slate-700" onClick={onClick} title={title}>
      {children}
    </button>
  );
}
