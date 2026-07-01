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
- [x] 阶段1: SW 离线答题 + Playwright E2E (commit: 8681370, 2026-06-29)
- [x] 阶段2 核心: CSV 批量导入 + 管理界面 (commit: 955cde3, 2026-06-29)
- [x] UGC Step 0: questions 表重建 + question_banks 表 (commit: 5c74ab6, 2026-07-02)
- [x] UGC Step 1: 用户系统 pbkdf2 + Flask session + CSRF + 限流 (commit: 5c74ab6, 2026-07-02)
- [x] UGC Step 2: 私有题库 CRUD + CSV 导入 + 进度隔离 (commit: 5c74ab6, 2026-07-02)
- [x] UGC Step 3: 公开题库 + 订阅 + 举报 (commit: 5c74ab6, 2026-07-02)
- [x] UGC 安全加固: P0 安全问题全部修复 (commit: 5c74ab6, 2026-07-02)

## 待办任务

> 路线图详见 docs/roadmap-2026-summer.md

### 阶段 5：工程化与架构优化

- [ ] 补 docs/API.md
- [ ] 补 docs/ARCHITECTURE.md
- [ ] 补 docs/SECURITY.md
- [ ] 补 docs/TEST_STRATEGY.md
- [ ] 建 quality_gate.py
- [ ] 建 .trae/routing.md
- [ ] 建 pyproject.toml + pytest-cov
- [ ] 统一身份模型设计
- [ ] app.py Blueprint 拆分
- [ ] database.py Repository 拆分

### 阶段 1：快而稳（暑假第 1-2 周）

- [ ] UptimeRobot 定时 ping 保活（需用户注册配置）
- [x] Service Worker 离线答题（离线可答题，联网同步）
- [x] 骨架屏 + 渐进加载优化
- [ ] Lighthouse 性能评分 ≥ 80
- [x] Playwright E2E 测试框架搭建（8 项测试覆盖核心路径）

### 阶段 2：自己能加题（暑假第 3-4 周）

- [x] CSV 题目导入（提供模板 + 格式校验 + 错误报告）
- [ ] Markdown 题目导入
- [x] Admin Token 认证（后端 require_admin 装饰器）
- [x] 题目管理界面（查看/删除/筛选，编辑待后续）
- [ ] CI/CD 自动部署（git push → 自动上线）

### 阶段 3：记住我是谁（暑假第 5-6 周）

- [ ] 用户注册/登录（邮箱 or 学号，JWT）
- [ ] session_id → user_id 数据迁移
- [ ] 跨设备数据同步
- [ ] 班级/学习群组 + 邀请码
- [ ] 班级排行榜

### 阶段 4：告诉我该学什么（暑假第 7-8 周）

- [ ] 知识点掌握度雷达图
- [ ] 错题趋势分析（时间轴）
- [ ] 复习计划推荐
- [ ] 周/月学习报告
- [ ] 数据导出 CSV/Excel

### 支线：游戏化（秋季课余构思）

- [ ] L2 机制级：连击/血条/关卡
- [ ] L3 结构级：技能树/地图/Boss战
- [ ] 像素风 RPG 视觉设计
