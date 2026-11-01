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
