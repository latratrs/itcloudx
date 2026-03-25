/**
 * TradeShield AI — News Ingestion Function
 * Firebase Cloud Function (Node.js 20)
 *
 * Fetches trade compliance RSS feeds directly from Google News using xml2js,
 * caches results in memory (5 min) and optionally in Firestore (30 min),
 * and returns structured JSON to the blog dashboard.
 *
 * Deploy: firebase deploy --only functions:fetchNews
 */

'use strict';

const { onRequest } = require('firebase-functions/v2/https');
const admin = require('firebase-admin');
const fetch = require('node-fetch');
const xml2js = require('xml2js');

if (!admin.apps.length) admin.initializeApp();
const db = admin.firestore();

// ── Feed definitions ──────────────────────────────────────────────────────────
const FEEDS = [
  { q: 'OFAC+sanctions+penalty+fine+2026',             cat: 'SANCTIONS',       col: '#f87171', icon: '🚨' },
  { q: 'DOJ+trade+fraud+tariff+evasion+criminal+2026', cat: 'ENFORCEMENT',     col: '#fb923c', icon: '⚖️' },
  { q: 'UFLPA+forced+labor+CBP+detention+2026',        cat: 'FORCED LABOR',    col: '#f87171', icon: '🔴' },
  { q: 'US+tariffs+Section+301+import+duties+2026',    cat: 'TARIFFS',         col: '#fbbf24', icon: '💰' },
  { q: 'anti-dumping+countervailing+duty+ruling+2026', cat: 'AD/CVD',          col: '#fbbf24', icon: '📋' },
  { q: 'BIS+export+controls+China+chips+2026',         cat: 'EXPORT CONTROLS', col: '#60a5fa', icon: '🔒' },
  { q: 'Red+Sea+shipping+disruption+freight+2026',     cat: 'SHIPPING',        col: '#818cf8', icon: '🚢' },
  { q: 'CBP+HTS+customs+classification+filing+2026',   cat: 'CUSTOMS FILING',  col: '#34d399', icon: '📑' },
  { q: 'China+retaliatory+tariff+trade+policy+2026',   cat: 'CHINA TRADE',     col: '#38bdf8', icon: '🌏' },
  { q: 'EU+CBAM+carbon+border+adjustment+2026',        cat: 'EU REGULATION',   col: '#a78bfa', icon: '🌿' },
];

const MEM_CACHE_TTL  = 5  * 60 * 1000; // 5 min in-process
const FIRE_CACHE_TTL = 30 * 60 * 1000; // 30 min Firestore
const FIRESTORE_DOC  = 'cache/news_feed';

// ── Phone normaliser — Rule 3: all numbers must be 555-555-5555 format ────────
function formatSherlock(text) {
  if (!text) return text;
  return text
    .replace(/\b(\d{1})[\s.\-]?(\d{3})[\s.\-]?(\d{3})[\s.\-]?(\d{4})\b/g, '$1-$2-$3-$4')
    .replace(/\((\d{3})\)[\s.\-]?(\d{3})[\s.\-]?(\d{4})\b/g, '$1-$2-$3')
    .replace(/\b(\d{3})[\s.\-](\d{3})[\s.\-](\d{4})\b/g, '$1-$2-$3');
}

// ── In-memory cache ───────────────────────────────────────────────────────────
let _memCache = null;

// ── RSS fetch + parse one feed entry ─────────────────────────────────────────
async function fetchFeed(entry) {
  const rssUrl = `https://news.google.com/rss/search?q=${entry.q}&hl=en-US&gl=US&ceid=US:en`;
  const res = await fetch(rssUrl, { timeout: 8000 });
  if (!res.ok) return [];
  const xml = await res.text();
  const parsed = await xml2js.parseStringPromise(xml, { explicitArray: false });
  const raw = parsed?.rss?.channel?.item;
  const items = (Array.isArray(raw) ? raw : raw ? [raw] : []).slice(0, 2);

  return items.map(item => {
    const pubDate  = new Date(item.pubDate || Date.now());
    const daysAgo  = Math.floor((Date.now() - pubDate.getTime()) / 86400000);
    const freshness = daysAgo === 0 ? 'Today' : daysAgo === 1 ? 'Yesterday' : `${daysAgo}d ago`;
    const impact   = daysAgo < 3 ? 'HIGH' : daysAgo < 10 ? 'MEDIUM' : 'LOW';
    const impCol   = impact === 'HIGH' ? '#f87171' : impact === 'MEDIUM' ? '#fbbf24' : '#34d399';

    // Strip HTML tags, apply phone normaliser
    const stripped = (item.description || item.title || '').replace(/<[^>]+>/g, '').trim();
    const summary  = formatSherlock(stripped.length > 200 ? stripped.slice(0, 197) + '…' : stripped);
    const title    = formatSherlock(item.title || '');

    let source = '';
    try { source = new URL(item.link).hostname.replace('www.', ''); } catch { /* ignore */ }

    return {
      cat: entry.cat, col: entry.col, icon: entry.icon,
      title, summary, impact, impCol, freshness,
      link: item.link || '#', source,
      publishedMs: pubDate.getTime(),
    };
  });
}

// ── Cloud Function ────────────────────────────────────────────────────────────
exports.fetchNews = onRequest(
  { cors: ['https://itcloudx.com', 'https://www.itcloudx.com', 'http://localhost:4321'],
    memory: '256MiB', timeoutSeconds: 30 },
  async (req, res) => {
    const cat = req.query.cat || 'all';

    // 1. Return in-memory cache if fresh
    if (_memCache && Date.now() - _memCache.ts < MEM_CACHE_TTL) {
      const articles = cat === 'all' ? _memCache.data : _memCache.data.filter(a => a.cat === cat);
      return res.json({ articles, cached: true, source: 'memory',
                        timestamp: new Date(_memCache.ts).toISOString() });
    }

    // 2. Try Firestore cache (survives cold starts)
    try {
      const snap = await db.doc(FIRESTORE_DOC).get();
      if (snap.exists) {
        const d = snap.data();
        if (d.ts && (Date.now() - d.ts) < FIRE_CACHE_TTL) {
          _memCache = { ts: d.ts, data: d.articles };
          const articles = cat === 'all' ? d.articles : d.articles.filter(a => a.cat === cat);
          return res.json({ articles, cached: true, source: 'firestore',
                            timestamp: new Date(d.ts).toISOString() });
        }
      }
    } catch (_e) { /* Firestore optional — continue to live fetch */ }

    // 3. Live fetch — all feeds in parallel
    const results  = await Promise.allSettled(FEEDS.map(fetchFeed));
    const articles = results.flatMap(r => r.status === 'fulfilled' ? r.value : []);
    const ts       = Date.now();

    _memCache = { ts, data: articles };

    // Persist to Firestore asynchronously (don't await — don't delay response)
    db.doc(FIRESTORE_DOC).set({ articles, ts }).catch(() => {});

    const filtered = cat === 'all' ? articles : articles.filter(a => a.cat === cat);
    res.setHeader('Cache-Control', 'public, max-age=300');
    res.json({ articles: filtered, cached: false, source: 'live',
               timestamp: new Date(ts).toISOString() });
  }
);
