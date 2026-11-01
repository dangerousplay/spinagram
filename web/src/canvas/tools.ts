// The canvas tools and toolbar actions: ids, labels and keys. The toolbar (Toolbar.tsx) and the key table
// (interaction.ts) are built from these, and icons.tsx maps every id here to an icon.

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
] as const;

export type ActionId = (typeof ACTIONS)[number]["id"];
