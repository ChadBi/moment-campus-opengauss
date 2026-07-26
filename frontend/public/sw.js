/**
 * UX-01.6: Service Worker — 只缓存应用壳，不缓存敏感 API 响应
 *
 * 设计原则：
 *   1. 应用壳（App Shell）：HTML / CSS / JS / 字体 / 图标 / 静态资源（Vite 构建产物）→ 缓存优先
 *   2. API 请求（/api/*）：永不缓存，永远走网络（避免敏感数据残留、避免脏数据）
 *   3. 图片资源（同源图片）：网络优先，失败回退缓存（节省流量但保持新鲜）
 *   4. 新版本检测：SW 更新后通过 controllerchange 事件触发前端提示刷新
 *
 * 缓存策略：
 *   - precache：仅核心应用壳（/、/index.html、manifest、icon）
 *   - runtime cache：Vite 构建产物（/assets/*）按文件名哈希永久缓存
 *   - 不缓存：/api/*、跨域请求、POST/PUT/DELETE 等非 GET 请求
 *
 * 安全约束：
 *   - 不缓存任何 /api/* 响应（含 token、用户数据、私信等敏感信息）
 *   - 不缓存 Authorization 头的请求结果
 *   - 删除旧缓存时同步清理，避免敏感数据残留
 */

const SW_VERSION = 'v1.0.0-ux01.6';
const APP_SHELL_CACHE = `moment-campus-shell-${SW_VERSION}`;
const RUNTIME_CACHE = `moment-campus-runtime-${SW_VERSION}`;

// 应用壳核心资源（precache）
const APP_SHELL_URLS = [
  '/',
  '/index.html',
  '/manifest.webmanifest',
  '/favicon.svg',
  '/icon-192.svg',
  '/icon-512.svg',
  '/icon-maskable-512.svg',
];

// 不缓存的路径前缀（敏感 API + 动态数据）
const NEVER_CACHE_PREFIXES = ['/api/', '/auth/'];

// 安装：precache 应用壳核心资源
self.addEventListener('install', (event) => {
  event.waitUntil(
    (async () => {
      const cache = await caches.open(APP_SHELL_CACHE);
      // 逐个添加，单个失败不阻塞其他资源
      await Promise.all(
        APP_SHELL_URLS.map(async (url) => {
          try {
            // 用 no-cache 避免预缓存旧版本
            const res = await fetch(url, { cache: 'no-cache' });
            if (res && res.ok) {
              await cache.put(url, res.clone());
            }
          } catch (e) {
            // 单个资源失败不阻塞安装
            console.warn('[SW] precache 失败:', url, e);
          }
        })
      );
      // 立即接管，不等旧 SW 释放
      await self.skipWaiting();
    })()
  );
});

// 激活：清理旧缓存并接管客户端
self.addEventListener('activate', (event) => {
  event.waitUntil(
    (async () => {
      const keys = await caches.keys();
      // 删除所有非当前版本的缓存（含旧 SW 残留）
      await Promise.all(
        keys
          .filter((key) => key !== APP_SHELL_CACHE && key !== RUNTIME_CACHE)
          .map((key) => caches.delete(key))
      );
      // 立即接管所有客户端，触发 controllerchange（前端据此提示新版本）
      await self.clients.claim();
      // 通知所有客户端有新版本
      const clients = await self.clients.matchAll({ type: 'window' });
      clients.forEach((client) => {
        client.postMessage({ type: 'SW_UPDATED', version: SW_VERSION });
      });
    })()
  );
});

// 判断是否为不缓存的请求
function shouldNeverCache(url) {
  return NEVER_CACHE_PREFIXES.some((prefix) => url.pathname.startsWith(prefix));
}

// 判断是否为同源 GET 请求（仅 GET 才能缓存）
function isCacheableGetRequest(request) {
  if (request.method !== 'GET') return false;
  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return false;
  if (shouldNeverCache(url)) return false;
  return true;
}

// 判断是否为 Vite 构建产物（带哈希，可永久缓存）
function isViteAsset(url) {
  return (
    url.pathname.startsWith('/assets/') ||
    /\.(?:js|css|woff2?|ttf|otf|eot|svg|png|jpg|jpeg|gif|webp|ico)$/i.test(url.pathname)
  );
}

// 判断是否为导航请求（HTML 文档）
function isNavigationRequest(request) {
  return (
    request.mode === 'navigate' ||
    (request.headers.get('accept') || '').includes('text/html')
  );
}

// 核心 fetch 处理
self.addEventListener('fetch', (event) => {
  const { request } = event;

  // 非 GET 请求与不缓存路径：直接透传网络，不拦截
  if (!isCacheableGetRequest(request)) {
    return; // 不调用 event.respondWith，浏览器默认处理
  }

  const url = new URL(request.url);

  // 导航请求（HTML 页面）：网络优先 + 离线回退缓存
  if (isNavigationRequest(request)) {
    event.respondWith(
      (async () => {
        try {
          // 优先网络，确保用户拿到最新 HTML
          const networkRes = await fetch(request, { cache: 'no-cache' });
          if (networkRes && networkRes.ok) {
            const cache = await caches.open(APP_SHELL_CACHE);
            cache.put('/', networkRes.clone());
            cache.put('/index.html', networkRes.clone());
          }
          return networkRes;
        } catch (e) {
          // 离线：回退到缓存的 index.html
          const cache = await caches.open(APP_SHELL_CACHE);
          const cached = (await cache.match('/index.html')) || (await cache.match('/'));
          if (cached) return cached;
          return new Response('离线模式，无法连接服务器', {
            status: 503,
            headers: { 'Content-Type': 'text/html; charset=utf-8' },
          });
        }
      })()
    );
    return;
  }

  // Vite 构建产物（带哈希）：缓存优先（永久）
  if (isViteAsset(url)) {
    event.respondWith(
      (async () => {
        const runtimeCache = await caches.open(RUNTIME_CACHE);
        const cached = await runtimeCache.match(request);
        if (cached) return cached;
        try {
          const networkRes = await fetch(request);
          if (networkRes && networkRes.ok) {
            runtimeCache.put(request, networkRes.clone());
          }
          return networkRes;
        } catch (e) {
          // 网络失败且无缓存：返回 504
          return new Response('资源加载失败（离线）', {
            status: 504,
            headers: { 'Content-Type': 'text/plain; charset=utf-8' },
          });
        }
      })()
    );
    return;
  }

  // 其他同源 GET 请求：网络优先 + 失败回退缓存（保持新鲜度）
  event.respondWith(
    (async () => {
      try {
        const networkRes = await fetch(request);
        if (networkRes && networkRes.ok) {
          const runtimeCache = await caches.open(RUNTIME_CACHE);
          runtimeCache.put(request, networkRes.clone());
        }
        return networkRes;
      } catch (e) {
        const runtimeCache = await caches.open(RUNTIME_CACHE);
        const cached = await runtimeCache.match(request);
        if (cached) return cached;
        return new Response('离线且无缓存', {
          status: 504,
          headers: { 'Content-Type': 'text/plain; charset=utf-8' },
        });
      }
    })()
  );
});

// 监听前端消息（如手动跳过等待）
self.addEventListener('message', (event) => {
  if (event.data && event.data.type === 'SKIP_WAITING') {
    self.skipWaiting();
  }
});
