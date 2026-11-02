// The element tree (inspector iteration T40; the user's request for an element tree, SYN-01/02 tree <-> canvas <-> code).
// Run: `bun test`.
import { describe, expect, test } from "bun:test";
import { ELEMENTS_DEFAULT, ELEMENTS_KEY, afterSelection, readElements, writeElements } from "./paletteState";
import type { SceneJson } from "./scene";
import { ancestorKeys, buildTree, filterTree, keyOf, revealSelection, selectFromRow, selectedKeys, visibleRows, type TreeNode } from "./tree";
import { hasIcon } from "./icons";
import { ACTIONS } from "./tools";
import { shortcutRows } from "./interaction";

const shape = (id: string, title: string, role = "node", icon?: string) => ({
  type: "shape", id, role, x: 0, y: 0, w: 10, h: 10, label: { blocks: [{ paragraphs: [title] }, { paragraphs: ["second block"] }] }, icon: icon ? { path: icon } : null,
});
const zoneShape = (k: number) => ({ type: "shape", id: `z${k}`, role: "zone", x: 0, y: 0, w: 10, h: 10 });
const zoneText = (k: number, text: string) => ({ type: "text", id: `z${k}-label`, block: { paragraphs: [text] } });
const zoneIcon = (k: number, path: string) => ({ type: "shape", id: `z${k}-icon`, role: "zone", icon: { path } });
const connector = (id: string, from: string, to: string, label?: string) => ({
  type: "connector",
  id,
  points: [[0, 0], [10, 10]],
  src: { shape_id: from, target: "node" },
  dst: { shape_id: to, target: "node" },
  label: label ? { x: 0, y: 0, w: 5, h: 5, label: { blocks: [{ paragraphs: [label] }] } } : null,
});

// cloud (z0) > [account (z1) > [cdn, vpc (z2) > [api, worker (column), db]], gw]; a free node `users`; a row of free nodes
const scene = {
  width: 100,
  height: 100,
  items: [
    zoneShape(0), zoneText(0, "AWS Cloud"), zoneIcon(0, "/icons/cloud.svg"),
    zoneShape(1), zoneText(1, "Account"),
    zoneShape(2), zoneText(2, "VPC"),
    shape("cdn", "CloudFront", "node", "/icons/cdn.svg"),
    shape("api", "Orders API"),
    shape("worker", "Billing worker"),
    shape("db", "Orders DB"),
    shape("gw", "Gateway"),
    shape("users", "Users"),
    shape("p", "Row item P"),
    shape("q", "Row item Q"),
    connector("e0", "users", "cdn", "HTTPS"),
    connector("e1", "api", "db"),
    { type: "connector", id: "bus-0", points: [[0, 0], [1, 1]] },
  ],
  zones: [
    { id: "cloud", shape_id: "z0", children: ["account", "gw"] },
    { id: "account", shape_id: "z1", children: ["cdn", "vpc"] },
    { id: "vpc", shape_id: "z2", children: ["api", "worker", "db"] },
  ],
  containers: [
    { id: "column0", axis: "column", members: ["api", "worker"], box: [0, 0, 10, 20] },
    { id: "row1", axis: "row", members: ["p", "q"], box: [0, 0, 20, 10] },
  ],
} as unknown as SceneJson;

const titles = (nodes: TreeNode[]): unknown[] => nodes.map((n) => (n.children.length ? [n.title, titles(n.children)] : n.title));

describe("the element tree", () => {
  const tree = buildTree(scene);

  test("zones nest by their children, a container sits in the zone that lists its members, with its members", () => {
    expect(titles(tree)).toEqual([
      ["AWS Cloud", [["Account", ["CloudFront", ["VPC", ["Orders DB", ["Column · 2 items", ["Orders API", "Billing worker"]]]]]], "Gateway"]],
      ["Row · 2 items", ["Row item P", "Row item Q"]],
      "Users",
      ["Edges · 2", ["Users → CloudFront (HTTPS)", "Orders API → Orders DB"]],
    ]);
  });

  test("rows carry their kind, id and key; the edges group lists the edges of the spec only", () => {
    const cloud = tree[0];
    expect([cloud.kind, cloud.id, cloud.key]).toEqual(["zone", "cloud", "zone:cloud"]);
    const edges = tree[tree.length - 1];
    expect([edges.kind, edges.children.map((e) => e.key)]).toEqual(["group", ["edge:e0", "edge:e1"]]);
    const column = cloud.children[0].children[1].children.find((n) => n.kind === "container")!;
    expect([column.key, column.iconName]).toEqual(["container:column0", "column"]);
  });

  test("a node and a zone show their own pack icon, others fall back to a built-in icon name", () => {
    expect(tree[0].iconPath).toBe("/icons/cloud.svg");
    expect(tree[0].children[0].children[0].iconPath).toBe("/icons/cdn.svg");
    const api = tree[0].children[0].children[1].children[1].children[0];
    expect([api.title, api.iconPath, api.iconName]).toEqual(["Orders API", null, "box"]);
    expect(tree[tree.length - 1].children[0].iconName).toBe("connect");
  });

  test("an element the scene draws no text for is listed by its id", () => {
    const bare = { ...scene, items: [{ type: "shape", id: "n1", role: "node" }, zoneShape(0)], zones: [{ id: "zz", shape_id: "z0", children: [] }], containers: [] } as unknown as SceneJson;
    expect(titles(buildTree(bare))).toEqual(["zz", "n1"]);
  });
});

describe("filtering", () => {
  const tree = buildTree(scene);

  test("a filter keeps the matches and the rows above them, nothing else", () => {
    expect(titles(filterTree(tree, "billing"))).toEqual([["AWS Cloud", [["Account", [["VPC", [["Column · 2 items", ["Billing worker"]]]]]]]]]);
  });

  test("it matches the id as well, ignoring case, and edges by their text", () => {
    expect(titles(filterTree(tree, "COLUMN0"))).toEqual([["AWS Cloud", [["Account", [["VPC", ["Column · 2 items"]]]]]]]);
    expect(titles(filterTree(tree, "https"))).toEqual([["Edges · 2", ["Users → CloudFront (HTTPS)"]]]);
  });

  test("the Edges group heading is not itself a match, a blank filter keeps everything and no match gives nothing", () => {
    expect(filterTree(tree, "edges")).toEqual([]);
    expect(filterTree(tree, "  ")).toBe(tree);
    expect(filterTree(tree, "zzz")).toEqual([]);
  });
});

describe("tree <-> canvas selection", () => {
  const tree = buildTree(scene);
  const row = (key: string): TreeNode => {
    const all = (l: TreeNode[]): TreeNode[] => l.flatMap((n) => [n, ...all(n.children)]);
    return all(tree).find((n) => n.key === key)!;
  };

  test("clicking a row selects exactly that element; Shift or Ctrl toggles it in the selection", () => {
    const api = row("node:api");
    expect(selectFromRow(api, [{ id: "db", kind: "node" }], false)).toEqual([{ id: "api", kind: "node" }]);
    expect(selectFromRow(api, [{ id: "db", kind: "node" }], true)).toEqual([{ id: "db", kind: "node" }, { id: "api", kind: "node" }]);
    expect(selectFromRow(api, [{ id: "api", kind: "node" }, { id: "db", kind: "node" }], true)).toEqual([{ id: "db", kind: "node" }]);
    expect(selectFromRow(row("edge:e1"), [], false)).toEqual([{ id: "e1", kind: "edge" }]);
    expect(selectFromRow(row("container:column0"), [], false)).toEqual([{ id: "column0", kind: "container" }]);
    expect(selectFromRow(row("zone:vpc"), [], false)).toEqual([{ id: "vpc", kind: "zone" }]);
  });

  test("the Edges heading selects nothing", () => {
    const cur = [{ id: "api", kind: "node" as const }];
    expect(selectFromRow(row("group:edges"), cur, false)).toBe(cur);
  });

  test("a canvas selection highlights the rows with those keys", () => {
    expect(selectedKeys([{ id: "api", kind: "node" }, { id: "e0", kind: "edge" }])).toEqual(new Set(["node:api", "edge:e0"]));
    expect(keyOf({ id: "cloud", kind: "zone" })).toBe("zone:cloud");
  });

  test("a canvas selection opens the collapsed rows above it, and only those", () => {
    const collapsed = new Set(["zone:cloud", "zone:account", "zone:vpc", "container:row1"]);
    const open = revealSelection(tree, [{ id: "worker", kind: "node" }], collapsed);
    expect(ancestorKeys(tree, "node:worker")).toEqual(["zone:cloud", "zone:account", "zone:vpc", "container:column0"]);
    expect(open).toEqual(new Set(["container:row1"])); // the row stays collapsed
  });

  test("collapsed rows hide their descendants", () => {
    const keys = visibleRows(tree, new Set(["zone:account"])).map((r) => r.node.key);
    expect(keys).toContain("zone:account");
    expect(keys).not.toContain("zone:vpc");
    expect(keys).toContain("node:gw");
    expect(visibleRows(tree, new Set()).find((r) => r.node.key === "node:worker")?.depth).toBe(4);
  });
});

describe("the Elements panel state", () => {
  const store = (initial: string | null) => {
    let v = initial;
    return { getItem: () => v, setItem: (_: string, x: string) => void (v = x) };
  };

  test("open and pinned round-trip through storage", () => {
    const st = store(null);
    expect(readElements(st)).toEqual({ open: false, pinned: false });
    writeElements({ open: true, pinned: true }, st);
    expect(st.getItem(ELEMENTS_KEY)).toBe('{"open":true,"pinned":true}');
    expect(readElements(st)).toEqual({ open: true, pinned: true });
  });

  test("a storage that throws, or holds anything else, gives closed and unpinned", () => {
    const broken = { getItem: () => { throw new Error("denied"); }, setItem: () => { throw new Error("denied"); } };
    expect(readElements(broken)).toBe(ELEMENTS_DEFAULT);
    expect(() => writeElements({ open: true, pinned: false }, broken)).not.toThrow();
    expect(readElements(store("not json"))).toBe(ELEMENTS_DEFAULT);
    expect(readElements(store('{"open":"yes","pinned":1}'))).toEqual({ open: false, pinned: false });
  });

  test("selecting an element opens the panel unless it is pinned", () => {
    expect(afterSelection({ open: false, pinned: false }, true)).toEqual({ open: true, pinned: false });
    expect(afterSelection({ open: false, pinned: true }, true)).toEqual({ open: false, pinned: true }); // pinned closed stays closed
    expect(afterSelection({ open: true, pinned: true }, true)).toEqual({ open: true, pinned: true });
    expect(afterSelection({ open: false, pinned: false }, false)).toEqual({ open: false, pinned: false }); // clearing opens nothing
  });

  test("the Elements action has an icon and a sheet entry", () => {
    expect(ACTIONS.some((a) => a.id === "elements")).toBe(true);
    expect(hasIcon("elements")).toBe(true);
    expect(shortcutRows().some((r) => /element tree/i.test(r.label))).toBe(true);
  });
});
