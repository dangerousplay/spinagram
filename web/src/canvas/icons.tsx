// One place that maps every canvas tool, toolbar action and palette item to an icon (lucide-react, ISC licence;
// each icon is imported by name so the bundle holds only these).
import {
  ArrowLeftRight,
  ArrowRightLeft,
  Box,
  Circle,
  CircleHelp,
  Columns2,
  Copy,
  Database,
  Diamond,
  Equal,
  FileText,
  FolderInput,
  Group,
  Hand,
  ListTree,
  MousePointer2,
  Palette,
  PanelBottom,
  PanelLeftRightDashed,
  Pill,
  Play,
  Redo2,
  RectangleHorizontal,
  Rows2,
  Shapes,
  Spline,
  Square,
  SquareDashed,
  StickyNote,
  Trash2,
  Type,
  Undo2,
  Ungroup,
  type LucideIcon,
} from "lucide-react";
import { SHAPE_KINDS, type PaletteItem } from "./palette";
import { QUICK_ACTIONS } from "./props";
import { ACTIONS, TOOLS } from "./tools";

/** Palette basics that are not shape kinds. */
export const CONTAINER_ICON_NAMES = ["zone", "row", "column"] as const;

const ICONS: Record<string, LucideIcon> = {
  // tools
  select: MousePointer2,
  hand: Hand,
  connect: Spline,
  // actions
  "group-row": Group,
  "group-column": Group,
  ungroup: Ungroup,
  delete: Trash2,
  undo: Undo2,
  redo: Redo2,
  palette: Shapes,
  elements: ListTree,
  help: CircleHelp,
  dock: PanelBottom,
  // quick actions of the properties panel (the ones that are also tools or actions share those icons)
  duplicate: Copy,
  "move-to-zone": FolderInput,
  style: Palette,
  reverse: ArrowLeftRight,
  parallel: Equal,
  // containers
  zone: SquareDashed,
  row: Columns2, // boxes side by side
  column: Rows2, // boxes stacked
  // shape kinds (box and text double as tools)
  box: Square,
  text: Type,
  pill: Pill,
  note: StickyNote,
  diamond: Diamond,
  decision: Diamond,
  process: RectangleHorizontal,
  io: ArrowRightLeft,
  document: FileText,
  data: Database,
  predefined: PanelLeftRightDashed,
  terminator: Pill,
  state: Circle,
  action: Play,
  object: Box,
};

/** Every name `EditorIcon` draws: the tools, the actions, the quick actions, the containers and the shape kinds. */
export const ICON_NAMES: string[] = [...new Set([...TOOLS.map((t) => t.id), ...ACTIONS.map((a) => a.id), ...QUICK_ACTIONS.map((q) => q.id), ...CONTAINER_ICON_NAMES, ...SHAPE_KINDS])];

export const hasIcon = (name: string): boolean => name in ICONS;

/** The icon name of a palette item, or null for an icon-pack item (it shows its pack image). */
export function iconNameOf(item: PaletteItem): string | null {
  return item.type === "icon" ? null : item.type === "shape" ? item.kind : item.type === "zoneStyle" ? "zone" : item.type;
}

export function EditorIcon({ name, size = 16, className }: { name: string; size?: number; className?: string }) {
  const Icon = ICONS[name] ?? Square;
  return <Icon size={size} strokeWidth={1.75} className={className} aria-hidden />;
}
