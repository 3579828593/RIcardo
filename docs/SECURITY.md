# 安全文档

> 期末冲刺刷题系统 — 安全设计与实践
>
> 参考：OWASP Application Security Verification Standard (ASVS) v4.0 分类

---

## 目录

1. [Authentication（认证）](#1-authentication认证)
2. [Session Management（会话管理）](#2-session-management会话管理)
3. [CSRF（跨站请求伪造防护）](#3-csrf跨站请求伪造防护)
4. [Authorization（授权）](#4-authorization授权)
5. [Input Validation（输入校验）](#5-input-validation输入校验)
6. [Output Encoding（输出编码）](#6-output-encoding输出编码)
7. [Rate Limiting（限流）](#7-rate-limiting限流)
8. [File Upload（文件上传）](#8-file-upload文件上传)
9. [Admin Operations（管理操作）](#9-admin-operations管理操作)
10. [Security Headers（安全响应头）](#10-security-headers安全响应头)
11. [Deployment Secrets（部署密钥）](#11-deployment-secrets部署密钥)
12. [已知安全问题](#12-已知安全问题)
13. [安全检查清单](#13-安全检查清单)

---

## 1. Authentication（认证）

### 1.1 密码哈希

**实现文件**：`backend/auth.py`

| 项目 | 值 | 说明 |
|------|-----|------|
| 算法 | `pbkdf2_sha256` | PBKDF2 with HMAC-SHA256 |
| 迭代次数 | 300,000 次 | 足够慢以抵抗暴力破解 |
| 盐值 | `secrets.token_hex(16)` | 16 字节随机盐，每次哈希唯一 |
| 哈希格式 | `pbkdf2_sha256$300000$salt_hex$hash_hex` | 自描述格式，支持未来升级迭代次数 |

```python
# auth.py
def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    iterations = 300000
    dk = hashlib.pbkdf2_hmac('sha256', password.encode(), bytes.fromhex(salt), iterations)
    return f"pbkdf2_sha256${iterations}${salt}${dk.hex()}"
```

**安全要点**：
- 使用 Python 标准库 `hashlib`，无外部依赖
- 盐值使用 `secrets` 模块（密码学安全随机数），非 `random`
- 哈希格式自描述，`verify_password` 从存储格式中读取迭代次数，支持未来升级

### 1.2 密码验证

```python
# auth.py
def verify_password(password: str, stored: str) -> bool:
    try:
        algo, iter_str, salt, hash_hex = stored.split('$')
        iterations = int(iter_str)
        dk = hashlib.pbkdf2_hmac('sha256', password.encode(), bytes.fromhex(salt), iterations)
        return secrets.compare_digest(dk.hex(), hash_hex)
    except (ValueError, AttributeError):
        return False
```

**安全要点**：
- 使用 `secrets.compare_digest()` 进行**常量时间比较**，防止时序攻击
- 异常时返回 `False`，不泄露内部错误信息
- 支持从存储格式中读取迭代次数，未来可平滑升级

### 1.3 密码策略

| 规则 | 值 | 实现位置 |
|------|-----|----------|
| 最小长度 | 6 字符 | `auth.validate_password()` |
| 最大长度 | 128 字符 | `auth.validate_password()` |
| 复杂度要求 | 无 | 仅长度限制（面向学生群体，降低使用门槛） |

```python
# auth.py
def validate_password(password: str):
    if not password or len(password) < 6:
        return False, "密码至少 6 位"
    if len(password) > 128:
        return False, "密码不能超过 128 位"
    return True, ""
```

### 1.4 学号格式校验

| 规则 | 值 |
|------|-----|
| 最小长度 | 3 字符 |
| 最大长度 | 32 字符 |
| 允许字符 | `[a-zA-Z0-9_-]` |

```python
# auth.py
def validate_student_id(student_id: str):
    if not student_id or len(student_id) < 3:
        return False, "学号至少 3 个字符"
    if len(student_id) > 32:
        return False, "学号不能超过 32 个字符"
    if not re.match(r'^[a-zA-Z0-9_-]+$', student_id):
        return False, "学号只能包含字母、数字、下划线和连字符"
    return True, ""
```

### 1.5 登录错误信息

登录失败统一返回 `"学号或密码错误"`（HTTP 401），**不区分**用户是否存在，防止用户枚举攻击。

---

## 2. Session Management（会话管理）

### 2.1 Flask Session 配置

**实现文件**：`backend/app.py`

```python
app.secret_key = cfg["security"]["secret_key"]
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = True
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(days=30)
```

| 配置项 | 值 | 安全意义 |
|--------|-----|----------|
| `secret_key` | 环境变量 `SECRET_KEY` | Session 签名密钥，生产环境必须设置 |
| `SESSION_COOKIE_HTTPONLY` | `True` | 防止 JavaScript 读取 cookie（防 XSS 窃取） |
| `SESSION_COOKIE_SAMESITE` | `Lax` | 防止跨站发送 cookie（防 CSRF） |
| `SESSION_COOKIE_SECURE` | `True` | 仅 HTTPS 传输 cookie |
| `PERMANENT_SESSION_LIFETIME` | 30 天 | 会话有效期 |

### 2.2 Session 操作

| 操作 | 实现 | 安全措施 |
|------|------|----------|
| 注册 | `session.clear()` → `session['user_id'] = uid` | 清除旧 session 防止固定攻击 |
| 登录 | `session.clear()` → 保留旧 CSRF → 设置 user_id | 保留 CSRF 避免页面失效 |
| 登出 | `session.clear()` | 完全清除会话 |
| 身份提取 | `session.get('user_id')` | 未登录返回 None |

### 2.3 匿名身份管理

匿名用户通过 `X-Session-Id` 请求头标识，服务端校验规则：

```python
# app.py
def _get_session_id() -> str:
    sid = request.headers.get("X-Session-Id", "").strip()
    if not sid or len(sid) < 8:
        return "anon"
    if len(sid) > 64 or not re.match(r'^[a-zA-Z0-9_-]+$', sid):
        return "anon"
    return sid
```

| 校验规则 | 说明 |
|----------|------|
| 长度 8-64 | 防止过短（碰撞）或过长（DoS） |
| 字符集 `[a-zA-Z0-9_-]` | 防止 SQL 注入和特殊字符攻击 |
| 不满足时降级为 `"anon"` | 不报错，返回空数据 |

### 2.4 数据迁移安全

登录/注册时自动迁移匿名数据到用户账号（`migrate_session_data`）：
- **幂等**：可重复执行不报错
- **去重**：已有同题记录不重复迁移（避免唯一约束冲突）
- **清理**：迁移后删除残留的匿名记录（防止数据泄露）

---

## 3. CSRF（跨站请求伪造防护）

### 3.1 CSRF Token 机制

**实现文件**：`backend/auth.py` + `backend/app.py`

```python
# auth.py
def ensure_csrf_token() -> str:
    if 'csrf_token' not in session:
        session['csrf_token'] = secrets.token_hex(16)
    return session['csrf_token']

def csrf_protect():
    if request.method == 'GET':
        return None
    if 'user_id' not in session:
        return None  # 未登录用户不受 CSRF 保护
    token = request.headers.get('X-CSRF-Token', '')
    if not secrets.compare_digest(token, session.get('csrf_token', '')):
        return jsonify({"error": "CSRF token invalid"}), 403
    return None
```

### 3.2 CSRF 防护矩阵

| 请求场景 | CSRF 要求 | 说明 |
|----------|-----------|------|
| GET 请求 | 不需要 | 安全的读操作 |
| 非 GET + 未登录 | 不需要 | 匿名用户豁免（**已知安全债务**） |
| 非 GET + 已登录 | **必须**携带 `X-CSRF-Token` | 通过 `before_request` 全局拦截 |
| `/api/auth/*` 路由 | 豁免 | 登录/注册需建立新 session |

### 3.3 全局中间件

```python
# app.py
@app.before_request
def before_request_csrf():
    if request.path.startswith('/api/auth/'):
        return None
    result = csrf_protect()
    if result is not None:
        return result
```

**安全要点**：
- CSRF token 使用 `secrets.token_hex(16)`（16 字节 = 128 位熵）
- 验证使用 `secrets.compare_digest()` 常量时间比较
- token 在注册/登录响应中返回给客户端
- 客户端需在后续写操作中通过 `X-CSRF-Token` 请求头携带

---

## 4. Authorization（授权）

### 4.1 四级身份模型

**实现文件**：`backend/permissions.py`

```
anonymous  <  student  <  owner  <  admin
(匿名)        (学生)     (题库主)  (管理员)
```

| 身份 | 标识 | 权限范围 |
|------|------|----------|
| `anonymous` | `X-Session-Id` / None | 读官方题库 + 公开题库 |
| `student` | `session['user_id']` + `role='student'` | + 自己创建的题库 |
| `owner` | `user.id == bank.owner_id` | + 自己私有题库的读写 |
| `admin` | `session['role'] == 'admin'` + `X-Admin-Token` | 全部题库（含 hidden/deleted） |

### 4.2 权限函数

```python
# permissions.py
def can_read_bank(user, bank) -> bool:
    """是否能查看题库内容"""
    if b.status in ('hidden', 'deleted'):
        return u is not None and u.role == 'admin'
    if b.owner_id is None:
        return True  # 官方题库
    if b.visibility == 'public':
        return True
    if u and u.role == 'admin':
        return True
    if u and b.owner_id == u.id:
        return True
    return False

def can_write_bank(user, bank) -> bool:
    """是否能编辑/删除题库"""
    if not user:
        return False
    if b.owner_id is None:
        return u.role == 'admin'  # 官方题库仅 admin
    return u.role == 'admin' or b.owner_id == u.id

def can_import_to_bank(user, bank) -> bool:
    """是否能导入题目"""
    return can_write_bank(user, bank)
```

### 4.3 权限校验入口

**`_check_bank_access()`**（`app.py`）：

```python
def _check_bank_access(bank_id, user=None, write=False):
    if bank_id is None or bank_id == 1:
        return True, None, None  # 官方题库，任何人可读
    bank_data = db.get_bank(bank_id)
    if not bank_data:
        return False, None, (jsonify({"error": "题库不存在"}), 404)
    bank = Bank(bank_data)
    user_obj = User(user) if user else None
    allowed = can_write_bank(user_obj, bank) if write else can_read_bank(user_obj, bank)
    if not allowed:
        return False, bank_data, (jsonify({"error": "无权访问此题库"}), 403)
    return True, bank_data, None
```

### 4.4 权限校验覆盖范围

| 端点 | 校验函数 | 防护对象 |
|------|----------|----------|
| `GET /api/questions` | `_check_bank_access` | 防止访问私有题库题目 |
| `GET /api/questions/random` | `_check_bank_access` | 同上 |
| `POST /api/submit` | `_check_bank_access` | 防止向私有题库提交答案 |
| `GET /api/banks/<id>` | `can_read_bank` | 防止查看私有题库信息 |
| `PUT/DELETE /api/banks/<id>` | `can_write_bank` | 防止编辑/删除他人题库 |
| `GET /api/banks/<id>/questions` | `can_read_bank` | 防止查看私有题库题目 |
| `GET /api/banks/<id>/progress` | `can_read_bank` | 防止查看他人进度 |
| `POST /api/banks/<id>/import` | `can_import_to_bank` | 防止向他人题库注入题目 |
| `POST /api/banks/<id>/subscribe` | visibility + status 检查 | 防止订阅私有题库 |
| `GET/POST /api/admin/*` | `require_admin` 装饰器 | 管理员操作隔离 |

### 4.5 数据隔离

| 数据类型 | 匿名隔离键 | 登录隔离键 | 隔离实现 |
|----------|-----------|-----------|----------|
| 答题记录 | `session_id` | `user_id` | WHERE 条件过滤 |
| 错题 | `session_id` | `user_id` | WHERE 条件过滤 |
| 收藏 | `session_id` | `user_id` | WHERE 条件过滤 |
| 举报 | `session_id` | `reporter_id` | WHERE 条件过滤 |
| 题库列表 | — | `owner_id` | scope 筛选 |

---

## 5. Input Validation（输入校验）

### 5.1 分页参数校验

```python
# app.py
def _positive_int_arg(name: str, default: int, maximum: int = None):
    value = request.args.get(name, default, type=int)
    if value is None or value < 1:
        return None, jsonify({"error": f"{name} 必须为正整数"}), 400
    if maximum is not None:
        value = min(value, maximum)
    return value, None, None
```

- 所有分页参数（`page`, `page_size`, `limit`）强制正整数校验
- `page_size` 和 `limit` 有上限（100），防止大量数据拉取

### 5.2 字段白名单

**题库更新**（`database.py`）：

```python
def update_bank(self, bank_id: int, data: dict) -> bool:
    allowed = {'name', 'course', 'description', 'visibility', 'status'}
    fields = {k: v for k, v in data.items() if k in allowed}
```

**题目更新**（`database.py`）：

```python
def update_question(self, qid: int, data: dict):
    allowed = {"stem", "options_json", "answer_json", "explanation",
               "knowledge", "difficulty", "chapter", "type"}
    fields = {k: v for k, v in data.items() if k in allowed}
```

- 使用白名单过滤，丢弃非允许字段
- 防止批量赋值（Mass Assignment）漏洞

### 5.3 LIKE 查询转义

```python
# database.py - search_questions()
if keyword:
    where.append("stem LIKE ? ESCAPE '\\'")
    escaped = keyword.replace("%", "\\%").replace("_", "\\_")
    params.append(f"%{escaped}%")
```

- 用户输入的 `%` 和 `_` 通配符被转义
- 使用参数化查询（`?` 占位符），防止 SQL 注入

### 5.4 CSV 导入字段校验

**实现文件**：`backend/csv_importer.py`

```python
REQUIRED_FIELDS = ['course', 'chapter', 'type', 'stem', 'answer']
OPTIONAL_FIELDS = ['explanation', 'knowledge']
VALID_TYPES = ['single', 'multiple', 'true_false', 'fill_blank', 'short_answer']
OPTION_KEYS = ['A', 'B', 'C', 'D', 'E', 'F']
```

| 校验项 | 规则 |
|--------|------|
| 表头 | 必须包含 `REQUIRED_FIELDS` 所有列 |
| 必填字段 | 每行不能缺少必填字段 |
| 题型 | 必须在 `VALID_TYPES` 中 |
| 章节号 | 必须为正整数 |
| 答案 | 不能为空 |
| 多选答案 | 逗号分隔解析 |
| 填空答案 | 管道符 `\|` 分隔多空 |

### 5.5 SQL 注入防护

所有数据库查询均使用**参数化查询**（`?` 占位符）：

```python
# 所有查询示例
conn.execute("SELECT * FROM questions WHERE id = ?", (qid,))
conn.execute("SELECT * FROM questions WHERE course = ? AND chapter = ?", (course, chapter))
```

- 不使用字符串拼接 SQL
- `LIKE` 查询的通配符单独转义
- 表名/列名不来自用户输入（白名单）

---

## 6. Output Encoding（输出编码）

### 6.1 题目内容消毒

**实现文件**：`backend/csv_importer.py`

```python
SENSITIVE_WORDS = ['<script', 'javascript:', 'onerror', 'onload', 'onclick']

def sanitize_question(q: dict) -> dict:
    # 1. 长度校验
    if len(stem) > MAX_STEM_LENGTH:
        q['_error'] = f"题干超过 {MAX_STEM_LENGTH} 字符"
        return q

    # 2. 先在原始文本上检测敏感词
    combined = '\n'.join(raw_texts).lower()
    q['_flagged'] = any(word in combined for word in SENSITIVE_WORDS)

    # 3. 后 HTML 转义
    for field in ['stem', 'explanation', 'knowledge']:
        if q.get(field):
            q[field] = html.escape(str(q[field]))
    for key in q.get('options', {}):
        q['options'][key] = html.escape(str(q['options'][key]))

    return q
```

**消毒策略：先检测后转义**

| 步骤 | 作用 |
|------|------|
| 1. 长度校验 | 题干 ≤ 2000 字符，选项 ≤ 500 字符 |
| 2. 敏感词检测 | 在原始文本上检测 `<script`, `javascript:`, `onerror`, `onload`, `onclick`，标记 `_flagged` |
| 3. HTML 转义 | 使用 `html.escape()` 转义 `<`, `>`, `&`, `"`, `'` |

**设计理由**：先在原始文本上检测（避免转义后漏检），再转义（确保存储安全）。被标记的题目仍会导入但 `flagged=1`，供管理员审查。

### 6.2 前端输出编码

| 渲染方式 | 安全性 | 使用情况 |
|----------|--------|----------|
| Vue 文本插值 `{{ }}` | 自动 HTML 转义 | 全部使用，无例外 |
| `v-html` 指令 | 不转义，直接渲染 HTML | **完全未使用** |
| Jinja 模板 `[[ ]]` | 自动转义 | 仅用于 index.html 页面结构 |

**安全要点**：
- Vue 3 的 `{{ }}` 文本插值默认对内容进行 HTML 转义
- 项目中**无任何 `v-html` 使用**，杜绝 XSS 通过前端渲染注入
- Jinja 模板分隔符改为 `[[ ]]` 避免与 Vue 冲突，保持自动转义

### 6.3 题干答案标注清理

```python
# database.py
def clean_stem(stem):
    # 移除括号中的答案标注
    stem = _re.sub(r'[（(]\s*(?:答案|答|对|错|[A-Da-d])\s*[）)]', '（　）', stem)
    # 移除题干末尾的答案标记
    stem = _re.sub(r'答案?\s*[:：]\s*\S+', '', stem)
    return stem.strip()
```

- 在 `search_questions()` 和 `get_random_questions()` 返回前清理
- 防止题干中残留的答案标注泄露正确答案

---

## 7. Rate Limiting（限流）

### 7.1 限流实现

**实现文件**：`backend/auth.py`

```python
def check_rate_limit(db, key: str, max_count: int, window_minutes: int) -> bool:
    now = datetime.utcnow()
    window_start = (now - timedelta(minutes=window_minutes)).strftime('%Y-%m-%d %H:%M:%S')
    with db.connection() as conn:
        conn.execute("DELETE FROM rate_limits WHERE window_start < ?", (window_start,))
        row = conn.execute(
            "SELECT SUM(count) as total FROM rate_limits WHERE key = ? AND window_start >= ?",
            (key, window_start)
        ).fetchone()
        current = row['total'] or 0
        if current >= max_count:
            return False
        conn.execute(
            "INSERT INTO rate_limits (key, count, window_start) VALUES (?, 1, ?) "
            "ON CONFLICT(key, window_start) DO UPDATE SET count = count + 1",
            (key, now_str)
        )
    return True
```

### 7.2 限流策略

| 操作 | 限流键 | 上限 | 窗口 | 说明 |
|------|--------|------|------|------|
| 注册 | `register:ip:{ip}` | 5 次 | 60 分钟 | 按 IP 限流 |
| 登录 | `login:ip:{ip}` | 10 次 | 10 分钟 | 按 IP 限流，防暴力破解 |
| 题库导入 | `import:user:{user_id}` | 10 次 | 1440 分钟（1 天） | 按用户限流 |
| 举报（匿名） | `report:ip:{ip}` | 5 次 | 60 分钟 | 按 IP 限流 |
| 举报（登录） | `report:user:{user_id}` | 5 次 | 60 分钟 | 按用户限流 |

### 7.3 限流数据存储

- 存储在 `rate_limits` 表中（`key` + `window_start` 联合主键）
- 每次请求时清理过期记录（`DELETE WHERE window_start < 窗口起始`）
- 使用 `ON CONFLICT ... DO UPDATE` 实现原子计数

### 7.4 请求体大小限制

```python
# app.py
app.config["MAX_CONTENT_LENGTH"] = 1024 * 1024  # 1 MB
```

- 限制请求体最大 1 MB
- 防止大文件上传导致内存耗尽

---

## 8. File Upload（文件上传）

### 8.1 CSV 文件上传

| 项目 | 值 | 说明 |
|------|-----|------|
| 接受类型 | `.csv` | 前端 `accept=".csv"` |
| 解码方式 | `utf-8-sig` | 处理 BOM 头，`errors="replace"` 容错 |
| 最大请求体 | 1 MB | `MAX_CONTENT_LENGTH` |
| 单次最大题目数 | 500 | `MAX_QUESTIONS_PER_IMPORT` |
| 题干最大长度 | 2000 字符 | `MAX_STEM_LENGTH` |
| 选项最大长度 | 500 字符 | `MAX_OPTION_LENGTH` |

### 8.2 上传流程安全

```
文件上传
  │
  ├─ 1. 请求体大小检查 (MAX_CONTENT_LENGTH = 1MB)
  │     └─ 超限 → 413 Request Entity Too Large
  │
  ├─ 2. 权限校验 (can_import_to_bank)
  │     └─ 无权 → 403
  │
  ├─ 3. 限流检查 (10 次/天)
  │     └─ 超限 → 429
  │
  ├─ 4. 解码 (utf-8-sig, errors="replace")
  │     └─ BOM 头自动移除
  │
  ├─ 5. CSV 解析 (parse_csv)
  │     └─ 表头校验、字段校验、题型校验
  │
  ├─ 6. 数量检查 (≤ 500 题)
  │     └─ 超限 → 400
  │
  ├─ 7. 逐题消毒 (sanitize_question)
  │     └─ 长度校验 → 敏感词检测 → HTML 转义
  │
  └─ 8. 批量写入 (INSERT OR IGNORE)
        └─ UNIQUE(bank_id, stem) 自动去重
```

### 8.3 安全要点

- **不执行上传文件**：CSV 仅被解析为文本数据，不作为代码执行
- **BOM 处理**：`utf-8-sig` 编码自动移除 BOM 头，防止解析异常
- **容错解码**：`errors="replace"` 将无效字节替换为替代字符，不抛异常
- **字段白名单**：仅解析 `REQUIRED_FIELDS` + `OPTIONAL_FIELDS` + `OPTION_KEYS`，忽略其他列
- **自动去重**：`UNIQUE(bank_id, stem)` 约束防止重复导入

---

## 9. Admin Operations（管理操作）

### 9.1 管理员认证

**实现文件**：`backend/app.py`

```python
def require_admin(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not cfg["security"]["admin_enabled"]:
            return jsonify({"error": "管理功能已禁用"}), 403
        token = request.headers.get("X-Admin-Token", "")
        expected = cfg["security"]["admin_token"]
        if not token or not expected or not compare_digest(token, expected):
            return jsonify({"error": "未授权"}), 401
        return f(*args, **kwargs)
    return wrapper
```

### 9.2 管理员认证机制

| 项目 | 值 | 说明 |
|------|-----|------|
| 认证方式 | `X-Admin-Token` 请求头 | 静态令牌认证 |
| 令牌来源 | `QUIZ_ADMIN_TOKEN` 环境变量 | 不硬编码在源码中 |
| 比较方式 | `hmac.compare_digest()` | 常量时间比较，防时序攻击 |
| 管理开关 | `admin_enabled` 配置项 | 可全局禁用管理功能 |
| 管理员角色 | `users.role = 'admin'` | 数据库角色字段 |

### 9.3 管理操作安全

| 操作 | 风险 | 防护措施 |
|------|------|----------|
| 创建/编辑/删除题目 | 数据篡改 | `require_admin` + `X-Admin-Token` |
| CSV 批量导入 | 数据注入 | `require_admin` + CSV 解析校验 |
| 去重操作 | 数据丢失 | `require_admin`；保留 MIN(id) |
| 数据库备份 | 数据泄露 | `require_admin`；备份文件存储在服务器 |
| 查看举报 | 隐私泄露 | `require_admin` |
| 处理举报 | 数据篡改 | `require_admin` + 状态白名单校验 |

### 9.4 管理员角色提升

- 用户表 `role` 字段有 `CHECK (role IN ('student', 'admin'))` 约束
- 无注册接口可设置 `admin` 角色（默认 `student`）
- 管理员角色需通过直接数据库操作设置

---

## 10. Security Headers（安全响应头）

### 10.1 响应头配置

**实现文件**：`backend/app.py`

```python
@app.after_request
def add_security_headers(response):
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault(
        "Content-Security-Policy",
        "default-src 'self'; "
        "script-src 'self' 'unsafe-eval'; "
        "style-src 'self' 'unsafe-inline'; "
        "connect-src 'self'; "
        "manifest-src 'self'; "
        "frame-ancestors 'self'"
    )
    return response
```

### 10.2 安全头说明

| 响应头 | 值 | 安全意义 |
|--------|-----|----------|
| `X-Content-Type-Options` | `nosniff` | 防止 MIME 类型嗅探 |
| `X-Frame-Options` | `SAMEORIGIN` | 防止点击劫持（仅同源可嵌入 iframe） |
| `Referrer-Policy` | `strict-origin-when-cross-origin` | 限制 Referer 泄露 |
| `Content-Security-Policy` | 见下文 | 内容安全策略 |

### 10.3 CSP 策略详解

```
default-src 'self';
script-src 'self' 'unsafe-eval';
style-src 'self' 'unsafe-inline';
connect-src 'self';
manifest-src 'self';
frame-ancestors 'self'
```

| 指令 | 值 | 说明 |
|------|-----|------|
| `default-src` | `'self'` | 默认仅允许同源资源 |
| `script-src` | `'self' 'unsafe-eval'` | 允许同源脚本 + `unsafe-eval`（Vue CDN 需要） |
| `style-src` | `'self' 'unsafe-inline'` | 允许同源样式 + 内联样式 |
| `connect-src` | `'self'` | 仅允许同源 API 请求 |
| `manifest-src` | `'self'` | PWA manifest 同源加载 |
| `frame-ancestors` | `'self'` | 防止被外部 iframe 嵌入 |

### 10.4 CSP 已知妥协

- **`script-src 'unsafe-eval'`**：Vue 3 CDN 全量版需要 `eval()`，这是一个已知安全妥协
  - 缓解：Vue 3 文本插值自动转义 + 无 `v-html` 使用
  - 未来改进：迁移到 Vue 3 本地构建版本（预编译模板），可移除 `unsafe-eval`
- **`style-src 'unsafe-inline'`**：允许内联样式
  - 缓解：内联样式仅用于布局，不含用户输入

---

## 11. Deployment Secrets（部署密钥）

### 11.1 环境变量

| 环境变量 | 用途 | 默认值 | 安全要求 |
|----------|------|--------|----------|
| `SECRET_KEY` | Flask session 签名密钥 | `dev-change-me-` + 随机 hex | **生产环境必须设置** |
| `QUIZ_ADMIN_TOKEN` | 管理员 API 令牌 | 无（管理功能禁用） | **生产环境必须设置** |
| `DATA_DIR` | 数据目录路径 | `backend/` | 可选 |
| `LOG_DIR` | 日志目录路径 | `backend/` | 可选 |
| `HOST` | 监听地址 | `127.0.0.1` | 可选 |
| `PORT` | 监听端口 | `5000` | 可选 |

### 11.2 密钥加载逻辑

```python
# config.py
cfg["security"]["secret_key"] = os.environ.get(
    cfg["security"]["secret_key_env"],
    "dev-change-me-" + str(os.urandom(16).hex())
)
cfg["security"]["admin_token"] = os.environ.get(cfg["security"]["admin_token_env"])
```

**安全要点**：
- `SECRET_KEY` 未设置时使用随机值（每次重启变化，session 失效），仅适合开发
- `QUIZ_ADMIN_TOKEN` 未设置时为 `None`，管理功能自动禁用
- 本地开发时若 `admin_enabled=True` 但无 token，使用 `"local-dev-only"` 默认值并发出警告

### 11.3 生产部署清单

| 检查项 | 要求 |
|--------|------|
| `SECRET_KEY` | 设置为足够长的随机字符串（≥ 32 字节） |
| `QUIZ_ADMIN_TOKEN` | 设置为足够长的随机字符串 |
| `SESSION_COOKIE_SECURE` | `True`（HTTPS 环境） |
| HTTPS | PythonAnywhere 默认提供 HTTPS |
| 数据库备份 | 定期执行 `/api/admin/backup` |
| 日志监控 | 监控 `logs/app.log` 异常请求 |

---

## 12. 已知安全问题

### 12.1 CSP 允许 `unsafe-eval`

| 项目 | 说明 |
|------|------|
| 风险等级 | 中 |
| 问题描述 | CSP `script-src` 包含 `'unsafe-eval'`，因为 Vue 3 CDN 全量版需要 `eval()` 进行模板编译 |
| 影响 | 攻击者若能注入 JavaScript，可利用 `eval()` 执行任意代码 |
| 缓解措施 | Vue 文本插值自动转义 + 无 `v-html` + 题目内容经 `sanitize_question()` 消毒 |
| 修复方案 | 迁移到 Vue 3 本地构建版本（预编译模板），移除 `unsafe-eval` |

### 12.2 匿名用户 POST 无 CSRF 保护

| 项目 | 说明 |
|------|------|
| 风险等级 | 低 |
| 问题描述 | `csrf_protect()` 对未登录用户（`session` 中无 `user_id`）的非 GET 请求豁免 CSRF 校验 |
| 影响 | 匿名用户的写操作（收藏、提交答案、举报）可被 CSRF 攻击利用 |
| 缓解措施 | 匿名用户操作影响范围有限（仅影响自身 session 数据），且举报有 IP 限流 |
| 修复方案 | 为匿名用户也生成 CSRF token（基于 session_id），或统一身份模型 |

### 12.3 `GET /api/questions/<qid>` 无题库权限校验

| 项目 | 说明 |
|------|------|
| 风险等级 | 中 |
| 问题描述 | 单题获取端点 `GET /api/questions/<qid>` 不校验题库权限，可通过题目 ID 枚举访问私有题库的题目 |
| 影响 | 攻击者可枚举题目 ID 获取私有题库的题目内容（含正确答案） |
| 缓解措施 | 题目 ID 为自增整数，枚举需大量请求；非敏感考试系统，风险可控 |
| 修复方案 | 在 `api_question()` 中增加 `_check_bank_access(q.get('bank_id'), user)` 校验 |

### 12.4 管理员令牌为静态值

| 项目 | 说明 |
|------|------|
| 风险等级 | 低 |
| 问题描述 | 管理员认证使用静态令牌（`QUIZ_ADMIN_TOKEN`），无过期机制 |
| 影响 | 令牌泄露后无法自动失效 |
| 缓解措施 | 令牌通过环境变量注入，不存储在代码或数据库中；可随时更换环境变量 |
| 修复方案 | 考虑引入 JWT 或基于时间的令牌轮换机制 |

### 12.5 备份路径在响应中返回

| 项目 | 说明 |
|------|------|
| 风险等级 | 低 |
| 问题描述 | `POST /api/admin/backup` 在响应中返回备份文件的完整服务器路径 |
| 影响 | 泄露服务器目录结构信息 |
| 缓解措施 | 仅管理员可调用此端点 |
| 修复方案 | 响应中仅返回备份文件名，不返回完整路径 |

### 12.6 SQLite 并发限制

| 项目 | 说明 |
|------|------|
| 风险等级 | 低 |
| 问题描述 | SQLite 使用长连接 + `threading.Lock()`，高并发下存在锁竞争 |
| 影响 | 并发写入时可能阻塞或超时 |
| 缓解措施 | WAL 模式提升并发读性能；PythonAnywhere 单进程部署，并发量有限 |
| 修复方案 | 高并发场景考虑迁移到 PostgreSQL |

---

## 13. 安全检查清单

### 13.1 部署前检查

- [ ] `SECRET_KEY` 环境变量已设置为随机长字符串
- [ ] `QUIZ_ADMIN_TOKEN` 环境变量已设置为随机长字符串
- [ ] `SESSION_COOKIE_SECURE = True`（HTTPS 环境）
- [ ] HTTPS 已启用（PythonAnywhere 默认提供）
- [ ] `debug = False`（生产配置）
- [ ] 数据库备份目录可写
- [ ] 日志目录可写

### 13.2 代码安全检查

- [ ] 所有 SQL 查询使用参数化（`?` 占位符）
- [ ] 所有用户输入经长度/格式校验
- [ ] 所有更新操作使用字段白名单
- [ ] Vue 模板无 `v-html` 使用
- [ ] CSV 导入经 `sanitize_question()` 消毒
- [ ] 管理员端点有 `@require_admin` 装饰器
- [ ] 题库访问有 `can_read_bank` / `can_write_bank` 校验
- [ ] LIKE 查询通配符已转义

### 13.3 运行时安全检查

- [ ] 限流功能正常工作（注册/登录/导入/举报）
- [ ] CSRF 保护正常工作（登录用户写操作需 token）
- [ ] 安全响应头正确设置（CSP/X-Frame-Options 等）
- [ ] 错误信息不泄露敏感信息（堆栈/路径/SQL）
- [ ] 日志记录异常请求（401/403/429/500）

### 13.4 OWASP ASVS 对照

| ASVS 章节 | 覆盖情况 | 说明 |
|-----------|----------|------|
| V2 Authentication | 覆盖 | pbkdf2_sha256, 30 万次迭代, 常量时间比较 |
| V3 Session Management | 覆盖 | HttpOnly + SameSite + Secure, 30 天有效期 |
| V4 Access Control | 覆盖 | 四级身份模型, can_read/write_bank, _check_bank_access |
| V5 Validation / Sanitization / Encoding | 覆盖 | 输入校验, 字段白名单, HTML 转义, Vue 自动转义 |
| V7 Cryptography | 部分 | 密码哈希使用 PBKDF2；无其他加密需求 |
| V8 Error / Logging | 覆盖 | 统一错误响应, 日志记录, 不泄露堆栈 |
| V9 Communications | 覆盖 | HTTPS (PythonAnywhere), Secure cookie |
| V12 Files / Resources | 覆盖 | CSV 上传校验, MAX_CONTENT_LENGTH, 文件类型限制 |
| V14 Configuration | 覆盖 | 环境变量密钥, CSP, 安全响应头 |
