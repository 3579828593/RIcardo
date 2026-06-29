# 任务清单

> 状态机：[ ] 未开始 → [~] 进行中 → [x] 已完成 → [!] 阻塞

## 已完成任务

- [x] Phase 1: 基础 Bug 修复 (commit: dddccd0)
- [x] Phase 2: UI 优化 + 筛选重构 (commit: 196b7b1)
- [x] Phase 2.5: 遗漏修复 + Anki 复习 (commit: cc2b15c)
- [x] Phase 3: 白屏修复 + 数据隔离 (commit: c3c50a8)
- [x] Phase 4: 单题流重构 (commit: 55e6ef0)
- [x] Phase 4.1: 工作流遗漏修复 (commit: d7725a7)
- [x] Phase 5: SDD 工作流体系建设 (commit: b3f9b04, 2026-06-29)
- [x] Phase 5.1: doneSet 服务端同步 (commit: d243602, 2026-06-29)

## 待办任务

### 高优先级

- [ ] 浏览器实际交互测试 (引入 Playwright E2E)
  - 测试单题流：答题 → 下一题跳过已做 → 进度条更新
  - 测试数据隔离：新会话 0 题 → 答题 → stats 正确
  - 测试 SW 更新：旧版本 → 新版本自动刷新
  - 测试 doneSet 同步：清除 localStorage → 刷新 → doneSet 从服务端恢复

- [~] doneSet 服务端同步 — 已实现，待多设备实际验证
  - 从 /api/stats 获取 answered_question_ids，恢复 doneSet
  - 解决换设备后进度丢失问题
  - 已部署线上，API 验证通过

### 中优先级

- [ ] UptimeRobot 定时 ping 保活
  - 解决 PythonAnywhere 免费层冷启动 5-10 秒问题
  - 每 5 分钟 ping 一次首页

- [ ] 像素游戏风格 UI (feature/pixel-ui 分支)
  - 调用 brainstorming 技能设计方向
  - 调用 frontend-design 技能实现
  - 不影响 main 生产环境

### 低优先级

- [ ] app.js 模块化拆分
  - 当前 app.js 接近 1100 行
  - 考虑拆分为多个 JS 文件（但保持无构建步骤）

- [ ] 题库管理后台
  - 增删改查题目
  - 需要 admin token 认证
