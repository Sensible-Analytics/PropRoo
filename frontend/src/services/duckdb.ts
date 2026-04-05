import * as duckdb from '@duckdb/duckdb-wasm';
import duckdb_wasm from '@duckdb/duckdb-wasm/dist/duckdb-mvp.wasm?url';
import mvp_worker_bundled from '@duckdb/duckdb-wasm/dist/duckdb-browser-mvp.worker.js?url';
import duckdb_wasm_eh from '@duckdb/duckdb-wasm/dist/duckdb-eh.wasm?url';
import eh_worker_bundled from '@duckdb/duckdb-wasm/dist/duckdb-browser-eh.worker.js?url';
import { Table } from 'apache-arrow';
import { getCachedQuery, cacheQueryResult } from './query-cache';

// R2 public bucket (CORS configured for direct browser access)
const R2_BASE_URL = 'https://pub-1e149224362a4914aecb74b6c2adedbe.r2.dev';

// Parquet files to load on startup
const PARQUET_FILES = [
  { name: 'sales', url: `${R2_BASE_URL}/sales.parquet` },
  { name: 'property_growth', url: `${R2_BASE_URL}/property_growth.parquet` },
  { name: 'street_summary', url: `${R2_BASE_URL}/street_summary.parquet` },
  { name: 'suburb_summary', url: `${R2_BASE_URL}/suburb_summary.parquet` },
] as const;

export type ProgressCallback = (file: string, pct: number) => void;

let dbInstance: duckdb.AsyncDuckDB | null = null;
let connInstance: duckdb.AsyncDuckDBConnection | null = null;
let initialized = false;

/**
 * Select the appropriate DuckDB WASM bundle for the current browser.
 */
async function selectBundle(): Promise<duckdb.DuckDBBundle> {
  const manualBundle: duckdb.DuckDBBundles = {
    mvp: {
      mainModule: duckdb_wasm,
      mainWorker: mvp_worker_bundled,
    },
    eh: {
      mainModule: duckdb_wasm_eh,
      mainWorker: eh_worker_bundled,
    },
  };
  const bundle = await duckdb.selectBundle(manualBundle);
  return bundle;
}

/**
 * Initialize DuckDB-WASM, load all parquet files from R2 in parallel.
 */
export async function initDuckDB(onProgress?: ProgressCallback): Promise<{
  db: duckdb.AsyncDuckDB;
  conn: duckdb.AsyncDuckDBConnection;
}> {
  if (initialized && dbInstance && connInstance) {
    return { db: dbInstance, conn: connInstance };
  }

  const bundle = await selectBundle();
  const worker = new Worker(bundle.mainWorker!);
  const logger = new duckdb.ConsoleLogger();
  const db = new duckdb.AsyncDuckDB(logger, worker);
  await db.instantiate(bundle.mainModule, bundle.pthreadWorker);

  const conn = await db.connect();
  dbInstance = db;
  connInstance = conn;

  // Load ALL parquet files in PARALLEL
  await Promise.all(
    PARQUET_FILES.map(async ({ name, url }) => {
      onProgress?.(name, 0);

      const response = await fetch(url);
      if (!response.ok) {
        throw new Error(`Failed to fetch ${url}: ${response.statusText}`);
      }

      const contentLength = response.headers.get('content-length');
      const total = contentLength ? parseInt(contentLength, 10) : 0;
      let loaded = 0;

      const reader = response.body?.getReader();
      if (!reader) {
        throw new Error('ReadableStream not supported');
      }

      const chunks: Uint8Array[] = [];
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        chunks.push(value);
        loaded += value.length;
        if (total > 0) {
          onProgress?.(name, Math.round((loaded / total) * 100));
        }
      }

      const buffer = new Uint8Array(loaded);
      let offset = 0;
      for (const chunk of chunks) {
        buffer.set(chunk, offset);
        offset += chunk.length;
      }

      onProgress?.(name, 100);

      await db!.registerFileBuffer(name, buffer);
      await conn!.query(`CREATE TABLE IF NOT EXISTS ${name} AS SELECT * FROM read_parquet('${name}')`);
    })
  );

  initialized = true;
  return { db, conn };
}

/**
 * Execute a SQL query and return results as plain objects.
 */
export async function query<T = Record<string, unknown>>(sql: string): Promise<T[]> {
  if (!connInstance) {
    throw new Error('DuckDB not initialized. Call initDuckDB() first.');
  }

  // Check cache first
  const cached = await getCachedQuery<T[]>(sql);
  if (cached) return cached;

  const arrowTable: Table = await connInstance.query(sql);
  const rows = arrowTable.toArray().map((row) => row.toJSON()) as T[];

  // Cache the result
  await cacheQueryResult(sql, rows);

  return rows;
}

/**
 * Get the raw DuckDB instance for advanced operations.
 */
export function getDuckDB(): duckdb.AsyncDuckDB | null {
  return dbInstance;
}

/**
 * Get the raw connection instance for advanced operations.
 */
export function getConnection(): duckdb.AsyncDuckDBConnection | null {
  return connInstance;
}

/**
 * Check if DuckDB has been initialized.
 */
export function isInitialized(): boolean {
  return initialized;
}

/**
 * Reset DuckDB state (useful for testing or re-initialization).
 */
export async function resetDuckDB(): Promise<void> {
  if (connInstance) {
    await connInstance.close();
    connInstance = null;
  }
  if (dbInstance) {
    await dbInstance.terminate();
    dbInstance = null;
  }
  initialized = false;
}

// Re-export the R2 base URL for use in other modules
export { R2_BASE_URL };
