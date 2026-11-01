// Canvas mode of the diagram view: select, drag with live edges, Delete. The Rust core runs in a Web Worker
// (spinagram-wasm): `reroute` + `renderSvg` once per animation frame while a node is dragged, `applyOps` on
// release, then the file is saved and the server render replaces the preview.
import { useCallback, useEffect, useRef, useState } from "react";
import { api, ApiError } from "../api";
import { CanvasClient } from "./client";
import { dragMoves, dragTo, startDrag, type Drag } from "./drag";
import { deleteOps, dropTarget, planDrop, renameOps, type Op } from "./ops";
import { boxOf, hitTest, hitZone, zoneBox, zoneMoveShapes, type Box, type SceneJson } from "./scene";
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

export type Selection = { id: string; kind: "node" | "zone"; nonce: number };
/** The inline editor of a node's title or a zone's label. */
export type Editing = { id: string; kind: "node" | "zone"; box: Box; text: string };

export function useCanvas({ diagramKey, layout, enabled, rev, tick, reload }: Options) {
  const [scene, setScene] = useState<SceneJson | null>(null);
  const [editable, setEditable] = useState<boolean | null>(null); // null until the scene arrived
  const [ready, setReady] = useState(false); // the worker holds the scene
  const [selection, setSelection] = useState<Selection | null>(null);
  const [drag, setDrag] = useState<Drag | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [editing, setEditing] = useState<Editing | null>(null);
  const client = useRef<CanvasClient | null>(null);
  const dragRef = useRef<Drag | null>(null);
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
    setSelection(null);
    setDrag(null);
    setPreview(null);
  }, [enabled]);
  useEffect(() => () => {
    client.current?.dispose();
    client.current = null;
    if (frame.current !== null) cancelAnimationFrame(frame.current);
  }, []);
  useEffect(() => {
    setSelection(null);
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

  /** The node, else the zone header, under a scene point: the target a press grabs. */
  const targetAt = useCallback((x: number, y: number): { box: Box; kind: "node" | "zone" } | null => {
    const sc = sceneRef.current;
    if (!sc) return null;
    const nid = hitTest(sc, x, y);
    const nbox = nid ? boxOf(sc, nid) : null;
    if (nbox) return { box: nbox, kind: "node" };
    const zid = hitZone(sc, x, y);
    const zbox = zid ? zoneBox(sc, zid) : null;
    return zbox ? { box: zbox, kind: "zone" } : null;
  }, []);

  /** Whether a press at a scene point belongs to the canvas (a node or a zone header), used to decide pan or drag. */
  const hits = useCallback((x: number, y: number) => targetAt(x, y) !== null, [targetAt]);

  /** A press at a scene point: selects the node or zone under it and starts dragging it. Returns whether one was hit. */
  const begin = useCallback(
    (x: number, y: number): boolean => {
      const t = targetAt(x, y);
      if (!t) {
        setSelection(null);
        return false;
      }
      const shapes = t.kind === "zone" ? zoneMoveShapes(sceneRef.current!, t.box.id) : [t.box.id];
      dragRef.current = startDrag(t.box, x, y, t.kind, shapes);
      setDrag(dragRef.current);
      setSelection({ id: t.box.id, kind: t.kind, nonce: Date.now() });
      return true;
    },
    [targetAt],
  );

  const move = useCallback(
    (x: number, y: number) => {
      if (!dragRef.current) return;
      dragRef.current = dragTo(dragRef.current, x, y);
      setDrag(dragRef.current);
      const moves = dragMoves(dragRef.current);
      if (moves) {
        latest.current = moves;
        schedule();
      }
    },
    [schedule],
  );

  /** The release: a click only selects; a drag commits its Move (MoveZone for a zone) to the snapped corner,
   * with a Reparent in the same batch when it was dropped into another zone (or out of its zone). */
  const end = useCallback(() => {
    const d = dragRef.current;
    dragRef.current = null;
    setDrag(null);
    if (frame.current !== null) {
      cancelAnimationFrame(frame.current);
      frame.current = null;
    }
    latest.current = null;
    if (!d || !d.moved) return;
    const plan = planDrop(sceneRef.current!, d.box, d.kind, d.dx, d.dy);
    if (!plan) {
      setPreview(null);
      return;
    }
    if ("error" in plan) {
      setPreview(null);
      setNotice(plan.error);
      return;
    }
    const m = plan.ops.find((o) => o.op === "move" || o.op === "move_zone") as Extract<Op, { op: "move" | "move_zone" }> | undefined;
    // show the dropped (snapped) position at once; the server render replaces it after the save
    if (m) {
      const moves = Object.fromEntries(d.shapes.map((id) => [id, [m.x - d.box.x, m.y - d.box.y] as [number, number]]));
      void client.current!.call({ t: "drag", moves }).then(setPreview).catch(() => undefined);
    }
    void commit(plan.ops);
  }, [commit]);

  const remove = useCallback(() => {
    if (!active || !selection) return;
    const id = selection.id;
    setSelection(null);
    void commit(deleteOps(id));
  }, [active, selection, commit]);

  const clear = useCallback(() => {
    setSelection(null);
    setEditing(null);
  }, []);

  /** Double-click: open the inline editor on the node's title or the zone's label (SEL-05, ZON-07). */
  const beginEdit = useCallback(
    async (x: number, y: number) => {
      if (!active) return;
      const t = targetAt(x, y);
      if (!t) return;
      setSelection({ id: t.box.id, kind: t.kind, nonce: Date.now() });
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
    [active, targetAt, diagramKey],
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

  // the selected node's box, following the pointer while it is dragged
  let selectedBox: Box | null = null;
  if (active && selection && scene) {
    const b = selection.kind === "zone" ? zoneBox(scene, selection.id) : boxOf(scene, selection.id);
    if (b) selectedBox = drag && drag.moved ? { ...b, x: b.x + drag.dx, y: b.y + drag.dy } : b;
  }

  // the zone the dragged item would be dropped into, highlighted while the pointer moves (ZON-06)
  let dropBox: Box | null = null;
  if (active && drag && drag.moved && scene) {
    const target = dropTarget(scene, drag.box, drag.kind, drag.dx, drag.dy);
    dropBox = target ? zoneBox(scene, target) : null;
  }

  return {
    active,
    dropBox,
    editing,
    beginEdit,
    cancelEdit,
    commitEdit,
    editable,
    selection,
    selectedBox,
    dragging: drag !== null,
    preview,
    clearPreview: useCallback(() => setPreview(null), []),
    notice,
    hits,
    begin,
    move,
    end,
    remove,
    clear,
    srcmap: active ? srcmap : null,
  };
}
