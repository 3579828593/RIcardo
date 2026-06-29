# 架构决策记录 (ADR)

> 记录关键架构决策的背景、理由和替代方案，避免重复讨论。

## ADR-001: Vue 3 CDN 而非 SPA 构建工具

**日期**: 2026-06-28
**状态**: 已采纳

**背景**: 项目部署在 PythonAnywhere 免费层，不支持 Node.js 运行时，无法在服务端执行构建步骤。

**决策**: 使用 Vue 3 CDN 引入，无 webpack/vite 构建步骤。前端代码为单个 `app.js` 文件。

**替代方案**:
- React + Vite: 需要 Node.js 构建，PythonAnywhere 不支持
- 原生 JS: 开发效率低，状态管理复杂
- Vue SFC + vue-cli: 同样需要构建步骤

**后果**: 
- 正面：部署简单，只需上传静态文件
- 负面：无 SFC 组件化，app.js 可能膨胀；无 TypeScript 类型检查

---

## ADR-002: Session ID 数据隔离而非用户登录

**日期**: 2026-06-28
**状态**: 已采纳

**背景**: 刷题系统需要数据隔离（不同用户不共享答题记录），但实现完整用户登录系统成本过高。

**决策**: 前端生成随机 Session ID 存入 localStorage，每次 API 请求通过 `X-Session-Id` header 传递，后端按 session_id 过滤数据。

**替代方案**:
- 用户注册+登录: 成本高，PythonAnywhere 免费层不适合
- IP 地址隔离: 不可靠（NAT、代理、移动网络 IP 变化）
- Cookie + 服务端 Session: 需要服务端 Session 存储，增加复杂度

**后果**:
- 正面：零成本实现隔离，用户无感知
- 负面：换设备/清缓存后数据丢失；无法跨设备同步

---

## ADR-003: SW StaleWhileRevalidate 而非 CacheFirst

**日期**: 2026-06-28
**状态**: 已采纳

**背景**: 原方案用 CacheFirst 缓存 app.js，导致用户拿到旧版本 JS（缺少新变量），Vue 挂载失败白屏。

**决策**: 静态资源改用 StaleWhileRevalidate——先返回缓存快速加载，同时后台拉取最新版本更新缓存。SW 版本号每次前端变更必须升级。

**替代方案**:
- NetworkFirst: 首次访问慢，PythonAnywhere 冷启动加剧
- CacheFirst + 版本号自动跳转: 复杂，不可靠
- 不缓存 app.js: 每次访问都慢

**后果**:
- 正面：首次访问快，后续访问也能拿到最新版
- 负面：首次加载旧版本（但立即后台更新，下次访问即为新版）

---

## ADR-004: 单题流模式 (cursor + doneSet)

**日期**: 2026-06-29
**状态**: 已采纳

**背景**: 用户反馈"刷题回溯继续错题结构乱"——继续做题按页数回溯、切换 Tab 丢失位置、已做未做混淆。参考粉笔/Anki/Quizlet 设计。

**决策**: 默认单题流模式。`cursor` 全局游标定位当前题，`doneSet` 记录已做题号，`nextQuestion` 自动跳过已做。进度基于 `singleDoneCount / allQuestions.length`。

**替代方案**:
- 纯列表翻页: 体验差，已做未做混淆
- 服务端记录进度: 增加后端复杂度
- Anki SRS 算法: 过度设计，当前只需简单顺序刷题

**后果**:
- 正面：聚焦单题体验，进度清晰
- 负面：doneSet 纯客户端，换设备不同步

---

## ADR-005: Files API 部署而非控制台命令

**日期**: 2026-06-29
**状态**: 已采纳

**背景**: PythonAnywhere 控制台 API 需要浏览器先加载控制台页面才能使用（412 错误），自动化部署不可靠。

**决策**: 使用 Files API (multipart/form-data) 直接上传文件到远程路径，然后 reload Web 应用。无需控制台。

**替代方案**:
- 控制台 API: 需浏览器先加载，不可靠
- Git pull on server: 需要控制台执行 git pull
- GitHub Actions: PythonAnywhere 免费层不支持 webhook

**后果**:
- 正面：部署可靠，无需人工干预
- 负面：需要维护上传文件列表（已解决：部署脚本包含 sw.js）

---

## ADR-006: SDD 工作流替代 HTML 看板

**日期**: 2026-06-29
**状态**: 已采纳

**背景**: 原方案用 900+ 行 HTML 看板作为 AI 上下文投喂工具，存在信噪比低、不可版本化、加剧上下文腐败、无法按需加载等问题。

**决策**: 采用 Spec-Driven Development (SDD) 体系：CONSTITUTION.md (项目宪法) + SPEC.md (功能规格) + REVIEW.md (审查清单) + memory-bank/ (YAML 状态快照) + tasks.md (任务清单)。

**替代方案**:
- 继续用 HTML 看板: 信噪比低，维护成本高
- 纯 Markdown 看板: 比 HTML 好，但缺少结构化状态管理
- 混合方案 (Markdown + HTML): 维护两套文件，成本高

**后果**:
- 正面：AI 按需加载、可 git 追踪、信噪比高、跨会话接力
- 负面：需要学习 SDD 约定（但长期收益远大于学习成本）
