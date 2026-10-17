// Code panel tab model (spec: .specs/features/live-editor/spec.md, EDIT-03/07/08/09, JUMP-01/02). Run: `bun test`.
import { describe, expect, test } from "bun:test";
import { anyDirty, disk, edit, fromSource, jumpLine, keepMine, merge, reload, saved, type SourceFile } from "./editor";

const spec: SourceFile = { path: "a.py", language: "python", text: 'd.box("API")\n', version: "v1" };
const css: SourceFile = { path: "a.css", language: "css", text: "node {}\n", version: "c1" };

describe("EDIT-03 modified mark", () => {
  test("a fresh tab is clean; editing marks it modified; typing back the disk text clears it", () => {
    const [t] = fromSource([spec]);
    expect(t.dirty).toBe(false);
    const e = edit(t, 'd.box("Gateway")\n');
    expect(e.dirty).toBe(true);
    expect(e.text).toBe('d.box("Gateway")\n');
    expect(edit(e, spec.text).dirty).toBe(false);
  });
  test("anyDirty reports a modified tab among clean ones", () => {
    const tabs = fromSource([spec, css]);
    expect(anyDirty(tabs)).toBe(false);
    expect(anyDirty([tabs[0], edit(tabs[1], "x")])).toBe(true);
  });
});

describe("EDIT-04 saving", () => {
  test("a save clears the mark and adopts the new version as the disk state", () => {
    const t = saved(edit(fromSource([spec])[0], "new\n"), "v2");
    expect(t).toMatchObject({ dirty: false, version: "v2", disk: "new\n", text: "new\n", conflict: null });
  });
});

describe("edge case: typing while a save is in flight", () => {
  test("the server's version is kept and the newer typing stays modified against it", () => {
    const sent = edit(fromSource([spec])[0], "first\n");
    const typed = edit(sent, "first and more\n"); // typed after the save request left
    const t = saved(typed, "v2", sent.text);
    expect(t).toMatchObject({ text: "first and more\n", disk: "first\n", version: "v2", dirty: true, conflict: null });
  });
});

describe("EDIT-07 a clean tab follows the disk", () => {
  test("a new version on disk replaces the text", () => {
    const t = disk(fromSource([spec])[0], { ...spec, text: "changed\n", version: "v2" });
    expect(t).toMatchObject({ text: "changed\n", disk: "changed\n", version: "v2", dirty: false, conflict: null });
  });
  test("the same version changes nothing", () => {
    const t0 = edit(fromSource([spec])[0], "mine\n");
    expect(disk(t0, spec)).toEqual(t0);
  });
});

describe("EDIT-08 / EDIT-09 conflicts", () => {
  const dirty = edit(fromSource([spec])[0], "mine\n");
  const theirs = { ...spec, text: "theirs\n", version: "v2" };
  test("a disk change while modified keeps my text and records a conflict", () => {
    const t = disk(dirty, theirs);
    expect(t.text).toBe("mine\n");
    expect(t.dirty).toBe(true);
    expect(t.conflict).toEqual({ text: "theirs\n", version: "v2" });
  });
  test("Reload from disk takes their text and clears the conflict", () => {
    expect(reload(disk(dirty, theirs))).toMatchObject({ text: "theirs\n", disk: "theirs\n", version: "v2", dirty: false, conflict: null });
  });
  test("Keep mine keeps my text against their version so the next save is accepted", () => {
    expect(keepMine(disk(dirty, theirs))).toMatchObject({ text: "mine\n", disk: "theirs\n", version: "v2", dirty: true, conflict: null });
  });
});

describe("refetch merge", () => {
  test("tabs keep their buffers, follow the disk, add new files and mark removed ones", () => {
    const tabs = [edit(fromSource([spec])[0], "mine\n"), fromSource([css])[0]];
    const extra: SourceFile = { path: "b.css", language: "css", text: "edge {}\n", version: "b1" };
    const next = merge(tabs, [spec, { ...css, text: "node { fill: red }\n", version: "c2" }, extra]);
    expect(next.map((t) => t.path)).toEqual(["a.py", "a.css", "b.css"]);
    expect(next[0].text).toBe("mine\n");
    expect(next[1].text).toBe("node { fill: red }\n");
    expect(merge(next, [spec])[1].removed).toBe(true);
  });
});

describe("JUMP-01 / JUMP-02 jump to a node's line", () => {
  const text = 'from spinagram import Diagram\nd = Diagram("K", "K")\nkarp = d.box("Karpenter", text="nodes")\nd.box(\'API\')\n';
  test("the first line holding the title as a string literal (1-based)", () => {
    expect(jumpLine(text, "Karpenter")).toBe(3);
    expect(jumpLine(text, "API")).toBe(4);
  });
  test("a title used twice jumps to its first line", () => {
    expect(jumpLine('a = d.box("Web")\nb = d.box("API")\nc = d.box("Web")\n', "Web")).toBe(1);
  });
  test("no literal match gives null (a bare word or a substring does not count)", () => {
    expect(jumpLine(text, "Diagram")).toBeNull(); // only ever a bare word here
    expect(jumpLine(text, "Karp")).toBeNull();
    expect(jumpLine(text, "nowhere")).toBeNull();
    expect(jumpLine(text, "")).toBeNull();
  });
});
