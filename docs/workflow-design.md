# SDD 工作流设计文档

> 从 HTML 看板到规格驱动开发（Spec-Driven Development）的完整工作流设计

## 1. 问题诊断：HTML 看板的 6 个缺陷

| # | 缺陷 | 影响 | 根因 |
|---|------|------|------|
| 1 | 展示导向非机器可读 | AI 解析效率低 | HTML 是呈现层标记，不是状态描述语言 |
| 2 | 加剧上下文腐败 | 关键信号被淹没 | 900 行 HTML 中 CSS/标签占比 60%+，信噪比极低 |
| 3 | 无法按需加载 | 全量加载浪费 token | 单一大文件，无法按模块拆分加载 |
| 4 | 不可有效版本化 | git diff 噪声大 | HTML 格式变更与内容变更混在一起 |
| 5 | 多 Agent 共享污染 | 子 Agent 互相干扰 | 臃肿 HTML 成为所有 Agent 的共享上下文 |
| 6 | 维护成本高 | 纯展示开销 | 每次更新需手动编辑 HTML 表格/badge/section |

## 2. SDD 体系架构

```
项目根目录/
├── AGENTS.md                    # AI 入口文件（入职培训）
├── .spec/
│   ├── CONSTITUTION.md          # 项目宪法（不可违反的约束）
│   ├── specs/                   # 功能规格目录
│   │   └── <feature>.md         # 具体功能 SPEC（按需创建）
│   └── reviews/                 # 审查清单目录
│       └── <feature>.md         # 具体功能 REVIEW（按需创建）
├── memory-bank/
│   ├── progress.yaml            # YAML 进度快照（跨会话接力）
│   └── decisions.md             # 架构决策记录 (ADR)
├── tasks.md                     # 任务清单（状态机）
└── docs/
    └── workflow-design.md       # 本文档
```

### 文件职责

| 文件 | 职责 | 何时读取 | 格式 |
|------|------|----------|------|
| `AGENTS.md` | 项目入口，技术栈，目录结构，开发规则 | 每次新会话 | Markdown |
| `.spec/CONSTITUTION.md` | 架构约束，代码风格，禁止事项 | 需要了解约束时 | Markdown |
| `.spec/specs/<feature>.md` | 功能接口设计，边界条件，验收标准 | 开发对应功能时 | Markdown |
| `.spec/reviews/<feature>.md` | AI 自检 + 人工验收 checklist | 审查对应功能时 | Markdown |
| `memory-bank/progress.yaml` | 当前进度，成就，决策，阻塞，已知问题 | 新会话开始时 | YAML |
| `memory-bank/decisions.md` | 架构决策背景，理由，替代方案 | 需要理解决策时 | Markdown |
| `tasks.md` | 任务清单，状态机，优先级 | 需要查看任务时 | Markdown |

### 三层文档体系

```
CONSTITUTION.md  →  "按什么规矩干"（不可违反）
      ↓
SPEC.md          →  "具体干什么"（接口、边界、验收）
      ↓
REVIEW.md        →  "干完怎么检查"（自检 + 验收）
```

## 3. 标准开发循环（7 步闭环）

```
┌─────────────────────────────────────────────────────────┐
│                    SDD 开发循环                           │
│                                                          │
│  1. 读取上下文                                           │
│     AGENTS.md → progress.yaml → tasks.md                │
│                    ↓                                     │
│  2. 编写/更新 SPEC                                       │
│     .spec/specs/<feature>.md                             │
│     （接口设计、边界条件、验收标准）                      │
│                    ↓                                     │
│  3. 实现                                                 │
│     按 SPEC 写代码，微任务闭环                            │
│     （1-3 文件、15-30 分钟、单一目的）                    │
│                    ↓                                     │
│  4. 测试                                                 │
│     python -m pytest backend/tests/ -v                   │
│     必须全部通过                                          │
│                    ↓                                     │
│  5. 自检 REVIEW                                          │
│     .spec/reviews/<feature>.md                           │
│     （边界条件、SW版本、引用拷贝、进度溢出）              │
│                    ↓                                     │
│  6. 提交 + 部署                                          │
│     git commit → git push → Files API 部署               │
│     （包含 sw.js！）                                     │
│                    ↓                                     │
│  7. 更新进度                                             │
│     memory-bank/progress.yaml                            │
│     tasks.md 标记完成                                    │
│                    ↓                                     │
│  回到步骤 1                                              │
└─────────────────────────────────────────────────────────┘
```

## 4. 跨会话接力协议

### 新会话开始时

AI 读取顺序（按需加载，不全量读取）：

```
1. AGENTS.md          → 了解项目背景和规则
2. progress.yaml      → 了解当前进度和状态
3. tasks.md           → 了解待办任务
4. (按需) CONSTITUTION.md → 了解架构约束
5. (按需) decisions.md → 了解决策背景
6. (按需) specs/*.md  → 了解功能规格
```

### 会话结束时

AI 必须更新：

```
1. progress.yaml      → 更新 current_state、achievements、known_issues
2. tasks.md           → 标记完成任务，添加新发现的问题
3. (如有) decisions.md → 记录新架构决策
```

### YAML 快照格式

```yaml
current_state:
  phase: Phase X
  status: 描述
  last_commit: hash
  sw_version: vX

achievements:
  - phase: Phase X
    name: 功能名
    commit: hash
    status: done

blockers: []

next_session_rules:
  - 规则1
  - 规则2
```

## 5. 任务编排矩阵

| 任务类型 | 技能 | Agent | 验证方式 |
|----------|------|-------|----------|
| 需求分析 | brainstorming | Explore | 用户确认 |
| 架构设计 | brainstorming → writing-plans | Plan | 用户确认 spec |
| 前端开发 | frontend-design | general_purpose_task | pytest + 线上验证 |
| 后端开发 | test-driven-development | general_purpose_task | pytest + API 验证 |
| 代码审查 | — | Explore (read-only) | REVIEW.md checklist |
| 部署 | — | 直接执行 | 线上功能验证 |
| Bug 修复 | test-driven-development | general_purpose_task | pytest + 回归 |

### 何时使用子 Agent

- **独立子任务**：拆分为子 Agent，每个独享干净上下文
- **只读分析**：用 Explore Agent，避免污染主上下文
- **并行研究**：多个 Explore Agent 并行（最多 3 个）
- **大量代码变更**：用 general_purpose_task Agent，返回摘要

### 子 Agent 交接协议

```
主 Agent → 子 Agent: 传递最小自包含上下文（不依赖对话历史）
子 Agent → 主 Agent: 返回结构化摘要（成果 + 文件列表 + 测试结果）
主 Agent → progress.yaml: 记录子 Agent 产出
```

## 6. SPEC.md 模板

```markdown
# SPEC: <功能名>

## 目标
一句话描述要实现什么。

## 接口设计
- API: GET/POST /api/xxx
- 参数: ...
- 返回: ...

## 边界条件
- 空值处理: ...
- 溢出处理: ...
- 并发处理: ...

## 验收标准
- [ ] 条件1
- [ ] 条件2
- [ ] 测试通过

## 涉及文件
- backend/xxx.py
- backend/static/js/app.js
- backend/templates/index.html
```

## 7. REVIEW.md 模板

```markdown
# REVIEW: <功能名>

## AI 自检清单
- [ ] 边界条件: 空值/溢出/引用共享
- [ ] SW 版本: 前端变更是否升级 CACHE_VERSION
- [ ] 数据隔离: 是否带 session_id
- [ ] 测试覆盖: 是否有对应测试
- [ ] 进度计算: 是否防溢出
- [ ] 数组拷贝: 是否用 [...arr]

## 线上验证
- [ ] API 功能正常
- [ ] 数据隔离有效
- [ ] SW 版本正确

## 回归测试
- [ ] 35/35 passed
```

## 8. 对比：旧 vs 新

| 维度 | HTML 看板 | SDD 体系 |
|------|-----------|----------|
| AI 解析效率 | 低（HTML 标签噪声） | 高（Markdown/YAML 结构化） |
| 上下文成本 | 高（900 行全量加载） | 低（按需加载，单文件 50-100 行） |
| 版本追踪 | 差（diff 噪声大） | 好（Markdown diff 清晰） |
| 跨会话接力 | 手动复制 HTML | 自动读 YAML 快照 |
| 多 Agent 协同 | 差（共享污染） | 好（独立上下文 + 结构化交接） |
| 维护成本 | 高（手动编辑 HTML） | 低（更新 YAML 字段） |
| 可扩展性 | 差（HTML 膨胀） | 好（按需创建 spec/review） |

## 9. 迁移路径

从 HTML 看板到 SDD 的迁移已完成：

1. ~~HTML 看板~~ → `AGENTS.md` + `CONSTITUTION.md`（规则层）
2. ~~HTML 进度表格~~ → `progress.yaml`（状态层）
3. ~~HTML 错因总结~~ → `decisions.md`（决策层）
4. ~~HTML 检查清单~~ → `CONSTITUTION.md` 部署检查清单（约束层）
5. ~~HTML 路线图~~ → `tasks.md`（任务层）

旧的 `quiz-dev-workflow.html` 保留作为历史参考，不再更新。新的工作流全部基于 SDD 文件体系。
