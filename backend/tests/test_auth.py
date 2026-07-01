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
