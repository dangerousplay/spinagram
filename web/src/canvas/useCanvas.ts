// Canvas mode of the diagram view: select, drag with live edges, Delete. The Rust core runs in a Web Worker
// (spinagram-wasm): `reroute` + `renderSvg` once per animation frame while a node is dragged, `applyOps` on
// release, then the file is saved and the server render replaces the preview.
import { useCallback, useEffect, useRef, useState } from "react";
import { api, ApiError } from "../api";
import { CanvasClient } from "./client";
import { dragMoves, dragTo, startDrag, type Drag } from "./drag";
import { deleteOps, moveOps, type Op } from "./ops";
import { boxOf, hitTest, type Box, type SceneJson } from "./scene";
import type { SrcMap } from "./srcmap";

export const CHANGED_ON_DISK = "File changed on disk; edit not applied";

type Options = {
  diagramKey: string;
  layout: string | null;
  enabled: boolean; // the Canvas toggle
  rev: number; // live-reload counter of the diagram
  tick: number; // bumped after an edit: the scene is read again
  reload: () => void; // render the diagram again (after a save, or a refused one)
};

export type Selection = { id: string; nonce: number };

export function useCanvas({ diagramKey, layout, enabled, rev, tick, reload }: Options) {
  const [scene, setScene] = useState<SceneJson | null>(null);
  const [editable, setEditable] = useState<boolean | null>(null); // null until the scene arrived
  const [ready, setReady] = useState(false); // the worker holds the scene
  const [selection, setSelection] = useState<Selection | null>(null);
  const [drag, setDrag] = useState<Drag | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
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

  /** The node under a scene point, without changing anything (used to decide between pan and drag). */
  const hits = useCallback((x: number, y: number) => !!sceneRef.current && hitTest(sceneRef.current, x, y) !== null, []);

  /** A press at a scene point: selects the node under it and starts dragging it. Returns whether one was hit. */
  const begin = useCallback((x: number, y: number): boolean => {
    const sc = sceneRef.current;
    const id = sc ? hitTest(sc, x, y) : null;
    const box = sc && id ? boxOf(sc, id) : null;
    if (!box) {
      setSelection(null);
      return false;
    }
    dragRef.current = startDrag(box, x, y);
    setDrag(dragRef.current);
    setSelection({ id: box.id, nonce: Date.now() });
    return true;
  }, []);

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

  /** The release: a click only selects; a drag commits one Move snapped to the grid. */
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
    const ops = moveOps(d.box, d.dx, d.dy);
    if (!ops) {
      setPreview(null);
      return;
    }
    const m = ops[0] as Extract<Op, { op: "move" }>;
    // show the dropped (snapped) position at once; the server render replaces it after the save
    void client.current!
      .call({ t: "drag", moves: { [d.box.id]: [m.x - d.box.x, m.y - d.box.y] } })
      .then(setPreview)
      .catch(() => undefined);
    void commit(ops);
  }, [commit]);

  const remove = useCallback(() => {
    if (!active || !selection) return;
    const id = selection.id;
    setSelection(null);
    void commit(deleteOps(id));
  }, [active, selection, commit]);

  const clear = useCallback(() => setSelection(null), []);

  const srcmap = useCallback(
    async (yaml: string): Promise<SrcMap> => JSON.parse(await client.current!.call({ t: "srcmap", yaml })) as SrcMap,
    [],
  );

  // the selected node's box, following the pointer while it is dragged
  let selectedBox: Box | null = null;
  if (active && selection && scene) {
    const b = boxOf(scene, selection.id);
    if (b) selectedBox = drag && drag.moved ? { ...b, x: b.x + drag.dx, y: b.y + drag.dy } : b;
  }

  return {
    active,
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
