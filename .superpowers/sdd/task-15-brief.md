# Task 15: Step 3 — 公开题库订阅/退订

## Context
This is Task 15 of 17 in a UGC question bank system implementation plan. The project is a Flask + Vue + SQLite quiz system at `d:\期末冲刺刷题系统`. Tasks 1-14 are complete (148 tests pass). This task adds subscribe/unsubscribe functionality for public question banks.

## Files
- Modify: `backend/database.py` — 新增 2 个订阅方法
- Modify: `backend/app.py` — 新增 1 个订阅/退订路由（POST + DELETE 同路由）
- Modify: `backend/tests/test_banks.py` — 新增 3 个测试

## Current State

### database.py — `bank_subscriptions` table already exists:
Created in Task 10, has columns: `user_id`, `bank_id`, `subscribed_at`, with UNIQUE(user_id, bank_id).

### database.py — `list_banks` already supports `scope=subscribed`:
Lines 361-368 already implement the subscribed scope query with JOIN on bank_subscriptions. No changes needed to list_banks.

### app.py — `GET /api/banks?scope=subscribed` already handled:
Lines 576-579 already handle the subscribed scope in the api_banks route. No changes needed to api_banks.

### app.py — already available (DO NOT re-import or re-define):
- `_get_current_user()` — returns user dict or None
- `Bank(bank_data)` — wraps bank dict, exposes `.visibility`
- `db.get_bank(bank_id)` — returns bank dict or None
- `check_rate_limit`, `csrf_protect` — from auth.py

### Where to add:
- **database.py**: Add the 2 new methods after `unsubscribe_bank` would go... actually, add them after the existing bank CRUD methods (after `count_user_banks` or after `handle_report` — wherever the last method in the class is, before `close`/`__del__`/`backup`).
- **app.py**: Add the new route after the report routes (added in Task 14), before `@app.errorhandler(404)`.

## Step 1: Write the failing tests

Append these 3 tests to `backend/tests/test_banks.py`:

```python
def test_subscribe_bank():
    """POST /api/banks/<id>/subscribe 订阅公开题库"""
    import os
    os.environ.setdefault("QUIZ_ADMIN_TOKEN", "test-admin-token")
    from app import app, db
    client = app.test_client()
    # 用户 A 创建公开题库
    reg_a = client.post("/api/auth/register", json={
        "student_id": "pubowner001", "password": "test123456", "nickname": "PubOwner"
    })
    csrf_a = reg_a.get_json()['csrf_token']
    create = client.post("/api/banks", json={
        "name": "公开题库", "course": "test", "visibility": "public"
    }, headers={"X-CSRF-Token": csrf_a})
    bank_id = create.get_json()['id']
    client.post("/api/auth/logout")

    # 用户 B 订阅
    reg_b = client.post("/api/auth/register", json={
        "student_id": "subscriber001", "password": "test123456", "nickname": "Sub"
    })
    csrf_b = reg_b.get_json()['csrf_token']
    resp = client.post(f"/api/banks/{bank_id}/subscribe",
                       headers={"X-CSRF-Token": csrf_b})
    assert resp.status_code == 200

    # 查看已订阅
    resp = client.get("/api/banks?scope=subscribed")
    assert resp.status_code == 200
    banks = resp.get_json()['banks']
    assert any(b['id'] == bank_id for b in banks)


def test_unsubscribe_bank():
    """DELETE /api/banks/<id>/subscribe 退订"""
    import os
    os.environ.setdefault("QUIZ_ADMIN_TOKEN", "test-admin-token")
    from app import app, db
    client = app.test_client()
    # 创建公开题库
    reg_a = client.post("/api/auth/register", json={
        "student_id": "unsubowner001", "password": "test123456", "nickname": "Owner"
    })
    csrf_a = reg_a.get_json()['csrf_token']
    create = client.post("/api/banks", json={
        "name": "退订测试", "course": "test", "visibility": "public"
    }, headers={"X-CSRF-Token": csrf_a})
    bank_id = create.get_json()['id']
    client.post("/api/auth/logout")

    # 订阅
    reg_b = client.post("/api/auth/register", json={
        "student_id": "unsub001", "password": "test123456", "nickname": "Unsub"
    })
    csrf_b = reg_b.get_json()['csrf_token']
    client.post(f"/api/banks/{bank_id}/subscribe", headers={"X-CSRF-Token": csrf_b})
    # 退订
    resp = client.delete(f"/api/banks/{bank_id}/subscribe",
                         headers={"X-CSRF-Token": csrf_b})
    assert resp.status_code == 200
    # 确认已退订
    resp = client.get("/api/banks?scope=subscribed")
    banks = resp.get_json()['banks']
    assert not any(b['id'] == bank_id for b in banks)


def test_cannot_subscribe_private_bank():
    """不能订阅私有题库"""
    import os
    os.environ.setdefault("QUIZ_ADMIN_TOKEN", "test-admin-token")
    from app import app
    client = app.test_client()
    reg_a = client.post("/api/auth/register", json={
        "student_id": "privowner001", "password": "test123456", "nickname": "PrivOwner"
    })
    csrf_a = reg_a.get_json()['csrf_token']
    create = client.post("/api/banks", json={
        "name": "私有题库", "course": "test", "visibility": "private"
    }, headers={"X-CSRF-Token": csrf_a})
    bank_id = create.get_json()['id']
    client.post("/api/auth/logout")

    reg_b = client.post("/api/auth/register", json={
        "student_id": "attacker001", "password": "test123456", "nickname": "Attacker"
    })
    csrf_b = reg_b.get_json()['csrf_token']
    resp = client.post(f"/api/banks/{bank_id}/subscribe",
                       headers={"X-CSRF-Token": csrf_b})
    assert resp.status_code == 403
```

## Step 2: Run test to verify it fails

Run: `cd d:\期末冲刺刷题系统\backend && python -m pytest tests/test_banks.py::test_subscribe_bank -v`
Expected: FAIL — 订阅路由不存在 (404)

## Step 3: Add subscription methods and routes

### 3a: Methods in database.py (add to QuizDatabase class, after report methods):

```python
    def subscribe_bank(self, user_id: int, bank_id: int) -> bool:
        """订阅题库。返回 True 表示新订阅，False 表示已订阅。"""
        try:
            with self.connection() as conn:
                conn.execute(
                    "INSERT INTO bank_subscriptions (user_id, bank_id) VALUES (?, ?)",
                    (user_id, bank_id)
                )
            return True
        except sqlite3.IntegrityError:
            return False

    def unsubscribe_bank(self, user_id: int, bank_id: int) -> bool:
        """退订题库。"""
        with self.connection() as conn:
            cur = conn.execute(
                "DELETE FROM bank_subscriptions WHERE user_id = ? AND bank_id = ?",
                (user_id, bank_id)
            )
            return cur.rowcount > 0
```

### 3b: Route in app.py (add after report routes, before @app.errorhandler(404)):

```python
@app.route("/api/banks/<int:bank_id>/subscribe", methods=["POST", "DELETE"])
def api_bank_subscribe(bank_id):
    """订阅/退订公开题库"""
    user = _get_current_user()
    if not user:
        return jsonify({"error": "未登录"}), 401

    bank_data = db.get_bank(bank_id)
    if not bank_data:
        return jsonify({"error": "题库不存在"}), 404

    bank = Bank(bank_data)

    if request.method == "POST":
        # 只能订阅公开题库
        if bank.visibility != 'public':
            return jsonify({"error": "只能订阅公开题库"}), 403
        db.subscribe_bank(user['id'], bank_id)
        return jsonify({"ok": True})
    else:
        db.unsubscribe_bank(user['id'], bank_id)
        return jsonify({"ok": True})
```

## Step 4: Run test to verify it passes

Run: `cd d:\期末冲刺刷题系统\backend && python -m pytest tests/test_banks.py -v`
Expected: PASS — all 29 tests pass (26 existing + 3 new)

## Step 5: Run full regression

Run: `cd d:\期末冲刺刷题系统\backend && python -m pytest tests/ -v --ignore=tests/e2e --tb=short`
Expected: 151 tests pass (148 existing + 3 new)

## Step 6: Commit

```bash
cd d:\期末冲刺刷题系统
git add backend/database.py backend/app.py backend/tests/test_banks.py
git commit -m "feat: Step 3 — 公开题库订阅/退订 + 权限校验"
```
