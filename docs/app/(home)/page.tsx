import { readFileSync } from 'node:fs';
import path from 'node:path';
import Link from 'next/link';
import { DynamicCodeBlock } from 'fumadocs-ui/components/dynamic-codeblock';
import { Example } from '@/components/example';
import { basePath } from '@/lib/shared';
import type { ViewId } from '@/lib/showcase';

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

// what comes after the quickstart: each feature shown in several real scenarios, with its source one tab away
const showcases: { eyebrow: string; title: string; body: string; points: string[]; ids: ViewId[]; href: string; start?: number }[] = [
  {
    eyebrow: 'Five steps',
    title: 'From boxes to a finished slide',
    body: 'Start with boxes and arrows. Add icons, then groups, then numbered steps and a legend. One stylesheet at the end adds your brand. Every step is a few more lines in the same file.',
    points: ['a >> b', 'with d.group(...)', 'step="Order is stored"', 'd.add_legend()', 'd.stylesheet("brand.css")'],
    ids: ['t01', 't02', 't03', 't04', 't05'],
    start: 4, // open on the finished slide; step 1 is mostly white space
    href: '/docs/getting-started',
  },
  {
    eyebrow: 'Real CSS',
    title: 'One diagram, four looks',
    body: 'Classes name a role, never a colour. The stylesheet decides how each role looks, and the legend restyles itself. Swap one file to rebrand a whole deck. The Python stays the same.',
    points: ['box-shadow: 0 0 32px', ':root { --night: #070B16 }', 'stroke-dasharray', 'marker-end: open-arrow'],
    ids: ['l01', 'l02', 'l03', 'l04'],
    href: '/docs/examples/css-looks',
  },
  {
    eyebrow: 'Dark canvases',
    title: 'Architecture slides that look designed',
    body: 'Glass cards, glowing heroes and project colours are all CSS. One shared stylesheet styles the whole Kubernetes platform: Cilium yellow, Gateway API teal, add-ons violet.',
    points: ['group.cluster { fill: var(--night) }', 'group.cluster node::title', 'box-shadow: 0 8px 18px'],
    ids: ['k8s01', 'k8s02', 'eks01', 'eks02'],
    href: '/docs/examples/kubernetes',
  },
  {
    eyebrow: 'Typed regions',
    title: 'Several diagram types on one canvas',
    body: 'Put a flowchart, a state machine or swimlanes next to your architecture. Each region is laid out by its own engine. Ordinary arrows connect them.',
    points: ['d.flowchart()', 'd.state_machine()', 'd.activity()', 'a.to(b, "triggers")'],
    ids: ['m01', 'm02', 'b04'],
    href: '/docs/examples/mixed-diagrams',
  },
  {
    eyebrow: 'Behavior',
    title: 'Flowcharts, state machines and swimlanes',
    body: 'Builders that speak each diagram’s language: decisions with .yes() and .no(), transitions written the UML way, lanes with fork and join bars.',
    points: ['valid.yes(charge)', 'created.on("pay", paid)', 'act.parallel()'],
    ids: ['b01', 'b02', 'b03', 'eks03'],
    href: '/docs/examples/behavior',
  },
  {
    eyebrow: 'Automatic layout',
    title: 'Clouds and networks that nest themselves',
    body: 'Regions, VPCs, zones, VLANs and racks are with-blocks. Plain Python loops build the repeated parts. You never write a coordinate.',
    points: ['for az, tier in tiers.items():', 'direction="down"', 'route: ortho'],
    ids: ['aws01', 'aws02', 'gcp01', 'net02', 'net01', 'home01'],
    href: '/docs/examples/architecture',
  },
  {
    eyebrow: 'Icons',
    title: 'Thousands of icons, one argument',
    body: 'AWS, Google Cloud, Azure, Kubernetes, CNCF, AI, self-hosted, network gear and your own SVG files. Packs download on first use and then work offline.',
    points: ['icon="aws:rds"', 'icon="cncf:cilium"', 'icon="ai:claude"', 'icon="logo.svg"'],
    ids: ['i01', 'ai01', 'note01'],
    href: '/docs/examples/icons',
  },
];

export default function HomePage() {
  return (
    <main className="mx-auto flex w-full max-w-7xl flex-1 flex-col gap-16 px-4 py-16 md:px-8">
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

      <section className="flex flex-col items-center gap-3 pt-8 text-center">
        <p className="text-sm font-semibold uppercase tracking-widest text-fd-primary">After the quickstart</p>
        <h2 className="text-3xl font-bold tracking-tight md:text-4xl">What you can do next</h2>
        <p className="max-w-2xl text-fd-muted-foreground">
          Every picture below is rendered by spinagram from a file in <code>examples/</code>. Switch between
          scenarios, then open the Python and CSS tabs to see the code behind each one.
        </p>
      </section>

      {showcases.map((s) => (
        <section key={s.title} className="flex flex-col gap-5">
          <div className="grid gap-4 lg:grid-cols-[minmax(0,2fr)_minmax(0,3fr)] lg:items-end lg:gap-10">
            <div className="flex flex-col gap-2">
              <p className="text-sm font-semibold uppercase tracking-widest text-fd-primary">{s.eyebrow}</p>
              <h2 className="text-2xl font-bold tracking-tight md:text-3xl">{s.title}</h2>
            </div>
            <div className="flex flex-col gap-3">
              <p className="text-fd-muted-foreground">{s.body}</p>
              <div className="flex flex-wrap items-center gap-1.5">
                {s.points.map((p) => (
                  <code key={p} className="rounded-md border bg-fd-secondary px-2 py-0.5 text-xs">
                    {p}
                  </code>
                ))}
                <Link href={s.href} className="ml-1 text-sm font-medium text-fd-primary hover:underline">
                  See how it works →
                </Link>
              </div>
            </div>
          </div>
          <Example id={s.ids} start={s.start} />
        </section>
      ))}

      <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {features.map(([title, body]) => (
          <div key={title} className="rounded-xl border bg-fd-card p-5">
            <h2 className="mb-1 font-semibold">{title}</h2>
            <p className="text-sm text-fd-muted-foreground">{body}</p>
          </div>
        ))}
      </section>

      <section className="flex flex-col items-center gap-4 rounded-2xl border bg-fd-card p-8 text-center">
        <h2 className="text-2xl font-bold tracking-tight">Find the one closest to yours</h2>
        <p className="max-w-xl text-fd-muted-foreground">
          Copy an example, run <code>spinagram serve</code>, and edit it with a live preview.
        </p>
        <div className="flex flex-wrap justify-center gap-3">
          <Link href="/docs/examples" className="rounded-full bg-fd-primary px-5 py-2.5 font-medium text-fd-primary-foreground">
            Browse the gallery
          </Link>
          <Link href="/docs/getting-started" className="rounded-full border px-5 py-2.5 font-medium">
            Get started
          </Link>
        </div>
      </section>
    </main>
  );
}
