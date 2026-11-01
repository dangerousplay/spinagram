import { readFileSync } from 'node:fs';
import path from 'node:path';
import { type ViewId, views } from './showcase';

const EXAMPLES = path.join(process.cwd(), '..', 'examples');

// <Example id="..." /> as plain markdown for llms.txt: each picture followed by its source files
export function expandExamples(markdown: string): string {
  return markdown.replace(/<Example\s+id=(?:"([^"]+)"|\{\[([^\]]+)\]\})[^>]*\/>/g, (_m, one: string, many: string) => {
    const ids = (one ? [one] : many.split(',').map((s) => s.trim().replace(/^['"]|['"]$/g, ''))) as ViewId[];
    const seen = new Set<string>();
    return ids
      .map((id) => {
        const view = views[id];
        const files = view.files
          .filter((f) => !seen.has(f) && seen.add(f))
          .map((f) => {
            const lang = f.endsWith('.css') ? 'css' : 'python';
            return `\`\`\`${lang} title="examples/${f}"\n${readFileSync(path.join(EXAMPLES, f), 'utf8').trimEnd()}\n\`\`\``;
          });
        return [`![${view.alt}](${view.src})`, ...files].join('\n\n');
      })
      .join('\n\n');
  });
}
