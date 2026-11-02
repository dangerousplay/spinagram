// Remembered open/closed state of the palette (PAL-03). The palette starts collapsed; a storage that is missing
// or throws leaves it collapsed.
export const PALETTE_OPEN_KEY = "spinagram.palette.open";

type Store = Pick<Storage, "getItem" | "setItem">;

function defaultStore(): Store | null {
  try {
    return localStorage;
  } catch {
    return null;
  }
}

export function readPaletteOpen(store: Store | null = defaultStore()): boolean {
  try {
    return store?.getItem(PALETTE_OPEN_KEY) === "1";
  } catch {
    return false;
  }
}

export function writePaletteOpen(open: boolean, store: Store | null = defaultStore()): void {
  try {
    store?.setItem(PALETTE_OPEN_KEY, open ? "1" : "0");
  } catch {
    /* storage unavailable: the state still holds for this page */
  }
}

// Remembered collapsed state of the palette's categories: an object of category id -> collapsed. A category with no
// entry (or a storage that is missing, throws or holds something else) takes its default (`defaultCollapsed`).
export const PALETTE_COLLAPSED_KEY = "spinagram.palette.collapsed";

export type CollapsedState = Record<string, boolean>;

export function readCollapsed(store: Store | null = defaultStore()): CollapsedState {
  try {
    const raw = JSON.parse(store?.getItem(PALETTE_COLLAPSED_KEY) ?? "null");
    if (!raw || typeof raw !== "object" || Array.isArray(raw)) return {};
    return Object.fromEntries(Object.entries(raw).filter(([, v]) => typeof v === "boolean")) as CollapsedState;
  } catch {
    return {};
  }
}

export function writeCollapsed(state: CollapsedState, store: Store | null = defaultStore()): void {
  try {
    store?.setItem(PALETTE_COLLAPSED_KEY, JSON.stringify(state));
  } catch {
    /* storage unavailable: the state still holds for this page */
  }
}

// Remembered dock of the canvas toolbar: along the left edge (the default) or at the bottom. A storage that is
// missing, throws or holds anything else gives the left dock.
export const DOCK_KEY = "spinagram.toolbar.dock";

export type Dock = "left" | "bottom";

export function readDock(store: Store | null = defaultStore()): Dock {
  try {
    return store?.getItem(DOCK_KEY) === "bottom" ? "bottom" : "left";
  } catch {
    return "left";
  }
}

export function writeDock(dock: Dock, store: Store | null = defaultStore()): void {
  try {
    store?.setItem(DOCK_KEY, dock);
  } catch {
    /* storage unavailable: the dock still holds for this page */
  }
}

export const otherDock = (dock: Dock): Dock => (dock === "left" ? "bottom" : "left");

// Remembered state of the Elements panel: whether it is open, and whether it is pinned. Unpinned, selecting an element
// opens it; pinned, it stays as the user left it (open or closed). Anything missing or malformed gives closed and
// unpinned.
export const ELEMENTS_KEY = "spinagram.elements.panel";

export type ElementsPref = { open: boolean; pinned: boolean };
export const ELEMENTS_DEFAULT: ElementsPref = { open: false, pinned: false };

export function readElements(store: Store | null = defaultStore()): ElementsPref {
  try {
    const raw = JSON.parse(store?.getItem(ELEMENTS_KEY) ?? "null");
    if (!raw || typeof raw !== "object") return ELEMENTS_DEFAULT;
    return { open: raw.open === true, pinned: raw.pinned === true };
  } catch {
    return ELEMENTS_DEFAULT;
  }
}

export function writeElements(pref: ElementsPref, store: Store | null = defaultStore()): void {
  try {
    store?.setItem(ELEMENTS_KEY, JSON.stringify(pref));
  } catch {
    /* storage unavailable: the state still holds for this page */
  }
}

/** The panel's state after the selection changed: unpinned, a selection opens it; pinned, nothing changes. */
export const afterSelection = (pref: ElementsPref, selected: boolean): ElementsPref => (selected && !pref.pinned && !pref.open ? { ...pref, open: true } : pref);
