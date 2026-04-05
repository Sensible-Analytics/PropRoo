import { openDB, type IDBPDatabase } from 'idb';

const DB_NAME = 'proproo-query-cache';
const STORE_NAME = 'query-results';

const TTL = {
  street: 7 * 24 * 60 * 60 * 1000,
  suburb: 24 * 60 * 60 * 1000,
  sales: 60 * 60 * 1000,
  generic: 30 * 60 * 1000,
} as const;

function generateCacheKey(sql: string): string {
  const normalized = sql.toLowerCase().replace(/\s+/g, ' ').trim();
  let hash = 0;
  for (let i = 0; i < normalized.length; i++) {
    hash = ((hash << 5) - hash) + normalized.charCodeAt(i);
    hash |= 0;
  }
  return `q:${Math.abs(hash).toString(36)}`;
}

function detectQueryType(sql: string): keyof typeof TTL {
  const lower = sql.toLowerCase();
  if (lower.includes('street')) return 'street';
  if (lower.includes('suburb')) return 'suburb';
  if (lower.includes('sales')) return 'sales';
  return 'generic';
}

async function getDB(): Promise<IDBPDatabase> {
  return openDB(DB_NAME, 1, {
    upgrade(db) {
      if (!db.objectStoreNames.contains(STORE_NAME)) {
        db.createObjectStore(STORE_NAME, { keyPath: 'key' });
      }
    },
  });
}

export async function getCachedQuery<T>(sql: string): Promise<T | null> {
  try {
    const db = await getDB();
    const key = generateCacheKey(sql);
    const entry = await db.get(STORE_NAME, key);
    if (!entry) return null;
    const age = Date.now() - entry.timestamp;
    const ttl = TTL[detectQueryType(sql)];
    if (age > ttl) {
      await db.delete(STORE_NAME, key);
      return null;
    }
    return entry.data as T;
  } catch { return null; }
}

export async function cacheQueryResult<T>(sql: string, data: T): Promise<void> {
  try {
    const db = await getDB();
    const key = generateCacheKey(sql);
    await db.put(STORE_NAME, { key, data, timestamp: Date.now() });
  } catch {}
}

export async function invalidateCache(pattern?: string): Promise<void> {
  try {
    const db = await getDB();
    if (!pattern) { await db.clear(STORE_NAME); return; }
    const keys = await db.getAllKeys(STORE_NAME);
    for (const key of keys) {
      if (String(key).includes(pattern)) await db.delete(STORE_NAME, key);
    }
  } catch {}
}
