// Inspector logic without React: element names and the hover label (chip) placed in scene coordinates.
import type { CssElement, StyleReport } from "./api";

/** Chip height and its gap to the box, in screen px: divided by the zoom so they read the same at any scale. */
export const CHIP_H = 22;
export const CHIP_GAP = 4;

export function elementLabel(e: CssElement): string {
  const cls = e.classes.map((c) => `.${c}`).join("");
  if (e.type === "edge") return `edge${cls} ${e.attrs.from} → ${e.attrs.to}`;
  return `${e.type}${e.id ? `#${e.id}` : ""}${cls}`;
}

export type Chip = { text: string; x: number; y: number; h: number; below: boolean };

/** The hover label of `key`: its name, plus `W × H` for boxes; above the box, or below it near the top edge. */
export function chip(report: StyleReport, key: string, scale: number): Chip | null {
  const el = report.elements.find((e) => e.key === key);
  const g = report.geometry[key];
  if (!el || !g) return null;
  let box = g.box ?? g.label;
  if (!box && g.points?.length) {
    const xs = g.points.map((p) => p[0]);
    const ys = g.points.map((p) => p[1]);
    box = [Math.min(...xs), Math.min(...ys), Math.max(...xs) - Math.min(...xs), Math.max(...ys) - Math.min(...ys)];
  }
  if (!box) return null;
  const [x, y, w, h] = box;
  const text = g.box ? `${elementLabel(el)} ${Math.round(w)} × ${Math.round(h)}` : elementLabel(el);
  const ch = CHIP_H / scale;
  const gap = CHIP_GAP / scale;
  const below = y - gap - ch < 0;
  return { text, x, y: below ? y + h + gap : y - gap - ch, h: ch, below };
}
