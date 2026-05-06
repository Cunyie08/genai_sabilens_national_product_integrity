const CACHE_NAME = 'sabilens-v1';
const urlsToCache = [
  '/',
  '/index.html',
  '/src/assets/SabiLens_Logo.png'
];

self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => cache.addAll(urlsToCache))
  );
});

self.addEventListener('fetch', event => {
  // Only cache GET requests for static assets.
  // API calls and POST requests must go directly to the network — passing a
  // large POST body (e.g. scan images) through the service worker pipe causes
  // the browser to fail with "Failed to fetch" on memory-constrained devices.
  if (
    event.request.method !== 'GET' ||
    event.request.url.includes('/api/')
  ) {
    return;
  }

  event.respondWith(
    caches.match(event.request)
      .then(response => response || fetch(event.request))
  );
});