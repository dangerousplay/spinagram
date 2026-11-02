// The YAML source map comes from Rust as UTF-8 byte ranges; CodeMirror counts UTF-16 units.
export type SrcMap = Record<string, [number, number]>;

/** UTF-16 offset in `text` of a UTF-8 byte offset (clamped to the text; an offset inside a character rounds up). */
export function byteToIndex(text: string, byte: number): number {
  let bytes = 0;
  let i = 0;
  while (i < text.length && bytes < byte) {
    const cp = text.codePointAt(i)!;
    bytes += cp < 0x80 ? 1 : cp < 0x800 ? 2 : cp < 0x10000 ? 3 : 4;
    i += cp > 0xffff ? 2 : 1;
  }
  return i;
}

/** The editor range `{from, to}` (UTF-16) of an element's YAML entry, or null for an id the map lacks. */
export function yamlRange(text: string, map: SrcMap, id: string): { from: number; to: number } | null {
  const r = map[id];
  return r ? { from: byteToIndex(text, r[0]), to: byteToIndex(text, r[1]) } : null;
}

/** The value of `key` (`title`, `label`) in the text of one YAML entry (block or flow), or null. Quoted values are
 * decoded; the entry text comes from the source map. */
export function entryField(entry: string, key: string): string | null {
  const m = entry.match(new RegExp(`(?:^|[\\s{,])${key}:[ \\t]*("(?:[^"\\\\]|\\\\.)*"|'(?:[^']|'')*'|[^,}\\n#]+)`));
  if (!m) return null;
  const v = m[1].trim();
  if (v.startsWith('"')) {
    try {
      return JSON.parse(v) as string;
    } catch {
      return v.slice(1, -1);
    }
  }
  return v.startsWith("'") ? v.slice(1, -1).replace(/''/g, "'") : v;
}

/** The label of an edge from the text of its YAML entry: a mapping's `label`, or the text after the colon of a string
 * edge (`"a -> b: label"`, as the loader's `parse_edge` reads it). Empty when it has none. */
export function edgeLabelOf(entry: string): string {
  const t = entry.trim();
  if (t.startsWith("{") || /(^|\n)\s*(- )?(from|to):/.test(t)) return entryField(t, "label") ?? "";
  let text = t;
  if (t.startsWith('"')) {
    try {
      text = JSON.parse(t) as string;
    } catch {
      text = t.slice(1, -1);
    }
  } else if (t.startsWith("'")) text = t.slice(1, -1).replace(/''/g, "'");
  const op = /<->|->|<-|--/.exec(text);
  if (!op) return "";
  let rest = text.slice(op.index + op[0].length).trimStart();
  const from = rest.startsWith("zone:") ? 5 : 0;
  const colon = rest.indexOf(":", from);
  if (colon < 0) return "";
  rest = rest.slice(colon + 1).trim();
  return rest;
}

/** Whether an edge entry is a mapping (`{from, to, ...}` or block keys) and not the string form `"a -> b: label"`. */
export const edgeIsMapping = (entry: string): boolean => {
  const t = entry.trim();
  return t.startsWith("{") || /(^|\n)\s*(- )?(from|to):/.test(t);
};

/** A key of an edge entry (`route`, `dashed`, `color`, ...), or null: a string edge has none of them. */
export const edgeField = (entry: string, key: string): string | null => (edgeIsMapping(entry) ? entryField(entry, key) : null);
