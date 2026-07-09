# Fix Brief: 最终审查修复 — C-1 + I-1 + I-2 + I-3

## 项目位置
`d:\期末冲刺刷题系统`

## 修复概要
最终代码审查发现 4 个需要修复的问题。本修复一次性处理所有问题。

## C-1 (Critical): 遗留端点权限绕过

### 问题
`/api/questions`、`/api/questions/random`、`/api/submit` 等遗留端点接受 `bank_id` 参数但不检查用户是否有权访问该题库。攻击者可以通过枚举 `bank_id` 访问任何私有题库的题目和答案。

### 修复方案
在 `backend/app.py` 中新增一个权限检查辅助函数，并在遗留端点中调用：

```python
def _check_bank_access(bank_id, user=None, write=False):
    """检查用户是否有权访问题库。返回 (allowed, bank_data_or_None, error_response_or_None)"""
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

需要修改的端点（在 `backend/app.py` 中）：

1. **`GET /api/questions`** (api_questions 函数):
   - 获取 `bank_id` 参数后，调用 `_check_bank_access(bank_id, user)`
   - 如果不允许，返回错误响应
   - 如果 `bank_id` 未提供，默认为 1

2. **`GET /api/questions/random`** (api_random 函数):
   - 同上

3. **`POST /api/submit`** (api_submit 函数):
   - 从请求中获取 `bank_id`（如果有），调用 `_check_bank_access(bank_id, user, write=False)`

4. **`GET /api/questions/<int:qid>`** (如果存在获取单个题目的路由):
   - 获取题目后，检查题目的 `bank_id` 是否可访问

### 具体代码修改

首先，在 `_get_current_user()` 函数之后添加 `_check_bank_access` 函数。

然后修改每个端点。以 `api_questions` 为例：

```python
@app.route("/api/questions")
def api_questions():
    page = max(1, request.args.get("page", 1, type=int))
    per_page = min(100, request.args.get("per_page", 20, type=int))
    bank_id = request.args.get("bank_id", 1, type=int)
    user = _get_current_user()
    
    # 权限检查
    allowed, _, error = _check_bank_access(bank_id, user)
    if not allowed:
        return error
    
    # ... 原有查询逻辑不变
```

对 `api_random` 做同样修改。

对 `api_submit`：从 JSON body 或 form 中获取 `bank_id`，做同样检查。如果 `bank_id` 未提供，默认为 1。

## I-1 (Important): flagged 列未写入

### 问题
`questions` 表有 `flagged` 列（默认 0），但 `batch_add_questions` 的 INSERT 语句没有写入 `flagged` 值。`sanitize_question` 设置的 `_flagged` 标记在导入时被丢弃。

### 修复方案
在 `backend/database.py` 的 `batch_add_questions` 方法中，从 question dict 提取 `_flagged` 并写入 `flagged` 列：

```python
# 在 INSERT 语句中添加 flagged 列
# 在参数中添加 1 if q.get('_flagged') else 0
```

具体修改 `batch_add_questions` 的 INSERT 语句，在列列表和值列表中添加 `flagged`。

## I-2 (Important): sanitize_question 未处理 answer 字段

### 问题
`sanitize_question` 函数只处理 `stem`, `explanation`, `knowledge` 和 `options`，但没有处理 `answer` 字段。虽然 answer 通常是 `['A']` 这样的列表，但如果包含恶意内容则不会被检测。

### 修复方案
在 `backend/csv_importer.py` 的 `sanitize_question` 函数中，在检测阶段添加 answer 的字符串表示到检测文本中，在转义阶段不需要处理（因为 answer 是列表，会被 JSON 序列化）。

具体修改：在 `raw_texts` 收集部分，添加 answer 的处理：
```python
# 在 raw_texts 收集循环之后添加：
if q.get('answer'):
    raw_texts.append(str(q['answer']))
```

## I-3 (Important): 订阅路由未检查题库状态

### 问题
订阅路由只检查 `bank.visibility != 'public'`，但没有检查 `bank.status`。如果题库状态是 `hidden` 或 `deleted`，即使 `visibility='public'` 也能被订阅。

### 修复方案
在 `backend/app.py` 的 `api_bank_subscribe` 路由中，POST 分支添加 status 检查：

```python
if request.method == "POST":
    if bank.visibility != 'public' or bank.status not in ('active',):
        return jsonify({"error": "只能订阅公开题库"}), 403
```

## 测试要求

### 新增测试
在 `backend/tests/test_banks.py` 中新增测试验证 C-1 修复：

```python
def test_cannot_access_private_bank_via_legacy_api():
    """不能通过遗留 API 访问别人的私有题库"""
    import os
    os.environ.setdefault("QUIZ_ADMIN_TOKEN", "test-admin-token")
    from app import app, db
    client = app.test_client()
    # 用户 A 创建私有题库并添加题目
    reg_a = client.post("/api/auth/register", json={
        "student_id": "legacy_owner", "password": "test123456", "nickname": "Owner"
    })
    csrf_a = reg_a.get_json()['csrf_token']
    create = client.post("/api/banks", json={"name": "私有", "course": "test", "visibility": "private"},
                         headers={"X-CSRF-Token": csrf_a})
    bank_id = create.get_json()['id']
    db.add_question({"course": "test", "chapter": 1, "type": "single",
                     "stem": "private_q_test", "options": {}, "answer": ["A"]}, bank_id=bank_id)
    client.post("/api/auth/logout")
    # 用户 B 尝试通过 /api/questions?bank_id=X 访问
    reg_b = client.post("/api/auth/register", json={
        "student_id": "legacy_attacker", "password": "test123456", "nickname": "Attacker"
    })
    csrf_b = reg_b.get_json()['csrf_token']
    resp = client.get(f"/api/questions?bank_id={bank_id}", headers={"X-CSRF-Token": csrf_b})
    assert resp.status_code == 403
```

### 回归测试
运行：`cd d:\期末冲刺刷题系统\backend && python -m pytest tests/ -v --ignore=tests/e2e --tb=short`
预期：152 tests pass (151 existing + 1 new)

## 提交
```bash
cd d:\期末冲刺刷题系统
git add backend/app.py backend/database.py backend/csv_importer.py backend/tests/test_banks.py
git commit -m "fix: 遗留端点权限校验 + flagged列写入 + sanitize answer + 订阅状态检查"
```
