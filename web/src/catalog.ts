// Catalog logic: search, tag filter, sections and recents for diagrams; search, sections and icon samples for
// themes and packs. Pure functions tested by `bun test` (catalog.test.ts, previews.test.ts).
import type { DiagramRef, Pack, ThemeEntry } from "./api";

export const UNCATEGORISED = "Uncategorised";
export const MAX_RECENTS = 10;
const RECENT_KEY = "spinagram:recent";

/** Every whitespace-separated term is a substring of the id, title, subtitle, category or a tag. */
export function matchesQuery(d: DiagramRef, query: string): boolean {
  return matchesTerms([d.id, d.title, d.subtitle ?? "", d.category, ...d.tags], query);
}

/** Diagrams matching the query that carry every selected tag. */
export function filterDiagrams(list: DiagramRef[], query: string, tags: string[]): DiagramRef[] {
  return list.filter((d) => matchesQuery(d, query) && tags.every((t) => d.tags.includes(t)));
}

export type CategoryGroup = { category: string; label: string; diagrams: DiagramRef[] };

/** One section per category, sorted by name, "Uncategorised" last; diagrams keep their order. */
export function groupByCategory(list: DiagramRef[]): CategoryGroup[] {
  const groups = new Map<string, CategoryGroup>();
  for (const d of list) {
    const g = groups.get(d.category) ?? { category: d.category, label: d.category || UNCATEGORISED, diagrams: [] };
    g.diagrams.push(d);
    groups.set(d.category, g);
  }
  return [...groups.values()].sort((a, b) =>
    !a.category !== !b.category ? (a.category ? -1 : 1) : a.label.localeCompare(b.label),
  );
}

/** Every tag with its number of diagrams, most used first, then A–Z. */
export function allTags(list: DiagramRef[]): { tag: string; count: number }[] {
  const counts = new Map<string, number>();
  for (const d of list) for (const t of d.tags) counts.set(t, (counts.get(t) ?? 0) + 1);
  return [...counts]
    .map(([tag, count]) => ({ tag, count }))
    .sort((a, b) => b.count - a.count || a.tag.localeCompare(b.tag));
}

/** ``key`` becomes the newest entry; no duplicates, at most ``max`` entries. */
export function pushRecent(keys: string[], key: string, max = MAX_RECENTS): string[] {
  return [key, ...keys.filter((k) => k !== key)].slice(0, max);
}

/** Recent keys whose diagram is still in the workspace. */
export function visibleRecents(keys: string[], known: Set<string>): string[] {
  return keys.filter((k) => known.has(k));
}

function browserStorage(): Storage | null {
  try {
    return typeof window === "undefined" ? null : window.localStorage;
  } catch {
    return null; // blocked site data
  }
}

/** Recent diagram keys in browser storage; falls back to memory when storage is missing or throws. */
export function recentStore(storage: Storage | null = browserStorage()) {
  let memory: string[] = [];
  return {
    load(): string[] {
      try {
        const raw = storage?.getItem(RECENT_KEY);
        if (raw == null) return memory;
        const parsed: unknown = JSON.parse(raw);
        return Array.isArray(parsed) ? parsed.filter((k): k is string => typeof k === "string") : [];
      } catch {
        return memory;
      }
    },
    save(keys: string[]): void {
      memory = keys;
      try {
        storage?.setItem(RECENT_KEY, JSON.stringify(keys));
      } catch {
        /* keep the session copy */
      }
    },
  };
}

// themes and icon packs ----------------------------------------------------------------------------

/** Every whitespace-separated term of ``query`` is a substring of one of ``fields`` (case-insensitive). */
export function matchesTerms(fields: string[], query: string): boolean {
  const terms = query.toLowerCase().split(/\s+/).filter(Boolean);
  const lower = fields.map((f) => f.toLowerCase());
  return terms.every((t) => lower.some((f) => f.includes(t)));
}

export function filterThemes(themes: ThemeEntry[], query: string): ThemeEntry[] {
  return themes.filter((t) => matchesTerms([t.name, t.ref], query));
}

export function filterPacks(packs: Pack[], query: string): Pack[] {
  return packs.filter((p) => matchesTerms([p.name, p.title], query));
}

/** ``n`` items at evenly spaced positions (all of them when there are ``n`` or fewer). */
export function sampleIcons<T>(icons: T[], n = 12): T[] {
  if (icons.length <= n) return icons;
  return Array.from({ length: n }, (_, i) => icons[Math.floor((i * icons.length) / n)]);
}

export type Section<T> = { label: string; items: T[] };

function sections<T>(parts: [string, T[]][]): Section<T>[] {
  return parts.filter(([, items]) => items.length > 0).map(([label, items]) => ({ label, items }));
}

/** Built-in themes, then the session's custom theme. */
export function themeSections(themes: ThemeEntry[]): Section<ThemeEntry>[] {
  return sections([
    ["Built-in", themes.filter((t) => t.builtin)],
    ["Custom", themes.filter((t) => !t.builtin)],
  ]);
}

/** Downloaded packs, then the rest. */
export function packSections(packs: Pack[]): Section<Pack>[] {
  return sections([
    ["Downloaded", packs.filter((p) => p.fetched)],
    ["Not downloaded", packs.filter((p) => !p.fetched)],
  ]);
}
