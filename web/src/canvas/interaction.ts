// Pure logic of the keyboard and pointer polish: one keymap table (the key handlers and the shortcut sheet both
// read it), what Esc does, arrow-key nudging, cursors, and the selection frame.
import { planMultiDrop, type DropPlan, type Item } from "./ops";
import { TOOLS, type ToolId } from "./tools";
import { boxOf, containerOf, zoneBox, zoneMoveShapes, type Box, type SceneJson, type Sel } from "./scene";


export type KeyLike = { key: string; metaKey: boolean; ctrlKey: boolean; shiftKey: boolean; altKey: boolean };

export type KeyAction =
  | { action: "delete" }
  | { action: "group-row" }
  | { action: "undo" }
  | { action: "redo" }
  | { action: "palette" }
  | { action: "escape" }
  | { action: "help" }
  | { action: "tool"; tool: ToolId }
  | { action: "nudge"; dx: number; dy: number };

export type Binding = {
  action: KeyAction["action"] | "pointer";
  keys: string; // as shown on the sheet
  label: string;
  /** Key bindings only: the action an event triggers, or null. */
  match?: (e: KeyLike) => KeyAction | null;
  /** Key bindings only: events that must trigger `action` (checked by the tests). */
  sample?: KeyLike[];
};

const ev = (key: string, mods: Partial<KeyLike> = {}): KeyLike => ({ key, metaKey: false, ctrlKey: false, shiftKey: false, altKey: false, ...mods });
const mod = (e: KeyLike) => (e.metaKey || e.ctrlKey) && !e.altKey;
const plain = (e: KeyLike) => !e.metaKey && !e.ctrlKey && !e.altKey;

const ARROWS: Record<string, [number, number]> = { ArrowLeft: [-1, 0], ArrowRight: [1, 0], ArrowUp: [0, -1], ArrowDown: [0, 1] };

/** Every canvas shortcut. `matchKey` and the `?` sheet are both derived from this table. */
export const KEYMAP: Binding[] = [
  { action: "pointer", keys: "Click", label: "Select a node, zone or row/column" },
  { action: "pointer", keys: "Shift+click", label: "Add to or remove from the selection" },
  { action: "pointer", keys: "Drag", label: "Move; drop into a zone or row/column to put it there" },
  { action: "pointer", keys: "Drag on empty canvas", label: "Select with a box" },
  { action: "pointer", keys: "Alt+drag", label: "Pan" },
  { action: "pointer", keys: "Space+drag", label: "Pan while Space is held, in any tool" },
  { action: "pointer", keys: "Click or drag (Box, Text, Zone)", label: "Place the default size centred on the point, or draw the rectangle" },
  { action: "pointer", keys: "Drag from node to node (Connect)", label: "Add an edge; nothing on empty canvas, the same node or a zone" },
  { action: "pointer", keys: "Shift while placing", label: "Keep the tool (it returns to Select otherwise)" },
  { action: "pointer", keys: "Double-click", label: "Rename a node or zone" },
  ...TOOLS.map(
    (t): Binding => ({
      action: "tool",
      keys: t.key.toUpperCase(),
      label: `${t.label} tool`,
      match: (e) => (plain(e) && e.key.toLowerCase() === t.key ? { action: "tool", tool: t.id } : null),
      sample: [ev(t.key), ev(t.key.toUpperCase(), { shiftKey: true })],
    }),
  ),
  {
    action: "delete",
    keys: "Delete / Backspace",
    label: "Delete the selection",
    match: (e) => (plain(e) && (e.key === "Delete" || e.key === "Backspace") ? { action: "delete" } : null),
    sample: [ev("Delete"), ev("Backspace")],
  },
  {
    action: "nudge",
    keys: "Arrow keys",
    label: "Nudge the selection 1 px (Shift: 10 px)",
    match: (e) => {
      const d = ARROWS[e.key];
      if (!d || !plain(e)) return null;
      const step = e.shiftKey ? 10 : 1;
      return { action: "nudge", dx: d[0] * step, dy: d[1] * step };
    },
    sample: [ev("ArrowLeft"), ev("ArrowDown", { shiftKey: true })],
  },
  {
    action: "group-row",
    keys: "Ctrl/Cmd+G",
    label: "Group the selected nodes as a row",
    match: (e) => (mod(e) && !e.shiftKey && e.key.toLowerCase() === "g" ? { action: "group-row" } : null),
    sample: [ev("g", { ctrlKey: true }), ev("G", { metaKey: true })],
  },
  {
    action: "undo",
    keys: "Ctrl/Cmd+Z",
    label: "Undo",
    match: (e) => (mod(e) && !e.shiftKey && e.key.toLowerCase() === "z" ? { action: "undo" } : null),
    sample: [ev("z", { ctrlKey: true }), ev("z", { metaKey: true })],
  },
  {
    action: "redo",
    keys: "Shift+Ctrl/Cmd+Z, Ctrl+Y",
    label: "Redo",
    match: (e) => (mod(e) && ((e.shiftKey && e.key.toLowerCase() === "z") || (!e.shiftKey && e.key.toLowerCase() === "y")) ? { action: "redo" } : null),
    sample: [ev("z", { ctrlKey: true, shiftKey: true }), ev("Z", { metaKey: true, shiftKey: true }), ev("y", { ctrlKey: true })],
  },
  {
    action: "palette",
    keys: "/ or Ctrl/Cmd+K",
    label: "Open the palette and search",
    match: (e) => ((plain(e) && e.key === "/") || (mod(e) && !e.shiftKey && e.key.toLowerCase() === "k") ? { action: "palette" } : null),
    sample: [ev("/"), ev("k", { ctrlKey: true }), ev("K", { metaKey: true })],
  },
  {
    action: "escape",
    keys: "Esc",
    label: "Cancel a drag, then clear the selection, then return to Select, then close the palette",
    match: (e) => (e.key === "Escape" ? { action: "escape" } : null),
    sample: [ev("Escape")],
  },
  {
    action: "help",
    keys: "?",
    label: "Show this sheet",
    match: (e) => (!e.metaKey && !e.ctrlKey && !e.altKey && e.key === "?" ? { action: "help" } : null),
    sample: [ev("?", { shiftKey: true })],
  },
];

/** The canvas action a key event triggers, from the keymap table. */
export function matchKey(e: KeyLike): KeyAction | null {
  for (const b of KEYMAP) {
    const hit = b.match?.(e);
    if (hit) return hit;
  }
  return null;
}

/** What the `?` sheet lists: every row of the keymap table. */
export const shortcutRows = (): { keys: string; label: string }[] => KEYMAP.map(({ keys, label }) => ({ keys, label }));

export type EscapeState = { sheet: boolean; dragging: boolean; nudging: boolean; selected: number; palette: boolean; /** a tool other than Select is active */ tool?: boolean };

/** What one Esc press undoes, innermost first. */
export function escapeStep(s: EscapeState): "sheet" | "drag" | "nudge" | "selection" | "tool" | "palette" | null {
  if (s.sheet) return "sheet";
  if (s.dragging) return "drag";
  if (s.nudging) return "nudge";
  if (s.selected > 0) return "selection";
  if (s.tool) return "tool";
  if (s.palette) return "palette";
  return null;
}

/** Arrow-key presses of one burst, summed. */
export type Burst = { dx: number; dy: number; presses: number };
export const EMPTY_BURST: Burst = { dx: 0, dy: 0, presses: 0 };
export const pressNudge = (b: Burst, dx: number, dy: number): Burst => ({ dx: b.dx + dx, dy: b.dy + dy, presses: b.presses + 1 });

/** The items a nudge moves: selected nodes and zones (containers are placed by their own keys). */
export function nudgeItems(scene: SceneJson, sel: Sel[]): Item[] {
  return sel.flatMap((s): Item[] => {
    if (s.kind === "container") return [];
    const box = s.kind === "zone" ? zoneBox(scene, s.id) : boxOf(scene, s.id);
    return box ? [{ box, kind: s.kind }] : [];
  });
}

/** The batch for a whole burst: one Move per node (MoveZone per zone) with the summed offset, 1 px grid. */
export function nudgeOps(scene: SceneJson, sel: Sel[], burst: Burst): DropPlan {
  if (burst.presses === 0 || (burst.dx === 0 && burst.dy === 0)) return null;
  const items = nudgeItems(scene, sel);
  // a lone container member is reordered by a drop, never nudged: keep nudges to free nodes and zones
  const free = items.filter((i) => i.kind === "zone" || !containerOf(scene, i.box.id));
  return free.length ? planMultiDrop(scene, free, burst.dx, burst.dy, 1) : null;
}

/** The scene shapes that move with a nudge, as a `reroute` move map for the live preview. */
export function nudgeMoves(scene: SceneJson, sel: Sel[], burst: Burst): Record<string, [number, number]> | null {
  if (burst.dx === 0 && burst.dy === 0) return null;
  const out: Record<string, [number, number]> = {};
  for (const i of nudgeItems(scene, sel)) {
    if (i.kind === "node" && containerOf(scene, i.box.id)) continue;
    for (const id of i.kind === "zone" ? zoneMoveShapes(scene, i.box.id) : [i.box.id]) out[id] = [burst.dx, burst.dy];
  }
  return Object.keys(out).length ? out : null;
}

export type Cursor = "grab" | "grabbing" | "crosshair" | "copy";

/** The pointer cursor on the canvas: `grabbing` while dragging, `copy` over a valid drop target, `grab` over a
 * node or zone header, `crosshair` on empty canvas. */
export function cursorFor(s: { dragging: boolean; overDropTarget: boolean; overElement: boolean }): Cursor {
  if (s.dragging) return s.overDropTarget ? "copy" : "grabbing";
  return s.overElement ? "grab" : "crosshair";
}

/** The frame drawn around a selection: the box itself, or the bounding box of several with their count. */
export function selectionFrame(boxes: Box[]): { box: Box; count: number } | null {
  if (boxes.length === 0) return null;
  const x = Math.min(...boxes.map((b) => b.x));
  const y = Math.min(...boxes.map((b) => b.y));
  const x2 = Math.max(...boxes.map((b) => b.x + b.w));
  const y2 = Math.max(...boxes.map((b) => b.y + b.h));
  return { box: { id: "selection", x, y, w: x2 - x, h: y2 - y }, count: boxes.length };
}

/** How long an op error toast stays (ms). */
export const TOAST_MS = 3000;
