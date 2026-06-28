const CACHE_NAME = 'quiz-v3';
const ASSETS = [
  '/',
  '/index.html',
  '/quiz-data.js?v=2',
  '/manifest.json',
  '/icon-192.png',
  '/icon-512.png'
];

// 安装：预缓存核心资源
self.addEventListener('install', (e) => {
  e.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(ASSETS).catch(() => {
        // 部分资源可能失败（如图标），不阻塞安装
        return cache.addAll(['/index.html', '/quiz-data.js?v=2']);
      });
    })
  );
  self.skipWaiting();
});

// 激活：清理旧缓存
self.addEventListener('activate', (e) => {
  e.waitUntil(
    caches.keys().then((keys) => {
      return Promise.all(
        keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k))
      );
    })
  );
  self.clients.claim();
});

// 请求策略：Cache First，回退 Network
self.addEventListener('fetch', (e) => {
  e.respondWith(
    caches.match(e.request).then((cached) => {
      return cached || fetch(e.request).then((response) => {
        // 动态缓存新资源
        if (response.status === 200) {
          const clone = response.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(e.request, clone));
        }
        return response;
      });
    }).catch(() => {
      // 离线回退
      if (e.request.destination === 'document') {
        return caches.match('/index.html');
      }
    })
  );
});
