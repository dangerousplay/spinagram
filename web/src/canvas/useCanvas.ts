// Canvas mode of the diagram view: select, drag with live edges, Delete. The Rust core runs in a Web Worker
// (spinagram-wasm): `reroute` + `renderSvg` once per animation frame while a node is dragged, `applyOps` on
// release, then the file is saved and the server render replaces the preview.
import { useCallback, useEffect, useRef, useState } from "react";
import { api, ApiError } from "../api";
import { CanvasClient } from "./client";
import { dragMoves, dragTo, startDrag, type Drag } from "./drag";
import { deleteOps, dropTarget, groupOps, planDrop, planMultiDrop, renameOps, setContainerOps, ungroupOps, zoneStyleOps, type Item, type Op } from "./ops";
import { boxOf, containerAt, containerBox, hitTest, hitZone, rubberBand, zoneBox, zoneMoveShapes, type Box, type Kind, type SceneJson, type Sel } from "./scene";
import { History } from "./history";
import { dropOps, ghostOf, type Ghost, type PaletteItem } from "./palette";
import { cursorFor, EMPTY_BURST, nudgeMoves, nudgeOps, pressNudge, TOAST_MS, type Burst, type Cursor } from "./interaction";
import { entryField, yamlRange, type SrcMap } from "./srcmap";
import { canvasUi, connectOps, editBoxOf, isPlaceTool, placeOps, toolAfterUse, type Point, type ToolId } from "./tools";

export const CHANGED_ON_DISK = "File changed on disk; edit not applied";

type Options = {
  diagramKey: string;
  layout: string | null;
  enabled: boolean; // the Canvas toggle
  rev: number; // live-reload counter of the diagram
  tick: number; // bumped after an edit: the scene is read again
  reload: () => void; // render the diagram again (after a save, or a refused one)
};

/** The last selected element (what the code panel highlights); `nonce` makes a repeated pick count. */
export type Selection = { id: string; kind: Kind; nonce: number };
/** Properties of a selected container, read from its YAML entry: `gap`, and `align` where the loader accepts it. */
export type ContainerProps = { id: string; gap: string; align: string | null };
/** The style of a lone selected zone, read from its YAML entry (`color`, `soft` when absent). */
export type ZoneProps = { id: string; style: string };
export type Band = { x0: number; y0: number; x1: number; y1: number };
/** The inline editor of a node's title or a zone's label. */
/** An error from an edit operation, shown for a moment at the place the pointer was. */
export type Toast = { message: string; x: number; y: number; nonce: number };
/** A rectangle being drawn with Box, Text or Zone, and an edge being drawn with Connect (with the node under the end). */
export type Drawing = { tool: "box" | "text" | "zone"; x0: number; y0: number; x1: number; y1: number };
export type Connecting = { from: string; x0: number; y0: number; x1: number; y1: number; target: Box | null };
export type Editing = { id: string; kind: "node" | "zone"; box: Box; text: string };

export function useCanvas({ diagramKey, layout, enabled, rev, tick, reload }: Options) {
  const [scene, setScene] = useState<SceneJson | null>(null);
  const [editable, setEditable] = useState<boolean | null>(null); // null until the scene arrived
  const [ready, setReady] = useState(false); // the worker holds the scene
  const [selected, setSelected] = useState<Sel[]>([]);
  const [nonce, setNonce] = useState(0);
  const [band, setBand] = useState<Band | null>(null);
  const [props, setProps] = useState<ContainerProps | null>(null);
  const [zoneProps, setZoneProps] = useState<ZoneProps | null>(null);
  const [drag, setDrag] = useState<Drag | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [ghost, setGhost] = useState<Ghost | null>(null); // the box of a just-dropped item, until its render arrives
  const [notice, setNotice] = useState<string | null>(null);
  const [editing, setEditing] = useState<Editing | null>(null);
  const [toast, setToast] = useState<Toast | null>(null);
  const [hovering, setHovering] = useState(false);
  const [tool, setToolState] = useState<ToolId>("select");
  const [drawing, setDrawing] = useState<Drawing | null>(null);
  const [connecting, setConnecting] = useState<Connecting | null>(null);
  const toolRef = useRef<ToolId>("select");
  toolRef.current = tool;
  const drawRef = useRef<(Drawing & { keep: boolean }) | null>(null);
  const connRef = useRef<{ from: string; x0: number; y0: number; keep: boolean } | null>(null);
  const pendingEdit = useRef<{ id: string; title: string; box: Box } | null>(null); // a placed Text, edited once it is in the scene
  const [nudging, setNudging] = useState(false);
  const pointer = useRef({ x: 0, y: 0 });
  const burst = useRef<Burst>(EMPTY_BURST);
  const settle = useRef<ReturnType<typeof setTimeout> | null>(null);
  const client = useRef<CanvasClient | null>(null);
  const dragRef = useRef<Drag | null>(null);
  const history = useRef(new History());
  const dragItems = useRef<Item[]>([]);
  const bandRef = useRef<{ x0: number; y0: number; shift: boolean; base: Sel[] } | null>(null);
  const selectedRef = useRef<Sel[]>([]);
  selectedRef.current = selected;
  const sceneRef = useRef<SceneJson | null>(null);
  const latest = useRef<Record<string, [number, number]> | null>(null);
  const busy = useRef(false);
  const frame = useRef<number | null>(null);
  const committing = useRef(false);
  sceneRef.current = scene;

  const { shown, active } = canvasUi(enabled, editable, ready);

  // the scene, whenever the canvas is on and the diagram renders again
  useEffect(() => {
    if (!enabled) return;
    const ctl = new AbortController();
    setReady(false);
    api
      .scene(diagramKey, layout, ctl.signal)
      .then(async (doc) => {
        setEditable(doc.editable);
        setScene(doc.scene as SceneJson);
        const pe = pendingEdit.current;
        const pb = pe ? editBoxOf(doc.scene as SceneJson, pe) : null;
        if (pe && pb) {
          pendingEdit.current = null;
          setEditing({ id: pe.id, kind: "node", box: pb, text: pe.title });
        }
        if (!doc.editable) return;
        client.current ??= new CanvasClient(new Worker(new URL("./worker.ts", import.meta.url), { type: "module" }));
        await client.current.call({ t: "load", scene: JSON.stringify(doc.scene), files: doc.files, fontBase: api.fontBase });
        if (!ctl.signal.aborted) setReady(true);
      })
      .catch((e: unknown) => {
        if (!ctl.signal.aborted) setNotice(e instanceof Error ? e.message : String(e));
      });
    return () => ctl.abort();
  }, [enabled, diagramKey, layout, rev, tick]);

  useEffect(() => {
    if (enabled) return;
    setSelected([]);
    setDrag(null);
    setPreview(null);
    drawRef.current = null;
    connRef.current = null;
    pendingEdit.current = null;
    setDrawing(null);
    setConnecting(null);
    setToolState("select");
  }, [enabled]);
  useEffect(() => () => {
    client.current?.dispose();
    client.current = null;
    if (frame.current !== null) cancelAnimationFrame(frame.current);
  }, []);
  useEffect(() => {
    setSelected([]);
    setPreview(null);
    setEditable(null);
    history.current.clear();
  }, [diagramKey]);
  useEffect(() => {
    if (!toast) return;
    const t = setTimeout(() => setToast(null), TOAST_MS);
    return () => clearTimeout(t);
  }, [toast]);
  useEffect(() => {
    if (!notice) return;
    const t = setTimeout(() => setNotice(null), 6000);
    return () => clearTimeout(t);
  }, [notice]);

  const pump = useCallback(() => {
    if (busy.current || !latest.current || !client.current) return;
    const moves = latest.current;
    latest.current = null;
    busy.current = true;
    client.current
      .call({ t: "drag", moves })
      .then((svg) => (dragRef.current || burst.current.presses > 0) && setPreview(svg))
      .catch(() => undefined)
      .finally(() => {
        busy.current = false;
        if (latest.current) schedule();
      });
    // eslint-disable-next-line @typescript-eslint/no-use-before-define
  }, []);
  const schedule = useCallback(() => {
    if (frame.current !== null) return;
    frame.current = requestAnimationFrame(() => {
      frame.current = null;
      pump();
    });
  }, [pump]);

  const showToast = useCallback((message: string) => {
    setToast({ message: message.replace(/^Error:\s*/, ""), x: pointer.current.x, y: pointer.current.y, nonce: Date.now() });
  }, []);

  const commit = useCallback(
    async (ops: Op[]) => {
      if (committing.current) return;
      committing.current = true;
      try {
        const src = (await api.source(diagramKey)).files[0];
        let patched: string;
        try {
          patched = await client.current!.call({ t: "ops", yaml: src.text, ops: JSON.stringify(ops) });
        } catch (e) {
          // the Rust core refused the batch: its reason shows next to the pointer, and nothing is saved
          setPreview(null);
          setGhost(null);
          showToast(e instanceof Error ? e.message : String(e));
          reload();
          return;
        }
        await api.save(src.path, patched, src.version);
        history.current.record({ path: src.path, before: src.text, after: patched });
        reload();
      } catch (e) {
        setPreview(null);
        setGhost(null);
        if (e instanceof ApiError && e.status === 409) {
          history.current.clear();
          setNotice(CHANGED_ON_DISK);
        } else setNotice(e instanceof Error ? e.message : String(e));
        reload();
      } finally {
        committing.current = false;
      }
    },
    [diagramKey, reload, showToast],
  );

  /** Undo or redo the last canvas edit of this session as a new save through the version-checked path. The file
   * must still be the text that edit produced (or left); anything else (a 409, or an edit made elsewhere) clears
   * the history and reloads (SEL-09). */
  const travel = useCallback(
    async (dir: "undo" | "redo") => {
      if (committing.current) return;
      const entry = dir === "undo" ? history.current.undo() : history.current.redo();
      if (!entry) return;
      committing.current = true;
      try {
        const src = (await api.source(diagramKey)).files[0];
        const expected = dir === "undo" ? entry.after : entry.before;
        if (src.path !== entry.path || src.text !== expected) {
          history.current.clear();
          setNotice(CHANGED_ON_DISK);
        } else {
          await api.save(src.path, dir === "undo" ? entry.before : entry.after, src.version);
        }
      } catch (e) {
        history.current.clear();
        setNotice(e instanceof ApiError && e.status === 409 ? CHANGED_ON_DISK : e instanceof Error ? e.message : String(e));
      } finally {
        committing.current = false;
        setPreview(null);
        reload();
      }
    },
    [diagramKey, reload],
  );
  const undo = useCallback(() => active && void travel("undo"), [active, travel]);
  const redo = useCallback(() => active && void travel("redo"), [active, travel]);

  const pick = useCallback((sel: Sel[]) => {
    setSelected(sel);
    setNonce(Date.now());
  }, []);

  /** What a press at a scene point grabs: a node, else a container (its box, between members), else a zone header. */
  const targetAt = useCallback((x: number, y: number): { box: Box; kind: Kind } | null => {
    const sc = sceneRef.current;
    if (!sc) return null;
    const nid = hitTest(sc, x, y);
    const nbox = nid ? boxOf(sc, nid) : null;
    if (nbox) return { box: nbox, kind: "node" };
    const cont = containerAt(sc, x, y);
    const cbox = cont ? containerBox(sc, cont.id) : null;
    if (cbox) return { box: cbox, kind: "container" };
    const zid = hitZone(sc, x, y);
    const zbox = zid ? zoneBox(sc, zid) : null;
    return zbox ? { box: zbox, kind: "zone" } : null;
  }, []);

  /** Whether a press at a scene point belongs to the canvas (a node, container or zone header). */
  const hits = useCallback((x: number, y: number) => targetAt(x, y) !== null, [targetAt]);

  const boxFor = useCallback((s: Sel): Box | null => {
    const sc = sceneRef.current;
    if (!sc) return null;
    return s.kind === "zone" ? zoneBox(sc, s.id) : s.kind === "container" ? containerBox(sc, s.id) : boxOf(sc, s.id);
  }, []);

  /** A press at a scene point. Shift toggles the element in the selection; otherwise the element is selected (a
   * selection it already belongs to is kept) and dragged. Returns whether a drag started. */
  const begin = useCallback(
    (x: number, y: number, shift = false): boolean => {
      pointer.current = { x, y };
      const t = targetAt(x, y);
      if (!t) {
        if (!shift) pick([]);
        return false;
      }
      const me: Sel = { id: t.box.id, kind: t.kind };
      const has = (l: Sel[]) => l.some((s) => s.id === me.id && s.kind === me.kind);
      const cur = selectedRef.current;
      if (shift) {
        pick(has(cur) ? cur.filter((s) => !(s.id === me.id && s.kind === me.kind)) : [...cur, me]);
        return false;
      }
      const sel = has(cur) ? cur : [me];
      pick(sel);
      if (t.kind === "container") return false; // a container is placed by its own keys: select only
      const items: Item[] = sel.flatMap((s) => {
        const b = boxFor(s);
        return b && s.kind !== "container" ? [{ box: b, kind: s.kind as "node" | "zone" }] : [];
      });
      const shapes = [...new Set(items.flatMap((i) => (i.kind === "zone" ? zoneMoveShapes(sceneRef.current!, i.box.id) : [i.box.id])))];
      dragItems.current = items;
      dragRef.current = startDrag(t.box, x, y, t.kind as "node" | "zone", shapes);
      setDrag(dragRef.current);
      return true;
    },
    [targetAt, pick, boxFor],
  );

  /** A press on empty canvas: starts a rubber band (SEL-01); with shift the selection is kept and extended. */
  const beginBand = useCallback((x: number, y: number, shift: boolean) => {
    bandRef.current = { x0: x, y0: y, shift, base: shift ? selectedRef.current : [] };
    setBand({ x0: x, y0: y, x1: x, y1: y });
  }, []);

  const abortTool = useCallback(() => {
    drawRef.current = null;
    connRef.current = null;
    setDrawing(null);
    setConnecting(null);
  }, []);

  /** Pick the tool the pointer works as. A drawing or edge in progress is dropped. */
  const setTool = useCallback(
    (t: ToolId) => {
      if (!active) return;
      abortTool();
      setToolState(t);
    },
    [active, abortTool],
  );

  /** A press with Box, Text, Zone or Connect at a scene point. Returns whether the press started something (so the
   * caller captures the pointer): a rectangle for the placing tools, an edge from the node pressed for Connect. */
  const beginTool = useCallback(
    (x: number, y: number, shift = false): boolean => {
      const t = toolRef.current;
      const sc = sceneRef.current;
      pointer.current = { x, y };
      if (!sc) return false;
      if (isPlaceTool(t)) {
        drawRef.current = { tool: t, x0: x, y0: y, x1: x, y1: y, keep: shift };
        setDrawing({ tool: t, x0: x, y0: y, x1: x, y1: y });
        return true;
      }
      if (t === "connect") {
        const from = hitTest(sc, x, y);
        const fb = from ? boxOf(sc, from) : null;
        if (!from || !fb) return false;
        const [cx, cy] = [fb.x + fb.w / 2, fb.y + fb.h / 2];
        connRef.current = { from, x0: cx, y0: cy, keep: shift };
        setConnecting({ from, x0: cx, y0: cy, x1: x, y1: y, target: null });
        return true;
      }
      return false;
    },
    [],
  );

  const move = useCallback(
    (x: number, y: number) => {
      pointer.current = { x, y };
      const dw = drawRef.current;
      if (dw) {
        drawRef.current = { ...dw, x1: x, y1: y };
        setDrawing({ tool: dw.tool, x0: dw.x0, y0: dw.y0, x1: x, y1: y });
        return;
      }
      const cn = connRef.current;
      if (cn) {
        const sc = sceneRef.current;
        const over = sc ? hitTest(sc, x, y) : null;
        const target = sc && over && over !== cn.from ? boxOf(sc, over) : null;
        setConnecting({ from: cn.from, x0: cn.x0, y0: cn.y0, x1: x, y1: y, target });
        return;
      }
      const b = bandRef.current;
      if (b && sceneRef.current) {
        setBand({ x0: b.x0, y0: b.y0, x1: x, y1: y });
        const ids = rubberBand(sceneRef.current, { x: b.x0, y: b.y0 }, { x, y });
        const base = b.base;
        pick([...base, ...ids.filter((id) => !base.some((s) => s.id === id && s.kind === "node")).map((id): Sel => ({ id, kind: "node" }))]);
        return;
      }
      if (!dragRef.current) return;
      dragRef.current = dragTo(dragRef.current, x, y);
      setDrag(dragRef.current);
      const moves = dragMoves(dragRef.current);
      if (moves) {
        latest.current = moves;
        schedule();
      }
    },
    [schedule, pick],
  );

  /** The release. A band ends. A click only selects; a drag commits its batch: Move (MoveZone for a zone) to the
   * snapped corner, Reparent when dropped into another zone, container insertions and removals (see `planDrop`). */
  const end = useCallback((shift = false) => {
    const dw = drawRef.current;
    const cn = connRef.current;
    const sc = sceneRef.current;
    if (dw || cn) {
      abortTool();
      if (!sc) return;
      const keep = shift || (dw ?? cn)!.keep;
      const t = toolRef.current;
      if (dw) {
        const place = placeOps(sc, dw.tool, { x: dw.x0, y: dw.y0 }, { x: dw.x1, y: dw.y1 } as Point);
        setToolState(toolAfterUse(t, keep));
        if (place.edit) pendingEdit.current = { id: place.id, title: "New text", box: place.box };
        void commit(place.ops);
      } else if (cn) {
        const ops = connectOps(sc, cn.from, pointer.current.x, pointer.current.y);
        if (!ops) return; // nothing added: the tool stays for another try
        setToolState(toolAfterUse(t, keep));
        void commit(ops);
      }
      return;
    }
    if (bandRef.current) {
      bandRef.current = null;
      setBand(null);
      return;
    }
    const d = dragRef.current;
    dragRef.current = null;
    setDrag(null);
    if (frame.current !== null) {
      cancelAnimationFrame(frame.current);
      frame.current = null;
    }
    latest.current = null;
    if (!d || !d.moved) return;
    const items = dragItems.current.length ? dragItems.current : [{ box: d.box, kind: d.kind }];
    const plan = items.length > 1 ? planMultiDrop(sceneRef.current!, items, d.dx, d.dy) : planDrop(sceneRef.current!, d.box, d.kind, d.dx, d.dy);
    if (!plan) {
      setPreview(null);
      return;
    }
    if ("error" in plan) {
      setPreview(null);
      showToast(plan.error);
      return;
    }
    const m = plan.ops.find((o) => (o.op === "move" || o.op === "move_zone") && o.id === d.box.id) as Extract<Op, { op: "move" | "move_zone" }> | undefined;
    // show the dropped (snapped) position at once; the server render replaces it after the save
    if (m) {
      const moves = Object.fromEntries(d.shapes.map((id) => [id, [m.x - d.box.x, m.y - d.box.y] as [number, number]]));
      void client.current!.call({ t: "drag", moves }).then(setPreview).catch(() => undefined);
    } else setPreview(null);
    void commit(plan.ops);
  }, [commit, showToast, abortTool]);

  /** Esc during a drag: drop it without any operation; the server render (the pre-drag scene) shows again. */
  const cancelDrag = useCallback(() => {
    abortTool();
    dragRef.current = null;
    bandRef.current = null;
    setDrag(null);
    setBand(null);
    if (frame.current !== null) {
      cancelAnimationFrame(frame.current);
      frame.current = null;
    }
    latest.current = null;
    setPreview(null);
  }, [abortTool]);

  /** Whether the pointer is over something the canvas grabs; sets the `grab` cursor. */
  const hover = useCallback(
    (x: number, y: number) => {
      pointer.current = { x, y };
      const over = targetAt(x, y) !== null;
      setHovering((h) => (h === over ? h : over));
    },
    [targetAt],
  );

  /** An arrow key press: the selection moves by the offset in the preview; the burst commits on key-up. */
  const nudge = useCallback((dx: number, dy: number) => {
    const sc = sceneRef.current;
    if (!active || !sc || !selectedRef.current.length || !client.current) return;
    if (settle.current !== null) {
      clearTimeout(settle.current);
      settle.current = null;
    }
    burst.current = pressNudge(burst.current, dx, dy);
    setNudging(true);
    const moves = nudgeMoves(sc, selectedRef.current, burst.current);
    if (moves) {
      latest.current = moves;
      schedule();
    }
  }, [active, schedule]);

  const commitBurst = useCallback(() => {
    settle.current = null;
    if (committing.current) {
      settle.current = setTimeout(commitBurst, 150); // a save is still running: wait for it
      return;
    }
    const b = burst.current;
    burst.current = EMPTY_BURST;
    setNudging(false);
    if (b.presses === 0) return;
    const sc = sceneRef.current;
    const plan = sc ? nudgeOps(sc, selectedRef.current, b) : null;
    latest.current = null;
    if (!plan) {
      setPreview(null);
      return;
    }
    if ("error" in plan) {
      setPreview(null);
      showToast(plan.error);
      return;
    }
    void commit(plan.ops);
  }, [commit, showToast]);

  /** Arrow key released: taps within a short moment join the same burst (holding a key never releases until the
   * end), then the burst is one batch: one save and one undo step. */
  const flushNudge = useCallback(() => {
    if (burst.current.presses === 0) return;
    if (settle.current !== null) clearTimeout(settle.current);
    settle.current = setTimeout(commitBurst, 350);
  }, [commitBurst]);

  const cancelNudge = useCallback(() => {
    if (settle.current !== null) {
      clearTimeout(settle.current);
      settle.current = null;
    }
    burst.current = EMPTY_BURST;
    setNudging(false);
    latest.current = null;
    setPreview(null);
  }, []);

  const remove = useCallback(() => {
    if (!active) return;
    const ids = selectedRef.current.filter((s) => s.kind !== "container").map((s) => s.id);
    if (!ids.length) return;
    pick([]);
    void commit(ids.flatMap(deleteOps));
  }, [active, commit, pick]);

  /** Group the selected nodes as a row or column (GRP-01). */
  const group = useCallback(
    (axis: "row" | "column") => {
      if (!active || !sceneRef.current) return;
      const ops = groupOps(sceneRef.current, selectedRef.current.filter((s) => s.kind === "node").map((s) => s.id), axis);
      if (!ops) return;
      pick([]);
      void commit(ops);
    },
    [active, commit, pick],
  );

  /** Ungroup the selected container (GRP-04). */
  const ungroup = useCallback(() => {
    const c = selectedRef.current.find((s) => s.kind === "container");
    const ops = c && sceneRef.current ? ungroupOps(sceneRef.current, c.id) : null;
    if (!active || !ops) return;
    pick([]);
    void commit(ops);
  }, [active, commit, pick]);

  /** Change the gap or align of the selected container (GRP-06). */
  const setContainer = useCallback(
    (p: { gap?: number; align?: string }) => {
      const c = selectedRef.current.find((s) => s.kind === "container");
      if (active && c) void commit(setContainerOps(c.id, p));
    },
    [active, commit],
  );

  /** Add a palette item with its centre at a scene point (PAL-03, PAL-04, PAL-05, ZON-01). */
  const add = useCallback(
    (item: PaletteItem, x: number, y: number) => {
      if (!active || !sceneRef.current) return;
      const ops = dropOps(sceneRef.current, item, x, y);
      setGhost(ghostOf(ops));
      void commit(ops);
    },
    [active, commit],
  );

  const clear = useCallback(() => {
    pick([]);
    setEditing(null);
  }, [pick]);

  /** Double-click: open the inline editor on the node's title or the zone's label (SEL-05, ZON-07). */
  const beginEdit = useCallback(
    async (x: number, y: number) => {
      if (!active) return;
      const t = targetAt(x, y);
      if (!t || t.kind === "container") return;
      pick([{ id: t.box.id, kind: t.kind }]);
      try {
        const src = (await api.source(diagramKey)).files[0];
        const map = JSON.parse(await client.current!.call({ t: "srcmap", yaml: src.text })) as SrcMap;
        const r = yamlRange(src.text, map, t.box.id);
        const text = (r && entryField(src.text.slice(r.from, r.to), t.kind === "zone" ? "label" : "title")) ?? "";
        setEditing({ id: t.box.id, kind: t.kind, box: t.box, text });
      } catch (e) {
        setNotice(e instanceof Error ? e.message : String(e));
      }
    },
    [active, targetAt, diagramKey, pick],
  );
  const cancelEdit = useCallback(() => setEditing(null), []);
  const commitEdit = useCallback(
    (text: string) => {
      const e = editing;
      setEditing(null);
      if (e && text !== e.text) void commit(renameOps(e.id, text));
    },
    [editing, commit],
  );

  const srcmap = useCallback(
    async (yaml: string): Promise<SrcMap> => JSON.parse(await client.current!.call({ t: "srcmap", yaml })) as SrcMap,
    [],
  );

  // the property bar of a lone selected container: its gap and align from the YAML entry
  const lone = selected.length === 1 && selected[0].kind === "container" ? selected[0].id : null;
  useEffect(() => {
    setProps(null);
    if (!active || !lone) return;
    let live = true;
    void (async () => {
      try {
        const src = (await api.source(diagramKey)).files[0];
        const r = yamlRange(src.text, await srcmap(src.text), lone);
        if (!r || !live) return;
        const entry = src.text.slice(r.from, r.to);
        setProps({ id: lone, gap: entryField(entry, "gap") ?? "20", align: entryField(entry, "zone") !== null ? (entryField(entry, "align") ?? "center") : null });
      } catch {
        /* the bar just stays hidden */
      }
    })();
    return () => {
      live = false;
    };
  }, [active, lone, diagramKey, srcmap, scene]);

  // the style picker of a lone selected zone: its `color` from the YAML entry
  const loneZone = selected.length === 1 && selected[0].kind === "zone" ? selected[0].id : null;
  useEffect(() => {
    setZoneProps(null);
    if (!active || !loneZone) return;
    let live = true;
    void (async () => {
      try {
        const src = (await api.source(diagramKey)).files[0];
        const r = yamlRange(src.text, await srcmap(src.text), loneZone);
        if (!r || !live) return;
        setZoneProps({ id: loneZone, style: entryField(src.text.slice(r.from, r.to), "color") ?? "soft" });
      } catch {
        /* the picker just stays hidden */
      }
    })();
    return () => {
      live = false;
    };
  }, [active, loneZone, diagramKey, srcmap, scene]);

  /** Give the selected zone another style (the zone picker of the canvas bar). */
  const setZoneStyle = useCallback(
    (style: string) => {
      const z = selectedRef.current.length === 1 && selectedRef.current[0].kind === "zone" ? selectedRef.current[0] : null;
      if (active && z) void commit(zoneStyleOps(z.id, style));
    },
    [active, commit],
  );

  // the boxes of the selection, following the pointer while the drag goes on
  const selectedBoxes: Box[] = [];
  if (active && scene) {
    for (const s of selected) {
      const b = boxFor(s);
      if (!b) continue;
      const moving = drag && drag.moved && dragItems.current.some((i) => i.box.id === s.id);
      selectedBoxes.push(moving ? { ...b, x: b.x + drag!.dx, y: b.y + drag!.dy } : b);
    }
  }

  // the zone the dragged item would be dropped into, highlighted while the pointer moves (ZON-06)
  let dropBox: Box | null = null;
  if (active && drag && drag.moved && scene && drag.kind) {
    const target = dropTarget(scene, drag.box, drag.kind, drag.dx, drag.dy);
    dropBox = target ? zoneBox(scene, target) : null;
  }

  const cursor: Cursor = cursorFor({ dragging: drag !== null && drag.moved, overDropTarget: dropBox !== null, overElement: hovering });

  const last = selected[selected.length - 1];
  const selection: Selection | null = last ? { ...last, nonce } : null;

  return {
    shown,
    active,
    editable,
    selection,
    selected,
    selectedBoxes,
    containerProps: props,
    zoneProps,
    setZoneStyle,
    band,
    dropBox,
    editing,
    dragging: drag !== null || band !== null || drawing !== null || connecting !== null,
    tool,
    drawing,
    connecting,
    setTool,
    beginTool,
    preview,
    ghost,
    clearPreview: useCallback(() => {
      setPreview(null);
      setGhost(null);
    }, []),
    notice,
    toast,
    cursor,
    nudging,
    hover,
    cancelDrag,
    nudge,
    flushNudge,
    cancelNudge,
    hits,
    begin,
    beginBand,
    beginEdit,
    cancelEdit,
    commitEdit,
    move,
    end,
    remove,
    add,
    undo,
    redo,
    group,
    ungroup,
    setContainer,
    clear,
    srcmap: active ? srcmap : null,
  };
}
