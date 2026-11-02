// The toolbar stays mounted while a save re-fetches the scene (insert-redraw iteration, T35). Run: `bun test`.
import { afterAll, beforeAll, describe, expect, test } from "bun:test";
import { Window } from "happy-dom";
import { createElement } from "react";
import { flushSync } from "react-dom";
import { createRoot } from "react-dom/client";
import { canvasUi } from "./tools";

const win = new Window();
const G = globalThis as Record<string, unknown>;
const NAMES = ["window", "document", "Node", "HTMLElement", "MutationObserver", "IS_REACT_ACT_ENVIRONMENT"] as const;
const saved = Object.fromEntries(NAMES.map((n) => [n, G[n]]));
let Toolbar: typeof import("./Toolbar").default;

beforeAll(async () => {
  Object.assign(globalThis, { window: win, document: win.document, Node: win.Node, HTMLElement: win.HTMLElement, MutationObserver: win.MutationObserver, IS_REACT_ACT_ENVIRONMENT: false });
  Toolbar = (await import("./Toolbar")).default;
});
afterAll(() => {
  for (const n of NAMES) if (saved[n] === undefined) delete G[n];
  else G[n] = saved[n];
});

const fake = (enabled: boolean, editable: boolean | null, ready: boolean) => {
  const ui = canvasUi(enabled, editable, ready);
  return { ...ui, tool: "select", selected: [], setTool() {}, group() {}, ungroup() {}, remove() {}, undo() {}, redo() {} } as never;
};

describe("canvas ui states", () => {
  test("shown follows canvas mode and editability, active also needs the scene", () => {
    expect(canvasUi(true, true, true)).toEqual({ shown: true, active: true });
    expect(canvasUi(true, true, false)).toEqual({ shown: true, active: false }); // a save re-fetching the scene
    expect(canvasUi(true, null, false)).toEqual({ shown: false, active: false });
    expect(canvasUi(true, false, true)).toEqual({ shown: false, active: false });
    expect(canvasUi(false, true, true)).toEqual({ shown: false, active: false });
  });

  test("the toolbar root is the same element across a save cycle and its tools disable meanwhile", async () => {
    const box = win.document.createElement("div");
    win.document.body.appendChild(box);
    const root = createRoot(box as unknown as Element);
    const render = (ready: boolean) =>
      flushSync(() => root.render(createElement(Toolbar, { canvas: fake(true, true, ready), paletteOpen: false, sheetOpen: false, onPalette() {}, onHelp() {} })));
    render(true);
    const bar = box.querySelector('[role="toolbar"]');
    expect(bar).not.toBeNull();
    const buttons = Array.from(box.querySelectorAll("button"));
    expect(buttons.length).toBeGreaterThan(8);
    const removed: string[] = [];
    const mo = new win.MutationObserver((ms) => {
      for (const m of ms) for (const n of Array.from(m.removedNodes)) removed.push((n as unknown as Element).localName);
    });
    mo.observe(box as never, { childList: true, subtree: true });
    render(false); // the scene is being fetched
    expect(box.querySelector('[role="toolbar"]')).toBe(bar);
    expect(Array.from(box.querySelectorAll("button"))).toEqual(buttons); // the same button objects
    expect((box.querySelector('[aria-label="Box"]') as HTMLButtonElement | null)?.disabled).toBe(true);
    render(true);
    expect(box.querySelector('[role="toolbar"]')).toBe(bar);
    expect((box.querySelector('[aria-label="Box"]') as HTMLButtonElement | null)?.disabled).toBe(false);
    expect(removed).toEqual([]);
    flushSync(() => root.unmount());
    await new Promise((r) => setTimeout(r, 20)); // let React's scheduler finish while `window` still exists
  });
});
