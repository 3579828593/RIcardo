// ============================================================
// Service Worker 注册脚本 (PWA)
// 作为外部脚本加载,符合 CSP script-src 'self' 策略
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
      })
      .catch(function (err) {
        console.warn('[PWA] Service Worker 注册失败:', err);
      });
  });
})();
