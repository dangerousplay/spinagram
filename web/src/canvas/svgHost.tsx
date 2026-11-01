// The element that shows the diagram's SVG. A new render (the WASM preview, then the server render) is patched into
// the SVG that is already on screen instead of replacing it: elements that did not change stay the same DOM
// objects, so embedded fonts and images are not parsed and decoded again, and the host is never empty. The
// patching library is morphdom (small, no dependencies); elements are matched by `id`.
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

/** Rendered SVG elements mostly have no `id`, so adding one box would shift every later element by position and
 * re-create all of them (the images with their decoded pixels included). Matching by signature, with the place among
 * elements sharing it, keeps every element that did not change and re-creates only those that did. */
function keyElements(root: Element, into: Map<Element, string>): void {
  const seen = new Map<string, number>();
  for (const el of Array.from(root.querySelectorAll("*"))) {
    if (el.getAttribute("id")) continue; // ids key themselves
    const sig = signature(el);
    const n = seen.get(sig) ?? 0;
    seen.set(sig, n + 1);
    into.set(el, `${n}#${sig}`);
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
