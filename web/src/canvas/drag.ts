// Drag state of one node, as plain functions: the React layer feeds pointer positions in and reads moves out.
import type { Box } from "./scene";

export type Drag = { box: Box; x0: number; y0: number; dx: number; dy: number; moved: boolean };

/** Pointer travel (scene px) before a press counts as a drag rather than a click. */
export const DRAG_THRESHOLD = 3;

export const startDrag = (box: Box, x: number, y: number): Drag => ({ box, x0: x, y0: y, dx: 0, dy: 0, moved: false });

/** The drag after the pointer reached (x, y) in scene px. */
export function dragTo(d: Drag, x: number, y: number): Drag {
  const dx = x - d.x0;
  const dy = y - d.y0;
  return { ...d, dx, dy, moved: d.moved || Math.hypot(dx, dy) > DRAG_THRESHOLD };
}

/** The move map `reroute` takes for the drag so far, or null while it is still a click. */
export function dragMoves(d: Drag): Record<string, [number, number]> | null {
  return d.moved ? { [d.box.id]: [d.dx, d.dy] } : null;
}
