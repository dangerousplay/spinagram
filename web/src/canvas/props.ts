// The properties panel's logic (T41): which fields each kind of element has (one table per kind, checked against the
// loader's keys by the tests), what a field commit sends, what several selected elements share, and what each quick
// action does. Pure functions; the form is Properties.tsx.
import { deleteSelectionOps, groupOps, ungroupOps, zoneStyleOps, type Op } from "./ops";
import { SHAPE_KINDS } from "./palette";
import { boxOf, containerOf, edgeById, snap, zoneBox, zoneParent, ZONE_HEADER, type Box, type SceneJson, type Sel } from "./scene";
import { edgeField, edgeLabelOf, entryField } from "./srcmap";

export type FieldKind = "text" | "number" | "bool" | "select" | "icon" | "zoneStyle" | "node";

export type Field = {
  key: string;
  label: string;
  kind: FieldKind;
  options?: readonly string[];
  /** `x`, `y`, `w`, `h`: written by move and resize, not by set_props */
  geometry?: boolean;
  readonly?: boolean;
};

const text = (key: string, label: string): Field => ({ key, label, kind: "text" });
const geometry = (key: string, label: string): Field => ({ key, label, kind: "number", geometry: true });
const GEOMETRY = [geometry("x", "X"), geometry("y", "Y"), geometry("w", "Width"), geometry("h", "Height")];

/** The keys the loader accepts, as the form offers them. `tests` read `yaml_io.py` and `model.py` to check this. */
export const FIELDS = {
  node: [
    { key: "id", label: "Id", kind: "text", readonly: true },
    text("title", "Title"),
    text("text", "Text"),
    { key: "icon", label: "Icon", kind: "icon" },
    { key: "kind", label: "Kind", kind: "select", options: SHAPE_KINDS },
    text("class", "Class"),
    ...GEOMETRY,
  ],
  zone: [
    { key: "id", label: "Id", kind: "text", readonly: true },
    text("label", "Label"),
    { key: "color", label: "Style", kind: "zoneStyle" },
    text("class", "Class"),
    ...GEOMETRY,
  ],
  edge: [
    { key: "id", label: "Id", kind: "text", readonly: true },
    { key: "from", label: "From", kind: "node" },
    { key: "to", label: "To", kind: "node" },
    text("label", "Label"),
    { key: "route", label: "Route", kind: "select", options: ["ortho", "elbow"] },
    { key: "dashed", label: "Dashed", kind: "bool" },
    text("color", "Color"),
    text("class", "Class"),
    { key: "arrow", label: "Arrow ends", kind: "select", options: ["end", "start", "both", "none"] },
  ],
} satisfies Record<string, Field[]>;

export type FieldOwner = keyof typeof FIELDS;

/** The fields of the elements in a selection: all of them for one element; for several, those every selected kind
 * has (same key and kind), without `id`, the ends of an edge and the position (setting `x` of several is no move). */
export function fieldsFor(sel: Sel[]): Field[] {
  const owners = [...new Set(sel.map((s) => s.kind))].filter((k): k is FieldOwner => k === "node" || k === "zone" || k === "edge");
  if (owners.length === 0 || owners.length !== new Set(sel.map((s) => s.kind)).size) return []; // a container has no fields
  if (sel.length === 1) return FIELDS[owners[0]];
  return FIELDS[owners[0]].filter((f) => {
    if (f.readonly || f.kind === "node" || f.key === "x" || f.key === "y") return false;
    return owners.every((o) => FIELDS[o].some((g) => g.key === f.key && g.kind === f.kind));
  });
}

/** The box a node or zone has in the scene. */
const boxFor = (scene: SceneJson, s: Sel): Box | null => (s.kind === "zone" ? zoneBox(scene, s.id) : s.kind === "node" ? boxOf(scene, s.id) : null);

/** A field's value now, as text (a checkbox: "true" or ""), from the scene (position, size, ends) and the element's YAML
 * entry (`entry`, from the source map). Empty when the key is not set. */
export function currentValue(scene: SceneJson, s: Sel, field: Field, entry: string): string {
  const box = boxFor(scene, s);
  if (field.geometry) return box ? String(Math.round(box[field.key as "x"] * 10) / 10) : "";
  if (field.key === "id") return s.id;
  if (s.kind === "edge") {
    if (field.key === "from" || field.key === "to") return edgeById(scene, s.id)?.[field.key] ?? "";
    if (field.key === "label") return edgeLabelOf(entry);
    const v = edgeField(entry, field.key) ?? "";
    return field.kind === "bool" ? (v === "true" ? "true" : "") : v;
  }
  const v = entryField(entry, field.key) ?? "";
  if (field.kind === "zoneStyle") return v || "soft";
  return field.kind === "bool" ? (v === "true" ? "true" : "") : v;
}

/** The value `fieldOps` compares a commit with: a checkbox is true or false, everything else its text. */
export const rawValue = (field: Field, value: string): string | boolean => (field.kind === "bool" ? value === "true" : value);

export type FieldResult = { ops: Op[] } | { error: string } | null;

const MAX_SIZE = 100000;

/** What committing `raw` in `field` sends for element `s`. A blank value (or an unchecked box) clears the key. Null
 * when nothing changes; an `error` is the reason to show, and nothing is sent. `current` is the field's value now. */
export function fieldOps(scene: SceneJson, s: Sel, field: Field, raw: string | boolean, current: string | boolean): FieldResult {
  if (field.readonly || raw === current) return null;
  if (field.geometry) return geometryOps(scene, s, field.key, String(raw));
  if (field.kind === "node") {
    const edge = edgeById(scene, s.id);
    const to = String(raw).trim();
    if (!edge || !to) return { error: "Choose a node" };
    return { ops: [field.key === "from" ? { op: "reconnect", id: s.id, from: to } : { op: "reconnect", id: s.id, to }] };
  }
  if (field.kind === "zoneStyle") return { ops: zoneStyleOps(s.id, String(raw).trim() || "soft") };
  const value = field.kind === "bool" ? (raw === true ? true : null) : String(raw).trim() === "" ? null : String(raw).trim();
  return { ops: [{ op: "set_props", id: s.id, props: { [field.key]: value } }] };
}

function geometryOps(scene: SceneJson, s: Sel, key: string, raw: string): FieldResult {
  const box = boxFor(scene, s);
  if (!box) return null;
  if (s.kind === "node" && containerOf(scene, s.id)) return { error: "A row or column member is placed by its container" };
  const v = Number(raw.trim());
  if (raw.trim() === "" || !Number.isFinite(v)) return { error: `${key.toUpperCase()} needs a number` };
  if ((key === "w" || key === "h") && (v < 1 || v > MAX_SIZE)) return { error: "A size must be at least 1" };
  const next = { x: box.x, y: box.y, w: box.w, h: box.h, [key]: v };
  if (next[key as "x"] === box[key as "x"]) return null;
  if (key === "x" || key === "y") return { ops: [{ op: s.kind === "zone" ? "move_zone" : "move", id: s.id, x: next.x, y: next.y }] };
  return { ops: [{ op: "resize", id: s.id, w: next.w, h: next.h }] };
}

// --- quick actions ---------------------------------------------------------------------------------------------

export const QUICK_ACTIONS = [
  { id: "duplicate", label: "Duplicate" },
  { id: "connect", label: "Add connection" },
  { id: "group-row", label: "Group as a row" },
  { id: "group-column", label: "Group as a column" },
  { id: "ungroup", label: "Ungroup" },
  { id: "move-to-zone", label: "Move to zone" },
  { id: "style", label: "Change style" },
  { id: "reverse", label: "Reverse the edge" },
  { id: "parallel", label: "Add a parallel edge" },
  { id: "delete", label: "Delete" },
] as const;

export type QuickId = (typeof QUICK_ACTIONS)[number]["id"];

/** The quick actions to show for a selection, and whether each can run. A row or column selected has only Ungroup. */
export function quickActions(scene: SceneJson | null, sel: Sel[]): { id: QuickId; enabled: boolean }[] {
  if (!scene || sel.length === 0) return [];
  const kinds = new Set(sel.map((s) => s.kind));
  const only = (k: Sel["kind"]) => kinds.size === 1 && kinds.has(k);
  const nodes = sel.filter((s) => s.kind === "node");
  const members = nodes.filter((n) => containerOf(scene, n.id));
  if (only("container")) return [{ id: "ungroup", enabled: true }];
  const out: { id: QuickId; enabled: boolean }[] = [];
  if (!kinds.has("edge") && !kinds.has("container")) out.push({ id: "duplicate", enabled: true });
  if (only("node")) {
    out.push({ id: "connect", enabled: sel.length === 1 });
    out.push({ id: "group-row", enabled: nodes.filter((n) => !containerOf(scene, n.id)).length >= 2 });
    out.push({ id: "group-column", enabled: nodes.filter((n) => !containerOf(scene, n.id)).length >= 2 });
    out.push({ id: "ungroup", enabled: members.length > 0 });
    out.push({ id: "move-to-zone", enabled: members.length === 0 });
  }
  if (only("zone")) out.push({ id: "style", enabled: sel.length === 1 });
  if (only("edge")) {
    out.push({ id: "reverse", enabled: true });
    out.push({ id: "parallel", enabled: sel.every((e) => edgeById(scene, e.id)?.from && edgeById(scene, e.id)?.to) });
  }
  out.push({ id: "delete", enabled: !kinds.has("container") });
  return out;
}

/** How far a duplicate sits from its original (scene px; the operation snaps it to 10). */
export const DUPLICATE_OFFSET = 30;

/** The batch a quick action sends; null for the ones that are not an edit (`connect` starts the Connect tool, `style`
 * focuses the style field) or that have nothing to do. `zone` is the target of Move to zone (null: the top level). */
export function quickOps(scene: SceneJson, id: QuickId, sel: Sel[], zone?: string | null): Op[] | null {
  const ops = ((): Op[] => {
    switch (id) {
      case "duplicate":
        return sel.filter((s) => s.kind === "node" || s.kind === "zone").map((s): Op => ({ op: "duplicate", id: s.id, dx: DUPLICATE_OFFSET, dy: DUPLICATE_OFFSET }));
      case "delete":
        return deleteSelectionOps(sel);
      case "group-row":
      case "group-column":
        return groupOps(scene, sel.filter((s) => s.kind === "node").map((s) => s.id), id === "group-row" ? "row" : "column") ?? [];
      case "ungroup": {
        const ids = new Set(sel.map((s) => (s.kind === "container" ? s.id : containerOf(scene, s.id)?.id)).filter((c): c is string => !!c));
        return [...ids].flatMap((c) => ungroupOps(scene, c) ?? []);
      }
      case "reverse":
        return sel.filter((s) => s.kind === "edge").map((s): Op => ({ op: "reverse", id: s.id }));
      case "parallel":
        return sel.flatMap((s): Op[] => {
          const e = s.kind === "edge" ? edgeById(scene, s.id) : null;
          return e?.from && e.to ? [{ op: "connect", from: e.from, to: e.to }] : [];
        });
      case "move-to-zone":
        return zone === undefined ? [] : sel.filter((s) => s.kind === "node").flatMap((s) => moveToZone(scene, s.id, zone));
      default:
        return [];
    }
  })();
  return ops.length ? ops : null;
}

/** Put node `id` in zone `zone` (or take it to the top level): Reparent, and a Move into the zone's area when the
 * node's centre is not already inside it. A member of a row or column is placed by its container: left alone. */
function moveToZone(scene: SceneJson, id: string, zone: string | null): Op[] {
  const box = boxOf(scene, id);
  if (!box || containerOf(scene, id)) return [];
  if (zoneParent(scene, id) === zone) return [];
  const ops: Op[] = [];
  const z = zone ? zoneBox(scene, zone) : null;
  if (z) {
    const [cx, cy] = [box.x + box.w / 2, box.y + box.h / 2];
    if (cx < z.x || cx > z.x + z.w || cy < z.y || cy > z.y + z.h) ops.push({ op: "move", id, x: snap(z.x + 40), y: snap(z.y + ZONE_HEADER + 24) });
  }
  ops.push({ op: "reparent", id, parent: zone });
  return ops;
}
