# SPEC: 阶段1 快而稳

## 目标
打开即用，3秒内可答题，微信内不白屏，离线可答题。

## 任务分解

### T1: UptimeRobot 保活
- 外部服务，需用户注册
- 每 5 分钟 ping https://3579828593.pythonanywhere.com/
- 解决 PythonAnywhere 免费层冷启动 5-10 秒问题
- 交付物：监控 URL 配置完成

### T2: Playwright E2E 测试框架
- 安装 Playwright + chromium
- 测试核心路径：加载→答题→提交→下一题→进度更新
- 测试数据隔离：新会话 0 题→答题→stats 正确
- 测试 SW 离线：断网后仍可显示缓存题目
- 文件：backend/tests/e2e/test_quiz_flow.py

### T3: Service Worker 离线答题
- sw.js 缓存 /api/questions 响应（NetworkFirst，fallback to cache）
- 离线时从缓存读取题目，答题暂存 localStorage
- 联网后自动同步暂存的答题记录
- SW 版本 v5 → v6
- 边界：缓存最多 351 题（约 500KB），不超过配额

### T4: 骨架屏 + 加载优化
- 骨架屏已有，优化过渡动画
- 题目加载用渐入动画
- 减少不必要的全屏 loading

### T5: Lighthouse 审计
- 运行 Lighthouse 审计
- 目标：性能 ≥ 80，FCP < 2 秒
- 优化点：字体加载策略、CSS 内联关键路径

## 验收标准
- [ ] UptimeRobot 配置完成
- [ ] Playwright E2E 至少 3 个测试通过
- [ ] 离线状态下可查看缓存题目
- [ ] Lighthouse 性能评分 ≥ 80
- [ ] 37/37 回归测试通过
- [ ] SW 版本升至 v6

## 涉及文件
- backend/static/sw.js — 离线缓存增强
- backend/static/js/app.js — 离线答题逻辑
- backend/static/js/sw-register.js — SW 更新提示
- backend/templates/index.html — 骨架屏优化
- backend/tests/e2e/ — Playwright 测试（新建）
