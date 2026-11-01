// Edit operations the canvas sends to the Rust core (`applyOps`, see src/spinagram/edit.py for the shapes).
import { descendants, snap, zoneBoxes, zoneParent, type Box, type SceneJson } from "./scene";

export type Op =
  | { op: "move"; id: string; x: number; y: number }
  | { op: "delete"; id: string }
  | { op: "move_zone"; id: string; x: number; y: number }
  | { op: "reparent"; id: string; parent: string | null }
  | { op: "rename"; id: string; title: string };

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

export type Dropped = { x: number; y: number };

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

/** The batch for dropping a node or zone after a drag by (dx, dy): its Move (MoveZone for a zone) to the snapped
 * corner and, when the drop target differs from its current zone, a Reparent in the same batch (ZON-02, ZON-03,
 * ZON-04). A zone dropped inside itself or a descendant is refused with "A zone cannot contain itself" (ZON-05).
 * Null when nothing changes. */
export function planDrop(scene: SceneJson, box: Box, kind: "node" | "zone", dx: number, dy: number, grid?: number): DropPlan {
  const target = dropTarget(scene, box, kind, dx, dy);
  if (kind === "zone" && target !== null && descendants(scene, box.id).includes(target)) return { error: CYCLE_MESSAGE };
  const ops: Op[] = [];
  const x = snap(box.x + dx, grid);
  const y = snap(box.y + dy, grid);
  if (x !== box.x || y !== box.y) ops.push(kind === "zone" ? { op: "move_zone", id: box.id, x, y } : { op: "move", id: box.id, x, y });
  if (target !== zoneParent(scene, box.id)) ops.push({ op: "reparent", id: box.id, parent: target });
  return ops.length ? { ops } : null;
}
