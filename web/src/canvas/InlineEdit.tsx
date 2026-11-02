// The inline editor of a node title or zone label. It takes focus (and selects its text) once it is mounted, so
// typing right after a double-click goes into the field and not into the canvas shortcuts.
import { useEffect, useRef } from "react";
import type { Editing } from "./useCanvas";

type Props = { editing: Editing; onCommit: (text: string) => void; onCancel: () => void };

export default function InlineEdit({ editing, onCommit, onCancel }: Props) {
  const input = useRef<HTMLInputElement>(null);
  useEffect(() => {
    const el = input.current;
    if (!el) return;
    el.focus();
    el.select();
    // a press that ended the double-click can still move focus away: take it back once
    const t = setTimeout(() => {
      if (document.activeElement !== el) {
        el.focus();
        el.select();
      }
    }, 50);
    return () => clearTimeout(t);
  }, []);
  return (
    <input
      ref={input}
      aria-label={editing.kind === "zone" ? "Zone label" : editing.kind === "edge" ? "Edge label" : "Node title"}
      defaultValue={editing.text}
      className="absolute z-10 rounded border-2 border-blue-500 bg-white px-2 text-sm text-slate-900 shadow-lg outline-none"
      style={{
        left: editing.box.x,
        top: editing.box.y + (editing.kind === "zone" ? 0 : editing.box.h / 2 - 16),
        width: Math.max(160, Math.min(editing.box.w, 420)),
        height: 32,
      }}
      onPointerDown={(e) => e.stopPropagation()}
      onDoubleClick={(e) => e.stopPropagation()}
      onKeyDown={(e) => {
        e.stopPropagation();
        if (e.key === "Enter") onCommit(e.currentTarget.value);
        else if (e.key === "Escape") onCancel();
      }}
      onBlur={onCancel}
    />
  );
}
