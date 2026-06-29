# CONSTITUTION.md — 项目宪法

> 不可违反的架构约束和代码规范。AI 和人都必须遵守。

## 技术栈

| 层 | 技术 | 版本 | 约束 |
|----|------|------|------|
| 后端 | Python + Flask | 3.10 / 3.0.3 | 不使用 ORM，直接 sqlite3 |
| 前端 | Vue 3 (CDN) | 3.x | 不引入构建步骤，不引入 Node.js |
| 数据库 | SQLite | 单文件 | 不使用 PostgreSQL/MySQL |
| 部署 | PythonAnywhere | 免费层 | 不使用 Docker 部署到生产 |
| 测试 | pytest | 9.x | 每次提交前必须全部通过 |

## 架构约束

### 不可违反

1. **无构建步骤**：前端不使用 webpack/vite/rollup，Vue 通过 CDN 引入
2. **单文件前端**：`app.js` 是唯一的 JS 应用文件，不超过 1200 行
3. **SQLite 单文件**：不引入其他数据库，迁移用 ALTER TABLE + 重建表
4. **Session ID 隔离**：所有数据操作必须带 session_id，不共享全局数据
5. **SW 版本联动**：任何前端文件变更，必须升级 `sw.js` 的 `CACHE_VERSION`

### 数据流

```
用户操作 → app.js (Vue) → apiFetch (带 X-Session-Id) → Flask 路由 → database.py (session_id 过滤) → SQLite
```

### 状态管理

- `cursor` (ref): 全局游标，当前题目位置
- `doneSet` (ref Set): 已做题号集合，持久化到 localStorage
- `singleMode` (ref bool): 默认 true，单题流模式
- `allQuestions` (ref []): 当前筛选集，单题模式用
- `reviewQueue` (ref []): Anki 复习队列，独立副本

## 代码风格

### JavaScript

- 用 `const` 声明函数，用 `ref()` 声明响应式状态
- 数组赋值用展开拷贝 `[...arr]`，禁止共享引用
- `computed` 属性必须处理空值边界（`if (!arr.length) return 0`）
- `watch` 自动保存状态到 localStorage

### Python

- Flask 路由函数以 `api_` 开头
- 数据库方法接受 `session_id` 参数
- 迁移逻辑：`_pre_migrate` (ADD COLUMN) → `executescript` → `_post_migrate` (rebuild table)
- 所有 API 返回 JSON，错误用 `{"error": "msg"}` + HTTP 状态码

### CSS

- 使用 CSS 变量（`:root` 定义，`[data-theme="dark"]` 覆盖）
- 像素风格设计：`border-radius: 0`、硬阴影 `box-shadow: 4px 4px 0`
- 移动优先：`max-width: 760px` 居中

## 测试要求

- 每个修复必须有对应测试
- 测试文件：`backend/tests/test_api.py`、`test_regression.py`、`test_frontend.py`
- 运行命令：`python -m pytest backend/tests/ -v --tb=short`
- 当前基线：35 passed, 8 subtests passed

## 部署检查清单

- [ ] 回归测试全部通过
- [ ] SW 版本号已升级（如有前端变更）
- [ ] 部署文件清单包含 sw.js
- [ ] 线上文件存在性验证
- [ ] 线上 API 功能验证
- [ ] 边界条件代码审查（溢出/空值/引用）
- [ ] 多会话数据隔离验证

## 禁止事项

- 禁止引入 npm/yarn 依赖
- 禁止使用 TypeScript（项目无构建步骤）
- 禁止使用 ORM（直接 sqlite3）
- 禁止在 app.js 中硬编码后端逻辑
- 禁止在 SW 缓存策略中使用 CacheFirst 缓存 app.js（会导致旧版本锁死）
- 禁止在 Vue mount 前依赖 #app 子元素（Vue 3 mount 不清空子元素）
