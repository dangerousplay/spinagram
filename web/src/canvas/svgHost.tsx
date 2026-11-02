// The element that shows the diagram's SVG. A new render (the WASM preview, then the server render) is patched into
// the SVG that is already on screen instead of replacing it: elements that did not change stay the same DOM
// objects, so embedded fonts and images are not parsed and decoded again, and the host is never empty. The
// patching library is morphdom (small, no dependencies); elements are matched by `id` or, for a rendered item group, by `data-id`.
import { useLayoutEffect, useRef } from "react";
import morphdom from "morphdom";

/** Parse markup into a detached `<svg>` element, or null when it holds no root element. */
function parse(host: Element, markup: string): Element | null {
  const tpl = host.ownerDocument.createElement("template");
  tpl.innerHTML = markup;
  return tpl.content.firstElementChild;
}

const LONG = 160;
const brief = (v: string) => (v.length > LONG ? `${v.length}:${v.slice(0, 40)}:${v.slice(-20)}` : v);

/** What identifies an element without an `id`: its tag and attributes (and the text of a text-only element). An
 * `<image>` is identified by its href alone, so an icon that moves keeps its element. Long values are shortened:
 * a key only decides which old element is reused for a new one, and the content is compared and patched after that,
 * so a collision costs nothing. */
function signature(el: Element): string {
  if (el.localName === "image") return `image|${brief(el.getAttribute("href") ?? el.getAttribute("xlink:href") ?? "")}`;
  const attrs = Array.from(el.attributes, (a) => `${a.name}=${brief(a.value)}`).join("|");
  const text = el.childElementCount === 0 ? brief(el.textContent ?? "") : "";
  return `${el.localName}|${attrs}|${text}`;
}

/** Rendered item groups carry `data-id` (their diagram id), and that keys them: the key does not depend on what else
 * is in the diagram. Inside a group, and for the few elements outside any group (background, metadata), an element
 * is keyed by signature and by its place among elements sharing it *within that scope*, so adding one item adds one
 * group and never re-keys an element of another item (the images with their decoded pixels included). */
function keyElements(root: Element, into: Map<Element, string>): void {
  const walk = (parent: Element, scope: string, seen: Map<string, number>) => {
    for (const el of Array.from(parent.children)) {
      const group = el.getAttribute("data-id");
      const id = el.getAttribute("id");
      if (id) {
        walk(el, scope, seen); // ids key themselves
      } else if (group !== null) {
        const key = `g:${group}`;
        into.set(el, key);
        walk(el, key, new Map());
      } else {
        const sig = signature(el);
        const n = seen.get(sig) ?? 0;
        seen.set(sig, n + 1);
        into.set(el, `${scope}|${n}#${sig}`);
        walk(el, scope, seen);
      }
    }
  };
  walk(root, "", new Map());
}

function copyKeys(from: Element, to: Element, keys: Map<Element, string>): void {
  const k = keys.get(from);
  if (k !== undefined) keys.set(to, k);
  Array.from(from.children).forEach((c, i) => copyKeys(c, to.children[i], keys));
}

/** Put a copy of every element that is new (no counterpart in `cur`) at its place among `cur`'s children before
 * morphdom runs. Left to morphdom, a new element in front of the others makes it move (take out and put back) every
 * element in between, which an `<image>` answers by decoding again; with the new ones already in place the
 * children line up and morphdom only patches. Elements that merely changed order are still moved by morphdom. */
function insertNew(cur: Element, next: Element, keys: Map<Element, string>): void {
  const keyOf = (el: Element) => el.getAttribute("id") || keys.get(el);
  const kids = Array.from(cur.children);
  const at = new Map(kids.map((el, i) => [keyOf(el), i] as const));
  const taken = new Set<number>();
  let i = 0;
  for (const want of Array.from(next.children)) {
    while (i < kids.length && taken.has(i)) i++;
    const key = keyOf(want);
    const found = at.get(key);
    if (found === undefined) {
      const copy = want.cloneNode(true) as Element;
      copyKeys(want, copy, keys);
      cur.insertBefore(copy, i < kids.length ? kids[i] : null);
      continue;
    }
    taken.add(found);
    insertNew(kids[found], want, keys);
  }
}

/** Make `host` show `markup`. The parsed result is complete before the host changes, and changes are applied
 * in place; an update with identical content touches nothing. */
export function patchSvg(host: Element, markup: string): void {
  const next = parse(host, markup);
  const cur = host.firstElementChild;
  if (!next) {
    return; // nothing renderable: keep what is shown rather than blank the host
  }
  if (!cur || cur.nodeName.toLowerCase() !== next.nodeName.toLowerCase() || host.childElementCount !== 1) {
    host.replaceChildren(next);
    return;
  }
  const keys = new Map<Element, string>();
  keyElements(cur, keys);
  keyElements(next, keys);
  // Drop the old elements that have no counterpart first: morphdom moves a matched element past an unmatched one in
  // its way, and moving an <image> out of and into the tree is what this avoids.
  const keyOf = (el: Element) => el.getAttribute("id") || keys.get(el);
  const wanted = new Set(Array.from(next.querySelectorAll("*"), keyOf));
  for (const el of Array.from(cur.querySelectorAll("*"))) if (!wanted.has(keyOf(el))) el.remove();
  insertNew(cur, next, keys);
  morphdom(cur, next, {
    getNodeKey: (n) => (n.nodeType === 1 ? keyOf(n as Element) || undefined : undefined),
    onBeforeElUpdated: (from, to) => !from.isEqualNode(to),
  });
}

export default function SvgHost({ markup }: { markup: string }) {
  const ref = useRef<HTMLDivElement>(null);
  useLayoutEffect(() => {
    if (ref.current) patchSvg(ref.current, markup);
  }, [markup]);
  return <div ref={ref} />;
}
