// Types and fetchers for the `diagramkit serve` API (src/diagramkit/ui/server.py).

export type Engine = { name: string; hint: string | null };
export type DiagramRef = { key: string; id: string; title: string; auto: boolean };
export type SpecFile = { path: string; error: string | null; diagrams: DiagramRef[] };
export type Workspace = {
  paths: string[];
  theme: string;
  theme_name: string;
  theme_error: string | null;
  layout: string | null;
  engines: Engine[];
  files: SpecFile[];
  offline: boolean;
};

export type DiagramInfo = { overflow: [number, number] | null; warnings: string[]; missing_packs: string[] };

export type ThemeEntry = { ref: string; name: string; builtin: boolean; active: boolean; error: string | null };
export type ColorToken = { token: string; value: string; hex: string | null; via: string | null };
export type FontFile = { key: string; weight: number; italic: boolean; format: string; available: boolean };
export type FontRole = {
  role: string;
  family: string;
  fallback: string | null;
  figma: Record<string, string>;
  files: FontFile[];
};
export type StyleRow = { name: string; value: unknown; swatches: Record<string, string>; preview: boolean };
export type ThemeSheet = {
  ref: string;
  name: string;
  extends: string | null;
  root: string;
  canvas: Record<string, unknown>;
  colors: ColorToken[];
  fonts: FontRole[];
  sample: string;
  styles: Record<string, StyleRow[]>;
  defaults: Record<string, unknown>;
  chrome: Record<string, unknown>;
  icons: Record<string, unknown>;
};

export type Pack = {
  name: string;
  title: string;
  version: string;
  origin: string;
  license: string;
  homepage: string;
  source: string;
  fetched: boolean;
  count: number;
  fetching: boolean;
  error: string | null;
};
export type PackIcon = { name: string; aliases: string[]; tones: string[]; ext: string };

export type UiEvent =
  | { type: "hello" }
  | { type: "workspace" }
  | { type: "diagram"; keys: string[] }
  | { type: "theme"; ref: string }
  | { type: "pack"; name: string; status: "fetching" | "done" | "failed"; error?: string };

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly file?: string,
  ) {
    super(message);
  }
}

async function check(r: Response): Promise<Response> {
  if (r.ok) return r;
  let body: { error?: string; file?: string } = {};
  try {
    body = await r.json();
  } catch {
    /* not JSON */
  }
  throw new ApiError(body.error ?? `${r.status} ${r.statusText}`, r.status, body.file);
}

async function json<T>(url: string, init?: RequestInit): Promise<T> {
  return (await check(await fetch(url, init))).json() as Promise<T>;
}

const enc = encodeURIComponent;

export const api = {
  workspace: () => json<Workspace>("api/workspace"),
  diagram: async (key: string, layout: string | null, signal?: AbortSignal) => {
    const q = layout ? `?layout=${enc(layout)}` : "";
    const r = await check(await fetch(`api/diagrams/${key.split("/").map(enc).join("/")}.svg${q}`, { signal }));
    let info: DiagramInfo = { overflow: null, warnings: [], missing_packs: [] };
    try {
      info = { ...info, ...JSON.parse(decodeURIComponent(r.headers.get("X-Diagram-Info") ?? "{}")) };
    } catch {
      /* older server */
    }
    return { svg: await r.text(), info };
  },
  themes: () => json<ThemeEntry[]>("api/themes"),
  theme: (ref: string) => json<ThemeSheet>(`api/themes/${enc(ref)}`),
  preview: (ref: string, kind: string, style: string, rev: number) =>
    `api/themes/${enc(ref)}/preview/${enc(kind)}/${enc(style)}.svg?rev=${rev}`,
  font: (ref: string, role: string, key: string, rev: number) =>
    `api/themes/${enc(ref)}/font/${enc(role)}/${enc(key)}?rev=${rev}`,
  packs: () => json<{ offline: boolean; packs: Pack[] }>("api/packs"),
  packIcons: (name: string) => json<PackIcon[]>(`api/packs/${enc(name)}/icons`),
  icon: (pack: string, icon: string) => `api/packs/${enc(pack)}/icons/${enc(icon)}`,
  fetchPack: (name: string) => json<{ status: string }>(`api/packs/${enc(name)}/fetch`, { method: "POST" }),
};
