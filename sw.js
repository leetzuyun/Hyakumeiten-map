/* sw.js — Service Worker for 百名店地圖 PWA */
const CACHE_NAME = 'hyakumeiten-v1';

// 安裝時快取核心資源
const PRECACHE = [
  './',
  './index.html',
  './restaurants_data.json',
  'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.css',
  'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.js',
  'https://cdnjs.cloudflare.com/ajax/libs/leaflet.markercluster/1.5.3/MarkerCluster.css',
  'https://cdnjs.cloudflare.com/ajax/libs/leaflet.markercluster/1.5.3/MarkerCluster.Default.css',
  'https://cdnjs.cloudflare.com/ajax/libs/leaflet.markercluster/1.5.3/leaflet.markercluster.min.js',
];

self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache => {
      // 逐一嘗試快取，失敗的不阻擋安裝
      return Promise.allSettled(PRECACHE.map(url => cache.add(url)));
    })
  );
  self.skipWaiting();
});

self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(keys =>
      Promise.all(keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k)))
    )
  );
  self.clients.claim();
});

// Stale-while-revalidate 策略：
// 地圖圖磚 (tile) → cache first，離線可用
// 其他資源 → 先回快取，背景更新
self.addEventListener('fetch', event => {
  const url = new URL(event.request.url);

  // OSM 地圖圖磚：cache first
  if (url.hostname.endsWith('tile.openstreetmap.org')) {
    event.respondWith(
      caches.match(event.request).then(cached => {
        if (cached) return cached;
        return fetch(event.request).then(resp => {
          if (!resp || resp.status !== 200) return resp;
          const clone = resp.clone();
          caches.open(CACHE_NAME).then(c => c.put(event.request, clone));
          return resp;
        }).catch(() => cached);
      })
    );
    return;
  }

  // 其他：network first，失敗回 cache
  event.respondWith(
    fetch(event.request)
      .then(resp => {
        if (!resp || resp.status !== 200 || event.request.method !== 'GET') return resp;
        const clone = resp.clone();
        caches.open(CACHE_NAME).then(c => c.put(event.request, clone));
        return resp;
      })
      .catch(() => caches.match(event.request))
  );
});
