# Task 13: Step 2 — CSV 导入到题库路由

## Context
This is Task 13 of 17 in a UGC question bank system implementation plan. The project is a Flask + Vue + SQLite quiz system at `d:\期末冲刺刷题系统`. Tasks 1-12 are complete (142 tests pass). This task adds a CSV import route to app.py that lets users import questions into their private banks.

## Files
- Modify: `backend/app.py` — 新增 `POST /api/banks/<id>/import` 路由 + 更新 csv_importer import
- Modify: `backend/tests/test_banks.py` — 新增 2 个测试 + 添加 `import io`

## Current State of app.py (critical context)

### Import line to modify (line 23):
Current:
```python
from csv_importer import parse_csv, generate_template
```
Change to:
```python
from csv_importer import parse_csv, generate_template, sanitize_question
```

### Already imported and available (DO NOT re-import):
- Line 39-42: `from auth import (hash_password, verify_password, validate_password, validate_student_id, ensure_csrf_token, csrf_protect, check_rate_limit)`
- Line 43: `from flask import session`
- Line 554: `from permissions import can_read_bank, can_write_bank, can_import_to_bank, Bank, User`
- Line 556-560: `MAX_BANKS_PER_USER = 20`, `MAX_IMPORT_PER_DAY = 10`, `MAX_QUESTIONS_PER_IMPORT = 500`, `MAX_STEM_LENGTH = 2000`, `MAX_OPTION_LENGTH = 500`

### Where to add the new route:
The last bank route `api_bank_progress` ends at line 704. The `@app.errorhandler(404)` starts at line 707. Insert the new route between lines 705 and 707 (after the blank line following api_bank_progress, before the error handler).

### Helper function already available:
- `_get_current_user()` — returns user dict or None from `session['user_id']`

### Database methods already available:
- `db.get_bank(bank_id)` — returns bank dict or None
- `db.batch_add_questions(questions, bank_id=bank_id)` — returns `{"added": int, "skipped": int}`
- `db.update_bank_question_count(bank_id)` — updates question count

## Step 1: Write the failing tests

Add `import io` at the top of `backend/tests/test_banks.py` (after existing imports).

Append these 2 tests to `backend/tests/test_banks.py`:

```python
def test_api_import_csv_to_bank():
    """POST /api/banks/<id>/import CSV 导入到指定题库"""
    import os
    os.environ.setdefault("QUIZ_ADMIN_TOKEN", "test-admin-token")
    from app import app
    client = app.test_client()
    reg = client.post("/api/auth/register", json={
        "student_id": "import001", "password": "test123456", "nickname": "导入测试"
    })
    csrf = reg.get_json()['csrf_token']
    # 创建题库
    create = client.post("/api/banks", json={"name": "导入题库", "course": "test"},
                         headers={"X-CSRF-Token": csrf})
    bank_id = create.get_json()['id']

    # CSV 内容
    csv_content = "course,chapter,type,stem,option_A,option_B,option_C,option_D,answer,explanation,knowledge\n"
    csv_content += "test,1,single,导入测试题1,A选项,B选项,C选项,D选项,A,解析,知识点\n"
    csv_content += "test,1,single,导入测试题2,A选项,B选项,C选项,D选项,B,解析,知识点\n"

    resp = client.post(f"/api/banks/{bank_id}/import",
                       data={"file": (io.BytesIO(csv_content.encode('utf-8-sig')), "test.csv")},
                       content_type="multipart/form-data",
                       headers={"X-CSRF-Token": csrf})
    assert resp.status_code == 201
    data = resp.get_json()
    assert data['imported'] == 2
    assert data['skipped'] == 0


def test_api_import_to_other_user_bank():
    """不能导入到别人的题库"""
    import os
    os.environ.setdefault("QUIZ_ADMIN_TOKEN", "test-admin-token")
    from app import app
    client = app.test_client()
    # 用户 A 创建题库
    reg_a = client.post("/api/auth/register", json={
        "student_id": "owner001", "password": "test123456", "nickname": "Owner"
    })
    csrf_a = reg_a.get_json()['csrf_token']
    create = client.post("/api/banks", json={"name": "A的题库", "course": "test"},
                         headers={"X-CSRF-Token": csrf_a})
    bank_id = create.get_json()['id']
    # 登出
    client.post("/api/auth/logout")
    # 用户 B 登录
    reg_b = client.post("/api/auth/register", json={
        "student_id": "intruder001", "password": "test123456", "nickname": "Intruder"
    })
    csrf_b = reg_b.get_json()['csrf_token']
    # 尝试导入到 A 的题库
    csv_content = "course,chapter,type,stem,answer\n test,1,single,入侵题,A\n"
    resp = client.post(f"/api/banks/{bank_id}/import",
                       data={"file": (io.BytesIO(csv_content.encode()), "t.csv")},
                       content_type="multipart/form-data",
                       headers={"X-CSRF-Token": csrf_b})
    assert resp.status_code == 403
```

## Step 2: Run test to verify it fails

Run: `cd d:\期末冲刺刷题系统\backend && python -m pytest tests/test_banks.py::test_api_import_csv_to_bank -v`
Expected: FAIL — `/api/banks/<id>/import` 路由不存在 (404)

## Step 3: Add import route to `app.py`

First, update the import on line 23:
```python
from csv_importer import parse_csv, generate_template, sanitize_question
```

Then, add this route after `api_bank_progress` (before the `@app.errorhandler(404)`):

```python
@app.route("/api/banks/<int:bank_id>/import", methods=["POST"])
def api_bank_import(bank_id):
    """CSV 导入到指定题库"""
    user = _get_current_user()
    if not user:
        return jsonify({"error": "未登录"}), 401

    bank_data = db.get_bank(bank_id)
    if not bank_data:
        return jsonify({"error": "题库不存在"}), 404

    bank = Bank(bank_data)
    user_obj = User(user)
    if not can_import_to_bank(user_obj, bank):
        return jsonify({"error": "无权导入到此题库"}), 403

    # 限流
    if not check_rate_limit(db, f"import:user:{user['id']}", MAX_IMPORT_PER_DAY, 1440):
        return jsonify({"error": f"今天导入次数已达上限 ({MAX_IMPORT_PER_DAY} 次)"}), 429

    # 读取 CSV 内容
    content = ""
    if "file" in request.files:
        raw = request.files["file"].read()
        content = raw.decode("utf-8-sig", errors="replace")
    else:
        data = request.get_json(silent=True) or {}
        content = data.get("content", "")

    if not content or not content.strip():
        return jsonify({"error": "CSV 内容为空"}), 400

    result = parse_csv(content)
    if not result["questions"]:
        return jsonify({
            "ok": False,
            "error": "没有可导入的题目",
            "parse_errors": result["errors"],
        }), 400

    if len(result["questions"]) > MAX_QUESTIONS_PER_IMPORT:
        return jsonify({
            "ok": False,
            "error": f"单次导入不能超过 {MAX_QUESTIONS_PER_IMPORT} 题",
        }), 400

    # sanitize 每道题
    flagged_count = 0
    valid_questions = []
    errors = list(result["errors"])
    for i, q in enumerate(result["questions"]):
        sq = sanitize_question(q)
        if sq.get('_error'):
            errors.append({"row": i + 2, "reason": sq['_error']})
            continue
        if sq.get('_flagged'):
            flagged_count += 1
        valid_questions.append(sq)

    if not valid_questions:
        return jsonify({
            "ok": False,
            "error": "所有题目都被过滤",
            "parse_errors": errors,
        }), 400

    # 写入数据库
    try:
        import_result = db.batch_add_questions(valid_questions, bank_id=bank_id)
        db.update_bank_question_count(bank_id)
        return jsonify({
            "ok": True,
            "imported": import_result["added"],
            "skipped": import_result["skipped"],
            "flagged": flagged_count,
            "errors": errors,
        }), 201
    except Exception as e:
        return jsonify({
            "ok": False,
            "error": f"数据库写入失败: {str(e)}",
            "parse_errors": errors,
        }), 500
```

## Step 4: Run test to verify it passes

Run: `cd d:\期末冲刺刷题系统\backend && python -m pytest tests/test_banks.py -v`
Expected: PASS — all 22 tests pass (20 existing + 2 new)

## Step 5: Run full regression

Run: `cd d:\期末冲刺刷题系统\backend && python -m pytest tests/ -v --ignore=tests/e2e --tb=short`
Expected: 144 tests pass (142 existing + 2 new)

## Step 6: Commit

```bash
cd d:\期末冲刺刷题系统
git add backend/app.py backend/tests/test_banks.py
git commit -m "feat: Step 2 — CSV 导入到指定题库 + sanitize + 限流"
```
