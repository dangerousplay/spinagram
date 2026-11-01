// The slice of the scene JSON (rust/schema/scene.schema.json) the canvas reads: node boxes, for hit-testing.
export type SceneItem = { type: string; id: string; role?: string; kind?: string; x?: number; y?: number; w?: number; h?: number };
export type SceneJson = { width: number; height: number; items: SceneItem[] };
export type Box = { id: string; x: number; y: number; w: number; h: number };

/** Grid the canvas snaps a dropped node to, in scene px. */
export const GRID = 10;

/** Round to the nearest grid line (halves go up). */
export function snap(v: number, grid: number = GRID): number {
  return Math.round(v / grid) * grid;
}

/** Boxes of the diagram's nodes in drawing order (later items are drawn on top). */
export function nodeBoxes(scene: SceneJson): Box[] {
  const out: Box[] = [];
  for (const it of scene.items) {
    if (it.type === "shape" && it.role === "node" && it.x !== undefined && it.y !== undefined && it.w !== undefined && it.h !== undefined) {
      out.push({ id: it.id, x: it.x, y: it.y, w: it.w, h: it.h });
    }
  }
  return out;
}

/** The topmost node whose box contains the point (scene px), or null. `slop` widens every box. */
export function hitTest(scene: SceneJson, x: number, y: number, slop = 0): string | null {
  const boxes = nodeBoxes(scene);
  for (let i = boxes.length - 1; i >= 0; i--) {
    const b = boxes[i];
    if (x >= b.x - slop && x <= b.x + b.w + slop && y >= b.y - slop && y <= b.y + b.h + slop) return b.id;
  }
  return null;
}

export function boxOf(scene: SceneJson, id: string): Box | null {
  return nodeBoxes(scene).find((b) => b.id === id) ?? null;
}
