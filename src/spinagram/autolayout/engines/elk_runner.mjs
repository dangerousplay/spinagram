// Runs ELK layered on a JSON graph read from stdin and prints the laid-out graph to stdout.
// Usage: <bun|node> elk_runner.mjs <dir containing node_modules/elkjs>
// ESM ignores NODE_PATH, so elkjs is resolved with createRequire anchored at that directory.
import { createRequire } from 'node:module';
import path from 'node:path';

const base = process.argv[2];
if (!base) {
  console.error('usage: elk_runner.mjs <elk module dir>');
  process.exit(2);
}
const require = createRequire(path.join(path.resolve(base), 'package.json'));
// elk-worker.min.js picks "web worker" mode when `self` exists and `document` does not — true under
// bun — and then exports nothing. A stub `document` while the bundle loads and builds its (embedded,
// lazily evaluated) worker makes it export the in-process Worker instead.
const stubDoc = typeof globalThis.document === 'undefined';
if (stubDoc) globalThis.document = {};
let elk;
try {
  const ELK = require('elkjs/lib/elk.bundled.js');
  elk = new ELK();
} finally {
  if (stubDoc) delete globalThis.document;
}

const chunks = [];
for await (const c of process.stdin) chunks.push(c);
const graph = JSON.parse(Buffer.concat(chunks).toString('utf8'));
try {
  const out = await elk.layout(graph);
  process.stdout.write(JSON.stringify(out));
} catch (e) {
  console.error(String(e && e.stack || e));
  process.exit(1);
}
