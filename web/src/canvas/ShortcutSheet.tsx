// The `?` sheet: every canvas shortcut, read from the same keymap table the key handlers use.
import { shortcutRows } from "./interaction";

export default function ShortcutSheet({ onClose }: { onClose: () => void }) {
  return (
    <div
      className="absolute inset-0 z-20 grid place-items-center bg-black/20"
      onPointerDown={(e) => {
        e.stopPropagation();
        onClose();
      }}
    >
      <div
        role="dialog"
        aria-label="Canvas shortcuts"
        className="max-h-[80%] w-[28rem] max-w-[92%] overflow-y-auto rounded-lg bg-white p-4 text-sm text-slate-700 shadow-2xl ring-1 ring-black/10 dark:bg-slate-800 dark:text-slate-200"
        onPointerDown={(e) => e.stopPropagation()}
      >
        <div className="mb-2 flex items-center justify-between">
          <h2 className="font-semibold">Canvas shortcuts</h2>
          <button onClick={onClose} aria-label="Close" className="rounded px-2 text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-700">
            ×
          </button>
        </div>
        <table className="w-full">
          <tbody>
            {shortcutRows().map((r) => (
              <tr key={r.keys} className="border-t border-slate-100 align-top dark:border-slate-700">
                <td className="py-1 pr-3 font-mono text-xs whitespace-nowrap text-slate-900 dark:text-slate-100">{r.keys}</td>
                <td className="py-1">{r.label}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <p className="mt-2 text-xs text-slate-500">Canvas on/off: the Canvas button, or c while it is off. Esc closes this sheet.</p>
      </div>
    </div>
  );
}
