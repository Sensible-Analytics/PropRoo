// Pages Function: /r2/*
// Proxies R2 bucket requests with CORS headers
// Server-side fetch has no CORS restrictions

const R2_BASE_URL = 'https://pub-1e149224362a4914aecb74b6c2adedbe.r2.dev';

export async function onRequest(context: any) {
  const { request, params } = context;

  // Extract the file path from the URL
  const filePath = params.path || '';
  const url = `${R2_BASE_URL}/${filePath}`;

  // Handle OPTIONS preflight
  if (request.method === 'OPTIONS') {
    return new Response(null, {
      status: 204,
      headers: {
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Methods': 'GET, HEAD, OPTIONS',
        'Access-Control-Allow-Headers': '*',
        'Access-Control-Max-Age': '86400',
      },
    });
  }

  // Fetch from R2 server-side (no CORS issue)
  const response = await fetch(url, {
    method: request.method,
    headers: {
      'Accept': request.headers.get('Accept') || '*/*',
    },
  });

  if (!response.ok) {
    return new Response(`R2 fetch failed: ${response.statusText}`, { status: response.status });
  }

  // Return with CORS headers
  const body = response.body;
  const headers = new Headers(response.headers);
  headers.set('Access-Control-Allow-Origin', '*');
  headers.set('Access-Control-Allow-Methods', 'GET, HEAD, OPTIONS');
  headers.set('Access-Control-Allow-Headers', '*');
  // Ensure Content-Type is correct
  if (!headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/octet-stream');
  }

  return new Response(body, {
    status: response.status,
    headers,
  });
}
