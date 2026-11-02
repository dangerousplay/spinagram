// The properties of the selection and the quick actions (T41), below the element tree. One form per kind of element
// (`FIELDS`); a field commits on Enter or blur (a select or checkbox on change) through the Rust operations, one save
// and one undo step per commit; several selected elements show the fields they share and commit to all in one batch.
import { useEffect, useMemo, useRef, useState } from "react";
import type { ZoneStyle } from "../api";
import { EditorIcon } from "./icons";
import IconPicker from "./IconPicker";
import { ZONE_PROVIDERS, zoneStyleItems } from "./palette";
import { api } from "../api";
import { QUICK_ACTIONS, currentValue, fieldOps, fieldsFor, quickActions, quickOps, rawValue, type Field, type QuickId } from "./props";
import { optionsOf } from "./tree";
import type { useCanvas } from "./useCanvas";

type Canvas = ReturnType<typeof useCanvas>;

const MIXED = "\u0000mixed";
const input = "min-w-0 flex-1 rounded border border-slate-300 bg-white px-2 py-1 text-slate-900 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100";

export default function Properties({ canvas, zoneStyles }: { canvas: Canvas; zoneStyles: ZoneStyle[] }) {
  const { scene, selected, entries } = canvas;
  const [text, setText] = useState<Record<string, string>>({});
  const [picker, setPicker] = useState(false);
  const [zoneMenu, setZoneMenu] = useState(false);
  const root = useRef<HTMLDivElement>(null);
  const ids = selected.map((s) => s.id).join("\n");

  // the YAML entries of the selection, read again whenever the scene is (after every save)
  useEffect(() => {
    let live = true;
    setPicker(false);
    setZoneMenu(false);
    if (!entries || selected.length === 0) {
      setText({});
      return;
    }
    entries(selected.map((s) => s.id))
      .then((t) => live && setText(t))
      .catch(() => live && setText({}));
    return () => {
      live = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ids, scene, entries === null]);

  const fields = useMemo(() => fieldsFor(selected), [selected]);
  const quick = useMemo(() => quickActions(scene, selected), [scene, selected]);
  const nodes = useMemo(() => (scene ? optionsOf(scene, "node") : []), [scene]);
  const zones = useMemo(() => (scene ? optionsOf(scene, "zone") : []), [scene]);
  const styleItems = useMemo(() => zoneStyleItems(zoneStyles).filter((i) => i.type === "zoneStyle"), [zoneStyles]);

  if (!scene || selected.length === 0) {
    return <p className="px-3 py-3 text-xs text-slate-500">Select an element to edit its properties.</p>;
  }

  /** The value of a field across the selection: the shared one, or MIXED when they differ. */
  const valueOf = (f: Field): string => {
    const vs = selected.map((s) => currentValue(scene, s, f, text[s.id] ?? ""));
    return vs.every((v) => v === vs[0]) ? vs[0] : MIXED;
  };

  const commit = (f: Field, raw: string | boolean) => {
    const results = selected.map((s) => fieldOps(scene, s, f, raw, rawValue(f, currentValue(scene, s, f, text[s.id] ?? ""))));
    const failed = results.find((r) => r && "error" in r);
    if (failed && "error" in failed) {
      canvas.notify(failed.error);
      return;
    }
    canvas.run(results.flatMap((r) => (r && "ops" in r ? r.ops : [])));
  };

  const runQuick = (id: QuickId, zone?: string | null) => {
    if (id === "connect") return canvas.addConnection();
    if (id === "style") return root.current?.querySelector<HTMLElement>('[data-field="color"]')?.focus();
    if (id === "move-to-zone" && zone === undefined) return setZoneMenu((v) => !v);
    const ops = quickOps(scene, id, selected, zone);
    if (!ops) return;
    if (id === "delete" || id === "group-row" || id === "group-column" || id === "ungroup") canvas.select([]);
    setZoneMenu(false);
    canvas.run(ops);
  };

  const field = (f: Field) => {
    const v = valueOf(f);
    const mixed = v === MIXED;
    const shown = mixed ? "" : v;
    const key = `${ids}|${f.key}|${shown}`;
    const common = { "data-field": f.key, "aria-label": f.label } as const;
    const enter = (e: React.KeyboardEvent<HTMLInputElement>) => {
      e.stopPropagation();
      if (e.key === "Enter") e.currentTarget.blur(); // the blur commits, once
      if (e.key === "Escape") {
        e.currentTarget.value = shown;
        e.currentTarget.blur();
      }
    };
    switch (f.kind) {
      case "bool":
        return <input key={key} type="checkbox" defaultChecked={shown === "true"} className="size-4" {...common} onChange={(e) => commit(f, e.currentTarget.checked)} />;
      case "select":
        return (
          <select key={key} defaultValue={shown} className={input} {...common} onChange={(e) => commit(f, e.currentTarget.value)}>
            <option value="">{mixed ? "mixed" : "(default)"}</option>
            {f.options?.map((o) => (
              <option key={o} value={o}>
                {o}
              </option>
            ))}
          </select>
        );
      case "node":
        return (
          <select key={key} defaultValue={shown} className={input} {...common} onChange={(e) => commit(f, e.currentTarget.value)}>
            {!nodes.some((n) => n.id === shown) && <option value={shown}>{shown || "(a zone or a point)"}</option>}
            {nodes.map((n) => (
              <option key={n.id} value={n.id}>
                {n.title}
              </option>
            ))}
          </select>
        );
      case "zoneStyle":
        return (
          <select key={key} defaultValue={shown} className={input} {...common} onChange={(e) => commit(f, e.currentTarget.value)}>
            <option value="soft">Generic zone</option>
            {!styleItems.some((i) => i.type === "zoneStyle" && i.style === shown) && shown !== "soft" && shown !== "" && <option value={shown}>{shown}</option>}
            {ZONE_PROVIDERS.map((p) => (
              <optgroup key={p.prefix} label={p.title}>
                {styleItems.flatMap((i) => (i.type === "zoneStyle" && i.provider === p.title ? [<option key={i.style} value={i.style}>{i.title}</option>] : []))}
              </optgroup>
            ))}
          </select>
        );
      case "icon": {
        const [pack, name] = shown.split(":", 2);
        const src = pack && name ? api.icon(pack, name) : null;
        return (
          <div className="flex min-w-0 flex-1 items-center gap-1">
            {src && <img src={src} alt="" className="size-5" />}
            <span className="min-w-0 flex-1 truncate font-mono text-xs" title={shown}>
              {mixed ? "mixed" : shown || "none"}
            </span>
            <button type="button" className="rounded border border-slate-300 px-2 py-0.5 text-xs hover:bg-slate-100 dark:border-slate-700 dark:hover:bg-slate-800" onClick={() => setPicker(true)}>
              Change…
            </button>
            {shown && (
              <button type="button" aria-label="Remove the icon" className="rounded px-1 text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-800" onClick={() => commit(f, "")}>
                ×
              </button>
            )}
          </div>
        );
      }
      default:
        return (
          <input
            key={key}
            defaultValue={shown}
            placeholder={mixed ? "mixed" : ""}
            readOnly={f.readonly}
            inputMode={f.kind === "number" ? "decimal" : undefined}
            className={`${input} ${f.readonly ? "bg-slate-50 text-slate-500 dark:bg-slate-950" : ""}`}
            {...common}
            onKeyDown={enter}
            onBlur={(e) => !f.readonly && e.currentTarget.value !== shown && commit(f, e.currentTarget.value)}
          />
        );
    }
  };

  return (
    <div ref={root} className="relative text-xs" aria-label="Properties">
      <div className="flex flex-wrap items-center gap-1 border-b border-slate-200 px-2 py-1.5 dark:border-slate-800" role="toolbar" aria-label="Quick actions">
        {quick.map(({ id, enabled }) => (
          <button
            key={id}
            type="button"
            disabled={!enabled}
            title={QUICK_ACTIONS.find((q) => q.id === id)?.label}
            aria-label={QUICK_ACTIONS.find((q) => q.id === id)?.label}
            onClick={() => runQuick(id)}
            className={`grid size-7 place-items-center rounded text-slate-700 dark:text-slate-200 ${enabled ? "hover:bg-slate-100 dark:hover:bg-slate-800" : "cursor-not-allowed opacity-35"}`}
          >
            <EditorIcon name={id} size={16} />
          </button>
        ))}
        {zoneMenu && (
          <div role="menu" aria-label="Move to zone" className="mt-1 w-full rounded border border-slate-200 bg-white py-1 dark:border-slate-700 dark:bg-slate-900">
            <button type="button" role="menuitem" className="block w-full px-2 py-1 text-left hover:bg-slate-100 dark:hover:bg-slate-800" onClick={() => runQuick("move-to-zone", null)}>
              (Top level)
            </button>
            {zones.map((z) => (
              <button key={z.id} type="button" role="menuitem" className="block w-full truncate px-2 py-1 text-left hover:bg-slate-100 dark:hover:bg-slate-800" onClick={() => runQuick("move-to-zone", z.id)}>
                {z.title}
              </button>
            ))}
          </div>
        )}
      </div>
      <div className="space-y-1.5 px-2 py-2">
        {selected.length > 1 && <p className="text-slate-500">{selected.length} elements: the fields they share change on all of them.</p>}
        {fields.length === 0 && <p className="text-slate-500">This selection has no editable fields.</p>}
        {fields.map((f) => (
          <label key={f.key} className="flex items-center gap-2">
            <span className="w-20 shrink-0 text-slate-600 dark:text-slate-400">{f.label}</span>
            {field(f)}
          </label>
        ))}
      </div>
      {picker && (
        <IconPicker
          onClose={() => setPicker(false)}
          onPick={(ref) => {
            setPicker(false);
            const f = fields.find((x) => x.key === "icon");
            if (f) commit(f, ref);
          }}
        />
      )}
    </div>
  );
}
