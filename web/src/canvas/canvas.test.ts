// Canvas logic (spec: .specs/features/wasm-editor, SYN-01, LRF-01 edges part, OPS-05 browser part). Run: `bun test`.
import { describe, expect, test } from "bun:test";
import { CanvasClient, type Port, type Response } from "./client";
import { dragMoves, dragTo, startDrag } from "./drag";
import { CYCLE_MESSAGE, deleteOps, dropTarget, moveOps, planDrop, renameOps } from "./ops";
import { boxOf, descendants, hitTest, hitZone, nodeBoxes, snap, zoneBox, zoneMoveShapes, zoneParent, type SceneJson } from "./scene";
import { byteToIndex, entryField, yamlRange } from "./srcmap";

const scene: SceneJson = {
  width: 1000,
  height: 600,
  items: [
    { type: "shape", id: "zone-a", role: "zone", x: 0, y: 0, w: 1000, h: 600 },
    { type: "shape", id: "back", role: "node", x: 100, y: 100, w: 200, h: 100 },
    { type: "shape", id: "front", role: "node", x: 200, y: 150, w: 200, h: 100 }, // overlaps `back`, drawn later
    { type: "connector", id: "e0" },
    { type: "shape", id: "e0-label", role: "pill", x: 250, y: 120, w: 40, h: 20 },
    { type: "text", id: "title" },
  ],
};

describe("hit-test", () => {
  test("only nodes are targets: zones, pills and connectors are not", () => {
    expect(nodeBoxes(scene).map((b) => b.id)).toEqual(["back", "front"]);
    expect(hitTest(scene, 500, 500)).toBeNull(); // inside the zone only
    expect(hitTest(scene, 260, 125)).toBe("back"); // under the pill: the node, not the pill
  });

  test("the topmost node wins where boxes overlap", () => {
    expect(hitTest(scene, 250, 175)).toBe("front");
    expect(hitTest(scene, 120, 120)).toBe("back");
    expect(hitTest(scene, 390, 240)).toBe("front");
  });

  test("a point outside every node misses, and slop widens the boxes", () => {
    expect(hitTest(scene, 95, 100)).toBeNull();
    expect(hitTest(scene, 95, 100, 6)).toBe("back");
    expect(hitTest(scene, 100, 100)).toBe("back"); // the edge counts
  });

  test("boxOf finds a node box by id", () => {
    expect(boxOf(scene, "front")).toEqual({ id: "front", x: 200, y: 150, w: 200, h: 100 });
    expect(boxOf(scene, "zone-a")).toBeNull();
  });
});

describe("snapping", () => {
  test("rounds to the nearest 10 px, halves up, negatives too", () => {
    expect(snap(104)).toBe(100);
    expect(snap(105)).toBe(110);
    expect(snap(116.2)).toBe(120);
    expect(snap(-14)).toBe(-10);
    expect(snap(0)).toBe(0);
    expect(snap(23, 5)).toBe(25);
  });
});

describe("operations", () => {
  const box = { id: "back", x: 100, y: 100, w: 200, h: 100 };

  test("a drag becomes one Move to the snapped corner", () => {
    expect(moveOps(box, 43, -18)).toEqual([{ op: "move", id: "back", x: 140, y: 80 }]);
    expect(moveOps({ ...box, x: 103, y: 97 }, 42, 0)).toEqual([{ op: "move", id: "back", x: 150, y: 100 }]);
  });

  test("a drag that snaps back to the start is no operation", () => {
    expect(moveOps(box, 3, -4)).toBeNull();
    expect(moveOps(box, 0, 0)).toBeNull();
  });

  test("delete names the node", () => {
    expect(deleteOps("front")).toEqual([{ op: "delete", id: "front" }]);
  });
});

describe("drag state", () => {
  const box = { id: "back", x: 100, y: 100, w: 200, h: 100 };

  test("a press that barely moves is a click, not a drag", () => {
    const d = dragTo(startDrag(box, 150, 150), 152, 151);
    expect(d.moved).toBe(false);
    expect(dragMoves(d)).toBeNull();
  });

  test("past the threshold the drag reports the travel as a move map", () => {
    let d = startDrag(box, 150, 150);
    d = dragTo(d, 170, 130);
    expect(d.moved).toBe(true);
    expect(dragMoves(d)).toEqual({ back: [20, -20] });
    d = dragTo(d, 150, 150); // back at the start: still a drag, with no travel
    expect(dragMoves(d)).toEqual({ back: [0, 0] });
  });
});

describe("source map to editor range", () => {
  const text = "id: t\nnodes:\n  - {id: a, title: Ünï}\n  - {id: b, title: \"日本\"}\nedges:\n  - \"a -> b\"\n";
  const enc = new TextEncoder();
  const bytesAt = (s: string, from = 0) => {
    const i = text.indexOf(s, from);
    return [enc.encode(text.slice(0, i)).length, enc.encode(text.slice(0, i + s.length)).length] as [number, number];
  };
  const map = { a: bytesAt("{id: a, title: Ünï}"), b: bytesAt('{id: b, title: "日本"}'), e0: bytesAt('"a -> b"') };

  test("byte offsets become UTF-16 offsets that slice the entry text", () => {
    for (const [id, want] of [["a", "{id: a, title: Ünï}"], ["b", '{id: b, title: "日本"}'], ["e0", '"a -> b"']] as const) {
      const r = yamlRange(text, map, id)!;
      expect(text.slice(r.from, r.to)).toBe(want);
    }
  });

  test("an unknown id has no range; offsets past the end clamp", () => {
    expect(yamlRange(text, map, "zzz")).toBeNull();
    expect(byteToIndex(text, 10_000)).toBe(text.length);
    expect(byteToIndex("😀x", 4)).toBe(2); // one astral character is 4 bytes and 2 UTF-16 units
  });
});

describe("worker client", () => {
  function fake() {
    const listeners: ((e: { data: Response }) => void)[] = [];
    const sent: { id: number; t: string }[] = [];
    const port: Port = {
      postMessage: (m) => sent.push(m as { id: number; t: string }),
      addEventListener: (_t, l) => listeners.push(l),
    };
    const reply = (r: Response) => listeners.forEach((l) => l({ data: r }));
    return { port, sent, reply };
  }

  test("answers are matched to calls by id, in any order", async () => {
    const { port, sent, reply } = fake();
    const c = new CanvasClient(port);
    const a = c.call({ t: "srcmap", yaml: "a" });
    const b = c.call({ t: "ops", yaml: "b", ops: "[]" });
    expect(sent.map((s) => s.t)).toEqual(["srcmap", "ops"]);
    reply({ id: sent[1].id, ok: true, value: "second" });
    reply({ id: sent[0].id, ok: true, value: "first" });
    expect(await a).toBe("first");
    expect(await b).toBe("second");
  });

  test("a failed request rejects with the worker's reason; dispose rejects what is pending", async () => {
    const { port, sent, reply } = fake();
    const c = new CanvasClient(port);
    const failing = c.call({ t: "ops", yaml: "x", ops: "[]" });
    reply({ id: sent[0].id, ok: false, error: "unknown id `q`" });
    await expect(failing).rejects.toThrow("unknown id `q`");
    const waiting = c.call({ t: "srcmap", yaml: "y" });
    c.dispose();
    await expect(waiting).rejects.toThrow("stopped");
  });
});

// --- zones (T12): canvas-editor ZON-02..07, SEL-05 -----------------------------------------------------------
const shape = (id: string, role: string, x: number, y: number, w: number, h: number) => ({ type: "shape", id, role, x, y, w, h });
const zscene: SceneJson = {
  width: 1300,
  height: 800,
  items: [
    shape("z0", "zone", 20, 20, 800, 500),
    shape("z1", "zone", 60, 80, 300, 300),
    shape("z2", "zone", 900, 20, 300, 300),
    shape("n1", "node", 400, 100, 120, 60),
    shape("n2", "node", 80, 120, 120, 60),
    shape("n3", "node", 950, 400, 120, 60),
  ],
  zones: [
    { id: "outer", shape_id: "z0", children: ["inner", "n1"] },
    { id: "inner", shape_id: "z1", children: ["n2"] },
    { id: "empty", shape_id: "z2", children: [] },
  ],
};
const n = (id: string) => boxOf(zscene, id)!;
const z = (id: string) => zoneBox(zscene, id)!;

describe("zone geometry", () => {
  test("zone boxes use the declared ids; parents and descendants follow the children lists", () => {
    expect(z("inner")).toEqual({ id: "inner", x: 60, y: 80, w: 300, h: 300 });
    expect(zoneParent(zscene, "n2")).toBe("inner");
    expect(zoneParent(zscene, "inner")).toBe("outer");
    expect(zoneParent(zscene, "outer")).toBeNull();
    expect(zoneParent(zscene, "n3")).toBeNull();
    expect(descendants(zscene, "outer").sort()).toEqual(["inner", "n1", "n2"]);
    expect(descendants(zscene, "empty")).toEqual([]);
  });

  test("a press on a header band or outline grabs the innermost zone; the middle of a zone grabs nothing", () => {
    expect(hitZone(zscene, 100, 100)).toBe("inner"); // header band of inner, which lies inside outer
    expect(hitZone(zscene, 25, 300)).toBe("outer"); // outer's header band is above; here its left outline
    expect(hitZone(zscene, 200, 300)).toBeNull(); // inside inner, away from every header and edge
    expect(hitZone(zscene, 1000, 40)).toBe("empty");
    expect(hitZone(zscene, 1250, 700)).toBeNull();
  });

  test("the zone move map holds the zone, its child zones and every child node, as scene shape ids", () => {
    expect(zoneMoveShapes(zscene, "outer").sort()).toEqual(["n1", "n2", "z0", "z1"]);
    expect(zoneMoveShapes(zscene, "inner").sort()).toEqual(["n2", "z1"]);
    expect(zoneMoveShapes(zscene, "empty")).toEqual(["z2"]);
    const d = dragTo(startDrag(z("outer"), 100, 100, "zone", zoneMoveShapes(zscene, "outer")), 130, 90);
    expect(dragMoves(d)).toEqual({ z0: [30, -10], z1: [30, -10], n1: [30, -10], n2: [30, -10] });
  });
});

describe("drop target and the batch for a drop", () => {
  test("the target is the innermost zone holding the centre of the moved box, none outside every zone", () => {
    expect(dropTarget(zscene, n("n2"), "node", 0, 0)).toBe("inner");
    expect(dropTarget(zscene, n("n2"), "node", 500, 0)).toBe("outer");
    expect(dropTarget(zscene, n("n2"), "node", 1000, 0)).toBe("empty");
    expect(dropTarget(zscene, n("n2"), "node", 0, 600)).toBeNull();
    expect(dropTarget(zscene, n("n3"), "node", 0, 0)).toBeNull();
  });

  test("moving a node inside its zone is a Move only", () => {
    expect(planDrop(zscene, n("n1"), "node", 3, 300)).toEqual({ ops: [{ op: "move", id: "n1", x: 400, y: 400 }] });
  });

  test("dropping a node into another zone is a Move and a Reparent in one batch", () => {
    expect(planDrop(zscene, n("n3"), "node", 0, -200)).toEqual({
      ops: [
        { op: "move", id: "n3", x: 950, y: 200 },
        { op: "reparent", id: "n3", parent: "empty" },
      ],
    });
    expect(planDrop(zscene, n("n2"), "node", 500, 0)).toEqual({
      ops: [
        { op: "move", id: "n2", x: 580, y: 120 },
        { op: "reparent", id: "n2", parent: "outer" },
      ],
    });
  });

  test("dropping a node outside every zone takes it out of its zone", () => {
    expect(planDrop(zscene, n("n1"), "node", 0, 600)).toEqual({
      ops: [
        { op: "move", id: "n1", x: 400, y: 700 },
        { op: "reparent", id: "n1", parent: null },
      ],
    });
  });

  test("a zone moves with MoveZone and nests or un-nests by the same rule", () => {
    expect(planDrop(zscene, z("inner"), "zone", 600, 0)).toEqual({ ops: [{ op: "move_zone", id: "inner", x: 660, y: 80 }] });
    expect(planDrop(zscene, z("inner"), "zone", 900, 0)).toEqual({
      ops: [
        { op: "move_zone", id: "inner", x: 960, y: 80 },
        { op: "reparent", id: "inner", parent: "empty" },
      ],
    });
    expect(planDrop(zscene, z("empty"), "zone", -700, 0)).toEqual({
      ops: [
        { op: "move_zone", id: "empty", x: 200, y: 20 },
        { op: "reparent", id: "empty", parent: "inner" },
      ],
    });
    expect(planDrop(zscene, z("inner"), "zone", 0, 600)).toEqual({
      ops: [
        { op: "move_zone", id: "inner", x: 60, y: 680 },
        { op: "reparent", id: "inner", parent: null },
      ],
    });
  });

  test("nothing to do when the drag snaps back and the zone stays", () => {
    expect(planDrop(zscene, n("n1"), "node", 2, -3)).toBeNull();
  });

  test("a zone dropped into its own descendant is refused with the spec message", () => {
    const cyc: SceneJson = {
      width: 400,
      height: 400,
      items: [shape("z0", "zone", 0, 0, 200, 200), shape("z1", "zone", 50, 50, 100, 100)],
      zones: [
        { id: "a", shape_id: "z0", children: ["b"] },
        { id: "b", shape_id: "z1", children: [] },
      ],
    };
    // a's centre (100, 100) is inside its child b, which travels with it
    expect(planDrop(cyc, zoneBox(cyc, "a")!, "zone", 10, 10)).toEqual({ error: CYCLE_MESSAGE });
    expect(CYCLE_MESSAGE).toBe("A zone cannot contain itself");
    // dropping a clear of b is fine
    expect(planDrop(cyc, zoneBox(cyc, "b")!, "zone", 400, 0)).toEqual({
      ops: [
        { op: "move_zone", id: "b", x: 450, y: 50 },
        { op: "reparent", id: "b", parent: null },
      ],
    });
  });
});

describe("inline edit", () => {
  test("rename names the node or zone", () => {
    expect(renameOps("inner", "Back end")).toEqual([{ op: "rename", id: "inner", title: "Back end" }]);
  });

  test("the current title is read from the entry text, quoted or plain, block or flow", () => {
    expect(entryField('{id: a, title: "Say \\"hi\\": ok", at: [1, 2]}', "title")).toBe('Say "hi": ok');
    expect(entryField("id: z\n    label: Zone A   # note\n    x: 20", "label")).toBe("Zone A");
    expect(entryField("{id: a, title: 'it''s', at: [1]}", "title")).toBe("it's");
    expect(entryField("{id: a, subtitle: nope}", "title")).toBeNull();
    expect(entryField("{id: a, title: Plain, x: 1}", "title")).toBe("Plain");
  });
});
