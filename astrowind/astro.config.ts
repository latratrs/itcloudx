import path from 'path';
import { fileURLToPath, pathToFileURL } from 'url';
import { defineConfig } from 'astro/config';

import tailwind from '@astrojs/tailwind';
import mdx from '@astrojs/mdx';
import sitemap from '@astrojs/sitemap';
import icon from 'astro-icon';
import compress from 'astro-compress';
import partytown from '@astrojs/partytown';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

// --- THE WINDOWS SHIELD (v2026.2) ---
// Direct resolution to prevent path-slashing issues on Windows PCs
const vendorPath = pathToFileURL(path.resolve(__dirname, './vendor/integration/index.ts')).href;
const astrowind = (await import(/* @vite-ignore */ vendorPath)).default;

export default defineConfig({
  output: 'static',
  trailingSlash: 'never',   // matches Firebase hosting trailingSlash: false
  build: { format: 'directory' },  // /blog/slug/index.html → served at /blog/slug by cleanUrls

  site: 'https://itcloudx.com',

  server: {
    host: true,
    // Automatic port switching: Firebase uses 8080, local uses 4321
    port: process.env.PORT ? Number(process.env.PORT) : 4321, 
  },

  integrations: [
    tailwind({ applyBaseStyles: false }),
    sitemap({ customPages: ['https://itcloudx.com/'] }),
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
    server: {
      allowedHosts: true,
      fs: { strict: false },
      cors: true,
    },
    resolve: {
      alias: {
        '~': path.resolve(__dirname, './src'),
        // MANUAL 'astrowind:config' ALIAS REMOVED TO PREVENT VIRTUAL MODULE CONFLICT
      },
    },
  },
  image: { inferSize: true, domains: ["images.unsplash.com", "plus.unsplash.com", "images.pexels.com", "cdn.pixabay.com"] },
});
