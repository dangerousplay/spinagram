// The properties panel's logic (inspector iteration T41): the field table, what each field commit sends, what a
// multi-selection shares, and the quick actions. Run: `bun test`.
import { describe, expect, test } from "bun:test";
import { readFileSync } from "node:fs";
import { hasIcon } from "./icons";
import { DUPLICATE_OFFSET, FIELDS, QUICK_ACTIONS, currentValue, fieldOps, fieldsFor, quickActions, quickOps, rawValue, type Field } from "./props";
import type { SceneJson, Sel } from "./scene";

const py = (file: string) => readFileSync(new URL(`../../../src/spinagram/${file}`, import.meta.url), "utf8");
const pySet = (src: string, name: string): string[] => [...(src.match(new RegExp(`${name} = \\{([^}]*)\\}`))?.[1] ?? "").matchAll(/"([^"]+)"/g)].map((m) => m[1]);
const pyFields = (src: string, cls: string): string[] => {
  const body = src.split(new RegExp(`^class ${cls}:`, "m"))[1]?.split(/^(?:@dataclass|class )/m)[0] ?? "";
  return [...body.matchAll(/^    (\w+):/gm)].map((m) => m[1]);
};

describe("the field table matches the loader", () => {
  const loader = py("yaml_io.py");
  const model = py("model.py");
  const nodeKeys = new Set([...pySet(loader, "_NODE_KEYS"), ...pySet(loader, "_NODE_EXTRA")]);
  const keys = (owner: keyof typeof FIELDS) => FIELDS[owner].filter((f) => !f.readonly).map((f) => f.key);
  // the YAML key `class` is the model's `cls`
  const model_ = (k: string) => (k === "class" ? "cls" : k);

  test("every node field is a key the YAML loader accepts for a node", () => {
    expect(nodeKeys.size).toBeGreaterThan(20); // the loader's table was read
    for (const k of keys("node")) expect(nodeKeys.has(k)).toBe(true);
  });

  test("every zone field is a field of the model's Zone, every edge field one of its Edge", () => {
    const zone = pyFields(model, "Zone");
    const edge = pyFields(model, "Edge");
    expect(zone).toContain("label");
    expect(edge).toContain("route");
    for (const k of keys("zone")) expect(zone).toContain(model_(k));
    for (const k of keys("edge").filter((k) => k !== "from" && k !== "to")) expect(edge).toContain(model_(k));
    expect(edge).toContain("src"); // `from` and `to` are the loader's names for these
    expect(edge).toContain("dst");
  });

  test("the geometry fields are the ones the loader reads as x, y, w, h", () => {
    for (const f of FIELDS.node.filter((f) => f.geometry)) expect(nodeKeys.has(f.key)).toBe(true);
    expect(FIELDS.node.filter((f) => f.geometry).map((f) => f.key)).toEqual(["x", "y", "w", "h"]);
    expect(FIELDS.zone.filter((f) => f.geometry).map((f) => f.key)).toEqual(["x", "y", "w", "h"]);
  });
});

const scene = {
  width: 1000,
  height: 800,
  items: [
    { type: "shape", id: "z0", role: "zone", x: 0, y: 0, w: 600, h: 500 },
    { type: "shape", id: "z1", role: "zone", x: 700, y: 0, w: 250, h: 300 },
    { type: "shape", id: "a", role: "node", x: 100, y: 100, w: 200, h: 100 },
    { type: "shape", id: "b", role: "node", x: 800, y: 100, w: 100, h: 100 },
    { type: "shape", id: "c", role: "node", x: 150, y: 600, w: 100, h: 100 },
    { type: "shape", id: "d", role: "node", x: 200, y: 300, w: 100, h: 50 }, // inside vpc's area, not in its children
    { type: "shape", id: "p", role: "node", x: 100, y: 400, w: 100, h: 60 },
    { type: "shape", id: "q", role: "node", x: 250, y: 400, w: 100, h: 60 },
    { type: "connector", id: "e0", points: [[300, 150], [800, 150]], src: { shape_id: "a", target: "node" }, dst: { shape_id: "b", target: "node" } },
    { type: "connector", id: "e1", points: [[0, 0], [5, 5]], src: { shape_id: "a", target: "node" }, dst: { shape_id: "z1", target: "zone" } },
  ],
  zones: [
    { id: "vpc", shape_id: "z0", children: ["a", "p", "q"] },
    { id: "app", shape_id: "z1", children: ["b"] },
  ],
  containers: [{ id: "row0", axis: "row", members: ["p", "q"], box: [100, 400, 250, 60] }],
} as unknown as SceneJson;

const node = (id: string): Sel => ({ id, kind: "node" });
const edge = (id: string): Sel => ({ id, kind: "edge" });
const zone = (id: string): Sel => ({ id, kind: "zone" });
const field = (owner: keyof typeof FIELDS, key: string): Field => FIELDS[owner].find((f) => f.key === key)!;
const ok = (r: ReturnType<typeof fieldOps>) => (r && "ops" in r ? r.ops : r);

describe("what a field commit sends", () => {
  test("a text field sets the key; blank clears it with null", () => {
    expect(ok(fieldOps(scene, node("a"), field("node", "title"), "Orders API", "Orders"))).toEqual([{ op: "set_props", id: "a", props: { title: "Orders API" } }]);
    expect(ok(fieldOps(scene, node("a"), field("node", "class"), "app-tier", ""))).toEqual([{ op: "set_props", id: "a", props: { class: "app-tier" } }]);
    expect(ok(fieldOps(scene, node("a"), field("node", "text"), "  ", "ECS"))).toEqual([{ op: "set_props", id: "a", props: { text: null } }]);
    expect(ok(fieldOps(scene, zone("vpc"), field("zone", "label"), "Prod", "VPC"))).toEqual([{ op: "set_props", id: "vpc", props: { label: "Prod" } }]);
  });

  test("an unchanged value, and the id, send nothing", () => {
    expect(fieldOps(scene, node("a"), field("node", "title"), "Same", "Same")).toBeNull();
    expect(fieldOps(scene, node("a"), field("node", "id"), "other", "a")).toBeNull();
  });

  test("a select sets the key, or clears it when blank; a checkbox sets true and clears on unchecked", () => {
    expect(ok(fieldOps(scene, edge("e0"), field("edge", "route"), "ortho", ""))).toEqual([{ op: "set_props", id: "e0", props: { route: "ortho" } }]);
    expect(ok(fieldOps(scene, edge("e0"), field("edge", "arrow"), "", "both"))).toEqual([{ op: "set_props", id: "e0", props: { arrow: null } }]);
    expect(ok(fieldOps(scene, edge("e0"), field("edge", "dashed"), true, false))).toEqual([{ op: "set_props", id: "e0", props: { dashed: true } }]);
    expect(ok(fieldOps(scene, edge("e0"), field("edge", "dashed"), false, true))).toEqual([{ op: "set_props", id: "e0", props: { dashed: null } }]);
    expect(ok(fieldOps(scene, node("a"), field("node", "kind"), "diamond", ""))).toEqual([{ op: "set_props", id: "a", props: { kind: "diamond" } }]);
  });

  test("the icon field writes the pack:name ref and clears with null", () => {
    expect(ok(fieldOps(scene, node("a"), field("node", "icon"), "aws:amazon-s3", ""))).toEqual([{ op: "set_props", id: "a", props: { icon: "aws:amazon-s3" } }]);
    expect(ok(fieldOps(scene, node("a"), field("node", "icon"), "", "aws:amazon-s3"))).toEqual([{ op: "set_props", id: "a", props: { icon: null } }]);
  });

  test("geometry goes through move, move_zone and resize with the other values kept", () => {
    expect(ok(fieldOps(scene, node("a"), field("node", "x"), "150", "100"))).toEqual([{ op: "move", id: "a", x: 150, y: 100 }]);
    expect(ok(fieldOps(scene, node("a"), field("node", "y"), "90", "100"))).toEqual([{ op: "move", id: "a", x: 100, y: 90 }]);
    expect(ok(fieldOps(scene, node("a"), field("node", "w"), "240", "200"))).toEqual([{ op: "resize", id: "a", w: 240, h: 100 }]);
    expect(ok(fieldOps(scene, node("a"), field("node", "h"), "120", "100"))).toEqual([{ op: "resize", id: "a", w: 200, h: 120 }]);
    expect(ok(fieldOps(scene, zone("vpc"), field("zone", "x"), "40", "0"))).toEqual([{ op: "move_zone", id: "vpc", x: 40, y: 0 }]);
    expect(ok(fieldOps(scene, zone("vpc"), field("zone", "h"), "520", "500"))).toEqual([{ op: "resize", id: "vpc", w: 600, h: 520 }]);
  });

  test("a bad geometry value is an error and sends nothing", () => {
    expect(fieldOps(scene, node("a"), field("node", "x"), "abc", "100")).toEqual({ error: "X needs a number" });
    expect(fieldOps(scene, node("a"), field("node", "y"), "", "100")).toEqual({ error: "Y needs a number" });
    expect(fieldOps(scene, node("a"), field("node", "w"), "0", "200")).toEqual({ error: "A size must be at least 1" });
    expect(fieldOps(scene, node("p"), field("node", "x"), "10", "100")).toEqual({ error: "A row or column member is placed by its container" });
    expect(fieldOps(scene, node("a"), field("node", "x"), "100", "100")).toBeNull();
  });

  test("the ends of an edge reconnect; the zone style field sets the zone style", () => {
    expect(ok(fieldOps(scene, edge("e0"), field("edge", "to"), "c", "b"))).toEqual([{ op: "reconnect", id: "e0", to: "c" }]);
    expect(ok(fieldOps(scene, edge("e0"), field("edge", "from"), "c", "a"))).toEqual([{ op: "reconnect", id: "e0", from: "c" }]);
    expect(fieldOps(scene, edge("e0"), field("edge", "to"), "", "b")).toEqual({ error: "Choose a node" });
    expect(ok(fieldOps(scene, zone("vpc"), field("zone", "color"), "aws-vpc", "soft"))).toEqual([{ op: "set_zone_style", id: "vpc", style: "aws-vpc" }]);
    expect(ok(fieldOps(scene, zone("vpc"), field("zone", "color"), "", "aws-vpc"))).toEqual([{ op: "set_zone_style", id: "vpc", style: "soft" }]);
  });

  test("a checkbox compares as a boolean", () => {
    expect(rawValue(field("edge", "dashed"), "true")).toBe(true);
    expect(rawValue(field("edge", "dashed"), "")).toBe(false);
    expect(rawValue(field("node", "title"), "x")).toBe("x");
  });
});

describe("what a field shows", () => {
  test("a node: keys from its YAML entry, geometry from the scene", () => {
    const entry = "{id: a, title: \"Orders API\", class: app, icon: aws:s3, dashed: true, at: [100, 100, 200, 100]}";
    expect(currentValue(scene, node("a"), field("node", "title"), entry)).toBe("Orders API");
    expect(currentValue(scene, node("a"), field("node", "class"), entry)).toBe("app");
    expect(currentValue(scene, node("a"), field("node", "icon"), entry)).toBe("aws:s3");
    expect(currentValue(scene, node("a"), field("node", "text"), entry)).toBe("");
    expect(currentValue(scene, node("a"), field("node", "w"), entry)).toBe("200");
    expect(currentValue(scene, node("a"), field("node", "id"), entry)).toBe("a");
  });

  test("a zone's style defaults to soft; an edge's ends come from the scene and its keys from a mapping only", () => {
    expect(currentValue(scene, zone("vpc"), field("zone", "color"), "{id: vpc, label: VPC}")).toBe("soft");
    expect(currentValue(scene, zone("vpc"), field("zone", "color"), "{id: vpc, color: aws-vpc}")).toBe("aws-vpc");
    expect(currentValue(scene, edge("e0"), field("edge", "from"), "")).toBe("a");
    expect(currentValue(scene, edge("e1"), field("edge", "to"), "")).toBe(""); // a zone end is not a node
    expect(currentValue(scene, edge("e0"), field("edge", "label"), '"a -> b: reads"')).toBe("reads");
    expect(currentValue(scene, edge("e0"), field("edge", "route"), '"a -> b: route: fast"')).toBe(""); // not a key of a string edge
    expect(currentValue(scene, edge("e0"), field("edge", "route"), "{from: a, to: b, route: ortho}")).toBe("ortho");
    expect(currentValue(scene, edge("e0"), field("edge", "dashed"), "{from: a, to: b, dashed: true}")).toBe("true");
  });
});

describe("a multi-selection", () => {
  const keys = (sel: Sel[]) => fieldsFor(sel).map((f) => f.key);

  test("one element has every field of its kind", () => {
    expect(keys([node("a")])).toEqual(["id", "title", "text", "icon", "kind", "class", "x", "y", "w", "h"]);
    expect(keys([edge("e0")])).toEqual(["id", "from", "to", "label", "route", "dashed", "color", "class", "arrow"]);
  });

  test("several nodes share their content and size, not id or position", () => {
    expect(keys([node("a"), node("b")])).toEqual(["title", "text", "icon", "kind", "class", "w", "h"]);
  });

  test("a node and a zone share class and size only; with an edge, class only; a container has none", () => {
    expect(keys([node("a"), zone("vpc")])).toEqual(["class", "w", "h"]);
    expect(keys([node("a"), zone("vpc"), edge("e0")])).toEqual(["class"]);
    expect(keys([edge("e0"), edge("e1")])).toEqual(["label", "route", "dashed", "color", "class", "arrow"]);
    expect(keys([{ id: "row0", kind: "container" }])).toEqual([]);
    expect(keys([node("a"), { id: "row0", kind: "container" }])).toEqual([]);
    expect(keys([])).toEqual([]);
  });

  test("committing a shared field sends one operation per selected element (one batch)", () => {
    const sel = [node("a"), node("b"), node("c")];
    const ops = sel.flatMap((s) => ok(fieldOps(scene, s, field("node", "class"), "app", "")) as unknown[]);
    expect(ops).toEqual([
      { op: "set_props", id: "a", props: { class: "app" } },
      { op: "set_props", id: "b", props: { class: "app" } },
      { op: "set_props", id: "c", props: { class: "app" } },
    ]);
  });
});

describe("quick actions", () => {
  test("every quick action has an icon", () => {
    for (const q of QUICK_ACTIONS) expect(hasIcon(q.id)).toBe(true);
  });

  test("which actions each selection shows", () => {
    const ids = (sel: Sel[]) => quickActions(scene, sel).map((q) => q.id);
    expect(ids([node("a")])).toEqual(["duplicate", "connect", "group-row", "group-column", "ungroup", "move-to-zone", "delete"]);
    expect(ids([zone("vpc")])).toEqual(["duplicate", "style", "delete"]);
    expect(ids([edge("e0")])).toEqual(["reverse", "parallel", "delete"]);
    expect(ids([{ id: "row0", kind: "container" }])).toEqual(["ungroup"]);
    expect(ids([node("a"), zone("vpc")])).toEqual(["duplicate", "delete"]);
    expect(ids([])).toEqual([]);
  });

  test("which of them can run", () => {
    const on = (sel: Sel[], id: string) => quickActions(scene, sel).find((q) => q.id === id)?.enabled;
    expect(on([node("a")], "group-row")).toBe(false); // needs two free nodes
    expect(on([node("a"), node("c")], "group-row")).toBe(true);
    expect(on([node("a"), node("p")], "group-row")).toBe(false); // p is already in a row
    expect(on([node("a"), node("c")], "connect")).toBe(false); // from one node only
    expect(on([node("a")], "ungroup")).toBe(false);
    expect(on([node("p")], "ungroup")).toBe(true); // its row
    expect(on([node("p")], "move-to-zone")).toBe(false);
    expect(on([edge("e1")], "parallel")).toBe(false); // an end is a zone
  });

  test("Duplicate sends one duplicate per node or zone, offset", () => {
    expect(quickOps(scene, "duplicate", [node("a"), zone("vpc")])).toEqual([
      { op: "duplicate", id: "a", dx: DUPLICATE_OFFSET, dy: DUPLICATE_OFFSET },
      { op: "duplicate", id: "vpc", dx: DUPLICATE_OFFSET, dy: DUPLICATE_OFFSET },
    ]);
  });

  test("Delete removes edges first, last to first, then the rest", () => {
    expect(quickOps(scene, "delete", [node("a"), edge("e0"), edge("e1")])).toEqual([
      { op: "delete", id: "e1" },
      { op: "delete", id: "e0" },
      { op: "delete", id: "a" },
    ]);
  });

  test("Group sends the free nodes ordered; Ungroup takes the container of a member or the container itself, once", () => {
    expect(quickOps(scene, "group-row", [node("c"), node("a")])).toEqual([{ op: "group", axis: "row", ids: ["a", "c"], gap: 20 }]);
    expect(quickOps(scene, "group-column", [node("c"), node("a")])).toEqual([{ op: "group", axis: "column", ids: ["a", "c"], gap: 20 }]);
    const ungroup = [{ op: "ungroup", id: "row0", boxes: { p: [100, 400, 100, 60], q: [250, 400, 100, 60] } }];
    expect(quickOps(scene, "ungroup", [node("p"), node("q")])).toEqual(ungroup);
    expect(quickOps(scene, "ungroup", [{ id: "row0", kind: "container" }])).toEqual(ungroup);
  });

  test("Move to zone reparents, and moves the node into the zone's area when it is outside it", () => {
    expect(quickOps(scene, "move-to-zone", [node("c")], "app")).toEqual([
      { op: "move", id: "c", x: 740, y: 80 },
      { op: "reparent", id: "c", parent: "app" },
    ]);
    // `a` is in vpc already; moving it to app puts it there
    expect(quickOps(scene, "move-to-zone", [node("a")], "app")?.map((o) => o.op)).toEqual(["move", "reparent"]);
    // a node whose centre is already inside the zone is only reparented
    expect(quickOps(scene, "move-to-zone", [node("d")], "vpc")).toEqual([{ op: "reparent", id: "d", parent: "vpc" }]); // inside it already: no move
    expect(quickOps(scene, "move-to-zone", [node("a")], "vpc")).toBeNull(); // already its child
    expect(quickOps(scene, "move-to-zone", [node("c")], null)).toBeNull(); // already at the top level
    expect(quickOps(scene, "move-to-zone", [node("b")], null)).toEqual([{ op: "reparent", id: "b", parent: null }]);
    expect(quickOps(scene, "move-to-zone", [node("p")], "app")).toBeNull(); // placed by its row
  });

  test("Reverse and Add a parallel edge send the edge's own ends", () => {
    expect(quickOps(scene, "reverse", [edge("e0")])).toEqual([{ op: "reverse", id: "e0" }]);
    expect(quickOps(scene, "parallel", [edge("e0")])).toEqual([{ op: "connect", from: "a", to: "b" }]);
    expect(quickOps(scene, "parallel", [edge("e1")])).toBeNull();
  });

  test("Add connection and Change style are not edits", () => {
    expect(quickOps(scene, "connect", [node("a")])).toBeNull();
    expect(quickOps(scene, "style", [zone("vpc")])).toBeNull();
  });
});
