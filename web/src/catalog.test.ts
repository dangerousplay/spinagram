// Diagram catalog logic (spec: .specs/features/diagram-catalog/spec.md). Run: `bun test`.
import { describe, expect, test } from "bun:test";
import type { DiagramRef } from "./api";
import {
  allTags,
  filterDiagrams,
  groupByCategory,
  MAX_RECENTS,
  pushRecent,
  recentStore,
  UNCATEGORISED,
  visibleRecents,
} from "./catalog";

const d = (id: string, title: string, category: string, tags: string[], subtitle: string | null = null): DiagramRef => ({
  key: `${id.toLowerCase()}.py#${id}`,
  id,
  title,
  auto: true,
  subtitle,
  category,
  tags,
});

const AWS01 = d("AWS01", "Three-tier web application", "AWS", ["aws"], "Edge, web, app and data tiers");
const AWS02 = d("AWS02", "Hub-and-spoke networking", "AWS", ["aws", "networking"]);
const GCP01 = d("GCP01", "Global web application", "Google Cloud", ["gcp", "kubernetes"]);
const K8S01 = d("K8S01", "Anatomy of a workload", "Kubernetes", ["kubernetes"]);
const NOTE = d("N1", "Release flow", "", []);
const ALL = [AWS01, AWS02, GCP01, K8S01, NOTE];
const ids = (list: DiagramRef[]) => list.map((x) => x.id);

describe("META-15 text search", () => {
  test("empty query keeps everything", () => {
    expect(ids(filterDiagrams(ALL, "  ", []))).toEqual(["AWS01", "AWS02", "GCP01", "K8S01", "N1"]);
  });
  test("matches id, title, subtitle, category and tags, case-insensitive", () => {
    expect(ids(filterDiagrams(ALL, "gcp01", []))).toEqual(["GCP01"]);
    expect(ids(filterDiagrams(ALL, "HUB-AND", []))).toEqual(["AWS02"]);
    expect(ids(filterDiagrams(ALL, "data tiers", []))).toEqual(["AWS01"]);
    expect(ids(filterDiagrams(ALL, "google", []))).toEqual(["GCP01"]);
    expect(ids(filterDiagrams(ALL, "kube", []))).toEqual(["GCP01", "K8S01"]);
  });
  test("every term must match", () => {
    expect(ids(filterDiagrams(ALL, "web aws", []))).toEqual(["AWS01"]);
    expect(ids(filterDiagrams(ALL, "web azure", []))).toEqual([]);
  });
});

describe("META-16 tag chips", () => {
  test("a diagram must carry every selected tag", () => {
    expect(ids(filterDiagrams(ALL, "", ["aws"]))).toEqual(["AWS01", "AWS02"]);
    expect(ids(filterDiagrams(ALL, "", ["aws", "networking"]))).toEqual(["AWS02"]);
    expect(ids(filterDiagrams(ALL, "", ["gcp", "aws"]))).toEqual([]);
  });
  test("chips combine with the text search", () => {
    expect(ids(filterDiagrams(ALL, "global", ["kubernetes"]))).toEqual(["GCP01"]);
  });
  test("tag counts list every tag, most used first", () => {
    expect(allTags(ALL)).toEqual([
      { tag: "aws", count: 2 },
      { tag: "kubernetes", count: 2 },
      { tag: "gcp", count: 1 },
      { tag: "networking", count: 1 },
    ]);
  });
});

describe("META-14 category sections", () => {
  test("one section per category, sorted by name, Uncategorised last", () => {
    const groups = groupByCategory([NOTE, K8S01, GCP01, AWS02, AWS01]);
    expect(groups.map((g) => g.label)).toEqual(["AWS", "Google Cloud", "Kubernetes", UNCATEGORISED]);
    expect(groups.map((g) => ids(g.diagrams))).toEqual([["AWS02", "AWS01"], ["GCP01"], ["K8S01"], ["N1"]]);
    expect(groups[3].category).toBe("");
  });
});

describe("META-23 recording recents", () => {
  test("newest first, no duplicates", () => {
    expect(pushRecent(["b", "a"], "c")).toEqual(["c", "b", "a"]);
    expect(pushRecent(["b", "a", "c"], "a")).toEqual(["a", "b", "c"]);
    expect(pushRecent(["a"], "a")).toEqual(["a"]);
  });
  test("keeps at most 10", () => {
    expect(MAX_RECENTS).toBe(10);
    const many = Array.from({ length: 10 }, (_, i) => `k${i}`);
    const got = pushRecent(many, "new");
    expect(got.length).toBe(10);
    expect(got[0]).toBe("new");
    expect(got).not.toContain("k9");
  });
});

describe("META-25 stale recents", () => {
  test("keys missing from the workspace are omitted", () => {
    expect(visibleRecents(["gone", "b", "a"], new Set(["a", "b"]))).toEqual(["b", "a"]);
  });
});

describe("META-26 storage", () => {
  const memoryStorage = () => {
    const data = new Map<string, string>();
    return {
      getItem: (k: string) => data.get(k) ?? null,
      setItem: (k: string, v: string) => void data.set(k, v),
    } as unknown as Storage;
  };
  test("recents persist through the storage", () => {
    const storage = memoryStorage();
    recentStore(storage).save(["b", "a"]);
    expect(recentStore(storage).load()).toEqual(["b", "a"]);
  });
  test("a throwing or missing storage keeps recents for the session", () => {
    const broken = {
      getItem: () => {
        throw new Error("denied");
      },
      setItem: () => {
        throw new Error("denied");
      },
    } as unknown as Storage;
    for (const storage of [broken, null]) {
      const store = recentStore(storage);
      expect(store.load()).toEqual([]);
      expect(() => store.save(["a"])).not.toThrow();
      expect(store.load()).toEqual(["a"]);
    }
  });
  test("corrupt stored data loads as empty", () => {
    const storage = memoryStorage();
    storage.setItem("spinagram:recent", "{not json");
    expect(recentStore(storage).load()).toEqual([]);
    storage.setItem("spinagram:recent", JSON.stringify([1, "a"]));
    expect(recentStore(storage).load()).toEqual(["a"]);
  });
});
