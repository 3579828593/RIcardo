# 设计文档：UGC 题库系统

> 创建日期: 2026-07-01
> 状态: 待审阅
> 路线图阶段: 阶段3（用户账号体系）+ UGC 题库（新增）

## 1. 背景与目标

### 背景

当前系统只有管理员能通过 admin token 上传题库。用户希望每个人都能上传自己的题库，实现 UGC（用户生成内容）模式。

### 目标

- 用户注册/登录（学号 + 密码，零新依赖）
- 每个用户可创建多个私有题库，CSV 批量导入题目
- 题库可设为公开，其他用户可"使用"（订阅）公开题库刷题
- 自动审核：HTML 转义防 XSS + 敏感词标记 + 举报机制
- 现有 351 题迁移为官方题库，零数据丢失

### 不做（YAGNI）

- 邮箱注册 / 密码找回（管理员重置）
- JWT / bcrypt（用 Flask session + pbkdf2 内置库）
- 题目在线编辑器（CSV 导入 + 删除已足够）
- 班级分组共享（后续迭代，visibility 字段已预留）

## 2. 用户系统

### 2.1 数据模型

```sql
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id TEXT UNIQUE NOT NULL,    -- 学号，唯一标识
    password_hash TEXT NOT NULL,        -- pbkdf2_hmac 哈希
    salt TEXT NOT NULL,                 -- 每用户独立盐（16字节 hex）
    nickname TEXT NOT NULL,             -- 显示名
    role TEXT DEFAULT 'student',        -- student / admin
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
```

### 2.2 认证机制

- **密码哈希**: `hashlib.pbkdf2_hmac('sha256', password, salt, 100000)` — Python 标准库，零依赖
- **会话管理**: Flask `session`（内置签名 cookie，`SECRET_KEY` 加密），`session.permanent = True`，有效期 30 天
- **请求识别**: 优先 `session['user_id']`，未登录回退到 `X-Session-Id` header
- **零前端改动**: 浏览器自动管理 session cookie，无需手动设置 Authorization header

### 2.3 API

```
POST /api/auth/register  { student_id, password, nickname }
  → 注册 + 自动登录 + 迁移当前 session_id 数据到 user_id
  → 返回 { id, student_id, nickname, role }

POST /api/auth/login     { student_id, password }
  → 登录 + 迁移当前 session_id 数据到 user_id
  → 返回 { id, student_id, nickname, role }

GET  /api/auth/me
  → 返回 { id, student_id, nickname, role } 或 401

POST /api/auth/logout
  → 清除 session
  → 返回 { ok: true }
```

### 2.4 数据迁移兼容

现有 `answer_records` / `mistakes` / `favorites` 表新增 `user_id INTEGER` 列（NULL 表示匿名）:

```sql
ALTER TABLE answer_records ADD COLUMN user_id INTEGER;
ALTER TABLE mistakes ADD COLUMN user_id INTEGER;
ALTER TABLE favorites ADD COLUMN user_id INTEGER;
```

登录时自动迁移逻辑:
```python
def migrate_session_data(user_id, session_id):
    """将匿名 session_id 的数据迁移到已登录 user_id"""
    db.execute("UPDATE answer_records SET user_id=? WHERE session_id=? AND user_id IS NULL", (user_id, session_id))
    db.execute("UPDATE mistakes SET user_id=? WHERE session_id=? AND user_id IS NULL", (user_id, session_id))
    db.execute("UPDATE favorites SET user_id=? WHERE session_id=? AND user_id IS NULL", (user_id, session_id))
```

查询优先级: `user_id` > `session_id`。未登录用户继续使用 `X-Session-Id`，完全向后兼容。

## 3. 题库系统

### 3.1 数据模型

```sql
CREATE TABLE question_banks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    owner_id INTEGER,                   -- NULL = 官方题库
    name TEXT NOT NULL,                 -- "高数期末2024"
    course TEXT NOT NULL,               -- "math" / "english" / 自定义
    description TEXT DEFAULT '',
    visibility TEXT DEFAULT 'private',  -- private / public
    question_count INTEGER DEFAULT 0,   -- 冗余计数
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (owner_id) REFERENCES users(id)
);

-- 订阅关系（使用公开题库）
CREATE TABLE bank_subscriptions (
    user_id INTEGER NOT NULL,
    bank_id INTEGER NOT NULL,
    subscribed_at TEXT DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, bank_id),
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (bank_id) REFERENCES question_banks(id)
);
```

### 3.2 questions 表迁移

```sql
ALTER TABLE questions ADD COLUMN bank_id INTEGER DEFAULT 1;
```

迁移脚本:
1. 创建 `question_banks` 表
2. 插入官方题库记录: `INSERT INTO question_banks (id, owner_id, name, course, visibility, question_count) VALUES (1, NULL, '官方题库', 'weather', 'public', 351)`
3. `UPDATE questions SET bank_id=1 WHERE bank_id IS NULL`
4. 修改 `UNIQUE(course, stem)` 约束为 `UNIQUE(bank_id, stem)` — 允许不同题库有相同题干

### 3.3 题库 CRUD API

```
GET  /api/banks                    → 题库列表（我的 + 公开 + 官方）
POST /api/banks                    → 创建题库 { name, course, description, visibility }
                                      需登录，owner_id = 当前用户
GET  /api/banks/<id>               → 题库详情 + 题目分页列表
PUT  /api/banks/<id>               → 编辑题库（仅 owner/admin）
DELETE /api/banks/<id>             → 删除题库（仅 owner/admin，题目级联删除）

POST /api/banks/<id>/import        → CSV 导入到指定题库（需登录 + owner）
GET  /api/banks/<id>/questions     → 题库内题目列表（分页 + 筛选）

POST /api/banks/<id>/subscribe     → 订阅公开题库
DELETE /api/banks/<id>/subscribe   → 退订题库
```

### 3.4 权限模型

| 操作 | 未登录 | 已登录(非owner) | 已登录(owner) | admin |
|------|--------|----------------|---------------|-------|
| 浏览公开题库 | 可以 | 可以 | 可以 | 可以 |
| 浏览私有题库 | 不可 | 不可 | 可以 | 可以 |
| 创建题库 | 不可 | 可以 | - | 可以 |
| 导入题目 | 不可 | 仅自己的 | - | 任意 |
| 编辑/删除题库 | 不可 | 不可 | 可以 | 可以 |
| 订阅公开题库 | 不可 | 可以 | - | 可以 |

官方题库（owner_id=NULL）只有 admin 能编辑/删除/导入。

### 3.5 自动审核

CSV 导入时，`csv_importer.py` 新增 `sanitize_question()` 过滤层:

```python
import html

def sanitize_question(q: dict) -> dict:
    """过滤题目中的危险内容"""
    # 1. HTML 标签转义（防 XSS）
    for field in ['stem', 'explanation', 'knowledge']:
        if q.get(field):
            q[field] = html.escape(q[field])
    for key in q.get('options', {}):
        q['options'][key] = html.escape(q['options'][key])
    # 2. 敏感词检测（记录日志，不阻止导入）
    sensitive_words = ['<script', 'javascript:', 'onerror', 'onload', 'onclick']
    for field in ['stem', 'explanation']:
        for word in sensitive_words:
            if word in (q.get(field) or '').lower():
                q['_flagged'] = True
    return q
```

- HTML 转义是强制的（所有用户内容经过 `html.escape`）
- 敏感词标记但不阻止导入（`_flagged=True` 存入数据库 flag 字段）
- 管理员可在举报面板查看 flagged 题目

### 3.6 举报功能

```sql
CREATE TABLE reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    reporter_id INTEGER,               -- 举报人（NULL = 匿名）
    question_id INTEGER NOT NULL,
    reason TEXT NOT NULL,              -- "内容错误" / "不当内容" / "侵权"
    detail TEXT DEFAULT '',
    status TEXT DEFAULT 'pending',     -- pending / resolved / dismissed
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
```

```
POST /api/questions/<id>/report    → 举报题目（登录或匿名均可）
GET  /api/admin/reports            → 管理员查看举报列表
PUT  /api/admin/reports/<id>       → 处理举报 { status: resolved/dismissed }
```

## 4. 刷题流程改造

### 4.1 "当前题库"概念

用户在刷题前选择题库。题库决定题目来源，进度按题库独立计算。

### 4.2 前端状态

```javascript
const currentBankId = ref(null);       // 当前题库 ID
const currentBankInfo = ref(null);     // 题库元信息
const myBanks = ref([]);               // 我的题库 + 已订阅的公开题库
const doneSetByBank = reactive({});    // 按题库隔离的已做集合

// 当前题库的 doneSet
const doneSet = computed(() => {
  if (!currentBankId.value) return new Set();
  return doneSetByBank[currentBankId.value] || new Set();
});
```

### 4.3 题库选择 UI

未选题库时，刷题 Tab 显示题库列表:
```
┌─────────────────────────────────────┐
│  选择题库开始刷题                    │
│  📚 天气分析（官方）  351题   [开始]  │
│  📚 我的高数题库      42题    [开始]  │
│  📚 英语四级（公开）  85题    [开始]  │
└─────────────────────────────────────┘
```

选中后进入单题刷题流程，顶部显示题库名 + "切换"按钮。

### 4.4 后端变更

`/api/questions` 新增 `bank_id` 查询参数:
```
GET /api/questions?bank_id=1&page=1&page_size=100
```
无 `bank_id` 参数时默认返回官方题库（bank_id=1），向后兼容。

### 4.5 进度隔离

- `doneSet` 按题库分别存储: `localStorage key = quiz_done_<bankId>`
- 切换题库时加载对应 doneSet
- 不同题库的进度互不影响

### 4.6 数据迁移

| 现有数据 | 迁移方式 |
|----------|----------|
| 351 题官方题 | bank_id=1，无需改动 |
| 现有 doneSet | 归入 bank_id=1 |
| 现有答题记录 | 通过 question_id JOIN 关联 bank_id |
| 现有 session_id | 继续工作，未登录用户默认刷官方题库 |

## 5. 文件变更清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `backend/database.py` | 修改 | 新增 users/banks/subscriptions/reports 表 + 迁移逻辑 |
| `backend/auth.py` | 新增 | 认证模块（注册/登录/密码哈希/session管理） |
| `backend/app.py` | 修改 | 新增 auth/banks/reports 路由 + 请求识别改造 |
| `backend/csv_importer.py` | 修改 | 新增 sanitize_question() |
| `backend/static/js/app.js` | 修改 | 题库选择 + 进度隔离 + 登录注册 UI |
| `backend/templates/index.html` | 修改 | "我的"Tab + 题库列表 + 登录注册表单 |
| `backend/static/sw.js` | 修改 | 版本升级 |
| `backend/tests/test_auth.py` | 新增 | 认证测试 |
| `backend/tests/test_banks.py` | 新增 | 题库 CRUD + 权限测试 |
| `backend/tests/conftest.py` | 修改 | 测试 fixtures 适配 |

## 6. 实施分期

考虑到改动量较大，分两期实施:

### 第一期: 用户系统 + 私有题库（本次开发）
- users 表 + 认证 API + 数据迁移
- question_banks 表 + 题库 CRUD + CSV 导入到指定题库
- 前端"我的"Tab + 登录注册 + 题库管理
- 刷题流程改造（选择题库 + 进度隔离）
- 自动审核（HTML 转义 + 敏感词标记）

### 第二期: 公开题库 + 订阅 + 举报（后续迭代）
- visibility 字段生效（public 题库可被搜索/订阅）
- bank_subscriptions 表 + 订阅/退订 API
- 举报功能 + 管理员审核面板
- "发现题库"页面

## 7. 测试计划

### 单元测试
- `test_auth.py`: 注册、登录、密码哈希、session 数据迁移
- `test_banks.py`: 题库 CRUD、权限校验、CSV 导入到题库
- `test_sanitize.py`: HTML 转义、敏感词检测

### E2E 测试
- 注册 → 登录 → 创建题库 → CSV 导入 → 刷题 → 进度隔离

### 回归测试
- 现有 77 项测试全部通过
- 未登录用户体验不变
- 官方题库正常可刷
