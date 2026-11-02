// Canvas logic (spec: .specs/features/wasm-editor, SYN-01, LRF-01 edges part, OPS-05 browser part). Run: `bun test`.
import { describe, expect, test } from "bun:test";
import { CanvasClient, type Port, type Response } from "./client";
import { dragMoves, dragTo, startDrag } from "./drag";
import { CYCLE_MESSAGE, zoneStyleOps, deleteOps, dropTarget, groupOps, moveOps, planDrop, planMultiDrop, renameOps, setContainerOps, ungroupOps } from "./ops";
import {
  boxOf,
  containerAt,
  containerOf,
  descendants,
  hitTest,
  hitZone,
  insertionIndex,
  nodeBoxes,
  rubberBand,
  snap,
  zoneBox,
  zoneMoveShapes,
  zoneParent,
  type SceneJson,
} from "./scene";
import { byteToIndex, entryField, yamlRange } from "./srcmap";
import { History, LIMIT } from "./history";
import { PALETTE_COLLAPSED_KEY, PALETTE_OPEN_KEY, readCollapsed, readPaletteOpen, writeCollapsed, writePaletteOpen } from "./paletteState";
import {
  EMPTY_BURST,
  KEYMAP,
  cursorFor,
  escapeStep,
  matchKey,
  nudgeMoves,
  nudgeOps,
  pressNudge,
  selectionFrame,
  shortcutRows,
  type KeyAction,
  type KeyLike,
} from "./interaction";
import { CONTAINER_ICON_NAMES, hasIcon, iconNameOf, ICON_NAMES } from "./icons";
import { QUICK_ACTIONS } from "./props";
import { ACTIONS, CLICK_SLOP, TOOLS, connectOps, editBoxOf, isPlaceTool, placeOps, toolAfterUse } from "./tools";
import { BUILTINS, SHAPE_KINDS, ZONE_TITLES, buildCorpus, zoneStyleItems, categorize, categoryOf, defaultCollapsed, paletteRows, displayName, dropOps, ghostOf, newId, noMatch, search, type IconEntry } from "./palette";

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

  test("where two zones' header bands overlap, the press grabs the smaller (inner) one", () => {
    const nested: SceneJson = {
      width: 600,
      height: 600,
      items: [shape("z0", "zone", 0, 0, 500, 500), shape("z1", "zone", 10, 10, 200, 200)],
      zones: [
        { id: "outer", shape_id: "z0", children: ["inner"] },
        { id: "inner", shape_id: "z1", children: [] },
      ],
    };
    expect(hitZone(nested, 20, 20)).toBe("inner"); // inside both header bands
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

// --- multi-select and containers (T13): SEL-01, SEL-02, GRP-01..06 ---------------------------------------------
const gscene: SceneJson = {
  width: 1200,
  height: 800,
  items: [
    shape("f1", "node", 700, 100, 100, 60),
    shape("f2", "node", 400, 160, 100, 60),
    shape("f3", "node", 550, 40, 100, 60),
    shape("a", "node", 100, 500, 100, 60),
    shape("b", "node", 230, 500, 100, 60),
    shape("c", "node", 360, 500, 100, 60),
    shape("h", "node", 800, 100, 80, 60),
    shape("i", "node", 800, 200, 80, 60),
  ],
  containers: [
    { id: "row0", axis: "row", members: ["a", "b", "c"], box: [100, 500, 360, 60] },
    { id: "column1", axis: "column", members: ["h", "i"], box: [800, 100, 80, 160] },
  ],
};
const g = (id: string) => boxOf(gscene, id)!;

describe("rubber band", () => {
  test("selects the nodes whose boxes meet the rectangle, from any corner, and nothing in empty space", () => {
    expect(rubberBand(gscene, { x: 90, y: 490 }, { x: 340, y: 580 }).sort()).toEqual(["a", "b"]);
    expect(rubberBand(gscene, { x: 340, y: 580 }, { x: 90, y: 490 }).sort()).toEqual(["a", "b"]); // reversed
    expect(rubberBand(gscene, { x: 200, y: 560 }, { x: 230, y: 600 }).sort()).toEqual(["a", "b"]); // touching edges count
    expect(rubberBand(gscene, { x: 0, y: 700 }, { x: 50, y: 790 })).toEqual([]);
    expect(rubberBand(gscene, { x: 950, y: 650 }, { x: 1100, y: 750 })).toEqual([]); // below and right of every node
  });
});

describe("grouping", () => {
  test("members are ordered by x for a row and by y for a column, gap 20", () => {
    expect(groupOps(gscene, ["f1", "f2", "f3"], "row")).toEqual([{ op: "group", axis: "row", ids: ["f2", "f3", "f1"], gap: 20 }]);
    expect(groupOps(gscene, ["f1", "f2", "f3"], "column")).toEqual([{ op: "group", axis: "column", ids: ["f3", "f1", "f2"], gap: 20 }]);
  });

  test("nodes already in a container are left out, and fewer than two nodes make no group", () => {
    expect(groupOps(gscene, ["f1", "a", "f2"], "row")).toEqual([{ op: "group", axis: "row", ids: ["f2", "f1"], gap: 20 }]);
    expect(groupOps(gscene, ["f1", "a"], "row")).toBeNull();
    expect(groupOps(gscene, ["f1"], "column")).toBeNull();
  });

  test("Ungroup carries the rendered box of every member", () => {
    expect(ungroupOps(gscene, "row0")).toEqual([
      { op: "ungroup", id: "row0", boxes: { a: [100, 500, 100, 60], b: [230, 500, 100, 60], c: [360, 500, 100, 60] } },
    ]);
    expect(ungroupOps(gscene, "nope")).toBeNull();
  });

  test("the property bar sends gap and align", () => {
    expect(setContainerOps("row0", { gap: 40 })).toEqual([{ op: "set_container", id: "row0", gap: 40 }]);
    expect(setContainerOps("row0", { gap: 8, align: "start" })).toEqual([{ op: "set_container", id: "row0", gap: 8, align: "start" }]);
  });

  test("containers and members are found from the scene", () => {
    expect(containerOf(gscene, "b")?.id).toBe("row0");
    expect(containerOf(gscene, "f1")).toBeNull();
    expect(containerAt(gscene, 300, 520)?.id).toBe("row0");
    expect(containerAt(gscene, 300, 300)).toBeNull();
  });
});

describe("dropping on and out of containers", () => {
  test("the insertion index counts the other members whose centre lies before the drop point", () => {
    const row = gscene.containers![0];
    expect(insertionIndex(gscene, row, "f1", 100, 530)).toBe(0); // centres are 150, 280, 410
    expect(insertionIndex(gscene, row, "f1", 300, 530)).toBe(2);
    expect(insertionIndex(gscene, row, "f1", 500, 530)).toBe(3);
    expect(insertionIndex(gscene, row, "a", 300, 530)).toBe(1); // `a` itself does not count: b is before, c after
    const col = gscene.containers![1];
    expect(insertionIndex(gscene, col, "f1", 840, 120)).toBe(0); // centres 130, 230
    expect(insertionIndex(gscene, col, "f1", 840, 180)).toBe(1);
  });

  test("a free node dropped on a container joins it at the gap its centre falls in", () => {
    // f1 (700,100) dragged so its centre lands at x 300 inside row0's box
    expect(planDrop(gscene, g("f1"), "node", -400, 420)).toEqual({ ops: [{ op: "add_to_container", id: "row0", node: "f1", index: 2 }] });
  });

  test("a member dropped inside its container is reordered; dropped where it was it is not", () => {
    expect(planDrop(gscene, g("a"), "node", 250, 0)).toEqual({ ops: [{ op: "add_to_container", id: "row0", node: "a", index: 1 }] });
    expect(planDrop(gscene, g("a"), "node", 10, 0)).toBeNull();
  });

  test("a member dragged out is removed from its container and placed at the drop point", () => {
    expect(planDrop(gscene, g("b"), "node", 0, -300)).toEqual({
      ops: [{ op: "remove_from_container", id: "row0", node: "b", boxes: { b: [230, 200, 100, 60] } }],
    });
  });

  test("taking a member out of a two-member container sends every member's box, for the dissolve", () => {
    expect(planDrop(gscene, g("h"), "node", -300, 0)).toEqual({
      ops: [{ op: "remove_from_container", id: "column1", node: "h", boxes: { h: [500, 100, 80, 60], i: [800, 200, 80, 60] } }],
    });
  });
});

describe("moving a selection", () => {
  const items = (ids: string[]) => ids.map((id) => ({ box: g(id), kind: "node" as const }));

  test("every selected node moves in one batch by the same drag", () => {
    expect(planMultiDrop(gscene, items(["f1", "f2", "f3"]), 40, 20)).toEqual({
      ops: [
        { op: "move", id: "f1", x: 740, y: 120 },
        { op: "move", id: "f2", x: 440, y: 180 },
        { op: "move", id: "f3", x: 590, y: 60 },
      ],
    });
  });

  test("container members do not move freely with a selection", () => {
    expect(planMultiDrop(gscene, items(["f1", "a"]), 40, 20)).toEqual({ ops: [{ op: "move", id: "f1", x: 740, y: 120 }] });
  });

  test("a node inside a selected zone moves with the zone only", () => {
    const sel = [
      { box: z("inner"), kind: "zone" as const },
      { box: n("n2"), kind: "node" as const },
    ];
    expect(planMultiDrop(zscene, sel, 30, 0)).toEqual({ ops: [{ op: "move_zone", id: "inner", x: 90, y: 80 }] });
  });

  test("a refused item refuses the batch", () => {
    const cyc: SceneJson = {
      width: 400,
      height: 400,
      items: [shape("z0", "zone", 0, 0, 200, 200), shape("z1", "zone", 50, 50, 100, 100)],
      zones: [
        { id: "a", shape_id: "z0", children: ["b"] },
        { id: "b", shape_id: "z1", children: [] },
      ],
    };
    expect(planMultiDrop(cyc, [{ box: zoneBox(cyc, "a")!, kind: "zone" }], 10, 10)).toEqual({ error: CYCLE_MESSAGE });
  });
});

// --- icon palette (T14): canvas-editor PAL-01..07, ZON-01 -------------------------------------------------------
const icon = (pack: string, name: string, aliases: string[] = []): IconEntry => ({ pack, name, aliases });
const small = buildCorpus([
  icon("aws", "postgresql", ["rds-postgres"]),
  icon("aws", "postgres", ["pg"]),
  icon("gcp", "postgis"),
  icon("gcp", "progress-bar"),
  icon("k8s", "post-office"),
  icon("aws", "redis", ["cache"]),
  icon("aws", "s3", ["bucket", "object-storage"]),
  icon("gcp", "kubernetes-engine", ["gke"]),
  icon("k8s", "pod"),
  icon("aws", "dynamodb", ["database", "nosql"]),
]);
const names = (q: string) => search(small, q).map((i) => (i.type === "icon" ? i.name : i.type));

describe("palette search", () => {
  test('"postgress" ranks postgres first', () => {
    expect(names("postgress")[0]).toBe("postgres");
  });

  test("one typo is tolerated in a query of 4 or more characters: substitution, deletion, insertion, transposition", () => {
    for (const q of ["postgras", "postgrs", "postgress", "psotgres", "pstgres"]) expect(names(q)).toContain("postgres");
    expect(names("rdis")).toContain("redis"); // 4 characters, transposed
    expect(names("redus")).toContain("redis");
    expect(names("kuberntes")).toContain("kubernetes-engine");
  });

  test("names, aliases and the pack name match, in any case", () => {
    expect(names("POSTGRES")).toContain("postgres");
    expect(names("bucket")).toEqual(["s3"]); // an alias
    expect(names("nosql")).toEqual(["dynamodb"]);
    expect(names("k8s")).toEqual(expect.arrayContaining(["pod", "post-office"])); // the pack name
    expect(names("gke")).toEqual(["kubernetes-engine"]);
  });

  test("an empty query lists the built-ins first: Zone, Row, Column, then the shapes", () => {
    const first = search(small, "", 5).map((i) => i.type);
    expect(first).toEqual(["zone", "row", "column", "shape", "shape"]);
    expect(names("zone")[0]).toBe("zone");
    expect(names("diamond")[0]).toBe("shape");
  });

  test("a query that matches nothing is empty and has the spec message", () => {
    expect(search(small, "qzxwv")).toEqual([]);
    expect(noMatch("qzxwv")).toBe("No icons match 'qzxwv'");
    expect(noMatch("  qzxwv ")).toBe("No icons match 'qzxwv'");
  });

  test("display names are the kebab name in title case", () => {
    expect(displayName("amazon-s3")).toBe("Amazon S3");
    expect(displayName("postgres")).toBe("Postgres");
  });
});

describe("new ids", () => {
  test("the kebab-case title, suffixed -2, -3 until unique among node and zone ids", () => {
    expect(newId("Postgres", [])).toBe("postgres");
    expect(newId("Postgres", ["postgres"])).toBe("postgres-2");
    expect(newId("Postgres", ["postgres", "postgres-2"])).toBe("postgres-3");
    expect(newId("Amazon S3 (EU)!", [])).toBe("amazon-s3-eu");
    expect(newId("???", [])).toBe("node");
    expect(newId("Zone", ["zone"])).toBe("zone-2"); // a zone id counts
  });
});

describe("dropping palette items", () => {
  const pg = small.items.find((i) => i.type === "icon" && i.name === "postgres")!;
  const empty: SceneJson = { width: 1600, height: 900, items: [] };

  test("an icon becomes a 220 x 96 node centred on the snapped drop point, with icon ref and display title", () => {
    expect(dropOps(empty, pg, 500, 300)).toEqual([{ op: "add_node", id: "postgres", title: "Postgres", icon: "aws:postgres", x: 390, y: 250, w: 220, h: 96 }]);
  });

  test("the id is made unique against the nodes and zones already there", () => {
    const sc: SceneJson = { ...zscene, width: 1600, height: 900, items: [...zscene.items, shape("postgres", "node", 0, 0, 10, 10)] };
    const op = dropOps(sc, pg, 1000, 700)[0];
    expect(op).toMatchObject({ op: "add_node", id: "postgres-2" });
  });

  test("a shape item adds a node of that kind titled New <kind>", () => {
    const box = small.items.find((i) => i.type === "shape" && i.kind === "box")!;
    const diamond = small.items.find((i) => i.type === "shape" && i.kind === "diamond")!;
    expect(dropOps(empty, box, 500, 300)).toEqual([{ op: "add_node", id: "new-box", title: "New box", kind: "box", x: 390, y: 250, w: 220, h: 96 }]);
    expect(dropOps(empty, diamond, 500, 300)[0]).toMatchObject({ kind: "diamond", title: "New diamond" });
  });

  test("the Zone item adds a 600 x 400 zone labelled Zone with a unique id (ZON-01)", () => {
    const zone = small.items.find((i) => i.type === "zone")!;
    expect(dropOps(empty, zone, 100, 100)).toEqual([{ op: "add_zone", id: "zone", label: "Zone", x: 100, y: 100, w: 600, h: 400 }]);
    expect(dropOps({ ...zscene, width: 1600, height: 900 }, zone, 100, 100)[0]).toMatchObject({ op: "add_zone", id: "zone" });
    const taken: SceneJson = { ...empty, zones: [{ id: "zone", shape_id: "z0", children: [] }] };
    expect(dropOps(taken, zone, 100, 100)[0]).toMatchObject({ id: "zone-2" });
  });

  test("a node dropped with its centre in a zone also becomes its child (ZON-02)", () => {
    const sc: SceneJson = { ...zscene, width: 1600, height: 900 };
    const ops = dropOps(sc, pg, 200, 300); // inside `inner`
    expect(ops).toEqual([
      { op: "add_node", id: "postgres", title: "Postgres", icon: "aws:postgres", x: 90, y: 250, w: 220, h: 96 },
      { op: "reparent", id: "postgres", parent: "inner" },
    ]);
  });

  test("the node is kept inside the canvas", () => {
    expect(dropOps(empty, pg, 0, 0)[0]).toMatchObject({ x: 0, y: 0 });
    expect(dropOps(empty, pg, 5000, 5000)[0]).toMatchObject({ x: 1380, y: 804 });
  });

  test("Row and Column add two boxes and group them on that axis", () => {
    const row = small.items.find((i) => i.type === "row")!;
    const ops = dropOps(empty, row, 500, 300);
    expect(ops.map((o) => o.op)).toEqual(["add_node", "add_node", "group"]);
    expect(ops[2]).toMatchObject({ op: "group", axis: "row", ids: ["new-box", "new-box-2"] });
    expect(dropOps(empty, small.items.find((i) => i.type === "column")!, 500, 300)[2]).toMatchObject({ axis: "column" });
  });
});

describe("palette search speed (PAL-01)", () => {
  // 10,000 icons across 12 packs: names built from word lists, some with aliases
  const stems = ["data", "base", "server", "queue", "cache", "storage", "network", "load", "balancer", "function", "stream", "cluster", "gateway", "monitor", "secret", "key", "vault", "index", "search", "event", "bus", "mesh", "proxy", "topic", "worker", "batch", "notebook", "registry", "pipeline", "firewall"];
  const prefixes = ["amazon", "azure", "google", "cloud", "elastic", "managed", "private", "global", "edge", "secure"];
  let seed = 7;
  const rnd = (n: number) => {
    seed = (seed * 1664525 + 1013904223) % 4294967296;
    return seed % n;
  };
  const corpus: IconEntry[] = [];
  for (let i = 0; i < 10_000; i++) {
    const name = `${prefixes[rnd(prefixes.length)]}-${stems[rnd(stems.length)]}-${stems[rnd(stems.length)]}-${i}`;
    corpus.push(icon(`pack${i % 12}`, name, i % 3 === 0 ? [stems[rnd(stems.length)], `alias${i}`] : []));
  }
  const big = buildCorpus(corpus);

  test("p95 of searches over 10,000 icons is at most 100 ms", () => {
    const queries = ["postgres", "data", "dta bse", "amazon server", "azure-queue", "balncer", "gateway 42", "elastic cluster", "vault", "secure-key-9", "pack3 stream", "notebok", "a", "ser", "cloud", "managd proxy"];
    const times: number[] = [];
    for (let round = 0; round < 8; round++) {
      for (const q of queries) {
        const t0 = performance.now();
        search(big, q);
        times.push(performance.now() - t0);
      }
    }
    times.sort((a, b) => a - b);
    const p95 = times[Math.floor(times.length * 0.95)];
    console.log(`palette search over ${big.items.length} items: p50 ${times[times.length >> 1].toFixed(1)} ms, p95 ${p95.toFixed(1)} ms, max ${times[times.length - 1].toFixed(1)} ms`);
    expect(big.items.length).toBeGreaterThanOrEqual(10_000);
    expect(p95).toBeLessThanOrEqual(100);
  });
});

// --- undo and redo (T15): canvas-editor SEL-09 -------------------------------------------------------------------
describe("history", () => {
  const edit = (i: number) => ({ path: "d.yaml", before: `text ${i}\n`, after: `text ${i + 1}\n` });

  test("keeps 50 steps: the oldest are dropped, the newest undone first", () => {
    expect(LIMIT).toBe(50);
    const h = new History();
    for (let i = 0; i < 60; i++) h.record(edit(i));
    const undone: string[] = [];
    for (let e = h.undo(); e; e = h.undo()) undone.push(e.before);
    expect(undone).toHaveLength(50);
    expect(undone[0]).toBe("text 59\n");
    expect(undone[49]).toBe("text 10\n"); // edits 0..9 were dropped
    expect(h.canUndo).toBe(false);
    expect(h.undo()).toBeUndefined();
  });

  test("a new edit clears the redo stack", () => {
    const h = new History();
    h.record(edit(0));
    h.record(edit(1));
    h.undo();
    expect(h.canRedo).toBe(true);
    h.record(edit(5));
    expect(h.canRedo).toBe(false);
    expect(h.redo()).toBeUndefined();
  });

  test("undo gives the exact prior text, redo the text after, and they alternate", () => {
    const h = new History();
    const before = "id: t   # keep\nnodes:\n  - {id: a, at: [1, 2, 3, 4]}\n\n";
    const after = "id: t   # keep\nnodes:\n  - {id: a, at: [10, 20, 3, 4]}\n\n";
    h.record({ path: "d.yaml", before, after });
    expect(h.undo()).toEqual({ path: "d.yaml", before, after });
    expect(h.canUndo).toBe(false);
    expect(h.redo()?.after).toBe(after);
    expect(h.canUndo).toBe(true);
    expect(h.undo()?.before).toBe(before);
  });

  test("an edit that changed nothing is not recorded; clear forgets both stacks", () => {
    const h = new History();
    h.record({ path: "d.yaml", before: "a", after: "a" });
    expect(h.canUndo).toBe(false);
    h.record(edit(0));
    h.undo();
    h.clear();
    expect(h.canUndo || h.canRedo).toBe(false);
  });
});

describe("palette open state (PAL-03)", () => {
  const mem = (initial?: string) => {
    const data = new Map<string, string>(initial === undefined ? [] : [[PALETTE_OPEN_KEY, initial]]);
    return { getItem: (k: string) => data.get(k) ?? null, setItem: (k: string, v: string) => void data.set(k, v) };
  };
  test("starts collapsed when nothing is stored", () => {
    expect(readPaletteOpen(mem())).toBe(false);
  });
  test("an opened palette is remembered, and so is a collapsed one", () => {
    const s = mem();
    writePaletteOpen(true, s);
    expect(readPaletteOpen(s)).toBe(true);
    writePaletteOpen(false, s);
    expect(readPaletteOpen(s)).toBe(false);
  });
  test("the stored flag survives what a save does (a fresh read gives the same state)", () => {
    const s = mem("1");
    expect(readPaletteOpen(s)).toBe(true);
    expect(readPaletteOpen(s)).toBe(true);
  });
  test("storage that throws falls back to collapsed and never throws", () => {
    const bad = {
      getItem: () => {
        throw new Error("denied");
      },
      setItem: () => {
        throw new Error("denied");
      },
    };
    expect(readPaletteOpen(bad)).toBe(false);
    expect(() => writePaletteOpen(true, bad)).not.toThrow();
    expect(readPaletteOpen(null)).toBe(false);
  });
});

describe("keyboard nudge (SEL-02 polish)", () => {
  const press = (key: string, shiftKey = false) => {
    const a = matchKey({ key, shiftKey, metaKey: false, ctrlKey: false, altKey: false });
    if (!a || a.action !== "nudge") throw new Error(`${key} is not a nudge`);
    return a;
  };
  const sel = [{ id: "n1", kind: "node" as const }];

  test("arrows nudge 1 px and Shift+arrow 10 px", () => {
    expect(press("ArrowRight")).toEqual({ action: "nudge", dx: 1, dy: 0 });
    expect(press("ArrowUp")).toEqual({ action: "nudge", dx: 0, dy: -1 });
    expect(press("ArrowLeft", true)).toEqual({ action: "nudge", dx: -10, dy: 0 });
    expect(press("ArrowDown", true)).toEqual({ action: "nudge", dx: 0, dy: 10 });
  });

  test("a burst of 5 presses is one Move per node with the summed offset", () => {
    let burst = EMPTY_BURST;
    for (const k of ["ArrowRight", "ArrowRight", "ArrowRight", "ArrowDown", "ArrowDown"]) {
      const a = press(k);
      burst = pressNudge(burst, a.dx, a.dy);
    }
    expect(burst).toEqual({ dx: 3, dy: 2, presses: 5 });
    const b = n("n1");
    const two = [...sel, { id: "n3", kind: "node" as const }];
    const plan = nudgeOps(zscene, two, burst);
    expect(plan).toEqual({
      ops: [
        { op: "move", id: "n1", x: b.x + 3, y: b.y + 2 },
        { op: "move", id: "n3", x: n("n3").x + 3, y: n("n3").y + 2 },
      ],
    });
  });

  test("a burst that returns to the start changes nothing; a zone nudges as MoveZone with its children", () => {
    let burst = pressNudge(EMPTY_BURST, 1, 0);
    burst = pressNudge(burst, -1, 0);
    expect(nudgeOps(zscene, sel, burst)).toBeNull();
    const zb = z("empty");
    const plan = nudgeOps(zscene, [{ id: "empty", kind: "zone" }], pressNudge(EMPTY_BURST, 0, 10));
    expect(plan).toEqual({ ops: [{ op: "move_zone", id: "empty", x: zb.x, y: zb.y + 10 }] });
    expect(nudgeMoves(zscene, [{ id: "outer", kind: "zone" }], pressNudge(EMPTY_BURST, 1, 0))).toEqual({ z0: [1, 0], z1: [1, 0], n1: [1, 0], n2: [1, 0] });
  });

  test("row and column members are placed by their container, so a nudge leaves them alone", () => {
    const burst = pressNudge(EMPTY_BURST, 10, 0);
    expect(nudgeOps(gscene, [{ id: "a", kind: "node" }], burst)).toBeNull();
    // even a long burst that would carry the member out of its row is not turned into a removal
    expect(nudgeOps(gscene, [{ id: "a", kind: "node" }], pressNudge(EMPTY_BURST, 0, 200))).toBeNull();
    const plan = nudgeOps(gscene, [{ id: "a", kind: "node" }, { id: "f1", kind: "node" }], burst);
    expect(plan?.ops.map((o) => ("id" in o ? o.id : null))).toEqual(["f1"]);
  });
});

describe("escape", () => {
  const base = { sheet: false, dragging: false, nudging: false, selected: 0, palette: false };
  test("each press undoes the innermost thing: sheet, drag, nudge, selection, palette", () => {
    expect(escapeStep({ ...base, sheet: true, dragging: true, selected: 2, palette: true })).toBe("sheet");
    expect(escapeStep({ ...base, dragging: true, selected: 2, palette: true })).toBe("drag");
    expect(escapeStep({ ...base, nudging: true, selected: 2 })).toBe("nudge");
    expect(escapeStep({ ...base, selected: 2, palette: true })).toBe("selection");
    expect(escapeStep({ ...base, palette: true })).toBe("palette");
    expect(escapeStep(base)).toBeNull();
  });

  test("with a tool active Esc returns to Select once the selection is clear, before the palette closes", () => {
    expect(escapeStep({ ...base, tool: true, selected: 1, palette: true })).toBe("selection");
    expect(escapeStep({ ...base, tool: true, palette: true })).toBe("tool");
    expect(escapeStep({ ...base, tool: true, dragging: true })).toBe("drag");
    expect(escapeStep({ ...base, palette: true })).toBe("palette");
  });

  test("a cancelled drag sends no operation: the move map of the drag is dropped and the pre-drag scene stays", () => {
    // the drag in progress holds a move map; the cancel step is "drag", never a commit
    const d = dragTo(startDrag(n("n1"), 100, 100), 160, 130);
    expect(dragMoves(d)).not.toBeNull();
    expect(escapeStep({ ...base, dragging: d.moved, selected: 1 })).toBe("drag");
    // a press that has not travelled past the click threshold is no drag: Esc then clears the selection
    const click = dragTo(startDrag(n("n1"), 100, 100), 101, 100);
    expect(dragMoves(click)).toBeNull();
    expect(escapeStep({ ...base, dragging: click.moved, selected: 1 })).toBe("selection");
  });
});

describe("cursors and selection frame", () => {
  test("grab over an element, crosshair on empty canvas, grabbing while dragging, copy over a drop target", () => {
    expect(cursorFor({ dragging: false, overDropTarget: false, overElement: true })).toBe("grab");
    expect(cursorFor({ dragging: false, overDropTarget: false, overElement: false })).toBe("crosshair");
    expect(cursorFor({ dragging: true, overDropTarget: false, overElement: true })).toBe("grabbing");
    expect(cursorFor({ dragging: true, overDropTarget: true, overElement: true })).toBe("copy");
  });

  test("a multi-selection is one bounding box with the count", () => {
    const f = selectionFrame([
      { id: "a", x: 10, y: 20, w: 100, h: 50 },
      { id: "b", x: 200, y: 5, w: 40, h: 40 },
    ]);
    expect(f).toEqual({ box: { id: "selection", x: 10, y: 5, w: 230, h: 65 }, count: 2 });
    expect(selectionFrame([])).toBeNull();
    expect(selectionFrame([{ id: "a", x: 1, y: 2, w: 3, h: 4 }])?.count).toBe(1);
  });
});

describe("keymap table and the shortcut sheet", () => {
  const ALL: KeyAction["action"][] = ["tool", "delete", "nudge", "group-row", "undo", "redo", "palette", "escape", "help"];

  test("every key binding fires its own action for each of its sample events", () => {
    for (const b of KEYMAP.filter((x) => x.match)) {
      expect(b.sample?.length).toBeGreaterThan(0);
      for (const e of b.sample as KeyLike[]) expect(matchKey(e)?.action, `${b.keys}: ${e.key}`).toBe(b.action);
    }
  });

  test("every action the handlers switch on has a row in the table, and the sheet lists every row", () => {
    for (const a of ALL) expect(KEYMAP.some((b) => b.action === a && b.match), a).toBe(true);
    const rows = shortcutRows();
    expect(rows.length).toBe(KEYMAP.length);
    for (const b of KEYMAP) expect(rows.some((r) => r.keys === b.keys && r.label === b.label)).toBe(true);
    for (const needle of ["Delete", "Arrow keys", "Ctrl/Cmd+G", "Ctrl/Cmd+Z", "Esc", "?", "Shift+click", "Alt+drag", "Double-click"]) {
      expect(rows.some((r) => r.keys.includes(needle)), needle).toBe(true);
    }
  });

  test("keys not in the table, and modified arrows, trigger nothing", () => {
    const mk = (key: string, m: Partial<KeyLike> = {}): KeyLike => ({ key, metaKey: false, ctrlKey: false, shiftKey: false, altKey: false, ...m });
    expect(matchKey(mk("a"))).toBeNull();
    expect(matchKey(mk("ArrowLeft", { ctrlKey: true }))).toBeNull();
    expect(matchKey(mk("Delete", { metaKey: true }))).toBeNull();
    expect(matchKey(mk("z", { ctrlKey: true, altKey: true }))).toBeNull();
  });
});

describe("drop ghost (T24)", () => {
  const sc = { width: 1000, height: 700, items: [], zones: [] } as unknown as SceneJson;
  test("a dropped box shows a ghost at exactly the place the node will be added, labelled with its title", () => {
    const ops = dropOps(sc, { type: "shape", kind: "box", title: "Box" }, 500, 300);
    const add = ops[0] as { x: number; y: number; w: number; h: number };
    expect(ghostOf(ops)).toEqual({ x: add.x, y: add.y, w: add.w, h: add.h, label: "New box" });
  });
  test("a zone ghost is the zone rectangle and a row ghost spans both boxes", () => {
    expect(ghostOf(dropOps(sc, { type: "zone", title: "Zone" }, 100, 100))).toEqual({ x: 100, y: 100, w: 600, h: 400, label: "Zone" });
    const g = ghostOf(dropOps(sc, { type: "row", title: "Row" }, 500, 300))!;
    expect(g.w).toBe(220 * 2 + 20);
    expect(g.h).toBe(96);
  });
  test("operations that add nothing give no ghost", () => {
    expect(ghostOf([{ op: "delete", id: "a" } as never])).toBeNull();
  });
});

describe("editor icons (T25)", () => {
  test("every shape kind, container, tool and toolbar action has an icon", () => {
    for (const name of [...SHAPE_KINDS, ...CONTAINER_ICON_NAMES, ...TOOLS.map((t) => t.id), ...ACTIONS.map((a) => a.id), ...QUICK_ACTIONS.map((q) => q.id)]) expect(hasIcon(name)).toBe(true);
  });
  test("ICON_NAMES lists exactly those names", () => {
    expect(new Set(ICON_NAMES)).toEqual(new Set([...SHAPE_KINDS, ...CONTAINER_ICON_NAMES, ...TOOLS.map((t) => t.id), ...ACTIONS.map((a) => a.id), ...QUICK_ACTIONS.map((q) => q.id)]));
  });
  test("a palette item maps to an icon name; an icon-pack item to none", () => {
    expect(iconNameOf({ type: "zone", title: "Zone" })).toBe("zone");
    expect(iconNameOf({ type: "row", title: "Row" })).toBe("row");
    expect(iconNameOf({ type: "shape", kind: "diamond", title: "Diamond" })).toBe("diamond");
    expect(iconNameOf({ type: "icon", pack: "aws", name: "s3", ref: "aws:s3", title: "S3", aliases: [] })).toBeNull();
    for (const kind of SHAPE_KINDS) expect(hasIcon(iconNameOf({ type: "shape", kind, title: kind })!)).toBe(true);
  });
  test("tool keys are single lowercase letters and unique", () => {
    const keys = TOOLS.map((t) => t.key);
    expect(new Set(keys).size).toBe(keys.length);
    for (const k of keys) expect(k).toMatch(/^[a-z]$/);
  });
});

describe("toolbar tools (T26): canvas-editor EDG-01..03", () => {
  const at = (x: number, y: number) => ({ x, y });
  const add = (ops: ReturnType<typeof placeOps>["ops"]) => ops[0] as { op: string; id: string; title?: string; kind?: string; x: number; y: number; w: number; h: number; label?: string };

  test("a click with Box adds the default box centred on the point, snapped, outside any zone", () => {
    const p = placeOps(zscene, "box", at(700, 600), at(702, 601));
    expect(p.ops).toHaveLength(1);
    expect(add(p.ops)).toMatchObject({ op: "add_node", title: "New box", kind: "box", x: 590, y: 550, w: 220, h: 96 });
    expect(p.edit).toBe(false);
  });

  test("a click inside a zone puts the new box in the innermost zone", () => {
    const p = placeOps(zscene, "box", at(200, 200), at(200, 200));
    expect(p.ops[1]).toEqual({ op: "reparent", id: p.id, parent: "inner" });
  });

  test("a drag with Box adds the drawn rectangle snapped, whichever way it is dragged", () => {
    const forward = placeOps(zscene, "box", at(414, 543), at(606, 628));
    const backward = placeOps(zscene, "box", at(606, 628), at(414, 543));
    expect(add(forward.ops)).toMatchObject({ x: 410, y: 540, w: 200, h: 90 });
    expect(add(backward.ops)).toMatchObject({ x: 410, y: 540, w: 200, h: 90 });
  });

  test("a drawn rectangle is never smaller than the tool's minimum and stays on the canvas", () => {
    expect(add(placeOps(zscene, "box", at(100, 100), at(115, 110)).ops)).toMatchObject({ x: 100, y: 100, w: 40, h: 30 });
    expect(add(placeOps(zscene, "zone", at(100, 100), at(115, 110)).ops)).toMatchObject({ w: 80, h: 60 });
    const edge = add(placeOps(zscene, "box", at(1290, 790), at(1400, 900)).ops);
    expect(edge.x + edge.w).toBeLessThanOrEqual(zscene.width);
    expect(edge.y + edge.h).toBeLessThanOrEqual(zscene.height);
  });

  test("a press that moves less than the click slop is a click", () => {
    const tiny = placeOps(zscene, "box", at(700, 600), at(700 + CLICK_SLOP - 1, 600));
    expect(add(tiny.ops)).toMatchObject({ w: 220, h: 96 });
    const drag = placeOps(zscene, "box", at(700, 600), at(700 + CLICK_SLOP, 600));
    expect(add(drag.ops).w).not.toBe(220);
  });

  test("Text adds a text-kind node and asks for the inline editor; Box and Zone do not", () => {
    const t = placeOps(zscene, "text", at(700, 600), at(700, 600));
    expect(add(t.ops)).toMatchObject({ op: "add_node", kind: "text", title: "New text" });
    expect(t.edit).toBe(true);
    expect(placeOps(zscene, "box", at(700, 600), at(700, 600)).edit).toBe(false);
    expect(placeOps(zscene, "zone", at(700, 600), at(700, 600)).edit).toBe(false);
  });

  test("the inline editor of a placed Text uses the placed box once the scene holds the item, even without a node box", () => {
    const t = placeOps(zscene, "text", at(700, 600), at(700, 600));
    expect(editBoxOf(zscene, t)).toBeNull(); // not saved and rendered yet
    // a text node renders as a plain text item: no role, no size
    const withText: SceneJson = { ...zscene, items: [...zscene.items, { type: "text", id: t.id, x: t.box.x, y: t.box.y }] };
    expect(boxOf(withText, t.id)).toBeNull();
    expect(editBoxOf(withText, t)).toEqual(t.box);
    expect(t.box).toEqual({ id: t.id, x: 590, y: 550, w: 220, h: 96 });
  });

  test("Zone adds a zone: default size centred on a click, the drawn rectangle on a drag", () => {
    const c = placeOps(zscene, "zone", at(650, 400), at(650, 400));
    expect(add(c.ops)).toMatchObject({ op: "add_zone", label: "Zone", x: 350, y: 200, w: 600, h: 400 });
    expect(add(c.ops).id).toBe(c.id);
    const d = placeOps(zscene, "zone", at(100, 600), at(400, 780));
    expect(add(d.ops)).toMatchObject({ op: "add_zone", x: 100, y: 600, w: 300, h: 180 });
  });

  test("new ids avoid the ones in the scene", () => {
    const first = placeOps(zscene, "box", at(700, 600), at(700, 600)).id;
    const withIt: SceneJson = { ...zscene, items: [...zscene.items, shape(first, "node", 0, 0, 10, 10)] };
    expect(placeOps(withIt, "box", at(700, 600), at(700, 600)).id).not.toBe(first);
  });

  test("Connect from a node to another node sends Connect, again when the edge exists", () => {
    const want = [{ op: "connect", from: "n1", to: "n2" }];
    expect(connectOps(zscene, "n1", 100, 130)).toEqual(want);
    expect(connectOps(zscene, "n1", 100, 130)).toEqual(want); // parallel edges are valid (EDG-04)
  });

  test("Connect adds nothing on empty canvas, on the same node, on a zone, or from something that is not a node", () => {
    expect(connectOps(zscene, "n1", 700, 700)).toBeNull(); // empty canvas
    expect(connectOps(zscene, "n1", 410, 110)).toBeNull(); // the same node
    expect(connectOps(zscene, "n1", 100, 330)).toBeNull(); // inside a zone only
    expect(connectOps(zscene, "n1", 1100, 100)).toBeNull(); // the empty zone
    expect(connectOps(zscene, "outer", 100, 130)).toBeNull(); // a zone is no source
    expect(connectOps(zscene, "missing", 100, 130)).toBeNull();
  });

  test("a tool returns to Select after use unless Shift keeps it", () => {
    for (const t of TOOLS) {
      expect(toolAfterUse(t.id, false)).toBe("select");
      expect(toolAfterUse(t.id, true)).toBe(t.id);
    }
    expect(TOOLS.filter((t) => isPlaceTool(t.id)).map((t) => t.id)).toEqual(["box", "text", "zone"]);
  });

  test("the keymap holds the key of every tool, and the sheet lists them", () => {
    const mk = (key: string, m: Partial<KeyLike> = {}): KeyLike => ({ key, metaKey: false, ctrlKey: false, shiftKey: false, altKey: false, ...m });
    for (const t of TOOLS) {
      expect(matchKey(mk(t.key))).toEqual({ action: "tool", tool: t.id });
      expect(matchKey(mk(t.key.toUpperCase(), { shiftKey: true }))).toEqual({ action: "tool", tool: t.id });
      expect(matchKey(mk(t.key, { ctrlKey: true }))?.action).not.toBe("tool");
      expect(shortcutRows().some((r) => r.keys === t.key.toUpperCase() && r.label.startsWith(t.label)), t.id).toBe(true);
    }
    expect(TOOLS.map((t) => t.key)).toEqual(["v", "h", "b", "t", "z", "c"]);
  });
});

describe("palette categories (T27): canvas-editor PAL-01, PAL-06", () => {
  const icons: IconEntry[] = [
    { pack: "gcp", name: "bigquery", aliases: [] },
    { pack: "aws", name: "amazon-s3", aliases: ["bucket"] },
    { pack: "aws", name: "lambda", aliases: [] },
  ];
  const corpus = buildCorpus(icons);
  const titles = (items: { title: string }[]) => items.map((i) => i.title);

  test("Zone, Box, Text, Row, Column and Note are Basics, in that order; the other shape kinds are Shapes", () => {
    const [basics, shapes] = categorize(corpus.items);
    expect(basics.title).toBe("Basics");
    expect(titles(basics.items)).toEqual(["Box", "Text", "Zone", "Row", "Column", "Note"]);
    expect(shapes.title).toBe("Shapes");
    expect(titles(shapes.items)).toEqual(titles(BUILTINS.filter((b) => b.type === "shape" && !["box", "text", "note"].includes(b.kind))));
    expect(shapes.items.every((i) => i.type === "shape")).toBe(true);
  });

  test("icons sit under their own pack, one category per pack, after Basics and Shapes and sorted by pack name", () => {
    const cats = categorize(corpus.items);
    expect(cats.map((c) => c.id)).toEqual(["basics", "shapes", "pack:aws", "pack:gcp"]);
    expect(titles(cats[2].items)).toEqual(["Amazon S3", "Lambda"]);
    expect(titles(cats[3].items)).toEqual(["Bigquery"]);
    expect(cats.reduce((n, c) => n + c.items.length, 0)).toBe(corpus.items.length);
  });

  test("a category with nothing in it is left out", () => {
    expect(categorize(buildCorpus([]).items).map((c) => c.id)).toEqual(["basics", "shapes"]);
    expect(categorize([]).length).toBe(0);
  });

  test("a search hit knows its category (the tag on its row)", () => {
    for (const hit of search(corpus, "bucket")) expect(categoryOf(hit)).toEqual({ id: "pack:aws", title: "aws" });
    expect(categoryOf({ type: "shape", kind: "diamond", title: "Diamond" })).toEqual({ id: "shapes", title: "Shapes" });
    expect(categoryOf({ type: "shape", kind: "note", title: "Note" }).id).toBe("basics");
    expect(categoryOf({ type: "zone", title: "Zone" }).id).toBe("basics");
  });

  test("rows: a header per category, items only under an open one; packs start collapsed", () => {
    const cats = categorize(corpus.items);
    const rows = paletteRows(cats, defaultCollapsed);
    expect(rows.filter((r) => r.type === "header").map((r) => r.type === "header" && [r.cat.id, r.collapsed])).toEqual([
      ["basics", false],
      ["shapes", false],
      ["pack:aws", true],
      ["pack:gcp", true],
    ]);
    expect(rows.filter((r) => r.type === "item").length).toBe(cats[0].items.length + cats[1].items.length);
    const open = paletteRows(cats, (id) => id !== "pack:aws");
    expect(open.filter((r) => r.type === "item").map((r) => r.type === "item" && r.item.title)).toEqual(["Amazon S3", "Lambda"]);
    expect(open.filter((r) => r.type === "header").every((r) => r.type === "header" && r.collapsed === (r.cat.id !== "pack:aws"))).toBe(true);
    expect(open[0].type === "header" && open[0].cat.items.length).toBe(6); // the header carries the count
  });

  test("the collapsed state round-trips through storage", () => {
    const data = new Map<string, string>();
    const store = { getItem: (k: string) => data.get(k) ?? null, setItem: (k: string, v: string) => void data.set(k, v) };
    expect(readCollapsed(store)).toEqual({});
    writeCollapsed({ basics: true, "pack:aws": false }, store);
    expect(readCollapsed(store)).toEqual({ basics: true, "pack:aws": false });
  });

  test("storage that throws, or holds something else, gives the defaults and never throws", () => {
    const bad = {
      getItem: () => {
        throw new Error("denied");
      },
      setItem: () => {
        throw new Error("denied");
      },
    };
    expect(readCollapsed(bad)).toEqual({});
    expect(() => writeCollapsed({ basics: true }, bad)).not.toThrow();
    expect(readCollapsed(null)).toEqual({});
    for (const raw of ["not json", "[1,2]", "42", "null", '{"a":"yes","b":true}']) {
      const s = { getItem: (k: string) => (k === PALETTE_COLLAPSED_KEY ? raw : null), setItem: () => undefined };
      const got = readCollapsed(s);
      expect(Object.values(got).every((v) => typeof v === "boolean")).toBe(true);
    }
    expect(readCollapsed({ getItem: () => '{"a":"yes","b":true}', setItem: () => undefined })).toEqual({ b: true });
  });
});

describe("Zones category and the zone style picker (T32)", () => {
  const style = (name: string, icon: string | null = null, stroke: string | null = "#123456", dashed = false) => ({ name, icon, fill: null, stroke, label: "#000000", dashed });
  // as `/api/zone-styles` lists them: theme order, every zone style including the non-provider and alias ones
  const styles = [
    style("soft"),
    style("warning"),
    style("aws-cloud", "aws:group-aws-cloud"),
    style("aws-vpc", "aws:group-virtualprivatecloud-vpc"),
    style("aws-subnet", "aws:group-privatesubnet"),
    style("aws-private-subnet", "aws:group-privatesubnet"),
    style("azure-subscription", "azure:subscriptions"),
    style("azure-resource-group", "azure:resource-groups", "#50A0DC", true),
    style("gcp-project", "gcp:project"),
    style("gcp-vpc", "gcp:virtual-private-cloud", "#4285F4", true),
    style("k8s-namespace", "k8s:ns", "#326CE5", true),
  ];
  const corpus = buildCorpus([{ pack: "aws", name: "amazon-s3", aliases: [] }], styles);
  const zoneItems = (q: string) => search(corpus, q).filter((i) => i.type === "zoneStyle");
  const titleOf = (i: { title: string }) => i.title;

  test("only provider styles become items, grouped AWS, Azure, Google Cloud, Kubernetes, the older alias left out", () => {
    const items = zoneStyleItems(styles);
    expect(items.map((i) => i.type === "zoneStyle" && `${i.provider}:${i.style}`)).toEqual([
      "AWS:aws-cloud",
      "AWS:aws-vpc",
      "AWS:aws-private-subnet",
      "Azure:azure-subscription",
      "Azure:azure-resource-group",
      "Google Cloud:gcp-project",
      "Google Cloud:gcp-vpc",
      "Kubernetes:k8s-namespace",
    ]);
    expect(items.map(titleOf)).toEqual(["AWS Cloud", "VPC", "Private subnet", "Subscription", "Resource group", "Project", "VPC network", "Namespace"]);
  });

  test("each item carries its real header icon ref and its colours", () => {
    const vpc = zoneStyleItems(styles).find((i) => i.type === "zoneStyle" && i.style === "aws-vpc");
    expect(vpc).toMatchObject({ icon: "aws:group-virtualprivatecloud-vpc", stroke: "#123456", dashed: false });
    const rg = zoneStyleItems(styles).find((i) => i.type === "zoneStyle" && i.style === "azure-resource-group");
    expect(rg).toMatchObject({ icon: "azure:resource-groups", stroke: "#50A0DC", dashed: true });
  });

  test("Zones comes right after Basics, with the generic Zone first and Basics keeping its Zone", () => {
    const cats = categorize(corpus.items);
    expect(cats.map((c) => c.id)).toEqual(["basics", "zones", "shapes", "pack:aws"]);
    expect(cats[1].items[0]).toEqual({ type: "zone", title: "Zone" });
    expect(cats[1].items.slice(1).every((i) => i.type === "zoneStyle")).toBe(true);
    expect(cats[0].items.map(titleOf)).toContain("Zone");
  });

  test("without zone styles there is no Zones category", () => {
    expect(categorize(buildCorpus([], []).items).map((c) => c.id)).toEqual(["basics", "shapes"]);
  });

  test("rows: the generic Zone, then a sub-header per provider before its items", () => {
    const rows = paletteRows(categorize(corpus.items), () => false);
    const at = rows.findIndex((r) => r.type === "header" && r.cat.id === "zones");
    const zoneRows = rows.slice(at + 1, rows.findIndex((r, i) => i > at && r.type === "header"));
    expect(zoneRows.map((r) => (r.type === "subheader" ? `# ${r.title}` : r.type === "item" ? r.item.title : "?"))).toEqual([
      "Zone",
      "# AWS",
      "AWS Cloud",
      "VPC",
      "Private subnet",
      "# Azure",
      "Subscription",
      "Resource group",
      "# Google Cloud",
      "Project",
      "VPC network",
      "# Kubernetes",
      "Namespace",
    ]);
    const closed = paletteRows(categorize(corpus.items), (id) => id === "zones");
    expect(closed.some((r) => r.type === "subheader")).toBe(false);
  });

  test("search finds the items by name: vpc, subscription, project, namespace", () => {
    expect(zoneItems("vpc").map(titleOf).sort()).toEqual(["VPC", "VPC network"]);
    expect(zoneItems("subscription").map(titleOf)).toEqual(["Subscription"]);
    expect(zoneItems("project").map(titleOf)).toEqual(["Project"]);
    expect(zoneItems("namespace").map(titleOf)).toEqual(["Namespace"]);
    expect(zoneItems("aws").length).toBeGreaterThanOrEqual(3); // by provider name too
    for (const hit of zoneItems("vpc")) expect(categoryOf(hit)).toEqual({ id: "zones", title: "Zones" });
  });

  test("dropping a zone style adds a zone with that style, its title as label, placed like a plain zone", () => {
    const item = zoneStyleItems(styles).find((i) => i.type === "zoneStyle" && i.style === "aws-vpc")!;
    expect(dropOps(zscene, item, 100, 600)).toEqual([{ op: "add_zone", id: "vpc", label: "VPC", style: "aws-vpc", x: 100, y: 400, w: 600, h: 400 }]);
    const plain = dropOps(zscene, { type: "zone", title: "Zone" }, 100, 600)[0];
    expect("style" in plain).toBe(false);
    const again = dropOps({ ...zscene, zones: [...(zscene.zones ?? []), { id: "vpc", shape_id: "zv", children: [] }] }, item, 0, 0)[0] as { id: string };
    expect(again.id).toBe("vpc-2");
  });

  test("the drop ghost of a styled zone is the zone rectangle", () => {
    const item = zoneStyleItems(styles)[0];
    const ops = dropOps(zscene, item, 100, 100);
    expect(ghostOf(ops)).toMatchObject({ x: 100, y: 100, w: 600, h: 400, label: "AWS Cloud" });
  });

  test("the Zone tool still adds the generic zone", () => {
    const op = placeOps(zscene, "zone", { x: 650, y: 400 }, { x: 650, y: 400 }).ops[0];
    expect(op.op).toBe("add_zone");
    expect("style" in op).toBe(false);
  });

  test("the picker sends set_zone_style for the zone", () => {
    expect(zoneStyleOps("outer", "azure-vnet")).toEqual([{ op: "set_zone_style", id: "outer", style: "azure-vnet" }]);
    expect(zoneStyleOps("outer", "soft")).toEqual([{ op: "set_zone_style", id: "outer", style: "soft" }]);
  });

  test("every provider zone style of the theme has a palette title", () => {
    for (const name of Object.keys(ZONE_TITLES)) expect(/^(aws|azure|gcp|k8s)-/.test(name), name).toBe(true);
    expect(Object.keys(ZONE_TITLES)).toHaveLength(25);
  });
});
