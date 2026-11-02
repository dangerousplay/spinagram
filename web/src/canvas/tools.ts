// The canvas tools and toolbar actions: ids, labels and keys, and the pure logic of using a tool: what a click or a
// drag with Box, Text or Zone adds, and what a Connect drag sends. The toolbar (Toolbar.tsx) and the key table
// (interaction.ts) are built from these, and icons.tsx maps every id here to an icon.
import type { Op } from "./ops";
import { NODE_H, NODE_W, ZONE_H, ZONE_W, centred, newId, takenIds, zoneAtPoint } from "./palette";
import { boxOf, hitTest, snap, type Box, type SceneJson } from "./scene";

/** A tool is a mode of the pointer. */
export const TOOLS = [
  { id: "select", label: "Select", key: "v" },
  { id: "hand", label: "Pan", key: "h" },
  { id: "box", label: "Box", key: "b" },
  { id: "text", label: "Text", key: "t" },
  { id: "zone", label: "Zone", key: "z" },
  { id: "connect", label: "Connect", key: "c" },
] as const;

export type ToolId = (typeof TOOLS)[number]["id"];

/** An action does something once when pressed. */
export const ACTIONS = [
  { id: "group-row", label: "Group as a row" },
  { id: "group-column", label: "Group as a column" },
  { id: "ungroup", label: "Ungroup" },
  { id: "delete", label: "Delete" },
  { id: "undo", label: "Undo" },
  { id: "redo", label: "Redo" },
  { id: "palette", label: "Palette" },
  { id: "help", label: "Shortcuts" },
  { id: "dock", label: "Dock the toolbar left or at the bottom" },
] as const;

export type ActionId = (typeof ACTIONS)[number]["id"];

export type Point = { x: number; y: number };
export type PlaceTool = "box" | "text" | "zone";
export const isPlaceTool = (t: ToolId): t is PlaceTool => t === "box" || t === "text" || t === "zone";

/** A press that travels less than this (scene px) in both directions is a click, not a drawn rectangle. */
export const CLICK_SLOP = 8;
/** The smallest rectangle a drag can draw (scene px). */
const MIN_SIZE: Record<PlaceTool, [number, number]> = { box: [40, 30], text: [40, 30], zone: [80, 60] };

export type Placement = { ops: Op[]; id: string; box: Box; /** the inline editor opens on the new item at once */ edit: boolean };

/** What a click or a drag with Box, Text or Zone adds. A click puts the default size centred on the point; a drag
 * draws the rectangle between the two points, snapped to the grid and kept on the canvas. A box or text joins the
 * zone its centre is in. Text is a `kind: text` node whose title is edited right away. */
export function placeOps(scene: SceneJson, tool: PlaceTool, a: Point, b: Point): Placement {
  const taken = takenIds(scene);
  const click = Math.abs(b.x - a.x) < CLICK_SLOP && Math.abs(b.y - a.y) < CLICK_SLOP;
  const [dw, dh] = tool === "zone" ? [ZONE_W, ZONE_H] : [NODE_W, NODE_H];
  let rect: { x: number; y: number; w: number; h: number };
  if (click) {
    rect = { ...centred(scene, a.x, a.y, dw, dh), w: dw, h: dh };
  } else {
    const [mw, mh] = MIN_SIZE[tool];
    const x0 = snap(Math.min(a.x, b.x));
    const y0 = snap(Math.min(a.y, b.y));
    const w = Math.min(Math.max(mw, snap(Math.max(a.x, b.x)) - x0), scene.width);
    const h = Math.min(Math.max(mh, snap(Math.max(a.y, b.y)) - y0), scene.height);
    rect = { x: Math.max(0, Math.min(x0, scene.width - w)), y: Math.max(0, Math.min(y0, scene.height - h)), w, h };
  }
  if (tool === "zone") {
    const id = newId("Zone", taken);
    return { ops: [{ op: "add_zone", id, label: "Zone", ...rect }], id, box: { id, ...rect }, edit: false };
  }
  const title = tool === "text" ? "New text" : "New box";
  const id = newId(title, taken);
  const add: Op = { op: "add_node", id, title, kind: tool, ...rect };
  const zone = zoneAtPoint(scene, rect.x + rect.w / 2, rect.y + rect.h / 2);
  return { ops: zone ? [add, { op: "reparent", id, parent: zone }] : [add], id, box: { id, ...rect }, edit: tool === "text" };
}

/** The edge a Connect drag from node `from` released at (x, y) adds: to the node under the point. A release on empty
 * canvas, on the same node or on a zone adds nothing (canvas-editor EDG-02, EDG-03); an edge that already exists is
 * added again, parallel edges being valid (EDG-04). */
export function connectOps(scene: SceneJson, from: string, x: number, y: number): Op[] | null {
  if (!boxOf(scene, from)) return null;
  const to = hitTest(scene, x, y);
  return to && to !== from ? [{ op: "connect", from, to }] : null;
}

/** The tool in use after one use of `tool`: back to Select, unless Shift was held to keep it. */
export const toolAfterUse = (tool: ToolId, keep: boolean): ToolId => (keep ? tool : "select");

/** Where the inline editor of a just-placed item goes, once the scene holds the item. A text node has no box in the
 * scene (it renders as plain text), so the box it was placed with is used; null while the scene lacks the item. */
export const editBoxOf = (scene: SceneJson, pending: { id: string; box: Box }): Box | null =>
  scene.items.some((i) => i.id === pending.id) ? pending.box : null;

/** What the canvas UI does with the three facts it has. `shown`: the canvas is on for an editable diagram, so its
 * toolbar, bar and palette are mounted. `active`: the scene is also loaded in the worker, so they work. While a save
 * is re-fetching the scene `ready` goes false: the controls stay mounted (disabled) instead of being torn down and
 * rebuilt, which is a visible flash. */
export function canvasUi(enabled: boolean, editable: boolean | null, ready: boolean): { shown: boolean; active: boolean } {
  const shown = enabled && editable === true;
  return { shown, active: shown && ready };
}

/** How the toolbar lays out in each dock. The left dock is a vertical bar centred on the left edge; the bottom dock
 * a horizontal bar centred in the row above the status bar (the zoom and view controls sit in the status bar, so it never covers them). The tooltip opens toward the canvas in both. */
export function dockLayout(dock: "left" | "bottom"): { orientation: "vertical" | "horizontal"; bar: string; separator: string; tip: string; /** where the selection bar sits so the toolbar does not cover it */ selectionBar: string } {
  return dock === "left"
    ? {
        orientation: "vertical",
        bar: "top-1/2 left-3 -translate-y-1/2 flex-col",
        separator: "my-0.5 h-px w-6",
        tip: "top-1/2 left-full ml-2 -translate-y-1/2",
        selectionBar: "bottom-14",
      }
    : {
        orientation: "horizontal",
        bar: "bottom-14 left-1/2 -translate-x-1/2 flex-row",
        separator: "mx-0.5 h-6 w-px",
        tip: "bottom-full left-1/2 mb-2 -translate-x-1/2",
        selectionBar: "bottom-28",
      };
}
