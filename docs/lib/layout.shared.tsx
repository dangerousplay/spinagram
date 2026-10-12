import type { BaseLayoutProps } from 'fumadocs-ui/layouts/shared';
import { appName, basePath, gitConfig } from './shared';

export function baseOptions(): BaseLayoutProps {
  return {
    nav: {
      title: (
        <>
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={`${basePath}/assets/logo.svg`} alt="" width={24} height={24} />
          <span className="font-semibold">{appName}</span>
        </>
      ),
    },
    links: [{ text: 'Docs', url: '/docs', active: 'nested-url' }],
    githubUrl: `https://github.com/${gitConfig.user}/${gitConfig.repo}`,
  };
}
