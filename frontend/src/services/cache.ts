import { openDB, type IDBPDatabase } from 'idb';

const DB_NAME = 'proproo-cache';
const STORE_NAME = 'query-cache';
const TTL_MS = 24 * 60 * 60 * 1000; // 24 hours

interface CacheEntry {
  data: unknown;
  timestamp: number;
  sql: string;
}

let dbPromise: Promise<IDBPDatabase> | null = null;

/**
 * Get or create the IndexedDB database instance.
 */
async function getDB(): Promise<IDBPDatabase> {
  if (!dbPromise) {
    dbPromise = openDB(DB_NAME, 1, {
      upgrade(db) {
        if (!db.objectStoreNames.contains(STORE_NAME)) {
          db.createObjectStore(STORE_NAME);
        }
      },
    });
  }
  return dbPromise;
}

/**
 * Generate a simple hash from a SQL string for use as a cache key.
 */
function hashSQL(sql: string): string {
  let hash = 0;
  for (let i = 0; i < sql.length; i++) {
    const char = sql.charCodeAt(i);
    hash = ((hash << 5) - hash) + char;
    hash |= 0; // Convert to 32bit integer
  }
  return `query:${Math.abs(hash).toString(36)}`;
}

/**
 * Get cached data for a SQL query. Returns null if not found or stale.
 */
export async function get<T = unknown>(sql: string): Promise<T | null> {
  try {
    const db = await getDB();
    const key = hashSQL(sql);
    const entry = await db.get(STORE_NAME, key) as CacheEntry | undefined;

    if (!entry) return null;
    if (isStale(entry.timestamp)) return null;

    return entry.data as T;
  } catch (err) {
    console.warn('Cache get failed:', err);
    return null;
  }
}

/**
 * Cache data for a SQL query.
 */
export async function set(sql: string, data: unknown): Promise<void> {
  try {
    const db = await getDB();
    const key = hashSQL(sql);
    await db.put(STORE_NAME, {
      data,
      timestamp: Date.now(),
      sql,
    }, key);
  } catch (err) {
    console.warn('Cache set failed:', err);
  }
}

/**
 * Check if a cache entry is stale based on timestamp.
 */
export function isStale(timestamp: number): boolean {
  return Date.now() - timestamp > TTL_MS;
}

/**
 * Clear all cached data.
 */
export async function clear(): Promise<void> {
  try {
    const db = await getDB();
    await db.clear(STORE_NAME);
  } catch (err) {
    console.warn('Cache clear failed:', err);
  }
}

/**
 * Get cache statistics (for debugging).
 */
export async function getStats(): Promise<{ count: number; stale: number }> {
  try {
    const db = await getDB();
    const keys = await db.getAllKeys(STORE_NAME);
    let stale = 0;
    for (const key of keys) {
      const entry = await db.get(STORE_NAME, key as string) as CacheEntry | undefined;
      if (entry && isStale(entry.timestamp)) {
        stale++;
      }
    }
    return { count: keys.length, stale };
  } catch (err) {
    console.warn('Cache stats failed:', err);
    return { count: 0, stale: 0 };
  }
}
