'use client';

import { useState, type ReactNode } from 'react';
import { ExternalLink, Maximize2 } from 'lucide-react';
import { cn } from '@/lib/cn';

export interface ExampleFile {
  name: string;
  path: string;
  url: string;
  lang: 'python' | 'css';
  lines: number;
  code: ReactNode;
}

export interface ExampleView {
  key: string;
  label: string;
  src: string;
  alt: string;
  files: ExampleFile[];
}

const LANGS = {
  python: { label: 'Python', color: '#FACC15' },
  css: { label: 'CSS', color: '#A78BFA' },
};

const DOTS = {
  backgroundImage: 'radial-gradient(color-mix(in oklab, var(--color-fd-foreground) 14%, transparent) 1px, transparent 1px)',
  backgroundSize: '18px 18px',
};

// the diagram is always on screen; the code sits to its right when the figure is wide, below it otherwise
export function ExampleTabs({ views, caption, start = 0 }: { views: ExampleView[]; caption?: string; start?: number }) {
  const [active, setActive] = useState(start);
  const [tab, setTab] = useState(0);
  const view = views[active];
  const file = view.files[Math.min(tab, view.files.length - 1)];

  return (
    <figure className="@container not-prose my-6 overflow-hidden rounded-2xl border bg-fd-card shadow-sm">
      {views.length > 1 ? (
        <div role="tablist" aria-label="Scenario" className="flex flex-wrap gap-1 border-b bg-fd-secondary/50 p-2">
          {views.map((v, i) => (
            <button
              key={v.key}
              type="button"
              role="tab"
              aria-selected={i === active}
              onClick={() => setActive(i)}
              className={cn(
                'rounded-full px-3 py-1 text-sm font-medium transition-colors',
                i === active
                  ? 'bg-fd-primary text-fd-primary-foreground shadow-sm'
                  : 'text-fd-muted-foreground hover:bg-fd-accent hover:text-fd-accent-foreground',
              )}
            >
              {v.label}
            </button>
          ))}
        </div>
      ) : null}

      <div className="grid @5xl:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
        <div className="group relative flex items-center bg-fd-muted/40 p-3 @md:p-5" style={DOTS}>
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            key={view.src}
            src={view.src}
            alt={view.alt}
            loading="lazy"
            className="mx-auto w-full rounded-lg shadow-[0_8px_30px_rgba(15,23,42,0.12)] ring-1 ring-black/5"
          />
          <a
            href={view.src}
            target="_blank"
            rel="noreferrer"
            aria-label="Open full size"
            className="absolute right-5 top-5 rounded-md border bg-fd-background/90 p-1.5 text-fd-muted-foreground opacity-0 transition-opacity hover:text-fd-foreground focus:opacity-100 group-hover:opacity-100 @md:right-7 @md:top-7"
          >
            <Maximize2 className="size-4" />
          </a>
        </div>

        <div className="flex min-w-0 flex-col border-t border-[#1E293B] bg-[#0B1120] text-slate-300 @5xl:border-l @5xl:border-t-0">
          <div className="flex items-stretch border-b border-white/10 bg-[#070B16]">
            <div className="flex shrink-0 items-center gap-1.5 px-3" aria-hidden>
              <span className="size-2.5 rounded-full bg-[#FF5F57]" />
              <span className="size-2.5 rounded-full bg-[#FEBC2E]" />
              <span className="size-2.5 rounded-full bg-[#28C840]" />
            </div>
            <div role="tablist" aria-label="Source" className="flex min-w-0 flex-1 overflow-x-auto">
              {view.files.map((f, i) => {
                const selected = f === file;
                return (
                  <button
                    key={f.path}
                    type="button"
                    role="tab"
                    aria-selected={selected}
                    onClick={() => setTab(i)}
                    className={cn(
                      'relative inline-flex shrink-0 items-center gap-2 border-r border-white/5 px-3.5 py-2.5 font-mono text-xs transition-colors',
                      selected ? 'bg-[#0B1120] text-slate-50' : 'text-slate-500 hover:bg-white/5 hover:text-slate-200',
                    )}
                  >
                    {selected ? (
                      <span className="absolute inset-x-0 top-0 h-0.5" style={{ background: LANGS[f.lang].color }} />
                    ) : null}
                    <span className="size-2 rounded-full" style={{ background: LANGS[f.lang].color }} />
                    {f.name}
                  </button>
                );
              })}
            </div>
            <a
              href={file.url}
              target="_blank"
              rel="noreferrer"
              aria-label={`Open ${file.name} on GitHub`}
              title="Open on GitHub"
              className="inline-flex shrink-0 items-center px-3 text-slate-500 transition-colors hover:text-slate-100"
            >
              <ExternalLink className="size-3.5" />
            </a>
          </div>
          {/* wide: the code fills the diagram's height; narrow: it flows below with a cap. It scrolls itself. */}
          <div className="relative @5xl:min-h-[320px] @5xl:flex-1">
            <div className="h-full @5xl:absolute @5xl:inset-0">{file.code}</div>
          </div>
          <div className="flex items-center gap-3 border-t border-white/10 bg-[#070B16] px-3 py-1.5 font-mono text-[11px] text-slate-500">
            <span className="inline-flex items-center gap-1.5">
              <span className="size-1.5 rounded-full" style={{ background: LANGS[file.lang].color }} />
              {LANGS[file.lang].label}
            </span>
            <span>{file.lines} lines</span>
            <span className="ml-auto truncate">examples/{file.path}</span>
          </div>
        </div>
      </div>

      {caption ? <figcaption className="border-t px-4 py-2.5 text-sm text-fd-muted-foreground">{caption}</figcaption> : null}
    </figure>
  );
}
