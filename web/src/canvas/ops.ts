// Edit operations the canvas sends to the Rust core (`applyOps`, see src/spinagram/edit.py for the shapes).
import { snap, type Box } from "./scene";

export type Op = { op: "move"; id: string; x: number; y: number } | { op: "delete"; id: string };

/** The Move for a node dragged by (dx, dy): its new corner snapped to the grid; null when nothing would change. */
export function moveOps(box: Box, dx: number, dy: number, grid?: number): Op[] | null {
  const x = snap(box.x + dx, grid);
  const y = snap(box.y + dy, grid);
  if (x === box.x && y === box.y) return null;
  return [{ op: "move", id: box.id, x, y }];
}

export const deleteOps = (id: string): Op[] => [{ op: "delete", id }];
