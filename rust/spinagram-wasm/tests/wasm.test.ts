// Integration tests of the wasm build (nodejs target) against golden files made by tests/gen_golden.py:
// drawn bodies from the pure-Python writer, patched YAML and source maps from the PyO3 binding.
// Build first: bash rust/spinagram-wasm/build.sh
import { describe, expect, test } from "bun:test";
import { readFileSync, readdirSync } from "node:fs";
import { join } from "node:path";
// eslint-disable-next-line @typescript-eslint/no-require-imports
const wasm = require("../pkg-node/spinagram_wasm.js");

const G = join(import.meta.dir, "golden");
const read = (name: string) => readFileSync(join(G, name), "utf8");
const readBytes = (path: string) => new Uint8Array(readFileSync(path));
const NAMES = ["decision", "ortho", "software_architecture"];

/** The scene JSON of a golden, with its icons registered under the names the scene uses. */
function scene(name: string): string {
  const json = read(`${name}.scene.json`);
  for (const m of json.matchAll(/@GOLDEN@\/icons\/([^"]+)/g)) {
    wasm.registerFile(m[0], readBytes(join(G, "icons", m[1])));
  }
  return json;
}

describe("renderSvg and renderBody", () => {
  for (const name of NAMES) {
    test(`${name}: the drawn body equals the Python writer's, byte for byte`, () => {
      expect(wasm.renderBody(scene(name))).toBe(read(`${name}.body.svg`));
    });
  }

  test("the software architecture golden embeds its icons (registerFile is used)", () => {
    expect(read("software_architecture.body.svg")).toContain("data:image/svg+xml;base64,");
    expect(wasm.renderBody(scene("software_architecture"))).toContain("data:image/svg+xml;base64,");
  });

  test("renderSvg wraps the same body in a document whose fonts load by URL", () => {
    // the default theme's Arial has no file; give every font one so the faces are listed
    const json = scene("decision").replaceAll('"file": null', '"file": "/fonts/dir/Inter-Bold.ttf"');
    const doc: string = wasm.renderSvg(json, "/api/fonts/");
    const body = read("decision.body.svg");
    expect(doc.startsWith('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1920 1080"')).toBe(true);
    expect(doc.endsWith(`${body}</svg>`)).toBe(true);
    expect(doc).toContain("<style>@font-face{font-family:'Arial';src:url(/api/fonts/Inter-Bold.ttf);font-weight:700;font-style:normal}");
    expect(doc).not.toContain("base64,AAEAAA"); // no embedded font subset
  });

  test("an icon that was not registered is an error naming the path", () => {
    const json = read("software_architecture.scene.json").replace(/@GOLDEN@\/icons\/java\.svg|@GOLDEN@\/icons\/terrastruct__java\.svg/g, "@GOLDEN@/icons/missing.svg");
    expect(() => wasm.renderBody(json)).toThrow(/missing\.svg/);
  });
});

describe("applyOps and srcmap", () => {
  for (const name of ["decision", "ortho", "software_architecture"]) {
    test(`${name}: applyOps equals the golden YAML byte for byte`, () => {
      expect(wasm.applyOps(read(`${name}.yaml`), read(`${name}.ops.json`))).toBe(read(`${name}.patched.yaml`));
    });

    test(`${name}: srcmap equals the golden source map`, () => {
      expect(JSON.parse(wasm.srcmap(read(`${name}.yaml`)))).toEqual(JSON.parse(read(`${name}.srcmap.json`)));
    });
  }

  test("a rejected batch throws the reason", () => {
    const yaml = read("decision.yaml");
    expect(() => wasm.applyOps(yaml, '[{"op":"move","id":"nope","x":1,"y":2}]')).toThrow(/unknown id `nope`/);
    expect(() => wasm.applyOps(yaml, '[{"op":"move","id":"start","x":1,"y":2},{"op":"add_node","id":"start"}]')).toThrow(/operation 1: add_node: duplicate id `start`/);
    expect(() => wasm.applyOps(yaml, "nonsense")).toThrow(/invalid operations/);
    expect(() => wasm.srcmap("a: [1")).toThrow(/invalid YAML/);
  });
});

describe("reroute", () => {
  for (const name of ["decision", "software_architecture"]) {
    test(`${name}: equals the PyO3 binding's scene byte for byte`, () => {
      expect(wasm.reroute(scene(name), read(`${name}.moves.json`)).trim()).toBe(read(`${name}.rerouted.scene.json`).trim());
    });
  }

  test("an empty move map keeps every connector's points", () => {
    const before = JSON.parse(scene("decision"));
    const after = JSON.parse(wasm.reroute(scene("decision"), "{}"));
    expect(after.items.filter((i: any) => i.type === "connector").map((c: any) => c.points)).toEqual(
      before.items.filter((i: any) => i.type === "connector").map((c: any) => c.points));
  });

  test("an unknown shape throws", () => {
    expect(() => wasm.reroute(scene("decision"), '{"nope":[1,1]}')).toThrow(/unknown shape `nope`/);
  });

  test("reroute then renderSvg on the software architecture scene: median ms per call", () => {
    const json = scene("software_architecture");
    const moves = ['{"api":[40,30]}', '{"api":[-40,-30]}'];
    const run = (i: number) => wasm.renderSvg(wasm.reroute(json, moves[i % 2]), "/api/fonts/");
    for (let i = 0; i < 10; i++) run(i); // warm up
    const times: number[] = [];
    for (let i = 0; i < 100; i++) {
      const t = performance.now();
      run(i);
      times.push(performance.now() - t);
    }
    times.sort((a, b) => a - b);
    const median = times[times.length / 2];
    console.log(`reroute + renderSvg, software_architecture (${JSON.parse(json).items.length} items): median ${median.toFixed(2)} ms, p95 ${times[95].toFixed(2)} ms`);
    expect(median).toBeLessThan(20); // 50 fps leaves 20 ms a frame
  });
});

describe("fonts", () => {
  test("a font registered from bytes measures like the PyO3 binding", () => {
    const m = JSON.parse(read("measure.json"));
    const file = join(import.meta.dir, "../../../src/spinagram/fonts/NotoSansMath-Regular.ttf");
    wasm.registerFont("noto-math", readBytes(file));
    expect(wasm.measureText("noto-math", m.text, m.size, m.weight)).toBe(m.width);
  });

  test("bytes that are not a font are rejected, and an unregistered name is an error", () => {
    expect(() => wasm.registerFont("bad", new Uint8Array([1, 2, 3]))).toThrow(/not a font/);
    expect(() => wasm.measureText("never-registered", "x", 12, 400)).toThrow(/not registered/);
  });
});

describe("zone styles (the same bytes as the PyO3 binding and the Rust tests)", () => {
  const flow = "id: Z02\ntitle: Zones flow\nzones: [{id: za, label: A, x: 0, y: 0, w: 500, h: 400}, {id: zb, label: B, x: 50, y: 50, w: 200, h: 200}]\nnodes: [{id: m1, title: M1, x: 300, y: 100}]\n";
  test("add_zone writes the style as the zone's color, and nothing extra without one", () => {
    const styled = wasm.applyOps(flow, JSON.stringify([{ op: "add_zone", id: "zc", style: "azure-resource-group", x: 1, y: 2, w: 3, h: 4 }]));
    expect(styled).toBe(flow.replace("h: 200}]", "h: 200}, {id: zc, color: azure-resource-group, x: 1, y: 2, w: 3, h: 4}]"));
    const plain = wasm.applyOps(flow, JSON.stringify([{ op: "add_zone", id: "zc", x: 1, y: 2, w: 3, h: 4 }]));
    expect(plain).toBe(flow.replace("h: 200}]", "h: 200}, {id: zc, x: 1, y: 2, w: 3, h: 4}]"));
  });
  test("set_zone_style adds the key, then replaces it, and refuses a node", () => {
    const once = wasm.applyOps(flow, JSON.stringify([{ op: "set_zone_style", id: "zb", style: "k8s-namespace" }]));
    expect(once).toBe(flow.replace("h: 200}]", "h: 200, color: k8s-namespace}]"));
    expect(wasm.applyOps(once, JSON.stringify([{ op: "set_zone_style", id: "zb", style: "aws-vpc" }]))).toBe(once.replace("k8s-namespace", "aws-vpc"));
    expect(() => wasm.applyOps(flow, JSON.stringify([{ op: "set_zone_style", id: "m1", style: "aws-vpc" }]))).toThrow(/not a zone/);
  });
});

test("the golden directory has what the tests read", () => {
  expect(readdirSync(join(G, "icons")).length).toBeGreaterThan(0);
});
