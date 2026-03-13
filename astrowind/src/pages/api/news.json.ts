// AI Trade Audit — News API route
// Pre-rendered at build time: fetches all RSS feeds in parallel and emits a
// static /api/news JSON snapshot. Client blog.astro fetches this at runtime;
// on miss it falls back to direct browser-side rss2json calls.
export const prerender = true;

import type { APIRoute } from 'astro';

interface NewsCard {
  q: string;
  cat: string;
  col: string;
  icon: string;
  title: string;
  summary: string;
  impact: 'HIGH' | 'MEDIUM' | 'LOW';
  impCol: string;
  freshness: string;
  link: string;
  source: string;
}

interface Cache {
  ts: number;
  data: NewsCard[];
}

const CACHE_TTL = 5 * 60 * 1000; // 5 minutes
let _cache: Cache | null = null;

const QUERIES = [
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
] as const;

async function fetchCategory(entry: (typeof QUERIES)[number]): Promise<NewsCard[]> {
  const rssUrl = `https://news.google.com/rss/search?q=${entry.q}&hl=en-US&gl=US&ceid=US:en`;
  const proxy = `https://api.rss2json.com/v1/api.json?rss_url=${encodeURIComponent(rssUrl)}&count=2`;
  const res = await fetch(proxy, { signal: AbortSignal.timeout(8000) });
  if (!res.ok) return [];
  const data = await res.json();
  return ((data.items ?? []) as Record<string, unknown>[]).slice(0, 2).map(item => {
    const pubDate = new Date(item.pubDate as string);
    const daysAgo = Math.floor((Date.now() - pubDate.getTime()) / 86400000);
    const freshness = daysAgo === 0 ? 'Today' : daysAgo === 1 ? 'Yesterday' : `${daysAgo}d ago`;
    const impact: 'HIGH' | 'MEDIUM' | 'LOW' = daysAgo < 3 ? 'HIGH' : daysAgo < 10 ? 'MEDIUM' : 'LOW';
    const impCol = impact === 'HIGH' ? '#f87171' : impact === 'MEDIUM' ? '#fbbf24' : '#34d399';
    // Strip HTML tags from description
    const raw = ((item.description ?? item.title ?? '') as string).replace(/<[^>]+>/g, '').trim();
    const summary = raw.length > 160 ? raw.slice(0, 157) + '…' : raw;
    let source = '';
    try { source = new URL(item.link as string).hostname.replace('www.', ''); } catch { /* ignore */ }
    return { ...entry, title: item.title as string, summary, impact, impCol, freshness, link: item.link as string, source };
  });
}

export const GET: APIRoute = async ({ url }) => {
  const cat = url.searchParams.get('cat') || 'all';

  // Serve from cache if fresh
  if (_cache && Date.now() - _cache.ts < CACHE_TTL) {
    const articles = cat === 'all' ? _cache.data : _cache.data.filter(a => a.cat === cat);
    return new Response(JSON.stringify({ articles, cached: true, timestamp: new Date(_cache.ts).toISOString() }), {
      headers: { 'Content-Type': 'application/json', 'Cache-Control': 'public, max-age=300' },
    });
  }

  // Fetch all categories in parallel
  const results = await Promise.allSettled(QUERIES.map(fetchCategory));
  const articles = results.flatMap(r => r.status === 'fulfilled' ? r.value : []);
  _cache = { ts: Date.now(), data: articles };

  const filtered = cat === 'all' ? articles : articles.filter(a => a.cat === cat);
  return new Response(JSON.stringify({ articles: filtered, cached: false, timestamp: new Date().toISOString() }), {
    headers: { 'Content-Type': 'application/json', 'Cache-Control': 'public, max-age=300' },
  });
};
