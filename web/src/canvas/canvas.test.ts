// Canvas logic (spec: .specs/features/wasm-editor, SYN-01, LRF-01 edges part, OPS-05 browser part). Run: `bun test`.
import { describe, expect, test } from "bun:test";
import { CanvasClient, type Port, type Response } from "./client";
import { dragMoves, dragTo, startDrag } from "./drag";
import { deleteOps, moveOps } from "./ops";
import { boxOf, hitTest, nodeBoxes, snap, type SceneJson } from "./scene";
import { byteToIndex, yamlRange } from "./srcmap";

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
