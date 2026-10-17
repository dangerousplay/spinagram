// The code panel's tabs as plain data: what is on disk, what the user typed, and conflicts between them.
// Pure functions so the transitions are tested with `bun test` (editor.test.ts).

export type Language = "python" | "css" | "yaml" | "text";
export type SourceFile = { path: string; language: Language; text: string; version: string };
export type Conflict = { text: string; version: string };
export type Tab = {
  path: string;
  language: Language;
  text: string; // the buffer
  disk: string; // the text last read from or written to disk
  version: string; // the version of `disk`, sent with a save
  dirty: boolean;
  conflict: Conflict | null; // the disk changed while the buffer was modified
  removed: boolean; // the file is no longer part of the diagram's source
};

export function languageOf(path: string): Language {
  const ext = path.slice(path.lastIndexOf(".")).toLowerCase();
  return ext === ".py" ? "python" : ext === ".css" ? "css" : ext === ".yaml" || ext === ".yml" ? "yaml" : "text";
}

function fresh(f: SourceFile): Tab {
  return { path: f.path, language: f.language, text: f.text, disk: f.text, version: f.version, dirty: false, conflict: null, removed: false };
}

export const fromSource = (files: SourceFile[]): Tab[] => files.map(fresh);

export const anyDirty = (tabs: Tab[]): boolean => tabs.some((t) => t.dirty);

/** The user typed: modified while the buffer differs from the disk text. */
export function edit(t: Tab, text: string): Tab {
  return { ...t, text, dirty: text !== t.disk };
}

/** The buffer was written; ``version`` is what the server returned. */
export function saved(t: Tab, version: string): Tab {
  return { ...t, disk: t.text, version, dirty: false, conflict: null };
}

/** A newer read of the file: a clean tab follows it, a modified one keeps its text and records a conflict. */
export function disk(t: Tab, f: SourceFile): Tab {
  if (f.version === t.version) return t;
  if (!t.dirty) return { ...fresh(f), path: t.path };
  return { ...t, conflict: { text: f.text, version: f.version } };
}

/** Resolve a conflict with the disk text. */
export function reload(t: Tab): Tab {
  return t.conflict ? { ...t, text: t.conflict.text, disk: t.conflict.text, version: t.conflict.version, dirty: false, conflict: null } : t;
}

/** Resolve a conflict with the buffer: it now stands against the disk version, so the next save is accepted. */
export function keepMine(t: Tab): Tab {
  if (!t.conflict) return t;
  const { text, version } = t.conflict;
  return { ...t, disk: text, version, dirty: t.text !== text, conflict: null };
}

/** Fold a refetched source into the open tabs: same order, new files appended, missing files marked removed. */
export function merge(tabs: Tab[], files: SourceFile[]): Tab[] {
  const byPath = new Map(files.map((f) => [f.path, f]));
  const out = tabs.map((t) => {
    const f = byPath.get(t.path);
    return f ? { ...disk(t, f), removed: false } : { ...t, removed: true };
  });
  for (const f of files) if (!tabs.some((t) => t.path === f.path)) out.push(fresh(f));
  return out;
}

/** 1-based line of the first string literal equal to ``title`` ("title" or 'title'), or null. */
export function jumpLine(text: string, title: string): number | null {
  if (!title) return null;
  const lines = text.split("\n");
  const i = lines.findIndex((l) => l.includes(`"${title}"`) || l.includes(`'${title}'`));
  return i < 0 ? null : i + 1;
}
