'use client';

import { useState, type ReactNode } from 'react';
import { Code2, ExternalLink, Maximize2 } from 'lucide-react';
import { cn } from '@/lib/cn';

export interface ExampleFile {
  name: string;
  path: string;
  url: string;
  code: ReactNode;
}

export interface ExampleView {
  key: string;
  label: string;
  src: string;
  alt: string;
  files: ExampleFile[];
}

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

        <div className="flex min-w-0 flex-col border-t @5xl:border-l @5xl:border-t-0">
          <div className="flex items-center gap-2 border-b bg-fd-secondary/50 px-2 py-1.5">
            <div role="tablist" aria-label="Source" className="flex min-w-0 flex-1 flex-wrap gap-1">
              {view.files.map((f, i) => (
                <button
                  key={f.path}
                  type="button"
                  role="tab"
                  aria-selected={f === file}
                  onClick={() => setTab(i)}
                  className={cn(
                    'inline-flex items-center gap-1.5 rounded-md px-2.5 py-1 font-mono text-xs transition-colors',
                    f === file
                      ? 'bg-fd-background text-fd-foreground shadow-sm ring-1 ring-fd-border'
                      : 'text-fd-muted-foreground hover:text-fd-foreground',
                  )}
                >
                  <Code2 className="size-3.5" /> {f.name}
                </button>
              ))}
            </div>
            <a
              href={file.url}
              target="_blank"
              rel="noreferrer"
              className="inline-flex shrink-0 items-center gap-1 rounded-md px-2 py-1 text-xs text-fd-muted-foreground hover:bg-fd-accent hover:text-fd-accent-foreground"
            >
              GitHub <ExternalLink className="size-3" />
            </a>
          </div>
          {/* wide: the code fills the diagram's height and scrolls; narrow: it flows below with a cap */}
          <div className="relative @5xl:min-h-[320px] @5xl:flex-1">
            <div className="max-h-[420px] overflow-auto text-[13px] @5xl:absolute @5xl:inset-0 @5xl:max-h-none">
              {file.code}
            </div>
          </div>
        </div>
      </div>

      {caption ? <figcaption className="border-t px-4 py-2.5 text-sm text-fd-muted-foreground">{caption}</figcaption> : null}
    </figure>
  );
}
