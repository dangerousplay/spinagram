// The element tree of the canvas (T40): the diagram as zones nested by their children, rows and columns with their
// members, free nodes, and an "Edges" group. Pure functions over the scene JSON; the panel is ElementTree.tsx.
import { sceneEdges, zoneParent, type SceneBlock, type SceneItem, type SceneJson, type SceneLabel, type Sel } from "./scene";

export type TreeKind = "zone" | "container" | "node" | "edge" | "group";

export type TreeNode = {
  /** `kind:id`, unique in the tree */
  key: string;
  id: string;
  kind: TreeKind;
  title: string;
  /** path of the icon file in the scene (a node's or zone's own icon), shown as its pack image */
  iconPath: string | null;
  /** the `EditorIcon` name when there is no pack image */
  iconName: string;
  children: TreeNode[];
};

export const keyOf = (s: Sel): string => `${s.kind}:${s.id}`;

const blockText = (b: SceneBlock | undefined): string => (b?.paragraphs ?? b?.lines ?? []).join(" ").trim();

/** The first text block of a label: a node's title, an edge pill's label. */
const labelText = (l: SceneLabel | null | undefined): string => blockText(l?.blocks?.[0]);

/** Build the tree. A node's title is the first block of its label, a zone's the text item next to its shape, an
 * edge's `from → to (label)`; ids stand in when the scene draws no text. */
export function buildTree(scene: SceneJson): TreeNode[] {
  const byId = new Map<string, SceneItem>(scene.items.map((i) => [i.id, i]));
  const zones = scene.zones ?? [];
  const containers = scene.containers ?? [];
  const zoneIds = new Set(zones.map((z) => z.id));
  const zoneOfShape = new Map(zones.map((z) => [z.shape_id, z.id]));
  const nodeTitle = new Map<string, string>();
  const nodes = scene.items.filter((i) => i.type === "shape" && i.role === "node");
  for (const n of nodes) nodeTitle.set(n.id, labelText(n.label) || n.id);
  const zoneTitle = (z: { id: string; shape_id: string }) => {
    return blockText(byId.get(`${z.shape_id}-label`)?.block) || z.id;
  };
  const zoneIcon = (shape: string): string | null => scene.items.find((i) => i.id.startsWith(`${shape}-icon`))?.icon?.path ?? null;

  const inContainer = new Set(containers.flatMap((c) => c.members));
  const nodeRow = (id: string): TreeNode => ({
    key: `node:${id}`,
    id,
    kind: "node",
    title: nodeTitle.get(id) ?? id,
    iconPath: byId.get(id)?.icon?.path ?? null,
    iconName: "box",
    children: [],
  });
  const containerRow = (c: (typeof containers)[number]): TreeNode => ({
    key: `container:${c.id}`,
    id: c.id,
    kind: "container",
    title: `${c.axis === "column" ? "Column" : "Row"} · ${c.members.length} items`,
    iconPath: null,
    iconName: c.axis,
    children: c.members.filter((m) => nodeTitle.has(m)).map(nodeRow),
  });
  /** the zone a container sits in: the one that lists its members */
  const containerZone = (c: (typeof containers)[number]): string | null => c.members.map((m) => zoneParent(scene, m)).find((z) => z !== null) ?? null;

  const zoneRow = (z: (typeof zones)[number]): TreeNode => {
    const kids: TreeNode[] = [];
    for (const child of z.children) {
      const sub = zones.find((o) => o.id === child);
      if (sub) kids.push(zoneRow(sub));
      else if (nodeTitle.has(child) && !inContainer.has(child)) kids.push(nodeRow(child));
    }
    for (const c of containers) if (containerZone(c) === z.id) kids.push(containerRow(c));
    return { key: `zone:${z.id}`, id: z.id, kind: "zone", title: zoneTitle(z), iconPath: zoneIcon(z.shape_id), iconName: "zone", children: kids };
  };

  const nested = new Set(zones.flatMap((z) => z.children.filter((c) => zoneIds.has(c))));
  const out: TreeNode[] = zones.filter((z) => !nested.has(z.id)).map(zoneRow);
  for (const c of containers) if (containerZone(c) === null) out.push(containerRow(c));
  for (const n of nodes) if (zoneParent(scene, n.id) === null && !inContainer.has(n.id)) out.push(nodeRow(n.id));

  const endTitle = (shape: string | null, raw: SceneItem["src"]): string => {
    if (shape && nodeTitle.has(shape)) return nodeTitle.get(shape)!;
    const z = raw ? zoneOfShape.get(raw.shape_id) : undefined;
    return z ? zoneTitle(zones.find((o) => o.id === z)!) : "?";
  };
  const edgeRows = sceneEdges(scene).map((e): TreeNode => {
    const item = byId.get(e.id)!;
    const label = labelText(item.label?.label);
    return {
      key: `edge:${e.id}`,
      id: e.id,
      kind: "edge",
      title: `${endTitle(e.from, item.src)} → ${endTitle(e.to, item.dst)}${label ? ` (${label})` : ""}`,
      iconPath: null,
      iconName: "connect",
      children: [],
    };
  });
  if (edgeRows.length) out.push({ key: "group:edges", id: "edges", kind: "group", title: `Edges · ${edgeRows.length}`, iconPath: null, iconName: "connect", children: edgeRows });
  return out;
}

/** The tree narrowed to what matches `query` (case-insensitive, on the row's title or id): matches and the ancestors
 * that lead to them. A blank query keeps everything. */
export function filterTree(nodes: TreeNode[], query: string): TreeNode[] {
  const q = query.trim().toLowerCase();
  if (!q) return nodes;
  const walk = (list: TreeNode[]): TreeNode[] =>
    list.flatMap((n): TreeNode[] => {
      const kids = walk(n.children);
      const hit = n.kind !== "group" && (n.title.toLowerCase().includes(q) || n.id.toLowerCase().includes(q));
      return hit || kids.length ? [{ ...n, children: kids }] : [];
    });
  return walk(nodes);
}

/** The rows in display order with their depth, skipping what a collapsed row hides. */
export function visibleRows(nodes: TreeNode[], collapsed: ReadonlySet<string>, depth = 0): { node: TreeNode; depth: number }[] {
  return nodes.flatMap((n) => [{ node: n, depth }, ...(collapsed.has(n.key) ? [] : visibleRows(n.children, collapsed, depth + 1))]);
}

/** The keys of the rows above `key`, outermost first (empty when it is at the top or absent). */
export function ancestorKeys(nodes: TreeNode[], key: string): string[] {
  const walk = (list: TreeNode[], path: string[]): string[] | null => {
    for (const n of list) {
      if (n.key === key) return path;
      const hit = walk(n.children, [...path, n.key]);
      if (hit) return hit;
    }
    return null;
  };
  return walk(nodes, []) ?? [];
}

/** The collapsed set after the selection changed on the canvas: every ancestor of a selected row opens, so the row is visible. */
export function revealSelection(nodes: TreeNode[], sel: Sel[], collapsed: ReadonlySet<string>): Set<string> {
  const open = new Set(sel.flatMap((s) => ancestorKeys(nodes, keyOf(s))));
  return new Set([...collapsed].filter((k) => !open.has(k)));
}

/** The selection after a click on a row: it replaces the selection; with `additive` (Shift or Ctrl/Cmd) it toggles the
 * row. A group row (Edges) selects nothing. */
export function selectFromRow(row: TreeNode, current: Sel[], additive: boolean): Sel[] {
  if (row.kind === "group") return current;
  const me: Sel = { id: row.id, kind: row.kind };
  if (!additive) return [me];
  return current.some((s) => keyOf(s) === row.key) ? current.filter((s) => keyOf(s) !== row.key) : [...current, me];
}

/** The keys of the rows that show as selected for a canvas selection. */
export const selectedKeys = (sel: Sel[]): Set<string> => new Set(sel.map(keyOf));
