# API 参考文档

> 期末冲刺刷题系统 — 完整 API 参考
>
| 项目 | 说明 |
|------|------|
| 基础技术栈 | Flask 3.0 + SQLite (WAL 模式) |
| 部署平台 | PythonAnywhere |
| API 前缀 | `/api/`（页面路由无前缀） |
| 内容类型 | `application/json`（除文件上传为 `multipart/form-data`） |
| 字符编码 | UTF-8 |

---

## 目录

1. [通用约定](#1-通用约定)
2. [页面路由（3）](#2-页面路由3)
3. [题目 API（5）](#3-题目-api5)
4. [答题 API（3）](#4-答题-api3)
5. [错题 / 收藏 API（3）](#5-错题--收藏-api3)
6. [认证 API（4）](#6-认证-api4)
7. [题库 API（7）](#7-题库-api7)
8. [管理 API（8）](#8-管理-api8)
9. [举报 API（1）](#9-举报-api1)
10. [错误码汇总](#10-错误码汇总)

---

## 1. 通用约定

### 1.1 身份认证与数据隔离

系统采用**双身份模型**，支持匿名和登录两种使用方式：

| 身份类型 | 标识方式 | 隔离机制 |
|----------|----------|----------|
| 匿名用户 | `X-Session-Id` 请求头 | 前端在 `localStorage` 生成唯一 ID（≥ 8 字符），每次请求携带；未携带时使用 `"anon"` |
| 登录用户 | Flask session cookie | 登录后通过 `session` cookie 识别，`session['user_id']` 标识用户 |

**Session-Id 校验规则**（`_get_session_id()`）：
- 长度范围：8 ~ 64 字符
- 允许字符：`[a-zA-Z0-9_-]`
- 不满足条件时降级为 `"anon"`，看到空数据

登录后，匿名 `session_id` 的答题/收藏/错题数据会自动迁移到 `user_id`（`db.migrate_session_data()`），迁移幂等可重复执行。

### 1.2 CSRF 防护

| 请求类型 | CSRF 要求 |
|----------|-----------|
| GET 请求 | 不需要 |
| 非 GET 请求（未登录用户） | 不需要（匿名用户豁免） |
| 非 GET 请求（登录用户） | **必须**携带 `X-CSRF-Token` 请求头，值与 `session['csrf_token']` 一致 |
| `/api/auth/` 路由 | 全部豁免（登录/注册需建立新 session） |

CSRF token 在注册或登录成功后由服务端生成（`secrets.token_hex(16)`）并返回给客户端，客户端需在后续写操作中携带。

### 1.3 请求头汇总

| 请求头 | 必要性 | 说明 |
|--------|--------|------|
| `X-Session-Id` | 匿名用户必需 | 匿名数据隔离标识 |
| `X-CSRF-Token` | 登录用户写操作必需 | CSRF 防护令牌 |
| `X-Admin-Token` | 管理员 API 必需 | 管理员令牌，值需与 `QUIZ_ADMIN_TOKEN` 环境变量一致 |
| `Content-Type` | POST/PUT 必需 | `application/json` 或 `multipart/form-data` |

### 1.4 分页约定

所有分页接口使用统一的查询参数：

| 参数 | 类型 | 默认值 | 最大值 | 说明 |
|------|------|--------|--------|------|
| `page` | int | 1 | — | 页码，必须为正整数 |
| `page_size` | int | 20 | 100 | 每页条数，必须为正整数 |

非法值（负数、零、非数字）返回 `400 Bad Request`。

### 1.5 响应格式

所有 API 返回 JSON（除页面路由和文件下载），统一结构：

```json
// 列表响应
{
  "items": [...],
  "page": 1,
  "page_size": 20,
  "total": 100
}

// 错误响应
{
  "error": "错误描述信息"
}
```

---

## 2. 页面路由（3）

### 2.1 GET `/` — 主页面

返回 Vue 3 SPA 主页面（`templates/index.html`）。

| 属性 | 说明 |
|------|------|
| 权限 | 无需认证 |
| 请求参数 | 无 |
| 响应类型 | `text/html` |

**响应**：渲染 `index.html`，包含 Vue 3 CDN 引用、应用挂载点和骨架屏。

**安全注意事项**：
- Jinja 模板分隔符已改为 `[[ ]]`，避免与 Vue `{{ }}` 插值冲突
- 页面内 Vue mustache 语法（`{{ q.stem }}`）原样保留，由浏览器端 Vue 渲染

---

### 2.2 GET `/lite` — 轻量版页面

服务端渲染的轻量页面，不依赖 Vue，兼容微信内置浏览器等受限内核。

| 属性 | 说明 |
|------|------|
| 权限 | 无需认证 |
| 请求参数 | `page`（int，默认 1） |
| 响应类型 | `text/html; charset=utf-8` |

**查询参数**：

| 参数 | 类型 | 默认 | 说明 |
|------|------|------|------|
| `page` | int | 1 | 页码，小于 1 时重置为 1 |

**响应**：
- 每页 1 题，服务端渲染完整 HTML
- 包含当前题目、页码、总页数、全站统计信息
- `Cache-Control: public, max-age=300`（允许浏览器缓存 5 分钟）

**安全注意事项**：
- HTML 内容由 `lite.py` 的 `render_lite_page()` 生成
- 题干经过 `clean_stem()` 清理答案标注

---

### 2.3 GET `/sw.js` — Service Worker

以根路径提供 Service Worker 脚本，使其 scope 覆盖整个站点。

| 属性 | 说明 |
|------|------|
| 权限 | 无需认证 |
| 请求参数 | 无 |
| 响应类型 | `application/javascript; charset=utf-8` |

**响应**：
- 返回 `static/sw.js` 文件内容
- 设置 `Service-Worker-Allowed: /` 允许根 scope 注册

**安全注意事项**：
- SW 文件物理存放于 `static/` 目录，通过此路由以 `/sw.js` 暴露
- SW 可拦截所有同源请求（离线缓存），需确保缓存策略安全

---

## 3. 题目 API（5）

### 3.1 GET `/api/questions` — 搜索题目

分页搜索题目，支持多维度筛选。

| 属性 | 说明 |
|------|------|
| 权限 | 匿名可访问；`bank_id` 非 1 时需通过 `_check_bank_access` 读权限校验 |
| 请求类型 | Query 参数 |

**查询参数**：

| 参数 | 类型 | 默认 | 说明 |
|------|------|------|------|
| `course` | string | — | 课程名精确匹配 |
| `chapter` | int | — | 章节号精确匹配 |
| `type` | string | — | 题型，支持逗号分隔多选（如 `single,multiple`） |
| `keyword` | string | — | 题干关键词模糊搜索（LIKE），通配符自动转义 |
| `knowledge` | string | — | 知识点精确匹配 |
| `bank_id` | int | — | 题库 ID；为空或 1（官方题库）时不检查权限 |
| `page` | int | 1 | 页码 |
| `page_size` | int | 20 | 每页条数（上限 100） |

**响应结构**：

```json
{
  "items": [
    {
      "id": 1,
      "original_id": null,
      "bank_id": 1,
      "course": "weather",
      "chapter": 1,
      "type": "single",
      "stem": "题干文本（已清理答案标注）",
      "options": {"A": "选项A", "B": "选项B"},
      "answer": ["A"],
      "explanation": "解析",
      "knowledge": "知识点",
      "difficulty": "medium",
      "flagged": 0,
      "created_at": "2026-01-01 00:00:00",
      "updated_at": "2026-01-01 00:00:00"
    }
  ],
  "page": 1,
  "page_size": 20,
  "total": 100
}
```

**错误码**：

| 状态码 | 场景 |
|--------|------|
| 400 | `page` 或 `page_size` 不是正整数 |
| 403 | 无权访问指定 `bank_id` 的题库 |

**安全注意事项**：
- `bank_id` 为非官方题库时，调用 `_check_bank_access(bank_id, user)` 校验读权限
- 题干经 `clean_stem()` 移除答案标注（如 `（答案）`、`答案：XXX`）
- `keyword` 参数的 `%` 和 `_` 通配符被转义，防止 LIKE 注入

---

### 3.2 GET `/api/questions/random` — 随机题目

随机获取指定数量的题目。

| 属性 | 说明 |
|------|------|
| 权限 | 匿名可访问；`bank_id` 非 1 时需通过 `_check_bank_access` 读权限校验 |

**查询参数**：

| 参数 | 类型 | 默认 | 最大 | 说明 |
|------|------|------|------|------|
| `course` | string | — | — | 课程筛选 |
| `chapter` | int | — | — | 章节筛选 |
| `type` | string | — | — | 题型筛选（支持逗号分隔） |
| `bank_id` | int | — | — | 题库 ID |
| `limit` | int | 20 | 100 | 返回数量上限 |

**响应结构**：

```json
{
  "items": [
    { "id": 42, "course": "weather", "stem": "...", ... }
  ]
}
```

**错误码**：

| 状态码 | 场景 |
|--------|------|
| 400 | `limit` 不是正整数 |
| 403 | 无权访问指定题库 |

**安全注意事项**：
- 使用 `ORDER BY RANDOM() LIMIT ?` 实现随机，参数化查询防止 SQL 注入
- `limit` 被限制在 100 以内，防止大量数据拉取

---

### 3.3 GET `/api/questions/<qid>` — 获取单题

根据题目 ID 获取单道题目详情。

| 属性 | 说明 |
|------|------|
| 权限 | 匿名可访问（无题库级别权限校验，依赖前端正确传递 `bank_id`） |

**路径参数**：

| 参数 | 类型 | 说明 |
|------|------|------|
| `qid` | int | 题目 ID |

**响应结构**：

```json
{
  "id": 1,
  "bank_id": 1,
  "course": "weather",
  "chapter": 1,
  "type": "single",
  "stem": "题干文本",
  "options": {"A": "选项A", "B": "选项B"},
  "answer": ["A"],
  "explanation": "解析",
  "knowledge": "知识点"
}
```

**错误码**：

| 状态码 | 场景 |
|--------|------|
| 404 | 题目不存在 |

**安全注意事项**：
- 注意：此端点本身不做题库权限校验，权限控制在前端和 `/api/questions` 层面
- `answer` 字段会返回正确答案，前端需在用户提交后才显示

---

### 3.4 GET `/api/chapters` — 章节列表

返回各课程实际包含的章节列表。

| 属性 | 说明 |
|------|------|
| 权限 | 匿名可访问 |

**查询参数**：

| 参数 | 类型 | 默认 | 说明 |
|------|------|------|------|
| `course` | string | — | 指定课程时返回该课程章节；不指定时返回所有课程 |

**响应结构（指定 course）**：

```json
{
  "course": "weather",
  "chapters": [1, 2, 3, 5, 8]
}
```

**响应结构（不指定 course）**：

```json
{
  "weather": [1, 2, 3, 5, 8],
  "english": [1, 2, 4]
}
```

**安全注意事项**：
- 使用 `GROUP_CONCAT(DISTINCT chapter)` 聚合查询，参数化防注入

---

### 3.5 GET `/api/admin/questions` — 管理员题目列表

> 注：此端点同时属于管理 API，因与题目查询相关在此一并说明。详见 [8.1](#81-get--post-apiadminquestions--管理员题目管理)。

管理员视角的分页搜索题目，支持创建单题（POST）。

---

## 4. 答题 API（3）

### 4.1 POST `/api/submit` — 提交答案

提交单题答案，服务端判分并记录答题数据。

| 属性 | 说明 |
|------|------|
| 权限 | 匿名/登录均可；`bank_id` 非 1 时需通过 `_check_bank_access` 读权限校验 |
| CSRF | 登录用户需要 |

**请求体（JSON）**：

```json
{
  "question_id": 1,
  "answer": "A",
  "elapsed_seconds": 15,
  "bank_id": 1
}
```

| 字段 | 类型 | 必需 | 默认 | 说明 |
|------|------|------|------|------|
| `question_id` | int | 是 | — | 题目 ID |
| `answer` | any | 否 | — | 用户答案（单选为 string，多选为 array，填空为 array） |
| `elapsed_seconds` | int | 否 | 0 | 答题用时（秒），负数会被截断为 0 |
| `bank_id` | int | 否 | 1 | 题库 ID，用于权限校验 |

**判分逻辑**（`_check_answer()`）：

| 题型 | 判分方式 |
|------|----------|
| `single` | 用户答案与正确答案均转大写后比较 |
| `multiple` | 用户答案数组与正确答案数组排序后逐元素比较 |
| `true_false` | 支持多种写法（对/错/true/false/A/B/0/1），统一归一化后比较 |
| `fill_blank` | 多空填空逐空比较，去除所有空白字符 |
| `short_answer` | 精确匹配或关键词包含 |

**响应结构**：

```json
{
  "correct": true,
  "correct_answer": ["A"],
  "explanation": "解析内容",
  "knowledge": "知识点"
}
```

**错误码**：

| 状态码 | 场景 |
|--------|------|
| 400 | 缺少 `question_id` |
| 403 | 无权访问指定题库 |
| 404 | 题目不存在 |

**安全注意事项**：
- 答题记录同时写入 `session_id` 和 `user_id`（登录时），实现双身份数据隔离
- 答对时自动清除该题的错题记录；答错时更新错题计数
- `elapsed_seconds` 负数被 `max(0, ...)` 截断

---

### 4.2 GET `/api/stats` — 获取统计数据

获取当前用户/会话的答题统计。

| 属性 | 说明 |
|------|------|
| 权限 | 匿名/登录均可，按身份隔离数据 |

**查询参数**：

| 参数 | 类型 | 默认 | 说明 |
|------|------|------|------|
| `bank_id` | int | — | 指定题库时返回该题库维度统计 |

**响应结构**：

```json
{
  "total_questions": 500,
  "answered_questions": 120,
  "answered_question_ids": [1, 2, 3, ...],
  "total_answers": 135,
  "correct_answers": 98,
  "accuracy": 0.7259,
  "mistake_count": 22,
  "favorite_count": 15,
  "type_distribution": {"single": 200, "multiple": 100, ...},
  "course_distribution": {"weather": 300, "english": 200}
}
```

**安全注意事项**：
- 登录用户按 `user_id` 查询，匿名用户按 `session_id` 查询
- `bank_id` 筛选通过 JOIN `questions` 表实现，不直接暴露其他用户数据

---

### 4.3 POST `/api/reset_stats` — 重置进度

清除当前用户/会话的答题记录和错题记录。

| 属性 | 说明 |
|------|------|
| 权限 | 匿名/登录均可 |
| CSRF | 登录用户需要 |

**请求体**：无

**响应结构**：

```json
{
  "ok": true,
  "message": "答题记录已清除"
}
```

**错误码**：

| 状态码 | 场景 |
|--------|------|
| 500 | 数据库操作失败 |

**安全注意事项**：
- 仅清除当前身份的数据（`session_id` 或 `user_id`），不影响其他用户
- 删除 `answer_records` 和 `mistakes` 表中对应记录，但不删除收藏

---

## 5. 错题 / 收藏 API（3）

### 5.1 GET `/api/mistakes` — 错题列表

获取当前用户/会话的错题列表，按错误次数和最近错误时间排序。

| 属性 | 说明 |
|------|------|
| 权限 | 匿名/登录均可，按身份隔离 |

**查询参数**：

| 参数 | 类型 | 默认 | 说明 |
|------|------|------|------|
| `page` | int | 1 | 页码 |
| `page_size` | int | 20 | 每页条数（上限 100） |

**响应结构**：

```json
{
  "items": [
    {
      "id": 1,
      "course": "weather",
      "stem": "题干",
      "options": {...},
      "answer": ["A"],
      "wrong_count": 3,
      "last_wrong_at": "2026-01-01 12:00:00"
    }
  ],
  "page": 1,
  "page_size": 20,
  "total": 22
}
```

**错误码**：

| 状态码 | 场景 |
|--------|------|
| 400 | `page` 或 `page_size` 不是正整数 |

**安全注意事项**：
- 数据隔离：登录按 `user_id`，匿名按 `session_id`

---

### 5.2 GET `/api/favorites` — 收藏列表

获取当前用户/会话的收藏题目列表。

| 属性 | 说明 |
|------|------|
| 权限 | 匿名/登录均可，按身份隔离 |

**查询参数**：

| 参数 | 类型 | 默认 | 说明 |
|------|------|------|------|
| `page` | int | 1 | 页码 |
| `page_size` | int | 20 | 每页条数（上限 100） |

**响应结构**：

```json
{
  "items": [
    {
      "id": 1,
      "course": "weather",
      "stem": "题干",
      "options": {...},
      "answer": ["A"],
      "tag": "重要",
      "fav_at": "2026-01-01 12:00:00"
    }
  ],
  "page": 1,
  "page_size": 20,
  "total": 15
}
```

**错误码**：

| 状态码 | 场景 |
|--------|------|
| 400 | 分页参数非法 |

---

### 5.3 POST / DELETE `/api/favorites/<qid>` — 收藏 / 取消收藏

切换收藏状态（POST）或删除收藏（DELETE）。

| 属性 | 说明 |
|------|------|
| 权限 | 匿名/登录均可 |
| CSRF | 登录用户需要 |

**路径参数**：

| 参数 | 类型 | 说明 |
|------|------|------|
| `qid` | int | 题目 ID |

**POST 请求体（JSON）**：

```json
{
  "tag": "自定义标签"
}
```

| 字段 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `tag` | string | 否 | 收藏标签 |

**POST 响应**（切换收藏，已收藏则取消）：

```json
{
  "favorited": true
}
```

**DELETE 响应**（幂等删除）：

```json
{
  "favorited": false,
  "removed": true
}
```

**安全注意事项**：
- POST 为切换语义：已收藏则取消，未收藏则添加
- DELETE 为幂等操作：未收藏时删除不报错，`removed` 返回 `false`
- 题库 ID 从题目记录中获取（`q.get('bank_id', 1)`）

---

## 6. 认证 API（4）

### 6.1 POST `/api/auth/register` — 注册

注册新用户账号。

| 属性 | 说明 |
|------|------|
| 权限 | 无需认证 |
| CSRF | 豁免 |
| 限流 | 5 次/小时（按 IP） |

**请求体（JSON）**：

```json
{
  "student_id": "2024001",
  "password": "mypassword",
  "nickname": "张三"
}
```

| 字段 | 类型 | 必需 | 校验规则 |
|------|------|------|----------|
| `student_id` | string | 是 | 3-32 字符，仅允许 `[a-zA-Z0-9_-]` |
| `password` | string | 是 | 6-128 字符 |
| `nickname` | string | 是 | 非空，不超过 32 字符 |

**响应结构（201）**：

```json
{
  "id": 1,
  "student_id": "2024001",
  "nickname": "张三",
  "role": "student",
  "csrf_token": "a1b2c3d4e5f6..."
}
```

**错误码**：

| 状态码 | 场景 |
|--------|------|
| 400 | 学号格式无效 / 密码强度不足 / 昵称非法 |
| 409 | 学号已注册 |
| 429 | 注册频率超限（5 次/小时） |

**安全注意事项**：
- 密码使用 `pbkdf2_sha256` 哈希，30 万次迭代
- 注册成功后自动建立 session 并迁移匿名数据
- 限流键：`register:ip:{ip}`

---

### 6.2 POST `/api/auth/login` — 登录

用户登录。

| 属性 | 说明 |
|------|------|
| 权限 | 无需认证 |
| CSRF | 豁免 |
| 限流 | 10 次/10 分钟（按 IP） |

**请求体（JSON）**：

```json
{
  "student_id": "2024001",
  "password": "mypassword"
}
```

**响应结构（200）**：

```json
{
  "id": 1,
  "student_id": "2024001",
  "nickname": "张三",
  "role": "student",
  "csrf_token": "a1b2c3d4e5f6..."
}
```

**错误码**：

| 状态码 | 场景 |
|--------|------|
| 401 | 学号或密码错误 |
| 429 | 登录尝试过于频繁（10 分钟后重试） |

**安全注意事项**：
- 密码验证使用 `secrets.compare_digest()` 常量时间比较，防止时序攻击
- 错误信息统一为"学号或密码错误"，不区分用户是否存在
- 登录成功后保留旧 CSRF token（如果有），避免页面 CSRF 失效
- 自动迁移匿名数据到用户账号
- 限流键：`login:ip:{ip}`

---

### 6.3 GET `/api/auth/me` — 获取当前用户

获取当前登录用户信息。

| 属性 | 说明 |
|------|------|
| 权限 | 需登录（未登录返回 401） |

**响应结构（200）**：

```json
{
  "id": 1,
  "student_id": "2024001",
  "nickname": "张三",
  "role": "student",
  "csrf_token": "a1b2c3d4e5f6..."
}
```

**错误码**：

| 状态码 | 场景 |
|--------|------|
| 401 | 未登录 |

**安全注意事项**：
- 通过 `get_user_by_id()` 查询，不返回 `password_hash` 字段

---

### 6.4 POST `/api/auth/logout` — 登出

清除当前 session。

| 属性 | 说明 |
|------|------|
| 权限 | 无需认证（已登录/未登录均可调用） |
| CSRF | 豁免 |

**请求体**：无

**响应结构**：

```json
{
  "ok": true
}
```

**安全注意事项**：
- 调用 `session.clear()` 清除所有 session 数据
- 登出后客户端需清除本地 CSRF token

---

## 7. 题库 API（7）

### 7.1 GET / POST `/api/banks` — 题库列表 / 创建题库

**GET — 获取题库列表**

| 属性 | 说明 |
|------|------|
| 权限 | 部分作用域需登录 |

**查询参数**：

| 参数 | 类型 | 默认 | 说明 |
|------|------|------|------|
| `scope` | string | `official` | 作用域：`official`/`mine`/`public`/`subscribed` |

| scope 值 | 权限要求 | 返回内容 |
|----------|----------|----------|
| `official` | 无 | 官方题库（`owner_id IS NULL`，`status='active'`） |
| `mine` | 需登录 | 当前用户创建的题库（`status != 'deleted'`） |
| `public` | 无 | 公开题库（`visibility='public'`，`status='active'`，`owner_id IS NOT NULL`） |
| `subscribed` | 需登录 | 当前用户订阅的题库 |

**响应结构**：

```json
{
  "banks": [
    {
      "id": 1,
      "owner_id": null,
      "name": "官方题库",
      "course": "weather",
      "description": "",
      "visibility": "public",
      "status": "active",
      "question_count": 500,
      "created_at": "2026-01-01 00:00:00"
    }
  ]
}
```

**POST — 创建题库**

| 属性 | 说明 |
|------|------|
| 权限 | 需登录 |
| CSRF | 需要 |

**请求体（JSON）**：

```json
{
  "name": "我的题库",
  "course": "weather",
  "description": "题库描述",
  "visibility": "private"
}
```

| 字段 | 类型 | 必需 | 校验规则 |
|------|------|------|----------|
| `name` | string | 是 | 非空，不超过 50 字符 |
| `course` | string | 是 | 非空 |
| `description` | string | 否 | 默认空字符串 |
| `visibility` | string | 否 | `private`(默认) / `public` / `unlisted` |

**响应结构（201）**：返回完整题库对象（同 GET 列表中的 bank 对象）

**错误码**：

| 状态码 | 场景 |
|--------|------|
| 400 | 名称/课程为空或超长 / 可见性无效 / 超过每人 20 个题库上限 |
| 401 | 未登录（`scope=mine`/`subscribed` 或 POST 时） |

**安全注意事项**：
- 每人最多创建 20 个题库（`MAX_BANKS_PER_USER`）
- 新建题库默认 `visibility='private'`，仅创建者可见

---

### 7.2 GET / PUT / DELETE `/api/banks/<bank_id>` — 题库详情 / 编辑 / 删除

**GET — 获取题库详情**

| 属性 | 说明 |
|------|------|
| 权限 | 需通过 `can_read_bank` 校验 |

**PUT — 编辑题库**

| 属性 | 说明 |
|------|------|
| 权限 | 需通过 `can_write_bank` 校验（owner 或 admin） |
| CSRF | 需要 |

**请求体**：可更新字段为白名单：`name`, `course`, `description`, `visibility`, `status`

**DELETE — 删除题库**

| 属性 | 说明 |
|------|------|
| 权限 | 需通过 `can_write_bank` 校验 |
| CSRF | 需要 |

**响应**：
- GET：题库对象
- PUT：更新后的题库对象
- DELETE：`{"ok": true}`

**错误码**：

| 状态码 | 场景 |
|--------|------|
| 403 | 无读/写权限 |
| 404 | 题库不存在 |

**安全注意事项**：
- 删除为软删除（`status='deleted'`），数据保留
- `update_bank()` 使用字段白名单过滤，防止注入非法字段

---

### 7.3 GET `/api/banks/<bank_id>/questions` — 题库题目列表

获取指定题库的题目列表。

| 属性 | 说明 |
|------|------|
| 权限 | 需通过 `can_read_bank` 校验 |

**查询参数**：

| 参数 | 类型 | 默认 | 说明 |
|------|------|------|------|
| `page` | int | 1 | 页码 |
| `page_size` | int | 20 | 每页条数（上限 100） |

**响应结构**：同 [`/api/questions`](#31-get--apiquestions--搜索题目)

**错误码**：

| 状态码 | 场景 |
|--------|------|
| 400 | 分页参数非法 |
| 403 | 无权访问 |
| 404 | 题库不存在 |

---

### 7.4 GET `/api/banks/<bank_id>/progress` — 题库进度

获取当前用户在指定题库的做题进度。

| 属性 | 说明 |
|------|------|
| 权限 | 需通过 `can_read_bank` 校验 |

**响应结构**：

```json
{
  "done_question_ids": [1, 2, 3],
  "total": 100,
  "done": 3,
  "correct_rate": 0.6667
}
```

| 字段 | 说明 |
|------|------|
| `done_question_ids` | 已做过的题目 ID 列表（去重） |
| `total` | 题库总题数 |
| `done` | 已做题数（去重） |
| `correct_rate` | 正确率（正确数/总答题数，保留 4 位小数） |

**错误码**：

| 状态码 | 场景 |
|--------|------|
| 403 | 无权访问 |
| 404 | 题库不存在 |

**安全注意事项**：
- 登录用户按 `user_id` 查询进度，匿名用户按 `session_id` 查询

---

### 7.5 POST `/api/banks/<bank_id>/import` — CSV 导入题目

向指定题库批量导入 CSV 题目。

| 属性 | 说明 |
|------|------|
| 权限 | 需登录 + `can_import_to_bank` 校验（等同 `can_write_bank`） |
| CSRF | 需要 |
| 限流 | 10 次/天（按用户） |

**请求方式**：

- **文件上传**：`multipart/form-data`，字段名 `file`，accept `.csv`
- **JSON 内容**：`application/json`，字段 `content` 为 CSV 文本

**CSV 必填列**：`course`, `chapter`, `type`, `stem`, `answer`

**CSV 可选列**：`explanation`, `knowledge`, `option_A` ~ `option_F`

**CSV 题型**：`single`, `multiple`, `true_false`, `fill_blank`, `short_answer`

**响应结构（201）**：

```json
{
  "ok": true,
  "imported": 48,
  "skipped": 2,
  "flagged": 1,
  "errors": [
    {"row": 5, "reason": "题干超过 2000 字符"}
  ]
}
```

**错误码**：

| 状态码 | 场景 |
|--------|------|
| 400 | CSV 内容为空 / 无可导入题目 / 超过单次 500 题上限 / 全部被过滤 |
| 401 | 未登录 |
| 403 | 无权导入到此题库 |
| 404 | 题库不存在 |
| 429 | 当日导入次数超限（10 次/天） |
| 500 | 数据库写入失败 |

**安全注意事项**：
- 每道题经 `sanitize_question()` 处理：先检测敏感词（`<script`, `javascript:`, `onerror`, `onload`, `onclick`），后 HTML 转义
- 题干上限 2000 字符（`MAX_STEM_LENGTH`），选项上限 500 字符（`MAX_OPTION_LENGTH`）
- 单次导入上限 500 题（`MAX_QUESTIONS_PER_IMPORT`）
- 利用 `UNIQUE(bank_id, stem)` 自动去重，重复题目跳过
- 限流键：`import:user:{user_id}`，窗口 1440 分钟（1 天）
- 导入后自动更新题库 `question_count`

---

### 7.6 POST / DELETE `/api/banks/<bank_id>/subscribe` — 订阅 / 退订

订阅或退订公开题库。

**POST — 订阅**

| 属性 | 说明 |
|------|------|
| 权限 | 需登录 |
| CSRF | 需要 |

**订阅条件**：
- 题库 `visibility` 必须为 `public`
- 题库 `status` 必须为 `active`

**DELETE — 退订**

| 属性 | 说明 |
|------|------|
| 权限 | 需登录 |
| CSRF | 需要 |

**响应**：

```json
{"ok": true}
```

**错误码**：

| 状态码 | 场景 |
|--------|------|
| 401 | 未登录 |
| 403 | 尝试订阅非公开/非活跃题库 |
| 404 | 题库不存在 |

**安全注意事项**：
- 只能订阅 `visibility='public'` 且 `status='active'` 的题库
- 订阅关系存储在 `bank_subscriptions` 表，`PRIMARY KEY(user_id, bank_id)` 防重复

---

## 8. 管理 API（8）

所有管理 API 均需通过 `require_admin` 装饰器校验，要求请求头 `X-Admin-Token` 与 `QUIZ_ADMIN_TOKEN` 环境变量一致（使用 `secrets.compare_digest` 常量时间比较）。

### 8.1 GET / POST `/api/admin/questions` — 管理员题目管理

**GET — 管理员题目列表**

| 属性 | 说明 |
|------|------|
| 权限 | `X-Admin-Token` |

**查询参数**：`course`, `chapter`, `type`, `keyword`, `page`, `page_size`（上限 100）

**POST — 创建单题**

| 属性 | 说明 |
|------|------|
| 权限 | `X-Admin-Token` |

**请求体（JSON）**：

```json
{
  "course": "weather",
  "chapter": 1,
  "type": "single",
  "stem": "题干",
  "options": {"A": "选项A", "B": "选项B"},
  "answer": ["A"],
  "explanation": "解析",
  "knowledge": "知识点"
}
```

必填字段：`course`, `chapter`, `type`, `stem`, `answer`

**响应（POST 201）**：

```json
{"id": 101}
```

**错误码**：

| 状态码 | 场景 |
|--------|------|
| 400 | 分页参数非法 / 缺少必填字段 |
| 401 | 未授权（token 缺失或错误） |
| 403 | 管理功能已禁用 |

---

### 8.2 PUT / DELETE `/api/admin/questions/<qid>` — 编辑 / 删除单题

**PUT — 编辑题目**

**请求体（JSON）**：可更新字段白名单：`stem`, `options`（自动序列化为 `options_json`）, `answer`（自动序列化为 `answer_json`）, `explanation`, `knowledge`, `difficulty`, `chapter`, `type`

**DELETE — 删除题目**

删除题目及其关联的答题记录、错题、收藏。

**响应**：
- PUT：`{"updated": true}`
- DELETE：`{"deleted": true}`

**错误码**：

| 状态码 | 场景 |
|--------|------|
| 401 | 未授权 |
| 403 | 管理功能已禁用 |

**安全注意事项**：
- 删除题目时级联清理 `answer_records`、`mistakes`、`favorites` 表
- `update_question()` 使用字段白名单防止注入

---

### 8.3 POST `/api/admin/import/csv` — CSV 批量导入（官方题库）

向官方题库（bank_id=1）批量导入 CSV 题目。

| 属性 | 说明 |
|------|------|
| 权限 | `X-Admin-Token` |

**请求方式**：同 [7.5](#75-post--apibanksbank_idimport--csv-导入题目)（文件上传或 JSON）

**响应结构（201）**：

```json
{
  "added": 48,
  "skipped": 2,
  "total": 50,
  "parse_errors": []
}
```

**错误码**：

| 状态码 | 场景 |
|--------|------|
| 400 | CSV 内容为空 / 解析失败 / 无有效题目 |
| 401 | 未授权 |
| 500 | 数据库写入失败 |

**安全注意事项**：
- 此端点导入到官方题库（`bank_id=1`），不经过 `sanitize_question()` 处理（仅 `parse_csv` 解析）
- 有解析错误但有有效题目时，仍导入有效部分并返回 `parse_errors`

---

### 8.4 GET `/api/admin/template` — 下载 CSV 模板

下载 CSV 导入模板文件。

| 属性 | 说明 |
|------|------|
| 权限 | `X-Admin-Token` |

**响应**：
- Content-Type: `text/csv`
- Content-Disposition: `attachment; filename=quiz_template.csv`
- 包含表头行和 5 种题型的示例行

**模板内容**：

```csv
course,chapter,type,stem,option_A,option_B,option_C,option_D,answer,explanation,knowledge
weather,1,single,这是一道单选题示例,选项A内容,选项B内容,选项C内容,选项D内容,A,解析内容,知识点
weather,1,multiple,这是一道多选题示例,选项A,选项B,选项C,选项D,"A,C",解析,知识点
weather,1,true_false,这是一道判断题,对,错,,,对,解析,知识点
weather,1,fill_blank,这是一个填空题答案是_____,,,,,答案,解析,知识点
english,1,short_answer,请简述英语语法规则,,,,,答案文本,解析,知识点
```

---

### 8.5 POST `/api/admin/dedupe` — 去重

按 `course + stem` 去重，保留最小 ID 的题目。

| 属性 | 说明 |
|------|------|
| 权限 | `X-Admin-Token` |

**请求体**：无

**响应**：

```json
{"removed": 5}
```

**安全注意事项**：
- 去重时级联删除关联的 `answer_records`、`mistakes`、`favorites`
- 保留 `MIN(id)` 的记录，删除其余重复项

---

### 8.6 POST `/api/admin/backup` — 数据库备份

创建数据库文件备份。

| 属性 | 说明 |
|------|------|
| 权限 | `X-Admin-Token` |

**请求体**：无

**响应**：

```json
{"backup_path": "/path/to/backups/quiz_20260101_120000.db"}
```

**安全注意事项**：
- 使用 `shutil.copy2()` 复制数据库文件
- 备份文件名含时间戳：`quiz_YYYYMMDD_HHMMSS.db`
- 备份路径在响应中返回（生产环境注意不暴露敏感路径）

---

### 8.7 GET `/api/admin/reports` — 举报列表

管理员查看举报列表。

| 属性 | 说明 |
|------|------|
| 权限 | `X-Admin-Token` |

**查询参数**：

| 参数 | 类型 | 默认 | 说明 |
|------|------|------|------|
| `status` | string | — | 筛选状态：`pending`/`resolved`/`dismissed`；不指定时返回全部 |

**响应结构**：

```json
{
  "reports": [
    {
      "id": 1,
      "reporter_id": 5,
      "session_id": null,
      "question_id": 42,
      "reason": "内容不当",
      "detail": "有错别字",
      "status": "pending",
      "handled_by": null,
      "handled_at": null,
      "admin_note": "",
      "created_at": "2026-01-01 12:00:00"
    }
  ]
}
```

---

### 8.8 PUT `/api/admin/reports/<report_id>` — 处理举报

管理员处理举报，更新状态和备注。

| 属性 | 说明 |
|------|------|
| 权限 | `X-Admin-Token` |

**请求体（JSON）**：

```json
{
  "status": "resolved",
  "admin_note": "已修正题目"
}
```

| 字段 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `status` | string | 是 | `resolved` 或 `dismissed` |
| `admin_note` | string | 否 | 处理备注，默认空字符串 |

**响应**：

```json
{"ok": true, "status": "resolved"}
```

**错误码**：

| 状态码 | 场景 |
|--------|------|
| 400 | 无效状态值 |
| 404 | 举报不存在 |

---

## 9. 举报 API（1）

### 9.1 POST `/api/questions/<qid>/report` — 举报题目

举报题目内容问题（登录或匿名均可）。

| 属性 | 说明 |
|------|------|
| 权限 | 匿名/登录均可 |
| CSRF | 登录用户需要 |
| 限流 | 5 次/小时（登录按 user_id，匿名按 IP） |

**路径参数**：

| 参数 | 类型 | 说明 |
|------|------|------|
| `qid` | int | 题目 ID |

**请求体（JSON）**：

```json
{
  "reason": "内容不当",
  "detail": "题目有错别字"
}
```

| 字段 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `reason` | string | 是 | 举报原因（不能为空） |
| `detail` | string | 否 | 详细描述 |

**响应结构（201）**：

```json
{
  "id": 1,
  "ok": true
}
```

**错误码**：

| 状态码 | 场景 |
|--------|------|
| 400 | 举报原因为空 |
| 404 | 题目不存在 |
| 409 | 已登录用户重复举报同一题目 |
| 429 | 举报频率超限（5 次/小时） |

**安全注意事项**：
- 已登录用户对同一题目的举报受唯一索引约束（`UNIQUE(reporter_id, question_id) WHERE reporter_id IS NOT NULL`），重复举报返回 409
- 匿名用户按 IP 限流，登录用户按 user_id 限流
- 限流键：`report:ip:{ip}` 或 `report:user:{user_id}`

---

## 10. 错误码汇总

| 状态码 | 含义 | 触发场景 |
|--------|------|----------|
| 200 | 成功 | 所有成功的 GET / PUT / DELETE |
| 201 | 创建成功 | 注册、创建题库、导入题目、举报、创建单题 |
| 400 | 请求参数错误 | 参数缺失/非法、字段校验失败、CSV 解析失败 |
| 401 | 未认证 | 未登录访问需登录接口、管理员 token 错误 |
| 403 | 无权限 | 题库读写权限不足、CSRF token 无效、管理功能禁用 |
| 404 | 资源不存在 | 题目/题库/举报不存在 |
| 409 | 冲突 | 学号已注册、重复举报 |
| 429 | 限流 | 登录/注册/导入/举报频率超限 |
| 500 | 服务器错误 | 数据库写入失败等内部异常 |

---

## 附录：限流策略汇总

| 操作 | 限流键 | 上限 | 窗口 |
|------|--------|------|------|
| 注册 | `register:ip:{ip}` | 5 次 | 60 分钟 |
| 登录 | `login:ip:{ip}` | 10 次 | 10 分钟 |
| 题库导入 | `import:user:{user_id}` | 10 次 | 1440 分钟（1 天） |
| 举报（匿名） | `report:ip:{ip}` | 5 次 | 60 分钟 |
| 举报（登录） | `report:user:{user_id}` | 5 次 | 60 分钟 |

限流数据存储在 `rate_limits` 表中，每次请求时清理过期记录并检查当前窗口内计数。

---

## 附录：题型说明

| 题型 | type 值 | 答案格式 | 说明 |
|------|---------|----------|------|
| 单选题 | `single` | `["A"]` | 用户答案为单个字母 |
| 多选题 | `multiple` | `["A", "C", "D"]` | 逗号分隔，排序后比较 |
| 判断题 | `true_false` | `["对"]` | 支持多种写法归一化 |
| 填空题 | `fill_blank` | `["答案1", "答案2"]` | 管道符 `\|` 分隔多空 |
| 简答题 | `short_answer` | `["答案文本"]` | 精确匹配或关键词包含 |

---

## 附录：数据隔离规则

| 数据类型 | 匿名用户隔离键 | 登录用户隔离键 | 迁移行为 |
|----------|----------------|----------------|----------|
| 答题记录 (`answer_records`) | `session_id` | `user_id` | 登录时迁移，去重后清理匿名记录 |
| 错题 (`mistakes`) | `session_id` | `user_id` | 同上 |
| 收藏 (`favorites`) | `session_id` | `user_id` | 同上 |
| 举报 (`reports`) | `session_id` | `reporter_id` | 不迁移 |
