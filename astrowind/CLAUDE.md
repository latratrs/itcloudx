# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

> See also: `~/itcloudx/CLAUDE.md` — project-wide reference (brand colors, Firebase config, PayPal plan IDs, etc.)

---

## Dev Commands

```bash
# Start dev server (runs on port 4321 locally, or $PORT if set)
npm run dev

# Production build (output: dist/)
npm run build

# Type-check + lint + prettier check
npm run check

# Auto-fix lint + formatting
npm run fix
```

---

## Architecture

### Output Mode
The site is **fully static** (`output: 'static'` in `astro.config.ts`). All pages use `export const prerender = true` except API routes which must use `export const prerender = false` (note: currently set to `true` in API routes — this is intentional because Firebase Hosting serves them, not Astro's SSR).

### AstroWind Integration
AstroWind is vendored at `./vendor/integration/` and loaded via a dynamic import in `astro.config.ts` (Windows path-safe workaround). It exposes:
- `astrowind:config` virtual module — typed config from `src/config.yaml`
- Widget components in `src/components/widgets/` (Hero, Features, Pricing, FAQs, Steps, etc.)
- Blog machinery reading from `src/data/post/*.md` / `*.mdx`

### Page Architecture
Custom pages (`index`, `audit`, `pricing`, `about`, `services`, `contact`) are **bespoke Tailwind/HTML** — they do NOT use AstroWind widget components. They import only `~/layouts/PageLayout.astro`.

Blog pages in `src/pages/[...blog]/` use AstroWind's built-in blog infrastructure with Astro content collections.

### API Routes
- `src/pages/api/scan.ts` — POST proxy → Firebase Cloud Function (`FIREBASE_FUNCTION_URL` env var). Falls back to demo mode when env var is missing.
- `src/pages/api/report.ts` — GET fetches Firestore REST API directly (no SDK) using jobId param, parses Firestore typed values.

### Navigation
All nav links and footer links are defined in `src/navigation.ts`. Header/footer components read from this file.

### Config
`src/config.yaml` controls site metadata, blog settings (slug pattern `/blog/%slug%`), Google Analytics ID (`G-BSSE9LSJPM`), and UI theme.

---

## Critical Patterns

### Dark Mode — REQUIRED on every custom light page
AstroWind injects `class="dark"` via JS after paint. Prevent it with this inline script at the top of the page `<Layout>`:

```html
<script is:inline>
  (function(){
    var h = document.documentElement;
    h.classList.remove('dark');
    h.style.colorScheme = 'light';
    new MutationObserver(function(){
      if(h.classList.contains('dark')){
        h.classList.remove('dark');
        h.style.colorScheme = 'light';
      }
    }).observe(h, {attributes:true, attributeFilter:['class']});
  })();
</script>
```

Never use Tailwind color classes (`bg-white`, `bg-gray-*`) on light cards — they get overridden. Use inline CSS or `!important` utility classes (`.pw`, `.pp`, `.pn` defined per-page).

### Astro Template Loops
Data arrays for `.map()` inside the template body **must** be defined in the `---` frontmatter. Inline array literals with JSX in the template body crash esbuild.

```astro
---
// CORRECT
const items = [{ title: 'A' }, { title: 'B' }];
---
{items.map(i => <div>{i.title}</div>)}
```

### Path Alias
`~` resolves to `./src/` (configured in `vite.resolve.alias`).

---

## Blog Posts
Markdown/MDX files live in `src/data/post/`. Front matter fields: `title`, `description`, `publishDate`, `category`, `tags[]`, `image` (optional). Published posts auto-appear in the blog listing at `/blog`.
