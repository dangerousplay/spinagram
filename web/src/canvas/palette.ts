// The icon palette: a searchable list of icons, shapes and containers to add to the diagram (canvas-editor PAL-*).
// Pure logic: the corpus, fuzzy search, ids, and the operations a drop sends. The panel is PalettePanel.tsx.
import uFuzzy from "@leeoniya/ufuzzy";
import type { ZoneStyle } from "../api";
import { type Op } from "./ops";
import { snap, zoneBoxes, type SceneJson } from "./scene";

export type IconEntry = { pack: string; name: string; aliases: string[] };

export type PaletteItem =
  | { type: "icon"; pack: string; name: string; ref: string; title: string; aliases: string[] }
  | { type: "shape"; kind: string; title: string }
  | { type: "zone"; title: string }
  | { type: "zoneStyle"; style: string; title: string; provider: string; icon: string | null; stroke: string | null; fill: string | null; dashed: boolean }
  | { type: "row"; title: string }
  | { type: "column"; title: string };

/** Size of a dropped icon or shape node (the auto-size minimums, PAL-04). */
export const NODE_W = 220;
export const NODE_H = 96;
/** Size of a dropped zone (ZON-01). */
export const ZONE_W = 600;
export const ZONE_H = 400;

export const SHAPE_KINDS = ["box", "pill", "text", "note", "diamond", "decision", "process", "io", "document", "data", "predefined", "terminator", "state", "action", "object"];

/** "amazon-s3" -> "Amazon S3": the display name of an icon. */
export function displayName(name: string): string {
  return name
    .split(/[-_\s]+/)
    .filter(Boolean)
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ");
}

/** The built-in items: Zone, Row, Column and the node shapes. */
export const BUILTINS: PaletteItem[] = [
  { type: "zone", title: "Zone" },
  { type: "row", title: "Row" },
  { type: "column", title: "Column" },
  ...SHAPE_KINDS.map((kind): PaletteItem => ({ type: "shape", kind, title: displayName(kind) })),
];

export type { ZoneStyle };

/** The provider groups of the Zones category, in order; a zone style belongs to the one its name starts with. */
export const ZONE_PROVIDERS = [
  { prefix: "aws", title: "AWS" },
  { prefix: "azure", title: "Azure" },
  { prefix: "gcp", title: "Google Cloud" },
  { prefix: "k8s", title: "Kubernetes" },
] as const;

/** What each provider zone style is called in the palette and on the zone it adds. */
export const ZONE_TITLES: Record<string, string> = {
  "aws-cloud": "AWS Cloud",
  "aws-account": "AWS Account",
  "aws-region": "Region",
  "aws-vpc": "VPC",
  "aws-az": "Availability Zone",
  "aws-public-subnet": "Public subnet",
  "aws-private-subnet": "Private subnet",
  "aws-auto-scaling-group": "Auto Scaling group",
  "aws-corporate-dc": "Corporate data center",
  "aws-spot-fleet": "Spot Fleet",
  "aws-server-contents": "Server contents",
  "aws-ec2-contents": "EC2 instance contents",
  "azure-management-group": "Management group",
  "azure-subscription": "Subscription",
  "azure-resource-group": "Resource group",
  "azure-vnet": "Virtual network",
  "azure-subnet": "Subnet",
  "gcp-cloud": "Google Cloud",
  "gcp-project": "Project",
  "gcp-region": "Region",
  "gcp-zone": "Zone",
  "gcp-vpc": "VPC network",
  "gcp-subnet": "Subnet",
  "k8s-cluster": "Cluster",
  "k8s-namespace": "Namespace",
};

/** Styles that only repeat another one under an older name (`aws-subnet` is the private subnet). */
const ZONE_ALIASES = new Set(["aws-subnet"]);

/** The Zones items for the styles the theme has: provider by provider in `ZONE_PROVIDERS` order, each keeping the
 * theme's order. A style that is not a provider group (soft, warning, ...) is not offered. */
export function zoneStyleItems(styles: ZoneStyle[]): PaletteItem[] {
  return ZONE_PROVIDERS.flatMap((p) =>
    styles
      .filter((s) => s.name.startsWith(`${p.prefix}-`) && !ZONE_ALIASES.has(s.name))
      .map((s): PaletteItem => ({
        type: "zoneStyle",
        style: s.name,
        title: ZONE_TITLES[s.name] ?? displayName(s.name.slice(p.prefix.length + 1)),
        provider: p.title,
        icon: s.icon,
        stroke: s.stroke,
        fill: s.fill,
        dashed: s.dashed,
      })),
  );
}

export function iconItem(e: IconEntry): PaletteItem {
  return { type: "icon", pack: e.pack, name: e.name, ref: `${e.pack}:${e.name}`, title: displayName(e.name), aliases: e.aliases };
}

/** The text a search matches against: name, aliases and pack name, lower case. */
export const haystackOf = (it: PaletteItem): string => {
  switch (it.type) {
    case "icon":
      return [it.name, ...it.aliases, it.pack].join(" ").toLowerCase();
    case "shape":
      return `${it.kind} shape`;
    case "zoneStyle":
      return `${it.title} ${it.style} ${it.provider} zone`.toLowerCase();
    default:
      return it.type;
  }
};

export type Corpus = { items: PaletteItem[]; haystack: string[] };

export function buildCorpus(icons: IconEntry[], zoneStyles: ZoneStyle[] = []): Corpus {
  const items = [...BUILTINS, ...zoneStyleItems(zoneStyles), ...icons.map(iconItem)];
  return { items, haystack: items.map(haystackOf) };
}

// one typo per term is tolerated (insertion, deletion, substitution or transposition), terms of 4+ characters only
const fuzzy = new uFuzzy({ intraMode: 1, intraIns: 1, intraSub: 1, intraTrn: 1, intraDel: 1 });

/** The items matching `query`, best first, at most `limit`. An empty query lists the built-ins, then icons by name. */
export function search(corpus: Corpus, query: string, limit = 100): PaletteItem[] {
  const q = query.trim().toLowerCase();
  if (!q) return corpus.items.slice(0, limit);
  const [idxs, info, order] = fuzzy.search(corpus.haystack, q, 0, 5000);
  if (!idxs || !idxs.length) return [];
  const ranked = info && order ? order.map((i) => info.idx[i]) : idxs;
  return ranked.slice(0, limit).map((i) => corpus.items[i]);
}

/** The message for a query that matches nothing (PAL-07). */
export const noMatch = (query: string): string => `No icons match '${query.trim()}'`;

/** A kebab-case id from a title, suffixed `-2`, `-3`, ... until it is not in `taken` (node and zone ids). */
export function newId(title: string, taken: Iterable<string>): string {
  const used = new Set(taken);
  const base = title.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "") || "node";
  if (!used.has(base)) return base;
  for (let n = 2; ; n++) if (!used.has(`${base}-${n}`)) return `${base}-${n}`;
}

/** Every node and zone id of the scene. */
export function takenIds(scene: SceneJson): string[] {
  const nodes = scene.items.filter((i) => i.type === "shape" && i.role === "node").map((i) => i.id);
  return [...nodes, ...(scene.zones ?? []).map((z) => z.id)];
}

const clamp = (v: number, lo: number, hi: number) => Math.max(lo, Math.min(v, Math.max(lo, hi)));

/** The top-left of a `w` x `h` box centred on (px, py), snapped, kept inside the canvas. */
export function centred(scene: SceneJson, px: number, py: number, w: number, h: number): { x: number; y: number } {
  return { x: clamp(snap(px - w / 2), 0, scene.width - w), y: clamp(snap(py - h / 2), 0, scene.height - h) };
}

/** The innermost zone holding a point, or null. */
export function zoneAtPoint(scene: SceneJson, x: number, y: number): string | null {
  let best: { id: string; area: number } | null = null;
  for (const b of zoneBoxes(scene)) {
    if (x < b.x || x > b.x + b.w || y < b.y || y > b.y + b.h) continue;
    if (!best || b.w * b.h < best.area) best = { id: b.id, area: b.w * b.h };
  }
  return best?.id ?? null;
}

/** The operations for dropping `item` with its centre at (px, py) in scene px (PAL-04, PAL-05, ZON-01, ZON-02).
 * An icon or shape becomes a node 220 x 96 centred on the point, snapped, with a unique id, and joins the zone under
 * the point. A zone is placed with its top-left at the point. Row and Column add two boxes grouped on that axis. */
export function dropOps(scene: SceneJson, item: PaletteItem, px: number, py: number): Op[] {
  const taken = takenIds(scene);
  switch (item.type) {
    case "zone": {
      const id = newId("Zone", taken);
      const x = clamp(snap(px), 0, scene.width - ZONE_W);
      const y = clamp(snap(py), 0, scene.height - ZONE_H);
      return [{ op: "add_zone", id, label: "Zone", x, y, w: ZONE_W, h: ZONE_H }];
    }
    case "zoneStyle": {
      const id = newId(item.title, taken);
      const x = clamp(snap(px), 0, scene.width - ZONE_W);
      const y = clamp(snap(py), 0, scene.height - ZONE_H);
      return [{ op: "add_zone", id, label: item.title, style: item.style, x, y, w: ZONE_W, h: ZONE_H }];
    }
    case "row":
    case "column": {
      const first = newId("New box", taken);
      const second = newId("New box", [...taken, first]);
      const row = item.type === "row";
      const w = NODE_W * (row ? 2 : 1) + (row ? 20 : 0);
      const h = NODE_H * (row ? 1 : 2) + (row ? 0 : 20);
      const { x, y } = centred(scene, px, py, w, h);
      return [
        { op: "add_node", id: first, title: "New box", x, y, w: NODE_W, h: NODE_H },
        { op: "add_node", id: second, title: "New box", x: row ? x + NODE_W + 20 : x, y: row ? y : y + NODE_H + 20, w: NODE_W, h: NODE_H },
        { op: "group", axis: item.type, ids: [first, second], gap: 20, x, y },
      ];
    }
    default: {
      const title = item.type === "icon" ? item.title : `New ${item.kind}`;
      const id = newId(title, taken);
      const { x, y } = centred(scene, px, py, NODE_W, NODE_H);
      const add: Op = { op: "add_node", id, title, x, y, w: NODE_W, h: NODE_H, ...(item.type === "icon" ? { icon: item.ref } : { kind: item.kind }) };
      const zone = zoneAtPoint(scene, x + NODE_W / 2, y + NODE_H / 2);
      return zone ? [add, { op: "reparent", id, parent: zone }] : [add];
    }
  }
}

/** The placeholder shown at the drop point while the edit is saved and rendered: the bounding box of every box
 * the operations add, with the title of the first. Null when they add nothing with a position. */
export type Ghost = { x: number; y: number; w: number; h: number; label: string };
export function ghostOf(ops: Op[]): Ghost | null {
  const boxes: Ghost[] = [];
  for (const o of ops) {
    if (o.op === "add_zone") boxes.push({ x: o.x, y: o.y, w: o.w, h: o.h, label: o.label ?? o.id });
    else if (o.op === "add_node" && o.x !== undefined && o.y !== undefined) boxes.push({ x: o.x, y: o.y, w: o.w ?? NODE_W, h: o.h ?? NODE_H, label: o.title ?? o.id });
  }
  if (!boxes.length) return null;
  const x = Math.min(...boxes.map((b) => b.x));
  const y = Math.min(...boxes.map((b) => b.y));
  return { x, y, w: Math.max(...boxes.map((b) => b.x + b.w)) - x, h: Math.max(...boxes.map((b) => b.y + b.h)) - y, label: boxes[0].label };
}

// --- categories ----------------------------------------------------------------------------------------------

/** The palette items listed under Basics, in this order. */
const BASICS: { type: PaletteItem["type"]; kind?: string }[] = [
  { type: "shape", kind: "box" },
  { type: "shape", kind: "text" },
  { type: "zone" },
  { type: "row" },
  { type: "column" },
  { type: "shape", kind: "note" },
];

export type Category = { id: string; title: string; items: PaletteItem[] };

const basicIndex = (it: PaletteItem) => BASICS.findIndex((b) => b.type === it.type && (b.kind === undefined || (it.type === "shape" && it.kind === b.kind)));

/** The category an item belongs to: Basics (Box, Text, Zone, Row, Column, Note), Shapes (every other shape kind) or
 * the icon pack it comes from. Ids: `basics`, `shapes`, `pack:<name>`. */
export function categoryOf(it: PaletteItem): { id: string; title: string } {
  if (it.type === "icon") return { id: `pack:${it.pack}`, title: it.pack };
  if (it.type === "zoneStyle") return { id: "zones", title: "Zones" };
  return basicIndex(it) >= 0 ? { id: "basics", title: "Basics" } : { id: "shapes", title: "Shapes" };
}

/** Items grouped for the palette when the search box is empty: Basics, Shapes, then one category per icon pack
 * (by pack name). Empty categories are left out; items keep their order inside a category. */
export function categorize(items: PaletteItem[]): Category[] {
  const byId = new Map<string, Category>();
  for (const it of items) {
    const c = categoryOf(it);
    let cat = byId.get(c.id);
    if (!cat) byId.set(c.id, (cat = { ...c, items: [] }));
    cat.items.push(it);
  }
  const basics = byId.get("basics");
  basics?.items.sort((a, b) => basicIndex(a) - basicIndex(b));
  const zones = byId.get("zones");
  const generic = items.find((i) => i.type === "zone");
  if (zones && generic) zones.items.unshift(generic); // the plain Zone leads the provider groups
  const packs = [...byId.values()].filter((c) => c.id.startsWith("pack:")).sort((a, b) => a.title.localeCompare(b.title));
  return [byId.get("basics"), byId.get("zones"), byId.get("shapes"), ...packs].filter((c): c is Category => c !== undefined);
}

/** Icon packs start collapsed (they can hold thousands of items); Basics and Shapes start open. */
export const defaultCollapsed = (id: string): boolean => id.startsWith("pack:");

export type PaletteRow =
  | { type: "header"; cat: Category; collapsed: boolean }
  | { type: "subheader"; title: string }
  | { type: "item"; item: PaletteItem; cat: Pick<Category, "id" | "title"> };

/** The rows the panel draws: a header per category, and under an open one its items. */
export function paletteRows(cats: Category[], collapsedOf: (id: string) => boolean): PaletteRow[] {
  return cats.flatMap((cat): PaletteRow[] => {
    const collapsed = collapsedOf(cat.id);
    if (collapsed) return [{ type: "header", cat, collapsed }];
    const rows: PaletteRow[] = [{ type: "header", cat, collapsed }];
    let provider: string | null = null;
    for (const item of cat.items) {
      if (item.type === "zoneStyle" && item.provider !== provider) rows.push({ type: "subheader", title: (provider = item.provider) });
      rows.push({ type: "item", item, cat });
    }
    return rows;
  });
}
