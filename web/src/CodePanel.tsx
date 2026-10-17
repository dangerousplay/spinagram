import { useCallback, useEffect, useRef, useState } from "react";
import { api, ApiError } from "./api";
import type { EditorHandle } from "./codemirror";
import { edit, fromSource, merge, saved, type Tab } from "./editor";

type Props = {
  diagramKey: string;
  rev: number; // bumps on every live reload of the diagram: the source is read again
  jump: { line: number; nonce: number } | null; // a request to show a line of the spec tab
  onClose: () => void;
};

const base = (path: string) => path.slice(path.lastIndexOf("/") + 1);

/** The diagram's spec and stylesheet files, editable; Save (or Cmd/Ctrl+S) writes the active tab. */
export default function CodePanel({ diagramKey, rev, jump, onClose }: Props) {
  const [tabs, setTabs] = useState<Tab[] | null>(null);
  const [active, setActive] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const host = useRef<HTMLDivElement>(null);
  const editor = useRef<EditorHandle | null>(null);
  const shown = useRef<{ path: string; text: string } | null>(null); // what the editor currently holds
  const tabsRef = useRef<Tab[] | null>(null);
  const activeRef = useRef(0);
  tabsRef.current = tabs;
  activeRef.current = active;

  const load = useCallback(
    (signal?: AbortSignal) =>
      api
        .source(diagramKey, signal)
        .then((r) => {
          setTabs((prev) => (prev ? merge(prev, r.files) : fromSource(r.files)));
          setError(null);
        })
        .catch((e: unknown) => {
          if (signal?.aborted) return;
          if (e instanceof ApiError && e.status === 404) setTabs((prev) => prev?.map((t) => ({ ...t, removed: true })) ?? null);
          setError(e instanceof Error ? e.message : String(e));
        }),
    [diagramKey],
  );

  useEffect(() => {
    const ctl = new AbortController();
    void load(ctl.signal);
    return () => ctl.abort();
  }, [load, rev]);

  const save = useCallback(async () => {
    const tabsNow = tabsRef.current;
    const i = activeRef.current;
    const t = tabsNow?.[i];
    if (!t || !t.dirty || t.removed) return;
    setSaving(true);
    try {
      const { version } = await api.save(t.path, t.text, t.version);
      setTabs((prev) => prev && prev.map((x, k) => (k === i && x.text === t.text ? saved(x, version) : x)));
      setNotice(null);
    } catch (e) {
      setNotice(e instanceof Error ? e.message : String(e));
    } finally {
      setSaving(false);
    }
  }, []);

  // the editor is created once, in its own chunk
  useEffect(() => {
    let disposed = false;
    void import("./codemirror").then(({ createEditor }) => {
      if (disposed || !host.current) return;
      editor.current = createEditor(host.current, {
        onChange: (text) => {
          const i = activeRef.current;
          if (shown.current) shown.current.text = text;
          setTabs((prev) => prev && prev.map((t, k) => (k === i ? edit(t, text) : t)));
        },
        onSave: () => void save(),
      });
      shown.current = null; // load whatever tab is active now
      setTabs((prev) => (prev ? [...prev] : prev));
    });
    return () => {
      disposed = true;
      editor.current?.destroy();
      editor.current = null;
    };
  }, [save]);

  // keep the editor on the active tab, and in step with the disk for a clean tab
  useEffect(() => {
    const t = tabs?.[active];
    const ed = editor.current;
    if (!t || !ed) return;
    if (shown.current?.path !== t.path) {
      ed.load(t.text, t.language);
      shown.current = { path: t.path, text: t.text };
    } else if (shown.current.text !== t.text) {
      ed.setText(t.text);
      shown.current.text = t.text;
    }
  }, [tabs, active]);

  // a jump request shows the spec tab and its line
  useEffect(() => {
    if (!jump || !editor.current || !tabs?.length) return;
    if (active !== 0) {
      setActive(0);
      return; // the tab switch re-runs this effect with the spec loaded
    }
    editor.current.jumpTo(jump.line);
  }, [jump, active, tabs]);

  const current = tabs?.[active];
  return (
    <aside className="flex w-[44%] min-w-[420px] flex-col border-l border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-950" aria-label="Code">
      <div className="flex h-10 shrink-0 items-center gap-1 overflow-x-auto border-b border-slate-200 px-2 dark:border-slate-800" role="tablist">
        {tabs?.map((t, i) => (
          <button
            key={t.path}
            role="tab"
            aria-selected={i === active}
            title={t.path}
            onClick={() => setActive(i)}
            className={`flex shrink-0 items-center gap-1.5 rounded-md px-2.5 py-1 font-mono text-xs ${
              i === active ? "bg-slate-100 text-slate-900 dark:bg-slate-800 dark:text-slate-100" : "text-slate-500 hover:bg-slate-50 dark:hover:bg-slate-900"
            } ${t.removed ? "line-through opacity-60" : ""}`}
          >
            {base(t.path)}
            {t.dirty && <span className="size-1.5 rounded-full bg-amber-500" aria-label="modified" />}
          </button>
        ))}
        <div className="ml-auto flex shrink-0 items-center gap-2 pl-2">
          <button
            onClick={() => void save()}
            disabled={!current?.dirty || current.removed || saving}
            title="Save (Cmd/Ctrl+S)"
            className="rounded-md bg-blue-600 px-3 py-1 text-xs font-medium text-white enabled:hover:bg-blue-700 disabled:opacity-40"
          >
            {saving ? "Saving…" : "Save"}
          </button>
          <button onClick={onClose} title="Close the code panel (e)" className="rounded-md px-2 py-1 text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-800">
            ×
          </button>
        </div>
      </div>
      {current && (
        <div className="shrink-0 truncate border-b border-slate-100 px-3 py-1 font-mono text-[11px] text-slate-400 dark:border-slate-900">
          {current.removed ? `file removed: ${current.path}` : current.path}
        </div>
      )}
      {(notice || (error && !tabs)) && (
        <p className="shrink-0 border-b border-red-200 bg-red-50 px-3 py-2 text-xs text-red-800 dark:border-red-900 dark:bg-red-950 dark:text-red-200">
          {notice ?? error}
        </p>
      )}
      <div ref={host} className="min-h-0 flex-1 overflow-hidden" />
    </aside>
  );
}
