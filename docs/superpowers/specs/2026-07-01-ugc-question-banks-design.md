# 设计文档：UGC 题库系统 (v2)

> 创建日期: 2026-07-01
> 版本: v2（根据安全/权限/迁移审查反馈修订）
> 状态: 待审阅
> 路线图阶段: 阶段3（用户账号体系）+ UGC 题库（新增）

## 1. 背景与目标

### 背景

当前系统只有管理员能通过 admin token 上传题库。用户希望每个人都能上传自己的题库，实现 UGC 模式。

### 目标

- 用户注册/登录（学号 + 密码，零新依赖）
- 每个用户可创建多个私有题库，CSV 批量导入题目
- 题库可设为公开，其他用户可"使用"（订阅）公开题库刷题
- 自动审核 + 举报机制
- 现有题库迁移为官方题库，零数据丢失

### 不做（YAGNI）

- 邮箱注册 / 密码找回（管理员重置）
- JWT / bcrypt（用 Flask session + pbkdf2 内置库）
- 题目在线编辑器（CSV 导入 + 删除已足够）
- 班级分组共享（后续迭代）

## 2. 实施分期（4 步渐进）

风险从低到高，每步可独立上线：

### Step 0: 官方题库抽象
- `question_banks` 表 + `questions.bank_id` 列
- 现有题库迁移为 bank_id=1（官方）
- `/api/questions?bank_id=1` 支持
- 现有功能完全不变

### Step 1: 用户系统
- `users` 表 + 注册/登录/登出
- Flask session + CSRF 防护
- session 数据迁移（事务 + 去重 + 幂等）
- 限流

### Step 2: 私有题库
- 创建/删除题库 + CSV 导入到指定题库
- 前端题库选择 UI + 按题库刷题
- 服务端进度隔离
- 自动审核（先检测后转义）

### Step 3: 公开题库 + 举报
- visibility public + 发现页 + 订阅/退订
- 举报功能 + 管理员审核面板
- 公开题库搜索

## 3. 用户系统

### 3.1 数据模型

```sql
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,        -- 格式: pbkdf2_sha256$300000$salt_hex$hash_hex
    nickname TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'student'
        CHECK (role IN ('student', 'admin')),
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
```

### 3.2 认证机制

**密码哈希** — 可升级格式，存储算法+迭代次数+盐+哈希：
```python
import hashlib, secrets

def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    iterations = 300000
    dk = hashlib.pbkdf2_hmac('sha256', password.encode(), bytes.fromhex(salt), iterations)
    return f"pbkdf2_sha256${iterations}${salt}${dk.hex()}"

def verify_password(password: str, stored: str) -> bool:
    algo, iter_str, salt, hash_hex = stored.split('$')
    iterations = int(iter_str)
    dk = hashlib.pbkdf2_hmac('sha256', password.encode(), bytes.fromhex(salt), iterations)
    return secrets.compare_digest(dk.hex(), hash_hex)
```

**会话管理** — Flask session 是签名防篡改，不是加密。Cookie 配置：
```python
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,       # JS 不可读
    SESSION_COOKIE_SAMESITE='Lax',     # 防 CSRF 辅助
    SESSION_COOKIE_SECURE=True,         # 仅 HTTPS（PythonAnywhere 支持）
    PERMANENT_SESSION_LIFETIME=timedelta(days=30),
)
```

session 中只放 `user_id` 和 `role`，不存放密码哈希或权限列表。

**CSRF 防护** — 登录后生成 csrf_token，前端所有非 GET 请求带 `X-CSRF-Token` header：
```python
def ensure_csrf_token():
    if 'csrf_token' not in session:
        session['csrf_token'] = secrets.token_hex(16)
    return session['csrf_token']

@app.before_request
def csrf_protect():
    if request.method != 'GET' and 'user_id' in session:
        token = request.headers.get('X-CSRF-Token', '')
        if not secrets.compare_digest(token, session.get('csrf_token', '')):
            return jsonify({"error": "CSRF token invalid"}), 403
```

**限流** — 基于 SQLite 的简单滑动窗口：
```sql
CREATE TABLE rate_limits (
    key TEXT NOT NULL,                  -- "login:ip:1.2.3.4" / "register:ip:..." / "import:user:5"
    count INTEGER NOT NULL,
    window_start TEXT NOT NULL,
    PRIMARY KEY (key, window_start)
);
```

限流规则：
| 接口 | 限制 |
|------|------|
| POST /api/auth/login (失败) | 同一 IP 10 次/10 分钟 |
| POST /api/auth/register | 同一 IP 5 次/小时 |
| POST /api/banks/<id>/import | 同一用户 10 次/天 |
| POST /api/questions/<id>/report | 同一 IP/session 5 次/小时 |

### 3.3 API

```
POST /api/auth/register  { student_id, password, nickname }
  → 注册 + 自动登录 + 迁移当前 session_id 数据
  → 返回 { id, student_id, nickname, role, csrf_token }

POST /api/auth/login     { student_id, password }
  → 登录 + 迁移当前 session_id 数据
  → 返回 { id, student_id, nickname, role, csrf_token }

GET  /api/auth/me
  → { id, student_id, nickname, role } 或 401

POST /api/auth/logout
  → 清除 session
  → 返回 { ok: true }
```

### 3.4 数据迁移兼容

现有 `answer_records` / `mistakes` / `favorites` 新增 `user_id` 和 `bank_id` 列：

```sql
ALTER TABLE answer_records ADD COLUMN user_id INTEGER;
ALTER TABLE answer_records ADD COLUMN bank_id INTEGER;
ALTER TABLE mistakes ADD COLUMN user_id INTEGER;
ALTER TABLE mistakes ADD COLUMN bank_id INTEGER;
ALTER TABLE favorites ADD COLUMN user_id INTEGER;
ALTER TABLE favorites ADD COLUMN bank_id INTEGER;
```

`bank_id` 冗余存储的原因：题目删除后历史记录仍能追溯题库；按题库统计不需要 JOIN。

**迁移函数** — 事务 + 去重 + 幂等：
```python
def migrate_session_data(user_id, session_id):
    """将匿名 session_id 数据迁移到 user_id。幂等可重复执行。"""
    with db.connection() as conn:
        # answer_records: 迁移不重复的记录
        conn.execute("""
            UPDATE answer_records SET user_id=?
            WHERE session_id=? AND user_id IS NULL
            AND question_id NOT IN (
                SELECT question_id FROM answer_records WHERE user_id=?
            )
        """, (user_id, session_id, user_id))

        # favorites: 迁移不重复的收藏
        conn.execute("""
            UPDATE favorites SET user_id=?
            WHERE session_id=? AND user_id IS NULL
            AND question_id NOT IN (
                SELECT question_id FROM favorites WHERE user_id=?
            )
        """, (user_id, session_id, user_id))

        # mistakes: 同理
        conn.execute("""
            UPDATE mistakes SET user_id=?
            WHERE session_id=? AND user_id IS NULL
            AND question_id NOT IN (
                SELECT question_id FROM mistakes WHERE user_id=?
            )
        """, (user_id, session_id, user_id))

        # 清理重复的匿名数据（已迁移的删除）
        conn.execute("DELETE FROM answer_records WHERE session_id=? AND user_id=?", (session_id, user_id))
        conn.execute("DELETE FROM favorites WHERE session_id=? AND user_id=?", (session_id, user_id))
        conn.execute("DELETE FROM mistakes WHERE session_id=? AND user_id=?", (session_id, user_id))
```

查询优先级：`user_id` > `session_id`。未登录用户继续使用 `X-Session-Id`。

唯一约束防重复：
```sql
CREATE UNIQUE INDEX IF NOT EXISTS idx_fav_user_question ON favorites(user_id, question_id) WHERE user_id IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS idx_mistakes_user_question ON mistakes(user_id, question_id) WHERE user_id IS NOT NULL;
```

## 4. 题库系统

### 4.1 数据模型

```sql
CREATE TABLE question_banks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    owner_id INTEGER,                   -- NULL = 官方题库
    name TEXT NOT NULL,
    course TEXT NOT NULL,
    description TEXT DEFAULT '',
    visibility TEXT NOT NULL DEFAULT 'private'
        CHECK (visibility IN ('private', 'public', 'unlisted')),
    status TEXT NOT NULL DEFAULT 'active'
        CHECK (status IN ('active', 'hidden', 'deleted', 'reviewing')),
    question_count INTEGER DEFAULT 0,   -- 冗余计数，导入/删除时同步更新
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (owner_id) REFERENCES users(id)
);

CREATE TABLE bank_subscriptions (
    user_id INTEGER NOT NULL,
    bank_id INTEGER NOT NULL,
    subscribed_at TEXT DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, bank_id),
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (bank_id) REFERENCES question_banks(id)
);
```

### 4.2 questions 表迁移（重建表方案）

SQLite 不能直接修改 UNIQUE 约束，需要重建表：

```sql
-- 1. 开启事务
BEGIN;

-- 2. 创建新表（UNIQUE(bank_id, stem) 替代 UNIQUE(course, stem)）
CREATE TABLE questions_new (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    original_id INTEGER,
    bank_id INTEGER NOT NULL DEFAULT 1,
    course TEXT NOT NULL,
    chapter INTEGER NOT NULL,
    type TEXT NOT NULL,
    stem TEXT NOT NULL,
    options_json TEXT,
    answer_json TEXT,
    explanation TEXT DEFAULT '',
    knowledge TEXT DEFAULT '',
    flagged INTEGER DEFAULT 0,          -- 审核标记
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(bank_id, stem),
    FOREIGN KEY (bank_id) REFERENCES question_banks(id)
);

-- 3. 拷贝数据
INSERT INTO questions_new (original_id, bank_id, course, chapter, type, stem, options_json, answer_json, explanation, knowledge, created_at)
SELECT id, 1, course, chapter, type, stem, options_json, answer_json, explanation, knowledge, created_at FROM questions;

-- 4. 校验数量
-- 应用层: assert COUNT(*) 一致

-- 5. 替换
DROP TABLE questions;
ALTER TABLE questions_new RENAME TO questions;

-- 6. 创建索引
CREATE INDEX idx_questions_bank_id ON questions(bank_id);

-- 7. 插入官方题库（question_count 动态计算）
INSERT INTO question_banks (id, owner_id, name, course, visibility, status, question_count)
VALUES (1, NULL, '官方题库', 'weather', 'public', 'active', (SELECT COUNT(*) FROM questions));

-- 8. 提交事务
COMMIT;
```

**不硬编码 351**：官方题库的 `question_count` 用 `SELECT COUNT(*)` 动态计算。

### 4.3 必要索引

```sql
CREATE INDEX idx_question_banks_owner ON question_banks(owner_id);
CREATE INDEX idx_question_banks_visibility ON question_banks(visibility);
CREATE INDEX idx_questions_bank_id ON questions(bank_id);
CREATE INDEX idx_bank_subscriptions_user ON bank_subscriptions(user_id);
CREATE INDEX idx_answer_records_user_bank ON answer_records(user_id, bank_id);
CREATE INDEX idx_mistakes_user_bank ON mistakes(user_id, bank_id);
CREATE INDEX idx_favorites_user_bank ON favorites(user_id, bank_id);
```

### 4.4 题库 API（scope 分离）

```
GET  /api/banks?scope=mine          → 我的题库
GET  /api/banks?scope=official      → 官方题库
GET  /api/banks?scope=subscribed    → 已订阅的公开题库
GET  /api/banks?scope=public        → 发现公开题库（Step 3）

POST /api/banks                     → 创建题库（需登录）
GET  /api/banks/<id>                → 题库元信息（不含题目）
GET  /api/banks/<id>/questions      → 题目分页列表
GET  /api/banks/<id>/progress       → 当前用户进度 { done_ids, total, done, correct_rate }
PUT  /api/banks/<id>                → 编辑题库（仅 owner/admin）
DELETE /api/banks/<id>              → 删除题库（仅 owner/admin，题目级联删除）

POST /api/banks/<id>/import         → CSV 导入到指定题库（需登录 + owner）
POST /api/banks/<id>/subscribe      → 订阅公开题库（Step 3）
DELETE /api/banks/<id>/subscribe    → 退订（Step 3）
```

`GET /api/banks/<id>` 只返回元信息，不返回题目列表。题目用 `/questions` 单独请求。

### 4.5 权限模型（集中封装）

不散落在路由里，集中为 3 个函数：

```python
def can_read_bank(user, bank):
    """是否能查看题库内容"""
    if bank.status in ('hidden', 'deleted'):
        return user is not None and user.role == 'admin'
    if bank.owner_id is None:
        return True  # 官方题库
    if bank.visibility == 'public':
        return True
    if user and user.role == 'admin':
        return True
    if user and bank.owner_id == user.id:
        return True
    return False

def can_write_bank(user, bank):
    """是否能编辑/删除题库"""
    if not user:
        return False
    if bank.owner_id is None:
        return user.role == 'admin'  # 官方题库仅 admin
    return user.role == 'admin' or bank.owner_id == user.id

def can_import_to_bank(user, bank):
    """是否能导入题目"""
    return can_write_bank(user, bank)
```

| 操作 | 未登录 | 已登录(非owner) | 已登录(owner) | admin |
|------|--------|----------------|---------------|-------|
| 浏览公开/官方题库 | 可以 | 可以 | 可以 | 可以 |
| 浏览私有题库 | 不可 | 不可 | 可以 | 可以 |
| 创建题库 | 不可 | 可以 | - | 可以 |
| 导入题目 | 不可 | 仅自己的 | - | 任意 |
| 编辑/删除题库 | 不可 | 不可 | 可以 | 可以 |

### 4.6 自动审核（先检测后转义）

**关键修复**：先检测敏感词（原始文本），再 HTML 转义。

```python
import html

SENSITIVE_WORDS = ['<script', 'javascript:', 'onerror', 'onload', 'onclick']

def sanitize_question(q: dict) -> dict:
    """过滤题目中的危险内容。先检测敏感词，后 HTML 转义。"""
    # 1. 先在原始文本上检测敏感词
    raw_texts = []
    for field in ['stem', 'explanation', 'knowledge']:
        if q.get(field):
            raw_texts.append(q[field])
    for value in q.get('options', {}).values():
        raw_texts.append(value)
    combined = '\n'.join(raw_texts).lower()
    q['_flagged'] = any(word in combined for word in SENSITIVE_WORDS)

    # 2. 后 HTML 转义
    for field in ['stem', 'explanation', 'knowledge']:
        if q.get(field):
            q[field] = html.escape(q[field])
    for key in q.get('options', {}):
        q['options'][key] = html.escape(q['options'][key])

    return q
```

`questions` 表新增 `flagged INTEGER DEFAULT 0` 列存储审核标记。

### 4.7 CSV 导入限制

| 限制 | 值 |
|------|-----|
| 单文件大小 | 2MB（`MAX_CONTENT_LENGTH` 已有） |
| 单次导入题数 | 500 题 |
| 单用户题库数 | 20 个 |
| 单题 stem 最大长度 | 2000 字符 |
| 选项最大长度 | 500 字符 |
| 导入频率 | 10 次/天/用户 |

导入返回详细统计：
```json
{
  "ok": true,
  "imported": 38,
  "skipped": 4,
  "flagged": 2,
  "errors": [
    {"row": 12, "reason": "缺少正确答案"},
    {"row": 20, "reason": "题干超过2000字符"}
  ]
}
```

### 4.8 question_count 维护

- CSV 导入后：`UPDATE question_banks SET question_count = (SELECT COUNT(*) FROM questions WHERE bank_id=?) WHERE id=?`
- 删除题目后：同上
- 管理命令定期校准：`UPDATE question_banks SET question_count = (SELECT COUNT(*) FROM questions WHERE bank_id=question_banks.id)`

## 5. 举报功能（Step 3）

```sql
CREATE TABLE reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    reporter_id INTEGER,               -- NULL = 匿名
    session_id TEXT,                   -- 匿名举报的 session 标识
    question_id INTEGER NOT NULL,
    reason TEXT NOT NULL,
    detail TEXT DEFAULT '',
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'resolved', 'dismissed')),
    handled_by INTEGER,                -- 处理人 user_id
    handled_at TEXT,
    admin_note TEXT DEFAULT '',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- 防重复举报（已登录用户）
CREATE UNIQUE INDEX idx_reports_user_question
ON reports(reporter_id, question_id)
WHERE reporter_id IS NOT NULL;

-- 举报查询索引
CREATE INDEX idx_reports_status ON reports(status);
```

```
POST /api/questions/<id>/report    → 举报题目（登录或匿名）
GET  /api/admin/reports            → 举报列表（需 admin）
PUT  /api/admin/reports/<id>       → 处理举报 { status, admin_note }
```

## 6. 刷题流程改造

### 6.1 "当前题库"概念

用户在刷题前选择题库。题库决定题目来源，进度按题库独立计算。

### 6.2 前端状态

```javascript
const currentBankId = ref(null);
const currentBankInfo = ref(null);
const myBanks = ref([]);
const doneSetByBank = reactive({});

const doneSet = computed(() => {
  if (!currentBankId.value) return new Set();
  return doneSetByBank[currentBankId.value] || new Set();
});
```

### 6.3 服务端进度隔离（已登录用户以后端为准）

未登录：继续使用 localStorage + X-Session-Id
已登录：以后端 `answer_records` 为准，localStorage 只做缓存

```
GET /api/banks/<id>/progress
→ { done_question_ids: [...], total, done, correct_rate }
```

前端登录后：每次切换题库调用此接口同步 doneSet。提交答案后后端更新记录，前端更新本地缓存。

### 6.4 后端变更

`/api/questions` 新增 `bank_id` 查询参数：
```
GET /api/questions?bank_id=1&page=1&page_size=100
```
无 `bank_id` 参数时默认返回官方题库（bank_id=1），向后兼容。

## 7. 文件变更清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `backend/database.py` | 修改 | 新增表 + 迁移逻辑（重建 questions 表） |
| `backend/auth.py` | 新增 | 认证模块（注册/登录/密码哈希/CSRF/限流） |
| `backend/permissions.py` | 新增 | 权限函数（can_read_bank/can_write_bank/can_import_to_bank） |
| `backend/app.py` | 修改 | 新增路由 + CSRF 中间件 + 请求识别改造 |
| `backend/csv_importer.py` | 修改 | 新增 sanitize_question() + 导入限制 |
| `backend/migrations.py` | 新增 | 数据库迁移脚本（事务 + 重建表） |
| `backend/static/js/app.js` | 修改 | 题库选择 + 进度隔离 + 登录注册 UI |
| `backend/templates/index.html` | 修改 | "我的"Tab + 题库列表 + 登录注册表单 |
| `backend/static/sw.js` | 修改 | 版本升级 |
| `backend/tests/test_auth.py` | 新增 | 认证 + CSRF + 限流测试 |
| `backend/tests/test_banks.py` | 新增 | 题库 CRUD + 权限测试 |
| `backend/tests/test_migrations.py` | 新增 | 迁移正确性测试 |
| `backend/tests/test_sanitize.py` | 新增 | 审核逻辑测试 |
| `backend/tests/conftest.py` | 修改 | 测试 fixtures 适配 |

## 8. 测试计划

### 单元测试
- `test_auth.py`: 注册、登录、密码哈希格式、CSRF 验证、限流
- `test_banks.py`: 题库 CRUD、权限校验（4 种角色）、CSV 导入到题库
- `test_sanitize.py`: 先检测后转义顺序、敏感词标记、双重转义防护
- `test_migrations.py`: questions 表重建、数据一致性、bank_id 迁移

### E2E 测试
- 注册 → 登录 → 创建题库 → CSV 导入 → 刷题 → 进度隔离
- 未登录用户 → 官方题库正常刷题（回归）

### 回归测试
- 现有 77 项测试全部通过
- 未登录用户体验不变

## 9. P0 清单（上线前必须完成）

1. Flask session cookie 安全配置（HTTPOnly + SameSite + Secure）
2. 所有非 GET 请求 CSRF 防护
3. 密码哈希格式 `pbkdf2_sha256$iterations$salt$hash`（可升级）
4. 登录/注册/导入/举报限流
5. SQLite 迁移用重建表方案（不假设可 ALTER UNIQUE）
6. 官方题库 question_count 动态计算
7. 权限判断集中封装（can_read_bank/can_write_bank/can_import_to_bank）
8. sanitize_question 先检测敏感词，后 html.escape
9. 索引：bank_id、owner_id、visibility、user_id+bank_id
10. 迁移匿名数据：去重 + 事务 + 幂等
11. answer_records/mistakes/favorites 增加 bank_id 冗余列
12. 已登录用户进度以后端为准，localStorage 仅缓存
