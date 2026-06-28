// ============================================================
// Service Worker 注册脚本 (PWA)
// 作为外部脚本加载,符合 CSP script-src 'self' 策略
// 含 SW 更新自动刷新: 检测到新版本时自动重载页面一次
// ============================================================
(function () {
  'use strict';
  if (!('serviceWorker' in navigator)) {
    return;
  }
  window.addEventListener('load', function () {
    navigator.serviceWorker
      .register('/sw.js', { scope: '/' })
      .then(function (reg) {
        console.log('[PWA] Service Worker 注册成功, scope:', reg.scope);

        // 检测到新 SW 等待中时,触发激活
        if (reg.waiting) {
          reg.waiting.postMessage({ type: 'SKIP_WAITING' });
        }

        // 新 SW 安装完成时,提示或自动刷新
        reg.addEventListener('updatefound', function () {
          var newWorker = reg.installing;
          newWorker.addEventListener('statechange', function () {
            if (newWorker.state === 'installed' && navigator.serviceWorker.controller) {
              // 新 SW 已安装,且页面有旧 SW 控制 -> 刷新页面加载新版本
              console.log('[PWA] 检测到新版本,自动刷新...');
              window.location.reload();
            }
          });
        });
      })
      .catch(function (err) {
        console.warn('[PWA] Service Worker 注册失败:', err);
      });

    // 控制器变更时刷新 (skipWaiting 后触发)
    navigator.serviceWorker.addEventListener('controllerchange', function () {
      // 避免无限刷新: 只在首次 controllerchange 时刷新
      if (!window.__swReloaded) {
        window.__swReloaded = true;
        window.location.reload();
      }
    });
  });
})();
