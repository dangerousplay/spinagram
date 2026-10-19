import { useCallback, useEffect, useRef, useState } from "react";
import { api, ApiError } from "./api";
import type { EditorHandle } from "./codemirror";
import { anyDirty, edit, fromSource, keepMine, merge, reload, saved, type Tab } from "./editor";
import { setLeaveGuard } from "./hooks";

type Props = {
  diagramKey: string;
  rev: number; // bumps on every live reload of the diagram: the source is read again
  jump: { line: number; nonce: number } | null; // select this line of the spec (an element's declaration)
  onCollapse: () => void;
  onDirty: (dirty: boolean) => void; // the rail shows unsaved edits while the panel is collapsed
};

const base = (path: string) => path.slice(path.lastIndexOf("/") + 1);

/** The diagram's spec and stylesheet files, editable; Save (or Cmd/Ctrl+S) writes the active tab. */
export default function CodePanel({ diagramKey, rev, jump, onCollapse, onDirty }: Props) {
  const [tabs, setTabs] = useState<Tab[] | null>(null);
  const [active, setActive] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const inFlight = useRef(false); // one save at a time: a second one would carry a stale version
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
    if (!t || !t.dirty || t.removed || inFlight.current) return;
    inFlight.current = true;
    setSaving(true);
    try {
      const { version } = await api.save(t.path, t.text, t.version);
      setTabs((prev) => prev && prev.map((x, k) => (k === i ? saved(x, version, t.text) : x)));
      setNotice(null);
    } catch (e) {
      if (e instanceof ApiError && e.status === 409) {
        await load(); // the file changed since it was read: the refetch turns the modified tab into a conflict
        setNotice(null);
      } else setNotice(e instanceof Error ? e.message : String(e));
    } finally {
      inFlight.current = false;
      setSaving(false);
    }
  }, []);

  // unsaved edits: confirm before leaving the diagram or the page
  const dirty = tabs ? anyDirty(tabs) : false;
  useEffect(() => onDirty(dirty), [dirty, onDirty]);
  useEffect(() => {
    if (!dirty) return;
    const unload = (e: BeforeUnloadEvent) => {
      e.preventDefault();
      e.returnValue = "";
    };
    window.addEventListener("beforeunload", unload);
    setLeaveGuard(() => window.confirm("You have unsaved changes in the code panel. Leave and discard them?"));
    return () => {
      window.removeEventListener("beforeunload", unload);
      setLeaveGuard(null);
    };
  }, [dirty]);

  const resolve = (how: (t: Tab) => Tab) => setTabs((prev) => prev && prev.map((t, k) => (k === active ? how(t) : t)));

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

  // a jump request shows the spec tab and selects the line
  const handled = useRef(0);
  useEffect(() => {
    if (!jump || handled.current === jump.nonce || !editor.current || !tabs?.length) return;
    if (active !== 0) {
      setActive(0);
      return; // the tab switch re-runs this effect with the spec loaded
    }
    handled.current = jump.nonce;
    editor.current.jumpTo(jump.line);
  }, [jump, active, tabs]);

  const current = tabs?.[active];
  return (
    <aside className="flex min-w-0 flex-1 flex-col border-l border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-950" aria-label="Code">
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
          <button
            onClick={onCollapse}
            title="Collapse the code panel (e)"
            aria-label="Collapse the code panel"
            className="rounded-md px-2 py-1 text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-800"
          >
            »
          </button>
        </div>
      </div>
      {current && (
        <div className="shrink-0 truncate border-b border-slate-100 px-3 py-1 font-mono text-[11px] text-slate-400 dark:border-slate-900">
          {current.removed ? `file removed: ${current.path}` : current.path}
        </div>
      )}
      {current?.conflict && (
        <div className="flex shrink-0 items-center gap-2 border-b border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-900 dark:border-amber-900 dark:bg-amber-950 dark:text-amber-200" role="alert">
          <span className="mr-auto">This file changed on disk since you started editing.</span>
          <button className="rounded-md border border-amber-300 px-2 py-0.5 hover:bg-amber-100 dark:border-amber-800 dark:hover:bg-amber-900" onClick={() => resolve(reload)}>
            Reload from disk
          </button>
          <button className="rounded-md border border-amber-300 px-2 py-0.5 hover:bg-amber-100 dark:border-amber-800 dark:hover:bg-amber-900" onClick={() => resolve(keepMine)}>
            Keep mine
          </button>
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
