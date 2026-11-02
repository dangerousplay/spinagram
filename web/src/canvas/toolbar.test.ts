// The toolbar stays mounted while a save re-fetches the scene (insert-redraw iteration, T35). Run: `bun test`.
import { afterAll, beforeAll, describe, expect, test } from "bun:test";
import { Window } from "happy-dom";
import { createElement } from "react";
import { flushSync } from "react-dom";
import { createRoot } from "react-dom/client";
import { DOCK_KEY, otherDock, readDock, writeDock } from "./paletteState";
import { ACTIONS, canvasUi, dockLayout } from "./tools";
import { hasIcon } from "./icons";
import { shortcutRows } from "./interaction";

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
      flushSync(() => root.render(createElement(Toolbar, { canvas: fake(true, true, ready), dock: "left", onDock() {}, paletteOpen: false, elementsOpen: false, sheetOpen: false, onPalette() {}, onElements() {}, onHelp() {} })));
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

describe("toolbar dock", () => {
  const store = (initial: string | null) => {
    let v = initial;
    return { getItem: () => v, setItem: (_: string, x: string) => void (v = x) };
  };

  test("the dock preference round-trips through storage", () => {
    const st = store(null);
    expect(readDock(st)).toBe("left");
    writeDock("bottom", st);
    expect(st.getItem(DOCK_KEY)).toBe("bottom");
    expect(readDock(st)).toBe("bottom");
    writeDock("left", st);
    expect(readDock(st)).toBe("left");
  });

  test("a storage that throws, or holds anything else, gives the left dock", () => {
    const broken = { getItem: () => { throw new Error("denied"); }, setItem: () => { throw new Error("denied"); } };
    expect(readDock(broken)).toBe("left");
    expect(() => writeDock("bottom", broken)).not.toThrow();
    expect(readDock(null)).toBe("left");
    expect(readDock(store("sideways"))).toBe("left");
  });

  test("the toggle switches the orientation", () => {
    expect(otherDock("left")).toBe("bottom");
    expect(otherDock("bottom")).toBe("left");
    expect(dockLayout("left").orientation).toBe("vertical");
    expect(dockLayout("bottom").orientation).toBe("horizontal");
    expect(dockLayout("left").separator).not.toBe(dockLayout("bottom").separator);
    // the selection bar moves up when the toolbar is at the bottom, so the two never overlap
    expect(dockLayout("bottom").selectionBar).not.toBe(dockLayout("left").selectionBar);
    // tooltips open toward the canvas: to the right of a left bar, above a bottom bar
    expect(dockLayout("left").tip).toContain("left-full");
    expect(dockLayout("bottom").tip).toContain("bottom-full");
  });

  test("the dock action is in the action table, has an icon and a sheet entry", () => {
    expect(ACTIONS.some((a) => a.id === "dock")).toBe(true);
    expect(hasIcon("dock")).toBe(true);
    expect(shortcutRows().some((r) => /toolbar/i.test(r.label) && /left/i.test(r.label) && /bottom/i.test(r.label))).toBe(true);
  });

  test("a toolbar rendered in the bottom dock is horizontal, and the dock button asks for the other edge", async () => {
    const box = win.document.createElement("div");
    win.document.body.appendChild(box);
    const root = createRoot(box as unknown as Element);
    const asked: string[] = [];
    flushSync(() =>
      root.render(createElement(Toolbar, { canvas: fake(true, true, true), dock: "bottom", onDock: (d: string) => void asked.push(d), paletteOpen: false, elementsOpen: false, sheetOpen: false, onPalette() {}, onElements() {}, onHelp() {} })),
    );
    expect(box.querySelector('[role="toolbar"]')?.getAttribute("aria-orientation")).toBe("horizontal");
    (box.querySelector(`[aria-label="${ACTIONS.find((a) => a.id === "dock")!.label}"]`) as HTMLButtonElement).click();
    expect(asked).toEqual(["left"]);
    flushSync(() => root.unmount());
    await new Promise((r) => setTimeout(r, 20));
  });
});
