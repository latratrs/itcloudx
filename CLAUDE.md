# CLAUDE.md — TradeShield AI Project Intelligence
> This file is the authoritative reference for all AI assistants working on this project.
> Keep it updated as the project evolves.

---

## Standing Rules

1. **Lyra (Gemini) is the Central Brain / Strategist** — Gemini 1.5 Pro is the AI engine for all compliance analysis. Treat it as the authoritative reasoning layer.
2. **Read `.idx/last_build.log` before fixing errors** — always check the last build log first when diagnosing build or deploy failures.
3. **Phone numbers use dashes** — format as `555-555-5555` everywhere (UI copy, forms, docs).
4. **OCR data from images takes 3:1 priority over text predictions** — when image OCR and model text predictions conflict, weight OCR output 3× higher.
5. **Primary SEO target: "AI Trade Audit"** — all page titles, meta descriptions, headings, and blog content should optimize for this keyword cluster.

---

## Project Overview

**Product:** TradeShield AI — AI-powered US customs & trade compliance SaaS
**Tagline:** "Stop Fines Before They Start."
**Domain:** itcloudx.com
**Owner:** Yuriy Altshul
**Billing Entity:** Deccod (PayPal business: latraveltours@gmail.com)
**Status:** Public Beta — founding member pricing locked in forever

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | AstroWind v1.0.0-beta.52 (Astro + Tailwind) |
| Backend | Firebase Cloud Functions (Python 3.11) |
| AI Engine | Google Gemini 1.5 Pro (gemini-1.5-pro) |
| Database | Firestore (project: itcloudx-com) |
| CMS | Payload CMS (Next.js, port 3000) |
| Hosting | Firebase Hosting → itcloudx.com |
| Dev Environment | Google Cloud Workstations / Project IDX |

---

## Directory Structure

    ~/itcloudx/
    astrowind/
      src/pages/index.astro         Homepage (COMPLETE)
      src/pages/pricing.astro       Pricing page (COMPLETE)
      src/pages/audit.astro         Audit results page (COMPLETE)
      src/pages/api/scan.ts         Firebase upload proxy (COMPLETE)
      src/pages/api/report.ts       Firestore report fetcher (COMPLETE)
      src/components/Logo.astro     TradeShield AI SVG logo (COMPLETE)
      src/components/widgets/Header.astro  Nav (COMPLETE)
      .env                          FIREBASE_FUNCTION_URL
    functions/
      main.py                       Sherlock Vision engine (COMPLETE)
      requirements.txt              Python dependencies (COMPLETE)
      DEPLOY.md                     Deployment guide
    cms/                            Payload CMS (port 3000)

---

## Dev Commands

    Start dev server:
    cd ~/itcloudx/astrowind && npm run dev

    Dev URL:
    https://4321-firebase-itcloudx-1772666570747.cluster-jw5ir3bv6veogx2wok4xpwqr3k.cloudworkstations.dev/

    Deploy functions only:
    firebase deploy --only functions

    Set Gemini API key:
    firebase functions:secrets:set GEMINI_API_KEY

    View logs:
    firebase functions:log

---

## Environment Variables

File: ~/itcloudx/astrowind/.env

    FIREBASE_FUNCTION_URL=https://us-central1-itcloudx-com.cloudfunctions.net/scan

---

## Firebase / Backend

| Setting | Value |
|---------|-------|
| Project ID | itcloudx-com |
| Function name | scan |
| Function URL | https://us-central1-itcloudx-com.cloudfunctions.net/scan |
| Region | us-central1 |
| Runtime | Python 3.11 |
| Memory | 1GB |
| Timeout | 120s |
| Gemini API Key | AIzaSyAFIqu1RdxQwft4RjS4ZYZLaqKmtfVzn2I |
| Gemini Model | gemini-1.5-pro — NOT gemini-1.5-pro-latest |

Firestore Collections:
- leads/ — every scan attempt (jobId, email, company, status, timestamp)
- compliance_audits/ — full audit results (products[], risk scores, report_data)

CORS allowed origins:
- https://itcloudx.com
- https://www.itcloudx.com
- http://localhost:4321

---

## PayPal Subscription Plans (Deccod account)

| Plan | Plan ID |
|------|---------|
| Professional Monthly $299 | P-1NU513273T353600TNGWN7CQ |
| Professional Annual $249/mo | P-7GJ23119F6048484ANGWOEWY |
| Premium Monthly $799 | P-6B6986702B7923417NGWOKBQ |
| Premium Annual $666/mo | P-4XK302596Y708620JNGWOMYA |

PayPal Client ID:
AQu2DIWmRI5-Lv8n_GnWuY5XjcEpfhTm9Vx8DBGgbh2Rh_nWwyU83OBByfBlr96o4gtotz0pqkjtk6kq

Enterprise: Custom quote → compliance@itcloudx.com

---

## Pricing Tiers

| Tier | Name | Monthly | Annual/mo | Scans/mo |
|------|------|---------|-----------|----------|
| 1 | Free Audit | $0 | $0 | 5 |
| 2 | Professional | $299 | $249 | 500 |
| 3 | Premium | $799 | $666 | 2,500 |
| 4 | Enterprise | Custom | $1,999+ | Unlimited API |

---

## Brand Colors

| Name | Hex | Use |
|------|-----|-----|
| Navy | #0b1e3d | Primary background, headings |
| Teal | #0a7c6e | CTA buttons, success states |
| Teal Lt | #0fb39d | Hover states, accents |
| Gold | #f0a820 | Warnings, highlights |
| Rust | #b8361e | Fine alerts, danger |
| Paper | #f7f5f0 | Light section backgrounds |

Font: Inter Variable via @fontsource-variable/inter

---

## Dark Mode Fix — CRITICAL

AstroWind adds class="dark" to html via JS. CSS-only fixes do NOT work.
Every light page needs this script at the top:

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

Never use Tailwind color classes on light cards. Use CSS with !important:

    .pw  { background-color:#ffffff!important; }
    .pp  { background-color:#f7f5f0!important; }
    .pn  { background-color:#0b1e3d!important; }

---

## Astro Patterns

Data arrays for loops must be defined in frontmatter (---), NOT inline in template.
Inline .map() with JSX in the template body causes esbuild compile errors.

API routes must have: export const prerender = false;

---

## Sherlock Vision File Support

| File Type | Method | Reliability |
|-----------|--------|-------------|
| .csv | Text extraction | 100% |
| .xlsx/.xls | Pandas to text | 100% |
| .pdf | Native Gemini | 98% |
| .jpg/.png | PIL 2x upscale OCR | 95% |
| .tiff | PIL 2x upscale OCR | 95% |

Risk levels: LOW 0-33, MEDIUM 34-66, HIGH 67-100

---

## Pages Status

| Page | Route | Status |
|------|-------|--------|
| Homepage | / | COMPLETE |
| Audit Results | /audit | COMPLETE |
| Pricing | /pricing | COMPLETE |
| About | /about | Step 10 pending |
| HS Lookup | /tools/hs-lookup | Step 11 pending |
| De Minimis Calc | /tools/de-minimis | Step 12 pending |

---

## Known Bugs Fixed

1. Dark mode cards black — AstroWind adds class=dark after paint. Fix: MutationObserver above.
2. Astro compile error "service is no longer running" — inline .map() with JSX crashes esbuild. Fix: move arrays to frontmatter.
3. SERVER_TIMESTAMP wrong import — use: from google.cloud.firestore_v1 import SERVER_TIMESTAMP
4. Gemini model name — use gemini-1.5-pro NOT gemini-1.5-pro-latest
5. CSV/Excel to Gemini — Gemini cant read binary files. Fix: extract to text first with csv.reader or pandas.

---

## Remaining Steps

- Step 10: /about page
- Step 11: /tools/hs-lookup — free HS code search SEO magnet
- Step 12: /tools/de-minimis — calculator
- Step 13: SEO meta via Payload CMS
- Step 14: 2 more blog posts
- Step 15: Submit sitemap.xml to Google Search Console
- Step 16: Firebase Trigger Email on new lead
- Firestore security rules
- Deploy to production itcloudx.com

---

## Production Deploy

    firebase functions:secrets:set GEMINI_API_KEY
    firebase deploy --only functions
    cd astrowind && npm run build
    firebase deploy --only hosting

---

## Contact

Enterprise: compliance@itcloudx.com
Billing: latraveltours@gmail.com (Deccod / PayPal)
