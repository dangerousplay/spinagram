// Dry-runs a diagramkit Figma script against a minimal mock of the Plugin API.
// Usage: node figma_mock.mjs <script.js> [editorType]
import { readFileSync } from 'node:fs';
let ids = 0;
function node(type) {
  const n = { id: `1:${++ids}`, type, name: '', x: 0, y: 0, width: 100, height: 20, children: [], fills: [], strokes: [],
    resize(w, h) { this.width = w; this.height = h; },
    resizeWithoutConstraints(w, h) { this.width = w; this.height = h; },
    _pd: {}, setPluginData(k, v) { this._pd = { ...this._pd, [k]: v }; }, getPluginData(k) { return (this._pd || {})[k] || ''; },
    appendChild(c) { c.parent = this; this.children.push(c); },
    remove() { if (this.parent) this.parent.children = this.parent.children.filter(x => x !== this); },
    clone() { const c = node(this.type); c.name = this.name; return c; },
    findOne(p) { for (const c of this.children) { if (p(c)) return c; const r = c.findOne?.(p); if (r) return r; } return null; } };
  if (type === 'TEXT') {
    Object.defineProperty(n, 'characters', { set(v) { if (!n.fontName) throw new Error('font not loaded'); n._c = v; n.width = v.length * 8; }, get() { return n._c; } });
  }
  if (type === 'VECTOR') n.setVectorNetworkAsync = async (net) => {
    for (const s of net.segments) if (!net.vertices[s.start] || !net.vertices[s.end]) throw new Error('bad segment');
    n.vectorNetwork = net; };
  return n;
}
const page = node('PAGE');
globalThis.figma = {
  editorType: process.argv[3] || 'figma', currentPage: page,
  createFrame: () => node('FRAME'), createSlide: () => { const s = node('SLIDE'); page.appendChild(s); return s; },
  createSection: () => { const s = node('SECTION'); page.appendChild(s); return s; },
  createConnector: () => { const c = node('CONNECTOR'); c.text = {};
    Object.defineProperty(c.text, 'characters', { set(v) { if (!c.text.fontName) throw new Error('connector font not set'); c.text._c = v; } });
    return c; },
  createNodeFromSvg: (src) => { if (!/^<svg[\s>]/.test(src.trim().replace(/^<\?xml[^>]*>\s*/, ''))) throw new Error('bad svg'); return node('FRAME'); },
  createRectangle: () => node('RECTANGLE'), createVector: () => node('VECTOR'), createText: () => node('TEXT'),
  loadFontAsync: async () => {},
  group(nodes, parent) { const g = node('GROUP'); for (const c of nodes) { c.remove(); g.appendChild(c); } parent.appendChild(g); return g; },
};
const origFrame = figma.createFrame;
figma.createFrame = () => { const f = origFrame(); page.appendChild(f); return f; };
const code = readFileSync(process.argv[2], 'utf8');
const AsyncFunction = (async () => {}).constructor;
const out = await new AsyncFunction(code)();
const all = []; (function walk(n) { for (const c of n.children) { all.push(c); walk(c); } })(page);
const count = (t) => all.filter(n => n.type === t).length;
console.log(JSON.stringify({ created: out.created, images: out.imageTargets.length, container: out.name,
  connectors: count('CONNECTOR'), vectors: count('VECTOR'), svgIcons: all.filter(n => / icon$/.test(n.name) && n.type === 'FRAME').length }));
