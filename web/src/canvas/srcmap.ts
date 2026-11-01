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
