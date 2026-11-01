import { readFileSync } from 'node:fs';
import path from 'node:path';
import { ServerCodeBlock } from 'fumadocs-ui/components/codeblock.rsc';
import { ExampleTabs } from '@/components/example-tabs';
import { basePath, gitConfig } from '@/lib/shared';
import { type ViewId, views } from '@/lib/showcase';

const EXAMPLES = path.join(process.cwd(), '..', 'examples');
const sourceUrl = (file: string) =>
  `https://github.com/${gitConfig.user}/${gitConfig.repo}/blob/${gitConfig.branch}/examples/${file}`;

// a rendered diagram with its Python and CSS one tab away; several ids become a switcher above the picture
export async function Example({ id, caption, start = 0 }: { id: ViewId | ViewId[]; caption?: string; start?: number }) {
  const ids = Array.isArray(id) ? id : [id];
  const items = await Promise.all(
    ids.map(async (key) => {
      const view = views[key];
      const files = await Promise.all(
        view.files.map(async (file) => {
          const lang = file.endsWith('.css') ? ('css' as const) : ('python' as const);
          const code = readFileSync(path.join(EXAMPLES, file), 'utf8').trimEnd();
          return {
            name: path.basename(file),
            path: file,
            url: sourceUrl(file),
            lang,
            lines: code.split('\n').length,
            code: (
              <ServerCodeBlock
                lang={lang}
                code={code}
                themes={{ light: 'github-dark-default', dark: 'github-dark-default' }}
                codeblock={{
                  className: 'example-code my-0 h-full rounded-none border-0 bg-transparent shadow-none',
                  'data-line-numbers': true,
                  // the code view scrolls itself, so its scroll bars stay at its edges
                  viewportProps: { className: 'example-scroll max-h-[420px] @5xl:h-full @5xl:max-h-none' },
                }}
              />
            ),
          };
        }),
      );
      return { key, label: view.label, src: `${basePath}${view.src}`, alt: view.alt, files };
    }),
  );
  return <ExampleTabs views={items} caption={caption} start={start} />;
}
