import { useCallback, useEffect, useState } from "react";
import { api, type DirListing, type Workspace } from "./api";
import { confirmLeave, setLeaveGuard } from "./hooks";

type Props = {
  onClose: () => void;
  onOpened: (ws: Workspace) => void;
};

/** Browse folders on this machine and make one the workspace root (its specs are loaded, subfolders included). */
export default function OpenFolder({ onClose, onOpened }: Props) {
  const [listing, setListing] = useState<DirListing | null>(null);
  const [path, setPath] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const browse = useCallback((to?: string) => {
    setError(null);
    api
      .listDir(to)
      .then((l) => {
        setListing(l);
        setPath(l.path);
      })
      .catch((e: Error) => setError(e.message));
  }, []);

  useEffect(() => browse(), [browse]);

  useEffect(() => {
    const esc = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", esc);
    return () => window.removeEventListener("keydown", esc);
  }, [onClose]);

  const open = () => {
    const target = path.trim() || listing?.path;
    if (!target || !confirmLeave()) return; // unsaved code edits: ask before the workspace changes under them
    setBusy(true);
    setError(null);
    api
      .open(target)
      .then((ws) => {
        setLeaveGuard(null); // already confirmed: the page change that follows must not ask again
        onOpened(ws);
      })
      .catch((e: Error) => setError(e.message))
      .finally(() => setBusy(false));
  };

  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-black/30 p-6" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div role="dialog" aria-modal="true" aria-labelledby="open-folder-title" className="flex max-h-[80vh] w-full max-w-xl flex-col rounded-xl bg-white shadow-2xl dark:bg-slate-900">
        <div className="border-b border-slate-200 p-4 dark:border-slate-800">
          <h2 id="open-folder-title" className="font-semibold">
            Open a folder of diagrams
          </h2>
          <form
            className="mt-3 flex gap-2"
            onSubmit={(e) => {
              e.preventDefault();
              browse(path.trim());
            }}
          >
            <input
              value={path}
              onChange={(e) => setPath(e.target.value)}
              spellCheck={false}
              aria-label="Folder path"
              placeholder="/path/to/diagrams"
              className="min-w-0 flex-1 rounded-md border border-slate-300 bg-white px-2 py-1.5 font-mono text-xs dark:border-slate-700 dark:bg-slate-950"
            />
            <button type="submit" className="rounded-md border border-slate-300 px-3 text-xs hover:bg-slate-50 dark:border-slate-700 dark:hover:bg-slate-800">
              Go
            </button>
          </form>
        </div>
        <ul className="min-h-40 flex-1 overflow-auto p-2 text-sm" aria-label="Folders">
          {listing?.parent && (
            <li>
              <button className="w-full rounded-md px-3 py-1.5 text-left text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-800" onClick={() => browse(listing.parent!)}>
                ↑ ..
              </button>
            </li>
          )}
          {listing?.dirs.map((d) => (
            <li key={d.path}>
              <button className="flex w-full items-center gap-2 rounded-md px-3 py-1.5 text-left hover:bg-slate-100 dark:hover:bg-slate-800" onClick={() => browse(d.path)}>
                <span aria-hidden>📁</span>
                <span className="truncate">{d.name}</span>
                {d.specs > 0 && (
                  <span className="ml-auto shrink-0 rounded-full bg-blue-50 px-2 text-xs text-blue-700 dark:bg-blue-950 dark:text-blue-300">
                    {d.specs} spec{d.specs > 1 ? "s" : ""}
                  </span>
                )}
              </button>
            </li>
          ))}
          {listing && listing.dirs.length === 0 && <li className="px-3 py-1.5 text-slate-400">No subfolders</li>}
        </ul>
        {error && (
          <p className="mx-4 rounded-md bg-red-50 px-3 py-2 text-xs text-red-800 dark:bg-red-950 dark:text-red-200" role="alert">
            {error}
          </p>
        )}
        <div className="flex items-center gap-3 border-t border-slate-200 p-4 dark:border-slate-800">
          <p className="text-xs text-slate-500">
            Opening a folder runs its Python specs, like <code className="font-mono">spinagram serve &lt;folder&gt;</code>. Open only
            folders you trust.
            {listing ? ` ${listing.specs} spec${listing.specs === 1 ? "" : "s"} directly in this folder; subfolders are included.` : ""}
          </p>
          <div className="ml-auto flex shrink-0 gap-2">
            <button onClick={onClose} className="rounded-md px-3 py-1.5 text-xs hover:bg-slate-100 dark:hover:bg-slate-800">
              Cancel
            </button>
            <button onClick={open} disabled={busy || !path.trim()} className="rounded-md bg-blue-600 px-3 py-1.5 text-xs font-medium text-white enabled:hover:bg-blue-700 disabled:opacity-40">
              {busy ? "Opening…" : "Open"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
