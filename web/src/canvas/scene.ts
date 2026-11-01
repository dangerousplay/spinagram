// The slice of the scene JSON (rust/schema/scene.schema.json) the canvas reads: node boxes, for hit-testing.
export type SceneItem = { type: string; id: string; role?: string; kind?: string; x?: number; y?: number; w?: number; h?: number };
export type SceneZone = { id: string; shape_id: string; children: string[] };
export type SceneContainer = { id: string; axis: string; members: string[]; box: [number, number, number, number] };
export type SceneJson = { width: number; height: number; items: SceneItem[]; zones?: SceneZone[]; containers?: SceneContainer[] };
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

// --- zones ---------------------------------------------------------------------------------------------------

/** A press this close to a zone's top edge (its header band) or to its outline grabs the zone. */
export const ZONE_HEADER = 56;
export const ZONE_EDGE = 8;

/** Boxes of the zones, `id` being the id the spec declares (what the edit operations take), in scene order. */
export function zoneBoxes(scene: SceneJson): Box[] {
  const out: Box[] = [];
  for (const z of scene.zones ?? []) {
    const it = scene.items.find((i) => i.type === "shape" && i.id === z.shape_id);
    if (it && it.x !== undefined && it.y !== undefined && it.w !== undefined && it.h !== undefined) out.push({ id: z.id, x: it.x, y: it.y, w: it.w, h: it.h });
  }
  return out;
}

export const zoneBox = (scene: SceneJson, id: string): Box | null => zoneBoxes(scene).find((b) => b.id === id) ?? null;

const area = (b: Box) => b.w * b.h;
const contains = (b: Box, x: number, y: number) => x >= b.x && x <= b.x + b.w && y >= b.y && y <= b.y + b.h;

/** The innermost (smallest) zone whose header band or outline is under the point, or null. Nodes win over this. */
export function hitZone(scene: SceneJson, x: number, y: number): string | null {
  let best: Box | null = null;
  for (const b of zoneBoxes(scene)) {
    if (!contains(b, x, y)) continue;
    const onEdge = x - b.x <= ZONE_EDGE || b.x + b.w - x <= ZONE_EDGE || b.y + b.h - y <= ZONE_EDGE;
    if (!(y - b.y <= ZONE_HEADER || onEdge)) continue;
    if (!best || area(b) < area(best)) best = b;
  }
  return best?.id ?? null;
}

/** The zone that lists `id` among its children, or null (top level). */
export const zoneParent = (scene: SceneJson, id: string): string | null => (scene.zones ?? []).find((z) => z.children.includes(id))?.id ?? null;

/** Every id below zone `id`: child nodes and zones, their children, and so on. */
export function descendants(scene: SceneJson, id: string): string[] {
  const out: string[] = [];
  const todo = [id];
  while (todo.length) {
    const cur = todo.pop()!;
    for (const kid of (scene.zones ?? []).find((z) => z.id === cur)?.children ?? []) {
      if (!out.includes(kid)) {
        out.push(kid);
        todo.push(kid);
      }
    }
  }
  return out;
}

/** The shapes a zone drag moves, as the ids `reroute` takes: the zone, every child zone and every child node.
 * `reroute` carries each shape's own label, icon, accent parts and (for a zone) header label, icons and strip. */
export function zoneMoveShapes(scene: SceneJson, id: string): string[] {
  const shapeOf = new Map((scene.zones ?? []).map((z) => [z.id, z.shape_id]));
  return [id, ...descendants(scene, id)].map((i) => shapeOf.get(i) ?? i);
}
