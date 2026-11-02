// The Elements panel: the diagram as a tree (zones, rows and columns with their members, free nodes, edges), a filter
// box, and a pin. Clicking a row selects the element on the canvas (and, with the code panel open, highlights its
// YAML); selecting on the canvas highlights and reveals the row. See tree.ts for the logic.
import { useEffect, useMemo, useRef, useState } from "react";
import { ChevronDown, ChevronRight, Pin, PinOff, X } from "lucide-react";
import { EditorIcon } from "./icons";
import { buildTree, filterTree, revealSelection, selectFromRow, selectedKeys, visibleRows, type TreeNode } from "./tree";
import type { Sel } from "./scene";

type Props = {
  scene: Parameters<typeof buildTree>[0] | null;
  files: Record<string, string>;
  selected: Sel[];
  pinned: boolean;
  onSelect: (sel: Sel[]) => void;
  onPin: () => void;
  onClose: () => void;
};

const MIME: Record<string, string> = { svg: "image/svg+xml", png: "image/png", jpg: "image/jpeg", jpeg: "image/jpeg" };

/** A data URI for an icon file the scene names, or null when the bytes were not sent. */
export function iconSrc(files: Record<string, string>, path: string | null): string | null {
  const data = path ? files[path] : undefined;
  return path && data ? `data:${MIME[path.split(".").pop()?.toLowerCase() ?? ""] ?? "application/octet-stream"};base64,${data}` : null;
}

function RowIcon({ node, files }: { node: TreeNode; files: Record<string, string> }) {
  const src = iconSrc(files, node.iconPath);
  return (
    <span className="flex size-5 shrink-0 items-center justify-center text-slate-600 dark:text-slate-300">
      {src ? <img src={src} alt="" className="max-h-full max-w-full" /> : <EditorIcon name={node.iconName} size={16} />}
    </span>
  );
}

export default function ElementTree({ scene, files, selected, pinned, onSelect, onPin, onClose }: Props) {
  const [query, setQuery] = useState("");
  const [collapsed, setCollapsed] = useState<ReadonlySet<string>>(new Set());
  const list = useRef<HTMLDivElement>(null);
  const tree = useMemo(() => (scene ? buildTree(scene) : []), [scene]);
  const shown = useMemo(() => filterTree(tree, query), [tree, query]);
  // a filter opens everything it matched; otherwise the user's collapsed rows apply
  const rows = useMemo(() => visibleRows(shown, query.trim() ? new Set() : collapsed), [shown, collapsed, query]);
  const keys = selectedKeys(selected);

  // a selection made on the canvas opens the rows above it and scrolls to it
  useEffect(() => {
    setCollapsed((c) => revealSelection(tree, selected, c));
    const first = selected[0];
    if (first) requestAnimationFrame(() => list.current?.querySelector<HTMLElement>(`[data-key="${CSS.escape(`${first.kind}:${first.id}`)}"]`)?.scrollIntoView({ block: "nearest" }));
  }, [selected, tree]);

  const toggle = (key: string) =>
    setCollapsed((c) => {
      const next = new Set(c);
      if (!next.delete(key)) next.add(key);
      return next;
    });

  return (
    <aside className="flex w-72 shrink-0 flex-col border-l border-slate-200 bg-white text-sm dark:border-slate-800 dark:bg-slate-950" aria-label="Elements">
      <div className="flex items-center gap-1 border-b border-slate-200 px-2 py-1.5 dark:border-slate-800">
        <h2 className="flex-1 px-1 text-xs font-semibold tracking-wide text-slate-600 uppercase dark:text-slate-300">Elements</h2>
        <button
          type="button"
          onClick={onPin}
          aria-pressed={pinned}
          aria-label={pinned ? "Unpin the panel" : "Pin the panel"}
          title={pinned ? "Pinned: it stays open or closed as you left it. Click to open it when an element is selected." : "Unpinned: selecting an element opens the panel. Click to keep it as it is."}
          className={`grid size-7 place-items-center rounded ${pinned ? "bg-blue-600 text-white" : "text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-800"}`}
        >
          {pinned ? <Pin size={14} /> : <PinOff size={14} />}
        </button>
        <button type="button" onClick={onClose} aria-label="Close the elements panel" className="grid size-7 place-items-center rounded text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-800">
          <X size={14} />
        </button>
      </div>
      <div className="border-b border-slate-200 p-2 dark:border-slate-800">
        <input
          type="search"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => e.stopPropagation()}
          placeholder="Filter elements"
          aria-label="Filter elements"
          className="w-full rounded border border-slate-300 bg-white px-2 py-1 text-slate-900 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
        />
      </div>
      <div ref={list} role="tree" className="min-h-0 flex-1 overflow-y-auto py-1">
        {rows.map(({ node, depth }) => {
          const open = !collapsed.has(node.key) || query.trim() !== "";
          const on = keys.has(node.key);
          return (
            <div
              key={node.key}
              role="treeitem"
              aria-selected={on}
              aria-expanded={node.children.length ? open : undefined}
              data-key={node.key}
              className={`flex cursor-default items-center gap-1 pr-2 ${on ? "bg-blue-100 text-blue-950 dark:bg-blue-950 dark:text-blue-100" : "hover:bg-slate-100 dark:hover:bg-slate-900"} ${node.kind === "group" ? "font-semibold text-slate-600 dark:text-slate-300" : ""}`}
              style={{ paddingLeft: 6 + depth * 14 }}
              onClick={(e) => (node.kind === "group" ? toggle(node.key) : onSelect(selectFromRow(node, selected, e.shiftKey || e.ctrlKey || e.metaKey)))}
            >
              <button
                type="button"
                tabIndex={-1}
                aria-label={open ? "Collapse" : "Expand"}
                className={`grid size-5 shrink-0 place-items-center text-slate-400 ${node.children.length ? "" : "invisible"}`}
                onClick={(e) => {
                  e.stopPropagation();
                  toggle(node.key);
                }}
              >
                {open ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
              </button>
              <RowIcon node={node} files={files} />
              <span className="min-w-0 flex-1 truncate py-1" title={node.title}>
                {node.title}
              </span>
              {node.kind === "container" && <span className="shrink-0 font-mono text-[10px] text-slate-500">{node.id}</span>}
            </div>
          );
        })}
        {rows.length === 0 && <p className="px-3 py-3 text-slate-500">{query.trim() ? `No element matches "${query.trim()}"` : "Nothing in this diagram yet"}</p>}
      </div>
    </aside>
  );
}
