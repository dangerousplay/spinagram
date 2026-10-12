// Layout shared by the Diagrams, Themes and Icon packs pages: a search box, titled sections of cards and
// the "nothing matches" state.
import type { ReactNode } from "react";

export const cardClass =
  "group overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm transition hover:-translate-y-0.5 hover:border-slate-300 hover:shadow-md dark:border-slate-800 dark:bg-slate-900 dark:hover:border-slate-700";

type ShellProps = {
  query: string;
  onQuery: (q: string) => void;
  placeholder: string;
  label: string;
  shown: number;
  total: number;
  noun: string;
  filtering: boolean;
  children: ReactNode;
};

export function CatalogShell({ query, onQuery, placeholder, label, shown, total, noun, filtering, children }: ShellProps) {
  return (
    <div className="h-full overflow-y-auto">
      <div className="mx-auto max-w-6xl px-6 py-6">
        <div className="flex flex-wrap items-center gap-3">
          <input
            type="search"
            autoFocus
            value={query}
            onChange={(e) => onQuery(e.target.value)}
            placeholder={placeholder}
            aria-label={label}
            className="min-w-0 flex-1 rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm shadow-sm outline-none focus:border-accent focus:ring-2 focus:ring-accent-soft dark:border-slate-700 dark:bg-slate-900 dark:focus:ring-blue-950"
          />
          <span className="text-xs text-slate-500">
            {filtering ? `${shown} of ${total}` : total} {noun}
            {total === 1 ? "" : "s"}
          </span>
        </div>
        {children}
      </div>
    </div>
  );
}

export function CardSection({ label, count, children }: { label: string; count: number; children: ReactNode }) {
  return (
    <section className="mt-8" aria-label={label}>
      <h2 className="mb-3 flex items-baseline gap-2 text-sm font-semibold">
        {label}
        <span className="text-xs font-normal text-slate-400">{count}</span>
      </h2>
      <div className="grid grid-cols-[repeat(auto-fill,minmax(15rem,1fr))] gap-4">{children}</div>
    </section>
  );
}

export function NoMatch({ what, onClear }: { what: string; onClear: () => void }) {
  return (
    <div className="mt-16 text-center">
      <p className="font-medium">No {what} match</p>
      <button type="button" onClick={onClear} className="mt-2 text-sm text-accent hover:underline">
        Clear search
      </button>
    </div>
  );
}
