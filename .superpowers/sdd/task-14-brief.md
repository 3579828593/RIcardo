# Task 14: Step 3 — reports 表 + 举报路由

## Context
This is Task 14 of 17 in a UGC question bank system implementation plan. The project is a Flask + Vue + SQLite quiz system at `d:\期末冲刺刷题系统`. Tasks 1-13 are complete (144 tests pass). This task adds a question reporting system: users can report problematic questions, admins can review and handle reports.

## Files
- Modify: `backend/database.py` — 新增 reports 表 + 3 个举报 CRUD 方法
- Modify: `backend/app.py` — 新增 3 个举报路由
- Modify: `backend/tests/test_banks.py` — 新增 4 个测试

## Current State

### database.py — where to add reports table:
In `_init_db()`, the `executescript` block ends at line 159 (`""")`). The last table is `rate_limits` (lines 153-158). Add the reports table SQL **between line 158 (end of rate_limits) and line 159 (closing `""")`)**.

### database.py — where to add CRUD methods:
Add the 3 new methods to the `QuizDatabase` class. Place them after existing bank-related methods (e.g., after `count_user_banks` or wherever the last method is, before `close` or `__del__`).

### app.py — already available (DO NOT re-import or re-define):
- Line 59: `def require_admin(f):` — decorator that checks `X-Admin-Token` header
- Line 100: `def _get_session_id() -> str:` — returns session ID
- Line 510 in database.py: `def get_question(self, qid: int) -> dict:` — returns question dict or None
- `_get_current_user()` — returns user dict or None
- `check_rate_limit(db, key, max_count, window_minutes)` — from auth.py
- `Bank`, `User`, `can_import_to_bank` — from permissions.py

### app.py — where to add routes:
Add the 3 new routes after the existing bank routes (after `api_bank_import` which was added in Task 13, before the `@app.errorhandler(404)`).

## Step 1: Write the failing tests

Append these 4 tests to `backend/tests/test_banks.py`:

```python
def test_report_question():
    """POST /api/questions/<id>/report 举报题目"""
    import os
    os.environ.setdefault("QUIZ_ADMIN_TOKEN", "test-admin-token")
    from app import app, db
    client = app.test_client()
    qid = db.add_question({"course": "test", "chapter": 1, "type": "single",
                           "stem": "report_test_q", "options": {}, "answer": ["A"]})
    resp = client.post(f"/api/questions/{qid}/report", json={
        "reason": "内容不当", "detail": "有错别字"
    })
    assert resp.status_code == 201


def test_report_question_logged_in():
    """登录用户举报"""
    import os
    os.environ.setdefault("QUIZ_ADMIN_TOKEN", "test-admin-token")
    from app import app, db
    client = app.test_client()
    reg = client.post("/api/auth/register", json={
        "student_id": "reporter001", "password": "test123456", "nickname": "举报者"
    })
    csrf = reg.get_json()['csrf_token']
    qid = db.add_question({"course": "test", "chapter": 1, "type": "single",
                           "stem": "report_login_test", "options": {}, "answer": ["A"]})
    resp = client.post(f"/api/questions/{qid}/report", json={
        "reason": "错误答案"
    }, headers={"X-CSRF-Token": csrf})
    assert resp.status_code == 201


def test_admin_list_reports():
    """GET /api/admin/reports 管理员查看举报列表"""
    import os
    os.environ.setdefault("QUIZ_ADMIN_TOKEN", "test-admin-token")
    from app import app, db
    client = app.test_client()
    qid = db.add_question({"course": "test", "chapter": 1, "type": "single",
                           "stem": "admin_report_test", "options": {}, "answer": ["A"]})
    client.post(f"/api/questions/{qid}/report", json={"reason": "测试"})
    resp = client.get("/api/admin/reports", headers={"X-Admin-Token": "test-admin-token"})
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data['reports']) >= 1


def test_admin_handle_report():
    """PUT /api/admin/reports/<id> 处理举报"""
    import os
    os.environ.setdefault("QUIZ_ADMIN_TOKEN", "test-admin-token")
    from app import app, db
    client = app.test_client()
    qid = db.add_question({"course": "test", "chapter": 1, "type": "single",
                           "stem": "handle_report_test", "options": {}, "answer": ["A"]})
    client.post(f"/api/questions/{qid}/report", json={"reason": "测试"})
    # 获取 report id
    reports = client.get("/api/admin/reports", headers={"X-Admin-Token": "test-admin-token"}).get_json()['reports']
    report_id = reports[-1]['id']
    # 处理
    resp = client.put(f"/api/admin/reports/{report_id}",
                      json={"status": "resolved", "admin_note": "已处理"},
                      headers={"X-Admin-Token": "test-admin-token"})
    assert resp.status_code == 200
    assert resp.get_json()['status'] == 'resolved'
```

## Step 2: Run test to verify it fails

Run: `cd d:\期末冲刺刷题系统\backend && python -m pytest tests/test_banks.py::test_report_question -v`
Expected: FAIL — reports 表和举报路由不存在

## Step 3: Add reports table and CRUD to database.py, routes to app.py

### 3a: reports table SQL (in database.py _init_db executescript, after rate_limits table, before closing `""")`):

```sql
                CREATE TABLE IF NOT EXISTS reports (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    reporter_id INTEGER,
                    session_id TEXT,
                    question_id INTEGER NOT NULL,
                    reason TEXT NOT NULL,
                    detail TEXT DEFAULT '',
                    status TEXT NOT NULL DEFAULT 'pending'
                        CHECK (status IN ('pending', 'resolved', 'dismissed')),
                    handled_by INTEGER,
                    handled_at TEXT,
                    admin_note TEXT DEFAULT '',
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                );
                CREATE UNIQUE INDEX IF NOT EXISTS idx_reports_user_question
                ON reports(reporter_id, question_id) WHERE reporter_id IS NOT NULL;
                CREATE INDEX IF NOT EXISTS idx_reports_status ON reports(status);
```

### 3b: CRUD methods (add to QuizDatabase class in database.py):

```python
    def create_report(self, question_id: int, reason: str, detail: str = '',
                      reporter_id: int = None, session_id: str = None) -> int:
        """创建举报。已登录用户重复举报返回 None。"""
        try:
            with self.connection() as conn:
                cur = conn.execute(
                    """INSERT INTO reports (reporter_id, session_id, question_id, reason, detail)
                    VALUES (?, ?, ?, ?, ?)""",
                    (reporter_id, session_id, question_id, reason, detail)
                )
                return cur.lastrowid
        except sqlite3.IntegrityError:
            return None  # 重复举报

    def list_reports(self, status: str = None) -> list:
        """列出举报"""
        with self.connection() as conn:
            if status:
                rows = conn.execute(
                    "SELECT * FROM reports WHERE status = ? ORDER BY created_at DESC", (status,)
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM reports ORDER BY created_at DESC"
                ).fetchall()
        return [dict(r) for r in rows]

    def handle_report(self, report_id: int, status: str, admin_note: str = '',
                      handler_id: int = None) -> bool:
        """处理举报"""
        with self.connection() as conn:
            cur = conn.execute(
                """UPDATE reports SET status = ?, admin_note = ?, handled_by = ?, handled_at = CURRENT_TIMESTAMP
                WHERE id = ?""",
                (status, admin_note, handler_id, report_id)
            )
            return cur.rowcount > 0
```

### 3c: Routes (add to app.py, after bank routes, before @app.errorhandler(404)):

```python
@app.route("/api/questions/<int:qid>/report", methods=["POST"])
def api_report_question(qid):
    """举报题目（登录或匿名）"""
    q = db.get_question(qid)
    if not q:
        return jsonify({"error": "题目不存在"}), 404

    data = request.get_json(silent=True) or {}
    reason = (data.get("reason") or "").strip()
    detail = (data.get("detail") or "").strip()
    if not reason:
        return jsonify({"error": "举报原因不能为空"}), 400

    user = _get_current_user()
    reporter_id = user['id'] if user else None
    session_id = _get_session_id() if not user else None

    # 限流
    ip = request.remote_addr or "unknown"
    rate_key = f"report:ip:{ip}" if not user else f"report:user:{user['id']}"
    if not check_rate_limit(db, rate_key, 5, 60):
        return jsonify({"error": "举报过于频繁，请稍后再试"}), 429

    report_id = db.create_report(qid, reason, detail, reporter_id, session_id)
    if report_id is None:
        return jsonify({"error": "你已经举报过这道题"}), 409

    return jsonify({"id": report_id, "ok": True}), 201


@app.route("/api/admin/reports", methods=["GET"])
@require_admin
def api_admin_reports():
    """管理员查看举报列表"""
    status = request.args.get("status")
    reports = db.list_reports(status)
    return jsonify({"reports": reports})


@app.route("/api/admin/reports/<int:report_id>", methods=["PUT"])
@require_admin
def api_admin_handle_report(report_id):
    """管理员处理举报"""
    data = request.get_json(silent=True) or {}
    status = data.get("status")
    admin_note = data.get("admin_note", "")
    if status not in ('resolved', 'dismissed'):
        return jsonify({"error": "无效状态"}), 400
    ok = db.handle_report(report_id, status, admin_note)
    if not ok:
        return jsonify({"error": "举报不存在"}), 404
    return jsonify({"ok": True, "status": status})
```

## Step 4: Run test to verify it passes

Run: `cd d:\期末冲刺刷题系统\backend && python -m pytest tests/test_banks.py -v`
Expected: PASS — all 26 tests pass (22 existing + 4 new)

## Step 5: Run full regression

Run: `cd d:\期末冲刺刷题系统\backend && python -m pytest tests/ -v --ignore=tests/e2e --tb=short`
Expected: 148 tests pass (144 existing + 4 new)

## Step 6: Commit

```bash
cd d:\期末冲刺刷题系统
git add backend/database.py backend/app.py backend/tests/test_banks.py
git commit -m "feat: Step 3 — reports 表 + 举报路由 + 管理员审核面板"
```
