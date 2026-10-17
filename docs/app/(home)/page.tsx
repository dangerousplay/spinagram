import { readFileSync } from 'node:fs';
import path from 'node:path';
import Link from 'next/link';
import { DynamicCodeBlock } from 'fumadocs-ui/components/dynamic-codeblock';
import { basePath } from '@/lib/shared';

// the homepage sample is the real example file, trimmed to the diagram itself
function quickstart(): string {
  const src = readFileSync(path.join(process.cwd(), '..', 'examples', 'quickstart.py'), 'utf8');
  const start = src.indexOf('from spinagram');
  const end = src.indexOf('\nif __name__');
  return src.slice(start, end).trim() + '\n\nd.save("out/", formats=["svg", "png", "pptx"])';
}

const features = [
  ['Editable everywhere', 'PowerPoint slides with native shapes and bound connectors, Figma and FigJam nodes, SVG and PNG.'],
  ['Python first', 'users >> lb >> api. Groups are with-blocks, lists fan out, loops build the rest.'],
  ['Automatic layout', 'No coordinates. Boxes fit their text, groups nest, four engines to choose from.'],
  ['Thousands of icons', 'AWS, GCP, Azure, Kubernetes, CNCF projects, product logos, languages and more: twelve packs, downloaded on first use.'],
  ['Your brand', 'One theme directory sets colours, fonts, styles and chrome for every output.'],
  ['Built for review', 'Overflow checks, a live preview, and numbers that carry their sources.'],
];

export default function HomePage() {
  return (
    <main className="mx-auto flex w-full max-w-6xl flex-1 flex-col gap-16 px-4 py-16 md:px-8">
      <section className="flex flex-col items-center gap-6 text-center">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src={`${basePath}/assets/logo.svg`} alt="spinagram logo" width={88} height={88} />
        <h1 className="text-4xl font-bold tracking-tight md:text-5xl">Diagrams as code, editable everywhere</h1>
        <p className="max-w-2xl text-lg text-fd-muted-foreground">
          Write a few lines of Python. Get SVG, PNG, PowerPoint with native shapes, and Figma nodes you can keep
          editing. spinagram does the layout.
        </p>
        <div className="flex flex-wrap justify-center gap-3">
          <Link
            href="/docs/getting-started"
            className="rounded-full bg-fd-primary px-5 py-2.5 font-medium text-fd-primary-foreground"
          >
            Get started
          </Link>
          <Link href="/docs/write/python" className="rounded-full border px-5 py-2.5 font-medium">
            Python guide
          </Link>
        </div>
        <code className="rounded-lg border bg-fd-secondary px-4 py-2 text-sm">pip install &quot;spinagram[all]&quot;</code>
      </section>

      <section className="grid items-start gap-6 lg:grid-cols-2">
        <DynamicCodeBlock lang="python" code={quickstart()} />
        <figure className="overflow-hidden rounded-xl border bg-white">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={`${basePath}/assets/quickstart.svg`} alt="Web app on AWS, laid out automatically" className="w-full" />
        </figure>
      </section>

      <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {features.map(([title, body]) => (
          <div key={title} className="rounded-xl border bg-fd-card p-5">
            <h2 className="mb-1 font-semibold">{title}</h2>
            <p className="text-sm text-fd-muted-foreground">{body}</p>
          </div>
        ))}
      </section>
    </main>
  );
}
