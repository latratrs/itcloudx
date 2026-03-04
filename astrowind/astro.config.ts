import path from 'path';
import { fileURLToPath, pathToFileURL } from 'url';
import { defineConfig } from 'astro/config';

import tailwind from '@astrojs/tailwind';
import mdx from '@astrojs/mdx';
import sitemap from '@astrojs/sitemap';
import icon from 'astro-icon';
import compress from 'astro-compress';
import partytown from '@astrojs/partytown';
import node from '@astrojs/node';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

// --- THE WINDOWS SHIELD (v2026.2) ---
// Direct resolution to prevent path-slashing issues on Windows PCs
const vendorPath = pathToFileURL(path.resolve(__dirname, './vendor/integration/index.ts')).href;
const astrowind = (await import(/* @vite-ignore */ vendorPath)).default;

export default defineConfig({
  output: 'server',
  adapter: node({ mode: 'standalone' }),

  server: {
    host: true,
    // Automatic port switching: Firebase uses 8080, local uses 4321
    port: process.env.PORT ? Number(process.env.PORT) : 4321, 
  },

  integrations: [
    tailwind({ applyBaseStyles: false }),
    sitemap(),
    mdx(),
    icon(),
    partytown({ config: { forward: ['dataLayer.push'] } }),
    compress({
      CSS: true,
      HTML: { 'html-minifier-terser': { removeAttributeQuotes: false } },
      JavaScript: true,
    }),
    // The Astrowind integration generates the 'astrowind:config' module automatically
    astrowind({ config: './src/config.yaml' }),
  ],

  vite: {
    resolve: {
      alias: {
        '~': path.resolve(__dirname, './src'),
        // MANUAL 'astrowind:config' ALIAS REMOVED TO PREVENT VIRTUAL MODULE CONFLICT
      },
    },
    server: {
      fs: { strict: false },
    },
  },
});