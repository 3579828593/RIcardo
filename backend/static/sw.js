// ============================================================
// 期末冲刺刷题系统 Service Worker
// 版本: v7
// 策略:
//   - 首页 / 与核心静态资源: 预缓存 (precache)
//   - 静态资源 (/static/...): StaleWhileRevalidate (先返回缓存,后台更新)
//   - API 请求 (/api/...): NetworkFirst (回退缓存,支持离线读)
//   - 其他导航请求: NetworkFirst, 离线回退到缓存的首页
// ============================================================

const CACHE_VERSION = 'v7';
const STATIC_CACHE = `quiz-static-${CACHE_VERSION}`;
const API_CACHE = `quiz-api-${CACHE_VERSION}`;
const RUNTIME_CACHE = `quiz-runtime-${CACHE_VERSION}`;

// 预缓存的核心资源
const PRECACHE_URLS = [
  '/',
  '/static/vendor/vue.global.prod.js',
  '/static/js/app.js',
  '/static/manifest.json',
  '/static/icons/icon-192.jpg',
  '/static/icons/icon-512.jpg'
];

// ---------- 安装: 预缓存核心资源 ----------
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(STATIC_CACHE).then((cache) => {
      // 使用 addAll 容错: 单个资源失败不阻塞安装
      return Promise.all(
        PRECACHE_URLS.map((url) =>
          cache.add(url).catch((err) => {
            console.warn('[SW] 预缓存失败:', url, err);
          })
        )
      );
    })
  );
  // 立即激活,不必等待旧 SW 释放
  self.skipWaiting();
});

// ---------- 消息: 处理 SKIP_WAITING ----------
self.addEventListener('message', (event) => {
  if (event.data && event.data.type === 'SKIP_WAITING') {
    self.skipWaiting();
  }
});

// ---------- 激活: 清理旧版本缓存 ----------
self.addEventListener('activate', (event) => {
  const validCaches = new Set([STATIC_CACHE, API_CACHE, RUNTIME_CACHE]);
  event.waitUntil(
    caches.keys().then((keys) => {
      return Promise.all(
        keys
          .filter((key) => !validCaches.has(key))
          .map((key) => {
            console.log('[SW] 清理旧缓存:', key);
            return caches.delete(key);
          })
      );
    }).then(() => self.clients.claim())
  );
});

// ---------- 工具函数 ----------
function isApiRequest(url) {
  return url.pathname.startsWith('/api/');
}

function isStaticAsset(url) {
  return url.pathname.startsWith('/static/');
}

// StaleWhileRevalidate: 先返回缓存(快),同时后台拉取最新版本更新缓存
// 这样用户永远能快速加载,同时下次访问就是最新版本
async function staleWhileRevalidate(request, cacheName) {
  const cache = await caches.open(cacheName);
  const cached = await cache.match(request);
  const fetchPromise = fetch(request).then((response) => {
    if (response && response.status === 200) {
      cache.put(request, response.clone());
    }
    return response;
  }).catch(() => cached);
  return cached || fetchPromise;
}

// CacheFirst: 优先缓存,缓存未命中再回网络(并把结果写入缓存)
async function cacheFirst(request, cacheName) {
  const cache = await caches.open(cacheName);
  const cached = await cache.match(request);
  if (cached) {
    return cached;
  }
  try {
    const response = await fetch(request);
    if (response && response.status === 200) {
      cache.put(request, response.clone());
    }
    return response;
  } catch (err) {
    // 离线且无缓存
    return Response.error();
  }
}

// NetworkFirst: 优先网络,失败回退缓存(离线可读)
async function networkFirst(request, cacheName) {
  const cache = await caches.open(cacheName);
  try {
    const response = await fetch(request);
    if (response && response.status === 200) {
      cache.put(request, response.clone());
    }
    return response;
  } catch (err) {
    const cached = await cache.match(request);
    if (cached) {
      return cached;
    }
    return Response.error();
  }
}

// ---------- 请求拦截 ----------
self.addEventListener('fetch', (event) => {
  const req = event.request;

  // 只处理同源 GET 请求
  const url = new URL(req.url);
  if (req.method !== 'GET' || url.origin !== self.location.origin) {
    return;
  }

  // 1) API 请求 -> NetworkFirst
  if (isApiRequest(url)) {
    event.respondWith(networkFirst(req, API_CACHE));
    return;
  }

  // 2) 静态资源 -> StaleWhileRevalidate (先返回缓存,后台更新)
  if (isStaticAsset(url)) {
    event.respondWith(staleWhileRevalidate(req, STATIC_CACHE));
    return;
  }

  // 3) 导航请求 (HTML 文档) -> NetworkFirst, 离线回退首页
  if (req.mode === 'navigate') {
    event.respondWith(
      (async () => {
        try {
          const response = await fetch(req);
          const cache = await caches.open(RUNTIME_CACHE);
          cache.put(req, response.clone());
          return response;
        } catch (err) {
          const cached = await caches.match(req);
          if (cached) return cached;
          // 最终回退到预缓存的首页
          return (await caches.match('/')) || Response.error();
        }
      })()
    );
    return;
  }

  // 4) 其他 GET 请求 -> CacheFirst (运行时缓存)
  event.respondWith(cacheFirst(req, RUNTIME_CACHE));
});
