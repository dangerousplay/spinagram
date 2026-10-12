// Theme and pack catalog logic (spec: .specs/features/catalog-previews/spec.md). Run: `bun test`.
import { describe, expect, test } from "bun:test";
import type { Pack, ThemeEntry } from "./api";
import { filterPacks, filterThemes, packSections, sampleIcons, themeSections } from "./catalog";

const theme = (ref: string, name: string, builtin: boolean, active = false): ThemeEntry => ({
  ref,
  name,
  builtin,
  active,
  error: null,
});
const pack = (name: string, title: string, fetched: boolean): Pack => ({
  name,
  title,
  version: "1",
  origin: "builtin",
  license: "",
  homepage: "",
  source: "npm",
  fetched,
  count: fetched ? 100 : 0,
  fetching: false,
  error: null,
});

const THEMES = [theme("active", "corp", false, true), theme("default", "default", true), theme("night", "Night Ops", true)];
const PACKS = [pack("aws", "AWS Architecture Icons", true), pack("gcp", "Google Cloud Icons", false), pack("k8s", "Kubernetes Icons", true)];

describe("PREV-06 theme search", () => {
  test("every term must match the name or ref, case-insensitive", () => {
    expect(filterThemes(THEMES, "").map((t) => t.ref)).toEqual(["active", "default", "night"]);
    expect(filterThemes(THEMES, "NIGHT").map((t) => t.ref)).toEqual(["night"]);
    expect(filterThemes(THEMES, "act").map((t) => t.ref)).toEqual(["active"]);
    expect(filterThemes(THEMES, "night corp")).toEqual([]);
  });
});

describe("PREV-10 pack search", () => {
  test("every term must match the name or title, case-insensitive", () => {
    expect(filterPacks(PACKS, "icons").map((p) => p.name)).toEqual(["aws", "gcp", "k8s"]);
    expect(filterPacks(PACKS, "google").map((p) => p.name)).toEqual(["gcp"]);
    expect(filterPacks(PACKS, "k8s kube").map((p) => p.name)).toEqual(["k8s"]);
    expect(filterPacks(PACKS, "aws google")).toEqual([]);
  });
});

describe("PREV-07 sample icons", () => {
  test("12 icons at evenly spaced positions", () => {
    const icons = Array.from({ length: 120 }, (_, i) => i);
    expect(sampleIcons(icons)).toEqual([0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100, 110]);
    expect(sampleIcons(Array.from({ length: 13 }, (_, i) => i))).toEqual([0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]);
  });
  test("every icon when the pack has 12 or fewer", () => {
    expect(sampleIcons([1, 2, 3])).toEqual([1, 2, 3]);
    expect(sampleIcons(Array.from({ length: 12 }, (_, i) => i)).length).toBe(12);
    expect(sampleIcons([])).toEqual([]);
  });
});

describe("PREV-05, PREV-09 sections", () => {
  test("themes: Built-in then Custom", () => {
    expect(themeSections(THEMES).map((s) => [s.label, s.items.map((t) => t.ref)])).toEqual([
      ["Built-in", ["default", "night"]],
      ["Custom", ["active"]],
    ]);
  });
  test("packs: Downloaded then Not downloaded", () => {
    expect(packSections(PACKS).map((s) => [s.label, s.items.map((p) => p.name)])).toEqual([
      ["Downloaded", ["aws", "k8s"]],
      ["Not downloaded", ["gcp"]],
    ]);
  });
  test("empty sections are left out", () => {
    expect(themeSections([THEMES[1]]).map((s) => s.label)).toEqual(["Built-in"]);
    expect(packSections([]).length).toBe(0);
  });
});
