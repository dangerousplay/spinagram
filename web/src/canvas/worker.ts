// Web Worker: loads spinagram-wasm (the Rust core) and answers canvas requests. Build the wasm first:
// `bash rust/spinagram-wasm/build.sh` writes web/src/wasm.
import init, { applyOps, registerFile, renderSvg, reroute, srcmap } from "../wasm/spinagram_wasm.js";
import type { Request, Response } from "./client";

const ready = init();
let scene = "";
let fontBase = "";

function bytes(b64: string): Uint8Array {
  const bin = atob(b64);
  const out = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
  return out;
}

async function handle(req: Request): Promise<string> {
  await ready;
  switch (req.t) {
    case "load":
      for (const [path, b64] of Object.entries(req.files)) registerFile(path, bytes(b64));
      scene = req.scene;
      fontBase = req.fontBase;
      return "";
    case "drag":
      return renderSvg(reroute(scene, JSON.stringify(req.moves)), fontBase);
    case "ops":
      return applyOps(req.yaml, req.ops);
    case "srcmap":
      return srcmap(req.yaml);
  }
}

self.addEventListener("message", (e: MessageEvent<Request & { id: number }>) => {
  const { id, ...req } = e.data;
  handle(req as Request).then(
    (value) => (self as unknown as Worker).postMessage({ id, ok: true, value } satisfies Response),
    (err: unknown) => (self as unknown as Worker).postMessage({ id, ok: false, error: err instanceof Error ? err.message : String(err) } satisfies Response),
  );
});
