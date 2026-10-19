// Inspector hover label (spec: .specs/features/inspector-declarations/spec.md, HIL-02/03/04). Run: `bun test`.
import { describe, expect, test } from "bun:test";
import type { CssElement, StyleReport } from "./api";
import { CHIP_GAP, CHIP_H, chip } from "./inspect";

const el = (key: string, type: string, id: string | null, attrs: Record<string, string> = {}, classes: string[] = []): CssElement => ({
  key, type, kinds: [type], id, classes, attrs, parent: null, styles: {}, trace: {}, declaration: null,
});

const report: StyleReport = {
  diagram: "L01",
  title: "t",
  styled: false,
  sheets: [],
  elements: [
    el("node:users", "node", "users", { label: "Applications" }),
    el("node:top", "node", "top", {}, ["hot"]),
    el("edge:0", "edge", null, { from: "users", to: "alb" }),
  ],
  unused: [],
  warnings: [],
  geometry: {
    "node:users": { box: [100.4, 200, 181.6, 64.3] },
    "node:top": { box: [50, 10, 80, 40] },
    "edge:0": { points: [[300, 230], [400, 230]], route: "straight" },
  },
  size: [1920, 1080],
};

describe("HIL-02 node label with size", () => {
  test("element label, then W × H rounded, above the box", () => {
    const c = chip(report, "node:users", 1)!;
    expect(c.text).toBe("node#users 182 × 64");
    expect(c.below).toBe(false);
    expect(c.x).toBe(100.4);
    expect(c.y).toBe(200 - CHIP_GAP - CHIP_H);
  });
  test("chip size and gap follow the zoom so it reads the same on screen", () => {
    const c = chip(report, "node:users", 0.5)!;
    expect(c.h).toBe(CHIP_H / 0.5);
    expect(c.y).toBe(200 - (CHIP_GAP + CHIP_H) / 0.5);
  });
  test("classes are part of the label", () => {
    expect(chip(report, "node:top", 1)!.text).toBe("node#top.hot 80 × 40");
  });
});

describe("HIL-03 edge label without size", () => {
  test("edge a → b", () => {
    expect(chip(report, "edge:0", 1)!.text).toBe("edge users → alb");
  });
});

describe("HIL-04 below when no room above", () => {
  test("a box near the top edge gets the chip under it", () => {
    const c = chip(report, "node:top", 1)!;
    expect(c.below).toBe(true);
    expect(c.y).toBe(10 + 40 + CHIP_GAP);
  });
  test("the gap counts: below as soon as chip and gap do not fit above, above when they exactly fit", () => {
    const at = (top: number) =>
      chip({ ...report, geometry: { ...report.geometry, "node:top": { box: [50, top, 80, 40] } } }, "node:top", 1)!.below;
    expect(at(CHIP_H + CHIP_GAP - 1)).toBe(true); // the chip alone would fit; with the gap it does not
    expect(at(CHIP_H + CHIP_GAP)).toBe(false);
  });
});
