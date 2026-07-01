# -*- coding: utf-8 -*-
"""测试认证模块：密码哈希、CSRF、限流"""
import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def test_hash_password_format():
    """密码哈希格式: pbkdf2_sha256$iterations$salt$hash"""
    from auth import hash_password
    h = hash_password("test123")
    parts = h.split('$')
    assert len(parts) == 4
    assert parts[0] == 'pbkdf2_sha256'
    assert int(parts[1]) == 300000
    assert len(parts[2]) == 32  # 16 bytes hex = 32 chars
    assert len(parts[3]) == 64  # 32 bytes hex = 64 chars


def test_verify_password_correct():
    """正确密码验证通过"""
    from auth import hash_password, verify_password
    h = hash_password("mypassword")
    assert verify_password("mypassword", h) is True


def test_verify_password_wrong():
    """错误密码验证失败"""
    from auth import hash_password, verify_password
    h = hash_password("mypassword")
    assert verify_password("wrongpassword", h) is False


def test_hash_password_unique_salt():
    """每次哈希使用不同盐"""
    from auth import hash_password
    h1 = hash_password("same")
    h2 = hash_password("same")
    assert h1 != h2
    from auth import verify_password
    assert verify_password("same", h1)
    assert verify_password("same", h2)


def test_password_too_short():
    """密码长度不足 6 位拒绝"""
    from auth import validate_password
    ok, msg = validate_password("12345")
    assert ok is False
    assert "6" in msg


def test_student_id_format():
    """学号格式验证"""
    from auth import validate_student_id
    assert validate_student_id("2024001")[0] is True
    assert validate_student_id("ab")[0] is False  # 太短
    assert validate_student_id("")[0] is False


def test_ensure_csrf_token():
    """CSRF token 生成且稳定"""
    from auth import ensure_csrf_token
    from flask import Flask, session
    app = Flask(__name__)
    app.secret_key = "test"
    with app.test_request_context():
        t1 = ensure_csrf_token()
        t2 = ensure_csrf_token()
        assert t1 == t2  # 同一 session 内稳定
        assert len(t1) == 32  # 16 bytes hex


def test_users_table_exists():
    """users 表存在且有正确结构"""
    from database import QuizDatabase
    import tempfile, os
    with tempfile.TemporaryDirectory() as tmpdir:
        db = QuizDatabase(os.path.join(tmpdir, "test.db"))
        with db.connection() as conn:
            cols = [r[1] for r in conn.execute("PRAGMA table_info(users)").fetchall()]
        for expected in ['id', 'student_id', 'password_hash', 'nickname', 'role', 'created_at']:
            assert expected in cols, f"users 表缺少 {expected} 列"
        db.close()


def test_rate_limits_table_exists():
    """rate_limits 表存在"""
    from database import QuizDatabase
    import tempfile, os
    with tempfile.TemporaryDirectory() as tmpdir:
        db = QuizDatabase(os.path.join(tmpdir, "test.db"))
        with db.connection() as conn:
            tables = [r[0] for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()]
        assert 'rate_limits' in tables
        db.close()


def test_create_user():
    """create_user 正确创建用户"""
    from database import QuizDatabase
    import tempfile, os
    with tempfile.TemporaryDirectory() as tmpdir:
        db = QuizDatabase(os.path.join(tmpdir, "test.db"))
        uid = db.create_user("2024001", "hashed_password", "张三")
        assert uid is not None and uid > 0
        user = db.get_user_by_student_id("2024001")
        assert user is not None
        assert user['nickname'] == '张三'
        assert user['role'] == 'student'
        db.close()


def test_create_user_duplicate():
    """重复学号注册失败"""
    from database import QuizDatabase
    import tempfile, os
    with tempfile.TemporaryDirectory() as tmpdir:
        db = QuizDatabase(os.path.join(tmpdir, "test.db"))
        db.create_user("2024001", "hash1", "张三")
        uid2 = db.create_user("2024001", "hash2", "李四")
        assert uid2 is None
        db.close()


def test_get_user_by_id():
    """get_user_by_id 返回用户信息（不含密码哈希）"""
    from database import QuizDatabase
    import tempfile, os
    with tempfile.TemporaryDirectory() as tmpdir:
        db = QuizDatabase(os.path.join(tmpdir, "test.db"))
        uid = db.create_user("2024002", "hashed", "王五")
        user = db.get_user_by_id(uid)
        assert user is not None
        assert user['student_id'] == '2024002'
        assert 'password_hash' not in user
        db.close()


def test_answer_records_has_user_id_bank_id():
    """answer_records 有 user_id 和 bank_id 列"""
    from database import QuizDatabase
    import tempfile, os
    with tempfile.TemporaryDirectory() as tmpdir:
        db = QuizDatabase(os.path.join(tmpdir, "test.db"))
        with db.connection() as conn:
            cols = [r[1] for r in conn.execute("PRAGMA table_info(answer_records)").fetchall()]
        assert 'user_id' in cols
        assert 'bank_id' in cols
        db.close()


def test_migrate_session_data_idempotent():
    """迁移函数幂等：重复执行不报错"""
    from database import QuizDatabase
    import tempfile, os
    with tempfile.TemporaryDirectory() as tmpdir:
        db = QuizDatabase(os.path.join(tmpdir, "test.db"))
        uid = db.create_user("migrate001", "hash", "迁移测试")
        with db.connection() as conn:
            conn.execute(
                "INSERT INTO answer_records (question_id, user_answer, correct, session_id, bank_id) VALUES (1, 'A', 1, 'sess-abc', 1)"
            )
            conn.execute(
                "INSERT INTO favorites (question_id, session_id, bank_id) VALUES (1, 'sess-abc', 1)"
            )
            conn.execute(
                "INSERT INTO mistakes (question_id, session_id, bank_id) VALUES (1, 'sess-abc', 1)"
            )
        db.migrate_session_data(uid, "sess-abc")
        with db.connection() as conn:
            r = conn.execute("SELECT user_id FROM answer_records WHERE session_id = 'sess-abc'").fetchone()
            assert r['user_id'] == uid
        db.migrate_session_data(uid, "sess-abc")
        db.close()


def test_migrate_session_data_dedup():
    """迁移时去重：已有同题记录不重复迁移"""
    from database import QuizDatabase
    import tempfile, os
    with tempfile.TemporaryDirectory() as tmpdir:
        db = QuizDatabase(os.path.join(tmpdir, "test.db"))
        uid = db.create_user("dedup001", "hash", "去重测试")
        with db.connection() as conn:
            conn.execute(
                "INSERT INTO answer_records (question_id, user_answer, correct, session_id, user_id, bank_id) VALUES (1, 'A', 1, 'old-sess', ?, 1)",
                (uid,)
            )
            conn.execute(
                "INSERT INTO answer_records (question_id, user_answer, correct, session_id, bank_id) VALUES (1, 'B', 0, 'new-sess', 1)"
            )
        db.migrate_session_data(uid, "new-sess")
        with db.connection() as conn:
            count = conn.execute(
                "SELECT COUNT(*) FROM answer_records WHERE session_id = 'new-sess' AND user_id = ?",
                (uid,)
            ).fetchone()[0]
            assert count == 0
        db.close()
