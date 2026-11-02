// Selecting, relabelling, reconnecting and deleting edges on the canvas (inspector iteration T39; canvas-editor EDG-05
// and the user's request to select arrows, edit, add and delete them). Run: `bun test`.
import { describe, expect, test } from "bun:test";
import { deleteSelectionOps, reconnectOps, relabelOps } from "./ops";
import { edgeBox, edgePath, endHandleAt, hitEdge, pickAt, sceneEdges, type SceneJson } from "./scene";
import { edgeLabelOf } from "./srcmap";
import { connectSource } from "./tools";

const scene: SceneJson = {
  width: 800,
  height: 600,
  items: [
    { type: "shape", id: "zone-a", role: "zone", x: 0, y: 0, w: 800, h: 600 },
    { type: "shape", id: "a", role: "node", x: 0, y: 0, w: 100, h: 100 },
    { type: "shape", id: "b", role: "node", x: 300, y: 0, w: 100, h: 100 },
    { type: "shape", id: "c", role: "node", x: 300, y: 200, w: 100, h: 100 },
    // e0: a -> b, a straight line with a label pill on it
    { type: "connector", id: "e0", route: "poly", points: [[100, 50], [300, 50]], label: { x: 170, y: 40, w: 60, h: 20 }, src: { shape_id: "a", target: "node" }, dst: { shape_id: "b", target: "node" } },
    // e1: a -> c, down and across (a corner at 50,250)
    { type: "connector", id: "e1", route: "poly", points: [[50, 100], [50, 250], [300, 250]], src: { shape_id: "a", target: "node" }, dst: { shape_id: "c", target: "node" } },
    // e2: a curve from c to b
    { type: "connector", id: "e2", route: "curve", points: [[400, 250], [500, 150], [400, 50]], src: { shape_id: "c", target: "node" }, dst: { shape_id: "b", target: "node" } },
    { type: "connector", id: "bus-0", route: "poly", points: [[0, 500], [700, 500]] }, // not an edge of the spec
    { type: "shape", id: "e0-label", role: "pill", x: 170, y: 40, w: 60, h: 20 },
  ],
};

describe("edge hit-test", () => {
  test("a point on the line hits the edge, within 6 px", () => {
    expect(hitEdge(scene, 130, 50, 6)).toBe("e0");
    expect(hitEdge(scene, 130, 55, 6)).toBe("e0");
    expect(hitEdge(scene, 130, 57, 6)).toBeNull();
  });

  test("near a corner it hits, a little further off it does not", () => {
    expect(hitEdge(scene, 53, 253, 6)).toBe("e1"); // 4.2 px from the corner at 50,250
    expect(hitEdge(scene, 58, 258, 6)).toBeNull(); // 11 px
    expect(hitEdge(scene, 200, 247, 6)).toBe("e1"); // on the last segment
  });

  test("the label of an edge counts as the edge", () => {
    expect(hitEdge(scene, 200, 58, 6)).toBe("e0"); // 8 px off the line, but inside the label pill
    expect(hitEdge(scene, 200, 63, 6)).toBeNull(); // just below the pill
  });

  test("a curve is hit along its curve, not along its control polygon", () => {
    const e2 = scene.items.find((i) => i.id === "e2")!;
    const mid = edgePath(e2)[8]; // t = 0.5 of a quadratic: (450, 150)
    expect(mid).toEqual([450, 150]);
    expect(hitEdge(scene, 450, 150, 6)).toBe("e2");
    expect(hitEdge(scene, 500, 150, 6)).toBeNull(); // the control point itself is 50 px off the curve
  });

  test("far from every edge it misses, and connectors that are not edges of the spec are ignored", () => {
    expect(hitEdge(scene, 600, 400, 6)).toBeNull();
    expect(hitEdge(scene, 350, 500, 6)).toBeNull(); // on `bus-0`
    expect(sceneEdges(scene).map((e) => e.id)).toEqual(["e0", "e1", "e2"]);
  });

  test("a node wins a tie: at the point where the edge meets its node the press picks the node", () => {
    expect(hitEdge(scene, 100, 50, 6)).toBe("e0"); // the edge starts here ...
    expect(pickAt(scene, 100, 50, 6)).toEqual({ id: "a", kind: "node" }); // ... and so does the node's boundary
    expect(pickAt(scene, 150, 50, 6)).toEqual({ id: "e0", kind: "edge" });
  });

  test("an edge is picked before the zone behind it, and empty zone area picks nothing", () => {
    expect(pickAt(scene, 130, 50, 6)).toEqual({ id: "e0", kind: "edge" });
    expect(pickAt(scene, 600, 400, 6)).toBeNull(); // inside the zone, below its header, away from everything
  });

  test("the box of an edge spans its path and its label", () => {
    const e0 = sceneEdges(scene)[0];
    expect(edgeBox(e0)).toEqual({ id: "e0", x: 100, y: 40, w: 200, h: 20 });
  });
});

describe("edge operations", () => {
  test("Delete on an edge removes that edge by its id", () => {
    expect(deleteSelectionOps([{ id: "e1", kind: "edge" }])).toEqual([{ op: "delete", id: "e1" }]);
  });

  test("deleting several edges goes last to first so each id still names its edge", () => {
    const ops = deleteSelectionOps([{ id: "e0", kind: "edge" }, { id: "e2", kind: "edge" }, { id: "e1", kind: "edge" }]);
    expect(ops).toEqual([{ op: "delete", id: "e2" }, { op: "delete", id: "e1" }, { op: "delete", id: "e0" }]);
  });

  test("a mixed selection deletes edges first, then nodes; containers are left alone", () => {
    const ops = deleteSelectionOps([{ id: "b", kind: "node" }, { id: "e0", kind: "edge" }, { id: "row0", kind: "container" }]);
    expect(ops).toEqual([{ op: "delete", id: "e0" }, { op: "delete", id: "b" }]);
  });

  test("a label edit sets the label; blank text removes it", () => {
    expect(relabelOps("e0", "reads")).toEqual([{ op: "set_props", id: "e0", props: { label: "reads" } }]);
    expect(relabelOps("e0", "  trimmed ")).toEqual([{ op: "set_props", id: "e0", props: { label: "trimmed" } }]);
    expect(relabelOps("e0", "")).toEqual([{ op: "set_props", id: "e0", props: { label: null } }]);
    expect(relabelOps("e0", "   ")).toEqual([{ op: "set_props", id: "e0", props: { label: null } }]);
  });

  test("dropping the target end of an edge on another node reconnects that end", () => {
    expect(reconnectOps(scene, "e0", "to", 350, 250)).toEqual([{ op: "reconnect", id: "e0", to: "c" }]);
    expect(reconnectOps(scene, "e0", "from", 350, 250)).toEqual([{ op: "reconnect", id: "e0", from: "c" }]);
  });

  test("a release on empty space, on a zone, or on a node the edge already touches adds nothing", () => {
    expect(reconnectOps(scene, "e0", "to", 600, 400)).toBeNull(); // empty space (inside only the zone)
    expect(reconnectOps(scene, "e0", "to", 350, 50)).toBeNull(); // its own target
    expect(reconnectOps(scene, "e0", "to", 50, 50)).toBeNull(); // the node at its other end: a self-loop
    expect(reconnectOps(scene, "e0", "from", 50, 50)).toBeNull();
    expect(reconnectOps(scene, "nope", "to", 350, 250)).toBeNull();
  });

  test("the end handles are grabbed within a radius of the path's two ends", () => {
    const e0 = sceneEdges(scene)[0];
    expect(endHandleAt(e0, 104, 52, 10)).toBe("from");
    expect(endHandleAt(e0, 296, 48, 10)).toBe("to");
    expect(endHandleAt(e0, 200, 50, 10)).toBeNull();
  });

  test("Connect starts from the lone selected node (Add connection, or C with a node selected)", () => {
    expect(connectSource([{ id: "a", kind: "node" }])).toBe("a");
    expect(connectSource([{ id: "a", kind: "node" }, { id: "b", kind: "node" }])).toBeNull();
    expect(connectSource([{ id: "e0", kind: "edge" }])).toBeNull();
    expect(connectSource([])).toBeNull();
  });
});

describe("the label of an edge entry", () => {
  test("a string edge's label follows its colon, whatever the quoting", () => {
    expect(edgeLabelOf('"api -> db: reads"')).toBe("reads");
    expect(edgeLabelOf("'a -> b: x y'")).toBe("x y");
    expect(edgeLabelOf('"a <-> zone:z: tag"')).toBe("tag");
    expect(edgeLabelOf("a -> b")).toBe("");
    expect(edgeLabelOf('"a -> zone:z"')).toBe("");
  });

  test("a mapping's label is its label key, in flow or block form", () => {
    expect(edgeLabelOf("{from: db, to: cache, label: sync, route: ortho}")).toBe("sync");
    expect(edgeLabelOf("from: cache\n    to: api\n    label: back\n    dashed: true")).toBe("back");
    expect(edgeLabelOf("{from: a, to: b}")).toBe("");
  });
});
