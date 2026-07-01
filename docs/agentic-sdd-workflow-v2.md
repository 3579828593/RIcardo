# Agentic SDD 施工级工作流 v2.0

> 2026-07-02 · 基于 Agentic SDD 终局蓝图 + 6 类补充内容 · 可直接执行

---

## 0. 核心判断

**P0 安全问题已全部修复（commit 5c74ab6）。** 项目当前不存在未修复的 Critical 级安全问题。

下一步不是继续堆功能，而是把项目升级为"Agent 可理解、可验证、可接力、可自动门禁"的工程系统。

---

## 1. 当前状态（2026-07-02 真实快照）

| 维度 | 状态 | 数据 |
|------|------|------|
| 安全 | P0 全部修复 | 6 项 Critical/Important 已修复 |
| 测试 | 151 项通过 | 11 个测试文件 + 1 个 E2E |
| 文档 | 7 层事实源已建 | AGENTS/CONSTITUTION/API/ARCHITECTURE/SECURITY/TEST_STRATEGY/progress |
| 工作流 | SDD + 路由 + 门禁 | routing.md + quality_gate.py + pyproject.toml |
| 架构债务 | 3 项 P0 + 5 项 P1 | 双身份/胖控制器/过载/判分重复/权限不一致 |
| 部署 | PythonAnywhere 在线 | v12 SW · 351 题 · Files API 智能部署 |

---

## 2. 七层事实源（已全部建立）

| 层级 | 文件 | 状态 | 职责 |
|------|------|------|------|
| 入口层 | `AGENTS.md` | 已有 | AI 进入项目的入口目录 |
| 宪法层 | `.spec/CONSTITUTION.md` | 已有 | 不可违反的技术约束 |
| 架构层 | `docs/ARCHITECTURE.md` | **新建** | 模块图、数据流、部署图、债务清单 |
| API 层 | `docs/API.md` | **新建** | 32 个端点统一参考 |
| 安全层 | `docs/SECURITY.md` | **新建** | OWASP 分类安全清单 |
| 测试层 | `docs/TEST_STRATEGY.md` | **新建** | 测试矩阵、覆盖率、权限回归 |
| 状态层 | `progress.yaml + tasks.md + decisions.md` | **已更新** | 151 测试 / v12 / 1a6442e |

---

## 3. 任务依赖 DAG（施工顺序）

```
A. P0 安全修复 ✅ 已完成 (commit 5c74ab6)
   ↓
B. 权限回归测试 ✅ 已完成 (test_banks.py 151项)
   ↓
C. 安全 SPEC + REVIEW ✅ 已完成 (.spec/specs/ugc-security-hardening.md)
   ↓
D. 七层事实源文档 ✅ 已完成 (API/ARCHITECTURE/SECURITY/TEST_STRATEGY)
   ↓
E. Agent 路由表 ✅ 已完成 (.trae/routing.md)
   ↓
F. 质量门禁脚本 ✅ 已完成 (scripts/quality_gate.py + pyproject.toml)
   ↓
G. 状态同步 ✅ 已完成 (progress.yaml + tasks.md 更新)
   ↓ ──────────── 当前位置 ────────────
H. 运行质量门禁验证 ← 下一步
   ↓
I. CI/CD GitHub Actions
   ↓
J. 身份模型统一设计 (SPEC)
   ↓
K. app.py Blueprint 拆分
   ↓
L. database.py Repository 拆分
   ↓
M. 前后端判分逻辑统一
   ↓
N. 学习分析（路线图阶段 4）
```

**关键约束：不要在 H-G 完成前做 N（学习分析）。**

---

## 4. Definition of Done（每类任务完成标准）

### 4.1 后端任务

```
- [ ] 有对应 SPEC
- [ ] 有数据库迁移说明（如涉及）
- [ ] 有权限检查（_check_bank_access 或 can_read_bank）
- [ ] 有错误响应（JSON format + HTTP status code）
- [ ] 有测试用例
- [ ] pytest 全通过
- [ ] docs/API.md 已更新
- [ ] .spec/reviews/ 已填写
```

### 4.2 前端任务

```
- [ ] app.js 状态边界处理完整（空数据/加载中/错误态）
- [ ] localStorage key 兼容旧数据
- [ ] sw.js CACHE_VERSION 已升级（如前端资源变更）
- [ ] 至少有 smoke test
- [ ] 无 {{ }} 未渲染残留（Vue 插值正常）
```

### 4.3 安全任务

```
- [ ] 权限测试覆盖 anonymous/private/owner/admin
- [ ] CSRF 防护已考虑
- [ ] 输入校验已考虑
- [ ] 输出编码已考虑
- [ ] 限流已考虑
- [ ] Security Agent 已审查
```

### 4.4 部署任务

```
- [ ] quality_gate.py 通过
- [ ] pytest 全通过
- [ ] API smoke test 通过（/api/questions, /api/auth/me, /api/banks）
- [ ] progress.yaml 已更新
- [ ] 有回滚预案
```

---

## 5. Agent 输入输出协议

### Explore Agent
```
输入：用户想法 + 现有文档
输出：问题列表 / 风险列表 / 可行方案 / 推荐方案 / 不做事项
禁止：直接改代码
```

### Architect Agent
```
输入：Product SPEC + CONSTITUTION.md
输出：数据模型 / API 变更 / 权限矩阵 / 迁移方案 / 回滚方案
禁止：绕过技术约束
```

### Backend Agent
```
输入：SPEC + docs/API.md + docs/SECURITY.md
输出：修改文件列表 / 新增测试列表 / 数据迁移说明 / 风险说明
禁止：无测试提交
```

### Frontend Agent
```
输入：SPEC + 前端约束
输出：app.js/index.html/sw.js 变更 / SW 版本号
禁止：忘记升级 SW CACHE_VERSION
```

### Test Agent
```
输入：SPEC + 实现diff
输出：覆盖矩阵 / 新增测试 / 未覆盖风险 / pytest 结果
禁止：只测 happy path
```

### Security Agent
```
输入：代码 + docs/SECURITY.md
输出：安全审查报告（Critical/Important/Minor）/ 是否允许合并
禁止：只看新增代码
```

### Review Agent
```
输入：diff + 测试结果
输出：REVIEW.md / 必须修复项 / 建议改进项
禁止：直接修代码
```

### DevOps Agent
```
输入：部署脚本 + 环境变量
输出：部署报告 / 线上验证结果 / 回滚预案
禁止：无回滚预案部署
```

### Memory Agent
```
输入：最终结果
输出：progress.yaml 更新 / tasks.md 更新 / decisions.md 更新
禁止：记录未经验证的状态
```

---

## 6. 风险登记表

| 编号 | 风险 | 等级 | 状态 | 处理方案 |
|------|------|------|------|----------|
| R-1 | 私有题库通过 legacy API 泄露 | Critical | **已修复** | _check_bank_access 全覆盖 |
| R-2 | flagged 不入库导致审核失效 | High | **已修复** | INSERT 添加 flagged 字段 |
| R-3 | answer 字段未 sanitize | Medium | **已修复** | sanitize_question 包含 answer |
| R-4 | subscribe 未检查 status | Medium | **已修复** | 增加 status='active' 检查 |
| R-5 | 登录限流覆盖成功登录 | Medium | **已修复** | 成功登录不增加计数 |
| R-6 | 双身份模型导致代码分支爆炸 | High | 待处理 | 统一为 user_id 模型 |
| R-7 | app.py 胖控制器 781 行 | Medium | 待处理 | Blueprint 拆分 |
| R-8 | database.py 过载 884 行 | Medium | 待处理 | Repository 模式 |
| R-9 | 前后端判分逻辑重复 | Medium | 待处理 | 抽取 grading.py |
| R-10 | progress.yaml 过期 | Medium | **已修复** | 同步到 151 测试/v12 |
| R-11 | CI/CD 缺失 | Medium | 待处理 | GitHub Actions |
| R-12 | CSP 允许 unsafe-eval | Low | 已知取舍 | Vue CDN 需要 |

---

## 7. 质量门禁规则

### 7.1 自动检查（quality_gate.py）

| 检查项 | 规则 | 阻断级别 |
|--------|------|----------|
| SW 版本号 | sw.js 必须有 CACHE_VERSION 且格式为 vX | 阻断 |
| 静默吞异常 | 禁止 `except: pass` | 阻断 |
| pytest | 全部测试通过 | 阻断 |
| 部署清单 | SKILL.md 必须包含 sw.js | 阻断 |
| progress 文件 | progress.yaml 必须存在 | 阻断 |
| 路由权限 | /api/ 路由须有权限校验或属公开端点 | 警告 |

### 7.2 人工检查（REVIEW 清单）

```
- [ ] 权限测试覆盖 anonymous/owner/admin/private/public
- [ ] 每个新 API 端点有对应的 docs/API.md 条目
- [ ] 数据库变更有迁移前后校验
- [ ] 前端变更有 SW 版本号升级
- [ ] 无硬编码密码或 token
```

---

## 8. 标准开发流程（10 步闭环）

```
1. Intent          用户意图 / 产品目标
2. Context         AGENTS.md → progress.yaml → tasks.md → SPEC → docs
3. Spec            写清楚目标、非目标、API、数据模型、边界、验收
4. Plan            拆成 1-3 文件级微任务
5. Implement       每个任务小步提交
6. Test            单元 + 权限 + 回归 + E2E smoke
7. Review          REVIEW.md 清单 + 只读代码审查
8. Gate            quality_gate.py + pytest + coverage
9. Deploy          部署 + 线上 smoke test + 回滚预案
10. Memory         更新 progress.yaml + tasks.md + decisions.md
```

---

## 9. 下一步执行清单

### 立即执行（今天）

```
[ ] 运行 quality_gate.py 验证门禁可用
[ ] git add 所有新建文件并提交
[ ] git push 到 GitHub
```

### 第 2 轮：CI/CD（1-2 天）

```
[ ] 创建 .github/workflows/test.yml
[ ] push 时自动运行 pytest
[ ] PR 模板强制填写 SPEC/REVIEW
```

### 第 3 轮：身份模型统一（1 周）

```
[ ] 写 SPEC: identity-unification.md
[ ] 设计迁移方案（匿名用户 → 临时 user 记录）
[ ] 设计回滚方案
[ ] TDD 实现 + 全量测试
```

### 第 4 轮：模块拆分（2 周）

```
[ ] app.py → routes/ Blueprint（保持行为不变）
[ ] database.py → repositories/ 模式
[ ] 抽取 grading.py 判分逻辑
[ ] CSS 外置为独立文件
```

### 第 5 轮：学习分析（路线图阶段 4）

```
[ ] 知识点掌握度雷达图
[ ] 错题趋势分析
[ ] 复习计划推荐
[ ] 周/月学习报告
```

---

## 10. 新建文件清单

| 文件路径 | 类型 | 说明 |
|----------|------|------|
| `docs/API.md` | 事实源 | 32 个 API 端点完整参考 |
| `docs/ARCHITECTURE.md` | 事实源 | 系统架构图、模块图、数据流 |
| `docs/SECURITY.md` | 事实源 | OWASP 分类安全清单 |
| `docs/TEST_STRATEGY.md` | 事实源 | 测试分层、覆盖率、权限矩阵 |
| `.trae/routing.md` | 路由表 | 7 类触发器 + 9 个 Agent 角色 |
| `scripts/quality_gate.py` | 门禁脚本 | 6 项自动检查 |
| `pyproject.toml` | 配置 | pytest + coverage 配置 |
| `.spec/specs/ugc-security-hardening.md` | SPEC | P0 安全修复记录 |
| `.spec/reviews/ugc-security-hardening.md` | REVIEW | 安全审查清单 |
| `memory-bank/progress.yaml` | 状态 | 已同步到 151 测试/v12 |
| `tasks.md` | 任务 | 已添加工程化待办 |
