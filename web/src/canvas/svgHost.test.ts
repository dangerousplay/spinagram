// The diagram host patches in place (toolbar iteration T24). Run: `bun test`.
import { afterAll, beforeAll, describe, expect, test } from "bun:test";
import { Window } from "happy-dom";

const win = new Window();
const G = globalThis as Record<string, unknown>;
const NAMES = ["document", "Node", "HTMLElement"] as const;
const saved = Object.fromEntries(NAMES.map((n) => [n, G[n]]));
let patchSvg: (host: Element, markup: string) => void;

beforeAll(async () => {
  Object.assign(globalThis, { document: win.document, Node: win.Node, HTMLElement: win.HTMLElement });
  patchSvg = (await import("./svgHost")).patchSvg;
});
afterAll(() => {
  for (const n of NAMES) if (saved[n] === undefined) delete G[n];
  else G[n] = saved[n];
});

// (happy-dom drops the content of <style> inside <svg>, so a <defs> stands in for the embedded font style)
const svg = (body: string) =>
  `<svg xmlns="http://www.w3.org/2000/svg" width="100" height="50"><defs><linearGradient id="g"><stop offset="0"/></linearGradient></defs><image id="logo" href="data:image/png;base64,AAAA"/>${body}</svg>`;
const host = () => win.document.createElement("div") as unknown as Element;

describe("patchSvg", () => {
  test("the first update shows the svg", () => {
    const h = host();
    patchSvg(h, svg('<rect id="a" x="1"/>'));
    expect(h.querySelector("rect")?.getAttribute("x")).toBe("1");
  });

  test("unchanged nodes stay the same DOM objects and changed ones change", () => {
    const h = host();
    patchSvg(h, svg('<rect id="a" x="1"/><rect id="b" x="5"/>'));
    const root = h.firstElementChild;
    const style = h.querySelector("defs");
    const image = h.querySelector("image");
    const a = h.querySelector("#a");
    const b = h.querySelector("#b");
    patchSvg(h, svg('<rect id="a" x="1"/><rect id="b" x="9"/>'));
    expect(h.firstElementChild).toBe(root);
    expect(h.querySelector("defs")).toBe(style);
    expect(h.querySelector("image")).toBe(image);
    expect(h.querySelector("#a")).toBe(a);
    expect(h.querySelector("#b")).toBe(b);
    expect(b?.getAttribute("x")).toBe("9");
  });

  test("a moved element keeps its identity (matched by id, not by position)", () => {
    const h = host();
    patchSvg(h, svg('<rect id="a" x="1"/><rect id="b" x="5"/>'));
    const a = h.querySelector("#a");
    patchSvg(h, svg('<rect id="b" x="5"/><rect id="a" x="1"/>'));
    expect(h.querySelector("#a")).toBe(a);
  });

  test("images keep their element when a box is added before them or the icon moves", () => {
    const img = (n: number, x: number) => `<image id="" x="${x}" href="data:image/png;base64,ICON${n}"/>`;
    const h = host();
    patchSvg(h, svg(`<rect x="1"/><text>a</text>${img(1, 10)}<rect x="2"/>${img(2, 50)}${img(1, 90)}`));
    const [i1, i2, i1b] = Array.from(h.querySelectorAll("image")).slice(1);
    // a new box (rect + text) lands before every icon, and the first icon moves
    patchSvg(h, svg(`<rect x="9"/><text>new</text><rect x="1"/><text>a</text>${img(1, 33)}<rect x="2"/>${img(2, 50)}${img(1, 90)}`));
    const after = Array.from(h.querySelectorAll("image")).slice(1);
    expect(after[0]).toBe(i1);
    expect(after[1]).toBe(i2);
    expect(after[2]).toBe(i1b);
    expect(after[0].getAttribute("x")).toBe("33");
  });

  test("an element added or removed near the top does not re-create the ones after it", () => {
    const body = '<rect x="1"/><text x="1">a</text><rect x="2"/><text x="2">b</text><path d="M0"/>';
    const h = host();
    patchSvg(h, svg(`<metadata id="hash">h1</metadata>${body}`));
    const before = Array.from(h.querySelectorAll("rect,text,path"));
    patchSvg(h, svg(body)); // the preview has no metadata element
    patchSvg(h, svg(`<metadata id="hash">h2</metadata><rect x="9"/><text x="9">n</text>${body}`));
    const after = Array.from(h.querySelectorAll("rect,text,path"));
    for (const el of before) expect(after.includes(el)).toBe(true);
    expect(after.length).toBe(before.length + 2);
    expect(h.querySelector("metadata")?.textContent).toBe("h2");
  });

  test("a changed element is patched and the rest of the diagram is untouched", () => {
    const h = host();
    patchSvg(h, svg('<rect x="1"/><rect x="2"/><rect x="3"/>'));
    const [r1, , r3] = Array.from(h.querySelectorAll("rect"));
    patchSvg(h, svg('<rect x="1"/><rect x="20"/><rect x="3"/>'));
    const now = Array.from(h.querySelectorAll("rect"));
    expect(now[0]).toBe(r1);
    expect(now[2]).toBe(r3);
    expect(now[1].getAttribute("x")).toBe("20");
  });

  test("added and removed elements appear and disappear", () => {
    const h = host();
    patchSvg(h, svg('<rect id="a"/>'));
    patchSvg(h, svg('<rect id="c"/>'));
    expect(h.querySelector("#a")).toBeNull();
    expect(h.querySelector("#c")).not.toBeNull();
  });

  test("the host is never empty while it updates", () => {
    const h = host();
    patchSvg(h, svg('<rect id="a" x="1"/>'));
    const seen: number[] = [];
    const mo = new win.MutationObserver(() => seen.push(h.childElementCount));
    mo.observe(h as unknown as Node, { childList: true, subtree: true });
    patchSvg(h, svg('<rect id="a" x="2"/>'));
    patchSvg(h, "");
    patchSvg(h, "not markup at all");
    expect(h.childElementCount).toBe(1);
    expect(seen.every((n) => n === 1)).toBe(true);
    expect(h.querySelector("rect")?.getAttribute("x")).toBe("2");
  });

  test("an identical update makes no mutation at all", async () => {
    const h = host();
    patchSvg(h, svg('<rect id="a" x="1"/>'));
    let n = 0;
    const mo = new win.MutationObserver((ms) => (n += ms.length));
    mo.observe(h as unknown as Node, { childList: true, subtree: true, attributes: true, characterData: true });
    patchSvg(h, svg('<rect id="a" x="1"/>'));
    await new Promise((r) => setTimeout(r, 10));
    expect(n).toBe(0);
  });

  // Rendered item groups (CTR-01): <g data-id="n0"> holds the box, <g data-id="n0@front"> its icon and title.
  const node = (id: string, x: number, icon: string) =>
    `<g data-id="${id}"><rect x="${x}" width="9"/></g><g data-id="${id}@front"><image x="${x}" href="data:image/png;base64,${icon}"/><text x="${x}">${id}</text></g>`;

  test("inserting an item group before the others never detaches an existing image", async () => {
    const h = host();
    patchSvg(h, svg(node("a", 10, "AAA") + node("b", 60, "BBB") + node("c", 110, "AAA")));
    const before = Array.from(h.querySelectorAll("image")).slice(1);
    const removed: string[] = [];
    const added: string[] = [];
    const mo = new win.MutationObserver((ms) => {
      for (const m of ms) {
        const images = (n: Element) => (n.localName === "image" ? [n] : Array.from(n.querySelectorAll?.("image") ?? []));
        for (const n of Array.from(m.removedNodes) as Element[]) removed.push(...images(n).map((i) => i.getAttribute("x") ?? ""));
        for (const n of Array.from(m.addedNodes) as Element[]) added.push(...images(n).map((i) => i.getAttribute("x") ?? ""));
      }
    });
    mo.observe(h as unknown as Node, { childList: true, subtree: true });
    // a new item is drawn before every other one (its own id and its own image)
    patchSvg(h, svg(node("new", 5, "NEW") + node("a", 10, "AAA") + node("b", 60, "BBB") + node("c", 110, "AAA")));
    await new Promise((r) => setTimeout(r, 10));
    const after = Array.from(h.querySelectorAll("image")).slice(1);
    expect(after.length).toBe(4);
    for (const img of before) expect(after.includes(img)).toBe(true);
    expect(removed).toEqual([]); // no existing image was taken out of the tree
    expect(added).toEqual(["5"]); // only the inserted item's image is new
  });

  test("deleting an item group removes only that item", () => {
    const h = host();
    patchSvg(h, svg(node("a", 10, "AAA") + node("b", 60, "BBB")));
    const b = h.querySelector('[data-id="b@front"] image');
    patchSvg(h, svg(node("b", 60, "BBB")));
    expect(h.querySelector('[data-id="a"]')).toBeNull();
    expect(h.querySelector('[data-id="b@front"] image')).toBe(b);
  });

  test("deleting the first item group never detaches the images of the items after it", async () => {
    const h = host();
    patchSvg(h, svg(node("a", 10, "AAA") + node("b", 60, "BBB") + node("c", 110, "CCC")));
    const removed: string[] = [];
    const mo = new win.MutationObserver((ms) => {
      for (const m of ms) {
        for (const n of Array.from(m.removedNodes) as Element[]) {
          const imgs = n.localName === "image" ? [n] : Array.from(n.querySelectorAll?.("image") ?? []);
          removed.push(...imgs.map((i) => i.getAttribute("x") ?? ""));
        }
      }
    });
    mo.observe(h as unknown as Node, { childList: true, subtree: true });
    patchSvg(h, svg(node("b", 60, "BBB") + node("c", 110, "CCC")));
    await new Promise((r) => setTimeout(r, 10));
    expect(removed.filter((x) => x !== "10")).toEqual([]); // no image of a remaining item leaves the tree
  });

  test("a group moved in the order keeps its elements (keyed by data-id, not position)", () => {
    const h = host();
    patchSvg(h, svg(node("a", 10, "AAA") + node("b", 60, "BBB")));
    const a = h.querySelector('[data-id="a@front"] image');
    patchSvg(h, svg(node("b", 60, "BBB") + node("a", 10, "AAA")));
    expect(h.querySelector('[data-id="a@front"] image')).toBe(a);
  });
});
