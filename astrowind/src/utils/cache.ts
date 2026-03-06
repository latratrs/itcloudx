type CacheEntry = {
  data: any;
  expiresAt: number;
};

const cache = new Map<string, CacheEntry>();
const TTL = 5 * 60 * 1000; // 5 minutes

export function getCache(key: string): any | null {
  const entry = cache.get(key);
  if (!entry) return null;
  if (Date.now() > entry.expiresAt) {
    cache.delete(key);
    return null;
  }
  return entry.data;
}

export function setCache(key: string, data: any): void {
  cache.set(key, { data, expiresAt: Date.now() + TTL });
}

export async function fetchWithCache(url: string): Promise<any> {
  const cached = getCache(url);
  if (cached) return cached;
  const response = await fetch(url);
  const data = await response.json();
  setCache(url, data);
  return data;
}
