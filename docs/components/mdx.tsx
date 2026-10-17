import defaultMdxComponents from 'fumadocs-ui/mdx';
import { Step, Steps } from 'fumadocs-ui/components/steps';
import { Tab, Tabs } from 'fumadocs-ui/components/tabs';
import Link from 'next/link';
import type { ReactNode } from 'react';
import type { MDXComponents } from 'mdx/types';
import { basePath } from '@/lib/shared';

// a grid of rendered diagrams, each card links to the page that explains it
function Gallery({ children }: { children: ReactNode }) {
  return <div className="not-prose my-6 grid gap-4 sm:grid-cols-2">{children}</div>;
}

function Shot({ src, title, href, children }: { src: string; title: string; href?: string; children?: ReactNode }) {
  const body = (
    <>
      <div className="overflow-hidden border-b bg-white">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src={`${basePath}${src}`} alt={title} loading="lazy" className="w-full" />
      </div>
      <div className="p-3">
        <p className="font-medium">{title}</p>
        {children ? <div className="text-sm text-fd-muted-foreground [&_p]:m-0">{children}</div> : null}
      </div>
    </>
  );
  const cls = 'block overflow-hidden rounded-xl border bg-fd-card transition-colors';
  return href ? (
    <Link href={href} className={`${cls} hover:bg-fd-accent`}>
      {body}
    </Link>
  ) : (
    <div className={cls}>{body}</div>
  );
}

export function getMDXComponents(components?: MDXComponents) {
  return {
    ...defaultMdxComponents,
    Gallery,
    Shot,
    Step,
    Steps,
    Tab,
    Tabs,
    ...components,
  } satisfies MDXComponents;
}

export const useMDXComponents = getMDXComponents;

declare global {
  type MDXProvidedComponents = ReturnType<typeof getMDXComponents>;
}
