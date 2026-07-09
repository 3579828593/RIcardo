# UGC 题库系统 — 最终全分支代码审查报告

> 审查范围：`917915c`（UGC 实现前）→ `8c57b36`（当前 HEAD），共 17 个功能提交 + 1 个修复提交
> 审查日期：2026-07-01
> 测试结果：151 项测试全部通过（不含 e2e/playwright）

---

## Critical 级别问题（必须修复才能合并）

### C-1. `/api/questions` 系列端点缺少题库权限校验 — 私有题库数据泄露

**文件与行号：**
- `backend/app.py` 第 212-227 行（`api_questions`）
- `backend/app.py` 第 230-240 行（`api_random`）
- `backend/app.py` 第 251-256 行（`api_question`）
- `backend/app.py` 第 259-281 行（`api_submit`）
- `backend/app.py` 第 176-198 行（`/lite` 轻量版页面）

**问题描述：**

`permissions.py` 定义了 `can_read_bank` 权限函数，`/api/banks/<id>/questions` 和 `/api/banks/<id>/progress` 端点正确使用了该函数。但以下遗留端点完全没有进行题库权限校验：

1. **`GET /api/questions?bank_id=X`**：任何用户（包括未登录用户）可以通过传入私有题库的 `bank_id` 直接获取该题库的所有题目（含答案、解析）。

2. **`GET /api/questions`（不传 bank_id）**：返回**所有题库**的题目（包括私有题库），违反了设计规格中"无 bank_id 参数时默认返回官方题库（bank_id=1），向后兼容"的要求。实际实现中 `bank_id=None` 时不添加任何过滤条件，导致全库泄露。

3. **`GET /api/questions/random`**：不传 `bank_id` 时从所有题库（含私有）随机抽取题目。前端 `loadRandom()` 函数也未传递 `currentBankId`。

4. **`GET /api/questions/<qid>`**：通过题目 ID 直接返回任意题目详情（含答案），不检查该题目所属题库的可见性。

5. **`POST /api/submit`**：提交答案后返回 `correct_answer`、`explanation`、`knowledge`，不检查题目所属题库权限。攻击者知道私有题库的题目 ID 即可获取答案。

6. **`GET /lite`**：轻量版页面调用 `db.search_questions(page=page, page_size=page_size)` 不传 `bank_id`，展示所有题库题目。

**影响：** 私有题库的权限模型被完全绕过。攻击者只需枚举 `bank_id`（自增整数）或 `question_id`（自增整数）即可获取所有私有题库的完整内容（题目、选项、答案、解析）。

**修复建议：**

```python
# 方案：在 /api/questions 系列端点中增加权限校验

@app.route("/api/questions", methods=["GET"])
def api_questions():
    bank_id = request.args.get("bank_id", type=int)
    # 无 bank_id 时默认官方题库（符合设计规格）
    if bank_id is None:
        bank_id = 1
    # 权限校验
    bank_data = db.get_bank(bank_id)
    if not bank_data:
        return jsonify({"error": "题库不存在"}), 404
    user = _get_current_user()
    if not can_read_bank(User(user) if user else None, Bank(bank_data)):
        return jsonify({"error": "无权访问"}), 403
    # ... 原有查询逻辑

@app.route("/api/questions/random", methods=["GET"])
def api_random():
    bank_id = request.args.get("bank_id", type=int)
    if bank_id is None:
        bank_id = 1
    # 同样需要权限校验
    ...

@app.route("/api/questions/<int:qid>", methods=["GET"])
def api_question(qid):
    q = db.get_question(qid)
    if not q:
        return jsonify({"error": "题目不存在"}), 404
    # 检查题目所属题库权限
    bank_data = db.get_bank(q.get('bank_id', 1))
    if not can_read_bank(...):
        return jsonify({"error": "无权访问"}), 403
    return jsonify(q)

@app.route("/api/submit", methods=["POST"])
def api_submit():
    ...
    q = db.get_question(qid)
    if not q:
        return jsonify({"error": "题目不存在"}), 404
    # 检查题目所属题库权限
    bank_data = db.get_bank(q.get('bank_id', 1))
    if not can_read_bank(...):
        return jsonify({"error": "无权访问"}), 403
    ...
```

同时修复前端 `loadRandom()` 函数，添加 `bank_id` 参数：
```javascript
const loadRandom = async () => {
    const params = new URLSearchParams({ limit: 20 });
    if (currentBankId.value) params.set('bank_id', currentBankId.value);
    ...
};
```

---

## Important 级别问题（强烈建议修复）

### I-1. `flagged` 审核标记列从未被写入数据库

**文件与行号：**
- `backend/csv_importer.py` 第 146-178 行（`sanitize_question` 设置 `_flagged`）
- `backend/database.py` 第 491-526 行（`batch_add_questions` 未写入 `flagged` 列）
- `backend/app.py` 第 759-781 行（导入路由仅计数不持久化）

**问题描述：**

`questions` 表有 `flagged INTEGER DEFAULT 0` 列（设计规格要求"存储审核标记"），`sanitize_question` 会设置 `_flagged` 属性。但 `batch_add_questions` 的 INSERT 语句不包含 `flagged` 列，导致审核标记永远为默认值 0。导入路由中 `flagged_count` 仅作为响应返回给用户，未持久化。

**影响：** 管理员无法后续筛选被标记的题目进行审查，审核流程不完整。

**修复建议：** 在 `batch_add_questions` 中读取 `q.get('_flagged')` 并写入 `flagged` 列：

```python
cur = conn.execute(
    """INSERT OR IGNORE INTO questions
    (original_id, bank_id, course, chapter, type, stem, options_json, answer_json,
     explanation, knowledge, flagged)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
    (..., 1 if q.get('_flagged') else 0),
)
```

### I-2. `sanitize_question` 未处理 `answer` 字段

**文件与行号：** `backend/csv_importer.py` 第 146-178 行

**问题描述：**

`sanitize_question` 对 `stem`、`explanation`、`knowledge`、`options` 进行了敏感词检测和 HTML 转义，但完全跳过了 `answer` 字段。答案字段来自用户 CSV 输入，同样可能包含 XSS 载荷。

**影响：** 当前前端使用 Vue 文本插值（`{{ }}`）和 `textContent`（lite 版），不会执行 HTML，因此暂无直接 XSS 风险。但这违反了纵深防御原则——若未来有任何场景将答案渲染为 HTML，将产生 XSS 漏洞。

**修复建议：** 在 `sanitize_question` 中增加对 `answer` 字段的处理：

```python
# 在敏感词检测部分增加 answer
for item in q.get('answer', []):
    if item:
        raw_texts.append(str(item))

# 在 HTML 转义部分增加 answer
q['answer'] = [html.escape(str(a)) if a else a for a in q.get('answer', [])]
```

### I-3. 订阅路由未检查题库 `status`

**文件与行号：** `backend/app.py` 第 852-873 行（`api_bank_subscribe`）

**问题描述：**

订阅路由仅检查 `bank.visibility != 'public'`，未检查 `bank.status`。一个 `status='hidden'` 或 `status='deleted'` 但 `visibility='public'` 的题库仍可被订阅。虽然 `list_banks(scope='public')` 会过滤 `status='active'`，但知道 `bank_id` 的用户可直接调用订阅端点。

**修复建议：** 使用 `can_read_bank` 替代直接检查 `visibility`：

```python
if request.method == "POST":
    user_obj = User(user)
    if not can_read_bank(user_obj, bank):
        return jsonify({"error": "只能订阅公开题库"}), 403
    db.subscribe_bank(user['id'], bank_id)
```

### I-4. 登录限流覆盖所有尝试，而非仅失败尝试

**文件与行号：** `backend/app.py` 第 513 行

**问题描述：**

设计规格要求"POST /api/auth/login (失败) — 同一 IP 10 次/10 分钟"。实际实现对所有登录请求（包括成功登录）计数限流。用户在 10 分钟内成功登录 10 次后会被锁定。

**影响：** 用户体验问题，非安全问题（实际更严格）。

**修复建议：** 仅在登录失败时调用 `check_rate_limit`，或将限制改为"失败次数"计数：

```python
user = db.get_user_by_student_id(student_id)
if not user or not verify_password(password, user['password_hash']):
    if not check_rate_limit(db, f"login:ip:{ip}", 10, 10):
        return jsonify({"error": "登录尝试过于频繁，请 10 分钟后再试"}), 429
    return jsonify({"error": "学号或密码错误"}), 401
```

---

## Minor 级别问题（可选修复）

### M-1. `/api/auth/logout` 豁免 CSRF 保护
**文件：** `backend/app.py` 第 164 行
**说明：** `/api/auth/` 路由全部豁免 CSRF，包括 logout。攻击者可通过 CSRF 诱导用户登出。低风险，多数框架也这样做。

### M-2. 迁移后 `options_json`/`answer_json` 丢失 NOT NULL / DEFAULT 约束
**文件：** `backend/database.py` 第 234-253 行
**说明：** 原表定义为 `NOT NULL DEFAULT '{}'`，新表仅为 `TEXT`。`_row_to_dict` 使用 `.pop(..., default)` 处理 NULL，功能无影响，但约束不一致。

### M-3. 错误响应格式不完全统一
**文件：** `backend/app.py`
**说明：** 大部分错误使用 `{"error": "message"}`，但导入路由使用 `{"ok": False, "error": "..."}`，`reset_stats` 使用 `{"ok": False, "error": str(e)}`。功能无影响，建议统一。

### M-4. 限流清理在每次检查时执行 DELETE
**文件：** `backend/auth.py` 第 74 行
**说明：** `check_rate_limit` 每次调用都执行 `DELETE FROM rate_limits WHERE window_start < ?`。小规模无影响，大规模可改为定时清理。

### M-5. `update_bank` 允许 owner 修改 `status` 字段
**文件：** `backend/database.py` 第 381 行
**说明：** `allowed` 集合包含 `'status'`，owner 可将题库设为 `'reviewing'`、`'hidden'` 等。可能是有意设计（owner 可隐藏自己的题库），但 `'reviewing'` 状态语义不明。

---

## 架构评估

### 职责边界 — 优秀

四个模块的职责划分清晰且一致遵守：

| 模块 | 职责 | 评价 |
|------|------|------|
| `auth.py` | 密码哈希、CSRF、限流 | 零外部依赖，接口简洁 |
| `permissions.py` | 题库读写权限判断 | 3 个函数集中封装，dict/Row 自动包装 |
| `database.py` | 表结构、迁移、CRUD | 统一通过 `QuizDatabase` 类的方法访问 |
| `app.py` | 路由、请求处理、中间件 | 认证通过 `auth.py`，权限通过 `permissions.py` |

### 权限检查一致性 — 良好（有遗漏）

- 题库专属端点（`/api/banks/<id>/*`）全部正确使用 `can_read_bank`/`can_write_bank`/`can_import_to_bank`
- 遗留端点（`/api/questions`、`/api/questions/<qid>`、`/api/submit`）未集成权限检查（见 C-1）
- `can_import_to_bank` 正确委托给 `can_write_bank`

### 数据库操作一致性 — 优秀

所有数据库操作通过 `QuizDatabase` 类的方法进行，使用 `@contextmanager` 统一管理事务（提交/回滚），所有 SQL 查询使用参数化查询（`?` 占位符）。

### 模块化设计 — 优秀

- `auth.py` 的函数可独立测试（test_auth.py 验证了纯函数行为）
- `permissions.py` 的权限函数接受 dict/Row/None，兼容性好
- `csv_importer.py` 的 `parse_csv` 和 `sanitize_question` 是纯函数，易于测试

---

## 安全评估

### 密码安全 — 优秀

- 使用 `pbkdf2_sha256$300000$salt_hex$hash_hex` 格式，300,000 次迭代符合 OWASP 2023 建议
- 每次哈希使用 `secrets.token_hex(16)` 生成独立盐
- 验证使用 `secrets.compare_digest`（常数时间比较，防时序攻击）
- 格式可升级（存储 iterations，验证时读取）

### CSRF 防护 — 良好

- 登录用户的非 GET 请求必须携带 `X-CSRF-Token` header
- 使用 `secrets.compare_digest` 比较 token
- `/api/auth/` 路由合理豁免（登录/注册需要建立新 session）
- 登录时保留旧 CSRF token，避免页面刷新后 token 丢失（Task 16 修复确认）
- `/api/auth/me` 正确返回 `csrf_token`，前端 `checkAuth` 正确恢复

### 限流 — 良好

| 接口 | 限制 | 实现 | 状态 |
|------|------|------|------|
| 注册 | 5 次/60 分钟/IP | `register:ip:{ip}` | 正确 |
| 登录 | 10 次/10 分钟/IP | `login:ip:{ip}` | 覆盖所有尝试（见 I-4） |
| 举报 | 5 次/60 分钟 | `report:ip:{ip}` 或 `report:user:{id}` | 正确 |
| CSV 导入 | 10 次/天/用户 | `import:user:{id}` | 正确 |

### SQL 注入防护 — 优秀

- 所有用户输入通过 `?` 参数化查询传入
- 动态列名（`update_bank`、`update_question`）使用白名单过滤
- `_get_session_id()` 使用正则校验格式（`^[a-zA-Z0-9_-]+$`），防止注入
- LIKE 查询的通配符被正确转义（`%` → `\%`，`_` → `\_`）

### XSS 防护 — 良好

- `sanitize_question` 正确实现"先检测后转义"顺序
- 敏感词检测在原始文本上进行，HTML 转义在后
- 前端无 `v-html` 使用，Vue 文本插值自动转义
- lite 版使用 `escapeHtml()` 函数手动转义
- 遗漏：`answer` 字段未纳入 sanitize 范围（见 I-2）

### 数据迁移安全 — 优秀

- questions 表重建保留了所有列（`difficulty`、`updated_at`、`created_at`）— commit `efb48d0` 修复确认
- 迁移前校验数据量（`old_count == new_count`），不一致则抛异常
- `migrate_session_data` 使用 `NOT IN` 子查询去重 + `DELETE WHERE user_id IS NULL` 清理重复
- 迁移幂等：检查列存在后再 ALTER TABLE，检查 `bank_id` 列存在后再迁移
- 向后兼容：未登录用户（session_id 模式）所有查询正常工作

### Session 安全 — 优秀

- `SESSION_COOKIE_HTTPONLY = True`
- `SESSION_COOKIE_SAMESITE = "Lax"`
- `SESSION_COOKIE_SECURE = True`
- `PERMANENT_SESSION_LIFETIME = 30 天`
- session 中仅存 `user_id` 和 `role`，不存密码哈希

---

## 已知观察项确认

| 观察项 | 状态 | 证据 |
|--------|------|------|
| Task 16 review fix: checkAuth 恢复 CSRF token | **已修复** | `app.js` 第 344 行：`csrfToken.value = data.csrf_token \|\| ''` |
| Task 16 review fix: checkAuth 加载题库列表 | **已修复** | `app.js` 第 345-348 行：`loadMyBanks()` + `loadSubscribedBanks()` |
| `/api/auth/me` 返回 csrf_token | **已修复** | `app.py` 第 545-551 行：response 包含 `csrf_token` |

---

## 总体判定

### NEEDS_FIX

**理由：** 存在 1 个 Critical 级别问题（C-1），导致私有题库的权限模型被遗留端点完全绕过。虽然新增的 `/api/banks/<id>/*` 端点权限校验正确，但 `/api/questions`、`/api/questions/<qid>`、`/api/submit`、`/api/questions/random`、`/lite` 均未集成权限检查，攻击者可通过这些端点直接访问私有题库的全部题目和答案。

**修复优先级：**
1. **必须修复** C-1（权限绕过）— 影响核心安全模型
2. **强烈建议** I-1 ~ I-4 — 影响功能完整性和一致性
3. **可选修复** M-1 ~ M-5 — 不影响合并

**修复 C-1 后建议增加的测试用例：**
- 未登录用户访问 `/api/questions?bank_id=<private_bank_id>` 返回 403
- 非 owner 用户访问 `/api/questions?bank_id=<private_bank_id>` 返回 403
- 未登录用户访问 `/api/questions/<private_question_id>` 返回 403
- `/api/questions` 不传 bank_id 时仅返回官方题库题目
