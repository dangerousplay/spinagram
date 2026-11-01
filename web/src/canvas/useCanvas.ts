// Canvas mode of the diagram view: select, drag with live edges, Delete. The Rust core runs in a Web Worker
// (spinagram-wasm): `reroute` + `renderSvg` once per animation frame while a node is dragged, `applyOps` on
// release, then the file is saved and the server render replaces the preview.
import { useCallback, useEffect, useRef, useState } from "react";
import { api, ApiError } from "../api";
import { CanvasClient } from "./client";
import { dragMoves, dragTo, startDrag, type Drag } from "./drag";
import { deleteOps, dropTarget, groupOps, planDrop, planMultiDrop, renameOps, setContainerOps, ungroupOps, type Item, type Op } from "./ops";
import { boxOf, containerAt, containerBox, hitTest, hitZone, rubberBand, zoneBox, zoneMoveShapes, type Box, type Kind, type SceneJson, type Sel } from "./scene";
import { dropOps, type PaletteItem } from "./palette";
import { entryField, yamlRange, type SrcMap } from "./srcmap";

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
export type Band = { x0: number; y0: number; x1: number; y1: number };
/** The inline editor of a node's title or a zone's label. */
export type Editing = { id: string; kind: "node" | "zone"; box: Box; text: string };

export function useCanvas({ diagramKey, layout, enabled, rev, tick, reload }: Options) {
  const [scene, setScene] = useState<SceneJson | null>(null);
  const [editable, setEditable] = useState<boolean | null>(null); // null until the scene arrived
  const [ready, setReady] = useState(false); // the worker holds the scene
  const [selected, setSelected] = useState<Sel[]>([]);
  const [nonce, setNonce] = useState(0);
  const [band, setBand] = useState<Band | null>(null);
  const [props, setProps] = useState<ContainerProps | null>(null);
  const [drag, setDrag] = useState<Drag | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [editing, setEditing] = useState<Editing | null>(null);
  const client = useRef<CanvasClient | null>(null);
  const dragRef = useRef<Drag | null>(null);
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

  const active = enabled && editable === true && ready;

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
  }, [diagramKey]);
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
      .then((svg) => dragRef.current && setPreview(svg))
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

  const commit = useCallback(
    async (ops: Op[]) => {
      if (committing.current) return;
      committing.current = true;
      try {
        const src = (await api.source(diagramKey)).files[0];
        const patched = await client.current!.call({ t: "ops", yaml: src.text, ops: JSON.stringify(ops) });
        await api.save(src.path, patched, src.version);
        reload();
      } catch (e) {
        setPreview(null);
        if (e instanceof ApiError && e.status === 409) setNotice(CHANGED_ON_DISK);
        else setNotice(e instanceof Error ? e.message : String(e));
        reload();
      } finally {
        committing.current = false;
      }
    },
    [diagramKey, reload],
  );

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

  const move = useCallback(
    (x: number, y: number) => {
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
  const end = useCallback(() => {
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
      setNotice(plan.error);
      return;
    }
    const m = plan.ops.find((o) => (o.op === "move" || o.op === "move_zone") && o.id === d.box.id) as Extract<Op, { op: "move" | "move_zone" }> | undefined;
    // show the dropped (snapped) position at once; the server render replaces it after the save
    if (m) {
      const moves = Object.fromEntries(d.shapes.map((id) => [id, [m.x - d.box.x, m.y - d.box.y] as [number, number]]));
      void client.current!.call({ t: "drag", moves }).then(setPreview).catch(() => undefined);
    } else setPreview(null);
    void commit(plan.ops);
  }, [commit]);

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
      void commit(dropOps(sceneRef.current, item, x, y));
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

  const last = selected[selected.length - 1];
  const selection: Selection | null = last ? { ...last, nonce } : null;

  return {
    active,
    editable,
    selection,
    selected,
    selectedBoxes,
    containerProps: props,
    band,
    dropBox,
    editing,
    dragging: drag !== null || band !== null,
    preview,
    clearPreview: useCallback(() => setPreview(null), []),
    notice,
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
    group,
    ungroup,
    setContainer,
    clear,
    srcmap: active ? srcmap : null,
  };
}
