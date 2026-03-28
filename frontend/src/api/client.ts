const API_BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:8000';

export async function apiFetch<T>(
  endpoint: string,
  params?: Record<string, string | number | undefined>
): Promise<T> {
  const url = new URL(`${API_BASE}${endpoint}`);
  if (params) {
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined) url.searchParams.set(k, String(v));
    });
  }
  const res = await fetch(url.toString());
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}