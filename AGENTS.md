# AGENTS.md — AI 代理入职培训文件

> 本文件是 AI 代理的项目入口文档。每次新会话开始时，AI 应先读此文件，再按需加载其他文件。

## 项目概述

**期末冲刺刷题系统**：Flask + Vue 3 + SQLite 单文件数据库的 Web 刷题应用。
351 道题（天气分析 268 + 大学英语 83），部署在 PythonAnywhere 免费层。

## 技术栈约束

- **后端**: Python 3.10 / Flask 3.0.3 / SQLite
- **前端**: Vue 3 (CDN, 无构建步骤) / 原生 CSS / Service Worker PWA
- **部署**: PythonAnywhere (免费层, 100 CPU秒/天, 需3个月续期)
- **测试**: pytest (35 项回归测试)
- **禁止**: 引入构建工具(webpack/vite)、引入 Node.js 依赖、使用 ORM

## 目录结构

```
backend/
  app.py              # Flask 路由 + API 端点
  database.py         # SQLite 数据层 (含迁移逻辑)
  lite.py             # 轻量版 SSR (无 Vue, ES5)
  config.py           # 配置
  static/js/app.js    # Vue 3 应用主逻辑 (单文件)
  static/sw.js        # Service Worker (当前 v5)
  templates/index.html # 主页面模板
  tests/              # pytest 测试套件
scripts/pa_deploy.py  # PythonAnywhere 部署脚本
```

## 开发规则

1. **每次前端变更必须升级 SW 版本号** (`sw.js` 中 `CACHE_VERSION`)
2. **部署清单必须包含 sw.js** (Files API 上传)
3. **所有 API 使用 session_id 隔离** (`X-Session-Id` header)
4. **测试通过才能提交**: `python -m pytest backend/tests/ -v`
5. **提交前做边界条件审查**: 溢出、空值、引用共享
6. **数组赋值用展开拷贝**: `[...arr]` 而非直接引用
7. **单次提交只做一件事**: 遵循 Conventional Commits

## 部署流程

```bash
# 1. 测试
python -m pytest backend/tests/ -v

# 2. 提交
git add <files>
git commit -m "feat/fix: 描述"
git push origin main

# 3. 部署 (Files API, 无需控制台)
python scripts/pa_deploy.py update
# 或使用 Files API 脚本上传变更文件

# 4. 线上验证
# 检查 SW 版本、API 功能、数据隔离
```

## 按需加载

以下文件按需读取，不要一次性全部加载：

| 文件 | 何时加载 |
|------|----------|
| `.spec/CONSTITUTION.md` | 需要了解架构约束、代码风格时 |
| `memory-bank/progress.yaml` | 新会话开始时，了解当前进度 |
| `memory-bank/decisions.md` | 需要了解架构决策背景时 |
| `tasks.md` | 需要查看任务清单时 |
| `.spec/specs/*.md` | 开发对应功能时 |
| `.spec/reviews/*.md` | 审查对应功能时 |

## 已知限制

- PythonAnywhere 免费层冷启动 5-10 秒
- doneSet 纯客户端 localStorage，换设备不同步（设计限制）
- 无用户登录系统，靠 session_id 隔离
- SW StaleWhileRevalidate 策略：先返回缓存，后台更新
