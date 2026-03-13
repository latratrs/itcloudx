#!/usr/bin/env node
/**
 * weeklyBuilder.js — TradeShield AI Weekly Intelligence Builder
 *
 * Fetches live trade-compliance news across 9 distinct topic feeds,
 * generates a unique article + cover image per topic with Gemini,
 * and writes 9 ready-to-publish Astro 5 markdown posts into src/data/post/.
 *
 * Usage:
 *   node scripts/weeklyBuilder.js          # generate all 9
 *   node scripts/weeklyBuilder.js --count=3  # generate first N only
 *
 * Requires:  GEMINI_API_KEY stored in GCP Secret Manager
 */

import 'dotenv/config';
import fs     from 'fs';
import path   from 'path';
import { fileURLToPath } from 'url';
import Parser from 'rss-parser';
import { SecretManagerServiceClient } from '@google-cloud/secret-manager';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT      = path.resolve(__dirname, '..');

// ── Config ────────────────────────────────────────────────────────────────────
const SECRET_NAME         = 'projects/836345929499/secrets/GEMINI_API_KEY/versions/latest';
const GEMINI_TEXT_PRIMARY = 'https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-pro:generateContent';
const GEMINI_TEXT_FALLBACK= 'https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-pro:generateContent';
const IMAGEN_URL          = 'https://generativelanguage.googleapis.com/v1beta/models/gemini-3.1-flash-image-preview:generateContent';
const POST_DIR            = path.join(ROOT, 'src/data/post');
const IMG_DIR             = path.join(ROOT, 'src/assets/images');

// Parse --count=N flag
const countArg = process.argv.find(a => a.startsWith('--count='));
const RUN_COUNT = countArg ? Math.max(1, parseInt(countArg.split('=')[1], 10)) : 9;

async function getGeminiKey() {
  const client = new SecretManagerServiceClient();
  try {
    const [version] = await client.accessSecretVersion({ name: SECRET_NAME });
    const key = version.payload?.data?.toString('utf8')?.trim();
    if (!key) throw new Error('Secret payload was empty');
    return key;
  } catch (e) {
    console.error(`SEC_MGR_ERROR: Failed to fetch GEMINI_API_KEY from Secret Manager — ${e.message}`);
    process.exit(1);
  }
}

// ── 9 distinct topic sets ─────────────────────────────────────────────────────
// Each entry: { label, category, rssUrls[], staticFallback[] }
const TOPIC_SETS = [
  {
    label:    'OFAC Sanctions',
    category: 'SANCTIONS',
    rssUrls: [
      'https://news.google.com/rss/search?q=OFAC+sanctions+SDN+list+2026&hl=en-US&gl=US&ceid=US:en',
    ],
    staticFallback: [
      'OFAC Adds 18 Entities to SDN List for Russia Sanctions Evasion Network',
      'Treasury Blocks $2.3B in Iranian Assets via New OFAC Designations',
      'OFAC Issues General License for Humanitarian Trade with Syria',
      'US Sanctions 7 Chinese Firms for Supporting North Korea Weapons Program',
      'OFAC Civil Penalty: Bank Fined $185M for Processing Sanctioned Transactions',
    ],
  },
  {
    label:    'CBP Customs & Tariffs',
    category: 'TARIFFS',
    rssUrls: [
      'https://news.google.com/rss/search?q=CBP+customs+tariff+import+enforcement+2026&hl=en-US&gl=US&ceid=US:en',
    ],
    staticFallback: [
      'CBP Seizes $420M in Counterfeit Goods at Los Angeles Port in Q1 2026',
      'Section 301 Tariffs Extended on 382 Chinese Product Categories Through 2027',
      'CBP Issues Binding Ruling on HTS Classification for EV Battery Components',
      'US Tariff Rate on Chinese Steel Products Raised to 35% Under New Order',
      'CBP Announces ACE Portal Upgrade for Real-Time Duty Calculation',
    ],
  },
  {
    label:    'BIS Export Controls',
    category: 'EXPORT CONTROLS',
    rssUrls: [
      'https://news.google.com/rss/search?q=BIS+export+controls+entity+list+semiconductor+2026&hl=en-US&gl=US&ceid=US:en',
    ],
    staticFallback: [
      'BIS Expands Entity List with 34 Chinese AI and Advanced Chip Firms',
      'Commerce Tightens EAR Controls on 3nm Chip Exports to Restricted Countries',
      'BIS Enforcement Action: $95M Penalty for Unlicensed Export of Dual-Use Tech',
      'New EAR Rule Targets Quantum Computing Components to China and Russia',
      'BIS Adds 12 Russian Defense Entities to Entity List Amid Ongoing Conflict',
    ],
  },
  {
    label:    'UFLPA Forced Labor',
    category: 'UFLPA',
    rssUrls: [
      'https://news.google.com/rss/search?q=UFLPA+forced+labor+Xinjiang+detention+2026&hl=en-US&gl=US&ceid=US:en',
    ],
    staticFallback: [
      'CBP Issues New UFLPA Detention Orders on Textile Shipments from Xinjiang',
      'UFLPA Entity List Grows by 22 Solar Panel Manufacturers in Q1 2026',
      'Importers Face 60-Day Rebuttable Presumption Clock Under Updated UFLPA Guidance',
      'CBP Detains $340M in Goods Under UFLPA at Ports of Entry YTD 2026',
      'DHS Publishes New UFLPA Enforcement Strategy for Apparel Sector',
    ],
  },
  {
    label:    'HTS Classification & Penalties',
    category: 'CUSTOMS FILING',
    rssUrls: [
      'https://news.google.com/rss/search?q=HTS+code+misclassification+customs+penalty+DOJ+2026&hl=en-US&gl=US&ceid=US:en',
    ],
    staticFallback: [
      'DOJ Trade Fraud Task Force Secures $55M in Penalties for HTS Misclassification',
      'CBP Issues 127 Prior Disclosure Waivers for Tariff Underreporting in 2025',
      'Importer Hit with $12M False Claims Act Judgment for Steel HTS Fraud',
      'CBP Publishes Updated Informed Compliance Publication on Textile Classification',
      'DOJ Files Charges Against Broker Network for Systematic HTS Fraud Scheme',
    ],
  },
  {
    label:    'Anti-Dumping & CVD',
    category: 'TARIFFS',
    rssUrls: [
      'https://news.google.com/rss/search?q=anti-dumping+countervailing+duty+ITC+Commerce+2026&hl=en-US&gl=US&ceid=US:en',
    ],
    staticFallback: [
      'ITC Initiates Anti-Dumping Investigation on Chinese Aluminum Extrusions',
      'Commerce Sets 218% AD Rate on Vietnamese Solar Panels in Final Ruling',
      'US Steel Industry Files New CVD Petition Against South Korean Imports',
      'ITC Upholds $1.2B Anti-Dumping Order on Chinese Ceramic Tiles',
      'Commerce Launches Scope Ruling on Wooden Cabinets from Malaysia',
    ],
  },
  {
    label:    'Supply Chain & De Minimis',
    category: 'TRADE POLICY',
    rssUrls: [
      'https://news.google.com/rss/search?q=de+minimis+supply+chain+compliance+import+2026&hl=en-US&gl=US&ceid=US:en',
    ],
    staticFallback: [
      'Congress Moves to End $800 De Minimis Exemption for Chinese E-Commerce',
      'CBP Proposes Rule Requiring Formal Entry for All Packages Over $200',
      'Temu and Shein Face New Customs Scrutiny Under De Minimis Reform Bill',
      'Supply Chain Mapping Now Required for High-Risk Goods Under Proposed CBP Rule',
      'DHS Issues Advisory on Supply Chain Risks from Sanctioned Freight Forwarders',
    ],
  },
  {
    label:    'Trade Policy & Section 232',
    category: 'TRADE POLICY',
    rssUrls: [
      'https://news.google.com/rss/search?q=Section+232+trade+policy+USTR+WTO+2026&hl=en-US&gl=US&ceid=US:en',
    ],
    staticFallback: [
      'USTR Launches New Section 301 Investigation into Chinese Maritime Sector',
      'Section 232 Steel Tariffs Extended for EU, Japan with New Quota System',
      'WTO Appellate Body Reinstated — US Faces Rulings on Steel and Aluminum Tariffs',
      'Biden-Era Trade Deal with Indo-Pacific Partners Faces Congressional Review',
      'Commerce Initiates National Security Review of Imported Drone Components',
    ],
  },
  {
    label:    'Sanctions Evasion & Compliance Tech',
    category: 'SANCTIONS',
    rssUrls: [
      'https://news.google.com/rss/search?q=sanctions+evasion+compliance+technology+screening+2026&hl=en-US&gl=US&ceid=US:en',
    ],
    staticFallback: [
      'FinCEN Issues Alert on Cryptocurrency Used to Evade Russia Sanctions',
      'OFAC Updates Compliance Framework to Include AI-Powered Screening Requirements',
      'DOJ Charges 9 in International Sanctions Evasion Ring Involving Shell Companies',
      'SWIFT Announces Enhanced Sanctions Screening API for Correspondent Banks',
      'Treasury Publishes New Guidance on Virtual Asset Service Provider Sanctions Compliance',
    ],
  },
];

// ── Helpers ───────────────────────────────────────────────────────────────────

function slugify(text) {
  return text
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 80);
}

function isoDate(d = new Date()) {
  return d.toISOString().replace(/\.\d{3}Z$/, 'Z');
}

function normalisePhones(text) {
  return text
    .replace(/\((\d{3})\)\s?(\d{3})[.\-](\d{4})/g, '$1-$2-$3')
    .replace(/\b(\d{3})[\s.](\d{3})[\s.](\d{4})\b/g, '$1-$2-$3');
}

function sleep(ms) {
  return new Promise(r => setTimeout(r, ms));
}

/** Build the structured JSON prompt */
function buildPrompt(headlineBlock, topicLabel, strict = false) {
  const strictNote = strict
    ? '\nStrict JSON only. No other text. Must be valid JSON object.'
    : '';
  return `You are TradeShield AI, an expert US customs and trade compliance analyst specialising in ${topicLabel}.

Output **only** valid JSON — no markdown, no explanation, no fences. The JSON must have exactly these keys:
{
  "title": "string — catchy, SEO-friendly title optimised for 'AI Trade Audit'",
  "category": "string — one of: SANCTIONS | TARIFFS | EXPORT CONTROLS | UFLPA | CUSTOMS FILING | TRADE POLICY",
  "tags": ["array of 3-6 relevant compliance tags"],
  "excerpt": "string — 1-2 sentence Key Takeaways summary for the blog card",
  "body": "string — full Markdown article, 500-800 words. Use ## H2 headings for each section. Use **bold** for key terms, agency names, and dollar amounts. Use - bullet lists for enforcement actions or risk items. Required sections: ## Overview, ## Key Developments, ## Enforcement Actions, ## What Importers Must Do Now"
}

Base the content on these recent news headlines:\n${headlineBlock}\n\nMake it professional, neutral, and focused on trade compliance implications for US importers in 2026.${strictNote}`;
}

// ── RSS fetch for one topic set ───────────────────────────────────────────────
async function fetchTopicItems(topic) {
  const parser = new Parser({ timeout: 10_000 });
  for (const url of topic.rssUrls) {
    try {
      const feed  = await parser.parseURL(url);
      const items = (feed.items ?? []).filter(i => i.title);
      if (items.length > 0) {
        console.log(`  📡  Fetched ${items.length} items for [${topic.label}]`);
        return items.slice(0, 5).map(i => ({
          title:   i.title,
          link:    i.link ?? i.guid ?? '',
          pubDate: i.pubDate ?? i.isoDate ?? new Date().toISOString(),
        }));
      }
    } catch (e) {
      console.warn(`  ⚠️  RSS failed for [${topic.label}]: ${e.message}`);
    }
  }
  // Use topic-specific static fallback
  console.warn(`  ⚠️  Using static fallback for [${topic.label}]`);
  return topic.staticFallback.map(title => ({
    title, link: '', pubDate: new Date().toISOString(),
  }));
}

// ── Gemini text call ──────────────────────────────────────────────────────────
async function callGemini(modelUrl, prompt, geminiKey) {
  const label = modelUrl.match(/models\/([^:]+)/)?.[1] ?? modelUrl;

  const res = await fetch(`${modelUrl}?key=${geminiKey}`, {
    method:  'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      contents: [{ parts: [{ text: prompt }] }],
      generationConfig: {
        temperature: 0.55,
        maxOutputTokens: 65536,
        response_mime_type: 'application/json',
      },
    }),
    signal: AbortSignal.timeout(45_000),
  });

  if (!res.ok) {
    const err = await res.text();
    const isQuota = res.status === 429 || res.status === 503;
    throw Object.assign(
      new Error(`${label} ${res.status}: ${err.slice(0, 200)}`),
      { quota: isQuota }
    );
  }

  const data    = await res.json();
  const rawText = data.candidates?.[0]?.content?.parts?.[0]?.text ?? '';
  const cleaned = rawText.replace(/^```(?:json)?\s*/i, '').replace(/\s*```\s*$/, '').trim();
  return { label, cleaned };
}

async function generateArticle(items, topic, geminiKey) {
  const headlineBlock = items.map((it, i) => `${i + 1}. ${it.title}`).join('\n');
  const modelUrls = [GEMINI_TEXT_PRIMARY, GEMINI_TEXT_FALLBACK];
  let lastError;

  for (const modelUrl of modelUrls) {
    const label = modelUrl.match(/models\/([^:]+)/)?.[1] ?? modelUrl;
    console.log(`  🔮  Text model: ${label}`);

    // Attempt 1
    let cleaned;
    try {
      ({ cleaned } = await callGemini(modelUrl, buildPrompt(headlineBlock, topic.label, false), geminiKey));
    } catch (e) {
      if (e.quota) {
        console.warn(`  ⚠️  ${label} quota — trying fallback model…`);
        lastError = e;
        await sleep(3000);
        continue;
      }
      throw e;
    }

    try { return JSON.parse(cleaned); } catch { /* fall through to retry */ }
    console.warn(`  ⚠️  ${label} non-JSON — retrying strict…`);

    // Attempt 2 — strict
    try {
      const { cleaned: c2 } = await callGemini(modelUrl, buildPrompt(headlineBlock, topic.label, true), geminiKey);
      return JSON.parse(c2);
    } catch (e2) {
      if (e2.quota) {
        console.warn(`  ⚠️  ${label} quota on retry — next model…`);
        lastError = e2;
        await sleep(3000);
        continue;
      }
      throw new Error(`${label} non-JSON after strict retry: ${String(e2).slice(0, 200)}`);
    }
  }

  throw lastError ?? new Error('All Gemini text models failed');
}

// ── Image generation ──────────────────────────────────────────────────────────
async function generateCoverImage(topic, index, geminiKey) {
  const imagePrompt =
    `High-end editorial photography for an intelligence briefing on ${topic.label}, ` +
    'deep navy and teal color palette, ultra-sharp professional lighting, NO text, NO letters, NO watermarks';

  const res = await fetch(`${IMAGEN_URL}?key=${geminiKey}`, {
    method:  'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      contents: [{ parts: [{ text: imagePrompt }] }],
      generationConfig: { responseModalities: ['IMAGE', 'TEXT'] },
    }),
    signal: AbortSignal.timeout(60_000),
  });

  if (!res.ok) {
    const err = await res.text();
    console.warn(`  ⚠️  Image failed (${res.status}): ${err.slice(0, 120)} — using fallback`);
    return null;
  }

  const data   = await res.json();
  const parts  = data.candidates?.[0]?.content?.parts ?? [];
  const imgPart = parts.find(p => p.inlineData?.mimeType?.startsWith('image/'));
  const b64    = imgPart?.inlineData?.data;

  if (!b64) {
    console.warn('  ⚠️  Image response had no bytes — using fallback');
    return null;
  }

  const imgFilename = `weekly-cover-${String(index + 1).padStart(2, '0')}.jpg`;
  const imgPath     = path.join(IMG_DIR, imgFilename);
  fs.writeFileSync(imgPath, Buffer.from(b64, 'base64'));
  console.log(`  🖼️   Cover saved → src/assets/images/${imgFilename}`);
  return `~/assets/images/${imgFilename}`;
}

// ── Write markdown post ───────────────────────────────────────────────────────
function writePost(article, imageSrc, index) {
  const now      = new Date();
  // Stagger publish timestamps by 1 hour each so posts sort distinctly
  now.setHours(now.getHours() - (8 - index));
  const slug     = slugify(article.title) + '-' + new Date().toISOString().slice(0, 10);
  // Avoid collisions: append index if file already exists
  let filename   = `${slug}.md`;
  let filepath   = path.join(POST_DIR, filename);
  if (fs.existsSync(filepath)) {
    filename = `${slug}-${index + 1}.md`;
    filepath = path.join(POST_DIR, filename);
  }

  const finalImage = imageSrc ?? '~/assets/images/TradeShield-AI.jpg';
  const tagsYaml   = (article.tags ?? []).map(t => `"${t}"`).join(', ');
  const bodyClean  = normalisePhones(article.body ?? '');

  const frontmatter = `---
title: "${article.title.replace(/"/g, '\\"')}"
excerpt: "${(article.excerpt ?? '').replace(/"/g, '\\"')}"
publishDate: ${isoDate(now)}
image: ${finalImage}
category: ${article.category ?? 'Trade Compliance News'}
tags: [${tagsYaml}]
author: TradeShield AI
draft: false
---`;

  const body = `${bodyClean}

---
*Powered by TradeShield AI — [Run your free compliance audit](/audit) today.*`;

  fs.writeFileSync(filepath, `${frontmatter}\n\n${body}\n`);
  console.log(`  ✅  Post written → src/data/post/${filename}`);
  return filename;
}

// ── Main loop ─────────────────────────────────────────────────────────────────
(async () => {
  console.log(`🚀  TradeShield AI Bulk Builder — generating ${RUN_COUNT} posts\n`);

  const geminiKey = await getGeminiKey();
  console.log('🔐  GEMINI_API_KEY loaded from Secret Manager\n');

  const topics  = TOPIC_SETS.slice(0, RUN_COUNT);
  const created = [];

  for (let i = 0; i < topics.length; i++) {
    const topic = topics[i];
    console.log(`\n━━━ [${i + 1}/${topics.length}] ${topic.label} ━━━`);

    // 1. Fetch RSS for this topic
    const items = await fetchTopicItems(topic);

    // 2. Generate article
    let article;
    try {
      article = await generateArticle(items, topic, geminiKey);
      console.log(`  📝  Title: ${article.title}`);
    } catch (e) {
      console.error(`  ❌  Article generation failed for [${topic.label}]: ${e.message}`);
      continue;
    }

    // 3. Generate cover image (non-fatal)
    let imageSrc = null;
    try {
      imageSrc = await generateCoverImage(topic, i, geminiKey);
    } catch (e) {
      console.warn(`  ⚠️  Image error: ${e.message} — using fallback`);
    }

    // 4. Write post
    const filename = writePost(article, imageSrc, i);
    created.push(filename);

    // Polite delay between iterations to avoid API rate limits
    if (i < topics.length - 1) {
      console.log('  ⏳  Waiting 4s before next topic…');
      await sleep(4000);
    }
  }

  console.log(`\n✨  Done! ${created.length}/${topics.length} posts created:`);
  created.forEach(f => console.log(`    • src/data/post/${f}`));
  console.log('\n    Run  npm run dev  to preview them.\n');
})();
