import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api, ApiError, type DiagramInfo, type DiagramRef, type SpecFile, type StyleReport } from "./api";
import { href, typingIn, useKey, usePanZoom } from "./hooks";
import CodePanel from "./CodePanel";
import CanvasBar from "./canvas/CanvasBar";
import InlineEdit from "./canvas/InlineEdit";
import ShortcutSheet from "./canvas/ShortcutSheet";
import Toolbar from "./canvas/Toolbar";
import SvgHost from "./canvas/svgHost";
import { escapeStep, matchKey, selectionFrame } from "./canvas/interaction";
import { readPaletteOpen, writePaletteOpen } from "./canvas/paletteState";
import PalettePanel, { PALETTE_MIME } from "./canvas/PalettePanel";
import type { PaletteItem } from "./canvas/palette";
import { useCanvas } from "./canvas/useCanvas";
import { hitTest, InspectorPanel, Overlay } from "./Inspector";

const INSPECT_KEY = "spinagram.inspect";

const CURSORS = { grab: "cursor-grab", grabbing: "cursor-grabbing", crosshair: "cursor-crosshair", copy: "cursor-copy" } as const;

function stored(key: string): boolean {
  try {
    return localStorage.getItem(key) === "1";
  } catch {
    return false;
  }
}

function store(key: string, on: boolean): void {
  try {
    localStorage.setItem(key, on ? "1" : "0");
  } catch {
    /* storage unavailable: the toggle still works for this page */
  }
}

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

/** The eight handles of a selection outline (they show what is selected; resizing is done in the YAML). */
function Handles() {
  const at = ["-top-1 -left-1", "-top-1 left-1/2 -ml-1", "-top-1 -right-1", "top-1/2 -mt-1 -left-1", "top-1/2 -mt-1 -right-1", "-bottom-1 -left-1", "-bottom-1 left-1/2 -ml-1", "-bottom-1 -right-1"];
  return (
    <>
      {at.map((c) => (
        <span key={c} className={`absolute h-2 w-2 rounded-[1px] border border-blue-600 bg-white ${c}`} />
      ))}
    </>
  );
}

export default function DiagramView({ diagramKey, diagram, file, themeError, layout, rev }: Props) {
  const [svg, setSvg] = useState<string | null>(null);
  const [error, setError] = useState<{ message: string; file?: string } | null>(null);
  const [info, setInfo] = useState<DiagramInfo | null>(null);
  const [loading, setLoading] = useState(true);
  const size = useMemo(() => (svg ? svgSize(svg) : null), [svg]);
  const [canvasOn, setCanvasOn] = useState(false);
  const [tick, setTick] = useState(0); // bumped after a canvas edit: render and scene are read again
  const panGate = useRef<(e: PointerEvent) => boolean>(() => true);
  const [space, setSpace] = useState(false); // Space held: any tool pans
  const { ref, view, fit, actual, zoomBy } = usePanZoom(size, (e) => panGate.current(e));
  const fitted = useRef(false);
  const [inspect, setInspect] = useState(() => stored(INSPECT_KEY));
  const [code, setCode] = useState(false); // the code panel starts collapsed: the diagram gets the room
  const [codeMounted, setCodeMounted] = useState(false); // once opened it stays mounted, so collapsing keeps edits
  const [codeDirty, setCodeDirty] = useState(false);
  const [jump, setJump] = useState<{ line: number; nonce: number } | null>(null);
  const [report, setReport] = useState<StyleReport | null>(null);
  const [reportError, setReportError] = useState<string | null>(null);
  const [hover, setHover] = useState<string | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const press = useRef<{ x: number; y: number } | null>(null);
  const paletteFocus = useRef<(() => void) | null>(null);
  const [paletteOpen, setPaletteOpenState] = useState(readPaletteOpen); // starts collapsed, remembered per browser
  const setPaletteOpen = useCallback((open: boolean) => {
    setPaletteOpenState(open);
    writePaletteOpen(open);
  }, []);
  const openPalette = useCallback(() => {
    setPaletteOpen(true);
    setTimeout(() => paletteFocus.current?.(), 50);
  }, [setPaletteOpen]);
  const reloadDiagram = useCallback(() => setTick((t) => t + 1), []);
  const canvas = useCanvas({ diagramKey, layout, enabled: canvasOn, rev, tick, reload: reloadDiagram });

  const toggleInspect = useCallback(() => {
    setInspect((on) => {
      store(INSPECT_KEY, !on);
      return !on;
    });
    setHover(null);
  }, []);
  const toggleCode = useCallback(() => {
    setCodeMounted(true);
    setCode((on) => !on);
  }, []);
  const showLine = useCallback((line: number) => {
    setCodeMounted(true);
    setCode(true);
    setJump({ line, nonce: Date.now() });
  }, []);

  // the styles report follows the diagram: refetched on every live reload, selection kept by key; the code
  // panel uses its geometry too, to find the node under a click
  useEffect(() => {
    if (!inspect && !code) return;
    const ctl = new AbortController();
    api
      .styles(diagramKey, layout, ctl.signal)
      .then((r) => {
        setReport(r);
        setReportError(null);
      })
      .catch((e: unknown) => !ctl.signal.aborted && setReportError(e instanceof Error ? e.message : String(e)));
    return () => ctl.abort();
  }, [inspect, code, diagramKey, layout, rev]);

  const sceneAt = (e: { clientX: number; clientY: number }) => {
    const r = ref.current!.getBoundingClientRect();
    return { x: (e.clientX - r.left - view.x) / view.scale, y: (e.clientY - r.top - view.y) / view.scale };
  };
  // with the canvas on, a press on an element drags it and a press on empty canvas rubber-bands; Alt+drag pans
  const panning = space || canvas.tool === "hand";
  panGate.current = (e) => !canvas.active || e.altKey || panning;
  const onMove = (e: React.PointerEvent) => {
    if (canvas.dragging) {
      const p = sceneAt(e);
      canvas.move(p.x, p.y);
      return;
    }
    if (canvas.active && !e.buttons && canvas.tool === "select") {
      const p = sceneAt(e);
      canvas.hover(p.x, p.y);
    }
    if (!inspect || !report || e.buttons) return;
    const p = sceneAt(e);
    setHover(hitTest(report, p.x, p.y, 6 / view.scale));
  };
  const onDown = (e: React.PointerEvent) => {
    press.current = { x: e.clientX, y: e.clientY };
    if (canvas.active && e.button === 0 && !e.altKey && !panning) {
      const p = sceneAt(e);
      if (canvas.tool !== "select") {
        if (canvas.beginTool(p.x, p.y, e.shiftKey)) ref.current?.setPointerCapture(e.pointerId);
      } else if (canvas.begin(p.x, p.y, e.shiftKey)) ref.current?.setPointerCapture(e.pointerId);
      else if (!canvas.hits(p.x, p.y)) {
        canvas.beginBand(p.x, p.y, e.shiftKey);
        ref.current?.setPointerCapture(e.pointerId);
      }
    }
  };
  const onUp = (e: React.PointerEvent) => {
    if (canvas.dragging) {
      press.current = null;
      canvas.end(e.shiftKey);
      return;
    }
    const p0 = press.current;
    press.current = null;
    if (!report || !p0 || Math.hypot(e.clientX - p0.x, e.clientY - p0.y) > 4) return; // a drag pans
    const p = sceneAt(e);
    const hit = hitTest(report, p.x, p.y, 6 / view.scale);
    if (inspect) setSelected(hit);
    else if (code && hit) {
      const line = report.elements.find((el) => el.key === hit)?.declaration?.line;
      if (line) setJump({ line, nonce: Date.now() });
    }
  };

  useEffect(() => {
    const ctl = new AbortController();
    setLoading(true);
    api
      .diagram(diagramKey, layout, ctl.signal)
      .then((r) => {
        setSvg(r.svg); // keep zoom/pan: only the first render of this view fits
        canvas.clearPreview(); // the server render is the authority again
        setInfo(r.info);
        setError(null);
      })
      .catch((e: unknown) => {
        if (ctl.signal.aborted) return;
        if (e instanceof ApiError) setError({ message: e.message, file: e.file });
        else setError({ message: String(e) });
      })
      .finally(() => {
        if (ctl.signal.aborted) return;
        setLoading(false);
        canvas.clearPreview(); // a failed render must not leave a drop ghost or preview behind
      });
    return () => ctl.abort();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [diagramKey, layout, rev, tick]);

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
  useKey("i", toggleInspect);
  useKey("e", toggleCode);
  useKey("c", () => {
    if (!canvas.active) setCanvasOn((on) => !on); // with the canvas active, c is the Connect tool (the keymap)
  });
  // every canvas key goes through the keymap table (canvas/interaction.ts), which also feeds the `?` sheet
  const [sheet, setSheet] = useState(false);
  const keys = useRef({ canvas, paletteOpen, sheet, openPalette, setPaletteOpen });
  keys.current = { canvas, paletteOpen, sheet, openPalette, setPaletteOpen };
  useEffect(() => {
    const on = (e: KeyboardEvent) => {
      const k = keys.current;
      if (!k.canvas.active || typingIn(e.target instanceof HTMLElement ? e.target : null)) return;
      const hit = matchKey(e);
      if (!hit) return;
      e.preventDefault();
      switch (hit.action) {
        case "delete":
          return k.canvas.remove();
        case "group-row":
          return k.canvas.group("row");
        case "undo":
          return k.canvas.undo();
        case "redo":
          return k.canvas.redo();
        case "palette":
          return k.openPalette();
        case "help":
          return setSheet((v) => !v);
        case "tool":
          return k.canvas.setTool(hit.tool);
        case "nudge":
          return k.canvas.nudge(hit.dx, hit.dy);
        case "escape": {
          const step = escapeStep({
            sheet: k.sheet,
            dragging: k.canvas.dragging,
            nudging: k.canvas.nudging,
            selected: k.canvas.selected.length,
            palette: k.paletteOpen,
            tool: k.canvas.tool !== "select",
          });
          if (step === "sheet") setSheet(false);
          else if (step === "drag") k.canvas.cancelDrag();
          else if (step === "nudge") k.canvas.cancelNudge();
          else if (step === "selection") {
            setSelected(null);
            k.canvas.clear();
          } else if (step === "tool") k.canvas.setTool("select");
          else if (step === "palette") k.setPaletteOpen(false);
        }
      }
    };
    const up = (e: KeyboardEvent) => {
      if (e.key.startsWith("Arrow")) keys.current.canvas.flushNudge();
    };
    window.addEventListener("keydown", on);
    window.addEventListener("keyup", up);
    return () => {
      window.removeEventListener("keydown", on);
      window.removeEventListener("keyup", up);
    };
  }, []);
  useEffect(() => {
    // Space held pans in any tool; it also stops the page and a focused button from reacting to the key
    const down = (e: KeyboardEvent) => {
      if (e.code !== "Space" || !keys.current.canvas.active || typingIn(e.target instanceof HTMLElement ? e.target : null)) return;
      e.preventDefault();
      setSpace(true);
    };
    const up = (e: KeyboardEvent) => e.code === "Space" && setSpace(false);
    const blur = () => setSpace(false);
    window.addEventListener("keydown", down);
    window.addEventListener("keyup", up);
    window.addEventListener("blur", blur);
    return () => {
      window.removeEventListener("keydown", down);
      window.removeEventListener("keyup", up);
      window.removeEventListener("blur", blur);
    };
  }, []);
  useEffect(() => {
    // outside the canvas Esc still clears the inspector selection
    const on = (e: KeyboardEvent) => {
      if (e.key === "Escape" && !keys.current.canvas.active && !typingIn(e.target instanceof HTMLElement ? e.target : null)) setSelected(null);
    };
    window.addEventListener("keydown", on);
    return () => window.removeEventListener("keydown", on);
  }, []);

  const frame = selectionFrame(canvas.selectedBoxes);
  const fileError = file?.error && !diagram;
  return (
    <div className="flex h-full">
    {canvas.active && paletteOpen && (
      <PalettePanel
        rev={rev}
        focusRef={paletteFocus}
        onClose={() => setPaletteOpen(false)}
        onAdd={(item) => {
          const r = ref.current?.getBoundingClientRect();
          const c = r ? sceneAt({ clientX: r.left + r.width / 2, clientY: r.top + r.height / 2 }) : { x: 400, y: 300 };
          canvas.add(item, c.x, c.y);
        }}
      />
    )}
    <div className="relative min-w-0 flex-1 overflow-hidden bg-slate-100 dark:bg-slate-900">
      <div
        ref={ref}
        className={`absolute inset-0 touch-none select-none ${
          canvas.active
            ? panning
              ? "cursor-grab"
              : canvas.tool === "select"
                ? CURSORS[canvas.cursor]
                : "cursor-crosshair"
            : inspect && hover
              ? "cursor-pointer"
              : "cursor-grab"
        }`}
        onPointerMove={onMove}
        onPointerDown={onDown}
        onPointerUp={onUp}
        onDragOver={(e) => {
          if (canvas.active && e.dataTransfer.types.includes(PALETTE_MIME)) e.preventDefault();
        }}
        onDrop={(e) => {
          const raw = e.dataTransfer.getData(PALETTE_MIME);
          if (!canvas.active || !raw) return;
          e.preventDefault();
          const p = sceneAt(e);
          canvas.add(JSON.parse(raw) as PaletteItem, p.x, p.y);
        }}
        onDoubleClick={(e) => {
          if (!canvas.active) return;
          const p = sceneAt(e);
          void canvas.beginEdit(p.x, p.y);
        }}
        onPointerLeave={() => setHover(null)}
      >
        {svg && (
          <div
            className={`absolute top-0 left-0 origin-top-left shadow-xl ring-1 ring-black/5 transition-opacity ${
              error ? "opacity-30 grayscale" : ""
            }`}
            style={{ transform: `translate(${view.x}px, ${view.y}px) scale(${view.scale})`, width: size?.w, height: size?.h }}
          >
            <SvgHost markup={canvas.preview ?? svg} />
            {canvas.selectedBoxes.map((b, i) => (
              <div
                key={`${b.id}-${i}`}
                className={`pointer-events-none absolute rounded-sm border-blue-500 bg-blue-500/10 ${canvas.selectedBoxes.length > 1 ? "border" : "border-2"}`}
                style={{ left: b.x, top: b.y, width: b.w, height: b.h }}
              >
                {canvas.selectedBoxes.length === 1 && <Handles />}
              </div>
            ))}
            {frame && frame.count > 1 && (
              <div
                className="pointer-events-none absolute border-2 border-dashed border-blue-600"
                style={{ left: frame.box.x - 4, top: frame.box.y - 4, width: frame.box.w + 8, height: frame.box.h + 8 }}
              >
                <Handles />
                <span className="absolute -top-3 -right-3 grid h-6 min-w-6 place-items-center rounded-full bg-blue-600 px-1 text-xs font-semibold text-white shadow">
                  {frame.count}
                </span>
              </div>
            )}
            {canvas.band && (
              <div
                className="pointer-events-none absolute border border-dashed border-blue-600 bg-blue-500/10"
                style={{
                  left: Math.min(canvas.band.x0, canvas.band.x1),
                  top: Math.min(canvas.band.y0, canvas.band.y1),
                  width: Math.abs(canvas.band.x1 - canvas.band.x0),
                  height: Math.abs(canvas.band.y1 - canvas.band.y0),
                }}
              />
            )}
            {canvas.drawing && (
              <div
                className="pointer-events-none absolute border-2 border-dashed border-blue-600 bg-blue-500/10"
                style={{
                  left: Math.min(canvas.drawing.x0, canvas.drawing.x1),
                  top: Math.min(canvas.drawing.y0, canvas.drawing.y1),
                  width: Math.abs(canvas.drawing.x1 - canvas.drawing.x0),
                  height: Math.abs(canvas.drawing.y1 - canvas.drawing.y0),
                }}
              />
            )}
            {canvas.connecting && (
              <>
                {canvas.connecting.target && (
                  <div
                    className="pointer-events-none absolute rounded-sm border-2 border-emerald-500 bg-emerald-500/10"
                    style={{ left: canvas.connecting.target.x, top: canvas.connecting.target.y, width: canvas.connecting.target.w, height: canvas.connecting.target.h }}
                  />
                )}
                <svg className="pointer-events-none absolute top-0 left-0 overflow-visible" width={size?.w} height={size?.h} aria-hidden>
                  <line
                    x1={canvas.connecting.x0}
                    y1={canvas.connecting.y0}
                    x2={canvas.connecting.x1}
                    y2={canvas.connecting.y1}
                    stroke={canvas.connecting.target ? "#10b981" : "#2563eb"}
                    strokeWidth={3}
                    strokeDasharray="8 6"
                    strokeLinecap="round"
                  />
                  <circle cx={canvas.connecting.x1} cy={canvas.connecting.y1} r={5} fill={canvas.connecting.target ? "#10b981" : "#2563eb"} />
                </svg>
              </>
            )}
            {canvas.dropBox && (
              <div
                className="pointer-events-none absolute rounded-sm border-2 border-dashed border-emerald-500 bg-emerald-500/10"
                style={{ left: canvas.dropBox.x, top: canvas.dropBox.y, width: canvas.dropBox.w, height: canvas.dropBox.h }}
              />
            )}
            {canvas.ghost && (
              <div
                data-testid="drop-ghost"
                className="pointer-events-none absolute grid place-items-center rounded-sm border-2 border-dashed border-emerald-500 bg-white/70 text-[13px] font-medium text-slate-600"
                style={{ left: canvas.ghost.x, top: canvas.ghost.y, width: canvas.ghost.w, height: canvas.ghost.h }}
              >
                {canvas.ghost.label}
              </div>
            )}
            {canvas.editing && <InlineEdit key={canvas.editing.id} editing={canvas.editing} onCommit={canvas.commitEdit} onCancel={canvas.cancelEdit} />}
            {inspect && report && <Overlay report={report} hover={hover} selected={selected} scale={view.scale} />}
          </div>
        )}
      </div>

      <Toolbar
        canvas={canvas}
        paletteOpen={paletteOpen}
        sheetOpen={sheet}
        onPalette={() => (paletteOpen ? setPaletteOpen(false) : openPalette())}
        onHelp={() => setSheet((v) => !v)}
      />
      <CanvasBar canvas={canvas} />
      {canvas.active && sheet && <ShortcutSheet onClose={() => setSheet(false)} />}
      {canvas.toast && (
        <div
          key={canvas.toast.nonce}
          role="alert"
          className="pointer-events-none absolute z-30 max-w-xs rounded-md bg-red-600 px-3 py-1.5 text-xs font-medium text-white shadow-lg"
          style={{ left: view.x + canvas.toast.x * view.scale + 12, top: view.y + canvas.toast.y * view.scale + 16 }}
        >
          {canvas.toast.message}
        </div>
      )}

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
        {canvasOn && canvas.editable === false && (
          <span className="rounded-md bg-amber-100 px-2 py-1 text-amber-900 shadow dark:bg-amber-950 dark:text-amber-200">
            Canvas editing needs a hand-placed YAML spec
          </span>
        )}
        {canvas.notice && (
          <span className="rounded-md bg-red-100 px-2 py-1 text-red-900 shadow dark:bg-red-950 dark:text-red-200" role="alert">
            {canvas.notice}
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
        <button
          className={`border-l border-slate-200 px-3 py-1 dark:border-slate-700 ${
            canvasOn ? "bg-blue-600 text-white hover:bg-blue-700" : "hover:bg-slate-100 dark:hover:bg-slate-700"
          }`}
          onClick={() => setCanvasOn((on) => !on)}
          title="Canvas (c): click to select (Shift adds, drag on empty canvas draws a selection box, Alt+drag pans), drag to move (drop into a zone or row to put it there), Ctrl/Cmd+G groups as a row, double-click renames, Delete removes (hand-placed YAML specs)"
          aria-pressed={canvasOn}
        >
          Canvas
        </button>
        <button
          className={`border-l border-slate-200 px-3 py-1 dark:border-slate-700 ${
            code ? "bg-blue-600 text-white hover:bg-blue-700" : "hover:bg-slate-100 dark:hover:bg-slate-700"
          }`}
          onClick={toggleCode}
          title="Code (e): the Python and CSS of this diagram; click a box to find its line"
          aria-pressed={code}
        >
          Code
        </button>
        <button
          className={`border-l border-slate-200 px-3 py-1 dark:border-slate-700 ${
            inspect ? "bg-blue-600 text-white hover:bg-blue-700" : "hover:bg-slate-100 dark:hover:bg-slate-700"
          }`}
          onClick={toggleInspect}
          title="Inspect styles (i): click an element to see its CSS"
          aria-pressed={inspect}
        >
          Inspect
        </button>
      </div>
    </div>
    {codeMounted && (
      <div className={code ? "flex w-[44%] min-w-[420px] shrink-0" : "hidden"}>
        <CodePanel
          diagramKey={diagramKey}
          rev={rev}
          jump={jump}
          onCollapse={toggleCode}
          onDirty={setCodeDirty}
          select={canvas.active ? canvas.selection : null}
          srcmapOf={canvas.srcmap}
        />
      </div>
    )}
    {!code && (
      <button
        onClick={toggleCode}
        title="Show the code (e)"
        aria-label="Show the code"
        className="flex w-8 shrink-0 flex-col items-center gap-2 border-l border-slate-200 bg-white py-3 text-xs text-slate-500 hover:bg-slate-50 hover:text-slate-900 dark:border-slate-800 dark:bg-slate-950 dark:hover:bg-slate-900 dark:hover:text-slate-100"
      >
        <span aria-hidden>«</span>
        <span className="[writing-mode:vertical-rl]">Code</span>
        {codeDirty && <span className="size-1.5 rounded-full bg-amber-500" aria-label="unsaved changes" />}
      </button>
    )}
    {inspect && (
      <InspectorPanel
        report={report}
        specPath={file?.path}
        onShow={showLine}
        error={reportError}
        selected={selected}
        onSelect={setSelected}
        onHover={setHover}
        onClose={toggleInspect}
      />
    )}
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
