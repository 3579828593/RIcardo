# -*- coding: utf-8 -*-
"""测试题库 CRUD + 权限"""
import pytest
import sys
import io
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def _make_bank(owner_id=None, visibility='private', status='active'):
    """构造一个 bank dict（模拟 sqlite3.Row）"""
    return {
        'id': 1, 'owner_id': owner_id, 'name': '测试题库', 'course': 'test',
        'visibility': visibility, 'status': status, 'question_count': 0,
    }


def _make_user(user_id=None, role='student'):
    return {'id': user_id, 'role': role, 'nickname': 'test', 'student_id': 'test'}


def test_can_read_official_bank():
    """官方题库任何人可读"""
    from permissions import can_read_bank
    bank = _make_bank(owner_id=None, visibility='public')
    assert can_read_bank(None, bank) is True
    assert can_read_bank(_make_user(1), bank) is True


def test_can_read_private_bank_owner():
    """私有题库 owner 可读"""
    from permissions import can_read_bank
    bank = _make_bank(owner_id=5, visibility='private')
    assert can_read_bank(_make_user(5), bank) is True


def test_can_read_private_bank_non_owner():
    """私有题库非 owner 不可读"""
    from permissions import can_read_bank
    bank = _make_bank(owner_id=5, visibility='private')
    assert can_read_bank(_make_user(3), bank) is False
    assert can_read_bank(None, bank) is False


def test_can_read_public_bank():
    """公开题库任何人可读"""
    from permissions import can_read_bank
    bank = _make_bank(owner_id=5, visibility='public')
    assert can_read_bank(None, bank) is True
    assert can_read_bank(_make_user(3), bank) is True


def test_can_read_hidden_bank_admin_only():
    """hidden 状态仅 admin 可读"""
    from permissions import can_read_bank
    bank = _make_bank(owner_id=5, visibility='public', status='hidden')
    assert can_read_bank(None, bank) is False
    assert can_read_bank(_make_user(5), bank) is False
    assert can_read_bank(_make_user(1, 'admin'), bank) is True


def test_can_write_bank_owner():
    """owner 可写"""
    from permissions import can_write_bank
    bank = _make_bank(owner_id=5)
    assert can_write_bank(_make_user(5), bank) is True


def test_can_write_bank_non_owner():
    """非 owner 不可写"""
    from permissions import can_write_bank
    bank = _make_bank(owner_id=5)
    assert can_write_bank(_make_user(3), bank) is False
    assert can_write_bank(None, bank) is False


def test_can_write_official_bank_admin():
    """官方题库仅 admin 可写"""
    from permissions import can_write_bank
    bank = _make_bank(owner_id=None)
    assert can_write_bank(_make_user(1, 'admin'), bank) is True
    assert can_write_bank(_make_user(1, 'student'), bank) is False


def test_can_import_same_as_write():
    """can_import_to_bank 等同 can_write_bank"""
    from permissions import can_import_to_bank, can_write_bank
    bank = _make_bank(owner_id=5)
    user = _make_user(5)
    assert can_import_to_bank(user, bank) == can_write_bank(user, bank)


def test_create_bank():
    """创建题库"""
    from database import QuizDatabase
    import tempfile, os
    with tempfile.TemporaryDirectory() as tmpdir:
        db = QuizDatabase(os.path.join(tmpdir, "test.db"))
        uid = db.create_user("bank001", "hash", "Bank用户")
        bank_id = db.create_bank(owner_id=uid, name="我的题库", course="test")
        assert bank_id is not None and bank_id > 1
        bank = db.get_bank(bank_id)
        assert bank['name'] == '我的题库'
        assert bank['owner_id'] == uid
        assert bank['visibility'] == 'private'
        db.close()


def test_list_banks_by_owner():
    """列出用户自己的题库"""
    from database import QuizDatabase
    import tempfile, os
    with tempfile.TemporaryDirectory() as tmpdir:
        db = QuizDatabase(os.path.join(tmpdir, "test.db"))
        uid = db.create_user("list001", "hash", "List用户")
        db.create_bank(owner_id=uid, name="题库A", course="test")
        db.create_bank(owner_id=uid, name="题库B", course="english")
        banks = db.list_banks(owner_id=uid, scope="mine")
        assert len(banks) == 2
        db.close()


def test_list_official_banks():
    """列出官方题库"""
    from database import QuizDatabase
    import tempfile, os
    with tempfile.TemporaryDirectory() as tmpdir:
        db = QuizDatabase(os.path.join(tmpdir, "test.db"))
        banks = db.list_banks(scope="official")
        assert len(banks) == 1
        assert banks[0]['name'] == '官方题库'
        db.close()


def test_delete_bank():
    """删除题库（软删除：status=deleted）"""
    from database import QuizDatabase
    import tempfile, os
    with tempfile.TemporaryDirectory() as tmpdir:
        db = QuizDatabase(os.path.join(tmpdir, "test.db"))
        uid = db.create_user("del001", "hash", "Del用户")
        bank_id = db.create_bank(owner_id=uid, name="待删除", course="test")
        ok = db.delete_bank(bank_id)
        assert ok is True
        bank = db.get_bank(bank_id)
        assert bank['status'] == 'deleted'
        db.close()


def test_update_bank_question_count():
    """更新题库题目计数"""
    from database import QuizDatabase
    import tempfile, os
    with tempfile.TemporaryDirectory() as tmpdir:
        db = QuizDatabase(os.path.join(tmpdir, "test.db"))
        uid = db.create_user("count001", "hash", "Count用户")
        bank_id = db.create_bank(owner_id=uid, name="计数题库", course="test")
        db.add_question({"course": "test", "chapter": 1, "type": "single",
                         "stem": "count_test_1", "options": {}, "answer": ["A"]}, bank_id=bank_id)
        db.update_bank_question_count(bank_id)
        bank = db.get_bank(bank_id)
        assert bank['question_count'] == 1
        db.close()


def test_api_create_bank():
    """POST /api/banks 创建题库"""
    import os
    os.environ.setdefault("QUIZ_ADMIN_TOKEN", "test-admin-token")
    from app import app
    client = app.test_client()
    reg = client.post("/api/auth/register", json={
        "student_id": "apibank001", "password": "test123456", "nickname": "API Bank"
    })
    csrf = reg.get_json()['csrf_token']
    resp = client.post("/api/banks", json={
        "name": "我的API题库", "course": "test"
    }, headers={"X-CSRF-Token": csrf})
    assert resp.status_code == 201
    data = resp.get_json()
    assert data['name'] == '我的API题库'
    assert data['visibility'] == 'private'


def test_api_create_bank_not_logged_in():
    """未登录不能创建题库"""
    import os
    os.environ.setdefault("QUIZ_ADMIN_TOKEN", "test-admin-token")
    from app import app
    client = app.test_client()
    resp = client.post("/api/banks", json={"name": "test", "course": "test"})
    assert resp.status_code == 401


def test_api_list_my_banks():
    """GET /api/banks?scope=mine 列出我的题库"""
    import os
    os.environ.setdefault("QUIZ_ADMIN_TOKEN", "test-admin-token")
    from app import app
    client = app.test_client()
    reg = client.post("/api/auth/register", json={
        "student_id": "listbk001", "password": "test123456", "nickname": "List"
    })
    csrf = reg.get_json()['csrf_token']
    client.post("/api/banks", json={"name": "题库1", "course": "test"},
                headers={"X-CSRF-Token": csrf})
    client.post("/api/banks", json={"name": "题库2", "course": "english"},
                headers={"X-CSRF-Token": csrf})
    resp = client.get("/api/banks?scope=mine")
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data['banks']) == 2


def test_api_list_official_banks():
    """GET /api/banks?scope=official 列出官方题库"""
    import os
    os.environ.setdefault("QUIZ_ADMIN_TOKEN", "test-admin-token")
    from app import app
    client = app.test_client()
    resp = client.get("/api/banks?scope=official")
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data['banks']) >= 1
    assert data['banks'][0]['name'] == '官方题库'


def test_api_get_bank():
    """GET /api/banks/<id> 获取题库信息"""
    import os
    os.environ.setdefault("QUIZ_ADMIN_TOKEN", "test-admin-token")
    from app import app
    client = app.test_client()
    resp = client.get("/api/banks/1")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['name'] == '官方题库'


def test_api_delete_bank():
    """DELETE /api/banks/<id> 删除题库"""
    import os
    os.environ.setdefault("QUIZ_ADMIN_TOKEN", "test-admin-token")
    from app import app
    client = app.test_client()
    reg = client.post("/api/auth/register", json={
        "student_id": "delbk001", "password": "test123456", "nickname": "Del"
    })
    csrf = reg.get_json()['csrf_token']
    create = client.post("/api/banks", json={"name": "待删", "course": "test"},
                         headers={"X-CSRF-Token": csrf})
    bank_id = create.get_json()['id']
    resp = client.delete(f"/api/banks/{bank_id}", headers={"X-CSRF-Token": csrf})
    assert resp.status_code == 200


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
