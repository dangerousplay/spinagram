import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { createMDX } from 'fumadocs-mdx/next';

const withMDX = createMDX();

// GitHub Pages serves the site under /spinagram; CI sets NEXT_PUBLIC_BASE_PATH, local dev leaves it empty.
const basePath = process.env.NEXT_PUBLIC_BASE_PATH ?? '';

/** @type {import('next').NextConfig} */
const config = {
  output: 'export',
  basePath,
  trailingSlash: true,
  images: { unoptimized: true },
  reactStrictMode: true,
  // pages <include> files from ../examples, outside this app
  turbopack: { root: path.join(path.dirname(fileURLToPath(import.meta.url)), '..') },
};

export default withMDX(config);
