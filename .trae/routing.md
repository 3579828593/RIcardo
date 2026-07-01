# Agent Routing Rules

## 安全优先触发器
当任务涉及 auth/session/csrf/permission/bank visibility/import/report 时：
- 必须先读 docs/SECURITY.md
- 必须新增或更新权限测试
- Security Agent 必须参与审查
- 禁止绕过 _check_bank_access

## 前端触发器
当修改 app.js/index.html/sw.js 时：
- 必须升级 sw.js 中 CACHE_VERSION
- 必须跑前端 smoke test
- 必须检查 localStorage key 兼容性
- Frontend Agent 负责执行

## 数据库触发器
当修改 database.py 的 schema/migration 时：
- 必须写迁移前后数据量校验
- 必须有 rollback plan
- 禁止 except: pass 静默吞异常
- Backend Agent + Test Agent 联合执行

## API 变更触发器
当修改 app.py 路由时：
- 必须更新 docs/API.md
- 必须更新对应测试
- 必须检查权限校验完整性

## 部署触发器
部署前必须通过：
- pytest 全通过
- quality_gate.py 通过
- API smoke test 通过
- progress.yaml 已更新

## 重构触发器
当进行架构重构时：
- 必须保持行为不变（现有测试全通过）
- 每次只拆一个模块
- 拆完后跑全量测试验证

## Agent 角色表
| Agent | 职责 | 输入 | 输出 | 禁止 |
|-------|------|------|------|------|
| Explore | 需求澄清/风险发现 | 用户想法/文档 | 问题清单/风险清单 | 直接改代码 |
| Architect | 数据模型/API/权限 | SPEC/宪法 | 架构方案/ADR | 绕过技术约束 |
| Backend | Flask/SQLite/认证 | SPEC/API文档 | 后端代码+测试 | 无测试提交 |
| Frontend | Vue/UI/PWA | SPEC/前端约束 | app.js/index.html | 忘记升级SW |
| Test | 单元/集成/E2E | SPEC/diff | 测试用例/报告 | 只测happy path |
| Security | 权限/CSRF/XSS | 代码/SECURITY.md | 安全审查报告 | 只看新增代码 |
| Review | 只读审查 | diff/测试结果 | REVIEW.md | 直接修代码 |
| DevOps | CI/CD/部署/回滚 | 部署脚本 | 部署报告 | 无回滚部署 |
| Memory | 更新状态/ADR | 最终结果 | progress/tasks更新 | 记录未验证状态 |

## 事实源优先级
AI 读取项目时按此顺序：
1. AGENTS.md (入口)
2. progress.yaml (当前状态)
3. tasks.md (待办)
4. CONSTITUTION.md (约束)
5. 当前相关 SPEC
6. 当前相关 REVIEW
7. docs/API.md / SECURITY.md / ARCHITECTURE.md / TEST_STRATEGY.md
8. 代码
9. 综合评估/历史文档
