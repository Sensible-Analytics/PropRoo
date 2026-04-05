const CACHE_NAME = 'proproo-v1';
const PARQUET_URLS = [
  'https://pub-1e149224362a4914aecb74b6c2adedbe.r2.dev/sales.parquet',
  'https://pub-1e149224362a4914aecb74b6c2adedbe.r2.dev/property_growth.parquet',
  'https://pub-1e149224362a4914aecb74b6c2adedbe.r2.dev/street_summary.parquet',
  'https://pub-1e149224362a4914aecb74b6c2adedbe.r2.dev/suburb_summary.parquet',
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(PARQUET_URLS))
  );
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k)))
    )
  );
  self.clients.claim();
});

self.addEventListener('fetch', (event) => {
  if (event.request.url.includes('.parquet')) {
    event.respondWith(
      caches.match(event.request).then((cached) => {
        if (cached) {
          // Stale-while-revalidate
          fetch(event.request).then((fresh) => {
            caches.open(CACHE_NAME).then((cache) => cache.put(event.request, fresh));
          });
          return cached;
        }
        return fetch(event.request).then((response) => {
          if (response.ok) {
            caches.open(CACHE_NAME).then((cache) => cache.put(event.request, response.clone()));
          }
          return response;
        });
      })
    );
  }
});
