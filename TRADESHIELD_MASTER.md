# 🛡️ TradeShield AI — Master Project Document
**Version**: 3.1 | **Updated**: March 25, 2026 | **Author**: Yuriy Altshul

> Upload this document to Claude at the start of each session for instant project context.

---

## 🏢 Business Overview

| Field | Value |
|-------|-------|
| **Product** | TradeShield AI |
| **Website** | https://itcloudx.com |
| **Revenue Entity** | Deccod LLC (deccod.com) — has bank account + PayPal |
| **Tagline** | Stop Fines Before They Start |
| **Target Customers** | Amazon sellers, freight forwarders, importers, customs brokers |
| **Revenue Model** | Free (5 scans/mo) → Pro $299/mo → Enterprise $999+/mo |
| **Payment** | PayPal via Deccod entity |
| **Contact** | yaltshul@itcloudx.com |

---



---

## 💳 PayPal Subscriptions (MVP wiring)

**Status (2026-03-25)**: Webhook endpoint deployed; backend can upsert Firestore `subscriptions` records by PayPal subscription event.

- **Webhook URL (Firebase Function)**: https://us-central1-itcloudx-com.cloudfunctions.net/paypal_webhook
- **Auth (MVP)**: requires header `X-Webhook-Secret` matching Secret Manager `PAYPAL_WEBHOOK_SECRET`
- **Firestore writes**: `subscriptions/paypal:<paypal_subscription_id>`
- **Plan → Tier mapping (live)**:
  - Pro monthly: `P-1NU513273T353600TNGWN7CQ` → `pro`
  - Pro yearly: `P-7GJ23119F6048484ANGWOEWY` → `pro`
  - Premium monthly: `P-6B6986702B7923417NGWOKBQ` → `premium`
  - Premium yearly: `P-4XK302596Y708620JNGWOMYA` → `premium`

Next: enforce monthly quotas by Firebase Auth UID + show “WOW” scans-remaining meter in UI.


## 🏗️ Tech Stack

### Frontend
| Component | Detail |
|-----------|--------|
| Framework | AstroWind (Astro v4 + Tailwind CSS) |
| Template | @onwidget/astrowind v1.0.0-beta.52 |
| Node Version | v22.22.0 |
| Hosting | Firebase Hosting (project: itcloudx-com) |
| Live URL | https://itcloudx.com / https://itcloudx-com.web.app |

### Backend & AI
| Component | Detail |
|-----------|--------|
| AI Model | Gemini 2.5 Flash (gemini-2.5-flash) |
| AI SDK | google-genai (NOT deprecated google.generativeai) |
| Image Gen | Imagen 4 (imagen-4.0-generate-001) — 70 req/day limit |
| Python | 3.11 |
| Python Venv | ~/tradeshield-env/ |
| Backend | Google Cloud Functions Gen2 (Python 3.11) |

### Infrastructure
| Component | Detail |
|-----------|--------|
| Cloud Project | itcloudx-com |
| Firebase Project | itcloudx-com |
| Dev IDE | Firebase Studio (Google Cloud Workstation) |
| Dev URL | https://4321-firebase-itcloudx-1772666570747.cluster-jw5ir3bv6veogx2wok4xpwqr3k.cloudworkstations.dev/ |
| Git Repo | https://github.com/latratrs/itcloudx (main branch) |
| Secret Manager | GEMINI_API_KEY, GITHUB_TOKEN |

---

## �� Directory Structure
```
~/itcloudx/
├── astrowind/                    # Astro frontend
│   ├── src/
│   │   ├── pages/               # All page routes (.astro files)
│   │   ├── data/post/           # Blog posts (.md files)
│   │   ├── assets/images/       # Cover images (weekly-cover-*.jpg)
│   │   ├── components/
│   │   │   ├── blog/
│   │   │   │   ├── GridItem.astro      # Blog card component (uses findImage)
│   │   │   │   └── Grid.astro          # Blog grid
│   │   │   └── widgets/
│   │   │       └── Announcement.astro  # Dynamic latest post bar
│   │   └── utils/
│   │       └── images.ts        # findImage() - uses /src/assets/images glob
│   └── dist/client/             # Built static files served by Firebase
├── functions/
│   ├── main.py                  # Cloud Functions (scan, refresh_sanctions)
│   ├── weekly_publisher.py      # Weekly blog publisher Cloud Function
│   └── requirements.txt         # Python dependencies
├── news_scraper_v2.py           # Local weekly blog generator (manual use)
├── publish.sh                   # One-command local publish script
├── firebase.json                # Firebase config
└── TRADESHIELD_MASTER.md        # This document
```

---

## ☁️ Cloud Functions

| Function | URL | Purpose |
|----------|-----|---------|
| scan | https://scan-tmv6tfm3wa-uc.a.run.app | Main scanner - HS codes, sanctions, PDF |
| refresh_sanctions | us-central1 | Refreshes OFAC/UN/EU sanctions cache |
| trade-vision-scan | us-central1 | Alternative scanner endpoint |
| weekly_publish | https://us-central1-itcloudx-com.cloudfunctions.net/weekly_publish | Weekly blog publisher |

### Deploy Cloud Function (scan)
```bash
gcloud functions deploy scan --gen2 --runtime python311 --trigger-http \
  --allow-unauthenticated --region us-central1 --source ~/itcloudx/functions \
  --entry-point scan --memory 1GB --cpu 1 --timeout 120s --concurrency 1 \
  --set-secrets GEMINI_API_KEY=GEMINI_API_KEY:latest --project itcloudx-com
```

---

## 📅 Weekly Blog Publishing System

### Architecture (as of March 2026)
```
Cloud Scheduler (every Sunday 8am PT)
    ↓
weekly_publish Cloud Function
    ↓
Gemini 2.5 Flash generates 3 articles (1500-2000 words each)
    ↓
Imagen 4 generates cover images (70/day quota)
    ↓  
GitHub API commits .md + .jpg files directly to repo
    ↓
Firebase auto-deploys (or trigger manually)
```

### Cloud Scheduler Job
- **Name**: weekly-publish-job
- **Schedule**: `0 15 * * 0` (Sunday 8am PT / 3pm UTC)
- **URL**: https://us-central1-itcloudx-com.cloudfunctions.net/weekly_publish
- **Method**: POST

### Manual Trigger
```bash
curl -X POST https://us-central1-itcloudx-com.cloudfunctions.net/weekly_publish
```

### Local Manual Publish (workstation)
```bash
source ~/tradeshield-env/bin/activate && python3 ~/itcloudx/news_scraper_v2.py
# Then build and deploy:
~/itcloudx/publish.sh
```

### Topic Clusters (3 articles per run)
1. **Sanctions & OFAC** — OFAC/EU/UN enforcement, counterparty screening
2. **Tariffs & HS Codes** — Section 301/232, misclassification risks  
3. **Global Trade Enforcement** — CBP, UFLPA, supply chain

### Secrets Required
```bash
# GEMINI_API_KEY - in Google Secret Manager
# GITHUB_TOKEN - GitHub PAT with repo scope (latratrs/itcloudx)
gcloud secrets list --project=itcloudx-com
```

---

## 🔧 Key Commands
```bash
# Activate Python venv
source ~/tradeshield-env/bin/activate

# Build Astro site
cd ~/itcloudx/astrowind && npm run build

# Deploy to Firebase
cd ~/itcloudx && firebase deploy --only hosting

# Full weekly publish (local)
~/itcloudx/publish.sh

# Generate articles only (local)
python3 ~/itcloudx/news_scraper_v2.py

# Trigger weekly publisher manually (Cloud Function)
curl -X POST https://us-central1-itcloudx-com.cloudfunctions.net/weekly_publish

# View scan function logs
cd ~/itcloudx && npx -y firebase-tools@latest functions:log --only scan --lines 100

# Deploy scan function only
cd ~/itcloudx && npx -y firebase-tools@latest deploy --only functions:python-scanner

# Deploy Cloud Function
cd ~/itcloudx/functions && gcloud functions deploy weekly_publish \
  --gen2 --runtime python311 --trigger-http --allow-unauthenticated \
  --region us-central1 --source . --entry-point weekly_publish \
  --memory 1GB --timeout 540s \
  --set-secrets "GEMINI_API_KEY=GEMINI_API_KEY:latest,GITHUB_TOKEN=GITHUB_TOKEN:latest" \
  --project itcloudx-com

# Git commit and push
cd ~/itcloudx && git add -A && git commit -m "message" && git push origin main

# Check available Gemini models
python3 -c "from google import genai; import os; client = genai.Client(api_key=os.environ.get('GEMINI_API_KEY')); [print(m.name) for m in client.models.list()]"
```

---

## 📄 Blog System

### How It Works
- Posts are `.md` files in `astrowind/src/data/post/`
- Images in `astrowind/src/assets/images/weekly-cover-*.jpg`
- `findImage()` in `images.ts` uses `/src/assets/images/**/*` glob (NOT `~/assets/...`)
- `GridItem.astro` extracts `.src` URL from ImageMetadata via `imgUrl`
- Announcement bar is dynamic — auto-shows latest post title

### Required Frontmatter
```yaml
---
title: "SEO Title Here"
excerpt: "155 char description"
publishDate: 2026-03-25T00:00:00Z
image: ~/assets/images/weekly-cover-example.jpg
category: Trade Compliance News
tags: [Sanctions, OFAC, Tariffs, Import Compliance, Trade Compliance]
author: TradeShield AI
draft: false
faq:
  - question: "Question here"
    answer: "Answer here"
---
```

### Known Issues Fixed
| Issue | Fix Applied |
|-------|-------------|
| Related posts grey images | GridItem.astro uses findImage() + extracts imgSrc.src as imgUrl |
| import.meta.glob ~/ alias | Changed to /src/assets/images/**/* in images.ts |
| Blog showing AstroWind demo | Deleted demo .md files from src/data/post/ |
| Announcement bar static | Now uses findLatestPosts() dynamically |

---

## 💰 Pricing

| Feature | Free Scout $0 | Professional $299/mo | Enterprise $999+/mo |
|---------|--------------|---------------------|---------------------|
| Scans/month | 5 | Unlimited | Unlimited |
| HS Classification | ✓ | ✓ | ✓ |
| Sanctions check | Basic | OFAC+UN+EU | OFAC+UN+EU |
| PDF report | Watermarked | Full clean | Full clean |
| Bulk CSV/Excel | ✗ | ✓ | ✓ |
| REST API | ✗ | ✗ | ✓ |
| Billed via | — | Deccod/PayPal | Deccod/Invoice |

### PayPal Plan IDs
- Pro monthly: `P-1NU513273T353600TNGWN7CQ`
- Pro yearly: `P-7GJ23119F6048484ANGWOEWY`

### Test Pro Accounts
- latraveltours@gmail.com
- novinka@gmail.com  
- yaltshul@gmail.com

---

## 🗺️ Product Roadmap

### ✅ Live (March 2026)
- Homepage, audit page, pricing, blog, about, contact
- Core scanner: file upload → Gemini → HS codes + sanctions + PDF
- Free (watermarked) vs Pro (clean) PDF reports
- Section 301/232/122 surcharge calculation
- 30-day Firestore scan history with TTL
- Weekly AI blog with Imagen 4 cover images
- Cloud Scheduler for Sunday auto-publish (weekly_publish function)
- PDF delivered as base64 in response (no Firebase Storage needed)
- Scan counter + tier enforcement in Cloud Function
- leads.set(merge=True) — Firestore upsert on every scan

### 🔧 In Development
- Firebase Auth scan counter enforcement (5 free/month)
- PayPal webhook → auto-activate Pro tier in Firestore
- Email capture → Mailchimp upsell sequence

### 📅 Planned (Month 3+)
- Layer 2: Real-time tariff change monitoring + email alerts
- Layer 3: Carrier & supplier vetting (FMCSA + OFAC)
- Layer 4: ESG/carbon per-shipment reporting (EU CBAM)
- Layer 5: Public API ($0.05-$0.50/call) — acquisition target

---

## 🤖 Multi-AI Workflow

| AI Agent | Role |
|----------|------|
| **Claude** | Backend, Cloud Functions, deployment, complex edits, master document |
| **GitHub Copilot** | Frontend content, SEO fixes, navigation, PR reviews |
| **Gemini** | Article generation, image generation, scan analysis |

### Rules
- Always `git pull` before starting work
- After Copilot PRs: review diff, fix prices/emails/URLs, then merge + deploy
- Never use sudo (NixOS — use venv instead)
- pip installs: always use `~/tradeshield-env/bin/pip`

---

## 🔐 Firebase Configuration

### firebase.json
```json
{
  "hosting": {
    "public": "astrowind/dist/client",
    "cleanUrls": true,
    "trailingSlash": false,
    "redirects": [
      {"source": "/desktop-as-a-service", "destination": "/services", "type": 301},
      {"source": "/cyber-security", "destination": "/services", "type": 301}
    ],
    "rewrites": [{"source": "**", "destination": "/index.html"}]
  }
}
```

### astro.config.ts Key Settings
```typescript
output: 'server'
adapter: node({ mode: 'standalone' })
site: 'https://itcloudx.com'
// Static pages use: export const prerender = true
```

---

## 📊 SEO Strategy

### Target Keywords
- AI HS code classifier
- automated customs compliance 2026
- OFAC screening tool
- customs tariff calculator
- HS code misclassification fine
- free HS code lookup

### Google Verification
```html
<meta content="orcPxI47GSa-cRvY11tUe6iGg2IO_RPvnA1q95iEM3M" name="google-site-verification">
```

### JSON-LD Schema
BaseHead.astro injects: SoftwareApplication, FAQPage, Organization, Article schemas.

---

## ⚠️ Known Gotchas

| Issue | Solution |
|-------|----------|
| pip blocked on NixOS | Always use venv: `source ~/tradeshield-env/bin/activate` |
| Gemini model not found | Use `gemini-2.5-flash` (gemini-1.5-pro-latest deprecated) |
| Imagen daily limit | 70 requests/day — resets daily. Falls back to TradeShield-AI.jpg |
| Firebase 404 on deploy | `firebase.json` must have `hosting.public = 'astrowind/dist/client'` |
| output: hybrid removed | Use `output: 'server'` with `export const prerender = true` |
| Astro build slow | ~90s due to astro-compress image optimization |
| GitHub Actions push conflict | Disabled — use Cloud Scheduler instead |
| Related posts grey images | Fixed: GridItem uses findImage() + imgUrl = imgSrc.src |
| Scan score = 0 | Fixed: pdf_url scope bug crashed response — moved pdf_url/pdf_base64/pdf_error declarations before try block |
| PDF not available error | Fixed: Removed Firebase Storage upload (no bucket provisioned) — PDF now returned as base64 directly |
| Firestore leads 404 | Fixed: Changed leads.update() → leads.set(merge=True) |
| Firebase Storage | Not provisioned — PDFs delivered via base64 in response body instead |
| Weekly publish GitHub Actions | Disabled — replaced with Cloud Scheduler + weekly_publish Cloud Function |
| Git push auth | No stored credentials — use: git push https://latratrs:TOKEN@github.com/latratrs/itcloudx.git main |
| GitHub token scope | Needs repo + workflow scopes for pushing workflow files |

---

*TradeShield AI · itcloudx.com · Deccod LLC · Updated March 25, 2026*
