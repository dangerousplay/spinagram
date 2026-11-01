// Edit operations the canvas sends to the Rust core (`applyOps`, see src/spinagram/edit.py for the shapes).
import {
  boxOf,
  containerAt,
  containerBox,
  containerOf,
  descendants,
  insertionIndex,
  snap,
  zoneBoxes,
  zoneParent,
  type Box,
  type SceneJson,
} from "./scene";

export type Op =
  | { op: "move"; id: string; x: number; y: number }
  | { op: "delete"; id: string }
  | { op: "move_zone"; id: string; x: number; y: number }
  | { op: "reparent"; id: string; parent: string | null }
  | { op: "rename"; id: string; title: string }
  | { op: "group"; axis: "row" | "column"; ids: string[]; gap?: number; x?: number; y?: number }
  | { op: "ungroup"; id: string; boxes: Record<string, Rect> }
  | { op: "add_to_container"; id: string; node: string; index?: number }
  | { op: "remove_from_container"; id: string; node: string; boxes: Record<string, Rect> }
  | { op: "set_container"; id: string; gap?: number; align?: string }
  | { op: "add_node"; id: string; title?: string; kind?: string; icon?: string; x?: number; y?: number; w?: number; h?: number }
  | { op: "add_zone"; id: string; label?: string; x: number; y: number; w: number; h: number };

export type Rect = [number, number, number, number];

/** The Move for a node dragged by (dx, dy): its new corner snapped to the grid; null when nothing would change. */
export function moveOps(box: Box, dx: number, dy: number, grid?: number): Op[] | null {
  const x = snap(box.x + dx, grid);
  const y = snap(box.y + dy, grid);
  if (x === box.x && y === box.y) return null;
  return [{ op: "move", id: box.id, x, y }];
}

export const deleteOps = (id: string): Op[] => [{ op: "delete", id }];

export const renameOps = (id: string, title: string): Op[] => [{ op: "rename", id, title }];

export const CYCLE_MESSAGE = "A zone cannot contain itself";

/** The zone a dragged node or zone would be dropped into: the innermost zone holding the centre of the moved
 * box (ZON-02, ZON-06). Zones that travel with a dragged zone are tested where they are dropped. */
export function dropTarget(scene: SceneJson, box: Box, kind: "node" | "zone", dx: number, dy: number): string | null {
  const cx = snap(box.x + dx) + box.w / 2;
  const cy = snap(box.y + dy) + box.h / 2;
  const travelling = kind === "zone" ? descendants(scene, box.id) : [];
  let best: Box | null = null;
  for (const z of zoneBoxes(scene)) {
    if (z.id === box.id) continue;
    const shift = travelling.includes(z.id) ? { x: snap(box.x + dx) - box.x, y: snap(box.y + dy) - box.y } : { x: 0, y: 0 };
    const b = { ...z, x: z.x + shift.x, y: z.y + shift.y };
    if (cx < b.x || cx > b.x + b.w || cy < b.y || cy > b.y + b.h) continue;
    if (!best || b.w * b.h < best.w * best.h) best = b;
  }
  return best?.id ?? null;
}

export type DropPlan = { ops: Op[] } | { error: string } | null;

const rect = (b: Box): Rect => [b.x, b.y, b.w, b.h];

/** The rendered boxes of the members of container `id`, optionally with one of them replaced. */
function memberBoxes(scene: SceneJson, id: string, replace?: Box): Record<string, Rect> {
  const out: Record<string, Rect> = {};
  for (const m of (scene.containers ?? []).find((c) => c.id === id)?.members ?? []) {
    const b = boxOf(scene, m);
    if (b) out[m] = rect(b);
  }
  if (replace) out[replace.id] = rect(replace);
  return out;
}

/** The batch for dropping a node or zone after a drag by (dx, dy): its Move (MoveZone for a zone) to the snapped
 * corner and, when the drop target differs from its current zone, a Reparent in the same batch (ZON-02, ZON-03,
 * ZON-04). A zone dropped inside itself or a descendant is refused with "A zone cannot contain itself" (ZON-05).
 * A node that is a member of a row or column is placed by it: dropped inside the container's box it is
 * reordered, dropped outside it is removed from it and placed at the drop point (GRP-03); a free node dropped on
 * a container's box joins it at the gap its centre falls in (GRP-02). Null when nothing changes. */
export function planDrop(scene: SceneJson, box: Box, kind: "node" | "zone", dx: number, dy: number, grid?: number): DropPlan {
  const x = snap(box.x + dx, grid);
  const y = snap(box.y + dy, grid);
  if (kind === "node") {
    const member = containerOf(scene, box.id);
    const cbox = member ? containerBox(scene, member.id) : null;
    const [cx, cy] = [x + box.w / 2, y + box.h / 2];
    if (member && cbox) {
      const inside = cx >= cbox.x && cx <= cbox.x + cbox.w && cy >= cbox.y && cy <= cbox.y + cbox.h;
      if (inside) {
        const index = insertionIndex(scene, member, box.id, cx, cy);
        return index === member.members.indexOf(box.id) ? null : { ops: [{ op: "add_to_container", id: member.id, node: box.id, index }] };
      }
      const moved: Box = { ...box, x, y };
      // a container left with fewer than two members dissolves, so it needs every member's box
      const boxes = member.members.length <= 2 ? memberBoxes(scene, member.id, moved) : { [box.id]: rect(moved) };
      const ops: Op[] = [{ op: "remove_from_container", id: member.id, node: box.id, boxes }];
      const target = dropTarget(scene, box, kind, dx, dy);
      if (target !== zoneParent(scene, box.id)) ops.push({ op: "reparent", id: box.id, parent: target });
      return { ops };
    }
    const onto = containerAt(scene, cx, cy);
    if (onto) return { ops: [{ op: "add_to_container", id: onto.id, node: box.id, index: insertionIndex(scene, onto, box.id, cx, cy) }] };
  }
  const target = dropTarget(scene, box, kind, dx, dy);
  if (kind === "zone" && target !== null && descendants(scene, box.id).includes(target)) return { error: CYCLE_MESSAGE };
  const ops: Op[] = [];
  if (x !== box.x || y !== box.y) ops.push(kind === "zone" ? { op: "move_zone", id: box.id, x, y } : { op: "move", id: box.id, x, y });
  if (target !== zoneParent(scene, box.id)) ops.push({ op: "reparent", id: box.id, parent: target });
  return ops.length ? { ops } : null;
}

export type Item = { box: Box; kind: "node" | "zone" };

/** The batch for dropping a whole selection after a drag by (dx, dy): each item as in `planDrop`, all in one batch.
 * Container members do not move freely with a selection, and nodes inside a selected zone move with the zone. */
export function planMultiDrop(scene: SceneJson, items: Item[], dx: number, dy: number, grid?: number): DropPlan {
  const zones = items.filter((i) => i.kind === "zone").map((i) => i.box.id);
  const below = new Set(zones.flatMap((z) => descendants(scene, z)));
  const ops: Op[] = [];
  for (const it of items) {
    if (below.has(it.box.id)) continue;
    if (items.length > 1 && it.kind === "node" && containerOf(scene, it.box.id)) continue;
    const plan = planDrop(scene, it.box, it.kind, dx, dy, grid);
    if (plan && "error" in plan) return plan;
    if (plan) ops.push(...plan.ops);
  }
  return ops.length ? { ops } : null;
}

/** The Group for `ids` (nodes not already in a container), ids ordered by x for a row and by y for a column,
 * gap 20 (GRP-01). Null with fewer than two such nodes. */
export function groupOps(scene: SceneJson, ids: string[], axis: "row" | "column"): Op[] | null {
  const boxes = ids.filter((id) => !containerOf(scene, id)).map((id) => boxOf(scene, id)).filter((b): b is Box => b !== null);
  if (boxes.length < 2) return null;
  boxes.sort((a, b) => (axis === "row" ? a.x - b.x : a.y - b.y));
  return [{ op: "group", axis, ids: boxes.map((b) => b.id), gap: 20 }];
}

/** Ungroup of container `id`, carrying each member's rendered box (GRP-04). */
export function ungroupOps(scene: SceneJson, id: string): Op[] | null {
  const boxes = memberBoxes(scene, id);
  return Object.keys(boxes).length ? [{ op: "ungroup", id, boxes }] : null;
}

export const setContainerOps = (id: string, props: { gap?: number; align?: string }): Op[] => [{ op: "set_container", id, ...props }];
